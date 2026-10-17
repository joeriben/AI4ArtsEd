"""
Test Output-Chunk System - Validate Structure and Backend Processing

This test validates:
1. Output-Chunk JSON structure
2. Backend router's ability to load and process Output-Chunks
3. Input mapping application
"""

import json
import asyncio
from pathlib import Path
from schemas.engine.backend_router import BackendRouter, BackendRequest, BackendType


def test_output_chunk_structure():
    """Test 1: Validate Output-Chunk JSON structure"""
    print("\n=== Test 1: Validate Output-Chunk Structure ===")

    chunk_path = Path(__file__).parent / "schemas" / "chunks" / "output_image_sd35_large.json"

    if not chunk_path.exists():
        print(f"❌ FAILED: Chunk file not found at {chunk_path}")
        return False

    with open(chunk_path, 'r', encoding='utf-8') as f:
        chunk = json.load(f)

    # Validate required fields
    required_fields = ['name', 'type', 'backend_type', 'media_type', 'workflow', 'input_mappings', 'output_mapping']
    missing = [f for f in required_fields if f not in chunk]

    if missing:
        print(f"❌ FAILED: Missing required fields: {missing}")
        return False

    # Validate type
    if chunk['type'] != 'output_chunk':
        print(f"❌ FAILED: Expected type='output_chunk', got '{chunk['type']}'")
        return False

    # Validate backend_type
    if chunk['backend_type'] != 'comfyui':
        print(f"❌ FAILED: Expected backend_type='comfyui', got '{chunk['backend_type']}'")
        return False

    # Validate workflow structure
    if not isinstance(chunk['workflow'], dict):
        print(f"❌ FAILED: workflow must be a dict")
        return False

    # Validate input_mappings
    if not isinstance(chunk['input_mappings'], dict):
        print(f"❌ FAILED: input_mappings must be a dict")
        return False

    # Check key mappings exist
    required_mappings = ['prompt']  # At minimum, prompt must be mappable
    for mapping in required_mappings:
        if mapping not in chunk['input_mappings']:
            print(f"❌ FAILED: input_mappings missing required mapping: {mapping}")
            return False

    # Validate output_mapping
    if not isinstance(chunk['output_mapping'], dict):
        print(f"❌ FAILED: output_mapping must be a dict")
        return False

    required_output_fields = ['node_id', 'output_type']
    missing_output = [f for f in required_output_fields if f not in chunk['output_mapping']]
    if missing_output:
        print(f"❌ FAILED: output_mapping missing fields: {missing_output}")
        return False

    print(f"✅ PASSED: Output-Chunk structure valid")
    print(f"   - Name: {chunk['name']}")
    print(f"   - Media Type: {chunk['media_type']}")
    print(f"   - Workflow Nodes: {len(chunk['workflow'])}")
    print(f"   - Input Mappings: {len(chunk['input_mappings'])}")
    return True


def test_backend_router_load_chunk():
    """Test 2: Validate backend_router can load Output-Chunk"""
    print("\n=== Test 2: Backend Router Load Chunk ===")

    router = BackendRouter()

    # Test loading the chunk
    chunk = router._load_output_chunk('output_image_sd35_large')

    if not chunk:
        print(f"❌ FAILED: Backend router could not load chunk")
        return False

    print(f"✅ PASSED: Backend router successfully loaded chunk")
    print(f"   - Chunk Name: {chunk['name']}")
    print(f"   - Backend Type: {chunk['backend_type']}")
    return True


def test_input_mappings_application():
    """Test 3: Validate input_mappings are correctly applied"""
    print("\n=== Test 3: Input Mappings Application ===")

    router = BackendRouter()
    chunk = router._load_output_chunk('output_image_sd35_large')

    if not chunk:
        print(f"❌ FAILED: Could not load chunk for testing")
        return False

    # Create test workflow (simplified copy)
    import copy
    test_workflow = copy.deepcopy(chunk['workflow'])

    # Test input data
    test_input_data = {
        'prompt': 'A beautiful sunset over mountains',
        'negative_prompt': 'blurry, bad quality',
        'width': 512,
        'height': 512,
        'steps': 20,
        'cfg': 7.0,
        'seed': 42
    }

    # Apply mappings
    mapped_workflow = router._apply_input_mappings(
        test_workflow,
        chunk['input_mappings'],
        test_input_data
    )

    # Validate that values were applied
    # Check prompt (node 10)
    if '10' in mapped_workflow:
        prompt_value = mapped_workflow['10'].get('inputs', {}).get('value')
        if prompt_value != test_input_data['prompt']:
            print(f"❌ FAILED: Prompt not correctly mapped")
            print(f"   Expected: {test_input_data['prompt']}")
            print(f"   Got: {prompt_value}")
            return False

    # Check width/height (node 3)
    if '3' in mapped_workflow:
        width = mapped_workflow['3'].get('inputs', {}).get('width')
        height = mapped_workflow['3'].get('inputs', {}).get('height')
        if width != test_input_data['width'] or height != test_input_data['height']:
            print(f"❌ FAILED: Width/Height not correctly mapped")
            return False

    # Check steps (node 8)
    if '8' in mapped_workflow:
        steps = mapped_workflow['8'].get('inputs', {}).get('steps')
        if steps != test_input_data['steps']:
            print(f"❌ FAILED: Steps not correctly mapped")
            return False

    print(f"✅ PASSED: Input mappings correctly applied")
    print(f"   - Prompt: '{test_input_data['prompt'][:50]}...'")
    print(f"   - Dimensions: {test_input_data['width']}x{test_input_data['height']}")
    print(f"   - Steps: {test_input_data['steps']}")
    return True


async def test_backend_request_preparation():
    """Test 4: Validate BackendRequest can be prepared for ComfyUI"""
    print("\n=== Test 4: Backend Request Preparation ===")

    router = BackendRouter()

    # Create a test request
    request = BackendRequest(
        backend_type=BackendType.COMFYUI,
        model="",  # Not used for ComfyUI
        prompt="A majestic mountain landscape at sunset",
        parameters={
            'output_chunk': 'output_image_sd35_large',
            'width': 768,
            'height': 768,
            'steps': 25,
            'cfg': 6.5
        },
        stream=False
    )

    # NOTE: We cannot actually submit to ComfyUI without a running server
    # But we can validate the workflow preparation

    chunk = router._load_output_chunk('output_image_sd35_large')
    if not chunk:
        print(f"❌ FAILED: Could not load chunk")
        return False

    import copy
    workflow = copy.deepcopy(chunk['workflow'])

    input_data = {'prompt': request.prompt, **request.parameters}
    workflow = router._apply_input_mappings(workflow, chunk['input_mappings'], input_data)

    # Validate workflow is ready
    if not workflow:
        print(f"❌ FAILED: Workflow not prepared")
        return False

    print(f"✅ PASSED: Backend request preparation successful")
    print(f"   - Workflow nodes: {len(workflow)}")
    print(f"   - Ready for ComfyUI submission")
    print(f"   - Note: Actual submission requires running ComfyUI server")
    return True


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("OUTPUT-CHUNK SYSTEM VALIDATION TESTS")
    print("=" * 60)

    results = []

    # Test 1: Structure validation
    results.append(("Structure Validation", test_output_chunk_structure()))

    # Test 2: Backend router load
    results.append(("Backend Router Load", test_backend_router_load_chunk()))

    # Test 3: Input mappings
    results.append(("Input Mappings Application", test_input_mappings_application()))

    # Test 4: Backend request (async)
    results.append(("Backend Request Preparation", asyncio.run(test_backend_request_preparation())))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Output-Chunk system is working correctly.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
