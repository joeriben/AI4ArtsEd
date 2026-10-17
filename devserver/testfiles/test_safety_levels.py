#!/usr/bin/env python3
"""
Test: Safety Level Parameter funktioniert
"""
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def main():
    executor = PipelineExecutor(Path('schemas'))

    test_input = "A dark scary demon"

    print("="*80)
    print("TEST: Safety Level Parameter")
    print("="*80)
    print(f"Input: '{test_input}'")
    print()

    # Test 1: Kids (should block)
    print("1. safety_level='kids' (should BLOCK 'dark', 'scary', 'demon')")
    result_kids = await executor.execute_pipeline('dada', test_input, safety_level='kids')
    print(f"   Blocked: {result_kids.metadata.get('stage_3_blocked', False) if result_kids.metadata else False}")

    # Test 2: Youth (should allow 'dark' but block 'scary'? - actually 'scary' not in youth)
    print("\n2. safety_level='youth' (less strict, but still has some terms)")
    result_youth = await executor.execute_pipeline('dada', test_input, safety_level='youth')
    print(f"   Blocked: {result_youth.metadata.get('stage_3_blocked', False) if result_youth.metadata else False}")

    # Test 3: Research (should NOT run Stage 3 at all)
    print("\n3. safety_level='research' (Stage 3 should be skipped)")
    result_off = await executor.execute_pipeline('dada', test_input, safety_level='research')
    print(f"   Has Stage 3 metadata: {'stage_3_blocked' in (result_off.metadata or {})}")
    print(f"   Output exists: {bool(result_off.final_output)}")

    print("\n" + "="*80)
    print("RESULTS:")
    print(f"  Kids blocked: {result_kids.metadata.get('stage_3_blocked', False) if result_kids.metadata else False} (expected: True)")
    print(f"  Youth blocked: {result_youth.metadata.get('stage_3_blocked', False) if result_youth.metadata else False} (expected: False - youth filter doesn't have 'dark', 'scary', 'demon')")
    print(f"  Off skipped Stage 3: {not ('stage_3_blocked' in (result_off.metadata or {}))} (expected: True)")

if __name__ == "__main__":
    asyncio.run(main())
