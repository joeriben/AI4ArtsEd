"""
Course-aware resolution of the Stage-2 interception config (P3).

This lives in the DevServer (orchestrator) layer — the PipelineExecutor stays a
"dumb engine" and keeps receiving a ready-made ResolvedConfig via
`config_override`.

A style is addressed by a STYLE KEY string, identical backend<->frontend:

    "preset:<name>"      e.g. "preset:bauhaus"  → an immutable PRESET config
    "custom:<prompt_id>" e.g. "custom:42"       → a kept InterceptionPrompt
    "<name>"             (no prefix)            → treated as "preset:<name>"

PRESET JSON files (schemas/configs/interception/*.json) are the Originals and are
NEVER mutated by any code path. Editing a preset = SAVE AS = FORK into a new
InterceptionPrompt row (forked_from_preset set); the preset stays latent and is
always restorable.

WHO OWNS WHAT: everyone who is logged in keeps their own — a
participant's own perspective belongs to them exactly as an educator's does.
Ownership is `InterceptionPrompt.owner_id`; the resolver lets an owner resolve
their own prompt anywhere, with or without an active course. What a course SHOWS
to its members stays the leader's decision (the CoursePaletteItem palette).

Safety is NOT affected: kids/youth prefixes are prepended later in
instruction_selector.get_instruction(), regardless of where `context` came from —
so a kept prompt CANNOT bypass safety.
"""
from __future__ import annotations

import dataclasses
import logging
import os
from typing import Optional

from my_app.lab.db import SessionLocal
from my_app.lab.models import (
    User,
    Role,
    CoursePaletteItem,
    InterceptionPrompt,
    PaletteSourceType,
    # style_key helpers — single source of truth (no duplicate impls):
    parse_style_key,
    make_preset_style_key,
    make_custom_style_key,
)

logger = logging.getLogger(__name__)

# Pipelines a kept prompt / fork is allowed to use (validated in the routes).
ALLOWED_PIPELINES = {"text_transformation", "text_transformation_recursive"}

# Meta tag identifying a PRESET interception style. This is the ONLY correct way
# to enumerate preset styles — there is no list_interception_configs().
INTERCEPTION_STAGE = "interception"

# Perspectives the chooser does not put on the surface. Mirrored in
# InterceptionPresetOverlay.vue (EXCLUDED_IDS); a name may only ever be in both
# or in neither, or a course could offer something no member can see.
NOT_OFFERED = {"tonejs_composer"}


def is_offerable_perspective(name: str, resolved) -> bool:
    """Whether `name` may be offered as a perspective at all.

    Three conditions, and existence is deliberately not one of the three on its
    own: the config_loader resolves EVERY stage in one flat namespace, so a bare
    existence check accepted `sd35_large` or `surrealizer` as the structure of a
    kept perspective — and Stage 2 would then execute an image pipeline with
    caller-written parameters. What may be offered is what the perspective
    chooser can actually show: an interception-stage config running one of the
    two text pipelines, minus the names the chooser hides.

    This is the ONE place that decides it. The base_config gate, the course
    palette and the preset listing all ask here.
    """
    if resolved is None:
        return False
    if (resolved.meta or {}).get("stage") != INTERCEPTION_STAGE:
        return False
    if (resolved.pipeline_name or "") not in ALLOWED_PIPELINES:
        return False
    return name not in NOT_OFFERED


def course_prompts_enabled() -> bool:
    """Whether the call sites resolve through this module.

    Default ON — the whole point of the feature is that keeping a perspective is
    reachable without setting an environment variable. `AI4ARTSED_COURSE_PROMPTS=0`
    restores the pre-P3 path exactly: `config_loader.get_config(schema_name)`.

    Note that even with it ON a preset key takes the identical path and returns
    the identical object (see `get_config`), so the switch is a kill switch for
    the custom branch, not a behavioural fork for presets.
    """
    return os.environ.get("AI4ARTSED_COURSE_PROMPTS", "1") != "0"


class CoursePromptResolver:
    def __init__(self, config_loader=None):
        # Injected for testability; defaults to the global singleton at runtime.
        self._config_loader = config_loader

    @property
    def config_loader(self):
        if self._config_loader is None:
            from schemas.engine.config_loader import config_loader as _cl
            self._config_loader = _cl
        return self._config_loader

    # -- public API ---------------------------------------------------------
    def get_config(self, style_key: str, course_id: Optional[int] = None,
                   user: Optional[User] = None):
        """Return a ResolvedConfig for `style_key`, honouring the active course.

        - "preset:<name>" / bare → config_loader.get_config(name), unchanged and
          returning the very same object today's call site would have got.
        - "custom:<id>"          → the kept InterceptionPrompt, after authz:
          its owner always; anyone else only while it sits enabled AND published
          in the palette of the course they are in.
        """
        source_type, value = parse_style_key(style_key)

        if source_type == "preset":
            resolved = self.config_loader.get_config(value)
            if resolved is None:
                logger.warning("[COURSE-PROMPT] Unknown preset '%s'", value)
            return resolved

        # source_type == "custom"
        try:
            prompt_id = int(value)
        except (TypeError, ValueError):
            logger.warning("[COURSE-PROMPT] Malformed custom style_key '%s'", style_key)
            return None

        db = SessionLocal()
        prompt = db.get(InterceptionPrompt, prompt_id)
        if prompt is None:
            logger.warning("[COURSE-PROMPT] custom:%s not found", prompt_id)
            return None

        if self._is_owner(prompt, user):
            # Your own perspective is yours to run, published or not, course or
            # no course. This is what "wer angemeldet ist behaelt sein eigenes"
            # means at the resolver.
            return self._build_from_prompt(prompt)

        # Somebody else's prompt is only reachable through a course palette, by
        # a member or a leader of that course, and only while the owner has
        # published it. A session its place no longer admits keeps its course
        # for the safety level alone (auth_service._check_place_session).
        if not course_id:
            logger.warning(
                "[COURSE-PROMPT] custom:%s requested without course context", prompt_id
            )
            return None
        from my_app.lab.auth_service import has_course_access
        if user is None or not has_course_access(user, course_id):
            logger.warning(
                "[COURSE-PROMPT] custom:%s requested outside a session of course %s (denied)",
                prompt_id, course_id,
            )
            return None
        if not self._custom_in_palette(course_id, prompt_id):
            logger.warning(
                "[COURSE-PROMPT] custom:%s not in palette of course %s (denied)",
                prompt_id, course_id,
            )
            return None
        if not prompt.is_published:
            logger.warning("[COURSE-PROMPT] custom:%s not published (denied)", prompt_id)
            return None

        return self._build_from_prompt(prompt)

    def list_preset_styles(self) -> list[dict]:
        """All immutable PRESET interception styles, addressable as preset:<name>."""
        out: list[dict] = []
        for name in self.config_loader.list_configs():
            resolved = self.config_loader.get_config(name)
            if not resolved:
                continue
            if not is_offerable_perspective(name, resolved):
                continue
            out.append({
                "style_key": make_preset_style_key(name),
                "name": name,
                "display_name": resolved.display_name,
                "source_type": "preset",
            })
        return out

    def list_course_palette(self, course_id: Optional[int]) -> list[dict]:
        """The curated palette of a course: its enabled CoursePaletteItem rows.

        With no course_id → empty (the caller falls back to list_preset_styles()
        for the presets-only case).
        """
        if not course_id:
            return []

        db = SessionLocal()
        items = (
            db.query(CoursePaletteItem)
            .filter(
                CoursePaletteItem.course_id == course_id,
                CoursePaletteItem.enabled.is_(True),
            )
            .order_by(CoursePaletteItem.position.asc())
            .all()
        )

        out: list[dict] = []
        for item in items:
            if _source_is_preset(item):
                name = item.preset_name
                resolved = self.config_loader.get_config(name) if name else None
                out.append({
                    "style_key": make_preset_style_key(name or ""),
                    "label": item.label or name,
                    "source_type": "preset",
                    "display_name": resolved.display_name if resolved else None,
                })
            else:  # custom
                prompt = db.get(InterceptionPrompt, item.prompt_id) if item.prompt_id else None
                # Skip dangling OR unpublished customs from the members' palette
                # (defence in depth: the palette write already requires published,
                # but a prompt can be unpublished again afterwards).
                if prompt is None or not prompt.is_published:
                    continue
                out.append({
                    "style_key": make_custom_style_key(prompt.id),
                    "label": item.label or prompt.name,
                    "source_type": "custom",
                    "forked_from_preset": prompt.forked_from_preset,
                })
        return out

    # -- internals ----------------------------------------------------------
    def _custom_in_palette(self, course_id: int, prompt_id: int) -> bool:
        """True if this prompt is included (enabled) in the course palette."""
        db = SessionLocal()
        return (
            db.query(CoursePaletteItem)
            .filter(
                CoursePaletteItem.course_id == course_id,
                CoursePaletteItem.prompt_id == prompt_id,
                CoursePaletteItem.enabled.is_(True),
            )
            .first()
            is not None
        )

    def _is_owner(self, prompt: InterceptionPrompt, user: Optional[User]) -> bool:
        """Whether `user` owns this prompt. Admin always passes."""
        if user is None:
            return False
        role = getattr(getattr(user, "role", None), "value", getattr(user, "role", None))
        if role == Role.admin.value:
            return True
        return prompt.owner_id == user.id

    def _build_from_prompt(self, prompt: InterceptionPrompt):
        """Build a ResolvedConfig from a kept InterceptionPrompt, inheriting
        pipeline/chunks from its structural base preset and overriding only
        context/parameters/task_instruction.
        """
        # The structural base is the preset it forks from, or an explicit
        # base_config (for prompts written from scratch). For a fresh fork
        # base_config == forked_from_preset.
        base_name = prompt.base_config or prompt.forked_from_preset
        base = self.config_loader.get_config(base_name) if base_name else None

        if base is None:
            logger.warning(
                "[COURSE-PROMPT] No base config '%s' for custom:%s; cannot resolve",
                base_name, prompt.id,
            )
            return None

        merged_params = {**(base.parameters or {}), **(prompt.parameters or {})}

        # ResolvedConfig is a plain (non-slots) dataclass → replace() is safe and
        # leaves the loader's cached object untouched.
        resolved = dataclasses.replace(
            base,
            name=make_custom_style_key(prompt.id),
            context=prompt.context_text,   # str OR {de,en,...}; resolve_context_language handles both
            parameters=merged_params,
        )

        # chunk_builder._get_task_instruction() reads this via getattr(...).
        if prompt.task_instruction:
            setattr(resolved, "task_instruction", prompt.task_instruction)

        logger.info(
            "[COURSE-PROMPT] Resolved custom:%s (base preset '%s')",
            prompt.id, base_name,
        )
        return resolved


def _source_is_preset(item: CoursePaletteItem) -> bool:
    """The Enum column comes back as PaletteSourceType, but a row built by hand
    (tests, raw SQL) can carry the plain string. Read both."""
    st = item.source_type
    if isinstance(st, PaletteSourceType):
        return st == PaletteSourceType.preset
    return st == PaletteSourceType.preset.value


# Module-level singleton, mirroring the existing `config_loader` / `pipeline_executor`.
course_prompt_resolver = CoursePromptResolver()
