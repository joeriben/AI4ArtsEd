"""What a chat model is handed of a run, a favourite or a kept strategy, by level.

The chats' answers are not checked since 2026-11-08: what reaches a chat model
can reach the room. A run's texts were checked at the level the run was made
at. At kids and youth the material of a run made at a looser level, or of one
that names no level, is therefore not handed to a chat model, by the rule the
favourites' restore asks (safety_gate.run_opens_at): not by the chat's page
context, not by view_run, not by lookup_shared_favorites. The global strategy
store keeps the least strict level any of a strategy's text was written at,
and canvas_graph_library asks the same rule of it. A canvas run records its
level, so that view_run can ask it.

The same rule holds for what the chat kept itself or was handed by a person at
another level: a run's stored conversation keeps each line's level, a
favourite's note the level it was written at, a remembered note the level of
its turn; an upload is looked at only with its pass for the level.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from my_app.services import canvas_workflow_store as store
from my_app.services import pipeline_recorder
from my_app.services.safety_gate import looser_level, run_opens_at
from my_app.services.tool_registry import get_tool_registry


@pytest.fixture
def storage(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr("my_app.routes.chat_routes.JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(store, "STORAGE_DIR", tmp_path / "canvas_workflows")
    pipeline_recorder._active_recorders.clear()
    yield tmp_path
    pipeline_recorder._active_recorders.clear()


def _run(storage, run_id, level, said="Ein Haus am See"):
    recorder = pipeline_recorder.get_recorder(run_id, config_name="bauhaus", safety_level=level,
                                              device_id="dev", base_path=storage)
    recorder.save_entity("input", said)
    recorder.save_entity("interception", f"{said}, gesehen")
    return recorder


def _tool(name, args, level):
    return get_tool_registry().execute(name, args, level=level)


# ── The rule ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("run_level, level, opens", [
    ("kids", "kids", True), ("youth", "kids", False), ("adult", "kids", False),
    ("kids", "youth", True), ("youth", "youth", True), ("adult", "youth", False),
    ("research", "youth", False), (None, "kids", False), (None, "youth", False),
    ("research", "adult", True), (None, "adult", True), (None, "research", True),
])
def test_a_run_opens_at_its_level_and_looser_ones_below_adult(run_level, level, opens):
    assert run_opens_at(run_level, level) is opens


def test_the_looser_of_several_levels_and_unknown_for_a_non_level():
    assert looser_level("kids") == "kids"
    assert looser_level("kids", "adult") == "adult"
    assert looser_level("research", "youth") == "research"
    assert looser_level("kids", None) is None
    assert looser_level("kids", "teens") is None
    assert looser_level() is None


# ── The chat's page context ─────────────────────────────────────────────────

def test_the_page_context_leaves_out_a_looser_runs_texts(storage):
    from my_app.routes.chat_routes import load_session_context
    _run(storage, "run_ctx_adult", "adult")
    context = load_session_context("run_ctx_adult", "kids")["context"]
    assert "Ein Haus" not in context["input_text"]
    assert "Ein Haus" not in context["interception_text"]
    assert context["safety_level"] == "adult"


@pytest.mark.parametrize("asking", ["youth", "adult"])
def test_the_page_context_carries_a_runs_texts_where_it_opens(storage, asking):
    from my_app.routes.chat_routes import load_session_context
    _run(storage, "run_ctx_youth", "youth")
    context = load_session_context("run_ctx_youth", asking)["context"]
    assert context["input_text"] == "Ein Haus am See"


# ── view_run ────────────────────────────────────────────────────────────────

def test_view_run_does_not_open_a_looser_run(storage):
    _run(storage, "run_view_adult", "adult")
    result = _tool("view_run", {"run_id": "run_view_adult"}, "kids")
    assert result.startswith("Error:")
    assert "Ein Haus" not in result


@pytest.mark.parametrize("asking", ["kids", "adult"])
def test_view_run_opens_a_run_where_it_opens(storage, asking):
    _run(storage, "run_view_kids", "kids")
    result = _tool("view_run", {"run_id": "run_view_kids"}, asking)
    assert "Ein Haus am See" in result


def _canvas_run(storage, run_id, level):
    run_dir = storage / "2026-11-14" / "dev" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(json.dumps({"type": "complete", "data": {
        "results": {"ic1": {"type": "interception", "output": "Ein Turm aus Glas"}}}}) + "\n",
        encoding="utf-8")
    if level != "missing":
        (run_dir / "metadata.json").write_text(json.dumps({"safety_level": level}),
                                               encoding="utf-8")


@pytest.mark.parametrize("run_level, asking, opens", [
    ("kids", "kids", True), ("adult", "kids", False), ("adult", "youth", False),
    ("missing", "kids", False), ("missing", "adult", True), ("adult", "adult", True),
])
def test_view_run_asks_an_apparatus_runs_level(storage, run_level, asking, opens):
    _canvas_run(storage, "run_cv_canvas", run_level)
    result = _tool("view_run", {"run_id": "run_cv_canvas"}, asking)
    assert ("Ein Turm aus Glas" in result) is opens
    assert result.startswith("Error:") is (not opens)


def test_a_canvas_run_records_its_level(storage, monkeypatch):
    from my_app.services import canvas_run_service
    monkeypatch.setattr(canvas_run_service, "_worker", lambda *args, **kwargs: None)
    run_id = canvas_run_service.start_run(nodes=[], connections=[], device_id="dev",
                                          safety_level="youth")
    folder = next(storage.glob(f"*/dev/{run_id}"))
    assert json.loads((folder / "metadata.json").read_text())["safety_level"] == "youth"


# ── lookup_shared_favorites ─────────────────────────────────────────────────

def test_the_favourites_tool_leaves_out_a_looser_runs_favourite_whole(storage):
    _run(storage, "run_fav_kids", "kids", said="Ein Baum")
    _run(storage, "run_fav_adult", "adult", said="Ein Schiff")
    (storage / "favorites.json").write_text(json.dumps({"version": "1.0", "mode": "global",
        "favorites": [
            {"run_id": "run_fav_adult", "media_type": "image", "user_note": "unser Schiff",
             "note_level": "adult"},
            {"run_id": "run_fav_kids", "media_type": "image", "user_note": "unser Baum",
             "note_level": "kids"},
            {"run_id": "run_gone", "media_type": "image", "user_note": "weg"},
        ]}), encoding="utf-8")
    at_kids = _tool("lookup_shared_favorites", {}, "kids")
    assert "Ein Baum" in at_kids and "unser Baum" in at_kids
    assert "Schiff" not in at_kids and "run_fav_adult" not in at_kids
    assert "run_gone" not in at_kids
    assert "1 kept in total" in at_kids
    at_adult = _tool("lookup_shared_favorites", {}, "adult")
    assert "Ein Schiff" in at_adult and "run_gone" in at_adult
    assert "3 kept in total" in at_adult


# ── canvas_graph_library ────────────────────────────────────────────────────

GRAPH = {
    "nodes": [
        {"id": "in1", "type": "input", "promptText": "a tree"},
        {"id": "tr1", "type": "translation"},
        {"id": "gn1", "type": "generation", "configId": "sd35_large"},
    ],
    "connections": [{"sourceId": "in1", "targetId": "tr1"},
                    {"sourceId": "tr1", "targetId": "gn1"}],
}


def _save(level, title="Ein Weg"):
    saved = _tool("canvas_graph_library",
                  {"action": "save", "title": title, "graph": GRAPH}, level)
    assert saved.startswith("Kept strategy"), saved
    return store.list_strategies()[0]["id"]


def test_a_kept_strategy_records_the_level_it_was_written_at(storage):
    sid = _save("youth")
    assert store.get_strategy(sid)["safety_level"] == "youth"


def test_a_strategy_without_a_level_counts_as_written_at_the_strictest(storage):
    sid = _save(None)
    assert store.get_strategy(sid)["safety_level"] == "kids"


@pytest.mark.parametrize("action, extra", [
    ("get", {}),
    ("revise", {"graph": GRAPH, "memo": "anders"}),
    ("feedback", {"note": "gut"}),
])
def test_a_looser_strategy_is_not_opened_at_kids(storage, action, extra):
    sid = _save("adult", title="Ein Schiff")
    before = store.get_strategy(sid)
    result = _tool("canvas_graph_library", {"action": action, "workflow_id": sid, **extra},
                   "kids")
    assert result.startswith("Error:") and "Schiff" not in result
    after = store.get_strategy(sid)
    assert after["versions"] == before["versions"]


def test_the_list_holds_what_opens_at_the_asking_level(storage):
    _save("adult", title="Ein Schiff")
    _save("kids", title="Ein Baum")
    at_kids = _tool("canvas_graph_library", {"action": "list"}, "kids")
    assert "Ein Baum" in at_kids and "Schiff" not in at_kids
    at_youth = _tool("canvas_graph_library", {"action": "list"}, "youth")
    assert "Ein Baum" in at_youth and "Schiff" not in at_youth
    at_adult = _tool("canvas_graph_library", {"action": "list"}, "adult")
    assert "Ein Baum" in at_adult and "Ein Schiff" in at_adult


@pytest.mark.parametrize("action, extra", [
    ("revise", {"graph": GRAPH, "memo": "anders"}),
    ("feedback", {"note": "gut"}),
])
def test_a_text_written_at_a_looser_level_makes_the_strategy_looser(storage, action, extra):
    sid = _save("kids")
    result = _tool("canvas_graph_library", {"action": action, "workflow_id": sid, **extra},
                   "adult")
    assert not result.startswith("Error:"), result
    assert store.get_strategy(sid)["safety_level"] == "adult"
    assert _tool("canvas_graph_library", {"action": "get", "workflow_id": sid},
                 "kids").startswith("Error:")


def test_a_strategy_kept_before_levels_were_recorded_opens_above_youth_only(storage):
    sid = _save("kids")
    path = store.STORAGE_DIR / f"{sid}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["safety_level"]
    path.write_text(json.dumps(record), encoding="utf-8")
    assert _tool("canvas_graph_library", {"action": "get", "workflow_id": sid},
                 "youth").startswith("Error:")
    assert not _tool("canvas_graph_library", {"action": "get", "workflow_id": sid},
                     "adult").startswith("Error:")


# ── a run's stored conversation ─────────────────────────────────────────────

def _stored(storage, run_id, lines):
    recorder = pipeline_recorder.load_recorder(run_id, base_path=storage)
    path = recorder.run_folder / "chat_history.json"
    path.write_text(json.dumps(lines), encoding="utf-8")
    return path


ADULT_TURN = [{"role": "user", "content": "Frage A", "safety_level": "adult"},
              {"role": "assistant", "content": "Antwort A", "safety_level": "adult"}]
KIDS_TURN = [{"role": "user", "content": "Frage K", "safety_level": "kids"},
             {"role": "assistant", "content": "Antwort K", "safety_level": "kids"}]
OLD_TURN = [{"role": "user", "content": "Frage alt"},
            {"role": "assistant", "content": "Antwort alt"}]


@pytest.mark.parametrize("asking, kept", [
    ("kids", ["Frage K", "Antwort K"]),
    ("youth", ["Frage K", "Antwort K"]),
    ("adult", ["Frage A", "Antwort A", "Frage K", "Antwort K", "Frage alt", "Antwort alt"]),
])
def test_a_stored_conversation_is_handed_on_where_each_line_opens(asking, kept):
    from my_app.routes.chat_routes import _history_at
    lines = ADULT_TURN + KIDS_TURN + OLD_TURN
    assert [m["content"] for m in _history_at(lines, asking)] == kept


def test_a_turn_at_kids_is_not_handed_the_lines_of_adult_and_keeps_them(
        storage, monkeypatch, chat_checks_pass):
    from flask import Flask
    from my_app.routes import chat_routes
    _run(storage, "run_hist", "kids")
    path = _stored(storage, "run_hist", ADULT_TURN + KIDS_TURN)
    handed = {}

    def helper(**kwargs):
        handed["messages"] = kwargs["messages"]
        yield ("result", {"content": "gut", "thinking": None, "tool_calls": None,
                          "model_used": "stand-in/one"})

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    with Flask(__name__).test_request_context("/api/chat", json={}):
        list(chat_routes._chat_events({"message": "und nun?", "run_id": "run_hist",
                                       "context": {"language": "de"}}, "kids"))
    said = " ".join(str(m["content"]) for m in handed["messages"] if m["role"] != "system")
    assert "Antwort K" in said and "Antwort A" not in said
    kept = json.loads(path.read_text(encoding="utf-8"))
    assert [m["content"] for m in kept[:4]] == ["Frage A", "Antwort A", "Frage K", "Antwort K"]
    assert [(m["role"], m["content"], m["safety_level"]) for m in kept[4:]] == [
        ("user", "und nun?", "kids"), ("assistant", "gut", "kids")]


def test_the_history_route_shows_what_opens_at_the_resolved_level(storage, monkeypatch):
    from flask import Flask
    from my_app.routes import chat_routes
    _run(storage, "run_hist_get", "kids")
    _stored(storage, "run_hist_get", ADULT_TURN + KIDS_TURN)
    monkeypatch.setattr(chat_routes, "resolve_safety_level", lambda: "kids")
    app = Flask(__name__)
    app.register_blueprint(chat_routes.chat_bp)
    history = app.test_client().get("/api/chat/history/run_hist_get").get_json()["history"]
    assert [m["content"] for m in history] == ["Frage K", "Antwort K"]


# ── a favourite's note ──────────────────────────────────────────────────────

@pytest.mark.parametrize("note_level, asking, shown", [
    ("kids", "kids", True), ("adult", "kids", False), (None, "kids", False),
    ("adult", "youth", False), ("adult", "adult", True), (None, "adult", True),
])
def test_a_note_is_handed_on_where_its_level_opens(storage, note_level, asking, shown):
    _run(storage, "run_note", "kids", said="Ein Baum")
    fav = {"run_id": "run_note", "media_type": "image", "user_note": "unser Baumhaus"}
    if note_level:
        fav["note_level"] = note_level
    (storage / "favorites.json").write_text(json.dumps(
        {"version": "1.0", "mode": "global", "favorites": [fav]}), encoding="utf-8")
    result = _tool("lookup_shared_favorites", {}, asking)
    assert "Ein Baum" in result
    assert ("unser Baumhaus" in result) is shown
    found = _tool("lookup_shared_favorites", {"query": "Baumhaus"}, asking)
    assert ("unser Baumhaus" in found) is shown


# ── a remembered note ───────────────────────────────────────────────────────

@pytest.fixture
def memory(monkeypatch, tmp_path):
    from my_app.services import resona_memory
    monkeypatch.setattr(resona_memory, "STORAGE_DIR", tmp_path / "resona_memory")
    return resona_memory


def test_a_remembered_note_keeps_the_level_of_its_turn(memory):
    ctx = {"device_id": "dev-mem", "run_id": None}
    reg = get_tool_registry()
    assert reg.execute("remember", {"kind": "note", "content": "Wellen aus Papier"},
                       context=ctx, level="youth").startswith("Remembered")
    assert memory.load_all("dev-mem")[0]["safety_level"] == "youth"


@pytest.mark.parametrize("written, asking, found", [
    ("kids", "kids", True), ("adult", "kids", False), (None, "youth", False),
    ("adult", "adult", True), (None, "adult", True),
])
def test_recall_and_the_digest_hold_what_opens(memory, written, asking, found):
    from my_app.routes.chat_routes import _build_resona_memory_digest
    memory.remember("dev-mem", "note", "Wellen aus Papier", safety_level=written)
    ctx = {"device_id": "dev-mem", "run_id": None}
    recalled = get_tool_registry().execute("recall", {"query": "Wellen"}, context=ctx,
                                           level=asking)
    assert ("Wellen aus Papier" in recalled) is found
    assert ("Wellen aus Papier" in _build_resona_memory_digest("dev-mem", asking)) is found


# ── an upload ───────────────────────────────────────────────────────────────

UPLOAD = "c3d4e5f6-a7b8-4c9d-8e0f-2a3b4c5d6e7f"


@pytest.fixture
def upload(monkeypatch, tmp_path):
    from PIL import Image
    from my_app.services.llm_service import llm_service
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", tmp_path)
    Image.new("RGB", (8, 8), (20, 120, 220)).save(tmp_path / f"{UPLOAD}.png", format="PNG")
    looked = []
    monkeypatch.setattr(llm_service, "describe_image_neutral",
                        lambda b64: looked.append(b64) or "a blue square")
    return looked


def _view(asking):
    return get_tool_registry().execute("view_upload", {"upload_id": UPLOAD},
                                       context={"brought_upload_ids": [UPLOAD]}, level=asking)


@pytest.mark.parametrize("asking", ["kids", "youth"])
def test_an_upload_without_a_pass_is_not_looked_at_below_adult(upload, asking):
    result = _view(asking)
    assert result.startswith("Error:") and "not looked at" in result
    assert upload == []


@pytest.mark.parametrize("passed_at, asking, looked", [
    ("kids", "kids", True), ("kids", "youth", True), ("youth", "kids", False),
])
def test_an_upload_is_looked_at_with_its_pass(upload, passed_at, asking, looked):
    from my_app.services import safety_gate
    safety_gate.record_upload_verdict(UPLOAD, safety_gate.Verdict(
        True, safety_gate.CHECKPOINT_INTAKE, passed_at, "image"))
    result = _view(asking)
    assert ("a blue square" in result) is looked
    assert (upload != []) is looked


def test_an_upload_is_looked_at_at_adult_without_a_pass(upload):
    assert "a blue square" in _view("adult")


# ── Together's journal ──────────────────────────────────────────────────────

@pytest.fixture
def journal(monkeypatch, tmp_path):
    from my_app.services import resona_journal
    monkeypatch.setattr(resona_journal, "STORAGE_DIR", tmp_path / "resona_journal")
    return resona_journal


def _round(journal, jid, written, said, intent):
    journal.append_dialog_batch(
        jid, [("user", f"Frage {said}"), ("assistant", f"Antwort {said}")],
        device_id="dev-j", lang="de",
        media_intents=[{"intent_id": intent, "config_id": "sd35_large",
                        "prompt": f"Bild {said}"}],
        safety_level=written)
    journal.append_event(jid, "memory", {"kind": "Notiz", "content": f"Notiz {said}",
                                         "safety_level": written}, device_id="dev-j")
    journal.append_event(jid, "media_result", {"intent_id": intent, "status": "completed",
                                               "run_id": f"run_{said}", "media_type": "image"},
                         device_id="dev-j")


@pytest.fixture
def three_rounds(journal):
    """One round at adult, one at kids and one from before events carried a level."""
    jid = journal.ensure("dev-j")["journal_id"]
    _round(journal, jid, "adult", "A", "mi_a")
    _round(journal, jid, "kids", "K", "mi_k")
    _round(journal, jid, None, "alt", "mi_alt")
    return jid


def test_a_round_writes_its_level_into_the_journal(journal, three_rounds):
    events = journal.read_events(three_rounds)["events"]
    levels = {(e["type"], (e["payload"].get("content") or e["payload"].get("prompt")
                           or e["payload"].get("run_id"))): e["payload"].get("safety_level")
              for e in events if e["type"] != "journal"}
    assert levels[("dialog", "Frage A")] == "adult"
    assert levels[("dialog", "Antwort K")] == "kids"
    assert levels[("media_intent", "Bild K")] == "kids"
    assert levels[("memory", "Notiz A")] == "adult"
    assert levels[("dialog", "Frage alt")] is None


@pytest.mark.parametrize("asking, kept", [
    ("kids", {"K"}), ("youth", {"K"}), ("adult", {"A", "K", "alt"}),
])
def test_the_journal_is_handed_on_where_each_event_opens(journal, three_rounds, asking, kept):
    events = journal.events_at(journal.read_events(three_rounds)["events"], asking)
    said = set()
    for e in events:
        p = e["payload"]
        text = p.get("content") or p.get("prompt") or p.get("run_id") or ""
        if e["type"] != "journal":
            said.add(text.split(" ")[-1].split("_")[-1])
    assert said == kept


def test_the_journal_route_shows_what_opens_at_the_resolved_level(journal, three_rounds,
                                                                  monkeypatch):
    from flask import Flask
    from my_app.routes import resona_routes
    monkeypatch.setattr(resona_routes, "resolve_safety_level", lambda: "kids")
    app = Flask(__name__)
    app.register_blueprint(resona_routes.resona_bp)
    body = app.test_client().get(f"/api/resona/journal/{three_rounds}?offset=0&limit=500")
    events = body.get_json()["events"]
    dialog = [e["payload"]["content"] for e in events if e["type"] == "dialog"]
    assert dialog == ["Frage K", "Antwort K"]
    assert [e["payload"]["run_id"] for e in events if e["type"] == "media_result"] == ["run_K"]


@pytest.mark.parametrize("asking, shown, hidden", [
    ("kids", ["run_K", "Bild K"], ["run_A", "Bild A", "run_alt", "Bild alt"]),
    ("adult", ["run_A", "Bild A", "run_K", "run_alt"], []),
])
def test_the_runs_on_the_table_are_those_that_open(journal, three_rounds, asking, shown,
                                                   hidden):
    from my_app.routes.chat_routes import _build_resona_runs_context
    ctx = _build_resona_runs_context(three_rounds, asking)
    for said in shown:
        assert said in ctx
    for said in hidden:
        assert said not in ctx


def test_a_turn_writes_its_level_into_the_journal(storage, journal, monkeypatch,
                                                  chat_checks_pass):
    from flask import Flask
    from my_app.routes import chat_routes
    jid = journal.ensure("dev-j")["journal_id"]

    def helper(**kwargs):
        yield ("result", {"content": "gut", "thinking": None, "tool_calls": None,
                          "model_used": "stand-in/one"})

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    with Flask(__name__).test_request_context("/api/chat", json={}):
        list(chat_routes._chat_events({"message": "und nun?", "context": {
            "resona_mode": True, "language": "de", "device_id": "dev-j",
            "journal_id": jid}}, "youth"))
    dialog = [e["payload"] for e in journal.read_events(jid)["events"] if e["type"] == "dialog"]
    assert [(d["content"], d.get("safety_level")) for d in dialog] == [
        ("und nun?", "youth"), ("gut", "youth")]


# ── the favourites' list ────────────────────────────────────────────────────

@pytest.mark.parametrize("note_level, asking, shown", [
    ("kids", "kids", True), ("adult", "kids", False), (None, "kids", False),
    ("adult", "adult", True), (None, "adult", True),
])
def test_the_favourites_list_shows_a_note_where_its_level_opens(storage, monkeypatch,
                                                                note_level, asking, shown):
    from flask import Flask
    from my_app.routes import favorites_routes
    _run(storage, "run_list", "kids")
    # A kept sound: at kids a picture is listed only with its verdict (_listable).
    fav = {"run_id": "run_list", "media_type": "audio", "user_note": "unser Baumhaus",
           "device_id": "dev", "user_id": "anonymous", "added_at": "2026-11-14T10:00:00"}
    if note_level:
        fav["note_level"] = note_level
    (storage / "favorites.json").write_text(json.dumps(
        {"version": "1.0", "mode": "global", "favorites": [fav]}), encoding="utf-8")
    monkeypatch.setattr(favorites_routes, "JSON_STORAGE_DIR", storage)
    monkeypatch.setattr(favorites_routes, "resolve_safety_level", lambda: asking)
    app = Flask(__name__)
    app.register_blueprint(favorites_routes.favorites_bp)
    listed = app.test_client().get("/api/favorites?device_id=dev&view_mode=global").get_json()
    notes = [f.get("user_note") for f in listed["favorites"]]
    assert notes == (["unser Baumhaus"] if shown else [""])


# ── the lookup above youth reads only the run records it shows ──────────────

def test_the_lookup_above_youth_reads_no_more_records_than_it_shows(storage, monkeypatch):
    for i in range(12):
        _run(storage, f"run_many_{i}", "kids", said=f"Haus {i}")
    favs = [{"run_id": f"run_many_{i}", "media_type": "image"} for i in range(12)]
    (storage / "favorites.json").write_text(json.dumps(
        {"version": "1.0", "mode": "global", "favorites": favs}), encoding="utf-8")
    pipeline_recorder._active_recorders.clear()
    read = []
    real = pipeline_recorder.load_recorder
    monkeypatch.setattr(pipeline_recorder, "load_recorder",
                        lambda run_id, base_path=None: read.append(run_id) or real(
                            run_id, base_path=base_path))
    result = _tool("lookup_shared_favorites", {"limit": 3}, "adult")
    assert "Haus 0" in result
    assert len(read) == 3


# ── view_favorite ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("run_level, asking, opened", [
    ("adult", "kids", False), ("adult", "youth", False), ("youth", "kids", False),
    ("kids", "kids", True), ("kids", "youth", True),
    ("adult", "adult", True),
])
def test_view_favorite_opens_a_favourite_where_its_run_opens(storage, run_level, asking,
                                                             opened):
    _run(storage, "run_vf", run_level)
    (storage / "favorites.json").write_text(json.dumps(
        {"version": "1.0", "mode": "global",
         "favorites": [{"run_id": "run_vf", "media_type": "image"}]}), encoding="utf-8")
    result = _tool("view_favorite", {"run_id": "run_vf"}, asking)
    assert ("is not opened here" in result) is not opened


# ── a favourite brought to Together's board ─────────────────────────────────

@pytest.mark.parametrize("run_level, asking, kept", [
    ("adult", "kids", False), ("youth", "kids", False), ("kids", "kids", True),
    ("kids", "youth", True), ("adult", "adult", True),
])
def test_a_brought_favourite_goes_on_where_its_run_opens(storage, run_level, asking, kept):
    from my_app.routes.chat_routes import _brought_at
    _run(storage, "run_br", run_level)
    items = [{"kind": "favorite", "media_type": "image", "run_id": "run_br"},
             {"kind": "text", "excerpt": "unsere Notiz"}]
    shown = _brought_at(items, asking)
    assert ({"kind": "favorite", "media_type": "image", "run_id": "run_br"} in shown) is kept
    assert {"kind": "text", "excerpt": "unsere Notiz"} in shown


def test_a_brought_favourite_whose_run_is_gone_does_not_go_on_below_adult(storage):
    from my_app.routes.chat_routes import _brought_at
    items = [{"kind": "favorite", "media_type": "image", "run_id": "run_gone"}]
    assert _brought_at(items, "kids") == []
    assert _brought_at(items, "adult") == items
