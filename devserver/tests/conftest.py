#!/usr/bin/env python3
"""Shared fixtures for the devserver suite.

Two things, both about what a test run may touch.

The apparatus export never writes into the room's own record while tests run.
Added 2026-09-09, after a suite run left six invented apparatus in
devserver/exports/json/canvas_graph_runs/ — the directory whose whole purpose is
to say what a room actually built. A record that counts test fixtures cannot
answer the question it was ordered for.

The lab database is a throwaway file (2026-09-24). my_app.lab.db binds its engine
to AI4ARTSED_DB_PATH at import time, and every create_app() runs the start-up
migration of lab/db.py on the file it names, which removes the names of the
participant accounts and cannot be undone. Without the redirect, a test that
builds the app would migrate the checkout's own devserver/var/lab.db, on the
development server the file the running backend serves; lab/db.py refuses to
bind that file while pytest runs.
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Before anything imports my_app.lab.db. A test module that names a file of its
# own later replaces one throwaway file with another.
_LAB_DB_DIR = tempfile.mkdtemp(prefix="lab_suite_")
os.environ["AI4ARTSED_DB_PATH"] = str(Path(_LAB_DB_DIR) / "lab.db")
atexit.register(shutil.rmtree, _LAB_DB_DIR, ignore_errors=True)

import pytest


@pytest.fixture(autouse=True)
def apparatus_exports_stay_out_of_the_record(tmp_path, monkeypatch):
    """Point the apparatus export at a scratch directory for every test.

    Autouse and unconditional: any test that reaches run_canvas_graph writes a
    file, and most of them reach it without meaning to (through the registry,
    through a chat turn). A test that wants to read what it wrote points the two
    paths somewhere of its own and overrides this.
    """
    try:
        from my_app.services import canvas_graph_export as cge
    except Exception:
        yield
        return
    runs = tmp_path / "canvas_graph_runs"
    monkeypatch.setattr(cge, "EXPORT_DIR", runs)
    monkeypatch.setattr(cge, "REJECTED_DIR", runs / "rejected")
    # Everything else a Resona turn writes about the room, for the same reason:
    # the kept repertoire, what she noted, and the workshop's own journal.
    for module, attr, name in (
        ("canvas_workflow_store", "STORAGE_DIR", "canvas_workflows"),
        ("resona_memory", "STORAGE_DIR", "resona_memory"),
        ("resona_journal", "STORAGE_DIR", "resona_journal"),
    ):
        try:
            mod = __import__(f"my_app.services.{module}", fromlist=[module])
            monkeypatch.setattr(mod, attr, tmp_path / name)
        except Exception:
            pass
    yield
