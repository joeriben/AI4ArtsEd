"""
LivePipelineRecorder - Stateful media recording system

Writes files immediately as entities appear, maintains state for frontend queries,
and self-describes expected outputs.

Replaces (both removed since):
- execution_history/tracker.py (ExecutionTracker)
- my_app/services/media_storage.py (MediaStorage)

Migration Status:
- Added download capabilities from MediaStorage (add_media_from_comfyui, add_media_from_url)
- Added utility methods (_detect_format_from_data, _get_image_dimensions)
- Now has complete media handling - no longer depends on MediaStorage for downloads
"""

import json
import logging
import os
import requests
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

logger = logging.getLogger(__name__)

# Held while a metadata.json is written and moved into place. The server is
# threaded (waitress): two saves of one run would otherwise race, and the earlier
# state could land last and replace the record the run ended with. Module-wide
# rather than per recorder, because load_recorder builds its recorders without
# __init__; a save takes milliseconds, so runs hardly wait on each other.
_metadata_save_lock = threading.Lock()


# ---------------------------------------------------------------------------
# The safety verdict, as a property of the thing it judges
# ---------------------------------------------------------------------------
#
# The verdict used to be recorded next to the picture instead of on it:
# save_error() writes an entity of type "error" carrying `stage` and
# `error_type`, and nothing that says WHICH output it condemns. Delivery reads
# `output_<kind>` entities by index and never looked at the error entities at
# all, so a blocked picture stayed in final/ and every route handed it out.
#
# The entities list is the platform's inventory — a file in final/ that no
# entity names is invisible everywhere (ARCHITECTURE PART 18). So the verdict
# belongs in that inventory, on the entity, where every reader already looks.

SAFETY_VERDICT_KEY = "safety"

# Levels at which a generated picture is held against a content check before it
# is shown, and at which delivery hands a picture out only with a pass that
# answers for the level of whoever asks. Above them nothing is withheld here:
# adult checks no pictures, research nothing at all. Kept here
# because the delivery side has to answer without importing routes.
IMAGE_CHECKED_LEVELS = ("kids", "youth")

# Code a language model wrote, which the browser runs: a p5.js or Tone.js
# sketch, Sonic Pi. The check at the result writes its verdict onto the entity
# (safety_gate.check_result_code), and delivery reads it as it reads a
# picture's. Code is also checked at adult, where no picture is, so a sketch
# refused at adult is not handed out there either.
CODE_KINDS = ("p5", "tonejs", "sonicpi")

# Media kinds for which a verdict is recorded HERE: pictures, videos and code.
# A video is checked as a whole at the result (safety_gate.check_result_video)
# and goes out by its verdict as a picture does. Sound has no output check
# anywhere on the platform — a missing verdict on it says nothing was ever
# asked, and refusing it would hide work over a check that does not exist.
VERDICT_BEARING_KINDS = ("image", "video") + CODE_KINDS

# Pictures MADE OF the pictures above: the strip a run lays out when it
# produced several images, and the before/after pair. They carry no content of
# their own — every pixel in them comes from an `output_image` that the check
# already judged — so they are as clear as the least clear of those, and they
# need no model call. Asked lazily, from the run's own record, so it makes no
# difference whether the strip is written before or after the check runs.
DERIVED_IMAGE_KINDS = ("image_composite", "image_comparison")

# Pictures a run shows on its way to the result: the parts a Latent Lab
# instrument keeps (the frames of a denoising run). They are held back until
# the run's finished picture is cleared and travel with it (decided with the
# structure of 2026-10-29); a verdict of their own would cost a call per frame.
# A part is held whatever format it names: the format is the sender's word, and
# every part an instrument sends today is a picture.
INTERMEDIATE_IMAGE_KINDS = ("latent_lab_step",)

# Media the check at the result reads through a picture of them: a 3D model,
# which its run renders as a preview and stores as an `output_image`. The
# preview is checked like any picture, and the model goes out as clear as the
# run's pictures. A 3D run without a preview has nothing to clear it with.
PREVIEWED_KINDS = ("3d",)

# A post-production piece (post_production_service): a still or a film laid
# under a sound. It is made of other runs' pieces and carries no verdict of its
# own, so it is as clear as the pieces its record names (`composed_from`).
COMPOSITION_KIND = "composition"

# Whether a run's generation took a picture in: image to image, several images,
# image to video. A picture such a run makes is made from the one it took in,
# and goes where that one may go: an upload stays on this server, and so does
# what is made from it. True or False where the run said it
# (LivePipelineRecorder.record_input_image); a run that does not say counts as
# one whose origin is unknown (media_ref.may_leave_server).
INPUT_IMAGE_KEY = "had_input_image"


class SafetyRefusal(Exception):
    """Raised where a recorded output may not be handed out.

    `field` says what was refused, for the block message: "code" for code a
    language model wrote, "video" for a video, "image" for everything else a
    door refuses.
    """

    def __init__(self, reason: str, run_id: str = "", filename: str = "",
                 field: str = "image"):
        self.reason = reason
        self.run_id = run_id
        self.filename = filename
        self.field = field
        super().__init__(
            f"run {run_id or '?'}: {filename or 'entity'} is {reason}"
        )


def public_entity(entity: dict) -> dict:
    """An entity as it may leave the server, with the verdict cut back.

    A verdict carries `reason` and `description`: the first is the German
    sentence a model wrote about why the picture is withheld, the second is that
    model's account of what is IN the picture. Handing those out is publishing
    in prose what the refusal withheld as bytes — so what travels is whether it
    was cleared, and the wording a surface shows is its own.

    Applied wherever a run's entities go out as JSON. There are several such
    places (the run's own listing, the favourites restore, the pipeline status,
    the session detail), and they cut it back HERE rather than each in its own
    words.
    """
    if not isinstance(entity, dict):
        return entity
    meta = entity.get("metadata")
    if not isinstance(meta, dict) or not isinstance(meta.get(SAFETY_VERDICT_KEY), dict):
        return entity
    trimmed = dict(entity)
    trimmed["metadata"] = dict(meta)
    trimmed["metadata"][SAFETY_VERDICT_KEY] = {
        "safe": meta[SAFETY_VERDICT_KEY].get("safe")
    }
    return trimmed


def _kind_of(entity_type) -> str:
    """The kind behind `output_`.

    Runs from before the `output_` prefix recorded the bare kind, and the
    platform's selection rule still picks those up (media_ref, legacy branch).
    Reading only the prefixed form would let exactly those through unasked.
    """
    etype = str(entity_type or "")
    return etype[len("output_"):] if etype.startswith("output_") else etype


def _sources_cleared(run_metadata: dict, level) -> tuple:
    """Whether every picture of the run is cleared for `level`: what a picture
    made of them, or shown on the way to them, needs, and what a 3D model
    needs whose preview is one of them.

    Over the RUN rather than over the entity's own `source_files`, which is the
    stricter of the two readings: a strip is written from the pictures of its
    own run, so the two sets are the same today, and where they ever differ this
    one refuses more, never less.
    """
    sources = 0
    for entity in run_metadata.get("entities", []):
        if entity.get("type") != "output_image":
            continue
        sources += 1
        cleared, reason = entity_cleared_for_delivery(entity, run_metadata, level)
        if not cleared:
            return False, reason
    if not sources:
        # A picture made of pictures, a part on the way to one, or a 3D model
        # without its preview, in a run holding none. Nothing to derive a
        # verdict from, and an empty loop must not read as agreement.
        return False, "unchecked"
    return True, ""


def _composition_cleared(entity: dict, level) -> tuple:
    """Whether every piece a composition was made of is cleared for `level`.

    Its record names them (`composed_from`: role, run, entity type), and each is
    asked where it lies, the way `post_production_service._resolve_ref` took it:
    the first entity of that type in its run. A composition that names no
    piece, or a piece that is gone, has nothing to derive a verdict from. No
    composition is made of another one, so a piece of that kind is refused
    rather than followed.
    """
    import config

    pieces = (entity.get("metadata") or {}).get("composed_from")
    if not isinstance(pieces, list) or not pieces:
        return False, "unchecked"
    for piece in pieces:
        if not isinstance(piece, dict):
            return False, "unchecked"
        run_id = str(piece.get("run_id") or "")
        etype = str(piece.get("type") or "")
        if not run_id or not etype or _kind_of(etype) == COMPOSITION_KIND:
            return False, "unchecked"
        source = load_recorder(run_id, base_path=Path(config.JSON_STORAGE_DIR))
        if source is None:
            return False, "unchecked"
        found = next((e for e in source.metadata.get("entities", [])
                      if e.get("type") == etype), None)
        if found is None:
            return False, "unchecked"
        cleared, reason = entity_cleared_for_delivery(found, source.metadata, level)
        if not cleared:
            return False, reason
    return True, ""


def refused_field(entity: dict) -> str:
    """What a refused entity is called in the block message: code, a video, or
    a picture. A 3D model is refused by its preview and called a picture."""
    kind = _kind_of(entity.get("type"))
    if kind in CODE_KINDS:
        return "code"
    return "video" if kind == "video" else "image"


def entity_verdict(safe: bool, reason: str = "", description: str = "",
                   level: Optional[str] = None) -> dict:
    """A content-check verdict in the form an entity carries it.

    It stands under SAFETY_VERDICT_KEY in the entity's metadata, where delivery
    reads it (safety_gate.entity_cleared_for). Every recorder writes this one
    form. A verdict without a level counts at the level of its run.
    """
    verdict = {
        "safe": bool(safe),
        "reason": reason or "",
        "description": description or "",
        "checked_at": datetime.now().isoformat(),
    }
    if level:
        verdict["level"] = level
    return verdict


def entity_cleared_for_delivery(entity: dict, run_metadata: dict, level) -> tuple:
    """
    May this entity be handed to whoever asks at `level`?

    Returns (cleared: bool, reason: str). The reason is empty when cleared and
    carries a short machine-readable word otherwise ('blocked', 'unchecked').

    `level` is the level of whoever asks, resolved by the view that serves them
    — never the level the run was made at. At kids and youth a picture goes out
    only with a pass that answers for that level: a pass counts for its own
    level and every looser one, and a verdict written without a level counts at
    the level of its run (safety_gate.entity_cleared_for). A picture still being
    checked has no verdict yet and is refused until it has one, and so is a
    picture of a run recorded before verdicts were kept. Delivery asks no model:
    browsing a gallery costs nothing.

    'blocked' says that a check refused the picture at this level or a looser
    one. A refusal at a stricter level says nothing about this one, and there
    the picture is 'unchecked'.

    A video goes by the same rule as a picture, by the verdict the check at the
    result wrote on it. A 3D model goes by its preview: it is as clear as the
    run's pictures, and a run without a preview has nothing to clear it. Code a
    language model wrote goes by its own verdict, as a picture does. Code is
    the one kind the check at the result reads at adult too, so a sketch
    refused at adult is not handed to adult either; no pass is asked of it there.
    """
    from my_app.services.safety_gate import entity_cleared_for, normalise_level

    level = normalise_level(level)
    kind = _kind_of(entity.get("type"))
    if level not in IMAGE_CHECKED_LEVELS:
        # Nothing needs a pass here. Code is the one kind the check at the
        # result reads at this level as well, and a refusal of it stands.
        if kind in CODE_KINDS and _refused_for(entity, run_metadata, level):
            return False, "blocked"
        return True, ""

    if (kind in DERIVED_IMAGE_KINDS or kind in INTERMEDIATE_IMAGE_KINDS
            or kind in PREVIEWED_KINDS):
        return _sources_cleared(run_metadata, level)
    if kind == COMPOSITION_KIND:
        return _composition_cleared(entity, level)
    if kind not in VERDICT_BEARING_KINDS:
        return True, ""

    if entity_cleared_for(entity, run_metadata, level):
        return True, ""
    if _refused_for(entity, run_metadata, level):
        return False, "blocked"
    return False, "unchecked"


def _refused_for(entity: dict, run_metadata: dict, level: str) -> bool:
    """Whether a verdict on the entity refused it where `level` stands.

    The one asking stands where the refusal was made, or stricter. A refusal at
    a stricter level says nothing about this one.
    """
    from my_app.services.safety_gate import counts_for
    from my_app.services.safety_level_resolver import SAFETY_LEVELS_STRICTEST_FIRST

    verdict = (entity.get("metadata") or {}).get(SAFETY_VERDICT_KEY)
    if not isinstance(verdict, dict) or verdict.get("safe") is not False:
        return False
    judged_at = verdict.get("level") or run_metadata.get("safety_level")
    return judged_at in SAFETY_LEVELS_STRICTEST_FIRST and counts_for(level, judged_at)


def filter_deliverable(entities: list, run_metadata: dict, level) -> list:
    """Every entity of `entities` that may be handed to `level`, order preserved."""
    return [e for e in entities if entity_cleared_for_delivery(e, run_metadata, level)[0]]



class LivePipelineRecorder:
    """
    Live stateful recorder that writes pipeline artifacts immediately to disk.

    Key features:
    1. Writes files immediately (not retroactively)
    2. Maintains current state for frontend queries
    3. Self-describes expected outputs upfront
    4. One folder per run with numbered files
    5. Single metadata.json with complete state
    """

    def __init__(
        self,
        run_id: str,
        config_name: str,
        safety_level: str,
        user_id: str = 'anonymous',
        device_id: Optional[str] = None,
        base_path: Optional[Path] = None
    ):
        """
        Initialize recorder and create run folder.

        Args:
            run_id: Unique identifier for this pipeline run
            config_name: Schema/config name (e.g., "dada", "stillepost")
            safety_level: Safety level (e.g., "kids", "teens")
            user_id: User identifier
            device_id: Device/browser identifier for folder structure (auto-generated if None)
            base_path: Base directory for pipeline_runs/ (defaults to current dir)
        """
        import uuid as uuid_module

        self.run_id = run_id
        self.config_name = config_name
        self.safety_level = safety_level
        self.user_id = user_id
        # Generate unique device_id if not provided
        self.device_id = device_id or f"dev_{uuid_module.uuid4().hex[:12]}"

        # Setup folder structure with date-based organization
        if base_path is None:
            base_path = Path.cwd()
        self.base_path = Path(base_path)

        # Date + Device based folder structure
        # exports/json/YYYY-MM-DD/device_id/run_xxx/
        date_folder = datetime.now().strftime('%Y-%m-%d')
        self.run_folder = self.base_path / date_folder / self.device_id / run_id
        self.run_folder.mkdir(parents=True, exist_ok=True)

        # Clean folder structure
        # final/ - for final outputs (favorites/restore)
        self.final_folder = self.run_folder / "final"
        self.final_folder.mkdir(parents=True, exist_ok=True)
        # prompting_process/ - for research data (all iterations)
        self.prompting_folder = self.run_folder / "prompting_process"
        self.prompting_sequence = 0  # Separate counter for prompting iterations

        # Initialize state
        self.current_stage = 0
        self.current_step = "initialized"
        self.sequence_number = 0

        # Expected outputs based on standard pipeline
        self.expected_outputs = [
            "input",
            "translation",
            "safety",
            "interception",
            "safety_pre_output",
            "output_image"
        ]

        # Initialize metadata
        self.metadata = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "config_name": config_name,
            "safety_level": safety_level,
            "user_id": user_id,
            "device_id": device_id,
            "expected_outputs": self.expected_outputs,
            "current_state": {
                "stage": self.current_stage,
                "step": self.current_step,
                "progress": "0/6"
            },
            "entities": []
        }

        # Write initial metadata
        self._save_metadata()

        logger.info(f"[RECORDER] Initialized run {run_id} in {self.run_folder}")

    def record_input_image(self, took_one: bool) -> None:
        """Say whether this run's generation took a picture in (`INPUT_IMAGE_KEY`).

        Once a run has taken one in, it has: a later generation without one
        does not clear what the earlier one made from it. And a run that wrote
        outputs before it said anything keeps not saying it, since what those
        were made from is not known here.
        """
        known = self.metadata.get(INPUT_IMAGE_KEY)
        if took_one:
            if known is True:
                return
            self.metadata[INPUT_IMAGE_KEY] = True
        elif known is not None:
            return
        elif any(str(e.get("type") or "").startswith("output_")
                 for e in self.metadata.get("entities", [])):
            return
        else:
            self.metadata[INPUT_IMAGE_KEY] = False
        self._save_metadata()

    def set_state(self, stage: int, step: str):
        """
        Update current pipeline state.

        Args:
            stage: Current stage number (1-5)
            step: Human-readable step description
        """
        self.current_stage = stage
        self.current_step = step

        # Update progress
        completed = len(self.metadata["entities"])
        total = len(self.expected_outputs)
        progress = f"{completed}/{total}"

        self.metadata["current_state"] = {
            "stage": stage,
            "step": step,
            "progress": progress
        }

        self._save_metadata()
        logger.info(f"[RECORDER] State updated: Stage {stage} - {step} ({progress})")

    def save_entity(
        self,
        entity_type: str,
        content: Union[str, bytes, dict],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save an entity to disk immediately and update metadata.

        Args:
            entity_type: Type of entity (e.g., "input", "translation", "output_image")
            content: Entity content (text, bytes, or dict)
            metadata: Optional metadata about this entity

        Returns:
            Filename of saved entity
        """
        self.sequence_number += 1

        # Determine file extension based on content type
        if isinstance(content, bytes):
            # Binary content - detect format
            if metadata and "format" in metadata:
                ext = metadata["format"]
            else:
                # Auto-detect format from binary data
                # Extract media_type from entity_type ('output_video' → 'video')
                if entity_type.startswith('output_'):
                    media_type = entity_type.replace('output_', '')
                else:
                    media_type = 'image'  # Default for non-output entities

                ext = self._detect_format_from_data(content, media_type)
                logger.debug(f"[RECORDER] Auto-detected format '{ext}' for {entity_type} (media_type={media_type})")
        elif isinstance(content, dict):
            ext = "json"
        else:
            ext = "txt"

        # Number prefix (01_, 02_) in final/ subfolder
        # final/ contains the definitive outputs for favorites/restore
        # prompting_process/ contains all iterations (001_, 002_...)
        filename = f"{self.sequence_number:02d}_{entity_type}.{ext}"
        filepath = self.final_folder / filename

        # AI-Origin Disclosure (EU AI Act Art. 50): apply watermark to
        # output_image / output_video bytes before persisting. Service is
        # fail-open — original bytes returned if anything goes wrong, and a
        # medium the disclosure is not in is written as NN_<type>_ai_generated.
        if isinstance(content, bytes):
            from my_app.services.media_marking import mark_for_disk
            content, filename = mark_for_disk(content, entity_type, metadata or {}, filename, "[RECORDER]")
            filepath = self.final_folder / filename

        # Write file
        self._write_file(filepath, content)

        # Add to metadata
        entity_record = {
            "sequence": self.sequence_number,
            "type": entity_type,
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.metadata["entities"].append(entity_record)

        # Update progress in current_state
        completed = len(self.metadata["entities"])
        total = len(self.expected_outputs)
        self.metadata["current_state"]["progress"] = f"{completed}/{total}"

        self._save_metadata()

        logger.info(f"[RECORDER] Saved entity {self.sequence_number}: {entity_type} -> {filename}")
        return filename

    def save_to_prompting_process(
        self,
        entity_type: str,
        content: Union[str, bytes, dict],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save entity to prompting_process/ subfolder (for research data).

        Used during interception to capture all prompt iterations.
        These are preserved when folder is renamed to run_xxx.

        Args:
            entity_type: Type of entity (e.g., "input", "interception")
            content: Entity content
            metadata: Optional metadata

        Returns:
            Filename of saved entity
        """
        # Create subfolder if needed
        self.prompting_folder.mkdir(parents=True, exist_ok=True)

        self.prompting_sequence += 1

        # Determine extension
        if isinstance(content, bytes):
            ext = "bin"
        elif isinstance(content, dict):
            ext = "json"
        else:
            ext = "txt"

        # Create numbered filename (3 digits for many iterations)
        filename = f"{self.prompting_sequence:03d}_{entity_type}.{ext}"
        filepath = self.prompting_folder / filename

        # Write file
        self._write_file(filepath, content)

        # Track in metadata
        if 'prompting_process' not in self.metadata:
            self.metadata['prompting_process'] = []

        self.metadata['prompting_process'].append({
            "sequence": self.prompting_sequence,
            "type": entity_type,
            "filename": f"prompting_process/{filename}",
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        })

        self._save_metadata()

        logger.info(f"[RECORDER] Saved to prompting_process: {filename}")
        return filename

    def save_error(
        self,
        stage: int,
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save an error entity.

        Args:
            stage: Stage where error occurred
            error_type: Type of error (e.g., "safety_blocked", "api_error")
            message: Error message
            details: Additional error details

        Returns:
            Filename of saved error entity
        """
        error_data = {
            "stage": stage,
            "error_type": error_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }

        return self.save_entity(
            entity_type="error",
            content=error_data,
            metadata={"stage": stage, "error_type": error_type}
        )

    def mark_entity_safety(
        self,
        sequence: int,
        safe: bool,
        reason: str = "",
        description: str = "",
        level: Optional[str] = None,
    ) -> bool:
        """
        Write a content-check verdict onto the entity it judges.

        `sequence` is the entity's own number, the one save_entity returned it
        under. The verdict lands in that entity's metadata, so every reader of
        the inventory sees it without a second lookup, and delivery can refuse
        an entity without knowing anything about how the check was run.

        `level` is the safety level the check asked at. A pass answers for that
        level and every looser one, and only that far: a picture cleared at
        youth has not been asked the children's question. A verdict written
        without a level counts at the level of its run.

        Returns True when an entity was stamped.
        """
        for entity in self.metadata.get("entities", []):
            if entity.get("sequence") != sequence:
                continue
            verdict = entity_verdict(safe, reason, description, level)
            entity.setdefault("metadata", {})[SAFETY_VERDICT_KEY] = verdict
            self._save_metadata()
            logger.info(
                "[RECORDER] Entity %s marked %s%s",
                sequence, "safe" if safe else "BLOCKED",
                "" if safe else f" ({reason})",
            )
            return True

        logger.error(
            "[RECORDER] mark_entity_safety: run %s has no entity %s — verdict lost",
            self.run_id, sequence,
        )
        return False

    def output_entities(self, media_type: str) -> list:
        """
        Every `output_<media_type>` entity of this run, in the order delivery
        serves them.

        One line, because the selection rule already exists and calls itself
        the platform's single one (`media_ref.find_media_entities`). Another
        copy of it here would be a parallel structure — and the copies that do
        exist have drifted: most of them take the entities in the order they lie
        in the list rather than by `sequence`, which makes an index mean
        different pictures on different paths. Consolidating those is its own
        piece of work; this method adds none.
        """
        from my_app.utils.media_ref import find_media_entities
        return find_media_entities(self.metadata.get("entities", []), media_type)

    def checked_entity_path(self, entity: dict, level) -> Path:
        """
        The file behind an entity — and only when the content check cleared it.

        THE place a recorded entity becomes a path. Guarding one route's
        resolver left seven other ways to the same bytes (static export route,
        the by-filename route, the entity route, the research-table thumbnail,
        Resona's chat, the media-ref resolver, post-production). They differ in
        how they find the entity and agree in what they do with it, so the
        refusal belongs here, where they meet.

        `level` is the level of whoever asks (entity_cleared_for_delivery).

        Raises SafetyRefusal when the entity was blocked or never cleared for
        that level.
        """
        cleared, reason = entity_cleared_for_delivery(entity, self.metadata, level)
        if not cleared:
            raise SafetyRefusal(reason, self.run_id, entity.get("filename") or "",
                                field=refused_field(entity))
        return self.final_folder / entity["filename"]

    def checked_path_for_filename(self, filename: str, level) -> Path:
        """
        The file a caller names by its FILENAME — asked the same question.

        Two routes address a run's files by name instead of by entity, and a
        name alone carries no verdict. So the name is turned back into the
        entity that owns it, and that entity is asked. A file in `final/` that
        no entity names is served as before: ARCHITECTURE PART 18 has it that
        such a file is invisible platform-wide, and inventing a refusal for it
        here would be a second rule about entities living outside the register.

        Raises SafetyRefusal when the named file belongs to a refused entity.
        """
        name = str(filename or "")
        for entity in self.metadata.get("entities", []):
            if entity.get("filename") == name:
                return self.checked_entity_path(entity, level)
        return self.final_folder / name

    def unchecked_entity_path_for_checking(self, entity: dict) -> Path:
        """
        The file behind an entity WITHOUT asking the verdict.

        Exactly one caller may use this: the content check itself, which has to
        read the picture or the video in order to judge it, at a moment when no
        verdict can exist yet. Anything else that reaches for this is handing
        out an unjudged picture.
        """
        return self.final_folder / entity["filename"]

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status for frontend queries.

        Returns:
            Status dictionary with current state and completed outputs
        """
        # Defensive: ensure entities field exists (backward compatibility)
        entities = self.metadata.get("entities", [])
        completed_outputs = [e["type"] for e in entities]

        # Determine next expected output
        next_expected = None
        for expected in self.expected_outputs:
            if expected not in completed_outputs:
                next_expected = expected
                break

        # Defensive: ensure current_state exists
        current_state = self.metadata.get("current_state", {
            "stage": 0,
            "step": "unknown",
            "progress": "0/0"
        })

        return {
            "run_id": self.run_id,
            "current_state": current_state,
            "expected_outputs": self.expected_outputs,
            "completed_outputs": completed_outputs,
            "next_expected": next_expected,
            "entities": [public_entity(e) for e in entities]
        }

    def get_entity_path(self, entity_type: str, level) -> Optional[Path]:
        """
        Filesystem path for the FIRST entity of a type, or None.

        Asks the content check's verdict on the way out, at the level of
        whoever asks, so a caller that reaches for a path by type cannot hand
        out a picture delivery would refuse.

        Returns None where the entity is absent AND where it is refused; a
        caller that wants to tell those apart uses `checked_entity_path`, which
        raises with a reason.
        """
        for entity in self.metadata["entities"]:
            if entity["type"] == entity_type:
                # Entities are stored in final/ subfolder
                try:
                    return self.checked_entity_path(entity, level)
                except SafetyRefusal as refusal:
                    logger.warning("[RECORDER] %s", refusal)
                    return None
        return None

    def save_prompt_id(self, prompt_id: str, media_type: str = 'image'):
        """
        Save ComfyUI prompt_id to metadata for SSE streaming.

        Args:
            prompt_id: ComfyUI prompt ID
            media_type: Type of media being generated
        """
        if 'comfyui_prompt_ids' not in self.metadata:
            self.metadata['comfyui_prompt_ids'] = []

        self.metadata['comfyui_prompt_ids'].append({
            'prompt_id': prompt_id,
            'media_type': media_type,
            'timestamp': datetime.now().isoformat()
        })

        self._save_metadata()
        logger.info(f"[RECORDER] Saved prompt_id {prompt_id} for {media_type}")

    def mark_complete(self):
        """Mark the pipeline run as complete."""
        self.set_state(5, "complete")
        logger.info(f"[RECORDER] Run {self.run_id} marked complete")

    async def download_and_save_from_comfyui(
        self,
        prompt_id: str,
        media_type: str,
        config: str,
        seed: Optional[int] = None
    ) -> Optional[str]:
        """
        Download media from ComfyUI and save as entity.

        Args:
            prompt_id: ComfyUI prompt ID
            media_type: Type of media ('image', 'audio', 'video')
            config: Output config name
            seed: Optional seed value used for generation

        Returns:
            Filename of saved entity, or None if failed
        """
        try:
            from my_app.services.comfyui_ws_client import get_comfyui_ws_client
            client = get_comfyui_ws_client()

            # Check ComfyUI health before waiting
            is_healthy = await client.health_check()
            if not is_healthy:
                logger.error(f"[RECORDER] ✗ ComfyUI not responding before download attempt for {prompt_id}")
                return None

            # Wait for workflow completion (with polling + retry logic), as long
            # as the configuration promises every ComfyUI run; a fixed 90 s
            # stood here until 2026-10-10 and gave up on a video (finding S-053 of the code review of 2026-10-10).
            from config import COMFYUI_TIMEOUT
            logger.info(f"[RECORDER] Waiting for ComfyUI workflow completion: {prompt_id}")
            history = await client.wait_for_completion(prompt_id, timeout=COMFYUI_TIMEOUT)

            # Check if history was returned
            if not history:
                logger.error(f"[RECORDER] ✗ No history returned for {prompt_id} - workflow may have timed out or disappeared")
                return None

            # Get generated files
            if media_type == 'image':
                files = await client.get_generated_images(history)
            elif media_type in ['audio', 'music']:
                files = await client.get_generated_audio(history)
            elif media_type == 'video':
                files = await client.get_generated_video(history)
            elif media_type == '3d':
                files = await client.get_generated_3d(history)    
            else:
                logger.error(f"[RECORDER] ✗ Unsupported media type for ComfyUI: {media_type}")
                return None

            if not files:
                logger.error(f"[RECORDER] ✗ No {media_type} files found in ComfyUI history for {prompt_id}")
                logger.error(f"[RECORDER] History keys: {list(history.keys()) if history else 'None'}")
                return None

            logger.info(f"[RECORDER] Found {len(files)} {media_type} file(s) from ComfyUI")

            # Download ALL files (for multi-image workflows)
            downloaded_files = []
            saved_filenames = []

            for idx, file_info in enumerate(files):
                file_data = await client.get_image(
                    filename=file_info['filename'],
                    subfolder=file_info.get('subfolder', ''),
                    folder_type=file_info.get('type', 'output')
                )

                if not file_data:
                    logger.warning(f"[RECORDER] Failed to download file {idx+1}/{len(files)}: {file_info['filename']}")
                    continue

                downloaded_files.append(file_data)

                # Detect format
                file_format = self._detect_format_from_data(file_data, media_type)

                # Get dimensions for images
                metadata = {
                    'config': config,
                    'format': file_format,
                    'backend': 'comfyui',
                    'prompt_id': prompt_id,
                    'file_index': idx,
                    'total_files': len(files),
                    'node_id': file_info.get('node_id', 'unknown')
                }

                # Add seed if provided
                if seed is not None:
                    metadata['seed'] = seed

                if media_type == 'image':
                    width, height = self._get_image_dimensions_from_bytes(file_data)
                    if width and height:
                        metadata['width'] = width
                        metadata['height'] = height

                # Save individual file as entity
                filename = self.save_entity(
                    entity_type=f'output_{media_type}',
                    content=file_data,
                    metadata=metadata
                )
                saved_filenames.append(filename)
                logger.info(f"[RECORDER] ✓ Saved image {idx+1}/{len(files)}: {filename}")

            if not downloaded_files:
                logger.error(f"[RECORDER] ✗ Failed to download any {media_type} files")
                return None

            # Every file the run produced is saved; the first is the one the
            # pipeline carries on with.
            return saved_filenames[0] if saved_filenames else None

        except Exception as e:
            logger.error(f"[RECORDER] Error downloading from ComfyUI: {e}")
            return None

    async def download_and_save_from_url(
        self,
        url: str,
        media_type: str,
        config: str,
        seed: Optional[int] = None
    ) -> Optional[str]:
        """
        Download media from URL and save as entity.

        Args:
            url: URL to download from
            media_type: Type of media ('image', 'audio', 'video')
            config: Output config name
            seed: Optional seed value used for generation

        Returns:
            Filename of saved entity, or None if failed
        """
        try:
            # Download from URL
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            file_data = response.content

            # Detect backend from URL
            backend = 'api'
            if 'openrouter' in url or 'openai' in url:
                backend = 'gpt5'
            elif 'replicate' in url:
                backend = 'replicate'

            # Detect format
            file_format = self._detect_format_from_data(file_data, media_type)

            # Get dimensions for images
            metadata = {
                'config': config,
                'format': file_format,
                'backend': backend,
                'source_url': url
            }

            # Add seed if provided
            if seed is not None:
                metadata['seed'] = seed

            if media_type == 'image':
                width, height = self._get_image_dimensions_from_bytes(file_data)
                if width and height:
                    metadata['width'] = width
                    metadata['height'] = height

            # Save as entity
            filename = self.save_entity(
                entity_type=f'output_{media_type}',
                content=file_data,
                metadata=metadata
            )

            logger.info(f"[RECORDER] Downloaded and saved {media_type} from URL ({len(file_data)} bytes)")
            return filename

        except Exception as e:
            logger.error(f"[RECORDER] Error downloading from URL: {e}")
            return None

    def _detect_format_from_data(self, data: bytes, media_type: str) -> str:
        """
        Detect file format from binary data.

        Args:
            data: Binary file data
            media_type: Expected media type

        Returns:
            File format extension (e.g., 'png', 'jpg', 'mp3')
        """
        if media_type == 'image':
            try:
                img = Image.open(BytesIO(data))
                return img.format.lower() if img.format else 'png'
            except:
                return 'png'  # Default
        elif media_type in ['audio', 'music']:
            # Simple heuristic based on headers
            if data[:4] == b'RIFF':
                return 'wav'
            elif data[:3] == b'ID3' or data[:2] == b'\xff\xfb':
                return 'mp3'
            return 'wav'  # Default
        elif media_type == 'video':
            if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                return 'webp'
            elif len(data) >= 8 and data[4:8] == b'ftyp':
                return 'mp4'
            return 'mp4'  # Default
        else:
            return 'bin'  # Unknown

    def _get_image_dimensions_from_bytes(self, data: bytes) -> tuple[Optional[int], Optional[int]]:
        """
        Get image dimensions from binary data.

        Args:
            data: Binary image data

        Returns:
            (width, height) tuple, or (None, None) if unable to determine
        """
        try:
            img = Image.open(BytesIO(data))
            return img.width, img.height
        except:
            return None, None

    def create_composite_image(
        self,
        image_data_list: List[bytes],
        labels: List[str],
        workflow_title: str,
    ) -> bytes:
        """
        Create a composite image with header and labeled sub-images arranged horizontally.

        Args:
            image_data_list: List of image data (bytes) to composite
            labels: List of labels for each image (same length as image_data_list)
            workflow_title: Title to display in header

        Returns:
            PNG bytes of composite image
        """
        try:
            # Load images from bytes
            images = [Image.open(BytesIO(data)) for data in image_data_list]

            # Get dimensions (assuming all images are same size)
            img_width, img_height = images[0].size
            num_images = len(images)

            # Layout constants
            SPACING = 30  # Space between images
            HEADER_HEIGHT = 80  # Header section height
            FOOTER_HEIGHT = 120  # Footer for labels (2-3 lines of text)

            # Calculate composite dimensions
            composite_width = (img_width * num_images) + (SPACING * (num_images - 1))
            composite_height = HEADER_HEIGHT + img_height + FOOTER_HEIGHT

            # Create composite image with white background
            composite = Image.new('RGB', (composite_width, composite_height), color='white')
            draw = ImageDraw.Draw(composite)

            # Try to load fonts (with fallback)
            try:
                header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
                label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            except:
                # Fallback to default font if DejaVu not available
                logger.warning("[COMPOSITE] DejaVu fonts not found, using default font")
                header_font = ImageFont.load_default()
                label_font = ImageFont.load_default()

            # Draw header with light gray background
            draw.rectangle([(0, 0), (composite_width, HEADER_HEIGHT)], fill='#f5f5f5')

            # Draw header text (2 lines)
            header_line1 = "UNESCO Chair in Digital Culture and Arts in Education"
            header_line2 = f"ai4artsed Project - {workflow_title}"

            # Center header text
            bbox1 = draw.textbbox((0, 0), header_line1, font=header_font)
            bbox2 = draw.textbbox((0, 0), header_line2, font=header_font)
            text1_width = bbox1[2] - bbox1[0]
            text2_width = bbox2[2] - bbox2[0]

            draw.text(
                ((composite_width - text1_width) // 2, 15),
                header_line1,
                fill='#333333',
                font=header_font
            )
            draw.text(
                ((composite_width - text2_width) // 2, 45),
                header_line2,
                fill='#333333',
                font=header_font
            )

            # Paste images horizontally
            current_x = 0
            for i, img in enumerate(images):
                y_offset = HEADER_HEIGHT
                composite.paste(img, (current_x, y_offset))

                # Draw label below image (centered, multi-line)
                label = labels[i]
                label_lines = label.split('\n')

                # Calculate label position (centered under image)
                label_y = HEADER_HEIGHT + img_height + 15
                for line in label_lines:
                    bbox = draw.textbbox((0, 0), line, font=label_font)
                    line_width = bbox[2] - bbox[0]
                    label_x = current_x + (img_width - line_width) // 2
                    draw.text((label_x, label_y), line, fill='#000000', font=label_font)
                    label_y += 30  # Line spacing

                current_x += img_width + SPACING

            # Convert to PNG bytes
            output_buffer = BytesIO()
            composite.save(output_buffer, format='PNG')
            return output_buffer.getvalue()

        except Exception as e:
            logger.error(f"[COMPOSITE] Error creating composite image: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _write_file(self, filepath: Path, content: Union[str, bytes, dict]):
        """
        Write content to file with appropriate encoding.

        Args:
            filepath: Path to write to
            content: Content to write
        """
        try:
            if isinstance(content, bytes):
                # Binary content (images)
                filepath.write_bytes(content)
            elif isinstance(content, dict):
                # JSON content
                filepath.write_text(json.dumps(content, indent=2, ensure_ascii=False))
            else:
                # Text content
                filepath.write_text(str(content), encoding='utf-8')
        except Exception as e:
            logger.error(f"[RECORDER] Failed to write {filepath}: {e}")
            raise

    def _save_metadata(self):
        """Save metadata.json to disk immediately.

        Written to a file of its own beside it and moved over it, as
        latent_lab_recorder._amend_entity_meta does: whoever reads the record
        while it is saved -- the stream route, the research export -- finds the
        previous version or this one, never part of one. The temporary name is
        one per call, so two threads never write into the same file.
        """
        metadata_path = self.run_folder / "metadata.json"
        tmp = metadata_path.with_name(f"{metadata_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with _metadata_save_lock:
                tmp.write_text(
                    json.dumps(self.metadata, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
                os.replace(str(tmp), str(metadata_path))
        except Exception as e:
            logger.error(f"[RECORDER] Failed to save metadata: {e}")
            try:
                tmp.unlink()
            except OSError:
                pass
            raise

    def save_workflow_json(self, workflow: Dict[str, Any], entity_type: str = 'workflow') -> str:
        """
        Save complete workflow JSON for reproducibility.

        This is used for legacy workflows to archive the complete workflow structure
        that was executed, enabling reproducibility and debugging.

        Args:
            workflow: Complete ComfyUI workflow JSON
            entity_type: Type of entity (default: 'workflow')

        Returns:
            Filename of saved workflow JSON
        """
        try:
            metadata = {
                'type': 'workflow_archive',
                'timestamp': datetime.now().isoformat(),
                'node_count': len(workflow) if isinstance(workflow, dict) else 0
            }

            filename = self.save_entity(
                entity_type=entity_type,
                content=workflow,  # save_entity handles dict → JSON conversion
                metadata=metadata
            )

            logger.info(f"[RECORDER] Saved workflow JSON with {metadata['node_count']} nodes")
            return filename

        except Exception as e:
            logger.error(f"[RECORDER] Error saving workflow JSON: {e}")
            raise

    # REMOVED: download_and_save_all_from_comfyui()
    # Legacy workflows: comfyui_ws_client.submit_and_track submits, waits and
    # downloads; the prompt helpers are the functions of legacy_workflow_service.py.
    # Media files reach the recorder as binary data.


def generate_run_id(suffix: str = None) -> str:
    """Single authority for run_id generation. Chronologically sortable."""
    base = f"run_{int(time.time() * 1000)}_{os.urandom(3).hex()}"
    return f"{base}_{suffix}" if suffix else base


# Singleton management
_active_recorders: Dict[str, LivePipelineRecorder] = {}


def get_recorder(
    run_id: str,
    config_name: Optional[str] = None,
    safety_level: Optional[str] = None,
    user_id: str = 'anonymous',
    device_id: Optional[str] = None,
    base_path: Optional[Path] = None
) -> LivePipelineRecorder:
    """
    Get or create a recorder for a specific run.

    Args:
        run_id: Unique run identifier
        config_name: Schema/config name (required for new recorders)
        safety_level: Safety level (required for new recorders)
        user_id: User identifier
        device_id: Device/browser identifier for folder structure (auto-generated if None)
        base_path: Base directory for pipeline_runs/

    Returns:
        LivePipelineRecorder instance
    """
    if run_id in _active_recorders:
        return _active_recorders[run_id]

    if config_name is None or safety_level is None:
        raise ValueError("config_name and safety_level required for new recorder")

    recorder = LivePipelineRecorder(
        run_id=run_id,
        config_name=config_name,
        safety_level=safety_level,
        user_id=user_id,
        device_id=device_id,  # Will auto-generate if None
        base_path=base_path
    )
    _active_recorders[run_id] = recorder
    return recorder


def load_recorder(run_id: str, base_path: Optional[Path] = None) -> Optional[LivePipelineRecorder]:
    """
    Load an existing recorder from disk.

    Searches across date-based folders with device_id subfolders:
    - New format: YYYY-MM-DD/device_id/run_xxx/
    - Legacy format: YYYY-MM-DD/run_xxx/ (backward compat)
    - Direct path: run_xxx/ (oldest format)

    Args:
        run_id: Run identifier to load
        base_path: Base directory for pipeline_runs/

    Returns:
        LivePipelineRecorder instance, or None if not found
    """
    if run_id in _active_recorders:
        return _active_recorders[run_id]

    if base_path is None:
        base_path = Path.cwd()

    base_path = Path(base_path)

    # Search for run_id across folders (multiple formats for backward compat)
    metadata_path = None

    # First, check direct path (oldest legacy format)
    direct_path = base_path / run_id / "metadata.json"
    if direct_path.exists():
        metadata_path = direct_path
    else:
        # Search in date folders
        for date_folder in sorted(base_path.glob('20??-??-??'), reverse=True):
            # New format - check device_id subfolders first
            # Structure: YYYY-MM-DD/device_id/run_xxx/
            for device_folder in date_folder.iterdir():
                if device_folder.is_dir():
                    candidate = device_folder / run_id / "metadata.json"
                    if candidate.exists():
                        metadata_path = candidate
                        break
            if metadata_path:
                break

            # Legacy format: YYYY-MM-DD/run_xxx/ (no device_id folder)
            legacy_candidate = date_folder / run_id / "metadata.json"
            if legacy_candidate.exists():
                metadata_path = legacy_candidate
                break

    if not metadata_path:
        logger.warning(f"[RECORDER] No metadata found for run {run_id}")
        return None

    try:
        metadata = json.loads(metadata_path.read_text())

        # Backward compatibility: handle old metadata format
        # Old format used "schema" instead of "config_name"
        config_name = metadata.get("config_name") or metadata.get("schema", "unknown")

        # Old format might not have safety_level
        safety_level = metadata.get("safety_level", "kids")

        # Get the actual run folder from the metadata path
        actual_run_folder = metadata_path.parent

        # Create recorder instance manually (bypass __init__'s folder creation)
        recorder = object.__new__(LivePipelineRecorder)
        recorder.run_id = metadata["run_id"]
        recorder.config_name = config_name
        recorder.safety_level = safety_level
        recorder.user_id = metadata.get("user_id", "anonymous")
        recorder.device_id = metadata.get("device_id", "anonymous")
        recorder.base_path = base_path
        recorder.run_folder = actual_run_folder  # Use existing folder path
        # Restore subfolder paths and ensure they exist
        recorder.final_folder = actual_run_folder / "final"
        recorder.final_folder.mkdir(parents=True, exist_ok=True)
        recorder.prompting_folder = actual_run_folder / "prompting_process"
        recorder.current_stage = 0
        recorder.current_step = "initialized"
        recorder.sequence_number = 0
        # Restore prompting_sequence from existing data
        recorder.prompting_sequence = len(metadata.get("prompting_process", []))
        recorder.expected_outputs = [
            "input", "translation", "safety", "interception",
            "safety_pre_output", "output_image"
        ]
        recorder.metadata = {}

        # Restore state (handle both old and new formats)
        # Ensure critical fields exist in metadata for backward compatibility
        if "entities" not in metadata:
            metadata["entities"] = []

        if "current_state" not in metadata:
            metadata["current_state"] = {
                "stage": 0,
                "step": "completed",
                "progress": "0/0"
            }

        if "expected_outputs" not in metadata:
            metadata["expected_outputs"] = recorder.expected_outputs

        # Now it's safe to restore metadata
        recorder.metadata = metadata

        # Restore internal state
        recorder.sequence_number = len(metadata["entities"])
        recorder.current_stage = metadata["current_state"].get("stage", 0)
        recorder.current_step = metadata["current_state"].get("step", "initialized")

        _active_recorders[run_id] = recorder
        logger.info(f"[RECORDER] Loaded existing run {run_id}")
        return recorder

    except Exception as e:
        logger.error(f"[RECORDER] Failed to load run {run_id}: {e}")
        return None
