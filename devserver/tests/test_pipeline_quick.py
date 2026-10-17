#!/usr/bin/env python3
"""Quick test with 10 prompts to verify script works"""
import sys
import time
from pathlib import Path
import asyncio

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.engine.pipeline_executor import PipelineExecutor


async def main():
    print("Quick 10-prompt test", flush=True)
    print("="*80 + "\n", flush=True)

    # Load 10 test prompts
    test_file = Path(__file__).parent / 'test_10_prompts.txt'
    with open(test_file, 'r', encoding='utf-8') as f:
        prompts = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(prompts)} prompts\n", flush=True)

    executor = PipelineExecutor(Path(__file__).parent.parent / 'schemas')

    passed = 0
    blocked = 0
    errors = 0

    for i, prompt in enumerate(prompts, 1):
        start = time.time()
        try:
            result = await executor.execute_pipeline(
                'dada',
                prompt,
                safety_level='kids'
            )
            elapsed = time.time() - start

            if result.success:
                passed += 1
                status = "✅"
            else:
                blocked += 1
                status = "🛑"

            print(f"[{i:2d}/{len(prompts)}] {status} {elapsed:.2f}s | {prompt[:50]}", flush=True)

        except Exception as e:
            errors += 1
            elapsed = time.time() - start
            print(f"[{i:2d}/{len(prompts)}] ❌ {elapsed:.2f}s | ERROR: {e}", flush=True)

    print(f"\n{'='*80}", flush=True)
    print(f"Results: {passed} passed, {blocked} blocked, {errors} errors", flush=True)
    print(f"{'='*80}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
