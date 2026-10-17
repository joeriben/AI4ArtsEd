"""A reading of a recording, a video or a picture, as a ComfyUI node.

The DevServer's media analysis client (my_app/services/
media_analysis_client.py) queues one prompt of this node per reading: the
file was put into ComfyUI's input directory through /upload/image and is
named here. The task says which reader runs (audio: the chat model that
hears; image and video: the local Qwen3-VL from models/llm; lyrics: the
transcriber; music_tags: a ranking of the labels), and the prompts, the
labels and the trust_remote_code flag come from the DevServer's table.
Everything that holds the models is in _media_reading.py.
"""
import json
import time

from . import _local_llm, _media_files, _media_reading

TASKS = ["audio", "image", "video", "lyrics", "music_tags"]


class ai4artsed_media_reading:
    @classmethod
    def INPUT_TYPES(cls):
        # The readers under models/media_reading and the language models
        # under models/llm (image, video), one list.
        dirs = _media_reading.installed_dirs() + [d for d in _local_llm.installed_dirs()
                                                  if d not in _media_reading.installed_dirs()]
        return {
            "required": {
                "task": (TASKS, {"default": "audio"}),
                "model_name": (dirs or ["(no reader under models/media_reading)"],),
                # The file's name in ComfyUI's input directory.
                "file": ("STRING", {"default": ""}),
            },
            "optional": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "system_prompt": ("STRING", {"multiline": True, "default": ""}),
                # lyrics: the language to transcribe in; blank = detected
                "language": ("STRING", {"default": ""}),
                # music_tags: the labels to rank, a JSON list of strings
                "labels": ("STRING", {"multiline": True, "default": ""}),
                "center": ("BOOLEAN", {"default": False}),
                # audio: whether the checkpoint's own modelling code may run
                "trust_remote_code": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Run every time it is queued: a reading asked for is a reading
        # made, and ComfyUI would otherwise answer a file of the same name
        # from its cache after the file was replaced.
        return float("nan")

    def run(self, task, model_name, file, prompt="", system_prompt="", language="", labels="",
            center=False, trust_remote_code=False):
        start = time.time()
        path = _media_files.input_path(file)
        ui = {"model": [model_name], "task": [task]}
        if task == "audio":
            text = _media_reading.describe_audio(model_name, path, prompt, system_prompt,
                                                 trust_remote_code=bool(trust_remote_code))
            ui["analysis"] = [text]
        elif task == "image":
            text = _media_reading.describe_image(model_name, path, prompt)
            ui["analysis"] = [text]
        elif task == "video":
            text = _media_reading.describe_video(model_name, path, prompt)
            ui["analysis"] = [text]
        elif task == "lyrics":
            out = _media_reading.transcribe(model_name, path, language=language or None)
            text = out["text"]
            ui["text"] = [text]
            ui["language"] = [out["language"] or ""]
        elif task == "music_tags":
            label_list = _media_files.json_input(labels, "labels", [])
            if not isinstance(label_list, list):
                raise ValueError("labels has to be a JSON list of strings")
            tags = _media_reading.tag_music(model_name, path, label_list, center=bool(center))
            text = json.dumps(tags)
            ui["tags"] = [text]
            ui["vocabulary_size"] = [len(label_list)]
            ui["centered"] = [bool(center)]
        else:
            raise ValueError(f"unknown task {task!r}")
        ui["duration_ms"] = [_media_reading.read_time_ms(start)]
        return {"ui": ui, "result": (text,)}
