"""One envelope for every picture that goes to a vision model.

`media_ref.py` states the envelope and why it exists: under 64 px the runner
rejects the bitmap, over 768 px oversized input "has repeatedly taken the runner
down and 500'd every request behind it". Three call sites sent pictures and only
one went through it.

`/api/media/analyze/image` sent `resolved.read_bytes()` whenever no reading frame
was set -- the uploads it reads are capped at 2048 px and re-saved as PNG, so a
picture arrived at roughly 5-11 MB of base64 where the rest of the platform
sends ~100 KB. `/api/schema/compare/analyze-image` kept a copy of the resize with
two of the three steps missing.

These tests hold the envelope itself, and that neither route has its own copy of
it left.
"""
import ast
import base64
import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_app.utils.media_ref import IMAGE_MAX_SIZE, IMAGE_MIN_SIZE, encode_image_b64

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _decode(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def _write(tmp_path, img, name="x.png"):
    path = tmp_path / name
    img.save(path)
    return path


# --------------------------------------------------------------------------
# The envelope
# --------------------------------------------------------------------------

def test_an_oversized_picture_is_brought_down(tmp_path):
    path = _write(tmp_path, Image.new("RGB", (2048, 2048), (10, 20, 30)))
    out = _decode(encode_image_b64(path))
    assert max(out.size) <= IMAGE_MAX_SIZE


def test_an_undersized_picture_is_brought_up(tmp_path):
    """Below the floor the runner refuses, and the route reported an empty reading."""
    path = _write(tmp_path, Image.new("RGB", (32, 32), (10, 20, 30)))
    out = _decode(encode_image_b64(path))
    assert min(out.size) >= IMAGE_MIN_SIZE


def test_a_palette_png_does_not_raise(tmp_path):
    """`save(format='JPEG')` on mode P raises; the upload path converts only RGBA."""
    path = _write(tmp_path, Image.new("RGB", (800, 600), (10, 20, 30)).convert("P"))
    out = _decode(encode_image_b64(path))
    assert out.mode == "RGB"
    assert max(out.size) <= IMAGE_MAX_SIZE


def test_a_transparent_png_keeps_its_shape(tmp_path):
    path = _write(tmp_path, Image.new("RGBA", (900, 300), (10, 20, 30, 128)))
    out = _decode(encode_image_b64(path))
    assert out.mode == "RGB"
    assert out.size[0] > out.size[1], "the aspect ratio was not kept"


def test_a_picture_inside_the_envelope_is_left_alone(tmp_path):
    path = _write(tmp_path, Image.new("RGB", (700, 500), (10, 20, 30)))
    out = _decode(encode_image_b64(path))
    assert out.size == (700, 500)


def test_the_answer_is_smaller_than_the_file(tmp_path):
    """The point of the envelope, in bytes."""
    path = _write(tmp_path, Image.effect_noise((2048, 2048), 90).convert("RGB"))
    assert len(encode_image_b64(path)) < path.stat().st_size


# --------------------------------------------------------------------------
# No route keeps its own copy
# --------------------------------------------------------------------------

def _source(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
        return handle.read()


def test_the_reading_route_does_not_send_raw_bytes():
    src = _source("my_app/routes/media_routes.py")
    assert "b64encode(resolved.read_bytes())" not in src
    assert "encode_image_b64(resolved)" in src


def test_the_compare_route_has_no_resize_of_its_own():
    src = _source("my_app/routes/schema_pipeline_routes.py")
    assert "img.thumbnail((768, 768)" not in src
    assert "normalize_image(img_path)" in src


def test_the_envelope_is_stated_in_one_place():
    """Both numbers live in media_ref and nowhere else as literals on this path."""
    src = _source("my_app/utils/media_ref.py")
    tree = ast.parse(src)
    names = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
             for t in node.targets if isinstance(t, ast.Name)}
    assert {"IMAGE_MAX_SIZE", "IMAGE_MIN_SIZE"} <= names


def test_both_stations_of_the_compare_route_get_the_same_bytes():
    """One station takes base64, the other a file. A second encode would let the
    two drift, and reading a variable the resize no longer produces crashes the
    file station outright -- which is what happened while this change was made."""
    src = _source("my_app/routes/schema_pipeline_routes.py")
    assert "image_bytes = base64.b64decode(image_b64)" in src
    assert "tmp.write(image_bytes)" in src
    assert "buf.getvalue()" not in src
