import torch
import numpy as np

"""
ai4artsed_vector_dimension_eliminator.py
---------------------------------------
Experimental node for eliminating specific dimensions in conditioning vectors
to explore their semantic meaning in the generation process.

This node allows targeted manipulation of conditioning tensor dimensions to
understand how individual or groups of dimensions affect the final output.
"""

NODE_NAME = "AI4ArtsEd Vector Dimension Eliminator"

class ai4artsed_vector_dimension_eliminator:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "start_dimension": ("INT", {"default": 0, "min": 0, "max": 10000, "step": 1}),
                "num_dimensions": ("INT", {"default": 100, "min": 1, "max": 10000, "step": 1}),
                "fill_value": ("FLOAT", {"default": 0.0, "min": -10.0, "max": 10.0, "step": 0.01}),
                "mode": (["zero_out", "random", "average", "invert"], {"default": "zero_out"}),
            },
            "optional": {
                "output_info": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "dimension_info")
    FUNCTION = "eliminate_dimensions"
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
                return tokens, pooled, inner_list[1]  # Return full dict for preservation
        
        raise ValueError(f"Could not extract tensor from conditioning of type: {type(conditioning)}")

    def eliminate_dimensions(self, conditioning, start_dimension, num_dimensions, fill_value, mode, output_info=False):
        print(f"\n--- Running AI4ArtsEd Vector Dimension Eliminator ---")
        print(f"Mode: {mode}")
        print(f"Start dimension: {start_dimension}")
        print(f"Number of dimensions: {num_dimensions}")
        print(f"Fill value: {fill_value}")
        
        try:
            # Extract tensor and metadata
            tokens, pooled, metadata_dict = self._extract_tensor_and_pooled(conditioning)
            
            # Get tensor info
            batch_size, seq_len, embed_dim = tokens.shape
            print(f"Conditioning shape: {tokens.shape}")
            print(f"Batch size: {batch_size}, Sequence length: {seq_len}, Embedding dim: {embed_dim}")
            
            # Validate dimension indices
            if start_dimension >= embed_dim:
                print(f"WARNING: Start dimension {start_dimension} >= embedding dimension {embed_dim}. No modification will be made.")
                info_string = f"No modification: start_dimension ({start_dimension}) out of bounds"
                return (conditioning, info_string)
            
            # Calculate actual dimensions to modify
            end_dimension = min(start_dimension + num_dimensions, embed_dim)
            actual_num_dims = end_dimension - start_dimension
            print(f"Modifying dimensions {start_dimension} to {end_dimension-1} (total: {actual_num_dims} dimensions)")
            
            # Clone tensors to avoid in-place modification
            modified_tokens = tokens.clone()
            modified_pooled = pooled.clone() if pooled is not None else None
            
            # Apply dimension elimination based on mode
            if mode == "zero_out":
                # Set specified dimensions to zero
                modified_tokens[:, :, start_dimension:end_dimension] = 0.0
                if modified_pooled is not None and start_dimension < modified_pooled.shape[-1]:
                    pooled_end = min(end_dimension, modified_pooled.shape[-1])
                    modified_pooled[:, start_dimension:pooled_end] = 0.0
                    
            elif mode == "random":
                # Fill with random values
                random_values = torch.randn_like(modified_tokens[:, :, start_dimension:end_dimension])
                # Scale random values to match typical embedding magnitudes
                embedding_std = tokens.std()
                random_values = random_values * embedding_std * 0.5  # Use half the std for safety
                modified_tokens[:, :, start_dimension:end_dimension] = random_values
                if modified_pooled is not None and start_dimension < modified_pooled.shape[-1]:
                    pooled_end = min(end_dimension, modified_pooled.shape[-1])
                    pooled_random = torch.randn_like(modified_pooled[:, start_dimension:pooled_end])
                    modified_pooled[:, start_dimension:pooled_end] = pooled_random * embedding_std * 0.5
                    
            elif mode == "average":
                # Fill with average value of the entire embedding
                avg_value = tokens.mean()
                modified_tokens[:, :, start_dimension:end_dimension] = avg_value
                if modified_pooled is not None and start_dimension < modified_pooled.shape[-1]:
                    pooled_end = min(end_dimension, modified_pooled.shape[-1])
                    pooled_avg = pooled.mean()
                    modified_pooled[:, start_dimension:pooled_end] = pooled_avg
                    
            elif mode == "invert":
                # Invert the sign of specified dimensions
                modified_tokens[:, :, start_dimension:end_dimension] *= -1.0
                if modified_pooled is not None and start_dimension < modified_pooled.shape[-1]:
                    pooled_end = min(end_dimension, modified_pooled.shape[-1])
                    modified_pooled[:, start_dimension:pooled_end] *= -1.0
            
            else:  # Custom fill value
                modified_tokens[:, :, start_dimension:end_dimension] = fill_value
                if modified_pooled is not None and start_dimension < modified_pooled.shape[-1]:
                    pooled_end = min(end_dimension, modified_pooled.shape[-1])
                    modified_pooled[:, start_dimension:pooled_end] = fill_value
            
            # Calculate statistics for info output
            if output_info:
                # Compare original vs modified
                diff_norm = torch.norm(tokens - modified_tokens)
                relative_change = diff_norm / (torch.norm(tokens) + 1e-8)
                
                # Per-dimension statistics
                original_dim_mean = tokens[:, :, start_dimension:end_dimension].mean().item()
                original_dim_std = tokens[:, :, start_dimension:end_dimension].std().item()
                modified_dim_mean = modified_tokens[:, :, start_dimension:end_dimension].mean().item()
                modified_dim_std = modified_tokens[:, :, start_dimension:end_dimension].std().item()
                
                info_parts = [
                    f"=== Vector Dimension Eliminator Info ===",
                    f"Mode: {mode}",
                    f"Tensor shape: {list(tokens.shape)}",
                    f"Modified dimensions: {start_dimension}-{end_dimension-1} ({actual_num_dims} dims)",
                    f"Relative change: {relative_change:.4f}",
                    f"",
                    f"Original dims - Mean: {original_dim_mean:.4f}, Std: {original_dim_std:.4f}",
                    f"Modified dims - Mean: {modified_dim_mean:.4f}, Std: {modified_dim_std:.4f}",
                    f"",
                    f"Percentage of embedding modified: {(actual_num_dims/embed_dim)*100:.1f}%"
                ]
                info_string = "\n".join(info_parts)
            else:
                info_string = f"Modified dims {start_dimension}-{end_dimension-1} ({mode})"
            
            # Repackage conditioning with modified tensors
            new_metadata = metadata_dict.copy()
            if modified_pooled is not None:
                new_metadata['pooled_output'] = modified_pooled
                
            result_conditioning = [[modified_tokens, new_metadata]]
            
            print(f"--- Vector elimination successful ---\n")
            return (result_conditioning, info_string)
            
        except Exception as e:
            # Said, not hidden: until 2026-10-10 this returned the conditioning
            # untouched, with the error in the info string, under a successful
            # run (finding S-013 of the code review of 2026-10-10).
            print(f"\nERROR in AI4ArtsEd Vector Dimension Eliminator: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

# ---- ComfyUI registration ---------------------------------------------------


