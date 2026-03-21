"""
GPU Service Flask Application Factory

Creates the Flask app with CORS for localhost and registers all route blueprints.
"""

import logging
from flask import Flask
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

    # Register route blueprints
    from routes.health_routes import health_bp
    from routes.diffusers_routes import diffusers_bp
    from routes.heartmula_routes import heartmula_bp
    from routes.text_routes import text_bp
    from routes.stable_audio_routes import stable_audio_bp
    from routes.cross_aesthetic_routes import cross_aesthetic_bp
    from routes.mmaudio_routes import mmaudio_bp
    from routes.hunyuan3d_routes import hunyuan3d_bp
    from routes.vlm_proxy_routes import vlm_proxy_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(diffusers_bp)
    app.register_blueprint(heartmula_bp)
    app.register_blueprint(text_bp)
    app.register_blueprint(stable_audio_bp)
    app.register_blueprint(cross_aesthetic_bp)
    app.register_blueprint(mmaudio_bp)
    app.register_blueprint(hunyuan3d_bp)
    app.register_blueprint(vlm_proxy_bp)

    logger.info("[GPU-SERVICE] Flask app created with all route blueprints")
    return app
