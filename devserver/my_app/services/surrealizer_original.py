"""The two prompts the ComfyUI Surrealizer wrote, and the alpha it proposed.

The 2025 workflow did not hand one text to both encoders. It ran the input
through two separate interceptions with two different instructions -- a reordered
keyword list of at most 50 words for CLIP-L, a single prose paragraph of at most
250 words for T5 -- and fused what came back. Node 78 of the workflow says so in
one line: the effect "is achieved by interpolating on the Token/Vektor-Level of
clip_l & t5, which are fed two optimized prompts".

Both instructions below are the workflow's own, character for character; they are
generated from
archive/legacy_docs/workflows_legacy/vector/ai4artsed_Surrealization_2506092253.json
(nodes 69 and 68) and must not be edited by hand. Regenerate instead.

The envelope around the two instructions is the workflow's own, character for
character (ai4artsed_prompt_interception.py, run()):

    Task:\n{style}\n\nContext:\n{input_context}\nPrompt:\n{input}

It is handed over as a prebuilt prompt, because the platform's own envelope is a
different one and appends a rule the workflow never had -- "ALWAYS reply in the
language of the input. NO meta-remarks, NO headlines ..." Both texts here are
LLM output; a changed envelope is a changed prompt, and the language rule alone
would turn a German input's T5 paragraph German, which the workflow never did.
Temperature is the node's 0.7.

Three things about the original cannot be carried over as they were, and all
three are named rather than papered over:

  - The models. The workflow named two local Ollama models, one per instruction.
    Model names must not stand as literals in this code base, and that Ollama is
    no longer connected. Both instructions run on the platform's Stage-2
    interception model.
  - The system message. The node sent "You are a fresh assistant instance.
    Forget all previous conversation history." as its own turn. This engine has
    no system channel, and folding that sentence into the user turn would be a
    different thing wearing its words.
  - The alpha extractor. The workflow's T5 instruction ends by asking for an
    "#a=" value, and a third LLM call read that number out. The number is read
    here with a regular expression -- same value, one call less, no model that
    can misread a digit. The "#a=" string stays in the T5 text, because in the
    workflow it stayed there too and was encoded with the rest.

Fail-closed on purpose: if either interception fails, the caller gets an
exception. Falling back to the raw prompt would produce exactly the run this
restoration exists to end -- one that looks like the original and is not.
"""

import asyncio
import functools
import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)


class SurrealizerPromptError(RuntimeError):
    """Neither prompt may be guessed at, so a failed interception stops the run."""


# Node 69, "Prompt optimization clip_l & clip_g".
CLIP_CONTEXT = 'prompt expert'
CLIP_STYLE_PROMPT = 'YOUR OUTPUT MUST NOT EXCEED 50 WORDS!\nOUTPUT THE PURE PRESULTING PROMPT ONLY!\n\nNEVER INCLUDE ANY META-INFORMATION SUCH AS THE NAMES OF THE DIMENSIONS BELOW OR THE TOKEN COUNT\n\nYou will receive a user prompt for image generation. Restructure it ONLY by reordering, for CLIP models that strongly weight early tokens and truncate at 75 tokens.\n\nGeneral information:\nALWAYS EXTRAKT ONLY THE INFORMATION THAT IS VISUALLY RELEVANT. YOUR PROMPT WILL RESULT IN A COMMA_SEPARATED SERIES OF GROUPED TOKENS; BARELY EVER CONNTECTED BY VERBS OR CONJUNCTIONS.\n\nBUT YOU WILL REORDER ALL THESE TOKENS ACCORDING TO THE FOLLOWING ORDER:\n\nEarly tokens = critical: The first 20–30 tokens largely determine the image\nMinimize Attributes: CLIP struggles with complex attributes – keep them short\nClear, direct terms: CLIP prefers concrete nouns and simple adjectives\nDo not alter the input text – no substitutions, paraphrasing, or lexical replacements allowed\n\n\nYOUR OUTPUT:\nCore Motif: max. 15 words\nPlace the main subject FIRST\nUse the exact wording provided in the original prompt\nEMPTY LINE\nAction: max 20 words\nFollows the subject directly for strong subject-action linkage\nPrefer simple verb phrases; maintain exact original wording\nEMPTY LINE\nStyle/Medium: max 10 words\nPlace early in the prompt for maximum impact on CLIP\nTypical examples: “oil painting”, “photography”, “3D render”\nUse only if present in the original prompt\nEMPTY LINE\nContext: max 10 words\nLocation or setting, compressed\nReorder only; do not paraphrase\nEMPTY LINE\nAttributes: max 10 words:\nMinimize; include only if essential\nNo changes to wording – do not replace or reformulate\nEMPTY LINETechnical Aspects (0–5 tokens, 0–7%):\nInclude only if tokens remain and if originally present\n\nYOUR OUTPUT MUST NOT EXCEED 50 WORDS!\nOMIT the Category names ("Core Motif"), it will only confuse CLIP and reduces the token budget without contributing to image quality. \nNEVER INCLUDE ANY META-INFORMATION SUCH AS THE NAMES OF THE DIMENSIONS BELOW OR THE TOKEN COUNT'

# Node 68, "Prompt optimization t5".
T5_CONTEXT = 'prompting expert'
T5_STYLE_PROMPT = 'YOUR OUTPUT MUST NOT EXCEED 250 WORDS!\n\nTransform the following input text—regardless of genre—into a single, uninterrupted paragraph structured for encoding by a T5 model and subsequent conditioning of a Stable Diffusion 3.5 (or Flux1) image generation model.\n\nYou must retain all original words exactly once: do not omit, duplicate, or paraphrase beyond necessary syntactic adjustments. Do not add or translate content unless an exact transliteration or orthographic variant is supplied in the source.\n\nReorganize the prompt according to the following internal semantic structure, which must guide your composition logic but leave no visible trace in the final output:\n\n    Core subject (approx. 10–30 tokens): Identify and foreground the principal subject matter as fully specified in the source.\n\n    Action (10–40 tokens): Preserve any dynamic, procedural, or temporal structures, expressed clearly through grammatically embedded verb phrases.\n\n    Relational context (30–100 tokens): Expand on spatial relations, historical or cultural frameworks, ecological configurations, embodied perspectives, and temporal situatedness, all inferred from internal content only.\n\n    Attributive qualities (30–80 tokens): Elaborate sensory and atmospheric descriptors—light, surface, sound, temperature, tactility, material behaviour—based on concrete and culturally situated evidence. Avoid cliché mappings such as “melancholy → rain” or “futurism → neon.” Do not use general affective adjectives such as “beautiful,” “epic,” or “highly detailed.” Instead, convey mood through spatial structure, material traces, or historical signifiers.\n\n    Stylistic and medial references (10–40 tokens): If applicable, retain or clarify stylistic provenance using historically anchored terms (e.g., “early Bauhaus sketch,” “Qing-dynasty monochrome ink”). Avoid genre tropes unless explicitly included in the original text.\n\n    Technical parameters (0–20 tokens): Place any camera data, aspect ratio, rendering models, or diffusion-specific settings at the end of the prompt.\nALPHA-VALUE: control the amount of extrapolation and semantik exaggeration of the resulting t5-vectors. For rather unconventional input texts (surreal, phantasy), stay close to 15 or below. For highly conventional inputs, choose values up to 35. Everything in between will be assigned a value between 20 and 25. Output this value in the format "#a=[value] for further parsing.\n\nAdditional requirements:\n– If the input contains explicit negations (e.g., “no neon”), isolate and place them at the end of the prompt after an em dash as a negative prompt clause.\n– If the source uses conflicting descriptors (e.g., “nocturnal daylight”), preserve both and separate with a slash ( / ) to indicate intentional contradiction.\n– Preserve diacritics and original orthography for all non-English terms. Do not transliterate unless a dual form is provided.\n– For ambiguous or poetic language, preserve ambiguity. If metaphors operate structurally (e.g., “grief carved into the orchard”), translate them into spatial/material compositions rather than interpretive paraphrase.\n– If vague temporal expressions appear (e.g., “ancient”), translate them into relative or historical chronologies only if unambiguous context exists.\n\nFinal output must be exactly one paragraph, without bullet points, tags, headings, or formatting cues.\n\nYOUR OUTPUT MUST NOT EXCEED 250 WORDS!'

# Node 70's fallback when the T5 text carries no "#a=".
DEFAULT_ALPHA = 20.0

# The LAST marker wins: the T5 instruction asks for it at the end, and the
# input text is carried through, so an input containing "#a=" of its own must
# not outrank the model's answer. `(?<!\w)` keeps it off the tail of a word.
_ALPHA_RE = re.compile(r"(?<!\w)#a\s*=\s*\[?\s*(-?\d+(?:[.,]\d+)?)")
# The node accepted -75..75 and nothing outside it.
ALPHA_MIN, ALPHA_MAX = -75.0, 75.0


def _intercept(prompt: str, context: str, style_prompt: str, label: str) -> str:
    from schemas.engine.prompt_interception_engine import (
        PromptInterceptionEngine,
        PromptInterceptionRequest,
    )
    import config

    # The node's own envelope, verbatim. Passed as prebuilt_prompt so that
    # build_full_prompt() -- a different order, plus formatting rules the
    # workflow never had -- is bypassed entirely.
    full_prompt = (
        f"Task:\n{style_prompt.strip()}\n\n"
        f"Context:\n{context.strip()}\nPrompt:\n{prompt.strip()}"
    )

    engine = PromptInterceptionEngine()
    pi_request = PromptInterceptionRequest(
        input_prompt=prompt,
        input_context=context,
        style_prompt=style_prompt,
        task_instruction="",
        prebuilt_prompt=full_prompt,
        model=config.STAGE2_INTERCEPTION_MODEL,
        debug=False,
        parameters={"temperature": 0.7},
    )
    pi_response = asyncio.run(engine.process_request(pi_request))
    if not (pi_response.success and pi_response.output_str and pi_response.output_str.strip()):
        raise SurrealizerPromptError(
            f"{label} interception failed: {pi_response.error or 'empty output'}"
        )
    return pi_response.output_str.strip()


def read_alpha(t5_text: str) -> float:
    """The alpha the T5 instruction proposed, or node 70's fallback of 20."""
    found = _ALPHA_RE.findall(t5_text or "")
    if not found:
        return DEFAULT_ALPHA
    value = float(found[-1].replace(",", "."))
    return max(ALPHA_MIN, min(ALPHA_MAX, value))


def build_prompts(user_prompt: str) -> Tuple[str, str, float]:
    """Return (clip_prompt, t5_prompt, proposed_alpha) for one input text."""
    user_prompt = (user_prompt or "").strip()
    if not user_prompt:
        raise SurrealizerPromptError("empty input prompt")
    return _adapted(user_prompt)


# One adaption per prompt, for the life of the process. The two interceptions
# run at the node's temperature 0.7 and answer differently every time, so a
# series over alpha that had them run per generation compared prompts as much
# as alphas. A failed interception raises and is not kept, so
# the next run asks again.
@functools.lru_cache(maxsize=256)
def _adapted(user_prompt: str) -> Tuple[str, str, float]:
    t5_prompt = _intercept(user_prompt, T5_CONTEXT, T5_STYLE_PROMPT, "T5")
    clip_prompt = _intercept(user_prompt, CLIP_CONTEXT, CLIP_STYLE_PROMPT, "CLIP-L")
    proposed_alpha = read_alpha(t5_prompt)

    logger.info(
        "[SURREALIZER-ORIGINAL] clip=%d chars, t5=%d chars, proposed alpha=%s",
        len(clip_prompt), len(t5_prompt), proposed_alpha,
    )
    return clip_prompt, t5_prompt, proposed_alpha
