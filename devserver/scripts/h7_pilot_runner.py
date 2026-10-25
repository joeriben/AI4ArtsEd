#!/usr/bin/env python3
"""H7 pilot runner — one document, per PILOT_H7_joerissen_SPEZIFIKATION_2026-07-06.

Executes the pilot EXACTLY as specified: deterministic Phase 0 (segmenter
`bib-seg-v1`, no embeddings), Phase 1 P1/P2/P3 per segment (co-present
sequence, retry idiom, verbatim-BELEG gate), Phase 2 P4 per escalated source,
Phase 3 P5 profile reduction -> PROFIL + fallgestalt.json. Prompts are read
VERBATIM from the spec file (single source of truth, no copy drift).

Pilot-grade code (Ein-Dokument-Gate): lives in scripts/, writes only under
devserver/exports/knowledge_pilot/ (server-local, gitignored). No index
integration, no publish; the rendered result is reviewed first.

Usage (from repo root, venv):
  venv/bin/python devserver/scripts/h7_pilot_runner.py --smoke
  venv/bin/python devserver/scripts/h7_pilot_runner.py --phase0
  venv/bin/python devserver/scripts/h7_pilot_runner.py --run [--max-segments N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs/plans/knowledge/PILOT_H7_joerissen_SPEZIFIKATION_2026-07-06.md"
RAW = REPO / ("resources/knowledge_originals/operator/"
              "jorissen-et-al-2025-wahrnehmungskrisen-generative-kunstliche-"
              "intelligenz-als-herausforderung-padagogischer-und-erzie.raw.md")
OUT = REPO / "devserver/exports/knowledge_pilot/h7_joerissen"
sys.path.insert(0, str(REPO / "devserver"))
from my_app.services.llm_providers import credentials  # noqa: E402

# The address and the key from the one table (config/llm_providers.json),
# the way every caller of the platform's transport takes them since
# 2026-09-12; until 2026-10-10 this script read the provider's key file
# itself and carried the address as a literal (finding S-058 of the code review of 2026-10-10).
API_URL, _API_KEY = credentials("mammouth")

# Haus-Provider Mammouth, nicht OpenRouter (dessen
# Key-Policy blockt MiMo; Mammouth fuehrt kein MiMo — live geprueft, 75
# Modelle). Gewaehlt: mistral-large-3 = SARAHs eigene Budget-Linie (EU),
# also Tier-Paritaet zum Produzenten der Methode. MiMo-Paritaetslauf bleibt
# spaeter via OpenRouter moeglich.
MODEL = "mistral-large-3"
CONCURRENCY = 4                  # spec §3.2: conc 4–6 (Mammouth-Limits schonen)
RETRY_TEMPS = [0.0, 0.25, 0.5, 0.6]  # spec §3.2 retry idiom
DOC_META = {
    "titel": ("Wahrnehmungskrisen. Generative Künstliche Intelligenz als "
              "Herausforderung pädagogischer und erziehungswissenschaftlicher "
              "Wahrnehmungsweisen"),
    "autoren": "Benjamin Jörissen, Leopold Klepacki, Viktoria Flasche, Manuel Zahn",
    "jahr": "2025",
    "authors_last": ["Jörissen", "Klepacki", "Flasche", "Zahn"],
}

_stats_lock = threading.Lock()
STATS = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "retries": 0,
         "beleg_failures": 0, "errors": 0}


# ---------------------------------------------------------------------------
# Prompts: verbatim extraction from the spec (P1..P5 = first fenced block
# after each "### P<n>" heading)
# ---------------------------------------------------------------------------

def load_prompts() -> dict:
    text = SPEC.read_text(encoding="utf-8")
    prompts = {}
    for n in (1, 2, 3, 4, 5):
        m = re.search(rf"^### P{n} .*?\n+```\n(.*?)\n```", text,
                      re.S | re.M)
        if not m:
            raise SystemExit(f"Prompt P{n} nicht in der Spec gefunden")
        prompts[f"P{n}"] = m.group(1)
    return prompts


# ---------------------------------------------------------------------------
# Phase 0 — deterministic segmentation (bib-seg-v1, spec §3.1)
# ---------------------------------------------------------------------------

ABBREV = ["z. B.", "z.B.", "vgl.", "et al.", "u. a.", "u.a.", "bzw.", "ca.",
          "S.", "Abs.", "d. h.", "d.h.", "u. ä.", "ebd.", "f.", "ff.",
          "Hrsg.", "Aufl.", "Nr.", "Bd.", "Jg.", "o. J.", "resp.", "etc.",
          "inkl.", "sog.", "usw.", "Kap."]

K1 = ["denn", "weil", "da", "nämlich", "zumal",
      "daher", "somit", "folglich", "also", "deshalb", "darum",
      "jedoch", "dennoch", "zwar", "gleichwohl",
      "sofern", "falls", "wenn",
      "zudem", "ferner", "außerdem", "zugleich",
      "d. h.", "d.h.", "anders gesagt",
      "vielmehr", "sondern",
      "dieses", "diese", "dabei", "dadurch", "hierfür", "darin"]

K2_PRONOUNS = ["er", "sie", "ihm", "ihr", "ihn", "sein", "seine", "seiner",
               "seinem", "seinen", "ihre", "ihrer", "ihrem", "ihren",
               "dieser", "diese", "dieses", "diesen", "diesem",
               "deren", "dessen", "jene", "jener", "jenes"]
# spec: expletives "es" ausgeblendet -> "es" deliberately NOT a K2 trigger

AFFIL = ["im anschluss an", "in anlehnung an", "aufbauend auf",
         "stützt sich auf", "zufolge", "gemäß", "mit blick auf",
         "im sinne von", "folgend"]
DIST = ["im gegensatz zu", "in abgrenzung zu", "kritisch", "kritisiert",
        "greift zu kurz", "übersieht", "verkürzt", "widerspricht",
        "problematisch", "wendet ein", "dagegen"]


def normalize(raw: str) -> str:
    # Docling dehyphenation: "Aufforde -rung" -> "Aufforderung"
    text = re.sub(r"(\w) -(?=[a-zäöüß])", r"\1", raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _protected(text: str, i: int) -> bool:
    """True if the terminator at i must NOT split (abbrev/initial/number)."""
    before = text[max(0, i - 12):i + 1]
    for ab in ABBREV:
        if before.endswith(ab):
            return True
    # initials (single capital + dot) and enumerations like "1."
    if re.search(r"(?:^|\s)[A-ZÄÖÜ]\.$", before):
        return True
    if text[i] == "." and i + 1 < len(text) and text[i + 1].isdigit():
        return True  # decimals 0.8
    if re.search(r"\d\.$", before) and i + 1 < len(text) and text[i + 1] != " ":
        return True
    return False


def split_sentences(par: str) -> list:
    """Sentence atoms: boundaries at . ! ? … ; — protected regions kept intact."""
    sents, buf, depth = [], [], 0
    quotes = {"»": "«", "›": "‹", "„": "“", "(": ")", "[": "]"}
    open_q = list(quotes.keys())
    close_q = list(quotes.values())
    i = 0
    while i < len(par):
        ch = par[i]
        buf.append(ch)
        if ch in open_q:
            depth += 1
        elif ch in close_q and depth > 0:
            depth -= 1
        elif ch in ".!?…;" and depth == 0 and not _protected(par, i):
            nxt = par[i + 1:i + 3]
            if ch == "." and re.match(r"[a-zäöüß0-9]", nxt.strip()[:1] or ""):
                pass  # likely abbreviation continuation
            else:
                s = "".join(buf).strip()
                if s:
                    sents.append(s)
                buf = []
        i += 1
    tail = "".join(buf).strip()
    if tail:
        sents.append(tail)
    return sents


def _first_words(s: str, n: int = 3) -> str:
    return " ".join(re.sub(r"[^\wäöüÄÖÜß. ]", " ", s.lower()).split()[:n])


def _k1_initial(s: str) -> bool:
    fw = _first_words(s)
    return any(fw.startswith(k) for k in K1)


def _k2_initial(s: str) -> bool:
    first = (_first_words(s, 1) or "")
    return first in K2_PRONOUNS


def segment_document(norm: str) -> list:
    """bib-seg-v1: returns [{seq, text, char_start, char_end, n_sentences}]."""
    segments = []
    pos = 0
    paragraphs = [p for p in norm.split("\n\n")]
    prev_par_last = None
    for par in paragraphs:
        par_stripped = par.strip()
        start_in_norm = norm.find(par_stripped, pos) if par_stripped else -1
        if not par_stripped:
            continue
        if par_stripped.startswith("#"):
            segments.append({"text": par_stripped, "sentences": 1,
                             "char_start": start_in_norm,
                             "char_end": start_in_norm + len(par_stripped),
                             "heading": True, "k1_first": False, "k2_first": False})
            pos = start_in_norm + len(par_stripped)
            prev_par_last = None
            continue
        sents = split_sentences(par_stripped)
        if not sents:
            continue
        groups = [[sents[0]]]
        for s in sents[1:]:
            if _k1_initial(s) or _k2_initial(s):
                groups[-1].append(s)
            else:
                groups.append([s])
        # tail singleton: absorb a 1-sentence tail into the previous group
        if len(groups) > 1 and len(groups[-1]) == 1:
            groups[-2].extend(groups.pop())
        # paratactic run: merge maximal runs (>=2) of connectorless 1-sentence groups
        merged, run = [], []
        for g in groups:
            if len(g) == 1:
                run.append(g)
            else:
                if len(run) >= 2:
                    merged.append([s for r in run for s in r])
                elif run:
                    merged.extend(run)
                run = []
                merged.append(g)
        if len(run) >= 2:
            merged.append([s for r in run for s in r])
        elif run:
            merged.extend(run)
        par_segments = []
        for g in merged:
            text = " ".join(g)
            cs = norm.find(g[0][:60], pos)
            seg = {"text": text, "sentences": len(g), "char_start": cs,
                   "char_end": cs + len(text) if cs >= 0 else -1,
                   "heading": False,
                   "k1_first": _k1_initial(g[0]), "k2_first": _k2_initial(g[0])}
            par_segments.append(seg)
            if cs >= 0:
                pos = cs + len(g[0])
        # cross-paragraph stitch (tightly gated: K1 clause-initial AND K2 on pair)
        if (prev_par_last is not None and par_segments
                and par_segments[0]["k1_first"] and par_segments[0]["k2_first"]):
            prev_par_last["text"] += " " + par_segments[0]["text"]
            prev_par_last["sentences"] += par_segments[0]["sentences"]
            prev_par_last["char_end"] = par_segments[0]["char_end"]
            par_segments = par_segments[1:]
        segments.extend(par_segments)
        if par_segments:
            prev_par_last = par_segments[-1]
    for i, s in enumerate(segments):
        s["seq"] = i
        s.pop("k1_first", None)
        s.pop("k2_first", None)
    return segments


# Two-stage citation detection: any parenthesis content is scanned for ALL
# author-year pairs (handles "vgl."-prefixes, multi-author slashes, ";"-lists,
# page suffixes incl. "ff."); plus the prose form "Name (Jahr)".
PAREN_RE = re.compile(r"\(([^()]{0,240})\)")
INNER_CITE = re.compile(
    r"([A-ZÄÖÜ][\w'’-]+)(?:\s*/\s*[A-ZÄÖÜ][\w'’-]+)*(?:\s+et\s+al\.?)?"
    r"\s+(\d{4})[a-z]?(?:\s*:\s*\d+(?:\s*(?:[-–]\s*\d+|f{1,2}\.?))?)?"
)
PROSE_CITE = re.compile(
    r"([A-ZÄÖÜ][\w'’-]+)(?:\s+et\s+al\.?)?\s*\(\s*(\d{4})[a-z]?(?:\s*:\s*\d+)?\s*\)"
)


def find_citations(text):
    hits = []
    for pm in PAREN_RE.finditer(text):
        for m in INNER_CITE.finditer(pm.group(1)):
            hits.append(m.group(1))
    for m in PROSE_CITE.finditer(text):
        hits.append(m.group(1))
    return hits


def citation_topology(norm: str, segments: list) -> dict:
    """Per first author: mult (bibliography works), dens (in-text events),
    op flag, citing segment seqs. Plus sigma-cheap routing + self-citations."""
    m = re.search(r"^#+\s*(Literatur(verzeichnis)?|References|Bibliograph\w*)\s*$",
                  norm, re.M | re.I)
    bib_start = m.start() if m else len(norm)
    body_end_seq = [s for s in segments if s["char_start"] < bib_start and s["char_start"] >= 0]

    authors: dict = {}
    for seg in body_end_seq:
        for name in find_citations(seg["text"]):
            a = authors.setdefault(name, {"dens": 0, "mult": 0, "segments": []})
            a["dens"] += 1
            if seg["seq"] not in a["segments"]:
                a["segments"].append(seg["seq"])
    bib_text = norm[bib_start:]
    for line in bib_text.splitlines():
        lm = re.match(r"\s*(?:[-•*]\s*)?([A-ZÄÖÜ][\w'’-]+),", line)
        if lm and lm.group(1) in authors:
            authors[lm.group(1)]["mult"] += 1

    def stance_of(text: str) -> int:
        low = text.lower()
        aff = any(p in low for p in AFFIL)
        dis = any(p in low for p in DIST)
        if aff and not dis:
            return 1
        if dis and not aff:
            return -1
        return 0

    seg_by_seq = {s["seq"]: s for s in segments}
    for name, a in authors.items():
        # densMin: SARAH default 3, per spec §3.1(6) am Material revidierbar.
        # Befund Jörissen-Paper (4k Wörter, 35 Erstautoren): max dens = 2 —
        # bei 3 bliebe die Checkliste leer. Revision v1->v2: densMin = 2.
        a["op"] = a["dens"] >= 2
        citing_texts = [seg_by_seq[q]["text"] for q in a["segments"]]
        paratext = stance_of(" ".join(citing_texts))
        densest = max(a["segments"],
                      key=lambda q: seg_by_seq[q]["text"].count(name)) if a["segments"] else None
        window = stance_of(seg_by_seq[densest]["text"]) if densest is not None else 0
        if paratext == 0 and window == 0:
            a["sigma"] = None
            a["route"] = "none"
        elif paratext == window or paratext == 0 or window == 0:
            a["sigma"] = "+" if (paratext or window) > 0 else "-"
            a["route"] = "cheap"
        else:
            a["sigma"] = None
            a["route"] = "escalate"
    self_cites = {n: a for n, a in authors.items()
                  if n in DOC_META["authors_last"]}
    return {"authors": authors, "self_citations": list(self_cites.keys()),
            "bib_start": bib_start}


# ---------------------------------------------------------------------------
# OpenRouter client
# ---------------------------------------------------------------------------

def _api_key() -> str:
    return _API_KEY


def call_llm(system: str, user: str, temperature: float = 0.0,
             max_tokens: Optional[int] = None) -> str:
    body = {"model": MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature}
    # Omitted unless a caller insists: a cap here truncates a profile
    # mid-sentence and the run silently produces half-material.
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    for attempt in range(6):
        try:
            r = requests.post(API_URL, json=body, timeout=(10, None),
                              headers={"Authorization": f"Bearer {_api_key()}"})
            if r.status_code == 429:
                # Mammouth rolling model-group limits: wait and retry
                time.sleep(60)
                continue
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {})
            with _stats_lock:
                STATS["calls"] += 1
                STATS["prompt_tokens"] += usage.get("prompt_tokens", 0)
                STATS["completion_tokens"] += usage.get("completion_tokens", 0)
            return (data["choices"][0]["message"]["content"] or "").strip()
        except requests.RequestException as e:
            if attempt == 5:
                with _stats_lock:
                    STATS["errors"] += 1
                raise
            time.sleep(6 * (attempt + 1))
    return ""


def call_with_retry_idiom(system: str, user: str, max_tokens: Optional[int] = None) -> str:
    """SARAH callText idiom: empty/degenerate -> up to 4 tries, rising temp."""
    for i, temp in enumerate(RETRY_TEMPS):
        out = call_llm(system, user, temperature=temp, max_tokens=max_tokens)
        if out and len(out) >= 10:
            return out
        with _stats_lock:
            STATS["retries"] += 1
    return out


# ---------------------------------------------------------------------------
# Phase 1–3
# ---------------------------------------------------------------------------

def sequence_text(segments: list) -> str:
    return "\n".join(f"[§{s['seq']}] {s['text']}" for s in segments)


def _ws_norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def verify_beleg(output: str, norm_ws: str) -> bool:
    quotes = re.findall(r"«(.+?)»", output, re.S)
    if not quotes:
        return False
    return all(_ws_norm(q) in norm_ws for q in quotes)


def run_segment(seg, seq_text, prompts, norm_ws):
    n = seg["seq"]
    rec = {"seq": n, "char_start": seg["char_start"], "char_end": seg["char_end"],
           "model": f"mammouth/{MODEL}",
           "prov": {"rekonstruktion": "r", "bewegung": "r", "standort": "r"}}

    # P1 — reconstruction (system + sequence prefix; user per spec)
    p1_system = prompts["P1"] + f"\n\n[GESAMTE SEGMENT-SEQUENZ — §-Nummern global]\n{seq_text}"
    p1_user = (f"Rekonstruiere das Segment [§{n}]. Die ganze Sequenz liegt dir vor — "
               f"eine Stütze kann anderswo im Text eingelöst sein.")
    out1 = call_with_retry_idiom(p1_system, p1_user)
    if "KEIN EIGENSTÄNDIGER ZUG" in out1.upper()[:80]:
        rec["gate"] = "kein_zug"
        tm = re.search(r"—\s*(.+)$", out1.splitlines()[0])
        rec["gate_typ"] = tm.group(1).strip() if tm else "unbenannt"
    else:
        rec["gate"] = "zug"
        rec["gate_typ"] = None
        if not verify_beleg(out1, norm_ws):
            with _stats_lock:
                STATS["beleg_failures"] += 1
            out1b = call_with_retry_idiom(
                p1_system,
                p1_user + "\n\nBELEG ist kein wörtliches Zitat — zitiere exakt.")
            if verify_beleg(out1b, norm_ws):
                out1, rec["beleg_verified"] = out1b, True
            else:
                rec["beleg_verified"] = False
        else:
            rec["beleg_verified"] = True
        for field, pat in (("rekonstruktion", r"REKONSTRUKTION:\s*(.+?)(?=\n[A-ZÄÖÜ]+:|\Z)"),
                           ("stuetzung", r"STÜTZUNG:\s*(.+?)(?=\n[A-ZÄÖÜ]+:|\Z)"),
                           ("beleg", r"BELEG:\s*(«.+?»)")):
            mm = re.search(pat, out1, re.S)
            rec[field] = _ws_norm(mm.group(1)) if mm else None
        rec["begriffe"] = [
            {"term": _ws_norm(t), "herkunft": _ws_norm(h)}
            for t, h in re.findall(r"BEGRIFF:\s*(.+?)\s*\|\s*HERKUNFT:\s*(.+)", out1)
        ]
    rec["p1_raw"] = out1

    # P2 — movement (blind to P1; own system prefix per spec)
    p2_system = (prompts["P2"]
                 .replace("{titel}", DOC_META["titel"])
                 .replace("{autoren}", DOC_META["autoren"])
                 .replace("{jahr}", DOC_META["jahr"])
                 .replace("{sequenceText}", seq_text))
    p2_user = (f"[ANKER-SEGMENT §{n}]\n[§{n}] {seg['text']}\n\n"
               f"Erzeuge jetzt die reflektierende Interpretation für dieses Anker-Segment.")
    out2 = call_with_retry_idiom(p2_system, p2_user)
    mm = re.search(r"##\s*BEWEGUNG\s*\n(.+)", out2, re.S)
    rec["bewegung"] = _ws_norm(mm.group(1) if mm else out2)

    # P3 — standpoint (gate-driven)
    p3_system = prompts["P3"] + f"\n\n[GANZER TEXT — KO-PRÄSENT]\n{seq_text}"
    p3_user = f"[ANKER-SEGMENT §{n} — analysieren]\n[§{n}] {seg['text']}"
    out3 = call_with_retry_idiom(p3_system, p3_user)
    rec["standort"] = None if "KEIN METHODISCHER STANDORT" in out3.upper() else _ws_norm(out3)
    return rec


def records_digest(records: list) -> str:
    lines = []
    for r in sorted(records, key=lambda x: x["seq"]):
        if r["gate"] == "kein_zug":
            lines.append(f"[§{r['seq']}] KEIN EIGENSTÄNDIGER ZUG — {r['gate_typ']}")
            continue
        lines.append(f"[§{r['seq']}] REKONSTRUKTION: {r.get('rekonstruktion')}")
        if r.get("stuetzung"):
            lines.append(f"  STÜTZUNG: {r['stuetzung']}")
        if r.get("beleg"):
            v = "" if r.get("beleg_verified") else " [beleg nicht verifiziert]"
            lines.append(f"  BELEG: {r['beleg']}{v}")
        if r.get("bewegung"):
            lines.append(f"  BEWEGUNG: {r['bewegung']}")
        if r.get("standort"):
            lines.append(f"  STANDORT: {r['standort']}")
        for b in r.get("begriffe", []):
            lines.append(f"  BEGRIFF: {b['term']} | HERKUNFT: {b['herkunft']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main phases
# ---------------------------------------------------------------------------

def phase0() -> tuple:
    raw = RAW.read_text(encoding="utf-8")
    norm = normalize(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "norm.md").write_text(norm, encoding="utf-8")
    segments = segment_document(norm)
    topo = citation_topology(norm, segments)
    # determinism check: second run must be identical
    again = segment_document(norm)
    deterministic = [s["text"] for s in segments] == [s["text"] for s in again]
    report = {
        "segmenter": "bib-seg-v1",
        "n_segments": len(segments),
        "deterministic_recheck": deterministic,
        "operative_sources": {n: {"dens": a["dens"], "mult": a["mult"],  # self-authors excluded (TRAJEKTORIE)
                                  "route": a["route"], "sigma": a["sigma"],
                                  "segments": a["segments"]}
                              for n, a in sorted(topo["authors"].items(),
                                                 key=lambda kv: -kv[1]["dens"])
                              if a["op"] and n not in DOC_META["authors_last"]},
        "escalate": [n for n, a in topo["authors"].items()
                     if a["route"] == "escalate" and a["op"]
                     and n not in DOC_META["authors_last"]],
        "self_citations": topo["self_citations"],
    }
    (OUT / "phase0.json").write_text(
        json.dumps({"report": report, "segments": segments}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    probe = "\n\n".join(f"[§{s['seq']}] ({s['sentences']} Satz/Sätze) {s['text'][:220]}"
                        for s in segments[:10])
    (OUT / "phase0_report.md").write_text(
        f"# Phase 0 — bib-seg-v1 (deterministisch)\n\n"
        f"Segmente: **{report['n_segments']}** (Spec-Band 75–110) · "
        f"Determinismus-Recheck: {'bit-identisch' if deterministic else 'ABWEICHUNG!'}\n\n"
        f"## Segmentgrenzen-Probe (erste 10)\n\n{probe}\n\n"
        f"## Operative Quellen (dens ≥ 3)\n\n"
        + "\n".join(f"- **{n}**: dens={a['dens']}, mult={a['mult']}, route={a['route']}"
                    + (f", σ={a['sigma']}" if a['sigma'] else "")
                    + f", Segmente {a['segments']}"
                    for n, a in report["operative_sources"].items())
        + f"\n\n## Eskalation (P4): {report['escalate'] or 'keine'}\n"
        f"\n## Selbstzitat-Kandidaten (TRAJEKTORIE): {report['self_citations'] or 'keine'}\n",
        encoding="utf-8")
    return norm, segments, topo, report


def run_all(max_segments=None):
    prompts = load_prompts()
    norm, segments, topo, report = phase0()
    norm_ws = _ws_norm(norm)
    seq_text = sequence_text(segments)
    todo = segments if max_segments is None else segments[:max_segments]

    records_path = OUT / "records.jsonl"
    done = {}
    if records_path.exists():
        for line in records_path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                done[r["seq"]] = r
            except Exception:
                pass
    pending = [s for s in todo if s["seq"] not in done]
    print(f"Phase 1: {len(pending)} von {len(todo)} Segmenten offen "
          f"(conc {CONCURRENCY}) …", flush=True)

    lock = threading.Lock()
    with records_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
            futures = {ex.submit(run_segment, s, seq_text, prompts, norm_ws): s
                       for s in pending}
            for fut in as_completed(futures):
                seg = futures[fut]
                try:
                    rec = fut.result()
                except Exception as e:
                    print(f"  §{seg['seq']} FEHLER: {e}", flush=True)
                    continue
                with lock:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
                    done[rec["seq"]] = rec
                    if len(done) % 10 == 0:
                        print(f"  {len(done)}/{len(todo)} Segmente · "
                              f"{STATS['prompt_tokens']//1000}k in / "
                              f"{STATS['completion_tokens']//1000}k out", flush=True)

    # Done-Gate (spec §3.2): all N segments must carry records before P4/P5
    missing = [s["seq"] for s in todo if s["seq"] not in done]
    if missing:
        raise SystemExit(f"Done-Gate verletzt — Segmente ohne Record: {missing}")

    records = [done[s["seq"]] for s in todo]

    # Phase 2 — P4 per escalated operative source
    resolved = {}
    for name, a in topo["authors"].items():
        if name in DOC_META["authors_last"]:
            continue  # self-citation -> TRAJEKTORIE, never QUELLEN
        if a["op"] and a["route"] == "cheap":
            rel = "affirms" if a["sigma"] == "+" else "reserves"
            resolved[name] = {"relation": rel, "prov": "c",
                              "line": f"QUELLE: {name} | RELATION: {rel} (σ-cheap, konkordant)"}
    escalate = [n for n, a in topo["authors"].items()
                if a["op"] and a["route"] == "escalate"
                and n not in DOC_META["authors_last"]]
    print(f"Phase 2: {len(escalate)} Eskalation(en): {escalate}", flush=True)
    for name in escalate:
        a = topo["authors"][name]
        user = (f"Quelle: {name}. Zitierende Segmente: "
                + ", ".join(f"§{q}" for q in a["segments"])
                + ". Bestimme jetzt die Haltung des Werks zu dieser Quelle.")
        p4_system = prompts["P4"] + f"\n\n[GANZER TEXT — KO-PRÄSENT]\n{seq_text}"
        out = call_with_retry_idiom(p4_system, user)
        mm = re.search(r"RELATION:\s*(affirms|extends|contrasts|reserves|rejects)", out)
        resolved[name] = {"relation": mm.group(1) if mm else "reserves",
                          "prov": "r", "line": _ws_norm(out)}

    # Phase 3 — P5 profile reduction
    checklist = "\n".join(
        f"- {n} (dens={a['dens']}, mult={a['mult']}, op=ja, Segmente "
        + ", ".join(f"§{q}" for q in a["segments"]) + ")"
        for n, a in sorted(topo["authors"].items(), key=lambda kv: -kv[1]["dens"])
        if a["op"] and n not in DOC_META["authors_last"])
    resolved_txt = "\n".join(v["line"] for v in resolved.values()) or "—"
    p5_user = (f"[SEGMENT-RECORDS — „{DOC_META['titel']}“]\n"
               f"{records_digest(records)}\n\n"
               f"[OPERATIVE QUELLEN — Checkliste aus der Zitationsanalyse]\n{checklist or '—'}\n\n"
               f"[ENTSCHIEDENE HALTUNGEN]\n{resolved_txt}\n\n"
               f"Erzeuge jetzt das diskursive Profil dieses Werks in den fünf Blöcken.")
    print("Phase 3: P5 Profil-Reduktion …", flush=True)
    profile = call_with_retry_idiom(prompts["P5"], p5_user)
    (OUT / "profile.md").write_text(profile, encoding="utf-8")

    # Fallgestalt (types.ts-treu, minimal assembly per spec §3.4)
    fall = build_fallgestalt(profile, topo, resolved)
    (OUT / "fallgestalt.json").write_text(
        json.dumps(fall, ensure_ascii=False, indent=1), encoding="utf-8")

    (OUT / "run_stats.json").write_text(json.dumps(STATS, indent=1), encoding="utf-8")
    render_review(report, records, profile, resolved)
    print("FERTIG:", json.dumps(STATS), flush=True)


def build_fallgestalt(profile: str, topo: dict, resolved: dict) -> dict:
    def block(name):
        m = re.search(rf"\[{name}\]\s*\n(.*?)(?=\n\[[A-Z]+\]|\Z)", profile, re.S)
        return (m.group(1).strip() if m else "")

    V, E = [], []
    pos = block("SELBSTPOSITION")
    anchors = [int(x) for x in re.findall(r"§(\d+)", pos)]
    V.append({"kind": "position", "goal": pos.split("|")[0].replace("ZIEL:", "").strip(),
              "anchors": anchors, "prov": "r"})
    for name, a in topo["authors"].items():
        if not a["op"] or name in DOC_META["authors_last"]:
            continue
        rel = resolved.get(name, {}).get("relation")
        V.append({"kind": "source", "id": name, "mult": a["mult"], "dens": a["dens"],
                  "op": True, "anchors": a["segments"],
                  "prov": {"topology": "c", "stance": resolved.get(name, {}).get("prov")}})
        if rel:
            exported = "affirms" if rel in ("affirms", "extends") else "reserves"
            E.append({"kind": exported, "internalKind": rel, "from": "position",
                      "to": name, "sigma": "+" if exported == "affirms" else "-"})
    for t, h, anch in re.findall(
            r"BEGRIFF:\s*(.+?)\s*\|\s*HERKUNFT:\s*(.+?)\s*\|\s*ANKER:\s*([^|]+)", profile):
        V.append({"kind": "term", "id": _ws_norm(t), "coinedBy": _ws_norm(h),
                  "anchors": [int(x) for x in re.findall(r"§(\d+)", anch)], "prov": "r"})
        E.append({"kind": "coins", "from": "position", "to": _ws_norm(t)})
    for line in block("TRAJEKTORIE").splitlines():
        if line.strip().startswith("SELBSTBEZUG"):
            E.append({"kind": "trajectory", "from": "position",
                      "detail": _ws_norm(line)})
    return {"V": V, "E": E,
            "meta": {"doc": DOC_META, "model": f"mammouth/{MODEL}",
                     "segmenter": "bib-seg-v1", "status": "draft"}}


def render_review(report, records, profile, resolved):
    n_zug = sum(1 for r in records if r["gate"] == "zug")
    n_verified = sum(1 for r in records if r.get("beleg_verified"))
    seg_render = records_digest(records)
    md = (f"# H7-Pilot — Jörissen et al. 2025 „Wahrnehmungskrisen“ — ERGEBNIS ZUR SICHTUNG\n\n"
          f"Modell: mammouth/{MODEL} · Segmenter bib-seg-v1 · Status: **draft** (kein Publish)\n\n"
          f"Segmente: {report['n_segments']} · davon mit eigenständigem Zug: {n_zug} · "
          f"BELEG wörtlich verifiziert: {n_verified}/{n_zug} · "
          f"Tokens: {STATS['prompt_tokens']//1000}k in / {STATS['completion_tokens']//1000}k out · "
          f"Calls: {STATS['calls']} (Retries {STATS['retries']}, BELEG-Retries {STATS['beleg_failures']})\n\n"
          f"---\n\n## PROFIL (P5 — die fünf H7-Blöcke, wörtlich)\n\n```\n{profile}\n```\n\n"
          f"---\n\n## SEGMENTE (vollständig, §0–§{report['n_segments']-1})\n\n```\n{seg_render}\n```\n")
    (OUT / "REVIEW.md").write_text(md, encoding="utf-8")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--phase0", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--max-segments", type=int, default=None)
    args = ap.parse_args()
    if args.smoke:
        out = call_llm("Antworte mit genau einem Wort.", "Sag: bereit", 0.0, 10)
        print("SMOKE:", repr(out), "| usage:", STATS)
        sys.exit(0)
    if args.phase0:
        _, segments, topo, report = phase0()
        print(json.dumps(report, ensure_ascii=False, indent=1))
        sys.exit(0)
    if args.run:
        run_all(max_segments=args.max_segments)
        sys.exit(0)
    ap.print_help()
