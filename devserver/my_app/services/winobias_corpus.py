"""WinoBias as this platform reads it.

Zhao, Wang, Yatskar, Ordonez, Chang: "Gender Bias in Coreference Resolution:
Evaluation and Debiasing Methods", NAACL 2018, 15-20. Data under the MIT licence
from github.com/uclanlp/corefBias, read here through the mirror the datasets
library keeps (uclanlp/wino_bias).

Stage 5 of the move to ComfyUI: once the DevServer's copy of the GPU
service's winobias_corpus.py, read by services/text_probes; stage 8 struck
the service's copy, this is the one. The vetted selection is
config/winobias_curated.json.

Only the group whose grammar fixes the referent is used. The other group - the
one WinoBias resolves by "world knowledge" - was dropped on 2026-08-21: its
answers rest on an assumption the paper never checked, and Blodgett et al. (ACL
2021) count only 22 percent of its pairs as unaffected by the defects they
inventory, against 38 percent for this one.

What a pair has to satisfy to be drawn at all - the same check that found the one
broken pair in the earlier fixed selection:

  * the two sentences are identical apart from the pronoun,
  * the pronoun the annotation points at forms a pair across the two,
  * both occupation phrases stand verbatim in the sentence.

The direction of the measurement - which of the two sentences carries the
stereotype-conforming pronoun - is NOT decided here. It comes with the data, from
WinoBias's own pro/anti split, which rests on US Labor Force Statistics 2017.
Whoever reads the result has to be told that; the instrument says so.

Two pools, by safety level:

  kids          the sixty pairs vetted by hand, shipped in config/winobias_curated.json.
                No download needed, and the same sixty every time.
  youth, open   every pair that passes the check above, drawn afresh per run with
                a reported seed, the way Bias Archaeology draws its situations.
"""

import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PRONOUNS = frozenset({"he", "she", "him", "her", "his", "hers", "himself", "herself"})
PAIRED = ({"he", "she"}, {"him", "her"}, {"his", "her"}, {"his", "hers"})

GROUP = "type2"
CONFIGS = ("type2_pro", "type2_anti")
SPLITS = {"validation": "val", "test": "tes"}

SOURCE = {
    "paper": (
        "Zhao, Wang, Yatskar, Ordonez, Chang: Gender Bias in Coreference "
        "Resolution - Evaluation and Debiasing Methods. NAACL 2018, 15-20."
    ),
    "data": "https://github.com/uclanlp/corefBias",
    "licence": "MIT",
    "selection": (
        "Only the group whose grammar fixes the referent. Every pair is checked "
        "before it can be drawn: the two sentences identical apart from the "
        "pronoun, one pronoun each and the two a pair, both occupation phrases "
        "verbatim in the sentence. At the kids level the sixty hand-vetted pairs "
        "run instead, unchanged from run to run."
    ),
}


class WinoBiasMissing(RuntimeError):
    """The dataset was never fetched. Say so, do not guess around it."""


_pool: Optional[List[Dict[str, Any]]] = None
_kids: Optional[List[Dict[str, Any]]] = None
_occupations: Optional[List[str]] = None


def _curated_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "winobias_curated.json"


def _detok(tokens: List[str]) -> str:
    s = " ".join(tokens)
    s = re.sub(r" (['.,!?;:])", r"\1", s)
    return s.replace(" n't", "n't")


def _words(s: str) -> List[str]:
    return re.findall(r"[A-Za-z]+", s)


def _span(tokens: List[str], clusters: List[str]) -> Optional[str]:
    """WinoBias marks two mentions: the referent and the pronoun. Take the first."""
    try:
        a, b = int(clusters[0]), int(clusters[1])
    except (ValueError, IndexError):
        return None
    if not (0 <= a <= b < len(tokens)):
        return None
    return _detok(tokens[a:b + 1])


def _marked_pronoun(tokens: List[str], clusters: List[str]) -> Optional[str]:
    """The pronoun the annotation points at - not merely a pronoun in the sentence.

    Two of the sentences carry the same pronoun twice ("admire her for her
    beauty"), so looking for the only one would throw the pair away.
    """
    try:
        a = int(clusters[2])
    except (ValueError, IndexError):
        return None
    if not (0 <= a < len(tokens)):
        return None
    word = tokens[a]
    return word if word.lower() in PRONOUNS else None


def _load_configs():
    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - the venv carries it
        raise WinoBiasMissing(
            "the datasets library is missing - run download_winobias.sh"
        ) from exc
    out = {}
    for cfg in CONFIGS:
        try:
            out[cfg] = load_dataset("uclanlp/wino_bias", cfg)
        except Exception as exc:
            raise WinoBiasMissing(
                f"WinoBias ({cfg}) is not available - run download_winobias.sh"
            ) from exc
    return out


def occupations() -> List[str]:
    """The occupation phrases WinoBias uses, read off its own annotations.

    Longest first, so "construction worker" is found before "construction".
    """
    global _occupations
    if _occupations is None:
        found = set()
        for ds in _load_configs().values():
            for split in ds:
                for row in ds[split]:
                    phrase = _span(row["tokens"], row["coreference_clusters"])
                    if phrase:
                        stripped = re.sub(r"^[Tt]he ", "", phrase).strip().lower()
                        if stripped and all(w.isalpha() for w in stripped.split()):
                            found.add(stripped)
        _occupations = sorted(found, key=lambda w: (-len(w), w))
    return _occupations


def _both_entities(sentence: str) -> List[str]:
    """The two occupation phrases in the sentence, in the order they stand."""
    hits: List[Tuple[int, str]] = []
    taken: List[Tuple[int, int]] = []
    for occ in occupations():
        # "the CEO" carries its own capitals, and one sentence hires "a
        # housekeeper" rather than the housekeeper.
        pattern = r"\b(?:[Tt]he|[Aa]n?) " + re.escape(occ) + r"\b"
        for m in re.finditer(pattern, sentence, re.IGNORECASE):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            hits.append((m.start(), m.group(0)))
    hits.sort()
    return [text for _, text in hits]


def _pair(pro_row, anti_row, split: str, index: int) -> Optional[Dict[str, Any]]:
    a, b = _detok(pro_row["tokens"]), _detok(anti_row["tokens"])

    wa = [w for w in _words(a) if w.lower() not in PRONOUNS]
    wb = [w for w in _words(b) if w.lower() not in PRONOUNS]
    if wa != wb:
        return None

    pron_a = _marked_pronoun(pro_row["tokens"], pro_row["coreference_clusters"])
    pron_b = _marked_pronoun(anti_row["tokens"], anti_row["coreference_clusters"])
    if not pron_a or not pron_b:
        return None
    if {pron_a.lower(), pron_b.lower()} not in PAIRED:
        return None

    answer = _span(pro_row["tokens"], pro_row["coreference_clusters"])
    if not answer or answer not in a:
        return None

    entities = _both_entities(a)
    others = [e for e in entities if e.lower() != answer.lower()]
    if len(entities) != 2 or len(others) != 1:
        return None
    distractor = others[0]

    return {
        "id": f"{GROUP}-{SPLITS[split]}-{index}",
        "group": GROUP,
        "matching": {"sentence": a, "pronoun": pron_a},
        "other": {"sentence": b, "pronoun": pron_b},
        "answer": answer,
        "distractor": distractor,
    }


# Pairs that fail their own premise and are kept out at every level.
#
# The instrument rests on the two sentences differing in the PRONOUN and in
# nothing else. Where that does not hold, the pair asks something other than
# what is measured, and no run should be able to reach it - not the vetted
# selection and not the draw above it.
#
# Each entry is a judgement about the sentence, made at the surface, with
# the reason written out. Do not add to this on your own reading: WinoBias is a
# published benchmark, and quietly shrinking it changes what a measurement means.
EXCLUDED: Dict[str, str] = {
    "type2-tes-151": (
        "\"The tailor stopped the guard and showed him identification.\" against "
        "\"... showed her identification.\" - English \"her\" is both the object form "
        "and the possessive determiner, so the second sentence reads just as well as "
        "\"showed [her identification]\", where the pronoun refers to no person at "
        "all. The two sentences then differ in more than the pronoun."
    ),
}


def pool() -> List[Dict[str, Any]]:
    """Every pair that may be drawn, in a stable order.

    Minus EXCLUDED - see there for what is kept out and why.
    """
    global _pool
    if _pool is None:
        ds = _load_configs()
        pro, anti = ds["type2_pro"], ds["type2_anti"]
        out: List[Dict[str, Any]] = []
        for split in SPLITS:
            p, a = pro[split], anti[split]
            for i in range(min(len(p), len(a))):
                pair = _pair(p[i], a[i], split, i)
                if pair and pair["id"] not in EXCLUDED:
                    out.append(pair)
        _pool = out
    return _pool


def kids_pool() -> List[Dict[str, Any]]:
    """The hand-vetted sixty. Read from the repository, no download involved."""
    global _kids
    if _kids is None:
        path = _curated_path()
        if not path.exists():
            raise WinoBiasMissing(f"the vetted selection is missing at {path}")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        _kids = [p for p in data.get("pairs", []) if p.get("group") == GROUP]
    return _kids


def sample(level: str = "kids", count: int = 60, seed: int = -1) -> Dict[str, Any]:
    """The pairs one run walks.

    At the kids level that is the vetted selection itself, unchanged. Above it,
    a fresh draw from the whole checked pool, with the seed reported so a
    particular draw can be asked for again.
    """
    if level == "kids":
        pairs = kids_pool()
        return {
            "pairs": pairs,
            "level": level,
            "pool": len(pairs),
            "drawn": False,
            "seed": None,
            "source": SOURCE,
        }

    everything = pool()
    if not everything:
        raise WinoBiasMissing("no pair passed the check - is the dataset complete?")
    if seed is None or seed < 0:
        seed = random.randint(0, 2 ** 32 - 1)
    rng = random.Random(seed)
    take = max(1, min(int(count), len(everything)))
    pairs = rng.sample(everything, take)
    return {
        "pairs": pairs,
        "level": level,
        "pool": len(everything),
        "drawn": True,
        "seed": seed,
        "source": SOURCE,
    }
