"""
Install Service — GGUF model auto-install from HuggingFace.

Installs models registered in MODEL_CONFIGS (via hf_repo_id/hf_filename) by
spawning huggingface_hub.hf_hub_download in a worker thread and streaming
progress as SSE-friendly event dicts.

MVP constraints:
- Only one install at a time (class-level lock).
- No cancel, no queue. Phase 2 adds those.
- Source-of-truth is MODEL_CONFIGS — the public API takes an alias, never
  a repo_id, so users cannot trigger arbitrary downloads.
"""

import glob
import logging
import os
import shutil
import threading
import time
from typing import Iterator, Dict, Any, Optional

logger = logging.getLogger(__name__)


class _InstallBusyError(RuntimeError):
    pass


class InstallService:
    """Serial GGUF installer. One install at a time."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_alias: Optional[str] = None

    def is_busy(self) -> bool:
        return self._active_alias is not None

    def active_alias(self) -> Optional[str]:
        return self._active_alias

    def precheck(self, alias: str) -> Dict[str, Any]:
        """
        Return {ok: bool, reason: str, approx_mb: int}.
        Validates alias, HF metadata, disk budget. No side effects.
        """
        from services.llm_backend import MODEL_CONFIGS
        config = MODEL_CONFIGS.get(alias)
        if not config:
            return {"ok": False, "reason": f"Unknown model alias: {alias}", "approx_mb": 0}
        if not config.get("hf_repo_id") or not config.get("hf_filename"):
            return {"ok": False, "reason": f"Model {alias} is not installable (no hf_repo_id)", "approx_mb": 0}
        approx_mb = config.get("approx_download_mb", 0)
        dest_dir = os.path.dirname(config["model_path"])
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as e:
            return {"ok": False, "reason": f"Cannot create {dest_dir}: {e}", "approx_mb": approx_mb}
        free_mb = shutil.disk_usage(dest_dir).free // (1024 * 1024)
        # HF keeps .incomplete and final file simultaneously until the move.
        needed_mb = approx_mb * 2
        if free_mb < needed_mb:
            return {
                "ok": False,
                "reason": f"Insufficient disk: need ~{needed_mb} MB, have {free_mb} MB free",
                "approx_mb": approx_mb,
            }
        return {"ok": True, "reason": "", "approx_mb": approx_mb}

    def install(self, alias: str) -> Iterator[Dict[str, Any]]:
        """
        Install generator. Yields SSE-friendly event dicts:
          {"type": "start",    "alias", "file",    "total_mb"}
          {"type": "progress", "alias", "file", "done_mb", "total_mb", "speed_mb_s"}
          {"type": "done",     "alias", "elapsed_s"}
          {"type": "error",    "alias", "message"}

        For VLMs with mmproj, a 2nd start/progress cycle follows the main file.
        """
        from services.llm_backend import MODEL_CONFIGS

        # Precheck (fail before acquiring lock)
        check = self.precheck(alias)
        if not check["ok"]:
            yield {"type": "error", "alias": alias, "message": check["reason"]}
            return

        # Acquire lock atomically
        if not self._lock.acquire(blocking=False):
            yield {
                "type": "error",
                "alias": alias,
                "message": f"Another install is already running ({self._active_alias})",
            }
            return
        self._active_alias = alias

        start_t = time.time()
        try:
            config = MODEL_CONFIGS[alias]
            dest_dir = os.path.dirname(config["model_path"])
            os.makedirs(dest_dir, exist_ok=True)

            # Main file
            yield from self._download_file(
                alias=alias,
                repo_id=config["hf_repo_id"],
                filename=config["hf_filename"],
                local_dir=dest_dir,
                approx_mb=config.get("approx_download_mb", 0),
            )

            # mmproj (VLM only)
            mmproj_name = config.get("hf_mmproj_filename")
            if mmproj_name:
                yield from self._download_file(
                    alias=alias,
                    repo_id=config.get("hf_mmproj_repo_id") or config["hf_repo_id"],
                    filename=mmproj_name,
                    local_dir=dest_dir,
                    approx_mb=0,  # Size unknown in config, UI falls back to done_mb
                )

            elapsed = int(time.time() - start_t)
            logger.info(f"[INSTALL] {alias} finished in {elapsed}s")
            yield {"type": "done", "alias": alias, "elapsed_s": elapsed}

        except Exception as e:
            logger.exception(f"[INSTALL] {alias} failed")
            yield {"type": "error", "alias": alias, "message": str(e)[:500]}
        finally:
            self._active_alias = None
            self._lock.release()

    # ────────────────────────────────────────────────────────────────────

    def _download_file(
        self,
        alias: str,
        repo_id: str,
        filename: str,
        local_dir: str,
        approx_mb: int,
    ) -> Iterator[Dict[str, Any]]:
        """Downloads one file via hf_hub_download in a thread, polls progress."""
        from huggingface_hub import hf_hub_download

        total_mb = approx_mb
        result: Dict[str, Any] = {"path": None, "error": None}

        def worker():
            try:
                result["path"] = hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=local_dir,
                )
            except Exception as e:
                result["error"] = str(e)

        t = threading.Thread(target=worker, daemon=True, name=f"install-{filename}")
        t.start()

        yield {
            "type": "start",
            "alias": alias,
            "file": filename,
            "total_mb": total_mb,
        }

        incomplete_pattern = os.path.join(
            local_dir, ".cache", "huggingface", "download", "*.incomplete"
        )
        last_emit = 0.0
        last_done = 0
        last_time = time.time()

        while t.is_alive():
            # Poll .incomplete file size → bytes downloaded so far
            candidates = glob.glob(incomplete_pattern)
            # Pick the most recently modified (HF writes one per active download)
            done_bytes = 0
            if candidates:
                try:
                    newest = max(candidates, key=os.path.getmtime)
                    done_bytes = os.path.getsize(newest)
                except (OSError, ValueError):
                    done_bytes = 0
            done_mb = done_bytes // (1024 * 1024)

            now = time.time()
            if now - last_emit >= 1.0:
                dt = max(now - last_time, 0.001)
                speed = (done_mb - last_done) / dt
                yield {
                    "type": "progress",
                    "alias": alias,
                    "file": filename,
                    "done_mb": done_mb,
                    "total_mb": total_mb,
                    "speed_mb_s": round(speed, 2),
                }
                last_emit = now
                last_done = done_mb
                last_time = now
            time.sleep(0.5)

        t.join(timeout=5)

        if result["error"]:
            raise RuntimeError(f"HuggingFace download failed for {filename}: {result['error']}")

        # Emit a final progress event at 100% so the UI settles
        if result["path"]:
            try:
                final_mb = os.path.getsize(result["path"]) // (1024 * 1024)
            except OSError:
                final_mb = total_mb
            yield {
                "type": "progress",
                "alias": alias,
                "file": filename,
                "done_mb": final_mb,
                "total_mb": final_mb,
                "speed_mb_s": 0,
            }


# ────────────────────────────────────────────────────────────────────
# Singleton
# ────────────────────────────────────────────────────────────────────

_service: Optional[InstallService] = None


def get_install_service() -> InstallService:
    global _service
    if _service is None:
        _service = InstallService()
    return _service
