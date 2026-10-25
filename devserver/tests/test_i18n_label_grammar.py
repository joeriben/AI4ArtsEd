#!/usr/bin/env python3
"""
Policy: a label string is the noun of its key.

An informing label -- a rubric, field name, heading, card title, note title, tab, the
one-line subtitle under a tab name, tooltip, settings caption -- is a naming form. It
names the category of the content underneath it, and where the i18n key carries a noun,
that noun is the string: `promptLabel` -> "Prompt", `motivation` -> "Reason",
`summaryLabel` -> "Summary".

Two forms are forbidden in a label slot, and this file looks for exactly them:

  - The question title, open or closed, with or without a question mark. "What happens
    here", "Why this was offered", "How It Works", "Is the operation commutative". A
    question title carries an unwritten frame -- "[here you learn] what happens here" --
    while the slot holds the category of the answer.
  - The phrase with a relative clause or participle. "The prompt that made it",
    "Der Prompt, der es erzeugt hat". The article presupposes a referent nobody has
    introduced, and the clause narrates the surface instead of naming it.

THIS GATE IS A FLOOR, NOT THE RULE. It sees a trailing question mark, an initial
interrogative or auxiliary in any letter case, and an article followed by a relative
clause. A string it passes has not yet been judged: `docs/COPY_RULES.md`
carries the rest, including the noun-phrase that merely restates a question, the gerund
heading, and every criterion for explanatory prose.

Placeholders are out of scope by design, not by oversight. `docs/COPY_RULES.md` governs them -- a
placeholder invites input and may legitimately be a question -- and their keys carry no
label suffix, so nothing here reaches them.

A genuine question addressed to the user -- a confirm dialog, a reflection prompt -- is
content, not a label, and stays a question. Those live in ALLOWED, entry by entry.

Sibling of `test_no_model_literals.py`, whose shape this file follows: lists that only
shrink, a staged-only mode for the hook, a whole-tree mode for pytest. Enforced as
gate 5 in `scripts/git-hooks/pre-commit`.

Run: python3 devserver/tests/test_i18n_label_grammar.py
     python3 -m pytest devserver/tests/test_i18n_label_grammar.py -q
"""
import functools
import hashlib
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
I18N_DIR = REPO / "public" / "ai4artsed-frontend" / "src" / "i18n"
I18N_REL = "public/ai4artsed-frontend/src/i18n"

# A locale module is a .ts file in the i18n directory whose own stem is the object it
# exports: `export const uk = {`. index.ts exports SUPPORTED_LANGUAGES and the locale
# helpers, fails that test, and is therefore not a language.
#
# Discovered rather than written down. The platform gained four languages between the
# day this directory was laid out and the day this gate went up, and a hand-written list
# would have quietly covered six of ten. A discovered language with no word table below
# is a hard failure, never a pass -- see missing_word_tables().
LOCALE_EXPORT = re.compile(r"^export const (\w+)\s*=\s*\{", re.M)


@functools.lru_cache(maxsize=None)
def _read(lang: str) -> str:
    return (I18N_DIR / f"{lang}.ts").read_text(encoding="utf-8")


def _is_locale_source(stem: str, source: str) -> bool:
    match = LOCALE_EXPORT.search(source)
    return bool(match) and match.group(1) == stem


def discover_languages():
    """Every locale module in the working tree, in alphabetical order."""
    found = []
    if not I18N_DIR.is_dir():
        return ()
    for path in sorted(I18N_DIR.glob("*.ts")):
        if _is_locale_source(path.stem, _read(path.stem)):
            found.append(path.stem)
    return tuple(found)


LANGUAGES = discover_languages()

# --------------------------------------------------------------------------------
# Scope: which keys are label slots.
#
# The suffix is matched CASE-SENSITIVELY on the camel-case boundary, so that the word
# is a word of the key and not the tail of another one: `queueAhead` ends in the letters
# "head" and is not a heading. A key may also BE the lower-case word (`label`, `title`).
#
# A segment of five camel words or more is a sentence used as an identifier, not the
# name of a slot -- `bothClipEncodersReadTheCaption` is the caption's text, keyed by
# what it says. Every real label key in the tree is two or three words. The cap is here
# because the boundary rule alone puts that key in scope, and the string under it is
# prose that the checks would then read as a label.
#
# Everything outside this -- prose bodies, placeholders, messages, confirm texts, button
# captions -- is out of scope, because those slots legitimately carry sentences.
# --------------------------------------------------------------------------------
LABEL_SUFFIX = re.compile(r"(?:^|[a-z0-9_])(Label|Title|Head|Heading|Caption|Tooltip|Hint|Help)$")
LABEL_EXACT = {
    "label", "title", "head", "heading", "caption", "tooltip", "hint", "help",
    "short", "sub", "pick", "motivation", "apparatus", "noteTitle",
    "name", "surfaceSettings",
}
CAMEL_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")
MAX_CAMEL_WORDS = 4

# A gloss slot -- the hint under a field, a settings description, a tab subtitle. Rule
# 17 gives it one declarative sentence or a nominal description, so the article-plus-
# relative shape is the correct form there and not a finding: "the name it is saved
# under", "The transformer layer that receives the steering vector." A question is not,
# which is why question_mark, wh_initial and aux_initial still apply here.
GLOSS_SUFFIX = re.compile(r"(?:^|[a-z0-9_])(Hint|Help)$")
GLOSS_EXACT = {"hint", "help", "sub", "short"}


def is_gloss_key(dotted: str) -> bool:
    last = dotted.rsplit(".", 1)[-1]
    return last in GLOSS_EXACT or bool(GLOSS_SUFFIX.search(last))


def is_label_key(dotted: str) -> bool:
    last = dotted.rsplit(".", 1)[-1]
    if last in LABEL_EXACT:
        return True
    if not LABEL_SUFFIX.search(last):
        return False
    return len(CAMEL_WORD.findall(last)) <= MAX_CAMEL_WORDS


# --------------------------------------------------------------------------------
# The three shapes this gate can see.
#
# Anchored at the start and CASE-INSENSITIVE there. An earlier version matched only a
# capitalised interrogative, on the reasoning that a lower-case one is prose; it is not.
# `what made this` and `which models are compared` were live labels in en.ts, written
# lower-case because they sit under a heading, and the case-sensitive pattern walked
# past both.
#
# Korean carries no word boundary in the Latin sense -- a particle follows the
# interrogative directly, with no space between them -- so its list matches without one
# and over-reports rather than misses.
#
# Hebrew and Arabic do separate their words, but their interrogatives are two letters
# that also open ordinary words: mi ("who") opens mizug ("fusion") and meyatzer
# ("generates"), and the ma of ma dam ("as long as") is the ma of "what". Both therefore
# require the interrogative to BE the first word, and Arabic additionally refuses the ma
# that ma dam opens. Three correctly written labels were reported before that went in.
#
# Every other language keeps \b, so that "Wo" does not fire on "Worum", "Як" not on
# "Який", and "Как" not on "Както".
#
# Arabic leaves out the two interrogatives that double as ordinary words: min ("from",
# also "who") and ayy ("any", also "which"). A list that fires on every prepositional
# phrase is a list somebody switches off.
# --------------------------------------------------------------------------------
HE_AR_WORD_END = r"(?=\s|$|[?؟!.,:;،؛\-–—־\"'«»()\[\]])"

WH_INITIAL = {
    # How-to and What's new are ordinary UI nouns, not questions.
    "en": re.compile(r"^(?!How-to\b|What's new\b)"
                     r"(What|Why|How|Which|Where|When|Who|Whose|Whom)\b", re.I),
    "de": re.compile(
        r"^(Was|Warum|Wie viele|Wieviel|Wie|Welche[rsnm]?|Wo|Wann|Wer|Wessen"
        r"|Wem|Wen|Worum|Womit|Wozu|Wieso|Weshalb|Weswegen|Wodurch|Wohin|Woher"
        r"|Wofür|Worauf|Woran|Wovon|Woraus|Worin|Wonach|Inwiefern|Inwieweit)\b", re.I
    ),
    "fr": re.compile(
        r"^(Pourquoi|Comment|À quoi|Combien|Quoi|Que|Qu'|Quel|Quelle|Quels|Quelles"
        r"|Lequel|Laquelle|Lesquels|Lesquelles|Où|Quand|Qui|Ce que|Ce qui)\b", re.I
    ),
    "tr": re.compile(r"^(Neden|Niçin|Niye|Nasıl|Hangisi|Hangi|Kaç|Kimin|Kim"
                     r"|Nereden|Nereye|Nerede|Ne zaman|Ne)\b", re.I),
    "uk": re.compile(r"^(Що|Чому|Як|Який|Яка|Яке|Які|Де|Коли|Хто|Навіщо|Скільки"
                     r"|Куди|Звідки|Чий|Чия|Чиє|Кого|Кому)\b", re.I),
    "ko": re.compile(r"^(무엇|왜|어떻게|어떤|어느|어디|언제|누가|누구|무슨|얼마나|몇)"),
    "es": re.compile(
        r"^(Qué|Por qué|Cómo|Cuál|Cuáles|Cuánto|Cuánta|Cuántos|Cuántas"
        r"|Dónde|Cuándo|Quién|Quiénes|Lo que)\b", re.I
    ),
    "he": re.compile(
        r"^(מהו|מהי|מהם|מהן|מה|למה|מדוע|איך|כיצד|איזה|איזו|אילו|היכן|איפה"
        r"|מתי|מי|כמה|לאן|מאיפה|מהיכן)" + HE_AR_WORD_END
    ),
    "ar": re.compile(r"^(ما(?!\s*دام)|ماذا|لماذا|كيف|أين|متى|كم)" + HE_AR_WORD_END),
    "bg": re.compile(r"^(Какво|Защо|Как|Кой|Коя|Кое|Кои|Къде|Кога|Що|Колко"
                     r"|Откъде|Чий|Чия|Чие|Кого)\b", re.I),
}

# A closed question needs no interrogative and often carries no mark: "Is the operation
# commutative". Guarded by the same short-value test as definite_relative, because these
# words open ordinary sentences too ("Can be read as ...", "Ist der Lauf beendet, ...").
AUX_INITIAL = {
    # Do/Did/Have/Has/Had are left out on purpose: "Have a look", "Do not translate".
    "en": re.compile(r"^(Is|Are|Was|Were|Does|Can|Could|Will|Would|Should)\b"),
    "de": re.compile(r"^(Ist|Sind|War|Waren|Kann|Können|Wird|Werden|Soll|Sollen"
                     r"|Hat|Haben)\b"),
    "fr": re.compile(r"^(Est-ce|Peut-on|Faut-il)\b"),
    "es": re.compile(r"^(Es|Son|Puede|Pueden|Debe)\b"),
    "uk": re.compile(r"^Чи\b"),
    "bg": re.compile(r"^Дали\b"),
    "he": re.compile(r"^האם"),
    "ar": re.compile(r"^هل"),
}
# Turkish marks a yes/no question with an enclitic at the end, not a word at the front.
AUX_TRAILING = {
    "tr": re.compile(r"\b(mı|mi|mu|mü)\s*\??$", re.I),
}

# An article, one to three words, then a relative pronoun or a participle.
#
# APPLIES TO LABEL KEYS ONLY, never to a gloss key -- see is_gloss_key(). A gloss takes
# a nominal description, and "the name it is saved under" is that description, correctly
# written. The other three checks do run on gloss keys: a gloss is a sentence, never a
# question.
#
# Turkish, Ukrainian and Korean have no pattern here: the first two build the relative
# clause as a participle in front of the noun, with no article and no pronoun to anchor
# on, and Korean does the same. A pattern for them would have to parse, not match.
#
# Hebrew has none either. ha-NOUN she-WORD is equally the possessive ("ha-tekst
# shelkha" = "your text") and two ordinary nouns that happen to begin with those two
# letters ("heskem shimush" = "usage agreement"). Every shape that separated the real
# relative from those also cut real relatives, and a correct string reported is worse
# than a wrong one missed: this gate is a floor.
DEFINITE_RELATIVE = {
    "en": (
        re.compile(r"^(The|This|That|Your|Its|These|Those)(?: \S+){1,3} "
                   r"(that|which|who|whose|made|built|used|chosen|behind)\b", re.I),
        # The contact clause drops the relative pronoun entirely: "The image the model
        # made", "The prompt you sent".
        re.compile(r"^(The|This|That|Your|Its|These|Those) \S+ "
                   r"(the|a|an|my|its|this|that|these|those|you|we|they|it) \S+", re.I),
    ),
    "de": (
        re.compile(r"^(Der|Die|Das|Dieser|Diese|Dieses)(?: [^\s,.]+){1,3}, "
                   r"(der|die|das|den|dem|deren|dessen|welche[rsn]?)\b", re.I),
    ),
    "fr": (
        re.compile(r"^(?:(?:Le|La|Les) |L')\S+(?: \S+){0,2} (qui|que|qu')\b", re.I),
    ),
    "es": (
        re.compile(r"^(El|La|Los|Las)(?: \S+){1,3} (que|quien|cuyo|cuya)\b", re.I),
    ),
    "ar": (
        re.compile(r"^ال\S+ (الذي|التي|اللذان|اللتان|الذين|اللاتي)\b"),
    ),
    "bg": (
        re.compile(r"^\S+(ът|ят|та|то|те), (който|която|което|които)\b", re.I),
    ),
}

# "Ends with a question mark, in any language" means the mark that language writes.
# Arabic ends a question with U+061F, not with the ASCII one, so an ASCII-only test
# reads every Arabic question as a statement.
QUESTION_MARKS = ("?", "؟", "？")

# `A - B + C = ?` is a formula whose right-hand side is what the run produces. The
# question mark is the empty slot, not a question.
FORMULA_TAIL = re.compile(r"[=:]\s*\?$")

# A leading placeholder, quotation mark, dash, bullet or inverted question mark is
# packaging around the string, not its first word.
LEADING_STRIP = re.compile(r"^(?:\{[^{}]*\}|[\s\"“”„«»'\-–—•·*#¿؟]+)+")

# Below this length, and without a closing period, a value is a label and the
# article-plus-relative and auxiliary shapes mean what they look like. Above it the same
# words open ordinary prose -- "This means that the run stopped early.", "Diese Rolle
# schreibt Programmcode, der im Browser läuft." -- and the checks would report the gloss
# slots the rule deliberately allows to be sentences.
SHORT_VALUE_CHARS = 80


def _is_short_label(text: str) -> bool:
    return len(text) < SHORT_VALUE_CHARS and not text.endswith(".")


def check_value(lang: str, value: str, dotted: str = None):
    """The name of the first check the value trips, or None.

    `dotted` is the key the value sits under. Without it every check runs; with it, a
    gloss key is exempt from definite_relative.
    """
    text = LEADING_STRIP.sub("", value.strip()).strip()
    if not text:
        return None
    if text.endswith(QUESTION_MARKS) and not FORMULA_TAIL.search(text):
        return "question_mark"
    pattern = WH_INITIAL.get(lang)
    if pattern is not None and pattern.match(text):
        return "wh_initial"
    if _is_short_label(text):
        pattern = AUX_INITIAL.get(lang)
        if pattern is not None and pattern.match(text):
            return "aux_initial"
        pattern = AUX_TRAILING.get(lang)
        if pattern is not None and pattern.search(text):
            return "aux_initial"
        if dotted is None or not is_gloss_key(dotted):
            for pattern in DEFINITE_RELATIVE.get(lang, ()):
                if pattern.match(text):
                    return "definite_relative"
    return None


# --------------------------------------------------------------------------------
# ALLOWED: dotted key paths, language-independent.
#
# Two kinds of entry, and only these two:
#   - A genuine question to the user. The slot addresses the reader and expects an
#     answer, so it is a question in every language.
#   - Wording the user supplied. `docs/COPY_RULES.md`: supplied wording precedes every
#     criterion, and is used verbatim even where a criterion would reject it.
#
# The list may shrink. It must not grow: a question written into a label slot after
# 2026-09-04 is a rewrite, never an entry here.
# --------------------------------------------------------------------------------
ALLOWED = {
    # A confirm dialog. The user is asked whether to delete the course, and answers.
    "educator.deleteCourseTitle",
    # SUPPLIED WORDING (see the comment above the key in en.ts).
    # Supplied wording precedes every criterion (docs/COPY_RULES.md).
    "latentLab.textLab.repeng.strengthLabel",
}

# The frozen stock of 2026-09-04. ALLOWED is asserted to be a subset of it, so the list
# can lose entries and never gain them. Changing this tuple is a decision recorded in
# the commit message, not a way past a red test.
ALLOWED_STOCK = (
    "educator.deleteCourseTitle",
    "training.tryout.hint",
    "latentLab.textLab.repeng.strengthLabel",
)

# --------------------------------------------------------------------------------
# INHERITED_DEBT: (language, dotted key path) for what was already in the tree when
# this gate went up.
#
# Two kinds sit here, both of them debt and neither of them permission:
#   - The non-English stock. Those files still carry the old forms; they are corrected
#     by the i18n-translator batch, one language at a time, and every entry it fixes
#     comes off this list in the same commit -- the gate blocks a commit that fixes a
#     string and leaves its line standing.
#   - English keys nothing reads. Deleting a dead key is a separate decision from
#     rewriting a live one, so they are held rather than rewritten blind.
#
# `latentLab.imageLab.tabs.census.short` is dead by absence of the census ITEM from the
# image group in views/latent_lab.vue -- not by absence of a reader. The dynamic prefix
# that file builds is alive and reaches its siblings; this one has no item left to name.
#
# Shrinks only; never add. Membership is enforced against
# devserver/tests/data/i18n_label_debt_stock_2026-09-04.txt.
# --------------------------------------------------------------------------------
INHERITED_DEBT = {
    # --- English: keys nothing under public/ai4artsed-frontend/src reads ---
    # The explain-panel titles of six instruments and the crossmodal hints. The panels
    # they belonged to are gone from the components; the strings stayed behind. Deleting
    # a dead key is a separate decision from rewriting a live one, so they are held here
    # rather than rewritten blind.
    #
    # Checked one by one: no `t('<path>')`, and no dynamic prefix that lands on the last
    # segment. `surrealizer.techTitle` and `latentLab.archaeology.headerTitle` read as
    # live to a grep on the last segment alone -- `techTitle` exists under
    # five Latent Lab instruments, and six other instruments have a
    # `headerTitle` -- but neither of those two is read by the view that would read it.
    # `latentLab.imageLab.tabs.census.short` is the case described above this list.
    #
    # Every LIVE English label was rewritten on 2026-09-04. None is listed here.
    ("en", "latentLab.algebra.explainHowTitle"),
    ("en", "latentLab.algebra.explainReadTitle"),
    ("en", "latentLab.algebra.explainWhatTitle"),
    ("en", "latentLab.archaeology.explainHowTitle"),
    ("en", "latentLab.archaeology.explainWhatTitle"),
    ("en", "latentLab.archaeology.headerTitle"),
    ("en", "latentLab.attention.explainHowTitle"),
    ("en", "latentLab.attention.explainReadTitle"),
    ("en", "latentLab.attention.explainWhatTitle"),
    ("en", "latentLab.composable.explainHowTitle"),
    ("en", "latentLab.composable.explainWhatTitle"),
    ("en", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("en", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("en", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("en", "latentLab.crossmodal.guidance.lambdaHint"),
    ("en", "latentLab.crossmodal.guidance.warmupHint"),
    ("en", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("en", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("en", "latentLab.crossmodal.synth.explainHowTitle"),
    ("en", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("en", "latentLab.imageLab.tabs.census.short"),
    ("en", "latentLab.probing.explainHowTitle"),
    ("en", "latentLab.probing.explainReadTitle"),
    ("en", "latentLab.probing.explainWhatTitle"),
    ("en", "latentLab.textLab.repeng.explainHowTitle"),
    ("en", "latentLab.textLab.repeng.explainWhatTitle"),
    ("en", "latentLab.textLab.repeng.targetLayerHint"),

    # --- The nine translations ---
    # Their files still carry the old forms. The i18n-translator batch corrects them one
    # language at a time, and every entry it fixes comes off this list in the same
    # commit -- the gate blocks a commit that fixes a string and leaves its line.

    # ar (44)
    ("ar", "latentLab.algebra.explainHowTitle"),
    ("ar", "latentLab.algebra.explainReadTitle"),
    ("ar", "latentLab.algebra.explainWhatTitle"),
    ("ar", "latentLab.archaeology.explainHowTitle"),
    ("ar", "latentLab.archaeology.explainWhatTitle"),
    ("ar", "latentLab.archaeology.headerTitle"),
    ("ar", "latentLab.attention.explainHowTitle"),
    ("ar", "latentLab.attention.explainReadTitle"),
    ("ar", "latentLab.attention.explainWhatTitle"),
    ("ar", "latentLab.composable.explainHowTitle"),
    ("ar", "latentLab.composable.explainWhatTitle"),
    ("ar", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("ar", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("ar", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("ar", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("ar", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("ar", "latentLab.crossmodal.synth.explainHowTitle"),
    ("ar", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("ar", "latentLab.probing.explainHowTitle"),
    ("ar", "latentLab.probing.explainReadTitle"),
    ("ar", "latentLab.probing.explainWhatTitle"),
    ("ar", "latentLab.textLab.repeng.explainHowTitle"),
    ("ar", "latentLab.textLab.repeng.explainWhatTitle"),

    # bg (50)
    ("bg", "latentLab.algebra.explainHowTitle"),
    ("bg", "latentLab.algebra.explainReadTitle"),
    ("bg", "latentLab.algebra.explainWhatTitle"),
    ("bg", "latentLab.archaeology.explainHowTitle"),
    ("bg", "latentLab.archaeology.explainWhatTitle"),
    ("bg", "latentLab.archaeology.headerTitle"),
    ("bg", "latentLab.attention.explainHowTitle"),
    ("bg", "latentLab.attention.explainReadTitle"),
    ("bg", "latentLab.attention.explainWhatTitle"),
    ("bg", "latentLab.composable.explainHowTitle"),
    ("bg", "latentLab.composable.explainWhatTitle"),
    ("bg", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("bg", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("bg", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("bg", "latentLab.crossmodal.guidance.lambdaHint"),
    ("bg", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("bg", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("bg", "latentLab.crossmodal.synth.explainHowTitle"),
    ("bg", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("bg", "latentLab.probing.explainHowTitle"),
    ("bg", "latentLab.probing.explainReadTitle"),
    ("bg", "latentLab.probing.explainWhatTitle"),
    ("bg", "latentLab.textLab.repeng.explainHowTitle"),
    ("bg", "latentLab.textLab.repeng.explainWhatTitle"),
    ("bg", "latentLab.textLab.repeng.targetLayerHint"),

    # de (56)
    ("de", "latentLab.algebra.explainHowTitle"),
    ("de", "latentLab.algebra.explainReadTitle"),
    ("de", "latentLab.algebra.explainWhatTitle"),
    ("de", "latentLab.archaeology.explainHowTitle"),
    ("de", "latentLab.archaeology.explainWhatTitle"),
    ("de", "latentLab.archaeology.headerTitle"),
    ("de", "latentLab.attention.explainHowTitle"),
    ("de", "latentLab.attention.explainReadTitle"),
    ("de", "latentLab.attention.explainWhatTitle"),
    ("de", "latentLab.composable.explainHowTitle"),
    ("de", "latentLab.composable.explainWhatTitle"),
    ("de", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("de", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("de", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("de", "latentLab.crossmodal.guidance.lambdaHint"),
    ("de", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("de", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("de", "latentLab.crossmodal.synth.explainHowTitle"),
    ("de", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("de", "latentLab.probing.explainHowTitle"),
    ("de", "latentLab.probing.explainReadTitle"),
    ("de", "latentLab.probing.explainWhatTitle"),
    ("de", "latentLab.textLab.repeng.explainHowTitle"),
    ("de", "latentLab.textLab.repeng.explainWhatTitle"),
    ("de", "latentLab.textLab.repeng.targetLayerHint"),

    # es (50)
    ("es", "latentLab.algebra.explainHowTitle"),
    ("es", "latentLab.algebra.explainReadTitle"),
    ("es", "latentLab.algebra.explainWhatTitle"),
    ("es", "latentLab.archaeology.explainHowTitle"),
    ("es", "latentLab.archaeology.explainWhatTitle"),
    ("es", "latentLab.archaeology.headerTitle"),
    ("es", "latentLab.attention.explainHowTitle"),
    ("es", "latentLab.attention.explainReadTitle"),
    ("es", "latentLab.attention.explainWhatTitle"),
    ("es", "latentLab.composable.explainHowTitle"),
    ("es", "latentLab.composable.explainWhatTitle"),
    ("es", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("es", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("es", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("es", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("es", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("es", "latentLab.crossmodal.synth.explainHowTitle"),
    ("es", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("es", "latentLab.probing.explainHowTitle"),
    ("es", "latentLab.probing.explainReadTitle"),
    ("es", "latentLab.probing.explainWhatTitle"),
    ("es", "latentLab.textLab.repeng.explainHowTitle"),
    ("es", "latentLab.textLab.repeng.explainWhatTitle"),
    ("es", "latentLab.textLab.repeng.targetLayerHint"),

    # fr (51)
    ("fr", "latentLab.algebra.explainHowTitle"),
    ("fr", "latentLab.algebra.explainReadTitle"),
    ("fr", "latentLab.algebra.explainWhatTitle"),
    ("fr", "latentLab.archaeology.explainHowTitle"),
    ("fr", "latentLab.archaeology.explainWhatTitle"),
    ("fr", "latentLab.archaeology.headerTitle"),
    ("fr", "latentLab.attention.explainHowTitle"),
    ("fr", "latentLab.attention.explainReadTitle"),
    ("fr", "latentLab.attention.explainWhatTitle"),
    ("fr", "latentLab.composable.explainHowTitle"),
    ("fr", "latentLab.composable.explainWhatTitle"),
    ("fr", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("fr", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("fr", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("fr", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("fr", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("fr", "latentLab.crossmodal.synth.explainHowTitle"),
    ("fr", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("fr", "latentLab.probing.explainHowTitle"),
    ("fr", "latentLab.probing.explainReadTitle"),
    ("fr", "latentLab.probing.explainWhatTitle"),
    ("fr", "latentLab.textLab.repeng.explainHowTitle"),
    ("fr", "latentLab.textLab.repeng.explainWhatTitle"),
    ("fr", "latentLab.textLab.repeng.targetLayerHint"),

    # he (49)
    ("he", "latentLab.algebra.explainHowTitle"),
    ("he", "latentLab.algebra.explainReadTitle"),
    ("he", "latentLab.algebra.explainWhatTitle"),
    ("he", "latentLab.archaeology.explainHowTitle"),
    ("he", "latentLab.archaeology.explainWhatTitle"),
    ("he", "latentLab.archaeology.headerTitle"),
    ("he", "latentLab.attention.explainHowTitle"),
    ("he", "latentLab.attention.explainReadTitle"),
    ("he", "latentLab.attention.explainWhatTitle"),
    ("he", "latentLab.composable.explainHowTitle"),
    ("he", "latentLab.composable.explainWhatTitle"),
    ("he", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("he", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("he", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("he", "latentLab.crossmodal.guidance.lambdaHint"),
    ("he", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("he", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("he", "latentLab.crossmodal.synth.explainHowTitle"),
    ("he", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("he", "latentLab.probing.explainHowTitle"),
    ("he", "latentLab.probing.explainReadTitle"),
    ("he", "latentLab.probing.explainWhatTitle"),
    ("he", "latentLab.textLab.repeng.explainHowTitle"),
    ("he", "latentLab.textLab.repeng.explainWhatTitle"),
    ("he", "latentLab.textLab.repeng.targetLayerHint"),

    # ko (34)
    ("ko", "latentLab.algebra.explainHowTitle"),
    ("ko", "latentLab.algebra.explainReadTitle"),
    ("ko", "latentLab.algebra.explainWhatTitle"),
    ("ko", "latentLab.archaeology.explainHowTitle"),
    ("ko", "latentLab.archaeology.explainWhatTitle"),
    ("ko", "latentLab.archaeology.headerTitle"),
    ("ko", "latentLab.attention.explainHowTitle"),
    ("ko", "latentLab.attention.explainReadTitle"),
    ("ko", "latentLab.attention.explainWhatTitle"),
    ("ko", "latentLab.composable.explainHowTitle"),
    ("ko", "latentLab.composable.explainWhatTitle"),
    ("ko", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("ko", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("ko", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("ko", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("ko", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("ko", "latentLab.crossmodal.synth.explainHowTitle"),
    ("ko", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("ko", "latentLab.probing.explainHowTitle"),
    ("ko", "latentLab.probing.explainReadTitle"),
    ("ko", "latentLab.probing.explainWhatTitle"),
    ("ko", "latentLab.textLab.repeng.explainHowTitle"),
    ("ko", "latentLab.textLab.repeng.explainWhatTitle"),
    ("ko", "latentLab.textLab.repeng.targetLayerHint"),

    # tr (33)
    ("tr", "latentLab.algebra.explainHowTitle"),
    ("tr", "latentLab.algebra.explainReadTitle"),
    ("tr", "latentLab.algebra.explainWhatTitle"),
    ("tr", "latentLab.archaeology.explainHowTitle"),
    ("tr", "latentLab.archaeology.explainWhatTitle"),
    ("tr", "latentLab.archaeology.headerTitle"),
    ("tr", "latentLab.attention.explainHowTitle"),
    ("tr", "latentLab.attention.explainReadTitle"),
    ("tr", "latentLab.attention.explainWhatTitle"),
    ("tr", "latentLab.composable.explainHowTitle"),
    ("tr", "latentLab.composable.explainWhatTitle"),
    ("tr", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("tr", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("tr", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("tr", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("tr", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("tr", "latentLab.crossmodal.synth.explainHowTitle"),
    ("tr", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("tr", "latentLab.probing.explainHowTitle"),
    ("tr", "latentLab.probing.explainReadTitle"),
    ("tr", "latentLab.probing.explainWhatTitle"),
    ("tr", "latentLab.textLab.repeng.explainHowTitle"),
    ("tr", "latentLab.textLab.repeng.explainWhatTitle"),

    # uk (49)
    ("uk", "latentLab.algebra.explainHowTitle"),
    ("uk", "latentLab.algebra.explainReadTitle"),
    ("uk", "latentLab.algebra.explainWhatTitle"),
    ("uk", "latentLab.archaeology.explainHowTitle"),
    ("uk", "latentLab.archaeology.explainWhatTitle"),
    ("uk", "latentLab.archaeology.headerTitle"),
    ("uk", "latentLab.attention.explainHowTitle"),
    ("uk", "latentLab.attention.explainReadTitle"),
    ("uk", "latentLab.attention.explainWhatTitle"),
    ("uk", "latentLab.composable.explainHowTitle"),
    ("uk", "latentLab.composable.explainWhatTitle"),
    ("uk", "latentLab.crossmodal.guidance.explainHowTitle"),
    ("uk", "latentLab.crossmodal.guidance.explainWhatTitle"),
    ("uk", "latentLab.crossmodal.guidance.imageTypeTitle"),
    ("uk", "latentLab.crossmodal.mmaudio.explainHowTitle"),
    ("uk", "latentLab.crossmodal.mmaudio.explainWhatTitle"),
    ("uk", "latentLab.crossmodal.synth.explainHowTitle"),
    ("uk", "latentLab.crossmodal.synth.explainWhatTitle"),
    ("uk", "latentLab.probing.explainHowTitle"),
    ("uk", "latentLab.probing.explainReadTitle"),
    ("uk", "latentLab.probing.explainWhatTitle"),
    ("uk", "latentLab.textLab.repeng.explainHowTitle"),
    ("uk", "latentLab.textLab.repeng.explainWhatTitle"),
    ("uk", "latentLab.textLab.repeng.targetLayerHint"),
}

STOCK_PATH = pathlib.Path(__file__).resolve().parent / "data" / \
    "i18n_label_debt_stock_2026-09-04.txt"
# The stock file's sha256. It changes only by a decision recorded in the commit message:
# the file is the frozen list, and a gate whose baseline can be rewritten silently is
# not a baseline.
STOCK_SHA256 = "3d4dc0844242baa2a375fd0c2c3414dea42518408972c76d9cb860d395a25a19"


# --------------------------------------------------------------------------------
# Parser. A line-based key stack over the i18n object literal.
#
# These files are one key per line, one nesting level per line, with a handful of
# one-line objects. A parser that understood TypeScript would need a dependency the
# pre-commit hook cannot assume, so this one reads lines -- and says so loudly where it
# meets a shape it cannot read, rather than skipping it. A skipped line is an unchecked
# string, and eighteen of them hid behind the first version of this parser.
# --------------------------------------------------------------------------------
KEY_NAME = r"([A-Za-z0-9_]+|'[^']*'|\"[^\"]*\")"
OPEN_BLOCK = re.compile(r"^\s*" + KEY_NAME + r":\s*\{\s*$")
CLOSE_BLOCK = re.compile(r"^\s*\}")
INLINE_BLOCK = re.compile(r"^\s*" + KEY_NAME + r":\s*\{(.+)\}\s*,?\s*$")
BARE_KEY = re.compile(r"^\s*" + KEY_NAME + r":\s*$")
BARE_STRING = re.compile(r"^\s*(['\"])((?:[^'\"\\]|\\.|(?!\1)['\"])*)\1\s*,?\s*$")
PAIR = re.compile(
    KEY_NAME + r"\s*:\s*(?:'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\")"
)

ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|n|t|r|\\|'|\")")
_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}


def _unescape(value: str) -> str:
    """Decode the escapes these files actually use.

    `\\u2014` is written out in about a hundred values; leaving it encoded made every
    anchored check read a backslash as the first character.
    """
    def one(match):
        token = match.group(1)
        if token[0] == "u":
            try:
                return chr(int(token[1:], 16))
            except ValueError:                               # pragma: no cover
                return match.group(0)
        return _SIMPLE_ESCAPES[token]
    try:
        out = ESCAPE.sub(one, value)
    except Exception:                                        # noqa: BLE001
        return value
    # An emoji is written as a UTF-16 surrogate PAIR: \ud83d\udcd0. Decoding the two
    # halves separately yields two lone surrogates, which compare equal to nothing.
    if any("\ud800" <= char <= "\udfff" for char in out):
        try:
            out = out.encode("utf-16", "surrogatepass").decode("utf-16")
        except (UnicodeDecodeError, UnicodeEncodeError):     # pragma: no cover
            pass
    return out


def _clean_key(raw: str) -> str:
    return raw[1:-1] if raw[:1] in "'\"" else raw


def _scan_line(line: str):
    """(code before an out-of-string `//`, backtick seen, `/*` seen), outside strings."""
    quote = None
    backtick = block = False
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "`":
            backtick = True
        elif char == "/" and index + 1 < length:
            if line[index + 1] == "/":
                return line[:index], backtick, block
            if line[index + 1] == "*":
                block = True
        index += 1
    return line, backtick, block


def _pairs(text: str):
    for match in PAIR.finditer(text):
        raw = match.group(2) if match.group(2) is not None else match.group(3)
        yield _clean_key(match.group(1)), _unescape(raw)


def parse_locale(source: str, label: str = "<locale>"):
    """(entries, problems). An entry is (dotted key, value, line number).

    Problems name a file and a line and are failures, not warnings: a template literal
    or a block comment is a shape this parser cannot read, and a parser that skips what
    it cannot read reports a clean file that was never checked.
    """
    stack = []
    pending = None
    entries = []
    problems = []
    for number, line in enumerate(source.splitlines(), 1):
        code, backtick, block = _scan_line(line)
        if backtick:
            problems.append(f"{label}:{number}: backtick template literal -- this "
                            f"parser reads one-line string values only")
            continue
        if block:
            problems.append(f"{label}:{number}: /* block comment -- this parser reads "
                            f"line comments only")
            continue

        if pending is not None:
            held, held_line, pending = pending[0], pending[1], None
            match = BARE_STRING.match(code)
            if match:
                # The key's line, not the value's: that is the line somebody edits.
                entries.append((".".join(stack + [held]),
                                _unescape(match.group(2)), held_line))
                continue

        match = OPEN_BLOCK.match(code)
        if match:
            stack.append(_clean_key(match.group(1)))
            continue

        match = INLINE_BLOCK.match(code)
        if match:
            parent = _clean_key(match.group(1))
            for key, value in _pairs(match.group(2)):
                entries.append((".".join(stack + [parent, key]), value, number))
            continue

        if CLOSE_BLOCK.match(code):
            if stack:
                stack.pop()
            continue

        found = list(_pairs(code))
        if found:
            # One pair or several; several on one line are several values, never one
            # value with commas in it.
            for key, value in found:
                entries.append((".".join(stack + [key]), value, number))
            continue

        match = BARE_KEY.match(code)
        if match:
            pending = (_clean_key(match.group(1)), number)
    return entries, problems


def parse_ts(source: str):
    """Entries only. For callers that have already handled the problems."""
    return parse_locale(source)[0]


REPORT_TAIL = "the string is the noun of its key (docs/COPY_RULES.md)"


def check_content(lang: str, source: str, label: str = None):
    """Offenders in one locale source, allowlists applied."""
    if label is None:
        label = f"{lang}.ts"
    entries, problems = parse_locale(source, label)
    found = list(problems)
    for dotted, value, number in entries:
        if not is_label_key(dotted):
            continue
        check = check_value(lang, value, dotted)
        if check is None:
            continue
        if dotted in ALLOWED or (lang, dotted) in INHERITED_DEBT:
            continue
        found.append(f"{label}:{number}  {dotted} = '{value}'  -> {check}; {REPORT_TAIL}")
    return found


def missing_word_tables(languages=None):
    """Languages this file cannot judge. Loud on purpose, in every mode.

    A language that reaches the i18n directory without a word table would otherwise pass
    by having no check to fail, which is the one failure mode a gate must not have.
    """
    languages = LANGUAGES if languages is None else languages
    if not languages:
        return [f"no locale module found under {I18N_REL} -- the gate checked nothing"]
    return [f"no word table for {lang} -- add one to WH_INITIAL in "
            f"devserver/tests/test_i18n_label_grammar.py"
            for lang in languages if lang not in WH_INITIAL]


def _offenders():
    """Every offender in the working tree, every locale module."""
    found = []
    for lang in LANGUAGES:
        found.extend(check_content(lang, _read(lang)))
    return found


def _live_offences():
    """(language, dotted key) for every label slot that currently trips a check.

    The lists are measured against this: an entry that matches nothing here has been
    fixed or deleted, and a list that keeps a fixed entry is a door nobody remembers
    leaving open.
    """
    live = set()
    for lang in LANGUAGES:
        for dotted, value, _ in parse_ts(_read(lang)):
            if is_label_key(dotted) and check_value(lang, value, dotted) is not None:
                live.add((lang, dotted))
    return live


def _stale():
    live = _live_offences()
    live_keys = {dotted for _, dotted in live}
    stale = [f"ALLOWED: {key}" for key in sorted(ALLOWED) if key not in live_keys]
    stale += [f"INHERITED_DEBT: {lang} {key}"
              for lang, key in sorted(INHERITED_DEBT) if (lang, key) not in live]
    return stale


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
    import subprocess
    return subprocess.run(("git",) + args, cwd=str(REPO),
                          capture_output=True, text=True, check=True).stdout


TEST_REL = "devserver/tests/test_i18n_label_grammar.py"


def _staged_report():
    """(lines, blocking) for the commit in front of the gate.

    Several sessions share this checkout. A gate that judges the whole working tree
    stops a commit over a string in a file the committer never opened, and over another
    session's half-finished edit. Neither is grounds to refuse the commit being made.
    """
    staged = set(_git("diff", "--cached", "--name-only",
                      "--diff-filter=ACMR").splitlines())

    # Locales come from what git TRACKS, plus what this commit adds. An untracked
    # scratch file in the i18n directory is not a locale of this repository and must not
    # block a commit that never touched it.
    def _under(names):
        return {name for name in names
                if name.startswith(I18N_REL + "/") and name.endswith(".ts")}

    in_index = _under(_git("ls-files", "--", I18N_REL).splitlines())
    try:
        in_head = _under(_git("ls-tree", "-r", "--name-only", "HEAD",
                              "--", I18N_REL).splitlines())
    except Exception:                                        # noqa: BLE001
        in_head = set()                                      # no commit yet

    # In HEAD and no longer in the index: this commit deletes or renames it. Read from
    # the index alone this is invisible, because git rm takes the path out of both.
    gone = []
    for name in sorted(in_head - in_index):
        stem = name.rsplit("/", 1)[-1][:-3]
        try:
            if _is_locale_source(stem, _git("show", f"HEAD:{name}")):
                gone.append(name)
        except Exception:                                    # noqa: BLE001
            continue

    languages = {}
    for name in sorted(in_index | _under(staged)):
        stem = name.rsplit("/", 1)[-1][:-3]
        try:
            source = _git("show", f":{name}")
        except Exception:                                    # noqa: BLE001
            continue
        if _is_locale_source(stem, source):
            languages[stem] = (name, source)

    if gone:
        return ([f"label-grammar: {name} is a tracked locale this commit removes. Its "
                 f"INHERITED_DEBT lines and its word table go in the same commit."
                 for name in gone], True)

    untested = missing_word_tables(sorted(languages))
    if untested and languages:
        return (untested, True)

    # Discovery is the whole set; the CHECK is only what this commit touches. A gate
    # that judged every tracked locale would refuse a Python-only commit over a string
    # in a file the committer never opened -- which is the whole reason this mode
    # exists.
    touched = sorted(lang for lang, (name, _) in languages.items() if name in staged)

    lines = []
    for lang in touched:
        name, source = languages[lang]
        lines.extend(check_content(lang, source, label=name))
    if lines:
        return (lines, True)

    # The list shrinks WITH the fix, not after it. A commit that corrects a string still
    # listed as debt has to take the line out in the same commit, or the entry goes
    # stale and the next whole-tree run fails on somebody else's desk.
    #
    # Only keys still present and now clean count. A key that vanished from the staged
    # blob may equally be a parser hiccup, and a gate that guesses is a gate that blocks
    # the wrong commit.
    fixed = []
    for lang in touched:
        name, source = languages[lang]
        listed = {key for language, key in INHERITED_DEBT if language == lang}
        if not listed:
            continue
        for dotted, value, _ in parse_ts(source):
            if dotted in listed and is_label_key(dotted) \
                    and check_value(lang, value, dotted) is None:
                fixed.append(f"{lang} {dotted}")
    if fixed and TEST_REL not in staged:
        return ([f"label-grammar: this commit fixes {len(fixed)} string(s) still listed "
                 f"as inherited debt: {' '.join(sorted(fixed))}. Remove those lines from "
                 f"INHERITED_DEBT in {TEST_REL} and stage that file with this commit -- "
                 f"the list shrinks with the fix, not after it."], True)
    return ([], False)


# --------------------------------------------------------------------------------
# pytest
# --------------------------------------------------------------------------------
def test_i18n_label_grammar():
    untested = missing_word_tables()
    assert not untested, "\n  ".join(untested)
    offenders = _offenders()
    stale = _stale()
    assert not offenders and not stale, (
        "A label names the category of what is under it, and that category is the noun "
        "of its key:\n  "
        + "\n  ".join(offenders + stale)
    )


def test_the_lists_only_shrink():
    """Membership against a frozen stock, not a count.

    A count lets one entry be swapped for another and stay green. The stock file is the
    list as it stood on 2026-09-04; every entry in the live list has to be in it.
    """
    assert set(ALLOWED) <= set(ALLOWED_STOCK), (
        "ALLOWED grew -- a question in a label slot is a rewrite, not an entry:\n  "
        + "\n  ".join(sorted(set(ALLOWED) - set(ALLOWED_STOCK)))
    )
    stock = _stock_entries()
    assert stock is not None, f"the frozen stock is missing: {STOCK_PATH}"
    assert _stock_sha256() == STOCK_SHA256, (
        f"the frozen stock changed. {STOCK_PATH.name} is the list as it stood on "
        f"2026-09-04; editing it is a decision that belongs in the commit message, not "
        f"a way past a red test."
    )
    assert INHERITED_DEBT <= stock, (
        "INHERITED_DEBT grew -- it holds the stock of 2026-09-04 and shrinks only:\n  "
        + "\n  ".join(f"{lang} {key}" for lang, key in sorted(INHERITED_DEBT - stock))
    )


if __name__ == "__main__":
    if not I18N_DIR.is_dir():
        print(f"label-grammar: no {I18N_REL} in this checkout, gate does not apply")
        raise SystemExit(0)

    if "--staged" in sys.argv:
        try:
            lines, blocking = _staged_report()
        except Exception as e:                               # noqa: BLE001
            # A gate that cannot read the commit says so and steps aside. Blocking every
            # commit in the checkout because git or this file misbehaved is the larger
            # harm.
            print(f"label-grammar gate could not read the staged commit ({e}); "
                  f"letting it through", file=sys.stderr)
            raise SystemExit(0)
        if blocking:
            print("\nCOMMIT BLOCKED -- label grammar:\n  " + "\n  ".join(lines)
                  + "\n\nA label is a naming form: no article, no relative clause, no "
                    "question,\nno question mark. Write the noun the key already "
                    "carries -- promptLabel ->\n'Prompt', motivation -> 'Reason'. "
                    "docs/COPY_RULES.md has the full rule.\n\nA genuine question "
                    "to the user belongs in a content slot, or in this test's\nALLOWED "
                    "with its reason. Widening a list is a decision recorded in the\n"
                    "commit message, not a --no-verify.\n", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)

    bad = _offenders() + _stale() + missing_word_tables()
    if bad:
        print("\n".join(bad), file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)
