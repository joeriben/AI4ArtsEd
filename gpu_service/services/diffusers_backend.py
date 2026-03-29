"""
Diffusers Backend - Direct HuggingFace Diffusers inference

Session 149: Direct model inference backend.
Provides full control over the inference pipeline and optional TensorRT acceleration.

Features:
- StableDiffusion3Pipeline for SD3.5 Large/Medium
- FluxPipeline for Flux models
- TensorRT acceleration (2.3x speedup when available)
- Step-by-step callback for live preview streaming
- VRAM management with model loading/unloading

Usage:
    backend = get_diffusers_backend()
    if await backend.is_available():
        image_bytes = await backend.generate_image(
            prompt="A red apple",
            model_id="stabilityai/stable-diffusion-3.5-large",
            seed=42,
            callback=step_callback  # For live preview
        )
"""

import gc
import logging
import threading
import time
import warnings
from typing import Optional, Dict, Any, Callable, AsyncGenerator
import asyncio

# Suppress noisy HuggingFace tokenizer deprecation warnings
warnings.filterwarnings("ignore", message=".*add_prefix_space.*")
warnings.filterwarnings("ignore", message=".*slow tokenizers.*")
warnings.filterwarnings("ignore", message=".*Token indices sequence length is longer than.*")

logger = logging.getLogger(__name__)

# Module-level generation progress (thread-safe via GIL for simple dict ops)
_generation_progress = {"step": 0, "total_steps": 0, "active": False}


def get_generation_progress() -> dict:
    """Return current generation progress for polling endpoint."""
    return dict(_generation_progress)


class DiffusersImageGenerator:
    """
    Direct image generation using HuggingFace Diffusers

    Supports:
    - SD3.5 Large/Medium (StableDiffusion3Pipeline)
    - Flux (FluxPipeline)
    - Optional TensorRT acceleration
    - Live preview via step callbacks
    """

    def __init__(self):
        """Initialize Diffusers backend"""
        from config import (
            DIFFUSERS_CACHE_DIR,
            DIFFUSERS_USE_TENSORRT,
            DIFFUSERS_TORCH_DTYPE,
            DIFFUSERS_DEVICE,
            DIFFUSERS_ENABLE_ATTENTION_SLICING,
            DIFFUSERS_ENABLE_VAE_TILING
        )

        self.cache_dir = DIFFUSERS_CACHE_DIR
        self.use_tensorrt = DIFFUSERS_USE_TENSORRT
        self.torch_dtype_str = DIFFUSERS_TORCH_DTYPE
        self.device = DIFFUSERS_DEVICE
        self.enable_attention_slicing = DIFFUSERS_ENABLE_ATTENTION_SLICING
        self.enable_vae_tiling = DIFFUSERS_ENABLE_VAE_TILING

        # Multi-model GPU cache with LRU eviction
        self._pipelines: Dict[str, Any] = {}
        self._current_model: Optional[str] = None
        self._model_last_used: Dict[str, float] = {}  # timestamp for LRU
        self._model_vram_mb: Dict[str, float] = {}    # measured per-model VRAM
        self._model_in_use: Dict[str, int] = {}       # refcount (eviction guard)
        self._load_lock = threading.Lock()             # serialize load/evict
        self._inference_lock = threading.Lock()          # serialize inference (T5 tokenizer not thread-safe)

        # Register with VRAM coordinator for cross-backend eviction
        self._register_with_coordinator()

        logger.info(f"[DIFFUSERS] Initialized: cache={self.cache_dir}, tensorrt={self.use_tensorrt}, device={self.device}")

    def _register_with_coordinator(self):
        """Register with VRAM coordinator for cross-backend eviction."""
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[DIFFUSERS] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[DIFFUSERS] Failed to register with VRAM coordinator: {e}")

    def _locked_generate(self, fn):
        """Run a generation function under the inference lock.

        HuggingFace Rust tokenizers raise 'Already borrowed' when called
        concurrently from multiple threads. Since GPU inference is serial
        anyway, we serialize at the tokenize+generate boundary.
        """
        with self._inference_lock:
            return fn()

    # =========================================================================
    # VRAMBackend Protocol Implementation
    # =========================================================================

    def get_backend_id(self) -> str:
        """Unique identifier for this backend."""
        return "diffusers"

    def get_registered_models(self) -> list:
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
            for mid in self._pipelines
        ]

    def evict_model(self, model_id: str) -> bool:
        """Evict a specific model (called by coordinator)."""
        return self._unload_model_sync(model_id)

    def _unload_model_sync(self, model_id: str) -> bool:
        """Synchronously unload a model from memory."""
        import torch

        if model_id not in self._pipelines:
            return False

        try:
            del self._pipelines[model_id]
            self._model_last_used.pop(model_id, None)
            self._model_vram_mb.pop(model_id, None)
            self._model_in_use.pop(model_id, None)

            if self._current_model == model_id:
                self._current_model = None

            if torch.cuda.is_available():
                gc.collect()
                torch.cuda.empty_cache()

            logger.info(f"[DIFFUSERS] Unloaded model: {model_id}")
            return True
        except Exception as e:
            logger.error(f"[DIFFUSERS] Error unloading {model_id}: {e}")
            return False

    def _get_torch_dtype(self):
        """Get torch dtype from config string"""
        import torch
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        return dtype_map.get(self.torch_dtype_str, torch.float16)

    def _get_vram_estimate_key(self, model_id: str, pipeline_class: str) -> str:
        """Map (model_id, pipeline_class, quantization) to a MODEL_PEAK_VRAM_MB key."""
        from config import DIFFUSERS_FLUX2_QUANTIZE, DIFFUSERS_WAN22_QUANTIZE

        if pipeline_class == "Flux2Pipeline":
            return f"flux2_{DIFFUSERS_FLUX2_QUANTIZE.lower()}"
        elif pipeline_class in ("WanPipeline", "WanImageToVideoPipeline"):
            quant = DIFFUSERS_WAN22_QUANTIZE.lower()
            kind = "i2v" if pipeline_class == "WanImageToVideoPipeline" else "t2v"
            moe = "_moe" if "A14B" in model_id else ""
            return f"wan22_{kind}{moe}_{quant}"
        elif "stable-diffusion-3.5" in model_id:
            # Normalize dtype name to match MODEL_PEAK_VRAM_MB keys (fp16, bf16)
            _dtype_short = {"float16": "fp16", "bfloat16": "bf16", "float32": "fp32"}
            short = _dtype_short.get(self.torch_dtype_str, self.torch_dtype_str)
            return f"sd35_large_{short}"
        else:
            return f"unknown_{pipeline_class}"

    def _get_peak_vram_mb(self, model_id: str, pipeline_class: str) -> float:
        """Get estimated peak VRAM (MB) from config table. Falls back to 20GB."""
        from config import MODEL_PEAK_VRAM_MB

        key = self._get_vram_estimate_key(model_id, pipeline_class)
        estimate = MODEL_PEAK_VRAM_MB.get(key)
        if estimate is None:
            logger.warning(f"[DIFFUSERS] No VRAM estimate for key '{key}', using 20GB default")
            return 20_000
        return float(estimate)

    def _resolve_pipeline_class(self, pipeline_class: str):
        """Resolve pipeline class string to actual class."""
        if pipeline_class == "StableDiffusion3Pipeline":
            from diffusers import StableDiffusion3Pipeline
            return StableDiffusion3Pipeline
        elif pipeline_class == "FluxPipeline":
            from diffusers import FluxPipeline
            return FluxPipeline
        elif pipeline_class == "Flux2Pipeline":
            from diffusers import Flux2Pipeline
            return Flux2Pipeline
        elif pipeline_class == "WanPipeline":
            from diffusers import WanPipeline
            return WanPipeline
        elif pipeline_class == "WanImageToVideoPipeline":
            from diffusers import WanImageToVideoPipeline
            return WanImageToVideoPipeline
        else:
            raise ValueError(f"Unknown pipeline class: {pipeline_class}")

    def _load_flux2_pipeline(self, model_id: str, kwargs: dict):
        """Load Flux2 pipeline component-by-component with explicit bf16.

        Flux2Pipeline.from_pretrained ignores torch_dtype/dtype kwargs,
        loading everything in float32 (~106GB RAM). Loading components
        individually with torch_dtype=bfloat16 uses ~1.2GB RAM instead.

        FP8 mode (DIFFUSERS_FLUX2_QUANTIZE=fp8): quantizes transformer to
        Float8WeightOnlyConfig via TorchAoConfig (~16GB) and text encoder to
        Int8WeightOnlyConfig v2 (~12GB). Peak VRAM ~24GB with CPU offload.
        """
        import torch
        from diffusers import (
            Flux2Pipeline, Flux2Transformer2DModel,
            AutoencoderKLFlux2, FlowMatchEulerDiscreteScheduler,
        )
        from transformers import AutoModelForImageTextToText, PixtralProcessor
        from config import DIFFUSERS_FLUX2_QUANTIZE

        dtype = torch.bfloat16
        cache_kwargs = {"cache_dir": str(self.cache_dir)} if self.cache_dir else {}
        quantize = DIFFUSERS_FLUX2_QUANTIZE.lower()

        if quantize == "fp8":
            from diffusers import TorchAoConfig
            from transformers import TorchAoConfig as TransformersAoConfig
            from torchao.quantization import Float8WeightOnlyConfig, Int8WeightOnlyConfig
            diff_quant = TorchAoConfig(Float8WeightOnlyConfig())
            tf_quant = TransformersAoConfig(Int8WeightOnlyConfig(version=2))
            logger.info(f"[DIFFUSERS] Flux2: loading transformer FP8 + text encoder INT8...")
            transformer = Flux2Transformer2DModel.from_pretrained(
                model_id, subfolder="transformer",
                quantization_config=diff_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
            text_encoder = AutoModelForImageTextToText.from_pretrained(
                model_id, subfolder="text_encoder",
                quantization_config=tf_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
        else:
            logger.info(f"[DIFFUSERS] Flux2: loading components in bf16...")
            transformer = Flux2Transformer2DModel.from_pretrained(
                model_id, subfolder="transformer",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )
            text_encoder = AutoModelForImageTextToText.from_pretrained(
                model_id, subfolder="text_encoder",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )
        vae = AutoencoderKLFlux2.from_pretrained(
            model_id, subfolder="vae",
            torch_dtype=dtype, **cache_kwargs
        )
        tokenizer = PixtralProcessor.from_pretrained(
            model_id, subfolder="tokenizer", **cache_kwargs
        )
        scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
            model_id, subfolder="scheduler", **cache_kwargs
        )

        pipe = Flux2Pipeline(
            transformer=transformer,
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            vae=vae,
            scheduler=scheduler,
        )
        pipe.enable_model_cpu_offload()

        logger.info(f"[DIFFUSERS] Flux2: pipeline loaded ({quantize}) with cpu_offload")
        return pipe

    def _load_wan_pipeline(self, model_id: str, kwargs: dict, pipeline_class_str: str = "WanPipeline"):
        """Load Wan 2.2 pipeline component-by-component with quantization support.

        Handles both T2V (WanPipeline) and I2V (WanImageToVideoPipeline).
        MoE models (A14B) have dual transformers (transformer + transformer_2).

        FP8 mode (DIFFUSERS_WAN22_QUANTIZE=fp8): quantizes transformers to
        Float8WeightOnlyConfig via TorchAoConfig (~14GB total) and text encoder to
        Int8WeightOnlyConfig v2. Peak VRAM ~14GB with CPU offload.
        """
        import torch
        from diffusers import AutoencoderKLWan
        from config import DIFFUSERS_WAN22_QUANTIZE

        PipelineClass = self._resolve_pipeline_class(pipeline_class_str)
        dtype = torch.bfloat16
        cache_kwargs = {"cache_dir": str(self.cache_dir)} if self.cache_dir else {}
        quantize = DIFFUSERS_WAN22_QUANTIZE.lower()

        # Check if model has dual transformers (MoE A14B models)
        import json
        from pathlib import Path
        from huggingface_hub import cached_assets_path
        has_dual_transformer = False
        model_index = {}
        try:
            # Try loading model_index.json to detect dual transformer
            from huggingface_hub import hf_hub_download
            model_index_path = hf_hub_download(model_id, "model_index.json", **cache_kwargs)
            with open(model_index_path) as f:
                model_index = json.load(f)
            has_dual_transformer = "transformer_2" in model_index
        except Exception as e:
            logger.warning(f"[DIFFUSERS] Could not check model_index.json for dual transformer: {e}")
            # Heuristic: A14B models have dual transformers
            has_dual_transformer = "A14B" in model_id

        if quantize == "fp8":
            from diffusers import TorchAoConfig, WanTransformer3DModel
            from transformers import TorchAoConfig as TransformersAoConfig, UMT5EncoderModel
            from torchao.quantization import Float8WeightOnlyConfig, Int8WeightOnlyConfig
            diff_quant = TorchAoConfig(Float8WeightOnlyConfig())
            tf_quant = TransformersAoConfig(Int8WeightOnlyConfig(version=2))

            logger.info(f"[DIFFUSERS] Wan: loading transformer(s) FP8 + text encoder INT8...")
            transformer = WanTransformer3DModel.from_pretrained(
                model_id, subfolder="transformer",
                quantization_config=diff_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
            transformer_2 = None
            if has_dual_transformer:
                transformer_2 = WanTransformer3DModel.from_pretrained(
                    model_id, subfolder="transformer_2",
                    quantization_config=diff_quant,
                    low_cpu_mem_usage=True, **cache_kwargs
                )
            text_encoder = UMT5EncoderModel.from_pretrained(
                model_id, subfolder="text_encoder",
                quantization_config=tf_quant,
                low_cpu_mem_usage=True, **cache_kwargs
            )
        else:
            from diffusers import WanTransformer3DModel
            from transformers import UMT5EncoderModel

            logger.info(f"[DIFFUSERS] Wan: loading components in bf16...")
            transformer = WanTransformer3DModel.from_pretrained(
                model_id, subfolder="transformer",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )
            transformer_2 = None
            if has_dual_transformer:
                transformer_2 = WanTransformer3DModel.from_pretrained(
                    model_id, subfolder="transformer_2",
                    torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
                )
            text_encoder = UMT5EncoderModel.from_pretrained(
                model_id, subfolder="text_encoder",
                torch_dtype=dtype, low_cpu_mem_usage=True, **cache_kwargs
            )

        # VAE MUST be float32
        vae = AutoencoderKLWan.from_pretrained(
            model_id, subfolder="vae",
            torch_dtype=torch.float32, **cache_kwargs
        )

        # Tokenizer + Scheduler
        from transformers import AutoTokenizer
        from diffusers import UniPCMultistepScheduler
        tokenizer = AutoTokenizer.from_pretrained(model_id, subfolder="tokenizer", **cache_kwargs)
        scheduler = UniPCMultistepScheduler.from_pretrained(model_id, subfolder="scheduler", **cache_kwargs)

        # Assemble pipeline
        pipe_kwargs = {
            "transformer": transformer,
            "vae": vae,
            "text_encoder": text_encoder,
            "tokenizer": tokenizer,
            "scheduler": scheduler,
        }
        if transformer_2 is not None:
            pipe_kwargs["transformer_2"] = transformer_2
            pipe_kwargs["boundary_ratio"] = model_index.get("boundary_ratio", 0.9)

        pipe = PipelineClass(**pipe_kwargs)
        pipe.enable_model_cpu_offload()

        dual_info = " (dual MoE)" if has_dual_transformer else ""
        logger.info(f"[DIFFUSERS] Wan: pipeline loaded ({quantize}{dual_info}) with cpu_offload")
        return pipe

    def _ensure_vram_available(self, required_mb: float = 0) -> None:
        """Request VRAM via coordinator, triggering cross-backend eviction if needed.

        The coordinator handles eviction across all backends (diffusers, text, heartmula).

        Args:
            required_mb: Minimum free VRAM needed. If 0, uses DIFFUSERS_VRAM_RESERVE_MB.
                         For cold loads (unknown model size), pass float('inf') to request
                         maximum available space.
        """
        from config import DIFFUSERS_VRAM_RESERVE_MB

        target_mb = required_mb if required_mb > 0 else DIFFUSERS_VRAM_RESERVE_MB

        # Use coordinator for cross-backend eviction
        try:
            from services.vram_coordinator import get_vram_coordinator, EvictionPriority
            coordinator = get_vram_coordinator()
            success = coordinator.request_vram("diffusers", target_mb, EvictionPriority.NORMAL)
            if not success:
                target_str = "max available" if target_mb == float('inf') else f"{target_mb:.0f}MB"
                logger.warning(f"[DIFFUSERS] VRAM eviction incomplete (requested {target_str})")
        except Exception as e:
            logger.warning(f"[DIFFUSERS] VRAM coordinator request failed: {e}")
            # Fallback to local-only eviction
            self._ensure_vram_available_local(target_mb)

    def _ensure_vram_available_local(self, target_mb: float) -> None:
        """Fallback: evict only own models (no cross-backend)."""
        import torch

        while True:
            if not torch.cuda.is_available():
                break

            free_mb = (torch.cuda.get_device_properties(0).total_memory
                       - torch.cuda.memory_allocated(0)) / (1024 * 1024)
            if free_mb >= target_mb:
                break

            candidates = [
                (mid, self._model_last_used.get(mid, 0))
                for mid in self._pipelines
                if self._model_in_use.get(mid, 0) <= 0
            ]

            if not candidates:
                if target_mb != float('inf'):
                    logger.warning(
                        f"[DIFFUSERS] Cannot free VRAM: {free_mb:.0f}MB free, "
                        f"need {target_mb:.0f}MB, no evictable models"
                    )
                break

            evict_id = min(candidates, key=lambda x: x[1])[0]
            self._unload_model_sync(evict_id)

    def _load_model_sync(self, model_id: str, pipeline_class: str = "StableDiffusion3Pipeline") -> bool:
        """
        Synchronous model loading with GPU cache + LRU eviction.
        Thread-safe via _load_lock.

        Returns True if model is ready on GPU.
        """
        with self._load_lock:
            try:
                import torch

                # Case 1: Already on GPU → reuse
                if model_id in self._pipelines:
                    self._model_last_used[model_id] = time.time()
                    self._current_model = model_id
                    return True

                # Case 2: Not loaded → evict if needed, load from disk
                peak_vram = self._get_peak_vram_mb(model_id, pipeline_class)
                self._ensure_vram_available(required_mb=peak_vram)

                PipelineClass = self._resolve_pipeline_class(pipeline_class)

                logger.info(f"[DIFFUSERS] Loading model from disk: {model_id}")

                vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

                # All diffusers pipelines use torch_dtype in from_pretrained()
                dtype_key = "torch_dtype"
                kwargs = {
                    dtype_key: self._get_torch_dtype(),
                    "use_safetensors": True,
                    "low_cpu_mem_usage": True,
                }
                if self.cache_dir:
                    kwargs["cache_dir"] = str(self.cache_dir)

                # Wan pipelines: component-level loading with quantization support
                if pipeline_class in ("WanPipeline", "WanImageToVideoPipeline"):
                    pipe = self._load_wan_pipeline(model_id, kwargs, pipeline_class)
                # Flux2: from_pretrained ignores torch_dtype → loads float32 (~106GB RAM).
                # Load components individually with explicit bf16 to avoid float32 intermediate.
                elif pipeline_class == "Flux2Pipeline":
                    pipe = self._load_flux2_pipeline(model_id, kwargs)
                else:
                    pipe = PipelineClass.from_pretrained(model_id, **kwargs)
                    pipe = pipe.to(self.device)

                if self.enable_attention_slicing:
                    pipe.enable_attention_slicing()
                if self.enable_vae_tiling:
                    pipe.enable_vae_tiling()

                self._pipelines[model_id] = pipe
                self._current_model = model_id
                self._model_last_used[model_id] = time.time()

                # Use static peak estimate for coordinator (measurement is broken
                # for CPU-offloaded models — they report ~0 since weights are on CPU)
                self._model_vram_mb[model_id] = peak_vram

                # Log measured vs estimated for validation
                vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
                measured_mb = (vram_after - vram_before) / (1024 * 1024)
                logger.info(
                    f"[DIFFUSERS] Model loaded: {model_id} "
                    f"(estimated: {peak_vram:.0f}MB, measured: {measured_mb:.0f}MB)"
                )
                return True

            except Exception as e:
                logger.error(f"[DIFFUSERS] Failed to load model {model_id}: {e}")
                import traceback
                traceback.print_exc()
                return False

    async def is_available(self) -> bool:
        """
        Check if Diffusers backend is available

        Returns:
            True if torch and diffusers are installed and GPU is available
        """
        try:
            import torch
            from diffusers import StableDiffusion3Pipeline

            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("[DIFFUSERS] CUDA requested but not available")
                return False

            return True

        except ImportError as e:
            logger.error(f"[DIFFUSERS] Dependencies not installed: {e}")
            return False

    async def get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU memory information"""
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                total = props.total_memory / 1024**3

                return {
                    "gpu_name": props.name,
                    "total_vram_gb": round(total, 2),
                    "allocated_gb": round(allocated, 2),
                    "reserved_gb": round(reserved, 2),
                    "free_gb": round(total - reserved, 2)
                }
            return {"available": False}
        except Exception as e:
            logger.error(f"[DIFFUSERS] Error getting GPU info: {e}")
            return {"error": str(e)}

    async def load_model(
        self,
        model_id: str,
        pipeline_class: str = "StableDiffusion3Pipeline",
    ) -> bool:
        """
        Load a model into GPU memory with LRU cache.

        - Already on GPU: updates last_used timestamp (instant)
        - Not loaded: evicts LRU models, loads from disk (~10s)

        Args:
            model_id: HuggingFace model ID or local path
            pipeline_class: Pipeline class to use

        Returns:
            True if loaded successfully
        """
        return await asyncio.to_thread(self._load_model_sync, model_id, pipeline_class)

    async def unload_model(self, model_id: Optional[str] = None) -> bool:
        """
        Fully unload a model from memory (GPU + CPU RAM).

        Args:
            model_id: Model to unload (default: current model)

        Returns:
            True if unloaded successfully
        """
        model_id = model_id or self._current_model

        if model_id not in self._pipelines:
            logger.warning(f"[DIFFUSERS] Model not loaded: {model_id}")
            return False

        try:
            import torch

            del self._pipelines[model_id]
            self._model_last_used.pop(model_id, None)
            self._model_vram_mb.pop(model_id, None)
            self._model_in_use.pop(model_id, None)

            if model_id == self._current_model:
                self._current_model = None

            # Force CUDA memory cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            logger.info(f"[DIFFUSERS] Unloaded model: {model_id}")
            return True

        except Exception as e:
            logger.error(f"[DIFFUSERS] Error unloading model: {e}")
            return False

    def _apply_loras(self, pipe, loras: list):
        """Load LoRA weights onto pipeline for current generation."""
        from config import LORA_DIR

        adapter_names = []
        adapter_weights = []
        for i, lora in enumerate(loras):
            lora_path = LORA_DIR / lora['name']
            if not lora_path.exists():
                logger.error(f"[DIFFUSERS-LORA] LoRA file not found: {lora_path}")
                continue
            adapter_name = f"lora_{i}"
            pipe.load_lora_weights(
                str(LORA_DIR), weight_name=lora['name'], adapter_name=adapter_name,
                prefix=None,  # Auto-detect Kohya key format (lora_unet_*, lora_te1_*)
            )
            adapter_names.append(adapter_name)
            adapter_weights.append(lora.get('strength', 1.0))
            logger.info(f"[DIFFUSERS-LORA] Loaded: {lora['name']} (strength={lora.get('strength', 1.0)})")

        if adapter_names:
            try:
                pipe.set_adapters(adapter_names, adapter_weights)
                logger.info(f"[DIFFUSERS-LORA] Active adapters: {adapter_names}")
            except ValueError as e:
                # Kohya SD3 LoRAs may fuse directly without PEFT adapter tracking
                logger.warning(f"[DIFFUSERS-LORA] set_adapters skipped (weights applied directly): {e}")

    def _remove_loras(self, pipe):
        """Unload all LoRA weights from pipeline."""
        try:
            pipe.unload_lora_weights()
            logger.info("[DIFFUSERS-LORA] Unloaded LoRA weights")
        except Exception as e:
            logger.warning(f"[DIFFUSERS-LORA] Error unloading LoRAs: {e}")

    async def generate_image(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
        pipeline_class: str = "StableDiffusion3Pipeline",
        loras: Optional[list] = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate an image using Diffusers

        Args:
            prompt: Positive prompt
            model_id: Model to use
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            steps: Number of steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            callback: Step callback for progress (step, total_steps, latents)
            pipeline_class: Pipeline class string (e.g. "Flux2Pipeline")
            loras: Optional list of LoRA dicts [{name, strength}]
            **kwargs: Additional pipeline arguments

        Returns:
            PNG image bytes, or None on failure
        """
        try:
            import torch
            import io

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id, pipeline_class):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                # CPU offload pipelines (Flux2) need generator on CPU
                gen_device = "cpu" if pipeline_class == "Flux2Pipeline" else self.device
                generator = torch.Generator(device=gen_device).manual_seed(seed)

                logger.info(f"[DIFFUSERS] Generating: steps={steps}, size={width}x{height}, seed={seed}")

                # Always wire progress callback for polling endpoint
                def step_callback(pipe_inst, step, timestep, callback_kwargs):
                    _generation_progress["step"] = step + 1  # 0-indexed → 1-indexed
                    _generation_progress["total_steps"] = steps
                    if callback:
                        try:
                            callback(step, steps, callback_kwargs.get("latents"))
                        except Exception as e:
                            logger.warning(f"[DIFFUSERS] Callback error: {e}")
                    return callback_kwargs

                # Run inference in thread to avoid blocking event loop
                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    if loras:
                        self._apply_loras(pipe, loras)
                    try:
                        # Build generation kwargs
                        gen_kwargs = {
                            "prompt": prompt,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                        }

                        # Flux/Flux2 don't support negative_prompt
                        if pipeline_class not in ("FluxPipeline", "Flux2Pipeline"):
                            gen_kwargs["negative_prompt"] = negative_prompt if negative_prompt else None

                        # SD3.5 triple encoder: CLIP-L (77t), CLIP-G (77t), T5-XXL (512t)
                        if hasattr(pipe, 'tokenizer_3'):
                            gen_kwargs["max_sequence_length"] = 512
                            # Use explicit per-encoder prompts if provided via kwargs
                            if kwargs.get('prompt_2') or kwargs.get('prompt_3'):
                                if kwargs.get('prompt_2'):
                                    gen_kwargs["prompt_2"] = kwargs['prompt_2']
                                if kwargs.get('prompt_3'):
                                    gen_kwargs["prompt_3"] = kwargs['prompt_3']
                                logger.info(
                                    f"[DIFFUSERS] Triple-prompt: CLIP-L={len(prompt.split()):.0f}w, "
                                    f"CLIP-G={len((kwargs.get('prompt_2') or prompt).split()):.0f}w, "
                                    f"T5={len((kwargs.get('prompt_3') or prompt).split()):.0f}w"
                                )
                            else:
                                # Auto-split: truncate for CLIP, full prompt for T5
                                clip_tokenizer = pipe.tokenizer
                                clip_tokens = clip_tokenizer(
                                    prompt, truncation=False, add_special_tokens=False
                                )["input_ids"]
                                if len(clip_tokens) > 75:  # 77 minus SOT/EOT
                                    gen_kwargs["prompt_3"] = prompt
                                    gen_kwargs["prompt"] = clip_tokenizer.decode(
                                        clip_tokens[:75], skip_special_tokens=True
                                    )
                                    logger.info(
                                        f"[DIFFUSERS] Prompt split: CLIP uses 75 of "
                                        f"{len(clip_tokens)} tokens, T5-XXL uses full prompt"
                                    )

                        # Flux2 visual conditioning: pass reference image as context tokens
                        if pipeline_class == "Flux2Pipeline" and kwargs.get('image_bytes'):
                            from PIL import Image
                            pil_image = Image.open(io.BytesIO(kwargs['image_bytes'])).convert("RGB")
                            gen_kwargs["image"] = pil_image
                            logger.info(f"[DIFFUSERS] Flux2 visual conditioning: {pil_image.size}")

                        # SD3.5 img2img: create lightweight Img2Img pipeline via from_pipe()
                        if pipeline_class == "StableDiffusion3Pipeline" and kwargs.get('image_bytes'):
                            from PIL import Image
                            from diffusers import StableDiffusion3Img2ImgPipeline
                            pil_image = Image.open(io.BytesIO(kwargs['image_bytes'])).convert("RGB")
                            pil_image = pil_image.resize((width, height), Image.LANCZOS)
                            i2i_pipe = StableDiffusion3Img2ImgPipeline.from_pipe(pipe)
                            # VAE tiling: img2img encodes the input image via VAE,
                            # which at 1024x1024 with 16-ch latents causes massive
                            # VRAM spikes without tiling (65GB+ vs ~28GB with tiling)
                            i2i_pipe.vae.enable_tiling()
                            gen_kwargs["image"] = pil_image
                            gen_kwargs["strength"] = float(kwargs.get('strength', 0.65))
                            gen_kwargs.pop("width", None)
                            gen_kwargs.pop("height", None)
                            logger.info(
                                f"[DIFFUSERS] SD3.5 img2img: {pil_image.size}, "
                                f"strength={gen_kwargs['strength']}"
                            )
                            gen_kwargs["callback_on_step_end"] = step_callback
                            gen_kwargs["callback_on_step_end_tensor_inputs"] = ["latents"]
                            result = i2i_pipe(**gen_kwargs)
                            return result.images[0]

                        gen_kwargs["callback_on_step_end"] = step_callback
                        gen_kwargs["callback_on_step_end_tensor_inputs"] = ["latents"]

                        result = pipe(**gen_kwargs)
                        return result.images[0]
                    finally:
                        if loras:
                            self._remove_loras(pipe)
                        _generation_progress["active"] = False

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert to PNG bytes
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

                logger.info(f"[DIFFUSERS] Generated image: {len(image_bytes)} bytes")
                return image_bytes

            finally:
                self._model_in_use[model_id] -= 1

        except Exception as e:
            logger.error(f"[DIFFUSERS] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_video(
        self,
        prompt: str,
        model_id: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
        negative_prompt: str = "",
        width: int = 1280,
        height: int = 720,
        num_frames: int = 81,
        steps: int = 30,
        cfg_scale: float = 5.0,
        fps: int = 16,
        seed: int = -1,
        pipeline_class: str = "WanPipeline",
        guidance_scale_2: float = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate a video using Diffusers (WanPipeline).

        Args:
            prompt: Positive prompt
            model_id: Wan model to use
            negative_prompt: Negative prompt
            width: Video width
            height: Video height
            num_frames: Number of frames to generate
            steps: Number of inference steps
            cfg_scale: Guidance scale
            fps: Frames per second for output MP4
            seed: Random seed (-1 for random)
            pipeline_class: Pipeline class string
            guidance_scale_2: Second guidance scale for MoE models (A14B)

        Returns:
            MP4 video bytes, or None on failure
        """
        try:
            import torch

            if not await self.load_model(model_id, pipeline_class):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(
                    f"[DIFFUSERS] Generating video: steps={steps}, "
                    f"size={width}x{height}, frames={num_frames}, seed={seed}"
                )

                def video_step_callback(pipe_inst, step, timestep, callback_kwargs):
                    _generation_progress["step"] = step + 1
                    _generation_progress["total_steps"] = steps
                    return callback_kwargs

                _guidance_scale_2 = guidance_scale_2

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    try:
                        gen_kwargs = {
                            "prompt": prompt,
                            "negative_prompt": negative_prompt if negative_prompt else None,
                            "width": width,
                            "height": height,
                            "num_frames": num_frames,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "callback_on_step_end": video_step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }
                        # MoE models use a second guidance scale
                        if _guidance_scale_2 is not None:
                            gen_kwargs["guidance_scale_2"] = _guidance_scale_2
                        result = pipe(**gen_kwargs)
                        if not hasattr(result, 'frames') or result.frames is None or len(result.frames) == 0:
                            raise ValueError("Pipeline returned no video frames")
                        return result.frames[0]
                    finally:
                        _generation_progress["active"] = False

                frames = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert frames to MP4 bytes via temp file
                # (export_to_video only accepts file paths, not BytesIO)
                import tempfile
                import os
                from diffusers.utils import export_to_video
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    export_to_video(frames, tmp_path, fps=fps)
                    with open(tmp_path, 'rb') as f:
                        video_bytes = f.read()
                finally:
                    os.unlink(tmp_path)

                logger.info(
                    f"[DIFFUSERS] Generated video: {len(video_bytes)} bytes, "
                    f"{num_frames} frames @ {fps}fps, seed={seed}"
                )
                return video_bytes

            finally:
                self._model_in_use[model_id] -= 1

        except Exception as e:
            logger.error(f"[DIFFUSERS] Video generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_video_from_image(
        self,
        image_bytes: bytes,
        prompt: str = "",
        model_id: str = "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
        negative_prompt: str = "",
        width: int = 1280,
        height: int = 720,
        num_frames: int = 81,
        steps: int = 40,
        cfg_scale: float = 4.0,
        fps: int = 16,
        seed: int = -1,
        guidance_scale_2: float = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate a video from an image using WanImageToVideoPipeline.

        Args:
            image_bytes: PNG/JPEG image bytes
            prompt: Optional text prompt to guide the animation
            model_id: Wan I2V model to use
            negative_prompt: Negative prompt
            width: Video width
            height: Video height
            num_frames: Number of frames to generate
            steps: Number of inference steps
            cfg_scale: Guidance scale
            fps: Frames per second for output MP4
            seed: Random seed (-1 for random)
            guidance_scale_2: Second guidance scale for MoE models (A14B)

        Returns:
            MP4 video bytes, or None on failure
        """
        try:
            import torch
            from PIL import Image
            import io

            pipeline_class = "WanImageToVideoPipeline"

            if not await self.load_model(model_id, pipeline_class):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Convert image bytes to PIL Image
                pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                # Resize to target dimensions
                pil_image = pil_image.resize((width, height), Image.LANCZOS)

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(
                    f"[DIFFUSERS] Generating I2V video: steps={steps}, "
                    f"size={width}x{height}, frames={num_frames}, seed={seed}"
                )

                def video_step_callback(pipe_inst, step, timestep, callback_kwargs):
                    _generation_progress["step"] = step + 1
                    _generation_progress["total_steps"] = steps
                    return callback_kwargs

                _guidance_scale_2 = guidance_scale_2
                _pil_image = pil_image

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    try:
                        gen_kwargs = {
                            "image": _pil_image,
                            "prompt": prompt if prompt else "",
                            "negative_prompt": negative_prompt if negative_prompt else None,
                            "width": width,
                            "height": height,
                            "num_frames": num_frames,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "callback_on_step_end": video_step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }
                        if _guidance_scale_2 is not None:
                            gen_kwargs["guidance_scale_2"] = _guidance_scale_2
                        result = pipe(**gen_kwargs)
                        if not hasattr(result, 'frames') or result.frames is None or len(result.frames) == 0:
                            raise ValueError("Pipeline returned no video frames")
                        return result.frames[0]
                    finally:
                        _generation_progress["active"] = False

                frames = await asyncio.to_thread(self._locked_generate, _generate)

                import tempfile
                import os
                from diffusers.utils import export_to_video
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    export_to_video(frames, tmp_path, fps=fps)
                    with open(tmp_path, 'rb') as f:
                        video_bytes = f.read()
                finally:
                    os.unlink(tmp_path)

                logger.info(
                    f"[DIFFUSERS] Generated I2V video: {len(video_bytes)} bytes, "
                    f"{num_frames} frames @ {fps}fps, seed={seed}"
                )
                return video_bytes

            finally:
                self._model_in_use[model_id] -= 1

        except Exception as e:
            logger.error(f"[DIFFUSERS] I2V video generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_image_with_fusion(
        self,
        prompt: str,
        t5_prompt: Optional[str] = None,
        alpha_factor: float = 0.0,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
        loras: Optional[list] = None,
        fusion_strategy: str = "legacy",
    ) -> Optional[bytes]:
        """
        Generate an image using T5-CLIP token-level fusion (Surrealizer)

        Fusion strategies:
        - "legacy": Original behavior. LERP first 77 tokens, append T5 rest
          unchanged. T5 tokens >77 act as semantic anchor (dilute surreal
          effect on long prompts).
        - "dual_alpha": Kontingente Ähnlichkeit. Gentle alpha on first 77
          tokens (structural anchor via CLIP-L), full alpha on tokens 78+
          (semantic surprise). Balances recognizability with extrapolation.
        - "normalized": Uniform alpha on ALL positions (CLIP=0 beyond 77),
          then L2-normalize each token to mean T5 magnitude. Preserves
          extrapolation direction, controls magnitude for attention balance.

        Args:
            prompt: Text prompt (used for CLIP-L encoding)
            t5_prompt: Optional expanded prompt for T5 encoding (None = use prompt)
            alpha_factor: -75 to +75 (raw from UI slider)
                0 = pure CLIP-L, 1 = pure T5, 15-35 = surreal sweet spot
            model_id: SD3.5 model to use
            negative_prompt: Negative prompt (fused with same alpha)
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            callback: Step callback for progress
            fusion_strategy: "legacy", "dual_alpha", or "normalized"

        Returns:
            PNG image bytes, or None on failure
        """
        try:
            import torch
            import torch.nn.functional as F
            import io

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Guard: verify individual encoder methods are available
                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[DIFFUSERS-FUSION] Pipeline missing _get_clip_prompt_embeds or _get_t5_prompt_embeds")
                    return None

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(f"[DIFFUSERS-FUSION] Generating: strategy={fusion_strategy}, alpha={alpha_factor}, steps={steps}, size={width}x{height}, seed={seed}, t5_expanded={t5_prompt is not None}")

                def _fuse_prompt(clip_text: str, t5_text: str):
                    """T5-CLIP fusion with selectable strategy.

                    Encoding (shared across all strategies):
                    - CLIP-L only (no CLIP-G): [1, 77, 4096] (768d real + 3328d zeros)
                    - T5-XXL: [1, T5_len, 4096] (all 4096d real)
                    - Pooled: CLIP-L(768d) + zeros(1280d) = [1, 2048]

                    The 768d/4096d asymmetry (CLIP-L real in a 4096d space) is the
                    foundation all strategies exploit — it creates the vector space
                    that extrapolation pushes into.
                    """
                    device = pipe._execution_device

                    with torch.no_grad():
                        # --- CLIP-L only (no CLIP-G) ---
                        clip_l_embeds, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=clip_text, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_padded = F.pad(clip_l_embeds, (0, 4096 - clip_l_embeds.shape[-1]))
                        pooled = F.pad(clip_l_pooled, (0, 1280))

                        # --- T5 encoding ---
                        t5_embeds = pipe._get_t5_prompt_embeds(
                            prompt=t5_text, num_images_per_prompt=1, max_sequence_length=512, device=device
                        )

                    interp_len = min(77, clip_padded.shape[1])
                    t5_len = t5_embeds.shape[1]

                    if fusion_strategy == "dual_alpha":
                        # Full extrapolation on core (where CLIP-T5 mixing creates
                        # surreal direction), gentle anchor on extended (prevents
                        # normal T5 semantics from dominating MMDiT attention).
                        alpha_core = alpha_factor
                        alpha_ext = alpha_factor * 0.15

                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]

                        # Core: full extrapolation (surreal direction from CLIP-T5 blend)
                        fused_core = (1.0 - alpha_core) * clip_interp + alpha_core * t5_interp
                        # Extended: gentle anchor (doesn't overwhelm core with normal semantics)
                        fused_ext = alpha_ext * t5_remainder

                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)

                        logger.info(
                            f"[FUSION:dual_alpha] core_α={alpha_core:.2f} ({interp_len}t), "
                            f"ext_α={alpha_ext:.2f} ({t5_len - interp_len}t)"
                        )

                    elif fusion_strategy == "normalized":
                        # Full extrapolation on core tokens, then scale extended
                        # tokens to match core magnitude. This preserves the surreal
                        # extrapolation direction while keeping attention balanced
                        # (extended tokens don't overwhelm OR underwhelm core).

                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]

                        # Core: full extrapolation (same as legacy)
                        fused_core = (1.0 - alpha_factor) * clip_interp + alpha_factor * t5_interp

                        # Scale extended tokens to match core's extrapolated magnitude
                        core_mag = fused_core.norm(dim=-1).mean()
                        t5_ext_norms = t5_remainder.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                        fused_ext = t5_remainder * (core_mag / t5_ext_norms)

                        fused_embeds = torch.cat([fused_core, fused_ext], dim=1)

                        logger.info(
                            f"[FUSION:normalized] α={alpha_factor}, core_mag={core_mag:.2f}, "
                            f"core={interp_len}t, ext={t5_len - interp_len}t"
                        )

                    else:
                        # Legacy: LERP first 77, append T5 remainder unchanged.
                        clip_interp = clip_padded[:, :interp_len, :]
                        t5_interp = t5_embeds[:, :interp_len, :]
                        t5_remainder = t5_embeds[:, interp_len:, :]

                        fused_part = (1.0 - alpha_factor) * clip_interp + alpha_factor * t5_interp
                        fused_embeds = torch.cat([fused_part, t5_remainder], dim=1)

                        logger.info(
                            f"[FUSION:legacy] α={alpha_factor}, LERP {interp_len}t, "
                            f"append {t5_len - interp_len}t unchanged"
                        )

                    return fused_embeds, pooled

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    if loras:
                        self._apply_loras(pipe, loras)
                    try:
                        # Effective T5 prompt: expanded if provided, else original
                        effective_t5_prompt = t5_prompt if t5_prompt else prompt

                        # Fuse positive prompt (CLIP-L gets original, T5 gets expanded)
                        pos_embeds, pos_pooled = _fuse_prompt(prompt, effective_t5_prompt)

                        # Free cached CUDA memory from pos encoding before neg pass
                        torch.cuda.empty_cache()

                        # Fuse negative prompt (no expansion — same text for both)
                        neg_text = negative_prompt if negative_prompt else ""
                        neg_embeds, neg_pooled = _fuse_prompt(neg_text, neg_text)

                        logger.info(
                            f"[DIFFUSERS-FUSION] strategy={fusion_strategy}, alpha={alpha_factor}, "
                            f"shape={pos_embeds.shape}"
                        )

                        def fusion_step_callback(pipe_inst, step, timestep, callback_kwargs):
                            _generation_progress["step"] = step + 1
                            _generation_progress["total_steps"] = steps
                            if callback:
                                try:
                                    callback(step, steps, callback_kwargs.get("latents"))
                                except Exception as e:
                                    logger.warning(f"[DIFFUSERS-FUSION] Callback error: {e}")
                            return callback_kwargs

                        # Build generation kwargs — all 4 embedding tensors bypass encode_prompt
                        gen_kwargs = {
                            "prompt_embeds": pos_embeds,
                            "negative_prompt_embeds": neg_embeds,
                            "pooled_prompt_embeds": pos_pooled,
                            "negative_pooled_prompt_embeds": neg_pooled,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "max_sequence_length": 512,
                            "callback_on_step_end": fusion_step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }

                        result = pipe(**gen_kwargs)
                        return result.images[0]
                    finally:
                        if loras:
                            self._remove_loras(pipe)
                        _generation_progress["active"] = False

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert to PNG bytes
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

                logger.info(f"[DIFFUSERS-FUSION] Generated image: {len(image_bytes)} bytes")
                return image_bytes

            finally:
                self._model_in_use[model_id] -= 1
                # Fusion creates manual embeddings (CLIP-L, T5, fused tensors) outside
                # the pipeline's scope. Without explicit cleanup, these fragment VRAM
                # and cause OOM on the next call at full resolution.
                torch.cuda.empty_cache()

        except Exception as e:
            logger.error(f"[DIFFUSERS-FUSION] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def generate_image_with_attention(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        capture_layers: Optional[list] = None,
        capture_every_n_steps: int = 5,
        callback: Optional[Callable[[int, int, Any], None]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate an image with attention map capture for Attention Cartography.

        Installs custom attention processors on selected transformer blocks,
        generates the image, collects text→image attention maps at specified
        timesteps and layers, then restores original processors.

        Args:
            prompt: Positive prompt
            model_id: Model to use
            negative_prompt: Negative prompt
            width/height: Image dimensions
            steps: Number of inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            capture_layers: Transformer block indices to capture (default: [3, 9, 17])
            capture_every_n_steps: Capture attention every N steps
            callback: Step callback for progress

        Returns:
            Dict with keys:
            - image_base64: base64 encoded PNG
            - tokens: list of token strings
            - attention_maps: {step_N: {layer_M: [[...]]}}
            - spatial_resolution: [h, w] of attention map grid
            - image_resolution: [h, w] of generated image
            - seed: actual seed used
        """
        try:
            import torch
            import io
            import base64

            from services.attention_processors_sd3 import (
                AttentionMapStore,
                install_attention_capture,
                restore_attention_processors,
            )

            if capture_layers is None:
                capture_layers = [3, 9, 17]

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                # Compute which steps to capture
                capture_steps = list(range(0, steps, capture_every_n_steps))
                if (steps - 1) not in capture_steps:
                    capture_steps.append(steps - 1)

                # Pre-compute CLIP-L token positions for attention map truncation.
                # SD3.5's encoder_hidden_states has ~589 text columns (77 CLIP + 512 T5).
                # We only need columns for actual word tokens (not BOS/EOS/PAD), reducing
                # JSON from ~300MB to ~10MB.
                token_column_indices = None
                tokens = []
                word_groups = []  # [[0,1], [2], [3,4]] — subtoken indices per word
                tokenizer = pipe.tokenizer  # CLIP-L
                if tokenizer is not None:
                    encoded = tokenizer(
                        prompt, padding=False, truncation=True,
                        max_length=77, return_tensors=None,
                    )
                    token_ids = encoded['input_ids']
                    token_column_indices = []
                    current_group = []
                    prev_raw = None
                    for pos, tid in enumerate(token_ids):
                        if tid in tokenizer.all_special_ids:
                            continue
                        token_idx = len(tokens)
                        token_column_indices.append(pos)
                        # CLIP BPE uses </w> suffix on word-FINAL subtokens
                        # (NOT leading-space like GPT-2)
                        raw = tokenizer.convert_ids_to_tokens(tid)
                        is_word_start = (
                            token_idx == 0
                            or (prev_raw is not None and prev_raw.endswith('</w>'))
                        )
                        display = raw.replace('</w>', '')
                        tokens.append(display)
                        if is_word_start and current_group:
                            word_groups.append(current_group)
                            current_group = []
                        current_group.append(token_idx)
                        prev_raw = raw
                    if current_group:
                        word_groups.append(current_group)
                    logger.info(
                        f"[DIFFUSERS-ATTENTION] CLIP-L: {len(tokens)} subtokens, "
                        f"{len(word_groups)} words, groups={word_groups}"
                    )

                # T5-XXL tokenization (tokenizer_3 in SD3.5)
                tokens_t5 = []
                word_groups_t5 = []
                t5_column_indices = []
                tokenizer_t5 = getattr(pipe, 'tokenizer_3', None)
                if tokenizer_t5 is not None:
                    encoded_t5 = tokenizer_t5(
                        prompt, padding=False, truncation=True,
                        max_length=512, return_tensors=None,
                    )
                    t5_ids = encoded_t5['input_ids']
                    pad_id = tokenizer_t5.pad_token_id
                    eos_id = tokenizer_t5.eos_token_id
                    current_group_t5 = []
                    for pos, tid in enumerate(t5_ids):
                        if tid == pad_id or tid == eos_id:
                            continue
                        t5_token_idx = len(tokens_t5)
                        # T5 columns start at offset 77 in the combined encoder_hidden_states
                        t5_column_indices.append(77 + pos)
                        # SentencePiece uses ▁ (U+2581) prefix as word-START marker
                        raw = tokenizer_t5.convert_ids_to_tokens(tid)
                        is_word_start = raw.startswith('\u2581')
                        display = raw.lstrip('\u2581')
                        tokens_t5.append(display)
                        if is_word_start and current_group_t5:
                            word_groups_t5.append(current_group_t5)
                            current_group_t5 = []
                        current_group_t5.append(t5_token_idx)
                    if current_group_t5:
                        word_groups_t5.append(current_group_t5)
                    logger.info(
                        f"[DIFFUSERS-ATTENTION] T5-XXL: {len(tokens_t5)} subtokens, "
                        f"{len(word_groups_t5)} words, groups={word_groups_t5}"
                    )

                # Combine CLIP-L + T5 column indices for the attention store
                combined_column_indices = (token_column_indices or []) + t5_column_indices

                # Create attention store
                store = AttentionMapStore(
                    capture_layers=capture_layers,
                    capture_steps=capture_steps,
                    text_column_indices=combined_column_indices if combined_column_indices else None,
                )

                logger.info(
                    f"[DIFFUSERS-ATTENTION] Generating: steps={steps}, size={width}x{height}, "
                    f"seed={seed}, capture_layers={capture_layers}, capture_steps={capture_steps}"
                )

                def _generate():
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    # Install attention capture processors
                    original_processors = install_attention_capture(pipe, store, capture_layers)

                    try:
                        # Step callback to update store's current_step
                        # IMPORTANT: callback_on_step_end fires AFTER step N completes.
                        # We set current_step = step + 1 so the NEXT forward pass sees the right step.
                        # Step 0's forward pass uses the initial current_step=0 (set below).
                        def step_callback(pipe_instance, step, timestep, callback_kwargs):
                            store.current_step = step + 1
                            _generation_progress["step"] = step + 1
                            _generation_progress["total_steps"] = steps
                            if callback:
                                try:
                                    callback(step, steps, callback_kwargs.get("latents"))
                                except Exception as e:
                                    logger.warning(f"[DIFFUSERS-ATTENTION] Callback error: {e}")
                            return callback_kwargs

                        gen_kwargs = {
                            "prompt": prompt,
                            "negative_prompt": negative_prompt if negative_prompt else None,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "callback_on_step_end": step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }

                        # SD3.5: Set max_sequence_length for T5
                        if hasattr(pipe, 'tokenizer_3'):
                            gen_kwargs["max_sequence_length"] = 512

                        result = pipe(**gen_kwargs)
                        return result.images[0]
                    finally:
                        _generation_progress["active"] = False
                        # Always restore original processors
                        restore_attention_processors(pipe, original_processors, capture_layers)

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert image to base64
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                # tokens already computed above (pre-generation CLIP-L tokenization)

                # Compute spatial resolution (patch grid)
                # SD3.5 uses 2x2 patches → 1024/16 = 64 spatial positions per axis
                patch_size = 2  # SD3 latent patch size
                vae_scale = 8   # VAE downscale factor
                spatial_h = height // (vae_scale * patch_size)
                spatial_w = width // (vae_scale * patch_size)

                # Log attention map dimensions for debugging
                map_sample_key = next(iter(store.maps), None)
                if map_sample_key:
                    layer_sample = next(iter(store.maps[map_sample_key].values()), None)
                    if layer_sample:
                        logger.info(
                            f"[DIFFUSERS-ATTENTION] Map shape: [{len(layer_sample)}×{len(layer_sample[0]) if layer_sample else 0}] "
                            f"(image_tokens × text_tokens)"
                        )

                result = {
                    "image_base64": image_base64,
                    "tokens": tokens,
                    "word_groups": word_groups,
                    "tokens_t5": tokens_t5,
                    "word_groups_t5": word_groups_t5,
                    "clip_token_count": len(tokens),
                    "attention_maps": store.maps,
                    "spatial_resolution": [spatial_h, spatial_w],
                    "image_resolution": [height, width],
                    "seed": seed,
                    "capture_layers": capture_layers,
                    "capture_steps": capture_steps,
                }

                logger.info(
                    f"[DIFFUSERS-ATTENTION] Generated with attention: "
                    f"{len(store.maps)} timesteps captured, "
                    f"tokens={len(tokens)}, spatial={spatial_h}x{spatial_w}"
                )
                return result

            finally:
                self._model_in_use[model_id] -= 1

        except Exception as e:
            logger.error(f"[DIFFUSERS-ATTENTION] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_image_with_probing(
        self,
        prompt_a: str,
        prompt_b: str,
        encoder: str = "t5",
        transfer_dims: list = None,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
    ) -> Optional[Dict[str, Any]]:
        """
        Feature Probing: analyze embedding differences between two prompts
        and optionally transfer selected dimensions.

        Phase 1 (transfer_dims=None): Encode both prompts, compute difference
        vector, generate image A. Returns image + probing analysis data.

        Phase 2 (transfer_dims provided): Copy selected dimensions from B→A,
        generate image with modified embedding (same seed for comparison).

        Args:
            prompt_a: Base prompt
            prompt_b: Comparison prompt
            encoder: Which encoder to probe ("clip_l", "clip_g", "t5")
            transfer_dims: Dimension indices to transfer (None = analysis only)
            negative_prompt: Negative prompt
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            model_id: Model to use

        Returns:
            Dict with image_base64, probing_data, seed
        """
        try:
            import torch
            import torch.nn.functional as F
            import io
            import base64
            from services.embedding_analyzer import (
                compute_dimension_differences,
                apply_dimension_transfer,
            )

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id):
                return {'error': f'Model loading failed for {model_id}'}

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                # Verify encoder access methods
                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[DIFFUSERS-PROBING] Pipeline missing encoder methods")
                    return {'error': 'Pipeline missing _get_clip_prompt_embeds or _get_t5_prompt_embeds'}

                # Generate random seed if needed
                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                logger.info(
                    f"[DIFFUSERS-PROBING] encoder={encoder}, transfer={'yes' if transfer_dims else 'no'}, "
                    f"steps={steps}, size={width}x{height}, seed={seed}"
                )

                def _generate():
                    device = pipe._execution_device
                    generator = torch.Generator(device=self.device).manual_seed(seed)

                    # --- Encode both prompts with the selected encoder ---
                    # _all_pooled_a/b only used for "all" mode
                    _all_pooled_a = _all_pooled_b = None

                    if encoder == "all":
                        # Encode all three encoders for both prompts
                        clip_l_a, clip_l_pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_a, clip_g_pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_a = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_l_b, clip_l_pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_b, clip_g_pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_b = pipe._get_t5_prompt_embeds(
                            prompt=prompt_b, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        # Compose full prompt_embeds: [CLIP-L+CLIP-G padded to 4096, T5] along seq dim
                        clip_combined_a = F.pad(torch.cat([clip_l_a, clip_g_a], dim=-1), (0, 4096 - 2048))
                        clip_combined_b = F.pad(torch.cat([clip_l_b, clip_g_b], dim=-1), (0, 4096 - 2048))
                        embed_a = torch.cat([clip_combined_a, t5_a], dim=1)  # [1, 77+512, 4096]
                        embed_b = torch.cat([clip_combined_b, t5_b], dim=1)
                        # Store composed pooled for interpolation during transfer
                        _all_pooled_a = torch.cat([clip_l_pooled_a, clip_g_pooled_a], dim=-1)  # [1, 2048]
                        _all_pooled_b = torch.cat([clip_l_pooled_b, clip_g_pooled_b], dim=-1)
                        pooled_a = pooled_b = None
                        embed_dim_name = "All Encoders (CLIP-L+CLIP-G+T5)"
                    elif encoder == "clip_l":
                        embed_a, pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        embed_b, pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        embed_dim_name = "CLIP-L (768d)"
                    elif encoder == "clip_g":
                        embed_a, pooled_a = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        embed_b, pooled_b = pipe._get_clip_prompt_embeds(
                            prompt=prompt_b, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        embed_dim_name = "CLIP-G (1280d)"
                    else:  # t5
                        embed_a = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        embed_b = pipe._get_t5_prompt_embeds(
                            prompt=prompt_b, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        pooled_a = pooled_b = None
                        embed_dim_name = "T5-XXL (4096d)"

                    logger.info(
                        f"[DIFFUSERS-PROBING] Encoded: {embed_dim_name}, "
                        f"A shape={embed_a.shape}, B shape={embed_b.shape}"
                    )

                    # --- Compute difference vector ---
                    diff_data = compute_dimension_differences(embed_a, embed_b)

                    # --- Build the prompt_embeds for generation ---
                    if transfer_dims is not None:
                        # Phase 2: modify embed_a with selected dims from embed_b
                        gen_embed = apply_dimension_transfer(embed_a, embed_b, transfer_dims)
                        logger.info(f"[DIFFUSERS-PROBING] Transferred {len(transfer_dims)} dims from B→A")
                    else:
                        # Phase 1: generate with original embed_a
                        gen_embed = embed_a

                    # --- Prepare full embedding for SD3.5 pipeline ---
                    # SD3.5 expects prompt_embeds of shape [1, seq_len, 4096]
                    # composed of: CLIP-L(768) + CLIP-G(1280) padded to 4096, then T5(4096)
                    # concatenated along sequence dimension.
                    #
                    # "all" mode: gen_embed is already the full composed tensor
                    # Individual modes: compose from probed + non-probed encoders

                    if encoder == "all":
                        # gen_embed is already full [1, 589, 4096] composed embedding
                        prompt_embeds = gen_embed
                        # Interpolate pooled based on transfer coverage
                        if transfer_dims is not None and _all_pooled_a is not None:
                            coverage = len(transfer_dims) / embed_a.shape[-1]
                            pooled_embeds = (1.0 - coverage) * _all_pooled_a + coverage * _all_pooled_b
                            logger.info(f"[DIFFUSERS-PROBING] All-mode pooled interpolation: coverage={coverage:.1%}")
                        else:
                            pooled_embeds = _all_pooled_a

                    elif encoder == "t5":
                        # Get CLIP embeddings normally
                        clip_l_embed, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_embed, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        # CLIP embeddings combined: [1, 77, 768+1280] → padded to 4096
                        clip_combined = torch.cat([clip_l_embed, clip_g_embed], dim=-1)  # [1, 77, 2048]
                        clip_combined = F.pad(clip_combined, (0, 4096 - clip_combined.shape[-1]))  # [1, 77, 4096]

                        # T5 is what we're probing — use gen_embed (original or modified)
                        t5_embed = gen_embed  # [1, seq_len, 4096]

                        # Combine: clip + t5
                        prompt_embeds = torch.cat([clip_combined, t5_embed], dim=1)
                        pooled_embeds = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)  # [1, 2048]

                    elif encoder == "clip_l":
                        # Get CLIP-G and T5 normally
                        clip_g_embed, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_embed = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )

                        # CLIP-L is what we're probing — use gen_embed (768d)
                        clip_combined = torch.cat([gen_embed, clip_g_embed], dim=-1)  # [1, 77, 2048]
                        clip_combined = F.pad(clip_combined, (0, 4096 - clip_combined.shape[-1]))  # [1, 77, 4096]

                        prompt_embeds = torch.cat([clip_combined, t5_embed], dim=1)
                        # Pooled: use original CLIP-L pooled (not modified — pooled is global, not per-dim)
                        pooled_embeds = torch.cat([pooled_a, clip_g_pooled], dim=-1)

                    else:  # clip_g
                        # Get CLIP-L and T5 normally
                        clip_l_embed, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        t5_embed = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )

                        # CLIP-G is what we're probing — use gen_embed (1280d)
                        clip_combined = torch.cat([clip_l_embed, gen_embed], dim=-1)  # [1, 77, 2048]
                        clip_combined = F.pad(clip_combined, (0, 4096 - clip_combined.shape[-1]))  # [1, 77, 4096]

                        prompt_embeds = torch.cat([clip_combined, t5_embed], dim=1)
                        pooled_embeds = torch.cat([clip_l_pooled, pooled_b if transfer_dims else pooled_a], dim=-1)

                    # --- Negative embeddings (encode normally) ---
                    neg_text = negative_prompt if negative_prompt else ""
                    neg_clip_l, neg_clip_l_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=0
                    )
                    neg_clip_g, neg_clip_g_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=1
                    )
                    neg_t5 = pipe._get_t5_prompt_embeds(
                        prompt=neg_text, num_images_per_prompt=1,
                        max_sequence_length=512, device=device
                    )
                    neg_clip_combined = torch.cat([neg_clip_l, neg_clip_g], dim=-1)
                    neg_clip_combined = F.pad(neg_clip_combined, (0, 4096 - neg_clip_combined.shape[-1]))
                    neg_prompt_embeds = torch.cat([neg_clip_combined, neg_t5], dim=1)
                    neg_pooled = torch.cat([neg_clip_l_pooled, neg_clip_g_pooled], dim=-1)

                    # --- Generate image ---
                    gen_kwargs = {
                        "prompt_embeds": prompt_embeds,
                        "negative_prompt_embeds": neg_prompt_embeds,
                        "pooled_prompt_embeds": pooled_embeds,
                        "negative_pooled_prompt_embeds": neg_pooled,
                        "width": width,
                        "height": height,
                        "num_inference_steps": steps,
                        "guidance_scale": cfg_scale,
                        "generator": generator,
                        "max_sequence_length": 512,
                    }

                    result = pipe(**gen_kwargs)
                    return result.images[0], diff_data

                image, diff_data = await asyncio.to_thread(self._locked_generate, _generate)

                # Convert to base64
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                probing_data = {
                    'encoder': encoder,
                    'embed_dim': diff_data['embed_dim'],
                    **diff_data,
                }

                if transfer_dims is not None:
                    probing_data['transferred_dims'] = transfer_dims
                    probing_data['num_transferred'] = len(transfer_dims)

                logger.info(
                    f"[DIFFUSERS-PROBING] Done: embed_dim={diff_data['embed_dim']}, "
                    f"top diff={diff_data['top_values'][:3] if diff_data['top_values'] else 'none'}"
                )

                return {
                    'image_base64': image_base64,
                    'probing_data': probing_data,
                    'seed': seed,
                }

            finally:
                self._model_in_use[model_id] -= 1
                # Probing creates manual embeddings (up to 6 encoder passes for "all" mode)
                # outside the pipeline's scope. Cleanup prevents VRAM fragmentation.
                torch.cuda.empty_cache()

        except Exception as e:
            logger.error(f"[DIFFUSERS-PROBING] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}

    async def generate_image_with_algebra(
        self,
        prompt_a: str,
        prompt_b: str,
        prompt_c: str,
        encoder: str = "all",
        scale_sub: float = 1.0,
        scale_add: float = 1.0,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        generate_reference: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Concept Algebra: A - scale_sub*B + scale_add*C on text encoder embeddings.

        Inspired by Mikolov's word2vec analogies (King - Man + Woman = Queen),
        applied to SD3.5 text encoder embeddings for image generation.

        Args:
            prompt_a: Base concept (e.g. "King on a throne")
            prompt_b: Concept to subtract (e.g. "Man")
            prompt_c: Concept to add (e.g. "Woman")
            encoder: Which encoder(s) to apply algebra on ("all", "clip_l", "clip_g", "t5")
            scale_sub: Scaling factor for subtraction
            scale_add: Scaling factor for addition
            negative_prompt: Negative prompt
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            model_id: Model to use
            generate_reference: Also generate image with original embed_a

        Returns:
            Dict with reference_image, result_image, algebra_data, seed
        """
        try:
            import torch
            import torch.nn.functional as F
            import io
            import base64
            from services.embedding_analyzer import apply_concept_algebra

            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[DIFFUSERS-ALGEBRA] Pipeline missing encoder methods")
                    return None

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                logger.info(
                    f"[DIFFUSERS-ALGEBRA] encoder={encoder}, scale_sub={scale_sub}, scale_add={scale_add}, "
                    f"steps={steps}, size={width}x{height}, seed={seed}"
                )

                def _encode_prompt(prompt_text, device):
                    """Encode a single prompt with the selected encoder."""
                    if encoder == "all":
                        clip_l, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5 = pipe._get_t5_prompt_embeds(
                            prompt=prompt_text, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_combined = F.pad(torch.cat([clip_l, clip_g], dim=-1), (0, 4096 - 2048))
                        embed = torch.cat([clip_combined, t5], dim=1)
                        pooled = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)
                        return embed, pooled
                    elif encoder == "clip_l":
                        embed, pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        return embed, pooled
                    elif encoder == "clip_g":
                        embed, pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        return embed, pooled
                    else:  # t5
                        embed = pipe._get_t5_prompt_embeds(
                            prompt=prompt_text, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        return embed, None

                def _compose_full_embedding(gen_embed, gen_pooled, device):
                    """Compose probed encoder embedding into full SD3.5 format."""
                    if encoder == "all":
                        return gen_embed, gen_pooled
                    elif encoder == "t5":
                        clip_l_e, clip_l_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g_e, clip_g_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        clip_combined = F.pad(torch.cat([clip_l_e, clip_g_e], dim=-1), (0, 4096 - 2048))
                        prompt_embeds = torch.cat([clip_combined, gen_embed], dim=1)
                        pooled_embeds = torch.cat([clip_l_p, clip_g_p], dim=-1)
                        return prompt_embeds, pooled_embeds
                    elif encoder == "clip_l":
                        clip_g_e, clip_g_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=1
                        )
                        t5_e = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_combined = F.pad(torch.cat([gen_embed, clip_g_e], dim=-1), (0, 4096 - 2048))
                        prompt_embeds = torch.cat([clip_combined, t5_e], dim=1)
                        pooled_embeds = torch.cat([gen_pooled, clip_g_p], dim=-1)
                        return prompt_embeds, pooled_embeds
                    else:  # clip_g
                        clip_l_e, clip_l_p = pipe._get_clip_prompt_embeds(
                            prompt=prompt_a, device=device, num_images_per_prompt=1, clip_model_index=0
                        )
                        t5_e = pipe._get_t5_prompt_embeds(
                            prompt=prompt_a, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                        clip_combined = F.pad(torch.cat([clip_l_e, gen_embed], dim=-1), (0, 4096 - 2048))
                        prompt_embeds = torch.cat([clip_combined, t5_e], dim=1)
                        pooled_embeds = torch.cat([clip_l_p, gen_pooled], dim=-1)
                        return prompt_embeds, pooled_embeds

                def _build_negative_embeds(device):
                    """Build negative prompt embeddings."""
                    neg_text = negative_prompt if negative_prompt else ""
                    neg_clip_l, neg_clip_l_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=0
                    )
                    neg_clip_g, neg_clip_g_pooled = pipe._get_clip_prompt_embeds(
                        prompt=neg_text, device=device, num_images_per_prompt=1, clip_model_index=1
                    )
                    neg_t5 = pipe._get_t5_prompt_embeds(
                        prompt=neg_text, num_images_per_prompt=1,
                        max_sequence_length=512, device=device
                    )
                    neg_clip_combined = F.pad(torch.cat([neg_clip_l, neg_clip_g], dim=-1), (0, 4096 - 2048))
                    neg_prompt_embeds = torch.cat([neg_clip_combined, neg_t5], dim=1)
                    neg_pooled = torch.cat([neg_clip_l_pooled, neg_clip_g_pooled], dim=-1)
                    return neg_prompt_embeds, neg_pooled

                def _generate_image(prompt_embeds, pooled_embeds, neg_prompt_embeds, neg_pooled, generator):
                    """Generate a single image from pre-computed embeddings."""
                    gen_kwargs = {
                        "prompt_embeds": prompt_embeds,
                        "negative_prompt_embeds": neg_prompt_embeds,
                        "pooled_prompt_embeds": pooled_embeds,
                        "negative_pooled_prompt_embeds": neg_pooled,
                        "width": width,
                        "height": height,
                        "num_inference_steps": steps,
                        "guidance_scale": cfg_scale,
                        "generator": generator,
                        "max_sequence_length": 512,
                    }
                    result = pipe(**gen_kwargs)
                    return result.images[0]

                def _image_to_base64(image):
                    """Convert PIL image to base64 PNG string."""
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    return base64.b64encode(buffer.getvalue()).decode('utf-8')

                def _generate():
                    device = pipe._execution_device
                    generator_ref = torch.Generator(device=self.device).manual_seed(seed)
                    generator_res = torch.Generator(device=self.device).manual_seed(seed)

                    # Encode all three prompts with selected encoder
                    embed_a, pooled_a = _encode_prompt(prompt_a, device)
                    embed_b, pooled_b = _encode_prompt(prompt_b, device)
                    embed_c, pooled_c = _encode_prompt(prompt_c, device)

                    logger.info(
                        f"[DIFFUSERS-ALGEBRA] Encoded: A={embed_a.shape}, B={embed_b.shape}, C={embed_c.shape}"
                    )

                    # Apply concept algebra (token + pooled embeddings)
                    embed_result, l2_dist, pooled_result = apply_concept_algebra(
                        embed_a, embed_b, embed_c, scale_sub, scale_add,
                        pooled_a, pooled_b, pooled_c,
                    )
                    if pooled_result is None:
                        pooled_result = pooled_a

                    # Build negative embeddings (shared for both generations)
                    neg_prompt_embeds, neg_pooled = _build_negative_embeds(device)

                    # Generate reference image (prompt A, same seed)
                    reference_b64 = None
                    if generate_reference:
                        ref_prompt_embeds, ref_pooled = _compose_full_embedding(embed_a, pooled_a, device)
                        ref_image = _generate_image(ref_prompt_embeds, ref_pooled, neg_prompt_embeds, neg_pooled, generator_ref)
                        reference_b64 = _image_to_base64(ref_image)
                        logger.info("[DIFFUSERS-ALGEBRA] Reference image generated")

                    # Generate result image (algebra embedding, same seed)
                    res_prompt_embeds, res_pooled = _compose_full_embedding(embed_result, pooled_result, device)
                    res_image = _generate_image(res_prompt_embeds, res_pooled, neg_prompt_embeds, neg_pooled, generator_res)
                    result_b64 = _image_to_base64(res_image)
                    logger.info("[DIFFUSERS-ALGEBRA] Result image generated")

                    return reference_b64, result_b64, l2_dist

                reference_b64, result_b64, l2_dist = await asyncio.to_thread(self._locked_generate, _generate)

                return {
                    'reference_image': reference_b64,
                    'result_image': result_b64,
                    'algebra_data': {
                        'encoder': encoder,
                        'operation': 'A - scale_sub*B + scale_add*C',
                        'scale_sub': scale_sub,
                        'scale_add': scale_add,
                        'l2_distance': l2_dist,
                    },
                    'seed': seed,
                }

            finally:
                self._model_in_use[model_id] -= 1
                # Algebra creates manual embeddings (3 prompts x up to 3 encoders)
                # outside the pipeline's scope. Cleanup prevents VRAM fragmentation.
                torch.cuda.empty_cache()

        except Exception as e:
            logger.error(f"[DIFFUSERS-ALGEBRA] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_image_with_archaeology(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        capture_every_n: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate image with step-by-step denoising visualization.

        At each sampling step, VAE-decodes the current latents into a 512x512
        JPEG thumbnail. Returns all step thumbnails plus the full-resolution
        final image.

        Args:
            prompt: Text prompt
            model_id: Model to use
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            steps: Number of sampling steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            capture_every_n: Capture every N steps (1 = every step)

        Returns:
            Dict with image_base64, step_images, seed, total_steps; or None on failure
        """
        try:
            import torch
            import io
            import base64

            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                generator = torch.Generator(device=self.device).manual_seed(seed)

                logger.info(
                    f"[DIFFUSERS-ARCHAEOLOGY] Generating: prompt={prompt[:80]!r}, "
                    f"steps={steps}, seed={seed}, capture_every_n={capture_every_n}"
                )

                step_images = []

                def _generate():
                    from diffusers.image_processor import VaeImageProcessor
                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})

                    def step_callback(pipe_instance, step, timestep, callback_kwargs):
                        _generation_progress["step"] = step + 1
                        _generation_progress["total_steps"] = steps
                        if capture_every_n > 1 and step % capture_every_n != 0:
                            return callback_kwargs

                        try:
                            latents = callback_kwargs.get("latents")
                            if latents is not None:
                                with torch.no_grad():
                                    decoded = pipe_instance.vae.decode(
                                        latents / pipe_instance.vae.config.scaling_factor
                                    ).sample

                                processor = VaeImageProcessor()
                                pil_image = processor.postprocess(decoded, output_type="pil")[0]

                                # Encode as full-resolution JPEG q95
                                buf = io.BytesIO()
                                pil_image.save(buf, format="JPEG", quality=95)
                                b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

                                step_images.append({
                                    'step': step,
                                    'timestep': float(timestep),
                                    'image_base64': b64,
                                })
                        except Exception as e:
                            logger.warning(f"[DIFFUSERS-ARCHAEOLOGY] Step {step} capture failed: {e}")

                        return callback_kwargs

                    try:
                        gen_kwargs = {
                            "prompt": prompt,
                            "negative_prompt": negative_prompt if negative_prompt else None,
                            "width": width,
                            "height": height,
                            "num_inference_steps": steps,
                            "guidance_scale": cfg_scale,
                            "generator": generator,
                            "callback_on_step_end": step_callback,
                            "callback_on_step_end_tensor_inputs": ["latents"],
                        }

                        if hasattr(pipe, 'tokenizer_3'):
                            gen_kwargs["max_sequence_length"] = 512

                        result = pipe(**gen_kwargs)
                        return result.images[0]
                    finally:
                        _generation_progress["active"] = False

                image = await asyncio.to_thread(self._locked_generate, _generate)

                # Final image as full-resolution PNG base64
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                logger.info(
                    f"[DIFFUSERS-ARCHAEOLOGY] Done: {len(step_images)} step images captured, "
                    f"final PNG {len(buffer.getvalue())} bytes"
                )

                return {
                    'image_base64': image_base64,
                    'step_images': step_images,
                    'seed': seed,
                    'total_steps': steps,
                }

            finally:
                self._model_in_use[model_id] -= 1

        except Exception as e:
            logger.error(f"[DIFFUSERS-ARCHAEOLOGY] Generation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _tokenize_prompt(self, pipe, prompt: str) -> list:
        """Tokenize a prompt and return human-readable token strings.

        Uses the CLIP tokenizer (tokenizer_1) for display-friendly tokens,
        since CLIP tokens map cleanly to words/subwords.
        """
        try:
            tokenizer = pipe.tokenizer  # CLIP-L tokenizer
            if tokenizer is None and hasattr(pipe, 'tokenizer_2'):
                tokenizer = pipe.tokenizer_2  # CLIP-G
            if tokenizer is None:
                return [prompt]  # Fallback: return whole prompt

            encoded = tokenizer(
                prompt,
                padding=False,
                truncation=True,
                max_length=77,
                return_tensors=None,
            )
            token_ids = encoded['input_ids']

            # Decode each token individually, skip special tokens
            tokens = []
            for tid in token_ids:
                decoded = tokenizer.decode([tid], skip_special_tokens=True).strip()
                if decoded:
                    tokens.append(decoded)

            return tokens if tokens else [prompt]

        except Exception as e:
            logger.warning(f"[DIFFUSERS-ATTENTION] Tokenization failed: {e}")
            return prompt.split()

    async def generate_image_streaming(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate image with step-by-step streaming for live preview

        Yields dicts with:
        - {"type": "progress", "step": N, "total": M}
        - {"type": "preview", "image": base64_encoded_preview}
        - {"type": "complete", "image": base64_encoded_final}
        - {"type": "error", "message": "..."}
        """
        try:
            import torch
            import io
            import base64

            # Ensure model is loaded and on GPU
            if not await self.load_model(model_id):
                yield {"type": "error", "message": f"Failed to load model: {model_id}"}
                return

            pipe = self._pipelines[model_id]
            steps = kwargs.get("steps", 25)

            # Create queue for step updates
            step_queue: asyncio.Queue = asyncio.Queue()

            def step_callback(pipe_instance, step, timestep, callback_kwargs):
                # Decode latents to preview image (every N steps)
                if step % 5 == 0 or step == steps - 1:
                    try:
                        latents = callback_kwargs.get("latents")
                        if latents is not None:
                            # Quick decode for preview (lower quality is fine)
                            with torch.no_grad():
                                preview = pipe_instance.vae.decode(
                                    latents / pipe_instance.vae.config.scaling_factor
                                ).sample

                            # Convert to image
                            from diffusers.image_processor import VaeImageProcessor
                            processor = VaeImageProcessor()
                            preview_image = processor.postprocess(preview, output_type="pil")[0]

                            # Encode to base64
                            buffer = io.BytesIO()
                            preview_image.save(buffer, format="JPEG", quality=50)
                            b64 = base64.b64encode(buffer.getvalue()).decode()

                            step_queue.put_nowait({
                                "type": "preview",
                                "step": step,
                                "total": steps,
                                "image": b64
                            })
                    except Exception as e:
                        logger.warning(f"[DIFFUSERS] Preview generation failed: {e}")

                step_queue.put_nowait({
                    "type": "progress",
                    "step": step,
                    "total": steps
                })
                return callback_kwargs

            # Start generation in background
            async def generate():
                return await self.generate_image(
                    prompt=prompt,
                    model_id=model_id,
                    callback=step_callback,
                    **kwargs
                )

            gen_task = asyncio.create_task(generate())

            # Stream progress updates
            while not gen_task.done():
                try:
                    update = await asyncio.wait_for(step_queue.get(), timeout=0.1)
                    yield update
                except asyncio.TimeoutError:
                    continue

            # Drain remaining queue
            while not step_queue.empty():
                yield step_queue.get_nowait()

            # Get final result
            final_image = await gen_task

            if final_image:
                yield {
                    "type": "complete",
                    "image": base64.b64encode(final_image).decode()
                }
            else:
                yield {
                    "type": "error",
                    "message": "Generation failed"
                }

        except Exception as e:
            logger.error(f"[DIFFUSERS] Streaming error: {e}")
            yield {"type": "error", "message": str(e)}

    async def generate_mosaic_tiles(
        self,
        grid_assignment: list,
        region_labels: dict,
        original_image_base64: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        tile_size: int = 512,
        steps: int = 8,
        cfg_scale: float = 3.5,
        strength: float = 0.7,
        seed: int = -1,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate mosaic tiles via img2img from original image patches.

        Each grid cell's patch from the original image is used as the
        init_image for img2img denoising with the cell's concept prompt.
        The tile retains the original's brightness/color while showing
        the concept — the Arcimboldo principle.

        Args:
            grid_assignment: [[int]] grid of region indices
            region_labels: {region_idx_str: "concept label"}
            original_image_base64: Original image to extract patches from
            model_id: SD3.5 model to use
            tile_size: Tile generation resolution
            steps: Inference steps
            cfg_scale: CFG scale
            strength: Denoising strength (0=keep original, 1=full denoise)
            seed: Base seed (-1 for random)

        Returns:
            Dict with tiles keyed by "row_col": base64_jpeg
        """
        try:
            import torch
            import io
            import base64
            from PIL import Image as PILImage
            from diffusers import StableDiffusion3Img2ImgPipeline

            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                t2i_pipe = self._pipelines[model_id]

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                grid = grid_assignment
                grid_h = len(grid)
                grid_w = len(grid[0]) if grid_h > 0 else 0
                total_tiles = grid_h * grid_w

                logger.info(
                    f"[MOSAIC-TILES] img2img {grid_h}x{grid_w}={total_tiles} tiles, "
                    f"strength={strength}, steps={steps}"
                )

                _generation_progress.update({
                    "step": 0, "total_steps": total_tiles, "active": True
                })

                def _generate():
                    # Create img2img pipeline from loaded t2i pipeline
                    i2i_pipe = StableDiffusion3Img2ImgPipeline.from_pipe(t2i_pipe)

                    # Decode original image
                    orig_data = base64.b64decode(original_image_base64)
                    orig_img = PILImage.open(io.BytesIO(orig_data)).convert('RGB')
                    orig_w, orig_h = orig_img.size
                    cell_w = orig_w // grid_w
                    cell_h = orig_h // grid_h

                    tiles_result = {}
                    tiles_done = 0

                    with torch.no_grad():
                        for gy in range(grid_h):
                            for gx in range(grid_w):
                                region_idx = str(grid[gy][gx])
                                label = region_labels.get(region_idx, "object")

                                # Extract cell patch from original
                                x0 = gx * cell_w
                                y0 = gy * cell_h
                                patch = orig_img.crop((x0, y0, x0 + cell_w, y0 + cell_h))
                                patch = patch.resize((tile_size, tile_size), PILImage.LANCZOS)

                                # img2img: denoise from original patch
                                tile_seed = seed + gy * grid_w + gx
                                generator = torch.Generator(device=self.device).manual_seed(tile_seed)

                                result = i2i_pipe(
                                    prompt=f"A detailed close-up of {label}, square composition",
                                    image=patch,
                                    strength=strength,
                                    num_inference_steps=steps,
                                    guidance_scale=cfg_scale,
                                    generator=generator,
                                )

                                tile_img = result.images[0]

                                # Encode to JPEG
                                buffer = io.BytesIO()
                                tile_img.save(buffer, format="JPEG", quality=85)
                                tile_key = f"{gy}_{gx}"
                                tiles_result[tile_key] = base64.b64encode(
                                    buffer.getvalue()
                                ).decode('utf-8')

                                tiles_done += 1
                                _generation_progress["step"] = tiles_done

                                if tiles_done % 50 == 0:
                                    logger.info(f"[MOSAIC-TILES] {tiles_done}/{total_tiles}")

                    _generation_progress["active"] = False

                    logger.info(f"[MOSAIC-TILES] Done: {total_tiles} tiles")
                    return tiles_result

                tiles = await asyncio.to_thread(self._locked_generate, _generate)

                return {
                    "tiles": tiles,
                    "seed": seed,
                    "total_generated": len(tiles),
                }

            finally:
                self._model_in_use[model_id] -= 1
                torch.cuda.empty_cache()

        except Exception as e:
            logger.error(f"[MOSAIC-TILES] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def generate_image_composable(
        self,
        concepts: list,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        normalize_weights: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Composable Diffusion: per-concept noise prediction blending.

        Instead of encoding all concepts into one embedding, each concept gets
        its own transformer pass at every denoising step. Noise predictions are
        blended with weights before the scheduler step.

        Based on Liu et al. (2022) "Compositional Visual Generation with
        Composable Diffusion Models".

        Args:
            concepts: List of {"prompt": str, "weight": float} dicts
            model_id: SD3.5 model to use
            negative_prompt: Shared negative prompt
            width/height: Image dimensions
            steps: Inference steps
            cfg_scale: CFG scale
            seed: Random seed (-1 for random)
            normalize_weights: If True, concept weights sum to 1.0

        Returns:
            Dict with image_base64, seed, concept_count, timing_s
        """
        try:
            import torch
            import torch.nn.functional as F
            import io
            import base64

            if not concepts or len(concepts) < 2:
                logger.error("[COMPOSABLE] Need at least 2 concepts")
                return None

            if not await self.load_model(model_id):
                return None

            self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
            try:
                self._model_last_used[model_id] = time.time()
                pipe = self._pipelines[model_id]

                if not hasattr(pipe, '_get_clip_prompt_embeds') or not hasattr(pipe, '_get_t5_prompt_embeds'):
                    logger.error("[COMPOSABLE] Pipeline missing encoder methods")
                    return None

                if seed == -1:
                    import random
                    seed = random.randint(0, 2**32 - 1)

                # Extract and optionally normalize weights
                weights = [c.get("weight", 1.0) for c in concepts]
                if normalize_weights:
                    w_sum = sum(weights)
                    if w_sum > 0:
                        weights = [w / w_sum for w in weights]

                logger.info(
                    f"[COMPOSABLE] {len(concepts)} concepts, weights={[f'{w:.2f}' for w in weights]}, "
                    f"steps={steps}, size={width}x{height}, seed={seed}, cfg={cfg_scale}"
                )

                def _encode_full(prompt_text, device):
                    """Encode a prompt with all three SD3.5 encoders."""
                    with torch.no_grad():
                        clip_l, clip_l_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device,
                            num_images_per_prompt=1, clip_model_index=0
                        )
                        clip_g, clip_g_pooled = pipe._get_clip_prompt_embeds(
                            prompt=prompt_text, device=device,
                            num_images_per_prompt=1, clip_model_index=1
                        )
                        t5 = pipe._get_t5_prompt_embeds(
                            prompt=prompt_text, num_images_per_prompt=1,
                            max_sequence_length=512, device=device
                        )
                    clip_combined = F.pad(
                        torch.cat([clip_l, clip_g], dim=-1),
                        (0, 4096 - 2048)
                    )
                    prompt_embeds = torch.cat([clip_combined, t5], dim=1)
                    pooled = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)
                    return prompt_embeds, pooled

                def _generate():
                    from diffusers.pipelines.stable_diffusion_3.pipeline_stable_diffusion_3 import (
                        retrieve_timesteps, calculate_shift
                    )

                    _generation_progress.update({"step": 0, "total_steps": steps, "active": True})
                    start_time = time.time()

                    try:
                        device = pipe._execution_device
                        generator = torch.Generator(device=self.device).manual_seed(seed)

                        # --- Encode all concepts ---
                        concept_embeds_list = []
                        concept_pooled_list = []
                        for i, concept in enumerate(concepts):
                            embeds, pooled = _encode_full(concept["prompt"], device)
                            concept_embeds_list.append(embeds)
                            concept_pooled_list.append(pooled)
                            logger.info(f"[COMPOSABLE] Encoded concept {i}: '{concept['prompt'][:50]}' shape={embeds.shape}")

                        # Pad all concept embeds to same sequence length
                        max_seq_len = max(e.shape[1] for e in concept_embeds_list)
                        for i in range(len(concept_embeds_list)):
                            if concept_embeds_list[i].shape[1] < max_seq_len:
                                pad_len = max_seq_len - concept_embeds_list[i].shape[1]
                                concept_embeds_list[i] = F.pad(concept_embeds_list[i], (0, 0, 0, pad_len))

                        # --- Encode negative prompt ---
                        neg_text = negative_prompt if negative_prompt else ""
                        neg_embeds, neg_pooled = _encode_full(neg_text, device)
                        # Pad negative to same seq length
                        if neg_embeds.shape[1] < max_seq_len:
                            pad_len = max_seq_len - neg_embeds.shape[1]
                            neg_embeds = F.pad(neg_embeds, (0, 0, 0, pad_len))

                        torch.cuda.empty_cache()

                        # --- Prepare latents ---
                        num_channels_latents = pipe.transformer.config.in_channels
                        latents = pipe.prepare_latents(
                            1, num_channels_latents, height, width,
                            concept_embeds_list[0].dtype, device, generator, None
                        )

                        # --- Prepare timesteps with dynamic shifting ---
                        scheduler_kwargs = {}
                        if pipe.scheduler.config.get("use_dynamic_shifting", None):
                            _, _, lat_h, lat_w = latents.shape
                            image_seq_len = (lat_h // pipe.transformer.config.patch_size) * (
                                lat_w // pipe.transformer.config.patch_size
                            )
                            mu = calculate_shift(
                                image_seq_len,
                                pipe.scheduler.config.get("base_image_seq_len", 256),
                                pipe.scheduler.config.get("max_image_seq_len", 4096),
                                pipe.scheduler.config.get("base_shift", 0.5),
                                pipe.scheduler.config.get("max_shift", 1.16),
                            )
                            scheduler_kwargs["mu"] = mu

                        timesteps, num_inference_steps = retrieve_timesteps(
                            pipe.scheduler, steps, device, **scheduler_kwargs
                        )

                        # === COMPOSABLE DENOISING LOOP ===
                        with torch.no_grad():
                            for step_idx, t in enumerate(timesteps):
                                _generation_progress["step"] = step_idx

                                timestep_single = t.expand(latents.shape[0])

                                # 1. Unconditional pass (shared negative)
                                noise_uncond = pipe.transformer(
                                    hidden_states=latents,
                                    timestep=timestep_single,
                                    encoder_hidden_states=neg_embeds,
                                    pooled_projections=neg_pooled,
                                    return_dict=False,
                                )[0]

                                # 2. Per-concept conditional passes
                                noise_composed = torch.zeros_like(noise_uncond)
                                for i, (embeds, pooled, w) in enumerate(
                                    zip(concept_embeds_list, concept_pooled_list, weights)
                                ):
                                    noise_i = pipe.transformer(
                                        hidden_states=latents,
                                        timestep=timestep_single,
                                        encoder_hidden_states=embeds,
                                        pooled_projections=pooled,
                                        return_dict=False,
                                    )[0]
                                    noise_composed = noise_composed + w * noise_i

                                # 3. CFG: uncond + cfg_scale * (composed - uncond)
                                noise_pred = noise_uncond + cfg_scale * (noise_composed - noise_uncond)

                                # 4. Scheduler step
                                latents_dtype = latents.dtype
                                latents = pipe.scheduler.step(noise_pred, t, latents, return_dict=False)[0]
                                if latents.dtype != latents_dtype:
                                    latents = latents.to(latents_dtype)

                        _generation_progress["step"] = steps

                        # === VAE decode ===
                        with torch.no_grad():
                            latents = (latents / pipe.vae.config.scaling_factor) + pipe.vae.config.shift_factor
                            image = pipe.vae.decode(latents, return_dict=False)[0]
                            image = pipe.image_processor.postprocess(image, output_type="pil")[0]

                        elapsed = time.time() - start_time
                        logger.info(f"[COMPOSABLE] Done in {elapsed:.1f}s, {len(concepts)} concepts × {steps} steps")

                        # Convert to base64
                        buffer = io.BytesIO()
                        image.save(buffer, format="PNG")
                        image_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                        return {
                            "image_base64": image_b64,
                            "seed": seed,
                            "concept_count": len(concepts),
                            "weights_used": weights,
                            "timing_s": round(elapsed, 1),
                        }
                    finally:
                        _generation_progress["active"] = False

                result = await asyncio.to_thread(self._locked_generate, _generate)
                return result

            finally:
                self._model_in_use[model_id] -= 1
                torch.cuda.empty_cache()

        except Exception as e:
            logger.error(f"[COMPOSABLE] Generation error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def encode_prompt_info(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
    ) -> Dict[str, Any]:
        """
        Analyze how the three SD3.5 text encoders process a prompt.

        Returns tokenization, per-token embedding norms (activation strength),
        and encoder agreement (cosine similarity between encoders per token position).

        This is lightweight: one forward pass per encoder (~100ms total on GPU).
        Falls back to tokenization-only if model is not loaded.
        """
        try:
            import torch
            import torch.nn.functional as F

            result = {"model_id": model_id}

            # Check if model is loaded — if not, return tokenization only
            if model_id not in self._pipelines:
                # Try to load, but don't block if it fails
                if not await self.load_model(model_id):
                    return {"error": f"Model {model_id} not available"}

            pipe = self._pipelines[model_id]

            # Verify this is an SD3.5-style pipeline with triple encoders
            has_triple = (
                hasattr(pipe, 'tokenizer') and
                hasattr(pipe, 'tokenizer_2') and
                hasattr(pipe, 'tokenizer_3')
            )
            if not has_triple:
                return {"error": "Pipeline does not have triple text encoders (not SD3.5?)"}

            has_encoders = (
                hasattr(pipe, '_get_clip_prompt_embeds') and
                hasattr(pipe, '_get_t5_prompt_embeds')
            )

            # --- Tokenization (CPU only, always available) ---
            def _tokenize(tokenizer, name, max_len):
                tokens = tokenizer(
                    prompt,
                    padding=False,
                    truncation=False,
                    return_tensors=None,
                )
                input_ids = tokens["input_ids"]
                # Strip special tokens (SOT/EOT for CLIP, pad for T5)
                if hasattr(tokenizer, 'bos_token_id') and input_ids and input_ids[0] == tokenizer.bos_token_id:
                    input_ids = input_ids[1:]
                if hasattr(tokenizer, 'eos_token_id') and input_ids and input_ids[-1] == tokenizer.eos_token_id:
                    input_ids = input_ids[:-1]

                decoded_tokens = [tokenizer.decode([tid]) for tid in input_ids]
                count = len(input_ids)
                truncated = count > max_len

                return {
                    "tokens": decoded_tokens[:max_len],
                    "count": min(count, max_len),
                    "total_count": count,
                    "max": max_len,
                    "truncated": truncated,
                }

            clip_l_tok = _tokenize(pipe.tokenizer, "clip_l", 75)  # 77 - 2 special tokens
            clip_g_tok = _tokenize(pipe.tokenizer_2, "clip_g", 75)
            t5_tok = _tokenize(pipe.tokenizer_3, "t5", 512)

            result["clip_l"] = {**clip_l_tok, "embed_dim": 768}
            result["clip_g"] = {**clip_g_tok, "embed_dim": 1280}
            result["t5"] = {**t5_tok, "embed_dim": 4096}

            # --- Embedding analysis (GPU, only if encoders available) ---
            if has_encoders:
                self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1
                try:
                    self._model_last_used[model_id] = time.time()
                    device = pipe._execution_device

                    def _encode():
                        with torch.no_grad():
                            # CLIP-L: [1, 77, 768]
                            clip_l_embeds, _ = pipe._get_clip_prompt_embeds(
                                prompt=prompt, device=device,
                                num_images_per_prompt=1, clip_model_index=0
                            )
                            # CLIP-G: [1, 77, 1280]
                            clip_g_embeds, _ = pipe._get_clip_prompt_embeds(
                                prompt=prompt, device=device,
                                num_images_per_prompt=1, clip_model_index=1
                            )
                            # T5-XXL: [1, N, 4096]
                            t5_embeds = pipe._get_t5_prompt_embeds(
                                prompt=prompt, num_images_per_prompt=1,
                                max_sequence_length=512, device=device
                            )

                        # Per-token L2 norms (activation strength)
                        clip_l_norms = torch.norm(clip_l_embeds[0], dim=-1).cpu()  # [77]
                        clip_g_norms = torch.norm(clip_g_embeds[0], dim=-1).cpu()  # [77]
                        t5_norms = torch.norm(t5_embeds[0], dim=-1).cpu()  # [N]

                        # Normalize to [0, 1] for visualization
                        def _normalize(norms, token_count):
                            """Normalize norms for actual tokens (skip padding)."""
                            actual = norms[:token_count]
                            if actual.max() > actual.min():
                                return ((actual - actual.min()) / (actual.max() - actual.min())).tolist()
                            return [0.5] * token_count

                        clip_l_count = clip_l_tok["count"]
                        clip_g_count = clip_g_tok["count"]
                        t5_count = t5_tok["count"]

                        result["clip_l"]["token_norms"] = _normalize(clip_l_norms, clip_l_count)
                        result["clip_g"]["token_norms"] = _normalize(clip_g_norms, clip_g_count)
                        result["t5"]["token_norms"] = _normalize(t5_norms, t5_count)

                        # Encoder agreement: cosine similarity per token position
                        # Compare over shared token count (min of all encoders)
                        shared_count = min(clip_l_count, clip_g_count, t5_count)
                        if shared_count > 0:
                            # Pad CLIP embeddings to T5 dim for meaningful comparison
                            clip_l_padded = F.pad(clip_l_embeds[0, :shared_count], (0, 4096 - 768))
                            clip_g_padded = F.pad(clip_g_embeds[0, :shared_count], (0, 4096 - 1280))
                            t5_shared = t5_embeds[0, :shared_count]

                            cos = torch.nn.CosineSimilarity(dim=-1)
                            result["encoder_agreement"] = {
                                "clip_l_vs_t5": cos(clip_l_padded, t5_shared).cpu().tolist(),
                                "clip_g_vs_t5": cos(clip_g_padded, t5_shared).cpu().tolist(),
                                "clip_l_vs_clip_g": cos(
                                    F.pad(clip_l_embeds[0, :shared_count], (0, 1280 - 768)),
                                    clip_g_embeds[0, :shared_count]
                                ).cpu().tolist(),
                                "shared_positions": shared_count,
                            }

                    await asyncio.to_thread(_encode)

                finally:
                    self._model_in_use[model_id] -= 1

            logger.info(
                f"[ENCODE-INFO] clip_l={clip_l_tok['count']}/{clip_l_tok['max']}, "
                f"clip_g={clip_g_tok['count']}/{clip_g_tok['max']}, "
                f"t5={t5_tok['count']}/{t5_tok['max']}, "
                f"has_norms={'token_norms' in result.get('clip_l', {})}"
            )
            return result

        except Exception as e:
            logger.error(f"[ENCODE-INFO] Error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}


# Singleton instance
_backend: Optional[DiffusersImageGenerator] = None


def get_diffusers_backend() -> DiffusersImageGenerator:
    """
    Get Diffusers backend singleton

    Returns:
        DiffusersImageGenerator instance
    """
    global _backend
    if _backend is None:
        _backend = DiffusersImageGenerator()
    return _backend


def reset_diffusers_backend():
    """Reset the singleton backend (for testing)"""
    global _backend
    _backend = None
