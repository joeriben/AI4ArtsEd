#!/usr/bin/env python3
"""
Tests for the canvas-partial-recovery job architecture.

Covers:
  * canvas_run_service job registry: start -> events -> complete; a reconnecting
    reader that attaches at ?after=<n> receives exactly the rest; status.json
    state transitions; events replayed from events.jsonl when they predate the
    in-memory buffer window; the startup hook re-marks orphaned running ->
    interrupted.
  * routes: GET /api/canvas/partial/<run_id> (partial items sorted + state),
    unknown id -> 404, path-traversal -> 400; GET /api/canvas/runs/<id>/status.

The heavy CanvasWorkflowExecutor + PromptInterceptionEngine are stubbed: this
suite validates the execution SHELL and persistence, not node execution.
"""
import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.services.canvas_run_service as crs


# ── fakes ────────────────────────────────────────────────────────────────────

class _FakeRecorder:
    """Minimal stand-in for CanvasRecorder: owns a run folder + final/ and a
    mark_complete that writes completed_at into metadata.json (mirrors the real
    one closely enough for the service + partial route)."""
    def __init__(self, run_folder: Path):
        self.run_folder = run_folder
        self.final_folder = run_folder / "final"
        self.final_folder.mkdir(parents=True, exist_ok=True)
        self.device_id = "test-device"
        self.metadata = {"run_id": run_folder.name, "entities": []}
        self._write_meta()

    def _write_meta(self):
        (self.run_folder / "metadata.json").write_text(
            json.dumps(self.metadata, ensure_ascii=False), encoding="utf-8")

    def mark_complete(self):
        self.metadata["completed_at"] = "2026-07-05T00:00:00"
        self._write_meta()


class _FakeExecutor:
    """Yields a scripted event stream, then reports success via get_result.
    The `script` is a list of (event_type, data) plus a final result dict."""
    script = []      # class attr set per test
    result = {"success": True, "results": {}, "collector_items": [],
              "execution_trace": ["a", "b"]}
    delay = 0.0

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def execute_with_events(self):
        for ev in type(self).script:
            if type(self).delay:
                time.sleep(type(self).delay)
            yield ev

    def get_result(self):
        return type(self).result


@pytest.fixture()
def wired(tmp_path, monkeypatch):
    """Redirect JSON_STORAGE_DIR into tmp_path and stub the executor + recorder
    so start_run drives our fake. Resets the in-memory registry each test."""
    import config
    storage = tmp_path / "json"
    storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", storage, raising=False)

    made = {}

    def _fake_get_recorder(run_id, workflow=None, device_id=None, **kw):
        rf = storage / "2026-07-05" / "test-device" / run_id
        rec = _FakeRecorder(rf)
        # persist workflow.json (partial route reads it for prompts_pending)
        (rf / "workflow.json").write_text(
            json.dumps(workflow or {"nodes": [], "connections": []}), encoding="utf-8")
        made[run_id] = rec
        return rec

    monkeypatch.setattr(crs, "get_canvas_recorder", _fake_get_recorder)
    monkeypatch.setattr(crs, "cleanup_canvas_recorder", lambda run_id: None)
    monkeypatch.setattr(crs, "CanvasWorkflowExecutor", _FakeExecutor)
    # start_run imports PromptInterceptionEngine inside the worker; stub the
    # module attribute path it uses.
    import types
    fake_mod = types.ModuleType("schemas.engine.prompt_interception_engine")
    fake_mod.PromptInterceptionEngine = lambda: object()
    monkeypatch.setitem(sys.modules, "schemas.engine.prompt_interception_engine", fake_mod)

    crs._reset_registry_for_tests()
    yield crs, storage, made
    crs._reset_registry_for_tests()


def _collect(gen, limit=100):
    out = []
    for rec in gen:
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def _wait_state(svc, run_id, states, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = svc.get_status(run_id)
        if st["state"] in states:
            return st
        time.sleep(0.02)
    return svc.get_status(run_id)


# ── job registry ─────────────────────────────────────────────────────────────

def test_start_events_complete(wired):
    svc, storage, _ = wired
    _FakeExecutor.script = [
        ("progress", {"node_id": "n1", "node_type": "input", "message": "go"}),
        ("node_complete", {"node_id": "n1", "node_type": "input"}),
        ("progress", {"node_id": "n2", "node_type": "generation", "message": "gen"}),
        ("node_complete", {"node_id": "n2", "node_type": "generation"}),
    ]
    _FakeExecutor.result = {"success": True, "results": {"n2": {"type": "generation"}},
                            "collector_items": [], "execution_trace": ["n1", "n2"]}
    _FakeExecutor.delay = 0.0

    run_id = svc.start_run(nodes=[{"id": "n1", "type": "input"}], connections=[])
    assert run_id.startswith("run_") and run_id.endswith("_canvas")

    events = _collect(svc.iter_events(run_id, after=-1))
    types_ = [e["type"] for e in events]
    # 4 executor events + a synthetic terminal 'complete'
    assert types_ == ["progress", "node_complete", "progress", "node_complete", "complete"]
    # running indices are contiguous from 0
    assert [e["_i"] for e in events] == [0, 1, 2, 3, 4]
    # complete carries run_id + exportPath
    assert events[-1]["data"]["run_id"] == run_id
    assert "exportPath" in events[-1]["data"]

    st = _wait_state(svc, run_id, {"complete"})
    assert st["state"] == "complete"
    assert st["n_events"] == 5

    # persisted: events.jsonl has all 5 lines; status.json says complete
    rf = storage / "2026-07-05" / "test-device" / run_id
    lines = [l for l in (rf / "events.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 5
    status = json.loads((rf / "status.json").read_text())
    assert status["state"] == "complete" and status["n_events"] == 5


def test_start_records_the_workflow_name(wired):
    svc, storage, made = wired
    _FakeExecutor.script = []
    _FakeExecutor.result = {"success": True, "results": {}, "collector_items": [],
                            "execution_trace": []}
    _FakeExecutor.delay = 0.0
    run_id = svc.start_run(nodes=[{"id": "n1", "type": "input"}], connections=[],
                           name="Zwei Lesarten")
    _collect(svc.iter_events(run_id, after=-1))
    workflow = json.loads((made[run_id].run_folder / "workflow.json").read_text(encoding="utf-8"))
    assert workflow["name"] == "Zwei Lesarten"
    assert workflow["nodes"] == [{"id": "n1", "type": "input"}]


def test_reconnect_after_index_gets_rest(wired):
    """A reader attaching at ?after=1 must get exactly events 2,3,4 (and the
    complete). Simulates a torn live stream reconnecting."""
    svc, storage, _ = wired
    _FakeExecutor.script = [
        ("progress", {"node_id": "n1", "node_type": "input"}),
        ("node_complete", {"node_id": "n1", "node_type": "input"}),
        ("progress", {"node_id": "n2", "node_type": "generation"}),
        ("node_complete", {"node_id": "n2", "node_type": "generation"}),
    ]
    _FakeExecutor.result = {"success": True, "results": {}, "collector_items": [],
                            "execution_trace": ["n1", "n2"]}
    _FakeExecutor.delay = 0.03  # let the first reader attach mid-run

    run_id = svc.start_run(nodes=[{"id": "n1", "type": "input"}], connections=[])
    # Reader A reads only the first two, then "drops".
    first_two = []
    gen = svc.iter_events(run_id, after=-1)
    for rec in gen:
        first_two.append(rec)
        if len(first_two) == 2:
            break
    assert [e["_i"] for e in first_two] == [0, 1]

    # let the job finish
    _wait_state(svc, run_id, {"complete", "error"})

    # Reader B reconnects at after=1 → must see 2,3,4 then terminal complete.
    rest = _collect(svc.iter_events(run_id, after=1))
    idxs = [e["_i"] for e in rest]
    assert idxs == [2, 3, 4]
    assert rest[-1]["type"] == "complete"


def test_reconnect_from_disk_when_buffer_trimmed(wired, monkeypatch):
    """Events older than the in-memory buffer window are replayed from
    events.jsonl on reconnect."""
    svc, storage, _ = wired
    monkeypatch.setattr(crs, "MAX_BUFFER_EVENTS", 2, raising=False)
    _FakeExecutor.script = [("progress", {"i": i}) for i in range(6)]
    _FakeExecutor.result = {"success": True, "results": {}, "collector_items": [],
                            "execution_trace": []}
    _FakeExecutor.delay = 0.0

    run_id = svc.start_run(nodes=[{"id": "n1", "type": "input"}], connections=[])
    _wait_state(svc, run_id, {"complete", "error"})

    # Buffer now holds only the last few; a reconnect from -1 must still yield
    # every event 0..N (early ones sourced from events.jsonl).
    all_ev = _collect(svc.iter_events(run_id, after=-1))
    idxs = [e["_i"] for e in all_ev]
    # 6 scripted + 1 complete = indices 0..6, all present and ordered
    assert idxs == list(range(7))


def test_error_result_yields_error_terminal(wired):
    svc, storage, _ = wired
    _FakeExecutor.script = [("progress", {"node_id": "n1", "node_type": "input"})]
    _FakeExecutor.result = {"success": False, "error": "boom"}
    _FakeExecutor.delay = 0.0

    run_id = svc.start_run(nodes=[{"id": "n1", "type": "input"}], connections=[])
    events = _collect(svc.iter_events(run_id, after=-1))
    assert events[-1]["type"] == "error"
    assert events[-1]["data"]["message"] == "boom"
    st = _wait_state(svc, run_id, {"error"})
    assert st["state"] == "error" and st["error"] == "boom"


def test_startup_hook_marks_running_interrupted(wired):
    svc, storage, _ = wired
    # Fabricate an orphaned run folder with status running.
    rf = storage / "2026-07-05" / "dev" / "run_orphan_abc_canvas"
    rf.mkdir(parents=True)
    crs._write_status_file(rf, "running", 3, started_at="2026-07-05T00:00:00")

    # A completed run must NOT be touched.
    rf2 = storage / "2026-07-05" / "dev" / "run_done_xyz_canvas"
    rf2.mkdir(parents=True)
    crs._write_status_file(rf2, "complete", 9)

    n = crs.mark_orphans_interrupted(base_path=storage)
    assert n == 1
    st = json.loads((rf / "status.json").read_text())
    assert st["state"] == "interrupted"
    assert st["error"]
    # untouched
    st2 = json.loads((rf2 / "status.json").read_text())
    assert st2["state"] == "complete"


def test_get_status_unknown_run(wired):
    svc, storage, _ = wired
    assert svc.get_status("run_nope_canvas")["state"] == "unknown"


# ── routes ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Flask client with JSON_STORAGE_DIR pointed at a tmp exports tree that
    already holds one torn canvas run (2 of 3 images finished)."""
    import config
    storage = tmp_path / "json"
    storage.mkdir(parents=True)
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", storage, raising=False)

    # Build a partial run on disk: metadata with 2 output_image entities +
    # a workflow.json declaring 3 generation nodes → prompts_pending == 1.
    run_id = "run_partialtest_001_canvas"
    rf = storage / "2026-07-05" / "dev-1" / run_id
    final = rf / "final"
    final.mkdir(parents=True)
    # two tiny PNG-ish files (content irrelevant for the partial listing route)
    (final / "02_output_image.png").write_bytes(b"\x89PNG\r\n\x1a\nAAA")
    (final / "04_output_image.png").write_bytes(b"\x89PNG\r\n\x1a\nBBB")
    metadata = {
        "run_id": run_id,
        "type": "canvas_workflow",
        "device_id": "dev-1",
        "entities": [
            {"sequence": 1, "type": "generation_prompt", "filename": "01_generation_prompt.txt", "metadata": {}},
            {"sequence": 2, "type": "output_image", "filename": "02_output_image.png",
             "metadata": {"config_id": "sd35_large", "file_index": 0}},
            {"sequence": 3, "type": "generation_prompt", "filename": "03_generation_prompt.txt", "metadata": {}},
            {"sequence": 4, "type": "output_image", "filename": "04_output_image.png",
             "metadata": {"config_id": "sd35_large", "file_index": 1}},
        ],
        # NOTE: no completed_at -> torn run
    }
    (rf / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (rf / "workflow.json").write_text(json.dumps({
        "nodes": [
            {"id": "g1", "type": "generation"},
            {"id": "g2", "type": "generation"},
            {"id": "g3", "type": "generation"},
            {"id": "i1", "type": "input"},
        ],
        "connections": [],
    }), encoding="utf-8")

    # A completed run for the "state: complete" branch.
    run_done = "run_partialtest_done_canvas"
    rfd = storage / "2026-07-05" / "dev-1" / run_done
    (rfd / "final").mkdir(parents=True)
    (rfd / "final" / "02_output_image.png").write_bytes(b"\x89PNG\r\n\x1a\nCCC")
    (rfd / "metadata.json").write_text(json.dumps({
        "run_id": run_done, "device_id": "dev-1", "completed_at": "2026-07-05T01:00:00",
        "entities": [{"sequence": 2, "type": "output_image", "filename": "02_output_image.png",
                      "metadata": {"file_index": 0}}],
    }), encoding="utf-8")

    from my_app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client(), run_id, run_done


def test_partial_route_lists_sorted_items(client):
    c, run_id, _ = client
    r = c.get(f"/api/canvas/partial/{run_id}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["run_id"] == run_id
    assert body["state"] == "partial"
    assert len(body["items"]) == 2
    # sorted by index; URLs reuse the media serve path
    assert [it["index"] for it in body["items"]] == [0, 1]
    assert body["items"][0]["url"] == f"/api/media/image/{run_id}/0"
    assert body["items"][1]["url"] == f"/api/media/image/{run_id}/1"
    assert all(it["kind"] == "image" for it in body["items"])
    # 3 generation nodes declared, 2 images present -> 1 pending
    assert body["prompts_pending"] == 1


def test_partial_route_complete_state(client):
    c, _, run_done = client
    r = c.get(f"/api/canvas/partial/{run_done}")
    assert r.status_code == 200
    assert r.get_json()["state"] == "complete"


def test_partial_route_unknown_id_404(client):
    c, _, _ = client
    r = c.get("/api/canvas/partial/run_does_not_exist_canvas")
    assert r.status_code == 404
    assert r.get_json()["state"] == "unknown"


def test_partial_route_traversal_rejected(client):
    c, _, _ = client
    # Traversal attempts must never reach the filesystem. Either Werkzeug rejects
    # the encoded-slash path outright (403/404), or the run_ shape guard trips
    # (400). None may 200.
    for bad in ["..%2f..%2fetc%2fpasswd", "run_../../../etc", "run_x/../y"]:
        r = c.get(f"/api/canvas/partial/{bad}")
        assert r.status_code in (400, 403, 404), f"{bad} -> {r.status_code}"
    # An explicit dotted id that fails the strict run_ shape:
    r = c.get("/api/canvas/partial/run_%2e%2e_canvas")
    assert r.status_code in (400, 403, 404)
    # A literal dot in the id also fails the guard (never a 200).
    r = c.get("/api/canvas/partial/run_a.b_canvas")
    assert r.status_code == 400


def test_status_route_shapes(client):
    c, run_id, _ = client
    # Unknown-but-valid id -> 200 unknown (no registry, no status.json here).
    r = c.get("/api/canvas/runs/run_valid_but_absent_canvas/status")
    assert r.status_code == 200
    assert r.get_json()["state"] == "unknown"
    # Bad shape -> rejected (400 from the guard, or 403/404 from Werkzeug).
    r = c.get("/api/canvas/runs/..%2fetc/status")
    assert r.status_code in (400, 403, 404)
    # A literal dot -> 400 from the strict run_ guard.
    r = c.get("/api/canvas/runs/run_a.b_canvas/status")
    assert r.status_code == 400
