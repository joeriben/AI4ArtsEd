"""
LLM Backend — Local LLM inference via llama-cpp-python (in-process).

Runs small GGUF models (safety, DSGVO, VLM) directly
in the GPU Service process with full VRAM coordinator integration.

Models:
- qwen3:1.7b — DSGVO verification, text tasks
- llama-guard3:1b — Stage 3 safety (Llama Guard S1-S13)
- qwen3-vl:2b — VLM safety checks (image classification, workshop-validated)
- qwen2.5-vl:2b — VLM fallback (NOT recommended: hallucinates UNSAFE on SAFE/UNSAFE prompts)
"""

import gc
import logging
import os
import threading
import time
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Model definitions: alias → config
MODEL_DIR = os.path.expanduser("~/ai/llama-server-models")

MODEL_CONFIGS = {
    # ── Chat-capable models (appear in Compare Hub) ──────────────────────
    "qwen3:1.7b": {
        "model_path": os.path.join(MODEL_DIR, "Qwen3-1.7B-Q8_0.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 2000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Qwen 3 1.7B",
    },
    "qwen3:4b": {
        "model_path": os.path.join(MODEL_DIR, "Qwen3-4B-Q8_0.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 4500,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Qwen 3 4B",
    },
    "phi-3.5-mini": {
        "model_path": os.path.join(MODEL_DIR, "Phi-3.5-mini-instruct-Q8_0.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 4000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Phi 3.5 Mini (Microsoft)",
    },
    "gemma-2-2b": {
        "model_path": os.path.join(MODEL_DIR, "gemma-2-2b-it-Q8_0.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 3000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Gemma 2 2B (Google)",
    },
    # ── Utility models (safety, VLM — not for Compare Hub) ──────────────
    "llama-guard3:1b": {
        "model_path": os.path.join(MODEL_DIR, "Llama-Guard-3-1B.Q8_0.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 1800,
        "chat_handler": None,
        "chat_capable": False,
        "display_name": "Llama Guard 3 1B",
    },
    "qwen2.5-vl:2b": {
        "model_path": os.path.join(MODEL_DIR, "qwen25-vl-2b", "Qwen2.5_VL_2B.Q4_K_M.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "qwen25-vl-2b", "Qwen2.5_VL_2B.mmproj-f16.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 2500,
        "chat_handler": "qwen25vl",
        "chat_capable": False,
        "vlm_capable": True,
        "display_name": "Qwen 2.5 VL 2B",
    },
    "qwen3-vl:2b": {
        "model_path": os.path.join(MODEL_DIR, "qwen3-vl-2b", "Qwen3VL-2B-Instruct-Q4_K_M.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "qwen3-vl-2b", "mmproj-Qwen3VL-2B-Instruct-F16.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 2500,
        "chat_handler": "qwen25vl",  # Qwen25VLChatHandler works for qwen3-vl too
        "chat_capable": False,
        "vlm_capable": True,
        "display_name": "Qwen 3 VL 2B",
    },
    "qwen3-vl:4b": {
        "model_path": os.path.join(MODEL_DIR, "qwen3-vl-4b", "Qwen3-VL-4B-Instruct-Q4_K_M.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "qwen3-vl-4b", "mmproj-F16.gguf"),
        "n_ctx": 4096,
        "n_gpu_layers": -1,
        "estimated_vram_mb": 4500,
        "chat_handler": "qwen25vl",  # Qwen25VLChatHandler works for qwen3-vl
        "chat_capable": False,
        "vlm_capable": True,
        "display_name": "Qwen 3 VL 4B",
    },
}

# Aliases for backward compatibility with legacy model names
MODEL_ALIASES = {
    "llama-guard3:latest": "llama-guard3:1b",
}


class LLMBackend:
    """
    In-process LLM inference with VRAM coordinator integration.

    Each model is a separate llama_cpp.Llama instance.
    Models are loaded lazily on first use.
    """

    def __init__(self):
        self._models: Dict[str, Any] = {}  # alias → Llama instance
        self._model_vram_mb: Dict[str, float] = {}
        self._model_last_used: Dict[str, float] = {}
        self._model_in_use: Dict[str, int] = {}
        self._load_lock = threading.Lock()

        self._register_with_coordinator()
        logger.info("[LLM] Initialized: in-process llama-cpp-python backend")

    def _register_with_coordinator(self):
        """Register with VRAM coordinator for cross-backend eviction."""
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[LLM] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[LLM] Failed to register with VRAM coordinator: {e}")

    # =========================================================================
    # VRAMBackend Protocol Implementation
    # =========================================================================

    def get_backend_id(self) -> str:
        return "llm"

    def get_registered_models(self) -> List[Dict[str, Any]]:
        from services.vram_coordinator import EvictionPriority
        return [
            {
                "model_id": mid,
                "vram_mb": self._model_vram_mb.get(mid, 0),
                "priority": EvictionPriority.LOW,  # LLMs are cheap to reload
                "last_used": self._model_last_used.get(mid, 0),
                "in_use": self._model_in_use.get(mid, 0),
            }
            for mid in self._models
        ]

    def evict_model(self, model_id: str) -> bool:
        """Evict a specific model (called by coordinator)."""
        return self._unload_model(model_id)

    # =========================================================================
    # Model Loading / Unloading
    # =========================================================================

    def _resolve_alias(self, model: str) -> str:
        """Resolve model alias to canonical name."""
        model = model.replace("local/", "") if model.startswith("local/") else model
        return MODEL_ALIASES.get(model, model)

    def _load_model(self, model_alias: str) -> bool:
        """Load a model into GPU memory."""
        from llama_cpp import Llama

        config = MODEL_CONFIGS.get(model_alias)
        if not config:
            logger.error(f"[LLM] Unknown model: {model_alias}")
            return False

        if not os.path.exists(config["model_path"]):
            logger.error(f"[LLM] Model file not found: {config['model_path']}")
            return False

        with self._load_lock:
            if model_alias in self._models:
                return True  # Already loaded

            # Request VRAM from coordinator
            estimated_mb = config["estimated_vram_mb"]
            try:
                from services.vram_coordinator import get_vram_coordinator, EvictionPriority
                coordinator = get_vram_coordinator()
                coordinator.request_vram("llm", estimated_mb, EvictionPriority.NORMAL)
            except Exception as e:
                logger.warning(f"[LLM] VRAM coordinator request failed: {e}")

            logger.info(f"[LLM] Loading {model_alias} from {config['model_path']}...")

            try:
                import torch
                vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

                # Build chat handler for VLM models
                chat_handler = None
                if config.get("chat_handler") == "qwen25vl":
                    from llama_cpp.llama_chat_format import Qwen25VLChatHandler
                    mmproj = config.get("mmproj_path", "")
                    if not os.path.exists(mmproj):
                        logger.error(f"[LLM] mmproj not found: {mmproj}")
                        return False
                    chat_handler = Qwen25VLChatHandler(clip_model_path=mmproj)
                    logger.info(f"[LLM] VLM chat handler created: Qwen25VLChatHandler")

                llm = Llama(
                    model_path=config["model_path"],
                    n_ctx=config["n_ctx"],
                    n_gpu_layers=config["n_gpu_layers"],
                    chat_handler=chat_handler,
                    verbose=False,
                )

                vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
                actual_vram_mb = (vram_after - vram_before) / (1024 * 1024)

                self._models[model_alias] = llm
                self._model_vram_mb[model_alias] = actual_vram_mb if actual_vram_mb > 0 else estimated_mb
                self._model_last_used[model_alias] = time.time()
                self._model_in_use[model_alias] = 0

                logger.info(f"[LLM] Loaded {model_alias} (VRAM: {self._model_vram_mb[model_alias]:.0f}MB)")
                return True

            except Exception as e:
                logger.error(f"[LLM] Failed to load {model_alias}: {e}")
                import traceback
                traceback.print_exc()
                return False

    def _unload_model(self, model_alias: str) -> bool:
        """Unload a model and free VRAM."""
        if model_alias not in self._models:
            return False

        try:
            import torch

            del self._models[model_alias]
            self._model_vram_mb.pop(model_alias, None)
            self._model_last_used.pop(model_alias, None)
            self._model_in_use.pop(model_alias, None)

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"[LLM] Unloaded {model_alias}")
            return True
        except Exception as e:
            logger.error(f"[LLM] Error unloading {model_alias}: {e}")
            return False

    def _get_model(self, model: str):
        """Get a loaded model, loading it on demand."""
        alias = self._resolve_alias(model)
        if alias not in self._models:
            if not self._load_model(alias):
                return None
        self._model_last_used[alias] = time.time()
        return self._models.get(alias)

    # =========================================================================
    # Inference
    # =========================================================================

    def chat(self, model: str, messages: list, images: Optional[list] = None,
             temperature: float = 0.7, max_tokens: int = 500,
             repetition_penalty: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Chat completion (OpenAI-compatible message format).

        For VLM: images should be base64 strings, injected into the first user message
        as OpenAI-style image_url content parts.
        """
        alias = self._resolve_alias(model)
        llm = self._get_model(alias)
        if llm is None:
            return None

        self._model_in_use[alias] = self._model_in_use.get(alias, 0) + 1
        try:
            final_messages = self._build_messages_with_images(messages, images)

            kwargs = {
                "messages": final_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if repetition_penalty is not None:
                kwargs["repeat_penalty"] = repetition_penalty

            result = llm.create_chat_completion(**kwargs)

            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return {
                "content": content,
                "thinking": None,
                "tool_calls": None,
            }
        except Exception as e:
            logger.error(f"[LLM] Chat failed ({alias}): {e}")
            return None
        finally:
            self._model_in_use[alias] = max(0, self._model_in_use.get(alias, 1) - 1)

    def generate(self, model: str, prompt: str,
                 temperature: float = 0.7, max_tokens: int = 500,
                 repetition_penalty: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Raw text completion."""
        alias = self._resolve_alias(model)
        llm = self._get_model(alias)
        if llm is None:
            return None

        self._model_in_use[alias] = self._model_in_use.get(alias, 0) + 1
        try:
            kwargs = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if repetition_penalty is not None:
                kwargs["repeat_penalty"] = repetition_penalty

            result = llm.create_completion(**kwargs)

            text = result.get("choices", [{}])[0].get("text", "").strip()
            return {
                "response": text,
                "thinking": None,
            }
        except Exception as e:
            logger.error(f"[LLM] Generate failed ({alias}): {e}")
            return None
        finally:
            self._model_in_use[alias] = max(0, self._model_in_use.get(alias, 1) - 1)

    def _build_messages_with_images(self, messages: list, images: Optional[list] = None) -> list:
        """Convert images to OpenAI multimodal content format."""
        if not images:
            return messages

        result = []
        images_injected = False
        for msg in messages:
            m = dict(msg)
            if not images_injected and m.get("role") == "user":
                text_content = m.get("content", "")
                content_parts = [{"type": "text", "text": text_content}]
                for img_b64 in images:
                    if not img_b64.startswith("data:"):
                        img_b64 = f"data:image/jpeg;base64,{img_b64}"
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": img_b64}
                    })
                m["content"] = content_parts
                images_injected = True
            result.append(m)
        return result

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """List loaded models for status endpoint."""
        return [
            {
                "id": mid,
                "vram_mb": self._model_vram_mb.get(mid, 0),
                "in_use": self._model_in_use.get(mid, 0),
                "last_used": self._model_last_used.get(mid, 0),
            }
            for mid in self._models
        ]

    def get_available_models(self) -> List[str]:
        """List all configured model aliases."""
        all_models = list(MODEL_CONFIGS.keys())
        all_models.extend(MODEL_ALIASES.keys())
        return all_models

    def get_chat_models(self) -> List[Dict[str, Any]]:
        """List chat-capable models with availability info for Compare Hub."""
        result = []
        for alias, config in MODEL_CONFIGS.items():
            if not config.get("chat_capable", False):
                continue
            result.append({
                "id": alias,
                "display_name": config.get("display_name", alias),
                "available": os.path.exists(config["model_path"]),
                "estimated_vram_mb": config.get("estimated_vram_mb", 0),
            })
        return result

    def get_vlm_models(self) -> List[Dict[str, Any]]:
        """List VLM-capable models with availability info for Compare Hub."""
        result = []
        for alias, config in MODEL_CONFIGS.items():
            if not config.get("vlm_capable", False):
                continue
            model_ok = os.path.exists(config["model_path"])
            mmproj_ok = os.path.exists(config.get("mmproj_path", ""))
            result.append({
                "id": alias,
                "display_name": config.get("display_name", alias),
                "available": model_ok and mmproj_ok,
                "estimated_vram_mb": config.get("estimated_vram_mb", 0),
            })
        return result

    def is_available(self) -> bool:
        """Check if llama-cpp-python is importable."""
        try:
            import llama_cpp
            return True
        except ImportError:
            return False


# =========================================================================
# Singleton
# =========================================================================

_backend: Optional[LLMBackend] = None


def get_llm_backend() -> LLMBackend:
    """Get or create the LLM backend singleton."""
    global _backend
    if _backend is None:
        _backend = LLMBackend()
    return _backend
