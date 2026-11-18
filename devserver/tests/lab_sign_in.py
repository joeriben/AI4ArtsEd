"""
A test client signed in as the admin, for the tests that build the whole app
(`create_app`). Every route of the app but the start page and the sign-in
needs a sign-in since 2026-11-15 (my_app/lab/sign_in_gate.py), and the machine
the server runs on is no admin any more (routes/settings_routes.py,
`_settings_admitted`).

The session is the one the sign-in page leaves (routes/auth_routes.py,
`login`): the account, its stamp, its role and the version of the conditions
of use it agreed to. What the sign-in itself checks is tested in
test_sign_in_gate.py.
"""
from my_app.lab import models as M
from my_app.lab.auth_service import account_stamp
from my_app.lab.db import SessionLocal
from my_app.lab.terms import SESSION_KEY, TERMS_VERSION


def sign_in_admin(client):
    """Sign `client` in as an active admin of the lab database, made where it
    holds none. Returns the client."""
    db = SessionLocal()
    admin = (
        db.query(M.User)
        .filter(M.User.role == M.Role.admin, M.User.is_active.is_(True))
        .order_by(M.User.id)
        .first()
    )
    if admin is None:
        admin = M.User(username="test-admin", role=M.Role.admin, password_hash="!", is_active=True)
        db.add(admin)
        db.commit()
    with client.session_transaction() as s:
        s["user_id"] = admin.id
        s["user_stamp"] = account_stamp(admin)
        s["role"] = admin.role.value
        s[SESSION_KEY] = TERMS_VERSION
    return client
