"""
Miniatures of stored media - built once, cached, served small.

A stored output is the full render: a picture measured 1328 px wide for a plate
that stands 100 px on screen, megabytes per row. TWO surfaces show such media
small - the research-data table of the settings area and the favourites strip at
the foot of every page - and both would otherwise pull the whole file for every
row. This module is the ONE place that makes the small copy; a second
implementation of it would be a bug (docs/ELEMENT_STRUCTURE_REGISTRY.md, rule
13). It lived in `routes/settings_routes.py` until 2026-08-25, when the strip
needed it too.

The cache lies under `exports/.thumbnails` (gitignored, verified with
`git check-ignore`) and is keyed by the caller: an export keys by run, a media
route keys by run and index, so two pictures of one run cannot overwrite each
other's miniature.
"""
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

#: The miniature a strip of small plates needs — the favourites strip shows
#: each at 100 px, the research-data table smaller still.
THUMBNAIL_PX = 160
#: The miniature a CARD needs. A runs strip is where two runs are held against
#: each other, its cards start at 240 px and can be dragged wider, and what is
#: being compared can be a heat map whose colour edges are the whole finding —
#: a 160 px copy blown up to card size would take exactly that away. Sizes are
#: a fixed set rather than a free number so the cache cannot be filled by asking
#: for a thousand of them.
THUMBNAIL_PX_CARD = 512
THUMBNAIL_SIZES = (THUMBNAIL_PX, THUMBNAIL_PX_CARD)
THUMBNAIL_JPEG_QUALITY = 80
#: Raised whenever the miniature is BUILT differently — it is part of the cache
#: name. The freshness check compares a copy against its source, and a source
#: that has not changed keeps its copy forever; a better encoder would then
#: reach only media made after it. Entries under an earlier number are simply
#: never asked for again.
#:   2 — no chroma subsampling, and the AI-origin marking carried over.
THUMBNAIL_BUILD = 2
THUMBNAIL_CACHE_DIR = config.EXPORTS_DIR / ".thumbnails"

# Videos need a decoder to yield a still frame. Where ffmpeg is absent the
# caller simply reports no thumbnail, rather than showing a broken image.
FFMPEG_BINARY = shutil.which('ffmpeg')


def _suffix(px: int) -> str:
    """What tells one cached miniature of a source from another: its size and
    the way it was built."""
    return f'_{px}_b{THUMBNAIL_BUILD}'


def can_build_thumbnail(kind: Optional[str]) -> bool:
    """Whether this server can produce a miniature for that kind of media."""
    if kind == 'image':
        return True
    if kind == 'video':
        return FFMPEG_BINARY is not None
    return False


#: The file formats that can say they are turned. A picture this platform
#: generates cannot, but one somebody uploaded from a phone can.
_ORIENTED_FORMATS = ('JPEG', 'MPO', 'TIFF', 'WEBP', 'HEIF', 'AVIF')


def source_size(source: Path) -> Optional[tuple]:
    """How large a browser will lay this picture out, or None where it cannot
    be read.

    The header only - Pillow does not decode a file to answer `size` - and
    turned the way the file says it is turned: a browser applies the EXIF
    orientation by itself (`image-orientation: from-image` is its default), so
    a picture written sideways is laid out sideways and the measurements have
    to say so.

    None on ANY failure, and that is the point: this is what a surface uses to
    hold a place open, never what it uses to decide something. A picture that
    cannot be measured is still served.
    """
    try:
        from PIL import Image
        with Image.open(source) as img:
            width, height = img.size
            orientation = None
            # ONLY where a file can carry an orientation at all. Pillow answers
            # `getexif()` for a PNG by DECODING it (the marking sits in a chunk
            # among the others), which turns a header read of 0.02 ms into 22 ms
            # - measured over the 74 pictures of this server's strip: 1.2 ms all
            # together against 1.6 seconds.
            if img.format in _ORIENTED_FORMATS:
                try:
                    orientation = img.getexif().get(0x0112)
                except Exception:
                    orientation = None
        if orientation in (5, 6, 7, 8):
            width, height = height, width
        return int(width), int(height)
    except Exception:
        logger.debug("[THUMBS] Could not measure %s", source, exc_info=True)
        return None


def build_thumbnail(source: Path, target: Path, kind: str, px: int = THUMBNAIL_PX) -> bool:
    """
    Write a JPEG miniature of `source` to `target`. Returns False on failure.

    The write is atomic: two requests racing for the same cold cache entry
    cannot serve each other a half-written file.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.jpg.%d.tmp' % os.getpid())
    try:
        if kind == 'image':
            from PIL import Image, ImageOps
            from my_app.services.watermark_service import carry_disclosure_jpeg_kwargs
            with Image.open(source) as img:
                # The AI-origin disclosure the platform wrote into the stored
                # file (EU AI Act Art. 50) lives in that file's own metadata,
                # and re-encoding drops it. A miniature is a copy of a produced
                # medium like any other, so it carries the marking on — read off
                # the source before anything is done to it, the same way the
                # upload path does it (routes/media_routes.py).
                carried = carry_disclosure_jpeg_kwargs(dict(img.info or {}))
                img = ImageOps.exif_transpose(img)
                img.thumbnail((px, px), Image.LANCZOS)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                img.save(tmp, 'JPEG', quality=THUMBNAIL_JPEG_QUALITY,
                         optimize=True, subsampling=0, **carried)
        elif kind == 'video':
            if FFMPEG_BINARY is None:
                return False
            result = subprocess.run(
                [FFMPEG_BINARY, '-y', '-loglevel', 'error',
                 '-i', str(source), '-frames:v', '1',
                 '-vf', 'scale=%d:%d:force_original_aspect_ratio=decrease' % (px, px),
                 '-f', 'image2', str(tmp)],
                capture_output=True,
            )
            if result.returncode != 0 or not tmp.exists():
                logger.warning("[THUMBS] ffmpeg could not read a frame from %s: %s",
                               source.name, result.stderr.decode('utf-8', 'replace')[:200])
                return False
        else:
            return False
        os.replace(str(tmp), str(target))
        return True
    except Exception as e:
        logger.warning("[THUMBS] Thumbnail for %s failed: %s", source.name, e)
        return False
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def cached_thumbnail(source: Path, kind: str, key: str, px: int = THUMBNAIL_PX) -> Optional[Path]:
    """
    The miniature of `source`, built if the cache has none that is at least as
    new as its source. Returns None where none can be made - the caller decides
    what to answer with, because a table and a strip answer differently.

    `px` is the longest side. Each size is cached under its own name, so the
    strip's small plate and the card's larger one never overwrite each other.
    """
    if not can_build_thumbnail(kind):
        return None
    if px not in THUMBNAIL_SIZES:
        px = THUMBNAIL_PX
    try:
        if not source.exists():
            return None
        target = THUMBNAIL_CACHE_DIR / (re.sub(r'[^A-Za-z0-9_.-]', '_', key) + _suffix(px) + '.jpg')
        if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
            return target
        return target if build_thumbnail(source, target, kind, px) else None
    except OSError as e:
        logger.warning("[THUMBS] Cache for %s unreachable: %s", key, e)
        return None


def drop_cached(key: str) -> None:
    """Forget every miniature made from one source, in all sizes.

    The freshness check compares modification times, and a thumbnail begun
    before its source was rewritten can land after it — then the cache holds a
    picture older than its source while claiming to be newer, and the route
    answers it as `immutable` for a year. A source that is REPLACED (a Latent
    Lab plate set again) says so here instead of relying on that comparison.
    """
    stem = re.sub(r'[^A-Za-z0-9_.-]', '_', key)
    for px in THUMBNAIL_SIZES:
        try:
            (THUMBNAIL_CACHE_DIR / (stem + _suffix(px) + '.jpg')).unlink()
        except OSError:
            pass
