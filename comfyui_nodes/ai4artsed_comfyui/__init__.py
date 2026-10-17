from .ai4artsed_text_remix import ai4artsed_text_remix
from .ai4artsed_random_instruction_generator import ai4artsed_random_instruction_generator
from .ai4artsed_random_artform_generator import ai4artsed_random_artform_generator
from .ai4artsed_random_language_selector import ai4artsed_random_language_selector
from .ai4artsed_openrouter_key import ai4artsed_openrouter_key
from .ai4artsed_t5_clip_fusion import ai4artsed_t5_clip_fusion
from .ai4artsed_conditioning_fusion import ai4artsed_conditioning_fusion
from .ai4artsed_prompt_interception import ai4artsed_prompt_interception
from .ai4artsed_image_analysis import ai4artsed_image_analysis
from .ai4artsed_vector_dimension_eliminator import ai4artsed_vector_dimension_eliminator
from .ai4artsed_switch_promptsafety import ai4artsed_switch_promptsafety
from .ai4artsed_photo_prompt_randomizer import ai4artsed_photo_prompt_randomizer
from .ai4artsed_clean_prompt_randomizer import ai4artsed_clean_prompt_randomizer
from .ai4artsed_local_llm import ai4artsed_local_llm
from .ai4artsed_text_probes import ai4artsed_llm_option_scores, ai4artsed_llm_rep_engineering
from .ai4artsed_stable_audio import ai4artsed_stable_audio
from .ai4artsed_audio_synth import ai4artsed_audio_synth
from .ai4artsed_image_guided_audio import ai4artsed_image_guided_audio
from .ai4artsed_mmaudio import ai4artsed_mmaudio
from .ai4artsed_heartmula import ai4artsed_heartmula
from .ai4artsed_hunyuan3d import ai4artsed_hunyuan3d
from .ai4artsed_media_reading import ai4artsed_media_reading

# The tokenizers of the Latent Lab's text side answer on ComfyUI's own HTTP
# server, off the queue (_tokenizer_routes.py). Outside ComfyUI there is no
# server to register on, and install() says so by answering False; a fault in
# the routes is logged there, and the nodes below stay registered either way.
try:
    from . import _tokenizer_routes
    _tokenizer_routes.install()
except Exception as _e:
    import logging
    logging.getLogger(__name__).error(f"[AI4ArtsEd] tokenizer routes stay unregistered: {_e}")

# The media stations (Stable Audio 3, ImageBind, MMAudio, HeartMuLa, Hunyuan3D,
# the media readers) report which library is importable and which weights are
# installed on GET /ai4artsed/stations (_station_routes.py); the DevServer's
# backend status reads it. Same shape as the tokenizer routes.
try:
    from . import _station_routes
    _station_routes.install()
except Exception as _e:
    import logging
    logging.getLogger(__name__).error(f"[AI4ArtsEd] station routes stay unregistered: {_e}")

# What ComfyUI holds on the card — its own models and the stations' — on
# GET /ai4artsed/card (_card_routes.py); the DevServer's gate reads it for
# the settings page and the workshop companion. Same shape as the two above.
try:
    from . import _card_routes
    _card_routes.install()
except Exception as _e:
    import logging
    logging.getLogger(__name__).error(f"[AI4ArtsEd] card route stays unregistered: {_e}")

NODE_CLASS_MAPPINGS = {
    "ai4artsed_text_remix": ai4artsed_text_remix,
    "ai4artsed_random_instruction_generator": ai4artsed_random_instruction_generator,
    "ai4artsed_random_artform_generator": ai4artsed_random_artform_generator,
    "ai4artsed_random_language_selector": ai4artsed_random_language_selector,
    "ai4artsed_openrouter_key": ai4artsed_openrouter_key,
    "ai4artsed_t5_clip_fusion": ai4artsed_t5_clip_fusion,
    "ai4artsed_conditioning_fusion": ai4artsed_conditioning_fusion,
    "ai4artsed_prompt_interception": ai4artsed_prompt_interception,
    "ai4artsed_image_analysis": ai4artsed_image_analysis,
    "ai4artsed_vector_dimension_eliminator": ai4artsed_vector_dimension_eliminator,
    "ai4artsed_switch_promptsafety": ai4artsed_switch_promptsafety,
    "ai4artsed_photo_prompt_randomizer": ai4artsed_photo_prompt_randomizer,
    "ai4artsed_clean_prompt_randomizer": ai4artsed_clean_prompt_randomizer,
    "ai4artsed_local_llm": ai4artsed_local_llm,
    "ai4artsed_llm_option_scores": ai4artsed_llm_option_scores,
    "ai4artsed_llm_rep_engineering": ai4artsed_llm_rep_engineering,
    "ai4artsed_stable_audio": ai4artsed_stable_audio,
    "ai4artsed_audio_synth": ai4artsed_audio_synth,
    "ai4artsed_image_guided_audio": ai4artsed_image_guided_audio,
    "ai4artsed_mmaudio": ai4artsed_mmaudio,
    "ai4artsed_heartmula": ai4artsed_heartmula,
    "ai4artsed_hunyuan3d": ai4artsed_hunyuan3d,
    "ai4artsed_media_reading": ai4artsed_media_reading,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ai4artsed_text_remix": "AI4ArtsEd Text Remix",
    "ai4artsed_random_instruction_generator": "AI4ArtsEd Random Instruction Generator",
    "ai4artsed_random_artform_generator": "AI4ArtsEd Random Artform Generator",
    "ai4artsed_random_language_selector": "AI4ArtsEd Random Language Selector",
    "ai4artsed_openrouter_key": "AI4ArtsEd OpenRouter Key",
    "ai4artsed_t5_clip_fusion": "AI4ArtsEd T5-CLIP Fusion",
    "ai4artsed_conditioning_fusion": "AI4ArtsEd Conditioning Fusion",
    "ai4artsed_prompt_interception": "AI4ArtsEd Prompt Interception",
    "ai4artsed_image_analysis": "AI4ArtsEd Image Analysis",
    "ai4artsed_vector_dimension_eliminator": "AI4ArtsEd Vector Dimension Eliminator",
    "ai4artsed_switch_promptsafety": "AI4ArtsEd Promptsafety Switch",
    "ai4artsed_photo_prompt_randomizer": "AI4ArtsEd Photo Prompt Randomizer",
    "ai4artsed_clean_prompt_randomizer": "AI4ArtsEd Clean Prompt Randomizer",
    "ai4artsed_local_llm": "AI4ArtsEd Local LLM",
    "ai4artsed_llm_option_scores": "AI4ArtsEd LLM Option Scores",
    "ai4artsed_llm_rep_engineering": "AI4ArtsEd LLM Representation Engineering",
    "ai4artsed_stable_audio": "AI4ArtsEd Stable Audio",
    "ai4artsed_audio_synth": "AI4ArtsEd Audio Synth",
    "ai4artsed_image_guided_audio": "AI4ArtsEd Image-Guided Audio",
    "ai4artsed_mmaudio": "AI4ArtsEd MMAudio",
    "ai4artsed_heartmula": "AI4ArtsEd HeartMuLa",
    "ai4artsed_hunyuan3d": "AI4ArtsEd Hunyuan3D",
    "ai4artsed_media_reading": "AI4ArtsEd Media Reading",
}
