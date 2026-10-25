"""What the second review of 2026-10-10 refuted on the early packages, held.

Each case was red on the tree before its fix:
  - malformed concepts ended a composable run at stage 1 with a 500 (85ba393
    made stage 1 read them; the chunk had read them itself before);
  - checks_passed carried a check once per text;
  - the kids/youth classifier's refusal came back as a 500, which every
    surface reads as a breakdown, not as the block it is;
  - a skipped stage 2 handed the visitor's own text to the refusal detector
    (501b5d8), and a visitor who wrote the sentence was "refused";
  - the Flow's streaming path and the Canvas node let the model-written
    refusal through as the interception (S-015, the other two sites);
  - the registry kept two methods that called methods 3d8301d struck.
"""
import ast
import sys
import types
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.routes import schema_pipeline_routes as R  # noqa: E402
from schemas.engine.instruction_selector import SAFETY_REFUSAL_SENTENCE  # noqa: E402

DEVSERVER = Path(__file__).resolve().parents[1]
SCHEMA = "bauhaus"
HARMLESS = "Ein Haus steht in einer Landschaft."
REFUSAL = SAFETY_REFUSAL_SENTENCE + " Bitte formuliere es anders."


# ---------------------------------------------------------------------------
# stage 1: concepts and checks_passed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sent", ["{not json", "[1,", 42])
def test_malformed_concepts_are_not_stage_ones_to_refuse(sent):
    """The chunk reads the concepts and says what is wrong with them; stage 1
    reads the prompts it can find, and finds none here."""
    assert R._concept_prompts(sent) == []


def test_well_formed_concepts_are_still_read():
    assert R._concept_prompts('[{"prompt": "a"}, {"prompt": " "}, {"prompt": "b"}]') == [
        ("concept_1", "a"), ("concept_3", "b")]


def test_checks_passed_names_each_check_once(monkeypatch):
    async def stage1(text, safety_level, pipeline_executor, user_language='de'):
        return (True, text, None, ["fast_filter", "spacy"])

    monkeypatch.setattr(R, "execute_stage1_safety_unified", stage1)
    monkeypatch.setattr(R, "pipeline_executor", object())
    is_safe, _, passed, _, checked = R._stage1_check_texts(
        [("input_text", "a"), ("context_prompt", "b"), ("concept_1", "c")], "kids", "de")
    assert is_safe
    assert passed == ["fast_filter", "spacy"]
    assert checked == {"input_text": "a", "context_prompt": "b", "concept_1": "c"}


# ---------------------------------------------------------------------------
# the stage-2 route: the classifier's refusal, and what is not a refusal
# ---------------------------------------------------------------------------

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
                        lambda texts, level, lang: (True, None, ["stub"], None, {'input_text': HARMLESS}))


def test_the_classifier_refusal_is_a_block_not_a_breakdown(client, stage1_waved_through, monkeypatch):
    async def classifier(**kwargs):
        return R._ClassifierResult(success=False, final_output='', error="UNSAFE_VIOLENCE: not for kids",
                                   metadata={'gate': 'classifier', 'label': 'UNSAFE'})

    monkeypatch.setattr(R, "execute_stage2_classifier", classifier)
    response = client.post('/api/schema/pipeline/stage2',
                           json={'schema': SCHEMA, 'input_text': HARMLESS, 'skip_optimization': True})
    assert response.status_code == 403, response.get_data(as_text=True)
    body = response.get_json()
    assert body['status'] == 'blocked'
    assert body['blocked_at_stage'] == 2
    assert body['reason'] == "UNSAFE_VIOLENCE: not for kids"
    assert body['checks_passed'] == ["stub"]


def test_a_classifier_that_could_not_be_reached_is_still_a_breakdown(client, stage1_waved_through, monkeypatch):
    async def classifier(**kwargs):
        return R._ClassifierResult(success=False, final_output='', error="nothing answers",
                                   metadata={'gate': 'classifier', 'status': 'unreachable'})

    monkeypatch.setattr(R, "execute_stage2_classifier", classifier)
    response = client.post('/api/schema/pipeline/stage2',
                           json={'schema': SCHEMA, 'input_text': HARMLESS, 'skip_optimization': True})
    assert response.status_code == 500


def test_a_visitor_who_wrote_the_sentence_is_not_refused_where_stage_2_was_skipped(
        client, stage1_waved_through, monkeypatch):
    """A skipped stage 2 hands the visitor's own text on; the detector reads
    what a MODEL wrote."""
    monkeypatch.setattr(R, "_stage1_check_texts",
                        lambda texts, level, lang: (True, None, ["stub"], None, {'input_text': REFUSAL}))

    async def classifier(**kwargs):
        return R._ClassifierResult(success=True, final_output=REFUSAL,
                                   metadata={'gate': 'classifier', 'label': 'SAFE'})

    monkeypatch.setattr(R, "execute_stage2_classifier", classifier)
    response = client.post('/api/schema/pipeline/stage2',
                           json={'schema': SCHEMA, 'input_text': REFUSAL, 'skip_optimization': True})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()['stage2_result'] == REFUSAL


# ---------------------------------------------------------------------------
# the Flow's streaming path
# ---------------------------------------------------------------------------

def test_the_flow_stream_says_blocked_on_a_model_written_refusal(monkeypatch):
    from test_sse_silent_windows import (_interception_data, _wire_interception,  # noqa: E402
                                         Opened, STAGE1_PASSED, event_names, event_payloads)
    _wire_interception(monkeypatch, Opened())
    monkeypatch.setattr(R, "_stage1_check_texts", lambda *a, **kw: STAGE1_PASSED)

    class Refusing:
        async def execute_pipeline(self, *a, **kw):
            return types.SimpleNamespace(success=True, final_output=REFUSAL, metadata={}, error=None)

    monkeypatch.setattr(R, "pipeline_executor", Refusing())

    body = "".join(R.execute_pipeline_streaming(_interception_data()))

    names = event_names(body)
    assert names[-1] == "blocked", names
    assert "chunk" not in names and "complete" not in names
    blocked = event_payloads(body)[-1]
    assert blocked["stage"] == 2
    assert blocked["blocked_at_stage"] == 2
    assert SAFETY_REFUSAL_SENTENCE.rstrip('.') in blocked["reason"]


def test_the_flow_stream_still_hands_a_written_perspective_on(monkeypatch):
    from test_sse_silent_windows import (_interception_data, _wire_interception,  # noqa: E402
                                         Opened, STAGE1_PASSED, event_names)
    _wire_interception(monkeypatch, Opened())
    monkeypatch.setattr(R, "_stage1_check_texts", lambda *a, **kw: STAGE1_PASSED)

    class Writing:
        async def execute_pipeline(self, *a, **kw):
            return types.SimpleNamespace(success=True, final_output="a house by the lake",
                                         metadata={}, error=None)

    monkeypatch.setattr(R, "pipeline_executor", Writing())
    names = event_names("".join(R.execute_pipeline_streaming(_interception_data())))
    assert names[-2:] == ["chunk", "complete"], names


# ---------------------------------------------------------------------------
# the Canvas node
# ---------------------------------------------------------------------------

def test_the_canvas_node_reads_the_refusal_as_a_block():
    from test_canvas_interception_passthrough import _Engine, _Recorder, _Response  # noqa: E402
    from my_app.services.canvas_executor import CanvasWorkflowExecutor

    class Refusing(_Engine):
        async def process_request(self, req):
            self.requests.append(req)
            return _Response(REFUSAL)

    nodes = [
        {"id": "in", "type": "input", "promptText": "a red circle"},
        {"id": "ic", "type": "interception", "llmModel": "local/stub", "contextPrompt": "Sieh es als Ort."},
        {"id": "out", "type": "display"},
    ]
    connections = [{"sourceId": "in", "targetId": "ic"}, {"sourceId": "ic", "targetId": "out"}]
    engine, recorder = Refusing(), _Recorder()
    ex = CanvasWorkflowExecutor(nodes, connections, recorder, "run_test", engine, safety_level="kids")
    list(ex.execute_with_events())

    assert len(engine.requests) == 1
    assert ex.results["ic"]["output"] == ""
    assert SAFETY_REFUSAL_SENTENCE.rstrip('.') in ex.results["ic"]["error"]
    assert [e for e in recorder.entities if e["node_id"] == "ic"] == []


# ---------------------------------------------------------------------------
# the registry
# ---------------------------------------------------------------------------

def test_the_registry_calls_no_method_it_no_longer_has():
    """3d8301d struck `get_config` and `_load_output_config` and kept the two
    methods that called them, under an `except Exception` that hid the
    AttributeError. Every `self.<name>(` in the class names a method of it."""
    tree = ast.parse((DEVSERVER / "my_app" / "services" / "backend_registry.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BackendRegistry")
    methods = {n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    called = set()
    for node in ast.walk(cls):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
            called.add(node.func.attr)
    assert called - methods == set(), f"called on self but not defined: {sorted(called - methods)}"


# ---------------------------------------------------------------------------
# the static route: what the edutainment animations draw from
# ---------------------------------------------------------------------------

def test_the_server_hands_out_the_pictures_under_images(tmp_path):
    """/images/<name>.svg comes back as the picture, not as the app's page.
    The forest game's bird sprite lives there (public/images/bird-cells.svg);
    in production nothing but this route serves it, and until the second
    review of 2026-10-10 it was answered with index.html."""
    from flask import Flask
    from my_app.routes.static_routes import static_bp

    (tmp_path / "images").mkdir()
    sprite = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    (tmp_path / "images" / "bird-cells.svg").write_bytes(sprite)
    (tmp_path / "index.html").write_text("<!DOCTYPE html>", encoding="utf-8")
    app = Flask(__name__, static_folder=str(tmp_path), static_url_path=None)
    app.register_blueprint(static_bp)
    response = app.test_client().get("/images/bird-cells.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml", f"answered as {response.mimetype}"
    assert response.data == sprite


# ---------------------------------------------------------------------------
# the sessions list: the output mode is what the run produced
# ---------------------------------------------------------------------------

def _a_recorded_run(base, run_id, default_output, output_type):
    """A run folder as the recorder lays it out: metadata.json beside final/,
    the config the run used, and one output."""
    import json
    folder = base / "2026-10-10" / "dev" / run_id
    (folder / "final").mkdir(parents=True)
    (folder / "final" / "01_config_used.json").write_text(json.dumps({
        "pipeline": "text_transformation",
        "media_preferences": {"default_output": default_output},
    }), encoding="utf-8")
    (folder / "final" / f"02_{output_type}.bin").write_bytes(b"x")
    (folder / "metadata.json").write_text(json.dumps({
        "run_id": run_id,
        "timestamp": "2026-10-10T12:00:00",
        "config_name": "bauhaus",
        "entities": [
            {"type": "config_used", "filename": "01_config_used.json"},
            {"type": output_type, "filename": f"02_{output_type}.bin"},
        ],
    }), encoding="utf-8")


@pytest.mark.parametrize("default_output, output_type, shown", [
    ("image", "output_audio", "text2audio"),
    ("image", "output_video", "text2video"),
    ("video", "output_image", "text2image"),
])
def test_the_sessions_list_names_what_the_run_produced(tmp_path, monkeypatch,
                                                       default_output, output_type, shown):
    """85ba393 made the list find the run's config_used, whose
    media_preferences.default_output is the INTERCEPTION config's default,
    and read the output mode off it: a run that made a song under a
    perspective whose default is the image read "text2image". Until then the
    list never found that file and read the mode off the output the run
    wrote, which is what the column and the export showed."""
    import config
    from my_app.routes import settings_routes as SR
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setitem(SR._metadata_cache, "data", None)
    _a_recorded_run(tmp_path, "run_sessions_mode", default_output, output_type)

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(SR.settings_bp)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["settings_authenticated"] = True
    body = client.get("/api/settings/sessions", environ_base={"REMOTE_ADDR": "10.0.0.9"}).get_json()

    session = next(s for s in body["sessions"] if s["run_id"] == "run_sessions_mode")
    assert session["output_mode"] == shown
    assert session["stage2_pipeline"] == "text_transformation"


def test_the_older_layout_is_still_read_the_way_it_was(tmp_path, monkeypatch):
    """A run of the older layout keeps 01_config_used.json beside
    metadata.json; for it the list read the mode off that file before
    2026-10-10, and still does."""
    import json
    import config
    from my_app.routes import settings_routes as SR
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setitem(SR._metadata_cache, "data", None)
    _a_recorded_run(tmp_path, "run_sessions_legacy", "image", "output_audio")
    folder = tmp_path / "2026-10-10" / "dev" / "run_sessions_legacy"
    (folder / "01_config_used.json").write_text(json.dumps({
        "pipeline": "an_older_pipeline",
        "media_preferences": {"default_output": "video"},
    }), encoding="utf-8")

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(SR.settings_bp)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["settings_authenticated"] = True
    body = client.get("/api/settings/sessions", environ_base={"REMOTE_ADDR": "10.0.0.9"}).get_json()

    session = next(s for s in body["sessions"] if s["run_id"] == "run_sessions_legacy")
    assert session["output_mode"] == "text2video"
    assert session["stage2_pipeline"] == "an_older_pipeline"


# ---------------------------------------------------------------------------
# the refusal: read on what the INTERCEPTION model wrote
# ---------------------------------------------------------------------------

def _stage2_returns(monkeypatch, **fields):
    async def fake(**kwargs):
        base = dict(success=True, error=None, steps=[], execution_time=0,
                    interception_result=None, optimized_prompt=None, metadata={})
        base.update(fields)
        return types.SimpleNamespace(**base)

    monkeypatch.setattr(R, "execute_stage2_with_optimization", fake)


def test_a_passed_through_text_is_no_refusal_whatever_it_says(client, monkeypatch):
    """A perspective that owes the visitor their own wording hands it on
    (metadata passthrough); the visitor who wrote the sentence is not refused."""
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(R, "_stage1_check_texts",
                        lambda texts, level, lang: (True, None, ["stub"], None, {'input_text': REFUSAL}))
    _stage2_returns(monkeypatch, final_output=REFUSAL, interception_result=REFUSAL,
                    metadata={'passthrough': True})
    response = client.post('/api/schema/pipeline/stage2', json={'schema': SCHEMA, 'input_text': REFUSAL})
    assert response.status_code == 200, response.get_data(as_text=True)


def test_the_refusal_is_read_before_the_adaption_rewrote_it(client, stage1_waved_through, monkeypatch):
    """With an output config the adaption runs after the interception, and
    what it makes of the sentence (an English image prompt) is no longer the
    sentence; the interception model's own text is."""
    _stage2_returns(monkeypatch, interception_result=REFUSAL,
                    final_output="a polite refusal, photographed in soft light",
                    optimized_prompt="a polite refusal, photographed in soft light")
    response = client.post('/api/schema/pipeline/stage2',
                           json={'schema': SCHEMA, 'input_text': HARMLESS, 'output_config': 'sd35_large'})
    assert response.status_code == 403, response.get_data(as_text=True)
    body = response.get_json()
    assert body['blocked_at_stage'] == 2
    assert SAFETY_REFUSAL_SENTENCE.rstrip('.') in body['reason']
