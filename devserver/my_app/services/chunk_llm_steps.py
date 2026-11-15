"""The language-model steps a media workflow declares, run on the platform
before the check before the model.

The Surrealization workflow of 2025 (schemas/chunks/legacy_surrealization.json)
held three Prompt Interception nodes. Two wrote the texts its encoders read, a
T5 text and a CLIP text; the third read the alpha the T5 text proposes. Inside
ComfyUI they wrote after every check, so the encoders received texts no check
had read. The chunk declares them as `llm_steps` now, and the route that runs
it runs them first: the check before the model reads what they wrote, and the
chunk's input_mappings put it into the graph.

A step makes the node's call as the node made it
(comfyui_nodes/ai4artsed_comfyui/ai4artsed_prompt_interception.py, `run`): the
same envelope, the same opening turn, temperature 0.7, on the role the
workflow's nodes were set to (legacy_workflow_service.replace_llm_models), so
the settings' Prompt Interception model with the settings' fallback behind it.

A step declares what it writes, what it reads ("prompt", or what an earlier
step wrote), the node's two texts (input_context, style_prompt) and its result:
"text", or "number" for the number the node read out of its answer.
"""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNKS_DIR = Path(__file__).resolve().parents[2] / "schemas" / "chunks"

# The node's ROLE; the workflow's nodes ran on platform/<ROLE>.
ROLE = "STAGE2_INTERCEPTION_MODEL"
OPENING_TURN = "You are a fresh assistant instance. Forget all previous conversation history."
TEMPERATURE = 0.7

# The node's three number patterns, in the order it tries them.
_GERMAN = r"[-+]?\d{1,3}(?:\.\d{3})*,\d+"
_ENGLISH = r"[-+]?\d*\.\d+"
_INTEGER = r"[-+]?\d+"


class LlmStepError(Exception):
    """A step that failed or wrote no text. The run does not go on without it:
    an encoder without its text is a different run."""


def steps_of(chunk_name):
    """The steps the JSON chunk `chunk_name` declares, in their order; [] for a
    chunk without steps, for a Python chunk and for no name."""
    if not chunk_name:
        return []
    path = CHUNKS_DIR / f"{chunk_name}.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("llm_steps") or []


def run_llm_steps(chunk_name, prompt):
    """{name: result} for every step the chunk declares, run in their order; {}
    for a chunk without steps.

    Raises LlmStepError where a step fails, where a text step answers with no
    text, and where a step reads what nothing before it wrote. A number step
    answers what the node answered: 0.0 where its answer holds no number.
    """
    results = {}
    for step in steps_of(chunk_name):
        writes = step.get("writes")
        written = {"prompt": prompt, **results}
        if step.get("reads") not in written:
            raise LlmStepError(f"the step that writes {writes} reads {step.get('reads')}, "
                               f"which nothing before it wrote")
        try:
            answer, model_used = _interception(written[step["reads"]], step["input_context"],
                                               step["style_prompt"])
        except Exception as e:
            raise LlmStepError(f"the step that writes {writes} failed: {e}") from e
        logger.info(f"[LLM-STEPS] {chunk_name}: {writes} written by {model_used}")
        if step.get("result") == "number":
            results[writes] = _as_float(answer)
        elif not answer:
            raise LlmStepError(f"the step that writes {writes} answered with no text")
        else:
            results[writes] = answer
    return results


def _interception(input_prompt, input_context, style_prompt):
    """(answer, model that wrote it): the node's call, its answer stripped as
    the node hands it on."""
    from my_app.routes.chat_routes import call_chat_helper
    full_prompt = (
        f"Task:\n{style_prompt.strip()}\n\n"
        f"Context:\n{input_context.strip()}\nPrompt:\n{input_prompt.strip()}"
    )
    messages = [{"role": "system", "content": OPENING_TURN},
                {"role": "user", "content": full_prompt}]
    result = call_chat_helper(messages, temperature=TEMPERATURE, role=ROLE)
    return (result.get("content") or "").strip(), result.get("model_used")


def _as_float(text):
    """The number the node reads out of an answer (its output_float): a German
    decimal first, then an English one, then an integer; 0.0 where there is
    none."""
    found = re.search(_GERMAN, text)
    if found:
        try:
            return float(found.group().replace(".", "").replace(",", "."))
        except ValueError:
            return 0.0
    for pattern in (_ENGLISH, _INTEGER):
        found = re.search(pattern, text)
        if found:
            try:
                return float(found.group())
            except ValueError:
                return 0.0
    return 0.0
