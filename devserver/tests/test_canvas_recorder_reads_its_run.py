"""
The Canvas keeps the picture a generation node made
(my_app/services/canvas_recorder.py, `save_image_from_url`).

The generation hands back the address the browser loads the picture from,
/api/media/image/<run>/<index>. Until 2026-11-15 the recorder fetched that
address from its own server over HTTP, without a session. Since every route but
the start page needs a sign-in (my_app/lab/sign_in_gate.py) that request is
answered 401, and the board's run kept no picture. The recorder reads the file
from the run's folder now, through the resolver the media route's selection
rule lives in (my_app/utils/media_ref.py), at the level of the run.

Run: python3 -m pytest devserver/tests/test_canvas_recorder_reads_its_run.py -q
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image

import my_app.services.canvas_recorder as canvas_recorder_module
from my_app.services.canvas_recorder import CanvasRecorder

RUN = "run_probe_canvas__gen_node"


def _png_bytes(color=(10, 120, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 12), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _pixels(data: bytes) -> bytes:
    """The picture without its metadata: the recorder writes the AI-origin
    disclosure into the file it keeps (services/media_marking.py)."""
    with Image.open(io.BytesIO(data)) as img:
        return img.convert("RGB").tobytes()


def _kept(board, sequence) -> bytes:
    return _pixels(board.get_entity_path(sequence).read_bytes())


class _FakeRun:
    def __init__(self, final_folder, entities):
        self.final_folder = final_folder
        self.metadata = {"entities": entities}


@pytest.fixture()
def generated(tmp_path, monkeypatch):
    """A generation run with one picture, and no HTTP to anywhere."""
    final = tmp_path / "gen" / "final"
    final.mkdir(parents=True)
    data = _png_bytes()
    (final / "02_output_image.png").write_bytes(data)
    picture = {"type": "output_image", "filename": "02_output_image.png",
               "sequence": 2, "metadata": {}}
    import my_app.services.pipeline_recorder as pr
    monkeypatch.setattr(pr, "load_recorder",
                        lambda run_id, base_path=None: _FakeRun(final, [picture]) if run_id == RUN else None)

    def no_http(*args, **kwargs):
        raise AssertionError("the recorder asked a server for a picture of its own runs")

    monkeypatch.setattr(canvas_recorder_module.requests, "get", no_http)
    return data, picture


def _board(tmp_path) -> CanvasRecorder:
    return CanvasRecorder(run_id="run_board", workflow={"nodes": [], "connections": []},
                          device_id="dev", base_path=tmp_path / "exports", safety_level="adult")


def test_the_picture_of_a_generation_node_is_kept(tmp_path, generated):
    data, _ = generated
    board = _board(tmp_path)
    sequence = board.save_image_from_url(node_id="gen1", url=f"/api/media/image/{RUN}/0",
                                         config_id="sd35_large", seed=7, level="adult")
    assert sequence is not None
    entity = board.get_entity_by_sequence(sequence)
    assert _kept(board, sequence) == _pixels(data)
    assert entity["metadata"]["width"] == 16
    assert entity["metadata"]["seed"] == 7
    assert entity["metadata"]["source_url"] == f"/api/media/image/{RUN}/0"


def test_the_address_without_an_index_and_with_a_query_names_the_same_picture(tmp_path, generated):
    data, _ = generated
    board = _board(tmp_path)
    sequence = board.save_image_from_url(node_id="gen1", url=f"/api/media/image/{RUN}?v=1",
                                         config_id="sd35_large", level="adult")
    assert _kept(board, sequence) == _pixels(data)


def test_a_picture_the_check_withholds_at_the_run_level_is_not_kept(tmp_path, generated):
    """Unjudged, a picture is none for kids (media_ref._from_run): the board of a
    kids run keeps nothing, as the media route would hand it nothing."""
    board = _board(tmp_path)
    assert board.save_image_from_url(node_id="gen1", url=f"/api/media/image/{RUN}/0",
                                     config_id="sd35_large", level="kids") is None
    assert board.metadata["entities"] == []


def test_a_picture_with_a_pass_for_the_run_level_is_kept(tmp_path, generated):
    data, picture = generated
    picture["metadata"]["safety"] = {"safe": True, "level": "kids"}
    board = _board(tmp_path)
    sequence = board.save_image_from_url(node_id="gen1", url=f"/api/media/image/{RUN}/0",
                                         config_id="sd35_large", level="kids")
    assert _kept(board, sequence) == _pixels(data)


def test_the_level_has_to_be_named():
    with pytest.raises(TypeError):
        CanvasRecorder.save_image_from_url(object(), node_id="gen1", url="/x", config_id="c")
