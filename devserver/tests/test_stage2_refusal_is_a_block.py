"""A model-written refusal is a block at stage 2, said by the backend.

The safety prefix tells the model to answer with one sentence instead of
transforming (instruction_selector.SAFETY_REFUSAL_SENTENCE). Until 2026-10-10
that sentence travelled as a successful stage-2 result: the stage-2 route
answered it with success and the run carried it on as the interception, and
two comparison surfaces matched the sentence's wording themselves, from a copy
of the constant (finding S-015 of the code review of 2026-10-10). The backend reads the sentence in one place now and
answers the block every surface already reads.
"""
import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         CHECKPOINT_RESULT, Verdict)
from schemas.engine.instruction_selector import SAFETY_REFUSAL_SENTENCE, is_safety_refusal

SCHEMA = "bauhaus"
HARMLESS = "Ein Haus steht in einer Landschaft."
REFUSAL = SAFETY_REFUSAL_SENTENCE + " Bitte formuliere es anders."


class _Recorder:
    """Takes every call a run makes on its record and keeps nothing."""
    metadata = {"entities": [], "models_used": {}}

    def output_entities(self, *a, **kw):
        return []

    def __getattr__(self, name):
        return lambda *a, **kw: None


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    return app.test_client()


@pytest.fixture
def checks_waved_through(monkeypatch):
    """The intake and the check at the result answer safe; they record what
    the check at the result was asked."""
    asked = []

    def _result(text, *, level, field="text"):
        asked.append(text)
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(R, "check_intake_texts",
                        lambda fields, *, level: Verdict(True, CHECKPOINT_INTAKE, level))
    monkeypatch.setattr(R, "check_result_text", _result)
    return asked


def _stage2_answers(monkeypatch, text):
    async def fake(**kwargs):
        return R._Stage2Answer(success=True, final_output=text)

    monkeypatch.setattr(R, "execute_stage2_with_optimization", fake)


def test_the_sentence_is_read_in_one_place():
    assert is_safety_refusal(REFUSAL)
    assert is_safety_refusal("  hierbei kann ich dich nicht unterstützen  ")
    assert not is_safety_refusal("a Bauhaus house by the lake")
    assert not is_safety_refusal(None)
    assert not is_safety_refusal({"structured": True})


@pytest.mark.parametrize("words", [
    REFUSAL,
    # Words that once marked a check that could not be carried out: the model
    # answered, and what it answered is a refusal, not a fault.
    SAFETY_REFUSAL_SENTENCE + " Das System reagiert nicht auf diese Bitte.",
])
def test_the_stage2_route_answers_a_block(client, checks_waved_through, monkeypatch, words):
    _stage2_answers(monkeypatch, words)
    response = client.post('/api/schema/pipeline/stage2', json={'schema': SCHEMA, 'input_text': HARMLESS})
    assert response.status_code == 403, response.get_data(as_text=True)
    body = response.get_json()
    assert body['success'] is False
    assert body['status'] == 'blocked'
    assert body['safety_block']['checkpoint'] == 'refusal'
    assert body['safety_block']['reason_key'] == 'refusal'
    assert body['safety_block']['field'] == 'interception'
    assert SAFETY_REFUSAL_SENTENCE.rstrip('.') in body['reason']
    # The refusal is the model's own; the check at the result is not asked about it.
    assert checks_waved_through == []


def test_a_written_perspective_still_passes(client, checks_waved_through, monkeypatch):
    _stage2_answers(monkeypatch, "a Bauhaus house by the lake")
    response = client.post('/api/schema/pipeline/stage2', json={'schema': SCHEMA, 'input_text': HARMLESS})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()['stage2_result'] == "a Bauhaus house by the lake"


def test_the_full_run_stops_at_stage_2(monkeypatch, tmp_path, checks_waved_through):
    """The run that goes on to generate: a refusal ends it before the check
    before the model and stage 4 see anything."""
    import config
    from my_app.services import pipeline_recorder
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    pipeline_recorder._active_recorders.clear()
    R.init_schema_engine()

    reached = {"before_model": [], "stage4": []}

    def before_model(texts, *, level, **kw):
        reached["before_model"].append(dict(texts))
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    async def stage4(**kw):
        reached["stage4"].append(kw)
        return {"success": False, "error": "stub: no model in this test", "run_id": kw.get("run_id")}

    monkeypatch.setattr(R, "check_before_model", before_model)
    monkeypatch.setattr(R, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    _stage2_answers(monkeypatch, REFUSAL)

    payload, status = R._run_interception_pipeline(
        {"schema": SCHEMA, "input_text": HARMLESS, "output_config": "sd35_large",
         "device_id": "test-stage2-refusal"}, "kids")
    R._active_generations.pop("test-stage2-refusal", None)

    assert status == 403, payload
    assert payload['status'] == 'blocked'
    assert payload['safety_block']['checkpoint'] == 'refusal'
    assert payload['safety_block']['reason_key'] == 'refusal'
    assert reached == {"before_model": [], "stage4": []}
    # The refusal is the model's own; the check at the result is not asked about it.
    assert checks_waved_through == []
