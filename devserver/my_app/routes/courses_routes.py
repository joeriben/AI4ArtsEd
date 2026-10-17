"""
/api/courses/* — course CRUD, co-leaders, the places of a course and its access
window (BAUPLAN Entscheid 2 in the form of 2026-09-23), and the two-step
cascade deletion flow.

P1 + P3. Since 2026-08-15 this file also carries the v2 style PALETTE — the
opt-in list of styles a course shows its members (`CoursePaletteItem`), plus the
presets still available to add. The palette lives with the course, not with the
prompt library, exactly as the binding design v2 has it. It is adapted from the
design template (origin/design/user-course-system) to the committed
`my_app/lab/` package layout.

A course admits devices, not a roster: the leader asks for a number of places,
and each place is a number and a code (lab/place_codes.py). A place is a PASSWORD-LESS participant
account that carries no name; a device enters with the place's code
(auth_routes.participant_login), and what the place keeps belongs to the place.
We still satisfy the NOT NULL password_hash column with an unusable sentinel
hash.

Location: devserver/my_app/routes/courses_routes.py
"""
from __future__ import annotations

import datetime as _dt
import logging

from flask import Blueprint, request, jsonify
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from my_app.lab.db import SessionLocal
from my_app.lab.models import (
    User, Role, Course, CourseEducator, CourseRole,
    CourseMembership, MembershipStatus, Work,
    CoursePaletteItem, PaletteSourceType, InterceptionPrompt,
)
from my_app.lab.auth_service import (
    current_user, current_course_id, is_course_educator, is_course_member,
    require_auth, require_role,
    require_course_access, require_course_owner, require_course_leader,
)
from my_app.lab.place_codes import access_open, iso_utc, issue_code
from my_app.utils.url_ids import MAX_ROW_ID

logger = logging.getLogger(__name__)
courses_bp = Blueprint("courses", __name__, url_prefix="/api/courses")

# Valid course safety levels — anchored to the platform's hardcoded levels
# (kids | youth | open; see the config schemas kids.json / youth.json /
# open.json).
_SAFETY_LEVELS = {"kids", "youth", "open"}

# Participants never authenticate with a password; store an unusable sentinel
# so the NOT NULL password_hash column is satisfied and no password can match.
_UNUSABLE_PW_HASH = "!"

# How many places one request makes at most. A school class is some thirty
# devices; the bound catches a typo that would hand out a thousand codes.
_MAX_PLACES_PER_REQUEST = 100


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------
def _course_dict(c: Course) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "safety_level": c.safety_level,
        "educator_can_view_participant_works": c.educator_can_view_participant_works,
        "archived": c.archived,
        "educators": [
            {"user_id": e.user_id, "role": e.role_in_course.value} for e in c.educators
        ],
        "place_count": sum(1 for m in c.members if _is_place(m)),
        # The access window, for the CourseEditor panel and the dashboard card.
        "access_until": iso_utc(c.access_until),
        "access_open": access_open(c),
    }


def _is_place(m: CourseMembership) -> bool:
    return m.status == MembershipStatus.active and m.place_number is not None


def _place_dict(m: CourseMembership) -> dict:
    """A place as its leader sees it: the number, and whether and since when it
    has a code. The code itself is in the one response that makes it."""
    return {
        "number": m.place_number,
        "has_code": bool(m.code_hash),
        "code_issued_at": iso_utc(m.code_issued_at),
    }


# ---------------------------------------------------------------------------
# Course CRUD
# ---------------------------------------------------------------------------
@courses_bp.route("", methods=["GET"])
@require_auth
def list_my_courses():
    """Courses where I lead (owner/co_leader) or am an active member (admin sees all).
    A place is in the one course its session is bound to."""
    user = current_user()
    db = SessionLocal()
    if user.role == Role.admin:
        courses = db.query(Course).order_by(Course.created_at.desc()).all()
    elif user.role == Role.participant:
        # Whatever other rows its account kept (auth_service.is_course_member).
        cid = current_course_id()
        course = db.get(Course, cid) if cid is not None and is_course_member(user, cid) else None
        courses = [course] if course is not None else []
    else:
        led = {e.course_id for e in db.query(CourseEducator).filter(CourseEducator.user_id == user.id)}
        # A membership that holds no place grants nothing (is_course_member).
        member = {m.course_id for m in db.query(CourseMembership).filter(
            CourseMembership.user_id == user.id,
            CourseMembership.status == MembershipStatus.active,
            CourseMembership.place_number.isnot(None))}
        ids = led | member
        courses = (
            db.query(Course).filter(Course.id.in_(ids)).order_by(Course.created_at.desc()).all()
            if ids else []
        )
    return jsonify({"courses": [_course_dict(c) for c in courses]}), 200


@courses_bp.route("", methods=["POST"])
@require_role(Role.educator)
def create_course():
    """Create a course; the caller becomes its owner.

    Body: {title, safety_level?, max_size?, phase?, notes?, description?,
    educator_can_view_participant_works?}. `title` is the course name; `age_group`
    is accepted as an alias for safety_level. max_size/phase/notes are optional
    metadata kept in the description (no dedicated columns in the P0 schema).
    """
    user = current_user()
    data = request.get_json(silent=True) or {}
    # Accept both "title" (spec) and "name" (design/model) as the course name.
    name = (data.get("title") or data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "title required"}), 400

    # Accept "safety_level" (canonical) or "age_group" (spec alias).
    safety = (data.get("safety_level") or data.get("age_group") or "youth").strip()
    if safety not in _SAFETY_LEVELS:
        return jsonify({"error": f"safety_level must be one of {sorted(_SAFETY_LEVELS)}"}), 400

    db = SessionLocal()
    course = Course(
        name=name,
        description=data.get("description") or data.get("notes", ""),
        safety_level=safety,
        educator_can_view_participant_works=bool(
            data.get("educator_can_view_participant_works", False)),
    )
    db.add(course)
    db.flush()  # get course.id
    db.add(CourseEducator(course_id=course.id, user_id=user.id, role_in_course=CourseRole.owner))
    db.commit()
    logger.info("[COURSE-CREATE] course=%s owner=%s safety=%s", course.id, user.id, safety)
    return jsonify({"course": _course_dict(course)}), 201


@courses_bp.route("/<int:course_id>", methods=["GET"])
@require_course_access
def get_course(course_id: int):
    db = SessionLocal()
    c = db.get(Course, course_id)
    if c is None:
        return jsonify({"error": "not found"}), 404
    out = _course_dict(c)
    # The list of places is the leader's. A place reads its course, and the
    # other places stay with the leader.
    if is_course_educator(current_user(), course_id):
        out["places"] = [
            _place_dict(m) for m in sorted(
                (m for m in c.members if _is_place(m)), key=lambda m: m.place_number
            )
        ]
    return jsonify({"course": out}), 200


@courses_bp.route("/<int:course_id>", methods=["PATCH"])
@require_course_owner
def update_course(course_id: int):
    db = SessionLocal()
    c = db.get(Course, course_id)
    if c is None:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    if "safety_level" in data or "age_group" in data:
        safety = (data.get("safety_level") or data.get("age_group") or "").strip()
        if safety not in _SAFETY_LEVELS:
            return jsonify({"error": f"safety_level must be one of {sorted(_SAFETY_LEVELS)}"}), 400
        c.safety_level = safety
    if "title" in data or "name" in data:
        new_name = (data.get("title") or data.get("name") or "").strip()
        if not new_name:
            return jsonify({"error": "title cannot be empty"}), 400
        c.name = new_name
    for field in ("description", "educator_can_view_participant_works", "archived"):
        if field in data:
            setattr(c, field, data[field])
    db.commit()
    return jsonify({"course": _course_dict(c)}), 200


# ---------------------------------------------------------------------------
# Co-leaders (CourseEducator)
# ---------------------------------------------------------------------------
@courses_bp.route("/<int:course_id>/educators", methods=["POST"])
@require_course_owner
def add_educator(course_id: int):
    """Add a co-leader by user_id, username OR email. Target must be an educator/admin."""
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    target = None
    uid = data.get("user_id")
    if uid is not None:
        # An account is named by an integer SQLite's INTEGER holds; binding
        # a larger one to a query raises.
        if isinstance(uid, bool) or not isinstance(uid, int) or not 0 < uid <= MAX_ROW_ID:
            return jsonify({"error": "target must be an existing educator"}), 400
        target = db.get(User, uid)
    else:
        ident = (data.get("username") or data.get("email") or "").strip()
        if ident:
            target = db.query(User).filter(
                (User.username == ident) | (User.email == ident.lower())
            ).first()
    if target is None or target.role not in (Role.educator, Role.admin):
        return jsonify({"error": "target must be an existing educator"}), 400
    # Idempotent: don't create a duplicate CourseEducator row.
    existing = db.query(CourseEducator).filter(
        CourseEducator.course_id == course_id, CourseEducator.user_id == target.id
    ).first()
    if existing is None:
        db.add(CourseEducator(course_id=course_id, user_id=target.id,
                              role_in_course=CourseRole(data.get("role", "co_leader"))))
        db.commit()
    return jsonify({"success": True, "user_id": target.id}), 201


@courses_bp.route("/<int:course_id>/educators/<int:user_id>", methods=["DELETE"])
@require_course_owner
def remove_educator(course_id: int, user_id: int):
    db = SessionLocal()
    # Never allow removing the last owner — a course must keep an owner.
    row = db.query(CourseEducator).filter(
        CourseEducator.course_id == course_id, CourseEducator.user_id == user_id
    ).first()
    if row is None:
        return jsonify({"success": True}), 200
    if row.role_in_course == CourseRole.owner:
        owners = db.query(CourseEducator).filter(
            CourseEducator.course_id == course_id,
            CourseEducator.role_in_course == CourseRole.owner,
        ).count()
        if owners <= 1:
            return jsonify({"error": "cannot remove the last owner of a course"}), 400
    db.delete(row)
    db.commit()
    return jsonify({"success": True}), 200


# ---------------------------------------------------------------------------
# Places and the access window (BAUPLAN Entscheid 2 in the form of 2026-09-23)
#   POST   /:id/places                 make N places; their codes, ONCE
#   POST   /:id/places/:number/code    replace one place's code; the new one, ONCE
#   PUT    /:id/access                 open the course to its codes until a moment
#   DELETE /:id/access                 close it now
# ---------------------------------------------------------------------------
@courses_bp.route("/<int:course_id>/places", methods=["POST"])
@require_course_leader
def add_places(course_id: int):
    """Make `count` new places, each with its own code, and return the codes:
    this response is the only one that carries them.

    Body: {count}. The numbers continue after the highest number the course
    has had, so a number never passes to a second device. The account of a
    place has the participant role and no email, no username and no display
    name.
    """
    db = SessionLocal()
    course = db.get(Course, course_id)
    if course is None:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True)
    count = data.get("count") if isinstance(data, dict) else None
    # A whole number, as the page sends it. int() would read true as 1, 2.9 as
    # 2 and "1_0" as 10, and fails on the infinity that 1e400 parses to.
    if isinstance(count, bool) or not isinstance(count, int):
        return jsonify({"error": "count must be a whole number"}), 400
    if not 1 <= count <= _MAX_PLACES_PER_REQUEST:
        return jsonify({"error": f"count must be between 1 and {_MAX_PLACES_PER_REQUEST}"}), 400

    leader_id = current_user().id
    last = db.query(func.max(CourseMembership.place_number)).filter(
        CourseMembership.course_id == course_id
    ).scalar() or 0
    issued = []
    try:
        for number in range(last + 1, last + 1 + count):
            account = User(
                role=Role.participant,
                password_hash=_UNUSABLE_PW_HASH,  # a place enters with its code alone
                created_by=leader_id,
                is_active=True,
            )
            db.add(account)
            db.flush()
            place = CourseMembership(
                course_id=course_id, user_id=account.id,
                status=MembershipStatus.active, place_number=number,
            )
            db.add(place)
            issued.append({"number": number, "code": issue_code(db, place)})
        db.commit()
    except IntegrityError:
        # Two leaders of the course asked at the same moment and drew the same
        # numbers; the unique index on (course, number) turned the second away.
        db.rollback()
        return jsonify({"error": "the places of this course changed meanwhile; ask again"}), 409
    logger.info("[COURSE-PLACES] course=%s: %s places made (%s-%s)",
                course_id, count, last + 1, last + count)
    return jsonify({"places": issued, "course": _course_dict(course)}), 201


@courses_bp.route("/<int:course_id>/places/<int:number>/code", methods=["POST"])
@require_course_leader
def replace_place_code(course_id: int, number: int):
    """Give one place a new code, the lost-code case of the concept.

    The old code stops at once, the sessions that entered with it end at their
    next request, and what the place keeps stays with it. A place that has no
    code yet (a roster entry migrated into a place) receives its first one the
    same way. The new code is in this response and nowhere else.
    """
    db = SessionLocal()
    place = db.query(CourseMembership).filter(
        CourseMembership.course_id == course_id,
        CourseMembership.place_number == number,
        CourseMembership.status == MembershipStatus.active,
    ).first()
    if place is None:
        return jsonify({"error": "not found"}), 404
    try:
        code = issue_code(db, place)
        db.commit()
    except IntegrityError:
        # Another request gave the same code to a place in the same moment;
        # the unique index on the hash turned this one away.
        db.rollback()
        return jsonify({"error": "the places of this course changed meanwhile; ask again"}), 409
    logger.info("[COURSE-PLACES] course=%s place=%s: new code", course_id, number)
    return jsonify({"place": {**_place_dict(place), "code": code}}), 201


@courses_bp.route("/<int:course_id>/access", methods=["PUT"])
@require_course_leader
def open_access(course_id: int):
    """Open the course to the codes of its places until `until`.

    Body: {until} — ISO 8601 with an offset, a moment ahead. A later moment
    extends a running course; the places and their codes stay as they are.
    """
    db = SessionLocal()
    course = db.get(Course, course_id)
    if course is None:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True)
    raw = data.get("until") if isinstance(data, dict) else None
    try:
        until = _dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return jsonify({"error": "until must be ISO 8601"}), 400
    if until.utcoffset() is None:
        # A moment without an offset names a different moment in every zone.
        return jsonify({"error": "until needs an offset, e.g. +02:00 or Z"}), 400
    try:
        until = until.astimezone(_dt.timezone.utc)
    except OverflowError:  # 9999-12-31T23:30-01:00 is a moment of the year 10000
        return jsonify({"error": "until lies beyond the year 9999"}), 400
    if until <= _dt.datetime.now(_dt.timezone.utc):
        return jsonify({"error": "until must lie ahead"}), 400
    # Stored as UTC: SQLite keeps the wall-clock digits and drops the offset.
    course.access_until = until
    db.commit()
    logger.info("[COURSE-ACCESS] course=%s open until %s", course_id, course.access_until)
    return jsonify({"course": _course_dict(course)}), 200


@courses_bp.route("/<int:course_id>/access", methods=["DELETE"])
@require_course_leader
def close_access(course_id: int):
    """Close the course now. No code enters it, and a session of its places
    that makes a request while the course is closed ends there; a device idle
    until the window opens again keeps its session. The places and their codes
    stay, and the same codes enter again once the window is opened again."""
    db = SessionLocal()
    course = db.get(Course, course_id)
    if course is None:
        return jsonify({"error": "not found"}), 404
    course.access_until = None
    db.commit()
    logger.info("[COURSE-ACCESS] course=%s closed", course_id)
    return jsonify({"course": _course_dict(course)}), 200


# ---------------------------------------------------------------------------
# Course DELETION (Entscheid 4) — two-step: impact preview, then confirmed cascade.
# ---------------------------------------------------------------------------
def _deletion_impact(db, course_id: int) -> dict:
    """Counts shown to the leader before a destructive cascade.

    course_custom_prompts is always 0 in P1 (the per-course palette / custom
    forks arrive in P3); the field is kept for a stable UI/API contract.
    """
    # The same filter as _is_place: a removed membership keeps its number
    # (lab/db.py) and counted here while the course card left it out (finding S-057 of the code review of 2026-10-10).
    places = db.query(CourseMembership).filter(
        CourseMembership.course_id == course_id,
        CourseMembership.status == MembershipStatus.active,
        CourseMembership.place_number.isnot(None),
    ).count()
    course_works = db.query(Work).filter(Work.course_id == course_id).count()
    return {
        "places": places,
        "course_works": course_works,
        "course_custom_prompts": 0,
    }


@courses_bp.route("/<int:course_id>/deletion-impact", methods=["GET"])
@require_course_owner
def deletion_impact(course_id: int):
    db = SessionLocal()
    if db.get(Course, course_id) is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"impact": _deletion_impact(db, course_id)}), 200


@courses_bp.route("/<int:course_id>", methods=["DELETE"])
@require_course_owner
def delete_course(course_id: int):
    """Cascade delete per Entscheid 4.

    Requires {"confirm": true}. Without it -> 409 + the impact preview so the UI
    can show the GDPR warning (minors' works WILL be deleted).

    Cascade:
      1. works with Work.course_id == this course — deleted.
      2. the Course row — its memberships, educators (and, from P3, palette items)
         are removed by ON DELETE CASCADE (models.py).
      3. participant accounts — the places — deleted ONLY if the account is in
         no OTHER course; otherwise just this membership is removed by the
         course cascade. A place belongs to one course, so its account goes.
    Preset JSON files are NEVER touched.
    """
    db = SessionLocal()
    course = db.get(Course, course_id)
    if course is None:
        return jsonify({"error": "not found"}), 404

    impact = _deletion_impact(db, course_id)
    data = request.get_json(silent=True) or {}
    if not data.get("confirm"):
        return jsonify({
            "error": "confirmation required",
            "impact": impact,
            "warning": "Cascade delete is irreversible. Minors' works WILL be "
                       "deleted (GDPR). Preset styles are never affected.",
        }), 409

    # Capture member user_ids BEFORE the course cascade removes memberships.
    member_user_ids = [
        m.user_id for m in db.query(CourseMembership).filter(
            CourseMembership.course_id == course_id
        ).all()
    ]

    # 1) Delete works belonging to this course.
    db.query(Work).filter(Work.course_id == course_id).delete(synchronize_session=False)

    # 2) Delete the course — memberships + educators cascade (models.py FK).
    db.delete(course)
    db.flush()

    # 3) Participant-account fate: a participant survives if still in ANY other course.
    removed_accounts = 0
    for uid in member_user_ids:
        user = db.get(User, uid)
        if user is None or user.role != Role.participant:
            continue
        still_enrolled = db.query(CourseMembership).filter(
            CourseMembership.user_id == uid
        ).count()
        if still_enrolled == 0:
            db.delete(user)
            removed_accounts += 1

    db.commit()
    logger.info("[COURSE-DELETE] course=%s works=%s removed_accounts=%s",
                course_id, impact["course_works"], removed_accounts)
    return jsonify({
        "success": True,
        "deleted": {
            "course_id": course_id,
            "course_works": impact["course_works"],
            "participant_accounts_removed": removed_accounts,
        },
    }), 200


# ---------------------------------------------------------------------------
# The palette (P3) — what a course SHOWS its members
# ---------------------------------------------------------------------------
# A course's available styles are expressed PURELY by palette composition: the
# leader adds/removes/reorders items, each pointing either at a latent PRESET
# Original or at a kept custom prompt. "Overriding" a preset means including the
# fork and omitting the preset item — there is no override flag.
#
# Who may add what: a leader adds presets freely, and custom prompts only from
# what they themselves keep. Handing somebody else's written perspective to a
# whole course is not a curation decision, it is theirs to make.
def _palette_or_404(db, course_id: int, item_id: int):
    item = db.get(CoursePaletteItem, item_id)
    if item is None or item.course_id != course_id:
        return None
    return item


@courses_bp.route("/<int:course_id>/palette", methods=["GET"])
@require_course_access
def list_palette(course_id: int):
    """The course's palette, in order.

    A leader sees the list as they curated it, switched-off entries included —
    that is the thing they are editing. A member sees their menu: what they can
    actually pick. An entry that is off, or that points at a perspective its
    author has not published, is not on their menu and its name is not either.
    """
    from my_app.lab.auth_service import is_course_educator
    db = SessionLocal()
    items = (
        db.query(CoursePaletteItem)
        .filter(CoursePaletteItem.course_id == course_id)
        .order_by(CoursePaletteItem.position.asc(), CoursePaletteItem.id.asc())
        .all()
    )
    if not is_course_educator(current_user(), course_id):
        visible = []
        for i in items:
            if not i.enabled:
                continue
            if i.prompt_id is not None:
                prompt = db.get(InterceptionPrompt, i.prompt_id)
                if prompt is None or not prompt.is_published:
                    continue
            visible.append(i)
        items = visible
    return jsonify({"palette": [i.to_dict() for i in items]}), 200


@courses_bp.route("/<int:course_id>/palette", methods=["POST"])
@require_course_leader
def add_palette_item(course_id: int):
    """Add one entry. Body: {source_type, preset_name?|prompt_id?, label?, position?}"""
    data = request.get_json(silent=True) or {}
    source_type = (data.get("source_type") or "").strip()
    if source_type not in ("preset", "custom"):
        return jsonify({"error": "source_type must be 'preset' or 'custom'"}), 400

    db = SessionLocal()
    user = current_user()
    preset_name = None
    prompt_id = None

    if source_type == "preset":
        preset_name = (data.get("preset_name") or "").strip()
        if not preset_name:
            return jsonify({"error": "preset_name required"}), 400
        # The same predicate the perspective chooser answers to. Admitting an
        # interception config the chooser cannot show (surrealizer, latent_lab,
        # the split instruments) meant a palette could narrow the offer to
        # nothing at all and leave members with an empty surface.
        from my_app.routes.schema_pipeline_routes import init_schema_engine
        init_schema_engine()
        from schemas.engine.config_loader import config_loader
        from my_app.services.course_prompt_resolver import is_offerable_perspective
        resolved = config_loader.get_config(preset_name)
        if not is_offerable_perspective(preset_name, resolved):
            return jsonify({
                "error": f"'{preset_name}' cannot be offered as a perspective"
            }), 400
        if db.query(CoursePaletteItem).filter(
            CoursePaletteItem.course_id == course_id,
            CoursePaletteItem.preset_name == preset_name,
        ).first():
            return jsonify({"error": "already in the palette"}), 409
    else:
        try:
            prompt_id = int(data.get("prompt_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "prompt_id required"}), 400
        prompt = db.get(InterceptionPrompt, prompt_id)
        if prompt is None:
            return jsonify({"error": "prompt not found"}), 404
        if prompt.owner_id != user.id and user.role != Role.admin:
            # Not a 403: do not confirm that somebody else's prompt exists.
            return jsonify({"error": "prompt not found"}), 404
        if not prompt.is_published:
            return jsonify({
                "error": "publish the perspective before putting it in a course"
            }), 400
        if db.query(CoursePaletteItem).filter(
            CoursePaletteItem.course_id == course_id,
            CoursePaletteItem.prompt_id == prompt_id,
        ).first():
            return jsonify({"error": "already in the palette"}), 409

    position = data.get("position")
    if position is None:
        last = (
            db.query(CoursePaletteItem)
            .filter(CoursePaletteItem.course_id == course_id)
            .order_by(CoursePaletteItem.position.desc())
            .first()
        )
        position = (last.position + 1) if last else 0

    item = CoursePaletteItem(
        course_id=course_id,
        source_type=(PaletteSourceType.preset if source_type == "preset"
                     else PaletteSourceType.custom),
        preset_name=preset_name,
        prompt_id=prompt_id,
        label=(data.get("label") or None),
        position=int(position),
        enabled=bool(data.get("enabled", True)),
    )
    db.add(item)
    db.commit()
    logger.info("[PALETTE] course=%s + %s", course_id, item.style_key)
    return jsonify({"item": item.to_dict()}), 201


@courses_bp.route("/<int:course_id>/palette/<int:item_id>", methods=["PATCH"])
@require_course_leader
def update_palette_item(course_id: int, item_id: int):
    """Rename, reorder or switch an entry off. What it points at cannot change —
    that would be a different entry."""
    db = SessionLocal()
    item = _palette_or_404(db, course_id, item_id)
    if item is None:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    if "label" in data:
        item.label = (data.get("label") or None)
    if "position" in data:
        try:
            item.position = int(data["position"])
        except (TypeError, ValueError):
            return jsonify({"error": "position must be a number"}), 400
    if "enabled" in data:
        item.enabled = bool(data["enabled"])
    db.commit()
    return jsonify({"item": item.to_dict()}), 200


@courses_bp.route("/<int:course_id>/palette/<int:item_id>", methods=["DELETE"])
@require_course_leader
def delete_palette_item(course_id: int, item_id: int):
    """Take an entry out. The prompt behind it is untouched — only the course
    stops showing it."""
    db = SessionLocal()
    item = _palette_or_404(db, course_id, item_id)
    if item is None:
        return jsonify({"error": "not found"}), 404
    db.delete(item)
    db.commit()
    return jsonify({"success": True}), 200


@courses_bp.route("/<int:course_id>/available-presets", methods=["GET"])
@require_course_leader
def available_presets(course_id: int):
    """Every offerable perspective, and which of them the palette already has."""
    from my_app.services.course_prompt_resolver import course_prompt_resolver
    # The loader reads its JSON only when asked to. Straight after a restart this
    # is the first thing an educator may open, and an unasked loader knows
    # nothing — the list came back empty with no error to show for it.
    from my_app.routes.schema_pipeline_routes import init_schema_engine
    init_schema_engine()
    db = SessionLocal()
    taken = {
        i.preset_name for i in db.query(CoursePaletteItem).filter(
            CoursePaletteItem.course_id == course_id,
            CoursePaletteItem.preset_name.isnot(None),
        )
    }
    styles = course_prompt_resolver.list_preset_styles()
    for s in styles:
        s["in_palette"] = s["name"] in taken
    return jsonify({"presets": styles}), 200
