"""
The LoRA register (issue #70): what a run may load, and to whom a surface
offers an adapter.

  1. Release: a platform row reaches every session, a course row the sessions
     of that course alone, a row released nowhere reaches nobody but the user
     who trained it.
  2. What reaches the workflow (`loras_for_run`): the register decides who is
     offered an adapter and the ADAPTER FILE decides which model carries it
     (section 6; nobody ticks a model off by hand since 2026-09-22). The file
     name decides nothing. A perspective's LoRA the register does not know,
     does not offer to this session, or whose file is gone is left out; one the
     output config cannot carry is left out; a requested file the session is
     not offered is refused; the hand's strength wins over the perspective's
     for the same file; strength is clamped; the trigger tags of the applied
     adapters go in front of the prompt once each, and a tag the prompt already
     carries stays where it is.
  3. The routes: the listing is open and scoped by the platform's rule for a
     course named by the client; the register is admin-only.
  4. The training place writes a row that names the file the trainer will
     write, released to the course the training was made in, and no row
     outside a course; a row that exists is never rewritten by a training.
  5. The seed: the presets' own adapters get their row once, with the trigger
     term the preset names; an admin's change stands.

The whole Lab DB is redirected to a throwaway file via AI4ARTSED_DB_PATH, set
BEFORE importing the lab modules (db.py binds its engine at import time), and
the LoRA folder to a throwaway directory so `present` is about files this test
put there.

Run: venv/bin/python -m pytest devserver/tests/test_lora_register.py -q
"""
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp(prefix="lora_register_test_"))
os.environ["AI4ARTSED_DB_PATH"] = str(_TMP / "lab_test.db")

import pytest
from flask import Flask

from my_app.lab.db import Base, engine, SessionLocal
from my_app.lab import models as M
from my_app.lab.auth_service import hash_password
from my_app.routes.auth_routes import auth_bp
from my_app.routes.lora_routes import loras_bp
from my_app.services import lora_base as B
from my_app.services import lora_register as R

_LORA_DIR = _TMP / "loras"
_LORA_DIR.mkdir()

# Output configs of this repo and the bases they name (`meta.lora_base`).
SD = "sd35_large"
SD_DIFF = "sd35_large_diffusers"
SD_IMG = "sd35_large_img2img"
SD_TURBO = "sd35_large_turbo"
FLUX = "flux2"
FLUX_IMG = "flux2_img2img"
SDXL = "sdxl"
CANVAS = "commoncanvas_xl_c"
CANVAS_DIFF = "commoncanvas_xl_c_diffusers"
SD15 = "sd15"
# The configs an SD 3.5 adapter reaches, in the order `configs_for` answers
# (the configs are read in sorted order). SD 3.5 Large and Large Turbo hold the
# same 1167 tensors in the same shapes, so an adapter of the one fits the other.
SD_CFGS = [SD, SD_DIFF, SD_IMG, SD_TURBO]
# What a trainer writes into an adapter's header. Every SD 3.5 training of this
# place carries the SAI model spec's architecture with `/lora` on the end; the
# Flux 2 adapter in the real folder carries the trainer's own field instead, so
# both are exercised.
SD_BASE = "stable-diffusion-3-5-large"
SD_TURBO_BASE = "stable-diffusion-3-5-large-turbo"
FLUX_BASE = "flux2"


@pytest.fixture(autouse=True)
def clean_schema(monkeypatch):
    monkeypatch.setattr(R, "LORA_OUTPUT_DIR", _LORA_DIR)
    monkeypatch.setattr(B, "LORA_OUTPUT_DIR", _LORA_DIR)
    B.forget()
    for p in _LORA_DIR.glob("*"):
        p.unlink()
    SessionLocal.remove()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    SessionLocal.remove()


@pytest.fixture
def app():
    a = Flask(__name__)
    a.secret_key = "test-secret"
    a.register_blueprint(auth_bp)
    a.register_blueprint(loras_bp)
    yield a
    SessionLocal.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _touch(file: str, base: str = SD_BASE, trainer_field: bool = False) -> None:
    """Put a real adapter in the folder: eight bytes of length and that many
    bytes of JSON header, which is what `lora_base` reads. A `base` of "" writes
    a file that names no model, as the video accelerators in the real folder do.
    """
    fields = {}
    if base:
        fields["ss_base_model_version" if trainer_field else "modelspec.architecture"] = (
            base if trainer_field else f"{base}/lora"
        )
    head = json.dumps({"__metadata__": fields} if fields else {}).encode("utf-8")
    (_LORA_DIR / file).write_bytes(struct.pack("<Q", len(head)) + head)
    B.forget(file)


def _course(name="Herbstkurs") -> int:
    db = SessionLocal()
    c = M.Course(name=name)
    db.add(c)
    db.commit()
    return c.id


def _place(course_id) -> str:
    """Open the course for an hour and give it a place; return the place's code."""
    import datetime as _dt
    from my_app.lab.place_codes import issue_code
    db = SessionLocal()
    db.get(M.Course, course_id).access_until = (
        _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=1)
    )
    u = M.User(role=M.Role.participant, password_hash="!")
    db.add(u)
    db.flush()
    place = M.CourseMembership(course_id=course_id, user_id=u.id, place_number=1)
    db.add(place)
    db.flush()
    code = issue_code(db, place)
    db.commit()
    return code


def _user(role, username, password="secret12") -> int:
    db = SessionLocal()
    u = M.User(
        email=None, username=username, role=role, display_name=username,
        password_hash=hash_password(password), is_active=True,
    )
    db.add(u)
    db.commit()
    return u.id


def _leads(user_id: int, course_id: int) -> None:
    db = SessionLocal()
    db.add(M.CourseEducator(course_id=course_id, user_id=user_id, role_in_course=M.CourseRole.owner))
    db.commit()


def _login(client, identifier, password="secret12"):
    return client.post("/api/auth/login", json={"identifier": identifier, "password": password})


# ---------------------------------------------------------------------------
# 1) release
# ---------------------------------------------------------------------------
def test_release_decides_who_is_offered():
    course = _course()
    other = _course("Winterkurs")
    owner = _user(M.Role.participant, "mia")
    _touch("sd35_solarization.safetensors")
    R.register_adapter("sd35_solarization.safetensors", "solarization", "solarization",
                       visibility="platform")
    R.register_adapter("sd35_kurs.safetensors", "Kurs-LoRA", "kurs",
                       course_id=course, visibility="course")
    R.register_adapter("sd35_privat.safetensors", "privat", "privat",
                       owner_id=owner, visibility="none")

    nobody = {r["file"] for r in R.visible_adapters(None)}
    assert nobody == {"sd35_solarization.safetensors"}
    member = {r["file"] for r in R.visible_adapters(course)}
    assert member == {"sd35_solarization.safetensors", "sd35_kurs.safetensors"}
    elsewhere = {r["file"] for r in R.visible_adapters(other)}
    assert elsewhere == {"sd35_solarization.safetensors"}
    # The one who trained it sees it, released nowhere or not.
    mine = {r["file"] for r in R.visible_adapters(None, owner)}
    assert mine == {"sd35_solarization.safetensors", "sd35_privat.safetensors"}

    rows = {r["file"]: r for r in R.visible_adapters(course)}
    assert rows["sd35_solarization.safetensors"]["present"] is True
    assert rows["sd35_kurs.safetensors"]["present"] is False
    assert rows["sd35_kurs.safetensors"]["course_name"] == "Herbstkurs"
    assert {r["file"]: r["owner_name"] for r in R.all_adapters()}["sd35_privat.safetensors"] == "mia"


def test_what_a_row_must_say():
    with pytest.raises(ValueError):
        R.register_adapter("sd35_x.safetensors", "x", "", visibility="course")
    with pytest.raises(ValueError):
        R.register_adapter("../sd35_x.safetensors", "x", "", visibility="platform")
    with pytest.raises(ValueError):
        R.register_adapter(".safetensors", "x", "", visibility="platform")
    with pytest.raises(ValueError):
        R.register_adapter("sd35_x.safetensors", "x", "", visibility="everyone")
    with pytest.raises(ValueError, match="no course"):
        R.register_adapter("sd35_x.safetensors", "x", "", course_id=999, visibility="course")
    assert R.all_adapters() == []


def test_registering_a_file_again_overwrites_its_row_unless_told_to_keep_it():
    R.register_adapter("sd35_x.safetensors", "x", "x", visibility="none")
    R.register_adapter("sd35_x.safetensors", "X neu", "xx", visibility="platform")
    rows = R.all_adapters()
    assert len(rows) == 1
    assert rows[0]["name"] == "X neu"
    assert rows[0]["trigger"] == "xx"
    # No file of that name lies in the folder, so nothing says what it was
    # trained over and no model carries it — an overwrite cannot change that.
    assert rows[0]["base"] == "" and rows[0]["base_configs"] == []
    assert rows[0]["visibility"] == "platform"
    # The training place and the seed never rewrite what stands.
    R.register_adapter("sd35_x.safetensors", "fremd", "böse", visibility="none", keep_existing=True)
    rows = R.all_adapters()
    assert rows[0]["name"] == "X neu" and rows[0]["trigger"] == "xx" and rows[0]["visibility"] == "platform"


def test_a_row_whose_course_was_deleted_can_still_be_changed():
    course = _course()
    row = R.register_adapter("sd35_kurs.safetensors", "kurs", "kurs", course_id=course, visibility="course")
    db = SessionLocal()
    db.delete(db.get(M.Course, course))
    db.commit()
    SessionLocal.remove()
    changed = R.update_adapter(row["id"], {"name": "Kurs von einst"})
    assert changed["name"] == "Kurs von einst" and changed["course_id"] is None
    with pytest.raises(ValueError):
        R.update_adapter(row["id"], {"visibility": "course"})
    assert R.update_adapter(row["id"], {"visibility": "platform"})["visibility"] == "platform"


def test_unregistered_files_are_what_the_folder_has_and_the_register_lacks(monkeypatch, tmp_path):
    from my_app.services import training_service as T
    monkeypatch.setattr(T, "DATASET_BASE_DIR", tmp_path / "datasets")
    project = tmp_path / "datasets" / "Sonne"
    project.mkdir(parents=True)
    (project / T.TRIGGER_FILE).write_text("sonne, gelb", encoding="utf-8")

    _touch("sd35_solarization.safetensors")
    _touch("sd35_Sonne-000004.safetensors")
    _touch("wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors", "")
    R.register_adapter("sd35_solarization.safetensors", "solarization", "", visibility="platform")
    entries = {e["file"]: e for e in R.unregistered_files()}
    assert set(entries) == {
        "sd35_Sonne-000004.safetensors",
        "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
    }
    # A training of this place comes with its own record: name and trigger.
    sonne = entries["sd35_Sonne-000004.safetensors"]
    assert sonne["name"] == "Sonne"
    assert sonne["trigger"] == "sonne, gelb"
    # The model is the file's own word, here as everywhere.
    assert sonne["base"] == SD_BASE
    assert sonne["base_configs"] == SD_CFGS
    # An accelerator of the video pipelines names no model and carries none.
    acc = entries["wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors"]
    assert acc["trigger"] == "" and acc["base"] == "" and acc["base_configs"] == []


# ---------------------------------------------------------------------------
# 2) what reaches the workflow
# ---------------------------------------------------------------------------
def _platform(file, trigger, base=SD_BASE):
    _touch(file, base)
    R.register_adapter(file, file, trigger, visibility="platform")


def test_the_perspectives_lora_is_applied_only_where_the_register_carries_it():
    _platform("sd3.5-large_cooked_negatives-000004.safetensors", "cooked film")
    cfg = [{"name": "sd3.5-large_cooked_negatives-000004.safetensors", "strength": 0.9}]

    applied, triggers = R.loras_for_run(cfg, None, SD, None)
    assert applied == [{"name": "sd3.5-large_cooked_negatives-000004.safetensors", "strength": 0.9}]
    assert triggers == ["cooked film"]

    # A hand-picked Flux 2 with that perspective in the ring: left out.
    applied, triggers = R.loras_for_run(cfg, None, FLUX, None)
    assert applied == [] and triggers == []

    # Unknown to the register: left out, whatever its name says.
    applied, triggers = R.loras_for_run(
        [{"name": "sd35_19th_century_photography_landscape-000004.safetensors", "strength": 0.9}],
        None, SD, None)
    assert applied == [] and triggers == []


def test_the_perspectives_lora_follows_the_release_and_the_folder():
    course = _course()
    _touch("sd35_kurs.safetensors")
    R.register_adapter("sd35_kurs.safetensors", "kurs", "kurs", course_id=course, visibility="course")
    cfg = [{"name": "sd35_kurs.safetensors", "strength": 0.9}]
    # Released to a course: applied in that course, left out elsewhere — the
    # surface marks it by the same rule.
    assert R.loras_for_run(cfg, None, SD, course)[0] == [{"name": "sd35_kurs.safetensors", "strength": 0.9}]
    assert R.loras_for_run(cfg, None, SD, None) == ([], [])
    assert R.loras_for_run(cfg, None, SD, _course("Winterkurs")) == ([], [])
    # The file is gone: left out, not put into a workflow ComfyUI rejects.
    (_LORA_DIR / "sd35_kurs.safetensors").unlink()
    assert R.loras_for_run(cfg, None, SD, course) == ([], [])


def test_a_requested_lora_the_session_is_not_offered_is_refused():
    course = _course()
    owner = _user(M.Role.participant, "mia")
    _touch("sd35_kurs.safetensors")
    _touch("sd35_privat.safetensors")
    R.register_adapter("sd35_kurs.safetensors", "kurs", "kurs", course_id=course, visibility="course")
    R.register_adapter("sd35_privat.safetensors", "privat", "privat", owner_id=owner, visibility="none")
    with pytest.raises(ValueError):
        R.loras_for_run(None, [{"name": "sd35_kurs.safetensors", "strength": 1.0}], SD, None)
    with pytest.raises(ValueError):
        R.loras_for_run(None, [{"name": "sd35_nirgends.safetensors", "strength": 1.0}], SD, course)
    applied, triggers = R.loras_for_run(None, [{"name": "sd35_kurs.safetensors", "strength": 1.0}], SD, course)
    assert applied == [{"name": "sd35_kurs.safetensors", "strength": 1.0}]
    assert triggers == ["kurs"]
    # The owner lays their own training, released nowhere.
    with pytest.raises(ValueError):
        R.loras_for_run(None, [{"name": "sd35_privat.safetensors", "strength": 1.0}], SD, course)
    applied, _ = R.loras_for_run(None, [{"name": "sd35_privat.safetensors", "strength": 1.0}], SD, None, owner)
    assert applied == [{"name": "sd35_privat.safetensors", "strength": 1.0}]


def test_a_requested_lora_whose_file_is_absent_is_refused():
    R.register_adapter("sd35_weg.safetensors", "weg", "weg", visibility="platform")
    with pytest.raises(ValueError, match="absent"):
        R.loras_for_run(None, [{"name": "sd35_weg.safetensors", "strength": 1.0}], SD, None)


def test_a_requested_lora_the_config_cannot_carry_is_left_out_not_refused():
    _platform("sd35_solarization.safetensors", "solarization")
    applied, triggers = R.loras_for_run(
        None, [{"name": "sd35_solarization.safetensors", "strength": 0.7}], FLUX, None)
    assert applied == [] and triggers == []


def test_strength_is_clamped_and_the_hands_strength_wins():
    _platform("sd35_solarization.safetensors", "solarization")
    applied, _ = R.loras_for_run(
        None, [{"name": "sd35_solarization.safetensors", "strength": 9}], SD, None)
    assert applied[0]["strength"] == 2.0
    applied, _ = R.loras_for_run(
        [{"name": "sd35_solarization.safetensors", "strength": 0.9}],
        [{"name": "sd35_solarization.safetensors", "strength": 0.6}], SD, None)
    assert applied == [{"name": "sd35_solarization.safetensors", "strength": 0.6}]
    with pytest.raises(ValueError):
        R.loras_for_run(None, [{"name": "sd35_solarization.safetensors", "strength": "stark"}], SD, None)


def test_triggers_stand_once_each_in_order_and_go_in_front_of_the_prompt():
    _platform("sd35_a.safetensors", "aaa")
    _platform("sd35_b.safetensors", "bbb")
    _platform("sd35_c.safetensors", "aaa")
    applied, triggers = R.loras_for_run(
        [{"name": "sd35_b.safetensors", "strength": 0.9}],
        [{"name": "sd35_a.safetensors", "strength": 1.0}, {"name": "sd35_c.safetensors", "strength": 1.0}],
        SD, None)
    assert [l["name"] for l in applied] == ["sd35_b.safetensors", "sd35_a.safetensors", "sd35_c.safetensors"]
    assert triggers == ["bbb", "aaa"]
    assert R.with_triggers("a quiet harbour", triggers) == "bbb, aaa, a quiet harbour"
    assert R.with_triggers("bbb, aaa, a quiet harbour", triggers) == "bbb, aaa, a quiet harbour"
    # A perspective that wrote the word into its text: nothing is put in front
    # of it a second time, and only the word that is missing goes in front.
    assert R.with_triggers("a harbour, shaped by AAA film", triggers) == "bbb, a harbour, shaped by AAA film"
    assert R.with_triggers("", triggers) == ""
    assert R.with_triggers(None, triggers) is None
    assert R.with_triggers("a quiet harbour", []) == "a quiet harbour"


def test_a_trigger_of_several_tags_goes_in_front_tag_by_tag():
    _platform("sd35_19th.safetensors", "19th_century_photography, landscape, historic photograph")
    applied, triggers = R.loras_for_run(None, [{"name": "sd35_19th.safetensors", "strength": 1.0}], SD, None)
    assert triggers == ["19th_century_photography", "landscape", "historic photograph"]
    # The preset made the interception write the first tag: only the others go in front.
    assert R.with_triggers("a valley, 19th_century_photography, sepia", triggers) == (
        "landscape, historic photograph, a valley, 19th_century_photography, sepia")


def test_nothing_asked_nothing_applied():
    assert R.loras_for_run(None, None, SD, None) == ([], [])
    assert R.loras_for_run([], [], SD, None) == ([], [])
    with pytest.raises(ValueError):
        R.loras_for_run(None, {"name": "x"}, SD, None)


# ---------------------------------------------------------------------------
# 3) the routes
# ---------------------------------------------------------------------------
def test_listing_is_open_and_scoped_by_the_platforms_course_rule(client):
    course = _course()
    other = _course("Winterkurs")
    _touch("sd35_solarization.safetensors")
    R.register_adapter("sd35_solarization.safetensors", "solarization", "solarization", visibility="platform")
    R.register_adapter("sd35_kurs.safetensors", "kurs", "kurs", course_id=course, visibility="course")
    R.register_adapter("sd35_winter.safetensors", "winter", "winter", course_id=other, visibility="course")

    # Anonymous: the platform's rows, whatever the client names.
    r = client.get("/api/loras")
    assert r.status_code == 200
    assert [x["file"] for x in r.get_json()["loras"]] == ["sd35_solarization.safetensors"]
    r = client.get(f"/api/loras?course_id={course}")
    assert [x["file"] for x in r.get_json()["loras"]] == ["sd35_solarization.safetensors"]

    # A place: the session's course, never the one the client names.
    code = _place(course)
    assert client.post("/api/auth/participant-login", json={"code": code}).status_code == 200
    files = lambda resp: {x["file"] for x in resp.get_json()["loras"]}
    assert files(client.get("/api/loras")) == {"sd35_solarization.safetensors", "sd35_kurs.safetensors"}
    assert files(client.get(f"/api/loras?course_id={other}")) == {"sd35_solarization.safetensors", "sd35_kurs.safetensors"}

    # An educator: the course they lead when they name it, nothing of a course they do not.
    eid = _user(M.Role.educator, "edu")
    _leads(eid, course)
    with client.session_transaction() as s:
        s.clear()
        s["user_id"], s["role"] = eid, "educator"
    assert files(client.get("/api/loras")) == {"sd35_solarization.safetensors"}
    assert files(client.get(f"/api/loras?course_id={course}")) == {"sd35_solarization.safetensors", "sd35_kurs.safetensors"}
    assert files(client.get(f"/api/loras?course_id={other}")) == {"sd35_solarization.safetensors"}


def test_register_is_admin_only(client):
    _user(M.Role.educator, "edu")
    assert client.get("/api/loras/register").status_code == 401
    _login(client, "edu")
    assert client.get("/api/loras/register").status_code == 403
    assert client.post("/api/loras/register", json={"file": "sd35_x.safetensors", "name": "x"}).status_code == 403


def test_admin_keeps_the_register(client):
    _user(M.Role.admin, "root")
    _login(client, "root")
    course = _course()
    _touch("sd35_solarization.safetensors")
    _touch("Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors", "")

    r = client.get("/api/loras/register")
    assert r.status_code == 200
    body = r.get_json()
    assert body["loras"] == []
    assert {e["file"] for e in body["unregistered"]} == {
        "sd35_solarization.safetensors", "Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors"}
    assert body["courses"] == [{"id": course, "name": "Herbstkurs"}]

    r = client.post("/api/loras/register", json={
        "file": "sd35_solarization.safetensors", "name": "solarization",
        "trigger": "solarization", "visibility": "platform"})
    assert r.status_code == 201
    row = r.get_json()
    assert row["present"] is True
    # The models are the file's word and reach the client with the row.
    assert row["base"] == SD_BASE and row["base_configs"] == SD_CFGS
    assert client.post("/api/loras/register", json={
        "file": "sd35_y.safetensors", "name": "y", "category": ["foto"]}).status_code == 400
    assert client.post("/api/loras/register", json={
        "file": "sd35_y.safetensors", "name": "y", "visibility": "course", "course_id": 999}).status_code == 400

    r = client.put(f"/api/loras/register/{row['id']}", json={"visibility": "course", "course_id": course})
    assert r.status_code == 200
    assert r.get_json()["visibility"] == "course"
    r = client.put(f"/api/loras/register/{row['id']}", json={"visibility": "course", "course_id": None})
    assert r.status_code == 400
    r = client.put(f"/api/loras/register/{row['id']}", json={"name": "  "})
    assert r.status_code == 400
    assert client.put("/api/loras/register/999", json={"name": "x"}).status_code == 404

    assert [e["file"] for e in client.get("/api/loras/register").get_json()["unregistered"]] == [
        "Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors"]

    assert client.delete(f"/api/loras/register/{row['id']}").status_code == 200
    assert client.delete(f"/api/loras/register/{row['id']}").status_code == 404
    assert client.get("/api/loras/register").get_json()["loras"] == []
    # The file stays where it is.
    assert (_LORA_DIR / "sd35_solarization.safetensors").exists()


# ---------------------------------------------------------------------------
# 4) the training place writes the row
# ---------------------------------------------------------------------------
def test_the_training_place_registers_what_it_will_write(monkeypatch, tmp_path):
    from my_app.services import training_service as T

    monkeypatch.setattr(T, "DATASET_BASE_DIR", tmp_path / "datasets")
    monkeypatch.setattr(T, "STAGING_DIR", tmp_path / "datasets" / ".staging")
    monkeypatch.setattr(T.TrainingService, "get_gpu_vram", lambda self: 96.0)
    svc = T.TrainingService()
    course = _course()
    owner = _user(M.Role.participant, "mia")

    def stage():
        staging = tmp_path / "datasets" / ".staging" / "tok"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "001.png").write_bytes(b"\x89PNG")

    stage()
    svc.create_project("Meine Sonne", [], "sonne, gelb", staging_token="tok",
                       captions=["ein Bild"], owner_id=owner, course_id=course)
    rows = R.all_adapters()
    assert len(rows) == 1
    assert rows[0]["file"] == f"{T.SD35_LORA_PREFIX}MeineSonne.safetensors"
    assert rows[0]["name"] == "Meine Sonne"
    assert rows[0]["trigger"] == "sonne, gelb"
    # The file the trainer will write is not there yet, so nothing names a
    # model: the models come from the file, and the file comes last.
    assert rows[0]["base"] == "" and rows[0]["base_configs"] == []
    assert rows[0]["visibility"] == "course"
    assert rows[0]["course_id"] == course
    assert rows[0]["owner_id"] == owner

    # Outside a course: no row. A personal training stands in no register.
    stage()
    svc.create_project("Mein Gesicht", [], "ich", staging_token="tok", captions=["ein Bild"], owner_id=owner)
    assert [r["name"] for r in R.all_adapters()] == ["Meine Sonne"]

    # A project name typed twice never rewrites the row that stands — this
    # route needs no login.
    stage()
    svc.create_project("Meine Sonne", [], "fremdes wort", staging_token="tok",
                       captions=["ein Bild"], owner_id=None, course_id=_course("Fremdkurs"))
    rows = R.all_adapters()
    assert len(rows) == 1 and rows[0]["trigger"] == "sonne, gelb" and rows[0]["course_id"] == course


# ---------------------------------------------------------------------------
# 5) the seed
# ---------------------------------------------------------------------------
def test_the_presets_adapters_get_their_row_once():
    _touch("sd3.5-large_cooked_negatives-000004.safetensors")
    written = R.seed_from_presets()
    rows = {r["file"]: r for r in R.all_adapters()}
    assert written == len(rows) >= 2
    cooked = rows["sd3.5-large_cooked_negatives-000004.safetensors"]
    assert cooked["trigger"] == "cooked negatives"
    assert cooked["visibility"] == "platform"
    assert cooked["base_configs"] == SD_CFGS
    assert cooked["name"] == "sd3.5-large cooked negatives"
    early = rows["sd35_19th_century_photography_landscape-000004.safetensors"]
    assert early["trigger"] == "19th_century_photography"
    assert early["name"] == "19th century photography landscape"
    # Seeded again: nothing written, and what an admin changed stands.
    R.update_adapter(cooked["id"], {"name": "cooked negatives", "visibility": "none"})
    assert R.seed_from_presets() == 0
    again = {r["file"]: r for r in R.all_adapters()}["sd3.5-large_cooked_negatives-000004.safetensors"]
    assert again["name"] == "cooked negatives" and again["visibility"] == "none"


# ---------------------------------------------------------------------------
# 6) the kind, which the chooser's ring sorts by (2026-09-22)
# ---------------------------------------------------------------------------
def test_the_kind_reaches_every_listing_and_is_never_none():
    _touch("sd35_solarization.safetensors")
    R.register_adapter("sd35_solarization.safetensors", "solarization", "solarization",
                       visibility="platform", category="Photography")
    R.register_adapter("sd35_x.safetensors", "x", "", visibility="platform")

    named = {r["file"]: r["category"] for r in R.all_adapters()}
    assert named["sd35_solarization.safetensors"] == "photography"
    # A row nobody gave a kind carries the empty string: the ring hangs it
    # under its release, which it cannot do for None.
    assert named["sd35_x.safetensors"] == ""
    offered = {r["file"]: r["category"] for r in R.visible_adapters(None)}
    assert offered == named


def test_a_kind_is_shaped_into_a_key():
    # The vocabulary is the frontend's; the register holds the SHAPE.
    R.register_adapter("sd35_a.safetensors", "a", "", visibility="none",
                       category="  Analoge  Fotografie!  ")
    R.register_adapter("sd35_b.safetensors", "b", "", visibility="none",
                       category="x" * 80)
    R.register_adapter("sd35_c.safetensors", "c", "", visibility="none", category=None)
    R.register_adapter("sd35_d.safetensors", "d", "", visibility="none",
                       category="photo\tgraphy")
    kinds = {r["file"]: r["category"] for r in R.all_adapters()}
    assert kinds["sd35_a.safetensors"] == "analoge_fotografie"
    assert kinds["sd35_b.safetensors"] == "x" * 40
    assert kinds["sd35_c.safetensors"] == ""
    # Any run of whitespace is ONE break, so two words never grow together.
    assert kinds["sd35_d.safetensors"] == "photo_graphy"


def test_a_kind_that_is_not_a_string_is_refused_like_a_bad_file():
    # `{"en": …}` is the shape every multilingual field on this platform has;
    # coerced, it would have stood on the ring as "en foto".
    for bad in ({"en": "Foto"}, ["a", "b"], True, 123, "!!!"):
        with pytest.raises(ValueError, match="category"):
            R.register_adapter("sd35_x.safetensors", "x", "", visibility="none",
                               category=bad)
    assert R.all_adapters() == []


def test_a_row_that_stands_takes_the_kind_it_lacks_and_keeps_the_one_it_has():
    # Every row written before 2026-09-22 has no kind; the seed passes
    # `keep_existing`, so the gap is the one thing it may still fill.
    R.register_adapter("sd35_a.safetensors", "a", "", visibility="platform")
    R.register_adapter("sd35_a.safetensors", "ignored", "", visibility="none",
                       category="photography", keep_existing=True)
    row = R.all_adapters()[0]
    assert row["category"] == "photography"
    assert row["name"] == "a" and row["visibility"] == "platform"

    R.register_adapter("sd35_a.safetensors", "ignored", "", visibility="none",
                       category="darkroom", keep_existing=True)
    assert R.all_adapters()[0]["category"] == "photography"


def test_an_admin_sets_the_kind_and_a_change_that_is_silent_about_it_keeps_it():
    R.register_adapter("sd35_a.safetensors", "a", "", visibility="platform",
                       category="photography")
    rid = R.all_adapters()[0]["id"]
    assert R.update_adapter(rid, {"category": "darkroom"})["category"] == "darkroom"
    assert R.update_adapter(rid, {"name": "A"})["category"] == "darkroom"
    assert R.update_adapter(rid, {"category": ""})["category"] == ""


def test_the_presets_adapters_carry_the_kind_their_config_names():
    R.seed_from_presets()
    kinds = {r["file"]: r["category"] for r in R.all_adapters()}
    assert kinds["sd3.5-large_cooked_negatives-000004.safetensors"] == "photography"
    assert kinds["sd35_19th_century_photography_landscape-000004.safetensors"] == "photography"


def test_the_seed_gives_the_kind_to_rows_that_were_written_before_the_column():
    """Every install that has run since 2026-09-21 carries both preset rows
    already. The seed leaves such a row alone — except for the kind, which no
    row written then could have."""
    cooked = "sd3.5-large_cooked_negatives-000004.safetensors"
    R.register_adapter(cooked, "cooked negatives", "cooked negatives",
                       visibility="platform")
    assert R.all_adapters()[0]["category"] == ""
    assert R.seed_from_presets() == 1  # the other one is written, this one stands
    rows = {r["file"]: r for r in R.all_adapters()}
    assert rows[cooked]["category"] == "photography"
    # Nothing else was touched.
    assert rows[cooked]["name"] == "cooked negatives" and rows[cooked]["visibility"] == "platform"


def test_an_older_database_file_gains_the_column_on_start(tmp_path, monkeypatch):
    """The Lab DB has no migration framework — `create_all` never alters a
    table that is there. A file written before 2026-09-22 therefore reaches
    the new code without `category`, and `init_db()` has to add it."""
    import sqlalchemy as sa
    from my_app.lab import db as D

    old = tmp_path / "old.db"
    eng = sa.create_engine(f"sqlite:///{old}")
    with eng.begin() as con:
        con.execute(sa.text("CREATE TABLE lora_adapters (id INTEGER PRIMARY KEY, file TEXT)"))
    monkeypatch.setattr(D, "engine", eng)

    D._ensure_columns()
    with eng.begin() as con:
        cols = {r[1] for r in con.execute(sa.text("PRAGMA table_info(lora_adapters)")).fetchall()}
    assert "category" in cols
    # Twice is no error: every start runs it.
    D._ensure_columns()


def test_a_database_without_the_table_at_all_is_left_to_create_all(tmp_path, monkeypatch):
    import sqlalchemy as sa
    from my_app.lab import db as D

    eng = sa.create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    monkeypatch.setattr(D, "engine", eng)
    D._ensure_columns()  # no table, no ALTER, no exception


# ---------------------------------------------------------------------------
# 7) which model carries an adapter: the file says it
# ---------------------------------------------------------------------------
def test_the_file_says_which_models_carry_it():
    """A model is not selected for an adapter; the LoRA file's own metadata
    says which model it belongs to. Both fields a trainer writes are read:
    the SAI model spec's architecture, which every SD 3.5 training of this
    place carries, and the trainer's own field, which is all the downloaded
    Flux 2 adapter carries."""
    _touch("sd35_spec.safetensors", SD_BASE)
    _touch("flux_trainer.safetensors", FLUX_BASE, trainer_field=True)
    R.register_adapter("sd35_spec.safetensors", "spec", visibility="platform")
    R.register_adapter("flux_trainer.safetensors", "flux", visibility="platform")

    rows = {r["file"]: r for r in R.visible_adapters(None)}
    assert rows["sd35_spec.safetensors"]["base"] == SD_BASE
    assert rows["sd35_spec.safetensors"]["base_configs"] == SD_CFGS
    assert rows["flux_trainer.safetensors"]["base"] == FLUX_BASE
    assert rows["flux_trainer.safetensors"]["base_configs"] == [FLUX]


def test_the_spec_field_wins_where_a_file_carries_both():
    head = json.dumps({"__metadata__": {
        "modelspec.architecture": f"{SD_BASE}/lora",
        "ss_base_model_version": "5-large",
    }}).encode("utf-8")
    (_LORA_DIR / "both.safetensors").write_bytes(struct.pack("<Q", len(head)) + head)
    B.forget("both.safetensors")
    assert B.declared_base("both.safetensors") == SD_BASE


def test_a_config_names_every_spelling_of_its_base():
    """`sd35_large.json` names what the SAI spec writes AND what the trainer's
    own field writes, so an SD 3.5 adapter is carried whichever of the two its
    file happens to hold. The spellings are held in the config, never
    reconciled in code."""
    _touch("kohya.safetensors", "5-large", trainer_field=True)
    assert R.configs_for("kohya.safetensors") == SD_CFGS


def test_every_config_that_can_load_an_adapter_names_what_it_runs():
    bases = {c["id"]: c["bases"] for c in R.carrier_configs()}
    assert bases[SD] == [SD_BASE, "5-large", SD_TURBO_BASE]
    assert bases[SD_IMG] == [SD_BASE, "5-large", SD_TURBO_BASE]
    assert bases[FLUX] == [FLUX_BASE]
    # CommonCanvas XL C holds the SDXL tensors but for two bookkeeping keys
    # (`position_ids`, `logit_scale`), so it runs what SDXL runs.
    assert bases[CANVAS] == bases[SDXL]
    assert bases[CANVAS_DIFF] == bases[SDXL]
    # These nine configs can load an adapter, and every one of them says which
    # model it runs. A model is added by reading what such a file says, never
    # by guessing a string, so a carrier without a base would carry nothing.
    assert sorted(bases) == sorted(
        [CANVAS, CANVAS_DIFF, FLUX, SD15, SD, SD_DIFF, SD_IMG, SD_TURBO, SDXL]
    )
    assert all(b for b in bases.values())


def test_a_legacy_workflow_carries_no_adapter():
    """`flux2_img2img` holds a checkpoint loader like any other carrier, and
    `execution_mode: legacy_workflow` hands it to `_process_legacy_workflow`
    (schemas/engine/backend_router.py), which passes the workflow through and
    reaches no LoraLoader. Derived as a carrier it would report an adapter as
    applied and put its trigger word in front of the prompt while loading
    nothing."""
    assert FLUX_IMG not in {c["id"] for c in R.carrier_configs()}
    _touch("flux_i2i.safetensors", FLUX_BASE, trainer_field=True)
    assert R.configs_for("flux_i2i.safetensors") == [FLUX]


def test_an_adapter_trained_over_turbo_reaches_the_large_configs():
    """SD 3.5 Large and Large Turbo hold the same 1167 tensors in the same
    shapes, so an adapter of the one fits the other. Both configs name both
    spellings and an adapter reaches the four either way."""
    _touch("turbo.safetensors", SD_TURBO_BASE)
    assert R.configs_for("turbo.safetensors") == SD_CFGS


def test_an_sdxl_adapter_reaches_commoncanvas_too():
    """Two spellings again: the SAI model spec writes one, sd-scripts own
    `sdxl_base_v1-0` the other, and both configs name both."""
    _touch("sdxl_spec.safetensors", "stable-diffusion-xl-v1-base")
    _touch("sdxl_kohya.safetensors", "sdxl_base_v1-0", trainer_field=True)
    assert R.configs_for("sdxl_spec.safetensors") == [CANVAS, CANVAS_DIFF, SDXL]
    assert R.configs_for("sdxl_kohya.safetensors") == [CANVAS, CANVAS_DIFF, SDXL]


def test_an_sd15_adapter_reaches_sd15_alone():
    _touch("sd15_spec.safetensors", "stable-diffusion-v1")
    _touch("sd15_kohya.safetensors", "sd_v1", trainer_field=True)
    assert R.configs_for("sd15_spec.safetensors") == [SD15]
    assert R.configs_for("sd15_kohya.safetensors") == [SD15]


def test_a_file_that_names_no_model_is_carried_by_none():
    """The accelerators of the video pipelines are such files. Registering one
    would offer it nowhere, which is why they have never been registered."""
    _platform("accelerator.safetensors", "", "")
    assert R.configs_for("accelerator.safetensors") == []
    cfg = [{"name": "accelerator.safetensors", "strength": 1.0}]
    assert R.loras_for_run(cfg, None, SD, None) == ([], [])
    assert R.loras_for_run(None, cfg, SD, None) == ([], [])


def test_a_base_no_config_here_runs_reaches_nothing():
    _platform("elsewhere.safetensors", "word", "a-model-nobody-here-runs")
    row = R.all_adapters()[0]
    assert row["base"] == "a-model-nobody-here-runs"
    assert row["base_configs"] == []


def test_no_client_can_set_the_models(client):
    """What this change is for: a POST or a PUT that names models is ignored,
    and the file keeps the last word in the run as well as in the listing."""
    _user(M.Role.admin, "root")
    _login(client, "root")
    _touch("sd35_solarization.safetensors")
    r = client.post("/api/loras/register", json={
        "file": "sd35_solarization.safetensors", "name": "solarization",
        "base_configs": [FLUX, FLUX_IMG], "visibility": "platform"})
    assert r.status_code == 201
    assert r.get_json()["base_configs"] == SD_CFGS

    rid = r.get_json()["id"]
    r = client.put(f"/api/loras/register/{rid}", json={"base_configs": []})
    assert r.status_code == 200 and r.get_json()["base_configs"] == SD_CFGS

    cfg = [{"name": "sd35_solarization.safetensors", "strength": 1.0}]
    assert R.loras_for_run(cfg, None, SD, None)[0] == cfg
    assert R.loras_for_run(cfg, None, FLUX, None) == ([], [])


def test_a_file_written_again_is_read_again():
    """A project retrained under the same name overwrites its file; what was
    read off the old one must not stand."""
    _touch("sd35_p.safetensors", SD_BASE)
    assert B.declared_base("sd35_p.safetensors") == SD_BASE
    # Written again WITHOUT clearing what was read: the key holds the moment
    # the file was written, so the new header is read.
    head = json.dumps({"__metadata__": {"ss_base_model_version": FLUX_BASE}}).encode("utf-8")
    (_LORA_DIR / "sd35_p.safetensors").write_bytes(struct.pack("<Q", len(head)) + head)
    assert B.declared_base("sd35_p.safetensors") == FLUX_BASE


def test_a_file_that_holds_no_header_names_nothing():
    (_LORA_DIR / "short.safetensors").write_bytes(b"\0")
    (_LORA_DIR / "huge.safetensors").write_bytes(struct.pack("<Q", 2 ** 40) + b"{}")
    (_LORA_DIR / "garbage.safetensors").write_bytes(struct.pack("<Q", 8) + b"not json")
    (_LORA_DIR / "cut.safetensors").write_bytes(struct.pack("<Q", 4096) + b"{}")
    B.forget()
    for f in ("short", "huge", "garbage", "cut", "nowhere"):
        assert B.declared_base(f"{f}.safetensors") == ""


def test_an_older_database_file_loses_the_hand_set_models_on_start(tmp_path, monkeypatch):
    """`lora_adapters.base_configs` was NOT NULL without a default. A file that
    keeps the column refuses every row the code now writes, because the model
    no longer knows it — so `init_db()` has to take it out."""
    import sqlalchemy as sa
    from my_app.lab import db as D

    eng = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as con:
        con.execute(sa.text(
            "CREATE TABLE lora_adapters (id INTEGER PRIMARY KEY, file TEXT, "
            "base_configs JSON NOT NULL)"
        ))
    monkeypatch.setattr(D, "engine", eng)

    D._drop_columns()
    with eng.begin() as con:
        cols = {r[1] for r in con.execute(sa.text("PRAGMA table_info(lora_adapters)")).fetchall()}
    assert "base_configs" not in cols
    # Twice is no error, and a file without the table at all is create_all's.
    D._drop_columns()
    empty = sa.create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    monkeypatch.setattr(D, "engine", empty)
    D._drop_columns()
