"""A generated file whose bytes do not carry the AI-Origin Disclosure says so in its name.

Rule of the project lead, 2026-11-14: "ungekennzeichnete Dateien erhalten ein
filename-Suffix _ai_generated". The marking falls open by decision (ARCHITECTURE
PART 36, section 7); these tests hold where the name takes over: the writers that
put media on the disk, the routes that hand them out, and the script that marks
what the storage holds from before the marking reached it.
"""
import base64
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.services import watermark_service as ws  # noqa: E402
from my_app.services.media_marking import disclosed_name, mark_for_disk  # noqa: E402

MARKING = "my_app.services.media_marking"
SUFFIX = ws.UNMARKED_SUFFIX


def _png_bytes(color=(10, 120, 200)) -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(out, format="PNG")
    return out.getvalue()


def _animated_gif_bytes() -> bytes:
    from PIL import Image

    frames = [Image.new("P", (8, 8), i) for i in (1, 2, 3)]
    out = io.BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:])
    return out.getvalue()


def _glb_bytes() -> bytes:
    import struct

    doc = json.dumps({"asset": {"version": "2.0"}}).encode("utf-8")
    doc += b" " * ((-len(doc)) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(doc))
            + struct.pack("<I4s", len(doc), b"JSON") + doc)


def _errors(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.fixture()
def unmarking(monkeypatch):
    """What a marking that fell open looks like from the writer's side."""
    monkeypatch.setattr(ws, "watermark_media_bytes", lambda raw, *a, **k: raw)


# ── The test the name is decided by ───────────────────────────────────────────

def _ffmpeg_sample(tmp_path, ext, args):
    out = tmp_path / f"sample.{ext}"
    done = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, str(out)],
                          capture_output=True)
    if done.returncode != 0 or not out.exists():
        pytest.skip(f"ffmpeg cannot write {ext} here")
    return out.read_bytes()


CONTAINERS = {
    "wav": ["-f", "lavfi", "-i", "sine=d=0.2"],
    "mp3": ["-f", "lavfi", "-i", "sine=d=0.2"],
    "flac": ["-f", "lavfi", "-i", "sine=d=0.2"],
    "ogg": ["-f", "lavfi", "-i", "sine=d=0.2", "-c:a", "libvorbis"],
    "m4a": ["-f", "lavfi", "-i", "sine=d=0.2", "-c:a", "aac"],
    "mp4": ["-f", "lavfi", "-i", "color=c=red:s=32x32:d=0.2", "-pix_fmt", "yuv420p"],
    "webm": ["-f", "lavfi", "-i", "color=c=red:s=32x32:d=0.2", "-c:v", "libvpx-vp9"],
}


@pytest.mark.parametrize("ext", sorted(CONTAINERS))
def test_every_container_the_platform_marks_carries_the_value(tmp_path, ext):
    """The name is decided by one test: is the IPTC value in the bytes. Every
    sound and film container has to pass it once marked, or a marked file
    would go out called unmarked."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("no ffmpeg")
    raw = _ffmpeg_sample(tmp_path, ext, CONTAINERS[ext])
    entity = "output_video" if ext in ("mp4", "webm") else "output_audio"
    assert not ws.carries_disclosure(raw)
    marked = ws.watermark_media_bytes(raw, entity, {"model": "t"})
    assert ws.carries_disclosure(marked), ext


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_every_picture_format_with_a_slot_carries_the_value(fmt):
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(out, format=fmt)
    raw = out.getvalue()
    assert not ws.carries_disclosure(raw)
    assert ws.carries_disclosure(ws.watermark_media_bytes(raw, "output_image", {"model": "t"}))


def test_3d_drawing_and_sketch_carry_the_value():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    sketch = b"function setup() {}\n"
    assert ws.carries_disclosure(ws.watermark_media_bytes(_glb_bytes(), "output_3d", {}))
    assert ws.carries_disclosure(ws.watermark_media_bytes(svg, "output_svg", {}))
    assert ws.carries_disclosure(ws.watermark_media_bytes(sketch, "output_p5", {}))


def test_the_algorithmic_value_counts_too():
    marked = ws.watermark_media_bytes(
        _png_bytes(), "output_image",
        {"digital_source_type": ws.DIGITAL_SOURCE_TYPE_ALGORITHMIC},
    )
    assert ws.DIGITAL_SOURCE_TYPE_AI.encode() not in marked
    assert ws.carries_disclosure(marked)


def test_what_counts_as_a_generated_medium():
    png = _png_bytes()
    assert ws.is_generated_medium(png, "output_image")
    assert ws.is_generated_medium(png, "generation")          # the canvas' own word
    assert ws.is_generated_medium(png, "latent_lab_step")
    assert ws.is_generated_medium(b"function setup() {}\n", "output_p5")
    assert ws.is_generated_medium(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60", "midi")
    # Never what a person brought in, never records, latents or JSON.
    assert not ws.is_generated_medium(png, "input_image")
    assert not ws.is_generated_medium(png, "upload_image")
    assert not ws.is_generated_medium(png, "recording")
    assert not ws.is_generated_medium(b"ein Prompt, kein Medium", "interception")
    assert not ws.is_generated_medium(b'{"a": 1}', "output_code")
    assert not ws.is_generated_medium(b"\x93NUMPY\x01\x00v\x00{'descr'", "output_latent")
    assert not ws.is_generated_medium("a string", "output_image")


@pytest.mark.parametrize("given,expected", [
    ("01_output_image.png", "01_output_image_ai_generated.png"),
    ("prompting_process/002_step_01.jpg", "prompting_process/002_step_01_ai_generated.jpg"),
    ("sung.mp3", "sung_ai_generated.mp3"),
    ("media", "media_ai_generated"),
    ("01_output_image_ai_generated.png", "01_output_image_ai_generated.png"),
    ("dir.v2/file", "dir.v2/file_ai_generated"),
    (".hidden", ".hidden_ai_generated"),
])
def test_the_suffix_goes_before_the_extension_once(given, expected):
    assert ws.unmarked_filename(given) == expected


# ── The writers ───────────────────────────────────────────────────────────────

def test_a_marked_medium_keeps_its_name(caplog):
    with caplog.at_level(logging.ERROR, logger=MARKING):
        content, name = mark_for_disk(_png_bytes(), "output_image", {}, "01_output_image.png", "[T]")
    assert name == "01_output_image.png"
    assert ws.carries_disclosure(content)
    assert not _errors(caplog)


def test_an_unmarked_medium_is_named_so_and_said_at_error(unmarking, caplog):
    with caplog.at_level(logging.ERROR, logger=MARKING):
        _, name = mark_for_disk(_png_bytes(), "output_image", {}, "01_output_image.png", "[T]")
    assert name == "01_output_image_ai_generated.png"
    assert any("01_output_image.png" in m and "AI-Origin Disclosure" in m for m in _errors(caplog))


def test_what_a_person_brought_in_is_never_named_ai_generated(unmarking, caplog):
    with caplog.at_level(logging.ERROR, logger=MARKING):
        _, name = mark_for_disk(_png_bytes(), "input_image", {}, "01_input_image.png", "[T]")
    assert name == "01_input_image.png"
    assert not _errors(caplog)


def test_an_animated_picture_is_named_so_without_any_fault_in_the_marking():
    """Left untouched by decision (one save would drop every frame but the
    first), so it carries nothing; its name carries it."""
    gif = _animated_gif_bytes()
    content, name = mark_for_disk(gif, "output_image", {}, "01_output_image.gif", "[T]")
    assert content == gif
    assert name == "01_output_image_ai_generated.gif"


def test_disclosed_name_for_what_goes_out_unstored(unmarking):
    assert disclosed_name(_png_bytes(), "output_audio", "speech.wav", "[T]") == "speech_ai_generated.wav"
    marked = ws.watermark_image_bytes(_png_bytes(), {})
    assert disclosed_name(marked, "output_media", "media", "[T]") == "media"


def _recorder(tmp_path, run_id):
    from my_app.services import pipeline_recorder as pr

    return pr.LivePipelineRecorder(
        run_id=run_id, config_name="sd35_large", safety_level="open",
        device_id="a-device", base_path=tmp_path,
    )


def test_the_pipeline_recorder_stores_and_records_the_name(tmp_path, unmarking):
    recorder = _recorder(tmp_path, "run_unmarked")
    filename = recorder.save_entity("output_image", _png_bytes(), {"format": "png"})
    assert filename.endswith(f"_output_image{SUFFIX}.png")
    assert (recorder.final_folder / filename).is_file()
    stored = json.loads((recorder.run_folder / "metadata.json").read_text(encoding="utf-8"))
    assert stored["entities"][-1]["filename"] == filename


def test_the_pipeline_recorder_keeps_the_name_of_a_marked_medium(tmp_path):
    recorder = _recorder(tmp_path, "run_marked")
    filename = recorder.save_entity("output_image", _png_bytes(), {"format": "png"})
    assert SUFFIX not in filename
    assert ws.carries_disclosure((recorder.final_folder / filename).read_bytes())


def test_the_canvas_recorder_stores_and_records_the_name(tmp_path, unmarking):
    from my_app.services import canvas_recorder as cr

    recorder = cr.CanvasRecorder(run_id="canvas_unmarked", workflow={"nodes": []},
                                 device_id="a-device", base_path=tmp_path)
    recorder.save_entity(node_id="n1", node_type="generation",
                         content=_png_bytes(), metadata={"format": "png"})
    entity = recorder.metadata["entities"][-1]
    assert entity["filename"].endswith(f"_generation{SUFFIX}.png")
    assert (recorder.final_folder / entity["filename"]).is_file()


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", str(tmp_path))
    return tmp_path


def _b64_png(color=(10, 120, 200)) -> str:
    return base64.b64encode(_png_bytes(color)).decode("ascii")


def _lab_folder(storage, run_id):
    return next(Path(storage).glob(f"*/*/{run_id}"))


def test_the_lab_recorder_names_its_step_and_its_output(storage, unmarking):
    from my_app.services import latent_lab_recorder as lab

    recorder = lab.LatentLabRecorder("sitting_u", "mean_images", device_id="dev",
                                     base_path=storage)
    written = recorder.record(
        parameters={"part": "cell"},
        outputs=[{"type": "image", "format": "png", "dataBase64": _b64_png()}],
        steps=[{"format": "png", "dataBase64": _b64_png()}],
    )
    folder = _lab_folder(storage, written["run_id"])
    record = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    by_type = {e["type"]: e["filename"] for e in record["entities"]}
    assert by_type["latent_lab_step"] == f"prompting_process/002_step_01{SUFFIX}.png"
    assert (folder / by_type["latent_lab_step"]).is_file()
    assert by_type["output_image"].endswith(f"_output_image{SUFFIX}.png")
    assert (folder / "final" / by_type["output_image"]).is_file()


def test_a_plate_is_set_under_the_name_its_bytes_call_for(storage, monkeypatch):
    """Fail-open like every other write: an unmarked plate is set, under
    `_ai_generated`, and a marked one set after it goes back to the plain name."""
    from my_app.services import latent_lab_recorder as lab

    recorder = lab.LatentLabRecorder("sitting_p", "attention_cartography",
                                     device_id="dev", base_path=storage)
    written = recorder.record(
        parameters={"part": "plate"},
        outputs=[{"type": "image", "format": "png", "dataBase64": _b64_png(),
                  "meta": {"plate": "reading"}}],
    )
    run_id = written["run_id"]
    folder = _lab_folder(storage, run_id)
    plain = next((folder / "final").glob("*_output_image.png")).name
    suffixed = ws.unmarked_filename(plain)

    def recorded_name():
        record = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        return next(e["filename"] for e in record["entities"] if e["type"] == "output_image")

    marking = ws.watermark_media_bytes
    monkeypatch.setattr(ws, "watermark_media_bytes", lambda raw, *a, **k: raw)
    red = base64.b64decode(_b64_png((200, 0, 0)))
    answer = lab.replace_output_image(run_id, 0, _b64_png((200, 0, 0)),
                                      device_id="dev", base_path=storage)
    assert answer["ok"] is True
    assert recorded_name() == suffixed
    assert (folder / "final" / suffixed).read_bytes() == red
    assert not (folder / "final" / plain).exists()

    monkeypatch.setattr(ws, "watermark_media_bytes", marking)
    answer = lab.replace_output_image(run_id, 0, _b64_png((0, 200, 0)),
                                      device_id="dev", base_path=storage)
    assert answer["ok"] is True
    assert recorded_name() == plain
    assert ws.carries_disclosure((folder / "final" / plain).read_bytes())
    assert not (folder / "final" / suffixed).exists()


def test_a_copy_taken_by_reference_keeps_the_name_of_its_source(storage, monkeypatch):
    from my_app.services import latent_lab_recorder as lab

    source = _recorder(storage, "run_source")
    monkeypatch.setattr(ws, "watermark_media_bytes", lambda raw, *a, **k: raw)
    stored = source.save_entity("output_image", _png_bytes(), {"format": "png"})
    assert SUFFIX in stored

    recorder = lab.LatentLabRecorder("sitting_r", "mean_images", device_id="a-device",
                                     base_path=storage)
    written = recorder.record(
        parameters={"part": "cell"},
        outputs=[{"type": "image", "format": "png", "ref": "/api/media/image/run_source/0"}],
        level="adult",
    )
    folder = _lab_folder(storage, written["run_id"])
    record = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    name = next(e["filename"] for e in record["entities"] if e["type"] == "output_image")
    assert name.endswith(f"_output_image{SUFFIX}.png")
    assert (folder / "final" / name).read_bytes() == (source.final_folder / stored).read_bytes()


def test_a_part_says_its_name_only_where_it_carries_the_suffix(tmp_path, monkeypatch):
    from flask import Flask

    from my_app.routes import latent_lab_recorder_routes as routes

    app = Flask(__name__)
    app.register_blueprint(routes.latent_lab_recorder_bp)
    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "adult")
    for name, says in ((f"002_step_01{SUFFIX}.png", True), ("002_step_02.png", False)):
        part = tmp_path / name
        part.write_bytes(_png_bytes())
        monkeypatch.setattr(routes, "resolve_part_path", lambda *a, _p=part, **k: _p)
        answer = app.test_client().get("/api/latent-lab/run/lab_x/part/0")
        assert answer.status_code == 200
        assert (SUFFIX in answer.headers.get("Content-Disposition", "")) is says


# ── What goes out ─────────────────────────────────────────────────────────────

def test_a_stored_unmarked_file_is_served_under_the_name(tmp_path):
    from my_app.routes.media_routes import _served_name

    assert _served_name("run_7.png", tmp_path / f"03_output_image{SUFFIX}.png") == f"run_7{SUFFIX}.png"
    assert _served_name("run_7.png", tmp_path / "03_output_image.png") == "run_7.png"


def test_the_parrot_serves_a_sung_answer_named_so(tmp_path, monkeypatch):
    from flask import Flask

    from my_app.routes import parrot_routes
    from my_app.services import parrot_service

    (tmp_path / f"sung{SUFFIX}.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    monkeypatch.setattr(parrot_service, "recording_dir", lambda rid: str(tmp_path))
    app = Flask(__name__)
    app.register_blueprint(parrot_routes.parrot_bp)
    rule = next(r for r in app.url_map.iter_rules() if r.endpoint.endswith(".sung"))
    answer = app.test_client().get(rule.rule.replace("<recording_id>", "r1"))
    assert answer.status_code == 200
    assert SUFFIX in answer.headers.get("Content-Disposition", "")


# ── The stored files from before the marking reached them ────────────────────

def _load_script():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "mark_stored_media.py"
    spec = importlib.util.spec_from_file_location("mark_stored_media", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _old_run(root: Path) -> Path:
    run = root / "2026-03-01" / "dev_2026-03-01" / "run_old"
    (run / "final").mkdir(parents=True)
    (run / "final" / "01_input_image.png").write_bytes(_png_bytes((1, 1, 1)))
    (run / "final" / "02_output_image.png").write_bytes(_png_bytes((2, 2, 2)))
    (run / "final" / "03_output_image.gif").write_bytes(_animated_gif_bytes())
    (run / "final" / "04_output_image.png").write_bytes(
        ws.watermark_image_bytes(_png_bytes((4, 4, 4)), {}))
    record = {"entities": [
        {"type": "input_image", "filename": "01_input_image.png",
         "timestamp": "2026-03-01T10:00:00"},
        {"type": "output_image", "filename": "02_output_image.png",
         "timestamp": "2026-03-01T10:01:00", "metadata": {"model": "sd35"}},
        {"type": "output_image", "filename": "03_output_image.gif",
         "timestamp": "2026-03-01T10:02:00"},
        {"type": "output_image", "filename": "04_output_image.png",
         "timestamp": "2026-03-01T10:03:00"},
    ]}
    (run / "metadata.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    old = time.time() - 7200
    os.utime(run / "metadata.json", (old, old))
    return run


def test_the_script_counts_and_writes_nothing_by_default(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    before = {p.name: p.read_bytes() for p in (run / "final").iterdir()}
    assert _load_script().main(["--root", str(root), "--backup-dir", str(tmp_path / "b")]) == 0
    assert {p.name: p.read_bytes() for p in (run / "final").iterdir()} == before
    assert not (tmp_path / "b").exists()


def test_the_script_marks_old_files_in_place_and_names_the_rest(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    backup = tmp_path / "originals"
    person = (run / "final" / "01_input_image.png").read_bytes()
    already = (run / "final" / "04_output_image.png").read_bytes()

    assert _load_script().main(["--root", str(root), "--backup-dir", str(backup), "--apply"]) == 0

    marked = (run / "final" / "02_output_image.png").read_bytes()
    assert ws.carries_disclosure(marked)
    # The marking names the day the run recorded, not the day it was marked.
    assert b"2026-03-01T10:01:00" in marked
    assert (run / "final" / "01_input_image.png").read_bytes() == person
    assert (run / "final" / "04_output_image.png").read_bytes() == already
    # The animated picture keeps its bytes and gets the name; its record follows.
    assert not (run / "final" / "03_output_image.gif").exists()
    assert (run / "final" / f"03_output_image{SUFFIX}.gif").is_file()
    record = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    assert record["entities"][2]["filename"] == f"03_output_image{SUFFIX}.gif"
    # Originals of what was replaced or rewritten, outside the storage.
    rel = run.relative_to(root)
    assert (backup / rel / "final" / "02_output_image.png").read_bytes() != marked
    assert (backup / rel / "metadata.json").is_file()
    assert not (backup / rel / "final" / "01_input_image.png").exists()


def test_the_script_leaves_a_run_that_is_still_being_written(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    os.utime(run / "metadata.json", None)
    raw = (run / "final" / "02_output_image.png").read_bytes()
    _load_script().main(["--root", str(root), "--backup-dir", str(tmp_path / "b"), "--apply"])
    assert (run / "final" / "02_output_image.png").read_bytes() == raw


def test_the_script_refuses_a_backup_inside_the_storage(tmp_path):
    root = tmp_path / "json"
    _old_run(root)
    assert _load_script().main(["--root", str(root), "--backup-dir", str(root / "b"), "--apply"]) == 2


def test_the_script_leaves_a_sketch_that_is_the_prompt_of_its_run(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    prompt = b"Ein geheimnisvoller Wald bei Nacht"
    (run / "final" / "05_input.txt").write_bytes(prompt)
    (run / "final" / "06_p5.js").write_bytes(prompt + b"\n")
    record = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    record["entities"] += [{"type": "input", "filename": "05_input.txt"},
                           {"type": "p5", "filename": "06_p5.js"}]
    (run / "metadata.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    old = time.time() - 7200
    os.utime(run / "metadata.json", (old, old))

    assert _load_script().main(["--root", str(root), "--backup-dir", str(tmp_path / "o"), "--apply"]) == 0
    assert (run / "final" / "06_p5.js").read_bytes() == prompt + b"\n"


def test_the_script_marks_generated_code_that_is_also_the_generation_prompt(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    code = b"function setup() { createCanvas(400, 400); }\n"
    (run / "final" / "05_generation_prompt.txt").write_bytes(code)
    (run / "final" / "06_p5.js").write_bytes(code)
    (run / "final" / "07_generation_prompt.txt").write_bytes(b"a quiet forest at night")
    (run / "final" / "08_p5.js").write_bytes(b"a quiet forest at night")
    record = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    record["entities"] += [{"type": "generation_prompt", "filename": "05_generation_prompt.txt"},
                           {"type": "p5", "filename": "06_p5.js"},
                           {"type": "generation_prompt", "filename": "07_generation_prompt.txt"},
                           {"type": "p5", "filename": "08_p5.js"}]
    (run / "metadata.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    old = time.time() - 7200
    os.utime(run / "metadata.json", (old, old))

    assert _load_script().main(["--root", str(root), "--backup-dir", str(tmp_path / "o"), "--apply"]) == 0
    assert ws.carries_disclosure((run / "final" / "06_p5.js").read_bytes())
    assert (run / "final" / "08_p5.js").read_bytes() == b"a quiet forest at night"


def test_the_script_renames_only_what_has_no_place_for_it(tmp_path, monkeypatch):
    """A marking that failed is left for a second run, not named for good."""
    root = tmp_path / "json"
    run = _old_run(root)
    script = _load_script()
    monkeypatch.setattr(script, "watermark_media_bytes", lambda raw, *a, **k: raw)
    assert script.main(["--root", str(root), "--backup-dir", str(tmp_path / "o"), "--apply"]) == 0
    assert (run / "final" / "02_output_image.png").is_file()
    assert (run / "final" / f"03_output_image{SUFFIX}.gif").is_file()


def test_the_script_marks_an_output_no_record_names(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    loose = run / "final" / "07_output_image.png"
    loose.write_bytes(_png_bytes((7, 7, 7)))
    old = time.time() - 7200
    os.utime(loose, (old, old))
    assert _load_script().main(["--root", str(root), "--backup-dir", str(tmp_path / "o"), "--apply"]) == 0
    assert ws.carries_disclosure(loose.read_bytes())


def test_the_script_takes_a_medium_in_a_run_folder_as_its_output(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    old = time.time() - 7200
    canvas = run / "final" / "02_image.png"
    legacy = run / "output_image.png"
    film = run / "final" / "06_output_video.png.webp"
    brought = run / "final" / "05_input_photo.png"
    # Colours of their own: a medium with the bytes of the run's input is a
    # copy of what a person brought in and is left alone.
    for path, colour in ((canvas, (31, 31, 31)), (legacy, (32, 32, 32)), (brought, (34, 34, 34))):
        path.write_bytes(_png_bytes(colour))
        os.utime(path, (old, old))
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8), (33, 33, 33)).save(out, format="WEBP")
    film.write_bytes(out.getvalue())
    os.utime(film, (old, old))
    before = brought.read_bytes()
    assert _load_script().main(["--root", str(root), "--backup-dir", str(tmp_path / "o"), "--apply"]) == 0
    assert ws.carries_disclosure(canvas.read_bytes())
    assert ws.carries_disclosure(legacy.read_bytes())
    assert ws.carries_disclosure(film.read_bytes())
    assert brought.read_bytes() == before


def test_the_script_puts_a_record_right_that_an_interruption_left(tmp_path):
    root = tmp_path / "json"
    run = _old_run(root)
    (run / "final" / "03_output_image.gif").rename(run / "final" / f"03_output_image{SUFFIX}.gif")
    assert _load_script().main(["--root", str(root), "--backup-dir", str(tmp_path / "o"), "--apply"]) == 0
    record = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    assert record["entities"][2]["filename"] == f"03_output_image{SUFFIX}.gif"


def test_the_script_refuses_a_used_backup_and_a_switched_off_marking(tmp_path, monkeypatch):
    import config

    root = tmp_path / "json"
    _old_run(root)
    used = tmp_path / "used"
    used.mkdir()
    (used / "x").write_text("x")
    script = _load_script()
    assert script.main(["--root", str(root), "--backup-dir", str(used), "--apply"]) == 2
    monkeypatch.setattr(config, "WATERMARK", {**config.WATERMARK, "metadata_audio": False})
    assert script.main(["--root", str(root), "--backup-dir", str(tmp_path / "o"), "--apply"]) == 2


# -- What the marking leaves of a file ----------------------------------------

def _png_with_chunks() -> bytes:
    from PIL import Image, PngImagePlugin

    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", '{"3": {"class_type": "KSampler"}}')
    info.add_text("parameters", "Steps: 30, Sampler: euler")
    out = io.BytesIO()
    Image.new("RGBA", (8, 8), (1, 2, 3, 200)).save(out, format="PNG", pnginfo=info, dpi=(300, 300))
    return out.getvalue()


def test_a_png_keeps_its_chunks_and_its_pixels_when_marked():
    from PIL import Image

    raw = _png_with_chunks()
    marked = ws.watermark_image_bytes(raw, {"model": "sd35"})
    assert ws.carries_disclosure(marked)
    with Image.open(io.BytesIO(raw)) as a, Image.open(io.BytesIO(marked)) as b:
        assert a.tobytes() == b.tobytes()
        assert b.info["prompt"] == a.info["prompt"]
        assert b.info["parameters"] == a.info["parameters"]
        assert round(b.info["dpi"][0]) == 300
        assert b.info["DigitalSourceType"] == ws.DIGITAL_SOURCE_TYPE_AI
        assert "XML:com.adobe.xmp" in b.info
    # The IDAT chunks are the same bytes: nothing was encoded again.
    assert raw[raw.index(b"IDAT") - 4:] in marked
    # Marked a second time with a corrected value, the old chunks go.
    again = ws.watermark_image_bytes(marked, {"digital_source_type": ws.DIGITAL_SOURCE_TYPE_ALGORITHMIC})
    assert again.count(b"DigitalSourceType\x00") == 1
    assert ws.DIGITAL_SOURCE_TYPE_AI.encode() not in again


def test_a_disclosure_only_in_a_compressed_chunk_is_written_again_plainly():
    from PIL import Image, PngImagePlugin

    info = PngImagePlugin.PngInfo()
    info.add_itxt("DigitalSourceType", ws.DIGITAL_SOURCE_TYPE_AI, zip=True)
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (9, 9, 9)).save(out, format="PNG", pnginfo=info)
    raw = out.getvalue()
    assert not ws.carries_disclosure(raw)
    assert ws.carries_disclosure(ws.watermark_image_bytes(raw, {}))


@pytest.mark.parametrize("ext,head", [("webm", b"\x1aE\xdf\xa3"), ("mp4", None)])
def test_a_film_stays_in_its_container(tmp_path, ext, head):
    if shutil.which("ffmpeg") is None:
        pytest.skip("no ffmpeg")
    raw = _ffmpeg_sample(tmp_path, ext, CONTAINERS[ext])
    marked = ws.watermark_media_bytes(raw, "output_video", {"model": "t"})
    assert ws.carries_disclosure(marked)
    if head:
        assert marked.startswith(head)
    else:
        assert marked[4:8] == b"ftyp"
        # The index stays in front, where a browser starts playing from.
        assert marked.index(b"moov") < marked.index(b"mdat")


def test_svg_text_of_a_record_is_no_drawing():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    assert ws.watermark_media_bytes(svg, "interception", {}) == svg
    assert not ws.is_generated_medium(svg, "interception")
    assert ws.is_generated_medium(svg, "output_image")


def test_a_name_loses_the_suffix_once_its_bytes_carry_the_disclosure():
    marked = ws.watermark_image_bytes(_png_bytes(), {})
    assert disclosed_name(marked, "output_image", f"02_output_image{SUFFIX}.png", "[T]") == "02_output_image.png"
    assert ws.plain_filename(f"a/b{SUFFIX}.png") == "a/b.png"


def test_a_miniature_says_whether_it_carries_the_disclosure(tmp_path):
    from my_app.services.thumbnails import build_thumbnail, served_thumbnail_name

    plain = tmp_path / "plain.png"
    plain.write_bytes(_png_bytes())
    marked = tmp_path / "marked.png"
    marked.write_bytes(ws.watermark_image_bytes(_png_bytes(), {}))
    for source, says in ((plain, True), (marked, False)):
        thumb = tmp_path / f"{source.stem}_thumb.jpg"
        assert build_thumbnail(source, thumb, "image")
        assert (SUFFIX in served_thumbnail_name(thumb)) is says


def test_the_miniature_of_a_marked_film_carries_the_marking(tmp_path):
    from my_app.services.thumbnails import build_thumbnail

    if shutil.which("ffmpeg") is None:
        pytest.skip("no ffmpeg")
    film = tmp_path / "film.mp4"
    film.write_bytes(ws.watermark_media_bytes(
        _ffmpeg_sample(tmp_path, "mp4", CONTAINERS["mp4"]), "output_video", {}))
    thumb = tmp_path / "film_thumb.jpg"
    assert build_thumbnail(film, thumb, "video")
    assert ws.carries_disclosure(thumb.read_bytes())


def test_the_restore_script_types_a_file_named_so():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "restore_entities_lost_from_record.py"
    spec = importlib.util.spec_from_file_location("restore_entities", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    named = module.NAMED.match(f"03_output_image{SUFFIX}.png")
    assert named.group(2) == "output_image"
    assert named.group(3) == "png"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
