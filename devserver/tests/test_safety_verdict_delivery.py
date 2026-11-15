"""
The content check's verdict must reach delivery.

Written after the leak it guards against: the verdict was recorded as a separate
entity of type "error" carrying `stage` and `error_type` and NOTHING that named
the picture it condemned, while delivery addressed pictures through
`output_image` entities and an index. Two registers that never met — a blocked
picture stayed in `final/` and every delivery route handed it out.

Two kinds of test here:

* the rule itself, exercised on records built by hand, and
* a structural guard over EVERY place a recorded output turns into a file.
  The first version of that guard named one such place and called it the only
  one; there were eight. So it now scans for the move — reaching into a run's
  `final/` folder — and holds an audited list of who may make it and why.
"""

import ast
import io
import re
from pathlib import Path

import pytest

from my_app.services.pipeline_recorder import (
    entity_cleared_for_delivery,
    filter_deliverable,
    public_entity,
)

from file_modules import REPO

RECORDER = REPO / "devserver" / "my_app" / "services" / "pipeline_recorder.py"


def _image(sequence=1, safety=None):
    entity = {"sequence": sequence, "type": "output_image", "filename": f"{sequence:02d}_output_image.png", "metadata": {}}
    if safety is not None:
        entity["metadata"]["safety"] = safety
    return entity


def _run(level="kids"):
    return {"safety_level": level}


# ---------------------------------------------------------------- the rule


def test_unmarked_picture_is_refused_where_verdicts_are_kept():
    """The heart of it: no verdict, no delivery. This is the fail-open that was."""
    cleared, reason = entity_cleared_for_delivery(_image(), _run("kids"), "kids")
    assert cleared is False
    assert reason == "unchecked"


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_picture_marked_unsafe_is_refused(level):
    entity = _image(safety={"safe": False, "reason": "S1"})
    cleared, reason = entity_cleared_for_delivery(entity, _run(level), level)
    assert cleared is False
    assert reason == "blocked"


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_picture_marked_safe_is_delivered(level):
    entity = _image(safety={"safe": True, "reason": ""})
    cleared, reason = entity_cleared_for_delivery(entity, _run(level), level)
    assert cleared is True
    assert reason == ""


def test_a_truthy_non_true_verdict_does_not_clear():
    """`safe` must BE True. A string, a 1, a dict — none of those is a verdict."""
    for value in ("yes", 1, {}, [], "False"):
        entity = _image(safety={"safe": value})
        cleared, _ = entity_cleared_for_delivery(entity, _run("kids"), "kids")
        assert cleared is False, f"{value!r} cleared a picture"


def test_a_verdict_that_is_not_a_mapping_does_not_clear():
    for value in ("safe", True, 1, ["safe"]):
        entity = _image()
        entity["metadata"]["safety"] = value
        cleared, reason = entity_cleared_for_delivery(entity, _run("kids"), "kids")
        assert cleared is False
        assert reason == "unchecked"


# ------------------------------------------------- where the rule stays silent


@pytest.mark.parametrize("requester", ["adult", "research"])
def test_a_requester_whose_level_checks_no_pictures_is_handed_them(requester):
    """Above youth no picture is held against a check, so delivery withholds
    none: not an unjudged one, and not one a stricter level refused."""
    assert entity_cleared_for_delivery(_image(), _run("kids"), requester)[0] is True
    refused = _image(safety={"safe": False, "reason": "S1", "level": "kids"})
    assert entity_cleared_for_delivery(refused, _run("kids"), requester)[0] is True


@pytest.mark.parametrize("requester", ["", None, "teens"])
def test_a_requester_without_a_level_is_asked_as_the_strictest(requester):
    """What is not a level counts as kids, the direction the resolver falls in."""
    at_youth = _image(safety={"safe": True, "level": "youth"})
    assert entity_cleared_for_delivery(at_youth, _run("youth"), requester)[0] is False
    at_kids = _image(safety={"safe": True, "level": "kids"})
    assert entity_cleared_for_delivery(at_kids, _run("kids"), requester)[0] is True


@pytest.mark.parametrize("kind", ["audio", "midi", "music"])
def test_kinds_without_a_check_are_untouched(kind):
    """
    A kind that no check at the result looks at goes out as it did. Refusing
    sound at kids level over a check that does not exist would take away work
    and protect no one. The gap is real and named in the plan; it is a
    different gap.
    """
    entity = {"sequence": 1, "type": f"output_{kind}", "filename": "x", "metadata": {}}
    cleared, _ = entity_cleared_for_delivery(entity, _run("kids"), "kids")
    assert cleared is True


def test_a_run_recorded_before_verdicts_is_refused_to_kids():
    """
    A run whose record predates per-picture verdicts carries none. Such runs
    counted as cleared while delivery read the level of the run; at kids and
    youth they are not shown any more, and above youth nothing changes.
    """
    old = {"safety_level": "kids", "entities": []}
    assert entity_cleared_for_delivery(_image(), old, "kids") == (False, "unchecked")
    assert entity_cleared_for_delivery(_image(), old, "adult") == (True, "")


def test_non_output_entities_pass():
    for etype in ("input", "translation", "interception", "safety", "error"):
        entity = {"sequence": 1, "type": etype, "filename": "x", "metadata": {}}
        assert entity_cleared_for_delivery(entity, _run("kids"), "kids")[0] is True


def test_filter_keeps_order_and_drops_only_the_refused():
    safe_a = _image(1, {"safe": True})
    blocked = _image(2, {"safe": False, "reason": "S1"})
    safe_b = _image(3, {"safe": True})
    kept = filter_deliverable([safe_a, blocked, safe_b], _run("kids"), "kids")
    assert [e["sequence"] for e in kept] == [1, 3]


# ------------------------------------------------------- the structural guard


def _function_source(path: Path, name: str) -> str:
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(io.open(path, encoding="utf-8").read(), node) or ""
    raise AssertionError(f"{path.name} has no function {name}")


# The audited set: every place in the backend that builds a path inside a run's
# `final/` folder, with what it does there. A picture becomes bytes by exactly
# this move, so this list IS the surface — and the first version of this guard
# named ONE of them and called it "the single place", which was wrong by seven.
#
# A new entry here is a decision: either the path leads to a generated picture,
# and then it asks the verdict, or it does not, and the reason is written down.
AUDITED_FINAL_FOLDER_USERS = {
    # --- asks the verdict -------------------------------------------------
    # The places that no longer appear here go through the recorder instead and
    # build no path of their own any more: backend_router._resolve_media_url_to_path
    # (a picture becoming the NEXT run's input), favorites_routes._image_file
    # and tool_registry.view_favorite.
    ("media_ref.py", "_from_run"):
        "asks entity_cleared_for_delivery — the resolver behind every vision path",
    ("pipeline_recorder.py", "checked_entity_path"): "the checked door itself",
    ("pipeline_recorder.py", "checked_path_for_filename"): "the same door, by name",
    ("media_routes.py", "_resolve_image"): "asks _entity_refusal, answers 403",
    ("media_routes.py", "get_p5"): "a sketch: asks _code_withheld, answers 403",
    ("media_routes.py", "get_tonejs"): "a sketch: asks _code_withheld, answers 403",
    ("media_routes.py", "get_sonicpi"): "Sonic Pi code: asks _code_withheld, answers 403",
    ("media_routes.py", "get_video"): "a video: asks _entity_refusal, answers 403",
    ("media_routes.py", "get_3d_mesh"):
        "a 3D model: asks _entity_refusal (its preview's verdict), answers 403",
    ("media_routes.py", "_run_analyze_av"):
        "reads a video after asking _entity_refusal, answers 403; sound has no "
        "check at the result",
    ("tool_registry.py", "view_run"): "asks checked_entity_path",
    # --- reads past the verdict, on purpose and named ---------------------
    ("pipeline_recorder.py", "unchecked_entity_path_for_checking"):
        "the content check has to read the picture in order to judge it",
    # --- writes, rather than hands out ------------------------------------
    ("pipeline_recorder.py", "save_entity"): "writes the file",
    ("canvas_recorder.py", "save_entity"): "writes the file",
    ("latent_lab_recorder.py", "record"): "writes the file",
    ("latent_lab_recorder.py", "replace_output_image"): "writes the file",
    # --- no picture ------------------------------------------------------
    ("media_routes.py", "get_audio"): "sound, which has no output check anywhere",
    ("media_routes.py", "get_music"): "sound, likewise",
    ("media_routes.py", "get_midi"): "notation",
    ("media_routes.py", "get_media_disclosure"): "the disclosure text",
    ("media_routes.py", "get_media_info"): "sizes and names, no picture bytes",
    ("favorites_routes.py", "get_favorites"): "the run's TEXT, for the list entry",
    ("favorites_routes.py", "get_restore_data"): "the text trace of a run",
    ("favorites_routes.py", "_canvas_workflow_of"):
        "a kept Canvas board's workflow JSON (nodes and connections), no picture",
    ("tool_registry.py", "_texts"): "the text trace of a run",
    ("canvas_routes.py", "get_canvas_partial"): "builds /api/media URLs, no bytes",
    ("canvas_recorder.py", "get_entity_path"): "the canvas register, its own surface",
    ("latent_lab_recorder.py", "instrument_from_metadata"): "a timestamp off the file",
    ("mean_images_routes.py", "_latent_of"): "a latent, which is no picture",
}


def test_every_path_built_from_a_runs_folder_is_audited():
    """
    The guard the first attempt got wrong.

    Reaching into `final/` is how a recorded output becomes a file, and every
    such place either asks the content check or has a reason not to. Scanning
    for the move itself — rather than trusting one function to be "the" place —
    is what makes the next one visible.
    """
    # Both trees: the engine reaches into a run's folder too, and the first
    # version of this scan looked only at `my_app` — which is where a blocked
    # picture could go back in as the next run's input, unseen.
    roots = [REPO / "devserver" / "my_app", REPO / "devserver" / "schemas"]
    unaudited = []
    found = set()
    for path in sorted(p for root in roots for p in root.rglob("*.py")):
        text = io.open(path, encoding="utf-8").read()
        if "final_folder" not in text:
            continue
        tree = ast.parse(text)
        spans = [
            (n.lineno, n.end_lineno, n.name)
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for i, line in enumerate(text.splitlines(), start=1):
            # `recorder.final_folder / x` AND `Path(recorder.final_folder) / x`.
            # Matching the bare first spelling is how this scan ran green while
            # the resolver every vision path goes through built its path in the
            # second one.
            if not re.search(r"final_folder\s*\)?\s*/", line):
                continue
            holder = max(
                (s for s in spans if s[0] <= i <= s[1]),
                key=lambda s: s[0], default=None,
            )
            key = (path.name, holder[2] if holder else "<module>")
            found.add(key)
            if key not in AUDITED_FINAL_FOLDER_USERS:
                unaudited.append(f"{path.name}:{i} in {key[1]}")

    assert not unaudited, (
        "these reach into a run's final/ folder without being audited — each one "
        "either asks the content check or states why it needs no verdict: "
        + ", ".join(unaudited)
    )

    # And the other direction: an entry that names a place which no longer makes
    # this move is a claim about the code that has stopped being true. Left
    # standing, the list would read as coverage it does not have.
    stale = sorted(set(AUDITED_FINAL_FOLDER_USERS) - found)
    assert not stale, (
        "these are listed as audited but no longer reach into a run's folder — "
        f"the list is describing code that has moved: {stale}"
    )


# The functions that read a picture or a video past its verdict, so that the
# check can read what it is about to judge. Every way lists its pictures for
# the check at the result through _pictures_of_run, and its videos through
# _videos_of_run.
CONTENT_CHECKS = {
    "schema_pipeline_routes.py:_pictures_of_run",
    "schema_pipeline_routes.py:_videos_of_run",
}


def test_only_the_content_check_reads_past_the_verdict():
    """
    One door leads to a picture without asking its verdict, and it exists so the
    check can read what it is about to judge. Any other reader would be a
    picture handed out unjudged, which is the whole failure this rule answers.
    """
    backend = REPO / "devserver" / "my_app"
    readers = set()
    for path in sorted(backend.rglob("*.py")):
        text = io.open(path, encoding="utf-8").read()
        if "unchecked_entity_path_for_checking" not in text:
            continue
        tree = ast.parse(text)
        functions = [n for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Attribute)
                    and node.attr == "unchecked_entity_path_for_checking"):
                continue
            around = [f for f in functions if f.lineno <= node.lineno <= f.end_lineno]
            inner = min(around, key=lambda f: f.end_lineno - f.lineno, default=None)
            readers.add(f"{path.name}:{inner.name if inner else '<module>'}")
    assert readers <= CONTENT_CHECKS, (
        f"the unchecked door is used somewhere other than a content check: "
        f"{sorted(readers - CONTENT_CHECKS)}"
    )
    assert readers == CONTENT_CHECKS, (
        f"listed as content checks but no longer reading the door: "
        f"{sorted(CONTENT_CHECKS - readers) or 'none'}"
    )


def test_the_two_by_name_routes_ask_the_rule():
    """
    `/api/pipeline/<run>/file/<name>` and `/api/pipeline/<run>/entity/<type>`
    are the picture path of two surfaces (direct, surrealizer). A rule that
    misses them misses the ordinary way a picture is looked at.
    """
    routes = REPO / "devserver" / "my_app" / "routes" / "pipeline_routes.py"
    by_name = _function_source(routes, "get_file_by_name")
    assert "checked_path_for_filename" in by_name and "403" in by_name
    by_type = _function_source(routes, "get_entity")
    assert "checked_entity_path" in by_type and "403" in by_type


def test_a_video_is_handed_out_and_read_only_by_the_rule():
    """
    A video is checked at the result as a whole and goes out by the verdict
    written on it, as a picture does. Reading it hands out what it shows.
    """
    routes = REPO / "devserver" / "my_app" / "routes" / "media_routes.py"
    for name in ("get_video", "_run_analyze_av"):
        source = _function_source(routes, name)
        assert "_entity_refusal" in source and "403" in source, name


def test_a_3d_model_is_handed_out_only_by_the_rule():
    """A 3D model goes out by the verdict on its preview, a picture of its run."""
    source = _function_source(REPO / "devserver" / "my_app" / "routes" / "media_routes.py",
                              "get_3d_mesh")
    assert "_entity_refusal" in source and "403" in source


def test_the_static_export_route_asks_the_rule():
    """
    `/exports/json/<path>` puts the whole run storage on the network as a
    directory. Walking to `<date>/<device>/<run>/final/<file>` reaches the same
    picture without touching a media route at all.
    """
    source = _function_source(
        REPO / "devserver" / "my_app" / "routes" / "static_routes.py", "serve_exports"
    )
    assert "checked_path_for_filename" in source
    assert "403" in source


def test_the_session_preview_asks_the_rule():
    """The table's thumbnail is a smaller copy of the same picture."""
    source = _function_source(
        REPO / "devserver" / "my_app" / "routes" / "settings_routes.py",
        "resolve_preview_media",
    )
    assert "entity_cleared_for_delivery" in source


def test_a_picture_is_cleared_before_it_goes_into_a_composition():
    """
    Post-production takes a run's picture and builds a new file from it, served
    under `output_composition` — an entity type that carries no verdict of its
    own. Without a check at the composing end, the refusal on delivery would be
    exactly one hop wide.
    """
    pp = REPO / "devserver" / "my_app" / "services" / "post_production_service.py"
    source = _function_source(pp, "_resolve_ref")
    assert "checked_entity_path" in source, (
        "_resolve_ref no longer asks whether the source picture was cleared"
    )


def test_the_restore_and_the_strip_ask_the_level_of_the_run():
    """
    A run's Stage-2 text was checked with the question of its own level, so at
    kids and youth only a run of the same level or a stricter one is opened
    again, and the strip lists only what may be opened.
    """
    routes = REPO / "devserver" / "my_app" / "routes" / "favorites_routes.py"
    assert "_restorable" in _function_source(routes, "get_restore_data")
    assert "403" in _function_source(routes, "get_restore_data")
    assert "_listable" in _function_source(routes, "get_favorites")


# --------------------------------------------- pictures made of other pictures


def test_a_composite_is_refused_while_a_picture_in_it_is():
    """
    The strip a run lays out when it produced several pictures contains every
    one of them. Refusing picture 2 and handing out the strip that has picture 2
    in it withholds nothing.
    """
    run = _run("kids")
    run["entities"] = [_image(1, {"safe": True}), _image(2, {"safe": False})]
    strip = {"sequence": 3, "type": "output_image_composite",
             "filename": "12.png", "metadata": {}}
    cleared, reason = entity_cleared_for_delivery(strip, run, "kids")
    assert cleared is False and reason == "blocked"


def test_a_composite_travels_when_every_picture_in_it_did():
    run = _run("kids")
    run["entities"] = [_image(1, {"safe": True}), _image(2, {"safe": True})]
    strip = {"sequence": 3, "type": "output_image_comparison",
             "filename": "12.png", "metadata": {}}
    assert entity_cleared_for_delivery(strip, run, "kids")[0] is True


def test_a_composite_is_refused_while_a_picture_in_it_is_unjudged():
    run = _run("kids")
    run["entities"] = [_image(1, {"safe": True}), _image(2, None)]
    strip = {"sequence": 3, "type": "output_image_composite",
             "filename": "12.png", "metadata": {}}
    cleared, reason = entity_cleared_for_delivery(strip, run, "kids")
    assert cleared is False and reason == "unchecked"


# ------------------------------------------- the verdict's own words stay here


def test_the_reason_and_the_description_do_not_travel():
    """
    A verdict carries the German sentence a model wrote about why the picture is
    withheld, and that model's account of what is IN it. Handing those out is
    publishing in prose what the refusal withheld as bytes.
    """
    entity = _image(1, {"safe": False, "reason": "Gewaltdarstellung",
                        "description": "Ein Mann mit einem Messer", "checked_at": "x"})
    out = public_entity(entity)
    assert out["metadata"]["safety"] == {"safe": False}
    # and the record itself is untouched
    assert entity["metadata"]["safety"]["reason"] == "Gewaltdarstellung"


def test_an_entity_without_a_verdict_travels_unchanged():
    entity = _image(1)
    assert public_entity(entity) is entity


def test_every_place_that_sends_entities_out_cuts_the_verdict_back():
    """
    The listing, the run's own metadata, the favourites restore, the pipeline
    status and the session detail all put a run's entities on the wire.
    """
    places = [
        (REPO / "devserver" / "my_app" / "routes" / "favorites_routes.py", "get_restore_data"),
        (RECORDER, "get_status"),
    ]
    for path, name in places:
        source = _function_source(path, name)
        assert "public_entity" in source or "_public(" in source, (
            f"{path.name}:{name} sends entities out without cutting the verdict back"
        )


# ------------------------------------- a fault is not a rating of what was made


def test_the_check_at_the_result_writes_no_fault_onto_the_picture(tmp_path, monkeypatch):
    """
    Measured over 60 days: 13 operational endings against 2 content ones in 944
    checks. Stamping both as `safe: False` records, on the picture and for good,
    a technical fault as a rating of what somebody made — and no later check can
    lift it, because a stamp outlives the fault that caused it. Every way reads
    its pictures through _pictures_of_run and asks check_result_image about each.
    """
    from my_app.routes import schema_pipeline_routes as spr
    from my_app.services import safety_gate
    from my_app.utils import vlm_safety

    class Recorder:
        run_id = "run_test"

        def __init__(self):
            self.marks = []

        def output_entities(self, kind):
            return [{"sequence": 1, "filename": "01_output_image.png"},
                    {"sequence": 2, "filename": "02_output_image.png"}]

        def unchecked_entity_path_for_checking(self, entity):
            return tmp_path / entity["filename"]

        def mark_entity_safety(self, sequence, safe, **kw):
            self.marks.append((sequence, safe))
            return True

    recorder = Recorder()
    (tmp_path / "02_output_image.png").write_bytes(b"a picture")
    pictures, refusal = spr._pictures_of_run(recorder, "kids", expect_image=True)
    assert [sequence for sequence, _path in pictures] == [2], (
        "the picture that is on disk is checked beside the one that is not")
    assert refusal.operational and refusal.reason == "file_missing"
    assert recorder.marks == [], (
        "a file that could not be read is stamped onto the picture as a verdict")

    monkeypatch.setattr(vlm_safety, "vlm_safety_check",
                        lambda path, level: (False, vlm_safety.VLM_OPERATIONAL_BLOCK_MESSAGE, ""))
    verdict = safety_gate.check_result_image(pictures[0][1], level="kids",
                                             recorder=recorder, entity=2)
    assert verdict.operational
    assert recorder.marks == [], "a check that gave no verdict is stamped onto the picture"


@pytest.mark.parametrize("expect_image", [False, True])
def test_a_3d_run_without_its_preview_is_withheld_as_a_fault(expect_image):
    """
    A 3D model is checked through its preview. Where Blender is missing or its
    render failed there is none, and nothing would clear the model: the run is
    withheld as a fault, rather than shown with a model that delivery then
    refuses.
    """
    from my_app.routes import schema_pipeline_routes as spr

    class Recorder:
        run_id = "run_test"

        def output_entities(self, kind):
            if kind == "3d":
                return [{"sequence": 1, "type": "output_3d", "filename": "01_output_3d.glb"}]
            return []

    pictures, refusal = spr._pictures_of_run(Recorder(), "kids", expect_image=expect_image)
    assert pictures == []
    assert refusal.operational and refusal.reason == "no_preview"
    assert refusal.field == "3d"


# ---------------------------------------------- the rule by level and kind
#
# How a verdict's level answers for whoever asks, and how each kind the check
# at the result reads goes out: pictures and the parts on the way to them,
# compositions, code, 3D models and videos.


def _verdict(level, safe=True):
    return {"safe": safe, "reason": "", "level": level}


def test_a_pass_at_youth_does_not_clear_a_picture_for_a_kids_requester():
    entity = _image(safety=_verdict("youth"))
    cleared, _ = entity_cleared_for_delivery(entity, _run("youth"), "kids")
    assert cleared is False


def test_a_pass_at_kids_clears_a_picture_for_a_youth_requester():
    entity = _image(safety=_verdict("kids"))
    cleared, _ = entity_cleared_for_delivery(entity, _run("kids"), "youth")
    assert cleared is True


def test_a_picture_made_where_nothing_was_checked_is_refused_to_a_kids_requester():
    """A run at research keeps no verdict, so its picture has none to show a kids course."""
    cleared, _ = entity_cleared_for_delivery(_image(), _run("research"), "kids")
    assert cleared is False


def test_the_filter_follows_the_level_of_whoever_asks():
    at_kids = _image(1, _verdict("kids"))
    at_youth = _image(2, _verdict("youth"))
    kept = filter_deliverable([at_kids, at_youth], _run("youth"), "kids")
    assert [e["sequence"] for e in kept] == [1]


def test_a_refusal_at_kids_says_nothing_about_youth():
    entity = _image(safety=_verdict("kids", safe=False))
    assert entity_cleared_for_delivery(entity, _run("kids"), "kids") == (False, "blocked")
    assert entity_cleared_for_delivery(entity, _run("kids"), "youth") == (False, "unchecked")


def test_a_refusal_at_youth_holds_for_kids():
    entity = _image(safety=_verdict("youth", safe=False))
    assert entity_cleared_for_delivery(entity, _run("youth"), "kids") == (False, "blocked")


def _step(fmt="jpg"):
    return {"sequence": 2, "type": "latent_lab_step",
            "filename": f"prompting_process/002_step_01.{fmt}",
            "metadata": {"step_index": 0, "format": fmt}}


def test_a_lab_step_goes_out_with_the_finished_picture():
    """The frames of a denoising run are no verdict's own: they travel with the
    picture they led to, and are held back until it is cleared."""
    run = {"entities": [_step(), _image(3, _verdict("kids"))]}
    assert entity_cleared_for_delivery(_step(), run, "kids") == (True, "")
    run["entities"][1] = _image(3, None)
    assert entity_cleared_for_delivery(_step(), run, "kids") == (False, "unchecked")
    assert entity_cleared_for_delivery(_step(), {"entities": [_step()]}, "kids") == (False, "unchecked")
    assert entity_cleared_for_delivery(_step(), run, "adult") == (True, "")


def test_a_lab_part_is_held_whatever_format_it_names():
    """The format is the sender's word: a part that names another one still
    waits for the finished picture."""
    run = {"entities": [_step("json")]}
    assert entity_cleared_for_delivery(_step("json"), run, "kids") == (False, "unchecked")
    run["entities"].append(_image(3, _verdict("kids")))
    assert entity_cleared_for_delivery(_step("svg"), run, "kids") == (True, "")


class _Recorded:
    def __init__(self, metadata):
        self.metadata = metadata


def _composition(*pieces):
    return {"sequence": 1, "type": "output_composition", "filename": "01.mp4",
            "metadata": {"composed_from": list(pieces)}}


def test_a_composition_is_as_clear_as_its_pieces(monkeypatch):
    from my_app.services import pipeline_recorder

    picture = {"safety_level": "kids", "entities": [_image(1, _verdict("kids"))]}
    sound = {"safety_level": "adult",
             "entities": [{"sequence": 1, "type": "output_audio", "filename": "x", "metadata": {}}]}
    runs = {"run_pic": _Recorded(picture), "run_snd": _Recorded(sound)}
    monkeypatch.setattr(pipeline_recorder, "load_recorder",
                        lambda run_id, base_path=None: runs.get(run_id))
    still_and_sound = _composition({"role": "image", "run_id": "run_pic", "type": "output_image"},
                                   {"role": "audio", "run_id": "run_snd", "type": "output_audio"})
    own = {"safety_level": "kids", "entities": [still_and_sound]}
    assert entity_cleared_for_delivery(still_and_sound, own, "kids") == (True, "")
    picture["entities"][0] = _image(1, _verdict("youth"))
    assert entity_cleared_for_delivery(still_and_sound, own, "kids") == (False, "unchecked")
    assert entity_cleared_for_delivery(still_and_sound, own, "adult") == (True, "")


def test_a_composition_that_names_no_piece_or_a_lost_one_is_refused(monkeypatch):
    from my_app.services import pipeline_recorder

    monkeypatch.setattr(pipeline_recorder, "load_recorder", lambda run_id, base_path=None: None)
    for entity in (_composition(),
                   _composition({"role": "image", "run_id": "run_gone", "type": "output_image"}),
                   _composition({"role": "image", "run_id": "run_x", "type": "output_composition"})):
        assert entity_cleared_for_delivery(entity, _run("kids"), "kids") == (False, "unchecked")


def test_the_upload_route_asks_the_verdict_beside_the_upload():
    source = _function_source(
        REPO / "devserver" / "my_app" / "routes" / "media_routes.py", "get_uploaded_image"
    )
    assert "upload_cleared_for" in source or "image_reference_cleared" in source
    assert "403" in source


@pytest.mark.parametrize("kind", ["p5", "tonejs", "sonicpi"])
def test_code_without_a_verdict_is_refused_to_a_kids_requester(kind):
    entity = {"sequence": 1, "type": f"output_{kind}", "filename": "x", "metadata": {}}
    cleared, _ = entity_cleared_for_delivery(entity, _run("kids"), "kids")
    assert cleared is False


def _sketch(safety=None, kind="p5"):
    """A sketch as the recorders write it today: under its runtime's bare name."""
    entity = {"sequence": 1, "type": kind, "filename": f"01_{kind}.txt", "metadata": {}}
    if safety is not None:
        entity["metadata"]["safety"] = safety
    return entity


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_sketch_without_a_verdict_is_refused_at_kids_and_youth(level):
    assert entity_cleared_for_delivery(_sketch(), _run(level), level) == (False, "unchecked")


@pytest.mark.parametrize("level", ["adult", "research"])
def test_a_sketch_without_a_verdict_goes_out_where_no_pass_is_asked(level):
    """Runs from before the check at the result read code carry none."""
    assert entity_cleared_for_delivery(_sketch(), _run(level), level) == (True, "")


def test_a_pass_on_a_sketch_answers_for_its_level_and_the_looser_ones():
    sketch = _sketch(_verdict("youth"))
    assert entity_cleared_for_delivery(sketch, _run("youth"), "youth") == (True, "")
    assert entity_cleared_for_delivery(sketch, _run("youth"), "kids") == (False, "unchecked")


@pytest.mark.parametrize("asker, answer", [
    ("kids", (False, "blocked")),
    ("youth", (False, "blocked")),
    ("adult", (False, "blocked")),
    ("research", (True, "")),
])
def test_a_sketch_refused_at_adult_stays_refused_there_and_below(asker, answer):
    """Code is checked at adult, where no picture is: the refusal stands there."""
    sketch = _sketch(_verdict("adult", safe=False), kind="tonejs")
    assert entity_cleared_for_delivery(sketch, _run("adult"), asker) == answer


def test_a_sketch_refused_at_kids_says_nothing_about_adult():
    sketch = _sketch(_verdict("kids", safe=False))
    assert entity_cleared_for_delivery(sketch, _run("kids"), "kids") == (False, "blocked")
    assert entity_cleared_for_delivery(sketch, _run("kids"), "adult") == (True, "")


def test_a_picture_still_goes_out_at_adult_whatever_stands_on_it():
    """The refusal that stands at adult is code's alone: adult checks no picture."""
    picture = _image(safety=_verdict("adult", safe=False))
    assert entity_cleared_for_delivery(picture, _run("adult"), "adult") == (True, "")


def _model(kind="output_3d"):
    return {"sequence": 2, "type": kind, "filename": "02_output_3d.glb", "metadata": {}}


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_3d_model_goes_out_as_clear_as_its_preview(level):
    """A 3D model is checked through its preview, the picture its run renders
    of it, and goes out by that picture's verdict."""
    run = {"safety_level": level, "entities": [_image(1, _verdict(level)), _model()]}
    assert entity_cleared_for_delivery(_model(), run, level) == (True, "")
    run["entities"][0] = _image(1, None)
    assert entity_cleared_for_delivery(_model(), run, level) == (False, "unchecked")
    run["entities"][0] = _image(1, _verdict(level, safe=False))
    assert entity_cleared_for_delivery(_model(), run, level) == (False, "blocked")


@pytest.mark.parametrize("level", ["kids", "youth"])
@pytest.mark.parametrize("kind", ["output_3d", "3d"])
def test_a_3d_model_without_a_preview_is_refused_at_kids_and_youth(level, kind):
    """Nothing would clear it, and a run without pictures is no agreement."""
    run = {"safety_level": level, "entities": [_model(kind)]}
    assert entity_cleared_for_delivery(_model(kind), run, level) == (False, "unchecked")


@pytest.mark.parametrize("level", ["adult", "research"])
def test_a_3d_model_goes_out_where_no_pass_is_asked(level):
    run = {"safety_level": "kids", "entities": [_model()]}
    assert entity_cleared_for_delivery(_model(), run, level) == (True, "")


def test_a_refused_3d_model_takes_the_pictures_message():
    """What was refused is its preview, a picture."""
    from my_app.services.pipeline_recorder import refused_field
    assert refused_field(_model()) == "image"


def _video(safety=None, kind="output_video"):
    entity = {"sequence": 1, "type": kind, "filename": "01_output_video.mp4", "metadata": {}}
    if safety is not None:
        entity["metadata"]["safety"] = safety
    return entity


@pytest.mark.parametrize("level", ["kids", "youth"])
@pytest.mark.parametrize("kind", ["output_video", "video"])
def test_a_video_without_a_verdict_is_refused_at_kids_and_youth(level, kind):
    """Runs from before the check at the result looked at a video carry none."""
    assert entity_cleared_for_delivery(_video(kind=kind), _run(level), level) == \
        (False, "unchecked")


@pytest.mark.parametrize("level", ["adult", "research"])
def test_a_video_goes_out_where_no_pass_is_asked(level):
    assert entity_cleared_for_delivery(_video(), _run(level), level) == (True, "")
    refused = _video(_verdict("kids", safe=False))
    assert entity_cleared_for_delivery(refused, _run("kids"), level) == (True, "")


def test_a_video_goes_by_its_verdict_as_a_picture_does():
    assert entity_cleared_for_delivery(_video(_verdict("kids")), _run("kids"), "youth") == \
        (True, "")
    assert entity_cleared_for_delivery(_video(_verdict("youth")), _run("youth"), "kids") == \
        (False, "unchecked")
    assert entity_cleared_for_delivery(_video(_verdict("youth", safe=False)), _run("youth"),
                                       "kids") == (False, "blocked")
    assert entity_cleared_for_delivery(_video(_verdict("kids", safe=False)), _run("kids"),
                                       "youth") == (False, "unchecked")


def test_a_refused_video_is_called_a_video():
    from my_app.services.pipeline_recorder import refused_field
    assert refused_field(_video()) == "video"
    assert refused_field(_video(kind="video")) == "video"
    assert refused_field(_image()) == "image"
    assert refused_field(_sketch()) == "code"


def test_a_film_under_a_sound_is_as_clear_as_the_film(monkeypatch):
    from my_app.services import pipeline_recorder

    film = {"safety_level": "kids", "entities": [_video()]}
    monkeypatch.setattr(pipeline_recorder, "load_recorder",
                        lambda run_id, base_path=None: _Recorded(film) if run_id == "run_film" else None)
    piece = _composition({"role": "video", "run_id": "run_film", "type": "output_video"})
    own = {"safety_level": "kids", "entities": [piece]}
    assert entity_cleared_for_delivery(piece, own, "kids") == (False, "unchecked")
    film["entities"][0] = _video(_verdict("kids"))
    assert entity_cleared_for_delivery(piece, own, "kids") == (True, "")
