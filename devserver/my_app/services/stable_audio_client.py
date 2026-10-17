"""
Stable Audio client — one prompt of the platform's node, run by ComfyUI.

A sound is one prompt of the node ai4artsed_stable_audio
(comfyui_nodes/ai4artsed_comfyui/), queued at ComfyUI and tracked the way a
picture or a local language model is (services/llm_client.run_node_files).
Which Stable Audio 3 checkpoint this card runs is services/stable_audio_tier
(medium on the wide card, the small variants below the threshold), and which
folder that is under ComfyUI's models/stable_audio/ is the table
config/local_media_weights.json. Until stage 6 of
the move to ComfyUI this posted to the GPU service's Stable
Audio station; the signatures are the ones the callers had then (the
stable_audio chunk, the cover band's availability check).
"""

import logging
import random
from typing import Optional

from my_app.services.gpu_lease_client import GpuBusyError, BackendGenerationError
from my_app.utils.response_reason import reason_line

logger = logging.getLogger(__name__)

NODE_CLASS = "ai4artsed_stable_audio"
STATION = "stable_audio"


def _random_seed() -> int:
    return random.randint(0, 2**32 - 1)


class StableAudioClient:
    """Stable Audio 3 on ComfyUI, through the platform's node."""

    def __init__(self):
        pass

    @staticmethod
    def _model_dir(kind: str = "music") -> str:
        """The folder the node is handed for this card and content kind;
        the tier reads the card once and keeps the answer."""
        from my_app.services import stable_audio_tier
        return stable_audio_tier.dir_name(kind)

    def _available(self, kind: str = "music") -> bool:
        """Whether the checkpoint this card would run is whole under
        ComfyUI's models/stable_audio/ and the station's library imports
        there, as the package reports it (services/media_stations)."""
        from my_app.services import media_stations
        try:
            return media_stations.has_folder(STATION, self._model_dir(kind))
        except Exception as e:
            logger.warning(f"[STABLE-AUDIO-CLIENT] availability unknown: {e}")
            return False

    async def is_available(self) -> bool:
        """Whether a sound can be made here now."""
        import asyncio
        return await asyncio.to_thread(self._available)

    def generate_audio_sync(
        self,
        prompt: str,
        duration_seconds: float = 10.0,
        negative_prompt: str = "",
        steps: int = 8,
        cfg_scale: float = 1.0,
        seed: int = -1,
        output_format: str = "wav",
        kind: str = "music",
    ) -> bytes:
        """The sound as bytes in `output_format`. A run that ended without
        one raises BackendGenerationError with the node's own sentence, and
        a card the gate holds for someone else raises GpuBusyError, as the
        service's answers did: the router reads "out of memory" and "device
        busy" off the sentence and keeps a card that has no room from being
        handed a second model (backend_router._is_card_fault), and the busy
        travels to the surface as busy. A seed below zero is drawn here, the
        way the service drew one. `kind` picks the checkpoint below the tier
        threshold (music, sfx); the callers of today all make music.
        Synchronous: called on a worker thread (`generate_audio`) and from
        Flask threads alike."""
        from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
        from my_app.services.llm_client import LLMClient
        model_dir = self._model_dir(kind)
        inputs = {
            "model_name": model_dir,
            "prompt": prompt,
            "duration_seconds": float(duration_seconds),
            "seed": int(seed) if seed is not None and int(seed) >= 0 else _random_seed(),
            "negative_prompt": negative_prompt or "",
            "steps": int(steps),
            "cfg_scale": float(cfg_scale),
            "output_format": output_format,
        }
        try:
            _out, files = LLMClient.run_node_files(NODE_CLASS, inputs,
                                                   workload=CURRENT_OUTPUT_CONFIG.get() or None)
        except GpuBusyError:
            raise
        except Exception as e:
            # Until 2026-09-14 every failure came back as None and reached
            # the chunk as "returned empty result": the shape the 2026-09-07
            # fix had closed, and the one the router hands to a second model.
            logger.error(f"[STABLE-AUDIO-CLIENT] Generation failed ({model_dir}): {e!r}")
            raise BackendGenerationError(reason_line(str(e) or repr(e), 300)) from e
        sound = next((f for f in files if f.media_type == "audio"), None)
        if sound is None:
            logger.error(f"[STABLE-AUDIO-CLIENT] the run ended without a sound ({model_dir})")
            raise BackendGenerationError(f"the run of {NODE_CLASS} ({model_dir}) ended without a sound")
        return sound.data

    async def generate_audio(
        self,
        prompt: str,
        duration_seconds: float = 10.0,
        negative_prompt: str = "",
        # SA3's baseline (the node's own defaults, SA3_DEFAULT_STEPS /
        # SA3_DEFAULT_CFG_SCALE in the package). These read 100 / 7.0 -- SA1's --
        # until 2026-08-08. No caller relies on them today: the only one, the
        # stable_audio chunk, always passes both from its output config. They
        # are kept right because a signature default is what the next caller
        # inherits, and inheriting SA1's numbers into SA3 is a twelvefold run
        # outside the model's regime.
        steps: int = 8,
        cfg_scale: float = 1.0,
        seed: int = -1,
        output_format: str = "wav",
    ) -> Optional[bytes]:
        """
        Generate audio from a text prompt, on ComfyUI.

        Returns:
            Audio bytes; a failed run raises, see generate_audio_sync
        """
        import asyncio
        return await asyncio.to_thread(
            self.generate_audio_sync, prompt, duration_seconds, negative_prompt,
            steps, cfg_scale, seed, output_format)


# Singleton
_client: Optional[StableAudioClient] = None


def get_stable_audio_client() -> StableAudioClient:
    global _client
    if _client is None:
        _client = StableAudioClient()
    return _client
