"""
Test SD3.5 Large Pipeline with Output-Chunk System

This test validates the complete pipeline:
1. Config loading (sd35_large.json)
2. Pipeline execution (single_text_media_generation)
3. Chunk loading (output_image.json)
4. Output-Chunk loading (output_image_sd35_large.json)
5. Parameter application
"""

import json
import asyncio
from pathlib import Path
from schemas.engine.config_loader import config_loader
from schemas.engine.chunk_builder import ChunkBuilder
from schemas.engine.backend_router import BackendRouter


def test_config_loading():
    """Test 1: Verify sd35_large config loads correctly"""
    print("\n=== Test 1: Config Loading ===")

    config_path = Path("schemas/configs/sd35_large.json")

    if not config_path.exists():
        print(f"❌ FAILED: Config file not found at {config_path}")
        return False

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Validate required fields
    required_fields = ['pipeline', 'name', 'parameters']
    missing = [f for f in required_fields if f not in config]

    if missing:
        print(f"❌ FAILED: Missing required fields: {missing}")
        return False

    # Validate OUTPUT_CHUNK parameter
    if 'OUTPUT_CHUNK' not in config['parameters']:
        print(f"❌ FAILED: OUTPUT_CHUNK parameter missing")
        return False

    output_chunk = config['parameters']['OUTPUT_CHUNK']
    if output_chunk != 'output_image_sd35_large':
        print(f"❌ FAILED: OUTPUT_CHUNK should be 'output_image_sd35_large', got '{output_chunk}'")
        return False

    # Validate explicit parameters
    required_params = ['WIDTH', 'HEIGHT', 'STEPS', 'CFG', 'NEGATIVE_PROMPT', 'SAMPLER', 'SCHEDULER', 'SEED']
    missing_params = [p for p in required_params if p not in config['parameters']]

    if missing_params:
        print(f"❌ FAILED: Missing explicit parameters: {missing_params}")
        return False

    print(f"✅ PASSED: Config loaded successfully")
    print(f"   - Output Chunk: {output_chunk}")
    print(f"   - Resolution: {config['parameters']['WIDTH']}x{config['parameters']['HEIGHT']}")
    print(f"   - Steps: {config['parameters']['STEPS']}")
    print(f"   - CFG: {config['parameters']['CFG']}")
    print(f"   - Negative Prompt: {config['parameters']['NEGATIVE_PROMPT'][:50]}...")
    return True


def test_pipeline_definition():
    """Test 2: Verify single_text_media_generation pipeline uses output_image chunk"""
    print("\n=== Test 2: Pipeline Definition ===")

    pipeline_path = Path("schemas/pipelines/single_text_media_generation.json")

    if not pipeline_path.exists():
        print(f"❌ FAILED: Pipeline file not found")
        return False

    with open(pipeline_path, 'r') as f:
        pipeline = json.load(f)

    # Validate chunks
    if 'chunks' not in pipeline:
        print(f"❌ FAILED: No chunks defined in pipeline")
        return False

    chunks = pipeline['chunks']
    if 'output_image' not in chunks:
        print(f"❌ FAILED: 'output_image' chunk not in pipeline")
        print(f"   Found chunks: {chunks}")
        return False

    print(f"✅ PASSED: Pipeline definition correct")
    print(f"   - Chunks: {chunks}")
    return True


def test_output_image_chunk():
    """Test 3: Verify output_image chunk exists and has OUTPUT_CHUNK parameter"""
    print("\n=== Test 3: Output Image Chunk ===")

    chunk_path = Path("schemas/chunks/output_image.json")

    if not chunk_path.exists():
        print(f"❌ FAILED: output_image.json chunk not found")
        return False

    with open(chunk_path, 'r') as f:
        chunk = json.load(f)

    # Validate backend_type
    if chunk.get('backend_type') != 'comfyui':
        print(f"❌ FAILED: backend_type should be 'comfyui'")
        return False

    # Validate OUTPUT_CHUNK placeholder
    if 'parameters' not in chunk or 'output_chunk' not in chunk['parameters']:
        print(f"❌ FAILED: output_chunk parameter not defined")
        return False

    output_chunk_placeholder = chunk['parameters']['output_chunk']
    if output_chunk_placeholder != '{{OUTPUT_CHUNK}}':
        print(f"❌ FAILED: output_chunk should use {{{{OUTPUT_CHUNK}}}} placeholder")
        return False

    print(f"✅ PASSED: output_image chunk configured correctly")
    print(f"   - Backend: {chunk['backend_type']}")
    print(f"   - Output Chunk Placeholder: {output_chunk_placeholder}")
    return True


def test_chunk_builder_parameter_replacement():
    """Test 4: Verify ChunkBuilder replaces OUTPUT_CHUNK placeholder"""
    print("\n=== Test 4: ChunkBuilder Parameter Replacement ===")

    try:
        # Initialize config_loader
        schemas_path = Path("schemas")
        config_loader.initialize(schemas_path)

        # Get sd35_large config
        resolved_config = config_loader.get_config('sd35_large')

        if not resolved_config:
            print(f"❌ FAILED: Could not load sd35_large config")
            return False

        # Initialize ChunkBuilder
        chunk_builder = ChunkBuilder(schemas_path)

        # Build output_image chunk with sd35_large config
        chunk_context = {
            'input_text': 'A beautiful mountain landscape',
            'previous_output': 'An artistic depiction of majestic mountains at sunset',
            'user_input': 'A beautiful mountain landscape'
        }

        chunk_request = chunk_builder.build_chunk(
            chunk_name='output_image',
            resolved_config=resolved_config,
            context=chunk_context,
        )

        # Validate output_chunk parameter is set
        if 'output_chunk' not in chunk_request['parameters']:
            print(f"❌ FAILED: output_chunk not in chunk_request parameters")
            print(f"   Parameters: {chunk_request['parameters'].keys()}")
            return False

        output_chunk_value = chunk_request['parameters']['output_chunk']
        if output_chunk_value != 'output_image_sd35_large':
            print(f"❌ FAILED: output_chunk should be 'output_image_sd35_large', got '{output_chunk_value}'")
            return False

        # Validate other parameters are present
        expected_params = ['width', 'height', 'steps', 'cfg', 'negative_prompt']
        missing_params = [p for p in expected_params if p not in chunk_request['parameters']]

        if missing_params:
            print(f"❌ FAILED: Missing parameters after replacement: {missing_params}")
            return False

        print(f"✅ PASSED: ChunkBuilder parameter replacement successful")
        print(f"   - output_chunk: {output_chunk_value}")
        print(f"   - width: {chunk_request['parameters'].get('width')}")
        print(f"   - height: {chunk_request['parameters'].get('height')}")
        print(f"   - steps: {chunk_request['parameters'].get('steps')}")
        print(f"   - cfg: {chunk_request['parameters'].get('cfg')}")
        return True

    except Exception as e:
        print(f"❌ FAILED: Exception during chunk building: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_backend_router_output_chunk_detection():
    """Test 5: Verify BackendRouter detects output_chunk parameter"""
    print("\n=== Test 5: BackendRouter Output-Chunk Detection ===")

    try:
        router = BackendRouter()

        # Simulate a request with output_chunk parameter
        test_parameters = {
            'output_chunk': 'output_image_sd35_large',
            'width': 1024,
            'height': 1024,
            'steps': 25,
            'cfg': 5.5
        }

        # Load the Output-Chunk
        chunk = router._load_output_chunk('output_image_sd35_large')

        if not chunk:
            print(f"❌ FAILED: Backend router could not load Output-Chunk")
            return False

        # Verify it's the correct chunk
        if chunk['name'] != 'output_image_sd35_large':
            print(f"❌ FAILED: Wrong chunk loaded")
            return False

        print(f"✅ PASSED: BackendRouter Output-Chunk detection successful")
        print(f"   - Chunk Name: {chunk['name']}")
        print(f"   - Media Type: {chunk['media_type']}")
        print(f"   - Workflow Nodes: {len(chunk['workflow'])}")
        return True

    except Exception as e:
        print(f"❌ FAILED: Exception during backend routing: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("SD3.5 LARGE PIPELINE WITH OUTPUT-CHUNK SYSTEM - VALIDATION TESTS")
    print("=" * 70)

    results = []

    # Test 1: Config loading
    results.append(("Config Loading", test_config_loading()))

    # Test 2: Pipeline definition
    results.append(("Pipeline Definition", test_pipeline_definition()))

    # Test 3: Output image chunk
    results.append(("Output Image Chunk", test_output_image_chunk()))

    # Test 4: ChunkBuilder parameter replacement
    results.append(("ChunkBuilder Parameter Replacement", test_chunk_builder_parameter_replacement()))

    # Test 5: BackendRouter (async)
    results.append(("BackendRouter Output-Chunk Detection", asyncio.run(test_backend_router_output_chunk_detection())))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! SD3.5 Large pipeline is ready for use.")
        print("\n📝 Next Steps:")
        print("   1. Start ComfyUI server")
        print("   2. Test with actual image generation:")
        print("      python test_refactored_system.py --config sd35_large --input 'A beautiful sunset'")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
