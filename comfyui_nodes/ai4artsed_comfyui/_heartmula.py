"""HeartMuLa (heartlib), run by ComfyUI.

A song from lyrics and tags: what gpu_service/services/heartmula_backend.py
did with heartlib's HeartMuLaGenPipeline, under ComfyUI's memory management
(_card). The language model (HeartMuLa, bfloat16) and the codec (HeartCodec,
float32) are held together as one model; the pipeline object keeps pointing
at them and is told the device they are on before every generation. The
GPU service built the pipeline with lazy_load, which loaded both from disk
for every song and dropped them after it; here they are built once and
ComfyUI moves them.

The weights are folders under <ComfyUI>/models/heartmula/<dir>/ laid out the
way heartlib's from_pretrained resolves them: tokenizer.json and
gen_config.json at the root, HeartMuLa-oss-<version>/ and HeartCodec-oss/
beside them (each a transformers-style folder with config.json and
safetensors shards).
"""
import json
import logging
import os
import time
from typing import Any, Dict, Iterable

import torch

from . import _card, _whole

logger = logging.getLogger(__name__)

FOLDER_NAME = "heartmula"
KEEP_BUILT = 1
DEFAULT_VERSION = "3B"
SAMPLE_RATE = 48000
# gpu_config MODEL_PEAK_VRAM_MB["heartmula"] = 16 000 MB, measured 11.1 GB at
# 30 s and cfg 1.0 with the weights; the caches of a 240 s song beyond the
# weights are what the reserve covers.
RESERVE_BYTES = 8 * 1024 ** 3

_card.register_folder(FOLDER_NAME)
_registry = _card.Registry("HeartMuLa", KEEP_BUILT)


def _versions(path: str):
    """The HeartMuLa-oss-<version> folders of a checkpoint root that are
    whole snapshots (_whole.heartmula_versions)."""
    return _whole.heartmula_versions(path)


def whole(path: str) -> bool:
    return _whole.whole("heartmula", path)


def installed_dirs():
    return _card.listed_dirs(FOLDER_NAME, whole)


def weights_path(dir_name: str) -> str:
    return _card.folder_path(FOLDER_NAME, dir_name, whole)


def _key(dir_name: str, version: str) -> str:
    return f"{dir_name}/{version}"


def _build_for(dir_name: str, version: str):
    def build(_key: str) -> Any:
        from heartlib import HeartMuLaGenPipeline
        from heartlib.heartcodec.modeling_heartcodec import HeartCodec
        from heartlib.heartmula.modeling_heartmula import HeartMuLa

        path = weights_path(dir_name)
        logger.info(f"[AI4ArtsEd HeartMuLa] Building {dir_name} ({version}) from {path}")
        cpu = torch.device("cpu")
        # lazy_load=True builds the pipeline without its two models; they
        # are loaded here, because HeartCodec's checkpoint stores each
        # codebook's `initted` flag as a one-element tensor where
        # vector-quantize-pytorch 1.27 registers a scalar, and transformers
        # 5 refuses the shape unless told to ignore it. A tensor it ignores
        # is left as the meta build made it, which is memory nobody wrote:
        # on 2026-09-14 all eight flags read True, on 2026-09-15 four of
        # them read False.
        # So the flags are copied in from the checkpoint by hand below
        # (all eight are [1.0] there), and the assertion after that keeps
        # it so, since False would re-fit the codebooks from the first batch.
        pipe = HeartMuLaGenPipeline.from_pretrained(
            path,
            device={"mula": cpu, "codec": cpu},
            dtype={"mula": torch.bfloat16, "codec": torch.float32},
            version=version,
            lazy_load=True,
        )
        pipe._mula = HeartMuLa.from_pretrained(pipe.mula_path, device_map=cpu, dtype=torch.bfloat16)
        pipe._codec, info = HeartCodec.from_pretrained(pipe.codec_path, device_map=cpu,
                                                       dtype=torch.float32,
                                                       ignore_mismatched_sizes=True,
                                                       output_loading_info=True)
        # The ignore is allowed for those eight flags and for nothing else:
        # any other tensor the checkpoint did not fill would run with its
        # initial values, and the sound would say nothing about why.
        # Measured 2026-09-15 on HeartCodec-oss in this venv: 0 missing,
        # 0 unexpected, the 8 `initted` flags mismatched ([1] vs []).
        unfilled = list(info.get("missing_keys", ())) + [
            (k if isinstance(k, str) else k[0]) for k in info.get("mismatched_keys", ())
            if not (k if isinstance(k, str) else k[0]).endswith("_codebook.initted")]
        if unfilled or info.get("error_msgs"):
            raise RuntimeError(f"HeartCodec at {pipe.codec_path} was not filled from its checkpoint: "
                               f"{len(unfilled)} tensor(s) unfilled {unfilled[:4]}, "
                               f"errors {list(info.get('error_msgs', ()))[:2]}")
        pipe.lazy_load = False
        # transformers 5 builds the model on the meta device and fills in
        # the checkpoint's tensors; a buffer a module computes in its
        # __init__ and does not save (torchtune's RoPE cache) stays unbuilt.
        for model in (pipe._mula, pipe._codec):
            for m in model.modules():
                if hasattr(m, "rope_init") and not getattr(m, "is_cache_built", True):
                    m.rope_init()
        flags = [name for name, _ in pipe._codec.named_buffers() if name.endswith("_codebook.initted")]
        stored = _checkpoint_tensors(pipe.codec_path, flags)
        for name, buf in pipe._codec.named_buffers():
            if name in stored:
                buf.copy_(stored[name].reshape(buf.shape).to(buf.dtype))
            if name.endswith("_codebook.initted") and not bool(buf.item()):
                raise RuntimeError(f"HeartCodec {name} is False in the checkpoint; the codebook would be re-fitted")
        pipe.mula.eval()
        pipe.codec.eval()
        container = _card.Container(mula=pipe.mula, codec=pipe.codec)
        return _card.Held(key=_key, patcher=_card.wrap(container), module=container,
                          weight_bytes=_card.module_bytes(container), extra={"pipe": pipe})
    return build


def _checkpoint_tensors(path: str, keys: Iterable[str]) -> Dict[str, torch.Tensor]:
    """The named tensors as the checkpoint under `path` stores them: read
    off the one file, or off the shards its index names for them. A key the
    checkpoint lacks is an error, not a silence."""
    from safetensors import safe_open
    keys = list(keys)
    index = os.path.join(path, "model.safetensors.index.json")
    by_file: Dict[str, list] = {}
    if os.path.exists(index):
        with open(index, encoding="utf-8") as f:
            weight_map = json.load(f)["weight_map"]
        for k in keys:
            if k not in weight_map:
                raise KeyError(f"{k} is not in {index}")
            by_file.setdefault(weight_map[k], []).append(k)
    else:
        by_file["model.safetensors"] = keys
    out: Dict[str, torch.Tensor] = {}
    for name, ks in by_file.items():
        with safe_open(os.path.join(path, name), framework="pt", device="cpu") as f:
            for k in ks:
                out[k] = f.get_tensor(k)
    return out


def get_built(dir_name: str, version: str = DEFAULT_VERSION) -> Any:
    path = weights_path(dir_name)
    if version not in _versions(path):
        raise FileNotFoundError(f"no HeartMuLa-oss-{version} under {path}; there: {_versions(path)}")
    incoming = (_card.bytes_of_files(os.path.join(path, f"HeartMuLa-oss-{version}"))
                + _card.bytes_of_files(os.path.join(path, "HeartCodec-oss")))
    return _registry.get(_key(dir_name, version), _build_for(dir_name, version), incoming)


def preload(dir_name: str, version: str = DEFAULT_VERSION) -> Dict[str, Any]:
    """Built and on the card, nothing generated: the settings page's load
    button."""
    held = get_built(dir_name, version)
    with held.lock:
        _card.on_card(held, RESERVE_BYTES, held.key)
    return {"loaded": held.key, "weight_bytes": held.weight_bytes}


def generate(dir_name: str, lyrics: str, tags: str, version: str = DEFAULT_VERSION,
             temperature: float = 1.0, topk: int = 70, cfg_scale: float = 3.0,
             max_audio_length_ms: int = 240_000, seed: int = 0) -> Dict[str, Any]:
    """The song: {audio [channels, samples] float32 on the CPU, sample_rate,
    duration_seconds, seed, generation_time_ms}. The pipeline's own steps
    (preprocess, _forward, the codec's detokenize) run as its __call__ runs
    them, with the file write of its postprocess left out."""
    import random

    t_start = time.time()
    held = get_built(dir_name, version)
    with held.lock:
        device = _card.on_card(held, RESERVE_BYTES, held.key)
        pipe = held.extra["pipe"]
        pipe.mula_device = device
        pipe.codec_device = device
        random.seed(seed)
        torch.manual_seed(seed)
        if device.type == "cuda":
            torch.cuda.manual_seed(seed)
        logger.info(f"[AI4ArtsEd HeartMuLa] Generating: tags='{tags[:60]}', "
                    f"max={max_audio_length_ms}ms, temperature={temperature}, topk={topk}, "
                    f"cfg={cfg_scale}, seed={seed}")
        _card.interrupted()
        # heartlib's frame loop (HeartMuLaGenPipeline._forward) asks nobody
        # between frames, and ComfyUI asks only before a node runs: a stop
        # reached a song still loading and none being made, and the card made
        # the whole song for nobody. Every frame goes through
        # mula.generate_frame, so the interrupt is asked there.
        mula = pipe.mula
        frame = mula.generate_frame

        def frame_unless_stopped(*args, **kwargs):
            _card.interrupted()
            return frame(*args, **kwargs)

        mula.generate_frame = frame_unless_stopped
        try:
            with torch.no_grad():
                model_inputs = pipe.preprocess({"lyrics": lyrics, "tags": tags}, cfg_scale=cfg_scale)
                model_outputs = pipe._forward(model_inputs, max_audio_length_ms=max_audio_length_ms,
                                              temperature=temperature, topk=topk, cfg_scale=cfg_scale)
                frames = model_outputs["frames"].to(device)
                wav = pipe.codec.detokenize(frames)
        finally:
            del mula.generate_frame
        audio = wav.to(torch.float32).cpu()
    if audio.dim() == 1:
        audio = audio.unsqueeze(0)
    return {
        "audio": audio,
        "sample_rate": SAMPLE_RATE,
        "duration_seconds": round(audio.shape[-1] / float(SAMPLE_RATE), 3),
        "seed": seed,
        "generation_time_ms": int((time.time() - t_start) * 1000),
    }
