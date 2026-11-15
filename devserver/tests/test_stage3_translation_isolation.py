"""
Test: the device translation cache of the text a media model receives.

Verifies that translation reuse does not bleed across devices and that
requests without a device_id do not enter a shared global cache bucket.
Stage 3 kept this cache until 2026-11-01; the translation for the model
(schema_pipeline_routes._translate_for_model) keeps it now.
Run: python tests/test_stage3_translation_isolation.py
"""
import asyncio
import sys

sys.path.insert(0, '.')

from my_app.routes import schema_pipeline_routes as R
from schemas.engine import stage_orchestrator

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def reset_translation_cache():
    with stage_orchestrator._translation_cache_lock:
        stage_orchestrator._translation_cache.clear()


class FakeResult:
    def __init__(self, output: str):
        self.success = True
        self.final_output = output


class FakePipelineExecutor:
    def __init__(self):
        self.calls = []

    async def execute_pipeline(self, config_name, prompt, context_override=None):
        # context_override carries the perspective wording, where one is given.
        self.calls.append((config_name, prompt))
        return FakeResult(f"EN::{prompt}")


async def run_tests():
    print("\n[TEST 1] Same device reuses translation")
    reset_translation_cache()
    executor = FakePipelineExecutor()

    await R._translate_for_model("eine rote Kugel", executor, device_id="ipad_a")
    await R._translate_for_model("eine rote Kugel", executor, device_id="ipad_a")
    check("Same device hits translation backend once", len(executor.calls) == 1)

    print("\n[TEST 2] Different devices do not share translation cache")
    reset_translation_cache()
    executor = FakePipelineExecutor()

    await R._translate_for_model("eine rote Kugel", executor, device_id="ipad_a")
    await R._translate_for_model("eine rote Kugel", executor, device_id="ipad_b")
    check("Two devices trigger two separate translations", len(executor.calls) == 2)

    print("\n[TEST 3] Missing device_id does not fall into shared cache")
    reset_translation_cache()
    executor = FakePipelineExecutor()

    await R._translate_for_model("eine rote Kugel", executor, device_id=None)
    await R._translate_for_model("eine rote Kugel", executor, device_id=None)
    check("Unscoped requests do not reuse cached translation", len(executor.calls) == 2)


def test_translation_cache_is_isolated_per_device():
    """The same checks under pytest. They used to run while the file was
    imported, so pytest ran them during collection, before any test, and a
    failure ended the collection with sys.exit."""
    asyncio.run(run_tests())
    assert FAIL == 0, f"{FAIL} check(s) failed"


if __name__ == "__main__":
    asyncio.run(run_tests())

    print(f"\n{'=' * 50}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    if FAIL != 0:
        sys.exit(1)
