"""
Stage Orchestrator - Helper functions for 4-Stage Architecture
Extracted from pipeline_executor.py for Phase 2 refactoring

These functions will be used by DevServer (schema_pipeline_routes.py)
to orchestrate Stage 1-3, while PipelineExecutor becomes a DUMB executor.

DUMB helpers: Just execute specific stage configs, return results
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
                    # Filter: Entities containing digits or SD weight syntax (e.g., "shadow gradient:1.2")
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

def _llm_safety_check_generation(generation_prompt: str, policy) -> Dict[str, Any]:
    """
    Ask the safety classifier one yes/no question about one text.

    `policy` is an (instruct, query) pair from my_app.services.safety_classifier
    and it says WHICH question: the age question of the level that is running,
    the §86a question, the adult-reader question. It is a required argument
    because the question is the check. Until 2026-09 one fixed question in a
    borrowed category list served every level, and the level was applied
    afterwards by dropping codes from the answer -- which is how a category the
    filter did not know became a release.

    Args:
        generation_prompt: The text to check (generation prompt, or Stage-1
            input for the §86a context check).
        policy: (instruct, query), phrased so that "yes" means unsafe.

    Returns:
        {
            "safe": bool,          # True only if a verdict exists and said no
            "uncoded_unsafe": bool,# True where it answered yes
            "verdict": bool,       # False = NO USABLE VERDICT (fail-closed)
            "model_used": str,
            "execution_time": float,
            "llm_output": str      # the score, for the run log
        }

    There is no window splitting any more: the old guard carried 2400 bytes at
    a time and this one carries its whole context, so a text too long for it
    fails at the server and arrives here as no verdict, which blocks.
    """
    import config
    from my_app.services import safety_classifier

    model = config.SAFETY_MODEL

    def _no_verdict(execution_time: float, llm_output: str = "") -> Dict[str, Any]:
        return {"safe": False, "uncoded_unsafe": False, "verdict": False,
                "model_used": model, "execution_time": execution_time, "llm_output": llm_output}

    instruct, query = policy
    start = _time.time()
    try:
        value = safety_classifier.score(instruct, query, generation_prompt)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[STAGE3-SAFETY] classifier failed ({model}): {e} — no verdict")
        return _no_verdict(_time.time() - start)

    execution_time = _time.time() - start
    if value is None:
        logger.error(f"[STAGE3-SAFETY] {model} gave no verdict ({execution_time*1000:.0f}ms)")
        return _no_verdict(execution_time)

    unsafe = value >= safety_classifier.UNSAFE_THRESHOLD
    logger.info(
        f"[STAGE3-SAFETY] {model} → {'UNSAFE' if unsafe else 'SAFE'} "
        f"(score {value:.3f}, threshold {safety_classifier.UNSAFE_THRESHOLD}, "
        f"{execution_time*1000:.0f}ms)"
    )
    return {"safe": not unsafe, "uncoded_unsafe": unsafe,
            "verdict": True, "model_used": model,
            "execution_time": execution_time, "llm_output": f"score={value:.4f}"}


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

    text_lower = text.lower()
    found_terms = []
    for term in terms_list:
        term_lower = term.lower()
        if len(term_lower) >= 6:
            # Fuzzy match: distance=1 for 6-7 char terms, distance=2 for 8+ chars
            max_dist = 1 if len(term_lower) < 8 else 2
            if _fuzzy_contains(text_lower, term_lower, max_distance=max_dist):
                found_terms.append(term)
        else:
            # Very short terms (<=3 chars): word-boundary only (prevents 'kan' in 'scharfkantige')
            # 4-5 char terms: substring match (catches 'Blut' in 'blutiger', same word stem)
            if len(term_lower) <= 3:
                if _word_boundary_match(text_lower, term_lower):
                    found_terms.append(term)
            else:
                if term_lower in text_lower:
                    found_terms.append(term)

    if found_terms:
        logger.info(f"[§86a] found {found_terms[:3]}... (lang={lang_key}, checked {len(terms_list)} of {sum(len(v) for v in terms_by_lang.values())})")
    else:
        logger.debug(f"[§86a] CLEAR (lang={lang_key}, checked {len(terms_list)})")

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


# `execute_stage1_safety` stood here until 2026-09-04. It had no caller in the
# repository — only the import in schema_pipeline_routes — and on a pipeline
# failure it returned `(True, [])`, i.e. a pass, with a log line that said
# "continuing (fail-open)". It was the last place in this module that would have
# reopened the aggregation the work order closed under A1, and dead code in a
# check path is worse than a missing check: it reads like a check that runs.
# The live entry point is `execute_stage1_safety_unified` below.


async def execute_stage1_safety_unified(
    text: str,
    safety_level: str,
    pipeline_executor,
    user_language: str = 'de'
) -> Tuple[bool, str, Optional[str], List[str]]:
    """
    Execute Stage 1: Fast-Filter-First Safety Check (NO Translation)

    New Flow (eliminates LLM call in 95%+ of cases):
    1. §86a Fast-Filter (language-aware, ~0.001s)
       → Hit? → BLOCK immediately (§86a is unambiguous)
    2. Age-appropriate Fast-Filter (language-aware, ~0.001s)
       → No hit? → continue to step 3
       → Hit? → LLM Context-Check (e.g. "cute vampire" vs "scary vampire")
    3. DSGVO SpaCy NER (~50-100ms)
       → No entities? → SAFE (done, no LLM needed)
       → Entities found? → BLOCK with explanation
       → SpaCy unavailable? → LLM Fallback (DSGVO check via safety pipeline)

    Args:
        text: Input text to safety-check (in original language)
        safety_level: 'kids', 'youth', 'adult', or 'research'
        pipeline_executor: PipelineExecutor instance
        user_language: Frontend interface language (fallback for Latin-script detection)

    Returns:
        (is_safe, original_text, error_message, checks_passed)
    """
    total_start = _time.time()

    # ── Research mode: skip ALL safety checks ─────────────────────────
    if safety_level == 'research':
        logger.info(f"[STAGE1] SKIPPED (safety_level=research)")
        return (True, text, None, [])

    # ── STEP 1: §86a Fast-Filter (language-aware, ~0.001s) ─────────────
    # §86a terms trigger a classifier context check (educational/historical exemption)
    s86a_start = _time.time()
    has_86a_terms, found_86a_terms = fast_filter_bilingual_86a(text, user_language)
    s86a_time = _time.time() - s86a_start

    if has_86a_terms:
        # §86a hit — behavior depends on safety level:
        # kids/youth: HARDBLOCK (no LLM exemption — children don't need "educational context" for NS symbols)
        # adult/open: LLM context check (educational/historical context is §86a-exempt)
        # The exemption is EXPLICIT, never a default: an unknown level string
        # hardblocks like kids instead of inheriting the adult path
        # (review note 2026-08-08; today all callers are resolver-fed, which
        # already fails to 'kids' — this guards the next caller).
        if safety_level not in ('adult', 'open'):
            # Kids/Youth: §86a terms are unambiguous → immediate block, no LLM needed
            error_message = (
                f"⚠️ Dein Prompt wurde blockiert\n\n"
                f"GRUND: §86a StGB\n\n"
                f"Dein Prompt enthält Begriffe, die nach deutschem Recht verboten sind: "
                f"{', '.join(found_86a_terms[:3])}\n\n"
                f"WARUM DIESE REGEL?\n"
                f"Diese Symbole werden benutzt, um Gewalt und Hass zu verbreiten.\n"
                f"Wir schützen dich und andere vor gefährlichen Inhalten."
            )
            logger.warning(f"[STAGE1] HARDBLOCK §86a ({safety_level}): {found_86a_terms[:3]} ({s86a_time*1000:.1f}ms)")
            return (False, text, error_message, ['§86a'])

        # Adult: context check — educational and historical use of these
        # symbols is §86a-exempt, and that is what the classifier is asked, in
        # its own question (SYMBOL_POLICY). An answer that does not arrive
        # fails closed below, as everywhere in this chain.
        logger.info(f"[STAGE1] §86a hit: {found_86a_terms[:3]} → classifier context check ({s86a_time*1000:.1f}ms)")
        from my_app.services.safety_classifier import SYMBOL_POLICY
        llm_result = _llm_safety_check_generation(text, SYMBOL_POLICY)
        llm_time = llm_result["execution_time"]

        if not llm_result["verdict"]:
            error_message = (
                f"⚠️ Dein Prompt wurde blockiert\n\n"
                f"GRUND: §86a StGB — Sicherheitssystem nicht erreichbar\n\n"
                f"Dein Prompt enthält Begriffe, die nach deutschem Recht verboten sein können: "
                f"{', '.join(found_86a_terms[:3])}\n\n"
                f"Das Sicherheitssystem konnte den Kontext nicht prüfen.\n"
                f"Bitte versuche es erneut."
            )
            logger.warning(f"[STAGE1] §86a: no verdict → fail-closed ({llm_time:.1f}s)")
            return (False, text, error_message, ['§86a'])

        is_safe = llm_result["safe"]

        if not is_safe:
            error_message = (
                f"⚠️ Dein Prompt wurde blockiert\n\n"
                f"GRUND: §86a StGB\n\n"
                f"Dein Prompt enthält Begriffe, die nach deutschem Recht verboten sind: "
                f"{', '.join(found_86a_terms[:3])}\n\n"
                f"WARUM DIESE REGEL?\n"
                f"Diese Symbole werden benutzt, um Gewalt und Hass zu verbreiten.\n"
                f"Wir schützen dich und andere vor gefährlichen Inhalten."
            )
            logger.warning(f"[STAGE1] BLOCKED §86a (classifier confirmed, {llm_result.get('llm_output', '')}) ({llm_time:.1f}s)")
            return (False, text, error_message, ['§86a'])
        else:
            # The classifier says no → educational context → continue for adults
            logger.info(f"[STAGE1] §86a educational exemption (adult, classifier: safe, {llm_time:.1f}s)")

    # ── STEP 2: DSGVO SpaCy NER (~50-100ms) or LLM Fallback ──────────
    # DSGVO runs BEFORE age filter to ensure no personal data leaves local system.
    # This allows the age filter (Step 3) to safely use external LLMs (gpt-oss-120b)
    # for context verification — DSGVO already guaranteed no personal names in text.
    checks_passed = ['§86a']

    dsgvo_start = _time.time()
    has_personal_data, found_entities, spacy_available = fast_dsgvo_check(text)
    dsgvo_time = _time.time() - dsgvo_start

    if spacy_available and has_personal_data:
        # NER triggered — LLM verification to avoid false positives
        # (SpaCy flags technical terms like "Agrarische Funktionszone" or "muted earth tones:1.1")
        logger.info(f"[STAGE1] DSGVO NER triggered: {found_entities[:3]} — verifying with LLM")
        verify_result = llm_personal_data_check(text, found_entities)
        if verify_result is None:
            # LLM unavailable — fail-closed
            error_message = (
                "Sicherheitssystem reagiert nicht, daher kann keine weitere "
                "Verarbeitung erfolgen. Bitte den Systemadministrator kontaktieren."
            )
            checks_passed.append('dsgvo_ner')
            logger.error(f"[STAGE1] BLOCKED — LLM verification unavailable (fail-closed)")
            return (False, text, error_message, checks_passed)
        elif verify_result:
            # LLM confirmed real names → BLOCK
            entities_str = ', '.join(found_entities[:5])
            error_message = (
                f"⚠️ Dein Prompt wurde blockiert\n\n"
                f"GRUND: DSGVO - Persönliche Daten erkannt\n\n"
                f"Folgende persönliche Daten wurden in deinem Prompt gefunden:\n"
                f"{entities_str}\n\n"
                f"WARUM DIESE REGEL?\n"
                f"Der Schutz persönlicher Daten (DSGVO) verbietet die Verarbeitung von Namen, "
                f"Adressen und Kontaktdaten ohne Einwilligung.\n"
                f"Bitte verwende Phantasienamen oder beschreibe Personen ohne echte Namen."
            )
            checks_passed.append('dsgvo_ner')
            checks_passed.append('dsgvo_llm_verify')
            logger.warning(f"[STAGE1] BLOCKED DSGVO (LLM confirmed): {found_entities[:3]} ({dsgvo_time*1000:.1f}ms)")
            return (False, text, error_message, checks_passed)
        else:
            # False positive (LLM rejected) → allow
            logger.info(f"[STAGE1] DSGVO NER false positive (LLM rejected): {found_entities[:3]}")

    elif spacy_available and not has_personal_data:
        # SpaCy clean → SAFE
        checks_passed.append('dsgvo_ner')

    elif not spacy_available:
        # SpaCy NOT available → direct LLM check for personal names
        logger.warning(f"[STAGE1] SpaCy unavailable → LLM fallback for DSGVO check")
        llm_start = _time.time()
        dsgvo_result = llm_personal_data_check(text)
        llm_time = _time.time() - llm_start

        if dsgvo_result is None:
            # LLM unavailable → fail-closed
            error_message = (
                "Sicherheitssystem reagiert nicht, daher kann keine weitere "
                "Verarbeitung erfolgen. Bitte den Systemadministrator kontaktieren."
            )
            checks_passed.append('dsgvo_llm')
            logger.warning(f"[STAGE1] DSGVO LLM fallback unavailable → fail-closed ({llm_time:.1f}s)")
            return (False, text, error_message, checks_passed)
        elif dsgvo_result:
            # LLM found personal names → BLOCK
            error_message = (
                f"⚠️ Dein Prompt wurde blockiert\n\n"
                f"GRUND: DSGVO - Persönliche Daten erkannt\n\n"
                f"Dein Prompt enthält möglicherweise persönliche Daten.\n\n"
                f"WARUM DIESE REGEL?\n"
                f"Der Schutz persönlicher Daten (DSGVO) verbietet die Verarbeitung von Namen, "
                f"Adressen und Kontaktdaten ohne Einwilligung.\n"
                f"Bitte verwende Phantasienamen oder beschreibe Personen ohne echte Namen."
            )
            checks_passed.append('dsgvo_llm')
            logger.warning(f"[STAGE1] BLOCKED DSGVO (LLM fallback confirmed, {llm_time:.1f}s)")
            return (False, text, error_message, checks_passed)
        else:
            # LLM says no personal names → safe
            checks_passed.append('dsgvo_llm')
            logger.info(f"[STAGE1] DSGVO LLM fallback: SAFE ({llm_time:.1f}s)")

    # Jugendschutz (kids/youth) is handled by Stage 2 safety prefix — not in Stage 1.

    # ── ALL CHECKS PASSED ──────────────────────────────────────────────
    total_time = _time.time() - total_start
    logger.info(f"[STAGE1] SAFE ({total_time*1000:.1f}ms total, checks: {checks_passed})")
    return (True, text, None, checks_passed)


# Decision 1 (work order §6.1): when the safety model yields no verdict, the
# run STOPS. The §86a word filter and the name check run locally and have
# already passed by the time this message can appear; the age judgement's
# second carrier is the Stage-2 safety preamble. What is missing without a
# verdict is the Llama-Guard assessment — and a run that continues without it
# is exactly the shape of all nine documented incidents. The message must not
# read as a content rating: in a workshop, nobody should take their own input
# for the cause. The operational way back is a restart of the GPU service.
SAFETY_CHECK_UNAVAILABLE_MESSAGE = (
    "⚠️ Technische Störung im Sicherheitssystem\n\n"
    "Die Sicherheitsprüfung konnte gerade nicht durchgeführt werden. "
    "Deine Eingabe ist NICHT der Grund und wurde nicht als problematisch eingestuft.\n\n"
    "Bitte versuche es gleich noch einmal. Wenn es wieder passiert, "
    "sag bitte der Kursleitung Bescheid."
)


async def execute_stage3_safety(
    prompt: str,
    safety_level: str,
    media_type: str,
    pipeline_executor,
    user_language: str = 'de',
    device_id: Optional[str] = None,
    force_translation: bool = False,
    translation_instruction: Optional[str] = None,
    as_given: bool = False,
) -> Dict[str, Any]:
    """
    Execute Stage 3: Pre-Output Safety Check (Jugendschutz)

    Tiered translation behavior:
    - research/adult: No translation, no safety check — original prompt to model
    - kids: Translate to English, run safety, pass TRANSLATED prompt to model
    - youth: Translate to English internally for safety check, pass ORIGINAL prompt to model
    - force_translation=True overrides the prompt choice only: the model always
      gets the English translation (t2x flow, which has no translate button);
      each level's safety behavior stays exactly as it was.
    - as_given=True: the text reaches the model as it was written, not as
      translated -- a text the output chunk reads itself (the song's lyrics and
      style tags). The classifier reads it as written, at kids the translation
      as well, and the run stops if either is refused; the positive prompt is
      the text as given.

    This decouples translation-for-safety from translation-for-generation.
    Youth+ users can explore how models react to their native language.
    The translate button in MediaInputBox remains available for manual use.

    Steps:
    1. research/adult → return original prompt immediately
    2. Translate to English (for kids/youth safety check)
    3. §86a fast-filter on translated text (instant block)
    4. Determine generation prompt (kids=translated, youth=original)
    5. Single Llama-Guard check with proper S1-S13 template on generation prompt

    Args:
        prompt: Prompt to check before media generation
        safety_level: 'kids', 'youth', 'adult', or 'research'
        media_type: Type of media being generated (for logging)
        pipeline_executor: PipelineExecutor instance
        user_language: Frontend interface language (fallback for Latin-script detection)

    Returns:
        {
            "safe": bool,
            "method": "disabled" | "86a_filter" | "llm_safety_check" | "llm_check_failed",
            "abort_reason": str | None,
            "positive_prompt": str | None,
            "negative_prompt": str | None
        }
    """
    import time

    # STEP 1: research/adult — no safety check; without forced translation the
    # original prompt goes straight to the model.
    if safety_level in ('research', 'adult') and not force_translation:
        return {
            "safe": True,
            "method": "disabled",
            "abort_reason": None,
            "positive_prompt": prompt,
            "negative_prompt": ""
        }

    # STEP 2: Translate to English (for safety check on kids/youth)
    # Reuse only within one device bucket to avoid cross-device prompt bleed.
    cached_translation = _get_translation_cache_entry(device_id)
    instruction_key = (translation_instruction or '').strip()
    if (
        cached_translation is not None
        and prompt == cached_translation.get('untranslated')
        and cached_translation.get('instruction', '') == instruction_key
        and cached_translation.get('translated') is not None
    ):
        translated_prompt = cached_translation['translated']
        translate_time = 0
        logger.info(
            f"[STAGE3-TRANSLATION] Reused for device {device_id}: "
            f"{translated_prompt[:150]}..."
        )
    else:
        translate_start = time.time()
        translate_result = await pipeline_executor.execute_pipeline(
            'pre_output/translation_en',  # Translation config (just translate chunk)
            prompt,
            context_override=translation_context(prompt, translation_instruction),
        )
        translate_time = time.time() - translate_start

        if translate_result.success:
            translated_prompt = translate_result.final_output
            _update_translation_cache(device_id, prompt, translated_prompt, instruction_key)
            logger.info(f"[STAGE3-TRANSLATION] Translated in {translate_time:.2f}s: {translated_prompt[:150]}...")
        else:
            # No translation, and therefore no text this stage can check: the §86a
            # filter below reads English term lists. The original prompt is NOT used
            # as a stand-in -- that would run the last gate on Stage-2-generated text
            # in a language it cannot read.
            translated_prompt = None
            logger.error(
                "[STAGE3-TRANSLATION] Translation failed — run stops (fail-closed); "
                "operational error, not a content rating"
            )

    # research/adult with forced translation: hand back what translation produced
    # and keep the no-safety-check contract of these levels. These levels run no
    # check, so a missing translation falls back to the original text here and only
    # here -- it is handed to generation untranslated, not to a gate.
    if safety_level in ('research', 'adult'):
        translated_prompt = translated_prompt if translated_prompt is not None else prompt
        return {
            "safe": True,
            "method": "disabled",
            "abort_reason": None,
            "positive_prompt": translated_prompt,
            "negative_prompt": "",
            "execution_time": translate_time
        }

    # A failed translation stops the run. Same shape as the missing-verdict case
    # below: an operational failure, distinguishable from a content rejection.
    if translated_prompt is None:
        return {
            "safe": False,
            "method": "translation_failed",
            "abort_reason": SAFETY_CHECK_UNAVAILABLE_MESSAGE,
            "positive_prompt": None,
            "negative_prompt": None,
            "execution_time": translate_time
        }

    # STEP 3: §86a fast-filter on translated text — use 'en'. Reached only when
    # translation succeeded, so the text really is English.
    has_86a, found_86a = fast_filter_bilingual_86a(translated_prompt, 'en')
    if has_86a:
        logger.warning(f"[STAGE3-SAFETY] §86a BLOCKED: {found_86a[:3]}")
        return {
            "safe": False,
            "method": "86a_filter",
            "abort_reason": f'§86a StGB: {", ".join(found_86a[:3])}',
            "positive_prompt": None,
            "negative_prompt": None,
            "execution_time": translate_time
        }

    # STEP 4: Determine generation prompt by safety level
    # kids → auto-translated English (better model output, full guardrails)
    # youth → original language (user explores model behavior, manual translate available)
    generation_prompt = translated_prompt if (safety_level == 'kids' or force_translation) else prompt
    classified = [generation_prompt]
    if as_given:
        # Until 2026-10-01 a text the chunk read itself was classified as its
        # translation at kids, so a translation that came out milder than the
        # text -- or that did what a line in the text told it to -- passed a
        # text the model then received untouched.
        generation_prompt = prompt
        classified = [translated_prompt, prompt] if safety_level == 'kids' else [prompt]

    # STEP 5: the safety classifier, asked the question of the level that is
    # running. The level used to reach the check only afterwards, as a filter
    # over the category codes a chat-trained guard had answered in; every code
    # the filter did not know was a release, and the numbering the template used
    # was not the numbering the model card declares. The question carries the
    # level now, and the answer is one yes or no about it.
    from my_app.services.safety_classifier import policy_for_level

    policy = policy_for_level(safety_level)
    logger.info(f"[STAGE3-SAFETY] Running the safety classifier ({safety_level}) on the generation prompt")
    for text in classified:
        llm_result = _llm_safety_check_generation(text, policy)
        if not llm_result["verdict"] or llm_result["uncoded_unsafe"]:
            break

    # Work order A1 / decision 1: no verdict → the run stops, and the message
    # names an operational failure, distinguishable from a content rejection.
    # The old aggregation read empty codes from a failed call as a pass —
    # every documented incident had that shape. Blocking is bound to a
    # verdict that actually exists.
    if not llm_result["verdict"]:
        logger.error(
            f"[STAGE3-SAFETY] NO VERDICT from {llm_result['model_used']} — run stops (fail-closed); "
            f"operational error, not a content rating"
        )
        return {
            "safe": False,
            "method": "llm_check_failed",
            "abort_reason": SAFETY_CHECK_UNAVAILABLE_MESSAGE,
            "positive_prompt": None,
            "negative_prompt": None,
            "model_used": llm_result["model_used"],
            "execution_time": translate_time + llm_result["execution_time"],
            "llm_output": llm_result.get("llm_output", ""),
        }

    # The verdict is one answer to the question of the running level, so there
    # is no category list left to filter and no second model left to ask. Both
    # were Llama-Guard machinery: its taxonomy answered one fixed question, and
    # what this platform actually needed was applied to that answer afterwards
    # — by dropping the codes an image cannot carry, and by re-asking a cloud
    # model about the two codes deemed over-eager. Every code the filter did
    # not know was a release. The classifier is asked this platform's question
    # itself now, so the answer needs neither correction.
    is_safe = not llm_result["uncoded_unsafe"]

    if is_safe:
        logger.info(f"[STAGE3-SAFETY] PASSED ({llm_result['execution_time']:.1f}s), using {'translated' if (safety_level == 'kids' or force_translation) and not as_given else 'original'} prompt for generation")
        return {
            "safe": True,
            "method": "llm_safety_check",
            "abort_reason": None,
            "positive_prompt": generation_prompt,
            "negative_prompt": "",
            "model_used": llm_result["model_used"],
            "execution_time": translate_time + llm_result["execution_time"]
        }
    else:
        logger.warning(f"[STAGE3-SAFETY] BLOCKED ({llm_result['execution_time']:.1f}s, {llm_result.get('llm_output', '')})")
        return {
            "safe": False,
            "method": "llm_safety_check",
            "abort_reason": "Content blocked by safety filter",
            "positive_prompt": None,
            "negative_prompt": None,
            "model_used": llm_result["model_used"],
            "execution_time": llm_result["execution_time"],
            "llm_output": llm_result.get("llm_output", ""),
            "found_terms": []
        }


# ============================================================================
# SESSION 84: STAGE 3 SAFETY CHECK FOR CODE OUTPUT
# ============================================================================

async def execute_stage3_safety_code(
    code: str,
    safety_level: str,
    media_type: str,
) -> dict:
    """
    Stage 3 Safety Check for Code Output (P5.js, SonicPi, etc.)

    Checks generated code for unsafe patterns without translation.
    Uses fast filter + conditional LLM verification.

    Args:
        code: Generated code (JavaScript, Ruby, etc.)
        safety_level: Safety level ('kids', 'youth', 'research')
        media_type: Media type ('code')

    Returns:
        dict: Safety result with structure:
            {
                'safe': bool,
                'positive_prompt': str (original code if safe),
                'method': str,
                'abort_reason': Optional[str],
                'patterns_found': Optional[List[str]],
                'execution_time': float
            }
    """
    from datetime import datetime

    start_time = datetime.now()

    logger.info(f"[STAGE3-CODE] Safety check for code (level: {safety_level})")

    # If safety is research or adult, skip all checks
    if safety_level in ('research', 'adult'):
        logger.info(f"[STAGE3-CODE] Safety level '{safety_level}' → allowing code")
        return {
            'safe': True,
            'positive_prompt': code,
            'method': 'safety_off',
            'execution_time': (datetime.now() - start_time).total_seconds()
        }

    # Fast filter: Check for dangerous code patterns
    UNSAFE_CODE_PATTERNS = [
        'eval(',
        'Function(',
        'document.cookie',
        'localStorage.',
        'sessionStorage.',
        'fetch(',
        'XMLHttpRequest',
        'import(',
        'require(',
        '<script',
        '</script',
        'innerHTML',
        'outerHTML',
        'document.write',
        'setTimeout(',
        'setInterval('
    ]

    found_patterns = []
    code_lower = code.lower()
    for pattern in UNSAFE_CODE_PATTERNS:
        if pattern.lower() in code_lower:
            found_patterns.append(pattern)

    if not found_patterns:
        # FAST PATH: No unsafe patterns detected
        logger.info(f"[STAGE3-CODE] Safety check passed (fast filter, no patterns found)")
        return {
            'safe': True,
            'positive_prompt': code,
            'method': 'fast_filter',
            'execution_time': (datetime.now() - start_time).total_seconds()
        }

    # SLOW PATH: the fast filter flagged something → ask the verdict model
    # whether the pattern is dangerous in THIS code.
    logger.warning(f"[STAGE3-CODE] Found patterns: {found_patterns} → verdict model")

    verification_prompt = (
        "You are a code safety reviewer for an educational creative-coding "
        "environment used by children.\n\n"
        "A generated sketch contains patterns a fast filter flags: "
        f"{', '.join(found_patterns)}\n\n"
        "The sketch runs in a sandboxed iframe. Decide whether these patterns "
        "are used in a way that is dangerous there — reaching out of the "
        "sandbox, contacting the network, reading or writing browser storage, "
        "injecting markup, or executing text as code — or whether this is "
        "ordinary creative-coding use.\n\n"
        "Code:\n"
        "```\n"
        f"{code}\n"
        "```\n\n"
        "Answer SAFE or UNSAFE."
    )

    # The call this check used to make was
    # `pipeline_executor.execute_chunk_async`, a method that has never existed
    # on PipelineExecutor. It was written in 6ce8456f on 2025-12-01 ("WIP:
    # Broken p5.js implementation"), and for the nine months after that every
    # flagged p5.js and SonicPi output raised AttributeError here and was handed
    # to the child with the flagged pattern still in it.
    #
    # A check asks a model directly, and it asks the one it was configured to
    # ask. `_call_verdict_model` is this platform's single adjudication call
    # (STAGE3_MODEL, no fallback chain, no output cap, `finish_reason` carried
    # back), already shared with the image check and the S4/S8 escalation, and
    # `_extract_verdict` is the one reader for its answer. Llama-Guard is the
    # wrong model for this question — it answers its own S1-S13 template, not a
    # free-form question about JavaScript — and the model that wrote the sketch
    # must not be the one to rate it.
    from my_app.utils.vlm_safety import _call_verdict_model, _extract_verdict

    def _no_verdict(why: str) -> dict:
        """A check that could not be carried out. It withholds the code, and it
        says so as a technical fault: the child's own sketch is not the cause,
        and the message must not read as a rating of it."""
        logger.error(f"[STAGE3-CODE] {why} — run stops (fail-closed); operational error, not a content rating")
        return {
            'safe': False,
            'positive_prompt': None,
            'abort_reason': SAFETY_CHECK_UNAVAILABLE_MESSAGE,
            'method': 'llm_check_failed',
            'patterns_found': found_patterns,
            'execution_time': (datetime.now() - start_time).total_seconds()
        }

    try:
        response, finish_reason = _call_verdict_model(verification_prompt)
    except Exception as e:
        # An exception is the absence of a verdict, and the absence of a verdict
        # is not permission (work order §6 decision 1).
        return _no_verdict(f"verdict model raised {e!r}")

    if not response:
        return _no_verdict("verdict model unreachable or answered empty")

    if finish_reason == 'length':
        # A truncated answer is cut-off reasoning, not a rating (work order A12).
        return _no_verdict("verdict truncated (finish_reason=length)")

    verdict = _extract_verdict(response)
    if verdict is None:
        return _no_verdict(f"no readable verdict in {response[:120]!r}")

    if verdict == 'safe':
        logger.info(f"[STAGE3-CODE] Verdict SAFE despite {found_patterns}")
        return {
            'safe': True,
            'positive_prompt': code,
            'method': 'llm_context_check',
            'patterns_found': found_patterns,
            'execution_time': (datetime.now() - start_time).total_seconds()
        }

    logger.warning(f"[STAGE3-CODE] Verdict UNSAFE for {found_patterns} — blocked")
    return {
        'safe': False,
        'positive_prompt': None,
        # The platform's existing wording for a content block with no S-code.
        # There is no code-specific German sentence in the tree; inventing one
        # is not this change's to make.
        'abort_reason': build_safety_message([]),
        'method': 'llm_context_check',
        'patterns_found': found_patterns,
        'execution_time': (datetime.now() - start_time).total_seconds()
    }
