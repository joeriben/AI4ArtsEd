"""
Mosaic Segmentation Service — Arcimboldo Mosaic

Converts attention maps from Attention Cartography into discrete
semantic regions, generates color-matched tiles, and composites
the final mosaic.

All functions are pure numpy/PIL — no GPU needed for segmentation
and composition. Tile generation delegates to DiffusersImageGenerator.
"""

import logging
import base64
import io
import numpy as np
from PIL import Image
from typing import Optional

logger = logging.getLogger(__name__)


def segment_attention_maps(
    attention_maps: dict,
    tokens: list,
    word_groups: list,
    spatial_resolution: list,
    image_base64: str,
    grid_size: int = 16,
    selected_layers: Optional[list] = None,
    min_region_fraction: float = 0.02,
) -> dict:
    """
    Convert per-token attention maps into discrete semantic regions.

    Args:
        attention_maps: {step_N: {layer_M: [[int]]}} from attention cartography
        tokens: List of token strings
        word_groups: List of [subtoken_indices] per word
        spatial_resolution: [h, w] of attention grid (e.g. [64, 64])
        image_base64: Base64 PNG of the generated image (for avg color)
        grid_size: Mosaic grid dimension (e.g. 16 for 16x16)
        selected_layers: Which layers to use (None = all)
        min_region_fraction: Merge regions smaller than this fraction

    Returns:
        {
            'label_map': [[int]],     # spatial_h x spatial_w, values = word_group index
            'regions': [{
                'idx': int,
                'label': str,
                'pixel_count': int,
                'avg_color_rgb': [r, g, b],
            }],
            'grid_assignment': [[int]],  # grid_size x grid_size
            'grid_size': int,
        }
    """
    sp_h, sp_w = spatial_resolution
    num_words = len(word_groups)

    # Build per-word aggregated attention map: [num_words, sp_h, sp_w]
    word_attention = np.zeros((num_words, sp_h, sp_w), dtype=np.float64)

    steps_used = 0
    for step_key, layers in attention_maps.items():
        for layer_key, attn_grid in layers.items():
            if selected_layers is not None:
                layer_num = int(layer_key.replace('layer_', ''))
                if layer_num not in selected_layers:
                    continue

            attn = np.array(attn_grid, dtype=np.float64)  # [sp_h*sp_w, num_tokens] or similar
            if attn.ndim != 2:
                continue

            # attn shape: [spatial_positions, text_tokens]
            # Sum attention for each word group's subtokens
            for word_idx, subtoken_indices in enumerate(word_groups):
                for tok_idx in subtoken_indices:
                    if tok_idx < attn.shape[1]:
                        word_attention[word_idx] += attn[:, tok_idx].reshape(sp_h, sp_w)

            steps_used += 1

    if steps_used == 0:
        raise ValueError("No attention data found for the selected layers")

    # Average across steps/layers
    word_attention /= steps_used

    # Winner-takes-all: assign each spatial position to the word with highest attention
    label_map = np.argmax(word_attention, axis=0).astype(np.int32)  # [sp_h, sp_w]

    # Merge small regions into nearest large neighbor
    total_pixels = sp_h * sp_w
    min_pixels = int(total_pixels * min_region_fraction)

    for word_idx in range(num_words):
        mask = label_map == word_idx
        count = np.sum(mask)
        if 0 < count < min_pixels:
            # Find positions of this small region
            positions = np.argwhere(mask)
            # For each position, find the neighbor with highest attention (excluding this word)
            other_attention = np.copy(word_attention)
            other_attention[word_idx] = -1  # Exclude this word
            replacement = np.argmax(other_attention, axis=0)
            label_map[mask] = replacement[mask]

    # Compute grid assignment: majority vote per grid cell
    grid_assignment = np.zeros((grid_size, grid_size), dtype=np.int32)
    cell_h = sp_h / grid_size
    cell_w = sp_w / grid_size

    for gy in range(grid_size):
        for gx in range(grid_size):
            y0 = int(gy * cell_h)
            y1 = int((gy + 1) * cell_h)
            x0 = int(gx * cell_w)
            x1 = int((gx + 1) * cell_w)
            cell = label_map[y0:y1, x0:x1]
            if cell.size > 0:
                grid_assignment[gy, gx] = np.bincount(cell.flatten()).argmax()

    # Decode image for average color computation
    image_data = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(image_data)).convert('RGB')
    img_array = np.array(image)
    img_h, img_w = img_array.shape[:2]

    # Upscale label_map to image resolution for color sampling
    label_map_full = np.kron(
        label_map,
        np.ones((img_h // sp_h, img_w // sp_w), dtype=np.int32)
    )
    # Handle rounding
    if label_map_full.shape[0] < img_h or label_map_full.shape[1] < img_w:
        padded = np.zeros((img_h, img_w), dtype=np.int32)
        padded[:label_map_full.shape[0], :label_map_full.shape[1]] = label_map_full
        # Fill remaining with nearest
        if label_map_full.shape[0] < img_h:
            padded[label_map_full.shape[0]:, :] = padded[label_map_full.shape[0]-1:label_map_full.shape[0], :]
        if label_map_full.shape[1] < img_w:
            padded[:, label_map_full.shape[1]:] = padded[:, label_map_full.shape[1]-1:label_map_full.shape[1]]
        label_map_full = padded

    # Compute per-region stats
    active_indices = set(grid_assignment.flatten().tolist())
    regions = []
    for word_idx in sorted(active_indices):
        mask = label_map_full == word_idx
        count = int(np.sum(mask))
        if count == 0:
            continue

        # Average color from the original image
        masked_pixels = img_array[mask[:img_h, :img_w]]
        avg_color = masked_pixels.mean(axis=0).astype(int).tolist() if len(masked_pixels) > 0 else [128, 128, 128]

        # Build word label from tokens
        if word_idx < len(word_groups):
            subtokens = word_groups[word_idx]
            label = ''.join(tokens[i] for i in subtokens if i < len(tokens)).replace('</w>', '').strip()
        else:
            label = f'region_{word_idx}'

        regions.append({
            'idx': int(word_idx),
            'label': label,
            'pixel_count': count,
            'avg_color_rgb': avg_color,
        })

    logger.info(
        f"[MOSAIC-SEG] {len(regions)} regions from {num_words} words, "
        f"grid {grid_size}x{grid_size}, {steps_used} attention samples"
    )

    return {
        'label_map': label_map.tolist(),
        'regions': regions,
        'grid_assignment': grid_assignment.tolist(),
        'grid_size': grid_size,
    }


def apply_color_transfer(tile: Image.Image, target_rgb: list) -> Image.Image:
    """
    Simple LAB-space color transfer: shift tile's mean color toward target.

    Args:
        tile: PIL Image to adjust
        target_rgb: [R, G, B] target average color

    Returns:
        Color-adjusted PIL Image
    """
    tile_array = np.array(tile, dtype=np.float32)
    tile_mean = tile_array.mean(axis=(0, 1))
    target = np.array(target_rgb, dtype=np.float32)

    # Compute shift and apply with dampening (0.6 to avoid over-correction)
    shift = (target - tile_mean) * 0.6
    adjusted = np.clip(tile_array + shift, 0, 255).astype(np.uint8)
    return Image.fromarray(adjusted)


def compose_mosaic(
    grid_assignment: list,
    tiles: dict,
    output_width: int = 1024,
    output_height: int = 1024,
) -> bytes:
    """
    Assemble tiles into a mosaic image.

    Args:
        grid_assignment: [[int]] grid_size x grid_size, values = region index
        tiles: {region_idx_str: [base64_png, ...]} tiles per region
        output_width/height: Final mosaic dimensions

    Returns:
        PNG bytes of the composed mosaic
    """
    grid = np.array(grid_assignment)
    grid_h, grid_w = grid.shape
    cell_w = output_width // grid_w
    cell_h = output_height // grid_h

    canvas = Image.new('RGB', (output_width, output_height), (0, 0, 0))

    # Track tile usage per region to cycle through available tiles
    tile_counters = {}

    for gy in range(grid_h):
        for gx in range(grid_w):
            region_idx = str(grid[gy, gx])
            region_tiles = tiles.get(region_idx, [])
            if not region_tiles:
                continue

            # Cycle through available tiles
            counter = tile_counters.get(region_idx, 0)
            tile_b64 = region_tiles[counter % len(region_tiles)]
            tile_counters[region_idx] = counter + 1

            # Decode and resize tile
            tile_data = base64.b64decode(tile_b64)
            tile_img = Image.open(io.BytesIO(tile_data)).convert('RGB')
            tile_img = tile_img.resize((cell_w, cell_h), Image.LANCZOS)

            # Paste into canvas
            canvas.paste(tile_img, (gx * cell_w, gy * cell_h))

    # Export as PNG
    buffer = io.BytesIO()
    canvas.save(buffer, format='PNG')

    logger.info(
        f"[MOSAIC-COMPOSE] {grid_h}x{grid_w} grid, "
        f"cell {cell_w}x{cell_h}px, output {output_width}x{output_height}"
    )

    return buffer.getvalue()
