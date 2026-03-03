"""
Text Backend - Dekonstruktive LLM operations for Latent Text Lab

Session 175: Experimental text generation with access to model internals.

Features:
- Auto-quantization based on available VRAM (bf16 → int8 → int4)
- VRAM coordination via VRAMCoordinator
- Dekonstruktive methods:
  - Embedding extraction and interpolation
  - Attention map visualization
  - Token-level logit manipulation (surgery)
  - Layer-by-layer analysis
  - Deterministic seed variations

Usage:
    backend = get_text_backend()
    await backend.load_model("Qwen/Qwen2.5-3B-Instruct")
    result = await backend.generate_with_token_surgery(
        prompt="Write a poem about nature",
        boost_tokens=["dark", "shadow"],
        suppress_tokens=["light", "sun"]
    )
"""

import gc
import logging
import threading
import time
import re
from typing import Optional, List, Dict, Any, AsyncGenerator
import asyncio

logger = logging.getLogger(__name__)


# =============================================================================
# VRAM Estimation
# =============================================================================

def estimate_model_vram(model_id: str, quantization: str = "bf16") -> float:
    """
    Estimate VRAM requirement for a model in GB.

    Uses config presets if available, falls back to parameter-count heuristic.
    """
    from config import TEXT_MODEL_PRESETS, TEXT_QUANT_MULTIPLIERS

    # Check presets first
    for preset in TEXT_MODEL_PRESETS.values():
        if preset["id"] == model_id:
            base_vram = preset["vram_gb"]
            break
    else:
        # Heuristic: ~2GB per billion parameters (bf16)
        match = re.search(r'(\d+)[Bb]', model_id)
        if match:
            params_b = int(match.group(1))
            base_vram = params_b * 2.0
        else:
            # Conservative default
            base_vram = 20.0
            logger.warning(f"[TEXT] Unknown model {model_id}, assuming {base_vram}GB")

    multiplier = TEXT_QUANT_MULTIPLIERS.get(quantization, 1.0)
    return base_vram * multiplier


def choose_quantization(model_id: str, available_vram_gb: float) -> tuple[str, float]:
    """
    Choose optimal quantization level for available VRAM.

    Strategy:
    1. Try bf16 (best quality)
    2. Fall back to int8 if needed
    3. Fall back to int4 as last resort

    Returns (quantization_string, estimated_vram_gb).
    """
    for quant in ["bf16", "int8", "int4"]:
        estimated = estimate_model_vram(model_id, quant)
        # Leave 10% headroom
        if estimated * 1.1 < available_vram_gb:
            return quant, estimated

    # Even int4 doesn't fit - return it anyway (will fail at load time)
    return "int4", estimate_model_vram(model_id, "int4")


class TextBackend:
    """
    Dekonstruktive LLM operations with VRAM coordination.

    Integrates with VRAMCoordinator for cross-backend eviction.
    """

    def __init__(self):
        """Initialize text backend."""
        from config import TEXT_DEVICE, TEXT_DEFAULT_DTYPE

        self.device = TEXT_DEVICE
        self.default_dtype = TEXT_DEFAULT_DTYPE

        # Model cache (mirrors DiffusersBackend pattern)
        self._models: Dict[str, tuple] = {}  # model_id -> (model, tokenizer)
        self._model_last_used: Dict[str, float] = {}
        self._model_vram_mb: Dict[str, float] = {}
        self._model_in_use: Dict[str, int] = {}
        self._model_quant: Dict[str, str] = {}
        self._load_lock = threading.Lock()

        # Register with VRAM coordinator
        self._register_with_coordinator()

        # Get total VRAM for planning
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                self._total_vram_gb = props.total_memory / 1024**3
            else:
                self._total_vram_gb = 0
        except ImportError:
            self._total_vram_gb = 0

        logger.info(f"[TEXT] Initialized: device={self.device}, total_vram={self._total_vram_gb:.1f}GB")

    def _register_with_coordinator(self):
        """Register with VRAM coordinator for cross-backend eviction."""
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[TEXT] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[TEXT] Failed to register with VRAM coordinator: {e}")

    # =========================================================================
    # VRAMBackend Protocol Implementation
    # =========================================================================

    def get_backend_id(self) -> str:
        """Unique identifier for this backend."""
        return "text"

    def get_registered_models(self) -> List[Dict[str, Any]]:
        """Return list of models with VRAM info for coordinator."""
        from services.vram_coordinator import EvictionPriority

        return [
            {
                "model_id": mid,
                "vram_mb": self._model_vram_mb.get(mid, 0),
                "priority": EvictionPriority.NORMAL,
                "last_used": self._model_last_used.get(mid, 0),
                "in_use": self._model_in_use.get(mid, 0),
            }
            for mid in self._models
        ]

    def evict_model(self, model_id: str) -> bool:
        """Evict a specific model (called by coordinator)."""
        return self._unload_model_sync(model_id)

    # =========================================================================
    # Model Loading
    # =========================================================================

    def _get_free_vram_gb(self) -> float:
        """Get currently free VRAM in GB (delegates to coordinator for NVML accuracy)."""
        try:
            from services.vram_coordinator import get_vram_coordinator
            return get_vram_coordinator().get_free_vram_mb(use_cache=False) / 1024
        except Exception:
            import torch
            if not torch.cuda.is_available():
                return 0
            total = torch.cuda.get_device_properties(0).total_memory
            allocated = torch.cuda.memory_allocated(0)
            return (total - allocated) / 1024**3

    def _load_model_sync(
        self,
        model_id: str,
        quantization: Optional[str] = None
    ) -> bool:
        """
        Load model with VRAM coordination.

        1. Estimate VRAM requirement
        2. Choose quantization if not specified
        3. Request VRAM from coordinator (triggers cross-backend eviction)
        4. Load model
        """
        with self._load_lock:
            import torch

            # Already loaded?
            if model_id in self._models:
                self._model_last_used[model_id] = time.time()
                return True

            # Determine quantization
            free_vram = self._get_free_vram_gb()
            if quantization is None:
                quantization, estimated_gb = choose_quantization(model_id, free_vram)
            else:
                estimated_gb = estimate_model_vram(model_id, quantization)

            required_mb = estimated_gb * 1024

            logger.info(
                f"[TEXT] Loading {model_id}: "
                f"quant={quantization}, estimated={estimated_gb:.1f}GB, "
                f"free={free_vram:.1f}GB"
            )

            # Request VRAM from coordinator (may evict other backends' models)
            try:
                from services.vram_coordinator import get_vram_coordinator, EvictionPriority
                coordinator = get_vram_coordinator()
                coordinator.request_vram("text", required_mb, EvictionPriority.NORMAL)
            except Exception as e:
                logger.warning(f"[TEXT] VRAM coordinator request failed: {e}")

            # Load model
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer

                vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

                tokenizer = AutoTokenizer.from_pretrained(model_id)
                if tokenizer.pad_token is None:
                    tokenizer.pad_token = tokenizer.eos_token

                # Build load kwargs — NO device_map, explicit .to(device) instead
                load_kwargs = {
                    "low_cpu_mem_usage": True,
                }

                if quantization == "bf16":
                    load_kwargs["dtype"] = torch.bfloat16
                elif quantization == "fp16":
                    load_kwargs["dtype"] = torch.float16
                elif quantization in ("int8", "int4", "nf4"):
                    from transformers import BitsAndBytesConfig

                    if quantization == "int8":
                        load_kwargs["quantization_config"] = BitsAndBytesConfig(
                            load_in_8bit=True
                        )
                    else:  # int4/nf4
                        load_kwargs["quantization_config"] = BitsAndBytesConfig(
                            load_in_4bit=True,
                            bnb_4bit_compute_dtype=torch.bfloat16,
                            bnb_4bit_quant_type="nf4" if quantization == "nf4" else "fp4"
                        )

                model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    **load_kwargs
                )
                model = model.to(self.device)
                model.config.output_hidden_states = True
                model.config.output_attentions = True
                model.eval()

                vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
                actual_vram_mb = (vram_after - vram_before) / (1024 * 1024)

                self._models[model_id] = (model, tokenizer)
                self._model_last_used[model_id] = time.time()
                self._model_vram_mb[model_id] = actual_vram_mb
                self._model_quant[model_id] = quantization

                logger.info(
                    f"[TEXT] Loaded {model_id}: "
                    f"quant={quantization}, actual_vram={actual_vram_mb:.0f}MB"
                )
                return True

            except Exception as e:
                logger.error(f"[TEXT] Failed to load {model_id}: {e}")
                import traceback
                traceback.print_exc()
                return False

    def _unload_model_sync(self, model_id: str) -> bool:
        """Unload a model from memory."""
        import torch

        if model_id not in self._models:
            return False

        try:
            del self._models[model_id]
            self._model_last_used.pop(model_id, None)
            self._model_vram_mb.pop(model_id, None)
            self._model_in_use.pop(model_id, None)
            self._model_quant.pop(model_id, None)

            if torch.cuda.is_available():
                gc.collect()
                torch.cuda.empty_cache()

            logger.info(f"[TEXT] Unloaded {model_id}")
            return True
        except Exception as e:
            logger.error(f"[TEXT] Error unloading {model_id}: {e}")
            return False

    async def load_model(
        self,
        model_id: str,
        quantization: Optional[str] = None
    ) -> bool:
        """Async wrapper for model loading."""
        return await asyncio.to_thread(self._load_model_sync, model_id, quantization)

    async def unload_model(self, model_id: str) -> bool:
        """Async wrapper for model unloading."""
        return await asyncio.to_thread(self._unload_model_sync, model_id)

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """Get info about currently loaded models."""
        return [
            {
                "model_id": mid,
                "vram_mb": self._model_vram_mb.get(mid, 0),
                "quantization": self._model_quant.get(mid, "unknown"),
                "in_use": self._model_in_use.get(mid, 0) > 0,
                "last_used": self._model_last_used.get(mid, 0),
            }
            for mid in self._models
        ]

    # =========================================================================
    # DEKONSTRUKTIVE METHODS
    # =========================================================================

    async def get_prompt_embedding(
        self,
        text: str,
        model_id: str,
        layer: int = -1
    ) -> Dict[str, Any]:
        """
        Extract embedding representation of a prompt.

        Args:
            text: Input text
            model_id: Model to use
            layer: Which layer's hidden state (-1 = last)

        Returns:
            Dict with embedding stats and optionally the embedding itself
        """
        import torch

        if not await self.load_model(model_id):
            return {"error": f"Failed to load model {model_id}"}

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            with torch.no_grad():
                outputs = model(**inputs)

            # Get specified layer's hidden state
            hidden_states = outputs.hidden_states
            if layer < 0:
                layer = len(hidden_states) + layer
            embedding = hidden_states[layer]

            # Mean pool over sequence, convert to float32 for numpy/stats compatibility
            pooled = embedding.mean(dim=1).float()

            return {
                "model_id": model_id,
                "text": text,
                "layer": layer,
                "num_layers": len(hidden_states),
                "embedding_dim": pooled.shape[-1],
                "embedding_norm": float(pooled.norm()),
                "embedding_mean": float(pooled.mean()),
                "embedding_std": float(pooled.std()),
            }
        finally:
            self._model_in_use[model_id] -= 1

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
        (Full generation from interpolated embeddings requires more complex projection)
        """
        import torch

        if not await self.load_model(model_id):
            return {"error": f"Failed to load model {model_id}"}

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            # Encode both prompts
            inputs_a = tokenizer(prompt_a, return_tensors="pt").to(model.device)
            inputs_b = tokenizer(prompt_b, return_tensors="pt").to(model.device)

            with torch.no_grad():
                outputs_a = model(**inputs_a)
                outputs_b = model(**inputs_b)

            # Convert to float32 for consistent numeric operations
            hidden_a = outputs_a.hidden_states[layer].mean(dim=1).float()
            hidden_b = outputs_b.hidden_states[layer].mean(dim=1).float()

            distance = (hidden_a - hidden_b).norm().item()

            results = []
            for i in range(steps):
                alpha = i / (steps - 1) if steps > 1 else 0
                interpolated = (1 - alpha) * hidden_a + alpha * hidden_b

                results.append({
                    "alpha": alpha,
                    "prompt_a_influence": 1 - alpha,
                    "prompt_b_influence": alpha,
                    "embedding_norm": float(interpolated.norm()),
                    "distance_from_a": float((interpolated - hidden_a).norm()),
                    "distance_from_b": float((interpolated - hidden_b).norm()),
                })

            return {
                "model_id": model_id,
                "prompt_a": prompt_a,
                "prompt_b": prompt_b,
                "layer": layer,
                "total_distance": distance,
                "interpolation_points": results,
            }
        finally:
            self._model_in_use[model_id] -= 1

    async def get_attention_map(
        self,
        text: str,
        model_id: str,
        layer: Optional[int] = None,
        head: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract attention patterns for visualization.

        Args:
            text: Input text
            model_id: Model to use
            layer: Specific layer (None = all layers, aggregated)
            head: Specific head (None = all heads, averaged)

        Returns:
            Dict with tokens and attention weights
        """
        import torch

        if not await self.load_model(model_id):
            return {"error": f"Failed to load model {model_id}"}

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            raw_tokens = tokenizer.convert_ids_to_tokens(inputs.input_ids[0])

            with torch.no_grad():
                outputs = model(**inputs)

            attentions = outputs.attentions  # tuple of (batch, heads, seq, seq)
            num_layers = len(attentions)
            num_heads = attentions[0].shape[1]

            if layer is not None:
                # Single layer
                attn = attentions[layer].float()  # (1, heads, seq, seq)
                if head is not None:
                    attn = attn[:, head:head+1, :, :]
                attn = attn.mean(dim=1)  # Average over heads
                attn_matrix = attn[0]  # (seq, seq)
            else:
                # Average over all layers and heads
                stacked = torch.stack([a.float().mean(dim=1) for a in attentions])
                attn_matrix = stacked.mean(dim=0)[0]  # (seq, seq)

            # --- Post-process: strip special tokens, merge subwords ---
            special_ids = set()
            if tokenizer.bos_token_id is not None:
                special_ids.add(tokenizer.bos_token_id)
            if tokenizer.eos_token_id is not None:
                special_ids.add(tokenizer.eos_token_id)
            if tokenizer.pad_token_id is not None:
                special_ids.add(tokenizer.pad_token_id)

            input_ids = inputs.input_ids[0].tolist()

            # 1) Filter out special tokens
            keep = [i for i, tid in enumerate(input_ids) if tid not in special_ids]
            if len(keep) < len(raw_tokens):
                attn_matrix = attn_matrix[keep][:, keep]
                raw_tokens = [raw_tokens[i] for i in keep]

            # 2) Merge subwords into whole words
            # SentencePiece: word-start tokens begin with ▁ (U+2581)
            # BPE (GPT-style): continuation tokens start with ## or Ġ
            word_groups: list[list[int]] = []
            word_labels: list[str] = []

            for i, tok in enumerate(raw_tokens):
                tok_str = str(tok)
                is_word_start = (
                    i == 0
                    or tok_str.startswith('\u2581')  # SentencePiece ▁
                    or tok_str.startswith('Ġ')       # GPT-2/BPE Ġ
                    or (not tok_str.startswith('##') and i == 0)
                )
                # BPE continuation: ## prefix
                is_continuation = tok_str.startswith('##')

                if is_word_start and not is_continuation:
                    word_groups.append([i])
                    # Clean display: strip ▁ and Ġ prefix
                    clean = tok_str.lstrip('\u2581').lstrip('Ġ')
                    word_labels.append(clean if clean else tok_str)
                else:
                    if not word_groups:
                        word_groups.append([i])
                        word_labels.append(tok_str.lstrip('##'))
                    else:
                        word_groups[-1].append(i)
                        # Append to current word label (strip ## prefix)
                        suffix = tok_str.lstrip('##')
                        word_labels[-1] += suffix

            # Aggregate attention: sum columns (how much attention a word receives),
            # average rows (how a word distributes its attention)
            n_words = len(word_groups)
            n_toks = attn_matrix.shape[0]
            merged = torch.zeros(n_words, n_words, device=attn_matrix.device)

            for wi, src_indices in enumerate(word_groups):
                for wj, tgt_indices in enumerate(word_groups):
                    # Average over source tokens, sum over target tokens
                    block = attn_matrix[src_indices][:, tgt_indices]
                    # Sum targets, then average sources
                    merged[wi, wj] = block.sum(dim=1).mean(dim=0)

            # Re-normalize rows to sum to 1
            row_sums = merged.sum(dim=1, keepdim=True)
            row_sums = row_sums.clamp(min=1e-8)
            merged = merged / row_sums

            return {
                "model_id": model_id,
                "text": text,
                "tokens": word_labels,
                "num_layers": num_layers,
                "num_heads": num_heads,
                "layer_selected": layer,
                "head_selected": head,
                "attention_matrix": merged.cpu().tolist(),
            }
        finally:
            self._model_in_use[model_id] -= 1

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
        import torch
        import random

        if not await self.load_model(model_id):
            return {"error": f"Failed to load model {model_id}"}

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            if seed == -1:
                seed = random.randint(0, 2**32 - 1)
            torch.manual_seed(seed)

            # Convert boost/suppress tokens to IDs (bare + space-prefixed + case variants)
            boost_ids = self._resolve_token_ids(tokenizer, boost_tokens or [])
            suppress_ids = self._resolve_token_ids(tokenizer, suppress_tokens or [])

            if suppress_ids:
                logger.info(f"[TEXT] Surgery: suppressing {len(suppress_ids)} token IDs for {len(suppress_tokens)} words")
            if boost_ids:
                logger.info(f"[TEXT] Surgery: boosting {len(boost_ids)} token IDs for {len(boost_tokens)} words")

            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            generated = inputs.input_ids.clone()
            prompt_length = inputs.input_ids.shape[1]

            for _ in range(max_new_tokens):
                with torch.no_grad():
                    outputs = model(generated)
                    logits = outputs.logits[:, -1, :].float()  # float32 for stable softmax

                    # Apply surgery (additive boost — stable, no degeneration)
                    for tid in boost_ids:
                        if tid < logits.shape[-1]:
                            logits[:, tid] += boost_factor
                    for tid in suppress_ids:
                        if tid < logits.shape[-1]:
                            logits[:, tid] = -float('inf')

                    probs = torch.softmax(logits / temperature, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1)

                    generated = torch.cat([generated, next_token], dim=-1)

                    if next_token.item() == tokenizer.eos_token_id:
                        break

            generated_text = tokenizer.decode(generated[0], skip_special_tokens=True)
            new_text = tokenizer.decode(generated[0, prompt_length:], skip_special_tokens=True)

            return {
                "model_id": model_id,
                "prompt": prompt,
                "generated_text": generated_text,
                "new_text": new_text,
                "seed": seed,
                "temperature": temperature,
                "boost_tokens": list(boost_tokens or []),
                "suppress_tokens": list(suppress_tokens or []),
                "boost_factor": boost_factor,
                "tokens_generated": generated.shape[1] - prompt_length,
            }
        finally:
            self._model_in_use[model_id] -= 1

    async def generate_streaming(
        self,
        prompt: str,
        model_id: str,
        max_new_tokens: int = 100,
        temperature: float = 0.7,
        seed: int = -1
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate text with real-time token streaming (SSE).

        Yields:
            {"type": "token", "token": "...", "token_id": N}
            {"type": "done", "full_text": "..."}
            {"type": "error", "message": "..."}
        """
        import torch
        import random

        if not await self.load_model(model_id):
            yield {"type": "error", "message": f"Failed to load model {model_id}"}
            return

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            if seed == -1:
                seed = random.randint(0, 2**32 - 1)
            torch.manual_seed(seed)

            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            generated = inputs.input_ids.clone()
            input_len = inputs.input_ids.shape[1]
            prev_decoded = ""

            for i in range(max_new_tokens):
                with torch.no_grad():
                    outputs = model(generated)
                    logits = outputs.logits[:, -1, :].float()  # float32 for stable softmax

                    probs = torch.softmax(logits / temperature, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1)

                    generated = torch.cat([generated, next_token], dim=-1)

                    token_id = next_token.item()

                    # Incremental decode preserves SentencePiece whitespace (▁)
                    current_decoded = tokenizer.decode(
                        generated[0][input_len:], skip_special_tokens=True
                    )
                    new_text = current_decoded[len(prev_decoded):]
                    prev_decoded = current_decoded

                    yield {
                        "type": "token",
                        "token": new_text,
                        "token_id": token_id,
                        "step": i,
                    }

                    if token_id == tokenizer.eos_token_id:
                        break

            full_text = tokenizer.decode(generated[0], skip_special_tokens=True)
            yield {
                "type": "done",
                "full_text": full_text,
                "seed": seed,
                "tokens_generated": generated.shape[1] - inputs.input_ids.shape[1],
            }

        except Exception as e:
            yield {"type": "error", "message": str(e)}
        finally:
            self._model_in_use[model_id] -= 1

    async def compare_layer_outputs(
        self,
        text: str,
        model_id: str
    ) -> Dict[str, Any]:
        """
        Analyze how representations change through layers.

        Returns statistics for each layer's hidden state.
        """
        import torch
        import numpy as np

        if not await self.load_model(model_id):
            return [{"error": f"Failed to load model {model_id}"}]

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            inputs = tokenizer(text, return_tensors="pt").to(model.device)

            with torch.no_grad():
                outputs = model(**inputs)

            results = []
            prev_hidden = None

            for i, hidden_state in enumerate(outputs.hidden_states):
                hs = hidden_state[0].float().cpu().numpy()

                layer_stats = {
                    "layer": i,
                    "mean_activation": float(np.mean(hs)),
                    "std_activation": float(np.std(hs)),
                    "max_activation": float(np.max(hs)),
                    "min_activation": float(np.min(hs)),
                    "sparsity": float(np.mean(np.abs(hs) < 0.01)),
                    "l2_norm": float(np.linalg.norm(hs)),
                }

                # Change from previous layer
                if prev_hidden is not None:
                    delta = hs - prev_hidden
                    layer_stats["delta_norm"] = float(np.linalg.norm(delta))
                    layer_stats["delta_mean"] = float(np.mean(np.abs(delta)))

                prev_hidden = hs
                results.append(layer_stats)

            return {
                "model_id": model_id,
                "text": text,
                "num_layers": len(results),
                "layers": results,
            }
        finally:
            self._model_in_use[model_id] -= 1

    # =========================================================================
    # WISSENSCHAFTLICHE METHODEN (Session 177)
    # =========================================================================

    def _resolve_token_ids(self, tokenizer, words: list) -> set:
        """Resolve words to ALL matching token IDs (bare + space-prefixed + case variants).

        BPE tokenizers encode " he" and "he" as different token IDs.
        During generation, most tokens appear with a space prefix (▁he / Ġhe).
        Without resolving both variants, suppress/boost targets the wrong IDs.
        """
        token_ids = set()
        for word in words:
            # Bare token
            ids = tokenizer.encode(word, add_special_tokens=False)
            token_ids.update(ids)
            # Space-prefixed (most common in generated text)
            ids_space = tokenizer.encode(" " + word, add_special_tokens=False)
            token_ids.update(ids_space)
            # Capitalized variant (if lowercase input)
            if word and word[0].islower():
                cap = word.capitalize()
                token_ids.update(tokenizer.encode(cap, add_special_tokens=False))
                token_ids.update(tokenizer.encode(" " + cap, add_special_tokens=False))
        return token_ids

    def _get_decoder_layers(self, model):
        """Get decoder layers for various model architectures."""
        # LLaMA, Qwen, Mistral
        if hasattr(model, 'model') and hasattr(model.model, 'layers'):
            return list(model.model.layers)
        # GPT-2, GPT-Neo
        if hasattr(model, 'transformer') and hasattr(model.transformer, 'h'):
            return list(model.transformer.h)
        # Falcon
        if hasattr(model, 'transformer') and hasattr(model.transformer, 'layers'):
            return list(model.transformer.layers)
        return None

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
        """
        Representation Engineering (Zou et al. 2023, Li et al. 2024).

        Find concept directions in activation space via contrast pairs,
        then manipulate generation by adding/subtracting these directions.

        Args:
            contrast_pairs: [{"positive": "...", "negative": "..."}, ...]
            model_id: Model to use
            target_layer: Which layer to extract/manipulate (-1 = last)
            test_text: Optional text to project and manipulate
            alpha: Manipulation strength (-3 to +3)
            max_new_tokens: Max tokens for manipulated generation
            temperature: Sampling temperature
            seed: Random seed (-1 for random)

        Returns:
            Dict with concept direction info, projections, manipulated generation
        """
        import torch
        import random

        if not await self.load_model(model_id):
            return {"error": f"Failed to load model {model_id}"}

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            # 1. Extract hidden states for all contrast pairs
            differences = []
            pair_projections = []
            num_layers = None

            for pair in contrast_pairs:
                pos_inputs = tokenizer(pair["positive"], return_tensors="pt").to(model.device)
                neg_inputs = tokenizer(pair["negative"], return_tensors="pt").to(model.device)

                with torch.no_grad():
                    pos_outputs = model(**pos_inputs)
                    neg_outputs = model(**neg_inputs)

                if num_layers is None:
                    num_layers = len(pos_outputs.hidden_states)

                layer_idx = target_layer if target_layer >= 0 else num_layers + target_layer
                layer_idx = max(0, min(layer_idx, num_layers - 1))

                # Mean pool over sequence
                pos_hidden = pos_outputs.hidden_states[layer_idx].mean(dim=1).float()
                neg_hidden = neg_outputs.hidden_states[layer_idx].mean(dim=1).float()

                diff = (pos_hidden - neg_hidden).squeeze(0)  # [dim]
                differences.append(diff)

            # 2. PCA on differences → concept direction
            diff_matrix = torch.stack(differences)  # [n_pairs, dim]
            mean_diff = diff_matrix.mean(dim=0)

            if len(differences) > 1:
                centered = diff_matrix - mean_diff
                U, S, Vh = torch.linalg.svd(centered, full_matrices=False)
                # SVD returns unit-norm singular vectors — scale by singular value
                # to preserve the actual magnitude of the concept encoding
                concept_direction_raw = S[0] * Vh[0]
                explained_variance = (S[0]**2 / (S**2).sum()).item()
            else:
                concept_direction_raw = differences[0]
                explained_variance = 1.0

            # Normalized direction for projections (dot product comparisons)
            direction_norm = concept_direction_raw.norm()
            concept_direction = concept_direction_raw / direction_norm

            # 3. Project each pair onto the direction
            for i, pair in enumerate(contrast_pairs):
                proj = torch.dot(differences[i], concept_direction).item()
                pair_projections.append({
                    "positive": pair["positive"],
                    "negative": pair["negative"],
                    "projection": proj,
                })

            result = {
                "model_id": model_id,
                "target_layer": layer_idx,
                "num_layers": num_layers,
                "embedding_dim": int(concept_direction.shape[0]),
                "num_pairs": len(contrast_pairs),
                "explained_variance": explained_variance,
                "direction_norm": float(direction_norm),
                "pair_projections": pair_projections,
            }

            # 4. If test text provided: project + manipulated generation
            if test_text:
                test_inputs = tokenizer(test_text, return_tensors="pt").to(model.device)

                with torch.no_grad():
                    test_outputs = model(**test_inputs)

                test_hidden = test_outputs.hidden_states[layer_idx].mean(dim=1).float()
                result["test_text"] = test_text
                result["test_projection"] = torch.dot(
                    test_hidden.squeeze(0), concept_direction
                ).item()

                if alpha != 0:
                    if seed == -1:
                        seed = random.randint(0, 2**32 - 1)

                    # Register hook to add concept direction at target layer
                    # hidden_states has N+1 entries: [0]=embedding, [1..N]=decoder layers
                    # decoder_layers has N entries: [0..N-1]
                    # So hidden_states[layer_idx] corresponds to decoder_layers[layer_idx - 1]
                    # Use RAW direction (not normalized) — magnitude encodes concept strength
                    model_dtype = next(model.parameters()).dtype
                    direction_gpu = concept_direction_raw.to(device=model.device, dtype=model_dtype).unsqueeze(0).unsqueeze(0)
                    decoder_layers = self._get_decoder_layers(model)
                    hook_layer_idx = layer_idx - 1

                    handle = None
                    if decoder_layers and 0 <= hook_layer_idx < len(decoder_layers):
                        def make_hook(dir_vec, strength):
                            def hook_fn(module, input, output):
                                if isinstance(output, tuple):
                                    return (output[0] + strength * dir_vec,) + output[1:]
                                return output + strength * dir_vec
                            return hook_fn

                        handle = decoder_layers[hook_layer_idx].register_forward_hook(
                            make_hook(direction_gpu, alpha)
                        )
                        logger.info(
                            f"[TEXT] RepEng: Hook registered on decoder layer {hook_layer_idx}, "
                            f"alpha={alpha}, raw_direction_norm={direction_norm:.4f}"
                        )
                    else:
                        logger.warning(
                            f"[TEXT] RepEng: Could not register hook — "
                            f"decoder_layers={'found' if decoder_layers else 'None'}, "
                            f"hook_layer_idx={hook_layer_idx}"
                        )

                    try:
                        # Manipulated generation (hook active)
                        torch.manual_seed(seed)
                        gen_manip = model.generate(
                            test_inputs.input_ids,
                            max_new_tokens=max_new_tokens,
                            do_sample=True,
                            temperature=temperature,
                            pad_token_id=tokenizer.eos_token_id,
                        )
                        result["manipulated_text"] = tokenizer.decode(
                            gen_manip[0], skip_special_tokens=True
                        )
                    finally:
                        if handle:
                            handle.remove()

                    # Baseline generation (same seed, no hook)
                    torch.manual_seed(seed)
                    gen_base = model.generate(
                        test_inputs.input_ids,
                        max_new_tokens=max_new_tokens,
                        do_sample=True,
                        temperature=temperature,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                    result["baseline_text"] = tokenizer.decode(
                        gen_base[0], skip_special_tokens=True
                    )
                    result["alpha"] = alpha
                    result["seed"] = seed

                    if result["baseline_text"] == result["manipulated_text"]:
                        logger.warning("[TEXT] RepEng: baseline == manipulated — hook may not be effective")

            return result
        finally:
            self._model_in_use[model_id] -= 1

    async def compare_models(
        self,
        text: str,
        model_id_a: str,
        model_id_b: str,
        max_new_tokens: int = 50,
        temperature: float = 0.7,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Comparative Model Archaeology (Belinkov 2022 + Olsson 2022).

        Compare two models' internal representations on the same input:
        layer-by-layer CKA alignment, attention patterns, generation.

        Args:
            text: Input text for both models
            model_id_a: First model
            model_id_b: Second model
            max_new_tokens: Max tokens for generation comparison
            temperature: Sampling temperature
            seed: Shared seed for deterministic comparison

        Returns:
            Dict with similarity matrix, layer stats, attention, generations
        """
        import torch

        if not await self.load_model(model_id_a):
            return {"error": f"Failed to load model {model_id_a}"}
        if not await self.load_model(model_id_b):
            return {"error": f"Failed to load model {model_id_b}"}

        model_a, tok_a = self._models[model_id_a]
        model_b, tok_b = self._models[model_id_b]
        self._model_in_use[model_id_a] = self._model_in_use.get(model_id_a, 0) + 1
        self._model_in_use[model_id_b] = self._model_in_use.get(model_id_b, 0) + 1

        try:
            inputs_a = tok_a(text, return_tensors="pt").to(model_a.device)
            inputs_b = tok_b(text, return_tensors="pt").to(model_b.device)

            with torch.no_grad():
                outputs_a = model_a(**inputs_a)
                outputs_b = model_b(**inputs_b)

            # Per-layer token-level representations for CKA
            def linear_cka(X, Y):
                """Linear CKA between [n, d1] and [n, d2] representations."""
                X = X - X.mean(dim=0)
                Y = Y - Y.mean(dim=0)
                K = X @ X.T
                L = Y @ Y.T
                num = (K * L).sum()
                denom = (K * K).sum().sqrt() * (L * L).sum().sqrt()
                if denom < 1e-10:
                    return 0.0
                return (num / denom).clamp(0, 1).item()

            # Align sequence lengths for CKA (use shorter)
            seq_a = outputs_a.hidden_states[0].shape[1]
            seq_b = outputs_b.hidden_states[0].shape[1]
            min_seq = min(seq_a, seq_b)

            n_a = len(outputs_a.hidden_states)
            n_b = len(outputs_b.hidden_states)

            # Compute CKA similarity matrix (subsample layers if too many)
            max_layers_vis = 32
            step_a = max(1, n_a // max_layers_vis)
            step_b = max(1, n_b // max_layers_vis)
            layer_indices_a = list(range(0, n_a, step_a))
            layer_indices_b = list(range(0, n_b, step_b))

            similarity_matrix = []
            for i in layer_indices_a:
                row = []
                ha = outputs_a.hidden_states[i][0, :min_seq, :].float().cpu()
                for j in layer_indices_b:
                    hb = outputs_b.hidden_states[j][0, :min_seq, :].float().cpu()
                    row.append(linear_cka(ha, hb))
                similarity_matrix.append(row)

            # Layer statistics
            def layer_stats(outputs):
                stats = []
                for i, h in enumerate(outputs.hidden_states):
                    hs = h[0].float()
                    stats.append({
                        "layer": i,
                        "l2_norm": float(hs.norm()),
                        "mean": float(hs.mean()),
                        "std": float(hs.std()),
                    })
                return stats

            # Attention patterns (last layer, averaged over heads)
            def get_attention_tokens(outputs, tokenizer, input_ids):
                attn = outputs.attentions[-1].float().mean(dim=1)[0]
                tokens = tokenizer.convert_ids_to_tokens(input_ids[0])
                return {
                    "tokens": [str(t) for t in tokens],
                    "attention": attn.cpu().tolist(),
                }

            attn_a = get_attention_tokens(outputs_a, tok_a, inputs_a.input_ids)
            attn_b = get_attention_tokens(outputs_b, tok_b, inputs_b.input_ids)

            # Generation comparison (same seed)
            torch.manual_seed(seed)
            gen_a = model_a.generate(
                inputs_a.input_ids,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                pad_token_id=tok_a.eos_token_id,
            )
            torch.manual_seed(seed)
            gen_b = model_b.generate(
                inputs_b.input_ids,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                pad_token_id=tok_b.eos_token_id,
            )

            return {
                "text": text,
                "model_a": {
                    "model_id": model_id_a,
                    "num_layers": n_a,
                    "dim": int(outputs_a.hidden_states[0].shape[-1]),
                    "layer_stats": layer_stats(outputs_a),
                    "attention": attn_a,
                    "generated_text": tok_a.decode(gen_a[0], skip_special_tokens=True),
                },
                "model_b": {
                    "model_id": model_id_b,
                    "num_layers": n_b,
                    "dim": int(outputs_b.hidden_states[0].shape[-1]),
                    "layer_stats": layer_stats(outputs_b),
                    "attention": attn_b,
                    "generated_text": tok_b.decode(gen_b[0], skip_special_tokens=True),
                },
                "similarity_matrix": similarity_matrix,
                "layer_indices_a": layer_indices_a,
                "layer_indices_b": layer_indices_b,
                "seed": seed,
            }
        finally:
            self._model_in_use[model_id_a] -= 1
            self._model_in_use[model_id_b] -= 1

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
        """
        Bias Archaeology (Zou 2023 RepEng + Bricken 2023 Monosemanticity).

        Systematic bias probing through controlled token manipulation.
        Predefined experiments for gender, sentiment, and domain biases.

        Args:
            prompt: Input prompt
            model_id: Model to use
            bias_type: Preset type (gender, sentiment, domain)
            custom_boost: Optional custom tokens to boost
            custom_suppress: Optional custom tokens to suppress
            num_samples: Number of samples per condition
            max_new_tokens: Max tokens per generation
            temperature: Sampling temperature
            seed: Base seed for reproducibility

        Returns:
            Dict with baseline samples, per-group manipulated samples, statistics
        """
        BIAS_PRESETS = {
            "gender": {
                "description_key": "gender",
                "mode": "suppress",
                "groups": [
                    {"name": "masculine", "tokens": [
                        "he", "him", "his", "man", "boy", "male",
                        "Mr", "father", "son", "brother", "He", "Him", "His"
                    ]},
                    {"name": "feminine", "tokens": [
                        "she", "her", "hers", "woman", "girl", "female",
                        "Ms", "Mrs", "mother", "daughter", "sister", "She", "Her"
                    ]},
                ],
            },
            "sentiment": {
                "description_key": "sentiment",
                "mode": "boost",
                "groups": [
                    {"name": "positive", "tokens": [
                        "good", "great", "happy", "love", "beautiful",
                        "wonderful", "excellent", "joy", "hope", "kind"
                    ]},
                    {"name": "negative", "tokens": [
                        "bad", "terrible", "sad", "hate", "ugly",
                        "horrible", "awful", "fear", "doom", "cruel"
                    ]},
                ],
            },
            "domain": {
                "description_key": "domain",
                "mode": "boost",
                "groups": [
                    {"name": "scientific", "tokens": [
                        "hypothesis", "experiment", "data", "analysis",
                        "empirical", "theory", "evidence", "methodology"
                    ]},
                    {"name": "poetic", "tokens": [
                        "whisper", "dream", "shadow", "echo",
                        "gentle", "eternal", "shimmer", "weave"
                    ]},
                ],
            },
        }

        preset = BIAS_PRESETS.get(bias_type, BIAS_PRESETS["gender"])

        # Custom tokens override
        if custom_boost or custom_suppress:
            groups = []
            if custom_boost:
                groups.append({"name": "custom_boost", "tokens": custom_boost})
            if custom_suppress:
                groups.append({"name": "custom_suppress", "tokens": custom_suppress})
            preset = {
                "description_key": "custom",
                "mode": "mixed",
                "groups": groups,
            }

        # Generate baseline samples
        baseline_results = []
        for i in range(num_samples):
            result = await self.generate_with_token_surgery(
                prompt=prompt,
                model_id=model_id,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                seed=seed + i,
            )
            if "error" in result:
                return result
            baseline_results.append({
                "seed": seed + i,
                "text": result["new_text"],
            })

        # Generate manipulated samples per group
        group_results = []
        for group in preset["groups"]:
            samples = []
            for i in range(num_samples):
                mode = preset["mode"]
                is_suppress = (
                    mode == "suppress" or
                    "suppress" in group["name"]
                )

                if is_suppress:
                    result = await self.generate_with_token_surgery(
                        prompt=prompt,
                        model_id=model_id,
                        suppress_tokens=group["tokens"],
                        max_new_tokens=max_new_tokens,
                        temperature=temperature,
                        seed=seed + i,
                    )
                else:
                    result = await self.generate_with_token_surgery(
                        prompt=prompt,
                        model_id=model_id,
                        boost_tokens=group["tokens"],
                        boost_factor=2.5,
                        max_new_tokens=max_new_tokens,
                        temperature=temperature,
                        seed=seed + i,
                    )

                if "error" in result:
                    return result
                samples.append({
                    "seed": seed + i,
                    "text": result["new_text"],
                })

            group_results.append({
                "group_name": group["name"],
                "tokens": group["tokens"],
                "mode": "suppress" if (preset["mode"] == "suppress" or "suppress" in group["name"]) else "boost",
                "samples": samples,
            })

        return {
            "model_id": model_id,
            "prompt": prompt,
            "bias_type": bias_type,
            "description_key": preset["description_key"],
            "baseline": baseline_results,
            "groups": group_results,
            "num_samples": num_samples,
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            "base_seed": seed,
        }

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
        import torch

        if not await self.load_model(model_id):
            return {"error": f"Failed to load model {model_id}"}

        model, tokenizer = self._models[model_id]
        self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1

        try:
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            results = []

            for i in range(num_variations):
                seed = base_seed + i
                torch.manual_seed(seed)

                outputs = model.generate(
                    inputs.input_ids,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=temperature,
                    top_p=0.9,
                    pad_token_id=tokenizer.eos_token_id,
                )

                text = tokenizer.decode(outputs[0], skip_special_tokens=True)

                results.append({
                    "variation": i,
                    "seed": seed,
                    "temperature": temperature,
                    "text": text,
                })

            return {
                "model_id": model_id,
                "prompt": prompt,
                "num_variations": num_variations,
                "base_seed": base_seed,
                "variations": results,
            }
        finally:
            self._model_in_use[model_id] -= 1


# =============================================================================
# Singleton
# =============================================================================

_backend: Optional[TextBackend] = None


def get_text_backend() -> TextBackend:
    """Get TextBackend singleton."""
    global _backend
    if _backend is None:
        _backend = TextBackend()
    return _backend


def reset_text_backend():
    """Reset singleton (for testing)."""
    global _backend
    _backend = None
