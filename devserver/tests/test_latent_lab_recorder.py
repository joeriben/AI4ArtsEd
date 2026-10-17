"""
Tests for the Latent Lab recorder, where an output arrives as a REFERENCE.

An output used to be bytes and nothing else. Mean Images writes every composite
cell as a run of its own the moment it is made, and writes the whole raster once
at the end — so the raster's outputs are pictures this storage already holds.
Sent as base64, every one of them would be carried by the browser and uploaded
again: a few hundred pictures up the wire for bytes the server can already
reach. A reference is the address they already have. The recorder resolves it
and COPIES the bytes into the new run, so each run stays complete on its own.

What is tested here is the contract that makes that safe: a reference is a run
address and nothing else, it is read through the platform's single resolver, it
is copied exactly as it lies, and a reference that resolves to nothing costs its
own output and never the run.

Run: python3 -m pytest devserver/tests/test_latent_lab_recorder.py -q
(from the worktree root; also works from devserver/ directly)
"""

import base64
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest
from PIL import Image

from my_app.services import latent_lab_recorder as lab
from my_app.utils.media_ref import find_media_entities


def _picture(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(32, 32, 3), dtype=np.uint8)


def _as_base64(array: np.ndarray) -> str:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _written(storage: Path, run_id: str) -> dict:
    """The metadata of one written run, found the way the platform finds it."""
    folder = next(storage.glob(f"*/*/{run_id}"))
    return json.loads((folder / "metadata.json").read_text(encoding="utf-8"))


def _pixels(storage: Path, run_id: str, entity: dict) -> np.ndarray:
    folder = next(storage.glob(f"*/*/{run_id}"))
    path = folder / "final" / entity["filename"]
    assert path.exists()
    with Image.open(path) as img:
        return np.asarray(img.convert("RGB"))


def _raw(storage: Path, run_id: str, entity: dict) -> bytes:
    """The file as it LIES — for the tests that are about the bytes themselves."""
    folder = next(storage.glob(f"*/*/{run_id}"))
    return (folder / "final" / entity["filename"]).read_bytes()


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    """The platform's storage, for the length of one test.

    The resolver reads `config.JSON_STORAGE_DIR` at call time, so a reference
    written here is looked up here and nothing touches the real exports.
    """
    import config

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", str(tmp_path))
    return tmp_path


def test_an_output_given_as_a_reference_is_read_out_of_the_storage(storage):
    """The referenced picture is what lands in the second run, pixel for pixel."""
    picture = _picture(seed=3)
    first = lab.LatentLabRecorder("sitting_a", "mean_images", device_id="dev", base_path=storage)
    made = first.record(
        parameters={"part": "cell"},
        outputs=[{"type": "image", "format": "png", "dataBase64": _as_base64(picture)}],
    )

    second = lab.LatentLabRecorder("sitting_b", "mean_images", device_id="dev", base_path=storage)
    written = second.record(
        parameters={"part": "raster"},
        outputs=[{
            "type": "image",
            "format": "png",
            "ref": f"/api/media/image/{made['run_id']}/0",
            "meta": {"model": "sd35_large", "view": "mean"},
        }],
    )

    metadata = _written(storage, written["run_id"])
    images = find_media_entities(metadata["entities"], "image")
    assert len(images) == 1
    # The instrument's own word about the output travels as it always did.
    assert images[0]["metadata"]["view"] == "mean"
    assert np.array_equal(_pixels(storage, written["run_id"], images[0]), picture)


def test_a_reference_that_resolves_to_nothing_costs_its_output_and_not_the_run(storage):
    """One unreadable output must never take the run with it."""
    picture = _picture(seed=5)
    recorder = lab.LatentLabRecorder("sitting_c", "mean_images", device_id="dev", base_path=storage)
    written = recorder.record(
        parameters={"part": "raster"},
        outputs=[
            {"type": "image", "format": "png", "ref": "/api/media/image/run_nowhere/0"},
            {"type": "image", "format": "png", "dataBase64": _as_base64(picture)},
        ],
    )

    assert written["run_id"]
    metadata = _written(storage, written["run_id"])
    images = find_media_entities(metadata["entities"], "image")
    assert len(images) == 1
    assert np.array_equal(_pixels(storage, written["run_id"], images[0]), picture)


def test_an_empty_reference_is_skipped_like_undecodable_base64(storage):
    recorder = lab.LatentLabRecorder("sitting_d", "mean_images", device_id="dev", base_path=storage)
    written = recorder.record(
        parameters={},
        outputs=[{"type": "image", "format": "png", "ref": "   "}],
    )
    metadata = _written(storage, written["run_id"])
    assert find_media_entities(metadata["entities"], "image") == []


def test_a_reference_that_is_a_file_path_is_refused_without_the_file_being_read(
    storage, tmp_path
):
    """A `ref` is a run address. A path is not one, and is never opened.

    `resolve_media_ref` takes far more than a run address — its first branch
    returns ANY existing filesystem path — and the route that carries a `ref`
    here is open to any client. Left to the resolver, a caller could name a file
    anywhere this process can read and have it copied into a run folder, from
    where the media routes hand it out.
    """
    secret = tmp_path / "elsewhere.txt"
    secret.write_bytes(b"this file is nobody's output")

    picture = _picture(seed=9)
    recorder = lab.LatentLabRecorder("sitting_e", "mean_images", device_id="dev", base_path=storage)
    written = recorder.record(
        parameters={"part": "raster"},
        outputs=[
            {"type": "image", "format": "png", "ref": str(secret)},
            {"type": "image", "format": "png", "dataBase64": _as_base64(picture)},
        ],
    )

    # The run stands, minus the output that was refused.
    assert written["run_id"]
    metadata = _written(storage, written["run_id"])
    images = find_media_entities(metadata["entities"], "image")
    assert len(images) == 1
    assert np.array_equal(_pixels(storage, written["run_id"], images[0]), picture)
    # And the file itself went nowhere.
    folder = next(storage.glob(f"*/*/{written['run_id']}"))
    assert all(
        secret.read_bytes() not in path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
    )


@pytest.mark.parametrize(
    "ref",
    [
        # Stopped twice over: the gate reads them first, and the resolver
        # would refuse them as well.
        "/api/media/uploads/upload_1",
        "/api/media/image/run_1/0?v=17",
        "../../etc/passwd",
        # And the three the gate alone refuses. First the BARE id of the run
        # written just below: left to the resolver this is "the latest image of
        # that run", and the picture would be handed out.
        "{run}",
        # The HALF address of the same run — a kind and a run, no index — which
        # is "the latest image" once more.
        "/api/media/image/{run}",
        # The same run under a kind the gate does not carry. That run holds a
        # 3d output too, so this address names something that is really there.
        "/api/media/3d/{run}/0",
    ],
)
def test_only_the_address_of_one_output_of_one_run_is_a_reference(storage, ref):
    """Every shape here falls short of one output of one run — in two ways.

    The uploads address, the address carrying a query string and the path
    traversal are stopped twice over: the gate reads them first, and
    `resolve_media_ref` would refuse them as well. The bare id, the half address
    and the 3d address RESOLVE — the run exists, each of them names an output
    that lies where the resolver looks, and the picture would be handed out. For
    those three the gate is the whole of the refusal, and that is what these
    lines say.
    """
    picture = _as_base64(_picture(seed=13))
    source = lab.LatentLabRecorder(
        "sitting_f_source", "mean_images", device_id="dev", base_path=storage
    )
    made = source.record(
        parameters={"part": "cell"},
        outputs=[
            {"type": "image", "format": "png", "dataBase64": picture},
            # The same picture under a second kind, so that the 3d address above
            # names an output this run really holds — `find_media_entities` looks
            # for `output_3d`, which this is written as.
            {"type": "3d", "format": "png", "dataBase64": picture},
        ],
    )

    recorder = lab.LatentLabRecorder("sitting_f", "mean_images", device_id="dev", base_path=storage)
    written = recorder.record(
        parameters={},
        outputs=[{"type": "image", "format": "png", "ref": ref.replace("{run}", made["run_id"])}],
    )
    metadata = _written(storage, written["run_id"])
    assert find_media_entities(metadata["entities"], "image") == []
    # And the run the address points at kept exactly what it was given.
    source_entities = _written(storage, made["run_id"])["entities"]
    assert len(find_media_entities(source_entities, "image")) == 1
    assert len(find_media_entities(source_entities, "3d")) == 1


def test_bytes_taken_through_a_reference_are_copied_exactly_as_they_lie(storage, monkeypatch):
    """The copy IS the picture the address hands out — mark and all.

    Those bytes were marked when they were first written. Marking them again
    would put a second disclosure into the file, and the copy would then differ
    from the picture the address it came from still serves.
    """
    picture = _picture(seed=11)
    other = _picture(seed=12)
    first = lab.LatentLabRecorder("sitting_g", "mean_images", device_id="dev", base_path=storage)
    made = first.record(
        parameters={"part": "cell"},
        outputs=[{"type": "image", "format": "png", "dataBase64": _as_base64(picture)}],
    )
    source = _raw(storage, made["run_id"], _written(storage, made["run_id"])["entities"][-1])

    # From here the marking ALTERS what it is given, so a picture that went
    # through it and one that did not can be told apart by their bytes.
    monkeypatch.setattr(lab, "_marked", lambda raw, entity_type, entity_metadata: raw + b"\x00")

    second = lab.LatentLabRecorder("sitting_h", "mean_images", device_id="dev", base_path=storage)
    written = second.record(
        parameters={"part": "raster"},
        outputs=[
            {"type": "image", "format": "png",
             "ref": f"/api/media/image/{made['run_id']}/0",
             "meta": {"view": "mean"}},
            {"type": "image", "format": "png", "dataBase64": _as_base64(other),
             "meta": {"view": "relief"}},
        ],
    )

    images = find_media_entities(_written(storage, written["run_id"])["entities"], "image")
    assert [e["metadata"]["view"] for e in images] == ["mean", "relief"]
    # The copy: byte for byte what the address hands out.
    assert _raw(storage, written["run_id"], images[0]) == source
    # The other output of the very same call: marked, and therefore altered.
    assert _raw(storage, written["run_id"], images[1]) == base64.b64decode(_as_base64(other)) + b"\x00"


# ---------------------------------------------------------------------------
# What a plate is CALLED
# ---------------------------------------------------------------------------

def test_a_composite_is_named_as_computed_from_several_renders():
    """Mean Images lays a plate that no model rendered: it computed it."""
    said = lab.name_plate({"plate": "composite", "reading": {"view": "mean", "pictures": 5}})
    assert "computed from several renders" in said
    assert "view: mean, pictures: 5" in said


def test_a_reading_keeps_the_wording_it_has_always_had():
    said = lab.name_plate({"plate": "reading", "reading": {"x": 1}})
    assert said == "the instrument's own reading, laid over the picture it was read from (x: 1)"


def test_a_plate_of_no_named_kind_is_named_as_a_reading():
    """Every plate written before the composite existed is a reading."""
    assert lab.name_plate({"plate": True}).startswith("the instrument's own reading")


def test_a_picture_that_is_no_plate_is_named_by_its_caller():
    assert lab.name_plate({"view": "mean"}) == ""
# ---------------------------------------------------------------------------
# Where a run keeps what it was made with
#
# A run written before a491f92f put its parameters, and its results, only into
# `prompting_process/001_parameters.json`. Read from the top level of the record
# alone, such a run comes back with nothing of itself and the surface restoring
# it fills the fields from whatever happens to stand on it.
# ---------------------------------------------------------------------------


def _older_run(folder: Path, parameters: dict, results: dict) -> Path:
    """A run of the kind written before the blocks stood at the top level."""
    run = folder / "run_older"
    (run / "prompting_process").mkdir(parents=True)
    (run / "final").mkdir()
    (run / "prompting_process" / "001_parameters.json").write_text(
        json.dumps({"parameters": parameters, "results": results}), encoding="utf-8"
    )
    return run


def test_an_older_run_gets_its_parameters_and_its_results_back(tmp_path):
    run = _older_run(tmp_path, {"seed": -1, "steps": 12}, {"seed": 4242, "total_steps": 12})
    metadata = {"type": "latent_lab", "entities": [
        {"type": "latent_lab_params", "filename": "prompting_process/001_parameters.json"},
    ]}

    parameters, results = lab.recovered_run_data(metadata, run / "final")

    assert parameters == {"seed": -1, "steps": 12}
    assert results == {"seed": 4242, "total_steps": 12}


def test_what_the_record_carries_itself_is_never_overwritten(tmp_path):
    run = _older_run(tmp_path, {"seed": 1}, {"seed": 1})
    metadata = {"type": "latent_lab", "parameters": {"seed": 9}, "results": {"seed": 9},
                "entities": []}

    assert lab.recovered_run_data(metadata, run / "final") == ({"seed": 9}, {"seed": 9})


def test_a_folder_of_several_generations_is_never_read(tmp_path):
    """`001_parameters.json` is the FIRST generation's, and there is no saying
    which one a picture in such a folder came from."""
    run = _older_run(tmp_path, {"seed": 1}, {"seed": 1})
    metadata = {"type": "latent_lab", "entities": [
        {"type": "latent_lab_params", "filename": "prompting_process/001_parameters.json"},
        {"type": "latent_lab_params", "filename": "prompting_process/003_parameters.json"},
    ]}

    assert lab.recovered_run_data(metadata, run / "final") == ({}, {})


def test_without_the_folder_the_params_entity_still_carries_the_parameters(tmp_path):
    metadata = {"type": "latent_lab", "entities": [
        {"type": "latent_lab_params", "metadata": {"seed": 7}},
    ]}

    assert lab.recovered_run_data(metadata, None) == ({"seed": 7}, {})


def test_blocks_that_are_not_objects_are_handed_on_as_nothing():
    metadata = {"type": "latent_lab", "parameters": ["seed"], "results": 3, "entities": []}

    assert lab.recovered_run_data(metadata, None) == ({}, {})


# ---------------------------------------------------------------------------
# What the AI-Origin Disclosure says about the picture
# ---------------------------------------------------------------------------


def test_the_disclosure_names_the_seed_that_made_the_picture():
    assert lab._disclosed({"seed": -1, "model": "m"}, {"seed": 4242}) == {"model": "m", "seed": 4242}


def test_without_a_result_the_disclosure_names_what_was_asked_for():
    assert lab._disclosed({"seed": 123}, {}) == {"seed": 123}


@pytest.mark.parametrize("parameters,results", [
    ({"seed": -1}, {}),
    ({}, {"seed": -1}),
    ({"seed": -1}, {"seed": -1}),
])
def test_the_sentinel_is_never_disclosed_as_a_seed(parameters, results):
    """-1 is what a surface keeps in the field to have the service draw. It is
    no seed, from either side."""
    assert lab._disclosed(parameters, results) == {}


@pytest.mark.parametrize("parameters,results,seed", [
    ({"seed": 5}, {"seed": 0}, 0),
    ({"seed": 0}, {}, 0),
])
def test_a_seed_of_zero_is_a_seed(parameters, results, seed):
    assert lab._disclosed(parameters, results) == {"seed": seed}


@pytest.mark.parametrize("parameters,results,expected", [
    ({"seed": 8}, {"seed": True}, {"seed": 8}),
    ({"seed": True}, {}, {}),
])
def test_a_boolean_is_no_seed(parameters, results, expected):
    """`isinstance(True, int)` holds in Python, and True is not a seed."""
    assert lab._disclosed(parameters, results) == expected


@pytest.mark.parametrize("results", [None, "seed", [1], 5])
def test_a_disclosure_is_never_worth_the_pictures_of_the_run(results):
    """The blocks come straight off the route. Raising here would land in the
    output loop's own `except` and cost the run every file it wrote."""
    assert lab._disclosed({"seed": 5}, results) == {"seed": 5}


def test_a_record_that_is_no_object_carries_nothing():
    assert lab.recovered_run_data("run_1", None) == ({}, {})


def test_the_block_the_record_keeps_stands_and_the_missing_one_is_read(tmp_path):
    """One block at the top level, the other only in the run's own file."""
    run = _older_run(tmp_path, {"seed": 1}, {"seed": 4242})
    metadata = {"type": "latent_lab", "parameters": {"seed": 9}, "entities": [
        {"type": "latent_lab_params", "filename": "prompting_process/001_parameters.json"},
    ]}

    assert lab.recovered_run_data(metadata, run / "final") == ({"seed": 9}, {"seed": 4242})


def test_a_folder_of_several_generations_still_hands_out_what_the_record_holds(tmp_path):
    run = _older_run(tmp_path, {"seed": 1}, {"seed": 1})
    metadata = {"type": "latent_lab", "parameters": {"seed": 9}, "entities": [
        {"type": "latent_lab_params", "filename": "prompting_process/001_parameters.json"},
        {"type": "latent_lab_params", "filename": "prompting_process/003_parameters.json"},
    ]}

    assert lab.recovered_run_data(metadata, run / "final") == ({"seed": 9}, {})


def test_a_params_entity_that_carries_no_object_is_no_fallback():
    metadata = {"type": "latent_lab", "entities": [
        {"type": "latent_lab_params", "metadata": "prompting_process/001_parameters.json"},
    ]}

    assert lab.recovered_run_data(metadata, None) == ({}, {})
