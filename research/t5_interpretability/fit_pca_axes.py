#!/usr/bin/env python3
"""
Fit PCA on T5 conditioning space embeddings.

Extracts principal components from the pre-computed 392K × 768d activation
tensor. The top-N components become "PCA axes" for the Latent Audio Synth:
each axis = a direction of maximum variance in the embedding space.

Unlike the hand-crafted semantic axes (tonal/noisy, bright/dark), PCA axes
are data-driven — they capture whatever the T5 encoder actually uses to
differentiate audio descriptions.

Output: pca_axes.json — array of {name, direction[768], explained_variance, cumulative_variance}
        pca_components.pt — raw torch tensor [N, 768]

Usage: venv/bin/python research/t5_interpretability/fit_pca_axes.py
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.decomposition import PCA

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "data"
ACTIVATIONS_PATH = DATA_DIR / "activations_pooled.pt"

N_COMPONENTS = 32  # Top-N principal components to export
OUTPUT_JSON = DATA_DIR / "pca_axes.json"
OUTPUT_PT = DATA_DIR / "pca_components.pt"
OUTPUT_MEAN = DATA_DIR / "pca_mean.pt"


def main():
    # Load pre-computed T5 embeddings
    logger.info(f"Loading activations from {ACTIVATIONS_PATH}")
    activations = torch.load(ACTIVATIONS_PATH, map_location="cpu")
    logger.info(f"Shape: {activations.shape}, dtype: {activations.dtype}")

    # Convert to float32 numpy for sklearn
    X = activations.float().numpy()
    logger.info(f"Fitting PCA with {N_COMPONENTS} components on {X.shape[0]} samples...")

    pca = PCA(n_components=N_COMPONENTS)
    pca.fit(X)

    # Results
    explained = pca.explained_variance_ratio_
    cumulative = np.cumsum(explained)

    logger.info(f"Top-{N_COMPONENTS} components explain {cumulative[-1]:.1%} of total variance")
    logger.info(f"Top 5:  {cumulative[4]:.1%}")
    logger.info(f"Top 10: {cumulative[9]:.1%}")
    logger.info(f"Top 20: {cumulative[19]:.1%}")

    # Export as JSON for backend integration
    axes = []
    for i in range(N_COMPONENTS):
        axes.append({
            "name": f"pc{i + 1}",
            "label": f"PC{i + 1}",
            "explained_variance": round(float(explained[i]), 6),
            "cumulative_variance": round(float(cumulative[i]), 4),
            "direction": [round(float(v), 6) for v in pca.components_[i]],
        })

    with open(OUTPUT_JSON, "w") as f:
        json.dump(axes, f, indent=2)
    logger.info(f"Saved {len(axes)} PCA axes to {OUTPUT_JSON}")

    # Export as torch tensors for direct backend use
    components = torch.from_numpy(pca.components_).float()  # [N, 768]
    mean = torch.from_numpy(pca.mean_).float()  # [768]
    torch.save(components, OUTPUT_PT)
    torch.save(mean, OUTPUT_MEAN)
    logger.info(f"Saved components tensor {components.shape} to {OUTPUT_PT}")
    logger.info(f"Saved mean vector {mean.shape} to {OUTPUT_MEAN}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"PCA Summary — {X.shape[0]} embeddings × {X.shape[1]}d")
    print(f"{'='*60}")
    for i in range(min(10, N_COMPONENTS)):
        bar = "█" * int(explained[i] * 200)
        print(f"  PC{i+1:2d}: {explained[i]:6.2%} (cum: {cumulative[i]:6.2%}) {bar}")
    print(f"  ...")
    print(f"  PC{N_COMPONENTS}: {explained[-1]:6.2%} (cum: {cumulative[-1]:6.2%})")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
