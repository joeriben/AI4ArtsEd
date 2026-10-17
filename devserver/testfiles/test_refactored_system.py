#!/usr/bin/env python3
"""
Test script for refactored architecture
Tests: config_loader, pipeline_executor
"""
import sys
from pathlib import Path

# Add devserver to path
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.config_loader import config_loader
from schemas.engine.pipeline_executor import executor

def test_config_loader():
    """Test config loading"""
    print("\n" + "="*60)
    print("TEST 1: Config Loader")
    print("="*60)

    schemas_path = Path(__file__).parent / "schemas"
    config_loader.initialize(schemas_path)

    # Test loading pipelines
    pipelines = config_loader.list_pipelines()
    print(f"✓ Pipelines loaded: {len(pipelines)}")
    for pipeline_name in pipelines:
        pipeline = config_loader.get_pipeline(pipeline_name)
        print(f"  - {pipeline_name}: {len(pipeline.chunks)} chunks")

    # Test loading configs
    configs = config_loader.list_configs()
    print(f"\n✓ Configs loaded: {len(configs)}")
    for config_name in configs:
        resolved = config_loader.get_config(config_name)
        print(f"  - {config_name}")
        print(f"    Pipeline: {resolved.pipeline_name}")
        print(f"    Chunks: {resolved.chunks}")
        from schemas.engine.config_loader import resolve_context_language
        ctx_str = resolve_context_language(resolved.context)
        print(f"    Context: {ctx_str[:60] if ctx_str else 'N/A'}...")
        print(f"    Display: {resolved.display_name.get('en', 'N/A')}")

    return True

def test_pipeline_info():
    """Test getting pipeline/config info"""
    print("\n" + "="*60)
    print("TEST 2: Pipeline Executor - Info Methods")
    print("="*60)

    schemas_path = Path(__file__).parent / "schemas"
    executor.config_loader.initialize(schemas_path)
    executor._initialized = True

    # Test get_available_configs
    available = executor.get_available_configs()
    print(f"✓ Available configs: {len(available)}")
    print(f"  {', '.join(available)}")

    # Test get_config_info
    if available:
        test_config = available[0]
        info = executor.get_config_info(test_config)
        if info:
            print(f"\n✓ Config info for '{test_config}':")
            print(f"  Display name (en): {info['display_name'].get('en')}")
            print(f"  Pipeline: {info['pipeline_name']}")
            print(f"  Chunks: {info['chunks']}")

    # Test backward compatibility
    schemas = executor.get_available_schemas()
    print(f"\n✓ Backward compatibility (get_available_schemas): {len(schemas)} items")

    return True

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("REFACTORED ARCHITECTURE TEST SUITE")
    print("="*60)

    try:
        # Test 1: Config Loader
        if not test_config_loader():
            print("\n❌ Config Loader test FAILED")
            return False

        # Test 2: Pipeline Info
        if not test_pipeline_info():
            print("\n❌ Pipeline Info test FAILED")
            return False

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nNext steps:")
        print("1. Test actual pipeline execution (requires Ollama running)")
        print("2. Test with real configs (dada.json, overdrive.json)")
        print("3. Update workflow_routes.py to use new executor")
        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
