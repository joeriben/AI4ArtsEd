"""The engine's local branch: one user message through the chat template.

From ac047ceb (2026-02-23) to 2026-09-16 `_call_local_llm` sent the prompt
raw to the local model, with no chat template around it, while the cloud
branch has sent the same prompt as the one user message of a conversation
since 3151a667 (2025-10-18). An instruct model given raw text continues it
instead of answering it: measured on 16.09.2026 with Qwen 3.5 9B as
STAGE3_MODEL in the kids replay, the model opened a train of thought on the
translation prompt, 39 of 43 answers were stopped inside it by the
repetition guard, and the fragment went on as the answer. These tests hold
the branch to the cloud branch's shape and to the same refusals: reasoning is
not an answer, and an answer the model did not finish is not one either.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import config
from my_app.services import llm_backend as llm_backend_module
from schemas.engine import prompt_interception_engine as engine_module
from schemas.engine.pipeline_executor import executor


class _Backend:
    """Stands in for the LLMClient: records what the engine asked for.

    `chat` and `generate` take their first two arguments by position, as
    the client does (llm_client.py, `chat(self, model, messages, ...)`), so
    a positional call in the engine is recorded and not mistaken for a
    defect; `generate` answers None and is recorded, so a branch that went
    back to the raw prompt shows up as a call, not as a swallowed error.
    """

    def __init__(self, answer):
        self.answer = answer
        self.chat_calls = []
        self.generate_calls = []

    def chat(self, model, messages, **kwargs):
        self.chat_calls.append({"model": model, "messages": messages, **kwargs})
        return self.answer

    def generate(self, model, prompt, **kwargs):
        self.generate_calls.append({"model": model, "prompt": prompt, **kwargs})
        return None


@pytest.fixture
def offline_engine(monkeypatch):
    """An engine whose model lists come from nowhere and whose local backend
    is the stub handed back by the factory this fixture returns."""
    monkeypatch.setattr(engine_module.model_selector, "get_local_models", lambda: [])
    monkeypatch.setattr(engine_module.model_selector, "get_openrouter_models", lambda: [])

    def _with(answer):
        backend = _Backend(answer)
        monkeypatch.setattr(llm_backend_module, "get_llm_backend", lambda: backend)
        return engine_module.PromptInterceptionEngine(), backend

    return _with


# The platform's standard test prompt (standard_test_prompt.txt) and its translation.
PROMPT = ("Ein Haus steht in einer Landschaft, umgeben von landwirtschaftlichen Flächen, "
          "Natur und Tieren. Es sind einige Menschen zu sehen.")
TRANSLATION = "A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen."


def _run(engine, prompt="Translate this: " + PROMPT, model="local/a-model:9b",
         parameters=None):
    return asyncio.run(engine.process_request(engine_module.PromptInterceptionRequest(
        input_prompt="", prebuilt_prompt=prompt, model=model, parameters=parameters,
    )))


def _answer(content=TRANSLATION, thinking=None, finish_reason="stop"):
    return {"content": content, "thinking": thinking, "tool_calls": None,
            "finish_reason": finish_reason}


class TestThePromptGoesAsOneUserMessage:
    def test_the_prompt_is_the_one_user_message_of_the_conversation(self, offline_engine):
        engine, backend = offline_engine(_answer())
        response = _run(engine, prompt="a prompt written for the cloud branch")
        assert backend.generate_calls == []
        assert len(backend.chat_calls) == 1
        call = backend.chat_calls[0]
        assert call["model"] == "a-model:9b"
        assert call["messages"] == [{"role": "user",
                                     "content": "a prompt written for the cloud branch"}]
        assert response.success, response.error

    def test_the_answer_is_the_content_and_the_thinking_is_not(self, offline_engine):
        engine, _ = offline_engine(_answer(content="the answer", thinking="the way there"))
        response = _run(engine)
        assert response.success, response.error
        assert response.output_str == "the answer"
        assert "the way there" not in response.output_str

    @pytest.mark.parametrize("flag", [False, True])
    def test_the_thinking_switch_of_the_config_reaches_the_call(self, offline_engine, flag):
        engine, backend = offline_engine(_answer())
        _run(engine, parameters={"enable_thinking": flag})
        assert backend.chat_calls[0]["enable_thinking"] is flag

    def test_a_config_that_says_nothing_leaves_the_switch_to_the_client(self, offline_engine):
        """The client's own default is the template's default (thinking on);
        the engine does not decide it a second time."""
        engine, backend = offline_engine(_answer())
        _run(engine, parameters={"temperature": 0.2})
        assert "enable_thinking" not in backend.chat_calls[0]

    def test_the_sampling_parameters_of_the_config_go_with_the_call(self, offline_engine):
        engine, backend = offline_engine(_answer())
        _run(engine, parameters={"temperature": 0.2, "repetition_penalty": 1.5})
        call = backend.chat_calls[0]
        assert call["temperature"] == 0.2
        assert call["repetition_penalty"] == 1.5


class TestWhatIsNotAnAnswerIsRefused:
    @pytest.mark.parametrize("finish_reason", ["repetition", "length", "stop"])
    def test_content_empty_and_thinking_written_is_a_failed_request(self, offline_engine,
                                                                    finish_reason):
        """The sentence says what came instead of an answer and the node's
        word for why the model stopped: a train of thought ended by the
        repetition guard is the measured local failure (Nr. 119, Nr. 122)."""
        engine, _ = offline_engine(_answer(content="", thinking="i should translate this",
                                           finish_reason=finish_reason))
        response = _run(engine)
        assert not response.success
        assert response.output_str == ""
        assert "no answer" in response.error
        assert "23 chars of thinking" in response.error
        assert f"finish_reason={finish_reason}" in response.error
        assert "a-model:9b" in response.error

    def test_content_empty_without_thinking_is_an_empty_response(self, offline_engine):
        engine, _ = offline_engine(_answer(content="", thinking=None))
        response = _run(engine)
        assert not response.success
        assert "empty response" in response.error
        assert "finish_reason=stop" in response.error

    def test_a_call_that_failed_is_not_reported_as_an_empty_answer(self, offline_engine):
        """The client hands back None after logging the cause; the engine says
        the call failed, and does not call a failure an empty answer."""
        engine, _ = offline_engine(None)
        response = _run(engine)
        assert not response.success
        assert "call failed" in response.error
        assert "empty" not in response.error

    def test_an_answer_that_reached_the_window_is_refused(self, offline_engine):
        engine, _ = offline_engine(_answer(content="A house stands in a", finish_reason="length"))
        response = _run(engine)
        assert not response.success
        assert "finish_reason=length" in response.error

    def test_an_answer_stopped_for_looping_is_refused(self, offline_engine):
        engine, _ = offline_engine(_answer(content="house house house house", finish_reason="repetition"))
        response = _run(engine)
        assert not response.success
        assert "finish_reason=repetition" in response.error


class TestTheTranslationAsksForNoReasoning:
    """A translation is a plain answer, as the adaption already says at the
    two endpoints the surface uses (schema_pipeline_routes, parameters=
    {"enable_thinking": False}); the config pre_output/translation_en says
    it for the pipeline, and the whole path -- config loader, chunk builder,
    router, engine -- carries it to the call. Only the backend and the model
    lists are stubbed."""

    @pytest.fixture
    def translation_on_a_local_model(self, monkeypatch):
        monkeypatch.setattr(engine_module.model_selector, "get_local_models", lambda: [])
        monkeypatch.setattr(engine_module.model_selector, "get_openrouter_models", lambda: [])
        monkeypatch.setattr(config, "STAGE3_MODEL", "local/a-model:9b")
        backend = _Backend(_answer())
        monkeypatch.setattr(llm_backend_module, "get_llm_backend", lambda: backend)
        if not executor.config_loader.resolved_configs:
            executor.config_loader.initialize(executor.schemas_path)
        return backend

    def test_the_translation_config_switches_thinking_off_at_the_call(
            self, translation_on_a_local_model):
        backend = translation_on_a_local_model
        result = asyncio.run(executor.execute_pipeline("pre_output/translation_en",
                                                       PROMPT))
        assert result.success, result.error
        assert backend.generate_calls == []
        assert len(backend.chat_calls) == 1
        call = backend.chat_calls[0]
        assert call["model"] == "a-model:9b"
        assert call["enable_thinking"] is False
        assert call["temperature"] == 0.2
        assert [m["role"] for m in call["messages"]] == ["user"]

    def test_without_the_line_in_the_config_the_switch_stays_with_the_client(
            self, translation_on_a_local_model, monkeypatch):
        """The counter-check that the line above is what carries the switch."""
        backend = translation_on_a_local_model
        resolved = executor.config_loader.get_config("pre_output/translation_en")
        params = dict(resolved.parameters)
        params.pop("enable_thinking", None)
        monkeypatch.setattr(resolved, "parameters", params)
        result = asyncio.run(executor.execute_pipeline("pre_output/translation_en",
                                                       PROMPT))
        assert result.success, result.error
        assert "enable_thinking" not in backend.chat_calls[0]
