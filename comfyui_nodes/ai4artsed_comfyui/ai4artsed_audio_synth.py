"""The audio synth of the cross-aesthetic surface, as a ComfyUI node.

The DevServer's cross-aesthetic routes queue one prompt of this node per
turn of the synth (mode "synth": two prompts, alpha, magnitude, noise, the
axes; mode "multi_axis": a base prompt and the axes). The axes come in as
JSON, [{"name", "t", "pole_a", "pole_b"}], the poles already framed the way
the DevServer's table frames them, with the framed neutral prompt and the
name of the PCA components file beside them. Everything that computes is
in _audio_synth.py.
"""
import json

from . import _audio_synth, _media_files, _stable_audio


class ai4artsed_audio_synth:
    @classmethod
    def INPUT_TYPES(cls):
        dirs = _stable_audio.installed_dirs()
        return {
            "required": {
                "model_name": (dirs or ["(no checkpoint under models/stable_audio)"],),
                "mode": (["synth", "multi_axis"], {"default": "synth"}),
                "prompt_a": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                "prompt_b": ("STRING", {"multiline": True, "default": ""}),
                "alpha": ("FLOAT", {"default": 0.5, "min": -10.0, "max": 10.0, "step": 0.01}),
                "magnitude": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "noise_sigma": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                # {"<dim>": offset}, JSON
                "dimension_offsets": ("STRING", {"multiline": True, "default": ""}),
                # [{"name", "t", "pole_a", "pole_b"}], JSON; a PCA axis is
                # named "pcN" and carries no poles.
                "axes": ("STRING", {"multiline": True, "default": ""}),
                "neutral_prompt": ("STRING", {"default": ""}),
                "pca_axes_file": ("STRING", {"default": ""}),
                # mode multi_axis: the starting point; blank = the neutral prompt
                "base_prompt": ("STRING", {"multiline": True, "default": ""}),
                "duration_seconds": ("FLOAT", {"default": 1.0, "min": 0.1,
                                               "max": _audio_synth.MAX_SYNTH_DURATION_S, "step": 0.1}),
                "steps": ("INT", {"default": _stable_audio.SA3_DEFAULT_STEPS, "min": 1, "max": 250}),
                "cfg_scale": ("FLOAT", {"default": _stable_audio.SA3_DEFAULT_CFG_SCALE,
                                        "min": 0.0, "max": 20.0, "step": 0.1}),
            },
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "embedding_stats")
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    def run(self, model_name, mode, prompt_a, seed, prompt_b="", alpha=0.5, magnitude=1.0,
            noise_sigma=0.0, dimension_offsets="", axes="", neutral_prompt="", pca_axes_file="",
            base_prompt="", duration_seconds=1.0, steps=_stable_audio.SA3_DEFAULT_STEPS,
            cfg_scale=_stable_audio.SA3_DEFAULT_CFG_SCALE):
        offsets = _media_files.json_input(dimension_offsets, "dimension_offsets", {})
        axis_list = _media_files.json_input(axes, "axes", [])
        if not isinstance(offsets, dict) or not isinstance(axis_list, list):
            raise ValueError("dimension_offsets has to be a JSON object and axes a JSON list")
        common = dict(dimension_offsets=offsets, axes=axis_list, neutral_prompt=neutral_prompt,
                      pca_file=pca_axes_file, duration_seconds=float(duration_seconds),
                      steps=int(steps), cfg_scale=float(cfg_scale), seed=int(seed))
        if mode == "multi_axis":
            # No axis is the base sound as it is (the neutral embedding, or
            # the base prompt), the way the station answered it.
            out = _audio_synth.multi_axis(model_name, base_prompt=base_prompt, **common)
        else:
            if not prompt_a.strip():
                raise ValueError("prompt_a is required")
            out = _audio_synth.synth(model_name, prompt_a, prompt_b=prompt_b, alpha=float(alpha),
                                     magnitude=float(magnitude), noise_sigma=float(noise_sigma), **common)
        announced = _media_files.announce(_media_files.wav_bytes(out["audio"], out["sample_rate"]), ".wav")
        stats = json.dumps(out["embedding_stats"])
        return {
            "ui": {
                "audio": [announced],
                "embedding_stats": [stats],
                "axis_contributions": [json.dumps(out["axis_contributions"])],
                "generation_time_ms": [out["generation_time_ms"]],
                "seed": [out["seed"]],
                "sample_rate": [out["sample_rate"]],
                "duration_seconds": [out["duration_seconds"]],
            },
            "result": ({"waveform": out["audio"].unsqueeze(0), "sample_rate": out["sample_rate"]}, stats),
        }
