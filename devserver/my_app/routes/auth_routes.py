"""
/api/auth/* — login, logout, identity.

Mirrors the style of settings_routes.py (Flask Blueprint, JSON, server session).
Scope:
  - POST /api/auth/login   {identifier, password} — educator/admin via
    email-or-username + password.
  - POST /api/auth/participant-login {code} — a device enters an EXCLUSIVE
    course room (BAUPLAN Entscheid 2) with the code of one of the course's
    places (2026-09-23, lab/place_codes.py). NO password, NO name. The session
    then carries course_id (the exclusivity axis) and the place.
  - POST /api/auth/logout
  - GET  /api/auth/me                — identity, the session's active course_id,
    and the number of a place session's place.

Location: devserver/my_app/routes/auth_routes.py
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, request, jsonify

from my_app.lab.db import SessionLocal
from my_app.lab.models import User, Role, MembershipStatus
from my_app.lab.auth_service import (
    check_place_session, current_user, current_course_id, current_place_number,
    login_user, login_place, logout_user, place_session_unverified,
    verify_password,
)
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
    course explicitly in the CourseSelector (BAUPLAN Entscheid 1).
    """
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or "").strip()
    password = data.get("password") or ""
    if not identifier or not password:
        return jsonify({"error": "identifier and password required"}), 400

    db = SessionLocal()
    user = (
        db.query(User)
        .filter((User.email == identifier) | (User.username == identifier))
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

    login_user(user)
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

    For a participant this is their fixed course binding; for an educator it is
    whatever they selected in the CourseSelector (or null = presets only).

    A device asks here whether the sign-in of its place still holds
    (stores/labAuth.ts, `checkPlaceSession`). Where the check of this
    request's place session failed, the answer carries `unverified`: its
    null user ends nothing, and the session stays for the next request.
    """
    user = current_user()
    if user is None:
        body = {"user": None, "course_id": None, "place": None}
        if place_session_unverified():
            body["unverified"] = True
        return jsonify(body), 200
    return jsonify({
        "user": user.to_public(),
        "course_id": current_course_id(),
        "place": current_place_number(),
    }), 200


