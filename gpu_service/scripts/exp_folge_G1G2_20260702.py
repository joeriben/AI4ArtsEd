#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folge-Reihe G1–G2 (2026-07-02) — VLM-Blindvalidierung des Prior-Zensus · Modellvergleich SD3.5-Medium.

Prä-registriertes Design: docs/analysis/embedding_subtraction/DESIGN_folgereihe_G1-G2_2026-07-02.md
  G1  Blinde Zweit-Kodierung der 120 F2-Bilder durch qwen3-vl:4b (Primär-Kodierer;
      32b-Zweit-Pass bedingt auf VRAM-Freigabe); Cohens κ + Konfusionsmatrix;
      Validierungs-Regel κ≥0.61 auf Mensch↔4b.
  G2  (bedingt) Prior-Zensus SD3.5-Medium: leerer Prompt, CFG 1.0, Seeds 1–120 — exakt F2
      bis auf model_id; VLM-kodiert + Hand-Stichprobe Seeds ≡ 1 mod 6.

Läuft AUF dem Fedora-Dev-Rechner. Phasen als Subkommandos:
  vlm-large [--model M]   G1a/G1b: 120 F2-Bilder blind kodieren → data_deconstruct_G/vlm_large_<tag>.csv
  agreement               G1c: κ/Konfusion/Sekundär-Übereinstimmung → agreement_stats.md + Regel-Entscheid
  gen-medium              G2a: 120 Medium-Zellen generieren (resumierbar, Heal wie F)
  vlm-medium [--model M]  G2b: Medium-Bilder blind kodieren → census_medium_vlm.csv
  tafeln-medium           G2c: 10 Tafeln à 12 → images_deconstruct_G/T9_G2_prior_NN.jpg
  stats-medium            G2c: Raten/Wilson Large↔Medium, Akkumulation, GT/Chao1, Basisstatistik
                          → census_medium_stats.md + spotcheck_skeleton.csv
  spotcheck --csv PATH    Stichproben-Übereinstimmung Hand↔VLM auf den 20 Spot-Seeds

GPU-Serialisierung: VLM-Phasen und Generierung nie gleichzeitig; gen-medium entlädt Ollama zuerst.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw

REPO = Path.home() / "ai" / "ai4artsed_development"
DOCA = REPO / "docs" / "analysis" / "embedding_subtraction"
DATA_G = DOCA / "data_deconstruct_G"
IMG_REPO_G = DOCA / "images_deconstruct_G"
HUMAN_CSV = DOCA / "data_deconstruct_F" / "census.csv"

OUT_F = Path.home() / "ai" / "deconstruct_suite_F"
OUT_G = Path.home() / "ai" / "deconstruct_suite_G"
IMG_G = OUT_G / "img"
MANIFEST_G = OUT_G / "manifest.jsonl"

OLLAMA = "http://127.0.0.1:11434/api/generate"
BASE = "http://127.0.0.1:17803/api/diffusers/generate/fusion"
AVAIL = "http://127.0.0.1:17803/api/diffusers/available"

M32 = "qwen3-vl:32b"
M4 = "qwen3-vl:4b"
MODEL_MEDIUM = "stabilityai/stable-diffusion-3.5-medium"
STEPS = 25
W = H = 1024
SPOT_SEEDS = list(range(1, 121, 6))  # ≡ 1 mod 6 → n=20

INSTRUCTION = """You are coding one AI-generated image for a research census. The image was
generated from an EMPTY prompt. Assign exactly ONE primary category and the
secondary tags defined below. Answer ONLY with a JSON object, no other text.

Primary category (field "primary", exactly one of):
- "K1" = a human figure or face is the dominant subject
- "K2" = object presentation: a single object staged like a product shot, on
  a pedestal/plinth, in a studio setting, or as a framed picture on a wall
- "K3" = text/typography is the dominant content
- "K4" = landscape or architecture without a dominant human figure
  (small/distant figures allowed)
- "K5" = an animal is the dominant subject
- "K6" = abstract, pattern, texture, or indeterminate content

Secondary tags:
- "malweise": rendering style, one of "malerisch" (painterly: visible
  brushwork, canvas/paint feel), "fotografisch" (photographic: camera-like
  realism, photo optics), "grafisch" (graphic/illustrative: flat shapes,
  print/drawing/illustration feel)
- "diorama": true if the scene looks like a miniature/diorama/model-scale
  arrangement, else false
- "schrift": true if ANY text or letter-like glyphs are visible (even
  non-dominant), else false
- "westlich": "ja" if the image shows a clearly Western iconographic
  signature (European portrait/oil-painting tradition, European architecture
  or clothing, Latin script), "nein" if it shows a clearly non-Western
  signature (e.g. East Asian, Islamic, South Asian iconography), "unklar"
  if neither is clearly identifiable
- If primary is "K1", also code the dominant figure: "geschlecht" one of
  "w"/"m"/"gemischt"/"unklar"; "alter" one of "kind"/"erwachsen"/"alt"/
  "unklar"; "hautton" one of "hell"/"mittel"/"dunkel"/"unklar".
  If primary is not "K1", set these three fields to "".

JSON: {"primary": "...", "malweise": "...", "diorama": false,
"schrift": false, "westlich": "...", "geschlecht": "...", "alter": "...",
"hautton": "..."}"""

PRIM = ("K1", "K2", "K3", "K4", "K5", "K6")
MALW = ("malerisch", "fotografisch", "grafisch")
WEST = ("ja", "nein", "unklar")
COLS = ["seed", "primary", "malweise", "diorama", "schrift", "westlich",
        "geschlecht", "alter", "hautton", "attempts", "dur_s", "status"]


# ---------------------------------------------------------------- VLM-Kodierung

def _coerce_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "ja", "yes", "1")


def _parse_vlm(text):
    # Flaches Ziel-JSON; Kandidaten von hinten (Thinking-Modelle können vorher Klammern emittieren)
    d = None
    for cand in reversed(re.findall(r"\{[^{}]*\}", text, re.S)):
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        if isinstance(obj, dict) and "primary" in obj:
            d = obj
            break
    if d is None:
        raise ValueError("kein JSON gefunden")
    prim = str(d.get("primary", "")).strip().upper()
    malw = str(d.get("malweise", "")).strip().lower()
    west = str(d.get("westlich", "")).strip().lower()
    if prim not in PRIM:
        raise ValueError(f"primary={prim!r}")
    if malw not in MALW:
        raise ValueError(f"malweise={malw!r}")
    if west not in WEST:
        raise ValueError(f"westlich={west!r}")
    row = {
        "primary": prim, "malweise": malw,
        "diorama": "ja" if _coerce_bool(d.get("diorama")) else "",
        "schrift": "ja" if _coerce_bool(d.get("schrift")) else "",
        "westlich": west,
        "geschlecht": "", "alter": "", "hautton": "",
    }
    if prim == "K1":
        g = str(d.get("geschlecht", "")).strip().lower()
        a = str(d.get("alter", "")).strip().lower()
        h = str(d.get("hautton", "")).strip().lower()
        row["geschlecht"] = g if g in ("w", "m", "gemischt", "unklar") else "unklar"
        row["alter"] = a if a in ("kind", "erwachsen", "alt", "unklar") else "unklar"
        row["hautton"] = h if h in ("hell", "mittel", "dunkel", "unklar") else "unklar"
    return row


_THINK_OK = {}


def ollama_code_image(model, png_path):
    b64 = base64.b64encode(png_path.read_bytes()).decode()
    payload = {
        "model": model, "prompt": INSTRUCTION, "images": [b64],
        "stream": False, "format": "json", "keep_alive": "15m",
        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192},
    }
    if _THINK_OK.get(model, True):
        payload["think"] = False
    r = requests.post(OLLAMA, json=payload, timeout=900)
    if r.status_code == 400 and "think" in r.text.lower() and "think" in payload:
        _THINK_OK[model] = False
        del payload["think"]
        r = requests.post(OLLAMA, json=payload, timeout=900)
    r.raise_for_status()
    d = r.json()
    # qwen3-vl routet die Ausgabe (inkl. JSON) ins thinking-Feld; response bleibt leer
    return (d.get("response") or "") + "\n" + (d.get("thinking") or "")


def vlm_pass(model, img_dir, seed_to_png, out_csv):
    """Blinde Einzel-Kodierung; resumierbar über vorhandene Seeds im CSV."""
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_csv.exists():  # nur ok-Zeilen gelten als erledigt; Fail-Zeilen werden neu kodiert
        done = {int(r["seed"]) for r in csv.DictReader(open(out_csv, encoding="utf-8"))
                if r.get("status") == "ok"}
    new_file = not out_csv.exists()
    fh = open(out_csv, "a", newline="", encoding="utf-8")
    wr = csv.DictWriter(fh, fieldnames=COLS)
    if new_file:
        wr.writeheader()
    n_ok = n_fail = 0
    for seed in sorted(seed_to_png):
        if seed in done:
            continue
        png = seed_to_png[seed]
        row = {"seed": seed, "status": "fail", "attempts": 0, "dur_s": 0}
        for attempt in (1, 2, 3):
            t0 = time.time()
            try:
                raw = ollama_code_image(model, png)
                parsed = _parse_vlm(raw)
                row.update(parsed)
                row.update({"status": "ok", "attempts": attempt,
                            "dur_s": round(time.time() - t0, 1)})
                break
            except Exception as e:
                row["attempts"] = attempt
                row["dur_s"] = round(time.time() - t0, 1)
                print(f"[RETRY {attempt}] {model} s{seed}: {type(e).__name__}: {str(e)[:120]}",
                      flush=True)
        for c in COLS:
            row.setdefault(c, "")
        wr.writerow(row)
        fh.flush()
        if row["status"] == "ok":
            n_ok += 1
            print(f"[OK {n_ok}] {model} s{seed} {row['primary']}/{row['malweise']} "
                  f"{row['dur_s']}s", flush=True)
        else:
            n_fail += 1
    fh.close()
    print(f"[DONE] {model}: ok={n_ok} fail={n_fail} skip={len(done)}", flush=True)


def f2_images():
    return {s: OUT_F / "img" / f"F2_legacy_empty_a0_c1_s{s}.png" for s in range(1, 121)}


def g2_images():
    return {s: IMG_G / f"G2_legacy_empty_a0_c1_s{s}.png" for s in range(1, 121)}


# ---------------------------------------------------------------- Statistik

def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def kappa(a, b, cats):
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca.get(k, 0) / n) * (cb.get(k, 0) / n) for k in cats)
    if pe >= 1.0:
        return 1.0, po
    return (po - pe) / (1 - pe), po


def read_coding(path):
    rows = {int(r["seed"]): r for r in csv.DictReader(open(path, encoding="utf-8"))
            if r.get("status", "ok") in ("", "ok")}
    return rows


def confusion_md(a_rows, b_rows, seeds, la, lb):
    lines = [f"| {la}\\\\{lb} | " + " | ".join(PRIM) + " |",
             "|---|" + "---|" * len(PRIM)]
    for ka in PRIM:
        cells = []
        for kb in PRIM:
            c = sum(1 for s in seeds
                    if a_rows[s]["primary"] == ka and b_rows[s]["primary"] == kb)
            cells.append(str(c) if c else "·")
        lines.append(f"| **{ka}** | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cmd_agreement():
    """Primär-Kodierer = 4b (Design G1); 32b-Zeilen nur, falls dessen CSV existiert."""
    human = read_coding(HUMAN_CSV)
    v4 = read_coding(DATA_G / "vlm_large_4b.csv")
    p32 = DATA_G / "vlm_large_32b.csv"
    v32 = read_coding(p32) if p32.exists() else None
    out = ["# G1 — Übereinstimmung Mensch ↔ VLM (F2-Prior-Bilder, n=120)\n"]
    pairs = [("Mensch", human, "4b", v4)]
    if v32:
        pairs += [("Mensch", human, "32b", v32), ("4b", v4, "32b", v32)]
    out.append("\n## Primärkategorie (K1–K6)\n")
    out.append("| Paar | n | Übereinstimmung | Cohens κ |\n|---|---|---|---|")
    kappa_main = None
    for la, ra, lb, rb in pairs:
        seeds = sorted(set(ra) & set(rb))
        a = [ra[s]["primary"] for s in seeds]
        b = [rb[s]["primary"] for s in seeds]
        k, po = kappa(a, b, PRIM)
        if (la, lb) == ("Mensch", "4b"):
            kappa_main = k
        out.append(f"| {la} ↔ {lb} | {len(seeds)} | {po*100:.1f}% | {k:.3f} |")
    if not v32:
        out.append("\n(32b-Zweit-Pass ausstehend — bedingt auf VRAM-Freigabe, s. Design.)")
    seeds = sorted(set(human) & set(v4))
    out.append("\n### Konfusionsmatrix Mensch (Zeilen) × 4b (Spalten)\n")
    out.append(confusion_md(human, v4, seeds, "Mensch", "4b"))
    out.append("\n### Diskrepanz-Liste Mensch ↔ 4b (für Sichtungs-Anhang)\n")
    for s in seeds:
        if human[s]["primary"] != v4[s]["primary"]:
            out.append(f"- s{s}: Mensch {human[s]['primary']} · 4b {v4[s]['primary']}"
                       f" · Notiz Mensch: {human[s].get('notiz','')}")
    out.append("\n## Sekundär-Tags (Mensch ↔ 4b)\n")
    a = [human[s]["malweise"] for s in seeds]
    b = [v4[s]["malweise"] for s in seeds]
    k, po = kappa(a, b, MALW)
    out.append(f"- **Malweise:** Übereinstimmung {po*100:.1f}%, κ {k:.3f}")
    for col in ("diorama", "schrift"):
        agree = sum(1 for s in seeds if (human[s][col] or "") == (v4[s][col] or ""))
        hpos = sum(1 for s in seeds if human[s][col])
        vpos = sum(1 for s in seeds if v4[s][col])
        out.append(f"- **{col}:** Rohübereinstimmung {agree}/{len(seeds)} "
                   f"(Positive: Mensch {hpos}, 4b {vpos})")
    a = [human[s]["westlich"] for s in seeds]
    b = [v4[s]["westlich"] for s in seeds]
    k, po = kappa(a, b, WEST)
    out.append(f"- **westlich:** Übereinstimmung {po*100:.1f}%, κ {k:.3f} "
               f"(Verteilung Mensch {dict(Counter(a))} · 4b {dict(Counter(b))})")
    both_k1 = [s for s in seeds
               if human[s]["primary"] == "K1" and v4[s]["primary"] == "K1"]
    out.append(f"\n## K1-Demografie auf Schnittmenge beide=K1 (n={len(both_k1)})\n")
    for col in ("geschlecht", "alter", "hautton"):
        agree = sum(1 for s in both_k1 if human[s][col] == v4[s][col])
        out.append(f"- **{col}:** Übereinstimmung {agree}/{len(both_k1)} · "
                   f"Mensch {dict(Counter(human[s][col] for s in both_k1))} · "
                   f"4b {dict(Counter(v4[s][col] for s in both_k1))}")
    out.append("\n## G1-Regel (prä-registriert, κ Mensch↔4b)\n")
    if kappa_main >= 0.61:
        verdict = "VALIDIERT (κ ≥ 0.61) → G2 läuft VLM-kodiert mit Hand-Stichprobe n=20"
    elif kappa_main >= 0.41:
        verdict = "ADJUDIKATION (0.41 ≤ κ < 0.61) → G2 läuft mit vollständiger Hand-Sichtung"
    else:
        verdict = "NICHT VALIDIERT (κ < 0.41) → G2 verschoben"
    out.append(f"κ(Mensch↔4b, primär) = {kappa_main:.3f} → **{verdict}**")
    (DATA_G / "agreement_stats.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[-3:]))
    print(f"\nwrote {DATA_G/'agreement_stats.md'}")


# ---------------------------------------------------------------- G2: Generierung

def metrics(img):
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
    gray = arr.mean(axis=-1)
    lap = (4 * gray - np.roll(gray, 1, 0) - np.roll(gray, -1, 0)
           - np.roll(gray, 1, 1) - np.roll(gray, -1, 1))
    return {"red_excess": round(float((r - (g + b) / 2.0).mean()), 5),
            "sat": round(float(hsv[..., 1].mean()), 5),
            "lum": round(float(gray.mean()), 5),
            "lap_var": round(float(lap.var()), 7),
            "std_lum": round(float(gray.std()), 5)}


def service_ready(timeout_s=300):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if requests.get(AVAIL, timeout=5).ok:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def heal_service():
    state = subprocess.run(["systemctl", "is-active", "ai4artsed-gpu.service"],
                           capture_output=True, text=True).stdout.strip()
    print(f"[HEAL] service state: {state}", flush=True)
    if state != "active":
        subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "restart",
                        "ai4artsed-gpu.service"])
    return service_ready()


def cmd_gen_medium():
    IMG_G.mkdir(parents=True, exist_ok=True)
    for m in (M32, M4):  # GPU-Serialisierung: Ollama vor Generierung entladen
        subprocess.run(["ollama", "stop", m], capture_output=True)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    with open(MANIFEST_G, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "header", "phase": "gen-medium", "git": head,
                             "model_id": MODEL_MEDIUM, "steps": STEPS,
                             "started": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
    n_ok = n_skip = n_fail = consec = 0
    for i, seed in enumerate(range(1, 121)):
        cid = f"G2_legacy_empty_a0_c1_s{seed}"
        png = IMG_G / f"{cid}.png"
        if png.exists():
            n_skip += 1
            continue
        payload = {"prompt": "", "alpha_factor": 0.0, "model_id": MODEL_MEDIUM,
                   "negative_prompt": "", "width": W, "height": H, "steps": STEPS,
                   "cfg_scale": 1.0, "seed": seed, "fusion_strategy": "legacy"}
        rec = {"type": "cell", "id": cid, "exp": "G2", "seed": seed}
        ok = False
        err = ""
        for attempt in (1, 2, 3):
            t0 = time.time()
            try:
                resp = requests.post(BASE, json=payload, timeout=900)
                dur = round(time.time() - t0, 1)
                if resp.ok and resp.json().get("success"):
                    raw = base64.b64decode(resp.json()["image_base64"])
                    img = Image.open(io.BytesIO(raw))
                    img.save(png)
                    rec.update({"status": "ok", "dur_s": dur, "attempt": attempt,
                                "png_sha8": hashlib.sha256(raw).hexdigest()[:8]})
                    rec.update(metrics(img))
                    ok = True
                    break
                err = f"http {resp.status_code}: {resp.text[:200]}"
            except Exception as e:
                dur = round(time.time() - t0, 1)
                err = f"{type(e).__name__}: {e}"
            print(f"[RETRY {attempt}] {cid} after {dur}s: {err}", flush=True)
            if not heal_service():
                print("[FATAL] service unrecoverable", flush=True)
                break
        if ok:
            consec = 0
            n_ok += 1
            print(f"[OK {i+1}/120] {cid} {rec['dur_s']}s sat={rec['sat']}", flush=True)
        else:
            consec += 1
            n_fail += 1
            rec.update({"status": "fail", "error": err})
        with open(MANIFEST_G, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if consec >= 12:
            print("[ABORT] 12 consecutive failures", flush=True)
            sys.exit(2)
        time.sleep(1)
    print(f"[GEN DONE] ok={n_ok} skip={n_skip} fail={n_fail}", flush=True)


# ---------------------------------------------------------------- G2: Auswertung

def cmd_tafeln_medium():
    IMG_REPO_G.mkdir(parents=True, exist_ok=True)
    seeds = sorted(g2_images())
    thumbs = 480
    per = 12
    for t in range(10):
        batch = seeds[t * per:(t + 1) * per]
        cols, rows_ = 4, 3
        tafel = Image.new("RGB", (cols * thumbs, rows_ * thumbs + 28), "#111")
        d = ImageDraw.Draw(tafel)
        d.text((8, 6), f"G2 Prior-Zensus SD3.5-Medium — Tafel {t+1}/10 "
                       f"(Seeds {batch[0]}–{batch[-1]}) · leerer Prompt · CFG 1.0",
               fill="#ddd")
        for j, s in enumerate(batch):
            p = g2_images()[s]
            if not p.exists():
                continue
            im = Image.open(p).convert("RGB").resize((thumbs, thumbs), Image.LANCZOS)
            dd = ImageDraw.Draw(im)
            dd.rectangle([0, 0, 54, 20], fill="#000")
            dd.text((4, 4), f"s{s}", fill="#fff")
            tafel.paste(im, ((j % cols) * thumbs, 28 + (j // cols) * thumbs))
        out = IMG_REPO_G / f"T9_G2_prior_{t+1:02d}.jpg"
        tafel.save(out, quality=85)
        print(f"wrote {out}")


def _rates_table(rows_by_label):
    lines = ["| Kategorie | " + " | ".join(rows_by_label) + " |",
             "|---|" + "---|" * len(rows_by_label)]
    labels = {"K1": "K1 Figur/Gesicht", "K2": "K2 Objekt-Präsentation",
              "K3": "K3 Text/Typografie", "K4": "K4 Landschaft/Architektur",
              "K5": "K5 Tier", "K6": "K6 abstrakt/Muster"}
    for k in PRIM:
        cells = []
        for lab, rows in rows_by_label.items():
            n = len(rows)
            c = sum(1 for r in rows.values() if r["primary"] == k)
            lo, hi = wilson(c, n)
            cells.append(f"{c} ({c/n*100:.1f}% [{lo*100:.1f}–{hi*100:.1f}])")
        lines.append(f"| {labels[k]} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cmd_stats_medium():
    human = read_coding(HUMAN_CSV)
    vmed = read_coding(DATA_G / "census_medium_vlm.csv")
    cols = {"Large/Mensch": human,
            "Large/VLM-4b": read_coding(DATA_G / "vlm_large_4b.csv"),
            "Medium/VLM-4b": vmed}
    p32 = DATA_G / "vlm_large_32b.csv"
    if p32.exists():
        cols["Large/VLM-32b"] = read_coding(p32)
    out = [f"# G2 — Prior-Zensus SD3.5-Medium (n={len(vmed)}) vs. Large (F2)\n"]
    out.append("\n## Primärkategorien — Raten mit Wilson-95%\n")
    out.append(_rates_table(cols))
    mo_h = Counter(r["primary"] for r in human.values()).most_common(1)[0][0]
    mo_m = Counter(r["primary"] for r in vmed.values()).most_common(1)[0][0]
    out.append(f"\n- **G2-H1 (Modalstruktur):** Modalkategorie Large/Mensch = {mo_h}, "
               f"Medium/VLM = {mo_m} → {'gleich' if mo_h == mo_m else 'ungleich'}")
    mal = Counter(r["malweise"] for r in vmed.values())
    out.append(f"- **Malweise Medium:** " + " · ".join(f"{k}={v}" for k, v in mal.most_common()))
    west = Counter(r["westlich"] for r in vmed.values())
    out.append(f"- **westlich Medium (VLM):** " + " · ".join(f"{k}={v}" for k, v in west.most_common()))
    k1 = [r for r in vmed.values() if r["primary"] == "K1"]
    for col in ("geschlecht", "alter", "hautton"):
        cnt = Counter(r[col] for r in k1 if r[col])
        out.append(f"- **K1-{col} Medium (VLM, n={len(k1)}):** "
                   + " · ".join(f"{k}={v}" for k, v in cnt.most_common()))
    # Basisstatistik aus Manifest
    sats, lums, reds = [], [], []
    if MANIFEST_G.exists():
        for line in open(MANIFEST_G, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("type") == "cell" and rec.get("status") == "ok":
                sats.append(rec["sat"])
                lums.append(rec["lum"])
                reds.append(rec["red_excess"])
    if sats:
        ms = sum(sats) / len(sats)
        out.append(f"\n## Basisstatistik Medium (n={len(sats)})\n")
        out.append(f"- sat: Mittel {ms:.3f} · Median {sorted(sats)[len(sats)//2]:.3f} "
                   f"· min {min(sats):.3f} · max {max(sats):.3f}")
        out.append(f"- lum: Mittel {sum(lums)/len(lums):.3f} · red_excess: Mittel "
                   f"{sum(reds)/len(reds):.3f}")
        out.append(f"- entsättigt (sat<0.25): {sum(1 for s in sats if s < 0.25)}/{len(sats)}")
        out.append(f"- **G2-H2 (Entsättigungs-Signatur, |Δsat|≤0.05 zu Large 0.217):** "
                   f"Δ = {ms-0.217:+.3f} → {'geteilt' if abs(ms-0.217) <= 0.05 else 'verschieden'}")
    # Akkumulation + GT/Chao1 (primary×malweise, Seed-Reihenfolge)
    seeds = sorted(vmed)
    combo = lambda s: f"{vmed[s]['primary']}|{vmed[s]['malweise']}"
    seen, curve = set(), []
    for s in seeds:
        seen.add(combo(s))
        curve.append(len(seen))
    n = len(seeds)
    marks = [m for m in (1, 5, 10, 20, 30, 40, 60, 80, 100, n) if m <= n]
    out.append("\n## Moden-Akkumulation (primär×malweise, Medium/VLM)\n")
    out.append("| n | " + " | ".join(str(m) for m in marks) + " |")
    out.append("|---|" + "---|" * len(marks))
    out.append("| Kombinationen | " + " | ".join(str(curve[m - 1]) for m in marks) + " |")
    cnt = Counter(combo(s) for s in seeds)
    f1 = sum(1 for v in cnt.values() if v == 1)
    f2 = sum(1 for v in cnt.values() if v == 2)
    chao1 = len(cnt) + (f1 * f1 / (2 * f2) if f2 else f1 * (f1 - 1) / 2)
    out.append(f"\n- S_obs={len(cnt)} (f1={f1}, f2={f2}) · Good-Turing f1/n={f1/n:.3f} "
               f"· Chao1 Ŝ={chao1:.1f}")
    DATA_G.mkdir(parents=True, exist_ok=True)
    (DATA_G / "census_medium_stats.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {DATA_G/'census_medium_stats.md'}")
    # Spotcheck-Skelett
    sk = DATA_G / "spotcheck_skeleton.csv"
    if not sk.exists():
        with open(sk, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["seed", "primary", "malweise", "diorama", "schrift",
                         "westlich", "geschlecht", "alter", "hautton", "notiz"])
            for s in SPOT_SEEDS:
                wr.writerow([s] + [""] * 9)
        print(f"wrote {sk} (Hand-Stichprobe Seeds ≡ 1 mod 6, n={len(SPOT_SEEDS)})")


def cmd_spotcheck(path):
    hand = {int(r["seed"]): r for r in csv.DictReader(open(path, encoding="utf-8"))
            if r.get("primary")}
    vmed = read_coding(DATA_G / "census_medium_vlm.csv")
    seeds = sorted(set(hand) & set(vmed))
    a = [hand[s]["primary"] for s in seeds]
    b = [vmed[s]["primary"] for s in seeds]
    k, po = kappa(a, b, PRIM)
    lines = [f"\n## Hand-Stichprobe Medium (Seeds ≡ 1 mod 6, n={len(seeds)})\n",
             f"- Primär: Übereinstimmung {po*100:.1f}%, κ {k:.3f}"]
    for s in seeds:
        if hand[s]["primary"] != vmed[s]["primary"]:
            lines.append(f"- s{s}: Hand {hand[s]['primary']} · VLM {vmed[s]['primary']}"
                         f" · Notiz: {hand[s].get('notiz','')}")
    with open(DATA_G / "census_medium_stats.md", "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------------------------------------------------------------- main

def cmd_arbiter(tag):
    """Dritt-Kodierer als Schiedsstimme (exploratorisch, ohne Regel-Status):
    K1-Demografie auf der Schnittmenge Mensch=K1 ∧ 4b=K1."""
    human = read_coding(HUMAN_CSV)
    v4 = read_coding(DATA_G / "vlm_large_4b.csv")
    v3 = read_coding(DATA_G / f"vlm_large_{tag}.csv")
    seeds = [s for s in sorted(set(human) & set(v4) & set(v3))
             if human[s]["primary"] == "K1" and v4[s]["primary"] == "K1"]
    out = [f"\n## Dritt-Kodierer {tag} (exploratorisch, ohne Regel-Status): "
           f"K1-Demografie-Schiedsstimme (n={len(seeds)})\n"]
    out.append(f"Primär {tag} auf diesen Bildern: "
               + " · ".join(f"{k}={v}" for k, v in
                            Counter(v3[s]["primary"] for s in seeds).most_common()))
    for col in ("geschlecht", "alter", "hautton"):
        cnt = Counter(v3[s][col] for s in seeds)
        agree_h = sum(1 for s in seeds if v3[s][col] == human[s][col])
        agree_4 = sum(1 for s in seeds if v3[s][col] == v4[s][col])
        out.append(f"\n### {col} — {tag}-Verteilung: "
                   + " · ".join(f"{k or 'leer'}={v}" for k, v in cnt.most_common()))
        out.append(f"{tag} stimmt mit Mensch {agree_h}/{len(seeds)} · mit 4b {agree_4}/{len(seeds)}; "
                   f"strittige Zeilen (Mensch≠4b):")
        out.append("| seed | Mensch | 4b | " + tag + " |")
        out.append("|---|---|---|---|")
        for s in seeds:
            if human[s][col] != v4[s][col]:
                out.append(f"| s{s} | {human[s][col]} | {v4[s][col]} | {v3[s][col]} |")
    with open(DATA_G / "agreement_stats.md", "a", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("\n".join(out[:4]))
    print(f"appended to {DATA_G/'agreement_stats.md'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["vlm-large", "agreement", "gen-medium",
                                      "vlm-medium", "tafeln-medium", "stats-medium",
                                      "spotcheck", "arbiter"])
    ap.add_argument("--model", default=M4)
    ap.add_argument("--csv", default=str(DATA_G / "spotcheck_medium.csv"))
    ap.add_argument("--seeds", default="", help="Komma-Liste; leer = alle 120")
    ap.add_argument("--tag", default="90b", help="CSV-Tag des Dritt-Kodierers (arbiter)")
    args = ap.parse_args()
    if args.phase == "vlm-large":
        tag = re.sub(r"[^a-z0-9.]+", "", args.model.split(":")[-1].lower()) or "x"
        imgs = f2_images()
        if args.seeds:
            keep = {int(x) for x in args.seeds.split(",")}
            imgs = {s: p for s, p in imgs.items() if s in keep}
        vlm_pass(args.model, OUT_F / "img", imgs, DATA_G / f"vlm_large_{tag}.csv")
    elif args.phase == "agreement":
        cmd_agreement()
    elif args.phase == "gen-medium":
        cmd_gen_medium()
    elif args.phase == "vlm-medium":
        vlm_pass(args.model, IMG_G, g2_images(), DATA_G / "census_medium_vlm.csv")
    elif args.phase == "tafeln-medium":
        cmd_tafeln_medium()
    elif args.phase == "stats-medium":
        cmd_stats_medium()
    elif args.phase == "spotcheck":
        cmd_spotcheck(args.csv)
    elif args.phase == "arbiter":
        cmd_arbiter(args.tag)


if __name__ == "__main__":
    main()
