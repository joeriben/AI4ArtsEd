#!/usr/bin/env python3
"""The two words that ask for the answer as a stream.

Written on 2026-09-05. `enable_streaming` is the older word;
`enable_answer_streaming` is the newer, more specific one, and it exists
because on this platform the older word already names TWO protocols depending
on which route reads it (see /pipeline/interception below). Until this file was
written the shared transport read the OLDER word by default, so a caller that
sent only the newer one -- the one a reader of services/directRun.ts would copy
-- was handed the plain, unprotected body by fourteen of the fifteen sites
that read the flag. Verified against the live backend before the change:
`{"prompt": "", "enable_answer_streaming": true}` to /api/commons/lookup came
back as a plain JSON 400; with both words it came back as the stream.

Nothing was broken by that on the day: `postStreamedRun` writes both words into
every body it sends. What stood there was a protection that depended on picking
the right synonym, on a server whose whole exposure is that an answer the edge
cuts at about a hundred seconds is thrown away.

So EITHER word opens it, and this file holds three claims:

  * Either word opens the stream, everywhere the transport is read with its
    default.
  * /pipeline/interception is unchanged, in all four combinations of the two
    words. There the older word names the Stage-1-and-2 EVENT protocol, served
    over GET to an EventSource; a POST that asks with it alone is refused by
    name rather than served a different pipeline, and that refusal has to
    survive this change.
  * The fifteen sites are counted, and what each expects is written down. A site
    that narrows to the older word alone would take the platform back to the
    trap this file exists to close, so the census below names the one route
    that is allowed to narrow at all.

Nothing here reaches a model, a GPU or ComfyUI.

Run:  python3 -m pytest devserver/tests/test_stream_flag_words.py -q
"""
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import commons_routes, schema_pipeline_routes
from my_app.services import commons_service
from my_app.services.streaming_response import (ANSWER_STREAM_FLAG,
                                                STREAM_FLAG, TRANSPORT_FLAGS,
                                                answered_either_way,
                                                asks_for_the_stream, said_yes)

OLD, NEW = STREAM_FLAG, ANSWER_STREAM_FLAG

ROUTES = Path(__file__).resolve().parents[1] / "my_app" / "routes"


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(commons_routes.commons_bp)
    app.register_blueprint(schema_pipeline_routes.schema_bp)
    return app


def is_a_stream(response) -> bool:
    return response.mimetype == "text/event-stream"


def terminal_frame(response):
    """The `(payload, http_status)` a plain POST would have returned, out of
    the stream's own last frame."""
    body = response.get_data(as_text=True)
    for raw in body.split("\n\n"):
        if raw.startswith("event: complete"):
            frame = json.loads(raw.split("data: ", 1)[1])
            return frame["body"], frame["http_status"]
    raise AssertionError(f"no terminal frame on this wire: {body[:400]!r}")


# ---------------------------------------------------------------------------
# 1. the predicate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    pytest.param({OLD: True}, id="the older word"),
    pytest.param({NEW: True}, id="the newer word"),
    pytest.param({OLD: True, NEW: True}, id="both"),
])
def test_either_word_asks_for_the_stream(body):
    assert asks_for_the_stream(body) is True


@pytest.mark.parametrize("body", [
    pytest.param({}, id="neither word"),
    pytest.param({OLD: False, NEW: False}, id="both said no"),
    pytest.param({"enable_streamings": True}, id="a word that is neither"),
    pytest.param([OLD], id="a body that is no object"),
    pytest.param(None, id="no body at all"),
])
def test_anything_else_asks_for_nothing(body):
    assert asks_for_the_stream(body) is False


def test_a_narrowed_flag_takes_that_word_and_no_other():
    """What /pipeline/interception depends on: there the older word means a
    different protocol, and must not open this one."""
    assert asks_for_the_stream({NEW: True}, ANSWER_STREAM_FLAG) is True
    assert asks_for_the_stream({OLD: True}, ANSWER_STREAM_FLAG) is False
    assert asks_for_the_stream({OLD: True, NEW: True}, ANSWER_STREAM_FLAG) is True


def a_short_answer():
    return {"said": "so"}, 200


@pytest.mark.parametrize("word", [OLD, NEW])
def test_the_gate_streams_for_either_word(app, word):
    with app.test_request_context("/", json={word: True}):
        response = answered_either_way({word: True}, a_short_answer,
                                       label="STAND-IN")
    assert is_a_stream(response)
    assert terminal_frame(response) == ({"said": "so"}, 200)


def test_the_gate_narrowed_to_the_newer_word_ignores_the_older_one(app):
    with app.test_request_context("/", json={OLD: True}):
        answer = answered_either_way({OLD: True}, a_short_answer,
                                     label="STAND-IN",
                                     flag=ANSWER_STREAM_FLAG)
    # The plain way back is the `(body, status)` pair Flask takes, not a
    # Response -- which is itself the assertion: no stream was opened.
    payload, http_status = answer
    assert payload.mimetype == "application/json"
    assert (payload.get_json(), http_status) == ({"said": "so"}, 200)


# ---------------------------------------------------------------------------
# 2. a route that reads the transport with its default
# ---------------------------------------------------------------------------
#
# /api/commons/lookup, and the empty prompt it refuses before anything is
# looked up: no model is reached, and the shape of the answer is the whole
# question here.

PROMPT_REQUIRED = ({"success": False, "error": "prompt required"}, 400)


@pytest.mark.parametrize("word", [OLD, NEW])
def test_the_lookup_answers_on_the_stream_for_either_word(app, word):
    response = app.test_client().post("/api/commons/lookup",
                                      json={"prompt": "", word: True})
    assert is_a_stream(response)
    payload, http_status = terminal_frame(response)
    assert (payload, http_status) == PROMPT_REQUIRED


def test_the_lookup_still_answers_one_json_body_where_no_stream_was_asked_for(app):
    response = app.test_client().post("/api/commons/lookup", json={"prompt": ""})
    assert response.mimetype == "application/json"
    assert (response.get_json(), response.status_code) == PROMPT_REQUIRED


# ---------------------------------------------------------------------------
# 3. /pipeline/interception, in all four combinations
# ---------------------------------------------------------------------------
#
# The reason the narrowing parameter exists. Recorded against the live backend
# at 127.0.0.1:17802 before this change and reproduced here, so that the four
# answers are held as a set rather than one at a time.

INTERCEPTION = "/api/schema/pipeline/interception"
MISSING_FIELDS = {"status": "error",
                  "error": 'Parameter "schema" and "input_text" erforderlich'}


@pytest.fixture()
def interception(app, monkeypatch):
    monkeypatch.setattr(schema_pipeline_routes, "resolve_safety_level",
                        lambda: "kids")
    return app.test_client()


def test_the_interception_answers_one_json_body_when_neither_word_is_sent(
        interception):
    response = interception.post(INTERCEPTION, json={"schema": "x",
                                                     "input_text": ""})
    assert response.mimetype == "application/json"
    assert (response.get_json(), response.status_code) == (MISSING_FIELDS, 400)


def test_the_interception_still_refuses_the_older_word_alone(interception):
    """The claim this change had to leave standing. Over POST the older word
    names a protocol that is served over GET and writes no terminal frame, so a
    caller sending it alone is told by name instead of being handed a stream it
    cannot read."""
    response = interception.post(INTERCEPTION,
                                 json={"schema": "x", "input_text": "",
                                       OLD: True})
    assert response.mimetype == "application/json"
    assert response.status_code == 400
    assert response.get_json()["cause"] == "ambiguous_streaming_flag"


def test_the_interception_streams_for_the_newer_word(interception):
    response = interception.post(INTERCEPTION,
                                 json={"schema": "x", "input_text": "",
                                       NEW: True})
    assert is_a_stream(response)
    assert terminal_frame(response) == (MISSING_FIELDS, 400)


def test_the_interception_streams_when_both_words_are_sent(interception):
    """What `postStreamedRun` actually sends: both words, which says which
    transport is meant and falls through to the answer stream."""
    response = interception.post(INTERCEPTION,
                                 json={"schema": "x", "input_text": "",
                                       OLD: True, NEW: True})
    assert is_a_stream(response)
    assert terminal_frame(response) == (MISSING_FIELDS, 400)


# ---------------------------------------------------------------------------
# 4. the census of the sites
# ---------------------------------------------------------------------------

# The one route allowed to narrow, and the word it narrows to. Everything else
# has to read the transport with its default, which takes either word.
MAY_NARROW = {("schema_pipeline_routes.py", "interception_pipeline"):
              ANSWER_STREAM_FLAG}


SCANNED = [ROUTES, ROUTES.parent / "services"]


def flag_reading_sites():
    """Every call in my_app/routes that asks whether the stream was requested,
    as (file, enclosing function, the `flag=` it passes or None)."""
    sites = []
    for path in sorted(ROUTES.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                name = getattr(call.func, "id", None) or \
                    getattr(call.func, "attr", None)
                if name not in ("answered_either_way", "asks_for_the_stream"):
                    continue
                narrowed = None
                for kw in call.keywords:
                    if kw.arg == "flag":
                        narrowed = ast.unparse(kw.value)
                # `asks_for_the_stream` also takes the flag positionally.
                if (name == "asks_for_the_stream" and len(call.args) > 1
                        and narrowed is None):
                    narrowed = ast.unparse(call.args[1])
                sites.append((path.name, node.name, name, narrowed))
    return sites


def every_reading_of_the_words():
    """Every place either WORD is read, however it is spelled.

    The census above walks two FUNCTION NAMES, and a scan of names cannot see a
    route that reads the word straight out of its body -- six of them do,
    including the three gates that decide between this platform's three
    streaming protocols. A route spelled `data.get('enable_streaming')` was
    invisible to it, which is the one shape the docstring of this file promises
    to notice.

    Both spellings a site can be written in: the WORDS themselves, and the
    constant names they are held under -- `data.get(STREAM_FLAG)` names no word
    a search for "enable_streaming" would find.

    Returned as (file, line, the source of the reading), from the routes AND
    the services: the transport itself lives in the latter, and so does the
    strict reading both now go through.
    """
    spellings = (OLD, NEW, "STREAM_FLAG", "TRANSPORT_FLAGS")
    seen = []
    for folder in SCANNED:
        for path in sorted(folder.glob("*.py")):
            source = path.read_text()
            for i, line in enumerate(source.splitlines(), start=1):
                bare = line.split("#", 1)[0]
                if any(word in bare for word in spellings):
                    seen.append((path.name, i, line.strip()))
    return seen


def test_every_site_but_one_takes_either_word():
    """The trap this change closed, kept closed.

    A site that narrows to the older word alone would hand the plain,
    unprotected body back to a caller that wrote the newer one -- which is
    exactly the state this file was written out of.
    """
    sites = flag_reading_sites()
    assert sites, "no site reads the streaming flag any more"

    narrowed = {(f, fn): flag for f, fn, _call, flag in sites if flag}
    assert set(narrowed) == set(MAY_NARROW), narrowed
    for where, flag in narrowed.items():
        assert flag == "ANSWER_STREAM_FLAG", (where, flag)


def test_the_sites_that_read_the_flag_are_counted():
    """Counted so that a new one is noticed rather than inherited.

    Seventeen `answered_either_way` sites carry a whole route's answer, and two
    further gates read the predicate on its own: /pipeline/safety/quick, whose
    blocking branch keeps a `try` of its own so both ways back refuse alike,
    and /pipeline/direct-workflow, which reads it to log before handing over.
    Eighteen of the nineteen take either word; the nineteenth is the
    interception route, and `test_every_site_but_one_takes_either_word` above is
    what says so by name.

    The three of /api/text (rep-engineering, bias-probe, bbq-probe) came on
    2026-09-09; the two of the Fusion Workbench (generate, _research_run)
    followed on 2026-09-14, when the workbench moved onto ComfyUI: its surfaces
    answer streamed and the flag decides whether the heartbeat travels.
    """
    sites = flag_reading_sites()
    gates = [s for s in sites if s[2] == "answered_either_way"]
    predicates = [s for s in sites if s[2] == "asks_for_the_stream"]
    assert len(gates) == 17, gates
    assert len(predicates) == 2, predicates
    assert len([s for s in sites if s[3] is None]) == 18, sites


def test_every_reading_of_the_words_goes_through_one_truth_test():
    """The half a scan of function names cannot reach.

    A route that reads a word out of its own body decides between protocols on
    its own, and there were six such readings when this was written -- three of
    them the gates of /pipeline/interception, /pipeline/optimize and
    /pipeline/generation. Each must read the word through `said_yes`, or
    through the query-string comparison the GET arms use, and never through
    Python's own idea of truth: `bool("false")` is True.
    """
    loose = []
    for name, line_no, source in every_reading_of_the_words():
        if "streaming_response" in name:
            continue                     # where `said_yes` itself is written
        if "said_yes(" in source or "request.args.get" in source:
            continue
        if not re.search(r"\.get\(|\[", source):
            continue                     # a mention, not a reading
        loose.append(f"{name}:{line_no}: {source}")
    assert not loose, (
        "read these through said_yes() in services/streaming_response.py:\n"
        + "\n".join(loose))


def test_the_scan_sees_a_word_spelled_out_by_hand(tmp_path):
    """Held against the shape it was blind to. A scan that cannot fail on the
    line it was written for pins nothing."""
    a_new_route = tmp_path / "invented_routes.py"
    a_new_route.write_text(
        "def run(data):\n"
        f"    if data.get('{OLD}'):\n"
        "        return 'a stream'\n", encoding="utf-8")
    found = [line for _n, _i, line in _readings_in(a_new_route)]
    assert found and OLD in found[0]


def _readings_in(path):
    return [(path.name, i, line.strip())
            for i, line in enumerate(path.read_text().splitlines(), start=1)
            if OLD in line.split("#", 1)[0] or NEW in line.split("#", 1)[0]]


# ---------------------------------------------------------------------------
# 5. what counts as YES
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [True, 1, "true", "TRUE", " True "])
def test_these_spellings_say_yes(value):
    assert said_yes(value) is True
    assert asks_for_the_stream({NEW: value}) is True


@pytest.mark.parametrize("value", [
    pytest.param("false", id="the word no, as a string"),
    pytest.param("False", id="the same word capitalised"),
    pytest.param("anything", id="a string that is neither"),
    pytest.param("", id="an empty string"),
    pytest.param(0, id="zero"),
    pytest.param(2, id="a number that is not one"),
    pytest.param([0], id="a list"),
    pytest.param({"a": 1}, id="an object"),
    pytest.param(None, id="null"),
    pytest.param(False, id="the JSON false"),
])
def test_everything_else_says_no(value):
    """`bool(value)` was the test until 2026-09-05, and `bool("false")` is
    True: a caller writing `"enable_answer_streaming": "false"` -- the shape a
    hand-written curl and a query string copied into a JSON body both produce
    -- opened the very transport it had just declined. A flag nobody can spell
    NO in is not a flag."""
    assert said_yes(value) is False
    assert asks_for_the_stream({NEW: value}) is False
    assert asks_for_the_stream({OLD: value}) is False


def test_the_older_test_would_have_said_yes_to_all_of_them():
    """Why the parametrisation above is not a list of things nobody sends."""
    said_yes_before = [v for v in ("false", "anything", 2, [0], {"a": 1})
                       if bool(v)]
    assert len(said_yes_before) == 5


# ---------------------------------------------------------------------------
# 6. the third protocol -- /pipeline/generation
# ---------------------------------------------------------------------------

GENERATION = "/api/schema/pipeline/generation"


def test_the_generation_route_refuses_the_answer_word_by_name(app):
    """The third protocol these words name on this platform.

    "enable_streaming" HERE opens the generation event stream, whose terminal
    `complete` carries the media output and no http_status and no body -- so a
    caller speaking the shared answer transport reads that frame as a silent
    empty success and shows nothing, with the picture made and stored.
    `postStreamedRun` in services/directRun.ts sends BOTH words, so the word
    for a transport this route does not serve is refused by name.
    """
    response = app.test_client().post(
        GENERATION, json={"prompt": "x", "output_config": "y", NEW: True})
    assert response.mimetype == "application/json"
    assert response.status_code == 400
    assert response.get_json()["cause"] == "ambiguous_streaming_flag"


def test_the_generation_route_refuses_both_words_too(app):
    """What `postStreamedRun` actually sends. Unlike the interception route,
    this one does not serve the answer transport at all, so naming it is a
    refusal either way rather than a choice between two."""
    response = app.test_client().post(
        GENERATION, json={"prompt": "x", "output_config": "y",
                          OLD: True, NEW: True})
    assert response.status_code == 400
    assert response.get_json()["cause"] == "ambiguous_streaming_flag"


def test_the_generation_route_still_streams_for_the_older_word_alone(
        app, monkeypatch):
    """The word this route DOES serve, unchanged. The generator is stood in
    for: this file settles which protocol a body asks for, and there is one
    GPU on this machine."""
    def stand_in(data):
        yield "event: connected\ndata: {}\n\n"

    monkeypatch.setattr(schema_pipeline_routes,
                        "execute_generation_streaming", stand_in)
    response = app.test_client().post(
        GENERATION, json={"prompt": "x", "output_config": "y", OLD: True})
    assert is_a_stream(response)
    assert "connected" in response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# 7. a body that is no JSON object
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    pytest.param([1, 2], id="an array"),
    pytest.param("hallo", id="a string"),
    pytest.param(42, id="a number"),
])
def test_the_interception_refuses_a_body_that_is_no_object(interception, body):
    """It answered a bare Flask 500 HTML page: `data.get(...)` on a list hits
    an AttributeError, which leaves the route entirely. A fault of this server,
    named where a caller's mistake stands -- on the route this platform's main
    surface runs through. `object_body` exists for exactly this."""
    response = interception.post(INTERCEPTION, json=body)
    assert response.mimetype == "application/json", \
        response.get_data(as_text=True)[:200]
    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]
    assert response.get_json()["status"] == "error"


def test_the_interception_still_takes_an_ordinary_object(interception):
    """The other half: nothing about a body that IS an object moved."""
    response = interception.post(INTERCEPTION, json={"schema": "x",
                                                     "input_text": ""})
    assert (response.get_json(), response.status_code) == (MISSING_FIELDS, 400)


def test_the_two_words_are_the_two_the_client_sends():
    """One handshake, one place: services/directRun.ts writes exactly these,
    and `without_transport_flags` strips exactly these before a body is
    forwarded to a station."""
    assert TRANSPORT_FLAGS == (STREAM_FLAG, ANSWER_STREAM_FLAG)
    directrun = (Path(__file__).resolve().parents[2] / "public"
                 / "ai4artsed-frontend" / "src" / "services" / "directRun.ts")
    if directrun.exists():
        source = directrun.read_text()
        assert STREAM_FLAG in source and ANSWER_STREAM_FLAG in source
