"""
Tests for the start-up migration of an older lab.db into places (2026-09-23;
lab/db.py `_ensure_indexes`, `_drop_columns`, `_migrate_places`).

A file in the schema before the places — `_OLD_TABLES` is the DDL the models
produced up to 2026-09-23 for the three tables the change touches — holding a
roster is opened by `init_db()` in a fresh interpreter: db.py binds its engine
to AI4ARTSED_DB_PATH at import time, and the other lab tests in this process
have bound it to their own files already. Afterwards:
  - `courses` has lost join_code with its unique index and the two columns of
    the course key, and has access_until; the ORM creates a new course;
  - every account with the participant role has lost its username, display
    name and email, and the educator has kept theirs;
  - every participant membership has a number in its course, in the order
    the members joined, a removed one included;
  - the code index and the place index exist;
  - a second start changes nothing;
  - an account on the rosters of two courses becomes one account per course,
    and what it made in a course goes with that course's account; it stays
    in the course it joined last among those that are not archived, and the
    account of every other course receives copies of its perspectives, with
    their versions, their forks and the palette entries of that course;
  - an account with the participant role that leads a course keeps its name
    and gets no number;
  - the migration runs once: the file's layout records it, and a named
    participant written afterwards keeps the name through the next start;
  - the removed names are gone from the bytes of the file while the process
    that migrated it still holds it open;
  - a migrated file has the columns and indexes of a fresh one;
  - a column that cannot be dropped keeps its index;
  - a deactivated participant becomes no place, and a creator that no longer
    exists does not stop the migration;
  - a write-ahead log a reader held is written back at the next start, a
    start after that takes no checkpoint of its own, and a row deleted before
    the places is gone from the bytes of the file.

Run: python3 -m pytest devserver/tests/test_lab_places_migration.py -q
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from file_modules import DEVSERVER

_OLD_TABLES = """
CREATE TABLE users (
    id INTEGER NOT NULL,
    email VARCHAR(255),
    username VARCHAR(120),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(11) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    locale VARCHAR(8) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_by INTEGER,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (email),
    UNIQUE (username),
    FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE courses (
    id INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    safety_level VARCHAR(16) NOT NULL,
    join_code VARCHAR(16) NOT NULL,
    educator_can_view_participant_works BOOLEAN NOT NULL,
    archived BOOLEAN NOT NULL,
    access_key_hash VARCHAR(255),
    access_key_expires_at DATETIME,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_courses_join_code ON courses (join_code);
CREATE TABLE course_memberships (
    id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status VARCHAR(7) NOT NULL,
    joined_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_course_member UNIQUE (course_id, user_id),
    FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
"""

_T = "2026-09-01 10:00:00"

_ROWS = """
INSERT INTO users VALUES
  (1, 'edu@example.org', 'edu', 'x', 'educator', 'Edu Cator', 'de', 1, NULL, '{t}'),
  (2, NULL, 'pupil_c', '!', 'participant', 'Clara C.', 'de', 1, 1, '{t}'),
  (3, 'kid@example.org', 'pupil_a', '!', 'participant', 'Anna A.', 'de', 1, 1, '{t}'),
  (4, NULL, 'pupil_b', '!', 'participant', 'Ben B.', 'de', 1, 1, '{t}'),
  (5, NULL, 'pupil_d', '!', 'participant', 'Dora D.', 'de', 1, 1, '{t}');
INSERT INTO courses VALUES
  (1, 'Herbst', '', 'youth', 'ABC234', 0, 0, 'pbkdf2:sha256$old', '2026-09-02 10:00:00', '{t}'),
  (2, 'Winter', '', 'kids', 'DEF567', 0, 0, NULL, NULL, '{t}');
INSERT INTO course_memberships VALUES
  (1, 1, 2, 'active',  '2026-09-01 12:00:00'),
  (2, 1, 3, 'active',  '2026-09-01 11:00:00'),
  (3, 1, 4, 'removed', '2026-09-01 13:00:00'),
  (4, 2, 5, 'active',  '2026-09-01 09:00:00');
""".format(t=_T)

# Pupil 6 is on the rosters of both courses and made something in each and
# outside any. Account 7 has the participant role and leads course 1: an
# educator demoted by hand.
_MORE = """
INSERT INTO users VALUES
  (6, NULL, 'pupil_e', 'h6', 'participant', 'Emil E.', 'de', 1, 1, '{t}'),
  (7, 'fritz@example.org', 'fritz', 'h7', 'participant', 'Fritz F.', 'de', 1, NULL, '{t}');
INSERT INTO course_memberships VALUES
  (5, 1, 6, 'active', '2026-09-01 14:00:00'),
  (6, 2, 6, 'active', '2026-09-01 08:00:00'),
  (7, 2, 7, 'active', '2026-09-01 15:00:00');
INSERT INTO course_educators VALUES (1, 1, 7, 'owner');
INSERT INTO works (id, owner_id, course_id, run_id, config_name, title, original_prompt,
                   transformed_prompt, safety_level, media_type, is_draft, notes, created_at)
VALUES
  (1, 6, 1, 'run_herbst', '', '', '', '', 'youth', 'image', 1, '', '{t}'),
  (2, 6, 2, 'run_winter', '', '', '', '', 'kids', 'image', 1, '', '{t}'),
  (3, 6, NULL, 'run_none', '', '', '', '', 'youth', 'image', 1, '', '{t}');
INSERT INTO prompt_drafts VALUES
  (1, 6, 1, 'input', '', 'herbst', '{t}'),
  (2, 6, 2, 'input', '', 'winter', '{t}');
INSERT INTO lora_adapters VALUES
  (1, 'herbst.safetensors', 'H', '', '', 6, 1, 'none', '{t}', '{t}'),
  (2, 'winter.safetensors', 'W', '', '', 6, 2, 'none', '{t}', '{t}');
INSERT INTO interception_prompts (id, owner_id, name, pipeline, context_text, is_published,
                                  created_at, updated_at)
VALUES (1, 6, 'P', 'text_transformation', '"x"', 0, '{t}', '{t}');
""".format(t=_T)

# Every name `_ROWS` gives a participant account.
_NAMES = ("pupil_a", "Anna A.", "kid@example.org", "pupil_b", "Ben B.",
          "pupil_c", "Clara C.", "pupil_d", "Dora D.")

# With `_MORE`: pupil 6 kept a second perspective, a fork of the first, and a
# version of the first, and the palettes of both courses hold the fork.
_PERSPECTIVES = """
INSERT INTO interception_prompts (id, owner_id, name, pipeline, context_text, is_published,
                                  forked_from_prompt_id, created_at, updated_at)
VALUES (2, 6, 'Q', 'text_transformation', '"y"', 1, 1, '{t}', '{t}');
INSERT INTO prompt_versions (id, prompt_id, version_no, name, context_text, created_at,
                             created_by)
VALUES (1, 1, 1, 'P0', '"w"', '{t}', 6);
INSERT INTO course_palette_items (id, course_id, source_type, prompt_id, position, enabled,
                                  created_at)
VALUES (1, 1, 'custom', 2, 0, 1, '{t}'), (2, 2, 'custom', 2, 0, 1, '{t}');
""".format(t=_T)

_START = r"""
import sys
sys.path.insert(0, sys.argv[1])
from my_app.lab.db import init_db, SessionLocal
from my_app.lab import models as M
init_db()
if len(sys.argv) > 2:
    db = SessionLocal()
    db.add(M.Course(name=sys.argv[2]))
    db.commit()
print("started")
"""

# The tables the places leave alone, as every running install has them.
_TABLES = r"""
import sys
sys.path.insert(0, sys.argv[1])
from my_app.lab.db import Base, engine
from my_app.lab import models  # noqa: F401
Base.metadata.create_all(bind=engine)
print("started")
"""

# Starts, then reads the file and its write-ahead log while a connection holds
# them open, and prints which of the given names the bytes contain.
_BYTES = r"""
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from my_app.lab.db import init_db, engine
init_db()
path = Path(sys.argv[2])
wal = Path(str(path) + "-wal")
with engine.connect():
    data = path.read_bytes() + (wal.read_bytes() if wal.exists() else b"")
print("found:" + ",".join(n for n in sys.argv[3:] if n.encode() in data))
print("started")
"""

# Starts, with a reader holding the file when the third argument is "held",
# and ends without closing anything: nothing but a start writes the log back.
_HELD = r"""
import os
import sqlite3
import sys
sys.path.insert(0, sys.argv[1])
if sys.argv[3] == "held":
    reader = sqlite3.connect(sys.argv[2], isolation_level=None)
    reader.execute("PRAGMA journal_mode=WAL")
    reader.execute("BEGIN")
    reader.execute("SELECT COUNT(*) FROM users").fetchone()
from my_app.lab.db import init_db
init_db()
print("started", flush=True)
os._exit(0)
"""


def _run(script: str, db_path: Path, *args: str) -> str:
    env = dict(os.environ, AI4ARTSED_DB_PATH=str(db_path))
    out = subprocess.run([sys.executable, "-c", script, str(DEVSERVER), *args],
                         env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().endswith("started"), out.stdout + out.stderr
    return out.stdout


def _start(db_path: Path, new_course: str = "") -> None:
    _run(_START, db_path, *([new_course] if new_course else []))


def _old_file(tmp_path: Path, more: str = "") -> Path:
    """An older file holding `_ROWS`. With `more`, the tables the places leave
    alone are made first and `more` goes in after."""
    path = tmp_path / "lab_old.db"
    con = sqlite3.connect(path)
    con.executescript(_OLD_TABLES + _ROWS)
    con.commit()
    con.close()
    if more:
        _run(_TABLES, path)
        con = sqlite3.connect(path)
        con.executescript(more)
        con.commit()
        con.close()
    return path


def _version(path: Path) -> int:
    con = sqlite3.connect(path)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


def _read(path: Path):
    con = sqlite3.connect(path)
    try:
        course_cols = [r[1] for r in con.execute("PRAGMA table_info(courses)")]
        indexes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
        users = {r[0]: r[1:] for r in con.execute(
            "SELECT id, role, username, display_name, email FROM users")}
        places = {r[0]: r[1:] for r in con.execute(
            "SELECT id, course_id, place_number, code_hash FROM course_memberships")}
        courses = [r[0] for r in con.execute("SELECT name FROM courses ORDER BY id")]
        return course_cols, indexes, users, places, courses
    finally:
        con.close()


def test_an_older_file_becomes_places(tmp_path):
    path = _old_file(tmp_path)
    _start(path, new_course="Frühling")
    course_cols, indexes, users, places, courses = _read(path)

    for gone in ("join_code", "access_key_hash", "access_key_expires_at"):
        assert gone not in course_cols
    assert "access_until" in course_cols
    assert "ix_courses_join_code" not in indexes
    assert {"ix_course_memberships_code_hash", "uq_course_place_number"} <= indexes
    assert courses == ["Herbst", "Winter", "Frühling"]

    # The names are gone from every participant account, and the educator's stay.
    assert users[1] == ("educator", "edu", "Edu Cator", "edu@example.org")
    for uid in (2, 3, 4, 5):
        assert users[uid] == ("participant", None, "", None)

    # Numbers in the order the members joined, per course; no code yet.
    assert places[2][:2] == (1, 1)   # joined 11:00
    assert places[1][:2] == (1, 2)   # joined 12:00
    assert places[3][:2] == (1, 3)   # joined 13:00, removed since
    assert places[4][:2] == (2, 1)
    assert all(p[2] is None for p in places.values())


def test_a_second_start_changes_nothing(tmp_path):
    path = _old_file(tmp_path)
    _start(path)
    first = _read(path)
    _start(path)
    assert _read(path) == first


def test_an_account_on_two_rosters_becomes_one_account_per_course(tmp_path):
    path = _old_file(tmp_path, more=_MORE)
    _start(path)
    con = sqlite3.connect(path)
    try:
        members = {r[0]: r[1:] for r in con.execute(
            "SELECT id, course_id, user_id, place_number FROM course_memberships")}

        # The account stays with the course it joined last (course 1, 14:00,
        # numbered after the three of `_ROWS`); the other membership has an
        # account of its own, without a name.
        assert members[5] == (1, 6, 4)
        own = members[6][1]
        assert own != 6 and members[6] == (2, own, 1)
        assert con.execute(
            "SELECT role, username, display_name, email, password_hash, created_by "
            "FROM users WHERE id = ?", (own,)).fetchone() == (
            "participant", None, "", None, "h6", 1)

        def owners(table):
            return dict(con.execute(f"SELECT id, owner_id FROM {table}"))

        # What was made in course 2 goes with course 2's account, and what
        # was made outside any course stays with the account. Both keep the
        # perspective.
        assert owners("works") == {1: 6, 2: own, 3: 6}
        assert owners("prompt_drafts") == {1: 6, 2: own}
        assert owners("lora_adapters") == {1: 6, 2: own}
        assert con.execute(
            "SELECT owner_id, name, context_text FROM interception_prompts ORDER BY id"
        ).fetchall() == [(6, "P", '"x"'), (own, "P", '"x"')]

        # The account that leads a course keeps its name and gets no number.
        assert con.execute(
            "SELECT username, display_name, email FROM users WHERE id = 7"
        ).fetchone() == ("fritz", "Fritz F.", "fritz@example.org")
        assert members[7] == (2, 7, None)
        assert members[4] == (2, 5, 2)
    finally:
        con.close()


def test_the_migration_runs_once(tmp_path):
    path = _old_file(tmp_path)
    _start(path)
    con = sqlite3.connect(path)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 3
    # A participant with a name, written into the migrated file by hand.
    con.execute(
        "INSERT INTO users (id, email, username, password_hash, role, display_name, "
        "locale, is_active, created_at) "
        "VALUES (9, NULL, 'late', '!', 'participant', 'Late L.', 'de', 1, ?)", (_T,))
    con.commit()
    con.close()
    _start(path)
    con = sqlite3.connect(path)
    try:
        assert con.execute(
            "SELECT username, display_name FROM users WHERE id = 9"
        ).fetchone() == ("late", "Late L.")
    finally:
        con.close()


def test_the_names_leave_the_bytes_of_the_file(tmp_path):
    """Read while the migrating process holds the file open: at the last close
    SQLite folds the write-ahead log back by itself, and until then a copy of
    the main file would still hold the old rows. The educator's name is there
    to show that the bytes were read."""
    path = _old_file(tmp_path)
    out = _run(_BYTES, path, str(path), "Edu Cator", *_NAMES)
    assert "found:Edu Cator\n" in out


def _layout(path: Path):
    con = sqlite3.connect(path)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        columns = {t: [r[1:] for r in con.execute(f"PRAGMA table_info({t})")] for t in tables}
        indexes = {}
        for table in tables:
            for _seq, name, unique, origin, partial in con.execute(f"PRAGMA index_list({table})"):
                cols = [r[2] for r in con.execute(f"PRAGMA index_info({name})")]
                indexes[name] = (table, unique, origin, partial, cols)
        version = con.execute("PRAGMA user_version").fetchone()[0]
        return columns, indexes, version
    finally:
        con.close()


def test_a_migrated_file_has_the_layout_of_a_fresh_one(tmp_path):
    """Column order included: a column an older file receives is appended."""
    old = _old_file(tmp_path)
    _start(old)
    fresh = tmp_path / "lab_fresh.db"
    _start(fresh)
    assert _layout(old) == _layout(fresh)


def test_a_column_that_stays_keeps_its_index(tmp_path):
    """SQLite refuses to drop a column a view reads. The index that has to go
    before the column is dropped in the same transaction, so it stays when
    the column stays."""
    path = _old_file(tmp_path)
    con = sqlite3.connect(path)
    con.execute("CREATE VIEW course_codes AS SELECT id, join_code FROM courses")
    con.commit()
    con.close()
    _start(path)
    course_cols, indexes, users, _places, _courses = _read(path)
    assert "join_code" in course_cols and "ix_courses_join_code" in indexes
    # The steps that do not depend on it ran.
    assert "access_key_hash" not in course_cols and "access_until" in course_cols
    assert users[2] == ("participant", None, "", None)


def test_the_account_stays_in_a_course_that_still_runs(tmp_path):
    """Course 1 is archived: the account stays in course 2, though the pupil
    joined course 1 later. The account of course 1's place receives copies of
    both perspectives, the version and the fork between them, and course 1's
    palette names the copy of the fork."""
    path = _old_file(tmp_path, more=_MORE + _PERSPECTIVES
                     + "UPDATE courses SET archived = 1 WHERE id = 1;")
    _start(path)
    con = sqlite3.connect(path)
    try:
        members = {r[0]: r[1:] for r in con.execute(
            "SELECT id, course_id, user_id FROM course_memberships")}
        assert members[6] == (2, 6)
        own = members[5][1]
        assert own != 6
        assert dict(con.execute("SELECT id, owner_id FROM works")) == {1: own, 2: 6, 3: 6}

        prompts = {r[0]: r[1:] for r in con.execute(
            "SELECT id, owner_id, name, forked_from_prompt_id FROM interception_prompts")}
        assert prompts[1] == (6, "P", None) and prompts[2] == (6, "Q", 1)
        copies = {name: pid for pid, (owner, name, _fork) in prompts.items() if owner == own}
        assert set(copies) == {"P", "Q"}
        assert prompts[copies["Q"]][2] == copies["P"]
        assert sorted(con.execute("SELECT prompt_id, name, created_by FROM prompt_versions")) == [
            (1, "P0", 6), (copies["P"], "P0", own)]
        assert dict(con.execute("SELECT course_id, prompt_id FROM course_palette_items")) == {
            1: copies["Q"], 2: 2}
    finally:
        con.close()


def test_deleting_one_course_leaves_the_perspectives_of_the_other(tmp_path):
    """Course 1 keeps the account and goes as courses_routes deletes a course:
    its works, the course, then the account of its place. The place of
    course 2 keeps the copies, the version and its palette entry."""
    path = _old_file(tmp_path, more=_MORE + _PERSPECTIVES)
    _start(path)
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        own = con.execute("SELECT user_id FROM course_memberships WHERE id = 6").fetchone()[0]
        con.execute("DELETE FROM works WHERE course_id = 1")
        con.execute("DELETE FROM courses WHERE id = 1")
        con.execute("DELETE FROM users WHERE id = 6")
        con.commit()
        kept = dict(con.execute("SELECT name, owner_id FROM interception_prompts"))
        assert kept == {"P": own, "Q": own}
        assert con.execute("SELECT created_by FROM prompt_versions").fetchall() == [(own,)]
        fork = con.execute(
            "SELECT id FROM interception_prompts WHERE name = 'Q'").fetchone()[0]
        assert con.execute(
            "SELECT course_id, prompt_id FROM course_palette_items").fetchall() == [(2, fork)]
    finally:
        con.close()


def test_a_deactivated_participant_becomes_no_place(tmp_path):
    """Its membership counts as removed and keeps its number: a code given to
    it would admit nobody."""
    path = _old_file(tmp_path, more="UPDATE users SET is_active = 0 WHERE id = 5;")
    _start(path)
    con = sqlite3.connect(path)
    try:
        rows = {r[0]: r[1:] for r in con.execute(
            "SELECT id, status, place_number FROM course_memberships")}
        assert rows[4] == ("removed", 1)
        assert rows[2] == ("active", 1)
    finally:
        con.close()


def test_a_creator_that_is_gone_does_not_stop_the_migration(tmp_path):
    """Account 6 names a creator deleted while the foreign keys were off, as
    they are in the sqlite3 shell."""
    path = _old_file(tmp_path, more=_MORE + "UPDATE users SET created_by = 99 WHERE id = 6;")
    _start(path)
    con = sqlite3.connect(path)
    try:
        assert con.execute("PRAGMA user_version").fetchone()[0] == 3
        own = con.execute("SELECT user_id FROM course_memberships WHERE id = 6").fetchone()[0]
        assert own != 6
        assert con.execute("SELECT created_by FROM users WHERE id = ?", (own,)).fetchone() == (None,)
        assert con.execute("SELECT username FROM users WHERE id = 6").fetchone() == (None,)
    finally:
        con.close()


def test_a_log_a_reader_held_is_written_back_at_the_next_start(tmp_path):
    """A reader holding the file while it is migrated keeps the checkpoint
    from writing the log back, and the removed names stay in the file itself.
    The next start writes it back, though it has nothing to migrate."""
    path = _old_file(tmp_path)
    _run(_HELD, path, str(path), "held")
    assert [n for n in _NAMES if n.encode() in path.read_bytes()], "no name was held"
    assert _version(path) == 2
    _run(_HELD, path, str(path), "free")
    assert [n for n in _NAMES if n.encode() in path.read_bytes()] == []
    assert _version(path) == 3


def test_a_start_after_the_log_is_written_back_takes_no_checkpoint(tmp_path):
    """A checkpoint that finds a reader waits for it, and meanwhile holds the
    writes of every other process for the busy timeout. Once the layout
    records the log written back, a start runs none, whoever holds the file."""
    path = _old_file(tmp_path)
    _start(path)
    assert _version(path) == 3
    reader = sqlite3.connect(path, isolation_level=None)
    writer = sqlite3.connect(path, isolation_level=None)
    try:
        writer.execute("CREATE TABLE _probe (x)")
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM users").fetchone()
        # The reader's snapshot is older than the log now.
        writer.execute("INSERT INTO _probe VALUES (0)")
        env = dict(os.environ, AI4ARTSED_DB_PATH=str(path))
        out = subprocess.run([sys.executable, "-c", _START, str(DEVSERVER)], env=env,
                             capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stderr
        assert "a reader held" not in out.stderr, out.stderr
    finally:
        reader.close()
        writer.close()


def test_the_row_of_an_account_deleted_before_leaves_the_file(tmp_path):
    """A participant deleted while secure_delete was off left its row in the
    file; the start that migrates the file rebuilds it."""
    path = _old_file(tmp_path)
    con = sqlite3.connect(path)
    con.execute("PRAGMA secure_delete = OFF")
    con.execute(
        "INSERT INTO users VALUES (8, 'greta@example.org', 'pupil_g', '!', 'participant', "
        "'Greta G.', 'de', 1, 1, ?)", (_T,))
    con.commit()
    con.execute("DELETE FROM users WHERE id = 8")
    con.commit()
    con.close()
    assert b"Greta G." in path.read_bytes()
    out = _run(_BYTES, path, str(path), "Edu Cator", "Greta G.", "greta@example.org")
    assert "found:Edu Cator\n" in out
