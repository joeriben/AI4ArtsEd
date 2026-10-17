"""
Resona Werkstatt-Journal (Phase R1/J1) — append-only event log per group.

One chronological, append-only event log per group/device that will (across
J1-J4) unify dialog turns, memory records, and media events into a single
"Werkstattbuch" (workshop journal) — pedagogical point: documentation as a
medium of insight, not proof.

J1 scope was journal lifecycle (ensure/read) + dialog persistence + journal
meta-events. J2/J3 added media provenance (media_intent at
decision time, media_result reported back by the frontend, reverse lookup
via find_media_provenance) and the memory dual-write mirror. The full
event-type enum is part of the schema since J1 (spec addendum D1);
self_activation stays schema-only until Eigenaktivitaet Stufe 1 (R3).

Storage: JSONL, one file per journal_id (mirrors resona_memory.py's one file
per device_id, but append-only lines instead of array-rewrite — journals grow
faster than the 300-record memory cap, so a crash-tolerant append beats a
full read-modify-write per event). Same storage root as resona_memory.py: the
devserver's own export tree, config.DEVSERVER_JSON_DIR (finding S-055 of the code review of 2026-10-10).

journal_id today == sanitize(device_id) (no
stable browser_id key — device_id's daily rotation is an intentional
shared-classroom-iPad protection, and the journal inherits it in J1).

Envelope (one JSONL line per event):
    {"v": 1, "seq": int, "ts": ISO-8601 UTC str, "type": str,
     "device_id": str, "payload": {...}}

device_id and journal_id are client-supplied (arrive over the network inside
a JSON body), so both are treated as untrusted: sanitized before touching the
filesystem (identical whitelist regex to resona_memory.py).
"""

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config

logger = logging.getLogger(__name__)

# devserver/my_app/services/resona_journal.py -> parents[2] == devserver/
STORAGE_DIR = config.DEVSERVER_JSON_DIR / "resona_journal"

# Full type enum per spec addendum D1 (self_activation included from J1, even
# though nothing writes it yet — the schema is forward-compatible on day one).
VALID_EVENT_TYPES = (
    "dialog",
    "memory",
    "media_intent",
    "media_result",
    "journal",
    "self_activation",
)

# Event types writable via this module's public API. self_activation is
# deliberately excluded until Eigenaktivitaet Stufe 1 (R3) builds its writer.
_WRITABLE_TYPES = ("dialog", "journal", "memory", "media_intent", "media_result")

VALID_DIALOG_ROLES = ("user", "assistant")
VALID_JOURNAL_ACTIONS = ("created", "resumed", "labeled", "exported", "cleared")
VALID_MEDIA_RESULT_STATUS = ("completed", "blocked", "error", "cancelled")

MAX_EVENTS_PER_JOURNAL = 5000  # cap; past this the journal goes read-only
                                # (a Werkstattbuch does not cut off its front —
                                # no oldest-dropped truncation, unlike resona_memory)
MAX_DIALOG_CHARS = 4000        # dialog payload content cap
MAX_OTHER_CHARS = 2000         # non-dialog payload string field cap
READ_LIMIT_MAX = 500           # hard clamp for read_events(limit=...)
READ_LIMIT_DEFAULT = 200

# One lock guards all journal files — writes are infrequent (a couple of
# events per chat turn), so a single lock is simpler than per-journal locking
# and avoids unbounded lock-dict growth across many journals (resona_memory.py
# precedent).
_LOCK = threading.Lock()

_JOURNAL_ID_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize_journal_id(raw: Optional[str]) -> Optional[str]:
    """
    Turn a client-supplied device_id/journal_id into a safe filename stem.

    Identical whitelist policy to resona_memory._sanitize_device_id: expected
    shape is '<uuid-or-random>_<YYYY-MM-DD>' (useDeviceId.ts), but it arrives
    inside a JSON body and is treated as untrusted — whitelist alphanumeric/
    -/_ only, cap length, reject empty results (no path traversal, no
    separators, no surprises).
    """
    if not raw or not isinstance(raw, str):
        return None
    cleaned = _JOURNAL_ID_SAFE.sub("_", raw.strip())[:200]
    cleaned = cleaned.strip("._")
    return cleaned or None


def _events_path(journal_id: str) -> Path:
    return STORAGE_DIR / f"{journal_id}.jsonl"


def _meta_path(journal_id: str) -> Path:
    return STORAGE_DIR / f"{journal_id}.meta.json"


def _load_meta(journal_id: str) -> Optional[dict]:
    path = _meta_path(journal_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            return meta if isinstance(meta, dict) else None
    except Exception as e:
        logger.error(f"[RESONA-JOURNAL] Failed to load meta {path}: {e}")
        return None


def _save_meta(journal_id: str, meta: dict) -> None:
    path = _meta_path(journal_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[RESONA-JOURNAL] Failed to save meta {path}: {e}")


def _append_line(journal_id: str, line_obj: dict) -> None:
    path = _events_path(journal_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line_obj, ensure_ascii=False))
        f.write("\n")


def _read_all_lines(journal_id: str) -> List[dict]:
    path = _events_path(journal_id)
    if not path.exists():
        return []
    events: List[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.error(f"[RESONA-JOURNAL] Skipping corrupt line in {path}: {e}")
    except Exception as e:
        logger.error(f"[RESONA-JOURNAL] Failed to read {path}: {e}")
    return events


def _truncate(value: str, limit: int) -> str:
    if not isinstance(value, str):
        return value
    return value[:limit] if len(value) > limit else value


def _validate_payload(event_type: str, payload: dict) -> Tuple[Optional[dict], Optional[str]]:
    """
    Validate + normalize (truncate) a payload for a given event type.
    Returns (normalized_payload, None) on success, or (None, error_message).
    Only validates the payload shapes J1 actually writes/accepts on the
    public append_event() path; other enum members are schema-only in J1.
    """
    if not isinstance(payload, dict):
        return None, "payload must be an object"

    if event_type == "dialog":
        role = (payload.get("role") or "").strip().lower()
        if role not in VALID_DIALOG_ROLES:
            return None, f"'{role}' is not a valid dialog role. Use one of: {', '.join(VALID_DIALOG_ROLES)}"
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            return None, "dialog payload requires non-empty content"
        lang = payload.get("lang")
        normalized = {
            "role": role,
            "content": _truncate(content, MAX_DIALOG_CHARS),
            "lang": lang if isinstance(lang, str) else None,
        }
        model = payload.get("model")
        if isinstance(model, str) and model.strip():
            # Optional provenance: which LLM actually produced an assistant turn.
            normalized["model"] = _truncate(model, 200)
        return normalized, None

    if event_type == "journal":
        action = (payload.get("action") or "").strip().lower()
        if action not in VALID_JOURNAL_ACTIONS:
            return None, f"'{action}' is not a valid journal action. Use one of: {', '.join(VALID_JOURNAL_ACTIONS)}"
        label = payload.get("label")
        normalized = {
            "action": action,
            "label": _truncate(label, MAX_OTHER_CHARS) if isinstance(label, str) else None,
        }
        return normalized, None

    if event_type == "memory":
        # J3 dual-write mirror of an accepted resona_memory record. kind is
        # already enforced by resona_memory.VALID_KINDS at the tool boundary;
        # here we only require non-empty strings (no cross-module import).
        kind = (payload.get("kind") or "").strip()
        if not kind:
            return None, "memory payload requires kind"
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            return None, "memory payload requires non-empty content"
        return {
            "kind": _truncate(kind, 64),
            "content": _truncate(content, MAX_OTHER_CHARS),
        }, None

    if event_type == "media_intent":
        intent_id = (payload.get("intent_id") or "").strip()
        config_id = (payload.get("config_id") or "").strip()
        prompt = payload.get("prompt")
        if not intent_id:
            return None, "media_intent payload requires intent_id"
        if not config_id:
            return None, "media_intent payload requires config_id"
        if not isinstance(prompt, str) or not prompt.strip():
            return None, "media_intent payload requires non-empty prompt"
        motivation = payload.get("motivation")
        normalized = {
            "intent_id": _truncate(intent_id, 64),
            "config_id": _truncate(config_id, 128),
            "prompt": _truncate(prompt, MAX_OTHER_CHARS),
            "motivation": _truncate(motivation, MAX_OTHER_CHARS)
            if isinstance(motivation, str) and motivation.strip() else None,
        }
        dialog_ref = payload.get("dialog_ref")
        if isinstance(dialog_ref, int) and not isinstance(dialog_ref, bool) and dialog_ref > 0:
            normalized["dialog_ref"] = dialog_ref
        return normalized, None

    if event_type == "media_result":
        intent_id = (payload.get("intent_id") or "").strip()
        status = (payload.get("status") or "").strip().lower()
        if not intent_id:
            return None, "media_result payload requires intent_id"
        if status not in VALID_MEDIA_RESULT_STATUS:
            return None, (f"'{status}' is not a valid media_result status. "
                          f"Use one of: {', '.join(VALID_MEDIA_RESULT_STATUS)}")
        run_id = payload.get("run_id")
        media_type = payload.get("media_type")
        media_url = payload.get("media_url")
        seed = payload.get("seed")
        return {
            "intent_id": _truncate(intent_id, 64),
            "run_id": _truncate(run_id, 128) if isinstance(run_id, str) and run_id.strip() else None,
            "status": status,
            "media_type": _truncate(media_type, 32) if isinstance(media_type, str) and media_type.strip() else None,
            "media_url": _truncate(media_url, 512) if isinstance(media_url, str) and media_url.strip() else None,
            "seed": seed if isinstance(seed, int) and not isinstance(seed, bool) else None,
        }, None

    # self_activation: schema-complete since J1 (spec addendum D1), but its
    # writer ships with Eigenaktivitaet Stufe 1 (R3) — reject until then.
    return None, f"event type '{event_type}' has no payload contract yet"


def journal_exists(journal_id: str) -> bool:
    safe = _sanitize_journal_id(journal_id)
    if not safe:
        return False
    return _meta_path(safe).exists()


def ensure(device_id: str) -> Optional[dict]:
    """
    Ensure a journal exists for this device_id's journal_id, creating it (and
    writing a journal/created event) if it does not yet exist. Idempotent:
    a second call for an existing journal returns created=False and writes
    nothing.

    Returns the meta dict (plus a "created" bool) or None if device_id fails
    sanitization.
    """
    safe = _sanitize_journal_id(device_id)
    if not safe:
        return None

    with _LOCK:
        meta = _load_meta(safe)
        if meta is not None:
            # Idempotent: existing journal, no event, no meta churn.
            result = dict(meta)
            result["created"] = False
            return result

        now = datetime.now(timezone.utc).isoformat()
        meta = {
            "journal_id": safe,
            "created_ts": now,
            "label": None,
            "schema_version": 1,
            "device_ids": [device_id],
            "event_count": 0,
            "last_ts": None,
            "read_only": False,
        }
        _write_events_locked(safe, meta, device_id, [("journal", {"action": "created", "label": None})])
        result = dict(meta)
        result["created"] = True
        return result


def device_ids(journal_id: str) -> List[str]:
    """
    The devices that wrote to this journal (meta['device_ids'], populated from
    creation onward). The delete path reads this BEFORE delete() to reach the
    matching Memory-Digest files. Empty list if the journal is unknown.
    """
    safe = _sanitize_journal_id(journal_id)
    if not safe:
        return []
    meta = _load_meta(safe)
    if not meta:
        return []
    return [d for d in (meta.get("device_ids") or []) if isinstance(d, str) and d]


_GENERATION_SUFFIX = re.compile(r"-g\d+$")


def owning_device(journal_id: str) -> Optional[str]:
    """
    The device this journal was created by, read off the journal_id itself:
    ensure() names the first journal after the sanitized device_id and
    new_journal() appends '-g2', '-g3', … to that same base.

    Derived, not looked up, on purpose. meta['device_ids'] is a client-supplied
    list any caller can append to (see _write_events_locked), so it may not
    decide which stranger's memory file a delete is allowed to sweep. This can.
    """
    safe = _sanitize_journal_id(journal_id)
    if not safe:
        return None
    return _GENERATION_SUFFIX.sub("", safe) or None


def has_other_generations(journal_id: str) -> bool:
    """
    Does this device have another journal besides this one — i.e. did anyone
    ever press "new conversation" here? True if a sibling <base> / <base>-gN
    meta file exists that is not this journal. Call BEFORE delete(), while this
    journal's own meta is still on disk.

    This is what decides whether records written before records carried a
    journal at all may be dropped along with this conversation: with no sibling,
    they can only have been made here; with a sibling, they may belong to the
    conversation that "new conversation" promised to keep, and keeping a stale
    note is the lesser wrong.
    """
    safe = _sanitize_journal_id(journal_id)
    base = owning_device(journal_id)
    if not safe or not base or not STORAGE_DIR.exists():
        return False
    suffix = ".meta.json"
    for path in STORAGE_DIR.glob(f"{base}*{suffix}"):
        stem = path.name[: -len(suffix)]
        if stem == safe:
            continue
        rest = stem[len(base):]
        if rest == "" or _GENERATION_SUFFIX.fullmatch(rest):
            return True
    return False


def delete(journal_id: str) -> bool:
    """
    Remove a journal's .jsonl + .meta.json. This function stays journal-only;
    media run folders are a separate store and are NOT touched (PLAN_DATENHALTUNG
    §5 / E5 — favorites reference run_ids). The Memory-Digest IS cleared, but by
    the caller: resona_routes.journal_delete pairs this with device_ids() +
    resona_memory.forget_journal(), because a journal whose memory survives is a
    deletion in name only. Returns True if at least one file was removed, False
    if the id is unsanitizable or no files existed.
    """
    safe = _sanitize_journal_id(journal_id)
    if not safe:
        return False
    with _LOCK:
        removed = False
        for path in (_events_path(safe), _meta_path(safe)):
            try:
                if path.exists():
                    path.unlink()
                    removed = True
            except Exception as e:
                logger.error(f"[RESONA-JOURNAL] Failed to delete {path}: {e}")
        return removed


def new_journal(device_id: str) -> Optional[dict]:
    """
    Mint a FRESH empty journal for this device without touching any existing one
    ("Neues Gespraech"). journal_id is the sanitized device_id for the first
    generation, then '<base>-g2', '<base>-g3', ... for the first free slot. The
    old journal stays on disk as the record. Returns the meta dict (created=True)
    or None if device_id fails sanitization.
    """
    base = _sanitize_journal_id(device_id)
    if not base:
        return None
    with _LOCK:
        jid = base
        n = 2
        while _meta_path(jid).exists():
            jid = f"{base}-g{n}"
            n += 1
            if n > 9999:
                logger.error(f"[RESONA-JOURNAL] new_journal: no free slot for {base}")
                return None
        now = datetime.now(timezone.utc).isoformat()
        meta = {
            "journal_id": jid,
            "created_ts": now,
            "label": None,
            "schema_version": 1,
            "device_ids": [device_id],
            "event_count": 0,
            "last_ts": None,
            "read_only": False,
        }
        _write_events_locked(jid, meta, device_id, [("journal", {"action": "created", "label": None})])
        result = dict(meta)
        result["created"] = True
        return result


def _write_events_locked(journal_id: str, meta: dict, device_id: str, type_payload_pairs: List[Tuple[str, dict]]) -> List[Optional[int]]:
    """
    Caller must hold _LOCK. Validates + appends each (type, payload) pair as
    one JSONL line, advancing seq monotonically; updates + persists meta once
    for the whole batch. If the journal is already read_only (at cap), no
    lines are written and every returned seq is None.

    Mutates `meta` in place (event_count/last_ts/device_ids/read_only) and
    persists it via _save_meta before returning.
    """
    seqs: List[Optional[int]] = []

    if meta.get("read_only"):
        return [None for _ in type_payload_pairs]

    if device_id and device_id not in meta.get("device_ids", []):
        meta.setdefault("device_ids", []).append(device_id)

    next_seq = meta.get("event_count", 0) + 1
    for event_type, payload in type_payload_pairs:
        if meta.get("read_only"):
            seqs.append(None)
            continue
        if event_type not in VALID_EVENT_TYPES:
            seqs.append(None)
            continue
        normalized_payload, err = _validate_payload(event_type, payload)
        if err:
            seqs.append(None)
            continue

        ts = datetime.now(timezone.utc).isoformat()
        line_obj = {
            "v": 1,
            "seq": next_seq,
            "ts": ts,
            "type": event_type,
            "device_id": device_id,
            "payload": normalized_payload,
        }
        _append_line(journal_id, line_obj)
        seqs.append(next_seq)
        meta["event_count"] = next_seq
        meta["last_ts"] = ts
        next_seq += 1

        if meta["event_count"] >= MAX_EVENTS_PER_JOURNAL:
            meta["read_only"] = True

    _save_meta(journal_id, meta)
    return seqs


def append_event(journal_id: str, event_type: str, payload: dict, device_id: str) -> Optional[int]:
    """
    Append a single event. Returns the assigned seq, or None if: journal_id
    fails sanitization, the journal does not exist, the event type/payload is
    invalid, or the journal is already read-only (at the event cap).
    """
    safe = _sanitize_journal_id(journal_id)
    if not safe:
        return None
    if event_type not in _WRITABLE_TYPES:
        # Schema-complete (D1) but not writable via this entry point (yet).
        return None

    with _LOCK:
        meta = _load_meta(safe)
        if meta is None:
            return None
        seqs = _write_events_locked(safe, meta, device_id, [(event_type, payload)])
        return seqs[0] if seqs else None


def append_dialog_batch(journal_id: str, turns: List[Tuple[str, str]], device_id: str, lang: Optional[str] = None, assistant_model: Optional[str] = None, media_intents: Optional[List[dict]] = None) -> List[Optional[int]]:
    """
    Append multiple dialog turns as one atomic batch under a single lock
    acquisition (used by chat_routes.py to write the user+assistant turn of
    one chat round in one go). turns: list of (role, content) tuples.

    assistant_model: if set, assistant turns get an additional payload field
    "model" recording the LLM that actually produced the reply (post-fallback).
    User turns never carry it.

    media_intents (J2): list of {intent_id, config_id, prompt, motivation}
    dicts — the generate_media decisions of this chat round. They are written
    in the same lock acquisition, directly after the dialog turns, each with
    dialog_ref pointing at the assistant turn's seq (the round stays
    contiguous in the journal).

    Returns the list of assigned seqs for the DIALOG turns in order (None
    entries for any turn that failed validation — e.g. bad role or empty
    content — the rest of the batch still proceeds).
    """
    safe = _sanitize_journal_id(journal_id)
    if not safe:
        return [None for _ in turns]

    pairs = []
    for role, content in turns:
        payload = {"role": role, "content": content, "lang": lang}
        if role == "assistant" and assistant_model:
            payload["model"] = assistant_model
        pairs.append(("dialog", payload))

    with _LOCK:
        meta = _load_meta(safe)
        if meta is None:
            return [None for _ in turns]
        seqs = _write_events_locked(safe, meta, device_id, pairs)
        if media_intents:
            assistant_seq = None
            for (role, _content), seq in zip(turns, seqs):
                if role == "assistant" and seq is not None:
                    assistant_seq = seq
            intent_pairs = []
            for mi in media_intents:
                intent_payload = {
                    "intent_id": (mi or {}).get("intent_id"),
                    "config_id": (mi or {}).get("config_id"),
                    "prompt": (mi or {}).get("prompt"),
                    "motivation": (mi or {}).get("motivation"),
                }
                if assistant_seq is not None:
                    intent_payload["dialog_ref"] = assistant_seq
                intent_pairs.append(("media_intent", intent_payload))
            _write_events_locked(safe, meta, device_id, intent_pairs)
        return seqs


_RUN_ID_SAFE = re.compile(r"[A-Za-z0-9_\-]{1,128}")


def find_media_provenance(run_id: str) -> Optional[Dict]:
    """
    Reverse lookup ("Rueckseite" of an artifact): find the media_result event
    carrying this run_id across all journals, plus its media_intent (matched
    by intent_id within the same journal). Returns
    {"journal_id": str, "result": event, "intent": event|None} or None.

    Scans newest journals first (run_ids are globally unique, first hit wins).
    Reads without the lock: files are append-only JSONL and _read_all_lines
    skips torn/corrupt lines.
    """
    if not isinstance(run_id, str) or not _RUN_ID_SAFE.fullmatch(run_id):
        return None
    if not STORAGE_DIR.exists():
        return None
    try:
        files = sorted(STORAGE_DIR.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError:
        return None
    for f in files:
        events = _read_all_lines(f.stem)
        result_ev = None
        for ev in events:
            if ev.get("type") == "media_result" and (ev.get("payload") or {}).get("run_id") == run_id:
                result_ev = ev
                break
        if result_ev is None:
            continue
        intent_ev = None
        intent_id = (result_ev.get("payload") or {}).get("intent_id")
        if intent_id:
            for ev in events:
                if ev.get("type") == "media_intent" and (ev.get("payload") or {}).get("intent_id") == intent_id:
                    intent_ev = ev
                    break
        return {"journal_id": f.stem, "result": result_ev, "intent": intent_ev}
    return None


def read_events(journal_id: str, offset: int = 0, limit: int = READ_LIMIT_DEFAULT) -> Optional[Dict]:
    """
    Return {"events": [...], "meta": {...}} for this journal, events in
    chronological (stored) order, sliced by [offset:offset+limit]. limit is
    hard-clamped to READ_LIMIT_MAX. Returns None if the journal does not
    exist (or journal_id fails sanitization) — callers use this to 404.
    """
    safe = _sanitize_journal_id(journal_id)
    if not safe:
        return None

    meta = _load_meta(safe)
    if meta is None:
        return None

    offset = max(0, offset or 0)
    limit = max(0, min(limit or READ_LIMIT_DEFAULT, READ_LIMIT_MAX))

    all_events = _read_all_lines(safe)
    sliced = all_events[offset:offset + limit]
    return {"events": sliced, "meta": meta}
