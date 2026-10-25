#!/usr/bin/env python3
"""
measure_meanalgebra_whitened.py — Nachtest zu measure_meanalgebra_cosine.py.

Frage: Ist die cos_seq~0.99-Saettigung des Erstlaufs ein Anisotropie-Artefakt?
Wir entfernen die gemeinsame Richtung (mean-centering gegen den In-Set-Mittelwert
der beteiligten Phrasen: 10 Basen + 40 Operanden, dedupliziert) und rechnen cos/f
auf den RESIDUEN neu. Zusaetzlich all-but-top-3 (Top-3-PCA-Abzug) im Pool.

Nichts erfunden: Korpus = exakt die committeten probe25-Phrasen (import CASES).
Faithful: gleiche encode_all-Logik / gleicher Backend wie der Erstlauf.

  base_c    = base    - mu
  operand_c = operand - scale_sub*mu
  cos_cen   = cos(operand_c, base_c)
  f_cen     = <operand_c, base_c> / <base_c, base_c>

KEINE Generierung, KEIN VLM. Nur Encoder + torch.no_grad().
Lauf (auf Fedora):  cd gpu_service && python scripts/measure_meanalgebra_whitened.py
"""

import os
import sys
import asyncio

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from services.diffusers_backend import get_diffusers_backend          # noqa: E402
from measure_meanalgebra_cosine import CASES, SCALE_SUB, MODEL_ID      # noqa: E402


def cos_flat(a, b):
    return F.cosine_similarity(a.flatten().float(), b.flatten().float(), dim=0).item()


def frac(d, base):
    d = d.flatten().float()
    base = base.flatten().float()
    return (torch.dot(d, base) / torch.dot(base, base)).item()


def main():
    backend = get_diffusers_backend()
    if not asyncio.run(backend.load_model(MODEL_ID)):
        print("MODEL LOAD FAILED")
        return
    pipe = backend._pipelines[MODEL_ID]
    device = pipe._execution_device

    cache = {}

    def enc(text):
        if text in cache:
            return cache[text]
        with torch.no_grad():
            cl, clp = pipe._get_clip_prompt_embeds(
                prompt=text, device=device, num_images_per_prompt=1, clip_model_index=0)
            cg, cgp = pipe._get_clip_prompt_embeds(
                prompt=text, device=device, num_images_per_prompt=1, clip_model_index=1)
            t5 = pipe._get_t5_prompt_embeds(
                prompt=text, num_images_per_prompt=1, max_sequence_length=512, device=device)
            seq = torch.cat([F.pad(torch.cat([cl, cg], dim=-1), (0, 4096 - 2048)), t5], dim=1)
            pool = torch.cat([clp, cgp], dim=-1)
        cache[text] = (seq, pool)
        return cache[text]

    # --- Korpus-Mittel (die gemeinsame Cone-Richtung) ueber DEDUPLIZIERTE Phrasen ---
    corpus = []
    for key, base, ops, *_ in CASES:
        corpus.append(base)
        corpus.extend(ops)
    corpus = list(dict.fromkeys(corpus))   # dedupe, Reihenfolge stabil
    seqs = torch.stack([enc(p)[0] for p in corpus], 0)   # [N,1,589,4096]
    pools = torch.stack([enc(p)[1] for p in corpus], 0)  # [N,1,2048]
    mu_seq = seqs.mean(0)                                 # [1,589,4096]
    mu_pool = pools.mean(0)                               # [1,2048]
    N = len(corpus)

    # --- all-but-top-3 Basis aus dem zentrierten Pool-Korpus ---
    Pc = (pools - mu_pool).reshape(N, -1).float()         # [N,2048]
    _, S, Vh = torch.linalg.svd(Pc, full_matrices=False)
    Vtop = Vh[:3]                                         # [3,2048], orthonormal
    ev = (S ** 2) / (S ** 2).sum()
    print(f"# Korpus N={N} (deduped). Pool-PC explained-variance top6: "
          + " ".join(f"{x:.3f}" for x in ev[:6].tolist()))

    def proj_out(x_pool):                                 # x_pool [1,2048] (zentriert)
        v = x_pool.reshape(1, -1).float()
        for k in range(Vtop.shape[0]):
            vk = Vtop[k:k + 1]
            v = v - (v @ vk.T) * vk
        return v

    cols = ["case", "lbl", "cos_seq_raw", "cos_seq_cen", "cos_pool_raw", "cos_pool_cen",
            "f_seq_cen", "f_pool_raw", "f_pool_cen", "cos_pool_abt3", "f_pool_abt3"]
    print("\t".join(cols))

    rows = []
    for key, base, ops, label, *_ in CASES:
        embA, poolA = enc(base)
        subE = torch.stack([enc(p)[0] for p in ops], 0).mean(0)
        subP = torch.stack([enc(p)[1] for p in ops], 0).mean(0)
        operandE = SCALE_SUB * subE
        operandP = SCALE_SUB * subP

        # raw (zur Kontrolle, muss Erstlauf reproduzieren)
        cos_seq_raw = cos_flat(operandE, embA)
        cos_pool_raw = cos_flat(operandP, poolA)
        f_pool_raw = frac(operandP, poolA)

        # zentriert: Residuen statt Absolut-Embeddings
        embA_c = embA - mu_seq
        operandE_c = operandE - SCALE_SUB * mu_seq
        poolA_c = poolA - mu_pool
        operandP_c = operandP - SCALE_SUB * mu_pool
        cos_seq_cen = cos_flat(operandE_c, embA_c)
        f_seq_cen = frac(operandE_c, embA_c)
        cos_pool_cen = cos_flat(operandP_c, poolA_c)
        f_pool_cen = frac(operandP_c, poolA_c)

        # all-but-top-3 (Pool, auf den zentrierten Residuen)
        pA = proj_out(poolA_c)
        oP = proj_out(operandP_c)
        cos_pool_abt3 = cos_flat(oP, pA)
        f_pool_abt3 = frac(oP, pA)

        r = dict(case=key, lbl=label, cos_seq_raw=cos_seq_raw, cos_seq_cen=cos_seq_cen,
                 cos_pool_raw=cos_pool_raw, cos_pool_cen=cos_pool_cen, f_seq_cen=f_seq_cen,
                 f_pool_raw=f_pool_raw, f_pool_cen=f_pool_cen,
                 cos_pool_abt3=cos_pool_abt3, f_pool_abt3=f_pool_abt3)
        rows.append(r)
        print("\t".join([key, label] + [f"{r[c]:.3f}" for c in cols[2:]]))

    def gm(lbl, k):
        v = [r[k] for r in rows if r["lbl"] == lbl]
        return sum(v) / len(v)

    print("\n# Gruppenmittel (Hypothese: collapse > persist)")
    print("metric\tcollapse\tpersist\tdelta")
    for k in cols[2:]:
        c, p = gm("collapse", k), gm("persist", k)
        print(f"{k}\t{c:.3f}\t{p:.3f}\t{c - p:+.3f}")


if __name__ == "__main__":
    main()
