"""
Image safety check — one classifier, one question, on this machine.

The picture goes to the safety classifier (my_app/services/safety_classifier)
together with the policy of the level that is running, and the answer is one
token: yes, this picture is unsuitable for that level, or no.

Until 2026-09 this took two models and two machines: a local vision model wrote
a neutral description of the picture, and a CLOUD model read that description
and spoke the verdict. The picture stayed here, the sentence about it did not,
and a sentence describing a child's picture is still about that child. There
were also two readers for one answer, and a description that was accurate could
still be judged wrong by a model that never saw the picture.

Fail-closed: blocks if safety cannot be confirmed.
"""

import io
import logging
import re
from pathlib import Path
from typing import Optional

from PIL import Image
# This file kept an address book of its own until 2026-09-04: four cloud
# providers with their URLs and key files, a third copy of a table that also
# stood in chat_routes and in the pipeline engine. Copies drift — the IONOS
# address in this one pointed at a host that has no DNS record at all, so an
# operator who moved the verdict model to IONOS would have had every picture
# withheld with a technical message. The addresses, the keys and the reader now
# come from the one service that owns them.
from my_app.services.openai_style_stream import call_chat
from my_app.services.llm_providers import split_provider

import config

# Max dimension for VLM input — safety classification doesn't need full resolution
VLM_MAX_SIZE = 768
# Min dimension — qwen3-vl panics on images < 32px (SmartResize factor=32).
# A panic kills the runner process, causing ALL subsequent VLM requests to 500
# until the backend is restarted. Discovered 2026-03-22 in production.
VLM_MIN_SIZE = 64

logger = logging.getLogger(__name__)

# ── User-facing block messages (work order A12) ─────────────────────────────
# The reason string travels verbatim into the blocked payload and is what the
# user reads. An operational failure must not look like a content rating, which
# is why there are two of them and why nothing else may be sent in their place.
# Content rating — the check ran and judged the image:
VLM_CONTENT_BLOCK_MESSAGE = (
    "⚠️ Dein Bild wurde nicht freigegeben\n\n"
    "Die Bildprüfung hat Inhalte erkannt, die für deine Altersstufe "
    "nicht geeignet sind. Versuche es mit einer anderen Idee."
)
# Operational failure — the check did NOT run to completion; fail-closed:
VLM_OPERATIONAL_BLOCK_MESSAGE = (
    "⚠️ Technische Störung bei der Bildprüfung\n\n"
    "Das Bild wurde sicherheitshalber zurückgehalten, weil die Prüfung "
    "technisch nicht abgeschlossen werden konnte. Das ist KEINE Einstufung "
    "deines Bildes.\n\n"
    "Bitte versuche es gleich noch einmal. Wenn es wieder passiert, "
    "sag bitte der Kursleitung Bescheid."
)


def _call_verdict_model(prompt: str) -> tuple[Optional[str], Optional[str]]:
    """Call STAGE3_MODEL for verdict classification. Routes by model prefix.

    Returns (content, finish_reason). content is None on failure. finish_reason
    is the provider's value when available ('stop', 'length', …), else None —
    'length' means the answer was cut off and whatever came back is NOT a
    verdict (work order A12: a truncated response is an operational error,
    distinguishable from a content rating).

    The contract in one line: this function may fail to produce a verdict, and
    it may never produce a pass it did not receive. Every failure it cannot
    resolve returns (None, None), which the caller reads as an operational
    block.
    """
    model = config.STAGE3_MODEL

    # The provider is the first segment of the id, and the table says whether
    # that segment names one; the model path is the rest.
    provider, api_model = split_provider(model)

    if not provider and model.startswith('local/'):
        api_model = model[6:]

    if provider:
        # One request, to the configured model and to no other. This call had no
        # retry of any kind: a single Cloudflare 524 — the edge giving up on a
        # request that had sat silent for a hundred seconds — was enough to
        # withhold a harmless picture behind a technical message. The shared
        # reader asks with stream=True, so the provider writes its first bytes
        # within seconds and that silence does not arise; and it asks again on
        # an availability failure, but only BEFORE the first byte and only of
        # the same model. It carries no fallback chain and must not be given
        # one here: a verdict from a model nobody configured is not a verdict.
        try:
            result = call_chat(
                provider,
                [{'role': 'user', 'content': prompt}],
                api_model,
                temperature=0,
                # No max_tokens: the verdict model reasons before it answers,
                # and the reasoning spends from the same budget. A cap of 200
                # cut the verdict off mid-thought in production (work order
                # 3g, measured 2026-08-05). Caps are permitted only where a
                # provider API requires the field.
                stage='safety',
            )
        except Exception as e:
            logger.error(f"[VLM-SAFETY] {provider} call failed: {e}")
            return None, None

        # Only what the model actually said counts as its answer. The reader
        # keeps reasoning in a field of its own and this call never reads it: a
        # rating has to be stated, and a model that thought about the picture
        # without answering has not rated it. The empty string that comes back
        # in that case yields no verdict below, and no verdict blocks.
        return (result.get('content') or '').strip(), result.get('finish_reason')
    else:
        # Local model via GPU Service LLM backend. Since the repetition guard
        # the local contract carries a finish_reason too ("stop" | "length" |
        # "repetition"), and it is passed on unchanged: the truncation check
        # below must see a cut local verdict exactly as it sees a cloud one.
        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=api_model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.0,
            enable_thinking=False,
        )
        if result is None:
            return None, None
        return result.get('content', '').strip(), result.get('finish_reason')


# ── Reading a verdict out of what a model actually said ─────────────────────
# The words that state a verdict. A leading "un" is the verdict itself, not a
# negation of one, so the two are matched together.
_VERDICT_WORD_RE = re.compile(r'\b(un)?safe\b', re.IGNORECASE)
# What ends the look-back for a negation. A verdict in one clause says nothing
# about the clause before it: "no violence, gore or nudity. SAFE" is a pass,
# not a contradiction.
_CLAUSE_BREAK_RE = re.compile(r'[.;:!?,\n]')
_WORD_RE = re.compile(r"[\w']+")
# The words that turn the claim that follows them around, within one clause.
# German is in the list because local models answer in the language they were
# asked in and parts of this platform ask in German.
_NEGATORS = frozenset({
    'not', 'no', 'never', 'none', 'nothing', 'neither', 'nor', 'without',
    'cannot', 'cant', "can't", "isn't", "isnt", "aren't", "arent",
    "doesn't", "doesnt", "don't", "dont", "wasn't", "wasnt",
    "weren't", "werent", "won't", "wont",
    'nicht', 'nichts', 'kein', 'keine', 'keinen', 'keinem', 'keiner', 'keines',
})
# How far back a negation may stand and still govern the verdict word. Four
# words covers "does not contain unsafe content" and stops well short of
# reaching into a neighbouring statement.
_NEGATION_LOOKBACK_WORDS = 4


def _verdict_claims(text: str) -> list[str]:
    """Every verdict this text states, in order, with negation resolved.

    The asymmetry is deliberate and is the whole point. A negated "safe" ("this
    is not safe") states UNSAFE and is returned as one. A negated "unsafe"
    ("this is not unsafe") states nothing and is dropped: read as a pass it
    would let a double negative and a half-finished sentence through, and this
    function may never invent a permission the model did not state. A text that
    only ever negates "unsafe" therefore yields no claims at all, and the
    caller blocks.
    """
    claims: list[str] = []
    for match in _VERDICT_WORD_RE.finditer(text):
        stated = 'unsafe' if match.group(1) else 'safe'
        clause = text[:match.start()]
        cut = None
        for boundary in _CLAUSE_BREAK_RE.finditer(clause):
            cut = boundary.end()
        if cut is not None:
            clause = clause[cut:]
        preceding = _WORD_RE.findall(clause.lower())[-_NEGATION_LOOKBACK_WORDS:]
        negated = any(word in _NEGATORS for word in preceding)
        if negated:
            if stated == 'unsafe':
                continue
            stated = 'unsafe'
        claims.append(stated)
    return claims


def _extract_verdict(text: str) -> str | None:
    """Extract SAFE/UNSAFE verdict from text.

    Returns 'safe', 'unsafe', or None when the text states no verdict this
    function can read with confidence. None is not a pass: every caller treats
    it as an operational block, which is why an answer that cannot be read has
    to land here rather than be guessed at.

    Until 2026-09-04 this took the first word, the last word, and failing those
    the last occurrence anywhere. A verdict reading "so this is not safe" was
    therefore classified SAFE, because the last word was "safe", and so was
    "Verdict: not safe". A verdict is a claim, and a claim carries its negation
    with it.
    """
    if not text or not text.strip():
        return None
    claims = _verdict_claims(text)
    if not claims:
        return None
    if all(claim == 'safe' for claim in claims):
        return 'safe'
    if all(claim == 'unsafe' for claim in claims):
        return 'unsafe'
    # The text states both. A model echoing its own instruction ("Answer SAFE
    # or UNSAFE") and a fragment of reasoning that argues itself around both
    # land here, and neither has rated anything.
    return None


def vlm_safety_check(image_path: str | Path, safety_level: str) -> tuple[bool, str, str]:
    """
    Ask the safety classifier one yes/no question about one picture.

    Returns (is_safe, reason, description). The third element was the account a
    local model wrote of the picture, which a CLOUD model then judged. There is
    no such account any more, and the slot stays EMPTY: it travels as
    `vlm_description` into the blocked payload and the interface prints it to
    the person as "Die Bild-KI sah: …". A first version of this rewrite put the
    score there, so a refused upload read `Die Bild-KI sah: "score=0.9712"` —
    found by an adversarial review on 2026-09-23. The number belongs in the
    journal and nowhere else.

    The picture never left the machine and still does not. What left, until
    now, was the sentence describing it -- and a description of a child's
    picture is still about that child. One model, here, answers instead.

    Args:
        image_path: Path to the image file on disk.
        safety_level: the level that is running. 'adult' and 'research' carry
            no question; every other level is asked one here, and a level this
            table does not know is asked the child's question. NOTE that most
            CALLERS gate on ('kids', 'youth') before they get here, so whether
            a picture at 'open' is checked is decided at the call site and not
            in this function (open question, 2026-09-23).

    Returns:
        (is_safe, reason, ''). Every way of failing to confirm safety returns
        False with VLM_OPERATIONAL_BLOCK_MESSAGE, which the frontend shows as a
        fault of the installation and never as a rating of what somebody made.
    """
    from my_app.services import safety_classifier

    model = safety_classifier.model_name()

    try:
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error("[VLM-SAFETY] Image file not found — BLOCKING (cannot verify safety)")
            return (False, VLM_OPERATIONAL_BLOCK_MESSAGE, '')

        if (safety_level or '').strip().lower() in ('adult', 'research'):
            # The two levels that carry no question, named here and nowhere
            # else. Until now the test was whether this file happened to carry
            # a prompt for the level, so a level nobody had written down was a
            # release.
            return (True, '', '')

        # --- Prepare image (shared normalisation: my_app/utils/media_ref.py) ---
        from my_app.utils.media_ref import normalize_image, image_to_b64
        img, original_size = normalize_image(image_path, max_size=VLM_MAX_SIZE, min_size=VLM_MIN_SIZE)
        image_b64 = image_to_b64(img)

        instruct, query = safety_classifier.policy_for_level(safety_level, medium="image")
        logger.info(f"[VLM-SAFETY] {model} ({safety_level}), {original_size} -> {img.size}")

        # The document is the picture. The classifier takes an image on its
        # own, so the line beside it says only that; the policy and the
        # question travel in their own fields.
        value = safety_classifier.score(
            instruct, query,
            "The document is the image below.",
            images=[image_b64],
        )

        if value is None:
            logger.error(f"[VLM-SAFETY] {model} gave no verdict — BLOCKING (operational)")
            return (False, VLM_OPERATIONAL_BLOCK_MESSAGE, '')

        if value >= safety_classifier.UNSAFE_THRESHOLD:
            logger.warning(f"[VLM-SAFETY] UNSAFE for {safety_level} ({model}, score={value:.4f})")
            return (False, VLM_CONTENT_BLOCK_MESSAGE, '')
        logger.info(f"[VLM-SAFETY] SAFE for {safety_level} ({model}, score={value:.4f})")
        return (True, '', '')

    except Exception as e:
        logger.error(f"[VLM-SAFETY] Error during check — BLOCKING (cannot verify safety): {e}")
        return (False, VLM_OPERATIONAL_BLOCK_MESSAGE, '')
