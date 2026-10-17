#!/usr/bin/env python3
"""
VoxCPM2 worker — the synthesiser that is asked for a voice in words.

Runs OUTSIDE the platform's environment and answers over localhost. Not a
preference: `voxcpm` pins `datasets>=3,<4` and `gradio>=6,<7` against the
platform's 4.5.0 and 5.50.0, so installing it alongside would downgrade the one
and upgrade the other under everything else that uses them. Qwen3-TTS was lost
to exactly that class of move — a transformers upgrade elsewhere in the same
environment, 2026-08-12 — and that loss is the reason this model is here.
`download_voxcpm.sh` builds the environment this file runs in; it is started by
`2_start_voxcpm.sh`, and the platform starts it by itself when it is needed.

Piper is reached out of process too, but per utterance: the `piper` binary
starts, speaks, exits. That cannot work here. This is a 2 B model on the GPU
and loading it costs about 25 seconds against 0.3 seconds of generation, so the
process stays up and holds it.

WHAT IT ANSWERS

    GET  /health   {"ok": true, "loaded": bool, "gate": "waiting"|"held"|..., ...}
    POST /speak    {"text": "...", "description": "..."} -> audio/wav

The audio comes back as the model wrote it: 48 kHz, no loudness applied.
Finishing it is the platform's job and happens for all three synthesisers in
the same code (`speech_audio.to_wav`) — a comparison between differently
normalised audio is a comparison of the normalisation.

HOW IT IS ASKED FOR A VOICE

The description is not a parameter. It goes inside the text, in parentheses, in
front of the sentence:

    (A young woman, gentle and sweet voice)Guten Tag.

So the model receives one string and has to decide for itself which part is an
instruction about speaking and which part is what to speak. That property is
the reason this synthesiser stands next to the other two, and it is not a
reason to trust the outcome: it is measured here, not assumed. Left empty, the
model reads the prosody off the sentence itself and nothing is asked at all.

Because the parenthesis is the whole delimiter, a sentence that itself begins
with "(" would silently become an instruction and never be spoken. That is
refused rather than guessed at — see `_compose`.

WHAT IT DOES NOT DO

VoxCPM2 can clone a voice from a few seconds of recording. Nothing here reaches
that: `prompt_wav_path` and `reference_wav_path` are never set, and no path
from the platform can set them. Whether a platform used by children in
workshops should offer voice cloning at all is an open question, and it is not
one this file may answer by quietly making it reachable.

WHO ADMITS IT TO THE CARD

The weights land on the card in THIS process, so this process asks for the
card's turn before loading them: the DevServer's gate hands it out over HTTP
(POST /api/gate/lease/acquire, heartbeat, release), the same way the GPU
service asks for its holds. The gate is found the way the GPU service finds
it: AI4ARTSED_DEVSERVER_URL, else http://127.0.0.1:<PORT>, PORT being the
variable the DevServer reads and 17802 its default (a production backend
answers on 17801; a worker started by hand there needs PORT in its
environment). A gate that does not answer is asked again, at a growing gap,
for as long as it takes: without a DevServer there is nobody to speak for,
and /health says "gate": "waiting" meanwhile. Until 2026-10-10 the DevServer
took this lease around starting the worker, and only when it started it: a
worker started by hand put 6774 MiB on the card that the coordinator learned
of only when the next hold measured them as foreign (S-005).
"""

import contextlib
import http.client
import io
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VOXCPM] %(levelname)s %(message)s",
)
logger = logging.getLogger("voxcpm_worker")

HOST = os.environ.get("VOXCPM_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOXCPM_PORT", "17805"))
MODEL_ID = os.environ.get("VOXCPM_MODEL_ID", "openbmb/VoxCPM2")

# The two settings the model card documents. Its own examples use these values.
DEFAULT_CFG = float(os.environ.get("VOXCPM_CFG", "2.0"))
DEFAULT_TIMESTEPS = int(os.environ.get("VOXCPM_TIMESTEPS", "10"))

# One GPU, one resident model, one generation at a time. Requests arrive on
# independent handler threads; two concurrent generate() calls would share the
# model's mutable state.
_gpu_lock = threading.Lock()

# --- the card's gate ---------------------------------------------------------
# What this process holds once its model is up, measured on the dev card
# rather than taken off a model card: 6774 MiB, 2026-08-26.
VRAM_MB = int(os.environ.get("VOXCPM_VRAM_MB", "6774"))
# What this process calls itself on the DevServer's gate: the holder the lease
# carries. (The settings row reads "in use" from the lease's KIND, which
# starts with the process label voxcpm, not from this name.)
GATE_HOLDER = "voxcpm_service"
GATE_HEARTBEAT_S = 10.0
GATE_RETRY_GAP_S = 2.0
GATE_RETRY_CEILING_S = 30.0
_DEVSERVER_DEFAULT_PORT = "17802"
# unasked | waiting | held | absent | released, reported over /health.
_gate_state = "unasked"

_model = None
_sample_rate = 0
_max_length = 0
_load_error = ""

# Positions kept free at the end of the model's context. Text tokens and audio
# frames share it, and the last frames of an utterance are the ones that would
# be lost, so the room is left rather than used to the last position.
CONTEXT_HEADROOM = 64

# Never below this many audio frames, whatever the arithmetic says: a text that
# fills the context has to come out as something audible rather than as a
# fragment.
MIN_AUDIO_FRAMES = 256

# The library's own retry_badcase_ratio_threshold. Kept as the floor: below it
# the model's guard against runaway generation would be weakened, and that is
# not what is being changed here.
DEFAULT_RATIO = 6.0

# HOW MUCH TEXT GOES INTO ONE PASS
#
# VoxCPM2 reads a long text faster than a short one and keeps getting faster the
# longer it runs. On the Bremen tale it read at roughly two to three times the
# pace it should. The same is reported in the model's own forum, and the
# maintainers have an open issue for it (OpenBMB/VoxCPM#297) with no answer.
#
# It is NOT this service's arithmetic and NOT the context running out. The
# technical report gives the numbers: the audio autoencoder runs at 25 Hz, four
# of its frames make one patch, so the language model produces 6.25 steps per
# second and one step is 160 ms of audio. The German tale is 978 text tokens, so
# `max_len` below comes to 7150 steps — nineteen minutes of audio allowed for a
# recording that came out at eighty-five seconds. The ceiling stands thirteen
# times above what is used. It never bites.
#
# What the makers themselves prescribe for long text is to split it and join the
# waveforms (usage guide, "Long-form"). That is what happens here.
#
# The shape of the cut: sense units, as large as they can be while the pace
# holds, and NOT one sentence at a time. So whole
# sentences are gathered until the next one would burst the segment, and a cut
# inside a sentence happens only when a single sentence is longer than the
# ceiling on its own, at the strongest punctuation it offers.
#
# The two numbers are in TEXT TOKENS, the model's own unit. Their warrant is one
# measurement: the opening of the Bremen tale, 138 tokens, reads at a calm pace.
# Nothing establishes where exactly the pace starts to go — that would take a
# run per length, and the numbers are the knob to turn when it is worth it.
SEGMENT_TARGET_TOKENS = 150
SEGMENT_MAX_TOKENS = 220

# Where a segment may end, strongest first. A sentence end takes any number of
# closing quotes with it — in German the period stands INSIDE the closing quote
# ("werden.'"), and a rule that looks only for the period cuts in the wrong
# place. The second row is for the sentence that is too long by itself.
_CLOSERS = "'\"\u00bb\u00ab\u201c\u201d\u201e\u2019\u203a\u2039\uff02\uff07"
_SENTENCE_END = re.compile(
    r"[.!?\u061f\u06d4\u3002\uff01\uff1f\u2026][" + re.escape(_CLOSERS) + r"]*\s+"
)
_CLAUSE_END = re.compile(
    r"[;:,\u060c\u061b\u3001\uff1b\uff0c][" + re.escape(_CLOSERS) + r"]*\s+"
)


def gate_url() -> str:
    url = os.environ.get("AI4ARTSED_DEVSERVER_URL", "").strip()
    if not url:
        url = "http://127.0.0.1:%s" % os.environ.get("PORT", _DEVSERVER_DEFAULT_PORT)
    return url.rstrip("/")


def _gate_post(path, body, timeout):
    """(status, payload dict) of one POST to the gate. Not answering raises."""
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        gate_url() + path, data=data, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except ValueError:
        payload = {}
    return status, (payload if isinstance(payload, dict) else {})


def _acquire(kind, model_id, required_mb, label, workload):
    """The gate's token, once the turn is ours; "" where the DevServer has no
    gate routes (HTTP 404: a build from before stage 7, then the hold goes
    ahead, said once). Asked again at a growing gap while the gate does not
    answer or refuses: the answer to a granted turn comes when it is ours,
    so the acquire itself has no read bound."""
    global _gate_state
    body = {"kind": kind, "model_id": model_id, "required_mb": float(required_mb),
            "label": label, "workload": workload, "holder": GATE_HOLDER}
    gap = GATE_RETRY_GAP_S
    said = ""
    _gate_state = "waiting"
    while True:
        try:
            status, payload = _gate_post("/api/gate/lease/acquire", body, timeout=None)
        # http.client raises its own family for a torn answer (IncompleteRead,
        # BadStatusLine); none of them is an OSError, and until 2026-10-10 one
        # ended the load for good (second review of the same day).
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
            sentence = ("The DevServer's gate at %s did not answer (%s: %s); asked again"
                        % (gate_url(), type(e).__name__, e))
            if sentence != said:
                logger.warning(sentence)
                said = sentence
            time.sleep(gap)
            gap = min(gap * 2, GATE_RETRY_CEILING_S)
            continue
        if status == 200 and payload.get("token"):
            _gate_state = "held"
            logger.info("The card's turn is ours (%s/%s, %.0f MiB)", kind, model_id, required_mb)
            return str(payload["token"])
        if status == 404:
            _gate_state = "absent"
            logger.warning("The DevServer at %s has no gate routes; loading without a lease",
                           gate_url())
            return ""
        reason = payload.get("detail") or payload.get("error") or "HTTP %s" % status
        sentence = "The DevServer's gate refused the turn (%s); asked again" % reason
        if sentence != said:
            logger.warning(sentence)
            said = sentence
        time.sleep(gap)
        gap = min(gap * 2, GATE_RETRY_CEILING_S)


def _keep_alive(token, stop):
    """One heartbeat per interval while the hold lasts. A 404 means the gate
    no longer knows the lease (its reaper collected it, or the DevServer
    restarted): the load runs on without the guarantee, said once."""
    while not stop.wait(GATE_HEARTBEAT_S):
        try:
            status, _ = _gate_post("/api/gate/lease/heartbeat", {"token": token}, timeout=5)
        except Exception as e:  # noqa: BLE001 — a heartbeat may not end a load
            logger.warning("The lease %s could not be kept alive (%s: %s); asked again",
                           token, type(e).__name__, e)
            continue
        if status == 404:
            if stop.is_set():
                return  # released meanwhile; a beat in flight met the gone lease
            logger.error("The lease %s is gone: the gate no longer knows it; this load "
                         "no longer holds the card's turn", token)
            return


def _release(token, failed):
    try:
        status, _ = _gate_post("/api/gate/lease/release",
                               {"token": token, "failed": bool(failed)}, timeout=10)
    except Exception as e:  # noqa: BLE001 — the gate's reaper collects what is left
        logger.warning("The lease %s could not be given back (%s: %s); the gate's reaper "
                       "collects it", token, type(e).__name__, e)
        return
    if status != 200:
        logger.warning("The gate answered HTTP %s to the release of %s", status, token)


@contextlib.contextmanager
def gpu_lease(kind, model_id, required_mb, label="", workload=""):
    """The card's turn for what runs inside, with its heartbeat; given back on
    the way out. The same shape as the DevServer's gpu_lease_client, in stdlib,
    because this process has no requests and no my_app."""
    global _gate_state
    token = _acquire(kind, model_id, required_mb, label, workload)
    stop = threading.Event()
    if token:
        threading.Thread(target=_keep_alive, args=(token, stop),
                         name="voxcpm-gate-heartbeat", daemon=True).start()
    failed = False
    try:
        yield token
    except BaseException:
        failed = True
        raise
    finally:
        stop.set()
        if token:
            _release(token, failed)
        if _gate_state == "held":
            _gate_state = "released"


def _load():
    """Bring the model up. Runs in its own thread so /health answers meanwhile.

    The socket is bound before this finishes on purpose: a caller waiting for
    the worker has to be able to tell "still loading" from "not there", and a
    port that refuses connections says neither.
    """
    global _model, _sample_rate, _max_length, _load_error
    try:
        from voxcpm import VoxCPM

        logger.info(f"Loading {MODEL_ID} ...")
        # The weights go on the card inside this hold (see WHO ADMITS IT TO
        # THE CARD above); the import before it allocates nothing there.
        with gpu_lease("voxcpm-load", "voxcpm", VRAM_MB, label="VoxCPM2 worker",
                       workload="voxcpm:load"):
            # The denoiser is for cleaning up reference recordings before
            # cloning. Nothing here clones, so it is never loaded.
            model = VoxCPM.from_pretrained(MODEL_ID, load_denoiser=False)
            _sample_rate = int(model.tts_model.sample_rate)
            # The model's own ceiling, read off the model rather than assumed.
            # Its KV cache is set up for exactly this many positions.
            _max_length = int(model.tts_model.config.max_length)
            _model = model
        logger.info(f"Loaded. {_sample_rate} Hz, {_max_length} positions.")
    except Exception as e:  # noqa: BLE001 — reported over /health, not swallowed
        _load_error = f"{type(e).__name__}: {e}"
        logger.error(f"Load failed: {_load_error}", exc_info=True)


def _compose(text: str, description: str) -> str:
    """The one string the model is handed.

    Raises ValueError when the utterance would be eaten by the delimiter.
    """
    said = (text or "").strip()
    if not said:
        raise ValueError("No text to speak")

    # A parenthesis inside the description would close the block early and put
    # the rest of it into the utterance, where it would be read out loud.
    wanted = (description or "").replace("(", " ").replace(")", " ").strip()

    if wanted:
        return f"({wanted}){said}"
    if said.startswith("("):
        raise ValueError(
            "This sentence begins with '(' and no voice was described. "
            "VoxCPM2 reads a leading parenthesis as an instruction about the "
            "voice and does not speak it, so the sentence would be lost.")
    return said


def _count(text: str) -> int:
    """Text tokens, in the model's own tokenizer."""
    return len(_model.tts_model.text_tokenizer(text))


def _pieces(text: str, boundary) -> list:
    """Split at a boundary, keeping the punctuation and the space with the left
    side. A text with no boundary in it comes back whole."""
    out, last = [], 0
    for m in boundary.finditer(text):
        out.append(text[last:m.end()])
        last = m.end()
    if last < len(text):
        out.append(text[last:])
    return out or [text]


def _segments(text: str) -> list:
    """Sense units, as large as they can be while the pace holds.

    Whole sentences are gathered while they fit. A sentence that is over the
    ceiling by itself is cut at its own clause punctuation; one that is over it
    even then is handed over whole, because a cut inside a clause would be
    audible as a cut and the pace is the cheaper loss.
    """
    units = []
    for sentence in _pieces(text, _SENTENCE_END):
        if _count(sentence) <= SEGMENT_MAX_TOKENS:
            units.append(sentence)
            continue
        run = ""
        for clause in _pieces(sentence, _CLAUSE_END):
            if run and _count(run + clause) > SEGMENT_MAX_TOKENS:
                units.append(run)
                run = clause
            else:
                run += clause
        if run:
            units.append(run)

    segments, run = [], ""
    for unit in units:
        if run and _count(run + unit) > SEGMENT_TARGET_TOKENS:
            segments.append(run.strip())
            run = unit
        else:
            run += unit
    if run.strip():
        segments.append(run.strip())
    return segments or [text]


def _speak(text: str, description: str, cfg: float, timesteps: int) -> bytes:
    """Speak once and return a 48 kHz WAV, unnormalised.

    A short text is one pass, as before. A long one is spoken in sense units,
    each one handed the PREVIOUS one as its anchor — the library's continuation
    mode, `prompt_text` plus the audio features that came back with it. So the
    voice, the pace and the reading carry across a cut; what a segment cannot
    see is the text still to come. That is the real cost of this, and it is the
    trade the makers' own long-form guidance asks for (see the note above).
    """
    import numpy as np
    import soundfile as sf
    import torch

    if _model is None:
        raise RuntimeError(_load_error or "Model is still loading")

    # What the library does to the text before it ever reaches the model. Done
    # here so the segments are cut on the string the model will actually see.
    said = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
    _compose(said, description)  # raises on the cases that would be swallowed

    tts = _model.tts_model
    segments = _segments(said)

    logger.info(f"{len(said)} chars | {_count(said)} tokens | "
                f"{len(segments)} segment(s) | described={bool(description.strip())} | "
                f"cfg={cfg} | timesteps={timesteps}")

    waves = []
    cache = None
    with _gpu_lock:
        # No timeout anywhere on these calls: they are model calls, and a cap
        # here would cut an utterance off mid-sentence rather than let it finish.
        for index, segment in enumerate(segments):
            # The voice is described to the first segment only. After that the
            # anchor carries it — that is what the anchor is for, and repeating
            # the description would put an instruction in the middle of a
            # reading that the model has already been given.
            target = _compose(segment, description) if index == 0 else segment

            anchor_tokens = _count(cache["prompt_text"]) if cache else 0
            anchor_frames = cache["audio_feat"].size(0) if cache else 0
            seen = _count(target) + anchor_tokens + anchor_frames
            max_len = max(MIN_AUDIO_FRAMES, _max_length - seen - CONTEXT_HEADROOM)
            ratio = max(DEFAULT_RATIO, (max_len - 10) / max(_count(target), 1))

            audio, _tokens, feat = tts.generate_with_prompt_cache(
                target_text=target,
                prompt_cache=cache,
                inference_timesteps=timesteps,
                cfg_value=cfg,
                max_len=max_len,
                retry_badcase=True,
                retry_badcase_ratio_threshold=ratio,
            )
            waves.append(np.asarray(audio.detach().cpu(), dtype=np.float32).reshape(-1))

            # Only the segment just spoken becomes the anchor. `merge_prompt_cache`
            # would keep every earlier one as well, which is how the library
            # stabilises a voice — and it would rebuild exactly the long sequence
            # this is here to avoid. The features go to the CPU because the cache
            # is concatenated with CPU tensors on the way in.
            cache = tts.merge_prompt_cache(
                None, segment, feat.detach().to("cpu", torch.float32))

    wav = waves[0] if len(waves) == 1 else np.concatenate(waves)

    buffer = io.BytesIO()
    sf.write(buffer, wav, _sample_rate, format="WAV", subtype="FLOAT")
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: A003 — BaseHTTPRequestHandler API
        logger.debug(fmt % args)

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler API
        if self.path.rstrip("/") != "/health":
            self._json(404, {"error": "not found"})
            return
        self._json(200, {
            "ok": True,
            "loaded": _model is not None,
            "error": _load_error,
            "gate": _gate_state,
            "model": MODEL_ID,
            "sample_rate": _sample_rate,
            "cfg_value": DEFAULT_CFG,
            "inference_timesteps": DEFAULT_TIMESTEPS,
        })

    def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler API
        if self.path.rstrip("/") != "/speak":
            self._json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:  # noqa: BLE001
            self._json(400, {"error": f"unreadable request: {e}"})
            return

        try:
            audio = _speak(
                str(data.get("text") or ""),
                str(data.get("description") or ""),
                float(data.get("cfg_value") or DEFAULT_CFG),
                int(data.get("inference_timesteps") or DEFAULT_TIMESTEPS),
            )
        except ValueError as e:
            # The caller's sentence, not a failure of the model.
            self._json(400, {"error": str(e)})
            return
        except Exception as e:  # noqa: BLE001
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            self._json(503, {"error": f"{type(e).__name__}: {e}"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)


def main() -> int:
    logger.info("The card's gate: %s (AI4ARTSED_DEVSERVER_URL, else PORT)", gate_url())
    threading.Thread(target=_load, name="voxcpm-load", daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    logger.info(f"Listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
