#!/usr/bin/env python3
"""
Quick test: Fast filter check function
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import load_filter_terms, fast_filter_check

# Test 1: Load filter terms
print("="*80)
print("TEST: Fast Filter Check Function")
print("="*80)
print()

print("1. Loading filter terms...")
terms = load_filter_terms()
print(f"   Kids terms loaded: {len(terms.get('kids', []))}")
print(f"   Youth terms loaded: {len(terms.get('youth', []))}")
print(f"   Kids terms (first 10): {terms.get('kids', [])[:10]}")
print()

# Test 2: Safe prompts (should NOT trigger)
safe_prompts = [
    "cats and dogs",
    "An extensive security test featuring a lengthy list",
    "beautiful sunset over mountains",
    "happy children playing"
]

print("2. Testing SAFE prompts (should have NO terms found):")
for prompt in safe_prompts:
    has_terms, found = fast_filter_check(prompt, 'kids')
    print(f"   '{prompt[:40]}...'")
    print(f"      has_terms={has_terms}, found={found}")
print()

# Test 3: Unsafe prompts (should trigger)
unsafe_prompts = [
    "scary demon with blood",
    "zombie apocalypse",
    "vampire with fangs",
    "dark horror scene"
]

print("3. Testing UNSAFE prompts (should FIND terms):")
for prompt in unsafe_prompts:
    has_terms, found = fast_filter_check(prompt, 'kids')
    print(f"   '{prompt}'")
    print(f"      has_terms={has_terms}, found={found}")
print()

print("="*80)
