"""
DEPRECATED: Use llm_service.py instead.
This module re-exports for backward compatibility.
"""
from my_app.services.llm_service import LLMService, llm_service

# Backward-compatible aliases
OllamaService = LLMService
ollama_service = llm_service
