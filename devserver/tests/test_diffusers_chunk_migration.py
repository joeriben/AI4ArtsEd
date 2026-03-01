#!/usr/bin/env python3
"""
Comprehensive tests for the JSON→Python Diffusers chunk migration.

Tests cover:
1. Chunk structure validation (CHUNK_META, DEFAULTS, execute function)
2. Parameter resolution (uppercase/lowercase, defaults, None-safety)
3. Content marker correctness (must match schema_pipeline_routes.py consumers)
4. Fallback chain integrity
5. Backend unavailability handling
6. Router routing logic (Python chunks take priority over JSON)
7. Edge cases (CFG=0.0, empty prompts, missing params)
"""

import sys
import asyncio
import importlib
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Add devserver to path
devserver_path = Path(__file__).parent.parent
sys.path.insert(0, str(devserver_path))

# ── Test infrastructure ──

CHUNK_DIR = devserver_path / "schemas" / "chunks"
CONFIG_DIR = devserver_path / "schemas" / "configs" / "output"

CHUNK_NAMES = [
    "output_image_sd35_diffusers",
    "output_image_sd35_turbo_diffusers",
    "output_image_flux2_diffusers",
    "output_image_surrealizer_diffusers",
    "output_image_attention_cartography_diffusers",
    "output_image_feature_probing_diffusers",
]

# Expected content markers (must match schema_pipeline_routes.py consumers)
EXPECTED_MARKERS = {
    "output_image_sd35_diffusers": "diffusers_generated",
    "output_image_sd35_turbo_diffusers": "diffusers_generated",
    "output_image_flux2_diffusers": "diffusers_generated",
    "output_image_surrealizer_diffusers": "diffusers_generated",
    "output_image_attention_cartography_diffusers": "diffusers_attention_generated",
    "output_image_feature_probing_diffusers": "diffusers_probing_generated",
}

# Expected fallback chains
EXPECTED_FALLBACKS = {
    "output_image_sd35_diffusers": "output_image_sd35_large",
    "output_image_sd35_turbo_diffusers": "output_image_sd35_diffusers",
    "output_image_flux2_diffusers": "output_image_flux2",
    "output_image_surrealizer_diffusers": None,
    "output_image_attention_cartography_diffusers": None,
    "output_image_feature_probing_diffusers": None,
}

# Configs that reference our chunks
CONFIG_CHUNK_MAPPING = {
    "sd35_large.json": "output_image_sd35_diffusers",
    "sd35_large_turbo.json": "output_image_sd35_turbo_diffusers",
    "surrealization_diffusers.json": "output_image_surrealizer_diffusers",
    "attention_cartography_diffusers.json": "output_image_attention_cartography_diffusers",
    "feature_probing_diffusers.json": "output_image_feature_probing_diffusers",
}


def load_chunk_module(chunk_name: str):
    """Load a chunk module dynamically (same as _execute_python_chunk does)."""
    chunk_path = CHUNK_DIR / f"{chunk_name}.py"
    assert chunk_path.exists(), f"Chunk file not found: {chunk_path}"
    spec = importlib.util.spec_from_file_location(f"test_chunk_{chunk_name}", chunk_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_mock_backend(generate_image_returns=b'\x89PNG_fake_image_bytes',
                        is_available=True,
                        generate_fusion_returns=b'\x89PNG_fake_fusion_bytes',
                        attention_result=None,
                        probing_result=None):
    """Create a mock DiffusersClient."""
    mock = AsyncMock()
    mock.is_available = AsyncMock(return_value=is_available)
    mock.generate_image = AsyncMock(return_value=generate_image_returns)
    mock.generate_image_with_fusion = AsyncMock(return_value=generate_fusion_returns)

    if attention_result is None:
        attention_result = {
            'image_base64': 'base64_fake_attention_image',
            'seed': 42,
            'tokens': ['a', 'cat'],
            'word_groups': [{'word': 'a', 'tokens': [0]}, {'word': 'cat', 'tokens': [1]}],
            'tokens_t5': ['a', 'cat'],
            'word_groups_t5': [],
            'clip_token_count': 2,
            'attention_maps': {'layer_3': {'step_0': [[0.5]]}},
            'spatial_resolution': [64, 64],
            'image_resolution': [1024, 1024],
            'capture_layers': [3, 9, 17],
            'capture_steps': [0, 1, 2],
        }
    mock.generate_image_with_attention = AsyncMock(return_value=attention_result)

    if probing_result is None:
        probing_result = {
            'image_base64': 'base64_fake_probing_image',
            'seed': 42,
            'probing_data': {
                'encoder': 'all',
                'differences': [0.1, 0.2, 0.3],
                'top_dims': [10, 20, 30],
            },
        }
    mock.generate_image_with_probing = AsyncMock(return_value=probing_result)

    return mock


# ══════════════════════════════════════════════════════════════════════
# Test Suite 1: Chunk Structure Validation
# ══════════════════════════════════════════════════════════════════════

def test_all_chunk_files_exist():
    """All 6 Python chunk files exist."""
    for name in CHUNK_NAMES:
        path = CHUNK_DIR / f"{name}.py"
        assert path.exists(), f"Missing chunk: {path}"
    print("  PASS: All 6 Python chunk files exist")


def test_no_json_chunks_remain():
    """All 6 JSON chunk files have been deleted."""
    for name in CHUNK_NAMES:
        json_path = CHUNK_DIR / f"{name}.json"
        assert not json_path.exists(), f"JSON chunk still exists: {json_path}"
    print("  PASS: All 6 JSON chunk files deleted")


def test_chunk_meta_structure():
    """Every chunk has CHUNK_META with required fields."""
    required_fields = {'name', 'media_type', 'output_format', 'requires_gpu', 'gpu_vram_mb'}
    for name in CHUNK_NAMES:
        module = load_chunk_module(name)
        assert hasattr(module, 'CHUNK_META'), f"{name}: missing CHUNK_META"
        meta = module.CHUNK_META
        for field in required_fields:
            assert field in meta, f"{name}: CHUNK_META missing '{field}'"
        assert meta['name'] == name, f"{name}: CHUNK_META.name mismatch"
        assert 'fallback_chunk' in meta, f"{name}: CHUNK_META missing 'fallback_chunk' (can be None)"
    print("  PASS: All chunks have valid CHUNK_META")


def test_chunk_defaults_structure():
    """Every chunk has DEFAULTS dict with basic parameters."""
    for name in CHUNK_NAMES:
        module = load_chunk_module(name)
        assert hasattr(module, 'DEFAULTS'), f"{name}: missing DEFAULTS"
        defaults = module.DEFAULTS
        assert 'steps' in defaults, f"{name}: DEFAULTS missing 'steps'"
        assert 'cfg' in defaults, f"{name}: DEFAULTS missing 'cfg'"
    print("  PASS: All chunks have valid DEFAULTS")


def test_chunk_execute_function():
    """Every chunk has an async execute() function."""
    for name in CHUNK_NAMES:
        module = load_chunk_module(name)
        assert hasattr(module, 'execute'), f"{name}: missing execute()"
        assert asyncio.iscoroutinefunction(module.execute), f"{name}: execute() is not async"
    print("  PASS: All chunks have async execute()")


def test_fallback_chains():
    """Verify fallback chain matches expected values."""
    for name in CHUNK_NAMES:
        module = load_chunk_module(name)
        expected = EXPECTED_FALLBACKS[name]
        actual = module.CHUNK_META.get('fallback_chunk')
        assert actual == expected, f"{name}: fallback mismatch: expected={expected}, got={actual}"
    print("  PASS: All fallback chains correct")


def test_fallback_targets_exist():
    """Verify all non-None fallback chunks actually exist as files."""
    for name in CHUNK_NAMES:
        module = load_chunk_module(name)
        fallback = module.CHUNK_META.get('fallback_chunk')
        if fallback:
            # Fallback targets are either .py or .json
            py_path = CHUNK_DIR / f"{fallback}.py"
            json_path = CHUNK_DIR / f"{fallback}.json"
            assert py_path.exists() or json_path.exists(), \
                f"{name}: fallback '{fallback}' not found as .py or .json"
    print("  PASS: All fallback targets exist")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 2: Content Marker Verification
# ══════════════════════════════════════════════════════════════════════

def test_content_markers_match_consumers():
    """
    Verify content markers match what schema_pipeline_routes.py checks.
    This is the most critical test — wrong markers = silent data loss.
    """
    routes_path = devserver_path / "my_app" / "routes" / "schema_pipeline_routes.py"
    routes_content = routes_path.read_text()

    # Verify all expected markers are consumed somewhere in routes
    for marker in set(EXPECTED_MARKERS.values()):
        assert f"'{marker}'" in routes_content or f'"{marker}"' in routes_content, \
            f"Content marker '{marker}' not found in schema_pipeline_routes.py"

    print("  PASS: All content markers have matching consumers in routes")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 3: Parameter Resolution (the tricky part)
# ══════════════════════════════════════════════════════════════════════

def test_sd35_basic_generation():
    """SD3.5 chunk: basic generation with defaults."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="A beautiful sunset")
        )

    assert result['content_marker'] == 'diffusers_generated'
    assert 'image_data' in result
    assert result['model_id'] == 'stabilityai/stable-diffusion-3.5-large'
    assert result['media_type'] == 'image'
    mock_backend.generate_image.assert_called_once()
    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['steps'] == 25
    assert call_kwargs['cfg_scale'] == 4.5
    print("  PASS: SD3.5 basic generation")


def test_sd35_text1_fallback():
    """SD3.5 chunk: uses TEXT_1 when prompt is None."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(TEXT_1="A cat on a roof")
        )

    assert result['content_marker'] == 'diffusers_generated'
    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['prompt'] == "A cat on a roof"
    print("  PASS: SD3.5 TEXT_1 fallback")


def test_sd35_previous_output_fallback():
    """SD3.5 chunk: uses PREVIOUS_OUTPUT when prompt and TEXT_1 are None."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(PREVIOUS_OUTPUT="A dog in a park")
        )

    assert result['content_marker'] == 'diffusers_generated'
    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['prompt'] == "A dog in a park"
    print("  PASS: SD3.5 PREVIOUS_OUTPUT fallback")


def test_sd35_uppercase_params():
    """SD3.5 chunk: accepts UPPERCASE parameter names from output configs."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(
                prompt="test",
                STEPS=30,
                CFG=5.5,
                WIDTH=768,
                HEIGHT=768,
                NEGATIVE_PROMPT="ugly",
            )
        )

    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['steps'] == 30
    assert call_kwargs['cfg_scale'] == 5.5
    assert call_kwargs['width'] == 768
    assert call_kwargs['height'] == 768
    assert call_kwargs['negative_prompt'] == "ugly"
    print("  PASS: SD3.5 uppercase params")


def test_sd35_lowercase_overrides_uppercase():
    """SD3.5 chunk: lowercase params take priority over uppercase."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(
                prompt="test",
                steps=10, STEPS=30,
                cfg=3.0, CFG=5.5,
            )
        )

    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['steps'] == 10, "lowercase 'steps' should override uppercase 'STEPS'"
    assert call_kwargs['cfg_scale'] == 3.0, "lowercase 'cfg' should override uppercase 'CFG'"
    print("  PASS: SD3.5 lowercase overrides uppercase")


def test_turbo_cfg_zero():
    """SD3.5 Turbo: CFG=0.0 must not be treated as falsy."""
    module = load_chunk_module("output_image_sd35_turbo_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test")
        )

    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['cfg_scale'] == 0.0, f"Turbo CFG should be 0.0, got {call_kwargs['cfg_scale']}"
    assert call_kwargs['steps'] == 4, f"Turbo steps should be 4, got {call_kwargs['steps']}"
    print("  PASS: Turbo CFG=0.0 preserved")


def test_turbo_cfg_zero_from_uppercase():
    """SD3.5 Turbo: CFG=0.0 from uppercase param."""
    module = load_chunk_module("output_image_sd35_turbo_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test", CFG=0.0, STEPS=4)
        )

    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['cfg_scale'] == 0.0, f"CFG from uppercase should be 0.0, got {call_kwargs['cfg_scale']}"
    print("  PASS: Turbo CFG=0.0 from uppercase")


def test_sd35_triple_prompt():
    """SD3.5 chunk: forwards prompt_2/prompt_3 for CLIP-L/G optimization."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(
                prompt="base prompt",
                prompt_2="clip_l visual keywords",
                prompt_3="clip_g semantic scene",
            )
        )

    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['prompt_2'] == "clip_l visual keywords"
    assert call_kwargs['prompt_3'] == "clip_g semantic scene"
    print("  PASS: SD3.5 triple-prompt forwarding")


def test_sd35_lora_forwarding():
    """SD3.5 chunk: forwards LoRA list to backend."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()
    loras = [{'name': 'test_lora', 'weight': 0.8}]

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test", loras=loras)
        )

    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['loras'] == loras
    print("  PASS: SD3.5 LoRA forwarding")


def test_empty_prompt_raises():
    """All chunks: empty prompt raises ValueError."""
    for name in CHUNK_NAMES:
        module = load_chunk_module(name)
        mock_backend = create_mock_backend()

        with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
            try:
                asyncio.get_event_loop().run_until_complete(
                    module.execute(prompt="")
                )
                assert False, f"{name}: should have raised ValueError for empty prompt"
            except ValueError:
                pass  # Expected

    print("  PASS: All chunks raise ValueError on empty prompt")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 4: Backend Unavailability
# ══════════════════════════════════════════════════════════════════════

def test_backend_unavailable_raises():
    """All chunks: raise RuntimeError when backend is unavailable."""
    for name in CHUNK_NAMES:
        module = load_chunk_module(name)
        mock_backend = create_mock_backend(is_available=False)

        with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
            try:
                asyncio.get_event_loop().run_until_complete(
                    module.execute(prompt="test prompt")
                )
                assert False, f"{name}: should have raised RuntimeError"
            except RuntimeError as e:
                assert "not available" in str(e).lower()

    print("  PASS: All chunks raise RuntimeError when backend unavailable")


def test_empty_result_raises():
    """Standard chunks: raise RuntimeError when backend returns None/empty."""
    for name in ["output_image_sd35_diffusers", "output_image_sd35_turbo_diffusers", "output_image_flux2_diffusers"]:
        module = load_chunk_module(name)
        mock_backend = create_mock_backend(generate_image_returns=None)

        with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
            try:
                asyncio.get_event_loop().run_until_complete(
                    module.execute(prompt="test")
                )
                assert False, f"{name}: should have raised RuntimeError for empty result"
            except RuntimeError as e:
                assert "empty result" in str(e).lower()

    print("  PASS: Standard chunks raise on empty backend result")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 5: Surrealizer-Specific Tests
# ══════════════════════════════════════════════════════════════════════

def test_surrealizer_auto_alpha():
    """Surrealizer: auto-generates alpha when None."""
    module = load_chunk_module("output_image_surrealizer_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="surreal landscape")
        )

    call_kwargs = mock_backend.generate_image_with_fusion.call_args.kwargs
    alpha = call_kwargs['alpha_factor']
    assert 20 <= alpha <= 30, f"Auto-alpha should be 20-30, got {alpha}"
    assert call_kwargs['fusion_strategy'] == 'dual_alpha'
    print("  PASS: Surrealizer auto-alpha")


def test_surrealizer_explicit_params():
    """Surrealizer: respects explicit alpha/strategy/t5_prompt."""
    module = load_chunk_module("output_image_surrealizer_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(
                prompt="surreal landscape",
                alpha_factor=15.0,
                fusion_strategy="normalized",
                t5_prompt="expanded T5 prompt",
            )
        )

    call_kwargs = mock_backend.generate_image_with_fusion.call_args.kwargs
    assert call_kwargs['alpha_factor'] == 15.0
    assert call_kwargs['fusion_strategy'] == 'normalized'
    assert call_kwargs['t5_prompt'] == 'expanded T5 prompt'
    print("  PASS: Surrealizer explicit params")


def test_surrealizer_no_fallback():
    """Surrealizer: fallback_chunk is None (no ComfyUI equivalent)."""
    module = load_chunk_module("output_image_surrealizer_diffusers")
    assert module.CHUNK_META['fallback_chunk'] is None
    print("  PASS: Surrealizer no fallback")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 6: Attention Cartography Tests
# ══════════════════════════════════════════════════════════════════════

def test_attention_basic():
    """Attention Cartography: returns correct structure."""
    module = load_chunk_module("output_image_attention_cartography_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="a cat")
        )

    assert result['content_marker'] == 'diffusers_attention_generated'
    assert 'image_data' in result
    assert 'attention_data' in result
    ad = result['attention_data']
    assert 'tokens' in ad
    assert 'attention_maps' in ad
    assert 'spatial_resolution' in ad
    assert 'capture_layers' in ad
    assert 'capture_steps' in ad
    print("  PASS: Attention Cartography basic")


def test_attention_default_layers():
    """Attention Cartography: defaults to layers [3, 9, 17]."""
    module = load_chunk_module("output_image_attention_cartography_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test")
        )

    call_kwargs = mock_backend.generate_image_with_attention.call_args.kwargs
    assert call_kwargs['capture_layers'] == [3, 9, 17]
    assert call_kwargs['capture_every_n_steps'] == 1
    print("  PASS: Attention default layers")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 7: Feature Probing Tests
# ══════════════════════════════════════════════════════════════════════

def test_probing_basic():
    """Feature Probing: returns correct structure."""
    module = load_chunk_module("output_image_feature_probing_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="a red car", prompt_b="a blue car")
        )

    assert result['content_marker'] == 'diffusers_probing_generated'
    assert 'image_data' in result
    assert 'probing_data' in result
    print("  PASS: Feature Probing basic")


def test_probing_with_transfer():
    """Feature Probing: forwards transfer_dims to backend."""
    module = load_chunk_module("output_image_feature_probing_diffusers")
    mock_backend = create_mock_backend()
    transfer = [10, 20, 30]

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="a", prompt_b="b", transfer_dims=transfer)
        )

    call_kwargs = mock_backend.generate_image_with_probing.call_args.kwargs
    assert call_kwargs['transfer_dims'] == transfer
    assert call_kwargs['encoder'] == 'all'
    print("  PASS: Feature Probing with transfer_dims")


def test_probing_error_handling():
    """Feature Probing: raises on error result from backend."""
    module = load_chunk_module("output_image_feature_probing_diffusers")
    mock_backend = create_mock_backend()
    mock_backend.generate_image_with_probing = AsyncMock(
        return_value={'error': 'Encoder mismatch'}
    )

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        try:
            asyncio.get_event_loop().run_until_complete(
                module.execute(prompt="a", prompt_b="b")
            )
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Encoder mismatch" in str(e)

    print("  PASS: Feature Probing error handling")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 8: Flux2 Tests
# ══════════════════════════════════════════════════════════════════════

def test_flux2_basic():
    """Flux2: correct model_id and pipeline_class."""
    module = load_chunk_module("output_image_flux2_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test")
        )

    assert result['model_id'] == 'black-forest-labs/FLUX.2-dev'
    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['pipeline_class'] == 'Flux2Pipeline'
    assert call_kwargs['steps'] == 20
    assert call_kwargs['cfg_scale'] == 1
    print("  PASS: Flux2 basic generation")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 9: Output Config Verification
# ══════════════════════════════════════════════════════════════════════

def test_output_configs_point_to_correct_chunks():
    """Output configs reference correct chunk names."""
    import json

    for config_name, expected_chunk in CONFIG_CHUNK_MAPPING.items():
        config_path = CONFIG_DIR / config_name
        assert config_path.exists(), f"Config not found: {config_path}"
        with open(config_path) as f:
            config = json.load(f)
        actual_chunk = config['parameters']['OUTPUT_CHUNK']
        assert actual_chunk == expected_chunk, \
            f"{config_name}: OUTPUT_CHUNK={actual_chunk}, expected={expected_chunk}"

    print("  PASS: All output configs point to correct chunks")


def test_sd35_config_backend_type():
    """sd35_large.json has backend_type=diffusers after migration."""
    import json

    config_path = CONFIG_DIR / "sd35_large.json"
    with open(config_path) as f:
        config = json.load(f)

    assert config['meta']['backend_type'] == 'diffusers', \
        f"sd35_large.json backend_type should be 'diffusers', got '{config['meta']['backend_type']}'"
    assert config['parameters']['OUTPUT_CHUNK'] == 'output_image_sd35_diffusers'
    print("  PASS: sd35_large.json backend_type=diffusers")


def test_no_circular_fallback():
    """No ComfyUI chunk references a Diffusers chunk as fallback (circular)."""
    import json

    for json_file in CHUNK_DIR.glob("*.json"):
        with open(json_file) as f:
            chunk = json.load(f)
        fallback = chunk.get('meta', {}).get('fallback_chunk', '')
        if fallback and 'diffusers' in fallback:
            assert False, f"{json_file.name}: circular fallback to Diffusers chunk '{fallback}'"

    print("  PASS: No circular fallback references")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 10: Router Logic Verification
# ══════════════════════════════════════════════════════════════════════

def test_router_no_diffusers_references():
    """backend_router.py has no references to removed methods."""
    router_path = devserver_path / "schemas" / "engine" / "backend_router.py"
    content = router_path.read_text()
    assert '_process_diffusers_chunk' not in content, "Dangling reference to _process_diffusers_chunk"
    assert '_get_diffusers_compatible_chunk' not in content, "Dangling reference to _get_diffusers_compatible_chunk"
    print("  PASS: No dangling method references in router")


def test_router_no_diffusers_backend_type_branch():
    """backend_router.py has no 'elif backend_type == diffusers' branch."""
    router_path = devserver_path / "schemas" / "engine" / "backend_router.py"
    content = router_path.read_text()
    # Check that the diffusers branch was removed from the routing logic
    assert "backend_type == 'diffusers'" not in content, \
        "The 'elif backend_type == diffusers' branch should have been removed"
    print("  PASS: No diffusers backend_type routing branch")


def test_router_fallback_logic_present():
    """Router _process_output_chunk has the new fallback logic for Python chunks."""
    router_path = devserver_path / "schemas" / "engine" / "backend_router.py"
    content = router_path.read_text()
    assert 'CHUNK_META' in content, "Fallback logic should reference CHUNK_META"
    assert 'fallback_chunk' in content, "Fallback logic should check fallback_chunk"
    assert "sys.modules.get(f\"chunk_{chunk_name}\")" in content, \
        "Fallback should read module from sys.modules"
    print("  PASS: Router fallback logic present")


def test_reference_chunks_untouched():
    """Reference Python chunks (concept_algebra, denoising_archaeology) still exist."""
    for name in ['output_image_concept_algebra_diffusers', 'output_image_denoising_archaeology_diffusers']:
        path = CHUNK_DIR / f"{name}.py"
        assert path.exists(), f"Reference chunk missing: {path}"
        module = load_chunk_module(name)
        assert hasattr(module, 'CHUNK_META')
        assert hasattr(module, 'execute')
    print("  PASS: Reference chunks untouched")


# ══════════════════════════════════════════════════════════════════════
# Test Suite 11: Seed Handling
# ══════════════════════════════════════════════════════════════════════

def test_seed_random_string():
    """Chunks: seed='random' generates a valid integer seed."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test", seed='random')
        )

    assert isinstance(result['seed'], int)
    assert 0 <= result['seed'] <= 2**32 - 1
    print("  PASS: seed='random' handling")


def test_seed_explicit():
    """Chunks: explicit seed is forwarded."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test", seed=12345)
        )

    assert result['seed'] == 12345
    call_kwargs = mock_backend.generate_image.call_args.kwargs
    assert call_kwargs['seed'] == 12345
    print("  PASS: Explicit seed forwarding")


def test_seed_minus_one():
    """Chunks: seed=-1 generates random seed."""
    module = load_chunk_module("output_image_sd35_diffusers")
    mock_backend = create_mock_backend()

    with patch('my_app.services.diffusers_backend.get_diffusers_backend', return_value=mock_backend):
        result = asyncio.get_event_loop().run_until_complete(
            module.execute(prompt="test", seed=-1)
        )

    assert isinstance(result['seed'], int)
    assert result['seed'] != -1
    print("  PASS: seed=-1 → random")


# ══════════════════════════════════════════════════════════════════════
# Run all tests
# ══════════════════════════════════════════════════════════════════════

def run_all_tests():
    """Run all test suites."""
    tests = [
        # Suite 1: Structure
        ("1.1", "Chunk files exist", test_all_chunk_files_exist),
        ("1.2", "JSON chunks deleted", test_no_json_chunks_remain),
        ("1.3", "CHUNK_META structure", test_chunk_meta_structure),
        ("1.4", "DEFAULTS structure", test_chunk_defaults_structure),
        ("1.5", "execute() function", test_chunk_execute_function),
        ("1.6", "Fallback chains", test_fallback_chains),
        ("1.7", "Fallback targets exist", test_fallback_targets_exist),
        # Suite 2: Content markers
        ("2.1", "Content markers match consumers", test_content_markers_match_consumers),
        # Suite 3: Parameters
        ("3.1", "SD3.5 basic generation", test_sd35_basic_generation),
        ("3.2", "SD3.5 TEXT_1 fallback", test_sd35_text1_fallback),
        ("3.3", "SD3.5 PREVIOUS_OUTPUT fallback", test_sd35_previous_output_fallback),
        ("3.4", "SD3.5 uppercase params", test_sd35_uppercase_params),
        ("3.5", "Lowercase overrides uppercase", test_sd35_lowercase_overrides_uppercase),
        ("3.6", "Turbo CFG=0.0 preserved", test_turbo_cfg_zero),
        ("3.7", "Turbo CFG=0.0 from uppercase", test_turbo_cfg_zero_from_uppercase),
        ("3.8", "SD3.5 triple-prompt", test_sd35_triple_prompt),
        ("3.9", "SD3.5 LoRA forwarding", test_sd35_lora_forwarding),
        ("3.10", "Empty prompt raises", test_empty_prompt_raises),
        # Suite 4: Backend unavailability
        ("4.1", "Backend unavailable raises", test_backend_unavailable_raises),
        ("4.2", "Empty result raises", test_empty_result_raises),
        # Suite 5: Surrealizer
        ("5.1", "Surrealizer auto-alpha", test_surrealizer_auto_alpha),
        ("5.2", "Surrealizer explicit params", test_surrealizer_explicit_params),
        ("5.3", "Surrealizer no fallback", test_surrealizer_no_fallback),
        # Suite 6: Attention
        ("6.1", "Attention basic", test_attention_basic),
        ("6.2", "Attention default layers", test_attention_default_layers),
        # Suite 7: Probing
        ("7.1", "Probing basic", test_probing_basic),
        ("7.2", "Probing with transfer_dims", test_probing_with_transfer),
        ("7.3", "Probing error handling", test_probing_error_handling),
        # Suite 8: Flux2
        ("8.1", "Flux2 basic", test_flux2_basic),
        # Suite 9: Configs
        ("9.1", "Config→Chunk mapping", test_output_configs_point_to_correct_chunks),
        ("9.2", "sd35_large.json backend_type", test_sd35_config_backend_type),
        ("9.3", "No circular fallback", test_no_circular_fallback),
        # Suite 10: Router
        ("10.1", "No dangling method refs", test_router_no_diffusers_references),
        ("10.2", "No diffusers routing branch", test_router_no_diffusers_backend_type_branch),
        ("10.3", "Fallback logic present", test_router_fallback_logic_present),
        ("10.4", "Reference chunks untouched", test_reference_chunks_untouched),
        # Suite 11: Seeds
        ("11.1", "seed='random' handling", test_seed_random_string),
        ("11.2", "Explicit seed forwarding", test_seed_explicit),
        ("11.3", "seed=-1 → random", test_seed_minus_one),
    ]

    print("=" * 70)
    print("Diffusers Chunk Migration — Comprehensive Test Suite")
    print("=" * 70)

    passed = 0
    failed = 0
    errors = []

    for test_id, name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_id, name, str(e)))
            print(f"  FAIL [{test_id}] {name}: {e}")

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)

    if errors:
        print("\nFailed tests:")
        for test_id, name, err in errors:
            print(f"  [{test_id}] {name}")
            print(f"         {err}")
        return 1
    else:
        print("\nAll tests passed!")
        return 0


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
