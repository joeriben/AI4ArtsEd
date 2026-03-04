"""
Stable Audio Backend - Direct Diffusers inference for audio generation

Session XXX: Audio generation backend using HuggingFace Diffusers StableAudioPipeline.
Replaces ComfyUI-based StableAudio generation with direct inference.

Features:
- Stable Audio Open 1.0 for text-to-audio generation
- Up to 47 seconds of audio per generation
- On-demand lazy loading (first request loads model)
- VRAM management with unload support
- MP3/WAV output formats

Usage:
    backend = get_stable_audio_backend()
    if await backend.is_available():
        audio_bytes = await backend.generate_audio(
            prompt="A gentle piano melody with soft strings",
            duration_seconds=30,
            output_format="mp3"
        )
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path
import asyncio
import io

logger = logging.getLogger(__name__)


class StableAudioGenerator:
    """
    Direct audio generation using HuggingFace Diffusers StableAudioPipeline

    Supports:
    - Stable Audio Open 1.0 (stabilityai/stable-audio-open-1.0)
    - Text-to-audio generation up to 47 seconds
    - Lazy model loading for VRAM efficiency
    - Configurable generation parameters
    """

    # Model configuration
    MODEL_ID = "stabilityai/stable-audio-open-1.0"
    MAX_DURATION_SECONDS = 47.0

    def __init__(self):
        """Initialize Stable Audio backend from registry config"""
        # Import registry to get config
        try:
            from my_app.services.backend_registry import get_backend_registry
            registry = get_backend_registry()
            config = registry.get_config("stable_audio")
        except ImportError:
            # Fallback if registry not available
            config = {}

        self.torch_dtype_str = config.get("torch_dtype", "float16")
        self.device = config.get("device", "cuda")
        self.max_duration = config.get("max_duration_seconds", self.MAX_DURATION_SECONDS)
        self.default_steps = config.get("default_steps", 100)
        self.default_cfg_scale = config.get("default_cfg_scale", 7.0)

        # Pipeline (lazy-loaded)
        self._pipeline = None
        self._is_loaded = False

        logger.info(f"[STABLE_AUDIO] Initialized: device={self.device}, dtype={self.torch_dtype_str}")

    def _get_torch_dtype(self):
        """Get torch dtype from config string"""
        import torch
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        return dtype_map.get(self.torch_dtype_str, torch.float16)

    async def is_available(self) -> bool:
        """
        Check if Stable Audio backend is available

        Returns:
            True if diffusers is installed and GPU is available
        """
        try:
            import torch
            from diffusers import StableAudioPipeline

            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("[STABLE_AUDIO] CUDA requested but not available")
                return False

            logger.info("[STABLE_AUDIO] Backend available")
            return True

        except ImportError as e:
            logger.error(f"[STABLE_AUDIO] Dependencies not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"[STABLE_AUDIO] Error checking availability: {e}")
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
        except Exception as e:
            logger.error(f"[STABLE_AUDIO] Error getting GPU info: {e}")
            return {"error": str(e)}

    async def _load_pipeline(self) -> bool:
        """
        Load Stable Audio pipeline into memory

        Returns:
            True if loaded successfully
        """
        if self._is_loaded:
            logger.info("[STABLE_AUDIO] Pipeline already loaded")
            return True

        try:
            import torch
            from diffusers import StableAudioPipeline

            logger.info(f"[STABLE_AUDIO] Loading pipeline from {self.MODEL_ID}...")

            # Load in thread to avoid blocking event loop
            def _load():
                pipe = StableAudioPipeline.from_pretrained(
                    self.MODEL_ID,
                    dtype=self._get_torch_dtype()
                )
                pipe = pipe.to(self.device)

                # Enable memory optimizations
                pipe.enable_attention_slicing()

                return pipe

            self._pipeline = await asyncio.to_thread(_load)
            self._is_loaded = True

            # Get GPU info after loading
            gpu_info = await self.get_gpu_info()
            logger.info(f"[STABLE_AUDIO] Pipeline loaded (VRAM: {gpu_info.get('allocated_gb', 'N/A')}GB)")

            return True

        except Exception as e:
            logger.error(f"[STABLE_AUDIO] Failed to load pipeline: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def unload_pipeline(self) -> bool:
        """
        Unload pipeline from memory to free VRAM

        Returns:
            True if unloaded successfully
        """
        if not self._is_loaded:
            logger.warning("[STABLE_AUDIO] Pipeline not loaded")
            return False

        try:
            import torch

            del self._pipeline
            self._pipeline = None
            self._is_loaded = False

            # Force CUDA memory cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            logger.info("[STABLE_AUDIO] Pipeline unloaded")
            return True

        except Exception as e:
            logger.error(f"[STABLE_AUDIO] Error unloading pipeline: {e}")
            return False

    async def generate_audio(
        self,
        prompt: str,
        negative_prompt: str = "",
        duration_seconds: float = 30.0,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        seed: int = -1,
        output_format: str = "mp3"
    ) -> Optional[bytes]:
        """
        Generate audio from text prompt

        Args:
            prompt: Text description of desired audio
            negative_prompt: Negative prompt (what to avoid)
            duration_seconds: Audio duration (max 47 seconds)
            steps: Number of inference steps (default from config)
            cfg_scale: Classifier-free guidance scale (default from config)
            seed: Random seed (-1 for random)
            output_format: Output format ('mp3' or 'wav')

        Returns:
            Audio bytes in specified format, or None on failure
        """
        try:
            import torch
            import scipy.io.wavfile as wavfile

            # Clamp duration
            duration_seconds = min(duration_seconds, self.max_duration)

            # Use defaults from config if not specified
            if steps is None:
                steps = self.default_steps
            if cfg_scale is None:
                cfg_scale = self.default_cfg_scale

            # Ensure pipeline is loaded
            if not self._is_loaded:
                if not await self._load_pipeline():
                    logger.error("[STABLE_AUDIO] Failed to load pipeline")
                    return None

            # Handle seed
            if seed == -1:
                import random
                seed = random.randint(0, 2**32 - 1)

            generator = torch.Generator(device=self.device).manual_seed(seed)

            logger.info(f"[STABLE_AUDIO] Generating: prompt='{prompt[:100]}...', duration={duration_seconds}s")
            logger.info(f"[STABLE_AUDIO] Parameters: steps={steps}, cfg={cfg_scale}, seed={seed}")

            # Generate in thread to avoid blocking
            def _generate():
                result = self._pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt if negative_prompt else None,
                    audio_end_in_s=duration_seconds,
                    num_inference_steps=steps,
                    guidance_scale=cfg_scale,
                    generator=generator
                )
                return result.audios[0]

            audio = await asyncio.to_thread(_generate)

            # Convert to bytes
            sample_rate = self._pipeline.vae.sampling_rate  # Usually 44100 Hz

            logger.info(f"[STABLE_AUDIO] Generated audio: shape={audio.shape}, sample_rate={sample_rate}")

            # Write WAV to buffer
            wav_buffer = io.BytesIO()

            # Transpose if needed (StableAudio outputs [channels, samples])
            if audio.ndim == 2 and audio.shape[0] < audio.shape[1]:
                audio = audio.T  # Transpose to [samples, channels]

            # Convert torch Tensor to numpy, then normalize to int16
            # (matches gpu_service/services/stable_audio_backend.py:778)
            import numpy as np
            audio_np = audio.cpu().float().numpy() if hasattr(audio, 'cpu') else audio
            audio_int16 = (audio_np * 32767).astype(np.int16)

            wavfile.write(wav_buffer, sample_rate, audio_int16)
            wav_bytes = wav_buffer.getvalue()

            # Convert to MP3 if requested
            if output_format.lower() == "mp3":
                try:
                    from pydub import AudioSegment

                    wav_buffer.seek(0)
                    audio_segment = AudioSegment.from_wav(wav_buffer)

                    mp3_buffer = io.BytesIO()
                    audio_segment.export(mp3_buffer, format="mp3", bitrate="192k")
                    audio_bytes = mp3_buffer.getvalue()

                    logger.info(f"[STABLE_AUDIO] Converted to MP3: {len(audio_bytes)} bytes")
                    return audio_bytes

                except ImportError:
                    logger.warning("[STABLE_AUDIO] pydub not installed, returning WAV")
                    return wav_bytes
                except Exception as e:
                    logger.warning(f"[STABLE_AUDIO] MP3 conversion failed: {e}, returning WAV")
                    return wav_bytes
            else:
                logger.info(f"[STABLE_AUDIO] Generated WAV: {len(wav_bytes)} bytes")
                return wav_bytes

        except Exception as e:
            logger.error(f"[STABLE_AUDIO] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None


# Singleton instance
_backend: Optional[StableAudioGenerator] = None


def get_stable_audio_backend() -> StableAudioGenerator:
    """
    Get Stable Audio backend singleton

    Returns:
        StableAudioGenerator instance
    """
    global _backend
    if _backend is None:
        _backend = StableAudioGenerator()
    return _backend


def reset_stable_audio_backend():
    """Reset the singleton backend (for testing)"""
    global _backend
    _backend = None
