"""Findings S-055 and S-077 of the code review of 2026-10-10.

S-055  Two export trees: exports/ at the repository root (the run data) and
       devserver/exports/ (the knowledge index, the Resona stores, the canvas
       stores, the knowledge areas). They stay two; config names both.
S-077  Sixteen modules derived a root from their own __file__, in two
       spellings; the knowledge index stood beside config.KNOWLEDGE_INDEX_DB,
       so a test that redirected config left the readers on the real index.
       Every root is read from config, the index path at call time.
"""
import os
import subprocess
import sys
from pathlib import Path

import config
from my_app.services import evidence_duty, knowledge_library

DEVSERVER = Path(config.__file__).resolve().parent
REPO = DEVSERVER.parent


def test_config_names_the_two_roots_as_the_modules_derived_them():
    assert config.DEVSERVER_DIR == DEVSERVER
    assert config.DEVSERVER_EXPORTS_DIR == DEVSERVER / "exports"
    assert config.DEVSERVER_JSON_DIR == DEVSERVER / "exports" / "json"
    assert config.DEVSERVER_DATA_DIR == DEVSERVER / "data"
    assert Path(config.EXPORTS_DIR) == REPO / "exports"
    assert Path(config.JSON_STORAGE_DIR) == REPO / "exports" / "json"
    assert Path(config.KNOWLEDGE_INDEX_DB) == DEVSERVER / "exports" / "knowledge_index.sqlite"


STORES_UNDER_CONFIG = r'''
import config
from pathlib import Path
from my_app.services import (bbq_runs, canvas_graph_export, canvas_workflow_store,
    knowledge_areas, local_llm_weights, local_media_weights,
    resona_journal, resona_memory, text_presets, thumbnails, translation_cache,
    usage_tracker)
json_dir = config.DEVSERVER_JSON_DIR
for got, want in (
    (canvas_graph_export.EXPORT_DIR, json_dir / "canvas_graph_runs"),
    (canvas_workflow_store.STORAGE_DIR, json_dir / "canvas_workflows"),
    (knowledge_areas.STORE_PATH, json_dir / "knowledge_areas.json"),
    (resona_journal.STORAGE_DIR, json_dir / "resona_journal"),
    (resona_memory.STORAGE_DIR, json_dir / "resona_memory"),
    (thumbnails.THUMBNAIL_CACHE_DIR, Path(config.EXPORTS_DIR) / ".thumbnails"),
    (translation_cache.DATA_DIR, config.DEVSERVER_DATA_DIR),
    (usage_tracker.DATA_DIR, config.DEVSERVER_DATA_DIR),
    (bbq_runs.DATA_DIR, config.DEVSERVER_DATA_DIR),
    (local_llm_weights.DEVSERVER_ROOT, config.DEVSERVER_DIR),
    (local_media_weights.DEVSERVER_ROOT, config.DEVSERVER_DIR),
    (text_presets.DEVSERVER_ROOT, config.DEVSERVER_DIR),
):
    assert got == want, (got, want)
print("ok")
'''


def test_every_store_stands_under_the_root_config_names():
    """In a fresh interpreter: the suite's conftest points four of these
    stores at a scratch directory for every test, so the live attributes in
    this process would show the scratch directory, not the module's value."""
    run = subprocess.run([sys.executable, "-c", STORES_UNDER_CONFIG], cwd=str(DEVSERVER),
                         env={**os.environ, "PYTHONPATH": str(DEVSERVER)},
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0 and run.stdout.strip() == "ok", run.stderr[-3000:]


def test_the_knowledge_index_path_follows_config_at_call_time(monkeypatch, tmp_path):
    db = tmp_path / "index.sqlite"
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db)
    assert knowledge_library.index_db_path() == db
    assert evidence_duty.index_path() == db
    assert not hasattr(knowledge_library, "DB_PATH")
    assert not hasattr(evidence_duty, "INDEX_PATH")


def test_no_module_derives_a_root_the_finding_names_from_its_own_file():
    """exports/, data/ and a devserver root of its own: the places S-077 names.
    The derivations of schemas/, config/*.json and the root files are not in
    the finding and are not read here."""
    files = sorted((DEVSERVER / "my_app" / "services").glob("*.py"))
    files += sorted((DEVSERVER / "my_app" / "routes").glob("*.py"))
    files.append(DEVSERVER / "my_app" / "__init__.py")
    files.append(DEVSERVER / "scripts" / "ingest_research_literature.py")
    offenders = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "__file__" not in line:
                continue
            if path.name == "llm_providers.py":
                continue  # stdlib-only by contract: ComfyUI's key node loads it by path
            if '"exports"' in line or '"data"' in line or "DEVSERVER_ROOT =" in line:
                offenders.append(f"{path.relative_to(DEVSERVER)}:{number}: {line.strip()}")
    assert offenders == [], "\n".join(offenders)


def test_llm_providers_loads_by_path_where_nothing_of_the_devserver_is_importable():
    """comfyui_nodes/ai4artsed_comfyui/_platform_credentials.py loads this module
    by path inside ComfyUI's process, where neither devserver/ nor config is on
    the path: the module is stdlib-only by contract. a3050f8 gave it `import
    config` for its root, and the OpenRouter key node failed with
    ModuleNotFoundError until the second review of 2026-10-10 found it."""
    path = DEVSERVER / "my_app" / "services" / "llm_providers.py"
    code = (
        "import importlib.util; "
        f"spec = importlib.util.spec_from_file_location('llm_providers_by_path', {str(path)!r}); "
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
        "print(m.DEVSERVER_ROOT)"
    )
    run = subprocess.run([sys.executable, "-I", "-c", code], cwd="/",
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-2000:]
    assert run.stdout.strip() == str(DEVSERVER)
