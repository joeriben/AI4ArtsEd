"""
Places — how a device enters a course.

A place is a number in its course and a code. The leader says how many devices
the course has, the platform makes as many places, each with its own code, and
shows every code once. Who uses which device is written down by the
institution, on paper or on the leader's computer; the platform keeps the
number and the code, and no field anywhere takes a name to a place. A lost code
is replaced on its own place, and the sessions that entered with the old one
end at their next request (auth_service._check_place_session). Two devices may
share a code: the number of places is what was handed out, and nothing counts
the devices.

A code is five characters from an alphabet of 25, one of 9,765,625; a simple
five-character code is secure enough for this purpose. It both
admits and names its place, so a login finds the place from the code alone,
and the code is kept as its SHA-256 under a unique index. A salted password
hash, as the course key had, cannot be looked up: every login would have to
try every place. The plaintext is in the response that hands it out and
nowhere else; it is never logged. At five characters the hash keeps the codes
out of plain view in the file, and whoever holds the file recovers every code
from its hash within seconds. The login counts the codes of the right
form that name no active place, per client address, and refuses every
entry from an address that has spent its budget (lab/login_attempts.py).

A course can be entered while its access window is open: until
`Course.access_until`, which the leader sets and can end at once. Unset is
closed, and an archived course is closed as well.

Location: devserver/my_app/lab/place_codes.py
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import secrets
import unicodedata
from typing import Optional

from .models import Course, CourseMembership

# Unambiguous alphabet: no 0/O, 1/I/L, 5/S, 8/B, 2/Z — safe to read aloud/type.
_ALPHABET = "ACDEFGHJKMNPQRTUVWXY34679"
CODE_LENGTH = 5


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def as_aware_utc(dt: Optional[_dt.datetime]) -> Optional[_dt.datetime]:
    """SQLite hands back a naive datetime even for a timezone-aware column.
    Every value this layer writes is UTC, so a naive one is read as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def iso_utc(dt: Optional[_dt.datetime]) -> Optional[str]:
    """ISO 8601 with its offset, so a browser reads the moment and not a
    wall-clock time of its own zone."""
    aware = as_aware_utc(dt)
    return aware.isoformat() if aware is not None else None


def generate_code() -> str:
    """A fresh code, e.g. "K7M3Q"."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


def normalise_code(raw: str) -> str:
    """The form the hash is taken of: the letters and digits of the input in
    upper case, so "k7m3q", "K7M 3Q" and "„K7M-3Q.“" enter the same place as
    "K7M3Q". NFKC first, so full-width letters count as the letters. A line of
    the course page's "Copy" text, "Place 3: K7M3Q" in any language, enters
    with what follows its colon. The whole text, one line per place, has no
    form, and neither has a line with a second colon: either would enter the
    place its last code names. Spaces, dashes, quotes, the invisible format
    characters a paste carries along (soft hyphen, zero-width space) and every
    other mark go. A generated code is unchanged by all of this, so no stored
    hash changes with it."""
    text = unicodedata.normalize("NFKC", raw or "").upper()
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1 or lines[0].count(":") > 1:
        return ""
    return "".join(ch for ch in lines[0].rpartition(":")[2] if ch.isalnum())


def hash_code(raw: str) -> str:
    return hashlib.sha256(normalise_code(raw).encode("utf-8")).hexdigest()


def access_open(course: Course, *, now: Optional[_dt.datetime] = None) -> bool:
    """Whether the codes of the course's places enter it now."""
    if course.archived:
        return False
    until = as_aware_utc(course.access_until)
    return until is not None and until > (now or _utcnow())


def issue_code(db, place: CourseMembership) -> str:
    """Give `place` a new code and return it in its written form.

    The place's previous code stops at once, because only one hash is kept,
    and so do the sessions that entered with it: they remember
    `code_issued_at`. `place` must already be in `db`; it is flushed, so the
    next draw in the same transaction sees this code as taken.
    """
    for _ in range(8):
        plain = generate_code()
        digest = hash_code(plain)
        taken = db.query(CourseMembership.id).filter(
            CourseMembership.code_hash == digest
        ).first()
        if taken is None:
            place.code_hash = digest
            place.code_issued_at = _utcnow()
            db.flush()
            return plain
    # An installation holds some thousands of places among 9.8 million codes;
    # eight draws that all meet a code in use mean the random source is broken,
    # and a place must never be handed a code another holds.
    raise RuntimeError("no unused place code after eight draws")


def code_stamp(place: CourseMembership) -> Optional[str]:
    """What a session remembers of the code it entered with."""
    return iso_utc(place.code_issued_at)


def course_stamp(course: Course) -> Optional[str]:
    """What a session remembers of the course it entered. SQLite gives the id
    of the newest course, once it is deleted, to the next course made
    (`courses.id` has no AUTOINCREMENT); the moment each was made tells the
    two apart."""
    return iso_utc(course.created_at)


def has_code_form(raw: str) -> bool:
    """Whether `raw` could be a code at all: five characters of the alphabet
    once normalised. An entry of another length, or with any other letter or
    digit (of ASCII: 0, O, 1, I, L, 5, S, 8, B, 2, Z), names no place of any
    course, whoever sends it."""
    code = normalise_code(raw)
    return len(code) == CODE_LENGTH and all(ch in _ALPHABET for ch in code)


def find_place(db, raw: str) -> Optional[CourseMembership]:
    """The place whose current code `raw` is, or None."""
    code = normalise_code(raw)
    if len(code) != CODE_LENGTH:
        return None
    return (
        db.query(CourseMembership)
        .filter(CourseMembership.code_hash == hash_code(code))
        .first()
    )
