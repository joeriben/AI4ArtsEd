#!/usr/bin/env python3
"""A config that moves takes six places with it.

Stage 0.3 of the ComfyUI migration.
Every output config is named in more places than the file it lives in, and each
one of them fails differently when the config is renamed, retired or replaced:

  1. the surfaces that name it            — here
  2. RESONA_CANVAS_CONFIGS                — test_resona_canvas_graphs.py
  3. CHUNK_MAP                            — test_safety_coverage_map.py
  4. LATENT_LAB_CHUNKS                    — test_latent_lab_model_policy.py
  5. the seed the chunk receives          — test_python_chunk_seed_policy.py
  6. output_config_defaults.json          — here
  7. the configs the two agents may run, which stand three times — here

Four of the six already had a guard. This file holds the ones that did not, plus
the spine they all rest on: that a config actually leads to a chunk that exists.

Six was the first count; a review on 2026-09-07 walked all 46 configs and
all 58 chunks through every versioned file and found seventeen kinds of place.
The ones still open: the preload table, the
non-output chunks, the measuring scripts, the two stage-2 configs that name an
output config, and the agents' reference text.

Written because two of them had already drifted, unnoticed, and only latently:
`output_config_defaults.json` named `wan22_t2v_diffusers` for video, which is no
config at all, and `acestep_simple` for music, which the platform declared dead
on 2026-06-19. Neither fires today, because no stage-2 config infers video or
music yet — and inferring the medium from the prompt is exactly what is being
built.

Run: pytest devserver/tests/test_output_config_carry_list.py
"""

import ast
import json
import os
import re
from pathlib import Path

from file_modules import REPO

SCHEMAS = REPO / "devserver" / "schemas"
CONFIG_DIR = SCHEMAS / "configs" / "output"
CHUNK_DIR = SCHEMAS / "chunks"
PIPELINE_DIR = SCHEMAS / "pipelines"
DEFAULTS = SCHEMAS / "output_config_defaults.json"
FRONTEND = REPO / "public" / "ai4artsed-frontend" / "src"


def _configs() -> dict:
    out = {}
    for path in sorted(CONFIG_DIR.rglob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    assert out, f"no output configs found under {CONFIG_DIR}"
    return out


def _pipelines() -> dict:
    out = {}
    for path in sorted(PIPELINE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data.get("name") or path.stem] = data
    return out


def _chunk_exists(name: str) -> bool:
    return (CHUNK_DIR / f"{name}.py").is_file() or (CHUNK_DIR / f"{name}.json").is_file()


def test_every_chunk_a_pipeline_names_exists():
    """Not the destination alone. `translate`, `text_split`, `manipulate` and
    the two prompt adaptions carry the run to the destination, and a pipeline
    that names one of them wrongly ends the same way: with nothing to load."""
    missing = {}
    for name, pipeline in _pipelines().items():
        for chunk in (pipeline.get("chunks") or []):
            if not isinstance(chunk, str) or "{{" in chunk:
                continue  # a placeholder the config fills in
            if not _chunk_exists(chunk):
                missing.setdefault(name, []).append(chunk)
    assert not missing, (
        f"Pipeline(s) naming chunk(s) that are not in schemas/chunks/: {missing}")


def test_the_template_chunk_list_holds_no_stale_entries():
    """TEMPLATE_CHUNKS lets a config name a destination its pipeline does not.
    An entry that names nothing widens that hole for a chunk that is gone."""
    gone = sorted(name for name in TEMPLATE_CHUNKS if not _chunk_exists(name))
    assert not gone, (
        f"TEMPLATE_CHUNKS names chunk(s) that no longer exist: {gone}")


# A chunk a pipeline names that is not a destination but a form (its
# workflow and model placeholders the config fills in, so a config using it
# still names its own OUTPUT_CHUNK). None at present: comfyui_image_generation
# went with the image_generation pipeline no config named (2026-10-10).
TEMPLATE_CHUNKS: set = set()


def _chunks_a_config_reaches(config: dict, pipelines: dict) -> tuple:
    """(names, where) — the chunks this config's run ends in, and how it got there."""
    own = (config.get("parameters") or {}).get("OUTPUT_CHUNK")
    pipeline = pipelines.get(config.get("pipeline")) or {}
    named = [c for c in (pipeline.get("chunks") or [])
             if isinstance(c, str) and not c.startswith("{{")]
    concrete = [c for c in named if c.startswith("output_") and c not in TEMPLATE_CHUNKS]
    if concrete:
        return concrete, "its pipeline"
    return ([own] if own else []), "OUTPUT_CHUNK"


def test_every_config_names_a_pipeline_that_exists():
    pipelines = _pipelines()
    broken = {cid: c.get("pipeline") for cid, c in _configs().items()
              if c.get("pipeline") not in pipelines}
    assert not broken, (
        f"Config(s) naming a pipeline that is not there: {broken}. "
        f"Known pipelines: {sorted(pipelines)}")


def test_every_config_ends_in_a_chunk_that_exists():
    """The spine. A config whose chunk is gone fails at run time, in a message
    about a missing chunk, at the moment somebody presses generate."""
    pipelines = _pipelines()
    broken = []
    for cid, config in _configs().items():
        chunks, where = _chunks_a_config_reaches(config, pipelines)
        if not chunks:
            broken.append(f"{cid}: names no chunk at all (pipeline "
                          f"{config.get('pipeline')!r} names none either)")
            continue
        for name in chunks:
            if not _chunk_exists(name):
                broken.append(f"{cid}: {where} names {name!r}, which is not in "
                              f"schemas/chunks/")
    assert not broken, "Config(s) leading nowhere:\n  " + "\n  ".join(broken)


def test_a_config_and_its_pipeline_do_not_name_different_chunks():
    """Where the pipeline carries its own chunk, an OUTPUT_CHUNK beside it is
    decoration — and decoration that names a different model is a config whose
    label and whose output disagree.

    This is how `acestep_simple` came to generate HeartMuLa music: its pipeline
    `music_generation` carries `output_music_heartmula`, and the config's own
    name says ACE-Step.
    """
    pipelines = _pipelines()
    disagreeing = []
    for cid, config in _configs().items():
        own = (config.get("parameters") or {}).get("OUTPUT_CHUNK")
        chunks, where = _chunks_a_config_reaches(config, pipelines)
        if where == "its pipeline" and own and own not in chunks:
            disagreeing.append(
                f"{cid}: declares OUTPUT_CHUNK {own!r}, but pipeline "
                f"{config.get('pipeline')!r} runs {chunks}")
    assert not disagreeing, (
        "Config and pipeline name different chunks:\n  " + "\n  ".join(disagreeing))


def test_the_default_for_each_medium_exists():
    """`lookup_output_config` reads this file whenever the medium was inferred
    rather than chosen, and hands the name straight on. A name that is no
    config ends the run with nothing to load."""
    configs = _configs()
    defaults = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    missing = {}
    for medium, value in defaults.items():
        if medium.startswith("_") or value is None:
            continue
        # A dict is a VRAM-tier mapping; every branch of it has to exist.
        names = list(value.values()) if isinstance(value, dict) else [value]
        for name in names:
            if str(name).startswith("_"):
                continue
            if name not in configs:
                missing.setdefault(medium, []).append(name)
    assert not missing, (
        f"output_config_defaults.json names config(s) that do not exist: {missing}. "
        f"Available: {sorted(configs)}")


# How a surface names a config, in the three shapes it actually takes.
#
# (a) A key that means "the output config": `outputConfig: 'sd35_large'`,
#     `const OUTPUT_CONFIG = 'feature_probing'`. Narrow on purpose — a `config:` holding
#     a display label or a handler name has no business here.
_NAMES_A_CONFIG = re.compile(
    r"""(?<![:@\w-])
        (?:[A-Za-z0-9_]*(?:CONFIG|Config|config)|config_name|configName
         |config_id|configId)\s*[:=]\s*['"]([a-z0-9_]+)['"]""",
    re.VERBOSE)

# (b) An entry in a catalog — the shape that carries the model rings:
#     `{ id: 'sd35_large', label: 'SD 3.5 Large' }`, or a plain list of names,
#     `['sd35_large', 'flux2']`. `id` alone would drag in every tab and chip on
#     the platform, so a catalog is recognised by what it HOLDS instead: an
#     array with at least one live config in it is a config catalog, and then
#     every entry in that array has to be one. An array of providers or of
#     depth levels holds none and is passed over untouched.
_CATALOG_ENTRY = re.compile(
    r"""\{\s*id\s*:\s*['"]([a-z0-9_]+)['"]\s*,\s*label\s*:""",
    re.VERBOSE)
# A plain list of names is only read as one when the WHOLE array is names:
# quoted lowercase words, commas, whitespace. Anything else in the brackets and
# it is an argument list or a fixture, and stays out of this.
_PLAIN_ARRAY = re.compile(
    r"""\[\s*((?:['"][a-z0-9_]+['"]\s*,\s*)*['"][a-z0-9_]+['"]\s*,?\s*)\]""")
_PLAIN_NAME = re.compile(r"""['"]([a-z0-9_]+)['"]""")

# (c) A constant in capitals holding a snake_case name: `I2I_IMAGE =
#     'qwen_img2img'`, `HEARTMULA = 'heartmula_standard'`. The constant's own
#     name says nothing about configs, so nothing above sees these — and the
#     material routing keeps four of them. Measured over the whole frontend:
#     ten such constants hold a live config; of the rest, the storage keys are
#     told apart by their name and the run ids stand in a spec.
#
# (d) A config that was retired keeps its file as `<name>.json.disabled`. Any
#     surface still naming one is the carry list's own failure case, whatever
#     shape it is written in.
_CONSTANT_NAME = re.compile(
    r"""\b(?:const|let)\s+([A-Z][A-Z0-9_]*)\s*(?::[^=\n]+)?
        =\s*['"]([a-z0-9]+(?:_[a-z0-9]+)+)['"]""",
    re.VERBOSE)


def _constant_names(text):
    """(name, line) for every constant in capitals that holds a snake_case
    string, apart from the ones whose own name says they hold a storage key."""
    found = []
    for match in _CONSTANT_NAME.finditer(text):
        constant = match.group(1)
        if constant.endswith("_KEY") or "STORAGE" in constant:
            continue
        found.append((match.group(2),
                      text.count("\n", 0, match.start()) + 1))
    return found


def _catalog_groups(text):
    """The catalogs of the file, as lists of (name, line).

    Object catalogs are cut at each `]`, which is where a flat array ends; a
    nested array closes first and so reads as its own group, which is what the
    media catalogs want. Plain name arrays are each their own group."""
    groups = []
    position = 0
    for chunk in text.split("]"):
        found = []
        for match in _CATALOG_ENTRY.finditer(chunk):
            line = text.count("\n", 0, position + match.start()) + 1
            found.append((match.group(1), line))
        if found:
            groups.append(sorted(set(found), key=lambda pair: pair[1]))
        position += len(chunk) + 1
    for match in _PLAIN_ARRAY.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        names = _PLAIN_NAME.findall(match.group(1))
        groups.append([(name, line) for name in names])
    return groups


_CONFIG_ARRAY = re.compile(
    r"""\b(?:const|let|var)\s+[A-Za-z0-9_]*[Cc]onfigs?\b[^=\n]*=\s*\[""")


def _declared_config_arrays(text):
    """(name, line) for the entries of an array whose declaration calls it
    configs. A catalog of one holds no second entry to recognise it by, so the
    name of the array is what says what stands in it."""
    found = []
    for match in _CONFIG_ARRAY.finditer(text):
        end = text.find("]", match.end())
        body = text[match.end():end if end != -1 else len(text)]
        for pattern, group in ((_CATALOG_ENTRY, 1), (_PLAIN_NAME, 1)):
            for entry in pattern.finditer(body):
                line = text.count("\n", 0, match.end() + entry.start()) + 1
                found.append((entry.group(group), line))
    return sorted(set(found), key=lambda pair: pair[1])


def _keyed_names(text):
    """Every config named by a key that says it is one, with its line."""
    return [(match.group(1), text.count("\n", 0, match.start()) + 1)
            for match in _NAMES_A_CONFIG.finditer(text)]


def _named_configs(text):
    """Every name the shapes above turn up, for the exception list."""
    seen = (list(_keyed_names(text)) + list(_constant_names(text))
            + list(_declared_config_arrays(text)))
    for group in _catalog_groups(text):
        seen.extend(group)
    return seen


# Surface strings that are not output configs, with what they are instead.
NOT_A_CONFIG = {
    # The Fusion Workbench asks its own proxy route (/api/fusion_workbench/*),
    # not the schema pipeline. Its constant is named OUTPUT_CONFIG all the same.
    "fusion_workbench",
    # A run label for /pipeline/run/init, beside 'compare_session'. It names
    # what the run IS, not which config makes the medium.
    "persona_session",
    # The Text Lab's name for the Qwen family in its model picker, which reads
    # the same as the retired qwen.json.disabled and is a different thing.
    "qwen",
    # The Latent Lab tool group that mmaudio, imagebind_guidance and audio_synth
    # declare themselves part of. A group of instruments, not an output config.
    "crossmodal_lab",
    # The Together surface's localStorage key for what survives a reload
    # (views/resona_board_memory.ts, `const KEY = 'resona_board'`). A board
    # memory, not a medium: the view decides what a card is, this name only
    # says where the browser keeps it.
    "resona_board",
    # A Flow perspective disc names the interception config it runs as its
    # configId (views/__tests__/x2x_flow.discs.spec.ts): 'bauhaus' is
    # schemas/configs/interception/bauhaus.json, no output config.
    "bauhaus",
    # The localStorage key under which a picture handed to the Flow waits for
    # it (lib/handOverImage.ts, `const KEY = 'i2i_transfer_data'`; the four
    # writers and the reader spelled it out until 2026-10-10). A hand-over
    # slot, not a medium.
    "i2i_transfer_data",
}


def test_no_surface_names_a_config_that_is_gone():
    """Point 1 of the carry list. A view naming a retired config shows an
    instrument that answers with an error when it is pressed, and it shows it
    without a hint that anything is wrong."""
    configs = _configs()
    retired = {path.name.split(".json")[0]
               for path in CONFIG_DIR.glob("*.json.disabled")}
    unknown = {}
    for root, _dirs, files in os.walk(FRONTEND):
        if os.sep + "i18n" in root:
            continue  # translated prose, not identifiers
        for filename in files:
            if not filename.endswith((".vue", ".ts")):
                continue
            path = Path(root) / filename
            source = path.read_text(encoding="utf-8")
            where = lambda number: f"{path.relative_to(FRONTEND)}:{number}"
            in_a_spec = "__tests__" in str(path)
            for value, number in (
                    _keyed_names(source)
                    + ([] if in_a_spec else _constant_names(source))
                    + _declared_config_arrays(source)):
                if value in configs or value in NOT_A_CONFIG:
                    continue
                unknown.setdefault(value, []).append(where(number))
            for group in _catalog_groups(source):
                if not any(name in configs for name in
                           (name for name, _line in group)):
                    continue  # holds no config, so it is not a config catalog
                for name, number in group:
                    if name not in configs and name not in NOT_A_CONFIG:
                        unknown.setdefault(name, []).append(where(number))
            for name in retired:
                for number, line in enumerate(source.splitlines(), 1):
                    if re.search(r"['\"]" + re.escape(name) + r"['\"]", line):
                        if name not in NOT_A_CONFIG:
                            unknown.setdefault(name, []).append(where(number))
    assert not unknown, (
        "Surface(s) naming a config that is not in schemas/configs/output/: "
        + json.dumps(unknown, indent=2)
        + "\n\nEither the config was renamed and the surface was not, or the "
          "string is not a config id — in which case add it to NOT_A_CONFIG "
          "with what it is instead.")


def test_the_exception_list_holds_no_stale_entries():
    """A name that became a real config, or vanished from the surfaces, has no
    business in the exception list."""
    configs = _configs()
    still_named = set()
    for root, _dirs, files in os.walk(FRONTEND):
        if os.sep + "i18n" in root:
            continue
        for filename in files:
            if filename.endswith((".vue", ".ts")):
                text = (Path(root) / filename).read_text(encoding="utf-8")
                for value, _line in _named_configs(text):
                    still_named.add(value)
    stale = sorted((NOT_A_CONFIG - still_named) | (NOT_A_CONFIG & set(configs)))
    assert not stale, (
        f"NOT_A_CONFIG names {stale}, which no surface uses any more or which "
        f"is a config now. Remove the entry.")

# ---------------------------------------------------------------------------
# 7. The text->media configs an agent may run, which stand three times.
# ---------------------------------------------------------------------------
# Resona reaches them through a tool, Persona through a line of prompt text, and
# the canvas author through a dict — three shapes of the same permission, none
# of which reads the others. Consolidating them is a change to what two agents
# say and needs its own decision; until then this holds them level, so a config
# that moves cannot leave one copy behind.

TOOL_REGISTRY = REPO / "devserver" / "my_app" / "services" / "tool_registry.py"
CANVAS_AUTHORING = (REPO / "devserver" / "my_app" / "services"
                    / "canvas_graph_authoring.py")
PERSONA_VIEW = FRONTEND / "views" / "ai_persona.vue"

_PERSONA_ENTRY = re.compile(r"^\s*'([a-z0-9_]+) \u2014 ", re.MULTILINE)


def _dict_keys(path, name):
    """The string keys of a dict assigned to `name`, wherever in the file it
    stands — the tool registry builds its copy inside a function."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Dict):
            continue
        names = []
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        if name in names:
            return [k.value for k in value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    raise AssertionError(f"{path.name} no longer holds a dict named {name!r}")


def _persona_configs():
    text = PERSONA_VIEW.read_text(encoding="utf-8")
    start = text.find("function buildAvailableConfigs()")
    assert start != -1, "ai_persona.vue no longer builds the list of configs"
    end = text.find("].join(", start)
    assert end != -1, "buildAvailableConfigs no longer ends in a joined list"
    return _PERSONA_ENTRY.findall(text[start:end])


def test_the_two_agents_and_the_canvas_offer_the_same_configs():
    """Point 7. The tool registry is the copy the run actually validates
    against, so it sets the count; the other two have to match it."""
    tool = _dict_keys(TOOL_REGISTRY, "resona_media_configs")
    canvas = _dict_keys(CANVAS_AUTHORING, "RESONA_CANVAS_CONFIGS")
    persona = _persona_configs()

    missing_in_canvas = sorted(set(tool) - set(canvas))
    assert not missing_in_canvas, (
        "RESONA_CANVAS_CONFIGS is missing config(s) the media tool offers: "
        f"{missing_in_canvas}")
    assert sorted(persona) == sorted(tool), (
        "ai_persona.vue offers a different set of configs than the media tool.\n"
        f"  only in the view: {sorted(set(persona) - set(tool))}\n"
        f"  only in the tool: {sorted(set(tool) - set(persona))}")


def test_every_config_the_agents_offer_exists():
    """A name an agent hands out is a name a run is submitted with. Where it
    names nothing, the agent writes an instruction that ends in an error."""
    configs = _configs()
    offered = set(_dict_keys(TOOL_REGISTRY, "resona_media_configs"))
    offered |= set(_dict_keys(CANVAS_AUTHORING, "RESONA_CANVAS_CONFIGS"))
    offered |= set(_persona_configs())
    gone = sorted(name for name in offered if name not in configs)
    assert not gone, (
        f"The agents offer config(s) that are not in schemas/configs/output/: "
        f"{gone}")
