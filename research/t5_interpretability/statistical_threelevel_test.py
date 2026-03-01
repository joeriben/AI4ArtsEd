#!/usr/bin/env python3
"""
Three-Level Axis Sonification Test

Empirically validates the 3-level taxonomy from the cultural drift analysis
by generating LERP audio for representative axes from each level:

  Level 1 — Culturally neutral:    loud↔quiet, complex↔simple
  Level 2 — Culturally biased:     traditional↔modern, professional↔amateur
  Level 3 — Culturally constitutive: tonal↔noisy, music↔noise

For each axis: LERP at 5 positions, N=50 per position = 250 samples.
Total: 6 axes × 250 = 1,500 samples.

Questions:
  1. Do all 3 levels produce measurable acoustic effects via LERP?
  2. Do they produce qualitatively different acoustic profiles?
  3. Does acoustic effect size correlate with embedding-space cultural drift?

Usage: venv/bin/python research/t5_interpretability/statistical_threelevel_test.py
"""

import base64
import io
import json
import logging
import sys
import time
from collections import OrderedDict
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
    ACTIVATIONS_POOLED_PATH, CORPUS_INDEX_PATH,
)

# ── Experiment Design ─────────────────────────────────────────────────────────

# 3 levels × 2 axes = 6 axes total
# Selection based on cultural drift analysis findings:
#   - Neutral: lowest max drift across 15 traditions
#   - Biased: measurable asymmetry between traditions
#   - Constitutive: defines the music/non-music boundary

LEVELS = OrderedDict([
    ("neutral", [
        ("loud_quiet", "sound loud", "sound quiet"),
        ("complex_simple", "complex music", "simple music"),
    ]),
    ("biased", [
        ("traditional_modern", "traditional music", "modern music"),
        ("professional_amateur", "professional music", "amateur music"),
    ]),
    ("constitutive", [
        ("tonal_noisy", "sound tonal", "sound noisy"),
        ("music_noise", "music", "noise"),
    ]),
])

LERP_POSITIONS = [0.0, 0.25, 0.5, 0.75, 1.0]
N_SAMPLES = 50  # per LERP position per axis
DURATION = 5.0
STEPS = 100
CFG = 7.0

OUTPUT_DIR = DATA_DIR / "statistical_threelevel_test"

# Map axis labels back to cultural_drift_analysis axis names for cross-referencing
DRIFT_AXIS_MAP = {
    "loud_quiet": "loud ↔ quiet",
    "complex_simple": "complex ↔ simple",
    "traditional_modern": "traditional ↔ modern",
    "professional_amateur": "professional ↔ amateur",
    "tonal_noisy": "tonal ↔ noisy",
    "music_noise": "music ↔ noise",
}


# ── T5 Encoding ──────────────────────────────────────────────────────────────

def load_t5():
    from transformers import T5EncoderModel, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(T5_MODEL_ID)
    model = T5EncoderModel.from_pretrained(T5_MODEL_ID).cuda().half()
    model.eval()
    return tokenizer, model


def encode_prompt(text: str, tokenizer, model) -> tuple[np.ndarray, np.ndarray]:
    """Encode text → [1, seq, 768] embedding + attention mask."""
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


def encode_prompt_pooled(text: str, tokenizer, model) -> np.ndarray:
    """Encode text → mean-pooled [768] vector (for cultural drift comparison)."""
    emb, mask = encode_prompt(text, tokenizer, model)
    emb_masked = emb * mask[..., np.newaxis]
    pooled = emb_masked.sum(axis=1) / mask.sum(axis=1, keepdims=True)
    return pooled.squeeze(0)


# ── Audio Generation ─────────────────────────────────────────────────────────

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


# ── Feature Extraction ───────────────────────────────────────────────────────

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


# ── Statistical Analysis ─────────────────────────────────────────────────────

def run_extreme_comparison(features_a: list[dict], features_b: list[dict]) -> dict:
    """Compare t=0.0 vs t=1.0 for one axis."""
    results = {}
    all_keys = sorted(features_a[0].keys())

    for key in all_keys:
        vals_a = np.array([f[key] for f in features_a])
        vals_b = np.array([f[key] for f in features_b])

        t_stat, p_value = stats.ttest_ind(vals_a, vals_b, equal_var=False)
        pooled_std = np.sqrt((vals_a.std()**2 + vals_b.std()**2) / 2)
        cohens_d = (vals_a.mean() - vals_b.mean()) / pooled_std if pooled_std > 0 else 0
        u_stat, u_p = stats.mannwhitneyu(vals_a, vals_b, alternative='two-sided')

        results[key] = {
            "mean_a": float(vals_a.mean()),
            "mean_b": float(vals_b.mean()),
            "std_a": float(vals_a.std()),
            "std_b": float(vals_b.std()),
            "cohens_d": float(cohens_d),
            "p_value": float(p_value),
            "mann_whitney_p": float(u_p),
            "significant_001": bool(p_value < 0.001),
            "significant_01": bool(p_value < 0.01),
            "significant_05": bool(p_value < 0.05),
        }

    return results


def compute_gradient(all_features: dict[float, list[dict]]) -> dict:
    """Pearson/Spearman correlation of each feature with LERP position."""
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


def compute_cultural_drift_for_axis(
    emb_a_pooled: np.ndarray,
    emb_b_pooled: np.ndarray,
    centroids: dict[str, np.ndarray],
) -> dict:
    """Compute cultural drift from LERP positions to tradition centroids (embedding space)."""
    drift = {}
    for name, centroid in centroids.items():
        distances = []
        for t in LERP_POSITIONS:
            emb = (1.0 - t) * emb_b_pooled + t * emb_a_pooled
            d = cosine_distance(emb, centroid)
            distances.append(float(d))
        drift[name] = {
            "distances": distances,
            "magnitude": distances[-1] - distances[0],
        }
    return drift


# ── Report Generation ────────────────────────────────────────────────────────

def generate_report(
    axis_results: dict,
    level_summary: dict,
    drift_comparison: dict,
) -> str:
    lines = [
        "# Three-Level Axis Sonification Test\n",
        "Empirical validation of the 3-level taxonomy from cultural drift analysis.\n",
        "For each axis: LERP between two natural T5 embeddings, N=50 per position, 5 positions.\n",
        "| Level | Description | Axes |",
        "|---|---|---|",
        "| Neutral | Minimal cultural drift | loud↔quiet, complex↔simple |",
        "| Biased | Measurable cultural asymmetry | traditional↔modern, professional↔amateur |",
        "| Constitutive | Defines music/non-music boundary | tonal↔noisy, music↔noise |",
        "",
    ]

    # Per-axis results
    for level_name, level_axes in LEVELS.items():
        lines.append(f"---\n\n## Level: {level_name.upper()}\n")

        for axis_label, prompt_a, prompt_b in level_axes:
            if axis_label not in axis_results:
                continue

            ar = axis_results[axis_label]
            extreme = ar["extreme"]
            gradient = ar["gradient"]
            pole_dist = ar.get("pole_distance", 0)

            lines.append(f"### {axis_label.replace('_', ' ↔ ')}\n")
            lines.append(f"- Pole A (t=1.0): `{prompt_a}`")
            lines.append(f"- Pole B (t=0.0): `{prompt_b}`")
            lines.append(f"- Embedding pole distance (cosine): {pole_dist:.4f}")

            # Count significant features
            sig_count = sum(1 for r in extreme.values() if r["significant_05"])
            lines.append(f"- Significant features (p<0.05): **{sig_count}/11**\n")

            # Top effects table
            lines.append("| Feature | Cohen's d | p-value | Sig? | Gradient r |")
            lines.append("|---|---|---|---|---|")

            sorted_extreme = sorted(
                extreme.items(), key=lambda x: abs(x[1]["cohens_d"]), reverse=True,
            )

            for key, r in sorted_extreme:
                sig = "***" if r["significant_001"] else ("**" if r["significant_01"] else ("*" if r["significant_05"] else ""))
                grad_r = gradient.get(key, {}).get("pearson_r", 0)
                grad_sig = "***" if gradient.get(key, {}).get("pearson_p", 1) < 0.001 else ""
                lines.append(
                    f"| {key} | {r['cohens_d']:+.3f} | {r['p_value']:.2e} | {sig} | {grad_r:+.3f}{grad_sig} |"
                )
            lines.append("")

    # Cross-level comparison
    lines.append("---\n\n## Cross-Level Comparison\n")
    lines.append("| Axis | Level | Max |d| | Sig features | Top feature | Pole dist |")
    lines.append("|---|---|---|---|---|---|")

    for level_name, level_axes in LEVELS.items():
        for axis_label, _, _ in level_axes:
            if axis_label not in axis_results:
                continue
            ar = axis_results[axis_label]
            extreme = ar["extreme"]
            sorted_d = sorted(extreme.items(), key=lambda x: abs(x[1]["cohens_d"]), reverse=True)
            max_d = sorted_d[0][1]["cohens_d"]
            top_feat = sorted_d[0][0]
            sig_count = sum(1 for r in extreme.values() if r["significant_05"])
            pole_dist = ar.get("pole_distance", 0)
            lines.append(
                f"| {axis_label.replace('_', '↔')} | {level_name} | {abs(max_d):.3f} | {sig_count}/11 | {top_feat} | {pole_dist:.4f} |"
            )
    lines.append("")

    # Level aggregates
    lines.append("### Aggregate by Level\n")
    lines.append("| Level | Mean max |d| | Mean sig features | Mean pole distance |")
    lines.append("|---|---|---|---|")

    for level_name in LEVELS:
        if level_name not in level_summary:
            continue
        ls = level_summary[level_name]
        lines.append(
            f"| {level_name} | {ls['mean_max_d']:.3f} | {ls['mean_sig_count']:.1f}/11 | {ls['mean_pole_dist']:.4f} |"
        )
    lines.append("")

    # Acoustic profile comparison
    lines.append("### Acoustic Profiles by Level\n")
    lines.append("Which features respond most at each level?\n")

    for level_name, level_axes in LEVELS.items():
        lines.append(f"**{level_name.upper()}**:")
        for axis_label, _, _ in level_axes:
            if axis_label not in axis_results:
                continue
            extreme = axis_results[axis_label]["extreme"]
            top3 = sorted(extreme.items(), key=lambda x: abs(x[1]["cohens_d"]), reverse=True)[:3]
            feats_str = ", ".join(
                f"{k} ({v['cohens_d']:+.3f})" for k, v in top3 if v["significant_05"]
            )
            if not feats_str:
                feats_str = "(no significant features)"
            lines.append(f"- {axis_label.replace('_', '↔')}: {feats_str}")
        lines.append("")

    # Cultural drift cross-reference
    if drift_comparison:
        lines.append("---\n\n## Cultural Drift Cross-Reference\n")
        lines.append("Comparison of embedding-space cultural drift (from `cultural_drift_analysis.py`)")
        lines.append("with acoustic effect size from this experiment.\n")
        lines.append("| Axis | Level | Max cultural drift | Max acoustic |d| | Drift/Acoustic ratio |")
        lines.append("|---|---|---|---|---|")

        for axis_label, dc in sorted(drift_comparison.items(), key=lambda x: x[1]["level_idx"]):
            level = dc["level"]
            max_drift = dc["max_drift_magnitude"]
            max_d = dc["max_acoustic_d"]
            ratio = abs(max_drift / max_d) if abs(max_d) > 0.01 else float("inf")
            ratio_str = f"{ratio:.3f}" if ratio < 100 else "n/a"
            lines.append(
                f"| {axis_label.replace('_', '↔')} | {level} | {max_drift:.4f} | {max_d:.3f} | {ratio_str} |"
            )
        lines.append("")
        lines.append("Higher drift/acoustic ratio = more cultural baggage per unit of acoustic change.\n")

    # Interpretation
    lines.append("---\n\n## Interpretation\n")

    # Check if the 3-level model holds
    level_max_ds = {}
    for level_name in LEVELS:
        if level_name in level_summary:
            level_max_ds[level_name] = level_summary[level_name]["mean_max_d"]

    if len(level_max_ds) == 3:
        if level_max_ds["neutral"] > 0.1 and level_max_ds["biased"] > 0.1 and level_max_ds["constitutive"] > 0.1:
            lines.append("**All three levels produce measurable acoustic effects via LERP.**\n")
        else:
            weak = [k for k, v in level_max_ds.items() if v < 0.1]
            lines.append(f"**Some levels show weak acoustic effects**: {', '.join(weak)}\n")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Flatten all axes
    all_axes = []
    for level_name, level_axes in LEVELS.items():
        for axis in level_axes:
            all_axes.append((level_name, *axis))

    total_axes = len(all_axes)
    total_samples = total_axes * len(LERP_POSITIONS) * N_SAMPLES
    logger.info(f"Experiment: {total_axes} axes × {len(LERP_POSITIONS)} positions × N={N_SAMPLES} = {total_samples} samples")

    # Check what needs generation
    need_generation = False
    for level_name, axis_label, prompt_a, prompt_b in all_axes:
        for t in LERP_POSITIONS:
            d = OUTPUT_DIR / axis_label / f"lerp_{t:.2f}"
            if not d.exists() or len(list(d.glob("*.wav"))) < N_SAMPLES:
                need_generation = True
                break
        if need_generation:
            break

    # Encode and generate
    pole_embeddings_pooled = {}  # for cultural drift comparison

    if need_generation:
        logger.info("Loading T5...")
        tokenizer, model = load_t5()

        # Encode all poles
        axis_embeddings = {}
        for level_name, axis_label, prompt_a, prompt_b in all_axes:
            logger.info(f"Encoding [{level_name}] {axis_label}: '{prompt_a}' / '{prompt_b}'")
            emb_a, mask_a = encode_prompt(prompt_a, tokenizer, model)
            emb_b, mask_b = encode_prompt(prompt_b, tokenizer, model)
            axis_embeddings[axis_label] = {
                "emb_a": emb_a, "emb_b": emb_b,
                "mask_a": mask_a, "mask_b": mask_b,
            }

            # Also encode pooled versions for drift comparison
            pole_embeddings_pooled[axis_label] = {
                "a": encode_prompt_pooled(prompt_a, tokenizer, model),
                "b": encode_prompt_pooled(prompt_b, tokenizer, model),
            }

            # Log pole distance
            pole_dist = cosine_distance(
                pole_embeddings_pooled[axis_label]["a"],
                pole_embeddings_pooled[axis_label]["b"],
            )
            logger.info(f"  Pole distance (cosine, pooled): {pole_dist:.4f}")

        del model
        torch.cuda.empty_cache()

        # Generate audio
        done = 0
        start_time = time.time()

        for level_name, axis_label, prompt_a, prompt_b in all_axes:
            ae = axis_embeddings[axis_label]

            for t in LERP_POSITIONS:
                out_dir = OUTPUT_DIR / axis_label / f"lerp_{t:.2f}"
                out_dir.mkdir(parents=True, exist_ok=True)

                existing = len(list(out_dir.glob("*.wav")))
                if existing >= N_SAMPLES:
                    logger.info(f"  {axis_label}/lerp_{t:.2f}: {existing} files exist, skipping")
                    done += N_SAMPLES
                    continue

                # LERP in full sequence space
                emb = (1.0 - t) * ae["emb_b"] + t * ae["emb_a"]
                mask = ae["mask_a"]  # masks nearly identical for short prompts

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

        # Still need pooled embeddings for drift comparison
        logger.info("Loading T5 for drift computation...")
        tokenizer, model = load_t5()
        for level_name, axis_label, prompt_a, prompt_b in all_axes:
            pole_embeddings_pooled[axis_label] = {
                "a": encode_prompt_pooled(prompt_a, tokenizer, model),
                "b": encode_prompt_pooled(prompt_b, tokenizer, model),
            }
        del model
        torch.cuda.empty_cache()

    # ── Feature Extraction ────────────────────────────────────────────────────

    logger.info("Extracting acoustic features...")
    axis_features: dict[str, dict[float, list[dict]]] = {}

    for level_name, axis_label, prompt_a, prompt_b in all_axes:
        axis_features[axis_label] = {}
        for t in LERP_POSITIONS:
            out_dir = OUTPUT_DIR / axis_label / f"lerp_{t:.2f}"
            features = []
            for wav_path in sorted(out_dir.glob("*.wav")):
                feats = extract_features(wav_path)
                if feats:
                    features.append(feats)
            axis_features[axis_label][t] = features
            logger.info(f"  {axis_label}/lerp_{t:.2f}: {len(features)} samples")

    # Verify minimum samples
    for axis_label, pos_features in axis_features.items():
        for t, feats in pos_features.items():
            if len(feats) < 10:
                logger.error(f"Too few samples: {axis_label}/lerp_{t:.2f} = {len(feats)}")
                return

    # ── Statistical Analysis ──────────────────────────────────────────────────

    logger.info("Running statistical analysis...")

    axis_results = {}
    for level_name, axis_label, prompt_a, prompt_b in all_axes:
        feats = axis_features[axis_label]

        # Extreme comparison
        extreme = run_extreme_comparison(feats[1.0], feats[0.0])

        # Gradient
        gradient = compute_gradient(feats)

        # Pole distance
        pole_dist = float(cosine_distance(
            pole_embeddings_pooled[axis_label]["a"],
            pole_embeddings_pooled[axis_label]["b"],
        ))

        axis_results[axis_label] = {
            "level": level_name,
            "prompt_a": prompt_a,
            "prompt_b": prompt_b,
            "pole_distance": pole_dist,
            "extreme": extreme,
            "gradient": gradient,
        }

    # ── Level Aggregation ─────────────────────────────────────────────────────

    level_summary = {}
    for level_name, level_axes in LEVELS.items():
        max_ds = []
        sig_counts = []
        pole_dists = []

        for axis_label, _, _ in level_axes:
            if axis_label not in axis_results:
                continue
            extreme = axis_results[axis_label]["extreme"]
            sorted_d = sorted(extreme.items(), key=lambda x: abs(x[1]["cohens_d"]), reverse=True)
            max_ds.append(abs(sorted_d[0][1]["cohens_d"]))
            sig_counts.append(sum(1 for r in extreme.values() if r["significant_05"]))
            pole_dists.append(axis_results[axis_label]["pole_distance"])

        if max_ds:
            level_summary[level_name] = {
                "mean_max_d": float(np.mean(max_ds)),
                "mean_sig_count": float(np.mean(sig_counts)),
                "mean_pole_dist": float(np.mean(pole_dists)),
                "axes": [a[0] for a in level_axes],
            }

    # ── Cultural Drift Cross-Reference ────────────────────────────────────────

    logger.info("Computing cultural drift cross-reference...")

    # Load tradition centroids
    drift_comparison = {}
    try:
        activations = torch.load(ACTIVATIONS_POOLED_PATH, weights_only=True).float().numpy()
        with open(CORPUS_INDEX_PATH) as f:
            index = json.load(f)

        traditions: dict[str, list[int]] = {}
        for i, entry in enumerate(index):
            if entry["category"].startswith("pillar1_"):
                subcat = entry["subcategory"]
                if subcat not in traditions:
                    traditions[subcat] = []
                traditions[subcat].append(i)

        centroids = {}
        for name, indices in sorted(traditions.items()):
            centroids[name] = activations[indices].mean(axis=0)

        # Compute drift for each axis
        level_idx_map = {"neutral": 0, "biased": 1, "constitutive": 2}
        for level_name, axis_label, prompt_a, prompt_b in all_axes:
            if axis_label not in pole_embeddings_pooled:
                continue

            emb_a_pooled = pole_embeddings_pooled[axis_label]["a"]
            emb_b_pooled = pole_embeddings_pooled[axis_label]["b"]

            drift = compute_cultural_drift_for_axis(emb_a_pooled, emb_b_pooled, centroids)

            max_drift_mag = max(abs(d["magnitude"]) for d in drift.values())
            max_d = 0
            if axis_label in axis_results:
                extreme = axis_results[axis_label]["extreme"]
                max_d = max(abs(r["cohens_d"]) for r in extreme.values())

            drift_comparison[axis_label] = {
                "level": level_name,
                "level_idx": level_idx_map[level_name],
                "max_drift_magnitude": max_drift_mag,
                "max_acoustic_d": max_d,
                "traditions_drift": {
                    name: d["magnitude"] for name, d in drift.items()
                },
            }

    except Exception as e:
        logger.warning(f"Could not compute cultural drift: {e}")

    # ── Save Results ──────────────────────────────────────────────────────────

    # Save per-axis results (without numpy arrays)
    with open(OUTPUT_DIR / "axis_results.json", "w") as f:
        json.dump(axis_results, f, indent=2)

    with open(OUTPUT_DIR / "level_summary.json", "w") as f:
        json.dump(level_summary, f, indent=2)

    if drift_comparison:
        with open(OUTPUT_DIR / "drift_comparison.json", "w") as f:
            json.dump(drift_comparison, f, indent=2)

    # ── Report ────────────────────────────────────────────────────────────────

    report = generate_report(axis_results, level_summary, drift_comparison)
    report_path = OUTPUT_DIR / "statistical_report.md"
    with open(report_path, "w") as f:
        f.write(report)

    logger.info(f"\n{'='*60}")
    logger.info(f"Report: {report_path}")
    logger.info(f"{'='*60}")

    # Print summary
    for level_name in LEVELS:
        if level_name in level_summary:
            ls = level_summary[level_name]
            logger.info(
                f"  {level_name:>15}: mean max|d|={ls['mean_max_d']:.3f}, "
                f"mean sig={ls['mean_sig_count']:.1f}/11, "
                f"pole_dist={ls['mean_pole_dist']:.4f}"
            )


if __name__ == "__main__":
    main()
