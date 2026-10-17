#!/usr/bin/env python3
"""Per-block delayed kickin sweep — all 38 SD3.5 transformer blocks individually.

Hooks one block at a time. For each block, runs the standard 10-value
kickin grid (same as previous band sweeps so results are directly comparable).

Output: /tmp/kickin_perblock_s123/block_NN/kickin_KK.png
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

# connect, read: a run stands in the plant-wide GPU queue before it renders, up
# to an hour and a half (GPU_ADMISSION_ACQUIRE_TIMEOUT_S); a read cap ends the
# wait, never the run.
TIMEOUT = (10, None)


# The port the DevServer answers on: the override server.py reads, so a sweep
# a running server launches (my_app/routes/dev_routes.py) posts back to that
# server, on 17801 in production as on 17802 here; --port names another.
SERVER_URL = f"http://localhost:{os.getenv('PORT', '17802')}"
KICKIN_STEPS = [0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 14, 18, 23]
DEFAULT_SEED = 123456789
NUM_BLOCKS = 38
DEFAULT_prompt_early = "ocean"
DEFAULT_prompt_full = "ocean and a ship"

W = H = 1024
STEPS = 25
CFG = 5.5

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_BASE = PROJECT_ROOT / "devserver" / "research_data" / "kickin"

# Block visiting order: first the stratified-sample priority blocks (extremes
# inward), then fill remaining gaps alternating low/high.
PRIORITY_BLOCKS = [0, 37, 5, 32, 10, 22, 16]


def _ensure_dataset_metadata(dataset_id: str, prompt_early: str, prompt_full: str, seed: int):
    """Write metadata.json for the dataset if it doesn't exist yet.
    Existing files are left untouched (preserves manual labels/notes)."""
    ds_dir = RESEARCH_BASE / dataset_id
    ds_dir.mkdir(parents=True, exist_ok=True)
    meta_file = ds_dir / "metadata.json"
    if meta_file.exists():
        return
    meta = {
        "id": dataset_id,
        "label": f"{prompt_early} → {prompt_full} (seed {seed})",
        "prompt_early": prompt_early,
        "prompt_full": prompt_full,
        "seed": seed,
        "steps": STEPS,
        "cfg": CFG,
        "width": W,
        "height": H,
        "kickin_steps": KICKIN_STEPS,
        "model": "stabilityai/stable-diffusion-3.5-large",
    }
    import json as _json
    meta_file.write_text(_json.dumps(meta, indent=2, ensure_ascii=False))


def build_block_order():
    visited = list(PRIORITY_BLOCKS)
    remaining = sorted(set(range(NUM_BLOCKS)) - set(visited))
    lo = [b for b in remaining if b < NUM_BLOCKS // 2]
    hi = [b for b in remaining if b >= NUM_BLOCKS // 2]
    lo.sort()
    hi.sort(reverse=True)
    fill = []
    li = hi_i = 0
    while li < len(lo) or hi_i < len(hi):
        if li < len(lo):
            fill.append(lo[li]); li += 1
        if hi_i < len(hi):
            fill.append(hi[hi_i]); hi_i += 1
    return visited + fill


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-id", type=str, default="ds_001")
    p.add_argument("--prompt-early", type=str, default=DEFAULT_prompt_early)
    p.add_argument("--prompt-full",  type=str, default=DEFAULT_prompt_full)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--server-url", type=str, default=SERVER_URL,
                   help="DevServer (default: http://localhost:$PORT, else :17802)")
    p.add_argument("--out-dir", type=str, default=None,
                   help="Override output directory (else derived from dataset-id)")
    p.add_argument("--start-block", type=int, default=0)
    p.add_argument("--end-block", type=int, default=NUM_BLOCKS)
    args = p.parse_args()

    if args.out_dir:
        base = Path(args.out_dir).resolve()
    else:
        base = (RESEARCH_BASE / args.dataset_id / "perblock").resolve()
    base.mkdir(parents=True, exist_ok=True)

    server_url = args.server_url
    prompt_early = args.prompt_early
    prompt_full = args.prompt_full
    seed = args.seed

    _ensure_dataset_metadata(args.dataset_id, prompt_early, prompt_full, seed)

    full_order = build_block_order()
    blocks = [b for b in full_order if args.start_block <= b < args.end_block]
    total = len(blocks) * len(KICKIN_STEPS)
    done = 0
    t0 = time.time()

    print(f"Per-block kickin sweep")
    print(f"  blocks: {blocks[0]}..{blocks[-1]}  ({len(blocks)} blocks)")
    print(f"  kickin steps: {KICKIN_STEPS}")
    print(f"  total generations: {total}")
    print(f"  output: {base}")
    print(f"  prompt_early='{prompt_early}'  prompt_full='{prompt_full}'  seed={seed}", flush=True)

    for block in blocks:
        block_dir = base / f"block_{block:02d}"
        block_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "block": block,
            "prompt_early": prompt_early,
            "prompt_full": prompt_full,
            "seed": seed,
            "steps": STEPS,
            "cfg": CFG,
            "kickin_steps": KICKIN_STEPS,
            "results": [],
        }

        for k in KICKIN_STEPS:
            done += 1
            elapsed = time.time() - t0
            eta = (elapsed / done * (total - done)) if done > 0 else 0
            print(f"[{done:4d}/{total}] block={block:02d} k={k:2d}  "
                  f"elapsed={elapsed/60:.1f}m  eta={eta/60:.1f}m", flush=True)

            payload = {
                "prompt_early": prompt_early,
                "prompt_full": prompt_full,
                "kickin_step": k,
                "block_range": [block, block + 1],
                "negative_prompt": "",
                "width": W,
                "height": H,
                "steps": STEPS,
                "cfg_scale": CFG,
                "seed": seed,
            }
            try:
                r = requests.post(
                    f"{server_url}/api/fusion_workbench/delayed_kickin",
                    json=payload, timeout=TIMEOUT,
                )
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                if r.status_code == 200 and body.get("success"):
                    img_bytes = base64.b64decode(body["image_base64"])
                    fname = f"kickin_{k:02d}.png"
                    (block_dir / fname).write_bytes(img_bytes)
                    summary["results"].append({"step": k, "file": fname, "ok": True,
                                                "bytes": len(img_bytes)})
                else:
                    err = body.get("error") if body else r.text[:200]
                    print(f"  FAIL: {err}", flush=True)
                    summary["results"].append({"step": k, "ok": False, "error": err})
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                summary["results"].append({"step": k, "ok": False, "error": str(e)})

        (block_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"  block {block:02d} complete → {block_dir}", flush=True)

    elapsed = time.time() - t0
    print(f"\nAll blocks done in {elapsed/60:.1f} minutes.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
