"""A local language model run by ComfyUI's own implementation of it.

ComfyUI carries its own implementation of some language models
(comfy/text_encoders): it reads one safetensors file in ComfyUI's format
(mixed precision, MXFP8 or NVFP4, or the maker's bf16), holds the weights
under its own patcher, and generates with its own decode loop, for the
models that have one with the multi-token head (MTP). A model whose row in
devserver/config/local_llm_weights.json names such a file ("comfy_weights"),
and whose file is installed, answers here; every other model answers through
transformers (_local_llm.generate, which branches to this module). The call
and the answer are the same on both ways.

What stays the folder's: the chat template, the tokenizer and the generation
config are read from the Hugging Face folder under models/llm, as on the
transformers way. The tokens are made by that tokenizer and handed to
ComfyUI in its own structure; ComfyUI's tokenizer is not used, because it
rewrites the text on the way (sd1_clip.escape_important turns "\\(" and
"\\)" into placeholders).

Reading the tokens along (the stop list). ComfyUI's decode loops return the
whole answer at the end and offer no callback per token. Both of them fetch
the list of stop tokens from the model's config when none is handed in, and
ask `token in stop_tokens` once per token (comfy/text_encoders/llama.py,
BaseGenerate.generate; comfy/text_encoders/qwen35.py, _generate_mtp, in the
loop head and in a generator expression per step). For the length of one
generate this module puts a list of its own on that config (_Watch): it
answers the question the way the list did, and reads the token along while
it does. The stream, the repetition guard and the interruption hang on
that. A halt is answered as "this token is a stop token", and stays
answered. The original list is put back in `finally`.

That reading depends on where ComfyUI asks. Three things guard it:
  1. The tokens read along are compared with the tokens ComfyUI returns. A
     difference is logged as a warning, and the answer is made from the
     returned tokens.
  2. The ComfyUI version this was checked against is written down
     (PINNED_COMFYUI, docs/installation/SOFTWARE_VERSIONS.md). Another
     version is said in the log when the package is imported and at every
     load of a model on this way.
  3. devserver/tests/test_comfy_llm_stop_watch.py reads the three places in
     the installed ComfyUI and fails when they moved.

The card. ComfyUI books nothing for a generation of these models
(comfy/sd.py, CLIP.load_model asks the encoder's memory_estimation_function,
and this encoder has none). What a generation allocates is booked here,
before the first token (_reserve_bytes), and the call is refused by name
when the card lacks the room (_card.room_for).
"""
import json
import logging
import math
import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import torch

import comfy.model_management
import folder_paths

from . import _card
from ._repetition_guard import RepetitionGuard

logger = logging.getLogger(__name__)

# The ComfyUI release the reading along was checked against: the three
# places that ask `in stop_tokens`, and the caps of the two decode loops.
# The same version stands in docs/installation/SOFTWARE_VERSIONS.md, and
# test_comfy_llm_stop_watch.py holds the two together.
PINNED_COMFYUI = "0.44.2"

# ComfyUI's folder for the files this way reads.
WEIGHTS_FOLDER = "text_encoders"

# The names of the frames that ask the stop list about a token nobody asked
# about before, and of the one that asks again about the last token of the
# step before (the loop head of the MTP decode).
NEW_TOKEN_FRAMES = ("generate", "<genexpr>")
LOOP_HEAD_FRAME = "_generate_mtp"

# ComfyUI's MTP decode allocates its caches for prompt + max_length + 7
# positions (qwen35.py, _generate_mtp: cap).
MTP_EXTRA_POSITIONS = 7

# The working memory of the forward pass over the prompt, per prompt token
# and per unit of the model's width. Measured 10.11.2026 on the 27B (width
# 5120) with prompts of 54, 2,265 and 28,833 tokens: 0.35 to 0.39 MiB per
# token beside the caches, 69 to 81 bytes per token and unit of width; a
# picture's tokens cost the same as text (12,288 picture tokens: 0.36 MiB
# each). 112 is booked: the measured growth with the prompt's length,
# carried on to a prompt that fills the window, ends at about 93.
PREFILL_BYTES_PER_TOKEN_AND_WIDTH = 112

# Booked beside that for what does not grow with the prompt (the sampling
# buffers, the tables of the decode). Measured 10.11.2026 with a prompt of 28
# tokens and the full window: 57 MiB beside the caches and states in a run
# on resident weights, 103 MiB in the first run after the load.
FIXED_WORK_BYTES = 128 * 1024 * 1024


def comfyui_version() -> Optional[str]:
    try:
        import comfyui_version as v
        return str(v.__version__)
    except Exception:
        return None


def version_note() -> Optional[str]:
    """The sentence about a ComfyUI that is not the pinned one, or None."""
    found = comfyui_version()
    if found == PINNED_COMFYUI:
        return None
    return (f"ComfyUI is {found or 'of an unknown version'}; the local language models that run "
            f"on ComfyUI's own implementation read their tokens along through the stop list of "
            f"its decode loops, and that was checked against ComfyUI {PINNED_COMFYUI} "
            f"(docs/installation/SOFTWARE_VERSIONS.md). Run "
            f"devserver/tests/test_comfy_llm_stop_watch.py against this ComfyUI before relying "
            f"on the stream, the repetition guard and the interruption of these models")


_note = version_note()
if _note:
    logger.warning(f"[AI4ArtsEd LLM] {_note}")


# ---------------------------------------------------------------------------
# Which file a folder has.

def _table_file() -> Path:
    """devserver/config/local_llm_weights.json of this checkout (the package
    is linked into ComfyUI's custom_nodes from the repository, as
    _audio_synth._config_dir reads devserver/config)."""
    return Path(__file__).resolve().parents[2] / "devserver" / "config" / "local_llm_weights.json"


_table_cache: Dict[str, Any] = {"stamp": None, "by_dir": {}, "sampling": {}}
_said: set = set()


def _say_once(key: str, text: str) -> None:
    if key not in _said:
        _said.add(key)
        logger.info(f"[AI4ArtsEd LLM] {text}")


def _comfy_weights_by_dir() -> Dict[str, dict]:
    """folder name -> the "comfy_weights" block of its row, read again when
    the table's file changed. The rows' "sampling" blocks are read with it
    (maker_sampling)."""
    path = _table_file()
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        _say_once("no table", f"{path} is not there; every local language model runs through transformers "
                              f"and samples with what its caller sends")
        _table_cache["stamp"], _table_cache["by_dir"], _table_cache["sampling"] = None, {}, {}
        return {}
    if _table_cache["stamp"] != stamp:
        with open(path, encoding="utf-8") as f:
            table = json.load(f)
        by_dir, sampling = {}, {}
        for row in (table.get("models") or {}).values():
            if not isinstance(row, dict) or not row.get("dir"):
                continue
            if row.get("comfy_weights"):
                by_dir[row["dir"]] = row["comfy_weights"]
            if row.get("sampling"):
                sampling[row["dir"]] = row["sampling"]
        _table_cache["by_dir"], _table_cache["sampling"] = by_dir, sampling
        _table_cache["stamp"] = stamp
    return _table_cache["by_dir"]


def weights_file(dir_name: str, weights_format: Optional[str] = None) -> Optional[str]:
    """The installed file in ComfyUI's format for this folder, or None when
    the model runs through transformers.

    None: the table names no such file for the folder, or the file of the
    table's default format is not installed (said once in the log). A format
    the caller names is the caller's choice: it is an error when the table
    does not know it or its file is missing, and no other format answers in
    its place."""
    block = _comfy_weights_by_dir().get(dir_name)
    if not block:
        if weights_format:
            raise ValueError(f"{dir_name} has no weights in ComfyUI's format in the table, "
                             f"and {weights_format!r} was asked for")
        return None
    files = block.get("files") or {}
    fmt = weights_format or block.get("default")
    name = files.get(fmt)
    if not name:
        raise ValueError(f"{dir_name} has no weights of the format {fmt!r} in the table; "
                         f"it names {sorted(files)}")
    full = folder_paths.get_full_path(WEIGHTS_FOLDER, name)
    if full is None:
        if weights_format:
            raise FileNotFoundError(
                f"{name} ({fmt}) of {dir_name} is not under ComfyUI's models/{WEIGHTS_FOLDER}; "
                f"devserver/scripts/convert_llm_for_comfyui.py writes it")
        _say_once(f"missing {name}",
                  f"{name} of {dir_name} is not under ComfyUI's models/{WEIGHTS_FOLDER}; the model "
                  f"runs through transformers (devserver/scripts/convert_llm_for_comfyui.py writes the file)")
        return None
    return full


# ---------------------------------------------------------------------------
# How a model samples.

SAMPLING_KEYS = ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty")


def maker_sampling(dir_name: str) -> Optional[Dict[str, float]]:
    """The sampling the model's maker gives for a chat with the think block:
    the "thinking" set of the "sampling" block of the folder's row in the
    table. None where the row carries no block.

    The values are the model card's (README.md, "Best Practices"). Where a
    row carries them, _local_llm.generate samples a chat with the think
    block with them on either way, ComfyUI's or transformers', in place of
    the caller's temperature and repetition penalty. A block without the set
    or without one of SAMPLING_KEYS, or with a value no draw takes, is an
    error; nothing is filled in."""
    _comfy_weights_by_dir()
    block = _table_cache["sampling"].get(dir_name)
    if not block:
        return None
    values = block.get("thinking") if isinstance(block, dict) else None
    if not isinstance(values, dict):
        raise ValueError(f"{dir_name}: the sampling block of its row in the table has no 'thinking' set")
    found = {}
    for key in SAMPLING_KEYS:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{dir_name}: the 'thinking' sampling set of its row in the table has no "
                             f"number for {key!r}")
        found[key] = float(value)
    if not (found["temperature"] > 0 and found["top_k"] >= 1 and found["top_k"].is_integer()
            and 0 < found["top_p"] <= 1 and 0 <= found["min_p"] <= 1
            and found["repetition_penalty"] > 0):
        raise ValueError(f"{dir_name}: the 'thinking' sampling set of its row in the table holds a "
                         f"value no draw takes: {found}")
    return found


def _sampling_args(native: "Native", maker: Optional[Dict[str, float]],
                   repetition_penalty: Optional[float]) -> Dict[str, Any]:
    """What ComfyUI's generate gets for the draw beside the temperature: the
    maker's set where the call carries one (maker_sampling); otherwise top_k
    and top_p of the folder's generation config, no min_p, no presence
    penalty, and the caller's repetition penalty or the config's."""
    if maker is not None:
        return {"top_k": int(maker["top_k"]), "top_p": maker["top_p"], "min_p": maker["min_p"],
                "repetition_penalty": maker["repetition_penalty"],
                "presence_penalty": maker["presence_penalty"]}
    return {"top_k": native.sampling["top_k"], "top_p": native.sampling["top_p"], "min_p": 0.0,
            "repetition_penalty": float(repetition_penalty) if repetition_penalty is not None
            else native.sampling["repetition_penalty"],
            "presence_penalty": 0.0}


# ---------------------------------------------------------------------------
# The model.

@dataclass
class Native:
    """A model loaded by ComfyUI's loader, and what the folder gives beside it."""
    key: str
    dir_name: str
    file: str
    clip: Any
    patcher: Any                        # clip.patcher, ComfyUI's own; it never calls _card.forget
    module: Any                         # clip.cond_stage_model (read by _card._drop_held)
    transformer: Any
    tokenizer: Any
    vision: bool
    image_pad_id: Optional[int]
    stop_ids: Tuple[int, ...]
    eos_texts: Tuple[str, ...]
    sampling: Dict[str, Any]
    weight_bytes: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


_registry: Optional[_card.Registry] = None


def _the_registry() -> _card.Registry:
    global _registry
    if _registry is None:
        from ._local_llm import KEEP_BUILT
        _registry = _card.Registry("LLM (ComfyUI)", KEEP_BUILT)
    return _registry


def transformer_of(clip: Any) -> Any:
    """ComfyUI's language model inside the object its loader returns."""
    inner = clip.cond_stage_model
    return getattr(inner, inner.clip).transformer


def _folder_generation(path: str) -> Dict[str, Any]:
    """generation_config.json of the folder, {} where the folder ships none."""
    file = os.path.join(path, "generation_config.json")
    if not os.path.isfile(file):
        return {}
    with open(file, encoding="utf-8") as f:
        return json.load(f)


def _folder_eos(path: str, generation: Dict[str, Any]) -> Any:
    """The end-of-sequence ids the folder names: its generation config's,
    else what transformers would derive for a folder without one, the
    eos_token_id of config.json (of the text part, in a vision model's)."""
    if generation.get("eos_token_id") is not None:
        return generation["eos_token_id"]
    with open(os.path.join(path, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    for c in (cfg, cfg.get("text_config") or {}):
        if c.get("eos_token_id") is not None:
            return c["eos_token_id"]
    return None


def _load(key: str) -> Native:
    """Read the file with ComfyUI's loader and the folder's tokenizer."""
    import comfy.sd
    from transformers import AutoTokenizer
    from ._local_llm import _read_config, _stop_ids, weights_path

    dir_name, file = key.split("|", 1)
    path = weights_path(dir_name)
    note = version_note()
    if note:
        logger.warning(f"[AI4ArtsEd LLM] {dir_name}: {note}")
    weight_bytes = os.path.getsize(file)
    logger.info(f"[AI4ArtsEd LLM] Loading {dir_name} from {file} "
                f"({weight_bytes / 2**30:.1f} GB) with ComfyUI's own implementation")
    clip = comfy.sd.load_clip(ckpt_paths=[file], clip_type=comfy.sd.CLIPType.STABLE_DIFFUSION)
    transformer = transformer_of(clip)
    config = transformer.model.config
    if not isinstance(getattr(config, "stop_tokens", None), list):
        raise RuntimeError(
            f"{file}: ComfyUI's model for it carries no list of stop tokens on its config "
            f"({type(getattr(config, 'stop_tokens', None)).__name__}); the tokens of a generation "
            f"cannot be read along, and the model is not run on this way")
    for name in ("generate", "init_kv_cache"):
        if not callable(getattr(transformer, name, None)):
            raise RuntimeError(f"{file}: ComfyUI's model for it has no {name}()")

    tokenizer = AutoTokenizer.from_pretrained(path)
    generation = _folder_generation(path)
    folder_stop = _stop_ids(_folder_eos(path, generation), tokenizer.eos_token_id)
    comfy_stop = tuple(int(i) for i in config.stop_tokens)
    if set(folder_stop) != set(comfy_stop):
        logger.warning(f"[AI4ArtsEd LLM] {dir_name}: the folder ends a turn at {sorted(folder_stop)}, "
                       f"ComfyUI's model at {sorted(comfy_stop)}; a generation stops at either")
    stop_ids = tuple(dict.fromkeys(comfy_stop + folder_stop))
    vision = getattr(_read_config(path), "vision_config", None) is not None
    pad = tokenizer.convert_tokens_to_ids("<|image_pad|>") if vision else None
    if vision and (pad is None or pad == tokenizer.unk_token_id):
        raise RuntimeError(f"{dir_name} reads pictures and its tokenizer has no <|image_pad|> token")
    sampling = {
        # What transformers samples with where the folder ships no
        # generation config: top_k 50, top_p 1.0.
        "top_k": int(generation.get("top_k", 50) or 0),
        "top_p": float(1.0 if generation.get("top_p") is None else generation["top_p"]),
        "repetition_penalty": float(1.0 if generation.get("repetition_penalty") is None
                                    else generation["repetition_penalty"]),
    }
    return Native(key=key, dir_name=dir_name, file=file, clip=clip, patcher=clip.patcher,
                  module=clip.cond_stage_model, transformer=transformer, tokenizer=tokenizer,
                  vision=vision, image_pad_id=pad, stop_ids=stop_ids,
                  eos_texts=tuple(tokenizer.decode([i]) for i in stop_ids),
                  sampling=sampling, weight_bytes=weight_bytes)


def _ram_available() -> int:
    """The host RAM a load can take, as ComfyUI counts it (a memory limit on
    the process included)."""
    import comfy.system_memory
    return int(comfy.system_memory.virtual_memory_available())


def _ram_headroom() -> int:
    """The host RAM that stays free beside a load: what the operator gave
    ComfyUI as RAM headroom (--cache-ram), which ComfyUI sets while a prompt
    executes."""
    import comfy.memory_management
    return int(comfy.memory_management.RAM_CACHE_HEADROOM)


def get_loaded(dir_name: str, file: str) -> Native:
    """The model of this file, loaded on first use. ComfyUI's loader keeps a
    model's weights in host RAM beside what it puts on the card (measured,
    2026-11-10: 31.7 GB of anonymous memory for a 27B in MXFP8, 16.4 GB more
    for a second one, with 4.3 GB of 62 GB left available and swap in use).
    So a load says what its file weighs, and this way's older models are
    dropped first while RAM does not hold the file and the headroom beside
    it; what RAM and swap cannot hold at all is refused by the registry."""
    registry = _the_registry()
    key = f"{dir_name}|{file}"
    with _card._build_lock:
        if registry.peek(key) is not None:
            return registry.get(key, _load, 0)
        incoming = os.path.getsize(file)
        headroom = _ram_headroom()
        while registry.keys():
            available = _ram_available()
            if available >= incoming + headroom:
                break
            registry.drop(registry._oldest(),
                          f"{key} reads {incoming / 2**30:.1f} GB into RAM, {available / 2**30:.1f} GB "
                          f"are available and {headroom / 2**30:.1f} GB stay free")
        return registry.get(key, _load, incoming)


# ---------------------------------------------------------------------------
# The card.

def _reserve_bytes(transformer: Any, prompt_tokens: int, max_length: int, device: Any) -> int:
    """What one generation allocates beside the weights, from the config of
    ComfyUI's model.

    Four parts, each measured on 10.11.2026 (Qwen 3.8 27B, MXFP8 and NVFP4,
    ComfyUI 0.44.2):
      * the key/value cache of the full-attention layers and of the MTP
        head's one layer, for prompt + max_length + 7 positions, in the
        dtype ComfyUI computes in. Measured for the 65,536 window:
        4,749,687,296 bytes together with the states of the next part; this sum gives
        4,749,684,736 for both.
      * the states of the linear-attention layers, which do not grow with
        the window: recurrent state (float32), convolution state and the
        side buffers of the deferred commit. Measured 185,796,096 bytes for
        the 27B's 48 such layers; this sum gives 185,794,560.
      * the forward pass over the prompt (PREFILL_BYTES_PER_TOKEN_AND_WIDTH).
        A picture's tokens are prompt tokens here, so a picture is covered
        by this part and needs no reserve of its own.
      * FIXED_WORK_BYTES.
    """
    config = transformer.model.config
    element = 2 if comfy.model_management.should_use_bf16(device) else 4
    layer_types = list(getattr(config, "layer_types", None) or
                       ["full_attention"] * int(config.num_hidden_layers))
    full = sum(1 for t in layer_types if t == "full_attention")
    linear = sum(1 for t in layer_types if t == "linear_attention")
    kv_heads = int(getattr(config, "num_key_value_heads", None) or config.num_attention_heads)
    head_dim = int(getattr(config, "head_dim", None) or config.hidden_size // config.num_attention_heads)
    positions = int(prompt_tokens) + int(max_length) + MTP_EXTRA_POSITIONS
    caches = full + (1 if getattr(transformer, "mtp", None) is not None else 0)
    kv = caches * 2 * kv_heads * head_dim * element * positions

    states = 0
    if linear:
        value_heads = int(config.linear_num_value_heads)
        key_heads = int(config.linear_num_key_heads)
        key_dim = int(config.linear_key_head_dim)
        value_dim = int(config.linear_value_head_dim)
        conv_dim = key_heads * key_dim * 2 + value_heads * value_dim
        slots = _slot_max()
        recurrent = value_heads * key_dim * value_dim * 4
        conv = conv_dim * (int(config.conv_kernel_size) - 1) * element
        side = 2 * (2 * conv_dim * slots * element) + 2 * slots * value_heads * 2 * 4 + 2 * slots * key_heads * 2 * 4
        states = linear * (recurrent + conv + side)

    prefill = int(prompt_tokens) * int(config.hidden_size) * PREFILL_BYTES_PER_TOKEN_AND_WIDTH
    return kv + states + prefill + FIXED_WORK_BYTES


def _slot_max() -> int:
    """The token slots of the deferred-commit buffers (comfy_kitchen)."""
    try:
        import comfy_kitchen
        return int(comfy_kitchen.gated_delta_slot_max)
    except Exception:
        return 8


def _book(native: Native, reserve: int) -> None:
    """Room for the weights still to come onto the card and for the reserve,
    or a refusal by name; then the load, with the reserve announced.

    ComfyUI's patcher for these files puts weights on the card as the
    forward pass reaches them, so before the first generation almost all of
    the model is still to come (model_size - loaded_size), and nothing of it
    once it is resident."""
    mm = comfy.model_management
    patcher = native.patcher
    to_load = max(0, int(patcher.model_size()) - int(patcher.loaded_size()))
    ours = [lm for lm in mm.current_loaded_models if lm.model is patcher]
    _card.room_for(to_load, reserve, native.dir_name, keep=ours)
    mm.load_models_gpu([patcher], memory_required=reserve)


# ---------------------------------------------------------------------------
# Reading the tokens along.

class _Watch(list):
    """The stop list of one generate: the stop tokens, and a reader.

    `sink(token)` is called once for every token ComfyUI asks about for the
    first time, in the order it generates them, and answers True when the
    generation is to halt. The token is recorded before the sink decides.
    A halt sticks: every later question is answered True, whoever asks.
    """

    def __init__(self, stop_ids, sink: Callable[[int], bool]):
        super().__init__(stop_ids)
        self.sink = sink
        self.seen: List[int] = []
        self.halted = False
        self.head_calls = 0
        self.unknown: Dict[str, int] = {}

    def __contains__(self, token) -> bool:
        frame = sys._getframe(1).f_code.co_name
        if frame == LOOP_HEAD_FRAME:
            self.head_calls += 1
            if self.head_calls > 1:
                # The loop head asks again about the last token of the step
                # before; it was read when the step asked about it.
                return self.halted or list.__contains__(self, token)
        elif frame not in NEW_TOKEN_FRAMES:
            # Somebody this module does not know asks. The token is not
            # counted, the question is answered, and the caller is named
            # after the run (generate compares what was read with what
            # came back).
            self.unknown[frame] = self.unknown.get(frame, 0) + 1
            return self.halted or list.__contains__(self, token)
        token = int(token)
        self.seen.append(token)
        if self.sink(token):
            self.halted = True
        return self.halted or list.__contains__(self, token)


def _finite_sampling(native: "Native", reader: "_Reader", sample_token: Callable) -> Callable:
    """ComfyUI's sample_token behind the check the transformers way makes in
    _local_llm._Finite: scores with a nan, a +inf, or a row without a finite
    value end the run in Python, before torch.multinomial is asked. Its
    check on the device asserts, and after a device-side assert every later
    CUDA call throws -- on 15.09.2026 that ended the ComfyUI process (see
    _Finite). sample_token is the one place ComfyUI draws a token at (held
    by test_comfy_llm_stop_watch.py against the pinned release); where it
    takes the argmax, nothing is drawn and nothing can assert."""
    def checked(logits, *args, **kwargs):
        bad = (torch.isnan(logits).any() | torch.isposinf(logits).any()
               | (~torch.isfinite(logits).any(dim=-1)).any())
        if bool(bad):
            raise RuntimeError(
                f"{native.dir_name} produced scores no token can be taken from (nan, +inf, or a row "
                f"without a finite value) after {reader.tokens} generated tokens; the run ends before "
                f"one is taken. The file read was {native.file}; look at ComfyUI's log of its load "
                f"for keys it reported missing or unexpected")
        return sample_token(logits, *args, **kwargs)
    return checked


def _first_difference(a: List[int], b: List[int]) -> Optional[int]:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


class _Reader:
    """What happens to a token read along: decoded into pieces the way the
    transformers way's streamer decodes them, the think block held back
    from the stream, the end-of-turn texts taken out of it, the repetition
    guard fed, the interruption looked for."""

    def __init__(self, native: Native, opened: bool, raw: bool,
                 on_token: Optional[Callable[[str], None]], vocab: int):
        from transformers import TextStreamer
        from ._local_llm import _Spoken

        reader = self

        class _Pieces(TextStreamer):
            def on_finalized_text(self, text: str, stream_end: bool = False):
                reader._piece(text)

        self.native = native
        self.raw = raw
        self.on_token = on_token
        self.vocab = vocab
        self.streamer = _Pieces(native.tokenizer, skip_prompt=False, skip_special_tokens=False)
        self.spoken = _Spoken(in_think=opened)
        self.guard = RepetitionGuard()
        self.pieces: List[str] = []
        self.answered: List[str] = []
        self.repetition = False
        self.interrupted = False
        self.tokens = 0

    def token(self, token: int) -> bool:
        """One token; True when the generation is to halt."""
        if not 0 <= token < self.vocab:
            raise RuntimeError(
                f"{self.native.dir_name} produced the token {token} after {self.tokens} tokens, "
                f"outside its vocabulary of {self.vocab}; the run ends here")
        self.tokens += 1
        self.streamer.put(torch.tensor([token]))
        if comfy.model_management.processing_interrupted():
            self.interrupted = True
        return self.repetition or self.interrupted

    def end(self) -> None:
        self.streamer.end()

    def _piece(self, piece: str) -> None:
        if not piece:
            return
        self.pieces.append(piece)
        answer = piece if self.raw else self.spoken.feed(piece)
        if self.on_token is not None:
            shown = answer
            for eos in self.native.eos_texts:
                if eos:
                    shown = shown.replace(eos, "")
            if shown:
                self.on_token(shown)
        if not self.repetition:
            self.answered.append(answer)
            if self.guard.feed_split(piece, answer, "" if self.raw else self.spoken.held):
                self.repetition = True
                logger.info(f"[AI4ArtsEd LLM] {self.native.dir_name} repeated "
                            f"{self.guard.describe()} and was stopped")


# ---------------------------------------------------------------------------
# One generation.

def _picture_tensors(pils: List[Any]) -> List[torch.Tensor]:
    """ComfyUI's picture form, [1, H, W, 3] in 0..1, from PIL images."""
    import numpy as np
    return [torch.from_numpy(np.asarray(p.convert("RGB"), dtype=np.float32) / 255.0).unsqueeze(0)
            for p in pils]


def _picture_tokens(picture: torch.Tensor) -> int:
    """How many positions ComfyUI's model gives a picture: its own
    preprocessing, run on the CPU, and the grid it reports, merged two by
    two (qwen35.py, preprocess_embed; the patch size is the vision tower's)."""
    import comfy.text_encoders.qwen_vl as qwen_vl
    _, grid = qwen_vl.process_qwen2vl_images(picture, patch_size=16, image_mean=[0.5, 0.5, 0.5],
                                             image_std=[0.5, 0.5, 0.5])
    t, h, w = (int(v) for v in grid[0])
    return t * (h // 2) * (w // 2)


def _token_rows(ids: List[int], pictures: List[torch.Tensor], pad: Optional[int]) -> List[tuple]:
    """The prompt in ComfyUI's token structure: (id, weight) per token, and
    at each picture place the picture itself."""
    places = sum(1 for i in ids if i == pad) if pad is not None else 0
    if places != len(pictures):
        raise ValueError(f"the prompt has {places} places for pictures and {len(pictures)} were attached")
    waiting = iter(pictures)
    row = []
    for i in ids:
        if pad is not None and i == pad:
            row.append(({"type": "image", "data": next(waiting), "original_type": "image"}, 1.0))
        else:
            row.append((int(i), 1.0))
    return row


def generate(dir_name: str, file: str,
             messages: Optional[List[dict]], pils: List[Any], prompt: Optional[str],
             temperature: float, repetition_penalty: Optional[float], seed: Optional[int],
             context_tokens: int, on_token: Optional[Callable[[str], None]],
             enable_thinking: bool,
             maker: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """One answer on ComfyUI's own implementation. Called by
    _local_llm.generate, which has checked its arguments and documents the
    call and the answer. `maker` is the maker's sampling set where the call
    takes one (maker_sampling); _local_llm.generate has put its temperature
    into `temperature` already."""
    from ._local_llm import _Spoken, _partition, _strip_eos

    native = get_loaded(dir_name, file)
    tok = native.tokenizer
    raw = prompt is not None
    with native.lock:
        if raw:
            ids = tok(prompt, add_special_tokens=True).input_ids
        else:
            turns = _with_picture_places(messages, len(pils))
            text = tok.apply_chat_template(turns, tokenize=False, add_generation_prompt=True,
                                           enable_thinking=bool(enable_thinking))
            ids = tok(text, add_special_tokens=False).input_ids
        pictures = _picture_tensors(pils)
        row = _token_rows(ids, pictures, native.image_pad_id)
        prompt_len = len(ids) - len(pictures) + sum(_picture_tokens(p) for p in pictures)
        if prompt_len >= context_tokens:
            raise ValueError(
                f"the prompt is {prompt_len} tokens and the context window {context_tokens}; "
                f"nothing is left for the answer")
        opened = not raw and tok.decode(ids[-8:]).rstrip().endswith(_Spoken.OPEN)
        max_length = int(context_tokens) - prompt_len

        mm = comfy.model_management
        device = native.patcher.load_device
        transformer = native.transformer
        config = transformer.model.config
        reserve = _reserve_bytes(transformer, prompt_len, max_length, device)
        _book(native, reserve)

        reader = _Reader(native, opened, raw, on_token, int(config.vocab_size))
        original = config.stop_tokens
        watch = _Watch(native.stop_ids, reader.token)
        encoder = native.clip.cond_stage_model
        if seed is None:
            # ComfyUI would take 42 for every call that names none.
            seed = int.from_bytes(os.urandom(4), "little")
        drawn = _sampling_args(native, maker, repetition_penalty)
        name = getattr(encoder, "clip_name", None) or "tokens"
        peak_before = None
        if torch.device(device).type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
            peak_before = torch.cuda.memory_allocated(device)
        try:
            config.stop_tokens = watch
            # ComfyUI's own hook for what a generation needs beside the
            # weights (comfy/sd.py, CLIP.load_model): with it, the load
            # inside CLIP.generate announces the same reserve instead of
            # none.
            encoder.memory_estimation_function = lambda tokens, device=None: reserve
            # For this run, on the instance; the class keeps its method.
            transformer.sample_token = _finite_sampling(native, reader, transformer.sample_token)
            returned = native.clip.generate(
                {name: [row]}, do_sample=temperature > 0, max_length=max_length,
                temperature=float(temperature) if temperature > 0 else 1.0,
                seed=int(seed) & 0xffffffffffffffff, mtp=True, **drawn)
        finally:
            # For every way out, ComfyUI's interruption included
            # (InterruptProcessingException is a BaseException and is passed
            # on as it is).
            config.stop_tokens = original
            for holder, name_ in ((encoder, "memory_estimation_function"), (transformer, "sample_token")):
                try:
                    delattr(holder, name_)
                except AttributeError:
                    pass
        returned = [int(t) for t in returned]
        if peak_before is not None:
            peak = torch.cuda.max_memory_allocated(device) - peak_before
            log = logger.warning if peak > reserve else logger.info
            log(f"[AI4ArtsEd LLM] {dir_name}: the generation took {peak / 2**20:.0f} MiB beside the "
                f"weights, {reserve / 2**20:.0f} MiB were booked"
                + (" -- MORE than booked" if peak > reserve else ""))

        # What was read along against what came back.
        agree = True
        seen = list(watch.seen)
        if seen != returned:
            ahead = returned[len(seen):] if returned[:len(seen)] == seen else None
            if ahead is not None and len(returned) == max_length == len(seen) + 1 and not seen:
                # A window with room for one token: ComfyUI's MTP loop takes
                # the first token and leaves before it asks about it.
                reader.token(ahead[0])
            else:
                agree = False
                at = _first_difference(seen, returned)
                logger.warning(
                    f"[AI4ArtsEd LLM] {dir_name}: {len(seen)} tokens were read along and "
                    f"{len(returned)} came back, first difference at {at} "
                    f"(asked from elsewhere: {watch.unknown or 'nobody'}); the answer is made from "
                    f"the returned tokens. ComfyUI is {comfyui_version()}, checked was {PINNED_COMFYUI}")
        elif watch.unknown:
            logger.warning(f"[AI4ArtsEd LLM] {dir_name}: the stop list was asked from "
                           f"{watch.unknown}, which this module does not know")
        reader.end()

    if reader.interrupted:
        # ComfyUI's own way of ending a run: the flag is cleared and the
        # executor reports execution_interrupted for this prompt.
        mm.throw_exception_if_processing_interrupted()

    if agree:
        text = "".join(reader.pieces)
        answered = "".join(reader.answered)
    else:
        text = tok.decode(returned, skip_special_tokens=False)
        answered = text if raw else _partition(_strip_eos(text, native.eos_texts).strip(), opened)[0]
    text = _strip_eos(text, native.eos_texts).strip()
    if reader.repetition:
        finish = "repetition"
    elif returned and returned[-1] in native.stop_ids:
        finish = "stop"
    elif len(returned) >= max_length:
        finish = "length"
    else:
        finish = "stop"

    thinking = None
    if not raw:
        text, thinking = _partition(text, opened)
    return {
        "content": text,
        "thinking": thinking,
        "finish_reason": finish,
        "prompt_tokens": prompt_len,
        "completion_tokens": len(returned),
        "once": reader.guard.once(_strip_eos(answered, native.eos_texts)) if not raw else "",
    }


def _with_picture_places(messages: List[dict], pictures: int) -> List[dict]:
    """The messages for the chat template, one picture place per attached
    picture in the first user turn ahead of its text -- where
    _local_llm._with_images puts the pictures on the transformers way. The
    template writes the place; the picture itself goes into the token row."""
    out = []
    placed = pictures == 0
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts = [{"type": "text", "text": content}] if isinstance(content, str) else list(content)
        if role == "user" and not placed:
            parts = [{"type": "image"}] * pictures + parts
            placed = True
        out.append({"role": role, "content": parts})
    if not placed:
        out.append({"role": "user", "content": [{"type": "image"}] * pictures})
    return out
