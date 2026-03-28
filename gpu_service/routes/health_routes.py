"""
GPU Service Health Routes

Provides health check, GPU info, and loaded model status.
"""

import logging
import os
import signal
import time
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check with GPU and model status."""
    try:
        import torch

        gpu_info = {}
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            total = props.total_memory / 1024**3
            gpu_info = {
                "gpu_name": props.name,
                "total_vram_gb": round(total, 2),
                "allocated_gb": round(allocated, 2),
                "reserved_gb": round(reserved, 2),
                "free_gb": round(total - reserved, 2),
            }

        # Get VRAM coordinator status (includes all backends)
        coordinator_status = {}
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator_status = coordinator.get_status()
        except Exception as e:
            logger.warning(f"VRAM coordinator status failed: {e}")

        return jsonify({
            "status": "ok",
            "gpu": gpu_info,
            "vram_coordinator": coordinator_status,
        })

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@health_bp.route('/api/health/vram', methods=['GET'])
def vram_status():
    """Detailed VRAM status from coordinator."""
    try:
        from services.vram_coordinator import get_vram_coordinator
        coordinator = get_vram_coordinator()
        return jsonify(coordinator.get_status())
    except Exception as e:
        logger.error(f"VRAM status error: {e}")
        return jsonify({"error": str(e)}), 500


@health_bp.route('/api/health/kill-foreign', methods=['POST'])
def kill_foreign_process():
    """Kill a foreign GPU process by PID. Only kills PIDs confirmed as foreign GPU consumers."""
    try:
        from services.vram_coordinator import get_vram_coordinator
        from config import COMFYUI_PORT

        data = request.get_json()
        if not data or "pid" not in data:
            return jsonify({"error": "Request body must contain 'pid'"}), 400

        target_pid = int(data["pid"])
        our_pid = os.getpid()

        # Safety: never kill ourselves
        if target_pid == our_pid:
            return jsonify({"error": "Cannot kill own process"}), 403

        # Verify PID is in NVML's foreign process list
        coordinator = get_vram_coordinator()
        nvml_info = coordinator._get_nvml_memory_info()
        if nvml_info is None:
            return jsonify({"error": "NVML not available — cannot verify foreign process"}), 503

        foreign_procs = [p for p in nvml_info["processes"] if p["foreign"]]
        target_proc = next((p for p in foreign_procs if p["pid"] == target_pid), None)
        if target_proc is None:
            return jsonify({"error": f"PID {target_pid} is not a foreign GPU process"}), 403

        cmdline = target_proc["cmdline"].lower()

        # Safety: never kill expected ComfyUI
        if str(COMFYUI_PORT) in cmdline:
            return jsonify({"error": f"PID {target_pid} is expected ComfyUI on port {COMFYUI_PORT} — refusing to kill"}), 403

        # Kill it
        vram_before = target_proc["vram_mb"]
        logger.warning(f"[VRAM-WATCHDOG] Killing foreign PID {target_pid} ({vram_before:.0f}MB): {target_proc['cmdline']}")

        try:
            os.kill(target_pid, signal.SIGTERM)
        except ProcessLookupError:
            return jsonify({"killed": True, "pid": target_pid, "freed_mb": vram_before, "note": "Process already gone"})
        except PermissionError:
            return jsonify({"error": f"Permission denied killing PID {target_pid}"}), 403

        # Wait up to 2s for graceful exit, then SIGKILL
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(target_pid, 0)  # Check if alive
            except ProcessLookupError:
                logger.info(f"[VRAM-WATCHDOG] PID {target_pid} terminated gracefully")
                return jsonify({"killed": True, "pid": target_pid, "freed_mb": vram_before})

        # Still alive — escalate
        try:
            os.kill(target_pid, signal.SIGKILL)
            logger.warning(f"[VRAM-WATCHDOG] PID {target_pid} required SIGKILL")
        except ProcessLookupError:
            pass
        except PermissionError:
            return jsonify({"error": f"SIGTERM sent but SIGKILL denied for PID {target_pid}"}), 403

        return jsonify({"killed": True, "pid": target_pid, "freed_mb": vram_before, "escalated": True})

    except ValueError:
        return jsonify({"error": "Invalid PID — must be integer"}), 400
    except Exception as e:
        logger.error(f"Kill foreign error: {e}")
        return jsonify({"error": str(e)}), 500
