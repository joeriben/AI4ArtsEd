"""
Bootstrap: create tables and seed the admin account. Idempotent — safe to run
on every startup.

The admin is seeded without a password (UNUSABLE_PASSWORD_HASH): no password
opens the account until devserver/scripts/set_admin_account.py has set one.
No password is written into the code, and the settings password is not copied
onto the account (docs/DEVELOPMENT_DECISIONS.md, 2026-11-15).

Called (fail-safe) from create_app; see my_app/lab/__init__.py::init_lab.
Location: devserver/my_app/lab/seed.py
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from .auth_service import SET_ADMIN_COMMAND, UNUSABLE_PASSWORD_HASH
from .db import SessionLocal, init_db
from .models import User, Role

logger = logging.getLogger(__name__)

# The file routes/settings_routes.py names as SETTINGS_PASSWORD_FILE, written
# out here because the lab system does not import that module
# (tests/test_set_admin_account.py holds the two to one path).
SETTINGS_PASSWORD_FILE = Path(__file__).resolve().parents[2] / "settings_password.key"


def seed_admin() -> None:
    """Ensure an admin account exists; a new one has no usable password.

    Idempotent: if an admin already exists, returns immediately.
    """
    init_db()
    db = SessionLocal()
    admin = db.query(User).filter(User.role == Role.admin).first()
    if admin is not None:
        return

    admin = User(
        username="admin",
        role=Role.admin,
        display_name="Administrator",
        password_hash=UNUSABLE_PASSWORD_HASH,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    logger.warning(
        "[LAB-SEED] admin account created (id=%s) without a password. Set its name, "
        "email and password with: %s (from the repository root, as the user the "
        "backend runs as)",
        admin.id, SET_ADMIN_COMMAND,
    )


def report_copied_settings_hash(key_file: Path = SETTINGS_PASSWORD_FILE) -> int:
    """Warn for every admin account that carries the hash of settings_password.key.

    Versions before 2026-11-15 copied that hash onto the admin account at the
    first start, and they wrote the password that was published with the code
    into a missing settings_password.key. Where neither was changed since, the
    admin account has that password, and the sign-in refuses it
    (auth_service.is_published_password). Reads only; returns the number of
    such accounts.
    """
    try:
        stored = key_file.read_text(encoding="utf-8").strip()
    except OSError:
        return 0
    if not stored:
        return 0
    db = SessionLocal()
    try:
        copies = (
            db.query(User)
            .filter(User.role == Role.admin, User.password_hash == stored)
            .all()
        )
    except SQLAlchemyError as error:
        db.rollback()
        logger.warning("[LAB-SEED] could not compare the admin accounts with %s: %s",
                       key_file.name, type(error).__name__)
        return 0
    for admin in copies:
        logger.warning(
            "[LAB-SEED] admin account %s carries the hash of %s, as versions before "
            "2026-11-15 copied it at the first start. Where neither was changed since, "
            "that is the password published with the code, and the sign-in refuses it. "
            "Set a new one with: %s",
            admin.username or f"#{admin.id}", key_file.name, SET_ADMIN_COMMAND,
        )
    return len(copies)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_admin()
    print("Lab DB initialised and admin seeded.")
