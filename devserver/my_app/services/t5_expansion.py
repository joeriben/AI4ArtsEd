"""T5 prompt expansion — shared helper (Surrealizer / Fusion Workbench).

CLIP receives the short literal prompt; T5 receives a richer, longer text whose
512-token tail carries content CLIP cannot. This runs the Stage-2 interception
model with a fixed instruction to produce that enrichment.

Returns the expansion text only (the ~200 added words). Callers build the T5
prompt as ``prompt + " " + expansion``. Fail-open: returns None on any failure,
so callers fall back to the plain prompt.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

T5_EXPANSION_INSTRUCTION = (
    "Expand this prompt into a rich narrative paragraph (~200 words). "
    "Add: mood, atmosphere, sensory details, emotional depth, spatial context, associations. "
    "Do NOT repeat the original prompt — only add new content that enriches and deepens it. "
    "Write in the same language as the input. Output ONLY the expansion text, nothing else."
)


def expand_t5(prompt: str) -> Optional[str]:
    """Return the ~200-word T5 expansion for ``prompt``, or None on failure."""
    prompt = (prompt or "").strip()
    if not prompt:
        return None
    try:
        from schemas.engine.prompt_interception_engine import (
            PromptInterceptionEngine,
            PromptInterceptionRequest,
        )
        import config

        engine = PromptInterceptionEngine()
        pi_request = PromptInterceptionRequest(
            input_prompt=prompt,
            input_context="",
            style_prompt=T5_EXPANSION_INSTRUCTION,
            task_instruction="",
            model=config.STAGE2_INTERCEPTION_MODEL,
            debug=False,
        )
        pi_response = asyncio.run(engine.process_request(pi_request))
        if pi_response.success and pi_response.output_str:
            return pi_response.output_str.strip()
        logger.warning(f"[t5_expansion] failed: {pi_response.error}")
        return None
    except Exception as e:
        logger.warning(f"[t5_expansion] error (fail-open): {e}")
        return None
