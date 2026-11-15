"""
The lease for a process that is NOT the DevServer.

Inside the DevServer a lease is a call on the gate in the same process
(services/gpu_lease_client.py, which asks no other service). A command-line
runner that drives ComfyUI itself (scripts/knowledge_run.py) is another
process: get_gpu_gate() there builds a gate of its own that knows nothing of
the DevServer's runs, so the per-call lease of comfyui_ws_client serialises
only that process. The lease the running platform sees is taken here, from
the DevServer's gate over HTTP (routes/gpu_gate_routes.py), the same shape
voxcpm_service/server.py and scripts/convert_llm_for_comfyui.py take it in.
"""

import contextlib
import logging
import threading

from my_app.services.gpu_lease_client import GpuBusyError

logger = logging.getLogger(__name__)


def _gate_post(gate_url: str, path: str, body: dict, timeout):
    import requests
    return requests.post(gate_url.rstrip("/") + path, json=body, timeout=timeout)


@contextlib.contextmanager
def gpu_lease_remote(gate_url: str, kind: str, model_id: str, required_mb: float = 0,
                     label: str = "", holder: str = "", heartbeat_interval_s: float = 10):
    """Hold the DevServer gate's slot for the length of the block.

    Fail-closed: a gate that does not answer, or answers without a token,
    raises, and nothing runs."""
    try:
        resp = _gate_post(gate_url, "/api/gate/lease/acquire",
                          {"kind": kind, "model_id": model_id, "required_mb": float(required_mb),
                           "label": label, "holder": holder}, timeout=None)
    except Exception as e:  # noqa: BLE001 - said as the reason nothing runs
        raise RuntimeError(f"the DevServer's gate at {gate_url} did not answer "
                           f"({type(e).__name__}: {e}); nothing was run") from e
    if resp.status_code == 503:
        raise GpuBusyError.from_response(resp)
    token = ""
    try:
        token = str((resp.json() or {}).get("token") or "")
    except Exception:  # noqa: BLE001
        token = ""
    if resp.status_code != 200 or not token:
        raise RuntimeError(f"the DevServer's gate at {gate_url} answered HTTP "
                           f"{resp.status_code} without a lease; nothing was run")
    logger.info("[GPU-LEASE] Acquired %s (%s/%s, remote at %s)", token, kind, model_id, gate_url)
    stop = threading.Event()

    def _keep_alive():
        while not stop.wait(heartbeat_interval_s):
            try:
                r = _gate_post(gate_url, "/api/gate/lease/heartbeat", {"token": token}, timeout=5)
            except Exception as e:  # noqa: BLE001 - a missed beat is asked again
                logger.warning("[GPU-LEASE] heartbeat of %s failed: %s", token, e)
                continue
            if r.status_code == 404:
                logger.error("[GPU-LEASE] the gate no longer knows %s", token)
                return

    threading.Thread(target=_keep_alive, name="gpu-lease-remote-heartbeat", daemon=True).start()
    failed = False
    try:
        yield token
    except BaseException:
        failed = True
        raise
    finally:
        stop.set()
        with contextlib.suppress(Exception):
            _gate_post(gate_url, "/api/gate/lease/release",
                       {"token": token, "failed": failed}, timeout=10)
        logger.info("[GPU-LEASE] Released %s (remote%s)", token, ", failed" if failed else "")
