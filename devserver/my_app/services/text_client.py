"""
Text HTTP Client — Interface to GPU service's Latent Text Lab

Calls the shared GPU service (port 17803) via HTTP REST for
dekonstruktive LLM operations (embedding, attention, token surgery).

Session 175: Initial implementation for Latent Text Lab backend.
"""

import logging
from typing import Optional, List, Dict, Any, AsyncGenerator

logger = logging.getLogger(__name__)


class TextClient:
    """HTTP client for the GPU service's text backend.

    Provides access to dekonstruktive LLM operations:
    - Embedding extraction and interpolation
    - Attention map visualization
    - Token-level logit manipulation (surgery)
    - Layer-by-layer analysis
    - Seed variation generation
    """

    def __init__(self):
        from config import GPU_SERVICE_URL, GPU_SERVICE_TIMEOUT
        self.base_url = GPU_SERVICE_URL.rstrip('/')
        self.timeout = GPU_SERVICE_TIMEOUT
        logger.info(f"[TEXT-CLIENT] Initialized: url={self.base_url}, timeout={self.timeout}s")

    def _post(self, path: str, data: dict, timeout: Optional[int] = None) -> Optional[dict]:
        """Synchronous POST to GPU service. Returns JSON response or None."""
        import requests
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=data, timeout=timeout or self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            logger.error(f"[TEXT-CLIENT] GPU service unreachable at {url}")
            return None
        except requests.Timeout:
            logger.error(f"[TEXT-CLIENT] Request timed out: {path}")
            return None
        except Exception as e:
            logger.error(f"[TEXT-CLIENT] Request failed: {e}")
            return None

    def _get(self, path: str) -> Optional[dict]:
        """Synchronous GET to GPU service. Returns JSON response or None."""
        import requests
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[TEXT-CLIENT] GET failed: {e}")
            return None

    # =========================================================================
    # Model Management
    # =========================================================================

    async def load_model(
        self,
        model_id: str,
        quantization: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load an LLM model.

        Args:
            model_id: HuggingFace model ID or preset name
            quantization: Optional quantization (bf16, fp16, int8, int4, nf4)

        Returns:
            Dict with success, model_id, quantization, vram_mb
        """
        import asyncio
        data = {"model_id": model_id}
        if quantization:
            data["quantization"] = quantization

        result = await asyncio.to_thread(self._post, '/api/text/load', data)
        return result or {"error": "GPU service unreachable"}

    async def unload_model(self, model_id: str) -> Dict[str, Any]:
        """Unload a specific model."""
        import asyncio
        result = await asyncio.to_thread(
            self._post, '/api/text/unload', {'model_id': model_id}
        )
        return result or {"error": "GPU service unreachable"}

    async def get_loaded_models(self) -> List[Dict[str, Any]]:
        """Get list of currently loaded models."""
        import asyncio
        result = await asyncio.to_thread(self._get, '/api/text/models')
        if result:
            return result.get("models", [])
        return []

    async def get_presets(self, scenario: str = "qwen") -> Dict[str, Any]:
        """Get available model presets with VRAM info."""
        import asyncio
        result = await asyncio.to_thread(
            self._get, f'/api/text/presets?scenario={scenario}'
        )
        return result or {}

    # =========================================================================
    # Dekonstruktive Operations
    # =========================================================================

    async def get_prompt_embedding(
        self,
        text: str,
        model_id: str,
        layer: int = -1
    ) -> Dict[str, Any]:
        """
        Get embedding representation of a prompt.

        Args:
            text: Input text
            model_id: Model to use
            layer: Which layer's hidden state (-1 = last)

        Returns:
            Dict with embedding stats
        """
        import asyncio
        data = {"text": text, "model_id": model_id, "layer": layer}
        result = await asyncio.to_thread(self._post, '/api/text/embedding', data)
        return result or {"error": "GPU service unreachable"}

    async def interpolate_prompts(
        self,
        prompt_a: str,
        prompt_b: str,
        model_id: str,
        steps: int = 5,
        layer: int = -1
    ) -> Dict[str, Any]:
        """
        Analyze embedding space between two prompts.

        Returns statistics at each interpolation point.
        """
        import asyncio
        data = {
            "prompt_a": prompt_a,
            "prompt_b": prompt_b,
            "model_id": model_id,
            "steps": steps,
            "layer": layer
        }
        result = await asyncio.to_thread(self._post, '/api/text/interpolate', data)
        return result or {"error": "GPU service unreachable"}

    async def get_attention_map(
        self,
        text: str,
        model_id: str,
        layer: Optional[int] = None,
        head: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get attention patterns for visualization.

        Args:
            text: Input text
            model_id: Model to use
            layer: Specific layer (None = all layers, aggregated)
            head: Specific head (None = all heads, averaged)

        Returns:
            Dict with tokens and attention weights
        """
        import asyncio
        data = {"text": text, "model_id": model_id}
        if layer is not None:
            data["layer"] = layer
        if head is not None:
            data["head"] = head

        result = await asyncio.to_thread(self._post, '/api/text/attention', data)
        return result or {"error": "GPU service unreachable"}

    async def generate_with_token_surgery(
        self,
        prompt: str,
        model_id: str,
        boost_tokens: Optional[List[str]] = None,
        suppress_tokens: Optional[List[str]] = None,
        boost_factor: float = 2.0,
        max_new_tokens: int = 50,
        temperature: float = 0.7,
        seed: int = -1
    ) -> Dict[str, Any]:
        """
        Generate text with logit manipulation for bias exploration.

        Args:
            prompt: Input prompt
            model_id: Model to use
            boost_tokens: Words to make more likely
            suppress_tokens: Words to suppress
            boost_factor: Multiplier for boosted tokens
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            seed: Random seed (-1 for random)

        Returns:
            Dict with generated text and metadata
        """
        import asyncio
        data = {
            "prompt": prompt,
            "model_id": model_id,
            "boost_tokens": boost_tokens,
            "suppress_tokens": suppress_tokens,
            "boost_factor": boost_factor,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "seed": seed
        }
        result = await asyncio.to_thread(
            self._post, '/api/text/generate', data, timeout=120
        )
        return result or {"error": "GPU service unreachable"}

    async def generate_streaming(
        self,
        prompt: str,
        model_id: str,
        max_new_tokens: int = 100,
        temperature: float = 0.7,
        seed: int = -1
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate text with real-time SSE streaming.

        Yields:
            {"type": "token", "token": "...", "token_id": N}
            {"type": "done", "full_text": "..."}
            {"type": "error", "message": "..."}
        """
        import requests
        import json

        url = f"{self.base_url}/api/text/generate/stream"
        data = {
            "prompt": prompt,
            "model_id": model_id,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "seed": seed
        }

        try:
            with requests.post(url, json=data, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            try:
                                chunk = json.loads(line_str[6:])
                                yield chunk
                            except json.JSONDecodeError:
                                continue
        except requests.ConnectionError:
            yield {"type": "error", "message": "GPU service unreachable"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}

    # =========================================================================
    # Wissenschaftliche Methoden (Session 177)
    # =========================================================================

    async def rep_engineering(
        self,
        contrast_pairs: List[Dict[str, str]],
        model_id: str,
        target_layer: int = -1,
        test_text: Optional[str] = None,
        alpha: float = 1.0,
        max_new_tokens: int = 50,
        temperature: float = 0.7,
        seed: int = -1
    ) -> Dict[str, Any]:
        """Representation Engineering: concept directions via contrast pairs."""
        import asyncio
        data = {
            "contrast_pairs": contrast_pairs,
            "model_id": model_id,
            "target_layer": target_layer,
            "test_text": test_text,
            "alpha": alpha,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "seed": seed,
        }
        result = await asyncio.to_thread(
            self._post, '/api/text/rep-engineering', data, timeout=120
        )
        return result or {"error": "GPU service unreachable"}

    async def compare_models(
        self,
        text: str,
        model_id_a: str,
        model_id_b: str,
        max_new_tokens: int = 50,
        temperature: float = 0.7,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Compare two models' internal representations."""
        import asyncio
        data = {
            "text": text,
            "model_id_a": model_id_a,
            "model_id_b": model_id_b,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "seed": seed,
        }
        result = await asyncio.to_thread(
            self._post, '/api/text/compare', data, timeout=180
        )
        return result or {"error": "GPU service unreachable"}

    async def bias_probe(
        self,
        prompt: str,
        model_id: str,
        bias_type: str = "gender",
        custom_boost: Optional[List[str]] = None,
        custom_suppress: Optional[List[str]] = None,
        num_samples: int = 3,
        max_new_tokens: int = 50,
        temperature: float = 0.7,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Systematic bias probing through controlled token manipulation."""
        import asyncio
        data = {
            "prompt": prompt,
            "model_id": model_id,
            "bias_type": bias_type,
            "custom_boost": custom_boost,
            "custom_suppress": custom_suppress,
            "num_samples": num_samples,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "seed": seed,
        }
        result = await asyncio.to_thread(
            self._post, '/api/text/bias-probe', data, timeout=180
        )
        return result or {"error": "GPU service unreachable"}

    async def generate_variations(
        self,
        prompt: str,
        model_id: str,
        num_variations: int = 5,
        temperature: float = 0.8,
        base_seed: int = 42,
        max_new_tokens: int = 50
    ) -> Dict[str, Any]:
        """
        Generate deterministic variations with different seeds.

        Useful for exploring the stochastic nature of generation.
        """
        import asyncio
        data = {
            "prompt": prompt,
            "model_id": model_id,
            "num_variations": num_variations,
            "temperature": temperature,
            "base_seed": base_seed,
            "max_new_tokens": max_new_tokens
        }
        result = await asyncio.to_thread(
            self._post, '/api/text/variations', data, timeout=180
        )
        return result or {"error": "GPU service unreachable"}

    async def compare_layer_outputs(
        self,
        text: str,
        model_id: str
    ) -> Dict[str, Any]:
        """
        Analyze how representations change through layers.

        Returns statistics for each layer's hidden state.
        """
        import asyncio
        data = {"text": text, "model_id": model_id}
        result = await asyncio.to_thread(self._post, '/api/text/layers', data)
        return result or {"error": "GPU service unreachable"}


# =============================================================================
# Singleton / Factory
# =============================================================================

_client: Optional[TextClient] = None


def get_text_client() -> TextClient:
    """Get TextClient singleton."""
    global _client
    if _client is None:
        _client = TextClient()
    return _client


def reset_text_client():
    """Reset singleton (for testing)."""
    global _client
    _client = None
