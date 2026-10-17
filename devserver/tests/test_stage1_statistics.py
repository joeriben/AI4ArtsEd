#!/usr/bin/env python3
"""
Stage 1 Filter Statistics Test
Tests 1500 prompts (3 x 500) against Stage 1 hybrid filter
"""
import sys
from pathlib import Path
import time
from collections import Counter
import json
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.engine.stage_orchestrator import load_filter_terms, fast_filter_check

def load_prompts(filepath):
    """Load prompts from text file (one per line)"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def test_prompt_set(prompts, set_name, filter_level='stage1'):
    """Test a set of prompts and return statistics"""
    triggered = 0
    all_found_terms = []
    triggered_prompts = []

    start_time = time.time()

    for prompt in prompts:
        has_terms, found_terms = fast_filter_check(prompt, filter_level)
        if has_terms:
            triggered += 1
            all_found_terms.extend(found_terms)
            triggered_prompts.append((prompt, found_terms))

    elapsed = time.time() - start_time

    return {
        'set_name': set_name,
        'total': len(prompts),
        'triggered': triggered,
        'not_triggered': len(prompts) - triggered,
        'trigger_rate': (triggered / len(prompts) * 100) if prompts else 0,
        'avg_time_per_prompt': (elapsed / len(prompts) * 1000) if prompts else 0,  # ms
        'total_time': elapsed,
        'found_terms_counter': Counter(all_found_terms),
        'triggered_prompts': triggered_prompts[:10]  # Show first 10
    }

def main():
    testfiles_dir = Path(__file__).parent.parent / 'testfiles'

    files = {
        'harmlos': testfiles_dir / 'harmlos_kinder_jugend_prompts_500.txt',
        'probe_safe': testfiles_dir / 'probe_prompts_500_safe.txt',
        'provokant_safe': testfiles_dir / 'provokant_probe_prompts_500_safe.txt'
    }

    print("="*80)
    print("STAGE 1 FILTER STATISTICS TEST")
    print("="*80)
    print()

    # Load filter terms
    terms = load_filter_terms()
    print(f"Filter loaded: {len(terms.get('stage1', []))} terms in Stage 1")
    print(f"Terms (first 15): {terms.get('stage1', [])[:15]}")
    print()

    results = {}
    all_triggered = []  # Collect all triggered prompts for detailed report

    for set_name, filepath in files.items():
        if not filepath.exists():
            print(f"❌ File not found: {filepath}")
            continue

        print(f"Testing: {set_name} ({filepath.name})")
        prompts = load_prompts(filepath)
        print(f"  Loaded: {len(prompts)} prompts")

        result = test_prompt_set(prompts, set_name)
        results[set_name] = result

        # Collect triggered prompts with category info
        for prompt, found_terms in result['triggered_prompts']:
            all_triggered.append({
                'category': set_name,
                'prompt': prompt,
                'found_terms': found_terms,
                'term_count': len(found_terms)
            })

        print(f"  Triggered: {result['triggered']}/{result['total']} ({result['trigger_rate']:.1f}%)")
        print(f"  Avg time: {result['avg_time_per_prompt']:.3f}ms per prompt")
        print(f"  Total time: {result['total_time']:.2f}s")
        print()

    print("="*80)
    print("DETAILED STATISTICS")
    print("="*80)
    print()

    for set_name, result in results.items():
        print(f"📊 {set_name.upper()}")
        print(f"   Total prompts: {result['total']}")
        print(f"   Triggered: {result['triggered']} ({result['trigger_rate']:.1f}%)")
        print(f"   Not triggered: {result['not_triggered']} ({100-result['trigger_rate']:.1f}%)")
        print()

        if result['found_terms_counter']:
            print(f"   Top 10 found terms:")
            for term, count in result['found_terms_counter'].most_common(10):
                print(f"      '{term}': {count}x")
            print()

        if result['triggered_prompts']:
            print(f"   First 5 triggered prompts:")
            for i, (prompt, terms) in enumerate(result['triggered_prompts'][:5], 1):
                print(f"      {i}. \"{prompt[:60]}...\" → {terms}")
            print()
        print()

    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()

    total_prompts = sum(r['total'] for r in results.values())
    total_triggered = sum(r['triggered'] for r in results.values())
    total_time = sum(r['total_time'] for r in results.values())

    print(f"Total prompts tested: {total_prompts}")
    print(f"Total triggered: {total_triggered} ({total_triggered/total_prompts*100:.1f}%)")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average: {total_time/total_prompts*1000:.3f}ms per prompt")
    print()

    # Interpretation
    print("INTERPRETATION:")
    print()

    if 'harmlos' in results:
        harmlos_rate = results['harmlos']['trigger_rate']
        print(f"✓ False Positive Rate (harmlos): {harmlos_rate:.1f}%")
        if harmlos_rate < 5:
            print("   → ✅ EXCELLENT: Very low false positive rate!")
        elif harmlos_rate < 15:
            print("   → ⚠️  ACCEPTABLE: Some false positives, but workable")
        else:
            print("   → ❌ HIGH: Too many false positives, filter needs refinement")
    print()

    if 'probe_safe' in results:
        probe_rate = results['probe_safe']['trigger_rate']
        print(f"✓ Detection Rate (probe_safe): {probe_rate:.1f}%")
        print(f"   Note: ChatGPT marked these as 'safe', so triggers = false positives")
    print()

    if 'provokant_safe' in results:
        provokant_rate = results['provokant_safe']['trigger_rate']
        print(f"✓ Detection Rate (provokant_safe): {provokant_rate:.1f}%")
        print(f"   Note: ChatGPT marked these as 'safe', so triggers = false positives")
    print()

    print("PERFORMANCE:")
    print(f"✓ Average speed: {total_time/total_prompts*1000:.3f}ms per prompt")
    print(f"✓ Throughput: {total_prompts/total_time:.0f} prompts/second")
    print()
    print("="*80)

    # Save triggered prompts to file for manual review
    if all_triggered:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"stage1_filter_findings_{timestamp}.txt"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("STAGE 1 FILTER FINDINGS - MANUAL REVIEW REQUIRED\n")
            f.write("="*80 + "\n")
            f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total tested: {total_prompts} prompts\n")
            f.write(f"Total triggered: {len(all_triggered)} prompts\n")
            f.write(f"Trigger rate: {len(all_triggered)/total_prompts*100:.2f}%\n")
            f.write("\n")
            f.write("REVIEW INSTRUCTIONS:\n")
            f.write("- Check each triggered prompt below\n")
            f.write("- Determine if it's a FALSE POSITIVE (harmless content incorrectly flagged)\n")
            f.write("- Or TRUE POSITIVE (actually problematic content)\n")
            f.write("- Use this to refine the filter list if needed\n")
            f.write("\n")
            f.write("="*80 + "\n\n")

            for i, item in enumerate(all_triggered, 1):
                f.write(f"FINDING #{i}\n")
                f.write(f"Category: {item['category']}\n")
                f.write(f"Prompt: \"{item['prompt']}\"\n")
                f.write(f"Found terms: {item['found_terms']}\n")
                f.write(f"Assessment: [ ] FALSE POSITIVE  [ ] TRUE POSITIVE\n")
                f.write(f"Notes: ___________________________________________\n")
                f.write("\n" + "-"*80 + "\n\n")

        print(f"\n📄 Detailed findings saved to: {output_file}")
        print(f"   Please review {len(all_triggered)} triggered prompts manually")
        print()
    else:
        print("\n✅ No triggered prompts - no findings file created")
        print()

    # Also save JSON for programmatic analysis
    if all_triggered:
        json_output = f"stage1_filter_findings_{timestamp}.json"
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump({
                'test_date': datetime.now().isoformat(),
                'total_tested': total_prompts,
                'total_triggered': len(all_triggered),
                'trigger_rate': len(all_triggered)/total_prompts*100,
                'filter_terms_count': len(terms.get('stage1', [])),
                'findings': all_triggered,
                'statistics_by_category': {
                    name: {
                        'total': res['total'],
                        'triggered': res['triggered'],
                        'trigger_rate': res['trigger_rate']
                    }
                    for name, res in results.items()
                }
            }, f, indent=2, ensure_ascii=False)
        print(f"📊 JSON data saved to: {json_output}")
        print()

if __name__ == "__main__":
    main()
