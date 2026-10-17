"""
Custom Attention Processors for SD3.5 MMDiT — Attention Map Extraction

Latent Lab: Attention Cartography (Tab 1)
Captures text→image cross-attention maps from SD3.5's Joint Transformer blocks.

Scientific basis: Hertz et al. (2022) "Prompt-to-Prompt Image Editing with Cross Attention Control"

Challenge: SD3.5's JointAttnProcessor2_0 uses F.scaled_dot_product_attention (SDPA)
which does NOT return attention weights. This processor computes attention manually
via softmax(Q·K^T / √d) to extract the text→image attention submatrix.

Memory budget:
- Full attention per layer: [num_heads, seq_len, seq_len] where seq_len = image_tokens + text_tokens
  At 1024x1024: 4096 + 512 = 4608 tokens → 4608² × num_heads × 4 bytes ≈ way too much
- Strategy: Only store text→image attention, averaged across heads
  Per capture: [4096 image_tokens × 512 text_tokens] × 4 bytes = 8 MB
  Total at 3 layers × 5 timesteps = 120 MB (manageable)

Performance: Manual attention adds ~20-30% overhead vs SDPA. Acceptable for research tool.
"""

import logging
import math
from typing import Optional, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AttentionMapStore:
    """Stores captured attention maps across timesteps and layers."""

    capture_layers: List[int] = field(default_factory=lambda: [3, 9, 17])
    capture_steps: List[int] = field(default_factory=list)
    maps: Dict[str, Dict[str, list]] = field(default_factory=dict)

    # Current timestep tracking (set externally by callback)
    current_step: int = 0
    num_text_tokens: int = 0
    num_image_tokens: int = 0

    # Optional: indices of text columns to keep (e.g., CLIP-L word token positions)
    # If set, only these columns are stored, dramatically reducing JSON size.
    # Example: for "a house by the lake", CLIP-L tokenizes as [BOS, a, house, by, the, lake, EOS, PAD...]
    # text_column_indices would be [1, 2, 3, 4, 5] (skipping BOS/EOS/PAD)
    text_column_indices: Optional[List[int]] = None

    def should_capture(self, layer_idx: int) -> bool:
        """Check if we should capture attention at this layer/step."""
        return (
            self.current_step in self.capture_steps
            and layer_idx in self.capture_layers
        )

    def store(self, layer_idx: int, attention_map):
        """Store an attention map for the current step and layer.

        Args:
            layer_idx: Which transformer block
            attention_map: [image_tokens, text_tokens] tensor (already averaged across heads)
        """
        step_key = f"step_{self.current_step}"
        layer_key = f"layer_{layer_idx}"

        if step_key not in self.maps:
            self.maps[step_key] = {}

        # Truncate to only the relevant text token columns (huge JSON size reduction)
        if self.text_column_indices is not None:
            import torch
            indices = torch.tensor(self.text_column_indices, device=attention_map.device)
            attention_map = attention_map[:, indices]

        # Quantize to integers for compact JSON serialization.
        # Full float32 precision produces ~21 chars per value ("0.001500000013038516"),
        # integers produce ~2-4 chars ("15"). Frontend normalizes to max anyway,
        # so absolute scale doesn't matter — only relative proportions.
        # 126MB → ~15MB JSON, then gzip brings it to ~2-3MB.
        import torch
        quantized = (attention_map * 10000).round().to(torch.int32)
        self.maps[step_key][layer_key] = quantized.cpu().tolist()

    def clear(self):
        """Clear all stored maps."""
        self.maps.clear()
        self.current_step = 0


class AttentionCaptureProcessor:
    """
    Exact replica of JointAttnProcessor2_0 with optional attention map capture.

    When capture is active (matching layer + step), replaces SDPA with manual
    softmax(QK^T/√d) to extract text→image cross-attention weights.
    Otherwise uses efficient SDPA identically to the original processor.

    Verified against diffusers v0.36.0 JointAttnProcessor2_0.__call__.
    """

    def __init__(self, layer_idx: int, store: AttentionMapStore):
        self.layer_idx = layer_idx
        self.store = store

    def __call__(
        self,
        attn,
        hidden_states,
        encoder_hidden_states=None,
        attention_mask=None,
        *args,
        **kwargs,
    ):
        import torch
        import torch.nn.functional as F

        residual = hidden_states
        batch_size = hidden_states.shape[0]

        # `sample` projections (image/latent stream)
        query = attn.to_q(hidden_states)
        key = attn.to_k(hidden_states)
        value = attn.to_v(hidden_states)

        inner_dim = key.shape[-1]
        head_dim = inner_dim // attn.heads

        query = query.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        key = key.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        value = value.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)

        if attn.norm_q is not None:
            query = attn.norm_q(query)
        if attn.norm_k is not None:
            key = attn.norm_k(key)

        # `context` projections (text/encoder stream)
        if encoder_hidden_states is not None:
            encoder_hidden_states_query_proj = attn.add_q_proj(encoder_hidden_states)
            encoder_hidden_states_key_proj = attn.add_k_proj(encoder_hidden_states)
            encoder_hidden_states_value_proj = attn.add_v_proj(encoder_hidden_states)

            encoder_hidden_states_query_proj = encoder_hidden_states_query_proj.view(
                batch_size, -1, attn.heads, head_dim
            ).transpose(1, 2)
            encoder_hidden_states_key_proj = encoder_hidden_states_key_proj.view(
                batch_size, -1, attn.heads, head_dim
            ).transpose(1, 2)
            encoder_hidden_states_value_proj = encoder_hidden_states_value_proj.view(
                batch_size, -1, attn.heads, head_dim
            ).transpose(1, 2)

            if attn.norm_added_q is not None:
                encoder_hidden_states_query_proj = attn.norm_added_q(encoder_hidden_states_query_proj)
            if attn.norm_added_k is not None:
                encoder_hidden_states_key_proj = attn.norm_added_k(encoder_hidden_states_key_proj)

            # Concatenate: [image, text] along sequence dim (dim=2)
            query = torch.cat([query, encoder_hidden_states_query_proj], dim=2)
            key = torch.cat([key, encoder_hidden_states_key_proj], dim=2)
            value = torch.cat([value, encoder_hidden_states_value_proj], dim=2)

        # Attention computation
        should_capture = self.store.should_capture(self.layer_idx)

        if should_capture:
            # Manual attention to extract attention weights
            scale = 1.0 / math.sqrt(head_dim)
            attn_weights = torch.matmul(query, key.transpose(-2, -1)) * scale

            if attention_mask is not None:
                attn_weights = attn_weights + attention_mask

            attn_weights = F.softmax(attn_weights, dim=-1)

            # Extract text→image attention submatrix
            if encoder_hidden_states is not None:
                num_img = residual.shape[1]
                num_txt = encoder_hidden_states.shape[1]

                # attn_weights: [B, heads, img+txt, img+txt]
                # Image rows (0:num_img), text columns (num_img:num_img+num_txt)
                text_to_image_attn = attn_weights[:, :, :num_img, num_img:num_img + num_txt]
                avg_attn = text_to_image_attn.mean(dim=(0, 1))

                self.store.num_image_tokens = num_img
                self.store.num_text_tokens = num_txt
                self.store.store(self.layer_idx, avg_attn)

            hidden_states = torch.matmul(attn_weights, value)
        else:
            # Efficient SDPA (no map extraction)
            hidden_states = F.scaled_dot_product_attention(
                query, key, value, dropout_p=0.0, is_causal=False
            )

        hidden_states = hidden_states.transpose(1, 2).reshape(batch_size, -1, attn.heads * head_dim)
        hidden_states = hidden_states.to(query.dtype)

        if encoder_hidden_states is not None:
            # Split back into image and text streams
            hidden_states, encoder_hidden_states = (
                hidden_states[:, :residual.shape[1]],
                hidden_states[:, residual.shape[1]:],
            )
            if not attn.context_pre_only:
                encoder_hidden_states = attn.to_add_out(encoder_hidden_states)

        # Linear proj + dropout
        hidden_states = attn.to_out[0](hidden_states)
        hidden_states = attn.to_out[1](hidden_states)

        if encoder_hidden_states is not None:
            return hidden_states, encoder_hidden_states
        else:
            return hidden_states


def install_attention_capture(
    pipe,
    store: AttentionMapStore,
    capture_layers: Optional[List[int]] = None
) -> Dict[str, any]:
    """
    Install attention capture processors on an SD3 pipeline's transformer.

    Args:
        pipe: StableDiffusion3Pipeline instance
        store: AttentionMapStore to collect attention maps
        capture_layers: Which transformer block indices to capture (default: [3, 9, 17])

    Returns:
        Dict of original processors (for restoration)
    """
    if capture_layers is None:
        capture_layers = [3, 9, 17]

    store.capture_layers = capture_layers
    transformer = pipe.transformer

    original_processors = {}
    blocks = transformer.transformer_blocks

    for idx in capture_layers:
        if idx < len(blocks):
            block = blocks[idx]
            # Save original processor
            original_processors[f"block_{idx}"] = block.attn.processor
            # Install capture processor
            block.attn.set_processor(AttentionCaptureProcessor(idx, store))
            logger.info(f"[ATTENTION] Installed capture processor on block {idx}")
        else:
            logger.warning(f"[ATTENTION] Block index {idx} out of range (total: {len(blocks)})")

    logger.info(f"[ATTENTION] Capture installed on {len(original_processors)} blocks")
    return original_processors


def restore_attention_processors(
    pipe,
    original_processors: Dict[str, any],
    capture_layers: Optional[List[int]] = None
):
    """
    Restore original attention processors after capture.

    Args:
        pipe: StableDiffusion3Pipeline instance
        original_processors: Dict from install_attention_capture
        capture_layers: Which blocks to restore
    """
    if capture_layers is None:
        capture_layers = [3, 9, 17]

    transformer = pipe.transformer
    blocks = transformer.transformer_blocks

    for idx in capture_layers:
        key = f"block_{idx}"
        if key in original_processors and idx < len(blocks):
            blocks[idx].attn.set_processor(original_processors[key])
            logger.info(f"[ATTENTION] Restored original processor on block {idx}")

    logger.info(f"[ATTENTION] All processors restored")
