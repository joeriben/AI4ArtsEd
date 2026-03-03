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
import time as _time

logger = logging.getLogger(__name__)

# Translation reuse: skip API call if prompt unchanged since last translation
_last_untranslated: Optional[str] = None
_last_translated: Optional[str] = None

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


def _fuzzy_contains(text_lower: str, term: str, max_distance: int = 2) -> bool:
    """Check if any word/phrase in text fuzzy-matches term within Levenshtein distance"""
    term_len = len(term)
    words = text_lower.split()

    if ' ' in term:
        # Multi-word term (e.g., "heil hitler"): check word combinations
        term_word_count = len(term.split())
        for i in range(len(words)):
            for j in range(i + 1, min(i + term_word_count + 1, len(words) + 1)):
                combo = ' '.join(words[i:j])
                if abs(len(combo) - term_len) <= max_distance:
                    if _levenshtein(combo, term) <= max_distance:
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


def llm_verify_person_name(text: str, ner_entities: list) -> Optional[bool]:
    """
    LLM verification for SpaCy NER PER-entity hits.

    SpaCy NER produces false positives (e.g. "Agrarische Funktionszone" → PER,
    "muted earth tones:1.1" → PER). This function asks a LOCAL LLM whether
    the detected entities are real personal names before blocking.

    IMPORTANT: Always local (Ollama) — NEVER external APIs.
    Personal names must not leave the local system (DSGVO).

    Model selection: STAGE1_TEXT_MODEL if local, else SAFETY_MODEL fallback.

    Args:
        text: The original user text
        ner_entities: List of NER-detected entity strings (e.g. ["Name: Agrarische Funktionszone"])

    Returns:
        True if LLM confirms real person name(s).
        False if LLM rejects (false positive).
        None if LLM unavailable or returns empty (fail-closed).
    """
    import config

    # Extract just the name parts from "Name: ..." format
    names = [e.replace("Name: ", "") for e in ner_entities]
    names_str = ", ".join(names)

    # Resolve local Ollama model for DSGVO NER verification.
    # DSGVO: personal names must NEVER leave the local system — Ollama only.
    model = config.DSGVO_VERIFY_MODEL
    # Strip local/ prefix for Ollama
    ollama_model = model.replace("local/", "") if model.startswith("local/") else model

    prompt = (
        f"A text analysis system flagged the following words as person names. "
        f"Are they actually person names, or false positives?\n\n"
        f"Flagged words: {names_str}\n"
        f"Original text: \"{text}\"\n\n"
        f"Rules:\n"
        f"- Actual person names (real or fictional) = UNSAFE\n"
        f"- Descriptions, adjectives, materials, places, objects, technical terms = SAFE\n\n"
        f"Answer ONLY with SAFE or UNSAFE."
    )
    messages = [{"role": "user", "content": prompt}]

    try:
        from my_app.services.llm_backend import get_llm_backend
        from config import OLLAMA_TIMEOUT_SAFETY

        start = _time.time()
        llm_result = get_llm_backend().chat(
            model=ollama_model,
            messages=messages,
            temperature=0.0,
            max_new_tokens=500,
            timeout=OLLAMA_TIMEOUT_SAFETY,
        )
        duration_ms = (_time.time() - start) * 1000

        if llm_result is None:
            logger.error(
                f"[DSGVO-LLM-VERIFY] entities={names_str} → LLM ({ollama_model}) returned None "
                f"({duration_ms:.0f}ms) — fail-closed"
            )
            return None

        result = llm_result.get("content", "").strip()

        # Thinking model fallback: Thinking models put reasoning in 'thinking', answer in 'content'.
        # Under VRAM pressure, 'content' may be empty — extract SAFE/UNSAFE from 'thinking'.
        if not result:
            thinking = (llm_result.get("thinking") or "").strip()
            if thinking:
                logger.info(f"[DSGVO-LLM-VERIFY] content empty, checking thinking field ({len(thinking)} chars)")
                thinking_upper = thinking.upper()
                if "UNSAFE" in thinking_upper:
                    result = "UNSAFE"
                elif "SAFE" in thinking_upper:
                    result = "SAFE"

        if not result:
            logger.error(
                f"[DSGVO-LLM-VERIFY] entities={names_str} → LLM ({ollama_model}) returned EMPTY "
                f"({duration_ms:.0f}ms) — fail-closed"
            )
            return None

        result_upper = result.upper().strip()
        # "UNSAFE" must be checked first — "SAFE" is a substring of "UNSAFE"
        is_real_name = result_upper.startswith("UNSAFE")
        logger.info(
            f"[DSGVO-LLM-VERIFY] entities={names_str} → LLM={result!r} → "
            f"{'UNSAFE — real person identified' if is_real_name else 'SAFE'} ({duration_ms:.0f}ms)"
        )
        return is_real_name

    except Exception as e:
        logger.error(f"[DSGVO-LLM-VERIFY] LLM verification failed ({ollama_model}): {e} — fail-closed")
        return None


def llm_dsgvo_fallback_check(text: str) -> Optional[bool]:
    """
    Direct LLM check for personal names when SpaCy is unavailable.

    Unlike llm_verify_person_name() (which verifies SpaCy NER hits),
    this function asks the LLM to *discover* personal names in the text.
    Used only as a fallback when SpaCy models can't be loaded.

    Uses DSGVO_VERIFY_MODEL (local Ollama) — personal names must NEVER
    leave the local system.

    Returns:
        True if LLM finds personal names (block).
        False if no personal names found (safe).
        None if LLM unavailable (fail-closed).
    """
    import config

    model = config.DSGVO_VERIFY_MODEL
    ollama_model = model.replace("local/", "") if model.startswith("local/") else model

    prompt = (
        f"Does the following text contain real person names (first names, last names, "
        f"or full names of real people)?\n\n"
        f"Text: \"{text}\"\n\n"
        f"Rules:\n"
        f"- Real person names (Angela Merkel, Hans Müller, etc.) = UNSAFE\n"
        f"- Fictional/fantasy names in creative context = SAFE\n"
        f"- Descriptions, adjectives, places, objects = SAFE\n"
        f"- No names at all = SAFE\n\n"
        f"Answer ONLY with SAFE or UNSAFE."
    )
    messages = [{"role": "user", "content": prompt}]

    try:
        from my_app.services.llm_backend import get_llm_backend
        from config import OLLAMA_TIMEOUT_SAFETY

        start = _time.time()
        llm_result = get_llm_backend().chat(
            model=ollama_model,
            messages=messages,
            temperature=0.0,
            max_new_tokens=500,
            timeout=OLLAMA_TIMEOUT_SAFETY,
        )
        duration_ms = (_time.time() - start) * 1000

        if llm_result is None:
            logger.error(f"[DSGVO-LLM-FALLBACK] LLM ({ollama_model}) returned None ({duration_ms:.0f}ms) — fail-closed")
            return None

        result = llm_result.get("content", "").strip()

        # Thinking model fallback
        if not result:
            thinking = (llm_result.get("thinking") or "").strip()
            if thinking:
                logger.info(f"[DSGVO-LLM-FALLBACK] content empty, checking thinking field ({len(thinking)} chars)")
                thinking_upper = thinking.upper()
                if "UNSAFE" in thinking_upper:
                    result = "UNSAFE"
                elif "SAFE" in thinking_upper:
                    result = "SAFE"

        if not result:
            logger.error(f"[DSGVO-LLM-FALLBACK] LLM ({ollama_model}) returned EMPTY ({duration_ms:.0f}ms) — fail-closed")
            return None

        result_upper = result.upper().strip()
        has_names = result_upper.startswith("UNSAFE")
        logger.info(
            f"[DSGVO-LLM-FALLBACK] LLM={result!r} → "
            f"{'UNSAFE — personal names found' if has_names else 'SAFE'} ({duration_ms:.0f}ms)"
        )
        return has_names

    except Exception as e:
        logger.error(f"[DSGVO-LLM-FALLBACK] LLM failed ({ollama_model}): {e} — fail-closed")
        return None


# Llama-Guard template (loaded once from safety_llamaguard.json)
_LLAMAGUARD_TEMPLATE: Optional[str] = None

def _get_llamaguard_template() -> str:
    """Load Llama-Guard prompt template from safety config (cached)."""
    global _LLAMAGUARD_TEMPLATE
    if _LLAMAGUARD_TEMPLATE is None:
        config_path = Path(__file__).parent.parent / "configs" / "pre_interception" / "safety_llamaguard.json"
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        _LLAMAGUARD_TEMPLATE = config_data["context"]
    return _LLAMAGUARD_TEMPLATE


# Cache for age-filter LLM verification results (prevents inconsistent re-checks)
# Key: (text, safety_level), Value: (result, timestamp)
_AGE_VERIFY_CACHE: Dict[tuple, tuple] = {}
_AGE_VERIFY_CACHE_TTL = 60  # seconds


def llm_verify_age_filter_context(text: str, found_terms: list, safety_level: str) -> Optional[bool]:
    """
    LLM context verification for age-filter fast-filter hits.

    Uses Llama-Guard-3 (SAFETY_MODEL) — NOT DSGVO model.
    Llama-Guard gets ONLY the user text, classifies safe/unsafe.

    Results are cached for 60s to prevent inconsistent answers when
    /safety/quick and [UNIFIED-STREAMING] check the same text.

    Args:
        text: The original user text
        found_terms: List of filter terms that matched
        safety_level: 'kids' or 'youth'

    Returns:
        True if LLM confirms content is inappropriate (block).
        False if LLM says benign context (allow).
        None if LLM unavailable (fail-closed).
    """
    import config

    # Cache lookup — prevents inconsistent re-checks within TTL
    cache_key = (text.strip().lower(), safety_level)
    now = _time.time()
    if cache_key in _AGE_VERIFY_CACHE:
        cached_result, cached_time = _AGE_VERIFY_CACHE[cache_key]
        if now - cached_time < _AGE_VERIFY_CACHE_TTL:
            logger.info(f"[AGE-LLM-VERIFY] Cache hit → {'UNSAFE' if cached_result else 'SAFE'} (age={now - cached_time:.0f}s)")
            return cached_result

    terms_str = ", ".join(found_terms[:5])
    model = config.SAFETY_MODEL  # llama-guard3, NOT DSGVO model

    # Build Llama-Guard prompt (same template as Stage 1)
    template = _get_llamaguard_template()
    prompt = template.replace("{{PREVIOUS_OUTPUT}}", text)

    try:
        from my_app.services.llm_backend import get_llm_backend
        from config import OLLAMA_TIMEOUT_SAFETY

        start = _time.time()
        llm_result = get_llm_backend().generate(
            model=model,
            prompt=prompt,
            temperature=0.0,
            max_new_tokens=50,
            timeout=OLLAMA_TIMEOUT_SAFETY,
            enable_thinking=False,
        )
        duration_ms = (_time.time() - start) * 1000

        if llm_result is None:
            logger.error(f"[AGE-LLM-VERIFY] terms={terms_str} → Llama-Guard ({model}) returned None ({duration_ms:.0f}ms) — fail-closed")
            return None

        output = llm_result.get("response", "").strip()
        if not output:
            logger.error(f"[AGE-LLM-VERIFY] terms={terms_str} → Llama-Guard ({model}) returned EMPTY ({duration_ms:.0f}ms) — fail-closed")
            return None

        is_safe, codes = parse_llamaguard_output(output)
        is_unsafe = not is_safe

        logger.info(
            f"[AGE-LLM-VERIFY] terms={terms_str} → Llama-Guard={output!r} → "
            f"{'UNSAFE ' + str(codes) if is_unsafe else 'SAFE — false positive'} ({duration_ms:.0f}ms)"
        )
        _AGE_VERIFY_CACHE[cache_key] = (is_unsafe, _time.time())
        return is_unsafe

    except Exception as e:
        logger.error(f"[AGE-LLM-VERIFY] Llama-Guard failed ({model}): {e} — fail-closed")
        return None


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
            logger.info(f"Loaded §86a critical terms: {total} terms ({len(_BILINGUAL_86A_CACHE)} langs)")
        except Exception as e:
            logger.error(f"Failed to load bilingual §86a terms: {e}")
            _BILINGUAL_86A_CACHE = {}

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
        if len(term_lower) >= 6:
            # Fuzzy match: distance=1 for 6-7 char terms, distance=2 for 8+ chars
            # (distance=2 on 6-char words gives 33% error rate → false positives like "Potter"→"Folter")
            max_dist = 1 if len(term_lower) < 8 else 2
            if _fuzzy_contains(prompt_lower, term_lower, max_distance=max_dist):
                found_terms.append(term)
        else:
            # Very short terms (<=3 chars): word-boundary only (prevents 'kan' in 'scharfkantige')
            # 4-5 char terms: substring match (catches 'Blut' in 'blutiger', same word stem)
            if len(term_lower) <= 3:
                if _word_boundary_match(prompt_lower, term_lower):
                    found_terms.append(term)
            else:
                if term_lower in prompt_lower:
                    found_terms.append(term)

    if found_terms:
        total = sum(len(v) for v in terms_by_lang.values()) if isinstance(terms_by_lang, dict) else len(terms_list)
        logger.info(f"[FILTER-{safety_level.upper()}] found {found_terms[:3]}... (lang={lang_key}, checked {len(terms_list)} of {total})")

    return (len(found_terms) > 0, found_terms)

# ============================================================================
# PARSING HELPERS
# ============================================================================

def parse_llamaguard_output(output: str) -> Tuple[bool, List[str]]:
    """
    Parse Llama-Guard output format:
    "safe" → (True, [])
    "unsafe\nS1,S3" → (False, ['S1', 'S3'])
    "unsafe,S8, Violent Crimes" → (False, ['S8'])
    """
    lines = output.strip().split('\n')
    first_line = lines[0].strip()
    first_line_lower = first_line.lower()

    if first_line_lower == 'safe':
        return (True, [])
    elif first_line_lower.startswith('unsafe'):
        # Handle two formats:
        # Format 1: "unsafe\nS1,S3" (two lines)
        # Format 2: "unsafe,S8, Violent Crimes" (one line with comma)

        if ',' in first_line:
            # Format 2: Extract codes from first line after "unsafe,"
            # Use original case-preserved string for S-code extraction
            parts = first_line.split(',', 1)[1].strip()
            # Extract S-codes (S1, S2, etc.) - case insensitive
            codes = re.findall(r'[Ss]\d+', parts)
            # Normalize to uppercase
            codes = [code.upper() for code in codes]
            return (False, codes)
        elif len(lines) > 1:
            # Format 1: Codes on second line
            codes = [code.strip() for code in lines[1].split(',')]
            return (False, codes)
        return (False, [])
    else:
        # Unexpected format
        logger.warning(f"Unexpected Llama-Guard output format: {output[:100]}")
        return (True, [])  # Default to safe if uncertain

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

async def execute_stage1_translation(
    text: str,
    pipeline_executor
) -> str:
    """
    Execute Stage 1a: Translation
    DUMB: Just calls translation pipeline, returns result

    Args:
        text: Input text to translate
        pipeline_executor: PipelineExecutor instance

    Returns:
        Translated text
    """
    result = await pipeline_executor.execute_pipeline(
        'pre_interception/correction_translation_de_en',
        text,
    )

    if result.success:
        return result.final_output
    else:
        logger.warning(f"Translation failed: {result.error}, continuing with original text")
        return text

async def execute_stage1_safety(
    text: str,
    safety_level: str,
    pipeline_executor
) -> Tuple[bool, List[str]]:
    """
    Execute Stage 1b: Hybrid Safety Check
    Fast string-match → LLM verification if terms found

    Args:
        text: Text to check for safety
        safety_level: Not used in Stage 1 (always uses 'stage1' filters)
        pipeline_executor: PipelineExecutor instance

    Returns:
        (is_safe, error_codes)
    """
    import time

    # HYBRID APPROACH: Fast string-match first
    start_time = time.time()
    has_terms, found_terms = fast_filter_check(text, 'stage1')
    fast_check_time = time.time() - start_time

    if not has_terms:
        # FAST PATH: No problematic terms → instantly safe (95% of requests)
        logger.info(f"[STAGE1-SAFETY] PASSED (fast-path, {fast_check_time*1000:.1f}ms)")
        return (True, [])

    # SLOW PATH: Terms found → Llama-Guard context verification
    logger.info(f"[STAGE1-SAFETY] found terms {found_terms[:3]}... → Llama-Guard check (fast: {fast_check_time*1000:.1f}ms)")

    llm_start_time = time.time()
    result = await pipeline_executor.execute_pipeline(
        'pre_interception/safety_llamaguard',
        text,
    )
    llm_check_time = time.time() - llm_start_time

    if result.success:
        is_safe, codes = parse_llamaguard_output(result.final_output)

        if not is_safe:
            logger.warning(f"[STAGE1-SAFETY] BLOCKED by Llama-Guard: {codes} (llm: {llm_check_time:.1f}s)")
            return (False, codes)
        else:
            # FALSE POSITIVE: Terms found but context is safe
            logger.info(f"[STAGE1-SAFETY] PASSED (Llama-Guard verified false positive, llm: {llm_check_time:.1f}s)")
            return (True, [])
    else:
        logger.warning(f"[STAGE1-SAFETY] Llama-Guard failed: {result.error}, continuing (fail-open)")
        return (True, [])  # Fail-open

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
    # §86a violations are unambiguous — no LLM context check needed
    s86a_start = _time.time()
    has_86a_terms, found_86a_terms = fast_filter_bilingual_86a(text, user_language)
    s86a_time = _time.time() - s86a_start

    if has_86a_terms:
        error_message = (
            f"⚠️ Dein Prompt wurde blockiert\n\n"
            f"GRUND: §86a StGB\n\n"
            f"Dein Prompt enthält Begriffe, die nach deutschem Recht verboten sind: {', '.join(found_86a_terms[:3])}\n\n"
            f"WARUM DIESE REGEL?\n"
            f"Diese Symbole werden benutzt, um Gewalt und Hass zu verbreiten.\n"
            f"Wir schützen dich und andere vor gefährlichen Inhalten."
        )
        logger.warning(f"[STAGE1] BLOCKED §86a fast-filter: {found_86a_terms[:3]} ({s86a_time*1000:.1f}ms)")
        return (False, text, error_message, ['§86a'])

    # ── STEP 2: Age-appropriate Fast-Filter (~0.001s) ──────────────────
    # Skip for 'adult' and 'research' — only §86a and DSGVO apply
    if safety_level not in ('research', 'adult'):
        age_start = _time.time()
        has_age_terms, found_age_terms = fast_filter_check(text, safety_level, user_language)
        age_time = _time.time() - age_start

        if has_age_terms:
            # Terms found → LLM context check (prevents false positives like "cute vampire")
            logger.info(f"[STAGE1] Age-filter hit: {found_age_terms[:3]} → LLM context check ({age_time*1000:.1f}ms)")

            llm_start = _time.time()
            verify_result = llm_verify_age_filter_context(text, found_age_terms, safety_level)
            llm_time = _time.time() - llm_start

            if verify_result is None:
                # LLM unavailable → fail-closed (kids safety errs on caution)
                terms_str = ', '.join(found_age_terms[:5])
                error_message = (
                    f"⚠️ Dein Prompt wurde blockiert\n\n"
                    f"GRUND: Sicherheitssystem nicht erreichbar\n\n"
                    f"Gefundene Begriffe: {terms_str}\n\n"
                    f"Das Sicherheitssystem konnte die Begriffe nicht im Kontext prüfen.\n"
                    f"Bitte versuche es erneut oder formuliere deinen Prompt um."
                )
                logger.warning(f"[STAGE1] Age-filter LLM unavailable → fail-closed ({llm_time:.1f}s)")
                return (False, text, error_message, ['§86a', 'age_filter'])

            elif verify_result:
                # LLM confirmed inappropriate → BLOCK with age-appropriate message
                terms_str = ', '.join(found_age_terms[:5])
                if safety_level == 'kids':
                    error_message = (
                        f"⚠️ Dein Prompt wurde blockiert\n\n"
                        f"GRUND: Kinder-Schutzfilter (6-12 Jahre)\n\n"
                        f"Gefundene Begriffe: {terms_str}\n\n"
                        f"WARUM DIESE REGEL?\n"
                        f"Dein Prompt enthält Begriffe, die für Kinder erschreckend oder verstörend sein können.\n"
                        f"Wir schützen dich vor Inhalten, die Angst machen oder ungeeignet für dein Alter sind."
                    )
                else:
                    error_message = (
                        f"⚠️ Dein Prompt wurde blockiert\n\n"
                        f"GRUND: Jugendschutzfilter (13-17 Jahre)\n\n"
                        f"Gefundene Begriffe: {terms_str}\n\n"
                        f"WARUM DIESE REGEL?\n"
                        f"Dein Prompt enthält explizite Begriffe, die für Jugendliche ungeeignet sind."
                    )
                logger.warning(f"[STAGE1] BLOCKED age-filter (LLM confirmed, {llm_time:.1f}s)")
                return (False, text, error_message, ['§86a', 'age_filter'])

            else:
                # LLM says benign context (false positive like "cute vampire") → allow
                logger.info(f"[STAGE1] Age-filter false positive confirmed by LLM ({llm_time:.1f}s)")
                # Fall through to DSGVO check
    else:
        logger.debug(f"[STAGE1] Age-filter skipped (safety_level={safety_level})")

    # ── STEP 3: DSGVO SpaCy NER (~50-100ms) or LLM Fallback ──────────
    # Track which checks we've passed so far
    checks_passed = ['§86a']
    if safety_level not in ('research', 'adult'):
        checks_passed.append('age_filter')

    dsgvo_start = _time.time()
    has_personal_data, found_entities, spacy_available = fast_dsgvo_check(text)
    dsgvo_time = _time.time() - dsgvo_start

    if spacy_available and has_personal_data:
        # NER triggered — LLM verification to avoid false positives
        # (SpaCy flags technical terms like "Agrarische Funktionszone" or "muted earth tones:1.1")
        logger.info(f"[STAGE1] DSGVO NER triggered: {found_entities[:3]} — verifying with LLM")
        verify_result = llm_verify_person_name(text, found_entities)
        if verify_result is None:
            # LLM unavailable — fail-closed
            error_message = (
                "Sicherheitssystem (Ollama) reagiert nicht, daher kann keine weitere "
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
        dsgvo_result = llm_dsgvo_fallback_check(text)
        llm_time = _time.time() - llm_start

        if dsgvo_result is None:
            # LLM unavailable → fail-closed
            error_message = (
                "Sicherheitssystem (Ollama) reagiert nicht, daher kann keine weitere "
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

    # ── ALL CHECKS PASSED ──────────────────────────────────────────────
    total_time = _time.time() - total_start
    logger.info(f"[STAGE1] SAFE ({total_time*1000:.1f}ms total, checks: {checks_passed})")
    return (True, text, None, checks_passed)

async def execute_stage3_safety(
    prompt: str,
    safety_level: str,
    media_type: str,
    pipeline_executor,
    user_language: str = 'de'
) -> Dict[str, Any]:
    """
    Execute Stage 3: Pre-Output Safety Check (Jugendschutz)

    Tiered translation behavior:
    - research/adult: No translation, no safety check — original prompt to model
    - kids: Translate to English, run safety, pass TRANSLATED prompt to model
    - youth: Translate to English internally for safety check, pass ORIGINAL prompt to model

    This decouples translation-for-safety from translation-for-generation.
    Youth+ users can explore how models react to their native language.
    The translate button in MediaInputBox remains available for manual use.

    Steps:
    1. research/adult → return original prompt immediately
    2. Translate to English (for kids/youth safety check)
    3. §86a fast-filter on translated text (instant block)
    4. LLM safety check on translated text
    5. Return: kids → translated prompt | youth → original prompt

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
    global _last_untranslated, _last_translated

    # STEP 1: research/adult — no translation, no safety check
    if safety_level in ('research', 'adult'):
        return {
            "safe": True,
            "method": "disabled",
            "abort_reason": None,
            "positive_prompt": prompt,
            "negative_prompt": ""
        }

    # STEP 2: Translate to English (for safety check on kids/youth)
    # Skip API call if prompt unchanged since last translation
    if prompt == _last_untranslated and _last_translated is not None:
        translated_prompt = _last_translated
        translate_time = 0
        logger.info(f"[STAGE3-TRANSLATION] Reused (prompt unchanged): {translated_prompt[:150]}...")
    else:
        translate_start = time.time()
        translate_result = await pipeline_executor.execute_pipeline(
            'pre_output/translation_en',  # Translation config (just translate chunk)
            prompt,
        )
        translate_time = time.time() - translate_start

        if translate_result.success:
            translated_prompt = translate_result.final_output
            _last_untranslated = prompt
            _last_translated = translated_prompt
            logger.info(f"[STAGE3-TRANSLATION] Translated in {translate_time:.2f}s: {translated_prompt[:150]}...")
        else:
            # Translation failed - use original prompt
            translated_prompt = prompt
            logger.warning(f"[STAGE3-TRANSLATION] Translation failed, using original prompt")

    # STEP 3: §86a fast-filter on translated text — use 'en' (text is already English)
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

    # STEP 3b: Age-appropriate fast-filter on ORIGINAL (pre-translation) text
    # Translation models sanitize violence ("erschlägt"→"strikes", "erschiessen"→"arrest"),
    # so the fast-filter MUST run on the original input, not the translated output.
    has_age_terms, found_age_terms = fast_filter_check(prompt, safety_level, user_language)
    if has_age_terms:
        filter_name = 'Kids-Filter' if safety_level == 'kids' else 'Youth-Filter'
        logger.info(f"[STAGE3-SAFETY] {filter_name} fast-filter hit on original text: {found_age_terms[:3]} → LLM context check")
        verify_result = llm_verify_age_filter_context(prompt, found_age_terms, safety_level)
        if verify_result is None:
            # LLM unavailable — fail-closed (defense-in-depth, Stage 1 should have caught this)
            logger.warning(f"[STAGE3-SAFETY] {filter_name} LLM verify unavailable — fail-closed")
            return {
                "safe": False,
                "method": "age_filter_verify_unavailable",
                "abort_reason": f"{filter_name}: safety verification unavailable",
                "positive_prompt": None,
                "negative_prompt": None,
                "execution_time": translate_time
            }
        elif verify_result:
            logger.warning(f"[STAGE3-SAFETY] {filter_name} BLOCKED (LLM confirmed): {found_age_terms[:3]}")
            return {
                "safe": False,
                "method": "age_filter",
                "abort_reason": f'{filter_name}: {", ".join(found_age_terms[:3])}',
                "positive_prompt": None,
                "negative_prompt": None,
                "execution_time": translate_time
            }
        else:
            logger.info(f"[STAGE3-SAFETY] {filter_name} false positive (LLM rejected): {found_age_terms[:3]}")

    # STEP 4: ALWAYS run LLM safety check for kids/youth
    # Semantic violence/harm cannot be caught by wordlists alone —
    # "Wesen sind feindselig zueinander und fügen einander Schaden zu"
    # passes all fast-filters but generates harmful imagery for children.
    safety_check_config = f'pre_output/safety_check_{safety_level}'

    logger.info(f"[STAGE3-SAFETY] Running LLM safety check ({safety_level})")
    llm_start_time = time.time()
    result = await pipeline_executor.execute_pipeline(
        safety_check_config,
        translated_prompt,
    )
    llm_check_time = time.time() - llm_start_time

    # Extract metadata from pipeline result
    model_used = None
    backend_type = None
    if result.steps and len(result.steps) > 0:
        for step in reversed(result.steps):
            if step.metadata:
                model_used = step.metadata.get('model_used', model_used)
                backend_type = step.metadata.get('backend_type', backend_type)
                if model_used and backend_type:
                    break

    # STEP 5: Select generation prompt by safety level
    # kids → auto-translated English (better model output, full guardrails)
    # youth → original language (user explores model behavior, manual translate available)
    generation_prompt = translated_prompt if safety_level == 'kids' else prompt

    if result.success:
        safety_data = parse_preoutput_json(result.final_output)

        if not safety_data.get('safe', True):
            abort_reason = safety_data.get('abort_reason', 'Content blocked by safety filter')
            logger.warning(f"[STAGE3-SAFETY] BLOCKED by LLM: {abort_reason} (llm: {llm_check_time:.1f}s)")

            return {
                "safe": False,
                "method": "llm_safety_check",
                "abort_reason": abort_reason,
                "positive_prompt": None,
                "negative_prompt": None,
                "model_used": model_used,
                "backend_type": backend_type,
                "execution_time": llm_check_time
            }
        else:
            logger.info(f"[STAGE3-SAFETY] PASSED (LLM, {llm_check_time:.1f}s), using {'translated' if safety_level == 'kids' else 'original'} prompt for generation")

            return {
                "safe": True,
                "method": "llm_safety_check",
                "abort_reason": None,
                "positive_prompt": generation_prompt,
                "negative_prompt": safety_data.get('negative_prompt', ''),
                "model_used": model_used,
                "backend_type": backend_type,
                "execution_time": translate_time + llm_check_time
            }
    else:
        logger.warning(f"[STAGE3-SAFETY] LLM check failed: {result.error}, BLOCKING (fail-closed)")
        return {
            "safe": False,
            "method": "llm_check_failed",
            "abort_reason": "Safety check failed (LLM error/timeout) — blocking as precaution",
            "positive_prompt": None,
            "negative_prompt": None
        }


# ============================================================================
# SESSION 84: STAGE 3 SAFETY CHECK FOR CODE OUTPUT
# ============================================================================

async def execute_stage3_safety_code(
    code: str,
    safety_level: str,
    media_type: str,
    pipeline_executor
) -> dict:
    """
    Stage 3 Safety Check for Code Output (P5.js, SonicPi, etc.)

    Checks generated code for unsafe patterns without translation.
    Uses fast filter + conditional LLM verification.

    Args:
        code: Generated code (JavaScript, Ruby, etc.)
        safety_level: Safety level ('kids', 'youth', 'research')
        media_type: Media type ('code')
        pipeline_executor: Pipeline executor for LLM calls

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

    # SLOW PATH: Unsafe patterns found → LLM context verification
    logger.warning(f"[STAGE3-CODE] Found patterns: {found_patterns} → LLM verification")

    # Create verification prompt
    verification_prompt = f"""You are a code safety analyzer for educational creative coding environments.

A student generated code that contains potentially unsafe patterns: {', '.join(found_patterns)}

Analyze the code and determine:
1. Is this code actually dangerous, or are these patterns used safely?
2. Could this code be executed in a sandboxed iframe without risk?

Code to analyze:
```javascript
{code}
```

Respond with JSON only:
{{
  "safe": true or false,
  "reasoning": "brief explanation",
  "abort_reason": "reason if unsafe, otherwise null"
}}
"""

    # Call LLM for context verification
    try:
        llm_result = await pipeline_executor.execute_chunk_async(
            chunk_name='manipulate',
            inputs={'INPUT_TEXT': verification_prompt},
        )

        # Parse JSON response
        import json
        import re

        # Extract JSON from response (handle markdown code blocks)
        response_text = llm_result.get('output', '{"safe": false}')
        json_match = re.search(r'\{[^{}]*"safe"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            response_data = json.loads(json_match.group())
        else:
            response_data = json.loads(response_text)

        is_safe = response_data.get('safe', False)
        abort_reason = response_data.get('abort_reason')

        logger.info(f"[STAGE3-CODE] LLM verification result: safe={is_safe}, reason={abort_reason}")

        return {
            'safe': is_safe,
            'positive_prompt': code if is_safe else '',
            'abort_reason': abort_reason if not is_safe else None,
            'method': 'llm_context_check',
            'patterns_found': found_patterns,
            'execution_time': (datetime.now() - start_time).total_seconds()
        }

    except Exception as e:
        # Fail-open: Allow code if LLM check fails (sandbox provides final protection)
        logger.error(f"[STAGE3-CODE] LLM verification failed: {e} → allowing code (fail-open)")
        return {
            'safe': True,
            'positive_prompt': code,
            'method': 'llm_failed_failopen',
            'patterns_found': found_patterns,
            'execution_time': (datetime.now() - start_time).total_seconds()
        }
