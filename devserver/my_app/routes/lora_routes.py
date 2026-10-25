"""
/api/loras/* — the LoRA register: what a surface offers, and the table the
Settings keep it in.

    GET    /api/loras                  what THIS session is offered (platform
                                       rows, the rows of its course, its own
                                       trainings), each with `present` —
                                       whether the file lies in the LoRA
                                       folder right now. `?course_id=` names
                                       the course an educator works in; a
                                       participant's course is the session's
                                       (`lora_register.session_scope`).
    GET    /api/loras/register         admin: every row, the files in the
                                       folder no row names, and the courses a
                                       row can be released to.
    POST   /api/loras/register         admin: register a file.
    PUT    /api/loras/register/<id>    admin: change a row.
    DELETE /api/loras/register/<id>    admin: take a row out (the file stays).

Authz: the listing is open — the Flow is used without a login, and what a
session without a course and without a user sees is the platform's rows alone. The register is
gated by require_role('admin'); the legacy settings-admin session is bridged
to the seeded admin by current_user().

Location: devserver/my_app/routes/lora_routes.py
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from my_app.lab.auth_service import require_role
from my_app.lab.db import SessionLocal
from my_app.lab.models import Course, Role
from my_app.services import lora_register

logger = logging.getLogger(__name__)

loras_bp = Blueprint("loras", __name__, url_prefix="/api/loras")


@loras_bp.route("", methods=["GET"])
def list_visible():
    course_id, user_id = lora_register.session_scope(request.args.get("course_id"))
    return jsonify({"loras": lora_register.visible_adapters(course_id, user_id)})


def _courses() -> list:
    db = SessionLocal()
    rows = db.query(Course).filter(Course.archived.is_(False)).order_by(Course.name).all()
    return [{"id": c.id, "name": c.name} for c in rows]


@loras_bp.route("/register", methods=["GET"])
@require_role(Role.admin)
def register_list():
    return jsonify({
        "loras": lora_register.all_adapters(),
        "unregistered": lora_register.unregistered_files(),
        "courses": _courses(),
        "carriers": lora_register.carrier_configs(),
    })


@loras_bp.route("/register", methods=["POST"])
@require_role(Role.admin)
def register_create():
    data = request.get_json(silent=True) or {}
    try:
        row = lora_register.register_adapter(
            file=data.get("file", ""),
            name=data.get("name", ""),
            trigger=data.get("trigger", ""),
            owner_id=None,
            course_id=data.get("course_id"),
            visibility=data.get("visibility", "none"),
            category=data.get("category", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(row), 201


@loras_bp.route("/register/<int:adapter_id>", methods=["PUT"])
@require_role(Role.admin)
def register_update(adapter_id: int):
    data = request.get_json(silent=True) or {}
    try:
        row = lora_register.update_adapter(adapter_id, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if row is None:
        return jsonify({"error": "no such LoRA"}), 404
    return jsonify(row)


@loras_bp.route("/register/<int:adapter_id>", methods=["DELETE"])
@require_role(Role.admin)
def register_delete(adapter_id: int):
    if not lora_register.delete_adapter(adapter_id):
        return jsonify({"error": "no such LoRA"}), 404
    return jsonify({"ok": True})
