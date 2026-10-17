#!/usr/bin/env python3
"""
Test script for Stage 3A: Pre-Output Text Safety Check
Tests Youth/Kids filter before media generation
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def test_kids_filter_unsafe():
    """Test Kids filter blocks horror/violence content"""
    print("\n" + "="*80)
    print("TEST 1: Kids Filter - Unsafe Content (Horror)")
    print("="*80)

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    unsafe_input = "A scary demon with skulls and blood"
    print(f"Input: {unsafe_input}")
    print(f"Expected: BLOCKED (demon, scary, skulls, blood all in Kids filter)")

    result = await executor.execute_pipeline(
        'dada',  # Has media_preferences with safety_level='kids'
        unsafe_input,
    )

    print(f"\nStatus: {result.status}")
    print(f"Final Output (first 300 chars):\n{result.final_output[:300]}...")

    if result.metadata:
        print(f"\nMetadata:")
        print(f"  stage_3_blocked: {result.metadata.get('stage_3_blocked', False)}")
        print(f"  safety_level: {result.metadata.get('safety_level', 'N/A')}")
        if result.metadata.get('abort_reason'):
            print(f"  abort_reason: {result.metadata['abort_reason']}")

    if result.metadata and result.metadata.get('stage_3_blocked'):
        print(f"✅ Test PASSED: Unsafe content was blocked by Stage 3")
        return True
    else:
        print(f"❌ Test FAILED: Unsafe content was NOT blocked!")
        return False

async def test_kids_filter_safe():
    """Test Kids filter allows safe content"""
    print("\n" + "="*80)
    print("TEST 2: Kids Filter - Safe Content")
    print("="*80)

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    safe_input = "The street where I live, in the morning"
    print(f"Input: {safe_input}")
    print(f"Expected: ALLOWED (no problematic terms)")

    result = await executor.execute_pipeline(
        'dada',
        safe_input,
    )

    print(f"\nStatus: {result.status}")
    print(f"Final Output (first 200 chars):\n{result.final_output[:200]}...")

    if result.metadata:
        print(f"\nMetadata:")
        print(f"  stage_3_safe: {result.metadata.get('stage_3_safe', False)}")
        print(f"  stage_3_blocked: {result.metadata.get('stage_3_blocked', False)}")
        print(f"  safety_level: {result.metadata.get('safety_level', 'N/A')}")
        if result.metadata.get('positive_prompt'):
            print(f"  positive_prompt: {result.metadata['positive_prompt'][:100]}...")
        if result.metadata.get('negative_prompt'):
            print(f"  negative_prompt: {result.metadata['negative_prompt'][:100]}...")

    if result.metadata and result.metadata.get('stage_3_safe') and not result.metadata.get('stage_3_blocked'):
        print(f"✅ Test PASSED: Safe content was allowed by Stage 3")
        return True
    else:
        print(f"❌ Test FAILED: Safe content was blocked!")
        return False

async def test_kids_vs_youth_difference():
    """Test that Kids filter is stricter than Youth filter"""
    print("\n" + "="*80)
    print("TEST 3: Kids vs Youth - Content with 'dark' term")
    print("="*80)

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    # "dark" is in Kids filter but NOT in Youth filter
    ambiguous_input = "A dark mysterious forest"
    print(f"Input: {ambiguous_input}")
    print(f"Expected: Kids=BLOCKED (has 'dark'), Youth=ALLOWED (no 'dark')")

    # Test with Kids filter (dada.json has safety_level='kids')
    print(f"\n--- Testing with Kids filter ---")
    result_kids = await executor.execute_pipeline(
        'dada',
        ambiguous_input,
    )

    kids_blocked = result_kids.metadata.get('stage_3_blocked', False) if result_kids.metadata else False
    print(f"Kids filter: {'BLOCKED' if kids_blocked else 'ALLOWED'}")

    # For Youth, we'd need a config with safety_level='youth'
    # For now, just report Kids result
    print(f"\n(Note: Youth filter test would require separate config with safety_level='youth')")

    if kids_blocked:
        print(f"✅ Test PASSED: Kids filter blocks 'dark' term")
        return True
    else:
        print(f"❌ Test FAILED: Kids filter should block 'dark' term")
        return False

async def test_violence_terms():
    """Test explicit violence terms are blocked"""
    print("\n" + "="*80)
    print("TEST 4: Violence Terms")
    print("="*80)

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    violence_input = "A scene of murder and torture with blood"
    print(f"Input: {violence_input}")
    print(f"Expected: BLOCKED (murder, torture, blood)")

    result = await executor.execute_pipeline(
        'dada',
        violence_input,
    )

    print(f"\nStatus: {result.status}")

    if result.metadata:
        blocked = result.metadata.get('stage_3_blocked', False)
        print(f"Stage 3 blocked: {blocked}")
        if result.metadata.get('abort_reason'):
            print(f"Reason: {result.metadata['abort_reason'][:200]}...")

    if result.metadata and result.metadata.get('stage_3_blocked'):
        print(f"✅ Test PASSED: Violence content blocked")
        return True
    else:
        print(f"❌ Test FAILED: Violence content not blocked")
        return False

async def main():
    """Run all Stage 3A tests"""
    print("\n" + "="*80)
    print("STAGE 3A: PRE-OUTPUT TEXT SAFETY CHECK TESTS")
    print("="*80)

    tests = [
        ("Kids Filter - Unsafe Content", test_kids_filter_unsafe),
        ("Kids Filter - Safe Content", test_kids_filter_safe),
        ("Kids vs Youth Difference", test_kids_vs_youth_difference),
        ("Violence Terms", test_violence_terms),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = await test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(1 for _, p in results if p)
    total = len(results)

    for test_name, test_passed in results:
        status = "✅ PASSED" if test_passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All Stage 3A tests PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
