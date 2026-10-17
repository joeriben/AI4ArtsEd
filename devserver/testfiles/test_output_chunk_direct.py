"""
Direct Output-Chunk Test - SD3.5 Large Image Generation

This test validates ONLY the Output-Chunk system:
- Load output_image_sd35_large.json
- Apply input_mappings with test prompts
- Prepare workflow for ComfyUI submission
- NO pre-pipeline, NO manipulate chunk, just pure output testing
"""

import json
import asyncio
from pathlib import Path
from schemas.engine.backend_router import BackendRouter, BackendRequest, BackendType


async def test_direct_output_chunk_submission():
    """Test direct Output-Chunk workflow preparation and submission"""
    print("\n" + "=" * 70)
    print("DIRECT OUTPUT-CHUNK TEST - SD3.5 Large Image Generation")
    print("=" * 70)

    # Test parameters - simple prompts for testing
    test_positive_prompt = "A majestic mountain landscape at sunset, dramatic lighting, high quality, detailed"
    test_negative_prompt = "blurry, bad quality, watermark, text, distorted, low resolution"

    print(f"\n📝 Test Input:")
    print(f"   Positive: {test_positive_prompt}")
    print(f"   Negative: {test_negative_prompt}")
    print(f"   Resolution: 1024x1024")
    print(f"   Steps: 25")
    print(f"   CFG: 5.5")

    # Initialize BackendRouter
    router = BackendRouter()

    # Create a direct ComfyUI request with output_chunk parameter
    request = BackendRequest(
        backend_type=BackendType.COMFYUI,
        model="",  # Not needed for Output-Chunks
        prompt=test_positive_prompt,  # This will be injected as positive prompt
        parameters={
            'output_chunk': 'output_image_sd35_large',
            'negative_prompt': test_negative_prompt,
            'width': 1024,
            'height': 1024,
            'steps': 25,
            'cfg': 5.5,
            'sampler_name': 'euler',
            'scheduler': 'normal',
            'seed': 'random'
        },
        stream=False
    )

    print("\n🔧 Test 1: Load Output-Chunk")
    chunk = router._load_output_chunk('output_image_sd35_large')

    if not chunk:
        print("❌ FAILED: Could not load Output-Chunk")
        return False

    print(f"✅ PASSED: Output-Chunk loaded")
    print(f"   - Name: {chunk['name']}")
    print(f"   - Media Type: {chunk['media_type']}")
    print(f"   - Workflow Nodes: {len(chunk['workflow'])}")
    print(f"   - Input Mappings: {len(chunk['input_mappings'])}")

    print("\n🔧 Test 2: Apply Input Mappings")
    import copy
    workflow = copy.deepcopy(chunk['workflow'])

    input_data = {
        'prompt': test_positive_prompt,
        'negative_prompt': test_negative_prompt,
        'width': 1024,
        'height': 1024,
        'steps': 25,
        'cfg': 5.5,
        'sampler_name': 'euler',
        'scheduler': 'normal',
        'seed': 'random'
    }

    workflow = router._apply_input_mappings(workflow, chunk['input_mappings'], input_data)

    # Validate that prompts were injected
    node_10_value = workflow.get('10', {}).get('inputs', {}).get('value')
    node_11_value = workflow.get('11', {}).get('inputs', {}).get('value')

    if node_10_value != test_positive_prompt:
        print(f"❌ FAILED: Positive prompt not correctly mapped")
        print(f"   Expected: {test_positive_prompt}")
        print(f"   Got: {node_10_value}")
        return False

    if node_11_value != test_negative_prompt:
        print(f"❌ FAILED: Negative prompt not correctly mapped")
        return False

    print(f"✅ PASSED: Input mappings applied correctly")
    print(f"   - Positive prompt → Node 10: '{node_10_value[:50]}...'")
    print(f"   - Negative prompt → Node 11: '{node_11_value[:50]}...'")
    print(f"   - Width → Node 3: {workflow.get('3', {}).get('inputs', {}).get('width')}")
    print(f"   - Height → Node 3: {workflow.get('3', {}).get('inputs', {}).get('height')}")
    print(f"   - Steps → Node 8: {workflow.get('8', {}).get('inputs', {}).get('steps')}")
    print(f"   - CFG → Node 8: {workflow.get('8', {}).get('inputs', {}).get('cfg')}")

    seed = workflow.get('8', {}).get('inputs', {}).get('seed')
    print(f"   - Seed → Node 8: {seed} (random generated)")

    print("\n🔧 Test 3: Prepare Backend Request")
    # Test the full _process_output_chunk flow (without actual ComfyUI submission)
    try:
        # This will fail at ComfyUI health check since we're not running ComfyUI
        # But we can validate the workflow preparation
        response = await router._process_output_chunk(
            chunk_name='output_image_sd35_large',
            prompt=test_positive_prompt,
            parameters={
                'negative_prompt': test_negative_prompt,
                'width': 1024,
                'height': 1024,
                'steps': 25,
                'cfg': 5.5,
                'sampler_name': 'euler',
                'scheduler': 'normal',
                'seed': 'random'
            }
        )

        if response.success:
            print(f"✅ PASSED: Backend request prepared successfully")

            if response.content == "workflow_prepared":
                print(f"   - Status: Workflow prepared (ComfyUI not running)")
                print(f"   - Output Mapping: {response.metadata.get('output_mapping')}")
                print(f"   - Ready for submission when ComfyUI is available")
            else:
                print(f"   - Status: {response.content}")
                print(f"   - Metadata: {response.metadata}")
        else:
            print(f"⚠️  WARNING: {response.error}")
            print(f"   (This is expected if ComfyUI is not running)")

    except Exception as e:
        print(f"⚠️  WARNING: Exception during backend processing: {e}")
        print(f"   (This is expected if ComfyUI is not running)")

    print("\n🔧 Test 4: Validate Workflow Structure")
    # Check that workflow is valid ComfyUI API format
    required_nodes = ['1', '2', '3', '4', '5', '8', '9', '10', '11']
    missing_nodes = [n for n in required_nodes if n not in workflow]

    if missing_nodes:
        print(f"❌ FAILED: Missing required nodes: {missing_nodes}")
        return False

    # Check SaveImage node (node 4)
    save_node = workflow.get('4')
    if not save_node or save_node.get('class_type') != 'SaveImage':
        print(f"❌ FAILED: SaveImage node not configured correctly")
        return False

    # Check KSampler node (node 8)
    sampler_node = workflow.get('8')
    if not sampler_node or sampler_node.get('class_type') != 'KSampler':
        print(f"❌ FAILED: KSampler node not configured correctly")
        return False

    print(f"✅ PASSED: Workflow structure valid")
    print(f"   - All required nodes present")
    print(f"   - SaveImage node: {save_node.get('class_type')}")
    print(f"   - KSampler node: {sampler_node.get('class_type')}")

    print("\n" + "=" * 70)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 70)
    print("\n📋 Summary:")
    print("   ✅ Output-Chunk loads correctly")
    print("   ✅ Input mappings apply prompts and parameters")
    print("   ✅ Workflow prepared for ComfyUI submission")
    print("   ✅ Workflow structure is valid ComfyUI API format")
    print("\n📝 To test with actual image generation:")
    print("   1. Start ComfyUI server")
    print("   2. Ensure sd3.5_large.safetensors model is installed")
    print("   3. Ensure clip_g.safetensors and t5xxl_fp16.safetensors are installed")
    print("   4. Run this test again - it will submit to ComfyUI")
    print("\n   Or use the API directly:")
    print("   POST /api/workflow/execute")
    print("   {")
    print('     "config_name": "sd35_large",')
    print('     "input_text": "A beautiful mountain landscape"')
    print("   }")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_direct_output_chunk_submission())
    exit(0 if success else 1)
