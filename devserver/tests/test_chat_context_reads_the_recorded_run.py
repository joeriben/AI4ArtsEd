"""The chat's session context is read off the run's entities.

The recorder writes a run's files as final/NN_<type>.<ext>, numbered in the
order they were saved; the chat's context reader asked for 03_input.txt,
06_interception.txt and 02_config_used.json by name and found nothing for a
current run, so the chat carried its placeholders although it was called with
the run id (finding S-007 of the code review of 2026-10-10). The sessions list of the settings page read
01_config_used.json the same way.
"""
import pytest


@pytest.fixture
def storage(monkeypatch, tmp_path):
    import config
    from my_app.services import pipeline_recorder
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr("my_app.routes.chat_routes.JSON_STORAGE_DIR", tmp_path)
    pipeline_recorder._active_recorders.clear()
    return tmp_path


def test_the_context_carries_the_runs_input_interception_and_medium(storage):
    from my_app.services.pipeline_recorder import get_recorder
    from my_app.routes.chat_routes import load_session_context

    recorder = get_recorder("run_ctx_test_1", config_name="bauhaus", safety_level="open",
                            device_id="dev", base_path=storage)
    # The order a run saves in: the config first, then the texts, so none of
    # the three lands on the number the old reader guessed for it.
    recorder.save_entity("config_used", {"output_config": {"media_type": "image"}})
    recorder.save_entity("safety", "passed")
    recorder.save_entity("input", "Ein Haus am See")
    recorder.save_entity("translation_en", "A house by the lake")
    recorder.save_entity("interception", "A Bauhaus house by the lake")

    out = load_session_context("run_ctx_test_1")
    assert out["success"], out
    context = out["context"]
    assert context["input_text"] == "Ein Haus am See"
    assert context["interception_text"] == "A Bauhaus house by the lake"
    assert context["media_type"] == "image"
