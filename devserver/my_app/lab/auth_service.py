"""
Authentication & authorization helpers for the Lab User/Course system.

Reuses the EXISTING Flask server-side session (httpOnly cookie, app.secret_key,
supports_credentials) — the same mechanism settings_routes.py uses — but keyed on
user_id/role instead of a single boolean.

Bridge to the legacy admin (BAUPLAN P0): if the request is already authenticated
as the settings-admin (session['settings_authenticated']) but no user_id is set,
we treat it as the seeded admin user. The existing settings login is untouched.

Password hashing uses werkzeug.security exactly like settings_routes.py
(pbkdf2:sha256); devserver/scripts/set_admin_account.py writes both with it.

Location: devserver/my_app/lab/auth_service.py
"""
from __future__ import annotations

import hashlib
import logging
from functools import wraps
from typing import Optional

from flask import session, jsonify, g, request
from werkzeug.security import generate_password_hash, check_password_hash

from .db import SessionLocal
from .models import (
    User, Role, Course, CourseEducator, CourseMembership,
    CourseRole, MembershipStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Password helpers (identical scheme to settings_routes.py)
# ---------------------------------------------------------------------------
# Stored where an account has no password at all: a place enters with its
# code, and the seeded admin until a password is set. It has no method
# segment, so check_password_hash answers False for every input.
UNUSABLE_PASSWORD_HASH = "!"

# The three passwords that earlier versions built into the code: the settings
# password a fresh installation received from 2025-12-18 (6b5760e1), the one
# that replaced it on 2026-01-05 (77aa5635) and stood until 2026-11-15, which
# the first start of the lab system also copied onto the admin account
# (2026-07-05 to 2026-11-15), and the one the admin account was seeded with
# where settings_password.key was missing (2026-07-05 to 2026-11-15). All
# three stand in the history of the repository, so an installation that kept
# one is open to whoever reads it. The sign-in and the settings password
# refuse them (routes/auth_routes.py, routes/settings_routes.py), and
# scripts/set_admin_account.py does not set them. Kept as SHA-256 digests:
# the passwords are public, and the digest keeps them out of the tree.
# tests/test_set_admin_account.py checks the three against the history.
PUBLISHED_PASSWORD_DIGESTS = frozenset({
    "55f2458efe5c7c179918a90bdcd695b9220e623c34dc485291210b8698a3a879",
    "792903ba6b8e6d8f6e6a0cae6a9ae9aa9dbf46fe924c50baad12f1088afd5ff7",
    "48ce26b6e0a4ee87a1b0ed1e418e8fb2ab66e6bb4c7a8cc953bb5e9b217b59fd",
})
SET_ADMIN_COMMAND = "./venv/bin/python devserver/scripts/set_admin_account.py"


def is_published_password(plain: str) -> bool:
    """Whether `plain` is one of the passwords earlier versions built in."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest() in PUBLISHED_PASSWORD_DIGESTS


def hash_password(plain: str) -> str:
    return generate_password_hash(plain, method="pbkdf2:sha256")


def verify_password(stored_hash: str, plain: str) -> bool:
    return check_password_hash(stored_hash, plain)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def login_user(user: User) -> None:
    # A browser a place session ran in keeps its cookie; the course and the
    # place of that session must not pass to the account signing in now.
    session.pop("course_id", None)
    session.pop("course_stamp", None)
    session.pop("place_id", None)
    session.pop("place_code", None)
    # The agreement a previous sign-in of this browser made is not this one's:
    # the sign-in route sets it for the account it signs in (lab/terms.py).
    session.pop("terms_version", None)
    # Nor are the settings somebody opened in this browser with the settings
    # password before (routes/settings_routes.py, `_settings_admitted`): a
    # course leader signing in there would have had them (2026-11-15).
    session.pop("settings_authenticated", None)
    session["user_id"] = user.id
    session["user_stamp"] = account_stamp(user)
    session["role"] = user.role.value
    session.permanent = True


def login_place(place: CourseMembership) -> None:
    """Establish a session for one place of one course.

    Mirrors login_user() but additionally pins session["course_id"] — THE
    exclusivity axis (BAUPLAN Entscheid 2) — with the moment the course was
    made (`is_session_course`), and the place, with the moment the code it
    entered with was issued. A place never authenticates with a
    password; a device enters with the place's code (lab/place_codes.py).
    The binding is fixed for the lifetime of the session, and every request
    checks it again (`_check_place_session`).

    A settings-admin flag the browser still carries goes: the device is a
    place now, and `current_user` would bridge the flag to the admin account
    the moment the place session ends.
    """
    from .place_codes import code_stamp, course_stamp
    session.pop("settings_authenticated", None)
    session.pop("terms_version", None)
    session["user_id"] = place.user_id
    session["user_stamp"] = account_stamp(place.user)
    session["role"] = Role.participant.value
    session["course_id"] = place.course_id
    session["course_stamp"] = course_stamp(place.course)
    session["place_id"] = place.id
    session["place_code"] = code_stamp(place)
    session.permanent = True


def set_active_course(course: Optional[Course]) -> None:
    """The course a leader or an admin works in, chosen in the sign-in field
    of the header (POST /api/auth/active-course, 2026-11-14).

    Explicit only: a sign-in does NOT set a course (Entscheid 1). None is no
    course: the account works in its own use ("Eigene Nutzung", decided
    2026-10-31), at the installation's level. A course is pinned with the
    moment it was made, as a place session pins it (`login_place`): the
    safety level of the course applies only to the course the session chose
    (`is_session_course`), and `_check_chosen_course` ends a choice whose
    course is gone or no longer led by the account.
    """
    from .place_codes import course_stamp
    if course is None:
        session.pop("course_id", None)
        session.pop("course_stamp", None)
    else:
        session["course_id"] = course.id
        session["course_stamp"] = course_stamp(course)


def current_course_id() -> Optional[int]:
    """The course_id pinned in the session — a participant's fixed course
    binding OR the educator's explicitly chosen active course — or None."""
    _check_place_session()
    _check_chosen_course()
    cid = session.get("course_id")
    return int(cid) if cid is not None else None


def is_session_course(course) -> bool:
    """Whether `course` is the course this session entered and not one made
    later under its id (place_codes.course_stamp). A session that carries no
    stamp, a participant session from before the places, matches none."""
    from .place_codes import course_stamp
    return "course_stamp" in session and session["course_stamp"] == course_stamp(course)


def account_stamp(user: User) -> Optional[str]:
    """What a session remembers of the account it signed in as: the moment
    the account was made, as `place_codes.course_stamp` does for a course. A
    favourite kept under the account keeps it too (routes/favorites_routes.py,
    `_asker`)."""
    from .place_codes import iso_utc
    return iso_utc(user.created_at)


def _is_session_account(user: User) -> bool:
    """Whether `user` is the account this session signed in as and not one
    made later under its id. SQLite gives the id of the newest account, once
    it is deleted, to the next account made (`users.id` has no
    AUTOINCREMENT), and a browser still signed in as the deleted account
    would act as the new one. A session signed in before the stamp
    (2026-09-24) takes the stamp of the account it reaches now."""
    stamp = account_stamp(user)
    if "user_stamp" not in session:
        session["user_stamp"] = stamp
        return True
    return session["user_stamp"] == stamp


def current_place_number() -> Optional[int]:
    """The number of the place this session entered with, or None: an
    educator, an admin, an anonymous device, or a place session that has just
    ended."""
    _check_place_session()
    pid = session.get("place_id")
    if pid is None or _place_unverified():
        return None
    with _short_session() as db:
        place = db.get(CourseMembership, int(pid))
        return place.place_number if place is not None else None


def logout_user() -> None:
    session.pop("user_id", None)
    session.pop("user_stamp", None)
    session.pop("role", None)
    session.pop("course_id", None)
    session.pop("course_stamp", None)
    session.pop("place_id", None)
    session.pop("place_code", None)
    session.pop("terms_version", None)
    # The sign-in through the settings password: kept, it made the browser the
    # first admin again after the sign-out (`current_user`), and what the
    # browser kept then belonged to that account.
    session.pop("settings_authenticated", None)


# The request attribute that says what this request's check of its place
# session found: unset, _CHECKED, or _UNVERIFIED. On the request and not on
# `flask.g`: `g` belongs to the app context, and a request that finds one
# already pushed inherits the previous request's `g` —
# services/safety_level_resolver.py keeps its memo on the request for the
# same reason.
_PLACE_CHECK = "_lab_place_session_check"
_CHECKED = "checked"
_UNVERIFIED = "unverified"


def _check_place_session() -> None:
    """End a place session that its place no longer admits. Once per request.

    A place session holds while its place is active and still carries the code
    the session entered with, while its course exists and is open (access
    window, archived), and while its account is active and a participant
    account. The course key this replaced was checked at login alone: a
    revoked key and a name taken off the roster left running sessions
    standing until they expired. A participant session from before the
    places, which holds no place, ends here as well.

    A place session is one that claims the participant role or holds a
    place; a session that reaches the account of a place without either ends
    in `current_user`. The check runs before the view (`check_place_session`),
    so the cookie carries an end even where the response is streamed.

    An ended session keeps its course, with the moment the course was made:
    the device stays under the course's safety level
    (services/safety_level_resolver.py), as a session under the course key
    stayed until it expired, and falls to the installation's level only
    through a sign-out. The account, the place and a settings-admin flag go.

    Where the check itself fails (the database refuses), this request is
    served without the place's account and under the course's level, and the
    session stays for the next request to check.
    """
    try:
        req = request._get_current_object()
    except RuntimeError:
        return  # outside a request there is no session to check
    if getattr(req, _PLACE_CHECK, None) is not None:
        return
    setattr(req, _PLACE_CHECK, _CHECKED)
    if session.get("role") != Role.participant.value and session.get("place_id") is None:
        return
    try:
        admitted = _place_admits_session()
    except Exception:
        logger.exception("[AUTH] place session not checked: course=%s place=%s",
                         session.get("course_id"), session.get("place_id"))
        setattr(req, _PLACE_CHECK, _UNVERIFIED)
        g.pop("user", None)
        return
    if admitted:
        return
    logger.info("[AUTH] place session ended: course=%s place=%s",
                session.get("course_id"), session.get("place_id"))
    _end_place_session()
    g.pop("user", None)


def check_place_session() -> None:
    """Check this request's place session before its view runs; registered in
    routes/auth_routes.py for every request of the app. A streamed response
    writes its cookie before its body: an end reached inside the body
    (Resona's chat stream, the interception event stream) stayed in memory,
    and the cookie kept the place for the next request. A file of the
    frontend is served without the check: reading the session makes Flask
    add `Vary: Cookie` to the response. A leader's chosen course is checked
    here as well (`_check_chosen_course`), for the same reason."""
    if request.path.startswith("/api/"):
        _check_place_session()
        _check_chosen_course()


# The request attribute that says the chosen course of this request's session
# has been checked; on the request for the reason given at _PLACE_CHECK.
_CHOSEN_CHECK = "_lab_chosen_course_check"


def _check_chosen_course() -> None:
    """End a leader's choice of a course the account can no longer work in.
    Once per request.

    A choice (`set_active_course`) holds while its course exists, is the
    course that was chosen and not one made later under its id
    (`is_session_course`), and is led by the account (`is_course_educator`;
    an admin passes). A co-leader taken off a course, or a course deleted,
    ends it: the course leaves the session, and the account works in its own
    use again, at the installation's level. Without this, the session would
    keep the course of an account that no longer leads it, for as long as the
    session lives: its safety level, and its adapters for a run that names no
    course (services/lora_register.py, `session_scope`).

    A place session is no choice and is checked in `_check_place_session`; a
    session without an account keeps its course (an ended place session
    stays under its course's level, see there). Where the check itself
    fails, the choice stays for the next request to check.
    """
    try:
        req = request._get_current_object()
    except RuntimeError:
        return  # outside a request there is no session to check
    if getattr(req, _CHOSEN_CHECK, False):
        return
    setattr(req, _CHOSEN_CHECK, True)
    cid = session.get("course_id")
    if cid is None or session.get("place_id") is not None:
        return
    if session.get("role") == Role.participant.value:
        return
    try:
        user = current_user()
        if user is None or user.role == Role.participant:
            return
        with _short_session() as db:
            course = db.get(Course, int(cid))
            holds = course is not None and is_session_course(course)
        holds = holds and is_course_educator(user, int(cid))
    except Exception:
        logger.exception("[AUTH] chosen course not checked: course=%s", cid)
        return
    if not holds:
        logger.info("[AUTH] chosen course %s left the session of account %s", cid, user.id)
        set_active_course(None)


def _place_unverified() -> bool:
    """Whether this request's place session could not be checked."""
    try:
        req = request._get_current_object()
    except RuntimeError:
        return False
    return getattr(req, _PLACE_CHECK, None) == _UNVERIFIED


def place_session_unverified() -> bool:
    """Whether the check of this request's place session failed
    (`_check_place_session`): the request runs without the place's account,
    and the session stays for the next request to check."""
    _check_place_session()
    return _place_unverified()


def _end_place_session() -> None:
    """Take the account and the place out of the session. The course stays,
    with the moment it was made."""
    for key in ("user_id", "user_stamp", "role", "place_id", "place_code",
                "settings_authenticated"):
        session.pop(key, None)


def _place_admits_session() -> bool:
    from .place_codes import access_open, code_stamp
    place_id = session.get("place_id")
    if place_id is None:
        return False
    with _short_session() as db:
        place = db.get(CourseMembership, int(place_id))
        if place is None or place.status != MembershipStatus.active:
            return False
        if place.user_id != session.get("user_id") or place.course_id != session.get("course_id"):
            return False
        if not place.code_hash or code_stamp(place) != session.get("place_code"):
            return False
        if place.course is None or not access_open(place.course):
            return False
        user = place.user
        return user is not None and user.is_active and user.role == Role.participant


def _short_session():
    """A Session of its own for the check that runs on every request: the
    scoped session returns its connection to the pool only at app-context
    teardown, which for a generation is minutes, and holding one that long
    exhausts the pool under a class (services/safety_level_resolver.py)."""
    from sqlalchemy.orm import Session as _Session
    from .db import engine
    return _Session(engine)


def current_user() -> Optional[User]:
    """Return the authenticated User, or None.

    Bridges the legacy admin login: if the request is authenticated as the
    settings-admin (session['settings_authenticated']) but no user_id is set,
    we treat it as the seeded admin user. This keeps the existing admin panel
    and the new system consistent without touching settings_routes.py.
    A place session that could not be checked in this request has no user,
    and neither has a session that holds the account of a place without
    having entered it, nor one that signed in as an account deleted since,
    whose id SQLite has given to a new account (`_is_session_account`).
    """
    _check_place_session()
    if _place_unverified():
        return None
    if "user" in g:
        return g.user

    uid = session.get("user_id")
    user = None
    db = SessionLocal()
    if uid is not None:
        user = db.get(User, uid)
        if user is not None and user.role == Role.participant and session.get("place_id") is None:
            # The account of a place, held by a session that never entered it:
            # a role claim from before a demotion, or an id SQLite gave to a
            # new account (`users.id` has no AUTOINCREMENT). A place session
            # would have been checked above; this one holds no place.
            logger.info("[AUTH] session ended: account %s is a place, the session holds none", uid)
            _end_place_session()
            user = None
        elif user is not None and not _is_session_account(user):
            logger.info("[AUTH] session ended: account %s was made after the session signed in", uid)
            _end_place_session()
            user = None
    elif session.get("settings_authenticated"):
        user = db.query(User).filter(User.role == Role.admin).first()

    g.user = user
    return user


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return wrapper


def require_role(*roles):
    """Require the user to hold one of the given roles. admin always passes.

    Accepts Role members or their string values interchangeably.
    """
    role_values = {r.value if isinstance(r, Role) else r for r in roles}

    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"error": "Authentication required"}), 401
            if user.role == Role.admin or user.role.value in role_values:
                return f(*args, **kwargs)
            return jsonify({"error": "Forbidden"}), 403
        return wrapper
    return deco


# ---------------------------------------------------------------------------
# Course-scoped authorization (used from P1 onward; defined here so the whole
# authz surface lives in one module)
# ---------------------------------------------------------------------------
def is_course_educator(user: User, course_id: int, *, owner_only: bool = False) -> bool:
    if user.role == Role.admin:
        return True
    if user.role == Role.participant:
        # A place leads no course, whatever rows its account kept from before
        # it was one (lab/db.py `_migrate_places`).
        return False
    db = SessionLocal()
    q = db.query(CourseEducator).filter(
        CourseEducator.course_id == course_id,
        CourseEducator.user_id == user.id,
    )
    if owner_only:
        q = q.filter(CourseEducator.role_in_course == CourseRole.owner)
    return db.query(q.exists()).scalar()


def is_course_member(user: User, course_id: int) -> bool:
    """An active place in the course. A place is a member of the one course
    its session is bound to. A membership that holds no place — an account
    that joined with the join code before the places — grants nothing: its
    course no longer shows it and cannot end it."""
    if user.role == Role.participant:
        try:
            bound = session.get("course_id")
        except RuntimeError:
            bound = None
        if bound is None or int(bound) != int(course_id):
            return False
    db = SessionLocal()
    return db.query(
        db.query(CourseMembership).filter(
            CourseMembership.course_id == course_id,
            CourseMembership.user_id == user.id,
            CourseMembership.status == MembershipStatus.active,
            CourseMembership.place_number.isnot(None),
        ).exists()
    ).scalar()


def has_course_access(user: User, course_id: int) -> bool:
    """Educator (any role) OR active member OR admin."""
    return is_course_educator(user, course_id) or is_course_member(user, course_id)


def require_course_access(f):
    """Route must take `course_id` as a path/kwarg parameter."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        course_id = kwargs.get("course_id")
        if course_id is None or not has_course_access(user, int(course_id)):
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


def require_course_owner(f):
    """Course OWNER only (CourseRole.owner). admin passes.

    Used for course PATCH, educator add/remove, deletion-impact and DELETE.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        course_id = kwargs.get("course_id")
        if course_id is None or not is_course_educator(user, int(course_id), owner_only=True):
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


def require_course_leader(f):
    """Course LEADER = owner OR co_leader (any CourseEducator). admin passes.

    The educator-level course gate: guards palette writes, the places and the
    access window; plain participants (active members) must NOT pass.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        course_id = kwargs.get("course_id")
        if course_id is None or not is_course_educator(user, int(course_id)):
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper
