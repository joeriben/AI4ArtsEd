#!/usr/bin/env python3
"""
Simple quick test for Stage 3A
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def test_simple():
    """Simple test: Does Stage 3 run at all?"""
    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    print("Test Input: 'A scary demon'")
    print("Expected: Stage 3 should run and check this")
    print()

    result = await executor.execute_pipeline(
        'dada',
        'A scary demon',
    )

    print(f"Status: {result.status}")
    print(f"Has metadata: {result.metadata is not None}")

    if result.metadata:
        print(f"\nMetadata keys: {list(result.metadata.keys())}")
        print(f"stage_3_blocked: {result.metadata.get('stage_3_blocked', 'NOT SET')}")
        print(f"stage_3_safe: {result.metadata.get('stage_3_safe', 'NOT SET')}")
        print(f"safety_level: {result.metadata.get('safety_level', 'NOT SET')}")

        if result.metadata.get('abort_reason'):
            print(f"\nAbort reason: {result.metadata['abort_reason'][:200]}")

    print(f"\nFinal output (first 300 chars):")
    print(result.final_output[:300])

if __name__ == "__main__":
    asyncio.run(test_simple())
