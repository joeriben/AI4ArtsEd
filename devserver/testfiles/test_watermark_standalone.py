"""
Standalone test for watermark_service — run this BEFORE wiring the service
into pipeline_recorder. (Never integrate watermark code without proving it
works in isolation first.)

Usage:
    cd <repo>
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
    "metadata_audio": True,
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
    _sniff_media_kind,
    read_media_disclosure,
    watermark_audio_bytes,
    watermark_image_bytes,
    watermark_media_bytes,
    watermark_result_metadata,
    watermark_video_bytes,
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


def find_sample_audio() -> Path | None:
    for pattern in ("*output_audio*.mp3", "*output_music*.mp3", "*output_audio*.wav", "*output_music*.wav"):
        cand = sorted(
            (REPO / "exports").rglob(pattern),
            key=lambda p: p.stat().st_size,
        )
        if cand:
            return cand[0]
    return None


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


def test_audio() -> None:
    audio_path = find_sample_audio()
    if audio_path is None:
        print("\n[test_audio] no sample audio in exports/; skipping")
        return
    print(f"\n[test_audio] sample: {audio_path}")
    original = audio_path.read_bytes()
    # Anything produced since the service went in already carries the mark, and
    # for those "unchanged" is the CORRECT answer — a container that is marked
    # is not remuxed a second time. So the test strips first and marks that.
    was_marked = DIGITAL_SOURCE_TYPE_AI.encode("utf-8") in original
    if was_marked:
        assert_(
            watermark_audio_bytes(original, {"model": "test-audio-model"}) == original,
            "an already-marked container comes straight back",
        )
        stripped = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(audio_path),
             "-map_metadata", "-1", "-c", "copy", "-f", audio_path.suffix.lstrip("."), "-"],
            capture_output=True, timeout=60,
        ).stdout
        if stripped:
            original = stripped

    out = watermark_audio_bytes(original, {"model": "test-audio-model"})
    assert_(len(out) > 0, "watermarked audio bytes non-empty")
    assert_(out != original, "an unmarked container is marked")

    if shutil.which("ffprobe"):
        suffix = audio_path.suffix or ".bin"
        tmp = Path(f"/tmp/_wm_test_audio{suffix}")
        tmp.write_bytes(out)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", str(tmp)],
            capture_output=True, text=True, timeout=15,
        )
        print("  ffprobe excerpt:")
        for line in result.stdout.splitlines():
            if any(k in line.lower() for k in ("description", "comment", "creation_time", "encoded_by", "digitalsource")):
                print(f"    {line}")
        assert_(
            "AI-generated" in result.stdout or "trainedAlgorithmicMedia" in result.stdout,
            "ffprobe sees AI-origin in audio metadata",
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
    assert_(out2 == png, "a picture a PERSON brought in is never marked as AI-generated")

    out3 = watermark_media_bytes(png, "input_image2", {})
    assert_(out3 == png, "...nor the second and third of them")

    out4 = watermark_media_bytes(png, "generation", {"model": "x"})
    assert_(out4 != png, "a generated picture under an unlisted name IS marked (canvas: 'generation')")

    text = b"not a medium, just a line of prose that a run happened to produce"
    assert_(watermark_media_bytes(text, "interception", {}) == text,
            "text that is not a sketch stays untouched")


def test_disabled() -> None:
    print("\n[test_disabled]")
    config.WATERMARK = {"metadata_image": False, "visible_image": False, "invisible_image": False}
    png = find_sample_png().read_bytes()
    out = watermark_image_bytes(png, {})
    assert_(out == png, "fully disabled → bytes unchanged")


def test_invisible_roundtrip() -> None:
    """Phase 4: invisible DWT-DCT watermark must survive PNG round-trip and decode back."""
    print("\n[test_invisible_roundtrip]")
    # Reset to a config that only exercises the invisible layer
    config.WATERMARK = {
        "metadata_image": False,
        "visible_image": False,
        "invisible_image": True,
        "invisible_payload": "AI-generated",
    }
    png_path = find_sample_png()
    original = png_path.read_bytes()
    out = watermark_image_bytes(original, {})
    assert_(out != original, "invisible-only path changed bytes")

    # Decode it back
    import io as _io
    import numpy as np
    import cv2
    from PIL import Image
    from imwatermark import WatermarkDecoder

    img = Image.open(_io.BytesIO(out)).convert("RGB")
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    dec = WatermarkDecoder("bytes", 8 * len("AI-generated"))
    decoded = dec.decode(bgr, "dwtDct")
    try:
        text = decoded.decode("utf-8", errors="replace")
    except Exception:
        text = str(decoded)
    print(f"  decoded payload bytes: {decoded!r}")
    print(f"  decoded payload utf-8: {text!r}")
    # DWT-DCT is robust but not bit-perfect on all images; tolerate Hamming
    # distance ≤ 3 chars over the 12-char payload.
    expected = "AI-generated"
    if len(text) == len(expected):
        diff = sum(1 for a, b in zip(text, expected) if a != b)
    else:
        diff = len(expected)
    assert_(diff <= 3, f"invisible payload recoverable (hamming={diff})")


# ---------------------------------------------------------------------------
# What came in on 2026-08-15: every medium, and the way back out of the file
# ---------------------------------------------------------------------------

def _find(pattern: str) -> Path | None:
    """The smallest sample that is actually a file — tests should be quick.

    Torsos are skipped: exports/ holds an 11-byte PNG from a run that broke off
    in 2025, and a truncated file tests the error path, not the medium.
    """
    cand = sorted(
        (p for p in (REPO / "exports").rglob(pattern) if p.stat().st_size >= 256),
        key=lambda p: p.stat().st_size,
    )
    return cand[0] if cand else None


def _reset_config() -> None:
    """The tests before this one leave WATERMARK in odd states."""
    config.WATERMARK = {
        "metadata_image": True, "metadata_video": True, "metadata_audio": True,
        "metadata_3d": True, "metadata_svg": True, "metadata_code": True,
        "metadata_include_model": True, "metadata_include_date": True,
        "software_name": "TestRunner",
        "visible_image": False, "visible_video": False, "invisible_image": False,
    }


def test_sniffer() -> None:
    """The entity's NAME is not evidence — on disk there are files called
    output_image that are mp3. The dispatcher has to go by the bytes."""
    print("\n[test_sniffer]")
    _reset_config()
    cases = [
        ("*output_image*.png", "image"),
        ("*output_audio*.wav", "audio"),
        ("*output_video*.mp4", "video"),
        ("*output_3d*.glb", "glb"),
        ("*output_svg*.svg", "svg"),
        ("*_p5.js", "text"),
    ]
    for pattern, want in cases:
        sample = _find(pattern)
        if sample is None:
            print(f"  skip {pattern} (no sample in exports/)")
            continue
        got = _sniff_media_kind(sample.read_bytes())
        assert_(got == want, f"{pattern} sniffs as {want} (got {got})")

    mislabelled = _find("*output_image*.mp3")
    if mislabelled is not None:
        marked = watermark_media_bytes(mislabelled.read_bytes(), "output_image", {"model": "x"})
        assert_(marked[:3] in (b"ID3", b"\xff\xfb") or marked[:4] == b"RIFF",
                "an mp3 named output_image goes through the audio branch, not the image branch")


def test_every_medium_roundtrip(tmp: Path) -> None:
    """Mark it, write it, read it back. Marked or the test fails — there is no
    third answer, and 'we wrote it' is not evidence that it is in the file."""
    print("\n[test_every_medium_roundtrip]")
    _reset_config()
    cases = [
        ("*output_image*.png", "output_image"),
        ("*output_image_composite*.png", "output_image_composite"),
        ("*output_video*.mp4", "output_video"),
        ("*output_audio*.wav", "output_audio"),
        ("*output_audio*.mp3", "output_audio"),
        ("*output_3d*.glb", "output_3d"),
        ("*output_svg*.svg", "output_svg"),
        ("*_p5.js", "p5"),
    ]
    for pattern, entity_type in cases:
        sample = _find(pattern)
        if sample is None:
            print(f"  skip {pattern} (no sample in exports/)")
            continue
        marked = watermark_media_bytes(sample.read_bytes(), entity_type, {"model": "test-model"})
        out = tmp / sample.name
        out.write_bytes(marked)
        info = read_media_disclosure(out)
        assert_(info["marked"], f"{pattern} reads back marked ({info['standard']}/{info['carrier']})")


def test_glb_stays_a_glb(tmp: Path) -> None:
    """A rebuilt chunk table that is off by one byte is a broken model."""
    print("\n[test_glb_stays_a_glb]")
    import struct

    _reset_config()
    sample = _find("*output_3d*.glb")
    if sample is None:
        print("  skip (no GLB in exports/)")
        return
    original = sample.read_bytes()
    marked = watermark_media_bytes(original, "output_3d", {"model": "test-model"})

    def chunks(b: bytes):
        out, off = [], 12
        while off + 8 <= len(b):
            length, ctype = struct.unpack_from("<I4s", b, off)
            out.append((ctype, b[off + 8: off + 8 + length]))
            off += 8 + length
        return out

    before, after = chunks(original), chunks(marked)
    assert_(struct.unpack_from("<I", marked, 8)[0] == len(marked), "GLB total-length field matches the file")
    assert_([c[1] for c in before if c[0] == b"BIN\x00"] == [c[1] for c in after if c[0] == b"BIN\x00"],
            "GLB binary chunk is byte-identical")
    import json as _json
    doc = _json.loads(after[0][1].decode("utf-8"))
    assert_(doc["asset"]["extras"]["iptcExt:DigitalSourceType"] == DIGITAL_SOURCE_TYPE_AI,
            "GLB asset.extras carries the controlled vocabulary")


def test_wav_keeps_its_sound(tmp: Path) -> None:
    """RIFF INFO has no field for the vocabulary, so the packet goes into a
    _PMX chunk. The samples themselves may not move."""
    print("\n[test_wav_keeps_its_sound]")
    _reset_config()
    sample = _find("*output_audio*.wav")
    if sample is None or shutil.which("ffmpeg") is None:
        print("  skip (no WAV in exports/, or no ffmpeg)")
        return
    marked = watermark_media_bytes(sample.read_bytes(), "output_audio", {"model": "test-model"})
    out = tmp / "marked.wav"
    out.write_bytes(marked)

    info = read_media_disclosure(out)
    assert_(info["standard"] == "iptc-digitalsourcetype",
            f"WAV carries the controlled vocabulary (got {info['standard']}/{info['carrier']})")

    def pcm(path: Path) -> bytes:
        return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-"],
                              capture_output=True).stdout

    assert_(pcm(sample) == pcm(out), "WAV samples are unchanged")
    twice = watermark_media_bytes(marked, "output_audio", {"model": "test-model"})
    assert_(twice.count(b"_PMX") == 1, "marking twice leaves ONE _PMX chunk, not two")


def test_marking_twice_is_free(tmp: Path) -> None:
    """A picture now passes the marking twice — once where the result is
    assembled, once where it is written down. The second pass must not touch it."""
    print("\n[test_marking_twice_is_free]")
    _reset_config()
    png = find_sample_png().read_bytes()
    once = watermark_media_bytes(png, "output_image", {"model": "m"})
    twice = watermark_media_bytes(once, "output_image", {"model": "m"})
    assert_(twice == once, "second marking returns the identical bytes")


def test_response_payload(tmp: Path) -> None:
    """The latent lab downloads what it was HANDED, never the file on disk."""
    print("\n[test_response_payload]")
    import base64 as _b64

    _reset_config()
    png = find_sample_png().read_bytes()
    plain = "not a payload, just a sentence that happens to sit in metadata"
    meta = {
        "image_data": _b64.b64encode(png).decode(),
        "not_media": plain,
        "archaeology_data": {"step_images": [{"step": 1, "image_base64": _b64.b64encode(png).decode()}]},
    }
    watermark_result_metadata(meta, {"model": "test-model"})

    out = tmp / "payload.png"
    out.write_bytes(_b64.b64decode(meta["image_data"]))
    assert_(read_media_disclosure(out)["marked"], "image_data in the response is marked")

    step = tmp / "step.png"
    step.write_bytes(_b64.b64decode(meta["archaeology_data"]["step_images"][0]["image_base64"]))
    assert_(read_media_disclosure(step)["marked"], "each archaeology step image is marked")
    assert_(meta["not_media"] == plain, "a plain string in the metadata is left alone")


def test_what_the_review_refuted(tmp: Path) -> None:
    """The findings of the 2026-08-15 adversarial review, one assertion each.

    Every one of these was a real defect in the change that introduced content
    sniffing. They stay here so the next rewrite has to face them again.
    """
    print("\n[test_what_the_review_refuted]")
    import base64 as _b64
    import io as _io
    import xml.etree.ElementTree as ET
    from PIL import Image, PngImagePlugin

    from my_app.services.watermark_service import (
        DIGITAL_SOURCE_TYPE_ALGORITHMIC,
        _sniff_media_kind as sniff,
    )

    _reset_config()

    # A still picture in an ISO-BMFF container is not a film. Sending it to the
    # video writer remuxed it into an mp4 that was written back under the
    # picture's own name.
    for brand, want in ((b"avif", "image"), (b"heic", "image"),
                        (b"isom", "video"), (b"M4A ", "audio"), (b"zzzz", "")):
        head = b"\x00\x00\x00\x20ftyp" + brand + b"\x00" * 40
        assert_(sniff(head) == want, f"ftyp{brand.decode().strip()} sniffs as {want or 'unknown'}")

    # An animated picture is not ours to flatten.
    frames = [Image.new("RGB", (32, 32), (i * 30, 0, 0)) for i in range(5)]
    for fmt in ("GIF", "WEBP"):
        buf = _io.BytesIO()
        frames[0].save(buf, format=fmt, save_all=True, append_images=frames[1:], duration=100)
        raw = buf.getvalue()
        assert_(watermark_media_bytes(raw, "output_image", {"model": "m"}) == raw,
                f"an animated {fmt} comes back untouched")

    # A `>` inside an attribute value is legal and must not split the root tag;
    # `&` in a description must not make the document malformed.
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg" aria-label="a > b" '
           b'width="4" height="4"><rect width="4" height="4"/></svg>')
    marked = watermark_media_bytes(svg, "output_svg", {"model": "Tom & Jerry <v2>"})
    ET.fromstring(marked)
    assert_(True, "an SVG survives a '>' in an attribute and an '&' in the description")

    # A camera's own digitalCapture value is not an AI marking — in either
    # direction: it must not suppress ours, and it must not read as ours.
    info = PngImagePlugin.PngInfo()
    info.add_text("DigitalSourceType",
                  "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture")
    buf = _io.BytesIO()
    Image.new("RGB", (40, 40), (10, 20, 30)).save(buf, format="PNG", pnginfo=info)
    cap = buf.getvalue()
    assert_(watermark_image_bytes(cap, {"model": "m"}) != cap,
            "a digitalCapture value does not suppress the AI marking")
    p = tmp / "capture.png"
    p.write_bytes(cap)
    assert_(read_media_disclosure(p)["marked"] is False,
            "and a digitalCapture file does not read back as AI-marked")

    # A prose comment mentioning AI is not a disclosure.
    h = tmp / "human.js"
    h.write_text("// AI-generated content policy notes\nconst x = 1;\n")
    assert_(read_media_disclosure(h)["marked"] is False,
            "a human note about AI does not read as a marking")

    # JSON under a code name keeps its shape.
    js = b'{"a": 1}'
    assert_(watermark_media_bytes(js, "output_code", {}) == js, "JSON is not given a comment header")

    # A data: URI is the shape every chat-completions provider hands back.
    buf = _io.BytesIO()
    Image.new("RGB", (60, 60), (1, 2, 3)).save(buf, format="PNG")
    plain = buf.getvalue()
    meta = {"image_data": "data:image/png;base64," + _b64.b64encode(plain).decode()}
    watermark_result_metadata(meta, {"model": "m"})
    assert_(meta["image_data"].startswith("data:image/png;base64,"), "the data: prefix survives")
    q = tmp / "uri.png"
    q.write_bytes(_b64.b64decode(meta["image_data"].split(",", 1)[1]))
    assert_(read_media_disclosure(q)["marked"], "and the payload behind it is marked")

    # A JPEG must not lose a generation to being marked.
    jb = _io.BytesIO()
    Image.open(_io.BytesIO(plain)).convert("RGB").save(jb, format="JPEG", quality=95)
    jraw = jb.getvalue()
    jm = watermark_media_bytes(jraw, "output_image", {"model": "m"})
    with Image.open(_io.BytesIO(jraw)) as a, Image.open(_io.BytesIO(jm)) as b:
        assert_(list(a.getdata()) == list(b.getdata()), "JPEG pixels are bit-identical after marking")
    j = tmp / "j.jpg"
    j.write_bytes(jm)
    assert_(read_media_disclosure(j)["marked"], "and the JPEG reads back marked")

    # Rule-based synthesis is not a trained model.
    wav = _find("*output_audio*.wav")
    if wav is not None:
        alg = watermark_media_bytes(wav.read_bytes(), "output_audio",
                                    {"model": "espeak",
                                     "digital_source_type": DIGITAL_SOURCE_TYPE_ALGORITHMIC})
        s = tmp / "espeak.wav"
        s.write_bytes(alg)
        got = read_media_disclosure(s)
        assert_(got["digital_source_type"] == DIGITAL_SOURCE_TYPE_ALGORITHMIC,
                "eSpeak is marked algorithmicMedia, not trainedAlgorithmicMedia")
        assert_(got["marked"], "and still counts as marked")


def test_absent_file_is_not_an_unmarked_file(tmp: Path) -> None:
    """A file nobody could open must not be reported as one without a marking."""
    print("\n[test_absent_file_is_not_an_unmarked_file]")
    info = read_media_disclosure(tmp / "there-is-no-such-file.png")
    assert_(info["present"] is False, "a missing file reports present=False")
    assert_(info["marked"] is False, "and makes no claim about a marking")


if __name__ == "__main__":
    print("=" * 60)
    print("watermark_service standalone test")
    print("=" * 60)
    test_image()
    test_video()
    test_audio()
    test_dispatcher()
    test_disabled()
    test_invisible_roundtrip()

    import tempfile
    _tmp = Path(tempfile.mkdtemp(prefix="watermark_test_"))
    try:
        test_sniffer()
        test_every_medium_roundtrip(_tmp)
        test_glb_stays_a_glb(_tmp)
        test_wav_keeps_its_sound(_tmp)
        test_marking_twice_is_free(_tmp)
        test_response_payload(_tmp)
        test_what_the_review_refuted(_tmp)
        test_absent_file_is_not_an_unmarked_file(_tmp)
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)

    print("\nAll checks passed.")
