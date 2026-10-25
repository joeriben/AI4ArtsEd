"""
GPU Service Flask Application Factory

Creates the Flask app with CORS for localhost and registers all route blueprints.
"""

import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_compress import Compress

logger = logging.getLogger(__name__)


def create_app():
    """Create and configure the GPU service Flask app."""
    app = Flask(__name__)

    # CORS for localhost only (dev 17802, prod 17801, frontend 5173)
    # Note: Primary callers are Flask backends via Python requests (no CORS needed),
    # but we enable it for debugging with curl/browser tools.
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:17801",
                "http://localhost:17802",
                "http://localhost:5173",
                "http://127.0.0.1:17801",
                "http://127.0.0.1:17802",
                "http://127.0.0.1:5173",
            ]
        }
    })

    # gzip/brotli compression for large responses (attention_maps etc.)
    Compress(app)

    @app.before_request
    def _carry_the_run():
        """Whose run this request belongs to, before anything serves it.

        On the APP and not on a blueprint. It stood on two of eleven — the
        diffusers routes and the text routes — and the other nine carried
        nothing, so everything the crossmodal lab, the audio surfaces, the
        media analysis and the 3D route hold the card for stood in the register
        under no run at all and was left out of every answer a bar asked for.
        A mark that has to be repeated per blueprint is a mark that is missing
        somewhere.

        All four unconditionally, the empty case included: a waitress thread
        serves one request after another, and a mark left standing files the
        next run's figures under the last one's name.

        Reading the body here parses it before a gated route takes the card
        rather than while it holds it. That trades a queued request's body
        sitting in memory while it waits for a slow read no longer happening
        with the slot held.
        """
        # `silent` hides a parse error and nothing else: a bare list or a
        # string is a body that parsed, and the marks are read off it by a
        # function that assumes nothing about its shape.
        from services.gpu_admission import carry_the_run
        carry_the_run(request.get_json(silent=True))

    # Register route blueprints
    from routes.health_routes import health_bp
    from routes.diffusers_routes import diffusers_bp
    from routes.cross_aesthetic_routes import cross_aesthetic_bp
    from routes.mmaudio_routes import mmaudio_bp
    from routes.llm_routes import llm_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(diffusers_bp)
    app.register_blueprint(cross_aesthetic_bp)
    app.register_blueprint(mmaudio_bp)
    app.register_blueprint(llm_bp)

    from services.gpu_admission import GpuBusy

    @app.errorhandler(GpuBusy)
    def _gpu_busy(e):
        # Busy is not broken. A caller that gets 500 retries nothing and reports
        # a failed generation; 503 says the card is occupied and the same request
        # will work later. Every gated route answers this way without having to
        # say so itself.
        logger.warning(f"[GPU-SERVICE] Rejecting request, GPU busy: {e}")
        # The sentence goes in BOTH fields: callers that read "error" would
        # otherwise be handed the bare token "gpu_busy" and could tell the person
        # waiting nothing at all.
        return jsonify({"success": False, "error": str(e), "code": "gpu_busy",
                        "detail": str(e),
                        # WHICH refusal, beside the sentence that says it in
                        # words. Callers pass this on; the surface picks its
                        # wording from it.
                        "busy_reason": getattr(e, "reason", "busy"),
                        "holder_kind": getattr(e, "holder_kind", ""),
                        "waiting": getattr(e, "waiting", 0),
                        "free_mb": getattr(e, "free_mb", 0.0),
                        "required_mb": getattr(e, "required_mb", 0.0)}), 503

    logger.info("[GPU-SERVICE] Flask app created with all route blueprints")
    return app
