"""
Post-Production Service — the platform's first "media-as-operand" action class.

Generation is prompt -> artifact. Transformation is text -> text. Post-production
is artifact(s) -> artifact: it takes one or more EXISTING media artifacts and
composes a NEW one. This is categorically different from Stage 4 generation, where
media is always a terminal leaf; here media is an *operand*.

Phase 1 ships exactly one operation:
  - still_plus_audio: a kept image + a kept sound -> an MP4 "Bild+Ton"
    (a static frame held for the sound's duration). Delivered as .mp4 because
    that is the only container universally playable; but its platform semantics
    are its own — entity type "output_composition", with "composed_from"
    provenance recording which artifacts it was built from (NOT prompt->artifact).

Design notes:
  - Inputs are referenced by run_id (what Resona gets from lookup_shared_favorites)
    or an /api/media/<type>/<run_id> URL. Resolution reuses the recorder's own
    get_entity_path(), exactly like view_favorite (tool_registry.py).
  - Output is persisted via the standard LivePipelineRecorder (get_recorder +
    save_entity), so a composition is a first-class run: it appears on disk under
    exports/json/, is served by /api/media/composition/<run_id>, and can be
    favorited like any other artifact.
  - ffmpeg is reused as the muxing primitive (same dependency watermark_service
    already relies on). The mux is fast, so callers may run it inline.

Later operations (video+audio underlay, image montage) are additive entries in
OPERATIONS — no change to the core.
"""

import logging
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Entity type of every post-production output. Deliberately NOT "output_video":
# a composition is its own kind (see module docstring). Consumers (serving route,
# watermark dispatch, gallery) branch on this.
COMPOSITION_ENTITY_TYPE = "output_composition"

# Role -> acceptable source entity types. A resona image favorite is "output_image";
# a sound favorite is "output_audio" (or "output_music" for the music configs).
_ROLE_ENTITY_TYPES: Dict[str, List[str]] = {
    "image": ["output_image"],
    "audio": ["output_audio", "output_music"],
    "video": ["output_video"],
}

_MEDIA_URL_RE = re.compile(r"/api/media/[^/]+/([^/?#]+)")


class PostProductionError(Exception):
    """Raised when a composition cannot be produced (bad refs, ffmpeg failure)."""


# ---------------------------------------------------------------------------
# Ref resolution
# ---------------------------------------------------------------------------

def _extract_run_id(ref: str) -> str:
    """Accept a bare run_id or an /api/media/<type>/<run_id>[/idx] URL."""
    ref = (ref or "").strip()
    m = _MEDIA_URL_RE.search(ref)
    return m.group(1) if m else ref


def _resolve_ref(ref: str, role: str, base_path: Path) -> Tuple[Path, str, str]:
    """Resolve an input ref to (file_path, run_id, entity_type).

    Reuses the recorder's own get_entity_path (same channel as view_favorite).
    """
    from my_app.services.pipeline_recorder import SafetyRefusal, load_recorder

    run_id = _extract_run_id(ref)
    if not run_id:
        raise PostProductionError(f"role '{role}': empty reference")

    accepted = _ROLE_ENTITY_TYPES.get(role)
    if not accepted:
        raise PostProductionError(f"unknown role '{role}'")

    recorder = load_recorder(run_id, base_path=base_path)
    if recorder is None:
        raise PostProductionError(
            f"role '{role}': run '{run_id}' not found on disk"
        )

    # The verdict is asked before the source goes into a composition. Without
    # it the refusal on delivery would be one hop wide: a blocked picture could
    # be laid into a still+sound file, and that file is served under its own
    # entity type, which carries no verdict of its own.
    for etype in accepted:
        for entity in recorder.metadata.get("entities", []):
            if entity.get("type") != etype:
                continue
            try:
                path = recorder.checked_entity_path(entity)
            except SafetyRefusal as refusal:
                raise PostProductionError(
                    f"role '{role}': run '{run_id}' {etype} is {refusal.reason}"
                )
            if path.exists():
                return Path(path), run_id, etype
            break

    have = [e.get("type") for e in recorder.metadata.get("entities", [])]
    raise PostProductionError(
        f"role '{role}': run '{run_id}' has no {accepted} entity (has: {have})"
    )


# ---------------------------------------------------------------------------
# ffmpeg helpers
# ---------------------------------------------------------------------------

def _require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise PostProductionError("ffmpeg not found on PATH")
    return exe


def _probe_duration(path: Path) -> Optional[float]:
    """Return media duration in seconds via ffprobe, or None if unavailable."""
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def _build_still_plus_audio(paths: Dict[str, Path], out_path: Path) -> List[str]:
    """ffmpeg command: hold a still frame for the audio's duration + mux the audio.

    Bounded with -t <audio_duration> so the video ends exactly with the sound
    (plain -loop + -shortest overshoots by up to one keyframe interval).
    """
    exe = _require_ffmpeg()
    audio_dur = _probe_duration(paths["audio"])
    cmd = [
        exe, "-nostdin", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(paths["image"]),
        "-i", str(paths["audio"]),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if audio_dur and audio_dur > 0:
        cmd += ["-t", f"{audio_dur:.3f}"]
    else:
        cmd += ["-shortest"]  # fallback if ffprobe unavailable
    cmd.append(str(out_path))
    return cmd


def _build_video_plus_audio(paths: Dict[str, Path], out_path: Path) -> List[str]:
    """ffmpeg command: lay a sound under a video; the piece runs for the SHORTER
    of the two, then BOTH picture (-> black) and sound (-> silence) fade out softly.

    Platform videos are short (5-10s) and usually silent; sounds run longer. So the
    video governs the length and the (longer) sound is cut with a graceful ~1s fade,
    rather than looped or frozen. Fade is clamped so it never exceeds a short clip.
    User decision 2026-07-04: "shorter ends the piece, softly faded out."
    """
    exe = _require_ffmpeg()
    v_dur = _probe_duration(paths["video"]) or 0.0
    a_dur = _probe_duration(paths["audio"]) or 0.0
    durs = [d for d in (v_dur, a_dur) if d and d > 0]
    total = min(durs) if durs else 0.0
    fade = min(1.0, total * 0.5) if total > 0 else 0.0
    cmd = [
        exe, "-nostdin", "-y", "-loglevel", "error",
        "-i", str(paths["video"]),
        "-i", str(paths["audio"]),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if total > 0:
        st = max(0.0, total - fade)
        cmd += [
            "-t", f"{total:.3f}",
            "-vf", f"fade=t=out:st={st:.3f}:d={fade:.3f}",
            "-af", f"afade=t=out:st={st:.3f}:d={fade:.3f}",
        ]
    else:
        cmd += ["-shortest"]  # fallback if probing failed
    cmd.append(str(out_path))
    return cmd


# ---------------------------------------------------------------------------
# Operation registry
# ---------------------------------------------------------------------------

OPERATIONS: Dict[str, dict] = {
    "still_plus_audio": {
        "label": "Bild+Ton (still image with sound)",
        "roles": ["image", "audio"],   # required input roles
        "output_format": "mp4",
        "build_cmd": _build_still_plus_audio,
    },
    "video_plus_audio": {
        "label": "Video+Ton (video with sound)",
        "roles": ["video", "audio"],   # required input roles
        "output_format": "mp4",
        "build_cmd": _build_video_plus_audio,
    },
    # Phase 2+ (additive, no core change):
    #   "image_montage": [image, image, ...] -> image
}


def list_operations() -> Dict[str, str]:
    """operation_id -> human label (for tool enums / UI)."""
    return {op_id: spec["label"] for op_id, spec in OPERATIONS.items()}


def validate_inputs(
    operation_id: str,
    inputs: Dict[str, str],
    *,
    base_path: Optional[Path] = None,
) -> List[dict]:
    """Resolve + type-check an operation's inputs WITHOUT composing.

    Lets a caller (Resona's compose_media decision tool) confirm the refs are
    real artifacts of the right role before acknowledging the composition, and
    get the same ``composed_from`` provenance compose() will record.

    Returns composed_from (list of {role, run_id, type}).
    Raises PostProductionError on unknown operation or unresolvable/mistyped refs.
    """
    spec = OPERATIONS.get(operation_id)
    if spec is None:
        raise PostProductionError(
            f"unknown operation '{operation_id}'; available: {list(OPERATIONS)}"
        )
    if base_path is None:
        import config
        base_path = Path(config.JSON_STORAGE_DIR)
    base_path = Path(base_path)

    composed_from: List[dict] = []
    for role in spec["roles"]:
        ref = inputs.get(role)
        if not ref:
            raise PostProductionError(
                f"operation '{operation_id}' requires input role '{role}'"
            )
        _path, run_id, etype = _resolve_ref(ref, role, base_path)
        composed_from.append({"role": role, "run_id": run_id, "type": etype})
    return composed_from


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _new_run_id() -> str:
    """Match the platform's run_id shape: run_<ms>_<hex6>."""
    return f"run_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def compose(
    operation_id: str,
    inputs: Dict[str, str],
    *,
    base_path: Optional[Path] = None,
    safety_level: str = "open",
    user_id: str = "resona",
    device_id: Optional[str] = None,
) -> dict:
    """Compose a new artifact from existing ones.

    Args:
        operation_id: key in OPERATIONS (Phase 1: "still_plus_audio").
        inputs: {role: ref} where ref is a run_id or /api/media/<type>/<run_id> URL
            (e.g. {"image": "run_...", "audio": "run_..."}).
        base_path: recorder storage root; defaults to config.JSON_STORAGE_DIR.
        safety_level/user_id/device_id: metadata for the new composition run.

    Returns:
        {run_id, media_type: "composition", url, filename, operation, composed_from}

    Raises:
        PostProductionError on unknown operation, unresolvable refs, or ffmpeg failure.
    """
    spec = OPERATIONS.get(operation_id)
    if spec is None:
        raise PostProductionError(
            f"unknown operation '{operation_id}'; available: {list(OPERATIONS)}"
        )

    if base_path is None:
        import config
        base_path = Path(config.JSON_STORAGE_DIR)
    base_path = Path(base_path)

    # Resolve every required role -> path, and record provenance.
    resolved: Dict[str, Path] = {}
    composed_from: List[dict] = []
    for role in spec["roles"]:
        ref = inputs.get(role)
        if not ref:
            raise PostProductionError(f"operation '{operation_id}' requires input role '{role}'")
        path, run_id, etype = _resolve_ref(ref, role, base_path)
        resolved[role] = path
        composed_from.append({"role": role, "run_id": run_id, "type": etype})

    # Build + run ffmpeg into a temp file, then hand the bytes to the recorder.
    out_fmt = spec["output_format"]
    with tempfile.TemporaryDirectory(prefix="pp_") as tmpd:
        out_path = Path(tmpd) / f"composition.{out_fmt}"
        cmd = spec["build_cmd"](resolved, out_path)
        logger.info(f"[POST-PROD] {operation_id}: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              stdin=subprocess.DEVNULL)
        if proc.returncode != 0 or not out_path.exists():
            raise PostProductionError(
                f"ffmpeg failed for '{operation_id}': {proc.stderr.strip()[:500]}"
            )
        media_bytes = out_path.read_bytes()

    # Persist as a first-class run (own semantic: config_name marks provenance).
    from my_app.services.pipeline_recorder import get_recorder

    run_id = _new_run_id()
    recorder = get_recorder(
        run_id=run_id,
        config_name="post_production",
        safety_level=safety_level,
        user_id=user_id,
        device_id=device_id,
        base_path=base_path,
    )
    filename = recorder.save_entity(
        COMPOSITION_ENTITY_TYPE,
        media_bytes,
        metadata={
            "format": out_fmt,
            "pp_operation": operation_id,
            "composed_from": composed_from,
        },
    )

    logger.info(
        f"[POST-PROD] {operation_id} -> run {run_id} ({filename}), "
        f"from {[c['run_id'] for c in composed_from]}"
    )
    return {
        "run_id": run_id,
        "media_type": "composition",
        "url": f"/api/media/composition/{run_id}",
        "filename": filename,
        "operation": operation_id,
        "composed_from": composed_from,
    }
