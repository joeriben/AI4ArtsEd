#!/usr/bin/env python3
"""
Compare image-safety strategies on a folder of scary test images.

Strategies:
- qwen_direct: direct SAFE/UNSAFE with current local VLM
- qwen_to_cloud: current production-style two-model path
- qwen_to_gemma4: current local describer + Gemma 4 verdict
- gemma4_direct: Gemma 4 sees image and judges directly
- gemma4_to_cloud: Gemma 4 describes + cloud verdict
- gemma4_to_gemma4: Gemma 4 describes + Gemma 4 verdict

Outputs a JSON file with per-image, per-strategy results.

Example:
  cd devserver && ../venv/bin/python testfiles/test_gemma4_safety_matrix.py \
    --image-dir /home/joerissen/Pictures/scary_pictures_for_safety_testing
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoModelForMultimodalLM, AutoProcessor


DEVSERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVSERVER_DIR))

import config  # noqa: E402
from my_app.services.llm_backend import get_llm_backend  # noqa: E402
from my_app.utils.vlm_safety import (  # noqa: E402
    VLM_MAX_SIZE,
    VLM_MIN_SIZE,
    VLM_PROMPTS,
    VLM_DESCRIBE_PROMPTS,
    VLM_VERDICT_PROMPTS,
    _call_verdict_model,
    _extract_verdict,
)


DEFAULT_IMAGE_DIR = Path("/home/joerissen/Pictures/scary_pictures_for_safety_testing")
DEFAULT_GEMMA4_MODEL = "google/gemma-4-E4B-it"


def _prepare_image_bytes(image_path: Path) -> tuple[str, tuple[int, int], tuple[int, int]]:
    img = Image.open(image_path)
    original_size = img.size

    if min(img.size) < VLM_MIN_SIZE:
        scale = VLM_MIN_SIZE / min(img.size)
        new_size = (max(VLM_MIN_SIZE, int(img.width * scale)), max(VLM_MIN_SIZE, int(img.height * scale)))
        img = img.resize(new_size, Image.LANCZOS)
    if max(img.size) > VLM_MAX_SIZE:
        img.thumbnail((VLM_MAX_SIZE, VLM_MAX_SIZE), Image.LANCZOS)
    if img.mode not in ("RGB", "L"):
        if img.mode == "RGBA" or (img.mode == "P" and "transparency" in img.info):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            rgba = img.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), original_size, img.size


def _image_for_gemma(image_path: Path) -> Image.Image:
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


@dataclass
class StrategyResult:
    strategy: str
    safety_level: str
    verdict: str | None
    raw_response: str | None
    description: str | None
    elapsed_s: float
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "safety_level": self.safety_level,
            "verdict": self.verdict,
            "raw_response": self.raw_response,
            "description": self.description,
            "elapsed_s": round(self.elapsed_s, 3),
            "error": self.error,
        }


class Gemma4Runner:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForMultimodalLM.from_pretrained(
            model_id,
            torch_dtype="auto",
            device_map="auto",
        )

    def generate(self, prompt: str, image_path: Path | None = None, max_new_tokens: int = 256) -> str:
        if image_path is None:
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        else:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": _image_for_gemma(image_path)},
                    {"type": "text", "text": prompt},
                ],
            }]

        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
        ).to(self.model.device)

        input_len = inputs["input_ids"].shape[-1]
        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        response = self.processor.decode(outputs[0][input_len:], skip_special_tokens=False)
        parsed = self.processor.parse_response(response)
        if isinstance(parsed, dict):
            return (parsed.get("text") or parsed.get("content") or response).strip()
        return str(parsed).strip()


def run_qwen_direct(image_path: Path, safety_level: str) -> StrategyResult:
    start = time.time()
    image_b64, original_size, resized_size = _prepare_image_bytes(image_path)
    result = get_llm_backend().chat(
        model=config.VLM_SAFETY_MODEL,
        messages=[{"role": "user", "content": VLM_PROMPTS[safety_level]}],
        images=[image_b64],
        temperature=0.0,
        max_new_tokens=800,
        enable_thinking=False,
    )
    elapsed = time.time() - start

    if result is None:
        return StrategyResult("qwen_direct", safety_level, None, None, None, elapsed, "LLM returned None")

    raw = (result.get("content") or result.get("thinking") or "").strip()
    verdict = _extract_verdict(raw)
    desc = f"image {original_size}->{resized_size}"
    return StrategyResult("qwen_direct", safety_level, verdict, raw, desc, elapsed)


def run_qwen_to_cloud(image_path: Path, safety_level: str) -> StrategyResult:
    start = time.time()
    image_b64, _, _ = _prepare_image_bytes(image_path)
    describe_result = get_llm_backend().chat(
        model=config.VLM_SAFETY_MODEL,
        messages=[{"role": "user", "content": VLM_DESCRIBE_PROMPTS[safety_level]}],
        images=[image_b64],
        temperature=0.0,
        max_new_tokens=1500,
        enable_thinking=False,
    )
    if describe_result is None:
        return StrategyResult("qwen_to_cloud", safety_level, None, None, None, time.time() - start, "Description returned None")

    description = (describe_result.get("content") or describe_result.get("thinking") or "").strip()
    if not description:
        return StrategyResult("qwen_to_cloud", safety_level, None, None, "", time.time() - start, "Empty description")

    verdict_prompt = VLM_VERDICT_PROMPTS[safety_level].format(description=description)
    raw = _call_verdict_model(verdict_prompt)
    elapsed = time.time() - start
    verdict = _extract_verdict(raw or "")
    return StrategyResult("qwen_to_cloud", safety_level, verdict, raw, description, elapsed, None if raw else "Verdict returned None")


def run_qwen_to_gemma4(image_path: Path, safety_level: str, gemma4: Gemma4Runner) -> StrategyResult:
    start = time.time()
    image_b64, _, _ = _prepare_image_bytes(image_path)
    describe_result = get_llm_backend().chat(
        model=config.VLM_SAFETY_MODEL,
        messages=[{"role": "user", "content": VLM_DESCRIBE_PROMPTS[safety_level]}],
        images=[image_b64],
        temperature=0.0,
        max_new_tokens=1500,
        enable_thinking=False,
    )
    if describe_result is None:
        return StrategyResult("qwen_to_gemma4", safety_level, None, None, None, time.time() - start, "Description returned None")

    description = (describe_result.get("content") or describe_result.get("thinking") or "").strip()
    if not description:
        return StrategyResult("qwen_to_gemma4", safety_level, None, None, "", time.time() - start, "Empty description")

    verdict_prompt = VLM_VERDICT_PROMPTS[safety_level].format(description=description)
    raw = gemma4.generate(verdict_prompt, image_path=None, max_new_tokens=128)
    elapsed = time.time() - start
    verdict = _extract_verdict(raw)
    return StrategyResult("qwen_to_gemma4", safety_level, verdict, raw, description, elapsed)


def run_gemma4_direct(image_path: Path, safety_level: str, gemma4: Gemma4Runner) -> StrategyResult:
    start = time.time()
    raw = gemma4.generate(VLM_PROMPTS[safety_level], image_path=image_path, max_new_tokens=128)
    elapsed = time.time() - start
    verdict = _extract_verdict(raw)
    return StrategyResult("gemma4_direct", safety_level, verdict, raw, None, elapsed)


def run_gemma4_to_cloud(image_path: Path, safety_level: str, gemma4: Gemma4Runner) -> StrategyResult:
    start = time.time()
    description = gemma4.generate(VLM_DESCRIBE_PROMPTS[safety_level], image_path=image_path, max_new_tokens=256)
    verdict_prompt = VLM_VERDICT_PROMPTS[safety_level].format(description=description)
    raw = _call_verdict_model(verdict_prompt)
    elapsed = time.time() - start
    verdict = _extract_verdict(raw or "")
    return StrategyResult("gemma4_to_cloud", safety_level, verdict, raw, description, elapsed, None if raw else "Verdict returned None")


def run_gemma4_to_gemma4(image_path: Path, safety_level: str, gemma4: Gemma4Runner) -> StrategyResult:
    start = time.time()
    description = gemma4.generate(VLM_DESCRIBE_PROMPTS[safety_level], image_path=image_path, max_new_tokens=256)
    verdict_prompt = VLM_VERDICT_PROMPTS[safety_level].format(description=description)
    raw = gemma4.generate(verdict_prompt, image_path=None, max_new_tokens=128)
    elapsed = time.time() - start
    verdict = _extract_verdict(raw)
    return StrategyResult("gemma4_to_gemma4", safety_level, verdict, raw, description, elapsed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Gemma 4 safety strategies on scary image folder.")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--gemma4-model", default=DEFAULT_GEMMA4_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="Optional image limit for quick tests")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEVSERVER_DIR / "tests" / "results" / "gemma4_safety_matrix.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_dir: Path = args.image_dir

    if not image_dir.exists():
        print(f"Image dir not found: {image_dir}")
        return 1

    image_paths = sorted([p for p in image_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])
    if args.limit > 0:
        image_paths = image_paths[:args.limit]

    if not image_paths:
        print(f"No images found in {image_dir}")
        return 1

    print(f"Loading {args.gemma4_model}...")
    gemma4 = Gemma4Runner(args.gemma4_model)

    results: list[dict[str, Any]] = []
    strategies = [
        run_qwen_direct,
        run_qwen_to_cloud,
        lambda p, lvl: run_qwen_to_gemma4(p, lvl, gemma4),
        lambda p, lvl: run_gemma4_direct(p, lvl, gemma4),
        lambda p, lvl: run_gemma4_to_cloud(p, lvl, gemma4),
        lambda p, lvl: run_gemma4_to_gemma4(p, lvl, gemma4),
    ]

    for image_path in image_paths:
        print(f"\n=== {image_path.name} ===")
        image_result: dict[str, Any] = {"image": image_path.name, "results": []}
        for safety_level in ("kids", "youth"):
            for strategy in strategies:
                try:
                    result = strategy(image_path, safety_level)
                except Exception as exc:
                    result = StrategyResult(
                        getattr(strategy, "__name__", "strategy"),
                        safety_level,
                        None,
                        None,
                        None,
                        0.0,
                        str(exc),
                    )
                image_result["results"].append(result.as_dict())
                print(f"{result.strategy:16} {safety_level:5} -> {result.verdict or 'NONE':7} {result.elapsed_s:6.1f}s")
        results.append(image_result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "gemma4_model": args.gemma4_model,
        "image_dir": str(image_dir),
        "images": results,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True))
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
