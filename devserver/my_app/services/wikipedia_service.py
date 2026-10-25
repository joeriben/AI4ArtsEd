"""
Wikipedia Service: Secure Wikipedia API client for LLM research capability

This service provides the LLM with access to Wikipedia during prompt interception,
allowing it to fetch factual information about cultural heritages, arts, aesthetics,
and other educational contexts.

Security:
- Whitelist-only: Only *.wikipedia.org URLs are accessible
- Language validation: Only allowed language codes accepted
- URL encoding: Search terms properly encoded
- Content truncation: Prevents memory exhaustion

Architecture:
- This is a fundamental capability of ALL interceptions
- NOT a separate pipeline - integrated at chunk execution level
- Language auto-detected from input text (falls back to config default)
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from functools import lru_cache
import threading
import time
import logging
import re
import urllib.parse
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

# Supported Wikipedia languages (ISO 639-1 codes)
# Expanded to 70+ languages for epistemic justice
SUPPORTED_LANGUAGES = frozenset([
    # Europe
    'de', 'en', 'it', 'fr', 'es', 'pt', 'nl', 'pl', 'ru', 'sv', 'uk', 'cs', 'el', 'he',
    'da', 'no', 'fi', 'ro', 'hu', 'sr', 'hr', 'bs', 'ca', 'eu', 'gl',
    # Asia
    'zh', 'zh-yue', 'ja', 'ko', 'hi', 'ta', 'bn', 'te', 'mr', 'gu', 'kn', 'ml', 'pa', 'ur',
    'id', 'jv', 'su', 'tl', 'ceb', 'th', 'vi', 'my', 'fa', 'tr', 'ar', 'arz', 'ps',
    # Africa
    'ha', 'yo', 'ig', 'sw', 'am', 'om', 'zu', 'xh', 'af', 'tw', 'wo', 'mg', 'ber',
    # Americas
    'nah', 'qu', 'ay', 'ht', 'ik', 'chr',
    # Oceania
    'mi', 'to', 'sm', 'fj',
])

# Maximum content length per summary (characters)
MAX_CONTENT_LENGTH = 2000

# HTTP timeout for Wikipedia API requests
HTTP_TIMEOUT = 10.0

# Patterns to detect disambiguation pages across languages
DISAMBIGUATION_PATTERNS = frozenset([
    'disambiguation',           # English
    'begriffsklärung',          # German
    'desambiguación',           # Spanish
    'homonymie',                # French
    'disambigua',               # Italian
    'doorverwijspagina',        # Dutch
    'значения',                 # Russian (meanings)
    'ujednoznacznienie',        # Polish
    '曖昧さ回避',                # Japanese
    '消歧义',                    # Chinese (simplified)
])

# User-Agent required by Wikipedia API (https://meta.wikimedia.org/wiki/User-Agent_policy)
HTTP_USER_AGENT = "AI4ArtsEd-DevServer/1.0 (https://github.com/ai4artsed; ai4artsed@example.org) Python/aiohttp"


@dataclass
class WikipediaResult:
    """Result from a Wikipedia lookup"""
    term: str
    language: str
    title: str
    extract: str
    url: str
    success: bool
    error: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return f"[Wikipedia: {self.title}] {self.extract}"
        return f"[Wikipedia: {self.term}] Not found: {self.error}"


class WikipediaCache:
    """Simple time-based cache for Wikipedia results"""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, tuple] = {}  # key -> (result, timestamp)
        self._ttl = ttl_seconds
        self._lock = threading.Lock()  # shared by every lookup of the process

    def _make_key(self, term: str, language: str) -> str:
        return f"{language}:{term.lower()}"

    def get(self, term: str, language: str) -> Optional[WikipediaResult]:
        """Get cached result if not expired"""
        key = self._make_key(term, language)
        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    logger.debug(f"[WIKI-CACHE] Hit for '{term}' ({language})")
                    return result
                else:
                    # Expired
                    del self._cache[key]
        return None

    def set(self, term: str, language: str, result: WikipediaResult) -> None:
        """Cache a result"""
        key = self._make_key(term, language)
        with self._lock:
            self._cache[key] = (result, time.time())
        logger.debug(f"[WIKI-CACHE] Stored '{term}' ({language})")

    def clear(self) -> None:
        """Clear all cached results"""
        with self._lock:
            self._cache.clear()


class WikipediaService:
    """
    Secure Wikipedia API client for LLM research during prompt interception.

    Uses Wikipedia REST API: https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}

    Security constraints:
    - Only queries *.wikipedia.org (whitelist)
    - Only allows known language codes
    - URL-encodes search terms to prevent injection
    - Limits content length to prevent memory exhaustion
    """

    def __init__(self, cache_ttl: int = 3600):
        self._cache = shared_cache(cache_ttl)

    def _create_session(self) -> aiohttp.ClientSession:
        """Create a new aiohttp session with required headers"""
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        headers = {
            'User-Agent': HTTP_USER_AGENT,
            'Accept': 'application/json'
        }
        return aiohttp.ClientSession(timeout=timeout, headers=headers)

    def _validate_language(self, language: str) -> bool:
        """Check if language code is in whitelist"""
        return language.lower() in SUPPORTED_LANGUAGES


    def _is_disambiguation_page(self, data: dict) -> bool:
        """
        Detect if API response is a disambiguation page.

        Checks:
        1. type field == 'disambiguation' (used by English Wikipedia)
        2. description field contains disambiguation keywords (used by other languages)
        """
        # Check type field (English Wikipedia uses this)
        if data.get('type') == 'disambiguation':
            return True

        # Check description field for disambiguation patterns
        description = data.get('description', '').lower()
        for pattern in DISAMBIGUATION_PATTERNS:
            if pattern in description:
                return True

        return False

    async def lookup(self, term: str, language: str = 'de') -> WikipediaResult:
        """
        Look up a term on Wikipedia using Opensearch API (fuzzy matching).

        Strategy:
        1. Use Opensearch API to find the best matching article title
        2. Fetch the full summary using Page Summary API

        Args:
            term: Search term (will be URL-encoded)
            language: ISO 639-1 language code (default: 'de')

        Returns:
            WikipediaResult with success=True and extract, or success=False with error
        """
        # Normalize language code
        lang_code = language.lower()

        # Validate language
        if not self._validate_language(lang_code):
            logger.warning(f"[WIKI] Invalid language code '{language}', using 'de'")
            lang_code = 'de'

        # Check cache first
        cached = self._cache.get(term, lang_code)
        if cached:
            return cached

        logger.info(f"[WIKI] Searching '{term}' on {lang_code}.wikipedia.org (Opensearch)")

        try:
            async with self._create_session() as session:
                # Step 1: Use Opensearch API to find matching article
                opensearch_url = f"https://{lang_code}.wikipedia.org/w/api.php"
                opensearch_params = {
                    'action': 'opensearch',
                    'search': term,
                    'limit': 1,
                    'format': 'json'
                }

                async with session.get(opensearch_url, params=opensearch_params) as search_response:
                    if search_response.status != 200:
                        result = WikipediaResult(
                            term=term,
                            language=lang_code,
                            title='',
                            extract='',
                            url='',
                            success=False,
                            error=f"Opensearch API error: HTTP {search_response.status}"
                        )
                        logger.warning(f"[WIKI] Opensearch HTTP error {search_response.status} for '{term}'")
                        self._cache.set(term, lang_code, result)
                        return result

                    search_data = await search_response.json()
                    # Opensearch returns: [searchTerm, [titles], [descriptions], [urls]]

                    if len(search_data) < 4 or not search_data[1]:
                        # No results found
                        result = WikipediaResult(
                            term=term,
                            language=lang_code,
                            title='',
                            extract='',
                            url='',
                            success=False,
                            error=f"No Wikipedia article found for '{term}'"
                        )
                        logger.info(f"[WIKI] Not found: '{term}'")
                        self._cache.set(term, lang_code, result)
                        return result

                    found_title = search_data[1][0]
                    found_url = search_data[3][0] if search_data[3] else ''

                    logger.info(f"[WIKI] Opensearch found: '{found_title}' for search '{term}'")

                # Step 2: Fetch full summary using Page Summary API
                encoded_title = urllib.parse.quote(found_title, safe='')
                summary_url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"

                async with session.get(summary_url) as summary_response:
                    if summary_response.status == 200:
                        data = await summary_response.json()

                        # Check for disambiguation page
                        if self._is_disambiguation_page(data):
                            result = WikipediaResult(
                                term=term,
                                language=lang_code,
                                title=data.get('title', found_title),
                                extract='',
                                url=data.get('content_urls', {}).get('desktop', {}).get('page', found_url),
                                success=False,
                                error=f"Begriffsklärung: '{data.get('title', found_title)}' ist mehrdeutig - keine eindeutige Faktenbasis verfügbar."
                            )
                            logger.info(f"[WIKI] Disambiguation page detected for '{term}'")
                            self._cache.set(term, lang_code, result)
                            return result

                        # Extract summary text
                        extract = data.get('extract', '')
                        title = data.get('title', found_title)
                        page_url = data.get('content_urls', {}).get('desktop', {}).get('page', found_url)

                        # Truncate if too long
                        if len(extract) > MAX_CONTENT_LENGTH:
                            extract = extract[:MAX_CONTENT_LENGTH] + '...'

                        result = WikipediaResult(
                            term=term,
                            language=lang_code,
                            title=title,
                            extract=extract,
                            url=page_url,
                            success=True
                        )

                        logger.info(f"[WIKI] Found '{title}': {len(extract)} chars")

                    else:
                        # Summary fetch failed - still return opensearch result with URL
                        result = WikipediaResult(
                            term=term,
                            language=lang_code,
                            title=found_title,
                            extract='',
                            url=found_url,
                            success=True  # We found it, just couldn't get summary
                        )
                        logger.warning(f"[WIKI] Summary fetch failed for '{found_title}', using Opensearch URL")

        except asyncio.TimeoutError:
            result = WikipediaResult(
                term=term,
                language=lang_code,
                title='',
                extract='',
                url='',
                success=False,
                error="Wikipedia API timeout"
            )
            logger.warning(f"[WIKI] Timeout for '{term}'")

        except Exception as e:
            result = WikipediaResult(
                term=term,
                language=lang_code,
                title='',
                extract='',
                url='',
                success=False,
                error=f"Wikipedia lookup failed: {str(e)}"
            )
            logger.error(f"[WIKI] Error for '{term}': {e}")

        # Cache result (even failures, to avoid repeated lookups)
        self._cache.set(term, lang_code, result)

        return result

    async def lookup_multiple(
        self,
        terms: List[tuple],  # List of (term, language) tuples
        max_lookups: int = 5
    ) -> List[WikipediaResult]:
        """
        Look up multiple terms concurrently.

        Args:
            terms: List of (term, language) tuples
            max_lookups: Maximum number of lookups (prevents abuse)

        Returns:
            List of WikipediaResults
        """
        # Limit number of lookups
        limited_terms = terms[:max_lookups]
        if len(terms) > max_lookups:
            logger.warning(f"[WIKI] Limited from {len(terms)} to {max_lookups} lookups")

        # Execute lookups concurrently
        tasks = [self.lookup(term, lang) for term, lang in limited_terms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                term, lang = limited_terms[i]
                final_results.append(WikipediaResult(
                    term=term,
                    language=lang,
                    title='',
                    extract='',
                    url='',
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        return final_results


# Singleton instance (lazy initialization)
_wikipedia_service: Optional[WikipediaService] = None


_shared_cache: Optional[WikipediaCache] = None
_shared_cache_lock = threading.Lock()


def shared_cache(ttl_seconds: int) -> WikipediaCache:
    """The one cache of this process. The service is built per lookup
    (its aiohttp session belongs to the running loop), and until 2026-10-10
    each service brought a cache of its own, so a term was asked of
    Wikipedia again on the next run and WIKIPEDIA_CACHE_TTL bounded nothing
    (finding S-027 of the code review of 2026-10-10). The TTL is the first caller's; every caller passes the same
    config value."""
    global _shared_cache
    with _shared_cache_lock:
        if _shared_cache is None:
            _shared_cache = WikipediaCache(ttl_seconds=ttl_seconds)
        return _shared_cache


def get_wikipedia_service(cache_ttl: int = 3600) -> WikipediaService:
    """A WikipediaService for one lookup, on the process-wide cache.

    A new instance each time: its aiohttp session is tied to the event loop
    of the caller, and callers come from different threads and loops.
    """
    return WikipediaService(cache_ttl=cache_ttl)
