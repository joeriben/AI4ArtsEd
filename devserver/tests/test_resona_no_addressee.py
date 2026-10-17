"""
Tests that nothing in Resona's context addresses her as a second person.

Why it exists: the prompt was rebuilt as a situation rather than a figure —
every self-reference removed, the vocabulary audited on one criterion (does the
term have a referent on this platform?). The core prompt came out clean and the
figure came back anyway, because the core prompt is only part of what reaches
the model. The compass headers, the machine note, the language directive and
above all the tool descriptions still spoke to a "you", and several of them gave
that "you" a body and possessions: a file "put before your eyes", "your grown
repertoire", "a prompt YOU write". An addressee has an I. That is where the I
came from, not from the core prompt.

This is the same leak the vocabulary audit had: a rule enforced in the prompt
and silently absent one layer down, in the strings the registry composes. The
prompt is version-controlled prose that gets read; tool descriptions get edited
while adding a parameter. So the check lives here, not in review.

What is enforced (the enforcement, never the wording of a draft):
  - no second person anywhere in the resona-scope tool schemas — descriptions
    and parameter descriptions alike, since both reach the model verbatim,
  - no first OR second person, singular or plural, in the composed system
    prompt — in EVERY situation branch, since each carries its own block —
    except where the prompt QUOTES: the two service questions it names in
    order to rule out, a cited work's title, and a label the interface
    actually carries.

The pattern covers "we/us/our" too. A first-person plural is the same move as
the address, one step further in: it does not just give the model a self, it
enrols the group into it.

Run: python3 -m pytest devserver/tests/test_resona_no_addressee.py -q
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes.chat_routes import build_system_prompt
from my_app.services.tool_registry import get_tool_registry

PERSON = re.compile(
    r"\b(I|I'm|I've|I'll|I'd|me|my|mine|myself|"
    r"we|we're|we've|we'll|we'd|us|our|ours|ourselves|let's|"
    r"you|you're|you've|you'll|you'd|your|yours|yourself|yourselves)\b",
    re.IGNORECASE,
)

SITUATIONS = ("workshop", "consulting", "nachklapp")

# Quoted material, not address. Removed before counting, each with its reason.
QUOTED = [
    # HOW A TURN ENDS names the two sentences it rules out. Naming them requires
    # writing them.
    'The service question — "Shall I …?", "Do you want me to …?" —',
    # The start page carries this label in the interface; the modes note reports
    # what is on the screen. It addresses the group, not the model.
    "'Your Call!'",
    # A cited work's title in the values compass. Three occurrences; the loop
    # below removes every one.
    "Reimagining Our Futures Together",
    # WHAT SPEAKS HERE names the permitted self-reference forms. Naming them
    # requires writing them — the same case as the two service questions above.
    'Where a first person cannot be avoided it is plural — "we", "us"; in '
    'German "wir", "uns". A first person singular is never written: not "I", '
    'not the German "ich".',
]


def _normalize(text: str) -> str:
    """Prompts are hard-wrapped; a phrase assertion breaks at the line break."""
    return re.sub(r"\s+", " ", text)


@pytest.fixture(scope="module", params=SITUATIONS)
def resona_prompt(request) -> str:
    return _normalize(build_system_prompt(
        context={"resona_mode": True, "resona_situation": request.param,
                 "device_id": "test-no-addressee"},
        language="de",
    ))


@pytest.fixture(scope="module")
def resona_tools() -> list:
    return get_tool_registry().get_openai_format(scope="resona")


def test_tool_descriptions_carry_no_addressee(resona_tools):
    offenders = []
    for tool in resona_tools:
        fn = tool["function"]
        for hit in PERSON.findall(fn.get("description", "")):
            offenders.append(f"{fn['name']} (description): {hit}")
    assert not offenders, (
        "Tool descriptions address the model as 'you'. They reach the model "
        "verbatim, so an addressee here installs the I that the prompt was "
        "rebuilt to remove. Write the tool's own action, not the reader's:\n  "
        + "\n  ".join(offenders)
    )


def test_tool_parameters_carry_no_addressee(resona_tools):
    offenders = []
    for tool in resona_tools:
        fn = tool["function"]
        params = json.dumps(fn.get("parameters", {}), ensure_ascii=False)
        for hit in PERSON.findall(params):
            offenders.append(f"{fn['name']} (parameters): {hit}")
    assert not offenders, (
        "Parameter descriptions address the model as 'you' — same context, "
        "same effect as the tool description itself:\n  " + "\n  ".join(offenders)
    )


def test_system_prompt_carries_no_addressee_outside_quotation(resona_prompt):
    stripped = resona_prompt
    for quote in QUOTED:
        assert quote in stripped, (
            "The quoted passage this test exempts is no longer in the prompt: "
            f"{quote!r}. Update QUOTED — do not widen the pattern."
        )
        stripped = stripped.replace(quote, " ")  # every occurrence

    offenders = []
    for match in PERSON.finditer(stripped):
        start = max(0, match.start() - 70)
        offenders.append("…" + stripped[start:match.end() + 70].strip() + "…")
    assert not offenders, (
        "The composed Resona context addresses her as 'you'. The prompt was "
        "rebuilt as a situation; an addressee anywhere in what is assembled "
        "around it puts the figure back. Remove the address rather than adding "
        "a rule against the I:\n  " + "\n  ".join(offenders)
    )
