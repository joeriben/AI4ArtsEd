import torch
import math

"""
ai4artsed_conditioning_fusion.py
--------------------------------
Enhanced conditioning fusion node with multiple interpolation methods for exploring
semantic spaces between two conditioning tensors.

Interpolation Methods:
    • Linear (LERP): Standard linear interpolation (1-α)A + αB
    • Spherical (SLERP): Interpolation along the unit sphere
    • Multi-step: Progressive blending through intermediate steps
    • Latent-aware: Magnitude-normalized interpolation for better semantic preservation
"""

NODE_NAME = "AI4ArtsEd Conditioning Fusion"

class ai4artsed_conditioning_fusion:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning_a": ("CONDITIONING",),
                "conditioning_b": ("CONDITIONING",),
                "alpha": ("FLOAT", {"default": 0.5, "min": -5, "max": 5, "step": 0.01}),
                "interpolation_method": (["linear", "spherical", "multi_step", "latent_aware"], {"default": "linear"}),
                "steps": ("INT", {"default": 3, "min": 2, "max": 10, "step": 1}),  # For multi-step method
            },
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "fuse"
    CATEGORY = "AI4ArtsEd"

    def _extract_tensor_and_pooled(self, conditioning):
        """Helper function to robustly extract tensors and pooled output."""
        if not conditioning:
            raise ValueError("Input conditioning is empty.")

        if isinstance(conditioning, list) and len(conditioning) > 0 and isinstance(conditioning[0], list):
            inner_list = conditioning[0]
            if len(inner_list) == 2 and isinstance(inner_list[0], torch.Tensor):
                tokens = inner_list[0]
                pooled = inner_list[1].get('pooled_output')
                if pooled is None:
                    pooled = torch.zeros(tokens.shape[0], tokens.size(-1), dtype=tokens.dtype, device=tokens.device)
                return tokens, pooled
        
        raise ValueError(f"Could not extract tensor from conditioning of type: {type(conditioning)}")

    def _linear_interpolation(self, a, b, alpha):
        """Standard linear interpolation."""
        return (1.0 - alpha) * a + alpha * b

    def _spherical_interpolation(self, a, b, alpha):
        """Spherical linear interpolation (SLERP)."""
        # Normalize vectors
        a_norm = torch.nn.functional.normalize(a, dim=-1)
        b_norm = torch.nn.functional.normalize(b, dim=-1)
        
        # Calculate dot product (cosine of angle)
        dot = torch.sum(a_norm * b_norm, dim=-1, keepdim=True)
        
        # Clamp to avoid numerical issues
        dot = torch.clamp(dot, -1.0, 1.0)
        
        # Calculate angle
        theta = torch.acos(torch.abs(dot))
        
        # Handle near-parallel vectors
        sin_theta = torch.sin(theta)
        mask = sin_theta < 1e-6
        
        # SLERP formula
        result = torch.where(
            mask,
            self._linear_interpolation(a_norm, b_norm, alpha),  # Fallback to linear for parallel vectors
            (torch.sin((1.0 - alpha) * theta) * a_norm + torch.sin(alpha * theta) * b_norm) / sin_theta
        )
        
        # Restore original magnitudes
        a_mag = torch.norm(a, dim=-1, keepdim=True)
        b_mag = torch.norm(b, dim=-1, keepdim=True)
        result_mag = (1.0 - alpha) * a_mag + alpha * b_mag
        
        return result * result_mag

    def _multi_step_interpolation(self, a, b, alpha, steps):
        """Multi-step interpolation through intermediate points."""
        if steps <= 2:
            return self._linear_interpolation(a, b, alpha)
        
        # Create intermediate steps
        step_size = 1.0 / (steps - 1)
        current = a.clone()
        
        for i in range(1, steps):
            step_alpha = i * step_size
            if step_alpha >= alpha:
                # Interpolate between previous step and current target
                local_alpha = (alpha - (i-1) * step_size) / step_size
                prev_step_alpha = (i-1) * step_size
                prev = self._linear_interpolation(a, b, prev_step_alpha)
                curr = self._linear_interpolation(a, b, step_alpha)
                return self._linear_interpolation(prev, curr, local_alpha)
        
        return self._linear_interpolation(a, b, alpha)

    def _latent_aware_interpolation(self, a, b, alpha):
        """Magnitude-aware interpolation for better semantic preservation."""
        # Calculate magnitudes
        a_mag = torch.norm(a, dim=-1, keepdim=True)
        b_mag = torch.norm(b, dim=-1, keepdim=True)
        
        # Normalize to unit vectors
        a_unit = a / (a_mag + 1e-8)
        b_unit = b / (b_mag + 1e-8)
        
        # Interpolate directions using SLERP
        direction = self._spherical_interpolation(a_unit, b_unit, alpha)
        
        # Interpolate magnitudes separately
        magnitude = (1.0 - alpha) * a_mag + alpha * b_mag
        
        # Combine direction and magnitude
        return direction * magnitude

    def fuse(self, conditioning_a, conditioning_b, alpha, interpolation_method, steps):
        print(f"\n--- Running AI4ArtsEd Conditioning Fusion Node ({interpolation_method}) ---")
        try:
            # Extract tensors and pooled outputs
            tokens_a, pooled_a = self._extract_tensor_and_pooled(conditioning_a)
            tokens_b, pooled_b = self._extract_tensor_and_pooled(conditioning_b)

            print(f"Conditioning A shape: {tokens_a.shape}")
            print(f"Conditioning B shape: {tokens_b.shape}")
            print(f"Alpha value: {alpha}")
            print(f"Interpolation method: {interpolation_method}")

            # Validate shapes
            if tokens_a.shape[0] != tokens_b.shape[0]:
                raise ValueError(f"Batch size mismatch: A has {tokens_a.shape[0]} but B has {tokens_b.shape[0]}.")
            if tokens_a.shape[-1] != tokens_b.shape[-1]:
                raise ValueError(f"Embedding dimension mismatch: A is {tokens_a.shape[-1]}D but B is {tokens_b.shape[-1]}D.")

            # Determine lengths for blending
            len_a = tokens_a.shape[1]
            len_b = tokens_b.shape[1]
            interp_len = min(len_a, len_b)
            
            print(f"Blending the first {interp_len} tokens using {interpolation_method} interpolation.")

            # Slice tensors for interpolation
            interp_part_a = tokens_a[:, :interp_len, :]
            interp_part_b = tokens_b[:, :interp_len, :]

            # Apply selected interpolation method
            if interpolation_method == "linear":
                interpolated_tokens = self._linear_interpolation(interp_part_a, interp_part_b, alpha)
            elif interpolation_method == "spherical":
                interpolated_tokens = self._spherical_interpolation(interp_part_a, interp_part_b, alpha)
            elif interpolation_method == "multi_step":
                interpolated_tokens = self._multi_step_interpolation(interp_part_a, interp_part_b, alpha, steps)
            elif interpolation_method == "latent_aware":
                interpolated_tokens = self._latent_aware_interpolation(interp_part_a, interp_part_b, alpha)
            else:
                interpolated_tokens = self._linear_interpolation(interp_part_a, interp_part_b, alpha)

            # Handle remainder tokens
            append_part = torch.empty((tokens_a.shape[0], 0, tokens_a.shape[2]), dtype=tokens_a.dtype, device=tokens_a.device)
            if len_a > len_b:
                append_part = tokens_a[:, interp_len:, :]
                print(f"Appending remaining {append_part.shape[1]} tokens from Conditioning A.")
            elif len_b > len_a:
                append_part = tokens_b[:, interp_len:, :]
                print(f"Appending remaining {append_part.shape[1]} tokens from Conditioning B.")

            # Concatenate final result
            fused_tokens = torch.cat([interpolated_tokens, append_part], dim=1)

            # Blend pooled outputs using the same method
            if interpolation_method == "spherical":
                fused_pooled = self._spherical_interpolation(pooled_a, pooled_b, alpha)
            elif interpolation_method == "latent_aware":
                fused_pooled = self._latent_aware_interpolation(pooled_a, pooled_b, alpha)
            else:
                fused_pooled = self._linear_interpolation(pooled_a, pooled_b, alpha)
            
            print(f"Final fused conditioning shape: {fused_tokens.shape}")

            # Repackage result
            result_conditioning = [[fused_tokens, {"pooled_output": fused_pooled}]]
            
            print("--- Fusion successful ---\n")
            return (result_conditioning,)

        except Exception as e:
            # Said, not hidden: until 2026-10-10 this returned conditioning A
            # unfused under a successful run (finding S-013 of the code review of 2026-10-10).
            print(f"\nERROR in AI4ArtsEd Conditioning Fusion: {str(e)}")
            raise

# ---- ComfyUI registration ---------------------------------------------------


