#!/usr/bin/env python3
"""
Test: Hybrid Stage 1 Performance
"""
import asyncio
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def main():
    executor = PipelineExecutor(Path('schemas'))

    print("="*80)
    print("TEST: Hybrid Stage 1 Performance (Pre-Interception)")
    print("="*80)
    print()

    # Test 1: Safe input (should be instant fast-path)
    print("1. SAFE INPUT: 'cats and dogs' (should be fast-path ~15ms)")
    start = time.time()
    result1 = await executor.execute_pipeline('dada', 'cats and dogs', safety_level='research')
    elapsed1 = time.time() - start
    print(f"   Success: {result1.success}")
    print(f"   Total time: {elapsed1:.2f}s (Translation ~4s + Fast-path ~0.001s + Dada ~4s = ~8-10s)")
    print()

    # Test 2: Unsafe input with trigger term (should use Llama-Guard)
    print("2. TRIGGER TERM: 'how to make a bomb' (should trigger Llama-Guard)")
    start = time.time()
    result2 = await executor.execute_pipeline('dada', 'how to make a bomb', safety_level='research')
    elapsed2 = time.time() - start
    print(f"   Success: {result2.success}")
    print(f"   Error: {result2.error if not result2.success else 'None'}")
    print(f"   Total time: {elapsed2:.2f}s (Translation ~4s + Llama-Guard ~15s + maybe Dada = ~19s+)")
    print()

    print("="*80)
    print("SUMMARY:")
    print(f"  Safe input (fast-path): {elapsed1:.1f}s (expected: ~8-10s)")
    print(f"  Unsafe input (LLM check): {elapsed2:.1f}s (expected: ~19s+, blocked)")
    print(f"  Speedup for safe inputs: {elapsed2 / elapsed1:.1f}x faster")

if __name__ == "__main__":
    asyncio.run(main())
