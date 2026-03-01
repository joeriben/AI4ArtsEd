#!/usr/bin/env python3
"""
Remaining Axes LERP Sonification

Generates LERP audio for the 15 axes NOT covered by statistical_threelevel_test.py.
Uses the same output directory structure so the comprehensive analysis script
can read all 21 axes uniformly.

Original 3-level design tested 6 axes:
  - loud↔quiet, complex↔simple (neutral)
  - traditional↔modern, professional↔amateur (biased)
  - tonal↔noisy, music↔noise (constitutive)

This script adds the remaining 15:
  Perceptual: rhythmic↔sustained, bright↔dark, smooth↔harsh,
              dense↔sparse, fast↔slow, close↔distant
  Cultural:   acoustic↔electronic, sacred↔secular, solo↔ensemble,
              improvised↔composed, ceremonial↔everyday, vocal↔instrumental
  Critical:   beautiful↔ugly, authentic↔fusion, refined↔raw

Usage: venv/bin/python research/t5_interpretability/statistical_remaining_axes.py
"""

import base64
import io
import json
import logging
import sys
import time
from pathlib import Path

import librosa
import numpy as np
import requests
import torch
from scipy import stats
from scipy.spatial.distance import cosine as cosine_distance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    T5_MODEL_ID, T5_MAX_LENGTH,
    GPU_SERVICE_URL, DATA_DIR,
)

# ── Experiment Config ─────────────────────────────────────────────────────────

# The 15 remaining axes (matching cultural_drift_analysis.py naming)
AXES = [
    # Perceptual (6 remaining)
    ("rhythmic_sustained", "sound rhythmic", "sound sustained"),
    ("bright_dark", "sound bright", "sound dark"),
    ("smooth_harsh", "sound smooth", "sound harsh"),
    ("dense_sparse", "sound dense", "sound sparse"),
    ("fast_slow", "sound fast", "sound slow"),
    ("close_distant", "sound close", "sound distant"),
    # Cultural (6 remaining)
    ("acoustic_electronic", "acoustic music", "electronic music"),
    ("sacred_secular", "sacred music", "secular music"),
    ("solo_ensemble", "solo music", "ensemble music"),
    ("improvised_composed", "improvised music", "composed music"),
    ("ceremonial_everyday", "ceremonial music", "everyday music"),
    ("vocal_instrumental", "vocal music", "instrumental music"),
    # Critical (3 remaining)
    ("beautiful_ugly", "beautiful sound", "ugly sound"),
    ("authentic_fusion", "authentic music", "fusion music"),
    ("refined_raw", "refined music", "raw music"),
]

LERP_POSITIONS = [0.0, 0.25, 0.5, 0.75, 1.0]
N_SAMPLES = 30  # per LERP position — lower N to fit within time budget
DURATION = 5.0
STEPS = 100
CFG = 7.0

# Same output dir as threelevel test for unified analysis
OUTPUT_DIR = DATA_DIR / "statistical_threelevel_test"


def load_t5():
    from transformers import T5EncoderModel, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(T5_MODEL_ID)
    model = T5EncoderModel.from_pretrained(T5_MODEL_ID).cuda().half()
    model.eval()
    return tokenizer, model


def encode_prompt(text: str, tokenizer, model) -> tuple[np.ndarray, np.ndarray]:
    inputs = tokenizer(
        text,
        return_tensors="pt",
        padding="max_length",
        max_length=T5_MAX_LENGTH,
        truncation=True,
    )
    with torch.no_grad():
        outputs = model(
            input_ids=inputs.input_ids.cuda(),
            attention_mask=inputs.attention_mask.cuda(),
        )
    emb = outputs.last_hidden_state.cpu().float().numpy()
    mask = inputs.attention_mask.cpu().float().numpy()
    return emb, mask


def _numpy_to_b64(arr: np.ndarray) -> str:
    buf = io.BytesIO()
    np.save(buf, arr.astype(np.float32))
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_audio(emb: np.ndarray, mask: np.ndarray, seed: int) -> bytes | None:
    url = f"{GPU_SERVICE_URL}/api/stable_audio/generate_from_embeddings"
    payload = {
        "embeddings_b64": _numpy_to_b64(emb),
        "attention_mask_b64": _numpy_to_b64(mask),
        "duration_seconds": DURATION,
        "steps": STEPS,
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


def extract_features(wav_path: Path) -> dict | None:
    try:
        y, sr = librosa.load(wav_path, sr=None, mono=True)
        if np.abs(y).max() < 1e-6:
            return None

        features = {}

        onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
        duration = len(y) / sr
        features["onset_density"] = len(onset_frames) / duration if duration > 0 else 0

        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        features["spectral_centroid_mean"] = float(np.mean(cent))
        features["spectral_centroid_std"] = float(np.std(cent))

        rms = librosa.feature.rms(y=y)
        features["rms_mean"] = float(np.mean(rms))
        features["rms_std"] = float(np.std(rms))

        flat = librosa.feature.spectral_flatness(y=y)
        features["spectral_flatness_mean"] = float(np.mean(flat))

        zcr = librosa.feature.zero_crossing_rate(y)
        features["zcr_mean"] = float(np.mean(zcr))

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        features["tempo"] = float(np.atleast_1d(tempo)[0])

        bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        features["spectral_bandwidth_mean"] = float(np.mean(bw))

        S = np.abs(librosa.stft(y))
        flux = np.sqrt(np.sum(np.diff(S, axis=1)**2, axis=0))
        features["spectral_flux_mean"] = float(np.mean(flux))
        features["spectral_flux_std"] = float(np.std(flux))

        return features
    except Exception as e:
        logger.error(f"Feature extraction failed for {wav_path}: {e}")
        return None


def run_extreme_comparison(features_a: list[dict], features_b: list[dict]) -> dict:
    results = {}
    all_keys = sorted(features_a[0].keys())

    for key in all_keys:
        vals_a = np.array([f[key] for f in features_a])
        vals_b = np.array([f[key] for f in features_b])

        t_stat, p_value = stats.ttest_ind(vals_a, vals_b, equal_var=False)
        pooled_std = np.sqrt((vals_a.std()**2 + vals_b.std()**2) / 2)
        cohens_d = (vals_a.mean() - vals_b.mean()) / pooled_std if pooled_std > 0 else 0

        results[key] = {
            "mean_a": float(vals_a.mean()),
            "mean_b": float(vals_b.mean()),
            "cohens_d": float(cohens_d),
            "p_value": float(p_value),
            "significant_001": bool(p_value < 0.001),
            "significant_01": bool(p_value < 0.01),
            "significant_05": bool(p_value < 0.05),
        }

    return results


def compute_gradient(all_features: dict[float, list[dict]]) -> dict:
    feature_keys = sorted(all_features[LERP_POSITIONS[0]][0].keys())
    gradient = {}

    for key in feature_keys:
        positions = []
        values = []
        for t in sorted(all_features.keys()):
            for feat in all_features[t]:
                positions.append(t)
                values.append(feat[key])

        positions = np.array(positions)
        values = np.array(values)

        r, p = stats.pearsonr(positions, values)
        rho, rho_p = stats.spearmanr(positions, values)

        pos_means = {}
        for t in sorted(all_features.keys()):
            vals = [f[key] for f in all_features[t]]
            pos_means[f"mean_{t:.2f}"] = float(np.mean(vals))

        gradient[key] = {
            "pearson_r": float(r),
            "pearson_p": float(p),
            "spearman_rho": float(rho),
            "spearman_p": float(rho_p),
            **pos_means,
        }

    return gradient


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_samples = len(AXES) * len(LERP_POSITIONS) * N_SAMPLES
    logger.info(f"Remaining axes: {len(AXES)} axes × {len(LERP_POSITIONS)} positions × N={N_SAMPLES} = {total_samples} samples")

    # Check what needs generation
    need_generation = False
    for axis_label, prompt_a, prompt_b in AXES:
        for t in LERP_POSITIONS:
            d = OUTPUT_DIR / axis_label / f"lerp_{t:.2f}"
            if not d.exists() or len(list(d.glob("*.wav"))) < N_SAMPLES:
                need_generation = True
                break
        if need_generation:
            break

    if need_generation:
        logger.info("Loading T5...")
        tokenizer, model = load_t5()

        # Encode all poles
        axis_data = {}
        for axis_label, prompt_a, prompt_b in AXES:
            logger.info(f"Encoding {axis_label}: '{prompt_a}' / '{prompt_b}'")
            emb_a, mask_a = encode_prompt(prompt_a, tokenizer, model)
            emb_b, mask_b = encode_prompt(prompt_b, tokenizer, model)
            axis_data[axis_label] = {
                "emb_a": emb_a, "emb_b": emb_b,
                "mask_a": mask_a, "mask_b": mask_b,
            }

        del model
        torch.cuda.empty_cache()

        # Generate audio
        done = 0
        start_time = time.time()

        for axis_label, prompt_a, prompt_b in AXES:
            ae = axis_data[axis_label]

            for t in LERP_POSITIONS:
                out_dir = OUTPUT_DIR / axis_label / f"lerp_{t:.2f}"
                out_dir.mkdir(parents=True, exist_ok=True)

                existing = len(list(out_dir.glob("*.wav")))
                if existing >= N_SAMPLES:
                    logger.info(f"  {axis_label}/lerp_{t:.2f}: {existing} files, skipping")
                    done += N_SAMPLES
                    continue

                emb = (1.0 - t) * ae["emb_b"] + t * ae["emb_a"]
                mask = ae["mask_a"]

                logger.info(f"  Generating {axis_label}/lerp_{t:.2f}...")

                for seed in range(N_SAMPLES):
                    out_path = out_dir / f"seed_{seed:03d}.wav"
                    if out_path.exists():
                        done += 1
                        continue

                    audio = generate_audio(emb, mask, seed)
                    if audio:
                        with open(out_path, "wb") as f:
                            f.write(audio)

                    done += 1
                    if done % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = done / elapsed if elapsed > 0 else 0
                        eta = (total_samples - done) / rate if rate > 0 else 0
                        logger.info(
                            f"    [{done}/{total_samples}] ({rate:.1f}/sec, ETA {eta:.0f}s)"
                        )
    else:
        logger.info("All samples exist, skipping generation")

    # Per-axis analysis (quick, for intermediate results)
    logger.info("Extracting features and computing per-axis statistics...")
    per_axis_results = {}

    for axis_label, prompt_a, prompt_b in AXES:
        axis_features: dict[float, list[dict]] = {}

        for t in LERP_POSITIONS:
            out_dir = OUTPUT_DIR / axis_label / f"lerp_{t:.2f}"
            features = []
            for wav_path in sorted(out_dir.glob("*.wav")):
                feats = extract_features(wav_path)
                if feats:
                    features.append(feats)
            axis_features[t] = features

        # Check minimum
        min_n = min(len(f) for f in axis_features.values())
        if min_n < 5:
            logger.warning(f"  {axis_label}: too few samples (min={min_n}), skipping")
            continue

        extreme = run_extreme_comparison(axis_features[1.0], axis_features[0.0])
        gradient = compute_gradient(axis_features)

        sig_count = sum(1 for r in extreme.values() if r["significant_05"])
        max_d = max(abs(r["cohens_d"]) for r in extreme.values())
        top_feat = max(extreme.items(), key=lambda x: abs(x[1]["cohens_d"]))[0]

        per_axis_results[axis_label] = {
            "prompt_a": prompt_a,
            "prompt_b": prompt_b,
            "extreme": extreme,
            "gradient": gradient,
            "sig_count": sig_count,
            "max_d": max_d,
            "top_feature": top_feat,
        }

        logger.info(f"  {axis_label}: max|d|={max_d:.3f}, sig={sig_count}/11, top={top_feat}")

    # Save per-axis results
    with open(OUTPUT_DIR / "remaining_axes_results.json", "w") as f:
        json.dump(per_axis_results, f, indent=2)

    logger.info(f"\n{'='*60}")
    logger.info("Remaining axes generation + analysis complete.")
    logger.info(f"Results: {OUTPUT_DIR / 'remaining_axes_results.json'}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
