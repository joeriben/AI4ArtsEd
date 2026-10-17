#!/usr/bin/env python3
"""
Media-path checks for a Transformers upgrade: image, video, voice, description.

The import-level checks live in test_transformers_upgrade_smoke.py and the
component-level ones in test_transformers_upgrade_empirical.py. This file asks
the question those two cannot answer: does the platform still *produce* an
image, a video, a spoken sentence and a description of what it made?

Run it under the current venv first to get a baseline, then under the upgrade
venv. A probe that fails under both is not an upgrade regression — it is
something else, and the comparison is the only way to tell them apart.

    python devserver/testfiles/test_transformers_upgrade_media.py
    python devserver/testfiles/test_transformers_upgrade_media.py image voice

Models are read from the running configuration, never restated here, and are
loaded offline from the local cache. Nothing is downloaded.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Callable

ROOT_DIR = Path(__file__).resolve().parents[2]
DEVSERVER_DIR = ROOT_DIR / "devserver"
for _p in (ROOT_DIR, DEVSERVER_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Same discipline as the empirical script: no hub traffic during validation.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

OUT_DIR = Path(os.environ.get("UPGRADE_TEST_OUT", "/tmp/transformers_upgrade_media"))

# The one string this file speaks with. Taken from the existing empirical
# script so no new test wording enters the repository.
PROBE_TEXT = "The forest is dark and"


class ProbeFailure(Exception):
    """A probe that got partway. `payload` is what it did establish.

    A probe that collects several results must not report success because the
    call returned — the one that failed has to reach the report as a failure,
    with everything the run did manage to show still attached.
    """

    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload or {}


def _free() -> None:
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass


def _vram_gb() -> float:
    try:
        import torch
        return torch.cuda.memory_allocated() / 1024 ** 3
    except Exception:
        return -1.0


# ---------------------------------------------------------------- image


def probe_image() -> dict:
    """SD3.5 through diffusers — CLIP and T5 text encoders come from transformers."""
    import asyncio
    import torch
    from diffusers import StableDiffusion3Pipeline
    from my_app.services.latent_lab_model import get_latent_lab_model_id

    model_id = asyncio.run(get_latent_lab_model_id())
    print(f"[image] {model_id}")

    pipe = StableDiffusion3Pipeline.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    pipe = pipe.to("cuda")

    image = pipe(
        prompt=PROBE_TEXT,
        num_inference_steps=8,
        height=512,
        width=512,
        generator=torch.Generator("cuda").manual_seed(0),
    ).images[0]

    path = OUT_DIR / "image.png"
    image.save(path)

    del pipe
    _free()
    return {"artifact": str(path), "size": list(image.size), "model": model_id}


# ---------------------------------------------------------------- video


def probe_video() -> dict:
    """Wan through diffusers — the UMT5 text encoder comes from transformers."""
    import torch
    from diffusers import WanPipeline
    from diffusers.utils import export_to_video

    model_id = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
    print(f"[video] {model_id}")

    pipe = WanPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    pipe = pipe.to("cuda")

    result = pipe(
        prompt=PROBE_TEXT,
        height=480,
        width=832,
        num_frames=25,
        num_inference_steps=8,
        generator=torch.Generator("cuda").manual_seed(0),
    )
    frames = result.frames[0]

    path = OUT_DIR / "video.mp4"
    export_to_video(frames, str(path), fps=12)

    del pipe
    _free()
    return {"artifact": str(path), "frames": len(frames), "model": model_id}


# ---------------------------------------------------------------- voice


def probe_voice() -> dict:
    """The platform voice, which is the only one an upgrade here can reach.

    Supertonic carries the platform's own voice and touches no transformers at
    all — so this probe answers "the voice still speaks", not "transformers is
    safe for speech".

    Qwen3-TTS used to be probed alongside it, and was the sharp case: it
    shipped its own modeling code written against transformers internals. On
    2026-08-12 an upgrade broke exactly that and the technology was removed.
    Its replacement, VoxCPM2, is not probed here and cannot be: it runs out of
    process in its own environment with its own torch and transformers, which
    is precisely why it was installed that way. Nothing in this process
    reaches it.
    """
    import asyncio

    # `errors` is what makes this probe fail: a collected error must not be
    # allowed to pass as a result, and an unreachable synthesiser is a
    # collected error, not a silence.
    out: dict = {}
    errors: list[str] = []

    # --- the platform voice
    try:
        from my_app.services.supertonic_backend import get_supertonic_backend
        backend = get_supertonic_backend()
        available = asyncio.run(backend.is_available())
        out["supertonic_available"] = bool(available)
        if not available:
            # Untested is not tested-and-fine. A synthesiser this run could not
            # reach says nothing about the upgrade, and must not read as if it
            # did — that is the same fail-open the checking chain was cleaned of.
            errors.append("supertonic: not available, nothing was probed")
        else:
            audio, seed, voice, f0 = asyncio.run(
                backend.synthesize(PROBE_TEXT, language="en"))
            path = OUT_DIR / "voice_supertonic.wav"
            path.write_bytes(audio)
            out["supertonic_artifact"] = str(path)
            out["supertonic_bytes"] = len(audio)
            out["supertonic_voice"] = voice
            out["supertonic_f0"] = round(float(f0), 1)
    except Exception as exc:
        out["supertonic_error"] = f"{type(exc).__name__}: {exc}"
        errors.append(f"supertonic: {type(exc).__name__}: {exc}")

    # The other two synthesisers are out of process by design and are not
    # probed here — see the docstring.
    out["out_of_process"] = "voxcpm, piper — own environments, unaffected"

    _free()
    if errors:
        raise ProbeFailure("; ".join(errors), out)
    return out


# ---------------------------------------------------------------- description


def probe_description() -> dict:
    """Qwen3-VL describing what the image and video probes produced.

    This is the only description path that runs on transformers. The image
    description the platform shows a user does not: it goes to Ollama, and the
    lookback check to llama-cpp. Both are unaffected by a transformers
    upgrade — and equally unable to answer for it.
    """
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from my_app.services import local_llm_weights, local_media_weights

    # The reader the platform's table names for a video, and what it is told
    # (config/local_media_weights.json, reading block); a 'local/' alias is an
    # entry of the language-model table.
    alias = local_media_weights.reader_alias("video")
    repo_id = local_llm_weights.entry(alias)["repo"]
    video_prompt = local_media_weights.prompt("video")
    print(f"[description] {repo_id}")

    processor = AutoProcessor.from_pretrained(repo_id, local_files_only=True)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        repo_id,
        dtype=torch.bfloat16,
        device_map="cuda",
        local_files_only=True,
    )
    model.eval()

    from PIL import Image

    # Which picture was described has to reach the report. Two runs compared
    # against each other are only comparable if they described the same thing,
    # and a stand-in that goes unrecorded makes them look like they did.
    image_path = OUT_DIR / "image.png"
    described = "image probe output"
    if not image_path.exists():
        described = "flat stand-in (image probe produced nothing)"
        Image.new("RGB", (512, 512), (40, 60, 90)).save(image_path)

    image = Image.open(image_path).convert("RGB")

    messages = [{
        "role": "user",
        "content": [
            {"type": "image"},
            {"type": "text", "text": video_prompt},
        ],
    }]
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], return_tensors="pt").to("cuda")

    # No output cap: the model stops at its own end token. A cap here would cut
    # a description mid-sentence and the run would still call it a pass.
    with torch.inference_mode():
        generated = model.generate(**inputs, do_sample=False)
    trimmed = generated[0][inputs["input_ids"].shape[1]:]
    description = processor.decode(trimmed, skip_special_tokens=True).strip()

    print(f"[description] {description[:200]}")

    del model
    _free()
    if not description:
        raise ProbeFailure("empty description", {"model": repo_id})
    return {"model": repo_id, "described": described, "description": description}


# ---------------------------------------------------------------- driver


PROBES: dict[str, Callable[[], dict]] = {
    "image": probe_image,
    "video": probe_video,
    "voice": probe_voice,
    "description": probe_description,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("probes", nargs="*", choices=list(PROBES),
                        help="probes to run (default: all, in order)")
    args = parser.parse_args()
    selected = args.probes or list(PROBES)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import torch
    import transformers
    import diffusers

    env = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "diffusers": diffusers.__version__,
        "cuda": torch.cuda.is_available(),
    }
    print(json.dumps(env, indent=2))

    results: dict = {"env": env, "probes": {}}
    failed: list[str] = []

    for name in selected:
        print(f"\n===== {name} =====")
        started = time.time()
        try:
            payload = PROBES[name]()
            results["probes"][name] = {
                "ok": True, "seconds": round(time.time() - started, 1), **payload}
            print(f"[{name}] OK in {time.time() - started:.1f}s "
                  f"(vram {_vram_gb():.1f} GB still allocated)")
        except Exception as exc:
            failed.append(name)
            results["probes"][name] = {
                "ok": False,
                "seconds": round(time.time() - started, 1),
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                **getattr(exc, "payload", {}),
            }
            print(f"[{name}] FAILED: {type(exc).__name__}: {exc}")
        _free()

    # Merge, don't overwrite: rerunning one probe must not erase the others.
    tag = f"transformers-{transformers.__version__}"
    report = OUT_DIR / f"report_{tag}.json"
    if report.exists():
        try:
            previous = json.loads(report.read_text())
            merged = dict(previous.get("probes", {}))
            merged.update(results["probes"])
            results["probes"] = merged
        except Exception:
            pass
    report.write_text(json.dumps(results, indent=2))
    print(f"\nreport: {report}")

    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print("OK: all selected media probes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
