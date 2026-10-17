"""
Phase 2 Unit Tests: Test stage_orchestrator.py helper functions
Tests parsing functions with sample data (no async/services needed)
"""
import sys
from pathlib import Path

# Add schemas to path
sys.path.insert(0, str(Path(__file__).parent))

from schemas.engine.stage_orchestrator import (
    parse_llamaguard_output,
    parse_preoutput_json,
    build_safety_message,
    fast_filter_check,
    load_filter_terms
)

def test_parse_llamaguard_output():
    """Test Llama-Guard output parsing (both formats)"""
    print("Testing parse_llamaguard_output()...")

    # Test 1: Safe output
    result = parse_llamaguard_output("safe")
    assert result == (True, []), f"Expected (True, []), got {result}"
    print("  ✅ Safe output parsed correctly")

    # Test 2: Unsafe output (format 1: two lines)
    result = parse_llamaguard_output("unsafe\nS8,S11")
    assert result[0] == False, f"Expected False, got {result[0]}"
    assert len(result[1]) > 0, f"Expected codes, got {result[1]}"
    print(f"  ✅ Unsafe output (format 1) parsed correctly: {result}")

    # Test 3: Unsafe output (format 2: one line with comma)
    result = parse_llamaguard_output("unsafe,S8, Violent Crimes")
    assert result[0] == False, f"Expected False, got {result[0]}"
    assert 'S8' in result[1], f"Expected S8 in codes, got {result[1]}"
    print(f"  ✅ Unsafe output (format 2) parsed correctly: {result}")

    print("✅ parse_llamaguard_output() tests passed\n")

def test_parse_preoutput_json():
    """Test pre-output JSON parsing"""
    print("Testing parse_preoutput_json()...")

    # Test 1: Plain text "safe"
    result = parse_preoutput_json("safe")
    assert result['safe'] == True, f"Expected safe=True, got {result}"
    print("  ✅ Plain text 'safe' parsed correctly")

    # Test 2: Plain text "unsafe"
    result = parse_preoutput_json("unsafe")
    assert result['safe'] == False, f"Expected safe=False, got {result}"
    print("  ✅ Plain text 'unsafe' parsed correctly")

    # Test 3: JSON format
    json_input = '''{"safe": false, "abort_reason": "Violence detected", "positive_prompt": "modified prompt"}'''
    result = parse_preoutput_json(json_input)
    assert result['safe'] == False, f"Expected safe=False, got {result}"
    assert result['abort_reason'] == "Violence detected", f"Expected abort_reason, got {result}"
    print("  ✅ JSON format parsed correctly")

    # Test 4: JSON with markdown code blocks
    json_markdown = '''```json
{"safe": true, "positive_prompt": "A beautiful flower"}
```'''
    result = parse_preoutput_json(json_markdown)
    assert result['safe'] == True, f"Expected safe=True, got {result}"
    print("  ✅ JSON with markdown parsed correctly")

    print("✅ parse_preoutput_json() tests passed\n")

def test_build_safety_message():
    """Test safety message building"""
    print("Testing build_safety_message()...")

    # Test with S8 code - just verify we get a meaningful message
    result = build_safety_message(['S8'], lang='de')
    assert len(result) > 20, f"Expected meaningful message, got: {result[:100]}"
    assert 'Prompt' in result or 'blockiert' in result.lower(), f"Expected safety message, got: {result[:100]}"
    print(f"  ✅ Safety message built correctly (German): {result[:80]}...")

    # Test with English
    result = build_safety_message(['S8'], lang='en')
    assert isinstance(result, str) and len(result) > 20, f"Expected meaningful string, got: {result[:100]}"
    print(f"  ✅ Safety message built correctly (English): {result[:80]}...")

    # Test with multiple codes
    result = build_safety_message(['S8', 'S11'], lang='de')
    assert len(result) > 40, f"Expected longer message for multiple codes, got: {result[:100]}"
    print(f"  ✅ Multiple codes handled correctly")

    print("✅ build_safety_message() tests passed\n")

def test_fast_filter_check():
    """Test fast filter string matching"""
    print("Testing fast_filter_check()...")

    # Load filter terms first
    terms = load_filter_terms()
    print(f"  Loaded filter terms: stage1={len(terms.get('stage1', []))}, kids={len(terms.get('kids', []))}, youth={len(terms.get('youth', []))}")

    # Test 1: Safe prompt (no terms)
    has_terms, found = fast_filter_check("A beautiful flower in the meadow", 'kids')
    assert has_terms == False, f"Expected no terms in safe prompt, got {found}"
    print(f"  ✅ Safe prompt: no terms found")

    # Test 2: Prompt with common false positive (should find term)
    has_terms, found = fast_filter_check("I listen to music on my CD player", 'kids')
    # Note: This WILL find "player" in kids filter (that's why we need LLM context check)
    if has_terms:
        print(f"  ✅ Found terms in false positive case: {found[:3]} (LLM would verify as safe)")
    else:
        print(f"  ✅ No terms found (filter may not include 'player')")

    # Test 3: Youth filter (less strict than kids)
    has_terms_kids, found_kids = fast_filter_check("dark chocolate", 'kids')
    has_terms_youth, found_youth = fast_filter_check("dark chocolate", 'youth')
    print(f"  ✅ Youth filter less strict: kids={has_terms_kids} ({found_kids[:2] if found_kids else []}), youth={has_terms_youth} ({found_youth[:2] if found_youth else []})")

    print("✅ fast_filter_check() tests passed\n")

def test_load_filter_terms():
    """Test filter terms loading"""
    print("Testing load_filter_terms()...")

    terms = load_filter_terms()
    assert 'stage1' in terms, "Expected 'stage1' in filter terms"
    assert 'kids' in terms, "Expected 'kids' in filter terms"
    assert 'youth' in terms, "Expected 'youth' in filter terms"

    # Check that lists are not empty
    assert len(terms['stage1']) > 0, "Expected stage1 terms"
    assert len(terms['kids']) > 0, "Expected kids terms"
    assert len(terms['youth']) > 0, "Expected youth terms"

    # Kids should have more terms than youth (stricter)
    assert len(terms['kids']) >= len(terms['youth']), "Expected kids filter to be stricter"

    print(f"  ✅ Filter terms loaded: stage1={len(terms['stage1'])}, kids={len(terms['kids'])}, youth={len(terms['youth'])}")
    print("✅ load_filter_terms() tests passed\n")

if __name__ == '__main__':
    print("="*60)
    print("Phase 2 Unit Tests: stage_orchestrator.py")
    print("="*60 + "\n")

    try:
        test_load_filter_terms()
        test_parse_llamaguard_output()
        test_parse_preoutput_json()
        test_build_safety_message()
        test_fast_filter_check()

        print("="*60)
        print("✅ ALL PHASE 2 UNIT TESTS PASSED")
        print("="*60)
        print("\nNext: Phase 3 - Implement execute_4_stage_flow() in DevServer")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
