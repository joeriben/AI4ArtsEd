"""
VRAM Coordinator - Central VRAM management for all GPU backends

Session 175: Enables bidirectional cross-backend eviction without loops.
Session 244: NVML integration for real GPU visibility (foreign processes, zombies).

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
- NVML: sees ALL GPU processes (Ollama, ComfyUI, zombies)
- Dynamic threshold: expected foreign VRAM adapts to Ollama/ComfyUI state
- Port blacklist: detects SwarmUI zombies on forbidden ports
"""

import gc
import logging
import os
import socket
import threading
import time
import urllib.request
import json
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

        # NVML state
        self._nvml_handle = None
        self._nvml_available = False

        # Warning cooldown
        self._last_foreign_warn_time: float = 0

        # Initialize NVML
        self._init_nvml()

        logger.info("[VRAM-COORD] Initialized")

        # Startup VRAM scan (after NVML init)
        self._log_startup_vram()

    # =========================================================================
    # NVML Integration
    # =========================================================================

    def _init_nvml(self) -> None:
        """One-time NVML init. Fail-open if nvidia-ml-py missing."""
        from config import VRAM_USE_NVML

        if not VRAM_USE_NVML:
            logger.info("[VRAM-COORD] NVML disabled by config")
            return

        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._nvml_available = True
            logger.info("[VRAM-COORD] NVML initialized — real GPU memory visibility enabled")
        except ImportError:
            logger.warning("[VRAM-COORD] nvidia-ml-py not installed — using PyTorch-only VRAM (blind to foreign processes)")
        except Exception as e:
            logger.warning(f"[VRAM-COORD] NVML init failed: {e} — using PyTorch-only VRAM")

    def _get_nvml_memory_info(self) -> Optional[Dict[str, Any]]:
        """
        Get real GPU memory info via NVML.

        Returns dict with total_mb, used_mb, free_mb, foreign_mb, processes[].
        Returns None on failure (fail-open).
        """
        if not self._nvml_available or self._nvml_handle is None:
            return None

        try:
            import pynvml

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
            total_mb = mem_info.total / (1024 * 1024)
            used_mb = mem_info.used / (1024 * 1024)
            free_mb = mem_info.free / (1024 * 1024)

            # Get all GPU processes
            our_pid = os.getpid()
            processes = []

            try:
                gpu_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(self._nvml_handle)
            except Exception:
                gpu_procs = []

            foreign_mb = 0
            for proc in gpu_procs:
                pid = proc.pid
                vram_mb = (proc.usedGpuMemory or 0) / (1024 * 1024)
                is_foreign = pid != our_pid
                cmdline = self._read_proc_cmdline(pid)

                if is_foreign:
                    foreign_mb += vram_mb

                processes.append({
                    "pid": pid,
                    "vram_mb": round(vram_mb, 1),
                    "foreign": is_foreign,
                    "cmdline": cmdline,
                })

            return {
                "total_mb": round(total_mb, 1),
                "used_mb": round(used_mb, 1),
                "free_mb": round(free_mb, 1),
                "foreign_mb": round(foreign_mb, 1),
                "processes": processes,
            }

        except Exception as e:
            logger.warning(f"[VRAM-COORD] NVML memory query failed: {e}")
            return None

    @staticmethod
    def _read_proc_cmdline(pid: int) -> str:
        """Read /proc/{pid}/cmdline. Returns '(unknown)' on failure."""
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                raw = f.read(512)
            return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        except Exception:
            return "(unknown)"

    def _get_expected_foreign_vram_mb(self) -> float:
        """
        Dynamic threshold: how much foreign VRAM is expected.

        Queries Ollama /api/ps + checks ComfyUI port + adds driver overhead.
        Adapts automatically when safety models change or services start/stop.
        """
        from config import VRAM_FOREIGN_OVERHEAD_MB, OLLAMA_API_URL, COMFYUI_PORT

        expected = VRAM_FOREIGN_OVERHEAD_MB  # Base: CUDA contexts + driver + display

        # Query Ollama for loaded models
        try:
            req = urllib.request.Request(f"{OLLAMA_API_URL}/api/ps", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                for model in data.get("models", []):
                    size_vram = model.get("size_vram", 0)
                    expected += size_vram / (1024 * 1024)  # bytes → MB
        except Exception:
            pass  # Ollama unreachable → assume 0, still add overhead

        # Check if expected ComfyUI is running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", COMFYUI_PORT))
            sock.close()
            if result == 0:
                expected += 1024  # Generous estimate for idle ComfyUI
        except Exception:
            pass

        return expected

    def _check_foreign_processes(self, nvml_info: Dict[str, Any]) -> None:
        """
        Compare actual foreign VRAM vs expected.
        Warns (with 60s cooldown) if unexpected foreign VRAM detected.
        """
        now = time.time()
        if now - self._last_foreign_warn_time < 60:
            return

        actual_foreign_mb = nvml_info.get("foreign_mb", 0)
        expected_foreign_mb = self._get_expected_foreign_vram_mb()

        if actual_foreign_mb > expected_foreign_mb:
            delta = actual_foreign_mb - expected_foreign_mb
            self._last_foreign_warn_time = now
            logger.warning(
                f"[VRAM-COORD] Foreign VRAM {actual_foreign_mb:.0f}MB exceeds "
                f"expected {expected_foreign_mb:.0f}MB by {delta:.0f}MB"
            )
            for proc in nvml_info.get("processes", []):
                if proc["foreign"]:
                    logger.warning(
                        f"[VRAM-COORD]   Foreign: PID {proc['pid']} "
                        f"({proc['vram_mb']:.0f}MB): {proc['cmdline']}"
                    )

    def _check_blacklisted_ports(self) -> List[Dict[str, Any]]:
        """
        Check if any blacklisted ports (SwarmUI zombies) are active.
        Returns list of active blacklisted port info.
        """
        from config import VRAM_BLACKLISTED_PORTS

        active = []
        for port in VRAM_BLACKLISTED_PORTS:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()
                if result == 0:
                    # Port is active — try to find the PID
                    pid, cmdline = self._find_pid_for_port(port)
                    entry = {"port": port, "pid": pid, "cmdline": cmdline}
                    active.append(entry)
                    logger.warning(
                        f"[VRAM-COORD] BLACKLISTED PORT {port} ACTIVE — "
                        f"AI Lab destabilization detected!"
                    )
                    if pid:
                        logger.warning(
                            f"[VRAM-COORD]   PID {pid} on port {port}: {cmdline}"
                        )
                        logger.warning(
                            f'[VRAM-COORD]   Terminate via: POST /api/health/kill-foreign '
                            f'{{"pid": {pid}}}'
                        )
            except Exception:
                pass

        return active

    @staticmethod
    def _find_pid_for_port(port: int) -> tuple:
        """Find PID listening on a port via psutil. Returns (pid, cmdline) or (None, '')."""
        try:
            import psutil
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr.port == port and conn.status == "LISTEN":
                    try:
                        proc = psutil.Process(conn.pid)
                        return conn.pid, " ".join(proc.cmdline())
                    except Exception:
                        return conn.pid, "(unknown)"
        except Exception:
            pass
        return None, ""

    def _log_startup_vram(self) -> None:
        """One-time startup scan: log VRAM state + processes + blacklisted ports."""
        nvml_info = self._get_nvml_memory_info()
        if nvml_info is None:
            logger.info("[VRAM-COORD] Startup: NVML not available, skipping detailed scan")
            return

        logger.info(
            f"[VRAM-COORD] Startup VRAM: total={nvml_info['total_mb']:.0f}MB, "
            f"used={nvml_info['used_mb']:.0f}MB, free={nvml_info['free_mb']:.0f}MB"
        )

        expected = self._get_expected_foreign_vram_mb()
        actual_foreign = nvml_info["foreign_mb"]
        logger.info(
            f"[VRAM-COORD] Expected foreign: {expected:.0f}MB, "
            f"actual foreign: {actual_foreign:.0f}MB"
        )

        if actual_foreign > expected:
            logger.warning(
                f"[VRAM-COORD] Actual foreign exceeds expected by "
                f"{actual_foreign - expected:.0f}MB"
            )
        else:
            logger.info("[VRAM-COORD] Actual foreign within expected range")

        for proc in nvml_info.get("processes", []):
            tag = "[FOREIGN]" if proc["foreign"] else "[self]"
            logger.info(
                f"[VRAM-COORD] Startup GPU process {tag}: PID {proc['pid']}, "
                f"{proc['vram_mb']:.0f}MB — {proc['cmdline']}"
            )

        blacklisted = self._check_blacklisted_ports()
        from config import VRAM_BLACKLISTED_PORTS
        for port in VRAM_BLACKLISTED_PORTS:
            status = "ACTIVE" if any(b["port"] == port for b in blacklisted) else "clear"
            logger.info(f"[VRAM-COORD] Blacklisted port {port}={status}")

    # =========================================================================
    # Backend Registration
    # =========================================================================

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

    # =========================================================================
    # VRAM Queries
    # =========================================================================

    def get_free_vram_mb(self, use_cache: bool = True) -> float:
        """
        Get currently free VRAM in MB.

        Prefers NVML (sees all processes) with PyTorch fallback.
        Runs foreign process checks on non-cached queries.
        """
        import torch

        now = time.time() * 1000
        if use_cache and (now - self._last_vram_check) < self._cache_ttl_ms:
            return self._cached_free_mb

        # Try NVML first (sees all GPU processes)
        nvml_info = self._get_nvml_memory_info()
        if nvml_info is not None:
            free_mb = nvml_info["free_mb"]

            # Run checks on fresh queries
            self._check_foreign_processes(nvml_info)
            self._check_blacklisted_ports()
        else:
            # Fallback: PyTorch only (blind to foreign processes)
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

    # =========================================================================
    # Eviction
    # =========================================================================

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

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status for debugging/API."""
        all_models = self._collect_all_models()

        status = {
            "free_mb": self.get_free_vram_mb(),
            "total_mb": self.get_total_vram_mb(),
            "nvml_available": self._nvml_available,
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

        # Add NVML-specific info
        nvml_info = self._get_nvml_memory_info()
        if nvml_info is not None:
            status["nvml_free_mb"] = nvml_info["free_mb"]
            status["nvml_used_mb"] = nvml_info["used_mb"]
            status["foreign_vram_mb"] = nvml_info["foreign_mb"]
            status["expected_foreign_vram_mb"] = round(self._get_expected_foreign_vram_mb(), 1)
            status["gpu_processes"] = nvml_info["processes"]
        else:
            status["nvml_free_mb"] = None
            status["nvml_used_mb"] = None
            status["foreign_vram_mb"] = None
            status["expected_foreign_vram_mb"] = None
            status["gpu_processes"] = []

        # Blacklisted ports
        status["blacklisted_ports"] = self._check_blacklisted_ports()

        return status


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
