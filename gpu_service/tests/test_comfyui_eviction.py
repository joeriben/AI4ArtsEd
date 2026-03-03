#!/usr/bin/env python3
"""
Manual test: Cross-process ComfyUI eviction in VRAMCoordinator.

Prerequisites:
  1. GPU service running (./6_start_gpu_service.sh)
  2. ComfyUI running on port 17804 with a model loaded
     (generate an image via ComfyUI first so it holds VRAM)

Usage:
  cd gpu_service && ../venv/bin/python tests/test_comfyui_eviction.py

Steps:
  1. Shows current VRAM state (free, foreign, ComfyUI port)
  2. Tests _try_comfyui_eviction() directly
  3. Shows VRAM state after eviction
"""

import logging
import sys
import os
import socket
import json
import urllib.request

# Show coordinator INFO logs in test output
logging.basicConfig(level=logging.INFO, format="%(message)s")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_comfyui_port():
    from config import COMFYUI_PORT
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", COMFYUI_PORT))
        sock.close()
        return result == 0, COMFYUI_PORT
    except Exception:
        return False, COMFYUI_PORT


def fmt(val, suffix="MB"):
    """Format a numeric value or return N/A."""
    if val is None:
        return "N/A"
    return f"{val:.0f} {suffix}"


def get_vram_status():
    """Query GPU service health endpoint."""
    try:
        req = urllib.request.Request("http://localhost:17803/api/health/vram")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def print_vram_status(status, label=""):
    """Print VRAM info from coordinator.get_status() response."""
    if "error" in status:
        print(f"    GPU service not reachable: {status['error']}")
        return

    # /api/health/vram returns coordinator.get_status() directly (no wrapper key)
    print(f"    Free:     {fmt(status.get('free_mb'))}")
    print(f"    Total:    {fmt(status.get('total_mb'))}")
    print(f"    Foreign:  {fmt(status.get('foreign_vram_mb'))}")
    print(f"    Expected: {fmt(status.get('expected_foreign_vram_mb'))}")

    processes = status.get("gpu_processes", [])
    if processes:
        print("    GPU processes:")
        for p in processes:
            tag = "[FOREIGN]" if p.get("foreign") else "[self]   "
            print(f"      {tag} PID {p['pid']}: {p['vram_mb']:.0f} MB — {p['cmdline'][:80]}")


def main():
    print("=" * 60)
    print("ComfyUI Cross-Process Eviction Test")
    print("=" * 60)

    # Step 1: Check prerequisites
    comfyui_up, port = check_comfyui_port()
    print(f"\n[1] ComfyUI port {port}: {'UP' if comfyui_up else 'DOWN'}")
    if not comfyui_up:
        print("    ComfyUI not running — eviction will return 0 (expected).")
        print("    Start ComfyUI and load a model for a real test.")

    # Step 2: Show current VRAM state
    print("\n[2] Current VRAM state (via GPU service /api/health/vram):")
    status = get_vram_status()
    if "error" in status:
        print(f"    GPU service not reachable: {status['error']}")
        print("    Continuing with direct coordinator test...\n")
    else:
        print_vram_status(status)

    # Step 3: Test eviction directly via coordinator
    print("\n[3] Testing _try_comfyui_eviction() directly...")
    freed = 0
    try:
        from services.vram_coordinator import get_vram_coordinator
        coordinator = get_vram_coordinator()

        free_before = coordinator.get_free_vram_mb(use_cache=False)
        print(f"    NVML free before: {free_before:.0f} MB")

        freed = coordinator._try_comfyui_eviction()
        print(f"    Freed: {freed:.0f} MB")

        free_after = coordinator.get_free_vram_mb(use_cache=False)
        print(f"    NVML free after:  {free_after:.0f} MB")
        print(f"    Delta:            {free_after - free_before:.0f} MB")
    except Exception as e:
        print(f"    Error: {e}")
        import traceback
        traceback.print_exc()

    # Step 4: Show VRAM state after
    print("\n[4] VRAM state after eviction:")
    status = get_vram_status()
    if "error" not in status:
        print_vram_status(status)
    else:
        print(f"    GPU service not reachable: {status['error']}")

    print("\n" + "=" * 60)
    if freed > 0:
        print(f"SUCCESS: ComfyUI released {freed:.0f} MB VRAM")
    elif comfyui_up:
        print("ComfyUI was up but freed 0 MB (may have been idle / no models loaded)")
    else:
        print("ComfyUI not running — eviction correctly returned 0")
    print("=" * 60)


if __name__ == "__main__":
    main()
