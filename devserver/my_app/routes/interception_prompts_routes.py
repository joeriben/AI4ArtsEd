"""
/api/interception-prompts/* — what a person keeps of their own (P3).

This blueprint owns the *authoring* surface: CRUD over one's own
InterceptionPrompt rows, the SAVE-AS-FORK flow over the immutable PRESET
configs, duplication, non-destructive version history, the two restore paths
(back to an earlier own edit / back to the preset Original), and a preview that
runs through the real safety chain.

WHO MAY KEEP: everyone who is logged in. A participant's own
perspective belongs to them exactly as an educator's does — the gate is
`require_auth`, not a role. What a course SHOWS its members stays the leader's
decision and lives in courses_routes.py as the CoursePaletteItem palette.

Invariants this file honours:
  * No code path writes schemas/configs/interception/*.json — PRESETS are
    immutable. Forking/editing only ever creates or mutates a DB row; the preset
    JSON stays latent and is always restorable.
  * Editing snapshots the PRIOR state into PromptVersion BEFORE mutating, so own
    edits are non-destructively reversible.
  * revert-to-preset re-copies the current preset content into the fork
    (snapshot first), restoring the latent Original without touching the file.
  * style_key format is "preset:<name>" / "custom:<prompt_id>" — identical across
    resolver, routes and frontend.
  * Safety prefixes (kids/youth) still apply — they are prepended later in
    instruction_selector.get_instruction(), regardless of where `context` came
    from, so a kept prompt can NEVER bypass safety (the preview shows this).

Location: devserver/my_app/routes/interception_prompts_routes.py
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Optional

from flask import Blueprint, request, jsonify

from my_app.lab.db import SessionLocal
from my_app.lab.models import Role, InterceptionPrompt, PromptVersion
from my_app.lab.auth_service import current_user, require_auth
from my_app.services.course_prompt_resolver import (
    ALLOWED_PIPELINES,
    course_prompt_resolver,
    is_offerable_perspective,
)

logger = logging.getLogger(__name__)

prompts_bp = Blueprint(
    "interception_prompts", __name__, url_prefix="/api/interception-prompts"
)

MAX_CONTEXT_LEN = 8000
MAX_NAME_LEN = 200
MAX_SAMPLE_LEN = 4000
_SAFETY_LEVELS = ("kids", "youth", "open")

# What a kept perspective may carry in `parameters`, and nothing else.
#
# These reach two places: the model call, and the placeholder context the chunk
# builder assembles. Until a perspective could be written by whoever is logged
# in, they came only from reviewed JSON — so this is an ALLOWLIST, not a list of
# refusals. Two kinds of key are absent on purpose and must stay absent:
#
#   * the reserved placeholder names (TASK_INSTRUCTION, INPUT_TEXT, CONTEXT,
#     INSTRUCTION, USER_INPUT, PREVIOUS_OUTPUT). A parameter of that name used
#     to overwrite the very value the safety chain had just computed, which took
#     the kids/youth prefix back out of the prompt. chunk_builder no longer lets
#     a parameter shadow them at all; this list keeps them from being written in
#     the first place.
#   * every output cap (max_tokens and its aliases). A hard cap truncates a
#     transformation mid-sentence and is forbidden platform-wide. The presets
#     shed theirs in d4f8a89a; the 34 JSONs that still carried one turned out to
#     be a 2025-11 backup snapshot under configs/tmp/, which the loader read like
#     any other config until EXCLUDED_CONFIG_DIRS stopped it. Nothing kept here
#     can add one back, whatever a fork inherits from.
#   * top_p, top_k, min_p, presence_penalty and frequency_penalty, accepted
#     and bounded here until 2026-10-10 while no model call read them: the
#     interception engine hands a local model temperature, max_tokens,
#     repetition_penalty and enable_thinking, a cloud model temperature and
#     max_tokens (finding S-012 of the code review of 2026-10-10). A kept perspective that still carries one of them
#     from before that day is cleaned on its next update, not refused.
ALLOWED_PARAM_KEYS = {
    "temperature",
    "repetition_penalty",
    "enable_thinking",
    # read by text_transformation_recursive
    "iterations", "use_random_languages", "final_language",
}

# Bounds for the numeric ones. `iterations` is bounded because it multiplies the
# number of model calls a single run makes.
_PARAM_BOUNDS = {
    "temperature": (0.0, 2.0),
    "repetition_penalty": (0.0, 4.0),
    "iterations": (1.0, 10.0),
}


# ---------------------------------------------------------------------------
# config_loader access (lazy — this module must import before the engine exists)
# ---------------------------------------------------------------------------
def _preset_resolved(preset_name: str):
    """Resolve a PRESET config by name (read-only, never mutates).

    Warms the engine first: the loader reads its JSON only when asked to, and
    this blueprint can be the first thing touched after a restart. Cold, it
    knows no name at all, so every base config would have been refused.
    """
    from my_app.routes.schema_pipeline_routes import init_schema_engine
    init_schema_engine()
    from schemas.engine.config_loader import config_loader
    return config_loader.get_config(preset_name)


def _base_or_none(preset_name: str):
    """Resolve `preset_name` only if it may be the structure of a perspective.

    `base_config` decides which PIPELINE and CHUNKS the kept text runs through,
    so existence is not the question — offerability is. The predicate lives in
    course_prompt_resolver and is the same one the course palette asks.
    """
    if not isinstance(preset_name, str) or not preset_name.strip():
        return None
    name = preset_name.strip()
    resolved = _preset_resolved(name)
    return resolved if is_offerable_perspective(name, resolved) else None


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def _validate_prompt(data: dict) -> tuple[bool, str]:
    """Validate authored prompt content (context length, pipeline, params).

    Applied on create and on the MERGED view of an update, so a partial update
    cannot walk the row out of the invariants.
    """
    ctx = data.get("context_text")
    if not ctx:
        return False, "context_text required"
    # str OR i18n dict {de,en,...}; resolve_context_language() handles both.
    if isinstance(ctx, str):
        text_len = len(ctx)
    elif isinstance(ctx, dict):
        text_len = max((len(v) for v in ctx.values() if isinstance(v, str)), default=0)
    else:
        return False, "context_text must be a string or an i18n dict"
    if text_len == 0:
        return False, "context_text empty"
    if text_len > MAX_CONTEXT_LEN:
        return False, f"context_text too long (>{MAX_CONTEXT_LEN})"
    if data.get("pipeline", "text_transformation") not in ALLOWED_PIPELINES:
        return False, "pipeline not allowed"

    bc = data.get("base_config")
    if bc is not None and not isinstance(bc, str):
        return False, "base_config must be a string"

    ti = data.get("task_instruction")
    if ti is not None:
        if not isinstance(ti, str):
            return False, "task_instruction must be a string"
        if len(ti) > MAX_CONTEXT_LEN:
            return False, f"task_instruction too long (>{MAX_CONTEXT_LEN})"

    params = data.get("parameters") or {}
    if not isinstance(params, dict):
        return False, "parameters must be an object"
    for key, value in params.items():
        if key not in ALLOWED_PARAM_KEYS:
            return False, f"parameter '{key}' not allowed"
        if key in _PARAM_BOUNDS:
            lo, hi = _PARAM_BOUNDS[key]
            try:
                num = float(value)
            except (TypeError, ValueError):
                return False, f"parameter '{key}' must be numeric"
            if not (lo <= num <= hi):
                return False, f"parameter '{key}' out of range ({lo}..{hi})"
        elif not isinstance(value, (str, bool, int, float)) or isinstance(value, bytes):
            return False, f"parameter '{key}' must be a scalar"
    return True, ""


def _clean_params(raw) -> dict:
    """Keep only what the allowlist names.

    Used where the parameters were NOT authored by the caller — forking a preset
    copies that preset's own parameters, and those carry keys (max_tokens above
    all) that a kept perspective must not inherit.
    """
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in ALLOWED_PARAM_KEYS}


def _fold_name(label: str) -> str:
    """The form two names are compared in.

    Several given names carry a soft hyphen (U+00AD) where they may be broken
    across the lines of a round tile. It is invisible and `str.strip()` leaves
    it in place, so `Konsum\u00adkritik` and `Konsumkritik` read as two
    different names while a person sees one — which is exactly the collision
    this guard exists to catch.
    """
    return label.replace("\u00ad", "").strip().lower()


def _preset_display_names() -> set:
    """Every name a GIVEN perspective goes by, in every language it carries."""
    names = set()
    try:
        from my_app.routes.schema_pipeline_routes import init_schema_engine
        init_schema_engine()
        from schemas.engine.config_loader import config_loader
        for cfg_name in config_loader.list_configs():
            resolved = config_loader.get_config(cfg_name)
            if resolved is None:
                continue
            if (getattr(resolved, "meta", None) or {}).get("stage") != "interception":
                continue
            for label in (getattr(resolved, "display_name", None) or {}).values():
                if isinstance(label, str) and label.strip():
                    names.add(_fold_name(label))
    except Exception:
        # The catalogue is unreadable. One's own names still are, and a check
        # that refuses to run would refuse every save with it.
        logger.warning("[PROMPT-LIB] preset catalogue unreadable for the name check",
                       exc_info=True)
    return names


def _taken_names(owner_id: int, except_id: Optional[int] = None) -> set:
    """Every name already spoken for: the given perspectives, and this person's
    own. `except_id` is the row being written over.

    A title must not repeat an existing one. Earlier a saved perspective took
    the name of the preset it was written over, wore that preset's picture,
    and stood beside it in the chooser with nothing to tell the two apart.
    """
    taken = _preset_display_names()
    db = SessionLocal()
    rows = db.query(InterceptionPrompt).filter(
        InterceptionPrompt.owner_id == owner_id
    ).all()
    for row in rows:
        if except_id is not None and row.id == except_id:
            continue
        if row.name and row.name.strip():
            taken.add(_fold_name(row.name))
    return taken


def _free_name(fallback: str, taken: set) -> str:
    """A name this route invents itself is made free rather than refused —
    there is nobody at the other end to ask."""
    stem = (fallback or "Untitled").strip() or "Untitled"
    if _fold_name(stem) not in taken:
        return stem[:MAX_NAME_LEN]
    i = 2
    while _fold_name(f"{stem} {i}") in taken:
        i += 1
    return f"{stem} {i}"[:MAX_NAME_LEN]


def _resolve_name(raw, fallback: str, owner_id: int,
                  except_id: Optional[int] = None):
    """(name, error_response). A name a PERSON wrote is refused when it is
    taken; one this route falls back to is made free instead."""
    taken = _taken_names(owner_id, except_id)
    given = (raw or "").strip() if isinstance(raw, str) else ""
    if given:
        if _fold_name(given) in taken:
            return None, (jsonify({
                "error": f"the name '{given}' already belongs to another perspective"
            }), 409)
        return given[:MAX_NAME_LEN], None
    return _free_name(fallback, taken), None


# ---------------------------------------------------------------------------
# authz helpers (owner-or-admin)
# ---------------------------------------------------------------------------
def _owned_or_404(pid: int) -> Optional[InterceptionPrompt]:
    """Return the prompt if it exists and the caller owns it (admin overrides).

    Returns None for both 'missing' and 'not mine', so callers answer 404 in
    either case and do not leak the existence of somebody else's prompt.
    """
    user = current_user()
    p = SessionLocal().get(InterceptionPrompt, pid)
    if p is None:
        return None
    if p.owner_id != user.id and user.role != Role.admin:
        return None
    return p


def _commit_or_conflict(db):
    """Commit, or answer 409 if the version number was taken meanwhile.

    Two edits of the same perspective at the same moment both read the same
    highest version_no and both wrote next_no; the second hit
    uq_prompt_version_no and came back as an unhandled 500. Nothing is lost —
    the first edit stands — so the second is told exactly that.
    """
    from sqlalchemy.exc import IntegrityError
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify({
            "error": "this perspective was edited somewhere else a moment ago — "
                     "reload it and make the change again"
        }), 409
    return None


def _snapshot_version(db, p: InterceptionPrompt) -> PromptVersion:
    """Write a PromptVersion capturing the PRIOR state of `p` BEFORE it mutates.

    version_no increases monotonically per prompt. Called inside the same
    transaction as the mutation, so snapshot and change commit together.
    """
    last = (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == p.id)
        .order_by(PromptVersion.version_no.desc())
        .first()
    )
    next_no = (last.version_no + 1) if last else 1
    snap = PromptVersion(
        prompt_id=p.id,
        version_no=next_no,
        name=p.name,
        context_text=p.context_text,
        task_instruction=p.task_instruction,
        parameters=p.parameters or {},
        created_by=current_user().id,
    )
    db.add(snap)
    return snap


# ---------------------------------------------------------------------------
# what I keep
# ---------------------------------------------------------------------------
@prompts_bp.route("", methods=["GET"])
@require_auth
def list_prompts():
    """Everything the caller keeps, newest first."""
    user = current_user()
    rows = (
        SessionLocal()
        .query(InterceptionPrompt)
        .filter(InterceptionPrompt.owner_id == user.id)
        .order_by(InterceptionPrompt.updated_at.desc())
        .all()
    )
    return jsonify({"prompts": [p.to_dict() for p in rows]}), 200


@prompts_bp.route("/<int:pid>", methods=["GET"])
@require_auth
def get_prompt(pid: int):
    p = _owned_or_404(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"prompt": p.to_dict()}), 200


@prompts_bp.route("", methods=["POST"])
@require_auth
def create_prompt():
    """Keep a perspective written from scratch.

    `base_config` names the preset whose PIPELINE and CHUNKS this text runs
    through — structure only, no content. It defaults to `user_defined`, which is
    the blank perspective ("Du bestimmst") the surface already offers.
    """
    data = request.get_json(silent=True) or {}
    raw_base = data.get("base_config")
    if raw_base is not None and not isinstance(raw_base, str):
        return jsonify({"error": "base_config must be a string"}), 400
    base_config = (raw_base or "user_defined").strip() or "user_defined"
    payload = {**data, "base_config": base_config}
    ok, err = _validate_prompt(payload)
    if not ok:
        return jsonify({"error": err}), 400
    base = _base_or_none(base_config)
    if base is None:
        return jsonify({
            "error": f"'{base_config}' cannot be the structure of a perspective"
        }), 400

    name, name_err = _resolve_name(data.get("name"), "Untitled", current_user().id)
    if name_err:
        return name_err

    db = SessionLocal()
    p = InterceptionPrompt(
        owner_id=current_user().id,
        name=name,
        base_config=base_config,
        # Derived, never taken from the body: the pipeline that actually runs is
        # the base config's, so a `pipeline` field in the request would only ever
        # be a second, decorative truth.
        pipeline=base.pipeline_name or "text_transformation",
        context_text=data["context_text"],
        task_instruction=data.get("task_instruction"),
        parameters=data.get("parameters") or {},
        is_published=bool(data.get("is_published", False)),
        forked_from_preset=None,
        forked_from_prompt_id=None,
    )
    db.add(p)
    db.commit()
    logger.info("[PROMPT-LIB] user #%s kept a new perspective -> custom:%s",
                p.owner_id, p.id)
    return jsonify({"prompt": p.to_dict()}), 201


@prompts_bp.route("/<int:pid>", methods=["PUT"])
@require_auth
def update_prompt(pid: int):
    """Edit one's own. Snapshots the PRIOR state into PromptVersion FIRST, so
    every own edit stays reversible. Editing a fork never touches the preset."""
    p = _owned_or_404(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    # The stored row may carry a parameter the allowlist has since retired;
    # the merged view is validated without it, so an old perspective stays
    # editable.
    stored = p.to_dict()
    stored["parameters"] = _clean_params(stored.get("parameters"))
    ok, err = _validate_prompt({**stored, **data})
    if not ok:
        return jsonify({"error": err}), 400
    new_pipeline = None
    if "base_config" in data:
        # No falsy escape hatch: whatever is assigned is checked, including ""
        # and null, which previously skipped the check and were stored anyway.
        base = _base_or_none(data["base_config"])
        if base is None:
            return jsonify({
                "error": f"'{data['base_config']}' cannot be the structure of a perspective"
            }), 400
        new_pipeline = base.pipeline_name or "text_transformation"

    db = SessionLocal()
    _snapshot_version(db, p)  # capture PRIOR state before mutating

    # forked_from_preset / forked_from_prompt_id are provenance — not editable;
    # `pipeline` follows base_config and is not taken from the body.
    for f in (
        "base_config", "context_text",
        "task_instruction", "parameters", "is_published",
    ):
        if f in data:
            setattr(p, f, data[f])
    if new_pipeline is not None:
        p.base_config = str(data["base_config"]).strip()
        p.pipeline = new_pipeline
    if "name" in data:
        new_name, name_err = _resolve_name(
            data.get("name"), p.name, p.owner_id, except_id=p.id
        )
        if name_err:
            return name_err
        p.name = new_name
    conflict = _commit_or_conflict(db)
    if conflict:
        return conflict
    return jsonify({"prompt": p.to_dict()}), 200


@prompts_bp.route("/<int:pid>", methods=["DELETE"])
@require_auth
def delete_prompt(pid: int):
    """Drop one's own. PromptVersion rows and any palette entries cascade."""
    p = _owned_or_404(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    db = SessionLocal()
    db.delete(p)
    db.commit()
    return jsonify({"success": True}), 200


# ---------------------------------------------------------------------------
# fork flows (save-as a PRESET, or duplicate one's own)
# ---------------------------------------------------------------------------
@prompts_bp.route("/from-preset", methods=["POST"])
@require_auth
def fork_from_preset():
    """SAVE AS = FORK a PRESET into a new editable, owned perspective.

    Copies the preset's RESOLVED context/parameters/task into a new row. The
    preset JSON is read-only here and stays latent / always restorable.

    Body: {preset_name, name?, context_text?}
    """
    data = request.get_json(silent=True) or {}
    preset_name = (data.get("preset_name") or "").strip()
    if not preset_name:
        return jsonify({"error": "preset_name required"}), 400

    base = _base_or_none(preset_name)
    if base is None:
        return jsonify({
            "error": f"'{preset_name}' cannot be the structure of a perspective"
        }), 404

    # The caller may hand in the text as it stands on their surface — that is the
    # whole point of "keep this": what gets kept is what is written there now,
    # not what the preset says. Without it, the preset's own text is copied.
    context_text = data.get("context_text") or base.context
    payload = {
        "context_text": context_text,
        "pipeline": base.pipeline_name or "text_transformation",
        # The preset's own parameters are inherited FILTERED: they may carry
        # keys a kept perspective must not hold (an output cap above all), and
        # the person forking did not write them.
        "parameters": _clean_params(data.get("parameters") or base.parameters),
    }
    ok, err = _validate_prompt(payload)
    if not ok:
        return jsonify({"error": err}), 400

    name, name_err = _resolve_name(data.get("name"), preset_name, current_user().id)
    if name_err:
        return name_err

    db = SessionLocal()
    p = InterceptionPrompt(
        owner_id=current_user().id,
        name=name,
        # base_config == forked_from_preset initially (structural inheritance).
        base_config=preset_name,
        pipeline=payload["pipeline"],
        context_text=context_text,
        task_instruction=getattr(base, "task_instruction", None),
        parameters=payload["parameters"],
        is_published=bool(data.get("is_published", False)),
        forked_from_preset=preset_name,   # provenance: the latent Original
        forked_from_prompt_id=None,
    )
    db.add(p)
    db.commit()
    logger.info("[PROMPT-LIB] user #%s forked preset '%s' -> custom:%s",
                p.owner_id, preset_name, p.id)
    return jsonify({"prompt": p.to_dict()}), 201


@prompts_bp.route("/<int:pid>/fork", methods=["POST"])
@require_auth
def fork_prompt(pid: int):
    """Duplicate one's own into a new copy. Version history is NOT copied — the
    duplicate starts a fresh history."""
    src = _owned_or_404(pid)
    if src is None:
        return jsonify({"error": "not found"}), 404
    db = SessionLocal()
    data = request.get_json(silent=True) or {}
    name, name_err = _resolve_name(
        data.get("name"), f"{src.name} (copy)", current_user().id
    )
    if name_err:
        return name_err
    p = InterceptionPrompt(
        owner_id=current_user().id,
        name=name,
        base_config=src.base_config,
        pipeline=src.pipeline,
        context_text=src.context_text,
        task_instruction=src.task_instruction,
        parameters=dict(src.parameters or {}),
        is_published=False,
        forked_from_preset=src.forked_from_preset,  # preserve original provenance
        forked_from_prompt_id=src.id,
    )
    db.add(p)
    db.commit()
    logger.info("[PROMPT-LIB] user #%s duplicated custom:%s -> custom:%s",
                p.owner_id, src.id, p.id)
    return jsonify({"prompt": p.to_dict()}), 201


# ---------------------------------------------------------------------------
# version history + restore
# ---------------------------------------------------------------------------
@prompts_bp.route("/<int:pid>/versions", methods=["GET"])
@require_auth
def list_versions(pid: int):
    """Non-destructive history of one's own edits (newest first)."""
    p = _owned_or_404(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    rows = (
        SessionLocal()
        .query(PromptVersion)
        .filter(PromptVersion.prompt_id == pid)
        .order_by(PromptVersion.version_no.desc())
        .all()
    )
    return jsonify({"versions": [v.to_dict() for v in rows]}), 200


@prompts_bp.route("/<int:pid>/revert/<int:version_no>", methods=["POST"])
@require_auth
def revert_to_version(pid: int, version_no: int):
    """Restore an earlier own edit. Snapshots the CURRENT state first, so the
    restore is itself reversible."""
    p = _owned_or_404(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    db = SessionLocal()
    version = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.prompt_id == pid,
            PromptVersion.version_no == version_no,
        )
        .first()
    )
    if version is None:
        return jsonify({"error": "version not found"}), 404

    _snapshot_version(db, p)  # snapshot current before restoring
    p.name = version.name
    p.context_text = version.context_text
    p.task_instruction = version.task_instruction
    p.parameters = dict(version.parameters or {})
    db.commit()
    logger.info("[PROMPT-LIB] custom:%s reverted to own version %s", pid, version_no)
    return jsonify({"prompt": p.to_dict()}), 200


@prompts_bp.route("/<int:pid>/revert-to-preset", methods=["POST"])
@require_auth
def revert_to_preset(pid: int):
    """Restore the PRESET Original into a fork, discarding own edits.

    Re-copies the CURRENT preset content from the latent JSON after snapshotting
    the current state. Only valid for prompts forked from a preset. The preset
    file is read-only and never mutated.
    """
    p = _owned_or_404(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    if not p.forked_from_preset:
        return jsonify({"error": "prompt is not forked from a preset"}), 400

    base = _preset_resolved(p.forked_from_preset)
    if base is None:
        return jsonify({
            "error": f"preset '{p.forked_from_preset}' no longer exists"
        }), 404

    db = SessionLocal()
    _snapshot_version(db, p)  # snapshot own current state first
    p.base_config = p.forked_from_preset
    p.pipeline = base.pipeline_name or "text_transformation"
    p.context_text = base.context
    p.task_instruction = getattr(base, "task_instruction", None)
    p.parameters = dict(base.parameters or {})
    db.commit()
    logger.info("[PROMPT-LIB] custom:%s reverted to preset '%s'",
                pid, p.forked_from_preset)
    return jsonify({"prompt": p.to_dict()}), 200


# ---------------------------------------------------------------------------
# preview (dry run through the SAME safety chain)
# ---------------------------------------------------------------------------
@prompts_bp.route("/<int:pid>/preview", methods=["POST"])
@require_auth
def preview_prompt(pid: int):
    """Run an owned prompt against a sample input through the real Stage 2.

    Stage 1 runs over `sample_input` at the resolved level, exactly as it does
    at every other entry into Stage 2, and the run stops here if it blocks.
    Then execute_stage2_interception with that same safety_level, so the
    kids/youth SAFETY PREFIXES are prepended in
    instruction_selector.get_instruction() exactly as in production. Whoever
    wrote the perspective sees that safety still applies to it BEFORE it goes
    into a course palette — a kept prompt can never bypass safety.

    Body: {sample_input, safety_level, user_language}
    """
    p = _owned_or_404(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    raw_sample = data.get("sample_input")
    if raw_sample is not None and not isinstance(raw_sample, str):
        return jsonify({"error": "sample_input must be a string"}), 400
    sample = (raw_sample or "").strip()
    if not sample:
        return jsonify({"error": "sample_input required"}), 400
    if len(sample) > MAX_SAMPLE_LEN:
        return jsonify({"error": f"sample_input too long (>{MAX_SAMPLE_LEN})"}), 400

    # The level the session actually stands at — installation level, tightened by
    # the course. A dry run may TIGHTEN below it, exactly as a course may, and
    # may never loosen it: taking the level from the request body let a member of
    # a kids course preview at `open`.
    from my_app.services.safety_level_resolver import (
        resolve_safety_level, SAFETY_LEVELS_STRICTEST_FIRST,
    )
    session_level = resolve_safety_level()
    order = list(SAFETY_LEVELS_STRICTEST_FIRST)
    safety_level = data.get("safety_level", session_level)
    if safety_level not in order:
        return jsonify({"error": "invalid safety_level"}), 400
    if session_level not in order:          # cannot happen; fail closed if it does
        session_level = order[0]
    if order.index(safety_level) > order.index(session_level):
        logger.info(
            "[PROMPT-LIB] preview asked for %s, session stands at %s — using %s",
            safety_level, session_level, session_level,
        )
        safety_level = session_level

    # Imported here, not at module level: schema_pipeline_routes imports a large
    # part of the engine, and this blueprint is registered before it.
    from my_app.routes.schema_pipeline_routes import (
        init_schema_engine, execute_stage2_interception, llm_queue_semaphore,
        _stage1_check_texts, _stage2_refusal,
    )
    init_schema_engine()

    # THE ENTRY GATE, over the text the client sent. `execute_stage2_interception`
    # states in its own docstring that its input is "already safety-checked in
    # Stage 1", and every other way into it holds that: /pipeline/stage2 and
    # /pipeline/interception both run the gate at the request boundary. This one
    # did not. `sample_input` is free-form POST body from whoever is logged in —
    # the gate is `require_auth`, which on this platform is every participant —
    # and it went to a model with the Stage-2 safety PREFIX in front of it and
    # nothing checking the text itself.
    #
    # The prefix is not the check. It shapes what the interception is asked to
    # do; it does not look at what it is being asked to do it to.
    #
    # Before the semaphore below, not inside it: the gate takes a slot of the
    # same plant-wide queue for its own run, and holding two at once for one
    # request is what a queue of one would deadlock on.
    #
    # `user_language` is the fast filters' fallback for deciding the script of a
    # Latin-alphabet text; the platform's default is what the generation routes
    # pass when a client sends none.
    user_language = data.get("user_language") or "de"
    is_safe, error_message, checks_passed, blocked_on, _checked = _stage1_check_texts(
        [("sample_input", sample)], safety_level, user_language,
    )
    if not is_safe:
        logger.warning("[PROMPT-LIB] preview of custom:%s BLOCKED at stage 1 (%s)",
                       pid, blocked_on)
        return jsonify({
            "error": error_message or "Content blocked by safety check",
            "blocked_at_stage": 1,
            "safety_level": safety_level,
            "checks_passed": checks_passed,
        }), 403

    cfg = course_prompt_resolver.get_config(p.style_key, user=current_user())
    if cfg is None:
        return jsonify({
            "error": f"cannot resolve base config '{p.base_config or p.forked_from_preset}'"
        }), 400

    try:
        # The same queue every other Stage-2 entry point stands in. Without it a
        # dry run was the one way to reach the models unqueued.
        with llm_queue_semaphore:
            result = asyncio.run(execute_stage2_interception(
                cfg.name, sample, cfg, safety_level,
                # Originalsprachen-Verarbeitung: without it the preview renders
                # the context in the platform default and a chained perspective
                # comes back in English whatever the sample was written in.
                user_language=data.get("user_language") or "de",
            ))
    except Exception as e:                      # noqa: BLE001 — surfaced to the caller
        logger.error("[PROMPT-LIB] preview of custom:%s failed: %s", pid, e)
        return jsonify({"error": f"preview failed: {e}"}), 500

    output = getattr(result, "final_output", None)
    if output is None and isinstance(result, dict):
        output = result.get("final_output")

    # The refusal the safety prefix asks for is a block at stage 2, in the shape
    # of the stage-1 block above; until the second review of 2026-10-10 it went
    # back as the output, 200 (finding S-015 of the code review of 2026-10-10).
    refusal = _stage2_refusal(result) if not isinstance(result, dict) else None
    if refusal:
        logger.warning("[PROMPT-LIB] preview of custom:%s refused by the model", pid)
        return jsonify({
            "error": refusal,
            "blocked_at_stage": 2,
            "safety_level": safety_level,
            "checks_passed": checks_passed,
        }), 403

    _ = dataclasses  # kept: the resolver's replace() path is what produced cfg
    return jsonify({
        "style_key": p.style_key,
        "safety_level": safety_level,
        "output": output or "",
    }), 200
