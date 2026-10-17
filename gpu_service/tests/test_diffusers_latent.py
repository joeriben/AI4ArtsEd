"""A latent that outlives its run, and the picture it decodes to.

Mean Images averages many pictures into one. Taken before the
decoder the mean keeps the local sharpness of a single picture; taken on the
finished PNGs it keeps less than half. So a run hands its final latent back and
a later request decodes the mean of many -- which only works if both sides do
the same arithmetic and speak the same wire form.

What the tests here hold on to:
  - the wire form survives the round trip (shape, float16, values), refuses a
    pickled .npy, and refuses a latent that is not finite;
  - the decode adds the shift. The live preview inside generate_image divides
    by scaling_factor and stops there; copying that would return a picture the
    run itself never produced;
  - a kept latent and the metadata beside it describe the SAME array -- shape,
    dtype and the pipeline class the run actually resolved to;
  - a run that cannot keep a latent keeps none and still paints its picture;
  - the routes refuse before the card what the card would refuse expensively,
    name what was wrong, and pass a busy card on as 503.

No model, no GPU, no diffusers pipeline: stand-ins with the handful of
attributes the arithmetic reads.
"""

import asyncio
import base64
import io
import os
import sys
import types

import numpy as np
import pytest
import torch
from PIL import Image

GPU_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GPU_SERVICE_DIR not in sys.path:
    sys.path.insert(0, GPU_SERVICE_DIR)

from services.diffusers_backend import (DiffusersImageGenerator,  # noqa: E402
                                        decode_latent_tensor,
                                        latent_to_npy_bytes,
                                        npy_bytes_to_array)
from services.gpu_admission import GpuBusy  # noqa: E402

# SD3.5's own numbers, so the tests read like the thing they stand for.
SCALING = 1.5305
SHIFT = 0.0609
LATENT_CHANNELS = 16

# Made-up ids: no checkpoint has to exist, and the second one carries the
# spelling _pipeline_class_for reads the SDXL family off.
FAKE_SD3 = "fake/triple-encoder"
FAKE_SDXL = "fake/commoncanvas-xl-c"
FAKE_FLUX = "fake/flux-two"


def _png(picture) -> bytes:
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    return buffer.getvalue()


def _npy(array) -> bytes:
    """A .npy the way a careless caller would send one -- no checks applied."""
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


class StubVae:
    """A VAE reduced to what the decode arithmetic touches, and a memory."""

    def __init__(self, scaling_factor=SCALING, shift_factor=SHIFT,
                 latent_channels=LATENT_CHANNELS):
        self.config = types.SimpleNamespace(
            scaling_factor=scaling_factor,
            shift_factor=shift_factor,
            latent_channels=latent_channels,
            block_out_channels=[128, 256, 512, 512],
        )
        self.seen = None
        self.tiled = False
        self.dtype = torch.float32
        self.device = torch.device("cpu")

    def enable_tiling(self):
        self.tiled = True

    def decode(self, latents, return_dict=False):
        self.seen = latents
        return (latents,)


class StubProcessor:
    """Hands back what it was given, so the test can look at it."""

    def postprocess(self, image, output_type="pil"):
        return [image]


class PictureProcessor:
    """Returns a real picture, and remembers the tensor it was handed."""

    def __init__(self):
        self.seen = None
        self.picture = Image.new("RGB", (2, 2), (10, 20, 30))

    def postprocess(self, image, output_type="pil"):
        self.seen = image
        return [self.picture]


class StubPipe:
    """A pipeline reduced to: callable, and it owns a VAE and a processor."""

    def __init__(self, latent):
        self.vae = StubVae()
        self.image_processor = PictureProcessor()
        self.latent = latent
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        if kwargs.get("output_type") == "latent":
            return types.SimpleNamespace(images=self.latent)
        return types.SimpleNamespace(images=[self.image_processor.picture])


# =============================================================================
# The wire form
# =============================================================================

def test_the_latent_survives_the_round_trip():
    """Shape, dtype and values, as they leave and as they come back."""
    source = (np.arange(16 * 4 * 4, dtype=np.float32).reshape(16, 4, 4) / 7.0) - 100.0

    restored = npy_bytes_to_array(latent_to_npy_bytes(source))

    assert restored.dtype == np.float16, "the wire form is float16, always"
    assert restored.shape == (16, 4, 4)
    np.testing.assert_array_equal(restored, source.astype(np.float16))


def test_the_batch_axis_is_dropped_on_the_way_out():
    """A run makes one picture, so [1, C, h, w] and [C, h, w] are one thing."""
    source = np.zeros((1, 16, 4, 4), dtype=np.float32)

    assert npy_bytes_to_array(latent_to_npy_bytes(source)).shape == (16, 4, 4)
    # A real batch is left alone rather than silently halved.
    batched = np.zeros((2, 16, 4, 4), dtype=np.float32)
    assert npy_bytes_to_array(latent_to_npy_bytes(batched)).shape == (2, 16, 4, 4)


def test_a_pickled_npy_is_refused():
    """This parses an HTTP body. A pickled .npy is code, not numbers."""
    buffer = io.BytesIO()
    np.save(buffer, np.array([{"run": "code"}], dtype=object), allow_pickle=True)

    with pytest.raises(ValueError):
        npy_bytes_to_array(buffer.getvalue())


def test_a_latent_that_is_not_finite_is_refused_rather_than_written():
    """One diverged run would otherwise turn the mean of twenty into a black square."""
    broken = np.zeros((16, 4, 4), dtype=np.float32)
    broken[0, 0, 0] = np.nan

    with pytest.raises(ValueError, match="not finite"):
        latent_to_npy_bytes(broken)


def test_a_value_the_cast_turns_into_inf_is_refused_too():
    """Finite in float32, Inf in float16 -- checked AFTER the cast, or not at all."""
    with pytest.raises(ValueError, match="not finite"):
        latent_to_npy_bytes(np.full((16, 4, 4), 1e6, dtype=np.float32))


# =============================================================================
# The decode arithmetic
# =============================================================================

def test_the_decode_adds_the_shift():
    """`latent / scaling_factor + shift_factor` -- the pipeline's own last step.

    Without the shift every picture comes out off by a constant, and the flag
    would change the picture it was only supposed to also keep. (Struck with
    the decode route on 2026-10-10 although the arithmetic stayed; back since
    the second review.)
    """
    vae, processor = StubVae(), StubProcessor()
    latent = torch.randn(16, 8, 8, dtype=torch.float32)

    returned = decode_latent_tensor(vae, processor, latent)

    expected = latent.unsqueeze(0) / SCALING + SHIFT
    assert torch.allclose(vae.seen, expected, atol=1e-6)
    assert not torch.allclose(vae.seen, latent.unsqueeze(0) / SCALING), \
        "the shift is what this test exists for"
    assert returned is vae.seen, "what the VAE returned is what the processor got"


def test_the_decode_takes_a_latent_with_or_without_a_batch_axis():
    """The stored form has no batch axis; the pipeline's has one."""
    vae, processor = StubVae(), StubProcessor()
    latent = torch.zeros(16, 8, 8)

    decode_latent_tensor(vae, processor, latent)
    assert tuple(vae.seen.shape) == (1, 16, 8, 8)

    decode_latent_tensor(vae, processor, latent.unsqueeze(0))
    assert tuple(vae.seen.shape) == (1, 16, 8, 8)


def test_a_vae_without_a_shift_is_read_as_no_shift():
    """SDXL scales and does not shift; its config carries the field as None."""
    vae, processor = StubVae(shift_factor=None), StubProcessor()
    latent = torch.randn(4, 8, 8)

    decode_latent_tensor(vae, processor, latent)

    assert torch.allclose(vae.seen, latent.unsqueeze(0) / SCALING, atol=1e-6)


# =============================================================================
# generate_image: what a run keeps, and when it keeps nothing
# =============================================================================

@pytest.fixture
def backend(monkeypatch):
    """The real generator, with no card under it.

    The plant-wide slot and the inference lock have their own file
    (test_diffusers_tokenizer_lock.py); here they would only add a thread
    between the assertion and what it is about.
    """
    made = DiffusersImageGenerator()
    made.device = "cpu"

    async def _already_loaded(model_id, pipeline_class="StableDiffusion3Pipeline",
                              prefetch=False):
        return True

    monkeypatch.setattr(made, "load_model", _already_loaded)
    monkeypatch.setattr(made, "_locked_generate", lambda fn: fn())
    return made


def _generate(backend, pipe, model_id=FAKE_SD3, **kwargs):
    """One run of generate_image with the sink held open. Returns (png, sink)."""
    backend._pipelines[model_id] = pipe
    sink = {}
    png = asyncio.run(backend.generate_image(
        prompt="a red apple",
        model_id=model_id,
        steps=2,
        seed=7,
        keep_latent=True,
        latent_sink=sink,
        **kwargs,
    ))
    assert png is not None, "generate_image swallowed an error -- read the captured log"
    return png, sink


def test_the_kept_latent_and_its_metadata_describe_the_same_array(backend):
    """meta.shape is read off the array that was written, not off another one.

    The batch axis is where this goes wrong quietly: the .npy drops it, and a
    metadata shape computed one line earlier still carries it. Nothing fails,
    and the DevServer compares shapes that no latent has.
    """
    latent = torch.arange(16 * 8 * 8, dtype=torch.float32).reshape(1, 16, 8, 8) / 1000.0
    pipe = StubPipe(latent)

    png, sink = _generate(backend, pipe)

    written = npy_bytes_to_array(sink["latent"])
    assert sink["meta"]["shape"] == list(written.shape)
    assert tuple(written.shape) == (16, 8, 8)
    assert sink["meta"]["dtype"] == str(written.dtype) == "float16"
    assert sink["meta"]["model_id"] == FAKE_SD3
    assert sink["meta"]["pipeline_class"] == "StableDiffusion3Pipeline"
    assert sink["meta"]["scaling_factor"] == SCALING
    assert sink["meta"]["shift_factor"] == SHIFT
    np.testing.assert_allclose(
        written.astype(np.float32),
        latent[0].numpy().astype(np.float16).astype(np.float32))

    # The picture came out of that same latent, through the pipeline's own tail.
    assert pipe.kwargs["output_type"] == "latent"
    assert torch.allclose(pipe.image_processor.seen, latent / SCALING + SHIFT, atol=1e-6)
    assert png == _png(pipe.image_processor.picture)


def test_a_class_that_is_not_sd3_keeps_no_latent(backend):
    """Flux and the video pipelines hold a latent of another shape entirely."""
    pipe = StubPipe(torch.zeros(1, 16, 8, 8))

    png, sink = _generate(backend, pipe, model_id=FAKE_FLUX,
                          pipeline_class="Flux2Pipeline")

    assert sink == {}
    assert "output_type" not in pipe.kwargs, "the pipeline ran its own decoder"
    assert png == _png(pipe.image_processor.picture)


def test_a_model_id_that_resolves_to_sdxl_keeps_no_latent(backend):
    """The route's default class is SD3; the id says otherwise, and the id wins.

    Run with output_type="latent" this would hand out an SDXL latent and then
    decode it through SD3's tail -- a wrong picture, and nothing to say so.
    """
    pipe = StubPipe(torch.zeros(1, 4, 8, 8))

    png, sink = _generate(backend, pipe, model_id=FAKE_SDXL)

    assert sink == {}
    assert "output_type" not in pipe.kwargs
    assert png == _png(pipe.image_processor.picture)


def test_img2img_keeps_no_latent(backend, monkeypatch):
    """A picture in means another pipeline object runs; its latent is not this one."""
    import diffusers

    latent = torch.zeros(1, 16, 8, 8)
    pipe = StubPipe(latent)
    made = []

    class StubImg2Img:
        @classmethod
        def from_pipe(cls, source):
            i2i = StubPipe(latent)
            made.append(i2i)
            return i2i

    monkeypatch.setattr(diffusers, "StableDiffusion3Img2ImgPipeline", StubImg2Img,
                        raising=False)

    png, sink = _generate(backend, pipe, image_bytes=_png(Image.new("RGB", (4, 4))))

    assert sink == {}
    assert made and made[0].vae.tiled, "the img2img path is the one that ran"
    assert png == _png(made[0].image_processor.picture)


def test_a_latent_that_diverged_is_not_kept_and_the_picture_still_comes_back(backend):
    """The run keeps its picture; the set is then meaned pixel by pixel, and says so."""
    latent = torch.zeros(1, 16, 8, 8)
    latent[0, 3, 4, 5] = float("nan")
    pipe = StubPipe(latent)

    png, sink = _generate(backend, pipe)

    assert sink == {}, "no latent, and no metadata describing one either"
    assert png == _png(pipe.image_processor.picture)


# =============================================================================
# The routes
# =============================================================================

LATENT = np.full((16, 8, 8), 0.25, dtype=np.float32)
META = {
    "model_id": FAKE_SD3,
    "pipeline_class": "StableDiffusion3Pipeline",
    "scaling_factor": SCALING,
    "shift_factor": SHIFT,
    "shape": [16, 8, 8],
    "dtype": "float16",
}


class StubBackend:
    """A generation that keeps its latent, and a decode that gives it back."""

    def __init__(self, fails=None):
        self.fails = fails
        self.asked_keep = None
        self.decoded = None

    async def generate_image(self, **kwargs):
        self.asked_keep = kwargs.get("keep_latent")
        sink = kwargs.get("latent_sink")
        if kwargs.get("keep_latent") and sink is not None:
            sink["latent"] = latent_to_npy_bytes(LATENT)
            sink["meta"] = dict(META)
        return b"PNG-of-that-latent"

    async def decode_latent(self, model_id, pipeline_class, latent, error_sink=None):
        self.decoded = latent
        if self.fails:
            if error_sink is not None:
                error_sink["error"] = self.fails
            return None
        return b"PNG-of-the-mean"


class BusyBackend:
    """The card is occupied. Both routes have to say so the same way."""

    decoded = None

    async def generate_image(self, **kwargs):
        raise GpuBusy("queue full", reason="queue_full")

    async def decode_latent(self, **kwargs):
        raise GpuBusy("queue full", reason="queue_full")


@pytest.fixture
def client(monkeypatch):
    """The blueprint on a bare Flask app, with a stub where the card would be.

    `client.holder["backend"]` is the stub; a test that needs another one puts
    it there.
    """
    from flask import Flask, jsonify
    import routes.diffusers_routes as routes

    holder = {"backend": StubBackend()}
    monkeypatch.setattr(routes, "_get_backend", lambda: holder["backend"])
    app = Flask(__name__)
    app.register_blueprint(routes.diffusers_bp)

    # The answer app.create_app() gives, in the part these tests read: busy is
    # not broken, and a caller handed 500 retries nothing.
    @app.errorhandler(GpuBusy)
    def _gpu_busy(e):
        return jsonify({"success": False, "error": str(e), "code": "gpu_busy",
                        "busy_reason": getattr(e, "reason", "busy")}), 503

    with app.test_client() as made:
        made.holder = holder
        yield made


def test_the_latent_travels_only_when_it_was_asked_for(client):
    """`keep_latent` is what puts the two fields into the answer, nothing else."""
    asked = client.post("/api/diffusers/generate",
                        json={"prompt": "a red apple", "keep_latent": True}).get_json()

    assert asked["success"] is True
    assert asked["latent_meta"] == META
    restored = npy_bytes_to_array(base64.b64decode(asked["latent_base64"]))
    np.testing.assert_array_equal(restored, LATENT.astype(np.float16))

    plain = client.post("/api/diffusers/generate",
                        json={"prompt": "a red apple"}).get_json()

    assert plain["success"] is True
    assert "latent_base64" not in plain and "latent_meta" not in plain
    assert client.holder["backend"].asked_keep is False, \
        "the flag reaches the backend as it came"


def test_a_pipeline_that_keeps_no_latent_still_answers_with_its_picture(client):
    """img2img and Flux2 keep none. That is an absence, not a failure."""
    class NoLatent(StubBackend):
        async def generate_image(self, **kwargs):
            return b"PNG"

    client.holder["backend"] = NoLatent()

    answer = client.post("/api/diffusers/generate",
                         json={"prompt": "x", "keep_latent": True})

    assert answer.status_code == 200
    assert answer.get_json()["success"] is True
    assert "latent_base64" not in answer.get_json()



def test_a_busy_card_answers_503(client):
    """Busy is not broken. A caller handed 500 reports a failed run and retries nothing."""
    client.holder["backend"] = BusyBackend()

    generated = client.post("/api/diffusers/generate",
                            json={"prompt": "x", "keep_latent": True})
    assert generated.status_code == 503
    assert generated.get_json()["code"] == "gpu_busy"
