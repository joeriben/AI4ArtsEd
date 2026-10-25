import re
from ._devserver import model_choices, chat
import base64
import io
from PIL import Image

class ai4artsed_image_analysis:
    # The job this node does on the platform; its model and fallback are
    # the settings' (platform/IMAGE_ANALYSIS_MODEL in the dropdown).
    ROLE = "IMAGE_ANALYSIS_MODEL"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True}),
                "model": (model_choices(cls.ROLE),),
            },
            "optional": {
                "system_prompt": ("STRING", {"multiline": True}),
                "debug": (["enable", "disable"], {"default": "disable"}),
            }
        }

    RETURN_TYPES = ("STRING", "FLOAT", "INT", "BOOLEAN")
    RETURN_NAMES = ("output_str", "output_float", "output_int", "output_binary")
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"

    def run(self, image, prompt, model, system_prompt=None, debug="disable"):
        # Convert image tensor to JPEG base64
        array = image[0].detach().cpu().numpy()
        pil_img = Image.fromarray((array * 255).astype("uint8"))
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        full_prompt = prompt.strip()

        # Through the DevServer (_devserver.py), which hands the image to a
        # model that can see it and applies the settings' fallback. A failure
        # is raised with the DevServer's answer; no error text goes downstream
        # as the analysis.
        messages = [
            {"role": "system", "content": system_prompt or "You are a multimodal assistant."},
            {"role": "user", "content": full_prompt}
        ]
        output, _ = chat("Image Analysis", messages, model, temperature=0.7, image_b64=img_b64)

        if debug == "enable":
            print("--- AI4ArtsEd Image Analysis Debug ---")
            print("Model:", model)
            print("Prompt:", full_prompt)
            print("Output:", output)

        # Parse return values
        text = output.strip()
        num_match = re.search(r"[-+]?\d*\.\d+", text)
        fval = float(num_match.group()) if num_match else 0.0
        int_match = re.search(r"[-+]?\d+", text)
        ival = int(int_match.group()) if int_match else 0
        bval = any(x in text.lower() for x in ["true", "yes"]) or (num_match and float(num_match.group()) != 0)

        return text, fval, ival, bval
