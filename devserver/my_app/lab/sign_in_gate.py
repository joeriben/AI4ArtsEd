"""
Nothing without a sign-in: a visitor from outside sees the start page at
most (docs/DEVELOPMENT_DECISIONS.md, 2026-11-15).

Every request passes here before its view (`install`). It goes through when
the session is signed in (`signed_in_user`), when its route is in
PUBLIC_ENDPOINTS, or when its route is in MACHINE_ENDPOINTS and the request
comes from the machine the server runs on. Every other request is answered
401 `sign_in_required`. A route added later is closed until it is named here:
the lists are a written decision, checked in
devserver/tests/test_sign_in_gate.py.

PUBLIC_ENDPOINTS
  - static.serve_spa: the page of the app and its files (the bundle, the
    logos, the preview pictures of the start page). The start page, the
    sign-in page, the imprint and the privacy notice are pages of the app;
    the router of the frontend (src/router/index.ts) sends every other page
    to the sign-in.
  - auth.login, auth.participant_login, auth.logout, auth.me: the sign-in
    itself, and the question whether one holds.
  - settings.get_safety_level, settings.get_ui_mode: asked by the shell of
    the app on every page, the start page included (src/App.vue, main.ts).

MACHINE_ENDPOINTS: called by the server's own services on this machine, with
no session: the GPU service and the voice service lease the card
(services/gpu_admission.py, voxcpm_service/server.py), and the nodes of
ComfyUI reach the language models through the chat proxy
(comfyui_nodes/ai4artsed_comfyui/_devserver.py). The lease routes and the
chat proxy check the origin themselves as well
(`require_machine_or_settings_auth`, `chat_proxy`); the list of models
(`chat_models`) answers a signed-in session too, as the comparison surfaces
read it (src/composables/useChatModels.ts).

Fail closed: where the sign-in cannot be read (the lab database refuses), the
request is not signed in.

Location: devserver/my_app/lab/sign_in_gate.py
"""
from __future__ import annotations

import logging
from typing import Optional

from flask import g, jsonify, request, session

logger = logging.getLogger(__name__)

PUBLIC_ENDPOINTS = frozenset({
    "static.serve_spa",
    "auth.login",
    "auth.participant_login",
    "auth.logout",
    "auth.me",
    "settings.get_safety_level",
    "settings.get_ui_mode",
})

MACHINE_ENDPOINTS = frozenset({
    "gpu_gate.acquire_lease",
    "gpu_gate.heartbeat_lease",
    "gpu_gate.release_lease",
    "chat.chat_proxy",
    "chat.chat_models",
})


def signed_in_user():
    """The account this session is signed in as, or None.

    A place is signed in while its place admits the session
    (auth_service.current_user). An account with a password is signed in only
    with the version of the conditions it agreed to when it signed in
    (lab/terms.py): a session from before the agreement, or one that came in
    through the settings password alone, signs in again. An account that has
    been deactivated is signed in no longer.
    """
    try:
        from .auth_service import current_user
        from .terms import SESSION_KEY, TERMS_VERSION, needs_terms
        user = current_user()
    except Exception:
        logger.exception("[SIGN-IN] the sign-in of this request could not be read")
        g.sign_in_unreadable = True
        return None
    if user is None or not user.is_active:
        return None
    if needs_terms(user) and session.get(SESSION_KEY) != TERMS_VERSION:
        return None
    return user


def sign_in_unreadable() -> bool:
    """Whether `signed_in_user` could not read the sign-in of this request.
    The gate refuses such a request; /api/auth/me says so (`unverified`), and
    the page keeps its sign-in until a later answer reads it (2026-11-15:
    before, /me answered 500 here, and a page took it as no answer)."""
    return bool(g.get("sign_in_unreadable"))


def _from_this_machine() -> bool:
    from my_app.routes.settings_routes import is_localhost_request
    return is_localhost_request()


def _gate() -> Optional[tuple]:
    if request.method == "OPTIONS":
        return None  # a CORS preflight carries no cookie; its answer carries no data
    endpoint = request.endpoint
    if endpoint is None:
        return None  # no route: Flask answers 404 or 405
    if endpoint in PUBLIC_ENDPOINTS:
        return None
    if endpoint in MACHINE_ENDPOINTS and _from_this_machine():
        return None
    if signed_in_user() is not None:
        return None
    return jsonify({"error": "sign_in_required"}), 401


def install(app) -> None:
    """Put the gate before every view of the app. Called once in create_app,
    after the blueprints, whether or not the lab started."""
    app.before_request(_gate)
