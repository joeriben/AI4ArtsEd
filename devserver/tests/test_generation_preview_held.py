"""A picture shown while it is being made belongs to its run, and at kids and
youth it does not go out.

The card serves one generation at a time. The GPU service kept ONE progress for
all of them, so a run waiting for the card polled the steps and the picture of
the run that held it, and the generation stream sent them to its own surface.
The poll now names its run. And a preview has no verdict: at kids and youth a
picture goes out only with one, so there the stream says how far the run is and
shows nothing (safety_gate.preview_for). 2026-10-31.

Nothing here reaches a model, a GPU or ComfyUI: every backend is a stand-in, the
wiring of test_sse_silent_windows.

Run: python3 -m pytest devserver/tests/test_generation_preview_held.py -q
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes import schema_pipeline_routes as spr
from test_sse_silent_windows import Opened, _generation_data, _wire_the_generation
from test_sse_transport_sites import event_payloads

PICTURE = "AAAA"


class NoEncoders:
    """The station says nothing about the encoders; the run goes on."""
    status_code = 503

    def json(self):
        return {}


def run_at(monkeypatch, level):
    """The generation stream at `level`, beside a card that is drawing: every
    poll of its progress answers step 3 of 25, with a picture."""
    asked = []
    polled = threading.Event()

    class Progress:
        def json(self):
            return {"active": True, "step": 3, "total_steps": 25, "preview": PICTURE}

    class Card:
        def post(self, *a, **kw):
            return NoEncoders()

        def get(self, url, params=None, timeout=None):
            asked.append(params)
            polled.set()
            return Progress()

    async def generated(**kw):
        # The run stays on the card until the stream has asked how far it is.
        polled.wait(timeout=10)
        return {"success": True, "run_id": kw.get("run_id"), "loras": [],
                "media_output": {"media_type": "image", "url": "stand-in"}}

    _wire_the_generation(monkeypatch, Opened())
    monkeypatch.setattr(spr, "requests", Card())
    monkeypatch.setattr(spr, "execute_stage4_generation_only", generated)
    monkeypatch.setattr(spr, "_pictures_of_run", lambda *a, **kw: ([], None))
    payloads = event_payloads("".join(spr.execute_generation_streaming(_generation_data(), level)))
    run_id = next(p["run_id"] for p in payloads if "run_id" in p)
    progress = [p for p in payloads if "total_steps" in p]
    return progress, asked, run_id


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_where_pictures_are_checked_the_stream_shows_how_far_and_no_picture(monkeypatch, level):
    progress, _asked, _run_id = run_at(monkeypatch, level)
    assert progress, "the stream said nothing about the progress"
    assert [(p["step"], p["preview"]) for p in progress] == [(3, None)] * len(progress)


@pytest.mark.parametrize("level", ["adult", "research"])
def test_where_no_picture_is_checked_the_preview_goes_out(monkeypatch, level):
    progress, _asked, _run_id = run_at(monkeypatch, level)
    assert progress, "the stream said nothing about the progress"
    assert progress[0]["preview"] == f"data:image/jpeg;base64,{PICTURE}"


def test_the_stream_asks_for_the_progress_of_its_own_run(monkeypatch):
    _progress, asked, run_id = run_at(monkeypatch, "adult")
    assert asked and all(params == {"run_label": run_id} for params in asked)
