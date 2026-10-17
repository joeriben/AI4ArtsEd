"""Every ready-made Canvas workflow opens, names only what exists, and runs whole.

The presets in schemas/canvas_presets are what "New" offers on the Canvas
(views/canvas_workflow.vue, lib/canvasPresets.ts). They are data, and every name
in them is a string: a perspective, an output config, a lineup of the model
register, a reading frame, a prompt of the platform's example list. A name that
stops resolving does not fail loudly anywhere -- a lens fetch answers 404 and the
node runs with no perspective, a generation node stands without a model -- so the
names are read here, against the same sources the surface and the executor read.

What is checked, per file:

1. It is a Canvas workflow with a `preset` block: an id that is the file's own
   name, a kind (basic forms or explorations), an order, a medium, and i18n keys
   for its name and description. (That the keys exist in en.ts is the frontend's
   test, lib/__tests__/canvasPresets.spec.ts, which can read the locale.)
2. Its nodes are of types the executor runs, with unique ids, and its
   connections join nodes that are there, under labels the board uses.
3. A generation node names an output config that exists; an interception node a
   lens the Canvas lists AND the executor can run; a lineup a lineup the model
   register names, at a place it has; an image analysis node a reading frame
   both the backend and the board know; an adaption node a preset the executor
   maps; an input node a prompt of the platform's example list.
4. A whole run fits inside the executor's cap on executions: past it the run
   stops where it is, and a chain like Telephone would end mid-way, silently.
5. A preset whose result is a picture has its preview picture on disk, where the
   ring reads it (public/canvas-presets/<id>.webp), and the server hands it out
   as a picture: the SPA route answers a path it does not serve as a file with
   index.html and 200, which the ring shows as a plain disc.

Run: cd devserver && python3 -m pytest tests/test_canvas_presets.py -q
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pytest

from file_modules import DEVSERVER

REPO = DEVSERVER.parent
SCHEMAS = DEVSERVER / "schemas"
PRESETS = SCHEMAS / "canvas_presets"
FRONTEND = REPO / "public" / "ai4artsed-frontend"
SRC = FRONTEND / "src"
PREVIEWS = FRONTEND / "public" / "canvas-presets"
sys.path.insert(0, str(DEVSERVER))

from my_app.services.canvas_executor import (  # noqa: E402
    MAX_TOTAL_EXECUTIONS,
    NODE_TYPE_LABELS,
    _ADAPTION_CONFIGS,
    _ADAPTION_MEDIA,
    _load_interception_context,
)
from my_app.services import reading_frames  # noqa: E402

KINDS = {"basic", "explore"}
MEDIA = {"image", "video", "sound", "text"}
LABELS = {None, "input-1", "input-2", "params"}
SOURCES = {"input", "image_input", "seed", "resolution", "quality"}
PARAMS = {"seed", "resolution", "quality"}

FILES = sorted(PRESETS.glob("*.atcanvas"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canvas_lenses() -> set:
    """The lens ids the Canvas node offers (types/canvas.ts INTERCEPTION_PRESETS)."""
    text = (SRC / "types" / "canvas.ts").read_text(encoding="utf-8")
    block = text.split("export const INTERCEPTION_PRESETS", 1)[1].split("\n}\n", 1)[0]
    return set(re.findall(r"^\s*'?([^\s':]+)'?\s*:\s*\{\s*label", block, re.M))


def _board_frames() -> set:
    """The reading frames the board offers (data/readingFrames.ts)."""
    text = (SRC / "data" / "readingFrames.ts").read_text(encoding="utf-8")
    block = text.split("READING_FRAMES = [", 1)[1].split("]", 1)[0]
    return set(re.findall(r"'([^']+)'", block))


def _example_prompts() -> set:
    """The platform's example prompts (lib/promptPresets.ts PROMPT_PRESETS)."""
    text = (SRC / "lib" / "promptPresets.ts").read_text(encoding="utf-8")
    block = text.split("PROMPT_PRESETS = [", 1)[1].split("]", 1)[0]
    return set(re.findall(r"'([^']+)'", block))


def _lineups() -> dict:
    register = json.loads((DEVSERVER / "config" / "model_register.json").read_text(encoding="utf-8"))
    return register.get("interception_lineups") or {}


def _executions(nodes: list, connections: list) -> int:
    """How many work items the executor processes for one run of this graph.

    The executor's queue (services/canvas_executor.py execute_with_events): every
    source is one item; every item a node finishes sends one item down each of
    its connections -- except a parameter node, which sends nothing and is read
    by the generation from the results, and a generation, which counts every
    text item that reaches it but sends its result on only once the last of its
    text inputs has arrived.
    """
    types = {n["id"]: n["type"] for n in nodes}
    outgoing = defaultdict(list)
    text_in = defaultdict(int)
    for c in connections:
        outgoing[c["sourceId"]].append(c["targetId"])
        if types[c["sourceId"]] not in PARAMS:
            text_in[c["targetId"]] += 1
    queue = [n["id"] for n in nodes if n["type"] in SOURCES]
    arrived = defaultdict(int)
    count = 0
    while queue:
        node_id = queue.pop(0)
        count += 1
        assert count <= 10 * MAX_TOTAL_EXECUTIONS, "the graph does not end"
        kind = types[node_id]
        if kind in PARAMS:
            continue
        if kind == "generation":
            arrived[node_id] += 1
            if arrived[node_id] < text_in[node_id]:
                continue
        queue.extend(outgoing[node_id])
    return count


def test_presets_are_there():
    assert FILES, f"no presets in {PRESETS}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_preset_block(path):
    data = _load(path)
    assert data.get("type") == "canvas_workflow"
    block = data.get("preset")
    assert isinstance(block, dict), "no preset block"
    assert block.get("id") == path.stem
    assert block.get("kind") in KINDS
    assert isinstance(block.get("order"), int)
    assert block.get("medium") in MEDIA
    for field in ("name", "description"):
        assert isinstance(block.get(field), str) and "." in block[field], f"{field} is no i18n key"


def test_orders_are_unique_per_kind():
    seen = defaultdict(list)
    for path in FILES:
        block = _load(path)["preset"]
        seen[block["kind"]].append(block["order"])
    for kind, orders in seen.items():
        assert len(orders) == len(set(orders)), f"two {kind} presets share an order: {orders}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_graph(path):
    data = _load(path)
    nodes, connections = data["nodes"], data.get("connections", [])
    ids = [n["id"] for n in nodes]
    assert len(ids) == len(set(ids)), "two nodes share an id"
    for n in nodes:
        assert n["type"] in NODE_TYPE_LABELS, f"{n['id']}: the executor runs no '{n['type']}'"
        assert isinstance(n.get("x"), (int, float)) and isinstance(n.get("y"), (int, float))
    assert any(n["type"] == "collector" for n in nodes), "no collector"
    for c in connections:
        assert c["sourceId"] in ids and c["targetId"] in ids, f"dangling connection {c}"
        assert c.get("label") in LABELS, f"unknown label {c.get('label')!r}"
        target = next(n for n in nodes if n["id"] == c["targetId"])
        if target["type"] == "generation":
            source = next(n for n in nodes if n["id"] == c["sourceId"])
            want = {"params"} if source["type"] in PARAMS else {"input-1", "input-2"}
            assert c.get("label") in want, f"{c['sourceId']} -> {c['targetId']} needs one of {want}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_names_resolve(path):
    lenses = _canvas_lenses()
    frames = _board_frames()
    prompts = _example_prompts()
    lineups = _lineups()
    for n in _load(path)["nodes"]:
        where = f"{path.stem}/{n['id']}"
        if n["type"] == "generation":
            cfg = n.get("configId")
            assert cfg and (SCHEMAS / "configs" / "output" / f"{cfg}.json").exists(), \
                f"{where}: no output config '{cfg}'"
        if n["type"] == "interception" and n.get("interceptionPreset"):
            lens = n["interceptionPreset"]
            assert lens in lenses, f"{where}: the Canvas lists no lens '{lens}'"
            _, err = _load_interception_context(lens)
            assert err is None, f"{where}: {err}"
        if "lineup" in n:
            name, place = n["lineup"]
            assert name in lineups, f"{where}: the register names no lineup '{name}'"
            assert 0 <= place < len(lineups[name]), f"{where}: '{name}' has no place {place}"
        if n["type"] == "image_evaluation":
            frame = n.get("imageEvaluationPreset")
            assert frame in frames, f"{where}: the board offers no frame '{frame}'"
            assert reading_frames.has(frame), f"{where}: the backend has no frame '{frame}'"
        if n["type"] == "model_adaption":
            preset = n.get("modelAdaptionPreset")
            assert preset in _ADAPTION_CONFIGS or preset in _ADAPTION_MEDIA, \
                f"{where}: the executor maps no adaption '{preset}'"
        if "promptPreset" in n:
            assert n["promptPreset"] in prompts, f"{where}: no example prompt '{n['promptPreset']}'"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_a_run_fits_the_cap(path):
    data = _load(path)
    count = _executions(data["nodes"], data.get("connections", []))
    assert count <= MAX_TOTAL_EXECUTIONS, f"{count} executions, the cap is {MAX_TOTAL_EXECUTIONS}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_picture_presets_have_their_preview(path):
    block = _load(path)["preset"]
    if block["medium"] != "image":
        return
    # Asked of the frontend's source, not of the picture folder: the commit
    # gate copies public/canvas-presets only when the index holds a file of it,
    # so a missing folder is exactly the case this test is for.
    if not SRC.exists():
        pytest.skip("the frontend is not in this tree")
    assert (PREVIEWS / f"{block['id']}.webp").exists(), f"no preview {block['id']}.webp in {PREVIEWS}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_the_server_hands_out_the_preview(path, tmp_path):
    """/canvas-presets/<id>.webp comes back as the picture, not as the app's page."""
    block = _load(path)["preset"]
    if block["medium"] != "image":
        return
    if not PREVIEWS.exists():
        pytest.skip("the frontend's public folder is not in this tree")
    from flask import Flask
    from my_app.routes.static_routes import static_bp

    picture = PREVIEWS / f"{block['id']}.webp"
    (tmp_path / "canvas-presets").mkdir()
    (tmp_path / "canvas-presets" / picture.name).write_bytes(picture.read_bytes())
    (tmp_path / "index.html").write_text("<!DOCTYPE html>", encoding="utf-8")
    app = Flask(__name__, static_folder=str(tmp_path), static_url_path=None)
    app.register_blueprint(static_bp)
    response = app.test_client().get(f"/canvas-presets/{picture.name}")
    assert response.status_code == 200
    assert response.mimetype == "image/webp", f"answered as {response.mimetype}"
    assert response.data == picture.read_bytes()
