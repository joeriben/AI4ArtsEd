"""The readings of the Latent Text Lab, as ComfyUI nodes.

The DevServer queues a prompt of one of these nodes for every run of the
coreference contrast, the BBQ probe and the Representation Engineering
surface (my_app/services/text_probes.py); the numbers come back through
/history as the node's ui output, one JSON text. In a workflow built in
ComfyUI the same JSON stands on the node's output.

The model is a folder under models/llm/, listed by name; what reads it is in
_text_probes.py, what holds it on the card in _local_llm.py.
"""
import json

from ._local_llm import installed_dirs
from ._text_probes import option_scores, rep_engineering


def _json_list(text: str, what: str) -> list:
    try:
        parsed = json.loads(text)
    except ValueError as e:
        raise ValueError(f"{what} has to be a JSON list: {e}")
    if not isinstance(parsed, list):
        raise ValueError(f"{what} has to be a JSON list")
    return parsed


class ai4artsed_llm_option_scores:
    """After each prompt, the log-probability of each option as the next
    token. The DevServer builds the prompts and reads the numbers."""

    @classmethod
    def INPUT_TYPES(cls):
        dirs = installed_dirs()
        return {
            "required": {
                "llm_name": (dirs or ["(no model under models/llm)"],),
                # A JSON list of prompts, each ending where the answer begins.
                "prompts": ("STRING", {"multiline": True, "default": "[]"}),
                # A JSON list of the answer options as the model would write
                # them next, with their leading space.
                "options": ("STRING", {"multiline": False, "default": "[\" A\", \" B\"]"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("scores_json",)
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Run every time it is queued. ComfyUI answers a prompt whose inputs
        # it has seen before from its cache, and a run of the same items on
        # the same model, the way a course repeats the vetted sixty, has to
        # reach the card to be a run.
        return float("nan")

    def run(self, llm_name, prompts, options):
        prompt_list = _json_list(prompts, "prompts")
        option_list = _json_list(options, "options")
        if not all(isinstance(p, str) for p in prompt_list):
            raise ValueError("every prompt has to be a string")
        if not all(isinstance(o, str) for o in option_list):
            raise ValueError("every option has to be a string")
        result = option_scores(llm_name, prompt_list, option_list)
        text = json.dumps(result)
        return {"ui": {"result": [text]}, "result": (text,)}


class ai4artsed_llm_rep_engineering:
    """Representation Engineering (Zou et al. 2023): the axis contrast pairs
    share in one layer, and generations with that axis added."""

    @classmethod
    def INPUT_TYPES(cls):
        dirs = installed_dirs()
        return {
            "required": {
                "llm_name": (dirs or ["(no model under models/llm)"],),
                # A JSON list of {"positive": ..., "negative": ...}.
                "contrast_pairs": ("STRING", {"multiline": True, "default": "[]"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                # The text that is projected onto the axis and continued
                # under it; empty reads the axis alone.
                "test_text": ("STRING", {"multiline": True, "default": ""}),
                # A JSON list of strengths, one generation each; 0 is the
                # untouched run.
                "alphas": ("STRING", {"multiline": False, "default": "[0]"}),
                # Which hidden state is read and steered. Empty is the middle
                # of the stack, where Zou et al. read; -1 the last; any other
                # number indexes the hidden states directly.
                "target_layer": ("STRING", {"multiline": False, "default": ""}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                # 0 takes the surface's own hard limit (see _text_probes).
                "max_new_tokens": ("INT", {"default": 0, "min": 0, "max": 1048576}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("reading_json",)
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # See ai4artsed_llm_option_scores: a queued reading reaches the card.
        return float("nan")

    def run(self, llm_name, contrast_pairs, seed, test_text="", alphas="[0]",
            target_layer="", temperature=0.7, max_new_tokens=0):
        pairs = _json_list(contrast_pairs, "contrast_pairs")
        strengths = _json_list(alphas, "alphas") if alphas.strip() else []
        if not all(isinstance(a, (int, float)) for a in strengths):
            raise ValueError("every strength in alphas has to be a number")
        layer = target_layer.strip()
        try:
            layer_idx = int(layer) if layer else None
        except ValueError:
            raise ValueError(f"target_layer has to be a whole number or empty, got {target_layer!r}")
        result = rep_engineering(
            llm_name, pairs,
            target_layer=layer_idx,
            test_text=test_text if test_text.strip() else None,
            alphas=[float(a) for a in strengths],
            max_new_tokens=int(max_new_tokens) if max_new_tokens > 0 else None,
            temperature=float(temperature),
            seed=int(seed),
        )
        text = json.dumps(result)
        return {"ui": {"result": [text]}, "result": (text,)}
