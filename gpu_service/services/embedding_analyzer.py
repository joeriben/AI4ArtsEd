"""
Embedding Analyzer — Feature Probing & Concept Algebra utilities

Pure tensor operations for analyzing and manipulating text encoder embeddings.
Used by Feature Probing (Latent Lab Tab 2) and Concept Algebra (Latent Lab Tab 3).
"""

import logging
from typing import Optional, Sequence

import torch
from torch import Tensor

logger = logging.getLogger(__name__)


def _select_positions(
    delta: Tensor,
    content_ranges: Optional[Sequence[tuple[int, int]]],
) -> Tensor:
    """Keep only the sequence positions named by content_ranges.

    Ranges are half-open [start, end). Several are allowed because the SD3.5
    sequence is two encoders concatenated, so the content sits in two blocks
    with the padding of the first between them.
    """
    if not content_ranges:
        return delta
    return torch.cat([delta[:, start:end, :] for start, end in content_ranges], dim=1)


def compute_dimension_differences(
    embed_a: Tensor,
    embed_b: Tensor,
    content_ranges: Optional[Sequence[tuple[int, int]]] = None,
) -> dict:
    """Per-dimension absolute difference, averaged across token positions.

    Returns ALL dimensions sorted by magnitude (no arbitrary top-k cutoff).
    The frontend uses diff_per_dim for threshold-based selection and
    top_dims/top_values for the sorted bar chart display.

    content_ranges names the positions that carry the prompt. Text encoders pad
    to a fixed width — CLIP to 77, T5 to 512 — so a five-token prompt leaves 72
    or 507 positions holding nothing but the encoder's response to padding.
    Averaging across all of them ranks dimensions by that response instead of by
    how the two prompts differ, and with T5 the padding is the larger part by far.

    The window is passed as ranges rather than a boolean mask: ranges travel into
    probing_data as plain JSON, they allocate nothing, and slicing is what
    apply_dimension_transfer needs anyway to write into the same positions.

    Args:
        embed_a: [1, seq_len, embed_dim] embedding from prompt A
        embed_b: [1, seq_len, embed_dim] embedding from prompt B
        content_ranges: optional [(start, end), ...] half-open position ranges to
            average over. None averages over the whole padded sequence — the
            behaviour every caller had before this parameter existed.

    Returns:
        dict with:
        - diff_per_dim: list of floats [embed_dim], absolute difference per dimension
        - top_dims: list of ints, ALL dimension indices sorted by difference magnitude
        - top_values: list of floats, difference values sorted by magnitude
        - embed_dim: int, total number of dimensions
        - total_l2: float, L2 distance between the embeddings over the SAME
          positions the ranking used, so the two numbers stay comparable
        - nonzero_dims: int, number of dimensions with nonzero difference
        - content_positions: int, how many positions the numbers above rest on
    """
    delta = _select_positions(embed_b - embed_a, content_ranges)
    content_positions = int(delta.shape[1])

    # Average absolute difference across token positions
    diff = delta.abs().mean(dim=1).squeeze(0)  # [embed_dim]

    # Total L2 distance for context
    total_l2 = delta.norm(p=2).item()
    nonzero = (diff > 1e-6).sum().item()

    # Sort ALL dimensions by magnitude — no arbitrary cutoff
    top = torch.topk(diff, k=diff.shape[0])

    logger.info(
        f"[EMBEDDING-DIFF] embed_dim={diff.shape[0]}, positions={content_positions}"
        f"{'' if content_ranges else ' (full padded sequence)'}, total_L2={total_l2:.4f}, "
        f"nonzero_dims={nonzero}/{diff.shape[0]}, "
        f"top1={top.values[0].item():.4f}, top10_sum={top.values[:10].sum().item():.4f}, "
        f"top50_sum={top.values[:50].sum().item():.4f}, top200_sum={top.values[:min(200, diff.shape[0])].sum().item():.4f}"
    )

    return {
        'diff_per_dim': diff.cpu().tolist(),
        'top_dims': top.indices.cpu().tolist(),
        'top_values': top.values.cpu().tolist(),
        'embed_dim': diff.shape[0],
        'total_l2': total_l2,
        'nonzero_dims': int(nonzero),
        'content_positions': content_positions,
    }


def apply_dimension_transfer(
    embed_a: Tensor,
    embed_b: Tensor,
    dims: list,
    content_ranges: Optional[Sequence[tuple[int, int]]] = None,
) -> tuple[Tensor, dict]:
    """Copy specific dimensions from embed_b into embed_a.

    The write is confined to content_ranges because that is where the dimensions
    were ranked. Writing them into the padding tail as well would move positions
    no measurement ever looked at, where A and B differ for reasons unrelated to
    the selection — the image would then change for something the instrument
    cannot show.

    Args:
        embed_a: [1, seq_len, embed_dim] base embedding
        embed_b: [1, seq_len, embed_dim] source embedding
        dims: list of dimension indices to transfer
        content_ranges: optional [(start, end), ...] half-open position ranges to
            write into. None writes across the whole padded sequence — the
            behaviour before this parameter existed.

    Returns:
        (result, stats) — result is a clone of embed_a carrying the selected
        dimensions of embed_b. stats holds change_l2, total_diff_l2 and
        captured_pct: the share of the A/B difference the selection accounts for.
        That share was computed and only logged; it belongs to the reader of the
        image, so it is handed back for probing_data.
    """
    result = embed_a.clone()
    if content_ranges:
        for start, end in content_ranges:
            result[:, start:end, dims] = embed_b[:, start:end, dims]
    else:
        result[:, :, dims] = embed_b[:, :, dims]

    # Diagnostic: how much did we actually change?
    change_l2 = (result - embed_a).norm(p=2).item()
    total_diff_l2 = _select_positions(embed_b - embed_a, content_ranges).norm(p=2).item()
    pct = (change_l2 / total_diff_l2 * 100) if total_diff_l2 > 0 else 0.0

    logger.info(
        f"[DIMENSION-TRANSFER] {len(dims)} dims transferred, "
        f"change_L2={change_l2:.4f}, total_diff_L2={total_diff_l2:.4f}, "
        f"captured={pct:.1f}% of total difference"
    )

    return result, {
        'change_l2': change_l2,
        'total_diff_l2': total_diff_l2,
        'captured_pct': pct,
    }


def apply_concept_algebra(
    embed_a: Tensor,
    embed_b: Tensor,
    embed_c: Tensor,
    scale_sub: float = 1.0,
    scale_add: float = 1.0,
    pooled_a: Optional[Tensor] = None,
    pooled_b: Optional[Tensor] = None,
    pooled_c: Optional[Tensor] = None,
) -> tuple[Tensor, float, Optional[Tensor]]:
    """Concept Algebra: result = A - scale_sub * B + scale_add * C

    Mikolov analogy: embed("King") - embed("Man") + embed("Woman") ≈ embed("Queen")
    Applied to text encoder embeddings for image generation.
    Same formula applied to both token embeddings and pooled embeddings.

    Args:
        embed_a: [1, seq_len, embed_dim] base embedding
        embed_b: [1, seq_len, embed_dim] embedding to subtract
        embed_c: [1, seq_len, embed_dim] embedding to add
        scale_sub: scaling factor for subtraction (default 1.0)
        scale_add: scaling factor for addition (default 1.0)
        pooled_a: [1, pooled_dim] optional pooled embedding (SD3.5: 2048d)
        pooled_b: [1, pooled_dim] optional pooled embedding
        pooled_c: [1, pooled_dim] optional pooled embedding

    Returns:
        (result_embedding, l2_distance_from_a, pooled_result_or_None)
    """
    result = embed_a - scale_sub * embed_b + scale_add * embed_c
    l2_dist = (result - embed_a).norm(p=2).item()

    # Apply identical formula to pooled embeddings
    pooled_result = None
    if pooled_a is not None and pooled_b is not None and pooled_c is not None:
        pooled_result = pooled_a - scale_sub * pooled_b + scale_add * pooled_c

    logger.info(
        f"[CONCEPT-ALGEBRA] A - {scale_sub}*B + {scale_add}*C, "
        f"L2(result, A)={l2_dist:.4f}, shapes: A={embed_a.shape}, B={embed_b.shape}, C={embed_c.shape}"
    )

    return result, l2_dist, pooled_result
