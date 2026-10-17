"""
Lab User/Course system (Phase 0) — additive identity/course persistence.

This package holds ONLY identity/courses/ownership/prompt-library/work-metadata
in a single SQLite file (devserver/var/lab.db). It is isolated from the existing
JSON/run storage and from the orchestration engine.

`init_lab(app)` is the single entry point create_app calls. It is FAIL-SAFE:
any DB error is logged and swallowed so the server still starts without the Lab
features (the existing platform stays fully usable without login).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def init_lab(app) -> bool:
    """Initialise the Lab DB, register per-request teardown, and seed the admin.

    Returns True on success, False if the Lab layer was skipped due to an error.
    Never raises — a broken DB path must NOT prevent the server from starting.
    """
    try:
        from .db import init_db, register_teardown
        from .seed import seed_admin

        init_db()                 # create tables (idempotent)
        register_teardown(app)    # SessionLocal.remove() per request
        seed_admin()              # admin from settings_password.key (idempotent)
        logger.info("[LAB] user/course system initialised")
        return True
    except Exception as e:  # noqa: BLE001 — fail-safe by design
        logger.warning("[LAB] initialisation skipped (server continues without lab features): %s", e)
        return False
