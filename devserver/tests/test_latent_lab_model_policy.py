#!/usr/bin/env python3
"""
Policy guard: pedagogical-platform Latent Lab chunks must source their
SD3.5 model_id from my_app.services.latent_lab_model.get_latent_lab_model_id(),
not from a hardcoded string.

The resolver answers SD3.5-Large on every card (Large has to fit in 32 GB;
the former Medium fallback for cards under 50 GB is gone). It stays the ONE
place that names the model: a chunk
that hardcodes "stabilityai/stable-diffusion-3.5-*" decides the model where
nobody looks for the decision.

This test catches regressions when a new Latent Lab chunk is added without
wiring up the resolver. If it fails, either:
  (a) wire the new chunk through get_latent_lab_model_id(), or
  (b) if the chunk is research-only and intentionally Large-locked, add it
      to RESEARCH_ONLY_CHUNKS below and document the reason.

Run: pytest devserver/tests/test_latent_lab_model_policy.py
"""

import re
from pathlib import Path

import pytest

CHUNKS_DIR = Path(__file__).resolve().parents[1] / "schemas" / "chunks"

# Pedagogical-platform Latent Lab chunks that MUST take the model from the resolver.
# Update this list when adding a new pedagogical Latent Lab feature.
LATENT_LAB_CHUNKS = [
    "output_image_surrealizer_diffusers.py",
    "output_image_feature_probing_diffusers.py",
    "output_image_attention_cartography_diffusers.py",
    "output_image_concept_algebra_diffusers.py",
    "output_image_denoising_archaeology_diffusers.py",
    "output_image_denoising_archaeology_comfyui.py",
    "output_image_composable_diffusion_diffusers.py",
    "output_image_composable_diffusion_comfyui.py",
    "output_image_concept_algebra_comfyui.py",
    "output_image_feature_probing_comfyui.py",
    "output_image_surrealizer_comfyui.py",
    "output_image_attention_cartography_comfyui.py",
]

# Chunks that legitimately hardcode SD3.5 model IDs and are out of scope:
# - output_image_sd35_diffusers.py: standard SD3.5 image generation, not Latent Lab.
# - output_image_sd35_img2img_diffusers.py: standard SD3.5 img2img.
# - output_image_sd35_turbo_diffusers.py: standard SD3.5 Turbo.
# Empty since 2026-09-19: the two Decomposition chunks were its only entries and
# left with the instrument. The list and its checks stay for the next one.
RESEARCH_ONLY_CHUNKS: set[str] = set()

HARDCODED_SD35 = re.compile(r'["\']stabilityai/stable-diffusion-3\.5')
# Both import forms. The ComfyUI chunks need several names from the resolver and
# take them in one parenthesised import; a check written against the single-line
# form matched none of them and passed every one of them without looking.
RESOLVER_IMPORT = re.compile(
    r"from my_app\.services\.latent_lab_model import\s*\(?[^)]*get_latent_lab_model_id"
)
RESOLVER_IMPORT_HINT = "from my_app.services.latent_lab_model import get_latent_lab_model_id"
RESOLVER_CALL = "get_latent_lab_model_id()"


def _check_chunk(chunk_name: str) -> None:
    path = CHUNKS_DIR / chunk_name
    assert path.is_file(), f"Latent Lab chunk not found: {path}"
    content = path.read_text(encoding="utf-8")

    assert RESOLVER_IMPORT.search(content), (
        f"{chunk_name} is registered in LATENT_LAB_CHUNKS but does not import "
        f"the resolver. Add: '{RESOLVER_IMPORT_HINT}' inside execute()."
    )
    assert RESOLVER_CALL in content, (
        f"{chunk_name} imports the resolver but never calls it. "
        f"Add: 'model_id = await get_latent_lab_model_id()' before the "
        f"backend.generate_image_with_*() call."
    )
    forbidden = HARDCODED_SD35.findall(content)
    assert not forbidden, (
        f"{chunk_name} hardcodes a SD3.5 model ID ({forbidden!r}). "
        f"Latent Lab chunks must take the model from get_latent_lab_model_id(), "
        f"the one place that names it. If this chunk "
        f"is intentionally Large-only research code, add it to "
        f"RESEARCH_ONLY_CHUNKS and remove it from LATENT_LAB_CHUNKS."
    )


@pytest.mark.parametrize("chunk_name", LATENT_LAB_CHUNKS)
def test_the_registered_chunks_use_the_resolver(chunk_name):
    """Every chunk on the list, rather than six named by hand.

    The list grew with each chunk of the ComfyUI move while the checks stayed at
    the six original names, so a registration recorded an intention and checked
    nothing.
    """
    _check_chunk(chunk_name)


def test_chunk_lists_are_disjoint():
    """A chunk cannot be both pedagogical (must use resolver) and research-only."""
    overlap = set(LATENT_LAB_CHUNKS) & RESEARCH_ONLY_CHUNKS
    assert not overlap, (
        f"Chunks appear in both LATENT_LAB_CHUNKS and RESEARCH_ONLY_CHUNKS: {overlap}. "
        f"A chunk must be one or the other."
    )


def test_research_only_chunks_exist():
    """Sanity: research-only chunks listed actually exist on disk."""
    for chunk_name in RESEARCH_ONLY_CHUNKS:
        path = CHUNKS_DIR / chunk_name
        assert path.is_file(), (
            f"RESEARCH_ONLY_CHUNKS lists {chunk_name} but the file is missing. "
            f"Either the chunk was removed (update the list) or the path is wrong."
        )


if __name__ == "__main__":
    # Allow running as a plain script: `python test_latent_lab_model_policy.py`
    failures = []
    tests = [
        ("surrealizer",            lambda: _check_chunk("output_image_surrealizer_diffusers.py")),
        ("feature_probing",        lambda: _check_chunk("output_image_feature_probing_diffusers.py")),
        ("attention_cartography",  lambda: _check_chunk("output_image_attention_cartography_diffusers.py")),
        ("concept_algebra",        lambda: _check_chunk("output_image_concept_algebra_diffusers.py")),
        ("denoising_archaeology",  lambda: _check_chunk("output_image_denoising_archaeology_diffusers.py")),
        ("composable_diffusion",   lambda: _check_chunk("output_image_composable_diffusion_diffusers.py")),
        ("disjoint_lists",         test_chunk_lists_are_disjoint),
        ("research_only_exists",   test_research_only_chunks_exist),
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failures.append((name, str(e)))
            print(f"  FAIL  {name}: {e}")
    print()
    if failures:
        print(f"{len(failures)} test(s) failed.")
        raise SystemExit(1)
    print(f"All {len(tests)} tests passed.")
