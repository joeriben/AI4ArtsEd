#!/usr/bin/env python3
"""
Decomposition Band-Probing Pilot

Goal: empirically probe what the three layer bands (shallow / middle / deep)
actually do in SD3.5 Large, since there is no published study mapping
block-by-block semantics for MMDiT-38.

For each test prompt-pair, generate 4 images at FIXED seed:
  1. baseline  — no overrides
  2. shallow     — override active across ALL step phases in band "shallow"  (blocks 0-9)
  3. middle    — override active across ALL step phases in band "middle" (blocks 10-22)
  4. deep      — override active across ALL step phases in band "deep"   (blocks 23-37)

Saving the override active in all step phases isolates the LAYER axis.

Tests probe four semantic axes via different encoders:
  - identity   (CLIP-L) — does object-class swap survive each band?
  - style      (CLIP-G) — does stylistic signature land in each band?
  - composition (T5)    — does spatial/scene reordering land in each band?
  - narrative  (T5)     — does emotional/relational content land in each band?

Side-by-side grids are composed per test for visual analysis.

Usage:
  python test_decomposition_band_probing.py [--port 17802] [--out-dir ./decomp_band_probing]
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
from PIL import Image, ImageDraw, ImageFont


# Test set — one test per axis, can extend later
TESTS = [
    {
        "id": "A_identity_apple_pear",
        "axis": "identity",
        "stream": "clip_l",
        "base":     "a red apple on a wooden table, photograph",
        "override": "a green pear",
    },
    {
        "id": "B_style_apple_oilpainting",
        "axis": "style",
        "stream": "clip_g",
        "base":     "a red apple, photograph",
        "override": "oil painting, thick impasto brushstrokes",
    },
    {
        "id": "C_composition_apple_floating",
        "axis": "composition",
        "stream": "t5",
        "base":     "a red apple on a wooden table",
        "override": "an apple floating in mid-air in an empty room",
    },
    {
        "id": "D_narrative_fox_memory",
        "axis": "narrative",
        "stream": "t5",
        "base":     "a fox in a snowy forest",
        "override": "a fox remembering its first hunt at dusk",
    },
]

BANDS = ["shallow", "middle", "deep"]
STEP_PHASES = ["composition", "semantics", "detail"]

SEED = 123456789
ALPHA = 1.0
STEPS = 25
CFG = 5.5
WIDTH = 1024
HEIGHT = 1024


def png_hash(image_bytes: bytes) -> str:
    """Hash of the decoded pixels. The DevServer marks every PNG it answers with
    (AI-Origin Disclosure, EU AI Act Art. 50) and the mark carries the time of the
    answer to the second, so the file bytes of two identical runs differ; the
    pixels are what "identical" means here."""
    image = Image.open(io.BytesIO(image_bytes))
    return hashlib.sha256(image.tobytes()).hexdigest()[:16]


def generate(server_url: str, source_prompt: str, cells: list,
                 timeout=TIMEOUT) -> Optional[bytes]:
    payload = {
        "source_prompt": source_prompt,
        "cells": cells,
        "alpha": ALPHA,
        "negative_prompt": "",
        "width": WIDTH,
        "height": HEIGHT,
        "steps": STEPS,
        "cfg_scale": CFG,
        "seed": SEED,
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


def build_grid(images: dict, test: dict, out_path: Path):
    """Compose a 4-up grid: baseline | shallow | middle | deep, with labels."""
    cell_w = 512  # downscale 1024 → 512 for the grid
    cell_h = 512
    label_h = 60
    title_h = 70
    margin = 12

    cols = 4
    grid_w = cols * cell_w + (cols + 1) * margin
    grid_h = title_h + label_h + cell_h + 2 * margin

    grid = Image.new("RGB", (grid_w, grid_h), (16, 16, 16))
    draw = ImageDraw.Draw(grid)

    # Fonts: try platform defaults, fall back to default
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 22)
        font_label = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 13)
    except OSError:
        font_title = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Title
    title = f"[{test['id']}]  axis={test['axis']}  stream={test['stream']}  seed={SEED}"
    draw.text((margin, 10), title, fill=(220, 220, 220), font=font_title)
    sub = f"base: {test['base']!r}   override: {test['override']!r}"
    draw.text((margin, 38), sub, fill=(150, 150, 150), font=font_small)

    # 4 columns
    col_labels = ["baseline (no override)", "shallow (blocks 0-9)",
                  "middle (blocks 10-22)", "deep (blocks 23-37)"]
    col_keys   = ["baseline", "shallow", "middle", "deep"]

    for i, (key, label) in enumerate(zip(col_keys, col_labels)):
        x = margin + i * (cell_w + margin)
        y_label = title_h
        y_img = title_h + label_h

        # Label
        draw.text((x + 6, y_label + 18), label, fill=(200, 200, 200), font=font_label)

        # Image
        bytes_ = images.get(key)
        if bytes_:
            im = Image.open(io.BytesIO(bytes_)).convert("RGB")
            im = im.resize((cell_w, cell_h), Image.LANCZOS)
            grid.paste(im, (x, y_img))
        else:
            draw.rectangle([x, y_img, x + cell_w, y_img + cell_h], outline=(80, 80, 80))
            draw.text((x + 16, y_img + cell_h // 2), "(missing)",
                      fill=(200, 80, 80), font=font_label)

    grid.save(out_path)


def cells_for_band(band: str, stream: str, prompt: str) -> list:
    """Override active across all 3 step phases of a single layer band."""
    return [
        {"step": phase, "layer": band, "stream": stream, "prompt": prompt}
        for phase in STEP_PHASES
    ]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=17802)
    p.add_argument("--out-dir", type=str, default="./decomp_band_probing")
    args = p.parse_args()

    server_url = f"http://localhost:{args.port}"
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Band-probing pilot — seed={SEED}, α={ALPHA}, steps={STEPS}")
    print(f"  Tests: {len(TESTS)}, generations per test: 4")
    print(f"  Out: {out_dir}\n")

    summary = []
    t_start = time.time()

    for test in TESTS:
        print(f"=== {test['id']}  axis={test['axis']}  stream={test['stream']} ===")
        print(f"  base:     {test['base']!r}")
        print(f"  override: {test['override']!r}")
        per_test_dir = out_dir / test["id"]
        per_test_dir.mkdir(exist_ok=True)

        images_bytes = {}
        hashes = {}

        # Baseline (no overrides)
        t0 = time.time()
        b = generate(server_url, test["base"], cells=[])
        if b is None:
            print(f"  FAIL: baseline")
            continue
        images_bytes["baseline"] = b
        hashes["baseline"] = png_hash(b)
        (per_test_dir / "00_baseline.png").write_bytes(b)
        print(f"  baseline:  {time.time()-t0:5.1f}s  hash={hashes['baseline']}")

        # One generation per layer band
        for band in BANDS:
            t0 = time.time()
            cells = cells_for_band(band, test["stream"], test["override"])
            b = generate(server_url, test["base"], cells=cells)
            if b is None:
                print(f"  FAIL: {band}")
                continue
            images_bytes[band] = b
            hashes[band] = png_hash(b)
            (per_test_dir / f"{band}.png").write_bytes(b)
            print(f"  {band:<10s} {time.time()-t0:5.1f}s  hash={hashes[band]}")

        # 4-up grid
        grid_path = out_dir / f"{test['id']}_grid.png"
        build_grid(images_bytes, test, grid_path)
        print(f"  → grid: {grid_path.name}")

        summary.append({
            "id": test["id"],
            "axis": test["axis"],
            "stream": test["stream"],
            "base": test["base"],
            "override": test["override"],
            "hashes": hashes,
            "grid": grid_path.name,
        })
        print()

    # Index
    (out_dir / "summary.json").write_text(
        json.dumps({"seed": SEED, "alpha": ALPHA, "steps": STEPS,
                    "tests": summary}, indent=2, ensure_ascii=False)
    )

    print(f"Total: {time.time()-t_start:.1f}s")
    print(f"Outputs: {out_dir}")
    print(f"Grids (one per test): {len(summary)}")


if __name__ == "__main__":
    main()
