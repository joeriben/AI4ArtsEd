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


class UsageTracker:
    """Thread-safe, append-only JSONL usage logger with in-memory aggregation."""

    _instance: Optional["UsageTracker"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "UsageTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._file_lock = threading.Lock()
        return cls._instance

    def log(self, model: str, provider: str, stage: str,
            input_tokens: int, output_tokens: int) -> None:
        """Append a usage record. Safe to call from any thread."""
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "model": model,
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

    def get_usage(self, days: int = 30) -> List[dict]:
        """Read records from the last N days."""
        if not USAGE_FILE.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
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
                        if ts >= cutoff:
                            records.append(rec)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except Exception as e:
            logger.error(f"Failed to read usage file: {e}")
        return records

    def get_aggregated(self, days: int = 30) -> dict:
        """Aggregate usage by model, stage, and date."""
        records = self.get_usage(days)

        by_model: dict = {}
        by_stage: dict = {}
        by_date: dict = {}
        total_input = 0
        total_output = 0
        total_calls = 0

        for rec in records:
            model = rec.get("model", "unknown")
            stage = rec.get("stage", "unknown")
            inp = rec.get("input_tokens", 0)
            out = rec.get("output_tokens", 0)
            date_str = rec.get("ts", "")[:10]  # YYYY-MM-DD

            total_input += inp
            total_output += out
            total_calls += 1

            # By model
            if model not in by_model:
                by_model[model] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
            by_model[model]["input_tokens"] += inp
            by_model[model]["output_tokens"] += out
            by_model[model]["calls"] += 1

            # By stage
            if stage not in by_stage:
                by_stage[stage] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
            by_stage[stage]["input_tokens"] += inp
            by_stage[stage]["output_tokens"] += out
            by_stage[stage]["calls"] += 1

            # By date
            if date_str not in by_date:
                by_date[date_str] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
            by_date[date_str]["input_tokens"] += inp
            by_date[date_str]["output_tokens"] += out
            by_date[date_str]["calls"] += 1

        return {
            "by_model": by_model,
            "by_stage": by_stage,
            "by_date": dict(sorted(by_date.items(), reverse=True)),
            "period_days": days,
            "total_calls": total_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
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
