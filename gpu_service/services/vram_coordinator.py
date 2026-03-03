"""
VRAM Coordinator - Central VRAM management for all GPU backends

Session 175: Enables bidirectional cross-backend eviction without loops.

Architecture:
                    ┌─────────────────────┐
                    │  VRAMCoordinator    │
                    │  (Singleton)        │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
    │ DiffusersBackend│ │ TextBackend │ │ HeartMuLaBackend│
    │ (image/video)   │ │ (LLM)       │ │ (music)         │
    └─────────────────┘ └─────────────┘ └─────────────────┘

Key Features:
- Backends register with the coordinator
- `request_vram()` triggers cross-backend LRU eviction
- Priority system prevents evicting in-use models
- Central coordination prevents eviction loops
"""

import gc
import logging
import threading
import time
from typing import Optional, Dict, List, Any, Callable, Protocol
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)


class EvictionPriority(IntEnum):
    """
    Higher priority = harder to evict.

    When Backend A (prio 2) needs VRAM and Backend B (prio 1) has models,
    A can evict B's models.

    Same priority: LRU decides.
    """
    LOW = 1       # Cache, previews, temporary models
    NORMAL = 2    # Standard models (SD3.5, Llama, etc.)
    HIGH = 3      # Currently in-use models (in_use > 0)
    CRITICAL = 4  # Never evict (system-critical)


@dataclass
class RegisteredModel:
    """Info about a registered model."""
    backend_id: str
    model_id: str
    vram_mb: float
    priority: EvictionPriority
    last_used: float
    in_use: int  # Refcount


class VRAMBackend(Protocol):
    """Protocol that backends must implement for VRAM coordination."""

    def get_registered_models(self) -> List[Dict[str, Any]]:
        """Return list of models with vram_mb, priority, last_used, in_use."""
        ...

    def evict_model(self, model_id: str) -> bool:
        """Evict a specific model. Returns True if successful."""
        ...

    def get_backend_id(self) -> str:
        """Unique identifier for this backend."""
        ...


class VRAMCoordinator:
    """
    Central VRAM management.

    Backends register here and report model loads/unloads.
    When VRAM is needed, the coordinator decides who gets evicted.
    """

    def __init__(self):
        self._backends: Dict[str, VRAMBackend] = {}
        self._request_lock = threading.Lock()
        self._eviction_in_progress = False

        # Cache for fast VRAM queries
        self._last_vram_check: float = 0
        self._cached_free_mb: float = 0
        self._cache_ttl_ms: float = 100  # 100ms cache

        logger.info("[VRAM-COORD] Initialized")

    def register_backend(self, backend: VRAMBackend) -> None:
        """Register a backend for VRAM coordination."""
        backend_id = backend.get_backend_id()
        self._backends[backend_id] = backend
        logger.info(f"[VRAM-COORD] Registered backend: {backend_id}")

    def unregister_backend(self, backend_id: str) -> None:
        """Unregister a backend."""
        if backend_id in self._backends:
            del self._backends[backend_id]
            logger.info(f"[VRAM-COORD] Unregistered backend: {backend_id}")

    def get_free_vram_mb(self, use_cache: bool = True) -> float:
        """Get currently free VRAM in MB."""
        import torch

        now = time.time() * 1000
        if use_cache and (now - self._last_vram_check) < self._cache_ttl_ms:
            return self._cached_free_mb

        if not torch.cuda.is_available():
            return 0

        total = torch.cuda.get_device_properties(0).total_memory
        allocated = torch.cuda.memory_allocated(0)
        free_mb = (total - allocated) / (1024 * 1024)

        self._cached_free_mb = free_mb
        self._last_vram_check = now
        return free_mb

    def get_total_vram_mb(self) -> float:
        """Get total VRAM in MB."""
        import torch
        if not torch.cuda.is_available():
            return 0
        return torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)

    def request_vram(
        self,
        requester_id: str,
        required_mb: float,
        requester_priority: EvictionPriority = EvictionPriority.NORMAL
    ) -> bool:
        """
        Request VRAM, evicting other models if necessary.

        Args:
            requester_id: Backend ID making the request
            required_mb: How much VRAM is needed
            requester_priority: Priority of the requesting operation

        Returns:
            True if enough VRAM is now available

        Eviction Strategy:
        1. Only evict models with priority <= requester_priority (same tier: LRU)
        2. Among evictable models, use LRU order
        3. Never evict models with in_use > 0 (elevated to HIGH priority)
        4. Stop when enough VRAM is free
        """
        with self._request_lock:
            if self._eviction_in_progress:
                logger.warning(f"[VRAM-COORD] Eviction already in progress, {requester_id} waiting")
                # Could implement queue here, for now just proceed

            self._eviction_in_progress = True

            try:
                return self._do_eviction(requester_id, required_mb, requester_priority)
            finally:
                self._eviction_in_progress = False

    def _collect_all_models(self) -> List[RegisteredModel]:
        """Collect model info from all backends."""
        all_models = []

        for backend_id, backend in self._backends.items():
            try:
                models = backend.get_registered_models()
                for m in models:
                    # Determine effective priority (in_use elevates to HIGH)
                    base_priority = m.get("priority", EvictionPriority.NORMAL)
                    in_use = m.get("in_use", 0)
                    effective_priority = EvictionPriority.HIGH if in_use > 0 else base_priority

                    all_models.append(RegisteredModel(
                        backend_id=backend_id,
                        model_id=m["model_id"],
                        vram_mb=m.get("vram_mb", 0),
                        priority=effective_priority,
                        last_used=m.get("last_used", 0),
                        in_use=in_use,
                    ))
            except Exception as e:
                logger.error(f"[VRAM-COORD] Failed to get models from {backend_id}: {e}")

        return all_models

    def _do_eviction(
        self,
        requester_id: str,
        required_mb: float,
        requester_priority: EvictionPriority
    ) -> bool:
        """
        Core eviction logic.

        Returns True if enough VRAM is available after eviction.
        """
        import torch

        free_mb = self.get_free_vram_mb(use_cache=False)
        is_inf = required_mb == float('inf')

        if not is_inf and free_mb >= required_mb:
            logger.debug(f"[VRAM-COORD] {requester_id}: Already have {free_mb:.0f}MB >= {required_mb:.0f}MB")
            return True

        needed_str = "max available" if is_inf else f"{required_mb:.0f}MB"
        logger.info(
            f"[VRAM-COORD] {requester_id} needs {needed_str}, "
            f"have {free_mb:.0f}MB, starting eviction"
        )

        # Collect all models from all backends
        all_models = self._collect_all_models()

        # Filter evictable models:
        # - priority <= requester_priority (same priority: LRU decides)
        # - in_use == 0 (not currently being used; in_use > 0 elevated to HIGH)
        # Note: We CAN evict from the same backend (requester evicting its own old models)
        evictable = [
            m for m in all_models
            if m.priority <= requester_priority
            and m.in_use == 0
        ]

        # Sort by priority (lowest first), then by last_used (oldest first)
        evictable.sort(key=lambda m: (m.priority, m.last_used))

        evicted_count = 0
        evicted_mb = 0

        for model in evictable:
            if not is_inf and free_mb >= required_mb:
                break

            logger.info(
                f"[VRAM-COORD] Evicting {model.backend_id}/{model.model_id} "
                f"({model.vram_mb:.0f}MB, priority={model.priority.name})"
            )

            try:
                backend = self._backends.get(model.backend_id)
                if backend and backend.evict_model(model.model_id):
                    evicted_count += 1
                    evicted_mb += model.vram_mb

                    # Break circular refs, then release CUDA memory
                    gc.collect()
                    torch.cuda.empty_cache()
                    free_mb = self.get_free_vram_mb(use_cache=False)
            except Exception as e:
                logger.error(f"[VRAM-COORD] Eviction failed: {e}")

        # Final check
        free_mb = self.get_free_vram_mb(use_cache=False)

        if is_inf:
            # Unknown model size: success if we freed something or nothing to free
            success = evicted_count > 0 or len(evictable) == 0
        else:
            success = free_mb >= required_mb

        logger.info(
            f"[VRAM-COORD] Eviction complete: evicted {evicted_count} models "
            f"({evicted_mb:.0f}MB), now have {free_mb:.0f}MB, "
            f"needed {needed_str}, success={success}"
        )

        return success

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status for debugging/API."""
        all_models = self._collect_all_models()

        return {
            "free_mb": self.get_free_vram_mb(),
            "total_mb": self.get_total_vram_mb(),
            "registered_backends": list(self._backends.keys()),
            "loaded_models": [
                {
                    "backend": m.backend_id,
                    "model": m.model_id,
                    "vram_mb": m.vram_mb,
                    "priority": m.priority.name,
                    "in_use": m.in_use,
                    "last_used": m.last_used,
                }
                for m in all_models
            ],
            "eviction_in_progress": self._eviction_in_progress,
        }


# =============================================================================
# Singleton
# =============================================================================

_coordinator: Optional[VRAMCoordinator] = None


def get_vram_coordinator() -> VRAMCoordinator:
    """Get VRAMCoordinator singleton."""
    global _coordinator
    if _coordinator is None:
        _coordinator = VRAMCoordinator()
    return _coordinator


def reset_vram_coordinator():
    """Reset singleton (for testing)."""
    global _coordinator
    _coordinator = None
