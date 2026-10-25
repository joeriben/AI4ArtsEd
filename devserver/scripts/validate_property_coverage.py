#!/usr/bin/env python3
"""
Property Coverage Validation Script

Validates that property combinations are well-covered by existing configs.
Identifies gaps where combinations have no matching configs.

Phase 1 Property Quadrants Implementation
"""

import json
import itertools
from pathlib import Path
from collections import defaultdict

# Property pairs
PROPERTY_PAIRS = [
    ('chill', 'chaotic'),
    ('narrative', 'algorithmic'),
    ('historical', 'contemporary'),
    ('explore', 'create'),
    ('playful', 'serious')
]

def load_configs_with_properties():
    """Load all configs that have properties field."""
    configs_dir = Path(__file__).parent.parent / 'schemas/configs/interception'
    configs = []

    for config_file in configs_dir.glob('*.json'):
        try:
            with open(config_file, encoding='utf-8') as f:
                config = json.load(f)
                if 'properties' in config:
                    configs.append({
                        'id': config_file.stem,
                        'name': config.get('name', {}),
                        'properties': set(config['properties'])
                    })
        except Exception as e:
            print(f"Error loading {config_file}: {e}")

    return configs

def generate_reasonable_combinations(min_props=2, max_props=6):
    """
    Generate reasonable property combinations.
    We consider combinations of 2-6 properties (one from each pair).
    """
    combinations = []

    # For each subset size (2 to 6 properties)
    for r in range(min_props, max_props + 1):
        # Choose r pairs
        for combo_pairs in itertools.combinations(range(len(PROPERTY_PAIRS)), r):
            # For each selected pair, try both properties
            for selections in itertools.product([0, 1], repeat=len(combo_pairs)):
                combo = []
                for i, pair_idx in enumerate(combo_pairs):
                    property_choice = selections[i]
                    combo.append(PROPERTY_PAIRS[pair_idx][property_choice])
                combinations.append(frozenset(combo))

    return combinations

def find_matches(configs, property_set):
    """Find configs that match ALL properties in the set."""
    matches = []
    for config in configs:
        if property_set.issubset(config['properties']):
            matches.append(config)
    return matches

def analyze_coverage(configs):
    """Analyze coverage for different combination sizes."""
    print("=" * 70)
    print("PROPERTY COVERAGE ANALYSIS")
    print("=" * 70)
    print()

    # Analyze by combination size
    for size in range(2, 7):
        print(f"\n{'='*70}")
        print(f"COMBINATIONS OF {size} PROPERTIES")
        print('='*70)

        combinations = generate_reasonable_combinations(size, size)
        uncovered = []
        coverage_counts = defaultdict(int)

        for combo in combinations:
            matches = find_matches(configs, combo)
            coverage_counts[len(matches)] += 1

            if not matches:
                uncovered.append(combo)

        total = len(combinations)
        covered = total - len(uncovered)
        coverage_pct = (covered / total * 100) if total > 0 else 0

        print(f"\nTotal combinations: {total}")
        print(f"Covered combinations: {covered} ({coverage_pct:.1f}%)")
        print(f"Uncovered combinations: {len(uncovered)}")

        # Show coverage distribution
        print(f"\nCoverage distribution:")
        for count in sorted(coverage_counts.keys()):
            combos = coverage_counts[count]
            pct = (combos / total * 100) if total > 0 else 0
            if count == 0:
                print(f"  {count} configs: {combos:4d} combos ({pct:5.1f}%) ❌")
            elif count == 1:
                print(f"  {count} config:  {combos:4d} combos ({pct:5.1f}%) ⚠️")
            else:
                print(f"  {count} configs: {combos:4d} combos ({pct:5.1f}%) ✅")

        # Show sample uncovered combinations
        if uncovered:
            print(f"\nSample uncovered combinations (showing up to 10):")
            for combo in sorted(uncovered, key=lambda x: len(x), reverse=True)[:10]:
                print(f"  - {', '.join(sorted(combo))}")

def show_config_stats(configs):
    """Show statistics about configs."""
    print("\n" + "="*70)
    print("CONFIG STATISTICS")
    print("="*70)
    print()

    print(f"Total configs with properties: {len(configs)}")
    print()

    # Count properties per config
    prop_counts = defaultdict(int)
    for config in configs:
        prop_counts[len(config['properties'])] += 1

    print("Properties per config:")
    for count in sorted(prop_counts.keys()):
        configs_count = prop_counts[count]
        print(f"  {count} properties: {configs_count} configs")

    # Most common properties
    print("\nProperty usage:")
    property_usage = defaultdict(int)
    for config in configs:
        for prop in config['properties']:
            property_usage[prop] += 1

    for prop in sorted(property_usage.keys()):
        count = property_usage[prop]
        pct = (count / len(configs) * 100)
        print(f"  {prop:15s}: {count:2d} configs ({pct:5.1f}%)")

def show_high_priority_gaps(configs):
    """Show high-priority gaps (4-5 property combinations)."""
    print("\n" + "="*70)
    print("HIGH-PRIORITY GAPS (4-5 properties)")
    print("="*70)
    print()

    combinations_4 = generate_reasonable_combinations(4, 4)
    combinations_5 = generate_reasonable_combinations(5, 5)

    uncovered = []
    for combo in list(combinations_4) + list(combinations_5):
        matches = find_matches(configs, combo)
        if not matches:
            uncovered.append(combo)

    if uncovered:
        print(f"Found {len(uncovered)} uncovered 4-5 property combinations")
        print("\nTop 20 gaps (sorted by complexity):")
        for combo in sorted(uncovered, key=lambda x: len(x), reverse=True)[:20]:
            print(f"  [{len(combo)} props] {', '.join(sorted(combo))}")
    else:
        print("✅ All 4-5 property combinations are covered!")

def main():
    """Main analysis function."""
    configs = load_configs_with_properties()

    if not configs:
        print("❌ No configs with properties found!")
        return 1

    show_config_stats(configs)
    analyze_coverage(configs)
    show_high_priority_gaps(configs)

    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    print()
    print("1. Combinations with 0 configs: Consider creating new configs")
    print("2. Combinations with 1 config: OK, but could add variety")
    print("3. Combinations with 2+ configs: Good coverage ✅")
    print()
    print("Note: Not all combinations need configs (some may not make sense)")
    print("Focus on pedagogically valuable combinations first.")
    print()

    return 0

if __name__ == '__main__':
    exit(main())
