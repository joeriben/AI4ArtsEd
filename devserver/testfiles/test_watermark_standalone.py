"""
Standalone test for watermark_service — run this BEFORE wiring the service
into pipeline_recorder. (Session 118 lesson: never integrate watermark code
without proving it works in isolation first.)

Usage:
    cd /home/joerissen/ai/ai4artsed_development
    PYTHONPATH=devserver venv/bin/python devserver/testfiles/test_watermark_standalone.py
"""

import io
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "devserver"))

# Force a known-good config for the test (overrides whatever user_settings.json says)
import config  # type: ignore
config.WATERMARK = {
    "metadata_image": True,
    "metadata_video": True,
    "metadata_include_model": True,
    "metadata_include_date": True,
    "metadata_include_prompt": True,  # ON for test, default OFF in real settings
    "metadata_include_seed": True,
    "software_name": "TestRunner",
    "visible_image": True,            # ON for test
    "visible_video": True,
    "visible_text": "AI-generated",
    "visible_position": "bottom-right",
    "visible_opacity": 0.5,
    "invisible_image": False,
}

from my_app.services.watermark_service import (  # noqa: E402
    DIGITAL_SOURCE_TYPE_AI,
    watermark_image_bytes,
    watermark_video_bytes,
    watermark_media_bytes,
)


def find_sample_png() -> Path:
    # Skip composites — they often have white background strips that hide
    # white-text visible watermarks (only outline shows), making pixel-diff
    # tests unreliable. Prefer regular generated images.
    candidates = sorted(
        (p for p in (REPO / "exports").rglob("*output_image*.png") if "composite" not in p.name),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("No non-composite sample PNG in exports/. Generate one first.")
    return candidates[0]


def find_sample_mp4() -> Path | None:
    cand = sorted(
        (REPO / "exports").rglob("*output_video*.mp4"),
        key=lambda p: p.stat().st_size,
    )
    return cand[0] if cand else None


def assert_(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  FAIL: {msg}")
        sys.exit(1)
    print(f"  ok   {msg}")


def test_image() -> None:
    png_path = find_sample_png()
    print(f"\n[test_image] sample: {png_path}")
    original = png_path.read_bytes()
    out = watermark_image_bytes(original, {
        "model": "test-model-v1",
        "seed": 42,
        "prompt": "a unit test for watermarking",
    })

    assert_(out != original, "watermarked bytes differ from original")
    assert_(len(out) > 0, "watermarked bytes are non-empty")

    # Pillow can re-read result
    from PIL import Image
    img = Image.open(io.BytesIO(out))
    img.load()
    assert_(img.format == "PNG", f"format is PNG (got {img.format})")

    # iTXt / tEXt present
    text_chunks = getattr(img, "text", {}) or {}
    keys = list(text_chunks.keys())
    assert_("XML:com.adobe.xmp" in keys, f"XMP chunk present (keys={keys})")
    xmp = text_chunks["XML:com.adobe.xmp"]
    assert_(DIGITAL_SOURCE_TYPE_AI in xmp, "XMP contains DigitalSourceType=trainedAlgorithmicMedia")
    assert_("test-model-v1" in xmp or "test-model-v1" in text_chunks.get("Description", ""),
            "model name embedded in metadata")

    # Visible mark check (heuristic): with visible_image ON, decoded image
    # should differ from original at the bottom-right region
    from PIL import Image as _Image
    orig_img = _Image.open(io.BytesIO(original)).convert("RGBA")
    new_img = _Image.open(io.BytesIO(out)).convert("RGBA")
    if orig_img.size == new_img.size:
        # sample bottom-right corner
        w, h = orig_img.size
        box = (max(0, w - 200), max(0, h - 60), w, h)
        diff_pixels = sum(
            1 for o, n in zip(orig_img.crop(box).getdata(), new_img.crop(box).getdata())
            if o != n
        )
        assert_(diff_pixels > 50, f"visible mark altered pixels in bottom-right (changed={diff_pixels})")
    else:
        print("  ?    sizes differ; skipping pixel-diff check")

    # exiftool roundtrip (if available)
    if shutil.which("exiftool"):
        tmp = Path("/tmp/_wm_test.png")
        tmp.write_bytes(out)
        result = subprocess.run(
            ["exiftool", "-XMP-iptcExt:DigitalSourceType", "-Software", "-Description", str(tmp)],
            capture_output=True, text=True, timeout=10,
        )
        print(f"  exiftool says:\n    {result.stdout.strip().replace(chr(10), chr(10) + '    ')}")
        assert_("trainedAlgorithmicMedia" in result.stdout or "DigitalSourceType" in result.stdout,
                "exiftool sees DigitalSourceType")
        tmp.unlink(missing_ok=True)
    else:
        print("  ?    exiftool not installed; skipping CLI roundtrip")


def test_video() -> None:
    mp4_path = find_sample_mp4()
    if mp4_path is None:
        print("\n[test_video] no sample MP4 in exports/; skipping")
        return
    print(f"\n[test_video] sample: {mp4_path}")
    original = mp4_path.read_bytes()
    out = watermark_video_bytes(original, {"model": "test-video-model"})
    assert_(len(out) > 0, "watermarked video bytes non-empty")
    # If ffmpeg ran, bytes change (re-encode for visible) or at least metadata changes
    assert_(out != original or len(out) == 0, "watermarked bytes differ from original")

    if shutil.which("ffprobe"):
        tmp = Path("/tmp/_wm_test.mp4")
        tmp.write_bytes(out)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", str(tmp)],
            capture_output=True, text=True, timeout=15,
        )
        print(f"  ffprobe excerpt:")
        for line in result.stdout.splitlines():
            if any(k in line.lower() for k in ("description", "comment", "creation_time", "encoder", "digitalsource")):
                print(f"    {line}")
        assert_(
            "AI-generated" in result.stdout or "trainedAlgorithmicMedia" in result.stdout,
            "ffprobe sees AI-origin in container metadata",
        )
        tmp.unlink(missing_ok=True)
    else:
        print("  ?    ffprobe not installed; skipping CLI roundtrip")


def test_dispatcher() -> None:
    print("\n[test_dispatcher]")
    png = find_sample_png().read_bytes()
    out = watermark_media_bytes(png, "output_image", {"model": "x"})
    assert_(out != png, "dispatcher routes output_image → image watermark")

    out2 = watermark_media_bytes(png, "input", {})
    assert_(out2 == png, "dispatcher passes through unknown entity_type unchanged")


def test_disabled() -> None:
    print("\n[test_disabled]")
    config.WATERMARK = {"metadata_image": False, "visible_image": False}
    png = find_sample_png().read_bytes()
    out = watermark_image_bytes(png, {})
    assert_(out == png, "fully disabled → bytes unchanged")


if __name__ == "__main__":
    print("=" * 60)
    print("watermark_service standalone test")
    print("=" * 60)
    test_image()
    test_video()
    test_dispatcher()
    test_disabled()
    print("\nAll checks passed.")
