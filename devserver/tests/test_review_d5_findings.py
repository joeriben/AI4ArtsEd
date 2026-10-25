"""Findings of the code review of 2026-10-10, package D5.

S-024  The training routes answered an error as {"message"} where every other
       route answers {"error"}; the training view read the one shape. Both
       sides say error now; the three success answers keep their message.
S-045  Three tables in types/canvas.ts carried user-facing texts in eight
       languages outside the translation workflow; they carry keys now, and
       every key is in en.ts.
S-016  The export surface carried its texts as literals (part B).
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FE = REPO / "public" / "ai4artsed-frontend" / "src"


def test_the_training_routes_answer_an_error_as_error():
    source = (REPO / "devserver/my_app/routes/training_routes.py").read_text(encoding="utf-8")
    as_message = [line.strip() for line in source.splitlines()
                  if re.search(r'\{"message": .*\}\), (4|5)\d\d$', line)]
    assert as_message == [], as_message
    # Seventeen said message until today; three said error already.
    assert len(re.findall(r'jsonify\(\{"error": .*\}\), (4|5)\d\d$', source, flags=re.M)) == 20
    # A success still says what happened.
    assert '"message": "Training started"' in source
    assert '"message": "Training stopped"' in source


def test_the_training_view_reads_the_error_shape():
    view = (FE / "views/TrainingView.vue").read_text(encoding="utf-8")
    assert "data?.message" not in view and "data.message" not in view
    assert "response.data?.error" in view and "e.response?.data?.error" in view


def _en_keys():
    """Every dotted key of en.ts, read by nesting; a one-line object
    (`mode1: { name: '…', desc: '…' },`) yields its inner keys."""
    text = (FE / "i18n/en.ts").read_text(encoding="utf-8")
    keys = set()
    stack = []
    for line in text.splitlines():
        one_line = re.match(r"^(\s*)('?)([\wé]+)\2: \{ (.*) \},?\s*$", line)
        if one_line:
            depth = len(one_line.group(1)) // 2
            del stack[depth - 1:]
            for inner in re.findall(r"(?:^|, )([\wé]+): (?:'|\"|`)", one_line.group(4)):
                keys.add(".".join(stack + [one_line.group(3), inner]))
            continue
        m = re.match(r"^(\s*)('?)([\wé]+)\2: (\{|'|\"|`)", line)
        if not m:
            if re.match(r"^\s*\},?\s*$", line) and stack:
                stack.pop()
            continue
        depth = len(m.group(1)) // 2
        del stack[depth - 1:]
        if m.group(4) == "{":
            stack.append(m.group(3))
        else:
            keys.add(".".join(stack + [m.group(3)]))
    return keys


def test_the_canvas_tables_name_keys_that_exist():
    source = (FE / "types/canvas.ts").read_text(encoding="utf-8")
    assert "label: { en:" not in source and "description: { en:" not in source
    wanted = set(re.findall(r"(?:labelKey|descriptionKey): '([\w.é]+)'", source))
    assert len(wanted) == 24 + 5 + 30, len(wanted)
    missing = sorted(wanted - _en_keys())
    assert missing == [], missing


def test_the_export_surface_carries_no_literal_text():
    view = (FE / "components/SessionExportView.vue").read_text(encoding="utf-8")
    template = view.split("<script setup>")[0]
    # Text between tags once every {{ … }} is struck: the second review of
    # 2026-10-10 found `25 per page` and `{{ stats.total }} total sessions`
    # behind a pattern that skipped digits and interpolations.
    bare = re.sub(r"\{\{.*?\}\}", "", template, flags=re.S)
    literal = [m.group(1) for m in re.finditer(r">\s*([^<>]*?[A-Za-z][^<>]*?)\s*<", bare)]
    assert literal == [], literal
    # A quoted string with letters inside an interpolation is a literal too
    # ('N/A' stood in three cells, 'Less' in the dates toggle), unless it is
    # the key of a t() call or a value beside a comparison (=== 'asc'). A
    # template literal counts with its `${…}` struck.
    quoted = []
    for inter in re.findall(r"\{\{(.*?)\}\}", template, flags=re.S):
        for m in re.finditer(r"'((?:[^'\\]|\\.)*)'", inter):
            if not re.search(r"[A-Za-z]", m.group(1)):
                continue
            before, after = inter[:m.start()].rstrip(), inter[m.end():].lstrip()
            if before.endswith("t("):
                continue
            if re.search(r"(===|!==|==|!=)$", before) or re.match(r"(===|!==|==|!=)", after):
                continue
            quoted.append(m.group(1))
        for m in re.finditer(r"`((?:[^`\\]|\\.)*)`", inter):
            if re.search(r"[A-Za-z]", re.sub(r"\$\{.*?\}", "", m.group(1))):
                quoted.append(m.group(1))
    assert quoted == [], quoted
    assert not re.search(r'(?<!:)placeholder="[A-Za-z]', template)
    script = view.split("<script setup>")[1].split("</script>")[0]
    assert not re.search(r"error\.value = (['`])[A-Za-z]", script)
    used = set(re.findall(r"t\('(sessionExport\.\w+)'\)", view))
    assert used, "the surface names no sessionExport key"
    missing = sorted(used - _en_keys())
    assert missing == [], missing
