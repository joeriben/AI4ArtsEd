"""
Bootstrap: create tables and seed the admin user from the EXISTING settings
password hash, so the legacy admin login and the new user system agree on who
"admin" is. Idempotent — safe to run on every startup.

The settings password is stored (already hashed, werkzeug pbkdf2:sha256) in
devserver/settings_password.key by settings_routes.initialize_password(). We
reuse that hash verbatim, so no plaintext is needed and both login paths verify
the same credential.

Called (fail-safe) from create_app; see my_app/lab/__init__.py::init_lab.
Location: devserver/my_app/lab/seed.py
"""
from __future__ import annotations

import logging
from pathlib import Path

from .db import SessionLocal, init_db
from .models import User, Role

logger = logging.getLogger(__name__)

# Same file settings_routes.py uses:
#   settings_routes.py: SETTINGS_PASSWORD_FILE = <repo_root>/settings_password.key
#   which resolves (from devserver/my_app/routes/) to devserver/settings_password.key.
# lab/seed.py -> parents[2] == devserver/
SETTINGS_PASSWORD_FILE = Path(__file__).resolve().parents[2] / "settings_password.key"


def seed_admin() -> None:
    """Ensure exactly one admin user exists, reusing the settings password hash.

    Idempotent: if an admin already exists, returns immediately.
    """
    init_db()
    db = SessionLocal()
    admin = db.query(User).filter(User.role == Role.admin).first()
    if admin is not None:
        return

    # Reuse the already-hashed settings password verbatim (a werkzeug pbkdf2
    # hash — the same scheme our verify_password expects).
    if SETTINGS_PASSWORD_FILE.exists():
        password_hash = SETTINGS_PASSWORD_FILE.read_text().strip()
    else:
        from .auth_service import hash_password
        password_hash = hash_password("change-me-immediately")
        logger.warning(
            "[LAB-SEED] settings_password.key missing at %s — admin seeded with a placeholder",
            SETTINGS_PASSWORD_FILE,
        )

    admin = User(
        username="admin",
        role=Role.admin,
        display_name="Administrator",
        password_hash=password_hash,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    logger.info("[LAB-SEED] admin user created (id=%s)", admin.id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_admin()
    print("Lab DB initialised and admin seeded.")
