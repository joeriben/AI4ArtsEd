"""What ComfyUI's media stations report about themselves.

The platform's node package answers GET /ai4artsed/stations on ComfyUI's
HTTP server (comfyui_nodes/ai4artsed_comfyui/_station_routes.py): for each
station -- Stable Audio 3, ImageBind, MMAudio, HeartMuLa, Hunyuan3D 2, the
media readers -- whether its library imports inside ComfyUI's venv and which
weight folders under models/<station>/ are whole. Asked off the queue, it
puts nothing on the card. Until stage 6 of
the move to ComfyUI the same questions went to the GPU
service's /api/<station>/available routes.

Who asks: the clients' is_available (stable_audio_client, heartmula_client,
hunyuan3d_client, media_analysis_client), the backend status of the
settings page (settings_routes.get_backend_status), the Crossmodal Lab's
available route. Which alias a folder name stands for is the table
config/local_media_weights.json (services/local_media_weights).
"""
import logging
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def read() -> Optional[Dict[str, dict]]:
    """Every station as the package reports it: {station: {"library": bool,
    "installed": [folder names], "error": str}}.

    None when ComfyUI did not answer -- down, restarting, or started without
    the package. A station that cannot be asked says nothing about which
    models exist, so callers keep that apart from a station that answered
    with an empty folder list.
    """
    from config import COMFYUI_URL
    url = f"{COMFYUI_URL}/ai4artsed/stations"
    try:
        # A read cap is right here: the answer is a directory listing and
        # an import check, nothing waits in the queue for it. The first
        # call after a ComfyUI start may still be importing the six
        # libraries (4.5 s for all of them, measured 2026-09-14; the
        # package starts importing them at its own start), so the cap
        # leaves room for that on a cold page cache.
        resp = requests.get(url, timeout=(5, 30))
    except Exception as e:
        logger.warning(f"[MEDIA-STATIONS] ComfyUI did not answer {url}: {e}")
        return None
    if not resp.ok:
        logger.warning(f"[MEDIA-STATIONS] {url} answered {resp.status_code}")
        return None
    try:
        data = resp.json()
    except ValueError:
        logger.warning(f"[MEDIA-STATIONS] {url} answered with no JSON")
        return None
    return data if isinstance(data, dict) else None


def station(name: str, stations: Optional[Dict[str, dict]] = None) -> Optional[dict]:
    """One station's report, or None when ComfyUI did not answer or does not
    list it. `stations` is a report already read, for a caller that asks
    after several stations at once."""
    if stations is None:
        stations = read()
    if not stations:
        return None
    one = stations.get(name)
    return one if isinstance(one, dict) else None


def installed(name: str, stations: Optional[Dict[str, dict]] = None) -> List[str]:
    """The whole weight folders of a station, by folder name; empty when
    the station could not be asked."""
    one = station(name, stations)
    return [str(d) for d in (one or {}).get("installed", [])]


def available(name: str, stations: Optional[Dict[str, dict]] = None) -> bool:
    """Whether the station can run at all: its library imports and at least
    one weight folder is whole."""
    one = station(name, stations)
    return bool(one and one.get("library") and one.get("installed"))


def why_unavailable(name: str, stations: Optional[Dict[str, dict]] = None) -> str:
    """The sentence a chunk raises with when `available` is False: ComfyUI
    did not answer, the station's library does not import in its venv (with
    the import's own error), or no whole weights folder is under
    models/<station>/. Empty when the station is available."""
    if stations is None:
        stations = read()
    if not stations:
        return "ComfyUI did not answer /ai4artsed/stations (down, restarting, or started without the package)"
    one = stations.get(name)
    if not isinstance(one, dict):
        return f"ComfyUI's stations answer lists no station {name!r}"
    if not one.get("library"):
        return f"the station's library does not import in ComfyUI's venv ({one.get('error') or 'no error given'})"
    if not one.get("installed"):
        return f"no whole weights folder under ComfyUI's models/{name}/"
    return ""


def has_folder(name: str, folder: str, stations: Optional[Dict[str, dict]] = None) -> bool:
    """Whether the station's library imports and this folder is whole."""
    one = station(name, stations)
    return bool(one and one.get("library") and folder in (one.get("installed") or []))
