"""The step the card is on, read by the polling surfaces, and the cancel that
reaches the Diffusers station for a Diffusers run alone.

Stage 4 of the move to ComfyUI: the
DevServer's housekeeping of a run - which step it is on, which station a
cancel goes to - stopped asking the GPU service. The step comes from the
ComfyUI client, which hears every progress message of the prompt it tracks;
the cancel reads the run's config to know where the run is.
"""
import sys
import types

from file_modules import DEVSERVER

if str(DEVSERVER) not in sys.path:
    sys.path.insert(0, str(DEVSERVER))


def test_the_step_reader_hears_the_tracked_prompt_and_keeps_the_pair_after_it():
    from my_app.services import comfyui_ws_client as ws
    ws.note_step("p1", 3, 25)
    assert ws.step_now() == {"step": 3, "total_steps": 25, "active": True}
    ws.end_step("other")  # another prompt's end leaves the running one alone
    assert ws.step_now()["active"] is True
    ws.end_step("p1")
    assert ws.step_now() == {"step": 3, "total_steps": 25, "active": False}


def test_the_settings_route_answers_the_step_reader():
    from flask import Flask
    from my_app.routes import settings_routes
    from my_app.services import comfyui_ws_client as ws
    ws.note_step("p2", 7, 30)
    app = Flask(__name__)
    app.register_blueprint(settings_routes.settings_bp)
    answer = app.test_client().get("/api/settings/generation-progress")
    assert answer.status_code == 200
    assert answer.get_json() == {"step": 7, "total_steps": 30, "active": True}


def test_a_cancel_reaches_the_diffusers_station_for_a_diffusers_run_alone(monkeypatch):
    import requests
    from my_app.routes import schema_pipeline_routes as spr

    posted = []
    monkeypatch.setattr(requests, "post",
                        lambda url, **kw: posted.append(url) or types.SimpleNamespace(ok=True))

    class Loader:
        def get_config(self, name):
            return types.SimpleNamespace(meta={"backend_type": name.split(":")[0]})

    monkeypatch.setattr(spr, "pipeline_executor", types.SimpleNamespace(config_loader=Loader()))
    with spr._generation_tracker_lock:
        spr._active_generations["dev-comfy"] = {
            "run_id": "r1", "output_config": "comfyui:x", "phase": "generating", "ts": 0}
        spr._active_generations["dev-diff"] = {
            "run_id": "r2", "output_config": "diffusers:x", "phase": "generating", "ts": 0}
    try:
        spr._cancel_diffusers_for("dev-comfy")
        assert posted == []
        spr._cancel_diffusers_for("dev-diff")
        assert len(posted) == 1 and posted[0].endswith("/cancel")
    finally:
        with spr._generation_tracker_lock:
            spr._active_generations.pop("dev-comfy", None)
            spr._active_generations.pop("dev-diff", None)
    assert spr._backend_of(None) is None
    assert spr._backend_of("comfyui:y") == "comfyui"
