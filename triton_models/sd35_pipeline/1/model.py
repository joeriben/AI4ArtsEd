"""
SD3.5 Pipeline Orchestrator for Triton Inference Server
Coordinates text encoding, denoising, and VAE decoding.
"""
import numpy as np
import torch
import triton_python_backend_utils as pb_utils


class TritonPythonModel:
    def initialize(self, args):
        self.device = "cuda"
        # Default parameters
        self.default_steps = 28
        self.default_guidance_scale = 4.5
        self.default_width = 1024
        self.default_height = 1024
        
    def execute(self, requests):
        responses = []
        for request in requests:
            prompt = pb_utils.get_input_tensor_by_name(request, "prompt").as_numpy()[0].decode()
            
            # Get optional parameters
            steps = self._get_optional_int(request, "num_inference_steps", self.default_steps)
            guidance = self._get_optional_float(request, "guidance_scale", self.default_guidance_scale)
            width = self._get_optional_int(request, "width", self.default_width)
            height = self._get_optional_int(request, "height", self.default_height)
            seed = self._get_optional_int(request, "seed", None)
            
            # Set seed if provided
            if seed is not None:
                torch.manual_seed(seed)
            
            # Step 1: Encode text using text_encoder model
            text_input = pb_utils.Tensor("prompt", np.array([[prompt]], dtype=object))
            text_request = pb_utils.InferenceRequest(
                model_name="sd35_text_encoder",
                requested_output_names=["encoder_hidden_states", "pooled_projections"],
                inputs=[text_input]
            )
            text_response = text_request.exec()
            encoder_hidden_states = pb_utils.get_output_tensor_by_name(text_response, "encoder_hidden_states").as_numpy()
            pooled_projections = pb_utils.get_output_tensor_by_name(text_response, "pooled_projections").as_numpy()
            
            # Step 2: Initialize latents
            latent_h = height // 8
            latent_w = width // 8
            latents = torch.randn(1, 16, latent_h, latent_w, device=self.device, dtype=torch.float16)
            
            # Step 3: Denoising loop
            # Note: This is simplified - full implementation needs proper scheduler
            timesteps = torch.linspace(999, 0, steps, device=self.device)
            
            for t in timesteps:
                # Call UNet/transformer
                unet_inputs = [
                    pb_utils.Tensor("hidden_states", latents.cpu().numpy()),
                    pb_utils.Tensor("encoder_hidden_states", encoder_hidden_states),
                    pb_utils.Tensor("pooled_projections", pooled_projections),
                    pb_utils.Tensor("timestep", np.array([[t.item()]], dtype=np.float16)),
                ]
                unet_request = pb_utils.InferenceRequest(
                    model_name="sd35_unet",
                    requested_output_names=["sample"],
                    inputs=unet_inputs
                )
                unet_response = unet_request.exec()
                noise_pred = pb_utils.get_output_tensor_by_name(unet_response, "sample").as_numpy()
                
                # Update latents (simplified Euler step)
                latents = latents - 0.01 * torch.from_numpy(noise_pred).to(self.device)
            
            # Step 4: VAE decode
            vae_input = pb_utils.Tensor("latent", latents.cpu().numpy())
            vae_request = pb_utils.InferenceRequest(
                model_name="sd35_vae",
                requested_output_names=["sample"],
                inputs=[vae_input]
            )
            vae_response = vae_request.exec()
            image = pb_utils.get_output_tensor_by_name(vae_response, "sample").as_numpy()
            
            # Convert to uint8
            image = ((image + 1) * 127.5).clip(0, 255).astype(np.uint8)
            image = np.transpose(image[0], (1, 2, 0))  # CHW -> HWC
            
            out_image = pb_utils.Tensor("image", image)
            responses.append(pb_utils.InferenceResponse([out_image]))
        
        return responses
    
    def _get_optional_int(self, request, name, default):
        tensor = pb_utils.get_input_tensor_by_name(request, name)
        return int(tensor.as_numpy()[0]) if tensor is not None else default
    
    def _get_optional_float(self, request, name, default):
        tensor = pb_utils.get_input_tensor_by_name(request, name)
        return float(tensor.as_numpy()[0]) if tensor is not None else default
    
    def finalize(self):
        pass
