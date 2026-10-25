"""
Hunyuan3D client — one prompt of the platform's node, run by ComfyUI.

A mesh is one prompt of the node ai4artsed_hunyuan3d
(comfyui_nodes/ai4artsed_comfyui/), queued at ComfyUI and tracked the way a
picture is (services/llm_client.run_node_files); the GLB comes back as the
file the node announces under "3d". The checkpoint is a folder under
ComfyUI's models/hunyuan3d/, named by the table
config/local_media_weights.json. The async signatures are the ones the
callers had (the hunyuan3d chunk, the availability service). Until stage 6
of the move to ComfyUI this posted to the GPU service's
Hunyuan3D station.
"""

import logging
import random
from typing import Optional

from my_app.services.gpu_lease_client import GpuBusyError, BackendGenerationError
from my_app.utils.response_reason import reason_line

logger = logging.getLogger(__name__)

NODE_CLASS = "ai4artsed_hunyuan3d"
STATION = "hunyuan3d"


def _random_seed() -> int:
    return random.randint(0, 2**32 - 1)


class Hunyuan3DClient:
    """Hunyuan3D-2 on ComfyUI, through the platform's node."""

    def __init__(self):
        pass

    @staticmethod
    def _installed() -> list:
        """(alias, folder) of every whole Hunyuan3D snapshot under ComfyUI's
        models/hunyuan3d/, in table order, as the package reports them."""
        from my_app.services import local_media_weights, media_stations
        folders = media_stations.installed(STATION) if media_stations.available(STATION) else []
        return [(alias, (local_media_weights.entry(alias) or {}).get("dir"))
                for alias in local_media_weights.aliases_of_station(STATION)
                if (local_media_weights.entry(alias) or {}).get("dir") in folders]

    def _first_installed(self):
        installed = self._installed()
        return installed[0] if installed else None

    async def is_available(self) -> bool:
        """Whether a mesh can be made here now: the station's library
        imports in ComfyUI's venv and a snapshot of the table is whole."""
        import asyncio
        try:
            return await asyncio.to_thread(lambda: self._first_installed() is not None)
        except Exception as e:
            logger.warning(f"[HUNYUAN3D-CLIENT] availability unknown: {e}")
            return False

    def generate_mesh_sync(
        self,
        image_base64: str,
        seed: int = -1,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5,
        octree_resolution: int = 256,
    ) -> tuple:
        """(GLB bytes, the seed the mesh was made with). A run that ended
        without a mesh raises BackendGenerationError with the node's own
        sentence, and a card the gate holds for someone else raises
        GpuBusyError, as the service's answers did (the router reads "out of
        memory" and "device busy" off the sentence,
        backend_router._is_card_fault, and the busy travels to the surface as
        busy). A seed below zero is drawn here, the way the service drew
        one."""
        from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
        from my_app.services.llm_client import LLMClient
        found = self._first_installed()
        if found is None:
            raise BackendGenerationError(
                "no whole Hunyuan3D snapshot under ComfyUI's models/hunyuan3d")
        _alias, folder = found
        actual_seed = int(seed) if seed is not None and int(seed) >= 0 else _random_seed()
        inputs = {
            "model_name": folder,
            "seed": actual_seed,
            "num_inference_steps": int(num_inference_steps),
            "guidance_scale": float(guidance_scale),
            "octree_resolution": int(octree_resolution),
            "image_base64": image_base64,
        }
        try:
            out, files = LLMClient.run_node_files(NODE_CLASS, inputs,
                                                  workload=CURRENT_OUTPUT_CONFIG.get() or None)
        except GpuBusyError:
            raise
        except Exception as e:
            # Until 2026-09-14 every failure came back as (None, seed) and
            # reached the chunk as "returned empty result", the busy included.
            logger.error(f"[HUNYUAN3D-CLIENT] Mesh generation failed ({folder}): {e!r}")
            raise BackendGenerationError(reason_line(str(e) or repr(e), 300)) from e
        mesh = next((f for f in files if f.media_type == "mesh"), None)
        if mesh is None:
            logger.error(f"[HUNYUAN3D-CLIENT] the run ended without a mesh ({folder})")
            raise BackendGenerationError(f"the run of {NODE_CLASS} ({folder}) ended without a mesh")
        return mesh.data, int(out.get("seed", actual_seed))

    async def generate_mesh(
        self,
        image_base64: str,
        seed: int = -1,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5,
        octree_resolution: int = 256,
    ) -> tuple:
        """
        Generate a 3D mesh from an input image, on ComfyUI.

        Returns:
            Tuple of (GLB bytes, actual_seed); a failed run raises, see
            generate_mesh_sync
        """
        import asyncio
        return await asyncio.to_thread(
            self.generate_mesh_sync, image_base64, seed, num_inference_steps,
            guidance_scale, octree_resolution)


# Singleton
_client: Optional[Hunyuan3DClient] = None


def get_hunyuan3d_client() -> Hunyuan3DClient:
    global _client
    if _client is None:
        _client = Hunyuan3DClient()
    return _client
