"""
Diffusers Backend - Direct HuggingFace Diffusers inference

Direct model inference backend.
Provides full control over the inference pipeline and optional TensorRT acceleration.

Features:
- StableDiffusion3Pipeline for SD3.5 Large/Medium
- FluxPipeline for Flux models
- TensorRT acceleration (2.3x speedup when available)
- Step-by-step callback for live preview streaming
- VRAM management with model loading/unloading

Usage:
    backend = get_diffusers_backend()
    if await backend.is_available():
        image_bytes = await backend.generate_image(
            prompt="A red apple",
            model_id="stabilityai/stable-diffusion-3.5-large",
            seed=42,
            callback=step_callback  # For live preview
        )
"""

import gc
import logging
import threading
import time
import warnings
from typing import Optional, Dict, Any, Callable
import asyncio

# Suppress noisy HuggingFace tokenizer deprecation warnings
warnings.filterwarnings("ignore", message=".*add_prefix_space.*")
warnings.filterwarnings("ignore", message=".*slow tokenizers.*")
warnings.filterwarnings("ignore", message=".*Token indices sequence length is longer than.*")

from services.gpu_admission import GpuBusy
from config import DEFAULT_MODEL_ID
from services.generation_failure import GenerationFailed
from services.generation_cancel import (GenerationCancelled,
                                        interrupt_if_cancelled,
                                        raise_if_cancelled)

logger = logging.getLogger(__name__)

# Module-level generation progress (thread-safe via GIL for simple dict ops)
_generation_progress = {"step": 0, "total_steps": 0, "active": False}


def get_generation_progress() -> dict:
    """Return current generation progress for polling endpoint."""
    return dict(_generation_progress)


# === Decomposition Mode: 3×3×3 Intervention Space ===
# Geometry for SD3.5 Large MMDiT (38 transformer blocks, 3 text encoders).
#
# Step phase names follow Kwon et al. 2023 ("Diffusion Models Already Have a
# Semantic Latent Space", ICLR 2023, arXiv:2210.10960), as adapted to 25-step
# SD3.5 in this codebase's docs/LATENT_LAB_SCIENTIFIC_FOUNDATION.md (sec. 5):
#   composition (Steps 1–8), semantics (Steps 9–17), detail (Steps 18–25)
#   → fractional boundaries 8/25 = 0.32 and 17/25 = 0.68.
# Disclaimer per platform docs: these phase boundaries are empirically
# adapted from Kwon's DDPM/SD1.x findings to SD3.5 Rectified Flow — descriptive
# observations, not normative laws.
DECOMP_STEP_BANDS = {
    'composition': (0.0,  0.32),
    'semantics':   (0.32, 0.68),
    'detail':      (0.68, 1.01),  # 1.01 to include the final step at frac == 1.0
}
# Layer band names follow the platform's Attention Cartography convention
# ("shallow/middle/deep", inspired by Tang et al. 2022 DAAM multi-layer analysis).
# Original Latent Lab references layers 3, 9, 17 for SD3.5 Medium (24 blocks).
# For SD3.5 Large (38 blocks), these midpoints scale proportionally to
# approximately 5, 14, 27 — bands defined around them.
DECOMP_LAYER_BANDS = {
    'shallow': (0,  10),
    'middle':  (10, 23),
    'deep':    (23, 38),
}
# Slices in pre-projection 4096-dim prompt_embeds space.
# Layout: tokens [0:77] = CLIP-L (dims 0:768) || CLIP-G (dims 768:2048) || padding (dims 2048:4096),
#         tokens [77:]  = T5-XXL (all 4096 dims).
DECOMP_STREAM_SLICES = {
    'clip_l': (slice(0, 77),   slice(0, 768)),
    'clip_g': (slice(0, 77),   slice(768, 2048)),
    't5':    (slice(77, None), slice(None, None)),
}
DECOMP_VALID_STREAMS = set(DECOMP_STREAM_SLICES.keys())
DECOMP_VALID_STEP_BANDS = set(DECOMP_STEP_BANDS.keys())
DECOMP_VALID_LAYER_BANDS = set(DECOMP_LAYER_BANDS.keys())


def _install_run_scheduler(pipe, scheduler_name: Optional[str], shift: Optional[float]) -> None:
    """Put the scheduler ONE run asked for onto an already loaded pipeline.

    The two backbones of Denoising Archaeology offer different room here, and
    that difference is the point of offering it at all:
      - SDXL runs a curved path, and fifteen different rules for walking it are
        built. They come out of the pipeline's own `compatibles` list.
      - SD3.5 runs a straight one, so there is exactly one rule -- what can be
        set is `shift`, how the steps are SPREAD along that path.

    An unknown name or a shift the scheduler does not carry is logged and
    skipped. A generation is not worth losing because a surface sent a word this
    diffusers version does not know.

    The caller restores the previous scheduler; doing it here would need the
    caller to hold it anyway.
    """
    if not scheduler_name and shift is None:
        return

    current = pipe.scheduler
    target = type(current)

    if scheduler_name:
        allowed = {c.__name__: c for c in getattr(current, "compatibles", [])}
        allowed[type(current).__name__] = type(current)
        picked = allowed.get(scheduler_name)
        if picked is None:
            logger.warning(
                "[SCHEDULER] %r is not compatible with %s, staying with %s",
                scheduler_name, type(pipe).__name__, type(current).__name__,
            )
        else:
            target = picked

    cfg = dict(current.config)
    if shift is not None:
        if "shift" not in cfg:
            logger.warning("[SCHEDULER] %s carries no shift, ignoring %r", target.__name__, shift)
        else:
            try:
                cfg["shift"] = float(shift)
            except (TypeError, ValueError):
                logger.warning("[SCHEDULER] Unreadable shift %r, keeping %s", shift, cfg["shift"])

    try:
        pipe.scheduler = target.from_config(cfg)
    except Exception as e:
        # The promise above is that a bad value costs no run, and it has to hold
        # for the value that reaches diffusers, not only for the one this
        # function reads. The caller is already past the point where it could
        # report a bad request, and the pipeline still has its own scheduler.
        logger.warning("[SCHEDULER] %s could not be built (%s), staying with %s",
                       target.__name__, e, type(current).__name__)
        return

    logger.info(
        "[SCHEDULER] %s (order %s%s)",
        target.__name__,
        getattr(pipe.scheduler, "order", 1),
        f", shift {cfg['shift']}" if shift is not None and "shift" in cfg else "",
    )


# === Latents that outlive their run ===
# Mean Images averages many pictures into one. Measured on 20 of
# them: the mean taken BEFORE the decoder keeps the local sharpness of a single
# picture, the mean of the finished PNGs less than half of it. So a run can be
# asked to hand back its final latent, and a later request decodes the mean of
# many. The three helpers below are what both sides share, so that the
# arithmetic exists once.

# The VAE decode peak for SD3.5 at 1024x1024: the ~5 GB the tiling decision in
# _tile_vae_if_needed is built on, the amount that does not fit beside the safety
# chain on a 24 GB card. A generation reserves it inside its model's peak; a
# stand-alone decode has no load path that would, so _vae_for asks for it there.
VAE_DECODE_PEAK_MB = 5_000


def latent_to_npy_bytes(array) -> bytes:
    """The wire form of a latent: a .npy file, float16, without the batch axis.

    float16 is the compact form that every VAE dtype this backend loads (float16
    by config default, bfloat16 where a model asks for it) casts to without
    losing anything over the range a latent occupies -- and it halves what
    travels as base64 through two services and back.

    A latent that is not finite AFTER that cast is refused rather than written:
    one diverged run would otherwise poison the mean of twenty (the caller in
    generate_image catches this and keeps no latent for that run).
    """
    import io
    import numpy as np

    arr = np.asarray(array)
    if arr.ndim == 4 and arr.shape[0] == 1:
        arr = arr[0]          # one picture per run; the batch axis says nothing
    with np.errstate(over="ignore", invalid="ignore"):
        # The overflow this cast can raise is the very thing the next lines
        # report, with the shape and the counts numpy's own warning leaves out.
        written = arr.astype(np.float16)
    if not np.isfinite(written).all():
        raise ValueError(
            f"latent is not finite: {int(np.isnan(written).sum())} NaN, "
            f"{int(np.isinf(written).sum())} Inf in {list(written.shape)}")
    buffer = io.BytesIO()
    np.save(buffer, written, allow_pickle=False)
    return buffer.getvalue()


def npy_bytes_to_array(data: bytes):
    """Read back what latent_to_npy_bytes wrote.

    allow_pickle stays off: this parses a body that arrived over HTTP, and a
    pickled .npy is code, not numbers.
    """
    import io
    import numpy as np

    return np.load(io.BytesIO(data), allow_pickle=False)


def decode_latent_tensor(vae, image_processor, latents):
    """Turn a raw pipeline latent into its picture, as SD3's own __call__ does.

    `latents / scaling_factor + shift_factor`, then the VAE, then the processor
    (diffusers 0.36, pipeline_stable_diffusion_3.py, the else-branch of
    `output_type == "latent"`). The shift is the part that is easy to lose: the
    live preview in generate_image drops it on purpose -- a 256px thumbnail
    nobody keeps -- and copying THAT arithmetic here would make a kept latent
    decode to a different picture than the run it came from returned.
    """
    import torch

    if latents.ndim == 3:
        latents = latents.unsqueeze(0)
    scaling = float(vae.config.scaling_factor)
    shift = float(getattr(vae.config, "shift_factor", None) or 0.0)
    with torch.no_grad():
        scaled = (latents / scaling) + shift
        image = vae.decode(scaled, return_dict=False)[0]
        return image_processor.postprocess(image, output_type="pil")[0]


# A settable law over the T5 tail stood here on 2026-09-10, in two forms --
# 0.15 * alpha and (alpha / anchor) ** F -- and both are gone the same day.
# The anchor was DERIVED FROM the 0.15 it was meant to replace (0.15 * alpha
# crosses 1 at alpha 6.67, and 7 reproduces that to five percent), so the
# smoother function carried the arbitrariness of the constant it replaced.
# Variables no hypothesis can be formed about have no business here. The gate
# for a tail law is a PREDICTED effect, grounded and then empirically redeemed,
# and an aesthetic or didactic gain that pays for the apparatus -- some
# measurable difference is not enough.
#
# The tail runs at its own length, which is the only form with no free
# parameter in it. dual_alpha keeps the 0.15 it has carried since 7565a6a7:
# that factor IS what distinguishes that strategy, and runs are recorded under
# it.


def slerp_tokens(a, b, alpha):
    """Interpolate two token tensors on the sphere: the direction turns, the length runs linearly.

    At a given alpha the direction is the one reached by turning alpha * theta
    away from `a` in the plane the two directions span, and it carries a length
    that runs linearly from the length of `a` to the length of `b`. At alpha 0
    the result is `a`, at alpha 1 it is `b`.

    On the sphere the direction has length 1 at every alpha, the ones past the
    anchors included, because sin((1-alpha)*theta)*u_a + sin(alpha*theta)*u_b
    over sin(theta) equals cos(alpha*theta)*u_a + sin(alpha*theta)*n with n the
    unit vector perpendicular to u_a in that plane. Out there it keeps turning at
    alpha * theta and comes round again: at alpha 20 with two roughly
    perpendicular readings the walk is some 31 radians, five turns of the great
    circle. The length term crosses zero at alpha = |a| / (|a| - |b|), which lies
    past alpha 1 where `a` is the longer of the two readings and below alpha 0
    where `b` is; past that crossing the direction is the opposite one.

    The procedure comes from the ComfyUI node ai4artsed_conditioning_fusion
    (`_spherical_interpolation`), the first place two conditionings were mixed
    here, with one step dropped. That node takes theta as acos(|dot|) and sums
    the unmodified u_b, so where the dot product is negative it weighs the arc to
    -u_b and adds u_b: the result then lies at half the angle between the two
    readings and has length tan(theta/2). Nothing keeps that dot product positive
    for CLIP against T5, two encoders trained apart from each other, so the
    arithmetic and the formula on the instrument would agree at some core
    positions and part company at the rest. Here theta is acos(dot), the angle
    the two readings actually stand at; both anchors stay exact and the printed
    formula holds at every position.

    Where the two directions coincide or oppose each other the plane is
    undefined, and the straight line between the two unit vectors is taken
    instead (below sin theta = 1e-6). Both anchors survive that branch; the
    length-1 identity above belongs to the sphere and holds inside it alone. For
    CLIP against T5 the branch is unreachable in practice -- it asks for |dot|
    within some 5e-13 of 1, and the two encoders come out around 0.04 -- so it is
    a floor under the arithmetic rather than a case the instrument shows.

    The pooled vector stays out of this, as it does under every strategy in this
    file: T5 has no pooled counterpart in SD3.5. The node does slerp its pooled
    half, and its alpha widget stops at 5 either way, so what is taken from there
    is the procedure; a run here has no counterpart run there to be held against.

    Direction and length are computed in float32 and cast back, as the push
    strategies do: at alpha 35 the argument of the sine reaches some 50 radians,
    where fp16 resolves an angle to about 0.03 and its sine to two decimals.
    (ComfyUI hands its nodes fp32 conditioning and keeps it, so the node had no
    cast at all. The cast back is what the whole conditioning path here is made
    of, and it carries a ceiling: the longest core token of an SD3.5 run measures
    around 1200, so beyond about alpha 55 a concentrated direction reaches fp16's
    65504 and the token comes back as inf. Legacy meets the same ceiling at the
    same token; slerp reaches it intermittently rather than monotonically,
    because sin(alpha*theta) oscillates.)
    """
    import torch

    a32 = a.float()
    b32 = b.float()
    a_dir = torch.nn.functional.normalize(a32, dim=-1)
    b_dir = torch.nn.functional.normalize(b32, dim=-1)
    dot = torch.clamp((a_dir * b_dir).sum(dim=-1, keepdim=True), -1.0, 1.0)
    theta = torch.acos(dot)
    sin_theta = torch.sin(theta)
    turned = torch.where(
        sin_theta < 1e-6,
        (1.0 - alpha) * a_dir + alpha * b_dir,
        (torch.sin((1.0 - alpha) * theta) * a_dir + torch.sin(alpha * theta) * b_dir)
        / sin_theta.clamp(min=1e-6),
    )
    length = ((1.0 - alpha) * a32.norm(dim=-1, keepdim=True)
              + alpha * b32.norm(dim=-1, keepdim=True))
    return (turned * length).to(a.dtype)


class DiffusersImageGenerator:
    """
    Direct image generation using HuggingFace Diffusers

    Supports:
    - SD3.5 Large/Medium (StableDiffusion3Pipeline)
    - Flux (FluxPipeline)
    - Optional TensorRT acceleration
    - Live preview via step callbacks
    """

    def __init__(self):
        """Initialize Diffusers backend"""
        from config import (
            DIFFUSERS_CACHE_DIR,
            DIFFUSERS_USE_TENSORRT,
            DIFFUSERS_TORCH_DTYPE,
            DIFFUSERS_DEVICE,
            DIFFUSERS_ENABLE_ATTENTION_SLICING,
            DIFFUSERS_ENABLE_VAE_TILING
        )

        self.cache_dir = DIFFUSERS_CACHE_DIR
        self.use_tensorrt = DIFFUSERS_USE_TENSORRT
        self.torch_dtype_str = DIFFUSERS_TORCH_DTYPE
        self.device = DIFFUSERS_DEVICE
        self.enable_attention_slicing = DIFFUSERS_ENABLE_ATTENTION_SLICING
        self.enable_vae_tiling = DIFFUSERS_ENABLE_VAE_TILING

        # Multi-model GPU cache with LRU eviction
        self._pipelines: Dict[str, Any] = {}
        self._current_model: Optional[str] = None
        self._model_last_used: Dict[str, float] = {}  # timestamp for LRU
        self._model_vram_mb: Dict[str, float] = {}    # measured per-model VRAM
        self._model_in_use: Dict[str, int] = {}       # refcount (eviction guard)
        # Decoding a kept latent needs the VAE and nothing else. Pulling the
        # whole 30 GB pipeline back onto the card for that would be the most
        # expensive way to run 84M parameters, so a decode may load the VAE
        # alone and keep it here. Unregistered with the coordinator, and bounded
        # instead: an entry appears only for a model that was decoded while its
        # pipeline was NOT resident, and it is dropped again the moment that
        # pipeline loads or is unloaded. The weights are small (84M parameters
        # at _get_torch_dtype(), so ~170 MB at the float16 default); the cost
        # that is worth reserving is the decode peak, and _vae_for asks the
        # coordinator for VAE_DECODE_PEAK_MB before it puts one on the card.
        self._vaes: Dict[str, Any] = {}
        self._load_lock = threading.Lock()             # serialize load/evict
        # Re-entrant, and it has to be: the tokenizers are the shared resource,
        # not the forward pass, and the helpers that touch them (_tokenize_prompt,
        # the token-window helper in probing) are called from both sides — from a
        # request that already holds this lock for its whole generation, and from
        # a describing surface that holds nothing. A plain Lock would make the
        # first of those deadlock against itself, so every caller would have to
        # know which side it is on. Re-entrancy is per thread, and fn() in
        # _locked_generate runs in the thread that took the lock.
        self._inference_lock = threading.RLock()   # every tokenizer call, and every forward pass

        # Register with VRAM coordinator for cross-backend eviction
        self._register_with_coordinator()

        logger.info(f"[DIFFUSERS] Initialized: cache={self.cache_dir}, tensorrt={self.use_tensorrt}, device={self.device}")

    def _register_with_coordinator(self):
        """Register with VRAM coordinator for cross-backend eviction."""
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[DIFFUSERS] Registered with VRAM coordinator")
        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.warning(f"[DIFFUSERS] Failed to register with VRAM coordinator: {e}")

    def _locked_generate(self, fn, model_id=None):
        """Run a generation function under the inference lock.

        HuggingFace Rust tokenizers raise 'Already borrowed' when called
        concurrently from multiple threads. Since GPU inference is serial
        anyway, we serialize at the tokenize+generate boundary.

        THIS LOCK IS NOT ONLY FOR GENERATION. A tokenizer call anywhere in this
        backend — a describing surface counting tokens, a helper measuring how
        much of the window a prompt fills — has to take it too. Measured twice
        (journal 2026-09-01 09:18 and 2026-09-02 17:14): a running generation
        was killed by "Already borrowed" raised inside tokenizer_3, in the same
        second as an unlocked encode call from another request. The generation
        pays for the describing call, which is the wrong way round.

        Outside that sits the plant-wide slot: it keeps this forward pass from
        allocating while heartmula, an audio model or the ComfyUI process is
        allocating. Slot first, then the inference lock — that order holds
        everywhere, so the two can never be taken against each other.
        """
        from services.gpu_admission import (get_gpu_admission, CURRENT_RUN_LABEL,
                                            CURRENT_WORKLOAD, CURRENT_MODEL)
        from services.vram_coordinator import EvictionPriority
        # What THIS request asked for, not what happened to be loaded last:
        # several pipelines live here at once, and _current_model is a single
        # marker that another request can move between this run's load and its
        # forward pass. The marker stays as the fallback for callers that
        # arrive without one.
        model_id = model_id or CURRENT_MODEL.get("") or self._current_model or "diffusers"
        with get_gpu_admission().slot("diffusers", model_id, 0, EvictionPriority.NORMAL,
                                      label=CURRENT_RUN_LABEL.get(""),
                                      workload=CURRENT_WORKLOAD.get("")):
            with self._inference_lock:
                return fn()

    # =========================================================================
    # VRAMBackend Protocol Implementation
    # =========================================================================

    def get_backend_id(self) -> str:
        """Unique identifier for this backend."""
        return "diffusers"

    def get_registered_models(self) -> list:
        """Return list of models with VRAM info for coordinator."""
        from services.vram_coordinator import EvictionPriority

        return [
            {
                "model_id": mid,
                "vram_mb": self._model_vram_mb.get(mid, 0),
                "priority": EvictionPriority.NORMAL,
                "last_used": self._model_last_used.get(mid, 0),
                "in_use": self._model_in_use.get(mid, 0),
            }
            for mid in self._pipelines
        ]

    def evict_model(self, model_id: str) -> bool:
        """Evict a specific model (called by coordinator)."""
        return self._unload_model_sync(model_id)

    def _unload_model_sync(self, model_id: str) -> bool:
        """Synchronously unload a model from memory."""
        import torch

        if model_id not in self._pipelines:
            return False

        # A model loaded seconds ago belongs to a generation that has not yet
        # raised its refcount — it loads, then claims. Evicting inside that gap
        # leaves the generation reaching for a pipeline that is gone.
        # Ten seconds covers the load-then-claim gap; longer would start
        # protecting models that are simply idle, and eviction is what keeps the
        # card from filling up.
        loaded_ago = time.time() - self._model_last_used.get(model_id, 0)
        if loaded_ago < 10:
            logger.info(f"[DIFFUSERS] Not unloading {model_id} — it was taken into use "
                        f"{loaded_ago:.0f}s ago")
            return False

        # The coordinator reads the refcount when it picks a victim; between that
        # and here a generation can have claimed the model. Re-read it, or the
        # running generation finds its pipeline gone mid-flight.
        if self._model_in_use.get(model_id, 0) > 0:
            logger.info(f"[DIFFUSERS] Not unloading {model_id} — "
                        f"{self._model_in_use[model_id]} generation(s) using it")
            return False

        try:
            del self._pipelines[model_id]
            self._model_last_used.pop(model_id, None)
            self._model_vram_mb.pop(model_id, None)
            self._model_in_use.pop(model_id, None)
            self._vaes.pop(model_id, None)   # freed by the collect/empty_cache below

            if self._current_model == model_id:
                self._current_model = None

            if torch.cuda.is_available():
                gc.collect()
                torch.cuda.empty_cache()

            logger.info(f"[DIFFUSERS] Unloaded model: {model_id}")
            return True
        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS] Error unloading {model_id}: {e}")
            return False

    def _get_torch_dtype(self):
        """Get torch dtype from config string"""
        import torch
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        return dtype_map.get(self.torch_dtype_str, torch.float16)

    def _get_vram_estimate_key(self, model_id: str, pipeline_class: str) -> str:
        """Map (model_id, pipeline_class, quantization) to a MODEL_PEAK_VRAM_MB key."""
        from config import DIFFUSERS_FLUX2_QUANTIZE, DIFFUSERS_WAN22_QUANTIZE

        if pipeline_class == "Flux2Pipeline":
            return f"flux2_{DIFFUSERS_FLUX2_QUANTIZE.lower()}"
        elif pipeline_class in ("WanPipeline", "WanImageToVideoPipeline"):
            quant = DIFFUSERS_WAN22_QUANTIZE.lower()
            kind = "i2v" if pipeline_class == "WanImageToVideoPipeline" else "t2v"
            moe = "_moe" if "A14B" in model_id else ""
            return f"wan22_{kind}{moe}_{quant}"
        elif "stable-diffusion-3.5" in model_id:
            # Normalize dtype name to match MODEL_PEAK_VRAM_MB keys (fp16, bf16)
            _dtype_short = {"float16": "fp16", "bfloat16": "bf16", "float32": "fp32"}
            short = _dtype_short.get(self.torch_dtype_str, self.torch_dtype_str)
            size = "medium" if "medium" in model_id else "large"
            return f"sd35_{size}_{short}"
        elif pipeline_class == "StableDiffusionXLPipeline":
            _dtype_short = {"float16": "fp16", "bfloat16": "bf16", "float32": "fp32"}
            short = _dtype_short.get(self.torch_dtype_str, self.torch_dtype_str)
            # Two models load under this class now, and the sdxl_* figure is
            # Denoising Archaeology's worst case -- a float32 VAE decode at every
            # captured step. A plain generation never pays that, and charging it
            # the same number evicts models it does not displace and forces CPU
            # offload on a card the weights fit into three times over.
            if "commoncanvas" in model_id.lower():
                return f"commoncanvas_{short}"
            return f"sdxl_{short}"
        else:
            return f"unknown_{pipeline_class}"

    def _get_peak_vram_mb(self, model_id: str, pipeline_class: str) -> float:
        """Get estimated peak VRAM (MB) from config table. Falls back to 20GB."""
        from config import MODEL_PEAK_VRAM_MB

        key = self._get_vram_estimate_key(model_id, pipeline_class)
        estimate = MODEL_PEAK_VRAM_MB.get(key)
        if estimate is None:
            logger.warning(f"[DIFFUSERS] No VRAM estimate for key '{key}', using 20GB default")
            return 20_000
        return float(estimate)

    def _pipeline_class_for(self, model_id: str, requested: str) -> str:
        """A model and the class it loads under are one fact.

        Callers that do not know the pairing send only an id -- the warm-ahead
        loop does (devserver/my_app/services/gpu_warm_ahead.py) -- and then the
        route default applies, which is SD3. That would load an SDXL repository
        as an MMDiT and fail every poll for as long as the run is queued.
        """
        # The repositories that carry this architecture do not agree on how to
        # spell it: SDXL itself says "stable-diffusion-xl", CommonCanvas says
        # "CommonCanvas-XL". Both load under the same class, and a miss here
        # costs the whole warm-ahead, not just its spelling.
        lowered = model_id.lower()
        if "stable-diffusion-xl" in lowered or "commoncanvas-xl" in lowered:
            return "StableDiffusionXLPipeline"
        return requested

    def _resolve_pipeline_class(self, pipeline_class: str):
        """Resolve pipeline class string to actual class."""
        if pipeline_class == "StableDiffusion3Pipeline":
            from diffusers import StableDiffusion3Pipeline
            return StableDiffusion3Pipeline
        elif pipeline_class == "FluxPipeline":
            from diffusers import FluxPipeline
            return FluxPipeline
        elif pipeline_class == "Flux2Pipeline":
            from diffusers import Flux2Pipeline
            return Flux2Pipeline
        elif pipeline_class == "WanPipeline":
            from diffusers import WanPipeline
            return WanPipeline
        elif pipeline_class == "WanImageToVideoPipeline":
            from diffusers import WanImageToVideoPipeline
            return WanImageToVideoPipeline
        elif pipeline_class == "StableDiffusionXLPipeline":
            from diffusers import StableDiffusionXLPipeline
            return StableDiffusionXLPipeline
        else:
            raise ValueError(f"Unknown pipeline class: {pipeline_class}")

    def _load_flux2_pipeline(self, model_id: str, kwargs: dict):
        """Load Flux2 pipeline component-by-component with explicit bf16.

        Flux2Pipeline.from_pretrained ignores torch_dtype/dtype kwargs,
        loading everything in float32 (~106GB RAM). Loading components
        individually with torch_dtype=bfloat16 uses ~1.2GB RAM instead.

        FP8 mode (DIFFUSERS_FLUX2_QUANTIZE=fp8): quantizes transformer to
        Float8WeightOnlyConfig via TorchAoConfig (~16GB) and text encoder to
        Int8WeightOnlyConfig v2 (~12GB). Peak VRAM ~24GB with CPU offload.
        """
        import torch
        from diffusers import (
            Flux2Pipeline, Flux2Transformer2DModel,
            AutoencoderKLFlux2, FlowMatchEulerDiscreteScheduler,
        )
        from transformers import AutoModelForImageTextToText, PixtralProcessor
        from config import DIFFUSERS_FLUX2_QUANTIZE

        dtype = torch.bfloat16
        cache_kwargs = {"cache_dir": str(self.cache_dir)} if self.cache_dir else {}
        quantize = DIFFUSERS_FLUX2_QUANTIZE.lower()

        if quantize == "fp8":
            from diffusers import TorchAoConfig
            from transformers import TorchAoConfig as TransformersAoConfig
            from torchao.quantization import Float8WeightOnlyConfig, Int8WeightOnlyConfig
            diff_quant = TorchAoConfig(Float8WeightOnlyConfig())
            tf_quant = TransformersAoConfig(Int8WeightOnlyConfig(version=2))
            logger.info(f"[DIFFUSERS] Flux2: loading transformer FP8 + text encoder INT8...")
            transformer = Flux2Transformer2DModel.from_pretrained(
                model_id, subfolder="transformer",
                quantization_config=diff_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
            text_encoder = AutoModelForImageTextToText.from_pretrained(
                model_id, subfolder="text_encoder",
                quantization_config=tf_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
        else:
            logger.info(f"[DIFFUSERS] Flux2: loading components in bf16...")
            transformer = Flux2Transformer2DModel.from_pretrained(
                model_id, subfolder="transformer",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )
            text_encoder = AutoModelForImageTextToText.from_pretrained(
                model_id, subfolder="text_encoder",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )
        vae = AutoencoderKLFlux2.from_pretrained(
            model_id, subfolder="vae",
            torch_dtype=dtype, **cache_kwargs
        )
        tokenizer = PixtralProcessor.from_pretrained(
            model_id, subfolder="tokenizer", **cache_kwargs
        )
        scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
            model_id, subfolder="scheduler", **cache_kwargs
        )

        pipe = Flux2Pipeline(
            transformer=transformer,
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            vae=vae,
            scheduler=scheduler,
        )
        pipe.enable_model_cpu_offload()

        logger.info(f"[DIFFUSERS] Flux2: pipeline loaded ({quantize}) with cpu_offload")
        return pipe

    def _load_wan_pipeline(self, model_id: str, kwargs: dict, pipeline_class_str: str = "WanPipeline"):
        """Load Wan 2.2 pipeline component-by-component with quantization support.

        Handles both T2V (WanPipeline) and I2V (WanImageToVideoPipeline).
        MoE models (A14B) have dual transformers (transformer + transformer_2).

        FP8 mode (DIFFUSERS_WAN22_QUANTIZE=fp8): quantizes transformers to
        Float8WeightOnlyConfig via TorchAoConfig (~14GB total) and text encoder to
        Int8WeightOnlyConfig v2. Peak VRAM ~14GB with CPU offload.
        """
        import torch
        from diffusers import AutoencoderKLWan
        from config import DIFFUSERS_WAN22_QUANTIZE

        PipelineClass = self._resolve_pipeline_class(pipeline_class_str)
        dtype = torch.bfloat16
        cache_kwargs = {"cache_dir": str(self.cache_dir)} if self.cache_dir else {}
        quantize = DIFFUSERS_WAN22_QUANTIZE.lower()

        # Check if model has dual transformers (MoE A14B models)
        import json
        from pathlib import Path
        from huggingface_hub import cached_assets_path
        has_dual_transformer = False
        model_index = {}
        try:
            # Try loading model_index.json to detect dual transformer
            from huggingface_hub import hf_hub_download
            model_index_path = hf_hub_download(model_id, "model_index.json", **cache_kwargs)
            with open(model_index_path) as f:
                model_index = json.load(f)
            has_dual_transformer = "transformer_2" in model_index
        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.warning(f"[DIFFUSERS] Could not check model_index.json for dual transformer: {e}")
            # Heuristic: A14B models have dual transformers
            has_dual_transformer = "A14B" in model_id

        if quantize == "fp8":
            from diffusers import TorchAoConfig, WanTransformer3DModel
            from transformers import TorchAoConfig as TransformersAoConfig, UMT5EncoderModel
            from torchao.quantization import Float8WeightOnlyConfig, Int8WeightOnlyConfig
            diff_quant = TorchAoConfig(Float8WeightOnlyConfig())
            tf_quant = TransformersAoConfig(Int8WeightOnlyConfig(version=2))

            logger.info(f"[DIFFUSERS] Wan: loading transformer(s) FP8 + text encoder INT8...")
            transformer = WanTransformer3DModel.from_pretrained(
                model_id, subfolder="transformer",
                quantization_config=diff_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
            transformer_2 = None
            if has_dual_transformer:
                transformer_2 = WanTransformer3DModel.from_pretrained(
                    model_id, subfolder="transformer_2",
                    quantization_config=diff_quant,
                    low_cpu_mem_usage=True, **cache_kwargs
                )
            text_encoder = UMT5EncoderModel.from_pretrained(
                model_id, subfolder="text_encoder",
                quantization_config=tf_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
        else:
            from diffusers import WanTransformer3DModel
            from transformers import UMT5EncoderModel

            logger.info(f"[DIFFUSERS] Wan: loading components in bf16...")
            transformer = WanTransformer3DModel.from_pretrained(
                model_id, subfolder="transformer",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )
            transformer_2 = None
            if has_dual_transformer:
                transformer_2 = WanTransformer3DModel.from_pretrained(
                    model_id, subfolder="transformer_2",
                    torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
                )
            text_encoder = UMT5EncoderModel.from_pretrained(
                model_id, subfolder="text_encoder",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )

        # VAE MUST be float32
        vae = AutoencoderKLWan.from_pretrained(
            model_id, subfolder="vae",
            torch_dtype=torch.float32, **cache_kwargs
        )

        # Tokenizer + Scheduler
        from transformers import AutoTokenizer
        from diffusers import UniPCMultistepScheduler
        tokenizer = AutoTokenizer.from_pretrained(model_id, subfolder="tokenizer", **cache_kwargs)
        scheduler = UniPCMultistepScheduler.from_pretrained(model_id, subfolder="scheduler", **cache_kwargs)

        # Assemble pipeline
        pipe_kwargs = {
            "transformer": transformer,
            "vae": vae,
            "text_encoder": text_encoder,
            "tokenizer": tokenizer,
            "scheduler": scheduler,
        }
        if transformer_2 is not None:
            pipe_kwargs["transformer_2"] = transformer_2
            pipe_kwargs["boundary_ratio"] = model_index.get("boundary_ratio", 0.9)

        pipe = PipelineClass(**pipe_kwargs)
        pipe.enable_model_cpu_offload()

        dual_info = " (dual MoE)" if has_dual_transformer else ""
        logger.info(f"[DIFFUSERS] Wan: pipeline loaded ({quantize}{dual_info}) with cpu_offload")
        return pipe

    def _ensure_vram_available(self, required_mb: float = 0) -> None:
        """Request VRAM via coordinator, triggering cross-backend eviction if needed.

        The coordinator handles eviction across all backends (diffusers, text, heartmula).

        Args:
            required_mb: Minimum free VRAM needed. If 0, uses DIFFUSERS_VRAM_RESERVE_MB.
                         For cold loads (unknown model size), pass float('inf') to request
                         maximum available space.
        """
        from config import DIFFUSERS_VRAM_RESERVE_MB

        target_mb = required_mb if required_mb > 0 else DIFFUSERS_VRAM_RESERVE_MB

        # Use coordinator for cross-backend eviction
        try:
            from services.vram_coordinator import get_vram_coordinator, EvictionPriority
            coordinator = get_vram_coordinator()
            success = coordinator.request_vram("diffusers", target_mb, EvictionPriority.NORMAL)
            if not success:
                target_str = "max available" if target_mb == float('inf') else f"{target_mb:.0f}MB"
                logger.warning(f"[DIFFUSERS] VRAM eviction incomplete (requested {target_str})")
        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.warning(f"[DIFFUSERS] VRAM coordinator request failed: {e}")
            # Fallback to local-only eviction
            self._ensure_vram_available_local(target_mb)

    def _ensure_vram_available_local(self, target_mb: float) -> None:
        """Fallback: evict only own models (no cross-backend)."""
        import torch

        while True:
            if not torch.cuda.is_available():
                break

            free_mb = (torch.cuda.get_device_properties(0).total_memory
                       - torch.cuda.memory_allocated(0)) / (1024 * 1024)
            if free_mb >= target_mb:
                break

            candidates = [
                (mid, self._model_last_used.get(mid, 0))
                for mid in self._pipelines
                if self._model_in_use.get(mid, 0) <= 0
            ]

            if not candidates:
                if target_mb != float('inf'):
                    logger.warning(
                        f"[DIFFUSERS] Cannot free VRAM: {free_mb:.0f}MB free, "
                        f"need {target_mb:.0f}MB, no evictable models"
                    )
                break

            evict_id = min(candidates, key=lambda x: x[1])[0]
            self._unload_model_sync(evict_id)

    def _tile_vae_if_needed(self, holder, model_id: str) -> None:
        """Turn VAE tiling on where the card needs it -- pipeline or bare VAE.

        VAE tiling: explicit env-var, OR auto-enable for SD3.5 on tight-VRAM
        cards. Latent Lab co-resides Diffusers (~17 GB) with Llama-Guard +
        Stage-2 LLM + Qwen-VL (~6 GB total) -- on 24 GB GPUs the VAE decode peak
        (~5 GB) doesn't fit. 5090 (32 GB) and larger cards have enough headroom.

        Lifted out of _load_model_sync so that a VAE loaded ALONE for a decode
        gets the same treatment as the one inside a pipeline. Two copies of this
        decision would drift, and the one that drifted would be the decode --
        peaking where the generation that produced the latent did not, on
        exactly the cards that made tiling necessary.
        """
        import torch

        should_tile = self.enable_vae_tiling
        if not should_tile and "stable-diffusion-3.5" in model_id and torch.cuda.is_available():
            total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            if total_gb < 28:
                should_tile = True
                logger.info(f"[DIFFUSERS] Auto-enabling VAE tiling for SD3.5 on {total_gb:.1f} GB GPU (< 28 GB threshold)")
        if not should_tile:
            return

        # SD3/Flux/Wan pipelines don't expose enable_vae_tiling()
        # on the pipeline itself — call it on the VAE submodule.
        vae = None
        if hasattr(holder, "enable_vae_tiling"):
            holder.enable_vae_tiling()
            vae = getattr(holder, "vae", None)
        elif hasattr(holder, "vae") and hasattr(holder.vae, "enable_tiling"):
            holder.vae.enable_tiling()
            vae = holder.vae
        elif hasattr(holder, "enable_tiling"):
            holder.enable_tiling()          # a bare autoencoder, loaded for a decode
            vae = holder
        else:
            logger.warning(f"[DIFFUSERS] VAE tiling requested but {type(holder).__name__} exposes neither method — skipping")

        # SD3.5 VAE config has tile_latent_min_size=128 which equals
        # the latent size at 1024² output, so the strict-greater-than
        # threshold in AutoencoderKL._decode never triggers tiling.
        # Lower it so 1024² goes through 4 tiles (64×64 latent each).
        if vae is not None and getattr(vae, "tile_latent_min_size", 0) >= 128:
            vae.tile_latent_min_size = 64
            vae.tile_sample_min_size = 512
            logger.info(f"[DIFFUSERS] VAE tile thresholds lowered: latent_min=64, sample_min=512")

    def _load_model_sync(self, model_id: str, pipeline_class: str = "StableDiffusion3Pipeline",
                         prefetch: bool = False) -> bool:
        """
        Synchronous model loading with GPU cache + LRU eviction.
        Thread-safe via _load_lock.

        Runs inside the plant-wide slot as well: loading is where the big
        allocation happens — 30 GB for SD3.5-Large — and on 2026-08-17 that is
        exactly what ran the card dry, with four other loads in the same second.
        Serialising only the forward pass would have left that untouched.

        Returns True if model is ready on GPU.
        """
        from services.gpu_admission import get_gpu_admission
        from services.vram_coordinator import EvictionPriority

        # An already-resident model allocates nothing, so it does not queue: the
        # forward pass takes the slot right after, and making a single generation
        # wait twice for the same card helps nobody. Checked UNDER the load lock —
        # eviction runs without it, so a check outside would let a 30 GB cold load
        # slip past the gate whenever a model was dropped in that instant.
        with self._load_lock:
            if model_id in self._pipelines:
                self._model_last_used[model_id] = time.time()
                self._current_model = model_id
                return True

        # A prefetch loads BESIDE a running operation on purpose — that is the
        # whole point of warming ahead — so it does not take the slot. It is
        # allowed only when the gate itself has just said there is measured
        # room for it; the route checks that with the gate, not with the
        # caller. Everything else loads inside the slot, as before.
        import contextlib as _ctx
        from services.gpu_admission import CURRENT_RUN_LABEL
        # No workload here on purpose: a load is measured against the MODEL —
        # how long weights take off disk does not depend on what is asked of
        # them afterwards. See Lease.stats_key.
        _gate_cm = (_ctx.nullcontext() if prefetch
                    else get_gpu_admission().slot("diffusers-load", model_id, 0,
                                                  EvictionPriority.NORMAL,
                                                  label=CURRENT_RUN_LABEL.get("")))
        with _gate_cm as _gate_lease, self._load_lock:
            try:
                pipe = None  # bound early so the except-block can release a partial load
                import torch

                # Case 1: Already on GPU → reuse
                if model_id in self._pipelines:
                    self._model_last_used[model_id] = time.time()
                    self._current_model = model_id
                    return True

                # Case 2: Not loaded → evict if needed, load from disk
                pipeline_class = self._pipeline_class_for(model_id, pipeline_class)
                peak_vram = self._get_peak_vram_mb(model_id, pipeline_class)

                # If the full-residency peak exceeds the physical card, load
                # with CPU offload (weights streamed on demand) instead of
                # pipe.to(device) — the same mechanism Flux2 already uses
                # (_load_flux2_pipeline). Models that fit are untouched.
                use_cpu_offload = False
                if torch.cuda.is_available():
                    total_mb = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
                    if peak_vram > total_mb:
                        use_cpu_offload = True
                        logger.info(
                            f"[DIFFUSERS] {model_id}: estimated peak {peak_vram:.0f}MB "
                            f"exceeds GPU capacity {total_mb:.0f}MB — loading with CPU offload"
                        )

                self._ensure_vram_available(required_mb=peak_vram)

                PipelineClass = self._resolve_pipeline_class(pipeline_class)

                logger.info(f"[DIFFUSERS] Loading model from disk: {model_id}")

                vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

                # All diffusers pipelines use torch_dtype in from_pretrained()
                dtype_key = "torch_dtype"
                kwargs = {
                    dtype_key: self._get_torch_dtype(),
                    "use_safetensors": True,
                    "low_cpu_mem_usage": True,
                }
                if self.cache_dir:
                    kwargs["cache_dir"] = str(self.cache_dir)

                # Wan pipelines: component-level loading with quantization support
                if pipeline_class in ("WanPipeline", "WanImageToVideoPipeline"):
                    pipe = self._load_wan_pipeline(model_id, kwargs, pipeline_class)
                # Flux2: from_pretrained ignores torch_dtype → loads float32 (~106GB RAM).
                # Load components individually with explicit bf16 to avoid float32 intermediate.
                elif pipeline_class == "Flux2Pipeline":
                    pipe = self._load_flux2_pipeline(model_id, kwargs)
                else:
                    pipe = PipelineClass.from_pretrained(model_id, **kwargs)
                    if use_cpu_offload:
                        # enable_model_cpu_offload() manages device placement
                        # itself — must NOT also call pipe.to(device).
                        pipe.enable_model_cpu_offload()
                    else:
                        pipe = pipe.to(self.device)

                if self.enable_attention_slicing:
                    pipe.enable_attention_slicing()

                self._tile_vae_if_needed(pipe, model_id)

                self._pipelines[model_id] = pipe
                self._current_model = model_id
                self._model_last_used[model_id] = time.time()
                # From here the pipeline's own VAE serves every decode of this
                # model; a copy loaded for an earlier one would be a second set
                # of weights on the card, answering to nobody.
                self._vaes.pop(model_id, None)

                # Use static peak estimate for coordinator (measurement is broken
                # for CPU-offloaded models — they report ~0 since weights are on CPU)
                self._model_vram_mb[model_id] = peak_vram

                # Log measured vs estimated for validation
                vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
                measured_mb = (vram_after - vram_before) / (1024 * 1024)
                logger.info(
                    f"[DIFFUSERS] Model loaded: {model_id} "
                    f"(estimated: {peak_vram:.0f}MB, measured: {measured_mb:.0f}MB)"
                )
                return True

            except Exception as e:
                logger.error(f"[DIFFUSERS] Failed to load model {model_id}: {e}")
                import traceback
                traceback.print_exc()
                # Release any partially-transferred GPU tensors. Without this a
                # failed pipe.to(device) leaves its weights resident and the
                # VRAM coordinator cannot reclaim them (the load was never
                # registered) — wedging the card for every later request.
                try:
                    if pipe is not None:
                        del pipe
                    self._pipelines.pop(model_id, None)
                    import gc
                    gc.collect()
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception as cleanup_err:
                    logger.warning(f"[DIFFUSERS] Cleanup after failed load incomplete: {cleanup_err}")
                # The failure travels as a return, which the slot never sees.
                # Unmarked, this load claimed residency for the pipeline the
                # lines above just deleted (the next run priced warm and
                # WITHOUT a load surcharge — an under-stated wait), filed its
                # partial allocation as the model footprint, armed the
                # post-load reservation for a phantom, and entered the load
                # bucket every config on this checkpoint reads.
                if _gate_lease is not None:
                    _gate_lease.failed = True
                return False

    async def is_available(self) -> bool:
        """
        Check if Diffusers backend is available

        Returns:
            True if torch and diffusers are installed and GPU is available
        """
        try:
            import torch
            from diffusers import StableDiffusion3Pipeline

            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("[DIFFUSERS] CUDA requested but not available")
                return False

            return True

        except ImportError as e:
            logger.error(f"[DIFFUSERS] Dependencies not installed: {e}")
            return False

    async def get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU memory information"""
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                total = props.total_memory / 1024**3

                return {
                    "gpu_name": props.name,
                    "total_vram_gb": round(total, 2),
                    "allocated_gb": round(allocated, 2),
                    "reserved_gb": round(reserved, 2),
                    "free_gb": round(total - reserved, 2)
                }
            return {"available": False}
        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS] Error getting GPU info: {e}")
            return {"error": str(e)}

    async def load_model(
        self,
        model_id: str,
        pipeline_class: str = "StableDiffusion3Pipeline",
        prefetch: bool = False,
    ) -> bool:
        """
        Load a model into GPU memory with LRU cache.

        - Already on GPU: updates last_used timestamp (instant)
        - Not loaded: evicts LRU models, loads from disk (~10s)

        Args:
            model_id: HuggingFace model ID or local path
            pipeline_class: Pipeline class to use

        Returns:
            True if loaded successfully
        """
        return await asyncio.to_thread(self._load_model_sync, model_id, pipeline_class, prefetch)

    async def unload_model(self, model_id: Optional[str] = None) -> bool:
        """
        Fully unload a model from memory (GPU + CPU RAM).

        Args:
            model_id: Model to unload (default: current model)

        Returns:
            True if unloaded successfully
        """
        model_id = model_id or self._current_model

        if model_id not in self._pipelines:
            logger.warning(f"[DIFFUSERS] Model not loaded: {model_id}")
            return False

        try:
            import torch

            del self._pipelines[model_id]
            self._model_last_used.pop(model_id, None)
            self._model_vram_mb.pop(model_id, None)
            self._model_in_use.pop(model_id, None)
            self._vaes.pop(model_id, None)   # freed by the empty_cache below

            if model_id == self._current_model:
                self._current_model = None

            # Force CUDA memory cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            logger.info(f"[DIFFUSERS] Unloaded model: {model_id}")
            return True

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS] Error unloading model: {e}")
            return False

    def _apply_loras(self, pipe, loras: list):
        """Load LoRA weights onto pipeline for current generation."""
        from config import LORA_DIR

        adapter_names = []
        adapter_weights = []
        for i, lora in enumerate(loras):
            lora_path = LORA_DIR / lora['name']
            if not lora_path.exists():
                logger.error(f"[DIFFUSERS-LORA] LoRA file not found: {lora_path}")
                continue
            adapter_name = f"lora_{i}"
            pipe.load_lora_weights(
                str(LORA_DIR), weight_name=lora['name'], adapter_name=adapter_name,
                prefix=None,  # Auto-detect Kohya key format (lora_unet_*, lora_te1_*)
            )
            adapter_names.append(adapter_name)
            adapter_weights.append(lora.get('strength', 1.0))
            logger.info(f"[DIFFUSERS-LORA] Loaded: {lora['name']} (strength={lora.get('strength', 1.0)})")

        if adapter_names:
            try:
                pipe.set_adapters(adapter_names, adapter_weights)
                logger.info(f"[DIFFUSERS-LORA] Active adapters: {adapter_names}")
            except ValueError as e:
                # Kohya SD3 LoRAs may fuse directly without PEFT adapter tracking
                logger.warning(f"[DIFFUSERS-LORA] set_adapters skipped (weights applied directly): {e}")

    def _remove_loras(self, pipe):
        """Unload all LoRA weights from pipeline."""
        try:
            pipe.unload_lora_weights()
            logger.info("[DIFFUSERS-LORA] Unloaded LoRA weights")
        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.warning(f"[DIFFUSERS-LORA] Error unloading LoRAs: {e}")

    async def generate_image(
        self,
        prompt: str,
        model_id: str = DEFAULT_MODEL_ID,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
        pipeline_class: str = "StableDiffusion3Pipeline",
        loras: Optional[list] = None,
        keep_latent: bool = False,
        latent_sink: Optional[dict] = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate an image using Diffusers

        Args:
            prompt: Positive prompt
            model_id: Model to use
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            steps: Number of steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            callback: Step callback for progress (step, total_steps, latents)
            pipeline_class: Pipeline class string (e.g. "Flux2Pipeline")
            loras: Optional list of LoRA dicts [{name, strength}]
            keep_latent: Also keep the final latent (SD3.5 text-to-image only)
            latent_sink: Dict the kept latent and its metadata are written into
            **kwargs: Additional pipeline arguments

        Returns:
            PNG image bytes, or None on failure
        """
        try:
            import torch
            import io

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id, pipeline_class):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                # CPU offload pipelines (Flux2) need generator on CPU
                gen_device = "cpu" if pipeline_class == "Flux2Pipeline" else self.device
                generator = torch.Generator(device=gen_device).manual_seed(seed)

                logger.info(f"[DIFFUSERS] Generating: steps={steps}, size={width}x{height}, seed={seed}")

                # Always wire progress callback for polling endpoint
                def step_callback(pipe_inst, step, timestep, callback_kwargs):
                    # Has this run been stopped? Then leave the loop now; the
                    # preview below would only decode latents for a picture
                    # nobody is waiting for any more.
                    if interrupt_if_cancelled(pipe_inst):
                        return callback_kwargs
                    _generation_progress["step"] = step + 1  # 0-indexed → 1-indexed
                    _generation_progress["total_steps"] = steps
                    # Decode latents to preview image every 5 steps
                    if step % 5 == 0 or step == steps - 1:
                        try:
                            latents = callback_kwargs.get("latents")
                            if latents is not None:
                                with torch.no_grad():
                                    preview = pipe_inst.vae.decode(
                                        latents / pipe_inst.vae.config.scaling_factor
                                    ).sample
                                from diffusers.image_processor import VaeImageProcessor
                                from PIL import Image
                                import base64
                                processor = VaeImageProcessor()
                                preview_img = processor.postprocess(preview, output_type="pil")[0]
                                preview_img = preview_img.resize((256, 256), Image.LANCZOS)
                                buf = io.BytesIO()
                                preview_img.save(buf, format="JPEG", quality=40)
                                _generation_progress["preview"] = base64.b64encode(buf.getvalue()).decode()
                        except Exception as e:
                            logger.debug(f"[DIFFUSERS] Preview decode failed (non-critical): {e}")
                    if callback:
                        try:
                            callback(step, steps, callback_kwargs.get("latents"))
                        except Exception as e:
                            logger.warning(f"[DIFFUSERS] Callback error: {e}")
                    return callback_kwargs

                # Only the SD3.5 text-to-image path can hand its latent back:
                # img2img runs a different pipeline object below, and Flux2 and
                # the video pipelines have a latent of another shape entirely.
                # Decided on the RESOLVED class, never on what the caller sent:
                # the route's default is SD3, so a CommonCanvas or SDXL id that
                # arrives under it would run with output_type="latent" and then
                # be decoded with SD3's tail -- a wrong picture, and no error to
                # say so. A caller that asks anyway gets its picture and no
                # latent; the flag is a wish, not a demand (see the route).
                resolved_class = self._pipeline_class_for(model_id, pipeline_class)
                wants_latent = (
                    keep_latent
                    and resolved_class == "StableDiffusion3Pipeline"
                    and not kwargs.get('image_bytes')
                )

                # Run inference in thread to avoid blocking event loop
                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True, "preview": None})
                    if loras:
                        self._apply_loras(pipe, loras)
                    try:
                        # Build generation kwargs
                        gen_kwargs = {
                            "prompt": prompt,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                        }

                        # Flux/Flux2 don't support negative_prompt
                        if pipeline_class not in ("FluxPipeline", "Flux2Pipeline"):
                            gen_kwargs["negative_prompt"] = negative_prompt if negative_prompt else None

                        # SD3.5 triple encoder: CLIP-L (77t), CLIP-G (77t), T5-XXL (512t)
                        if hasattr(pipe, 'tokenizer_3'):
                            gen_kwargs["max_sequence_length"] = 512
                            # Use explicit per-encoder prompts if provided via kwargs
                            if kwargs.get('prompt_2') or kwargs.get('prompt_3'):
                                if kwargs.get('prompt_2'):
                                    gen_kwargs["prompt_2"] = kwargs['prompt_2']
                                if kwargs.get('prompt_3'):
                                    gen_kwargs["prompt_3"] = kwargs['prompt_3']
                                logger.info(
                                    f"[DIFFUSERS] Triple-prompt: CLIP-L={len(prompt.split()):.0f}w, "
                                    f"CLIP-G={len((kwargs.get('prompt_2') or prompt).split()):.0f}w, "
                                    f"T5={len((kwargs.get('prompt_3') or prompt).split()):.0f}w"
                                )
                            # No pre-truncation here. The pipeline tokenizes CLIP with
                            # padding="max_length", max_length=77, truncation=True and
                            # falls back to prompt_3 = prompt on its own, so cutting the
                            # text beforehand changed nothing — it only swallowed the
                            # pipeline's own warning about what was dropped.

                        # Flux2 visual conditioning: pass reference image as context tokens
                        if pipeline_class == "Flux2Pipeline" and kwargs.get('image_bytes'):
                            from PIL import Image
                            pil_image = Image.open(io.BytesIO(kwargs['image_bytes'])).convert("RGB")
                            gen_kwargs["image"] = pil_image
                            logger.info(f"[DIFFUSERS] Flux2 visual conditioning: {pil_image.size}")

                        # SD3.5 img2img: create lightweight Img2Img pipeline via from_pipe()
                        if pipeline_class == "StableDiffusion3Pipeline" and kwargs.get('image_bytes'):
                            from PIL import Image
                            from diffusers import StableDiffusion3Img2ImgPipeline
                            pil_image = Image.open(io.BytesIO(kwargs['image_bytes'])).convert("RGB")
                            pil_image = pil_image.resize((width, height), Image.LANCZOS)
                            i2i_pipe = StableDiffusion3Img2ImgPipeline.from_pipe(pipe)
                            # VAE tiling: img2img encodes the input image via VAE,
                            # which at 1024x1024 with 16-ch latents causes massive
                            # VRAM spikes without tiling (65GB+ vs ~28GB with tiling)
                            i2i_pipe.vae.enable_tiling()
                            gen_kwargs["image"] = pil_image
                            gen_kwargs["strength"] = float(kwargs.get('strength', 0.65))
                            gen_kwargs.pop("width", None)
                            gen_kwargs.pop("height", None)
                            logger.info(
                                f"[DIFFUSERS] SD3.5 img2img: {pil_image.size}, "
                                f"strength={gen_kwargs['strength']}"
                            )
                            gen_kwargs["callback_on_step_end"] = step_callback
                            gen_kwargs["callback_on_step_end_tensor_inputs"] = ["latents"]
                            result = i2i_pipe(**gen_kwargs)
                            raise_if_cancelled()
                            return result.images[0]

                        gen_kwargs["callback_on_step_end"] = step_callback
                        gen_kwargs["callback_on_step_end_tensor_inputs"] = ["latents"]

                        if wants_latent:
                            # The pipeline stops before its own decoder and
                            # hands out the latent; the decode below is that
                            # same decoder, step for step, so the picture this
                            # run returns is the one it would have returned
                            # without the flag. The latent goes into the sink
                            # RAW -- before the scaling/shift step -- because
                            # that is the form the mean is taken in.
                            gen_kwargs["output_type"] = "latent"
                            result = pipe(**gen_kwargs)
                            raise_if_cancelled()
                            latents = result.images
                            if latent_sink is not None:
                                array = latents.detach().to(
                                    device="cpu", dtype=torch.float32).numpy()
                                if array.ndim == 4 and array.shape[0] == 1:
                                    array = array[0]
                                # Cast HERE, so that the shape and the dtype in
                                # the metadata are read off the array that is
                                # actually written and cannot describe another.
                                array = array.astype("float16")
                                try:
                                    latent_sink["latent"] = latent_to_npy_bytes(array)
                                except ValueError as e:
                                    # A diverged latent leaves the sink EMPTY and
                                    # the run keeps its picture. Averaged in, a
                                    # single one of these turns the mean of
                                    # twenty into a black square that answers
                                    # 200; without it the set is meaned pixel by
                                    # pixel, and says which mean it shows.
                                    latent_sink.clear()
                                    logger.warning(
                                        f"[DIFFUSERS] No latent kept for {model_id} "
                                        f"(seed {seed}): {e}")
                                else:
                                    latent_sink["meta"] = {
                                        "model_id": model_id,
                                        "pipeline_class": resolved_class,
                                        "scaling_factor": float(pipe.vae.config.scaling_factor),
                                        "shift_factor": float(
                                            getattr(pipe.vae.config, "shift_factor", None) or 0.0),
                                        "shape": [int(n) for n in array.shape],
                                        "dtype": str(array.dtype),
                                    }
                            return decode_latent_tensor(pipe.vae, pipe.image_processor, latents)

                        result = pipe(**gen_kwargs)
                        # An interrupted pipeline does not raise -- it returns
                        # the half-denoised latents as an image. Without this
                        # the stopped run would hand out that mush as a result.
                        raise_if_cancelled()
                        return result.images[0]
                    finally:
                        if loras:
                            self._remove_loras(pipe)
                        _generation_progress.update({"active": False, "preview": None})

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert to PNG bytes
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

                logger.info(f"[DIFFUSERS] Generated image: {len(image_bytes)} bytes")
                return image_bytes

            finally:
                self._model_in_use[model_id] -= 1

        except GpuBusy:
            raise          # busy is not a failed generation
        except GenerationCancelled:
            raise          # stopped on request is not a failed generation either
        except Exception as e:
            logger.error(f"[DIFFUSERS] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise GenerationFailed(str(e) or e.__class__.__name__) from e

    def _vae_for(self, model_id: str, pipeline_class: str):
        """The VAE to decode with, and the processor that goes with it.

        A resident pipeline brings its own -- same weights, same dtype, same
        tiling, and nothing is loaded twice. Otherwise the VAE is loaded ALONE
        and put through the same three steps a pipeline load performs on it:
        the cache and dtype of `_load_model_sync`, the VRAM reservation for the
        decode peak, and `_tile_vae_if_needed`. That is what a latent needs to
        decode to the same picture either way -- and until the tiling was
        included here, on a card that needs it, it did not.

        Runs under the inference lock (its callers are inside _locked_generate).
        """
        from diffusers.image_processor import VaeImageProcessor

        pipe = self._pipelines.get(model_id)
        vae = getattr(pipe, "vae", None) if pipe is not None else None
        if vae is not None and getattr(pipe, "image_processor", None) is not None:
            return vae, pipe.image_processor

        if vae is None:
            vae = self._vaes.get(model_id)
        if vae is None:
            if pipeline_class != "StableDiffusion3Pipeline":
                # Every family keeps its latents in its own autoencoder class.
                # Guessing one here would decode noise and call it a picture.
                raise ValueError(
                    f"no stand-alone VAE loader for pipeline class {pipeline_class!r}; "
                    f"load {model_id} first")
            from diffusers import AutoencoderKL
            kwargs = {
                "torch_dtype": self._get_torch_dtype(),
                "use_safetensors": True,
                "low_cpu_mem_usage": True,
            }
            if self.cache_dir:
                kwargs["cache_dir"] = str(self.cache_dir)
            logger.info(f"[DIFFUSERS] Loading VAE alone for decode: {model_id}")
            vae = AutoencoderKL.from_pretrained(model_id, subfolder="vae", **kwargs)
            # A decode has no load path of its own: _locked_generate takes the
            # plant-wide slot but reserves nothing, so the peak the decoder
            # itself needs is asked for here, with the figure the tiling
            # decision is built on.
            self._ensure_vram_available(required_mb=VAE_DECODE_PEAK_MB)
            vae = vae.to(self.device)
            self._tile_vae_if_needed(vae, model_id)
            self._vaes[model_id] = vae

        channels = getattr(vae.config, "block_out_channels", None) or [0] * 4
        return vae, VaeImageProcessor(vae_scale_factor=2 ** (len(channels) - 1))


    async def generate_video(
        self,
        prompt: str,
        model_id: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
        negative_prompt: str = "",
        width: int = 1280,
        height: int = 720,
        num_frames: int = 81,
        steps: int = 30,
        cfg_scale: float = 5.0,
        fps: int = 16,
        seed: int = -1,
        pipeline_class: str = "WanPipeline",
        guidance_scale_2: float = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate a video using Diffusers (WanPipeline).

        Args:
            prompt: Positive prompt
            model_id: Wan model to use
            negative_prompt: Negative prompt
            width: Video width
            height: Video height
            num_frames: Number of frames to generate
            steps: Number of inference steps
            cfg_scale: Guidance scale
            fps: Frames per second for output MP4
            seed: Random seed (-1 for random)
            pipeline_class: Pipeline class string
            guidance_scale_2: Second guidance scale for MoE models (A14B)

        Returns:
            MP4 video bytes, or None on failure
        """
        try:
            import torch

            if not await self.load_model(model_id, pipeline_class):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(
                    f"[DIFFUSERS] Generating video: steps={steps}, "
                    f"size={width}x{height}, frames={num_frames}, seed={seed}"
                )

                def video_step_callback(pipe_inst, step, timestep, callback_kwargs):
                    if interrupt_if_cancelled(pipe_inst):
                        return callback_kwargs
                    _generation_progress["step"] = step + 1
                    _generation_progress["total_steps"] = steps
                    return callback_kwargs

                _guidance_scale_2 = guidance_scale_2

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    try:
                        gen_kwargs = {
                            "prompt": prompt,
                            "negative_prompt": negative_prompt if negative_prompt else None,
                            "width": width,
                            "height": height,
                            "num_frames": num_frames,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "callback_on_step_end": video_step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }
                        # MoE models use a second guidance scale
                        if _guidance_scale_2 is not None:
                            gen_kwargs["guidance_scale_2"] = _guidance_scale_2
                        result = pipe(**gen_kwargs)
                        # Before the frame check: a stopped run is a stop, not
                        # a pipeline that failed to deliver frames.
                        raise_if_cancelled()
                        if not hasattr(result, 'frames') or result.frames is None or len(result.frames) == 0:
                            raise ValueError("Pipeline returned no video frames")
                        return result.frames[0]
                    finally:
                        _generation_progress["active"] = False

                frames = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert frames to MP4 bytes via temp file
                # (export_to_video only accepts file paths, not BytesIO)
                import tempfile
                import os
                from diffusers.utils import export_to_video
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    export_to_video(frames, tmp_path, fps=fps)
                    with open(tmp_path, 'rb') as f:
                        video_bytes = f.read()
                finally:
                    os.unlink(tmp_path)

                logger.info(
                    f"[DIFFUSERS] Generated video: {len(video_bytes)} bytes, "
                    f"{num_frames} frames @ {fps}fps, seed={seed}"
                )
                return video_bytes

            finally:
                self._model_in_use[model_id] -= 1

        except GpuBusy:
            raise          # busy is not a failed generation
        except GenerationCancelled:
            raise          # stopped on request is not a failed generation either
        except Exception as e:
            logger.error(f"[DIFFUSERS] Video generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_video_from_image(
        self,
        image_bytes: bytes,
        prompt: str = "",
        model_id: str = "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
        negative_prompt: str = "",
        width: int = 1280,
        height: int = 720,
        num_frames: int = 81,
        steps: int = 40,
        cfg_scale: float = 4.0,
        fps: int = 16,
        seed: int = -1,
        guidance_scale_2: float = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate a video from an image using WanImageToVideoPipeline.

        Args:
            image_bytes: PNG/JPEG image bytes
            prompt: Optional text prompt to guide the animation
            model_id: Wan I2V model to use
            negative_prompt: Negative prompt
            width: Video width
            height: Video height
            num_frames: Number of frames to generate
            steps: Number of inference steps
            cfg_scale: Guidance scale
            fps: Frames per second for output MP4
            seed: Random seed (-1 for random)
            guidance_scale_2: Second guidance scale for MoE models (A14B)

        Returns:
            MP4 video bytes, or None on failure
        """
        try:
            import torch
            from PIL import Image
            import io

            pipeline_class = "WanImageToVideoPipeline"

            if not await self.load_model(model_id, pipeline_class):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Convert image bytes to PIL Image
                pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                # Resize to target dimensions
                pil_image = pil_image.resize((width, height), Image.LANCZOS)

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(
                    f"[DIFFUSERS] Generating I2V video: steps={steps}, "
                    f"size={width}x{height}, frames={num_frames}, seed={seed}"
                )

                def video_step_callback(pipe_inst, step, timestep, callback_kwargs):
                    if interrupt_if_cancelled(pipe_inst):
                        return callback_kwargs
                    _generation_progress["step"] = step + 1
                    _generation_progress["total_steps"] = steps
                    return callback_kwargs

                _guidance_scale_2 = guidance_scale_2
                _pil_image = pil_image

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    try:
                        gen_kwargs = {
                            "image": _pil_image,
                            "prompt": prompt if prompt else "",
                            "negative_prompt": negative_prompt if negative_prompt else None,
                            "width": width,
                            "height": height,
                            "num_frames": num_frames,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "callback_on_step_end": video_step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }
                        if _guidance_scale_2 is not None:
                            gen_kwargs["guidance_scale_2"] = _guidance_scale_2
                        result = pipe(**gen_kwargs)
                        # Before the frame check: a stopped run is a stop, not
                        # a pipeline that failed to deliver frames.
                        raise_if_cancelled()
                        if not hasattr(result, 'frames') or result.frames is None or len(result.frames) == 0:
                            raise ValueError("Pipeline returned no video frames")
                        return result.frames[0]
                    finally:
                        _generation_progress["active"] = False

                frames = await asyncio.to_thread(self._locked_generate, _generate)

                import tempfile
                import os
                from diffusers.utils import export_to_video
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    export_to_video(frames, tmp_path, fps=fps)
                    with open(tmp_path, 'rb') as f:
                        video_bytes = f.read()
                finally:
                    os.unlink(tmp_path)

                logger.info(
                    f"[DIFFUSERS] Generated I2V video: {len(video_bytes)} bytes, "
                    f"{num_frames} frames @ {fps}fps, seed={seed}"
                )
                return video_bytes

            finally:
                self._model_in_use[model_id] -= 1

        except GpuBusy:
            raise          # busy is not a failed generation
        except GenerationCancelled:
            raise          # stopped on request is not a failed generation either
        except Exception as e:
            logger.error(f"[DIFFUSERS] I2V video generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_image_with_fusion(
        self,
        prompt: str,
        t5_prompt: Optional[str] = None,
        alpha_factor: float = 0.0,
        model_id: str = DEFAULT_MODEL_ID,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
        loras: Optional[list] = None,
        fusion_strategy: str = "legacy",
        pooled_prompt: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Generate an image using T5-CLIP token-level fusion (Surrealizer)

        Fusion strategies:
        - "original": (its core takes the same "#path=" option as centered_fade
          below; its own alpha IS the turn on the sphere, because its anchors
          are 0 and 1)
          the 2025 ComfyUI workflow as it ran there -- CLIP-L alone
          (CLIP-G's dims zero, raw unprojected pooled), T5 at its own token
          length, plain LERP over the first 77 positions with T5's remainder
          appended. a=0 is CLIP-L alone, a=1 is T5 alone.
          Since 2026-09-12 no surface sends this name: Encoder Fusion's
          switch position "Adapted prompts" runs the two prompts on
          centered_fade (the route rewrites the name), so that against "Same
          prompt" it changes the prompts alone. This branch is the
          reproduction, reached by hand.
        - "legacy": Original behavior. LERP first 77 tokens, append T5 rest
          unchanged. T5 tokens >77 act as semantic anchor (dilute surreal
          effect on long prompts).
        - "slerp": legacy's operands and legacy's tail, with the core
          interpolated on the sphere (slerp_tokens, from the ComfyUI node
          ai4artsed_conditioning_fusion). a=0 is CLIP and a=1 is T5, as under
          legacy; between them the direction turns by a*theta and the length
          runs from the one to the other, and past them it keeps turning.
        - "dual_alpha": Kontingente Ähnlichkeit. Full alpha on first 77
          tokens (core: the CLIP<->T5 blend that makes the surreal direction),
          a gentle 0.15x alpha on tokens 78+ (extended anchor, keeps normal T5
          semantics from dominating). Balances recognizability with extrapolation.
        - "normalized": Uniform alpha on ALL positions (CLIP=0 beyond 77),
          then L2-normalize each token to mean T5 magnitude. Preserves
          extrapolation direction, controls magnitude for attention balance.
        - "centered_fade": 1D axis with a genuine middle. At the neutral point
          both CLIP-L and T5 act fully; the control fades toward pure T5 or pure
          CLIP-L, and inverts past the ends. Fixes the missing "both-full" center
          of dual_alpha (see _fuse_prompt; commit d9683936). Its tail runs at
          x1. Its core runs across the chord between the two readings;
          "centered_fade#path=sphere" walks the great circle through them
          instead, at t = (alpha + 1) / 2, so the three anchors hold and the
          middle keeps the readings' own length. No surface sends the sphere
          any more: it joins the embeddings of two different prompts, and has
          no object between the two readings of one. The name stays for the
          stored runs of 2026-09-10 to -12 and for the research that cites
          it.

        Args:
            prompt: Text prompt (used for CLIP-L encoding)
            t5_prompt: Optional expanded prompt for T5 encoding (None = use prompt)
            alpha_factor: -75 to +75 (raw from UI slider)
                0 = pure CLIP-L, 1 = pure T5, 15-35 = surreal sweet spot
            model_id: SD3.5 model to use
            negative_prompt: Negative prompt (fused with same alpha)
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            callback: Step callback for progress
            fusion_strategy: "legacy", "slerp", "dual_alpha", "centered_fade", "normalized" (deprecated); _fuse_prompt also implements experimental CLIP-G / random variants (cg_band, cg_damp, clipg_anchor_no_t5, clip_anchor_neg_t5, cg_band_oldpool, random_matched, random_shuffled)

        Returns:
            PNG image bytes, or None on failure
        """
        try:
            import torch
            import torch.nn.functional as F
            import io

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Guard: verify individual encoder methods are available
                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[DIFFUSERS-FUSION] Pipeline missing _get_clip_prompt_embeds or _get_t5_prompt_embeds")
                    return None

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(f"[DIFFUSERS-FUSION] Generating: strategy={fusion_strategy}, alpha={alpha_factor}, steps={steps}, size={width}x{height}, seed={seed}, t5_expanded={t5_prompt is not None}")

                # --- Direktiven-Parsing: "<base>#k=v#..." (rng=, band=, cap=, capdir=) ---
                # Erweiterungen laufen ueber den Strategie-String, damit die Route
                # (diffusers_routes.py) unangetastet bleibt. Nacht-Reihe E1-E4 2026-07-03.
                import os as _os
                import json as _json
                _fs_parts = fusion_strategy.split('#')
                fusion_base = _fs_parts[0]
                fs_opts = {}
                for _part in _fs_parts[1:]:
                    if '=' in _part:
                        _k, _v = _part.split('=', 1)
                        fs_opts[_k] = _v
                cap_steps = set()
                if 'cap' in fs_opts:
                    cap_steps = {int(_x) for _x in fs_opts['cap'].split(',') if _x.strip()}
                cap_dir = fs_opts.get('capdir')
                # Path the core takes between the two readings: the chord by
                # default, "path=sphere" the great circle through them. Sent by
                # no surface since 2026-09-12; reached by hand and by the
                # stored runs that carry it.
                _path = fs_opts.get('path')
                if cap_dir:
                    _os.makedirs(cap_dir, exist_ok=True)

                # Folge-Reihe I (2026-09-13): the research options are checked here,
                # once, so that a misspelt option is an error naming its cause and
                # never a run that silently computes something else.
                _bad = None
                if 't5len' in fs_opts and not fs_opts['t5len'].isdigit():
                    _bad = "t5len needs an integer"
                elif fs_opts.get('pooled') not in (None, 'zero'):
                    _bad = "pooled takes only 'zero'"
                elif fs_opts.get('neg') not in (None, 'alpha0'):
                    _bad = "neg takes only 'alpha0'"
                elif fs_opts.get('pos0') not in (None, 'keep', 'only', 'random'):
                    _bad = "pos0 takes keep, only or random"
                elif fs_opts.get('fuse_only') is not None and not (
                        {_c.strip() for _c in fs_opts['fuse_only'].split(',')}
                        <= {'bos', 'content', 'eos', 'pads'}):
                    _bad = "fuse_only takes classes from bos, content, eos, pads"
                elif fs_opts.get('hook') not in (None, 'textstream'):
                    _bad = "hook takes only 'textstream'"
                elif fs_opts.get('hook') and not cap_dir:
                    _bad = "hook=textstream needs capdir=<dir>"
                elif fs_opts.get('cfg_interval') is not None:
                    _ci = [_x.strip() for _x in fs_opts['cfg_interval'].split(',')]
                    if len(_ci) != 2 or not all(_x.isdigit() for _x in _ci):
                        _bad = "cfg_interval needs two integers a,b"
                    elif cfg_scale <= 1.0:
                        # the batch is doubled from the first step on and cannot
                        # change size mid-run; a weight of 1 inside the interval
                        # would undouble it
                        _bad = "cfg_interval needs cfg_scale > 1"
                if _bad is None and fusion_base == 'legacy_dirnorm':
                    try:
                        float(fs_opts['dir'])
                        float(fs_opts['norm'])
                    except (KeyError, ValueError):
                        _bad = "legacy_dirnorm needs dir=<alpha> and norm=<alpha>"
                    if _bad is None and fs_opts.get('neg'):
                        _bad = "neg=alpha0 has no effect under legacy_dirnorm (dir and norm set both passes)"
                if _bad is None and fusion_base == 'push_negmu':
                    if not fs_opts.get('mu') or not _os.path.isfile(fs_opts['mu']):
                        _bad = "push_negmu needs mu=<path of an existing .pt file>"
                if _bad is None and fusion_base == 'three_factor':
                    try:
                        float(fs_opts['a']); float(fs_opts['b']); float(fs_opts['c'])
                    except (KeyError, ValueError):
                        _bad = "three_factor needs a=<float>, b=<float> and c=<float>"
                    if _bad is None and fs_opts.get('t5') not in ('full', 'tail'):
                        _bad = "three_factor needs t5=full (T5 rows 0..511 below the CLIP rows) or t5=tail (rows 77..)"
                    if _bad is None and fs_opts.get('shift') is not None and not (
                            fs_opts['shift'].isdigit() and int(fs_opts['shift']) < 77):
                        _bad = "shift takes an integer 0..76: that many zero rows before T5's row 0 (Folge-Reihe N)"
                    if _bad is None and fs_opts.get('neg'):
                        _bad = "neg=alpha0 has no effect under three_factor (a, b, c set both passes)"
                if _bad is None and fusion_base in ('original', 'original_cg'):
                    _new = {'t5len', 'pooled', 'pos0', 'fuse_only', 'neg'} & set(fs_opts)
                    if _new or pooled_prompt is not None:
                        _bad = (f"{fusion_base} runs none of the options of Folge-Reihe I "
                                f"({', '.join(sorted(_new)) or 'pooled_prompt'})")
                if _bad is not None:
                    raise ValueError(f"fusion_strategy '{fusion_strategy}': {_bad}")

                # Under the original fusion the T5 side has no fixed length, so the
                # positive and the negative pass come out different lengths -- and
                # diffusers refuses that pair, because it stacks the two into one
                # batch for classifier-free guidance. ComfyUI had no such constraint:
                # comfy/samplers.py groups conditionings by shape and runs each at
                # its own length, so its negative stayed at its own 77 while the
                # positive was as long as its text. Inside a single pipeline call
                # both must match, so both run at the longer of the two and the
                # shorter side gets T5 pad tokens -- which is what stock SD3 does for
                # every short negative anyway. Set once in _generate, before either
                # pass, so that neither text can be cut to fit the other.
                _original_t5_len = {"n": None}

                def _fuse_prompt(clip_text: str, t5_text: str, pooled_text=None,
                                 alpha_override=None, _alpha_outer=alpha_factor):
                    """T5-CLIP fusion with selectable strategy.

                    Encoding (shared across all strategies):
                    - CLIP-L + CLIP-G: [1, 77, 4096] (2048d real + 2048d zeros)
                    - T5-XXL: [1, T5_len, 4096] (all 4096d real)
                    - Pooled: CLIP-L(768d) + CLIP-G(1280d) = [1, 2048] (constant across alpha;
                      T5 has no pooled counterpart in SD3.5, so pooled is never alpha-weighted)

                    The 2048d/4096d asymmetry (CLIP-L+CLIP-G real in a 4096d space) is the
                    foundation all strategies exploit — it creates the vector space
                    that extrapolation pushes into. (Previously CLIP-L only; CLIP-G added
                    because its exclusion was a pragmatic/technical gap, not a principled
                    design choice — CLIP-G's pooled half drives AdaLN modulation at every
                    MMDiT block, so omitting it degraded the "beide voll" baseline globally.)
                    """
                    # Folge-Reihe I (2026-09-13): the negative pass may run at its own
                    # alpha ("neg=alpha0"). The name is rebound here, once, before any
                    # branch reads it, so every branch below sees this pass's alpha.
                    alpha_factor = _alpha_outer if alpha_override is None else float(alpha_override)
                    device = pipe._execution_device

                    if fusion_base in ("original", "original_cg"):
                        # ----------------------------------------------------------------
                        # The 2025 ComfyUI workflow, restored as it ran there.
                        # Sources: archive/legacy_docs/workflows_legacy/vector/
                        #   ai4artsed_Surrealization_2506092253.json (nodes 6/21/51/54/18)
                        #   and the node ai4artsed_t5_clip_fusion.py.
                        # Three things separate it from every strategy below, and each of
                        # them was lost separately over the sessions:
                        #
                        #  1. CLIP-L ALONE. CLIPLoader("clip_l.safetensors", type=sd3)
                        #     builds an SD3ClipModel with clip_g=None, so sd3_clip.py pads
                        #     clip_l's 768 dims straight to 4096: dims 768:4096 are ZERO,
                        #     CLIP-G's slot included. Its pooled is
                        #     cat(clip_l pooler, zeros(1280)) -- and that pooler is the RAW
                        #     one (SD3ClipModel builds clip_l with
                        #     return_projected_pooled=False), where diffusers takes the
                        #     projected text_embeds. The pooled drives AdaLN in every MMDiT
                        #     block, so this is not a rounding difference.
                        #  2. T5 AT ITS OWN LENGTH. ComfyUI's T5XXLTokenizer runs
                        #     pad_to_max_length=False with min_length=77: the tail is as
                        #     long as the text is, not padded out to a fixed 512.
                        #  3. THE LERP over the first 77 positions, T5's remainder
                        #     appended untouched, pooled from the CLIP side.
                        #
                        # Anchors on this axis: a=0 is CLIP-L alone, a=1 is T5 alone.
                        #
                        # Changed 2026-08-23, and this one is NOT the 2025 workflow:
                        # between the anchors the LERP weighed both readings by
                        # halves, and 0.5*CLIP + 0.5*T5 conditions more weakly than
                        # either reading alone: two halves do not add up to
                        # full guidance strength.
                        # So the middle of this axis now carries centered_fade's
                        # band: both readings at 1, and the standing one held there
                        # while the other fades. AT the anchors and OUTSIDE them
                        # nothing changed, and the two meet without a step -- what a
                        # run at a=0, a=1 or beyond them produced, it still produces.
                        # Strictly between them it does not.
                        # ----------------------------------------------------------------
                        # `original_cg` is a research probe; no surface sets
                        # it. It asks what happens if CLIP-G is added
                        # to this path UNMANIPULATED -- its embedding in dims
                        # 768:2048 at weight 1 whatever alpha does, and its pooled
                        # half beside CLIP-L's raw one. 
                        # Everything else stays the workflow's: CLIP-L alpha-weighted,
                        # T5 at its own length, the raw CLIP-L pooler.
                        with_cg = fusion_base == "original_cg"
                        te = pipe.text_encoder
                        # The tokenizers and the encoders together: this runs
                        # outside _locked_generate, and everything it touches is
                        # shared with whatever generation is in flight.
                        with self._inference_lock, torch.no_grad():
                            # The hidden states come through the pipeline's own
                            # method, because that is the call accelerate's offload
                            # hook wraps -- reaching into the submodule first would
                            # run it wherever the weights happen to sit.
                            clip_l_embeds, _ = pipe._get_clip_prompt_embeds(
                                prompt=clip_text, device=device,
                                num_images_per_prompt=1, clip_model_index=0,
                            )
                            # The pooled ComfyUI uses is the RAW one, and diffusers
                            # hands out only the projected text_embeds -- so this one
                            # pass into the transformer itself, right after the call
                            # above has placed the encoder.
                            te_device = next(te.parameters()).device
                            clip_ids = pipe.tokenizer(
                                clip_text,
                                padding="max_length",
                                max_length=pipe.tokenizer_max_length,
                                truncation=True,
                                return_tensors="pt",
                            ).input_ids.to(te_device)
                            l_pooled_raw = te.text_model(clip_ids).pooler_output.to(device)
                            # ComfyUI returns both conditionings as fp32 and fuses in
                            # fp32 (sd1_clip.py: z.float(), pooled.float()); with
                            # coefficients running to +/-75 that is not cosmetic.
                            if with_cg:
                                clip_g_embeds, clip_g_pooled = pipe._get_clip_prompt_embeds(
                                    prompt=clip_text, device=device,
                                    num_images_per_prompt=1, clip_model_index=1,
                                )
                                clip_combined = torch.cat(
                                    [clip_l_embeds.float(), clip_g_embeds.float()], dim=-1
                                )
                                clip_padded = F.pad(
                                    clip_combined, (0, 4096 - clip_combined.shape[-1])
                                )
                                # CLIP-L's pooler stays the RAW one; CLIP-G's is the
                                # projected one the pipeline hands out, as everywhere
                                # else it is used.
                                pooled = torch.cat(
                                    [l_pooled_raw.float(), clip_g_pooled.float()], dim=-1
                                )
                            else:
                                clip_padded = F.pad(
                                    clip_l_embeds.float(), (0, 4096 - clip_l_embeds.shape[-1])
                                )
                                pooled = F.pad(l_pooled_raw.float(), (0, 1280))

                            # min_length=77 as in ComfyUI; beyond that the text decides.
                            t5_ids = pipe.tokenizer_3(
                                t5_text, padding=False, truncation=False
                            ).input_ids
                            t5_natural_len = _original_t5_len["n"] or max(77, len(t5_ids))
                            t5_embeds = pipe._get_t5_prompt_embeds(
                                prompt=t5_text,
                                num_images_per_prompt=1,
                                max_sequence_length=t5_natural_len,
                                device=device,
                            ).float()

                        interp_len = min(77, clip_padded.shape[1])
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_append = t5_embeds[:, interp_len:, :]
                        # The band on this axis' own anchors: 0 is CLIP-L alone and
                        # 1 is T5 alone, so its middle is 0.5 and its half-width is
                        # 0.5. t runs -1 .. +1 across it, which is the same reading
                        # centered_fade's alpha carries.
                        t_val = 2.0 * alpha_factor - 1.0
                        if -1.0 <= t_val <= 1.0:
                            w_clip = 1.0 if t_val <= 0.0 else 1.0 - t_val
                            w_t5 = 1.0 + t_val if t_val <= 0.0 else 1.0
                        else:
                            w_clip = 1.0 - alpha_factor
                            w_t5 = alpha_factor
                        if _path == "sphere":
                            # This axis carries its two anchors at alpha 0 and
                            # alpha 1, so the alpha IS the turn: 0 stands at
                            # CLIP-L's direction, 1 at T5's, and past either end
                            # the direction keeps turning where the weights above
                            # invert one side.
                            #
                            # CLIP-G has no place on the sphere. Under
                            # `original_cg` its 1280 dims ride at weight 1 whatever
                            # alpha does, which is a statement about one part of
                            # the reading; a turn moves the whole reading at once
                            # and can hold no part of it still. The combination is
                            # refused rather than answered with a run that is
                            # neither of the two things it names.
                            if with_cg:
                                raise ValueError(
                                    "original_cg holds CLIP-G at weight 1, which the "
                                    "sphere cannot do: a turn moves the whole reading. "
                                    "Use original#path=sphere, or original_cg on the chord."
                                )
                            fused_core = slerp_tokens(clip_interp, t5_interp, alpha_factor)
                        elif with_cg:
                            # Dimension-wise: alpha on CLIP-L's 768, 1 on CLIP-G's
                            # 1280, and T5 over the whole 4096 as before. The tail
                            # from 2048 is zero either way.
                            wvec = torch.ones(
                                clip_interp.shape[-1],
                                device=clip_interp.device,
                                dtype=clip_interp.dtype,
                            )
                            wvec[0:768] = w_clip
                            fused_core = clip_interp * wvec + w_t5 * t5_interp
                        else:
                            fused_core = w_clip * clip_interp + w_t5 * t5_interp
                        fused_embeds = torch.cat([fused_core, t5_append], dim=1)
                        out_dtype = pipe.transformer.dtype
                        fused_embeds = fused_embeds.to(out_dtype)
                        pooled = pooled.to(out_dtype)
                        _path_name = "sphere" if _path == "sphere" else "chord"
                        logger.info(
                            f"[FUSION:{fusion_base}] alpha={alpha_factor:.3f} t={t_val:.3f} "
                            f"path={_path_name} "
                            f"w_clip={w_clip:.3f} w_t5={w_t5:.3f} "
                            f"{'CLIP-L + CLIP-G x1 (pooled=raw clip_l + clip_g)' if with_cg else 'CLIP-L alone (dims 768:4096 zero, pooled=raw clip_l+zeros)'}, "
                            f"{interp_len}t + T5 tail {t5_embeds.shape[1] - interp_len}t, "
                            f"T5 at its own length {t5_embeds.shape[1]}"
                        )
                        return fused_embeds, pooled

                    with self._inference_lock, torch.no_grad():
                        # --- CLIP-L + CLIP-G (pattern per the "all"-encoder path above) ---
                        clip_l_embeds, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=clip_text, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_embeds, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=clip_text, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        clip_combined = torch.cat([clip_l_embeds, clip_g_embeds], dim=-1)
                        clip_padded = F.pad(clip_combined, (0, 4096 - clip_combined.shape[-1]))
                        pooled = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)
                        # Folge-Reihe I (2026-09-13): the pooled vector from a text of
                        # its own (request field pooled_prompt), so that a foreign CLIP
                        # text can be negated while the pooled vector stays the
                        # prompt's; pooled=zero is the training's "CLIP dropped" state.
                        if pooled_text is not None and pooled_text != clip_text:
                            _, _pl = pipe._get_clip_prompt_embeds(
                                prompt=pooled_text, device=device, num_images_per_prompt=1, clip_model_index=0
                            )
                            _, _pg = pipe._get_clip_prompt_embeds(
                                prompt=pooled_text, device=device, num_images_per_prompt=1, clip_model_index=1
                            )
                            pooled = torch.cat([_pl, _pg], dim=-1)
                        if fs_opts.get('pooled') == 'zero':
                            pooled = torch.zeros_like(pooled)

                        # --- T5 encoding --- (t5len=<N> sets the length; 512 as before)
                        _t5_max_len = int(fs_opts.get('t5len', 512))
                        t5_embeds = pipe._get_t5_prompt_embeds(
                            prompt=t5_text, num_images_per_prompt=1, max_sequence_length=_t5_max_len, device=device
                        )

                    interp_len = min(77, clip_padded.shape[1])
                    t5_len = t5_embeds.shape[1]

                    if fusion_base == "dual_alpha":
                        # Full extrapolation on core (where CLIP-T5 mixing creates
                        # surreal direction), gentle anchor on extended (prevents
                        # normal T5 semantics from dominating MMDiT attention).
                        alpha_core = alpha_factor
                        alpha_ext = alpha_factor * 0.15

                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]

                        # Core: full extrapolation (surreal direction from CLIP-T5 blend)
                        fused_core = (1.0 - alpha_core) * clip_interp + alpha_core * t5_interp
                        # Extended: gentle anchor (doesn't overwhelm core with normal semantics)
                        fused_ext = alpha_ext * t5_remainder

                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)

                        logger.info(
                            f"[FUSION:dual_alpha] core_α={alpha_core:.2f} ({interp_len}t), "
                            f"ext_α={alpha_ext:.2f} ({t5_len - interp_len}t)"
                        )

                    elif fusion_base == "normalized":
                        # Full extrapolation on core tokens, then scale extended
                        # tokens to match core magnitude. This preserves the surreal
                        # extrapolation direction while keeping attention balanced
                        # (extended tokens don't overwhelm OR underwhelm core).

                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]

                        # Core: full extrapolation (same as legacy)
                        fused_core = (1.0 - alpha_factor) * clip_interp + alpha_factor * t5_interp

                        # Scale extended tokens to match core's extrapolated magnitude
                        core_mag = fused_core.norm(dim=-1).mean()
                        t5_ext_norms = t5_remainder.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                        fused_ext = t5_remainder * (core_mag / t5_ext_norms)

                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)

                        logger.info(
                            f"[FUSION:normalized] α={alpha_factor}, core_mag={core_mag:.2f}, "
                            f"core={interp_len}t, ext={t5_len - interp_len}t"
                        )

                    elif fusion_base == "centered_fade":
                        # Normalband (Halbbreite h) MIT Rampe (keine Deadzone):
                        #   t = alpha / h
                        #   t <= 0:  w_clip = max(1, -t)   ;  w_t5 = 1 + t
                        #   t >  0:  w_clip = 1 - t        ;  w_t5 = max(1, t)
                        #   Anker:  alpha=-h -> (1,0) nur CLIP | alpha=0 -> (1,1) beide voll | alpha=+h -> (0,1) nur T5.
                        #   |alpha|>h: stetige Fortsetzung, ein Gewicht waechst unbeschraenkt, das andere
                        #   invertiert/uebersaettigt (deckt sich fuer alpha>=h exakt mit der Original-LERP
                        #   w_clip=1-alpha, w_t5=alpha). KEIN min-Deckel auf die wachsende Seite.
                        NORMAL_BAND_H = 1.0
                        a_val = alpha_factor
                        t_val = a_val / NORMAL_BAND_H
                        if t_val <= 0.0:
                            w_clip = max(1.0, -t_val)
                            w_t5 = 1.0 + t_val
                        else:
                            w_clip = 1.0 - t_val
                            w_t5 = max(1.0, t_val)
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        if _path == "sphere":
                            # The same three anchors, walked on the sphere instead
                            # of across the chord: t = (alpha + 1) / 2 puts CLIP
                            # alone at alpha -1, the bisector at 0 and T5 alone at
                            # +1. Past the anchors the direction keeps turning,
                            # where the chord inverts one of the two weights.
                            # slerp_tokens runs the length linearly between the two
                            # readings, so the middle stands at their mean length
                            # rather than at the chord's sqrt(2) for two readings
                            # that meet at a right angle.
                            _t_sphere = (a_val + 1.0) / 2.0
                            fused_core = slerp_tokens(clip_interp, t5_interp, _t_sphere)
                        else:
                            fused_core = w_clip * clip_interp + w_t5 * t5_interp
                        fused_ext = t5_remainder  # T5-Schwanz x1 (legacy "wie bisher")
                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)
                        _path_name = "sphere" if _path == "sphere" else "chord"
                        logger.info(
                            f"[FUSION:centered_fade] alpha={a_val:.3f} h={NORMAL_BAND_H} "
                            f"path={_path_name} w_clip={w_clip:.3f} w_t5={w_t5:.3f}, "
                            f"core {interp_len}t, tail {t5_len - interp_len}t x1"
                        )

                    elif fusion_base == "cg_band":
                        # V1: CLIP-G eigenes Gewicht, im Normalband mitgerampt, ausserhalb eingefroren.
                        #   w_L = centered_fade-Rampe; w_G = clamp(w_L, 0, 1); w_t5 = centered_fade-Rampe.
                        #   Anker: a=-1 voll CLIP(L+G) | a=0 beide voll | a=+1 nur T5.
                        #   a<-1 -> w_G=1 (Anker) ; a>1 -> w_G=0 (wie alt, CLIP-L-only).
                        t = alpha_factor
                        if t <= 0.0:
                            w_l = max(1.0, -t); w_t5 = 1.0 + t
                        else:
                            w_l = 1.0 - t; w_t5 = max(1.0, t)
                        w_g = min(1.0, max(0.0, w_l))
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = w_l
                        wvec[768:2048] = w_g
                        fused_core = clip_interp * wvec + w_t5 * t5_interp
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                        logger.info(f"[FUSION:cg_band] alpha={alpha_factor:.3f} w_l={w_l:.3f} w_g={w_g:.3f} w_t5={w_t5:.3f}")

                    elif fusion_base == "cg_damp":
                        # V2: CLIP-G nie invertiert/aufgeblasen -- w_G = w_L / max(1,|alpha|) (Betrag <=1).
                        t = alpha_factor
                        if t <= 0.0:
                            w_l = max(1.0, -t); w_t5 = 1.0 + t
                        else:
                            w_l = 1.0 - t; w_t5 = max(1.0, t)
                        w_g = w_l / max(1.0, abs(alpha_factor))
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = w_l
                        wvec[768:2048] = w_g
                        fused_core = clip_interp * wvec + w_t5 * t5_interp
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                        logger.info(f"[FUSION:cg_damp] alpha={alpha_factor:.3f} w_l={w_l:.3f} w_g={w_g:.3f} w_t5={w_t5:.3f}")

                    elif fusion_base == "clipg_anchor_no_t5":
                        # V3: reiner CLIP-Raum, KEIN T5. CLIP-L (-Seite) <-> CLIP-G (+Seite) gerampt.
                        #   a=-1 -> nur CLIP-L | a=0 -> CLIP-L+G voll | a=+1 -> nur CLIP-G. Kein Tail.
                        t = alpha_factor
                        if t <= 0.0:
                            w_l = max(1.0, -t); w_g = 1.0 + t
                        else:
                            w_l = 1.0 - t; w_g = max(1.0, t)
                        clip_interp = clip_padded[:, :interp_len, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = w_l
                        wvec[768:2048] = w_g
                        fused_embeds = clip_interp * wvec  # nur 77 CLIP-Token, kein T5
                        logger.info(f"[FUSION:clipg_anchor_no_t5] alpha={alpha_factor:.3f} w_l={w_l:.3f} w_g={w_g:.3f} (no T5)")

                    elif fusion_base == "clip_anchor_neg_t5":
                        # V4: CLIP(L+G) fester Anker (x1), T5 subtrahiert: core = CLIP + (-alpha)*T5.
                        #   a=0 -> pures CLIP | a>0 -> T5 abgezogen | a<0 -> T5 addiert. Tail x(-alpha).
                        w_t5 = -alpha_factor
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        fused_core = clip_interp + w_t5 * t5_interp
                        fused_ext = w_t5 * t5_remainder
                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)
                        logger.info(f"[FUSION:clip_anchor_neg_t5] alpha={alpha_factor:.3f} clip=x1 w_t5={w_t5:.3f}")


                    elif fusion_base == "cg_band_oldpool":
                        # DIAGNOSE: Sequenz exakt wie cg_band, aber pooled = ALT (CLIP-L + Nullen).
                        #   Isoliert den Pooled/AdaLN-Beitrag von CLIP-G. Bei a>1 (w_g=0) ist die
                        #   Sequenz bit-identisch zum alten legacy CLIP-L-only-Lauf -> reproduziert
                        #   diesen exakt (gleiche Params). Differenz zu cg_band = allein Pooled/AdaLN.
                        t = alpha_factor
                        if t <= 0.0:
                            w_l = max(1.0, -t); w_t5 = 1.0 + t
                        else:
                            w_l = 1.0 - t; w_t5 = max(1.0, t)
                        w_g = min(1.0, max(0.0, w_l))
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = w_l
                        wvec[768:2048] = w_g
                        fused_core = clip_interp * wvec + w_t5 * t5_interp
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                        pooled = F.pad(clip_l_pooled, (0, 1280))  # ALTE Pooled: CLIP-G raus
                        logger.info(f"[FUSION:cg_band_oldpool] alpha={alpha_factor:.3f} w_l={w_l:.3f} w_g={w_g:.3f} w_t5={w_t5:.3f} (pooled=OLD CLIP-L+zeros)")


                    elif fusion_base == "ramp3_chain":
                        # Simplex-Kette CLIP-L -> CLIP-G -> T5 (kontinuierlich, gegenlaeufig).
                        #   a<=0: w_L=-a, w_G=1+a, w_T5=0   |   a>=0: w_L=0, w_G=1-a, w_T5=a
                        #   Anker: a=-1 pur CLIP-L | a=0 pur CLIP-G | a=+1 pur T5. |a|>1 extrapoliert.
                        a = alpha_factor
                        if a <= 0.0:
                            w_l = -a; w_g = 1.0 + a; w_t5 = 0.0
                        else:
                            w_l = 0.0; w_g = 1.0 - a; w_t5 = a
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = w_l
                        wvec[768:2048] = w_g
                        fused_core = clip_interp * wvec + w_t5 * t5_interp
                        fused_ext = w_t5 * t5_remainder
                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)
                        logger.info(f"[FUSION:ramp3_chain] alpha={a:.3f} w_l={w_l:.3f} w_g={w_g:.3f} w_t5={w_t5:.3f}")

                    elif fusion_base == "ramp3_t5center":
                        # An 0 gespiegelt, T5 mittig: CLIP-L(-1) <-> T5(0) <-> CLIP-G(+1).
                        #   a<=0: w_L=-a, w_T5=1+a, w_G=0   |   a>=0: w_G=a, w_T5=1-a, w_L=0
                        a = alpha_factor
                        if a <= 0.0:
                            w_l = -a; w_t5 = 1.0 + a; w_g = 0.0
                        else:
                            w_l = 0.0; w_t5 = 1.0 - a; w_g = a
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = w_l
                        wvec[768:2048] = w_g
                        fused_core = clip_interp * wvec + w_t5 * t5_interp
                        fused_ext = w_t5 * t5_remainder
                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)
                        logger.info(f"[FUSION:ramp3_t5center] alpha={a:.3f} w_l={w_l:.3f} w_g={w_g:.3f} w_t5={w_t5:.3f}")

                    elif fusion_base == "v4_sym":
                        # V4 an 0 gespiegelt: CLIP(L+G) x1 Anker, w_T5=|a| (T5 beidseitig verstaerkt).
                        #   a=0 pur CLIP | a=+-1 CLIP+1*T5 | a=+-15 CLIP+15*T5. Symmetrisch: +a == -a.
                        a = alpha_factor
                        w_t5 = abs(a)
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        fused_core = clip_interp + w_t5 * t5_interp
                        fused_ext = w_t5 * t5_remainder
                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)
                        logger.info(f"[FUSION:v4_sym] alpha={a:.3f} clip=x1 w_t5={w_t5:.3f}")


                    elif fusion_base == "ramp3_pointsym":
                        # PUNKTSPIEGELUNG am Ursprung (ungerade, f(-a)=-f(a)) + gegenlaeufig.
                        #   CLIP-L = gerader Anker (w_L=1); CLIP-G und T5 ungerade & gegenlaeufig:
                        #   w_G=a, w_T5=-a.  a=0 -> pur CLIP-L | +a: +CLIP-G/-T5 | -a: -CLIP-G/+T5.
                        #   config(-a) = CLIP-L - Teil ; config(+a) = CLIP-L + Teil  -> punktgespiegelt.
                        a = alpha_factor
                        w_g = a
                        w_t5 = -a
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = 1.0        # CLIP-L: gerader Anker
                        wvec[768:2048] = w_g     # CLIP-G: ungerade
                        fused_core = clip_interp * wvec + w_t5 * t5_interp
                        fused_ext = w_t5 * t5_remainder
                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)
                        logger.info(f"[FUSION:ramp3_pointsym] alpha={a:.3f} w_l=1 w_g={w_g:.3f} w_t5={w_t5:.3f}")


                    elif fusion_base == "pooled_overdrive":
                        # HEBEL #1: Global-Overdrive ueber das Pooled (AdaLN an JEDEM MMDiT-Block).
                        #   Sequence = STOCK SD3: CLIP 77 + T5 512 = 589 Token, voellig UNVERAENDERT
                        #   -> bei beta=1 exakt das Stock-Bild. Nur pooled wird skaliert: pooled *= beta.
                        #   beta = alpha_factor.  1=stock | >1 Overdrive | 0 kein Text-Global (nur Timestep) | <0 invertiert.
                        #   Nur der POSITIVE Pass (nicht-leerer Text) wird skaliert; leerer Negativ-Pass bleibt roh.
                        beta = alpha_factor
                        fused_embeds = torch.cat([clip_padded, t5_embeds], dim=1)
                        if clip_text.strip():
                            pooled = pooled * beta
                        logger.info(f"[FUSION:pooled_overdrive] beta={beta:.3f} seq=stock({fused_embeds.shape[1]}t) pooled*=beta (pos only)")


                    elif fusion_base == "composite_v4surr":
                        # COMPOSITE (harmonisiert b): links v4_sym, rechts Surrealizer-Dekonstruktion.
                        #   CLIP = L+G eine Gewichtung; pooled = cat(L,G) UNANGETASTET (harmonisiert).
                        #   a<=0: w_clip=1,   w_t5=|a|   (CLIP-Anker fest, T5 verstaerkt)
                        #   a>0 : w_clip=1-a, w_t5=a     (CLIP verblasst->invertiert, T5 waechst)
                        #   w_t5=|a| durchgehend; nahtlos bei a=0 (w_clip=1, w_t5=0). Tail x w_t5.
                        a = alpha_factor
                        w_t5 = abs(a)
                        w_clip = 1.0 if a <= 0.0 else (1.0 - a)
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        wvec = torch.ones(clip_interp.shape[-1], device=clip_interp.device, dtype=clip_interp.dtype)
                        wvec[0:768] = w_clip
                        wvec[768:2048] = w_clip
                        fused_core = clip_interp * wvec + w_t5 * t5_interp
                        fused_ext = w_t5 * t5_remainder
                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)
                        logger.info(f"[FUSION:composite_v4surr] alpha={a:.3f} w_clip={w_clip:.3f} w_t5={w_t5:.3f}")


                    elif fusion_base in ("push_t5only", "push_negclip"):
                        # F3-ZERLEGUNG (Folge-Reihe 2026-07-03): legacy-Push a*(T5-CLIP) in seine
                        # Komponenten zerlegt. Richtung = reine Komponente (+T5 bzw. -CLIP), pro
                        # Token normiert; per-Token-NORM exakt an den legacy-Push angepasst
                        # (E1-Methodik, gerichtet statt zufaellig). Tail = T5 x1 (identisch legacy).
                        # Rechnung in fp32 (a*75-Normen overflowen fp16-Zwischensummen), Cast zurueck.
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        push32 = (alpha_factor * (t5_interp.float() - clip_interp.float()))
                        push_norms = push32.norm(dim=-1, keepdim=True)
                        if fusion_base == "push_t5only":
                            d = t5_interp.float()
                        else:
                            d = -clip_interp.float()
                        d = d / d.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                        fused_core = (clip_interp.float() + d * push_norms).to(clip_interp.dtype)
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                    elif fusion_base == "random_matched":
                        # E1-KONTROLLE (Nacht-Reihe 2026-07-03): Push-RICHTUNG randomisiert,
                        # per-Token-NORM exakt an den legacy-Push angepasst.
                        #   legacy:  fused_i = clip_i + a*(t5_i - clip_i)   (Push p_i = a*(t5_i - clip_i))
                        #   hier:    fused_i = clip_i + r_i * ||p_i||,  r_i isotrop (Einheitssphaere, 4096d)
                        #   Tail = T5 x1 (identisch legacy). Deterministisch via rng=<seed> (CPU-Generator).
                        #   band=clip beschraenkt r vor der Normierung auf Dims 0:2048 (CLIP-Band).
                        #   Rechnung in fp32 (Norm eines a*75-Push overflowt fp16-Zwischensummen), Cast zurueck.
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        push32 = (alpha_factor * (t5_interp.float() - clip_interp.float()))
                        push_norms = push32.norm(dim=-1, keepdim=True)
                        rng_seed = int(fs_opts.get('rng', '1'))
                        g_cpu = torch.Generator(device='cpu').manual_seed(rng_seed)
                        r = torch.randn(clip_interp.shape, generator=g_cpu, dtype=torch.float32)
                        if fs_opts.get('band') == 'clip':
                            r[..., 2048:] = 0.0
                        r = r / r.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                        r = r.to(device=clip_interp.device)
                        fused_core = (clip_interp.float() + r * push_norms).to(clip_interp.dtype)
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                        logger.info(
                            f"[FUSION:random_matched] alpha={alpha_factor:.3f} rng={rng_seed} "
                            f"band={fs_opts.get('band', 'full')} push_norm mean={push_norms.mean().item():.2f} "
                            f"max={push_norms.max().item():.2f}"
                        )

                    elif fusion_base == "random_shuffled":
                        # E1-KONTROLLE (Nacht-Reihe 2026-07-03): ECHTER legacy-Push, aber die
                        # Token-Zuordnung ist permutiert — gleiches Vektor-SET, zerstoerte
                        # Ausrichtung Token<->Push. Tail = T5 x1. Deterministisch via rng=<seed>.
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        push = alpha_factor * (t5_interp - clip_interp)
                        rng_seed = int(fs_opts.get('rng', '1'))
                        g_cpu = torch.Generator(device='cpu').manual_seed(rng_seed)
                        perm = torch.randperm(push.shape[1], generator=g_cpu)
                        fused_core = clip_interp + push[:, perm, :]
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                        logger.info(
                            f"[FUSION:random_shuffled] alpha={alpha_factor:.3f} rng={rng_seed} "
                            f"perm_head={perm[:6].tolist()}"
                        )

                    elif fusion_base == "slerp":
                        # Legacy's operands and legacy's tail; the core is
                        # interpolated on the sphere.
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]

                        fused_part = slerp_tokens(clip_interp, t5_interp, alpha_factor)
                        fused_embeds = torch.cat([fused_part, t5_remainder], dim=1)

                        logger.info(
                            f"[FUSION:slerp] \u03b1={alpha_factor}, SLERP {interp_len}t, "
                            f"append {t5_len - interp_len}t unchanged"
                        )

                    elif fusion_base == "three_factor":
                        # Folge-Reihe M (2026-09-14): the three factors of the schema
                        # (ai4artsed_research, SCHEMA_surrealizer_split_and_combine
                        # _2026-09-14.md, section 4). CLIP rows 0..76: a*clip + b*t5,
                        # paired by row number; the T5 rows below them: c*t5, either
                        # all 512 (t5=full: the head twice, in the mix and as rows of
                        # its own) or rows 77.. (t5=tail: legacy's layout). Computed
                        # in the tensors' own dtype, as legacy and serial are, so that
                        # a=1-alpha, b=alpha, c=1, t5=tail reproduces legacy's cell
                        # bit for bit. alpha_factor is not read here.
                        _fa = float(fs_opts['a'])
                        _fb = float(fs_opts['b'])
                        _fc = float(fs_opts['c'])
                        # Folge-Reihe N (2026-09-16): shift=k puts k zero rows before
                        # T5's row 0, so that CLIP row i pairs with T5 row i-k (a
                        # dummy value at 0, the first word onto the first word
                        # instead of onto the start mark). The block below
                        # follows the shifted sequence: under t5=tail it starts at
                        # T5's row 77-k. shift absent or 0 is the arithmetic of
                        # Reihe M, unchanged.
                        _shift = int(fs_opts.get('shift') or 0)
                        t5_src = t5_embeds
                        if _shift:
                            t5_src = torch.cat([torch.zeros_like(t5_embeds[:, :_shift, :]), t5_embeds], dim=1)
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_src[:, :interp_len, :]
                        fused_core = _fa * clip_interp + _fb * t5_interp
                        t5_block = t5_src if fs_opts['t5'] == 'full' else t5_src[:, interp_len:, :]
                        fused_embeds = torch.cat([fused_core, _fc * t5_block], dim=1)
                        logger.info(
                            f"[FUSION:three_factor] a={_fa:.3f} b={_fb:.3f} c={_fc:.3f} "
                            f"t5={fs_opts['t5']} shift={_shift} core {interp_len}t, T5 block {t5_block.shape[1]}t"
                        )

                    elif fusion_base == "serial":
                        # Folge-Reihe I (2026-09-13): the stock layout of SD3 -- CLIP's
                        # 77 positions and T5's N positions side by side (Esser et al.
                        # 2024, B.2) -- with the CLIP core alone weighted by (1 - alpha).
                        # No T5 share on the CLIP positions. alpha=0 is the platform's
                        # own conditioning (t5len 512); alpha=1 is the core zeroed (the
                        # training's "CLIP dropped", pooled kept unless pooled=zero);
                        # alpha>1 negates the core.
                        clip_interp = clip_padded[:, :interp_len, :]
                        fused_core = (1.0 - alpha_factor) * clip_interp
                        fused_embeds = torch.cat([fused_core, t5_embeds], dim=1)
                        logger.info(
                            f"[FUSION:serial] alpha={alpha_factor:.3f} core {interp_len}t x(1-alpha), "
                            f"T5 {t5_len}t appended serially"
                        )

                    elif fusion_base == "push_negmu":
                        # Folge-Reihe I: one direction for every position, the negated
                        # mean of the CLIP content tokens of the battery (file via
                        # mu=<path>, 4096 floats, encoder space); per-token norm as
                        # legacy's push, tail x1, float32 and cast back (as push_negclip).
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        _mu = torch.load(fs_opts['mu'], map_location='cpu').float().reshape(-1)
                        if _mu.numel() != clip_interp.shape[-1]:
                            raise ValueError(
                                f"push_negmu: mu has {_mu.numel()} dims, expected {clip_interp.shape[-1]}"
                            )
                        d = (-_mu / _mu.norm().clamp(min=1e-8)).to(device=clip_interp.device)
                        push_norms = (
                            alpha_factor * (t5_interp.float() - clip_interp.float())
                        ).norm(dim=-1, keepdim=True)
                        fused_core = (clip_interp.float() + d * push_norms).to(clip_interp.dtype)
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                        logger.info(
                            f"[FUSION:push_negmu] alpha={alpha_factor:.3f} mu={fs_opts['mu']} "
                            f"push_norm mean={push_norms.mean().item():.2f}"
                        )

                    elif fusion_base == "legacy_dirnorm":
                        # Folge-Reihe I: legacy's direction at alpha dir=<a>, legacy's
                        # per-token norm at alpha norm=<b>; tail x1; float32, cast back.
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]
                        _a = float(fs_opts['dir'])
                        _b = float(fs_opts['norm'])
                        _core_a = (1.0 - _a) * clip_interp.float() + _a * t5_interp.float()
                        _core_b = (1.0 - _b) * clip_interp.float() + _b * t5_interp.float()
                        _dir = _core_a / _core_a.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                        fused_core = (_dir * _core_b.norm(dim=-1, keepdim=True)).to(clip_interp.dtype)
                        fused_embeds = torch.cat([fused_core, t5_remainder], dim=1)
                        logger.info(f"[FUSION:legacy_dirnorm] dir alpha={_a:.3f} norm alpha={_b:.3f}")

                    else:
                        # Legacy: LERP first 77, append T5 remainder unchanged.
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]

                        fused_part = (1.0 - alpha_factor) * clip_interp + alpha_factor * t5_interp
                        fused_embeds = torch.cat([fused_part, t5_remainder], dim=1)

                        logger.info(
                            f"[FUSION:legacy] α={alpha_factor}, LERP {interp_len}t, "
                            f"append {t5_len - interp_len}t unchanged"
                        )

                    # Folge-Reihe I (2026-09-13): position classes after the strategy.
                    # pos0=keep|only|random acts on position 0 (the BOS state, the same
                    # vector for every prompt); fuse_only=<classes> (bos, content, eos,
                    # pads) sets every position outside the named classes back to the
                    # CLIP state. Both act on both passes.
                    _pos0 = fs_opts.get('pos0')
                    _fuse_only = fs_opts.get('fuse_only')
                    if _pos0 or _fuse_only:
                        _core = fused_embeds[:, :interp_len, :].clone()
                        _clip_core = clip_padded[:, :interp_len, :].to(_core.dtype)
                        if _fuse_only:
                            _ids = pipe.tokenizer(
                                clip_text, padding="max_length", max_length=pipe.tokenizer_max_length,
                                truncation=True, return_tensors="pt",
                            ).input_ids[0]
                            _eos = int((_ids == pipe.tokenizer.eos_token_id).nonzero()[0])
                            _classes = {c.strip() for c in _fuse_only.split(',') if c.strip()}
                            _keep = torch.zeros(interp_len, dtype=torch.bool, device=_core.device)
                            if 'bos' in _classes:
                                _keep[0] = True
                            if 'content' in _classes and _eos > 1:
                                _keep[1:_eos] = True
                            if 'eos' in _classes:
                                _keep[_eos] = True
                            if 'pads' in _classes and _eos + 1 < interp_len:
                                _keep[_eos + 1:] = True
                            _core[:, ~_keep, :] = _clip_core[:, ~_keep, :]
                        if _pos0 == 'keep':
                            _core[:, 0, :] = _clip_core[:, 0, :]
                        elif _pos0 == 'only':
                            _core[:, 1:, :] = _clip_core[:, 1:, :]
                        elif _pos0 == 'random':
                            _g = torch.Generator(device='cpu').manual_seed(int(fs_opts.get('rng', '1')))
                            _r = torch.randn(_core.shape[-1], generator=_g, dtype=torch.float32)
                            _r = (_r / _r.norm()).to(device=_core.device)
                            _n0 = (
                                alpha_factor * (t5_embeds[:, 0, :].float() - clip_padded[:, 0, :].float())
                            ).norm(dim=-1, keepdim=True)
                            _core[:, 0, :] = (clip_padded[:, 0, :].float() + _r * _n0).to(_core.dtype)
                        fused_embeds = torch.cat([_core, fused_embeds[:, interp_len:, :]], dim=1)
                        logger.info(f"[FUSION:classes] pos0={_pos0} fuse_only={_fuse_only}")

                    return fused_embeds, pooled

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    if loras:
                        self._apply_loras(pipe, loras)
                    try:
                        # Effective T5 prompt: expanded if provided, else original
                        effective_t5_prompt = t5_prompt if t5_prompt else prompt

                        # The original fusion is defined by its TWO texts. Falling
                        # back to one for both encoders is the exact defect this
                        # branch was built to end -- it would still produce an
                        # image, and the image would be attributed to a mechanism
                        # that did not run. So it stops here instead.
                        if fusion_base == "original" and not (t5_prompt or "").strip():
                            raise ValueError(
                                "original fusion needs its own T5 text; "
                                "one prompt for both encoders is a different mechanism"
                            )

                        # Both passes run at the longest of the two T5 texts, decided
                        # here rather than by whichever is fused first. Letting the
                        # positive set it truncated a negative that happened to be
                        # longer -- silently, and diffusers' own warning would have
                        # named the wrong span. Padding the shorter side costs pad
                        # tokens; cutting the longer one costs words.
                        if fusion_base in ("original", "original_cg"):
                            _neg_for_len = negative_prompt if negative_prompt else ""
                            _original_t5_len["n"] = max(
                                77,
                                len(pipe.tokenizer_3(
                                    effective_t5_prompt, padding=False, truncation=False
                                ).input_ids),
                                len(pipe.tokenizer_3(
                                    _neg_for_len, padding=False, truncation=False
                                ).input_ids),
                            )

                        # Fuse positive prompt (CLIP-L gets original, T5 gets expanded)
                        pos_embeds, pos_pooled = _fuse_prompt(
                            prompt, effective_t5_prompt, pooled_text=pooled_prompt
                        )

                        # Free cached CUDA memory from pos encoding before neg pass
                        torch.cuda.empty_cache()

                        # Fuse negative prompt (no expansion — same text for both);
                        # "neg=alpha0" runs it at alpha 0 (Folge-Reihe I, 2026-09-13).
                        neg_text = negative_prompt if negative_prompt else ""
                        neg_embeds, neg_pooled = _fuse_prompt(
                            neg_text, neg_text,
                            alpha_override=0.0 if fs_opts.get('neg') == 'alpha0' else None,
                        )

                        logger.info(
                            f"[DIFFUSERS-FUSION] strategy={fusion_strategy}, alpha={alpha_factor}, "
                            f"shape={pos_embeds.shape}"
                        )

                        # Folge-Reihe I (2026-09-13): cfg_interval=<a>,<b> keeps the
                        # guidance weight only in the steps a <= i < b (0-based); outside
                        # it the weight is 1 (+1e-6, so the batch stays doubled).
                        _cfg_interval = None
                        if fs_opts.get('cfg_interval'):
                            _ci = [int(_x) for _x in fs_opts['cfg_interval'].split(',')]
                            _cfg_interval = (_ci[0], _ci[1])
                        _hook_state = {"step": 0}

                        def fusion_step_callback(pipe_inst, step, timestep, callback_kwargs):
                            _generation_progress["step"] = step + 1
                            _generation_progress["total_steps"] = steps
                            _hook_state["step"] = step + 1
                            if _cfg_interval is not None:
                                _nxt = step + 1
                                pipe_inst._guidance_scale = (
                                    cfg_scale if _cfg_interval[0] <= _nxt < _cfg_interval[1] else 1.0 + 1e-6
                                )
                            # E4 Stufen-Lokalisierung (Nacht-Reihe 2026-07-03): Latent-Statistik
                            # jeden Schritt + VAE-Decodes an angeforderten Schritten (cap/capdir).
                            if cap_dir:
                                try:
                                    _lats = callback_kwargs.get("latents")
                                    if _lats is not None:
                                        _lf = _lats.detach().float()
                                        _stats = {
                                            "step": step + 1,
                                            "timestep": float(timestep),
                                            "ch_mean": [round(float(_x), 5) for _x in _lf.mean(dim=(0, 2, 3))],
                                            "ch_std": [round(float(_x), 5) for _x in _lf.std(dim=(0, 2, 3))],
                                            "absmax": round(float(_lf.abs().max()), 4),
                                        }
                                        with open(_os.path.join(cap_dir, "latent_stats.jsonl"), "a") as _fh:
                                            _fh.write(_json.dumps(_stats) + "\n")
                                        if (step + 1) in cap_steps:
                                            _vae = pipe_inst.vae
                                            _lat = _lats.detach().to(_vae.dtype)
                                            _lat = _lat / _vae.config.scaling_factor + _vae.config.shift_factor
                                            with torch.no_grad():
                                                _dec = _vae.decode(_lat).sample
                                            _pil = pipe_inst.image_processor.postprocess(_dec, output_type="pil")[0]
                                            _pil.resize((512, 512)).save(
                                                _os.path.join(cap_dir, f"step_{step + 1:02d}.jpg"), quality=90
                                            )
                                            del _dec, _lat
                                            torch.cuda.empty_cache()
                                except Exception as _cap_e:
                                    logger.warning(f"[FUSION-CAP] step {step + 1}: {_cap_e}")
                            if callback:
                                try:
                                    callback(step, steps, callback_kwargs.get("latents"))
                                except Exception as e:
                                    logger.warning(f"[DIFFUSERS-FUSION] Callback error: {e}")
                            return callback_kwargs

                        # Build generation kwargs — all 4 embedding tensors bypass encode_prompt
                        gen_kwargs = {
                            "prompt_embeds": pos_embeds,
                            "negative_prompt_embeds": neg_embeds,
                            "pooled_prompt_embeds": pos_pooled,
                            "negative_pooled_prompt_embeds": neg_pooled,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": (
                                cfg_scale
                                if _cfg_interval is None or _cfg_interval[0] <= 0 < _cfg_interval[1]
                                else 1.0 + 1e-6
                            ),
                            "generator": generator,
                            "max_sequence_length": 512,
                            "callback_on_step_end": fusion_step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }

                        # Folge-Reihe I: hook=textstream records, per block and step, the
                        # mean cosine between the text stream's input and output of the
                        # block (positive half of the batch), core and tail apart.
                        _hook_handles = []
                        if fs_opts.get('hook') == 'textstream' and cap_dir:
                            def _mk_hook(_idx):
                                def _hook(_mod, _args, _kwargs, _out):
                                    try:
                                        _enc_in = _kwargs.get("encoder_hidden_states")
                                        _enc_out = _out[0] if isinstance(_out, tuple) else None
                                        if _enc_in is None or _enc_out is None:
                                            return
                                        _i = _enc_in[-1].float()
                                        _o = _enc_out[-1].float()
                                        _cs = F.cosine_similarity(_i, _o, dim=-1)
                                        _rec = {
                                            "step": _hook_state["step"] + 1, "block": _idx,
                                            "cos_core": round(float(_cs[:77].mean()), 5),
                                            "cos_tail": round(float(_cs[77:].mean()), 5) if _cs.shape[0] > 77 else None,
                                            "norm_in_core": round(float(_i[:77].norm(dim=-1).mean()), 3),
                                            "norm_out_core": round(float(_o[:77].norm(dim=-1).mean()), 3),
                                        }
                                        with open(_os.path.join(cap_dir, "textstream.jsonl"), "a") as _fh:
                                            _fh.write(_json.dumps(_rec) + "\n")
                                    except Exception as _he:
                                        logger.warning(f"[FUSION-HOOK] block {_idx}: {_he}")
                                return _hook
                            for _bi, _blk in enumerate(pipe.transformer.transformer_blocks):
                                _hook_handles.append(_blk.register_forward_hook(_mk_hook(_bi), with_kwargs=True))
                        try:
                            result = pipe(**gen_kwargs)
                        finally:
                            for _h in _hook_handles:
                                _h.remove()
                        return result.images[0]
                    finally:
                        if loras:
                            self._remove_loras(pipe)
                        _generation_progress["active"] = False

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert to PNG bytes
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

                logger.info(f"[DIFFUSERS-FUSION] Generated image: {len(image_bytes)} bytes")
                return image_bytes

            finally:
                self._model_in_use[model_id] -= 1
                # Fusion creates manual embeddings (CLIP-L, T5, fused tensors) outside
                # the pipeline's scope. Without explicit cleanup, these fragment VRAM
                # and cause OOM on the next call at full resolution.
                torch.cuda.empty_cache()

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS-FUSION] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def generate_image_with_decomposition(
        self,
        source_prompt: str,
        cells: Optional[list] = None,
        clip_l_prompt: Optional[str] = None,
        clip_l_step_bands: Optional[list] = None,
        clip_l_layer_bands: Optional[list] = None,
        clip_g_prompt: Optional[str] = None,
        clip_g_step_bands: Optional[list] = None,
        clip_g_layer_bands: Optional[list] = None,
        t5_prompt: Optional[str] = None,
        t5_step_bands: Optional[list] = None,
        t5_layer_bands: Optional[list] = None,
        alpha: float = 1.0,
        model_id: str = DEFAULT_MODEL_ID,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 5.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
    ) -> Optional[bytes]:
        """
        Decomposition Mode — 3×3×3 Intervention Space.

        Source prompt is encoded through all three SD3.5 encoders (CLIP-L, CLIP-G,
        T5-XXL) as the baseline. For each stream where an override prompt is
        provided, the corresponding slice of prompt_embeds is replaced during the
        configured step phases and layer bands.

        Stream override is realised via a delta approach:
          1. Build modified pre-projection prompt_embeds (source with one slice
             swapped for the override-encoded version).
          2. Project both base and modified through context_embedder once.
          3. delta_stream = override_post - base_post.
          4. Per-band-entry-block pre-hook adds (alpha * sum-of-active-deltas)
             to encoder_hidden_states once per step when the (step_phase ×
             layer_band) cell is active. Injection at the band's first block
             propagates through subsequent blocks of that band via joint
             attention — avoiding per-block accumulation that would scale
             intervention strength with band width.

        Bypasses encode_prompt by passing pre-computed embeddings to pipe(),
        identical to the Surrealizer pattern. CFG-doubling is handled inside the
        hook (batch is [negative; positive] — override is applied to the positive
        half only).

        Args:
            source_prompt: baseline prompt for all three encoders.
            <stream>_prompt: optional override per stream. None = baseline only.
            <stream>_step_bands: subset of {'composition','semantics','detail'},
                                 default = all.
            <stream>_layer_bands: subset of {'shallow','middle','deep'},
                                  default = all.
            alpha: blend strength in [-1.0, 1.0]. 1.0 = full delta applied.
            Standard image params: model_id, negative_prompt, width, height,
                                   steps, cfg_scale, seed, callback.

        Returns:
            PNG image bytes, or None on failure.
        """
        try:
            import torch
            import io

            all_step_bands = list(DECOMP_STEP_BANDS.keys())
            all_layer_bands = list(DECOMP_LAYER_BANDS.keys())

            def _validate_bands(bands, valid_set, name):
                if bands is None:
                    return None
                invalid = set(bands) - valid_set
                if invalid:
                    raise ValueError(
                        f"{name}: invalid bands {invalid}; valid: {sorted(valid_set)}"
                    )
                return list(bands)

            clip_l_step_bands  = _validate_bands(clip_l_step_bands,  DECOMP_VALID_STEP_BANDS,  "clip_l_step_bands")  or all_step_bands
            clip_l_layer_bands = _validate_bands(clip_l_layer_bands, DECOMP_VALID_LAYER_BANDS, "clip_l_layer_bands") or all_layer_bands
            clip_g_step_bands  = _validate_bands(clip_g_step_bands,  DECOMP_VALID_STEP_BANDS,  "clip_g_step_bands")  or all_step_bands
            clip_g_layer_bands = _validate_bands(clip_g_layer_bands, DECOMP_VALID_LAYER_BANDS, "clip_g_layer_bands") or all_layer_bands
            t5_step_bands      = _validate_bands(t5_step_bands,      DECOMP_VALID_STEP_BANDS,  "t5_step_bands")      or all_step_bands
            t5_layer_bands     = _validate_bands(t5_layer_bands,     DECOMP_VALID_LAYER_BANDS, "t5_layer_bands")     or all_layer_bands

            alpha = max(-1.0, min(1.0, float(alpha)))

            # --- Normalize cells: explicit list takes precedence; else expand legacy
            # per-stream + bands into the same flat cells representation.
            normalized_cells = []  # list of {"step", "layer", "stream", "prompt"}

            if cells is not None and len(cells) > 0:
                # Explicit cells input — validate each entry
                for i, cell in enumerate(cells):
                    if not isinstance(cell, dict):
                        raise ValueError(f"cells[{i}] must be a dict, got {type(cell)}")
                    step = cell.get('step')
                    layer = cell.get('layer')
                    stream = cell.get('stream')
                    prompt = cell.get('prompt')
                    if step not in DECOMP_VALID_STEP_BANDS:
                        raise ValueError(f"cells[{i}].step={step!r}; valid: {sorted(DECOMP_VALID_STEP_BANDS)}")
                    if layer not in DECOMP_VALID_LAYER_BANDS:
                        raise ValueError(f"cells[{i}].layer={layer!r}; valid: {sorted(DECOMP_VALID_LAYER_BANDS)}")
                    if stream not in DECOMP_VALID_STREAMS:
                        raise ValueError(f"cells[{i}].stream={stream!r}; valid: {sorted(DECOMP_VALID_STREAMS)}")
                    if not prompt or not str(prompt).strip():
                        # Empty prompt = inactive cell — skip silently
                        continue
                    normalized_cells.append({
                        'step': step, 'layer': layer,
                        'stream': stream, 'prompt': str(prompt),
                    })
            else:
                # Legacy expansion: per-stream prompt × step_bands × layer_bands
                legacy_streams = (
                    ('clip_l', clip_l_prompt, clip_l_step_bands, clip_l_layer_bands),
                    ('clip_g', clip_g_prompt, clip_g_step_bands, clip_g_layer_bands),
                    ('t5',     t5_prompt,     t5_step_bands,     t5_layer_bands),
                )
                for stream, prompt, step_bands, layer_bands in legacy_streams:
                    if not prompt:
                        continue
                    for s in step_bands:
                        for l in layer_bands:
                            normalized_cells.append({
                                'step': s, 'layer': l,
                                'stream': stream, 'prompt': prompt,
                            })

            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if not hasattr(pipe, 'transformer') or not hasattr(pipe.transformer, 'transformer_blocks'):
                    logger.error("[DIFFUSERS-DECOMP] Pipeline missing transformer.transformer_blocks")
                    return None
                if not hasattr(pipe.transformer, 'context_embedder'):
                    logger.error("[DIFFUSERS-DECOMP] Pipeline missing transformer.context_embedder")
                    return None

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(
                    f"[DIFFUSERS-DECOMP] seed={seed}, steps={steps}, size={width}x{height}, "
                    f"active_cells={len(normalized_cells)}, alpha={alpha}"
                )

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    device = pipe._execution_device
                    hook_handles = []

                    hook_state = {
                        "step": 0,
                        "total_steps": steps,
                        "alpha": alpha,
                    }

                    try:
                        # Encode source through all three encoders (baseline)
                        with torch.no_grad():
                            (
                                src_pos_embeds,
                                src_neg_embeds,
                                src_pos_pooled,
                                src_neg_pooled,
                            ) = pipe.encode_prompt(
                                prompt=source_prompt,
                                prompt_2=source_prompt,
                                prompt_3=source_prompt,
                                negative_prompt=negative_prompt or None,
                                negative_prompt_2=negative_prompt or None,
                                negative_prompt_3=negative_prompt or None,
                                device=device,
                                num_images_per_prompt=1,
                                do_classifier_free_guidance=(cfg_scale > 1.0),
                                max_sequence_length=512,
                            )

                        # Pre-compute deltas: each unique (stream, prompt) pair encoded once.
                        # Then map per-cell (step, layer, stream) -> delta tensor.
                        cell_deltas = {}  # (step, layer, stream) -> delta tensor

                        if normalized_cells:
                            ce = pipe.transformer.context_embedder
                            unique_overrides = {}  # (stream, prompt_text) -> delta tensor
                            with torch.no_grad():
                                base_post = ce(src_pos_embeds)

                                for cell in normalized_cells:
                                    stream_name = cell['stream']
                                    override_prompt = cell['prompt']
                                    key = (stream_name, override_prompt)
                                    if key not in unique_overrides:
                                        tok_sl, dim_sl = DECOMP_STREAM_SLICES[stream_name]
                                        modified_pre = src_pos_embeds.clone()

                                        if stream_name == 'clip_l':
                                            ovr, _ = pipe._get_clip_prompt_embeds(
                                                prompt=override_prompt, device=device,
                                                num_images_per_prompt=1, clip_model_index=0,
                                            )
                                            modified_pre[:, tok_sl, dim_sl] = ovr.to(modified_pre.dtype)

                                        elif stream_name == 'clip_g':
                                            ovr, _ = pipe._get_clip_prompt_embeds(
                                                prompt=override_prompt, device=device,
                                                num_images_per_prompt=1, clip_model_index=1,
                                            )
                                            modified_pre[:, tok_sl, dim_sl] = ovr.to(modified_pre.dtype)

                                        elif stream_name == 't5':
                                            ovr = pipe._get_t5_prompt_embeds(
                                                prompt=override_prompt, num_images_per_prompt=1,
                                                max_sequence_length=512, device=device,
                                            )
                                            modified_pre[:, tok_sl, dim_sl] = ovr.to(modified_pre.dtype)

                                        override_post = ce(modified_pre)
                                        unique_overrides[key] = (override_post - base_post).detach()
                                        del modified_pre, override_post

                                    cell_deltas[(cell['step'], cell['layer'], stream_name)] = unique_overrides[key]

                                del base_post
                            torch.cuda.empty_cache()

                        if cell_deltas:
                            blocks = pipe.transformer.transformer_blocks
                            num_blocks = len(blocks)
                            entry_blocks = sorted({lo for (lo, _) in DECOMP_LAYER_BANDS.values()})
                            logger.info(
                                f"[DIFFUSERS-DECOMP] Installing entry-block hooks on blocks "
                                f"{entry_blocks} (of {num_blocks} total) for {len(cell_deltas)} "
                                f"cells across "
                                f"{len(set((s,l) for (s,l,_) in cell_deltas))} (step,layer) positions"
                            )

                            # Pre-compute block_idx -> layer_band lookup (constant across steps)
                            block_to_band = [None] * num_blocks
                            for i in range(num_blocks):
                                for band_name, (lo, hi) in DECOMP_LAYER_BANDS.items():
                                    if lo <= i < hi:
                                        block_to_band[i] = band_name
                                        break

                            def make_block_hook(block_idx):
                                layer_band = block_to_band[block_idx]
                                if layer_band is None:
                                    # Block outside all bands — never modify
                                    return None
                                band_lo, _ = DECOMP_LAYER_BANDS[layer_band]
                                if block_idx != band_lo:
                                    # Apply-delta-once-per-cell: inject only at the band's
                                    # entry block. The modification propagates through the
                                    # band's remaining blocks via joint attention, so each
                                    # active cell contributes exactly one addition per step
                                    # regardless of band width.
                                    return None

                                def pre_hook(module, args, kwargs):
                                    encoder_hs = kwargs.get('encoder_hidden_states')
                                    if encoder_hs is None and len(args) >= 2:
                                        encoder_hs = args[1]
                                    if encoder_hs is None:
                                        return None

                                    step_frac = hook_state["step"] / max(1, hook_state["total_steps"])
                                    # Find current step phase
                                    current_phase = None
                                    for phase_name, (lo, hi) in DECOMP_STEP_BANDS.items():
                                        if lo <= step_frac < hi:
                                            current_phase = phase_name
                                            break
                                    if current_phase is None:
                                        return None

                                    # Look up deltas for this (phase, layer_band, stream) cell, all three streams
                                    active_delta = None
                                    for stream_name in ('clip_l', 'clip_g', 't5'):
                                        d = cell_deltas.get((current_phase, layer_band, stream_name))
                                        if d is None:
                                            continue
                                        active_delta = d if active_delta is None else active_delta + d

                                    if active_delta is None:
                                        return None

                                    delta_scaled = active_delta * hook_state["alpha"]
                                    b_runtime = encoder_hs.shape[0]
                                    b_delta = delta_scaled.shape[0]

                                    delta_target = delta_scaled.to(dtype=encoder_hs.dtype, device=encoder_hs.device)

                                    if b_runtime == b_delta:
                                        modified = encoder_hs + delta_target
                                    elif b_runtime == 2 * b_delta:
                                        # CFG batch layout: [negative; positive]
                                        # Apply override only to positive half
                                        modified = encoder_hs.clone()
                                        modified[b_delta:] = encoder_hs[b_delta:] + delta_target
                                    else:
                                        return None

                                    new_kwargs = dict(kwargs)
                                    new_kwargs['encoder_hidden_states'] = modified
                                    return args, new_kwargs
                                return pre_hook

                            for i, block in enumerate(blocks):
                                hook_fn = make_block_hook(i)
                                if hook_fn is None:
                                    continue
                                handle = block.register_forward_pre_hook(
                                    hook_fn, with_kwargs=True
                                )
                                hook_handles.append(handle)

                        def decomp_step_callback(pipe_instance, step, timestep, callback_kwargs):
                            # Fires AFTER step N completes → set state for the NEXT forward pass
                            hook_state["step"] = step + 1
                            _generation_progress["step"] = step + 1
                            _generation_progress["total_steps"] = steps
                            if callback:
                                try:
                                    callback(step, steps, callback_kwargs.get("latents"))
                                except Exception as e:
                                    logger.warning(f"[DIFFUSERS-DECOMP] Callback error: {e}")
                            return callback_kwargs

                        gen_kwargs = {
                            "prompt_embeds": src_pos_embeds,
                            "negative_prompt_embeds": src_neg_embeds,
                            "pooled_prompt_embeds": src_pos_pooled,
                            "negative_pooled_prompt_embeds": src_neg_pooled,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "max_sequence_length": 512,
                            "callback_on_step_end": decomp_step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }

                        result = pipe(**gen_kwargs)
                        return result.images[0]

                    finally:
                        for h in hook_handles:
                            try:
                                h.remove()
                            except Exception as e:
                                logger.warning(f"[DIFFUSERS-DECOMP] Hook removal error: {e}")
                        _generation_progress["active"] = False

                image = await asyncio.to_thread(self._locked_generate, _generate)

                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

                logger.info(f"[DIFFUSERS-DECOMP] Generated image: {len(image_bytes)} bytes")
                return image_bytes

            finally:
                self._model_in_use[model_id] -= 1
                torch.cuda.empty_cache()

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS-DECOMP] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def generate_image_with_attention(
        self,
        prompt: str,
        model_id: str = DEFAULT_MODEL_ID,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        capture_layers: Optional[list] = None,
        capture_every_n_steps: int = 5,
        callback: Optional[Callable[[int, int, Any], None]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate an image with attention map capture for Attention Cartography.

        Installs custom attention processors on selected transformer blocks,
        generates the image, collects text→image attention maps at specified
        timesteps and layers, then restores original processors.

        Args:
            prompt: Positive prompt
            model_id: Model to use
            negative_prompt: Negative prompt
            width/height: Image dimensions
            steps: Number of inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            capture_layers: Transformer block indices to capture (default: [3, 9, 17])
            capture_every_n_steps: Capture attention every N steps
            callback: Step callback for progress

        Returns:
            Dict with keys:
            - image_base64: base64 encoded PNG
            - tokens: list of token strings
            - attention_maps: {step_N: {layer_M: [[...]]}}
            - spatial_resolution: [h, w] of attention map grid
            - image_resolution: [h, w] of generated image
            - seed: actual seed used
        """
        try:
            import torch
            import io
            import base64

            from services.attention_processors_sd3 import (
                AttentionMapStore,
                install_attention_capture,
                restore_attention_processors,
            )

            if capture_layers is None:
                capture_layers = [3, 9, 17]

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                # Compute which steps to capture
                capture_steps = list(range(0, steps, capture_every_n_steps))
                if (steps - 1) not in capture_steps:
                    capture_steps.append(steps - 1)

                # Pre-compute CLIP-L token positions for attention map truncation.
                # SD3.5's encoder_hidden_states has ~589 text columns (77 CLIP + 512 T5).
                # We only need columns for actual word tokens (not BOS/EOS/PAD), reducing
                # JSON from ~300MB to ~10MB.
                token_column_indices = None
                tokens = []
                word_groups = []  # [[0,1], [2], [3,4]] — subtoken indices per word
                # Both tokenizers, under the lock every other tokenizer call
                # takes: this is prepared before _locked_generate runs, so a
                # generation from another request is very likely in flight.
                with self._inference_lock:
                    tokenizer = pipe.tokenizer  # CLIP-L
                    if tokenizer is not None:
                        encoded = tokenizer(
                            prompt, padding=False, truncation=True,
                            max_length=77, return_tensors=None,
                        )
                        token_ids = encoded['input_ids']
                        token_column_indices = []
                        current_group = []
                        prev_raw = None
                        for pos, tid in enumerate(token_ids):
                            if tid in tokenizer.all_special_ids:
                                continue
                            token_idx = len(tokens)
                            token_column_indices.append(pos)
                            # CLIP BPE uses </w> suffix on word-FINAL subtokens
                            # (NOT leading-space like GPT-2)
                            raw = tokenizer.convert_ids_to_tokens(tid)
                            is_word_start = (
                                token_idx == 0
                                or (prev_raw is not None and prev_raw.endswith('</w>'))
                            )
                            # CLIP's BPE works on BYTES, so `convert_ids_to_tokens`
                            # hands back their placeholder form: "flaechen" arrives as
                            # "fl" + "\u00c3\u00a4" + "chen</w>" and reads as mojibake
                            # in the chip. `convert_tokens_to_string` runs the byte
                            # decoder over it and gives the word back.
                            try:
                                display = tokenizer.convert_tokens_to_string([raw])
                            except Exception:
                                display = raw.replace('</w>', '')
                            tokens.append(display)
                            if is_word_start and current_group:
                                word_groups.append(current_group)
                                current_group = []
                            current_group.append(token_idx)
                            prev_raw = raw
                        if current_group:
                            word_groups.append(current_group)
                        logger.info(
                            f"[DIFFUSERS-ATTENTION] CLIP-L: {len(tokens)} subtokens, "
                            f"{len(word_groups)} words, groups={word_groups}"
                        )

                    # T5-XXL tokenization (tokenizer_3 in SD3.5)
                    tokens_t5 = []
                    word_groups_t5 = []
                    t5_column_indices = []
                    tokenizer_t5 = getattr(pipe, 'tokenizer_3', None)
                    if tokenizer_t5 is not None:
                        encoded_t5 = tokenizer_t5(
                            prompt, padding=False, truncation=True,
                            max_length=512, return_tensors=None,
                        )
                        t5_ids = encoded_t5['input_ids']
                        pad_id = tokenizer_t5.pad_token_id
                        eos_id = tokenizer_t5.eos_token_id
                        current_group_t5 = []
                        for pos, tid in enumerate(t5_ids):
                            if tid == pad_id or tid == eos_id:
                                continue
                            t5_token_idx = len(tokens_t5)
                            # T5 columns start at offset 77 in the combined encoder_hidden_states
                            t5_column_indices.append(77 + pos)
                            # SentencePiece uses ▁ (U+2581) prefix as word-START marker
                            raw = tokenizer_t5.convert_ids_to_tokens(tid)
                            is_word_start = raw.startswith('\u2581')
                            display = raw.lstrip('\u2581')
                            tokens_t5.append(display)
                            if is_word_start and current_group_t5:
                                word_groups_t5.append(current_group_t5)
                                current_group_t5 = []
                            current_group_t5.append(t5_token_idx)
                        if current_group_t5:
                            word_groups_t5.append(current_group_t5)
                        logger.info(
                            f"[DIFFUSERS-ATTENTION] T5-XXL: {len(tokens_t5)} subtokens, "
                            f"{len(word_groups_t5)} words, groups={word_groups_t5}"
                        )

                # Combine CLIP-L + T5 column indices for the attention store
                combined_column_indices = (token_column_indices or []) + t5_column_indices

                # Create attention store
                store = AttentionMapStore(
                    capture_layers=capture_layers,
                    capture_steps=capture_steps,
                    text_column_indices=combined_column_indices if combined_column_indices else None,
                )

                logger.info(
                    f"[DIFFUSERS-ATTENTION] Generating: steps={steps}, size={width}x{height}, "
                    f"seed={seed}, capture_layers={capture_layers}, capture_steps={capture_steps}"
                )

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    # Install attention capture processors
                    original_processors = install_attention_capture(pipe, store, capture_layers)

                    try:
                        # Step callback to update store's current_step
                        # IMPORTANT: callback_on_step_end fires AFTER step N completes.
                        # We set current_step = step + 1 so the NEXT forward pass sees the right step.
                        # Step 0's forward pass uses the initial current_step=0 (set below).
                        def step_callback(pipe_instance, step, timestep, callback_kwargs):
                            store.current_step = step + 1
                            _generation_progress["step"] = step + 1
                            _generation_progress["total_steps"] = steps
                            if callback:
                                try:
                                    callback(step, steps, callback_kwargs.get("latents"))
                                except Exception as e:
                                    logger.warning(f"[DIFFUSERS-ATTENTION] Callback error: {e}")
                            return callback_kwargs

                        gen_kwargs = {
                            "prompt": prompt,
                            "negative_prompt": negative_prompt if negative_prompt else None,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "callback_on_step_end": step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }

                        # SD3.5: Set max_sequence_length for T5
                        if hasattr(pipe, 'tokenizer_3'):
                            gen_kwargs["max_sequence_length"] = 512

                        result = pipe(**gen_kwargs)
                        return result.images[0]
                    finally:
                        _generation_progress["active"] = False
                        # Always restore original processors
                        restore_attention_processors(pipe, original_processors, capture_layers)

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert image to base64
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                # tokens already computed above (pre-generation CLIP-L tokenization)

                # Compute spatial resolution (patch grid)
                # SD3.5 uses 2x2 patches → 1024/16 = 64 spatial positions per axis
                patch_size = 2  # SD3 latent patch size
                vae_scale = 8   # VAE downscale factor
                spatial_h = height // (vae_scale * patch_size)
                spatial_w = width // (vae_scale * patch_size)

                # Log attention map dimensions for debugging
                map_sample_key = next(iter(store.maps), None)
                if map_sample_key:
                    layer_sample = next(iter(store.maps[map_sample_key].values()), None)
                    if layer_sample:
                        logger.info(
                            f"[DIFFUSERS-ATTENTION] Map shape: [{len(layer_sample)}×{len(layer_sample[0]) if layer_sample else 0}] "
                            f"(image_tokens × text_tokens)"
                        )

                result = {
                    "image_base64": image_base64,
                    "tokens": tokens,
                    "word_groups": word_groups,
                    "tokens_t5": tokens_t5,
                    "word_groups_t5": word_groups_t5,
                    "clip_token_count": len(tokens),
                    "attention_maps": store.maps,
                    "spatial_resolution": [spatial_h, spatial_w],
                    "image_resolution": [height, width],
                    "seed": seed,
                    "capture_layers": capture_layers,
                    "capture_steps": capture_steps,
                }

                logger.info(
                    f"[DIFFUSERS-ATTENTION] Generated with attention: "
                    f"{len(store.maps)} timesteps captured, "
                    f"tokens={len(tokens)}, spatial={spatial_h}x{spatial_w}"
                )
                return result

            finally:
                self._model_in_use[model_id] -= 1

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS-ATTENTION] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_image_with_probing(
        self,
        prompt_a: str,
        prompt_b: str,
        encoder: str = "t5",
        transfer_dims: list = None,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> Optional[Dict[str, Any]]:
        """
        Feature Probing: analyze embedding differences between two prompts
        and optionally transfer selected dimensions.

        Phase 1 (transfer_dims=None): Encode both prompts, compute difference
        vector, generate image A. Returns image + probing analysis data.

        Phase 2 (transfer_dims provided): Copy selected dimensions from B→A,
        generate image with modified embedding (same seed for comparison).

        Args:
            prompt_a: Base prompt
            prompt_b: Comparison prompt
            encoder: Which encoder to probe ("clip_l", "clip_g", "t5")
            transfer_dims: Dimension indices to transfer (None = analysis only)
            negative_prompt: Negative prompt
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            model_id: Model to use

        Returns:
            Dict with image_base64, probing_data, seed
        """
        try:
            import torch
            import torch.nn.functional as F
            import io
            import base64
            from services.embedding_analyzer import (
                compute_dimension_differences,
                apply_dimension_transfer,
            )

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id):
                return {'error': f'Model loading failed for {model_id}'}

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Verify encoder access methods
                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[DIFFUSERS-PROBING] Pipeline missing encoder methods")
                    return {'error': 'Pipeline missing _get_clip_prompt_embeds or _get_t5_prompt_embeds'}

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                logger.info(
                    f"[DIFFUSERS-PROBING] encoder={encoder}, transfer={'yes' if transfer_dims else 'no'}, "
                    f"steps={steps}, size={width}x{height}, seed={seed}"
                )

                # --- The positions that actually carry the prompt ---
                # Both encoders pad to a fixed width: CLIP to 77, T5 to 512. A short
                # prompt fills a handful of positions and leaves the rest to the
                # encoder's response to padding — a response that differs between two
                # prompts without saying anything about how the prompts differ.
                # Ranking dimensions across the whole padded sequence lets that
                # response outvote the content, and with T5 it outnumbers it roughly a
                # hundred to one. The window below is the prefix the longer of the two
                # prompts fills, EOS included; both prompts share it so that A and B
                # are compared position for position.
                clip_max_length = getattr(pipe, 'tokenizer_max_length', None) or 77
                t5_max_length = 512  # mirrors max_sequence_length in the encode calls below

                def _filled_length(tokenizers, max_length: int) -> int:
                    """Longest prefix either prompt occupies on any of these tokenizers.

                    Padding is right-hand for CLIP and T5 alike, so what a prompt
                    fills is always a prefix and a (start, end) range describes it.
                    """
                    # Called before _locked_generate: same tokenizers, same lock.
                    with self._inference_lock:
                        return max(
                            min(
                                len(tok(text, padding=False, truncation=True,
                                        max_length=max_length).input_ids),
                                max_length,
                            )
                            for tok in tokenizers
                            for text in (prompt_a, prompt_b)
                        )

                try:
                    if encoder == "all":
                        # Two windows, not one. The composed sequence runs
                        # CLIP-L+CLIP-G over 0:77 and T5 over 77:589, so the CLIP
                        # padding sits in the middle of it.
                        clip_len = _filled_length((pipe.tokenizer, pipe.tokenizer_2), clip_max_length)
                        t5_len = _filled_length((pipe.tokenizer_3,), t5_max_length)
                        content_ranges = [(0, clip_len), (clip_max_length, clip_max_length + t5_len)]
                    elif encoder == "clip_l":
                        content_ranges = [(0, _filled_length((pipe.tokenizer,), clip_max_length))]
                    elif encoder == "clip_g":
                        content_ranges = [(0, _filled_length((pipe.tokenizer_2,), clip_max_length))]
                    else:  # t5
                        content_ranges = [(0, _filled_length((pipe.tokenizer_3,), t5_max_length))]
                except Exception as e:
                    # A pipeline can be assembled without one of the tokenizers. Fall
                    # back to the full padded sequence and say so, rather than report
                    # a window that was never applied.
                    logger.warning(
                        f"[DIFFUSERS-PROBING] token lengths unavailable "
                        f"({type(e).__name__}: {e}) — measuring over the full padded sequence"
                    )
                    content_ranges = None

                logger.info(f"[DIFFUSERS-PROBING] content window ({encoder}): {content_ranges}")

                def _generate():
                    device = pipe._execution_device
                    generator = torch.Generator(device=self.device).manual_seed(seed)

                    # --- Encode both prompts with the selected encoder ---
                    # _all_pooled_a only used for "all" mode
                    _all_pooled_a = None

                    if encoder == "all":
                        # Encode all three encoders for both prompts
                        clip_l_a, clip_l_pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_a, clip_g_pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_a = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_l_b, clip_l_pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_b, clip_g_pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_b = pipe._get_t5_prompt_embeds(
                            prompt=prompt_b, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        # Compose full prompt_embeds: [CLIP-L+CLIP-G padded to 4096, T5] along seq dim
                        clip_combined_a = F.pad(torch.cat([clip_l_a, clip_g_a], dim=-1), (0, 4096 - 2048))
                        clip_combined_b = F.pad(torch.cat([clip_l_b, clip_g_b], dim=-1), (0, 4096 - 2048))
                        embed_a = torch.cat([clip_combined_a, t5_a], dim=1)  # [1, 77+512, 4096]
                        embed_b = torch.cat([clip_combined_b, t5_b], dim=1)
                        # Prompt A's pooled summary. It is held fixed while dimensions
                        # are transferred, so the image difference comes from the selection.
                        _all_pooled_a = torch.cat([clip_l_pooled_a, clip_g_pooled_a], dim=-1)  # [1, 2048]
                        pooled_a = pooled_b = None
                        embed_dim_name = "All Encoders (CLIP-L+CLIP-G+T5)"
                    elif encoder == "clip_l":
                        embed_a, pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        embed_b, pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        embed_dim_name = "CLIP-L (768d)"
                    elif encoder == "clip_g":
                        embed_a, pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        embed_b, pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        embed_dim_name = "CLIP-G (1280d)"
                    else:  # t5
                        embed_a = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        embed_b = pipe._get_t5_prompt_embeds(
                            prompt=prompt_b, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        pooled_a = pooled_b = None
                        embed_dim_name = "T5-XXL (4096d)"

                    logger.info(
                        f"[DIFFUSERS-PROBING] Encoded: {embed_dim_name}, "
                        f"A shape={embed_a.shape}, B shape={embed_b.shape}"
                    )

                    # --- Compute difference vector ---
                    diff_data = compute_dimension_differences(
                        embed_a, embed_b, content_ranges=content_ranges
                    )

                    # --- Build the prompt_embeds for generation ---
                    transfer_stats = None
                    if transfer_dims is not None:
                        # Phase 2: modify embed_a with selected dims from embed_b
                        gen_embed, transfer_stats = apply_dimension_transfer(
                            embed_a, embed_b, transfer_dims, content_ranges=content_ranges
                        )
                        logger.info(f"[DIFFUSERS-PROBING] Transferred {len(transfer_dims)} dims from B→A")
                    else:
                        # Phase 1: generate with original embed_a
                        gen_embed = embed_a

                    # --- Prepare full embedding for SD3.5 pipeline ---
                    # SD3.5 expects prompt_embeds of shape [1, seq_len, 4096]
                    # composed of: CLIP-L(768) + CLIP-G(1280) padded to 4096, then T5(4096)
                    # concatenated along sequence dimension.
                    #
                    # "all" mode: gen_embed is already the full composed tensor
                    # Individual modes: compose from probed + non-probed encoders

                    if encoder == "all":
                        # gen_embed is already full [1, 589, 4096] composed embedding
                        prompt_embeds = gen_embed
                        # The pooled embedding stays with prompt A, whatever is
                        # transferred. It is a second, short summary vector next to the
                        # sequence the selection acts on; blending it in proportion to the
                        # number of transferred dimensions moved the image for a reason the
                        # instrument does not show, so the change on screen no longer came
                        # from the selected dimensions alone.
                        pooled_embeds = _all_pooled_a

                    elif encoder == "t5":
                        # Get CLIP embeddings normally
                        clip_l_embed, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_embed, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        # CLIP embeddings combined: [1, 77, 768+1280] → padded to 4096
                        clip_combined = torch.cat([clip_l_embed, clip_g_embed], dim=-1)  # [1, 77, 2048]
                        clip_combined = F.pad(clip_combined, (0, 4096 - clip_combined.shape[-1]))  # [1, 77, 4096]

                        # T5 is what we're probing — use gen_embed (original or modified)
                        t5_embed = gen_embed  # [1, seq_len, 4096]

                        # Combine: clip + t5
                        prompt_embeds = torch.cat([clip_combined, t5_embed], dim=1)
                        pooled_embeds = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)  # [1, 2048]

                    elif encoder == "clip_l":
                        # Get CLIP-G and T5 normally
                        clip_g_embed, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_embed = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )

                        # CLIP-L is what we're probing — use gen_embed (768d)
                        clip_combined = torch.cat([gen_embed, clip_g_embed], dim=-1)  # [1, 77, 2048]
                        clip_combined = F.pad(clip_combined, (0, 4096 - clip_combined.shape[-1]))  # [1, 77, 4096]

                        prompt_embeds = torch.cat([clip_combined, t5_embed], dim=1)
                        # Pooled: use original CLIP-L pooled (not modified — pooled is global, not per-dim)
                        pooled_embeds = torch.cat([pooled_a, clip_g_pooled], dim=-1)

                    else:  # clip_g
                        # Get CLIP-L and T5 normally
                        clip_l_embed, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        t5_embed = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )

                        # CLIP-G is what we're probing — use gen_embed (1280d)
                        clip_combined = torch.cat([clip_l_embed, gen_embed], dim=-1)  # [1, 77, 2048]
                        clip_combined = F.pad(clip_combined, (0, 4096 - clip_combined.shape[-1]))  # [1, 77, 4096]

                        prompt_embeds = torch.cat([clip_combined, t5_embed], dim=1)
                        # Pooled stays with A here too. Any transfer at all used to swap
                        # this vector to B wholesale, so a single selected dimension already
                        # dragged the whole summary across.
                        pooled_embeds = torch.cat([clip_l_pooled, pooled_a], dim=-1)

                    # --- Negative embeddings (encode normally) ---
                    neg_text = negative_prompt if negative_prompt else ""
                    neg_clip_l, neg_clip_l_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=0
                    )
                    neg_clip_g, neg_clip_g_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=1
                    )
                    neg_t5 = pipe._get_t5_prompt_embeds(
                        prompt=neg_text, num_images_per_prompt=1,
                        max_sequence_length=512, device=device
                    )
                    neg_clip_combined = torch.cat([neg_clip_l, neg_clip_g], dim=-1)
                    neg_clip_combined = F.pad(neg_clip_combined, (0, 4096 - neg_clip_combined.shape[-1]))
                    neg_prompt_embeds = torch.cat([neg_clip_combined, neg_t5], dim=1)
                    neg_pooled = torch.cat([neg_clip_l_pooled, neg_clip_g_pooled], dim=-1)

                    # --- Generate image ---
                    gen_kwargs = {
                        "prompt_embeds": prompt_embeds,
                        "negative_prompt_embeds": neg_prompt_embeds,
                        "pooled_prompt_embeds": pooled_embeds,
                        "negative_pooled_prompt_embeds": neg_pooled,
                        "width": width,
                        "height": height,
                        "num_inference_steps": steps,
                        "guidance_scale": cfg_scale,
                        "generator": generator,
                        "max_sequence_length": 512,
                    }

                    result = pipe(**gen_kwargs)
                    return result.images[0], diff_data, transfer_stats

                image, diff_data, transfer_stats = await asyncio.to_thread(
                    self._locked_generate, _generate
                )

                # Convert to base64
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                probing_data = {
                    'encoder': encoder,
                    'embed_dim': diff_data['embed_dim'],
                    **diff_data,
                }
                # content_positions arrives with diff_data; the ranges say WHERE
                # those positions are, which is what "all" mode needs to be read at
                # all — its window is split across two encoders.
                if content_ranges is not None:
                    probing_data['content_ranges'] = [[start, end] for start, end in content_ranges]

                if transfer_dims is not None:
                    probing_data['transferred_dims'] = transfer_dims
                    probing_data['num_transferred'] = len(transfer_dims)
                    if transfer_stats:
                        # How much of the A/B difference this selection accounts for.
                        probing_data.update(transfer_stats)

                logger.info(
                    f"[DIFFUSERS-PROBING] Done: embed_dim={diff_data['embed_dim']}, "
                    f"top diff={diff_data['top_values'][:3] if diff_data['top_values'] else 'none'}"
                )

                return {
                    'image_base64': image_base64,
                    'probing_data': probing_data,
                    'seed': seed,
                }

            finally:
                self._model_in_use[model_id] -= 1
                # Probing creates manual embeddings (up to 6 encoder passes for "all" mode)
                # outside the pipeline's scope. Cleanup prevents VRAM fragmentation.
                torch.cuda.empty_cache()

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS-PROBING] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}

    async def generate_image_with_algebra(
        self,
        prompt_a: str,
        prompt_b: str,
        prompt_c: str,
        encoder: str = "all",
        scale_sub: float = 1.0,
        scale_add: float = 1.0,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        model_id: str = DEFAULT_MODEL_ID,
        generate_reference: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Concept Algebra: A - scale_sub*B + scale_add*C on text encoder embeddings.

        Inspired by Mikolov's word2vec analogies (King - Man + Woman = Queen),
        applied to SD3.5 text encoder embeddings for image generation.

        Args:
            prompt_a: Base concept (e.g. "King on a throne")
            prompt_b: Concept to subtract (e.g. "Man")
            prompt_c: Concept to add (e.g. "Woman")
            encoder: Which encoder(s) to apply algebra on ("all", "clip_l", "clip_g", "t5")
            scale_sub: Scaling factor for subtraction
            scale_add: Scaling factor for addition
            negative_prompt: Negative prompt
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            model_id: Model to use
            generate_reference: Also generate image with original embed_a

        Returns:
            Dict with reference_image, result_image, algebra_data, seed
        """
        try:
            import torch
            import torch.nn.functional as F
            import io
            import base64
            from services.embedding_analyzer import apply_concept_algebra

            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[DIFFUSERS-ALGEBRA] Pipeline missing encoder methods")
                    return None

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                logger.info(
                    f"[DIFFUSERS-ALGEBRA] encoder={encoder}, scale_sub={scale_sub}, scale_add={scale_add}, "
                    f"steps={steps}, size={width}x{height}, seed={seed}"
                )

                def _encode_prompt(prompt_text, device):
                    """Encode a single prompt with the selected encoder."""
                    if encoder == "all":
                        clip_l, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5 = pipe._get_t5_prompt_embeds(
                            prompt=prompt_text, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_combined = F.pad(torch.cat([clip_l, clip_g], dim=-1), (0, 4096 - 2048))
                        embed = torch.cat([clip_combined, t5], dim=1)
                        pooled = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)
                        return embed, pooled
                    elif encoder == "clip_l":
                        embed, pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        return embed, pooled
                    elif encoder == "clip_g":
                        embed, pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        return embed, pooled
                    else:  # t5
                        embed = pipe._get_t5_prompt_embeds(
                            prompt=prompt_text, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        return embed, None

                def _compose_full_embedding(gen_embed, gen_pooled, device):
                    """Compose probed encoder embedding into full SD3.5 format."""
                    if encoder == "all":
                        return gen_embed, gen_pooled
                    elif encoder == "t5":
                        clip_l_e, clip_l_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_e, clip_g_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        clip_combined = F.pad(torch.cat([clip_l_e, clip_g_e], dim=-1), (0, 4096 - 2048))
                        prompt_embeds = torch.cat([clip_combined, gen_embed], dim=1)
                        pooled_embeds = torch.cat([clip_l_p, clip_g_p], dim=-1)
                        return prompt_embeds, pooled_embeds
                    elif encoder == "clip_l":
                        clip_g_e, clip_g_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_e = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_combined = F.pad(torch.cat([gen_embed, clip_g_e], dim=-1), (0, 4096 - 2048))
                        prompt_embeds = torch.cat([clip_combined, t5_e], dim=1)
                        pooled_embeds = torch.cat([gen_pooled, clip_g_p], dim=-1)
                        return prompt_embeds, pooled_embeds
                    else:  # clip_g
                        clip_l_e, clip_l_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        t5_e = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_combined = F.pad(torch.cat([clip_l_e, gen_embed], dim=-1), (0, 4096 - 2048))
                        prompt_embeds = torch.cat([clip_combined, t5_e], dim=1)
                        pooled_embeds = torch.cat([clip_l_p, gen_pooled], dim=-1)
                        return prompt_embeds, pooled_embeds

                def _build_negative_embeds(device):
                    """Build negative prompt embeddings."""
                    neg_text = negative_prompt if negative_prompt else ""
                    neg_clip_l, neg_clip_l_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=0
                    )
                    neg_clip_g, neg_clip_g_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=1
                    )
                    neg_t5 = pipe._get_t5_prompt_embeds(
                        prompt=neg_text, num_images_per_prompt=1,
                        max_sequence_length=512, device=device
                    )
                    neg_clip_combined = F.pad(torch.cat([neg_clip_l, neg_clip_g], dim=-1), (0, 4096 - 2048))
                    neg_prompt_embeds = torch.cat([neg_clip_combined, neg_t5], dim=1)
                    neg_pooled = torch.cat([neg_clip_l_pooled, neg_clip_g_pooled], dim=-1)
                    return neg_prompt_embeds, neg_pooled

                def _generate_image(prompt_embeds, pooled_embeds, neg_prompt_embeds, neg_pooled, generator):
                    """Generate a single image from pre-computed embeddings."""
                    gen_kwargs = {
                        "prompt_embeds": prompt_embeds,
                        "negative_prompt_embeds": neg_prompt_embeds,
                        "pooled_prompt_embeds": pooled_embeds,
                        "negative_pooled_prompt_embeds": neg_pooled,
                        "width": width,
                        "height": height,
                        "num_inference_steps": steps,
                        "guidance_scale": cfg_scale,
                        "generator": generator,
                        "max_sequence_length": 512,
                    }
                    result = pipe(**gen_kwargs)
                    return result.images[0]

                def _image_to_base64(image):
                    """Convert PIL image to base64 PNG string."""
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    return base64.b64encode(buffer.getvalue()).decode('utf-8')

                def _generate():
                    device = pipe._execution_device
                    generator_ref = torch.Generator(device=self.device).manual_seed(seed)
                    generator_res = torch.Generator(device=self.device).manual_seed(seed)

                    # Encode all three prompts with selected encoder
                    embed_a, pooled_a = _encode_prompt(prompt_a, device)
                    embed_b, pooled_b = _encode_prompt(prompt_b, device)
                    embed_c, pooled_c = _encode_prompt(prompt_c, device)

                    logger.info(
                        f"[DIFFUSERS-ALGEBRA] Encoded: A={embed_a.shape}, B={embed_b.shape}, C={embed_c.shape}"
                    )

                    # Apply concept algebra (token + pooled embeddings)
                    embed_result, l2_dist, pooled_result = apply_concept_algebra(
                        embed_a, embed_b, embed_c, scale_sub, scale_add,
                        pooled_a, pooled_b, pooled_c,
                    )
                    if pooled_result is None:
                        pooled_result = pooled_a

                    # Build negative embeddings (shared for both generations)
                    neg_prompt_embeds, neg_pooled = _build_negative_embeds(device)

                    # Generate reference image (prompt A, same seed)
                    reference_b64 = None
                    if generate_reference:
                        ref_prompt_embeds, ref_pooled = _compose_full_embedding(embed_a, pooled_a, device)
                        ref_image = _generate_image(ref_prompt_embeds, ref_pooled, neg_prompt_embeds, neg_pooled, generator_ref)
                        reference_b64 = _image_to_base64(ref_image)
                        logger.info("[DIFFUSERS-ALGEBRA] Reference image generated")

                    # Generate result image (algebra embedding, same seed)
                    res_prompt_embeds, res_pooled = _compose_full_embedding(embed_result, pooled_result, device)
                    res_image = _generate_image(res_prompt_embeds, res_pooled, neg_prompt_embeds, neg_pooled, generator_res)
                    result_b64 = _image_to_base64(res_image)
                    logger.info("[DIFFUSERS-ALGEBRA] Result image generated")

                    return reference_b64, result_b64, l2_dist

                reference_b64, result_b64, l2_dist = await asyncio.to_thread(self._locked_generate, _generate)

                return {
                    'reference_image': reference_b64,
                    'result_image': result_b64,
                    'algebra_data': {
                        'encoder': encoder,
                        'operation': 'A - scale_sub*B + scale_add*C',
                        'scale_sub': scale_sub,
                        'scale_add': scale_add,
                        'l2_distance': l2_dist,
                    },
                    'seed': seed,
                }

            finally:
                self._model_in_use[model_id] -= 1
                # Algebra creates manual embeddings (3 prompts x up to 3 encoders)
                # outside the pipeline's scope. Cleanup prevents VRAM fragmentation.
                torch.cuda.empty_cache()

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS-ALGEBRA] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_image_with_archaeology(
        self,
        prompt: str,
        model_id: str = DEFAULT_MODEL_ID,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        capture_every_n: int = 1,
        pipeline_class: str = "StableDiffusion3Pipeline",
        scheduler: Optional[str] = None,
        shift: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate image with step-by-step denoising visualization.

        At each sampling step, VAE-decodes the current latents into a 512x512
        JPEG thumbnail. Returns all step thumbnails plus the full-resolution
        final image.

        Args:
            prompt: Text prompt
            model_id: Model to use
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            steps: Number of sampling steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            capture_every_n: Capture every N steps (1 = every step)
            pipeline_class: Which diffusers pipeline the model needs. The step
                capture itself is architecture-neutral -- it hangs on
                callback_on_step_end and the VAE, which every one of them has.
            scheduler: Class name of a scheduler to run this one generation with,
                from the loaded pipeline's own `compatibles`. An unknown name is
                logged and ignored -- a run is not worth losing over it.
            shift: For flow matching only: how the steps are spread along the
                path. Higher values spend more of the run at the noisy end.

        Returns:
            Dict with image_base64, step_images, seed, total_steps, scheduler and
            scheduler_order; or None on failure
        """
        try:
            import torch
            import io
            import base64

            if not await self.load_model(model_id, pipeline_class):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(
                    f"[DIFFUSERS-ARCHAEOLOGY] Generating: prompt={prompt[:80]!r}, "
                    f"steps={steps}, seed={seed}, capture_every_n={capture_every_n}"
                )

                step_images = []
                # What actually ran, read off the pipeline rather than assumed,
                # so the surface can label a second-order run truthfully.
                sched_info = {"name": type(pipe.scheduler).__name__, "order": 1}

                def _generate():
                    # The scheduler is swapped INSIDE the generation lock and put
                    # back in the same breath: the pipeline stays resident between
                    # runs, so one left standing would silently rule every later
                    # run of this model -- including runs of other instruments.
                    #
                    # EVERYTHING from here on is inside the one try below. There
                    # must be no statement between the swap and the finally that
                    # restores it, and none between marking the progress active
                    # and the finally that clears it -- either gap strands global
                    # state on a raise.
                    original_scheduler = pipe.scheduler
                    try:
                        _install_run_scheduler(pipe, scheduler, shift)
                        sched_info["name"] = type(pipe.scheduler).__name__
                        sched_info["order"] = int(getattr(pipe.scheduler, "order", 1) or 1)
                        _generation_progress.update({"step": 0, "total_steps": steps, "active": True})

                        return _run(sched_info["order"])
                    finally:
                        pipe.scheduler = original_scheduler
                        _generation_progress["active"] = False

                def _run(order):
                    from diffusers.image_processor import VaeImageProcessor

                    def step_callback(pipe_instance, step, timestep, callback_kwargs):
                        # `step` counts the pipeline's TIMESTEPS. A second-order
                        # scheduler has 2n-1 of them for n steps, so reporting it
                        # raw would put "49 / 25" -- 196 % -- in front of every
                        # surface that reads this module-wide progress.
                        _generation_progress["step"] = min(step // order + 1, steps)
                        _generation_progress["total_steps"] = steps
                        # Thinning has to bite on the STEP, not on the timestep:
                        # per timestep it would drop whole steps of a second-order
                        # run rather than every nth of them.
                        if capture_every_n > 1 and (step // order) % capture_every_n != 0:
                            return callback_kwargs

                        try:
                            latents = callback_kwargs.get("latents")
                            if latents is not None:
                                vae_c = pipe_instance.vae
                                sched = pipe_instance.scheduler

                                # What x_t IS depends on the scheduler, and that is
                                # where the two architectures part company.
                                #  - flow matching (SD3.5): x_t = (1-s)*x0 + s*eps with
                                #    s in [0,1], so the latent stays O(1) and the VAE
                                #    can read it as it stands.
                                #  - k-diffusion (SDXL and the older U-Nets):
                                #    x_t = x0 + s*eps with s up to ~11.7 at 25 steps, so
                                #    the latent is far too large. Measured 2026-08-20:
                                #    the decoder input came out 8.7x too wide after the
                                #    first step and 46 % of the pixels clipped.
                                # Dividing by sqrt(s^2+1) is what the scheduler does to
                                # the latent before it hands it to the net.
                                sigmas = getattr(sched, "sigmas", None)
                                lat = latents
                                if sigmas is not None and "FlowMatch" not in type(sched).__name__:
                                    nxt = step + 1
                                    if 0 <= nxt < len(sigmas):
                                        sigma = float(sigmas[nxt])
                                        lat = lat / ((sigma * sigma + 1.0) ** 0.5)

                                # SD3.5 shifts as well as scales; SDXL only scales.
                                # Without the shift an SD3.5 frame comes out off by a
                                # constant -- the two other decode sites in this file
                                # already add it.
                                shift = getattr(vae_c.config, "shift_factor", None) or 0.0

                                # A VAE that declares force_upcast returns NaN in
                                # float16, and NaN survives the clamp as black: all 25
                                # SDXL frames measured at mean 0.0, std 0.0 on
                                # 2026-08-20. Its pipeline upcasts for the final image,
                                # but only after the loop -- this decode is inside it.
                                # Cast for the decode and put it straight back, because
                                # the pipeline decodes the final image itself and
                                # assumes the dtype it loaded with.
                                orig_dtype = vae_c.dtype
                                needs_upcast = (
                                    orig_dtype == torch.float16
                                    and getattr(vae_c.config, "force_upcast", False)
                                )
                                if needs_upcast:
                                    vae_c.to(dtype=torch.float32)
                                try:
                                    with torch.no_grad():
                                        decoded = vae_c.decode(
                                            lat.to(vae_c.dtype) / vae_c.config.scaling_factor
                                            + shift
                                        ).sample
                                finally:
                                    if needs_upcast:
                                        vae_c.to(dtype=orig_dtype)

                                processor = VaeImageProcessor()
                                pil_image = processor.postprocess(decoded, output_type="pil")[0]

                                # Encode as full-resolution JPEG q95
                                buf = io.BytesIO()
                                pil_image.save(buf, format="JPEG", quality=95)
                                b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

                                step_images.append({
                                    'step': step,
                                    'timestep': float(timestep),
                                    'image_base64': b64,
                                })
                        except Exception as e:
                            logger.warning(f"[DIFFUSERS-ARCHAEOLOGY] Step {step} capture failed: {e}")

                        return callback_kwargs

                    gen_kwargs = {
                        "prompt": prompt,
                        "negative_prompt": negative_prompt if negative_prompt else None,
                        "width": width,
                        "height": height,
                        "num_inference_steps": steps,
                        "guidance_scale": cfg_scale,
                        "generator": generator,
                        "callback_on_step_end": step_callback,
                        "callback_on_step_end_tensor_inputs": ["latents"],
                    }

                    if hasattr(pipe, 'tokenizer_3'):
                        gen_kwargs["max_sequence_length"] = 512

                    result = pipe(**gen_kwargs)
                    return result.images[0]

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Final image as full-resolution PNG base64
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                logger.info(
                    f"[DIFFUSERS-ARCHAEOLOGY] Done: {len(step_images)} step images captured, "
                    f"final PNG {len(buffer.getvalue())} bytes"
                )

                return {
                    'image_base64': image_base64,
                    'step_images': step_images,
                    'seed': seed,
                    'total_steps': steps,
                    # A second-order scheduler asks the net twice per step, so
                    # more frames come back than steps were asked for. The
                    # surface needs both numbers to name a frame correctly.
                    'scheduler': sched_info["name"],
                    'scheduler_order': sched_info["order"],
                }

            finally:
                self._model_in_use[model_id] -= 1

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[DIFFUSERS-ARCHAEOLOGY] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _tokenize_prompt(self, pipe, prompt: str) -> list:
        """Tokenize a prompt and return human-readable token strings.

        Uses the CLIP tokenizer (tokenizer_1) for display-friendly tokens,
        since CLIP tokens map cleanly to words/subwords.
        """
        try:
            tokenizer = pipe.tokenizer  # CLIP-L tokenizer
            if tokenizer is None and hasattr(pipe, 'tokenizer_2'):
                tokenizer = pipe.tokenizer_2  # CLIP-G
            if tokenizer is None:
                return [prompt]  # Fallback: return whole prompt

            # Re-entrant on purpose: this helper is called from describing
            # paths and from inside a generation that already holds it.
            with self._inference_lock:
                encoded = tokenizer(
                    prompt,
                    padding=False,
                    truncation=True,
                    max_length=77,
                    return_tensors=None,
                )
                token_ids = encoded['input_ids']

                # Decode each token individually, skip special tokens
                tokens = []
                for tid in token_ids:
                    decoded = tokenizer.decode([tid], skip_special_tokens=True).strip()
                    if decoded:
                        tokens.append(decoded)

            return tokens if tokens else [prompt]

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.warning(f"[DIFFUSERS-ATTENTION] Tokenization failed: {e}")
            return prompt.split()


    async def generate_image_composable(
        self,
        concepts: list,
        model_id: str = DEFAULT_MODEL_ID,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        normalize_weights: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Composable Diffusion: per-concept noise prediction blending.

        Instead of encoding all concepts into one embedding, each concept gets
        its own transformer pass at every denoising step. Noise predictions are
        blended with weights before the scheduler step.

        Based on Liu et al. (2022) "Compositional Visual Generation with
        Composable Diffusion Models".

        Args:
            concepts: List of {"prompt": str, "weight": float} dicts
            model_id: SD3.5 model to use
            negative_prompt: Shared negative prompt
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            normalize_weights: If True, concept weights sum to 1.0

        Returns:
            Dict with image_base64, seed, concept_count, timing_s
        """
        try:
            import torch
            import torch.nn.functional as F
            import io
            import base64

            if not concepts or len(concepts) < 2:
                logger.error("[COMPOSABLE] Need at least 2 concepts")
                return None

            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[COMPOSABLE] Pipeline missing encoder methods")
                    return None

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                # --- Composition weights (Liu et al. 2022) ---
                # The paper composes scores as  eps_u + sum_i v_i * (eps_i - eps_u),
                # where each v_i is an independent guidance temperature for concept i
                # (Eq. 11). Concept negation (Eq. 15) is that same expression with a
                # negative v_i, because
                #   eps_u + w*(eps_a - eps_b) == eps_u + w*(eps_a - eps_u) - w*(eps_b - eps_u)
                # Two parameterizations of the user-facing weights:
                #   "mixture"     (normalize_weights, all w >= 0): v_i = cfg * w_i / sum(w)
                #                 Total guidance stays at cfg; the weights are shares of it.
                #                 This is the historical behaviour of this endpoint.
                #   "temperature" (otherwise):                     v_i = cfg * w_i
                #                 Each concept keeps its own strength; w < 0 means NOT.
                raw_weights = [float(c.get("weight", 1.0)) for c in concepts]
                has_negative = any(w < 0 for w in raw_weights)

                if normalize_weights and has_negative:
                    logger.info("[COMPOSABLE] Negative weight present -> normalization off (a signed mixture has no meaning)")
                    normalize_weights = False

                if normalize_weights:
                    w_sum = sum(raw_weights)
                    weights = [w / w_sum for w in raw_weights] if w_sum > 0 else list(raw_weights)
                    composition_mode = "mixture"
                else:
                    weights = list(raw_weights)
                    composition_mode = "temperature"

                guidance = [cfg_scale * w for w in weights]

                logger.info(
                    f"[COMPOSABLE] {len(concepts)} concepts, mode={composition_mode}, "
                    f"weights={[f'{w:.2f}' for w in weights]}, guidance={[f'{v:.2f}' for v in guidance]}, "
                    f"negated={sum(1 for v in guidance if v < 0)}, "
                    f"steps={steps}, size={width}x{height}, seed={seed}, cfg={cfg_scale}"
                )

                def _encode_full(prompt_text, device, encoder="all"):
                    """Encode a prompt with the SD3.5 encoders.

                    encoder="all"  -> the full sequence, [CLIP tokens ; T5 tokens]
                    encoder="clip" -> the T5 block zeroed: the literal-visual reading alone
                    encoder="t5"   -> the CLIP block zeroed: the thematic reading alone

                    The pooled projection stays real in every case. It is the switch for
                    whether a coherent image forms at all, not a carrier of content, so
                    zeroing it would end the run rather than isolate a reading.
                    """
                    with torch.no_grad():
                        clip_l, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device,
                            num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device,
                            num_images_per_prompt=1, clip_model_index=1
                        )
                        t5 = pipe._get_t5_prompt_embeds(
                            prompt=prompt_text, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                    clip_combined = F.pad(
                        torch.cat([clip_l, clip_g], dim=-1),
                        (0, 4096 - 2048)
                    )
                    if encoder == "clip":
                        t5 = torch.zeros_like(t5)
                    elif encoder == "t5":
                        clip_combined = torch.zeros_like(clip_combined)
                    prompt_embeds = torch.cat([clip_combined, t5], dim=1)
                    pooled = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)
                    return prompt_embeds, pooled

                def _generate():
                    from diffusers.pipelines.stable_diffusion_3.pipeline_stable_diffusion_3 import (
                        retrieve_timesteps, calculate_shift
                    )

                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    start_time = time.time()

                    try:
                        device = pipe._execution_device
                        generator = torch.Generator(device=self.device).manual_seed(seed)

                        # --- Encode all concepts ---
                        concept_embeds_list = []
                        concept_pooled_list = []
                        for i, concept in enumerate(concepts):
                            embeds, pooled = _encode_full(
                                concept["prompt"], device, concept.get("encoder", "all")
                            )
                            concept_embeds_list.append(embeds)
                            concept_pooled_list.append(pooled)
                            logger.info(
                                f"[COMPOSABLE] Encoded concept {i} "
                                f"(encoder={concept.get('encoder', 'all')}): "
                                f"'{concept['prompt'][:50]}' shape={embeds.shape}"
                            )

                        # Pad all concept embeds to same sequence length
                        max_seq_len = max(e.shape[1] for e in concept_embeds_list)
                        for i in range(len(concept_embeds_list)):
                            if concept_embeds_list[i].shape[1] < max_seq_len:
                                pad_len = max_seq_len - concept_embeds_list[i].shape[1]
                                concept_embeds_list[i] = F.pad(concept_embeds_list[i], (0, 0, 0, pad_len))

                        # --- Encode negative prompt ---
                        neg_text = negative_prompt if negative_prompt else ""
                        neg_embeds, neg_pooled = _encode_full(neg_text, device)
                        # Pad negative to same seq length
                        if neg_embeds.shape[1] < max_seq_len:
                            pad_len = max_seq_len - neg_embeds.shape[1]
                            neg_embeds = F.pad(neg_embeds, (0, 0, 0, pad_len))

                        torch.cuda.empty_cache()

                        # --- Prepare latents ---
                        num_channels_latents = pipe.transformer.config.in_channels
                        latents = pipe.prepare_latents(
                            1, num_channels_latents, height, width,
                            concept_embeds_list[0].dtype, device, generator, None
                        )

                        # --- Prepare timesteps with dynamic shifting ---
                        scheduler_kwargs = {}
                        if pipe.scheduler.config.get("use_dynamic_shifting", None):
                            _, _, lat_h, lat_w = latents.shape
                            image_seq_len = (lat_h // pipe.transformer.config.patch_size) * (
                                lat_w // pipe.transformer.config.patch_size
                            )
                            mu = calculate_shift(
                                image_seq_len,
                                pipe.scheduler.config.get("base_image_seq_len", 256),
                                pipe.scheduler.config.get("max_image_seq_len", 4096),
                                pipe.scheduler.config.get("base_shift", 0.5),
                                pipe.scheduler.config.get("max_shift", 1.16),
                            )
                            scheduler_kwargs["mu"] = mu

                        timesteps, num_inference_steps = retrieve_timesteps(
                            pipe.scheduler, steps, device, **scheduler_kwargs
                        )

                        # === COMPOSABLE DENOISING LOOP ===
                        with torch.no_grad():
                            for step_idx, t in enumerate(timesteps):
                                _generation_progress["step"] = step_idx

                                timestep_single = t.expand(latents.shape[0])

                                # 1. Unconditional pass (shared negative)
                                noise_uncond = pipe.transformer(
                                    hidden_states=latents,
                                    timestep=timestep_single,
                                    encoder_hidden_states=neg_embeds,
                                    pooled_projections=neg_pooled,
                                    return_dict=False,
                                )[0]

                                # 2. Per-concept conditional passes, accumulated as
                                #    eps_u + sum_i v_i * (eps_i - eps_u)   (Liu et al., Eq. 11).
                                #    A negative v_i is the negation operator (Eq. 15).
                                noise_pred = noise_uncond
                                for i, (embeds, pooled, v) in enumerate(
                                    zip(concept_embeds_list, concept_pooled_list, guidance)
                                ):
                                    noise_i = pipe.transformer(
                                        hidden_states=latents,
                                        timestep=timestep_single,
                                        encoder_hidden_states=embeds,
                                        pooled_projections=pooled,
                                        return_dict=False,
                                    )[0]
                                    noise_pred = noise_pred + v * (noise_i - noise_uncond)

                                # 4. Scheduler step
                                latents_dtype = latents.dtype
                                latents = pipe.scheduler.step(noise_pred, t, latents, return_dict=False)[0]
                                if latents.dtype != latents_dtype:
                                    latents = latents.to(latents_dtype)

                        _generation_progress["step"] = steps

                        # === VAE decode ===
                        with torch.no_grad():
                            latents = (latents / pipe.vae.config.scaling_factor) + pipe.vae.config.shift_factor
                            image = pipe.vae.decode(latents, return_dict=False)[0]
                            image = pipe.image_processor.postprocess(image, output_type="pil")[0]

                        elapsed = time.time() - start_time
                        logger.info(f"[COMPOSABLE] Done in {elapsed:.1f}s, {len(concepts)} concepts × {steps} steps")

                        # Convert to base64
                        buffer = io.BytesIO()
                        image.save(buffer, format="PNG")
                        image_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                        return {
                            "image_base64": image_b64,
                            "seed": seed,
                            "concept_count": len(concepts),
                            "weights_used": weights,
                            "guidance_used": guidance,
                            "composition_mode": composition_mode,
                            "negated_count": sum(1 for v in guidance if v < 0),
                            "timing_s": round(elapsed, 1),
                        }
                    finally:
                        _generation_progress["active"] = False

                result = await asyncio.to_thread(self._locked_generate, _generate)
                return result

            finally:
                self._model_in_use[model_id] -= 1
                torch.cuda.empty_cache()

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[COMPOSABLE] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def encode_prompt_info(
        self,
        prompt: str,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> Dict[str, Any]:
        """
        Analyze how the three SD3.5 text encoders process a prompt.

        Returns tokenization, per-token embedding norms (activation strength),
        and encoder agreement (cosine similarity between encoders per token position).

        This is lightweight: one forward pass per encoder (~100ms total on GPU).
        Falls back to tokenization-only if model is not loaded.
        """
        try:
            import torch
            import torch.nn.functional as F

            result = {"model_id": model_id}

            # A U-Net model has no third tokenizer and never will. Asking the
            # question by loading it costs a slot on the card and an eviction of
            # whatever was resident, for an answer the pairing already gives --
            # and this route is called for every diffusers config.
            if self._pipeline_class_for(model_id, "StableDiffusion3Pipeline") != "StableDiffusion3Pipeline":
                return {"error": "Pipeline does not have triple text encoders (not SD3.5?)"}

            # Check if model is loaded — if not, return tokenization only
            if model_id not in self._pipelines:
                # Try to load, but don't block if it fails
                if not await self.load_model(model_id):
                    return {"error": f"Model {model_id} not available"}

            # Kept from eviction from here on, as every generation keeps its
            # model right after its load (PART 27): until 2026-10-10 the count
            # was taken only after the three tokenizers had run, and a load of
            # another model in that window could take this one off the card.
            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                pipe = self._pipelines[model_id]

                # Verify this is an SD3.5-style pipeline with triple encoders
                has_triple = (
                    hasattr(pipe, 'tokenizer') and
                    hasattr(pipe, 'tokenizer_2') and
                    hasattr(pipe, 'tokenizer_3')
                )
                if not has_triple:
                    return {"error": "Pipeline does not have triple text encoders (not SD3.5?)"}

                has_encoders = (
                    hasattr(pipe, '_get_clip_prompt_embeds') and
                    hasattr(pipe, '_get_t5_prompt_embeds')
                )

                # --- Tokenization (CPU only, always available) ---
                def _tokenize(tokenizer, name, max_len):
                    tokens = tokenizer(
                        prompt,
                        padding=False,
                        truncation=False,
                        return_tensors=None,
                    )
                    input_ids = tokens["input_ids"]
                    # Strip special tokens (SOT/EOT for CLIP, pad for T5)
                    if hasattr(tokenizer, 'bos_token_id') and input_ids and input_ids[0] == tokenizer.bos_token_id:
                        input_ids = input_ids[1:]
                    if hasattr(tokenizer, 'eos_token_id') and input_ids and input_ids[-1] == tokenizer.eos_token_id:
                        input_ids = input_ids[:-1]

                    decoded_tokens = [tokenizer.decode([tid]) for tid in input_ids]
                    count = len(input_ids)
                    truncated = count > max_len

                    return {
                        "tokens": decoded_tokens[:max_len],
                        "count": min(count, max_len),
                        "total_count": count,
                        "max": max_len,
                        "truncated": truncated,
                    }

                # All three under the inference lock. This surface is asked WHILE a
                # generation runs — that is what it is for — and the tokenizers it
                # reads are the ones that generation is using.
                with self._inference_lock:
                    clip_l_tok = _tokenize(pipe.tokenizer, "clip_l", 75)  # 77 - 2 special tokens
                    clip_g_tok = _tokenize(pipe.tokenizer_2, "clip_g", 75)
                    t5_tok = _tokenize(pipe.tokenizer_3, "t5", 512)

                result["clip_l"] = {**clip_l_tok, "embed_dim": 768}
                result["clip_g"] = {**clip_g_tok, "embed_dim": 1280}
                result["t5"] = {**t5_tok, "embed_dim": 4096}

                # --- Embedding analysis (GPU, only if encoders available) ---
                if has_encoders:
                    self._model_last_used[model_id] = time.time()
                    device = pipe._execution_device

                    def _encode():
                        with self._inference_lock, torch.no_grad():
                            # CLIP-L: [1, 77, 768]
                            clip_l_embeds, _ = pipe._get_clip_prompt_embeds(
                                prompt=prompt, device=device,
                                num_images_per_prompt=1, clip_model_index=0
                            )
                            # CLIP-G: [1, 77, 1280]
                            clip_g_embeds, _ = pipe._get_clip_prompt_embeds(
                                prompt=prompt, device=device,
                                num_images_per_prompt=1, clip_model_index=1
                            )
                            # T5-XXL: [1, N, 4096]
                            t5_embeds = pipe._get_t5_prompt_embeds(
                                prompt=prompt, num_images_per_prompt=1,
                                max_sequence_length=512, device=device
                            )

                        # Per-token L2 norms (activation strength)
                        clip_l_norms = torch.norm(clip_l_embeds[0], dim=-1).cpu()  # [77]
                        clip_g_norms = torch.norm(clip_g_embeds[0], dim=-1).cpu()  # [77]
                        t5_norms = torch.norm(t5_embeds[0], dim=-1).cpu()  # [N]

                        # Normalize to [0, 1] for visualization
                        def _normalize(norms, token_count):
                            """Normalize norms for actual tokens (skip padding)."""
                            actual = norms[:token_count]
                            if actual.max() > actual.min():
                                return ((actual - actual.min()) / (actual.max() - actual.min())).tolist()
                            return [0.5] * token_count

                        clip_l_count = clip_l_tok["count"]
                        clip_g_count = clip_g_tok["count"]
                        t5_count = t5_tok["count"]

                        result["clip_l"]["token_norms"] = _normalize(clip_l_norms, clip_l_count)
                        result["clip_g"]["token_norms"] = _normalize(clip_g_norms, clip_g_count)
                        result["t5"]["token_norms"] = _normalize(t5_norms, t5_count)

                        # Encoder agreement: cosine similarity per token position
                        # Compare over shared token count (min of all encoders)
                        shared_count = min(clip_l_count, clip_g_count, t5_count)
                        if shared_count > 0:
                            # Pad CLIP embeddings to T5 dim for meaningful comparison
                            clip_l_padded = F.pad(clip_l_embeds[0, :shared_count], (0, 4096 - 768))
                            clip_g_padded = F.pad(clip_g_embeds[0, :shared_count], (0, 4096 - 1280))
                            t5_shared = t5_embeds[0, :shared_count]

                            cos = torch.nn.CosineSimilarity(dim=-1)
                            result["encoder_agreement"] = {
                                "clip_l_vs_t5": cos(clip_l_padded, t5_shared).cpu().tolist(),
                                "clip_g_vs_t5": cos(clip_g_padded, t5_shared).cpu().tolist(),
                                "clip_l_vs_clip_g": cos(
                                    F.pad(clip_l_embeds[0, :shared_count], (0, 1280 - 768)),
                                    clip_g_embeds[0, :shared_count]
                                ).cpu().tolist(),
                                "shared_positions": shared_count,
                            }

                    # Under the plant-wide SLOT since 2026-10-10 (finding S-003 of the code review of 2026-10-10): three
                    # encoder forward passes allocate on the card, and Rule 15
                    # admits every forward. Until then this ran outside the slot
                    # so that it could answer during a generation; it never did,
                    # because the inference LOCK below already waits for the
                    # pass it describes.
                    #
                    # Inside the inference LOCK, which it was not until
                    # 2026-09-02. The reasoning was the same — answer while the
                    # generation runs — and the cost was a generation killed by
                    # "Already borrowed" out of tokenizer_3, twice in two days.
                    # The tokenizers are one object per pipeline and they cannot
                    # be read from two threads; so this waits for the pass it
                    # describes, and answers a moment later instead of taking it
                    # down.
                    await asyncio.to_thread(self._locked_generate, _encode, model_id)


                logger.info(
                    f"[ENCODE-INFO] clip_l={clip_l_tok['count']}/{clip_l_tok['max']}, "
                    f"clip_g={clip_g_tok['count']}/{clip_g_tok['max']}, "
                    f"t5={t5_tok['count']}/{t5_tok['max']}, "
                    f"has_norms={'token_norms' in result.get('clip_l', {})}"
                )
                return result
            finally:
                self._model_in_use[model_id] -= 1

        except GpuBusy:
            raise          # busy is not a failed generation
        except Exception as e:
            logger.error(f"[ENCODE-INFO] Error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}


# Singleton instance
_backend: Optional[DiffusersImageGenerator] = None


def get_diffusers_backend() -> DiffusersImageGenerator:
    """
    Get Diffusers backend singleton

    Returns:
        DiffusersImageGenerator instance
    """
    global _backend
    if _backend is None:
        _backend = DiffusersImageGenerator()
    return _backend


def reset_diffusers_backend():
    """Reset the singleton backend (for testing)"""
    global _backend
    _backend = None
