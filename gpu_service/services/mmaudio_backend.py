"""
MMAudio Backend — CVPR 2025 Video/Image-to-Audio Generation

Dedicated crossmodal model trained on both visual and audio modalities.
157M parameters, flow matching (NOT diffusion), 25 Euler steps.
Generates up to 8s of 44.1kHz audio in ~1.2s.

Features:
- Image-to-audio generation (duplicates image as pseudo-video frames)
- Text-to-audio generation
- Combined image + text conditioning
- Lazy loading with VRAM coordinator integration
- ~6GB VRAM when loaded

Requirements:
    git clone https://github.com/hkchengrex/MMAudio
    pip install -e ./MMAudio

Usage:
    backend = get_mmaudio_backend()
    if await backend.is_available():
        audio_bytes = await backend.generate_from_image(image_bytes, prompt="fire crackling")
"""

import logging
import time
from typing import Optional, Dict, Any, List
import asyncio

logger = logging.getLogger(__name__)


class MMAudioBackend:
    """
    MMAudio generation backend.

    Implements VRAMBackend protocol for VRAM coordinator integration.
    Lazy-loads the model on first use.
    """

    def __init__(self):
        from config import MMAUDIO_MODEL, MMAUDIO_REPO

        self.model_variant = MMAUDIO_MODEL  # e.g. "large_44k_v2"
        self.repo_path = MMAUDIO_REPO

        self._model = None
        self._feature_utils = None
        self._net = None
        self._fm = None
        self._seq_cfg = None
        self._model_config = None
        self._is_loaded = False
        self._vram_mb: float = 0
        self._last_used: float = 0
        self._in_use: int = 0

        self._register_with_coordinator()
        logger.info(f"[MMAUDIO] Initialized: model={self.model_variant}, repo={self.repo_path}")

    def _register_with_coordinator(self):
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[MMAUDIO] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[MMAUDIO] Failed to register: {e}")

    # =========================================================================
    # VRAMBackend Protocol
    # =========================================================================

    def get_backend_id(self) -> str:
        return "mmaudio"

    def get_registered_models(self) -> List[Dict[str, Any]]:
        from services.vram_coordinator import EvictionPriority

        if not self._is_loaded:
            return []

        return [
            {
                "model_id": f"mmaudio_{self.model_variant}",
                "vram_mb": self._vram_mb,
                "priority": EvictionPriority.NORMAL,
                "last_used": self._last_used,
                "in_use": self._in_use,
            }
        ]

    def evict_model(self, model_id: str) -> bool:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.unload())
        finally:
            loop.close()

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def is_available(self) -> bool:
        """Check if MMAudio can be loaded."""
        try:
            import sys
            if self.repo_path not in sys.path:
                sys.path.insert(0, self.repo_path)
            import mmaudio  # noqa: F401
            return True
        except ImportError:
            logger.warning("[MMAUDIO] mmaudio package not importable")
            return False

    async def _load(self) -> bool:
        """Load MMAudio model and feature extractors."""
        if self._is_loaded:
            return True

        try:
            import torch
            import sys
            if self.repo_path not in sys.path:
                sys.path.insert(0, self.repo_path)

            try:
                from services.vram_coordinator import get_vram_coordinator, EvictionPriority
                coordinator = get_vram_coordinator()
                coordinator.request_vram("mmaudio", 6000, EvictionPriority.NORMAL)
            except Exception as e:
                logger.warning(f"[MMAUDIO] VRAM coordinator request failed: {e}")

            logger.info(f"[MMAUDIO] Loading model: {self.model_variant}...")
            vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

            def _load_sync():
                from mmaudio.eval_utils import all_model_cfg, setup_eval_logging
                from mmaudio.model.flow_matching import FlowMatching
                from mmaudio.model.networks import get_my_mmaudio
                from mmaudio.model.utils.features_utils import FeaturesUtils

                setup_eval_logging()

                model_config = all_model_cfg[self.model_variant]
                model_config.download_if_needed()
                seq_cfg = model_config.seq_cfg

                device = 'cuda'
                dtype = torch.bfloat16

                # Load network
                net = get_my_mmaudio(model_config.model_name).to(device, dtype).eval()
                net.load_weights(torch.load(model_config.model_path, map_location=device, weights_only=True))

                # Flow matching solver
                fm = FlowMatching(min_sigma=0, inference_mode='euler', num_steps=25)

                # Feature extractors (CLIP, synchformer, VAE, vocoder)
                feature_utils = FeaturesUtils(
                    tod_vae_ckpt=model_config.vae_path,
                    synchformer_ckpt=model_config.synchformer_ckpt,
                    enable_conditions=True,
                    mode=model_config.mode,
                    bigvgan_vocoder_ckpt=model_config.bigvgan_16k_path,
                    need_vae_encoder=False,
                )
                feature_utils = feature_utils.to(device, dtype).eval()

                return net, feature_utils, model_config, seq_cfg, fm

            self._net, self._feature_utils, self._model_config, self._seq_cfg, self._fm = await asyncio.to_thread(_load_sync)
            self._is_loaded = True
            self._last_used = time.time()

            vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
            self._vram_mb = (vram_after - vram_before) / (1024 * 1024)

            logger.info(f"[MMAUDIO] Model loaded (VRAM: {self._vram_mb:.0f}MB)")
            return True

        except Exception as e:
            logger.error(f"[MMAUDIO] Failed to load: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def unload(self) -> bool:
        """Unload MMAudio from GPU."""
        if not self._is_loaded:
            return False

        try:
            import torch

            del self._net
            del self._feature_utils
            del self._fm
            self._net = None
            self._feature_utils = None
            self._fm = None
            self._seq_cfg = None
            self._model_config = None
            self._is_loaded = False
            self._vram_mb = 0
            self._in_use = 0

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            logger.info("[MMAUDIO] Model unloaded")
            return True

        except Exception as e:
            logger.error(f"[MMAUDIO] Unload error: {e}")
            return False

    # =========================================================================
    # Generation
    # =========================================================================

    async def generate_from_image(
        self,
        image_bytes: bytes,
        prompt: str = "",
        negative_prompt: str = "",
        duration_seconds: float = 8.0,
        cfg_strength: float = 4.5,
        num_steps: int = 25,
        seed: int = -1,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate audio from an image (+ optional text prompt).

        MMAudio is a video-to-audio model. For image input, we duplicate
        the single frame to create pseudo-video input matching the expected
        temporal structure.

        Args:
            image_bytes: Input image as bytes
            prompt: Optional text conditioning
            negative_prompt: Negative text conditioning
            duration_seconds: Audio duration (max 8s)
            cfg_strength: Classifier-free guidance strength
            num_steps: Euler ODE solver steps
            seed: Random seed (-1 = random)

        Returns:
            Dict with audio_bytes, seed, generation_time_ms or None
        """
        import random as random_mod

        if not self._is_loaded:
            if not await self._load():
                return None

        self._in_use += 1
        self._last_used = time.time()
        start_time = time.time()

        try:
            import torch
            import tempfile
            from PIL import Image
            import io
            from pathlib import Path

            duration_seconds = min(duration_seconds, 8.0)
            if seed == -1:
                seed = random_mod.randint(0, 2**32 - 1)

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            def _generate():
                from mmaudio.eval_utils import generate, load_image

                # Save image to temp file (MMAudio load_image expects a path)
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    image.save(f, format='PNG')
                    tmp_path = Path(f.name)

                try:
                    with torch.inference_mode():
                        rng = torch.Generator(device='cuda')
                        rng.manual_seed(seed)

                        # Load and preprocess image using MMAudio's own transforms
                        image_info = load_image(tmp_path)
                        clip_frames = image_info.clip_frames.unsqueeze(0)  # [1, 3, H, W]

                        # Update sequence lengths for the requested duration
                        self._seq_cfg.duration = duration_seconds
                        self._net.update_seq_lengths(
                            self._seq_cfg.latent_seq_len,
                            self._seq_cfg.clip_seq_len,
                            self._seq_cfg.sync_seq_len,
                        )

                        # Use num_steps from request
                        self._fm.num_steps = num_steps

                        audios = generate(
                            clip_frames,
                            None,  # sync_frames not used for image input
                            [prompt] if prompt else [''],
                            negative_text=[negative_prompt] if negative_prompt else [''],
                            feature_utils=self._feature_utils,
                            net=self._net,
                            fm=self._fm,
                            rng=rng,
                            cfg_strength=cfg_strength,
                            image_input=True,
                        )
                        return audios.float().cpu()[0]  # [channels, T_audio]
                finally:
                    tmp_path.unlink(missing_ok=True)

            audio_tensor = await asyncio.to_thread(_generate)

            # Encode to WAV
            audio_bytes = self._encode_wav(audio_tensor)
            if audio_bytes is None:
                return None

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"[MMAUDIO] Generated from image: duration={duration_seconds}s, "
                f"time={elapsed_ms}ms, seed={seed}"
            )

            return {
                "audio_bytes": audio_bytes,
                "seed": seed,
                "generation_time_ms": elapsed_ms,
            }

        except Exception as e:
            logger.error(f"[MMAUDIO] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            self._in_use -= 1

    async def generate_from_text(
        self,
        prompt: str,
        negative_prompt: str = "",
        duration_seconds: float = 8.0,
        cfg_strength: float = 4.5,
        num_steps: int = 25,
        seed: int = -1,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate audio from text prompt only (no visual input).

        Args:
            prompt: Text description of desired audio
            negative_prompt: Negative text conditioning
            duration_seconds: Audio duration (max 8s)
            cfg_strength: CFG strength
            num_steps: Euler solver steps
            seed: Random seed

        Returns:
            Dict with audio_bytes, seed, generation_time_ms or None
        """
        import random as random_mod

        if not self._is_loaded:
            if not await self._load():
                return None

        self._in_use += 1
        self._last_used = time.time()
        start_time = time.time()

        try:
            import torch

            duration_seconds = min(duration_seconds, 8.0)
            if seed == -1:
                seed = random_mod.randint(0, 2**32 - 1)

            def _generate():
                from mmaudio.eval_utils import generate

                with torch.inference_mode():
                    rng = torch.Generator(device='cuda')
                    rng.manual_seed(seed)

                    # Update sequence lengths for the requested duration
                    self._seq_cfg.duration = duration_seconds
                    self._net.update_seq_lengths(
                        self._seq_cfg.latent_seq_len,
                        self._seq_cfg.clip_seq_len,
                        self._seq_cfg.sync_seq_len,
                    )

                    # Use num_steps from request
                    self._fm.num_steps = num_steps

                    audios = generate(
                        None,  # clip_video
                        None,  # sync_video
                        [prompt],
                        negative_text=[negative_prompt] if negative_prompt else [''],
                        feature_utils=self._feature_utils,
                        net=self._net,
                        fm=self._fm,
                        rng=rng,
                        cfg_strength=cfg_strength,
                    )
                    return audios.float().cpu()[0]

            audio_tensor = await asyncio.to_thread(_generate)

            audio_bytes = self._encode_wav(audio_tensor)
            if audio_bytes is None:
                return None

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"[MMAUDIO] Generated from text: prompt='{prompt[:60]}...', "
                f"duration={duration_seconds}s, time={elapsed_ms}ms"
            )

            return {
                "audio_bytes": audio_bytes,
                "seed": seed,
                "generation_time_ms": elapsed_ms,
            }

        except Exception as e:
            logger.error(f"[MMAUDIO] Text generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            self._in_use -= 1

    def _encode_wav(self, audio_tensor) -> Optional[bytes]:
        """Encode audio tensor to WAV bytes."""
        import io
        import numpy as np

        try:
            if hasattr(audio_tensor, 'cpu'):
                audio_np = audio_tensor.cpu().float().numpy()
            else:
                audio_np = np.array(audio_tensor)

            # Ensure [samples, channels] for soundfile
            if audio_np.ndim == 1:
                audio_np = audio_np[:, np.newaxis]
            elif audio_np.ndim == 2 and audio_np.shape[0] < audio_np.shape[1]:
                audio_np = audio_np.T  # [channels, samples] -> [samples, channels]
            elif audio_np.ndim == 3:
                audio_np = audio_np.squeeze(0).T

            # Use model's native sample rate (44100 for 44k variants, 16000 for 16k)
            sample_rate = self._seq_cfg.sampling_rate if self._seq_cfg else 44100

            import soundfile as sf
            buffer = io.BytesIO()
            sf.write(buffer, audio_np, sample_rate, format="WAV")
            buffer.seek(0)
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"[MMAUDIO] WAV encoding error: {e}")
            return None


# =============================================================================
# Singleton
# =============================================================================

_backend: Optional[MMAudioBackend] = None


def get_mmaudio_backend() -> MMAudioBackend:
    global _backend
    if _backend is None:
        _backend = MMAudioBackend()
    return _backend


