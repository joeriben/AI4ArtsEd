"""Audio for a picture with Stable Audio 3 under ImageBind guidance, as a
ComfyUI node.

The DevServer's cross-aesthetic routes queue one prompt of this node per
image-guided generation; the picture comes as base64 text, or, in a
workflow, as an IMAGE. Everything that computes is _stable_audio.
generate_guided, with the image side in _imagebind.
"""
from . import _imagebind, _media_files, _stable_audio


class ai4artsed_image_guided_audio:
    @classmethod
    def INPUT_TYPES(cls):
        dirs = _stable_audio.installed_dirs()
        ib = _imagebind.installed_dirs()
        return {
            "required": {
                "model_name": (dirs or ["(no checkpoint under models/stable_audio)"],),
                "imagebind_name": (ib or ["(no checkpoint under models/imagebind)"],),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "lambda_guidance": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "warmup_steps": ("INT", {"default": 8, "min": 0, "max": 250}),
                "total_steps": ("INT", {"default": _stable_audio.SA3_DEFAULT_STEPS, "min": 1, "max": 250}),
                "duration_seconds": ("FLOAT", {"default": 10.0, "min": 0.1,
                                               "max": _stable_audio.MAX_DURATION_S, "step": 0.1}),
                "cfg_scale": ("FLOAT", {"default": _stable_audio.SA3_DEFAULT_CFG_SCALE,
                                        "min": 0.0, "max": 20.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                "image": ("IMAGE",),
                "image_base64": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    RETURN_TYPES = ("AUDIO", "FLOAT")
    RETURN_NAMES = ("audio", "cosine_similarity")
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    def run(self, model_name, imagebind_name, prompt, lambda_guidance, warmup_steps, total_steps,
            duration_seconds, cfg_scale, seed, image=None, image_base64=""):
        pil = _media_files.pil_image(image_base64, image)
        if pil is None:
            raise ValueError("a picture is required: image_base64 or an IMAGE input")
        out = _stable_audio.generate_guided(
            model_name, imagebind_name, pil, prompt=prompt, lambda_guidance=float(lambda_guidance),
            warmup_steps=int(warmup_steps), total_steps=int(total_steps),
            duration_seconds=float(duration_seconds), cfg_scale=float(cfg_scale), seed=int(seed))
        announced = _media_files.announce(_media_files.wav_bytes(out["audio"], out["sample_rate"]), ".wav")
        return {
            "ui": {
                "audio": [announced],
                "cosine_similarity": [out["cosine_similarity"]],
                "guidance_steps_skipped": [out["guidance_steps_skipped"]],
                "generation_time_ms": [out["generation_time_ms"]],
                "seed": [out["seed"]],
                "sample_rate": [out["sample_rate"]],
                "duration_seconds": [out["duration_seconds"]],
            },
            "result": ({"waveform": out["audio"].unsqueeze(0), "sample_rate": out["sample_rate"]},
                       out["cosine_similarity"]),
        }
