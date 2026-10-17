"""Installing the weights of a media station.

The alias names a row of config/local_media_weights.json (services/
local_media_weights); the row says where the weights come from and the folder
under <ComfyUI>/models/<station>/ they are written to, where the station's
node lists them. Until stage 6 of the move to ComfyUI each
station had a way of its own: MMAudio's own installer into gpu_service/
weights, huggingface-cli commands for HeartMuLa into heartlib/ckpt, the
Hugging Face cache for the readers and for Stable Audio, a wget for ImageBind.
The events this module yields are the ones services/local_llm_install yields
for the language models, so a reader of one reads the other:

  {"type": "start",    "alias", "file", "total_mb"}
  {"type": "progress", "alias", "file", "done_mb", "total_mb", "speed_mb_s"}
  {"type": "done",     "alias", "elapsed_s"}
  {"type": "error",    "alias", "message"}

Four kinds of source, the table's 'kind':
  snapshot  a Hugging Face repository, minus its 'ignore' patterns
  files     named files of a repository, at their path in the repository
  url       one file from a URL
  parts     several repositories into sub-folders ('.' is the folder itself)
'cached' names repositories the station's library loads by name from the
Hugging Face cache (~/.cache/huggingface/hub, HF_HOME to move it); they are
fetched into that cache after the weights, so a fresh installation runs
without a download on first use.

The download lands in a staging folder beside the destination
(.incoming-<dir>, same filesystem) and is renamed into place once the folder
is whole (local_media_weights.folder_is_whole, the node package's own test,
which the station applies when it lists its folders), so a folder under
models/<station>/ either holds whole weights or is absent. A download that was cut off keeps its staging
folder, and the next install of the same alias takes it up: the files that
were finished stay, and the part that was in flight is fetched again: a URL
over plain HTTP from the byte it stopped at (the Range request of
_fetch_url), a repository file over Hugging Face's Xet storage (hf_xet) from
the chunk cache under ~/.cache/huggingface/xet, the part itself rewritten
from the start.

The public API takes an alias, never a repository id or a URL, so nothing on
a surface can trigger an arbitrary download. One install at a time, and the
download runs to its end once started: a reader that stops reading the
events leaves the download running, and the next request finds it busy.
"""
import logging
import os
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

from my_app.services import local_media_weights as weights
from my_app.services.local_install_disk import (bytes_on_disk as _bytes_on_disk,
                                                 free_bytes_under as _free_bytes_under)

logger = logging.getLogger(__name__)

_STAGING_PREFIX = ".incoming-"
_URL_PART_SUFFIX = ".incomplete"

# What no library of the stations reads from a cached repository: the Flax,
# TensorFlow, ONNX and Rust exports some repositories publish beside the
# PyTorch weights (xlm-roberta-base carries 4.1 GB of them next to 1.1 GB of
# safetensors). The PyTorch weights stay in both formats where a repository
# has both; which one the library picks is the library's business.
_CACHE_IGNORE = ("*.msgpack", "*.h5", "*.onnx", "onnx/*", "*.tflite", "*.ot", "*.ckpt")



def _source(e: dict) -> str:
    """The source of an entry as a message names it."""
    kind = e.get("kind")
    if kind == "url":
        return e["url"]
    if kind == "parts":
        return ", ".join(e["parts"].values())
    return e.get("repo", "?")


def _gated_repos(e: dict) -> List[str]:
    """The repositories of an entry the table marks gated (a licence to
    accept on Hugging Face, the token as HF_TOKEN)."""
    if not e.get("gated"):
        return []
    if e.get("kind") == "parts":
        return list(e["parts"].values())
    return [e["repo"]] if e.get("repo") else []


class LocalMediaInstaller:
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
        gated = _gated_repos(e)
        if gated:
            from huggingface_hub import get_token
            if not get_token():
                return {
                    "ok": False,
                    "reason": (f"{', '.join(gated)} is gated: it needs a Hugging Face account that "
                               f"accepted the model's licence, and its token as HF_TOKEN in the "
                               f"DevServer's environment"),
                    "approx_mb": approx_mb,
                }
        root = weights.station_root(e["station"])
        final = root / e["dir"]
        if final.exists():
            # In place and not whole (is_installed said so): a download that
            # was renamed before the test, or a folder somebody copied or
            # linked in. Nothing here deletes a folder it did not write; the
            # operator completes it or takes it away, and this says which
            # folder and what it lacks.
            return {
                "ok": False,
                "reason": (f"{final} exists and holds no whole copy of {_source(e)}: "
                           f"{weights.folder_missing(e['station'], final)}; complete it by hand "
                           f"or move it away, then install again"),
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
        root = weights.station_root(e["station"])
        staging = str(root / f"{_STAGING_PREFIX}{e['dir']}")
        final = str(root / e["dir"])
        total_mb = check["approx_mb"]
        start_t = time.time()
        # What the progress events name as the file: the folder while the
        # weights come in, the repository while a cached one does.
        state: Dict[str, Any] = {"error": None, "file": e["dir"]}

        def worker():
            # The whole install, on this thread, with the lock: download,
            # the test that the folder is whole, the cached repositories,
            # the rename into place. Whoever stops reading the events leaves
            # it to finish.
            try:
                os.makedirs(root, exist_ok=True)
                self._fetch(e, staging)
                lacking = weights.folder_missing(e["station"], staging)
                if lacking is not None:
                    raise RuntimeError(
                        f"the download of {_source(e)} ended and the folder {staging} is not "
                        f"whole: {lacking}; the folder is kept, and the next install takes it up")
                self._fetch_cached(e, state)
                os.replace(staging, final)
                logger.info(f"[MEDIA-INSTALL] {_source(e)} -> {final}")
            except Exception as exc:
                logger.exception(f"[MEDIA-INSTALL] {alias} failed")
                state["error"] = str(exc)[:500]
            finally:
                self._active_alias = None
                self._lock.release()

        # Started before the first event goes out: from here on the thread
        # owns the lock, and a reader that leaves after any event leaves a
        # download that ends by itself.
        t = threading.Thread(target=worker, daemon=True, name=f"media-install-{alias}")
        t.start()
        yield {"type": "start", "alias": alias, "file": e["dir"], "total_mb": total_mb}

        last_done = _bytes_on_disk(staging) // (1024 * 1024)
        last_time = time.time()
        while t.is_alive():
            t.join(timeout=1.0)
            now = time.time()
            # Once the folder is renamed into place the staging path is
            # empty; the last count stands until the final one below.
            done_mb = (_bytes_on_disk(staging) // (1024 * 1024)
                       if os.path.isdir(staging) else last_done)
            speed = (done_mb - last_done) / max(now - last_time, 0.001)
            yield {"type": "progress", "alias": alias, "file": state["file"],
                   "done_mb": done_mb, "total_mb": total_mb, "speed_mb_s": round(speed, 2)}
            last_done, last_time = done_mb, now

        if state["error"]:
            yield {"type": "error", "alias": alias, "message": state["error"]}
            return
        final_mb = _bytes_on_disk(final) // (1024 * 1024)
        yield {"type": "progress", "alias": alias, "file": e["dir"],
               "done_mb": final_mb, "total_mb": final_mb, "speed_mb_s": 0}
        elapsed = int(time.time() - start_t)
        logger.info(f"[MEDIA-INSTALL] {alias} finished in {elapsed}s")
        yield {"type": "done", "alias": alias, "elapsed_s": elapsed}

    @staticmethod
    def _fetch(e: dict, staging: str) -> None:
        """The weights into the staging folder, by the entry's kind; raises
        with the source's own words when it fails."""
        kind = e.get("kind")
        if kind == "snapshot":
            _fetch_snapshot(e["repo"], staging, e.get("ignore"))
        elif kind == "parts":
            for sub, repo in e["parts"].items():
                target = staging if sub == "." else os.path.join(staging, sub)
                _fetch_snapshot(repo, target, e.get("ignore"))
        elif kind == "files":
            from huggingface_hub import hf_hub_download
            for name in e["files"]:
                try:
                    hf_hub_download(repo_id=e["repo"], filename=name, local_dir=staging)
                except Exception as exc:
                    raise RuntimeError(
                        f"Hugging Face download of {name} from {e['repo']} failed: {exc}") from exc
        elif kind == "url":
            # The table's size is what the file weighs, read off the file;
            # half of it is the floor under which what came back is not
            # the file (an error page with a 200, a truncated body a
            # server sent no length for).
            _fetch_url(e["url"], os.path.join(staging, e["file"]),
                       at_least=int(float(e.get("size_gb", 0)) * 1e9 / 2))
        else:
            raise RuntimeError(f"the table names no way to fetch kind {kind!r}")

    @staticmethod
    def _fetch_cached(e: dict, state: Dict[str, Any]) -> None:
        """The repositories the station's library loads by name, into the
        Hugging Face cache; what is there already is left alone."""
        from huggingface_hub import snapshot_download
        for repo in e.get("cached") or []:
            state["file"] = repo
            try:
                snapshot_download(repo_id=repo, ignore_patterns=list(_CACHE_IGNORE))
            except Exception as exc:
                raise RuntimeError(
                    f"Hugging Face download of {repo} into the cache failed: {exc}") from exc
        state["file"] = e["dir"]


def _fetch_snapshot(repo: str, target: str, ignore: Optional[List[str]]) -> None:
    from huggingface_hub import snapshot_download
    try:
        path = snapshot_download(repo_id=repo, local_dir=target, ignore_patterns=ignore or None)
    except Exception as exc:
        raise RuntimeError(f"Hugging Face download of {repo} failed: {exc}") from exc
    if not path or not os.path.isdir(path):
        raise RuntimeError(f"Hugging Face reported no snapshot for {repo}; nothing was written")


def _fetch_url(url: str, target: str, at_least: int = 0) -> None:
    """One file over HTTP into `target`, written as <target>.incomplete and
    renamed when the body ended where the server said it would. A part that
    is there from an earlier attempt is continued with a Range request when
    the server honours it (206), and rewritten from the start when it does
    not (200). A 416 says the part already reaches the file's end, and its
    Content-Range names that end: a part that is longer than the file is not
    the file and is taken away, so the next attempt starts over. A file
    shorter than `at_least` bytes is refused as not the file. No read limit
    on the body: a download runs at the speed of the line, and the platform
    sets no clock on that."""
    import requests
    part = target + _URL_PART_SUFFIX
    os.makedirs(os.path.dirname(target), exist_ok=True)
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    try:
        with requests.get(url, headers=headers, stream=True, timeout=(10, None)) as r:
            if r.status_code == 416:
                # The part reaches the file's end or past it; the server
                # says which in Content-Range: bytes */<total>.
                total = _content_range_total(r.headers.get("Content-Range"))
                if total is not None and have > total:
                    os.remove(part)
                    raise RuntimeError(
                        f"the part of {url} held {have} bytes and the file has {total}; the part "
                        f"was not this file and was taken away, the next install starts over")
                expected = total if total is not None else have
            else:
                r.raise_for_status()
                mode = "ab" if (have and r.status_code == 206) else "wb"
                if mode == "wb":
                    have = 0
                length = r.headers.get("Content-Length")
                expected = have + int(length) if length else None
                with open(part, mode) as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
    except requests.RequestException as exc:
        raise RuntimeError(f"download of {url} failed: {exc}") from exc
    size = os.path.getsize(part)
    if expected is not None and size != expected:
        raise RuntimeError(
            f"download of {url} ended after {size} of {expected} bytes; the part is kept, "
            f"and the next install takes it up")
    if size < at_least:
        os.remove(part)
        raise RuntimeError(
            f"download of {url} ended after {size} bytes where the file weighs at least "
            f"{at_least}; what came back was not the file and was taken away")
    os.replace(part, target)


def _content_range_total(header: Optional[str]) -> Optional[int]:
    """The total of a Content-Range header ("bytes */123", "bytes 0-9/123"),
    None where there is none or it is '*'."""
    if not header or "/" not in header:
        return None
    total = header.rsplit("/", 1)[1].strip()
    return int(total) if total.isdigit() else None


_installer: Optional[LocalMediaInstaller] = None


def get_local_media_installer() -> LocalMediaInstaller:
    global _installer
    if _installer is None:
        _installer = LocalMediaInstaller()
    return _installer


def _aliases_of(argv: list) -> List[str]:
    """The aliases the arguments name: an alias as such, a station by every
    alias of the station; none names every alias of the table. Each once, in
    the order given. An argument that is neither is kept, so the install
    reports it unknown."""
    if not argv:
        return list(weights.models())
    aliases: List[str] = []
    for arg in argv:
        named = weights.aliases_of_station(arg) if arg in weights.stations() else [arg]
        for alias in named:
            if alias not in aliases:
                aliases.append(alias)
    return aliases


def main(argv: list) -> int:
    """`python -m my_app.services.local_media_install [alias|station ...]` from
    devserver/: installs the aliases named, every alias of a station named,
    or, with nothing named, every model of the table. One line per second
    while a download runs; the exit code is the number of aliases that were
    not installed."""
    failed = 0
    installer = get_local_media_installer()
    for alias in _aliases_of(argv):
        if weights.is_installed(alias):
            print(f"{alias}: installed ({weights.weights_dir(alias)})")
            continue
        print(f"{alias}: installing")
        for event in installer.install(alias):
            if event["type"] == "progress":
                print(f"  {event['done_mb']} / {event['total_mb']} MB  {event['speed_mb_s']} MB/s"
                      f"  ({event['file']})", flush=True)
            elif event["type"] == "error":
                print(f"{alias}: FAILED: {event['message']}")
                failed += 1
            elif event["type"] == "done":
                print(f"{alias}: done in {event['elapsed_s']} s")
    return failed


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
