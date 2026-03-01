#!/usr/bin/env python3
"""
Comprehensive Three-Level Axis Analysis

Reads all 21 axes' data from statistical_threelevel_test/ directory
and computes:

1. Per-axis: effect sizes, gradient analysis, significant features
2. Cross-level comparison: do neutral/biased/constitutive differ systematically?
3. Feature profile clustering: do axes within same level share acoustic profiles?
4. Drift-acoustic correlation: does embedding-space drift predict acoustic effect?
5. Axis independence: orthogonality within and across levels
6. Full 21×21 effect-size correlation matrix

Requires: all 21 axes' audio data in statistical_threelevel_test/
  (from statistical_threelevel_test.py + statistical_remaining_axes.py)

Usage: venv/bin/python research/t5_interpretability/analyze_threelevel.py
"""

import json
import logging
import sys
from collections import OrderedDict
from pathlib import Path

import librosa
import numpy as np
import torch
from scipy import stats
from scipy.spatial.distance import cosine as cosine_distance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    T5_MODEL_ID, T5_MAX_LENGTH,
    DATA_DIR, ACTIVATIONS_POOLED_PATH, CORPUS_INDEX_PATH,
)

# ── All 21 Axes ──────────────────────────────────────────────────────────────

# Original drift-analysis levels (perceptual / cultural / critical)
DRIFT_LEVELS = OrderedDict([
    ("perceptual", [
        ("loud_quiet", "sound loud", "sound quiet"),
        ("tonal_noisy", "sound tonal", "sound noisy"),
        ("rhythmic_sustained", "sound rhythmic", "sound sustained"),
        ("bright_dark", "sound bright", "sound dark"),
        ("smooth_harsh", "sound smooth", "sound harsh"),
        ("dense_sparse", "sound dense", "sound sparse"),
        ("fast_slow", "sound fast", "sound slow"),
        ("close_distant", "sound close", "sound distant"),
    ]),
    ("cultural", [
        ("traditional_modern", "traditional music", "modern music"),
        ("professional_amateur", "professional music", "amateur music"),
        ("acoustic_electronic", "acoustic music", "electronic music"),
        ("sacred_secular", "sacred music", "secular music"),
        ("solo_ensemble", "solo music", "ensemble music"),
        ("improvised_composed", "improvised music", "composed music"),
        ("ceremonial_everyday", "ceremonial music", "everyday music"),
        ("vocal_instrumental", "vocal music", "instrumental music"),
    ]),
    ("critical", [
        ("complex_simple", "complex music", "simple music"),
        ("music_noise", "music", "noise"),
        ("beautiful_ugly", "beautiful sound", "ugly sound"),
        ("authentic_fusion", "authentic music", "fusion music"),
        ("refined_raw", "refined music", "raw music"),
    ]),
])

# 3-level taxonomy (from cultural drift findings)
# Will be updated empirically — this is the a priori classification
TAXONOMY_3LEVEL = {
    "neutral": ["loud_quiet", "complex_simple", "close_distant", "dense_sparse"],
    "biased": [
        "traditional_modern", "professional_amateur", "beautiful_ugly",
        "sacred_secular", "authentic_fusion",
    ],
    "constitutive": ["tonal_noisy", "music_noise", "refined_raw"],
    # Axes that don't neatly fit — to be classified empirically
    "unclassified": [
        "rhythmic_sustained", "bright_dark", "smooth_harsh",
        "fast_slow", "acoustic_electronic", "solo_ensemble",
        "improvised_composed", "ceremonial_everyday", "vocal_instrumental",
    ],
}

# Map axis labels to cultural drift analysis names
DRIFT_AXIS_MAP = {
    "loud_quiet": "loud ↔ quiet",
    "complex_simple": "complex ↔ simple",
    "traditional_modern": "traditional ↔ modern",
    "professional_amateur": "professional ↔ amateur",
    "tonal_noisy": "tonal ↔ noisy",
    "music_noise": "music ↔ noise",
    "rhythmic_sustained": "rhythmic ↔ sustained",
    "bright_dark": "bright ↔ dark",
    "smooth_harsh": "smooth ↔ harsh",
    "dense_sparse": "dense ↔ sparse",
    "fast_slow": "fast ↔ slow",
    "close_distant": "close ↔ distant",
    "acoustic_electronic": "acoustic ↔ electronic",
    "sacred_secular": "sacred ↔ secular",
    "solo_ensemble": "solo ↔ ensemble",
    "improvised_composed": "improvised ↔ composed",
    "ceremonial_everyday": "ceremonial ↔ everyday",
    "vocal_instrumental": "vocal ↔ instrumental",
    "beautiful_ugly": "beautiful ↔ ugly",
    "authentic_fusion": "authentic ↔ fusion",
    "refined_raw": "refined ↔ raw",
}

LERP_POSITIONS = [0.0, 0.25, 0.5, 0.75, 1.0]
FEATURE_KEYS = [
    "onset_density", "spectral_centroid_mean", "spectral_centroid_std",
    "rms_mean", "rms_std", "spectral_flatness_mean", "zcr_mean",
    "tempo", "spectral_bandwidth_mean", "spectral_flux_mean", "spectral_flux_std",
]

OUTPUT_DIR = DATA_DIR / "statistical_threelevel_test"


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


# ── Statistical Helpers ──────────────────────────────────────────────────────

def compute_cohens_d(vals_a: np.ndarray, vals_b: np.ndarray) -> float:
    pooled_std = np.sqrt((vals_a.std()**2 + vals_b.std()**2) / 2)
    return float((vals_a.mean() - vals_b.mean()) / pooled_std) if pooled_std > 0 else 0.0


def run_extreme_comparison(features_a: list[dict], features_b: list[dict]) -> dict:
    results = {}
    for key in FEATURE_KEYS:
        vals_a = np.array([f[key] for f in features_a])
        vals_b = np.array([f[key] for f in features_b])
        t_stat, p_value = stats.ttest_ind(vals_a, vals_b, equal_var=False)
        results[key] = {
            "mean_a": float(vals_a.mean()),
            "mean_b": float(vals_b.mean()),
            "std_a": float(vals_a.std()),
            "std_b": float(vals_b.std()),
            "cohens_d": compute_cohens_d(vals_a, vals_b),
            "p_value": float(p_value),
            "significant_001": bool(p_value < 0.001),
            "significant_01": bool(p_value < 0.01),
            "significant_05": bool(p_value < 0.05),
        }
    return results


def compute_gradient(all_features: dict[float, list[dict]]) -> dict:
    gradient = {}
    for key in FEATURE_KEYS:
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


def compute_effect_profile(extreme: dict) -> np.ndarray:
    """Return a vector of Cohen's d values across all features — the 'acoustic fingerprint' of an axis."""
    return np.array([extreme[k]["cohens_d"] for k in FEATURE_KEYS])


# ── Cultural Drift Loading ───────────────────────────────────────────────────

def load_tradition_centroids() -> dict[str, np.ndarray] | None:
    """Load tradition centroids from the probing corpus."""
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

        return centroids
    except Exception as e:
        logger.warning(f"Could not load tradition centroids: {e}")
        return None


def load_cultural_drift_results() -> dict | None:
    """Load pre-computed drift results from cultural_drift_analysis.py."""
    drift_path = DATA_DIR / "cultural_drift" / "drift_results.json"
    if drift_path.exists():
        with open(drift_path) as f:
            return json.load(f)
    return None


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_axis_data(axis_label: str) -> dict[float, list[dict]] | None:
    """Load extracted features for an axis. If features aren't cached, extract from WAV."""
    cache_path = OUTPUT_DIR / axis_label / "features_cache.json"
    if cache_path.exists():
        with open(cache_path) as f:
            cached = json.load(f)
        # Convert string keys back to float
        return {float(k): v for k, v in cached.items()}

    # Extract from WAV files
    axis_features: dict[float, list[dict]] = {}
    for t in LERP_POSITIONS:
        out_dir = OUTPUT_DIR / axis_label / f"lerp_{t:.2f}"
        if not out_dir.exists():
            return None
        features = []
        for wav_path in sorted(out_dir.glob("*.wav")):
            feats = extract_features(wav_path)
            if feats:
                features.append(feats)
        if len(features) < 5:
            return None
        axis_features[t] = features

    # Cache for future runs
    cache_data = {str(t): feats for t, feats in axis_features.items()}
    with open(cache_path, "w") as f:
        json.dump(cache_data, f)

    return axis_features


# ── Cross-Axis Analyses ──────────────────────────────────────────────────────

def compute_effect_correlation_matrix(profiles: dict[str, np.ndarray]) -> tuple[np.ndarray, list[str]]:
    """Compute correlation matrix between axes' effect profiles."""
    labels = sorted(profiles.keys())
    n = len(labels)
    corr = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            r, _ = stats.pearsonr(profiles[labels[i]], profiles[labels[j]])
            corr[i, j] = r
    return corr, labels


def compute_within_level_similarity(
    profiles: dict[str, np.ndarray],
    level_assignment: dict[str, str],
) -> dict:
    """Compute mean pairwise correlation within and between levels."""
    levels = sorted(set(level_assignment.values()))
    result = {}

    for level in levels:
        axes_in = [a for a, l in level_assignment.items() if l == level and a in profiles]
        if len(axes_in) < 2:
            result[level] = {"within_mean_r": float("nan"), "n_axes": len(axes_in)}
            continue
        pairs = []
        for i in range(len(axes_in)):
            for j in range(i + 1, len(axes_in)):
                r, _ = stats.pearsonr(profiles[axes_in[i]], profiles[axes_in[j]])
                pairs.append(r)
        result[level] = {
            "within_mean_r": float(np.mean(pairs)),
            "within_std_r": float(np.std(pairs)),
            "n_pairs": len(pairs),
            "n_axes": len(axes_in),
        }

    # Between-level similarity
    between_pairs = []
    for i, (a1, l1) in enumerate(level_assignment.items()):
        for a2, l2 in list(level_assignment.items())[i + 1:]:
            if l1 != l2 and a1 in profiles and a2 in profiles:
                r, _ = stats.pearsonr(profiles[a1], profiles[a2])
                between_pairs.append(r)
    if between_pairs:
        result["between_levels"] = {
            "mean_r": float(np.mean(between_pairs)),
            "std_r": float(np.std(between_pairs)),
            "n_pairs": len(between_pairs),
        }

    return result


def compute_drift_acoustic_correlation(
    axis_results: dict,
    drift_data: dict,
) -> dict:
    """Correlate embedding-space cultural drift magnitude with acoustic effect size."""
    drift_mags = []
    acoustic_ds = []
    axis_labels = []

    for axis_label, ar in axis_results.items():
        drift_key = DRIFT_AXIS_MAP.get(axis_label)
        if not drift_key or drift_key not in drift_data:
            continue

        drift_info = drift_data[drift_key]
        max_drift = max(
            abs(drift_info["drift"][trad][-1] - drift_info["drift"][trad][0])
            for trad in drift_info["drift"]
        )
        max_d = max(abs(r["cohens_d"]) for r in ar["extreme"].values())

        drift_mags.append(max_drift)
        acoustic_ds.append(max_d)
        axis_labels.append(axis_label)

    if len(drift_mags) < 3:
        return {}

    drift_mags = np.array(drift_mags)
    acoustic_ds = np.array(acoustic_ds)

    r, p = stats.pearsonr(drift_mags, acoustic_ds)
    rho, rho_p = stats.spearmanr(drift_mags, acoustic_ds)

    return {
        "pearson_r": float(r),
        "pearson_p": float(p),
        "spearman_rho": float(rho),
        "spearman_p": float(rho_p),
        "n": len(drift_mags),
        "per_axis": {
            label: {"drift": float(dm), "acoustic_d": float(ad)}
            for label, dm, ad in zip(axis_labels, drift_mags, acoustic_ds)
        },
    }


# ── Report Generation ────────────────────────────────────────────────────────

def generate_report(
    axis_results: dict,
    level_summary: dict,
    corr_matrix: np.ndarray,
    corr_labels: list[str],
    similarity: dict,
    drift_acoustic: dict,
    drift_data: dict | None,
) -> str:
    lines = [
        "# Comprehensive Three-Level Axis Analysis\n",
        "Empirical validation of the 3-level taxonomy across all 21 semantic axes.\n",
        "| Level | Description | # Axes |",
        "|---|---|---|",
    ]

    for level_name, level_axes in DRIFT_LEVELS.items():
        lines.append(f"| {level_name} | Original drift-analysis level | {len(level_axes)} |")
    lines.append("")

    # ── 1. Per-Axis Results ────────────────────────────────────────────────

    lines.append("---\n\n## 1. Per-Axis Results\n")
    lines.append("| Axis | Drift Level | Max |d| | Sig (p<.05) | Top Feature | Gradient r |")
    lines.append("|---|---|---|---|---|---|")

    for level_name, level_axes in DRIFT_LEVELS.items():
        for axis_label, _, _ in level_axes:
            if axis_label not in axis_results:
                lines.append(f"| {axis_label} | {level_name} | — | — | (no data) | — |")
                continue
            ar = axis_results[axis_label]
            extreme = ar["extreme"]
            gradient = ar["gradient"]
            sorted_d = sorted(extreme.items(), key=lambda x: abs(x[1]["cohens_d"]), reverse=True)
            max_d = abs(sorted_d[0][1]["cohens_d"])
            top_feat = sorted_d[0][0]
            sig = sum(1 for r in extreme.values() if r["significant_05"])
            top_grad = max(gradient.items(), key=lambda x: abs(x[1]["pearson_r"]))
            grad_r = top_grad[1]["pearson_r"]
            lines.append(
                f"| {axis_label} | {level_name} | {max_d:.3f} | {sig}/11 | {top_feat} | {grad_r:+.3f} |"
            )
    lines.append("")

    # ── 2. Level Aggregation ──────────────────────────────────────────────

    lines.append("---\n\n## 2. Aggregation by Drift-Analysis Level\n")
    lines.append("| Level | N axes | Mean max |d| | Mean sig | Mean gradient |r| |")
    lines.append("|---|---|---|---|---|")

    for level_name in DRIFT_LEVELS:
        if level_name not in level_summary:
            continue
        ls = level_summary[level_name]
        lines.append(
            f"| {level_name} | {ls['n_axes']} | {ls['mean_max_d']:.3f} | "
            f"{ls['mean_sig']:.1f}/11 | {ls['mean_grad_r']:.3f} |"
        )
    lines.append("")

    # ── 3. Acoustic Profiles ─────────────────────────────────────────────

    lines.append("---\n\n## 3. Acoustic Feature Profiles\n")
    lines.append("Which features respond most at each level (top 3 by mean |d| across axes in level).\n")

    for level_name, level_axes in DRIFT_LEVELS.items():
        axes_in = [a for a, _, _ in level_axes if a in axis_results]
        if not axes_in:
            continue

        # Average absolute Cohen's d per feature
        feature_means = {}
        for key in FEATURE_KEYS:
            ds = [abs(axis_results[a]["extreme"][key]["cohens_d"]) for a in axes_in]
            feature_means[key] = np.mean(ds)

        sorted_feats = sorted(feature_means.items(), key=lambda x: x[1], reverse=True)[:3]
        lines.append(f"**{level_name}**: " + ", ".join(f"{k} (mean |d|={v:.3f})" for k, v in sorted_feats))
    lines.append("")

    # ── 4. Effect Correlation Matrix ─────────────────────────────────────

    lines.append("---\n\n## 4. Effect Profile Correlation Matrix\n")
    lines.append("Pearson correlation between axes' Cohen's d profiles (11 features).\n")
    lines.append("High correlation = axes produce similar acoustic changes.\n")

    # Header
    short_labels = [l[:8] for l in corr_labels]
    header = "| | " + " | ".join(short_labels) + " |"
    lines.append(header)
    lines.append("|---" * (len(corr_labels) + 1) + "|")

    for i, label in enumerate(corr_labels):
        row = f"| {label[:8]}"
        for j in range(len(corr_labels)):
            val = corr_matrix[i, j]
            if i == j:
                row += " | —"
            elif abs(val) > 0.7:
                row += f" | **{val:+.2f}**"
            else:
                row += f" | {val:+.2f}"
        row += " |"
        lines.append(row)
    lines.append("")

    # ── 5. Within-Level Similarity ───────────────────────────────────────

    lines.append("---\n\n## 5. Within-Level vs Between-Level Similarity\n")
    lines.append("Do axes within the same level produce similar acoustic effects?\n")
    lines.append("| Level | Mean within-r | Std | N pairs |")
    lines.append("|---|---|---|---|")

    for level_name in DRIFT_LEVELS:
        if level_name in similarity:
            s = similarity[level_name]
            if np.isnan(s.get("within_mean_r", float("nan"))):
                lines.append(f"| {level_name} | n/a | n/a | {s.get('n_axes', 0)} axes |")
            else:
                lines.append(
                    f"| {level_name} | {s['within_mean_r']:+.3f} | {s.get('within_std_r', 0):.3f} | {s.get('n_pairs', 0)} |"
                )

    if "between_levels" in similarity:
        b = similarity["between_levels"]
        lines.append(
            f"| **between** | {b['mean_r']:+.3f} | {b['std_r']:.3f} | {b['n_pairs']} |"
        )
    lines.append("")
    lines.append("If within-level r >> between-level r, the level taxonomy captures real acoustic groupings.\n")

    # ── 6. Drift-Acoustic Correlation ────────────────────────────────────

    if drift_acoustic:
        lines.append("---\n\n## 6. Cultural Drift vs Acoustic Effect\n")
        lines.append(
            "Does embedding-space cultural drift magnitude predict acoustic effect size?\n"
        )
        lines.append(f"- Pearson r = {drift_acoustic['pearson_r']:+.3f} (p = {drift_acoustic['pearson_p']:.4f})")
        lines.append(f"- Spearman rho = {drift_acoustic['spearman_rho']:+.3f} (p = {drift_acoustic['spearman_p']:.4f})")
        lines.append(f"- N = {drift_acoustic['n']} axes\n")

        lines.append("| Axis | Max cultural drift | Max acoustic |d| |")
        lines.append("|---|---|---|")
        for label, info in sorted(
            drift_acoustic["per_axis"].items(),
            key=lambda x: x[1]["drift"],
            reverse=True,
        ):
            lines.append(f"| {label} | {info['drift']:.4f} | {info['acoustic_d']:.3f} |")
        lines.append("")

    # ── 7. Taxonomy Validation ───────────────────────────────────────────

    lines.append("---\n\n## 7. Three-Level Taxonomy Validation\n")
    lines.append("The a priori taxonomy categorized axes by cultural drift magnitude:\n")
    lines.append("- **Neutral**: minimal drift → safe for purely aesthetic exploration")
    lines.append("- **Biased**: measurable asymmetry → drift should be shown to learners")
    lines.append("- **Constitutive**: defines music/non-music boundary → pedagogically critical\n")

    # Compare predicted vs observed
    lines.append("### Empirical Classification\n")
    lines.append("Axes ranked by max acoustic |d|, color-coded by a priori level:\n")
    lines.append("| Rank | Axis | Predicted level | Max |d| | Cultural drift | Ratio (drift/d) |")
    lines.append("|---|---|---|---|---|---|")

    # Determine each axis's predicted level
    axis_to_level = {}
    for level, axes in TAXONOMY_3LEVEL.items():
        for a in axes:
            axis_to_level[a] = level

    ranked = sorted(
        axis_results.items(),
        key=lambda x: max(abs(r["cohens_d"]) for r in x[1]["extreme"].values()),
        reverse=True,
    )

    for rank, (axis_label, ar) in enumerate(ranked, 1):
        max_d = max(abs(r["cohens_d"]) for r in ar["extreme"].values())
        predicted = axis_to_level.get(axis_label, "unclassified")

        # Get drift if available
        drift_key = DRIFT_AXIS_MAP.get(axis_label)
        drift_val = 0
        if drift_data and drift_key and drift_key in drift_data:
            drift_info = drift_data[drift_key]
            drift_val = max(
                abs(drift_info["drift"][trad][-1] - drift_info["drift"][trad][0])
                for trad in drift_info["drift"]
            )
        ratio = drift_val / max_d if max_d > 0.01 else float("inf")
        ratio_str = f"{ratio:.3f}" if ratio < 100 else "n/a"

        lines.append(
            f"| {rank} | {axis_label} | {predicted} | {max_d:.3f} | {drift_val:.4f} | {ratio_str} |"
        )
    lines.append("")

    # Summary statistics by predicted level
    lines.append("### Summary by Predicted Level\n")
    lines.append("| Level | N axes | Mean |d| | Mean drift | Mean ratio |")
    lines.append("|---|---|---|---|---|")

    for level_name in ["neutral", "biased", "constitutive", "unclassified"]:
        axes_in = [a for a in axis_results if axis_to_level.get(a) == level_name]
        if not axes_in:
            continue
        ds = [max(abs(r["cohens_d"]) for r in axis_results[a]["extreme"].values()) for a in axes_in]
        drifts = []
        for a in axes_in:
            dk = DRIFT_AXIS_MAP.get(a)
            if drift_data and dk and dk in drift_data:
                di = drift_data[dk]
                drifts.append(max(
                    abs(di["drift"][t][-1] - di["drift"][t][0])
                    for t in di["drift"]
                ))
        mean_d = np.mean(ds)
        mean_drift = np.mean(drifts) if drifts else 0
        mean_ratio = mean_drift / mean_d if mean_d > 0.01 else 0
        lines.append(
            f"| {level_name} | {len(axes_in)} | {mean_d:.3f} | {mean_drift:.4f} | {mean_ratio:.3f} |"
        )
    lines.append("")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("Loading data for all 21 axes...")

    all_axes_flat = []
    for level_name, level_axes in DRIFT_LEVELS.items():
        for axis in level_axes:
            all_axes_flat.append((level_name, *axis))

    # Load per-axis data
    axis_results = {}
    effect_profiles = {}

    for level_name, axis_label, prompt_a, prompt_b in all_axes_flat:
        data = load_axis_data(axis_label)
        if data is None:
            logger.warning(f"  {axis_label}: no data found, skipping")
            continue

        n_total = sum(len(f) for f in data.values())
        logger.info(f"  {axis_label}: {n_total} samples across {len(data)} positions")

        extreme = run_extreme_comparison(data[1.0], data[0.0])
        gradient = compute_gradient(data)

        axis_results[axis_label] = {
            "level": level_name,
            "prompt_a": prompt_a,
            "prompt_b": prompt_b,
            "extreme": extreme,
            "gradient": gradient,
            "n_per_position": {str(t): len(f) for t, f in data.items()},
        }

        effect_profiles[axis_label] = compute_effect_profile(extreme)

    logger.info(f"Loaded {len(axis_results)} axes with data")

    if len(axis_results) < 3:
        logger.error("Too few axes with data for cross-axis analysis")
        return

    # ── Level Aggregation ─────────────────────────────────────────────────

    logger.info("Computing level aggregation...")
    level_summary = {}

    for level_name, level_axes in DRIFT_LEVELS.items():
        axes_in = [a for a, _, _ in level_axes if a in axis_results]
        if not axes_in:
            continue

        max_ds = []
        sig_counts = []
        grad_rs = []

        for a in axes_in:
            extreme = axis_results[a]["extreme"]
            gradient = axis_results[a]["gradient"]
            max_ds.append(max(abs(r["cohens_d"]) for r in extreme.values()))
            sig_counts.append(sum(1 for r in extreme.values() if r["significant_05"]))
            grad_rs.append(max(abs(g["pearson_r"]) for g in gradient.values()))

        level_summary[level_name] = {
            "n_axes": len(axes_in),
            "mean_max_d": float(np.mean(max_ds)),
            "std_max_d": float(np.std(max_ds)),
            "mean_sig": float(np.mean(sig_counts)),
            "mean_grad_r": float(np.mean(grad_rs)),
        }

    # ── Correlation Matrix ────────────────────────────────────────────────

    logger.info("Computing effect correlation matrix...")
    corr_matrix, corr_labels = compute_effect_correlation_matrix(effect_profiles)

    # ── Within-Level Similarity ───────────────────────────────────────────

    logger.info("Computing within-level similarity...")
    level_assignment = {a: axis_results[a]["level"] for a in axis_results}
    similarity = compute_within_level_similarity(effect_profiles, level_assignment)

    # ── Drift-Acoustic Correlation ────────────────────────────────────────

    logger.info("Computing drift-acoustic correlation...")
    drift_data = load_cultural_drift_results()
    drift_acoustic = {}
    if drift_data:
        drift_acoustic = compute_drift_acoustic_correlation(axis_results, drift_data)

    # ── Save Results ──────────────────────────────────────────────────────

    results_bundle = {
        "axis_results": axis_results,
        "level_summary": level_summary,
        "similarity": similarity,
        "drift_acoustic": drift_acoustic,
    }

    with open(OUTPUT_DIR / "comprehensive_results.json", "w") as f:
        json.dump(results_bundle, f, indent=2)

    # Save correlation matrix separately (not JSON-friendly as np array)
    np.savez(
        OUTPUT_DIR / "correlation_matrix.npz",
        matrix=corr_matrix,
        labels=np.array(corr_labels),
    )

    # ── Report ────────────────────────────────────────────────────────────

    report = generate_report(
        axis_results, level_summary,
        corr_matrix, corr_labels,
        similarity, drift_acoustic, drift_data,
    )
    report_path = OUTPUT_DIR / "comprehensive_report.md"
    with open(report_path, "w") as f:
        f.write(report)

    logger.info(f"\n{'='*60}")
    logger.info(f"Report: {report_path}")
    logger.info(f"{'='*60}")

    # Print summary
    for level_name in DRIFT_LEVELS:
        if level_name in level_summary:
            ls = level_summary[level_name]
            logger.info(
                f"  {level_name:>12}: mean|d|={ls['mean_max_d']:.3f}±{ls['std_max_d']:.3f}, "
                f"sig={ls['mean_sig']:.1f}/11, grad={ls['mean_grad_r']:.3f} "
                f"(N={ls['n_axes']})"
            )

    if drift_acoustic:
        logger.info(
            f"\n  Drift-Acoustic: r={drift_acoustic['pearson_r']:+.3f} (p={drift_acoustic['pearson_p']:.4f}), "
            f"rho={drift_acoustic['spearman_rho']:+.3f} (N={drift_acoustic['n']})"
        )


if __name__ == "__main__":
    main()
