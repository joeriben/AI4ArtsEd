"""
The block message: one form, `safety_block`.

Until 2026-11-01 the server sent it beside the old fields (`stage`,
`blocked_at_stage`, `blocked_on`, `blocked` and their kin), which a page loaded
before the interface read `safety_block` still read. Since then the block
message is the one form.
Three kinds of test here:

* the form;
* the quick check, whose answers the board's intake and the upload widgets read;
* a structural guard: every block answer carries the block message, and none
  carries an old field.
"""

import ast

import pytest

from file_modules import REPO
from my_app.services import safety_gate as gate


# ── The form ────────────────────────────────────────────────────────────────

def test_a_verdict_gives_the_block_message():
    verdict = gate.Verdict(False, gate.CHECKPOINT_INTAKE, "kids", "prompt",
                           gate.REASON_PERSONAL_DATA, "DSGVO: Max Muster")
    assert verdict.block() == gate.safety_block(gate.CHECKPOINT_INTAKE, gate.REASON_PERSONAL_DATA,
                                                "DSGVO: Max Muster", "prompt")


@pytest.mark.parametrize("word, key", [
    ("unchecked", gate.REASON_IMAGE_UNCHECKED),
    ("blocked", gate.REASON_IMAGE_CONTENT),
])
def test_a_refused_delivery(word, key):
    assert gate.delivery_block(word) == {"checkpoint": gate.CHECKPOINT_RESULT, "field": "image",
                                         "reason_key": key, "reason": word}


@pytest.mark.parametrize("word, key", [
    ("unchecked", gate.REASON_UNCHECKED),
    ("blocked", gate.REASON_CODE),
])
def test_a_refused_delivery_of_code_is_said_as_code(word, key):
    assert gate.delivery_block(word, field="code") == {
        "checkpoint": gate.CHECKPOINT_RESULT, "field": "code", "reason_key": key, "reason": word}


# ── The quick check ─────────────────────────────────────────────────────────

@pytest.fixture
def quick():
    import my_app.routes.schema_pipeline_routes as R
    return R


def intake_answers(quick, monkeypatch, verdict):
    """The intake, standing in: it answers `verdict` and records what it was
    asked."""
    asked = []

    def intake(material, *, level, kind, field):
        asked.append((material, level, kind, field))
        return verdict

    monkeypatch.setattr(quick, "check_intake", intake)
    return asked


def test_the_quick_check_is_the_intake(quick, monkeypatch):
    asked = intake_answers(quick, monkeypatch,
                           gate.Verdict(True, gate.CHECKPOINT_INTAKE, "kids", "text"))
    body, status = quick._run_safety_check_quick({"text": " ein Haus "}, "kids")
    assert status == 200 and body["safe"] is True
    assert asked == [("ein Haus", "kids", "text", "text")]


def test_the_quick_check_answers_with_the_intakes_block(quick, monkeypatch):
    for key in (gate.REASON_PERSONAL_DATA, gate.REASON_UNAVAILABLE):
        intake_answers(quick, monkeypatch,
                       gate.Verdict(False, gate.CHECKPOINT_INTAKE, "kids", "text", key, "warum"))
        body, status = quick._run_safety_check_quick({"text": "x"}, "kids")
        assert status == 200 and body["safe"] is False
        assert body["safety_block"] == {"checkpoint": "intake", "field": "text",
                                        "reason_key": key, "reason": "warum"}


def test_the_quick_check_on_a_picture(quick, monkeypatch):
    """The picture mode reads the verdict a picture got where it came in and
    asks no model (tests/test_upload_intake.py has the verdicts). A path that
    carries none is refused in the same form as every other block."""
    from my_app.utils import vlm_safety

    def asked(path, level):
        raise AssertionError("the quick check asked the vision model")

    monkeypatch.setattr(vlm_safety, "vlm_safety_check", asked)
    body, _ = quick._run_safety_check_quick({"image_path": "/x.png"}, "kids")
    assert body["safe"] is False
    assert body["safety_block"] == {"checkpoint": "intake", "field": "image",
                                    "reason_key": "image_unchecked", "reason": ""}


def test_a_quick_check_that_raised_is_a_fault(quick, monkeypatch):
    def broken(material, *, level, kind, field):
        raise RuntimeError("the recogniser is gone")

    monkeypatch.setattr(quick, "check_intake", broken)
    body, _ = quick._run_safety_check_quick({"text": "x"}, "kids")
    assert body["safe"] is False
    assert body["safety_block"]["reason_key"] == "unavailable"


# ── Every block answer carries it ───────────────────────────────────────────

# The files that answer a block.
ANSWER_FILES = (
    "devserver/my_app/routes/schema_pipeline_routes.py",
    "devserver/my_app/routes/interception_prompts_routes.py",
    "devserver/my_app/routes/mean_images_routes.py",
    "devserver/my_app/routes/pipeline_routes.py",
    "devserver/my_app/routes/media_routes.py",
    "devserver/my_app/routes/canvas_routes.py",
    "devserver/my_app/services/canvas_executor.py",
)


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def _called(node) -> str:
    return getattr(node.func, "id", None) or getattr(node.func, "attr", None) or ""


def _is_block_answer(entries: dict) -> bool:
    return (_const(entries.get("status")) == "blocked"
            or _const(entries.get("error")) == "safety_blocked"
            # the quick check's refusal
            or (_const(entries.get("safe")) is False and "error_message" in entries))


def _blocks_by_form(tree) -> set:
    """The dicts a block is sent as by its form: a stream's `blocked` event, and
    an answer with 403, which in these files is the status of a block alone."""
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and _called(node) == "generate_sse_event"
                and len(node.args) > 1 and _const(node.args[0]) == "blocked"
                and isinstance(node.args[1], ast.Dict)):
            found.add(id(node.args[1]))
        if (isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)
                and len(node.value.elts) == 2 and _const(node.value.elts[1]) == 403):
            body = node.value.elts[0]
            if isinstance(body, ast.Call) and _called(body) == "jsonify" and body.args:
                body = body.args[0]
            if isinstance(body, ast.Dict):
                found.add(id(body))
    return found


def test_every_block_answer_carries_the_block_message():
    missing, seen = [], 0
    for rel in ANSWER_FILES:
        tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
        by_form = _blocks_by_form(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            entries = {_const(k): v for k, v in zip(node.keys, node.values) if k is not None}
            if id(node) not in by_form and not _is_block_answer(entries):
                continue
            seen += 1
            if "safety_block" not in entries:
                missing.append(f"{rel}:{node.lineno}")
    assert missing == [], f"block answers without `safety_block`: {missing}"
    # Not a guard over nothing: the forms above still find the answers.
    assert seen >= 30, seen


# The fields a block was said in before the block message, and that a block
# carried beside it until no reader was left.
OLD_FIELDS = {"stage", "blocked", "blocked_at_stage", "blocked_on", "blocked_reason",
              "blocked_stage"}


def test_no_block_answer_carries_an_old_field():
    """Beside the block message, in it or in a dict it carries, and in no
    result a block is written into afterwards."""
    found, seen = [], 0
    for rel in ANSWER_FILES:
        tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                entries = {_const(k): v for k, v in zip(node.keys, node.values)
                           if k is not None}
                if "safety_block" not in entries:
                    continue
                seen += 1
                names = set(entries)
                for value in entries.values():
                    if isinstance(value, ast.Dict):
                        names |= {_const(k) for k in value.keys if k is not None}
                found += [f"{rel}:{node.lineno} {name}" for name in sorted(OLD_FIELDS & names)]
            elif (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
                    and _const(node.slice) in OLD_FIELDS - {"stage"}):
                found.append(f"{rel}:{node.lineno} {_const(node.slice)}")
    assert found == [], f"old fields of the block message: {found}"
    assert seen >= 30, seen
