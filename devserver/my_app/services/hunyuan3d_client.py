"""
Hunyuan3D HTTP Client — GPU Service Backend

Calls the shared GPU service (port 17803) for local Hunyuan3D-2 mesh generation.
Drop-in client with identical async signatures to the in-process backend.
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Hunyuan3DClient:
    """HTTP client for Hunyuan3D-2 on the local GPU service."""

    def __init__(self):
        from config import GPU_SERVICE_URL, GPU_SERVICE_TIMEOUT_3D
        self.base_url = GPU_SERVICE_URL.rstrip('/')
        self.timeout = GPU_SERVICE_TIMEOUT_3D

    def _post(self, path: str, data: dict) -> Optional[dict]:
        import requests
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=data, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            logger.error(f"[HUNYUAN3D-CLIENT] GPU service unreachable at {url}")
            return None
        except requests.Timeout:
            logger.error(f"[HUNYUAN3D-CLIENT] Timeout after {self.timeout}s: {path}")
            return None
        except Exception as e:
            logger.error(f"[HUNYUAN3D-CLIENT] Request failed: {e}")
            return None

    def _get(self, path: str) -> Optional[dict]:
        import requests
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[HUNYUAN3D-CLIENT] GET failed: {e}")
            return None

    async def is_available(self) -> bool:
        """Check if GPU service has Hunyuan3D-2 available."""
        import asyncio
        try:
            result = await asyncio.to_thread(self._get, '/api/hunyuan3d/available')
            return result is not None and result.get('available', False)
        except Exception:
            return False

    async def generate_mesh(
        self,
        prompt: str,
        seed: int = -1,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5,
        octree_resolution: int = 256,
    ) -> tuple:
        """
        Generate a 3D mesh from text prompt via local GPU service.

        Returns:
            Tuple of (GLB bytes, actual_seed) or (None, seed) on failure
        """
        import asyncio

        result = await asyncio.to_thread(self._post, '/api/hunyuan3d/generate', {
            'prompt': prompt,
            'seed': seed,
            'num_inference_steps': num_inference_steps,
            'guidance_scale': guidance_scale,
            'octree_resolution': octree_resolution,
        })

        if result is None or not result.get('success'):
            logger.error("[HUNYUAN3D-CLIENT] Mesh generation failed")
            return None, seed

        actual_seed = result.get('seed', seed)
        return base64.b64decode(result['mesh_base64']), actual_seed


# Singleton
_client: Optional[Hunyuan3DClient] = None


def get_hunyuan3d_client() -> Hunyuan3DClient:
    global _client
    if _client is None:
        _client = Hunyuan3DClient()
    return _client
