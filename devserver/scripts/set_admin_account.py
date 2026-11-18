#!/usr/bin/env python3
"""Set the name, the email address and the password of the admin account, and
the settings password.

No password is written into the code of this platform. A new installation
has an admin account without a password (my_app/lab/seed.py) and no settings
password (my_app/routes/settings_routes.py); this command gives it both.
It is also the command that changes them later.

It asks in the terminal: the user name and the email address (Enter keeps the
value shown), the new password twice (getpass, from a terminal only: never an
argument, never the environment), and whether the settings password is to be
the same password. It refuses fewer than 12 characters and the three passwords
that earlier versions built into the code (my_app/lab/auth_service.py,
PUBLISHED_PASSWORD_DIGESTS).

It runs as the user who owns devserver/, the user the backend runs as, and as
no other, root included: the backend reads settings_password.key as that user
at mode 0600, and the code of the checkout is not run with anybody else's
rights. That is settled before anything of my_app is imported, because
my_app/lab/db.py creates devserver/var when it is imported.

The lab database is the file my_app/lab/db.py names; AI4ARTSED_DB_PATH
overrides it, and where the backend's service sets that variable, the command
needs the same value. The command prints the path. The backend creates the
database at its first start, and the command refuses to run before that. The
database files are made the owner's alone (mode 0600) before the new hash is
written into them. The admin account is committed first. The settings
password then goes to devserver/settings_password.key, written beside the old
file under a temporary name and moved into place, so a reader sees the old
file or the new one; if that fails, the command says that the account is set
and the settings password is not.

The command prints names, paths and counts, never a password or a hash.
Sessions that are signed in stay signed in; the command says how to end them.

Run from the repository root, as the user the backend runs as:

    ./venv/bin/python devserver/scripts/set_admin_account.py
    sudo -u <that user> ./venv/bin/python devserver/scripts/set_admin_account.py

Exit status: 0 done, 1 refused or failed, 2 given an argument.
"""
from __future__ import annotations

import getpass
import os
import re
import stat
import sys
import tempfile
import warnings
from pathlib import Path


DEVSERVER_DIR = Path(__file__).resolve().parents[1]
# The file my_app/routes/settings_routes.py names as SETTINGS_PASSWORD_FILE.
# Written out here and not imported, because importing that module creates
# devserver/var; tests/test_set_admin_account.py holds the two to one path.
SETTINGS_PASSWORD_FILE = DEVSERVER_DIR / "settings_password.key"

MIN_LENGTH = 12
PRIVATE_FILE_MODE = 0o600
LAB_DATABASE_SUFFIXES = ("", "-wal", "-shm")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

UNCHANGED = "The admin account and the settings password were left as they were."


class Refused(RuntimeError):
    """Nothing was changed; the message says why and what to do."""


def _who(uid: int) -> str:
    try:
        import pwd
        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


def owner_of_checkout(key_file: Path) -> int:
    """The uid the command has to run as: the owner of the key file's directory.

    An existing key file has to be a regular file of that owner (judged with
    os.lstat, so a link is judged as a link).
    """
    directory = os.stat(key_file.parent)
    try:
        found = os.lstat(key_file)
    except FileNotFoundError:
        return directory.st_uid
    if not stat.S_ISREG(found.st_mode):
        raise Refused(f"{key_file.name} is a symbolic link or not a regular file. Look at what it "
                      f"is, remove it by hand if it should go, and run the command again.")
    if found.st_uid != directory.st_uid:
        raise Refused(f"{key_file.name} belongs to {_who(found.st_uid)}, but {key_file.parent.name}/ "
                      f"belongs to {_who(directory.st_uid)}. Make both belong to the user the backend "
                      f"runs as, and run the command as that user.")
    return directory.st_uid


def require_owner(uid: int, euid: int | None = None) -> None:
    """Refuse every process that does not run as `uid`, root included."""
    me = os.geteuid() if euid is None else euid
    if me == uid:
        return
    raise Refused(f"devserver/ belongs to {_who(uid)}, and this command runs as {_who(me)}. "
                  f"Run it as {_who(uid)}, the user the backend runs as.")


def refusal(first: str, second: str) -> str | None:
    """Why the two password entries are not accepted, or None when they are."""
    from my_app.lab.auth_service import is_published_password
    if len(first) < MIN_LENGTH:
        return f"The password needs at least {MIN_LENGTH} characters."
    if not first.strip():
        return "The password needs more than whitespace."
    if is_published_password(first):
        return "That password was published with the code. Choose another one."
    if first != second:
        return "The two entries differ."
    return None


def name_refusal(username: str, email: str) -> str | None:
    """Why the user name or the email address is not accepted, or None."""
    if not username or len(username) > 120 or re.search(r"\s|@", username):
        return "The user name must not be empty and holds neither a space nor an @."
    if email and (len(email) > 255 or not EMAIL.match(email)):
        return "That is no email address."
    return None


def tighten_lab_database(lab_db: Path) -> tuple[int, int]:
    """Set the lab database and its -wal and -shm files to mode 0600.

    Only a regular file that group or others can read or write is touched; a
    link is left alone, since chmod would follow it. Returns (set, failed).
    """
    tightened = failed = 0
    for suffix in LAB_DATABASE_SUFFIXES:
        path = Path(f"{lab_db}{suffix}")
        try:
            found = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError:
            failed += 1
            continue
        if not stat.S_ISREG(found.st_mode) or not found.st_mode & 0o077:
            continue
        try:
            os.chmod(path, PRIVATE_FILE_MODE)
        except OSError:
            failed += 1
        else:
            tightened += 1
    return tightened, failed


def stage_key_file(key_file: Path, password_hash: str) -> str:
    """Write the hash to a new file (mode 0600) beside `key_file`; return its name.

    The name ends in `.key`, so a file left behind by a killed process stays
    under the repository's `*.key` ignore rule.
    """
    descriptor, staged = tempfile.mkstemp(prefix=".settings_password-", suffix=".key",
                                          dir=key_file.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), PRIVATE_FILE_MODE)
            handle.write(password_hash)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        os.unlink(staged)
        raise
    return staged


def cause(error: BaseException) -> str:
    """The error's type and the database's own message, without the statement.

    The text of a SQLAlchemy error carries the statement and its bound values,
    the new password hash among them; `orig` is the database's message alone.
    """
    original = getattr(error, "orig", None)
    return f"{type(error).__name__}: {original}" if original is not None else type(error).__name__


def _ask_password(ask) -> tuple[str, str]:
    """Both entries, from a terminal only.

    getpass falls back to plain input with a GetPassWarning where no terminal
    can hide what is typed (ssh without -t, a pipe): the password would be
    echoed or sit in a script. That is refused.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        first = ask("New password: ")
        second = ask("Repeat the password: ")
    return first, second


def main(argv: list[str] | None = None, ask=getpass.getpass, read=input,
         key_file: Path | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    if arguments:
        print("This command takes no arguments: it asks for everything.", file=sys.stderr)
        return 2
    key_file = Path(SETTINGS_PASSWORD_FILE if key_file is None else key_file)

    try:
        require_owner(owner_of_checkout(key_file))
    except (Refused, OSError) as error:
        print(f"{UNCHANGED} {error}", file=sys.stderr)
        return 1

    if str(DEVSERVER_DIR) not in sys.path:
        sys.path.insert(0, str(DEVSERVER_DIR))
    from sqlalchemy.exc import OperationalError
    from my_app.lab.auth_service import hash_password
    from my_app.lab.db import SessionLocal, _DB_PATH
    from my_app.lab.models import User, Role

    lab_db = Path(_DB_PATH)
    print(f"Lab database: {lab_db}")
    not_started = (f"{UNCHANGED} The lab database has no admin account yet: start the backend "
                   f"once, it creates the database with one, and run the command again. Where the "
                   f"backend's service sets AI4ARTSED_DB_PATH, run the command with the same value.")
    if not lab_db.exists():
        print(not_started, file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        try:
            admins = db.query(User).filter(User.role == Role.admin).order_by(User.id).all()
        except OperationalError:
            admins = []
        if not admins:
            print(not_started, file=sys.stderr)
            return 1
        try:
            if len(admins) == 1:
                admin = admins[0]
            else:
                names = ", ".join(a.username or a.email or f"#{a.id}" for a in admins)
                wanted = read(f"Admin accounts: {names}. Which one: ").strip()
                matches = [a for a in admins if wanted and (
                    wanted == a.username or (a.email and wanted.lower() == a.email))]
                if len(matches) != 1:
                    print(f"{UNCHANGED} No admin account has that name.", file=sys.stderr)
                    return 1
                admin = matches[0]
            print(f"Admin account: user name {admin.username or '(none)'}, "
                  f"email address {admin.email or '(none)'}.")
            username = read(f"User name [{admin.username or ''}]: ").strip() or (admin.username or "")
            email = (read(f"Email address [{admin.email or ''}]: ").strip() or (admin.email or "")).lower()
            problem = name_refusal(username, email)
            if problem is None:
                names = {username} | ({email} if email else set())
                taken = db.query(User).filter(
                    User.id != admin.id,
                    User.username.in_(names) | User.email.in_(names),
                ).count()
                if taken:
                    problem = "The user name or the email address belongs to another account."
            if problem:
                print(f"{UNCHANGED} {problem}", file=sys.stderr)
                return 1
            first, second = _ask_password(ask)
            problem = refusal(first, second)
            if problem:
                print(f"{UNCHANGED} {problem}", file=sys.stderr)
                return 1
            answer = read("Set the settings password to the same password? [Y/n]: ").strip().lower()
        except getpass.GetPassWarning:
            print(f"{UNCHANGED} The password is read from a terminal only. Run the command "
                  "in an interactive shell (over ssh: ssh -t).", file=sys.stderr)
            return 1
        except (EOFError, KeyboardInterrupt):
            print(f"{UNCHANGED} The entry ended.", file=sys.stderr)
            return 1
        settings_too = answer in ("", "y", "yes", "j", "ja")

        tightened, failed = tighten_lab_database(lab_db)
        if tightened:
            print(f"Lab database files that other users could read or write, now mode 0600: {tightened}.")
        if failed:
            print(f"WARNING: {failed} lab database file(s) can be read or written by other users and "
                  f"could not be set to mode 0600.", file=sys.stderr)

        admin.username = username
        admin.email = email or None
        admin.password_hash = hash_password(first)
        try:
            db.commit()
        except BaseException as error:  # noqa: BLE001 - reported; a rollback undoes it
            db.rollback()
            print(f"{UNCHANGED} The lab database refused the change ({cause(error)}).", file=sys.stderr)
            return 1
        print(f"Set: user name {username}, email address {email or '(none)'}, password of the admin account.")

        if settings_too:
            staged = None
            try:
                staged = stage_key_file(key_file, hash_password(first))
                os.replace(staged, key_file)
                staged = None
            except BaseException as error:  # noqa: BLE001 - reported, the account stays set
                print(f"The admin account is set; the settings password was left as it was "
                      f"({cause(error)}). Run the command again to set it.", file=sys.stderr)
                return 1
            finally:
                if staged is not None:
                    try:
                        os.unlink(staged)
                    except FileNotFoundError:
                        pass
            print(f"Set: settings password, {key_file} with mode 0600.")
        else:
            print("The settings password was left as it was.")
        if not admin.is_active:
            print("WARNING: this admin account is deactivated, and the sign-in refuses it.", file=sys.stderr)
        print('Sign in on the tab "Course leader" with the user name or the email address.')
        print("Sessions that are signed in stay signed in. To end them all: stop the backend; where "
              "its service sets SECRET_KEY, give it a new one, otherwise remove "
              f"{key_file.with_name('session_signing.key')} (and session_signing_previous.key if it "
              "exists); then start the backend.")
        return 0
    finally:
        SessionLocal.remove()


if __name__ == "__main__":
    raise SystemExit(main())
