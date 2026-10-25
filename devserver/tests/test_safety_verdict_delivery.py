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
    SAFETY_VERDICTS_FLAG,
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


def _run(level="kids", verdicts=True):
    meta = {"safety_level": level}
    if verdicts:
        meta[SAFETY_VERDICTS_FLAG] = True
    return meta


# ---------------------------------------------------------------- the rule


def test_unmarked_picture_is_refused_where_verdicts_are_kept():
    """The heart of it: no verdict, no delivery. This is the fail-open that was."""
    cleared, reason = entity_cleared_for_delivery(_image(), _run("kids"))
    assert cleared is False
    assert reason == "unchecked"


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_picture_marked_unsafe_is_refused(level):
    entity = _image(safety={"safe": False, "reason": "S1"})
    cleared, reason = entity_cleared_for_delivery(entity, _run(level))
    assert cleared is False
    assert reason == "blocked"


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_picture_marked_safe_is_delivered(level):
    entity = _image(safety={"safe": True, "reason": ""})
    cleared, reason = entity_cleared_for_delivery(entity, _run(level))
    assert cleared is True
    assert reason == ""


def test_a_truthy_non_true_verdict_does_not_clear():
    """`safe` must BE True. A string, a 1, a dict — none of those is a verdict."""
    for value in ("yes", 1, {}, [], "False"):
        entity = _image(safety={"safe": value})
        cleared, _ = entity_cleared_for_delivery(entity, _run("kids"))
        assert cleared is False, f"{value!r} cleared a picture"


def test_a_verdict_that_is_not_a_mapping_does_not_clear():
    for value in ("safe", True, 1, ["safe"]):
        entity = _image()
        entity["metadata"]["safety"] = value
        cleared, reason = entity_cleared_for_delivery(entity, _run("kids"))
        assert cleared is False
        assert reason == "unchecked"


# ------------------------------------------------- where the rule stays silent


@pytest.mark.parametrize("level", ["open", "research", "", None])
def test_levels_without_an_image_check_are_untouched(level):
    """No check runs at these levels, so refusing here would hide sound work."""
    cleared, _ = entity_cleared_for_delivery(_image(), _run(level))
    assert cleared is True


@pytest.mark.parametrize("kind", ["audio", "video", "3d", "midi", "music"])
def test_kinds_without_a_check_are_untouched(kind):
    """
    This platform checks pictures and nothing else. Refusing sound at kids level
    over a check that does not exist would take away work and protect no one.
    The gap is real and named in the plan; it is a different gap.
    """
    entity = {"sequence": 1, "type": f"output_{kind}", "filename": "x", "metadata": {}}
    cleared, _ = entity_cleared_for_delivery(entity, _run("kids"))
    assert cleared is True


def test_runs_recorded_before_verdicts_are_untouched():
    """
    A run whose record predates per-picture verdicts carries no flag. Nothing in
    it can say what was checked, so the rule stays silent rather than guessing.
    """
    cleared, _ = entity_cleared_for_delivery(_image(), _run("kids", verdicts=False))
    assert cleared is True


def test_non_output_entities_pass():
    for etype in ("input", "translation", "interception", "safety", "error"):
        entity = {"sequence": 1, "type": etype, "filename": "x", "metadata": {}}
        assert entity_cleared_for_delivery(entity, _run("kids"))[0] is True


def test_filter_keeps_order_and_drops_only_the_refused():
    safe_a = _image(1, {"safe": True})
    blocked = _image(2, {"safe": False, "reason": "S1"})
    safe_b = _image(3, {"safe": True})
    kept = filter_deliverable([safe_a, blocked, safe_b], _run("kids"))
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
    ("media_routes.py", "get_3d_mesh"): "3D, which has no output check anywhere",
    ("media_routes.py", "get_audio"): "sound, likewise",
    ("media_routes.py", "get_music"): "sound, likewise",
    ("media_routes.py", "get_video"): "video, likewise — the named gap",
    ("media_routes.py", "get_midi"): "notation",
    ("media_routes.py", "get_sonicpi"): "code, checked on its own path",
    ("media_routes.py", "get_p5"): "code, checked on its own path",
    ("media_routes.py", "get_tonejs"): "code, checked on its own path",
    ("media_routes.py", "_run_analyze_av"): "sound and video analysis",
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


def test_only_the_content_check_reads_past_the_verdict():
    """
    One door leads to a picture without asking its verdict, and it exists so the
    check can read what it is about to judge. A second caller would be a picture
    handed out unjudged, which is the whole failure this rule answers.
    """
    backend = REPO / "devserver" / "my_app"
    callers = []
    for path in sorted(backend.rglob("*.py")):
        text = io.open(path, encoding="utf-8").read()
        for i, line in enumerate(text.splitlines(), start=1):
            if "unchecked_entity_path_for_checking" not in line:
                continue
            if line.strip().startswith("def "):
                continue
            callers.append(f"{path.name}:{i}")
    assert len(callers) == 1, (
        "the door that reads past the verdict must have exactly one caller, the "
        f"content check itself — found: {callers or 'none, so the check no longer reads its own pictures'}"
    )
    assert callers[0].startswith("schema_pipeline_routes.py:"), (
        f"the unchecked door is used somewhere other than the content check: {callers}"
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


def test_the_flag_is_set_when_the_run_is_made_not_when_a_verdict_lands():
    """
    Where the flag is raised by a successful verdict, a run whose marking fails
    for every picture carries no flag, drops into the branch for records made
    before verdicts existed, and hands its pictures out.
    """
    marking = _function_source(RECORDER, "mark_entity_safety")
    assert "SAFETY_VERDICTS_FLAG" not in marking, (
        "the flag is raised as a side effect of marking again"
    )
    text = io.open(RECORDER, encoding="utf-8").read()
    tree = ast.parse(text)
    recorder_class = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == "LivePipelineRecorder"
    )
    setup = next(
        ast.get_source_segment(text, n) or ""
        for n in recorder_class.body
        if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    assert "SAFETY_VERDICTS_FLAG" in setup, (
        "the run no longer declares itself judged at the moment it is created"
    )


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
    cleared, reason = entity_cleared_for_delivery(strip, run)
    assert cleared is False and reason == "blocked"


def test_a_composite_travels_when_every_picture_in_it_did():
    run = _run("kids")
    run["entities"] = [_image(1, {"safe": True}), _image(2, {"safe": True})]
    strip = {"sequence": 3, "type": "output_image_comparison",
             "filename": "12.png", "metadata": {}}
    assert entity_cleared_for_delivery(strip, run)[0] is True


def test_a_composite_is_refused_while_a_picture_in_it_is_unjudged():
    run = _run("kids")
    run["entities"] = [_image(1, {"safe": True}), _image(2, None)]
    strip = {"sequence": 3, "type": "output_image_composite",
             "filename": "12.png", "metadata": {}}
    cleared, reason = entity_cleared_for_delivery(strip, run)
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


def test_an_operational_ending_writes_no_verdict_onto_the_picture():
    """
    Measured over 60 days: 13 operational endings against 2 content ones in 944
    checks. Stamping both as `safe: False` records, on the picture and for good,
    a technical fault as a rating of what somebody made — and no later check can
    lift it, because a stamp outlives the fault that caused it.
    """
    source = _function_source(
        REPO / "devserver" / "my_app" / "routes" / "schema_pipeline_routes.py",
        "_vlm_safety_check_image",
    )
    assert "VLM_OPERATIONAL_BLOCK_MESSAGE" in source, (
        "the check no longer tells a judgement from a fault before marking"
    )
    marking = source[source.index("mark_entity_safety"):]
    assert "file_missing" not in marking, (
        "a file that could not be read is stamped onto the picture as a verdict"
    )
