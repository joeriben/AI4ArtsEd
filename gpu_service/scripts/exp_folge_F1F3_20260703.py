#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folge-Reihe F1–F3 (2026-07-03) — Guidance-Ästhetik · Prior-Zensus · Bündel-Zerlegung.

Prä-registriertes Design: docs/analysis/embedding_subtraction/DESIGN_folgereihe_F1-F3_2026-07-03.md
  F1  Guidance-Feinraster + Negativ-Sonde ("Rot loswerden") + dynamische Bestpunkt-Replikation
  F2  Prior-Zensus n=120 (leerer Prompt, CFG 1.0, Seeds 1–120)
  F3  Zerlegung des legacy-Push: push_t5only / push_negclip (norm-gematcht, E1-Methodik)

Läuft AUF dem Fedora-Dev-Rechner gegen den lokalen GPU-Service (17803), sequentiell.
Outputs: ~/ai/deconstruct_suite_F/img/ + manifest.jsonl. Konstanten identisch Nacht-Reihe;
Prompts wörtlich aus der abgestimmten Batterie — keine neu erfundenen Operanden
(Negativ-Sonde: Operand aus dem Messbefund abgeleitet, s. Design F1).
"""
import hashlib
import json
import subprocess
import sys
import time
import base64
import io
from pathlib import Path

import numpy as np
import requests
from PIL import Image

BASE = "http://127.0.0.1:17803/api/diffusers/generate/fusion"
AVAIL = "http://127.0.0.1:17803/api/diffusers/available"
OUT = Path.home() / "ai" / "deconstruct_suite_F"
IMG = OUT / "img"
MANIFEST = OUT / "manifest.jsonl"
REPO = Path.home() / "ai" / "ai4artsed_development"

MODEL = "stabilityai/stable-diffusion-3.5-large"
STEPS = 25
W = H = 1024
CFG_STD = 5.5
NEG_PROBE = "red, oversaturated colors"

PROMPTS = {
    "p0ext": ("Ein zweistöckiges Bauernhaus mit rotem Ziegeldach steht am Rand einer weiten "
              "Landschaft. Ringsum erstrecken sich gepflügte Äcker, reife Weizenfelder und grüne "
              "Wiesen, durchzogen von Feldwegen und Hecken. Auf den Weiden grasen Kühe, Schafe "
              "und Pferde; über den Feldern kreisen Vögel. Mehrere Menschen sind verstreut zu "
              "sehen: einige arbeiten auf dem Hof, andere gehen über die Felder oder stehen am "
              "Wegrand."),
    "p1": ("Menschen drängen sich auf einem Bahnsteig, umgeben von Betonpfeilern, "
           "Anzeigetafeln und einfahrenden Zügen."),
    "p2": ("Ein umgestürzter Baum liegt in einem Sumpf, umgeben von Schilf, Nebel und "
           "stehendem Wasser."),
    "p3": ("Ein Leuchtturm steht auf einer Klippe über dem Meer, umgeben von Brandung, "
           "Möwen und Abendrot."),
    "empty": "",
}


def fnum(x):
    x = float(x)
    if x == int(x):
        return str(int(x)).replace("-", "m")
    return str(x).replace(".", "p").replace("-", "m")


def make_cell(exp, strat_base, pk, alpha, cfg=CFG_STD, seed=42, neg=""):
    cid = f"{exp}_{strat_base}_{pk}_a{fnum(alpha)}_c{fnum(cfg)}_s{seed}"
    if neg:
        cid += "_neg1"
    return {
        "id": cid, "exp": exp, "strategy": strat_base, "strategy_base": strat_base,
        "prompt_key": pk, "alpha": float(alpha), "cfg": float(cfg), "seed": int(seed),
        "neg": neg,
    }


def build_cells():
    cells, seen = [], set()

    def add(*a, **kw):
        c = make_cell(*a, **kw)
        if c["id"] not in seen:
            seen.add(c["id"])
            cells.append(c)

    # ---------------- F1: Guidance-Feinraster (CFG 1.0/3.0/5.5 existieren in E1/E2) ----------------
    for cfg in (1.5, 2.0, 2.5, 4.0):
        for pk in ("p0ext", "p2"):
            for a in (0, 15, 35, 75):
                add("F1", "legacy", pk, a, cfg=cfg)
    for pk in ("p0ext", "p2"):                       # dual_alpha-Prüfpunkt
        add("F1", "dual_alpha", pk, 35, cfg=2.5)
    for pk in ("p0ext", "p2"):                       # Negativ-Sonde bei voller Guidance
        for a in (15, 35):
            add("F1", "legacy", pk, a, cfg=5.5, neg=NEG_PROBE)

    # ---------------- F2: Prior-Zensus ----------------
    for seed in range(1, 121):
        add("F2", "legacy", "empty", 0, cfg=1.0, seed=seed)

    # ---------------- F3: Bündel-Zerlegung ----------------
    for strat in ("push_t5only", "push_negclip"):
        for pk in ("p0ext", "p2"):
            for a in (5, 15, 35, 75):
                add("F3", strat, pk, a)
            add("F3", strat, pk, 35, seed=7)
        for pk in ("p1", "p3"):
            add("F3", strat, pk, 35)

    return cells


def best_cfg_cells():
    """Deterministische Regel (Design F1): CFG* = größtes CFG in {1.5,2.0,2.5,4.0} mit
    mittlerem red_excess(α35, legacy, p0ext+p2, ohne neg) < 0.10 → p1/p3-Replikation."""
    rows = {}
    for line in open(MANIFEST, encoding="utf-8"):
        rec = json.loads(line)
        if (rec.get("type") == "cell" and rec.get("status") == "ok" and rec.get("exp") == "F1"
                and rec.get("strategy_base") == "legacy" and rec.get("alpha") == 35.0
                and not rec.get("neg") and rec.get("prompt_key") in ("p0ext", "p2")):
            rows.setdefault(rec["cfg"], []).append(rec["red_excess"])
    star = None
    for cfg in (4.0, 2.5, 2.0, 1.5):
        xs = rows.get(cfg, [])
        if xs and sum(xs) / len(xs) < 0.10:
            star = cfg
            break
    if star is None:
        print("[F1*] kein CFG unter Schwelle 0.10 — Replikation entfällt", flush=True)
        return []
    print(f"[F1*] CFG* = {star}", flush=True)
    return [make_cell("F1", "legacy", pk, 35, cfg=star) for pk in ("p1", "p3")]


def metrics(img):
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    red_excess = float((r - (g + b) / 2.0).mean())
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
    gray = arr.mean(axis=-1)
    lap = (4 * gray
           - np.roll(gray, 1, 0) - np.roll(gray, -1, 0)
           - np.roll(gray, 1, 1) - np.roll(gray, -1, 1))
    return {
        "mean_r": round(float(r.mean()), 5),
        "mean_g": round(float(g.mean()), 5),
        "mean_b": round(float(b.mean()), 5),
        "red_excess": round(red_excess, 5),
        "sat": round(float(hsv[..., 1].mean()), 5),
        "lum": round(float(gray.mean()), 5),
        "lap_var": round(float(lap.var()), 7),
        "std_lum": round(float(gray.std()), 5),
    }


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
        subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "restart", "ai4artsed-gpu.service"])
    return service_ready()


def run_cells(cells, n_total, offset=0):
    n_ok = n_skip = n_fail = consec_fail = 0
    for i, c in enumerate(cells):
        png = IMG / f"{c['id']}.png"
        if png.exists():
            n_skip += 1
            print(f"[SKIP] {c['id']}", flush=True)
            continue
        payload = {
            "prompt": PROMPTS[c["prompt_key"]],
            "alpha_factor": c["alpha"],
            "model_id": MODEL,
            "negative_prompt": c.get("neg", ""),
            "width": W, "height": H, "steps": STEPS,
            "cfg_scale": c["cfg"], "seed": c["seed"],
            "fusion_strategy": c["strategy"],
        }
        rec = dict(c)
        rec["type"] = "cell"
        ok = False
        rec_err = ""
        for attempt in (1, 2, 3):
            t0 = time.time()
            try:
                resp = requests.post(BASE, json=payload, timeout=600)
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
                rec_err = f"http {resp.status_code}: {resp.text[:200]}"
            except Exception as e:
                dur = round(time.time() - t0, 1)
                rec_err = f"{type(e).__name__}: {e}"
            print(f"[RETRY {attempt}] {c['id']} after {dur}s: {rec_err}", flush=True)
            if not heal_service():
                print("[FATAL] service unrecoverable", flush=True)
                rec.update({"status": "fail", "error": rec_err})
                break
        if ok:
            consec_fail = 0
            n_ok += 1
            print(f"[OK {offset+i+1}/{n_total}] {c['id']} {rec['dur_s']}s red_excess={rec['red_excess']}", flush=True)
        else:
            consec_fail += 1
            n_fail += 1
            rec.setdefault("status", "fail")
            rec.setdefault("error", rec_err)
        with open(MANIFEST, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if consec_fail >= 12:
            print("[ABORT] 12 consecutive failures", flush=True)
            sys.exit(2)
        time.sleep(1)
    return n_ok, n_skip, n_fail


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    cells = build_cells()
    hdr = {"type": "header", "started": time.strftime("%Y-%m-%d %H:%M:%S"),
           "git_head": head, "model": MODEL, "steps": STEPS, "size": [W, H],
           "neg_probe": NEG_PROBE, "n_cells_static": len(cells),
           "prompt_sha8": {k: hashlib.sha256(v.encode()).hexdigest()[:8] for k, v in PROMPTS.items()}}
    with open(MANIFEST, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(hdr, ensure_ascii=False) + "\n")
    print(f"[START] {len(cells)} statische Zellen + dynamische F1*-Replikation, HEAD={head}", flush=True)

    if not service_ready():
        print("[FATAL] service not ready at start", flush=True)
        sys.exit(1)

    n_ok, n_skip, n_fail = run_cells(cells, len(cells) + 2)
    extra = best_cfg_cells()
    if extra:
        ok2, skip2, fail2 = run_cells(extra, len(cells) + len(extra), offset=len(cells))
        n_ok += ok2
        n_skip += skip2
        n_fail += fail2

    summary = {"type": "summary", "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
               "ok": n_ok, "skip": n_skip, "fail": n_fail}
    with open(MANIFEST, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    print(f"[DONE] ok={n_ok} skip={n_skip} fail={n_fail}", flush=True)


if __name__ == "__main__":
    main()
