"""
API Usage Tracker — logs per-call token usage to JSONL for local cost analysis.

Records: model, provider, stage, input/output tokens, timestamp.
Aggregation: by model, by stage, by date.
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Storage location
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
USAGE_FILE = DATA_DIR / "api_usage.jsonl"


def _load_pricing() -> dict:
    """Load all pricing files from data/pricing_*.json. Returns {provider: {model: {input, output}}}."""
    pricing = {}
    for f in DATA_DIR.glob("pricing_*.json"):
        provider = f.stem.replace("pricing_", "")
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                # Strip _comment key
                pricing[provider] = {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception as e:
            logger.error(f"Failed to load pricing {f}: {e}")
    return pricing


def _calc_cost(model: str, provider: str, input_tokens: int, output_tokens: int,
               pricing: dict) -> float:
    """Calculate estimated cost in USD. Returns 0 if no pricing data."""
    prov_pricing = pricing.get(provider, {})
    if not prov_pricing:
        return 0.0
    # Strip provider prefix from model name (e.g. "mammouth/claude-sonnet-4-6" -> "claude-sonnet-4-6")
    bare_model = model.split("/", 1)[-1] if "/" in model else model
    rates = prov_pricing.get(bare_model)
    if not rates:
        return 0.0
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


class UsageTracker:
    """Thread-safe, append-only JSONL usage logger with in-memory aggregation."""

    _instance: Optional["UsageTracker"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "UsageTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._file_lock = threading.Lock()
            cls._instance._pricing_cache = None
            cls._instance._pricing_mtime = 0.0
        return cls._instance

    def _get_pricing(self) -> dict:
        """Load pricing with simple mtime-based cache."""
        try:
            latest_mtime = max(
                (f.stat().st_mtime for f in DATA_DIR.glob("pricing_*.json")),
                default=0.0
            )
        except Exception:
            latest_mtime = 0.0
        if self._pricing_cache is None or latest_mtime > self._pricing_mtime:
            self._pricing_cache = _load_pricing()
            self._pricing_mtime = latest_mtime
        return self._pricing_cache

    def log(self, model: str, provider: str, stage: str,
            input_tokens: int, output_tokens: int) -> None:
        """Append a usage record. Safe to call from any thread."""
        # Strip provider prefix (e.g. "mammouth/claude-sonnet-4-6" -> "claude-sonnet-4-6")
        bare_model = model.split("/", 1)[-1] if "/" in model else model
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "model": bare_model,
            "provider": provider,
            "stage": stage,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with self._file_lock:
                with open(USAGE_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write usage record: {e}")

    def get_usage(self, days: int = 30,
                  date_from: Optional[str] = None,
                  date_to: Optional[str] = None) -> List[dict]:
        """Read records filtered by date range or last N days.

        If date_from/date_to are given, they take precedence over days.
        days=0 means all records.
        """
        if not USAGE_FILE.exists():
            return []

        if date_from or date_to:
            start = datetime.fromisoformat(date_from) if date_from else datetime.min
            end = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59) if date_to else datetime.max
        elif days == 0:
            start, end = datetime.min, datetime.max
        else:
            start = datetime.now() - timedelta(days=days)
            end = datetime.max

        records = []
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        ts = datetime.fromisoformat(rec["ts"])
                        if start <= ts <= end:
                            records.append(rec)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except Exception as e:
            logger.error(f"Failed to read usage file: {e}")
        return records

    def get_aggregated(self, days: int = 30,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None) -> dict:
        """Aggregate usage by model, stage, and date — with cost estimates."""
        records = self.get_usage(days, date_from, date_to)
        pricing = self._get_pricing()

        by_model: dict = {}
        by_stage: dict = {}
        by_date: dict = {}
        total_input = 0
        total_output = 0
        total_calls = 0
        total_cost = 0.0

        def _bucket(d: dict, key: str) -> dict:
            if key not in d:
                d[key] = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost": 0.0}
            return d[key]

        for rec in records:
            model = rec.get("model", "unknown")
            provider = rec.get("provider", "unknown")
            stage = rec.get("stage", "unknown")
            inp = rec.get("input_tokens", 0)
            out = rec.get("output_tokens", 0)
            date_str = rec.get("ts", "")[:10]
            cost = _calc_cost(model, provider, inp, out, pricing)

            total_input += inp
            total_output += out
            total_calls += 1
            total_cost += cost

            for bucket, key in [(by_model, model), (by_stage, stage), (by_date, date_str)]:
                b = _bucket(bucket, key)
                b["input_tokens"] += inp
                b["output_tokens"] += out
                b["calls"] += 1
                b["cost"] += cost

        # Round cost values
        for d in (by_model, by_stage, by_date):
            for v in d.values():
                v["cost"] = round(v["cost"], 4)

        return {
            "by_model": by_model,
            "by_stage": by_stage,
            "by_date": dict(sorted(by_date.items(), reverse=True)),
            "period_days": days,
            "total_calls": total_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost": round(total_cost, 4),
        }


def extract_usage(response_json: dict, provider: str) -> tuple:
    """Normalize usage from API response. Returns (input_tokens, output_tokens)."""
    usage = response_json.get("usage") or {}
    if not usage:
        return 0, 0
    if provider in ("anthropic", "bedrock"):
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    # OpenAI-compatible (mammouth, openrouter, openai, mistral, ionos)
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def get_usage_tracker() -> UsageTracker:
    """Module-level accessor for the singleton tracker."""
    return UsageTracker()
