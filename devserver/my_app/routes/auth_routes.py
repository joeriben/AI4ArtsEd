"""
/api/auth/* — login, logout, identity.

Mirrors the style of settings_routes.py (Flask Blueprint, JSON, server session).
Scope:
  - POST /api/auth/login   {identifier, password} — educator/admin via
    email-or-username + password, and the agreement to the conditions of use
    (lab/terms.py, 2026-11-15).
  - POST /api/auth/participant-login {code} — a device enters an EXCLUSIVE
    course room (BAUPLAN Entscheid 2) with the code of one of the course's
    places (2026-09-23, lab/place_codes.py). NO password, NO name. The session
    then carries course_id (the exclusivity axis) and the place.
  - POST /api/auth/logout
  - POST /api/auth/active-course {course_id} — a leader or an admin chooses
    the course they work in, or null for their own use (2026-11-14).
  - GET  /api/auth/me                — identity, the session's active course_id
    and that course's name, and the number of a place session's place.

Location: devserver/my_app/routes/auth_routes.py
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, request, jsonify, session

from my_app.lab.db import SessionLocal
from my_app.lab.models import User, Role, Course, MembershipStatus
from my_app.lab.auth_service import (
    check_place_session, current_user, current_course_id, current_place_number,
    is_course_educator, is_session_course, login_user, login_place,
    logout_user, place_session_unverified, set_active_course, verify_password,
    is_published_password, SET_ADMIN_COMMAND,
)
from my_app.lab import terms
from my_app.lab.sign_in_gate import sign_in_unreadable, signed_in_user
from my_app.utils.url_ids import MAX_ROW_ID
from my_app.lab.login_attempts import attempts_of, client_address
from my_app.lab.place_codes import access_open, find_place, has_code_form

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
# Every request of the app, before its view (auth_service.check_place_session).
auth_bp.before_app_request(check_place_session)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Password login by email (educator/admin) OR username.

    EVERYONE on this endpoint authenticates with a password. Participants do NOT
    use this route — a device enters via /participant-login with the code of
    its place.
    An educator login does NOT set course_id: the educator picks the active
    course explicitly in the sign-in field of the header (BAUPLAN Entscheid
    1; POST /active-course).

    Body: {identifier, password, accept_terms?, language?}. 403
    `published_password` for a password earlier versions built into the code
    (auth_service.is_published_password), whoever's it is. 409
    `terms_required`, with `terms_version`, where the credentials hold and the
    account has not agreed to the version of the conditions that stands
    (lab/terms.py); the same request with `accept_terms` set to that version
    and `language` set to the language the text stood in keeps the agreement
    and signs in.
    """
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or "").strip()
    password = data.get("password") or ""
    if not identifier or not password:
        return jsonify({"error": "identifier and password required"}), 400
    # A password earlier versions built into the code is refused before any
    # account is looked up, so the answer says nothing about the account.
    if is_published_password(password):
        logger.warning("[AUTH] refused a password that was published with the code; "
                       "set a new one with: %s", SET_ADMIN_COMMAND)
        return jsonify({"error": "published_password"}), 403

    db = SessionLocal()
    # Addresses are stored in lower case (admin_users_routes.py,
    # scripts/set_admin_account.py), so one typed in any case is found, as in
    # courses_routes.py.
    user = (
        db.query(User)
        .filter((User.email == identifier.lower()) | (User.username == identifier))
        .first()
    )
    # A place enters with its code and nowhere else. An account with the
    # participant role and a password (an educator demoted by hand) would get
    # a session here that is bound to no course.
    if (user is None or not user.is_active or user.role == Role.participant
            or not verify_password(user.password_hash, password)):
        # Without the identifier: the field also receives the code of a place
        # typed into the wrong tab, and a password typed into the wrong field.
        logger.warning("[AUTH] failed login")
        return jsonify({"error": "Invalid credentials"}), 401

    # The conditions of use are agreed to with the sign-in (lab/terms.py). An
    # account that has not agreed to the version that stands is not signed in:
    # the answer names the version, and the page asks again with
    # `accept_terms` set to it and `language`, the language the text stood in.
    if terms.needs_terms(user) and not terms.has_accepted(db, user):
        if data.get("accept_terms") != terms.TERMS_VERSION:
            return jsonify({"error": "terms_required", "terms_version": terms.TERMS_VERSION}), 409
        language = data.get("language")
        if not isinstance(language, str) or language not in terms.LANGUAGES:
            return jsonify({"error": "language required"}), 400
        terms.record(db, user, language)
        logger.info("[AUTH] account %s agreed to the conditions of %s", user.id, terms.TERMS_VERSION)

    login_user(user)
    if terms.needs_terms(user):
        session[terms.SESSION_KEY] = terms.TERMS_VERSION
    logger.info("[AUTH] login ok: %s (%s)", user.login_identifier, user.role.value)
    return jsonify({"user": user.to_public()}), 200


@auth_bp.route("/participant-login", methods=["POST"])
def participant_login():
    """A device enters a course with the code of one of its places.

    BAUPLAN Entscheid 2 (exclusive course room) in the form of 2026-09-23: the
    code alone names the place and its course, nothing else is asked, and
    there is no name to give. On success the session is pinned to that one
    course (session["course_id"], the exclusivity axis) and to the place.

    Body: {code}. 400 without one. 401 `invalid_code` where no active place
    carries this code: a typo, or a code its leader has replaced. 403
    `access_closed` where the code is right and the course cannot be entered
    now: its access window is past or unset, or it is archived. 429
    `too_many_attempts`, with `retry_after` in seconds and the same in the
    Retry-After header, to any entry from an address that has spent its
    budget of codes that name no active place (lab/login_attempts.py).
    The code is never logged.
    """
    data = request.get_json(silent=True)
    raw = data.get("code") if isinstance(data, dict) else None
    code = raw.strip() if isinstance(raw, str) else ""
    if not code:
        return jsonify({"error": "code required"}), 400

    # The check of the budget, the lookup and the charge run inside one
    # reservation of an attempt (lab/login_attempts.py): an empty budget
    # answers before the lookup, and only a code of the right form that
    # names no active place is charged. An entry that cannot be a code
    # reserves nothing and is looked up nowhere.
    form = has_code_form(code)
    with attempts_of(current_app).attempt(client_address(request), reserve=form) as attempt:
        if attempt.wait:
            logger.warning("[AUTH] place login refused: the address has spent its attempts")
            response = jsonify({"error": "too_many_attempts", "retry_after": attempt.wait})
            response.headers["Retry-After"] = str(attempt.wait)
            return response, 429

        db = SessionLocal()
        place = find_place(db, code) if form else None
        user = place.user if place is not None else None
        if (place is None or place.status != MembershipStatus.active or user is None
                or not user.is_active or user.role != Role.participant):
            attempt.spend()
            logger.info("[AUTH] place login rejected: no active place carries the given code")
            return jsonify({"error": "invalid_code"}), 401

    course = place.course
    if course is None or not access_open(course):
        logger.info("[AUTH] place login rejected: course %s is closed", place.course_id)
        return jsonify({"error": "access_closed"}), 403

    login_place(place)
    logger.info("[AUTH] place login ok: course=%s place=%s", course.id, place.place_number)
    return jsonify({
        "user": user.to_public(),
        "course": {"id": course.id, "name": course.name, "safety_level": course.safety_level},
        "place": place.place_number,
    }), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return jsonify({"success": True}), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    """Current identity plus the session's active course_id (Entscheid 1/2).

    For a participant this is their fixed course binding; for a leader or an
    admin it is the course chosen in the sign-in field of the header
    (POST /active-course), or null for their own use.

    A device asks here whether the sign-in of its place still holds
    (stores/labAuth.ts, `checkPlaceSession`). Where the check of this
    request's place session failed, the answer carries `unverified`: its
    null user ends nothing, and the session stays for the next request.

    Signed in is what the gate lets through (lab/sign_in_gate.py): an account
    with a password that has not agreed to the conditions with this sign-in
    answers here as no one. Where the sign-in could not be read at all (the
    lab database refused), the answer carries `unverified` as well.
    """
    user = signed_in_user()
    if user is None:
        body = {"user": None, "course_id": None, "course": None, "place": None}
        if sign_in_unreadable() or place_session_unverified():
            body["unverified"] = True
        return jsonify(body), 200
    return jsonify(_identity(user)), 200


def _identity(user: User) -> dict:
    """What /me answers for a signed-in session. `course` is the active
    course's id and name, which the sign-in field of the header shows; null
    where no course is active, or where the course under the session's id is
    not the one it entered (the safety level then holds the strictest)."""
    cid = current_course_id()
    db = SessionLocal()
    course = None
    if cid is not None:
        found = db.get(Course, cid)
        if found is not None and is_session_course(found):
            course = {"id": found.id, "name": found.name}
    body = {
        "user": user.to_public(),
        "course_id": cid,
        "course": course,
        "place": current_place_number(),
    }
    # The profile shows when the account agreed to which version of the
    # conditions (views/AccountView.vue); a place agrees to none.
    if terms.needs_terms(user):
        agreed = terms.latest(db, user)
        body["terms"] = agreed.to_public() if agreed is not None else None
    return body


@auth_bp.route("/active-course", methods=["POST"])
def choose_course():
    """The course a leader or an admin works in (2026-11-14), chosen in the
    sign-in field of the header; null is the account's own use ("Eigene
    Nutzung", decided 2026-10-31).

    Body: {course_id: int | null}. 401 without a sign-in. 403 for a place,
    whose course is the one its code entered, and for a course id the
    account leads no course under (`is_course_educator`; an admin passes),
    whether or not a course has it: the answer tells nobody which ids exist.
    404 where no course has the id, for an admin, and for an id no course
    can have. 400 where the body names no course_id or one that is no whole
    number. The answer is that of /me.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required"}), 401
    if user.role == Role.participant:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "course_id" not in data:
        return jsonify({"error": "course_id required"}), 400
    raw = data["course_id"]
    if raw is None:
        set_active_course(None)
        logger.info("[AUTH] account %s works in its own use", user.id)
        return jsonify(_identity(user)), 200
    if isinstance(raw, bool) or not isinstance(raw, int):
        return jsonify({"error": "course_id must be a whole number or null"}), 400
    if not 0 < raw <= MAX_ROW_ID:
        return jsonify({"error": "Not found"}), 404
    if not is_course_educator(user, raw):
        return jsonify({"error": "Forbidden"}), 403
    course = SessionLocal().get(Course, raw)
    if course is None:
        return jsonify({"error": "Not found"}), 404
    set_active_course(course)
    logger.info("[AUTH] account %s works in course %s", user.id, course.id)
    return jsonify(_identity(user)), 200


