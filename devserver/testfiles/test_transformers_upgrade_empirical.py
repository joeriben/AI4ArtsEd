#!/usr/bin/env python3
"""
Empirical stage-2 checks for an isolated Transformers upgrade venv.

This script exercises real model/component load paths using models that are
already cached locally. It avoids network downloads by using local_files_only.
"""

from __future__ import annotations

import gc
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run_text_backend_probe() -> list[str]:
    failures: list[str] = []
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_id = "google/gemma-2-2b-it"
    print(f"[text] loading {model_id}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        local_files_only=True,
        low_cpu_mem_usage=True,
        dtype=torch.bfloat16,
    )
    model = model.to("cuda")
    model.eval()

    inputs = tokenizer("The forest is dark and", return_tensors="pt").to("cuda")
    with torch.inference_mode():
        outputs = model.generate(**inputs, max_new_tokens=12, do_sample=False)
    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"[text] sample={text!r}")
    if not text:
        failures.append("text-backend: empty generation output")

    del model
    gc.collect()
    torch.cuda.empty_cache()
    return failures


def run_flux2_probe() -> list[str]:
    failures: list[str] = []
    print("[flux2] loading tokenizer/text components")

    from transformers import AutoModelForImageTextToText, PixtralProcessor

    model_id = "black-forest-labs/FLUX.2-dev"

    processor = PixtralProcessor.from_pretrained(
        model_id,
        subfolder="tokenizer",
        local_files_only=True,
    )
    _ = processor

    text_encoder = AutoModelForImageTextToText.from_pretrained(
        model_id,
        subfolder="text_encoder",
        local_files_only=True,
        low_cpu_mem_usage=True,
    )
    del text_encoder
    gc.collect()

    print("[flux2] processor + text_encoder loaded")
    return failures


def run_wan_probe() -> list[str]:
    failures: list[str] = []
    print("[wan] loading tokenizer/text encoder")

    from transformers import AutoTokenizer, UMT5EncoderModel

    model_id = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        subfolder="tokenizer",
        local_files_only=True,
    )
    _ = tokenizer

    text_encoder = UMT5EncoderModel.from_pretrained(
        model_id,
        subfolder="text_encoder",
        local_files_only=True,
        low_cpu_mem_usage=True,
    )
    del text_encoder
    gc.collect()

    print("[wan] tokenizer + text_encoder loaded")
    return failures


def run_t5_probe() -> list[str]:
    failures: list[str] = []
    print("[t5] loading base tokenizer/encoder")

    from transformers import AutoTokenizer, T5EncoderModel

    model_id = "google-t5/t5-base"
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    model = T5EncoderModel.from_pretrained(model_id, local_files_only=True)

    inputs = tokenizer("safety check", return_tensors="pt")
    outputs = model(**inputs)
    if outputs.last_hidden_state is None:
        failures.append("t5: no hidden state output")

    del model
    gc.collect()

    print("[t5] encoder forward pass ok")
    return failures


def main() -> int:
    failures: list[str] = []

    import torch
    import transformers
    import diffusers

    print(f"torch={torch.__version__}")
    print(f"diffusers={diffusers.__version__}")
    print(f"transformers={transformers.__version__}")

    try:
        failures.extend(run_text_backend_probe())
    except Exception as exc:
        failures.append(f"text-backend: {exc}")

    try:
        failures.extend(run_flux2_probe())
    except Exception as exc:
        failures.append(f"flux2: {exc}")

    try:
        failures.extend(run_wan_probe())
    except Exception as exc:
        failures.append(f"wan: {exc}")

    try:
        failures.extend(run_t5_probe())
    except Exception as exc:
        failures.append(f"t5: {exc}")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nOK: empirical load checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
