"""What register a piece of speech came out in — measured, not intended.

One measurement, used by every synthesiser here, which have nothing else in
common. It lives here rather than inside any of them because the number is only
worth anything when the same procedure produced it: a study that hears
Supertonic against VoxCPM2 against Piper compares those readings directly, and
implementations that drifted apart would make that comparison quietly false.

The procedure is the one the Supertonic register rule was built on
(DEVELOPMENT_DECISIONS.md, 2026-08-08) and is unchanged by the move.
"""

import numpy as np


def median_f0(x: np.ndarray, sample_rate: int) -> float:
    """Median fundamental frequency over the voiced parts, in Hz.

    Autocorrelation over 40 ms windows. Good enough to tell a female register
    from a male one, which is all it is asked to do — this is a gate, not an
    analysis. Returns 0.0 when nothing voiced was found; the caller treats that
    as "no verdict" rather than as "too low".
    """
    lo, hi = int(sample_rate / 400), int(sample_rate / 60)
    window, hop = int(sample_rate * 0.04), int(sample_rate * 0.02)
    values = []
    for i in range(0, len(x) - window, hop):
        frame = x[i:i + window]
        if np.sqrt((frame ** 2).mean()) < 0.02:
            continue
        frame = frame - frame.mean()
        corr = np.correlate(frame, frame, "full")[len(frame) - 1:]
        if corr[0] <= 0:
            continue
        segment = corr[lo:hi]
        if not len(segment):
            continue
        k = int(np.argmax(segment)) + lo
        if corr[k] / corr[0] >= 0.3:
            values.append(sample_rate / k)
    return float(np.median(values)) if values else 0.0


