"""
Measured facts about what a model can actually be handed, per capability.

The platform used to answer that from the provider prefix -- anything under a cloud
prefix was assumed to see images. The guess was wrong for the model that was then
configured as CHAT_HELPER_MODEL, which answers

    HTTP 404 "No endpoints found that support image input"

and that answer is final rather than retriable, so every ChatOverlay and surrealizer
image turn died with a 500 instead of falling back to a local description.

This module replaces the guess with a measurement. Settings sends the model a probe
the platform builds itself and reads the answer; the verdict is written down; the
request path only ever reads what was written. Nothing asks a provider what its
models can do while a workshop is running, so an unreachable provider cannot make the
platform forget what it already knows.

What a role needs of its model is a vocabulary (CAPABILITIES); two of its entries can
be measured, because both are required by some roles and not by others, and both fail
silently when the wrong model is assigned:

  image  the model is handed the picture itself. Without it the chat answers from a
         description the local vision model wrote, so anything the description leaves
         out cannot be asked about.
  tools  the model may call the platform's functions. Without it Resona and the idea
         development mode simply never act -- they talk about what they would do.

Three floors stand above every measurement, because they are properties of the
transport rather than of the model, and no probe can lift them:

  image_input     a provider whose entry in config/llm_providers.json says
                  "image_input": false is not handed the picture: the reader
                  (stream_chat in openai_style_stream) builds the request
                  without it. IONOS is the one so declared.
  local + tools   LLMClient.chat accepts `tools` and ignores it, in its own words:
                  "the local llama-server engine does not support these legacy features".
  local + blind   the same client catches every exception and returns None, so a
                  model that takes no image, a model that is not installed and a VRAM
                  shortage arrive identically. A correct reading proves sight;
                  nothing available there disproves it, so no local "cannot" is ever
                  written for image.
"""

import base64
import glob
import io
import json
import logging
import random
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# Per-installation, therefore gitignored -- and deliberately NOT a key inside
# user_settings.json: POST /api/settings/ rewrites that file from the keys the form
# renders, so anything else stored there is deleted on the next save.
STORE_FILE = Path(__file__).resolve().parent.parent.parent / "model_capabilities.json"

# The vocabulary of things a role can need from its model. Fixed order, because the
# Settings table renders it as a row of slots under a shared header: the same position
# means the same requirement in every row, so a column can be read downwards.
#
# Not every entry is claimed by a role today. sound, video and three_d are here as
# places, not as findings: no model on this platform is currently handed audio, video
# or geometry -- those media are produced in ComfyUI and no LLM reads them back. They
# keep their slot so that the day one does, the row says so instead of the vocabulary
# having to be reopened.
CAPABILITIES = ("image", "sound", "video", "three_d", "coding", "thinking", "tools")

# What can be measured. Every requirement a role actually holds has a probe, because a
# slot that says a requirement is needed and then says nothing about whether the model
# meets it leaves the operator with the question they came with.
#
# sound, video and three_d have none, and none is invented for them: no role hands a
# model audio, video or geometry, so no row asks and no slot stays open.
MEASURABLE = ("image", "tools", "thinking", "coding")

# Which role needs what. Each entry is a claim about a line of code, never about the
# family a model belongs to:
#   image     the gate in chat_routes that decides whether the picture itself is handed
#             over (CHAT_HELPER_MODEL / PERSONA_MODEL / RESONA_MODEL), and
#             vision_support.describe_image_for_fallback plus llm_service, which run the
#             local analysis (IMAGE_ANALYSIS_MODEL). The image check is no row here: it
#             asks SAFETY_MODEL, a classifier that answers no chat probe, and the GPU
#             service refuses any model its registry does not declare a classifier.
#   tools     chat_routes attaches tool definitions for Resona (scoped) and for the
#             modes that formerly carried INTERFACE_REFERENCE, which is the idea
#             development mode. No other role is handed one.
#   thinking  chat_routes calls those same conversational roles with
#             enable_thinking=True unless a compare mode switches it off. The probe
#             asks the same way and looks for a reasoning channel in the answer: what
#             is measured is what the platform gets, not what the model does inside.
#   coding    CODING_MODEL is the role that writes Tone.js and p5.js.
ROLE_REQUIREMENTS = {
    "CHAT_HELPER_MODEL": ("image", "thinking"),
    "PERSONA_MODEL": ("image", "thinking", "tools"),
    "RESONA_MODEL": ("image", "thinking", "tools"),
    "IMAGE_ANALYSIS_MODEL": ("image",),
    "CODING_MODEL": ("coding",),
}


# ---------------------------------------------------------------- the image probe

# Five digits, not two. A model answering without having seen anything guesses a
# two-digit value about 1 in 90 times, and a blind control run in fact answered
# "1234567890", which contains 9 of the 90 two-digit values; the same answer carries
# 6 of the 90000 five-digit ones.
TEST_DIGITS = 5

IMAGE_QUESTION = (
    "Which number is written in this image? "
    "Answer with the digits only, nothing else."
)

# Sentences in which a provider states that the model takes no image. ONLY an exact
# phrase from this list may be recorded as a refusal. Keying on a status code plus the
# word "image" would also match "Invalid image data", which is an encoding fault on a
# model that sees perfectly well -- and the false negative is the expensive direction:
# it routes every image turn through the local description for good, silently.
# Dropped from this list on 2026-08-13: "does not support image". It also matches
# "does not support image_url content parts", which is a complaint about how the image
# was packed -- raised by providers about models that see perfectly well. Filing that as
# a refusal routes every image turn through the local description for good.
# Added 2026-09-22: Mistral's wording for a model that takes none, measured as
# HTTP 400 {"message": "Image input is not enabled for this model", "code": "3051"}
# on zai-glm-5-3. It names what the model is configured to accept, not how the
# picture was packed, so it does not carry the hazard that got "does not support
# image" dropped. Without the line the probe answered "unclear" and recorded
# nothing, so the row for a model that plainly cannot see stayed unchecked and
# every re-probe spent another call on it.
IMAGE_REFUSAL_PHRASES = (
    "no endpoints found that support image input",
    "image input is not supported",
    "image input is not enabled",
    "does not support image input",
    "vision is not supported",
)

# ---------------------------------------------------------------- the tools probe

TOOL_NAME = "report_number"

TOOL_DEFINITION = [{
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Report a single number back to the platform.",
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "integer", "description": "the number to report"}},
            "required": ["value"],
        },
    },
}]

TOOLS_QUESTION = (
    f"Call the {TOOL_NAME} tool with the value 7. "
    "Do not answer in prose; use the tool."
)

TOOLS_REFUSAL_PHRASES = (
    "does not support tool",
    "tool use is not supported",
    "function calling is not supported",
    "tools are not supported",
    "no endpoints found that support tool use",
)

# ------------------------------------------------------------- the thinking probe

# Any question will do -- what is measured is whether a reasoning channel comes back,
# not whether the answer is right. A question with one step in it makes an empty
# channel mean something: there was something to think about.
THINKING_QUESTION = (
    "A shelf holds three boxes. Each of them holds two more. "
    "How many boxes are there in total? Answer with the number only."
)

THINKING_REFUSAL_PHRASES = (
    "does not support thinking",
    "does not support reasoning",
    "reasoning is not supported",
    "thinking is not supported",
)

# ------------------------------------------------------------- the coding probe

CODING_QUESTION = (
    "Write a JavaScript function named solve that returns the number 7. "
    "Answer with the code only, no explanation."
)

CODING_REFUSAL_PHRASES = (
    "does not support code",
    "code generation is not supported",
)

# Failures that say nothing about the model. Kept apart from "unclear" so the operator
# can tell "ask again later" from "that answer was strange".
_REACHABILITY_MARKERS = (
    "connection", "timed out", "timeout", "temporarily unavailable",
    "api error: 401", "api error: 403", "api error: 429",
    "api error: 500", "api error: 502", "api error: 503", "api error: 504",
    "no api key", "key not found", "not configured",
)

_lock = threading.Lock()
_inflight = set()


# --------------------------------------------------------------------------- keys

def canonical(model_string: str) -> str:
    """The key a fact is filed under.

    Lowercased and without the local/ prefix, because the platform writes the same
    local model both ways -- one role's setting carries the prefix, another holds the
    bare name. Cloud strings keep their provider prefix: the same model name at two
    providers is two facts.
    """
    m = (model_string or "").strip().lower()
    if m.startswith("local/"):
        m = m[len("local/"):]
    return m


def is_local(model_string: str) -> bool:
    """True when the string routes to the local station (ComfyUI, since stage
    3 of the move) rather than to a provider.

    Mirrors the runtime split rather than restating it: the table of local
    models is keyed without 'local/' (local_llm_weights.resolve_alias strips
    only that), and _dispatch_single_model raises "Unknown model prefix" for
    a string carrying no known provider prefix.
    """
    m = (model_string or "").strip().lower()
    return m.startswith("local/") or "/" not in m


def floor_for(model_string: str, capability: str) -> Optional[dict]:
    """A verdict that follows from the transport, so no call is spent and no
    measurement can overrule it. None when the question is genuinely open."""
    if capability == "image":
        from my_app.services.llm_providers import provider, provider_of
        entry = provider(provider_of(model_string) or "")
        if entry and entry.get("image_input") is False:
            return {
                "can": False,
                "why": f"The {entry['label']} connection takes no image (image_input is "
                       f"false in config/llm_providers.json), so the request is built "
                       f"without one and no model reached through it can be handed one.",
            }
        if is_local(model_string):
            # Whether a local checkpoint carries a vision tower is in its
            # config, and the table records it; a probe would build the
            # model (minutes, other built models dropped for it) to be
            # refused the picture afterwards.
            from my_app.services import local_llm_weights
            local = local_llm_weights.entry(model_string)
            if local is not None and not local.get("vision"):
                return {
                    "can": False,
                    "why": f"{local['repo']} carries no vision tower (vision is false in "
                           f"config/local_llm_weights.json), so the node refuses a picture "
                           f"for it before any weight is loaded.",
                }
    if capability == "tools" and is_local(model_string):
        return {
            "can": False,
            "why": "The local backend accepts a tool definition and ignores it "
                   "(the platform's ComfyUI node carries no tool calls), so a "
                   "local model never gets the chance to use one.",
        }
    return None


# -------------------------------------------------------------------------- store

class StoreUnreadable(Exception):
    """The file is there and cannot be parsed. Reading may treat that as 'nothing known';
    writing may not, or one measurement would replace every earlier one."""


def load_store(strict: bool = False) -> Dict[str, dict]:
    try:
        if STORE_FILE.exists():
            with open(STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            logger.warning("[CAPABILITIES] store is not an object; treating as empty")
            if strict:
                raise StoreUnreadable("the store is not an object")
    except StoreUnreadable:
        raise
    except Exception as e:
        logger.warning(f"[CAPABILITIES] store unreadable ({e}); treating as empty")
        if strict:
            raise StoreUnreadable(str(e))
    return {}


def get_recorded(model_string: str, capability: str = "image") -> Optional[bool]:
    """What was measured, or None if it was never probed. Floors answer first."""
    floor = floor_for(model_string, capability)
    if floor is not None:
        return floor["can"]
    entry = load_store().get(canonical(model_string), {})
    value = entry.get(capability) if isinstance(entry, dict) else None
    if isinstance(value, dict) and isinstance(value.get("can"), bool):
        return value["can"]
    return None


def record(model_string: str, capability: str, can: bool, evidence: str) -> None:
    with _lock:
        store = load_store()
        entry = store.get(canonical(model_string))
        if not isinstance(entry, dict):
            entry = {}
        entry["model_string"] = model_string
        entry[capability] = {
            "can": can,
            "checked": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evidence": (evidence or "")[:500],
        }
        store[canonical(model_string)] = entry
        _write(store)
    logger.info(f"[CAPABILITIES] recorded {model_string}: {capability}={can}")


def forget(model_string: str, capability: Optional[str] = None) -> bool:
    """Drop a recorded verdict so the model can be measured again.

    Without this a wrong record is permanent: a 404 from a model name that was
    mistyped, or from one the provider had temporarily deprovisioned, looks exactly
    like the refusal that made this module necessary.
    """
    key = canonical(model_string)
    with _lock:
        store = load_store()
        entry = store.get(key)
        if not isinstance(entry, dict):
            return False
        if capability is None:
            del store[key]
        else:
            if capability not in entry:
                return False
            del entry[capability]
            if not any(c in entry for c in CAPABILITIES):
                del store[key]
        _write(store)
    logger.info(f"[CAPABILITIES] forgot {model_string} ({capability or 'all'})")
    return True


def _write(store: Dict[str, dict]) -> None:
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_FILE.with_name(STORE_FILE.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    tmp.replace(STORE_FILE)


# --------------------------------------------------------------------- test image

def _font(size: int):
    """Any usable bold sans on this machine; None if the box ships no TTF at all."""
    for pattern in ("**/DejaVuSans-Bold.ttf", "**/DroidSans-Bold.ttf",
                    "**/*Sans-Bold.ttf", "**/*Bold.ttf", "**/*.ttf"):
        for path in sorted(glob.glob(f"/usr/share/fonts/{pattern}", recursive=True)):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


def build_test_image() -> Tuple[str, str]:
    """Draw the test image. Returns (base64 JPEG, the digits it shows).

    Nothing in it comes from a user or from a run, so it is a platform-generated image
    in the sense of DEVELOPMENT_DECISIONS 2026-03-25 and may go to a provider. Its
    size stays inside the 64..768 px envelope media_ref keeps for the local runner, so
    the same image can be sent over either transport.
    """
    digits = "".join(random.choice("0123456789") for _ in range(TEST_DIGITS))
    width, height = 640, 280
    font = _font(180)
    if font is not None:
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)
        box = draw.textbbox((0, 0), digits, font=font)
        draw.text(
            ((width - (box[2] - box[0])) / 2 - box[0],
             (height - (box[3] - box[1])) / 2 - box[1]),
            digits, fill="black", font=font,
        )
    else:
        # No TTF installed: draw small with PIL's built-in font and scale up. Blocky,
        # still unambiguous, and it keeps the probe from depending on a font package.
        small = Image.new("RGB", (64, 28), "white")
        ImageDraw.Draw(small).text((4, 8), digits, fill="black")
        img = small.resize((width, height), Image.NEAREST)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), digits


def _digits_of(text: str) -> str:
    """Just the digits. Small vision models wrap the answer -- measured replies included
    leading dots, stray digits and backticks, all of them correct readings."""
    return re.sub(r"\D", "", text or "")


def _reads_digits(answer: str, digits: str) -> bool:
    """Whether the reply names the number, rather than merely containing it somewhere.

    A run of digits in the reply has to BE the number. Substring matching over the
    reply's concatenated digits would accept an echo of the base64 image, which is
    thousands of five-digit windows and turns a blind model into a seeing one.
    """
    if not digits or not answer:
        return False
    if _digits_of(answer) == digits:
        return True
    return digits in re.findall(r"\d+", answer)


def _answer_of(result: Optional[dict]) -> str:
    """The local vision models put the answer in the thinking field often enough that
    reading only content loses correct readings; IONOS puts reasoning there as well."""
    if not result:
        return ""
    return ((result.get("content") or "").strip()
            or (result.get("thinking") or "").strip())


# -------------------------------------------------------------------------- probe

def _verdict(model_string: str, capability: str, verdict: str, answer: str,
             expected: str, evidence: str, recordable: bool = True) -> dict:
    recorded = False
    if recordable and verdict in ("can", "cannot"):
        record(model_string, capability, verdict == "can", evidence)
        recorded = True
    return {
        "model": model_string,
        "capability": capability,
        "verdict": verdict,
        "answer": answer,
        "expected": expected,
        "evidence": evidence,
        "recorded": recorded,
    }


def probe(model_string: str, capability: str = "image") -> dict:
    """Measure one capability of one model.

    Verdicts:
      can         the model did the thing. Recorded.
      cannot      the transport rules it out, or the provider refused in its own
                  words. Recorded unless it follows from a floor, which needs no
                  record because it is read from the code every time.
      unclear     something came back that neither proves nor disproves it. Shown to
                  the operator; never recorded.
      unreachable the provider or the GPU service could not be asked at all.
    """
    model_string = (model_string or "").strip()
    if capability not in CAPABILITIES:
        raise ValueError(f"unknown capability: {capability}")
    if capability not in MEASURABLE:
        raise ValueError(f"no probe exists for: {capability}")
    if not model_string:
        return _verdict("", capability, "unclear", "", "", "no model given", recordable=False)

    floor = floor_for(model_string, capability)
    if floor is not None:
        # No call is spent: whatever came back would be a fact about the transport,
        # not about the model, and the floor is read from the code on every lookup.
        return _verdict(model_string, capability, "can" if floor["can"] else "cannot",
                        "", "", floor["why"], recordable=False)

    key = (canonical(model_string), capability)
    with _lock:
        if key in _inflight:
            return _verdict(model_string, capability, "unclear", "", "",
                            "a check for this model is already running", recordable=False)
        _inflight.add(key)
    try:
        return {
            "image": _probe_image,
            "tools": _probe_tools,
            "thinking": _probe_thinking,
            "coding": _probe_coding,
        }[capability](model_string)
    finally:
        with _lock:
            _inflight.discard(key)


def _probe_image(model_string: str) -> dict:
    image_b64, digits = build_test_image()

    if is_local(model_string):
        from my_app.services.llm_backend import get_llm_backend
        name = model_string
        if name.lower().startswith("local/"):
            name = name[len("local/"):]
        try:
            result = get_llm_backend().chat(
                model=name,
                messages=[{"role": "user", "content": IMAGE_QUESTION}],
                images=[image_b64],
                temperature=0.0,
                enable_thinking=False,
            )
        except Exception as e:
            return _verdict(model_string, "image", "unreachable", "", digits,
                            f"{type(e).__name__}: {e}")
        answer = _answer_of(result)
        if _reads_digits(answer, digits):
            return _verdict(model_string, "image", "can", answer, digits, "read the test image")
        # Not a refutation: the local client returns None for a model that takes no
        # image, a model that is not installed, a VRAM shortage and a restarting
        # service alike.
        return _verdict(
            model_string, "image", "unclear", answer, digits,
            "the local backend gave no readable answer, and it cannot say why: "
            "no image support, no such model and no free VRAM all look the same there.",
            recordable=False,
        )

    from my_app.routes.chat_routes import _dispatch_single_model
    try:
        result = _dispatch_single_model(
            model_string,
            [{"role": "user", "content": IMAGE_QUESTION}],
            temperature=0.0, max_tokens=None, enable_thinking=False,
            tools=[], image_b64=image_b64,
        )
    except Exception as e:
        return _classify_error("image", model_string, e, digits, IMAGE_REFUSAL_PHRASES)
    answer = _answer_of(result)
    if _reads_digits(answer, digits):
        return _verdict(model_string, "image", "can", answer, digits, "read the test image")
    return _verdict(model_string, "image", "unclear", answer, digits,
                    "answered, but not with the number in the image", recordable=False)


def _probe_tools(model_string: str) -> dict:
    """Offer one small tool and see whether the model reaches for it.

    Local models never get here -- the floor above answers for them, because the local
    client drops the tool definition before it is ever sent.
    """
    from my_app.routes.chat_routes import _dispatch_single_model
    expected = f"{TOOL_NAME}(7)"
    try:
        result = _dispatch_single_model(
            model_string,
            [{"role": "user", "content": TOOLS_QUESTION}],
            temperature=0.0, max_tokens=None, enable_thinking=False,
            tools=TOOL_DEFINITION, image_b64=None,
        )
    except Exception as e:
        return _classify_error("tools", model_string, e, expected, TOOLS_REFUSAL_PHRASES)

    calls = (result or {}).get("tool_calls") or []
    names = []
    for call in calls:
        if not isinstance(call, dict):
            continue  # a provider that returns bare strings must not crash the check
        fn = call.get("function")
        names.append(fn.get("name") if isinstance(fn, dict) else call.get("name"))
    if TOOL_NAME in names:
        return _verdict(model_string, "tools", "can", ", ".join(n for n in names if n),
                        expected, "called the offered tool")
    return _verdict(model_string, "tools", "unclear", _answer_of(result), expected,
                    "answered in prose instead of calling the tool", recordable=False)


def _probe_thinking(model_string: str) -> dict:
    """See whether a reasoning channel comes back through this connection.

    What is measured is the pair, model and connection, which is also what the store is
    keyed on. The two connections differ and the verdict must not pretend otherwise:
    the local client hands the switch to the model's chat template (since 16.09.2026;
    until then it took the switch and ignored it), so a local model whose template has
    the switch is asked to reason here; the cloud payloads carry no such parameter.
    Every route now reads a reasoning field back if the model sent one unbidden, which
    until 2026-08-13 only the IONOS one did.

    So an absent channel is never reported as the model being unable to reason. It is
    reported as what it is: nothing arrives here that the platform could use.
    """
    expected = "a reasoning channel in the reply"
    messages = [{"role": "user", "content": THINKING_QUESTION}]
    try:
        if is_local(model_string):
            from my_app.services.llm_backend import get_llm_backend
            name = model_string
            if name.lower().startswith("local/"):
                name = name[len("local/"):]
            result = get_llm_backend().chat(
                model=name, messages=messages, temperature=0.0, enable_thinking=True)
        else:
            from my_app.routes.chat_routes import _dispatch_single_model
            result = _dispatch_single_model(
                model_string, messages, temperature=0.0, max_tokens=None,
                enable_thinking=True, tools=None, image_b64=None)
    except Exception as e:
        return _classify_error("thinking", model_string, e, expected,
                               THINKING_REFUSAL_PHRASES)

    thinking = ((result or {}).get("thinking") or "").strip()
    content = ((result or {}).get("content") or "").strip()
    local = is_local(model_string)
    if thinking:
        return _verdict(model_string, "thinking", "can", thinking[:200], expected,
                        "reasoning came back and the platform can show it")
    if content:
        why = ("answered without a think block although the switch was on: this "
               "model's chat template carries no such switch, or the model wrote none "
               "-- so what is measured is what the model offers unbidden"
               if local else
               "answered without a reasoning field, which this connection would have "
               "passed on had one been sent")
        return _verdict(model_string, "thinking", "cannot", content[:200], expected, why)
    return _verdict(model_string, "thinking", "unclear", "", expected,
                    "nothing came back at all", recordable=False)


def _code_of(text: str) -> str:
    """The code out of a reply that may or may not be fenced, in any language."""
    fenced = re.findall(r"```[\w+-]*\s*\n(.*?)```", text or "", re.S)
    return (fenced[0] if fenced else (text or "")).strip()


def _probe_coding(model_string: str) -> dict:
    """Ask for one small function in the language this role actually writes.

    Deliberately a low bar, and named as one: it separates a model that emits source
    from one that talks about source. It says nothing about how well the model writes
    the p5.js and Tone.js this role is for.

    Nothing here is filed as a refusal on formatting. A reply that carries a function
    counts; a reply that carries no code at all is the only "cannot", because that is
    the only outcome where the model did not do the thing rather than doing it oddly.
    """
    expected = "a function"
    messages = [{"role": "user", "content": CODING_QUESTION}]
    try:
        if is_local(model_string):
            from my_app.services.llm_backend import get_llm_backend
            name = model_string
            if name.lower().startswith("local/"):
                name = name[len("local/"):]
            result = get_llm_backend().chat(
                model=name, messages=messages, temperature=0.0, enable_thinking=False)
        else:
            from my_app.routes.chat_routes import _dispatch_single_model
            result = _dispatch_single_model(
                model_string, messages, temperature=0.0, max_tokens=None,
                enable_thinking=False, tools=None, image_b64=None)
    except Exception as e:
        return _classify_error("coding", model_string, e, expected, CODING_REFUSAL_PHRASES)

    answer = _answer_of(result)
    if not answer:
        return _verdict(model_string, "coding", "unclear", "", expected,
                        "nothing came back at all", recordable=False)
    code = _code_of(answer)
    has_function = bool(re.search(r"\bfunction\b|=>", code))
    balanced = code.count("{") == code.count("}") and code.count("{") > 0
    if has_function and balanced:
        return _verdict(model_string, "coding", "can", code[:200], expected,
                        "returned a function")
    if has_function or "{" in code:
        return _verdict(model_string, "coding", "unclear", code[:200], expected,
                        "something code-shaped came back, but not a function this could "
                        "read as complete", recordable=False)
    return _verdict(model_string, "coding", "cannot", code[:200], expected,
                    "answered without any code")


def _classify_error(capability: str, model_string: str, error: Exception,
                    expected: str, refusal_phrases: Tuple[str, ...]) -> dict:
    text = str(error).strip()
    low = text.lower()
    # Reachability first: a 429 or a 503 whose body happens to mention image support is
    # a bad moment, not a fact about the model, and only the refusal branch is permanent.
    if any(marker in low for marker in _REACHABILITY_MARKERS):
        return _verdict(model_string, capability, "unreachable", "", expected, text[:300])
    for phrase in refusal_phrases:
        if phrase in low:
            return _verdict(model_string, capability, "cannot", "", expected, text[:300])
    return _verdict(model_string, capability, "unclear", "", expected, text[:300],
                    recordable=False)


# ------------------------------------------------------------------ what to check

# The roles whose request path can be routed onward. What it is routed to is decided at
# request time out of hardware_matrix.json -- by provider, by credential, by the
# data-protection gate -- so this is a set that exists right now, never a named fallback.
# It is used to MEASURE, not to display: those models are handed the same image and the
# same tool definitions as the configured one, so they have to be measured, but they
# have no row and are named in none.
ROLES_ROUTED_ONWARD = ("CHAT_HELPER_MODEL", "PERSONA_MODEL", "RESONA_MODEL")


def reachable_models(role: str, model: str) -> List[str]:
    """Every model a request in this role can currently reach, the configured one first."""
    if role not in ROLES_ROUTED_ONWARD or not model:
        return [model] if model else []
    try:
        from my_app.routes.chat_routes import build_model_candidate_chain
        return [m for m in build_model_candidate_chain(role, model) if m]
    except Exception as e:
        logger.warning(f"[CAPABILITIES] reachable models for {role} unavailable: {e}")
        return [model]


def role_overview() -> Dict[str, dict]:
    """Per role: what it needs, which model the operator configured for it, and what
    has been measured about that model.

    That model and nothing else. Which model a request actually reaches when the
    configured one fails is decided at request time out of hardware_matrix.json, by
    provider, by credential, by the data-protection gate -- there is no such thing
    here as a named fallback, and a settings row that printed one would be stating a
    fact the platform does not hold.
    """
    import config
    from my_app.routes.chat_routes import get_user_setting

    # A store that is there and cannot be parsed must not be replaced by this one
    # measurement -- that would silently discard every earlier one.
    try:
        store = load_store(strict=True)
    except StoreUnreadable as e:
        logger.error("[CAPABILITIES] refusing to write over an unreadable store (%s); "
                     "move %s aside to start fresh", e, STORE_FILE)
        return
    overview: Dict[str, dict] = {}
    for role, requires in ROLE_REQUIREMENTS.items():
        model = (get_user_setting(role, default=getattr(config, role, "")) or "").strip()
        measurable = [c for c in requires if c in MEASURABLE]
        # The sentence and the date behind a verdict travel with it. Without them a red
        # slot is a judgement with no evidence, and nothing on the page says when it was
        # arrived at or on what grounds.
        recorded = store.get(canonical(model), {}) if model else {}
        overview[role] = {
            "requires": list(requires),
            "measurable": measurable,
            "model": model,
            "local": is_local(model) if model else False,
            "known": {c: get_recorded(model, c) for c in measurable} if model else {},
            "fixed": {c: floor_for(model, c) is not None for c in measurable} if model else {},
            "evidence": {c: (recorded.get(c) or {}).get("evidence", "") for c in measurable} if model else {},
            "checked": {c: (recorded.get(c) or {}).get("checked", "") for c in measurable} if model else {},
        }
    return overview
