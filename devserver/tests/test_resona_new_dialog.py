"""
Tests for the "new dialog" path — dropping a conversation must take Resona's
notes from that conversation with it, and nothing else.

Three bugs are pinned down here:

1. The reported one. DELETE /api/resona/journal/<jid> removed the journal's
   .jsonl+.meta.json while exports/json/resona_memory/<device_id>.json stayed on
   disk, and chat_routes._build_resona_memory_digest re-injected it into every
   following turn. "Delete" left the memory standing.

2. The one a whole-file purge would have introduced. new_journal() mints
   <base>-g2/-g3 for the SAME device, and a journal carried across days collects
   one device_id per day, so one memory file holds several conversations.
   Dropping the file would destroy the notes of conversations that "new
   conversation" promises to keep.

3. The pause hole. Pausing the journal used to be expressed by withholding
   journal_id from the chat request, which also stripped every record of the
   conversation it was made in — so those records could never be dropped by
   anything, ever. The pause is now stated separately (journal_paused): the
   recording stops, the attribution does not.

Run: python3 -m pytest devserver/tests/test_resona_new_dialog.py -q
"""

import sys
from pathlib import Path

# devserver/tests/test_resona_new_dialog.py -> parents[1] == devserver/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.services import resona_journal, resona_memory, resona_question_filter
from my_app.services.tool_registry import get_tool_registry
from my_app.routes.resona_routes import resona_bp


DEVICE_A = "aaaaaaaa-1111-2222-3333-444444444444_2026-08-07"
DEVICE_A_NEXT_DAY = "aaaaaaaa-1111-2222-3333-444444444444_2026-08-09"
DEVICE_B = "bbbbbbbb-1111-2222-3333-444444444444_2026-08-07"


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Both stores redirected to throwaway dirs, so no test can touch real
    workshop data in exports/json/."""
    monkeypatch.setattr(resona_memory, "STORAGE_DIR", tmp_path / "resona_memory")
    monkeypatch.setattr(resona_journal, "STORAGE_DIR", tmp_path / "resona_journal")
    yield


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(resona_bp)
    return app.test_client()


def contents(device_id):
    return [r["content"] for r in resona_memory.load_all(device_id)]


def unstamp(device_id):
    """Rewrite this device's records into the pre-change shape (no journal_id
    key at all), so the legacy path can be tested for what it is."""
    records = resona_memory.load_all(device_id)
    for rec in records:
        rec.pop("journal_id", None)
    resona_memory._save_records(device_id, records)


# ---------------------------------------------------------------------------
# The stamp that makes a record attributable
# ---------------------------------------------------------------------------

def test_remember_stamps_the_journal_it_was_made_in():
    resona_memory.remember(DEVICE_A, "goal", "in a journal", journal_id="J1")
    assert resona_memory.load_all(DEVICE_A)[0]["journal_id"] == "J1"


def test_remember_with_no_journal_carries_the_key_as_none():
    """No journal at all (a failed ensure). The key must be present anyway —
    forget_journal tells 'made outside any journal' from 'written before
    records were stamped' by presence, not by value."""
    resona_memory.remember(DEVICE_A, "note", "no journal")
    rec = resona_memory.load_all(DEVICE_A)[0]
    assert "journal_id" in rec and rec["journal_id"] is None


def test_a_paused_journal_still_stamps_but_records_nothing():
    """K1: pausing stops the RECORDING. It must not make the note forget which
    dialog it was made in — that is what left paused notes undroppable."""
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    before = resona_journal.read_events(jid)["meta"]["event_count"]

    get_tool_registry().execute(
        "remember",
        {"kind": "note", "content": "noted while paused"},
        context={"device_id": DEVICE_A, "journal_id": jid, "journal_paused": True},
    )

    assert resona_memory.load_all(DEVICE_A)[0]["journal_id"] == jid
    events = resona_journal.read_events(jid)
    assert events["meta"]["event_count"] == before
    assert not [e for e in events["events"] if e["type"] == "memory"]


def test_an_unpaused_journal_records_the_note_as_well():
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]

    get_tool_registry().execute(
        "remember",
        {"kind": "note", "content": "noted openly"},
        context={"device_id": DEVICE_A, "journal_id": jid, "journal_paused": False},
    )

    mirrored = [e for e in resona_journal.read_events(jid)["events"] if e["type"] == "memory"]
    assert [e["payload"]["content"] for e in mirrored] == ["noted openly"]


# ---------------------------------------------------------------------------
# forget_journal — exact
# ---------------------------------------------------------------------------

def test_forget_journal_drops_only_that_journals_records():
    resona_memory.remember(DEVICE_A, "goal", "of J1", journal_id="J1")
    resona_memory.remember(DEVICE_A, "goal", "of J2", journal_id="J2")

    assert resona_memory.forget_journal(DEVICE_A, "J1") == 1
    assert contents(DEVICE_A) == ["of J2"]


def test_forget_journal_leaves_records_of_no_journal_standing():
    resona_memory.remember(DEVICE_A, "goal", "of J1", journal_id="J1")
    resona_memory.remember(DEVICE_A, "note", "made with no journal")

    assert resona_memory.forget_journal(DEVICE_A, "J1") == 1
    assert contents(DEVICE_A) == ["made with no journal"]


def test_forget_journal_ignores_unstamped_records_unless_asked():
    """Records from before this change carry no journal_id key at all."""
    resona_memory.remember(DEVICE_A, "note", "legacy")
    unstamp(DEVICE_A)

    assert resona_memory.forget_journal(DEVICE_A, "J1") == 0
    assert contents(DEVICE_A) == ["legacy"]
    assert resona_memory.forget_journal(DEVICE_A, "J1", include_unstamped=True) == 1
    assert contents(DEVICE_A) == []


def test_forget_journal_removes_the_file_when_nothing_is_left():
    resona_memory.remember(DEVICE_A, "goal", "of J1", journal_id="J1")
    resona_memory.forget_journal(DEVICE_A, "J1")
    assert not resona_memory._device_path(DEVICE_A).exists()


@pytest.mark.parametrize("device,journal", [
    ("", "J1"), ("...", "J1"), (None, "J1"),
    (DEVICE_A, ""), (DEVICE_A, None), (DEVICE_A, "   "),
])
def test_forget_journal_is_a_noop_on_garbage(device, journal):
    resona_memory.remember(DEVICE_A, "goal", "untouched", journal_id="J1")
    assert resona_memory.forget_journal(device, journal) == 0
    assert contents(DEVICE_A) == ["untouched"]


def test_a_silently_unwritten_purge_raises_rather_than_reporting_success():
    """_save_records logs and swallows. A purge that did not land must not pass
    for one, because a journal deletion is about to run on its word."""
    resona_memory.remember(DEVICE_A, "goal", "of J1", journal_id="J1")
    resona_memory.remember(DEVICE_A, "goal", "of J2", journal_id="J2")

    original = resona_memory._save_records
    try:
        resona_memory._save_records = lambda *a, **kw: None
        with pytest.raises(RuntimeError):
            resona_memory.forget_journal(DEVICE_A, "J1")
    finally:
        resona_memory._save_records = original

    assert len(resona_memory.load_all(DEVICE_A)) == 2


# ---------------------------------------------------------------------------
# owning_device / device_ids / has_other_generations
# ---------------------------------------------------------------------------

def test_owning_device_is_derived_from_the_journal_id():
    assert resona_journal.owning_device(DEVICE_A) == DEVICE_A
    assert resona_journal.owning_device(f"{DEVICE_A}-g2") == DEVICE_A
    assert resona_journal.owning_device(f"{DEVICE_A}-g17") == DEVICE_A


@pytest.mark.parametrize("bad", ["", "...", None])
def test_owning_device_none_for_garbage(bad):
    assert resona_journal.owning_device(bad) is None


def test_device_ids_reads_every_device_that_wrote():
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_journal.append_event(jid, "memory", {"kind": "note", "content": "x"}, device_id=DEVICE_A_NEXT_DAY)
    assert set(resona_journal.device_ids(jid)) == {DEVICE_A, DEVICE_A_NEXT_DAY}


@pytest.mark.parametrize("bad", ["", "no-such-journal", "../escape"])
def test_device_ids_empty_for_unknown(bad):
    assert resona_journal.device_ids(bad) == []


def test_has_other_generations_only_when_a_sibling_exists():
    first = resona_journal.ensure(DEVICE_A)["journal_id"]
    assert resona_journal.has_other_generations(first) is False

    second = resona_journal.new_journal(DEVICE_A)["journal_id"]
    assert resona_journal.has_other_generations(first) is True
    assert resona_journal.has_other_generations(second) is True


def test_has_other_generations_ignores_a_different_device():
    first = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_journal.ensure(DEVICE_B)
    assert resona_journal.has_other_generations(first) is False


# ---------------------------------------------------------------------------
# The route — bug 1
# ---------------------------------------------------------------------------

def test_delete_takes_this_dialogs_memory_with_it(client):
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_memory.remember(DEVICE_A, "goal", "must not survive", journal_id=jid)

    res = client.delete(f"/api/resona/journal/{jid}")

    assert res.status_code == 200
    body = res.get_json()
    assert body["deleted"] is True and body["memories_forgotten"] == 1
    assert not resona_journal.journal_exists(jid)
    assert contents(DEVICE_A) == []


def test_delete_also_reaches_records_a_later_day_made_in_the_same_journal(client):
    """The journal is resumed from localStorage across days while device_id
    rotates daily, so its records sit in two different memory files."""
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_journal.append_event(jid, "memory", {"kind": "note", "content": "x"}, device_id=DEVICE_A_NEXT_DAY)
    resona_memory.remember(DEVICE_A, "goal", "day one", journal_id=jid)
    resona_memory.remember(DEVICE_A_NEXT_DAY, "goal", "day two", journal_id=jid)

    assert client.delete(f"/api/resona/journal/{jid}").get_json()["memories_forgotten"] == 2
    assert contents(DEVICE_A) == [] and contents(DEVICE_A_NEXT_DAY) == []


def test_delete_takes_the_only_conversations_pre_stamping_records(client):
    """Nothing else on this device could own them, so they go with it."""
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_memory.remember(DEVICE_A, "goal", "legacy")
    unstamp(DEVICE_A)

    assert client.delete(f"/api/resona/journal/{jid}").get_json()["memories_forgotten"] == 1
    assert contents(DEVICE_A) == []


def test_delete_clears_the_cut_sentence_notice(client):
    """Otherwise the first turn of the next dialog accounts for a sentence in a
    reply that no longer exists."""
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_question_filter.note_removed(DEVICE_A, 1)

    client.delete(f"/api/resona/journal/{jid}")

    assert resona_question_filter.take_notice(DEVICE_A) == ""


def test_delete_of_an_unknown_journal_404s_and_forgets_nothing(client):
    resona_memory.remember(DEVICE_A, "goal", "untouched", journal_id="whatever")
    assert client.delete("/api/resona/journal/no-such-journal").status_code == 404
    assert contents(DEVICE_A) == ["untouched"]


# ---------------------------------------------------------------------------
# The route — bug 2: what must SURVIVE the delete
# ---------------------------------------------------------------------------

def test_delete_of_a_later_generation_keeps_the_kept_conversations_memory(client):
    """"New conversation" promises the old one is kept and what was noted stays
    known. Both journals live on the same device, hence in one memory file."""
    first = resona_journal.ensure(DEVICE_A)["journal_id"]
    second = resona_journal.new_journal(DEVICE_A)["journal_id"]
    assert second != first
    resona_memory.remember(DEVICE_A, "goal", "noted in the kept one", journal_id=first)
    resona_memory.remember(DEVICE_A, "goal", "noted in the dropped one", journal_id=second)

    assert client.delete(f"/api/resona/journal/{second}").get_json()["memories_forgotten"] == 1

    assert resona_journal.journal_exists(first)
    assert contents(DEVICE_A) == ["noted in the kept one"]


def test_delete_of_a_later_generation_keeps_pre_stamping_records(client):
    """The kept conversation may be exactly where those unattributed records
    were made, so a sibling makes them untouchable."""
    first = resona_journal.ensure(DEVICE_A)["journal_id"]
    second = resona_journal.new_journal(DEVICE_A)["journal_id"]
    resona_memory.remember(DEVICE_A, "goal", "legacy, could be the kept one's")
    unstamp(DEVICE_A)

    assert client.delete(f"/api/resona/journal/{second}").get_json()["memories_forgotten"] == 0
    assert contents(DEVICE_A) == ["legacy, could be the kept one's"]
    assert resona_journal.journal_exists(first)


def test_delete_keeps_records_that_belong_to_no_journal(client):
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_memory.remember(DEVICE_A, "goal", "in the dialog", journal_id=jid)
    resona_memory.remember(DEVICE_A, "note", "no journal at all")

    client.delete(f"/api/resona/journal/{jid}")

    assert contents(DEVICE_A) == ["no journal at all"]


def test_a_foreign_device_in_the_meta_cannot_lose_its_unstamped_records(client):
    """meta['device_ids'] is client-supplied: POST /journal/<jid>/media takes
    device_id straight from the body. It must not become a lever on a
    stranger's pre-stamping records — only the journal's own device, derived
    from the journal_id, gives those up."""
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_journal.append_event(jid, "memory", {"kind": "note", "content": "x"}, device_id=DEVICE_B)

    for device in (DEVICE_A, DEVICE_B):
        resona_memory.remember(device, "note", f"legacy of {device}")
        unstamp(device)

    client.delete(f"/api/resona/journal/{jid}")

    assert contents(DEVICE_A) == []                         # the owner's, fair game
    assert contents(DEVICE_B) == [f"legacy of {DEVICE_B}"]  # the stranger's, untouched


def test_a_bystanding_devices_memory_is_untouched(client):
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_memory.remember(DEVICE_B, "goal", "never wrote to that journal", journal_id="other")

    client.delete(f"/api/resona/journal/{jid}")

    assert contents(DEVICE_B) == ["never wrote to that journal"]


# ---------------------------------------------------------------------------
# Order and honesty of the two halves
# ---------------------------------------------------------------------------

def test_a_failing_memory_purge_leaves_the_journal_alone(client, monkeypatch):
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_memory.remember(DEVICE_A, "goal", "still here", journal_id=jid)

    def boom(*a, **kw):
        raise RuntimeError("disk full")

    monkeypatch.setattr(resona_memory, "forget_journal", boom)

    assert client.delete(f"/api/resona/journal/{jid}").status_code == 500
    assert resona_journal.journal_exists(jid)
    assert contents(DEVICE_A) == ["still here"]


def test_a_journal_that_will_not_unlink_is_a_500_not_a_404(client, monkeypatch):
    """404 would tell the group nothing happened, right after their notes went."""
    jid = resona_journal.ensure(DEVICE_A)["journal_id"]
    resona_memory.remember(DEVICE_A, "goal", "gone", journal_id=jid)
    monkeypatch.setattr(resona_journal, "delete", lambda _jid: False)

    res = client.delete(f"/api/resona/journal/{jid}")

    assert res.status_code == 500
    assert contents(DEVICE_A) == []


# ---------------------------------------------------------------------------
# The other path must stay the other path
# ---------------------------------------------------------------------------

def test_new_conversation_keeps_journal_and_memory():
    """"New conversation" is the Consulting->Workshop bridge. If this ever
    starts forgetting, the two paths have collapsed into one."""
    old = resona_journal.ensure(DEVICE_A)
    resona_memory.remember(DEVICE_A, "goal", "planned in consulting", journal_id=old["journal_id"])

    fresh = resona_journal.new_journal(DEVICE_A)

    assert fresh["journal_id"] != old["journal_id"]
    assert resona_journal.journal_exists(old["journal_id"])
    assert contents(DEVICE_A) == ["planned in consulting"]
