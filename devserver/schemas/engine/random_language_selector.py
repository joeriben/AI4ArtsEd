"""
Random Language Selector
Provides random language selection for translation pipelines.
"""
import random
from typing import List, Optional


# Supported languages for translation
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'de': 'German',
    'fr': 'French',
    'es': 'Spanish',
    'it': 'Italian',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'pl': 'Polish',
    'ru': 'Russian',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'ko': 'Korean',
    'tr': 'Turkish',
    'uk': 'Ukrainian',
    'he': 'Hebrew',
    'bg': 'Bulgarian'
}


def get_random_language(exclude: Optional[List[str]] = None) -> str:
    """
    Returns ONE random language code from supported languages.

    This is a minimal helper that only handles random selection.
    All loop logic, final language, and sequence management
    belongs in the pipeline/config layer.

    Args:
        exclude: Optional list of language codes to exclude from selection

    Returns:
        Single language code (e.g., 'fr', 'de', 'zh')

    Example:
        >>> lang1 = get_random_language()
        >>> 'fr'
        >>> lang2 = get_random_language(exclude=['fr'])
        >>> 'de'  # Won't return 'fr'
    """
    exclude = exclude or []

    # Filter out excluded languages
    available = [code for code in SUPPORTED_LANGUAGES.keys() if code not in exclude]

    if not available:
        # Fallback: if all languages excluded, return random from full set
        available = list(SUPPORTED_LANGUAGES.keys())

    return random.choice(available)


def get_language_name(code: str) -> str:
    """
    Returns the full language name for a given code.

    Args:
        code: Language code (e.g., 'en', 'de')

    Returns:
        Full language name (e.g., 'English', 'German')
        Returns code itself if not found
    """
    return SUPPORTED_LANGUAGES.get(code, code)


