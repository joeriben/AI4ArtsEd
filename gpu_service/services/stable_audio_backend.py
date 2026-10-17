"""
Stable Audio Backend - Audio generation via Stable Audio 3 (stable-audio-tools)

Re-platformed from Stable Audio Open 1.0 (diffusers StableAudioPipeline) to
Stable Audio 3 (stable-audio-tools). See research/sa3_migration/MIGRATION_DESIGN.md.

Why stable-audio-tools instead of diffusers:
- diffusers has no SA3 pipeline yet.
- `generate_diffusion_cond_inpaint(model, conditioning_tensors=<dict>)` accepts PRECOMPUTED
  conditioning tensors, and `model.conditioner([{prompt, seconds_total}], device)` produces
  that dict. This is the exact injection seam the Latent Synth needs — manipulate the cross-attn
  prompt tensor in the dict and pass it straight back. No denoising-loop reimplementation
  (SA1/diffusers required one; SA3 does not).
- We use the *_inpaint variant (not plain generate_diffusion_cond) because SA3 medium's DiT
  declares local_add_cond_ids = [inpaint_mask, inpaint_masked_input]; the inpaint entry point
  supplies these as zeros when inpaint_audio=None (= pure generation), the plain entry point
  does not. The model card uses the same function for ordinary text-to-audio.

SA3 medium facts (model_config.json):
- t5gemma prompt conditioner (google/t5gemma-b-b-ul2), bundled in repo subfolder; max_length 256,
  output dim 768 (== SA1 T5-Base dim → PCA/canvas structurally compatible).
- seconds_total conditioning only — NO seconds_start (SA1 had it; `start_position` cannot carry over).
- 44100 Hz, stereo, autoencoder pretransform downsampling_ratio 4096, DiT rf_denoiser objective.

Caller contract preserved exactly (see MIGRATION_DESIGN.md §5):
    encode_prompt(text) -> (prompt_embeds [1,256,768], attention_mask [1,256])
    generate_audio(prompt, duration_seconds, negative_prompt, steps, cfg_scale, seed, output_format) -> bytes
    generate_from_embeddings(prompt_embeds, attention_mask, seconds_start, seconds_end, ...) -> bytes
    generate_audio_with_guidance(...) -> dict   # i2a — Task #4 (RF sampler guidance), stubbed here
    get_vae(); is_available(); VRAM coordinator protocol; singleton.
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import asyncio

from services.generation_failure import GenerationFailed

logger = logging.getLogger(__name__)

# --- SA3 inference baseline (authoritative: model card + model_config.json) ---
# SA3 medium is adversarially post-trained for few-step rectified-flow inference.
#   - model_config training.demo.demo_steps == 8
#   - model card example: sampler_type="pingpong", cfg_scale=1.0
# generate_diffusion_cond_inpaint pops sampler_type with default "euler" (generation.py:569),
# bypassing sample_diffusion's own RF auto-pingpong (sampling.py:806) — so it MUST be
# passed explicitly. These are documented baselines; empirical tuning is pending GPU
# availability (the encode/test GPU was VRAM-saturated at migration time).
SA3_DEFAULT_STEPS = 8
SA3_DEFAULT_CFG_SCALE = 1.0
SA3_SAMPLER_TYPE = "pingpong"


@contextmanager
def _grad_through_decode(pretransform):
    """Let the gradient pass through the autoencoder decode.

    AudioAutoencoder.decode runs its own inner pretransform (the STFT stage) under
    torch.no_grad() unless that pretransform carries enable_grad. With the flag off the
    autograd graph is cut inside the decode: no gradient ever reaches the latent, nothing
    raises, and a guided step silently degenerates into an unguided one. Open the flag for
    the guided decode only - left open, it would keep a decode graph alive on every
    ordinary generation.
    """
    inner = getattr(getattr(pretransform, "model", None), "pretransform", None)
    previous = getattr(inner, "enable_grad", None)
    if inner is not None:
        inner.enable_grad = True
    try:
        yield
    finally:
        if inner is not None and previous is not None:
            inner.enable_grad = previous


class StableAudioGenerator:
    """
    Audio generation using Stable Audio 3 via stable-audio-tools.

    Supports:
    - Text-to-audio generation (generate_audio)
    - Pre-computed embedding injection for Latent Synth / cross-aesthetic (generate_from_embeddings)
    - Standalone conditioner access for embedding manipulation (encode_prompt)
    - Lazy model loading for VRAM efficiency + VRAM coordinator integration
    """

    def __init__(self):
        from config import (
            STABLE_AUDIO_DEVICE,
            STABLE_AUDIO_DTYPE,
            STABLE_AUDIO_LAZY_LOAD,
            STABLE_AUDIO_MAX_DURATION,
            STABLE_AUDIO_SAMPLE_RATE,
        )
        from services.stable_audio_model import get_stable_audio_model_id

        # VRAM-tiered single source of truth (medium vs small-music). SFX = small-sfx,
        # wired when a dedicated SFX generation path lands (see MIGRATION_DESIGN.md §4).
        self.model_id = get_stable_audio_model_id("music")
        self.device = STABLE_AUDIO_DEVICE
        self.dtype_str = STABLE_AUDIO_DTYPE
        self.lazy_load = STABLE_AUDIO_LAZY_LOAD
        self.max_duration = STABLE_AUDIO_MAX_DURATION
        self.sample_rate = STABLE_AUDIO_SAMPLE_RATE  # overwritten from model_config on load

        # Model (lazy-loaded). `self.model` is a stable-audio-tools
        # ConditionedDiffusionModelWrapper: .conditioner, .model (DiT), .pretransform (autoencoder).
        self.model = None
        self.model_config: Optional[dict] = None
        self._downsampling_ratio: int = 4096
        self._max_sample_size: int = 16777216

        self._is_loaded = False
        self._vram_mb: float = 0
        self._last_used: float = 0
        self._in_use: int = 0

        self._register_with_coordinator()

        logger.info(
            f"[STABLE-AUDIO] Initialized (SA3/stable-audio-tools): model={self.model_id}, "
            f"device={self.device}, lazy_load={self.lazy_load}"
        )

    def _register_with_coordinator(self):
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[STABLE-AUDIO] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[STABLE-AUDIO] Failed to register with VRAM coordinator: {e}")

    # =========================================================================
    # VRAMBackend Protocol
    # =========================================================================

    def get_backend_id(self) -> str:
        return "stable_audio"

    def get_registered_models(self) -> List[Dict[str, Any]]:
        from services.vram_coordinator import EvictionPriority

        if not self._is_loaded:
            return []

        return [
            {
                "model_id": self.model_id,
                "vram_mb": self._vram_mb,
                "priority": EvictionPriority.NORMAL,
                "last_used": self._last_used,
                "in_use": self._in_use,
            }
        ]

    def evict_model(self, model_id: str) -> bool:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.unload_pipeline())
        finally:
            loop.close()

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def is_available(self) -> bool:
        try:
            from stable_audio_tools import get_pretrained_model  # noqa: F401
            return True
        except ImportError:
            logger.error("[STABLE-AUDIO] stable-audio-tools not installed")
            return False

    def _resolve_dtype(self):
        import torch
        return {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }.get(self.dtype_str, torch.float32)

    async def _load_pipeline(self) -> bool:
        if self._is_loaded:
            return True

        try:
            import torch
            from stable_audio_tools import get_pretrained_model

            # Request VRAM from coordinator (~6GB estimated for SA3 medium in float32)
            try:
                from services.vram_coordinator import get_vram_coordinator, EvictionPriority
                coordinator = get_vram_coordinator()
                coordinator.request_vram("stable_audio", 6000, EvictionPriority.NORMAL)
            except Exception as e:
                logger.warning(f"[STABLE-AUDIO] VRAM coordinator request failed: {e}")

            logger.info(f"[STABLE-AUDIO] Loading SA3 model: {self.model_id}...")

            vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
            torch_dtype = self._resolve_dtype()

            def _load():
                model, model_config = get_pretrained_model(self.model_id)
                model = model.to(self.device)
                # Correctness-first: keep float32 unless explicitly overridden (Task #4 tunes dtype).
                # If a half dtype is configured, cast the DiT only; keep the autoencoder
                # (pretransform) in float32 for decode stability (cf. heartlib codec lesson).
                if torch_dtype != torch.float32:
                    try:
                        model.model = model.model.to(torch_dtype)
                    except Exception as e:
                        logger.warning(f"[STABLE-AUDIO] DiT half-cast failed, staying float32: {e}")
                model.eval()
                return model, model_config

            self.model, self.model_config = await asyncio.to_thread(_load)
            self.sample_rate = int(self.model_config.get("sample_rate", self.sample_rate))
            self._max_sample_size = int(self.model_config.get("sample_size", self._max_sample_size))

            # STABLE_AUDIO_MAX_DURATION is a platform decision; the loaded FILE has
            # its own ceiling, and the two differ by a factor of two across tiers —
            # SA3 medium reaches 380s, the small music/sfx models exactly 120s, and
            # which one loads depends on the card (stable_audio_model.py, 50 GB
            # threshold). _aligned_sample_size caps at the file's ceiling in any
            # case, so a configured value above it never produced longer audio: it
            # produced SHORTER audio and said nothing. Take the smaller of the two
            # once, here, so every number downstream is one the model can keep.
            native_max = self._max_sample_size / float(self.sample_rate)
            if native_max < self.max_duration:
                logger.warning(
                    f"[STABLE-AUDIO] configured ceiling {self.max_duration:.1f}s is above "
                    f"what this model file renders ({native_max:.1f}s); using {native_max:.1f}s"
                )
                self.max_duration = native_max
            try:
                self._downsampling_ratio = int(self.model.pretransform.downsampling_ratio)
            except Exception:
                self._downsampling_ratio = 4096

            self._is_loaded = True
            self._last_used = time.time()

            vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
            self._vram_mb = (vram_after - vram_before) / (1024 * 1024)

            logger.info(
                f"[STABLE-AUDIO] SA3 model loaded (VRAM: {self._vram_mb:.0f}MB, "
                f"sr={self.sample_rate}, ds_ratio={self._downsampling_ratio})"
            )
            return True

        except Exception as e:
            logger.error(f"[STABLE-AUDIO] Failed to load SA3 model: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def unload_pipeline(self) -> bool:
        if not self._is_loaded:
            return False

        try:
            import torch

            del self.model
            self.model = None
            self.model_config = None
            self._is_loaded = False
            self._vram_mb = 0
            self._in_use = 0

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            logger.info("[STABLE-AUDIO] SA3 model unloaded")
            return True

        except Exception as e:
            logger.error(f"[STABLE-AUDIO] Error unloading model: {e}")
            return False

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _aligned_sample_size(self, duration_seconds: float) -> int:
        """Audio-sample count for `duration_seconds`, rounded UP to the autoencoder
        downsampling ratio and capped at the model maximum."""
        target = int(round(duration_seconds * self.sample_rate))
        ds = self._downsampling_ratio
        aligned = ((target + ds - 1) // ds) * ds
        return max(ds, min(aligned, self._max_sample_size))

    def _postprocess(self, audio):
        """Peak-normalize to [-1, 1] (SA3/RF output can exceed unit range) and return
        a float32 CPU tensor shaped [channels, samples]."""
        import torch
        audio = audio.to(torch.float32).cpu()
        peak = torch.max(torch.abs(audio))
        if peak > 0:
            audio = audio / peak
        return audio.clamp(-1.0, 1.0)

    # =========================================================================
    # Generation
    # =========================================================================

    async def generate_audio(
        self,
        prompt: str,
        duration_seconds: float = 10.0,
        negative_prompt: str = "",
        steps: int = SA3_DEFAULT_STEPS,
        cfg_scale: float = SA3_DEFAULT_CFG_SCALE,
        seed: int = -1,
        output_format: str = "wav",
    ) -> Optional[bytes]:
        """Generate audio from a text prompt (t2a).

        SA3 medium is adversarially post-trained for FEW-step inference: the model card
        and model_config (`training.demo.demo_steps`) both use 8 steps with the `pingpong`
        rectified-flow sampler and cfg_scale=1.0 (guidance is baked into the distillation).
        At cfg_scale≈1.0 the negative prompt is effectively inert — a behavior change from
        SA1 (which used cfg≈5-7). Defaults reflect the documented SA3 baseline; callers may
        override. Empirical tuning pending GPU availability (see MIGRATION_DESIGN §5).
        """
        try:
            import torch
            # SA3 medium's DiT requires inpaint local-conditioning (local_add_cond_ids:
            # inpaint_mask, inpaint_masked_input). Only generate_diffusion_cond_inpaint
            # supplies them — with inpaint_audio=None it sets zeros (= pure generation),
            # which is exactly the t2a path the model card uses. Plain generate_diffusion_cond
            # omits these conds and would fail/produce garbage on this model.
            from stable_audio_tools.inference.generation import generate_diffusion_cond_inpaint

            if not self._is_loaded:
                if not await self._load_pipeline():
                    return None

            self._in_use += 1
            self._last_used = time.time()

            try:
                if duration_seconds > self.max_duration:
                    logger.warning(
                        f"[STABLE-AUDIO] {duration_seconds:.1f}s requested, this model tops "
                        f"out at {self.max_duration:.1f}s; generating {self.max_duration:.1f}s"
                    )
                duration_seconds = min(duration_seconds, self.max_duration)

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                sample_size = self._aligned_sample_size(duration_seconds)
                conditioning = [{"prompt": prompt, "seconds_total": duration_seconds}]
                negative_conditioning = (
                    [{"prompt": negative_prompt, "seconds_total": duration_seconds}]
                    if negative_prompt else None
                )

                logger.info(
                    f"[STABLE-AUDIO] Generating: prompt='{prompt[:80]}', "
                    f"duration={duration_seconds}s, steps={steps}, cfg={cfg_scale}, seed={seed}"
                )

                def _generate():
                    with torch.no_grad():
                        audio = generate_diffusion_cond_inpaint(
                            self.model,
                            conditioning=conditioning,
                            negative_conditioning=negative_conditioning,
                            steps=steps,
                            cfg_scale=cfg_scale,
                            sample_size=sample_size,
                            seed=seed,
                            device=self.device,
                            # RF sampler. The wrapper pops sampler_type with default "euler",
                            # bypassing sample_diffusion's own RF auto-default (sampling.py:806)
                            # — so pingpong MUST be passed explicitly.
                            sampler_type=SA3_SAMPLER_TYPE,
                        )
                    # [B, channels, samples] -> [channels, samples], peak-normalized, trimmed
                    audio = self._postprocess(audio[0])
                    return audio[:, : int(round(duration_seconds * self.sample_rate))]

                audio = await asyncio.to_thread(_generate)
                return self._encode_audio(audio, output_format, seed)

            finally:
                self._in_use -= 1

        except Exception as e:
            logger.error(f"[STABLE-AUDIO] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise GenerationFailed(str(e) or e.__class__.__name__) from e

    async def generate_from_embeddings(
        self,
        prompt_embeds,  # torch.Tensor [B, seq, 768]
        attention_mask=None,  # torch.Tensor [B, seq] or None
        seconds_start: float = 0.0,
        seconds_end: float = 10.0,
        negative_prompt: str = "",
        steps: int = SA3_DEFAULT_STEPS,
        cfg_scale: float = SA3_DEFAULT_CFG_SCALE,
        seed: int = -1,
    ) -> Optional[bytes]:
        """
        Generate audio from pre-computed t5gemma conditioning (Latent Synth / cross-aesthetic).

        The manipulated prompt embedding is injected directly into the conditioning_tensors dict
        and passed to generate_diffusion_cond_inpaint — bypassing text encoding.

        NOTE (SA3 behavior change): SA3 has no `seconds_start` conditioner. `seconds_start` is kept
        for API compatibility but the temporal OFFSET is inert; only the duration
        (seconds_end - seconds_start) is used. See MIGRATION_DESIGN.md §6 (`start_position`).

        CFG correctness: the negative branch uses zeros in the SAME conditioning space
        (zeros_like(prompt_embeds)), not a text-encoded "". For cross-modal / manipulated
        embeddings the two spaces differ, so a text negative would make the CFG subtraction
        meaningless. (Preserved from the SA1 implementation.)

        ⚠️ LATENT-SYNTH AMPLIFICATION CAVEAT (SA3): SA1 amplified embedding-steering by running
        at cfg≈7 against a zeros-negative (CFG pushes the sample away from the neutral baseline,
        magnifying the axis manipulation). SA3 medium's documented operating point is cfg=1.0,
        where that amplification VANISHES — the steering then lives entirely in the injected
        embedding. The perceptual strength of the semantic axes may therefore differ from SA1.
        cfg_scale is parametrized so callers can dial guidance back up, but high cfg on a
        distilled few-step model can over-saturate. This MUST be validated perceptually once
        GPU VRAM is available (see MIGRATION_DESIGN §5/§8).
        """
        try:
            import torch
            # SA3 medium's DiT requires inpaint local-conditioning (local_add_cond_ids:
            # inpaint_mask, inpaint_masked_input). Only generate_diffusion_cond_inpaint
            # supplies them — with inpaint_audio=None it sets zeros (= pure generation),
            # which is exactly the t2a path the model card uses. Plain generate_diffusion_cond
            # omits these conds and would fail/produce garbage on this model.
            from stable_audio_tools.inference.generation import generate_diffusion_cond_inpaint

            if not self._is_loaded:
                if not await self._load_pipeline():
                    return None

            self._in_use += 1
            self._last_used = time.time()

            try:
                duration = max(0.1, min(seconds_end - seconds_start, self.max_duration))

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                model_dtype = next(self.model.model.parameters()).dtype
                prompt_embeds = prompt_embeds.to(device=self.device, dtype=model_dtype)
                if attention_mask is not None:
                    attention_mask = attention_mask.to(device=self.device).bool()
                else:
                    attention_mask = torch.ones(
                        prompt_embeds.shape[:2], device=self.device, dtype=torch.bool
                    )

                # Build the conditioning_tensors dict. We reuse the conditioner ONLY to obtain
                # the seconds_total tensor (cheap; the prompt is overridden by the injected embed).
                def _generate():
                    with torch.no_grad():
                        base = self.model.conditioner(
                            [{"prompt": "", "seconds_total": duration}], self.device
                        )
                        seconds_tensor = base["seconds_total"]

                        cond_tensors = {
                            "prompt": [prompt_embeds, attention_mask],
                            "seconds_total": seconds_tensor,
                        }
                        neg_tensors = {
                            "prompt": [
                                torch.zeros_like(prompt_embeds),
                                torch.ones_like(attention_mask),
                            ],
                            "seconds_total": seconds_tensor,
                        }

                        sample_size = self._aligned_sample_size(duration)
                        audio = generate_diffusion_cond_inpaint(
                            self.model,
                            conditioning_tensors=cond_tensors,
                            negative_conditioning_tensors=neg_tensors,
                            steps=steps,
                            cfg_scale=cfg_scale,
                            sample_size=sample_size,
                            seed=seed,
                            device=self.device,
                            sampler_type=SA3_SAMPLER_TYPE,  # RF sampler (see generate_audio)
                        )
                    audio = self._postprocess(audio[0])
                    return audio[:, : int(round(duration * self.sample_rate))]

                logger.info(
                    f"[STABLE-AUDIO] Generating from embeddings: "
                    f"shape={list(prompt_embeds.shape)}, duration={duration}s, "
                    f"steps={steps}, seed={seed}"
                )

                audio = await asyncio.to_thread(_generate)
                return self._encode_audio(audio, "wav", seed)

            finally:
                self._in_use -= 1

        except Exception as e:
            logger.error(f"[STABLE-AUDIO] Embedding generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def encode_prompt(self, text: str):
        """
        Encode text via SA3's t5gemma conditioner.

        Exposes the conditioning step so callers (Latent Synth) can manipulate the embedding
        before generate_from_embeddings(). Returns the cross-attention prompt tensor only;
        the seconds_total used here is throwaway (re-applied at generation time).

        Returns:
            (prompt_embeds [1, 256, 768], attention_mask [1, 256]) or (None, None) on failure.
        """
        try:
            import torch

            if not self._is_loaded:
                if not await self._load_pipeline():
                    return None, None

            self._last_used = time.time()

            def _encode():
                with torch.no_grad():
                    cond = self.model.conditioner(
                        [{"prompt": text, "seconds_total": 10.0}], self.device
                    )
                # conditioner returns {"prompt": [emb [1,256,768], mask [1,256]], ...}
                emb, mask = cond["prompt"]
                return emb, mask

            prompt_embeds, attention_mask = await asyncio.to_thread(_encode)
            logger.info(
                f"[STABLE-AUDIO] Encoded prompt: shape={list(prompt_embeds.shape)}, "
                f"text='{text[:60]}'"
            )
            return prompt_embeds, attention_mask

        except Exception as e:
            logger.error(f"[STABLE-AUDIO] Prompt encoding error: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    async def generate_audio_with_guidance(
        self,
        image_bytes: bytes,
        prompt: str = "",
        lambda_guidance: float = 0.1,
        warmup_steps: int = 10,
        total_steps: int = SA3_DEFAULT_STEPS,
        duration_seconds: float = 10.0,
        cfg_scale: float = SA3_DEFAULT_CFG_SCALE,
        seed: int = -1,
    ) -> Optional[Dict[str, Any]]:
        """
        Image-to-audio via ImageBind gradient guidance (SA3 RF sampler implementation).

        Implements a custom pingpong guided sampling loop, since stable-audio-tools does
        not support cond_fn for rf_denoiser objectives. At each warmup step:
          1. Forward pass with grad: x0_pred = x - t * model(x, t, **cond)
          2. Decode x0_pred → audio → differentiable mel (kaldi.fbank, no file I/O)
          3. IB audio embedding → cosine similarity with image_emb → backprop → grad_z
          4. Clip grad norm (stability), apply: x ← x + lambda_guidance * grad_z
          5. Rerun forward (no_grad) for the pingpong denoising step
        After warmup_steps the loop continues unguided.

        Caller contract (preserved from SA1): returns dict with
            audio_bytes, cosine_similarity, seed, generation_time_ms.
        """
        import time as _time
        t_start = _time.time()

        try:
            import torch
            import torch.nn.functional as F
            import torchaudio
            import torchaudio.functional as ta_f

            if not self._is_loaded:
                if not await self._load_pipeline():
                    return None

            from services.imagebind_backend import get_imagebind_backend
            imagebind = get_imagebind_backend()

            image_emb = await imagebind.encode_image(image_bytes)
            if image_emb is None:
                logger.error("[STABLE-AUDIO-GUIDED] ImageBind image encoding failed")
                return None
            image_emb = image_emb.to(self.device).detach()  # [1, 1024]

            ib_model = imagebind._model
            if ib_model is None:
                logger.error("[STABLE-AUDIO-GUIDED] ImageBind model not loaded after encode_image")
                return None

            if seed == -1:
                import random
                seed = random.randint(0, 2**32 - 1)

            duration_seconds = min(duration_seconds, self.max_duration)
            effective_warmup = min(warmup_steps, total_steps)

            self._in_use += 1
            self._last_used = _time.time()

            try:
                def _guided_generate():
                    from stable_audio_tools.inference.sampling import build_schedule
                    from imagebind.models.imagebind_model import ModalityType

                    torch.manual_seed(seed)

                    sample_size = self._aligned_sample_size(duration_seconds)
                    latent_size = sample_size // self._downsampling_ratio
                    batch_size = 1

                    model_dtype = next(self.model.model.parameters()).dtype
                    pretransform = self.model.pretransform
                    pretransform_dtype = next(pretransform.parameters()).dtype

                    # Build conditioning tensors (mirrors generate_diffusion_cond_inpaint)
                    cond_tensors = self.model.conditioner(
                        [{"prompt": prompt, "seconds_total": duration_seconds}], self.device
                    )
                    neg_tensors = self.model.conditioner(
                        [{"prompt": "", "seconds_total": duration_seconds}], self.device
                    )

                    # SA3 medium requires inpaint local conditioning (zeros = pure generation)
                    zero_mask = torch.zeros(
                        (batch_size, 1, latent_size), device=self.device
                    )
                    zero_input = torch.zeros(
                        (batch_size, self.model.io_channels, latent_size), device=self.device
                    )
                    cond_tensors["inpaint_mask"] = [zero_mask]
                    cond_tensors["inpaint_masked_input"] = [zero_input]
                    neg_tensors["inpaint_mask"] = [zero_mask]
                    neg_tensors["inpaint_masked_input"] = [zero_input]

                    cond_inputs = self.model.get_conditioning_inputs(cond_tensors)
                    neg_cond_inputs = self.model.get_conditioning_inputs(
                        neg_tensors, negative=True
                    )
                    # The conditioner is a full text encoder and runs in grad mode here,
                    # so its outputs carry a graph -- and the same graph is reused by every
                    # guidance step. The first backward() frees it and the next step dies
                    # with "backward through the graph a second time". The conditioning is
                    # a constant for the guidance, so cut it loose from the graph.
                    cond_inputs = {
                        k: (v.detach().type(model_dtype) if torch.is_tensor(v) else v)
                        for k, v in cond_inputs.items()
                    }
                    neg_cond_inputs = {
                        k: (v.detach() if torch.is_tensor(v) else v)
                        for k, v in neg_cond_inputs.items()
                    }

                    # Merged pos+neg conditioning for batch_cfg (matches generate_diffusion_cond_inpaint)
                    extra_args = {
                        **cond_inputs,
                        **neg_cond_inputs,
                        "cfg_scale": cfg_scale,
                        "batch_cfg": True,
                        "rescale_cfg": True,
                    }

                    # RF schedule
                    sigmas = build_schedule(
                        steps=total_steps,
                        sigma_max=1.0,
                        dist_shift=getattr(self.model, "sampling_dist_shift", None),
                        effective_seq_len=None,
                        fallback_seq_len=latent_size,
                        include_endpoint=True,
                        device=self.device,
                    )

                    noise = torch.randn(
                        [batch_size, self.model.io_channels, latent_size],
                        dtype=model_dtype, device=self.device,
                    )

                    # ImageBind audio constants (from ImageBind/imagebind/data.py)
                    IB_SR = 16000
                    IB_N_MELS = 128
                    IB_TARGET_LEN = 204
                    IB_CLIP_DUR = 2.0
                    IB_N_CLIPS = 3
                    IB_MEAN = -4.268
                    IB_STD = 9.138
                    IB_CLIP_SAMPLES = int(IB_CLIP_DUR * IB_SR)  # 32000

                    def waveform_to_imagebind_tensor(audio):
                        """
                        Differentiable analog of ImageBind load_and_transform_audio_data.
                        audio: [B, channels, n_samples] at self.sample_rate (SA3: stereo, 44100 Hz)
                        Returns: [B, 3, 1, 128, 204] ready for imagebind_model({AUDIO: ...})
                        """
                        # Mono
                        w = audio.mean(dim=1, keepdim=True) if audio.shape[1] > 1 else audio

                        # Resample to 16 kHz (differentiable sinc filter)
                        if self.sample_rate != IB_SR:
                            w = ta_f.resample(w, self.sample_rate, IB_SR)
                        # w: [B, 1, n_samples_16k]

                        n_samples = w.shape[-1]
                        duration_w = n_samples / IB_SR
                        available = max(0.0, duration_w - IB_CLIP_DUR)

                        # Uniform clip start positions (matches ConstantClipsPerVideoSampler)
                        if IB_N_CLIPS > 1:
                            starts = [i / (IB_N_CLIPS - 1) * available for i in range(IB_N_CLIPS)]
                        else:
                            starts = [0.0]

                        B_ = w.shape[0]
                        clips_out = []
                        for pos in starts:
                            s = int(pos * IB_SR)
                            e = s + IB_CLIP_SAMPLES
                            clip = w[..., s:e]
                            if clip.shape[-1] < IB_CLIP_SAMPLES:
                                clip = F.pad(clip, (0, IB_CLIP_SAMPLES - clip.shape[-1]))

                            mel_batch = []
                            for b in range(B_):
                                wb = clip[b]  # [1, IB_CLIP_SAMPLES]
                                wb = wb - wb.mean()
                                # kaldi.fbank: [1, n_samp] → [n_frames, n_mels], autograd-ok
                                fb = torchaudio.compliance.kaldi.fbank(
                                    wb, htk_compat=True, sample_frequency=IB_SR,
                                    use_energy=False, window_type="hanning",
                                    num_mel_bins=IB_N_MELS, dither=0.0,
                                    frame_length=25, frame_shift=10,
                                )
                                fb = fb.transpose(0, 1)  # [n_mels, n_frames]
                                n_f = fb.shape[1]
                                if n_f < IB_TARGET_LEN:
                                    fb = F.pad(fb, (0, IB_TARGET_LEN - n_f))
                                else:
                                    fb = fb[:, :IB_TARGET_LEN]
                                fb = fb.unsqueeze(0)  # [1, n_mels, target_len]
                                fb = (fb - IB_MEAN) / IB_STD
                                mel_batch.append(fb)

                            mel_batch = torch.stack(mel_batch, dim=0)  # [B, 1, 128, 204]
                            clips_out.append(mel_batch)

                        return torch.stack(clips_out, dim=1)  # [B, n_clips, 1, 128, 204]

                    # Guided pingpong loop (replicates sample_flow_pingpong with grad injection)
                    x = noise
                    t = sigmas
                    num_steps = t.shape[-1] - 1
                    last_cos_sim = 0.0

                    logger.info(
                        f"[STABLE-AUDIO-GUIDED] Starting: total_steps={total_steps}, "
                        f"warmup={effective_warmup}, lambda={lambda_guidance}, "
                        f"duration={duration_seconds}s, seed={seed}"
                    )

                    for i in range(num_steps):
                        t_curr = t[i].to(x.dtype)
                        t_next = t[i + 1].to(x.dtype)
                        t_curr_tensor = t_curr * torch.ones(
                            (batch_size,), dtype=x.dtype, device=self.device
                        )

                        if i < effective_warmup:
                            try:
                                with torch.enable_grad():
                                    z = x.detach().requires_grad_(True)
                                    # The DiT's attention lowers to Triton's FlexAttention.
                                    # In float32 its BACKWARD kernels ask for 128-224 KB of
                                    # shared memory per block; this card offers 99 KB, so
                                    # autotuning finds no valid config and the guided step
                                    # dies without ever producing audio. In bfloat16 the
                                    # kernel fits. Only the DiT runs reduced: the
                                    # autoencoder below stays float32 for decode stability,
                                    # and the gradient is norm-clipped further down anyway,
                                    # so it is used as a direction, not as a precise value.
                                    with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
                                        v = self.model.model(z, t_curr_tensor, **extra_args)
                                    v = v.to(z.dtype)
                                    x0_pred = z - t_curr * v

                                    # Decode latent → audio (differentiable)
                                    with _grad_through_decode(pretransform):
                                        audio_pred = pretransform.decode(
                                            x0_pred.to(pretransform_dtype)
                                        )

                                    # Differentiable mel → ImageBind embedding
                                    ib_input = waveform_to_imagebind_tensor(
                                        audio_pred.to(torch.float32)
                                    )
                                    ib_out = ib_model({ModalityType.AUDIO: ib_input})
                                    audio_emb = ib_out[ModalityType.AUDIO]  # [B, 1024]

                                    cos_sim = F.cosine_similarity(
                                        audio_emb, image_emb, dim=-1
                                    ).mean()
                                    cos_sim.backward()

                                if z.grad is not None:
                                    grad = z.grad.detach()
                                    grad_norm = grad.norm()
                                    if torch.isnan(grad_norm) or torch.isinf(grad_norm):
                                        logger.warning(
                                            f"[STABLE-AUDIO-GUIDED] Step {i}: "
                                            f"NaN/inf gradient, skipping guidance"
                                        )
                                    else:
                                        # Clip gradient norm for stability across image types;
                                        # do NOT scale by t_curr (not standard classifier guidance)
                                        MAX_GRAD_NORM = 1.0
                                        if grad_norm > MAX_GRAD_NORM:
                                            grad = grad * (MAX_GRAD_NORM / grad_norm)
                                        x = (x + lambda_guidance * grad).detach()
                                        last_cos_sim = cos_sim.item()
                                        logger.debug(
                                            f"[STABLE-AUDIO-GUIDED] Step {i}: "
                                            f"cos_sim={last_cos_sim:.4f}, "
                                            f"grad_norm={min(grad_norm.item(), MAX_GRAD_NORM):.4f}"
                                        )
                                else:
                                    # A missing gradient is not a harmless case: the step
                                    # then runs unguided while the page still reports a
                                    # guided run. Say so.
                                    logger.warning(
                                        f"[STABLE-AUDIO-GUIDED] Step {i}: no gradient "
                                        f"reached the latent, step ran unguided"
                                    )
                            except Exception as step_err:
                                logger.warning(
                                    f"[STABLE-AUDIO-GUIDED] Guidance step {i} failed "
                                    f"(continuing unguided): {step_err}",
                                    exc_info=True,
                                )

                        # Denoising step (no grad, on post-guidance x)
                        with torch.no_grad():
                            v2 = self.model.model(x, t_curr_tensor, **extra_args)
                            denoised = x - t_curr * v2

                        # Pingpong: fresh noise reinjection (matches sample_flow_pingpong)
                        x = (1 - t_next) * denoised + t_next * torch.randn_like(x)

                    # Decode final latent
                    with torch.no_grad():
                        audio = pretransform.decode(x.to(pretransform_dtype))

                    return audio, last_cos_sim

                audio_tensor, final_cos_sim = await asyncio.to_thread(_guided_generate)

                audio = self._postprocess(audio_tensor[0])
                audio = audio[:, : int(round(duration_seconds * self.sample_rate))]
                audio_bytes = self._encode_audio(audio, "wav", seed)

                if audio_bytes is None:
                    return None

                return {
                    "audio_bytes": audio_bytes,
                    "cosine_similarity": float(final_cos_sim),
                    "seed": seed,
                    "generation_time_ms": int((_time.time() - t_start) * 1000),
                }

            finally:
                self._in_use -= 1

        except Exception as e:
            logger.error(f"[STABLE-AUDIO-GUIDED] Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_vae(self):
        """Get the autoencoder (pretransform) for cross-aesthetic latent decoding."""
        if not self._is_loaded or self.model is None:
            return None
        return self.model.pretransform

    def _encode_audio(self, audio, output_format: str, seed: int) -> Optional[bytes]:
        """Encode an audio tensor/array [channels, samples] to bytes."""
        import numpy as np

        try:
            if hasattr(audio, "cpu"):
                audio_np = audio.cpu().float().numpy()
            else:
                audio_np = np.array(audio)

            # soundfile expects [samples, channels]
            if audio_np.ndim == 2:
                audio_np = audio_np.T

            if output_format == "mp3":
                return self._encode_mp3(audio_np)
            return self._encode_wav(audio_np)

        except Exception as e:
            logger.error(f"[STABLE-AUDIO] Audio encoding error: {e}")
            return None

    def _encode_wav(self, audio_np) -> bytes:
        import io
        import soundfile as sf

        buffer = io.BytesIO()
        sf.write(buffer, audio_np, self.sample_rate, format="WAV")
        buffer.seek(0)
        return buffer.getvalue()

    def _encode_mp3(self, audio_np) -> bytes:
        import io

        try:
            from pydub import AudioSegment
            wav_bytes = self._encode_wav(audio_np)
            audio_segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))
            mp3_buffer = io.BytesIO()
            audio_segment.export(mp3_buffer, format="mp3", bitrate="192k")
            mp3_buffer.seek(0)
            return mp3_buffer.getvalue()
        except ImportError:
            logger.warning("[STABLE-AUDIO] pydub not available, falling back to WAV")
            return self._encode_wav(audio_np)


# =============================================================================
# Singleton
# =============================================================================

_backend: Optional[StableAudioGenerator] = None


def get_stable_audio_backend() -> StableAudioGenerator:
    global _backend
    if _backend is None:
        _backend = StableAudioGenerator()
    return _backend


def reset_stable_audio_backend():
    global _backend
    _backend = None
