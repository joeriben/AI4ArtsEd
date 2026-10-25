"""
Tests for the Denoising Archaeology's run being written by the server.

Until 2026-09-22 the surface wrote the record itself, from the bytes the direct
endpoint had just sent it: the step frames and the finished picture down as
base64, and the same up again. Now the endpoint writes the run into the
sitting the surface names and answers with the run as the storage hands it
back, whose parts are addresses (services/denoising_archaeology_record.py).

What is tested here is the contract the surface relies on: the run lands in
the named sitting with the fields the surface used to write, under the same
names; each part carries the step of the run it belongs to, by the rule the
surface has used since second-order methods produced pairs; and a request
that names no sitting, an unknown one, one of another instrument or device,
or a field the surface could not have sent is refused with a word, and the
endpoint stays on its old answer.

Run: python3 -m pytest devserver/tests/test_denoising_archaeology_record.py -q
(from the worktree root; also works from devserver/ directly)
"""

import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image

from my_app.services import latent_lab_recorder as lab
from my_app.services.denoising_archaeology_record import (
    record_archaeology_run,
    step_of_capture,
)


def _frame(shade: int, fmt: str = "JPEG") -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (shade, shade, shade)).save(buffer, format=fmt)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _answer(count: int = 3, order: int = 1, seed: int = 7) -> dict:
    """What the chunk reports for a run of `count` captures."""
    return {
        "step_images": [
            {"step": i, "timestep": 1.0 - i / count, "image_base64": _frame(40 + i * 50)}
            for i in range(count)
        ],
        "total_steps": count if order == 1 else (count + 1) // 2,
        "seed": seed,
        "scheduler": "euler/normal",
        "scheduler_order": order,
        "backbone": "sd35",
    }


def _run(record, answer, **overrides):
    fields = dict(
        prompt="a house in a landscape",
        negative_prompt="",
        steps=answer["total_steps"],
        cfg=4.5,
        output_config="denoising_archaeology_comfyui",
        pipeline_run_id="run_pipeline_1",
        result_seed=99,
        archaeology_data=answer,
        image_base64=_frame(220, "PNG"),
    )
    fields.update(overrides)
    return record_archaeology_run(record, **fields)


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    """The platform's storage, for the length of one test; no real export is touched."""
    import config
    from my_app.services import pipeline_recorder

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", str(tmp_path))
    # A recorder loaded from an earlier test's storage would answer for a run
    # id that now lies in another folder.
    pipeline_recorder._active_recorders.clear()
    return tmp_path


@pytest.fixture()
def sitting(storage):
    recorder = lab.create_lab_recorder(latent_lab_tool="denoising_archaeology", device_id="dev")
    yield recorder
    lab.cleanup_lab_recorder(recorder.session_id)


def _record(sitting, **fields):
    base = {"session_id": sitting.session_id, "device_id": "dev", "seed": 123, "random_seed": False}
    base.update(fields)
    return base


def test_the_run_lands_in_the_named_sitting_as_the_surface_used_to_write_it(storage, sitting):
    answer = _answer(count=3)
    obj, refusal = _run(_record(sitting), answer)

    assert refusal is None
    assert obj["tool"] == "denoising_archaeology"
    assert obj["session_id"] == sitting.session_id

    # The fields the surface wrote until 2026-09-22, under the same names.
    params = obj["parameters"]
    assert params["prompt"] == "a house in a landscape"
    assert params["negative_prompt"] == ""
    assert params["steps"] == 3
    assert params["cfg"] == 4.5
    assert params["seed"] == 123
    assert params["random_seed"] is False
    assert params["backbone"] == "sd35"
    assert params["output_config"] == "denoising_archaeology_comfyui"
    assert params["pipeline_run_id"] == "run_pipeline_1"

    results = obj["results"]
    assert results["seed"] == 7
    assert results["total_steps"] == 3
    assert results["scheduler"] == "euler/normal"
    assert results["scheduler_order"] == 1

    # The parts are addresses, in the order of the run, each naming its step.
    parts = [p for p in obj["parts"] if p["kind"] == "step"]
    assert [p["meta"]["step"] for p in parts] == [1, 2, 3]
    assert all(p["meta"]["second"] is False for p in parts)
    assert [p["url"] for p in parts] == [
        f"/api/latent-lab/run/{obj['run_id']}/part/{i}" for i in range(3)
    ]
    for i in range(3):
        assert lab.resolve_part_path(obj["run_id"], i, base_path=storage) is not None

    # The finished picture is the run's one image output, at a media address.
    images = [o for o in obj["outputs"] if o["type"] == "image"]
    assert len(images) == 1
    assert images[0]["url"].startswith(f"/api/media/image/{obj['run_id']}/0")

    # The object answered is the one the store hands back for that run.
    assert lab.build_instrument_object(obj["run_id"], base_path=storage) == obj


def test_the_net_is_the_one_the_chunk_reports(storage, sitting):
    answer = _answer()
    answer["backbone"] = "sdxl"
    obj, refusal = _run(_record(sitting), answer)
    assert refusal is None
    assert obj["parameters"]["backbone"] == "sdxl"


def test_a_chunk_that_names_no_net_is_refused(storage, sitting):
    answer = _answer()
    del answer["backbone"]
    assert _run(_record(sitting), answer) == (None, "backbone_unnamed")


def test_a_second_order_method_pairs_its_captures_by_the_surface_rule(storage, sitting):
    # Five captures of a second-order rule at three steps: (0,1) is step 1,
    # (2,3) is step 2, and the last step has no partner.
    answer = _answer(count=5, order=2)
    obj, _ = _run(_record(sitting), answer)

    parts = [p for p in obj["parts"] if p["kind"] == "step"]
    assert [(p["meta"]["step"], p["meta"]["second"]) for p in parts] == [
        (1, False), (1, True), (2, False), (2, True), (3, False),
    ]
    assert obj["results"]["scheduler_order"] == 2


def test_step_of_capture_is_the_surface_rule():
    assert step_of_capture(0, 1) == {"step": 1, "second": False}
    assert step_of_capture(24, 1) == {"step": 25, "second": False}
    assert step_of_capture(0, 2) == {"step": 1, "second": False}
    assert step_of_capture(1, 2) == {"step": 1, "second": True}
    assert step_of_capture(22, 2) == {"step": 12, "second": False}


def test_the_reported_seed_falls_back_to_the_endpoints_and_never_to_a_bool(storage, sitting):
    answer = _answer()
    answer["seed"] = None
    obj, _ = _run(_record(sitting), answer, result_seed=99)
    assert obj["results"]["seed"] == 99

    answer = _answer()
    answer["seed"] = True
    obj, _ = _run(_record(sitting), answer, result_seed=None)
    assert "seed" not in obj["results"]


def test_a_scheduler_the_chunk_did_not_name_is_left_out(storage, sitting):
    answer = _answer()
    answer["scheduler"] = None
    obj, _ = _run(_record(sitting), answer)
    assert "scheduler" not in obj["results"]


def test_a_run_without_a_picture_records_its_frames_and_no_output(storage, sitting):
    obj, refusal = _run(_record(sitting), _answer(count=2), image_base64=None)
    assert refusal is None
    assert [p["kind"] for p in obj["parts"]] == ["step", "step"]
    assert obj["outputs"] == []


def test_a_request_without_a_record_asks_for_none(storage, sitting):
    assert _run(None, _answer()) == (None, None)


@pytest.mark.parametrize(
    "record, word",
    [
        ("lab_123", "record_malformed"),
        ({"device_id": "dev", "seed": 1, "random_seed": False}, "no_session_id"),
        ({"session_id": "   ", "device_id": "dev", "seed": 1, "random_seed": False}, "no_session_id"),
    ],
)
def test_a_request_that_names_no_sitting_is_refused_with_the_word(storage, sitting, record, word):
    assert _run(record, _answer()) == (None, word)


def test_an_unknown_sitting_is_refused(storage, sitting):
    assert _run(_record(sitting, session_id="lab_nowhere"), _answer()) == (None, "no_open_sitting")


def test_a_sitting_of_another_instrument_is_refused(storage):
    other = lab.create_lab_recorder(latent_lab_tool="mean_images", device_id="dev")
    try:
        assert _run(_record(other), _answer()) == (None, "sitting_of_another_instrument")
    finally:
        lab.cleanup_lab_recorder(other.session_id)


def test_a_sitting_of_another_device_is_refused(storage, sitting):
    assert _run(_record(sitting, device_id="someone_else"), _answer()) == (
        None, "sitting_of_another_device",
    )


@pytest.mark.parametrize(
    "fields, word",
    [
        ({"device_id": None}, "no_device_id"),
        ({"device_id": ""}, "no_device_id"),
        ({"seed": "123"}, "seed_not_a_whole_number"),
        ({"seed": ""}, "seed_not_a_whole_number"),
        ({"seed": True}, "seed_not_a_whole_number"),
        ({"seed": 1.5}, "seed_not_a_whole_number"),
        ({"random_seed": None}, "random_seed_not_a_tick"),
        ({"random_seed": "yes"}, "random_seed_not_a_tick"),
    ],
)
def test_a_record_with_a_field_the_surface_could_not_have_sent_is_refused(storage, sitting, fields, word):
    assert _run(_record(sitting, **fields), _answer()) == (None, word)


def test_a_seed_field_sent_as_null_is_carried_as_none(storage, sitting):
    # The surface sends null for a field that holds no whole number.
    obj, refusal = _run(_record(sitting, seed=None, random_seed=True), _answer(seed=5))
    assert refusal is None
    assert obj["parameters"]["seed"] is None
    assert obj["parameters"]["random_seed"] is True
    assert obj["results"]["seed"] == 5


def test_a_capture_that_names_no_index_is_counted_by_its_place(storage, sitting):
    answer = _answer(count=3)
    del answer["step_images"][1]["step"]
    answer["step_images"].append({"step": 3, "image_base64": ""})
    answer["step_images"].append("not a capture")
    obj, _ = _run(_record(sitting), answer)
    parts = [p for p in obj["parts"] if p["kind"] == "step"]
    assert [p["meta"]["step"] for p in parts] == [1, 2, 3]


def test_a_write_that_fails_is_refused_with_the_word(storage, sitting, monkeypatch):
    def broken(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(sitting, "record", broken)
    assert _run(_record(sitting), _answer()) == (None, "not_written")
