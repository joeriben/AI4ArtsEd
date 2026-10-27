#!/usr/bin/env python3
"""
Policy: an element structure exists ONCE. The registry rule, made mechanical.

`docs/ELEMENT_STRUCTURE_REGISTRY.md` has said since 2026-07 that a second
implementation of an existing element structure is a bug.
It is prose, and prose is what was walked past: on 2026-08-21 the
platform held FIVE hand-copies of the band's run button, and the conversion of
Denoising Archaeology to the band had silently deleted its ready-made prompts -- block,
import, list and handler -- in a commit whose message did not mention it.

Prose did not catch either. This does.

The rules below are narrow on purpose. Each one encodes a duplication that actually
happened, in a shape that cannot fire on anything else; a gate that cries wolf is a
gate somebody switches off. What this test cannot check -- whether a NEW structure
belongs in the registry -- stays a reading obligation.

Sibling of `test_no_model_literals.py`, whose shape this follows down to the
--staged entry point. Run: python3 -m pytest devserver/tests/test_element_structure_policy.py -q
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "public/ai4artsed-frontend/src"

# ---------------------------------------------------------------------------
# R1  The run triangle is DRAWN once.
#
# `components/FlowRunButton.vue` is the button. `views/x2x_flow.vue` draws the same
# glyph without being that button, and it is not a copy: there the NODE is the control
# (hold-to-stop, opens into the run panel) and the triangle is one of its phases -- see
# the registry entry. Anywhere else, this path is a sixth copy.
# ---------------------------------------------------------------------------
PLAY_PATH = "M8 5.5 19 12 8 18.5Z"
PLAY_PATH_ALLOWED = {
    "components/FlowRunButton.vue",
    "views/x2x_flow.vue",
}

# ---------------------------------------------------------------------------
# R2  The triangle is STYLED once: `assets/flow-stage.css`, which owns the flow's
# size steps and where `--flow-play` already lived. Until 2026-08-21 the same five
# declarations stood in five files. State modifiers a page gives the glyph
# (`.nd.op.ready:hover .play`, `.play.off`) are the page's business and not matched
# here -- only a bare `.play { ... }` block, which is the definition itself.
# ---------------------------------------------------------------------------
PLAY_RULE = re.compile(r"^\s*\.play\s*\{", re.MULTILINE)
PLAY_RULE_ALLOWED = {"assets/flow-stage.css"}

# ---------------------------------------------------------------------------
# R3  An instrument surface that takes a WRITTEN prompt carries the combination
# Model Bias sets (`views/compare/model_comparison.vue`): the ready-made prompts above
# the field, and the perspective in it. The Model-Bias input combination is a mandatory
# template for such a surface.
#
# "Written" is the whole condition, and it has two halves: the field can be written
# INTO, and what is written is TEXT.
#
# Written into: `v-model:value`, or the same two-way binding spelled out as `:value=`
# WITH `@update:value=`. Until 2026-09-03 only the shorthand counted, and a page that
# wrote the pair out by hand was skipped although the visitor types into it exactly the
# same way -- `views/compare/system_prompt_comparison.vue` had stood outside the rule
# since it was written. A field bound one-way, `:value=` and no writer, holds a case
# drawn from a benchmark rather than a prompt: Bias Archaeology 1 and 2 rightly offer
# neither a prompt list nor a perspective, because a perspective would rewrite the
# wording that IS the measurement. Cover Band takes a recording. None of the three is
# caught, and none of them binds a writer.
#
# Text: `input-type="image"` is a picture being handed over, and a ready list of
# prompts and a perspective ring have nothing to offer it. The upload field of Image
# Understanding is such a field; the written question BESIDE it on the same page binds
# `v-model:value` and is covered as it should be.
#
# The gate read `<FlowHeader` until 2026-08-22, when the last instrument gave up its
# band and the rule quietly covered NOTHING -- the tree went green because there was
# no longer anything to check, which is the failure this file exists to prevent. What
# it was ever a proxy for is "a rebuilt instrument surface", and such a surface is now
# recognised by where its trigger hangs (`.shell-bar-run`) just as it used to be by the
# band. Both markers stand, so a surface that keeps a band stays covered.
#
# Deliberately NOT widened to every file that binds `v-model:value`: one surface
# outside this form does (direct), and whether the combination is mandatory for it
# is an open product decision. This repair does not make it.
# ---------------------------------------------------------------------------
MEDIA_INPUT_TAG = re.compile(r"<MediaInputBox\b(.*?)/>", re.DOTALL)

# The two ways a field is written into, and the one kind of field this rule leaves out.
VALUE_LONGHAND = re.compile(r"(^|\s):value\s*=")
VALUE_WRITER = re.compile(r"@update:value\s*=")
IMAGE_FIELD = re.compile(r'input-type\s*=\s*"image"')

# The perspective stands on an instrument surface in one of THREE shapes, and the rule
# asks the surface for one of them -- never for a particular one.
#
#  1. The RING in the field: `:show-preset-button` opens `InterceptionPresetOverlay`,
#     ONE perspective is chosen there, and it applies to everything the surface runs.
#     This is the shape Model Bias set and the one every instrument had until
#     2026-09-04.
#  2. The surface CHOOSES SEVERAL perspectives, because they are what it varies --
#     Perspectives on a Template, whose rows ARE the perspectives. It opens the same
#     ring, from a strip of discs rather than from the field, and takes several out
#     of it; a second chooser beside that strip would be the parallel structure Rule
#     13 forbids. Until 2026-09-04 it chose from chips of its own, and this clause
#     was written for that surface.
#  3. The surface RUNS perspectives it NAMES -- Aesthetic Poles (2026-09-04), which puts
#     one template through the two poles of one checklist. Which perspectives run is
#     what that instrument IS and not something to be chosen on it; a ring would offer
#     a third one for the same line, and a chooser would make it a different
#     instrument.
#
# The second shape IS the platform's catalogue of perspectives -- since 2026-09-04 one
# module, which the chooser and the instrument both read
# (`composables/usePerspectiveCatalog.ts`). A surface that imports it is reading that
# list, which is the same act the ring performs through the chooser.
#
# The third is the RUN of the group: `composables/useInterceptionSeries.ts` writes every
# row that carries a request through POST /api/schema/pipeline/stage2 with a preset as
# its `schema`, which is the interception itself. A surface built on it therefore puts
# its line through perspectives by construction, and whether they were chosen in a ring,
# ticked in a column or named by the instrument is a question about WHICH perspective,
# not about whether there is one.
#
# Both are recognised by an IMPORT THAT NAMES THE THING, never by a bare token and
# never by any import from the module: until 2026-09-04 the rule matched the pipeline
# name `text_transformation_recursive` anywhere in the file, so a comment mentioning
# that pipeline satisfied the perspective rule for every prompt field of a surface with
# no chooser at all; and until the fix round after it, any named import from the run
# module did -- `import { markTerms }` takes a helper that marks words in a string, and
# a surface running no interception passed on it. So the braces have to name the reader
# of the list (`usePerspectiveCatalog`) or the run itself (`useInterceptionSeries`).
# Naming the consuming FILES instead would be an allowlist by another name, and the set
# below "may shrink, must not grow".
PERSPECTIVE_MODULES = (
    "@/composables/usePerspectiveCatalog",
    "@/composables/useInterceptionSeries",
)


def _imports(text: str, module: str) -> bool:
    """Whether the file really TAKES THE THING these modules are named for.

    The braces have to NAME it: `usePerspectiveCatalog` for the catalogue,
    `useInterceptionSeries` for the run -- the function that reads the list, or the one
    that puts a line through a perspective. Matching any named import from the module
    was not enough: `import { markTerms } from '@/composables/useInterceptionSeries'`
    takes an ordinary helper that marks words in a string, runs no interception, and
    satisfied the rule for a surface that never puts its line through a perspective at
    all.

    In either spelling of the quotes and over as many lines as the braces take. Reading
    only one spelling would have let a surface out of the rule for a reason as small as
    a double quote, and the gate would have gone green over it.

    `import type { ... }` is deliberately not matched: a type is not a chooser and runs
    nothing, and a file that takes only a type from these modules neither reads the list
    nor puts a line through a perspective. What stands inside the braces may not contain
    a closing brace, so the match cannot run from an EARLIER import statement down to
    this one.

    And the braces are READ, specifier by specifier, rather than searched for the name:
    a search saw the name wherever it stood, so `{ markTerms as useInterceptionSeries }`
    (which takes the helper and merely calls it the run) and `{ type
    useInterceptionSeries }` (which takes a type by that name) both satisfied the gate.
    What counts is the IMPORTED name -- the one on the module's side of an `as`. What a
    file calls it locally is its own business, so `{ useInterceptionSeries as series }`
    does take the run.
    """
    wanted = module.rsplit("/", 1)[-1]
    statement = r"""^import\s+\{([^}]*)\}\s*from\s+['"]%s['"]""" % re.escape(module)
    for braces in re.findall(statement, text, re.MULTILINE | re.DOTALL):
        for specifier in braces.split(","):
            tokens = specifier.split()
            # `{ type X }`: a type runs nothing, exactly as `import type` does not.
            if not tokens or tokens[0] == "type":
                continue
            if tokens[0] == wanted:
                return True
    return False


def _takes_a_written_prompt(attrs: str) -> bool:
    """Whether this field is one a visitor types a prompt into."""
    if IMAGE_FIELD.search(attrs):
        return False
    if "v-model:value" in attrs:
        return True
    return bool(VALUE_LONGHAND.search(attrs) and VALUE_WRITER.search(attrs))

# What marks a rebuilt instrument surface. Named once: the rule and the staleness
# check below both read it, and two copies of the list would drift apart.
# The three surfaces of the Crossmodal Lab (views/latent_lab/audio_synth.vue,
# imagebind_guidance.vue, mmaudio.vue) carry none of the three markers above and
# were not seen until 2026-10-10 (finding S-041 of the code review of 2026-10-10): the synth's script had carried a
# perspective since 2026-09-05 that its template never offered. Their root
# class names them.
SURFACE_MARKERS = ("<FlowHeader", "shell-bar-run", "<ShellRun", 'class="xm-lab"')


def _is_instrument_surface(text: str) -> bool:
    return any(marker in text for marker in SURFACE_MARKERS)

# Documented exceptions. May shrink, must not grow: a new entry is a recorded product
# decision, never a way past a red test. Empty on 2026-08-21 -- the tree satisfies all
# three rules.
#
# THREE entries since 2026-09-03, and every one of them is a FINDING AWAITING A
# DECISION rather than a settled case; the list may shrink, never grow. A FOURTH
# came on 2026-10-27 and is the same finding a second time: Model Comparison
# (Transformers Lab) was ordered as a copy of System Prompts and inherits its missing ready
# list. It is not a decision either; it is decided together with the System
# Prompts entry and goes with it. The first came
# with the widening of the trigger to `<ShellRun` (above), which brought five surfaces
# inside the gate that had stood outside it; four satisfy the rule already, and the
# Tokenizer
# carries the ready-made sentences but no perspective ring. Whether it SHOULD carry one
# is an open product decision: the sentence there is what gets taken apart into
# tokens, so a perspective would hand the visitor a different sentence to measure,
# and that is a question about the instrument, not about this file. Until it is
# decided, the gap stands NAMED here instead of hidden behind a narrower trigger.
# Delete this entry once it is decided either way.
ALLOWED: set = {
    ("views/latent_lab/tokenization_comparison.vue", "perspective"),
    # The same, from the second widening on 2026-09-03 (a two-way binding spelled out
    # by hand now counts as written). System Prompts has the perspective and no ready
    # list; Representation Engineering has the ready list and no perspective. Both gaps
    # predate this file's ability to see them, both are open product decisions, and
    # both entries go the moment they are decided.
    ("views/compare/system_prompt_comparison.vue", "examples"),
    ("views/latent_lab/representation_engineering.vue", "perspective"),
    # The same open decision as System Prompts', not a second one: Model
    # Comparison (Transformers Lab) was ordered on 2026-10-27 as a copy of System Prompts with
    # the two axes exchanged, and takes its message field as that
    # surface has it. Whether the two carry ready-made messages, and which, is
    # decided for both at once; the two entries go together.
    ("views/latent_lab/system_prompt_across_models.vue", "examples"),
}


def _files(*suffixes):
    for path in sorted(SRC.rglob("*")):
        if path.suffix in suffixes and path.is_file():
            yield path.relative_to(SRC).as_posix(), path.read_text(encoding="utf-8")


def _offenders_in(rel, text):
    found = []

    if PLAY_PATH in text and rel not in PLAY_PATH_ALLOWED and (rel, "play-path") not in ALLOWED:
        found.append(
            f"{rel}: draws the run triangle by hand -- use <FlowRunButton> "
            f"(components/FlowRunButton.vue)"
        )

    if PLAY_RULE.search(text) and rel not in PLAY_RULE_ALLOWED and (rel, "play-rule") not in ALLOWED:
        found.append(
            f"{rel}: defines `.play` a second time -- it is drawn in assets/flow-stage.css"
        )

    if _is_instrument_surface(text):
        for attrs in MEDIA_INPUT_TAG.findall(text):
            if not _takes_a_written_prompt(attrs):
                continue                      # a case, a recording, a picture
            if "<PromptExamples" not in text and (rel, "examples") not in ALLOWED:
                found.append(
                    f"{rel}: prompt field on an instrument surface without "
                    f"<PromptExamples> above it "
                    f"-- the combination Model Bias sets is mandatory"
                )
            has_perspective = "show-preset-button" in attrs or any(
                _imports(text, module) for module in PERSPECTIVE_MODULES
            )
            if not has_perspective and (rel, "perspective") not in ALLOWED:
                found.append(
                    f"{rel}: prompt field on an instrument surface without a perspective "
                    f"-- one of the three shapes: the ring (:show-preset-button + "
                    f"components/InterceptionPresetOverlay.vue), the surface's own "
                    f"perspective list (composables/usePerspectiveCatalog.ts), or the "
                    f"group's run (composables/useInterceptionSeries.ts)"
                )
    return found


def _offenders():
    found = []
    for rel, text in _files(".vue", ".css"):
        found.extend(_offenders_in(rel, text))
    return found


def _staged_offenders():
    """What THIS commit touches -- the staged content of staged frontend files.

    Whole files, not added lines: these rules are properties of a file (a field either
    has its list above it or it has not), and half a rule read from a diff hunk is
    worse than none. Still narrow, because only files the commit actually touches are
    judged -- several sessions share this checkout, and another session's unfinished
    edit is not grounds to refuse a commit that has nothing to do with it.
    """
    import subprocess

    def git(*args):
        return subprocess.run(("git",) + args, cwd=str(REPO),
                              capture_output=True, text=True, check=True).stdout

    prefix = "public/ai4artsed-frontend/src/"
    found = []
    for name in git("diff", "--cached", "--name-only", "--diff-filter=ACM").splitlines():
        if not name.startswith(prefix) or not name.endswith((".vue", ".css")):
            continue
        found.extend(_offenders_in(name[len(prefix):], git("show", f":{name}")))
    return found


def test_element_structures_are_not_reimplemented_by_hand():
    offenders = _offenders()
    assert not offenders, (
        "An element structure exists once "
        "(docs/ELEMENT_STRUCTURE_REGISTRY.md):\n  " + "\n  ".join(offenders)
    )


def test_the_allowlist_does_not_cover_what_is_already_gone():
    """A stale exemption is an open door nobody remembers opening."""
    live = set()
    for rel, text in _files(".vue", ".css"):
        if PLAY_PATH in text:
            live.add((rel, "play-path"))
        if PLAY_RULE.search(text):
            live.add((rel, "play-rule"))
        if _is_instrument_surface(text):
            live.add((rel, "examples"))
            live.add((rel, "perspective"))
    stale = sorted(ALLOWED - live)
    assert not stale, (
        "allowlist entries that no longer match anything -- delete them:\n  "
        + "\n  ".join(f"{rel}: {what}" for rel, what in stale)
    )


def test_an_import_is_recognised_in_every_spelling_and_a_mention_is_not():
    """What R3 turns on: whether the surface really READS one of these modules.

    The rule matched a bare token until 2026-09-04, so a comment naming a pipeline
    satisfied it; then one spelling of one import, so a double quote or a brace over
    several lines would have let a surface out of the rule again. Both failures are
    invisible from outside -- the gate simply goes green.
    """
    module = "@/composables/usePerspectiveCatalog"
    reads = (
        "import { usePerspectiveCatalog } from '@/composables/usePerspectiveCatalog'\n",
        'import { usePerspectiveCatalog } from "@/composables/usePerspectiveCatalog"\n',
        "import {\n  usePerspectiveCatalog,\n} from '@/composables/usePerspectiveCatalog'\n",
        'import {\n  usePerspectiveCatalog,\n} from "@/composables/usePerspectiveCatalog"\n',
        # After another import: the braces may not swallow the earlier statement.
        "import { ref } from 'vue'\nimport { usePerspectiveCatalog } from "
        "'@/composables/usePerspectiveCatalog'\n",
    )
    for text in reads:
        assert _imports(text, module), f"an import went unrecognised:\n{text}"

    does_not_read = (
        # A mention is not a reading -- the failure this check exists for.
        "// see composables/usePerspectiveCatalog for what a perspective is\n",
        "const where = '@/composables/usePerspectiveCatalog'\n",
        # A type is not a chooser.
        "import type { PaletteItem } from '@/composables/usePerspectiveCatalog'\n",
        # Another module, whose name this one is a prefix of.
        "import { usePerspectiveCatalogue } from '@/composables/usePerspectiveCatalogue'\n",
        # An import from the module that takes something else out of it: the reader of
        # the list is what makes a surface a chooser, not any export it happens to use.
        "import { paletteColour } from '@/composables/usePerspectiveCatalog'\n",
    )
    for text in does_not_read:
        assert not _imports(text, module), f"this is no import of the module:\n{text}"


def test_the_run_counts_where_the_run_ITSELF_is_taken():
    """The third shape is the RUN, and only the run.

    `composables/useInterceptionSeries.ts` also exports `markTerms`, an ordinary helper
    that marks words in a string. A surface taking that alone runs no interception, and
    until 2026-09-04 it satisfied the perspective rule with it -- the gate green over a
    prompt field that never went through a perspective at all.
    """
    module = "@/composables/useInterceptionSeries"
    reads = (
        "import { useInterceptionSeries } from '@/composables/useInterceptionSeries'\n",
        'import { useInterceptionSeries } from "@/composables/useInterceptionSeries"\n',
        # The spelling the three instruments of the group actually carry.
        "import {\n  markTerms,\n  useInterceptionSeries,\n  type SeriesRow,\n} from "
        "'@/composables/useInterceptionSeries'\n",
        'import {\n  useInterceptionSeries,\n} from "@/composables/useInterceptionSeries"\n',
        # The run under a local name: what a file calls it is its own business.
        "import { useInterceptionSeries as series } from "
        "'@/composables/useInterceptionSeries'\n",
    )
    for text in reads:
        assert _imports(text, module), f"an import of the run went unrecognised:\n{text}"

    does_not_read = (
        # The helper alone -- the shape this check exists for.
        "import { markTerms } from '@/composables/useInterceptionSeries'\n",
        "import {\n  markTerms,\n  perspectiveTerms,\n} from "
        "'@/composables/useInterceptionSeries'\n",
        # A type is not a run.
        "import type { SeriesRow } from '@/composables/useInterceptionSeries'\n",
        # The helper wearing the run's name. An alias renames what a file takes; it
        # does not change what it took, and a search for the bare name saw the run.
        "import { markTerms as useInterceptionSeries } from "
        "'@/composables/useInterceptionSeries'\n",
        # A type by that name, spelled inside the braces rather than before them.
        "import { type useInterceptionSeries } from "
        "'@/composables/useInterceptionSeries'\n",
    )
    for text in does_not_read:
        assert not _imports(text, module), f"this is not the run:\n{text}"


def test_the_canonical_parts_are_where_the_rules_say():
    """The rules point at files. If one is renamed, the gate must fail loudly here
    rather than quietly stop catching anything."""
    missing = [p for p in (
        "components/FlowRunButton.vue",
        "components/PromptExamples.vue",
        "components/MediaInputBox.vue",
        "components/InterceptionPresetOverlay.vue",
        "composables/usePerspectiveCatalog.ts",
        "assets/flow-stage.css",
        "assets/instrument-surface.css",
        "views/compare/model_comparison.vue",
    ) if not (SRC / p).exists()]
    assert not missing, (
        "this policy names parts that are no longer there -- update the rules, "
        "do not delete them:\n  " + "\n  ".join(missing)
    )


if __name__ == "__main__":
    # The pre-commit hook's entry point. It asks only about the commit in front of it;
    # the whole-tree question is the test above, which runs when someone runs the tests.
    import sys

    if "--staged" not in sys.argv:
        raise SystemExit("usage: test_element_structure_policy.py --staged  (or run pytest)")
    try:
        bad = _staged_offenders()
    except Exception as e:                                   # noqa: BLE001
        # A gate that cannot read the commit says so and steps aside.
        print(f"element-structure gate could not read the staged commit ({e}); "
              f"letting it through", file=sys.stderr)
        raise SystemExit(0)
    if bad:
        print("\nCOMMIT BLOCKED -- an element structure exists once:\n  "
              + "\n  ".join(bad)
              + "\n\nRead docs/ELEMENT_STRUCTURE_REGISTRY.md and use what is there.\n"
                "If a second implementation genuinely has to exist, that is a\n"
                "decision recorded in the commit message, not a --no-verify.\n",
                file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)
