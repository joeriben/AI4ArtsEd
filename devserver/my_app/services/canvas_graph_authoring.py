"""
Canvas Graph Authoring — validation + expansion for Resona-authored workflow graphs.

Resona ("Resona spricht Graphen") authors a small experimental apparatus as a
graph of steps that this platform executes: input carries a text, interception
transforms it under an instruction Resona writes, translation renders it English
before image models, generation renders media, evaluation has a result read,
comparison_evaluator sets results side by side. This module turns a compact
Resona-authored graph into an executor-ready payload for
CanvasWorkflowExecutor (devserver/my_app/services/canvas_executor.py).

Pure functions, no Flask, no I/O — unit-testable in isolation.

Two responsibilities:
  1. validate_and_expand(graph) — reject malformed/unsafe graphs (unknown node
     types, unknown generation configs, cycles, no input, unreachable nodes,
     bad edges, missing/out-of-range params) and expand generation-node
     convenience keys (seed/width/height/steps/cfg) into the proper param
     source nodes (seed/resolution/quality) the executor reads by walking
     incoming edges.
  2. summarize_graph(payload) — a ≤200-char human line for journal/prompt echoes.

Mirrors the executor's semantics deliberately:
  - Source nodes (self-starting, no meaningful incoming text) = input / seed /
    resolution / quality (see CanvasWorkflowExecutor._find_source_nodes).
  - Type-compat per edge mirrors the executor's accepts_* table
    (_get_next_connections): param nodes (seed/resolution/quality) connect ONLY
    to generation; text connects to interception/translation/generation/
    evaluation/comparison_evaluator; generation output connects to
    evaluation/image_evaluation (the executor does NOT propagate images to
    comparison_evaluator — compare images via image_evaluation readings).
"""

import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# --- Allow-list of generation configIds Resona may wire into a graph ---------
# Terse labels; keys MUST have a matching devserver/schemas/configs/output/<id>.json.
# The 8 shipped text->media configs plus the 6 pedagogical Latent-Lab experiments.
RESONA_CANVAS_CONFIGS: Dict[str, str] = {
    # Shipped text->media configs
    "sd35_large": "SD3.5 Large — detailed images",
    "flux2": "FLUX.2 — images",
    "gemini_3_pro_image": "Gemini 3 Pro image (€ paid cloud call, cloud)",
    "stableaudio_open": "Stable Audio — sound",
    "heartmula_standard": "HeartMuLa — music (lyrics || tags)",
    "wan22_t2v_video_fast": "Wan 2.2 — text-to-video",
    "ltx_video": "LTX — text-to-video",
    "hunyuan3d_text_to_3d": "Hunyuan3D — text-to-3D",
    # Latent-Lab experiments (pedagogical)
    "surrealization": "Surrealizer — embedding inversion",
    "concept_algebra": "Concept Algebra — prompt arithmetic",
    "feature_probing": "Dimension Explorer — embedding dimensions carried from prompt B into A",
    "composable_diffusion": "Composable Diffusion — AND/NOT composition",
    "denoising_archaeology_comfyui": "Denoising Archaeology — interrupted denoising",
    "attention_cartography": "Attention Cartography — attention maps",
}

# Authoring node types Resona may place directly in a graph.
AUTHORING_NODE_TYPES = (
    "input",
    "interception",
    "translation",
    "generation",
    "evaluation",
    "image_evaluation",
    "comparison_evaluator",
    "seed",
    "resolution",
    "quality",
)

# Source node types (self-starting; no meaningful incoming text edge).
# Mirrors CanvasWorkflowExecutor._find_source_nodes (Resona v1 subset:
# input + the three param nodes; image_input/random_prompt are not authored).
_SOURCE_TYPES = ("input", "seed", "resolution", "quality")

# Parameter node types (attach only to generation).
_PARAM_TYPES = ("seed", "resolution", "quality")

# Caps.
MAX_AUTHORED_NODES = 12
MAX_GENERATION_NODES = 4

# Convenience-key int ranges for expansion.
_MIN_SEED = 0
_MAX_SHARED_SEED = 2**31 - 1  # value range for the auto-shared comparison seed


# --- Hand-over to the Canvas ------------------------------------------------
# An expanded payload is a CanvasWorkflow in everything but two things: its
# nodes carry no place on the board, and there is no envelope around them.
#
# The node FIELDS need no translation whatsoever. This module was written
# against the executor and the executor reads the Canvas's own camelCase keys,
# so every key an authored or synthesised node carries — configId, promptText,
# contextPrompt, llmModel, translationPrompt, evaluationPrompt,
# imageEvaluationPrompt, visionModel, comparisonCriteria, comparisonLlmModel,
# seedMode, seedValue, resolutionPreset, resolutionWidth, resolutionHeight,
# qualitySteps, qualityCfg — already sits on CanvasNode
# (public/ai4artsed-frontend/src/types/canvas.ts). configLang is the one
# exception: the executor reads it, the Canvas has no field for it, and it
# travels through untouched.
#
# The board's own measurements, so a laid-out graph reads like a hand-built one:
# CanvasWorkspace.vue holds NARROW_WIDTH 180, WIDE_WIDTH 280, DEFAULT_HEIGHT 80.
_COLUMN_PITCH = 380
_ROW_PITCH = 140
_ORIGIN_X = 80
_ORIGIN_Y = 80


def _depths(nodes: List[Dict[str, Any]],
            connections: List[Dict[str, Any]]) -> Dict[str, int]:
    """How far each node stands from the start, counted in edges.

    The LONGEST path, so a node waiting on two chains of unequal length stands
    behind the longer one and no edge ever points backwards on the board. The
    graph is acyclic — validate_and_expand refuses a cycle — so relaxing every
    edge at most len(nodes) times settles.
    """
    depth = {n["id"]: 0 for n in nodes if isinstance(n.get("id"), str)}
    edges = [(c.get("sourceId"), c.get("targetId")) for c in connections]
    edges = [(a, b) for a, b in edges if a in depth and b in depth]
    for _ in range(len(depth)):
        moved = False
        for src, dst in edges:
            if depth[dst] < depth[src] + 1:
                depth[dst] = depth[src] + 1
                moved = True
        if not moved:
            break
    return depth


def to_canvas_workflow(payload: Dict[str, Any],
                       name: str = "",
                       description: str = "",
                       workflow_id: str = "") -> Dict[str, Any]:
    """An expanded payload as a CanvasWorkflow the Canvas can open.

    Two additions and nothing else: a place on the board for every node, and the
    envelope (id / name / type / timestamps) that canvasStore.loadWorkflow reads.
    Nodes are laid out left to right by their distance from the start, one column
    per step, stacked within a column in the order the graph names them.

    A node keeps everything it already carries; `config` is filled in where it is
    missing, because CanvasNode declares it non-optional.
    """
    nodes = list(payload.get("nodes") or [])
    connections = list(payload.get("connections") or [])
    depth = _depths(nodes, connections)

    rows: Dict[int, int] = {}
    placed: List[Dict[str, Any]] = []
    for n in nodes:
        node = dict(n)
        col = depth.get(node.get("id"), 0)
        row = rows.get(col, 0)
        rows[col] = row + 1
        node.setdefault("config", {})
        node["x"] = _ORIGIN_X + col * _COLUMN_PITCH
        node["y"] = _ORIGIN_Y + row * _ROW_PITCH
        placed.append(node)

    conns = [dict(c) for c in connections]
    _name_the_models(placed)
    _show_the_authored_question(placed)
    _number_the_comparison_inputs(placed, conns)
    _add_collector(placed, conns, rows)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": workflow_id or f"cg_{uuid.uuid4().hex[:8]}",
        "name": name or "Apparatus",
        "description": description or "",
        "type": "canvas_workflow",
        "nodes": placed,
        "connections": conns,
        "createdAt": now,
        "updatedAt": now,
    }


# Which platform setting each kind of node's model comes from, mirroring
# canvas_executor._execute_* exactly.
_MODEL_SETTING = {
    "interception": ("llmModel", "STAGE2_INTERCEPTION_MODEL"),
    "translation": ("llmModel", "STAGE3_MODEL"),
    "evaluation": ("llmModel", "STAGE2_INTERCEPTION_MODEL"),
    "comparison_evaluator": ("comparisonLlmModel", "STAGE2_INTERCEPTION_MODEL"),
    "image_evaluation": ("visionModel", "IMAGE_ANALYSIS_MODEL"),
}


def _name_the_models(nodes: List[Dict[str, Any]]) -> None:
    """Write down the model each node ran on.

    An authored node may leave its model out, and the executor then reads the
    platform setting. The Canvas cannot: canvas.ts's isWorkflowValid requires
    llmModel on every interception and translation node and visionModel on every
    image reading, and without them the imported apparatus opens with errors and
    a dead Run button. So the setting the executor WOULD have read is written
    into the node here — the same value, from the same place, named instead of
    implied. It is also the more honest record: a file that says which model ran
    survives a later change to the setting.
    """
    from my_app.services.canvas_executor import _configured_canvas_model
    for n in nodes:
        field_setting = _MODEL_SETTING.get(n.get("type"))
        if not field_setting:
            continue
        field, setting = field_setting
        if not n.get(field):
            value = _configured_canvas_model(setting)
            if value:
                n[field] = value


def _show_the_authored_question(nodes: List[Dict[str, Any]]) -> None:
    """Make an authored image question visible in the Canvas.

    StageModule.vue renders `imageEvaluationPreset || 'bildwissenschaftlich'` and
    only shows the question field for the preset 'custom', so a node that
    carries a question and no preset opens claiming a framework it does not run
    and hiding the question it does. 'custom' is exactly the case the executor
    reads the authored question in (`preset == 'custom' or authored_prompt_wins`,
    canvas_executor._execute_image_evaluation), so naming it changes nothing
    about what runs and everything about what the card says.
    """
    for n in nodes:
        if (n.get("type") == "image_evaluation"
                and n.get("imageEvaluationPrompt")
                and not n.get("imageEvaluationPreset")):
            n["imageEvaluationPreset"] = "custom"


def _number_the_comparison_inputs(nodes: List[Dict[str, Any]],
                                  connections: List[Dict[str, Any]]) -> None:
    """Label the edges into a comparison the way the Canvas draws them.

    CanvasWorkspace routes a comparison_evaluator's incoming edges by the labels
    'input-1', 'input-2', … that canvas_workflow.vue writes when a person wires
    one by hand. Unlabelled, every reading lands on the same point of the node's
    left edge and its numbered connectors read as unconnected. The executor
    ignores the label and goes by arrival order either way.
    """
    comparisons = {n["id"] for n in nodes if n.get("type") == "comparison_evaluator"}
    seen: Dict[str, int] = {}
    for c in connections:
        target = c.get("targetId")
        if target in comparisons:
            seen[target] = seen.get(target, 0) + 1
            c["label"] = f"input-{seen[target]}"


def _add_collector(nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]],
                   rows: Dict[int, int]) -> None:
    """One collector, gathering whatever the apparatus ends with.

    The executor needs none — it keeps every node's result and reports them all.
    The Canvas does: canvas.ts's isWorkflowValid has hasCollector in it, so
    without one the imported apparatus shows "Missing collector node" and both
    Run and Batch stay disabled. This is the one node in an exported file that
    the room did not run, and it is here so that the file can be run AGAIN.
    """
    if any(n.get("type") == "collector" for n in nodes):
        return
    ids = {n["id"] for n in nodes if isinstance(n.get("id"), str)}
    feeds = {c.get("sourceId") for c in connections}
    # Every node the run ends on, plus every image — a generation that feeds a
    # reading is not an end, and without this the pictures would be the one
    # thing a re-run does not put in the drawer. A parameter node feeds a
    # generation and produces nothing to collect (canvas_executor accepts_seed /
    # accepts_resolution / accepts_quality: generation only), so it stays out.
    gathered = [n for n in nodes
                if isinstance(n.get("id"), str)
                and n.get("type") not in _PARAM_TYPES
                and (n["id"] not in feeds or n.get("type") == "generation")]
    if not gathered:
        return
    cid = "collector"
    while cid in ids:
        cid += "_"
    col = max((n["x"] for n in nodes), default=_ORIGIN_X) + _COLUMN_PITCH
    # id / type / x / y / config and nothing else, exactly as canvasStore.addNode
    # builds one: width and height belong to whoever drags its corner.
    nodes.append({
        "id": cid,
        "type": "collector",
        "config": {},
        "x": col,
        "y": _ORIGIN_Y,
    })
    for e in gathered:
        connections.append({"sourceId": e["id"], "targetId": cid, "label": None})


def _interception_config_ids() -> set:
    """
    The platform's configured interception lenses (configIds), read from
    devserver/schemas/configs/interception/*.json. Cached after first read;
    the single deliberate I/O of this module (instrument fidelity needs the
    real allow-list at DECISION time). Tests may monkeypatch this function.
    """
    global _INTERCEPTION_IDS_CACHE
    if _INTERCEPTION_IDS_CACHE is None:
        from pathlib import Path
        from my_app.services.canvas_executor import _load_interception_context
        cfg_dir = Path(__file__).parent.parent.parent / "schemas" / "configs" / "interception"
        try:
            # A graph may name what the executor will load, read through the
            # executor's own loader. Until 2026-10-01 this list kept a copy of
            # one of its refusals (the looping pipelines), offered configs it
            # refused (no context, an accented id), and offered the configs of
            # the song, image and Latent Lab instruments, whose context is no
            # lens instruction and which it refuses since.
            _INTERCEPTION_IDS_CACHE = {
                cf.stem for cf in cfg_dir.glob("*.json")
                if _load_interception_context(cf.stem)[1] is None
            }
        except OSError:
            _INTERCEPTION_IDS_CACHE = set()
    return _INTERCEPTION_IDS_CACHE


_INTERCEPTION_IDS_CACHE: Optional[set] = None
_MIN_DIM, _MAX_DIM = 256, 2048
_MIN_STEPS, _MAX_STEPS = 1, 60
_MIN_CFG, _MAX_CFG = 0, 15
# Surrealizer instrument params ride inline on the generation node (NOT param
# nodes) and are read directly by the executor. normalized is intentionally not
# offered (scheduled for removal); centered_fade is exposed alongside.
_MIN_ALPHA, _MAX_ALPHA = -75.0, 75.0
_FUSION_STRATEGIES = ("legacy", "dual_alpha", "centered_fade")


def _output_kind(node_type: str) -> str:
    """
    The kind of data a node emits, for edge type-compat.
    'text'  — input/interception/translation/evaluation/image_evaluation/comparison_evaluator
    'media' — generation (image OR audio/video/3d; executor calls it image-ish)
    'param' — seed/resolution/quality
    """
    if node_type in _PARAM_TYPES:
        return "param"
    if node_type == "generation":
        return "media"
    return "text"


def _accepts(target_type: str, source_kind: str) -> bool:
    """
    May an edge carrying `source_kind` legally enter a node of `target_type`?
    Mirrors the executor accepts_* table (see module docstring).
    """
    if source_kind == "param":
        # Param nodes may ONLY feed generation.
        return target_type == "generation"
    if source_kind == "text":
        return target_type in (
            "interception",
            "translation",
            "generation",
            "evaluation",
            "comparison_evaluator",
        )
    if source_kind == "media":
        # Generation output: read-only downstream (no generation->generation).
        # The executor propagates images to evaluation/image_evaluation but NOT
        # to comparison_evaluator (verified live 2026-07-03: the cmp node never
        # ran) — images reach comparison via image_evaluation readings.
        return target_type in ("evaluation", "image_evaluation")
    return False


def _as_int(value: Any) -> Optional[int]:
    """Coerce a JSON number/int-like to int, or None if not an integer value."""
    if isinstance(value, bool):
        return None  # bool is an int subclass — reject explicitly
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s.lstrip("-").isdigit():
            return int(s)
    return None


def validate_and_expand(graph: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate a Resona-authored graph and expand generation-node convenience keys
    into proper param source nodes.

    Returns (expanded_payload, None) on success, (None, error_message) on failure.
    expanded_payload = {"nodes": [...], "connections": [...]} — executor-ready.
    """
    # --- Shape ---------------------------------------------------------------
    if not isinstance(graph, dict):
        return None, "graph must be an object with 'nodes' (list) and optional 'connections' (list)."

    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) == 0:
        return None, "graph.nodes must be a non-empty list of node objects."

    connections = graph.get("connections", [])
    if connections is None:
        connections = []
    if not isinstance(connections, list):
        return None, "graph.connections must be a list (or omitted)."

    if len(nodes) > MAX_AUTHORED_NODES:
        return None, (
            f"Too many nodes ({len(nodes)}). Keep an apparatus small: at most "
            f"{MAX_AUTHORED_NODES} nodes."
        )

    # --- Nodes: ids, types ---------------------------------------------------
    seen_ids: set = set()
    node_types: Dict[str, str] = {}
    gen_count = 0
    for n in nodes:
        if not isinstance(n, dict):
            return None, "each node must be an object."
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip():
            return None, "each node needs a unique non-empty string 'id'."
        if nid in seen_ids:
            return None, f"duplicate node id: '{nid}'."
        seen_ids.add(nid)

        ntype = n.get("type")
        if ntype not in AUTHORING_NODE_TYPES:
            allowed = ", ".join(AUTHORING_NODE_TYPES)
            return None, (
                f"node '{nid}' has unknown type '{ntype}'. Allowed types: {allowed}."
            )
        node_types[nid] = ntype
        if ntype == "generation":
            gen_count += 1

    if gen_count > MAX_GENERATION_NODES:
        return None, (
            f"Too many generation nodes ({gen_count}). At most "
            f"{MAX_GENERATION_NODES} per apparatus."
        )

    # --- Generation nodes: configId must be allow-listed ---------------------
    for n in nodes:
        if n.get("type") != "generation":
            continue
        cfg = n.get("configId")
        if cfg not in RESONA_CANVAS_CONFIGS:
            valid = ", ".join(sorted(RESONA_CANVAS_CONFIGS.keys()))
            return None, (
                f"generation node '{n.get('id')}' has unknown configId "
                f"'{cfg}'. Valid configIds: {valid}."
            )

    # --- Must contain at least one input node --------------------------------
    if not any(t == "input" for t in node_types.values()):
        return None, "graph must contain at least one 'input' node."

    # --- Connections: normalize + validate refs ------------------------------
    norm_conns: List[Dict[str, Any]] = []
    for c in connections:
        if not isinstance(c, dict):
            return None, "each connection must be an object with 'sourceId' and 'targetId'."
        src = c.get("sourceId")
        tgt = c.get("targetId")
        if not isinstance(src, str) or src not in node_types:
            return None, f"connection sourceId '{src}' does not reference an existing node."
        if not isinstance(tgt, str) or tgt not in node_types:
            return None, f"connection targetId '{tgt}' does not reference an existing node."
        if src == tgt:
            return None, f"connection cannot link node '{src}' to itself."
        norm_conns.append({"sourceId": src, "targetId": tgt, "label": c.get("label") or None})

    # --- Type-compat per edge ------------------------------------------------
    for c in norm_conns:
        src_type = node_types[c["sourceId"]]
        tgt_type = node_types[c["targetId"]]
        kind = _output_kind(src_type)
        if not _accepts(tgt_type, kind):
            if kind == "param":
                return None, (
                    f"a {src_type} node may only connect to a generation node "
                    f"(edge '{c['sourceId']}' -> '{c['targetId']}' is invalid)."
                )
            if kind == "media" and tgt_type == "comparison_evaluator":
                return None, (
                    f"images cannot feed comparison_evaluator directly (edge "
                    f"'{c['sourceId']}' -> '{c['targetId']}'): read each image "
                    "with an image_evaluation node first, then connect those "
                    "readings to comparison_evaluator."
                )
            return None, (
                f"a {src_type} node ({kind}) may not connect to a {tgt_type} node "
                f"(edge '{c['sourceId']}' -> '{c['targetId']}' is invalid)."
            )

    # --- Acyclic (simple DFS) ------------------------------------------------
    adj: Dict[str, List[str]] = {nid: [] for nid in node_types}
    for c in norm_conns:
        adj[c["sourceId"]].append(c["targetId"])

    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in node_types}

    def _has_cycle(start: str) -> bool:
        # Iterative DFS with an explicit stack of (node, child-index).
        stack: List[Tuple[str, int]] = [(start, 0)]
        color[start] = GRAY
        while stack:
            node, idx = stack[-1]
            if idx < len(adj[node]):
                stack[-1] = (node, idx + 1)
                nxt = adj[node][idx]
                if color[nxt] == GRAY:
                    return True
                if color[nxt] == WHITE:
                    color[nxt] = GRAY
                    stack.append((nxt, 0))
            else:
                color[node] = BLACK
                stack.pop()
        return False

    for nid in node_types:
        if color[nid] == WHITE:
            if _has_cycle(nid):
                return None, "graph must be acyclic — a cycle was detected."

    # --- Reachability: every non-source node reachable from some source ------
    source_ids = [nid for nid, t in node_types.items() if t in _SOURCE_TYPES]
    reachable: set = set()
    frontier = list(source_ids)
    for s in source_ids:
        reachable.add(s)
    while frontier:
        cur = frontier.pop()
        for nxt in adj[cur]:
            if nxt not in reachable:
                reachable.add(nxt)
                frontier.append(nxt)
    for nid, t in node_types.items():
        if t in _SOURCE_TYPES:
            continue
        if nid not in reachable:
            return None, (
                f"node '{nid}' is not reachable from any source node "
                f"(input/seed/resolution/quality). Wire it into the graph."
            )

    # --- Interception nodes: real lens (configId) XOR authored instruction ---
    # Instrument fidelity (2026-07-16): when the apparatus is about one of the
    # platform's perspectives, the node references it by configId and the REAL
    # lens text runs. An authored contextPrompt stays available for lenses the
    # platform does not have — but never both on one node. Runs after the
    # structural checks so structural errors surface first.
    for n in nodes:
        if n.get("type") != "interception":
            continue
        nid = n.get("id")
        cfg = (n.get("configId") or "").strip() if isinstance(n.get("configId"), str) else n.get("configId")
        ctx = (n.get("contextPrompt") or "").strip() if isinstance(n.get("contextPrompt"), str) else n.get("contextPrompt")
        if cfg and ctx:
            return None, (
                f"interception node '{nid}': give either configId (a configured "
                f"lens of the platform) or contextPrompt (your own instruction), not both."
            )
        if not cfg and not ctx:
            return None, (
                f"interception node '{nid}': needs a lens — configId of a "
                f"configured perspective, or a contextPrompt you write."
            )
        if cfg:
            known = _interception_config_ids()
            if cfg not in known:
                # All of them: lookup_interception action='list_configs'
                # lists every interception config, the ones no node can run
                # among them.
                return None, (
                    f"interception node '{nid}': unknown configId '{cfg}'. "
                    f"The lenses a canvas node can run: {', '.join(sorted(known))}."
                )
        lang = n.get("configLang")
        if lang is not None and (not isinstance(lang, str) or len(lang.strip()) != 2):
            return None, (
                f"interception node '{nid}': configLang must be a 2-letter "
                f"language code (e.g. 'de', 'en')."
            )

    # --- Expansion: convenience keys -> param source nodes -------------------
    expanded_nodes: List[Dict[str, Any]] = []
    synth_nodes: List[Dict[str, Any]] = []
    synth_conns: List[Dict[str, Any]] = []
    synth_ids: set = set(node_types.keys())  # guard against id collisions

    def _fresh_id(base: str) -> str:
        candidate = base
        suffix = 2
        while candidate in synth_ids:
            candidate = f"{base}_{suffix}"
            suffix += 1
        synth_ids.add(candidate)
        return candidate

    for n in nodes:
        if n.get("type") != "generation":
            expanded_nodes.append(dict(n))
            continue

        gid = n["id"]
        node_copy = dict(n)

        # seed
        if "seed" in node_copy:
            sv = _as_int(node_copy.pop("seed"))
            if sv is None or sv < _MIN_SEED:
                return None, (
                    f"generation node '{gid}': seed must be an integer >= {_MIN_SEED}."
                )
            sid = _fresh_id(f"{gid}__seed")
            synth_nodes.append(
                {"id": sid, "type": "seed", "seedMode": "fixed", "seedValue": sv}
            )
            synth_conns.append({"sourceId": sid, "targetId": gid, "label": None})

        # width/height -> resolution
        has_w = "width" in node_copy
        has_h = "height" in node_copy
        if has_w or has_h:
            wv = _as_int(node_copy.pop("width", None)) if has_w else None
            hv = _as_int(node_copy.pop("height", None)) if has_h else None
            if not has_w or not has_h:
                return None, (
                    f"generation node '{gid}': width and height must be given "
                    f"together to set a custom resolution."
                )
            if wv is None or hv is None or not (_MIN_DIM <= wv <= _MAX_DIM) or not (
                _MIN_DIM <= hv <= _MAX_DIM
            ):
                return None, (
                    f"generation node '{gid}': width/height must be integers "
                    f"between {_MIN_DIM} and {_MAX_DIM}."
                )
            rid = _fresh_id(f"{gid}__resolution")
            synth_nodes.append(
                {
                    "id": rid,
                    "type": "resolution",
                    "resolutionPreset": "custom",
                    "resolutionWidth": wv,
                    "resolutionHeight": hv,
                }
            )
            synth_conns.append({"sourceId": rid, "targetId": gid, "label": None})

        # steps/cfg -> quality
        has_steps = "steps" in node_copy
        has_cfg = "cfg" in node_copy
        if has_steps or has_cfg:
            qn: Dict[str, Any] = {"type": "quality"}
            if has_steps:
                stv = _as_int(node_copy.pop("steps"))
                if stv is None or not (_MIN_STEPS <= stv <= _MAX_STEPS):
                    return None, (
                        f"generation node '{gid}': steps must be an integer "
                        f"between {_MIN_STEPS} and {_MAX_STEPS}."
                    )
                qn["qualitySteps"] = stv
            if has_cfg:
                cfv = node_copy.pop("cfg")
                # cfg may be a float; accept int or float in range.
                if isinstance(cfv, bool) or not isinstance(cfv, (int, float)):
                    cfv_num: Optional[float] = None
                    if isinstance(cfv, str):
                        try:
                            cfv_num = float(cfv.strip())
                        except ValueError:
                            cfv_num = None
                else:
                    cfv_num = float(cfv)
                if cfv_num is None or not (_MIN_CFG <= cfv_num <= _MAX_CFG):
                    return None, (
                        f"generation node '{gid}': cfg must be a number between "
                        f"{_MIN_CFG} and {_MAX_CFG}."
                    )
                # keep an int as int, else float
                qn["qualityCfg"] = int(cfv_num) if float(cfv_num).is_integer() else cfv_num
            qid = _fresh_id(f"{gid}__quality")
            qn["id"] = qid
            synth_nodes.append(qn)
            synth_conns.append({"sourceId": qid, "targetId": gid, "label": None})

        # Surrealizer instrument params: alpha_factor + fusion_strategy. Unlike
        # seed/resolution/quality these are NOT universal render params and get no
        # param node -- they ride inline on the generation node and are read directly
        # by the executor. Guard here; only surrealization accepts them.
        cfg_id = node_copy.get("configId")
        if "alpha_factor" in node_copy or "fusion_strategy" in node_copy:
            if cfg_id != "surrealization":
                return None, (
                    f"generation node '{gid}': alpha_factor/fusion_strategy are only "
                    f"valid for configId 'surrealization'."
                )
            if "alpha_factor" in node_copy:
                av = node_copy["alpha_factor"]
                if isinstance(av, bool) or not isinstance(av, (int, float)):
                    if isinstance(av, str):
                        try:
                            av = float(av.strip())
                        except ValueError:
                            av = None
                    else:
                        av = None
                if av is None or not (_MIN_ALPHA <= av <= _MAX_ALPHA):
                    return None, (
                        f"generation node '{gid}': alpha_factor must be a number "
                        f"between {_MIN_ALPHA} and {_MAX_ALPHA}."
                    )
                node_copy["alpha_factor"] = int(av) if float(av).is_integer() else float(av)
            if "fusion_strategy" in node_copy:
                fs = node_copy["fusion_strategy"]
                if fs not in _FUSION_STRATEGIES:
                    return None, (
                        f"generation node '{gid}': fusion_strategy must be one of "
                        f"{', '.join(_FUSION_STRATEGIES)}."
                    )

        expanded_nodes.append(node_copy)

    # --- Shared comparison seed (2026-07-16, method before effect) -----------
    # An apparatus that renders the same motif more than once is a comparison;
    # with per-branch random seeds the image difference is not attributable to
    # the text difference (n=1, uncontrolled). If the author set NO seed
    # anywhere, all generation nodes share ONE fixed seed, freshly drawn per
    # validation — differences then come from the text, not the dice.
    # Explicit seeds (convenience key or authored seed node) are respected.
    gen_ids = [n["id"] for n in nodes if n.get("type") == "generation"]
    any_seed_authored = (
        any(t == "seed" for t in node_types.values())
        or any(sn.get("type") == "seed" for sn in synth_nodes)
    )
    if len(gen_ids) >= 2 and not any_seed_authored:
        shared_value = random.randint(_MIN_SEED, _MAX_SHARED_SEED)
        sid = _fresh_id("shared__seed")
        synth_nodes.append(
            {"id": sid, "type": "seed", "seedMode": "fixed", "seedValue": shared_value}
        )
        for gid in gen_ids:
            synth_conns.append({"sourceId": sid, "targetId": gid, "label": None})

    payload = {
        "nodes": expanded_nodes + synth_nodes,
        "connections": norm_conns + synth_conns,
    }
    return payload, None


def summarize_graph(payload: Dict[str, Any]) -> str:
    """
    A compact (≤200 char) human line describing an executor-ready payload, for
    journal/prompt echoes. Example:
      "input → interception ('a lens…') → 2× generation(sd35_large, flux2)"
    """
    if not isinstance(payload, dict):
        return ""
    nodes = payload.get("nodes", []) or []

    order = ("input", "interception", "translation", "generation", "evaluation", "image_evaluation", "comparison_evaluator")
    counts: Dict[str, int] = {}
    interception_ctx: Optional[str] = None
    gen_configs: List[str] = []
    for n in nodes:
        t = n.get("type")
        if t in _PARAM_TYPES:
            continue  # synthesized params are noise in the summary
        counts[t] = counts.get(t, 0) + 1
        if t == "interception" and interception_ctx is None:
            cfg_ref = (n.get("configId") or "").strip()
            ctx = (n.get("contextPrompt") or "").strip()
            if cfg_ref:
                interception_ctx = f"lens:{cfg_ref}"
            elif ctx:
                interception_ctx = ctx
        if t == "generation":
            cfg = n.get("configId")
            if cfg:
                gen_configs.append(cfg)

    parts: List[str] = []
    for t in order:
        c = counts.get(t, 0)
        if c == 0:
            continue
        if t == "interception" and interception_ctx:
            snippet = interception_ctx
            if len(snippet) > 30:
                snippet = snippet[:29].rstrip() + "…"
            label = f"interception ('{snippet}')"
        elif t == "generation" and gen_configs:
            label = f"generation({', '.join(gen_configs)})"
        else:
            label = t
        if c > 1 and t != "generation":
            label = f"{c}× {label}"
        elif c > 1 and t == "generation":
            label = f"{c}× {label}"
        parts.append(label)

    summary = " → ".join(parts) if parts else "empty graph"
    if len(summary) > 200:
        summary = summary[:199].rstrip() + "…"
    return summary
