"""Files in and out of the media stations' nodes.

Out: a generated sound or mesh is written to ComfyUI's temp directory and
announced in the node's ui output the way PreviewAudio announces a preview
({"audio": [{"filename", "subfolder", "type": "temp"}]}); the DevServer fetches
what a run announced from /view (comfyui_ws_client.ANNOUNCED_FILES) and the
node's other ui values carry the numbers beside it.

In: a recording or a picture the DevServer hands over lives in ComfyUI's
input directory, put there through /upload/image, and is named by its file
name; a picture may also come as base64 text or as an IMAGE tensor of a
workflow (_local_llm._pil_images reads all three).
"""
import io
import os
import random
import string
from typing import Any, Dict, Optional

import folder_paths

from ._local_llm import _pil_images


def announce(data: bytes, suffix: str, prefix: str = "ai4artsed") -> Dict[str, Any]:
    """Write `data` to a fresh file of the temp directory and return the
    announcement of it. The suffix carries the dot (".wav", ".glb")."""
    stem = f"{prefix}_temp_{''.join(random.choice(string.ascii_lowercase) for _ in range(5))}"
    full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
        stem, folder_paths.get_temp_directory())
    name = f"{filename}_{counter:05}_{suffix}"
    with open(os.path.join(full_output_folder, name), "wb") as f:
        f.write(data)
    return {"filename": name, "subfolder": subfolder, "type": "temp"}


def input_path(filename: str) -> str:
    """The file of that name in ComfyUI's input directory, or an error that
    names it. A name with a path in it is refused: the input directory is
    the only place a node reads a handed-over file from."""
    if not filename or os.path.basename(filename) != filename or " [" in filename:
        # get_annotated_filepath reads a "name [output]" suffix as a folder
        # to look in; the only folder a node reads from is the input one.
        raise ValueError(f"a file name of the input directory is required, not {filename!r}")
    path = folder_paths.get_annotated_filepath(filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no file {filename!r} in ComfyUI's input directory")
    return path


def pil_image(image_base64: str = "", image: Any = None, mode: str = "RGB"):
    """One PIL image from the base64 text, else from the IMAGE tensor; None
    when neither is there. `mode` is what the station reads: Hunyuan3D reads
    RGBA, and a picture handed over with an alpha channel keeps it."""
    if image_base64 and image_base64.strip():
        import base64
        from PIL import Image
        text = image_base64.strip()
        try:
            raw = base64.b64decode(text.split(",", 1)[1] if text.startswith("data:") else text, validate=True)
        except (ValueError, IndexError) as e:
            raise ValueError(f"image_base64 is not base64 ({e})") from None
        try:
            return Image.open(io.BytesIO(raw)).convert(mode)
        except Exception as e:
            raise ValueError(f"image_base64 decodes to no picture PIL can open ({e})") from None
    if image is not None:
        return _pil_images([image])[0].convert(mode)
    return None



def wav_bytes(audio, sample_rate: int) -> bytes:
    """A WAV of a float tensor [channels, samples] on the CPU (soundfile
    writes [samples, channels])."""
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio.numpy().T, sample_rate, format="WAV")
    return buf.getvalue()


def mp3_bytes(audio, sample_rate: int) -> bytes:
    """An MP3 at 192 kbit/s of the same tensor, through pydub (ffmpeg)."""
    from pydub import AudioSegment
    wav = wav_bytes(audio, sample_rate)
    seg = AudioSegment.from_file(io.BytesIO(wav), format="wav")
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="192k")
    return buf.getvalue()


def encoded(audio, sample_rate: int, output_format: str) -> bytes:
    if output_format == "mp3":
        return mp3_bytes(audio, sample_rate)
    return wav_bytes(audio, sample_rate)



def json_input(text: str, what: str, default: Optional[Any] = None) -> Any:
    """A JSON input of a node, `default` when it is blank."""
    import json
    if text is None or not str(text).strip():
        return default
    try:
        return json.loads(text)
    except ValueError as e:
        raise ValueError(f"{what} is not JSON: {e}") from e
