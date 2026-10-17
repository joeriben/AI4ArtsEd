"""
Media Analysis client — the readers of the platform's node, run by ComfyUI.

Every reading is one prompt of the node ai4artsed_media_reading
(comfyui_nodes/ai4artsed_comfyui/): the file is put into ComfyUI's input
directory (services/llm_client.upload_input), the node is queued and tracked
the way a local language model is (llm_client.run_node), and the copy is
taken out of that directory again once the run has ended. Which reader
answers which task -- MiDashengLM for a recording, HeartTranscriptor for
the words, CLAP and MuQ-MuLan for the ranking, the vision model for a
picture or a video -- and what each is told is the reading block of the
table config/local_media_weights.json (services/local_media_weights). Until
stage 6 of the move to ComfyUI this posted to the GPU
service's /api/analysis/* stations; the methods are the ones the callers
had then (the cover band's chain, the VLM comparison, the flow's reading of
a run's sound or video).

Same shape as before: synchronous, one method per reading, no business
logic. The DevServer orchestrates; this only carries.

What comes back is not what it looks like, and callers have to carry that
into whatever they show:

- transcribe() on audio with no words in it does not return an empty string.
  It returns a short, fluent, confident sentence. Room noise produced
  "1. No triggerpull is required."; digital silence produced "you".
- tag() has no abstain. Cosine similarity always yields an order, so silence
  is ranked as confidently as a song. A result is "the best match inside the
  list we passed", never "what this is".

Measured 2026-08-05, see docs/analysis/HEARTTRANSCRIPTOR_raumaufnahme_test_2026-08-04.md.
"""

import json
import logging
import os
import uuid
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NODE_CLASS = "ai4artsed_media_reading"
STATION = "media_reading"

# Why the last call came back empty, for the caller that has to say something.
# A ContextVar rather than an attribute: the client is one shared object and
# the requests arrive on independent threads, so an attribute would hand one
# caller another caller's reason.
LAST_REASON: "ContextVar[str]" = ContextVar("analysis_last_reason", default="")
# And the HTTP status that says which side it was (llm_client.node_failure_status).
LAST_STATUS: "ContextVar[int]" = ContextVar("analysis_last_status", default=500)


def last_reason() -> str:
    """What went wrong in the last call on this thread, in words to show."""
    return LAST_REASON.get("")


def last_status() -> int:
    """The status a route answers the last failure of this thread with."""
    return LAST_STATUS.get(500)


class MediaAnalysisClient:
    """The readers on ComfyUI, through the platform's node."""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # The one way every reading goes.

    def _read(self, task: str, path: str, **inputs) -> Optional[Dict[str, Any]]:
        """One prompt of the node for `task` over the file at `path`: what the
        node wrote (its ui outputs), or None with the reason in LAST_REASON.

        The file goes up under a name of its own, so that two readings of
        files that share a name never overwrite each other, and comes down
        again whichever way the run ended: a recording of people has no
        business lying in ComfyUI's input directory past its reading.
        """
        from config import COMFYUI_BASE_PATH
        from my_app.services import local_media_weights
        from my_app.services.llm_client import LLMClient, node_failure_status, upload_input
        LAST_REASON.set("")
        LAST_STATUS.set(500)
        try:
            alias, model_dir = local_media_weights.reader_dir(task)
        except KeyError as e:
            logger.error(f"[ANALYSIS-CLIENT] {task}: {e}")
            LAST_REASON.set(f"No reader is configured for {task}.")
            return None
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            logger.error(f"[ANALYSIS-CLIENT] {task}: cannot read {path}: {e}")
            LAST_REASON.set("The file to read could not be opened.")
            return None
        name = f"ai4artsed_read_{uuid.uuid4().hex}{os.path.splitext(path)[1].lower()}"
        try:
            stored = upload_input(data, name)
        except Exception as e:
            logger.error(f"[ANALYSIS-CLIENT] {task}: upload to ComfyUI failed: {e}")
            LAST_REASON.set(f"The file could not be handed to ComfyUI: {str(e)[:200]}")
            LAST_STATUS.set(node_failure_status(e))
            return None
        try:
            return LLMClient.run_node(NODE_CLASS, {"task": task, "model_name": model_dir,
                                                   "file": stored, **inputs})
        except Exception as e:
            reason = str(e) or type(e).__name__
            # A caller that names its model (both rankers of the cover band do)
            # replaces the table's reader; the line names the one that ran.
            ran = inputs["model_name"] if "model_name" in inputs else alias
            logger.error(f"[ANALYSIS-CLIENT] {task} with {ran} failed: {reason}")
            LAST_REASON.set(reason[:300])
            LAST_STATUS.set(node_failure_status(e))
            return None
        finally:
            try:
                os.remove(os.path.join(COMFYUI_BASE_PATH, "input", stored))
            except OSError as e:
                logger.warning(f"[ANALYSIS-CLIENT] the copy {stored} stays in ComfyUI's input directory: {e}")

    def is_available(self) -> bool:
        """Whether the readers can be asked at all: the station's library
        imports in ComfyUI's venv and a reader is installed."""
        from my_app.services import media_stations
        try:
            return media_stations.available(STATION)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # The readings.

    def transcribe(self, path: str,
                   language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """The words the model produces for this recording, and in what language.

        Returns {"text": str, "language": str | None}. The language is the
        model's own guess, made before any word was chosen -- see the note on
        transcribe in the package's _media_reading.
        """
        out = self._read("lyrics", path, language=language or "")
        if out is None:
            return None
        return {"text": str(out.get("text") or ""), "language": (out.get("language") or None)}

    def tag(self, path: str, labels: Optional[List[str]] = None,
            model: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Full ranking of `labels` against the recording, best first.

        Returns the whole list including the tail -- what a model puts last is
        a statement about its own vocabulary, and the page shows it.

        `model` names which ranker answers, by its alias in the table. Left
        out, the table's reader for music_tags answers; the cover band names
        both of its machines explicitly, because the page says which one
        produced which list. `labels` left out is the table's vocabulary.
        """
        from my_app.services import local_media_weights
        inputs: Dict[str, Any] = {
            "labels": json.dumps(list(labels) if labels else local_media_weights.music_tag_vocabulary()),
            "center": local_media_weights.center_label_embeddings(),
        }
        if model:
            model_dir = local_media_weights.dir_name(model)
            if not model_dir:
                logger.error(f"[ANALYSIS-CLIENT] {model!r} is no ranker of the table")
                LAST_REASON.set(f"{model} is not a ranker this installation knows.")
                return None
            inputs["model_name"] = model_dir
        out = self._read("music_tags", path, **inputs)
        if out is None:
            return None
        try:
            tags = json.loads(out.get("tags") or "[]")
        except ValueError:
            LAST_REASON.set("The ranking came back unreadable.")
            return None
        return tags if isinstance(tags, list) else []

    def describe_image(self, path: str, prompt: Optional[str] = None) -> Optional[str]:
        """Reading of a still image by the table's image reader (the same
        weights as the video reading).

        The prompt is the caller's reading frame; without one the table's
        restrained default is used.
        """
        from my_app.services import local_media_weights
        out = self._read("image", path, prompt=prompt or local_media_weights.prompt("image"))
        return None if out is None else str(out.get("analysis") or "")

    def describe_video(self, path: str, prompt: Optional[str] = None) -> Optional[str]:
        """Reading of a video by the table's video reader, frames sampled
        the way the station samples them."""
        from my_app.services import local_media_weights
        out = self._read("video", path, prompt=prompt or local_media_weights.prompt("video"))
        return None if out is None else str(out.get("analysis") or "")

    def describe(self, path: str, prompt: Optional[str] = None) -> Optional[str]:
        """Prose description of the recording (MiDashengLM).

        Used as a gate, not as a station: it is the only one of the three that
        answers "There is nothing." to an empty room. It also attributes gender
        and age to voices even when told not to, so its text must not be shown
        over recordings of people.
        """
        from my_app.services import local_media_weights
        out = self._read(
            "audio", path,
            prompt=prompt or local_media_weights.prompt("audio"),
            system_prompt=local_media_weights.prompt("audio_system"),
            trust_remote_code=local_media_weights.reader_trusts_remote_code("audio"))
        return None if out is None else str(out.get("analysis") or "")


_client: Optional[MediaAnalysisClient] = None


def get_media_analysis_client() -> MediaAnalysisClient:
    global _client
    if _client is None:
        _client = MediaAnalysisClient()
    return _client
