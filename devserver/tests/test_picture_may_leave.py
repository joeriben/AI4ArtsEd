"""A picture goes to a model outside this server only where it may leave it.

The chat has kept uploaded and camera pictures here since 2026-03-25
(DEVELOPMENT_DECISIONS), decided by where the file lay. Three ways out
remained, closed on 2026-10-31:

  * a picture made FROM an upload, by image to image, lay in a run's folder and
    counted as generated, so it went to the provider. A run now says whether it
    took a picture in, and a picture of such a run stays, like the upload.
    A run that does not say counts as unknown, and stays;
  * the fallback chain handed the picture to every candidate that could see,
    wherever that candidate ran. It now hands the picture itself only to a
    local candidate unless the caller said the picture may leave, and a
    candidate outside this server gets the account of it;
  * the LLM proxy of the ComfyUI nodes cannot say where its picture came from,
    so its picture goes to a local model alone.

Nothing here reaches a model: every model call is a stand-in.

Run: python3 -m pytest devserver/tests/test_picture_may_leave.py -q
"""
import ast
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask
from PIL import Image

import config
from my_app.routes import chat_routes
from my_app.services import pipeline_recorder as pr
from my_app.utils import vision_support
from my_app.utils.media_ref import may_leave_server


# The turn is under test here, not what it checks.
pytestmark = pytest.mark.usefixtures("chat_checks_pass")

KEY = pr.INPUT_IMAGE_KEY
MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "what is in it?"}]
PICTURE = "QUJD"
OUTSIDE = "openrouter/some/model"   # a provider's model that can see
HERE = "local/seer:4b"              # a local model that can see
BLIND = "openrouter/blind/model"    # a provider's model that cannot


def _png(path, size=(96, 96)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (10, 120, 200)).save(path, format="PNG")


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    """A run storage and an upload directory of their own, and a way to put a
    run into the storage: one picture, made at adult, saying `took_one` about
    its input (None: saying nothing)."""
    runs = tmp_path / "runs"
    uploads = tmp_path / "uploads_tmp"
    uploads.mkdir()
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", runs)
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", uploads)
    monkeypatch.setattr(pr, "_active_recorders", {})

    def run(run_id, took_one):
        folder = runs / "2026-10-31" / "a-device" / run_id
        _png(folder / "final" / "01_output_image.png")
        metadata = {"run_id": run_id, "config_name": "sd35_large", "safety_level": "adult",
                    "entities": [{"type": "output_image", "filename": "01_output_image.png",
                                  "sequence": 1}]}
        if took_one is not None:
            metadata[KEY] = took_one
        (folder / "metadata.json").write_text(json.dumps(metadata))
        return run_id

    return SimpleNamespace(run=run, uploads=uploads, root=tmp_path)


# ── Where a picture may go, read from where it lies and what its run says ──

def test_a_picture_made_from_words_alone_may_leave(storage):
    run_id = storage.run("run_words", False)
    assert may_leave_server(run_id, level="adult") is True
    assert may_leave_server(f"/api/media/image/{run_id}/0", level="adult") is True


def test_a_picture_made_from_a_picture_stays(storage):
    run_id = storage.run("run_from_picture", True)
    assert may_leave_server(run_id, level="adult") is False
    assert may_leave_server(f"/api/media/image/{run_id}/0", level="adult") is False


def test_a_run_that_does_not_say_counts_as_unknown_and_stays(storage):
    assert may_leave_server(storage.run("run_older", None), level="adult") is False


def test_an_upload_stays_also_in_a_folder_below_the_upload_directory(storage):
    _png(storage.uploads / "abc-123.png")
    _png(storage.uploads / "masks" / "mask-1.png")
    assert may_leave_server("abc-123", level="adult") is False
    assert may_leave_server("/api/media/uploads/abc-123", level="adult") is False
    assert may_leave_server(str(storage.uploads / "masks" / "mask-1.png"), level="adult") is False


def test_a_camera_picture_stays(storage):
    assert may_leave_server("data:image/jpeg;base64,/9j/4AAQ", level="adult") is False


def test_a_reference_that_does_not_resolve_stays(storage):
    assert may_leave_server("run_nobody_made", level="adult") is False
    assert may_leave_server("", level="adult") is False
    assert may_leave_server(None, level="adult") is False


def test_a_file_outside_the_run_storage_stays(storage):
    _png(storage.root / "elsewhere" / "picture.png")
    assert may_leave_server(str(storage.root / "elsewhere" / "picture.png"), level="adult") is False


def test_a_picture_withheld_at_the_level_stays(storage):
    """At kids a picture resolves only with a pass, and this one has none."""
    assert may_leave_server(storage.run("run_unchecked", False), level="kids") is False


# ── The run says it, and keeps saying it ───────────────────────────────────

def _recorder(tmp_path, run_id):
    return pr.LivePipelineRecorder(run_id=run_id, config_name="sd35_large", safety_level="adult",
                                   device_id="a-device", base_path=tmp_path)


def test_a_run_that_took_a_picture_in_keeps_saying_so(tmp_path):
    recorder = _recorder(tmp_path, "run_sticky")
    recorder.record_input_image(False)
    assert recorder.metadata[KEY] is False
    recorder.record_input_image(True)
    recorder.record_input_image(False)
    assert recorder.metadata[KEY] is True
    on_disk = json.loads((recorder.run_folder / "metadata.json").read_text())
    assert on_disk[KEY] is True


def test_a_run_that_wrote_outputs_before_it_said_anything_keeps_not_saying_it(tmp_path):
    recorder = _recorder(tmp_path, "run_late")
    recorder.metadata["entities"].append({"type": "output_image", "filename": "01_output_image.png"})
    recorder.record_input_image(False)
    assert KEY not in recorder.metadata
    recorder.record_input_image(True)
    assert recorder.metadata[KEY] is True


def _executor_that_stops(monkeypatch):
    import my_app.routes.schema_pipeline_routes as routes

    async def execute_pipeline(**kwargs):
        return SimpleNamespace(success=False, error="stopped here on purpose",
                               metadata={}, final_output=None)

    monkeypatch.setattr(routes, "pipeline_executor",
                        SimpleNamespace(execute_pipeline=execute_pipeline,
                                        config_loader=SimpleNamespace(get_config=lambda name: None)))


@pytest.mark.parametrize("pictures, took_one", [({}, False),
                                                ({"input_image": "/some/upload.png"}, True),
                                                ({"multi_images": {"input_image2": "/some/upload.png"}}, True)])
def test_stage_four_says_whether_it_took_a_picture_in(storage, monkeypatch, pictures, took_one):
    from my_app.routes.schema_pipeline_routes import execute_stage4_generation_only
    _executor_that_stops(monkeypatch)
    asyncio.run(execute_stage4_generation_only(
        prompt="a house", output_config="sd35_large", safety_level="adult",
        run_id="run_stage_four", seed=1, **pictures))
    assert pr._active_recorders["run_stage_four"].metadata[KEY] is took_one


def test_a_direct_workflow_takes_no_picture_in(storage, monkeypatch):
    from my_app.routes.schema_pipeline_routes import _run_direct_workflow
    _executor_that_stops(monkeypatch)
    # At research, where nothing is checked, so that no check is reached.
    _run_direct_workflow({"prompt": "a house", "output_config": "sd35_large", "seed": 1}, "research")
    [recorder] = pr._active_recorders.values()
    assert recorder.metadata[KEY] is False


def test_every_way_into_stage_four_says_it():
    """Three ways in, none of which meets the others (test_fallback_is_honest
    names them). A way that forgets this leaves its pictures unknown, which
    keeps them here: the cost of forgetting is the cloud model's eyes, never a
    picture sent away."""
    source = Path(__file__).resolve().parents[1] / "my_app" / "routes" / "schema_pipeline_routes.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    says = {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "record_input_image" for call in ast.walk(node))}
    assert {"execute_stage4_generation_only", "_run_interception_pipeline",
            "_run_direct_workflow"} <= says


# ── The chain hands the picture itself only where it may go ───────────────

@pytest.fixture()
def chain(monkeypatch):
    """A role whose chain holds a provider's model that sees, a local one that
    sees, and a provider's model that does not; the account of a picture is a
    stand-in."""
    monkeypatch.setattr(chat_routes, "get_user_setting", lambda key, default=None: OUTSIDE)
    monkeypatch.setattr(chat_routes, "build_model_candidate_chain",
                        lambda key, primary: [OUTSIDE, HERE, BLIND])
    monkeypatch.setattr(vision_support, "is_vision_capable", lambda model: model != BLIND)
    described = []

    def account(messages, image_b64):
        described.append(image_b64)
        return messages[:-1] + [{"role": "user", "content": "[account] what is in it?"}]

    monkeypatch.setattr(vision_support, "messages_with_description", account)
    return described


def _handed(attempts):
    return {model: image for _i, model, _messages, image, _n in attempts}


def test_a_picture_that_may_not_leave_goes_to_the_local_candidate_alone(chain):
    attempts = list(chat_routes._chain_attempts(MESSAGES, PICTURE, None, "CHAT_HELPER_MODEL",
                                                may_leave_server=False))
    assert _handed(attempts) == {OUTSIDE: None, HERE: PICTURE, BLIND: None}
    outside = next(a for a in attempts if a[1] == OUTSIDE)
    assert outside[2][-1]["content"].startswith("[account]")


def test_a_picture_that_may_leave_goes_to_every_candidate_that_sees(chain):
    attempts = list(chat_routes._chain_attempts(MESSAGES, PICTURE, None, "CHAT_HELPER_MODEL",
                                                may_leave_server=True))
    assert _handed(attempts) == {OUTSIDE: PICTURE, HERE: PICTURE, BLIND: None}


def test_a_caller_who_does_not_say_is_a_caller_who_does_not_know(chain, monkeypatch):
    dispatched = []
    monkeypatch.setattr(chat_routes, "_dispatch_single_model",
                        lambda model, messages, *a, **k: dispatched.append((model, a[-1])) or {"content": "x"})
    chat_routes.call_chat_helper(MESSAGES, image_b64=PICTURE)
    assert dispatched == [(OUTSIDE, None)]


def test_inside_comfyui_a_candidate_outside_this_server_ends_the_call_and_says_why(chain):
    with pytest.raises(Exception, match="runs outside this server, where this picture may not go"):
        list(chat_routes._chain_attempts(MESSAGES, PICTURE, None, "CHAT_HELPER_MODEL",
                                         describe=False, may_leave_server=False))
    assert chain == []


# ── The proxy cannot say where its picture came from ───────────────────────

@pytest.fixture()
def proxy(chain, monkeypatch):
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([{"id": OUTSIDE}, {"id": HERE}], False, {}))
    dispatched = []
    monkeypatch.setattr(chat_routes, "_dispatch_single_model",
                        lambda model, messages, *a, **k: dispatched.append((model, messages, a[-1]))
                        or {"content": "answer"})
    app = Flask(__name__)
    app.register_blueprint(chat_routes.chat_bp)
    return SimpleNamespace(client=app.test_client(), dispatched=dispatched, described=chain)


def test_the_proxy_hands_a_provider_the_account_and_not_the_picture(proxy):
    r = proxy.client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": OUTSIDE,
                                                   "image_b64": PICTURE})
    assert r.status_code == 200, r.get_json()
    [(model, messages, image)] = proxy.dispatched
    assert (model, image) == (OUTSIDE, None)
    assert messages[-1]["content"].startswith("[account]")
    assert proxy.described == [PICTURE]


def test_the_proxy_hands_a_local_model_the_picture(proxy):
    r = proxy.client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": HERE,
                                                   "image_b64": PICTURE})
    assert r.status_code == 200, r.get_json()
    assert [(m, i) for m, _msgs, i in proxy.dispatched] == [(HERE, PICTURE)]


def test_the_proxy_tells_a_node_why_a_provider_gets_nothing(proxy):
    r = proxy.client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": OUTSIDE,
                                                   "image_b64": PICTURE, "runs_inside_comfyui": True})
    assert r.status_code == 502
    assert "where this picture may not go" in r.get_json()["error"]
    assert proxy.dispatched == []


# ── The chat: the picture's run decides, and the look follows it ────────────

@pytest.fixture()
def app_ctx():
    app = Flask(__name__)
    with app.test_request_context("/api/chat", json={}):
        yield


def _turn(monkeypatch, image_path):
    """One chat turn about `image_path`, answered by a model outside this server
    that can see. The model asks one look, if it holds the tool, and then answers."""
    rounds, looks = [], []
    monkeypatch.setattr(vision_support, "is_vision_capable", lambda model: True)
    monkeypatch.setattr(vision_support, "ask_about_image",
                        lambda b64, question, for_model="", may_leave_server=False:
                        looks.append(may_leave_server) or "a blue square")
    from my_app.services.llm_service import llm_service
    monkeypatch.setattr(llm_service, "describe_image_brief", lambda b64: "a blue square")

    def helper(**kwargs):
        rounds.append(kwargs)
        holds_look = any(t["function"]["name"] == "look_at_image" for t in (kwargs.get("tools") or []))
        if holds_look and len(rounds) == 1:
            yield ("result", {"content": "", "thinking": None, "model_used": OUTSIDE, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "look_at_image",
                             "arguments": json.dumps({"question": "what colour is it?"})}}]})
            return
        yield ("token", "Blue.")
        yield ("result", {"content": "Blue.", "thinking": None, "tool_calls": None,
                          "model_used": OUTSIDE})

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    events = list(chat_routes._chat_events(
        {"message": "what colour is it?", "image_path": image_path, "model": OUTSIDE},
        level="adult"))
    assert events[-1]["type"] == "done", events[-1]
    return rounds, looks


def test_the_chat_hands_a_picture_made_from_words_to_the_model(storage, app_ctx, monkeypatch):
    rounds, looks = _turn(monkeypatch, storage.run("run_words_chat", False))
    assert rounds[0]["image_b64"]
    assert rounds[0]["may_leave_server"] is True
    assert looks == []


def test_the_chat_keeps_a_picture_made_from_a_picture_and_looks_at_it_here(
        storage, app_ctx, monkeypatch):
    rounds, looks = _turn(monkeypatch, storage.run("run_from_picture_chat", True))
    assert all(r["image_b64"] is None for r in rounds)
    assert all(r["may_leave_server"] is False for r in rounds)
    assert looks == [False]


def test_the_chat_keeps_an_upload_and_looks_at_it_here(storage, app_ctx, monkeypatch):
    _png(storage.uploads / "abc-456.png")
    rounds, looks = _turn(monkeypatch, "abc-456")
    assert all(r["image_b64"] is None for r in rounds)
    assert looks == [False]
