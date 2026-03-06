"""
Hunyuan3D-2 Backend — Text-to-3D Mesh Generation

Generates textured 3D meshes (GLB) from text prompts using Tencent's Hunyuan3D-2.
Architecture: Shape generation (1.1B DiT) → Texture painting (1.3B Paint) → GLB export.

Features:
- Text-to-3D mesh generation with textures
- GLB export (universal 3D format, compatible with <model-viewer>)
- On-demand lazy loading (~16 GB VRAM total)
- VRAM management with coordinator integration

Usage:
    backend = get_hunyuan3d_backend()
    if await backend.is_available():
        glb_bytes = await backend.generate_mesh(prompt="a red apple")
"""

import logging
import time
from typing import Optional, Dict, Any, List
import asyncio

logger = logging.getLogger(__name__)


class Hunyuan3DBackend:
    """
    3D mesh generation using Hunyuan3D-2 (tencent/Hunyuan3D-2).

    Supports:
    - Text-to-3D mesh generation (Shape + Texture pipeline)
    - GLB export via trimesh
    - Lazy model loading for VRAM efficiency
    - VRAM coordinator integration for cross-backend eviction
    """

    def __init__(self):
        from config import (
            HUNYUAN3D_ENABLED,
            HUNYUAN3D_MODEL_ID,
            HUNYUAN3D_DEVICE,
            HUNYUAN3D_DTYPE,
        )

        self.enabled = HUNYUAN3D_ENABLED
        self.model_id = HUNYUAN3D_MODEL_ID
        self.device = HUNYUAN3D_DEVICE
        self.dtype_str = HUNYUAN3D_DTYPE

        # Pipelines (lazy-loaded)
        self._shape_pipeline = None
        self._texture_pipeline = None
        self._is_loaded = False
        self._vram_mb: float = 0
        self._last_used: float = 0
        self._in_use: int = 0

        self._register_with_coordinator()

        logger.info(
            f"[HUNYUAN3D] Initialized: model={self.model_id}, "
            f"device={self.device}, enabled={self.enabled}"
        )

    def _register_with_coordinator(self):
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[HUNYUAN3D] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[HUNYUAN3D] Failed to register with VRAM coordinator: {e}")

    # =========================================================================
    # VRAMBackend Protocol
    # =========================================================================

    def get_backend_id(self) -> str:
        return "hunyuan3d"

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
        """Check if Hunyuan3D-2 dependencies are available."""
        if not self.enabled:
            return False
        try:
            import hy3dgen  # noqa: F401
            return True
        except ImportError:
            logger.error("[HUNYUAN3D] hy3dgen not installed")
            return False

    async def _load_pipeline(self) -> bool:
        """Lazy-load the Hunyuan3D-2 shape and texture pipelines."""
        if self._is_loaded:
            return True

        try:
            import torch

            # Request VRAM from coordinator (~16GB estimated)
            try:
                from services.vram_coordinator import get_vram_coordinator, EvictionPriority
                coordinator = get_vram_coordinator()
                coordinator.request_vram("hunyuan3d", 16000, EvictionPriority.NORMAL)
            except Exception as e:
                logger.warning(f"[HUNYUAN3D] VRAM coordinator request failed: {e}")

            logger.info(f"[HUNYUAN3D] Loading pipelines from {self.model_id}...")

            dtype_map = {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}
            torch_dtype = dtype_map.get(self.dtype_str, torch.float16)

            vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

            def _load():
                from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
                from hy3dgen.texgen import Hunyuan3DPaintPipeline

                shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
                    self.model_id,
                    subfolder="hunyuan3d-dit-v2-0",
                    torch_dtype=torch_dtype,
                    device=self.device,
                )

                texture_pipe = Hunyuan3DPaintPipeline.from_pretrained(
                    self.model_id,
                )

                return shape_pipe, texture_pipe

            self._shape_pipeline, self._texture_pipeline = await asyncio.to_thread(_load)
            self._is_loaded = True
            self._last_used = time.time()

            vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
            self._vram_mb = (vram_after - vram_before) / (1024 * 1024)

            logger.info(f"[HUNYUAN3D] Pipelines loaded (VRAM: {self._vram_mb:.0f}MB)")
            return True

        except Exception as e:
            logger.error(f"[HUNYUAN3D] Failed to load pipelines: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def unload_pipeline(self) -> bool:
        """Unload pipelines and free VRAM."""
        if not self._is_loaded:
            return False

        try:
            import torch

            del self._shape_pipeline
            del self._texture_pipeline
            self._shape_pipeline = None
            self._texture_pipeline = None
            self._is_loaded = False
            self._vram_mb = 0
            self._in_use = 0

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            logger.info("[HUNYUAN3D] Pipelines unloaded")
            return True

        except Exception as e:
            logger.error(f"[HUNYUAN3D] Error unloading pipelines: {e}")
            return False

    # =========================================================================
    # Generation
    # =========================================================================

    async def generate_mesh(
        self,
        prompt: str,
        seed: int = -1,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5,
        octree_resolution: int = 256,
    ) -> Optional[bytes]:
        """
        Generate a textured 3D mesh from a text prompt.

        Args:
            prompt: Text description of the 3D object
            seed: Seed for reproducibility (-1 = random)
            num_inference_steps: Number of shape generation steps
            guidance_scale: CFG scale for shape generation
            octree_resolution: Resolution of the octree mesh (higher = more detail)

        Returns:
            Tuple of (GLB bytes, actual_seed) or (None, seed) on failure
        """
        try:
            import torch

            if not self._is_loaded:
                if not await self._load_pipeline():
                    return None, seed

            self._in_use += 1
            self._last_used = time.time()

            try:
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                logger.info(
                    f"[HUNYUAN3D] Generating mesh: prompt='{prompt[:80]}...', "
                    f"steps={num_inference_steps}, cfg={guidance_scale}, seed={seed}"
                )

                def _generate():
                    import io
                    generator = torch.Generator(device=self.device).manual_seed(seed)

                    # Step 1: Shape generation (DiT flow matching)
                    with torch.no_grad():
                        mesh = self._shape_pipeline(
                            prompt=prompt,
                            num_inference_steps=num_inference_steps,
                            guidance_scale=guidance_scale,
                            generator=generator,
                            octree_resolution=octree_resolution,
                        )

                    # Step 2: Texture painting
                    with torch.no_grad():
                        textured_mesh = self._texture_pipeline(mesh, prompt=prompt)

                    # Step 3: Export to GLB
                    glb_buffer = io.BytesIO()
                    textured_mesh.export(glb_buffer, file_type="glb")
                    glb_buffer.seek(0)
                    return glb_buffer.getvalue()

                glb_bytes = await asyncio.to_thread(_generate)

                logger.info(f"[HUNYUAN3D] Mesh generated: {len(glb_bytes)} bytes (seed={seed})")
                return glb_bytes, seed

            finally:
                self._in_use -= 1

        except Exception as e:
            logger.error(f"[HUNYUAN3D] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None, seed


# =============================================================================
# Singleton
# =============================================================================

_backend: Optional[Hunyuan3DBackend] = None


def get_hunyuan3d_backend() -> Hunyuan3DBackend:
    global _backend
    if _backend is None:
        _backend = Hunyuan3DBackend()
    return _backend


def reset_hunyuan3d_backend():
    global _backend
    _backend = None
