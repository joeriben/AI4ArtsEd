"""No output cap reaches a model through the Prompt Interception engine.

Until 2026-11-08 the engine forwarded a `max_tokens` from a config's
parameters on all three of its branches: to the shared cloud reader, to the
local client as `max_new_tokens` (which the client dropped before the node),
and into the Bedrock request body. No JSON config named one, so the
passthrough slept. A cap below the model's ceiling cuts the answer
mid-sentence, and on a reasoning model it can be spent inside the train of
thought before a line of content is written. The passthrough is gone; the
cloud and local branches are held in their own test files
(test_cloud_transport_callers.py, test_interception_local_branch.py). This
file holds the Bedrock branch and the configs: since a cap a config names is
now not sent, a config that names one would carry a field that does nothing,
and none may. A perspective kept in the lab database cannot add one
(interception_prompts_routes.ALLOWED_PARAM_KEYS); one kept before 2026-10-10
may still carry one until its next update, and it is not sent either.
"""

import asyncio
import io
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import config
from schemas.engine import prompt_interception_engine as engine_module

DEVSERVER = Path(__file__).resolve().parents[1]

# The names an output cap goes by across the dialects the platform speaks.
CAP_KEYS = {"max_tokens", "max_new_tokens", "max_output_tokens",
            "max_completion_tokens", "maxOutputTokens", "num_predict"}

# Where configs, chunks and pipelines live that the engine is handed
# parameters from. schemas/archive is not loaded by anything.
CONFIG_ROOTS = [
    DEVSERVER / "schemas" / "chunks",
    DEVSERVER / "schemas" / "configs",
    DEVSERVER / "schemas" / "pipelines",
    DEVSERVER / "config",
]
CONFIG_FILES = [DEVSERVER / "schemas" / "output_config_defaults.json"]


class _Bedrock:
    def __init__(self):
        self.bodies = []

    def invoke_model(self, modelId, body):
        self.bodies.append(json.loads(body))
        answer = {"content": [{"type": "text", "text": "an intercepted text"}]}
        return {"body": io.BytesIO(json.dumps(answer).encode("utf-8"))}


@pytest.fixture
def bedrock(monkeypatch):
    client = _Bedrock()
    fake = types.ModuleType("boto3")
    fake.client = lambda **kwargs: client
    monkeypatch.setitem(sys.modules, "boto3", fake)
    monkeypatch.setattr(engine_module.model_selector, "get_local_models", lambda: [])
    monkeypatch.setattr(engine_module.model_selector, "get_openrouter_models", lambda: [])
    return client


def _call_bedrock(parameters):
    engine = engine_module.PromptInterceptionEngine()
    return asyncio.run(engine._call_aws_bedrock("a prompt", "eu.a-model", False,
                                                parameters=parameters))


class TestTheBedrockBody:
    def test_the_field_this_api_requires_carries_the_ceiling(self, bedrock):
        output, _ = _call_bedrock(None)
        assert output == "an intercepted text"
        assert bedrock.bodies[0]["max_tokens"] == config.ANTHROPIC_MAX_TOKENS_CEILING

    def test_a_cap_a_config_names_does_not_replace_the_ceiling(self, bedrock):
        _call_bedrock({"max_tokens": 512, "temperature": 0.2})
        body = bedrock.bodies[0]
        assert body["max_tokens"] == config.ANTHROPIC_MAX_TOKENS_CEILING
        assert body["temperature"] == 0.2


def _cap_keys_in(node, trail=""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else str(key)
            if key in CAP_KEYS:
                yield here
            yield from _cap_keys_in(value, here)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _cap_keys_in(value, f"{trail}[{i}]")


def test_no_config_names_an_output_cap():
    from schemas.engine.config_loader import EXCLUDED_CONFIG_DIRS

    found, unreadable = [], []
    paths = [p for root in CONFIG_ROOTS for p in sorted(root.rglob("*.json"))
             # Folders the loader never reads (tmp, backup, ...), as
             # test_review_d2_findings.py skips them.
             if not EXCLUDED_CONFIG_DIRS & set(p.relative_to(root).parts)] + CONFIG_FILES
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            unreadable.append(f"{path.relative_to(DEVSERVER)}: {e}")
            continue
        for where in _cap_keys_in(data):
            found.append(f"{path.relative_to(DEVSERVER)}: {where}")
    assert not found, "configs that name an output cap:\n" + "\n".join(found)
    assert not unreadable, "configs the scan could not read:\n" + "\n".join(unreadable)


def test_the_config_roots_exist():
    """A moved directory would leave the scan above passing over nothing."""
    for root in CONFIG_ROOTS:
        assert root.is_dir(), root
        assert any(root.rglob("*.json")), root
    for path in CONFIG_FILES:
        assert path.is_file(), path
