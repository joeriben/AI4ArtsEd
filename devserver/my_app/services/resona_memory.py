"""
Resona Episodic Memory (Phase 2) — Consulting-to-Workshop bridge.

Resona is one presence across two situations (Consulting: planning with the
educator beforehand; Workshop: present with the group). This module gives her
a shared, device-keyed memory so she "knows this is the situation that was
planned for" (docs/plans/resona/PLAN.md, Phase 2).

Storage: flat JSON, one file per device_id (mirrors chat_history.json — one
file per key) under the devserver's own export tree, config.DEVSERVER_JSON_DIR
(not config.JSON_STORAGE_DIR at the repository root, where favorites.json and
the session folders live; S-055). device_id is client-supplied
(browser_id + date, see useDeviceId.ts), so it is sanitized before touching
the filesystem.

Record shape: {"kind": str, "content": str, "ts": ISO-8601 str, "run_id": str|None,
"journal_id": str|None} — journal_id is what makes a record attributable, so
"new dialog" can drop this conversation's notes without touching the notes of
conversations that were explicitly kept (see forget_journal).
kind ∈ {"goal", "milestone", "tool_choice", "discarded", "canvas_solution", "note"}
— chosen AND discarded options both matter (PLAN.md: "gewählte UND verworfene Tools").

Append-only from the caller's perspective; internally bounded (oldest records
dropped past MAX_RECORDS_PER_DEVICE) so a long-lived device file cannot grow
unbounded across a school year.
"""

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import config

logger = logging.getLogger(__name__)

STORAGE_DIR = config.DEVSERVER_JSON_DIR / "resona_memory"

VALID_KINDS = ("goal", "milestone", "tool_choice", "discarded", "canvas_solution", "note")

MAX_RECORDS_PER_DEVICE = 300  # bound file size; oldest dropped first
MAX_CONTENT_CHARS = 2000       # bound a single record's content length
RECALL_MAX_RESULTS = 8         # bound how many records recall() surfaces
RECALL_MAX_CHARS = 1500        # bound recall()'s total formatted output

# One lock guards all device files — memory writes are infrequent (a few per
# chat turn at most), so a single lock is simpler than per-device locking and
# avoids unbounded lock-dict growth across many devices.
_LOCK = threading.Lock()

_DEVICE_ID_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize_device_id(device_id: str) -> Optional[str]:
    """
    Turn a client-supplied device_id into a safe filename stem.

    device_id is expected to look like '<uuid-or-random>_<YYYY-MM-DD>' (see
    useDeviceId.ts), but it arrives over the network inside a JSON body, so it
    is treated as untrusted: whitelist alphanumeric/-/_ only, cap length, and
    reject empty results (no path traversal, no separators, no surprises).
    """
    if not device_id or not isinstance(device_id, str):
        return None
    cleaned = _DEVICE_ID_SAFE.sub("_", device_id.strip())[:200]
    cleaned = cleaned.strip("._")
    return cleaned or None


def _device_path(device_id: str) -> Optional[Path]:
    safe = _sanitize_device_id(device_id)
    if not safe:
        return None
    return STORAGE_DIR / f"{safe}.json"


def _load_records(device_id: str) -> List[dict]:
    path = _device_path(device_id)
    if not path or not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"[RESONA-MEMORY] Failed to load {path}: {e}")
        return []


def _save_records(device_id: str, records: List[dict]) -> None:
    path = _device_path(device_id)
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[RESONA-MEMORY] Failed to save {path}: {e}")


def remember(device_id: str, kind: str, content: str, run_id: Optional[str] = None,
             journal_id: Optional[str] = None) -> str:
    """
    Append one memory record for this device. Returns a short confirmation or
    error string suitable for returning directly to the LLM as a tool result.

    device_id, run_id and journal_id come from the backend request context,
    never from the model's tool arguments (see chat_routes.py's tool-call loop,
    which binds them via the registry's execute(..., context=...) parameter).

    journal_id is None only when there is no journal at all (a failed ensure).
    Pausing the journal does NOT strip it — the pause stops the recording, not
    the knowledge of where a note was made. A record with no journal belongs to
    no conversation and is therefore never dropped by forget_journal; see there.
    """
    safe_device = _sanitize_device_id(device_id) if device_id else None
    if not safe_device:
        return "Error: no valid device context — cannot remember without a device_id."

    kind = (kind or "").strip().lower()
    if kind not in VALID_KINDS:
        return f"Error: '{kind}' is not a valid kind. Use one of: {', '.join(VALID_KINDS)}"

    content = (content or "").strip()
    if not content:
        return "Error: content is required to remember something."
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS]

    record = {
        "kind": kind,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        # Always present from this version on, None included: forget_journal
        # tells "made outside any journal" (key present, None) from "written
        # before records were stamped" (key absent) by presence, not by value.
        "journal_id": journal_id if isinstance(journal_id, str) and journal_id else None,
    }

    with _LOCK:
        records = _load_records(device_id)
        records.append(record)
        if len(records) > MAX_RECORDS_PER_DEVICE:
            records = records[-MAX_RECORDS_PER_DEVICE:]
        _save_records(device_id, records)

    logger.info(f"[RESONA-MEMORY] Remembered kind={kind} for device={safe_device} ({len(content)} chars)")
    return f"Remembered ({kind})."


def recall(device_id: str, query: str) -> str:
    """
    Case-insensitive substring match over content + kind, most recent first.
    Returns a compact formatted string for the LLM, bounded in count and length.
    Empty query or no hits -> an honest "nothing found" string (never invented).
    """
    safe_device = _sanitize_device_id(device_id) if device_id else None
    if not safe_device:
        return "No memory available (no device context)."

    query = (query or "").strip()
    if not query:
        return "No memory found (empty query)."

    records = _load_records(device_id)
    if not records:
        return "No memory found for this group yet."

    needle = query.lower()
    matches = [
        r for r in records
        if needle in (r.get("content", "") or "").lower()
        or needle in (r.get("kind", "") or "").lower()
    ]
    if not matches:
        return f"No memory found matching '{query}'."

    # Most recent first
    matches = list(reversed(matches))[:RECALL_MAX_RESULTS]

    lines = []
    total = 0
    for r in matches:
        date = (r.get("ts") or "")[:10]  # YYYY-MM-DD
        line = f"- [{r.get('kind', 'note')}, {date}] {r.get('content', '')}"
        if total + len(line) > RECALL_MAX_CHARS:
            break
        lines.append(line)
        total += len(line)

    if not lines:
        return f"No memory found matching '{query}'."
    return "\n".join(lines)


def load_all(device_id: str) -> List[dict]:
    """Return all records for a device, oldest first (as stored). Used to compose
    the system-prompt digest (chat_routes.build_system_prompt, resona_mode branch)."""
    return _load_records(device_id)


def forget_journal(device_id: str, journal_id: str, include_unstamped: bool = False) -> int:
    """
    Drop this device's records that were made in the given journal — the memory
    half of "new dialog" (resona_routes.journal_delete). Returns how many went.

    Exact, not wholesale, and the exactness is the point. new_journal() mints
    <base>-g2, -g3 … for the SAME device, and a journal carried across days
    collects one device_id per day, so several conversations share one memory
    file. Dropping the file would take the notes of conversations that "new
    conversation" explicitly keeps — the opposite of what either button says.

    Two kinds of record are deliberately NOT touched:
      - journal_id None (key present): made with no journal at all (a failed
        ensure), so no conversation may claim it. Note that a PAUSED journal
        still stamps its records, and they do go with it.
      - journal_id of any other journal: not ours to drop.

    include_unstamped covers records written before records carried a journal
    at all (key absent). Only the journal's OWN device gets that treatment
    (resona_routes.journal_delete), because a journal's meta device_ids list is
    client-supplied and must not become a lever on a stranger's memory. It is
    self-limiting: no new unstamped records are ever written.
    """
    safe_device = _sanitize_device_id(device_id) if device_id else None
    safe_journal = journal_id.strip() if isinstance(journal_id, str) else ""
    if not safe_device or not safe_journal:
        return 0

    with _LOCK:
        records = _load_records(device_id)
        if not records:
            return 0

        def is_ours(rec: dict) -> bool:
            if not isinstance(rec, dict):
                return False
            if "journal_id" not in rec:
                return include_unstamped
            return rec.get("journal_id") == safe_journal

        keep = [r for r in records if not is_ours(r)]
        dropped = len(records) - len(keep)
        if dropped == 0:
            return 0
        if keep:
            _save_records(device_id, keep)
            # _save_records logs and swallows; the caller is about to delete a
            # journal on the strength of this, so a silent no-write must not
            # pass for a purge.
            if len(_load_records(device_id)) != len(keep):
                raise RuntimeError(f"memory purge did not persist for device={safe_device}")
        else:
            path = _device_path(device_id)
            if path and path.exists():
                path.unlink()  # let it raise: the caller must not report success

    logger.info(
        f"[RESONA-MEMORY] Forgot {dropped} record(s) of journal={safe_journal} "
        f"for device={safe_device}"
    )
    return dropped
