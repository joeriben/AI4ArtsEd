#!/usr/bin/env python3
"""
Policy: filler says nothing, and the gate proves it.

UCD-103 (reopened 2026-09-25): redundant filler that says nothing, in a place
where no filling was needed. Five large passes removed slop from the surfaces and it grew back,
because the classes the passes hunted lived in no gate: a gate that checks
only what it can name cannot hold a state nobody named. This file names the
classes the reopen found and holds them out of the two hand-maintained
sources.

What it sees, exactly (FILLER_PATTERNS):

  - The pleonasms: „Wort für Wort" / "word for word" outside
    a contrastive negation ("liest den Prompt nicht Wort für Wort ab" states
    a fact of attention and stays -- the phrase asserts nothing there, it
    negates). The assertive uses („sprechen ihn Wort für Wort, wie er im
    Feld steht") said nothing the field did not say; the correction pass of
    2026-09-25 removed them.
    The check is therefore on the phrase MINUS the reach of a negation in
    front of it (a "nicht" / "not" within the 40 characters before the hit,
    or at clause start, shields the contrastive use and nothing else).
  - The fable metaphors for machine reading: „wie eine Bauanleitung" /
    "like a set of instructions" -- provenance decoration for an operation
    that has a plain name. A metaphor that carries no information the plain
    sentence lacks is filler (THE ADDRESS IS THE EXCEPTION, NOT THE FORM in
    docs/COPY_RULES.md is the sibling rule).
  - The reflexive reassurance around a plain fact: "This tool makes that
    distribution visible:" followed by a restatement. Out of scope for the
    regex gate -- clause-level judgement is the copy rules' own business; the
    patterns here are the classes a regex can see without judging prose.

In the VALUES of the two hand-maintained i18n sources, de.ts and en.ts,
parsed with the grammar gate's own scanner (test_i18n_label_grammar.py); a
template literal or block comment the parser cannot read is a finding,
never a skip. Source comments are stripped before values are read.

The eight target languages (fr es tr ko uk he ar bg) are out of scope: they
are translated by the batch agent against work orders
(src/i18n/WORK_ORDERS.md) and carry this standard through those passes;
their stock of filler phrases arrives with WO-2026-09-25-A1. Widening the
scope is a decision recorded in a commit message, not a silent edit here.

A pattern the gate finds is fine only with its reason named nearby, in a
source comment in the wording markers' shape -- the same shapes and the
same nearest-first search as test_i18n_direct_address.py (SUPPLIED WORDING
PRECEDES EVERY CRITERION, „Vorgegebener Wortlaut ... bleibt wörtlich", ...).
Supplied wording precedes every criterion.

Sibling of test_i18n_direct_address.py; enforced as gate 7 in
scripts/git-hooks/pre-commit.

Run: python3 devserver/tests/test_i18n_filler_phrases.py
     python3 -m pytest devserver/tests/test_i18n_filler_phrases.py -q
"""
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_i18n_label_grammar as grammar  # noqa: E402
import test_i18n_direct_address as address  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
I18N_REL = grammar.I18N_REL
SOURCE_LANGUAGES = ("de", "en")

TEST_REL = "devserver/tests/test_i18n_filler_phrases.py"

# --------------------------------------------------------------------------------
# The classes a regex can see without judging prose. Each entry:
# (compiled pattern, tail naming the class for the report). A hit shielded by
# a negation in the reach before it is contrastive and stays.
# --------------------------------------------------------------------------------
_FILLER_SPEC = [
    # The pleonasm, assertive uses only (see module header).
    (re.compile(r"[Ww]ort für [Ww]ort"), "pleonasm"),
    (re.compile(r"[Ww]ord for word"), "pleonasm"),
    # The fable metaphor for machine reading.
    (re.compile(r"wie eine Bauanleitung"), "fable metaphor"),
    (re.compile(r"like a set of instructions"), "fable metaphor"),
]

NEGATION = re.compile(r"\b(nicht|not|no longer|kein)\b")

# The reach in which a negation shields a contrastive use: the characters
# before the hit, up to and including the clause boundary.
_NEG_REACH = 40

DOCUMENTED_REASON = address.DOCUMENTED_REASON

# --------------------------------------------------------------------------------
# The state the 2026-09-25 correction pass established, held: the seven keys
# it corrected may not carry filler again, and none of them may be listed as
# excluded stock. (ADDRESS_SLOTS discipline, applied to this gate's stock.)
# --------------------------------------------------------------------------------
FILLER_SLOTS = {
    "compare.address.vlm-analysis.story",
    "compare.address.language.purpose",
    "compare.address.voice.story",
    "compare.address.systemprompt.purpose",
    "latentLab.attention.explainWhatText",
    "docs.guideLatentLab.theModelDoesNot",
}

FILLER_DEBT: set = set()          # no excluded stock as of 2026-09-25


def _hit_is_contrastive(value: str, start: int) -> bool:
    """True when a negation stands in the reach before the hit."""
    reach = value[max(0, start - _NEG_REACH):start]
    reach = re.sub(r"[.;:!?]\s*$", "", reach)          # clause start shields too
    return bool(NEGATION.search(reach))


def check_content(lang, source, label=None):
    """Undocumented filler phrases in one locale source."""
    if label is None:
        label = f"{lang}.ts"
    entries, problems = grammar.parse_locale(source, label)
    found = list(problems)
    lines = source.splitlines()
    ancestors = address._ancestor_map(source)
    for dotted, value, num in entries:
        if (lang, dotted) in FILLER_DEBT:
            continue
        for pattern, tail in _FILLER_SPEC:
            match = pattern.search(value)
            if match is None:
                continue
            if _hit_is_contrastive(value, match.start()):
                continue
            if address.reason_comment(lines, ancestors.get(num, ()),
                                       num, value) is not None:
                continue
            found.append(f"{label}:{num}  {dotted} = '{value}'  -> filler "
                         f"phrase ({tail}); filler says nothing, and no "
                         f"surface needs it (UCD-103, docs/COPY_RULES.md)")
            break
    return found


def _missing_sources():
    return [f"source file {lang}.ts missing under {I18N_REL} -- the gate "
            f"checked nothing"
            for lang in SOURCE_LANGUAGES
            if not (grammar.I18N_DIR / f"{lang}.ts").is_file()]


# --------------------------------------------------------------------------------
# Staged mode. The discipline is the address gate's: a gate judges only the
# commit in front of it, and a commit that touches no i18n source passes
# without reading anything.
# --------------------------------------------------------------------------------
def _git(*args):
    return subprocess.run(("git",) + args, cwd=str(REPO),
                          capture_output=True, text=True, check=True).stdout


def _staged_report():
    staged = set(_git("diff", "--cached", "--name-only",
                      "--diff-filter=ACMR").splitlines())
    sources = {}
    for name in staged:
        if not name.startswith(I18N_REL + "/") or not name.endswith(".ts"):
            continue
        stem = name.rsplit("/", 1)[-1][:-3]
        if stem in SOURCE_LANGUAGES:
            sources[name] = stem
    if not sources:
        return ([], False)
    lines = []
    for name, lang in sorted(sources.items()):
        source = _git("show", f":{name}")
        lines.extend(check_content(lang, source, label=name))
    return (lines, bool(lines))


# --------------------------------------------------------------------------------
# pytest
# --------------------------------------------------------------------------------
def test_filler_phrases_absent_from_the_two_sources():
    missing = _missing_sources()
    assert not missing, "\n  ".join(missing)
    found = []
    for lang in SOURCE_LANGUAGES:
        found += check_content(lang, grammar._read(lang))
    assert not found, ("Filler says nothing, and no surface needs it:\n  "
                       + "\n  ".join(found))


def test_filler_slots_may_not_be_stocked():
    """The state the 2026-09-25 pass established, held: none of the corrected
    keys carries filler, and none sits on an excluded stock."""
    on_slots = [f"{lang} {key}" for lang, key in sorted(FILLER_DEBT)
                if key in FILLER_SLOTS]
    assert not on_slots, ("a corrected surface may not be carried as "
                          "excluded stock:\n  " + "\n  ".join(on_slots))
    for lang in SOURCE_LANGUAGES:
        source = grammar._read(lang)
        entries, problems = grammar.parse_locale(source, f"{lang}.ts")
        assert not problems, problems
        lines = source.splitlines()
        ancestors = address._ancestor_map(source)
        for dotted, value, num in entries:
            if dotted not in FILLER_SLOTS:
                continue
            for pattern, _tail in _FILLER_SPEC:
                match = pattern.search(value)
                if match is None:
                    continue
                if _hit_is_contrastive(value, match.start()):
                    continue
                reason = address.reason_comment(lines, ancestors.get(num, ()),
                                                num, value)
                assert reason is not None, (
                    f"{lang}.ts:{num}  {dotted} = '{value}'  -> filler "
                    f"phrase on a corrected surface without a named reason "
                    f"(UCD-103)"
                )
                break


if __name__ == "__main__":
    if not grammar.I18N_DIR.is_dir():
        print(f"filler gate: no {I18N_REL} in this checkout, gate does not apply")
        raise SystemExit(0)

    if "--staged" in sys.argv:
        try:
            lines, blocking = _staged_report()
        except Exception as e:                               # noqa: BLE001
            print(f"filler gate could not read the staged commit ({e}); "
                  f"letting it through", file=sys.stderr)
            raise SystemExit(0)
        if blocking:
            print("\nCOMMIT BLOCKED -- filler phrase:\n  " + "\n  ".join(lines)
                  + "\n\nFiller says nothing, and no surface needs it. Name "
                  "the operation\nplainly, or -- where the wording itself is "
                  "the point -- name the reason\nin a source comment above "
                  "the key, in the wording markers' shape\n(SUPPLIED WORDING "
                  "PRECEDES EVERY CRITERION, „Vorgegebener Wortlaut ... bleibt "
                  "wörtlich\").\ndocs/COPY_RULES.md carries the "
                  "whole rule.\n\nWidening a list or bending the rule is a "
                  "decision recorded in the commit message, not a "
                  "--no-verify.\n", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)

    bad = (_missing_sources()
           + [line for lang in SOURCE_LANGUAGES
              for line in check_content(lang, grammar._read(lang))])
    if bad:
        print("\n".join(bad), file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)