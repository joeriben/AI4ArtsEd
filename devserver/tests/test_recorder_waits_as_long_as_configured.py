"""The recorder's own download from ComfyUI waits as long as the configuration
promises every ComfyUI run.

download_and_save_from_comfyui waited a fixed 90 s ("SD3.5 Large: ~18s") while
config.COMFYUI_TIMEOUT says 480; on the fallback branch of the schema routes a
video of several minutes was given up on after 90 s (finding S-053 of the code review of 2026-10-10).
"""
import asyncio


def test_the_wait_is_the_configured_comfyui_timeout(monkeypatch, tmp_path):
    import config
    from my_app.services import comfyui_ws_client as ws
    from my_app.services import pipeline_recorder

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    pipeline_recorder._active_recorders.clear()
    seen = {}

    class Client:
        async def health_check(self):
            return True

        async def wait_for_completion(self, prompt_id, timeout=None):
            seen["timeout"] = timeout
            return None

    monkeypatch.setattr(ws, "get_comfyui_ws_client", lambda *a, **k: Client())
    recorder = pipeline_recorder.get_recorder(
        "run_timeout_test", config_name="c", safety_level="open", device_id="dev",
        base_path=tmp_path)
    out = asyncio.run(recorder.download_and_save_from_comfyui("p-1", "video", "wan22"))
    assert out is None
    assert seen["timeout"] == config.COMFYUI_TIMEOUT
