#!/usr/bin/env python3
"""
Supplementary Test: Step × Layer Cell Sweep (single stream)

Tests the 9 cells of (step_phase × layer_band) for a single stream override.
Exercises the AND-gate logic of the per-block hook: a cell fires only when
BOTH step AND layer bands include the current position.

Stream choice: CLIP-G with an impressionist-painting override — produces the
strongest visual contrast, so cell-level differences are clearly readable.

Run after a successful test_decomposition.py run on the same backend.
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


def call_decomposition(
    server_url, source_prompt, *, clip_g_prompt=None,
    clip_g_step_bands=None, clip_g_layer_bands=None,
    alpha=1.0, steps=25, cfg_scale=5.5, seed=42, timeout=TIMEOUT,
):
    payload = {
        "source_prompt": source_prompt,
        "clip_g_prompt": clip_g_prompt,
        "clip_g_step_bands": clip_g_step_bands,
        "clip_g_layer_bands": clip_g_layer_bands,
        "alpha": alpha,
        "negative_prompt": "watermark",
        "width": 1024, "height": 1024,
        "steps": steps, "cfg_scale": cfg_scale, "seed": seed,
    }
    r = requests.post(f"{server_url}/api/fusion_workbench/decomposition",
                      json=payload, timeout=timeout)
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:200]}")
        return None
    body = r.json()
    if not body.get("success"):
        print(f"  ERROR: {body.get('error')}")
        return None
    return base64.b64decode(body["image_base64"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=17802)
    p.add_argument("--out-dir", type=str, default="./decomp_step_x_layer")
    p.add_argument("--steps", type=int, default=25)
    p.add_argument("--cfg", type=float, default=5.5)
    args = p.parse_args()

    server_url = f"http://localhost:{args.port}"
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    SOURCE = "A red fox sitting in a snowy forest at sunset"
    OVERRIDE = "Impressionist painting style, thick brushstrokes, vibrant colors"
    SEED = 42

    print(f"Step × Layer cell sweep — stream=clip_g, alpha=1.0, seed={SEED}")
    print(f"  Source:   {SOURCE!r}")
    print(f"  Override: {OVERRIDE!r}")
    print(f"  Out dir:  {out_dir}")
    print()

    STEP_BANDS = ["composition", "semantics", "detail"]
    LAYER_BANDS = ["shallow", "middle", "deep"]

    grid = {}
    t_start = time.time()

    # Baseline (no override) and full-active for reference
    for label, step_b, layer_b in [
        ("baseline_no_override", None, None),
        ("full_active",          STEP_BANDS, LAYER_BANDS),
    ]:
        t0 = time.time()
        if step_b is None:
            b = call_decomposition(server_url, SOURCE, steps=args.steps,
                                   cfg_scale=args.cfg, seed=SEED)
        else:
            b = call_decomposition(
                server_url, SOURCE,
                clip_g_prompt=OVERRIDE,
                clip_g_step_bands=step_b, clip_g_layer_bands=layer_b,
                steps=args.steps, cfg_scale=args.cfg, seed=SEED,
            )
        if b is None:
            print(f"  FAIL: {label}")
            continue
        h = png_hash(b)
        (out_dir / f"{label}.png").write_bytes(b)
        grid[label] = h
        print(f"  {label:<25s} {time.time()-t0:5.1f}s  hash={h}")

    print()
    # 9 individual cells
    for step_b in STEP_BANDS:
        for layer_b in LAYER_BANDS:
            label = f"cell_step-{step_b}_layer-{layer_b}"
            t0 = time.time()
            b = call_decomposition(
                server_url, SOURCE,
                clip_g_prompt=OVERRIDE,
                clip_g_step_bands=[step_b],
                clip_g_layer_bands=[layer_b],
                steps=args.steps, cfg_scale=args.cfg, seed=SEED,
            )
            if b is None:
                print(f"  FAIL: {label}")
                continue
            h = png_hash(b)
            (out_dir / f"{label}.png").write_bytes(b)
            grid[label] = h
            print(f"  {label:<30s} {time.time()-t0:5.1f}s  hash={h}")

    # Summary
    print()
    print(f"Total: {time.time()-t_start:.1f}s")
    print()
    print("Hash matrix (rows = step, cols = layer):")
    print(f"  {'':<6s} {'shallow':<19s} {'middle':<19s} {'deep':<19s}")
    for step_b in STEP_BANDS:
        row = [f"{step_b:<6s}"]
        for layer_b in LAYER_BANDS:
            h = grid.get(f"cell_step-{step_b}_layer-{layer_b}", "—")
            row.append(f"{h:<19s}")
        print("  " + " ".join(row))

    # Distinct-hash check (the AND-gate produces 9 distinct outputs if cells are independent)
    cell_hashes = [v for k, v in grid.items() if k.startswith("cell_")]
    distinct = len(set(cell_hashes))
    print()
    print(f"Distinct cell hashes: {distinct}/9")
    if distinct == 9:
        print("PASS — every (step × layer) cell produces a unique image.")
    else:
        print("CHECK — some cells produced identical outputs (possibly cells with very weak effect).")

    (out_dir / "grid.json").write_text(json.dumps(grid, indent=2))


if __name__ == "__main__":
    main()
