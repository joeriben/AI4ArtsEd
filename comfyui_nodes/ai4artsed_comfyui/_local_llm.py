"""The local language and image-reading models, run by ComfyUI.

Stage 3 of the move to ComfyUI: every local model of the
platform lives on the card under ComfyUI's memory management, the way ComfyUI
holds a checkpoint or a text encoder. A model here is a transformers module
wrapped in a ModelPatcher, read from its safetensors straight onto the card
(_build) and announced to ComfyUI as loaded; ComfyUI takes other models off
the card to make room for it, and takes THIS one off again when a diffusion
model needs the room -- and then it is released, read again on the next call
(_card.GoneWhenTakenOff). The room for the read is asked of ComfyUI before
it (_card.room_for) and the model is announced to ComfyUI right after
(_card.announce_on_card): llama-server sized its own window from what was
free at start and took further buffers on demand, which is what this
replaces.

What a call needs beyond the weights is announced up front, as the
memory_required of the load: the key/value cache of the context window this
call may use, and the activations of the vision tower when a picture is
attached. ComfyUI frees for that sum before the first token, so a generation
that runs to its window does not run into a card another model still holds.

The weights are safetensors snapshots under <ComfyUI>/models/llm/<repo dir>/,
one folder per repository, written by the DevServer's installer from
devserver/config/local_llm_weights.json. This module knows no model name: it
lists the folders that are there and loads the one it is handed.

Two entry points share everything here: the node (ai4artsed_local_llm.py),
which the DevServer queues one prompt at a time, and the LLM nodes of a
workflow built in ComfyUI, whose role resolved to a local model -- those run
inside an executing prompt and cannot queue behind themselves, so they call
generate() in place.
"""
import json
import logging
import os
import struct
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import torch
from transformers import LogitsProcessor, StoppingCriteria

import comfy.model_management
import folder_paths

from . import _card
from ._repetition_guard import RepetitionGuard
from ._snapshot import complete

logger = logging.getLogger(__name__)

# The folder under ComfyUI's models directory. The DevServer writes into the
# same name (my_app/services/local_llm_weights.py, MODELS_SUBDIR).
FOLDER_NAME = "llm"

# How many models stay built between calls. A built model is a model on the
# card: it is read from disk onto the card (_build), and when ComfyUI takes
# it off the card for a diffusion model it is gone, read again on the next
# call (_card.GoneWhenTakenOff). This bounds how many the station itself
# keeps there; ComfyUI takes them off sooner when it needs the room. Three,
# because a platform run touches at most three local models in a row -- the
# check model, the interception model and the image reader -- and a fourth
# would push the first out.
KEEP_BUILT = 3

# Reserved beside the weights when a picture is attached: what the vision
# tower allocates while it encodes. 1024 MB was measured for the llama.cpp
# encoder at the 2048 px the platform hands over (gpu_service, 2026-09-02);
# the transformers towers keep their patches in higher precision, so twice
# that is announced. An estimate on the safe side costs nothing when the room
# is there and an eviction when it is not; a short one costs the generation.
VISION_RESERVE_BYTES = 2048 * 1024 * 1024

# The context window a call may use when the caller names none: prompt and
# answer together, 64k. The key/value cache for it is announced to ComfyUI
# before the model is put on the card, and the answer ends with finish_reason
# "length" when it reaches the window -- said, never cut in silence. A caller
# with a longer prompt names a wider window (context_tokens); the reserve
# grows with it. This is the one ceiling of the platform's rule (no cap below
# ~64k), the window and not a cap on the answer within it.
DEFAULT_CONTEXT_TOKENS = 65536

# The event a running generation publishes on ComfyUI's websocket, one per
# piece of text, to the client that queued the prompt. The DevServer's client
# reads it (my_app/services/comfyui_ws_client.py, on_event).
TOKEN_EVENT = "ai4artsed.llm.token"


def models_root() -> str:
    return os.path.join(folder_paths.models_dir, FOLDER_NAME)


def _register_folder() -> None:
    root = models_root()
    os.makedirs(root, exist_ok=True)
    folder_paths.add_model_folder_path(FOLDER_NAME, root, is_default=True)


_register_folder()


def installed_dirs() -> List[str]:
    """The folder names under models/llm that hold a whole snapshot, sorted.

    Whole is _snapshot.complete: config.json there, no huggingface_hub
    '.incomplete' part left, every shard the index names in place. Every
    registered path of the folder is searched, so an extra_model_paths.yaml
    entry for 'llm' counts too.
    """
    found = []
    for base in folder_paths.get_folder_paths(FOLDER_NAME):
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            # A dot-folder is a download in flight (the DevServer's installer
            # stages under .incoming-<dir> and renames when whole).
            if name.startswith("."):
                continue
            if complete(os.path.join(base, name)) and name not in found:
                found.append(name)
    return found


def weights_path(dir_name: str) -> str:
    """The folder of a listed model, or an error naming what is there."""
    for base in folder_paths.get_folder_paths(FOLDER_NAME):
        d = os.path.join(base, dir_name)
        if os.path.isfile(os.path.join(d, "config.json")):
            return d
    raise FileNotFoundError(
        f"no model folder {dir_name!r} under {folder_paths.get_folder_paths(FOLDER_NAME)}; "
        f"installed: {installed_dirs()}")


# ---------------------------------------------------------------------------
# The module ComfyUI manages.

class TransformersModule(torch.nn.Module):
    """The transformers model, as the module ModelPatcher holds.

    ModelPatcher writes `device`, `model_lowvram` and its memory counters onto
    the module it manages, and a transformers model exposes `device` as a
    read-only property. This container has none of that: ComfyUI writes on the
    container, `.to()` moves the model inside it, and module_size counts the
    model's parameters through it.
    """

    def __init__(self, hf: torch.nn.Module):
        super().__init__()
        self.hf = hf

    def get_dtype(self):
        return self.hf.dtype


@dataclass
class Built:
    dir_name: str
    path: str
    patcher: Any
    module: TransformersModule
    processor: Any                      # AutoProcessor for a model with a vision tower
    tokenizer: Any
    config: Any
    vision: bool
    eos_ids: Tuple[int, ...] = ()       # the tokens a generation stops at (_stop_ids)
    eos_texts: Tuple[str, ...] = ()
    weight_bytes: int = 0               # the safetensors on disk, what the card holds
    lock: threading.Lock = field(default_factory=threading.Lock)


# The built models, KEEP_BUILT at most, held the way every station of the
# package holds its models (_card.Registry).
_registry = _card.Registry("LLM", KEEP_BUILT)


def _kv_cache_bytes(config: Any, tokens: int) -> int:
    """The key/value cache of `tokens` positions, from the model's config.

    Two floats per position per head per layer, in the cache's dtype (bf16,
    two bytes, whichever precision the weights have). Layers that are not
    full attention (a hybrid model lists them under layer_types) keep a state
    that does not grow with the window and are left out. The text part of a
    vision-language config carries the numbers.
    """
    text = getattr(config, "text_config", None) or config
    n = int(getattr(text, "num_hidden_layers", 0) or 0)
    layer_types = getattr(text, "layer_types", None)
    full = ([i for i, t in enumerate(layer_types) if t == "full_attention"]
            if layer_types else list(range(n)))
    # A config whose layers differ from one another (Gemma 4: 256-wide heads on
    # the sliding layers, 512-wide on the full ones) carries the numbers per
    # layer, and transformers refuses to answer the global attribute at all
    # (AmbiguousGlobalPerLayerAttributeError). Every layer is therefore read
    # on its own. transformers 5.17 gives every config a per_layer_config; on
    # a homogeneous one each layer's entry is the config itself, so the sum is
    # what the global numbers gave. The fallback to the config covers a
    # transformers without the attribute.
    per_layer = getattr(text, "per_layer_config", None)
    width = sum(_kv_width(per_layer[i] if per_layer is not None else text) for i in full)
    return 2 * width * 2 * int(tokens)


def _kv_width(c: Any) -> int:
    """Key/value heads times head width, for one layer's config."""
    kv_heads = int(getattr(c, "num_key_value_heads", None)
                   or getattr(c, "num_attention_heads", 0) or 0)
    head_dim = getattr(c, "head_dim", None)
    if not head_dim:
        heads = int(getattr(c, "num_attention_heads", 0) or 0)
        hidden = int(getattr(c, "hidden_size", 0) or 0)
        head_dim = hidden // heads if heads else 0
    return kv_heads * int(head_dim)


def _missing_requirements(path: str) -> List[str]:
    """Packages the checkpoint's loader needs that this venv lacks, by name.

    Checked before transformers is asked, so a missing package is reported as
    that rather than as whatever transformers raises three imports deep.
    """
    import importlib.util
    missing = []
    with open(os.path.join(path, "config.json")) as f:
        cfg = json.load(f)
    if (cfg.get("quantization_config") or {}).get("quant_method") == "fp8":
        if importlib.util.find_spec("accelerate") is None:
            missing.append("accelerate")
    # Mistral ships its own tokenizer file; a repository that also ships
    # tokenizer.json is read by transformers' own backend, and only one that
    # ships tekken.json alone needs mistral-common.
    if (os.path.isfile(os.path.join(path, "tekken.json"))
            and not os.path.isfile(os.path.join(path, "tokenizer.json"))):
        if importlib.util.find_spec("mistral_common") is None:
            missing.append("mistral-common")
    return missing


def _read_config(path: str):
    """The checkpoint's config, with an FP8 quantization block transformers
    can read. A checkpoint quantised for vLLM names the layers kept in full
    precision under 'ignored_layers'; transformers 5 knows only
    'modules_to_not_convert' and, handed the other key, would convert those
    layers (a vision tower's blocks, saved in bf16 without scales) to FP8
    with empty scales and answer nonsense on every picture. The key is
    renamed on the config object, which from_pretrained takes as it is.

    An entry of that list that names nothing in the checkpoint, is the
    beginning of module names that are there, and begins only quantised
    modules is dropped as well (_false_prefixes). Qwen ships the
    dense Qwen3.8-27B-FP8 with the exclusion list of an MoE sibling,
    `layers.N.mlp.gate` for every layer, and transformers matches an entry as
    an unanchored prefix (quantizers/quantizers_utils.py should_convert_module,
    `re.match(key, name)`): `mlp.gate` excluded `mlp.gate_proj`, which then
    stayed a bf16 Linear over FP8 bytes, its scales were reported UNEXPECTED
    for all 64 layers, and the model answered "革革革革" (Nebenbefund 113;
    measured 2026-09-21 under transformers 5.17.0 as before under 5.2.0).
    The check reads the checkpoint's tensor names; transformers matches the
    entries against the model's module names, after
    _normalize_modules_to_not_convert has passed them through the model's
    conversion mapping (quantizers/quantizer_finegrained_fp8.py), and for
    the checkpoints measured the two namings agree."""
    from transformers import AutoConfig
    config = AutoConfig.from_pretrained(path)
    qc = getattr(config, "quantization_config", None)
    if isinstance(qc, dict):
        if "ignored_layers" in qc and "modules_to_not_convert" not in qc:
            qc["modules_to_not_convert"] = list(qc.pop("ignored_layers"))
        if qc.get("modules_to_not_convert"):
            false = _false_prefixes(qc["modules_to_not_convert"], _tensor_names(path))
            if false:
                qc["modules_to_not_convert"] = [m for m in qc["modules_to_not_convert"] if m not in false]
                logger.info(f"[AI4ArtsEd LLM] {os.path.basename(path)}: {len(false)} entries of "
                            f"modules_to_not_convert name nothing in the checkpoint and are the "
                            f"beginning of names that are there; dropped (e.g. {sorted(false)[0]})")
    elif qc is not None:
        logger.warning(f"[AI4ArtsEd LLM] {os.path.basename(path)}: quantization_config is a "
                       f"{type(qc).__name__}; the renaming and the exclusion-list check read a dict "
                       f"and leave it as it is")
    return config


def _tensor_names(path: str) -> List[str]:
    """Every tensor name the snapshot's safetensors carry: the index's map
    where there is one and names something, else the header of each
    safetensors file at the root. A file whose header cannot be read (a
    git-lfs pointer, a part of a download, a file of another format under
    the suffix) is named in the log and left out: the list is a hint for
    _false_prefixes, and the names of a file left out are unknown to that
    check."""
    index = os.path.join(path, "model.safetensors.index.json")
    if os.path.isfile(index):
        with open(index) as f:
            names = list(json.load(f).get("weight_map", {}))
        if names:
            return names
    names = []
    for f in sorted(os.listdir(path)):
        if not f.endswith(".safetensors"):
            continue
        file = os.path.join(path, f)
        try:
            with open(file, "rb") as fh:
                n = struct.unpack("<Q", fh.read(8))[0]
                if n > 2**30:
                    raise ValueError(f"header length {n}: not a safetensors file")
                header = json.loads(fh.read(n))
        except (OSError, ValueError, struct.error) as e:
            logger.warning(f"[AI4ArtsEd LLM] {file}: header not read ({e}); its tensor names "
                           f"are unknown to the exclusion-list check")
            continue
        names.extend(k for k in header if k != "__metadata__")
    return names


def _false_prefixes(entries: List[str], tensor_names: List[str]) -> Set[str]:
    """The entries of an exclusion list that name no module and no tensor of
    the checkpoint, are the beginning of module names that are there
    (`mlp.gate` before `mlp.gate_proj`), and begin only modules the
    checkpoint quantised (a weight scale saved beside the weight):
    transformers matches such an entry as a prefix and would keep those
    modules out of the conversion their bytes need. An entry that names a
    module or a subtree (with or without a trailing dot), a tensor, a suffix
    or a regex is left alone; so is a stem that begins a module saved
    without a scale (`in_proj` before an `in_proj_qkvz` in bf16), which the
    list is keeping out of the conversion on purpose."""
    modules: Set[str] = set()
    for name in tensor_names:
        parts = name.split(".")
        for i in range(1, len(parts)):
            modules.add(".".join(parts[:i]))
    tensors = set(tensor_names)
    scaled = {name.rsplit(".", 1)[0] for name in tensor_names
              if name.endswith((".weight_scale_inv", ".weight_scale"))}
    out: Set[str] = set()
    for entry in entries:
        core = entry.rstrip(".")
        if not core or core in modules or core in tensors:
            continue
        begun = [m for m in modules if m.startswith(core) and m[len(core)] != "."]
        if begun and all(m in scaled for m in begun):
            out.add(entry)
    return out


def _softcapped(config) -> bool:
    """Whether the config, or the text config inside a vision model's, caps
    its attention logits (attn_logit_softcapping)."""
    for c in (config, getattr(config, "text_config", None)):
        if getattr(c, "attn_logit_softcapping", None) is not None:
            return True
    return False


def _build(dir_name: str) -> Built:
    """Read the snapshot onto the card and wrap it for ComfyUI.

    The room is made first (_card.room_for: what ComfyUI can take off the
    card leaves it, and the build is refused by name when the card still
    lacks the room). Then transformers reads the weights straight onto the
    card, one tensor at a time (device_map; core_model_loading.py
    _materialize_copy slices a tensor out of the safetensors file and moves
    it, so what RAM holds at any moment is the few tensors in transit, a
    pool of four workers, and the file's pages stay in the kernel's cache
    for the next read; modeling_utils.py caching_allocator_warmup reserves
    the model's bytes on the card before the read, and
    quantizers/quantizer_finegrained_fp8.py keeps FP8 weights as FP8 on a
    card of compute capability 8.9 or more, below that it dequantises them
    to bf16, twice the bytes). Then the model is announced to ComfyUI as
    loaded (_card.announce_on_card), so that ComfyUI takes it off the card
    like any other when a diffusion model needs the room."""
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoProcessor, AutoTokenizer

    path = weights_path(dir_name)
    missing = _missing_requirements(path)
    if missing:
        raise RuntimeError(
            f"{dir_name} needs {', '.join(missing)} in ComfyUI's venv "
            f"(pip install {' '.join(missing)})")

    config = _read_config(path)
    vision = getattr(config, "vision_config", None) is not None
    weight_bytes = _weight_bytes(path)
    device = comfy.model_management.get_torch_device()
    logger.info(f"[AI4ArtsEd LLM] Building {dir_name} ({config.model_type}, vision={vision}, "
                f"{weight_bytes / 2**30:.1f} GB) from {path} onto {device}")
    _card.room_for(weight_bytes, 0, dir_name)

    load_kwargs = dict(config=config, dtype=torch.bfloat16, device_map={"": str(device)})
    if _softcapped(config):
        # transformers picks its sdpa attention where none is asked for, and
        # that one (integrations/sdpa_attention.py) takes no softcap: a model
        # whose config caps its attention logits would run without the cap
        # it was trained with. The eager attention applies it; the GPU
        # service's text backend ran every model of the Text Lab eager.
        load_kwargs["attn_implementation"] = "eager"
    if vision:
        hf = AutoModelForImageTextToText.from_pretrained(path, **load_kwargs)
        processor = AutoProcessor.from_pretrained(path)
        tokenizer = processor.tokenizer
    else:
        hf = AutoModelForCausalLM.from_pretrained(path, **load_kwargs)
        processor = None
        tokenizer = AutoTokenizer.from_pretrained(path)
    hf.eval()

    module = TransformersModule(hf)
    patcher = _card.wrap(module)
    _card.announce_on_card(patcher)

    eos_ids = _stop_ids(getattr(hf.generation_config, "eos_token_id", None), tokenizer.eos_token_id)
    eos_texts = tuple(tokenizer.decode([i]) for i in eos_ids)

    return Built(dir_name=dir_name, path=path, patcher=patcher, module=module,
                 processor=processor, tokenizer=tokenizer, config=config,
                 vision=vision, eos_ids=eos_ids, eos_texts=eos_texts, weight_bytes=weight_bytes)


def _stop_ids(generation_eos: Any, tokenizer_eos: Optional[int]) -> Tuple[int, ...]:
    """The tokens a generation stops at: what the generation config names,
    and the tokenizer's own end-of-turn token beside it.

    A checkpoint without a generation_config.json (Qwen 3.5 4B and 9B) gets
    one derived from its config.json, and that names <|endoftext|> alone;
    the model ends its turn with <|im_end|>, which the tokenizer names as
    its eos token and nothing stopped at. Measured 16.09.2026 with the 9B on
    the chat route: the answer carried the tag ("... Grün.<|im_end|>\\n") and
    the model wrote on until <|endoftext|>. The union is handed to generate as its
    eos_token_id, and the same ids, decoded, are what the answer is stripped
    of (_strip_eos)."""
    ids = generation_eos
    if ids is None:
        ids = []
    elif isinstance(ids, int):
        ids = [ids]
    out = [int(i) for i in ids if i is not None]
    if tokenizer_eos is not None and int(tokenizer_eos) not in out:
        out.append(int(tokenizer_eos))
    return tuple(out)


def _weight_bytes(path: str) -> int:
    """The bytes of the safetensors files the snapshot loads: the shards its
    index names, wherever the index puts them, else the files at its root --
    the same set _snapshot.complete requires."""
    index = os.path.join(path, "model.safetensors.index.json")
    if os.path.isfile(index):
        with open(index) as f:
            shards = set(json.load(f).get("weight_map", {}).values())
        return sum(os.path.getsize(os.path.join(path, s)) for s in shards)
    return sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path)
               if f.endswith(".safetensors"))



def get_built(dir_name: str) -> Built:
    """The built model, built on first use (_build) and gone when ComfyUI
    takes it off the card. Before a build, the oldest built models are
    dropped while KEEP_BUILT already stand (_card.Registry). The build reads
    nothing into RAM whole, which is what the registry's last argument
    says."""
    return _registry.get(dir_name, _build, 0)


# ---------------------------------------------------------------------------
# One generation.

def _pil_images(images: Optional[List[Any]]) -> List[Any]:
    """PIL images from what a caller hands over: PIL images as they are, base64
    strings decoded, ComfyUI IMAGE tensors (B,H,W,C in 0..1) split per item."""
    import base64
    import io
    from PIL import Image

    out = []
    for img in images or []:
        if isinstance(img, Image.Image):
            out.append(img.convert("RGB"))
        elif isinstance(img, str):
            raw = base64.b64decode(img.split(",", 1)[1] if img.startswith("data:") else img)
            out.append(Image.open(io.BytesIO(raw)).convert("RGB"))
        elif isinstance(img, torch.Tensor):
            t = img if img.dim() == 4 else img.unsqueeze(0)
            for one in t:
                arr = (one.detach().cpu().clamp(0, 1).numpy() * 255).round().astype("uint8")
                out.append(Image.fromarray(arr).convert("RGB"))
        else:
            raise TypeError(f"image of type {type(img).__name__} cannot be read")
    return out


def _with_images(messages: List[dict], pils: List[Any]) -> List[dict]:
    """The messages in the form apply_chat_template reads, the pictures placed
    in the first user turn ahead of its text -- the placement the platform's
    callers were written against (gpu_service llm_backend, _build_messages_with_images)."""
    out = []
    placed = not pils
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, str):
            parts = [{"type": "text", "text": content}]
        else:
            parts = list(content)
        if role == "user" and not placed:
            parts = [{"type": "image", "image": p} for p in pils] + parts
            placed = True
        out.append({"role": role, "content": parts})
    if not placed:
        out.append({"role": "user", "content": [{"type": "image", "image": p} for p in pils]})
    return out


class _Stop(StoppingCriteria):
    """A stopping criterion transformers asks after every token: the
    repetition guard fired, or ComfyUI was told to interrupt."""

    def __init__(self, prompt_len: int):
        super().__init__()
        self.prompt_len = prompt_len
        self.generated = 0
        self.repetition = threading.Event()
        self.interrupted = False

    def __call__(self, input_ids, scores, **kwargs):
        self.generated = int(input_ids.shape[1]) - self.prompt_len
        if comfy.model_management.processing_interrupted():
            self.interrupted = True
        done = self.interrupted or self.repetition.is_set()
        return torch.full((input_ids.shape[0],), done, dtype=torch.bool, device=input_ids.device)


class _Finite(LogitsProcessor):
    """Ends the run before a token is taken from scores none can be taken from.

    On 15.09.2026 the 27B FP8 image reader, built by transformers 5.2.0 with
    all 64 gate_proj scales left UNEXPECTED by the loader (Nebenbefund 113),
    answered a picture with scores torch.multinomial refused: its check on
    the device asserted, and after a device-side assert every later CUDA
    call throws. ComfyUI caught the Python exception; three seconds later
    the poisoned context threw in C++ where nothing catches, and the process
    ended -- 2 min 48 s under its core dump until the unit was back, every
    run through ComfyUI with it. The check here reads the scores on the
    host (one small sync per token, next to the two the sampling loop
    already makes) and ends the run in Python, with the cause in the
    sentence. Any other device-side assert still ends the process the same
    way; this covers the one that happened.

    What multinomial refuses is a nan, a +inf, or a row without a finite
    value. A -inf among finite scores is how transformers' own processors
    mask a token (no-repeat n-grams, minimum length, suppressed tokens --
    switched on by a model's generation_config.json and run ahead of this
    one), and softmax turns it into a plain zero, so it passes. A mis-read
    model whose garbage stays finite passes as well; whether a model was
    read whole is a question for the load report.
    """

    def __init__(self, dir_name: str, prompt_len: int):
        self.dir_name = dir_name
        self.prompt_len = prompt_len

    def __call__(self, input_ids, scores):
        bad = (torch.isnan(scores).any() | torch.isposinf(scores).any()
               | (~torch.isfinite(scores).any(dim=-1)).any())
        if bool(bad):
            generated = int(input_ids.shape[1]) - self.prompt_len
            raise RuntimeError(
                f"{self.dir_name} produced scores no token can be taken from (nan, +inf, or a row "
                f"without a finite value) after {generated} generated tokens; the run ends before "
                f"one is taken. Look for a LOAD REPORT for {self.dir_name} in ComfyUI's log first: "
                f"the loader prints one only when it left checkpoint keys UNEXPECTED or MISSING, "
                f"and those weights were not loaded")
        return scores


class _Spoken:
    """The pieces of an answer outside its think block, for the stream.

    A reasoning model thinks between <think> and </think>; both are added
    tokens and reach a piece whole. What stands between them is held back,
    what stands outside is handed on as it comes, so a reader following the
    stream sees the answer and never the tags. Whether the block is already
    open when the first piece arrives is the caller's to say: the chat
    templates of Qwen 3.5 and 3.8 end the prompt with the opener, so the
    model's own text begins inside the block and carries only the closer.
    The whole answer is partitioned the same way at the end (generate).
    """
    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self, in_think: bool = False):
        self.in_think = in_think

    def feed(self, piece: str) -> str:
        out = ""
        while piece:
            if self.in_think:
                _head, tag, piece = piece.partition(self.CLOSE)
                if not tag:
                    return out
                self.in_think = False
            else:
                head, tag, piece = piece.partition(self.OPEN)
                out += head
                if not tag:
                    return out
                self.in_think = True
        return out


def _partition(text: str, opened: bool) -> Tuple[str, Optional[str]]:
    """The whole answer, cut the way _Spoken cuts the stream: what stands
    outside the think block is the content, what stands inside is the
    thinking, and `opened` says whether the block was open before the first
    character. The same walk as _Spoken.feed, so the stream and the content
    agree by construction: text a model writes before its own opener is
    content on both sides, a block the template opened and the model never
    closed is thinking on both sides, and a closer without an opener is
    ordinary text on both sides."""
    spoken, thought = "", ""
    in_think, rest = opened, text
    while rest:
        if in_think:
            head, tag, rest = rest.partition(_Spoken.CLOSE)
            thought += head
            if not tag:
                break
            in_think = False
        else:
            head, tag, rest = rest.partition(_Spoken.OPEN)
            spoken += head
            if not tag:
                break
            in_think = True
    return spoken.strip(), (thought.strip() or None)


def _strip_eos(text: str, eos_texts: Tuple[str, ...]) -> str:
    changed = True
    while changed:
        changed = False
        for e in eos_texts:
            if e and text.endswith(e):
                text = text[:-len(e)]
                changed = True
    return text



def _on_card(built: Built, reserve: int) -> torch.device:
    """Room made and the weights put on the card: the two calls every
    forward pass on a built model makes first (generate, and the readings
    of the Text Lab in _text_probes). Returns the device the model is on.
    force_full_load, in _card.on_card: a transformers model runs whole or
    not at all -- it casts nothing per layer the way comfy.ops modules do,
    so a partial load would leave half of it on the CPU and the forward
    pass would fail on the first tensor that crossed."""
    return _card.on_card(built, reserve, built.dir_name)


def generate(dir_name: str,
             messages: Optional[List[dict]] = None,
             images: Optional[List[Any]] = None,
             prompt: Optional[str] = None,
             temperature: float = 0.7,
             repetition_penalty: Optional[float] = None,
             seed: Optional[int] = None,
             context_tokens: int = DEFAULT_CONTEXT_TOKENS,
             on_token: Optional[Callable[[str], None]] = None,
             enable_thinking: bool = True) -> Dict[str, Any]:
    """One answer of a local model, on the card under ComfyUI's management.

    Returns {"content", "thinking", "finish_reason", "prompt_tokens",
    "completion_tokens"}. finish_reason is "stop" when the model came to its
    own end, "length" when the answer reached the context window, "repetition"
    when it began to loop and was stopped for it. What the model wrote up to
    that point stands. When ComfyUI is told to interrupt, the generation stops
    at the next token and this raises the executor's own interruption, which
    it reports as execution_interrupted.

    The <think> block of a reasoning model is cut off into "thinking" the way
    the platform has always done it: everything before a closing tag is the
    model thinking to itself, and a block that never closed is thinking too --
    the generation ended inside it, and what is left as the answer is what
    stood before the opener, usually nothing. A chat template that ends the
    prompt with the opener (Qwen 3.5, 3.8) opens the block before the model
    writes a token; that is read off the prompt, so an answer that ends
    inside the block comes back as thinking and an empty answer, never as
    the reasoning in the answer's place.

    `enable_thinking` goes to the chat template. With False, a template that
    has the switch (of the installed models: Qwen 3, 3.5, 3.8, SmolLM3) ends
    the prompt with an empty, closed block -- Qwen 3.5 and 3.8 write the
    opener there otherwise -- and the tail of the prompt says the block is
    closed, so nothing of the answer is cut off. Two of them change the
    system text with it as well (Qwen 3.8's reasoning-effort preamble,
    SmolLM3's /think and /no_think). A template without the switch (the
    Qwen3-VL Instruct models, Qwen 2.5) ignores it. A raw prompt has no
    template.

    The pieces of the answer go to on_token as they are written; a think
    block is held back from the stream (_Spoken) and comes back as "thinking".

    `messages` is a conversation and goes through the model's chat template;
    `prompt` is raw text and goes to the model as it is, the completion the
    platform's safety check and its translations were written against. One
    of the two, never both. A raw completion is handed back whole: no chat
    template opened a think block, so none is cut off.
    """
    from transformers import LogitsProcessorList, StoppingCriteriaList, TextIteratorStreamer

    if (messages is None) == (prompt is None):
        raise ValueError("generate takes either messages or prompt")
    for m in messages or []:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, list):
            foreign = [p.get("type") for p in content if isinstance(p, dict) and p.get("type") != "text"]
            if foreign:
                # A picture inside a message (an image_url part, the OpenAI
                # form) would be read by the processor on its own, past the
                # reserve announced below and past the check that the model
                # reads pictures at all. Pictures travel in `images`.
                raise ValueError(f"a message carries {foreign} parts; pictures travel in images=, "
                                 f"messages carry text")
    pils = _pil_images(images)
    if pils:
        # Whether the model reads pictures is in its config, read before
        # any weight is: a check that built a text model (minutes, up to two
        # other built models dropped for it) to refuse the picture afterwards
        # would have spent all of that on a question the config answers.
        if prompt is not None:
            # A picture is placed in the text by the chat template; raw
            # text carries no place for one.
            raise ValueError("a raw prompt takes no pictures; use messages")
        if getattr(_read_config(weights_path(dir_name)), "vision_config", None) is None:
            raise ValueError(f"{dir_name} reads no pictures, and {len(pils)} were attached")
    built = get_built(dir_name)

    # Held for the length of the call: two generations on the same module
    # would interleave in its cache. ComfyUI runs one prompt at a time, so the
    # lock only ever waits for an in-place call from a workflow node.
    with built.lock:
        if prompt is not None:
            if built.vision:
                inputs = built.processor(text=[prompt], images=pils or None, return_tensors="pt")
            else:
                inputs = built.tokenizer(prompt, return_tensors="pt")
        elif built.vision:
            inputs = built.processor.apply_chat_template(
                _with_images(messages, pils), add_generation_prompt=True,
                tokenize=True, return_dict=True, return_tensors="pt",
                enable_thinking=bool(enable_thinking))
        else:
            inputs = built.tokenizer.apply_chat_template(
                messages, add_generation_prompt=True,
                tokenize=True, return_dict=True, return_tensors="pt",
                enable_thinking=bool(enable_thinking))
        prompt_len = int(inputs["input_ids"].shape[1])
        if prompt_len >= context_tokens:
            raise ValueError(
                f"the prompt is {prompt_len} tokens and the context window {context_tokens}; "
                f"nothing is left for the answer")
        # Whether the template left the model inside an open think block:
        # the tail of the prompt as the model reads it. With thinking
        # switched off, the tail is the closer of the empty block the
        # template wrote, and the block counts as closed. Raw text is the
        # caller's own and is partitioned nowhere.
        tail = built.tokenizer.decode(inputs["input_ids"][0, -8:].tolist())
        opened = prompt is None and tail.rstrip().endswith(_Spoken.OPEN)

        reserve = _kv_cache_bytes(built.config, context_tokens)
        if pils:
            reserve += VISION_RESERVE_BYTES
        device = _on_card(built, reserve)
        inputs = {k: (v.to(device) if hasattr(v, "to") else v) for k, v in inputs.items()}

        if seed is not None:
            torch.manual_seed(int(seed))

        streamer = TextIteratorStreamer(built.tokenizer, skip_prompt=True,
                                        skip_special_tokens=False)
        stop = _Stop(prompt_len)
        max_new = int(context_tokens) - prompt_len
        gen_kwargs: Dict[str, Any] = dict(
            max_new_tokens=max_new,
            streamer=streamer,
            stopping_criteria=StoppingCriteriaList([stop]),
            logits_processor=LogitsProcessorList([_Finite(dir_name, prompt_len)]),
            do_sample=temperature > 0,
            pad_token_id=built.tokenizer.pad_token_id if built.tokenizer.pad_token_id is not None
            else built.tokenizer.eos_token_id,
            # Said explicitly: the generation config alone misses the
            # end-of-turn token of a checkpoint that ships none (_stop_ids).
            eos_token_id=list(built.eos_ids),
        )
        if temperature > 0:
            gen_kwargs["temperature"] = float(temperature)
        if repetition_penalty is not None:
            gen_kwargs["repetition_penalty"] = float(repetition_penalty)

        failure: List[BaseException] = []

        def run():
            try:
                with torch.inference_mode():
                    built.module.hf.generate(**inputs, **gen_kwargs)
            except BaseException as e:      # handed to the reading thread below
                failure.append(e)
                streamer.end()

        worker = threading.Thread(target=run, name=f"ai4artsed-llm-{dir_name}", daemon=True)
        worker.start()

        guard = RepetitionGuard()
        spoken = _Spoken(in_think=opened)
        pieces: List[str] = []
        for piece in streamer:
            if not piece:
                continue
            pieces.append(piece)
            if on_token is not None:
                # The stream carries the answer outside its think block, and
                # never the end-of-turn token, which the streamer decodes as
                # text (skip_special_tokens=False keeps the think tags, and
                # with them everything else that is special).
                shown = spoken.feed(piece) if prompt is None else piece
                for eos in built.eos_texts:
                    if eos:
                        shown = shown.replace(eos, "")
                if shown:
                    on_token(shown)
            if guard.feed(piece):
                stop.repetition.set()
                logger.info(f"[AI4ArtsEd LLM] {dir_name} repeated {guard.describe()} and was stopped")
        worker.join()
        if failure:
            raise failure[0]

    if stop.interrupted:
        # ComfyUI's own way of ending a run: the flag is cleared and the
        # executor reports execution_interrupted for this prompt.
        comfy.model_management.throw_exception_if_processing_interrupted()

    text = _strip_eos("".join(pieces), built.eos_texts).strip()
    if stop.repetition.is_set():
        finish = "repetition"
    elif stop.generated >= max_new:
        finish = "length"
    else:
        finish = "stop"

    thinking = None
    if prompt is None:
        text, thinking = _partition(text, opened)

    return {
        "content": text,
        "thinking": thinking,
        "finish_reason": finish,
        "prompt_tokens": prompt_len,
        "completion_tokens": stop.generated,
    }
