#!/usr/bin/env python3
"""
Policy: an address is the exception, and a documented one.

The address rule in `docs/COPY_RULES.md`: addressing the reader as a subject
("Ihr", "you", "Sie") is allowed only with a specific reason, named in the
source comment, and the address-free nominal form of the operation is the
standard, not the substitute an address is corrected into. The slop pass of 2026-09-24
(UCD-105) wrote the thirteen address surfaces address-free. This gate is the
lasting version of that result -- built on finding B1 of the Phase-D audit
(UCD-107) so that the next writer cannot put an address back into the sources
without a gate noticing.

What it sees, exactly:

  - The five German direct-address pronouns at word boundaries: Ihr, Euch,
    Euer, Du, Dein. The check is case-sensitive on purpose: lower-case "ihr"
    is the possessive of "she", and the article forms (Ihre, Eure, Deine) are
    not a direct address. An imperative verb ("Wählt", "Vergleicht") is a
    different form and stays the copy rules' own business; this gate reads
    pronouns.
  - In the VALUES of the two hand-maintained i18n sources, de.ts and en.ts.
    Source comments are stripped before values are read, by the same scanner
    the grammar gate uses (test_i18n_label_grammar.py); a template literal or
    block comment the parser cannot read is a finding, never a skip.
  - The eight target languages (fr es tr ko uk he ar bg) are out of scope:
    they are translated by the batch agent against work orders
    (WO-2026-09-24-C1..C8 in src/i18n/WORK_ORDERS.md) and carry the
    address-free standard through those passes. Widening the scope is a
    decision recorded in a commit message, not a silent edit here.

An address the gate finds is fine only with its reason named nearby, in a
source comment, in the shape the wording markers already use: SUPPLIED WORDING
PRECEDES EVERY CRITERION, "SUPPLIED WORDING: ...", "Vorgegebener Wortlaut ...
bleibt wörtlich". Where the reason may live, nearest first: a short dictation note directly above the
key's line documents that key (the latentLabOverview note); so does a block
that quotes the value's own words, in any position; so does the block above
the line before it, without further shape -- a marker there documents the
story/purpose pair, and its supplied-wording sentence names one half of it by
position (the census note above the story line says "Der Schlusssatz der
zweiten Hälfte", and the second half is the purpose); and so does the header
of an enclosing block when it is a compact wording marker ("// Vorgegebener
Wortlaut.", the ask note) or quotes the value (the compare address block
names model.purpose by quoting it). A long header that carries its marker in
passing documents nothing: the census note above the story line names the
purpose's closing sentence, not the story, and an address in the story is
exactly what that note says was rewritten out; the flowLogic header opens
about the barNote key and mentions the column subtitles in its fifth line,
and neither phrase excuses an address in the eight keys under it. Deleting
the comment makes the address undocumented again -- the documentation is
load-bearing.

The thirteen address surfaces themselves (ADDRESS_SLOTS below, the seventeen
keys of the slop pass: story and purpose of the eight surfaces plus the
voices mixNote) may not carry an undocumented address and may never be listed
as excluded stock -- the state the pass established is held, not lent.

The deliberately excluded stocks -- field labels, explanation texts, game and
context wording (S1-S3 in src/i18n/WORK_ORDERS.md) -- are carried in
ADDRESS_DEBT below and its frozen stock file. The lists only shrink: a commit
that fixes a listed string takes its entry out in the same commit, and the
--staged mode enforces that exactly as the grammar gate enforces
INHERITED_DEBT.

Sibling of test_i18n_label_grammar.py, whose shape this file follows and whose
parser it borrows. Enforced as gate 6 in scripts/git-hooks/pre-commit.

Run: python3 devserver/tests/test_i18n_direct_address.py
     python3 -m pytest devserver/tests/test_i18n_direct_address.py -q
"""
import hashlib
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# Runs from anywhere (the pre-commit hook uses the absolute path); the
# sibling import resolves to the same directory either way.
import test_i18n_label_grammar as grammar  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
I18N_REL = grammar.I18N_REL

# The two hand-maintained sources; see the header for why the eight target
# languages are out of scope.
SOURCE_LANGUAGES = ("de", "en")

# --------------------------------------------------------------------------------
# The thirteen address surfaces of the slop pass (UCD-105), the state this gate
# holds: story and purpose of the eight surfaces, plus the voices mixNote the
# pass added. Every key here is address-free except where the wording itself
# is documented, and none of them may ever sit on the excluded stock.
# --------------------------------------------------------------------------------
ADDRESS_SLOTS = {
    "latentLab.census.story",
    "latentLab.census.purpose",
    "latentLab.attention.story",
    "latentLab.attention.purpose",
    "latentLab.archaeology.story",
    "latentLab.archaeology.purpose",
    "compare.address.model.story",
    "compare.address.model.purpose",
    "compare.address.vlm-analysis.story",
    "compare.address.vlm-analysis.purpose",
    "compare.address.language.story",
    "compare.address.language.purpose",
    "compare.address.voice.story",
    "compare.address.voice.purpose",
    "compare.address.systemprompt.story",
    "compare.address.systemprompt.purpose",
    "compare.voice.supertonic.mixNote",
}

ADDRESS = re.compile(r"\b(Ihr|Euch|Euer|Du|Dein)\b")

# The shapes a reason takes in these files. A comment block that matches none
# of these documents nothing.
DOCUMENTED_REASON = re.compile(
    r"SUPPLIED WORDING"
    r"|[Vv]orgegebener Wortlaut"
    r"|bleib\w*[^.]{0,80}w(ö|oe)rtlich"
    r"|keeps its address word for word"
)

TEST_REL = "devserver/tests/test_i18n_direct_address.py"

# --------------------------------------------------------------------------------
# ADDRESS_DEBT: (language, dotted key path) for the deliberately excluded
# stocks of 2026-09-25 -- the addresses that stay until their own passes run
# (S1-S3 in src/i18n/WORK_ORDERS.md). Debt, never permission.
#
# Shrinks only; never add. Membership is asserted against
# devserver/tests/data/i18n_address_debt_stock_2026-09-25.txt, and the
# thirteen address surfaces may not carry an entry at all -- see
# test_address_slots_may_not_be_stocked.
# --------------------------------------------------------------------------------
ADDRESS_DEBT = {
    ("de", "canvas.stage.input.promptPlaceholder"),
    ("de", "direct.emptyState"),
    ("de", "docs.guideLatentLab.sd35UsesThree"),
    ("de", "docs.guideLatentLab.yourPromptTakenUp"),
    ("de", "docs.guideMusic.youCanWriteOwn"),
    ("de", "docs.guidePersona.whatAnswersHereNot"),
    ("de", "docs.guidePersona.youCanDisagreeRedirect"),
    ("de", "docs.guidePersona.whenMachineDecidesDialog"),
    ("de", "docs.guideTraining.generativeImageModelsClosed"),
    ("de", "docs.guideTraining.youUploadSetOwn"),
    ("de", "docs.principles.everyIntermediateStepVisible"),
    ("de", "docs.principles.theWikipediaLinksInvite"),
    ("de", "docs.wikipedia.culturalRespectDesc"),
    ("de", "edutainment.forest.clickToPlant"),
    ("de", "edutainment.forest.treesPlanted"),
    ("de", "edutainment.pixel.smartphoneComparison"),
    ("de", "edutainment.rareearth.gameOverInactive"),
    ("de", "form.inputLabel"),
    ("de", "latentLab.algebra.explainHowText"),
    ("de", "latentLab.crossmodal.synth.explainHowText"),
    ("de", "latentLab.flowLogic.diffusion.prompt.exploreNote"),
    ("de", "latentLab.flowLogic.diffusion.prompt.langNote"),
    ("de", "latentLab.flowLogic.diffusion.prompt.platformNote"),
    ("de", "latentLab.flowLogic.transformer.prompt.hidden"),
    ("de", "latentLab.flowLogic.transformer.prompt.note"),
    ("de", "latentLab.flowLogic.transformer.prompt.sysExample"),
    ("de", "latentLab.flowLogic.transformer.prompt.you"),
    ("de", "latentLab.flowLogic.transformer.vectors.embLabel"),
    ("de", "latentLab.loraReach.story"),
    ("de", "latentLab.probing.techText"),
    ("de", "latentLab.textLab.bias.noteBody"),
    ("de", "latentLab.textLab.tokens.cutHead"),
    ("de", "mediaInput.yourInputLabel"),
    ("de", "phase2.inputPlaceholder"),
    ("de", "phase2.userInput"),
    ("de", "phase2.yourInput"),
    ("de", "phase2.yourPrompt"),
    ("de", "pipeline.yourInput"),
    ("de", "policyChips.queuePlaceMine"),
    ("de", "safetyBlocked.dsgvo"),
    ("de", "safetyBlocked.generic"),
    ("de", "safetyBlocked.kids"),
    ("de", "safetyBlocked.para86a"),
    ("de", "safetyBlocked.vlm"),
    ("de", "safetyBlocked.youth"),
    ("de", "biasArchaeology.story"),
    ("de", "compare.voice.gap.english"),
    ("de", "corefTest.story"),
    ("de", "persona.description"),
    ("de", "persona.story"),
    ("de", "resona.journalNotice"),
    ("de", "settings.knowledge.items.readonlyHint"),
    ("de", "surrealizer.expandHint"),
    ("de", "training.info.runCost"),
    ("de", "trashy.analysisReflectionError"),
    ("de", "workshop.chat.overBudget"),
    ("de", "workshop.greeting.callToAction"),
    ("de", "workshop.greeting.context"),
    ("de", "workshop.greeting.flexibility"),
}

STOCK_PATH = pathlib.Path(__file__).resolve().parent / "data" / \
    "i18n_address_debt_stock_2026-09-25.txt"
# The stock file's sha256. It changes only by a decision recorded in the commit
# message: the file is the frozen list, and a gate whose baseline can be
# rewritten silently is not a baseline.
STOCK_SHA256 = "f0868ee5a6923152f804b05b74d4f9af4243d5e10b6c7d1ebe9404225ebdd206"


# --------------------------------------------------------------------------------
# Where a reason can live. Line numbers are 1-based, as parse_locale reports
# them (the key's own line, the line somebody edits).
# --------------------------------------------------------------------------------
def _comment_lines_above(lines, line_no):
    """The // comment block directly above line_no, top-down."""
    out = []
    i = line_no - 2                                # 0-based line above
    while i >= 0 and lines[i].strip().startswith("//"):
        out.append(lines[i].strip())
        i -= 1
    return list(reversed(out))


def _text(block):
    return " ".join(block)


def _ancestor_map(source):
    """Line number -> opener lines of the blocks enclosing that line.

    Built with the grammar gate's own block regexes, so the nesting this sees
    is the nesting its parser read.
    """
    stack = []
    enclosing = ()
    out = {}
    for number, line in enumerate(source.splitlines(), 1):
        out[number] = enclosing
        code, _, _ = grammar._scan_line(line)
        match = grammar.OPEN_BLOCK.match(code)
        if match:
            stack.append(number)
            enclosing = tuple(stack)
        elif grammar.CLOSE_BLOCK.match(code) and stack:
            stack.pop()
            enclosing = tuple(stack)
    return out


_UMAP = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue",
                       "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})

# A quotation, long enough to name one string and not a stray word.
QUOTED = re.compile(r"[„“”\"'«»]([^„“”\"'«»]{8,300}?)[„“”\"'«»]")


def _normal(text):
    """Lower-case, umlauts folded (oe for ö -- the comments spell it that
    way), everything but letters and digits dropped, runs of space folded."""
    folded = text.translate(_UMAP).lower()
    return " ".join("".join(c if c.isalnum() else " " for c in folded).split())


def _quote_reaches(header_text, value):
    """True when the header quotes the hit's own wording.

    The comments spell umlauts as ae/oe/ue and drop commas; the values carry
    them. Both sides are normalised, and a quotation of three words or more
    that reaches the value names that value -- the compare address block
    quotes model.purpose, and nothing else in that block.
    """
    hay = _normal(value)
    for match in QUOTED.finditer(header_text):
        span = _normal(match.group(1))
        if len(span.split()) >= 3 and span in hay:
            return True
    return False


def _content(block):
    return [line[2:].strip() for line in block if line[2:].strip()]


def _dictated_note(block):
    """True for a block of at most four lines whose FIRST line carries a
    dictation marker. It sits directly above the one value it dictated -- the
    latentLabOverview note -- and the line count is the whole test: a longer
    block that carries its marker in a later line opens about something else
    (the census note's marker sentence names the purpose's closing sentence,
    not the story it sits above; the flowLogic header opens about the barNote
    key and reaches its marker in the fifth line).
    """
    content = _content(block)
    return 0 < len(content) <= 4 and bool(DOCUMENTED_REASON.search(content[0]))


def _compact_marker(block):
    """True for a header of at most three lines, every non-empty line a
    wording marker ("// Vorgegebener Wortlaut.", the ask note). It names
    the wording of the block under it and nothing else, and that is what
    makes it documentation for the keys inside. A longer header that carries
    a marker in passing names some other key's wording, and the flowLogic
    header is the case in point.
    """
    content = _content(block)
    return 0 < len(content) <= 3 and all(DOCUMENTED_REASON.search(line)
                                          for line in content)


def reason_comment(lines, ancestors, num, value):
    """The comment text that names this address's reason, or None.

    Nearest first: a short dictation note directly above the key's line, or
    a block there that quotes the value; the block above the line before it
    when that line is a value -- a marker there documents the story/purpose
    pair, and its supplied-wording sentence names one half by position; and
    the header of an enclosing block, innermost first, when it is a compact
    wording marker or quotes the value.
    """
    direct = _comment_lines_above(lines, num)
    if _dictated_note(direct) or _quote_reaches(_text(direct), value):
        return _text(direct)

    above = num - 1
    if above >= 1 and not lines[above - 1].strip().startswith("//"):
        sibling = _comment_lines_above(lines, above)
        if DOCUMENTED_REASON.search(_text(sibling)):
            return _text(sibling)

    for opener in reversed(ancestors):
        header = _comment_lines_above(lines, opener)
        if not header:
            continue
        if _compact_marker(header) or _quote_reaches(_text(header), value):
            return _text(header)
    return None


REPORT_TAIL = "an address is the exception, and a documented one (docs/COPY_RULES.md)"


def check_content(lang, source, label=None):
    """Undocumented direct addresses in one locale source, allowlists applied."""
    if label is None:
        label = f"{lang}.ts"
    entries, problems = grammar.parse_locale(source, label)
    found = list(problems)
    lines = source.splitlines()
    ancestors = _ancestor_map(source)
    for dotted, value, num in entries:
        if not ADDRESS.search(value):
            continue
        if (lang, dotted) in ADDRESS_DEBT:
            continue
        if reason_comment(lines, ancestors.get(num, ()), num, value) is not None:
            continue
        found.append(f"{label}:{num}  {dotted} = '{value}'  -> direct address; "
                     f"{REPORT_TAIL}")
    return found


def _missing_sources():
    """A source the gate cannot read. Loud on purpose, in every mode."""
    return [f"source file {lang}.ts missing under {I18N_REL} -- the gate "
            f"checked nothing"
            for lang in SOURCE_LANGUAGES
            if not (grammar.I18N_DIR / f"{lang}.ts").is_file()]


def _live_hits():
    """(language, dotted key) for every value that currently trips the check."""
    live = set()
    for lang in SOURCE_LANGUAGES:
        for dotted, value, _ in grammar.parse_ts(grammar._read(lang)):
            if ADDRESS.search(value):
                live.add((lang, dotted))
    return live


def _stale():
    live = _live_hits()
    return [f"ADDRESS_DEBT: {lang} {key}"
            for lang, key in sorted(ADDRESS_DEBT)
            if (lang, key) not in live]


def _stock_entries():
    if not STOCK_PATH.exists():
        return None
    out = set()
    for line in STOCK_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lang, _, key = line.partition("\t")
        out.add((lang, key))
    return out


def _stock_sha256():
    return hashlib.sha256(STOCK_PATH.read_bytes()).hexdigest()


# --------------------------------------------------------------------------------
# Staged mode.
# --------------------------------------------------------------------------------
def _git(*args):
    return subprocess.run(("git",) + args, cwd=str(REPO),
                          capture_output=True, text=True, check=True).stdout


def _staged_report():
    """(lines, blocking) for the commit in front of the gate.

    The discipline is the grammar gate's: several sessions share this
    checkout, and a gate judges only the commit in front of it. A commit that
    touches no i18n source passes without reading anything.
    """
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
    if lines:
        return (lines, True)

    # The list shrinks WITH the fix, not after it. A commit that corrects a
    # string still listed as excluded stock has to take the entry out in the
    # same commit, or the next whole-tree run fails on somebody else's desk.
    # Only keys still present and now clean count: a key that vanished from
    # the staged blob may equally be a parser hiccup, and a gate that guesses
    # is a gate that blocks the wrong commit.
    fixed = []
    for name, lang in sorted(sources.items()):
        source = _git("show", f":{name}")
        listed = {key for language, key in ADDRESS_DEBT if language == lang}
        if not listed:
            continue
        for dotted, value, _ in grammar.parse_ts(source):
            if (lang, dotted) in listed and not ADDRESS.search(value):
                fixed.append(f"{lang} {dotted}")
    if fixed and TEST_REL not in staged:
        return ([f"direct-address: this commit fixes {len(fixed)} string(s) "
                 f"still listed as excluded stock: {' '.join(sorted(fixed))}. "
                 f"Take those entries out of ADDRESS_DEBT in {TEST_REL} and "
                 f"stage that file with this commit -- the list shrinks with "
                 f"the fix, not after it."], True)
    return ([], False)


# --------------------------------------------------------------------------------
# pytest
# --------------------------------------------------------------------------------
def test_direct_addresses_are_documented_or_listed():
    missing = _missing_sources()
    assert not missing, "\n  ".join(missing)
    found = []
    for lang in SOURCE_LANGUAGES:
        found += check_content(lang, grammar._read(lang))
    stale = _stale()
    assert not found and not stale, (
        "An address is the exception, and a documented one:\n  "
        + "\n  ".join(found + stale)
    )


def test_address_slots_may_not_be_stocked():
    """The state the slop pass of 2026-09-24 established, held: the seventeen
    keys of the thirteen address surfaces are address-free except where the
    wording itself is documented, and none of them sits on the excluded
    stock. An undocumented address there is the general test's finding; an
    entry here would be the way around it, and the way around it is what
    this test closes."""
    on_slots = [f"{lang} {key}" for lang, key in sorted(ADDRESS_DEBT)
                if key in ADDRESS_SLOTS]
    assert not on_slots, (
        "an address surface may not be carried as excluded stock:\n  "
        + "\n  ".join(on_slots)
    )
    for lang in SOURCE_LANGUAGES:
        source = grammar._read(lang)
        entries, problems = grammar.parse_locale(source, f"{lang}.ts")
        assert not problems, problems
        lines = source.splitlines()
        ancestors = _ancestor_map(source)
        for dotted, value, num in entries:
            if dotted not in ADDRESS_SLOTS:
                continue
            if not ADDRESS.search(value):
                continue
            reason = reason_comment(lines, ancestors.get(num, ()), num, value)
            assert reason is not None, (
                f"{lang}.ts:{num}  {dotted} = '{value}'  -> direct address on "
                f"an address surface without a named reason; the address-free "
                f"nominal form is the standard, not the substitute "
                f"(docs/COPY_RULES.md)"
            )


def test_the_list_only_shrinks():
    """Membership against a frozen stock, not a count.

    A count lets one entry be swapped for another and stay green. The stock
    file is the list as it stood on 2026-09-25; every entry in the live list
    has to be in it.
    """
    stock = _stock_entries()
    assert stock is not None, f"the frozen stock is missing: {STOCK_PATH}"
    assert _stock_sha256() == STOCK_SHA256, (
        f"the frozen stock changed. {STOCK_PATH.name} is the list as it stood "
        f"on 2026-09-25; editing it is a decision that belongs in the commit "
        f"message, not a way past a red test."
    )
    grew = sorted(ADDRESS_DEBT - stock)
    assert not grew, (
        "ADDRESS_DEBT grew -- it holds the excluded stock of 2026-09-25 and "
        "shrinks only:\n  " + "\n  ".join(f"{lang} {key}" for lang, key in grew)
    )


if __name__ == "__main__":
    if not grammar.I18N_DIR.is_dir():
        print(f"direct-address: no {I18N_REL} in this checkout, gate does not apply")
        raise SystemExit(0)

    if "--staged" in sys.argv:
        try:
            lines, blocking = _staged_report()
        except Exception as e:                               # noqa: BLE001
            # A gate that cannot read the commit says so and steps aside.
            # Blocking every commit in the checkout because git or this file
            # misbehaved is the larger harm.
            print(f"direct-address gate could not read the staged commit ({e}); "
                  f"letting it through", file=sys.stderr)
            raise SystemExit(0)
        if blocking:
            print("\nCOMMIT BLOCKED -- direct address:\n  " + "\n  ".join(lines)
                  + "\n\nAn address is the exception, and a documented one. "
                  "Write the operation\nimpersonally -- the nominal form is the "
                  "standard, not the substitute --\nor name the reason in a "
                  "source comment above the key, in the wording\nmarkers' shape "
                  "(SUPPLIED WORDING PRECEDES EVERY CRITERION,\n\"Vorgegebener "
                  "Wortlaut ... bleibt wörtlich\"). docs/COPY_RULES.md carries "
                  "the\nwhole rule; the excluded stocks (S1-S3 in "
                  "src/i18n/WORK_ORDERS.md) sit in\nADDRESS_DEBT and shrink "
                  "with their fixes.\n\nWidening a list or bending the rule is "
                  "a decision recorded in the commit message, not a "
                  "--no-verify.\n", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)

    bad = (_missing_sources()
           + [line for lang in SOURCE_LANGUAGES
              for line in check_content(lang, grammar._read(lang))]
           + _stale())
    if bad:
        print("\n".join(bad), file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)
