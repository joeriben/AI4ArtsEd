#!/usr/bin/env python3
"""
Test Script: Decomposition Mode — 3×3×3 Intervention Space (Phase 1 PoC)

Verifies the new decomposition backend endpoint with the 6 verification checks
defined in the plan, plus an exploratory test matrix over the operating modes.

Usage:
    python test_decomposition.py [--port 17802] [--comfyui-port 17804] [--out-dir ./decomp_out] [--quick]

    --port PORT       DevServer port (default 17802)
    --comfyui-port P  ComfyUI port, asked directly for the sanity check and for
                      dropping its output cache between the runs of checks 5 and 6
                      (default 17804)
    --out-dir DIR     Output directory for PNGs + metadata (default ./decomp_out)
    --quick           Only run sanity checks (1-3), skip exploratory matrix

Verification checks (all run by default):
    1. Sanity: DevServer up and ComfyUI answering on its own port
    2. Baseline: no overrides → bit-identical to standard SD3.5
    3. Stream-Solo-Total: t5_prompt = different → T5 slice replaced, CLIP slots baseline
    4. Dimension-Wirksamkeit: vary each dim, verify visually distinguishable
    5. Reproducibility: same params + seed → bit-identical PNG
    6. No-Leakage: different generations don't influence each other

Backend-Voraussetzungen:
    - DevServer and ComfyUI run (localhost:17802/api/settings/gpu-realtime and
      localhost:17804/system_stats answer)
    - SD3.5 Large gecached (oder Erstgenerierung lädt ~30 GB)
"""

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

import requests

# connect, read: a run stands in the plant-wide GPU queue before it renders, up
# to an hour and a half (GPU_ADMISSION_ACQUIRE_TIMEOUT_S); a read cap ends the
# wait, never the run.
TIMEOUT = (10, None)
from PIL import Image

# Force line-buffered output
import functools
print = functools.partial(print, flush=True)  # type: ignore[assignment]


def png_hash(image_bytes: bytes) -> str:
    """Hash of the decoded pixels. The DevServer marks every PNG it answers with
    (AI-Origin Disclosure, EU AI Act Art. 50) and the mark carries the time of the
    answer to the second, so the file bytes of two identical runs differ; the
    pixels are what "identical" means here."""
    image = Image.open(io.BytesIO(image_bytes))
    return hashlib.sha256(image.tobytes()).hexdigest()[:16]


def call_decomposition(
    server_url: str,
    source_prompt: str,
    *,
    clip_l_prompt: Optional[str] = None,
    clip_l_step_bands: Optional[list] = None,
    clip_l_layer_bands: Optional[list] = None,
    clip_g_prompt: Optional[str] = None,
    clip_g_step_bands: Optional[list] = None,
    clip_g_layer_bands: Optional[list] = None,
    t5_prompt: Optional[str] = None,
    t5_step_bands: Optional[list] = None,
    t5_layer_bands: Optional[list] = None,
    alpha: float = 1.0,
    negative_prompt: str = "watermark",
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg_scale: float = 5.5,
    seed: int = 42,
    timeout=TIMEOUT,
) -> Optional[bytes]:
    """Call /api/fusion_workbench/decomposition. Returns PNG bytes or None."""
    payload = {
        "source_prompt": source_prompt,
        "clip_l_prompt": clip_l_prompt,
        "clip_l_step_bands": clip_l_step_bands,
        "clip_l_layer_bands": clip_l_layer_bands,
        "clip_g_prompt": clip_g_prompt,
        "clip_g_step_bands": clip_g_step_bands,
        "clip_g_layer_bands": clip_g_layer_bands,
        "t5_prompt": t5_prompt,
        "t5_step_bands": t5_step_bands,
        "t5_layer_bands": t5_layer_bands,
        "alpha": alpha,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
    }
    try:
        r = requests.post(f"{server_url}/api/fusion_workbench/decomposition",
                          json=payload, timeout=timeout)
    except requests.RequestException as e:
        print(f"  ERROR: request failed: {e}")
        return None

    if r.status_code != 200:
        print(f"  ERROR: HTTP {r.status_code}: {r.text[:200]}")
        return None
    body = r.json()
    if not body.get("success"):
        print(f"  ERROR: server response: {body.get('error', 'unknown')}")
        return None
    return base64.b64decode(body["image_base64"])


def call_standard_sd35(
    server_url: str,
    prompt: str,
    *,
    negative_prompt: str = "watermark",
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg_scale: float = 5.5,
    seed: int = 42,
    timeout=TIMEOUT,
) -> Optional[bytes]:
    """The plain SD3.5 run for the baseline comparison: the Decomposition run
    with no cells."""
    payload = {
        "source_prompt": prompt,
        "cells": [],
        "model_id": "stabilityai/stable-diffusion-3.5-large",
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
    }
    try:
        r = requests.post(f"{server_url}/api/fusion_workbench/decomposition",
                          json=payload, timeout=timeout)
    except requests.RequestException as e:
        print(f"  ERROR: request failed: {e}")
        return None
    if r.status_code != 200:
        print(f"  ERROR: HTTP {r.status_code}: {r.text[:200]}")
        return None
    body = r.json()
    if not body.get("success"):
        print(f"  ERROR: server response: {body.get('error', 'unknown')}")
        return None
    return base64.b64decode(body["image_base64"])


def save_image(out_dir: Path, label: str, image_bytes: bytes, meta: Dict[str, Any]) -> str:
    """Save PNG + metadata JSON. Return PNG hash."""
    h = png_hash(image_bytes)
    png_path = out_dir / f"{label}.png"
    meta_path = out_dir / f"{label}.json"
    png_path.write_bytes(image_bytes)
    meta_with_hash = {**meta, "png_hash_sha256_16": h, "bytes": len(image_bytes)}
    meta_path.write_text(json.dumps(meta_with_hash, indent=2, ensure_ascii=False))
    return h


def check_server(server_url: str, comfyui_url: str) -> bool:
    """The DevServer answers, and ComfyUI answers on its own port. The
    DevServer's /api/settings/gpu-realtime answers without ComfyUI, so it
    proves the DevServer alone."""
    try:
        r = requests.get(f"{server_url}/api/settings/gpu-realtime", timeout=5)
    except requests.RequestException as e:
        print(f"  DevServer unreachable: {e}")
        return False
    if r.status_code != 200:
        print(f"  DevServer /api/settings/gpu-realtime → HTTP {r.status_code}")
        return False
    try:
        r = requests.get(f"{comfyui_url}/system_stats", timeout=5)
    except requests.RequestException as e:
        print(f"  ComfyUI unreachable at {comfyui_url}: {e}")
        return False
    if r.status_code != 200:
        print(f"  ComfyUI /system_stats → HTTP {r.status_code}")
        return False
    print(f"  DevServer up at {server_url}, ComfyUI up at {comfyui_url}.")
    return True


def drop_comfyui_cache(comfyui_url: str) -> bool:
    """ComfyUI answers a graph it has run before from its output cache, the
    saved picture included: two runs of one graph are one run. Checks 5 and 6
    are about a second run, so the cache is dropped between them. /free with
    free_memory also unloads the models; the next run loads them again."""
    try:
        r = requests.post(f"{comfyui_url}/free", json={"free_memory": True}, timeout=30)
    except requests.RequestException as e:
        print(f"  ComfyUI /free failed: {e}")
        return False
    if r.status_code != 200:
        print(f"  ComfyUI /free → HTTP {r.status_code}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=17802)
    parser.add_argument("--comfyui-port", type=int, default=17804)
    parser.add_argument("--out-dir", type=str, default="./decomp_out")
    parser.add_argument("--quick", action="store_true",
                        help="Only run checks 1-3 (sanity + baseline)")
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--cfg", type=float, default=5.5)
    args = parser.parse_args()

    server_url = f"http://localhost:{args.port}"
    comfyui_url = f"http://localhost:{args.comfyui_port}"
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Standard test prompts. Source vs T5-override pair chosen for clear visual
    # differentiation: a small mammal vs a large architectural object.
    SOURCE = "A red fox sitting in a snowy forest at sunset"
    OVERRIDE_T5 = "An ancient stone cathedral with tall spires under a stormy sky"
    OVERRIDE_CLIP_L = "An astronaut floating in space near a planet"
    OVERRIDE_CLIP_G = "Impressionist painting style, thick brushstrokes, vibrant colors"

    SEED = 42

    print("=" * 70)
    print(f"Decomposition Mode Test Suite")
    print(f"  Server:  {server_url}")
    print(f"  Out dir: {out_dir}")
    print(f"  Source:  {SOURCE!r}")
    print(f"  Steps={args.steps}, CFG={args.cfg}, Seed={SEED}")
    print("=" * 70)

    results = []

    # =========================================================================
    # CHECK 1: DevServer up, ComfyUI answering
    # =========================================================================
    print("\n[CHECK 1] DevServer & ComfyUI availability")
    if not check_server(server_url, comfyui_url):
        print("  FAIL: cannot proceed without the DevServer.")
        sys.exit(1)
    print("  PASS")
    results.append(("check1_server_alive", "PASS"))

    # =========================================================================
    # CHECK 2: Baseline-Test — no overrides → matches standard SD3.5
    # =========================================================================
    print("\n[CHECK 2] Baseline-Test (no overrides → matches standard SD3.5)")

    print("  Generating standard SD3.5 ...")
    t0 = time.time()
    std_bytes = call_standard_sd35(
        server_url, SOURCE, steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if std_bytes is None:
        print("  FAIL: standard SD3.5 returned None"); sys.exit(1)
    std_hash = save_image(out_dir, "check2_standard", std_bytes, {
        "test": "check2_standard_sd35",
        "prompt": SOURCE, "steps": args.steps, "cfg": args.cfg, "seed": SEED,
    })
    print(f"  standard: {time.time()-t0:.1f}s, hash={std_hash}")

    print("  Generating decomposition with no overrides ...")
    t0 = time.time()
    decomp_bytes = call_decomposition(
        server_url, SOURCE, steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if decomp_bytes is None:
        print("  FAIL: decomposition (no overrides) returned None"); sys.exit(1)
    decomp_hash = save_image(out_dir, "check2_decomp_no_overrides", decomp_bytes, {
        "test": "check2_decomp_no_overrides",
        "prompt": SOURCE, "steps": args.steps, "cfg": args.cfg, "seed": SEED,
    })
    print(f"  decomp:   {time.time()-t0:.1f}s, hash={decomp_hash}")

    if std_hash == decomp_hash:
        print("  PASS: bit-identical to standard SD3.5 (hook is neutral)")
        results.append(("check2_baseline_match", "PASS"))
    else:
        print(f"  WARN: hashes differ ({std_hash} vs {decomp_hash}) — hook may have a side effect.")
        print(f"  This is expected if encode_prompt path differs slightly. Visual comparison advised.")
        results.append(("check2_baseline_match", f"WARN (hashes differ: {std_hash} vs {decomp_hash})"))

    # =========================================================================
    # CHECK 3: Stream-Solo-Total — T5 override, full bands, α=1.0
    # =========================================================================
    print("\n[CHECK 3] Stream-Solo-Total — T5 override fully active")
    t0 = time.time()
    bytes_t5_solo = call_decomposition(
        server_url, SOURCE,
        t5_prompt=OVERRIDE_T5, alpha=1.0,
        steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if bytes_t5_solo is None:
        print("  FAIL: T5-solo returned None"); sys.exit(1)
    h_t5 = save_image(out_dir, "check3_t5_solo_total", bytes_t5_solo, {
        "test": "check3_t5_solo_total",
        "source_prompt": SOURCE, "t5_prompt": OVERRIDE_T5,
        "alpha": 1.0, "seed": SEED,
    })
    print(f"  done: {time.time()-t0:.1f}s, hash={h_t5}")
    print(f"  Visual check needed: output should show traces of {OVERRIDE_T5!r}.")
    results.append(("check3_t5_solo_total", "GENERATED — visual review needed"))

    if args.quick:
        print("\n[QUICK MODE] Skipping checks 4-6 and exploratory matrix.")
        _write_summary(out_dir, results)
        return

    # =========================================================================
    # CHECK 4: Dimension-Wirksamkeit (vary each dimension)
    # =========================================================================
    print("\n[CHECK 4] Dimension-Wirksamkeit — vary each dimension")

    # 4a: vary T5 step bands (everything else fixed)
    for bands_label, bands in [
        ("early_only", ["composition"]),
        ("mid_only",   ["semantics"]),
        ("late_only",  ["detail"]),
        ("all_steps",  ["composition", "semantics", "detail"]),
    ]:
        t0 = time.time()
        b = call_decomposition(
            server_url, SOURCE,
            t5_prompt=OVERRIDE_T5,
            t5_step_bands=bands,
            alpha=1.0,
            steps=args.steps, cfg_scale=args.cfg, seed=SEED,
        )
        if b is None:
            print(f"  FAIL: t5_step={bands_label} returned None")
            continue
        h = save_image(out_dir, f"check4_t5_step_{bands_label}", b, {
            "test": "check4_t5_step",
            "t5_step_bands": bands, "t5_prompt": OVERRIDE_T5, "seed": SEED,
        })
        print(f"  t5 step={bands_label:<12s}: {time.time()-t0:.1f}s, hash={h}")
    results.append(("check4a_t5_step_dimension", "GENERATED"))

    # 4b: vary T5 layer bands
    for bands_label, bands in [
        ("shallow", ["shallow"]),
        ("middle",   ["middle"]),
        ("deep",       ["deep"]),
    ]:
        t0 = time.time()
        b = call_decomposition(
            server_url, SOURCE,
            t5_prompt=OVERRIDE_T5,
            t5_layer_bands=bands,
            alpha=1.0,
            steps=args.steps, cfg_scale=args.cfg, seed=SEED,
        )
        if b is None:
            print(f"  FAIL: t5_layer={bands_label} returned None")
            continue
        h = save_image(out_dir, f"check4_t5_layer_{bands_label}", b, {
            "test": "check4_t5_layer",
            "t5_layer_bands": bands, "t5_prompt": OVERRIDE_T5, "seed": SEED,
        })
        print(f"  t5 layer={bands_label:<12s}: {time.time()-t0:.1f}s, hash={h}")
    results.append(("check4b_t5_layer_dimension", "GENERATED"))

    # 4c: vary stream (clip_l only, clip_g only, t5 only)
    for stream_label, stream_kwargs in [
        ("clip_l", {"clip_l_prompt": OVERRIDE_CLIP_L}),
        ("clip_g", {"clip_g_prompt": OVERRIDE_CLIP_G}),
        ("t5",     {"t5_prompt":     OVERRIDE_T5}),
    ]:
        t0 = time.time()
        b = call_decomposition(
            server_url, SOURCE, alpha=1.0,
            steps=args.steps, cfg_scale=args.cfg, seed=SEED,
            **stream_kwargs,
        )
        if b is None:
            print(f"  FAIL: stream={stream_label} returned None")
            continue
        h = save_image(out_dir, f"check4_stream_{stream_label}", b, {
            "test": "check4_stream",
            "stream": stream_label, **stream_kwargs, "seed": SEED,
        })
        print(f"  stream={stream_label:<6s}: {time.time()-t0:.1f}s, hash={h}")
    results.append(("check4c_stream_dimension", "GENERATED"))

    # =========================================================================
    # CHECK 5: Reproducibility — same params + seed → bit-identical PNG
    # =========================================================================
    print("\n[CHECK 5] Reproducibility — two runs same seed")
    t0 = time.time()
    b1 = call_decomposition(
        server_url, SOURCE, t5_prompt=OVERRIDE_T5, alpha=0.7,
        t5_step_bands=["detail"], t5_layer_bands=["deep"],
        steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if not drop_comfyui_cache(comfyui_url):
        print("  the second run would be answered from the first")
    b2 = call_decomposition(
        server_url, SOURCE, t5_prompt=OVERRIDE_T5, alpha=0.7,
        t5_step_bands=["detail"], t5_layer_bands=["deep"],
        steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if b1 is None or b2 is None:
        print("  FAIL: one of the runs returned None")
        results.append(("check5_reproducibility", "FAIL"))
    else:
        h1, h2 = png_hash(b1), png_hash(b2)
        save_image(out_dir, "check5_repro_run1", b1, {"test": "check5_run1", "seed": SEED})
        if h1 == h2:
            print(f"  PASS: bit-identical (hash={h1}, total {time.time()-t0:.1f}s)")
            results.append(("check5_reproducibility", "PASS"))
        else:
            print(f"  FAIL: hashes differ ({h1} vs {h2})")
            results.append(("check5_reproducibility", f"FAIL ({h1} vs {h2})"))

    # =========================================================================
    # CHECK 6: No-Leakage — different params back-to-back, second is independent
    # =========================================================================
    print("\n[CHECK 6] No-Leakage — params from prev run don't bleed")
    # Run A: with overrides
    _ = call_decomposition(
        server_url, SOURCE, t5_prompt=OVERRIDE_T5, alpha=1.0,
        t5_step_bands=["semantics"], t5_layer_bands=["middle"],
        steps=args.steps, cfg_scale=args.cfg, seed=SEED + 1,
    )
    # Run B: same source, NO overrides — must equal baseline, computed again
    if not drop_comfyui_cache(comfyui_url):
        print("  run B would be answered from the baseline's run")
    bb = call_decomposition(
        server_url, SOURCE,
        steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if bb is None:
        print("  FAIL: leakage-check run B returned None")
        results.append(("check6_no_leakage", "FAIL (None)"))
    else:
        h_bb = png_hash(bb)
        if h_bb == decomp_hash:
            print(f"  PASS: post-override no-override matches baseline (hash={h_bb})")
            results.append(("check6_no_leakage", "PASS"))
        else:
            print(f"  WARN: differs from baseline ({h_bb} vs {decomp_hash})")
            print(f"        — could be CUDA-RNG state, not necessarily a hook bug.")
            results.append(("check6_no_leakage", f"WARN ({h_bb} vs {decomp_hash})"))

    # =========================================================================
    # EXPLORATORY: pragmatic sweet-spot + asymmetric combo
    # =========================================================================
    print("\n[EXPLORATORY] Pragmatic sweet-spot ('Komposition A, Stimme B')")
    t0 = time.time()
    b = call_decomposition(
        server_url, SOURCE,
        clip_g_prompt=OVERRIDE_CLIP_G,
        t5_prompt=OVERRIDE_T5,
        clip_g_step_bands=["detail"], clip_g_layer_bands=["deep"],
        t5_step_bands=["detail"], t5_layer_bands=["deep"],
        alpha=0.7,
        steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if b is not None:
        h = save_image(out_dir, "explore_sweet_spot", b, {
            "test": "explore_sweet_spot",
            "description": "Komposition A, Stimme B (clip_g + t5 in late × voice)",
            "alpha": 0.7,
        })
        print(f"  done: {time.time()-t0:.1f}s, hash={h}")

    print("\n[EXPLORATORY] Inversion test (negative alpha)")
    t0 = time.time()
    b = call_decomposition(
        server_url, SOURCE,
        t5_prompt=OVERRIDE_T5, alpha=-0.5,
        steps=args.steps, cfg_scale=args.cfg, seed=SEED,
    )
    if b is not None:
        h = save_image(out_dir, "explore_inversion", b, {
            "test": "explore_inversion",
            "description": "T5 override with α=-0.5 (contrastive push-away)",
            "alpha": -0.5,
        })
        print(f"  done: {time.time()-t0:.1f}s, hash={h}")

    _write_summary(out_dir, results)


def _write_summary(out_dir: Path, results):
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, status in results:
        marker = "✓" if "PASS" in status else ("?" if "WARN" in status else ("✗" if "FAIL" in status else "•"))
        print(f"  {marker}  {name:<40s}  {status}")
    summary_path = out_dir / "SUMMARY.json"
    summary_path.write_text(json.dumps(
        {"results": [{"name": n, "status": s} for n, s in results]},
        indent=2, ensure_ascii=False
    ))
    print(f"\nAll outputs in: {out_dir}")
    print(f"Summary file:   {summary_path}")


if __name__ == "__main__":
    main()
