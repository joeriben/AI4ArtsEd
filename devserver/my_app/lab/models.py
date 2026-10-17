"""
ORM models for the Lab User/Course system (CANONICAL v2).

v2 model:
  - CoursePromptBinding is GONE (replaced by CoursePaletteItem).
  - Course.allowed_base_configs is GONE (replaced by explicit opt-in palette).
  - InterceptionPrompt.forked_from_preset + forked_from_prompt_id (fork provenance).
  - PromptVersion (non-destructive history of an educator's OWN edits).
  - CoursePaletteItem (per-course curated palette of presets + custom forks).

Places: a course admits
devices, each through a place — a number and a code
(CourseMembership.place_number / code_hash / code_issued_at) — while its access
window is open (Course.access_until). The course key of BAUPLAN Entscheid 2
(Course.access_key_hash / access_key_expires_at) and the join code went with the
roster they served; lab/db.py drops their columns from an older file.

Preset interception styles (the JSON files in schemas/configs/interception/*.json)
are the Originale. They are NEVER mutated by any code path. "Editing a preset" is
done via SAVE AS = FORK into a course-owned InterceptionPrompt (forked_from_preset
set).

STYLE KEY FORMAT (identical backend<->frontend):
    "preset:<name>"      e.g. "preset:bauhaus"   -> a latent preset Original
    "custom:<prompt_id>" e.g. "custom:42"        -> a course-owned InterceptionPrompt
    A bare name with no prefix is treated as "preset:<name>" (backward compatibility).
"""
from __future__ import annotations

import datetime as _dt
import enum
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String,
    Text, JSON, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------------------------------------------------------------------
# style_key helpers — single source of truth for the "preset:" / "custom:" format
# ---------------------------------------------------------------------------
def make_preset_style_key(name: str) -> str:
    return f"preset:{name}"


def make_custom_style_key(prompt_id: int) -> str:
    return f"custom:{prompt_id}"


def parse_style_key(style_key: str) -> tuple[str, str]:
    """Return (source_type, value). A bare name is treated as a preset name.

    source_type is one of "preset" | "custom".
    For "preset" the value is the preset name; for "custom" it is the prompt id (str).
    """
    if not style_key:
        return "preset", ""
    if ":" in style_key:
        kind, value = style_key.split(":", 1)
        if kind in ("preset", "custom"):
            return kind, value
    # Backward compatibility: bare name == preset.
    return "preset", style_key


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Role(str, enum.Enum):
    admin = "admin"
    educator = "educator"
    participant = "participant"


class CourseRole(str, enum.Enum):
    owner = "owner"
    co_leader = "co_leader"


class MembershipStatus(str, enum.Enum):
    invited = "invited"
    active = "active"
    removed = "removed"


class DraftKind(str, enum.Enum):
    input = "input"
    interception = "interception"


class PaletteSourceType(str, enum.Enum):
    """A palette item points either at a latent PRESET Original or a course-owned
    CUSTOM fork/prompt. Mirrors the style_key prefixes exactly."""
    preset = "preset"
    custom = "custom"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    """One table for all roles (single-table, `role` discriminator).

    Educators are ADMIN-CREATED — there is no educator self-signup. Educators in
    turn create the places of their courses (`created_by`): the account of a
    place has the participant role and carries no email, no username and no
    display name: no personal data on the platform, for devices are not persons.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # email: only for educator/admin (adults). Unique where present.
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    # username: an optional login name for educator/admin; a place has none.
    username: Mapped[Optional[str]] = mapped_column(String(120), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.participant)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    locale: Mapped[str] = mapped_column(String(8), default="de")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    led_courses = relationship("CourseEducator", back_populates="user", cascade="all, delete-orphan")
    memberships = relationship("CourseMembership", back_populates="user", cascade="all, delete-orphan")
    prompts = relationship("InterceptionPrompt", back_populates="owner", cascade="all, delete-orphan")
    works = relationship("Work", back_populates="owner", cascade="all, delete-orphan")
    drafts = relationship("PromptDraft", back_populates="owner", cascade="all, delete-orphan")

    @property
    def login_identifier(self) -> str:
        return self.email or self.username or f"user#{self.id}"

    def to_public(self) -> dict:
        """Safe representation for the frontend (NO password hash, minimal PII)."""
        return {
            "id": self.id,
            "role": self.role.value,
            "display_name": self.display_name,
            "identifier": self.login_identifier,
            "locale": self.locale,
            "is_active": self.is_active,
        }

    def to_dict(self) -> dict:
        """Admin-facing representation (NO password hash). Used by /api/admin/users."""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "role": self.role.value,
            "display_name": self.display_name,
            "locale": self.locale,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Course (Kurs)
# ---------------------------------------------------------------------------
class Course(Base):
    """A course. v2 REMOVES `allowed_base_configs`: which styles appear is now
    expressed PURELY by the explicit, opt-in CoursePaletteItem rows.

    A course runs EXCLUSIVELY (BAUPLAN Entscheid 2): a device enters it with the
    code of one of its places (CourseMembership), and only while its access
    window is open — until `access_until`; unset is closed (lab/place_codes.py).
    """
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    safety_level: Mapped[str] = mapped_column(String(16), default="youth")  # kids|youth|open
    # Privacy toggle (see design README §8): may educators view participants' works?
    educator_can_view_participant_works: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # Until when the codes of the course's places enter it (2026-09-23). After
    # created_at: an older file receives it by ALTER TABLE … ADD COLUMN, which
    # appends, and a fresh file has the same order.
    access_until: Mapped[Optional[_dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    educators = relationship("CourseEducator", back_populates="course", cascade="all, delete-orphan")
    members = relationship("CourseMembership", back_populates="course", cascade="all, delete-orphan")
    palette = relationship(
        "CoursePaletteItem",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CoursePaletteItem.position",
    )

    def to_dict(self) -> dict:
        from .place_codes import iso_utc  # place_codes imports this module
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "safety_level": self.safety_level,
            "educator_can_view_participant_works": self.educator_can_view_participant_works,
            "archived": self.archived,
            "access_until": iso_utc(self.access_until),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CourseEducator(Base):
    """M:N — a course is owned/led by one OR MORE Kursleitende."""
    __tablename__ = "course_educators"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_course_educator"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_in_course: Mapped[CourseRole] = mapped_column(Enum(CourseRole), default=CourseRole.owner)

    course = relationship("Course", back_populates="educators")
    user = relationship("User", back_populates="led_courses")


class CourseMembership(Base):
    """M:N — the accounts assigned to a course.

    Since 2026-09-23 a participant's membership is a PLACE: `place_number` is
    its number in the course, and the code that enters it is kept as
    `code_hash` alone (SHA-256 of the normalised code, lab/place_codes.py).
    `code_issued_at` is when the current code was made; a session remembers
    it, so a replaced code ends the sessions that entered with the old one.
    What a place keeps (its perspectives) is owned by the place's account.
    """
    __tablename__ = "course_memberships"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_member"),
        # An index and not a table constraint: an older file receives it as
        # CREATE UNIQUE INDEX (lab/db.py `_ADDED_INDEXES`), and a fresh file
        # carries the same form. NULLs never collide, so a membership without
        # a place needs no number.
        Index("uq_course_place_number", "course_id", "place_number", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[MembershipStatus] = mapped_column(Enum(MembershipStatus), default=MembershipStatus.active)
    joined_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    place_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    code_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    code_issued_at: Mapped[Optional[_dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    course = relationship("Course", back_populates="members")
    user = relationship("User", back_populates="memberships")


# ---------------------------------------------------------------------------
# Interception prompts (educator-authored AND forks) + version history
# ---------------------------------------------------------------------------
class InterceptionPrompt(Base):
    """An educator-owned interception prompt: either authored from scratch OR a
    FORK of a preset / another custom prompt.

    Mirrors the fields of a standard interception config
    (schemas/configs/interception/<name>.json): `context_text` == config `context`.

    Forking semantics (decision 2):
      - SAVE AS from a preset copies the preset content into a NEW prompt with
        `forked_from_preset` == the preset name; `base_config` == that preset name
        initially (so the resolver inherits pipeline/chunks from it).
      - "Restore original" (revert-to-preset) re-copies the current preset content
        into the fork, discarding leader edits. The preset file is never touched.
      - PromptVersion snapshots give non-destructive undo of the leader's OWN edits.
    """
    __tablename__ = "interception_prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Structural base for pipeline/chunks inheritance (a preset config name) or null.
    base_config: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    pipeline: Mapped[str] = mapped_column(String(80), default="text_transformation")
    # THE prompt text. str OR i18n dict {de,en,...}; resolve_context_language() handles both.
    context_text: Mapped[object] = mapped_column(JSON, nullable=False)
    # Optional TASK_INSTRUCTION override (else the instruction_type default applies).
    task_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    # Provenance (decision 2): which latent preset Original this was SAVED AS from.
    forked_from_preset: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Optional: which custom prompt this was duplicated from (self-FK).
    forked_from_prompt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("interception_prompts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner = relationship("User", back_populates="prompts")
    forked_from = relationship(
        "InterceptionPrompt",
        remote_side="InterceptionPrompt.id",
        backref="forks",
    )
    versions = relationship(
        "PromptVersion",
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="PromptVersion.version_no",
    )
    palette_items = relationship(
        "CoursePaletteItem",
        back_populates="prompt",
        cascade="all, delete-orphan",
    )

    @property
    def style_key(self) -> str:
        return make_custom_style_key(self.id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "name": self.name,
            "base_config": self.base_config,
            "pipeline": self.pipeline,
            "context_text": self.context_text,
            "task_instruction": self.task_instruction,
            "parameters": self.parameters or {},
            "is_published": self.is_published,
            "forked_from_preset": self.forked_from_preset,
            "forked_from_prompt_id": self.forked_from_prompt_id,
            "style_key": self.style_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def snapshot_version(self, version_no: int, created_by: Optional[int]) -> "PromptVersion":
        """Build a PromptVersion capturing the CURRENT (about-to-be-overwritten)
        state. The route layer calls this BEFORE applying an edit (PUT), so that
        revert/:versionNo can restore an earlier OWN edit non-destructively."""
        return PromptVersion(
            prompt_id=self.id,
            version_no=version_no,
            name=self.name,
            context_text=self.context_text,
            task_instruction=self.task_instruction,
            parameters=self.parameters or {},
            created_by=created_by,
        )


class PromptVersion(Base):
    """Immutable snapshot of a PRIOR state of an InterceptionPrompt.

    A snapshot is written on every UPDATE (PUT) of the prompt — capturing the
    state that is about to be replaced — so the owner can revert to an earlier
    OWN edit (POST .../revert/:versionNo). This is independent of revert-to-preset,
    which restores the latent preset Original instead.
    """
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version_no", name="uq_prompt_version_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey("interception_prompts.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    context_text: Mapped[object] = mapped_column(JSON, nullable=False)
    task_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    prompt = relationship("InterceptionPrompt", back_populates="versions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prompt_id": self.prompt_id,
            "version_no": self.version_no,
            "name": self.name,
            "context_text": self.context_text,
            "task_instruction": self.task_instruction,
            "parameters": self.parameters or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


# ---------------------------------------------------------------------------
# Per-course palette (opt-in) — REPLACES CoursePromptBinding
# ---------------------------------------------------------------------------
class CoursePaletteItem(Base):
    """One curated entry in a course's palette (decision 2: maximum leader
    sovereignty). The leader explicitly opts each item in — NOT all-or-nothing.

    An item points either at a latent PRESET Original (`source_type == preset`,
    `preset_name` set, `prompt_id` null) or at a course-owned CUSTOM prompt/fork
    (`source_type == custom`, `prompt_id` set, `preset_name` null).

    "Overriding a preset" is expressed PURELY by palette composition: include the
    fork (labelled e.g. "Bauhaus") and omit the preset item. There is NO
    overrides_base_config flag anymore.

    The addressable style key is derived (see `style_key`) and matches the
    backend<->frontend format exactly.
    """
    __tablename__ = "course_palette_items"
    __table_args__ = (
        # Invariant: preset => preset_name set & prompt_id null;
        #            custom => prompt_id set & preset_name null.
        CheckConstraint(
            "(source_type = 'preset' AND preset_name IS NOT NULL AND prompt_id IS NULL) "
            "OR (source_type = 'custom' AND prompt_id IS NOT NULL AND preset_name IS NULL)",
            name="ck_palette_source_invariant",
        ),
        # No duplicate preset entries in the same course.
        UniqueConstraint("course_id", "preset_name", name="uq_palette_course_preset"),
        # No duplicate custom-prompt entries in the same course.
        UniqueConstraint("course_id", "prompt_id", name="uq_palette_course_prompt"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[PaletteSourceType] = mapped_column(Enum(PaletteSourceType), nullable=False)
    # Exactly one of these is set per the CHECK invariant above.
    preset_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    prompt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("interception_prompts.id", ondelete="CASCADE"), nullable=True
    )
    # Optional display override (e.g. show a fork as "Bauhaus").
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    course = relationship("Course", back_populates="palette")
    prompt = relationship("InterceptionPrompt", back_populates="palette_items")

    @property
    def style_key(self) -> str:
        """Canonical addressable key — identical to the frontend format."""
        if self.source_type == PaletteSourceType.preset:
            return make_preset_style_key(self.preset_name or "")
        return make_custom_style_key(self.prompt_id or 0)

    def to_dict(self) -> dict:
        st = self.source_type.value if isinstance(self.source_type, PaletteSourceType) else self.source_type
        out = {
            "id": self.id,
            "course_id": self.course_id,
            "source_type": st,
            "preset_name": self.preset_name,
            "prompt_id": self.prompt_id,
            "label": self.label,
            "position": self.position,
            "enabled": self.enabled,
            "style_key": self.style_key,
        }
        # Surface fork provenance for the palette UI when this is a custom item.
        if self.source_type == PaletteSourceType.custom and self.prompt is not None:
            out["forked_from_preset"] = self.prompt.forked_from_preset
        return out


# ---------------------------------------------------------------------------
# Personal area: works + prompt drafts (unchanged from v1)
# ---------------------------------------------------------------------------
class Work(Base):
    """Metadata record over a generation. The media stay in exports/json/...;
    `run_id` is the join key to the existing LivePipelineRecorder output.

    `course_id` is used by the cascade delete (decision 4): works whose
    course_id == the deleted course are removed.
    """
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    run_id: Mapped[str] = mapped_column(String(120), index=True)
    config_name: Mapped[str] = mapped_column(String(160), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    original_prompt: Mapped[str] = mapped_column(Text, default="")
    transformed_prompt: Mapped[str] = mapped_column(Text, default="")
    safety_level: Mapped[str] = mapped_column(String(16), default="youth")
    media_type: Mapped[str] = mapped_column(String(16), default="image")
    thumb_path: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner = relationship("User", back_populates="works")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "course_id": self.course_id, "run_id": self.run_id,
            "config_name": self.config_name, "title": self.title,
            "original_prompt": self.original_prompt, "transformed_prompt": self.transformed_prompt,
            "safety_level": self.safety_level, "media_type": self.media_type,
            "thumb_path": self.thumb_path, "is_draft": self.is_draft, "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PromptDraft(Base):
    """A prompt the user saved for reuse (input prompt or interception draft)."""
    __tablename__ = "prompt_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[DraftKind] = mapped_column(Enum(DraftKind), default=DraftKind.input)
    title: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner = relationship("User", back_populates="drafts")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "course_id": self.course_id, "kind": self.kind.value,
            "title": self.title, "text": self.text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# LoRA register — which adapter files this platform offers, and to whom
# ---------------------------------------------------------------------------
class LoraVisibility(str, enum.Enum):
    """Who is offered an adapter on a surface.

    `platform`: every session. `course`: the sessions of `course_id` alone.
    `none`: registered and released nowhere — the state a training leaves an
    adapter in when no course was active at the training place, until somebody
    releases it in the Settings. A personal training (a face, a family) must
    never reach a workshop by default (issue #70), so nothing is released by
    being trained.
    """
    platform = "platform"
    course = "course"
    none = "none"


class LoraAdapter(Base):
    """One adapter file the platform offers: the register of issue #70.

    The file name decided membership until 2026-09-21 — `sd35_*` in the LoRA
    folder was "trained here", everything else was not — and a pattern cannot
    say who may see an adapter or what to write in a prompt to call it. This
    row says both. WHICH MODEL carries it is no field here (2026-09-22): the
    adapter file says what it was trained over and
    `services/lora_base.py` reads it, so nobody can tick the wrong one.
    What is NOT here is not offered:
    the accelerators of the video pipelines lie in the same folder and never
    appear, and every epoch file of a project stays on disk while the register
    names the ONE file that stands for the adapter.
    """
    __tablename__ = "lora_adapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The file in LORA_OUTPUT_DIR, as the workflow loads it. One row per file.
    file: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # What a surface calls it: the project name at training time, editable.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # The word the captions were written under; it goes in front of the prompt.
    trigger: Mapped[str] = mapped_column(Text, default="")
    # The kind of thing it makes, as the chooser sorts by it (2026-09-22): a
    # short key, empty where nobody has said. An adapter without one hangs in
    # the chooser under its release instead of under a kind.
    category: Mapped[str] = mapped_column(String(40), default="")
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    visibility: Mapped[LoraVisibility] = mapped_column(
        Enum(LoraVisibility), default=LoraVisibility.none
    )
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    owner = relationship("User")
    course = relationship("Course")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file": self.file,
            "name": self.name,
            "trigger": self.trigger or "",
            "category": self.category or "",
            "owner_id": self.owner_id,
            "course_id": self.course_id,
            "visibility": self.visibility.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
