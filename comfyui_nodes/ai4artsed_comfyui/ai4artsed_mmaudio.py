"""Audio for a picture, or for a text, with MMAudio, as a ComfyUI node.

The DevServer's cross-aesthetic routes queue one prompt of this node per
generation; the picture comes as base64 text, or, in a workflow, as an
IMAGE; without a picture the text alone conditions the sound. Everything
that holds the model is in _mmaudio.py.
"""
from . import _media_files, _mmaudio


class ai4artsed_mmaudio:
    @classmethod
    def INPUT_TYPES(cls):
        dirs = _mmaudio.installed_dirs()
        return {
            "required": {
                "model_name": (dirs or ["(no variant under models/mmaudio)"],),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "duration_seconds": ("FLOAT", {"default": _mmaudio.MAX_DURATION_S, "min": 0.5,
                                               "max": _mmaudio.MAX_DURATION_S, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                "image": ("IMAGE",),
                "image_base64": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "cfg_strength": ("FLOAT", {"default": _mmaudio.DEFAULT_CFG_STRENGTH,
                                           "min": 0.0, "max": 20.0, "step": 0.1}),
                "num_steps": ("INT", {"default": _mmaudio.DEFAULT_STEPS, "min": 1, "max": 200}),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    def run(self, model_name, prompt, duration_seconds, seed, image=None, image_base64="",
            negative_prompt="", cfg_strength=_mmaudio.DEFAULT_CFG_STRENGTH, num_steps=_mmaudio.DEFAULT_STEPS):
        pil = _media_files.pil_image(image_base64, image)
        out = _mmaudio.generate(model_name, image=pil, prompt=prompt, negative_prompt=negative_prompt,
                                duration_seconds=float(duration_seconds), cfg_strength=float(cfg_strength),
                                num_steps=int(num_steps), seed=int(seed))
        announced = _media_files.announce(_media_files.wav_bytes(out["audio"], out["sample_rate"]), ".wav")
        return {
            "ui": {
                "audio": [announced],
                "seed": [out["seed"]],
                "generation_time_ms": [out["generation_time_ms"]],
                "sample_rate": [out["sample_rate"]],
                "duration_seconds": [out["duration_seconds"]],
            },
            "result": ({"waveform": out["audio"].unsqueeze(0), "sample_rate": out["sample_rate"]},),
        }
