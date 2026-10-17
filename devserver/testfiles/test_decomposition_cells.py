#!/usr/bin/env python3
"""
Test: Cells-API (non-rectangular cell patterns)

Verifies the new `cells` parameter, which lets the user specify arbitrary
(step, layer, stream, prompt) tuples — including non-rectangular patterns
that the legacy AND-bands API could not express (e.g. diagonals).

Tests:
  1. Backward-compat: legacy (clip_l_prompt + full bands) ≡ equivalent cells list
  2. Diagonal: only 3 of 9 (step×layer) positions active, single stream
  3. Per-cell stream choice: different stream in each active cell
  4. Empty cells (prompt = '') are skipped silently
"""

import argparse
import base64
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Optional
import requests

# connect, read: a run stands in the plant-wide GPU queue before it renders, up
# to an hour and a half (GPU_ADMISSION_ACQUIRE_TIMEOUT_S); a read cap ends the
# wait, never the run.
TIMEOUT = (10, None)
from PIL import Image


def png_hash(image_bytes: bytes) -> str:
    """Hash of the decoded pixels. The DevServer marks every PNG it answers with
    (AI-Origin Disclosure, EU AI Act Art. 50) and the mark carries the time of the
    answer to the second, so the file bytes of two identical runs differ; the
    pixels are what "identical" means here."""
    image = Image.open(io.BytesIO(image_bytes))
    return hashlib.sha256(image.tobytes()).hexdigest()[:16]


def call_decomp(server_url, source_prompt, *, cells=None,
                clip_l_prompt=None, clip_l_step_bands=None, clip_l_layer_bands=None,
                clip_g_prompt=None, clip_g_step_bands=None, clip_g_layer_bands=None,
                t5_prompt=None, t5_step_bands=None, t5_layer_bands=None,
                alpha=1.0, steps=25, cfg_scale=5.5, seed=42, timeout=TIMEOUT):
    payload = {
        "source_prompt": source_prompt,
        "cells": cells,
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
        "negative_prompt": "watermark",
        "width": 1024, "height": 1024,
        "steps": steps, "cfg_scale": cfg_scale, "seed": seed,
    }
    r = requests.post(f"{server_url}/api/fusion_workbench/decomposition",
                      json=payload, timeout=timeout)
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:300]}")
        return None
    body = r.json()
    if not body.get("success"):
        print(f"  ERROR: {body.get('error')}")
        return None
    return base64.b64decode(body["image_base64"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=17802)
    p.add_argument("--out-dir", type=str, default="./decomp_cells")
    args = p.parse_args()

    server_url = f"http://localhost:{args.port}"
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    SOURCE = "A red fox sitting in a snowy forest at sunset"
    CLIP_L_OVR = "An astronaut floating in space near a planet"
    CLIP_G_OVR = "Impressionist painting style, thick brushstrokes, vibrant colors"
    T5_OVR = "An ancient stone cathedral with tall spires under a stormy sky"
    SEED = 42

    ALL_STEPS = ["composition", "semantics", "detail"]
    ALL_LAYERS = ["shallow", "middle", "deep"]

    print(f"Cells-API test — seed={SEED}, source={SOURCE!r}\n  Out: {out_dir}\n")

    results = []

    # --- TEST 1: Backward-compat ---
    print("[1] Backward-compat: legacy clip_g full → equivalent cells list")
    t0 = time.time()
    b_legacy = call_decomp(
        server_url, SOURCE,
        clip_g_prompt=CLIP_G_OVR,
        clip_g_step_bands=ALL_STEPS, clip_g_layer_bands=ALL_LAYERS,
        seed=SEED,
    )
    h_legacy = png_hash(b_legacy) if b_legacy else None
    (out_dir / "t1_legacy_full.png").write_bytes(b_legacy) if b_legacy else None
    print(f"  legacy: {time.time()-t0:.1f}s hash={h_legacy}")

    cells_full = [
        {"step": s, "layer": l, "stream": "clip_g", "prompt": CLIP_G_OVR}
        for s in ALL_STEPS for l in ALL_LAYERS
    ]
    t0 = time.time()
    b_cells = call_decomp(server_url, SOURCE, cells=cells_full, seed=SEED)
    h_cells = png_hash(b_cells) if b_cells else None
    (out_dir / "t1_cells_full.png").write_bytes(b_cells) if b_cells else None
    print(f"  cells:  {time.time()-t0:.1f}s hash={h_cells}")

    if h_legacy == h_cells and h_legacy is not None:
        print("  PASS — backward-compat: legacy ≡ cells full-cross-product")
        results.append(("t1_backward_compat", "PASS"))
    else:
        print(f"  FAIL — hashes differ: {h_legacy} vs {h_cells}")
        results.append(("t1_backward_compat", f"FAIL ({h_legacy} vs {h_cells})"))

    # --- TEST 2: Diagonal pattern ---
    print("\n[2] Diagonal: (composition,shallow), (semantics,middle), (detail,deep) — CLIP-G")
    cells_diag = [
        {"step": "composition", "layer": "shallow", "stream": "clip_g", "prompt": CLIP_G_OVR},
        {"step": "semantics",   "layer": "middle",   "stream": "clip_g", "prompt": CLIP_G_OVR},
        {"step": "detail",  "layer": "deep",       "stream": "clip_g", "prompt": CLIP_G_OVR},
    ]
    t0 = time.time()
    b = call_decomp(server_url, SOURCE, cells=cells_diag, seed=SEED)
    if b:
        h = png_hash(b)
        (out_dir / "t2_diagonal.png").write_bytes(b)
        print(f"  {time.time()-t0:.1f}s hash={h}")
        if h != h_cells and h != h_legacy:
            print("  PASS — diagonal differs from full-active (sparse pattern works)")
            results.append(("t2_diagonal_distinct", "PASS"))
        else:
            print("  FAIL — diagonal matched full-active")
            results.append(("t2_diagonal_distinct", "FAIL"))

    # --- TEST 3: Anti-diagonal ---
    print("\n[3] Anti-diagonal: (composition,deep), (semantics,middle), (detail,shallow) — CLIP-G")
    cells_anti = [
        {"step": "composition", "layer": "deep",       "stream": "clip_g", "prompt": CLIP_G_OVR},
        {"step": "semantics",   "layer": "middle",   "stream": "clip_g", "prompt": CLIP_G_OVR},
        {"step": "detail",  "layer": "shallow", "stream": "clip_g", "prompt": CLIP_G_OVR},
    ]
    t0 = time.time()
    b_anti = call_decomp(server_url, SOURCE, cells=cells_anti, seed=SEED)
    if b_anti:
        h_anti = png_hash(b_anti)
        (out_dir / "t3_anti_diagonal.png").write_bytes(b_anti)
        print(f"  {time.time()-t0:.1f}s hash={h_anti}")
        if h_anti not in (h_legacy, h_cells):
            print("  PASS — anti-diagonal produces distinct output")
            results.append(("t3_anti_diagonal", "PASS"))
        else:
            print("  FAIL")
            results.append(("t3_anti_diagonal", "FAIL"))

    # --- TEST 4: Mixed streams per cell ---
    print("\n[4] Mixed streams: each active cell uses a different stream")
    cells_mixed = [
        {"step": "composition", "layer": "deep",     "stream": "clip_l", "prompt": CLIP_L_OVR},
        {"step": "semantics",   "layer": "middle", "stream": "clip_g", "prompt": CLIP_G_OVR},
        {"step": "semantics",   "layer": "deep",     "stream": "t5",     "prompt": T5_OVR},
        {"step": "detail",  "layer": "deep",     "stream": "clip_g", "prompt": CLIP_G_OVR},
    ]
    t0 = time.time()
    b_mixed = call_decomp(server_url, SOURCE, cells=cells_mixed, seed=SEED)
    if b_mixed:
        h_mixed = png_hash(b_mixed)
        (out_dir / "t4_mixed_streams.png").write_bytes(b_mixed)
        print(f"  {time.time()-t0:.1f}s hash={h_mixed}")
        print("  GENERATED — visual review needed")
        results.append(("t4_mixed_streams", "GENERATED"))

    # --- TEST 5: Empty-prompt cells are skipped ---
    print("\n[5] Empty-prompt cells silently skipped (must equal baseline)")
    cells_empty = [
        {"step": "composition", "layer": "shallow", "stream": "clip_g", "prompt": ""},
        {"step": "semantics",   "layer": "middle",   "stream": "t5",     "prompt": "  "},
    ]
    t0 = time.time()
    b_empty = call_decomp(server_url, SOURCE, cells=cells_empty, seed=SEED)
    if b_empty:
        h_empty = png_hash(b_empty)
        (out_dir / "t5_empty_cells.png").write_bytes(b_empty)
        print(f"  {time.time()-t0:.1f}s hash={h_empty}")
        # baseline from earlier suite: a27d27f5c817f773
        # We don't have baseline computed here — just generate it for comparison
        b_base = call_decomp(server_url, SOURCE, seed=SEED)
        if b_base:
            h_base = png_hash(b_base)
            if h_empty == h_base:
                print(f"  PASS — empty cells match baseline (hash={h_base})")
                results.append(("t5_empty_cells_skipped", "PASS"))
            else:
                print(f"  FAIL — empty={h_empty} vs baseline={h_base}")
                results.append(("t5_empty_cells_skipped", f"FAIL ({h_empty} vs {h_base})"))

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, status in results:
        marker = "✓" if "PASS" in status else ("?" if "GEN" in status else "✗")
        print(f"  {marker}  {name:<35s} {status}")

    (out_dir / "summary.json").write_text(json.dumps(
        {"results": [{"name": n, "status": s} for n, s in results]}, indent=2
    ))
    print(f"\nOutputs: {out_dir}")


if __name__ == "__main__":
    main()
