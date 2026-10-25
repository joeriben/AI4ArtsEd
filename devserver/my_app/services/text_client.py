"""
Text Client — the tokenizer doors of the Latent Text Lab

Stage 5 of the move to ComfyUI: the tokenizer doors ask ComfyUI's HTTP
routes (tokenize, tokenizer_facts, encoder_rows); the coreference contrast,
BBQ, Representation Engineering and the model row (presets) left this client
for services/text_probes and services/text_presets. The calls of the GPU
service's routes no surface named (models, load, unload, embedding,
interpolate, attention, contrast-control, generate, variations, layers) were
struck in stage 8, and on 2026-10-10 the transport to the GPU service this
client had carried for them (_post, _get), which nothing called any more.
"""

import logging
from typing import Optional, List, Dict, Any


logger = logging.getLogger(__name__)


class TextClient:
    """The tokenizer doors, asked of ComfyUI's HTTP routes."""

    def __init__(self):
        from config import GPU_SERVICE_TIMEOUT
        # Connect side only: a model call takes as long as it takes, and a read
        # cap here would return "failed" while the answer is still being written.
        self.timeout = (min(GPU_SERVICE_TIMEOUT, 60), None)
        logger.info(f"[TEXT-CLIENT] Initialized: timeout={self.timeout[0]}s connect")

    # The tokenizers answer on ComfyUI's HTTP server since stage 5 of the move
    # to ComfyUI: the node package registers
    # them there, off the queue, because they read a vocabulary file and run
    # no model. The two calls below take that door; the GPU service's text
    # station went with stage 8 of the move (2026-10-10), and with it the
    # transport this client carried for it.
    @staticmethod
    def _comfyui_url() -> str:
        from config import COMFYUI_URL
        return COMFYUI_URL

    def _comfyui(self, method: str, path: str, data: Optional[dict] = None) -> Optional[dict]:
        """One call to the node package's routes on ComfyUI: the answer, or
        what stopped it, with the status ComfyUI answered. A read cap of 30 s
        stands here: no model is at work behind these routes."""
        import requests
        url = f"{self._comfyui_url()}{path}"
        try:
            if method == "GET":
                resp = requests.get(url, timeout=(self.timeout[0], 30))
            else:
                resp = requests.post(url, json=data, timeout=(self.timeout[0], 30))
        except requests.ConnectionError as e:
            logger.error(f"[TEXT-CLIENT] Nothing answers at {url}: {e}")
            return {"error": "Nothing answers where ComfyUI should be — it is down, or bound to another address.",
                    "http_status": 503}
        except requests.Timeout as e:
            logger.error(f"[TEXT-CLIENT] ComfyUI gave no answer on {path} within 30 s: {e}")
            return {"error": f"ComfyUI gave no answer on {path} within 30 s.", "http_status": 504}
        except requests.RequestException as e:
            logger.error(f"[TEXT-CLIENT] Request to ComfyUI failed: {e}")
            return {"error": f"The request to ComfyUI broke on {path}: {e}"}
        try:
            body = resp.json()
        except ValueError:
            logger.error(f"[TEXT-CLIENT] {path} answered {resp.status_code} with a body that is no JSON")
            if resp.status_code in (404, 405):
                # Where no route is registered, ComfyUI's own static handler
                # answers: 405 for a POST, 404 for a GET, both as plain text.
                return {"error": f"ComfyUI has no route at {path}: the node package did not register "
                                 f"its routes (ComfyUI answered {resp.status_code}).",
                        "http_status": resp.status_code}
            return {"error": f"ComfyUI answered {path} with {resp.status_code} and a body this client "
                             f"can read as no JSON.",
                    "http_status": resp.status_code}
        if not resp.ok:
            said = body.get("error") if isinstance(body, dict) else None
            logger.error(f"[TEXT-CLIENT] {path} answered {resp.status_code}: {said or '(no reason)'}")
            return {"error": said or f"ComfyUI answered {path} with {resp.status_code}",
                    "http_status": resp.status_code}
        if isinstance(body, dict):
            return body
        return {"error": f"ComfyUI answered {path} with {resp.status_code} and a body that is no object.",
                "http_status": 502}

    async def tokenize(self, text: str, model_id: str) -> Dict[str, Any]:
        """One text, one tokenizer, the pieces it falls into.

        No model is loaded for this and no VRAM is asked for — ComfyUI answers
        it out of a vocabulary file, off its queue.
        """
        import asyncio
        return await asyncio.to_thread(
            self._comfyui, "POST", "/ai4artsed/text/tokenize", {"text": text, "model_id": model_id}
        )

    async def tokenizer_facts(self, model_ids: List[str]) -> Dict[str, Any]:
        """Which of these tokenizers ComfyUI's machine has, with their numbers:
        {id: {available, window, matrix}}."""
        import asyncio
        return await asyncio.to_thread(
            self._comfyui, "POST", "/ai4artsed/text/tokenizer-facts", {"model_ids": list(model_ids)}
        )

    async def encoder_rows(self, text: str, t5_min_length: int) -> Dict[str, Any]:
        """The rows of SD 3.5's conditioning table one text fills, per encoder
        (CLIP and T5), as the picture graphs lay them. Two vocabulary files on
        ComfyUI, off its queue; no model."""
        import asyncio
        return await asyncio.to_thread(
            self._comfyui, "POST", "/ai4artsed/text/encoder-rows",
            {"text": text, "t5_min_length": int(t5_min_length)},
        )


# =============================================================================
# Singleton / Factory
# =============================================================================

_client: Optional[TextClient] = None


def get_text_client() -> TextClient:
    """Get TextClient singleton."""
    global _client
    if _client is None:
        _client = TextClient()
    return _client


