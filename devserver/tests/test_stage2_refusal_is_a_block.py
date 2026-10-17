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
def stage1_waved_through(monkeypatch):
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(R, "_stage1_check_texts",
                        lambda texts, level, lang: (True, None, [], None, {'input_text': HARMLESS}))


def _stage2_answers(monkeypatch, text):
    async def fake(**kwargs):
        return R._ClassifierResult(success=True, final_output=text)

    monkeypatch.setattr(R, "execute_stage2_with_optimization", fake)


def test_the_sentence_is_read_in_one_place():
    assert is_safety_refusal(REFUSAL)
    assert is_safety_refusal("  hierbei kann ich dich nicht unterstützen  ")
    assert not is_safety_refusal("a Bauhaus house by the lake")
    assert not is_safety_refusal(None)
    assert not is_safety_refusal({"structured": True})


def test_the_stage2_route_answers_a_block(client, stage1_waved_through, monkeypatch):
    _stage2_answers(monkeypatch, REFUSAL)
    response = client.post('/api/schema/pipeline/stage2', json={'schema': SCHEMA, 'input_text': HARMLESS})
    assert response.status_code == 403, response.get_data(as_text=True)
    body = response.get_json()
    assert body['success'] is False
    assert body['status'] == 'blocked'
    assert body['blocked_at_stage'] == 2
    assert SAFETY_REFUSAL_SENTENCE.rstrip('.') in body['reason']


def test_a_written_perspective_still_passes(client, stage1_waved_through, monkeypatch):
    _stage2_answers(monkeypatch, "a Bauhaus house by the lake")
    response = client.post('/api/schema/pipeline/stage2', json={'schema': SCHEMA, 'input_text': HARMLESS})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()['stage2_result'] == "a Bauhaus house by the lake"


def test_the_full_run_stops_at_stage_2(monkeypatch, tmp_path):
    """The run that goes on to generate: a refusal ends it before stage 3 and
    stage 4 see anything."""
    import config
    from my_app.services import pipeline_recorder
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    pipeline_recorder._active_recorders.clear()
    R.init_schema_engine()

    async def stage1(text, safety_level, pipeline_executor, user_language='de'):
        return (True, text, None, ["stub"])

    reached = {"stage3": [], "stage4": []}

    async def stage3(prompt, safety_level, media_type, pipeline_executor, **kw):
        reached["stage3"].append(prompt)
        return {"safe": True, "method": "stub", "positive_prompt": prompt}

    async def stage4(**kw):
        reached["stage4"].append(kw)
        return {"success": False, "error": "stub: no model in this test", "run_id": kw.get("run_id")}

    monkeypatch.setattr(R, "execute_stage1_safety_unified", stage1)
    monkeypatch.setattr(R, "execute_stage3_safety", stage3)
    monkeypatch.setattr(R, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    _stage2_answers(monkeypatch, REFUSAL)

    payload, status = R._run_interception_pipeline(
        {"schema": SCHEMA, "input_text": HARMLESS, "output_config": "sd35_large",
         "device_id": "test-stage2-refusal"}, "kids")
    R._active_generations.pop("test-stage2-refusal", None)

    assert status == 403, payload
    assert payload['status'] == 'blocked'
    assert payload['blocked_at_stage'] == 2
    assert reached == {"stage3": [], "stage4": []}
