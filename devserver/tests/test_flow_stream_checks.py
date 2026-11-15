"""The Flow's stream runs over the intake and the check at the result.

GET /pipeline/interception with enable_streaming, the run the Flow writes its
perspectives on. The intake takes both texts the visitor sent, under the names
they came under, before Stage 2. A Wikipedia notice goes out only once what it
shows that the model wrote, the terms and the model's reason for each, has
passed the check at the result; so does the text the model wrote, before its
`chunk`. A refusal at either check ends the stream with `blocked` at stage 2,
and nothing of what was refused is on the wire. The visitor's own wording,
which a perspective may hand on, is not checked again. Research checks nothing,
and there the stream takes no slot of the queue.

The gate's own functions stand in here; what they decide is tested in
test_safety_gate.py. No model is called.
"""
import concurrent.futures
import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes import schema_pipeline_routes as spr
from my_app.services.safety_gate import (CHECKPOINT_INTAKE, CHECKPOINT_RESULT,
                                         REASON_CONTENT, REASON_PERSONAL_DATA, Verdict)
from schemas.engine.pipeline_executor import WIKIPEDIA_STATUS
from test_sse_silent_windows import (INTERCEPTION_LEVEL, Opened, StubConfig, StubRunResult,
                                     _interception_data, _wire_interception)
from test_sse_transport_sites import event_names, event_payloads, wait_for

# What the executor writes for the stream while it looks two terms up: the
# terms as asked, then as found, each with the model's reason where it gave one.
ASKED = [{"term": "Glasarchitektur", "lang": "de", "title": "Glasarchitektur", "url": "",
          "success": False, "extract": "", "why": "wie mit Glas gebaut wurde"},
         {"term": "Bauhaus", "lang": "de", "title": "Bauhaus", "url": "",
          "success": False, "extract": "", "why": ""}]
FOUND = [dict(entry, url="https://de.wikipedia.org/wiki/" + entry["term"], success=True,
              extract="Ein Artikel.") for entry in ASKED]
SHOWN = "Glasarchitektur: wie mit Glas gebaut wurde\nBauhaus"
WRITTEN = "Ein Haus aus Glas, gebaut wie am Bauhaus."


class Checks:
    """The intake and the check at the result, standing in: they record what
    they were asked and refuse the field they are told to. `lookup_asked` is
    set whenever a notice is put to the check."""

    def __init__(self):
        self.intake = []
        self.result = []
        self.refuse_intake = None
        self.refuse_result = None
        self.lookup_asked = threading.Event()
        self.hold_first_lookup = None

    def check_intake_texts(self, fields, *, level):
        self.intake.append((dict(fields), level))
        if self.refuse_intake in fields:
            return Verdict(False, CHECKPOINT_INTAKE, level, self.refuse_intake,
                           REASON_PERSONAL_DATA, "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def check_result_text(self, text, *, level, field="text"):
        self.result.append((field, text))
        if field == "wikipedia_lookup":
            first = [f for f, _ in self.result].count(field) == 1
            self.lookup_asked.set()
            if first and self.hold_first_lookup is not None:
                self.hold_first_lookup()
        if field == self.refuse_result:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT,
                           "not for this level")
        return Verdict(True, CHECKPOINT_RESULT, level, field)


class Looking:
    """An interception that looks two terms up while it writes, as the executor
    does: the status `lookup`, then `complete`, then the answer. Each status is
    written once the poll has put the one before to the check, so the notices
    go out in the order they were made in."""

    def __init__(self, checks, wait_for_the_second=True):
        self.checks = checks
        self.wait_for_the_second = wait_for_the_second

    async def execute_pipeline(self, *args, run_id=None, **kwargs):
        asked = self.checks.lookup_asked
        WIKIPEDIA_STATUS[run_id] = {"status": "lookup", "terms": ASKED, "timestamp": time.time()}
        assert asked.wait(10.0), "the poll never put the lookup to the check"
        asked.clear()
        if self.checks.refuse_result != "wikipedia_lookup":
            WIKIPEDIA_STATUS[run_id] = {"status": "complete", "terms": FOUND,
                                        "timestamp": time.time()}
            if self.wait_for_the_second:
                assert asked.wait(10.0), "the poll never put the completed lookup to the check"
        return types.SimpleNamespace(success=True, final_output=WRITTEN, error=None,
                                     metadata={"wikipedia_lookups": 2})


class CountingGate:
    """llm_queue_semaphore, counted: how often it was entered, and how deep."""

    def __init__(self):
        self.entered = self.depth = self.max_depth = 0

    def __enter__(self):
        self.entered += 1
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        return self

    def __exit__(self, *exc):
        self.depth -= 1
        return False


@pytest.fixture
def checks(monkeypatch):
    _wire_interception(monkeypatch, Opened())
    stand_in = Checks()
    monkeypatch.setattr(spr, "check_intake_texts", stand_in.check_intake_texts)
    monkeypatch.setattr(spr, "check_result_text", stand_in.check_result_text)
    return stand_in


def _run(level=INTERCEPTION_LEVEL, **data):
    request = _interception_data()
    request.update(data)
    return "".join(spr.execute_pipeline_streaming(request, level))


def _notices(body):
    return [p for p in event_payloads(body) if "terms" in p]


# ── the intake ──────────────────────────────────────────────────────────────

def test_the_intake_takes_both_texts_by_their_names(checks):
    _run(context_prompt="Erzähle es als Gedicht.")
    assert checks.intake == [({"input_text": "ein satz am feldrand",
                               "context_prompt": "Erzähle es als Gedicht."}, INTERCEPTION_LEVEL)]


def test_a_refused_context_ends_the_stream_and_names_the_context(checks):
    checks.refuse_intake = "context_prompt"
    body = _run(context_prompt="Erzähle es als Gedicht.")
    assert event_names(body) == ["connected", "blocked"]
    assert event_payloads(body)[-1]["safety_block"]["field"] == "context_prompt"
    assert checks.result == []


# ── the result ──────────────────────────────────────────────────────────────

def test_the_text_the_model_wrote_is_checked_before_its_chunk(checks):
    body = _run()
    assert event_names(body) == ["connected", "stage_start", "chunk", "complete"]
    assert checks.result == [("interception", StubRunResult.final_output)]


def test_a_refused_text_ends_the_stream_before_its_chunk(checks):
    checks.refuse_result = "interception"
    body = _run()
    assert event_names(body) == ["connected", "stage_start", "blocked"]
    blocked = event_payloads(body)[-1]
    assert blocked["safety_block"] == {"checkpoint": "result", "field": "interception",
                                       "reason_key": "content", "reason": "not for this level"}
    assert StubRunResult.final_output not in body


def test_the_visitors_own_wording_is_not_checked_again(checks, monkeypatch):
    """A perspective that owes the visitor their prompt hands it on verbatim
    where the model looked nothing up."""
    from schemas.engine import config_loader as cl
    monkeypatch.setattr(cl, "wants_passthrough", lambda *a, **kw: True)
    body = _run()
    assert event_names(body)[-2:] == ["chunk", "complete"]
    assert checks.result == []


# ── the lookups ─────────────────────────────────────────────────────────────

def test_a_lookup_shows_its_terms_and_the_models_reasons():
    assert spr._lookup_text(ASKED) == SHOWN
    assert spr._lookup_text([{"term": "", "why": ""}, "not a lookup", None]) == ""
    assert spr._lookup_text(None) == ""


def test_each_lookup_notice_goes_out_after_its_check(checks, monkeypatch):
    monkeypatch.setattr(spr, "pipeline_executor", Looking(checks))
    body = _run()
    assert event_names(body) == ["connected", "stage_start", "wikipedia_lookup",
                                 "wikipedia_lookup", "chunk", "complete"]
    assert [n["status"] for n in _notices(body)] == ["start", "complete"]
    assert _notices(body)[-1]["terms"] == FOUND
    assert checks.result == [("wikipedia_lookup", SHOWN), ("wikipedia_lookup", SHOWN),
                             ("interception", WRITTEN)]


def test_a_refused_lookup_ends_the_stream_before_its_notice(checks, monkeypatch):
    checks.refuse_result = "wikipedia_lookup"
    monkeypatch.setattr(spr, "pipeline_executor", Looking(checks))
    body = _run()
    assert event_names(body) == ["connected", "stage_start", "blocked"]
    blocked = event_payloads(body)[-1]
    assert blocked["safety_block"]["checkpoint"] == "result"
    assert blocked["safety_block"]["field"] == "wikipedia_lookup"
    assert "Glasarchitektur" not in body
    assert WRITTEN not in body


def test_a_lookup_completed_while_the_one_before_was_checked_still_goes_out(
        checks, monkeypatch):
    """The check can take longer than the rest of the run. Here the run ends
    while the first notice is being checked, and the second still goes out,
    after its own check."""
    made = []

    class Recording(concurrent.futures.ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            future = super().submit(*args, **kwargs)
            made.append(future)
            return future

    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", Recording)
    checks.hold_first_lookup = lambda: wait_for(lambda: bool(made) and made[0].done())
    monkeypatch.setattr(spr, "pipeline_executor", Looking(checks, wait_for_the_second=False))
    body = _run()
    assert [n["status"] for n in _notices(body)] == ["start", "complete"]
    assert [f for f, _ in checks.result] == ["wikipedia_lookup", "wikipedia_lookup",
                                             "interception"]


# ── the queue, research, a reader who left ──────────────────────────────────

def test_each_check_holds_one_slot_and_never_two(checks, monkeypatch):
    gate = CountingGate()
    monkeypatch.setattr(spr, "llm_queue_semaphore", gate)
    monkeypatch.setattr(spr, "pipeline_executor", Looking(checks))
    _run()
    # The intake, the two notices, the text.
    assert gate.entered == 4
    assert gate.max_depth == 1
    assert gate.depth == 0


def test_research_checks_nothing_and_takes_no_slot(checks, monkeypatch):
    gate = CountingGate()
    monkeypatch.setattr(spr, "llm_queue_semaphore", gate)
    body = _run(level="research")
    assert event_names(body) == ["connected", "stage_start", "chunk", "complete"]
    assert checks.intake == [] and checks.result == []
    assert gate.entered == 0


def _transport_for_a_reader_who(gone):
    """The shared transport, as far as the work sees it: the source is made
    with this leaving signal and its items are handed on."""
    def events_with_heartbeat(events, *, label, frame, **_writers):
        for item in events(client_gone=gone):
            yield frame(item)
    return events_with_heartbeat


def test_a_reader_who_left_before_the_intake_costs_no_check_and_no_slot(
        checks, monkeypatch):
    gate = CountingGate()
    gone = threading.Event()
    gone.set()
    monkeypatch.setattr(spr, "llm_queue_semaphore", gate)
    monkeypatch.setattr(spr, "events_with_heartbeat", _transport_for_a_reader_who(gone))
    assert event_names(_run()) == ["connected"]
    assert checks.intake == []
    assert gate.entered == 0


def test_a_reader_who_left_while_waiting_for_a_slot_hands_it_back_unused(
        checks, monkeypatch):
    gone = threading.Event()

    class LeftWhileWaiting(CountingGate):
        def __enter__(self):
            gone.set()
            return super().__enter__()

    gate = LeftWhileWaiting()
    monkeypatch.setattr(spr, "llm_queue_semaphore", gate)
    monkeypatch.setattr(spr, "events_with_heartbeat", _transport_for_a_reader_who(gone))
    assert event_names(_run()) == ["connected"]
    assert checks.intake == []
    assert gate.entered == 1 and gate.depth == 0


# ── a saved perspective ─────────────────────────────────────────────────────

KEPT = "Sieh es von der Seite."
KEPT_TASK = "Schreibe kurz."


def _a_saved_perspective(monkeypatch):
    kept = StubConfig(name="custom:7", context=KEPT)
    kept.task_instruction = KEPT_TASK
    monkeypatch.setattr(spr, "_resolve_interception_config", lambda name: kept)


def test_the_text_of_a_saved_perspective_goes_through_the_intake(checks, monkeypatch):
    _a_saved_perspective(monkeypatch)
    _run(schema="custom:7")
    assert checks.intake == [({"input_text": "ein satz am feldrand", "context_prompt": "",
                               "context_text": KEPT, "task_instruction": KEPT_TASK},
                              INTERCEPTION_LEVEL)]


def test_a_refused_saved_perspective_ends_the_stream_and_names_its_field(checks, monkeypatch):
    _a_saved_perspective(monkeypatch)
    checks.refuse_intake = "task_instruction"
    body = _run(schema="custom:7")
    assert event_names(body) == ["connected", "blocked"]
    assert event_payloads(body)[-1]["safety_block"]["field"] == "task_instruction"
    assert checks.result == []
