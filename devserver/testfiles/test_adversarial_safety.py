#!/usr/bin/env python3
"""
Adversarial Safety Regression Test for Kids Fast-Filter

Tests that:
1. All MUST_BLOCK prompts trigger the fast-filter (bypass detection)
2. All MUST_PASS prompts do NOT trigger the fast-filter (false positive detection)
3. Semantic-only prompts are logged as known gaps (Stage 3 LLM responsibility)

Prompt file format:
  - Comments start with #
  - Language tag: [DE] or [EN] prefix (default: EN)
  - Semantic tag: [SEMANTIC] prefix (logged only, no failure)

Usage: cd devserver && python testfiles/test_adversarial_safety.py
Exit code: 0 = all pass, 1 = regressions found
"""
import sys
from pathlib import Path

# Add devserver to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.engine.stage_orchestrator import fast_filter_check


def load_prompts(filepath: Path) -> list[tuple[str, str, bool]]:
    """Load prompts from file. Returns list of (prompt, lang, is_semantic) tuples."""
    prompts = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            prompts.append(parse_prompt_line(line))
    return prompts


def parse_prompt_line(line: str) -> tuple[str, str, bool]:
    """Parse a prompt line, extracting language tag and semantic flag.

    Supports: [SEMANTIC], [DE], [EN] prefixes in any order.
    Returns (prompt, lang, is_semantic)
    """
    is_semantic = False
    lang = 'en'

    if line.startswith('[SEMANTIC]'):
        is_semantic = True
        line = line[len('[SEMANTIC]'):].strip()

    if line.startswith('[DE]'):
        lang = 'de'
        line = line[len('[DE]'):].strip()
    elif line.startswith('[EN]'):
        lang = 'en'
        line = line[len('[EN]'):].strip()

    return (line, lang, is_semantic)


def run_tests():
    test_dir = Path(__file__).resolve().parent
    must_block_file = test_dir / 'adversarial_kids_MUST_BLOCK.txt'
    must_pass_file = test_dir / 'adversarial_kids_MUST_PASS.txt'

    if not must_block_file.exists():
        print(f"FATAL: {must_block_file} not found")
        return 1
    if not must_pass_file.exists():
        print(f"FATAL: {must_pass_file} not found")
        return 1

    all_must_block = load_prompts(must_block_file)
    all_must_pass_raw = load_prompts(must_pass_file)

    # Separate MUST_PASS from SEMANTIC prompts
    must_pass = [(p, lang) for p, lang, sem in all_must_pass_raw if not sem]
    semantic = [(p, lang) for p, lang, sem in all_must_pass_raw if sem]
    must_block = [(p, lang) for p, lang, _ in all_must_block]

    print("=" * 70)
    print("ADVERSARIAL SAFETY REGRESSION TEST -- Kids Fast-Filter")
    print("=" * 70)
    print(f"  MUST_BLOCK prompts: {len(must_block)}")
    print(f"  MUST_PASS prompts:  {len(must_pass)}")
    print(f"  SEMANTIC prompts:   {len(semantic)} (logged only)")
    print()

    failures = []

    # --- Test 1: MUST_BLOCK ---
    print("-" * 70)
    print("TEST 1: MUST_BLOCK -- every prompt must trigger fast-filter")
    print("-" * 70)
    block_pass = 0
    block_fail = 0
    for prompt, lang in must_block:
        has_terms, found = fast_filter_check(prompt, 'kids', lang)
        if has_terms:
            block_pass += 1
        else:
            block_fail += 1
            failures.append(('BYPASS', prompt, lang))
            print(f"  BYPASS [{lang}]: \"{prompt}\"")
    print(f"  Result: {block_pass}/{len(must_block)} blocked, {block_fail} BYPASSED")
    print()

    # --- Test 2: MUST_PASS ---
    print("-" * 70)
    print("TEST 2: MUST_PASS -- no prompt must trigger fast-filter")
    print("-" * 70)
    pass_pass = 0
    pass_fail = 0
    for prompt, lang in must_pass:
        has_terms, found = fast_filter_check(prompt, 'kids', lang)
        if not has_terms:
            pass_pass += 1
        else:
            pass_fail += 1
            failures.append(('FALSE_POSITIVE', prompt, lang, found))
            print(f"  FALSE POSITIVE [{lang}]: \"{prompt}\" -- blocked by {found}")
    print(f"  Result: {pass_pass}/{len(must_pass)} passed, {pass_fail} FALSE POSITIVES")
    print()

    # --- Test 3: SEMANTIC (informational only) ---
    print("-" * 70)
    print("TEST 3: SEMANTIC -- known gaps (Stage 3 LLM responsibility)")
    print("-" * 70)
    sem_caught = 0
    sem_gap = 0
    for prompt, lang in semantic:
        has_terms, found = fast_filter_check(prompt, 'kids', lang)
        if has_terms:
            sem_caught += 1
            print(f"  CAUGHT [{lang}]: \"{prompt}\" -- by {found}")
        else:
            sem_gap += 1
            print(f"  GAP    [{lang}]: \"{prompt}\" -- relies on Stage 3 LLM")
    print(f"  Result: {sem_caught} caught by fast-filter, {sem_gap} gaps (expected)")
    print()

    # --- Summary ---
    print("=" * 70)
    if not failures:
        print("ALL TESTS PASSED")
        print("=" * 70)
        return 0
    else:
        print(f"FAILED -- {len(failures)} regression(s) found:")
        for f in failures:
            if f[0] == 'BYPASS':
                print(f"  BYPASS [{f[2]}]: \"{f[1]}\"")
            else:
                print(f"  FALSE POSITIVE [{f[2]}]: \"{f[1]}\" -- {f[3]}")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
