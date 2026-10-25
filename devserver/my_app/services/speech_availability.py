"""Is this platform speaking right now, and by what rule.

One source of truth for two callers who must not drift apart: the speech status
endpoint, which decides whether the interface offers a voice at all, and the
GIVEN VOICE note, which tells the agents that their words can be said aloud. If
each computed availability for itself, an agent could come to believe it is
heard on an installation where speech is switched off.

The facts about which levels may speak and which languages have a voice live in
the chunk, because the chunk is also the gate that enforces them. They are read
from there, never restated.
"""

import asyncio
import importlib.util
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_chunk_module = None


def speech_chunk():
    """The speech chunk module, loaded once, for the facts that live there."""
    global _chunk_module
    if _chunk_module is None:
        path = (Path(__file__).resolve().parents[2]
                / "schemas" / "chunks" / "output_speech_supertonic.py")
        spec = importlib.util.spec_from_file_location("_speech_chunk_facts", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _chunk_module = module
    return _chunk_module


def speech_availability(probe: bool = True) -> dict:
    """Whether this installation speaks, and if not, why not.

    `probe=False` skips loading the model and reports on configuration and
    safety level alone — enough for a prompt, and it keeps a chat turn from
    waiting on a model load.
    """
    from config import SUPERTONIC_ENABLED
    from my_app.services.safety_level_resolver import resolve_safety_level

    try:
        chunk = speech_chunk()
        level = resolve_safety_level()
        level_allowed = level in chunk.ALLOWED_SAFETY_LEVELS

        installed = None
        if SUPERTONIC_ENABLED and level_allowed and probe:
            from my_app.services.supertonic_backend import get_supertonic_backend
            installed = asyncio.run(get_supertonic_backend().is_available())

        if not SUPERTONIC_ENABLED:
            reason = 'disabled'
        elif not level_allowed:
            reason = 'safety_level'
        elif installed is False:
            reason = 'not_installed'
        else:
            reason = None

        return {
            'available': reason is None,
            'reason': reason,
            'safety_level': level,
            'voiced_languages': list(chunk.CHUNK_META['supported_languages']),
        }
    except Exception as e:
        # A broken check must not silence the platform's own status surface,
        # and must not tell an agent it is heard when nothing is known.
        logger.warning("[SPEECH] availability check failed: %s", e)
        return {'available': False, 'reason': 'unknown', 'safety_level': None,
                'voiced_languages': []}


# How the state reads in the GIVEN VOICE note. Kept next to the check rather
# than in the prompt builder: the reason codes come from here, so the sentences
# that explain them belong here too.
_SILENT = {
    'disabled': "silent — speech is switched off in this installation",
    'safety_level': ("silent — speech is not enabled at this installation's "
                     "safety level"),
    'not_installed': "silent — the speech model is not installed here",
    'unknown': "silent — whether speech works here could not be established",
}

_HEARD = {
    'on_request': ("spoken aloud whenever a listener asks for it, one piece "
                   "at a time"),
    'voice': ("spoken aloud and not written on the screen — someone chose to "
              "hear rather than read"),
    'both': "spoken aloud and written on the screen at once",
    'text': ("written on the screen only; nothing is spoken this turn — "
             "someone chose to read rather than hear"),
}

# What is true where nothing said otherwise. Silence is the honest default:
# only two surfaces in this platform offer a voice at all, so assuming one
# would tell most figures they can be heard where no one can hear them.
_NO_SURFACE = ("written on the screen only — this surface offers no way to "
               "hear it")


def voice_state_sentence(voice_mode: Optional[str] = None,
                         probe: bool = False) -> str:
    """One sentence: what happens to these words right now.

    `voice_mode` is what the calling surface knows and the backend cannot:
    whether there is a voice there at all, and what the listener set in
    their own browser where the choice is offered.

      'on_request'  a voice per message, asked for by hand (Persona)
      'voice' | 'both' | 'text'   the listener's own setting (Resona)
      absent        no voice on this surface

    Absent means silent, not "on request". Only two surfaces carry a voice,
    so the opposite default would tell most figures they can be heard in rooms
    that have no ears — and a figure that believes it is heard writes for one.
    """
    state = speech_availability(probe=probe)
    if not state['available']:
        return _SILENT.get(state['reason'] or 'unknown', _SILENT['unknown'])
    return _HEARD.get((voice_mode or "").strip().lower(), _NO_SURFACE)
