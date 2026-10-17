#!/usr/bin/env python3
"""
Policy guard for step 4 of the Intelligent Seed propagation chain.

The chain is documented in docs/ARCHITECTURE PART 01, section 3.5:

  1. DevServer        seed_override=calculated_seed
  2. PipelineExecutor parameter added
  3. Context          custom_placeholders['seed_override']
  4. Chunks           parameters['seed']   (lowercase!)

Step 4 is unconditional — pipeline_executor injects 'seed' into every chunk
request. This test guards the receiving end, and a chunk has two shapes of it.

A PYTHON chunk must declare a 'seed' parameter in its execute() signature, or
the injected value lands in **kwargs, is never read, and the chunk generates at
its own random.randint().

A COMFYUI chunk has no signature. Its receiving end is `input_mappings.seed`,
which names the node and field the value is written into before the workflow is
submitted (backend_router._apply_input_mappings). Without that entry the
workflow keeps the seed literal written into its sampler, and the value the
person set reaches nothing — the same failure, in the shape the main path takes
when it moves to ComfyUI. And a workflow with more than one sampler needs the
mapping to name every one of them: the multi-node list form exists for exactly
that (`"seed": [{...}, {...}]`), and one value is written to all of them.

That is not hypothetical. Between 2026-02-05 and 2026-08-03 step 4 carried an
exception for backend_type 'python'. On the day it was written the only Python
chunk was HeartMuLa, so it was narrow; the 2026-03-01 migration of six Diffusers
JSON chunks to Python chunks moved SD3.5, FLUX.2 and the first Latent Lab
instruments under it, and every chunk born as Python afterwards inherited it.
The seed set in the UI reached nothing, nothing was reproducible, and no A/B
comparison of two parameter settings was valid.

If a test here fails, the named chunk can no longer receive the user's seed.
Restore the 'seed' parameter in its execute() signature — do not relax the test.

Run: pytest devserver/tests/test_python_chunk_seed_policy.py
"""

import ast
import collections
from pathlib import Path

CHUNKS_DIR = Path(__file__).resolve().parents[1] / "schemas" / "chunks"

# Chunks whose output must be reproducible from a seed the user sets in the UI.
# Every generative Python chunk belongs here; a chunk with no stochastic
# component may be left out via NO_SEED_CHUNKS below, with a reason.
SEED_BEARING_CHUNKS = [
    # Latent Lab instruments
    "output_image_surrealizer_diffusers",
    "output_image_surrealizer_comfyui",
    "output_image_feature_probing_diffusers",
    "output_image_attention_cartography_diffusers",
    "output_image_attention_cartography_comfyui",
    "output_image_concept_algebra_diffusers",
    "output_image_denoising_archaeology_diffusers",
    "output_image_composable_diffusion_comfyui",
    "output_image_concept_algebra_comfyui",
    "output_image_feature_probing_comfyui",
    "output_image_denoising_archaeology_comfyui",
    "output_image_composable_diffusion_diffusers",
    # Standard image generation
    "output_image_sd35_diffusers",
    "output_image_sd35_img2img_diffusers",
    "output_image_sd35_turbo_diffusers",
    "output_image_flux2_diffusers",
    "output_image_flux2_img2img_diffusers",
    "output_image_commoncanvas_diffusers",
    # Video, audio, 3D
    "output_video_wan22_diffusers",
    "output_video_wan22_i2v_diffusers",
    "output_audio_stableaudio_diffusers",
    "output_music_heartmula",
    "output_3d_hunyuan3d",
    # Supertonic zieht einen Seed pro Aeusserung und gibt ihn zurueck
    # (`"seed": "random"` in seinen Voreinstellungen, nachgesehen 2026-08-29) --
    # die Abweichung zwischen zwei Laeufen ist gewollt, aber sie ist benennbar.
    "output_speech_supertonic",
]

# Chunks with no stochastic component and therefore no seed. Empty today —
# add an entry WITH a reason rather than dropping a chunk from both lists.
NO_SEED_CHUNKS: set = {
    # VoxCPM2 has no seed to declare: its generate() takes none (checked
    # against the installed package, 2026-08-12), so two runs of the same
    # sentence differ and there is nothing to hand back. The variation is
    # reported instead of hidden — the measured f0 sits next to every sample.
    "output_speech_voxcpm",
    # espeak ist ein Formant-Synthesizer: nichts daran ist zufaellig, dieselbe
    # Eingabe ergibt dieselbe Welle. Es gibt keinen Seed zu erklaeren
    # (nachgesehen 2026-08-29, das Wort kommt in der Datei nicht vor).
    "output_speech_espeak",
    # Piper zieht sein Rauschen INNERHALB des ONNX-Graphen (RandomNormalLike,
    # 10-11 Knoten je Stimme, nachgesehen 2026-09-18 an de_DE-mls-medium und
    # en_US-lessac-high); weder die Kommandozeile `piper` noch
    # PiperVoice.synthesize (piper-tts 1.6.0) nehmen einen Seed an. Zwei Laeufe
    # desselben Satzes weichen ab, und es gibt nichts zurueckzugeben — die
    # gemessene f0 steht wie bei VoxCPM2 neben jeder Aufnahme.
    "output_speech_piper",
}


def _declared_parameters(chunk_name: str) -> list:
    """Parameter names of the chunk's execute(), read without importing it.

    ast rather than import: the chunk modules pull in GPU clients at import time.
    """
    path = CHUNKS_DIR / f"{chunk_name}.py"
    assert path.is_file(), f"chunk file missing: {path}"

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute":
            a = node.args
            return [arg.arg for arg in a.posonlyargs + a.args + a.kwonlyargs]

    raise AssertionError(f"{chunk_name}.py declares no execute() function")


def test_seed_bearing_chunks_declare_seed():
    """Step 4 delivers 'seed' — the chunk must name it to receive it."""
    missing = [name for name in SEED_BEARING_CHUNKS if "seed" not in _declared_parameters(name)]
    assert not missing, (
        f"execute() declares no 'seed' parameter in: {missing}. The seed injected by "
        f"pipeline_executor lands in **kwargs, is never read, and the chunk generates at "
        f"a random one — irreproducible output, invalid A/B comparison."
    )


def test_seed_bearing_chunks_exist():
    """Sanity: the list does not name chunks that were removed or renamed."""
    for name in SEED_BEARING_CHUNKS:
        assert (CHUNKS_DIR / f"{name}.py").is_file(), (
            f"SEED_BEARING_CHUNKS lists '{name}' but schemas/chunks/{name}.py is missing. "
            f"Update the list if the chunk was removed or renamed."
        )


def test_the_no_seed_list_holds_no_stale_entries():
    """The way around the whole guarantee is to park a chunk here. Every entry
    has to name a chunk that exists AND one that really takes no seed — a chunk
    that declares one belongs in SEED_BEARING_CHUNKS, where it is checked."""
    wrong = []
    for name in sorted(NO_SEED_CHUNKS):
        if not (CHUNKS_DIR / f"{name}.py").is_file():
            wrong.append(f"{name}: no such chunk in schemas/chunks/")
            continue
        if "seed" in _declared_parameters(name):
            wrong.append(f"{name}: declares seed, so it bears one")
    assert not wrong, (
        "NO_SEED_CHUNKS is the exception to the seed guarantee and holds "
        "entries it should not:\n  " + "\n  ".join(wrong))


def test_every_python_chunk_is_classified():
    """A new Python chunk must be listed here or explicitly excluded."""
    on_disk = {p.stem for p in CHUNKS_DIR.glob("*.py") if not p.stem.startswith("_")}
    unclassified = on_disk - set(SEED_BEARING_CHUNKS) - NO_SEED_CHUNKS
    assert not unclassified, (
        f"New Python chunk(s) not covered by the seed policy: {sorted(unclassified)}. "
        f"Add each to SEED_BEARING_CHUNKS, or to NO_SEED_CHUNKS with a reason."
    )


# ---------------------------------------------------------------- ComfyUI side

# The inputs a node draws noise from. A workflow can hold several samplers —
# Wan 2.2 runs a high-noise and a low-noise stage in sequence — and each one
# left out keeps the literal written into the file.
#
# A sampler takes its seed one of two ways: as a number of its own, or as a
# link to another node's output ([node_id, slot]), which is how the two legacy
# workflows share one seed across three and four samplers via a PrimitiveInt.
# A linked sampler is fed by whatever feeds that node, so the mapping has to
# reach the SOURCE, and reaching the sampler itself would overwrite the link.
SEED_INPUTS = ("seed", "noise_seed")

# ComfyUI chunks with no sampler at all. Named rather than skipped silently.
# None at present: the template chunk comfyui_image_generation went with the
# image_generation pipeline no config named (2026-10-10).
NO_SAMPLER_CHUNKS: set = set()


def _comfyui_chunks():
    """(name, chunk) for every ComfyUI chunk that carries its own workflow."""
    import json
    for path in sorted(CHUNKS_DIR.glob("*.json")):
        try:
            chunk = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise AssertionError(f"{path.name} is not readable JSON: {e}")
        # The runtime default, mirrored: backend_router.py reads
        # chunk.get('backend_type', 'comfyui'). A chunk that declares nothing
        # runs as ComfyUI and is held to the same guarantee.
        if chunk.get("backend_type", "comfyui") != "comfyui":
            continue
        yield path.stem, chunk


def _sampler_nodes(workflow: dict) -> dict:
    """{node_id: the seed input it takes} for every node that draws noise."""
    found = {}
    for node_id, node in (workflow or {}).items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        for key in SEED_INPUTS:
            if key in inputs:
                found[str(node_id)] = key
    return found


def _seed_sources(workflow: dict) -> dict:
    """Where each sampler's seed has to be written.

    A sampler holding a number is written to itself. A sampler whose seed is a
    link is written where the link points — the node that holds the number for
    all of them.

    Returns {node to write: [samplers it feeds]}.
    """
    targets = collections.OrderedDict()
    for node_id, key in _sampler_nodes(workflow).items():
        value = ((workflow.get(node_id) or {}).get("inputs") or {}).get(key)
        if isinstance(value, list) and value and isinstance(value[0], str):
            source = value[0]
            field = "value"
            src_inputs = ((workflow.get(source) or {}).get("inputs") or {})
            if "value" not in src_inputs:
                # A source that holds no plain number is not a seed holder.
                field = None
            targets.setdefault((source, field), []).append(node_id)
        else:
            targets.setdefault((node_id, key), []).append(node_id)
    return targets


def test_every_comfyui_chunk_hands_its_samplers_the_seed():
    """One sampler left out keeps the literal that is written in the file.

    A run then answers to the seed for part of its denoising and to a number
    nobody chose for the rest — reproducible, and not reproducible from what
    the person set.
    """
    broken = []
    for name, chunk in _comfyui_chunks():
        workflow = chunk.get("workflow") or {}
        if not _sampler_nodes(workflow):
            continue
        wanted = _seed_sources(workflow)
        mapping = (chunk.get("input_mappings") or {}).get("seed")
        entries = mapping if isinstance(mapping, list) else ([mapping] if mapping else [])
        written = set()
        for entry in entries:
            if not isinstance(entry, dict):
                broken.append(f"{name}: seed mapping entry is not a mapping: {entry!r}")
                continue
            raw_node_id = entry.get("node_id")
            if not isinstance(raw_node_id, str):
                broken.append(
                    f"{name}: node_id {raw_node_id!r} is not a string. The "
                    f"workflow is keyed by strings, so this writes a second, "
                    f"empty node and leaves the sampler at its literal.")
                continue
            field = str(entry.get("field") or "")
            if not field.startswith("inputs."):
                broken.append(
                    f"{name}: field {field!r} misses the `inputs.` step. The "
                    f"value is written where the field says, so this lands "
                    f"beside class_type and the sampler keeps its literal.")
                continue
            node_id = raw_node_id
            key = field.split(".")[-1]
            if (node_id, key) not in wanted:
                broken.append(
                    f"{name}: seed writes {key!r} on node {node_id!r}, which holds no "
                    f"seed — expected one of {sorted(wanted)}")
                continue
            written.add((node_id, key))
        missed = [
            f"{where[0]}.{where[1]} (feeds {', '.join(fed)})"
            for where, fed in wanted.items() if where not in written]
        if missed:
            broken.append(
                f"{name}: {len(wanted)} place(s) hold the seed, "
                f"{len(written)} written — nothing written to {missed}")
    assert not broken, (
        "The seed does not reach every sampler:\n  " + "\n  ".join(broken)
        + "\n\nUse the multi-node form to name them all: "
        '"seed": [{"node_id": "a", "field": "inputs.noise_seed"}, {...}]')


def test_every_comfyui_chunk_is_classified():
    """A ComfyUI chunk with no sampler is named here, not passed over."""
    silent = [name for name, chunk in _comfyui_chunks()
              if not _sampler_nodes(chunk.get("workflow"))]
    unexplained = sorted(set(silent) - NO_SAMPLER_CHUNKS)
    assert not unexplained, (
        f"ComfyUI chunk(s) with no node that draws noise: {unexplained}. "
        f"Add each to NO_SAMPLER_CHUNKS with a reason, or wire its sampler.")
    gone = sorted(NO_SAMPLER_CHUNKS - set(silent))
    assert not gone, (
        f"NO_SAMPLER_CHUNKS names chunks that now have a sampler or are "
        f"gone: {gone}")


def test_injection_is_unconditional():
    """
    Step 4 must stay unconditional. A backend_type test around the injection is
    how the 2026-02-05 regression was built: it silently excluded whatever chunks
    a later migration moved into that backend.
    """
    executor = (
        Path(__file__).resolve().parents[1] / "schemas" / "engine" / "pipeline_executor.py"
    ).read_text(encoding="utf-8")

    marker = "chunk_request['parameters']['seed'] = seed_value"
    assert executor.count(marker) == 1, (
        f"Expected exactly one seed injection site in pipeline_executor.py, found "
        f"{executor.count(marker)}. Step 4 of the seed chain lives in one place."
    )

    # The guarding `if` must test only for the presence of the override.
    line_no = next(
        i for i, line in enumerate(executor.splitlines()) if marker in line
    )
    guard = executor.splitlines()[line_no - 2]
    assert guard.strip() == "if 'seed_override' in context.custom_placeholders:", (
        f"The seed injection is guarded by an unexpected condition: {guard.strip()!r}. "
        f"Step 4 applies to every chunk; a chunk with no use for a seed ignores the "
        f"parameter. Narrowing this by backend_type caused the Feb-Aug 2026 regression."
    )


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
