#!/usr/bin/env python3
"""
The callers that were put on the shared cloud transport (2026-09-04).

Every cloud call outside the chat surface used to be one unstreamed request that
sat silent for as long as the model thought. Nine HTTP 524s in seven days came
from exactly that — Cloudflare gives up on a request whose origin has produced
no byte for about a hundred seconds — four runs died and one burned six and a
half minutes over three attempts. The same request asked with stream=True had
its first bytes in 1.29 s.

So the pipeline engine's cloud calls, the image check's verdict call and the
chat helper's providers now go through my_app/services/openai_style_stream:
since 2026-09-12 through its one entry point, call_chat, which takes the
provider's dialect from config/llm_providers.json. This file holds what has to
remain true of them.

The image-check half carries the weight. That check decides whether a picture
may be shown to a child and it fails closed: every failure it cannot resolve
ends in VLM_OPERATIONAL_BLOCK_MESSAGE. A retry that turns a dead provider into
an answer is an improvement; a retry that turns a block into a pass is a hole.
The tests below drive the whole check with a stand-in provider and assert the
block in each failing shape — including one the old transport could not even
produce: a model that reasoned about the picture and never stated a verdict.

Nothing here reaches a provider. Run:
  python3 -m pytest devserver/tests/test_cloud_transport_callers.py -q
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image

from my_app.routes import chat_routes
from my_app.utils import vlm_safety
from schemas.engine import prompt_interception_engine as engine_module

# Not a real model id. The platform must hold no knowledge about any particular
# model, so a test that named one would be pinning the thing that was removed.
MODEL = "some-model-under-test"


def _answer(content="an intercepted text", thinking=None, finish="stop"):
    """What the shared reader hands back, in the shape it hands it back in."""
    return {"content": content, "thinking": thinking, "tool_calls": None,
            "finish_reason": finish}


# ---------------------------------------------------------------------------
# 1. The pipeline engine
# ---------------------------------------------------------------------------

@pytest.fixture()
def offline_model_lists(monkeypatch):
    """process_request refreshes both model lists on every call, and the local
    one is a request to the service on this machine."""
    monkeypatch.setattr(engine_module.model_selector, "get_local_models", lambda: [])
    monkeypatch.setattr(engine_module.model_selector, "get_openrouter_models", lambda: [])


@pytest.fixture()
def transport(monkeypatch):
    """The shared reader, standing where the provider would be and writing down
    what it was asked for."""
    calls = []

    def fake(provider, messages, model, **kw):
        calls.append({"provider": provider, "messages": messages, "model": model, **kw})
        return _answer()

    monkeypatch.setattr(engine_module, "call_chat", fake)
    return calls


def _run(engine, model, parameters=None, usage_stage="stage2"):
    return asyncio.run(engine.process_request(engine_module.PromptInterceptionRequest(
        input_prompt="", prebuilt_prompt="a prompt", model=model, parameters=parameters,
        usage_stage=usage_stage,
    )))


class TestThePipelineEngineStreamsItsCloudCalls:
    @pytest.mark.parametrize("prefix,provider", [
        ("mammouth/", "mammouth"),
        ("mistral/", "mistral"),
        ("ionos/", "ionos"),
        ("openrouter/", "openrouter"),
        # openai joined the shared table on 2026-09-04. It was the last chat
        # completion on the platform that sent its request and then waited in
        # silence, and the installation that runs on it is a preset in
        # hardware_matrix.json, not a hypothetical.
        ("openai/", "openai"),
    ])
    def test_each_provider_reaches_the_shared_reader(self, offline_model_lists,
                                                     transport, prefix, provider):
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"{prefix}{MODEL}")
        assert response.success
        assert response.output_str == "an intercepted text"
        assert transport[0]["provider"] == provider
        # The routing prefix belongs to this platform, not to the provider: what
        # goes over the wire is the bare model id, whichever of the two ways the
        # prefix survived to this point.
        assert transport[0]["model"] == MODEL

    def test_the_answer_comes_back_under_the_id_that_was_asked_for(
            self, offline_model_lists, transport):
        """A caller compares what it requested against what ran, so the string
        it gets back has to be its own: dispatched_model, the full id with the
        service in front. model_used is the other field of the contract, the
        path the provider was asked for, and it is the same shape for every
        provider now -- until 2026-09-12 one provider's prefix survived the
        extractor and this test held that anomaly in place."""
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"mammouth/{MODEL}")
        assert response.model_used == MODEL
        assert response.dispatched_model == f"mammouth/{MODEL}"

    def test_nothing_caps_the_answer_unless_a_config_asks(self, offline_model_lists,
                                                          transport):
        """A hard output cap truncates substance mid-sentence, and on a
        reasoning model it is spent before a line of content is written."""
        engine = engine_module.PromptInterceptionEngine()
        _run(engine, f"mammouth/{MODEL}")
        assert transport[0]["max_tokens"] is None

    def test_a_cap_a_config_did_ask_for_is_forwarded(self, offline_model_lists, transport):
        engine = engine_module.PromptInterceptionEngine()
        _run(engine, f"mammouth/{MODEL}", {"max_tokens": 64000, "temperature": 0.2})
        assert transport[0]["max_tokens"] == 64000
        assert transport[0]["temperature"] == 0.2

    def test_the_stage_the_request_carries_is_what_gets_booked(self, offline_model_lists,
                                                              transport):
        """Until 2026-10-10 the engine booked every call under an attribute
        nothing set, so a translation before stage 4 counted as stage 2
        (finding S-032 of the code review of 2026-10-10). The executor now says which stage the config is."""
        engine = engine_module.PromptInterceptionEngine()
        _run(engine, f"mistral/{MODEL}", usage_stage="stage3")
        assert transport[0]["stage"] == "stage3"
        _run(engine, f"mistral/{MODEL}")
        assert transport[1]["stage"] == "stage2"

    def test_ionos_keeps_its_one_provider_specific_field(self, offline_model_lists,
                                                         transport):
        """A reasoning model there cannot be told to stop reasoning; low effort
        is the only lever, and a config that needs a structured answer rather
        than a train of thought depends on it."""
        engine = engine_module.PromptInterceptionEngine()
        _run(engine, f"ionos/{MODEL}", {"enable_thinking": False})
        assert transport[0]["extra_payload"] == {"reasoning_effort": "low"}

    def test_no_field_is_invented_for_the_providers_that_have_none(
            self, offline_model_lists, transport):
        engine = engine_module.PromptInterceptionEngine()
        _run(engine, f"mammouth/{MODEL}")
        assert transport[0]["extra_payload"] is None

    def test_reasoning_alone_is_refused_as_an_intercepted_text(self, offline_model_lists,
                                                               monkeypatch):
        """This engine's own decision, and it stays this engine's: what leaves
        here travels on through a pipeline as if a person had written it. A
        model that thought and then said nothing has failed the request. The
        chat surface makes the opposite choice at its own call site, which is
        why the reader hands both fields over instead of choosing for either."""
        monkeypatch.setattr(engine_module, "call_chat",
                            lambda *a, **kw: _answer(content="", thinking="I would say yes."))
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"mammouth/{MODEL}")
        assert response.success is False
        assert "empty response" in (response.error or "")
        assert "I would say yes" not in (response.error or "")
        assert response.output_str == ""

    def test_a_truncated_answer_is_not_an_intercepted_text(self, offline_model_lists,
                                                            monkeypatch):
        """What leaves this engine travels on through a pipeline as if a person
        had written it, so half a text is not a shorter one. A Stage-3
        translation cut mid-sentence reaches the image model as a fragment and
        the §86a word list then runs on the fragment — the words it looks for
        can stand in the half that never arrived. The provider says so in
        finish_reason, and the engine read past that field until 2026-09-04.

        The control for this is every test above: they answer with
        finish_reason 'stop' and assert success."""
        monkeypatch.setattr(engine_module, "call_chat",
                            lambda *a, **kw: _answer(content="Ein Kind malt mit einer",
                                                     finish="length"))
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"mammouth/{MODEL}")
        assert response.success is False
        assert "cut off" in (response.error or "")
        assert response.output_str == ""

    def test_a_truncated_anthropic_answer_is_not_an_intercepted_text(
            self, offline_model_lists, monkeypatch):
        """The same guard on the other dialect. Anthropic calls it 'max_tokens'
        and the reader translates it to 'length' precisely so that one guard can
        read both."""
        monkeypatch.setattr(engine_module, "call_chat",
                            lambda *a, **kw: _answer(content="Ein Kind malt mit einer",
                                                     finish="length"))
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"anthropic/{MODEL}")
        assert response.success is False
        assert "cut off" in (response.error or "")
        assert response.output_str == ""

    def test_a_provider_failure_fails_the_request_it_was(self, offline_model_lists,
                                                         monkeypatch):
        """No substitute model answers in its place: a caller that asked for one
        model and silently got another cannot tell the two apart afterwards."""
        def boom(*a, **kw):
            raise Exception("API Error: 524\nweb server is down")

        monkeypatch.setattr(engine_module, "call_chat", boom)
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"mammouth/{MODEL}")
        assert response.success is False
        assert "524" in (response.error or "")

    def test_anthropic_moved_onto_the_shared_transport_in_its_own_dialect(
            self, offline_model_lists, monkeypatch):
        """Until 2026-09-04 this call sent its request and then waited for the
        whole answer, and this test asserted that it did — it was the last one
        on the platform that did. It speaks a different dialect (/v1/messages,
        x-api-key, named SSE events), which is why it could not join the five
        above when they were streamed. The reader has since grown a second
        grammar over the same opener, and this call goes through it.

        What must not have changed is the boundary: the same two-value return,
        under the name the caller asked for. Which dialect the request takes is
        the reader's decision, from the table, and is held in the reader's own
        tests; the engine names the provider and nothing else."""
        calls = []

        def fake(provider, messages, model, **kw):
            calls.append({"provider": provider, "messages": messages, "model": model, **kw})
            return _answer()

        monkeypatch.setattr(engine_module, "call_chat", fake)
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"anthropic/{MODEL}")
        assert response.success
        assert response.output_str == "an intercepted text"
        assert response.model_used == MODEL
        assert response.dispatched_model == f"anthropic/{MODEL}"
        assert calls[0]["provider"] == "anthropic"
        assert calls[0]["model"] == MODEL
        assert calls[0]["messages"] == [{"role": "user", "content": "a prompt"}]

    def test_nothing_is_sent_to_anthropic_that_a_config_did_not_ask_for(
            self, offline_model_lists, monkeypatch):
        """No temperature where none was named, so the model applies its own
        exactly as it did before this call was streamed; and no cap, so the
        reader fills in the ceiling this API requires the field to carry rather
        than a budget chosen here."""
        calls = []
        monkeypatch.setattr(engine_module, "call_chat",
                            lambda provider, messages, model, **kw: calls.append(kw) or _answer())
        engine = engine_module.PromptInterceptionEngine()
        _run(engine, f"anthropic/{MODEL}")
        assert calls[0]["temperature"] is None
        assert calls[0]["max_tokens"] is None

    def test_what_a_config_did_ask_anthropic_for_is_forwarded(self, offline_model_lists,
                                                              monkeypatch):
        calls = []
        monkeypatch.setattr(engine_module, "call_chat",
                            lambda provider, messages, model, **kw: calls.append(kw) or _answer())
        engine = engine_module.PromptInterceptionEngine()
        _run(engine, f"anthropic/{MODEL}", {"temperature": 0.2, "max_tokens": 64000})
        assert calls[0]["temperature"] == 0.2
        assert calls[0]["max_tokens"] == 64000
        assert calls[0]["stage"] == "stage2"

    def test_anthropic_reasoning_alone_is_refused_as_an_intercepted_text(
            self, offline_model_lists, monkeypatch):
        """The same decision the five above get, now reachable on this path
        too: Anthropic delivers reasoning as thinking blocks of its own, the
        reader keeps them in their own field, and what leaves this engine
        travels on through a pipeline as if a person had written it."""
        monkeypatch.setattr(engine_module, "call_chat",
                            lambda *a, **kw: _answer(content="",
                                                     thinking="I would say yes."))
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"anthropic/{MODEL}")
        assert response.success is False
        assert "empty response" in (response.error or "")
        assert "I would say yes" not in (response.error or "")
        assert response.output_str == ""

    def test_an_anthropic_failure_fails_the_request_it_was(self, offline_model_lists,
                                                           monkeypatch):
        def boom(*a, **kw):
            raise Exception("anthropic stream error: overloaded_error: Overloaded")

        monkeypatch.setattr(engine_module, "call_chat", boom)
        engine = engine_module.PromptInterceptionEngine()
        response = _run(engine, f"anthropic/{MODEL}")
        assert response.success is False
        assert "Overloaded" in (response.error or "")


def test_the_retry_loop_around_the_unstreamed_call_is_gone():
    """It asked the same silent question again rather than shortening the
    silence, and it asked it around a request that might already have been
    partly answered. The shared opener asks again for the same twelve statuses
    — 429, 502, 503, 504 and Cloudflare's 520-527 — with the same three
    attempts and the same backoff, and only BEFORE the first byte. That is why
    this could be removed rather than merely moved."""
    assert not hasattr(engine_module.PromptInterceptionEngine,
                       "_requests_post_with_retry")
    source = Path(engine_module.__file__).read_text(encoding="utf-8")
    # The engine builds no HTTP request of its own for a cloud model any more.
    assert "requests.post" not in source


def test_the_dead_second_stream_reader_is_gone():
    """_call_mistral_stream had no caller anywhere in the tree and was the
    platform's second reader for streamed OpenAI-style answers. An unused copy
    of a reader is how two copies drift apart while nobody notices."""
    source = Path(engine_module.__file__).read_text(encoding="utf-8")
    # The definition, not the name: a comment where it stood says why it went,
    # and that comment is worth more than the strictness of this assertion.
    assert "def _call_mistral_stream" not in source
    assert "iter_lines" not in source


# ---------------------------------------------------------------------------
# 2. The image check
# ---------------------------------------------------------------------------

VERDICT_MODEL = f"mammouth/{MODEL}"


@pytest.fixture()
def picture(tmp_path):
    """A real file, because the check normalises and encodes it before it asks
    anybody anything. 128px: it refuses images below 64."""
    path = tmp_path / "a-picture.png"
    Image.new("RGB", (128, 128), (120, 140, 160)).save(path)
    return path


@pytest.fixture()
def classifier(monkeypatch):
    """Puts one scripted score — or one failure — where the classifier would
    be. The picture check speaks to the GPU service on this machine now, so
    this stands in for that call and not for a provider."""
    from my_app.services import safety_classifier as sc

    def script(value=None, raises=None, record=None):
        def fake(instruct, query, document, images=None):
            if record is not None:
                record.update({"instruct": instruct, "query": query,
                               "document": document, "images": images})
            if raises is not None:
                raise raises
            return value

        monkeypatch.setattr(sc, "score", fake)
        monkeypatch.setattr(sc, "model_name", lambda: "a-classifier")

    return script


@pytest.fixture()
def verdict(monkeypatch):
    """Puts one scripted answer — or one failure — where the provider would be."""
    monkeypatch.setattr(vlm_safety.config, "STAGE3_MODEL", VERDICT_MODEL)

    def script(answer=None, raises=None, record=None):
        def fake(provider, messages, model, **kw):
            if record is not None:
                record.update({"provider": provider, "model": model, **kw})
            if raises is not None:
                raise raises
            return answer

        monkeypatch.setattr(vlm_safety, "call_chat", fake)

    return script


class TestTheImageCheckAsksTheModelItWasConfiguredToAsk:
    def test_the_configured_provider_and_model_are_what_is_asked(self, verdict):
        seen = {}
        verdict(answer=_answer(content="SAFE"), record=seen)
        content, finish = vlm_safety._call_verdict_model("a verdict prompt")
        assert (content, finish) == ("SAFE", "stop")
        assert seen["provider"] == "mammouth"
        assert seen["model"] == MODEL
        # A verdict is not chat and is not booked as chat.
        assert seen["stage"] == "safety"
        # The verdict model reasons before it answers, out of the same budget: a
        # cap of 200 cut one off mid-thought in production.
        assert seen.get("max_tokens") is None

    def test_the_shared_table_covers_every_provider_this_check_could_route_to(self):
        """The private table this file kept named these four. Deleting it lost
        no provider — and one of the four it named had an address with no DNS
        record at all."""
        from my_app.services import llm_providers as lp
        assert set(lp.names(lp.CHAT_COMPLETIONS)) >= {"mammouth", "mistral", "openrouter", "ionos"}

    def test_the_image_check_keeps_no_address_book_of_its_own(self):
        """It kept one until 2026-09-04, and the IONOS address in it resolves
        nowhere — written seventeen days after the working address was already
        in the tree, and never noticed because the verdict model has been
        elsewhere ever since. A third copy of a table is how that happens."""
        source = Path(vlm_safety.__file__).read_text(encoding="utf-8")
        assert "_CLOUD_PROVIDERS" not in source
        assert "ionoscloud.com" not in source
        assert "requests.post" not in source


class TestThePictureIsJudgedOnThisMachine:
    """Until 2026-09-23 a local model wrote a description of the picture and a
    CLOUD model rated the description. The picture stayed here; the sentence
    about it did not, and a sentence describing a child's picture is still
    about that child. These tests hold the picture, and every sentence about
    it, on this machine."""

    def test_no_cloud_transport_is_reached(self, picture, classifier, monkeypatch):
        def never(*a, **k):
            raise AssertionError("the picture check called the cloud transport")
        monkeypatch.setattr(vlm_safety, "call_chat", never)
        classifier(value=0.02)
        assert vlm_safety.vlm_safety_check(picture, "kids")[0] is True

    def test_the_picture_travels_as_an_image_and_not_as_a_description(
            self, picture, classifier):
        seen = {}
        classifier(value=0.02, record=seen)
        vlm_safety.vlm_safety_check(picture, "kids")
        assert seen["images"] and len(seen["images"]) == 1
        # The line beside the picture carries no account of it.
        assert seen["document"] == "The document is the image below."

    def test_the_question_is_the_one_for_a_picture_at_that_level(
            self, picture, classifier):
        from my_app.services import safety_classifier as sc
        seen = {}
        classifier(value=0.02, record=seen)
        vlm_safety.vlm_safety_check(picture, "youth")
        assert seen["query"] == sc.LEVEL_QUERIES["youth"]["image"]
        assert seen["instruct"] == sc.LEVEL_INSTRUCTS["youth"]


class TestTheImageCheckFailsClosed:
    def test_a_stated_no_is_the_only_way_through(self, picture, classifier):
        """The control for everything below it. The check blocks on any
        exception at all, so without a case that PASSES under the same harness
        the rest of this class would assert nothing."""
        classifier(value=0.02)
        is_safe, reason, detail = vlm_safety.vlm_safety_check(picture, "kids")
        assert is_safe is True
        assert reason == ""
        assert detail == ""

    @pytest.mark.parametrize("value", [0.02, 0.97])
    def test_the_score_never_travels_to_the_child(self, picture, classifier, value):
        """The third slot is handed on as `vlm_description` and printed under
        "Die Bild-KI sah:" (de.ts, key vlmSaw). It held the sentence a local
        model wrote about the picture; when the judgement moved onto this
        machine the slot briefly held the score instead, which would have shown
        a child 'Die Bild-KI sah: "score=0.9712"'. It carries nothing now, on
        both ways out."""
        classifier(value=value)
        assert vlm_safety.vlm_safety_check(picture, "kids")[2] == ""

    def test_a_yes_reads_as_a_rating_and_not_as_a_fault(self, picture, classifier):
        """The two block messages mean different things to the child reading
        them: one says the picture was judged, the other says it was not."""
        classifier(value=0.97)
        is_safe, reason, _ = vlm_safety.vlm_safety_check(picture, "kids")
        assert is_safe is False
        assert reason == vlm_safety.VLM_CONTENT_BLOCK_MESSAGE

    def test_no_verdict_blocks_as_a_fault(self, picture, classifier):
        classifier(value=None)
        is_safe, reason, _ = vlm_safety.vlm_safety_check(picture, "kids")
        assert is_safe is False
        assert reason == vlm_safety.VLM_OPERATIONAL_BLOCK_MESSAGE

    def test_a_classifier_that_raises_blocks_as_a_fault(self, picture, classifier):
        classifier(raises=Exception("connection reset by peer"))
        is_safe, reason, _ = vlm_safety.vlm_safety_check(picture, "kids")
        assert is_safe is False
        assert reason == vlm_safety.VLM_OPERATIONAL_BLOCK_MESSAGE

    def test_a_missing_file_blocks_as_a_fault(self, tmp_path, classifier):
        classifier(value=0.02)
        is_safe, reason, _ = vlm_safety.vlm_safety_check(tmp_path / "gone.png", "kids")
        assert is_safe is False
        assert reason == vlm_safety.VLM_OPERATIONAL_BLOCK_MESSAGE

    def test_the_threshold_is_read_the_way_the_model_card_states_it(
            self, picture, classifier):
        from my_app.services import safety_classifier as sc
        classifier(value=sc.UNSAFE_THRESHOLD)
        assert vlm_safety.vlm_safety_check(picture, "kids")[0] is False
        classifier(value=sc.UNSAFE_THRESHOLD - 0.001)
        assert vlm_safety.vlm_safety_check(picture, "kids")[0] is True

    @pytest.mark.parametrize("level", ["adult", "research"])
    def test_the_two_unchecked_levels_never_reach_the_classifier(
            self, picture, classifier, level):
        classifier(raises=AssertionError("asked on " + level))
        assert vlm_safety.vlm_safety_check(picture, level)[0] is True

    def test_open_is_checked(self, picture, classifier):
        """It was not. The old code checked a level only if this file happened
        to carry a describe prompt for it, and it carried kids and youth, so
        every picture at 'open' went out unlooked at."""
        classifier(value=0.97)
        assert vlm_safety.vlm_safety_check(picture, "open")[0] is False

    def test_a_level_nobody_set_is_asked_the_childs_question(
            self, picture, classifier):
        from my_app.services import safety_classifier as sc
        seen = {}
        classifier(value=0.02, record=seen)
        vlm_safety.vlm_safety_check(picture, "an-unknown-level")
        assert seen["query"] == sc.LEVEL_QUERIES["kids"]["image"]


class TestACutVerdictStreamWithholdsTheCode:
    """The whole check over a real socket, with the verdict cut after the word
    SAFE — the shape that showed a child a picture on 2026-09-04.

    Nothing is patched between the check and the wire here: what is served is
    the byte sequence a provider, or a proxy in front of one, produces when it
    stops in the middle, and what is asserted is what the child sees. The
    picture no longer travels this way; the sketch check does, because whether
    JavaScript escapes its sandbox is a question about code and not about
    content, and the classifier does not answer it.

    The socket harness is imported from the reader's own test file rather than
    written again here (project rule 13): a second copy of a scripted provider
    is how two copies drift apart.
    """

    SKETCH = "function setup() { eval('createCanvas(400, 400)') }"

    def _run(self):
        import asyncio
        from schemas.engine import stage_orchestrator as so
        return asyncio.run(so.execute_stage3_safety_code(self.SKETCH, "kids", "code"))

    @pytest.fixture()
    def cut_after_safe(self, monkeypatch):
        from test_openai_style_stream import (
            _Provider, chunk, sse, sse_cut_under_connection_close,
        )
        from my_app.services import openai_style_stream as oss

        provider = _Provider()
        provider.script(sse_cut_under_connection_close([sse(chunk({"content": "SAFE"}))]))
        monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, "mammouth",
                            lambda: (provider.url, "test-key"))
        monkeypatch.setattr(vlm_safety.config, "STAGE3_MODEL", VERDICT_MODEL)
        yield provider
        provider.close()

    def test_the_code_is_withheld(self, cut_after_safe):
        from schemas.engine import stage_orchestrator as so
        result = self._run()
        assert result["safe"] is False
        assert result["abort_reason"] == so.SAFETY_CHECK_UNAVAILABLE_MESSAGE

    def test_the_same_bytes_ending_properly_do_let_it_through(self, monkeypatch):
        """The control, and it matters: without it the block above could come
        from the socket harness rather than from the cut. The same word, the
        same transport, a stream that says it finished."""
        from test_openai_style_stream import _Provider, chunk, sse, sse_ok
        from my_app.services import openai_style_stream as oss

        provider = _Provider()
        provider.script(sse_ok([sse(chunk({"content": "SAFE"}, finish="stop"))]))
        monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, "mammouth",
                            lambda: (provider.url, "test-key"))
        monkeypatch.setattr(vlm_safety.config, "STAGE3_MODEL", VERDICT_MODEL)
        try:
            result = self._run()
        finally:
            provider.close()
        assert result["safe"] is True
        assert result["positive_prompt"] == self.SKETCH


# ---------------------------------------------------------------------------
# 3. The chat helper
# ---------------------------------------------------------------------------
# call_chat_helper carries this platform's two-stage model -> provider fallback
# chain and the data-protection gate that governs it. None of that changed on
# 2026-09-04: what changed is how ONE attempt travels. The four provider
# functions under the chain were four unstreamed POSTs and became four wrappers
# over the shared reader; since 2026-09-12 the dispatcher names the provider
# from the id and the reader takes the dialect from the table, so the wrappers
# and the prefix ladder are gone.
#
# Two things are held below. The chain still decides what it always decided —
# it falls over on an availability failure and it stands still on a refusal —
# and IONOS still never receives the picture.


@pytest.fixture()
def chat_transport(monkeypatch):
    """The shared reader, standing where the provider would be, in the chat
    module's namespace."""
    calls = []

    def fake(provider, messages, model, **kw):
        calls.append({"provider": provider, "messages": messages, "model": model, **kw})
        return _answer()

    monkeypatch.setattr(chat_routes, "call_chat", fake)
    return calls


class TestTheChatHelpersProvidersReachTheSharedReader:
    @pytest.mark.parametrize("prefix,provider", [
        ("mammouth/", "mammouth"),
        ("mistral/", "mistral"),
        ("ionos/", "ionos"),
        ("openrouter/", "openrouter"),
        # Until 2026-09-12 these two were sent to OpenRouter under a bare name
        # OpenRouter does not carry, so a fallback onto either failed the turn.
        # The provider named by the id is the provider that is asked.
        ("anthropic/", "anthropic"),
        ("openai/", "openai"),
    ])
    def test_each_provider_reaches_the_shared_reader(self, chat_transport, prefix, provider):
        result = chat_routes._dispatch_single_model(
            f"{prefix}{MODEL}", [{"role": "user", "content": "hallo"}],
            0.7, None, True, None, None)
        assert result["content"] == "an intercepted text"
        assert chat_transport[0]["provider"] == provider
        assert chat_transport[0]["model"] == MODEL
        # A chat turn is booked as chat, whichever provider answered it.
        assert chat_transport[0]["stage"] == "chat"

    def test_the_return_shape_is_the_one_the_chain_reads(self, chat_transport):
        result = chat_routes._dispatch_single_model(
            f"mammouth/{MODEL}", [{"role": "user", "content": "hallo"}],
            0.7, None, True, None, None)
        assert set(result) == {"content", "thinking", "tool_calls"}

    @pytest.mark.parametrize("prefix", ["mammouth/", "mistral/", "openrouter/"])
    def test_a_provider_that_can_be_handed_the_picture_is_handed_it(
            self, chat_transport, prefix):
        chat_routes._dispatch_single_model(
            f"{prefix}{MODEL}", [{"role": "user", "content": "what is this?"}],
            0.7, None, True, None, "a-base64-image")
        assert chat_transport[0]["image_b64"] == "a-base64-image"

    def test_ionos_is_never_handed_the_picture(self, monkeypatch):
        """The floor under is_vision_capable, and the reason it is a floor: this
        connection has never carried an image. It built its payload from the
        messages alone, so the picture was dropped before the request existed
        and the model answered from the text without saying so. The line is
        drawn in the table now ("image_input": false) and applied by the
        reader where the request is built, so it holds for every caller; the
        stand-in therefore sits under the reader's dialect switch, not above it."""
        from my_app.services import openai_style_stream as oss
        seen = []

        def fake_stream(provider, messages, model, temperature, max_tokens, **kw):
            seen.append({"provider": provider, "messages": messages, **kw})
            yield ("result", _answer())

        monkeypatch.setattr(oss, "_stream_openai_style", fake_stream)
        chat_routes._dispatch_single_model(
            f"ionos/{MODEL}", [{"role": "user", "content": "what is this?"}],
            0.7, None, True, None, "a-base64-image")
        assert seen[0]["provider"] == "ionos"
        assert seen[0]["image_b64"] is None
        # And nothing smuggled it into the messages instead.
        assert seen[0]["messages"] == [{"role": "user", "content": "what is this?"}]

    def test_no_cap_is_invented_for_a_turn_that_asked_for_none(self, chat_transport):
        chat_routes._dispatch_single_model(
            f"ionos/{MODEL}", [{"role": "user", "content": "hallo"}],
            0.7, None, True, None, None)
        assert chat_transport[0]["max_tokens"] is None

    def test_reasoning_stands_in_for_an_answer_the_model_never_gave(self, monkeypatch):
        """The chat surface's own policy, opposite to the pipeline engine's: a
        model that reasoned and then said nothing still has something to show a
        person. The reader keeps the two fields apart so each caller can decide
        for itself, and this is chat deciding."""
        monkeypatch.setattr(chat_routes, "call_chat",
                            lambda *a, **kw: _answer(content="", thinking="Ich überlege noch."))
        result = chat_routes._dispatch_single_model(
            f"mammouth/{MODEL}", [{"role": "user", "content": "hallo"}],
            0.7, None, True, None, None)
        assert result["content"] == "Ich überlege noch."
        assert result["thinking"] == "Ich überlege noch."


class TestATemperatureIsSentWhenSomebodyAskedForOne:
    """call_chat_helper carried a default of 0.7 and the chat route filled in
    0.7 where the request named none. On the messages dialect the platform's
    Anthropic preset names models that answer 400 to the field, so the
    default is the reader's, per dialect, and the helpers pass None on."""

    def test_no_temperature_reaches_the_reader_as_none(self, chat_transport):
        chat_routes.call_chat_helper([{"role": "user", "content": "hallo"}],
                                     model_override=f"anthropic/{MODEL}")
        assert chat_transport[0]["temperature"] is None

    def test_a_temperature_asked_for_reaches_the_reader_as_asked(self, chat_transport):
        chat_routes.call_chat_helper([{"role": "user", "content": "hallo"}],
                                     temperature=0.2, model_override=f"anthropic/{MODEL}")
        assert chat_transport[0]["temperature"] == 0.2

    def test_the_station_on_this_machine_keeps_its_default(self, monkeypatch):
        seen = []

        def fake_local(messages, model, temperature, max_tokens, **kw):
            seen.append(temperature)
            return _answer()

        monkeypatch.setattr(chat_routes, "_call_local_llm_chat", fake_local)
        chat_routes.call_chat_helper([{"role": "user", "content": "hallo"}],
                                     model_override=f"local/{MODEL}")
        assert seen == [0.7]


class TestTheFallbackChainStillDecidesWhatItDecided:
    """Not changed on 2026-09-04 and not this move's to change: which attempts
    are made, and in what order. Held here because the attempts now travel a
    different way, and a transport that swallowed or re-worded a failure would
    change the chain without touching a line of it."""

    @pytest.fixture(autouse=True)
    def two_candidates(self, monkeypatch):
        monkeypatch.setattr(chat_routes, "build_model_candidate_chain",
                            lambda setting_key, primary: [f"mammouth/{MODEL}",
                                                          f"mistral/{MODEL}"])

    def test_an_availability_failure_moves_to_the_next_candidate(self, monkeypatch):
        seen = []

        def fake(provider, messages, model, **kw):
            seen.append(provider)
            if provider == "mammouth":
                raise Exception("API Error: 524\nweb server is down")
            return _answer(content="the second candidate answered")

        monkeypatch.setattr(chat_routes, "call_chat", fake)
        result = chat_routes.call_chat_helper([{"role": "user", "content": "hallo"}])
        assert seen == ["mammouth", "mistral"]
        assert result["content"] == "the second candidate answered"
        assert result["model_used"] == f"mistral/{MODEL}"

    def test_a_content_refusal_stops_the_chain_where_it_stands(self, monkeypatch):
        """A prompt one provider refused must not be carried to a laxer one.
        That is not falling through, it is shopping for a yes."""
        seen = []

        def fake(provider, messages, model, **kw):
            seen.append(provider)
            raise Exception('API Error: 400\n{"error": "content policy violation"}')

        monkeypatch.setattr(chat_routes, "call_chat", fake)
        with pytest.raises(Exception) as excinfo:
            chat_routes.call_chat_helper([{"role": "user", "content": "hallo"}])
        assert "content policy" in str(excinfo.value)
        assert seen == ["mammouth"]

    def test_a_provider_that_answers_with_nothing_moves_to_the_next_candidate(self, monkeypatch):
        """The one behaviour the move changed. Mistral and OpenRouter used to
        hand an empty string back as though it were an answer; the reader raises
        instead, and the words it raises with are read as availability rather
        than as a refusal — so the turn moves on rather than showing a room a
        blank."""
        seen = []

        def fake(provider, messages, model, **kw):
            seen.append(provider)
            if provider == "mammouth":
                raise Exception(f"mammouth returned empty response for model {model}")
            return _answer(content="the second candidate answered")

        monkeypatch.setattr(chat_routes, "call_chat", fake)
        result = chat_routes.call_chat_helper([{"role": "user", "content": "hallo"}])
        assert seen == ["mammouth", "mistral"]
        assert result["content"] == "the second candidate answered"
