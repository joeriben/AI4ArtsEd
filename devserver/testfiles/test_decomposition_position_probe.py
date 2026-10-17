#!/usr/bin/env python3
"""
Position-Probe Sweep — SD3.5 Large MMDiT

Observational probe. No pre-categorisation of artistic dimensions.

Setup:
  baseline_prompt = ""  (empty string — the unconditional CFG default,
                         the only baseline that introduces no compositional
                         semantic load)
  probe_prompt    = one lexically unitary primitive (English, e.g. "a cannonball")

Prompts are English to avoid confounding the probe with the model's
non-English handling (especially CLIP-G).

For each (step_phase × layer_band × stream) region, the slice of
encoder_hidden_states at that region is REPLACED with the probe's encoding
of that stream. No alpha, no addition. Pure substitution.

Sweep granularity (band-based):
  3 step phases × 3 layer bands × 3 streams = 27 sweep images
  Plus baseline image (no probe) and target image (probe as full prompt).

Step phases (from docs/LATENT_LAB_SCIENTIFIC_FOUNDATION.md):
  composition: steps 0–7
  semantics:    steps 8–16
  detail:      steps 17–24

Layer bands (SD3.5 Large MMDiT, 38 blocks):
  shallow:  blocks 0–9
  middle: blocks 10–22
  deep:   blocks 23–37

Usage:
  python test_decomposition_position_probe.py \\
      --primitive "a cannonball" \\
      --out-dir /tmp/decomp_probe_cannonball_v1
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


# Sweep grid — band-based (regions, not points)
STEP_PHASES = [
    ('composition', (0, 8)),
    ('semantics',    (8, 17)),
    ('detail',      (17, 25)),
]
LAYER_BANDS = [
    ('shallow',  (0, 10)),
    ('middle', (10, 23)),
    ('deep',   (23, 38)),
]
STREAMS = ['clip_l', 'clip_g', 't5']

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


def generate_simple(server_url: str, prompt: str, seed: int,
                    timeout=TIMEOUT) -> Optional[bytes]:
    """Generate a single image with no probe (baseline or target): the
    Decomposition run with no cells is the plain conditioning."""
    payload = {
        "source_prompt": prompt,
        "cells": [],
        "negative_prompt": "",
        "width": WIDTH,
        "height": HEIGHT,
        "steps": STEPS,
        "cfg_scale": CFG,
        "seed": seed,
    }
    r = requests.post(f"{server_url}/api/fusion_workbench/decomposition", json=payload, timeout=timeout)
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:200]}")
        return None
    body = r.json()
    if not body.get("success"):
        print(f"  ERROR: {body.get('error')}")
        return None
    return base64.b64decode(body["image_base64"])


def generate_probe(server_url: str, baseline: str, probe: str,
                       step_range: tuple, block_range: tuple, stream: str,
                       seed: int, timeout=TIMEOUT) -> Optional[bytes]:
    """Generate one probe image at a specific (step_range, block_range, stream) region."""
    payload = {
        "baseline_prompt": baseline,
        "probe_prompt": probe,
        "probe_step_range": list(step_range),
        "probe_block_range": list(block_range),
        "probe_stream": stream,
        "negative_prompt": "",
        "width": WIDTH,
        "height": HEIGHT,
        "steps": STEPS,
        "cfg_scale": CFG,
        "seed": seed,
    }
    r = requests.post(f"{server_url}/api/fusion_workbench/position_probe",
                      json=payload, timeout=timeout)
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:200]}")
        return None
    body = r.json()
    if not body.get("success"):
        print(f"  ERROR: {body.get('error')}")
        return None
    return base64.b64decode(body["image_base64"])


def _load_fonts():
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 22)
        font_axis = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 16)
        font_label = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 13)
        font_small = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 11)
        return font_title, font_axis, font_label, font_small
    except OSError:
        d = ImageFont.load_default()
        return d, d, d, d


def build_stream_grid(images: dict, stream: str, primitive: str,
                      baseline_prompt: str, seed: int,
                      baseline_bytes: Optional[bytes], target_bytes: Optional[bytes],
                      out_path: Path):
    """
    Build a 3-rows × 3-cols grid for one stream.
    Rows = step phases (composition / semantics / detail),
    Columns = layer bands (shallow / middle / deep).
    Top: baseline + target reference thumbnails.
    """
    thumb = 384
    margin = 10
    label_w = 130   # row label width (wider for phase names)
    header_h = 70   # column labels height
    title_h = 100   # title + reference thumbs
    ref_thumb = 120

    cols = len(LAYER_BANDS)
    rows = len(STEP_PHASES)

    grid_w = label_w + cols * (thumb + margin) + margin
    grid_h = title_h + header_h + rows * (thumb + margin) + margin

    grid = Image.new("RGB", (grid_w, grid_h), (16, 16, 16))
    draw = ImageDraw.Draw(grid)
    f_title, f_axis, f_label, f_small = _load_fonts()

    # Title
    title = f"Position Probe (bands) — primitive: '{primitive}'   stream: {stream}   seed: {seed}"
    draw.text((margin, 10), title, fill=(220, 220, 220), font=f_title)
    baseline_repr = f"'{baseline_prompt}'" if baseline_prompt else "'' (empty string)"
    draw.text((margin, 40), f"baseline_prompt: {baseline_repr}   "
              f"(rows = step phases, cols = layer bands)",
              fill=(160, 160, 160), font=f_small)

    # Reference thumbnails (top-right)
    refs_x = grid_w - 2 * (ref_thumb + margin) - margin
    refs_y = 10
    if baseline_bytes:
        im = Image.open(io.BytesIO(baseline_bytes)).convert("RGB").resize(
            (ref_thumb, ref_thumb), Image.LANCZOS)
        grid.paste(im, (refs_x, refs_y))
        draw.text((refs_x, refs_y + ref_thumb + 2), "baseline",
                  fill=(180, 180, 180), font=f_small)
    if target_bytes:
        x2 = refs_x + ref_thumb + margin
        im = Image.open(io.BytesIO(target_bytes)).convert("RGB").resize(
            (ref_thumb, ref_thumb), Image.LANCZOS)
        grid.paste(im, (x2, refs_y))
        draw.text((x2, refs_y + ref_thumb + 2), f"target ({primitive})",
                  fill=(180, 180, 180), font=f_small)

    # Column headers (layer bands)
    for c, (band_name, (b_lo, b_hi)) in enumerate(LAYER_BANDS):
        x = label_w + c * (thumb + margin) + thumb // 2
        y = title_h + 10
        draw.text((x - 40, y), band_name, fill=(220, 220, 220), font=f_axis)
        draw.text((x - 50, y + 20), f"blocks {b_lo}-{b_hi-1}",
                  fill=(160, 160, 160), font=f_small)

    # Cells
    for r, (phase_name, srange) in enumerate(STEP_PHASES):
        # Row label
        y_lab = title_h + header_h + r * (thumb + margin) + thumb // 2 - 16
        draw.text((6, y_lab), phase_name, fill=(220, 220, 220), font=f_label)
        draw.text((6, y_lab + 18), f"steps {srange[0]}-{srange[1]-1}",
                  fill=(160, 160, 160), font=f_small)

        for c, (band_name, brange) in enumerate(LAYER_BANDS):
            x = label_w + c * (thumb + margin)
            y = title_h + header_h + r * (thumb + margin)

            key = (srange, brange, stream)
            img_bytes = images.get(key)
            if img_bytes:
                im = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize(
                    (thumb, thumb), Image.LANCZOS)
                grid.paste(im, (x, y))
            else:
                draw.rectangle([x, y, x + thumb, y + thumb], outline=(70, 70, 70))
                draw.text((x + thumb // 2 - 40, y + thumb // 2 - 6), "(missing)",
                          fill=(180, 80, 80), font=f_label)

    grid.save(out_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=17802)
    p.add_argument("--primitive", type=str, default="a cannonball",
                   help="The probe prompt — one lexically unitary primitive (English).")
    p.add_argument("--baseline", type=str, default="",
                   help="The baseline prompt. Default '' (empty string = unconditional default).")
    p.add_argument("--seed", type=int, default=123456789,
                   help="RNG seed. Default 123456789 (platform standard).")
    p.add_argument("--out-dir", type=str, required=True)
    args = p.parse_args()

    server_url = f"http://localhost:{args.port}"
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    per_image_dir = out_dir / "per_image"
    per_image_dir.mkdir(exist_ok=True)

    baseline_prompt = args.baseline
    seed = args.seed

    baseline_repr = f"'{baseline_prompt}'" if baseline_prompt else "'' (empty string)"

    print(f"Position-Probe Sweep (bands)")
    print(f"  baseline_prompt: {baseline_repr}")
    print(f"  probe_prompt:    '{args.primitive}'")
    print(f"  seed={seed}, steps={STEPS}")
    print(f"  step phases: {STEP_PHASES}")
    print(f"  layer bands: {LAYER_BANDS}")
    print(f"  streams: {STREAMS}")
    print(f"  total sweep images: {len(STEP_PHASES) * len(LAYER_BANDS) * len(STREAMS)}")
    print(f"  out: {out_dir}\n")

    t_start = time.time()

    # 1. Baseline image (no probe)
    print(f"[1] baseline ({baseline_repr}, no probe)...")
    t0 = time.time()
    baseline_bytes = generate_simple(server_url, baseline_prompt, seed)
    if baseline_bytes is None:
        print("FAIL: baseline. Aborting.")
        return 1
    (out_dir / "00_baseline.png").write_bytes(baseline_bytes)
    print(f"    {time.time()-t0:.1f}s  hash={png_hash(baseline_bytes)}")

    # 2. Target image (primitive as normal prompt)
    print(f"[2] target ('{args.primitive}', no probe)...")
    t0 = time.time()
    target_bytes = generate_simple(server_url, args.primitive, seed)
    if target_bytes is None:
        print("FAIL: target. Aborting.")
        return 1
    (out_dir / "01_target.png").write_bytes(target_bytes)
    print(f"    {time.time()-t0:.1f}s  hash={png_hash(target_bytes)}\n")

    # 3. Sweep
    images = {}  # (step_range, block_range, stream) -> bytes
    summary = {
        "baseline_prompt": baseline_prompt,
        "probe_prompt": args.primitive,
        "seed": seed,
        "steps": STEPS,
        "cfg_scale": CFG,
        "step_phases": [(name, list(r)) for name, r in STEP_PHASES],
        "layer_bands": [(name, list(r)) for name, r in LAYER_BANDS],
        "streams": STREAMS,
        "baseline_hash": png_hash(baseline_bytes),
        "target_hash": png_hash(target_bytes),
        "sweep": [],
    }

    total = len(STEP_PHASES) * len(LAYER_BANDS) * len(STREAMS)
    idx = 0
    for stream in STREAMS:
        print(f"=== stream: {stream} ===")
        for phase_name, srange in STEP_PHASES:
            for band_name, brange in LAYER_BANDS:
                idx += 1
                t0 = time.time()
                b = generate_probe(server_url, baseline_prompt, args.primitive,
                                       srange, brange, stream, seed)
                dt = time.time() - t0
                cell_id = f"{phase_name}×{band_name}"
                if b is None:
                    print(f"  [{idx:2d}/{total}] {cell_id:<24s}: FAIL")
                    summary["sweep"].append({
                        "phase": phase_name, "step_range": list(srange),
                        "band": band_name, "block_range": list(brange),
                        "stream": stream, "ok": False,
                    })
                    continue
                images[(srange, brange, stream)] = b
                h = png_hash(b)
                fname = f"{stream}_{phase_name}_{band_name}.png"
                (per_image_dir / fname).write_bytes(b)
                print(f"  [{idx:2d}/{total}] {cell_id:<24s}: {dt:5.1f}s  hash={h}")
                summary["sweep"].append({
                    "phase": phase_name, "step_range": list(srange),
                    "band": band_name, "block_range": list(brange),
                    "stream": stream, "ok": True, "hash": h, "file": fname,
                })
        print()

    # 4. Build per-stream grids
    for stream in STREAMS:
        out_path = out_dir / f"grid_{stream}.png"
        build_stream_grid(images, stream, args.primitive,
                          baseline_prompt, seed,
                          baseline_bytes, target_bytes, out_path)
        print(f"  grid: {out_path.name}")

    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )

    total_sec = time.time() - t_start
    print(f"\nTotal: {total_sec/60:.1f} min  ({total_sec:.0f}s)")
    print(f"Outputs: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
