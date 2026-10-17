#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nacht-Reihe E1–E4 (2026-07-03) — Dekonstruktive Eingriffspunkte: Art, Natur, Grenzen.

Prä-registriertes Design: docs/analysis/embedding_subtraction/DESIGN_nachtreihe_E1-E4_2026-07-03.md
  E1  Zufallskontrolle   — Richtungs-Spezifität des legacy-Push (norm-matched random / shuffled)
  E2  CFG-Ablation       — Konditionierungszustand vs. Guidance-Verstärker
  E3  Prior-Vergleich    — unkonditioniertes Vokabular des Modells (empty prompt)
  E4  Stufen-Lokalisierung — wann im Denoising entsteht das Vokabular (Frames + Latent-Statistik)

Läuft AUF dem Fedora-Dev-Rechner gegen den lokalen GPU-Service (17803), sequentiell.
Outputs: ~/ai/deconstruct_suite/{img,caps}/ + manifest.jsonl (außerhalb des Repos;
Tafeln + Bericht folgen in docs/analysis/embedding_subtraction/).

Konstanten identisch zur Forcing-Batterie (BERICHT_forcing_hebel_2026-07-02.md):
SD3.5-large, 1024², 25 Steps, CFG 5.5 (außer E2-Variation), Negativ leer, Seeds 42/7,
Prompts wörtlich aus der Batterie (§2.5) — keine neu erfundenen Operanden.
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
OUT = Path.home() / "ai" / "deconstruct_suite"
IMG = OUT / "img"
CAPS = OUT / "caps"
MANIFEST = OUT / "manifest.jsonl"
REPO = Path.home() / "ai" / "ai4artsed_development"

MODEL = "stabilityai/stable-diffusion-3.5-large"
STEPS = 25
W = H = 1024
NEG = ""
CFG_STD = 5.5
CAP_STEPS = "3,6,10,15,20,25"

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


def build_cells():
    cells = []
    seen = set()

    def add(exp, strat_base, pk, alpha, cfg=CFG_STD, seed=42, rng=None, band=None, cap=False):
        cid = f"{exp}_{strat_base}_{pk}_a{fnum(alpha)}_c{fnum(cfg)}_s{seed}"
        strat = strat_base
        if rng is not None:
            cid += f"_r{rng}"
            strat += f"#rng={rng}"
        if band:
            cid += f"_b{band}"
            strat += f"#band={band}"
        if cap:
            capdir = str(CAPS / cid)
            strat += f"#cap={CAP_STEPS}#capdir={capdir}"
        if cid in seen:
            return
        seen.add(cid)
        cells.append({
            "id": cid, "exp": exp, "strategy": strat, "strategy_base": strat_base,
            "prompt_key": pk, "alpha": float(alpha), "cfg": float(cfg), "seed": int(seed),
            "rng": rng, "band": band, "cap": bool(cap),
        })

    # ---------------- E1: Zufallskontrolle (Richtungs-Spezifität) ----------------
    for pk in ("p0ext", "p2"):
        for seed in (42, 7):
            for a in (0, 5, 15, 35, 75):
                add("E1", "legacy", pk, a, seed=seed)
            for rng in (1, 2):
                for a in (5, 15, 35, 75):
                    add("E1", "random_matched", pk, a, seed=seed, rng=rng)
            for a in (15, 35):
                add("E1", "random_shuffled", pk, a, seed=seed, rng=1)
    for a in (15, 35):  # Subraum-Variante: Zufall nur im CLIP-Band
        add("E1", "random_matched", "p0ext", a, seed=42, rng=1, band="clip")
    for pk in ("p1", "p3"):  # Replikation der Kopf-Zelle auf den zwei übrigen Batterie-Prompts
        add("E1", "legacy", pk, 35, seed=42)
        add("E1", "random_matched", pk, 35, seed=42, rng=1)

    # ---------------- E2: CFG-Ablation (Zustand vs. Verstärker) ----------------
    for pk in ("p0ext", "p2"):
        for strat in ("legacy", "dual_alpha"):
            for cfg in (1.0, 3.0, 5.5):
                if strat == "legacy" and cfg == 5.5:
                    continue  # identische Zellen laufen in E1 (gleiche Parameter, Referenz dort)
                for a in (0, 15, 35, 75):
                    add("E2", strat, pk, a, cfg=cfg, seed=42)
        add("E2", "random_matched", pk, 35, cfg=1.0, seed=42, rng=1)

    # ---------------- E3: Prior-Vergleich (unkonditioniertes Vokabular) ----------------
    for seed in (42, 7, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110):
        add("E3", "legacy", "empty", 0, cfg=1.0, seed=seed)
    for seed in (42, 7, 101, 102, 103, 104, 105, 106):
        add("E3", "legacy", "empty", 0, cfg=5.5, seed=seed)

    # ---------------- E4: Stufen-Lokalisierung (Frames + Latent-Statistik) ----------------
    for pk in ("p0ext", "p2"):
        for a in (0, 35, 75):
            add("E4", "legacy", pk, a, seed=42, cap=True)
    add("E4", "dual_alpha", "p0ext", 35, seed=42, cap=True)
    add("E4", "random_matched", "p0ext", 35, seed=42, rng=1, cap=True)
    add("E4", "legacy", "empty", 0, cfg=1.0, seed=42, cap=True)  # Prior-Trajektorie als Referenz

    return cells


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


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    CAPS.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    cells = build_cells()
    hdr = {"type": "header", "started": time.strftime("%Y-%m-%d %H:%M:%S"),
           "git_head": head, "model": MODEL, "steps": STEPS, "size": [W, H],
           "negative": NEG, "n_cells": len(cells),
           "prompt_sha8": {k: hashlib.sha256(v.encode()).hexdigest()[:8] for k, v in PROMPTS.items()}}
    with open(MANIFEST, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(hdr, ensure_ascii=False) + "\n")
    print(f"[START] {len(cells)} cells, HEAD={head}", flush=True)

    if not service_ready():
        print("[FATAL] service not ready at start", flush=True)
        sys.exit(1)

    consec_fail = 0
    n_ok = n_skip = n_fail = 0
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
            "negative_prompt": NEG,
            "width": W, "height": H, "steps": STEPS,
            "cfg_scale": c["cfg"], "seed": c["seed"],
            "fusion_strategy": c["strategy"],
        }
        rec = dict(c)
        rec["type"] = "cell"
        ok = False
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
            print(f"[OK {i+1}/{len(cells)}] {c['id']} {rec['dur_s']}s red_excess={rec['red_excess']}", flush=True)
        else:
            consec_fail += 1
            n_fail += 1
            rec.setdefault("status", "fail")
            rec.setdefault("error", rec_err)
        with open(MANIFEST, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if consec_fail >= 12:
            print("[ABORT] 12 consecutive failures", flush=True)
            break
        time.sleep(1)

    summary = {"type": "summary", "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
               "ok": n_ok, "skip": n_skip, "fail": n_fail}
    with open(MANIFEST, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    print(f"[DONE] ok={n_ok} skip={n_skip} fail={n_fail}", flush=True)


if __name__ == "__main__":
    main()
