#!/usr/bin/env python3
"""One request may name the model that writes its interception. Nothing else moves.

The instrument this serves puts the SAME prompt through the SAME perspective on
several writing models and lays the results side by side. That comparison only
says something while everything around the writing model is held still: the task
instruction with its kids/youth safety prefix, the config context, the Wikipedia
meta, the reading-volume clause, and the media adaption that follows the
interception. A row whose safety prefix or whose adaption had also changed would
be a second variable, and the reader could not tell which one they are looking
at.

So the tests here come in pairs: one that the named model actually arrives at the
backend, and one that the prompt which arrives with it is character for character
the prompt the configured model would have received.

The second half of the file is about what the endpoint ANSWERS when the named
model cannot write this interception. Each cause gets its own answer: an id this
installation does not know, an id whose service could not be asked, a register
carrying no entry for the provider this installation is set to, a model that is
listed but was never installed, a preset that binds its own model, a preset of
another stage, a chunk template this installation could not load, and a request
that writes no interception at all -- because the pipeline skips the step or
because the pre-check path was asked for. Each one asks something different of
the person reading it, so each one says what happened rather than that
something did.

Each answer says it twice: a sentence for the person, and a `cause` for whoever
called -- one word out of a fixed list. The picker never reads the sentence; it
offers the install, reports the outage or points at the provider setting from
the word alone, so the word is the contract and the sentence stays free to be
reworded or translated.

A preset that hands the input back verbatim is not among them. Whether it does
is settled by what the model reaches for while it writes, so the answer says
which of the two happened instead of the request being refused for the case it
might have been.

Everything is mocked. No model is called, no network is touched.

Run: python3 -m pytest devserver/tests/test_interception_model_choice.py -q
"""
import asyncio
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

import config
from my_app.routes import chat_routes
from my_app.routes import settings_routes
from my_app.routes import schema_pipeline_routes as R
from schemas.engine import prompt_interception_engine as engine_module
from schemas.engine.pipeline_executor import PipelineContext, PipelineStep
from schemas.engine.backend_router import (
    BackendRequest, BackendResponse, BackendRouter, BackendType,
)

SCHEMA = "bauhaus"
SKIP_STAGE2_SCHEMA = "surrealizer"
# A pipeline that skips Stage 2, put under a preset that DOES build an
# interception chunk: the presets shipping on such a pipeline build none, so
# only a fabricated one can show the two halves of the override apart.
SKIP_STAGE2_PIPELINE = "surrealizer"
# The preset that owes the user their prompt back when no context is given.
PASSTHROUGH_SCHEMA = "user_defined"
# The shipped preset that is pinned to the guard model reading the visitor's
# text. Configs outside interception/ keep their folder in the name.
GUARD_SCHEMA = "pre_interception/safety_llamaguard"
# An output config whose adaption still runs. The SD3.5 configs carry no
# adaption instruction any more — their chunk hands the intercepted text to
# the encoders as it stands — so a test about the adaption cannot be put on
ADAPTION_OUTPUT_CONFIG = "p5js_code"
HARMLESS = "Ein Haus steht in einer Landschaft."
BLOCKED = "a swastika painted on the door"
KIDS_PREFIX = "SAFETY (ages 8-13): This output generates media for children."

# Named, not resolved: the point of these tests is that the id the caller writes
# is the id that arrives, so it must not come from the same place the code reads.
CHOSEN = "local/some-offered-model:9b"
UNLISTED = "local/a-model-nobody-offers:1b"
CONFIGURED = "local/the-configured-model:27b"
DISPATCHED = "local/the-model-that-actually-ran:9b"
PINNED = "local/the-model-the-preset-is-pinned-to:1b"
# No prefix, so no service: this is a typo, not an id of anything.
BARE = "a-model-nobody-offers"
PROVIDER = "a-configured-provider"
# A chunk name no template answers to. The preset is the shipped one with its
# chunk taken away: what is missing is a file on this machine, not something the
# preset gets wrong.
MISSING_CHUNK = "a-chunk-template-this-installation-does-not-hold"
# The register the model list was read from, carrying the provider this
# installation is set to -- the state in which nothing about the register itself
# is what a refusal is about. The gate takes it from the same call the list
# comes from, so a stand-in for that call carries it.
OFFERED_REGISTER = {'llm_presets': {PROVIDER: {'models': {}}}}


@pytest.fixture(autouse=True)
def configured_model(monkeypatch):
    """The platform's own Stage-2 model, pinned for the length of a test.

    It is read from user_settings.json, and a worktree does not carry that file
    — so without this the "no model named" case would compare an empty string
    with an empty string and pass while proving nothing.
    """
    monkeypatch.setattr(config, "STAGE2_INTERCEPTION_MODEL", CONFIGURED)


class _Backend:
    """Stands in for the backend router and records what it was asked to run."""

    def __init__(self, dispatched_model=None, contents=None):
        self.requests = []
        self.dispatched_model = dispatched_model
        # One entry per call, the last one repeating: a Wikipedia lookup asks
        # the model twice, and the second answer is written with what it found.
        self.contents = list(contents) if contents else None

    async def process_request(self, request):
        self.requests.append(request)
        metadata = {"model_used": "the-name-the-backend-reports",
                    "backend_type": "local_llm"}
        if self.dispatched_model:
            metadata["dispatched_model"] = self.dispatched_model
        if self.contents:
            content = self.contents.pop(0) if len(self.contents) > 1 else self.contents[0]
        else:
            content = "an intercepted text"
        return BackendResponse(success=True, content=content, metadata=metadata)


class _CountingGate:
    """Stands in for llm_queue_semaphore and records what was held, and how deep."""

    def __init__(self):
        self.entered = 0
        self.depth = 0
        self.max_depth = 0

    def __enter__(self):
        self.entered += 1
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        return self

    def __exit__(self, *exc_info):
        self.depth -= 1
        return False


def _intercept(interception_model=None, safety_level="kids"):
    """One interception, with the backend replaced. Returns (result, request)."""
    R.init_schema_engine()
    cfg = R.pipeline_executor.config_loader.get_config(SCHEMA)
    assert cfg is not None, f"the '{SCHEMA}' interception config is not loadable"

    backend = _Backend()
    router = R.pipeline_executor.backend_router
    router.process_request = backend.process_request
    try:
        result = asyncio.run(R.execute_stage2_interception(
            schema_name=SCHEMA,
            input_text=HARMLESS,
            config=cfg,
            safety_level=safety_level,
            interception_model=interception_model,
        ))
    finally:
        # Taken off the instance, not set back to the bound method: set back,
        # it stays an attribute of this shared router and hides the class's
        # method from every later test in the process that replaces it there
        # (test_song_path_gate.py found the router silent after this file).
        del router.process_request

    assert backend.requests, "the interception never reached a backend"
    return result, backend.requests[-1]


# --------------------------------------------------------- which model runs it

class TestWhichModelRuns:
    def test_absent_runs_the_configured_model(self):
        _result, request = _intercept(interception_model=None)
        assert request.model == CONFIGURED

    def test_named_model_runs_this_request(self):
        _result, request = _intercept(interception_model=CHOSEN)
        assert request.model == CHOSEN

    def test_the_step_records_the_dispatched_id(self):
        """What the response reports as `interception_model` comes from here.

        The full id including its provider prefix, written down by the chunk
        builder at dispatch — and overwritten afterwards where the engine
        reports having reached somewhere else.
        """
        result, _request = _intercept(interception_model=CHOSEN)
        recorded = [s.metadata.get('final_model') for s in result.steps if s.metadata]
        assert CHOSEN in recorded

    def test_the_choice_lasts_one_request(self):
        """The config object is shared and cached; a run must not write into it."""
        _intercept(interception_model=CHOSEN)
        _result, request = _intercept(interception_model=None)
        assert request.model == CONFIGURED


# ------------------------------------------------------- and what must not move

class TestTheRestHoldsStill:
    def test_the_prompt_is_the_same_prompt(self):
        _r1, without = _intercept(interception_model=None)
        _r2, with_choice = _intercept(interception_model=CHOSEN)
        assert with_choice.prompt == without.prompt

    def test_the_kids_prefix_is_in_it(self):
        """Safety is unconditional: the prefix stands with a named model too."""
        _result, request = _intercept(interception_model=CHOSEN, safety_level="kids")
        assert KIDS_PREFIX in request.prompt

    def test_the_youth_prefix_is_in_it(self):
        _result, request = _intercept(interception_model=CHOSEN, safety_level="youth")
        assert "SAFETY (ages 14-18)" in request.prompt

    def test_the_input_text_is_in_it(self):
        _result, request = _intercept(interception_model=CHOSEN)
        assert HARMLESS in request.prompt

    def test_the_generation_parameters_are_the_same(self):
        _r1, without = _intercept(interception_model=None)
        _r2, with_choice = _intercept(interception_model=CHOSEN)
        assert with_choice.parameters == without.parameters


# --------------------------------------------------------------- the endpoint

@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    return app.test_client()


def _only_one_model_offered(monkeypatch):
    """The installation offers exactly one model, installed, and nothing else.

    The second part of the answer is the local station's reachability: False
    here means it answered, so a miss in this list is a genuine miss. The third
    is the register the list was read from, which the gate asks about the id's
    provider instead of reading the file a second time.
    """
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([{"id": CHOSEN, "label": "Some offered model",
                                   "available": True}], False, OFFERED_REGISTER))


@pytest.fixture
def offers(monkeypatch):
    _only_one_model_offered(monkeypatch)


@pytest.fixture
def stage1_waved_through(monkeypatch):
    """Stage 1 answers safe, and records that it was asked at all."""
    calls = []

    def _check(texts, level, lang):
        calls.append(texts)
        return (True, None, [], None, {'input_text': HARMLESS})

    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(R, "_stage1_check_texts", _check)
    return calls


@pytest.fixture
def captured_stage2(monkeypatch):
    """Stage 2 replaced by a recorder. Returns the dict it fills in."""
    seen = {}

    async def _capture(**kwargs):
        seen.update(kwargs)
        return R._ClassifierResult(success=True, final_output="done")

    monkeypatch.setattr(R, "execute_stage2_with_optimization", _capture)
    return seen


class TestTheEndpoint:
    def test_a_model_that_is_not_offered_is_refused(self, client, offers):
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': UNLISTED,
        })
        assert response.status_code == 400
        message = response.get_json()['error']
        assert UNLISTED in message, "the refusal must name the id it refused"
        assert "chat models" in message
        assert response.get_json()['cause'] == 'unknown_model'

    def test_the_refusal_names_no_second_cause(self, client, offers):
        """The status and the message carry the real reason, not a generic one."""
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': UNLISTED,
        })
        assert response.get_json()['success'] is False
        assert response.status_code == 400

    def test_an_offered_model_reaches_stage_2(self, client, offers,
                                              stage1_waved_through, captured_stage2):
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert captured_stage2.get('interception_model') == CHOSEN

    def test_without_the_field_stage_2_is_told_nothing(self, client,
                                                       stage1_waved_through, captured_stage2):
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert captured_stage2.get('interception_model') is None

    def test_the_safety_gate_still_stands(self, client, offers, monkeypatch):
        """A named model is not a way past Stage 1.

        The stimulus is the one test_86a_word_boundaries.py uses: at kids level
        it is a hard block, decided by the fast filter without any model call.
        """
        monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': BLOCKED,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 403
        assert response.get_json()['blocked_at_stage'] == 1


# ------------------------------------------------- what the field may contain

class TestTheFieldIsText:
    def test_a_number_is_refused_as_a_number(self, client, offers):
        """Not as a 500 carrying a Python type name."""
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': 123,
        })
        assert response.status_code == 400
        assert response.get_json()['error'] == 'interception_model must be a string'
        assert response.get_json()['cause'] == 'not_a_string'

    def test_a_list_is_refused_too(self, client, offers):
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': [CHOSEN],
        })
        assert response.status_code == 400
        assert response.get_json()['error'] == 'interception_model must be a string'
        assert response.get_json()['cause'] == 'not_a_string'

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_an_empty_value_counts_as_no_value(self, client, stage1_waved_through,
                                               captured_stage2, empty):
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': empty,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert captured_stage2.get('interception_model') is None


# --------------------------------------------- the four causes, four answers

class TestWhyTheModelCannotRun:
    def test_an_unreachable_local_service_is_an_outage_not_a_wrong_id(
            self, client, monkeypatch):
        """A list that could not be built proves nothing about the id in it.

        The local half of the list comes from a service on this machine. When it
        does not answer, every local id is missing from the list for a reason
        that has nothing to do with the id — and answering "not among the
        configured chat models" tells the person who picked a model that exists
        that they picked one that does not.
        """
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([], True, OFFERED_REGISTER))
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': UNLISTED,
        })
        assert response.status_code == 503
        message = response.get_json()['error']
        assert UNLISTED in message
        assert "cannot be verified" in message
        assert response.get_json()['cause'] == 'gpu_unreachable'

    def test_a_reachable_service_still_refuses_an_unknown_local_id(
            self, client, monkeypatch):
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([], False, OFFERED_REGISTER))
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': UNLISTED,
        })
        assert response.status_code == 400
        assert "chat models" in response.get_json()['error']

    def test_a_provider_without_a_key_says_so(self, client, monkeypatch):
        """The cloud half of the list holds every provider with a key. An id
        of a provider without one is absent from it by construction, which is
        a settings state, not a wrong id. (Until 2026-09-12 the list was the
        active provider's alone, and this said "not the active provider".)"""
        from my_app.services import llm_providers as lp
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([], False, OFFERED_REGISTER))
        monkeypatch.setattr(lp, "has_key", lambda name: False)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': "openai/a-model-of-a-provider-without-key",
        })
        assert response.status_code == 400
        message = response.get_json()['error']
        assert "openai" in message
        assert "API key" in message
        assert response.get_json()['cause'] == 'provider_without_key'

    def test_a_keyed_provider_without_an_entry_is_this_installations_repair(
            self, client, monkeypatch):
        """Nothing about the request is wrong, and no correction would help.

        A provider this installation holds a key for, with nothing recorded
        about it in the register: no id of that provider passes while this
        stands, so this is a state here, not a bad request.
        """
        from my_app.services import llm_providers as lp
        # The register comes back with the list, and this one carries nothing
        # about the provider the id names.
        monkeypatch.setattr(chat_routes, "list_chat_models", lambda: ([], False, {}))
        monkeypatch.setattr(lp, "has_key", lambda name: True)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': "openai/some-model",
        })
        assert response.status_code == 503
        message = response.get_json()['error']
        assert "model register" in message
        assert "openai" in message
        assert response.get_json()['cause'] == 'register_broken'

    def test_a_keyed_provider_with_an_entry_and_no_such_model_is_a_wrong_id(
            self, client, monkeypatch):
        """The register is asked about the provider the id names, and where
        it answers, an id that is not offered is a wrong id."""
        from my_app.services import llm_providers as lp
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([], False, {"llm_presets": {"openai": {"models": {}}}}))
        monkeypatch.setattr(lp, "has_key", lambda name: True)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': "openai/some-model",
        })
        assert response.status_code == 400
        assert "chat models" in response.get_json()['error']
        assert response.get_json()['cause'] == 'unknown_model'

    def test_a_service_the_table_does_not_carry_is_a_wrong_id(self, client, monkeypatch):
        monkeypatch.setattr(chat_routes, "list_chat_models", lambda: ([], False, {}))
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': "another-provider/some-model",
        })
        assert response.status_code == 400
        assert response.get_json()['cause'] == 'unknown_model'

    def test_a_bare_id_is_a_wrong_id_not_an_outage(self, client, monkeypatch):
        """A string with no prefix names no service.

        is_local() reads it as local, because that is how a ROLE SETTING may
        hold a local model -- but a request naming one is naming an id the list
        does not carry, and an installation without a local service would have
        answered a typo with an outage.
        """
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([], True, OFFERED_REGISTER))
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': BARE,
        })
        assert response.status_code == 400
        message = response.get_json()['error']
        assert BARE in message
        assert "chat models" in message

    def test_the_local_service_state_does_not_touch_a_cloud_id(self, client, monkeypatch):
        """A cloud id is not verified against the machine's own service."""
        from my_app.services import llm_providers as lp
        monkeypatch.setattr(lp, "has_key", lambda name: True)
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([], True, {'llm_presets': {'openai': {'models': {}}}}))
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': f"openai/{BARE}",
        })
        assert response.status_code == 400
        assert "chat models" in response.get_json()['error']

    def test_the_gate_reads_the_register_the_list_was_built_from(
            self, client, monkeypatch):
        """One read, one instant.

        The list and the register behind it decide the same answer together: an
        id is unknown, or its provider has no entry at all. Read a second time
        here, the register answers from a later state -- a settings save landing
        between the two pairs one state's ids with another's presets, and a
        cloud id whose entry stands is refused as an id of nothing.
        """
        from my_app.services import llm_providers as lp
        monkeypatch.setattr(lp, "has_key", lambda name: True)
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([], False, {'llm_presets': {'openai': {'models': {}}}}))

        def _a_second_read(*args, **kwargs):
            raise AssertionError("the gate read the register a second time")

        monkeypatch.setattr(settings_routes, "get_hardware_matrix", _a_second_read)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': "openai/a-model-that-is-not-offered",
        })
        assert response.status_code == 400
        assert response.get_json()['cause'] == 'unknown_model'

    def test_a_listed_model_that_was_never_installed_is_refused(self, client, monkeypatch):
        """Standing in the list is not standing on the disk.

        Every registered local alias is listed, installed or not, so that the
        picker can offer to install it. Membership alone would let an absent
        file through to the backend, where it dies as a 500 with the cause
        thrown away on the way back.
        """
        monkeypatch.setattr(chat_routes, "list_chat_models",
                            lambda: ([{"id": CHOSEN, "label": "Not installed",
                                       "available": False, "installable": True}],
                                     False, OFFERED_REGISTER))
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 409
        message = response.get_json()['error']
        assert CHOSEN in message
        assert "not installed" in message
        assert response.get_json()['cause'] == 'not_installed'


# ------------------------------------------- the gate stands before Stage 1

class TestTheGateComesFirst:
    def test_stage_1_is_not_asked_about_a_model_that_cannot_run(
            self, client, offers, stage1_waved_through):
        """A refused model costs no safety check and no model call.

        Stage 1 reaches a model of its own. A request that is going to be
        refused for its model must be refused before anything is spent on it.
        """
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': UNLISTED,
        })
        assert response.status_code == 400
        assert UNLISTED in response.get_json()['error']
        assert stage1_waved_through == [], "Stage 1 ran for a request that was refused"


# ------------------------------------- a preset that runs no interception step

class TestThePresetMustRunTheStep:
    def test_an_interception_preset_passes(self, client, offers,
                                           stage1_waved_through, captured_stage2):
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)

    def test_a_preset_that_skips_stage_2_is_refused(self, client, offers,
                                                    stage1_waved_through):
        """It would answer 200 and drop the model on the floor.

        Six presets build no chunk at all — the vector and latent instruments
        pass the prompt straight through, on purpose. A model named for a run
        that writes no interception has nothing to write.
        """
        R.init_schema_engine()
        assert R.pipeline_executor.config_loader.get_config(SKIP_STAGE2_SCHEMA), \
            f"the '{SKIP_STAGE2_SCHEMA}' config is not loadable"
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SKIP_STAGE2_SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 400
        assert "no interception step" in response.get_json()['error']
        assert response.get_json()['cause'] == 'no_interception_step'

    def test_a_plan_with_a_chunk_on_another_role_is_refused(
            self, client, offers, stage1_waved_through, monkeypatch):
        """The parameter names the interception step, not every step.

        A plan holding a second chunk on another model role would run that step
        on a model chosen for the interception — the translation written by the
        model the comparison was about.
        """
        R.init_schema_engine()
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        two_roles = replace(base, chunks=['manipulate', 'translate'])
        monkeypatch.setattr(R, "_resolve_interception_config", lambda name: two_roles)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 400
        message = response.get_json()['error']
        assert "translate" in message
        assert "interception step only" in message
        assert response.get_json()['cause'] == 'no_interception_step'

    def test_the_pre_check_path_is_refused(self, client, offers, stage1_waved_through):
        """It runs a classifier, not an interception. Nothing writes anything."""
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'skip_optimization': True,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 400
        assert "no interception step" in response.get_json()['error']
        assert response.get_json()['cause'] == 'no_interception_step'

    def test_the_pre_check_path_without_a_model_still_runs(
            self, client, stage1_waved_through, monkeypatch):
        """The refusal is about the model, not about the path."""
        async def _classifier(**kwargs):
            return R._ClassifierResult(success=True, final_output=HARMLESS)

        monkeypatch.setattr(R, "execute_stage2_classifier", _classifier)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'skip_optimization': True,
        })
        assert response.status_code == 200, response.get_data(as_text=True)


# --------------------------------------- what the response says about the run

@pytest.fixture
def stubbed_router():
    """The real Stage-2 path, with only the backend replaced.

    Returns a factory: call it with the id the engine should report having
    dispatched to, and the router is swapped for the length of the test.
    """
    R.init_schema_engine()
    router = R.pipeline_executor.backend_router
    made = []

    def _install(dispatched_model=None, contents=None):
        backend = _Backend(dispatched_model=dispatched_model, contents=contents)
        router.process_request = backend.process_request
        made.append(backend)
        return backend

    yield _install
    # Taken off the instance, as in _intercept above.
    if 'process_request' in vars(router):
        del router.process_request


@pytest.fixture
def wikipedia_says(monkeypatch):
    """The lookup service replaced by what it should answer.

    A factory: call it with the results, and it returns the stand-in, whose
    `asked` records the (term, language) pairs the executor actually asked for.
    What a lookup ANSWERS with is not what it was asked: the code is lowercased,
    one it does not serve is replaced, and the term comes back as the cache
    folded it.
    """
    from my_app.services import wikipedia_service as wiki_module

    class _Wikipedia:
        def __init__(self, results):
            self.results = results
            self.asked = []

        async def lookup_multiple(self, terms, max_lookups=5):
            self.asked.append(list(terms))
            return self.results

    def _install(results):
        service = _Wikipedia(results)
        monkeypatch.setattr(wiki_module, "get_wikipedia_service",
                            lambda **kwargs: service)
        return service

    return _install


class TestTheResponseIsTruthful:
    def test_the_dispatched_model_wins_over_the_requested_one(
            self, client, offers, stage1_waved_through, stubbed_router):
        """The frontend compares what it asked for against what ran.

        Which only says something while the second half is post-dispatch. The
        engine routes by its own rules and can reach a model other than the one
        named; a field written before the call would report the request back and
        every row would look like a match.
        """
        stubbed_router(dispatched_model=DISPATCHED)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['interception_model'] == DISPATCHED

    def test_without_a_dispatch_report_the_asked_for_model_stands(
            self, client, offers, stage1_waved_through, stubbed_router):
        stubbed_router(dispatched_model=None)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['interception_model'] == CHOSEN

    def test_the_lookups_travel_with_the_answer(self, client, stage1_waved_through,
                                                monkeypatch):
        """A text resting on retrieved articles is a different kind of text.

        Nothing in the text itself says so, so a reader laying two runs side by
        side has to be told rather than left to guess at the difference.
        """
        looked_up = [{'term': 'Bauhaus', 'lang': 'de', 'found': True},
                     {'term': 'Weimar', 'lang': 'en', 'found': False}]

        async def _looked_things_up(**kwargs):
            return R._ClassifierResult(
                success=True, final_output="done",
                metadata={'wikipedia_lookups': len(looked_up),
                          'wikipedia_terms': looked_up},
            )

        monkeypatch.setattr(R, "execute_stage2_with_optimization", _looked_things_up)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['wikipedia_lookups'] == 2
        assert body['wikipedia_terms'] == looked_up

    def test_a_run_without_lookups_says_so(self, client, stage1_waved_through,
                                           captured_stage2):
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['wikipedia_lookups'] == 0
        assert body['wikipedia_terms'] == []


# --------------------------------------------------------------- the adaption

class TestTheAdaptionKeepsItsModel:
    def test_the_adaption_runs_on_the_platform_model(
            self, client, offers, stage1_waved_through, stubbed_router, monkeypatch):
        """The media adaption runs on the platform's model for every row.

        A row whose adaption had also changed would say nothing about the
        interception: two variables moved and the reader cannot tell which one
        the difference belongs to. So the adaption is handed no model override
        at all, and falls to the configured one.
        """
        stubbed_router()
        adaptions = []

        async def _adapt(**kwargs):
            adaptions.append(kwargs)
            return "an adapted prompt"

        monkeypatch.setattr(R, "execute_optimization", _adapt)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'output_config': ADAPTION_OUTPUT_CONFIG,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert adaptions, (
            f"'{ADAPTION_OUTPUT_CONFIG}' carries an adaption instruction, so the "
            f"adaption must have run — without it this test asserts nothing")
        assert adaptions[0].get('model_override') is None, (
            "The media adaption was handed the chosen interception model. Then a "
            "comparison of interception models also compares adaptions, and the "
            "rows stop being comparable.")

    def test_the_interception_itself_did_run_on_the_choice(
            self, client, offers, stage1_waved_through, stubbed_router, monkeypatch):
        """The other half of the pair: the choice reaches the step it is for."""
        backend = stubbed_router()

        async def _adapt(**kwargs):
            return "an adapted prompt"

        monkeypatch.setattr(R, "execute_optimization", _adapt)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'output_config': ADAPTION_OUTPUT_CONFIG,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert backend.requests, "the interception never reached a backend"
        assert backend.requests[0].model == CHOSEN


# ------------------------------------------- where the text goes, per model id

class TestTheRecordedDataPath:
    def test_two_local_tiers_with_different_grounds_keep_both(self):
        """A status is shown with the grounds it was recorded on, all of them.

        'local' is not a provider and has no entry among the cloud presets; its
        grounds stand on the per-tier local presets. Picking one of several
        would show a sentence somebody did not write for this case, and showing
        none would leave a True flag standing on its own — the shape the
        register refuses everywhere else.
        """
        matrix = {
            'llm_presets': {},
            'local_llm_presets': {
                'vram_24': {'DSGVO_NOTE': 'First recorded ground.'},
                'vram_48': {'DSGVO_NOTE': 'Second recorded ground.'},
            },
        }
        state = settings_routes.data_path_of('local/any-model', matrix)
        assert state['service'] == 'local'
        assert state['dsgvo_recorded'] is True
        assert 'First recorded ground.' in state['dsgvo_note']
        assert 'Second recorded ground.' in state['dsgvo_note']

    def test_a_register_without_local_grounds_falls_back_to_the_shipped_one(self):
        state = settings_routes.data_path_of('local/any-model', {'llm_presets': {}})
        assert state['dsgvo_recorded'] is True
        assert state['dsgvo_note'], (
            "a recorded status without its grounds is a flag standing alone")

    def test_the_grounds_come_from_the_register_handed_in(self):
        """A caller holding the shipped register hands it in, and it is used.

        The live section is empty here, so the answer can only come from the
        second argument -- and if it came from a file read instead, the note
        would be that file's, from another instant.
        """
        live = {'llm_presets': {}, 'local_llm_presets': {}}
        shipped = {'local_llm_presets': {
            'vram_24': {'DSGVO_NOTE': 'The ground the caller handed in.'}}}
        state = settings_routes.data_path_of('local/any-model', live, shipped)
        assert state['dsgvo_note'] == 'The ground the caller handed in.'

    def test_a_local_model_with_no_grounds_anywhere_records_nothing(self):
        """A register with an empty local section and no shipped one to fall
        back on records nothing about a local model -- and nothing is the third
        state, not conform. A True flag with an empty note is the shape the
        register refuses for every other service: a status with nobody
        answering for it, and a surface drawing the mark from the flag alone
        shows it as recorded conform.
        """
        empty = {'llm_presets': {}, 'local_llm_presets': {}}
        state = settings_routes.data_path_of('local/any-model', empty, {})
        assert state['service'] == 'local'
        assert state['dsgvo_recorded'] is None
        assert state['dsgvo_note'] == ''

    def test_one_recorded_ground_is_enough_for_the_flag(self):
        """The other direction: with grounds, the flag stands -- on them."""
        matrix = {'llm_presets': {},
                  'local_llm_presets': {'vram_24': {'DSGVO_NOTE': 'The one ground.'}}}
        state = settings_routes.data_path_of('local/any-model', matrix, {})
        assert state['dsgvo_recorded'] is True
        assert state['dsgvo_note'] == 'The one ground.'

    def test_one_repeated_sentence_is_said_once(self):
        matrix = {
            'llm_presets': {},
            'local_llm_presets': {
                'vram_24': {'DSGVO_NOTE': 'The one recorded ground.'},
                'vram_48': {'DSGVO_NOTE': 'The one recorded ground.'},
            },
        }
        state = settings_routes.data_path_of('local/any-model', matrix)
        assert state['dsgvo_note'] == 'The one recorded ground.'


# ------------------------------------- the engine names the branch that ran

@pytest.fixture
def offline_model_lists(monkeypatch):
    """No model list is fetched over the network in these tests.

    process_request refreshes both lists on every call, and the local one is a
    request to the service on this machine.
    """
    monkeypatch.setattr(engine_module.model_selector, "get_local_models", lambda: [])
    monkeypatch.setattr(engine_module.model_selector, "get_openrouter_models", lambda: [])


def _run_engine(engine, model):
    return asyncio.run(engine.process_request(engine_module.PromptInterceptionRequest(
        input_prompt="", prebuilt_prompt="a prompt", model=model,
    )))


class TestTheEngineNamesTheBranchThatRan:
    def test_a_local_call_is_reported_with_its_service(self, offline_model_lists,
                                                       monkeypatch):
        engine = engine_module.PromptInterceptionEngine()

        async def _local(prompt, model, debug, unload_model, parameters=None):
            return "an intercepted text", model

        monkeypatch.setattr(engine, "_call_local_llm", _local)
        response = _run_engine(engine, "local/a-model:9b")
        assert response.success
        # The two are different strings on purpose: one names a model, the other
        # names a model AND where it ran.
        assert response.model_used == "a-model:9b"
        assert response.dispatched_model == "local/a-model:9b"

    def test_a_bare_name_in_the_live_local_list_reports_local(self, monkeypatch):
        """The first branch is entered on the list, not only on the prefix.

        So a string that looks like no service at all can still have run on this
        machine, and the answer has to say so.
        """
        monkeypatch.setattr(engine_module.model_selector, "get_local_models",
                            lambda: ["a-bare-name:9b"])
        monkeypatch.setattr(engine_module.model_selector, "get_openrouter_models",
                            lambda: [])
        engine = engine_module.PromptInterceptionEngine()

        async def _local(prompt, model, debug, unload_model, parameters=None):
            return "an intercepted text", model

        monkeypatch.setattr(engine, "_call_local_llm", _local)
        response = _run_engine(engine, "a-bare-name:9b")
        assert response.dispatched_model == "local/a-bare-name:9b"

    def test_a_cloud_branch_hands_back_the_path_and_the_service_goes_in_front_once(
            self, offline_model_lists, monkeypatch):
        """The cloud branch is asked for the provider's own path and hands it
        back; the id that is recorded carries the service exactly once. (Until
        2026-09-12 one branch handed its name back with the prefix still on it,
        and this test held that it was not prefixed twice.)"""
        engine = engine_module.PromptInterceptionEngine()
        seen = []

        async def _cloud(provider, prompt, model, debug, parameters=None, usage_stage="stage2"):
            seen.append((provider, model))
            return "an intercepted text", model

        monkeypatch.setattr(engine, "_call_cloud", _cloud)
        response = _run_engine(engine, "mammouth/a-model")
        assert seen == [("mammouth", "a-model")]
        assert response.dispatched_model == "mammouth/a-model"

    def test_a_tag_the_register_appends_never_reaches_the_provider(
            self, offline_model_lists, monkeypatch):
        """The model register may write ' [tag]' after an id. The extractor
        cuts it off, and the cloud branch asks for the extractor's path; sliced
        off the raw id, the tag went to the provider (a 400 there)."""
        engine = engine_module.PromptInterceptionEngine()
        seen = []

        async def _cloud(provider, prompt, model, debug, parameters=None, usage_stage="stage2"):
            seen.append((provider, model))
            return "an intercepted text", model

        monkeypatch.setattr(engine, "_call_cloud", _cloud)
        response = _run_engine(engine, "mammouth/a-model [free]")
        assert seen == [("mammouth", "a-model")]
        assert response.dispatched_model == "mammouth/a-model"

    def test_an_unknown_format_reports_nothing(self, offline_model_lists):
        engine = engine_module.PromptInterceptionEngine()
        response = _run_engine(engine, "no-such-service/a-model")
        assert response.success is False
        assert response.dispatched_model is None


class TestTheRouterCarriesIt:
    def test_the_dispatched_id_reaches_the_step_metadata(self, monkeypatch):
        """Between the engine and the endpoint stands exactly this hand-over."""

        class _StubEngine:
            async def process_request(self, request):
                return engine_module.PromptInterceptionResponse(
                    output_str="an intercepted text", output_float=0.0, output_int=0,
                    output_binary=False, success=True,
                    model_used="the-name-the-backend-reports",
                    dispatched_model=DISPATCHED,
                )

        monkeypatch.setattr(engine_module, "PromptInterceptionEngine", _StubEngine)
        response = asyncio.run(BackendRouter()._process_prompt_interception_request(
            BackendRequest(backend_type=BackendType.LOCAL_LLM, model=CHOSEN,
                           prompt="a prompt", parameters={})))
        assert response.success
        assert response.metadata['dispatched_model'] == DISPATCHED
        # Additive: the two fields that were there keep what they meant.
        assert response.metadata['model_used'] == "the-name-the-backend-reports"
        assert response.metadata['backend_type'] == BackendType.LOCAL_LLM.value


# ------------------------------------------ a preset whose model is not free

class TestThePresetsOwnModel:
    """A preset can carry a model of its own, and then it is not the request's.

    The per-request model is set through the same meta.model_override the
    chunk builder reads, so a request naming one silently replaced the preset's
    pin. One shipped preset is pinned to the guard model that reads the
    visitor's text without leaving this machine; its prompt, with that text in
    it, would have gone wherever the request pointed.
    """

    def test_a_bound_preset_is_refused(self, client, offers, stage1_waved_through,
                                       monkeypatch):
        R.init_schema_engine()
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        bound = replace(base, meta={**(base.meta or {}), 'model_override': PINNED})
        monkeypatch.setattr(R, "_resolve_interception_config", lambda name: bound)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 400
        message = response.get_json()['error']
        assert "binds its own model" in message
        assert SCHEMA in message
        assert response.get_json()['cause'] == 'preset_binds_model'
        assert stage1_waved_through == [], "Stage 1 ran for a request that was refused"

    def test_a_preset_of_another_stage_is_refused(self, client, offers,
                                                  stage1_waved_through, monkeypatch):
        R.init_schema_engine()
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        elsewhere = replace(base, meta={**(base.meta or {}), 'stage': 'pre_interception'})
        monkeypatch.setattr(R, "_resolve_interception_config", lambda name: elsewhere)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 400
        assert "is not an interception preset" in response.get_json()['error']
        assert response.get_json()['cause'] == 'not_interception_preset'

    def test_a_preset_that_says_nothing_about_its_stage_still_passes(
            self, client, offers, stage1_waved_through, captured_stage2, monkeypatch):
        """Four shipped presets name no stage. Silence is not another stage."""
        R.init_schema_engine()
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        silent = replace(base, meta={k: v for k, v in (base.meta or {}).items()
                                     if k != 'stage'})
        monkeypatch.setattr(R, "_resolve_interception_config", lambda name: silent)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)

    def test_the_shipped_guard_preset_is_refused_through_the_resolver(
            self, client, offers, stage1_waved_through):
        """Not a fabricated object: the file, through the route's own resolver."""
        R.init_schema_engine()
        guard = R.pipeline_executor.config_loader.get_config(GUARD_SCHEMA)
        if guard is None or not (getattr(guard, 'meta', None) or {}).get('model_override'):
            pytest.skip(f"'{GUARD_SCHEMA}' is not a model-bound preset in this worktree")
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': GUARD_SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 400
        message = response.get_json()['error']
        assert GUARD_SCHEMA in message
        assert "binds its own model" in message
        assert response.get_json()['cause'] == 'preset_binds_model'
        assert stage1_waved_through == [], "Stage 1 ran for a request that was refused"


# ---------------------------------------- a run that writes no interception

class TestTheRunHasToWriteSomething:
    def test_a_pipeline_that_skips_stage_2_is_refused(self, client, offers,
                                                      stage1_waved_through, monkeypatch):
        """The flag is the pipeline's; the value that decides is the effective one."""
        R.init_schema_engine()
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        skipping = replace(base, pipeline_name=SKIP_STAGE2_PIPELINE, chunks=['manipulate'])
        assert R.pipeline_executor.config_loader.get_pipeline(SKIP_STAGE2_PIPELINE), \
            f"the '{SKIP_STAGE2_PIPELINE}' pipeline is not loadable"
        monkeypatch.setattr(R, "_resolve_interception_config", lambda name: skipping)
        monkeypatch.setattr(R, "resolve_safety_level", lambda: "open")
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 400
        assert "no interception step" in response.get_json()['error']
        assert response.get_json()['cause'] == 'no_interception_step'

    def test_the_same_pipeline_runs_the_step_for_kids(self, client, offers,
                                                      stage1_waved_through,
                                                      captured_stage2, monkeypatch):
        """Kids and youth override the flag, and then the step DOES run.

        A guard reading the raw flag would refuse exactly the runs where the
        interception is mandatory.
        """
        R.init_schema_engine()
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        skipping = replace(base, pipeline_name=SKIP_STAGE2_PIPELINE, chunks=['manipulate'])
        monkeypatch.setattr(R, "_resolve_interception_config", lambda name: skipping)
        monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert captured_stage2.get('interception_model') == CHOSEN

    def test_a_preset_that_may_hand_the_input_back_is_not_refused(
            self, client, offers, stage1_waved_through, captured_stage2):
        """"Your Call!" is where the comparison has the most to show.

        Whether the prompt comes back unchanged is decided by what the model
        reaches for while it writes: the preset researches, and a run that
        looked something up wrote a text of its own. Refused in advance, the
        request that would have shown that difference was the one turned away --
        with a sentence that is false for it.
        """
        R.init_schema_engine()
        assert R.pipeline_executor.config_loader.get_config(PASSTHROUGH_SCHEMA), \
            f"the '{PASSTHROUGH_SCHEMA}' config is not loadable"
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': PASSTHROUGH_SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert captured_stage2.get('interception_model') == CHOSEN

    def test_the_same_preset_with_a_context_is_an_interception(
            self, client, offers, stage1_waved_through, captured_stage2):
        """A context in the request is something to write with, so it passes."""
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': PASSTHROUGH_SCHEMA, 'input_text': HARMLESS,
            'context_prompt': 'Write it as a field note.',
            'context_language': 'en',
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert captured_stage2.get('interception_model') == CHOSEN


# ------------------------------- a chunk this installation could not load

class TestAChunkTemplateThatWouldNotLoad:
    def test_a_missing_template_is_a_state_of_this_installation(
            self, client, offers, stage1_waved_through, monkeypatch):
        """Skipped, it read as a preset that runs no interception step.

        Which is said about the preset -- and the preset is whole; a file is
        missing here. The person was told to choose another perspective for
        something no perspective reaches, and the plan behind the answer was one
        chunk short of the plan that would have run.
        """
        R.init_schema_engine()
        assert MISSING_CHUNK not in R.pipeline_executor.chunk_builder.templates, \
            "the point of this test is a chunk name nothing answers to"
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        incomplete = replace(base, chunks=[MISSING_CHUNK])
        monkeypatch.setattr(R, "_resolve_interception_config", lambda name: incomplete)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 503
        message = response.get_json()['error']
        assert MISSING_CHUNK in message, "the answer names the template it wanted"
        assert "could not be loaded" in message
        assert response.get_json()['cause'] == 'chunk_template_missing'
        assert stage1_waved_through == [], "Stage 1 ran for a request that was refused"


# --------------------------------- every way of being refused, one word each

def _cause_not_a_string(monkeypatch):
    _only_one_model_offered(monkeypatch)
    return {'interception_model': 123}


def _cause_unknown_model(monkeypatch):
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([], False, OFFERED_REGISTER))
    return {'interception_model': UNLISTED}


def _cause_provider_without_key(monkeypatch):
    from my_app.services import llm_providers as lp
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([], False, OFFERED_REGISTER))
    monkeypatch.setattr(lp, "has_key", lambda name: False)
    return {'interception_model': "openai/a-model-of-a-provider-without-key"}


def _cause_not_installed(monkeypatch):
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([{"id": CHOSEN, "label": "Not installed",
                                   "available": False, "installable": True}],
                                 False, OFFERED_REGISTER))
    return {'interception_model': CHOSEN}


def _cause_preset_binds_model(monkeypatch):
    _only_one_model_offered(monkeypatch)
    R.init_schema_engine()
    base = R.pipeline_executor.config_loader.get_config(SCHEMA)
    bound = replace(base, meta={**(base.meta or {}), 'model_override': PINNED})
    monkeypatch.setattr(R, "_resolve_interception_config", lambda name: bound)
    return {'interception_model': CHOSEN}


def _cause_not_interception_preset(monkeypatch):
    _only_one_model_offered(monkeypatch)
    R.init_schema_engine()
    base = R.pipeline_executor.config_loader.get_config(SCHEMA)
    elsewhere = replace(base, meta={**(base.meta or {}), 'stage': 'pre_interception'})
    monkeypatch.setattr(R, "_resolve_interception_config", lambda name: elsewhere)
    return {'interception_model': CHOSEN}


def _cause_no_interception_step_precheck(monkeypatch):
    _only_one_model_offered(monkeypatch)
    return {'interception_model': CHOSEN, 'skip_optimization': True}


def _cause_no_interception_step_pipeline(monkeypatch):
    _only_one_model_offered(monkeypatch)
    R.init_schema_engine()
    base = R.pipeline_executor.config_loader.get_config(SCHEMA)
    skipping = replace(base, pipeline_name=SKIP_STAGE2_PIPELINE, chunks=['manipulate'])
    monkeypatch.setattr(R, "_resolve_interception_config", lambda name: skipping)
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "open")
    return {'interception_model': CHOSEN}


def _cause_no_interception_step_plan(monkeypatch):
    _only_one_model_offered(monkeypatch)
    R.init_schema_engine()
    base = R.pipeline_executor.config_loader.get_config(SCHEMA)
    two_roles = replace(base, chunks=['manipulate', 'translate'])
    monkeypatch.setattr(R, "_resolve_interception_config", lambda name: two_roles)
    return {'interception_model': CHOSEN}


def _cause_chunk_template_missing(monkeypatch):
    _only_one_model_offered(monkeypatch)
    R.init_schema_engine()
    base = R.pipeline_executor.config_loader.get_config(SCHEMA)
    incomplete = replace(base, chunks=[MISSING_CHUNK])
    monkeypatch.setattr(R, "_resolve_interception_config", lambda name: incomplete)
    return {'interception_model': CHOSEN}


def _cause_gpu_unreachable(monkeypatch):
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([], True, OFFERED_REGISTER))
    return {'interception_model': UNLISTED}


def _cause_register_broken(monkeypatch):
    from my_app.services import llm_providers as lp
    monkeypatch.setattr(chat_routes, "list_chat_models", lambda: ([], False, {}))
    monkeypatch.setattr(lp, "has_key", lambda name: True)
    return {'interception_model': "openai/some-model"}


# Every path that refuses: what has to be true for it, the status it answers
# with, and the word it names itself by. Three of them are the same word --
# a pre-check request, a pipeline that skips the step and a plan that builds
# no interception chunk all leave the caller with the same thing to do.
REFUSAL_PATHS = [
    ('not_a_string', 400, _cause_not_a_string),
    ('unknown_model', 400, _cause_unknown_model),
    ('provider_without_key', 400, _cause_provider_without_key),
    ('not_installed', 409, _cause_not_installed),
    ('preset_binds_model', 400, _cause_preset_binds_model),
    ('not_interception_preset', 400, _cause_not_interception_preset),
    ('no_interception_step', 400, _cause_no_interception_step_precheck),
    ('no_interception_step', 400, _cause_no_interception_step_pipeline),
    ('no_interception_step', 400, _cause_no_interception_step_plan),
    ('chunk_template_missing', 503, _cause_chunk_template_missing),
    ('gpu_unreachable', 503, _cause_gpu_unreachable),
    ('register_broken', 503, _cause_register_broken),
]


class TestEveryRefusalNamesItsCause:
    """No refusal leaves the caller with nothing but a sentence to parse.

    The tests above check one path each, in the words that path uses. This one
    walks all of them and asks the same two questions of every answer: is there
    a cause, and is it one the picker knows.
    """

    @pytest.mark.parametrize(
        "expected_cause,expected_status,setup", REFUSAL_PATHS,
        ids=[f.__name__[len('_cause_'):] for _c, _s, f in REFUSAL_PATHS])
    def test_the_answer_carries_a_known_cause(
            self, client, monkeypatch, stage1_waved_through,
            expected_cause, expected_status, setup):
        payload = setup(monkeypatch)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS, **payload,
        })
        assert response.status_code == expected_status, response.get_data(as_text=True)
        body = response.get_json()
        assert body['success'] is False
        assert body.get('cause') in R.INTERCEPTION_REFUSAL_CAUSES, \
            f"the answer named {body.get('cause')!r}, which nothing can read"
        assert body['cause'] == expected_cause
        assert body['error'], "the sentence stands beside the cause, not instead of it"
        assert stage1_waved_through == [], "Stage 1 ran for a request that was refused"

    def test_the_list_of_causes_is_the_list_of_paths(self):
        """Both directions: no word without a path, no path without a word.

        A word nothing can produce is one the picker branches on and never
        reaches; a path that grows a word of its own without a row here is one
        the picker cannot read.
        """
        assert {cause for cause, _s, _f in REFUSAL_PATHS} == \
            set(R.INTERCEPTION_REFUSAL_CAUSES)


# ------------------------------------------------- the queue this call stands in

class TestTheQueue:
    def test_the_stage_2_call_is_held_in_the_queue(self, client, offers,
                                                   stage1_waved_through, monkeypatch):
        """Every other entry point to a Stage-2 model call queues; so does this."""
        gate = _CountingGate()
        held = []

        async def _capture(**kwargs):
            held.append(gate.depth)
            return R._ClassifierResult(success=True, final_output="done")

        monkeypatch.setattr(R, "llm_queue_semaphore", gate)
        monkeypatch.setattr(R, "execute_stage2_with_optimization", _capture)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert held == [1], "the Stage-2 call ran outside the queue"
        assert gate.entered == 1
        assert gate.max_depth == 1, "the queue was entered twice in one request"
        assert gate.depth == 0, "the queue was not released"


# ------------------------------------- what the model looked up, as it happened

class TestTheLookupsAreRecorded:
    def test_a_run_through_the_executor_reports_what_it_looked_up(
            self, client, stage1_waved_through, stubbed_router, wikipedia_says):
        """Not a mocked result handed to the endpoint: the executor's own record.

        The model emits markers, the lookup runs, and the second pass writes with
        what came back. What the response says about that is written here.
        """
        from my_app.services.wikipedia_service import WikipediaResult

        wikipedia_says([
            WikipediaResult(term='Bauhaus', language='de', title='Bauhaus',
                            extract='A school.', url='https://example.invalid/1',
                            success=True),
            WikipediaResult(term='Weimar', language='en', title='', extract='',
                            url='', success=False, error='nothing came back'),
        ])
        stubbed_router(contents=[
            'a first answer with <wiki lang="de">Bauhaus</wiki> and '
            '<wiki lang="en">Weimar</wiki> in it',
            'the text it wrote with what it found',
        ])
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['wikipedia_terms'] == [
            {'term': 'Bauhaus', 'lang': 'de', 'found': True},
            {'term': 'Weimar', 'lang': 'en', 'found': False},
        ]
        assert body['wikipedia_lookups'] == len(body['wikipedia_terms'])

    def test_the_recursive_path_reports_them_too(self):
        """A second success return, which used to carry neither field.

        A run through it looked exactly like a run that had looked nothing up.
        """
        R.init_schema_engine()
        base = R.pipeline_executor.config_loader.get_config(SCHEMA)
        recursive = replace(
            base,
            pipeline_name='text_transformation_recursive',
            parameters={'iterations': 2, 'use_random_languages': False,
                        'languages': ['de', 'en'], 'final_language': 'en'},
        )
        looked_up = [{'term': 'Bauhaus', 'lang': 'de', 'found': True},
                     {'term': 'Weimar', 'lang': 'en', 'found': False}]
        context = PipelineContext(input_text=HARMLESS, user_input=HARMLESS)
        context.wikipedia['terms'] = looked_up

        async def _step(step, ctx, tracker=None, **kwargs):
            return "an intercepted text"

        executor = R.pipeline_executor
        original = executor._execute_single_step
        executor._execute_single_step = _step
        try:
            result = asyncio.run(executor._execute_recursive_pipeline_steps(
                SCHEMA, [PipelineStep(step_id='loop', chunk_name='manipulate')],
                context, resolved_config=recursive, safety_level='open',
            ))
        finally:
            executor._execute_single_step = original

        assert result.success
        assert result.metadata['wikipedia_terms'] == looked_up
        assert result.metadata['wikipedia_lookups'] == 2

    def test_one_term_in_two_languages_is_two_entries(
            self, client, stage1_waved_through, stubbed_router, wikipedia_says):
        """Two asks, two HTTP lookups -- and, recorded from the results, one entry.

        lookup() lowercases the code and puts its fallback in place of one it
        does not serve, so both answers came back saying the same language and
        the second entry was dropped as a duplicate of the first. What is
        recorded is the ask: the term as the model wrote it, the language it
        asked in.
        """
        from my_app.services.wikipedia_service import WikipediaResult

        service = wikipedia_says([
            # What the lookup ANSWERS with: the cache's folded title as the term,
            # and the language the service resolved to for both asks.
            WikipediaResult(term='Bauhaus (Kunstschule)', language='de',
                            title='Bauhaus', extract='A school.',
                            url='https://example.invalid/1', success=True),
            WikipediaResult(term='Bauhaus (Kunstschule)', language='de',
                            title='', extract='', url='', success=False,
                            error='nothing came back'),
        ])
        stubbed_router(contents=[
            'a first answer with <wiki lang="de">Bauhaus</wiki> and '
            '<wiki lang="xx">Bauhaus</wiki> in it',
            'the text it wrote with what it found',
        ])
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert service.asked == [[('Bauhaus', 'de'), ('Bauhaus', 'xx')]], (
            "both asks have to reach the lookup, or this proves nothing")
        assert body['wikipedia_terms'] == [
            {'term': 'Bauhaus', 'lang': 'de', 'found': True},
            {'term': 'Bauhaus', 'lang': 'xx', 'found': False},
        ]
        assert body['wikipedia_lookups'] == 2

    def test_the_same_term_written_twice_is_one_entry(
            self, client, stage1_waved_through, stubbed_router, wikipedia_says):
        """One ask: the second marker is the first one again, in other letters.

        The record and the fetch normalise the pair the same way, so what the
        one skips the other does not count.
        """
        from my_app.services.wikipedia_service import WikipediaResult

        service = wikipedia_says([
            WikipediaResult(term='Bauhaus', language='de', title='Bauhaus',
                            extract='A school.', url='https://example.invalid/1',
                            success=True),
        ])
        stubbed_router(contents=[
            'a first answer with <wiki lang="de">Bauhaus</wiki> and '
            '<wiki lang="de">bauhaus</wiki> in it',
            'the text it wrote with what it found',
        ])
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert service.asked == [[('Bauhaus', 'de')]]
        assert body['wikipedia_terms'] == [
            {'term': 'Bauhaus', 'lang': 'de', 'found': True},
        ]
        assert body['wikipedia_lookups'] == 1

    def test_a_lookup_that_came_back_with_nothing_says_so(
            self, client, stage1_waved_through, stubbed_router, wikipedia_says):
        """An ask that found no article is still an ask, and it is marked."""
        from my_app.services.wikipedia_service import WikipediaResult

        wikipedia_says([
            WikipediaResult(term='Weimar', language='en', title='', extract='',
                            url='', success=False, error='nothing came back'),
        ])
        stubbed_router(contents=[
            'a first answer with <wiki lang="en">Weimar</wiki> in it',
            'the text it wrote without it',
        ])
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['wikipedia_terms'] == [
            {'term': 'Weimar', 'lang': 'en', 'found': False},
        ]

    def test_the_model_cannot_write_the_record_of_its_own_research(
            self, client, offers, stage1_waved_through, stubbed_router):
        """Every step's output is JSON-parsed into custom_placeholders, key by key.

        With the record living in that dict, a model answering with the key
        wrote it: the run reported a lookup that never happened, and the preset
        that owes the user their prompt back kept the model's text instead --
        decided by the model whose text it was.
        """
        stubbed_router(dispatched_model=DISPATCHED, contents=[
            '{"_wikipedia_fetched_terms": [{"term": "Bauhaus", "lang": "de", '
            '"found": true}], "text": "a text the model wrote"}',
        ])
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': PASSTHROUGH_SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['wikipedia_lookups'] == 0
        assert body['wikipedia_terms'] == []
        assert body['passthrough'] is True
        assert body['interception_result'] == HARMLESS

    def test_the_bookkeeping_does_not_travel_into_the_next_request(
            self, client, stage1_waved_through, stubbed_router, wikipedia_says):
        """Every custom placeholder is injected into every chunk's parameters.

        So a record kept there was sent to the model along with the text, in the
        very request whose answer it was supposed to describe.
        """
        from my_app.services.wikipedia_service import WikipediaResult

        wikipedia_says([
            WikipediaResult(term='Bauhaus', language='de', title='Bauhaus',
                            extract='A school.', url='https://example.invalid/1',
                            success=True),
        ])
        backend = stubbed_router(contents=[
            'a first answer with <wiki lang="de">Bauhaus</wiki> in it',
            'the text it wrote with what it found',
        ])
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert len(backend.requests) == 2, "the second pass never ran"
        for request in backend.requests:
            carried = [k for k in request.parameters
                       if k.upper().startswith('_WIKIPEDIA')]
            assert carried == [], carried


# --------------------------- the run that hands the input back says that it did

class TestThePassthroughIsSaidInTheAnswer:
    """A row of a comparison that hands the input back carries the user's own
    wording next to the id of a model that wrote none of it. Nothing in the text
    says so -- so the answer does, and a reader is not left reading N identical
    rows as a finding about N models.
    """

    def test_a_run_that_looked_nothing_up_hands_the_input_back(
            self, client, offers, stage1_waved_through, stubbed_router):
        stubbed_router(dispatched_model=DISPATCHED)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': PASSTHROUGH_SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['passthrough'] is True
        assert body['interception_result'] == HARMLESS, (
            "the prompt is owed back as it was written")
        assert body['interception_model'] == DISPATCHED, (
            "the model that was asked is named -- beside a text it did not write")

    def test_a_run_that_looked_something_up_keeps_what_it_wrote(
            self, client, offers, stage1_waved_through, stubbed_router,
            wikipedia_says):
        """The same preset, the same request, and a model that went looking.

        What it wrote with the article it found is the answer; that is the whole
        point of looking anything up.
        """
        from my_app.services.wikipedia_service import WikipediaResult

        wikipedia_says([
            WikipediaResult(term='Oriki', language='yo', title='Oriki',
                            extract='A praise poem.',
                            url='https://example.invalid/2', success=True),
        ])
        stubbed_router(dispatched_model=DISPATCHED, contents=[
            'a first answer with <wiki lang="yo">Oriki</wiki> in it',
            'the text it wrote with what it found',
        ])
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': PASSTHROUGH_SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['passthrough'] is False
        assert body['interception_result'] == 'the text it wrote with what it found'
        assert body['wikipedia_lookups'] == 1

    def test_with_an_output_config_the_answer_carries_input_and_adaption(
            self, client, offers, stage1_waved_through, stubbed_router, monkeypatch):
        """passthrough is the INTERCEPTION step's answer, not the whole run's.

        Where an output_config is named, the adaption runs on what the
        interception handed on -- here the input as written -- and
        stage2_result is what it made of it. Read as "stage2_result is the
        input", the flag is false on exactly this path: the two fields are
        different strings, and it is interception_result that carries the input.
        """
        adapted = "an adapted prompt"
        stubbed_router(dispatched_model=DISPATCHED)

        async def _adapt(**kwargs):
            return adapted

        monkeypatch.setattr(R, "execute_optimization", _adapt)
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': PASSTHROUGH_SCHEMA, 'input_text': HARMLESS,
            'output_config': ADAPTION_OUTPUT_CONFIG,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['passthrough'] is True
        assert body['interception_result'] == HARMLESS, (
            "the input as written is what the interception handed back")
        assert body['optimized_prompt'] == adapted
        assert body['stage2_result'] == body['optimized_prompt'], (
            "stage2_result is the adaption here, not the input")

    def test_a_preset_that_owes_nothing_says_so_too(
            self, client, offers, stage1_waved_through, stubbed_router):
        """The field stands on every answer, not only where it is true."""
        stubbed_router()
        response = client.post('/api/schema/pipeline/stage2', json={
            'schema': SCHEMA, 'input_text': HARMLESS,
            'interception_model': CHOSEN,
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['passthrough'] is False


# ------------------------------- the metadata /pipeline/execute hands onward

class TestTheResultObjectsMetadata:
    def test_it_carries_the_full_dispatched_id(self, stubbed_router):
        """/pipeline/execute answers with this object's metadata verbatim.

        So the key has to mean there what the stage2 endpoint's field of the
        same name means: the model AND the service it ran on, not the name the
        backend reports once the prefix has been stripped off.
        """
        stubbed_router(dispatched_model=DISPATCHED)
        result = asyncio.run(R.execute_stage2_with_optimization(
            schema_name=SCHEMA,
            input_text=HARMLESS,
            config=R.pipeline_executor.config_loader.get_config(SCHEMA),
            safety_level="kids",
            interception_model=CHOSEN,
        ))
        assert result.metadata['interception_model'] == DISPATCHED
        assert 'interception_model_name' not in result.metadata


# ------------------------------------ one unreadable entry costs only itself

class TestTheModelListSurvivesOneBadEntry:
    def test_every_entry_keeps_the_three_keys(self, monkeypatch):
        """One list, one shape.

        The marks used to be derived under a single try around the loop: an
        entry that raised took the fields off every entry after it while the
        ones before kept theirs, and nothing in the list said which was which.
        """
        entries = [{"id": f"{PROVIDER}/first-model", "label": "First", "available": True},
                   {"id": f"{PROVIDER}/second-model", "label": "Second", "available": True}]
        monkeypatch.setattr(chat_routes, "_cloud_chat_models_from_matrix",
                            lambda matrix, **_: [dict(e) for e in entries])

        def _no_local_table(*args, **kwargs):
            raise RuntimeError("the table of local models is not read in a test")

        from my_app.services import local_llm_weights
        monkeypatch.setattr(local_llm_weights, "chat_models", _no_local_table)

        recorded = settings_routes.data_path_of

        def _raises_for_the_first(model_string, matrix=None, defaults=None):
            if model_string.endswith("first-model"):
                raise RuntimeError("the register could not be read for this one")
            return recorded(model_string, matrix, defaults)

        monkeypatch.setattr(settings_routes, "data_path_of", _raises_for_the_first)

        models, _unreachable, _register = chat_routes.list_chat_models()
        assert len(models) == 2
        for entry in models:
            assert set(entry) >= {'service', 'dsgvo_recorded', 'dsgvo_note'}, entry
        # The one that failed says nothing rather than nothing at all: the third
        # state claims neither conformity nor its opposite.
        assert models[0]['dsgvo_recorded'] is None
        assert models[0]['dsgvo_note'] == ''
        assert models[0]['service'] == PROVIDER


# --------------------------- the shipped register is read once for the list

class TestTheShippedRegisterIsReadOnce:
    """One list, one read. Asked per model it was a file read per model."""

    @pytest.mark.parametrize("answer", [
        ({'local_llm_presets': {}}, None),
        # An unreadable one is read once too: handed on as None it sent every
        # model back to the same missing file, and nothing said it was missing.
        (None, "Missing hardware_matrix.defaults.json"),
    ])
    def test_it_is_read_once_however_many_models_there_are(self, monkeypatch, answer):
        reads = []

        def _counted():
            reads.append(1)
            return answer

        # The local half of the list is the table of local models
        # (services/local_llm_weights, since stage 3 of the move to ComfyUI).
        from my_app.services import local_llm_weights
        monkeypatch.setattr(local_llm_weights, "chat_models", lambda: [
            {"id": "first-local", "display_name": "First", "available": True,
             "installable": True, "approx_download_mb": 1},
            {"id": "second-local", "display_name": "Second", "available": True,
             "installable": True, "approx_download_mb": 1},
        ])

        monkeypatch.setattr(settings_routes, "load_default_hardware_matrix", _counted)
        monkeypatch.setattr(settings_routes, "get_hardware_matrix",
                            lambda: {'llm_presets': {}, 'local_llm_presets': {}})
        monkeypatch.setattr(chat_routes, "_cloud_chat_models_from_matrix",
                            lambda matrix, **_: [])

        models, unreachable, register = chat_routes.list_chat_models()
        assert unreachable is False
        assert len(models) == 2, models
        assert register == {'llm_presets': {}, 'local_llm_presets': {}}, (
            "the third part of the answer is the register this list was read "
            "from -- a caller taking it instead of reading the file reads no "
            "later state")
        assert len(reads) == 1, (
            f"the shipped register was read {len(reads)} times for {len(models)} models")


# ------------------------------- the picker offers what this installation runs

class TestThePickerOffersOnlyTheRoleModels:
    """A fallback is not an offer.

    `chat_fallback_models` names what a failed call reaches for next, and it
    holds the previous generation on purpose. Read into the picker it put that
    generation on screen beside its own successor -- two versions of the same
    model with nothing saying why either is there, and one of them a model this
    installation had already moved past.
    """

    MATRIX = {"llm_presets": {"aprovider": {
        "models": {
            "STAGE1_TEXT_MODEL": "aprovider/current-writer",
            "STAGE2_INTERCEPTION_MODEL": "aprovider/current-writer",
            "STAGE3_MODEL": "aprovider/current-checker",
        },
        "chat_fallback_models": ["older-writer", "older-checker"],
    }}}

    def _offered(self, monkeypatch):
        # The list walks the provider table's keyed providers (2026-09-12);
        # this one is the whole table, with a key and no reach entry, so what
        # is offered is what its cells say.
        monkeypatch.setattr(chat_routes, "provider_names", lambda dialect=None: ["aprovider"])
        monkeypatch.setattr(chat_routes, "has_key", lambda name: name == "aprovider")
        monkeypatch.setattr(chat_routes, "model_reach", lambda: {})
        monkeypatch.setattr(chat_routes, "load_register", lambda: {})
        monkeypatch.setattr(chat_routes, "split_provider",
                            lambda m: ("aprovider", m[len("aprovider/"):])
                            if m.startswith("aprovider/") else (None, m))
        monkeypatch.setattr(chat_routes, "get_user_setting",
                            lambda key, default=None: "aprovider"
                            if key == "EXTERNAL_LLM_PROVIDER" else default)
        return [e["id"] for e in
                chat_routes._cloud_chat_models_from_matrix(self.MATRIX)]

    def test_the_role_models_are_offered_once_each(self, monkeypatch):
        assert self._offered(monkeypatch) == ["aprovider/current-writer",
                                              "aprovider/current-checker"]

    def test_no_fallback_reaches_the_picker(self, monkeypatch):
        offered = self._offered(monkeypatch)
        for m in self.MATRIX["llm_presets"]["aprovider"]["chat_fallback_models"]:
            assert f"aprovider/{m}" not in offered, (
                f"{m} stands in the matrix as what a failed call reaches for "
                f"next, not as a model to pick")

    def test_the_chain_still_reaches_for_them(self, monkeypatch):
        """The other half of the same field, and it has to stay.

        Emptying the matrix field would pass the test above and take the failed
        call's next attempt with it.
        """
        monkeypatch.setattr(chat_routes, "_load_llm_matrix", lambda: self.MATRIX)
        monkeypatch.setattr(settings_routes, "_recorded_conformity",
                            lambda *a, **k: True)
        monkeypatch.setattr(settings_routes, "_service_reached", lambda m: "aprovider")
        chain = chat_routes.build_model_candidate_chain(
            "STAGE2_INTERCEPTION_MODEL", "aprovider/current-writer")
        assert chain[:3] == ["aprovider/current-writer",
                             "aprovider/older-writer",
                             "aprovider/older-checker"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
