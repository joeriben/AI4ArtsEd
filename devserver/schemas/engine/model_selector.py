"""
Model Selection Service: Intelligent model switching for eco/fast modes
Includes fallback logic for all LLM operations

DEPRECATED: eco/fast execution modes removed in Session 65.
Model selection is now centralized in devserver/config.py (STAGE1_MODEL, STAGE2_MODEL, etc.).
This module is dead code — kept for reference only, pending removal.
"""
import re
import logging
import requests
from typing import Optional, Tuple, Dict, List, Any

logger = logging.getLogger(__name__)

# Model mappings imported from legacy config
OLLAMA_TO_OPENROUTER_MAP = {
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

OPENROUTER_TO_OLLAMA_MAP = {v: k for k, v in OLLAMA_TO_OPENROUTER_MAP.items()}

# Add reverse mappings for common OpenRouter models
OPENROUTER_TO_OLLAMA_MAP.update({
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
        self.ollama_to_openrouter = OLLAMA_TO_OPENROUTER_MAP
        self.openrouter_to_ollama = OPENROUTER_TO_OLLAMA_MAP
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
    
    def select_model_for_mode(self, base_model: str, execution_mode: str) -> str:
        """
        Select appropriate model based on execution mode
        Supports both concrete models and task categories
        
        Args:
            base_model: Template model OR task category
                       Concrete: "gemma2:9b", "openrouter/anthropic/claude-haiku-4.5"
                       Task-based: "task:standard", "task:advanced", "task:translation", etc.
            execution_mode: "eco" (local/Ollama) or "fast" (cloud/OpenRouter)
            
        Returns:
            Final model with proper prefix (e.g., "local/gemma2:9b" or "openrouter/...")
        """
        # Check if this is a task-based selection
        if base_model.startswith("task:"):
            task_type = base_model[5:]  # Remove "task:" prefix
            return self.select_model_by_task(task_type, execution_mode)
        
        # Concrete model - use standard mode switching
        if execution_mode == 'eco':
            return self.switch_to_eco_mode(base_model)
        elif execution_mode == 'fast':
            return self.switch_to_fast_mode(base_model)
        else:
            # Unknown mode, return as-is
            logger.warning(f"Unknown execution mode '{execution_mode}', using base model")
            return base_model
    
    def select_model_by_task(self, task_type: str, execution_mode: str = 'eco') -> str:
        """
        Select optimal model for a specific task type
        
        Args:
            task_type: Type of task (security, vision, translation, standard, advanced, data_extraction)
            execution_mode: "eco" (local) or "fast" (cloud) - ignored for security/vision tasks
            
        Returns:
            Optimal model for the task with proper prefix
        """
        if task_type not in self.task_categories:
            logger.warning(f"Unknown task type '{task_type}', using 'standard' as fallback")
            task_type = "standard"
        
        task_config = self.task_categories[task_type]
        
        # Security and vision tasks ALWAYS use local models (ignore execution_mode)
        if task_type in ["security", "vision"]:
            selected_model = task_config['eco']
            if execution_mode == 'fast':
                logger.info(f"[TASK-BASED] Task '{task_type}' requires local execution for privacy/security")
        else:
            selected_model = task_config.get(execution_mode, task_config['eco'])
        
        logger.info(f"[TASK-BASED] Task '{task_type}' → {selected_model} (mode: {execution_mode})")
        return selected_model
    
    def get_task_categories(self) -> Dict[str, Dict[str, str]]:
        """Get all defined task categories with descriptions"""
        return self.task_categories
    
    def list_task_types(self) -> List[str]:
        """List all available task types"""
        return sorted(self.task_categories.keys())
    
    def get_task_description(self, task_type: str) -> str:
        """Get description for a task type"""
        if task_type in self.task_categories:
            return self.task_categories[task_type]['description']
        return "Unknown task type"
    
    def switch_to_eco_mode(self, model: str) -> str:
        """
        Switch model to eco mode (local/Ollama)
        
        Args:
            model: Model string (may have prefix or not)
            
        Returns:
            Model with local/ prefix
        """
        # If already has local/ prefix, return as-is
        if model.startswith("local/"):
            return model
        
        # If has openrouter/ prefix, convert to local equivalent
        if model.startswith("openrouter/"):
            openrouter_model_name = model[11:].split(' ')[0]
            local_model = self.openrouter_to_ollama.get(openrouter_model_name)
            
            if local_model:
                result = f"local/{local_model}"
                logger.info(f"[ECO MODE] {model} → {result}")
                return result
            else:
                logger.warning(f"[ECO MODE] No local equivalent for {model}, using mistral-nemo")
                return "local/mistral-nemo"
        
        # No prefix, assume it's a local model name
        return f"local/{model}"
    
    def switch_to_fast_mode(self, model: str) -> str:
        """
        Switch model to fast mode (cloud/OpenRouter) with intelligent fallback
        
        Args:
            model: Model string (may have prefix or not)
            
        Returns:
            Model with openrouter/ prefix
        """
        # If already has openrouter/ prefix, return as-is
        if model.startswith("openrouter/"):
            return model
        
        # If has local/ prefix, extract the model name
        if model.startswith("local/"):
            local_model_raw = model[6:]
        else:
            # No prefix, assume it's a local model name
            local_model_raw = model
        
        # Remove any bracketed metadata (e.g., [context])
        local_model_with_tag = re.split(r'\s*\[', local_model_raw)[0].strip()
        
        # Try exact match first
        exact_match = (
            self.ollama_to_openrouter.get(local_model_with_tag) or 
            self.ollama_to_openrouter.get(local_model_with_tag.split(':')[0])
        )
        
        # Parse model for intelligent fallback
        req_base, req_size = self._parse_model_name(local_model_with_tag)
        
        # Apply intelligent fallback logic (from legacy)
        if 7 <= req_size <= 32 and "mistral-nemo" in self.ollama_to_openrouter and local_model_with_tag != "mistral-nemo":
            if exact_match == "mistralai/mistral-small-24b" or not exact_match:
                openrouter_model = self.ollama_to_openrouter["mistral-nemo"]
                logger.info(f"[FAST MODE] Using Mistral Nemo as intelligent fallback for {req_size}b model")
            else:
                openrouter_model = exact_match
                logger.info(f"[FAST MODE] Using exact match: {exact_match}")
        elif exact_match:
            openrouter_model = exact_match
            logger.info(f"[FAST MODE] Using exact match: {exact_match}")
        else:
            # Intelligent fallback
            openrouter_model = self._find_fallback_model(local_model_with_tag, req_base, req_size)
            if openrouter_model:
                logger.info(f"[FAST MODE] Found fallback: {openrouter_model}")
            else:
                logger.warning(f"[FAST MODE] No fallback found for {local_model_with_tag}, using Mistral Nemo")
                openrouter_model = self.ollama_to_openrouter.get("mistral-nemo", "mistralai/mistral-nemo")
        
        result = f"openrouter/{openrouter_model}"
        logger.info(f"[FAST MODE] {model} → {result}")
        return result
    
    def _parse_model_name(self, model_name: str) -> Tuple[str, int]:
        """
        Parse model name to extract base and size
        
        Args:
            model_name: Model name (e.g., "llama3.2:7b" or "gemma2:9b")
            
        Returns:
            Tuple of (base_name, size_in_billions)
        """
        # Extract size from patterns like :7b, :9b, -8b, etc.
        size_match = re.search(r'[:\-](\d+)b', model_name.lower())
        if size_match:
            size = int(size_match.group(1))
        else:
            size = 0
        
        # Extract base model name (remove size suffix and version numbers)
        base = re.sub(r'[:\-]\d+b.*', '', model_name.lower())
        base = re.sub(r'[\d\.\-]+$', '', base)  # Remove trailing numbers
        
        return base, size
    
    def _find_fallback_model(self, model_name: str, req_base: str, req_size: int) -> Optional[str]:
        """
        Find a suitable fallback model for fast mode
        
        Args:
            model_name: Original model name
            req_base: Base model name
            req_size: Model size in billions
            
        Returns:
            OpenRouter model name or None
        """
        # For medium-sized models, prefer Mistral Nemo
        if 7 <= req_size <= 32 and "mistral-nemo" in self.ollama_to_openrouter:
            return self.ollama_to_openrouter["mistral-nemo"]
        
        # Find candidates in the same family
        candidates = []
        for map_key in self.ollama_to_openrouter.keys():
            cand_base, cand_size = self._parse_model_name(map_key)
            if (req_base.startswith(cand_base) or cand_base.startswith(req_base)) and cand_size >= req_size:
                candidates.append((map_key, cand_size))
        
        if candidates:
            # Sort by size and pick the smallest that meets requirements
            candidates.sort(key=lambda x: x[1])
            return self.ollama_to_openrouter[candidates[0][0]]
        
        # Ultimate fallback
        return self.ollama_to_openrouter.get("mistral-nemo")
    
    def strip_prefix(self, model: str) -> str:
        """
        Remove provider prefix from model string

        Supported prefixes:
        - local/
        - bedrock/
        - anthropic/
        - openai/
        - openrouter/
        - mistral/
        - ionos/

        Args:
            model: Model string with or without prefix

        Returns:
            Model name without prefix
        """
        if model.startswith("local/"):
            return model[6:]
        elif model.startswith("bedrock/"):
            return model[8:]
        elif model.startswith("anthropic/"):
            return model[10:]
        elif model.startswith("openai/"):
            return model[7:]
        elif model.startswith("openrouter/"):
            return model[11:]
        elif model.startswith("mistral/"):
            return model[8:]
        elif model.startswith("ionos/"):
            return model[6:]
        return model


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
    
    def get_ollama_models(self) -> List[str]:
        """
        Get available Ollama models from API
        Transferred from prompt_interception_engine
        """
        try:
            from config import OLLAMA_API_BASE_URL
            response = requests.get(f"{OLLAMA_API_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
            return [m.get('name', '') for m in response.json().get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to get Ollama models: {e}")
            return []
    
    def find_openrouter_fallback(self, failed_model: str, debug: bool = False) -> str:
        """
        Find fallback for OpenRouter model (when API call fails)
        Transferred from prompt_interception_engine
        
        Args:
            failed_model: The model that failed
            debug: Enable debug logging
            
        Returns:
            Fallback model name
        """
        openrouter_models = self.get_openrouter_models()
        
        # Preferred fallbacks in order
        fallbacks = [
            "anthropic/claude-haiku-4.5",
            "meta-llama/llama-3.2-1b-instruct",
            "mistralai/ministral-8b"
        ]
        
        for fallback in fallbacks:
            if fallback in openrouter_models and fallback != failed_model:
                if debug:
                    logger.info(f"[FALLBACK] OpenRouter: {failed_model} → {fallback}")
                return fallback
        
        # Ultimate fallback
        if debug:
            logger.warning(f"[FALLBACK] Using ultimate OpenRouter fallback: claude-3-haiku")
        return "anthropic/claude-haiku-4.5"
    
    def find_ollama_fallback(self, failed_model: str, debug: bool = False) -> Optional[str]:
        """
        Find fallback for Ollama model (when model unavailable/fails)
        Transferred from prompt_interception_engine
        
        Args:
            failed_model: The model that failed
            debug: Enable debug logging
            
        Returns:
            Fallback model name or None if no models available
        """
        available_models = self.get_ollama_models()
        if not available_models:
            logger.error("[FALLBACK] No Ollama models available")
            return None

        # Preferred fallbacks in order (mistral-nemo is faster than gemma2:9b)
        preferred = ["mistral-nemo", "llama3.2:1b", "llama3.1:8b"]
        for pref in preferred:
            if pref in available_models and pref != failed_model:
                if debug:
                    logger.info(f"[FALLBACK] Ollama: {failed_model} → {pref}")
                return pref
        
        # First available model as ultimate fallback
        fallback = available_models[0] if available_models else None
        if debug and fallback:
            logger.warning(f"[FALLBACK] Using first available Ollama model: {fallback}")
        return fallback
    
    def extract_model_name(self, full_model_string: str) -> str:
        """
        Extract real model name from dropdown format
        Supports all provider prefixes: local/, anthropic/, openai/, openrouter/

        Args:
            full_model_string: Model string (may have prefix and metadata)

        Returns:
            Clean model name without prefix or metadata
        """
        if full_model_string.startswith("bedrock/"):
            without_prefix = full_model_string[8:]
            return without_prefix.split(" [")[0]
        elif full_model_string.startswith("anthropic/"):
            without_prefix = full_model_string[10:]
            return without_prefix.split(" [")[0]
        elif full_model_string.startswith("openai/"):
            without_prefix = full_model_string[7:]
            return without_prefix.split(" [")[0]
        elif full_model_string.startswith("openrouter/"):
            without_prefix = full_model_string[11:]
            return without_prefix.split(" [")[0]
        elif full_model_string.startswith("mistral/"):
            without_prefix = full_model_string[8:]
            return without_prefix.split(" [")[0]
        elif full_model_string.startswith("ionos/"):
            without_prefix = full_model_string[6:]
            return without_prefix.split(" [")[0]
        elif full_model_string.startswith("local/"):
            without_prefix = full_model_string[6:]
            return without_prefix.split(" [")[0]
        else:
            return full_model_string.split(" [")[0]


# Singleton instance
model_selector = ModelSelector()
