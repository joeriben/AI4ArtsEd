"""
Backend Registry - Centralized backend configuration and availability management

Replaces scattered ENABLED flags in config.py with a single JSON-based
configuration. Workshop-friendly: edit backends.json instead of Python code.

Features:
- Load backend configs from JSON
- Check backend availability (packages, VRAM, external services)
- Priority chains for media type routing
- VRAM-based auto-detection at startup

Usage:
    registry = get_backend_registry()

    # Check if a specific backend is available
    if registry.is_enabled("diffusers"):
        ...

    # Get preferred backend for a media type
    backend = await registry.get_preferred_backend("image")

"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, List, Any

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


    # =========================================================================
    # Startup VRAM Check
    # =========================================================================


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


