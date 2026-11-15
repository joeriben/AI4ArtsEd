"""The language-model steps of a media workflow run on the platform, before the
check before the model, as the workflow's own nodes ran them.

The Surrealization workflow (schemas/chunks/legacy_surrealization.json) held
three Prompt Interception nodes inside ComfyUI: 68 wrote the text T5 encodes,
69 the text CLIP encodes, and 70 read the alpha the T5 text proposes. They
wrote after every check. The chunk declares them as `llm_steps` now, the route
runs them first (my_app/services/chunk_llm_steps.py), and the graph receives
their results through input_mappings.

What holds the move to its word:
- the three instructions are the nodes' own, pinned by their SHA-256 as they
  stood in the workflow until 2026-10-31, the same as in the archived original
  (ai4artsed_Surrealization_2506092253.json);
- a step makes the call the node made and hands on what the node handed on:
  the node class itself runs beside the steps, on the same answers;
- the graph reads the results where it read the nodes, and a path that did not
  run the steps submits nothing.

No model is asked: the node's DevServer client and call_chat_helper are both
replaced by one fake that answers by the step's context.
"""
import asyncio
import hashlib
import json
import sys
import types
from types import SimpleNamespace

import pytest

from file_modules import REPO, load_module
from my_app.services import chunk_llm_steps as steps

CHUNK = "legacy_surrealization"
NODE_FILE = REPO / "comfyui_nodes" / "ai4artsed_comfyui" / "ai4artsed_prompt_interception.py"

# Each node's context and the SHA-256 of its instruction (style_prompt), as the
# workflow carried them, by what the step writes.
ORIGINAL = {
    "t5_prompt": ("68", "prompting expert",
                  "85e246e8498696296ccc32f9232508fb6b2f84239e6c77763e72dc733a79314d"),
    "clip_prompt": ("69", "prompt expert",
                    "7e998267e5de5816c68eb1a5dccea8a2107c748c59e467706ac9b7589127a658"),
    "proposed_alpha": ("70", "number identifier",
                       "0fdff2bcb2acde90b10093eef677064d5d8e0288979a90f3b380331f6847a91e"),
}
# What each node read, and the node and field of the graph that read its result.
WIRING = {
    "t5_prompt": ("prompt", "21", "inputs.text"),
    "clip_prompt": ("prompt", "6", "inputs.text"),
    "proposed_alpha": ("t5_prompt", "50", "inputs.value"),
}
GONE = {"68", "69", "70", "40", "41", "72"}

ANSWERS = {
    "prompting expert": "  A house of rough timber stands in a field. #a=1.234,5  ",
    "prompt expert": " house, field, rough timber ",
    "number identifier": "the number is 1.234,5",
}


def _context(messages):
    """The context a call's envelope names."""
    return messages[-1]["content"].split("Context:\n", 1)[1].split("\nPrompt:\n", 1)[0]


def _chunk():
    return json.loads((steps.CHUNKS_DIR / f"{CHUNK}.json").read_text(encoding="utf-8"))


@pytest.fixture
def node(monkeypatch):
    """The node class, loaded from its file into a package of its own whose
    DevServer client answers from `node.answers` and keeps what it was sent."""
    answers = dict(ANSWERS)
    calls = []

    def chat(node_label, messages, model, temperature=None, image_b64=None):
        calls.append({"messages": messages, "model": model, "temperature": temperature})
        return answers[_context(messages)], model

    package = types.ModuleType("parity_nodes")
    package.__path__ = []
    client = types.ModuleType("parity_nodes._devserver")
    client.model_choices = lambda role: [f"platform/{role}"]
    client.chat = chat
    monkeypatch.setitem(sys.modules, "parity_nodes", package)
    monkeypatch.setitem(sys.modules, "parity_nodes._devserver", client)
    module = load_module("parity_nodes.ai4artsed_prompt_interception", NODE_FILE)
    return SimpleNamespace(cls=module.ai4artsed_prompt_interception, answers=answers,
                           calls=calls)


@pytest.fixture
def platform(monkeypatch, node):
    """call_chat_helper, answering what the node's client answers and keeping
    what it was asked."""
    from my_app.routes import chat_routes
    calls = []

    def call_chat_helper(messages, temperature=None, max_tokens=None, enable_thinking=True,
                         model_override=None, tools=None, image_b64=None, role=None,
                         local_in_caller=False, may_leave_server=False):
        calls.append({"messages": messages, "temperature": temperature, "role": role,
                      "model_override": model_override, "max_tokens": max_tokens})
        answer = node.answers[_context(messages)]
        if isinstance(answer, Exception):
            raise answer
        return {"content": answer, "model_used": "the interception model"}

    monkeypatch.setattr(chat_routes, "call_chat_helper", call_chat_helper)
    return calls


# ── The declaration ─────────────────────────────────────────────────────────

def test_the_steps_carry_the_nodes_instructions():
    declared = {step["writes"]: step for step in steps.steps_of(CHUNK)}
    assert list(declared) == list(ORIGINAL), "the nodes' order: 70 reads what 68 wrote"
    for writes, (node_id, context, digest) in ORIGINAL.items():
        assert declared[writes]["input_context"] == context, node_id
        assert hashlib.sha256(declared[writes]["style_prompt"].encode("utf-8")).hexdigest() \
            == digest, f"the instruction of node {node_id} changed on its way into the step"


def test_the_graph_reads_the_results_where_it_read_the_nodes():
    chunk = _chunk()
    declared = {step["writes"]: step for step in chunk["llm_steps"]}
    for writes, (reads, node_id, field) in WIRING.items():
        assert declared[writes]["reads"] == reads, writes
        mapping = chunk["input_mappings"][writes]
        assert (mapping["node_id"], mapping["field"]) == (node_id, field), writes
    assert [step["result"] for step in chunk["llm_steps"]] == ["text", "text", "number"]
    assert not GONE & set(chunk["workflow"]), "the nodes and their previews left the graph"
    links = [value for node in chunk["workflow"].values()
             for value in node.get("inputs", {}).values() if isinstance(value, list)]
    assert not [link for link in links if link and link[0] in GONE]


def test_every_declared_step_reads_what_is_there_and_reaches_the_graph():
    wrong = []
    for path in sorted(steps.CHUNKS_DIR.glob("*.json")):
        try:
            chunk = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        written = {"prompt"}
        for step in chunk.get("llm_steps") or []:
            writes = step.get("writes")
            if not all(isinstance(step.get(key), str) and step[key].strip()
                       for key in ("writes", "reads", "input_context", "style_prompt")):
                wrong.append(f"{path.name}: a step lacks one of its four texts")
            if step.get("result") not in ("text", "number"):
                wrong.append(f"{path.name}: {writes} declares the result {step.get('result')!r}")
            if step.get("reads") not in written:
                wrong.append(f"{path.name}: {writes} reads {step.get('reads')} before it is "
                             f"written")
            mapping = (chunk.get("input_mappings") or {}).get(writes) or {}
            if mapping.get("node_id") not in (chunk.get("workflow") or {}):
                wrong.append(f"{path.name}: nothing in the graph reads {writes}")
            written.add(writes)
    assert not wrong, "\n".join(wrong)


# ── The call ────────────────────────────────────────────────────────────────

def test_a_step_makes_the_call_the_node_made(node, platform):
    """Same envelope, same opening turn, same temperature, same role; and what
    the workflow computed from the answers is what the steps compute."""
    prompt = "  a house in a field  "
    results = steps.run_llm_steps(CHUNK, prompt)

    declared = {step["writes"]: step for step in steps.steps_of(CHUNK)}

    def run(writes, text):
        return node.cls().run(text, declared[writes]["input_context"],
                              declared[writes]["style_prompt"],
                              f"platform/{node.cls.ROLE}", "disable")

    t5 = run("t5_prompt", prompt)
    clip = run("clip_prompt", prompt)
    alpha = run("proposed_alpha", t5[0])
    assert results == {"t5_prompt": t5[0], "clip_prompt": clip[0], "proposed_alpha": alpha[1]}
    assert results["proposed_alpha"] == 1234.5
    assert [call["messages"] for call in platform] == [call["messages"] for call in node.calls]
    assert {call["temperature"] for call in platform} == {
        call["temperature"] for call in node.calls} == {0.7}
    assert {call["role"] for call in platform} == {node.cls.ROLE}
    assert {call["model_override"] for call in platform} == {None}
    assert {call["max_tokens"] for call in platform} == {None}


def test_the_role_is_the_one_the_workflows_nodes_ran_on(node):
    from my_app.services.legacy_workflow_service import replace_llm_models
    graph = replace_llm_models({"1": {"class_type": "ai4artsed_prompt_interception",
                                      "inputs": {"model": "local/mistral:7b"}}})
    assert graph["1"]["inputs"]["model"] == f"platform/{steps.ROLE}"
    assert node.cls.ROLE == steps.ROLE


@pytest.mark.parametrize("answer", [
    "#a=22", "22", " 22 ", "1.234,5", "0,75", "-3.5 and 7", "+15", ".5", "12.5.2025",
    "1.000", "1.000.000,25", "no number", "", "a=1e3", "the value: 20",
])
def test_the_number_is_the_one_the_node_reads(node, answer):
    node.answers["number identifier"] = answer
    out = node.cls().run("a text", "number identifier", "an instruction", "a model", "disable")
    assert steps._as_float(answer.strip()) == out[1]


# ── Where a step does not answer ────────────────────────────────────────────

def test_a_step_that_fails_raises(node, platform):
    node.answers["prompt expert"] = RuntimeError("the model is gone")
    with pytest.raises(steps.LlmStepError, match="clip_prompt"):
        steps.run_llm_steps(CHUNK, "a house")


@pytest.mark.parametrize("empty", ["", "   \n"])
def test_a_text_step_that_writes_nothing_raises(node, platform, empty):
    node.answers["prompting expert"] = empty
    with pytest.raises(steps.LlmStepError, match="t5_prompt"):
        steps.run_llm_steps(CHUNK, "a house")


def test_a_number_step_without_a_number_answers_the_nodes_zero(node, platform):
    node.answers["number identifier"] = ""
    assert steps.run_llm_steps(CHUNK, "a house")["proposed_alpha"] == 0.0


def test_a_chunk_without_steps_asks_no_model(platform):
    assert steps.run_llm_steps("output_image_sd35_large", "a house") == {}
    assert steps.run_llm_steps(None, "a house") == {}
    assert platform == []


# ── The graph the legacy path submits ───────────────────────────────────────

WRITTEN = {"t5_prompt": "A house of rough timber.", "clip_prompt": "house, timber",
           "proposed_alpha": 22.0}


@pytest.fixture
def router(monkeypatch):
    """The BackendRouter with no ComfyUI to submit to: the graph the legacy
    path built is kept at its last step before the submission."""
    from my_app.services import legacy_workflow_service
    from schemas.engine.backend_router import BackendRouter
    kept = []
    replace = legacy_workflow_service.replace_llm_models

    def keep(workflow):
        kept.append(workflow)
        return replace(workflow)

    async def not_there():
        return False

    monkeypatch.setattr(legacy_workflow_service, "replace_llm_models", keep)
    made = BackendRouter()
    monkeypatch.setattr(made, "comfyui_manager",
                        SimpleNamespace(ensure_comfyui_available=not_there))

    def run(parameters):
        return asyncio.run(made._process_legacy_workflow(
            made._load_output_chunk(CHUNK), "a house", parameters))

    return SimpleNamespace(run=run, kept=kept)


def test_a_path_that_did_not_run_the_steps_submits_nothing(router):
    response = router.run({"alpha_factor": 0, "seed": 1})
    assert not response.success
    assert all(name in response.error for name in WRITTEN), response.error
    assert router.kept == [], "a graph was built"


def test_the_graph_carries_what_the_steps_wrote(router):
    response = router.run({**WRITTEN, "seed": 1})
    assert response.error == "ComfyUI not available"
    [graph] = router.kept
    assert graph["21"]["inputs"]["text"] == WRITTEN["t5_prompt"]
    assert graph["6"]["inputs"]["text"] == WRITTEN["clip_prompt"]
    assert graph["50"]["inputs"]["value"] == WRITTEN["proposed_alpha"]


def test_an_alpha_the_request_carries_replaces_the_proposed_one(router):
    router.run({**WRITTEN, "alpha_factor": -30, "seed": 1})
    [graph] = router.kept
    assert graph["50"]["inputs"]["value"] == -30
