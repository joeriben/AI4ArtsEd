#!/usr/bin/env python3
"""
Delayed Kick-In Probe — SD3.5 Large MMDiT

Tests how late in the diffusion process the second part of a compound prompt
can be introduced and still produce its visual content.

Setup:
  prompt_early = "ocean"
  prompt_full  = "ocean and a ship"

For each kickin_step value, the conditioning starts as prompt_early and
switches to prompt_full at the specified step. Switch is implemented at
block 0 of the transformer; subsequent blocks propagate the change naturally.

Default kickin grid: {0, 1, 4, 7, 10, 13, 16, 19, 22, 25}
  0  = prompt_full throughout (reference: full image)
  25 = prompt_early throughout (reference: ocean only, no ship ever)
  1..22 = ship "kicks in" at that step

Usage:
  python test_delayed_kickin.py --out-dir /tmp/kickin_ocean_ship_s123 --seed 123456789
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


DEFAULT_KICKIN_STEPS = [0, 1, 4, 7, 10, 13, 16, 19, 22, 25]
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


def generate_kickin(server_url: str, prompt_early: str, prompt_full: str,
                    kickin_step: int, seed: int,
                    block_range: Optional[list] = None,
                    timeout=TIMEOUT) -> Optional[bytes]:
    payload = {
        "prompt_early": prompt_early,
        "prompt_full": prompt_full,
        "kickin_step": kickin_step,
        "negative_prompt": "",
        "width": WIDTH,
        "height": HEIGHT,
        "steps": STEPS,
        "cfg_scale": CFG,
        "seed": seed,
    }
    if block_range is not None:
        payload["block_range"] = list(block_range)
    r = requests.post(f"{server_url}/api/fusion_workbench/delayed_kickin",
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
        font_label = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 12)
        return font_title, font_label, font_small
    except OSError:
        d = ImageFont.load_default()
        return d, d, d


def build_strip(images: dict, kickin_steps: list, prompt_early: str,
                prompt_full: str, seed: int, out_path: Path):
    """Build a horizontal strip showing all kickin_step results in order."""
    thumb = 384
    margin = 8
    label_h = 50
    title_h = 70

    n = len(kickin_steps)
    grid_w = n * (thumb + margin) + margin
    grid_h = title_h + thumb + label_h + 2 * margin

    grid = Image.new("RGB", (grid_w, grid_h), (16, 16, 16))
    draw = ImageDraw.Draw(grid)
    f_title, f_label, f_small = _load_fonts()

    title = f"Delayed Kick-In — prompt_early: '{prompt_early}'  |  prompt_full: '{prompt_full}'  |  seed: {seed}"
    draw.text((margin, 8), title, fill=(220, 220, 220), font=f_title)
    draw.text((margin, 38), f"each column = different kickin_step; the second prompt component takes over from that step onwards",
              fill=(160, 160, 160), font=f_small)

    for i, k in enumerate(kickin_steps):
        x = margin + i * (thumb + margin)
        y = title_h
        b = images.get(k)
        if b:
            im = Image.open(io.BytesIO(b)).convert("RGB").resize(
                (thumb, thumb), Image.LANCZOS)
            grid.paste(im, (x, y))
        else:
            draw.rectangle([x, y, x + thumb, y + thumb], outline=(70, 70, 70))
            draw.text((x + thumb // 2 - 30, y + thumb // 2),
                      "(missing)", fill=(180, 80, 80), font=f_label)

        y_lab = y + thumb + 6
        if k == 0:
            lab = "k=0 (full)"
        elif k >= STEPS:
            lab = f"k={k} (early only)"
        else:
            lab = f"k={k}"
        draw.text((x + 6, y_lab), lab, fill=(220, 220, 220), font=f_label)
        if 0 < k < STEPS:
            draw.text((x + 6, y_lab + 20),
                      f"early: steps 0-{k-1}, full: steps {k}-{STEPS-1}",
                      fill=(150, 150, 150), font=f_small)

    grid.save(out_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=17802)
    p.add_argument("--prompt-early", type=str, default="ocean")
    p.add_argument("--prompt-full",  type=str, default="ocean and a ship")
    p.add_argument("--seed", type=int, default=123456789)
    p.add_argument("--kickin-steps", type=str,
                   default=",".join(map(str, DEFAULT_KICKIN_STEPS)),
                   help="Comma-separated kickin_step values")
    p.add_argument("--block-range", type=str, default=None,
                   help="lo,hi (half-open) — installs hook on every block in range. "
                        "Default: hook on block 0 only (switch propagates everywhere).")
    p.add_argument("--out-dir", type=str, required=True)
    args = p.parse_args()

    kickin_steps = [int(x.strip()) for x in args.kickin_steps.split(",")]
    block_range = None
    if args.block_range:
        parts = args.block_range.split(",")
        if len(parts) != 2:
            raise SystemExit(f"--block-range must be 'lo,hi', got {args.block_range!r}")
        block_range = [int(parts[0]), int(parts[1])]

    server_url = f"http://localhost:{args.port}"
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Delayed Kick-In Probe")
    print(f"  prompt_early: '{args.prompt_early}'")
    print(f"  prompt_full:  '{args.prompt_full}'")
    print(f"  seed={args.seed}, steps={STEPS}")
    print(f"  kickin_steps: {kickin_steps}")
    if block_range:
        print(f"  block_range: {block_range}")
    else:
        print(f"  block_range: default (block 0 only)")
    print(f"  out: {out_dir}\n")

    images = {}
    summary = {
        "prompt_early": args.prompt_early,
        "prompt_full": args.prompt_full,
        "seed": args.seed,
        "steps": STEPS,
        "cfg_scale": CFG,
        "kickin_steps": kickin_steps,
        "results": [],
    }

    t_start = time.time()
    for i, k in enumerate(kickin_steps):
        t0 = time.time()
        b = generate_kickin(server_url, args.prompt_early, args.prompt_full,
                                k, args.seed, block_range=block_range)
        dt = time.time() - t0
        if b is None:
            print(f"  [{i+1:2d}/{len(kickin_steps)}] kickin_step={k:2d}: FAIL")
            summary["results"].append({"kickin_step": k, "ok": False})
            continue
        images[k] = b
        h = png_hash(b)
        fname = f"kickin_{k:02d}.png"
        (out_dir / fname).write_bytes(b)
        if k == 0:
            label = " (full prompt throughout)"
        elif k >= STEPS:
            label = " (early prompt throughout)"
        else:
            label = ""
        print(f"  [{i+1:2d}/{len(kickin_steps)}] kickin_step={k:2d}{label}: {dt:5.1f}s  hash={h}")
        summary["results"].append({
            "kickin_step": k, "ok": True, "hash": h, "file": fname,
        })

    # Build strip
    strip_path = out_dir / "strip.png"
    build_strip(images, kickin_steps, args.prompt_early, args.prompt_full,
                args.seed, strip_path)
    print(f"\n  strip: {strip_path.name}")

    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )

    print(f"\nTotal: {(time.time()-t_start):.0f}s")
    print(f"Outputs: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
