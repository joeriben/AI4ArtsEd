"""
VoxCPM2 backend — the synthesiser that is asked for a voice in words.

The third procedure in the voices comparison, and a genuinely different one.
Supertonic is given a mixture over ten fixed presets and has no parameter for
feeling at all. Qwen3-TTS was given an English sentence about the delivery,
next to the utterance. VoxCPM2 is given a description of the speaker *inside*
the utterance — "(A young woman, gentle and sweet voice)Guten Tag." — so the
model itself has to decide which part of the string is an instruction and which
part is what to say. Left empty, nothing is asked and the model reads the
prosody off the sentence.

**It runs as a separate process in its own environment**, like Piper and for a
sharper reason: `voxcpm` pins `datasets<4` and `gradio>=6` against the
platform's 4.5.0 and 5.50.0. Installing it alongside would move both under
everything else that uses them, which is how Qwen3-TTS was lost (2026-08-12).
`download_voxcpm.sh` builds that environment, `voxcpm_service/server.py` is the
worker, and this module only talks to it over localhost. Unlike Piper the
process stays up: a 2 B model on the GPU costs about 25 seconds to load against
0.3 seconds to speak.

**Provenance is not disclosed.** The model card says "2M+ hours multilingual
speech" and names no source; whether the recorded speakers agreed is unknown.
That is the same silence as Supertonic and Qwen3-TTS. The first column of the
comparison has no such question to answer: eSpeak NG was trained on nothing.

**Voice cloning is not reachable from here.** VoxCPM2 can clone a voice from a
few seconds of recording; no parameter in this module or in the worker leads to
it. Whether that belongs on a platform used by children in workshops is an open
question, and leaving it unreachable is not an answer to it — it is refusing to
answer it by accident.

This is not the platform's voice and must never become it. A caller reaches it
only by naming it (`system: "voxcpm"`).
"""

import asyncio
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)


# The platform languages VoxCPM2 speaks, out of its model card's list of 30:
# Arabic, German, English, Spanish, French, Hebrew, Korean, Turkish. Bulgarian
# and Ukrainian are not in that list. Russian is, and is deliberately NOT
# offered in Ukrainian's place — the same decision the other backends make.
#
# Written out rather than probed: the model takes no language parameter at all
# ("no language tag needed", says its card), so there is nothing to ask it.
SUPPORTED_LANGUAGES = ("ar", "de", "en", "es", "fr", "he", "ko", "tr")

# Not in that list, and answered with an English rendering of the same sentence
# rather than with a refusal. Kept next to the line above so the two cannot
# drift: together they are the platform's ten.
UNVOICED_PLATFORM_LANGUAGES = ("bg", "uk")


class UnvoicedLanguageError(RuntimeError):
    """VoxCPM2 has no voice for that language.

    Raised instead of speaking it with a neighbouring one, exactly as in the
    other backends. Two of the ten platform languages are missing — Bulgarian
    and Ukrainian — and Russian is deliberately not offered in their place.
    """

    def __init__(self, language: str):
        super().__init__(f"VoxCPM2 has no voice for language '{language}'")
        self.language = language


class VoxCPMBackend:
    """Speaks by asking the worker process, and starts it if it is not there.

    Holds no model: everything that would need the model's environment lives
    behind the HTTP call. What it does hold is the lifecycle — the same
    double-checked start under a lock, because the first request after a
    reboot would otherwise fail for a reason nobody can see.
    """

    def __init__(self):
        from config import (
            BASE_DIR, GPU_ADMISSION_ACQUIRE_TIMEOUT_S, VOXCPM_AUTO_START, VOXCPM_CFG_VALUE,
            VOXCPM_HEALTH_CHECK_INTERVAL, VOXCPM_INFERENCE_TIMESTEPS,
            VOXCPM_LOUDNESS_LUFS, VOXCPM_STARTUP_TIMEOUT, VOXCPM_URL,
        )

        self.base_url = VOXCPM_URL.rstrip('/')
        self.loudness_lufs = VOXCPM_LOUDNESS_LUFS
        self.cfg_value = VOXCPM_CFG_VALUE
        self.inference_timesteps = VOXCPM_INFERENCE_TIMESTEPS
        self._auto_start = VOXCPM_AUTO_START
        self._startup_timeout = VOXCPM_STARTUP_TIMEOUT
        # The gate's queue budget: how long the worker may wait for the
        # card's turn before the caller is told busy (see _wait_for_ready).
        self._gate_wait_budget = GPU_ADMISSION_ACQUIRE_TIMEOUT_S
        self._health_interval = VOXCPM_HEALTH_CHECK_INTERVAL
        self._base_dir = Path(BASE_DIR)
        self._startup_lock = threading.Lock()

    # ------------------------------------------------------------- languages

    def languages(self) -> list:
        """The platform languages this model speaks, from its model card."""
        return list(SUPPORTED_LANGUAGES)

    def resolve_language(self, language: Optional[str]) -> str:
        """The language code this model has a voice for, or refuse.

        A separate step, so that "no Bulgarian" can never arrive disguised as
        "the synthesiser is broken".
        """
        code = (language or "").strip().lower()
        if code in SUPPORTED_LANGUAGES:
            return code
        raise UnvoicedLanguageError(code)

    # ------------------------------------------------------------- lifecycle

    def _health(self) -> Optional[dict]:
        """What the worker says about itself, or None if it is not there."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            if response.status_code != 200:
                return None
            return response.json()
        except Exception as e:  # noqa: BLE001 — absence is the normal case here
            logger.debug(f"[VOXCPM] Health check failed: {e}")
            return None

    def _ensure_worker(self) -> bool:
        """The worker is up and the model is in memory, starting it if needed."""
        state = self._health()
        if state and state.get("loaded"):
            return True

        if state is not None:
            # It is there and still loading; wait rather than start a second.
            return self._wait_for_ready(time.time())

        if not self._auto_start:
            logger.warning("[VOXCPM] Worker not running and auto-start is off")
            return False

        with self._startup_lock:
            state = self._health()
            if state and state.get("loaded"):
                logger.info("[VOXCPM] Another thread started the worker")
                return True
            if state is None:
                script = self._base_dir / "2_start_voxcpm.sh"
                if not script.exists():
                    logger.error(f"[VOXCPM] Startup script not found: {script}")
                    return False
                logger.warning(f"[VOXCPM] Worker down, spawning: {script}")
                try:
                    subprocess.Popen(
                        [str(script)],
                        # Not pipes. The worker prints a progress bar per
                        # utterance, and a pipe nobody reads fills up and
                        # blocks the process writing to it — the model would
                        # go silent mid-run with nothing to show for it. Its
                        # log is written to the protocol file by _record.sh.
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        cwd=script.parent,
                        start_new_session=True,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(f"[VOXCPM] Start failed: {e}")
                    return False
            return self._wait_for_ready(time.time())

    def _wait_for_ready(self, start: float) -> bool:
        """Poll until the model is in memory, or give up and say so.

        Time the worker spends waiting for the card's turn (/health says
        "gate": "waiting") is not startup time: that is the gate's queue,
        whose budget is GPU_ADMISSION_ACQUIRE_TIMEOUT_S, and when it runs out
        the caller is told busy (GpuBusyError, the way the lease taken here
        used to raise it), never "not installed". Until 2026-10-10 the
        startup clock ran on through the queue, and a busy card read as a
        missing install (second review of the same day).
        """
        from my_app.services.gpu_lease_client import GpuBusyError
        waited_for_gate = 0.0
        last = time.time()
        while True:
            now = time.time()
            state = self._health()
            if state and state.get("gate") == "waiting" and not state.get("loaded"):
                waited_for_gate += now - last
                start += now - last  # the startup clock stands still in the queue
                if waited_for_gate > self._gate_wait_budget:
                    raise GpuBusyError(
                        "VoxCPM2 waited %.0f s for the card's turn" % waited_for_gate,
                        reason="wait_timeout")
            last = now
            elapsed = now - start
            if elapsed > self._startup_timeout:
                logger.error(f"[VOXCPM] Not ready after {self._startup_timeout}s")
                return False
            if state and state.get("loaded"):
                logger.info(f"[VOXCPM] Worker ready (took {elapsed:.1f}s)")
                return True
            if state and state.get("error"):
                logger.error(f"[VOXCPM] Worker failed to load: {state['error']}")
                return False
            time.sleep(self._health_interval)

    async def is_available(self) -> bool:
        """True when this could actually speak, not when it is configured."""
        # The weights land on the card in the worker's process, and that
        # process takes the lease that covers its load, over the gate's HTTP
        # API (voxcpm_service/server.py, S-005), whoever started it. Until
        # 2026-10-10 the lease was taken here, around starting the worker,
        # and only when the DevServer started it: a worker started by hand
        # put 6774 MiB on the card unannounced. Starting a process and
        # waiting for its /health allocate nothing, so nothing is held here;
        # the utterance takes its own lease in speak().
        return await asyncio.to_thread(self._ensure_worker)

    # -------------------------------------------------------------- synthesis

    async def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        voice_description: Optional[str] = None,
        cfg_value: Optional[float] = None,
        inference_timesteps: Optional[int] = None,
        **kwargs,
    ) -> Tuple[bytes, str, float]:
        """Speak `text` verbatim.

        Returns (WAV bytes, what was asked for, measured f0 in Hz). What was
        asked for is the description exactly as it was sent, so the label
        always names what the model actually received. The f0 is
        read off the audio being handed back, by the same procedure the other
        synthesisers are measured with — a measurement, never the feeling that
        was asked for.
        """
        from my_app.services.speech_audio import read_wav, to_wav
        from my_app.services.voice_register import median_f0

        if not text or not text.strip():
            raise ValueError("No text to speak")

        described = (voice_description or "").strip()
        payload = {
            "text": text,
            "description": described,
            "cfg_value": float(cfg_value if cfg_value is not None else self.cfg_value),
            "inference_timesteps": int(
                inference_timesteps if inference_timesteps is not None
                else self.inference_timesteps),
        }

        logger.info(f"[VOXCPM] {len(text)} chars | language={language} | "
                    f"described={bool(described)}")

        def _post():
            # Connect timeout only. The read has none on purpose: this is a
            # model call, and a cap here would abandon an utterance that is
            # still being produced.
            return requests.post(f"{self.base_url}/speak", json=payload,
                                 timeout=(5, None))

        from my_app.services.gpu_lease_client import gpu_lease

        # VoxCPM2 keeps its own process and its own weights on the card, so it
        # cannot take the plant-wide slot from in here - it takes a remote
        # lease, the way ComfyUI does. Measured 2026-08-26: 6774 MiB held by
        # that process while the coordinator believed the card was otherwise
        # occupied, which is how an eviction decision comes to be made against
        # a number that is wrong.
        #
        # required_mb stays 0. The weights are resident already; asking for
        # room would have somebody else evicted for memory nobody needs.
        async with gpu_lease("voxcpm", "voxcpm", 0, workload="voxcpm:speak"):
            response = await asyncio.to_thread(_post)

        if response.status_code != 200:
            try:
                reason = response.json().get("error") or response.text
            except Exception:  # noqa: BLE001
                reason = response.text
            reason = str(reason).strip()[:400]
            logger.error(f"[VOXCPM] Refused ({response.status_code}): {reason}")
            if response.status_code == 400:
                raise ValueError(reason)
            raise RuntimeError(reason or "VoxCPM2 synthesis failed")

        samples, sample_rate = read_wav(response.content)
        wav = to_wav(samples, sample_rate, self.loudness_lufs)
        f0_hz = median_f0(samples, sample_rate)

        # What was asked for, exactly as it was sent. The phrase to ask for
        # while nothing has been chosen belongs where the choosing happens:
        # the Compare surface sends "neutral voice" for three unlit rows.
        # Only the sent description travels from here, so a label
        # always names what the model received — and prose written in one
        # language stays out of a value that every reader is shown.
        spoke = described

        logger.info(f"[VOXCPM] {len(wav)} bytes ({f0_hz:.0f} Hz)")
        return wav, spoke, f0_hz


_backend: Optional[VoxCPMBackend] = None


def get_voxcpm_backend() -> VoxCPMBackend:
    """Return the process-wide VoxCPM2 backend."""
    global _backend
    if _backend is None:
        _backend = VoxCPMBackend()
    return _backend


