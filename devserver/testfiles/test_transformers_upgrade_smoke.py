#!/usr/bin/env python3
"""
Smoke checks for an isolated Transformers upgrade test environment.

This script is intentionally import-focused and avoids heavy model downloads.
It verifies the exact Transformers classes and integration points that are
productively used by AI4ArtsEd's main venv.

Run only inside an isolated upgrade test venv.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def check_import(label: str, module: str, names: list[str]) -> list[str]:
    failures: list[str] = []
    try:
        mod = importlib.import_module(module)
    except Exception as exc:
        return [f"{label}: failed to import module {module}: {exc}"]

    for name in names:
        if not hasattr(mod, name):
            failures.append(f"{label}: missing symbol {module}.{name}")
    return failures


def main() -> int:
    failures: list[str] = []

    try:
        import torch
        print(f"torch={torch.__version__}")
    except Exception as exc:
        print(f"FATAL: torch import failed: {exc}")
        return 1

    try:
        import diffusers
        print(f"diffusers={diffusers.__version__}")
    except Exception as exc:
        print(f"FATAL: diffusers import failed: {exc}")
        return 1

    try:
        import transformers
        print(f"transformers={transformers.__version__}")
    except Exception as exc:
        print(f"FATAL: transformers import failed: {exc}")
        return 1

    failures.extend(check_import(
        "text-backend",
        "transformers",
        ["AutoModelForCausalLM", "AutoTokenizer", "BitsAndBytesConfig"],
    ))

    failures.extend(check_import(
        "diffusers-flux2",
        "transformers",
        ["AutoModelForImageTextToText", "PixtralProcessor", "TorchAoConfig"],
    ))

    failures.extend(check_import(
        "diffusers-wan",
        "transformers",
        ["UMT5EncoderModel", "TorchAoConfig", "AutoTokenizer"],
    ))

    failures.extend(check_import(
        "research-t5",
        "transformers",
        ["T5EncoderModel", "AutoTokenizer"],
    ))

    # Confirm our productively imported modules still import cleanly.
    for module in (
        "gpu_service.services.text_backend",
        "gpu_service.services.diffusers_backend",
    ):
        try:
            importlib.import_module(module)
        except Exception as exc:
            failures.append(f"module-import: failed to import {module}: {exc}")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nOK: import-level smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
