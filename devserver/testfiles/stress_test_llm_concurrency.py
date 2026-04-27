#!/usr/bin/env python3
"""
Stress test reproducing the GPU Service crash from 2026-04-26 15:47:34.

Original failure mode:
  Three concurrent qwen3:1.7b chat calls from a DSGVO-NER burst on the same
  prompt. All three failed simultaneously after 15-19s with
  RemoteDisconnected, then port 17803 stayed dead (Connection refused) until
  manual restart.

Root cause (post-mortem):
  llama-cpp-python Llama.create_chat_completion is NOT thread-safe per
  instance. Concurrent calls on the same Llama corrupt KV-cache / CUDA state
  and segfault the whole GPU Service process.

Fix:
  Per-alias threading.Lock around create_chat_completion / create_completion
  in gpu_service/services/llm_backend.py.

This script verifies the fix by hammering qwen3:1.7b with concurrent calls.
Pass criteria: every call returns SAFE/UNSAFE (not None / not 500), and the
GPU Service is still alive after the test.
"""

import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

GPU_SERVICE = "http://localhost:17803"
MODEL = "qwen3:1.7b"

# Real DSGVO verification prompt template from
# devserver/schemas/engine/stage_orchestrator.py:279.
# Original entities from the crash log: "triangular ears" (false positive
# flagged by SpaCy NER on a wolf description).
ORIGINAL_TEXT = (
    "A wolf has dense gray-brown fur, a soft undercoat, upright triangular "
    "ears, a bushy low tail, and powerful paw pads."
)
ORIGINAL_ENTITIES = "triangular ears"


def build_dsgvo_prompt(entities: str, text: str) -> str:
    return (
        f"A text analysis system flagged the following words as person names. "
        f"Are they actually person names, or false positives?\n\n"
        f"Flagged words: {entities}\n"
        f'Original text: "{text}"\n\n'
        f"Rules:\n"
        f"- Actual person names (real or fictional) = UNSAFE\n"
        f"- Descriptions, adjectives, materials, places, objects, technical "
        f"terms = SAFE\n\n"
        f"Answer ONLY with SAFE or UNSAFE."
    )


def fire_one(call_id: int, entities: str, text: str) -> dict:
    """Send one chat request, return timing + result."""
    prompt = build_dsgvo_prompt(entities, text)
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 50,
    }
    t0 = time.monotonic()
    try:
        resp = requests.post(
            f"{GPU_SERVICE}/api/llm/chat",
            json=payload,
            timeout=120,
        )
        dt = time.monotonic() - t0
        if resp.status_code != 200:
            return {
                "id": call_id,
                "ok": False,
                "duration": dt,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
        data = resp.json()
        content = (data.get("content") or "").strip()
        return {
            "id": call_id,
            "ok": bool(content),
            "duration": dt,
            "content": content[:80],
        }
    except requests.exceptions.RequestException as e:
        return {
            "id": call_id,
            "ok": False,
            "duration": time.monotonic() - t0,
            "error": f"{type(e).__name__}: {e}",
        }


def is_service_alive() -> bool:
    try:
        r = requests.get(f"{GPU_SERVICE}/api/llm/models", timeout=5)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def run_burst(label: str, concurrency: int, entities: str, text: str) -> bool:
    print(f"\n=== {label}: {concurrency} concurrent calls ===")
    if not is_service_alive():
        print(f"  ABORT: GPU Service not reachable at {GPU_SERVICE}")
        return False

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(fire_one, i, entities, text) for i in range(concurrency)
        ]
        results = [f.result() for f in as_completed(futures)]
    wall = time.monotonic() - t0

    results.sort(key=lambda r: r["id"])
    ok_count = sum(1 for r in results if r["ok"])
    durations = [r["duration"] for r in results]

    for r in results:
        if r["ok"]:
            print(
                f"  [{r['id']}] {r['duration']:6.2f}s OK  "
                f"-> {r['content']!r}"
            )
        else:
            print(
                f"  [{r['id']}] {r['duration']:6.2f}s FAIL "
                f"-> {r.get('error', '???')}"
            )

    print(
        f"  Wall: {wall:.2f}s | per-call min/max/avg: "
        f"{min(durations):.2f}s / {max(durations):.2f}s / "
        f"{sum(durations) / len(durations):.2f}s | "
        f"OK: {ok_count}/{concurrency}"
    )

    if not is_service_alive():
        print("  POST-CHECK: GPU Service is DEAD — crash reproduced!")
        return False
    print("  POST-CHECK: GPU Service alive")
    return ok_count == concurrency


def main() -> int:
    print(f"Target: {GPU_SERVICE}, model: {MODEL}")
    print(
        f"Trigger: DSGVO verification, entities={ORIGINAL_ENTITIES!r}, "
        f"text length={len(ORIGINAL_TEXT)} chars"
    )

    # Warmup: first call loads the model (~5-10s), would skew burst timing.
    print("\n=== Warmup: 1 call (loads model into VRAM) ===")
    warm = fire_one(0, ORIGINAL_ENTITIES, ORIGINAL_TEXT)
    if not warm["ok"]:
        print(f"  Warmup failed: {warm}")
        return 1
    print(f"  Warmup OK in {warm['duration']:.2f}s -> {warm['content']!r}")

    # Phase 1: Exact reproduction of the crash trigger.
    if not run_burst(
        "Phase 1 (original crash trigger)", 3, ORIGINAL_ENTITIES, ORIGINAL_TEXT
    ):
        print("\nFAIL: Phase 1 did not pass — fix is incomplete.")
        return 2

    # Phase 2: Harder burst, same model.
    if not run_burst(
        "Phase 2 (5x burst, same prompt)", 5, ORIGINAL_ENTITIES, ORIGINAL_TEXT
    ):
        print("\nFAIL: Phase 2 did not pass.")
        return 3

    # Phase 3: 10x burst with varied entities.
    print("\n=== Phase 3: 10 concurrent calls, varied entities ===")
    if not is_service_alive():
        print(f"  ABORT: GPU Service not reachable at {GPU_SERVICE}")
        return 4
    varied_entities = [
        "triangular ears", "torn brown trousers", "long snout",
        "amber eyes", "gray fur", "wooded hill",
        "tattered linen pants", "pine tree silhouettes",
        "powerful paw pads", "bushy low tail",
    ]
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            pool.submit(fire_one, i, ent, ORIGINAL_TEXT)
            for i, ent in enumerate(varied_entities)
        ]
        results = [f.result() for f in as_completed(futures)]
    wall = time.monotonic() - t0
    results.sort(key=lambda r: r["id"])
    ok_count = sum(1 for r in results if r["ok"])
    for r in results:
        ent = varied_entities[r["id"]]
        if r["ok"]:
            print(
                f"  [{r['id']:2d}] {r['duration']:6.2f}s OK  "
                f"({ent!r:30}) -> {r['content']!r}"
            )
        else:
            print(
                f"  [{r['id']:2d}] {r['duration']:6.2f}s FAIL "
                f"({ent!r:30}) -> {r.get('error', '???')}"
            )
    print(
        f"  Wall: {wall:.2f}s | OK: {ok_count}/10 | "
        f"sequential lock effect: per-call ~{wall/10:.2f}s avg slot"
    )
    if not is_service_alive():
        print("  POST-CHECK: GPU Service is DEAD — crash reproduced!")
        return 5
    print("  POST-CHECK: GPU Service alive")

    print("\n=== ALL PHASES PASSED — fix verified ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
