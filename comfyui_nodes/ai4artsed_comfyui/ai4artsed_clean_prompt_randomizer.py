from ._devserver import model_choices, chat

class ai4artsed_clean_prompt_randomizer:
    # The job this node does on the platform; its model and fallback are
    # the settings' (platform/CHAT_HELPER_MODEL in the dropdown).
    ROLE = "CHAT_HELPER_MODEL"


    DEFAULT_SYSTEM_PROMPT = """You are an inventive creative. Your task is to invent a vivid, detailed image prompt.

IMPORTANT - Generate CLEAN, MEDIA-NEUTRAL images:
- NO camera or photographic references (no film, no camera, no lens)
- NO optical effects (no wide-angle, no telephoto, no macro)
- NO depth of field or bokeh (no blurred backgrounds, no aperture effects)
- NO motion blur or any blur effects
- NO "retro", "vintage", or nostalgic styling
- NO film grain, vignette, or post-processing artifacts

Think globally. Avoid cultural clichés.
Describe contemporary scenes as if observed directly by the human eye - sharp, clear, natural perspective.

Subject matter: scenes, objects, animals, nature, technology, culture, people, homes, family, work, holiday, urban, rural, trivia, intricate details.

Be verbose, provide rich visual details about colors, lighting, textures, composition, atmosphere.

Transform the prompt strictly following the context if provided.

NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER, STRICTLY FOLLOW THE INSTRUCTION."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "random_seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "system_prompt": ("STRING", {"multiline": True, "default": cls.DEFAULT_SYSTEM_PROMPT}),
                "model": (model_choices(cls.ROLE),),
            },
            "optional": {
                "context": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def run(self, random_seed, system_prompt, model, context=""):
        # random_seed wird ignoriert - dient nur zum Cache-Breaking

        if context and context.strip():
            user_prompt = f"Context to incorporate: {context.strip()}\n\nGenerate an image prompt based on this context."
        else:
            user_prompt = "Generate a creative image prompt."

        # Through the DevServer (_devserver.py); a failure is raised with the
        # DevServer's answer, and no other model answers in this node's place.
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        output_text, _ = chat("Clean Prompt Randomizer", messages, model, temperature=0.9)

        return (output_text.strip(),)
