"""
What each model actually costs — measured, not declared.

Two numbers per model, both taken from real runs:
  - how long it holds the slot (load and forward pass counted apart, because a
    cold load is the expensive half and a warm run is not),
  - how much VRAM it actually occupies while it runs.

Why measure at all. Every scheduling decision above this file rests on a
number: how long the person behind will wait, whether a second model still
fits beside the one that is running. The platform had exactly one declared
table (MODEL_PEAK_VRAM_MB of the GPU service) and it was a guess — 16 GB declared for heartmula
against 11.1 GB measured. A guess is enough to serialize with; it is not
enough to run two models side by side. So nothing here is invented: a model
without samples has no entry, and every consumer must be able to say "not
known yet" rather than assume.

The file is written outside the working tree by default. Operational state
does not belong in a repository.

Moved with the gate in stage 7 of the move to ComfyUI, from the GPU service
into this process. The file is this process's own: the GPU service keeps
writing its file until stage 8 takes it down, and two processes flushing
one table whole would each drop the other's readings. The first start
without a file of its own reads the old host's file once, so every hold and
footprint measured there is carried over, and a config whose duration was
known before stage 7 is still announced with it.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PATH = "/var/tmp/ai4artsed/gate_model_stats.json"
# The old host's file, read once when this process has none of its own.
_SEED_PATH = "/var/tmp/ai4artsed/gpu_model_stats.json"

# A moving average that follows change without forgetting the past run.
_ALPHA = 0.3
# Below this many samples a number is reported but must not be acted on.
TRUSTED_SAMPLES = 3
# How far the runs of one model may sit apart before their middle stops
# describing any of them, as a share of that middle. One checkpoint serves
# several configs here — the same video weights run a short pass and a long
# one — and averaging the two names a duration that neither has.
SPREAD_LIMIT = 0.6


def _now() -> float:
    return time.time()


class ModelStats:
    """Per-(kind, model) durations and footprints. Thread-safe, self-persisting."""

    def __init__(self, path: Optional[str] = None):
        self._lock = threading.Lock()
        # Its own variable: the GPU service's twin reads GPU_MODEL_STATS_PATH,
        # and one name for both would make two processes write one file.
        self._path = path or os.environ.get("GATE_MODEL_STATS_PATH", _DEFAULT_PATH)
        self._data: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._last_write = 0.0
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict) and isinstance(raw.get("models"), dict):
                self._data = raw["models"]
                logger.info("[MODEL-STATS] Loaded %d model records from %s",
                            len(self._data), self._path)
        except FileNotFoundError:
            self._seed()
        except Exception as e:
            # A damaged file must not take the service down; it starts over.
            logger.warning("[MODEL-STATS] Could not read %s (%s) — starting empty",
                           self._path, e)

    def _seed(self) -> None:
        """No file of our own yet: take the old host's measurements, once."""
        try:
            with open(_SEED_PATH, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            logger.info("[MODEL-STATS] No history yet at %s — starting empty", self._path)
            return
        except Exception as e:
            logger.warning("[MODEL-STATS] Could not read the old host's %s (%s) — starting empty",
                           _SEED_PATH, e)
            return
        if isinstance(raw, dict) and isinstance(raw.get("models"), dict):
            self._data = raw["models"]
            self._dirty = True
            logger.info("[MODEL-STATS] Seeded %d model records from the old host's %s; "
                        "written to %s from now on", len(self._data), _SEED_PATH, self._path)
        else:
            logger.warning("[MODEL-STATS] The old host's %s carries no 'models' table — "
                           "starting empty", _SEED_PATH)

    def _flush_locked(self, force: bool = False) -> None:
        if not self._dirty:
            return
        if not force and (_now() - self._last_write) < 30.0:
            return
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = f"{self._path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "written_at": _now(), "models": self._data},
                          fh, indent=1)
            os.replace(tmp, self._path)
            self._dirty = False
            self._last_write = _now()
        except Exception as e:
            logger.warning("[MODEL-STATS] Could not write %s: %s", self._path, e)

    def flush(self) -> None:
        with self._lock:
            self._flush_locked(force=True)

    # --------------------------------------------------------------- record
    @staticmethod
    def key(kind: str, model_id: str) -> str:
        return f"{kind}::{model_id or kind}"

    def record_hold(self, kind: str, key_id: str, held_s: float,
                    model_id: Optional[str] = None) -> None:
        """One completed run: how long it held the slot.

        `key_id` is what durations are keyed by — the output config where one
        is known, the model otherwise. `model_id` names the weights either way,
        so an entry keyed by config still says which model it belongs to; the
        two are not the same question and the file should not blur them.
        """
        if held_s <= 0:
            return
        k = self.key(kind, key_id)
        with self._lock:
            e = self._data.setdefault(k, {"kind": kind, "keyed_by": key_id})
            e["keyed_by"] = key_id
            e["model_id"] = model_id or key_id
            prev = e.get("hold_ema_s")
            # How far this run landed from what was expected, averaged the same
            # way as the expectation itself. The deviation, not the largest run
            # ever seen: one cold outlier should not silence a model for good,
            # while a genuinely two-sided distribution should keep it quiet.
            if prev is not None:
                dev = abs(held_s - float(prev))
                pmad = e.get("hold_mad_s")
                e["hold_mad_s"] = round(
                    dev if pmad is None
                    else (1 - _ALPHA) * float(pmad) + _ALPHA * dev, 2)
            e["hold_ema_s"] = held_s if prev is None else (1 - _ALPHA) * prev + _ALPHA * held_s
            e["hold_last_s"] = round(held_s, 1)
            e["hold_min_s"] = round(min(held_s, e.get("hold_min_s", held_s)), 1)
            e["hold_max_s"] = round(max(held_s, e.get("hold_max_s", held_s)), 1)
            e["hold_n"] = int(e.get("hold_n", 0)) + 1
            e["last_seen"] = _now()
            self._dirty = True
            self._flush_locked()

    def record_footprint(self, kind: str, model_id: str, used_mb: float) -> None:
        """One completed run: how much VRAM it actually held.

        `used_mb` is the largest drop in free memory observed while this run
        owned the slot — with the slot held, nothing else is allocating, so
        the drop is this run's own.
        """
        if used_mb <= 0:
            return
        k = self.key(kind, model_id)
        with self._lock:
            e = self._data.setdefault(k, {"kind": kind, "model_id": model_id})
            prev = e.get("vram_ema_mb")
            e["vram_ema_mb"] = used_mb if prev is None else (1 - _ALPHA) * prev + _ALPHA * used_mb
            e["vram_max_mb"] = round(max(used_mb, e.get("vram_max_mb", used_mb)))
            e["vram_n"] = int(e.get("vram_n", 0)) + 1
            e["last_seen"] = _now()
            self._dirty = True
            self._flush_locked()

    # ----------------------------------------------------------------- read
    def hold_estimate_s(self, kind: str, model_id: str,
                        trusted_only: bool = True) -> Optional[float]:
        """Expected slot time, or None when no duration can honestly be named.

        None on three counts, and each of them is a real answer:
          - this model has never been seen,
          - it has been seen fewer times than TRUSTED_SAMPLES,
          - its runs sit too far apart to have a middle. A wait announced as
            five minutes that turns into fifteen is worse than a wait that was
            never announced, and this is where that is decided.
        """
        with self._lock:
            e = self._data.get(self.key(kind, model_id))
            if not e or e.get("hold_ema_s") is None:
                return None
            ema = float(e["hold_ema_s"])
            if not trusted_only:
                return ema
            if int(e.get("hold_n", 0)) < TRUSTED_SAMPLES:
                return None
            mad = e.get("hold_mad_s")
            if mad is None:
                # Entries written before the deviation was measured. The
                # observed range stands in: over a handful of samples a range
                # covers roughly four deviations, so a quarter of it is the
                # right order and errs toward saying nothing.
                lo, hi = e.get("hold_min_s"), e.get("hold_max_s")
                if lo is None or hi is None:
                    return ema
                mad = (float(hi) - float(lo)) / 4.0
            if ema > 0 and float(mad) > SPREAD_LIMIT * ema:
                return None
            return ema

    def load_estimate_s(self, kind: str, model_id: str) -> Optional[float]:
        """What a load of this model costs when it really has to load.

        Not the average. A load whose model is already resident returns at
        once and is recorded like any other, so the mean sits between "no work"
        and "the whole model off disk" and describes neither. The longest
        observed load is the one that answers "how long if it has to happen".
        """
        with self._lock:
            e = self._data.get(self.key(kind, model_id))
            return None if not e else e.get("hold_max_s")

    def vram_estimate_mb(self, kind: str, model_id: str, trusted_only: bool = True) -> Optional[float]:
        """Measured footprint. With trusted_only, returns None until there are
        enough samples to act on — a single reading is an anecdote."""
        with self._lock:
            e = self._data.get(self.key(kind, model_id))
            if not e or e.get("vram_ema_mb") is None:
                return None
            if trusted_only and int(e.get("vram_n", 0)) < TRUSTED_SAMPLES:
                return None
            # The high-water mark, not the average: the question a prefetch asks
            # is whether it FITS, and averaging away the worst run answers a
            # different question.
            return float(e.get("vram_max_mb") or e["vram_ema_mb"])

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {k: dict(v) for k, v in self._data.items()}


_stats: Optional[ModelStats] = None
_stats_lock = threading.Lock()


def get_model_stats() -> ModelStats:
    global _stats
    if _stats is None:
        with _stats_lock:
            if _stats is None:
                _stats = ModelStats()
                # Writes are throttled to keep the gate lock short, so the last
                # half-minute of measurements would be lost on every restart —
                # and these are the measurements a workshop just paid for.
                import atexit
                atexit.register(_stats.flush)
    return _stats
