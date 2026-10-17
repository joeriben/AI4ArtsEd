#!/usr/bin/env python3
"""Substanz-Verdichtung — Single-Pass runner (one document).

Per docs/plans/knowledge/SPEC_substance_singlepass_2026-07-08.md:
liest EINEN wissenschaftlichen Text ko-präsent (deterministische Phase-0-
Segmentierung `bib-seg-v1`) und verdichtet ihn in EINEM Work-Pass-Call auf die
SUBSTANZ-Karte (KERNTHESE/KERNAUSSAGEN/GANG/KERNBEGRIFFE/STRITTIG/PRAXISBEZUG)
als internes Arbeitsmaterial für Resona. Kein Urteil, keine Diskurs-Verortung
(die geparkte Fallgestalt-/MoJo-Linie bleibt in h7_pilot_runner.py).

Der Frozen Prompt wird VERBATIM aus der Spec gelesen (Single Source, kein Copy-
Drift). Die deterministische Segmentierung wird aus h7_pilot_runner importiert
(eine Quelle für bib-seg-v1). Die API-Seite (Mammouth-Call, Retry, BELEG-Gate)
ist eigenständig, damit Modellwahl/Verifikation dieser Linie gehören.

Pilot-grade (Ein-Dokument-Gate): schreibt nur unter
devserver/exports/knowledge_pilot/ (server-local, gitignored). Kein Publish.

Usage (repo root, venv):
  venv/bin/python devserver/scripts/substance_pilot_runner.py --smoke
  venv/bin/python devserver/scripts/substance_pilot_runner.py --phase0
  venv/bin/python devserver/scripts/substance_pilot_runner.py --dry-run
  venv/bin/python devserver/scripts/substance_pilot_runner.py --run [--model NAME] [--doc PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path

import requests

# deterministische Phase 0 (bib-seg-v1) + Doc-Meta aus dem H7-Runner (single source)
from h7_pilot_runner import normalize, segment_document, sequence_text, DOC_META, RAW as DEFAULT_RAW

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs/plans/knowledge/SPEC_substance_singlepass_2026-07-08.md"
OUT = REPO / "devserver/exports/knowledge_pilot/substance_joerissen"
sys.path.insert(0, str(REPO / "devserver"))
from my_app.services.llm_providers import credentials  # noqa: E402

# Address and key from the one table (config/llm_providers.json), S-058.
API_URL, _API_KEY = credentials("mammouth")

# Haus-Provider Mammouth; qwen3.7-plus als Talent-Kandidat (--model tauscht).
DEFAULT_MODEL = "qwen3.7-plus"
MODEL = DEFAULT_MODEL
RETRY_TEMPS = [0.0, 0.25, 0.5, 0.6]
MAX_TOKENS = 8000

USER_TRIGGER = ("Lege jetzt die SUBSTANZ des ganzen Werks frei. Gib GENAU die "
                "vorgegebenen Blöcke aus, jeden mit seiner Kopfzeile in eckigen Klammern.")

STATS = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
         "retries": 0, "beleg_failures": 0, "errors": 0}
_stats_lock = threading.Lock()


# ── Prompt (verbatim aus der Spec) ─────────────────────────────────────────────

def load_prompt() -> str:
    md = SPEC.read_text(encoding="utf-8")
    m = re.search(r"##\s*PROMPT[^\n]*\n+```[a-z]*\n(.*?)\n```", md, re.S)
    if not m:
        raise SystemExit(f"Prompt-Block nicht in Spec gefunden: {SPEC}")
    return m.group(1).strip()


def build_system(frozen_prompt: str, seq_text: str) -> str:
    return f"{frozen_prompt}\n\n[GANZER TEXT — KO-PRÄSENT, §-nummeriert]\n{seq_text}"


# ── Mammouth-Call (eigenständig) ───────────────────────────────────────────────

def _api_key() -> str:
    return _API_KEY


def call_llm(system: str, user: str, temperature: float = 0.0,
             max_tokens: int = MAX_TOKENS) -> str:
    body = {"model": MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature, "max_tokens": max_tokens}
    for attempt in range(6):
        try:
            r = requests.post(API_URL, json=body, timeout=300,
                              headers={"Authorization": f"Bearer {_api_key()}"})
            if r.status_code == 429:  # Mammouth rolling model-group limit
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
        except requests.RequestException:
            if attempt == 5:
                with _stats_lock:
                    STATS["errors"] += 1
                raise
            time.sleep(6 * (attempt + 1))
    return ""


def call_with_retry_idiom(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    """SARAH callText idiom: empty/degenerate -> up to 4 tries, rising temp."""
    out = ""
    for temp in RETRY_TEMPS:
        out = call_llm(system, user, temperature=temp, max_tokens=max_tokens)
        if out and len(out) >= 40:
            return out
        with _stats_lock:
            STATS["retries"] += 1
    return out


# ── BELEG-Verifikation (C-Korrektur: Ellipsen-Split + Typo-Kanonisierung) ──────

_QUOTE_MAP = {
    "„": '"', "“": '"', "”": '"', "«": '"', "»": '"',
    "‚": "'", "‘": "'", "’": "'", "‹": "'", "›": "'",
    "–": "-", "—": "-", "…": "...",
}


def _canon(s: str) -> str:
    s = s or ""
    for k, v in _QUOTE_MAP.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


def _fragments(quote_canon: str) -> list:
    """Elidiertes Zitat «A [...] B» / «A … B» -> Fragmente ['A','B'] (>=3 Zeichen)."""
    parts = re.split(r"\s*\[?\s*\.\.\.\s*\]?\s*", quote_canon)
    return [p for p in (x.strip() for x in parts) if len(p) >= 3]


def check_belege(output: str, source_canon: str) -> list:
    """Je BELEG-Zitat «...» im Output: (Zitat, ok?) gegen den kanonisierten Quelltext."""
    res = []
    for q in re.findall(r"«(.+?)»", output, re.S):
        frags = _fragments(_canon(q))
        ok = bool(frags) and all(f in source_canon for f in frags)
        res.append((q.strip(), ok))
    return res


# ── Phase 0 (leicht: nur Segmentierung + Determinismus, keine Topologie) ───────

def phase0(raw_path: Path, out_dir: Path) -> tuple:
    raw = raw_path.read_text(encoding="utf-8")
    norm = normalize(raw)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "norm.md").write_text(norm, encoding="utf-8")
    segments = segment_document(norm)
    again = segment_document(norm)
    deterministic = [s["text"] for s in segments] == [s["text"] for s in again]
    report = {"segmenter": "bib-seg-v1", "n_segments": len(segments),
              "deterministic_recheck": deterministic}
    (out_dir / "phase0.json").write_text(
        json.dumps({"report": report, "segments": segments}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return norm, segments, report


# ── Dry-Run (Phase 0 + Prompt-Assembly, KEIN LLM-Call) ─────────────────────────

def dry_run(raw_path: Path, out_dir: Path, frozen_prompt: str) -> str:
    norm, segments, report = phase0(raw_path, out_dir)
    seq_text = sequence_text(segments)
    system = build_system(frozen_prompt, seq_text)
    (out_dir / "assembled_system_prompt.txt").write_text(system, encoding="utf-8")
    head = "\n\n".join(f"[§{s['seq']}] ({s['sentences']} Satz/Sätze) {s['text'][:200]}"
                       for s in segments[:5])
    tail = "\n\n".join(f"[§{s['seq']}] {s['text'][:160]}" for s in segments[-3:])
    md = (f"# Dry-Run — {DOC_META['titel']} — Phase 0 + Prompt-Assembly (KEIN LLM-Call)\n\n"
          f"Segmente: **{report['n_segments']}** · Determinismus-Recheck: "
          f"{'bit-identisch' if report['deterministic_recheck'] else 'ABWEICHUNG!'}\n\n"
          f"System-Prompt = Frozen Prompt + ko-präsente §-Sequenz: **{len(system)} Zeichen** "
          f"(→ assembled_system_prompt.txt)\n\n"
          f"## Frozen Prompt (Kopf, {len(frozen_prompt)} Zeichen gesamt)\n\n"
          f"```\n{frozen_prompt[:1400]}\n…\n```\n\n"
          f"## Segmentgrenzen-Probe (erste 5)\n\n{head}\n\n"
          f"## … (letzte 3)\n\n{tail}\n")
    (out_dir / "DRYRUN.md").write_text(md, encoding="utf-8")
    return md


# ── Run (ein Work-Pass) ────────────────────────────────────────────────────────

def run_work_pass(system: str, source_canon: str) -> tuple:
    out = call_with_retry_idiom(system, USER_TRIGGER, max_tokens=MAX_TOKENS)
    belege = check_belege(out, source_canon)
    n_ok = sum(1 for _, ok in belege if ok)
    # Ein korrektiver Retry NUR, wenn Belege da sind, aber KEINER verifiziert
    # (systematisches Zitat-Format-Problem) — sonst annotieren wir bloß.
    if belege and n_ok == 0:
        with _stats_lock:
            STATS["beleg_failures"] += 1
        out2 = call_with_retry_idiom(
            system,
            USER_TRIGGER + "\n\nDeine BELEG-Zitate stimmen wörtlich nicht mit dem Text "
            "überein. Zitiere jeden BELEG BUCHSTABENGETREU aus dem vorliegenden Text.",
            max_tokens=MAX_TOKENS)
        b2 = check_belege(out2, source_canon)
        if sum(1 for _, ok in b2 if ok) > n_ok:
            out, belege = out2, b2
    return out, belege


def render_review(report: dict, output: str, belege: list, out_dir: Path,
                  model: str, doc_title: str) -> str:
    n_b = len(belege)
    n_ok = sum(1 for _, ok in belege if ok)
    annotated = output
    for q, ok in belege:
        if not ok:
            annotated = annotated.replace(f"«{q}»", f"«{q}» [BELEG nicht verifiziert]", 1)
    md = (f"# Substanz-Verdichtung — {doc_title} — ERGEBNIS ZUR SICHTUNG\n\n"
          f"Modell: mammouth/{model} · Segmenter bib-seg-v1 · Single-Pass · "
          f"Status: **draft** (kein Publish)\n\n"
          f"Segmente: {report['n_segments']} · Determinismus: "
          f"{'ok' if report['deterministic_recheck'] else 'ABWEICHUNG!'} · "
          f"BELEG wörtlich verifiziert: **{n_ok}/{n_b}** · "
          f"Tokens: {STATS['prompt_tokens']//1000}k in / {STATS['completion_tokens']//1000}k out · "
          f"Calls: {STATS['calls']} (Retries {STATS['retries']}, BELEG-Retry {STATS['beleg_failures']})\n\n"
          f"---\n\n## SUBSTANZ-KARTE (verbatim)\n\n```\n{annotated}\n```\n")
    (out_dir / "REVIEW.md").write_text(md, encoding="utf-8")
    return md


def run_all(raw_path: Path, out_dir: Path, frozen_prompt: str) -> None:
    norm, segments, report = phase0(raw_path, out_dir)
    seq_text = sequence_text(segments)
    system = build_system(frozen_prompt, seq_text)
    source_canon = _canon(norm)
    print(f"Phase 0: {report['n_segments']} Segmente · "
          f"Determinismus {'ok' if report['deterministic_recheck'] else 'ABWEICHUNG'} · "
          f"System-Prompt {len(system)} Zeichen · Modell {MODEL}")
    out, belege = run_work_pass(system, source_canon)
    n_ok = sum(1 for _, ok in belege if ok)
    render_review(report, out, belege, out_dir, MODEL, DOC_META["titel"])
    print(f"Fertig: {len(out)} Zeichen · BELEG {n_ok}/{len(belege)} verifiziert · "
          f"{STATS['prompt_tokens']//1000}k in / {STATS['completion_tokens']//1000}k out · "
          f"→ {out_dir / 'REVIEW.md'}")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--phase0", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Mammouth-Modell (Talent-Vergleich)")
    ap.add_argument("--doc", default=str(DEFAULT_RAW), help="Pfad zum .raw.md-Dokument")
    args = ap.parse_args()

    MODEL = args.model  # rebind module global -> call_llm nutzt es
    raw_path = Path(args.doc)

    if args.smoke:
        out = call_llm("Antworte mit genau einem Wort.", "Sag: bereit", 0.0, 10)
        print("SMOKE:", repr(out), "| model:", MODEL, "| usage:", STATS)
        sys.exit(0)
    if args.phase0:
        _, segments, report = phase0(raw_path, OUT)
        print(json.dumps(report, ensure_ascii=False, indent=1))
        sys.exit(0)
    if args.dry_run:
        frozen = load_prompt()
        md = dry_run(raw_path, OUT, frozen)
        print(md)
        sys.exit(0)
    if args.run:
        frozen = load_prompt()
        run_all(raw_path, OUT, frozen)
        sys.exit(0)
    ap.print_help()
