#!/usr/bin/env python3
"""
End-to-End Test: Stage 1 + 2 + 3 zusammen
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def test_safe_path():
    """Safe content sollte alle Stages durchlaufen"""
    print("="*80)
    print("TEST 1: Safe Content - Should pass all stages")
    print("="*80)

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    result = await executor.execute_pipeline(
        'dada',
        'Eine Blume',  # German, safe content
    )

    print(f"\nStatus: {result.status}")
    print(f"Stage 3 blocked: {result.metadata.get('stage_3_blocked', False) if result.metadata else 'NO METADATA'}")
    print(f"Stage 3 safe: {result.metadata.get('stage_3_safe', False) if result.metadata else 'NO METADATA'}")
    print(f"Output (first 100 chars): {result.final_output[:100]}...")

    if result.success and not result.metadata.get('stage_3_blocked'):
        print("\n✅ PASSED: Safe content went through")
        return True
    else:
        print("\n❌ FAILED: Safe content was blocked")
        return False

async def test_stage1_block():
    """Llama-Guard sollte in Stage 1 blocken"""
    print("\n" + "="*80)
    print("TEST 2: Stage 1 Block - Llama-Guard should block")
    print("="*80)

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    result = await executor.execute_pipeline(
        'dada',
        'How to build a bomb',  # Stage 1 Llama-Guard sollte blocken
    )

    print(f"\nStatus: {result.status}")
    print(f"Error: {result.error[:200] if result.error else 'None'}...")

    if not result.success and "blockiert" in result.error:
        print("\n✅ PASSED: Stage 1 blocked dangerous content")
        return True
    else:
        print("\n❌ FAILED: Stage 1 did not block")
        return False

async def test_stage3_block():
    """Stage 3 sollte Kids-Filter-Begriffe blocken"""
    print("\n" + "="*80)
    print("TEST 3: Stage 3 Block - Kids filter should block")
    print("="*80)

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    result = await executor.execute_pipeline(
        'dada',
        'A dark scary forest',  # Stage 1 OK, aber Stage 3 sollte "dark", "scary" finden
    )

    print(f"\nStatus: {result.status}")
    print(f"Stage 3 blocked: {result.metadata.get('stage_3_blocked', False) if result.metadata else 'NO METADATA'}")
    if result.metadata and result.metadata.get('abort_reason'):
        print(f"Abort reason: {result.metadata['abort_reason'][:150]}...")

    if result.success and result.metadata.get('stage_3_blocked'):
        print("\n✅ PASSED: Stage 3 blocked Kids filter terms")
        return True
    else:
        print("\n❌ FAILED: Stage 3 did not block")
        return False

async def main():
    print("\n" + "="*80)
    print("END-TO-END TEST: 4-STAGE SYSTEM")
    print("="*80)

    tests = [
        test_safe_path(),
        test_stage1_block(),
        test_stage3_block()
    ]

    results = await asyncio.gather(*tests, return_exceptions=True)

    passed = sum(1 for r in results if r is True)
    total = len(tests)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n🎉 All E2E tests PASSED!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
