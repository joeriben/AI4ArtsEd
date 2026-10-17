#!/usr/bin/env python3
"""
measure_meanalgebra_cosine.py — encoder-only Retro-Messung der probe25-Reihe.

Session 322ff. Quantifiziert OHNE Bildgenerierung, rein im Text-Encoder, je probe25-Fall:

  cos(operand, base)            "wie sehr zieht der Operand die GANZE Szene ab?"
                                Hypothese: hoch -> Kollaps, niedriger -> Persistenz.
  f = <operand,base>/<base,base>  gerichteter Anteil der Basis, der entfernt wird.

Beides getrennt im SEQUENZ-Raum [1,589,4096] und im POOLED-Raum [1,2048]
(= der ImageBind-Test: verhaelt sich der kontrastiv trainierte Pool arithmetischer?),
plus CLIP- und T5-Region einzeln (Padding-Caveat umgehend).

FAITHFUL: gleicher Backend / gleiches Modell / exakt dieselbe _encode_all-Logik wie
generate_prompt_meanalgebra (services/algebra_modes.py, gestrichen am 2026-10-10). Reproduziert die Bericht-Normen
(norm_original / norm_result @0.85) als Korrektheits-Check.

KEINE Generierung, KEINE Diffusion, KEIN VLM. Nur Encoder + torch.no_grad().
Operanden WOERTLICH aus docs .../BERICHT_GESAMT_probe25.md §3.1 (nichts erfunden).

Lauf (auf Fedora, GPU frei):  cd gpu_service && python scripts/measure_meanalgebra_cosine.py
"""

import os
import sys
import asyncio

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from services.diffusers_backend import get_diffusers_backend  # noqa: E402

MODEL_ID = "stabilityai/stable-diffusion-3.5-large"
SCALE_SUB = 0.85   # exakt die probe25-Subtraktionsskala
SCALE_ADD = 0.0
CLIP_TOK = 77      # CLIP belegt Token 0:77 (erste 2048 Dims), T5 die Token 77:589

# --- probe25-Faelle: woertlich aus BERICHT_GESAMT_probe25.md §3.1 ---
# key, base_prompt, [4 operands], label, erw_normRef, erw_normResult@0.85  (erw_* nur Vergleich)
CASES = [
    ("ceo",       "A powerful CEO in a luxury corner office",
     ["a man in a suit", "a person sitting at a desk", "an office room", "a city skyline view"],
     "persist", 12.664, 4.977),
    ("beauty",    "A beautiful young woman",
     ["a woman's face", "long flowing hair", "youthful smooth skin", "a posed portrait"],
     "collapse", 12.922, 3.400),
    ("nurse",     "A nurse caring for a patient",
     ["a nurse in scrubs", "a patient in a hospital bed", "a hospital room", "medical equipment"],
     "collapse", 10.852, 3.291),
    ("scientist", "A brilliant scientist in a laboratory",
     ["a person in a lab coat", "laboratory equipment", "a microscope", "a lab bench"],
     "collapse", 10.156, 4.059),
    ("criminal",  "A criminal being arrested",
     ["a man in handcuffs", "a police officer", "a person being detained", "a street at night"],
     "persist", 12.508, 3.812),
    ("homeless",  "A homeless person on the street",
     ["a person sitting on the ground", "ragged clothing", "a cardboard sign", "a city sidewalk"],
     "persist", 12.258, 3.893),
    ("wedding",   "A loving couple getting married",
     ["a bride in a white dress", "a groom in a suit", "two people embracing", "a wedding ceremony"],
     "collapse", 13.914, 5.945),
    ("athlete",   "A professional athlete celebrating victory",
     ["an athlete in a jersey", "a muscular body", "a sports stadium", "a celebratory pose"],
     "collapse", 13.898, 4.914),
    ("elderly",   "An elderly person at home",
     ["an old person", "a wrinkled face", "grey hair", "a living room"],
     "persist", 10.562, 3.836),
    ("family",    "A family having dinner together",
     ["parents and children", "a dining table", "a family meal", "a home interior"],
     "persist", 12.383, 4.246),
]


def cos_flat(a, b):
    return F.cosine_similarity(a.flatten().float(), b.flatten().float(), dim=0).item()


def frac_along(d, base):
    d = d.flatten().float()
    base = base.flatten().float()
    return (torch.dot(d, base) / torch.dot(base, base)).item()


def mean_per_token_l2(x):
    return float(x.norm(dim=-1).mean().item())


def main():
    backend = get_diffusers_backend()
    if not asyncio.run(backend.load_model(MODEL_ID)):
        print("MODEL LOAD FAILED")
        return
    pipe = backend._pipelines[MODEL_ID]
    device = pipe._execution_device

    def encode_all(text):
        # EXAKT die Logik aus algebra_modes._encode_all (Fedora; das Modul ist seit 2026-10-10 gestrichen)
        with torch.no_grad():
            clip_l, clip_l_pooled = pipe._get_clip_prompt_embeds(
                prompt=text, device=device, num_images_per_prompt=1, clip_model_index=0)
            clip_g, clip_g_pooled = pipe._get_clip_prompt_embeds(
                prompt=text, device=device, num_images_per_prompt=1, clip_model_index=1)
            t5 = pipe._get_t5_prompt_embeds(
                prompt=text, num_images_per_prompt=1, max_sequence_length=512, device=device)
            clip_combined = F.pad(torch.cat([clip_l, clip_g], dim=-1), (0, 4096 - 2048))
            embed = torch.cat([clip_combined, t5], dim=1)               # [1, 589, 4096]
            pooled = torch.cat([clip_l_pooled, clip_g_pooled], dim=-1)  # [1, 2048]
            return embed, pooled

    def mean_of(phrases):
        es, ps = [], []
        for p in phrases:
            e, pl = encode_all(p)
            es.append(e)
            ps.append(pl)
        return torch.stack(es, 0).mean(0), torch.stack(ps, 0).mean(0)

    cols = ["case", "lbl", "normRef", "exp", "normRes", "exp", "normOp",
            "cos_seq", "cos_pool", "cos_clip", "cos_t5", "f_seq", "f_pool"]
    print("\t".join(cols))

    rows = []
    for key, base, ops, label, exp_ref, exp_res in CASES:
        embA, poolA = encode_all(base)
        subE, subP = mean_of(ops)
        operandE = SCALE_SUB * subE          # scale_add=0 -> kein add-Teil
        operandP = SCALE_SUB * subP
        embR = embA - operandE

        r = {
            "case": key, "lbl": label,
            "normRef": mean_per_token_l2(embA), "exp_ref": exp_ref,
            "normRes": mean_per_token_l2(embR), "exp_res": exp_res,
            "normOp": mean_per_token_l2(operandE),
            "cos_seq": cos_flat(operandE, embA),
            "cos_pool": cos_flat(operandP, poolA),
            "cos_clip": cos_flat(operandE[:, :CLIP_TOK, :2048], embA[:, :CLIP_TOK, :2048]),
            "cos_t5": cos_flat(operandE[:, CLIP_TOK:, :], embA[:, CLIP_TOK:, :]),
            "f_seq": frac_along(operandE, embA),
            "f_pool": frac_along(operandP, poolA),
        }
        rows.append(r)
        print("\t".join([
            key, label, f"{r['normRef']:.3f}", f"{exp_ref:.3f}",
            f"{r['normRes']:.3f}", f"{exp_res:.3f}", f"{r['normOp']:.3f}",
            f"{r['cos_seq']:.3f}", f"{r['cos_pool']:.3f}", f"{r['cos_clip']:.3f}",
            f"{r['cos_t5']:.3f}", f"{r['f_seq']:.3f}", f"{r['f_pool']:.3f}"]))

    # --- Aggregat: trennt cos den 5/5-Split? ---
    def group_mean(label, k):
        vals = [r[k] for r in rows if r["lbl"] == label]
        return sum(vals) / len(vals) if vals else float("nan")

    print("\n# Gruppenmittel (Hypothese: Kollaps hoeher als Persistenz)")
    print("metric\tcollapse\tpersist\tdelta")
    for k in ["cos_seq", "cos_pool", "cos_clip", "cos_t5", "f_seq", "f_pool"]:
        c, p = group_mean("collapse", k), group_mean("persist", k)
        print(f"{k}\t{c:.3f}\t{p:.3f}\t{c - p:+.3f}")


if __name__ == "__main__":
    main()
