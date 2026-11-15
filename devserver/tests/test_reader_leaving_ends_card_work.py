"""A run whose reader has left ends its prompts at ComfyUI and answers nothing.

On 2026-11-08 a Prompt Interception on a local model (`local/qwen3.8:27b`, the
config "the_unspoken", /pipeline/stage2) held the card's one slot from 18:52:24;
the page went at 19:00:58 and the prompt ran on for nobody until it was
interrupted by hand at 19:10:26. The run did not take the transport's leaving
signal, and its model call has no other way to be ended.

Held in place here:

- `generation_abort.ended_when_its_reader_leaves`: when the signal is set, the
  run is marked and every prompt noted under its run id is cancelled at
  ComfyUI, and asked for again every round while the client still holds it:
  ComfyUI answers a cancel with 200 whether or not it found the prompt. A
  signal set before the work begins marks the run at once; one set after the
  work has ended marks nothing. A run whose reader stays ends nothing; without
  a signal the run gets its id and nothing else. An adopted run id (the
  interception route's) keeps its mark, and the watcher takes a stop's mark of
  it as it takes the leaving, also without a stream. A watcher that cannot
  start leaves nothing set.
- What the mark does to a prompt submitted later: the ComfyUI client refuses
  it before it takes a place in line (`_with_gpu_lease`).
- `cancel_job` says whether ComfyUI took the cancel; `try_cancel_job` names
  the cause.
- The places the Prompt Interception and the adaption run behind a stream take
  the signal, run their model work inside the helper, and answer a run that
  ended as cancelled before any check: /pipeline/stage2, /pipeline/interception,
  /pipeline/optimize (both ways of writing the adaption), and the Flow's
  stream; a run that ended before the work began starts no model call. The
  translation of an edited context runs inside the helper too. A run that
  ended during the interception asks no adaption.
- /pipeline/interception: a stop pressed on the route's device reaches the
  prompt of the context translation and of Stage 2 at ComfyUI; a reader who
  leaves after Stage 2 gets no Stage 3 and no Stage 4, and one who leaves
  while Stage 4 renders ends its prompt; a check in Stage 3 that its ended run
  cut off is recorded as no block.

Not covered by these tests: the hop of the model call onto a pool thread with
a copied context (`llm_client._run`); the fakes here stand at the engine.

Run: pytest devserver/tests/test_reader_leaving_ends_card_work.py -q
"""
import ast
import asyncio
import inspect
import sys
import textwrap
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services import comfyui_ws_client as WS
from my_app.services import generation_abort as GA
from my_app.services import streaming_response as SR


class FakeComfyUI:
    """Stands for the ComfyUI client: records every cancel asked and every
    cancel taken, and can be told to refuse the first few, which the real
    client answers with False."""

    def __init__(self, refuse_first=0):
        self.asked = []
        self.cancelled = []
        self.refuse_first = refuse_first
        self.reached = threading.Event()
        self._lock = threading.Lock()   # a stop and the watcher ask from two threads

    async def cancel_job(self, prompt_id):
        with self._lock:
            self.asked.append(prompt_id)
            if self.refuse_first > 0:
                self.refuse_first -= 1
                return False
            self.cancelled.append(prompt_id)
        self.reached.set()
        return True

    async def try_cancel_job(self, prompt_id):
        return None if await self.cancel_job(prompt_id) else "refused"


@pytest.fixture()
def comfyui(monkeypatch):
    fake = FakeComfyUI()
    monkeypatch.setattr(WS, "get_comfyui_ws_client", lambda: fake)
    return fake


def _wait_for(predicate, seconds=10.0):
    end = time.time() + seconds
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def _in_thread(fn, *args, **kwargs):
    """Runs fn on a thread of its own, as the transport runs a run; the
    answer lands in the returned dict under 'answer'."""
    box = {}

    def run():
        box["answer"] = fn(*args, **kwargs)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    box["thread"] = thread
    return box


# ---------------------------------------------------------------------------
# 1. The helper
# ---------------------------------------------------------------------------

def test_a_reader_that_leaves_ends_the_runs_prompts(comfyui):
    left = threading.Event()
    with GA.ended_when_its_reader_leaves(left, kind="t", label="T") as run:
        assert GA.CURRENT_RUN_ID.get() == run.run_id
        assert GA.note_prompt(run.run_id, "p-1") is False
        assert not run.ended
        left.set()
        assert comfyui.reached.wait(5.0), "the prompt was not cancelled"
        assert GA.current_run_aborted(), "the run was not marked"
        assert run.ended
        GA.forget_prompt(run.run_id, "p-1")
    assert comfyui.cancelled == ["p-1"]
    assert run.ended, "the run forgot that it ended"
    assert not GA.is_aborted(run.run_id), "an own run id keeps no mark"


def test_a_prompt_named_after_the_leaving_is_told_so(comfyui):
    """The client interrupts a prompt itself when the run is already marked
    as it names it (comfyui_ws_client._submit_then_track)."""
    left = threading.Event()
    with GA.ended_when_its_reader_leaves(left, kind="t", label="T") as run:
        left.set()
        assert _wait_for(GA.current_run_aborted, 5.0)
        assert GA.note_prompt(run.run_id, "p-late") is True
        GA.forget_prompt(run.run_id, "p-late")


def test_a_prompt_submitted_after_the_leaving_never_queues(comfyui, monkeypatch):
    """The lease wrapper refuses a marked run before the gate and before
    ComfyUI hear of it."""
    leased, ran = [], []

    class _Lease:
        async def __aenter__(self):
            leased.append(1)

        async def __aexit__(self, *exc):
            return False

    from my_app.services import gpu_lease_client
    monkeypatch.setattr(gpu_lease_client, "gpu_lease", lambda *a, **k: _Lease())

    @WS._with_gpu_lease
    async def submit(self, workflow):
        ran.append(1)

    left = threading.Event()
    with GA.ended_when_its_reader_leaves(left, kind="t", label="T"):
        left.set()
        assert _wait_for(GA.current_run_aborted, 5.0)
        with pytest.raises(RuntimeError, match="cancelled before queueing"):
            asyncio.run(submit(None, {}))
    assert leased == [] and ran == []


def test_a_reader_gone_before_the_work_begins_marks_it_at_once(comfyui):
    gone = threading.Event()
    gone.set()
    with GA.ended_when_its_reader_leaves(gone, kind="t", label="T") as run:
        assert run.ended, "the work could start before the mark"
        assert GA.current_run_aborted()


def test_a_reader_that_stays_ends_nothing(comfyui):
    stays = threading.Event()
    with GA.ended_when_its_reader_leaves(stays, kind="t", label="T") as run:
        GA.note_prompt(run.run_id, "p-2")
        time.sleep(1.2)
        assert not GA.current_run_aborted()
        GA.forget_prompt(run.run_id, "p-2")
    time.sleep(0.8)
    assert comfyui.asked == []
    assert not run.ended
    assert not GA.is_aborted(run.run_id)


def test_a_leaving_after_the_work_ended_marks_nothing(comfyui):
    late = threading.Event()
    with GA.ended_when_its_reader_leaves(late, kind="t", label="T") as run:
        pass
    late.set()
    time.sleep(1.2)
    assert not run.ended
    assert not GA.is_aborted(run.run_id)


def test_without_a_signal_the_run_has_an_id_and_nothing_else(comfyui):
    before = {t.name for t in threading.enumerate()}
    outer = GA.CURRENT_RUN_ID.set("outer")
    try:
        with GA.ended_when_its_reader_leaves(None, kind="t", label="T") as run:
            assert run.run_id.startswith("t_")
            assert GA.CURRENT_RUN_ID.get() == run.run_id
            assert not [t for t in threading.enumerate()
                        if t.name == "t-ended" and t.name not in before]
        assert GA.CURRENT_RUN_ID.get() == "outer"
    finally:
        GA.CURRENT_RUN_ID.reset(outer)


def test_a_cancel_comfyui_did_not_take_is_asked_again(monkeypatch):
    fake = FakeComfyUI(refuse_first=1)
    monkeypatch.setattr(WS, "get_comfyui_ws_client", lambda: fake)
    left = threading.Event()
    with GA.ended_when_its_reader_leaves(left, kind="t", label="T") as run:
        GA.note_prompt(run.run_id, "p-3")
        left.set()
        assert fake.reached.wait(8.0), "the cancel was not asked again"
        GA.forget_prompt(run.run_id, "p-3")
    assert fake.asked[:2] == ["p-3", "p-3"]
    assert fake.cancelled[:1] == ["p-3"]


def test_a_prompt_still_held_is_asked_for_again(comfyui):
    """A 200 from ComfyUI does not say the prompt stopped: a prompt that went
    from the queue to the card between the two requests clears the interrupt
    as it starts. The cancel goes out again every round while the client
    still holds the prompt, and stops once the client has forgotten it."""
    left = threading.Event()
    with GA.ended_when_its_reader_leaves(left, kind="t", label="T") as run:
        GA.note_prompt(run.run_id, "p-4")
        left.set()
        assert _wait_for(lambda: len(comfyui.asked) >= 2, 8.0), "the cancel was not sent again"
        GA.forget_prompt(run.run_id, "p-4")
        time.sleep(0.2)
        asked = len(comfyui.asked)
        time.sleep(2.6)   # one more round of the watcher, the prompt forgotten
        assert len(comfyui.asked) == asked, "a forgotten prompt was asked for"
    assert set(comfyui.asked) == {"p-4"}


def test_the_client_says_when_comfyui_did_not_take_the_cancel():
    client = WS.ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    assert asyncio.run(client.cancel_job("p-unreachable")) is False
    assert "/queue" in asyncio.run(client.try_cancel_job("p-unreachable"))


def test_a_stop_ends_an_adopted_run_without_a_stream(monkeypatch):
    """One JSON body, no stream: the stop's own cancel is one attempt, and the
    watcher takes the stop's mark and asks again until ComfyUI takes it."""
    fake = FakeComfyUI(refuse_first=1)
    monkeypatch.setattr(WS, "get_comfyui_ws_client", lambda: fake)
    try:
        with GA.ended_when_its_reader_leaves(None, kind="t", label="T",
                                             run_id="run-json-stop") as run:
            GA.note_prompt("run-json-stop", "p-6")
            assert not run.ended
            GA.mark("run-json-stop")          # what the stop does to the run
            assert fake.reached.wait(8.0), "the stopped run's prompt was not cancelled"
            GA.forget_prompt("run-json-stop", "p-6")
            assert run.ended and not run.left
        assert GA.is_aborted("run-json-stop"), "the owner's mark was taken away"
    finally:
        GA.unmark("run-json-stop")


def test_a_watcher_that_cannot_start_leaves_nothing_set(monkeypatch):
    def refuse(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(GA.threading.Thread, "start", refuse)
    gone = threading.Event()
    gone.set()
    outer = GA.CURRENT_RUN_ID.set("outer")
    try:
        with pytest.raises(RuntimeError, match="can't start"):
            with GA.ended_when_its_reader_leaves(gone, kind="nostart", label="T"):
                pytest.fail("the work ran without its watcher")
        assert GA.CURRENT_RUN_ID.get() == "outer"
        assert not [r for r in GA._aborted if r.startswith("nostart_")]
    finally:
        GA.CURRENT_RUN_ID.reset(outer)


def test_an_adopted_run_that_was_stopped_has_ended(comfyui):
    """The interception route's run id: a stop marked it, so the work inside
    has ended before it begins, and the mark stands afterwards."""
    GA.mark("run-stopped")
    try:
        with GA.ended_when_its_reader_leaves(threading.Event(), kind="t", label="T",
                                             run_id="run-stopped") as run:
            assert run.run_id == "run-stopped"
            assert GA.CURRENT_RUN_ID.get() == "run-stopped"
            assert run.ended
        assert GA.is_aborted("run-stopped"), "the owner's mark was taken away"
    finally:
        GA.unmark("run-stopped")


def test_an_adopted_run_whose_reader_left_keeps_its_mark(comfyui):
    left = threading.Event()
    try:
        with GA.ended_when_its_reader_leaves(left, kind="t", label="T",
                                             run_id="run-adopted") as run:
            GA.note_prompt("run-adopted", "p-5")
            left.set()
            assert comfyui.reached.wait(5.0)
            GA.forget_prompt("run-adopted", "p-5")
        assert run.ended
        assert GA.is_aborted("run-adopted"), "Stage 4 would not see the end"
        assert comfyui.cancelled == ["p-5"]
    finally:
        GA.unmark("run-adopted")


def test_the_watcher_ends_with_the_work(comfyui):
    left = threading.Event()
    with GA.ended_when_its_reader_leaves(left, kind="watch", label="T"):
        assert [t for t in threading.enumerate() if t.name == "watch-ended"]
    assert _wait_for(lambda: not [t for t in threading.enumerate()
                                  if t.name == "watch-ended"], 3.0)


# ---------------------------------------------------------------------------
# 2. Who takes the signal, and where the work runs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("run", ["_run_stage2", "_run_interception_pipeline",
                                 "_run_optimize_prompt"])
def test_the_runs_take_the_leaving_signal(run):
    assert SR._asks_for_the_leaving_signal(getattr(R, run))


def _tree(function):
    return ast.parse(textwrap.dedent(inspect.getsource(getattr(R, function))))


def _name(func):
    return getattr(func, "attr", None) or getattr(func, "id", None)


def _calls_in(nodes):
    return {_name(c.func) for n in nodes for c in ast.walk(n) if isinstance(c, ast.Call)}


@pytest.mark.parametrize("function, signal, work", [
    ("_run_stage2", "client_gone", "execute_stage2_with_optimization"),
    ("_run_interception_pipeline", "client_gone", "execute_stage2_with_optimization"),
    ("_run_adaption_chunk", "client_gone", "process_request"),
    ("_run_optimize_prompt", "client_gone", "execute_optimization"),
    ("execute_pipeline_streaming", "stream_ended", "execute_pipeline"),
])
def test_the_model_work_runs_inside_the_helper(function, signal, work):
    found = []
    for node in ast.walk(_tree(function)):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            call = item.context_expr
            if (isinstance(call, ast.Call) and _name(call.func) == "ended_when_its_reader_leaves"
                    and work in _calls_in(node.body)):
                found.append(call)
    assert len(found) == 1, f"{work} does not run inside the helper in {function}"
    first = found[0].args[0]
    assert isinstance(first, ast.Name) and first.id == signal


def _helper_withs(function, work):
    """The `with` statements of the helper in `function` whose body calls `work`."""
    return [node for node in ast.walk(_tree(function))
            if isinstance(node, ast.With)
            and any(isinstance(i.context_expr, ast.Call)
                    and _name(i.context_expr.func) == "ended_when_its_reader_leaves"
                    for i in node.items)
            and work in _calls_in(node.body)]


@pytest.mark.parametrize("function, work", [
    ("_run_stage2", "execute_stage2_with_optimization"),
    ("_run_stage2", "_translate_context"),
    ("_run_interception_pipeline", "execute_stage2_with_optimization"),
    ("_run_interception_pipeline", "_translate_context"),
    ("_run_adaption_chunk", "process_request"),
    ("_run_optimize_prompt", "execute_optimization"),
    ("execute_pipeline_streaming", "execute_pipeline"),
])
def test_the_work_starts_only_for_a_run_that_has_not_ended(function, work):
    """Inside the helper, the call stands under `if not <run>.ended`, or after
    an `if <run>.ended: return`: a run whose stream ended before the work
    began starts no model call."""
    withs = _helper_withs(function, work)
    assert len(withs) == 1, f"{work} does not run inside the helper in {function}"
    call = min(c.lineno for c in ast.walk(withs[0])
               if isinstance(c, ast.Call) and _name(c.func) == work)
    guarded = [node for node in ast.walk(withs[0])
               if isinstance(node, ast.If) and (
                   (isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
                    and isinstance(node.test.operand, ast.Attribute)
                    and node.test.operand.attr == "ended"
                    and work in _calls_in(node.body))
                   or (isinstance(node.test, ast.Attribute) and node.test.attr == "ended"
                       and isinstance(node.body[0], ast.Return) and node.lineno < call))]
    assert guarded, f"{work} starts in {function} for a run that has ended"


@pytest.mark.parametrize("function, work", [
    ("_run_stage2", "execute_stage2_with_optimization"),
    ("_run_stage2", "_translate_context"),
    ("_run_interception_pipeline", "execute_stage2_with_optimization"),
    ("_run_interception_pipeline", "_translate_context"),
    ("_run_adaption_chunk", "process_request"),
    ("_run_optimize_prompt", "execute_optimization"),
])
def test_a_run_that_ended_answers_before_anything_else(function, work):
    """Right after the work's `with`: an `if` that reads `ended` and returns,
    and it comes before the first check that follows the work."""
    tree = _tree(function)
    end = _helper_withs(function, work)[0].end_lineno
    answers = [node.lineno for node in ast.walk(tree)
               if isinstance(node, ast.If) and node.lineno > end
               and any(isinstance(a, ast.Attribute) and a.attr == "ended"
                       for a in ast.walk(node.test))
               and any(isinstance(b, ast.Return) for b in node.body)]
    assert answers, f"{function} goes on after its run ended"
    checks = [c.lineno for c in ast.walk(tree)
              if isinstance(c, ast.Call) and c.lineno > end
              and (_name(c.func) or "").startswith("check_")]
    assert not checks or min(answers) < min(checks), \
        f"{function} checks a result before it asks whether its run ended"


def test_the_interception_route_adopts_its_run_id():
    """For the context translation, for Stage 2, and for Stage 3 and Stage 4."""
    calls = [c for c in ast.walk(_tree("_run_interception_pipeline"))
             if isinstance(c, ast.Call) and _name(c.func) == "ended_when_its_reader_leaves"]
    assert [k.value.id for c in calls for k in c.keywords if k.arg == "run_id"] \
        == ["run_id"] * 3


def test_the_flow_stream_ends_its_interception_however_it_ends():
    source = inspect.getsource(R.execute_pipeline_streaming)
    tail = source[source.rindex("    finally:"):]
    assert "stream_ended.set()" in tail


def test_a_run_that_ended_during_its_interception_asks_no_adaption(monkeypatch):
    asked = []

    async def interception(**kwargs):
        return SimpleNamespace(success=True, final_output="written", steps=[],
                               metadata={}, error=None, execution_time=0)

    async def adaption(**kwargs):
        asked.append(kwargs)
        return "adapted"

    monkeypatch.setattr(R, "execute_stage2_interception", interception)
    monkeypatch.setattr(R, "execute_optimization", adaption)
    monkeypatch.setattr(R, "_load_optimization_instruction", lambda name: "rules")
    GA.mark("run-ended-early")
    token = GA.CURRENT_RUN_ID.set("run-ended-early")
    try:
        result = asyncio.run(R.execute_stage2_with_optimization(
            schema_name="the_unspoken", input_text="ein Haus", config=None,
            safety_level="adult", output_config="sd35_large"))
    finally:
        GA.CURRENT_RUN_ID.reset(token)
        GA.unmark("run-ended-early")
    assert asked == []
    assert result.metadata.get("optimization_applied") is False


# ---------------------------------------------------------------------------
# 3. /pipeline/stage2
# ---------------------------------------------------------------------------

def _a_local_model_at_the_card(seen, entered, interrupted):
    """Stands for the interception on a local model: one prompt at ComfyUI,
    noted under the run's id as the client notes it, writing until the cancel
    reaches it."""
    async def run(**kwargs):
        run_id = GA.CURRENT_RUN_ID.get()
        seen["run_id"] = run_id
        seen["noted"] = None
        GA.note_prompt(run_id, "p-stage2")
        seen["noted"] = GA.prompts_of(run_id)
        entered.set()
        try:
            if not interrupted.wait(15.0):
                seen["ran_out"] = True
        finally:
            GA.forget_prompt(run_id, "p-stage2")
        return SimpleNamespace(success=False, error="interrupted", steps=[],
                               metadata={}, final_output="")
    return run


def _a_cloud_model(seen, entered):
    """Stands for the interception on a cloud model: no prompt at ComfyUI,
    and a text that comes back whole after the reader has left."""
    async def run(**kwargs):
        run_id = GA.CURRENT_RUN_ID.get()
        seen["run_id"] = run_id
        entered.set()
        assert _wait_for(lambda: GA.is_aborted(run_id), 10.0)
        return SimpleNamespace(success=True, error=None, steps=[], metadata={},
                               final_output="a whole text", execution_time=0)
    return run


@pytest.fixture()
def stage2_checks(monkeypatch):
    checked = []
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "adult")
    monkeypatch.setattr(R, "check_intake_texts",
                        lambda *a, **k: SimpleNamespace(passed=True))
    monkeypatch.setattr(R, "check_result_text",
                        lambda *a, **k: checked.append(a) or SimpleNamespace(passed=True))
    return checked


def test_stage2_ends_its_prompt_when_the_page_goes(comfyui, stage2_checks, monkeypatch):
    """Through the stream transport: the page closes the stream."""
    seen, entered = {}, threading.Event()
    monkeypatch.setattr(R, "execute_stage2_with_optimization",
                        _a_local_model_at_the_card(seen, entered, comfyui.reached))

    app = Flask(__name__)
    app.register_blueprint(R.schema_bp)
    with app.test_request_context("/api/schema/pipeline/stage2", method="POST",
                                  json={"schema": "the_unspoken", "input_text": "ein Haus",
                                        "enable_streaming": True}):
        response = R.execute_stage2()
        stream = iter(response.response)
        next(stream)
        assert entered.wait(10.0), "the run never reached the model"
        response.response.close()

    assert comfyui.reached.wait(10.0), "the prompt ran on after the page went"
    assert comfyui.cancelled == ["p-stage2"]
    assert seen["run_id"].startswith("stage2_")
    assert "ran_out" not in seen


@pytest.mark.parametrize("model", ["local", "cloud"])
def test_stage2_answers_nothing_once_its_reader_left(model, comfyui, stage2_checks,
                                                     monkeypatch):
    seen, entered, gone = {}, threading.Event(), threading.Event()
    fake = (_a_local_model_at_the_card(seen, entered, comfyui.reached) if model == "local"
            else _a_cloud_model(seen, entered))
    monkeypatch.setattr(R, "execute_stage2_with_optimization", fake)

    box = _in_thread(R._run_stage2, {"schema": "the_unspoken", "input_text": "ein Haus"},
                     "adult", client_gone=gone)
    assert entered.wait(10.0), "the run never reached the model"
    gone.set()
    box["thread"].join(20.0)

    payload, status = box["answer"]
    assert payload["status"] == "cancelled" and payload["success"] is False
    assert stage2_checks == [], "a text was checked for a reader who had left"
    if model == "local":
        assert comfyui.cancelled == ["p-stage2"]
    else:
        assert comfyui.asked == []


def _a_local_translation_at_the_card(seen, entered, interrupted):
    """Stands for the translation of an edited context on a local model: one
    prompt at ComfyUI, noted under the run's id, until the cancel reaches it;
    then the original comes back, as `_translate_context` answers a failure."""
    def run(context_prompt, context_language, tag, on_translated=None):
        run_id = GA.CURRENT_RUN_ID.get()
        seen["translation_run_id"] = run_id
        GA.note_prompt(run_id, "p-context")
        entered.set()
        try:
            if not interrupted.wait(15.0):
                seen["ran_out"] = True
        finally:
            GA.forget_prompt(run_id, "p-context")
        return context_prompt
    return run


def test_stage2_ends_the_context_translation_when_its_reader_leaves(
        comfyui, stage2_checks, monkeypatch):
    seen, entered, gone, stage2 = {}, threading.Event(), threading.Event(), []
    monkeypatch.setattr(R, "_translate_context",
                        _a_local_translation_at_the_card(seen, entered, comfyui.reached))

    async def interception(**kwargs):
        stage2.append(kwargs)

    monkeypatch.setattr(R, "execute_stage2_with_optimization", interception)
    box = _in_thread(R._run_stage2,
                     {"schema": "the_unspoken", "input_text": "ein Haus",
                      "context_prompt": "Schreibe über das Unausgesprochene.",
                      "context_language": "de"},
                     "adult", client_gone=gone)
    assert entered.wait(10.0), "the run never reached the translation"
    gone.set()
    box["thread"].join(20.0)
    payload, status = box["answer"]
    assert payload["status"] == "cancelled"
    assert seen["translation_run_id"].startswith("stage2_")
    assert comfyui.cancelled[:1] == ["p-context"] and "ran_out" not in seen
    assert stage2 == [], "Stage 2 ran after its reader left"


def test_stage2_as_one_json_body_ends_nothing(comfyui, stage2_checks, monkeypatch):
    """No stream, no leaving to see: the run gets its id and runs to its end."""
    seen, entered, done = {}, threading.Event(), threading.Event()
    done.set()
    monkeypatch.setattr(R, "execute_stage2_with_optimization",
                        _a_local_model_at_the_card(seen, entered, done))

    app = Flask(__name__)
    app.register_blueprint(R.schema_bp)
    with app.test_request_context("/api/schema/pipeline/stage2", method="POST",
                                  json={"schema": "the_unspoken", "input_text": "ein Haus"}):
        R.execute_stage2()
    assert seen["run_id"].startswith("stage2_")
    assert comfyui.asked == []


# ---------------------------------------------------------------------------
# 4. /pipeline/interception
# ---------------------------------------------------------------------------

class _Recorder:
    def __init__(self):
        self.metadata = {}

    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture()
def interception_run(monkeypatch, stage2_checks):
    """The route's checks are faked; what it checks after Stage 2 is recorded."""
    R.init_schema_engine()
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    return stage2_checks


# The answer of a run that ended during Stage 2: nothing of Stage 3 or 4 in it.
_ENDED_AT_STAGE2 = {"status", "schema", "run_id"}


def test_the_interception_route_ends_at_stage2_when_its_reader_leaves(
        comfyui, interception_run, monkeypatch):
    seen, entered, gone = {}, threading.Event(), threading.Event()
    monkeypatch.setattr(R, "generate_run_id", lambda: "run_4stage_left")
    monkeypatch.setattr(R, "execute_stage2_with_optimization",
                        _a_local_model_at_the_card(seen, entered, comfyui.reached))
    try:
        box = _in_thread(R._run_interception_pipeline,
                         {"schema": "the_unspoken", "input_text": "ein Haus",
                          "device_id": "test-device"}, "adult", client_gone=gone)
        assert entered.wait(10.0), "the run never reached the model"
        gone.set()
        box["thread"].join(20.0)
        payload, status = box["answer"]
    finally:
        GA.unmark("run_4stage_left")
    assert (payload["status"], payload["run_id"], status) == ("cancelled", "run_4stage_left", 200)
    assert set(payload) == _ENDED_AT_STAGE2
    assert seen["run_id"] == "run_4stage_left"
    assert comfyui.cancelled == ["p-stage2"]
    assert interception_run == [], "a text was checked for a reader who had left"


def test_a_stop_reaches_stage2_of_the_interception_route(interception_run, monkeypatch):
    """A run that names an output config is announced under its device at
    once. The stop route finds it there and marks its id; Stage 2 runs under
    that id, so the stop's cancel reaches its prompt at ComfyUI. ComfyUI
    refuses the first two cancels here, the stop's own and the watcher's
    first: the watcher asks again until it is taken."""
    fake = FakeComfyUI(refuse_first=2)
    monkeypatch.setattr(WS, "get_comfyui_ws_client", lambda: fake)
    seen, entered = {}, threading.Event()
    monkeypatch.setattr(R, "generate_run_id", lambda: "run_4stage_stop")
    monkeypatch.setattr(R, "execute_stage2_with_optimization",
                        _a_local_model_at_the_card(seen, entered, fake.reached))
    app = Flask(__name__)
    app.register_blueprint(R.schema_bp)
    try:
        box = _in_thread(R._run_interception_pipeline,
                         {"schema": "the_unspoken", "input_text": "ein Haus",
                          "device_id": "test-device-stop", "output_config": "sd35_large"},
                         "adult")
        assert entered.wait(10.0), "the run never reached the model"
        stop = app.test_client().post("/api/schema/pipeline/generation-cancel",
                                      json={"device_id": "test-device-stop"})
        assert stop.get_json() == {"cancelled": True}
        box["thread"].join(20.0)
        payload, status = box["answer"]
    finally:
        GA.unmark("run_4stage_stop")
    assert seen["run_id"] == "run_4stage_stop"
    assert fake.asked[:3] == ["p-stage2"] * 3 and fake.cancelled[:1] == ["p-stage2"]
    assert "ran_out" not in seen
    assert payload["status"] == "cancelled" and set(payload) == _ENDED_AT_STAGE2
    assert interception_run == []


def _a_finished_interception(seen):
    async def run(**kwargs):
        seen["stage2"] = GA.CURRENT_RUN_ID.get()
        return SimpleNamespace(success=True, error=None, steps=[], metadata={},
                               final_output="Ein Haus steht am Rand eines Feldes.",
                               execution_time=0)
    return run


class _RecorderOf(_Recorder):
    """Records the block entries; sets the leaving signal, if given, when the
    interception is stored, which is after Stage 2 and before Stage 3."""

    def __init__(self, gone=None):
        super().__init__()
        self.gone = gone
        self.errors = []

    def save_entity(self, kind, *args, **kwargs):
        if kind == "interception" and self.gone is not None:
            self.gone.set()

    def save_error(self, **kwargs):
        self.errors.append(kwargs)


def test_a_reader_who_left_after_stage2_gets_no_stage3_and_no_stage4(
        comfyui, interception_run, monkeypatch):
    seen, gone, stage3, stage4 = {}, threading.Event(), [], []
    recorder = _RecorderOf(gone)
    monkeypatch.setattr(R, "get_recorder", lambda **kw: recorder)
    monkeypatch.setattr(R, "generate_run_id", lambda: "run_4stage_after2")
    monkeypatch.setattr(R, "execute_stage2_with_optimization", _a_finished_interception(seen))
    monkeypatch.setattr(R, "check_before_model", lambda *a, **k: stage3.append(a))
    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline",
                        lambda *a, **k: stage4.append(a))
    try:
        payload, status = R._run_interception_pipeline(
            {"schema": "the_unspoken", "input_text": "ein Haus",
             "device_id": "test-device-after2", "output_config": "sd35_large"},
            "adult", client_gone=gone)
    finally:
        GA.unmark("run_4stage_after2")
    assert seen["stage2"] == "run_4stage_after2"
    assert (payload["status"], status) == ("cancelled", 200)
    assert payload["media_output"]["status"] == "cancelled"
    assert stage3 == [] and stage4 == []
    assert recorder.errors == []


def test_the_interception_route_ends_its_context_translation_on_a_stop(
        comfyui, interception_run, monkeypatch):
    """The translation of an edited context runs under the route's run id
    too: a stop pressed on the device reaches its prompt at ComfyUI, and
    Stage 2 does not run."""
    seen, entered, stage2 = {}, threading.Event(), []
    monkeypatch.setattr(R, "generate_run_id", lambda: "run_4stage_ctx")
    monkeypatch.setattr(R, "_translate_context",
                        _a_local_translation_at_the_card(seen, entered, comfyui.reached))

    async def interception(**kwargs):
        stage2.append(kwargs)

    monkeypatch.setattr(R, "execute_stage2_with_optimization", interception)
    app = Flask(__name__)
    app.register_blueprint(R.schema_bp)
    try:
        box = _in_thread(R._run_interception_pipeline,
                         {"schema": "the_unspoken", "input_text": "ein Haus",
                          "context_prompt": "Schreibe über das Unausgesprochene.",
                          "context_language": "de",
                          "device_id": "test-device-ctx", "output_config": "sd35_large"},
                         "adult")
        assert entered.wait(10.0), "the run never reached the translation"
        stop = app.test_client().post("/api/schema/pipeline/generation-cancel",
                                      json={"device_id": "test-device-ctx"})
        assert stop.get_json() == {"cancelled": True}
        box["thread"].join(20.0)
        payload, status = box["answer"]
    finally:
        GA.unmark("run_4stage_ctx")
    assert seen["translation_run_id"] == "run_4stage_ctx"
    assert comfyui.cancelled[:1] == ["p-context"] and "ran_out" not in seen
    assert payload["status"] == "cancelled" and set(payload) == _ENDED_AT_STAGE2
    assert stage2 == []


def test_a_reader_who_leaves_during_stage4_ends_its_prompt(
        comfyui, interception_run, monkeypatch):
    """The watch over Stage 3 and Stage 4 cancels what Stage 4 holds at
    ComfyUI when the reader leaves while it renders."""
    seen, entered, gone = {}, threading.Event(), threading.Event()
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _RecorderOf())
    monkeypatch.setattr(R, "generate_run_id", lambda: "run_4stage_s4")
    monkeypatch.setattr(R, "execute_stage2_with_optimization", _a_finished_interception(seen))
    monkeypatch.setattr(R, "check_before_model",
                        lambda *a, **k: SimpleNamespace(passed=True, operational=False))

    async def rendering(*args, **kwargs):
        run_id = GA.CURRENT_RUN_ID.get()
        seen["stage4"] = run_id
        GA.note_prompt(run_id, "p-stage4")
        gone.set()                       # the reader leaves while Stage 4 renders
        try:
            if not comfyui.reached.wait(15.0):
                seen["ran_out"] = True
        finally:
            GA.forget_prompt(run_id, "p-stage4")
        return SimpleNamespace(success=False, error="interrupted", final_output=None,
                               metadata={}, steps=[])

    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline", rendering)
    try:
        payload, status = R._run_interception_pipeline(
            {"schema": "the_unspoken", "input_text": "ein Haus",
             "device_id": "test-device-s4", "output_config": "sd35_large"},
            "adult", client_gone=gone)
    finally:
        GA.unmark("run_4stage_s4")
    assert seen["stage4"] == "run_4stage_s4"
    assert comfyui.cancelled[:1] == ["p-stage4"] and "ran_out" not in seen
    assert (payload["status"], status) == ("cancelled", 200)
    assert payload["media_output"]["status"] == "cancelled"


def test_a_check_its_ended_run_cut_off_is_recorded_as_no_block(
        comfyui, interception_run, monkeypatch):
    """At kids the prompt is translated before the check. The reader leaves
    while the translation runs; the watcher cancels it, and it comes back
    with nothing, which reads as a check that could not run. That is no
    verdict about the prompt and goes into no record as a block."""
    seen, stage4 = {}, []
    recorder = _RecorderOf()
    monkeypatch.setattr(R, "get_recorder", lambda **kw: recorder)
    monkeypatch.setattr(R, "generate_run_id", lambda: "run_4stage_cut")
    monkeypatch.setattr(R, "execute_stage2_with_optimization", _a_finished_interception(seen))

    async def translation_cut_off(*args, **kwargs):
        GA.mark("run_4stage_cut")       # what the watcher does when the reader leaves
        return None

    monkeypatch.setattr(R, "_translate_for_model", translation_cut_off)
    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline",
                        lambda *a, **k: stage4.append(a))
    try:
        payload, status = R._run_interception_pipeline(
            {"schema": "the_unspoken", "input_text": "ein Haus",
             "device_id": "test-device-cut", "output_config": "sd35_large"},
            "kids")
    finally:
        GA.unmark("run_4stage_cut")
    assert (payload["status"], status) == ("cancelled", 200)
    assert payload["media_output"]["status"] == "cancelled"
    assert recorder.errors == [], "a cut-off check was recorded as a block"
    assert stage4 == []


# ---------------------------------------------------------------------------
# 5. The Flow's stream
# ---------------------------------------------------------------------------

def test_the_flow_ends_its_prompt_when_the_page_goes(comfyui, monkeypatch):
    seen, entered = {}, threading.Event()
    R.init_schema_engine()
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    monkeypatch.setattr(R, "check_intake_texts",
                        lambda *a, **k: SimpleNamespace(passed=True))
    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline",
                        _a_local_model_at_the_card(seen, entered, comfyui.reached))

    app = Flask(__name__)
    with app.test_request_context():
        frames = R.execute_pipeline_streaming(
            {"schema": "the_unspoken", "input_text": "ein Haus", "device_id": "test-device"},
            "adult")
        for _ in frames:
            if entered.is_set():
                break
        assert entered.wait(10.0), "the run never reached the model"
        frames.close()

    assert comfyui.reached.wait(10.0), "the prompt ran on after the page went"
    assert comfyui.cancelled == ["p-stage2"]
    assert seen["run_id"].startswith("flow_interception_")
    assert "ran_out" not in seen
