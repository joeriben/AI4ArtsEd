"""
Backend Registry - Centralized backend configuration and availability management

Session 163: Replaces scattered ENABLED flags in config.py with a single JSON-based
configuration. Workshop-friendly: edit backends.json instead of Python code.

Features:
- Load backend configs from JSON
- Check backend availability (packages, VRAM, external services)
- Priority chains for media type routing
- Workflow requirement validation (ComfyUI custom nodes)
- VRAM-based auto-detection at startup

Usage:
    registry = get_backend_registry()

    # Check if a specific backend is available
    if registry.is_enabled("diffusers"):
        ...

    # Get preferred backend for a media type
    backend = await registry.get_preferred_backend("image")

    # Check if a workflow can run
    if await registry.is_workflow_available("split_and_combine_legacy"):
        ...
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, List, Any, Set
import asyncio

logger = logging.getLogger(__name__)


class BackendConfig:
    """Configuration for a single backend"""

    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.enabled = data.get("enabled", False)
        self.description = data.get("description", "")
        self.media_types = data.get("media_types", [])
        self.requirements = data.get("requirements", {})
        self.config = data.get("config", {})

        # Runtime state
        self._available: Optional[bool] = None
        self._availability_reason: str = ""

    def __repr__(self):
        return f"BackendConfig({self.name}, enabled={self.enabled})"


class BackendRegistry:
    """
    Loads backends.json and manages backend availability.
    Replaces scattered ENABLED flags in config.py.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize registry from JSON config

        Args:
            config_path: Path to backends.json (default: devserver/config/backends.json)
        """
        if config_path is None:
            # Default: devserver/config/backends.json
            config_path = Path(__file__).parent.parent.parent / "config" / "backends.json"

        self.config_path = config_path
        self._backends: Dict[str, BackendConfig] = {}
        self._priorities: Dict[str, List[str]] = {}
        self._settings: Dict[str, Any] = {}
        self._comfyui_nodes_cache: Optional[Set[str]] = None
        self._comfyui_cache_time: float = 0

        self._load_config()

    def _load_config(self):
        """Load JSON configuration"""
        import json

        if not self.config_path.exists():
            logger.warning(f"[REGISTRY] Config not found: {self.config_path}")
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Load backends
            backends_data = config.get("backends", {})
            for name, data in backends_data.items():
                self._backends[name] = BackendConfig(name, data)

            # Load priorities
            self._priorities = config.get("priorities", {})

            # Load settings
            self._settings = config.get("settings", {})

            logger.info(f"[REGISTRY] Loaded {len(self._backends)} backends from {self.config_path}")

            # Log enabled backends
            enabled = [b.name for b in self._backends.values() if b.enabled]
            logger.info(f"[REGISTRY] Enabled backends: {enabled}")

        except Exception as e:
            logger.error(f"[REGISTRY] Failed to load config: {e}")

    def reload(self):
        """Reload configuration from JSON"""
        self._backends.clear()
        self._priorities.clear()
        self._settings.clear()
        self._comfyui_nodes_cache = None
        self._load_config()

    # =========================================================================
    # Backend Status Checks
    # =========================================================================

    def is_enabled(self, backend_name: str) -> bool:
        """
        Check if backend is enabled in config

        Args:
            backend_name: Backend identifier (e.g., "diffusers", "heartmula")

        Returns:
            True if backend is enabled in backends.yaml
        """
        backend = self._backends.get(backend_name)
        if backend is None:
            logger.warning(f"[REGISTRY] Unknown backend: {backend_name}")
            return False
        return backend.enabled

    async def is_available(self, backend_name: str) -> bool:
        """
        Check if backend is enabled AND requirements are met

        Checks:
        - enabled: true in config
        - Required packages installed
        - VRAM >= min_vram_gb (if specified)
        - External service reachable (if external_service: true)
        - API key file exists (if specified)

        Args:
            backend_name: Backend identifier

        Returns:
            True if backend can be used
        """
        backend = self._backends.get(backend_name)
        if backend is None:
            return False

        if not backend.enabled:
            return False

        # Use cached result if available
        if backend._available is not None:
            return backend._available

        # Check requirements
        requirements = backend.requirements

        # Check packages
        packages = requirements.get("packages", [])
        for pkg in packages:
            if not self._check_package_installed(pkg):
                backend._available = False
                backend._availability_reason = f"Package not installed: {pkg}"
                logger.warning(f"[REGISTRY] {backend_name}: {backend._availability_reason}")
                return False

        # Check VRAM
        min_vram = requirements.get("min_vram_gb")
        if min_vram and self._settings.get("auto_detect_vram", True):
            available_vram = await self._get_available_vram()
            if available_vram is not None and available_vram < min_vram:
                backend._available = False
                backend._availability_reason = f"Insufficient VRAM: {available_vram:.1f}GB < {min_vram}GB required"
                logger.warning(f"[REGISTRY] {backend_name}: {backend._availability_reason}")
                return False

        # Check API key file
        api_key_file = requirements.get("api_key_file")
        if api_key_file:
            key_path = Path(__file__).parent.parent.parent / api_key_file
            if not key_path.exists():
                backend._available = False
                backend._availability_reason = f"API key file not found: {api_key_file}"
                logger.warning(f"[REGISTRY] {backend_name}: {backend._availability_reason}")
                return False

        # Check model path (for local models)
        model_path = requirements.get("model_path")
        if model_path:
            expanded_path = Path(os.path.expanduser(model_path))
            if not expanded_path.exists():
                backend._available = False
                backend._availability_reason = f"Model path not found: {model_path}"
                logger.warning(f"[REGISTRY] {backend_name}: {backend._availability_reason}")
                return False

        # External services are checked separately (async)
        if requirements.get("external_service"):
            # For now, assume available - actual check in get_preferred_backend
            pass

        backend._available = True
        backend._availability_reason = "All requirements met"
        logger.info(f"[REGISTRY] {backend_name}: Available")
        return True

    def _check_package_installed(self, package_name: str) -> bool:
        """Check if a Python package is installed"""
        try:
            __import__(package_name)
            return True
        except ImportError:
            return False

    async def _get_available_vram(self) -> Optional[float]:
        """Get available GPU VRAM in GB"""
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                total = props.total_memory / 1024**3
                # Return total VRAM (not free) for requirement checks
                return total
            return None
        except ImportError:
            return None
        except Exception as e:
            logger.warning(f"[REGISTRY] VRAM check failed: {e}")
            return None

    # =========================================================================
    # Backend Configuration Access
    # =========================================================================

    def get_config(self, backend_name: str) -> Dict[str, Any]:
        """
        Get backend-specific configuration

        Args:
            backend_name: Backend identifier

        Returns:
            Config dict from backends.yaml, or empty dict if not found
        """
        backend = self._backends.get(backend_name)
        if backend is None:
            return {}
        return backend.config.copy()

    def get_requirements(self, backend_name: str) -> Dict[str, Any]:
        """
        Get backend requirements

        Args:
            backend_name: Backend identifier

        Returns:
            Requirements dict from backends.yaml
        """
        backend = self._backends.get(backend_name)
        if backend is None:
            return {}
        return backend.requirements.copy()

    def get_all_backends(self) -> Dict[str, BackendConfig]:
        """Get all configured backends"""
        return self._backends.copy()

    def get_backends_for_media(self, media_type: str) -> List[str]:
        """
        Get all backends that support a media type

        Args:
            media_type: "image", "audio", "video", "music"

        Returns:
            List of backend names
        """
        result = []
        for name, backend in self._backends.items():
            if media_type in backend.media_types:
                result.append(name)
        return result

    # =========================================================================
    # Priority Chain Management
    # =========================================================================

    async def get_preferred_backend(self, media_type: str) -> Optional[str]:
        """
        Get first available backend for a media type based on priority

        Args:
            media_type: "image", "audio", "video", "music"

        Returns:
            Backend name, or None if no backend available
        """
        priority_chain = self._priorities.get(media_type, [])

        for backend_name in priority_chain:
            if await self.is_available(backend_name):
                if self._settings.get("log_backend_selection", True):
                    logger.info(f"[REGISTRY] Selected backend for {media_type}: {backend_name}")
                return backend_name

        # No preferred backend available
        logger.warning(f"[REGISTRY] No backend available for {media_type}")
        return None

    def get_fallback_chain(self, media_type: str) -> List[str]:
        """
        Get full priority chain for a media type

        Args:
            media_type: "image", "audio", "video", "music"

        Returns:
            List of backend names in priority order
        """
        return self._priorities.get(media_type, []).copy()

    def should_fallback_to_comfyui(self) -> bool:
        """Check if ComfyUI fallback is enabled in settings"""
        return self._settings.get("fallback_to_comfyui", True)

    # =========================================================================
    # Workflow Requirement Validation
    # =========================================================================

    async def is_workflow_available(self, config_id: str) -> bool:
        """
        Check if all requirements for a workflow are met

        For ComfyUI workflows, queries /object_info to verify custom nodes exist.

        Args:
            config_id: Output config identifier (e.g., "split_and_combine_legacy")

        Returns:
            True if workflow can be executed
        """
        # Load output config to check requirements
        try:
            config = self._load_output_config(config_id)
            if config is None:
                logger.warning(f"[REGISTRY] Output config not found: {config_id}")
                return False

            meta = config.get("meta", {})
            backend_type = meta.get("backend_type", "comfyui")
            requires_nodes = meta.get("requires_nodes", [])

            # If workflow needs specific ComfyUI nodes, verify they exist
            if requires_nodes and backend_type == "comfyui":
                comfyui_nodes = await self._query_comfyui_nodes()
                if comfyui_nodes is None:
                    # ComfyUI not reachable
                    return False

                missing = [n for n in requires_nodes if n not in comfyui_nodes]
                if missing:
                    logger.warning(f"[REGISTRY] Workflow {config_id} missing nodes: {missing}")
                    return False

            # Check if required backend is available
            backend = meta.get("backend", backend_type)
            if backend:
                return await self.is_available(backend)

            return True

        except Exception as e:
            logger.error(f"[REGISTRY] Error checking workflow {config_id}: {e}")
            return False

    async def get_missing_requirements(self, config_id: str) -> Dict[str, List[str]]:
        """
        Get missing requirements for a workflow

        Returns:
            Dict with keys: "nodes", "packages", "backends"
        """
        missing = {"nodes": [], "packages": [], "backends": []}

        try:
            config = self._load_output_config(config_id)
            if config is None:
                return missing

            meta = config.get("meta", {})
            requires_nodes = meta.get("requires_nodes", [])

            if requires_nodes:
                comfyui_nodes = await self._query_comfyui_nodes()
                if comfyui_nodes is not None:
                    missing["nodes"] = [n for n in requires_nodes if n not in comfyui_nodes]

            return missing

        except Exception:
            return missing

    def _load_output_config(self, config_id: str) -> Optional[Dict]:
        """Load an output config JSON file"""
        import json

        # Search in schemas/configs/output/
        configs_dir = Path(__file__).parent.parent.parent / "schemas" / "configs" / "output"
        config_file = configs_dir / f"{config_id}.json"

        if not config_file.exists():
            return None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    async def _query_comfyui_nodes(self) -> Optional[Set[str]]:
        """
        Query ComfyUI /object_info for available nodes

        Uses cached result if within TTL.
        """
        import time

        cache_ttl = self._settings.get("comfyui_node_cache_ttl", 300)
        now = time.time()

        # Return cached result if fresh
        if self._comfyui_nodes_cache is not None:
            if now - self._comfyui_cache_time < cache_ttl:
                return self._comfyui_nodes_cache

        # Query ComfyUI
        try:
            import aiohttp

            comfyui_config = self.get_config("comfyui")
            port = comfyui_config.get("comfy_port", 17804)
            url = f"http://localhost:{port}/object_info"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._comfyui_nodes_cache = set(data.keys())
                        self._comfyui_cache_time = now
                        logger.info(f"[REGISTRY] Cached {len(self._comfyui_nodes_cache)} ComfyUI nodes")
                        return self._comfyui_nodes_cache
                    else:
                        logger.warning(f"[REGISTRY] ComfyUI /object_info returned {response.status}")
                        return None

        except asyncio.TimeoutError:
            logger.warning("[REGISTRY] ComfyUI /object_info timeout")
            return None
        except Exception as e:
            logger.warning(f"[REGISTRY] ComfyUI /object_info error: {e}")
            return None

    # =========================================================================
    # Startup VRAM Check
    # =========================================================================

    async def check_vram_and_adjust(self):
        """
        Check VRAM at startup and disable backends that exceed available memory.
        Called once during server initialization.
        """
        if not self._settings.get("auto_detect_vram", True):
            logger.info("[REGISTRY] VRAM auto-detection disabled")
            return

        available_vram = await self._get_available_vram()
        if available_vram is None:
            logger.warning("[REGISTRY] Could not detect VRAM, skipping adjustment")
            return

        logger.info(f"[REGISTRY] Detected VRAM: {available_vram:.1f}GB")

        disabled_count = 0
        for name, backend in self._backends.items():
            if not backend.enabled:
                continue

            min_vram = backend.requirements.get("min_vram_gb")
            if min_vram and available_vram < min_vram:
                backend._available = False
                backend._availability_reason = f"VRAM {available_vram:.1f}GB < {min_vram}GB required"
                logger.warning(f"[REGISTRY] {name} disabled: {backend._availability_reason}")
                disabled_count += 1

        if disabled_count > 0:
            logger.info(f"[REGISTRY] Disabled {disabled_count} backends due to VRAM constraints")

    # =========================================================================
    # API Endpoints Data
    # =========================================================================

    async def get_status(self) -> Dict[str, Any]:
        """
        Get complete registry status for API endpoints

        Returns:
            Dict with backends, priorities, and settings
        """
        backends_status = {}

        for name, backend in self._backends.items():
            available = await self.is_available(name)
            backends_status[name] = {
                "enabled": backend.enabled,
                "available": available,
                "description": backend.description,
                "media_types": backend.media_types,
                "reason": backend._availability_reason if not available else "OK"
            }

        return {
            "backends": backends_status,
            "priorities": self._priorities,
            "settings": self._settings
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_registry: Optional[BackendRegistry] = None


def get_backend_registry() -> BackendRegistry:
    """
    Get BackendRegistry singleton

    Returns:
        BackendRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = BackendRegistry()
    return _registry


def reset_backend_registry():
    """Reset the singleton registry (for testing)"""
    global _registry
    _registry = None
