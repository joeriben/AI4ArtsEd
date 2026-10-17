#!/usr/bin/env python3
"""
The yes/no classification protocol, against a real child process and no GPU.

This is the path the age and content check now takes for every prompt and
every picture. It has one shape and one number: the model is given a policy
and a document, it writes one word, and the score is the softmax over the yes
and no logprobs of that one position. A threshold is read off that number, so
everything that can make the number wrong makes a verdict wrong -- and a
verdict that is wrong in one direction shows a child a picture.

Until 2026-09-23 none of it was under test. An adversarial review of that day
found a release path in the score reader and a silent hole where a model that
cannot answer the protocol at all still produced a well-formed number; both
are fixed, and both are asserted here, because the previous guarantee was a
comment.

The harness is tests/test_llm_child_backend.py's: a real child process,
spawned through the supervisor the service uses, answering on a real socket.
No model is loaded, no GPU is touched, and the aliases are synthetic.

Run:
    venv/bin/python -m pytest gpu_service/tests/test_safety_classifier_contract.py -q
"""

import base64
import os
import sys

import pytest
import requests

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from test_llm_child_backend import (  # noqa: E402
    PNG,
    Sandbox,
    model_config,
)

from services.llm_child_backend import (  # noqa: E402
    ChildDied,
    LLMBackend,
    MODEL_CONFIGS,
    ModelLoadRefused,
    data_url_for,
)

CLASSIFIER_ALIAS = "fake-guard:3b"
PLAIN_ALIAS = "fake-plain:1b"


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A sandbox carrying two aliases: one declared a classifier, one not."""
    sandbox = Sandbox(tmp_path, monkeypatch)
    sandbox.env(FAKE_LLAMA_MODE="ready", FAKE_LLAMA_HEALTH_DELAY_S="0")
    config = model_config(sandbox.model, sandbox.mmproj)
    config["classifier"] = True
    MODEL_CONFIGS[CLASSIFIER_ALIAS] = config
    MODEL_CONFIGS[PLAIN_ALIAS] = model_config(sandbox.model)
    try:
        yield sandbox
    finally:
        MODEL_CONFIGS.pop(CLASSIFIER_ALIAS, None)
        MODEL_CONFIGS.pop(PLAIN_ALIAS, None)
        sandbox.close()


def verdict(box, name, backend=None):
    """Which of the fake server's answers the next request gets.

    The environment only seeds a child at spawn, so a child that is already
    running is told through its own /control -- which is why that endpoint
    exists at all.
    """
    box.env(FAKE_LLAMA_VERDICT=name)
    if backend is not None:
        child = backend._supervisor._children.get(CLASSIFIER_ALIAS)
        if child is not None:
            requests.get(child.base_url() + "/control?verdict=" + name, timeout=5)


def sent(backend, alias=CLASSIFIER_ALIAS):
    """What the child was last sent, read back off the child itself."""
    child = backend._supervisor._children[alias]
    body = requests.get(child.base_url() + "/last-request", timeout=5).json()
    return body["body"]


# =============================================================================
# The payload
# =============================================================================

class TestTheRequestIsTheOneTheModelWasTrainedOn:
    def test_the_system_line_is_the_cards_own_and_carries_no_policy(self, box):
        backend = box.backend()
        verdict(box, "no")
        backend.classify(CLASSIFIER_ALIAS, "instruct here", "query here", "document here")
        messages = sent(backend)["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == LLMBackend.CLASSIFIER_SYSTEM
        # The policy travels in the user message. A system line that carried it
        # would be a second prompt the model was never trained against.
        assert "instruct here" not in messages[0]["content"]

    def test_the_policy_and_the_document_travel_in_the_three_fields(self, box):
        backend = box.backend()
        verdict(box, "no")
        backend.classify(CLASSIFIER_ALIAS, "the instruct", "the query", "the document")
        user = sent(backend)["messages"][1]
        assert user["role"] == "user"
        assert user["content"] == ("<Instruct>: the instruct\n\n"
                                   "<Query>: the query\n\n"
                                   "<Document>: the document")

    def test_the_logprobs_are_asked_for_and_the_sampler_cannot_move_them(self, box):
        backend = box.backend()
        verdict(box, "no")
        backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        payload = sent(backend)
        assert payload["logprobs"] is True
        assert payload["top_logprobs"] == 20
        assert payload["stream"] is False
        # Both of these: the server sends the raw softmax over the vocabulary,
        # so neither can distort the number -- and a later change to either
        # default must fail here rather than move a threshold quietly.
        assert payload["temperature"] == 0.0
        assert payload["repeat_penalty"] == 1.0

    def test_no_output_cap_is_set(self, box):
        """A cap on this path is a silent limit where silence is the failure:
        the answer would be cut before the word, no logprob would arrive, and
        the check would block every picture as a fault of the installation."""
        backend = box.backend()
        verdict(box, "no")
        backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        payload = sent(backend)
        for key in ("max_tokens", "n_predict", "max_completion_tokens"):
            assert key not in payload

    def test_a_picture_travels_with_the_prefix_cache_off(self, box, tmp_path):
        """The same reason as the reading path: a cached prefix carried across
        two pictures produced the damaged second reading."""
        backend = box.backend()
        verdict(box, "no")
        backend.classify(CLASSIFIER_ALIAS, "i", "q", "d",
                         images=[data_url_for(base64.b64encode(PNG).decode())])
        payload = sent(backend)
        assert payload["cache_prompt"] is False
        parts = payload["messages"][1]["content"]
        assert any(part.get("type") == "image_url" for part in parts)


# =============================================================================
# The model behind the alias
# =============================================================================

class TestOnlyADeclaredClassifierIsAsked:
    def test_a_model_that_is_not_one_is_refused_by_name(self, box):
        """A guard trained to write safe/unsafe still has yes and no in its
        vocabulary, so it answers this protocol with a well-formed number over
        two tokens it never meant to emit, at HTTP 200, and no layer above can
        tell that from a verdict."""
        backend = box.backend()
        verdict(box, "no")
        with pytest.raises(ModelLoadRefused) as caught:
            backend.classify(PLAIN_ALIAS, "i", "q", "d")
        assert PLAIN_ALIAS in str(caught.value)
        assert "classifier" in str(caught.value)

    def test_it_is_refused_before_the_child_is_ever_started(self, box):
        """The refusal is a configuration fault. Loading weights to discover it
        would put the wrong model on the card and hold a slot while doing it."""
        backend = box.backend()
        with pytest.raises(ModelLoadRefused):
            backend.classify(PLAIN_ALIAS, "i", "q", "d")
        assert PLAIN_ALIAS not in backend._supervisor._children

    def test_an_alias_nobody_registered_is_refused_too(self, box):
        backend = box.backend()
        with pytest.raises(ModelLoadRefused):
            backend.classify("fake-nothing:1b", "i", "q", "d")


# =============================================================================
# The number
# =============================================================================

class TestTheScoreIsReadOffTheAnswerItself:
    def test_a_no_scores_low_and_a_yes_scores_high(self, box):
        backend = box.backend()
        verdict(box, "no", backend)
        low = backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        verdict(box, "yes", backend)
        high = backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        assert low < 0.5 < high
        assert 0.0 <= low <= 1.0 and 0.0 <= high <= 1.0

    def test_a_first_token_that_is_not_an_answer_is_no_verdict(self, box):
        """The release path an adversarial review found on 2026-09-23. The
        model wrote something else; yes and no sit in the tail of that
        position with a millionth of the mass each, and their ratio is noise.
        Read as a score it is 0.09 -- under the threshold, which is a release.
        There is no verdict here, and None is how the caller is told so."""
        backend = box.backend()
        verdict(box, "preamble")
        assert backend.classify(CLASSIFIER_ALIAS, "i", "q", "d") is None

    def test_a_side_that_reaches_the_vocabulary_twice_is_counted_whole(self, box):
        """0.446 against 0.301 when the spellings are summed, 0.426 against
        0.301 when only the larger one is read. The threshold sits between
        them, so this is a picture held back or let out."""
        backend = box.backend()
        verdict(box, "split")
        score = backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        assert score == pytest.approx(0.4462 / (0.4462 + 0.3012), abs=0.002)
        assert score > 0.5

    def test_a_missing_side_is_no_verdict(self, box):
        """There is no two-way softmax over one side, and this method does not
        invent the other."""
        backend = box.backend()
        verdict(box, "only_yes")
        assert backend.classify(CLASSIFIER_ALIAS, "i", "q", "d") is None

    def test_an_answer_without_logprobs_is_no_verdict(self, box):
        backend = box.backend()
        verdict(box, "no_logprobs")
        assert backend.classify(CLASSIFIER_ALIAS, "i", "q", "d") is None

    def test_an_answer_without_choices_is_no_verdict(self, box):
        backend = box.backend()
        verdict(box, "no_choices")
        assert backend.classify(CLASSIFIER_ALIAS, "i", "q", "d") is None

    def test_every_way_of_having_no_verdict_says_which_one_it_was(self, box, caplog):
        """An operator reading "the answer was neither yes nor no" can act on
        it. A block with no line behind it is a fault nobody can place."""
        backend = box.backend()
        for name in ("preamble", "only_yes", "no_logprobs", "no_choices"):
            caplog.clear()
            verdict(box, name, backend)
            with caplog.at_level("ERROR"):
                assert backend.classify(CLASSIFIER_ALIAS, "i", "q", "d") is None
            assert any("[LLM]" in record.message or "[LLM]" in record.getMessage()
                       for record in caplog.records), name


class TestTheTokenReaderKnowsWhatAnAnswerIs:
    @pytest.mark.parametrize("token,side", [
        ("yes", "yes"), ("no", "no"),
        ("Yes", "yes"), ("NO", "no"),
        (" yes", "yes"), ("▁no", "no"), ("no\n", "no"),
    ])
    def test_the_spellings_the_vocabulary_offers_are_answers(self, token, side):
        assert LLMBackend._yes_no_side(token) == side

    @pytest.mark.parametrize("token", [
        "nonsense", "nope", "yesterday", "Sure", "", " ", "unsafe", "safe", "y", "n",
    ])
    def test_a_word_that_merely_begins_with_the_letters_is_not_one(self, token):
        assert LLMBackend._yes_no_side(token) is None


# =============================================================================
# The transport
# =============================================================================

class TestATwoHundredThatIsNotAVerdictIsNamed:
    def test_a_body_that_is_not_json_dies_with_a_cause(self, box):
        """Without this the decode error went past the route's handler and
        reached the caller as an HTML 500 with no [LLM] line: fail-closed, and
        blind."""
        backend = box.backend()
        verdict(box, "not_json")
        with pytest.raises(ChildDied) as caught:
            backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        assert "not JSON" in str(caught.value)

    def test_a_refusal_from_the_server_is_not_a_score(self, box):
        backend = box.backend()
        verdict(box, "no")
        backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        child = backend._supervisor._children[CLASSIFIER_ALIAS]
        requests.get(child.base_url() + "/control?status=500", timeout=5)
        with pytest.raises(Exception) as caught:
            backend.classify(CLASSIFIER_ALIAS, "i", "q", "d")
        assert not isinstance(caught.value, (int, float))

    def test_the_slot_is_given_back_after_a_verdict(self, box):
        """One admission per request, held across load and forward, released
        after. A slot kept by the check is a card nobody else can reach."""
        backend = box.backend()
        verdict(box, "no")
        for _ in range(3):
            assert backend.classify(CLASSIFIER_ALIAS, "i", "q", "d") is not None
        child = backend._supervisor._children[CLASSIFIER_ALIAS]
        assert child.in_use == 0


# =============================================================================
# The route between the two
# =============================================================================

class TestTheRouteNeverTurnsSilenceIntoAScore:
    """The seam. The engine answers a verdict or None, the caller reads a
    number and compares it to a threshold, and between them sits this route.
    The fifth of the chain's recorded failure patterns lives exactly here: a
    verdict reached, recorded -- and never read. A None arriving as
    `{"score": 0}` or as `{"score": null}` is a picture let out.
    """

    def client(self, monkeypatch, answer):
        from flask import Flask
        import routes.llm_routes as routes

        class StubEngine:
            def classify(self, **kwargs):
                if isinstance(answer, Exception):
                    raise answer
                return answer

        monkeypatch.setattr("services.llm_child_backend.get_llm_backend",
                            lambda: StubEngine())
        app = Flask(__name__)
        app.register_blueprint(routes.llm_bp, url_prefix="/api/llm")
        return app.test_client()

    def ask(self, client, **overrides):
        body = {"model": CLASSIFIER_ALIAS, "instruct": "i", "query": "q",
                "document": "d"}
        body.update(overrides)
        return client.post("/api/llm/classify", json=body)

    def test_a_verdict_comes_back_as_the_number(self, monkeypatch):
        response = self.ask(self.client(monkeypatch, 0.87))
        assert response.status_code == 200
        assert response.get_json()["score"] == pytest.approx(0.87)

    def test_no_verdict_is_an_error_and_carries_no_score(self, monkeypatch):
        response = self.ask(self.client(monkeypatch, None))
        assert response.status_code == 500
        assert "score" not in response.get_json()

    def test_a_refused_model_is_an_error_and_carries_no_score(self, monkeypatch):
        refusal = ModelLoadRefused("not a safety classifier")
        response = self.ask(self.client(monkeypatch, refusal))
        assert response.status_code != 200
        assert "score" not in response.get_json()

    def test_a_dead_child_is_an_error_and_carries_no_score(self, monkeypatch):
        gone = ChildDied(CLASSIFIER_ALIAS, exit_code=-9, detail="it is gone")
        response = self.ask(self.client(monkeypatch, gone))
        assert response.status_code != 200
        assert "score" not in response.get_json()

    @pytest.mark.parametrize("missing", ["model", "instruct", "query"])
    def test_a_request_without_a_policy_is_refused(self, monkeypatch, missing):
        """An empty policy field would otherwise reach the model as an empty
        question, which it answers -- and the answer to no question is what a
        mis-wired caller would then read as a verdict."""
        response = self.ask(self.client(monkeypatch, 0.02), **{missing: ""})
        assert response.status_code == 400
        assert "score" not in response.get_json()

    def test_a_request_with_neither_text_nor_picture_is_refused(self, monkeypatch):
        response = self.ask(self.client(monkeypatch, 0.02), document="")
        assert response.status_code == 400
        assert "score" not in response.get_json()

    def test_a_picture_alone_is_a_document(self, monkeypatch):
        """The image check sends no text worth the name: the picture is what
        is under examination."""
        response = self.ask(self.client(monkeypatch, 0.02), document="",
                            images=["AAAA"])
        assert response.status_code == 200
