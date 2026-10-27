"""
SD3.5 Text Encoder for Triton Inference Server
Uses transformers library to encode text prompts.
"""
import json
import numpy as np
import torch
import triton_python_backend_utils as pb_utils
from transformers import CLIPTokenizer, CLIPTextModelWithProjection, T5EncoderModel, T5Tokenizer


class TritonPythonModel:
    def initialize(self, args):
        self.device = "cuda"
        model_id = "stabilityai/stable-diffusion-3.5-large"
        
        # Load tokenizers
        self.tokenizer = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer")
        self.tokenizer_2 = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer_2")
        self.tokenizer_3 = T5Tokenizer.from_pretrained(model_id, subfolder="tokenizer_3")
        
        # Load text encoders
        self.text_encoder = CLIPTextModelWithProjection.from_pretrained(
            model_id, subfolder="text_encoder", torch_dtype=torch.float16
        ).to(self.device)
        self.text_encoder_2 = CLIPTextModelWithProjection.from_pretrained(
            model_id, subfolder="text_encoder_2", torch_dtype=torch.float16
        ).to(self.device)
        self.text_encoder_3 = T5EncoderModel.from_pretrained(
            model_id, subfolder="text_encoder_3", torch_dtype=torch.float16
        ).to(self.device)
        
    def execute(self, requests):
        responses = []
        for request in requests:
            prompt = pb_utils.get_input_tensor_by_name(request, "prompt").as_numpy()[0].decode()
            
            # Encode with all three encoders
            with torch.no_grad():
                # CLIP-L
                tokens_1 = self.tokenizer(prompt, return_tensors="pt", padding="max_length", max_length=77, truncation=True)
                text_embeddings_1 = self.text_encoder(tokens_1.input_ids.to(self.device))
                
                # CLIP-G
                tokens_2 = self.tokenizer_2(prompt, return_tensors="pt", padding="max_length", max_length=77, truncation=True)
                text_embeddings_2 = self.text_encoder_2(tokens_2.input_ids.to(self.device))
                
                # T5-XXL
                tokens_3 = self.tokenizer_3(prompt, return_tensors="pt", padding="max_length", max_length=256, truncation=True)
                text_embeddings_3 = self.text_encoder_3(tokens_3.input_ids.to(self.device)).last_hidden_state
                
                # Combine embeddings (SD3.5 specific concatenation)
                pooled = torch.cat([text_embeddings_1.text_embeds, text_embeddings_2.text_embeds], dim=-1)
                encoder_hidden_states = torch.cat([
                    text_embeddings_1.last_hidden_state,
                    text_embeddings_2.last_hidden_state,
                    text_embeddings_3,
                ], dim=1)
            
            out_encoder = pb_utils.Tensor("encoder_hidden_states", encoder_hidden_states.cpu().numpy())
            out_pooled = pb_utils.Tensor("pooled_projections", pooled.cpu().numpy())
            responses.append(pb_utils.InferenceResponse([out_encoder, out_pooled]))
        
        return responses
    
    def finalize(self):
        pass
