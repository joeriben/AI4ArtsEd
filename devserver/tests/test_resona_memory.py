"""
Tests for Resona Phase 2 episodic memory (docs/plans/resona/PLAN.md).

Covers:
- remember -> persist -> recall roundtrip (via resona_memory directly and via
  the tool_registry handlers, which is the real path chat_routes.py uses)
- kind validation (bad kind rejected)
- device isolation (device A never sees device B's records)
- record cap (oldest dropped past MAX_RECORDS_PER_DEVICE)
- scoping: get_openai_format(scope='resona') == exactly the granted set
  {generate_media, remember, recall, lookup_shared_favorites, view_favorite,
  lookup_reference, lookup_interception, run_canvas_graph, canvas_graph_library};
  scope=None (Trashy) contains none of the Resona-exclusive tools; the overlap is
  exactly the two granted lookups.

Run: python3 -m pytest devserver/tests/test_resona_memory.py -q
(from the worktree root; also works from devserver/ directly)
"""

import sys
from pathlib import Path

# devserver/tests/test_resona_memory.py -> parents[1] == devserver/
# Mirrors the sys.path convention used by chat_routes.py / other devserver tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import resona_memory
from my_app.services.tool_registry import get_tool_registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Redirect resona_memory's storage root to a throwaway tmp_path per test,
    so tests never touch (or depend on) real exports/json/resona_memory/ data."""
    monkeypatch.setattr(resona_memory, "STORAGE_DIR", tmp_path / "resona_memory")
    yield


# ---------------------------------------------------------------------------
# Core roundtrip (direct module API)
# ---------------------------------------------------------------------------

def test_remember_recall_roundtrip():
    device = "device_alpha_2026-07-02"
    result = resona_memory.remember(device, "goal", "Plan a stop-motion short about seasons")
    assert result.startswith("Remembered")

    found = resona_memory.recall(device, "stop-motion")
    assert "stop-motion short about seasons" in found
    assert "goal" in found


def test_recall_no_hits_is_honest():
    device = "device_alpha_2026-07-02"
    resona_memory.remember(device, "note", "Group likes bright colors")
    result = resona_memory.recall(device, "xylophone-nonsense-query")
    assert "No memory found" in result
    assert "xylophone-nonsense-query" in result


def test_recall_empty_query():
    device = "device_alpha_2026-07-02"
    resona_memory.remember(device, "note", "something")
    result = resona_memory.recall(device, "")
    assert "No memory found" in result


def test_recall_no_memory_yet():
    device = "device_never_used_2026-07-02"
    result = resona_memory.recall(device, "anything")
    assert "No memory found" in result


def test_recall_is_most_recent_first():
    device = "device_order_2026-07-02"
    resona_memory.remember(device, "note", "storyboard step one")
    resona_memory.remember(device, "note", "storyboard step two")
    resona_memory.remember(device, "note", "storyboard step three")
    result = resona_memory.recall(device, "storyboard")
    lines = [l for l in result.split("\n") if l.strip()]
    assert "step three" in lines[0]


# ---------------------------------------------------------------------------
# Kind validation
# ---------------------------------------------------------------------------

def test_bad_kind_rejected():
    device = "device_kind_2026-07-02"
    result = resona_memory.remember(device, "confession", "I feel bad")
    assert result.startswith("Error")
    assert "not a valid kind" in result
    # And it must not have been persisted
    assert resona_memory.load_all(device) == []


@pytest.mark.parametrize("kind", list(resona_memory.VALID_KINDS))
def test_all_valid_kinds_accepted(kind):
    device = f"device_kind_{kind}_2026-07-02"
    result = resona_memory.remember(device, kind, "some content")
    assert result == f"Remembered ({kind})."


def test_empty_content_rejected():
    device = "device_content_2026-07-02"
    result = resona_memory.remember(device, "goal", "   ")
    assert result.startswith("Error")
    assert resona_memory.load_all(device) == []


def test_missing_device_id_rejected():
    result = resona_memory.remember(None, "goal", "something")
    assert result.startswith("Error")
    assert "device" in result.lower()


# ---------------------------------------------------------------------------
# Device isolation
# ---------------------------------------------------------------------------

def test_device_isolation():
    device_a = "device_A_2026-07-02"
    device_b = "device_B_2026-07-02"

    resona_memory.remember(device_a, "goal", "Device A's secret storyboard plan")
    resona_memory.remember(device_b, "goal", "Device B's completely different plan")

    a_records = resona_memory.load_all(device_a)
    b_records = resona_memory.load_all(device_b)

    assert len(a_records) == 1
    assert len(b_records) == 1
    assert "Device A" in a_records[0]["content"]
    assert "Device B" in b_records[0]["content"]

    # Cross-device recall must find nothing
    result = resona_memory.recall(device_b, "Device A")
    assert "No memory found" in result


def test_device_id_sanitization_prevents_collision():
    # Two device_ids that differ only in characters stripped by sanitization
    # must NOT silently collide onto the same file if that would leak data
    # between distinct raw device_ids.
    device_1 = "device/with/slashes"
    device_2 = "device-with-slashes"
    resona_memory.remember(device_1, "note", "from device 1")
    resona_memory.remember(device_2, "note", "from device 2")
    # Whatever the sanitized form is, each device_id's own records must be
    # retrievable via recall with that same raw device_id.
    r1 = resona_memory.recall(device_1, "from device")
    r2 = resona_memory.recall(device_2, "from device")
    assert "from device 1" in r1
    assert "from device 2" in r2


# ---------------------------------------------------------------------------
# Record cap
# ---------------------------------------------------------------------------

def test_record_cap_drops_oldest():
    device = "device_cap_2026-07-02"
    total_to_write = resona_memory.MAX_RECORDS_PER_DEVICE + 25
    for i in range(total_to_write):
        resona_memory.remember(device, "note", f"record number {i}")

    records = resona_memory.load_all(device)
    assert len(records) == resona_memory.MAX_RECORDS_PER_DEVICE
    # Oldest (0..24) must have been dropped; the tail must be intact.
    contents = [r["content"] for r in records]
    assert "record number 0" not in contents
    assert f"record number {total_to_write - 1}" in contents


def test_content_length_is_bounded():
    device = "device_longcontent_2026-07-02"
    long_content = "x" * (resona_memory.MAX_CONTENT_CHARS + 500)
    resona_memory.remember(device, "note", long_content)
    records = resona_memory.load_all(device)
    assert len(records[0]["content"]) == resona_memory.MAX_CONTENT_CHARS


# ---------------------------------------------------------------------------
# Record shape
# ---------------------------------------------------------------------------

def test_record_shape_has_required_fields():
    device = "device_shape_2026-07-02"
    resona_memory.remember(device, "milestone", "Reached panel 4", run_id="run-abc",
                           journal_id="device_shape_2026-07-02")
    record = resona_memory.load_all(device)[0]
    # journal_id joined the shape so "new dialog" can drop one conversation's
    # notes without touching a kept conversation's (resona_memory.forget_journal,
    # devserver/tests/test_resona_new_dialog.py).
    assert set(record.keys()) == {"kind", "content", "ts", "run_id", "journal_id"}
    assert record["kind"] == "milestone"
    assert record["run_id"] == "run-abc"
    assert record["journal_id"] == "device_shape_2026-07-02"
    # ISO-8601 timestamp, parseable
    from datetime import datetime
    datetime.fromisoformat(record["ts"])


# ---------------------------------------------------------------------------
# Tool registry integration: the real path chat_routes.py uses
# ---------------------------------------------------------------------------

def test_registry_remember_recall_roundtrip_via_context():
    """The device_id must come from execute()'s context param, never from the
    model-supplied arguments — mirrors how chat_routes.py binds it."""
    registry = get_tool_registry()
    device = "device_registry_2026-07-02"
    ctx = {"device_id": device, "run_id": "run-xyz"}

    result = registry.execute(
        "remember",
        {"kind": "canvas_solution", "content": "Overhead rig with binder clips worked well"},
        context=ctx,
    )
    assert result.startswith("Remembered")

    recalled = registry.execute("recall", {"query": "binder clips"}, context=ctx)
    assert "binder clips" in recalled


def test_registry_remember_ignores_model_supplied_device_id():
    """A model could try to smuggle a device_id/_device_id in its tool call
    arguments — execute() must always override with the real request context."""
    registry = get_tool_registry()
    real_device = "device_real_2026-07-02"
    spoofed_device = "device_spoofed_2026-07-02"
    ctx = {"device_id": real_device, "run_id": None}

    # Model tries to sneak in a different device via _device_id (the reserved
    # key execute() itself uses) and also via a plain 'device_id' argument.
    registry.execute(
        "remember",
        {"kind": "note", "content": "spoof attempt", "_device_id": spoofed_device, "device_id": spoofed_device},
        context=ctx,
    )

    real_records = resona_memory.load_all(real_device)
    spoofed_records = resona_memory.load_all(spoofed_device)
    assert len(real_records) == 1
    assert real_records[0]["content"] == "spoof attempt"
    assert spoofed_records == []


def test_registry_remember_without_context_fails_safely():
    """If a caller forgets to bind context (e.g. a non-resona code path), the
    handler must fail with a clear error, not silently write to nowhere."""
    registry = get_tool_registry()
    result = registry.execute("remember", {"kind": "note", "content": "no context"}, context=None)
    assert result.startswith("Error")


def test_registry_bad_kind_via_tool_call():
    registry = get_tool_registry()
    ctx = {"device_id": "device_badkind_2026-07-02", "run_id": None}
    result = registry.execute("remember", {"kind": "not_a_kind", "content": "x"}, context=ctx)
    assert result.startswith("Error")


# ---------------------------------------------------------------------------
# Scope non-inheritance (the safety-critical guarantee)
# ---------------------------------------------------------------------------

def test_resona_scope_has_exactly_the_granted_tools():
    registry = get_tool_registry()
    resona_tools = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    assert resona_tools == {
        "generate_media",
        "compose_media",           # R-grant: post-production Bild+Ton
        "remember",
        "recall",
        "lookup_shared_favorites",
        "view_favorite",
        "view_run",                # Wahrnehmungspflicht 2026-07-16 (own runs)
        "view_upload",             # Perception grant 2026-07-17 (brought files)
        "lookup_reference",
        "lookup_interception",
        "run_canvas_graph",
        "canvas_graph_library",
        "search_websites",         # web perception grant
        "read_webpage",            # web perception grant
        "lookup_knowledge",        # Knowledge library Phase 1 (2026-07-04 grant)
        "read_knowledge",          # Knowledge library Phase 1 (2026-07-04 grant)
        "lookup_place",            # Places grant 2026-08-11 (both scopes)
    }


def test_trashy_universal_scope_excludes_memory_tools():
    registry = get_tool_registry()
    universal_tools = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    assert "remember" not in universal_tools
    assert "recall" not in universal_tools
    assert "generate_media" not in universal_tools
    assert "view_upload" not in universal_tools
    # Trashy keeps its own universal tools (unaffected by Resona's addition)
    assert "lookup_reference" in universal_tools
    assert "lookup_interception" in universal_tools


def test_scope_overlap_is_exactly_the_granted_lookups():
    # Both scopes hold a tool only by an explicit "default"+"resona" tag: the
    # two platform lookups (2026-07-03) and lookup_place (2026-08-11, what a lab
    # instrument or comparison mode says about its own technology). Everything
    # else stays exclusive to its side.
    registry = get_tool_registry()
    universal_tools = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    resona_tools = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    assert universal_tools & resona_tools == {
        "lookup_reference", "lookup_interception", "lookup_place"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
