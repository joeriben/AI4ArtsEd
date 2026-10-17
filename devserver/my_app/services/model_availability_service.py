"""
Model Availability Service - Multi-Backend Detection

Checks model/backend availability across all generation backends:
- ComfyUI: Queries /object_info for installed models
- The media stations (HeartMuLa, Stable Audio 3, Hunyuan3D 2): asked of ComfyUI's
  /ai4artsed/stations through their clients (until stage 6 of the move to ComfyUI
  the GPU service's availability endpoints on port 17803; the keys keep that name)
- Cloud APIs (Mammouth AI, OpenAI): available while the provider their chunk
  names holds a key; for a provider whose entry in config/llm_providers.json
  names the LiteLLM account API also one it accepts, with credit left
  (services/provider_account.py)

Each backend type is checked independently — ComfyUI being down does NOT
prevent Diffusers configs from being reported as available.
"""

import aiohttp
import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from schemas.engine.config_loader import config_is_hidden

logger = logging.getLogger(__name__)


class ModelAvailabilityService:
    """
    Service to check model/backend availability across all generation backends.

    - ComfyUI configs: Queries /object_info for installed models
    - Diffusers/HeartMuLa configs: Queries GPU service availability endpoints
    - Cloud API configs: available while their provider holds a key; for a
      provider whose entry names the LiteLLM account API also one it accepts,
      with credit left (services/provider_account.py)
    """

    # Cache for ComfyUI model queries (5-minute TTL)
    _cache: Dict[str, Any] = {
        "comfyui_models": None,
        "timestamp": None,
        "ttl_seconds": 300,  # 5 minutes
        "last_reachable": False
    }

    # Cache for GPU service availability (same TTL)
    _gpu_cache: Dict[str, Any] = {
        "diffusers_available": None,
        "heartmula_available": None,
        "hunyuan3d_available": None,
        "timestamp": None,
        "ttl_seconds": 300  # 5 minutes
    }

    def __init__(self, comfyui_base_url: Optional[str] = None):
        """
        Initialize the model availability service.

        Args:
            comfyui_base_url: Base URL for ComfyUI API (default: from config.py)
        """
        if comfyui_base_url is None:
            from config import COMFYUI_URL
            comfyui_base_url = COMFYUI_URL

        self.comfyui_base_url = comfyui_base_url
        self.config_dir = Path(__file__).parent.parent.parent / "schemas" / "configs" / "output"
        self.chunk_dir = Path(__file__).parent.parent.parent / "schemas" / "chunks"
        # The cloud configs this check found without a usable provider account,
        # so that a surface can name that cause (/api/models/availability),
        # and the provider each of them sends to, which the cause names.
        self.account_missing: set = set()
        self.account_provider: dict = {}

        logger.info(f"[MODEL_AVAILABILITY] Initialized with ComfyUI at {comfyui_base_url}")

    def _is_cache_valid(self) -> bool:
        """Check if the cached ComfyUI models data is still valid."""
        if not self._cache["timestamp"]:
            return False
        elapsed = time.time() - self._cache["timestamp"]
        return elapsed < self._cache["ttl_seconds"]

    def _get_cache_age(self) -> int:
        """Get the age of the cache in seconds."""
        if not self._cache["timestamp"]:
            return 0
        return int(time.time() - self._cache["timestamp"])

    def _is_comfyui_reachable(self) -> bool:
        """Check if the most recent ComfyUI query succeeded."""
        return self._cache["last_reachable"]

    def invalidate_caches(self):
        """Invalidate all caches (ComfyUI + GPU service). The provider account
        readings stay: this runs on ?force_refresh=true, which anyone can send,
        and it must not make this server call a provider with the operator's
        key at will (services/provider_account.py)."""
        self._cache["timestamp"] = None
        self._gpu_cache["timestamp"] = None

    def _is_gpu_cache_valid(self) -> bool:
        """Check if the cached GPU service data is still valid."""
        if not self._gpu_cache["timestamp"]:
            return False
        elapsed = time.time() - self._gpu_cache["timestamp"]
        return elapsed < self._gpu_cache["ttl_seconds"]

    async def get_gpu_service_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        The availability of HeartMuLa, Stable Audio and Hunyuan3D, asked of
        their clients (ComfyUI's stations since stage 6 of the move); the
        Diffusers flag stays False (stage 4 of the move).

        Returns:
            {
                "diffusers": False,
                "heartmula": True/False,
                "gpu_service_reachable": True/False
            }
        """
        if not force_refresh and self._is_gpu_cache_valid():
            logger.info(f"[MODEL_AVAILABILITY] Using cached GPU status")
            return {
                "diffusers": self._gpu_cache["diffusers_available"] or False,
                "heartmula": self._gpu_cache["heartmula_available"] or False,
                "stable_audio": self._gpu_cache.get("stable_audio_available") or False,
                "hunyuan3d": self._gpu_cache.get("hunyuan3d_available") or False,
                "gpu_service_reachable": bool(
                    self._gpu_cache["diffusers_available"]
                    or self._gpu_cache["heartmula_available"]
                    or self._gpu_cache.get("stable_audio_available")
                    or self._gpu_cache.get("hunyuan3d_available")
                ),
            }

        logger.info("[MODEL_AVAILABILITY] Querying GPU service availability")
        status = {
            "diffusers": False,
            "heartmula": False,
            "stable_audio": False,
            "hunyuan3d": False,
            "gpu_service_reachable": False,
        }

        # The Diffusers station is asked no more (stage 4 of the move to
        # ComfyUI): no surface offers a config that runs there, the checked
        # flag served the Diffusers twins alone, and the question was a call on
        # the old way every time a page asked for its ring. The twins read as
        # unavailable until stage 8 takes them.

        # Check HeartMuLa (the client asks ComfyUI's stations)
        try:
            from my_app.services.heartmula_client import HeartMuLaClient
            client = HeartMuLaClient()
            status["heartmula"] = await client.is_available()
            if status["heartmula"]:
                status["gpu_service_reachable"] = True
        except Exception as e:
            logger.warning(f"[MODEL_AVAILABILITY] HeartMuLa check failed: {e}")

        # Check Stable Audio (the client asks ComfyUI's stations)
        try:
            from my_app.services.stable_audio_client import StableAudioClient
            client = StableAudioClient()
            status["stable_audio"] = await client.is_available()
            if status["stable_audio"]:
                status["gpu_service_reachable"] = True
        except Exception as e:
            logger.warning(f"[MODEL_AVAILABILITY] Stable Audio check failed: {e}")

        # Check Hunyuan3D (the client asks ComfyUI's stations)
        try:
            from my_app.services.hunyuan3d_client import Hunyuan3DClient
            client = Hunyuan3DClient()
            status["hunyuan3d"] = await client.is_available()
            if status["hunyuan3d"]:
                status["gpu_service_reachable"] = True
        except Exception as e:
            logger.warning(f"[MODEL_AVAILABILITY] Hunyuan3D check failed: {e}")

        # Update cache
        self._gpu_cache["diffusers_available"] = status["diffusers"]
        self._gpu_cache["heartmula_available"] = status["heartmula"]
        self._gpu_cache["stable_audio_available"] = status.get("stable_audio", False)
        self._gpu_cache["hunyuan3d_available"] = status.get("hunyuan3d", False)
        self._gpu_cache["timestamp"] = time.time()

        logger.info(
            f"[MODEL_AVAILABILITY] GPU status: diffusers={status['diffusers']}, "
            f"heartmula={status['heartmula']}, stable_audio={status['stable_audio']}, "
            f"hunyuan3d={status['hunyuan3d']}"
        )

        return status

    async def get_comfyui_models(self, force_refresh: bool = False) -> Dict[str, List[str]]:
        """
        Query ComfyUI's /object_info endpoint to get available models.

        Args:
            force_refresh: If True, bypass cache and query fresh

        Returns:
            Dictionary with model lists:
            {
                "checkpoints": ["flux2_dev_fp8mixed.safetensors", ...],
                "unets": ["qwen_image_fp8_e4m3fn.safetensors", ...],
                "vaes": ["flux2-vae.safetensors", ...],
                "clips": ["mistral_3_small_flux2_fp8.safetensors", ...]
            }

        Raises:
            aiohttp.ClientError: If ComfyUI is unreachable or returns error
        """
        # Check cache first
        if not force_refresh and self._is_cache_valid():
            logger.info(f"[MODEL_AVAILABILITY] Using cached ComfyUI models (age: {self._get_cache_age()}s)")
            return self._cache["comfyui_models"]

        logger.info(f"[MODEL_AVAILABILITY] Querying ComfyUI at {self.comfyui_base_url}/object_info")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.comfyui_base_url}/object_info",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise aiohttp.ClientError(
                            f"ComfyUI returned status {response.status}: {error_text}"
                        )

                    data = await response.json()

                    # Extract model lists from loader node definitions
                    models = {
                        "checkpoints": [],
                        "unets": [],
                        "vaes": [],
                        "clips": []
                    }

                    # CheckpointLoaderSimple → ckpt_name
                    if "CheckpointLoaderSimple" in data:
                        ckpt_field = data["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
                        if isinstance(ckpt_field, list) and len(ckpt_field) > 0:
                            models["checkpoints"] = ckpt_field[0]

                    # UNETLoader → unet_name
                    if "UNETLoader" in data:
                        unet_field = data["UNETLoader"]["input"]["required"]["unet_name"]
                        if isinstance(unet_field, list) and len(unet_field) > 0:
                            models["unets"] = unet_field[0]

                    # VAELoader → vae_name
                    if "VAELoader" in data:
                        vae_field = data["VAELoader"]["input"]["required"]["vae_name"]
                        if isinstance(vae_field, list) and len(vae_field) > 0:
                            models["vaes"] = vae_field[0]

                    # CLIPLoader → clip_name
                    if "CLIPLoader" in data:
                        clip_field = data["CLIPLoader"]["input"]["required"]["clip_name"]
                        if isinstance(clip_field, list) and len(clip_field) > 0:
                            models["clips"] = clip_field[0]

                    logger.info(
                        f"[MODEL_AVAILABILITY] Found {len(models['checkpoints'])} checkpoints, "
                        f"{len(models['unets'])} UNETs, {len(models['vaes'])} VAEs, "
                        f"{len(models['clips'])} CLIPs"
                    )

                    # Update cache
                    self._cache["comfyui_models"] = models
                    self._cache["timestamp"] = time.time()
                    self._cache["last_reachable"] = True

                    return models

        except (aiohttp.ClientError, Exception) as e:
            logger.error(f"[MODEL_AVAILABILITY] ComfyUI unreachable: {e}")
            self._cache["last_reachable"] = False

            # Trigger auto-start via ComfyUIManager and retry once
            try:
                from my_app.services.comfyui_manager import get_comfyui_manager
                manager = get_comfyui_manager()
                if manager._auto_start_enabled and not manager.is_starting():
                    logger.info("[MODEL_AVAILABILITY] Triggering ComfyUI auto-start...")
                    started = await manager.ensure_comfyui_available()
                    if started:
                        logger.info("[MODEL_AVAILABILITY] ComfyUI started, retrying query...")
                        return await self.get_comfyui_models(force_refresh=True)
            except Exception as start_err:
                logger.warning(f"[MODEL_AVAILABILITY] ComfyUI auto-start failed: {start_err}")

            raise

    def _load_chunk_meta(self, chunk_name: str) -> dict:
        """Load chunk meta from .py (CHUNK_META) or .json (meta field).

        Python chunks take priority over JSON chunks.
        Returns the meta dict, or empty dict if not found.
        """
        # 1. Try Python chunk first
        chunk_py = self.chunk_dir / f"{chunk_name}.py"
        if chunk_py.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"avail_{chunk_name}", chunk_py)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return getattr(mod, 'CHUNK_META', {})
            except Exception as e:
                logger.debug(f"[MODEL_AVAILABILITY] Failed to load Python chunk {chunk_name}: {e}")

        # 2. Fallback to JSON
        chunk_json = self.chunk_dir / f"{chunk_name}.json"
        if chunk_json.exists():
            try:
                with open(chunk_json, 'r', encoding='utf-8') as f:
                    return json.load(f).get("meta", {})
            except Exception as e:
                logger.debug(f"[MODEL_AVAILABILITY] Failed to load JSON chunk {chunk_name}: {e}")

        return {}

    async def _check_fallback_chunk(self, config_id: str, output_chunk_name: str) -> bool:
        """Check if a chunk's fallback_chunk is available via ComfyUI.

        Loads the primary chunk, reads meta.fallback_chunk, then checks if
        ComfyUI has all models required by the fallback chunk's workflow.
        """
        try:
            # Load primary chunk meta (.py or .json)
            primary_meta = self._load_chunk_meta(output_chunk_name)
            fallback_name = primary_meta.get("fallback_chunk")
            if not fallback_name:
                return False

            # Load fallback chunk and check its models against ComfyUI
            fallback_path = self.chunk_dir / f"{fallback_name}.json"
            if not fallback_path.exists():
                # A Python fallback chunk runs on the GPU service, whose station
                # the caller has just read as unavailable. Until stage 4 of the
                # move to ComfyUI this answered True for the file's existence,
                # and four Diffusers twins reported available on a station
                # nobody asks any more.
                return False
            requirements = self._extract_chunk_requirements(fallback_path)

            if not requirements:
                # No model requirements = assume available
                return True

            available_models = await self.get_comfyui_models()

            type_map = {
                "checkpoint": "checkpoints",
                "unet": "unets",
                "vae": "vaes",
                "clip": "clips",
            }

            for req in requirements:
                model_list = available_models.get(type_map.get(req["loader_type"], ""), [])
                if req["model_name"] not in model_list:
                    logger.info(
                        f"[MODEL_AVAILABILITY] {config_id}: Fallback {fallback_name} missing "
                        f"{req['loader_type']} model '{req['model_name']}'"
                    )
                    return False

            return True

        except FileNotFoundError:
            return False
        except Exception as e:
            logger.debug(f"[MODEL_AVAILABILITY] {config_id}: Fallback check error: {e}")
            return False

    def _extract_chunk_requirements(self, chunk_path: Path) -> List[Dict[str, str]]:
        """
        Parse a chunk file to extract required models from workflow JSON.

        Args:
            chunk_path: Path to chunk JSON file

        Returns:
            List of required models:
            [
                {"loader_type": "checkpoint", "model_name": "flux2_dev_fp8mixed.safetensors"},
                {"loader_type": "clip", "model_name": "mistral_3_small_flux2_fp8.safetensors"},
                ...
            ]
        """
        try:
            with open(chunk_path, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)

            workflow = chunk_data.get("workflow", {})
            if not workflow:
                logger.warning(f"[MODEL_AVAILABILITY] No workflow found in {chunk_path.name}")
                return []

            requirements = []

            # Iterate through workflow nodes
            for node_id, node_data in workflow.items():
                class_type = node_data.get("class_type")
                inputs = node_data.get("inputs", {})

                # CheckpointLoaderSimple
                if class_type == "CheckpointLoaderSimple":
                    if "ckpt_name" in inputs:
                        requirements.append({
                            "loader_type": "checkpoint",
                            "model_name": inputs["ckpt_name"]
                        })

                # UNETLoader
                elif class_type == "UNETLoader":
                    if "unet_name" in inputs:
                        requirements.append({
                            "loader_type": "unet",
                            "model_name": inputs["unet_name"]
                        })

                # VAELoader
                elif class_type == "VAELoader":
                    if "vae_name" in inputs:
                        requirements.append({
                            "loader_type": "vae",
                            "model_name": inputs["vae_name"]
                        })

                # CLIPLoader
                elif class_type == "CLIPLoader":
                    if "clip_name" in inputs:
                        requirements.append({
                            "loader_type": "clip",
                            "model_name": inputs["clip_name"]
                        })

                # DualCLIPLoader
                elif class_type == "DualCLIPLoader":
                    if "clip_name1" in inputs:
                        requirements.append({
                            "loader_type": "clip",
                            "model_name": inputs["clip_name1"]
                        })
                    if "clip_name2" in inputs:
                        requirements.append({
                            "loader_type": "clip",
                            "model_name": inputs["clip_name2"]
                        })

                # TripleCLIPLoader
                elif class_type == "TripleCLIPLoader":
                    if "clip_name1" in inputs:
                        requirements.append({
                            "loader_type": "clip",
                            "model_name": inputs["clip_name1"]
                        })
                    if "clip_name2" in inputs:
                        requirements.append({
                            "loader_type": "clip",
                            "model_name": inputs["clip_name2"]
                        })
                    if "clip_name3" in inputs:
                        requirements.append({
                            "loader_type": "clip",
                            "model_name": inputs["clip_name3"]
                        })

            return requirements

        except FileNotFoundError:
            logger.error(f"[MODEL_AVAILABILITY] Chunk file not found: {chunk_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"[MODEL_AVAILABILITY] Invalid JSON in {chunk_path.name}: {e}")
            return []
        except Exception as e:
            logger.error(f"[MODEL_AVAILABILITY] Error parsing chunk {chunk_path.name}: {e}")
            return []


    def api_provider(self, config_id: str) -> Optional[str]:
        """The provider a config's output chunk sends its request to, or None
        for a config that runs here or whose chunk names none."""
        try:
            with open(self.config_dir / f"{config_id}.json", 'r', encoding='utf-8') as f:
                return self._api_provider_of(json.load(f))
        except Exception:
            return None

    def _api_provider_of(self, config_data: dict) -> Optional[str]:
        """`api_config.provider` of the config's output chunk, where that chunk
        is an api_output_chunk -- the type backend_router sends to a provider,
        with the key of the provider named here."""
        chunk_name = config_data.get("parameters", {}).get("OUTPUT_CHUNK")
        if not chunk_name:
            return None
        try:
            with open(self.chunk_dir / f"{chunk_name}.json", 'r', encoding='utf-8') as f:
                chunk = json.load(f)
        except Exception:
            return None
        if chunk.get("type") != "api_output_chunk":
            return None
        return (chunk.get("api_config") or {}).get("provider") or None

    async def check_config_availability(self, config_id: str) -> bool:
        """
        Check if all required models for a config are available.

        Args:
            config_id: Config ID (e.g., "flux2", "sd35_large")

        Returns:
            True if all required models are available, False otherwise
        """
        config_path = self.config_dir / f"{config_id}.json"

        try:
            # Load config
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # Skip hidden configs (incomplete stubs), read the one way
            if config_is_hidden(config_data):
                return True

            # Route availability check by backend_type
            backend_type = config_data.get("meta", {}).get("backend_type")

            if backend_type in ("diffusers", "heartmula", "stable_audio", "hunyuan3d"):
                gpu_status = await self.get_gpu_service_status()
                gpu_key = backend_type  # Keys match: "diffusers", "heartmula", "stable_audio"
                available = gpu_status.get(gpu_key, False)

                if available:
                    logger.info(f"[MODEL_AVAILABILITY] {config_id}: {backend_type} backend, available=True")
                    return True

                # Primary backend unavailable — check ComfyUI fallback via chunk meta
                output_chunk_name = config_data.get("parameters", {}).get("OUTPUT_CHUNK")
                if output_chunk_name:
                    fallback_available = await self._check_fallback_chunk(config_id, output_chunk_name)
                    if fallback_available:
                        logger.info(f"[MODEL_AVAILABILITY] {config_id}: {backend_type} unavailable, ComfyUI fallback available")
                        return True

                logger.info(f"[MODEL_AVAILABILITY] {config_id}: {backend_type} backend unavailable, no fallback")
                return False

            elif backend_type and backend_type not in ("comfyui", "comfyui_legacy"):
                # Cloud APIs and code-based backends (mammouth, openai, config_model,
                # python). A cloud config reaches its model through the provider its
                # chunk names. It is reported unavailable without a key there and,
                # for a provider whose entry names the LiteLLM account API, also
                # with a key the provider refuses, with a
                # budget used up that the provider names (budget_exceeded), or with
                # one that services/provider_account.py judges: for Gemini 3 Pro
                # Image, without a key, with a refused key, and without credit
                # (docs/DEVELOPMENT_DECISIONS.md). The code-based ones name no
                # provider and stay available. The account check is imported here,
                # in the function (tests/test_provider_account.py).
                from my_app.services import provider_account
                provider_name = self._api_provider_of(config_data)
                if provider_name and not provider_account.usable(provider_name):
                    self.account_missing.add(config_id)
                    self.account_provider[config_id] = provider_name
                    logger.info(
                        f"[MODEL_AVAILABILITY] {config_id}: no usable {provider_name} account "
                        f"(no key, key refused, or no credit), available=False"
                    )
                    return False
                logger.info(f"[MODEL_AVAILABILITY] {config_id}: {backend_type} backend, marking available")
                return True

            # Fall through to ComfyUI check for backend_type == "comfyui", "comfyui_legacy", or None

            # Extract OUTPUT_CHUNK reference
            output_chunk = config_data.get("parameters", {}).get("OUTPUT_CHUNK")
            if not output_chunk:
                logger.warning(f"[MODEL_AVAILABILITY] {config_id}: No OUTPUT_CHUNK found")
                return False

            # Load chunk and extract requirements
            chunk_path = self.chunk_dir / f"{output_chunk}.json"
            requirements = self._extract_chunk_requirements(chunk_path)

            if not requirements:
                logger.warning(f"[MODEL_AVAILABILITY] {config_id}: No model requirements found in chunk {output_chunk}")
                # If no requirements, assume available (might be a non-model chunk)
                return True

            # Get available models from ComfyUI
            available_models = await self.get_comfyui_models()

            # Check each requirement
            for req in requirements:
                loader_type = req["loader_type"]
                model_name = req["model_name"]

                # Map loader_type to the correct model list
                if loader_type == "checkpoint":
                    model_list = available_models["checkpoints"]
                elif loader_type == "unet":
                    model_list = available_models["unets"]
                elif loader_type == "vae":
                    model_list = available_models["vaes"]
                elif loader_type == "clip":
                    model_list = available_models["clips"]
                else:
                    logger.warning(f"[MODEL_AVAILABILITY] {config_id}: Unknown loader type '{loader_type}'")
                    continue

                # Check if model exists in ComfyUI's list
                if model_name not in model_list:
                    logger.info(
                        f"[MODEL_AVAILABILITY] {config_id}: Missing {loader_type} model '{model_name}'"
                    )
                    return False

            logger.info(f"[MODEL_AVAILABILITY] {config_id}: All models available")
            return True

        except FileNotFoundError:
            logger.error(f"[MODEL_AVAILABILITY] Config not found: {config_path}")
            return False
        except Exception as e:
            logger.error(f"[MODEL_AVAILABILITY] Error checking {config_id}: {e}")
            return False

    async def check_all_configs(self) -> Dict[str, bool]:
        """
        Check availability for all output configs.

        Returns:
            Dictionary mapping config_id to availability:
            {"flux2": true, "sd35_large": true, "wan22_video": false, ...}
        """
        availability = {}

        if not self.config_dir.exists():
            logger.error(f"[MODEL_AVAILABILITY] Config directory not found: {self.config_dir}")
            return availability

        # List all config files
        config_files = list(self.config_dir.glob("*.json"))
        logger.info(f"[MODEL_AVAILABILITY] Checking {len(config_files)} configs...")

        # Check each config
        for config_file in config_files:
            config_id = config_file.stem
            try:
                is_available = await self.check_config_availability(config_id)
                availability[config_id] = is_available
            except Exception as e:
                logger.error(f"[MODEL_AVAILABILITY] Error checking {config_id}: {e}")
                availability[config_id] = False

        available_count = sum(1 for v in availability.values() if v)
        logger.info(
            f"[MODEL_AVAILABILITY] Result: {available_count}/{len(availability)} configs available"
        )

        return availability
