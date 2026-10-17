import torch
from comfy.model_patcher import ModelPatcher

"""
ai4artsed_t5_clip_fusion.py
---------------------------
This node is opensource provided by the ai4artsed project.
Conceptualization: Benjamin Jörissen, https://github.com/joeriben, coding: ChatGPT o3 & claude-3-opus

**Purpose**
    Fuse conditioning from a CLIP-based encoder (like CLIP-L) and a long-context
    T5 encoder. This is intended for models that can handle variable-length
    conditioning, such as Stable Diffusion 3.
    
**Requirements**
clip_g.safetensors
clip_l.safetensors
t5xxlenconly.safetensors
    
*****************************************************************************************
THIS NODE DOES NOT WORK AS INTENDED IN THIS VERSION. HOWEVER, THE OUTPUT IS FUN TO PLAY WITH:

GENERALLY: negative alpha values = more boring; positive values = more weird

< -75 blackout
< -30 lost it completely
< -18.5 lost it ...
< -4 beginning to loose prompt ... (CLIP only)
< -1.5 = no influence from t5 anymore

-1.5 < X < +2 = reasonable mix of CLIP and t5

>2 = beginning to loose prompt ... (t5 mainly from here on)
>7 = lost it
>10 = ... completely
>76 blackout
*****************************************************************************************

    

Workflow:
    1. A short prompt (<= 77 tokens) is encoded using a CLIP model.
    2. A long prompt is encoded using a T5 model, resulting in potentially
       many more than 77 tokens.
    3. This node fuses the two embeddings according to a specific strategy.

How it works:
    • It takes two conditioning inputs: `clip_conditioning` and `t5_conditioning`.
    • The first part of the embeddings (up to 77 tokens) are interpolated.
    • The remaining tokens from the T5 embedding (beyond the 77th token) are
      appended to the result.

Token handling:
    1. **Interpolation (Tokens 1-77):** The first 77 tokens from the CLIP
       embedding are linearly interpolated (LERP) with the first 77 tokens
       from the T5 embedding. The `alpha` parameter controls this blend.
       - `fused = (1 - alpha) * clip_token + alpha * t5_token`
    2. **Concatenation (Tokens 78+):** All tokens from the T5 embedding *after*
       the 77th token are taken as-is and concatenated to the end of the
       interpolated result.
    
    This results in a final conditioning tensor that has the blended style and
    semantics of both models for the first 77 tokens, plus the extended semantic
    context from the T5 model for the remainder of the prompt.

Alpha parameter
    • `alpha` (0–1) controls the interpolation.
      - `alpha=0`: The first 77 tokens are 100% from CLIP.
      - `alpha=1`: The first 77 tokens are 100% from T5.
      - `alpha=0.5`: An equal 50/50 blend between CLIP and T5.
    • The tokens appended from T5 are not affected by `alpha`.
    
Important:
    • This node assumes the embedding dimensions of both `clip_conditioning`
      and `t5_conditioning` are identical. It will raise an error if they differ.
      (e.g., both must be 768-dim, or both 1024-dim, etc.).

Category
    • Registered under "AI4ArtsEd" in ComfyUI's node tree.
"""

NODE_NAME = "AI4ArtsEd T5‑CLIP Fusion"

class ai4artsed_t5_clip_fusion:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "clip_conditioning": ("CONDITIONING",),
                "t5_conditioning": ("CONDITIONING",),
                "alpha": ("FLOAT", {"default": 0.75, "min": -75, "max": 75, "step": 0.005}),
            },
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "fuse"
    CATEGORY = "AI4ArtsEd"

    def _extract_tensor_and_pooled(self, conditioning):
        """Helper function to robustly extract tensors and pooled output."""
        if not conditioning:
            raise ValueError("Input conditioning is empty.")

        # Handle nested list structure from ComfyUI: [[tensor, dict]]
        if isinstance(conditioning, list) and len(conditioning) > 0 and isinstance(conditioning[0], list):
            inner_list = conditioning[0]
            if len(inner_list) == 2 and isinstance(inner_list[0], torch.Tensor):
                tokens = inner_list[0]
                pooled = inner_list[1].get('pooled_output')
                if pooled is None:
                    # Create a default pooled output if not available
                    pooled = torch.zeros(tokens.shape[0], tokens.size(-1), dtype=tokens.dtype, device=tokens.device)
                return tokens, pooled, True # Return format marker

        # Handle standard tuple/list structure: (tensor, dict)
        elif isinstance(conditioning, (list, tuple)) and len(conditioning) == 2 and isinstance(conditioning[0], torch.Tensor):
            tokens, pool_dict = conditioning[0], conditioning[1]
            pooled = pool_dict.get('pooled_output')
            if pooled is None:
                pooled = torch.zeros(tokens.shape[0], tokens.size(-1), dtype=tokens.dtype, device=tokens.device)
            return tokens, pooled, False # Return format marker
            
        raise ValueError(f"Could not extract tensor from conditioning of type: {type(conditioning)}")


    def fuse(self, clip_conditioning, t5_conditioning, alpha):
        print("\n--- Running AI4ArtsEd T5-CLIP Fusion Node ---")
        try:
            # 1. Extract tensors and pooled outputs from conditioning data
            clip_tokens, clip_pooled, is_nested_list_format = self._extract_tensor_and_pooled(clip_conditioning)
            t5_tokens, _, _ = self._extract_tensor_and_pooled(t5_conditioning) # We don't need the T5 pooled output

            print(f"CLIP tokens shape: {clip_tokens.shape}")
            print(f"T5 tokens shape:   {t5_tokens.shape}")
            print(f"Alpha value: {alpha}")

            # 2. Validate shapes and dimensions
            if clip_tokens.shape[0] != t5_tokens.shape[0]:
                raise ValueError(f"Batch size mismatch: CLIP has batch size {clip_tokens.shape[0]} but T5 has {t5_tokens.shape[0]}.")
            if clip_tokens.shape[-1] != t5_tokens.shape[-1]:
                raise ValueError(f"Embedding dimension mismatch: CLIP is {clip_tokens.shape[-1]}D but T5 is {t5_tokens.shape[-1]}D. They must be the same.")

            # 3. Define interpolation length and slice tensors
            # We interpolate up to 77 tokens, or fewer if the CLIP embedding is shorter.
            interp_len = min(77, clip_tokens.shape[1])
            
            # Ensure T5 has enough tokens for interpolation part
            if t5_tokens.shape[1] < interp_len:
                 raise ValueError(f"T5 conditioning is too short ({t5_tokens.shape[1]} tokens) to be interpolated with CLIP conditioning ({interp_len} tokens).")


            clip_interp_part = clip_tokens[:, :interp_len, :]
            t5_interp_part = t5_tokens[:, :interp_len, :]
            
            # The part of the T5 embedding to be appended is everything AFTER the interpolated part.
            # This correctly handles cases where t5 is exactly interp_len long (resulting in an empty tensor).
            t5_append_part = t5_tokens[:, interp_len:, :]
            
            print(f"Interpolating the first {interp_len} tokens.")
            if t5_append_part.shape[1] > 0:
                print(f"Appending the remaining {t5_append_part.shape[1]} tokens from T5.")

            # 4. Perform the linear interpolation (LERP)
            # fused = (1-alpha)*clip + alpha*t5
            interpolated_part = (1.0 - alpha) * clip_interp_part + alpha * t5_interp_part
            
            # 5. Concatenate the interpolated part with the rest of the T5 embeddings
            fused_tokens = torch.cat([interpolated_part, t5_append_part], dim=1)
            
            print(f"Final fused conditioning shape: {fused_tokens.shape}")

            # 6. Repackage the result into the original conditioning format
            # We use the pooled output from the original CLIP conditioning.
            if is_nested_list_format:
                # ComfyUI's standard [[tensor, {"pooled_output": pooled_tensor}]] format
                result_conditioning = [[fused_tokens, {"pooled_output": clip_pooled}]]
            else:
                # Older tuple format (tensor, {"pooled_output": pooled_tensor})
                # Note: Returning a list is generally safer and more compatible.
                result_conditioning = [[fused_tokens, {"pooled_output": clip_pooled}]]

            print("--- Fusion successful ---\n")
            return (result_conditioning,)

        except Exception as e:
            # Said, not hidden: until 2026-10-10 this returned the CLIP
            # conditioning unfused, and the run sampled a picture without the
            # fusion under a successful run (finding S-013 of the code review of 2026-10-10). ComfyUI reports the
            # exception as the run's error, and the DevServer reads it as one.
            print(f"\nERROR in AI4ArtsEd T5-CLIP Fusion: {str(e)}")
            raise

