"""The direct route (/api/schema/pipeline/direct) reads every text the client
sent that reaches an encoder, at the intake and before the model.

Until 2026-10-10 the route checked `prompt` alone; prompt_b, prompt_c, the
concepts of a composable run and the negative prompt went to the chunk as
custom parameters and were encoded unchecked. Until the three checks, the check
before the model ran at kids and youth only, so at adult these texts reached
the encoder without a question of the level.

The intake and the check before the model are replaced by readers that keep
what they were given and refuse a text that carries their word; the executor
by one that records whether it was reached. The store is a temporary one, as
in test_latent_transport.

The Surrealization workflow writes two of its texts with a language model,
in steps that run between the two checks (my_app/services/chunk_llm_steps.py).
There call_chat_helper is replaced by one that answers by the step's context.
"""
from types import SimpleNamespace

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         REASON_PERSONAL_DATA, REASON_SYMBOL, Verdict)

AT_THE_INTAKE = "refuse-at-the-intake"
BEFORE_THE_MODEL = "refuse-before-the-model"


@pytest.fixture
def checks(monkeypatch):
    seen = {"intake": {}, "before_model": [], "order": []}

    def intake_one(text, *, level, kind, field):
        seen["intake"][field] = text
        seen["order"].append("intake")
        if AT_THE_INTAKE in str(text or ""):
            return Verdict(False, CHECKPOINT_INTAKE, level, field, REASON_PERSONAL_DATA,
                           "refused at the intake")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def intake(fields, *, level):
        for name, text in fields.items():
            verdict = intake_one(text, level=level, kind="text", field=name)
            if not verdict.passed:
                return verdict
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        seen["before_model"].append({"texts": dict(texts), "level": level})
        seen["order"].append("check")
        for name, text in texts.items():
            if BEFORE_THE_MODEL in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_SYMBOL,
                               "refused before the model")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    monkeypatch.setattr(R, "check_intake", intake_one)
    monkeypatch.setattr(R, "check_intake_texts", intake)
    monkeypatch.setattr(R, "check_before_model", before_model)
    return seen


def _executor_that_stops(monkeypatch):
    reached = {}

    async def execute_pipeline(**kwargs):
        reached["called"] = True
        return SimpleNamespace(success=False, error="stopped here on purpose",
                               metadata={}, final_output=None)

    monkeypatch.setattr(R, "pipeline_executor",
                        SimpleNamespace(execute_pipeline=execute_pipeline,
                                        config_loader=SimpleNamespace(
                                            get_config=lambda name: None)))
    return reached


@pytest.fixture
def storage(monkeypatch, tmp_path):
    import config
    from my_app.services import pipeline_recorder as recorder_mod
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    recorder_mod._active_recorders.clear()
    return tmp_path


def _run(field_values, level="adult"):
    data = {"prompt": "a house", "output_config": "sd35_large", "seed": 1}
    data.update(field_values)
    return R._run_direct_workflow(data, level)


def _read(texts):
    """The texts a check read, without the fields the request left empty."""
    return {name: text for name, text in texts.items() if text}


# ── The intake ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("field", ["prompt", "prompt_b", "prompt_c", "negative_prompt"])
def test_a_text_the_intake_refuses_reaches_no_model(monkeypatch, checks, storage, field):
    reached = _executor_that_stops(monkeypatch)
    payload, status = _run({field: f"a house {AT_THE_INTAKE}"})
    assert status == 403, payload
    assert payload["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert payload["safety_block"]["field"] == field
    assert checks["before_model"] == [], "the check before the model ran after a refusal"
    assert "called" not in reached, "the run went on past a refused text"


def test_a_concept_the_intake_refuses_reaches_no_model(monkeypatch, checks, storage):
    reached = _executor_that_stops(monkeypatch)
    payload, status = _run({"concepts": [{"prompt": "a cat", "weight": 0.5},
                                         {"prompt": AT_THE_INTAKE, "weight": 0.5}]})
    assert status == 403, payload
    assert payload["safety_block"]["field"] == "concepts[1]"
    assert "called" not in reached


def test_every_text_reaches_both_checks(monkeypatch, checks, storage):
    reached = _executor_that_stops(monkeypatch)
    _run({"prompt_b": "a king", "prompt_c": "a man", "negative_prompt": "no cats",
          "concepts": '[{"prompt": "k1", "weight": 1}, {"prompt": "k2", "weight": 1}]'})
    sent = {"prompt": "a house", "prompt_b": "a king", "prompt_c": "a man",
            "negative_prompt": "no cats", "concepts[0]": "k1", "concepts[1]": "k2"}
    assert _read(checks["intake"]) == sent
    assert [_read(seen["texts"]) for seen in checks["before_model"]] == [sent]
    assert reached.get("called") is True


# ── Before the model ────────────────────────────────────────────────────────

def test_a_text_refused_before_the_model_reaches_no_model(monkeypatch, checks, storage):
    reached = _executor_that_stops(monkeypatch)
    payload, status = _run({"negative_prompt": f"no cats {BEFORE_THE_MODEL}"})
    assert status == 403, payload
    assert payload["safety_block"]["checkpoint"] == CHECKPOINT_BEFORE_MODEL
    assert payload["safety_block"]["field"] == "negative_prompt"
    assert payload["checks_passed"] == ["intake"]
    assert "called" not in reached


@pytest.mark.parametrize("level", ["kids", "youth", "adult", "research"])
def test_the_check_before_the_model_is_asked_at_every_level(monkeypatch, checks, storage,
                                                            level):
    """adult has its own question now; at research the check itself lets
    everything pass."""
    _executor_that_stops(monkeypatch)
    _run({}, level=level)
    assert [seen["level"] for seen in checks["before_model"]] == [level]


def test_a_text_in_two_fields_is_read_once_before_the_model(monkeypatch, checks, storage):
    _executor_that_stops(monkeypatch)
    _run({"prompt_b": "a house", "concepts": [{"prompt": " a house ", "weight": 1}]})
    [seen] = checks["before_model"]
    assert _read(seen["texts"]) == {"prompt": "a house"}


def _adapted_prompts(monkeypatch, clip, t5):
    """Encoder Fusion's adapted prompts, written here instead of by the LLM."""
    from my_app.services import surrealizer_original
    monkeypatch.setattr(surrealizer_original, "build_prompts",
                        lambda prompt: (clip, t5, 0.5))


def test_the_encoder_prompts_an_llm_wrote_are_read_before_the_model(monkeypatch, checks,
                                                                   storage):
    _adapted_prompts(monkeypatch, "house, landscape", "A house stands in a wide landscape.")
    reached = _executor_that_stops(monkeypatch)
    _run({"fusion_strategy": "two_interceptions"})
    [seen] = checks["before_model"]
    assert seen["texts"]["clip_prompt"] == "house, landscape"
    assert seen["texts"]["t5_prompt"] == "A house stands in a wide landscape."
    assert "clip_prompt" not in checks["intake"], "the machine's text is not the user's"
    assert reached.get("called") is True


def test_an_encoder_prompt_refused_before_the_model_reaches_no_model(monkeypatch, checks,
                                                                     storage):
    _adapted_prompts(monkeypatch, "house, landscape", f"A house. {BEFORE_THE_MODEL}")
    reached = _executor_that_stops(monkeypatch)
    payload, status = _run({"fusion_strategy": "two_interceptions"})
    assert status == 403, payload
    assert payload["safety_block"]["field"] == "t5_prompt"
    assert "called" not in reached


# ── The level ───────────────────────────────────────────────────────────────

def test_a_level_that_cannot_be_resolved_runs_nothing(monkeypatch, checks, storage):
    reached = _executor_that_stops(monkeypatch)

    def unresolvable():
        raise RuntimeError("no level")

    monkeypatch.setattr(R, "resolve_safety_level", unresolvable)
    app = Flask(__name__)
    app.register_blueprint(R.schema_bp, url_prefix="/api/schema")
    response = app.test_client().post(
        "/api/schema/pipeline/direct",
        json={"prompt": "a house", "output_config": "sd35_large", "seed": 1})
    assert response.status_code == 500
    body = response.get_json()
    assert body["cause"] == "safety_level_unresolved"
    assert "could not be resolved" in body["error"]
    assert checks["intake"] == {} and "called" not in reached


# ── The workflow's language-model steps ─────────────────────────────────────

T5 = "A house of rough timber stands in a field. #a=22"
CLIP = "house, field, rough timber"


@pytest.fixture
def steps(monkeypatch, checks):
    """The Surrealization workflow's three steps, answered here by the context
    each one sends; what ran is kept in checks["order"]."""
    from my_app.routes import chat_routes
    answers = {"prompting expert": T5, "prompt expert": CLIP, "number identifier": "22"}

    def call_chat_helper(messages, **kw):
        context = messages[-1]["content"].split("Context:\n", 1)[1].split("\nPrompt:\n", 1)[0]
        checks["order"].append(f"step:{context}")
        if isinstance(answers[context], Exception):
            raise answers[context]
        return {"content": answers[context], "model_used": "the interception model"}

    monkeypatch.setattr(chat_routes, "call_chat_helper", call_chat_helper)
    return answers


def _executor_of_the_workflow(monkeypatch, checks):
    """The executor of the Surrealization workflow's config: the config names
    the chunk; the run keeps what it hands the chunk and stops."""
    reached = {}

    async def execute_pipeline(**kwargs):
        checks["order"].append("model")
        reached.update(kwargs["context_override"].custom_placeholders)
        return SimpleNamespace(success=False, error="stopped here on purpose",
                               metadata={}, final_output=None)

    config = SimpleNamespace(parameters={"OUTPUT_CHUNK": "legacy_surrealization"})
    monkeypatch.setattr(R, "pipeline_executor", SimpleNamespace(
        execute_pipeline=execute_pipeline,
        config_loader=SimpleNamespace(
            get_config=lambda name: config if name == "surrealization_legacy" else None)))
    return reached


def _workflow_run(**fields):
    return _run({"output_config": "surrealization_legacy", "alpha_factor": 0, **fields})


def _ran(order):
    """What ran, each kind once in a row."""
    return [kind for i, kind in enumerate(order) if i == 0 or kind != order[i - 1]]


def test_the_steps_run_after_the_intake_and_before_the_check(monkeypatch, checks, storage,
                                                             steps):
    _executor_of_the_workflow(monkeypatch, checks)
    _workflow_run()
    assert _ran(checks["order"]) == [
        "intake", "step:prompting expert", "step:prompt expert", "step:number identifier",
        "check", "model"]


def test_the_check_reads_what_the_steps_wrote(monkeypatch, checks, storage, steps):
    _executor_of_the_workflow(monkeypatch, checks)
    _workflow_run()
    [seen] = checks["before_model"]
    assert seen["texts"]["t5_prompt"] == T5
    assert seen["texts"]["clip_prompt"] == CLIP
    assert "proposed_alpha" not in seen["texts"], "a number is no text"
    assert "t5_prompt" not in checks["intake"], "the machine's text is not the user's"


def test_what_the_steps_wrote_goes_to_the_workflow(monkeypatch, checks, storage, steps):
    reached = _executor_of_the_workflow(monkeypatch, checks)
    _workflow_run()
    assert reached["t5_prompt"] == T5
    assert reached["clip_prompt"] == CLIP
    assert reached["proposed_alpha"] == 22.0
    assert reached["alpha_factor"] == 0, "the slider's alpha still replaces the proposed one"


def test_a_step_that_fails_ends_the_run(monkeypatch, checks, storage, steps):
    steps["prompt expert"] = RuntimeError("the model is gone")
    reached = _executor_of_the_workflow(monkeypatch, checks)
    payload, status = _workflow_run()
    assert status == 502, payload
    assert "clip_prompt" in payload["error"]
    assert checks["before_model"] == [] and reached == {}


def test_a_step_that_writes_no_text_ends_the_run(monkeypatch, checks, storage, steps):
    """The node handed an empty answer on and the encoder encoded it: a picture
    of nothing in particular under the name of the prompt."""
    steps["prompting expert"] = "  "
    reached = _executor_of_the_workflow(monkeypatch, checks)
    payload, status = _workflow_run()
    assert status == 502, payload
    assert "t5_prompt" in payload["error"]
    assert checks["before_model"] == [] and reached == {}


def test_a_text_a_step_wrote_and_the_check_refuses_reaches_no_model(monkeypatch, checks,
                                                                    storage, steps):
    steps["prompting expert"] = f"A house. {BEFORE_THE_MODEL}"
    reached = _executor_of_the_workflow(monkeypatch, checks)
    payload, status = _workflow_run()
    assert status == 403, payload
    assert payload["safety_block"]["field"] == "t5_prompt"
    assert reached == {}


def test_a_text_the_intake_refuses_reaches_no_step(monkeypatch, checks, storage, steps):
    _executor_of_the_workflow(monkeypatch, checks)
    payload, status = _workflow_run(prompt=f"a house {AT_THE_INTAKE}")
    assert status == 403, payload
    assert not [kind for kind in checks["order"] if kind.startswith("step:")]


def test_a_chunk_that_declares_no_steps_runs_none(monkeypatch, checks, storage, steps):
    reached = {}

    async def execute_pipeline(**kwargs):
        reached["called"] = True
        return SimpleNamespace(success=False, error="stopped here on purpose",
                               metadata={}, final_output=None)

    config = SimpleNamespace(parameters={"OUTPUT_CHUNK": "output_image_sd35_large"})
    monkeypatch.setattr(R, "pipeline_executor", SimpleNamespace(
        execute_pipeline=execute_pipeline,
        config_loader=SimpleNamespace(get_config=lambda name: config)))
    _run({})
    assert not [kind for kind in checks["order"] if kind.startswith("step:")]
    assert reached.get("called") is True
