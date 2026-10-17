import re
from ._devserver import model_choices, chat

class ai4artsed_prompt_interception:
    # The job this node does on the platform; its model and fallback are
    # the settings' (platform/STAGE2_INTERCEPTION_MODEL in the dropdown).
    ROLE = "STAGE2_INTERCEPTION_MODEL"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_prompt": ("STRING", {"multiline": True}),
                "input_context": ("STRING", {"default": "", "multiline": True}),
                "style_prompt": ("STRING", {"default": "", "multiline": True}),
                "model": (model_choices(cls.ROLE),),
                "debug": (["enable", "disable"], {"default": "disable"}),
            }
        }

    RETURN_TYPES = ("STRING", "FLOAT", "INT", "BOOLEAN")
    RETURN_NAMES = ("output_str", "output_float", "output_int", "output_binary")
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"

    def run(self, input_prompt, input_context, style_prompt, model, debug):
        full_prompt = (
            f"Task:\n{style_prompt.strip()}\n\n"
            f"Context:\n{input_context.strip()}\nPrompt:\n{input_prompt.strip()}"
        )

        # Through the DevServer, which resolves the model, holds the keys and
        # applies the fallback the settings page regulates (_devserver.py). A
        # failure is raised with the DevServer's answer; no other model answers
        # in this node's place, and no error text goes downstream as the prompt.
        messages = [
            {"role": "system", "content": "You are a fresh assistant instance. Forget all previous conversation history."},
            {"role": "user", "content": full_prompt}
        ]
        output_text, model_used = chat("Prompt Interception", messages, model, temperature=0.7)

        if debug == "enable":
            print("\n" + "="*60)
            print(">>> AI4ARTSED PROMPT INTERCEPTION NODE <<<")
            print("="*60)
            print(f"Selected: {model}")
            print(f"Model used: {model_used}")
            print("-" * 40)
            print("Prompt sent:")
            print(full_prompt)
            print("-" * 40)
            print("Response received:")
            print(output_text)
            print("="*60)

        # Formatierung: alle vier Rückgabeformate parallel mit Failsafes
        output_str = output_text.strip()

        # Musterdefinitionen
        german_pattern = r"[-+]?\d{1,3}(?:\.\d{3})*,\d+"
        english_pattern = r"[-+]?\d*\.\d+"
        int_pattern = r"[-+]?\d+"

        # Failsafe Float: deutsche Formate zuerst
        m = re.search(german_pattern, output_str)
        if m:
            num = m.group()
            normalized = num.replace(".", "").replace(",", ".")
            try:
                output_float = float(normalized)
            except:
                output_float = 0.0
        else:
            m = re.search(english_pattern, output_str)
            if m:
                try:
                    output_float = float(m.group())
                except:
                    output_float = 0.0
            else:
                m = re.search(int_pattern, output_str)
                if m:
                    try:
                        output_float = float(m.group())
                    except:
                        output_float = 0.0
                else:
                    output_float = 0.0

        # Failsafe Int
        m_int = re.search(int_pattern, output_str)
        if m_int:
            try:
                output_int = int(round(float(m_int.group())))
            except:
                output_int = 0
        else:
            output_int = 0

        # Failsafe Binary
        lower = output_str.lower()
        num_match = re.search(english_pattern, output_str) or re.search(int_pattern, output_str)
        if (
            "true" in lower
            or re.search(r"\b1\b", lower)
            or (num_match and float(num_match.group()) != 0)
        ):
            output_binary = True
        else:
            output_binary = False

        return output_str, output_float, output_int, output_binary
