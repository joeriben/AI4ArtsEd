"""Resona's internal evidence duty (Belegpflicht).

The LLM is forced by an internal evidence duty. Prompt exhortation alone did not stop ungrounded lecturing (an
abstract cultural-appropriation caveat while Abdilla/Kite sat unopened on
the shelf), so the duty is enforced mechanically in the chat loop:

- Resona tags research-leaning sentences with internal markers:
  [src: <doc_id|url|run_id>] for a source actually OPENED this turn,
  [own] for its own reasoning.
- validate() checks every marker against the ledger of tools that really
  ran (read_knowledge / read_webpage / view_run / view_favorite) and scans
  the text for named shelf authors and discourse terms the shelf can carry.
- A failing draft goes back to the model (which still has its tools, so it
  can do the reading NOW); after MAX_EVIDENCE_CORRECTIONS the reply ships
  and the remaining violations are logged and reported.
- strip_markers() removes the notation before anyone sees the reply,
  byte-identical everywhere else.

Rules of the check (hardened after an adversarial review):
- A named shelf author requires THEIR opened doc - a marker to something
  else does not cover them; German genitive (Abdillas, Kites) and ALL-CAPS
  count as mentions.
- A discourse trigger requires that Resona LOOKED: either a scholarly
  source (doc or curated web page - a viewed run does NOT count) was
  opened this turn, or a search actually ran and came back EMPTY. The
  empty search is a full third move, recorded as ('miss', query). What is
  owed is looking, not finding: a shelf that holds nothing on the topic
  must still leave a legal way to think and to say so, or the mechanism
  forces the very fabrication it exists to prevent (two forced correction
  rounds once produced a Wagner misattribution and leaked the mechanism
  into the reply). Wording the educator themselves used in
  the latest message is exempt - echoing the group is not lecturing.
- Web markers must name the exact opened page; empty or truncated refs are
  violations, not wildcards.

Deterministic by design; the lexicon (author surnames, multi-word glossary
terms) is read from the knowledge index and cached by file mtime. What the
check cannot do: bind an opened source to the TOPIC of a sentence - that
would need semantics. The surname rule binds per-author; the discourse rule
binds per-turn. This is the deterministic floor, not a proof of relevance.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import config

logger = logging.getLogger(__name__)


def index_path() -> Path:
    """config.KNOWLEDGE_INDEX_DB at call time, the file the ingest writes (finding S-077 of the code review of 2026-10-10)."""
    return Path(config.KNOWLEDGE_INDEX_DB)


MAX_EVIDENCE_CORRECTIONS = 2
_MIN_REF_LEN = 8  # every real doc_id/run_id/url is longer; shorter = truncated

_MARKER_PAT = r"\[\s*(?:src\s*:\s*([^\]]*?)|own)\s*\]"
_MARKER_RE = re.compile(_MARKER_PAT, re.I)

# Discourse signals the shelf can carry even when no author is named.
# Lowercase stems, substring-matched; multi-word glossary terms from the
# index are matched with word boundaries in _term_hit().
_PHRASES = (
    "cultural appropriation", "kulturelle aneignung", "kultureller aneignung",
    "colonial", "kolonial",            # covers post-/de-/neo- compounds
    "eurocentri", "eurozentri",
    "indigenous", "indigen",
    "aboriginal", "first nations",
    "epistemic injustice", "epistemische ungerechtigkeit",
    "bias", "stereotyp",
    "research shows", "studies show", "state of research",
    "scholars argue", "well established",
    "studien zeigen", "studien belegen", "die forschung zeigt",
    "der forschungsstand", "forschung legt nahe", "empirisch belegt",
    "laut studien", "forschungsliteratur",
)

# The platform's everyday self-description is working vocabulary, not a
# discourse invocation - it must never become a trigger, or every second
# reply would bounce ("this is an instrument of arts education...").
_TERM_STOPLIST = {
    "arts education", "art education", "cultural education",
    "kulturelle bildung", "aesthetic education", "ästhetische bildung",
    "artificial intelligence", "künstliche intelligenz",
    "generative ai", "generative ki", "machine learning",
}

_lexicon_cache: Tuple[float, Optional[Dict]] = (0.0, None)


def build_lexicon(docs: Iterable[Tuple[str, str, str]],
                  glossary: Iterable[Tuple[str, str]]) -> Dict:
    """Pure lexicon builder (injectable for tests).

    docs: (doc_id, title, authors); glossary: (term, doc_hint).
    Author fields are split on commas AND ' and '/' & ' before the
    organisation heuristic (parts of five+ words are skipped), so
    'Angie Abdilla and Suzanne Kite' yields both surnames. Min length 4
    keeps 'Kite'; three-letter surnames stay exempt (documented tradeoff).
    Terms: multi-word glossary entries only - single words ('Atelier',
    'Blick') would trip on ordinary workshop talk.
    """
    surnames: Dict[str, Set[str]] = {}
    for doc_id, _title, authors in docs:
        for comma_part in (authors or "").split(","):
            cp = comma_part.strip()
            words_cp = cp.split()
            # 'and'/'&' splits person PAIRS ('Eve Tuck and K. Wayne Yang');
            # longer phrases are organisation names ('... Protocol and ...
            # Working Group') and must stay whole so the 5-word org rule
            # can drop them - a naive split would mint 'Protocol'/'Group'.
            if words_cp and len(words_cp) <= 6 and re.search(r"\band\b|&", cp):
                subparts = re.split(r"\band\b|&", cp)
            else:
                subparts = [cp]
            for part in subparts:
                words = part.strip().split()
                if not words or len(words) >= 5:
                    continue
                surname = words[-1].strip(".()")
                if len(surname) < 4:
                    continue
                surnames.setdefault(surname, set()).add(doc_id)
        # Bibliographic doc_ids carry the lead author even when the authors
        # field does not (real case: abdilla-et-al-... lists only Lewis and
        # the working group). Only the unambiguous 'name-et-al-'/'name-and-'
        # shape is used - a bare first token would mint false surnames.
        lead = re.match(r"([a-zà-ÿ]{4,})-(?:et-al|and)-", doc_id or "")
        if lead:
            surnames.setdefault(lead.group(1).capitalize(), set()).add(doc_id)
    terms: Dict[str, Set[str]] = {}
    for term, doc_hint in glossary:
        t = (term or "").strip()
        if (len(t.split()) >= 2 and len(t) >= 8
                and t.lower() not in _TERM_STOPLIST):
            terms.setdefault(t.lower(), set()).add(doc_hint or "")
    return {"surnames": surnames, "terms": terms}


def load_lexicon() -> Dict:
    """Index-backed lexicon, cached by mtime; empty on any failure."""
    global _lexicon_cache
    try:
        mtime = index_path().stat().st_mtime
    except OSError:
        return {"surnames": {}, "terms": {}}
    if _lexicon_cache[0] == mtime and _lexicon_cache[1] is not None:
        return _lexicon_cache[1]
    try:
        db = sqlite3.connect(str(index_path()))
        docs = db.execute("SELECT doc_id, title, authors FROM docs").fetchall()
        glossary: List[Tuple[str, str]] = []
        for term, refs in db.execute("SELECT term, doc_refs_json FROM glossary"):
            hint = ""
            try:
                refs_list = json.loads(refs or "[]")
                if refs_list:
                    hint = str(refs_list[0])
            except Exception:
                hint = ""
            glossary.append((term, hint))
        db.close()
        lex = build_lexicon(docs, glossary)
    except Exception as e:  # noqa: BLE001 - a broken index must not break chat
        logger.warning("[EVIDENCE] lexicon load failed: %s", e)
        return {"surnames": {}, "terms": {}}
    _lexicon_cache = (mtime, lex)
    return lex


def _word_hit(surname: str, text: str) -> bool:
    """Word-boundary mention of a surname, incl. German genitive (Abdillas,
    Kites) and ALL-CAPS; lowercase forms ('a kite') stay exempt."""
    pat = (r"(?<![\wÀ-ɏ])(?:" + re.escape(surname) + "|" + re.escape(surname.upper())
           + r")(?:'s|s|n)?(?![\wÀ-ɏ])")
    return re.search(pat, text) is not None


def _term_hit(term: str, low: str) -> bool:
    """Word-boundary match for a glossary term on lowercased text - plain
    substring would fire on 'smart education tools' for 'art education'."""
    pat = r"(?<![\wà-ÿ])" + re.escape(term) + r"(?![\wà-ÿ])"
    return re.search(pat, low) is not None


def validate(reply: str, ledger: Sequence[Tuple[str, str]],
             lexicon: Optional[Dict] = None, user_text: str = "") -> List[str]:
    """Deterministic evidence check; returns violations (empty = passes).

    ledger: (kind, ref) for every source-opening tool that actually ran
    this turn - kind in {'doc', 'web', 'run'}, plus ('miss', query) for a
    search that ran and returned nothing. user_text: the latest user
    message; discourse wording the group itself used is exempt (echoing is
    not lecturing) - named authors are never exempt.
    """
    text = reply or ""
    if not text.strip():
        return []
    lex = lexicon if lexicon is not None else load_lexicon()
    docs_opened = {v for k, v in ledger if k == "doc"}
    webs_opened = {v.rstrip("/") for k, v in ledger if k == "web"}
    runs_opened = {v for k, v in ledger if k == "run"}
    searched_empty = {v for k, v in ledger if k == "miss"}
    # Scholarly ground: docs and curated pages carry a discourse; a viewed
    # run does not - seeing the group's image licenses no lecture. A search
    # that actually ran and came back empty grounds it too: that is the
    # honest report that the shelf holds nothing here. Without it the check
    # has no third move - [own] never covers a discourse and an unsuccessful
    # lookup leaves no trace - so a thin shelf leaves only a question or a
    # wrong citation. It does NOT relax the surname rule: missing on one
    # query never licenses invoking a shelf author unopened.
    scholarly_opened = bool(docs_opened or webs_opened or searched_empty)

    violations: List[str] = []
    for m in _MARKER_RE.finditer(text):
        ref = m.group(1)
        if ref is None:
            continue  # [own]
        ref = ref.strip()
        if len(ref) < _MIN_REF_LEN:
            violations.append(
                f"[src: {ref or ' '}] is empty or truncated - a marker names "
                "the exact doc_id, url, or run_id you opened, or it is [own]."
            )
            continue
        ok = (ref in docs_opened or ref in runs_opened
              or ref.rstrip("/") in webs_opened)
        if not ok:
            violations.append(
                f"[src: {ref}] is not backed by anything you opened this "
                "turn - open it (read_knowledge / read_webpage / view_run) "
                "or strike the sentence it covers."
            )

    stripped = _MARKER_RE.sub(" ", text)

    for surname in sorted(lex.get("surnames", {})):
        if not _word_hit(surname, stripped):
            continue
        doc_ids = lex["surnames"][surname]
        if doc_ids & docs_opened:
            continue
        hint = ", ".join(sorted(doc_ids)[:2])
        violations.append(
            f"You invoke {surname} without having opened their text this "
            f"turn - read_knowledge first (shelf: {hint}), then let what it "
            "actually says carry the sentence."
        )

    if not scholarly_opened:
        low = stripped.lower()
        user_low = (user_text or "").lower()
        triggers = [t for t in lex.get("terms", {})
                    if _term_hit(t, low) and not _term_hit(t, user_low)]
        triggers += [p for p in _PHRASES if p in low and p not in user_low]
        if triggers:
            shown = ", ".join(f"'{t}'" for t in sorted(set(triggers))[:4])
            violations.append(
                f"You invoke {shown} without having looked this turn - "
                "search first (lookup_knowledge, then read_knowledge; or "
                "search_websites / read_webpage on the curated sites). If "
                "the search comes back empty, that is enough: say the shelf "
                "holds nothing on it and stand on [own]. A viewed run "
                "carries no discourse."
            )
    return violations


def correction_message(violations: Sequence[str]) -> str:
    lines = "\n".join(f"- {v}" for v in list(violations)[:8])
    return (
        "INTERNAL EVIDENCE CHECK - this message is the platform, not a person; "
        "the group has NOT seen your draft.\n"
        "Your draft failed its evidence duty:\n" + lines + "\n"
        "You still have your tools. Open what you lean on NOW "
        "(read_knowledge / read_webpage / view_run) and let what the source "
        "actually says carry the sentence - reading comes first. If your "
        "search comes back empty, that is a real answer and the platform "
        "accepts it: say the library holds nothing on it and stand on [own] "
        "plainly. Keep the internal "
        "markers ([src: ...] / [own]); they are stripped before display."
    )


def strip_markers(text: str) -> str:
    """Remove the internal notation; the rest of the text stays
    byte-identical (no global whitespace normalization - it would flatten
    nested lists, code indents, and aligned poems)."""
    # marker glued to following punctuation: eat surrounding spaces too,
    # so 'dream [src: x] ,' becomes 'dream,'
    clean = re.sub(r"(?i)[ \t]*" + _MARKER_PAT + r"\s*(?=[.,;:!?])", "", text or "")
    clean = re.sub(r"(?i)[ \t]*" + _MARKER_PAT, "", clean)
    return clean
