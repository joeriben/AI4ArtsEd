"""
Latent Lab Model Resolver — single source of truth for SD3.5 model selection
in pedagogical-platform Latent Lab Stage-4 chunks.

Policy: the Latent Lab runs SD3.5-Large on every card. SD 3.5 Large has to
fit in 32 GB, which is the platform's hardware profile. Earlier this module
answered SD3.5-Medium (24 MMDiT blocks against 38) on every card under 50 GB
total VRAM, with an environment override AI4ARTSED_LATENT_LAB_MODEL on top;
the "~50 GB peak" behind that threshold was measured on the Diffusers
introspection path. That fallback is gone: no threshold, no override, and
the card is not read here at all.

get_latent_lab_model_id() keeps its name and stays async, because it is the
ONE place the chunks take the model from, and the policy test holds every
chunk to it: a chunk that names the model as a literal decides it where
nobody looks for the decision.

CALLERS: pedagogical-platform Latent Lab chunks. The list is checked, chunk by
chunk, against LATENT_LAB_CHUNKS in devserver/tests/test_latent_lab_model_policy.py.
  - output_image_surrealizer_diffusers.py
  - output_image_feature_probing_diffusers.py
  - output_image_feature_probing_comfyui.py
  - output_image_attention_cartography_diffusers.py
  - output_image_attention_cartography_comfyui.py
  - output_image_concept_algebra_diffusers.py
  - output_image_concept_algebra_comfyui.py
  - output_image_denoising_archaeology_diffusers.py
  - output_image_denoising_archaeology_comfyui.py
  - output_image_composable_diffusion_diffusers.py
  - output_image_composable_diffusion_comfyui.py
"""

from __future__ import annotations

LATENT_LAB_LARGE = "stabilityai/stable-diffusion-3.5-large"

# The second backbone a Latent Lab instrument may offer beside SD3.5: a U-Net
# instead of an MMDiT. Denoising Archaeology uses it so that the same prompt and
# the same seed can be watched being denoised by two architectures. The pipeline
# class belongs with the ID -- a model and the class it loads under are one fact,
# and splitting them across two files is how they drift apart.
LATENT_LAB_UNET = "stabilityai/stable-diffusion-xl-base-1.0"
UNET_PIPELINE_CLASS = "StableDiffusionXLPipeline"
MMDIT_PIPELINE_CLASS = "StableDiffusion3Pipeline"


async def get_latent_lab_model_id() -> str:
    """The SD3.5 model the Latent Lab runs on: Large, on every card.

    Async and under its old name, because the chunks await it and the policy
    test (devserver/tests/test_latent_lab_model_policy.py) holds them to it.
    Nothing is read and nothing is cached: there is no reading a card could
    change the answer with.
    """
    return LATENT_LAB_LARGE


def get_latent_lab_unet() -> tuple:
    """Return (model_id, pipeline_class) of the U-Net backbone.

    SDXL is the smaller of the two backbones by a wide margin.
    """
    return LATENT_LAB_UNET, UNET_PIPELINE_CLASS


def get_mmdit_pipeline_class() -> str:
    """The pipeline class every SD3.5 model in this lab loads under."""
    return MMDIT_PIPELINE_CLASS
