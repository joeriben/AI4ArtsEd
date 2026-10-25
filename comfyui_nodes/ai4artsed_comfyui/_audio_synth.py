"""The audio synth of the cross-aesthetic surface, run by ComfyUI.

Manipulates Stable Audio 3's t5gemma conditioning space (768 d) directly:
interpolation and extrapolation between two prompts, magnitude scaling,
noise injection, semantic and PCA axis deltas, per-dimension offsets -- and
generates audio from the result (_stable_audio.generate_from_embeddings).
What gpu_service/services/cross_aesthetic_backend.py computed, letter for
letter.

The axis vocabulary (which semantic axes there are, their poles, the neutral
prompt, the frame the poles are encoded under, the PCA labels) is the
DevServer's table (devserver/config/audio_synth_axes.json); the node is
handed the poles to encode, already framed, and the name of the PCA
components file, and knows none of it by itself.

A semantic axis is two text poles in embedding space, each direction
relative to the neutral prompt (dir = pole - neutral): t in [-1, 1], 0 = no
effect, +1 = the full direction to pole_a, -1 = the full direction to pole_b.
A PCA axis "pcN" is the Nth component of the fitted PCA (a 768 d unit
direction), added as t * direction across every sequence position.
"""
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from . import _stable_audio

logger = logging.getLogger(__name__)

# The synth's ceiling on one generation (the surface's slider ends there).
MAX_SYNTH_DURATION_S = 47.0

# Encoded poles and neutral prompts, per checkpoint, on the CPU: a pole is
# encoded once and read at every turn of the drawbar. The GPU service kept
# the same cache on the card; here nothing lives on the card outside
# ComfyUI's accounting.
_encoded: Dict[Tuple[str, str], Tuple[torch.Tensor, torch.Tensor]] = {}
_pca: Dict[str, torch.Tensor] = {}


def _config_dir() -> Path:
    """devserver/config of this checkout: the package lives in the same
    repository as the DevServer (comfyui_nodes/ai4artsed_comfyui, linked into
    ComfyUI's custom_nodes), so the file is read through that layout, the
    way _platform_credentials reads the DevServer's modules."""
    return Path(__file__).resolve().parents[2] / "devserver" / "config"


def pca_components(file_name: str) -> torch.Tensor:
    """The PCA components [N, 768] of the named file under devserver/config."""
    if file_name not in _pca:
        if not file_name or Path(file_name).name != file_name:
            raise ValueError(f"a file name under devserver/config is required, not {file_name!r}")
        path = _config_dir() / file_name
        if not path.is_file():
            raise FileNotFoundError(f"no PCA components file {path}")
        _pca[file_name] = torch.load(path, map_location="cpu")
        logger.info(f"[AI4ArtsEd AudioSynth] Loaded PCA components {file_name}: {tuple(_pca[file_name].shape)}")
    return _pca[file_name]


def _on_cpu(pair):
    emb, mask = pair
    return emb.detach().cpu(), mask.detach().cpu()


def encoded(dir_name: str, text: str) -> Tuple[torch.Tensor, torch.Tensor]:
    """(embedding [1, 256, 768], mask [1, 256]) of a text, cached on the CPU."""
    key = (dir_name, text)
    if key not in _encoded:
        _encoded[key] = _on_cpu(_stable_audio.encode_prompt(dir_name, text))
    return _encoded[key]


def _split_axes(axes: List[Dict[str, Any]]):
    semantic, pca = [], []
    for axis in axes or []:
        name = str(axis.get("name", ""))
        if name.startswith("pc") and name[2:].isdigit():
            pca.append(axis)
        else:
            semantic.append(axis)
    return semantic, pca


def _manipulate_embedding(emb_a, emb_b, alpha: float, magnitude: float, noise_sigma: float,
                          seed: int):
    """Interpolation / extrapolation, magnitude, noise."""
    if emb_b is not None:
        result = (1.0 - alpha) * emb_a + alpha * emb_b
        # Renormalize after extrapolation: preserve direction, clamp the
        # magnitude to the midpoint norm so the model stays in distribution.
        # Only when alpha is outside [0, 1].
        if alpha < 0.0 or alpha > 1.0:
            midpoint = 0.5 * emb_a + 0.5 * emb_b
            ref_norm = midpoint.norm()
            result_norm = result.norm()
            if result_norm > 1e-8:
                result = result * (ref_norm / result_norm)
    else:
        result = emb_a.clone()
    if magnitude != 1.0:
        result = result * magnitude
    if noise_sigma > 0.0:
        generator = torch.Generator(device=result.device)
        generator.manual_seed(seed + 1)  # offset from the generation seed
        noise = torch.randn_like(result, generator=generator) * noise_sigma
        result = result + noise
    return result


def _apply_axes(dir_name: str, result_emb, result_mask, axes: List[Dict[str, Any]],
                neutral_prompt: str, pca_file: str):
    """Semantic and PCA axis deltas on top of an embedding: the new
    embedding, the per-dimension contributions, the widened mask."""
    semantic, pca_axes = _split_axes(axes)
    axis_deltas: Dict[str, torch.Tensor] = {}
    if semantic:
        neutral_emb, _ = encoded(dir_name, neutral_prompt)
        for axis in semantic:
            t = float(axis.get("t", 0.0))
            emb_a, mask_a = encoded(dir_name, str(axis["pole_a"]))
            emb_b, mask_b = encoded(dir_name, str(axis["pole_b"]))
            dir_a = emb_a - neutral_emb
            dir_b = emb_b - neutral_emb
            delta = t * dir_a if t >= 0 else (-t) * dir_b
            result_emb = result_emb + delta
            axis_deltas[str(axis["name"])] = delta.detach().squeeze(0).mean(dim=0)
            result_mask = torch.maximum(result_mask, mask_a)
            result_mask = torch.maximum(result_mask, mask_b)
    if pca_axes:
        pca = pca_components(pca_file)
        for axis in pca_axes:
            name = str(axis["name"])
            t = float(axis.get("t", 0.0))
            idx = int(name[2:]) - 1  # "pc1" -> index 0
            if 0 <= idx < pca.shape[0]:
                direction = pca[idx].to(result_emb.device)  # [768]
                delta = t * direction.unsqueeze(0).unsqueeze(0)  # [1, 1, 768]
                result_emb = result_emb + delta
                axis_deltas[name] = t * direction
    return result_emb, axis_contributions(axis_deltas), result_mask


def _offsets(result_emb, dimension_offsets: Optional[Dict[Any, float]]):
    if dimension_offsets:
        for dim_idx, offset_value in dimension_offsets.items():
            dim_idx = int(dim_idx)
            if 0 <= dim_idx < result_emb.shape[-1]:
                result_emb[:, :, dim_idx] += float(offset_value)
    return result_emb


def axis_contributions(axis_deltas: Dict[str, torch.Tensor]) -> List[Dict[str, Any]]:
    """Per-dimension axis contribution for drawbar coloring: 768 entries
    [{"dim", "top_axis", "contribution", "all": {axis: value}}]."""
    if not axis_deltas:
        return []
    contributions = []
    for d in range(768):
        all_contribs = {}
        max_abs = 0.0
        top_axis = ""
        for axis_name, delta_tensor in axis_deltas.items():
            val = float(delta_tensor[d].item())
            all_contribs[axis_name] = round(val, 4)
            if abs(val) > max_abs:
                max_abs = abs(val)
                top_axis = axis_name
        contributions.append({"dim": d, "top_axis": top_axis,
                              "contribution": round(max_abs, 4), "all": all_contribs})
    return contributions


def stats(embedding, emb_a=None, emb_b=None) -> Dict[str, Any]:
    """Embedding statistics for the surface. With emb_b, all_activations are
    sorted by the A/B difference (feature probing), else by magnitude."""
    emb = embedding.detach()
    mean_val = emb.mean().item()
    std_val = emb.std().item()
    dim_means_abs = emb.squeeze(0).mean(dim=0).abs()  # [768]
    top_k = min(10, dim_means_abs.shape[0])
    top_vals, top_indices = dim_means_abs.topk(top_k)
    dim_means_signed = emb.squeeze(0).mean(dim=0)  # [768], signed
    if emb_b is not None and emb_a is not None:
        diff = emb_a.detach().squeeze(0).mean(dim=0) - emb_b.detach().squeeze(0).mean(dim=0)
        sort_order = diff.abs().argsort(descending=True)
        sort_mode = "diff"
    else:
        sort_order = dim_means_signed.abs().argsort(descending=True)
        sort_mode = "magnitude"
    all_activations = [{"dim": int(idx), "value": round(float(dim_means_signed[idx].item()), 4)}
                       for idx in sort_order.tolist()]
    result = {
        "mean": round(mean_val, 4),
        "std": round(std_val, 4),
        "top_dimensions": [{"dim": int(idx), "value": round(float(val), 4)}
                           for idx, val in zip(top_indices.tolist(), top_vals.tolist())],
        "all_activations": all_activations,
        "sort_mode": sort_mode,
    }
    if emb_a is not None:
        a_means = emb_a.detach().squeeze(0).mean(dim=0)
        result["emb_a_values"] = {int(idx): round(float(a_means[idx].item()), 4)
                                  for idx in sort_order.tolist()}
    if emb_b is not None:
        b_means = emb_b.detach().squeeze(0).mean(dim=0)
        result["emb_b_values"] = {int(idx): round(float(b_means[idx].item()), 4)
                                  for idx in sort_order.tolist()}
    return result


def _finish(dir_name: str, result_emb, result_mask, duration_seconds: float, steps: int,
            cfg_scale: float, seed: int, embedding_stats, contributions, start_time: float):
    duration_seconds = max(0.1, min(duration_seconds, MAX_SYNTH_DURATION_S))
    audio, sample_rate, duration = _stable_audio.generate_from_embeddings(
        dir_name, result_emb, result_mask, duration_seconds, steps=steps, cfg_scale=cfg_scale, seed=seed)
    return {
        "audio": audio,
        "sample_rate": sample_rate,
        "duration_seconds": duration,
        "embedding_stats": embedding_stats,
        "axis_contributions": contributions,
        "generation_time_ms": int((time.time() - start_time) * 1000),
        "seed": seed,
    }


def synth(dir_name: str, prompt_a: str, prompt_b: str = "", alpha: float = 0.5,
          magnitude: float = 1.0, noise_sigma: float = 0.0,
          dimension_offsets: Optional[Dict[Any, float]] = None,
          axes: Optional[List[Dict[str, Any]]] = None, neutral_prompt: str = "",
          pca_file: str = "", duration_seconds: float = 1.0, steps: int = 8,
          cfg_scale: float = 1.0, seed: int = 0) -> Dict[str, Any]:
    """Encode A (and B), interpolate, scale, add noise, add the axes, add the
    offsets, generate."""
    start_time = time.time()
    # The manipulation runs on the CPU (a [1, 256, 768] tensor); the
    # generation moves the result to the card.
    emb_a, mask_a = _on_cpu(_stable_audio.encode_prompt(dir_name, prompt_a))
    emb_b = mask_b = None
    if prompt_b:
        emb_b, mask_b = _on_cpu(_stable_audio.encode_prompt(dir_name, prompt_b))
    result_emb = _manipulate_embedding(emb_a, emb_b, alpha, magnitude, noise_sigma, seed)
    result_mask = mask_a if mask_b is None else torch.maximum(mask_a, mask_b)
    contributions: List[Dict[str, Any]] = []
    if axes:
        result_emb, contributions, result_mask = _apply_axes(
            dir_name, result_emb, result_mask, axes, neutral_prompt, pca_file)
    result_emb = _offsets(result_emb, dimension_offsets)
    embedding_stats = stats(result_emb, emb_a, emb_b)
    return _finish(dir_name, result_emb, result_mask, duration_seconds, steps, cfg_scale, seed,
                   embedding_stats, contributions, start_time)


def multi_axis(dir_name: str, axes: List[Dict[str, Any]], base_prompt: str = "",
               dimension_offsets: Optional[Dict[Any, float]] = None, neutral_prompt: str = "",
               pca_file: str = "", duration_seconds: float = 1.0, steps: int = 8,
               cfg_scale: float = 1.0, seed: int = 0) -> Dict[str, Any]:
    """result = base + sum of the axis deltas, base = encode(base_prompt) if
    given, else the neutral embedding; then the offsets; then audio."""
    start_time = time.time()
    if base_prompt and base_prompt.strip():
        base_emb, base_mask = _on_cpu(_stable_audio.encode_prompt(dir_name, base_prompt.strip()))
        result_emb, result_mask = base_emb.clone(), base_mask.clone()
    else:
        neutral_emb, neutral_mask = encoded(dir_name, neutral_prompt)
        result_emb, result_mask = neutral_emb.clone(), neutral_mask.clone()
    result_emb, contributions, result_mask = _apply_axes(
        dir_name, result_emb, result_mask, axes, neutral_prompt, pca_file)
    result_emb = _offsets(result_emb, dimension_offsets)
    embedding_stats = stats(result_emb)
    return _finish(dir_name, result_emb, result_mask, duration_seconds, steps, cfg_scale, seed,
                   embedding_stats, contributions, start_time)
