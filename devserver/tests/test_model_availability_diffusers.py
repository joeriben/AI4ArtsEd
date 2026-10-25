"""The availability service asks the Diffusers station nothing (stage 4).

Every page that shows a ring of configs asks `/api/models/availability`, and
that answer was built by asking the GPU service whether its Diffusers station
was up. Since stage 4 of the move to ComfyUI no config on a surface runs
there, so the question is left out: the flag is False, and the other three
stations are asked as before. A twin whose fallback is a Python chunk reports
unavailable; a twin with a ComfyUI fallback chunk reports what ComfyUI has,
because the backend router runs that chunk when the station fails.
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.services import model_availability_service as mas  # noqa: E402


class _Up:
    async def is_available(self):
        return True


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(mas.ModelAvailabilityService, "_gpu_cache", {
        "diffusers_available": None, "heartmula_available": None,
        "stable_audio_available": None, "hunyuan3d_available": None,
        "timestamp": None, "ttl_seconds": 300,
    })
    import my_app.services.heartmula_client as hm
    import my_app.services.stable_audio_client as sa
    import my_app.services.hunyuan3d_client as h3
    monkeypatch.setattr(hm, "HeartMuLaClient", _Up)
    monkeypatch.setattr(sa, "StableAudioClient", _Up)
    monkeypatch.setattr(h3, "Hunyuan3DClient", _Up)
    return mas.ModelAvailabilityService()


def test_the_diffusers_station_is_left_unasked(service, monkeypatch):
    """Recorded, and answering True: the block this replaced asked the station
    inside `except Exception`, so a stand-in that raised was swallowed there
    and the test held against the very code it was written to exclude."""
    import my_app.services.diffusers_client as dc
    asked = []

    async def is_available(self):
        asked.append(True)
        return True

    monkeypatch.setattr(dc.DiffusersClient, "is_available", is_available)
    status = asyncio.run(service.get_gpu_service_status(force_refresh=True))
    assert asked == []
    assert status["diffusers"] is False
    assert status["heartmula"] is True
    assert status["gpu_service_reachable"] is True


def test_a_twin_with_a_python_fallback_reports_unavailable(service):
    """A Python fallback chunk runs on the station nobody asks, and a file that
    exists is no station that answers. Until 2026-09-14 the existence of the
    file answered True, and sd35_large_turbo_diffusers reported available."""
    for config_id in ("sd35_large_turbo_diffusers",):
        assert asyncio.run(service.check_config_availability(config_id)) is False, config_id


def test_the_workshop_loads_sd35_on_comfyui():
    """`_WORKSHOP_LOAD_MAP` is the one table the settings' workshop loads by.
    Stage 4 moved sd35_large from the Diffusers station's /load to a ComfyUI
    chunk, and no declaration in the measuring script can see a revert of
    that row: the literal stays in the module for the preload route."""
    from my_app.routes.settings_routes import _WORKSHOP_LOAD_MAP
    row = _WORKSHOP_LOAD_MAP["sd35_large"]
    assert row["type"] == "comfyui" and "path" not in row
