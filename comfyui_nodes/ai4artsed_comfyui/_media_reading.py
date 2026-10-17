"""The readers of media (media -> text), run by ComfyUI.

What gpu_service/services/media_analysis_backend.py did, under ComfyUI's
memory management (_card): a description of a recording (MiDashengLM, a
chat model that hears), of a video or a still (Qwen3-VL through the
platform's local language models, _local_llm), the words the transcriber
believes were sung or spoken (HeartTranscriptor, a Whisper fine-tune,
through heartlib's pipeline class), and a ranking of English labels against
a recording (MuQ-MuLan and CLAP, cosine in a joint music/text space).

The weights are folders under <ComfyUI>/models/media_reading/<dir>/ --
transformers-style snapshots (config.json and the weights) -- except the
video and image reader, which is a folder under models/llm/ like every
local language model. Which folder is which reader, the prompts, the label
vocabulary and whether a checkpoint's own code may run (trust_remote_code,
MiDashengLM) are the DevServer's table (devserver/config/
local_media_weights.json); the node is handed the folder, the prompt, the
labels and the flag, and reads what the folder's config says the model is.

Torchcodec: qwen-vl-utils would read a video through it where the package
is present, and transformers' ASR pipeline probes for it; both are told to
read decoded arrays through the torchvision reader and librosa instead, as
the GPU service told them.
"""
import functools
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# Before qwen_vl_utils is imported anywhere in this process.
os.environ.setdefault("FORCE_QWENVL_VIDEO_READER", "torchvision")

import torch  # noqa: E402

from . import _card, _local_llm, _whole  # noqa: E402
from ._repetition_guard import RepetitionGuard  # noqa: E402

logger = logging.getLogger(__name__)

FOLDER_NAME = "media_reading"
KEEP_BUILT = 3

# MuQ-MuLan's audio encoder is trained at 24 kHz; CLAP's audio tower at 48 kHz.
MUQ_SAMPLE_RATE = 24000
CLAP_SAMPLE_RATE = 48000
# CLAP takes ten seconds at a time, and this checkpoint throws the rest
# away (its preprocessor_config.json says truncation="rand_trunc" and
# nb_max_samples 480000: handed a longer recording it keeps ONE random
# ten-second crop, and the same recording came back with a different top
# label between two identical calls). So the windows are cut here, spaced
# evenly across the whole recording, each exactly one window long.
CLAP_WINDOW_SAMPLES = 480000
CLAP_WINDOW_BATCH = 16
# Above this the windows are spread more thinly rather than the recording
# being cut short, and the thinning is logged.
CLAP_MAX_WINDOWS = 64

# Whisper's own generation_config stops at 448, which is the model's
# context; the chat readers run to the platform's ceiling, or to the
# model's own positions where those are fewer (_window).
GENERATION_TOKEN_CEILING = _local_llm.DEFAULT_CONTEXT_TOKENS

# Reserves per reader beyond the weights: gpu_config's estimated_vram_mb of
# each less what its weights weigh.
AUDIO_RESERVE_BYTES = 3 * 1024 ** 3      # MiDashengLM: the audio encoder and the answer
VIDEO_RESERVE_BYTES = 8 * 1024 ** 3      # Qwen3-VL: the frames' vision tokens
IMAGE_RESERVE_BYTES = _local_llm.VISION_RESERVE_BYTES
LYRICS_RESERVE_BYTES = 2 * 1024 ** 3
TAGGER_RESERVE_BYTES = 2 * 1024 ** 3

_card.register_folder(FOLDER_NAME)
_registry = _card.Registry("MediaReading", KEEP_BUILT)


# ---------------------------------------------------------------------------
# The folders.

def whole(path: str) -> bool:
    """A transformers-style snapshot: config.json, no part in flight, the
    weights (the shards the index names, else a safetensors or a
    pytorch_model.bin file: MuQ-MuLan and CLAP are published as .bin), as
    _whole.media_reading defines it for both sides."""
    return _whole.whole("media_reading", path)


def installed_dirs() -> List[str]:
    return _card.listed_dirs(FOLDER_NAME, whole)


def weights_path(dir_name: str) -> str:
    return _card.folder_path(FOLDER_NAME, dir_name, whole)


def model_type(path: str) -> str:
    import json
    try:
        with open(os.path.join(path, "config.json")) as f:
            return str(json.load(f).get("model_type", ""))
    except (OSError, ValueError):
        return ""


# ---------------------------------------------------------------------------
# The readers.

# Modules of the audio describer's own modelling code whose non-persistent
# buffers are computed in __init__: the audio front end's spectrogram window
# and mel filterbank. transformers 5 builds a model on the meta device and,
# once the weights are in, replaces every non-persistent buffer by an
# uninitialised tensor (_move_missing_keys_from_meta_to_device), counting on
# _init_weights to fill it, which only its own modules do. Two things follow
# for such a module: its __init__ has to run on a real device, since the
# filterbank's check calls .any() on the tensor, which a meta tensor refuses;
# and its buffers have to be computed again after loading. Both are done
# below by the module's own __init__, on the CPU and in float32, which is
# what the front end's forward casts them to.
INIT_BUFFER_MODULES = ("DashengFrontend",)


def _on_cpu(init):
    """The module's __init__, its tensors made on the CPU whatever device
    context the caller holds (transformers' is the meta device)."""
    @functools.wraps(init)
    def wrapped(self, *args, **kwargs):
        with torch.device("cpu"):
            init(self, *args, **kwargs)
    wrapped._ai4artsed_on_cpu = True
    return wrapped


def _init_buffer_classes(path: str, trust_remote_code: bool) -> List[type]:
    """The INIT_BUFFER_MODULES classes out of the checkpoint's own modelling
    code (the module its config's auto_map names), those that exist there.
    The class object is the one from_pretrained builds with: the dynamic
    module is imported once per file and kept in sys.modules."""
    if not trust_remote_code:
        return []
    from transformers import AutoConfig
    from transformers.dynamic_module_utils import get_class_from_dynamic_module
    config = AutoConfig.from_pretrained(path, trust_remote_code=True)
    reference = (getattr(config, "auto_map", None) or {}).get("AutoModelForCausalLM", "")
    module_name = reference.split(".")[0] if "." in reference else ""
    if not module_name:
        return []
    classes = []
    for name in INIT_BUFFER_MODULES:
        try:
            classes.append(get_class_from_dynamic_module(f"{module_name}.{name}", path))
        except AttributeError:
            pass
    return classes


def _rebuild_init_buffers(model: torch.nn.Module) -> int:
    """The non-persistent buffers of every INIT_BUFFER_MODULES module in the
    model computed afresh: a new instance from the module's config, on the
    CPU in float32, its buffers registered in place of the loaded ones.
    Returns how many modules were rebuilt."""
    count = 0
    default = torch.get_default_dtype()
    torch.set_default_dtype(torch.float32)
    try:
        for mod in model.modules():
            if type(mod).__name__ not in INIT_BUFFER_MODULES:
                continue
            with torch.device("cpu"):
                fresh = type(mod)(mod.config)
            for name, buf in fresh.named_buffers(recurse=False):
                mod.register_buffer(name, buf, persistent=name not in fresh._non_persistent_buffers_set)
            count += 1
    finally:
        torch.set_default_dtype(default)
    return count


def _build_audio_chat(dir_name: str, trust_remote_code: bool):
    """MiDashengLM: a causal LM with an audio encoder, in bfloat16. Its
    modelling code ships in the snapshot; trust_remote_code is the table's
    word, handed in by the DevServer."""
    def build(key: str) -> Any:
        from transformers import AutoModelForCausalLM, AutoProcessor
        path = weights_path(dir_name)
        logger.info(f"[AI4ArtsEd MediaReading] Building {dir_name} ({model_type(path)}, "
                    f"trust_remote_code={trust_remote_code}) from {path}")
        processor = AutoProcessor.from_pretrained(path, trust_remote_code=trust_remote_code)
        for cls in _init_buffer_classes(path, trust_remote_code):
            if not getattr(cls.__init__, "_ai4artsed_on_cpu", False):
                cls.__init__ = _on_cpu(cls.__init__)
        model = AutoModelForCausalLM.from_pretrained(path, trust_remote_code=trust_remote_code,
                                                     dtype=torch.bfloat16, low_cpu_mem_usage=True).eval()
        rebuilt = _rebuild_init_buffers(model)
        logger.info(f"[AI4ArtsEd MediaReading] {dir_name}: init-time buffers rebuilt in {rebuilt} module(s)")
        container = _card.Container(hf=model)
        return _card.Held(key=key, patcher=_card.wrap(container), module=container,
                          weight_bytes=_card.module_bytes(container), extra={"processor": processor})
    return build


def _build_transcriber(dir_name: str):
    """HeartTranscriptor: heartlib's pipeline class over the Whisper
    checkpoint, the way its from_pretrained builds it (the folder resolved
    here, since it is the model's own folder rather than a heartlib
    checkpoint tree), in float16."""
    def build(key: str) -> Any:
        import transformers.pipelines.automatic_speech_recognition as _asr
        _asr.is_torchcodec_available = lambda: False
        from heartlib import HeartTranscriptorPipeline
        from transformers.models.whisper.modeling_whisper import WhisperForConditionalGeneration
        from transformers.models.whisper.processing_whisper import WhisperProcessor
        path = weights_path(dir_name)
        logger.info(f"[AI4ArtsEd MediaReading] Building {dir_name} (transcriber) from {path}")
        model = WhisperForConditionalGeneration.from_pretrained(path, torch_dtype=torch.float16,
                                                                low_cpu_mem_usage=True)
        processor = WhisperProcessor.from_pretrained(path)
        pipe = HeartTranscriptorPipeline(
            model=model, tokenizer=processor.tokenizer, feature_extractor=processor.feature_extractor,
            device=torch.device("cpu"), dtype=torch.float16, chunk_length_s=30, batch_size=16)
        container = _card.Container(hf=pipe.model)
        return _card.Held(key=key, patcher=_card.wrap(container), module=container,
                          weight_bytes=_card.module_bytes(container), extra={"pipe": pipe})
    return build


def _build_tagger(dir_name: str):
    """CLAP (transformers) or MuQ-MuLan (muq), by the folder's model_type."""
    def build(key: str) -> Any:
        path = weights_path(dir_name)
        kind = model_type(path)
        logger.info(f"[AI4ArtsEd MediaReading] Building {dir_name} ({kind or 'muq-mulan'}) from {path}")
        if kind == "clap":
            from transformers import ClapModel, ClapProcessor
            processor = ClapProcessor.from_pretrained(path)
            model = ClapModel.from_pretrained(path).eval()
            extra = {"kind": "clap", "processor": processor}
        else:
            model = _muq_from_dir(path).eval().half()
            _name_attention(model)
            _collect_layer_states(model)
            extra = {"kind": "muq"}
        container = _card.Container(hf=model)
        return _card.Held(key=key, patcher=_card.wrap(container), module=container,
                          weight_bytes=_card.module_bytes(container), extra=extra)
    return build


def _name_attention(model: torch.nn.Module) -> int:
    """Give MuQ's conformer the attention implementation transformers asks for.

    muq builds transformers' Wav2Vec2ConformerEncoder on an EasyDict instead of
    a PretrainedConfig (muq/muq/models/muq_model.py), and the EasyDict has no
    `_attn_implementation`. transformers 5.17 reads that attribute on every
    forward pass (masking_utils._preprocess_mask_arguments and the conformer's
    self-attention), so every MuQ-MuLan reading ended in an AttributeError.
    "eager" is the conformer's own plain-PyTorch attention
    (modeling_wav2vec2_conformer.eager_attention_forward), which that file keeps
    equivalent to the original conformer implementation, the plain matmul
    attention transformers 4.57 ran. The venv is left as it is; only the config
    objects of this one model are completed (the conformer's and MuQ-MuLan's
    own, both EasyDicts). Returns how many config objects were completed.
    """
    done = 0
    seen = set()
    for module in model.modules():
        cfg = getattr(module, "config", None)
        # EasyDict is a dict subclass that takes attributes; a plain dict
        # would not, and a PretrainedConfig carries the attribute already.
        if isinstance(cfg, dict) and type(cfg) is not dict and id(cfg) not in seen:
            seen.add(id(cfg))
            if "_attn_implementation" not in cfg:
                cfg._attn_implementation = "eager"
                done += 1
    return done


def _collect_layer_states(model: torch.nn.Module) -> int:
    """Give MuQ's conformer back the per-layer states muq reads.

    muq asks the conformer for output_hidden_states=True and reads
    out["hidden_states"] (muq/muq/models/muq_model.py, MuQModel.encoder);
    MuQ-MuLan takes the last entry, the output of the final layer_norm, as the
    input of its embedding head (muq_mulan/models/audio.py). transformers
    5.17's Wav2Vec2ConformerEncoder returns last_hidden_state alone, so once
    the attention is named, every reading would end in a KeyError. The hooks
    rebuild the tuple the way the encoder built
    it before (transformers 4.57): the input of every layer, then the output of
    the final layer_norm. The forward pass itself stays the library's. Returns
    how many encoders were given the hooks.
    """
    from transformers.models.wav2vec2_conformer.modeling_wav2vec2_conformer import (
        Wav2Vec2ConformerEncoder,
    )
    done = 0
    for module in model.modules():
        if not isinstance(module, Wav2Vec2ConformerEncoder):
            continue
        states: List[torch.Tensor] = []
        wanted = [False]

        def begin(_mod, _args, kwargs, states=states, wanted=wanted):
            states.clear()
            wanted[0] = bool(kwargs.get("output_hidden_states"))

        def layer_input(_mod, args, kwargs, states=states, wanted=wanted):
            if wanted[0]:
                states.append(args[0] if args else kwargs["hidden_states"])

        def end(_mod, _args, _kwargs, out, states=states, wanted=wanted):
            if wanted[0] and out.get("hidden_states") is None:
                out["hidden_states"] = tuple(states) + (out.last_hidden_state,)
            states.clear()
            return out

        module.register_forward_pre_hook(begin, with_kwargs=True)
        for layer in module.layers:
            layer.register_forward_pre_hook(layer_input, with_kwargs=True)
        module.register_forward_hook(end, with_kwargs=True)
        done += 1
    return done


def _muq_from_dir(path: str):
    """MuQ-MuLan off its folder: config.json next to model.safetensors or,
    as the published checkpoint ships it, pytorch_model.bin. The hub mixin
    reads only the safetensors file off a folder and looks for the .bin
    on the hub alone, so the .bin is read here the way the mixin reads it
    there. The sub-models the config names (the MuQ audio transformer, the
    text transformer) come out of the Hugging Face cache either way."""
    from muq import MuQMuLan
    if os.path.isfile(os.path.join(path, "model.safetensors")):
        return MuQMuLan.from_pretrained(path)
    weights = os.path.join(path, "pytorch_model.bin")
    if not os.path.isfile(weights):
        raise FileNotFoundError(f"neither model.safetensors nor pytorch_model.bin under {path}")
    with open(os.path.join(path, "config.json")) as f:
        config = json.load(f)
    model = MuQMuLan(config)
    return MuQMuLan._load_as_pickle(model, weights, "cpu", False)


def _get(dir_name: str, build) -> Any:
    return _registry.get(dir_name, build, _card.bytes_of_files(weights_path(dir_name)))


# ---------------------------------------------------------------------------
# One answer off a chat reader.

def _window(config: Any) -> int:
    """The context the reader runs in: the platform's ceiling, or the
    model's own positions where its config states fewer (MiDashengLM's text
    decoder: 32 768)."""
    text = getattr(config, "text_config", None) or config
    positions = int(getattr(text, "max_position_embeddings", 0) or 0)
    return min(GENERATION_TOKEN_CEILING, positions) if positions else GENERATION_TOKEN_CEILING


def _answer(model: Any, tokenizer: Any, inputs: Dict[str, Any], window: int,
            prompt_len: int, seen_prompt_len: int, name: str,
            eos_ids: Optional[Tuple[int, ...]] = None) -> str:
    """One answer, taken the way _local_llm.generate takes one: streamed,
    so that the repetition guard stops a model that loops; a stopping
    criterion asked after every token (ComfyUI's interrupt, the guard); the
    room for the answer what the window leaves after the prompt.
    `seen_prompt_len` is what the criterion counts before the first new
    token: the prompt for a model whose generate returns the whole sequence
    (Qwen3-VL), 0 for one that returns the new tokens only (MiDashengLM).
    `eos_ids` are the tokens the generation stops at, where the caller holds
    them (Built.eos_ids: the generation config's and the tokenizer's
    end-of-turn token, which a Qwen 3.5 checkpoint's derived config leaves
    out); without them the model's own generation config decides."""
    from transformers import StoppingCriteriaList, TextIteratorStreamer
    if prompt_len >= window:
        raise ValueError(f"the prompt is {prompt_len} tokens and the window of {name} {window}; "
                         f"nothing is left for the answer")
    max_new = window - prompt_len
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    stop = _local_llm._Stop(seen_prompt_len)
    failure: List[BaseException] = []
    stop_at = {"eos_token_id": list(eos_ids)} if eos_ids else {}

    def run():
        try:
            with torch.inference_mode():
                model.generate(**inputs, max_new_tokens=max_new, streamer=streamer,
                               stopping_criteria=StoppingCriteriaList([stop]), **stop_at)
        except BaseException as e:      # handed to the reading thread below
            failure.append(e)
            streamer.end()

    _card.interrupted()
    worker = threading.Thread(target=run, name=f"ai4artsed-reader-{name}", daemon=True)
    worker.start()
    guard = RepetitionGuard()
    pieces: List[str] = []
    for piece in streamer:
        if not piece:
            continue
        pieces.append(piece)
        if guard.feed(piece):
            stop.repetition.set()
            logger.info(f"[AI4ArtsEd MediaReading] {name} repeated {guard.describe()} and was stopped")
    worker.join()
    if failure:
        raise failure[0]
    if stop.interrupted:
        _card.interrupted()
    if stop.generated >= max_new:
        logger.warning(f"[AI4ArtsEd MediaReading] {name} ran to the end of its window ({max_new} new tokens)")
    return "".join(pieces).strip()


# ---------------------------------------------------------------------------
# audio

def describe_audio(dir_name: str, path: str, prompt: str, system_prompt: str,
                   trust_remote_code: bool = False) -> str:
    """A description of the recording, in the words of the chat model that
    hears it. The recording is decoded with librosa and handed to the
    processor as an array."""
    import librosa
    held = _get(dir_name, _build_audio_chat(dir_name, trust_remote_code))
    wav, sampling_rate = librosa.load(path, sr=None, mono=True)
    messages = [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "audio", "audio": wav, "sampling_rate": sampling_rate},
        ]},
    ]
    with held.lock:
        model, processor = held.module.hf, held.extra["processor"]
        window = _window(model.config)
        device = _card.on_card(held, AUDIO_RESERVE_BYTES + _local_llm._kv_cache_bytes(model.config, window),
                               held.key)
        inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                               add_special_tokens=True, return_dict=True)
        # Per the model card: tensors to the device, floating tensors to bf16.
        inputs = inputs.to(device=device, dtype=model.dtype)
        # MiDashengLM's generate runs its decoder on inputs_embeds: the
        # sequence the stopping criterion sees, and the one returned, holds
        # the new tokens only, so the prompt counts as 0 there and its length
        # is taken off the window here.
        prompt_len = int(inputs["input_ids"].shape[1])
        return _answer(model, processor.tokenizer, dict(inputs), window, prompt_len, 0, held.key)


# ---------------------------------------------------------------------------
# image, video

def _describe_visual(llm_dir: str, content: List[dict], reserve: int, video: bool) -> str:
    from qwen_vl_utils import process_vision_info
    built = _local_llm.get_built(llm_dir)
    messages = [{"role": "user", "content": content}]
    with built.lock:
        window = _window(built.config)
        device = _local_llm._on_card(built, reserve + _local_llm._kv_cache_bytes(built.config, window))
        model, processor = built.module.hf, built.processor
        text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        if video:
            images, videos, video_kwargs = process_vision_info(
                messages, image_patch_size=16, return_video_kwargs=True, return_video_metadata=True)
            if videos is not None:
                videos, metadatas = zip(*videos)
                videos, metadatas = list(videos), list(metadatas)
            else:
                metadatas = None
            inputs = processor(text=[text_prompt], images=images, videos=videos, video_metadata=metadatas,
                               do_resize=False, return_tensors="pt", **video_kwargs)
        else:
            images, _videos = process_vision_info(messages, image_patch_size=16)
            inputs = processor(text=[text_prompt], images=images, return_tensors="pt")
        inputs = inputs.to(device)
        prompt_len = int(inputs["input_ids"].shape[1])
        return _answer(model, built.tokenizer, dict(inputs), window, prompt_len, prompt_len, llm_dir,
                       eos_ids=built.eos_ids)


def describe_image(llm_dir: str, path: str, prompt: str) -> str:
    return _describe_visual(llm_dir, [{"type": "image", "image": "file://" + path},
                                      {"type": "text", "text": prompt}], IMAGE_RESERVE_BYTES, video=False)


def describe_video(llm_dir: str, path: str, prompt: str) -> str:
    return _describe_visual(llm_dir, [{"type": "video", "video": "file://" + path},
                                      {"type": "text", "text": prompt}], VIDEO_RESERVE_BYTES, video=True)


# ---------------------------------------------------------------------------
# lyrics

def transcribe(dir_name: str, path: str, language: Optional[str] = None) -> Dict[str, Any]:
    """The words the model believes were sung or spoken, and in what language:
    {"text", "language"}. On input that has no words in it the model tends
    to produce a short, fluent, confident sentence, and the language it
    decided on first is invented like the rest; both are returned as they
    are, for the caller to qualify."""
    import librosa
    held = _get(dir_name, _build_transcriber(dir_name))
    pipe = held.extra["pipe"]
    sampling_rate = pipe.feature_extractor.sampling_rate
    wav, _ = librosa.load(path, sr=sampling_rate, mono=True)
    kwargs: Dict[str, Any] = {
        "num_beams": 2,
        "task": "transcribe",
        "condition_on_prev_tokens": False,
        "compression_ratio_threshold": 1.8,
        "temperature": (0.0, 0.1, 0.2, 0.4),
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.4,
    }
    if language:
        kwargs["language"] = language
    with held.lock:
        device = _card.on_card(held, LYRICS_RESERVE_BYTES, held.key)
        pipe.device = device
        _card.interrupted()
        with torch.no_grad():
            result = pipe({"raw": wav, "sampling_rate": sampling_rate}, **kwargs)
            detected = language or _detect_language(pipe, wav, sampling_rate)
    return {"text": (result.get("text") or "").strip(), "language": detected}


def _detect_language(pipe, wav, sampling_rate) -> Optional[str]:
    """Which language the model decided it was hearing, as an English name:
    the decision generate makes internally when no language is given, asked
    for directly, off the first thirty seconds. Never raises: a missing
    language costs a line on the page, a raised one the transcription."""
    try:
        feats = pipe.feature_extractor(wav, sampling_rate=sampling_rate, return_tensors="pt") \
            .input_features.to(pipe.model.device, dtype=pipe.model.dtype)
        with torch.no_grad():
            ids = pipe.model.detect_language(input_features=feats)
        token = pipe.tokenizer.decode(ids[0], skip_special_tokens=False)
        match = re.search(r"<\|([a-z]{2,3})\|>", token)
        if not match:
            return None
        from transformers.models.whisper.tokenization_whisper import LANGUAGES
        code = match.group(1)
        return LANGUAGES.get(code, code)
    except Exception as e:
        logger.warning(f"[AI4ArtsEd MediaReading] Language detection failed: {e}")
        return None


# ---------------------------------------------------------------------------
# music tags

def _load_audio(kind: str, path: str):
    """Mono float32 at the model's rate, peak-normalised over the whole
    recording (CLAP's embedding is markedly gain-sensitive: the same window
    at 0.1x and at 4x embeds to cosine 0.742 and 0.898 of itself, while a
    different passage of the same recording reaches 0.808 at worst).
    Raises on an empty file or digital silence."""
    import librosa
    import numpy as np
    sr = MUQ_SAMPLE_RATE if kind == "muq" else CLAP_SAMPLE_RATE
    wav, _ = librosa.load(path, sr=sr, mono=True)
    if wav.size == 0:
        raise ValueError(f"no audio frames in {os.path.basename(path)}")
    peak = float(np.abs(wav).max())
    if peak <= 0.0:
        raise ValueError(f"digital silence in {os.path.basename(path)}")
    return (wav / peak).astype(np.float32)


def _window_starts(n_samples: int) -> List[int]:
    """Evenly spaced start offsets, every window exactly one window long:
    one window for anything at or below the window length, else enough to
    cover the recording, spread from the first sample to the last."""
    if n_samples <= CLAP_WINDOW_SAMPLES:
        return [0]
    wanted = -(-n_samples // CLAP_WINDOW_SAMPLES)  # ceil
    count = min(wanted, CLAP_MAX_WINDOWS)
    if wanted > CLAP_MAX_WINDOWS:
        logger.info(f"[AI4ArtsEd MediaReading] {n_samples / CLAP_SAMPLE_RATE:.0f}s of audio: "
                    f"sampling {count} windows spread across it instead of {wanted} consecutive ones")
    last = n_samples - CLAP_WINDOW_SAMPLES
    return [round(i * last / (count - 1)) for i in range(count)]


def _projected(features: Any) -> torch.Tensor:
    """The projected embedding off a CLAP feature call. transformers 4 hands
    the tensor back; transformers 5 hands back the encoder's output object
    with the projected, normalised embedding as its pooler_output."""
    return features.pooler_output if hasattr(features, "pooler_output") else features


def _embed_audio(held: Any, device: torch.device, wav):
    """Unit-norm audio embeddings, one row per window: (1, dim) for
    MuQ-MuLan, which takes the whole waveform, (n_windows, dim) for CLAP."""
    model = held.module.hf
    if held.extra["kind"] == "muq":
        emb = model(wavs=torch.tensor(wav, dtype=torch.float16, device=device)[None]).float()
        return emb / emb.norm(dim=-1, keepdim=True).clamp_min(1e-8)
    processor = held.extra["processor"]
    if model.training:
        logger.warning("[AI4ArtsEd MediaReading] CLAP was in train mode, forcing eval")
        model.eval()
    starts = _window_starts(len(wav))
    rows = []
    for i in range(0, len(starts), CLAP_WINDOW_BATCH):
        batch = [wav[s:s + CLAP_WINDOW_SAMPLES] for s in starts[i:i + CLAP_WINDOW_BATCH]]
        inputs = processor(audio=batch, sampling_rate=CLAP_SAMPLE_RATE, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        rows.append(_projected(model.get_audio_features(**inputs)).float())
    return torch.cat(rows, dim=0)


def _embed_labels(held: Any, device: torch.device, labels: List[str], center: bool):
    """L2-normalised text embeddings for the labels, optionally centered
    (the mean of this label set subtracted, then renormalised)."""
    model = held.module.hf
    if held.extra["kind"] == "muq":
        emb = model(texts=labels)
    else:
        processor = held.extra["processor"]
        inputs = processor(text=labels, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        emb = _projected(model.get_text_features(**inputs))
    emb = emb.float()
    emb = emb / emb.norm(dim=-1, keepdim=True).clamp_min(1e-8)
    if center and emb.shape[0] > 1:
        emb = emb - emb.mean(dim=0, keepdim=True)
        emb = emb / emb.norm(dim=-1, keepdim=True).clamp_min(1e-8)
    return emb


def tag_music(dir_name: str, path: str, labels: List[str], center: bool = False) -> List[Dict[str, Any]]:
    """The whole ranking of the labels against the recording, best first:
    [{"label", "score"}], the score the average over the windows of the
    cosine between window and label. There is no abstain: silence comes
    back ranked as confidently as a song."""
    held = _get(dir_name, _build_tagger(dir_name))
    label_list = [str(x) for x in labels]
    if not label_list:
        return []
    wav = _load_audio(held.extra["kind"], path)
    with held.lock:
        device = _card.on_card(held, TAGGER_RESERVE_BYTES, held.key)
        _card.interrupted()
        with torch.no_grad():
            audio_emb = _embed_audio(held, device, wav)
            text_emb = _embed_labels(held, device, label_list, center)
            scores_t = (audio_emb @ text_emb.T).mean(dim=0)
    if not torch.isfinite(scores_t).all():
        raise RuntimeError(f"non-finite scores from {dir_name}")
    scores = scores_t.cpu().tolist()
    ranked = sorted(zip(label_list, scores), key=lambda pair: -pair[1])
    return [{"label": label, "score": round(score, 4)} for label, score in ranked]


def read_time_ms(start: float) -> int:
    return int((time.time() - start) * 1000)
