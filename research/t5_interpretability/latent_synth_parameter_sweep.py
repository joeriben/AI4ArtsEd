#!/usr/bin/env python3
"""
Latent Audio Synth — Parameter Sweep: Steps × Duration × Start Position

Tests whether Stable Audio Open can produce semantically differentiated output
at sub-second durations and low step counts. Answers three questions:

  1. At what duration does semantic differentiation collapse?
  2. At what step count does quality degrade unacceptably?
  3. Does start_position > 0 improve loop-quality (less transient, more sustain)?

Method:
  - Two contrasting prompts (bright/metallic vs. dark/rumble)
  - For each (duration, steps, start_position): generate both prompts
  - Extract librosa spectral features from each
  - Compute discrimination score (Cohen's d across feature set)
  - A score near 0 means the model can no longer differentiate the prompts

Grid: 6 durations × 5 step counts × 2 start positions × 2 prompts = 120 generations
Estimated runtime: 5–15 minutes depending on GPU.

Usage: venv/bin/python research/t5_interpretability/latent_synth_parameter_sweep.py
"""

import base64
import io
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

GPU_SERVICE_URL = "http://localhost:17803"

PROMPT_A = "bright metallic tone, high pitch"
PROMPT_B = "dark low rumble, subsonic"

DURATIONS = [0.1, 0.2, 0.3, 0.5, 1.0, 2.0]
STEPS = [5, 10, 20, 50, 100]
START_POSITIONS = [0.0, 0.5]

CFG = 7.0
SEED = 42

OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "parameter_sweep"


# ── Audio Generation ─────────────────────────────────────────────────────────

def generate_synth(
    prompt: str, duration: float, steps: int, start_position: float, seed: int
) -> bytes | None:
    """Call GPU service cross_aesthetic/synth endpoint."""
    url = f"{GPU_SERVICE_URL}/api/cross_aesthetic/synth"
    payload = {
        "prompt_a": prompt,
        "alpha": 0.5,
        "magnitude": 1.0,
        "noise_sigma": 0.0,
        "duration_seconds": duration,
        "start_position": start_position,
        "steps": steps,
        "cfg_scale": CFG,
        "seed": seed,
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return base64.b64decode(data["audio_base64"])
        else:
            logger.error(f"Generation failed: {data.get('error')}")
            return None
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None


# ── Feature Extraction ───────────────────────────────────────────────────────

def extract_features(wav_bytes: bytes) -> dict | None:
    """Extract spectral features from WAV bytes."""
    try:
        y, sr = librosa.load(io.BytesIO(wav_bytes), sr=None, mono=True)

        if len(y) == 0 or np.abs(y).max() < 1e-6:
            return {"silent": True}

        features = {}

        # Spectral centroid (brightness)
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        features["spectral_centroid_mean"] = float(np.mean(cent))
        features["spectral_centroid_std"] = float(np.std(cent))

        # Spectral flatness (noise vs tone)
        flat = librosa.feature.spectral_flatness(y=y)
        features["spectral_flatness_mean"] = float(np.mean(flat))

        # RMS energy
        rms = librosa.feature.rms(y=y)
        features["rms_mean"] = float(np.mean(rms))
        features["rms_std"] = float(np.std(rms))

        # Spectral bandwidth
        bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        features["spectral_bandwidth_mean"] = float(np.mean(bw))

        # Zero-crossing rate
        zcr = librosa.feature.zero_crossing_rate(y)
        features["zcr_mean"] = float(np.mean(zcr))

        # Spectral flux (temporal change)
        S = np.abs(librosa.stft(y))
        if S.shape[1] > 1:
            flux = np.sqrt(np.sum(np.diff(S, axis=1) ** 2, axis=0))
            features["spectral_flux_mean"] = float(np.mean(flux))
        else:
            features["spectral_flux_mean"] = 0.0

        # Spectral rolloff (high-frequency content)
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        features["spectral_rolloff_mean"] = float(np.mean(rolloff))

        features["silent"] = False
        return features

    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        return None


# ── Discrimination Score ─────────────────────────────────────────────────────

def discrimination_score(feat_a: dict, feat_b: dict) -> float:
    """
    Compute a simple discrimination score between two feature dicts.
    Uses mean absolute normalized difference across all numeric features.
    Returns 0 if identical, higher = more discriminable.
    """
    if feat_a is None or feat_b is None:
        return -1.0
    if feat_a.get("silent") or feat_b.get("silent"):
        return -1.0

    keys = [k for k in feat_a if k != "silent" and k in feat_b]
    if not keys:
        return -1.0

    diffs = []
    for k in keys:
        a, b = feat_a[k], feat_b[k]
        denom = max(abs(a), abs(b), 1e-8)
        diffs.append(abs(a - b) / denom)

    return float(np.mean(diffs))


# ── Transient Analysis ───────────────────────────────────────────────────────

def transient_ratio(wav_bytes: bytes) -> float | None:
    """
    Estimate what fraction of the signal energy is in the first 20%.
    High = attack-heavy, low = sustained.
    """
    try:
        y, sr = librosa.load(io.BytesIO(wav_bytes), sr=None, mono=True)
        if len(y) == 0 or np.abs(y).max() < 1e-6:
            return None
        boundary = len(y) // 5
        energy_head = float(np.sum(y[:boundary] ** 2))
        energy_total = float(np.sum(y ** 2))
        return energy_head / energy_total if energy_total > 0 else 0.0
    except Exception:
        return None


# ── Main ─────────────────────────────────────────────────────────────────────

def check_gpu_service() -> bool:
    """Verify GPU service is reachable."""
    try:
        resp = requests.get(f"{GPU_SERVICE_URL}/api/cross_aesthetic/available", timeout=5)
        data = resp.json()
        if data.get("available") and data.get("backends", {}).get("synth"):
            return True
        logger.error(f"GPU service not ready: {data}")
        return False
    except Exception as e:
        logger.error(f"GPU service unreachable: {e}")
        return False


def main():
    if not check_gpu_service():
        logger.error("GPU service not available. Start it first.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(DURATIONS) * len(STEPS) * len(START_POSITIONS) * 2
    logger.info(f"Starting parameter sweep: {total} generations")
    logger.info(f"Prompt A: {PROMPT_A}")
    logger.info(f"Prompt B: {PROMPT_B}")

    results = []
    gen_count = 0
    start_time = time.time()

    for duration in DURATIONS:
        for steps in STEPS:
            for start_pos in START_POSITIONS:
                condition = f"d={duration}s_st={steps}_sp={start_pos}"

                # Generate both prompts
                wav_a = generate_synth(PROMPT_A, duration, steps, start_pos, SEED)
                gen_count += 1
                wav_b = generate_synth(PROMPT_B, duration, steps, start_pos, SEED)
                gen_count += 1

                elapsed = time.time() - start_time
                rate = elapsed / gen_count if gen_count > 0 else 0
                remaining = rate * (total - gen_count)

                if wav_a is None or wav_b is None:
                    logger.warning(f"  {condition}: generation failed")
                    results.append({
                        "duration": duration, "steps": steps, "start_position": start_pos,
                        "discrimination": -1.0, "transient_a": None, "transient_b": None,
                        "features_a": None, "features_b": None, "error": True,
                    })
                    continue

                # Save WAVs
                for label, wav in [("A", wav_a), ("B", wav_b)]:
                    wav_path = OUTPUT_DIR / f"{condition}_{label}.wav"
                    wav_path.write_bytes(wav)

                # Extract features
                feat_a = extract_features(wav_a)
                feat_b = extract_features(wav_b)

                # Discrimination
                disc = discrimination_score(feat_a, feat_b)

                # Transient analysis
                tr_a = transient_ratio(wav_a)
                tr_b = transient_ratio(wav_b)

                results.append({
                    "duration": duration,
                    "steps": steps,
                    "start_position": start_pos,
                    "discrimination": round(disc, 4),
                    "transient_a": round(tr_a, 4) if tr_a is not None else None,
                    "transient_b": round(tr_b, 4) if tr_b is not None else None,
                    "features_a": feat_a,
                    "features_b": feat_b,
                })

                disc_str = f"{disc:.3f}" if disc >= 0 else "FAIL"
                tr_str = f"tr_A={tr_a:.2f} tr_B={tr_b:.2f}" if tr_a and tr_b else "N/A"
                logger.info(
                    f"  [{gen_count}/{total}] {condition}: disc={disc_str}, {tr_str}"
                    f"  (~{remaining:.0f}s remaining)"
                )

    total_time = time.time() - start_time
    logger.info(f"Sweep complete: {gen_count} generations in {total_time:.1f}s")

    # ── Save raw results ──
    results_path = OUTPUT_DIR / "results.json"
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "config": {
                "prompt_a": PROMPT_A, "prompt_b": PROMPT_B,
                "durations": DURATIONS, "steps": STEPS,
                "start_positions": START_POSITIONS,
                "cfg": CFG, "seed": SEED,
            },
            "total_time_seconds": round(total_time, 1),
            "results": results,
        }, f, indent=2)

    # ── Generate report ──
    report = generate_report(results, total_time)
    report_path = OUTPUT_DIR / "report.md"
    report_path.write_text(report)
    logger.info(f"Report: {report_path}")
    print("\n" + report)


def generate_report(results: list[dict], total_time: float) -> str:
    """Generate a markdown report from sweep results."""
    lines = [
        "# Latent Audio Synth — Parameter Sweep Results",
        f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total time:** {total_time:.1f}s",
        f"**Prompts:** A=\"{PROMPT_A}\" vs B=\"{PROMPT_B}\"",
        "",
        "## Discrimination Score (A vs B)",
        "",
        "Higher = model can tell the prompts apart. < 0.05 ≈ indistinguishable.",
        "",
    ]

    # Table: Duration × Steps, for start_position=0.0
    for sp in START_POSITIONS:
        lines.append(f"\n### Start Position = {sp:.0%}")
        lines.append("")
        header = "| Duration |" + "|".join(f" {s} steps " for s in STEPS) + "|"
        sep = "|---------|" + "|".join("--------" for _ in STEPS) + "|"
        lines.extend([header, sep])

        for dur in DURATIONS:
            row = f"| {dur}s |"
            for st in STEPS:
                r = next(
                    (x for x in results
                     if x["duration"] == dur and x["steps"] == st
                     and x["start_position"] == sp),
                    None,
                )
                if r is None or r.get("error"):
                    row += " ERR |"
                elif r["discrimination"] < 0:
                    row += " FAIL |"
                else:
                    d = r["discrimination"]
                    marker = " **" if d < 0.05 else ""
                    end = "**" if d < 0.05 else ""
                    row += f" {marker}{d:.3f}{end} |"
            lines.append(row)

    # Transient ratio analysis
    lines.extend([
        "",
        "## Transient Ratio (energy in first 20% of signal)",
        "",
        "Lower = more sustained material. 0.20 = perfectly uniform.",
        "",
    ])

    for sp in START_POSITIONS:
        lines.append(f"\n### Start Position = {sp:.0%}")
        lines.append("")

        header = "| Duration |" + "|".join(f" {s} steps " for s in STEPS) + "|"
        sep = "|---------|" + "|".join("--------" for _ in STEPS) + "|"
        lines.extend([header, sep])

        for dur in DURATIONS:
            row = f"| {dur}s |"
            for st in STEPS:
                r = next(
                    (x for x in results
                     if x["duration"] == dur and x["steps"] == st
                     and x["start_position"] == sp),
                    None,
                )
                if r is None or r.get("error") or r["transient_a"] is None:
                    row += " — |"
                else:
                    avg = (r["transient_a"] + r["transient_b"]) / 2
                    row += f" {avg:.3f} |"
            lines.append(row)

    # Key findings
    lines.extend([
        "",
        "## Key Findings",
        "",
    ])

    # Find minimum duration with disc > 0.05 at 100 steps
    for sp in START_POSITIONS:
        min_dur = None
        for dur in DURATIONS:
            r = next(
                (x for x in results
                 if x["duration"] == dur and x["steps"] == 100
                 and x["start_position"] == sp and not x.get("error")),
                None,
            )
            if r and r["discrimination"] > 0.05:
                min_dur = dur
                break
        if min_dur is not None:
            lines.append(
                f"- **Minimum differentiating duration at sp={sp:.0%}, 100 steps:** {min_dur}s"
            )
        else:
            lines.append(
                f"- **sp={sp:.0%}, 100 steps:** no duration produced discriminable output"
            )

    # Find minimum steps with disc > 0.05 at 1.0s
    for sp in START_POSITIONS:
        min_steps = None
        for st in STEPS:
            r = next(
                (x for x in results
                 if x["duration"] == 1.0 and x["steps"] == st
                 and x["start_position"] == sp and not x.get("error")),
                None,
            )
            if r and r["discrimination"] > 0.05:
                min_steps = st
                break
        if min_steps is not None:
            lines.append(
                f"- **Minimum differentiating steps at sp={sp:.0%}, 1.0s:** {min_steps}"
            )

    # Start position effect
    sp0_transients = [
        r["transient_a"] for r in results
        if r["start_position"] == 0.0 and r.get("transient_a") is not None
    ]
    sp5_transients = [
        r["transient_a"] for r in results
        if r["start_position"] == 0.5 and r.get("transient_a") is not None
    ]
    if sp0_transients and sp5_transients:
        avg_0 = np.mean(sp0_transients)
        avg_5 = np.mean(sp5_transients)
        lines.append(
            f"- **Mean transient ratio:** sp=0% → {avg_0:.3f}, sp=50% → {avg_5:.3f}"
            f"  (Δ={avg_0 - avg_5:.3f})"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    main()
