"""
The road a kept latent travels, end to end, on the DevServer side.

The two SD 3.5 rows can keep a picture's FINAL latent so that a SET of pictures
can be averaged BEFORE the decoder — measured on 2026-09-03, that decode has the
local sharpness of a single picture where the pixel mean has less than half of
it. `test_mean_images.py` holds the arithmetic and the overlay route, and it
starts from a latent already lying in a run folder. Everything BEFORE that lies
here, one station at a time:

    the request's flag  ->  custom_params  ->  the chunk  ->  the client
    ->  the GPU service  ->  the sink  ->  the run's own npy entity

and the call in the other direction, the decode of a mean, which ComfyUI runs
since 2026-09-14 (the last section), at every exit it has. The Diffusers
client's own decode keeps its tests until stage 8 of the move removes it. No
GPU and no model is reached: the backend and the HTTP call are replaced.

Run: python3 -m pytest devserver/tests/test_latent_transport.py -q
"""

import asyncio
import base64
import io
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from my_app.services import mean_images

CHUNKS = [
    "schemas.chunks.output_image_sd35_diffusers",
    "schemas.chunks.output_image_sd35_turbo_diffusers",
]


def _npy(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# The last station: the latent becomes an entity of the run
# ---------------------------------------------------------------------------

class _Recorder:
    """A recorder that only remembers what it was asked to write."""

    def __init__(self, breaks: Exception = None):
        self.saved = []
        self._breaks = breaks

    def save_entity(self, entity_type, content, metadata):
        if self._breaks is not None:
            raise self._breaks
        self.saved.append({"type": entity_type, "content": content,
                           "metadata": metadata})
        return f"{entity_type}.npy"


def _result(**metadata):
    return SimpleNamespace(metadata=metadata)


def test_the_latent_is_written_as_its_own_npy_entity():
    """
    Its own entity, so nothing about the picture moves: the media paths ask for
    `output_<kind>` and none of them asks for a latent.
    """
    from my_app.routes.schema_pipeline_routes import _save_output_latent

    payload = _npy(np.full((4, 8, 8), 1.5, dtype=np.float16))
    meta = {"model_id": "a-model/for-this-test", "pipeline_class": "APipeline",
            "shape": [4, 8, 8]}
    recorder = _Recorder()
    _save_output_latent(
        recorder,
        _result(latent_data=base64.b64encode(payload).decode("ascii"),
                latent_meta=meta, model_id="a-model/for-this-test"),
        "sd35_large", 42)

    assert len(recorder.saved) == 1
    written = recorder.saved[0]
    assert written["type"] == "output_latent"
    assert written["content"] == payload
    assert written["metadata"] == {
        "config": "sd35_large", "seed": 42, "model": "a-model/for-this-test",
        "format": "npy", "latent": meta,
    }
    # And it is a file numpy reads back, at the shape the meta claims.
    read = np.load(io.BytesIO(written["content"]), allow_pickle=False)
    assert list(read.shape) == meta["shape"]


@pytest.mark.parametrize("metadata", [
    {}, {"latent_data": ""}, {"latent_data": None}, {"latent_data": b"bytes"},
])
def test_a_run_that_kept_no_latent_writes_no_entity(metadata):
    from my_app.routes.schema_pipeline_routes import _save_output_latent

    recorder = _Recorder()
    _save_output_latent(recorder, SimpleNamespace(metadata=metadata), "c", 1)
    assert recorder.saved == []


def test_a_latent_that_cannot_be_decoded_costs_the_latent_and_not_the_run():
    from my_app.routes.schema_pipeline_routes import _save_output_latent

    recorder = _Recorder()
    _save_output_latent(recorder, _result(latent_data="!!! not base64 !!!"), "c", 1)
    assert recorder.saved == []


def test_a_store_that_will_not_take_the_latent_leaves_the_run_standing(caplog):
    """
    The picture IS the run and it is already written, its URL valid. A full or
    unwritable exports volume costs the latent mean of one set — it must not
    turn a finished generation into a failed one.
    """
    import logging

    from my_app.routes.schema_pipeline_routes import _save_output_latent

    caplog.set_level(logging.WARNING)
    recorder = _Recorder(breaks=OSError("no space left on device"))
    _save_output_latent(
        recorder,
        _result(latent_data=base64.b64encode(_npy(np.zeros((4, 8, 8)))).decode()),
        "sd35_large", 42)
    assert "no space left on device" in "\n".join(r.getMessage() for r in caplog.records)


def test_the_entity_names_the_model_of_the_picture_or_says_it_does_not_know():
    """Nothing is invented here: an absent name is written as 'unknown'."""
    from my_app.routes.schema_pipeline_routes import _save_output_latent

    recorder = _Recorder()
    _save_output_latent(recorder,
                        _result(latent_data=base64.b64encode(b"x").decode()), "c", 1)
    assert recorder.saved[0]["metadata"]["model"] == "unknown"
    assert recorder.saved[0]["metadata"]["latent"] == {}


# ---------------------------------------------------------------------------
# The chunk: it asks for the latent and hands on what came back
# ---------------------------------------------------------------------------

class _Backend:
    def __init__(self, latent: bytes = None, meta: dict = None):
        self.seen = {}
        self._latent = latent
        self._meta = meta

    async def availability(self):
        return True, ""

    async def generate_image(self, **kwargs):
        self.seen = kwargs
        sink = kwargs.get("latent_sink")
        if isinstance(sink, dict) and self._latent is not None:
            sink["latent"] = self._latent
            sink["meta"] = self._meta
        return b"\x89PNG-not-really-a-picture"


@pytest.mark.parametrize("chunk_name", CHUNKS)
def test_the_chunk_asks_for_the_latent_and_hands_it_on(monkeypatch, chunk_name):
    """
    Both halves have to travel: the flag, which tells the GPU service to keep the
    latent, and the sink, which is the only place the bytes can land. Either one
    alone leaves the run without a latent and says nothing about it.
    """
    import importlib

    import my_app.services.diffusers_client as diffusers_client

    chunk = importlib.import_module(chunk_name)
    payload = _npy(np.zeros((4, 8, 8), dtype=np.float16))
    meta = {"model_id": chunk.MODEL_ID, "pipeline_class": chunk.PIPELINE_CLASS,
            "shape": [4, 8, 8]}
    backend = _Backend(latent=payload, meta=meta)
    monkeypatch.setattr(diffusers_client, "get_diffusers_backend", lambda: backend)

    out = asyncio.run(chunk.execute(prompt="a house", seed=1, keep_latent=True))

    assert backend.seen.get("keep_latent") is True
    assert isinstance(backend.seen.get("latent_sink"), dict)
    assert base64.b64decode(out["latent_data"]) == payload
    assert out["latent_meta"] == meta
    # The picture is unchanged: it was decoded from exactly this latent.
    assert out["content_marker"] == "diffusers_generated"


@pytest.mark.parametrize("chunk_name", CHUNKS)
def test_without_the_flag_the_chunk_returns_what_it_always_did(monkeypatch, chunk_name):
    """Every run that does not ask travels exactly as it did before this build."""
    import importlib

    import my_app.services.diffusers_client as diffusers_client

    chunk = importlib.import_module(chunk_name)
    backend = _Backend()
    monkeypatch.setattr(diffusers_client, "get_diffusers_backend", lambda: backend)

    out = asyncio.run(chunk.execute(prompt="a house", seed=1))

    assert "keep_latent" not in backend.seen
    assert "latent_sink" not in backend.seen
    assert set(out) == {"content_marker", "image_data", "media_type", "backend",
                        "model_id", "seed", "parameters"}


@pytest.mark.parametrize("chunk_name", CHUNKS)
def test_a_run_asked_for_a_latent_it_did_not_get_still_returns_its_picture(
    monkeypatch, chunk_name
):
    """A run without a latent is a run without one, and the overlay says so."""
    import importlib

    import my_app.services.diffusers_client as diffusers_client

    chunk = importlib.import_module(chunk_name)
    backend = _Backend()          # asked, and the sink stays empty
    monkeypatch.setattr(diffusers_client, "get_diffusers_backend", lambda: backend)

    out = asyncio.run(chunk.execute(prompt="a house", seed=1, keep_latent=True))
    assert backend.seen.get("keep_latent") is True
    assert "latent_data" not in out and "latent_meta" not in out
    assert out["image_data"]


# ---------------------------------------------------------------------------
# The client: the flag goes out, the latent comes back into the sink
# ---------------------------------------------------------------------------

def test_generate_image_sends_the_flag_and_fills_the_sink(monkeypatch):
    import my_app.services.diffusers_client as diffusers_client

    sent = {}

    def post(path, data, timeout=None):
        sent.update({"path": path, "data": data})
        return {"success": True,
                "image_base64": base64.b64encode(b"PNG").decode(),
                "latent_base64": base64.b64encode(b"NPY").decode(),
                "latent_meta": {"model_id": "m", "shape": [4, 8, 8]}}

    client = diffusers_client.DiffusersClient()
    monkeypatch.setattr(client, "_post", post)
    sink = {}
    picture = asyncio.run(client.generate_image(prompt="a house", model_id="a-model",
                                                keep_latent=True, latent_sink=sink))

    assert sent["data"]["keep_latent"] is True
    assert picture == b"PNG"
    assert sink["latent"] == b"NPY"
    assert sink["meta"] == {"model_id": "m", "shape": [4, 8, 8]}


def test_generate_image_leaves_the_payload_alone_without_the_flag(monkeypatch):
    import my_app.services.diffusers_client as diffusers_client

    sent = {}

    def post(path, data, timeout=None):
        sent.update(data)
        return {"success": True, "image_base64": base64.b64encode(b"PNG").decode()}

    client = diffusers_client.DiffusersClient()
    monkeypatch.setattr(client, "_post", post)
    assert asyncio.run(client.generate_image(prompt="a house", model_id="a-model")) == b"PNG"
    assert "keep_latent" not in sent


# ---------------------------------------------------------------------------
# The first station: the request's flag reaches the chunk's parameters
# ---------------------------------------------------------------------------

def _executor_that_records(monkeypatch):
    """The pipeline executor, replaced by one that keeps the parameters it got."""
    import my_app.routes.schema_pipeline_routes as routes

    seen = {}

    async def execute_pipeline(**kwargs):
        override = kwargs.get("context_override")
        seen["custom"] = dict(getattr(override, "custom_placeholders", {}) or {})
        return SimpleNamespace(success=False, error="stopped here on purpose",
                               metadata={}, final_output=None)

    # The module holds the executor in a global that the app fills at start-up
    # and that stands at None in a test process, so the whole object is replaced.
    monkeypatch.setattr(routes, "pipeline_executor",
                        SimpleNamespace(execute_pipeline=execute_pipeline,
                                        config_loader=SimpleNamespace(
                                            get_config=lambda name: None)))
    return seen


@pytest.mark.parametrize("asked, expected", [(True, True), (False, None)])
def test_stage_four_carries_the_flag_into_the_chunks_parameters(
    monkeypatch, tmp_path, asked, expected
):
    """
    `custom_params` is the only road from a request to a chunk's `execute()`.
    A config with no latent to keep reads the key and ignores it — a ComfyUI
    workflow only reads the keys its own input mappings name.

    The store is a temporary one. This wrote its run into the REAL store under
    a fixed id, once per run of the suite, and by 2026-09-05 the id
    `run_for_this_test` stood in 81 DEVICE folders across TWO date folders —
    which is the shape `load_recorder` cannot choose between, so the recorder
    refuses it.
    """
    import config
    from my_app.services import pipeline_recorder as recorder_mod
    from my_app.routes.schema_pipeline_routes import execute_stage4_generation_only

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    recorder_mod._active_recorders.clear()

    seen = _executor_that_records(monkeypatch)
    asyncio.run(execute_stage4_generation_only(
        prompt="a house", output_config="sd35_large", safety_level="open",
        run_id="run_for_this_test", seed=1, keep_latent=asked))

    assert seen["custom"].get("keep_latent") is expected


@pytest.mark.parametrize("asked, expected", [(True, True), (False, None)])
def test_the_direct_route_carries_the_flag_into_the_chunks_parameters(
    monkeypatch, tmp_path, asked, expected
):
    """The instrument's own road: /api/schema/pipeline/direct.

    On a temporary store, like its sibling above. This one reaches
    `get_recorder` through `_run_direct_workflow` and had no such fixture, so
    it went on writing a run into the REAL store on every run of the suite.
    """
    import config
    from my_app.services import pipeline_recorder as recorder_mod
    from my_app.routes.schema_pipeline_routes import _run_direct_workflow

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    recorder_mod._active_recorders.clear()

    seen = _executor_that_records(monkeypatch)
    _run_direct_workflow(
        {"prompt": "a house", "output_config": "sd35_large", "seed": 1,
         "keep_latent": asked}, "open")

    assert seen["custom"].get("keep_latent") is expected


# ---------------------------------------------------------------------------
# Precision: what is lost, and where, when fifty latents are averaged
# ---------------------------------------------------------------------------

def test_fifty_float16_latents_are_averaged_in_float32():
    """
    `load_latent` widens to float32 on the way in, and the claim it makes is
    that the widening is not decoration: fifty float16 arrays averaged IN
    float16 lose the low bits of every one of them. Both halves are held here —
    the float32 sum is within float32 rounding of an exact one, and the float16
    sum is measurably further away.
    """
    rng = np.random.default_rng(5)
    raw = [rng.normal(0, 1, size=(4, 8, 8)).astype(np.float16) for _ in range(50)]

    got = mean_images.mean_latent(raw)
    exact = np.stack([a.astype(np.float64) for a in raw]).mean(0)
    in_float16 = np.stack(raw).mean(0, dtype=np.float16).astype(np.float64)

    assert got.dtype == np.float32
    assert np.max(np.abs(got - exact)) < 1e-5
    assert np.max(np.abs(in_float16 - exact)) > 1e-4


# ---------------------------------------------------------------------------
# The station between the chunk and the route: the executor's merge
# ---------------------------------------------------------------------------

def test_the_executor_carries_the_latent_out_of_the_last_step():
    """
    Sighted live on 2026-09-04: the GPU service kept the latent, the client
    carried it back, the chunk returned it — and every cell still said its mean
    was taken pixel by pixel. The keys stopped in `_execute_pipeline_steps`,
    which merges the last step's metadata through a fixed list of names and
    drops everything else without a word.

    The stubs in this file stop at the executor, which is why it slipped, so
    this one runs the REAL merge: a completed step whose metadata carries the
    latent and the picture, and nothing between it and the result.
    """
    from schemas.engine.pipeline_executor import (PipelineContext, PipelineExecutor,
                                                  PipelineStep)

    picture = io.BytesIO()
    from PIL import Image
    Image.new("RGB", (16, 16), (10, 120, 200)).save(picture, format="PNG")
    latent = base64.b64encode(_npy(np.zeros((4, 8, 8), dtype=np.float16))).decode()
    meta = {"model_id": "a-model/for-this-test", "pipeline_class": "APipeline",
            "shape": [4, 8, 8]}

    step = PipelineStep(step_id="output", chunk_name="a_chunk_for_this_test")
    step.metadata = {
        "image_data": base64.b64encode(picture.getvalue()).decode(),
        "media_type": "image",
        "model_id": meta["model_id"],
        "seed": 42,
        "latent_data": latent,
        "latent_meta": meta,
        # Held here so the assertions below mean something: this key is not on
        # the list, and it must not arrive. Without it, a merge that copied
        # everything would pass this test just as well as the gate does.
        "a_key_this_list_does_not_name": "should not arrive",
    }

    executor = PipelineExecutor(Path(__file__).resolve().parents[1] / "schemas")

    async def one_step(step_arg, context_arg, **kwargs):
        return "the step's own output"

    executor._execute_single_step = one_step
    result = asyncio.run(executor._execute_pipeline_steps(
        "a_config_for_this_test", [step],
        PipelineContext(input_text="a house", user_input="a house")))

    assert result.metadata["latent_data"] == latent
    assert result.metadata["latent_meta"] == meta
    # And the picture still travels. The disclosure is written into it at this
    # same point, so it is held on presence, not on its bytes.
    assert result.metadata["image_data"]
    assert result.metadata["seed"] == 42
    assert "a_key_this_list_does_not_name" not in result.metadata


# ---------------------------------------------------------------------------
# The ComfyUI leg of the same road
# ---------------------------------------------------------------------------

from schemas.engine.backend_router import _split_off_latent  # noqa: E402

DECODER = {"model_id": "a-model/for-this-test",
           "pipeline_class": "StableDiffusion3Pipeline"}


def _file(kind, data=b"x", meta=None):
    return SimpleNamespace(media_type=kind, data=data, filename=f"f.{kind}",
                           subfolder="", node_id="30", meta=meta or {})


def test_a_latent_leaves_the_media_files_and_arrives_as_its_own_key():
    """Handed on among the pictures, it would be shown as one."""
    latent, meta, media = _split_off_latent(
        [_file("image"), _file("latent", b"npy-bytes", {"shape": [16, 8, 8]}),
         _file("image")], DECODER)
    assert base64.b64decode(latent) == b"npy-bytes"
    assert [f.media_type for f in media] == ["image", "image"]
    assert meta["shape"] == [16, 8, 8]


def test_what_the_node_measured_and_what_the_chunk_declares_both_travel():
    _latent, meta, _media = _split_off_latent(
        [_file("latent", b"n", {"shape": [16, 8, 8], "dtype": "float16",
                                "scaling_factor": 1.5305, "shift_factor": 0.0609})],
        DECODER)
    assert meta["model_id"] == "a-model/for-this-test"
    assert meta["pipeline_class"] == "StableDiffusion3Pipeline"
    assert meta["scaling_factor"] == 1.5305 and meta["dtype"] == "float16"


def test_a_chunk_that_declares_no_decoder_keeps_no_latent():
    """Stored and undecodable answers the WHOLE set with an error.

    `_latent_of` raises LatentUnreadable when the entity names no model or no
    pipeline class, and the overlay route turns that into 502 for every cell of
    the set. Dropping it instead costs one set its latent mean and says so.
    """
    for decoder in (None, {}, {"model_id": "m"}, {"pipeline_class": "P"}):
        latent, meta, media = _split_off_latent(
            [_file("image"), _file("latent", b"n")], decoder)
        assert latent is None and meta == {}
        assert [f.media_type for f in media] == ["image"]


def test_the_comment_keys_of_the_declaration_stay_out_of_the_record():
    _latent, meta, _media = _split_off_latent(
        [_file("latent", b"n")], dict(DECODER, _comment="why this is here"))
    assert "_comment" not in meta


def test_a_second_latent_is_dropped_and_the_first_one_stands():
    latent, _meta, media = _split_off_latent(
        [_file("latent", b"first"), _file("latent", b"second"), _file("image")],
        DECODER)
    assert base64.b64decode(latent) == b"first"
    assert [f.media_type for f in media] == ["image"]


def test_a_run_without_a_latent_travels_exactly_as_before():
    latent, meta, media = _split_off_latent([_file("image"), _file("video")], DECODER)
    assert latent is None and meta == {}
    assert [f.media_type for f in media] == ["image", "video"]


COMFY_CHUNKS = [
    ("output_image_sd35_large.json", "stabilityai/stable-diffusion-3.5-large"),
    ("output_image_sd35_turbo.json", "stabilityai/stable-diffusion-3.5-large-turbo"),
]


@pytest.mark.parametrize("name,model_id", COMFY_CHUNKS)
def test_the_comfyui_chunk_keeps_a_latent_and_says_what_decodes_it(name, model_id):
    import json
    chunk = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "chunks" / name)
        .read_text(encoding="utf-8"))

    keep = chunk["input_mappings"]["keep_latent"]
    node = chunk["workflow"][keep["node_id"]]
    assert keep["default"] is False, "a run that did not ask must not pay for one"
    assert node["class_type"] == "AI4ArtsEdKeepLatent"

    # It reads the sampler and the decoder reads IT, so the picture the run
    # returns is decoded from exactly the latent that was written.
    assert node["inputs"]["samples"][0] == "8"
    assert chunk["workflow"]["2"]["inputs"]["samples"][0] == keep["node_id"]
    # The model is there for the latent format alone - see the node's header.
    assert node["inputs"]["model"][0] == "5"

    assert chunk["latent_decoder"]["model_id"] == model_id
    assert chunk["latent_decoder"]["pipeline_class"]


# ---------------------------------------------------------------------------
# The decode of a mean, in ComfyUI
# ---------------------------------------------------------------------------

from file_modules import REPO, load_module


def test_the_checkpoint_of_a_kept_latent_is_read_off_the_chunk_that_made_it():
    """The chunk that declares a model as the model of its latent is the chunk
    whose loader names the file; nothing is named in the decoder itself."""
    from my_app.services import latent_decoder
    assert latent_decoder.checkpoint_for(
        "stabilityai/stable-diffusion-3.5-large", "StableDiffusion3Pipeline"
    ) == "OfficialStableDiffusion/sd3.5_large.safetensors"
    assert latent_decoder.checkpoint_for(
        "stabilityai/stable-diffusion-3.5-large-turbo", "StableDiffusion3Pipeline"
    ) == "OfficialStableDiffusion/sd3.5_large_turbo.safetensors"


def test_a_model_no_chunk_declares_is_refused_by_name():
    from my_app.services import latent_decoder
    with pytest.raises(latent_decoder.LatentDecodeError) as raised:
        latent_decoder.checkpoint_for("nobody/made-this", "StableDiffusion3Pipeline")
    assert "nobody/made-this" in str(raised.value)


def test_the_decode_workflow_reads_the_file_through_the_platforms_node():
    from my_app.services import latent_decoder
    wf = latent_decoder.decode_workflow("OfficialStableDiffusion/sd3.5_large.safetensors",
                                        "mean.npy")
    of = lambda cls: [k for k, n in wf.items() if n["class_type"] == cls]
    loader, reader = of("CheckpointLoaderSimple"), of(latent_decoder.LOAD_NODE)
    decode, save = of("VAEDecode"), of("SaveImage")
    assert len(loader) == len(reader) == len(decode) == len(save) == 1
    assert wf[reader[0]]["inputs"]["model"] == [loader[0], 0]
    assert wf[reader[0]]["inputs"]["latent_file"] == "mean.npy"
    assert wf[decode[0]]["inputs"]["samples"] == [reader[0], 0]
    assert wf[decode[0]]["inputs"]["vae"] == [loader[0], 2]
    assert wf[save[0]]["inputs"]["images"] == [decode[0], 0]


def test_the_reader_node_is_registered_under_the_name_the_workflow_uses():
    """Read off the node file's mapping the way test_own_comfyui_nodes reads
    every own node, without ComfyUI's imports."""
    from test_own_comfyui_nodes import _mappings
    from my_app.services import latent_decoder
    assert latent_decoder.LOAD_NODE in _mappings(
        REPO / "comfyui_nodes" / "ai4artsed_keep_latent.py")


class _Comfy:
    """A ws client that remembers the upload, the workflow and the order of
    the two, and answers pictures. `submit_and_track` mirrors the real
    signature, so a keyword the decoder passes has to exist there."""

    def __init__(self, files=None, upload=True, stored_as=None, raises=None,
                 outputs=None):
        self.uploaded = []
        self.workflow = None
        self.workload = None
        self.calls = []
        self._files = files
        self._upload = upload
        self._stored_as = stored_as
        self._raises = raises
        self._outputs = outputs

    async def upload_file(self, data, filename):
        from my_app.services.comfyui_ws_client import ComfyUIUploadError
        self.calls.append("upload")
        if not self._upload:
            raise ComfyUIUploadError(503, "no room in the input directory")
        self.uploaded.append((data, filename))
        return self._stored_as or filename

    async def submit_and_track(self, workflow, timeout=480, on_progress=None,
                               on_event=None, before_submit=None):
        from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
        self.calls.append("lease")
        self.workload = CURRENT_OUTPUT_CONFIG.get()
        if before_submit is not None:
            await before_submit()
        self.calls.append("submit")
        self.workflow = workflow
        if self._raises:
            raise self._raises
        files = self._files
        if files is None:
            files = [SimpleNamespace(media_type="image", data=b"PNG")]
        outputs = self._outputs
        if outputs is None:
            outputs = {"4": {"images": [{"filename": "ai4artsed_mean_00001_.png"}]}}
        return SimpleNamespace(media_files=files, prompt_id="p-1",
                               outputs_metadata=outputs)


_META = {"model_id": "stabilityai/stable-diffusion-3.5-large",
         "pipeline_class": "StableDiffusion3Pipeline"}


def _with(monkeypatch, comfy, comfyui_up=True):
    async def available():
        return comfyui_up
    monkeypatch.setattr("my_app.services.comfyui_manager.get_comfyui_manager",
                        lambda: SimpleNamespace(ensure_comfyui_available=available))
    monkeypatch.setattr("my_app.services.comfyui_ws_client.get_comfyui_ws_client",
                        lambda: comfy)
    return comfy


def _decode(npy=b"npy"):
    from my_app.services import latent_decoder
    return asyncio.run(latent_decoder.decode_in_comfyui(_META, npy))


def test_the_mean_goes_up_as_a_file_and_comes_back_as_a_picture(monkeypatch):
    from my_app.services import latent_decoder
    comfy = _with(monkeypatch, _Comfy())
    assert _decode() == b"PNG"
    (data, name), = comfy.uploaded
    assert data == b"npy" and name.endswith(".npy")
    reader = [n for n in comfy.workflow.values()
              if n["class_type"] == latent_decoder.LOAD_NODE][0]
    assert reader["inputs"]["latent_file"] == name
    loader = [n for n in comfy.workflow.values()
              if n["class_type"] == "CheckpointLoaderSimple"][0]
    assert loader["inputs"]["ckpt_name"] == "OfficialStableDiffusion/sd3.5_large.safetensors"


def test_the_file_goes_up_under_the_lease_and_before_the_submission(monkeypatch):
    """A file that lay in ComfyUI's input directory through a wait for the
    card is gone after a restart, which empties that directory."""
    comfy = _with(monkeypatch, _Comfy())
    _decode()
    assert comfy.calls == ["lease", "upload", "submit"]


def test_the_decode_is_filed_under_its_own_workload(monkeypatch):
    """The gate's durations for a generation on this checkpoint must not
    learn from a decode of a few seconds."""
    from my_app.services import latent_decoder
    from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
    comfy = _with(monkeypatch, _Comfy())
    before = CURRENT_OUTPUT_CONFIG.get()
    _decode()
    assert comfy.workload == latent_decoder.DECODE_WORKLOAD == "vae-decode"
    assert CURRENT_OUTPUT_CONFIG.get() == before


def test_two_means_never_share_a_file_name(monkeypatch):
    """Two decodes in flight write two files; and ComfyUI keys its cache on a
    node's inputs, so the same name twice would answer the second mean with
    the first picture, without running."""
    comfy = _with(monkeypatch, _Comfy())
    _decode(b"one")
    _decode(b"two")
    names = [name for _data, name in comfy.uploaded]
    assert len(set(names)) == 2


@pytest.mark.parametrize("comfy, said", [
    (_Comfy(upload=False), "refused the upload (HTTP 503): no room"),
    (_Comfy(stored_as="elsewhere.npy"), "stored the latent as 'elsewhere.npy'"),
    (_Comfy(raises=RuntimeError("node 2: no such latent file")), "no such latent file"),
    (_Comfy(files=[], outputs={}), "history holds no outputs"),
    (_Comfy(files=[]), "could not be downloaded"),
    (_Comfy(files=[], outputs={"4": {}}), "announced no picture"),
    (_Comfy(files=[SimpleNamespace(media_type="latent", data=b"x")], outputs={"4": {}}),
     "announced no picture"),
])
def test_every_failed_decode_in_comfyui_raises_with_its_reason(monkeypatch, comfy, said):
    from my_app.services import latent_decoder
    _with(monkeypatch, comfy)
    with pytest.raises(latent_decoder.LatentDecodeError) as raised:
        _decode()
    assert said in str(raised.value)


def test_comfyui_that_is_down_is_named_before_anything_goes_up(monkeypatch):
    from my_app.services import latent_decoder
    comfy = _with(monkeypatch, _Comfy(), comfyui_up=False)
    with pytest.raises(latent_decoder.LatentDecodeError) as raised:
        _decode()
    assert "ComfyUI is not available" in str(raised.value)
    assert comfy.calls == []


def test_a_card_that_is_taken_still_travels_as_its_own_type_out_of_comfyui(monkeypatch):
    from my_app.services.gpu_lease_client import GpuBusyError
    _with(monkeypatch, _Comfy(raises=GpuBusyError("a training holds the card")))
    with pytest.raises(GpuBusyError):
        _decode()


def test_the_route_imports_no_diffusers_client_for_the_decode():
    """That the route calls the decoder is proven by the `decoder` fixture of
    test_mean_images.py, which replaces it and records the call. This one only
    holds that the old client is out of the file."""
    source = (REPO / "devserver" / "my_app" / "routes" / "mean_images_routes.py"
              ).read_text(encoding="utf-8")
    assert "latent_decoder.decode_in_comfyui(" in source
    assert "diffusers_client" not in source


# --- the node itself: keep, then load, on a stand-in model ------------------

def _node_file(tmp_path, monkeypatch):
    """The node file, loaded with a `folder_paths` that lives in tmp_path."""
    import sys
    import types
    torch = pytest.importorskip("torch")
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: str(tmp_path)
    folder_paths.get_annotated_filepath = lambda name: str(tmp_path / name)
    folder_paths.exists_annotated_filepath = lambda name: (tmp_path / name).exists()
    folder_paths.get_save_image_path = (
        lambda prefix, out: (str(tmp_path), prefix, 1, "", prefix))
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    module = load_module("ai4artsed_keep_latent_under_test",
                         REPO / "comfyui_nodes" / "ai4artsed_keep_latent.py")
    return module, torch


def _sd3_model():
    """SD 3.5's latent format, the affine ComfyUI's SD3 class carries."""
    scale, shift = 1.5305, 0.0609
    return SimpleNamespace(model=SimpleNamespace(
        latent_format=SimpleNamespace(scale_factor=scale, shift_factor=shift),
        process_latent_in=lambda x: (x - shift) * scale,
        process_latent_out=lambda x: x / scale + shift,
    ))


def test_a_kept_latent_read_back_is_the_latent_the_sampler_gave(tmp_path, monkeypatch):
    """Keep applies the model's step in, load applies it out: what reaches
    the VAE decode is what left the sampler, up to float16."""
    N, torch = _node_file(tmp_path, monkeypatch)
    model = _sd3_model()
    samples = torch.randn((1, 16, 4, 4), generator=torch.Generator().manual_seed(7))
    kept = N.AI4ArtsEdKeepLatent().keep(model, {"samples": samples}, True, "ai4artsed_latent")
    name = kept["ui"]["latents"][0]["filename"]
    (back,) = N.AI4ArtsEdLoadKeptLatent().load(model, name)
    assert back["samples"].shape == (1, 16, 4, 4)
    assert torch.allclose(back["samples"], samples, atol=5e-3)
    assert N.AI4ArtsEdLoadKeptLatent.VALIDATE_INPUTS(name) is True


def test_the_reader_applies_the_models_step_out_exactly_once(tmp_path, monkeypatch):
    """The mean is written in the model's own space (scaled and shifted);
    reading it back into the VAE's space is one application of the inverse."""
    N, torch = _node_file(tmp_path, monkeypatch)
    import numpy as np
    model = _sd3_model()
    np.save(tmp_path / "flat.npy", np.zeros((16, 2, 2), dtype=np.float32))
    (out,) = N.AI4ArtsEdLoadKeptLatent().load(model, "flat.npy")
    assert torch.allclose(out["samples"], torch.full((1, 16, 2, 2), 0.0609))


def test_the_reader_fingerprints_the_file_it_reads(tmp_path, monkeypatch):
    N, _torch = _node_file(tmp_path, monkeypatch)
    import numpy as np
    np.save(tmp_path / "a.npy", np.zeros((16, 2, 2), dtype=np.float32))
    first = N.AI4ArtsEdLoadKeptLatent.IS_CHANGED(None, "a.npy")
    np.save(tmp_path / "a.npy", np.ones((16, 2, 2), dtype=np.float32))
    assert N.AI4ArtsEdLoadKeptLatent.IS_CHANGED(None, "a.npy") != first


@pytest.mark.parametrize("write, said", [
    (lambda p: p.write_bytes(b"\x89PNG\r\n\x1a\n...."), "is no .npy file"),
    (lambda p: __import__("numpy").save(p, __import__("numpy").zeros((4, 4), dtype="float32")),
     "a latent of shape [C, h, w] is required"),
    (lambda p: __import__("numpy").save(p, __import__("numpy").full((16, 2, 2), float("nan"),
                                                                    dtype="float32")),
     "values that are not numbers"),
])
def test_what_is_no_latent_of_one_picture_is_refused_with_its_reason(
        tmp_path, monkeypatch, write, said):
    N, _torch = _node_file(tmp_path, monkeypatch)
    write(tmp_path / "x.npy")
    with pytest.raises(ValueError) as raised:
        N.AI4ArtsEdLoadKeptLatent().load(_sd3_model(), "x.npy")
    assert said in str(raised.value)


def test_a_file_the_input_directory_does_not_hold_fails_validation(tmp_path, monkeypatch):
    N, _torch = _node_file(tmp_path, monkeypatch)
    said = N.AI4ArtsEdLoadKeptLatent.VALIDATE_INPUTS("nowhere.npy")
    assert said is not True and "nowhere.npy" in said
