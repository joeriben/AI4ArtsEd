"""
HeartMuLa client — one prompt of the platform's node, run by ComfyUI.

A song is one prompt of the node ai4artsed_heartmula
(comfyui_nodes/ai4artsed_comfyui/), queued at ComfyUI and tracked the way a
picture is (services/llm_client.run_node_files). The checkpoint tree
(HeartMuLa, HeartCodec) is a folder under ComfyUI's models/heartmula/, named
by the table config/local_media_weights.json. The async API: is_available,
generate_music (heartmula_backend hands this client out). Until stage 6 of
the move to ComfyUI it posted to the GPU service's /api/heartmula/*.
"""

import logging
import random
from typing import Optional

from my_app.services.gpu_lease_client import GpuBusyError, BackendGenerationError
from my_app.utils.response_reason import reason_line

logger = logging.getLogger(__name__)

NODE_CLASS = "ai4artsed_heartmula"
STATION = "heartmula"


def _random_seed() -> int:
    return random.randint(0, 2**32 - 1)


class HeartMuLaClient:
    """HeartMuLa on ComfyUI, through the platform's node.

    Took the place of the in-process HeartMuLaMusicGenerator, which went with
    the GPU service's station on 2026-10-10.
    """

    def __init__(self):
        logger.info("[HEARTMULA-CLIENT] Initialized: the node on ComfyUI")

    @staticmethod
    def _installed() -> list:
        """(alias, folder, version) of every whole HeartMuLa checkpoint tree
        under ComfyUI's models/heartmula/, in table order, as the package
        reports them (services/media_stations)."""
        from my_app.services import local_media_weights, media_stations
        folders = media_stations.installed(STATION) if media_stations.available(STATION) else []
        out = []
        for alias in local_media_weights.aliases_of_station(STATION):
            e = local_media_weights.entry(alias) or {}
            if e.get("dir") in folders:
                out.append((alias, e["dir"], str(e.get("version") or "")))
        return out

    def _first_installed(self):
        installed = self._installed()
        return installed[0] if installed else None

    async def is_available(self) -> bool:
        """Whether a song can be made here now: the station's library imports
        in ComfyUI's venv and a checkpoint tree of the table is whole."""
        import asyncio
        try:
            return await asyncio.to_thread(lambda: self._first_installed() is not None)
        except Exception as e:
            logger.warning(f"[HEARTMULA-CLIENT] availability unknown: {e}")
            return False

    def preload_workflow(self) -> Optional[dict]:
        """The one-node prompt that puts the song models on the card without
        making a song (the node's preload_only), for the workshop preload of
        the settings page; None when no checkpoint tree is whole."""
        found = self._first_installed()
        if found is None:
            return None
        _alias, folder, version = found
        from my_app.services.llm_client import NODE_ID
        return {NODE_ID: {"class_type": NODE_CLASS, "inputs": {
            "model_name": folder, "lyrics": "", "tags": "", "seed": 0,
            "version": version, "preload_only": True,
        }}}

    def generate_music_sync(
        self,
        lyrics: str,
        tags: str,
        temperature: float = 1.0,
        topk: int = 70,
        cfg_scale: float = 3.0,
        max_audio_length_ms: int = 240000,
        seed: Optional[int] = None,
        output_format: str = "mp3",
    ) -> bytes:
        """The song as bytes in `output_format`. A run that ended without
        one raises BackendGenerationError with the node's own sentence, and
        a card the gate holds for someone else raises GpuBusyError, as the
        service's answers did (the router reads "out of memory" and "device
        busy" off the sentence, backend_router._is_card_fault, and the busy
        travels to the surface as busy). A seed of None or below zero is
        drawn here, the way the service drew one."""
        from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
        from my_app.services.llm_client import LLMClient
        found = self._first_installed()
        if found is None:
            raise BackendGenerationError(
                "no whole HeartMuLa checkpoint tree under ComfyUI's models/heartmula")
        _alias, folder, version = found
        inputs = {
            "model_name": folder,
            "lyrics": lyrics or "",
            "tags": tags or "",
            "seed": int(seed) if seed is not None and int(seed) >= 0 else _random_seed(),
            "version": version,
            "temperature": float(temperature),
            "topk": int(topk),
            "cfg_scale": float(cfg_scale),
            "max_audio_length_ms": int(max_audio_length_ms),
            "output_format": output_format,
            "preload_only": False,
        }
        try:
            _out, files = LLMClient.run_node_files(NODE_CLASS, inputs,
                                                   workload=CURRENT_OUTPUT_CONFIG.get() or None)
        except GpuBusyError:
            raise
        except Exception as e:
            # Until 2026-09-14 every failure came back as None and reached
            # the chunk as "Music generation failed", the busy included.
            logger.error(f"[HEARTMULA-CLIENT] Generation failed ({folder}): {e!r}")
            raise BackendGenerationError(reason_line(str(e) or repr(e), 300)) from e
        sound = next((f for f in files if f.media_type == "audio"), None)
        if sound is None:
            logger.error(f"[HEARTMULA-CLIENT] the run ended without a song ({folder})")
            raise BackendGenerationError(f"the run of {NODE_CLASS} ({folder}) ended without a song")
        return sound.data

    async def generate_music(
        self,
        lyrics: str,
        tags: str,
        temperature: float = 1.0,
        topk: int = 70,
        cfg_scale: float = 3.0,
        max_audio_length_ms: int = 240000,
        seed: Optional[int] = None,
        output_format: str = "mp3"
    ) -> Optional[bytes]:
        """Generate music. Returns audio bytes; a failed run raises, see
        generate_music_sync."""
        import asyncio
        return await asyncio.to_thread(
            self.generate_music_sync, lyrics, tags, temperature, topk, cfg_scale,
            max_audio_length_ms, seed, output_format)
