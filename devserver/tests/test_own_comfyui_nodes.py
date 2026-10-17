#!/usr/bin/env python3
"""The nodes this platform wrote itself have to reach ComfyUI.

Stage 0.4 of the ComfyUI migration.

ComfyUI validates every `class_type` when a workflow is submitted, so a node it
does not have ends the run at the door, before a model is touched. Two of the
node packages come from `install_comfyui_nodes.sh`, which clones them. The nodes
written here had no such path: the denoising archaeology node reached the
development card through a symlink set by hand on 2026-09-05, and a fresh
install would have gone without it.

comfyui_nodes/ holds two kinds of node, and this file reads both:

  ai4artsed_denoising_archaeology.py   a single file, registering a CamelCase
                                       name (AI4ArtsEdDenoisingArchaeology)
  ai4artsed_comfyui/                   a package: a directory with an __init__.py
                                       that registers the lowercase names
                                       (ai4artsed_conditioning_fusion, ...)

The package is the fork, taken whole on 2026-09-12, of
github.com/joeriben/ai4artsed_comfyui_nodes, which the installer cloned into
custom_nodes/ until that day. That repository stays a ComfyUI-only package and
is developed apart from this one; the fork is developed here. The fork carries
no key file: the clone read a second `openrouter.key` of its own, and API keys
live in one place. The nodes read the platform's provider table by path,
through `_platform_credentials.py`.

Run: pytest devserver/tests/test_own_comfyui_nodes.py
"""

import ast
import json
import re

from file_modules import REPO, load_module

OWN_NODES = REPO / "comfyui_nodes"
CHUNK_DIR = REPO / "devserver" / "schemas" / "chunks"
# Graphs a route submits without a chunk: the embedding research series
# (routes/fusion_workbench_routes.py) builds its graphs here.
GRAPH_SERVICES = (REPO / "devserver" / "my_app" / "services" / "latent_lab_context_graphs.py",)
# The builders the chunks share (docs/ELEMENT_STRUCTURE_REGISTRY.md): a node named only inside one of
# them counts as used where a chunk or graph service calls that builder.
SHARED_BUILDERS = REPO / "devserver" / "schemas" / "engine" / "comfyui_chunk_support.py"
INSTALLER = REPO / "install_comfyui_nodes.sh"
PROVIDER_TABLE = REPO / "devserver" / "config" / "llm_providers.json"
PROVIDER_TABLE_READER = REPO / "devserver" / "my_app" / "services" / "llm_providers.py"

# A class_type in one of these two shapes is one of ours: CamelCase from a
# single node file, lowercase with underscores from the package.
_OURS_FILE = re.compile(r"^AI4ArtsEd[A-Za-z0-9_]*$")
_OURS_PACKAGE = re.compile(r"^ai4artsed_[a-z0-9_]+$")
# JSON chunks write double quotes; a Python chunk may write either.
_CLASS_TYPE = re.compile(r"""["']class_type["']\s*:\s*["']([^"']+)["']""")
# The shape of a real key, on any line of any file in the package. The prefix
# alone ('sk-or-') stands in the key node's check and is shorter than this.
_KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9_-]{32,}")

# A node kept for a workflow that is not in the chunks today. Add an entry WITH
# a reason rather than letting an unused node stand silently.
_FORKED_WHOLE = ("copied with the whole package: the nodes are copied whether "
                 "they are used or not")
NOT_CALLED_BY_A_CHUNK: dict = {
    "ai4artsed_text_remix": _FORKED_WHOLE,
    "ai4artsed_random_instruction_generator": _FORKED_WHOLE,
    "ai4artsed_random_artform_generator": _FORKED_WHOLE,
    "ai4artsed_random_language_selector": _FORKED_WHOLE,
    "ai4artsed_image_analysis": _FORKED_WHOLE,
    "ai4artsed_vector_dimension_eliminator": _FORKED_WHOLE,
    "ai4artsed_switch_promptsafety": _FORKED_WHOLE,
    "ai4artsed_photo_prompt_randomizer": _FORKED_WHOLE,
    "ai4artsed_clean_prompt_randomizer": _FORKED_WHOLE,
    "ai4artsed_local_llm": ("called by no chunk: the DevServer's local LLM backend queues a "
                            "one-node prompt of it for every local chat, safety check and "
                            "image reading (my_app/services/llm_client.py, NODE_CLASS)"),
    "AI4ArtsEdLoadKeptLatent": ("called by no chunk: Mean Images queues a four-node decode "
                                "of it for the mean of a set (my_app/services/latent_decoder.py, "
                                "decode_workflow)"),
    "ai4artsed_llm_option_scores": ("called by no chunk: the Text Lab's coreference and BBQ "
                                    "probes queue a one-node prompt of it per batch of "
                                    "prompts (my_app/services/text_probes.py, SCORES_NODE)"),
    "ai4artsed_llm_rep_engineering": ("called by no chunk: the Text Lab's Representation "
                                      "Engineering queues a one-node prompt of it per reading "
                                      "(my_app/services/text_probes.py, REP_ENGINEERING_NODE)"),
    # Stage 6: the media stations. The chunks of the three configs hand to a
    # client, and the client queues the one-node prompt (the chunk names the
    # config's model, the client the node).
    "ai4artsed_stable_audio": ("called by no chunk by name: the Stable Audio 3 configs' chunk "
                               "hands to my_app/services/stable_audio_client.py, which queues "
                               "a one-node prompt of it (NODE_CLASS)"),
    "ai4artsed_heartmula": ("called by no chunk by name: the HeartMuLa config's chunk hands "
                            "to my_app/services/heartmula_client.py, which queues a one-node "
                            "prompt of it (NODE_CLASS)"),
    "ai4artsed_hunyuan3d": ("called by no chunk by name: the Hunyuan3D config's chunk hands "
                            "to my_app/services/hunyuan3d_client.py, which queues a one-node "
                            "prompt of it (NODE_CLASS)"),
    "ai4artsed_media_reading": ("called by no chunk: the media readings of the Flow page, the "
                                "cover band and the VLM comparison queue a one-node prompt of "
                                "it per reading (my_app/services/media_analysis_client.py, "
                                "NODE_CLASS)"),
    "ai4artsed_audio_synth": ("called by no chunk: the Crossmodal Lab's audio synthesis queues "
                              "a one-node prompt of it per run "
                              "(my_app/routes/cross_aesthetic_routes.py, SYNTH_NODE)"),
    "ai4artsed_image_guided_audio": ("called by no chunk: the Crossmodal Lab's image-guided "
                                     "audio queues a one-node prompt of it per run "
                                     "(my_app/routes/cross_aesthetic_routes.py, GUIDED_NODE)"),
    "ai4artsed_mmaudio": ("called by no chunk: the Crossmodal Lab's MMAudio queues a one-node "
                          "prompt of it per run (my_app/routes/cross_aesthetic_routes.py, "
                          "MMAUDIO_NODE)"),
}

# A package module that defines a node class and is not in __init__.py. Such a
# module is a file ComfyUI never sees; an entry names why it stands there.
NOT_REGISTERED_BY_THE_PACKAGE: dict = {}


def _node_files():
    return sorted(p for p in OWN_NODES.glob("*.py") if not p.name.startswith("_"))


def _packages():
    return sorted(p for p in OWN_NODES.iterdir()
                  if p.is_dir() and (p / "__init__.py").exists())


def _mappings(path):
    """{class_type: class name} from the file's NODE_CLASS_MAPPINGS."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "NODE_CLASS_MAPPINGS" not in names:
            continue
        if not isinstance(node.value, ast.Dict):
            raise AssertionError(
                f"{path.name}: NODE_CLASS_MAPPINGS is built rather than written "
                f"out, so what it registers cannot be read here")
        if any(key is None for key in node.value.keys):
            # `{**_EXTRA, "X": Y}` IS an ast.Dict, and the splat's key is None.
            # Everything inside _EXTRA would pass both checks below unseen.
            raise AssertionError(
                f"{path.name}: NODE_CLASS_MAPPINGS spreads another mapping into "
                f"itself, so part of what it registers cannot be read here")
        return {k.value: getattr(v, "id", None)
                for k, v in zip(node.value.keys, node.value.values)
                if isinstance(k, ast.Constant)}
    return {}


def _registered(path):
    """{class_type: class name} a single node file registers."""
    return _mappings(path)


def _package_registered(package):
    """{class_type: (class name, module file)} the package's __init__ registers,
    the module being the one its `from .x import Class` names."""
    init = package / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"))
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for alias in node.names:
                imported[alias.asname or alias.name] = package / f"{node.module}.py"
    return {class_type: (class_name, imported.get(class_name))
            for class_type, class_name in _mappings(init).items()}


# A node file that loads a function out of another node file, and what it takes:
# {node file: ((sibling file, function name), ...)}.
_SIBLING_HELPERS = {
    "ai4artsed_composable_diffusion.py": (
        ("ai4artsed_sd3_conditioning.py", "slerp_tokens"),
    ),
}


def _functions_defined(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _classes_defined(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


def _defines_a_node(path):
    """A ComfyUI node class is one with INPUT_TYPES; that is how ComfyUI
    itself tells a node from a helper."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(n, ast.FunctionDef) and n.name == "INPUT_TYPES"
               for n in ast.walk(tree))


def _all_registered():
    ours = set()
    for path in _node_files():
        ours |= set(_registered(path))
    for package in _packages():
        ours |= set(_package_registered(package))
    return ours


def _builders_naming_nodes():
    """{builder function name: {class_type}} over the shared builders module: a
    function whose body writes a class_type literal."""
    text = SHARED_BUILDERS.read_text(encoding="utf-8", errors="replace")
    named = {}
    blocks = re.split(r"^(?=def )", text, flags=re.MULTILINE)
    for block in blocks:
        head = re.match(r"def (\w+)\(", block)
        if head:
            found = set(_CLASS_TYPE.findall(block))
            if found:
                named[head.group(1)] = found
    return named


def _class_types_chunks_use():
    """{class_type: {chunk file names}} over every chunk, JSON and Python, and
    the graph services: the literal written there, or a shared builder called
    there that writes it."""
    used = {}
    builders = _builders_naming_nodes()
    for path in (sorted(CHUNK_DIR.rglob("*.json")) + sorted(CHUNK_DIR.rglob("*.py"))
                 + list(GRAPH_SERVICES)):
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in _CLASS_TYPE.findall(text):
            used.setdefault(name, set()).add(path.name)
        for builder, nodes in builders.items():
            if re.search(r"\b" + re.escape(builder) + r"\(", text):
                for name in nodes:
                    used.setdefault(name, set()).add(path.name)
    return used


def _provider_hosts():
    """Every host the provider table names, and each one's parent domain: a
    file that spells openrouter.ai reaches the global host while the table
    says eu.openrouter.ai."""
    table = json.loads(PROVIDER_TABLE.read_text(encoding="utf-8"))["providers"]
    hosts = set()
    for row in table.values():
        for key in ("api_url", "credits_url"):
            m = re.match(r"https?://([^/]+)", row.get(key) or "")
            if m:
                hosts.add(m.group(1))
                hosts.add(".".join(m.group(1).split(".")[-2:]))
    return sorted(hosts)


def test_there_is_at_least_one_own_node():
    """The directory is the deployment path; an empty one means the path was
    dropped rather than that nothing needs it."""
    assert _node_files() or _packages(), (
        f"{OWN_NODES.relative_to(REPO)} holds no node source. If the nodes moved, "
        f"the installer step and this file move with them.")


def test_every_own_node_registers_what_it_defines():
    """A node file that registers nothing is installed and does nothing; one
    that registers a class it does not define fails at ComfyUI's import."""
    wrong = []
    for path in _node_files():
        registered = _registered(path)
        if not registered:
            wrong.append(f"{path.name}: no NODE_CLASS_MAPPINGS")
            continue
        defined = _classes_defined(path)
        for class_type, class_name in registered.items():
            if class_name not in defined:
                wrong.append(
                    f"{path.name}: registers {class_type!r} as {class_name!r}, "
                    f"which the file does not define")
            if not _OURS_FILE.match(class_type):
                wrong.append(
                    f"{path.name}: registers {class_type!r}, which does not read "
                    f"as a single-file node of ours -- the package owns the "
                    f"lowercase names")
    for package in _packages():
        registered = _package_registered(package)
        if not registered:
            wrong.append(f"{package.name}/__init__.py: no NODE_CLASS_MAPPINGS")
            continue
        for class_type, (class_name, module) in registered.items():
            if module is None:
                wrong.append(
                    f"{package.name}/__init__.py: registers {class_type!r} as "
                    f"{class_name!r}, which no `from .x import` there brings in")
            elif not module.exists():
                wrong.append(
                    f"{package.name}/__init__.py: imports {class_name!r} from "
                    f"{module.name}, which is not in the package")
            elif class_name not in _classes_defined(module):
                wrong.append(
                    f"{package.name}/{module.name}: does not define {class_name!r}, "
                    f"which __init__.py registers as {class_type!r}")
            if not _OURS_PACKAGE.match(class_type):
                wrong.append(
                    f"{package.name}/__init__.py: registers {class_type!r}, which "
                    f"does not read as a package node of ours")
    assert not wrong, "Own node file(s) out of shape:\n  " + "\n  ".join(wrong)


def test_every_package_module_that_defines_a_node_is_registered():
    """A module with a node class that __init__.py never imports is a node
    ComfyUI never sees, with no error anywhere. Either register it or name
    in NOT_REGISTERED_BY_THE_PACKAGE why it stands there."""
    unseen = []
    stale = []
    for package in _packages():
        registered_modules = {module for _, module in _package_registered(package).values()}
        for path in sorted(package.glob("*.py")):
            if path.name == "__init__.py":
                continue
            rel = f"{package.name}/{path.name}"
            if _defines_a_node(path) and path not in registered_modules:
                if rel not in NOT_REGISTERED_BY_THE_PACKAGE:
                    unseen.append(rel)
            elif rel in NOT_REGISTERED_BY_THE_PACKAGE:
                stale.append(rel)
    assert not unseen, (
        f"Package module(s) with a node class that __init__.py does not register: "
        f"{unseen}. Register it, or add it to NOT_REGISTERED_BY_THE_PACKAGE with why.")
    assert not stale, (
        f"NOT_REGISTERED_BY_THE_PACKAGE names {stale}, which is registered or "
        f"defines no node after all. Remove the entry.")


def test_every_node_a_chunk_calls_is_here():
    """Point of the whole stage. A chunk naming an AI4ArtsEd node that lives in
    no file here is a run that ends at ComfyUI's door."""
    ours = _all_registered()
    missing = {}
    for class_type, chunks in _class_types_chunks_use().items():
        if ((_OURS_FILE.match(class_type) or _OURS_PACKAGE.match(class_type))
                and class_type not in ours):
            missing[class_type] = sorted(chunks)
    assert not missing, (
        f"Chunk(s) call node(s) that comfyui_nodes/ does not hold: {missing}")


# An input a chunk writes that its node does not declare. ComfyUI drops it in
# silence, so an entry here says what is known about the loss, and the entry goes
# only where correcting it would change a surface this change is not about.
INPUT_THE_NODE_DROPS: dict = {
    "ai4artsed_prompt_interception.unload_model": (
        "found on 2026-09-26 by this test, in schemas/chunks/legacy_surrealization.json "
        "(config surrealization_legacy), on all three of its interception nodes with "
        "'yes'/'no'/'yes'. The forked node (comfyui_nodes/ai4artsed_comfyui/"
        "ai4artsed_prompt_interception.py) declares no such input, so ComfyUI has been "
        "dropping it: the three local models are not unloaded between the steps, which "
        "is a VRAM question and leaves the text as it is. Untouched here because the "
        "legacy workflow is not what this change is about."),
}


def _declared_inputs(path, class_name):
    """The input names a node class writes out in INPUT_TYPES, or None where it
    builds them: nothing is claimed about a dict that is not there to read."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for cls in ast.walk(tree):
        if not (isinstance(cls, ast.ClassDef) and cls.name == class_name):
            continue
        for fn in ast.walk(cls):
            if not (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and fn.name == "INPUT_TYPES"):
                continue
            for ret in ast.walk(fn):
                if not (isinstance(ret, ast.Return) and isinstance(ret.value, ast.Dict)):
                    continue
                names = set()
                for key, value in zip(ret.value.keys, ret.value.values):
                    if key is None:
                        return None  # `{**SOMETHING}`: what it holds is unread
                    if not isinstance(key, ast.Constant):
                        return None
                    if key.value not in ("required", "optional"):
                        continue
                    if not isinstance(value, ast.Dict):
                        return None
                    for name in value.keys:
                        if not isinstance(name, ast.Constant):
                            return None
                        names.add(name.value)
                return names
    return None


def _declared_everywhere():
    """{class_type: set of input names | None} over every node of ours."""
    declared = {}
    for path in _node_files():
        for class_type, class_name in _registered(path).items():
            declared[class_type] = _declared_inputs(path, class_name)
    for package in _packages():
        for class_type, (class_name, module) in _package_registered(package).items():
            declared[class_type] = _declared_inputs(module, class_name) if module else None
    return declared


def _written_json(data, found, name):
    if isinstance(data, dict):
        class_type = data.get("class_type")
        inputs = data.get("inputs")
        if isinstance(class_type, str) and isinstance(inputs, dict):
            for widget in inputs:
                found.setdefault(class_type, {}).setdefault(widget, set()).add(name)
        for value in data.values():
            _written_json(value, found, name)
    elif isinstance(data, list):
        for value in data:
            _written_json(value, found, name)


def _inputs_chunks_write():
    """{class_type: {input name: {file names}}} over the chunks and the graph
    services: every `inputs` dict written beside a literal `class_type`. Only
    what stands there as a literal is read; a graph assembled at runtime is left
    out rather than guessed at."""
    found = {}
    for path in sorted(CHUNK_DIR.rglob("*.json")):
        try:
            _written_json(json.loads(path.read_text(encoding="utf-8")), found, path.name)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    for path in sorted(CHUNK_DIR.rglob("*.py")) + list(GRAPH_SERVICES):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            pairs = {k.value: v for k, v in zip(node.keys, node.values)
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            class_type = pairs.get("class_type")
            inputs = pairs.get("inputs")
            if not (isinstance(class_type, ast.Constant)
                    and isinstance(class_type.value, str)
                    and isinstance(inputs, ast.Dict)):
                continue
            for widget in inputs.keys:
                if isinstance(widget, ast.Constant) and isinstance(widget.value, str):
                    (found.setdefault(class_type.value, {})
                          .setdefault(widget.value, set()).add(path.name))
    return found


def test_every_input_a_chunk_writes_is_one_the_node_declares():
    """The silent half of the stage above. ComfyUI drops a submitted input the
    running node class does not declare -- no error at /prompt, no line in the
    log (execution.py, get_input_data: a key with no input category never
    reaches the node). The run goes through on the node's own default, and a
    chunk that reports what it SENT then reports something that did not happen.

    Read from the source on both sides, so this catches the misspelling and the
    input a chunk writes before the node declares it. What it cannot catch is a
    ComfyUI process older than the node file; a chunk whose record depends on
    the input asks the running ComfyUI itself (comfyui_chunk_support.py,
    node_accepts)."""
    declared = _declared_everywhere()
    undeclared = {}
    for class_type, widgets in _inputs_chunks_write().items():
        if class_type not in declared or declared[class_type] is None:
            continue
        for widget, files in widgets.items():
            key = f"{class_type}.{widget}"
            if widget not in declared[class_type] and key not in INPUT_THE_NODE_DROPS:
                undeclared[key] = sorted(files)
    assert not undeclared, (
        f"Input(s) written into a graph that our node does not declare, which "
        f"ComfyUI drops without a word: {undeclared}. Declare it on the node, "
        f"take it out of the graph, or name it in INPUT_THE_NODE_DROPS with what "
        f"is lost by it.")
    stale = sorted(
        key for key in INPUT_THE_NODE_DROPS
        if key.split(".", 1)[1] in (declared.get(key.split(".", 1)[0]) or ()))
    assert not stale, (
        f"INPUT_THE_NODE_DROPS names {stale}, which the node declares after all. "
        f"Remove the entry.")


def test_every_helper_a_node_takes_from_a_sibling_is_there():
    """ComfyUI gives a node file its own path as the module name, so a node that
    wants a function from another node file loads that file itself
    (ai4artsed_composable_diffusion.py, `_platform_slerp`). Nothing else would
    notice the sibling being renamed, moved into a package or losing the
    function: the node registers, the surface offers what it does, and the run
    dies after the model is loaded. Read from the source, so a renamed function
    is caught at the commit that renames it."""
    missing = []
    for path in _node_files():
        text = path.read_text(encoding="utf-8")
        for sibling, function in _SIBLING_HELPERS.get(path.name, ()):
            if f'"{sibling}"' not in text:
                missing.append(
                    f"{path.name} no longer names {sibling!r}; either the entry in "
                    f"_SIBLING_HELPERS is stale or the file loads something else now")
                continue
            target = OWN_NODES / sibling
            if not target.exists():
                missing.append(f"{path.name} loads {sibling}, which is not in comfyui_nodes/")
            elif function not in _functions_defined(target):
                missing.append(
                    f"{path.name} takes {function}() from {sibling}, which does not "
                    f"define it")
    assert not missing, "Sibling helper(s) out of reach:\n  " + "\n  ".join(missing)


def test_no_own_node_stands_unused():
    """The counter-direction. A node nothing calls is either dead or the chunk
    that called it was renamed -- both want to be seen."""
    used = set(_class_types_chunks_use())
    unused = {}
    for path in _node_files():
        for class_type in _registered(path):
            if class_type not in used and class_type not in NOT_CALLED_BY_A_CHUNK:
                unused[class_type] = path.name
    for package in _packages():
        for class_type in _package_registered(package):
            if class_type not in used and class_type not in NOT_CALLED_BY_A_CHUNK:
                unused[class_type] = package.name
    assert not unused, (
        f"Own node(s) no chunk calls: {unused}. Remove the node, or add it to "
        f"NOT_CALLED_BY_A_CHUNK with what keeps it.")


def test_the_exception_list_holds_no_stale_entries():
    ours = _all_registered()
    used = set(_class_types_chunks_use())
    stale = sorted((set(NOT_CALLED_BY_A_CHUNK) - ours)
                   | (set(NOT_CALLED_BY_A_CHUNK) & used))
    assert not stale, (
        f"NOT_CALLED_BY_A_CHUNK names {stale}, which is gone or called after "
        f"all. Remove the entry.")


def test_the_package_keeps_no_key_and_no_address():
    """API keys live in one place. The clone this package was
    forked from read an openrouter.key of its own, with a second address on
    its second line; a key file, a key, or a provider host inside the package
    is that second place coming back. The nodes reach the platform's table
    through _platform_credentials.py, and nothing else in the package names a
    host: the hosts are read from the table, so a provider added there is
    watched for here without a change to this file."""
    hosts = _provider_hosts()
    assert hosts, f"{PROVIDER_TABLE.relative_to(REPO)} names no host"
    offenders = []
    for package in _packages():
        for path in sorted(package.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(REPO)
            if path.suffix == ".key" or path.name.endswith(".template"):
                offenders.append(f"{rel}: a key file of the package's own")
            text = path.read_text(encoding="utf-8", errors="ignore")
            if _KEY_SHAPE.search(text):
                offenders.append(f"{rel}: holds something shaped like a key")
            if path.suffix != ".py" or path.name == "_platform_credentials.py":
                continue
            for host in hosts:
                if host in text:
                    offenders.append(f"{rel}: names {host}")
            if re.search(r"""['"]openrouter\.key['"]""", text):
                offenders.append(f"{rel}: reads a key file by name")
    assert not offenders, "A second place for keys:\n  " + "\n  ".join(offenders)


def test_the_package_reaches_the_provider_table():
    """The loader resolves the table's reader relative to the repository the
    package is linked from. If the reader moves, the nodes lose their keys with
    no error until the first run; this is where that shows."""
    for package in _packages():
        loader = package / "_platform_credentials.py"
        if not loader.exists():
            continue
        module = load_module("probe_platform_credentials", loader)
        assert module._MODULE_PATH == PROVIDER_TABLE_READER, (
            f"{loader.relative_to(REPO)} looks for the provider table's reader at "
            f"{module._MODULE_PATH}, and it sits at {PROVIDER_TABLE_READER}")
        assert PROVIDER_TABLE_READER.exists()
        url, _ = module.get_openrouter_credentials()
        assert url.startswith("https://") and url.endswith("/chat/completions"), url


def test_the_package_names_no_model_and_falls_back_to_none():
    """A model id is data, never a literal in code (the gate in
    test_no_model_literals.py, whose regex this reads, watches devserver/;
    this package is outside it). And no node answers a failed call with
    another model: this platform has no hardcoded fallback, and the fork's
    origin carried one per LLM node, with its own model list."""
    from test_no_model_literals import MODEL_LITERAL
    offenders = []
    for package in _packages():
        for path in sorted(package.glob("*.py")):
            rel = path.relative_to(REPO)
            text = path.read_text(encoding="utf-8")
            for match in MODEL_LITERAL.finditer(text):
                offenders.append(f"{rel}: names the model {match.group(1) or match.group(2)}")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and "fallback" in node.name.lower():
                    offenders.append(f"{rel}: defines {node.name}(), a fallback")
    assert not offenders, "\n  ".join(["In the package:"] + offenders)


# The nodes that call a language model. Each names the platform role its
# dropdown offers first (platform/<ROLE>), and none talks to a provider.
LLM_NODES = {
    "ai4artsed_prompt_interception.py": "STAGE2_INTERCEPTION_MODEL",
    "ai4artsed_photo_prompt_randomizer.py": "CHAT_HELPER_MODEL",
    "ai4artsed_clean_prompt_randomizer.py": "CHAT_HELPER_MODEL",
    "ai4artsed_switch_promptsafety.py": "SAFETY_MODEL",
    "ai4artsed_image_analysis.py": "IMAGE_ANALYSIS_MODEL",
}
CHAT_ROUTES = REPO / "devserver" / "my_app" / "routes" / "chat_routes.py"


def test_the_llm_nodes_go_through_the_devserver():
    """The DevServer is the nodes' LLM proxy: keys, the provider table and
    the fallback the settings page regulates stay in one
    place, and a node names a role or a model id and nothing else. A node
    that posts to a provider or to Ollama itself is that second place back."""
    wrong = []
    for package in _packages():
        for name, role in LLM_NODES.items():
            path = package / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if "from ._devserver import" not in text:
                wrong.append(f"{name}: does not import _devserver")
            if f'ROLE = "{role}"' not in text:
                wrong.append(f"{name}: does not name its platform role {role}")
            for second_place in ("requests.post(", "requests.get(", "localhost:11434", "api_key"):
                if second_place in text:
                    wrong.append(f"{name}: carries {second_place!r}")
        proxy = package / "_devserver.py"
        if proxy.exists():
            text = proxy.read_text(encoding="utf-8")
            if "/api/chat/proxy" not in text or "/api/chat/models" not in text:
                wrong.append("_devserver.py: does not reach /api/chat/proxy and /api/chat/models")
            if "timeout=(10, None)" not in text:
                wrong.append("_devserver.py: the model call carries a read timeout, or no connect timeout")
    routes = CHAT_ROUTES.read_text(encoding="utf-8")
    if "@chat_bp.route('/proxy', methods=['POST'])" not in routes:
        wrong.append("chat_routes.py: no /api/chat/proxy route for the nodes to reach")
    assert not wrong, "\n  ".join(["The nodes and the DevServer:"] + wrong)


def test_the_installer_deploys_them():
    """Without this step the directory is a place to keep sources and nothing
    reaches ComfyUI -- which is the state stage 0.4 found.

    Read against the lines that do the work, not against the word
    `comfyui_nodes`: that word also stands in the header comment.
    """
    script = INSTALLER.read_text(encoding="utf-8")
    assert 'OWN_NODES_DIR="$SCRIPT_DIR/comfyui_nodes"' in script, (
        "install_comfyui_nodes.sh no longer reads the node sources from this "
        "repo, so a fresh install leaves its own nodes out of ComfyUI.")
    assert 'for node_source in "$OWN_NODES_DIR"/*.py "$OWN_NODES_DIR"/*/; do' in script, (
        "install_comfyui_nodes.sh no longer walks both the single node files and "
        "the packages, so one of the two kinds never reaches ComfyUI.")
    assert 'node_target="$CUSTOM_NODES_DIR/$node_name"' in script, (
        "the link no longer lands in ComfyUI's custom_nodes/, so nothing it "
        "writes is ever loaded.")
    assert 'ln -sfn "$node_source" "$node_target"' in script, (
        "install_comfyui_nodes.sh no longer links the own node sources into "
        "ComfyUI's custom_nodes/.")
    assert not re.search(r"git\s+clone\s+\S*ai4artsed_comfyui", script), (
        "install_comfyui_nodes.sh clones the foreign package again. It lands at "
        "custom_nodes/ai4artsed_comfyui, the path the fork is linked to, and "
        "brings its own key file back.")
    # A clone that runs starts its line; the one in the help text sits in an echo.
    first_clone = re.search(r"^\s*git\s+clone\s+https://", script, re.MULTILINE)
    assert first_clone and script.index('OWN_NODES_DIR=') < first_clone.start(), (
        "the own nodes are linked after the foreign packages are cloned: the "
        "script stops at the first failing clone or pip (set -e), and the nodes "
        "the chunks call are then the ones left out.")


def test_the_installer_fails_where_a_node_could_not_be_installed():
    """A green run that left a node out is the state this stage came from. The
    step reports it and stops, rather than printing "all installed"."""
    script = INSTALLER.read_text(encoding="utf-8")
    assert 'OWN_NODES_BLOCKED=$((OWN_NODES_BLOCKED + 1))' in script
    assert '"$OWN_NODES_BLOCKED" -gt 0' in script, (
        "nothing counts the nodes that were left in place, so the installer "
        "cannot tell that it did not install them.")
    blocked = script.index('"$OWN_NODES_BLOCKED" -gt 0')
    assert "exit 1" in script[blocked:blocked + 500], (
        "the installer reports success even where an own node was not installed.")
