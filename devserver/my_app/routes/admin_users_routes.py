"""
/api/admin/users/* — admin-only management of EDUCATOR accounts (BAUPLAN
Entscheid 3: educators are admin-created, there is NO self-signup).

Educators in turn make the places of a course, one account without a name
per device (courses_routes.py); a place is managed there and nowhere here.
Admins are seeded (seed.py) and are never created here.

Authz: every route is gated by require_role('admin'). The legacy settings-admin
session is bridged to the seeded admin User in auth_service.current_user(), so
the existing admin panel login grants access here too.

Temporary passwords are shown to the admin EXACTLY ONCE in the response
(create + password-reset); only the salted hash is stored. They are not
recoverable afterwards.

Adapted from the design template (origin/design/user-course-system) to the
committed `my_app/lab/` package layout; adds the P1 password-reset action.

Location: devserver/my_app/routes/admin_users_routes.py
"""
from __future__ import annotations

import logging
import secrets

from flask import Blueprint, request, jsonify

from my_app.lab.db import SessionLocal
from my_app.lab.models import User, Role, CourseEducator, CourseMembership, PromptVersion
from my_app.lab.auth_service import current_user, require_role, hash_password

logger = logging.getLogger(__name__)
admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/api/admin/users")


def _holds_place(db, user: User) -> bool:
    """Whether the account is the account of a place: it holds a membership
    with a number (courses_routes.add_places, lab/db.py `_migrate_places`).
    An account with the participant role that holds none and leads a course,
    an educator demoted by hand before the places, stays in the admin's hands;
    one that leads none may only be deleted (`_leads_a_course`).
    """
    return db.query(
        db.query(CourseMembership).filter(
            CourseMembership.user_id == user.id,
            CourseMembership.place_number.isnot(None),
        ).exists()
    ).scalar()


def _leads_a_course(db, user: User) -> bool:
    """Whether the account has a row in `course_educators`: the rule by which
    lab/db.py `_PLACE_ACCOUNT` keeps a participant account out of the places.
    A participant account that leads no course was stripped of its names
    there, and no field of it takes one again."""
    return db.query(
        db.query(CourseEducator).filter(CourseEducator.user_id == user.id).exists()
    ).scalar()


def _user_admin_dict(u: User) -> dict:
    """Admin-facing view: more fields than to_public(), still NO password hash."""
    return {
        "id": u.id,
        "role": u.role.value,
        "email": u.email,
        "username": u.username,
        "display_name": u.display_name,
        "identifier": u.login_identifier,
        "locale": u.locale,
        "is_active": u.is_active,
        "created_by": u.created_by,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@admin_users_bp.route("", methods=["GET"])
@require_role(Role.admin)
def list_users():
    """List users. Optional ?role=educator|participant|admin filter (default: all)."""
    db = SessionLocal()
    role_filter = (request.args.get("role") or "").strip()
    q = db.query(User)
    if role_filter:
        try:
            q = q.filter(User.role == Role(role_filter))
        except ValueError:
            return jsonify({"error": f"invalid role '{role_filter}'"}), 400
    rows = q.order_by(User.created_at.desc()).all()
    return jsonify({"users": [_user_admin_dict(u) for u in rows]}), 200


# ---------------------------------------------------------------------------
# Create (educators only — Entscheid 3)
# ---------------------------------------------------------------------------
@admin_users_bp.route("", methods=["POST"])
@require_role(Role.admin)
def create_user():
    """Create an EDUCATOR account.

    Body: {email, username?, display_name?, temp_password?, locale?}. An email is
    required (educators are adults). A username is optional (email is the primary
    login identifier). If temp_password is omitted, one is generated and returned
    ONCE for the admin to hand over.
    """
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "educator").strip()
    if role != Role.educator.value:
        return jsonify({"error": "only 'educator' accounts may be created here"}), 400

    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email required for an educator"}), 400

    db = SessionLocal()
    if db.query(User).filter(User.email == email).first() is not None:
        return jsonify({"error": "email already in use"}), 409

    username = (data.get("username") or "").strip() or None
    if username and db.query(User).filter(User.username == username).first() is not None:
        return jsonify({"error": "username already in use"}), 409

    temp_pw = (data.get("temp_password") or "").strip() or secrets.token_urlsafe(9)
    user = User(
        email=email,
        username=username,
        role=Role.educator,
        display_name=(data.get("display_name") or email).strip(),
        locale=data.get("locale", "de"),
        password_hash=hash_password(temp_pw),
        is_active=True,
        created_by=current_user().id,
    )
    db.add(user)
    db.commit()
    out = _user_admin_dict(user)
    out["temp_password"] = temp_pw  # surfaced exactly once
    logger.info("[ADMIN-USER-CREATE] educator id=%s email=%s", user.id, email)
    return jsonify({"user": out}), 201


# ---------------------------------------------------------------------------
# Update — deactivate/reactivate, role/display_name/locale, password reset
# ---------------------------------------------------------------------------
@admin_users_bp.route("/<int:user_id>", methods=["PATCH"])
@require_role(Role.admin)
def update_user(user_id: int):
    """Patch is_active / role / display_name / locale, and/or reset the password.

    Password reset: pass {"reset_password": true} (optionally with an explicit
    "temp_password") — a NEW temporary password is set and returned ONCE on
    user.temp_password.

    Guard rails: an admin may not demote themselves out of admin, and may not
    deactivate their own account (avoids locking the panel). The account of a
    place (`_holds_place`) is managed in its course (courses_routes.py): it
    keeps its role, carries no name and has no password, and every field of it
    is refused here. So is every field of a participant account that leads no
    course (`_leads_a_course`); it may only be deleted. No other account takes
    the participant role.
    """
    db = SessionLocal()
    target = db.get(User, user_id)
    if target is None:
        return jsonify({"error": "not found"}), 404

    data = request.get_json(silent=True) or {}
    me = current_user()
    new_temp_pw = None

    if _holds_place(db, target):
        return jsonify({"error": "a place is managed in its course"}), 400
    if target.role == Role.participant and not _leads_a_course(db, target):
        return jsonify({"error": "a participant account that leads no course can only be deleted"}), 400

    if "role" in data:
        try:
            new_role = Role(data["role"])
        except ValueError:
            return jsonify({"error": f"invalid role '{data['role']}'"}), 400
        if new_role == Role.participant:
            return jsonify({"error": "participant accounts are the places of a course"}), 400
        if target.id == me.id and target.role == Role.admin and new_role != Role.admin:
            return jsonify({"error": "cannot demote your own admin account"}), 400
        target.role = new_role

    if "is_active" in data:
        if target.id == me.id and not data["is_active"]:
            return jsonify({"error": "cannot deactivate your own account"}), 400
        target.is_active = bool(data["is_active"])

    if "display_name" in data:
        target.display_name = (data["display_name"] or "").strip()
    if "locale" in data:
        target.locale = data["locale"]

    if data.get("reset_password"):
        new_temp_pw = (data.get("temp_password") or "").strip() or secrets.token_urlsafe(9)
        target.password_hash = hash_password(new_temp_pw)
        logger.info("[ADMIN-USER-RESET] password reset for user=%s", target.id)

    db.commit()
    out = _user_admin_dict(target)
    if new_temp_pw is not None:
        out["temp_password"] = new_temp_pw  # surfaced exactly once
    return jsonify({"user": out}), 200


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@admin_users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_role(Role.admin)
def delete_user(user_id: int):
    """Hard-delete a user account.

    Refuses to delete your own account. User-owned rows (courses they lead via
    CourseEducator, memberships, prompts, works, drafts) are removed by the
    User -> * ON DELETE CASCADE in models.py. Preset JSON files are never touched.

    NOTE: deleting an educator who solely owns courses also cascades those
    courses; the UI should warn.

    The account of a place is refused: a place goes with its course, and
    deleting its account alone would hand its number to the next place
    (courses_routes.add_places). The accounts this one made keep standing and
    lose the pointer to it: `users.created_by` has no ON DELETE rule, and
    every place an educator made points at them. The versions it wrote of
    other accounts' perspectives stay and lose their author the same way
    (`prompt_versions.created_by`): an admin writes one with every edit of
    somebody else's perspective, and the migration copied them with the
    perspectives (lab/db.py `_copy_perspectives`).
    """
    db = SessionLocal()
    target = db.get(User, user_id)
    if target is None:
        return jsonify({"error": "not found"}), 404
    me = current_user()
    if target.id == me.id:
        return jsonify({"error": "cannot delete your own account"}), 400
    if _holds_place(db, target):
        return jsonify({"error": "a place is managed in its course"}), 400

    led = db.query(CourseEducator).filter(CourseEducator.user_id == user_id).count()
    memberships = db.query(CourseMembership).filter(CourseMembership.user_id == user_id).count()
    db.query(User).filter(User.created_by == user_id).update(
        {User.created_by: None}, synchronize_session=False)
    db.query(PromptVersion).filter(PromptVersion.created_by == user_id).update(
        {PromptVersion.created_by: None}, synchronize_session=False)
    db.delete(target)
    db.commit()
    logger.info("[ADMIN-USER-DELETE] user=%s role=%s led_courses=%s memberships=%s",
                user_id, target.role.value, led, memberships)
    return jsonify({"success": True}), 200
