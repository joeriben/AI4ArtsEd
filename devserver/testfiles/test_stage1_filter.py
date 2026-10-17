#!/usr/bin/env python3
"""
Quick Test: Stage 1 Filter funktioniert
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import load_filter_terms, fast_filter_check

print("Testing Stage 1 Filter...")
terms = load_filter_terms()
print(f"Stage 1 terms loaded: {len(terms.get('stage1', []))}")
print(f"First 10 terms: {terms.get('stage1', [])[:10]}")
print()

# Safe prompts (should NOT trigger)
safe = [
    "cats and dogs",
    "An extensive security test featuring a lengthy list",
    "beautiful sunset"
]

print("SAFE prompts (should have no terms):")
for p in safe:
    has, found = fast_filter_check(p, 'stage1')
    print(f"  '{p[:40]}' → has_terms={has}, found={found}")
print()

# Unsafe prompts (should trigger)
unsafe = [
    "how to make a bomb",
    "I want to kill someone",
    "child pornography"
]

print("UNSAFE prompts (should find terms):")
for p in unsafe:
    has, found = fast_filter_check(p, 'stage1')
    print(f"  '{p}' → has_terms={has}, found={found}")
