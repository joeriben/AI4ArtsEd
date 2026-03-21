#!/usr/bin/env python3
"""
Stage 2 Model Comparison: Cheaper Alternatives to Claude Sonnet 4.6

Tests 4 models against 8 difficult interception configs to evaluate
whether cheaper models can handle pedagogically complex transformations.

Usage: python devserver/tests/stage2_model_comparison.py
"""

import json
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
    ("mammouth/gpt-5-mini", "GPT-5-mini"),
    ("mammouth/gemini-3-flash-preview", "Gemini 3 Flash"),
    ("mammouth/deepseek-r1-0528", "DeepSeek R1"),
    ("mammouth/deepseek-v3.2", "DeepSeek V3.2"),
    ("mammouth/llama-4-maverick", "Llama 4 Maverick"),
]

# --- Prompt Template (from manipulate.json) ---
TEMPLATE = (
    "Task:\n{task_instruction}\n\n"
    "Context:\n{context}\n\n"
    "Important: Respond in the same language as the input prompt below.\n\n"
    "Prompt:\n{input_text}"
)

# Task instruction (from instruction_selector.py, "transformation" type)
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

# --- Test Cases ---
# Each config gets: 1x EN (reference baseline) + 2x other languages
# EN reference lets us separate "can the model do the task?" from
# "can it do the task in other languages?" (multilingual capability)
TEST_CASES = [
    {
        "config": "planetarizer",
        "prompts": [
            ("A cup of coffee on a table", "en"),
            ("Bir akilli telefon", "tr"),
            ("도시의 놀이터", "ko"),
        ]
    },
    {
        "config": "sensitive",
        "prompts": [
            ("The moment before a glass falls", "en"),
            ("유리잔이 떨어지기 직전의 순간", "ko"),
            ("Des gens qui attendent a un arret de bus", "fr"),
        ]
    },
    {
        "config": "forceful",
        "prompts": [
            ("A factory at night", "en"),
            ("Una fabrica de noche", "es"),
            ("غابة", "ar"),
        ]
    },
    {
        "config": "confucianliterati",
        "prompts": [
            ("A city skyline at sunset", "en"),
            ("늙은 남자가 차를 마시고 있다", "ko"),
            ("Bir dag manzarasi", "tr"),
        ]
    },
    {
        "config": "bauhaus",
        "prompts": [
            ("A busy market scene", "en"),
            ("Bir cicek", "tr"),
            ("Жвавий ринок", "uk"),
        ]
    },
    {
        "config": "poetry_hoelderlin",
        "prompts": [
            ("Rain", "en"),
            ("Une rue vide", "fr"),
            ("Una calle vacia", "es"),
        ]
    },
    {
        "config": "mad_world",
        "prompts": [
            ("Someone giving a presentation", "en"),
            ("فصل دراسي", "ar"),
            ("Birisi sunum yapiyor", "tr"),
        ]
    },
    {
        "config": "analog_photography_1870s",
        "prompts": [
            ("Children playing in a courtyard", "en"),
            ("Дiти грають у дворi", "uk"),
            ("항구의 배들", "ko"),
        ]
    },
]


def load_api_key() -> str:
    """Load Mammouth API key from key file or environment."""
    import os
    key = os.environ.get("MAMMOUTH_API_KEY", "")
    if key:
        return key

    if MAMMOUTH_KEY_FILE.exists():
        for line in MAMMOUTH_KEY_FILE.read_text().strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                return line
    raise RuntimeError(f"No API key found. Set MAMMOUTH_API_KEY or create {MAMMOUTH_KEY_FILE}")


def load_config(config_name: str) -> dict:
    """Load an interception config JSON."""
    path = CONFIGS_DIR / f"{config_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return json.loads(path.read_text())


def get_context(config: dict, lang: str) -> str:
    """Get context in matching language, fallback to EN."""
    ctx = config.get("context", {})
    return ctx.get(lang, ctx.get("en", ""))


def call_mammouth(api_key: str, model_id: str, prompt: str,
                  parameters: dict) -> tuple:
    """Call Mammouth API. Returns (response_text, latency_seconds)."""
    api_model = model_id.replace("mammouth/", "")

    payload = {
        "model": api_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": parameters.get("temperature", 0.7),
        "max_tokens": parameters.get("max_tokens", 2048),
    }
    # Some providers reject temperature + top_p together (Anthropic, some others)
    # Only add top_p for models known to support it alongside temperature
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
    """Build the full Stage 2 prompt from template."""
    context = get_context(config, lang)
    return TEMPLATE.format(
        task_instruction=TASK_INSTRUCTION,
        context=context,
        input_text=input_text,
    )


def word_count(text: str) -> int:
    return len(text.split())


def run_comparison():
    """Run all test cases and generate reports."""
    api_key = load_api_key()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    total_calls = sum(len(tc["prompts"]) for tc in TEST_CASES) * len(MODELS)
    call_num = 0

    print(f"Stage 2 Model Comparison — {total_calls} API calls")
    print(f"Models: {', '.join(m[1] for m in MODELS)}")
    print(f"Configs: {', '.join(tc['config'] for tc in TEST_CASES)}")
    print("=" * 60)

    for tc in TEST_CASES:
        config_name = tc["config"]
        config = load_config(config_name)
        params = config.get("parameters", {})

        for input_text, lang in tc["prompts"]:
            full_prompt = build_prompt(config, input_text, lang)
            prompt_tokens_est = len(full_prompt.split())

            print(f"\n--- {config_name} | \"{input_text}\" ({lang}) ---")
            print(f"    Context language: "
                  f"{'matched' if lang in config.get('context', {}) else 'fallback EN'}"
                  f" | ~{prompt_tokens_est} words prompt")

            case_results = {
                "config": config_name,
                "input_text": input_text,
                "input_lang": lang,
                "context_lang": lang if lang in config.get("context", {}) else "en",
                "prompt_tokens_est": prompt_tokens_est,
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

                # Rate limit pause between calls
                time.sleep(1.0)

            results.append(case_results)

    # Save JSON results
    json_path = RESULTS_DIR / f"stage2_comparison_{timestamp}.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nJSON results: {json_path}")

    # Generate Markdown report
    md_path = RESULTS_DIR / f"stage2_comparison_{timestamp}.md"
    md_path.write_text(generate_markdown(results, timestamp))
    print(f"Markdown report: {md_path}")

    # Print summary
    print_summary(results)


def generate_markdown(results: list, timestamp: str) -> str:
    """Generate side-by-side Markdown comparison report."""
    lines = [
        f"# Stage 2 Model Comparison — {timestamp[:8]}",
        "",
        "## Models Tested",
        "| Model | ID | Cost (input/output per M tokens) |",
        "|---|---|---|",
        "| **Sonnet 4.6** (baseline) | claude-sonnet-4-6 | ~$3 / $15 |",
        "| **Haiku 4.5** | claude-haiku-4-5-20251001 | ~$0.80 / $4 |",
        "| **GLM-5** | glm-5 | $0.95 / $2.55 |",
        "| **Kimi-2.5** | kimi-k2.5 | $0.60 / $3 |",
        "",
        "---",
        "",
    ]

    for case in results:
        config = case["config"]
        prompt = case["input_text"]
        lang = case["input_lang"]
        ctx_lang = case["context_lang"]

        lines.append(f"## {config.upper()} — \"{prompt}\" [{lang}]")
        lines.append(f"*Context: {ctx_lang} | ~{case['prompt_tokens_est']} words prompt*")
        lines.append("")

        for model_label, data in case["models"].items():
            latency = data["latency_s"]
            wc = data["word_count"]
            output = data["output"]

            lines.append(f"### {model_label}")
            if data["is_error"]:
                lines.append(f"> {output}")
            else:
                lines.append(f"*{latency}s | {wc} words*")
                lines.append("")
                lines.append(output)
            lines.append("")

        # Scoring table
        model_labels = list(case["models"].keys())
        header = "| Dimension | " + " | ".join(model_labels) + " |"
        sep = "|---|" + "|".join(["---"] * len(model_labels)) + "|"
        dimensions = [
            "Epistemological Fidelity",
            "Constraint Adherence",
            "Image Prompt Quality",
            "Language Matching",
            "Pedagogical Value",
        ]
        lines.append(header)
        lines.append(sep)
        for dim in dimensions:
            lines.append(f"| {dim} | " + " | ".join(["___"] * len(model_labels)) + " |")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def print_summary(results: list):
    """Print error/success summary."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    model_stats = {}
    for case in results:
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
        print(f"  {label:20s}  OK: {stats['ok']:2d}  ERR: {stats['err']:2d}  "
              f"Avg latency: {avg_lat:.1f}s")


if __name__ == "__main__":
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_comparison()
