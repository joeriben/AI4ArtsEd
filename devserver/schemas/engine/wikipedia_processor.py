"""
Wikipedia Processor: Marker detection and content formatting for LLM research

This module extracts <wiki> markers from LLM output and formats Wikipedia
content for injection into the next iteration's context.

Trigger Pattern:
    <wiki lang="de">Suchbegriff</wiki>  - German Wikipedia
    <wiki lang="en">Search term</wiki>  - English Wikipedia
    <wiki>term</wiki>                    - Uses input language (auto-detected)

    Any marker may carry why="..." — the model's own reason for looking the term
    up. It is taken verbatim and never checked: the point is to make the model's
    estimate of its own limits readable, and a reason we filtered would be our
    estimate, not its. A marker without one still looks the term up.

Architecture:
- Chunk-level orchestration: pipeline_executor.py uses this to detect markers
- When markers found, chunk re-executes with Wikipedia context injected
- Maximum iterations configurable (default 3)
"""

from dataclasses import dataclass
from typing import List, Optional
import re
import logging

logger = logging.getLogger(__name__)

# Regex pattern to extract wiki markers
# Matches: <wiki>term</wiki> with any number of attributes in any order —
# group(1) is the raw attribute string, group(2) the term. Written this way so a
# new attribute (why=, and whatever comes after it) does not need a new pattern
# and cannot break the old two-attribute-free form.
WIKI_MARKER_PATTERN = re.compile(
    r'<wiki((?:\s+[a-z]+\s*=\s*"[^"]*")*)\s*>\s*([^<]+?)\s*</wiki>',
    re.IGNORECASE
)
_WIKI_ATTR_PATTERN = re.compile(r'([a-z]+)\s*=\s*"([^"]*)"', re.IGNORECASE)


@dataclass
class WikiMarker:
    """Represents a Wikipedia lookup marker found in LLM output"""
    term: str
    language: Optional[str]  # None = use input language
    original_marker: str     # Full matched text (for potential replacement)
    reason: Optional[str] = None  # why="..." — taken verbatim, never checked

    def __str__(self) -> str:
        if self.language:
            return f"<wiki lang=\"{self.language}\">{self.term}</wiki>"
        return f"<wiki>{self.term}</wiki>"


def extract_markers(text: str) -> List[WikiMarker]:
    """
    Extract all <wiki> markers from text.

    Args:
        text: LLM output text to search for markers

    Returns:
        List of WikiMarker objects found in the text
    """
    markers = []

    for match in WIKI_MARKER_PATTERN.finditer(text):
        attrs = {
            k.lower(): v.strip()
            for k, v in _WIKI_ATTR_PATTERN.findall(match.group(1) or '')
        }
        language = attrs.get('lang')
        term = match.group(2).strip()
        original = match.group(0)

        # Skip empty terms
        if not term:
            continue

        marker = WikiMarker(
            term=term,
            language=language.lower() if language and len(language) <= 8 else None,
            reason=attrs.get('why') or None,
            original_marker=original
        )
        markers.append(marker)
        logger.debug(f"[WIKI-MARKER] Found: {marker}")

    if markers:
        logger.info(f"[WIKI-MARKER] Extracted {len(markers)} marker(s) from output")
    else:
        logger.debug("[WIKI-MARKER] No markers found in output")

    return markers


def format_wiki_content(results: List) -> str:
    """
    Format Wikipedia results for injection into context.

    Args:
        results: List of WikipediaResult objects from wikipedia_service

    Returns:
        Formatted string for WIKIPEDIA_CONTEXT placeholder
    """
    # WikipediaResult is passed in, no import needed here

    if not results:
        return ""

    formatted_parts = []

    for result in results:
        if result.success:
            # Format successful lookup
            part = f"[Wikipedia: {result.title}]\n{result.extract}"
            formatted_parts.append(part)
        else:
            # Include failure message (helps LLM know search failed)
            part = f"[Wikipedia: {result.term}] Not found."
            formatted_parts.append(part)

    # Join with double newlines for readability
    content = "\n\n".join(formatted_parts)

    logger.info(f"[WIKI-FORMAT] Formatted {len(results)} result(s), {len(content)} chars total")

    return content


def remove_markers(text: str) -> str:
    """
    Remove all <wiki> markers from text.

    Use this to clean the final output after all research iterations.

    Args:
        text: Text containing <wiki> markers

    Returns:
        Text with markers removed (replaced by their term only)
    """
    def replace_marker(match):
        term = match.group(2).strip()
        return term

    cleaned = WIKI_MARKER_PATTERN.sub(replace_marker, text)
    return cleaned


def has_markers(text: str) -> bool:
    """
    Quick check if text contains any <wiki> markers.

    Args:
        text: Text to check

    Returns:
        True if any markers found
    """
    return bool(WIKI_MARKER_PATTERN.search(text))
