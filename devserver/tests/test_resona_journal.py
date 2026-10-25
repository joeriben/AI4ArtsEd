"""
Tests for Resona Werkstatt-Journal core (R1/J1, docs/plans/resona/PLAN_DATENHALTUNG.md).

Covers:
- ensure(): creates a journal + journal/created event; idempotent (second
  call created=False, no second event)
- append/read roundtrip, chronological order
- seq strictly monotonic (including across a mixed batch)
- event-type enum validation (unknown type rejected)
- dialog role validation
- content truncation (4000 dialog / 2000 other)
- event cap -> read-only (append returns None, meta flag set, no front-
  truncation of existing events)
- journal_id sanitization blocks path traversal
- append_dialog_batch is atomic under concurrent threads (interleaved
  batches never produce duplicate/corrupt seqs)
- meta correctness (event_count, last_ts, device_ids union)
- read_events pagination (offset/limit, limit clamp)

Run: python3 -m pytest devserver/tests/test_resona_journal.py -q
(from the worktree root; also works from devserver/ directly)
"""

import sys
import threading
from pathlib import Path

# devserver/tests/test_resona_journal.py -> parents[1] == devserver/
# Mirrors the sys.path convention used by chat_routes.py / other devserver tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import resona_journal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Redirect resona_journal's storage root to a throwaway tmp_path per test,
    so tests never touch (or depend on) real exports/json/resona_journal/ data."""
    monkeypatch.setattr(resona_journal, "STORAGE_DIR", tmp_path / "resona_journal")
    yield


# ---------------------------------------------------------------------------
# ensure()
# ---------------------------------------------------------------------------

def test_ensure_creates_journal_with_created_event():
    device = "device_alpha_2026-07-02"
    meta = resona_journal.ensure(device)

    assert meta is not None
    assert meta["created"] is True
    assert meta["journal_id"] == device
    assert meta["event_count"] == 1
    assert meta["read_only"] is False
    assert meta["device_ids"] == [device]

    result = resona_journal.read_events(device)
    assert len(result["events"]) == 1
    event = result["events"][0]
    assert event["type"] == "journal"
    assert event["payload"]["action"] == "created"
    assert event["seq"] == 1


def test_ensure_is_idempotent_no_second_event():
    device = "device_idem_2026-07-02"
    first = resona_journal.ensure(device)
    second = resona_journal.ensure(device)

    assert first["created"] is True
    assert second["created"] is False
    assert second["event_count"] == 1  # unchanged

    result = resona_journal.read_events(device)
    assert len(result["events"]) == 1  # still just the one created event


def test_ensure_invalid_device_id_returns_none():
    assert resona_journal.ensure(None) is None
    assert resona_journal.ensure("") is None


def test_journal_exists():
    device = "device_exists_2026-07-02"
    assert resona_journal.journal_exists(device) is False
    resona_journal.ensure(device)
    assert resona_journal.journal_exists(device) is True


# ---------------------------------------------------------------------------
# append/read roundtrip + chronology
# ---------------------------------------------------------------------------

def test_append_dialog_batch_roundtrip():
    device = "device_dialog_2026-07-02"
    resona_journal.ensure(device)

    seqs = resona_journal.append_dialog_batch(
        device,
        [("user", "hello resona"), ("assistant", "hello there")],
        device_id=device,
        lang="de",
    )
    assert seqs == [2, 3]

    result = resona_journal.read_events(device)
    events = result["events"]
    assert len(events) == 3  # created + 2 dialog turns

    # Chronological order
    assert events[0]["type"] == "journal"
    assert events[1]["type"] == "dialog"
    assert events[1]["payload"]["role"] == "user"
    assert events[1]["payload"]["content"] == "hello resona"
    assert events[1]["payload"]["lang"] == "de"
    assert events[2]["type"] == "dialog"
    assert events[2]["payload"]["role"] == "assistant"
    assert events[2]["payload"]["content"] == "hello there"


def test_append_event_requires_existing_journal():
    device = "device_noexist_2026-07-02"
    seq = resona_journal.append_event(device, "dialog", {"role": "user", "content": "hi"}, device_id=device)
    assert seq is None


def test_append_dialog_batch_requires_existing_journal():
    device = "device_noexist_batch_2026-07-02"
    seqs = resona_journal.append_dialog_batch(device, [("user", "hi")], device_id=device)
    assert seqs == [None]


def test_append_event_single_dialog():
    device = "device_single_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(device, "dialog", {"role": "user", "content": "solo turn"}, device_id=device)
    assert seq == 2

    result = resona_journal.read_events(device)
    assert result["events"][1]["payload"]["content"] == "solo turn"


# ---------------------------------------------------------------------------
# seq monotonicity
# ---------------------------------------------------------------------------

def test_seq_strictly_monotonic_across_calls():
    device = "device_seq_2026-07-02"
    resona_journal.ensure(device)  # seq 1

    seqs1 = resona_journal.append_dialog_batch(device, [("user", "a"), ("assistant", "b")], device_id=device)
    assert seqs1 == [2, 3]

    seqs2 = resona_journal.append_dialog_batch(device, [("user", "c"), ("assistant", "d")], device_id=device)
    assert seqs2 == [4, 5]

    result = resona_journal.read_events(device)
    all_seqs = [e["seq"] for e in result["events"]]
    assert all_seqs == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Event-type enum validation
# ---------------------------------------------------------------------------

def test_unknown_event_type_rejected():
    device = "device_badtype_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(device, "not_a_real_type", {"foo": "bar"}, device_id=device)
    assert seq is None

    result = resona_journal.read_events(device)
    assert len(result["events"]) == 1  # only the created event; nothing written


def test_self_activation_not_writable_before_r3():
    """self_activation stays schema-only until Eigenaktivitaet Stufe 1 (R3).
    memory/media_intent/media_result became writable in J2/J3 — with valid
    payloads; empty payloads still fail their contracts."""
    device = "device_schema_only_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(device, "self_activation", {"trigger": "checkin"}, device_id=device)
    assert seq is None
    for event_type in ("memory", "media_intent", "media_result"):
        seq = resona_journal.append_event(device, event_type, {}, device_id=device)
        assert seq is None, f"{event_type} with empty payload must fail its contract"


def test_valid_event_types_enum_is_complete():
    assert resona_journal.VALID_EVENT_TYPES == (
        "dialog", "memory", "media_intent", "media_result", "journal", "self_activation",
    )


# ---------------------------------------------------------------------------
# Role validation
# ---------------------------------------------------------------------------

def test_dialog_bad_role_rejected():
    device = "device_role_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(device, "dialog", {"role": "system", "content": "sneaky"}, device_id=device)
    assert seq is None

    result = resona_journal.read_events(device)
    assert len(result["events"]) == 1  # nothing appended


def test_dialog_empty_content_rejected():
    device = "device_emptycontent_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(device, "dialog", {"role": "user", "content": "   "}, device_id=device)
    assert seq is None


@pytest.mark.parametrize("role", list(resona_journal.VALID_DIALOG_ROLES))
def test_all_valid_dialog_roles_accepted(role):
    device = f"device_role_{role}_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(device, "dialog", {"role": role, "content": "x"}, device_id=device)
    assert seq is not None


# ---------------------------------------------------------------------------
# Content truncation
# ---------------------------------------------------------------------------

def test_dialog_content_truncated_at_4000():
    device = "device_trunc_dialog_2026-07-02"
    resona_journal.ensure(device)
    long_content = "x" * (resona_journal.MAX_DIALOG_CHARS + 500)
    resona_journal.append_event(device, "dialog", {"role": "user", "content": long_content}, device_id=device)

    result = resona_journal.read_events(device)
    stored = result["events"][1]["payload"]["content"]
    assert len(stored) == resona_journal.MAX_DIALOG_CHARS


def test_journal_label_truncated_at_2000():
    device = "device_trunc_other_2026-07-02"
    resona_journal.ensure(device)
    long_label = "y" * (resona_journal.MAX_OTHER_CHARS + 500)
    resona_journal.append_event(device, "journal", {"action": "labeled", "label": long_label}, device_id=device)

    result = resona_journal.read_events(device)
    stored = result["events"][1]["payload"]["label"]
    assert len(stored) == resona_journal.MAX_OTHER_CHARS


# ---------------------------------------------------------------------------
# Event cap -> read-only
# ---------------------------------------------------------------------------

def test_event_cap_makes_journal_read_only_no_front_truncation():
    device = "device_cap_2026-07-02"
    resona_journal.ensure(device)  # seq 1

    # Fill up to exactly the cap using single dialog events.
    remaining = resona_journal.MAX_EVENTS_PER_JOURNAL - 1
    for i in range(remaining):
        seq = resona_journal.append_event(device, "dialog", {"role": "user", "content": f"turn {i}"}, device_id=device)
        assert seq is not None

    result = resona_journal.read_events(device, limit=resona_journal.READ_LIMIT_MAX)
    assert result["meta"]["event_count"] == resona_journal.MAX_EVENTS_PER_JOURNAL
    assert result["meta"]["read_only"] is True

    # One more append must be refused (None), not silently drop the oldest event.
    seq = resona_journal.append_event(device, "dialog", {"role": "user", "content": "overflow"}, device_id=device)
    assert seq is None

    result2 = resona_journal.read_events(device, limit=resona_journal.READ_LIMIT_MAX)
    assert result2["meta"]["event_count"] == resona_journal.MAX_EVENTS_PER_JOURNAL  # unchanged
    # The very first event (journal/created, seq=1) must still be present --
    # a Werkstattbuch does not cut off its front.
    first_events = resona_journal.read_events(device, offset=0, limit=1)
    assert first_events["events"][0]["seq"] == 1
    assert first_events["events"][0]["type"] == "journal"


def test_batch_append_refused_once_read_only():
    device = "device_cap_batch_2026-07-02"
    resona_journal.ensure(device)
    remaining = resona_journal.MAX_EVENTS_PER_JOURNAL - 1
    for i in range(remaining):
        resona_journal.append_event(device, "dialog", {"role": "user", "content": f"t{i}"}, device_id=device)

    seqs = resona_journal.append_dialog_batch(device, [("user", "a"), ("assistant", "b")], device_id=device)
    assert seqs == [None, None]


# ---------------------------------------------------------------------------
# Sanitization / path traversal
# ---------------------------------------------------------------------------

def test_sanitization_blocks_path_traversal():
    malicious_ids = [
        "../../etc/passwd",
        "../../../secret",
        "..%2f..%2fetc%2fpasswd",
        "/etc/passwd",
    ]
    for bad_id in malicious_ids:
        meta = resona_journal.ensure(bad_id)
        # Either sanitized to a safe stem, or rejected outright -- never allowed
        # to escape STORAGE_DIR. Verify no file was written outside STORAGE_DIR.
        if meta is not None:
            journal_path = resona_journal._events_path(meta["journal_id"])
            resolved_storage = resona_journal.STORAGE_DIR.resolve()
            # journal_path's parent must be exactly STORAGE_DIR (no traversal).
            assert journal_path.parent.resolve() == resolved_storage, f"path traversal escaped for input {bad_id!r}"
            assert ".." not in meta["journal_id"]
            assert "/" not in meta["journal_id"]


def test_sanitize_journal_id_rejects_empty_and_none():
    assert resona_journal._sanitize_journal_id(None) is None
    assert resona_journal._sanitize_journal_id("") is None
    assert resona_journal._sanitize_journal_id("...") is None  # strips to empty
    assert resona_journal._sanitize_journal_id(123) is None  # not a string


def test_read_events_unsanitizable_id_returns_none():
    assert resona_journal.read_events("") is None
    assert resona_journal.read_events(None) is None


# ---------------------------------------------------------------------------
# Concurrency: append_dialog_batch is atomic
# ---------------------------------------------------------------------------

def test_concurrent_dialog_batches_no_duplicate_or_corrupt_seqs():
    device = "device_concurrent_2026-07-02"
    resona_journal.ensure(device)  # seq 1

    NUM_THREADS = 2
    BATCHES_PER_THREAD = 20

    def worker(thread_idx):
        for batch_idx in range(BATCHES_PER_THREAD):
            resona_journal.append_dialog_batch(
                device,
                [("user", f"t{thread_idx}-b{batch_idx}-user"), ("assistant", f"t{thread_idx}-b{batch_idx}-assistant")],
                device_id=device,
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(NUM_THREADS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    result = resona_journal.read_events(device, limit=resona_journal.READ_LIMIT_MAX)
    events = result["events"]

    expected_count = 1 + NUM_THREADS * BATCHES_PER_THREAD * 2  # created + all dialog turns
    assert len(events) == expected_count

    seqs = [e["seq"] for e in events]
    assert len(seqs) == len(set(seqs)), "duplicate seq detected -- lock did not serialize batches"
    assert seqs == sorted(seqs), "seqs not monotonic -- interleaving corrupted order"
    assert seqs == list(range(1, expected_count + 1)), "seq sequence has gaps"

    # No corrupt lines: every event must have parsed as a dict with the envelope fields.
    for e in events:
        assert set(("v", "seq", "ts", "type", "device_id", "payload")).issubset(e.keys())

    assert result["meta"]["event_count"] == expected_count


# ---------------------------------------------------------------------------
# Meta correctness
# ---------------------------------------------------------------------------

def test_meta_event_count_and_last_ts_update():
    device = "device_meta_2026-07-02"
    resona_journal.ensure(device)
    resona_journal.append_dialog_batch(device, [("user", "a"), ("assistant", "b")], device_id=device)

    result = resona_journal.read_events(device)
    meta = result["meta"]
    assert meta["event_count"] == 3
    assert meta["last_ts"] is not None
    from datetime import datetime
    datetime.fromisoformat(meta["last_ts"])  # parseable ISO-8601


def test_meta_device_ids_union():
    journal_device = "shared_journal_2026-07-02"
    resona_journal.ensure(journal_device)

    other_device = "other_device_same_journal_2026-07-02"
    resona_journal.append_event(journal_device, "dialog", {"role": "user", "content": "hi"}, device_id=other_device)

    result = resona_journal.read_events(journal_device)
    device_ids = result["meta"]["device_ids"]
    assert journal_device in device_ids
    assert other_device in device_ids
    assert len(device_ids) == len(set(device_ids))  # union, no dupes


def test_meta_schema_fields_present():
    device = "device_schema_2026-07-02"
    meta = resona_journal.ensure(device)
    expected_keys = {
        "journal_id", "created_ts", "label", "schema_version",
        "device_ids", "event_count", "last_ts", "read_only", "created",
    }
    assert expected_keys.issubset(meta.keys())
    assert meta["schema_version"] == 1
    assert meta["label"] is None


# ---------------------------------------------------------------------------
# read_events pagination
# ---------------------------------------------------------------------------

def test_read_events_pagination_offset_and_limit():
    device = "device_page_2026-07-02"
    resona_journal.ensure(device)  # seq 1
    for i in range(10):
        resona_journal.append_event(device, "dialog", {"role": "user", "content": f"turn {i}"}, device_id=device)
    # Now 11 events total (1 created + 10 dialog)

    page1 = resona_journal.read_events(device, offset=0, limit=5)
    assert len(page1["events"]) == 5
    assert page1["events"][0]["seq"] == 1

    page2 = resona_journal.read_events(device, offset=5, limit=5)
    assert len(page2["events"]) == 5
    assert page2["events"][0]["seq"] == 6

    page3 = resona_journal.read_events(device, offset=10, limit=5)
    assert len(page3["events"]) == 1
    assert page3["events"][0]["seq"] == 11


def test_read_events_limit_clamped_to_max():
    device = "device_clamp_2026-07-02"
    resona_journal.ensure(device)
    result = resona_journal.read_events(device, offset=0, limit=999999)
    # Only 1 event exists, so this doesn't directly prove the clamp, but the
    # clamp itself must not raise or misbehave with an oversized limit.
    assert len(result["events"]) == 1


def test_read_events_default_limit_used_when_none():
    device = "device_defaultlimit_2026-07-02"
    resona_journal.ensure(device)
    result = resona_journal.read_events(device)  # default offset=0, limit=default
    assert len(result["events"]) == 1


def test_read_events_nonexistent_journal_returns_none():
    assert resona_journal.read_events("device_never_created_2026-07-02") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


# ---------------------------------------------------------------------------
# Model provenance on assistant dialog events
# ---------------------------------------------------------------------------

def test_assistant_model_recorded_on_assistant_turn_only():
    device = "device_model_2026-07-02"
    resona_journal.ensure(device)
    seqs = resona_journal.append_dialog_batch(
        device,
        [("user", "wie sieht der plan aus?"), ("assistant", "hier ist der plan")],
        device_id=device,
        assistant_model="mammouth/claude-opus-4-8",
    )
    assert seqs == [2, 3]
    events = resona_journal.read_events(device)["events"]
    user_ev = events[1]
    assistant_ev = events[2]
    assert user_ev["payload"]["role"] == "user"
    assert "model" not in user_ev["payload"]
    assert assistant_ev["payload"]["role"] == "assistant"
    assert assistant_ev["payload"]["model"] == "mammouth/claude-opus-4-8"


def test_no_model_field_without_assistant_model():
    device = "device_nomodel_2026-07-02"
    resona_journal.ensure(device)
    resona_journal.append_dialog_batch(
        device, [("user", "a"), ("assistant", "b")], device_id=device
    )
    events = resona_journal.read_events(device)["events"]
    for ev in events:
        if ev["type"] == "dialog":
            assert "model" not in ev["payload"]


# ---------------------------------------------------------------------------
# J2: media provenance (media_intent via dialog batch, media_result, lookup)
# ---------------------------------------------------------------------------

def test_media_intent_batch_writes_after_dialog_with_dialog_ref():
    device = "device_intent_2026-07-02"
    resona_journal.ensure(device)
    seqs = resona_journal.append_dialog_batch(
        device,
        [("user", "zeig uns was"), ("assistant", "ich lege euch ein bild hin")],
        device_id=device,
        media_intents=[{
            "intent_id": "mi_abc12345",
            "config_id": "sd35_large",
            "prompt": "a red thread through an empty stairwell",
            "motivation": "a lens on your staircase idea",
        }],
    )
    assert seqs == [2, 3]
    events = resona_journal.read_events(device)["events"]
    assert [e["type"] for e in events] == ["journal", "dialog", "dialog", "media_intent"]
    intent = events[3]["payload"]
    assert intent["intent_id"] == "mi_abc12345"
    assert intent["config_id"] == "sd35_large"
    assert intent["motivation"] == "a lens on your staircase idea"
    assert intent["dialog_ref"] == 3  # seq of the assistant turn


def test_media_intent_motivation_optional():
    device = "device_intent_nomot_2026-07-02"
    resona_journal.ensure(device)
    resona_journal.append_dialog_batch(
        device,
        [("user", "a"), ("assistant", "b")],
        device_id=device,
        media_intents=[{"intent_id": "mi_x", "config_id": "flux2", "prompt": "p"}],
    )
    events = resona_journal.read_events(device)["events"]
    assert events[-1]["type"] == "media_intent"
    assert events[-1]["payload"]["motivation"] is None


def test_media_result_roundtrip_and_status_validation():
    device = "device_result_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(
        device,
        "media_result",
        {"intent_id": "mi_x", "run_id": "run_123", "status": "completed",
         "media_type": "image", "media_url": "/api/media/image/run_123/0", "seed": 42},
        device_id=device,
    )
    assert seq == 2
    bad = resona_journal.append_event(
        device, "media_result",
        {"intent_id": "mi_x", "status": "exploded"},
        device_id=device,
    )
    assert bad is None
    events = resona_journal.read_events(device)["events"]
    payload = events[1]["payload"]
    assert payload["status"] == "completed"
    assert payload["run_id"] == "run_123"
    assert payload["seed"] == 42


def test_find_media_provenance_returns_intent_and_result():
    device = "device_prov_2026-07-02"
    resona_journal.ensure(device)
    resona_journal.append_dialog_batch(
        device,
        [("user", "u"), ("assistant", "a")],
        device_id=device,
        media_intents=[{"intent_id": "mi_prov1", "config_id": "sd35_large",
                        "prompt": "p", "motivation": "m"}],
    )
    resona_journal.append_event(
        device, "media_result",
        {"intent_id": "mi_prov1", "run_id": "run_prov_9", "status": "completed",
         "media_type": "image", "media_url": "/api/media/image/run_prov_9/0"},
        device_id=device,
    )
    hit = resona_journal.find_media_provenance("run_prov_9")
    assert hit is not None
    assert hit["journal_id"] == "device_prov_2026-07-02"
    assert hit["result"]["payload"]["run_id"] == "run_prov_9"
    assert hit["intent"]["payload"]["intent_id"] == "mi_prov1"
    assert hit["intent"]["payload"]["motivation"] == "m"


def test_find_media_provenance_unknown_and_unsafe_run_id():
    assert resona_journal.find_media_provenance("run_does_not_exist") is None
    assert resona_journal.find_media_provenance("../etc/passwd") is None
    assert resona_journal.find_media_provenance("") is None


# ---------------------------------------------------------------------------
# J3: memory dual-write (tool boundary -> journal mirror)
# ---------------------------------------------------------------------------

def test_memory_event_contract():
    device = "device_mem_2026-07-02"
    resona_journal.ensure(device)
    seq = resona_journal.append_event(
        device, "memory", {"kind": "goal", "content": "collage workshop planned"},
        device_id=device,
    )
    assert seq == 2
    assert resona_journal.append_event(device, "memory", {"kind": "", "content": "x"}, device_id=device) is None
    assert resona_journal.append_event(device, "memory", {"kind": "goal", "content": "  "}, device_id=device) is None


def test_remember_dual_writes_memory_event(monkeypatch, tmp_path):
    from my_app.services import resona_memory
    from my_app.services.tool_registry import get_tool_registry
    monkeypatch.setattr(resona_memory, "STORAGE_DIR", tmp_path / "resona_memory")
    device = "device_dual_2026-07-02"
    resona_journal.ensure(device)
    out = get_tool_registry().execute(
        "remember",
        {"kind": "goal", "content": "Collage-Werkstatt geplant"},
        context={"device_id": device, "run_id": None, "journal_id": device},
    )
    assert not str(out).startswith("Error")
    events = resona_journal.read_events(device)["events"]
    mem = [e for e in events if e["type"] == "memory"]
    assert len(mem) == 1
    assert mem[0]["payload"] == {"kind": "goal", "content": "Collage-Werkstatt geplant"}


def test_remember_without_journal_id_writes_no_memory_event(monkeypatch, tmp_path):
    from my_app.services import resona_memory
    from my_app.services.tool_registry import get_tool_registry
    monkeypatch.setattr(resona_memory, "STORAGE_DIR", tmp_path / "resona_memory")
    device = "device_dual_off_2026-07-02"
    resona_journal.ensure(device)
    out = get_tool_registry().execute(
        "remember",
        {"kind": "goal", "content": "ohne journal"},
        context={"device_id": device, "run_id": None},
    )
    assert not str(out).startswith("Error")
    events = resona_journal.read_events(device)["events"]
    assert [e for e in events if e["type"] == "memory"] == []
