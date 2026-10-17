"""Installing a local language model from the settings page.

The alias names a row of config/local_llm_weights.json (services/
local_llm_weights); the row names the Hugging Face repository, and the
snapshot is written to <ComfyUI>/models/llm/<dir>, where ComfyUI's node lists
it. The GPU service's install_service.py did this for the GGUF registry until
stage 3 of the move to ComfyUI; the events this module
yields are the ones that service streamed, so the surface's reader
(useModelInstall) reads what it read:

  {"type": "start",    "alias", "file", "total_mb"}
  {"type": "progress", "alias", "file", "done_mb", "total_mb", "speed_mb_s"}
  {"type": "done",     "alias", "elapsed_s"}
  {"type": "error",    "alias", "message"}

The download lands in a staging folder beside the destination
(.incoming-<dir>, same filesystem) and is renamed into place once the snapshot
is whole (_snapshot.complete, the same test the node applies), so a folder
under models/llm/ either holds a whole model or is absent. A download that
was cut off keeps its staging folder, and the next install of the same alias
takes it up: the files that were finished stay, and the part that was in
flight is fetched again -- over plain HTTP from the byte it stopped at, over
Hugging Face's Xet storage (hf_xet, the case for the repositories in the
table) from the chunk cache under ~/.cache/huggingface/xet, the part itself
rewritten from the start.

The public API takes an alias, never a repository id, so nothing on the
surface can trigger an arbitrary download. One install at a time, and the
download runs to its end once started: a surface that stops reading the
events leaves the download running, and the next request finds it busy.
"""
import logging
import os
import threading
import time
from typing import Any, Dict, Iterator, Optional

from my_app.services import local_llm_weights as weights
from my_app.services.local_install_disk import (bytes_on_disk as _bytes_on_disk,
                                                 free_bytes_under as _free_bytes_under)

logger = logging.getLogger(__name__)

_STAGING_PREFIX = ".incoming-"



class LocalLLMInstaller:
    def __init__(self):
        # Held by the download thread from its start to its end, whoever is
        # still reading the events; released in that thread.
        self._lock = threading.Lock()
        self._active_alias: Optional[str] = None

    def is_busy(self) -> bool:
        return self._active_alias is not None

    def active_alias(self) -> Optional[str]:
        return self._active_alias

    def precheck(self, alias: str) -> Dict[str, Any]:
        """{ok, reason, approx_mb}: the alias, the token a gated repository
        needs, the disk. No side effects."""
        e = weights.entry(alias)
        if e is None:
            return {"ok": False, "reason": f"Unknown model alias: {alias}", "approx_mb": 0}
        approx_mb = int(round(float(e.get("size_gb") or 0) * 1024))
        if weights.is_installed(alias):
            return {"ok": False, "reason": f"{alias} is already installed", "approx_mb": approx_mb}
        if e.get("gated"):
            from huggingface_hub import get_token
            if not get_token():
                return {
                    "ok": False,
                    "reason": (f"{e['repo']} is gated: it needs a Hugging Face account that "
                               f"accepted the model's licence, and its token as HF_TOKEN in the "
                               f"DevServer's environment"),
                    "approx_mb": approx_mb,
                }
        root = weights.models_root()
        final = root / e["dir"]
        if final.exists():
            # In place and not whole (is_installed said so): a download that
            # was renamed before the test, or a folder somebody copied in.
            # Nothing here deletes a folder it did not write; the operator
            # completes it or takes it away, and this says which folder.
            return {
                "ok": False,
                "reason": (f"{final} exists and holds no whole snapshot of {e['repo']} "
                           f"(config.json, every shard the index names, no '.incomplete' part); "
                           f"complete it by hand or move it away, then install again"),
                "approx_mb": approx_mb,
            }
        if self._active_alias is not None:
            return {"ok": False, "reason": f"Another install is already running ({self._active_alias})",
                    "approx_mb": approx_mb}
        free_mb = _free_bytes_under(root) // (1024 * 1024)
        already_mb = _bytes_on_disk(str(root / f"{_STAGING_PREFIX}{e['dir']}"), in_flight=False) \
            // (1024 * 1024)
        needed_mb = max(0, int(approx_mb * 1.1) - already_mb)
        if free_mb < needed_mb:
            return {
                "ok": False,
                "reason": f"Insufficient disk: need ~{needed_mb} MB, have {free_mb} MB free",
                "approx_mb": approx_mb,
            }
        return {"ok": True, "reason": "", "approx_mb": approx_mb}

    def install(self, alias: str) -> Iterator[Dict[str, Any]]:
        check = self.precheck(alias)
        if not check["ok"]:
            yield {"type": "error", "alias": alias, "message": check["reason"]}
            return
        if not self._lock.acquire(blocking=False):
            yield {"type": "error", "alias": alias,
                   "message": f"Another install is already running ({self._active_alias})"}
            return
        self._active_alias = alias
        e = weights.entry(alias)
        root = weights.models_root()
        staging = str(root / f"{_STAGING_PREFIX}{e['dir']}")
        final = str(root / e["dir"])
        total_mb = check["approx_mb"]
        start_t = time.time()
        outcome: Dict[str, Any] = {"error": None}

        def worker():
            # The whole install, on this thread, with the lock: download,
            # the test that the snapshot is whole, the rename into place.
            # Whoever stops reading the events leaves it to finish.
            try:
                os.makedirs(root, exist_ok=True)
                self._fetch(e, staging)
                if not _whole(staging):
                    raise RuntimeError(
                        f"the download of {e['repo']} ended and the snapshot in {staging} is not "
                        f"whole (config.json, every shard the index names, no '.incomplete' part); "
                        f"the folder is kept, and the next install takes it up")
                os.replace(staging, final)
                logger.info(f"[LLM-INSTALL] {e['repo']} -> {final}")
            except Exception as exc:
                logger.exception(f"[LLM-INSTALL] {alias} failed")
                outcome["error"] = str(exc)[:500]
            finally:
                self._active_alias = None
                self._lock.release()

        # Started before the first event goes out: from here on the thread
        # owns the lock, and a reader that leaves after any event leaves a
        # download that ends by itself.
        t = threading.Thread(target=worker, daemon=True, name=f"llm-install-{alias}")
        t.start()
        yield {"type": "start", "alias": alias, "file": e["dir"], "total_mb": total_mb}

        last_done = _bytes_on_disk(staging) // (1024 * 1024)
        last_time = time.time()
        while t.is_alive():
            t.join(timeout=1.0)
            now = time.time()
            done_mb = _bytes_on_disk(staging) // (1024 * 1024)
            speed = (done_mb - last_done) / max(now - last_time, 0.001)
            yield {"type": "progress", "alias": alias, "file": e["dir"],
                   "done_mb": done_mb, "total_mb": total_mb, "speed_mb_s": round(speed, 2)}
            last_done, last_time = done_mb, now

        if outcome["error"]:
            yield {"type": "error", "alias": alias, "message": outcome["error"]}
            return
        final_mb = _bytes_on_disk(final) // (1024 * 1024)
        yield {"type": "progress", "alias": alias, "file": e["dir"],
               "done_mb": final_mb, "total_mb": final_mb, "speed_mb_s": 0}
        elapsed = int(time.time() - start_t)
        logger.info(f"[LLM-INSTALL] {alias} finished in {elapsed}s")
        yield {"type": "done", "alias": alias, "elapsed_s": elapsed}

    @staticmethod
    def _fetch(e: dict, staging: str) -> None:
        """snapshot_download into the staging folder; raises with the hub's
        own words when it fails."""
        from huggingface_hub import snapshot_download
        try:
            path = snapshot_download(
                repo_id=e["repo"],
                local_dir=staging,
                ignore_patterns=e.get("ignore") or None,
            )
        except Exception as exc:
            raise RuntimeError(f"Hugging Face download of {e['repo']} failed: {exc}") from exc
        if not path or not os.path.isdir(path):
            raise RuntimeError(f"Hugging Face reported no snapshot for {e['repo']}; nothing was written")


def _whole(folder: str) -> bool:
    return weights.folder_is_whole(folder)


_installer: Optional[LocalLLMInstaller] = None


def get_local_llm_installer() -> LocalLLMInstaller:
    global _installer
    if _installer is None:
        _installer = LocalLLMInstaller()
    return _installer


def _role_models() -> list:
    """The aliases the model roles of the settings name as local models, and
    the one the look at images runs on, each once, in the order of the roles
    (download_llm_models.sh installs these when it is given no alias).

    The look's model is named by no role on the settings page
    (llm_service.view_vlm_model). It used to be installed only because the
    image check's role, VLM_SAFETY_MODEL, happened to name the same model;
    that role went with the move to one classifier, whose weights belong to
    the GPU service and stand outside this table."""
    import config
    from my_app.routes.chat_routes import get_user_setting
    from my_app.routes.settings_routes import DSGVO_REVIEWED_FIELDS
    from my_app.services.llm_service import llm_service
    values = [get_user_setting(key, default=getattr(config, key, "")) or ""
              for key in DSGVO_REVIEWED_FIELDS]
    values.append(llm_service.view_vlm_model())
    aliases = []
    for value in values:
        if weights.entry(value) is not None:
            alias = weights.resolve_alias(value)
            if alias not in aliases:
                aliases.append(alias)
    return aliases


def main(argv: list) -> int:
    """`python -m my_app.services.local_llm_install [alias ...]` from devserver/:
    installs the aliases named, or, with none, every local model a model role
    of the settings names and the look's model (_role_models). One line per
    second while a download runs; the
    exit code is the number of aliases that were not installed."""
    aliases = [a[len(weights.LOCAL_PREFIX):] if a.startswith(weights.LOCAL_PREFIX) else a
               for a in argv] or _role_models()
    if not aliases:
        print("no local model to install: no alias given and no model role names one")
        return 0
    failed = 0
    installer = get_local_llm_installer()
    for alias in aliases:
        if weights.is_installed(alias):
            print(f"{alias}: installed ({weights.weights_dir(alias)})")
            continue
        print(f"{alias}: installing")
        for event in installer.install(alias):
            if event["type"] == "progress":
                print(f"  {event['done_mb']} / {event['total_mb']} MB  {event['speed_mb_s']} MB/s", flush=True)
            elif event["type"] == "error":
                print(f"{alias}: FAILED: {event['message']}")
                failed += 1
            elif event["type"] == "done":
                print(f"{alias}: done in {event['elapsed_s']} s")
    return failed


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
