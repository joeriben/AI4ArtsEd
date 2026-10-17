#!/usr/bin/env python3
"""
judge_probe25_blind.py — blindes Bild-Instrument fuer die probe25-2x2.

Schneidet die 10 Composite-Strips (strip_<case>.png, 1320x402: Kopfzeile + 4 Panels +
Fusszeile) in EINZEL-Panels (nur Bildbereich; Kopf/Fuss ab -> kein Prompt/Label-Leak)
und laesst je Panel ein lokales VLM (ollama) BLIND urteilen (nur Pixel, keine Hypothese):

  human:    yes | partial | no
  coherent: coherent | degraded | noise
  role:     kurze Rolle/Szene oder 'none'

Panel 0 = REF (Baseline), Panel 1-3 = manipuliert (sub s42/s7/s123).
Ueberleben = (c) der manipulierten Panels evoziert dieselbe Rolle wie (c) der Baseline,
bei (b) != noise. Der Richter sieht NIE Prompt, Label oder Hypothese.

Usage:
  python scripts/judge_probe25_blind.py crop  <strips_dir> <out_dir>
  python scripts/judge_probe25_blind.py judge <strips_dir> <out_dir> <ollama_model>
"""
import sys
import os
import base64

import requests
from PIL import Image

CASES = ["ceo", "beauty", "nurse", "scientist", "criminal",
         "homeless", "wedding", "athlete", "elderly", "family"]
PANEL_LABELS = ["REF", "sub_s42", "sub_s7", "sub_s123"]
N_PANELS = 4
OLLAMA = "http://localhost:11434/api/generate"
PROMPT = (
    "Describe this image in one sentence. "
    "Then answer EXACTLY in this format, one per line:\n"
    "human: <yes|partial|no>\n"
    "coherent: <coherent|degraded|noise>\n"
    "role: <short free text of the role/occupation/scene, or 'none'>"
)
STOP = {"a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "to",
        "is", "are", "person", "people", "image", "photo", "scene", "none", "man", "woman"}


# Feste Bandgrenzen der Vorlage (alle Strips 1320x402, identisches Template):
# Kopfzeile 0-56, Bildband 56-372, Fusszeile 372-402. An ceo-Panels verifiziert.
Y0, Y1 = 56, 372


def crop_strip(path, out_dir):
    case = os.path.basename(path).replace("strip_", "").replace(".png", "")
    img = Image.open(path).convert("RGB")
    W, H = img.size
    y0, y1 = Y0, Y1
    pw = W // N_PANELS
    outs = []
    for k in range(N_PANELS):
        x0 = k * pw
        x1 = (k + 1) * pw if k < N_PANELS - 1 else W
        panel = img.crop((x0 + 3, y0, x1 - 3, y1))     # 3px gegen Panel-Raender
        op = os.path.join(out_dir, f"{case}__{k}_{PANEL_LABELS[k]}.png")
        panel.save(op)
        outs.append(op)
    print(f"{case}: band=({y0},{y1}) panel_w={pw} -> {len(outs)} panels")
    return outs


def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def judge(path, model):
    r = requests.post(OLLAMA, json={
        "model": model, "prompt": PROMPT, "images": [b64(path)],
        "stream": False, "options": {"temperature": 0, "num_ctx": 4096}
    }, timeout=300)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def parse(resp):
    out = {"human": "?", "coherent": "?", "role": "?"}
    for line in resp.splitlines():
        low = line.strip().lower()
        for k in ("human", "coherent", "role"):
            if low.startswith(k + ":"):
                out[k] = line.split(":", 1)[1].strip()
    return out


def words(s):
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split()
            if w not in STOP and len(w) > 2}


def main():
    mode, strips, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)

    if mode == "crop":
        for c in CASES:
            crop_strip(os.path.join(strips, f"strip_{c}.png"), out)
        return

    if mode == "judge":
        model = sys.argv[4]
        for c in CASES:
            if not os.path.exists(os.path.join(out, f"{c}__0_REF.png")):
                crop_strip(os.path.join(strips, f"strip_{c}.png"), out)

        print(f"# model={model}")
        print("case\tpanel\thuman\tcoherent\trole")
        data = {}
        for c in CASES:
            data[c] = []
            for k in range(N_PANELS):
                panel = os.path.join(out, f"{c}__{k}_{PANEL_LABELS[k]}.png")
                pa = parse(judge(panel, model))
                data[c].append(pa)
                print(f"{c}\t{PANEL_LABELS[k]}\t{pa['human']}\t{pa['coherent']}\t{pa['role'][:70]}")

        print("\n# Per-Case: Ueberleben (manipuliert vs. Baseline)")
        print("case\tbase_role\tsurvived/3\tmanip_coherent\tmanip_roles")
        for c in CASES:
            base = data[c][0]
            bw = words(base["role"])
            survived = 0
            manip_roles, manip_coh = [], []
            for k in (1, 2, 3):
                m = data[c][k]
                manip_roles.append(m["role"][:30])
                manip_coh.append(m["coherent"])
                if "noise" not in m["coherent"].lower() and (bw & words(m["role"])):
                    survived += 1
            print(f"{c}\t{base['role'][:28]}\t{survived}/3\t{','.join(manip_coh)}\t{' | '.join(manip_roles)}")


if __name__ == "__main__":
    main()
