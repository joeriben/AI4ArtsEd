"""
Test script for GPT-5 Image via OpenRouter integration

This tests the API-based Output-Chunk system with GPT-5 Image.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from schemas.engine.backend_router import BackendRouter, BackendRequest, BackendType


async def test_gpt5_image_direct():
    """Test GPT-5 Image generation directly via API Output-Chunk"""
    print("=" * 80)
    print("TEST: GPT-5 Image Direct API Output-Chunk")
    print("=" * 80)

    # Check for API key file
    key_file = project_root / "openrouter.key"
    if not key_file.exists():
        print("\n❌ ERROR: openrouter.key file not found!")
        print(f"Please create it at: {key_file}")
        print("Content: just paste your OpenRouter API key (one line)")
        return False

    api_key = key_file.read_text().strip()
    print(f"\n✓ openrouter.key found: {api_key[:10]}...")

    # Test prompt
    test_prompt = "A serene mountain landscape at sunset with golden light reflecting on a calm lake, photorealistic, highly detailed"

    print(f"\n📝 Test Prompt: {test_prompt}")

    # Create Backend Request
    request = BackendRequest(
        backend_type=BackendType.COMFYUI,  # Will be routed to API backend automatically
        model="",  # Not needed for API Output-Chunks
        prompt=test_prompt,
        parameters={
            'output_chunk': 'output_image_gpt5',  # Use GPT-5 Image API Output-Chunk
            'max_tokens': 4096
        }
    )

    # Initialize Backend Router
    router = BackendRouter()
    router.initialize()  # No services needed for API chunks

    print("\n🚀 Submitting request to Backend Router...")

    # Process request
    try:
        response = await router.process_request(request)

        if response.success:
            print("\n✅ SUCCESS!")
            print(f"\n📷 Generated Image URL: {response.content}")
            print(f"\n📊 Metadata:")
            for key, value in response.metadata.items():
                print(f"   {key}: {value}")

            return True
        else:
            print(f"\n❌ FAILED: {response.error}")
            return False

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_gpt5_via_executor():
    """Test GPT-5 Image via PipelineExecutor (full chain: dada → gpt5_image)"""
    print("\n" + "=" * 80)
    print("TEST: Full Chain - dada → gpt5_image (fast mode)")
    print("=" * 80)

    # Check for API key file
    key_file = project_root / "openrouter.key"
    if not key_file.exists():
        print("\n❌ ERROR: openrouter.key file not found!")
        return False

    print(f"\n✓ openrouter.key found")

    from schemas.engine.pipeline_executor import PipelineExecutor

    executor = PipelineExecutor(schemas_path=project_root / "schemas")
    test_input = "A mystical forest with glowing mushrooms and ethereal light"

    print(f"\n📝 Input: {test_input}")
    print("📋 Config: gpt5_image")
    print("⚡ Mode: fast (OpenRouter cloud)")

    try:
        result = await executor.execute_pipeline(
            config_name='gpt5_image',
            input_text=test_input,
            user_input=test_input,
        )

        if result.success:
            print("\n✅ SUCCESS!")
            print(f"\n📝 Final Output: {result.final_output[:200]}...")
            print(f"\n📊 Steps: {len(result.steps)}")

            # Check for image generation
            for step in result.steps:
                if step.metadata and 'image_url' in step.metadata:
                    print(f"\n📷 Generated Image: {step.metadata['image_url']}")

            return True
        else:
            print(f"\n❌ FAILED: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("GPT-5 Image OpenRouter Integration Tests")
    print("=" * 80)

    # Test 1: Direct API Output-Chunk
    result1 = await test_gpt5_image_direct()

    # Test 2: Full chain via executor
    result2 = await test_gpt5_via_executor()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Direct API Output-Chunk: {'✅ PASSED' if result1 else '❌ FAILED'}")
    print(f"Full Chain (dada → gpt5): {'✅ PASSED' if result2 else '❌ FAILED'}")

    if result1 and result2:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed")

    return result1 and result2


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
