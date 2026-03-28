#!/usr/bin/env python3
"""
Test actual pipeline execution with local LLM
"""
import sys
import asyncio
from pathlib import Path

# Add devserver to path
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.pipeline_executor import executor
from my_app.services.llm_service import LLMService

async def test_simple_execution():
    """Test simple pipeline execution"""
    print("\n" + "="*60)
    print("PIPELINE EXECUTION TEST")
    print("="*60)

    # Initialize executor with LLM service
    schemas_path = Path(__file__).parent / "schemas"
    llm_svc = LLMService()

    executor.initialize(
        llm_service=llm_svc,
        workflow_logic_service=None,
        comfyui_service=None
    )

    print("✓ Executor initialized")

    # Test translation_en config (simplest, single step)
    config_name = "translation_en"
    input_text = "Hallo Welt, wie geht es dir?"

    print(f"\n📝 Testing config: {config_name}")
    print(f"   Input: {input_text}")
    print(f"   Execution mode: eco (local LLM)")

    try:
        result = await executor.execute_pipeline(
            config_name=config_name,
            input_text=input_text,
            user_input=input_text,
        )

        print(f"\n✓ Pipeline execution: {result.status}")
        print(f"  Execution time: {result.execution_time:.2f}s")
        print(f"  Steps completed: {len(result.steps)}")

        for step in result.steps:
            print(f"\n  Step: {step.step_id}")
            print(f"    Status: {step.status}")
            print(f"    Chunk: {step.chunk_name}")
            if step.metadata:
                print(f"    Model: {step.metadata.get('model_used', 'N/A')}")
                print(f"    Backend: {step.metadata.get('backend_type', 'N/A')}")

        if result.final_output:
            print(f"\n📤 Final output:")
            print(f"  {result.final_output}")
        else:
            print(f"\n❌ No final output")

        if result.error:
            print(f"\n❌ Error: {result.error}")

        return result.status.value == "completed"

    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_dada_execution():
    """Test Dada config (two-step pipeline)"""
    print("\n" + "="*60)
    print("DADA PIPELINE TEST")
    print("="*60)

    config_name = "dada"
    input_text = "Der Hund bellt laut im Garten."

    print(f"\n📝 Testing config: {config_name}")
    print(f"   Input: {input_text}")
    print(f"   Execution mode: eco (local LLM)")

    try:
        result = await executor.execute_pipeline(
            config_name=config_name,
            input_text=input_text,
            user_input=input_text,
        )

        print(f"\n✓ Pipeline execution: {result.status}")
        print(f"  Execution time: {result.execution_time:.2f}s")
        print(f"  Steps completed: {len(result.steps)}")

        for step in result.steps:
            print(f"\n  Step: {step.step_id}")
            print(f"    Status: {step.status}")
            print(f"    Chunk: {step.chunk_name}")
            if step.output_data:
                print(f"    Output preview: {step.output_data[:100]}...")

        if result.final_output:
            print(f"\n📤 Final output:")
            print(f"  {result.final_output}")
        else:
            print(f"\n❌ No final output")

        if result.error:
            print(f"\n❌ Error: {result.error}")

        return result.status.value == "completed"

    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all execution tests"""
    print("\n" + "="*60)
    print("PIPELINE EXECUTION TEST SUITE")
    print("="*60)

    try:
        # Test 1: Simple translation
        test1_success = await test_simple_execution()

        # Test 2: Dada manipulation
        test2_success = await test_dada_execution()

        print("\n" + "="*60)
        if test1_success and test2_success:
            print("✅ ALL EXECUTION TESTS PASSED")
        else:
            print("⚠️ SOME TESTS FAILED")
        print("="*60)

        return test1_success and test2_success

    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED WITH EXCEPTION:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
