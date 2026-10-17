"""
LLM Backend singleton factory.

Usage:
    from my_app.services.llm_backend import get_llm_backend
    result = get_llm_backend().chat(model="qwen3:1.7b", messages=[...])
"""

from my_app.services.llm_client import LLMClient

_backend = None


def get_llm_backend() -> LLMClient:
    """Get LLMClient singleton."""
    global _backend
    if _backend is None:
        _backend = LLMClient()
    return _backend
