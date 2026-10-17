"""The Diffusers default model is named once, in config (finding S-026 of the code review of 2026-10-10).

The routes fell back to a literal nine times and the backend defaulted eleven
signatures with the same string; a swap of the default meant twenty edits in
two files, or a service whose routes and backend disagreed. Read as source,
because the backend imports torch, which this venv does not carry.
"""
import ast
import os

GPU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LITERAL = "stabilityai/stable-diffusion-3.5-large"


def _prose_lines(source):
    covered = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                covered.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
    return covered


def test_only_config_carries_the_literal():
    carriers = []
    for folder in ("routes", "services"):
        root = os.path.join(GPU, folder)
        for name in sorted(os.listdir(root)):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            prose = _prose_lines(source)
            for number, line in enumerate(source.splitlines(), 1):
                if number in prose or line.lstrip().startswith("#"):
                    continue
                if LITERAL in line:
                    carriers.append(f"{folder}/{name}:{number}")
    assert carriers == [], carriers


def test_config_names_it_and_the_two_readers_import_it():
    with open(os.path.join(GPU, "config.py"), encoding="utf-8") as fh:
        assert f'DEFAULT_MODEL_ID = "{LITERAL}"' in fh.read()
    for rel in ("routes/diffusers_routes.py", "services/diffusers_backend.py"):
        with open(os.path.join(GPU, rel), encoding="utf-8") as fh:
            assert "from config import DEFAULT_MODEL_ID" in fh.read(), rel
