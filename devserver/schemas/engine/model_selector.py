"""
Model Selection Service: Intelligent model switching for eco/fast modes
Includes fallback logic for all LLM operations

DEPRECATED: eco/fast execution modes have been removed.
Model selection is now centralized in devserver/config.py (STAGE1_MODEL, STAGE2_MODEL, etc.).
Still in use: get_local_models() (schemas/engine/prompt_interception_engine.py,
my_app/routes/canvas_routes.py), which reads the table of local models.
"""
import logging
from typing import Dict, List

from my_app.services.llm_providers import split_provider

logger = logging.getLogger(__name__)

# Model mappings: local model names → OpenRouter equivalents
LOCAL_TO_OPENROUTER_MAP = {
    "deepcoder": "agentica-org/deepcoder-14b-preview",
    "deepseek-r1": "deepseek/deepseek-r1",
    # NOTE: google/gemma-2-9b-it NOT available on OpenRouter, fallback to mistral-nemo
    # "gemma-2-9b-it": "google/gemma-2-9b-it",  # REMOVED - not available
    "gemma-2-27b-it": "google/gemma-2-27b-it",
    "gemma-3-1b-it": "google/gemma-3-1b-it",
    "gemma-3-4b-it": "google/gemma-3-4b-it",
    "gemma-3-12b-it": "google/gemma-3-12b-it",
    "gemma-3-27b-it": "google/gemma-3-27b-it",
    "gemma-3n-e4b-it": "google/gemma-3n-e4b-it",
    "shieldgemma-9b": "google/shieldgemma-9b",
    "llava": "liuhaotian/llava-7b",
    "llava:13b": "liuhaotian/llava-13b",
    "llama-3.1-8b-instruct": "meta-llama/llama-3.1-8b-instruct",
    "llama-3.2-1b-instruct": "meta-llama/llama-3.2-1b-instruct",
    "llama-3.3-8b-instruct": "meta-llama/llama-3.3-8b-instruct",
    "llama-guard-3-1b": "meta-llama/llama-guard-3-1b",
    "llama-guard-3-8b": "meta-llama/llama-guard-3-8b",
    "codestral": "mistralai/codestral",
    "mistral-7b": "mistralai/mistral-7b",
    "mistral-nemo": "mistralai/mistral-nemo",
    "mistral-small:24b": "mistralai/mistral-small-24b",
    "mixtral-8x7b-instruct": "mistralai/mixtral-8x7b-instruct",
    "ministral-8b": "mistralai/ministral-8b",
    "phi-4": "microsoft/phi-4",
    "qwen2.5-translator": "qwen/qwen2.5-translator",
    "qwen2.5-32b-instruct": "qwen/qwen2.5-32b-instruct",
    "qwen3-8b": "qwen/qwen3-8b",
    "qwen3-14b": "qwen/qwen3-14b",
    "qwen3-30b-a3b": "qwen/qwen3-30b-a3b",
    "qwq-32b": "qwen/qwq-32b",
    "sailor2-20b": "sailor2/sailor2-20b",
    # Add common mappings without qualifiers
    # NOTE: gemma2:9b fallback to mistral-nemo (gemma-2-9b-it not on OpenRouter)
    "gemma2": "mistralai/mistral-nemo",
    "gemma2:9b": "mistralai/mistral-nemo",
    "gemma2:27b": "google/gemma-2-27b-it",
}

OPENROUTER_TO_LOCAL_MAP = {v: k for k, v in LOCAL_TO_OPENROUTER_MAP.items()}

# Add reverse mappings for common OpenRouter models
OPENROUTER_TO_LOCAL_MAP.update({
    "google/gemma-2-27b-it": "gemma2:27b",
    "anthropic/claude-haiku-4.5": "mistral-nemo",  # Fallback for Claude
    "anthropic/claude-haiku-4.5": "mistral-nemo",
    "mistralai/mistral-nemo": "mistral-nemo",
})


class ModelSelector:
    """
    Intelligent model selection for eco/fast execution modes
    Supports both concrete model names and task-based selection
    """
    
    def __init__(self):
        self.local_to_openrouter = LOCAL_TO_OPENROUTER_MAP
        self.openrouter_to_local = OPENROUTER_TO_LOCAL_MAP
        self.task_categories = self._define_task_categories()
    
    def _define_task_categories(self) -> Dict[str, Dict[str, str]]:
        """
        Define optimal models for different task categories
        Based on analysis of legacy workflows
        
        6 core categories organized by function:
        - Privacy/Security (always local)
        - Translation
        - Standard creative tasks
        - Advanced creative tasks
        - Data extraction
        
        Returns:
            Dict mapping task types to eco (local) and fast (cloud) models
        """
        return {
            # === PRIVACY & SECURITY (ALWAYS LOCAL) ===
            "security": {
                "eco": "local/llama-guard-3-8b",
                "fast": "local/llama-guard-3-8b",  # Never cloud for security
                "description": "Content moderation, safety checks (always local)"
            },
            
            "vision": {
                "eco": "local/llava:13b",
                "fast": "local/llava:13b",  # Never cloud for DSGVO privacy
                "description": "Image analysis, visual description (DSGVO-compliant, always local)"
            },
            
            # === LANGUAGE & TRANSLATION ===
            "translation": {
                "eco": "local/qwen2.5-translator",
                "fast": "openrouter/anthropic/claude-haiku-4.5",
                "description": "Language translation, multilingual tasks"
            },
            
            # === CREATIVE TASKS ===
            "standard": {
                "eco": "local/mistral-nemo",
                "fast": "openrouter/mistralai/mistral-nemo",
                "description": "Standard creative prompts, general artistic tasks (most common)"
            },
            
            "advanced": {
                "eco": "local/mistral-small:24b",
                "fast": "openrouter/google/gemini-2.5-pro",
                "description": "Complex cultural/ethical contexts, advanced semantics"
            },
            
            # === DATA PROCESSING ===
            "data_extraction": {
                "eco": "local/gemma3:4b",
                "fast": "openrouter/google/gemma-3-4b-it",
                "description": "Extract numbers, booleans, structured data from text"
            }
        }
    
    
    
    
    def strip_prefix(self, model: str) -> str:
        """
        Remove the service prefix from a model string: 'local/' or the name of
        a provider in config/llm_providers.json. A string without one is
        returned as it is.
        """
        if model.startswith("local/"):
            return model[6:]
        return split_provider(model)[1]


    def get_openrouter_models(self) -> Dict[str, Dict[str, str]]:
        """
        Get OpenRouter model metadata (price, tags)
        Transferred from prompt_interception_engine
        """
        return {
            "anthropic/claude-haiku-4.5": {"price": "$0.80/$4.00", "tag": "multilingual"},
            "anthropic/claude-haiku-4.5": {"price": "$0.80/$4.00", "tag": "multilingual"},
            "deepseek/deepseek-chat-v3-0324": {"price": "$0.27/$1.10", "tag": "rule-oriented"},
            "deepseek/deepseek-r1-0528": {"price": "$0.50/$2.15", "tag": "reasoning"},
            "google/gemini-2.5-flash": {"price": "$0.20/$2.50", "tag": "multilingual"},
            "google/gemma-3-27b-it": {"price": "$0.10/$0.18", "tag": "translator"},
            "meta-llama/llama-3.3-70b-instruct": {"price": "$0.59/$0.79", "tag": "rule-oriented"},
            "meta-llama/llama-guard-3-8b": {"price": "$0.05/$0.10", "tag": "rule-oriented"},
            "meta-llama/llama-3.2-1b-instruct": {"price": "$0.05/$0.10", "tag": "reasoning"},
            "mistralai/mistral-medium-3": {"price": "$0.40/$2.00", "tag": "reasoning"},
            "mistralai/mistral-small-3.1-24b-instruct": {"price": "$0.10/$0.30", "tag": "rule-oriented, vision"},
            "mistralai/mistral-nemo": {"price": "$0.01/$0.001", "tag": "multilingual"},
            "mistralai/ministral-8b": {"price": "$0.05/$0.10", "tag": "rule-oriented"},
            "mistralai/ministral-3b": {"price": "$0.05/$0.10", "tag": "rule-oriented"},
            "mistralai/mixtral-8x7b-instruct": {"price": "$0.45/$0.70", "tag": "cultural-expert"},
            "qwen/qwen3-32b": {"price": "$0.10/$0.30", "tag": "translator"},
        }
    
    def get_local_models(self) -> List[str]:
        """The installed local models, off the table of local models
        (config/local_llm_weights.json; they are run by ComfyUI)."""
        try:
            from my_app.services import local_llm_weights
            return local_llm_weights.installed_aliases()
        except Exception as e:
            logger.warning(f"Failed to get local LLM models: {e}")
            return []
    
    # There is no fallback model here. Two tables used to stand at this place, one
    # naming OpenRouter models and one naming local ones, and the local branch ended
    # in "any model that is not the one that just failed". A caller that asked for one
    # model and got an answer from another cannot tell the two apart afterwards -- the
    # answer carries no mark. A failed call now fails.

    
    def extract_model_name(self, full_model_string: str) -> str:
        """
        Extract real model name from dropdown format
        Supports all provider prefixes: local/, anthropic/, openai/, openrouter/

        Args:
            full_model_string: Model string (may have prefix and metadata)

        Returns:
            Clean model name without prefix or metadata
        """
        return self.strip_prefix(full_model_string).split(" [")[0]


# Singleton instance
model_selector = ModelSelector()
