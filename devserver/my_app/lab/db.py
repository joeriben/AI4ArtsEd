"""
SQLite persistence layer for the Lab User/Course system (Phase 0).

Why SQLite: relational
identity data (users <-> courses <-> prompts <-> works) needs FK integrity,
uniqueness and atomic updates. A single file fits the "single directory"
deployment. Isolated from the existing JSON/run storage — this DB holds ONLY
identity/courses/ownership/prompt-library/work-metadata. Runs, favorites and
settings keep living as JSON/*.key next to the code, untouched.

DB file location (gitignored): devserver/var/lab.db
  - resolved relative to devserver/ from this file's location, so it works
    regardless of the process cwd.
  - overridable via AI4ARTSED_DB_PATH (used by tests for throwaway isolation).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session, DeclarativeBase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# devserver/my_app/lab/db.py -> parents[2] == devserver/
_DEVSERVER_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _DEVSERVER_DIR / "var" / "lab.db"
_DB_PATH = Path(os.environ.get("AI4ARTSED_DB_PATH", str(_DEFAULT_DB_PATH)))

# A test run never binds the checkout's own file (2026-09-24). init_db() runs
# the start-up migration below on the file bound here, which removes the names
# of the participant accounts and cannot be undone. The suite under tests/
# names a throwaway file (tests/conftest.py); a test anywhere else names its
# own in AI4ARTSED_DB_PATH or stops here. pytest sets PYTEST_VERSION for the
# length of its run, and the processes a test starts inherit it.
if os.environ.get("PYTEST_VERSION") and _DB_PATH.resolve() == _DEFAULT_DB_PATH.resolve():
    raise RuntimeError(
        f"a test run would bind {_DEFAULT_DB_PATH}, the lab database of this "
        f"checkout; name a file of the test's own in AI4ARTSED_DB_PATH"
    )

# Best-effort directory creation. Outside a test run (above), importing this
# module must NEVER raise — a bad
# DB path must not crash the server at import time (the blueprint imports
# SessionLocal at module load). Any real failure surfaces later, in init_db(),
# where create_app wraps it fail-safe. SQLite connects lazily, so create_engine
# below does not touch the filesystem yet either.
try:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

# check_same_thread=False because Waitress serves with multiple threads.
engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """Enable WAL + FK enforcement on every connection.

    WAL gives us concurrent readers while a writer is active (Waitress is
    multi-threaded). foreign_keys=ON is required for SQLite to honour FK
    constraints / ON DELETE CASCADE at all.
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.execute("PRAGMA busy_timeout=5000;")
    cur.close()


# scoped_session -> one Session per thread, matching Waitress' threading model.
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
)


class Base(DeclarativeBase):
    """Declarative base for all Lab ORM models."""
    pass


# ---------------------------------------------------------------------------
# Lifecycle helpers (hooked into create_app / teardown)
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create tables if missing. Idempotent (MVP migration strategy).

    Ensures the DB directory exists first. If the path is genuinely unusable
    this raises — create_app calls this inside a fail-safe try/except so the
    server still starts (without lab features).
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    from . import models  # noqa: F401  (ensure models are imported/registered)
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _ensure_indexes()
    _drop_columns()
    _migrate_places()


# Columns that were added to a model after its table already existed.
# `create_all` makes MISSING TABLES and never alters one that is there, so a
# new column reaches a file that has been running only through an ALTER. One
# line per column, and each stays: an install is older than the code it runs.
_ADDED_COLUMNS = (
    # NOT NULL with the same default the model carries: `create_all` writes the
    # column non-nullable on a fresh file, and a migrated file that took NULLs
    # would be a second schema for the same column.
    ("lora_adapters", "category", "VARCHAR(40) NOT NULL DEFAULT ''"),
    # The places of 2026-09-23 (lab/place_codes.py). Nullable in the model as
    # well: a membership without a place has no number and no code, and a
    # course without a window is closed.
    ("course_memberships", "place_number", "INTEGER"),
    ("course_memberships", "code_hash", "VARCHAR(64)"),
    ("course_memberships", "code_issued_at", "DATETIME"),
    ("courses", "access_until", "DATETIME"),
)


def _ensure_columns() -> None:
    """Add the columns of `_ADDED_COLUMNS` that an older file lacks.

    Every ALTER stands on its own and a failure is logged, never raised: the
    read and the write are two statements, so a second process that starts at
    the same moment (a deploy restart over the running server, `python -m
    my_app.lab.seed`) adds the column between them and this one gets
    `duplicate column name`. Raising here would take the whole lab layer with
    it — `lab/__init__.py` swallows the exception, and then the session
    teardown and the admin seed do not run either.
    """
    from sqlalchemy import text

    for table, column, decl in _ADDED_COLUMNS:
        try:
            with engine.begin() as con:
                rows = con.execute(text(f"PRAGMA table_info({table})")).fetchall()
                if not rows:  # no such table yet — create_all owns that case
                    continue
                if column in {r[1] for r in rows}:
                    continue
                con.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {decl}"))
                logger.info(f"[LAB-DB] added {table}.{column}")
        except Exception as e:
            logger.warning(f"[LAB-DB] {table}.{column} not added: {e}")


# Indexes over columns of `_ADDED_COLUMNS`. `create_all` builds a table's
# indexes together with the table, so an older file receives them here, in
# exactly the form the model declares: name, columns, uniqueness.
_ADDED_INDEXES = (
    ("ix_course_memberships_code_hash",
     "CREATE UNIQUE INDEX IF NOT EXISTS ix_course_memberships_code_hash "
     "ON course_memberships (code_hash)"),
    ("uq_course_place_number",
     "CREATE UNIQUE INDEX IF NOT EXISTS uq_course_place_number "
     "ON course_memberships (course_id, place_number)"),
)


def _ensure_indexes() -> None:
    """Create the indexes of `_ADDED_INDEXES` that an older file lacks.

    Logged, never raised, for the reason `_ensure_columns` gives. Where the
    code index is missing, a login still finds its place, by a scan; where
    the place index is missing, two places of a course can come to share a
    number, so the log line names the file.
    """
    from sqlalchemy import text

    for name, ddl in _ADDED_INDEXES:
        try:
            with engine.begin() as con:
                con.execute(text(ddl))
        except Exception as e:
            logger.warning(f"[LAB-DB] index {name} not created in {_DB_PATH}: {e}")


# Columns a model no longer has. `create_all` never drops one, so a file that
# has been running keeps a column the code stopped writing — and where that
# column is NOT NULL without a default, as `lora_adapters.base_configs` was,
# every new row is refused by the file while a fresh install takes it. One line
# per column, and each stays: an install is older than the code it runs.
_DROPPED_COLUMNS = (
    # The models a LoRA runs under, ticked off by hand until 2026-09-22; the
    # adapter file says it (`my_app/services/lora_base.py`).
    ("lora_adapters", "base_configs"),
    # The course key of BAUPLAN Entscheid 2 and the join code, 2026-09-23: a
    # course admits the codes of its places (lab/place_codes.py). join_code is
    # NOT NULL without a default, so a file that keeps it refuses every new
    # course. SQLite refuses to drop an indexed column; a third element names
    # the indexes that go first, in the same transaction (`_drop_columns`).
    ("courses", "access_key_hash"),
    ("courses", "access_key_expires_at"),
    ("courses", "join_code", "ix_courses_join_code"),
)


def _column_names(cur, table: str) -> set:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _drop_columns() -> None:
    """Take the columns of `_DROPPED_COLUMNS` out of an older file.

    `ALTER TABLE … DROP COLUMN` needs SQLite 3.35 (2021); the platform's own
    hosts carry 3.37 and newer. One line runs in one transaction, its indexes
    together with its column: pysqlite opens a transaction before DML alone and
    commits DDL statement by statement, so the BEGIN is written here, on a
    connection of its own. A drop that fails leaves the index standing with
    its column. A failure is logged, never raised, for the reason
    `_ensure_columns` gives — but the consequence differs: where the drop does
    not happen and the column was NOT NULL, a new row cannot be written, so
    the log line says the file, not just the error.
    """
    from sqlalchemy import text

    for table, column, *indexes in _DROPPED_COLUMNS:
        raw = engine.raw_connection()
        try:
            cur = raw.cursor()
            if column not in _column_names(cur, table):
                continue
            cur.execute("BEGIN IMMEDIATE")
            try:
                if column in _column_names(cur, table):  # a second process may have been first
                    for index in indexes:
                        cur.execute(f"DROP INDEX IF EXISTS {index}")
                    cur.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
                raw.commit()
            except Exception:
                raw.rollback()
                raise
            logger.info(f"[LAB-DB] dropped {table}.{column}")
        except Exception as e:
            # What the failure left behind is read back rather than assumed:
            # the statement can fail after the column is already gone.
            try:
                with engine.connect() as con:
                    rows = con.execute(text(f"PRAGMA table_info({table})")).fetchall()
                gone = not rows or column not in {r[1] for r in rows}
            except Exception:
                gone = None
            if gone:
                logger.warning(f"[LAB-DB] dropping {table}.{column} reported {e}, and it is gone")
            else:
                state = "still stands" if gone is False else "was not read back"
                logger.warning(
                    f"[LAB-DB] {table}.{column} {state} in {_DB_PATH}: {e} — "
                    f"a new row in {table} is refused while it is NOT NULL"
                )
        finally:
            raw.close()


# SQLite's own header field for the layout of this file (PRAGMA user_version).
# 1: the roster of the file has become places (`_migrate_places`).
# 2: the file has been rebuilt once since (`_rebuild_file`).
# 3: the write-ahead log has been written back into it once since (`_fold_log`).
_LAYOUT_PLACES = 1
_LAYOUT_REBUILT = 2
_LAYOUT_FOLDED = 3

# The accounts `_migrate_places` turns into places: the participant role, and
# no course that the account leads. An account with the participant role that
# still leads a course is an educator demoted by hand.
_PLACE_ACCOUNT = (
    "u.role = 'participant' AND NOT EXISTS "
    "(SELECT 1 FROM course_educators e WHERE e.user_id = u.id)"
)


def _migrate_places() -> None:
    """Turn the roster of an older file into places, once (2026-09-23).

    Runs while the file's layout is below `_LAYOUT_PLACES` and raises it in the
    same transaction, so a later start and a second process find nothing to
    do. Four steps, over the accounts of `_PLACE_ACCOUNT`:

    1. An account on the rosters of several courses becomes one account per
       course. It stays with its latest active membership in a course that is
       not archived, and keeps there what it made outside any course. Every
       further membership moves to a new account without a name, together
       with the works, drafts and adapters made in that course, and receives
       a copy of every perspective the account kept, with its versions; an
       entry of that course's palette that names one of them names the copy.
    2. Every such account loses its username, display name and email: no
       personal data on the platform, for devices are not persons
       (docs/DEVELOPMENT_DECISIONS.md).
    3. A deactivated account becomes no place: its memberships count as
       removed.
    4. Every membership of such an account receives the next free number in
       its course, in the order the memberships were made, a removed one
       included, so its number passes to no other device.

    An account that leads a course keeps its name and gets no place. The names
    are overwritten in the file itself (`secure_delete`). A place made this
    way has no code until its leader gives it one.

    A failure is logged, never raised, and the next start tries again. Once
    the places stand, `_rebuild_file` runs until it has run once, and then
    `_fold_log` until it has written the log back once.
    """
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        version = cur.execute("PRAGMA user_version").fetchone()[0]
        if version < _LAYOUT_PLACES:
            try:
                _places_once(raw, cur)
            except Exception as e:
                logger.warning(f"[LAB-DB] places not migrated in {_DB_PATH}: {e}")
            version = cur.execute("PRAGMA user_version").fetchone()[0]
        if version == _LAYOUT_PLACES:
            _rebuild_file(cur)
            version = cur.execute("PRAGMA user_version").fetchone()[0]
        if version == _LAYOUT_REBUILT:
            _fold_log(cur)
    except Exception as e:
        logger.warning(f"[LAB-DB] layout of {_DB_PATH} not read: {e}")
    finally:
        raw.close()


def _places_once(raw, cur) -> None:
    """The steps of `_migrate_places` and the new layout, in one transaction."""
    secure = cur.execute("PRAGMA secure_delete").fetchone()[0]
    cur.execute("PRAGMA secure_delete = ON")
    try:
        cur.execute("BEGIN IMMEDIATE")
        try:
            # A second process may have been first while this one waited.
            if cur.execute("PRAGMA user_version").fetchone()[0] >= _LAYOUT_PLACES:
                raw.rollback()
                return
            done = _places_from_roster(cur)
            if done is None:
                raw.rollback()
                return
            cur.execute(f"PRAGMA user_version = {_LAYOUT_PLACES}")
            raw.commit()
        except Exception:
            raw.rollback()
            raise
    finally:
        cur.execute(f"PRAGMA secure_delete = {int(secure)}")
    split, stripped, withdrawn, numbered = done
    if split or stripped or withdrawn or numbered:
        logger.info(
            f"[LAB-DB] places: {split} memberships moved to accounts of their own, "
            f"names removed from {stripped} participant accounts, "
            f"{withdrawn} memberships of deactivated accounts removed, "
            f"{numbered} memberships numbered"
        )


def _rebuild_file(cur) -> None:
    """Rebuild the file once the places stand (VACUUM), then raise the layout
    to `_LAYOUT_REBUILT`; a start that ends in between rebuilds again.

    `secure_delete` overwrites what is deleted while it is on. Where SQLite ran
    with it off, an account deleted before the places left its row in a free
    page of the file, its names among them, and the dropped columns of the
    course key left theirs. The rebuild writes the rows that stand into new
    pages; the next checkpoint (`_fold_log`) writes those over the old ones
    and cuts the file to its new length.
    """
    try:
        cur.execute("VACUUM")
        cur.execute(f"PRAGMA user_version = {_LAYOUT_REBUILT}")
    except Exception as e:
        logger.warning(
            f"[LAB-DB] {_DB_PATH} not rebuilt: {e}; rows deleted before the places "
            f"can stay readable in its free pages until a start rebuilds it"
        )


def _fold_log(cur) -> None:
    """Write the write-ahead log back into the file and cut it (checkpoint),
    then raise the layout to `_LAYOUT_FOLDED`; until then every start tries
    again. Until a checkpoint the file itself holds the pages the log has
    replaced, the removed names among them, and the log keeps its frames of
    before the places until it is cut: a start killed after the places were
    committed, or a checkpoint that found a reader, left them readable.

    A start at `_LAYOUT_FOLDED` takes no checkpoint of its own. One that
    finds a reader waits for it and holds every other process's writes for
    the busy timeout meanwhile; SQLite writes the log back as it runs."""
    try:
        busy, _log, _moved = cur.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    except Exception as e:
        logger.warning(f"[LAB-DB] write-ahead log of {_DB_PATH} not written back: {e}")
        return
    if busy:
        logger.warning(
            f"[LAB-DB] a reader held {_DB_PATH}: the file itself keeps rows that the "
            f"write-ahead log has replaced, and the next start writes the log back"
        )
        return
    try:
        cur.execute(f"PRAGMA user_version = {_LAYOUT_FOLDED}")
    except Exception as e:
        logger.warning(f"[LAB-DB] layout of {_DB_PATH} not raised to {_LAYOUT_FOLDED}: {e}")


def _existing(cur, table: str, row_id):
    """`row_id` where that row of `table` exists, else None."""
    if row_id is None:
        return None
    found = cur.execute(f"SELECT 1 FROM {table} WHERE id = ?", (row_id,)).fetchone()
    return row_id if found else None


def _copy_row(cur, table: str, row_id: int, **values) -> int:
    """Insert a copy of one row of `table` and return the new id.

    `values` replace columns. Every other reference of the row is copied only
    where the row it names exists: a row deleted while the foreign keys were
    off, as they are in the sqlite3 shell, left references that point nowhere,
    and one of them in a new row would roll the whole migration back at every
    start.
    """
    columns = [r[1] for r in cur.execute(f"PRAGMA table_info({table})") if r[1] != "id"]
    refs = {r[3]: (r[2], r[4] or "id") for r in cur.execute(f"PRAGMA foreign_key_list({table})")}
    exprs, params = [], []
    for column in columns:
        if column in values:
            exprs.append("?")
            params.append(values[column])
        elif column in refs:
            parent, key = refs[column]
            exprs.append(
                f"CASE WHEN EXISTS (SELECT 1 FROM {parent} p WHERE p.{key} = t.{column}) "
                f"THEN t.{column} END"
            )
        else:
            exprs.append(f"t.{column}")
    cur.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"SELECT {', '.join(exprs)} FROM {table} t WHERE t.id = ?",
        (*params, row_id),
    )
    return cur.lastrowid


def _copy_perspectives(cur, account: int, own: int, course: int) -> None:
    """Give `own` a copy of every perspective `account` kept, with its versions
    and with the forks among them pointing at the copies, and point the
    entries of `course`'s palette that name one of them at its copy. A
    version the account wrote names `own`: `prompt_versions.created_by` has
    no ON DELETE rule, and a copy that named `account` would refuse the
    deletion of `account` with its course."""
    copies = {}
    for (prompt,) in cur.execute(
        "SELECT id FROM interception_prompts WHERE owner_id = ? ORDER BY id", (account,)
    ).fetchall():
        copies[prompt] = _copy_row(cur, "interception_prompts", prompt, owner_id=own)
    for prompt, copy in copies.items():
        cur.execute(
            "UPDATE interception_prompts SET forked_from_prompt_id = ? "
            "WHERE owner_id = ? AND forked_from_prompt_id = ?", (copy, own, prompt))
        for version, by in cur.execute(
            "SELECT id, created_by FROM prompt_versions WHERE prompt_id = ? ORDER BY id", (prompt,)
        ).fetchall():
            _copy_row(cur, "prompt_versions", version, prompt_id=copy,
                      created_by=own if by == account else _existing(cur, "users", by))
        cur.execute(
            "UPDATE course_palette_items SET prompt_id = ? WHERE course_id = ? AND prompt_id = ?",
            (copy, course, prompt))


def _places_from_roster(cur):
    """The four steps of `_migrate_places`, inside its transaction.

    Returns (moved memberships, accounts stripped of names, memberships of
    deactivated accounts removed, memberships numbered), or None where the
    columns of the places are missing.
    """
    if "place_number" not in _column_names(cur, "course_memberships"):
        logger.warning(
            f"[LAB-DB] places not migrated in {_DB_PATH}: "
            f"course_memberships.place_number is missing"
        )
        return None

    moved = 0
    shared = cur.execute(
        f"SELECT u.id FROM users u WHERE {_PLACE_ACCOUNT} AND "
        f"(SELECT COUNT(*) FROM course_memberships m WHERE m.user_id = u.id) > 1"
    ).fetchall()
    for (account,) in shared:
        # The account stays in the course the pupil joined last among those
        # that still run; a course that is missing counts as archived.
        memberships = cur.execute(
            "SELECT m.id, m.course_id FROM course_memberships m "
            "LEFT JOIN courses c ON c.id = m.course_id WHERE m.user_id = ? "
            "ORDER BY (m.status = 'active' AND COALESCE(c.archived, 1) = 0) DESC, "
            "m.joined_at DESC, m.id DESC", (account,)
        ).fetchall()
        for membership, course in memberships[1:]:
            own = _copy_row(cur, "users", account, email=None, username=None, display_name="")
            cur.execute("UPDATE course_memberships SET user_id = ? WHERE id = ?", (own, membership))
            for table in ("works", "prompt_drafts", "lora_adapters"):
                cur.execute(
                    f"UPDATE {table} SET owner_id = ? WHERE owner_id = ? AND course_id = ?",
                    (own, account, course),
                )
            _copy_perspectives(cur, account, own, course)
            moved += 1

    stripped = cur.execute(
        f"UPDATE users SET username = NULL, display_name = '', email = NULL "
        f"WHERE id IN (SELECT u.id FROM users u WHERE {_PLACE_ACCOUNT}) "
        f"AND (username IS NOT NULL OR email IS NOT NULL OR display_name <> '')"
    ).rowcount

    # A code given to the place of a deactivated account would admit nobody
    # (auth_service._check_place_session), and no route reactivates one.
    withdrawn = cur.execute(
        f"UPDATE course_memberships SET status = 'removed' WHERE status = 'active' "
        f"AND user_id IN (SELECT u.id FROM users u WHERE {_PLACE_ACCOUNT} AND NOT u.is_active)"
    ).rowcount

    unnumbered = cur.execute(
        f"SELECT m.id, m.course_id FROM course_memberships m JOIN users u ON u.id = m.user_id "
        f"WHERE {_PLACE_ACCOUNT} AND m.place_number IS NULL "
        f"ORDER BY m.course_id, m.joined_at, m.id"
    ).fetchall()
    for membership, course in unnumbered:
        number = cur.execute(
            "SELECT COALESCE(MAX(place_number), 0) + 1 FROM course_memberships "
            "WHERE course_id = ?", (course,)
        ).fetchone()[0]
        cur.execute(
            "UPDATE course_memberships SET place_number = ? WHERE id = ?", (number, membership)
        )
    return moved, stripped, withdrawn, len(unnumbered)


def register_teardown(app) -> None:
    """Remove the scoped session at the end of every Flask request."""
    @app.teardown_appcontext
    def _remove_session(exc=None):  # noqa: ANN001
        SessionLocal.remove()
