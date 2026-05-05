"""
WatermarkService — AI-Origin Disclosure (EU AI Act Art. 50)

Adds machine-readable AI-origin metadata (mandatory layer) and an optional
visible mark to generated images and videos. Vendor-neutral by design: this
service does not embed an "AI4ArtsEd" or any other provider brand. Operators
configure visible text via user_settings.json if they want one.

Settings live in `config.WATERMARK` (dict). Metadata embedding is the
compliance core; visible overlay is optional. Failure of either layer is
fail-open: original bytes are returned with a WARNING log so the workshop is
never blocked by watermark issues.

History: A previous attempt (Session 118, January 2026) was reverted due to
sudo-pip install side effects and module-level config import problems. This
implementation avoids both: dependencies (Pillow, ffmpeg) are already part of
the standard stack, and config access happens lazily inside methods.
"""

import io
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# XMP iptcExt:DigitalSourceType controlled vocabulary value for AI-generated
# content (IPTC + ISO 22144). This is the machine-readable marker that EU AI
# Act Art. 50 effectively codifies.
DIGITAL_SOURCE_TYPE_AI = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)

_VIDEO_TYPES = {"output_video"}
_IMAGE_TYPES = {"output_image"}


def _get_settings() -> Dict[str, Any]:
    """Load WATERMARK settings dict lazily (avoid module-load-time import)."""
    try:
        import config  # type: ignore
    except Exception as e:
        logger.warning(f"[WATERMARK] config not importable ({e}); watermark disabled")
        return {}
    return getattr(config, "WATERMARK", {}) or {}


def _build_description(entity_metadata: Dict[str, Any], settings: Dict[str, Any]) -> str:
    """Compose a human + machine readable description string."""
    parts = ["AI-generated"]
    if settings.get("metadata_include_model", True):
        model = entity_metadata.get("model") or entity_metadata.get("model_name")
        if model:
            parts.append(f"model={model}")
    if settings.get("metadata_include_date", True):
        parts.append(f"date={datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    if settings.get("metadata_include_seed", False):
        seed = entity_metadata.get("seed")
        if seed is not None:
            parts.append(f"seed={seed}")
    if settings.get("metadata_include_prompt", False):
        prompt = entity_metadata.get("prompt") or entity_metadata.get("prompt_text")
        if prompt:
            parts.append(f"prompt={prompt[:300]}")
    return ", ".join(parts)


def _xmp_packet(software_name: str, description: str) -> str:
    """Minimal XMP packet with iptcExt:DigitalSourceType and dc:description.

    Survives PNG iTXt (Pillow stores it under key 'XML:com.adobe.xmp') and is
    extractable by exiftool, Adobe tools, and any XMP-aware reader.
    """
    sw = software_name or ""
    return f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:xmp="http://ns.adobe.com/xap/1.0/"
   xmlns:iptcExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/">
   <iptcExt:DigitalSourceType>{DIGITAL_SOURCE_TYPE_AI}</iptcExt:DigitalSourceType>
   <xmp:CreatorTool>{sw}</xmp:CreatorTool>
   <xmp:CreateDate>{datetime.now(timezone.utc).isoformat(timespec='seconds')}</xmp:CreateDate>
   <dc:description>
    <rdf:Alt><rdf:li xml:lang="x-default">{description}</rdf:li></rdf:Alt>
   </dc:description>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def _draw_visible_image(img, settings: Dict[str, Any]):
    """Draw a configurable text mark on a Pillow Image (modifies in place)."""
    from PIL import Image as _Image, ImageDraw, ImageFont  # lazy

    text = settings.get("visible_text", "AI-generated") or "AI-generated"
    position = settings.get("visible_position", "bottom-right")
    opacity = float(settings.get("visible_opacity", 0.3))
    opacity = max(0.0, min(1.0, opacity))

    if img.mode != "RGBA":
        img_rgba = img.convert("RGBA")
    else:
        img_rgba = img

    overlay = _Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Font size ~ 2.5% of width, min 14px
    font_size = max(14, int(img_rgba.width * 0.025))
    font = None
    for candidate in [
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if Path(candidate).exists():
            try:
                font = ImageFont.truetype(candidate, font_size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(6, font_size // 3)

    if position == "top-left":
        x, y = pad, pad
    elif position == "top-right":
        x, y = img_rgba.width - tw - pad, pad
    elif position == "bottom-left":
        x, y = pad, img_rgba.height - th - pad * 2
    else:  # bottom-right (default)
        x, y = img_rgba.width - tw - pad, img_rgba.height - th - pad * 2

    a = int(255 * opacity)
    # Black outline for legibility on any background
    outline = max(1, font_size // 12)
    for dx in range(-outline, outline + 1):
        for dy in range(-outline, outline + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, a))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, a))

    img_rgba.alpha_composite(overlay)
    return img_rgba


def watermark_image_bytes(content: bytes, entity_metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Apply metadata (mandatory) and optionally visible (configurable) watermark to image bytes.

    Returns watermarked bytes on success, original bytes on any failure. Never raises.
    """
    settings = _get_settings()
    if not settings:
        return content

    apply_metadata = bool(settings.get("metadata_image", True))
    apply_visible = bool(settings.get("visible_image", False))
    if not (apply_metadata or apply_visible):
        return content

    try:
        from PIL import Image, PngImagePlugin  # lazy
    except Exception as e:
        logger.warning(f"[WATERMARK] Pillow not available ({e}); skipping image watermark")
        return content

    try:
        img = Image.open(io.BytesIO(content))
        img.load()
    except Exception as e:
        logger.warning(f"[WATERMARK] cannot decode image ({e}); skipping")
        return content

    fmt = (img.format or "PNG").upper()
    entity_metadata = entity_metadata or {}
    description = _build_description(entity_metadata, settings)
    software = settings.get("software_name", "") or ""

    try:
        if apply_visible:
            img = _draw_visible_image(img, settings)
            # Ensure we save in a mode the format supports
            if fmt == "JPEG" and img.mode == "RGBA":
                img = img.convert("RGB")

        out = io.BytesIO()
        if fmt == "PNG":
            pnginfo = PngImagePlugin.PngInfo()
            if apply_metadata:
                pnginfo.add_itxt("XML:com.adobe.xmp", _xmp_packet(software, description))
                pnginfo.add_text("Software", software or "AI4ArtsEd-platform")
                pnginfo.add_text("Description", description)
                pnginfo.add_text("DigitalSourceType", DIGITAL_SOURCE_TYPE_AI)
            img.save(out, format="PNG", pnginfo=pnginfo, optimize=False)
        elif fmt in ("JPEG", "JPG"):
            # JPEG: piexif optional; if missing we still write the file, just without EXIF
            save_kwargs: Dict[str, Any] = {"format": "JPEG", "quality": 95}
            if apply_metadata:
                try:
                    import piexif  # type: ignore
                    exif_dict = {
                        "0th": {
                            piexif.ImageIFD.Software: (software or "AI4ArtsEd-platform").encode("utf-8"),
                            piexif.ImageIFD.ImageDescription: description.encode("utf-8"),
                            piexif.ImageIFD.XMLPacket: _xmp_packet(software, description).encode("utf-8"),
                        },
                        "Exif": {
                            piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime("%Y:%m:%d %H:%M:%S").encode("utf-8"),
                        },
                    }
                    save_kwargs["exif"] = piexif.dump(exif_dict)
                except ImportError:
                    logger.info("[WATERMARK] piexif not installed; JPEG saved without EXIF metadata")
            img.save(out, **save_kwargs)
        else:
            # Unknown format: re-save losslessly to preserve image (no metadata embed)
            img.save(out, format=fmt)
            logger.info(f"[WATERMARK] format={fmt} not metadata-supported; only visible layer applied")

        return out.getvalue()
    except Exception as e:
        logger.warning(f"[WATERMARK] image watermark failed ({e}); returning original bytes")
        return content


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def watermark_video_bytes(content: bytes, entity_metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Apply container metadata (mandatory) and optionally visible drawtext to video bytes.

    Uses ffmpeg subprocess. Falls back to original bytes on any failure.
    """
    settings = _get_settings()
    if not settings:
        return content

    apply_metadata = bool(settings.get("metadata_video", True))
    apply_visible = bool(settings.get("visible_video", False))
    if not (apply_metadata or apply_visible):
        return content

    if not _ffmpeg_available():
        logger.warning("[WATERMARK] ffmpeg not found in PATH; skipping video watermark")
        return content

    entity_metadata = entity_metadata or {}
    description = _build_description(entity_metadata, settings)
    software = settings.get("software_name", "") or "AI4ArtsEd-platform"

    tmpdir = Path(tempfile.mkdtemp(prefix="watermark_"))
    in_path = tmpdir / "input.mp4"
    out_path = tmpdir / "output.mp4"
    try:
        in_path.write_bytes(content)

        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(in_path)]

        if apply_visible:
            text = settings.get("visible_text", "AI-generated") or "AI-generated"
            position = settings.get("visible_position", "bottom-right")
            opacity = float(settings.get("visible_opacity", 0.3))
            opacity = max(0.0, min(1.0, opacity))
            # ffmpeg drawtext: position-dependent x/y expressions
            position_expr = {
                "top-left": "x=10:y=10",
                "top-right": "x=w-tw-10:y=10",
                "bottom-left": "x=10:y=h-th-10",
                "bottom-right": "x=w-tw-10:y=h-th-10",
            }.get(position, "x=w-tw-10:y=h-th-10")
            # Escape single quotes/colons in text for drawtext
            safe_text = text.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
            drawtext = (
                f"drawtext=text='{safe_text}':"
                f"fontcolor=white@{opacity}:fontsize=h*0.04:"
                f"box=1:boxcolor=black@{opacity * 0.6}:boxborderw=6:"
                f"{position_expr}"
            )
            cmd += ["-vf", drawtext, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy"]
        else:
            # Pure metadata path: no re-encode, lossless
            cmd += ["-c", "copy"]

        if apply_metadata:
            cmd += [
                "-metadata", f"creation_time={datetime.now(timezone.utc).isoformat(timespec='seconds')}",
                "-metadata", f"description={description}",
                "-metadata", f"comment={description}",
                "-metadata", f"encoder={software}",
                "-metadata", f"DigitalSourceType={DIGITAL_SOURCE_TYPE_AI}",
            ]

        cmd.append(str(out_path))

        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            logger.warning(
                f"[WATERMARK] ffmpeg failed (rc={result.returncode}): "
                f"{result.stderr.decode('utf-8', errors='replace')[:400]}"
            )
            return content

        return out_path.read_bytes()
    except subprocess.TimeoutExpired:
        logger.warning("[WATERMARK] ffmpeg timed out; returning original video bytes")
        return content
    except Exception as e:
        logger.warning(f"[WATERMARK] video watermark failed ({e}); returning original bytes")
        return content
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def watermark_media_bytes(
    content: bytes,
    entity_type: str,
    entity_metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Dispatcher: watermark image or video bytes based on entity_type.

    Other entity types pass through unchanged. Never raises.
    """
    if not isinstance(content, bytes):
        return content
    if entity_type in _IMAGE_TYPES:
        return watermark_image_bytes(content, entity_metadata)
    if entity_type in _VIDEO_TYPES:
        return watermark_video_bytes(content, entity_metadata)
    return content
