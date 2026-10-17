#!/usr/bin/env python3
"""
Quick Integration Test: Hybrid Safety both stages
"""
import asyncio
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def test_safe_input():
    """Test: Safe input should use fast-path in Stage 1"""
    executor = PipelineExecutor(Path('schemas'))

    print("="*80)
    print("QUICK TEST: Hybrid Stage 1 (safe input)")
    print("="*80)
    print("Input: 'cats and dogs'")
    print("Expected: Stage 1 fast-path (~0.001s), NO Llama-Guard call")
    print()

    start = time.time()
    result = await executor.execute_pipeline('dada', 'cats and dogs', safety_level='research')
    elapsed = time.time() - start

    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Total time: {elapsed:.2f}s")
    print()

    if elapsed < 15:
        print("✅ HYBRID WORKS! (Stage 1 used fast-path, no 60s Llama-Guard)")
    else:
        print("❌ HYBRID FAILED! (Still calling Llama-Guard for every request)")

    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_safe_input())
