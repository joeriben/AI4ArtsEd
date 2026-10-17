from ._devserver import model_choices, chat
import random

class ai4artsed_photo_prompt_randomizer:
    # The job this node does on the platform; its model and fallback are
    # the settings' (platform/CHAT_HELPER_MODEL in the dropdown).
    ROLE = "CHAT_HELPER_MODEL"


    FILM_TYPES = {
        "random": None,  # Will be randomly selected at runtime
        "Kodachrome": "a Kodachrome film slide",
        "Ektachrome": "an Ektachrome film slide",
        "Portra 400": "a Kodak Portra 400 color negative",
        "Portra 800": "a Kodak Portra 800 color negative",
        "Ektar 100": "a Kodak Ektar 100 color negative",
        "Fuji Pro 400H": "a Fujifilm Pro 400H color negative",
        "Fuji Superia": "a Fujifilm Superia color negative",
        "CineStill 800T": "a CineStill 800T tungsten-balanced color negative",
        "Ilford HP5": "an Ilford HP5 Plus black and white negative",
        "Ilford Delta 400": "an Ilford Delta 400 black and white negative",
        "Ilford FP4": "an Ilford FP4 Plus black and white negative",
        "Ilford Pan F": "an Ilford Pan F Plus 50 black and white negative",
        "Ilford XP2": "an Ilford XP2 Super chromogenic black and white negative",
        "Tri-X 400": "a Kodak Tri-X 400 black and white negative",
    }

    DEFAULT_SYSTEM_PROMPT = """You are an inventive creative. Your task is to invent a REALISTIC photographic image prompt.

Think globally. Avoid cultural clichés. Avoid "retro" style descriptions.
Describe contemporary everyday motives: scenes, objects, animals, nature, tech, culture, people, homes, family, work, holiday, urban, rural, trivia, details.

Choose either unlikely, untypical or typical photographical sujets for realistic photographic images. Be verbose, provide intricate details.

Always begin your output with: "{film_description} of".
Transform the prompt strictly following the context if provided.

NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER, STRICTLY FOLLOW THE INSTRUCTION."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "random_seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "film_type": (list(cls.FILM_TYPES.keys()),),
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

    # Force re-execution every time
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def get_system_prompt(self, film_type, system_prompt_template):
        """Build system prompt with selected film type"""
        if film_type == "random":
            # Select random film type (excluding "random" itself)
            actual_films = [k for k in self.FILM_TYPES.keys() if k != "random"]
            film_type = random.choice(actual_films)

        film_description = self.FILM_TYPES[film_type]
        return system_prompt_template.format(film_description=film_description), film_type

    def run(self, random_seed, film_type, system_prompt, model, context=""):
        # random_seed wird ignoriert - dient nur zum Cache-Breaking

        # Build system prompt with film type
        final_system_prompt, actual_film = self.get_system_prompt(film_type, system_prompt)

        # Prompt-Erstellung
        if context and context.strip():
            user_prompt = f"Context to incorporate: {context.strip()}\n\nGenerate a photographic image prompt based on this context."
        else:
            user_prompt = "Generate a creative photographic image prompt."

        # Through the DevServer (_devserver.py); a failure is raised with the
        # DevServer's answer, and no other model answers in this node's place.
        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        output_text, _ = chat("Photo Prompt Randomizer", messages, model, temperature=0.9)

        return (output_text.strip(),)
