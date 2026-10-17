"""
ImageBind Backend — Shared Embedding Space for Vision + Audio

ImageBind (Meta, 2023) provides a joint 1024d embedding space across
six modalities (image, audio, text, depth, thermal, IMU).

Used for gradient-based guidance during Stable Audio denoising:
the gradient of cosine similarity between image and audio embeddings
steers audio generation towards the visual content.

Features:
- Image encoding: bytes -> [1, 1024] L2-normalized embedding
- Audio encoding: waveform -> [1, 1024] L2-normalized embedding
- ~4.5GB VRAM when loaded
- Lazy loading with VRAM coordinator integration

Requirements:
    pip install imagebind-package (or clone from facebookresearch/ImageBind)

Usage:
    backend = get_imagebind_backend()
    image_emb = await backend.encode_image(image_bytes)
    audio_emb = await backend.encode_audio(waveform_tensor, sample_rate=16000)
"""

import logging
import time
from typing import Optional, Dict, Any, List
import asyncio

logger = logging.getLogger(__name__)


class ImageBindBackend:
    """
    ImageBind embedding model for cross-modal gradient guidance.

    Implements VRAMBackend protocol for VRAM coordinator integration.
    """

    def __init__(self):
        from config import IMAGEBIND_MODEL_ID
        self.model_id = IMAGEBIND_MODEL_ID

        self._model = None
        self._is_loaded = False
        self._vram_mb: float = 0
        self._last_used: float = 0
        self._in_use: int = 0

        self._register_with_coordinator()
        logger.info(f"[IMAGEBIND] Initialized: model={self.model_id}")

    def _register_with_coordinator(self):
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[IMAGEBIND] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[IMAGEBIND] Failed to register: {e}")

    # =========================================================================
    # VRAMBackend Protocol
    # =========================================================================

    def get_backend_id(self) -> str:
        return "imagebind"

    def get_registered_models(self) -> List[Dict[str, Any]]:
        from services.vram_coordinator import EvictionPriority

        if not self._is_loaded:
            return []

        return [
            {
                "model_id": "imagebind_huge",
                "vram_mb": self._vram_mb,
                "priority": EvictionPriority.LOW,  # Easily evictable
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
        """Check if ImageBind can be loaded."""
        try:
            from imagebind.models import imagebind_model  # noqa: F401
            return True
        except ImportError:
            logger.warning("[IMAGEBIND] imagebind package not installed")
            return False

    async def _load(self) -> bool:
        """Load ImageBind model."""
        if self._is_loaded:
            return True

        try:
            import torch

            try:
                from services.vram_coordinator import get_vram_coordinator, EvictionPriority
                coordinator = get_vram_coordinator()
                coordinator.request_vram("imagebind", 5000, EvictionPriority.NORMAL)
            except Exception as e:
                logger.warning(f"[IMAGEBIND] VRAM request failed: {e}")

            logger.info("[IMAGEBIND] Loading ImageBind model...")
            vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

            def _load_sync():
                from imagebind.models import imagebind_model
                from imagebind.models.imagebind_model import ModalityType  # noqa: F401

                model = imagebind_model.imagebind_huge(pretrained=True)
                model = model.to("cuda").eval()
                return model

            self._model = await asyncio.to_thread(_load_sync)
            self._is_loaded = True
            self._last_used = time.time()

            vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
            self._vram_mb = (vram_after - vram_before) / (1024 * 1024)

            logger.info(f"[IMAGEBIND] Model loaded (VRAM: {self._vram_mb:.0f}MB)")
            return True

        except Exception as e:
            logger.error(f"[IMAGEBIND] Failed to load: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def unload(self) -> bool:
        """Unload ImageBind from GPU."""
        if not self._is_loaded:
            return False

        try:
            import torch
            del self._model
            self._model = None
            self._is_loaded = False
            self._vram_mb = 0
            self._in_use = 0

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("[IMAGEBIND] Model unloaded")
            return True
        except Exception as e:
            logger.error(f"[IMAGEBIND] Unload error: {e}")
            return False

    # =========================================================================
    # Encoding
    # =========================================================================

    async def encode_image(self, image_bytes: bytes):
        """
        Encode image to ImageBind embedding.

        Args:
            image_bytes: Raw image bytes (JPEG, PNG, etc.)

        Returns:
            torch.Tensor of shape [1, 1024], L2-normalized. None on failure.
        """
        if not self._is_loaded:
            if not await self._load():
                return None

        self._in_use += 1
        self._last_used = time.time()

        try:
            import torch
            from PIL import Image
            import io
            from imagebind.data import load_and_transform_vision_data
            from imagebind.models.imagebind_model import ModalityType
            import tempfile
            import os

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            def _encode():
                # ImageBind expects file paths for image input
                # Save temp file, load via their transform pipeline
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    image.save(f, format='PNG')
                    tmp_path = f.name

                try:
                    inputs = {
                        ModalityType.VISION: load_and_transform_vision_data(
                            [tmp_path], "cuda"
                        ),
                    }

                    with torch.no_grad():
                        embeddings = self._model(inputs)

                    return embeddings[ModalityType.VISION]  # [1, 1024]
                finally:
                    os.unlink(tmp_path)

            result = await asyncio.to_thread(_encode)
            logger.info(f"[IMAGEBIND] Image encoded: shape={list(result.shape)}")
            return result

        except Exception as e:
            logger.error(f"[IMAGEBIND] Image encoding error: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            self._in_use -= 1

    async def encode_audio(self, waveform, sample_rate: int = 16000):
        """
        Encode audio waveform to ImageBind embedding.

        ImageBind expects 2s clips @ 16kHz, 128-bin mel spectrogram.
        For longer audio, we take the first 2s.

        Args:
            waveform: torch.Tensor of shape [channels, samples] or [samples]
            sample_rate: Sample rate of the waveform

        Returns:
            torch.Tensor of shape [1, 1024], L2-normalized. None on failure.
        """
        if not self._is_loaded:
            if not await self._load():
                return None

        self._in_use += 1
        self._last_used = time.time()

        try:
            import torch
            import torchaudio
            from imagebind.data import load_and_transform_audio_data
            from imagebind.models.imagebind_model import ModalityType
            import tempfile
            import os

            def _encode():
                # Resample to 16kHz if needed
                wav = waveform
                if wav.dim() == 1:
                    wav = wav.unsqueeze(0)
                if wav.dim() == 3:
                    wav = wav.squeeze(0)

                if sample_rate != 16000:
                    resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                    wav = resampler(wav.cpu())

                # Mono
                if wav.shape[0] > 1:
                    wav = wav.mean(dim=0, keepdim=True)

                # Save to temp WAV file (ImageBind expects file paths)
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    torchaudio.save(f.name, wav.cpu(), 16000)
                    tmp_path = f.name

                try:
                    inputs = {
                        ModalityType.AUDIO: load_and_transform_audio_data(
                            [tmp_path], "cuda"
                        ),
                    }

                    with torch.no_grad():
                        embeddings = self._model(inputs)

                    return embeddings[ModalityType.AUDIO]  # [1, 1024]
                finally:
                    os.unlink(tmp_path)

            result = await asyncio.to_thread(_encode)
            logger.info(f"[IMAGEBIND] Audio encoded: shape={list(result.shape)}")
            return result

        except Exception as e:
            logger.error(f"[IMAGEBIND] Audio encoding error: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            self._in_use -= 1


# =============================================================================
# Singleton
# =============================================================================

_backend: Optional[ImageBindBackend] = None


def get_imagebind_backend() -> ImageBindBackend:
    global _backend
    if _backend is None:
        _backend = ImageBindBackend()
    return _backend


