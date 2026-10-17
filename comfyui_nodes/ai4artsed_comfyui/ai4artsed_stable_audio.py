"""Text to audio with Stable Audio 3, as a ComfyUI node.

The DevServer's Stable Audio client (my_app/services/stable_audio_client.py)
queues one prompt of this node per generation; the sound comes back as a
file the node announces in its ui output (fetched from /view), the numbers
beside it. In a workflow built in ComfyUI the node's AUDIO output feeds
any audio node. Everything that holds the model is in _stable_audio.py.
"""
from . import _media_files, _stable_audio


class ai4artsed_stable_audio:
    @classmethod
    def INPUT_TYPES(cls):
        dirs = _stable_audio.installed_dirs()
        return {
            "required": {
                # Listed from disk at every validation, so a checkpoint
                # installed while ComfyUI runs is offered without a restart.
                "model_name": (dirs or ["(no checkpoint under models/stable_audio)"],),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "duration_seconds": ("FLOAT", {"default": 10.0, "min": 0.1,
                                               "max": _stable_audio.MAX_DURATION_S, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "steps": ("INT", {"default": _stable_audio.SA3_DEFAULT_STEPS, "min": 1, "max": 250}),
                "cfg_scale": ("FLOAT", {"default": _stable_audio.SA3_DEFAULT_CFG_SCALE,
                                        "min": 0.0, "max": 20.0, "step": 0.1}),
                "output_format": (["wav", "mp3"], {"default": "wav"}),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    def run(self, model_name, prompt, duration_seconds, seed, negative_prompt="",
            steps=_stable_audio.SA3_DEFAULT_STEPS, cfg_scale=_stable_audio.SA3_DEFAULT_CFG_SCALE,
            output_format="wav"):
        audio, sample_rate, generated = _stable_audio.generate(
            model_name, prompt, duration_seconds=float(duration_seconds),
            negative_prompt=negative_prompt, steps=int(steps), cfg_scale=float(cfg_scale), seed=int(seed))
        announced = _media_files.announce(_media_files.encoded(audio, sample_rate, output_format),
                                          f".{output_format}")
        return {
            "ui": {
                "audio": [announced],
                "seed": [int(seed)],
                "sample_rate": [sample_rate],
                "duration_seconds": [generated],
                "requested_duration_seconds": [float(duration_seconds)],
            },
            "result": ({"waveform": audio.unsqueeze(0), "sample_rate": sample_rate},),
        }
