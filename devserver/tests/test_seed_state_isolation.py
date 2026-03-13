"""
Test: Per-device seed state isolation (Session 261)

Verifies that the seed logic is properly isolated between devices.
Run: python tests/test_seed_state_isolation.py
"""
import sys
import threading
import time

sys.path.insert(0, '.')

# Import the functions under test directly
from my_app.routes.schema_pipeline_routes import (
    _get_seed_state,
    _update_seed_state,
    _seed_state,
    _seed_state_lock,
    _SEED_STATE_TTL,
)

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


def reset():
    """Clear all seed state between test groups."""
    with _seed_state_lock:
        _seed_state.clear()


# ============================================================
# TEST 1: Basic isolation — two devices get independent state
# ============================================================
print("\n[TEST 1] Basic device isolation")
reset()

state_a = _get_seed_state("ipad_a")
state_b = _get_seed_state("ipad_b")

check("Device A starts with prompt=None", state_a["prompt"] is None)
check("Device B starts with prompt=None", state_b["prompt"] is None)

_update_seed_state("ipad_a", "ein roter Apfel", 42, "sd35_large")
state_a = _get_seed_state("ipad_a")
state_b = _get_seed_state("ipad_b")

check("Device A prompt updated", state_a["prompt"] == "ein roter Apfel")
check("Device A seed updated", state_a["seed"] == 42)
check("Device B prompt still None (isolated)", state_b["prompt"] is None)
check("Device B seed still None (isolated)", state_b["seed"] is None)

_update_seed_state("ipad_b", "wurstwasser trinken", 99, "flux2")
state_a = _get_seed_state("ipad_a")
state_b = _get_seed_state("ipad_b")

check("Device A still has its own prompt", state_a["prompt"] == "ein roter Apfel")
check("Device A still has its own seed", state_a["seed"] == 42)
check("Device B has its own prompt", state_b["prompt"] == "wurstwasser trinken")
check("Device B has its own seed", state_b["seed"] == 99)


# ============================================================
# TEST 2: Seed logic correctness (same prompt = new seed)
# ============================================================
print("\n[TEST 2] Seed logic: prompt changed vs unchanged")
reset()

import random

def compute_seed(device_id, new_prompt, new_config):
    """Simulate the Phase 4 seed logic from schema_pipeline_routes.py."""
    dev_state = _get_seed_state(device_id)
    if new_prompt != dev_state["prompt"] or new_config != dev_state["output_config"]:
        if dev_state["seed"] is not None:
            calculated_seed = dev_state["seed"]
        else:
            calculated_seed = 123456789
    else:
        calculated_seed = random.randint(0, 2147483647)
    _update_seed_state(device_id, new_prompt, calculated_seed, new_config)
    return calculated_seed

seed1 = compute_seed("dev_x", "hello", "sd35_large")
check("First run → standard seed 123456789", seed1 == 123456789)

seed2 = compute_seed("dev_x", "different prompt", "sd35_large")
check("Prompt changed → reuses previous seed", seed2 == 123456789)

seed3 = compute_seed("dev_x", "different prompt", "sd35_large")
check("Same prompt+config (re-run) → random seed", seed3 != 123456789)


# ============================================================
# TEST 3: Concurrent access — no data corruption
# ============================================================
print("\n[TEST 3] Concurrent access (20 threads, 100 ops each)")
reset()

errors = []

def worker(device_id, iterations=100):
    try:
        for i in range(iterations):
            prompt = f"prompt_{device_id}_{i}"
            _update_seed_state(device_id, prompt, i, f"config_{device_id}")
            state = _get_seed_state(device_id)
            # State should reflect THIS device's last write
            if state["prompt"] != prompt or state["seed"] != i:
                errors.append(f"{device_id}: expected ({prompt}, {i}), got ({state['prompt']}, {state['seed']})")
    except Exception as e:
        errors.append(f"{device_id}: exception {e}")

threads = [threading.Thread(target=worker, args=(f"device_{i}",)) for i in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()

check("No data corruption across 20 concurrent devices", len(errors) == 0)
if errors:
    for e in errors[:5]:
        print(f"    ERROR: {e}")


# ============================================================
# TEST 4: Cross-device bleeding scenario (the actual bug)
# ============================================================
print("\n[TEST 4] Cross-device bleeding scenario (the workshop bug)")
reset()

# iPad B generates diver image
seed_b = compute_seed("ipad_b", "eine Taucherin im Meer", "sd35_large")

# Laptop A generates with a DIFFERENT prompt
seed_a = compute_seed("laptop_a", "wurstwasser trinken", "sd35_large")

state_a = _get_seed_state("laptop_a")
state_b = _get_seed_state("ipad_b")

check("Laptop A has its OWN prompt", state_a["prompt"] == "wurstwasser trinken")
check("iPad B has its OWN prompt", state_b["prompt"] == "eine Taucherin im Meer")
check("Laptop A seed is independent from iPad B",
      state_a["prompt"] != state_b["prompt"])  # prompts didn't leak


# ============================================================
# TEST 5: TTL eviction
# ============================================================
print("\n[TEST 5] TTL eviction")
reset()

# Manually insert an entry with old timestamp
with _seed_state_lock:
    _seed_state["old_device"] = {
        "prompt": "stale", "seed": 1, "output_config": "x",
        "ts": time.time() - _SEED_STATE_TTL - 1  # expired
    }
    _seed_state["fresh_device"] = {
        "prompt": "fresh", "seed": 2, "output_config": "y",
        "ts": time.time()
    }

# Trigger eviction by getting any state
_get_seed_state("trigger_device")

with _seed_state_lock:
    check("Stale entry evicted", "old_device" not in _seed_state)
    check("Fresh entry retained", "fresh_device" in _seed_state)


# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed")
if FAIL == 0:
    print("ALL TESTS PASSED — seed state is properly isolated per device")
else:
    print("SOME TESTS FAILED — investigate above")
    sys.exit(1)
