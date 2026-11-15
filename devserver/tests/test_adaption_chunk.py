"""A model whose maker ships the model that writes its adaption.

The output config names the chunk (`meta.adaption_chunk`). /pipeline/optimize
runs it on the pictures the run will hand the image model, and its answer is the
adaption. What it wrote it read off the pictures, so the caption passes the
intake (a name on a sign reached none before) and then the check at the result
before it leaves; at the generation it goes on to the check before the model
and the translation like any other text.

The runs here are at research, where the checks pass without a model, except
where a check is the subject: there it stands in.
"""
import asyncio
import threading
from types import SimpleNamespace

import pytest
from flask import Flask

import config
import my_app.routes.schema_pipeline_routes as routes
from my_app.services import generation_abort
from my_app.services.gpu_lease_client import GpuBusyError
from schemas.engine.backend_router import BackendResponse, BackendRouter, _shown_text


class _Router:
    def __init__(self, response):
        self.response = response
        self.asked = []

    async def process_request(self, request):
        self.asked.append(request)
        return self.response


def _route_with(monkeypatch, response, adaption_chunk="the_chunk"):
    router = _Router(response)
    config = SimpleNamespace(meta={"adaption_chunk": adaption_chunk} if adaption_chunk else {})
    executor = SimpleNamespace(
        backend_router=router,
        config_loader=SimpleNamespace(get_config=lambda name: config),
    )
    monkeypatch.setattr(routes, "pipeline_executor", executor)
    monkeypatch.setattr(routes, "config_loader", executor.config_loader)
    monkeypatch.setattr(routes, "_load_estimated_duration", lambda name: "25")
    monkeypatch.setattr(routes, "_load_optimization_instruction", lambda name: None)
    return router


def _worded(text="a caption"):
    return BackendResponse(success=True, content=text, metadata={"model_used": "the writer"})


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """Two uploaded pictures, by name; the upload directory is this test's own."""
    directory = tmp_path / "uploads_tmp"
    directory.mkdir()
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", directory)
    paths = {}
    for name in ("a.png", "b.png"):
        (directory / name).write_bytes(b"picture")
        paths[name] = str((directory / name).resolve())
    return paths


def test_the_chunk_answers_with_the_pictures_in_hand(monkeypatch, uploads):
    router = _route_with(monkeypatch, _worded())
    body, status = routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "flux3_multi", "has_input_image": True,
        "input_image1": uploads["a.png"], "input_image2": uploads["b.png"],
    }, "research")
    assert status == 200
    assert body["success"] is True
    assert body["optimized_prompt"] == "a caption"
    assert body["optimization_applied"] is True
    assert body["model"] == "local/the writer"
    assert "unchanged" not in body
    parameters = router.asked[0].parameters
    assert parameters["_chunk_name"] == "the_chunk"
    assert parameters["prompt"] == "ein Haus"
    assert parameters["input_image1"] == uploads["a.png"]
    assert parameters["input_image2"] == uploads["b.png"]


@pytest.mark.parametrize("path", ("/etc/hostname", "{uploads}/../secret.png", "{uploads}/missing.png"))
def test_only_a_file_in_the_upload_directory_is_read(monkeypatch, uploads, tmp_path, path):
    (tmp_path / "secret.png").write_bytes(b"not uploaded")
    router = _route_with(monkeypatch, _worded())
    body, status = routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "flux3_multi",
        "input_image1": path.format(uploads=config.UPLOADS_TMP_DIR),
    }, "research")
    assert status == 400
    assert body["success"] is False
    assert body["code"] == "image_gone"
    assert router.asked == []


def test_without_pictures_the_text_stands_and_no_model_is_asked(monkeypatch):
    router = _route_with(monkeypatch, _worded())
    body, status = routes._run_optimize_prompt({"input_text": "ein Haus", "output_config": "flux3_multi"}, "research")
    assert status == 200
    assert body["unchanged"] is True
    assert body["optimized_prompt"] == "ein Haus"
    assert router.asked == []


def test_a_failure_is_said_and_no_other_model_writes_in_its_place(monkeypatch, uploads):
    _route_with(monkeypatch, BackendResponse(success=False, content="", error="the card said no"))

    async def no_other_model(**_):
        raise AssertionError("a language model was asked in the chunk's place")

    monkeypatch.setattr(routes, "execute_optimization", no_other_model)
    body, status = routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "flux3_multi", "input_image1": uploads["a.png"],
    }, "research")
    assert status == 500
    assert body == {"success": False, "error": "the card said no"}


def test_a_busy_card_stays_the_state_the_gate_named(monkeypatch, uploads):
    _route_with(monkeypatch, BackendResponse(
        success=False, content="", error="device busy",
        metadata={"busy": {"reason": "busy", "holder_kind": "", "waiting": 2}},
    ))
    body, status = routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "flux3_multi", "input_image1": uploads["a.png"],
    }, "research")
    assert status == 500
    assert body["code"] == "gpu_busy"
    assert body["busy"] == {"reason": "busy", "holder_kind": "", "waiting": 2}


class _Interrupted:
    """A prompt in ComfyUI that runs until the reader has left and it was cancelled."""

    def __init__(self, client_gone, cancelled):
        self.client_gone = client_gone
        self.cancelled = cancelled
        self.run_id = None
        self.workload = None
        self.saw_the_mark = False

    async def process_request(self, request):
        self.run_id = generation_abort.CURRENT_RUN_ID.get()
        self.workload = generation_abort.CURRENT_OUTPUT_CONFIG.get()
        generation_abort.note_prompt(self.run_id, "the-prompt")
        self.client_gone.set()
        for _ in range(100):
            if self.cancelled:
                break
            await asyncio.sleep(0.05)
        self.saw_the_mark = generation_abort.is_aborted(self.run_id)
        generation_abort.forget_prompt(self.run_id, "the-prompt")
        return BackendResponse(success=False, content="", error="interrupted")


def test_a_reader_who_left_takes_the_prompt_off_the_card(monkeypatch, uploads):
    _route_with(monkeypatch, _worded())
    cancelled = []

    class Client:
        # What the watcher of generation_abort asks: None, the cancel was taken.
        async def try_cancel_job(self, prompt_id):
            cancelled.append(prompt_id)

    monkeypatch.setattr("my_app.services.comfyui_ws_client.get_comfyui_ws_client", lambda: Client())
    client_gone = threading.Event()
    router = _Interrupted(client_gone, cancelled)
    routes.pipeline_executor.backend_router = router

    routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "flux3_multi", "input_image1": uploads["a.png"],
    }, "research", client_gone=client_gone)

    assert cancelled == ["the-prompt"]
    assert router.saw_the_mark
    assert router.run_id
    assert router.workload == "the_chunk"
    assert generation_abort.CURRENT_RUN_ID.get() != router.run_id
    assert not generation_abort.is_aborted(router.run_id)


def _legacy_chunk():
    return {"name": "the_chunk", "media_type": "text",
            "workflow": {"1": {"class_type": "Anything", "inputs": {}}},
            "input_mappings": {}, "meta": {"display_name": "the writer"},
            "output_mapping": {"node_id": "214", "output_type": "text", "field": "text"}}


class _Client:
    def __init__(self, raises=None, fails=None, outputs=None):
        self.raises = raises
        self.fails = fails
        self.outputs = {"214": {"text": ["a caption"]}} if outputs is None else outputs
        self.forgotten = []

    async def get_queue_status(self):
        return {"total": 0}

    async def submit_and_track(self, workflow, timeout=None, on_progress=None):
        if self.raises:
            raise self.raises
        on_progress(SimpleNamespace(event_type="submitted", prompt_id="the-prompt"))
        if self.fails:
            raise self.fails
        return SimpleNamespace(prompt_id="the-prompt", model_used="", outputs_metadata=self.outputs)

    async def forget_prompt(self, prompt_id):
        self.forgotten.append(prompt_id)


def _router_with_comfyui_up():
    async def available():
        return True

    router = BackendRouter()
    router.comfyui_manager = SimpleNamespace(ensure_comfyui_available=available)
    return router


def test_the_words_are_read_and_the_run_leaves_comfyuis_history(monkeypatch):
    client = _Client()
    monkeypatch.setattr("my_app.services.comfyui_ws_client.get_comfyui_ws_client", lambda: client)
    response = asyncio.run(_router_with_comfyui_up()._process_legacy_workflow(
        _legacy_chunk(), "ein Haus", {}))
    assert response.success is True
    assert response.content == "a caption"
    assert response.metadata["model_used"] == "the writer"
    assert client.forgotten == ["the-prompt"]


def test_a_run_that_was_stopped_leaves_comfyuis_history_too(monkeypatch):
    client = _Client(fails=RuntimeError("interrupted"))
    monkeypatch.setattr("my_app.services.comfyui_ws_client.get_comfyui_ws_client", lambda: client)
    response = asyncio.run(_router_with_comfyui_up()._process_legacy_workflow(
        _legacy_chunk(), "ein Haus", {}))
    assert response.success is False
    assert client.forgotten == ["the-prompt"]


def test_outputs_that_could_not_be_read_are_not_called_a_silent_model(monkeypatch):
    client = _Client(outputs={})
    monkeypatch.setattr("my_app.services.comfyui_ws_client.get_comfyui_ws_client", lambda: client)
    response = asyncio.run(_router_with_comfyui_up()._process_legacy_workflow(
        _legacy_chunk(), "ein Haus", {}))
    assert response.success is False
    assert "could not be read" in response.error


def test_a_refusal_of_the_gate_comes_out_of_the_workflow_as_a_busy_card(monkeypatch):
    refusal = GpuBusyError("device busy", reason="queue_full", waiting=3)
    client = _Client(raises=refusal)
    monkeypatch.setattr("my_app.services.comfyui_ws_client.get_comfyui_ws_client", lambda: client)
    response = asyncio.run(_router_with_comfyui_up()._process_legacy_workflow(
        _legacy_chunk(), "ein Haus", {}))
    assert response.success is False
    assert response.error == "device busy"
    assert response.metadata["busy"] == {"reason": "queue_full", "holder_kind": "", "waiting": 3}


def test_a_config_without_the_chunk_never_reaches_it(monkeypatch):
    router = _route_with(monkeypatch, _worded(), adaption_chunk=None)
    body, status = routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "qwen_img2img", "input_image1": "a.png",
    }, "research")
    assert status == 200
    assert body["unchanged"] is True
    assert router.asked == []


def _gate_stubs(monkeypatch, refuse_name=""):
    """The intake and the check at the result, standing in; what they were
    asked, in order. A text naming `refuse_name` fails the intake."""
    from my_app.services import safety_gate as gate
    seen = []

    def intake(fields, *, level):
        seen.append(("intake", dict(fields), level))
        for name, text in fields.items():
            if refuse_name and isinstance(text, str) and refuse_name in text:
                return gate.Verdict(False, gate.CHECKPOINT_INTAKE, level, name,
                                    gate.REASON_PERSONAL_DATA, "a name")
        return gate.Verdict(True, gate.CHECKPOINT_INTAKE, level)

    def result(text, *, level, field="text"):
        seen.append(("result", text, level, field))
        return gate.Verdict(True, gate.CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(routes, "check_intake_texts", intake)
    monkeypatch.setattr(routes, "check_result_text", result)
    return seen


def test_the_caption_passes_the_intake_and_then_the_check_at_the_result(monkeypatch, uploads):
    _route_with(monkeypatch, _worded("a sign on a house"))
    seen = _gate_stubs(monkeypatch)
    body, status = routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "flux3_multi", "input_image1": uploads["a.png"],
    }, "kids")
    assert status == 200
    assert body["optimized_prompt"] == "a sign on a house"
    assert seen == [
        ("intake", {"input_text": "ein Haus"}, "kids"),
        ("intake", {"optimized_prompt": "a sign on a house"}, "kids"),
        ("result", "a sign on a house", "kids", "optimized_prompt"),
    ]


def test_a_name_read_off_the_pictures_is_refused_before_it_leaves(monkeypatch, uploads):
    _route_with(monkeypatch, _worded("the sign reads Lena"))
    seen = _gate_stubs(monkeypatch, refuse_name="Lena")
    body, status = routes._run_optimize_prompt({
        "input_text": "ein Haus", "output_config": "flux3_multi", "input_image1": uploads["a.png"],
    }, "kids")
    assert status == 403
    assert body["success"] is False
    assert body["safety_block"]["checkpoint"] == "intake"
    assert body["safety_block"]["field"] == "optimized_prompt"
    assert body["safety_block"]["reason_key"] == "personal_data"
    # The intake refused; the check at the result was never asked.
    assert [s[0] for s in seen] == ["intake", "intake"]


class _Recorder:
    metadata = {"entities": [], "models_used": {}}

    def output_entities(self, *a, **kw):
        return []

    def __getattr__(self, name):
        return lambda *a, **kw: None


@pytest.fixture
def generation(monkeypatch):
    """The Flow's press on the generation stream, with stand-ins that record what they read."""
    from my_app.services import safety_gate as gate
    routes.init_schema_engine()
    seen = {"intake": [], "translated": [], "before_model": [], "stage4": []}

    def intake(fields, *, level):
        seen["intake"].append(dict(fields))
        for name, text in fields.items():
            if isinstance(text, str) and "Lena" in text:
                return gate.Verdict(False, gate.CHECKPOINT_INTAKE, level, name,
                                    gate.REASON_PERSONAL_DATA, "a name")
        return gate.Verdict(True, gate.CHECKPOINT_INTAKE, level)

    async def translate(text, *a, **kw):
        seen["translated"].append(text)
        return text

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        seen["before_model"].append(dict(texts))
        return gate.Verdict(True, gate.CHECKPOINT_BEFORE_MODEL, level)

    async def stage4(**kw):
        seen["stage4"].append(kw)
        return {"success": False, "error": "stub", "run_id": kw.get("run_id")}

    monkeypatch.setattr(routes, "check_intake_texts", intake)
    monkeypatch.setattr(routes, "_translate_for_model", translate)
    monkeypatch.setattr(routes, "check_before_model", before_model)
    monkeypatch.setattr(routes, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(routes, "get_recorder", lambda **kw: _Recorder())
    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "kids")
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(routes.schema_bp, url_prefix="/api/schema")
    client = app.test_client()

    def press(prompt, output_config="flux3_multi", **images):
        response = client.get("/api/schema/pipeline/generation", query_string={
            "prompt": prompt, "output_config": output_config, "device_id": "test-caption",
            "enable_streaming": "true", "force_translation": "true", **images,
        })
        body = response.get_data(as_text=True)
        return body, seen

    yield press
    routes._active_generations.pop("test-caption", None)


def test_the_caption_of_the_pictures_passes_the_intake_before_the_translation(generation):
    _body, seen = generation("a caption", input_image1="a.png")
    assert [fields["prompt"] for fields in seen["intake"]] == ["a caption"]
    assert seen["translated"] == ["a caption"]
    assert [texts["prompt"] for texts in seen["before_model"]] == ["a caption"]


def test_a_name_in_the_caption_never_reaches_the_translation(generation):
    body, seen = generation("the sign reads Lena", input_image1="a.png")
    assert "event: blocked" in body
    assert '"safety_block":{"checkpoint":"intake"' in body
    assert seen["translated"] == []
    assert seen["before_model"] == []
    assert seen["stage4"] == []


@pytest.mark.parametrize("output_config,images", [
    ("flux3_multi", {}),
    ("qwen_2511_multi", {"input_image1": "a.png"}),
])
def test_every_text_is_read_as_it_was_sent_with_or_without_pictures(generation, output_config, images):
    _body, seen = generation("a text", output_config=output_config, **images)
    assert [fields["prompt"] for fields in seen["intake"]] == ["a text"]
    assert [texts["prompt"] for texts in seen["before_model"]] == ["a text"]


@pytest.mark.parametrize("outputs,expected", [
    ({"214": {"text": ["  a caption \n"]}}, "a caption"),
    ({"214": {"text": "a caption"}}, "a caption"),
    ({"214": {"text": []}}, ""),
    ({"214": {}}, ""),
    ({}, ""),
    (None, ""),
])
def test_the_text_a_node_showed(outputs, expected):
    assert _shown_text(outputs, 214) == expected


@pytest.mark.parametrize("has_the_writer", (True, False))
def test_a_config_without_its_adaption_model_is_not_available(monkeypatch, has_the_writer):
    from my_app.services.model_availability_service import ModelAvailabilityService
    service = ModelAvailabilityService()
    clips = ["qwen3vl_4b_bf16.safetensors"]
    if has_the_writer:
        clips.append("qwen3.5_9b_flux3_prompt_upsampler_bf16.safetensors")
    models = {
        "checkpoints": [],
        "unets": ["flux3-image-klein-bf16.safetensors"],
        "vaes": ["Flux/flux2-vae.safetensors"],
        "clips": clips,
    }

    async def comfyui_models(force_refresh=False):
        return models

    monkeypatch.setattr(service, "get_comfyui_models", comfyui_models)
    assert asyncio.run(service.check_config_availability("flux3_multi")) is has_the_writer
