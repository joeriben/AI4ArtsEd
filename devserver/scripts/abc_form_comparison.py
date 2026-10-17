#!/usr/bin/env python3
"""A/B/C comparison: three library forms serve the same five consulting
questions to Resona's real model. Output is MATERIAL ONLY (verbatim answers,
setup constants, sizes) — no judgments.

A = normalized full text (norm.md)
B = old 9-chunk Verdichtung (exports/knowledge_library/<doc>.md, draft)
C = H7 pilot form (profile.md + full segment-record digest)

Idempotent: answers persist in abc_results.json (recovered from an existing
VERGLEICH md if the json is missing); reruns fill only failed/missing cells.
"""
from __future__ import annotations

import glob
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "devserver/exports/knowledge_pilot/h7_joerissen"
OUT_MD = REPO / "docs/plans/knowledge/VERGLEICH_abc_bibliotheksformen_2026-07-07.md"
OUT_JSON = PILOT / "abc_results.json"

sys.path.insert(0, str(REPO / "devserver/scripts"))
from h7_pilot_runner import records_digest  # noqa: E402  (verbatim reuse)

MODEL = "claude-opus-4-8"          # Resonas reales Modell (PERSONA_MODEL), via Mammouth
TEMPERATURE = 0.7                   # Resonas Chat-Default
MAX_TOKENS = 900
sys.path.insert(0, str(REPO / "devserver"))
from my_app.services.llm_providers import credentials  # noqa: E402

# Address and key from the one table (config/llm_providers.json), S-058.
API, KEY = credentials("mammouth")

FORM_A = (PILOT / "norm.md").read_text(encoding="utf-8")

b_matches = glob.glob(str(REPO / "devserver/exports/knowledge_library/jorissen-et-al-2025-*.md"))
assert len(b_matches) == 1, f"alte Verdichtung nicht eindeutig: {b_matches}"
FORM_B = Path(b_matches[0]).read_text(encoding="utf-8")

records = [json.loads(l) for l in (PILOT / "records.jsonl").read_text(encoding="utf-8").splitlines()]
FORM_C = ("[PROFIL]\n" + (PILOT / "profile.md").read_text(encoding="utf-8")
          + "\n\n[SEGMENT-RECORDS]\n" + records_digest(records))

FORMS = [
    ("A", "Volltext (norm.md)", FORM_A),
    ("B", "Alte Verdichtung (9-Chunk-Kompaktdatei, draft)", FORM_B),
    ("C", "H7-Form (PROFIL + Segment-Records)", FORM_C),
]
FORM_BY_KEY = {k: (label, mat) for k, label, mat in FORMS}

SYSTEM_TEMPLATE = """Du bist Resona, die kunstpädagogische Begleiterin dieser Plattform — beratend für eine Kursleitung (Planung/Nachgespräch) oder anwesend in der Werkstattgruppe. Deine Disziplin: Du arbeitest mit dem Wissen aus dem bereitgestellten Bibliotheks-Material — paraphrasiert, eine Tür nach der anderen, keine Vorträge. Fachliche Aussagen stützt du auf das Material; wörtlich zitierst du nur, wenn ausdrücklich danach gefragt ist, dann exakt und mit Fundstelle. Trägt das Material eine Antwort nicht, sagst du das klar, statt zu erfinden. Antworte auf Deutsch, knapp und brauchbar für die jeweilige Situation.

[BIBLIOTHEKS-MATERIAL zu: Jörissen/Klepacki/Flasche/Zahn 2025, „Wahrnehmungskrisen. Generative Künstliche Intelligenz als Herausforderung pädagogischer und erziehungswissenschaftlicher Wahrnehmungsweisen"]
{material}"""

QUESTIONS = [
    ("Q1", "Planung",
     'Was heißt „Wahrnehmungskrise" — und was folgt daraus für meinen Kurs?'),
    ("Q2", "Werkstatt",
     'Die Gruppe hat gerade ein Bild mit der Maschine erzeugt und fragt dich: „Sieht die Maschine das wie wir?"'),
    ("Q3", "Planung",
     'Wie thematisiere ich KI-Opazität mit Jugendlichen künstlerisch?'),
    ("Q4", "Planung/Kollegengespräch",
     'Eine Kollegin meint, KI sei doch nur ein Werkzeug wie der Taschenrechner — was gibt mir der Text an die Hand, um darauf zu antworten?'),
    ("Q5", "Zitierstellen",
     'Gib mir die zwei tragenden Stellen zum Begriff „Wahrnehmungskrise" im Wortlaut mit Fundstelle — fürs Konzeptpapier.'),
]

_lock = threading.Lock()
results: dict = {}
usage_stats: dict = {}


def _key(qk: str, fk: str) -> str:
    return f"{qk}:{fk}"


def _is_ok(text) -> bool:
    return bool(text) and not str(text).startswith(("[API-FEHLER", "[fehlt]"))


def load_state() -> None:
    if OUT_JSON.exists():
        data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        results.update(data.get("results", {}))
        usage_stats.update(data.get("usage", {}))
        return
    if OUT_MD.exists():
        md = OUT_MD.read_text(encoding="utf-8")
        pat = re.compile(
            r"^### (Q\d)·([ABC]) — .*?\((.*?)\)\n\n(.*?)(?=^### |^---$|\Z)",
            re.S | re.M)
        for qk, fk, tok, body in pat.findall(md):
            results[_key(qk, fk)] = body.strip()
            m = re.match(r"(\d+) in / (\d+) out", tok)
            usage_stats[_key(qk, fk)] = (
                {"prompt_tokens": int(m.group(1)), "completion_tokens": int(m.group(2))}
                if m else {})
        print(f"aus MD rekonstruiert: {sum(1 for v in results.values() if _is_ok(v))} ok")


def save_state() -> None:
    OUT_JSON.write_text(json.dumps(
        {"results": results, "usage": usage_stats}, ensure_ascii=False, indent=1),
        encoding="utf-8")


def ask(fk: str, qk: str, situation: str, frage: str) -> None:
    material = FORM_BY_KEY[fk][1]
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_TEMPLATE.replace("{material}", material)},
            {"role": "user", "content": f"[Situation: {situation}]\n{frage}"},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    last_err = None
    for attempt in range(6):
        try:
            r = requests.post(API, json=body, timeout=240,
                              headers={"Authorization": f"Bearer {KEY}"})
            if r.status_code == 429:
                time.sleep(60)
                continue
            r.raise_for_status()
            data = r.json()
            content = (data["choices"][0]["message"]["content"] or "").strip()
            usage = data.get("usage", {})
            with _lock:
                results[_key(qk, fk)] = content
                usage_stats[_key(qk, fk)] = usage
                save_state()
            print(f"  {qk}/{fk}: ok ({usage.get('prompt_tokens','?')} in / "
                  f"{usage.get('completion_tokens','?')} out)", flush=True)
            return
        except requests.RequestException as e:
            last_err = e
            time.sleep(15 * (attempt + 1))
    with _lock:
        results[_key(qk, fk)] = f"[API-FEHLER nach 6 Versuchen: {last_err}]"
        usage_stats[_key(qk, fk)] = {}
        save_state()


def render() -> None:
    lines = []
    lines.append("# A/B/C-Vergleich der Bibliotheksformen am Jörissen-Paper — MATERIAL (keine Wertung)")
    lines.append("")
    lines.append("Datum: 2026-07-07 · Modell: mammouth/" + MODEL
                 + f" (Resonas PERSONA_MODEL) · temperature {TEMPERATURE} · max_tokens {MAX_TOKENS}"
                 + " · 3 Formen × 5 Fragen = 15 Calls, identisches Framing")
    lines.append("")
    lines.append("## Formen (Quellen + Umfang)")
    for fk, label, mat in FORMS:
        lines.append(f"- **{fk} — {label}**: {len(mat):,} Zeichen".replace(",", "."))
    lines.append("- Quellen: A `exports/knowledge_pilot/h7_joerissen/norm.md`; "
                 "B `" + Path(b_matches[0]).name + "` (exports/knowledge_library/, status draft); "
                 "C `profile.md` + `records.jsonl` (records_digest des Pilot-Runners).")
    lines.append("")
    lines.append("## System-Prompt (wörtlich, identisch für alle; {material} = jeweilige Form)")
    lines.append("")
    lines.append("```")
    lines.append(SYSTEM_TEMPLATE)
    lines.append("```")
    lines.append("")
    lines.append("## Fragen (wörtlich)")
    for qk, sit, fr in QUESTIONS:
        lines.append(f"- **{qk}** [{sit}]: {fr}")
    lines.append("")
    for qk, sit, fr in QUESTIONS:
        lines.append("---")
        lines.append("")
        lines.append(f"## {qk} [{sit}]: {fr}")
        lines.append("")
        for fk, label, _mat in FORMS:
            u = usage_stats.get(_key(qk, fk), {})
            tok = (f"{u.get('prompt_tokens','?')} in / {u.get('completion_tokens','?')} out"
                   if u else "n/a")
            lines.append(f"### {qk}·{fk} — {label} ({tok})")
            lines.append("")
            lines.append(results.get(_key(qk, fk), "[fehlt]"))
            lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    load_state()
    todo = [(fk, qk, sit, fr)
            for (qk, sit, fr) in QUESTIONS
            for (fk, _l, _m) in FORMS
            if not _is_ok(results.get(_key(qk, fk)))]
    print(f"{len(todo)} offene Calls (Modell {MODEL}, temp {TEMPERATURE}) …", flush=True)
    if todo:
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(ask, fk, qk, sit, fr) for (fk, qk, sit, fr) in todo]
            for f in as_completed(futs):
                f.result()
    render()
    n_err = sum(1 for v in results.values() if not _is_ok(v))
    total_in = sum(u.get("prompt_tokens", 0) for u in usage_stats.values())
    print(f"GESCHRIEBEN: {OUT_MD}")
    print(f"STAND: {15 - n_err}/15 ok, offene Fehler: {n_err}, kumuliert {total_in} in-Tokens")
