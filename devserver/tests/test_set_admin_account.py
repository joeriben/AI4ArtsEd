"""devserver/scripts/set_admin_account.py: the command that sets the admin
account and the settings password, and the absence of any built-in password
(docs/DEVELOPMENT_DECISIONS.md, 2026-11-15).

Every run goes against the throwaway lab database of the suite
(tests/conftest.py) and a key file under tmp_path.
"""
import getpass
import hashlib
import os
import re
import stat
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
from sqlalchemy import text
from werkzeug.security import check_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import set_admin_account as S
from my_app.lab import auth_service
from my_app.lab import db as lab_db
from my_app.lab.db import Base, engine, SessionLocal
from my_app.lab import models as M
from my_app.lab.auth_service import (
    hash_password, verify_password, is_published_password, UNUSABLE_PASSWORD_HASH,
)
from my_app.lab.seed import seed_admin

NEW = "a-new-password-17"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def fresh_db():
    SessionLocal.remove()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    SessionLocal.remove()


@pytest.fixture
def key_file(tmp_path):
    f = tmp_path / "settings_password.key"
    f.write_text(hash_password("the-old-settings-pw"))
    f.chmod(0o600)
    return f


@pytest.fixture
def published(monkeypatch):
    """A stand-in for the passwords earlier versions built in."""
    value = "published-test-value"
    monkeypatch.setattr(auth_service, "PUBLISHED_PASSWORD_DIGESTS",
                        frozenset({hashlib.sha256(value.encode()).hexdigest()}))
    return value


def _answers(*values):
    it = iter(values)

    def answer(prompt=""):
        value = next(it)
        if isinstance(value, BaseException):
            raise value
        return value
    return answer


def _run(key_file, reads, passwords=(NEW, NEW), argv=()):
    return S.main(list(argv), ask=_answers(*passwords), read=_answers(*reads), key_file=key_file)


def _admin():
    SessionLocal.remove()
    return SessionLocal().query(M.User).filter(M.User.role == M.Role.admin).one()


def _unchanged(key_file):
    admin = _admin()
    assert admin.username == "admin"
    assert admin.email is None
    assert admin.password_hash == UNUSABLE_PASSWORD_HASH
    assert check_password_hash(key_file.read_text(), "the-old-settings-pw")


def _no_leftovers(key_file):
    assert not [p for p in key_file.parent.iterdir() if p.name.startswith(".settings_password-")]


def _educator(email="lehrkraft@example.org", username="lehrkraft"):
    db = SessionLocal()
    db.add(M.User(email=email, username=username, role=M.Role.educator, display_name="",
                  password_hash=hash_password("x" * 12), is_active=True))
    db.commit()
    SessionLocal.remove()


def _second_admin(username="zweiter", email=None):
    db = SessionLocal()
    db.add(M.User(username=username, email=email, role=M.Role.admin, display_name="",
                  password_hash=UNUSABLE_PASSWORD_HASH, is_active=True))
    db.commit()
    SessionLocal.remove()


def test_the_command_names_the_file_and_the_command_the_server_names():
    from my_app.lab import seed
    from my_app.routes import settings_routes as sr
    assert S.SETTINGS_PASSWORD_FILE.resolve() == sr.SETTINGS_PASSWORD_FILE.resolve()
    assert seed.SETTINGS_PASSWORD_FILE.resolve() == sr.SETTINGS_PASSWORD_FILE.resolve()
    assert sr.SET_PASSWORD_COMMAND == auth_service.SET_ADMIN_COMMAND
    assert auth_service.SET_ADMIN_COMMAND.endswith("devserver/scripts/" + Path(S.__file__).name)


def test_it_sets_name_email_password_and_the_settings_password(key_file, capsys):
    seed_admin()
    database = Path(lab_db._DB_PATH)
    database.chmod(0o644)
    assert _run(key_file, ["ai4admin", "Leitung@Example.org", ""]) == 0
    admin = _admin()
    assert admin.username == "ai4admin"
    assert admin.email == "leitung@example.org"
    assert verify_password(admin.password_hash, NEW)
    assert check_password_hash(key_file.read_text(), NEW)
    # Two hashes of one password: the account does not carry the key file's.
    assert admin.password_hash != key_file.read_text()
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    _no_leftovers(key_file)
    printed = capsys.readouterr()
    assert NEW not in printed.out + printed.err
    assert "pbkdf2" not in printed.out + printed.err
    assert str(database) in printed.out


def test_enter_keeps_name_and_email_and_no_keeps_the_settings_password(key_file):
    seed_admin()
    assert _run(key_file, ["ai4admin", "leitung@example.org", "y"]) == 0
    assert _run(key_file, ["", "", "n"], passwords=("another-pw-12345", "another-pw-12345")) == 0
    admin = _admin()
    assert (admin.username, admin.email) == ("ai4admin", "leitung@example.org")
    assert verify_password(admin.password_hash, "another-pw-12345")
    assert check_password_hash(key_file.read_text(), NEW)


@pytest.mark.parametrize("reads,passwords,reason", [
    (["ai4admin", "leitung@example.org", "y"], ("short", "short"), "at least 12"),
    (["ai4admin", "leitung@example.org", "y"], (NEW, NEW + "x"), "differ"),
    (["ai4admin", "leitung@example.org", "y"], (" " * 14, " " * 14), "whitespace"),
    (["ai 4admin", "", "y"], (NEW, NEW), "neither a space nor an @"),
    (["ai4@admin", "", "y"], (NEW, NEW), "neither a space nor an @"),
    (["ai4admin", "no-address", "y"], (NEW, NEW), "no email address"),
    (["lehrkraft", "", "y"], (NEW, NEW), "belongs to another account"),
    (["ai4admin", "Lehrkraft@Example.org", "y"], (NEW, NEW), "belongs to another account"),
    (["ai4admin", EOFError()], (NEW, NEW), "entry ended"),
    (["ai4admin", "leitung@example.org", KeyboardInterrupt()], (NEW, NEW), "entry ended"),
])
def test_a_refusal_changes_nothing(key_file, capsys, reads, passwords, reason):
    seed_admin()
    _educator()
    assert _run(key_file, reads, passwords) == 1
    _unchanged(key_file)
    assert reason in capsys.readouterr().err


def test_the_published_passwords_are_refused(key_file, published, capsys):
    seed_admin()
    assert _run(key_file, ["", "", "y"], (published,) * 2) == 1
    _unchanged(key_file)
    assert "published with the code" in capsys.readouterr().err


def _from_history(rev, path, pattern):
    """A value as it stood in the repository's history, or a skip where the
    history is not there (the public export, a shallow clone)."""
    try:
        shown = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{path}"],
                               capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip(f"commit {rev} is not in this checkout")
    found = re.search(pattern, shown)
    assert found is not None, f"{path} at {rev} no longer has the line this test reads"
    return found.group(1)


def test_the_refused_passwords_are_the_three_in_the_history():
    """The digests stand for the three passwords that stood in the code: the
    settings password of 6b5760e1 (2025-12-18), the one of 77aa5635
    (2026-01-05), unchanged until ebb69289, the last commit before it was taken
    out, and the seeded one as it stood there."""
    december = _from_history("6b5760e1", "devserver/my_app/routes/settings_routes.py",
                             r'correct_password\s*=\s*"([^"]+)"')
    january = _from_history("77aa5635", "devserver/my_app/routes/settings_routes.py",
                            r'FIXED_PASSWORD\s*=\s*"([^"]+)"')
    unchanged = _from_history("ebb69289", "devserver/my_app/routes/settings_routes.py",
                              r'FIXED_PASSWORD\s*=\s*"([^"]+)"')
    seeded = _from_history("ebb69289", "devserver/my_app/lab/seed.py",
                           r'hash_password\("([^"]+)"\)')
    refused = [is_published_password(value) for value in (december, january, seeded)]
    assert refused == [True, True, True]
    same = january == unchanged
    assert same is True
    assert len(auth_service.PUBLISHED_PASSWORD_DIGESTS) == 3


def test_an_argument_is_refused(key_file):
    seed_admin()
    assert _run(key_file, [], argv=["something"]) == 2
    _unchanged(key_file)


def test_another_user_than_the_owner_is_refused(key_file, monkeypatch):
    seed_admin()
    monkeypatch.setattr(os, "geteuid", lambda: os.stat(key_file.parent).st_uid + 1)
    assert _run(key_file, ["", "", "y"]) == 1
    _unchanged(key_file)
    with pytest.raises(S.Refused):
        S.require_owner(1000, euid=0)


def test_a_key_file_of_another_owner_is_refused(key_file, monkeypatch, capsys):
    seed_admin()
    real_lstat = os.lstat

    def lstat(path, *args, **kwargs):
        found = real_lstat(path, *args, **kwargs)
        if Path(path) == key_file:
            values = list(found[:10])
            values[4] = found.st_uid + 1          # st_uid
            return os.stat_result(values)
        return found

    monkeypatch.setattr(os, "lstat", lstat)
    assert _run(key_file, ["", "", "y"]) == 1
    monkeypatch.undo()
    _unchanged(key_file)
    assert "Make both belong to the user the backend runs as" in capsys.readouterr().err


def test_a_linked_key_file_is_refused(tmp_path):
    seed_admin()
    target = tmp_path / "elsewhere.key"
    target.write_text(hash_password("the-old-settings-pw"))
    link = tmp_path / "settings_password.key"
    link.symlink_to(target)
    assert _run(link, ["", "", "y"]) == 1
    assert link.is_symlink()
    assert check_password_hash(target.read_text(), "the-old-settings-pw")


def test_a_password_without_a_terminal_is_refused(key_file):
    seed_admin()

    def no_terminal(prompt=""):
        warnings.warn("cannot hide the input", getpass.GetPassWarning)
        return NEW

    assert S.main([], ask=no_terminal, read=_answers("", "", "y"), key_file=key_file) == 1
    _unchanged(key_file)


def test_without_an_admin_nothing_is_done(key_file):
    assert _run(key_file, ["", "", "y"]) == 1
    assert check_password_hash(key_file.read_text(), "the-old-settings-pw")


def test_before_the_first_start_nothing_is_done_or_created(key_file, tmp_path, monkeypatch, capsys):
    missing = tmp_path / "var" / "lab.db"
    monkeypatch.setattr(lab_db, "_DB_PATH", missing)
    assert _run(key_file, ["", "", "y"]) == 1
    assert not missing.exists()
    assert "start the backend once" in capsys.readouterr().err
    assert check_password_hash(key_file.read_text(), "the-old-settings-pw")


def test_a_database_without_tables_is_refused(key_file, capsys):
    Base.metadata.drop_all(bind=engine)
    assert _run(key_file, ["", "", "y"]) == 1
    assert "start the backend once" in capsys.readouterr().err
    assert check_password_hash(key_file.read_text(), "the-old-settings-pw")


def test_with_two_admins_it_asks_which(key_file):
    seed_admin()
    _second_admin(email="zweite@example.org")
    assert _run(key_file, ["Zweite@Example.org", "", "", "n"]) == 0
    SessionLocal.remove()
    db = SessionLocal()
    second = db.query(M.User).filter(M.User.email == "zweite@example.org").one()
    first = db.query(M.User).filter(M.User.username == "admin").one()
    assert verify_password(second.password_hash, NEW)
    assert first.password_hash == UNUSABLE_PASSWORD_HASH


@pytest.mark.parametrize("wanted", ["", "nobody", "lehrkraft"])
def test_with_two_admins_an_unknown_name_changes_nothing(key_file, capsys, wanted):
    seed_admin()
    _second_admin()
    _educator()
    assert _run(key_file, [wanted, "", "", "y"]) == 1
    assert "No admin account has that name" in capsys.readouterr().err
    SessionLocal.remove()
    db = SessionLocal()
    for admin in db.query(M.User).filter(M.User.role == M.Role.admin):
        assert admin.password_hash == UNUSABLE_PASSWORD_HASH
    assert check_password_hash(key_file.read_text(), "the-old-settings-pw")


def test_a_refusing_database_shows_no_hash_and_changes_nothing(key_file, capsys):
    """The text of a database error carries the statement; neither the hash
    nor the password reaches the terminal, and the key file stays."""
    seed_admin()
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TRIGGER refuse_update BEFORE UPDATE ON users "
            "BEGIN SELECT RAISE(ABORT, 'refused by the test'); END"))
    assert _run(key_file, ["ai4admin", "", "y"]) == 1
    printed = capsys.readouterr()
    for shown in (printed.out, printed.err):
        assert "pbkdf2" not in shown
        assert NEW not in shown
        assert "[parameters" not in shown
    assert "refused by the test" in printed.err
    _unchanged(key_file)
    _no_leftovers(key_file)


@pytest.mark.parametrize("failure", [OSError("disk full"), KeyboardInterrupt()])
def test_a_failing_key_file_leaves_the_account_set_and_says_so(key_file, monkeypatch, capsys, failure):
    seed_admin()

    def refuse(*args, **kwargs):
        raise failure

    monkeypatch.setattr(os, "replace", refuse)
    assert _run(key_file, ["ai4admin", "", "y"]) == 1
    monkeypatch.undo()
    assert "The admin account is set; the settings password was left as it was" in capsys.readouterr().err
    assert verify_password(_admin().password_hash, NEW)
    assert check_password_hash(key_file.read_text(), "the-old-settings-pw")
    _no_leftovers(key_file)


def test_the_database_files_are_made_private(tmp_path):
    db = tmp_path / "lab.db"
    db.write_text("")
    db.chmod(0o644)
    assert S.tighten_lab_database(db) == (1, 0)
    assert stat.S_IMODE(db.stat().st_mode) == 0o600


def test_no_password_is_built_into_the_settings(tmp_path, monkeypatch, published):
    """Without the key file the settings password opens nothing, and nothing
    creates the file; a published password opens nothing either."""
    from flask import Flask
    from my_app.routes import settings_routes as sr
    missing = tmp_path / "settings_password.key"
    monkeypatch.setattr(sr, "SETTINGS_PASSWORD_FILE", missing)
    assert sr.initialize_password() is False
    assert not missing.exists()
    a = Flask(__name__)
    a.secret_key = "test-secret"
    a.register_blueprint(sr.settings_bp)
    c = a.test_client()
    answer = c.post("/api/settings/auth", json={"password": "anything-at-all"})
    assert answer.status_code == 503
    assert answer.get_json()["error"] == "settings_password_not_set"
    present = tmp_path / "present.key"
    present.write_text(hash_password(published))
    monkeypatch.setattr(sr, "SETTINGS_PASSWORD_FILE", present)
    answer = c.post("/api/settings/auth", json={"password": published})
    assert answer.status_code == 403
    assert answer.get_json()["error"] == "published_password"
    with c.session_transaction() as sess:
        assert not sess.get("settings_authenticated")
    source = Path(sr.__file__).read_text()
    assert "FIXED_PASSWORD" not in source
    assert "generate_password_hash" not in source
