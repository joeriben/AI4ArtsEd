"""A Canvas workflow in the favourites strip.

A favourite is a run. POST /api/canvas/keep makes one that holds nothing but
the board (entity `canvas`); the strip lists it under its name, and its restore
data carries the board back (`canvas_workflow`). An output of a Canvas run
carries the board of the run that made it, read from that run's workflow.json.

Run: python3 -m pytest devserver/tests/test_canvas_keep.py -q
"""

import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

import config
from my_app.routes import canvas_routes, favorites_routes

DEVICE = "0b6f2c1e-6a43-4c1b-9d1e-2f3a4b5c6d7e_2026-10-01"

BOARD = {
    "id": "workflow_1",
    "name": "Perspektive gegen Rohtext",
    "type": "canvas_workflow",
    "nodes": [
        {"id": "in1", "type": "input", "x": 0, "y": 0, "promptText": "Ein Haus am Meer"},
        {"id": "gen1", "type": "generation", "x": 300, "y": 0, "configId": "sd3.5_large"},
    ],
    "connections": [{"sourceId": "in1", "targetId": "gen1"}],
}


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    # Bound at import in the favourites routes, read at call time in the keep route.
    monkeypatch.setattr(favorites_routes, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(canvas_routes, "resolve_safety_level", lambda: "kids")
    (tmp_path / "favorites.json").write_text(
        json.dumps({"version": "1.0", "mode": "global", "favorites": []}), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def client(storage):
    app = Flask(__name__)
    app.register_blueprint(canvas_routes.canvas_bp)
    app.register_blueprint(favorites_routes.favorites_bp)
    return app.test_client()


def _keep(client, board=BOARD, device_id=DEVICE):
    r = client.post("/api/canvas/keep", json={"workflow": board, "device_id": device_id})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["run_id"]


def _star(client, run_id):
    return client.post("/api/favorites", json={
        "run_id": run_id, "media_type": "canvas", "device_id": DEVICE, "source_view": "canvas",
    })


def _listed(client, run_id):
    r = client.get(f"/api/favorites?device_id={DEVICE}&view_mode=per_user")
    assert r.status_code == 200
    return next(f for f in r.get_json()["favorites"] if f["run_id"] == run_id)


class TestKeep:
    def test_the_run_holds_the_board(self, client, storage):
        run_id = _keep(client)
        folders = list(storage.glob(f"*/{DEVICE}/{run_id}"))
        assert len(folders) == 1
        meta = json.loads((folders[0] / "metadata.json").read_text(encoding="utf-8"))
        entity = next(e for e in meta["entities"] if e["type"] == "canvas")
        assert entity["metadata"]["name"] == "Perspektive gegen Rohtext"
        assert entity["metadata"]["node_count"] == 2
        stored = json.loads((folders[0] / "final" / entity["filename"]).read_text(encoding="utf-8"))
        assert stored["nodes"] == BOARD["nodes"]

    def test_starred_it_is_listed_under_its_name(self, client):
        run_id = _keep(client)
        r = _star(client, run_id)
        assert r.status_code == 201, r.get_json()
        answer = r.get_json()["favorite"]
        assert answer["thumbnail_url"] == ""
        assert answer["input_preview"] == "Perspektive gegen Rohtext"
        listed = _listed(client, run_id)
        assert listed["exists"] is True
        assert listed["input_preview"] == "Perspektive gegen Rohtext"

    def test_unnamed_it_is_listed_under_its_prompt(self, client):
        for name in ("", "New Workflow", "   "):
            run_id = _keep(client, {**BOARD, "name": name})
            assert _star(client, run_id).status_code == 201
            assert _listed(client, run_id)["input_preview"] == "Ein Haus am Meer"

    def test_its_restore_brings_the_board_back(self, client):
        run_id = _keep(client)
        _star(client, run_id)
        r = client.get(f"/api/favorites/{run_id}/restore")
        assert r.status_code == 200
        board = r.get_json()["canvas_workflow"]
        assert board["name"] == "Perspektive gegen Rohtext"
        assert board["type"] == "canvas_workflow"
        assert board["nodes"] == BOARD["nodes"]
        assert board["connections"] == BOARD["connections"]

    @pytest.mark.parametrize("body", [
        {},
        {"workflow": "nodes"},
        {"workflow": {"connections": []}},
        {"workflow": {"nodes": {}, "connections": []}},
        {"workflow": {"nodes": [], "connections": 3}},
        {"workflow": BOARD, "device_id": "../../elsewhere"},
        {"workflow": BOARD, "device_id": 7},
    ])
    def test_refuses_what_is_not_a_board(self, client, storage, body):
        r = client.post("/api/canvas/keep", json=body)
        assert r.status_code == 400
        assert not [p for p in storage.rglob("metadata.json")]
        assert not (storage.parent / "elsewhere").exists()


def _canvas_run(storage, run_id, workflow, kind="canvas_workflow"):
    folder = storage / "2026-10-01" / DEVICE / run_id
    (folder / "final").mkdir(parents=True)
    (folder / "metadata.json").write_text(json.dumps({
        "run_id": run_id, "type": kind, "device_id": DEVICE,
        "timestamp": "2026-10-01T14:32:00", "workflow_file": "workflow.json", "entities": [],
    }), encoding="utf-8")
    (folder / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")


def _output_run(storage, run_id):
    folder = storage / "2026-10-01" / DEVICE / run_id
    (folder / "final").mkdir(parents=True)
    (folder / "final" / "01_output_image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (folder / "metadata.json").write_text(json.dumps({
        "run_id": run_id, "config_name": "sd3.5_large", "device_id": DEVICE,
        "timestamp": "2026-10-01T14:33:00",
        "entities": [{"sequence": 1, "type": "output_image", "filename": "01_output_image.png",
                      "metadata": {}}],
    }), encoding="utf-8")


class TestOutputOfACanvasRun:
    def test_brings_the_board_of_its_run(self, client, storage):
        parent = "run_1727000000000_abc123_canvas"
        _canvas_run(storage, parent, {
            "name": "Zwei Lesarten", "nodes": BOARD["nodes"], "connections": BOARD["connections"]})
        _output_run(storage, f"{parent}__gen1")
        r = client.get(f"/api/favorites/{parent}__gen1/restore")
        assert r.status_code == 200
        board = r.get_json()["canvas_workflow"]
        assert board["name"] == "Zwei Lesarten"
        assert board["nodes"] == BOARD["nodes"]

    def test_a_run_from_before_the_name_opens_unnamed(self, client, storage):
        parent = "run_1727000000001_abc124_canvas"
        _canvas_run(storage, parent, {"nodes": BOARD["nodes"], "connections": BOARD["connections"]})
        _output_run(storage, f"{parent}__gen1")
        board = client.get(f"/api/favorites/{parent}__gen1/restore").get_json()["canvas_workflow"]
        assert board["name"] == ""

    def test_other_runs_bring_no_board(self, client, storage):
        parent = "run_1727000000002_abc125_flow"
        _canvas_run(storage, parent, {"nodes": BOARD["nodes"]}, kind="pipeline")
        _output_run(storage, f"{parent}__gen1")
        _output_run(storage, "run_1727000000003_abc126")
        for run_id in (f"{parent}__gen1", "run_1727000000003_abc126"):
            r = client.get(f"/api/favorites/{run_id}/restore")
            assert r.status_code == 200
            assert "canvas_workflow" not in r.get_json()


def test_a_batch_run_records_its_own_prompt(client, monkeypatch):
    """In prompt mode each run's workflow.json holds the prompt THAT run ran."""
    recorded = []

    class Recorder:
        device_id = DEVICE
        run_folder = Path("/nonexistent")

        def mark_complete(self):
            pass

    def fake_recorder(run_id, workflow=None, **kw):
        recorded.append(workflow)
        return Recorder()

    class Executor:
        def __init__(self, **kw):
            pass

        def execute_with_events(self):
            return iter(())

        def get_result(self):
            return {"success": True}

    engine = types.ModuleType("schemas.engine.prompt_interception_engine")
    engine.PromptInterceptionEngine = lambda: object()
    engine.PromptInterceptionRequest = object
    monkeypatch.setitem(sys.modules, "schemas.engine.prompt_interception_engine", engine)
    monkeypatch.setattr(canvas_routes, "get_canvas_recorder", fake_recorder)
    monkeypatch.setattr(canvas_routes, "cleanup_canvas_recorder", lambda run_id: None)
    monkeypatch.setattr(canvas_routes, "CanvasWorkflowExecutor", Executor)

    r = client.post("/api/canvas/execute-batch", json={
        "workflow": BOARD, "prompts": ["Ein Wald", "Ein Fluss"], "device_id": DEVICE,
        "base_seed": 7})
    assert b"batch_complete" in r.get_data()
    assert [w["nodes"][0]["promptText"] for w in recorded] == ["Ein Wald", "Ein Fluss"]
    assert [w["name"] for w in recorded] == ["Perspektive gegen Rohtext"] * 2
    assert [[n["seedBase"] for n in w["nodes"] if n["type"] == "seed"] for w in recorded] == [[7], [8]]
    assert BOARD["nodes"][0]["promptText"] == "Ein Haus am Meer"


class TestBoardAsRun:
    def test_a_generation_node_without_seed_gets_the_run_seed(self):
        nodes, connections = canvas_routes.board_as_run(BOARD["nodes"], BOARD["connections"], None, 1042, 3)
        seed = next(n for n in nodes if n["type"] == "seed")
        # "Batch (+1)" from the run's seed: alone it renders that seed, in a
        # batch again it counts up from it.
        assert seed["seedMode"] == "increment" and seed["seedBase"] == 1042
        assert seed["x"] == 80 and seed["y"] == 160
        assert {"sourceId": seed["id"], "targetId": "gen1", "label": None} in connections
        assert len(BOARD["nodes"]) == 2 and len(BOARD["connections"]) == 1

    def test_the_seed_node_stays_on_the_board(self):
        left = [{**BOARD["nodes"][0]}, {**BOARD["nodes"][1], "x": 100}]
        nodes, _ = canvas_routes.board_as_run(left, BOARD["connections"], None, 5)
        assert next(n for n in nodes if n["type"] == "seed")["x"] == 0

    def test_a_batch_plus_one_node_takes_the_run_place_into_its_base(self):
        own = BOARD["nodes"] + [{"id": "s1", "type": "seed", "seedMode": "increment", "seedBase": 100}]
        wires = BOARD["connections"] + [{"sourceId": "s1", "targetId": "gen1"}]
        nodes, _ = canvas_routes.board_as_run(own, wires, None, None, 4)
        assert next(n for n in nodes if n["id"] == "s1")["seedBase"] == 104
        assert own[-1]["seedBase"] == 100

    def test_a_seed_node_of_its_own_stays(self):
        own = BOARD["nodes"] + [{"id": "s1", "type": "seed", "seedMode": "random", "x": 0, "y": 0}]
        wires = BOARD["connections"] + [{"sourceId": "s1", "targetId": "gen1"}]
        nodes, connections = canvas_routes.board_as_run(own, wires, None, 1042)
        assert [n["id"] for n in nodes if n["type"] == "seed"] == ["s1"]
        assert connections == wires

    def test_without_a_run_seed_nothing_is_added(self):
        nodes, connections = canvas_routes.board_as_run(BOARD["nodes"], BOARD["connections"], "Wald", None)
        assert [n["type"] for n in nodes] == ["input", "generation"]
        assert nodes[0]["promptText"] == "Wald"
        assert connections == BOARD["connections"]


def test_batch_plus_one_counts_up_in_a_batch():
    """The Canvas seed mode "Batch (+1)" is `increment`: base, plus the run's place."""
    from my_app.services.canvas_executor import CanvasWorkflowExecutor
    node = {"id": "s", "type": "seed", "seedMode": "increment", "seedBase": 100}
    for run_index, expected in ((None, 100), (0, 100), (3, 103)):
        ex = CanvasWorkflowExecutor([node], [], object(), "run_t", object(), run_index=run_index)
        assert ex._execute_seed(node, "s")[0] == expected


@pytest.mark.parametrize("base, expected", [
    ("7", 10), (5.0, 8), (None, None), ("x", None), (True, None), (float("inf"), None),
])
def test_a_base_that_is_no_whole_number(base, expected):
    """Read the same way by the executor and by the recorded board."""
    from my_app.services.canvas_executor import CanvasWorkflowExecutor
    node = {"id": "s", "type": "seed", "seedMode": "increment", "seedBase": base}
    ex = CanvasWorkflowExecutor([node], [], object(), "run_t", object(), run_index=3)
    assert ex._execute_seed(node, "s")[0] == expected
    nodes, _ = canvas_routes.board_as_run([node], [], None, None, 3)
    assert nodes[0]["seedBase"] == (expected if expected is not None else base)


def test_an_unreadable_base_records_the_run_seed_it_fell_back_to():
    node = {"id": "s", "type": "seed", "seedMode": "increment", "seedBase": "7.5"}
    wires = [{"sourceId": "s", "targetId": "gen1"}]
    nodes, connections = canvas_routes.board_as_run([BOARD["nodes"][1], node], wires, None, 1042, 3)
    assert next(n for n in nodes if n["id"] == "s")["seedBase"] == 1042
    assert [n["id"] for n in nodes if n["type"] == "seed"] == ["s"]
    nodes, _ = canvas_routes.board_as_run([BOARD["nodes"][1], node], wires, None, None, 3)
    assert next(n for n in nodes if n["id"] == "s")["seedBase"] == "7.5"


def test_a_cleared_base_seed_does_not_stop_the_batch(client, monkeypatch):
    seen = []

    class Recorder:
        device_id = DEVICE
        run_folder = Path("/nonexistent")

        def mark_complete(self):
            pass

    class Executor:
        def __init__(self, **kw):
            seen.append(kw.get("run_seed"))

        def execute_with_events(self):
            return iter(())

        def get_result(self):
            return {"success": True}

    engine = types.ModuleType("schemas.engine.prompt_interception_engine")
    engine.PromptInterceptionEngine = lambda: object()
    engine.PromptInterceptionRequest = object
    monkeypatch.setitem(sys.modules, "schemas.engine.prompt_interception_engine", engine)
    monkeypatch.setattr(canvas_routes, "get_canvas_recorder", lambda run_id, **kw: Recorder())
    monkeypatch.setattr(canvas_routes, "cleanup_canvas_recorder", lambda run_id: None)
    monkeypatch.setattr(canvas_routes, "CanvasWorkflowExecutor", Executor)
    r = client.post("/api/canvas/execute-batch", json={"workflow": BOARD, "count": 2, "base_seed": ""})
    body = r.get_data()
    assert b"batch_complete" in body and b"run_error" not in body
    assert seen == [None, None]


def test_the_run_records_the_workflow_name():
    """execute-stream hands the board's name to the run (canvas_run_service)."""
    source = (Path(canvas_routes.__file__)).read_text(encoding="utf-8")
    assert "name=workflow_name(data.get('workflow'))" in source
