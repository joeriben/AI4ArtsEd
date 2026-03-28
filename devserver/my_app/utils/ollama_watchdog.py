"""DEPRECATED: Use llm_watchdog.py instead."""
from my_app.utils.llm_watchdog import attempt_restart, _llm_healthy

# Backward-compatible alias
_ollama_healthy = _llm_healthy
