"""
Media references, resolved in one place.

An image travels through this platform in a dozen shapes: an absolute path, a
relative media URL, a bare run_id, an upload id, raw base64. Every consumer used
to re-invent the resolution, and each invented its own silent fallback. The
worst of them treated any string it could not place as base64, so a media URL
was decoded into garbage and handed to the vision model as an image — which is
why a Canvas image_evaluation reading a generated image could never work, on any
config, since the node was introduced.

This module is the only code that turns a REFERENCE into a file path or into
base64 for the vision channel. It has explicit branches and no else-case: an
unresolvable reference raises MediaRefError naming what it received, instead of
guessing and failing three layers down as something unrelated.

Entity selection deliberately follows the media route
(/api/media/<kind>/<run_id>/<index>), because that URL is what the rest of the
platform passes around: exact `output_<kind>` entities, legacy bare `<kind>` as
fallback, ordered by sequence, index -1 = latest.
"""

import base64
import io
import logging
import re
from pathlib import Path
from typing import List, Optional, Union

from PIL import Image

logger = logging.getLogger(__name__)

# The envelope the vision paths already agreed on (vlm_safety, vision_support):
# under 64px the VLM runner rejects the bitmap, over 768px oversized input has
# repeatedly taken the runner down and 500'd every request behind it.
IMAGE_MAX_SIZE = 768
IMAGE_MIN_SIZE = 64

_MEDIA_URL_RE = re.compile(
    r'^/api/media/(?P<kind>image|audio|video|3d)/(?P<run_id>[^/?#]+?)(?:/(?P<index>-?\d+))?/?$'
)
_UPLOAD_URL_RE = re.compile(r'^/api/media/uploads/(?P<upload_id>[^/?#]+?)/?$')
_UPLOAD_EXTS = ('png', 'jpg', 'jpeg', 'webp')
_MAX_PATHLIKE_LEN = 1024  # beyond this a "string" is base64, not a path


class MediaRefError(FileNotFoundError):
    """A media reference could not be resolved. Raised, never swallowed.

    Subclasses FileNotFoundError so the handlers that already answer 404 for a
    missing image keep working unchanged."""


# Recorded as `output_*` and yet no medium anybody is handed. A run may keep
# its final latent so that a SET of runs can be averaged before the decoder
# (the Latent Lab instrument "Mean Images", 2026-09-04); that file is numpy,
# there is no media route for it, and every listing that walks `output_*` would
# otherwise offer it as something to look at, download or read a disclosure off.
NON_MEDIA_OUTPUTS = frozenset({'output_latent'})


def is_media_entity(entity_type: str) -> bool:
    """Whether an entity is an output a surface can actually be handed.

    For the listings that walk `output_*` generically, where the entity's KIND
    is whatever stands behind the underscore. `find_media_entities` below asks
    for one named kind and needs none of this.
    """
    name = str(entity_type or '')
    return name.startswith('output_') and name not in NON_MEDIA_OUTPUTS


def find_media_entities(entities: List[dict], kind: str = 'image') -> List[dict]:
    """All recorded entities of one media kind, in the order the media route
    serves them. The single entity-selection rule for the whole platform."""
    found = [e for e in entities if e.get('type') == f'output_{kind}']
    if not found:  # legacy runs recorded the bare kind
        found = [e for e in entities if e.get('type') == kind]
    found.sort(key=lambda e: e.get('sequence', (e.get('metadata') or {}).get('file_index', 0)))
    return found


def _load_recorder(run_id: str):
    from my_app.services.pipeline_recorder import load_recorder
    from config import JSON_STORAGE_DIR
    try:
        return load_recorder(run_id, base_path=Path(JSON_STORAGE_DIR))
    except Exception as e:
        logger.debug("[MEDIA-REF] load_recorder(%s) failed: %s", run_id, e)
        return None


def _upload_path(upload_id: str) -> Optional[Path]:
    from config import UPLOADS_TMP_DIR
    for ext in _UPLOAD_EXTS:
        candidate = Path(UPLOADS_TMP_DIR) / f"{upload_id}.{ext}"
        if candidate.exists():
            return candidate
    return None


def _from_run(run_id: str, kind: str, index: Optional[int], ref: str) -> Path:
    recorder = _load_recorder(run_id)
    if recorder is None:
        raise MediaRefError(f"no run record for '{run_id}' (ref: {ref})")
    entities = find_media_entities(recorder.metadata.get('entities', []), kind)
    if not entities:
        raise MediaRefError(f"run '{run_id}' recorded no {kind} output (ref: {ref})")
    i = -1 if index is None else int(index)
    if i < 0:
        i = len(entities) + i
    if i < 0 or i >= len(entities):
        raise MediaRefError(
            f"{kind} index {index} out of range for run '{run_id}' — {len(entities)} recorded"
        )
    # The verdict, asked here rather than at each caller: this resolver is what
    # Resona's vision channel, the image analysis and the chat's picture lookup
    # all go through, and none of them has an entity of its own to ask about.
    from my_app.services.pipeline_recorder import entity_cleared_for_delivery
    cleared, why = entity_cleared_for_delivery(entities[i], recorder.metadata)
    if not cleared:
        raise MediaRefError(
            f"run '{run_id}' {kind} {i} was withheld by the content check "
            f"({why}) (ref: {ref})"
        )
    path = Path(recorder.final_folder) / entities[i]['filename']
    if not path.exists():
        raise MediaRefError(f"recorded {kind} file is missing on disk: {path}")
    return path


def resolve_media_ref(ref: Union[str, Path, None], *, kind: str = 'image',
                      index: Optional[int] = None) -> Path:
    """Turn a media reference into a file path, or raise MediaRefError.

    Accepted, each as its own explicit branch:
      - an existing filesystem path (str or Path)
      - /api/media/<kind>/<run_id>[/<index>]
      - /api/media/uploads/<upload_id>
      - a bare upload_id or run_id

    An explicit `index` overrides the one carried in the URL. Nothing else is
    accepted — base64 is not a reference and is never inferred here.
    """
    if ref is None or (isinstance(ref, str) and not ref.strip()):
        raise MediaRefError("empty media reference")

    if isinstance(ref, Path):
        if ref.exists():
            return ref
        raise MediaRefError(f"path does not exist: {ref}")

    ref = ref.strip()

    if len(ref) <= _MAX_PATHLIKE_LEN and not ref.startswith('/api/'):
        try:
            candidate = Path(ref)
            if candidate.exists():
                return candidate
        except (OSError, ValueError):
            pass

    match = _MEDIA_URL_RE.match(ref)
    if match:
        url_index = match.group('index')
        return _from_run(
            match.group('run_id'),
            kind=match.group('kind'),
            index=index if index is not None else (int(url_index) if url_index is not None else None),
            ref=ref,
        )

    match = _UPLOAD_URL_RE.match(ref)
    if match:
        path = _upload_path(match.group('upload_id'))
        if path is not None:
            return path
        raise MediaRefError(f"no uploaded file for {ref}")

    if '/' not in ref and '\\' not in ref and len(ref) <= _MAX_PATHLIKE_LEN:
        path = _upload_path(ref)
        if path is not None:
            return path
        return _from_run(ref, kind=kind, index=index, ref=ref)

    raise MediaRefError(f"unresolvable media reference: {ref[:160]!r}")


def normalize_image(path: Union[str, Path], *, max_size: int = IMAGE_MAX_SIZE,
                    min_size: int = IMAGE_MIN_SIZE):
    """Open an image and bring it into the VLM runner's envelope.

    Returns (image, original_size). The one implementation of the resize +
    RGB-flatten step that vlm_safety documents as crash-preventing; callers that
    audit what they sent (safety log) get the original size back instead of
    keeping their own copy of this code.
    """
    path = Path(path)
    try:
        img = Image.open(path)
    except Exception as e:
        raise MediaRefError(f"could not read image {path}: {e}") from e
    original_size = img.size
    if min(img.size) < min_size:
        scale = min_size / min(img.size)
        img = img.resize(
            (max(min_size, int(img.width * scale)), max(min_size, int(img.height * scale))),
            Image.LANCZOS,
        )
        logger.warning("[MEDIA-REF] upscaled undersized image %s: %s -> %s",
                       path.name, original_size, img.size)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    if img.mode not in ('RGB', 'L'):
        if img.mode == 'RGBA' or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img.convert('RGBA'), mask=img.convert('RGBA').split()[-1])
            img = background
        else:
            img = img.convert('RGB')
    return img, original_size


def image_to_b64(img) -> str:
    """A normalised PIL image as the base64 JPEG the vision channel expects."""
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=80)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def encode_image_b64(path: Union[str, Path], *, normalize: bool = True,
                     max_size: int = IMAGE_MAX_SIZE, min_size: int = IMAGE_MIN_SIZE) -> str:
    """Read an image file as base64 for the vision channel."""
    path = Path(path)
    if not normalize:
        try:
            return base64.b64encode(path.read_bytes()).decode('ascii')
        except OSError as e:
            raise MediaRefError(f"could not read image {path}: {e}") from e
    try:
        img, _ = normalize_image(path, max_size=max_size, min_size=min_size)
        return image_to_b64(img)
    except MediaRefError:
        raise
    except Exception as e:
        raise MediaRefError(f"could not read image {path}: {e}") from e


def load_image_b64(ref: Union[str, Path, None], *, index: Optional[int] = None,
                   normalize: bool = True) -> str:
    """resolve_media_ref + encode_image_b64 — what a vision consumer wants."""
    return encode_image_b64(resolve_media_ref(ref, kind='image', index=index),
                            normalize=normalize)


def strip_data_url(value: str) -> str:
    """`data:image/png;base64,AAA` -> `AAA`. For call sites that genuinely hold
    base64 and must not be confused with the reference branches above."""
    if value and value.startswith('data:') and ',' in value:
        return value.split(',', 1)[1]
    return value
