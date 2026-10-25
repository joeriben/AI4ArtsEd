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

History: A previous attempt was reverted due to
sudo-pip install side effects and module-level config import problems. This
implementation avoids both: dependencies (Pillow, ffmpeg) are already part of
the standard stack, and config access happens lazily inside methods.
"""

import base64
import io
import json
import logging
import re
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

# Fallback map, used only when the bytes themselves say nothing. The content
# sniffer decides first — see watermark_media_bytes.
_VIDEO_TYPES = {"output_video", "output_composition"}  # PP composition (still+sound mp4) gets the mp4-container AI-origin disclosure
_IMAGE_TYPES = {"output_image", "output_image_composite", "output_image_comparison"}
_AUDIO_TYPES = {"output_audio", "output_music"}
# Sketches the run hands back as its medium. Everything else that is text —
# prompts, readings, workflows — must stay untouched.
_CODE_TYPES = {
    "p5", "tonejs", "sonicpi",
    "output_p5", "output_tonejs", "output_sonicpi", "output_code",
}
# What a PERSON brought in. A photograph someone uploaded and a voice someone
# recorded are not AI-generated, and marking them as such would be a false
# statement — the one thing this whole service exists to prevent. The names
# are checked, not the bytes: only the name knows where a file came from.
_NEVER_MARK_PREFIXES = ("input", "upload", "source_", "recording", "user_")


def _is_user_material(entity_type: str) -> bool:
    name = (entity_type or "").strip().lower()
    return name.startswith(_NEVER_MARK_PREFIXES) or "upload" in name


def _get_settings() -> Dict[str, Any]:
    """Load WATERMARK settings dict lazily (avoid module-load-time import)."""
    try:
        import config  # type: ignore
    except Exception as e:
        logger.warning(f"[WATERMARK] config not importable ({e}); watermark disabled")
        return {}
    return getattr(config, "WATERMARK", {}) or {}


# The same vocabulary holds a second value, and the difference is factual:
# `algorithmicMedia` names media a pure algorithm produced with NO sampled
# training data. eSpeak NG is exactly that — formant synthesis out of rules,
# nothing trained, nobody recorded (see the chunk's own docstring). Stamping it
# "trained" would be a false statement about how it came about, in the one
# field that exists to keep such statements true.
DIGITAL_SOURCE_TYPE_ALGORITHMIC = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/algorithmicMedia"
)

_KNOWN_SOURCE_TYPES = (DIGITAL_SOURCE_TYPE_AI, DIGITAL_SOURCE_TYPE_ALGORITHMIC)


def _source_type(entity_metadata: Optional[Dict[str, Any]]) -> str:
    """Which of the two values this medium has earned.

    A caller that knows better says so with `digital_source_type`; anything
    unrecognised falls back to the trained value, which is the safer claim to
    over-state.
    """
    value = (entity_metadata or {}).get("digital_source_type") or ""
    return value if value in _KNOWN_SOURCE_TYPES else DIGITAL_SOURCE_TYPE_AI


def _xml_text(value: Any) -> str:
    """Escape text on its way into an XMP packet or an SVG.

    A prompt reading `Tom & Jerry` — and `metadata_include_prompt` is a shipped
    setting — made the packet malformed XML; inside an SVG, where the packet
    sits in the document itself, that means the drawing stops rendering.
    """
    from xml.sax.saxutils import escape  # stdlib, lazy

    return escape(str(value or ""))


def _build_description(entity_metadata: Dict[str, Any], settings: Dict[str, Any]) -> str:
    """Compose a human + machine readable description string."""
    trained = _source_type(entity_metadata) == DIGITAL_SOURCE_TYPE_AI
    parts = ["AI-generated" if trained else "Algorithmically generated"]
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


def _xmp_packet(
    software_name: str,
    description: str,
    wrapped: bool = True,
    source_type: str = DIGITAL_SOURCE_TYPE_AI,
) -> str:
    """Minimal XMP packet with iptcExt:DigitalSourceType and dc:description.

    Survives PNG iTXt (Pillow stores it under key 'XML:com.adobe.xmp') and is
    extractable by exiftool, Adobe tools, and any XMP-aware reader.

    `wrapped=False` drops the xpacket processing instructions — that form goes
    INSIDE another XML document (SVG's <metadata>), where a stray PI has no
    business.
    """
    sw = _xml_text(software_name or "")
    description = _xml_text(description)
    head = '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n' if wrapped else ""
    tail = '\n<?xpacket end="w"?>' if wrapped else ""
    return head + f"""<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:xmp="http://ns.adobe.com/xap/1.0/"
   xmlns:iptcExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/">
   <iptcExt:DigitalSourceType>{source_type}</iptcExt:DigitalSourceType>
   <xmp:CreatorTool>{sw}</xmp:CreatorTool>
   <xmp:CreateDate>{datetime.now(timezone.utc).isoformat(timespec='seconds')}</xmp:CreateDate>
   <dc:description>
    <rdf:Alt><rdf:li xml:lang="x-default">{description}</rdf:li></rdf:Alt>
   </dc:description>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>""" + tail


def _apply_invisible_image(img, settings: Dict[str, Any]):
    """Embed a DWT-DCT invisible watermark into a Pillow Image.

    Opt-in via settings['invisible_image']. Survives JPEG re-encoding and
    moderate resizing, unlike pure metadata which strips on any container
    rewrite. Payload is a short fixed marker — the metadata layer carries the
    descriptive info; this layer is just "AI-generated, period".

    Returns a new Pillow Image. Falls back to the input image on any error.
    """
    try:
        import numpy as np  # lazy
        import cv2  # lazy
        from imwatermark import WatermarkEncoder  # lazy
        from PIL import Image as _Image  # lazy
    except Exception as e:
        logger.warning(f"[WATERMARK] invisible deps unavailable ({e}); skipping invisible layer")
        return img

    # DWT-DCT payload limit is small; keep it short and deployment-neutral.
    payload = (settings.get("invisible_payload") or "AI-generated")[:32]

    try:
        rgb = img.convert("RGB")
        arr = np.array(rgb)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        # imwatermark needs a minimum frame size for DWT decomposition;
        # very small images (<256px) get a no-op fall-through.
        h, w = bgr.shape[:2]
        if min(h, w) < 256:
            logger.info(f"[WATERMARK] image too small for invisible DWT-DCT ({w}x{h}); skipping")
            return img

        enc = WatermarkEncoder()
        enc.set_watermark("bytes", payload.encode("utf-8"))
        bgr_marked = enc.encode(bgr, "dwtDct")

        rgb_marked = cv2.cvtColor(bgr_marked, cv2.COLOR_BGR2RGB)
        return _Image.fromarray(rgb_marked)
    except Exception as e:
        logger.warning(f"[WATERMARK] invisible watermark failed ({e}); returning unmodified image")
        return img


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


_XMP_APP1_ID = b"http://ns.adobe.com/xap/1.0/\x00"
_EXIF_APP1_ID = b"Exif\x00\x00"


def _jpeg_with_app1(content: bytes, exif_payload: bytes, xmp_payload: bytes) -> Optional[bytes]:
    """Put the disclosure into a JPEG without re-encoding the picture.

    Pillow's `save()` always re-encodes, and a JPEG loses a little every time.
    That matters here more than usual: the denoising instrument hands back
    full-resolution JPEG steps and exists to let people study exactly that
    material. A JPEG is a marker stream — the two APP1 segments go in right
    after SOI (behind a JFIF APP0, if there is one) and the entropy-coded data
    is never read.

    Only the APP1 segments we write ourselves are replaced; a camera's own EXIF
    stays where it is. Returns None when the stream is not one we can safely
    edit — the caller then falls back to re-encoding.
    """
    if len(content) < 4 or content[:2] != b"\xff\xd8":
        return None

    off, head = 2, b""
    while off + 4 <= len(content):
        if content[off] != 0xFF:
            return None
        marker = content[off + 1]
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:  # standalone markers
            head += content[off:off + 2]
            off += 2
            continue
        length = int.from_bytes(content[off + 2:off + 4], "big")
        if length < 2 or off + 2 + length > len(content):
            return None
        segment = content[off:off + 2 + length]
        if marker == 0xE1 and segment[4:].startswith((_XMP_APP1_ID, _EXIF_APP1_ID)):
            off += 2 + length  # ours from an earlier pass: replaced, not stacked
            continue
        if marker in (0xE0, 0xE1):  # JFIF, or someone else's APP1
            head += segment
            off += 2 + length
            continue
        break

    segments = b""
    for payload in (exif_payload, xmp_payload):
        if not payload:
            continue
        if len(payload) + 2 > 0xFFFF:
            return None  # does not fit one segment; leave the file alone
        segments += b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    if not segments:
        return None
    return b"\xff\xd8" + head + segments + content[off:]


def watermark_image_bytes(content: bytes, entity_metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Apply metadata (mandatory) and optionally visible (configurable) watermark to image bytes.

    Returns watermarked bytes on success, original bytes on any failure. Never raises.
    """
    settings = _get_settings()
    if not settings:
        return content

    apply_metadata = bool(settings.get("metadata_image", True))
    apply_visible = bool(settings.get("visible_image", False))
    apply_invisible = bool(settings.get("invisible_image", False))
    if not (apply_metadata or apply_visible or apply_invisible):
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

    frames = int(getattr(img, "n_frames", 1) or 1)
    source_type = _source_type(entity_metadata)

    if not (apply_visible or apply_invisible):
        # Already marked: doing it again costs time and says nothing more. A
        # picture now passes this way twice — once where the result is
        # assembled, once where it is written down.
        #
        # The comparison is EXACT. A photograph correctly marked
        # `digitalCapture` by a camera-aware tool is not an AI-marked file, and
        # reading any non-empty value as "already done" would leave it
        # unmarked while we went on claiming it was marked. A packet that
        # merely mentions the URI somewhere — in a caption, in a history entry —
        # is not a disclosure either.
        info = img.info or {}
        already = _as_text(info.get("DigitalSourceType")) == source_type
        if not already:
            packet = info.get("XML:com.adobe.xmp") or info.get("xmp") or ""
            if isinstance(packet, bytes):
                packet = packet.decode("utf-8", errors="replace")
            already = _xmp_element(packet, "iptcExt:DigitalSourceType") == source_type
        if already:
            return content

    fmt = (img.format or "PNG").upper()
    entity_metadata = entity_metadata or {}
    description = _build_description(entity_metadata, settings)
    software = settings.get("software_name", "") or ""

    if frames > 1:
        # An animated picture is not ours to flatten. Pillow's save() writes
        # frame one and drops the rest, so a marked 8-frame GIF came back as a
        # still — the mark would cost the animation.
        logger.info(f"[WATERMARK] {fmt} has {frames} frames; leaving it untouched")
        return content

    try:
        if apply_invisible:
            img = _apply_invisible_image(img, settings)
        if apply_visible:
            img = _draw_visible_image(img, settings)
            # Ensure we save in a mode the format supports
            if fmt == "JPEG" and img.mode == "RGBA":
                img = img.convert("RGB")

        out = io.BytesIO()
        if fmt == "PNG":
            pnginfo = PngImagePlugin.PngInfo()
            if apply_metadata:
                pnginfo.add_itxt(
                    "XML:com.adobe.xmp",
                    _xmp_packet(software, description, source_type=source_type),
                )
                pnginfo.add_text("Software", software or "AI4ArtsEd-platform")
                pnginfo.add_text("Description", description)
                pnginfo.add_text("DigitalSourceType", source_type)
            img.save(out, format="PNG", pnginfo=pnginfo, optimize=False)
        elif fmt in ("JPEG", "JPG"):
            packet = _xmp_packet(software, description, source_type=source_type)
            exif = Image.Exif()
            exif[0x0131] = software or "AI4ArtsEd-platform"  # Software
            exif[0x010E] = description  # ImageDescription

            if apply_metadata and not (apply_visible or apply_invisible):
                # Nothing touched the pixels, so nothing needs re-encoding.
                spliced = _jpeg_with_app1(
                    content,
                    _EXIF_APP1_ID + exif.tobytes(),
                    _XMP_APP1_ID + packet.encode("utf-8"),
                )
                if spliced is not None:
                    return spliced

            save_kwargs: Dict[str, Any] = {"format": "JPEG", "quality": 95}
            if apply_metadata:
                save_kwargs["exif"] = exif
                save_kwargs["xmp"] = packet.encode("utf-8")
            img.save(out, **save_kwargs)
        elif fmt == "WEBP":
            save_kwargs = {"format": "WEBP", "lossless": True, "quality": 100}
            if apply_metadata:
                save_kwargs["xmp"] = _xmp_packet(
                    software, description, source_type=source_type
                ).encode("utf-8")
            img.save(out, **save_kwargs)
        else:
            # A format with no slot for the disclosure. Re-saving it costs more
            # than it buys — a GIF came back smaller and still unmarked — so
            # unless a layer has to be DRAWN, the bytes go back untouched.
            if not (apply_visible or apply_invisible):
                logger.info(f"[WATERMARK] format={fmt} has no metadata slot; left untouched")
                return content
            img.save(out, format=fmt)
            logger.info(f"[WATERMARK] format={fmt} not metadata-supported; only visible layer applied")

        return out.getvalue()
    except Exception as e:
        logger.warning(f"[WATERMARK] image watermark failed ({e}); returning original bytes")
        return content


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _container_already_marked(content: bytes, source_type: str) -> bool:
    """Is THIS disclosure already in the container?

    Container tags are stored as plain text, so the URI is literally in the
    bytes when it is there. Instant, against a remux that costs ~90 ms — and
    video and audio pass the marking twice per run, once where the result is
    assembled and once where it is written down.

    The comparison is against the value we are about to write, not against any
    known value. A caller further along knows things the executor could not:
    the executor stamps the safe default on a sound it knows nothing about, and
    the speech route then knows it came out of eSpeak. Reading "some marking is
    there" as "nothing left to do" would freeze the first, less informed answer.
    """
    return source_type.encode("utf-8") in content


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
    if not apply_visible and _container_already_marked(content, _source_type(entity_metadata)):
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
                # Without this the mov/mp4 muxer silently drops every key it does
                # not know -- which is exactly the one that carries the controlled
                # vocabulary. Read back, such a file showed only the plain-text
                # line (standard: "text"). With the flag the key travels in the
                # udta box and comes back as iptcExt's own value.
                "-movflags", "use_metadata_tags",
                "-metadata", f"creation_time={datetime.now(timezone.utc).isoformat(timespec='seconds')}",
                "-metadata", f"description={description}",
                "-metadata", f"comment={description}",
                "-metadata", f"encoder={software}",
                "-metadata", f"DigitalSourceType={_source_type(entity_metadata)}",
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


def _detect_audio_format(content: bytes) -> Optional[str]:
    """Detect audio container format from magic bytes. Returns extension or None."""
    if len(content) < 12:
        return None
    if content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "wav"
    if content[:3] == b"ID3" or content[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if content[:4] == b"fLaC":
        return "flac"
    if content[:4] == b"OggS":
        return "ogg"
    if content[4:8] == b"ftyp":
        return "m4a"
    return None


def _riff_chunks(content: bytes):
    """Walk a RIFF file's top-level chunks. None when it does not walk cleanly.

    Returns [(id, start_of_header, end_of_data)] and guarantees the walk ended
    exactly at the end of the file — anything else means we have misread the
    structure, and a file we have misread is one we must not rewrite.
    """
    import struct

    if len(content) < 12 or content[:4] != b"RIFF":
        return None
    off, chunks = 12, []
    while off + 8 <= len(content):
        cid = content[off:off + 4]
        length = struct.unpack_from("<I", content, off + 4)[0]
        end = off + 8 + length
        if end > len(content):
            return None
        chunks.append((cid, off, end))
        off = end + (length % 2)  # RIFF pads odd chunks to a word boundary
    return chunks if off == len(content) else None


def _riff_xmp_bytes(
    content: bytes,
    software: str,
    description: str,
    source_type: str = DIGITAL_SOURCE_TYPE_AI,
) -> bytes:
    """Put the XMP packet into the WAV's own _PMX chunk.

    A WAV keeps its tags in RIFF INFO fields, and that set is fixed: the muxer
    silently drops iptcExt:DigitalSourceType, so sound left the house carrying
    the plain description while every picture carried the controlled
    vocabulary. The XMP specification names the carrier for RIFF — a top-level
    chunk with the ID `_PMX`, holding the UTF-8 packet. (The letters are
    reversed; that is in the specification, from a byte-order bug in the first
    implementation.)

    Readers skip chunks they do not know, so nothing about the sound changes.
    Fail-open: original bytes whenever the file does not walk cleanly.
    """
    import struct

    chunks = _riff_chunks(content)
    if chunks is None or content[8:12] != b"WAVE":
        return content

    packet = _xmp_packet(software, description, source_type=source_type).encode("utf-8")
    chunk = b"_PMX" + struct.pack("<I", len(packet)) + packet
    if len(packet) % 2:
        chunk += b"\x00"

    existing = [c for c in chunks if c[0] == b"_PMX"]
    if existing:
        _cid, start, end = existing[0]
        end += (end - start - 8) % 2  # skip the pad byte too
        body = content[12:start] + chunk + content[end:]
    else:
        body = content[12:] + chunk
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def _riff_xmp_text(content: bytes) -> str:
    """The XMP packet out of a RIFF _PMX chunk, or an empty string."""
    chunks = _riff_chunks(content) or []
    for cid, start, end in chunks:
        if cid == b"_PMX":
            return content[start + 8:end].decode("utf-8", errors="replace")
    return ""


def watermark_audio_bytes(content: bytes, entity_metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Apply container metadata to audio bytes via ffmpeg subprocess.

    Lossless: uses -c copy, no re-encode. Supports WAV/MP3/FLAC/OGG/M4A.
    Fail-open: returns original bytes on any failure. Never raises.
    """
    settings = _get_settings()
    if not settings:
        return content
    if not bool(settings.get("metadata_audio", True)):
        return content
    if not _ffmpeg_available():
        logger.warning("[WATERMARK] ffmpeg not found in PATH; skipping audio watermark")
        return content
    if _container_already_marked(content, _source_type(entity_metadata)):
        return content

    fmt = _detect_audio_format(content)
    if fmt is None:
        logger.warning("[WATERMARK] could not detect audio format; skipping")
        return content

    entity_metadata = entity_metadata or {}
    description = _build_description(entity_metadata, settings)
    software = settings.get("software_name", "") or "AI4ArtsEd-platform"

    tmpdir = Path(tempfile.mkdtemp(prefix="watermark_audio_"))
    in_path = tmpdir / f"input.{fmt}"
    out_path = tmpdir / f"output.{fmt}"
    try:
        in_path.write_bytes(content)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(in_path),
            "-c", "copy",
        ]
        if fmt == "m4a":
            cmd += ["-movflags", "use_metadata_tags"]  # same mp4 muxer, same trap
        cmd += [
            "-metadata", f"description={description}",
            "-metadata", f"comment={description}",
            "-metadata", f"encoded_by={software}",
            "-metadata", f"DigitalSourceType={_source_type(entity_metadata)}",
            "-metadata", f"creation_time={datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            logger.warning(
                f"[WATERMARK] ffmpeg audio failed (rc={result.returncode}): "
                f"{result.stderr.decode('utf-8', errors='replace')[:400]}"
            )
            return content
        marked = out_path.read_bytes()
        if fmt == "wav":
            # RIFF INFO has no field for the controlled vocabulary; the packet
            # goes into the chunk the XMP specification provides for it.
            marked = _riff_xmp_bytes(
                marked, software, description, _source_type(entity_metadata)
            )
        return marked
    except subprocess.TimeoutExpired:
        logger.warning("[WATERMARK] ffmpeg audio timed out; returning original bytes")
        return content
    except Exception as e:
        logger.warning(f"[WATERMARK] audio watermark failed ({e}); returning original bytes")
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
    """Dispatcher: every medium this platform produces gets its marking.

    Routed by what the bytes ARE, with the entity's name only as the fallback.
    A name is not evidence about content, and the names have been wrong: files
    called output_image that are mp3, output_video that are PNG, and a whole
    class (output_image_composite, 157 of them) that no name list contained.

    Text passes through untouched unless the entity IS a piece of code that the
    run hands back as its medium — prompts, readings and JSON are not media.

    Never raises: whatever cannot be marked comes back as it went in.
    """
    if not isinstance(content, bytes):
        return content
    if _is_user_material(entity_type):
        return content

    kind = _sniff_media_kind(content)
    if kind == "image":
        return watermark_image_bytes(content, entity_metadata)
    if kind == "video":
        return watermark_video_bytes(content, entity_metadata)
    if kind == "audio":
        return watermark_audio_bytes(content, entity_metadata)
    if kind == "glb":
        return watermark_glb_bytes(content, entity_metadata)
    if kind == "svg":
        return watermark_svg_bytes(content, entity_metadata)
    if kind == "text":
        if entity_type in _CODE_TYPES:
            return watermark_code_bytes(content, entity_type, entity_metadata)
        return content

    # Unrecognised bytes: the name is all there is left to go on.
    if entity_type in _IMAGE_TYPES:
        return watermark_image_bytes(content, entity_metadata)
    if entity_type in _VIDEO_TYPES:
        return watermark_video_bytes(content, entity_metadata)
    if entity_type in _AUDIO_TYPES:
        return watermark_audio_bytes(content, entity_metadata)
    return content


# Media that travels back to the page as base64 inside a result's metadata.
# It is the same picture the recorder writes to disk — but the page hands THIS
# copy to whoever presses "download", so it has to carry the marking as well.
_B64_MEDIA_KEYS = (
    "image_data", "audio_data", "video_data", "mesh_data",
    "reference_image", "result_image",
    # What the two proxied workshops call their result. Not `image_base64`:
    # that name also carries the picture a user brought IN, and marking an
    # uploaded photograph as AI-generated would be a lie.
    "mosaic_base64", "audio_base64",
)


_B64_ALPHABET = re.compile(r"^[A-Za-z0-9+/=\s]+$")


def _mark_b64(value: Any, entity_type: str, entity_metadata: Dict[str, Any]) -> Any:
    """Mark one base64 payload. Anything that is not one comes back untouched.

    The payload does not always arrive bare. Every provider that answers through
    chat completions hands back a `data:image/png;base64,…` URI, and the caller
    downstream branches on that prefix — so it is stripped for the marking and
    put back afterwards, byte for byte. A strict decode rejected those outright,
    and the marking silently did not happen: the file on disk was marked while
    the copy the page downloaded was not.
    """
    if not isinstance(value, str) or len(value) < 32:
        return value

    prefix = ""
    payload = value
    if value.startswith("data:"):
        head, _, rest = value.partition(",")
        if not rest or "base64" not in head:
            return value
        prefix, payload = head + ",", rest

    # Tolerant decoding would happily turn a sentence into garbage bytes, so the
    # alphabet is checked first; line-wrapped payloads (MIME encoders) pass.
    if not _B64_ALPHABET.match(payload):
        return value
    try:
        raw = base64.b64decode(payload)
    except Exception:
        return value  # a URL, a path, a placeholder — not a payload
    if not raw:
        return value

    marked = watermark_media_bytes(raw, entity_type, entity_metadata)
    if marked is raw or marked == raw:
        return value
    return prefix + base64.b64encode(marked).decode("ascii")


def watermark_result_metadata(
    metadata: Optional[Dict[str, Any]],
    entity_metadata: Optional[Dict[str, Any]] = None,
    extra_keys: tuple = (),
) -> None:
    """Mark the base64 media a finished run carries back to the page, in place.

    The latent lab shows what it gets in this metadata and downloads exactly
    that — never the file on disk. Marking only at the recorder would leave
    every "download" button in the lab handing out an unmarked picture while
    the platform's own copy was properly marked.

    Never raises: a marking that fails leaves the payload as it was.
    """
    if not isinstance(metadata, dict):
        return
    entity_metadata = entity_metadata or {}
    named = {
        "audio_data": "output_audio",
        "video_data": "output_video",
        "mesh_data": "output_3d",
    }
    try:
        # extra_keys: names that are ambiguous in general but unambiguous where
        # the caller sits. `image_base64` is the fusion workbench's OUTPUT and
        # the upload path's INPUT — only the call site can tell which.
        for key in _B64_MEDIA_KEYS + tuple(extra_keys):
            if key in metadata:
                metadata[key] = _mark_b64(
                    metadata[key], named.get(key, "output_image"), entity_metadata
                )
        # The mosaic hands its tiles back in a dict keyed by row_col. They are
        # img2img outputs, and the review step shows every one of them.
        tiles = metadata.get("tiles")
        if isinstance(tiles, dict):
            for cell, payload in list(tiles.items()):
                tiles[cell] = _mark_b64(payload, "output_image", entity_metadata)

        # Denoising archaeology hands back the steps themselves; each one is a
        # picture someone can take home.
        steps = (metadata.get("archaeology_data") or {}).get("step_images")
        if isinstance(steps, list):
            for entry in steps:
                if isinstance(entry, dict) and "image_base64" in entry:
                    entry["image_base64"] = _mark_b64(
                        entry["image_base64"], "output_image", entity_metadata
                    )
    except Exception as e:
        logger.warning(f"[WATERMARK] result metadata marking failed ({e})")


# ---------------------------------------------------------------------------
# Reading back
#
# Art. 50 asks for the disclosure to travel WITH the medium. A record beside
# the file would therefore prove nothing: the only honest check opens the file
# that was delivered and looks for what watermark_media_bytes put in.
# ---------------------------------------------------------------------------

_READ_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
_READ_CONTAINER_SUFFIXES = {
    ".mp4", ".webm", ".mkv", ".mov", ".m4v",
    ".wav", ".mp3", ".flac", ".ogg", ".m4a",
}
_READ_GLB_SUFFIXES = {".glb"}
_READ_MARKUP_SUFFIXES = {".svg"}
_READ_CODE_SUFFIXES = {".js", ".mjs", ".rb"}


def _as_text(value: Any) -> str:
    """Metadata comes back as str, bytes or something else entirely."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\x00").strip()
    return str(value).strip()


def _xmp_element(xmp: str, tag: str) -> str:
    """The text of one XMP element.

    Deliberately small: what we read back are the packets _xmp_packet wrote,
    not arbitrary XMP from the wild.
    """
    open_t, close_t = "<%s>" % tag, "</%s>" % tag
    i = xmp.find(open_t)
    if i < 0:
        return ""
    j = xmp.find(close_t, i)
    if j < 0:
        return ""
    return xmp[i + len(open_t):j].strip()


def _xmp_alt_text(xmp: str) -> str:
    """The single rdf:li our dc:description carries."""
    i = xmp.find("<rdf:li")
    if i < 0:
        return ""
    j = xmp.find(">", i)
    k = xmp.find("</rdf:li>", j)
    if j < 0 or k < 0:
        return ""
    return xmp[j + 1:k].strip()


_DESCRIPTION_PREFIXES = ("ai-generated", "algorithmically generated")


def _conclude(
    out: Dict[str, Any],
    dst: str,
    description: str,
    software: str,
    carrier: str,
    allow_text_only: bool = True,
) -> Dict[str, Any]:
    """Decide what was found — and how well it is standardised.

    `allow_text_only=False` for carriers where the disclosure is plain text in
    the file itself. There, a line beginning "AI-generated" proves nothing: a
    person can write `// AI-generated content policy notes` at the head of a
    sketch, and reporting that file as marked would be the platform inventing a
    provenance nobody gave it. Containers keep the fallback — a file marked
    before the muxer flag was fixed carries the line and nothing else, and
    saying so is true.
    """
    dst = _as_text(dst)
    description = _as_text(description)
    out["digital_source_type"] = dst
    out["description"] = description
    out["software"] = software
    out["carrier"] = carrier
    if dst in _KNOWN_SOURCE_TYPES:
        out["marked"] = True
        out["standard"] = "iptc-digitalsourcetype"
    elif allow_text_only and description.lower().startswith(_DESCRIPTION_PREFIXES):
        out["marked"] = True
        out["standard"] = "text"
    return out


def _read_image_disclosure(path: Path, out: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image  # lazy
    except Exception as e:
        logger.warning(f"[WATERMARK] Pillow not available ({e}); cannot read disclosure")
        return out
    try:
        with Image.open(path) as img:
            info = dict(img.info or {})
            try:
                exif = dict(img.getexif() or {})
            except Exception:
                exif = {}
    except Exception as e:
        logger.info(f"[WATERMARK] cannot open {path.name} for disclosure ({e})")
        return out

    # PNG text chunks, exactly as watermark_image_bytes writes them
    dst = _as_text(info.get("DigitalSourceType"))
    description = _as_text(info.get("Description"))
    software = _as_text(info.get("Software"))
    carrier = "png-text" if (dst or description or software) else ""

    # XMP: PNG iTXt under Pillow's key, JPEG in the APP1 segment, TIFF/JPEG in
    # EXIF tag 700 (XMLPacket) — the same packet in three places.
    xmp = _as_text(info.get("XML:com.adobe.xmp") or info.get("xmp") or "")
    if not xmp:
        xmp = _as_text(exif.get(700))
    if xmp:
        dst = dst or _xmp_element(xmp, "iptcExt:DigitalSourceType")
        description = description or _xmp_alt_text(xmp)
        software = software or _xmp_element(xmp, "xmp:CreatorTool")
        carrier = carrier or "xmp"

    if not (dst or description):
        description = _as_text(exif.get(0x010E))  # ImageDescription
        software = software or _as_text(exif.get(0x0131))  # Software
        if description or software:
            carrier = carrier or "exif"

    return _conclude(out, dst, description, software, carrier)


def _read_container_disclosure(path: Path, out: Dict[str, Any]) -> Dict[str, Any]:
    if path.suffix.lower() == ".wav":
        try:
            xmp = _riff_xmp_text(path.read_bytes())
        except Exception as e:
            logger.info(f"[WATERMARK] cannot read {path.name} ({e})")
            xmp = ""
        if xmp:
            return _conclude(
                out,
                _xmp_element(xmp, "iptcExt:DigitalSourceType"),
                _xmp_alt_text(xmp),
                _xmp_element(xmp, "xmp:CreatorTool"),
                "riff-xmp",
            )

    if shutil.which("ffprobe") is None:
        logger.info("[WATERMARK] ffprobe not in PATH; cannot read container disclosure")
        return out
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return out
        payload = json.loads(result.stdout.decode("utf-8", errors="replace"))
        tags = (payload.get("format") or {}).get("tags") or {}
    except Exception as e:
        logger.info(f"[WATERMARK] ffprobe failed on {path.name} ({e})")
        return out

    low = {str(k).lower(): _as_text(v) for k, v in tags.items()}
    software = low.get("encoded_by") or low.get("encoder") or ""
    if software.startswith("Lavf"):
        software = ""  # that is the muxer signing itself, not the producing software
    return _conclude(
        out,
        low.get("digitalsourcetype", ""),
        low.get("description") or low.get("comment") or "",
        software,
        "container" if tags else "",
    )


def _read_glb_disclosure(path: Path, out: Dict[str, Any]) -> Dict[str, Any]:
    """Read asset.extras back out of a GLB's JSON chunk."""
    try:
        import struct

        raw = path.read_bytes()
        if len(raw) < 20 or raw[:4] != b"glTF":
            return out
        length, ctype = struct.unpack_from("<I4s", raw, 12)
        if ctype != b"JSON" or 20 + length > len(raw):
            return out
        doc = json.loads(raw[20:20 + length].decode("utf-8"))
        extras = ((doc.get("asset") or {}).get("extras") or {})
    except Exception as e:
        logger.info(f"[WATERMARK] cannot read GLB disclosure from {path.name} ({e})")
        return out
    return _conclude(
        out,
        extras.get("iptcExt:DigitalSourceType", ""),
        extras.get("dc:description", ""),
        _as_text(extras.get("xmp:CreatorTool", "")),
        "gltf-extras" if extras else "",
    )


def _read_text_disclosure(path: Path, out: Dict[str, Any], carrier: str) -> Dict[str, Any]:
    """A drawing and a sketch carry the disclosure as readable text.

    SVG keeps the XMP packet in its <metadata> element, a generated sketch
    keeps the same two facts in the comment at its head. Both are read the
    same way, and both stay legible to a person who opens the file.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.info(f"[WATERMARK] cannot read {path.name} ({e})")
        return out

    dst = _xmp_element(text, "iptcExt:DigitalSourceType")
    if not dst:
        # The comment header writes it as key=value, not as an element.
        for known in _KNOWN_SOURCE_TYPES:
            if f"iptcExt:DigitalSourceType={known}" in text:
                dst = known
                break
    description = _xmp_alt_text(text)
    software = _xmp_element(text, "xmp:CreatorTool")
    if not description:
        for line in text.splitlines()[:4]:
            stripped = line.lstrip("/*# \t").strip()
            if stripped.lower().startswith("ai-generated"):
                description = stripped
                break
    # allow_text_only=False: in a file whose disclosure IS text, a first line
    # that reads like one is not evidence that anything marked it.
    return _conclude(
        out, dst, description, software,
        carrier if (dst or description) else "",
        allow_text_only=False,
    )


def read_media_disclosure(path: Any) -> Dict[str, Any]:
    """Read the AI-origin disclosure back out of a produced file.

    The counterpart of watermark_media_bytes. Never raises: a file that cannot
    be opened, a format with no slot for the marking, a missing reader — all of
    them mean `marked: False`, because none of them is a marked file.
    """
    p = Path(path)
    out: Dict[str, Any] = {
        # Whether the file was there to be opened at all. An absent file is not
        # an unmarked file, and must not be reported as one: the card leaves the
        # row out rather than making a claim about something nobody read.
        "present": False,
        "marked": False,
        "standard": "",
        "digital_source_type": "",
        "description": "",
        "software": "",
        "carrier": "",
        "format": p.suffix.lstrip(".").lower(),
    }
    try:
        if not p.is_file():
            return out
        out["present"] = True
        suffix = p.suffix.lower()
        if suffix in _READ_IMAGE_SUFFIXES:
            return _read_image_disclosure(p, out)
        if suffix in _READ_CONTAINER_SUFFIXES:
            return _read_container_disclosure(p, out)
        if suffix in _READ_GLB_SUFFIXES:
            return _read_glb_disclosure(p, out)
        if suffix in _READ_MARKUP_SUFFIXES:
            return _read_text_disclosure(p, out, "svg-metadata")
        if suffix in _READ_CODE_SUFFIXES:
            return _read_text_disclosure(p, out, "code-header")
        return out
    except Exception as e:  # a read-out may never take a page down
        logger.warning(f"[WATERMARK] disclosure read failed ({e})")
        return out


def carry_disclosure_jpeg_kwargs(source_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The same carry-over, for a copy that is written as JPEG.

    `carry_disclosure_pnginfo` only helps a PNG. A picture that arrives as WebP
    is written out as JPEG, and that copy dropped everything the platform had
    marked — the marking died in our own re-encode while we went on claiming it.

    Returns kwargs for `Image.save` (possibly empty).
    """
    if not source_info:
        return {}
    xmp = source_info.get("XML:com.adobe.xmp") or source_info.get("xmp") or ""
    if isinstance(xmp, bytes):
        xmp = xmp.decode("utf-8", errors="replace")
    xmp = xmp.strip("\x00").strip()
    description = _as_text(source_info.get("Description"))
    software = _as_text(source_info.get("Software"))
    if not xmp and not description:
        return {}

    kwargs: Dict[str, Any] = {}
    try:
        from PIL import Image  # lazy

        if description or software:
            exif = Image.Exif()
            if software:
                exif[0x0131] = software
            if description:
                exif[0x010E] = description
            kwargs["exif"] = exif
        if xmp:
            kwargs["xmp"] = xmp.encode("utf-8")
    except Exception as e:
        logger.warning(f"[WATERMARK] Pillow not available ({e}); marking not carried over")
        return {}
    return kwargs


def carry_disclosure_pnginfo(source_info: Optional[Dict[str, Any]]):
    """Rebuild the AI-origin marking of a picture that is being re-encoded.

    Pillow writes no text chunk on save unless it is handed one back, so every
    re-encode silently drops the disclosure. Wherever a marked picture is
    copied — the board re-uploads what a run has just produced, and someone may
    bring in a marked picture from elsewhere — the copy has to carry it, or the
    marking dies in the copy while the platform still claims it.

    Args:
        source_info: the ORIGINAL image's `.info` (capture it before converting
            or resizing; those return fresh images with an empty info)

    Returns:
        A PngInfo to pass as `pnginfo=`, or None when there is nothing to carry.
    """
    if not source_info:
        return None
    try:
        from PIL import PngImagePlugin  # lazy
    except Exception as e:
        logger.warning(f"[WATERMARK] Pillow not available ({e}); marking not carried over")
        return None

    xmp = source_info.get("XML:com.adobe.xmp") or source_info.get("xmp") or ""
    if isinstance(xmp, bytes):
        xmp = xmp.decode("utf-8", errors="replace")
    xmp = xmp.strip("\x00").strip()
    text_keys = {
        k: _as_text(source_info.get(k))
        for k in ("DigitalSourceType", "Description", "Software")
        if source_info.get(k)
    }
    if not xmp and not text_keys:
        return None

    try:
        info = PngImagePlugin.PngInfo()
        if xmp:
            info.add_itxt("XML:com.adobe.xmp", xmp)
        for key, value in text_keys.items():
            if value:
                info.add_text(key, value)
        return info
    except Exception as e:
        logger.warning(f"[WATERMARK] could not carry marking over ({e})")
        return None


# ---------------------------------------------------------------------------
# Media that is not a picture, a film or a sound
# ---------------------------------------------------------------------------

def watermark_glb_bytes(content: bytes, entity_metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Write the AI-origin disclosure into a GLB's glTF asset block.

    glTF keeps a documented place for exactly this: `asset.extras` travels with
    the model through every viewer and re-export that respects the spec. The
    binary chunk is not touched, only the JSON chunk in front of it — and the
    container's length fields are rebuilt, or the file would be broken.

    Fail-open: original bytes on anything unexpected. Never raises.
    """
    settings = _get_settings()
    if not settings or not bool(settings.get("metadata_3d", True)):
        return content
    if len(content) < 20 or content[:4] != b"glTF":
        return content

    entity_metadata = entity_metadata or {}
    description = _build_description(entity_metadata, settings)
    software = settings.get("software_name", "") or "AI4ArtsEd-platform"

    try:
        import struct

        version, _total = struct.unpack_from("<II", content, 4)
        offset = 12
        chunks = []
        while offset + 8 <= len(content):
            length, ctype = struct.unpack_from("<I4s", content, offset)
            if offset + 8 + length > len(content):
                return content  # truncated file: leave it exactly as it is
            chunks.append((ctype, content[offset + 8: offset + 8 + length]))
            offset += 8 + length
        if not chunks or chunks[0][0] != b"JSON":
            return content

        doc = json.loads(chunks[0][1].decode("utf-8"))
        extras = doc.setdefault("asset", {}).setdefault("extras", {})
        extras["iptcExt:DigitalSourceType"] = _source_type(entity_metadata)
        extras["dc:description"] = description
        extras["xmp:CreatorTool"] = software

        new_json = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        new_json += b" " * ((-len(new_json)) % 4)  # spec: JSON chunk pads with spaces
        chunks[0] = (b"JSON", new_json)

        body = b"".join(
            struct.pack("<I", len(data)) + ctype + data for ctype, data in chunks
        )
        return b"glTF" + struct.pack("<II", version, 12 + len(body)) + body
    except Exception as e:
        logger.warning(f"[WATERMARK] GLB disclosure failed ({e}); returning original bytes")
        return content


def _tag_end(text: str, start: int) -> int:
    """Index of the `>` that closes the tag beginning at `start`.

    Not `text.find(">")`: an attribute value may hold one — `aria-label="a > b"`
    is legal — and splitting the root start tag leaves an SVG that no longer
    parses. Returns -1 when the tag does not close.
    """
    quote = ""
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == ">":
            return i
    return -1


def watermark_svg_bytes(content: bytes, entity_metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Put the XMP packet into the SVG's own <metadata> element.

    SVG has carried a place for RDF metadata since 1.0; readers ignore what
    they do not understand, so nothing about the drawing changes.
    """
    settings = _get_settings()
    if not settings or not bool(settings.get("metadata_svg", True)):
        return content

    entity_metadata = entity_metadata or {}
    description = _build_description(entity_metadata, settings)
    software = settings.get("software_name", "") or "AI4ArtsEd-platform"

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    if _source_type(entity_metadata) in text:
        return content  # already marked, with this very value

    start = text.find("<svg")
    if start < 0:
        return content
    end = _tag_end(text, start)
    if end < 0 or text[end - 1] == "/":
        return content  # empty <svg/>: nothing to put anything into

    block = (
        "\n  <metadata>\n"
        + _xmp_packet(
            software, description, wrapped=False, source_type=_source_type(entity_metadata)
        )
        + "\n  </metadata>"
    )
    return (text[: end + 1] + block + text[end + 1:]).encode("utf-8")


def watermark_code_bytes(
    content: bytes, entity_type: str, entity_metadata: Optional[Dict[str, Any]] = None
) -> bytes:
    """Head a generated sketch with the disclosure, in its own comment syntax.

    p5.js and Tone.js sketches ARE the medium here — they are what the run hands
    back and what someone takes home. A file format with no metadata block still
    has the one place every reader looks first.
    """
    settings = _get_settings()
    if not settings or not bool(settings.get("metadata_code", True)):
        return content

    entity_metadata = entity_metadata or {}
    description = _build_description(entity_metadata, settings)

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    if _source_type(entity_metadata) in text:
        return content

    if text.lstrip()[:1] in ("{", "["):
        # JSON, not a sketch. A comment header would make it unparseable, and
        # `output_code` is a name a JSON payload can arrive under.
        return content

    source_type = _source_type(entity_metadata)
    # A description can contain `*/` — a prompt is written by a person.
    safe = description.replace("*/", "* /")
    if "sonicpi" in (entity_type or "").lower():
        header = f"# {description}\n# iptcExt:DigitalSourceType={source_type}\n"
    else:
        header = f"/* {safe}\n   iptcExt:DigitalSourceType={source_type} */\n"
    return (header + text).encode("utf-8")


# ISO-BMFF says nothing about what is inside; only the brand does.
_BMFF_IMAGE_BRANDS = {
    b"avif", b"avis", b"heic", b"heix", b"heim", b"heis",
    b"hevc", b"hevx", b"hevm", b"hevs", b"mif1", b"msf1", b"miaf",
}
_BMFF_VIDEO_BRANDS = {
    b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42",
    b"avc1", b"dash", b"qt  ", b"M4V ", b"M4VH", b"M4VP", b"3gp4", b"3gp5",
}


def _sniff_media_kind(content: bytes) -> str:
    """What ARE these bytes? Returns 'image'/'video'/'audio'/'glb'/'svg'/'text'/''.

    The entity's name is not evidence: on disk there are 47 files called
    output_image that are mp3, and 10 called output_video that are PNG. Those
    went through the wrong branch for as long as the dispatcher trusted names.
    """
    if len(content) < 12:
        return ""
    head = content[:16]
    if head[:8] == b"\x89PNG\r\n\x1a\n" or head[:3] == b"\xff\xd8\xff" or head[:6] in (b"GIF87a", b"GIF89a"):
        return "image"
    if head[:2] in (b"II", b"MM") and content[2:4] in (b"\x2a\x00", b"\x00\x2a"):
        return "image"
    if head[:4] == b"RIFF":
        if content[8:12] == b"WEBP":
            return "image"
        if content[8:12] == b"WAVE":
            return "audio"
        return ""
    if head[:4] == b"glTF":
        return "glb"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio"
    if head[:4] == b"fLaC":
        return "audio"
    if head[:4] == b"OggS":
        return "audio"
    if content[4:8] == b"ftyp":
        # One box for film, sound AND still pictures; the brand decides. AVIF
        # and HEIC are ISO-BMFF too, and sending a still through the video
        # writer does not mark it — it remuxes it into an mp4 that is then
        # written back under the picture's own name.
        brand = content[8:12]
        if brand in _BMFF_IMAGE_BRANDS:
            return "image"
        if brand[:3] in (b"M4A", b"M4B") or brand == b"M4P ":
            return "audio"
        if brand in _BMFF_VIDEO_BRANDS:
            return "video"
        return ""  # an unknown brand: let the entity name decide
    if head[:4] == b"\x1aE\xdf\xa3":
        return "video"
    # errors="ignore", not a bare decode: one umlaut straddling byte 4096
    # raised, and the sketch went out unmarked while the same file one byte
    # shorter was marked.
    text = content[:4096].decode("utf-8", errors="ignore")
    if not text.strip():
        return ""
    stripped = text.lstrip()
    if stripped.startswith("<svg") or (stripped.startswith("<?xml") and "<svg" in text):
        return "svg"
    return "text"
