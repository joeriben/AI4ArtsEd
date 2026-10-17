# filename: ai4artsed_text_remix.py

import random

class ai4artsed_text_remix:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "mode": (
                    "STRING", {
                        "default": "random",
                        "choices": ["random", "all"] + [str(i) for i in range(1, 13)]
                    }
                ),
            },
            "optional": {
                f"text_{i}": ("STRING", {"multiline": True}) for i in range(1, 13)
            }
        }
        return inputs

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "remix"
    CATEGORY = "AI4ArtsEd"

    def remix(self, mode, **kwargs):
        texts = [kwargs.get(f"text_{i}") for i in range(1, 13)]
        non_empty_texts = [t for t in texts if t]

        if not non_empty_texts:
            return ("",)

        if mode == "random":
            return (random.choice(non_empty_texts),)
        elif mode == "all":
            return ("\n".join(non_empty_texts),)
        elif mode.isdigit() and 1 <= int(mode) <= 12:
            selected = texts[int(mode) - 1]
            return (selected if selected else "",)

        return ("",)
