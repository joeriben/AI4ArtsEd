"""ImageBind (Girdhar et al. 2023), run by ComfyUI.

The image side of the image-guided audio generation (_stable_audio.
generate_guided): the image's embedding in ImageBind's joint space, which
the guidance compares the generated audio's embedding against. What
gpu_service/services/imagebind_backend.py did, under ComfyUI's memory
management (_card).

The weights are folders under <ComfyUI>/models/imagebind/<dir>/ holding
imagebind_huge.pth, the checkpoint Meta publishes; the model is the
imagebind_huge architecture with that state dict, in float32 as published.
"""
import logging
import os
import tempfile
from typing import Any

import torch

from . import _card, _whole

logger = logging.getLogger(__name__)

FOLDER_NAME = "imagebind"
KEEP_BUILT = 1
WEIGHTS_FILE = _whole.IMAGEBIND_WEIGHTS_FILE
# The vision tower on one 224x224 picture; the audio tower's activations
# during a guided step are announced by the guided run itself.
RESERVE_BYTES = 1024 ** 3

_card.register_folder(FOLDER_NAME)
_registry = _card.Registry("ImageBind", KEEP_BUILT)


def whole(path: str) -> bool:
    return _whole.whole("imagebind", path)


def installed_dirs():
    return _card.listed_dirs(FOLDER_NAME, whole)


def weights_path(dir_name: str) -> str:
    return _card.folder_path(FOLDER_NAME, dir_name, whole)


def _build(dir_name: str) -> Any:
    from imagebind.models import imagebind_model

    path = os.path.join(weights_path(dir_name), WEIGHTS_FILE)
    logger.info(f"[AI4ArtsEd ImageBind] Building {dir_name} from {path}")
    model = imagebind_model.imagebind_huge(pretrained=False)
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    model.eval()
    container = _card.Container(imagebind=model)
    return _card.Held(key=dir_name, patcher=_card.wrap(container), module=container,
                      weight_bytes=_card.module_bytes(container))


def get_built(dir_name: str) -> Any:
    return _registry.get(dir_name, _build, _card.bytes_of_files(weights_path(dir_name)))


def on_card(held: Any, reserve: int = RESERVE_BYTES) -> torch.device:
    return _card.on_card(held, reserve, held.key)


def encode_image(held: Any, image) -> torch.Tensor:
    """The ImageBind embedding of a PIL image: [1, 1024], L2-normalized, on
    the device the model is on. ImageBind's own transform reads a file, so
    the picture passes through a temp file, as it did in the GPU service."""
    from imagebind.data import load_and_transform_vision_data
    from imagebind.models.imagebind_model import ModalityType

    device = held.patcher.load_device
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        image.convert("RGB").save(f, format="PNG")
        tmp_path = f.name
    try:
        inputs = {ModalityType.VISION: load_and_transform_vision_data([tmp_path], device)}
        with torch.no_grad():
            embeddings = held.module.imagebind(inputs)
        return embeddings[ModalityType.VISION]
    finally:
        os.unlink(tmp_path)
