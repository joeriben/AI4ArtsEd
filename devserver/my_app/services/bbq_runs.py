"""What every bias run on this platform measured, one line per model.

Two instruments write here: Bias Archaeology 1 over BBQ, and Bias Archaeology 2
over WinoBias. They are kept apart by the `instrument` field and never mixed -
a BBQ bias score and a WinoBias differential are not the same quantity, and a
median across both would be neither. Lines written before that field existed
are BBQ, which is what `_DEFAULT_INSTRUMENT` says.

A single run says what one machine did with one draw of sixty questions. It
does not say whether that is much or little. The line under a model's bars
answers that with the platform's own history: the median of every model series
ever measured here, so a reader has something to hold the number against.

What is kept is the benchmark's own arithmetic - which of the three answers was
picked how often, and BBQ's score over that. Nothing a person wrote or asked for
enters this file, and the file lives under devserver/data, which .gitignore
holds shut (devserver/data/*.jsonl); see the global rule on user data and
repositories.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List

import config

logger = logging.getLogger(__name__)

DATA_DIR = config.DEVSERVER_DATA_DIR
RUNS_FILE = DATA_DIR / "bbq_runs.jsonl"

# One writer at a time; a torn line would be a lost line for good.
_lock = threading.Lock()

# What a line without the field belongs to: everything written before there was
# a second instrument came from Bias Archaeology.
_DEFAULT_INSTRUMENT = "bbq"

# What a record may carry. A key outside this set is dropped rather than
# written: the file is small on purpose and stays readable by eye.
_FIELDS = (
    "instrument", "category", "model_id",
    "ambig", "unknown", "stereo", "other",
    "disambig", "correct_dis", "score",
)


def record(entry: Dict[str, Any]) -> None:
    """Append one finished model series. Failure here never fails a run."""
    line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for key in _FIELDS:
        if key in entry:
            line[key] = entry[key]
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            with open(RUNS_FILE, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning(f"[BBQ-RUNS] could not record: {exc}")


def _entries() -> List[Dict[str, Any]]:
    if not RUNS_FILE.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(RUNS_FILE, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning(f"[BBQ-RUNS] could not read: {exc}")
    return rows


def summary(category: str | None = None,
            instrument: str | None = None) -> Dict[str, Any]:
    """The platform's own history of this measure, whole and per model.

    `by_model` is what the surface reads: under a model's bars the useful
    reference is that MODEL's own history, not the platform's average over
    machines that differ by an order of magnitude in size. It is taken within
    one category, because a bias score for Age and one for Religion are not the
    same quantity and their median would be neither.

    `by_model_all` is the same per model across all categories of THIS
    instrument, and it is what
    the surface falls back on: a category that has been run once has a median of
    one series, which IS that series and says nothing. Then the model's own
    value over the whole benchmark is the honest reference, and the line stands
    instead of disappearing the moment the category is changed.

    `median` over everything stays, one level up, as the answer to "is this
    unusual here at all". A median of one series is that series, so `runs` goes
    out with each of them and a caller can tell the two apart.
    """
    want = instrument or _DEFAULT_INSTRUMENT
    everything = [
        row for row in _entries()
        if isinstance(row.get("score"), (int, float))
        and (row.get("instrument") or _DEFAULT_INSTRUMENT) == want
    ]
    rows = [
        row for row in everything
        if category is None or row.get("category") == category
    ]

    def by_model(source: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        per_model: Dict[str, List[float]] = {}
        for row in source:
            model_id = row.get("model_id")
            if isinstance(model_id, str) and model_id:
                per_model.setdefault(model_id, []).append(row["score"])
        return {
            model_id: {"runs": len(values), "median": round(median(values))}
            for model_id, values in per_model.items()
        }

    scores = [row["score"] for row in rows]
    return {
        "runs": len(scores),
        "median": round(median(scores)) if scores else None,
        "instrument": want,
        "category": category,
        "by_model": by_model(rows),
        "by_model_all": by_model(everything),
    }
