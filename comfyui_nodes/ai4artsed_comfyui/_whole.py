"""Whether a weights folder of a media station holds a whole model.

Read from both sides of the seam, the way _snapshot.py is for the language
models: the station modules list the folders they can load with these
functions (_stable_audio, _imagebind, _mmaudio, _heartmula, _hunyuan3d,
_media_reading), and the DevServer says which aliases are installed and
whether a download may leave its staging folder (my_app/services/
local_media_weights.py, which loads this module by path). One definition per
station, so the two sides agree.

Whole means, for every station: every file the station reads when it builds
the model is there, and no file of the download is still a huggingface_hub
'.incomplete' part (_snapshot.part_in_flight) under what the station reads.
A folder that holds one model is read whole. A root that holds sibling
models beside the ones read (heartlib's checkpoint root with its dated
variants, the Hunyuan3D snapshot with its fast and turbo variants) is held
to its own files and the folders read from it, and a download broken off in
a sibling folder does not count against it.
`missing(station, path)` names the first thing the folder lacks, for the
sentence an installer or a node answers with; `whole` is that being None.

Stdlib only.
"""
import json
import os
from typing import Callable, Dict, Iterable, List, Optional

try:
    from . import _snapshot
except ImportError:
    # Loaded by path, outside the package (the DevServer): the sibling is
    # loaded the same way.
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "ai4artsed_snapshot", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_snapshot.py"))
    _snapshot = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_snapshot)


def _files(path: str, names: Iterable[str], read_under: Optional[List[str]] = None) -> Optional[str]:
    """The first of `names` (paths relative to the folder) that is absent,
    else a part still in flight under what is read, else None. `read_under`
    None reads the whole folder; a list names the subfolders read, and the
    folder's own files with them."""
    if not os.path.isdir(path):
        return "the folder is absent"
    for rel in names:
        if not os.path.isfile(os.path.join(path, rel)):
            return f"{rel} is missing"
    if read_under is None:
        part = _snapshot.part_in_flight(path)
        return None if part is None else f"{part} is a part still in flight"
    for f in sorted(os.listdir(path)):
        if f.endswith(".incomplete") and os.path.isfile(os.path.join(path, f)):
            return f"{f} is a part still in flight"
    for sub in read_under:
        part = _snapshot.part_in_flight(os.path.join(path, sub))
        if part is not None:
            return f"{sub}/{part} is a part still in flight"
    return None


def _under(sub: str, why: Optional[str]) -> Optional[str]:
    return None if why is None else f"{sub}: {why}"


# ---------------------------------------------------------------------------
# Stable Audio (stable-audio-tools): a checkpoint folder.

def stable_audio_conditioner_subfolders(config: dict) -> List[str]:
    """The subfolders model_config.json names for its text conditioners
    (Stable Audio 3 ships its T5Gemma encoder beside the weights)."""
    found = []
    for c in (config.get("model", {}).get("conditioning", {}) or {}).get("configs", []) or []:
        sub = (c.get("config") or {}).get("subfolder")
        if sub:
            found.append(sub)
    return found


def stable_audio_config(path: str) -> Optional[dict]:
    try:
        with open(os.path.join(path, "model_config.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def stable_audio(path: str) -> Optional[str]:
    """model_config.json, the weights (model.safetensors, or the model.ckpt of
    the older releases), and every conditioner subfolder the config names,
    whole as the transformers snapshot it is."""
    if not os.path.isdir(path):
        return "the folder is absent"
    config = stable_audio_config(path)
    if config is None:
        return "model_config.json is missing or unreadable"
    if not any(os.path.isfile(os.path.join(path, w)) for w in ("model.safetensors", "model.ckpt")):
        return "model.safetensors is missing"
    for sub in stable_audio_conditioner_subfolders(config):
        why = _under(sub, _snapshot.missing(os.path.join(path, sub)))
        if why is not None:
            return why
    return _files(path, [], read_under=[])


# ---------------------------------------------------------------------------
# ImageBind: one checkpoint file.

IMAGEBIND_WEIGHTS_FILE = "imagebind_huge.pth"


def imagebind(path: str) -> Optional[str]:
    return _files(path, [IMAGEBIND_WEIGHTS_FILE])


# ---------------------------------------------------------------------------
# MMAudio: a variant folder, laid out the way MMAudio's all_model_cfg names
# the files relative to the folder: weights/mmaudio_<variant>.pth, the VAE
# of the sample rate, the Synchformer, and for a 16 k variant the BigVGAN
# vocoder. The variant is read off the weights file, so the test holds for
# the installer's staging folder as it does for the folder in place.

MMAUDIO_WEIGHTS_PREFIX = "weights/mmaudio_"


def mmaudio_variant(path: str) -> Optional[str]:
    weights = os.path.join(path, os.path.dirname(MMAUDIO_WEIGHTS_PREFIX))
    prefix = os.path.basename(MMAUDIO_WEIGHTS_PREFIX)
    try:
        names = sorted(f for f in os.listdir(weights) if f.startswith(prefix) and f.endswith(".pth"))
    except OSError:
        return None
    return names[0][len(prefix):-len(".pth")] if names else None


def mmaudio_files(variant: str) -> List[str]:
    names = [f"{MMAUDIO_WEIGHTS_PREFIX}{variant}.pth", "ext_weights/synchformer_state_dict.pth"]
    if variant.endswith("_16k"):
        names += ["ext_weights/v1-16.pth", "ext_weights/best_netG.pt"]
    else:
        names.append("ext_weights/v1-44.pth")
    return names


def mmaudio(path: str) -> Optional[str]:
    if not os.path.isdir(path):
        return "the folder is absent"
    variant = mmaudio_variant(path)
    if variant is None:
        return f"{MMAUDIO_WEIGHTS_PREFIX}<variant>.pth is missing"
    return _files(path, mmaudio_files(variant))


# ---------------------------------------------------------------------------
# HeartMuLa (heartlib): a checkpoint root with the tokenizer, the generation
# config, the codec, and one HeartMuLa-oss-<version> folder per version.

HEARTMULA_VERSION_PREFIX = "HeartMuLa-oss-"
HEARTMULA_CODEC_SUBFOLDER = "HeartCodec-oss"


def heartmula_versions(path: str) -> List[str]:
    """The versions whose HeartMuLa-oss-<version> folder is a whole snapshot,
    sorted: what the node offers. A version folder that holds its config and
    index without the shards is left out."""
    try:
        entries = sorted(os.listdir(path))
    except OSError:
        return []
    return [e[len(HEARTMULA_VERSION_PREFIX):] for e in entries
            if e.startswith(HEARTMULA_VERSION_PREFIX)
            and _snapshot.missing(os.path.join(path, e)) is None]


def heartmula(path: str) -> Optional[str]:
    if not os.path.isdir(path):
        return "the folder is absent"
    if not heartmula_versions(path):
        candidates = sorted(e for e in os.listdir(path) if e.startswith(HEARTMULA_VERSION_PREFIX))
        if candidates:
            return _under(candidates[0], _snapshot.missing(os.path.join(path, candidates[0])))
        return f"no {HEARTMULA_VERSION_PREFIX}<version> folder is there"
    why = _under(HEARTMULA_CODEC_SUBFOLDER, _snapshot.missing(os.path.join(path, HEARTMULA_CODEC_SUBFOLDER)))
    if why is not None:
        return why
    return _files(path, ["tokenizer.json", "gen_config.json"], read_under=[])


# ---------------------------------------------------------------------------
# Hunyuan3D 2 (hy3dgen): the shape model, the delight and the paint
# pipelines of one repository snapshot.

HUNYUAN3D_SHAPE_SUBFOLDER = "hunyuan3d-dit-v2-0"
HUNYUAN3D_DELIGHT_SUBFOLDER = "hunyuan3d-delight-v2-0"
HUNYUAN3D_PAINT_SUBFOLDER = "hunyuan3d-paint-v2-0"
HUNYUAN3D_FILES = [
    f"{HUNYUAN3D_SHAPE_SUBFOLDER}/config.yaml",
    f"{HUNYUAN3D_SHAPE_SUBFOLDER}/model.fp16.safetensors",
    f"{HUNYUAN3D_DELIGHT_SUBFOLDER}/model_index.json",
    f"{HUNYUAN3D_DELIGHT_SUBFOLDER}/unet/diffusion_pytorch_model.safetensors",
    f"{HUNYUAN3D_DELIGHT_SUBFOLDER}/vae/diffusion_pytorch_model.safetensors",
    f"{HUNYUAN3D_DELIGHT_SUBFOLDER}/text_encoder/model.safetensors",
    f"{HUNYUAN3D_PAINT_SUBFOLDER}/model_index.json",
    f"{HUNYUAN3D_PAINT_SUBFOLDER}/unet/diffusion_pytorch_model.safetensors",
    f"{HUNYUAN3D_PAINT_SUBFOLDER}/vae/diffusion_pytorch_model.safetensors",
    f"{HUNYUAN3D_PAINT_SUBFOLDER}/text_encoder/pytorch_model.bin",
]


def hunyuan3d(path: str) -> Optional[str]:
    return _files(path, HUNYUAN3D_FILES, read_under=[
        HUNYUAN3D_SHAPE_SUBFOLDER, HUNYUAN3D_DELIGHT_SUBFOLDER, HUNYUAN3D_PAINT_SUBFOLDER])


# ---------------------------------------------------------------------------
# The media readers (transformers): a snapshot, the weights as safetensors
# or as the pytorch_model.bin MuQ-MuLan and CLAP are published with.

MEDIA_READING_WEIGHTS_SUFFIXES = (".safetensors", ".bin")


def media_reading(path: str) -> Optional[str]:
    return _snapshot.missing(path, MEDIA_READING_WEIGHTS_SUFFIXES)


# ---------------------------------------------------------------------------

CHECKS: Dict[str, Callable[[str], Optional[str]]] = {
    "stable_audio": stable_audio,
    "imagebind": imagebind,
    "mmaudio": mmaudio,
    "heartmula": heartmula,
    "hunyuan3d": hunyuan3d,
    "media_reading": media_reading,
}


def missing(station: str, path: str) -> Optional[str]:
    """What the folder lacks to be a whole model of the station, or None."""
    try:
        check = CHECKS[station]
    except KeyError:
        raise KeyError(f"no media station {station!r}; the stations are {sorted(CHECKS)}") from None
    return check(path)


def whole(station: str, path: str) -> bool:
    return missing(station, path) is None
