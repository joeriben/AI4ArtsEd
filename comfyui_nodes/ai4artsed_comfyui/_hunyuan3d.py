"""Hunyuan3D 2 (hy3dgen), run by ComfyUI.

A textured mesh from one picture: the shape pipeline (a flow-matching DiT
and the shape VAE) and the texture pipeline (the delighting model and the
multiview diffusion model, both diffusers pipelines, and the differentiable
renderer) -- what gpu_service/services/hunyuan3d_backend.py did, under
ComfyUI's memory management (_card). Every torch module of both pipelines
is held in one container, so the station is one model to ComfyUI; the
pipeline objects keep pointing at the modules and are told the device
before every generation.

The weights are folders under <ComfyUI>/models/hunyuan3d/<dir>/ laid out
the way the tencent/Hunyuan3D-2 repository is: hunyuan3d-dit-v2-0/
(config.yaml, model.fp16.safetensors), hunyuan3d-delight-v2-0/ and
hunyuan3d-paint-v2-0/ (diffusers folders). The background remover (rembg,
u2net) reads its ONNX session from ~/.u2net, as it did in the GPU service.
"""
import io
import logging
import os
import time
from typing import Any, Dict

import torch

from . import _card, _whole

logger = logging.getLogger(__name__)

FOLDER_NAME = "hunyuan3d"
KEEP_BUILT = 1
SHAPE_SUBFOLDER = _whole.HUNYUAN3D_SHAPE_SUBFOLDER
DELIGHT_SUBFOLDER = _whole.HUNYUAN3D_DELIGHT_SUBFOLDER
PAINT_SUBFOLDER = _whole.HUNYUAN3D_PAINT_SUBFOLDER
# The GPU service requested 16 000 MB from its coordinator for the station,
# weights included; the renders at 2048 px and the multiview diffusion are
# what the reserve covers beyond the weights.
RESERVE_BYTES = 8 * 1024 ** 3

_card.register_folder(FOLDER_NAME)
_registry = _card.Registry("Hunyuan3D", KEEP_BUILT)


def whole(path: str) -> bool:
    return _whole.whole("hunyuan3d", path)


def installed_dirs():
    return _card.listed_dirs(FOLDER_NAME, whole)


def weights_path(dir_name: str) -> str:
    return _card.folder_path(FOLDER_NAME, dir_name, whole)


_WEIGHT_SUFFIXES = (".safetensors", ".bin", ".ckpt", ".pth")


def weight_bytes(path: str) -> int:
    """The bytes the build reads: the fp16 safetensors of the shape model, and
    of the two diffusers folders every weights file, a .bin or .ckpt only
    where no .safetensors of the same name stands beside it (diffusers takes
    the safetensors then). A folder that holds the whole repository, every
    variant and both formats, is counted as what is loaded from it."""
    total = os.path.getsize(os.path.join(path, SHAPE_SUBFOLDER, "model.fp16.safetensors"))
    for sub in (DELIGHT_SUBFOLDER, PAINT_SUBFOLDER):
        for root, _dirs, files in os.walk(os.path.join(path, sub)):
            for f in files:
                stem, ext = os.path.splitext(f)
                if ext not in _WEIGHT_SUFFIXES:
                    continue
                if ext != ".safetensors" and stem + ".safetensors" in files:
                    continue
                total += os.path.getsize(os.path.join(root, f))
    return total


def _modules_of(pipeline) -> Dict[str, torch.nn.Module]:
    """The torch modules of a diffusers pipeline, by component name."""
    return {name: m for name, m in pipeline.components.items() if isinstance(m, torch.nn.Module)}


def _build(dir_name: str) -> Any:
    from hy3dgen.rembg import BackgroundRemover
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
    from hy3dgen.texgen import Hunyuan3DPaintPipeline
    from hy3dgen.texgen.pipelines import Hunyuan3DTexGenConfig

    path = weights_path(dir_name)
    logger.info(f"[AI4ArtsEd Hunyuan3D] Building {dir_name} from {path}")
    cpu = torch.device("cpu")
    shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        path, subfolder=SHAPE_SUBFOLDER, dtype=torch.float16, device=cpu)
    config = Hunyuan3DTexGenConfig(os.path.join(path, DELIGHT_SUBFOLDER), os.path.join(path, PAINT_SUBFOLDER))
    config.device = cpu
    texture_pipe = Hunyuan3DPaintPipeline(config)
    modules: Dict[str, torch.nn.Module] = {
        "shape_model": shape_pipe.model,
        "shape_vae": shape_pipe.vae,
        "shape_conditioner": shape_pipe.conditioner,
    }
    for prefix, sub in (("delight", texture_pipe.models["delight_model"]),
                        ("multiview", texture_pipe.models["multiview_model"])):
        for name, m in _modules_of(sub.pipeline).items():
            modules[f"{prefix}_{name}"] = m
    container = _card.Container(**modules)
    return _card.Held(key=dir_name, patcher=_card.wrap(container), module=container,
                      weight_bytes=_card.module_bytes(container),
                      extra={"shape": shape_pipe, "texture": texture_pipe, "rembg": BackgroundRemover()})


def get_built(dir_name: str) -> Any:
    return _registry.get(dir_name, _build, weight_bytes(weights_path(dir_name)))


def _on_device(held: Any, device: torch.device) -> None:
    """Tell the pipeline objects the device their modules are on."""
    held.extra["shape"].to(device)
    texture = held.extra["texture"]
    texture.config.device = device
    for sub in texture.models.values():
        sub.device = device
    if hasattr(texture.render, "device"):
        texture.render.device = device


def generate(dir_name: str, image, seed: int = 0, num_inference_steps: int = 50,
             guidance_scale: float = 7.5, octree_resolution: int = 256) -> Dict[str, Any]:
    """A GLB from a PIL image (RGBA): {glb (bytes), size_bytes, seed,
    generation_time_ms}. Background removal first (rembg), as Hunyuan3D-2
    wants it; a failure there is logged and the picture used as it is."""
    t_start = time.time()
    held = get_built(dir_name)
    with held.lock:
        device = _card.on_card(held, RESERVE_BYTES, held.key)
        _on_device(held, device)
        image = image.convert("RGBA")
        try:
            image = held.extra["rembg"](image)
            logger.info("[AI4ArtsEd Hunyuan3D] Background removed")
        except Exception as e:
            logger.warning(f"[AI4ArtsEd Hunyuan3D] Background removal failed, using original: {e}")
        generator = torch.Generator(device=device).manual_seed(seed)
        logger.info(f"[AI4ArtsEd Hunyuan3D] Generating: steps={num_inference_steps}, "
                    f"cfg={guidance_scale}, octree={octree_resolution}, seed={seed}")
        _card.interrupted()
        with torch.no_grad():
            mesh = held.extra["shape"](
                image=image,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
                octree_resolution=octree_resolution,
            )[0]
        _card.interrupted()
        with torch.no_grad():
            textured_mesh = held.extra["texture"](mesh, image=image)
        buf = io.BytesIO()
        textured_mesh.export(buf, file_type="glb")
        glb = buf.getvalue()
    logger.info(f"[AI4ArtsEd Hunyuan3D] Mesh generated: {len(glb)} bytes (seed={seed})")
    return {
        "glb": glb,
        "size_bytes": len(glb),
        "seed": seed,
        "generation_time_ms": int((time.time() - t_start) * 1000),
    }
