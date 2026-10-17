#!/usr/bin/env python3
"""
Test: Wird bei safe content noch Bildgenerierung ausgelöst?
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def test_safe_triggers_media():
    """Safe content sollte Stage 3 passieren und media_output auslösen"""
    print("Testing: Safe content should trigger media generation")
    print("Input: 'A beautiful flower'")
    print()

    executor = PipelineExecutor(Path(__file__).parent / 'schemas')

    result = await executor.execute_pipeline(
        'dada',
        'A beautiful flower',
    )

    print(f"Status: {result.status}")
    print(f"Success: {result.success}")

    if result.metadata:
        print(f"\nMetadata:")
        print(f"  stage_3_blocked: {result.metadata.get('stage_3_blocked', False)}")
        print(f"  stage_3_safe: {result.metadata.get('stage_3_safe', False)}")
        print(f"  positive_prompt exists: {bool(result.metadata.get('positive_prompt'))}")
        print(f"  negative_prompt exists: {bool(result.metadata.get('negative_prompt'))}")

        if result.metadata.get('positive_prompt'):
            print(f"\nPositive prompt (first 100 chars):")
            print(f"  {result.metadata['positive_prompt'][:100]}")

        if result.metadata.get('negative_prompt'):
            print(f"\nNegative prompt (first 100 chars):")
            print(f"  {result.metadata['negative_prompt'][:100]}")

    print(f"\nFinal output (first 200 chars):")
    print(result.final_output[:200])

    # Check: Stage 3 should NOT block, should mark as safe
    if result.success and result.metadata.get('stage_3_safe') and not result.metadata.get('stage_3_blocked'):
        print("\n✅ SUCCESS: Safe content passed Stage 3 and is ready for media generation")
        print("   (Media generation would happen in schema_pipeline_routes.py)")
        return True
    else:
        print("\n❌ FAILED: Safe content was blocked or didn't pass Stage 3 correctly")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_safe_triggers_media())
    sys.exit(0 if result else 1)
