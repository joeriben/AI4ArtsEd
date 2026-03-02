"""
Service for resolving model paths in ComfyUI installation
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List
import time

logger = logging.getLogger(__name__)


class ModelPathResolver:
    """Resolves model file paths in ComfyUI installation"""

    def __init__(self, comfyui_base: str = None, **kwargs):
        """
        Initialize the model path resolver

        Args:
            comfyui_base: Base path to ComfyUI installation
        """
        self.comfyui_base = Path(comfyui_base) if comfyui_base else None

        # Model directory
        self.comfyui_models_dir = "models"  # Lowercase m

        # Cache for resolved paths
        self.model_cache: Dict[str, Optional[str]] = {}

        # Common subdirectories to check
        self.common_subdirs = [
            "",  # Root models directory
            "Stable-diffusion",
            "checkpoints",
            "unet",
            "diffusers",
            "vae",
            "loras",
            "embeddings"
        ]

        # Flag to track if we've logged missing base paths
        self._logged_missing_paths = False

    def _is_valid_model_path(self, path: str) -> bool:
        """Check if the given path is already a valid model path"""
        if not path:
            return False

        # If it contains path separators, assume it's already a path
        if "/" in path or "\\" in path:
            return True

        return False

    def _check_quick_paths(self, model_name: str) -> Optional[str]:
        """Check common/standard paths without recursive search"""
        quick_paths = []

        if self.comfyui_base and self.comfyui_base.exists():
            comfyui_models = self.comfyui_base / self.comfyui_models_dir
            for subdir in self.common_subdirs:
                if subdir:
                    quick_paths.append(comfyui_models / subdir / model_name)
                else:
                    quick_paths.append(comfyui_models / model_name)

        # Check each path
        for path in quick_paths:
            if path.exists() and path.is_file():
                resolved = str(path.resolve())
                logger.debug(f"Found model at: {resolved}")
                return resolved

        return None

    def _deep_search_model(self, model_name: str) -> Optional[str]:
        """Recursively search for model in all subdirectories"""
        search_roots = []

        if self.comfyui_base and self.comfyui_base.exists():
            comfyui_models = self.comfyui_base / self.comfyui_models_dir
            if comfyui_models.exists():
                search_roots.append(comfyui_models)

        # Search in each root
        for root in search_roots:
            logger.debug(f"Deep searching in: {root}")
            try:
                for path in root.rglob(model_name):
                    if path.is_file():
                        resolved = str(path.resolve())
                        logger.info(f"Found model via deep search: {resolved}")
                        return resolved
            except Exception as e:
                logger.warning(f"Error during deep search in {root}: {e}")

        return None

    def find_model(self, model_name: str) -> Optional[str]:
        """
        Find a model file by name, with caching and optimized search

        Args:
            model_name: Name of the model file (e.g., "512-inpainting-ema.safetensors")

        Returns:
            Full path to the model file, or None if not found
        """
        if not model_name:
            return None

        # Log missing base paths only once
        if not self._logged_missing_paths:
            if not self.comfyui_base:
                logger.warning("ComfyUI base path not configured")
            self._logged_missing_paths = True

        # 1. Check if it's already a valid path
        if self._is_valid_model_path(model_name):
            logger.debug(f"Model name '{model_name}' is already a path")
            return model_name

        # 2. Check cache
        if model_name in self.model_cache:
            cached_path = self.model_cache[model_name]
            if cached_path and Path(cached_path).exists():
                logger.debug(f"Using cached path for {model_name}: {cached_path}")
                return cached_path
            else:
                # Invalid cache entry, remove it
                del self.model_cache[model_name]

        # 3. Try quick paths first (standard locations)
        start_time = time.time()
        quick_result = self._check_quick_paths(model_name)
        if quick_result:
            self.model_cache[model_name] = quick_result
            logger.info(f"Found {model_name} in standard location ({time.time() - start_time:.2f}s)")
            return quick_result

        # 4. Deep search as last resort
        logger.info(f"Model {model_name} not in standard locations, starting deep search...")
        deep_result = self._deep_search_model(model_name)
        if deep_result:
            self.model_cache[model_name] = deep_result
            logger.info(f"Found {model_name} via deep search ({time.time() - start_time:.2f}s)")
            return deep_result

        # 5. Not found
        logger.warning(f"Model {model_name} not found in any location ({time.time() - start_time:.2f}s)")
        self.model_cache[model_name] = None  # Cache negative result
        return None

    def clear_cache(self):
        """Clear the model path cache"""
        self.model_cache.clear()
        logger.info("Model path cache cleared")

    def get_cache_info(self) -> Dict[str, int]:
        """Get information about the cache"""
        return {
            "size": len(self.model_cache),
            "hits": sum(1 for v in self.model_cache.values() if v is not None),
            "misses": sum(1 for v in self.model_cache.values() if v is None)
        }


# Singleton instance will be created in workflow_logic_service after config is loaded
