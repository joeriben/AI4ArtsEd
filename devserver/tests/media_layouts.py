"""The smallest folder each media station accepts as a whole model, for the
tests of the table (test_local_media_weights) and of the installer
(test_local_media_install): what comfyui_nodes/ai4artsed_comfyui/_whole.py
asks for, written as empty files under a folder of the test's choosing. A
config that the check reads is written with the content it reads."""
import json
from pathlib import Path

# Per station: the files, relative to the weights folder, and for a JSON
# file the object to write (None writes a few zero bytes). The mmaudio
# layout is for a 44 k variant; the folder has to be named like one.
LAYOUTS = {
    "stable_audio": [
        ("model_config.json", {"model": {"conditioning": {"configs": [
            {"id": "prompt", "type": "t5", "config": {"subfolder": "t5gemma-b-b-ul2"}}]}}}),
        ("model.safetensors", None),
        ("t5gemma-b-b-ul2/config.json", {}),
        ("t5gemma-b-b-ul2/model.safetensors", None),
    ],
    "imagebind": [("imagebind_huge.pth", None)],
    "mmaudio": [
        ("weights/mmaudio_large_44k_v2.pth", None),
        ("ext_weights/v1-44.pth", None),
        ("ext_weights/synchformer_state_dict.pth", None),
    ],
    "heartmula": [
        ("tokenizer.json", {}),
        ("gen_config.json", {}),
        ("HeartMuLa-oss-3B/config.json", {}),
        ("HeartMuLa-oss-3B/model.safetensors", None),
        ("HeartCodec-oss/config.json", {}),
        ("HeartCodec-oss/model.safetensors", None),
    ],
    "hunyuan3d": [
        ("hunyuan3d-dit-v2-0/config.yaml", None),
        ("hunyuan3d-dit-v2-0/model.fp16.safetensors", None),
        ("hunyuan3d-delight-v2-0/model_index.json", {}),
        ("hunyuan3d-delight-v2-0/unet/diffusion_pytorch_model.safetensors", None),
        ("hunyuan3d-delight-v2-0/vae/diffusion_pytorch_model.safetensors", None),
        ("hunyuan3d-delight-v2-0/text_encoder/model.safetensors", None),
        ("hunyuan3d-paint-v2-0/model_index.json", {}),
        ("hunyuan3d-paint-v2-0/unet/diffusion_pytorch_model.safetensors", None),
        ("hunyuan3d-paint-v2-0/vae/diffusion_pytorch_model.safetensors", None),
        ("hunyuan3d-paint-v2-0/text_encoder/pytorch_model.bin", None),
    ],
    "media_reading": [("config.json", {}), ("model.safetensors", None)],
}


def files_of(station):
    return [rel for rel, _content in LAYOUTS[station]]


def write_file(folder, rel, content=None, size=64):
    path = Path(folder, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    if content is not None:
        path.write_text(json.dumps(content))
    else:
        path.write_bytes(b"\0" * size)


def write_whole(station, folder, leave_out=()):
    """Write the station's whole layout under `folder`, minus `leave_out`."""
    for rel, content in LAYOUTS[station]:
        if rel not in leave_out:
            write_file(folder, rel, content)
