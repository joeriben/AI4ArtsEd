"""BBQ as this platform reads it.

Parrish et al. 2022, "BBQ: A Hand-Built Bias Benchmark for Question Answering",
Findings of ACL 2022, 2086-2105; data under CC BY 4.0 from github.com/nyu-mll/BBQ.

Stage 5 of the move to ComfyUI: once the DevServer's copy of the GPU
service's bbq_corpus.py, read by services/text_probes; stage 8 struck the
service's copy, this is the one. It reads the benchmark from BBQ_DIR, else
resources/bbq at the repository's root.

Why this benchmark and not a self-built probe: the direction of a bias is not
decided here at run time. Every template targets one bias that is documented as
harmful, carries the source it is attested in, and ships with a per-example
annotation (target_loc) of WHICH of the three answers reflects that bias. This
module only joins the two files and hands them out. Nothing is filtered - with
one exception, and it is a level, not a judgement about the benchmark: below the
open level some situations are kept back, and at the kids level some categories
are not offered at all. See KIDS_CATEGORIES and MINORS_LEVELS below.

The annotation is polarity-specific, and that is the point of BBQ's four-way
design: for "who was the secretary?" target_loc points at the stereotyped group,
for "who was the board chair?" at the other one. Without the second question one
could not tell a bias from a plain preference for one of the two labels.
"""

import csv
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

CATEGORIES = [
    ("Age", "Age"),
    ("Disability_status", "Disability status"),
    ("Gender_identity", "Gender identity"),
    ("Nationality", "Nationality"),
    ("Physical_appearance", "Physical appearance"),
    ("Race_ethnicity", "Race / ethnicity"),
    ("Religion", "Religion"),
    ("SES", "Socio-economic status"),
    ("Sexual_orientation", "Sexual orientation"),
    ("Race_x_gender", "Race x gender"),
    ("Race_x_SES", "Race x socio-economic status"),
]

SOURCE = {
    "paper": (
        "Parrish, Chen, Nangia, Padmakumar, Phang, Thompson, Htut, Bowman: "
        "BBQ - A Hand-Built Bias Benchmark for Question Answering. "
        "Findings of ACL 2022, 2086-2105."
    ),
    "doi": "10.18653/v1/2022.findings-acl.165",
    "data": "https://github.com/nyu-mll/BBQ",
    "licence": "CC BY 4.0",
    "selection": (
        "Nothing is filtered. Every run draws its own random sample of situations "
        "from the whole category, in clusters of four, so that repeating a run is a "
        "second sample and not the same questions again. The seed is reported with "
        "the sample, so a particular draw can be asked for again."
    ),
}


# The categories a course at the kids level is offered, and the situations kept
# back from it. NOTHING is filtered out of the benchmark itself - this is an
# AGE screen at one safety level, the same kind of thing as the category list
# beside it, and it applies only where the level says kids.
#
# The screen lives HERE and not in the surface. A list in the Vue file decides
# what a dropdown offers; it does not decide what the service hands out, and a
# request that names another category would have got it.
#
# What stands in it is a pedagogical decision. The unprotected-sex situation,
# which comes up in a kids draw, is held back as not appropriate at that level;
# with it go the heavy themes that stand in these four categories as a whole:
# drugs, domestic violence and mental illness, and alcohol, weapons, crime and
# violence of any kind, which stand in the same table and are of the same
# order. Do not extend this on your own judgement - what a course at that level
# should meet is a pedagogical question.
KIDS_CATEGORIES = ("Age", "SES", "Nationality", "Disability_status")

# One pattern per theme, so that a reader can see what each of them costs and
# strike one without touching the others. They are matched against the WHOLE
# situation - context, question and the three answers of all four rows - and not
# only against what reaches the screen. Only the two ambiguous rows are shown,
# and only they are drawn as bars; the two disambiguated ones are still sent to
# the model as the control condition. A theme that stands only in them is
# therefore in the material even though nobody reads it. Screening the whole
# situation takes it out of the material.
KIDS_EXCLUDE_THEMES = {
    "sex": r"unprotected sex|sexually (?:active|transmitted)|\bSTDs?\b|\bSTIs?\b|\bHIV\b|\bAIDS\b",
    "drugs": (
        r"\bdrugs?\b|\bheroin\b|\bcocaine\b|\bmeth\b|\bopioids?\b|\baddicts?\b|\baddicted\b"
        r"|\baddiction\b|\boverdos\w*|\bjunkie\b|\bweed\b|\bmarijuana\b|\bstoned\b"
    ),
    "alcohol": (
        r"\balcohol\w*|\bdrunk\w*|\bbeer\b|\bwine\b|\bliquor\b|\bbooze\w*|\bbinge drink\w*"
        r"|\bAA meeting\w*|\bdrinking\b|\bdrinks (?:to excess|only rarely)\b"
    ),
    "violence": (
        r"\bviolen\w*|\battacks?\b|\battacked\b|\bassault\w*|\bmurder\w*|\bkill(?:ed|ing|er|ers)?\b"
        r"|\bstab(?:s|bed|bing)?\b|\bshooting\b|\bbeats?\b|\bbeaten\b|\bbrawl\w*|\bfights?\b"
        r"|\bfighting\b|\bpunch\w*|\babus\w*"
    ),
    "weapons": r"\bguns?\b|\bfirearms?\b|\bweapons?\b|\bknife\b|\bknives\b|\bpistols?\b|\brifles?\b|\bshotguns?\b",
    "crime": (
        r"\barrest\w*|\bcrimes?\b|\bcriminals?\b|\bstole\b|\bstolen\b|\bsteal\w*|\btheft\b"
        r"|\brobb\w*|\bshoplift\w*|\bprisons?\b|\bjail\w*|\bconvict\w*|\bfraud\w*|\bscam\w*"
        r"|\bsmuggl\w*|\btraffick\w*|\bembezzl\w*"
    ),
    "terror": r"\bbomb\w*|\bterroris\w*|\bhijack\w*|\bexplo(?:ded|des|sion|sions|sive|sives)\b|\bIED\b",
    "mental_illness": (
        r"\bmental (?:illness|illnesses|health|disorders?|hospitals?)|\bmentally ill\b|\bschizophren\w*"
        r"|\bbipolar\b|\bdepress\w*|\bPTSD\b|\banxiety disorders?\b|\bpanic (?:attacks?|disorder)"
        r"|\bBPD\b|\bborderline personality\b|\bOCD\b|\bpsychiatric\b|\bself-harm\w*|\bsuicid\w*"
        r"|(?:consultation|appointment|session)s? with (?:a |an |the |their )?"
        r"(?:psycholog\w+|therapist|counsell?or)|\bsee(?:s|ing)? (?:a|the|their) "
        r"(?:psycholog\w+|therapist)\b|\bin therapy\b"
    ),
}

KIDS_EXCLUDE = re.compile(
    "|".join("(?:%s)" % pattern for pattern in KIDS_EXCLUDE_THEMES.values()), re.I
)

# BBQ labels the disability items itself, and the label holds where a wording
# might not: a situation can turn on a mental illness without naming one in the
# row that shows it. Against the data as it stands this costs nothing - all 130
# MentalIllness situations are already caught by their wording, read across all
# four rows (measured 2026-08-22) - so this is insurance against a later BBQ
# release, not a second screen doing work today.
#
# What remains of Disability_status asks about physical disability,
# neurodiversity, deafness, blindness and cognitive disability - a category,
# not a rest.
KIDS_EXCLUDE_SUBCATEGORIES = ("MentalIllness",)

# Six situations that are held back from EVERY level below `open`, kids and
# youth alike. They name no
# heavy theme, which is why the screen above walks past them, and they are not
# harmless: each one puts a person of the class in the room in the place the
# question asks about.
#
# They are matched wherever they stand, not only in the four categories a course
# at the kids level is offered - the same templates come back in the crossed
# categories that only youth and above are shown, and they are the same thing
# there.
MINORS_LEVELS = ("kids", "youth")

MINORS_EXCLUDE_THEMES = {
    # An autistic classmate everyone at school makes fun of "for being really
    # bizarre". In a workshop that person can be in the room.
    "mockery": r"\bweird\b|\bbizarre\b",
    # "the Pakistani family's house needs more cleaning because it smells of
    # food" - the ethnic disgust trope.
    "body_odour": r"\bsmells? bad\b|\bsmelly\b|\bdeodorant\b|because it smells\b|\bsmells of\b",
    # The submissive Asian girlfriend, and the wife who obeys her husband.
    "submissiveness": r"\bsubmissive\b|\bdocile\b",
    # "made fun of for not being good-looking enough", and being ranked by looks
    # along race and gender. Physical_appearance carries none of these words and
    # stands untouched - that category is ABOUT appearance, which is not this.
    "attractiveness": r"\battractive\b|\bunattractive\b|\bgood-looking\b|\bugly\b",
    # Same-sex marriage held against a grandparent's religious conviction.
    "same_sex_marriage": r"\bequal rights\b|\bsame-sex marriage\b|\bgay marriage\b",
    # Racism named as the thing one of the two did.
    "racism_named": r"\bracist\b|\bracial slur\b|\bracism\b",
}

MINORS_EXCLUDE = re.compile(
    "|".join("(?:%s)" % pattern for pattern in MINORS_EXCLUDE_THEMES.values()), re.I
)

# SOURCE says "Nothing is filtered", and on every other level that is true. It
# must not be what the kids level answers with while it hands out a screened
# pool.
KIDS_SELECTION = (
    "At the kids level this is not the whole benchmark. Four categories are offered, "
    "and within them the situations that turn on drugs, alcohol, violence, weapons, "
    "crime, terror, mental illness or sex are kept back - as whole situations, before "
    "the draw. What is left is drawn from as described above. Nothing is removed from "
    "the benchmark itself; the open level sees all of it."
)

YOUTH_SELECTION = (
    "At the youth level every category is offered, and six situations are kept back: "
    "an autistic classmate mocked as weird, the ethnic body-odour trope, the submissive "
    "girlfriend or wife, being ranked by looks, same-sex marriage held against a "
    "religious conviction, and racism named as one of the two people's deed. Whole "
    "situations, before the draw. Nothing is removed from the benchmark itself; the "
    "open level sees all of it."
)


def bbq_dir() -> Path:
    """Where download_bbq.sh puts the benchmark: BBQ_DIR, else resources/bbq
    at the repository root (gitignored; the data is fetched, never committed)."""
    env = os.environ.get("BBQ_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "resources" / "bbq"


_cache: Dict[str, List[Dict[str, Any]]] = {}
# The screened situations, per category AND level. The screen is a regex over
# every word of every row; run again for each of the eleven categories it puts
# ten seconds in front of a category list, and the surface came up empty
# (measured 2026-08-22). It depends on nothing but the corpus and the level.
_clusters: Dict[tuple, List[List[Dict[str, Any]]]] = {}
_targets: Optional[Dict[tuple, int]] = None


class BBQMissing(RuntimeError):
    """The dataset was never downloaded. Say so, do not guess around it."""


def _load_targets() -> Dict[tuple, int]:
    """example -> the answer index that reflects the bias, from BBQ's own metadata."""
    global _targets
    if _targets is None:
        path = bbq_dir() / "analysis_scripts" / "additional_metadata.csv"
        if not path.exists():
            raise BBQMissing(f"BBQ metadata missing at {path} - run download_bbq.sh")
        table: Dict[tuple, int] = {}
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                loc = row.get("target_loc", "")
                if loc in ("", "NA"):
                    continue
                try:
                    table[(row["category"], int(row["example_id"]))] = int(float(loc))
                except (ValueError, KeyError):
                    continue
        _targets = table
    return _targets


def load_category(category: str) -> List[Dict[str, Any]]:
    """Every question of one category, joined with its target annotation."""
    if category in _cache:
        return _cache[category]

    path = bbq_dir() / "data" / f"{category}.jsonl"
    if not path.exists():
        raise BBQMissing(f"BBQ data missing at {path} - run download_bbq.sh")

    targets = _load_targets()
    items: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            raw = json.loads(line)
            info = raw.get("answer_info", {})
            meta = raw.get("additional_metadata", {})
            unknown = next(
                (i for i in range(3) if (info.get(f"ans{i}", ["", ""])[1] or "").lower() == "unknown"),
                None,
            )
            items.append({
                "id": f"{category}-{raw['example_id']}",
                "example_id": raw["example_id"],
                "category": category,
                "question_index": raw.get("question_index"),
                "polarity": raw["question_polarity"],          # neg | nonneg
                "condition": raw["context_condition"],          # ambig | disambig
                "context": raw["context"],
                "question": raw["question"],
                "answers": [raw["ans0"], raw["ans1"], raw["ans2"]],
                "answer_groups": [info.get(f"ans{i}", ["", ""])[1] for i in range(3)],
                "unknown_index": unknown,
                "correct_index": raw["label"],
                "target_index": targets.get((category, raw["example_id"])),
                "stereotyped_groups": meta.get("stereotyped_groups", []),
                "subcategory": meta.get("subcategory", ""),
                "source": meta.get("source", ""),
            })

    _cache[category] = items
    return items


def _screened(item: Dict[str, Any], level: str) -> bool:
    """Whether this item is kept back at this level."""
    blob = " ".join([item["context"], item["question"], *item["answers"]])
    if level in MINORS_LEVELS and MINORS_EXCLUDE.search(blob):
        return True
    if level != "kids":
        return False
    if (item.get("subcategory") or "") in KIDS_EXCLUDE_SUBCATEGORIES:
        return True
    return bool(KIDS_EXCLUDE.search(blob))


def clusters(category: str, level: str = "open") -> List[List[Dict[str, Any]]]:
    """The four ways of asking one situation, kept together.

    BBQ writes each situation as four rows: negative and non-negative question,
    each with and without the disambiguating sentence. Sampling has to move in
    fours or the control condition falls apart.

    Below the open level a whole situation goes or stays: if any of its four
    rows is screened - by its theme, by its subcategory, or as one of the six
    held back from every level below open - the situation is not offered.
    Dropping only the offending row would leave a cluster whose control
    condition rests on a question the group never saw.
    """
    if (category, level) in _clusters:
        return _clusters[(category, level)]

    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for item in load_category(category):
        key = (item["question_index"], item["example_id"] // 4)
        grouped.setdefault(key, []).append(item)
    blocks = [grouped[k] for k in sorted(grouped)]
    if level in MINORS_LEVELS:
        blocks = [b for b in blocks if not any(_screened(i, level) for i in b)]
    _clusters[(category, level)] = blocks
    return blocks


def sample(category: str, count: int = 30, seed: Optional[int] = None,
           level: str = "open") -> Dict[str, Any]:
    """`count` situations drawn at random from the whole category.

    A draw, not a filter, and a fresh one per run: repeating a run then asks a
    second sample rather than the same questions again, and the difference
    between two runs is what sampling error looks like. Within what the level is
    offered, what is left out is left out by chance and not by anyone's
    judgement about what a class should see - what the kids level is offered is
    decided before the draw, see below.

    The four ways of asking one situation are drawn together. Without that the
    control condition would rest on other situations than the open one, and the
    two could not be held against each other.

    The seed is returned with the sample. Passing it back reproduces the exact
    draw - for a workshop that wants the same questions twice, or for checking a
    result someone else got.

    At the kids level the draw runs over the screened pool (KIDS_EXCLUDE_THEMES
    and KIDS_EXCLUDE_SUBCATEGORIES),
    so what is kept back is kept back before the dice are thrown and cannot come
    up in a run at all. A category the level is not offered is refused outright -
    the item screen alone would hand it out with the screened rows missing,
    which is not the same thing as not being offered it.
    """
    if not allowed(category, level):
        raise BBQDenied(f"category {category} is not offered at level {level}")
    blocks = clusters(category, level)
    if not blocks:
        return {"items": [], "seed": 0, "situations": 0}
    if seed is None:
        seed = random.SystemRandom().getrandbits(32)
    picked = random.Random(seed).sample(blocks, min(max(1, count), len(blocks)))
    return {
        "items": [item for block in picked for item in block],
        "seed": seed,
        "situations": len(picked),
        "drawn_from": len(blocks),
    }


class BBQDenied(RuntimeError):
    """Asked for a category this safety level is not offered."""


def allowed(category: str, level: str = "open") -> bool:
    """Whether a course at this level is offered this category at all.

    A name the benchmark does not have is not offered at any level. Without
    that, an unknown name would reach load_category and come back as "run
    download_bbq.sh", which reads like a broken install rather than a refusal.
    """
    if category not in {key for key, _ in CATEGORIES}:
        return False
    return level != "kids" or category in KIDS_CATEGORIES


def overview(level: str = "open") -> Dict[str, Any]:
    """What is there, without running anything.

    The counts are the ones the level actually gets: at kids the categories it
    is not offered are absent, and the numbers of the remaining four are counted
    over the screened pool, so the surface never announces more questions than
    the draw can reach.
    """
    out = []
    for key, label in CATEGORIES:
        if not allowed(key, level):
            continue
        try:
            load_category(key)
        except BBQMissing:
            out.append({"category": key, "label": label, "available": False})
            continue
        blocks = clusters(key, level)
        items = [i for b in blocks for i in b]
        out.append({
            "category": key,
            "label": label,
            "available": True,
            "questions": len(items),
            "situations": len(blocks),
            "with_target": sum(1 for i in items if i["target_index"] is not None),
            "sources": len({i["source"] for i in items if i["source"]}),
        })
    source = dict(SOURCE)
    if level == "kids":
        source["selection"] = KIDS_SELECTION
    elif level == "youth":
        source["selection"] = YOUTH_SELECTION
    return {"categories": out, "source": source}
