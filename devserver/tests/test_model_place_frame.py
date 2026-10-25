#!/usr/bin/env python3
"""The model at work, written on the connection the run already holds
(`note_dispatch` and `heartbeat_comment` in my_app/services/streaming_response.py).

The Latent Lab has a model display; per device it shows which model is
running, for every model that can be driven there.

Before this, the same statement was made by an apparatus: a register
in the GPU service, four routes for it, an announcement module in the DevServer
with four hook points, a query route, and a bar in the Latent Lab asking once a
second. It was removed (75d35eaa, 5d7d6688). What stands instead is the way this
platform already answers a long run: the DevServer knows what it sends, it sends
it on behalf of the device waiting for the answer, and the two-second heartbeat
of that very request carries the name back.

Five things have to hold, and every one of them broke a shape that came before:

  1. The name reaches the wire AT ALL, in a frame a client can read. The
     heartbeat is an SSE COMMENT, which a browser never delivers to a listener,
     so a name written into it as a comment would be invisible.
  2. The worker's dispatch is visible from the REQUEST THREAD. The work runs
     under `contextvars.copy_context()`; a value it sets in a contextvar of its
     own can never be read out here, which is why the holder is a mutable object
     installed before the copy.
  3. The name is said AGAIN on every beat. Said only on the change, it could not
     be recovered: one wrong clear on the page emptied the bar for the rest of a
     run, and a page has several honest reasons to clear.
  4. A holder belongs to ONE stream and is put back when that stream ends. The
     frames are pumped on a pooled worker thread — waitress keeps sixty-four —
     and a contextvar that is only ever set stays on that thread for the life of
     the process. Reproduced on 2026-09-09: a later request wrote its model into
     the holder of a stream that had ended, and the next stream on that thread
     opened by naming it.
  5. Both shapes of streamed route are covered: the ones that hand their frames
     to `sse_response`, and the five that build a Response of their own.

Nothing here reaches a model or a GPU. Run:
  python3 -m pytest devserver/tests/test_model_place_frame.py -q
"""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, Response, jsonify, stream_with_context

from my_app.services import streaming_response as SR


def app_with(route, path="/run"):
    """A Flask app serving one streamed route, driven through a test client."""
    app = Flask(__name__)
    app.add_url_rule(path, path.strip("/"), route, methods=["POST"])
    return app


def frames_of(app, path="/run", body=None):
    """Every frame the route wrote, as text."""
    client = app.test_client()
    response = client.post(path, json=body or {"enable_streaming": True})
    assert response.mimetype == "text/event-stream", response.mimetype
    return response.get_data(as_text=True)


def places_in(text):
    """The `model_place` payloads, in the order they were written."""
    out = []
    for block in text.split("\n\n"):
        if not block.startswith("event: model_place"):
            continue
        line = [ln for ln in block.split("\n") if ln.startswith("data: ")][0]
        out.append(json.loads(line[len("data: "):]))
    return out


def said_in(text):
    """The models named, with repeats of the same name collapsed."""
    names = []
    for p in places_in(text):
        if not names or names[-1] != p["model"]:
            names.append(p["model"])
    return names


def held_open(work):
    """A route whose work stops until the beat has written what it dispatched.

    Returns `(route, released)`. The beat is the platform's own writer; the only
    thing added is a word when a `model_place` frame has gone out, so a test can
    let the work carry on without racing the two-second cadence.
    """
    wrote = threading.Event()

    def route():
        def heartbeat(elapsed, nth):
            out = SR.heartbeat_comment(elapsed, nth)
            if "event: model_place" in out:
                wrote.set()
            return out

        return SR.sse_response(
            SR.streamed_answer(work, label="TEST", heartbeat=heartbeat,
                               interval=0.02))

    return route, wrote


class TestTheNameReachesTheWire:
    """A client can READ it. The beat itself is a comment and cannot be read."""

    def test_a_dispatch_from_the_worker_arrives_as_a_frame(self):
        wrote = threading.Event()

        def work():
            SR.note_dispatch("stabilityai/stable-diffusion-3.5-large", local=True)
            wrote.wait(5.0)
            return {"ok": True}, 200

        route, wrote = held_open(work)
        said = places_in(frames_of(app_with(route)))
        assert said, "the name never reached the wire"
        assert said[0] == {"model": "stabilityai/stable-diffusion-3.5-large",
                           "local": True}, said

    def test_the_beat_is_a_comment_while_no_model_is_at_work(self):
        """Nothing is added to the wire that was not going out already, and a
        run that reaches no model says nothing about one."""
        def work():
            return {"ok": True}, 200

        def route():
            return SR.sse_response(
                SR.streamed_answer(work, label="TEST", interval=0.02))

        text = frames_of(app_with(route))
        assert places_in(text) == []
        assert ": heartbeat" in text

    def test_a_failed_dispatch_takes_the_name_back(self):
        """A call that came back empty leaves nothing standing.

        The page keeps what it was last told, so a run that is at NO model has
        to SAY so: `model` null is that sentence, and it is sent only where a
        name was sent before it.
        """
        wrote = threading.Event()

        def work():
            SR.note_dispatch("mammouth/kimi-k3", local=False)
            wrote.wait(5.0)
            SR.note_dispatch(None, local=False)
            time.sleep(0.15)        # several beats at the interval below
            return {"ok": True}, 200

        route, wrote = held_open(work)
        said = places_in(frames_of(app_with(route)))
        assert said[0]["model"] == "mammouth/kimi-k3", said
        assert said[-1] == {"model": None, "local": False}, said

    def test_a_run_that_has_reached_no_model_takes_nothing_back(self):
        """A dispatch that names no model, before any has been named, is not a
        sentence about anything: the beat stays the comment it was."""
        place = SR.RunPlace()
        place.note(None, True)
        assert place.at() is None
        place.note("stabilityai/stable-diffusion-3.5-large", True)
        place.note(None, True)
        assert place.at() == (None, True)

    def test_the_answer_itself_is_untouched(self):
        """The terminal frame stays exactly what a plain POST would have
        returned, body and status. services/directRun.ts reads it and nothing
        else, and src/services/__tests__/directRun.spec.ts holds the same claim
        from the other side."""
        def work():
            SR.note_dispatch("mammouth/glm-5.3", local=False)
            return {"ok": True, "n": 7}, 201

        def route():
            return SR.sse_response(
                SR.streamed_answer(work, label="TEST", interval=0.02))

        text = frames_of(app_with(route))
        block = [b for b in text.split("\n\n") if b.startswith("event: complete")][0]
        line = [ln for ln in block.split("\n") if ln.startswith("data: ")][0]
        assert json.loads(line[len("data: "):]) == {
            "http_status": 201, "body": {"ok": True, "n": 7}}, block


class TestWhatTheWorkerWritesIsWhatTheRequestThreadReads:
    """The trap this shape exists to avoid: the work runs under a COPY of the
    context, so only a shared mutable object crosses back."""

    def test_the_holder_is_shared_and_not_copied(self):
        seen = {}
        done = threading.Event()

        def work():
            # The holder the WORK can see, on the worker thread.
            seen["worker"] = SR._run_place.get()
            SR.note_dispatch("local/qwen3", local=True)
            done.wait(5.0)
            return {"ok": True}, 200

        def route():
            def heartbeat(elapsed, nth):
                # Where the BEAT reads it, which is the only reading that
                # decides anything: what the worker wrote into has to be this.
                seen["beat"] = SR._run_place.get()
                out = SR.heartbeat_comment(elapsed, nth)
                if "event: model_place" in out:
                    done.set()
                return out

            return SR.sse_response(
                SR.streamed_answer(work, label="TEST", heartbeat=heartbeat,
                                   interval=0.02))

        places_in(frames_of(app_with(route)))
        assert seen["worker"] is not None
        assert seen["worker"] is seen["beat"], (
            "the worker wrote into a holder of its own — nothing it says can "
            "reach the beat")


class TestTheNameIsSaidAgainOnEveryBeat:
    def test_a_second_beat_repeats_it(self):
        """Said once, the line could not be recovered from a page that cleared
        it — and a page clears for several honest reasons."""
        beats = {"n": 0}
        done = threading.Event()

        def work():
            SR.note_dispatch("local/qwen3", local=True)
            done.wait(5.0)
            return {"ok": True}, 200

        def route():
            def heartbeat(elapsed, nth):
                out = SR.heartbeat_comment(elapsed, nth)
                if "event: model_place" in out:
                    beats["n"] += 1
                    if beats["n"] >= 2:
                        done.set()
                return out

            return SR.sse_response(
                SR.streamed_answer(work, label="TEST", heartbeat=heartbeat,
                                   interval=0.02))

        said = places_in(frames_of(app_with(route)))
        assert len(said) >= 2, said
        assert {p["model"] for p in said} == {"local/qwen3"}, said

    def test_the_line_follows_a_chain(self):
        """Nineteen model calls in one run is the case this exists for: the bar
        follows the chain instead of naming whichever call the answer mentions.

        It is SAMPLED, at the beat: a call that is over before the next beat is
        never seen. That is the honest limit of a name that travels on the
        heartbeat, and it is why the test lets each step wait for its frame."""
        go = threading.Semaphore(0)

        def work():
            for name in ("mammouth/glm-5.3", "local/qwen3",
                         "openrouter/deepseek/deepseek-v4-pro"):
                SR.note_dispatch(name, local=name.startswith("local/"))
                go.acquire()
            return {"ok": True}, 200

        def route():
            def heartbeat(elapsed, nth):
                out = SR.heartbeat_comment(elapsed, nth)
                if "event: model_place" in out:
                    go.release()
                return out

            return SR.sse_response(
                SR.streamed_answer(work, label="TEST", heartbeat=heartbeat,
                                   interval=0.02))

        text = frames_of(app_with(route))
        assert said_in(text) == ["mammouth/glm-5.3", "local/qwen3",
                                 "openrouter/deepseek/deepseek-v4-pro"], said_in(text)
        assert [p["local"] for p in places_in(text)][:1] == [False]


class TestAHolderBelongsToOneStream:
    """Reproduced on 2026-09-09, twice: a name from a finished request opening a
    stream that had dispatched nothing."""

    def test_a_dispatch_after_the_stream_reaches_no_later_stream(self):
        def dispatching_work():
            SR.note_dispatch("anthropic/claude-opus-4-1", local=False)
            return {"ok": True}, 200

        def first():
            return SR.sse_response(
                SR.streamed_answer(dispatching_work, label="TEST", interval=0.02))

        app = Flask(__name__)
        app.add_url_rule("/first", "first", first, methods=["POST"])

        @app.route("/plain", methods=["POST"])
        def plain():
            # A request of its own, reaching a model, on the same pooled thread.
            SR.note_dispatch("anthropic/claude-opus-4-1", local=False)
            return jsonify({"ok": True})

        def quiet_work():
            return {"ok": True}, 200

        @app.route("/second", methods=["POST"])
        def second():
            return SR.sse_response(
                SR.streamed_answer(quiet_work, label="TEST", interval=0.02))

        client = app.test_client()
        client.post("/first", json={"enable_streaming": True}).get_data()
        client.post("/plain")
        text = client.post("/second", json={"enable_streaming": True}).get_data(as_text=True)
        assert places_in(text) == [], (
            "a stream that reached no model named one anyway")

    def test_the_contextvar_is_put_back(self):
        def work():
            SR.note_dispatch("local/qwen3", local=True)
            return {"ok": True}, 200

        def route():
            return SR.sse_response(
                SR.streamed_answer(work, label="TEST", interval=0.02))

        before = SR._run_place.get()
        frames_of(app_with(route))
        assert SR._run_place.get() is before


class TestTheFiveRoutesThatBuildTheirOwnResponse:
    """chat, three canvas runs and the text proxy hand their frames to a
    `Response` of their own and never reach `sse_response`. They breathe with
    the same loop, so the holder stands around that loop as well."""

    def test_a_route_that_never_calls_sse_response_still_says_it(self):
        wrote = threading.Event()

        def source():
            SR.note_dispatch("local/qwen3", local=True)
            wrote.wait(5.0)
            yield {"n": 1}

        def route():
            def heartbeat(elapsed, nth):
                out = SR.heartbeat_comment(elapsed, nth)
                if "event: model_place" in out:
                    wrote.set()
                return out

            def generate():
                yield from SR.events_with_heartbeat(
                    source, label="TEST",
                    frame=lambda item: SR.generate_sse_event("item", item),
                    heartbeat=heartbeat, interval=0.02)

            return Response(stream_with_context(generate()),
                            mimetype="text/event-stream")

        said = places_in(frames_of(app_with(route)))
        assert said and said[0]["model"] == "local/qwen3", said


class TestOutsideAStreamNothingIsHeld:
    def test_a_dispatch_with_no_holder_is_silent(self):
        """Every model call on the platform goes through `note_dispatch`,
        including the ones made outside a streamed request. None of them may
        raise, and none may leave anything behind."""
        app = Flask(__name__)

        @app.route("/plain", methods=["POST"])
        def plain():
            SR.note_dispatch("mammouth/glm-5.3", local=False)
            return jsonify({"ok": True})

        assert SR._run_place.get() is None, (
            "a holder outlived its stream — see `_under_a_run_place`")
        response = app.test_client().post("/plain")
        assert response.status_code == 200
        assert SR._run_place.get() is None


class TestWhoeverSendsSaysWhatTheySend:
    """The dispatch is read off what goes ON THE WIRE, never off a config: the
    engine can send a model other than the one requested, and the platform holds
    the sent one to be the true answer (test_interception_model_choice.py).

    This is a REMINDER, not a coverage proof. It names the sites instrumented on
    2026-09-09 and holds them to it. It cannot see a missing one:
    `media_analysis_client`, `heartmula_client`, `stable_audio_client`,
    `comfyui_service` and `training_service` all
    reach a model and say nothing. None of them is reachable from a Latent Lab
    surface, and that bar is the only reader there is, so nothing is dark today
    that anybody can see; the day the line goes onto another surface, this list
    is the work. `hunyuan3d_client` is only ever asked whether it is there."""

    INSTRUMENTED = ("services/openai_style_stream.py", "services/llm_client.py",
                    "services/diffusers_client.py", "services/comfyui_ws_client.py",
                    # services/text_client.py is not here: the tokenizer doors on
                    # ComfyUI run no model, and the transport that announced one
                    # went with the GPU service's text station (2026-10-10).
                    # Two forwardings that carry no client of their own: they
                    # POST to the GPU service with plain `requests`.
                    "routes/fusion_workbench_routes.py",
                    "routes/cross_aesthetic_routes.py")

    def test_the_instrumented_still_say_what_they_send(self):
        import ast
        root = Path(__file__).resolve().parents[1] / "my_app"
        for name in self.INSTRUMENTED:
            source = (root / name).read_text(encoding="utf-8")
            ast.parse(source)
            assert "note_dispatch(" in source, (
                f"{name} reaches a model and says nothing about it")

    def test_the_instrumented_also_take_the_name_back(self):
        """Saying it is half of it. A call that FAILS leaves the name standing
        in the bar until a later dispatch replaces it or the run ends, so a site
        that announces needs a way to say it is at nothing as well —
        `note_dispatch(None, ...)`. Counted apart from the announcement,
        because a scan for the call alone cannot tell the two apart.

        `services/openai_style_stream.py` is the one that needs none: it does
        not swallow its failure but RAISES, so either the run ends — and the end
        of the stream takes the line — or the retry above it announces again."""
        root = Path(__file__).resolve().parents[1] / "my_app"
        for name in self.INSTRUMENTED:
            if name == "services/openai_style_stream.py":
                continue
            source = (root / name).read_text(encoding="utf-8")
            assert "note_dispatch(None" in source, (
                f"{name} announces a model and never takes the name back")
