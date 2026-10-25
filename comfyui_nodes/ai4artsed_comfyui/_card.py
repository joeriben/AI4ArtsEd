"""One holder for every model the platform's own nodes run.

Stage 6 of the move to ComfyUI: the media stations of the
GPU service -- Stable Audio 3, ImageBind, MMAudio, HeartMuLa, Hunyuan3D, the
readers of media_analysis -- run under ComfyUI's memory management, the way
the local language models have since stage 3 (_local_llm). What the stations
share is here: a torch module wrapped in a ModelPatcher, built once and
kept, put on the card per call with the room the call needs announced up
front (make_room, on_card), and taken off the card again by ComfyUI when a
diffusion model needs the room.

A model ComfyUI takes off the card is released and forgotten
(GoneWhenTakenOff): its weights are freed on the spot, the station that
built it forgets it, and the next call reads it from disk again. ComfyUI's
own way with a model it takes off the card is a copy in RAM
(ModelPatcher.unpatch_model to the offload device). For the platform's
models that filled the machine: after two days of running on 62 GB of RAM
the ComfyUI process stood at 35.5 GB resident and 51.5 GB in swap, and a
27B language model (28.7 GB of weights) was refused for RAM. The kernel's
page cache keeps the files of the models read last in whatever RAM is free
and gives them up without a
swap, so a read from disk again is a read from RAM while the RAM lasts
(measured 2026-09-21: 14 to 15 GB of weights built in 5 to 6 s).

A station keeps what it built in a Registry: `keep` models at most, the
oldest dropped first. A build that reads its weights into RAM whole says how
much (incoming_bytes) and is refused when RAM and swap together cannot hold
them: the kernel's answer to that read would be to kill ComfyUI, and every
run in the room with it. A build that reads onto the card (_local_llm) says
0.

A station also lists the folder its weights live in, under ComfyUI's models
directory (register_folder, listed_dirs, folder_path), the way models/llm is
listed: one folder per model, written by the DevServer's installer from
devserver/config/local_media_weights.json. Nothing here knows a model name;
it lists what is there and loads what it is handed.
"""
import gc
import logging
import math
import os
import threading
import weakref
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import torch

import comfy.model_management
import comfy.model_patcher
import folder_paths

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The folders.

def register_folder(name: str) -> str:
    """The folder <models>/<name>, created and registered with ComfyUI so an
    extra_model_paths.yaml entry of the same name counts too."""
    root = os.path.join(folder_paths.models_dir, name)
    os.makedirs(root, exist_ok=True)
    folder_paths.add_model_folder_path(name, root, is_default=True)
    return root


def listed_dirs(name: str, whole: Callable[[str], bool]) -> List[str]:
    """The folder names under <models>/<name> that `whole` accepts, sorted.
    A dot-folder is a download in flight (the DevServer's installer stages
    under .incoming-<dir> and renames when whole) and is left out."""
    found: List[str] = []
    for base in folder_paths.get_folder_paths(name):
        if not os.path.isdir(base):
            continue
        for entry in sorted(os.listdir(base)):
            if entry.startswith("."):
                continue
            path = os.path.join(base, entry)
            if os.path.isdir(path) and whole(path) and entry not in found:
                found.append(entry)
    return found


def folder_path(name: str, dir_name: str, whole: Callable[[str], bool]) -> str:
    """The folder of a listed model, or an error naming what is there."""
    for base in folder_paths.get_folder_paths(name):
        path = os.path.join(base, dir_name)
        if os.path.isdir(path) and whole(path):
            return path
    raise FileNotFoundError(
        f"no whole model folder {dir_name!r} under {folder_paths.get_folder_paths(name)}; "
        f"listed: {listed_dirs(name, whole)}")


def _walk(path: str):
    """os.walk without the dot-folders: huggingface_hub stages a local_dir
    download under .cache/huggingface/ and moves each file into the folder
    when it is whole, so what a dot-folder holds is never a file of the
    model, and a download that was broken off leaves its parts there."""
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        yield root, dirs, files


def bytes_of_files(path: str) -> int:
    """The bytes of every file of the model, symlinks followed: what RAM
    holds when the model is read whole."""
    total = 0
    for root, _dirs, files in _walk(path):
        for f in files:
            try:
                total += os.stat(os.path.join(root, f)).st_size
            except OSError:
                continue
    return total


# ---------------------------------------------------------------------------
# The module ComfyUI manages.

class Container(torch.nn.Module):
    """The station's torch modules, as the one module ModelPatcher holds.

    ModelPatcher writes `device`, `model_lowvram` and its memory counters onto
    the module it manages, and a library's model may expose `device` as a
    read-only property or keep sub-models in plain attributes. This container
    has none of that: ComfyUI writes on the container, `.to()` moves every
    module registered in it, and module_size counts their parameters through
    it. What a station keeps beside its modules (a processor, a config, a
    pipeline object that points at the modules) goes in Held.extra.
    """

    def __init__(self, **modules: torch.nn.Module):
        super().__init__()
        for name, module in modules.items():
            self.add_module(name, module)

    def get_dtype(self):
        for p in self.parameters():
            return p.dtype
        return torch.float32


class GoneWhenTakenOff(comfy.model_patcher.ModelPatcher):
    """The ModelPatcher over a station's module: a model ComfyUI takes off
    the card is released and forgotten.

    ComfyUI takes a model off the card in LoadedModel.model_unload
    (comfy/model_management.py): a part of it where a part would do
    (partially_unload), else the whole of it (detach, which calls
    unpatch_model with the offload device), and the base class moves the
    weights to the offload device either way: RAM, or under --highvram the
    card itself, where nothing moves. Here nothing is given up in part -- a
    library's model runs whole or not at all (on_card, force_full_load), and
    a half moved to RAM is pinned there (partially_unload pins each parameter
    it moves) and moved back module by module at the next load -- and the
    whole is released: the station that built the model forgets it (forget),
    and the weights go to the meta device, which gives their memory back to
    the card inside the same call, so the room ComfyUI is freeing is free
    before it loads what it is freeing it for.

    unpatch_model with weights and a device other than the card is the one
    path a model leaves the card by; detach calls it so, from
    LoadedModel.model_unload and from partially_load when a load fails.
    partially_load with the patches unchanged calls it without weights, which
    goes to the base class and moves nothing; __del__ calls detach without
    unpatching. A load of a released model (partially_load with the patches
    changed, which a station's model never sees) is refused with the cause
    (load), where the base class would fail on the first meta tensor.
    """

    def partially_unload(self, device_to, memory_to_free=0, force_patch_weights=False):
        return 0

    def load(self, device_to=None, lowvram_model_memory=0, force_patch_weights=False, full_load=False):
        if any(p.device.type == "meta" for p in self.model.parameters()):
            raise RuntimeError(
                f"{self.model.__class__.__name__} was taken off the card by ComfyUI and released; "
                f"the station that built it reads it again on its next call")
        return super().load(device_to=device_to, lowvram_model_memory=lowvram_model_memory,
                            force_patch_weights=force_patch_weights, full_load=full_load)

    def unpatch_model(self, device_to=None, unpatch_weights=True):
        if not (unpatch_weights and device_to is not None and device_to != self.load_device):
            return super().unpatch_model(device_to=device_to, unpatch_weights=unpatch_weights)
        # The base class's whole unload, with the move to device_to replaced
        # by the release. Backed-up weights (a patch's originals) are not
        # restored: there is no model left to restore them into.
        self.eject_model()
        self.unpatch_hooks()
        self.unpin_all_weights()
        self.backup.clear()
        forget(self)
        self.model.to("meta")
        # A tensor a library keeps as a plain attribute (the computed
        # `weight` of torch.nn.utils.weight_norm, which stable_audio_tools'
        # autoencoders use) is outside Module.to; it leaves the card here too.
        for m in self.model.modules():
            for k, v in list(vars(m).items()):
                if isinstance(v, torch.Tensor) and v.device.type != "meta":
                    setattr(m, k, v.to("meta"))
        self.model.device = device_to
        self.model.model_lowvram = False
        self.model.lowvram_patch_counter = 0
        self.model.current_weight_patches_uuid = None
        self.model.model_loaded_weight_memory = 0
        self.model.model_offload_buffer_memory = 0
        for m in self.model.modules():
            if hasattr(m, "comfy_patched_weights"):
                del m.comfy_patched_weights
        self.object_patches_backup.clear()


def wrap(module: torch.nn.Module) -> Any:
    """The ModelPatcher over a module: loaded to the card ComfyUI runs on,
    gone when ComfyUI takes it off (GoneWhenTakenOff)."""
    return GoneWhenTakenOff(
        module,
        load_device=comfy.model_management.get_torch_device(),
        offload_device=comfy.model_management.unet_offload_device(),
    )


def announce_on_card(patcher: Any) -> None:
    """A model a station read onto the card itself, announced to ComfyUI.

    load_models_gpu is the one call that registers a model with ComfyUI's
    accounting (current_loaded_models), and it loads what the patcher's
    counters say is not loaded yet. The counters are written here the way
    ModelPatcher.load writes them after a full load, so the registration
    moves nothing and asks the card for nothing beyond the inference margin,
    and from then on ComfyUI takes the model off the card like any other.
    """
    module = patcher.model
    module.device = patcher.load_device
    module.model_lowvram = False
    module.lowvram_patch_counter = 0
    module.model_loaded_weight_memory = patcher.model_size()
    module.model_offload_buffer_memory = 0
    module.current_weight_patches_uuid = patcher.patches_uuid
    comfy.model_management.load_models_gpu([patcher], force_full_load=True)


def module_bytes(module: torch.nn.Module) -> int:
    """The bytes of a module's parameters and buffers, what it weighs on
    either device."""
    total = 0
    for t in list(module.parameters()) + list(module.buffers()):
        total += t.numel() * t.element_size()
    return total


@dataclass
class Held:
    """A built model of a station: the patcher over its container, and what
    the station keeps beside it."""
    key: str
    patcher: Any
    module: torch.nn.Module
    weight_bytes: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


# ---------------------------------------------------------------------------
# The registries.

_registries: List["Registry"] = []
_build_lock = threading.RLock()
_use_counter = 0

# The models ComfyUI took off the card since a station last asked for one:
# forgotten by their registry inside free_memory's walk (forget), let go of
# by the next get() (_let_go), outside it. What waits here holds no weights
# (they went to the meta device); a language model's tokenizer, processor
# and config stay with it until then.
_taken_off: List[Any] = []


def _drop_held(name: str, key: str, held: Any, why: str) -> None:
    """Forget a built model. Its weights leave the card with the last
    reference: ComfyUI holds only a weak reference to it (LoadedModel),
    and cleanup_models_gc collects what a cycle keeps. A reference that
    survives -- a thread still in a generation, a traceback held somewhere
    -- keeps the weights where they are, and that is said in the log rather
    than counted as freed."""
    logger.info(f"[AI4ArtsEd {name}] Dropping {key} "
                f"({getattr(held, 'weight_bytes', 0) / 2**30:.1f} GB): {why}")
    alive = weakref.ref(held.module)
    del held
    gc.collect()
    comfy.model_management.cleanup_models_gc()
    if alive() is not None:
        logger.warning(f"[AI4ArtsEd {name}] {key} is still referenced after being dropped; "
                       f"its weights stay where they are until that reference goes")


class Registry:
    """The built models of one station, `keep` at most.

    get() returns the built model, built on first use by `build(key)`. Before
    a build, this station's oldest models are dropped while `keep` already
    stand. A build that reads its weights into RAM whole says how much
    (incoming_bytes) and is refused, with the three numbers, when RAM and
    swap together cannot hold them: the kernel's answer to that read would
    be to kill ComfyUI, and every run in the room with it. A build that
    reads onto the card says 0. A model _local_llm builds is on the card
    from the build; the other stations build in RAM and put the model on the
    card at the first call (on_card). Either way, what ComfyUI takes off the
    card is forgotten (forget) and built again on the next call.
    """

    def __init__(self, name: str, keep: int):
        self.name = name
        self.keep = keep
        self._held: Dict[str, Any] = {}
        self._stamp: Dict[str, int] = {}
        _registries.append(self)

    def keys(self) -> List[str]:
        return list(self._held)

    def peek(self, key: str) -> Optional[Any]:
        return self._held.get(key)

    def _oldest(self) -> Optional[str]:
        if not self._held:
            return None
        return min(self._stamp, key=self._stamp.get)

    def _touch(self, key: str) -> None:
        global _use_counter
        _use_counter += 1
        self._stamp[key] = _use_counter

    def drop(self, key: str, why: str) -> None:
        with _build_lock:
            self._stamp.pop(key, None)
            # No name for the model in this frame: a local would hold it
            # through _drop_held's collection, and the weights with it.
            _drop_held(self.name, key, self._held.pop(key), why)


    def forget_key(self, key: str, why: str) -> None:
        """Forget a built model without collecting anything: its weights are
        released where this is called from (GoneWhenTakenOff), and its last
        reference goes at the next get() (_taken_off, see forget)."""
        with _build_lock:
            held = self._held.pop(key, None)
            self._stamp.pop(key, None)
            if held is not None:
                _taken_off.append(held)
                logger.info(f"[AI4ArtsEd {self.name}] Forgetting {key} "
                            f"({getattr(held, 'weight_bytes', 0) / 2**30:.1f} GB): {why}")

    def get(self, key: str, build: Callable[[str], Any], incoming_bytes: int) -> Any:
        with _build_lock:
            _let_go()
            if key in self._held:
                self._touch(key)
                return self._held[key]
            while len(self._held) >= self.keep:
                self.drop(self._oldest(), f"{self.keep} stay built at most, {key} is next")
            if incoming_bytes > 0:
                import psutil
                available = int(psutil.virtual_memory().available)
                swap_free = int(psutil.swap_memory().free)
                if available + swap_free < incoming_bytes:
                    raise RuntimeError(
                        f"{key} weighs {incoming_bytes / 2**30:.1f} GB read into RAM, and "
                        f"{available / 2**30:.1f} GB of RAM and {swap_free / 2**30:.1f} GB of swap "
                        f"are free: the read cannot complete")
            held = build(key)
            self._held[key] = held
            self._touch(key)
            return held


def _let_go() -> None:
    """The last reference to the models ComfyUI took off the card goes here,
    outside free_memory's walk (_taken_off, see forget)."""
    del _taken_off[:]


def forget(patcher: Any) -> None:
    """The station that built the model over `patcher` forgets it; the next
    call builds it again. Called by the patcher as ComfyUI takes the model
    off the card (GoneWhenTakenOff.unpatch_model), inside
    comfy.model_management.free_memory's walk over current_loaded_models by
    index. Nothing here collects garbage, and the forgotten model waits in
    _taken_off until the next get(): the walk reads the patcher after
    model_unload returns (current_loaded_models[i].model.model, a weak
    reference) and pops the entry by index after its loop, so a patcher
    whose last reference went here would be None there, and a module dying
    here would fire cleanup_models under the walk, which pops the entry and
    shifts the indices the walk still uses; a collection here could do the
    same for a model dropped earlier. A patcher no station holds is nobody's
    to forget."""
    for registry in _registries:
        for key, held in list(registry._held.items()):
            if held.patcher is patcher:
                registry.forget_key(key, "taken off the card by ComfyUI; read again on the next call")


# ---------------------------------------------------------------------------
# The card.

def _no_room(name: str, needed: int, to_load: int, reserve: int, free: int) -> str:
    """The refusal, opening with the words the DevServer's router reads a
    card fault by (backend_router._is_card_fault: "out of memory"), so that a
    run refused for room is answered as such and not retried on a fallback
    chunk."""
    return (f"out of memory on the card for {name}: {needed / 2**30:.1f} GB needed "
            f"({to_load / 2**30:.1f} GB of weights to load and {reserve / 2**30:.1f} GB of "
            f"reserve for the run), {free / 2**30:.1f} GB free "
            f"after every other model was taken off")


def make_room(held: Any, reserve: int, name: str) -> None:
    """Free the card for this model and its reserve, or refuse by name.

    load_models_gpu frees what it can and then loads; it never says no. A
    model that has no room after everything else left the card is half
    moved when the allocator fails, the executor unloads every model to
    recover, and the error names none of the numbers. So the freeing is
    asked for here first, with this model's own loaded part kept, and the
    load is refused when the card still lacks the room -- before any weight
    moves.
    """
    mm = comfy.model_management
    to_load = held.patcher.model_size() - held.patcher.loaded_size()
    ours = [lm for lm in mm.current_loaded_models if lm.model is held.patcher]
    room_for(to_load, reserve, name, keep=ours)


def room_for(to_load: int, reserve: int, name: str, keep: Optional[List[Any]] = None) -> None:
    """Free the card for `to_load` bytes of weights and `reserve` beside
    them, with the loaded models in `keep` kept, or refuse by name
    (_no_room). make_room asks for the part of a built model that is not on
    the card yet; a station that reads weights onto the card itself asks
    for all of them before the read (_local_llm._build)."""
    mm = comfy.model_management
    device = mm.get_torch_device()
    # ceil: load_models_gpu asks free_memory for to_load * 1.1 as a float,
    # and a floor here could leave it a fraction of a byte short, for which
    # it would take another station's whole model off.
    needed = math.ceil(to_load * 1.1) + max(mm.minimum_inference_memory(),
                                            reserve + mm.extra_reserved_memory())
    mm.free_memory(needed, device, keep_loaded=keep or [])
    free = mm.get_free_memory(device)
    if free < needed:
        # What a build that failed on the card left behind sits in the
        # frames of its traceback, and ComfyUI's execute binds that
        # traceback in one of those frames (execution.py, `typ, _, tb =
        # sys.exc_info()`): a cycle, freed by a collection alone. ComfyUI
        # collects on its own only when a loaded model is dead
        # (cleanup_models_gc), which such a build never registered.
        gc.collect()
        mm.soft_empty_cache()
        free = mm.get_free_memory(device)
    if free < needed:
        raise RuntimeError(_no_room(name, needed, to_load, reserve, free))


def on_card(held: Any, reserve: int, name: str) -> torch.device:
    """Room made and the weights put on the card: the two calls every
    forward pass on a built model makes first. Returns the device the model
    is on."""
    make_room(held, reserve, name)
    # The one call that puts weights on the card. force_full_load: a
    # library's model runs whole or not at all -- it casts nothing per layer
    # the way comfy.ops modules do, so a partial load would leave half of it
    # on the CPU and the forward pass would fail on the first tensor that
    # crossed.
    comfy.model_management.load_models_gpu([held.patcher], memory_required=reserve,
                                           force_full_load=True)
    return held.patcher.load_device


def on_card_together(helds: List[Any], reserve: int, name: str) -> torch.device:
    """Two or more built models on the card in one load: the room for all
    of them is made first, with every one of them kept, so that loading the
    second cannot take the first off again."""
    mm = comfy.model_management
    to_load = sum(h.patcher.model_size() - h.patcher.loaded_size() for h in helds)
    ours = [lm for lm in mm.current_loaded_models if any(lm.model is h.patcher for h in helds)]
    room_for(to_load, reserve, name, keep=ours)
    mm.load_models_gpu([h.patcher for h in helds], memory_required=reserve, force_full_load=True)
    return helds[0].patcher.load_device


def autograd_ready(*modules: torch.nn.Module) -> None:
    """Weights a gradient can pass through.

    ComfyUI runs every node under torch.inference_mode(). A tensor made
    there is an inference tensor, and a parameter that took one through
    `.data` (Module.to does that) keeps no version counter: autograd
    refuses to save it for backward, and a view of it outside inference
    mode fails. The stations build and move their models inside node
    calls, so a station that differentiates through a model (the guided
    Stable Audio sampling) calls this after on_card, inside
    torch.inference_mode(False): every parameter and buffer is rebuilt as
    a new tensor object from a clone made in normal mode, on the device
    it already sits on. is_inference() does not tell the two apart
    (checked on torch 2.12: it answers False after a `.data` assignment
    while the view still fails), so all of them are rebuilt, each call.
    The gradient wanted is the latent's: the parameters are rebuilt with
    requires_grad=False, so a backward through the model allocates no
    weight-sized .grad on the card.
    """
    if torch.is_inference_mode_enabled():
        raise RuntimeError("autograd_ready is called inside torch.inference_mode(False)")
    with torch.no_grad():
        for module in modules:
            for mod in module.modules():
                for name, p in list(mod.named_parameters(recurse=False)):
                    mod._parameters[name] = torch.nn.Parameter(p.detach().clone(), requires_grad=False)
                for name, b in list(mod.named_buffers(recurse=False)):
                    mod._buffers[name] = b.detach().clone()


def interrupted() -> None:
    """Raise ComfyUI's interrupt where a station loops over steps, so a
    cancelled run stops between steps instead of at its end."""
    comfy.model_management.throw_exception_if_processing_interrupted()
