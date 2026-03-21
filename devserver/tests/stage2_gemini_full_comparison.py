#!/usr/bin/env python3
"""
Stage 2 Full Comparison: Gemini 3 Flash vs. Sonnet 4.6 across ALL configs.

Tests all text_transformation configs with context (32 configs)
using 3 universal prompts each, for horizontal comparison.

Usage: python devserver/tests/stage2_gemini_full_comparison.py
"""

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime

# --- Paths ---
DEVSERVER_ROOT = Path(__file__).parent.parent
CONFIGS_DIR = DEVSERVER_ROOT / "schemas" / "configs" / "interception"
RESULTS_DIR = Path(__file__).parent / "results"
MAMMOUTH_KEY_FILE = DEVSERVER_ROOT / "mammouth.key"

# --- API ---
MAMMOUTH_API_URL = "https://api.mammouth.ai/v1/chat/completions"

MODELS = [
    ("mammouth/claude-sonnet-4-6", "Sonnet 4.6"),
    ("mammouth/gemini-3-flash-preview", "Gemini 3 Flash"),
]

# --- Prompt Template (from manipulate.json) ---
TEMPLATE = (
    "Task:\n{task_instruction}\n\n"
    "Context:\n{context}\n\n"
    "Important: Respond in the same language as the input prompt below.\n\n"
    "Prompt:\n{input_text}"
)

TASK_INSTRUCTION = (
    "Transform the Input according to the rules in Context.\n"
    "ALWAYS reply in the language of the Input.\n\n"
    "CULTURAL RESPECT PRINCIPLES:\n"
    "- When describing cultural practices, heritages, or non-Western contexts: "
    "Use the same neutral, fact-based approach as for Western contexts\n"
    "- FORBIDDEN: Exoticizing, romanticizing, or mystifying cultural practices\n"
    "- FORBIDDEN: Orientalist tropes (exotic, mysterious, timeless, ancient wisdom, etc.)\n"
    "- FORBIDDEN: Homogenizing diverse cultures into aesthetic stereotypes\n\n"
    "Output ONLY the transformed result. Maximum 300 words.\n"
    "NO meta-commentary (\"I will...\", \"This shows...\", \"wird ausgefuehrt als...\").\n"
    "NO headlines, NO titles, NO bulletpoints, NO **formatting**.\n"
    "Use the specific vocabulary and techniques defined in Context."
)

# 3 universal prompts — same across all configs for horizontal comparison
# 2x EN (reference) + 1x multilingual (rotating)
UNIVERSAL_PROMPTS = [
    ("A cup of coffee on a table", "en"),
    ("Children playing near a river", "en"),
]

# Rotating multilingual prompts — assigned round-robin to configs
MULTILINGUAL_PROMPTS = [
    ("Bir yasli agac", "tr"),
    ("강가의 아이들", "ko"),
    ("Des oiseaux sur un fil electrique", "fr"),
    ("Una ventana abierta", "es"),
    ("شجرة قديمة", "ar"),
    ("Старий будинок на розi вулицi", "uk"),
]


def load_api_key() -> str:
    key = os.environ.get("MAMMOUTH_API_KEY", "")
    if key:
        return key
    if MAMMOUTH_KEY_FILE.exists():
        for line in MAMMOUTH_KEY_FILE.read_text().strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                return line
    raise RuntimeError(f"No API key found. Set MAMMOUTH_API_KEY or create {MAMMOUTH_KEY_FILE}")


def discover_configs() -> list:
    """Auto-discover all testable interception configs."""
    configs = []
    for f in sorted(CONFIGS_DIR.glob("*.json")):
        if "deactivated" in f.name:
            continue
        cfg = json.loads(f.read_text())
        # Only text_transformation pipeline with context, not skipping stage2
        if cfg.get("pipeline") != "text_transformation":
            continue
        if cfg.get("meta", {}).get("skip_stage2", False):
            continue
        if "context" not in cfg:
            continue
        configs.append(f.stem)
    return configs


def load_config(config_name: str) -> dict:
    path = CONFIGS_DIR / f"{config_name}.json"
    return json.loads(path.read_text())


def get_context(config: dict, lang: str) -> str:
    ctx = config.get("context", {})
    return ctx.get(lang, ctx.get("en", ""))


def call_mammouth(api_key: str, model_id: str, prompt: str,
                  parameters: dict) -> tuple:
    api_model = model_id.replace("mammouth/", "")

    payload = {
        "model": api_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": parameters.get("temperature", 0.7),
        "max_tokens": parameters.get("max_tokens", 2048),
    }
    # Skip top_p for providers that reject it alongside temperature
    skip_top_p = any(x in api_model for x in ("claude", "gpt", "gemini"))
    if "top_p" in parameters and not skip_top_p:
        payload["top_p"] = parameters["top_p"]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    start = time.time()
    try:
        resp = requests.post(MAMMOUTH_API_URL, headers=headers,
                             json=payload, timeout=120)
        latency = time.time() - start

        if resp.status_code != 200:
            return f"[ERROR {resp.status_code}]: {resp.text[:300]}", latency

        data = resp.json()
        content = data["choices"][0]["message"].get("content")
        if content is None:
            return "[ERROR]: Model returned empty/null content", latency
        return content.strip(), latency

    except requests.exceptions.Timeout:
        return "[ERROR]: Request timed out after 120s", time.time() - start
    except Exception as e:
        return f"[ERROR]: {str(e)[:300]}", time.time() - start


def build_prompt(config: dict, input_text: str, lang: str) -> str:
    context = get_context(config, lang)
    return TEMPLATE.format(
        task_instruction=TASK_INSTRUCTION,
        context=context,
        input_text=input_text,
    )


def word_count(text: str) -> int:
    return len(text.split())


def run_comparison():
    api_key = load_api_key()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    config_names = discover_configs()
    print(f"Discovered {len(config_names)} configs")

    # Assign multilingual prompts round-robin
    test_cases = []
    for i, config_name in enumerate(config_names):
        ml_prompt = MULTILINGUAL_PROMPTS[i % len(MULTILINGUAL_PROMPTS)]
        prompts = list(UNIVERSAL_PROMPTS) + [ml_prompt]
        test_cases.append({"config": config_name, "prompts": prompts})

    total_calls = len(test_cases) * 3 * len(MODELS)
    call_num = 0
    results = []

    print(f"Gemini 3 Flash Full Comparison — {total_calls} API calls")
    print(f"Models: {', '.join(m[1] for m in MODELS)}")
    print(f"Configs: {len(test_cases)}")
    print("=" * 60)

    for tc in test_cases:
        config_name = tc["config"]
        config = load_config(config_name)
        params = config.get("parameters", {})
        difficulty = config.get("display", {}).get("difficulty", "?")

        for input_text, lang in tc["prompts"]:
            full_prompt = build_prompt(config, input_text, lang)

            print(f"\n--- {config_name} (d{difficulty}) | \"{input_text}\" ({lang}) ---")

            case_results = {
                "config": config_name,
                "difficulty": difficulty,
                "input_text": input_text,
                "input_lang": lang,
                "context_lang": lang if lang in config.get("context", {}) else "en",
                "models": {}
            }

            for model_id, model_label in MODELS:
                call_num += 1
                print(f"    [{call_num}/{total_calls}] {model_label}...", end=" ", flush=True)

                output, latency = call_mammouth(api_key, model_id, full_prompt, params)
                wc = word_count(output) if not output.startswith("[ERROR") else 0

                case_results["models"][model_label] = {
                    "model_id": model_id,
                    "output": output,
                    "latency_s": round(latency, 2),
                    "word_count": wc,
                    "is_error": output.startswith("[ERROR"),
                }

                status = f"{latency:.1f}s, {wc}w" if not output.startswith("[ERROR") else output[:60]
                print(status)

                time.sleep(0.5)

            results.append(case_results)

    # Save JSON
    json_path = RESULTS_DIR / f"gemini_full_{timestamp}.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nJSON results: {json_path}")

    # Generate Markdown
    md_path = RESULTS_DIR / f"gemini_full_{timestamp}.md"
    md_path.write_text(generate_markdown(results, timestamp))
    print(f"Markdown report: {md_path}")

    # Summary
    print_summary(results)


def generate_markdown(results: list, timestamp: str) -> str:
    lines = [
        f"# Gemini 3 Flash Full Comparison — {timestamp[:8]}",
        "",
        "Sonnet 4.6 (baseline) vs. Gemini 3 Flash across ALL interception configs.",
        "",
        "---",
        "",
    ]

    current_config = None
    for case in results:
        config = case["config"]
        diff = case["difficulty"]
        prompt = case["input_text"]
        lang = case["input_lang"]

        if config != current_config:
            if current_config is not None:
                lines.append("---")
                lines.append("")
            lines.append(f"## {config} (difficulty {diff})")
            lines.append("")
            current_config = config

        lines.append(f"### \"{prompt}\" [{lang}]")
        lines.append("")

        for model_label, data in case["models"].items():
            if data["is_error"]:
                lines.append(f"**{model_label}**: ERROR — {data['output'][:100]}")
            else:
                lines.append(f"**{model_label}** *({data['latency_s']}s, {data['word_count']}w)*")
                lines.append("")
                lines.append(data["output"])
            lines.append("")

    return "\n".join(lines)


def print_summary(results: list):
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    model_stats = {}
    config_scores = {}

    for case in results:
        config = case["config"]
        diff = case["difficulty"]
        for label, data in case["models"].items():
            if label not in model_stats:
                model_stats[label] = {"ok": 0, "err": 0, "total_latency": 0.0}
            if data["is_error"]:
                model_stats[label]["err"] += 1
            else:
                model_stats[label]["ok"] += 1
                model_stats[label]["total_latency"] += data["latency_s"]

    for label, stats in model_stats.items():
        avg_lat = (stats["total_latency"] / stats["ok"]) if stats["ok"] > 0 else 0
        print(f"  {label:20s}  OK: {stats['ok']:3d}  ERR: {stats['err']:2d}  "
              f"Avg latency: {avg_lat:.1f}s")

    # Per-config comparison
    print(f"\nPer-config latency comparison (Sonnet vs Gemini):")
    print(f"{'Config':35s} {'Sonnet':>8s} {'Gemini':>8s} {'Speedup':>8s}")
    print("-" * 65)

    config_latencies = {}
    for case in results:
        config = case["config"]
        if config not in config_latencies:
            config_latencies[config] = {"Sonnet 4.6": [], "Gemini 3 Flash": []}
        for label, data in case["models"].items():
            if not data["is_error"]:
                config_latencies[config][label].append(data["latency_s"])

    for config, lats in sorted(config_latencies.items()):
        s_avg = sum(lats["Sonnet 4.6"]) / len(lats["Sonnet 4.6"]) if lats["Sonnet 4.6"] else 0
        g_avg = sum(lats["Gemini 3 Flash"]) / len(lats["Gemini 3 Flash"]) if lats["Gemini 3 Flash"] else 0
        speedup = s_avg / g_avg if g_avg > 0 else 0
        print(f"  {config:35s} {s_avg:7.1f}s {g_avg:7.1f}s {speedup:7.1f}x")


if __name__ == "__main__":
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_comparison()
