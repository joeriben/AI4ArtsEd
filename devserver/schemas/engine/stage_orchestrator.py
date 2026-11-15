"""
Stage Orchestrator - helpers the routes and the safety gate share
Extracted from pipeline_executor.py for Phase 2 refactoring

What stands here, among other things: the translation into English and its
context, the device translation cache, the word filters with the §86a lists,
the name recogniser and the name question, and the sentences of the block
message. Stage 1 and Stage 3, which this module ran for the routes, stood here
until 2026-11-01; the checks are my_app/services/safety_gate.py now.
"""
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import logging
import json
import re
import threading
import time as _time

logger = logging.getLogger(__name__)

# Translation reuse: cache only within a device bucket.
# A single global "last translation" leaks prompt state across workshop devices.
_translation_cache_lock = threading.Lock()
_translation_cache: Dict[str, Dict[str, Any]] = {}
_TRANSLATION_CACHE_TTL = 3600  # 1 hour


def _get_translation_cache_entry(device_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the translation cache bucket for one device, or None if unscoped."""
    if not device_id:
        return None

    now = _time.time()
    with _translation_cache_lock:
        stale = [
            key for key, value in _translation_cache.items()
            if now - value.get('ts', 0) > _TRANSLATION_CACHE_TTL
        ]
        for key in stale:
            del _translation_cache[key]

        return _translation_cache.get(device_id)


def _update_translation_cache(device_id: Optional[str], untranslated: str, translated: str,
                             instruction: str = '') -> None:
    """Store the latest translation for one device.

    The wording the translation was made under is part of what identifies it: a
    perspective that carries its own translation instruction gets a different
    English text out of the same German one, and reusing the other would hand
    the run somebody else's register.
    """
    if not device_id:
        return

    with _translation_cache_lock:
        _translation_cache[device_id] = {
            'untranslated': untranslated,
            'translated': translated,
            'instruction': instruction,
            'ts': _time.time(),
        }


def translation_instruction_for(interception_config) -> Optional[str]:
    """What a perspective says about carrying its result into English.

    A perspective whose result lives in a register — a way of speaking, not a
    set of words — says so on its own config as meta.translation_instruction.
    Everything else answers None here and its result is translated the way every
    result has always been translated.

    Takes the RESOLVED config, never a name: a kept perspective is addressed as
    custom:<id>, has no config file of its own and inherits the wording from the
    preset it was forked from. Looking that name up in the config loader answers
    None for exactly the runs that carry the wording.
    """
    instruction = (getattr(interception_config, 'meta', None) or {}).get('translation_instruction')
    if instruction and instruction.strip():
        logger.info("[STAGE3-TRANSLATION] '%s' brings its own wording along",
                    getattr(interception_config, 'name', '?'))
        return instruction
    return None


def translation_context(text: str, translation_instruction: Optional[str] = None):
    """The context every translation into English runs in.

    A translation has nothing to look up. Without the opt-out the executor hands
    the translator the Wikipedia research offer along with its prompt; the model
    answers with lookup markers, and every lookup runs the whole translation
    again, up to three times. With GLM 5.3 that took 91 to 429 s (22.-26.09.2026).
    The chain translation in Stage 2 opts out the same way.

    A perspective may also say how its result is to be carried into English —
    meta.translation_instruction on the Stage-2 config. Read here so every
    translation site takes the same wording. Where no perspective says anything,
    the translator's prompt is the one it has always been.
    """
    from .pipeline_executor import PipelineContext
    context = PipelineContext(input_text=text, user_input=text)
    context.custom_placeholders['_SKIP_WIKIPEDIA'] = True
    if (translation_instruction or '').strip():
        # The wording is written by whoever authored the perspective and lands in a
        # template that still has placeholders open. Braces are taken out of it, so
        # a wording can add a rule and nothing else.
        wording = translation_instruction.strip().replace('{{', '').replace('}}', '')
        context.custom_placeholders['TRANSLATION_INSTRUCTION'] = '\n\nREGISTER: ' + wording
    return context

# ============================================================================
# FUZZY MATCHING: Levenshtein distance for typo-resilient filter lists
# ============================================================================

def _levenshtein(s1: str, s2: str) -> int:
    """Simple Levenshtein distance (stdlib-only, no dependencies)"""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            curr_row.append(min(
                prev_row[j + 1] + 1,   # insertion
                curr_row[j] + 1,        # deletion
                prev_row[j] + (c1 != c2)  # substitution
            ))
        prev_row = curr_row
    return prev_row[-1]


_WORD_BOUNDARY_CACHE: Dict[str, re.Pattern] = {}

def _word_boundary_match(text_lower: str, term: str) -> bool:
    """Word-boundary match — prevents 'kan' matching inside 'scharfkantige'."""
    if term not in _WORD_BOUNDARY_CACHE:
        _WORD_BOUNDARY_CACHE[term] = re.compile(r'\b' + re.escape(term) + r'\b')
    return bool(_WORD_BOUNDARY_CACHE[term].search(text_lower))


_STEM_PREFIX_CACHE: Dict[str, re.Pattern] = {}

def _stem_prefix_match(text_lower: str, term: str) -> bool:
    """Stem-prefix match — term must start at a word boundary but may extend into the word.
    Catches 'Blut' in 'blutiger' (same stem), rejects 'Leiche' in 'gleiche' (different word)."""
    if term not in _STEM_PREFIX_CACHE:
        _STEM_PREFIX_CACHE[term] = re.compile(r'\b' + re.escape(term))
    return bool(_STEM_PREFIX_CACHE[term].search(text_lower))


_TOKEN_RE = re.compile(r'\w+', re.UNICODE)


def _tokens(text: str) -> List[str]:
    """The words of a text, punctuation dropped: 'SS-Symbol.' -> ['ss', 'symbol']."""
    return _TOKEN_RE.findall(text.lower())


def _word_matches(token: str, term_word: str) -> bool:
    """One word of a multi-word term against one word of the text.

    Tolerance by length, and never across the word's edge. A long word may be
    misspelled — deliberate obfuscation ("Ha1kenkreuz") is what the fuzzy search
    exists for — while a short one must be the word itself: two edits turn a
    one-letter word into any other, which is how "a symbol" came to match the
    term "ss symbol". From four letters on, an inflection is allowed in either
    direction, so that "concentration camps" matches the term "concentration
    camp" and "ss rune" the term "ss runes".
    """
    if token == term_word:
        return True
    n = len(term_word)
    if n >= 4 and len(token) >= 4 and (token.startswith(term_word) or term_word.startswith(token)):
        return True
    if n >= 8:
        return _levenshtein(token, term_word) <= 2
    if n >= 6:
        return _levenshtein(token, term_word) <= 1
    return False


def _fuzzy_contains(text_lower: str, term: str, max_distance: int = 2) -> bool:
    """Check if any word/phrase in text fuzzy-matches term within Levenshtein distance.

    `max_distance` governs single-word terms. A multi-word term is matched word
    for word at word boundaries instead (_word_matches): the distance used to run
    across the spaces, and with two edits allowed the term "ss symbol" matched
    the phrase "a symbol" — a §86a HARDBLOCK on every text containing it, among
    them every machine reading of a picture that mentioned a symbol. Terms
    like "is flag" or "raf terror" were one edit away from
    "his flag" and "raw terror" the same way.
    """
    term_len = len(term)
    words = text_lower.split()

    if ' ' in term:
        # Multi-word term (e.g. "heil hitler"): word for word, in order, at word
        # boundaries. Both sides are tokenised the same way, so a hyphen in the
        # term or in the text makes no difference ("al-qaida flag").
        term_words = _tokens(term)
        text_words = _tokens(text_lower)
        n = len(term_words)
        if n and len(text_words) >= n:
            for i in range(len(text_words) - n + 1):
                if all(_word_matches(text_words[i + k], term_words[k]) for k in range(n)):
                    return True
    else:
        # Single-word term: check each word individually
        for word in words:
            if abs(len(word) - term_len) <= max_distance:
                if _levenshtein(word, term) <= max_distance:
                    return True
    return False


# ============================================================================
# SPACY NER: DSGVO Personal Data Detection
# ============================================================================

# SpaCy models cache (loaded once at module level)
_SPACY_MODELS: Optional[List] = None
_SPACY_LOAD_ATTEMPTED = False

# Primary NER models: German (most users) + multilingual (foreign names)
# These two cover the DSGVO use case without excessive false positives.
# The multilingual model catches names from any language (Turkish, Arabic, etc.)
_SPACY_MODEL_NAMES = [
    'de_core_news_lg',   # German (primary language of the platform)
    'xx_ent_wiki_sm',    # Multilingual fallback (catches foreign names)
]


def _load_spacy_models() -> List:
    """Load all SpaCy NER models (called once, cached)"""
    global _SPACY_MODELS, _SPACY_LOAD_ATTEMPTED

    if _SPACY_LOAD_ATTEMPTED:
        return _SPACY_MODELS or []

    _SPACY_LOAD_ATTEMPTED = True

    try:
        import spacy
    except ImportError:
        logger.warning("[SPACY] spacy not installed — DSGVO NER check disabled")
        _SPACY_MODELS = []
        return []

    models = []
    load_start = _time.time()

    for model_name in _SPACY_MODEL_NAMES:
        try:
            nlp = spacy.load(model_name, disable=['parser', 'lemmatizer', 'attribute_ruler'])
            models.append((model_name, nlp))
        except OSError:
            logger.debug(f"[SPACY] Model '{model_name}' not installed, skipping")

    load_time = _time.time() - load_start
    _SPACY_MODELS = models
    logger.info(f"[SPACY] Loaded {len(models)} NER models in {load_time:.1f}s")
    return models


def fast_dsgvo_check(text: str) -> Tuple[bool, List[str], bool]:
    """
    Fast DSGVO personal name check using SpaCy NER (~12-60ms)

    Runs ALL loaded language models over the text and unions results.
    Reason: A Turkish name in German text needs the multilingual model.

    Detects ONLY:
    - PER: Person names (first + last name combinations)

    Addresses, emails, phone numbers are NOT checked here — they are
    not DSGVO-relevant without an associated personal name.

    Returns:
        (has_personal_name, found_names, spacy_available)
    """
    models = _load_spacy_models()

    if not models:
        return (False, [], False)

    found_entities = set()
    check_start = _time.time()

    # Run all language models and union results
    for model_name, nlp in models:
        try:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ == 'PER':
                    # Only flag multi-word names (first + last) — single words are too common
                    if ' ' not in ent.text.strip():
                        continue
                    # POS-tag filter: real names have PROPN tokens.
                    # False positives like "Schräges Fenster" are ADJ+NOUN.
                    has_propn = any(tok.pos_ == 'PROPN' for tok in ent)
                    if not has_propn:
                        logger.debug(f"[DSGVO-NER] POS-filtered: '{ent.text}' ({[tok.pos_ for tok in ent]})")
                        continue
                    # Filter: Entities containing digits or SD weight syntax (e.g., "soft light:1.2")
                    # Real person names never contain digits
                    if re.search(r'\d', ent.text):
                        logger.debug(f"[DSGVO-NER] Numeric filtered: '{ent.text}'")
                        continue
                    found_entities.add(f"Name: {ent.text.strip()}")
        except Exception as e:
            logger.debug(f"[SPACY] Error with model {model_name}: {e}")

    check_time = _time.time() - check_start
    entity_list = sorted(found_entities)

    if entity_list:
        logger.info(f"[DSGVO-NER] Found {len(entity_list)} names in {check_time*1000:.1f}ms: {entity_list[:3]}")
    else:
        logger.debug(f"[DSGVO-NER] Clean ({check_time*1000:.1f}ms)")

    return (len(entity_list) > 0, entity_list, True)


# Short-lived cache for the data-protection check.
# Prevents redundant calls when several concurrent runs ask about the same
# text (workshop burst generation). Keyed on the text, because the text is
# what is asked about: it used to be keyed on the entity list SpaCy produced,
# from the time when the question was "are THESE words names".
_dsgvo_verify_cache: Dict[str, tuple] = {}  # text → (result, timestamp)
_DSGVO_VERIFY_CACHE_TTL = 60  # seconds


def llm_personal_data_check(text: str, candidates: Optional[list] = None) -> Optional[bool]:
    """Does this text carry a private individual's name or address?

    True blocks, False releases, None is no answer and blocks at every caller.

    ONE function, where there were two. `llm_verify_person_name` asked a
    general-purpose model whether the words SpaCy had flagged were really
    names; `llm_dsgvo_fallback_check` asked the same model to find names by
    itself when SpaCy would not load. Both put the question in free text, both
    read the answer by looking for the letters SAFE at the start of a
    continuation, and "SAFE" is a substring of "UNSAFE" and of "NOT SAFE".
    They differed in their prompt and in nothing else that mattered, which is
    two implementations of one behaviour.

    `candidates` is SpaCy's hit list where there is one. It travels INTO the
    document, named for what it is, because the block message this feeds prints
    exactly those words back to the person under "Folgende persönliche Daten
    wurden in deinem Prompt gefunden". A first version of this rewrite dropped
    the list and asked about the text alone; the model could then answer yes
    about a name SpaCy never flagged, and the person was shown the wrong words
    as the reason — found by an adversarial review on 2026-09-23. The whole
    text goes as well, so the model still answers about everything in it and a
    name SpaCy missed is not lost.

    The data never leaves this machine. That was true before and stays true:
    the classifier runs in the GPU service on this card.
    """
    from my_app.services import safety_classifier

    named = [str(c).replace("Name: ", "") for c in (candidates or [])]
    document = text
    if named:
        document = (f"{text}\n\n"
                    f"A name-recognition pass flagged these words in the text "
                    f"above: {', '.join(named)}")

    now = _time.time()
    cached = _dsgvo_verify_cache.get(document)
    if cached is not None:
        cached_result, cached_ts = cached
        if now - cached_ts < _DSGVO_VERIFY_CACHE_TTL:
            logger.info(f"[DSGVO-CHECK] Cache hit → {'UNSAFE' if cached_result else 'SAFE'}")
            return cached_result

    start = _time.time()
    verdict = safety_classifier.is_unsafe(safety_classifier.NAME_POLICY, document)
    duration_ms = (_time.time() - start) * 1000

    if verdict is None:
        logger.error(f"[DSGVO-CHECK] no verdict ({duration_ms:.0f}ms) — fail-closed")
        return None

    logger.info(
        f"[DSGVO-CHECK] → {'UNSAFE — private individual identified' if verdict else 'SAFE'} "
        f"({duration_ms:.0f}ms)"
    )
    _dsgvo_verify_cache[document] = (verdict, _time.time())
    return verdict


# ============================================================================
# HYBRID SAFETY: Fast String-Matching + LLM Context Verification
# ============================================================================

# Cache for filter terms (loaded once at module level)
# kids/youth: Dict[lang, List[term]], stage1: List[term] (EN-only, unchanged)
_FILTER_TERMS_CACHE: Optional[Dict] = None
_BILINGUAL_86A_CACHE: Optional[Dict[str, List[str]]] = None


def _detect_input_language(text: str, user_language: str = 'de') -> str:
    """Detect input language. Unicode-script for non-Latin, frontend hint for Latin."""
    for ch in text:
        if '\uAC00' <= ch <= '\uD7AF' or '\u1100' <= ch <= '\u11FF':
            return 'ko'
        if '\u0400' <= ch <= '\u04FF':
            return 'uk'
        if '\u0590' <= ch <= '\u05FF':
            return 'he'
        if '\u0600' <= ch <= '\u06FF':
            return 'ar'
    return user_language  # Latin script → trust frontend


def _get_active_terms(terms_by_lang: Dict[str, List[str]], language: str) -> Tuple[List[str], str]:
    """Get terms for detected language + EN. Returns (terms, lang_key) for logging."""
    active = list(terms_by_lang.get('en', []))
    lang_key = 'en'
    if language != 'en' and language in terms_by_lang:
        active.extend(terms_by_lang[language])
        lang_key = f'{language}+en'
    return active, lang_key


def load_filter_terms() -> Dict:
    """Load all filter terms from JSON files (cached).
    Returns: {'kids': {lang: [terms]}, 'youth': {lang: [terms]}, 'stage1': [terms]}
    """
    global _FILTER_TERMS_CACHE

    if _FILTER_TERMS_CACHE is None:
        try:
            # Load Stage 3 filters (Youth/Kids) — structured by language
            stage3_path = Path(__file__).parent.parent / "youth_kids_safety_filters.json"
            with open(stage3_path, 'r', encoding='utf-8') as f:
                stage3_data = json.load(f)

            # Load Stage 1 filters (CSAM/Violence/Hate) — flat EN-only list
            stage1_path = Path(__file__).parent.parent / "stage1_safety_filters.json"
            with open(stage1_path, 'r', encoding='utf-8') as f:
                stage1_data = json.load(f)

            kids_by_lang = stage3_data['filters']['kids']['terms_by_language']
            youth_by_lang = stage3_data['filters']['youth']['terms_by_language']
            kids_total = sum(len(v) for v in kids_by_lang.values())
            youth_total = sum(len(v) for v in youth_by_lang.values())

            _FILTER_TERMS_CACHE = {
                'kids': kids_by_lang,
                'youth': youth_by_lang,
                'stage1': stage1_data['filters']['stage1']['terms']
            }
            logger.info(f"Loaded filter terms: stage1={len(_FILTER_TERMS_CACHE['stage1'])}, kids={kids_total} ({len(kids_by_lang)} langs), youth={youth_total} ({len(youth_by_lang)} langs)")
        except Exception as e:
            logger.error(f"Failed to load filter terms: {e}")
            _FILTER_TERMS_CACHE = {'kids': {}, 'youth': {}, 'stage1': []}

    return _FILTER_TERMS_CACHE


def load_bilingual_86a_terms() -> Dict[str, List[str]]:
    """Load §86a critical terms structured by language (cached)."""
    global _BILINGUAL_86A_CACHE

    if _BILINGUAL_86A_CACHE is None:
        try:
            bilingual_path = Path(__file__).parent.parent / "stage1_86a_critical_bilingual.json"
            with open(bilingual_path, 'r', encoding='utf-8') as f:
                bilingual_data = json.load(f)

            _BILINGUAL_86A_CACHE = bilingual_data['filters']['stage1_critical_86a']['terms_by_language']
            total = sum(len(v) for v in _BILINGUAL_86A_CACHE.values())
            if not total:
                raise ValueError("term list is empty")
            logger.info(f"Loaded §86a critical terms: {total} terms ({len(_BILINGUAL_86A_CACHE)} langs)")
        except Exception as e:
            # This used to log and hand back {}, and the filter above then
            # reported "clear" for every text — the empty list read as "nothing
            # objectionable". §86a carries a statutory duty, so a list that
            # cannot be loaded is a check that cannot run, and a check that
            # cannot run does not grant permission. The callers all fail closed
            # on an exception; the operator sees the cause in the log.
            _BILINGUAL_86A_CACHE = None
            logger.error(f"Failed to load bilingual §86a terms: {e} — fail-closed")
            raise RuntimeError(
                f"§86a term list unavailable ({bilingual_path}): {e}"
            ) from e

    return _BILINGUAL_86A_CACHE

def fast_filter_bilingual_86a(text: str, user_language: str = 'de') -> Tuple[bool, List[str]]:
    """
    Fuzzy language-aware matching for critical §86a terms (~1-5ms)
    Uses Levenshtein distance for terms >= 6 chars to catch misspellings.
    Only checks terms for detected input language + EN.

    Returns:
        (has_terms, found_terms) - True if §86a critical terms found
    """
    terms_by_lang = load_bilingual_86a_terms()

    if not terms_by_lang:
        return (False, [])

    detected_lang = _detect_input_language(text, user_language)
    terms_list, lang_key = _get_active_terms(terms_by_lang, detected_lang)

    if not terms_list:
        return (False, [])

    found_terms = _match_86a_terms(text.lower(), terms_list)

    if found_terms:
        logger.info(f"[§86a] found {found_terms[:3]}... (lang={lang_key}, checked {len(terms_list)} of {sum(len(v) for v in terms_by_lang.values())})")
    else:
        logger.debug(f"[§86a] CLEAR (lang={lang_key}, checked {len(terms_list)})")

    return (len(found_terms) > 0, found_terms)


def _match_86a_terms(text_lower: str, terms_list: List[str]) -> List[str]:
    """The §86a terms of `terms_list` that occur in `text_lower`, in list order.

    One matcher for both readers of the list: fuzzy from six letters on
    (distance 1 up to seven, 2 from eight), a whole word up to three letters
    (keeps 'kan' out of 'scharfkantige'), a substring for four and five
    (catches 'Blut' in 'blutiger', same word stem).
    """
    found_terms = []
    for term in terms_list:
        term_lower = term.lower()
        if len(term_lower) >= 6:
            max_dist = 1 if len(term_lower) < 8 else 2
            if _fuzzy_contains(text_lower, term_lower, max_distance=max_dist):
                found_terms.append(term)
        elif len(term_lower) <= 3:
            if _word_boundary_match(text_lower, term_lower):
                found_terms.append(term)
        elif term_lower in text_lower:
            found_terms.append(term)
    return found_terms


def fast_filter_86a_all_languages(text: str) -> Tuple[bool, List[str]]:
    """The §86a lists of EVERY language in the file, on one text.

    `fast_filter_bilingual_86a` reads two of them, the language it detects and
    English, and it detects a Latin-script language only from the interface
    language it is told. A Turkish term in a text sent from a German interface
    was therefore never looked for. This reads all of them, on whatever text it
    is given. A hit decides nothing by itself: the safety gate asks the
    classifier after it (my_app/services/safety_gate.py).

    Raises like `load_bilingual_86a_terms` when the list cannot be loaded; a
    list that cannot be read is a check that cannot run.
    """
    terms_by_lang = load_bilingual_86a_terms()
    terms_list = []
    seen = set()
    for terms in terms_by_lang.values():
        for term in terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                terms_list.append(term)
    if not terms_list:
        return (False, [])
    found_terms = _match_86a_terms((text or '').lower(), terms_list)
    if found_terms:
        logger.info(f"[§86a] found {found_terms[:3]}... (all languages, checked {len(terms_list)})")
    return (len(found_terms) > 0, found_terms)

def fast_filter_check(prompt: str, safety_level: str, user_language: str = 'de') -> Tuple[bool, List[str]]:
    """
    Fuzzy language-aware matching against filter lists (~1-5ms)
    Uses Levenshtein distance for terms >= 6 chars to catch misspellings.
    Only checks terms for detected input language + EN.

    Returns:
        (has_terms, found_terms) - True if problematic terms found
    """
    filter_terms = load_filter_terms()
    terms_by_lang = filter_terms.get(safety_level)

    # stage1 is still a flat list (EN-only), not language-structured
    if safety_level == 'stage1':
        terms_list = terms_by_lang if isinstance(terms_by_lang, list) else []
        lang_key = 'en'
    elif isinstance(terms_by_lang, dict):
        detected_lang = _detect_input_language(prompt, user_language)
        terms_list, lang_key = _get_active_terms(terms_by_lang, detected_lang)
    else:
        logger.warning(f"No filter terms for safety_level '{safety_level}'")
        return (False, [])

    if not terms_list:
        logger.warning(f"No filter terms for safety_level '{safety_level}' (lang={lang_key})")
        return (False, [])

    prompt_lower = prompt.lower()
    found_terms = []
    for term in terms_list:
        term_lower = term.lower()
        if safety_level == 'stage1' and len(term_lower) >= 6:
            # §86a: Fuzzy matching needed (deliberate obfuscation like "Ha1kenkreuz")
            max_dist = 1 if len(term_lower) < 8 else 2
            if _fuzzy_contains(prompt_lower, term_lower, max_distance=max_dist):
                found_terms.append(term)
        elif len(term_lower) <= 3:
            # Very short terms: word-boundary only (prevents 'kan' in 'scharfkantige')
            if _word_boundary_match(prompt_lower, term_lower):
                found_terms.append(term)
        else:
            # Age filter (4+ chars): stem-prefix match — term must start at word boundary
            # Catches 'Blut' in 'blutiger' (same stem), rejects 'Leiche' in 'gleiche' (different word)
            if _stem_prefix_match(prompt_lower, term_lower):
                found_terms.append(term)

    if found_terms:
        total = sum(len(v) for v in terms_by_lang.values()) if isinstance(terms_by_lang, dict) else len(terms_list)
        logger.info(f"[FILTER-{safety_level.upper()}] found {found_terms[:3]}... (lang={lang_key}, checked {len(terms_list)} of {total})")

    return (len(found_terms) > 0, found_terms)

# ============================================================================
# PARSING HELPERS
# ============================================================================

def build_safety_message(codes: List[str], lang: str = 'de') -> str:
    """
    Build user-friendly safety message from safety codes using safety_code_explanations.json
    """
    explanations_path = Path(__file__).parent.parent / 'safety_code_explanations.json'

    try:
        with open(explanations_path, 'r', encoding='utf-8') as f:
            explanations = json.load(f)

        base_msg = explanations['base_message'].get(lang, explanations['base_message']['en'])
        hint_msg = explanations['hint_message'].get(lang, explanations['hint_message']['en'])

        # Build message from codes
        messages = []
        for code in codes:
            if code in explanations['codes']:
                messages.append(f"• {explanations['codes'][code].get(lang, explanations['codes'][code]['en'])}")
            else:
                messages.append(f"• Code: {code}")

        if not messages:
            return explanations['fallback'].get(lang, explanations['fallback']['en'])

        full_message = base_msg + "\n\n" + "\n".join(messages) + hint_msg
        return full_message

    except Exception as e:
        logger.error(f"Error building safety message: {e}")
        return "Dein Prompt wurde aus Sicherheitsgründen blockiert." if lang == 'de' else "Your prompt was blocked for safety reasons."

def parse_preoutput_json(output: str) -> Dict[str, Any]:
    """
    Parse output from pre-output pipeline.
    Accepts two formats:
    1. Plain text: "safe" or "unsafe" (llama-guard format)
    2. JSON: {"safe": true/false, "positive_prompt": "...", ...}
    """
    output_cleaned = output.strip().lower()

    # CASE 1: Plain text "safe"/"unsafe" from llama-guard
    # Use first line only — llama-guard sometimes repeats safe/unsafe across many lines
    first_line = output_cleaned.split('\n')[0].strip()
    if first_line == "safe":
        return {
            "safe": True,
            "positive_prompt": None,
            "negative_prompt": None,
            "abort_reason": None
        }
    elif first_line.startswith("unsafe"):
        # llama-guard returns "unsafe\nS1\nS2" etc.
        return {
            "safe": False,
            "positive_prompt": None,
            "negative_prompt": None,
            "abort_reason": "Content flagged as unsafe by safety filter"
        }

    # CASE 2: Try JSON parsing
    try:
        # Remove markdown code blocks if present
        cleaned = re.sub(r'```json\s*|\s*```', '', output.strip())
        parsed = json.loads(cleaned)

        # Validate required fields
        if 'safe' not in parsed:
            raise ValueError("Missing 'safe' field in pre-output JSON")

        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"[SAFETY] Failed to parse pre-output (fail-closed): {e}\nOutput: {output[:200]}")
        return {
            "safe": False,
            "positive_prompt": None,
            "negative_prompt": None,
            "abort_reason": "Safety check returned unparseable output (fail-closed)"
        }

# ============================================================================
# STAGE EXECUTION FUNCTIONS (For DevServer to use in Phase 3)
# ============================================================================


# Stage 1 stood here until 2026-11-01: `execute_stage1_safety_unified`, and
# before 2026-09-04 a second entry point without a caller. Its name check is
# the intake now (safety_gate.check_intake), with the recogniser, the name
# question after a hit and the question on every text where the recogniser is
# missing; it looks for addresses as well. Its §86a lists run before every
# media model and on every text a model shows (check_before_model,
# check_result_text), in every language of the list file.


# The sentence for a check that could not be carried out: no answer from the
# classifier, no translation for the check, no list to read. The run stops
# then: a run that went on without a verdict is the shape of all nine
# documented incidents. The sentence must not read as a content rating: in a
# workshop, nobody should take their own input for the cause. The operational
# way back is a restart of the GPU service.
SAFETY_CHECK_UNAVAILABLE_MESSAGE = (
    "⚠️ Technische Störung im Sicherheitssystem\n\n"
    "Die Sicherheitsprüfung konnte gerade nicht durchgeführt werden. "
    "Deine Eingabe ist NICHT der Grund und wurde nicht als problematisch eingestuft.\n\n"
    "Bitte versuche es gleich noch einmal. Wenn es wieder passiert, "
    "sag bitte der Kursleitung Bescheid."
)


# Stage 3 stood here until 2026-11-01: `execute_stage3_safety`, the check
# before a media model, and `execute_stage3_safety_code`, the check of a sketch
# a model wrote. The check before the model is safety_gate.check_before_model:
# the §86a lists of every language on the text and its translation, the
# level's question on both, adult included, and the symbol question after a
# list hit. Where a media model receives a translation, the route that calls it
# makes it (schema_pipeline_routes._translate_for_model). Code is checked at the
# result (safety_gate.check_result_code), with the same pattern list; after a
# hit the local classifier is asked where the cloud verdict model was.
