"""
The lab database of a test run is never the checkout's own (tests/conftest.py,
2026-09-24): create_app() runs the start-up migration of lab/db.py on the file
AI4ARTSED_DB_PATH names, and the migration removes the names of the participant
accounts for good. A test outside tests/ gets no redirect, and lab/db.py
refuses to bind the checkout's own file while pytest runs.

Run: python3 -m pytest devserver/tests/test_lab_db_isolation.py -q
"""
import os
import subprocess
import sys

from file_modules import DEVSERVER

sys.path.insert(0, str(DEVSERVER))


def test_the_suite_never_opens_the_checkouts_lab_db():
    from my_app.lab import db
    assert db._DB_PATH.resolve() != db._DEFAULT_DB_PATH.resolve()


def test_a_test_run_that_names_no_file_stops_before_the_checkouts_own():
    """As a testfile outside tests/, run on its own, would. The import
    binds no file yet (SQLite connects lazily), so a guard that failed here
    would still have touched nothing."""
    env = {k: v for k, v in os.environ.items() if k != "AI4ARTSED_DB_PATH"}
    env.setdefault("PYTEST_VERSION", "test")
    script = "import sys; sys.path.insert(0, sys.argv[1]); import my_app.lab.db"
    out = subprocess.run([sys.executable, "-c", script, str(DEVSERVER)], env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode != 0
    assert "AI4ARTSED_DB_PATH" in out.stderr, out.stderr
