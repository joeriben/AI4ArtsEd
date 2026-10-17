"""MMAudio (Cheng et al. 2024), run by ComfyUI.

Audio for a picture, or for a text: what gpu_service/services/
mmaudio_backend.py did, under ComfyUI's memory management (_card). The
network, the flow-matching solver and MMAudio's feature extractors (CLIP,
Synchformer, the audio VAE) are held together as one model, in bfloat16, the
GPU service's operating point.

The weights are folders under <ComfyUI>/models/mmaudio/<variant>/ laid out
the way MMAudio's ModelConfig names them (all_model_cfg), relative to the
folder instead of the working directory: weights/mmaudio_<variant>.pth,
ext_weights/v1-44.pth (the VAE), ext_weights/synchformer_state_dict.pth, and
for a 16 k variant ext_weights/best_netG.pt (the vocoder). The CLIP image
tower comes from the Hugging Face cache by name (open_clip, apple/
DFN5B-CLIP-ViT-H-14-384), as it did in the GPU service.
"""
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

import torch

from . import _card, _whole

logger = logging.getLogger(__name__)

FOLDER_NAME = "mmaudio"
KEEP_BUILT = 1
MAX_DURATION_S = 8.0
DEFAULT_STEPS = 25
DEFAULT_CFG_STRENGTH = 4.5
# The GPU service loaded the variant whole under a 6000 MB request to its
# coordinator; the activations of an 8 s generation ran inside it.
RESERVE_BYTES = 4 * 1024 ** 3

_card.register_folder(FOLDER_NAME)
_registry = _card.Registry("MMAudio", KEEP_BUILT)


def _config_of(path: str):
    """MMAudio's ModelConfig for the folder: the variant is the folder's
    name, and every path of the config is taken relative to the folder."""
    from mmaudio.eval_utils import all_model_cfg
    variant = os.path.basename(path.rstrip(os.sep))
    cfg = all_model_cfg.get(variant)
    if cfg is None:
        return None
    root = Path(path)
    files = {
        "model_path": root / cfg.model_path,
        "vae_path": root / cfg.vae_path,
        "synchformer_ckpt": root / cfg.synchformer_ckpt,
        "bigvgan_16k_path": (root / cfg.bigvgan_16k_path) if cfg.bigvgan_16k_path is not None else None,
    }
    return cfg, files


def whole(path: str) -> bool:
    """The files all_model_cfg names for the variant, as _whole.mmaudio
    lists them for both sides; the build reads the config itself."""
    return _whole.whole("mmaudio", path)


def installed_dirs():
    return _card.listed_dirs(FOLDER_NAME, whole)


def weights_path(dir_name: str) -> str:
    return _card.folder_path(FOLDER_NAME, dir_name, whole)


def _build(dir_name: str) -> Any:
    from mmaudio.model.flow_matching import FlowMatching
    from mmaudio.model.networks import get_my_mmaudio
    from mmaudio.model.utils.features_utils import FeaturesUtils

    path = weights_path(dir_name)
    cfg, files = _config_of(path)
    logger.info(f"[AI4ArtsEd MMAudio] Building {dir_name} from {path}")
    dtype = torch.bfloat16
    net = get_my_mmaudio(cfg.model_name).to(dtype).eval()
    net.load_weights(torch.load(files["model_path"], map_location="cpu", weights_only=True))
    fm = FlowMatching(min_sigma=0, inference_mode="euler", num_steps=DEFAULT_STEPS)
    feature_utils = FeaturesUtils(
        tod_vae_ckpt=files["vae_path"],
        synchformer_ckpt=files["synchformer_ckpt"],
        enable_conditions=True,
        mode=cfg.mode,
        bigvgan_vocoder_ckpt=files["bigvgan_16k_path"],
        need_vae_encoder=False,
    ).to(dtype).eval()
    container = _card.Container(net=net, features=feature_utils)
    return _card.Held(key=dir_name, patcher=_card.wrap(container), module=container,
                      weight_bytes=_card.module_bytes(container),
                      extra={"config": cfg, "seq_cfg": cfg.seq_cfg, "fm": fm})


def get_built(dir_name: str) -> Any:
    return _registry.get(dir_name, _build, _card.bytes_of_files(weights_path(dir_name)))


def generate(dir_name: str, image=None, prompt: str = "", negative_prompt: str = "",
             duration_seconds: float = MAX_DURATION_S, cfg_strength: float = DEFAULT_CFG_STRENGTH,
             num_steps: int = DEFAULT_STEPS, seed: int = 0) -> Dict[str, Any]:
    """Audio for a PIL image (with the text as a prompt), or for the text
    alone when no image is given. Returns {audio [channels, samples] float32
    on the CPU, sample_rate, duration_seconds, seed, generation_time_ms}."""
    from mmaudio.eval_utils import generate as mm_generate, load_image

    t_start = time.time()
    duration_seconds = min(float(duration_seconds), MAX_DURATION_S)
    held = get_built(dir_name)
    with held.lock:
        device = _card.on_card(held, RESERVE_BYTES, held.key)
        net, feature_utils = held.module.net, held.module.features
        seq_cfg, fm = held.extra["seq_cfg"], held.extra["fm"]
        tmp_path: Optional[Path] = None
        try:
            with torch.inference_mode():
                rng = torch.Generator(device=device)
                rng.manual_seed(seed)
                clip_frames = None
                if image is not None:
                    # MMAudio's load_image reads a file.
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                        image.convert("RGB").save(f, format="PNG")
                        tmp_path = Path(f.name)
                    clip_frames = load_image(tmp_path).clip_frames.unsqueeze(0)  # [1, 3, H, W]
                seq_cfg.duration = duration_seconds
                net.update_seq_lengths(seq_cfg.latent_seq_len, seq_cfg.clip_seq_len, seq_cfg.sync_seq_len)
                fm.num_steps = num_steps
                _card.interrupted()
                audios = mm_generate(
                    clip_frames,
                    None,
                    [prompt] if prompt else [""],
                    negative_text=[negative_prompt] if negative_prompt else [""],
                    feature_utils=feature_utils,
                    net=net,
                    fm=fm,
                    rng=rng,
                    cfg_strength=cfg_strength,
                    image_input=image is not None,
                )
                audio = audios.float().cpu()[0]  # [channels, samples]
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
    if audio.dim() == 1:
        audio = audio.unsqueeze(0)
    return {
        "audio": audio,
        "sample_rate": int(seq_cfg.sampling_rate),
        "duration_seconds": duration_seconds,
        "seed": seed,
        "generation_time_ms": int((time.time() - t_start) * 1000),
    }
