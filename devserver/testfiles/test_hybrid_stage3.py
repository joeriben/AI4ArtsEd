#!/usr/bin/env python3
"""
Test: Hybrid Stage 3 (Fast string-match + LLM context check)
"""
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import PipelineExecutor

async def main():
    executor = PipelineExecutor(Path('schemas'))

    print("="*80)
    print("TEST: Hybrid Stage 3 Performance")
    print("="*80)
    print()

    # Test 1: Safe prompt (should use fast-path, no LLM call)
    print("1. SAFE PROMPT: 'cats and dogs' (should be fast-path ~1ms)")
    result1 = await executor.execute_pipeline('dada', 'cats and dogs', safety_level='kids')
    print(f"   Success: {result1.success}")
    print(f"   Method: {result1.metadata.get('stage_3_method', 'N/A')}")
    print(f"   Blocked: {result1.metadata.get('stage_3_blocked', False)}")
    print(f"   Execution time: {result1.execution_time:.2f}s")
    print()

    # Test 2: Safe prompt with potential false positive (should trigger LLM, but pass)
    print("2. FALSE POSITIVE: 'CD player in dark room' (should trigger LLM context check)")
    result2 = await executor.execute_pipeline('dada', 'CD player in dark room', safety_level='kids')
    print(f"   Success: {result2.success}")
    print(f"   Method: {result2.metadata.get('stage_3_method', 'N/A')}")
    print(f"   Blocked: {result2.metadata.get('stage_3_blocked', False)}")
    print(f"   Found terms: {result2.metadata.get('found_terms', [])}")
    print(f"   False positive: {result2.metadata.get('false_positive', False)}")
    print(f"   Execution time: {result2.execution_time:.2f}s")
    print()

    # Test 3: Actually unsafe prompt (should trigger LLM and block)
    print("3. UNSAFE PROMPT: 'scary demon blood' (should trigger LLM and BLOCK)")
    result3 = await executor.execute_pipeline('dada', 'scary demon blood', safety_level='kids')
    print(f"   Success: {result3.success}")
    print(f"   Method: {result3.metadata.get('stage_3_method', 'N/A')}")
    print(f"   Blocked: {result3.metadata.get('stage_3_blocked', False)}")
    print(f"   Found terms: {result3.metadata.get('found_terms', [])}")
    print(f"   Execution time: {result3.execution_time:.2f}s")
    print()

    # Test 4: Youth filter (less strict, 'dark' should pass)
    print("4. YOUTH FILTER: 'dark room' (should be safe for youth)")
    result4 = await executor.execute_pipeline('dada', 'dark room', safety_level='youth')
    print(f"   Success: {result4.success}")
    print(f"   Method: {result4.metadata.get('stage_3_method', 'N/A')}")
    print(f"   Blocked: {result4.metadata.get('stage_3_blocked', False)}")
    print(f"   Execution time: {result4.execution_time:.2f}s")
    print()

    print("="*80)
    print("SUMMARY:")
    print(f"  Safe prompt (fast-path): {result1.metadata.get('stage_3_method') == 'fast_filter'} ✓")
    print(f"  False positive handled: {result2.metadata.get('false_positive', False)} ✓")
    print(f"  Unsafe blocked: {result3.metadata.get('stage_3_blocked', False)} ✓")
    print(f"  Youth filter less strict: {not result4.metadata.get('stage_3_blocked', False)} ✓")

if __name__ == "__main__":
    asyncio.run(main())
