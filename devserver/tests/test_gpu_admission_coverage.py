#!/usr/bin/env python3
"""Nobody infers a single bit outside the admission gate.

A plant rule without a count is an intention. This is the count.

The gate — since stage 7 of the move to ComfyUI the DevServer's
(devserver/my_app/services/gpu_gate.py), which the GPU service's own
(gpu_service/services/gpu_admission.py) leases for every hold of its until
stage 8 — hands out one slot for the whole card, and the VRAM coordinator
decides what to evict from what it believes is resident. Both are only ever right about memory they were told
about. On 2026-08-18 the gate was wired into seven consumers and three were
passed over without a word; the Latent Text Lab then ran six months of
unserialised forward passes on a shared model object and answered with
hidden-state counts of 35, 15, 59, 5, 2, 18, 38 and 15 where 37 is the only
right number. Nothing in the tree would have found that, because nothing was
counting.

HOW A ROUTE IS COVERED. Two shapes exist on this platform and both are fine:

  * the route takes the slot itself (mmaudio, cross-aesthetic), or
  * the route hands over to a backend method that takes it (diffusers, which
    holds it across load and forward together).

So the check follows the call one level: for every backend method a route
calls, it looks that method up in the backend module and asks whether IT
reaches the gate. A method that touches no weights says so in
READ_ONLY_METHODS, once, with the reason.

FAIL-CLOSED IN THREE DIRECTIONS:

  * A route reaches the gate, or stands in READ_ONLY_ROUTES with a reason.
  * A module importing a model library stands in MODEL_MODULES.
  * A separate process putting weights on the card stands in REMOTE_CONSUMERS
    and its caller takes a remote lease.
  * Whoever starts a process at all stands in SUBPROCESS_STARTERS and says
    whether that process meets the card.

Writing a name into one of those tables is a decision somebody made and can be
read back. That is the entire point: an exception with a reason is a decision,
an exception without one is the 2026-08-18 mistake happening again.

Usage:
    python3 devserver/tests/test_gpu_admission_coverage.py            # whole tree
    python3 devserver/tests/test_gpu_admission_coverage.py --staged   # pre-commit
"""

import ast
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROUTES_DIR = os.path.join("gpu_service", "routes")
SERVICES_DIR = os.path.join("gpu_service", "services")
DEVSERVER_SERVICES = os.path.join("devserver", "my_app", "services")

# What counts as reaching the gate. Recognised as a CALL, never as a bare word:
# 'slot' is an ordinary variable name - the BBQ probe fills template slots - and
# a check that matched the word waved that route through as covered.
# Only 'slot' has to be seen as a call: the others are distinctive enough that
# naming them means using them, and they are routinely HANDED OVER rather than
# called - asyncio.to_thread(run_admitted, 'heartmula', model_id, 0, _generate).
GATE_CALLS = {"slot"}
GATE_MENTIONS = {"run_admitted", "gpu_lease", "gpu_lease_sync"}
GATE_DECORATORS = {"gated"}

# Libraries whose presence means the module can put weights on the card.
# Import-level, so no way of calling them hides the fact.
MODEL_LIBRARIES = {
    "torch", "transformers", "diffusers", "llama_cpp", "onnxruntime",
    "sentence_transformers", "vllm", "ctransformers", "exllamav2",
    "voxcpm", "heartlib", "imagebind", "hunyuan3d", "mmaudio",
}

# Route files that serve the machine room rather than the card. Each says why.
INFRASTRUCTURE_ROUTES = {
    "health_routes.py": "reports free memory and foreign processes, allocates none",
    "__init__.py": "no routes",
}

# Routes that touch no weights, named one by one so that adding one is visible.
READ_ONLY_ROUTES = {
    "diffusers_routes.py:generation_progress": "reads a progress counter",
    "diffusers_routes.py:cancel": "sets a flag another run reads; must be served WHILE the card is busy",
    "diffusers_routes.py:available": "reports whether the backend imported, and the model id it falls back to",
    "diffusers_routes.py:gpu_info": "reads memory figures off the driver",
    "cross_aesthetic_routes.py:semantic_axes": "reads the axis definitions off disk",
}

# Backend methods a route may call without a slot: they read state, never the
# card. Keyed by module, so one name cannot excuse another module's method.
READ_ONLY_METHODS = {
    "diffusers_backend.py": {
        "is_available", "get_gpu_info", "get_progress", "list_models",
        "get_loaded_models", "get_model_info",
    },
    "mmaudio_backend.py": {"is_available", "get_status"},
    "stable_audio_backend.py": {"is_available", "get_status"},
    "cross_aesthetic_backend.py": {"is_available", "get_status", "semantic_axes"},
}

# Every module importing a model library, and what covers it.
MODEL_MODULES = {
    "diffusers_backend.py": "gate: its own slot() for the load and one for the forward, the model kept from eviction between them by its refcount (PART 27)",
    "mmaudio_backend.py": "gate: mmaudio_routes.py",
    "stable_audio_backend.py": "gate: cross_aesthetic_routes.py, loaded for the synth",
    "stable_audio_model.py": "gate: cross_aesthetic_routes.py, loaded by stable_audio_backend",
    "cross_aesthetic_backend.py": "gate: cross_aesthetic_routes.py",
    "imagebind_backend.py": "gate: cross_aesthetic_routes.py, loaded by cross_aesthetic_backend",
    "attention_processors_sd3.py": "gate: diffusers_routes.py, loaded by diffusers_backend",
    "embedding_analyzer.py": "gate: diffusers_routes.py, called from diffusers_backend",
    "vram_coordinator.py": "the coordinator itself: it evicts, it never generates",
    # The one exception with a reason, from 941739df: what children see waits
    # for no video. Its model load asks for the slot with a short deadline and
    # goes ahead without it; its forward pass runs ungated on purpose.
    "llm_backend.py": "DECLARED EXCEPTION - safety chain, gated on load only (941739df)",
    # The engine that took over from it (LLM_ENGINE=child, the default). Same
    # exception, same reason: what children see waits for no video. The weights
    # now live in a child process, so what is gated here is the SPAWN - with the
    # same short deadline, and the same willingness to go ahead unserialized
    # rather than let a content check queue behind a render. Its forward pass is
    # ungated on purpose, as before.
    "llm_child_backend.py": "DECLARED EXCEPTION - safety chain, gated on the child spawn only (941739df)",
    # Process work only: it starts, watches and ends the children the module
    # above gates, and reads NVML per PID so the coordinator can book them. It
    # allocates nothing itself.
    "llm_child.py": "no gate: spawns, watches and reaps processes, allocates nothing",
}

# Route files exempt from the per-route check, with the reason.
EXEMPT_ROUTE_FILES = {
    "llm_routes.py": "DECLARED EXCEPTION - safety chain, see llm_backend.py (941739df)",
}

# Processes outside the GPU service that put weights on the card. They cannot
# take a slot, so a remote lease covers them: taken by the process itself
# over the gate's HTTP API, or by the DevServer caller that queues its work.
REMOTE_CONSUMERS = {
    # The VoxCPM2 worker takes voxcpm-load itself, in stdlib, before its
    # weights go on the card, whoever started it (finding S-005 of the code review of 2026-10-10); until
    # then the DevServer took it around the start, and only when it started
    # the worker. The utterance's lease stays in voxcpm_backend.speak.
    os.path.join("voxcpm_service", "server.py"):
        os.path.join("voxcpm_service", "server.py"),
    # ComfyUI's process, since the move to ComfyUI: the platform's node
    # package puts a language model
    # on the card for one answer (stage 3, _local_llm) and reads it for the
    # Text Lab (stage 5, _text_probes: the option scores and Representation
    # Engineering). Every prompt the DevServer queues there takes the remote
    # lease in comfyui_ws_client (_with_gpu_lease around submit_and_track),
    # keyed by the model the prompt names, so the gate books the run before
    # ComfyUI loads anything. A workflow run from ComfyUI's own page takes
    # none, as with every other node there.
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_local_llm.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_text_probes.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    # The media stations (stage 6): Stable Audio 3 and the synth over its
    # conditioning space, ImageBind for the guided generation, MMAudio,
    # HeartMuLa, Hunyuan3D 2 and the media readers. Each puts its weights on
    # the card through ComfyUI's own model management (_card), and every
    # prompt the DevServer queues for one of them takes the same remote lease
    # in comfyui_ws_client, keyed by the folder the node's model_name names.
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_stable_audio.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_audio_synth.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_imagebind.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_mmaudio.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_heartmula.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_hunyuan3d.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
    os.path.join("comfyui_nodes", "ai4artsed_comfyui", "_media_reading.py"):
        os.path.join(DEVSERVER_SERVICES, "comfyui_ws_client.py"),
}

# The DevServer process runs nothing on the card. Whatever imports a model
# library here is a mistake, or a decision written down.
# A file marked DECOMMISSIONED here has to STAY unimported. The word on its own
# is a label; what makes it a fact is this table plus check_decommissioned.
DEVSERVER_MODEL_MODULES = {
    "supertonic_backend.py": "DECLARED EXCEPTION - ONNX Runtime on the CPU, the card stays free",
    "backend_registry.py": "torch.cuda only: reads device properties, allocates nothing",
    "training_service.py": "torch.cuda only; the training itself is a subprocess and takes a lease",
    "heartmula_backend.py": "the factory returns the client of the node on ComfyUI",
}


# Work the DevServer starts as its OWN PROCESS. The census could not see this
# class at all: it scanned modules for model libraries and routes for the slot,
# and a training started with subprocess.Popen has neither. RAVE was found that
# way on 2026-08-26 - hours of GPU training, kicked off by a periodic tick from
# any open admin page, with the gate believing the card free. RAVE itself left
# the platform on 2026-09-10 (it moved to joeriben/rave_research); the class of
# work it stands for did not, which is why this table stays.
#
# Every file in the DevServer that starts a process says here whether that
# process meets the card. A new one that says nothing fails this test.
SUBPROCESS_STARTERS = {
    # holds a lease for as long as the outside process runs
    "training_service.py": "lease: lora_training, held across the run",
    "voxcpm_backend.py": "lease: voxcpm around each utterance; the worker it starts takes voxcpm-load itself over the gate's HTTP API (finding S-005 of the code review of 2026-10-10)",
    "blender_service.py": "lease: blender around the EEVEE render",
    "settings_routes.py": "lease: comfyui-load around the preload",
    "knowledge_ingest_service.py": "lease: docling, held across the Docling subprocess run (UCD-141); a Markdown passthrough imports no converter and the reindex step is sqlite only, so neither takes one",
    "scene_ingest_service.py": "lease: docling, held across the Docling subprocess run (UCD-141) — the same venv as knowledge_ingest_service, whose OCR stack the UCD-132 E2E of 2026-09-27 saw selecting cuda:0",
    "comfyui_manager.py": "starts the ComfyUI process; its runs take leases in comfyui_ws_client",
    # never meets the card
    "dev_routes.py": "developer tooling on this machine",
    "knowledge_routes.py": "rebuilds the knowledge FTS index; sqlite only, no model library",
    "training_routes.py": "drives training_service, which holds the lease",
    "espeak_backend.py": "speech on the CPU",
    "piper_backend.py": "speech on the CPU: the `piper` binary of its own venv, no CUDA provider",
    "post_production_service.py": "ffmpeg, on the CPU",
    "thumbnails.py": "image scaling, on the CPU",
    "watermark_service.py": "image compositing, on the CPU",
    "resona_hardware.py": "reads what hardware is present",
}

STARTS_A_PROCESS = ("subprocess.Popen", "subprocess.run", "subprocess.check")


def _read(path):
    with open(os.path.join(REPO, path), "r", encoding="utf-8") as handle:
        return handle.read()


def _names_used(node):
    """Every name and attribute mentioned inside this node."""
    used = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name):
            used.add(inner.id)
        elif isinstance(inner, ast.Attribute):
            used.add(inner.attr)
    return used


def _reaches_gate(node):
    """Does this function ask the gate for the slot, or hold a lease?"""
    for deco in node.decorator_list:
        call = deco.func if isinstance(deco, ast.Call) else deco
        name = call.attr if isinstance(call, ast.Attribute) else getattr(call, "id", "")
        if name in GATE_DECORATORS:
            return True
    if _names_used(node) & GATE_MENTIONS:
        return True
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in GATE_CALLS:
            return True
    return False


def _under_their_own_names(node):
    """Undo `from x import y as z`, for names used inside this node.

    Two diffusers routes import their algebra function as _gomd and _gpm; read
    literally, they call something that exists nowhere, and a check that stopped
    at the written name would report both as running outside the gate.
    """
    aliases = {}
    for inner in ast.walk(node):
        if isinstance(inner, (ast.Import, ast.ImportFrom)):
            for alias in inner.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name.split(".")[-1]
    return aliases


def _called_names(node):
    """Everything this node calls, by name.

    Both shapes count: backend.generate(...) and a plain run_algebra_mode(...)
    imported from another module.
    """
    called = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        if isinstance(inner.func, ast.Attribute):
            called.add(inner.func.attr)
        elif isinstance(inner.func, ast.Name):
            called.add(inner.func.id)
    return called


def _functions(tree):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _route_functions(tree):
    """Functions carrying a Flask route decorator, with their decorator names."""
    found = []
    for node in _functions(tree):
        names, is_route = set(), False
        for deco in node.decorator_list:
            call = deco.func if isinstance(deco, ast.Call) else deco
            if isinstance(call, ast.Attribute):
                names.add(call.attr)
                if call.attr == "route":
                    is_route = True
            elif isinstance(call, ast.Name):
                names.add(call.id)
        if is_route:
            found.append((node, names))
    return found


_METHOD_CACHE = {}
_GLOBAL_GATED = None


def _globally_gated_names():
    """Method names that reach the gate, from every model module at once.

    diffusers_routes has module-level helpers that hand their forward pass to
    diffusers' _locked_generate. A closure that stopped at the module border
    would report all of those as uncovered.
    """
    global _GLOBAL_GATED
    if _GLOBAL_GATED is None:
        homes, gated_in = {}, set()
        for filename in sorted(MODEL_MODULES):
            rel = os.path.join(SERVICES_DIR, filename)
            if not os.path.exists(os.path.join(REPO, rel)):
                continue
            tree = ast.parse(_read(rel), filename=rel)
            for node in _functions(tree):
                homes.setdefault(node.name, set()).add(filename)
                if _reaches_gate(node):
                    gated_in.add(node.name)
        # Only names that exist in exactly ONE module travel. Two backends both
        # call theirs _load_pipeline, one of them holds the slot and the other
        # does not - and a name shared that way would vouch for the wrong one.
        _GLOBAL_GATED = {name for name in gated_in if len(homes.get(name, ())) == 1}
    return _GLOBAL_GATED


def _methods_reaching_gate(module_filename):
    """Which methods of a backend module reach the gate, and which exist at all.

    Transitively: a method reaches the gate when it names it, or when it calls
    another method of the same module that does. Diffusers is built that way -
    the generate methods hand over to one helper that holds the slot across
    load and forward - and a check that only looked one level deep would call
    every one of them uncovered.
    """
    if module_filename in _METHOD_CACHE:
        return _METHOD_CACHE[module_filename]
    rel = os.path.join(SERVICES_DIR, module_filename)
    gated, present, calls = set(), set(), {}
    if os.path.exists(os.path.join(REPO, rel)):
        tree = ast.parse(_read(rel), filename=rel)
        # A gated name from another module counts here only where this module
        # defines nothing of that name itself. Several backends have a
        # load_model, and one of them being gated says nothing about the rest.
        own = {node.name for node in _functions(tree)}
        gated |= (_globally_gated_names() - own)
        for node in _functions(tree):
            present.add(node.name)
            # Mentions, not just calls: a helper handed to
            # asyncio.to_thread(self._locked_generate, fn) is passed,
            # never called here, and a closure over calls alone would
            # report every diffusers generation as uncovered.
            calls[node.name] = _names_used(node)
            if _reaches_gate(node) or (_names_used(node) & gated):
                gated.add(node.name)
        while True:
            grown = {name for name, called in calls.items() if called & gated}
            if grown <= gated:
                break
            gated |= grown
    _METHOD_CACHE[module_filename] = (gated, present)
    return gated, present


def _backends_imported(tree):
    """Model modules this route file imports, as filenames."""
    imported = set()
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        for module in modules:
            leaf = module.split(".")[-1] + ".py"
            if leaf in MODEL_MODULES:
                imported.add(leaf)
    return imported


def check_routes(only=None):
    problems = []
    routes_path = os.path.join(REPO, ROUTES_DIR)
    for filename in sorted(os.listdir(routes_path)):
        if not filename.endswith(".py"):
            continue
        if filename in INFRASTRUCTURE_ROUTES or filename in EXEMPT_ROUTE_FILES:
            continue
        rel = os.path.join(ROUTES_DIR, filename)
        if only is not None and rel not in only:
            continue
        tree = ast.parse(_read(rel), filename=rel)
        reaching = _globally_gated_names() - {n.name for n in _functions(tree)}
        helpers = {n.name for n in _functions(tree)
                   if _reaches_gate(n) or (_names_used(n) & reaching)}
        local_calls = {n.name: _names_used(n) for n in _functions(tree)}
        while True:
            grown = {name for name, called in local_calls.items() if called & helpers}
            if grown <= helpers:
                break
            helpers |= grown
        backends = _backends_imported(tree)

        for node, decorators in _route_functions(tree):
            key = "%s:%s" % (filename, node.name)
            if key in READ_ONLY_ROUTES:
                continue
            reachable = _names_used(node) | decorators
            aliases = _under_their_own_names(node)
            reachable |= {aliases[name] for name in reachable if name in aliases}
            if _reaches_gate(node) or (reachable & reaching) or (reachable & helpers):
                continue

            # The route hands over. Follow every call it makes into the backends
            # this file imports, and ask what those methods do.
            called = _called_names(node)
            called |= {aliases[name] for name in called if name in aliases}
            unaccounted = []
            covered = False
            for backend in sorted(backends):
                gated, present = _methods_reaching_gate(backend)
                read_only = READ_ONLY_METHODS.get(backend, set())
                for method in sorted(called & present):
                    if method in gated:
                        covered = True
                    elif method not in read_only:
                        unaccounted.append("%s.%s" % (backend, method))
            if covered and not unaccounted:
                continue

            if unaccounted:
                problems.append(
                    "%s:%d  route '%s' calls %s, and none of those takes the slot.\n"
                    "    Take it in the route, or in the method, or name the "
                    "method in READ_ONLY_METHODS with the reason it touches no "
                    "weights." % (rel, node.lineno, node.name, ", ".join(unaccounted))
                )
            else:
                problems.append(
                    "%s:%d  route '%s' reaches the gate on no path.\n"
                    "    Take the slot in the route, or name it in "
                    "READ_ONLY_ROUTES with the reason it touches no weights."
                    % (rel, node.lineno, node.name)
                )

        if filename not in {*INFRASTRUCTURE_ROUTES, *EXEMPT_ROUTE_FILES} and not backends:
            continue
    return problems


def _imports_model_library(rel):
    tree = ast.parse(_read(rel), filename=rel)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in MODEL_LIBRARIES:
                    return alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in MODEL_LIBRARIES:
                return node.module.split(".")[0]
    return None


def check_modules(only=None):
    problems = []
    for directory, table, where in (
        (SERVICES_DIR, MODEL_MODULES, "MODEL_MODULES"),
        (DEVSERVER_SERVICES, DEVSERVER_MODEL_MODULES, "DEVSERVER_MODEL_MODULES"),
    ):
        full = os.path.join(REPO, directory)
        if not os.path.isdir(full):
            continue
        for filename in sorted(os.listdir(full)):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            rel = os.path.join(directory, filename)
            if only is not None and rel not in only:
                continue
            library = _imports_model_library(rel)
            if library is None or filename in table:
                continue
            problems.append(
                "%s  imports '%s' and stands in no table.\n"
                "    Put it in %s with the route that covers it, or with the "
                "reason it needs none." % (rel, library, where)
            )
    return problems


def check_remote(only=None):
    problems = []
    for worker, client in REMOTE_CONSUMERS.items():
        if only is not None and client not in only and worker not in only:
            continue
        if not os.path.exists(os.path.join(REPO, client)):
            problems.append("%s  is gone; %s has no gated caller left." % (client, worker))
            continue
        # A call, not a name: the VoxCPM worker defines its own gpu_lease, and
        # the substring would hold with the call at _load deleted (second
        # review of 2026-10-10).
        if not re.search(r"(?<!def )\bgpu_lease(?:_sync)?\(", _read(client)):
            problems.append(
                "%s  drives a model in another process (%s) and takes no lease.\n"
                "    Its memory stays invisible to the coordinator, which then "
                "decides evictions against a number that is wrong."
                % (client, worker)
            )
    return problems


def check_subprocesses(only=None):
    """Whoever starts a process says whether that process meets the card."""
    problems = []
    for directory in (os.path.join("devserver", "my_app", "routes"),
                      os.path.join("devserver", "my_app", "services")):
        full = os.path.join(REPO, directory)
        if not os.path.isdir(full):
            continue
        for filename in sorted(os.listdir(full)):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            rel = os.path.join(directory, filename)
            if only is not None and rel not in only:
                continue
            body = _read(rel)
            if not any(token in body for token in STARTS_A_PROCESS):
                continue
            if filename in SUBPROCESS_STARTERS:
                promise = SUBPROCESS_STARTERS[filename]
                if promise.startswith("lease:") and "gpu_lease" not in body:
                    problems.append(
                        "%s  promises '%s' and holds no lease.\n"
                        "    Either take one, or say here what changed."
                        % (rel, promise))
                continue
            problems.append(
                "%s  starts a process and stands in no table.\n"
                "    Put it in SUBPROCESS_STARTERS: either it holds a lease "
                "while that process runs, or it says why the card never sees it."
                % rel
            )
    return problems


def check_decommissioned(only=None):
    """A file called decommissioned has to be one: nothing may import it.

    Without this the word is decoration. With it, the day somebody reaches for
    one of these copies - and puts weights into the DevServer process, where
    the coordinator would never see them - the commit stops.
    """
    problems = []
    retired = [name for name, why in DEVSERVER_MODEL_MODULES.items()
               if why.startswith("DECOMMISSIONED")]
    if not retired:
        return problems

    hunted = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs
                   if d not in {".git", "node_modules", "venv", "dist", "__pycache__"}]
        for filename in files:
            if filename.endswith(".py"):
                hunted.append(os.path.join(root, filename))

    for name in retired:
        stem = name[:-3]
        for path in hunted:
            if os.path.basename(path) == name:
                continue
            rel = os.path.relpath(path, REPO)
            if only is not None and rel not in only:
                continue
            try:
                body = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                # Not every .py in the tree is UTF-8; one that cannot be read
                # cannot be importing anything either.
                continue
            if ("import %s" % stem) in body or ("from %s" % stem) in body:
                problems.append(
                    "%s  imports %s, which is marked decommissioned.\n"
                    "    Use the copy in the GPU service, or take the mark off "
                    "that file and say what covers it." % (rel, name))
    return problems


def main():
    only = None
    if "--staged" in sys.argv:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=REPO, capture_output=True, text=True,
        )
        only = {line for line in out.stdout.splitlines() if line.endswith(".py")}
        if not only:
            return 0

    problems = (check_routes(only) + check_modules(only)
                + check_remote(only) + check_subprocesses(only)
                + check_decommissioned(only))
    if problems:
        sys.stderr.write(
            "\nGPU admission coverage: %d place(s) reach the card without "
            "announcing it.\n\n" % len(problems)
        )
        for problem in problems:
            sys.stderr.write("  %s\n\n" % problem)
        sys.stderr.write(
            "One slot, one card, one coordinator - it is only ever right about "
            "memory it was told about.\n"
            "Rule and reasoning: the docstring at the top of this file.\n\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
