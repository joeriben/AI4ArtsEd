"""A song from lyrics and tags with HeartMuLa, as a ComfyUI node.

The DevServer's HeartMuLa client (my_app/services/heartmula_client.py)
queues one prompt of this node per song, and one with preload_only for the
settings page's load button, which puts the weights on the card and
generates nothing. Everything that holds the model is in _heartmula.py.
"""
import torch

from . import _heartmula, _media_files


class ai4artsed_heartmula:
    @classmethod
    def INPUT_TYPES(cls):
        dirs = _heartmula.installed_dirs()
        return {
            "required": {
                "model_name": (dirs or ["(no checkpoint tree under models/heartmula)"],),
                "lyrics": ("STRING", {"multiline": True, "default": ""}),
                "tags": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                # The HeartMuLa-oss-<version> folder of the checkpoint tree.
                "version": ("STRING", {"default": _heartmula.DEFAULT_VERSION}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "topk": ("INT", {"default": 70, "min": 1, "max": 1000}),
                "cfg_scale": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 20.0, "step": 0.1}),
                "max_audio_length_ms": ("INT", {"default": 240_000, "min": 1000, "max": 600_000, "step": 1000}),
                "output_format": (["mp3", "wav"], {"default": "mp3"}),
                "preload_only": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, preload_only=False, **kwargs):
        # A preload is asked for so that the weights are on the card now: it
        # runs every time it is queued. ComfyUI would otherwise answer the
        # second preload of the same model from its cache, in no time and
        # with nothing put on the card. A song with the same inputs is
        # answered from the cache like every other generation.
        return float("nan") if preload_only else ""

    def run(self, model_name, lyrics, tags, seed, version=_heartmula.DEFAULT_VERSION, temperature=1.0,
            topk=70, cfg_scale=3.0, max_audio_length_ms=240_000, output_format="mp3", preload_only=False):
        if preload_only:
            loaded = _heartmula.preload(model_name, version or _heartmula.DEFAULT_VERSION)
            return {"ui": {"loaded": [loaded["loaded"]], "weight_bytes": [loaded["weight_bytes"]]},
                    "result": ({"waveform": torch.zeros(1, 2, 1), "sample_rate": _heartmula.SAMPLE_RATE},)}
        out = _heartmula.generate(
            model_name, lyrics, tags, version=version or _heartmula.DEFAULT_VERSION,
            temperature=float(temperature), topk=int(topk), cfg_scale=float(cfg_scale),
            max_audio_length_ms=int(max_audio_length_ms), seed=int(seed))
        announced = _media_files.announce(
            _media_files.encoded(out["audio"], out["sample_rate"], output_format), f".{output_format}")
        return {
            "ui": {
                "audio": [announced],
                "seed": [out["seed"]],
                "duration_seconds": [out["duration_seconds"]],
                "sample_rate": [out["sample_rate"]],
                "generation_time_ms": [out["generation_time_ms"]],
            },
            "result": ({"waveform": out["audio"].unsqueeze(0), "sample_rate": out["sample_rate"]},),
        }
