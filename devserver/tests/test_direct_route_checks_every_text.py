"""Stage 1 of the direct route (/api/schema/pipeline/direct) sees every text
the client sent that reaches an encoder.

Until 2026-10-10 the route checked `prompt` alone; prompt_b, prompt_c, the
concepts of a composable run and the negative prompt went to the chunk as
custom parameters and were encoded unchecked. Stage 3 runs for kids and youth
only, so on open, adult and research these texts reached the encoder without
the §86a and DSGVO checks, and the negative prompt stood on no stage's list at
all (finding S-002 of the code review of 2026-10-10).

Stage 1 itself is replaced by a reader that records what it saw and blocks on
one word; the executor by one that records whether it was reached. The store
is a temporary one, as in test_latent_transport.
"""
from types import SimpleNamespace

import pytest


def _stage1_that_sees(monkeypatch, forbidden="VERBOTEN"):
    import my_app.routes.schema_pipeline_routes as routes
    seen = []

    async def fake(text, safety_level, pipeline_executor, user_language=None):
        seen.append(text)
        if forbidden in text:
            return False, text, f"blocked: {text}", ["fast"]
        return True, text, None, ["fast"]

    monkeypatch.setattr(routes, "execute_stage1_safety_unified", fake)
    return seen


def _executor_that_stops(monkeypatch):
    import my_app.routes.schema_pipeline_routes as routes
    reached = {}

    async def execute_pipeline(**kwargs):
        reached["called"] = True
        return SimpleNamespace(success=False, error="stopped here on purpose",
                               metadata={}, final_output=None)

    monkeypatch.setattr(routes, "pipeline_executor",
                        SimpleNamespace(execute_pipeline=execute_pipeline,
                                        config_loader=SimpleNamespace(
                                            get_config=lambda name: None)))
    return reached


@pytest.fixture
def storage(monkeypatch, tmp_path):
    import config
    from my_app.services import pipeline_recorder as recorder_mod
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    recorder_mod._active_recorders.clear()
    return tmp_path


def _run(field_values):
    from my_app.routes.schema_pipeline_routes import _run_direct_workflow
    data = {"prompt": "a house", "output_config": "sd35_large", "seed": 1}
    data.update(field_values)
    return _run_direct_workflow(data, "open")


@pytest.mark.parametrize("field", ["prompt_b", "prompt_c", "negative_prompt"])
def test_a_hit_in_a_second_text_is_blocked_at_stage_one(monkeypatch, storage, field):
    _stage1_that_sees(monkeypatch)
    reached = _executor_that_stops(monkeypatch)
    payload, status = _run({field: "a VERBOTEN thing"})
    assert status == 403, payload
    assert payload["stage"] == 1
    assert payload["blocked_on"] == field
    assert "called" not in reached, "the run went on past a blocked text"


def test_a_hit_in_a_concept_is_blocked_at_stage_one(monkeypatch, storage):
    _stage1_that_sees(monkeypatch)
    reached = _executor_that_stops(monkeypatch)
    payload, status = _run({"concepts": [{"prompt": "a cat", "weight": 0.5},
                                         {"prompt": "VERBOTEN", "weight": 0.5}]})
    assert status == 403, payload
    assert payload["blocked_on"] == "concept_2"
    assert "called" not in reached


def test_every_text_is_read_when_none_hits(monkeypatch, storage):
    seen = _stage1_that_sees(monkeypatch)
    reached = _executor_that_stops(monkeypatch)
    _run({"prompt_b": "a king", "prompt_c": "a man", "negative_prompt": "no cats",
          "concepts": '[{"prompt": "k1", "weight": 1}, {"prompt": "k2", "weight": 1}]'})
    assert set(seen) == {"a house", "a king", "a man", "no cats", "k1", "k2"}
    assert reached.get("called") is True
