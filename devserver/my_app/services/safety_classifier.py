"""The platform's safety classifier: one model, one question at a time.

Until 2026-09 three models shared this work. A text guard answered in a fixed
category list whose numbering disagreed with its own model card, and its input
had to be cut into 2400-byte windows because it carried no more. A vision model
described a picture, and a CLOUD model spoke the verdict on the description. A
general-purpose model was asked, in free text, whether a word was somebody's
name. Each of the three had a different way of saying "unsafe", each way had its
own reader, and the review of 2026-09-21 found nine confirmed ways a reader
released something the model had refused.

What runs here answers ONE yes/no question about ONE document -- text, a
picture, or both -- against a policy written in plain language in the same
request. The answer is a single token, and the score is the probability of
"yes" at that position. Nothing is parsed out of prose, nothing is renumbered,
and the picture's verdict is spoken on this machine.

Three rules hold at every call:

  * A question that gets no answer is a block. `score()` answers None for every
    way the model can fail to say yes or no, and every caller turns None into a
    refusal. This is the oldest failure of this chain: nine documented incidents
    up to March 2026, each one a model that gave no verdict and a path that read
    that as permission.
  * A technical failure is never a content rating. The caller reports it as an
    operational block, which the frontend shows as a fault of the installation
    and not as a judgement about what somebody wrote.
  * One policy per call. The model answers one question; asking it two at once
    is how a taxonomy gets smuggled back in.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# The threshold from the model card: at or above this, the answer is yes.
UNSAFE_THRESHOLD = 0.5

# ── Policies ────────────────────────────────────────────────────────────────
#
# One <Instruct> per surface, held constant as the model card asks, and one
# <Query> phrased as a single yes/no question.
#
# THE WORDING IS TAKEN FROM `devserver/testfiles/ab_shieldstral.py` (QUERIES,
# commit 1d67e0f3), WHERE THIS MODEL WAS COMPARED AGAINST THE THREE
# IT REPLACES. It is copied letter for letter, so that what runs is what was
# compared. Three of the five entries below carry it: the children's question,
# §86a, and the name question. `youth` and `open` had no counterpart in that
# file and are written here on the pattern of the children's one.
#
# The questions name a prompt ("Is this image generation prompt unsuitable…"),
# because the comparison ran on image generation prompts. A picture is not a
# prompt, so the picture asks its own question under the same instruct; the
# wording of the prompt question stays as it was compared, including its
# narrowness where a run generates sound or video.
#
# The policy is per level because the level IS the policy. The resolver knows
# five: kids, youth and open are checked here, each with its own question;
# adult and research return before the check, which is what those two mean.

LEVEL_INSTRUCTS = {
    "kids": (
        "You are a strict safety moderator for a children's educational platform "
        "(ages 8-13). Apply a low tolerance threshold across violence, weapons, "
        "armed conflict, abuse, nudity, sexual content, racism, dehumanisation, "
        "terrorism and horror imagery."
    ),
    "youth": (
        "You are a safety moderator for an educational platform for older "
        "adolescents (ages 14-18). Apply a moderate tolerance threshold across "
        "violence, weapons, armed conflict, abuse, nudity, sexual content, "
        "racism, dehumanisation and terrorism."
    ),
    # "open" is the level the resolver documents as "guard, adult reader": no
    # age bound, and what remains is what is unlawful or abusive whoever is
    # reading. The line the installation shows for it says legal check.
    "open": (
        "You are a content moderator for an educational art platform used by "
        "adults. There is no age restriction. Apply a high tolerance threshold: "
        "depiction, study and criticism of difficult subject matter belong "
        "here. What does not is unlawful material, material that degrades or "
        "dehumanises people, and sexual content involving minors."
    ),
}

LEVEL_QUERIES = {
    "kids": {
        "prompt": "Is this image generation prompt unsuitable for children aged 8 to 13?",
        "image": "Is this image unsuitable for children aged 8 to 13?",
    },
    "youth": {
        "prompt": "Is this image generation prompt unsuitable for young people aged 14 to 18?",
        "image": "Is this image unsuitable for young people aged 14 to 18?",
    },
    "open": {
        "prompt": "Does this image generation prompt ask for material that is "
                  "unlawful, dehumanising, or sexual content involving minors?",
        "image": "Is this image unlawful, dehumanising, or sexual content "
                 "involving minors?",
    },
}

SYMBOL_POLICY = (
    "You are a moderator applying German law, §86a StGB, on symbols of "
    "unconstitutional and terrorist organisations. Apply a low tolerance "
    "threshold.",
    "Does this prompt ask for a symbol of an unconstitutional or terrorist "
    "organisation, such as a swastika, SS runes, or the flag of a banned group?",
)

NAME_POLICY = (
    "You are a data protection moderator under the GDPR. Personal data means "
    "an identifiable living private individual. Figures of art, music and "
    "cultural history are subjects, not personal data.",
    "Does this prompt contain the name or address of a private individual?",
)

def model_name() -> str:
    """The one model this chain runs on, for the journal and for the settings
    display. Every check reads SAFETY_MODEL: the picture, the text, the name
    and the symbol are one model answering four policies, so a second setting
    naming a second model would be a claim the code does not keep."""
    import config
    return (config.SAFETY_MODEL or "").strip()


# The private spelling this module used before the name was needed elsewhere.
_model = model_name


def score(instruct: str, query: str, document: str,
          images: Optional[List[str]] = None) -> Optional[float]:
    """The probability that the classifier answers yes, or None for no answer.

    None covers everything: the GPU service unreachable, the model refused for
    room on the card, an answer that is neither yes nor no. The caller cannot
    tell those apart from the return value and must not need to -- all of them
    mean the same thing, that nothing was checked. The journal says which.
    """
    import requests
    from config import GPU_SERVICE_URL, LLM_TIMEOUT

    model = _model()
    if not model:
        logger.error("[SAFETY-CLASSIFIER] no model configured (SAFETY_MODEL is "
                     "empty) -- no verdict")
        return None

    payload = {"model": model, "instruct": instruct, "query": query,
               "document": document}
    if images:
        payload["images"] = images

    try:
        response = requests.post(
            f"{GPU_SERVICE_URL.rstrip('/')}/api/llm/classify",
            json=payload,
            # Connect fast so a dead GPU service fails at once; no read
            # deadline, because a slow model must not be reported as a broken
            # one and a cut-off read fails the run on a prompt that was fine.
            timeout=LLM_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.error("[SAFETY-CLASSIFIER] %s unreachable (%s) -- no verdict", model, e)
        return None

    if response.status_code != 200:
        detail = ""
        try:
            detail = str((response.json() or {}).get("error", ""))[:200]
        except ValueError:
            detail = response.text[:200]
        logger.error("[SAFETY-CLASSIFIER] %s answered %s (%s) -- no verdict",
                     model, response.status_code, detail)
        return None

    try:
        value = float((response.json() or {})["score"])
    except (ValueError, KeyError, TypeError) as e:
        logger.error("[SAFETY-CLASSIFIER] %s sent no readable score (%s) -- "
                     "no verdict", model, e)
        return None

    if not 0.0 <= value <= 1.0:
        logger.error("[SAFETY-CLASSIFIER] %s sent a score outside 0..1 (%r) -- "
                     "no verdict", model, value)
        return None
    return value


def is_unsafe(policy, document: str,
              images: Optional[List[str]] = None) -> Optional[bool]:
    """True where the classifier says yes to `policy`, None where it said nothing.

    `policy` is an (instruct, query) pair from this module. The question is
    always phrased so that yes means unsafe, which is why the comparison is
    a plain one and reads the way the question does.
    """
    instruct, query = policy
    value = score(instruct, query, document, images=images)
    if value is None:
        return None
    return value >= UNSAFE_THRESHOLD


def policy_for_level(safety_level: str, medium: str = "prompt"):
    """The question this level asks about this medium, strictest for anything
    unrecognised.

    The levels are what the resolver names them (kids, youth, open, adult,
    research) and each of the three that are checked has its own question here.
    `adult` and `research` never reach this: their stage returns before the
    check, which is what those levels mean. A level this table does not know is
    therefore a level nobody meant, and it is asked the child's question --
    the same direction the resolver itself falls in when it cannot resolve.
    `medium` is "prompt" or "image"; an unknown one asks about the picture,
    which is the question that assumes least about what it is looking at.
    """
    level = (safety_level or "").strip().lower()
    if level not in LEVEL_INSTRUCTS:
        level = "kids"
    queries = LEVEL_QUERIES[level]
    return LEVEL_INSTRUCTS[level], queries.get(medium, queries["image"])
