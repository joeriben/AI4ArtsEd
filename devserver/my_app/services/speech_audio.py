"""
Finishing a spoken utterance: one loudness for the whole of it, then WAV.

Shared by every synthesiser here, for the same reason `voice_register` is
shared. The voices mode puts the systems side by side in one player, and a
comparison between differently normalised audio is a comparison of the
normalisation. Whatever is heard next to each other has to have been finished
the same way.

Deliberately not per-sentence peak normalisation. The platform speaks sentence
by sentence so the first words arrive quickly; normalising each piece to its
own peak makes the loudness jump between them. Piper's own `normalize_audio`
does exactly that and is therefore switched off at the source — see
docs/SPRACHSYNTHESE_PIPER_KONFIGURATION.md.

The procedure is the one Supertonic was speaking with; it moved here unchanged
so that a second and third synthesiser cannot drift from it.
"""

import io
import logging

import numpy as np

logger = logging.getLogger(__name__)


def to_wav(audio: np.ndarray, sample_rate: int, lufs: float) -> bytes:
    """One loudness (EBU R128) over the whole utterance, then WAV bytes.

    Raises RuntimeError when there is nothing to hear. Silence must not pass as
    success: "nothing to hear" and "nothing was said" are indistinguishable to
    a caller that received a valid WAV.
    """
    import pyloudnorm as pyln
    import soundfile as sf

    x = np.asarray(audio, dtype=np.float32).squeeze()
    if x.ndim > 1:
        x = x.mean(axis=1)

    if len(x) < sample_rate * 0.05 or float(np.max(np.abs(x))) < 1e-4:
        raise RuntimeError("Speech synthesis produced silence")

    # The meter needs a window; very short pieces are left as they are.
    if len(x) > sample_rate * 0.4:
        measured = pyln.Meter(sample_rate).integrated_loudness(x)
        # Below this the piece is not quiet speech, it is noise, and the gain
        # would only amplify the noise.
        if np.isfinite(measured) and measured > -50.0:
            gain = 10.0 ** ((lufs - measured) / 20.0)
            x = x * gain

    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0.99:
        x = x * (0.99 / peak)

    buffer = io.BytesIO()
    sf.write(buffer, x.astype(np.float32), sample_rate,
             format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def read_wav(data: bytes):
    """A WAV's samples as float32 mono, with its sample rate.

    eSpeak NG writes a finished WAV rather than handing back an array, so its audio
    has to be read back in before it can be finished like everything else.
    """
    import soundfile as sf

    x, sample_rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return x, int(sample_rate)
