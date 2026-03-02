"""
Flask application factory and initialization
"""
import logging
import os
import sys
from flask import Flask, request
from flask_cors import CORS
from flask_compress import Compress

from config import LOG_LEVEL, LOG_FORMAT, PUBLIC_DIR, DISABLE_API_CACHE, CACHE_STRATEGY, ENABLE_LEGACY_MIGRATION, CORS_ALLOWED_ORIGINS


def _run_startup_migration():
    """Run legacy folder migration on startup if needed."""
    if not ENABLE_LEGACY_MIGRATION:
        logging.debug("[MIGRATION] Legacy migration disabled via config")
        return

    try:
        from pathlib import Path
        from my_app.utils.legacy_migration import is_legacy_folder, run_migration, run_migration_async

        # Get exports base path
        # __file__ is devserver/my_app/__init__.py
        # parent.parent.parent gives us project root
        export_base = Path(__file__).parent.parent.parent / "exports" / "json"

        if not export_base.exists():
            logging.info("[MIGRATION] Export directory does not exist yet - skipping migration")
            return

        # Quick check: Count legacy folders
        legacy_count = 0
        try:
            for item in export_base.iterdir():
                if item.is_dir() and is_legacy_folder(item.name):
                    legacy_count += 1
                    if legacy_count > 50:  # Stop counting after 50 for performance
                        break
        except OSError as e:
            logging.error(f"[MIGRATION] Error scanning export directory: {e}")
            return

        if legacy_count == 0:
            logging.debug("[MIGRATION] No legacy folders found - migration complete")
            return

        logging.info(f"[MIGRATION] Starting legacy folder migration in {export_base}")
        logging.info(f"[MIGRATION] Found at least {legacy_count} legacy folders to process")

        # Small migrations: Run synchronously (don't block server start)
        if legacy_count <= 50:
            logging.info("[MIGRATION] Running migration synchronously")

            def progress_callback(current, total):
                if current % 10 == 0:
                    logging.info(f"[MIGRATION] Progress: {current}/{total}")

            result = run_migration(export_base, dry_run=False, progress_callback=progress_callback)

            # Log summary
            logging.info("[MIGRATION] ========== SUMMARY ==========")
            logging.info(f"[MIGRATION] Total found: {result.total_found}")
            logging.info(f"[MIGRATION] Migrated: {result.migrated}")
            logging.info(f"[MIGRATION] Already migrated: {result.already_migrated}")
            logging.info(f"[MIGRATION] Errors: {result.errors}")
            logging.info("[MIGRATION] ==============================")

            if result.errors > 0:
                logging.error("[MIGRATION] Some errors occurred during migration - check logs")

        # Large migrations: Run in background thread
        else:
            logging.info("[MIGRATION] Running migration in background thread")
            run_migration_async(export_base, dry_run=False)

    except Exception as e:
        logging.error(f"[MIGRATION] Unexpected error during startup migration: {e}")


def reload_user_settings():
    """Load user settings from user_settings.json and override config.py defaults.

    Can be called at startup or anytime to hot-reload settings without restart.
    """
    try:
        import json
        from pathlib import Path
        import config

        settings_file = Path(__file__).parent.parent / "user_settings.json"

        if not settings_file.exists():
            logging.info("[CONFIG] No user_settings.json found, using defaults")
            return

        with open(settings_file) as f:
            data = json.load(f)

        if not data:
            logging.info("[CONFIG] user_settings.json is empty, using defaults")
            return

        logging.info(f"[CONFIG] Loading user settings from {settings_file.name}")

        # Override config values
        count = 0
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
                count += 1
            else:
                logging.warning(f"[CONFIG] Unknown setting '{key}' ignored")

        logging.info(f"[CONFIG] {count} user settings applied successfully")

        # Normalize legacy safety level values
        if getattr(config, 'DEFAULT_SAFETY_LEVEL', '') == 'off':
            config.DEFAULT_SAFETY_LEVEL = 'research'
            logging.info("[CONFIG] Normalized safety level 'off' → 'research'")

    except Exception as e:
        logging.error(f"[CONFIG] Error loading user settings: {e}")


def _check_spacy_models():
    """Verify SpaCy + required NER models are installed. Abort if missing."""
    required_models = ['de_core_news_lg', 'xx_ent_wiki_sm']

    try:
        import spacy
    except ImportError:
        logging.error("[STARTUP] FATAL: spacy is not installed!")
        logging.error("[STARTUP] Install: venv/bin/python -m pip install 'spacy>=3.8.0'")
        logging.error("[STARTUP] Then:    venv/bin/python -m spacy download de_core_news_lg")
        logging.error("[STARTUP]          venv/bin/python -m spacy download xx_ent_wiki_sm")
        sys.exit(1)

    missing = []
    for model_name in required_models:
        if not spacy.util.is_package(model_name):
            missing.append(model_name)

    if missing:
        logging.error(f"[STARTUP] FATAL: Missing SpaCy NER models: {', '.join(missing)}")
        logging.error("[STARTUP] DSGVO protection requires these models. Install with:")
        for m in missing:
            logging.error(f"[STARTUP]   venv/bin/python -m spacy download {m}")
        sys.exit(1)

    logging.info(f"[STARTUP] SpaCy NER models OK: {', '.join(required_models)}")


def create_app():
    """
    Create and configure the Flask application

    Returns:
        Flask app instance
    """
    # Configure logging
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

    # Load user settings BEFORE creating app
    reload_user_settings()

    # Verify DSGVO-critical SpaCy models are available
    _check_spacy_models()

    # Create Flask app
    # static_url_path=None disables Flask's automatic static file serving
    # We handle static files manually in static_routes.py for SPA support
    app = Flask(__name__, static_folder=str(PUBLIC_DIR), static_url_path=None)
    
    # Configure session
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    # Production (PORT=17801) uses HTTPS via Cloudflare → Secure cookies required
    # Development (PORT=17802) uses HTTP → Secure=False
    is_production = os.environ.get('PORT') == '17801'
    app.config['SESSION_COOKIE_SECURE'] = is_production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_PATH'] = '/'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

    # Enable CORS with session support
    # Must explicitly set origins when using credentials (cannot use wildcard)
    CORS(app,
         supports_credentials=True,
         origins=CORS_ALLOWED_ORIGINS,
         allow_headers=['Content-Type'],
         expose_headers=['Set-Cookie'])

    # gzip/brotli compression for large responses (e.g. attention_maps: 50MB → ~3MB)
    Compress(app)

    # Environment-based API caching strategy
    @app.after_request
    def add_cache_headers(response):
        """
        Add cache headers to API responses based on environment

        Development (DISABLE_API_CACHE=true):
        - Aggressive no-cache headers to prevent stale data during development
        - Fixes: Cloudflare Edge + Safari caching issues

        Production (DISABLE_API_CACHE=false):
        - Intelligent caching for GET requests (configs/models: 5min)
        - POST/SSE requests are never cached (browser default)
        - Reduces server load and improves performance
        """
        # Only add headers to API routes (not static assets)
        if request.path.startswith('/api/') or request.path.startswith('/pipeline_configs_'):
            if DISABLE_API_CACHE:
                # Development: Disable all caching
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            else:
                # Production: Enable intelligent caching for GET requests
                for route_prefix, cache_header in CACHE_STRATEGY.items():
                    if request.path.startswith(route_prefix):
                        response.headers['Cache-Control'] = cache_header
                        break
                # If no cache strategy matched, don't add headers (browser default)

        return response

    # Register blueprints
    from my_app.routes.workflow_streaming_routes import workflow_streaming_bp
    from my_app.routes.export_routes import export_bp
    from my_app.routes.static_routes import static_bp
    from my_app.routes.config_routes import config_bp
    from my_app.routes.sse_routes import sse_bp
    from my_app.routes.schema_pipeline_routes import schema_bp, schema_compat_bp
    from my_app.routes.media_routes import media_bp
    from my_app.routes.execution_routes import execution_bp
    from my_app.routes.pipeline_routes import pipeline_bp  # NEW: LivePipelineRecorder API
    from my_app.routes.chat_routes import chat_bp  # Session 82: Chat overlay helper
    from my_app.routes.settings_routes import settings_bp  # Settings configuration API
    from my_app.routes.training_routes import training_bp # Session 99: LoRA Training
    from my_app.routes.favorites_routes import favorites_bp  # Session 127: Footer Gallery Favorites
    from my_app.routes.canvas_routes import canvas_bp  # Session 129: Canvas Workflow Builder
    from my_app.routes.dev_routes import dev_bp  # Dev tools: pixel template editor
    from my_app.routes.text_routes import text_bp  # Session 176: Latent Text Lab
    from my_app.routes.cross_aesthetic_routes import cross_aesthetic_bp  # Session 177: Cross-Aesthetic proxy
    from my_app.routes.latent_lab_recorder_routes import latent_lab_recorder_bp  # Latent Lab research data export
    from my_app.routes.news_routes import news_bp  # Platform news items

    # Register API blueprints FIRST (before static catch-all)
    app.register_blueprint(config_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(workflow_streaming_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(sse_bp)
    app.register_blueprint(schema_bp)  # New API: /api/schema/*
    app.register_blueprint(schema_compat_bp)  # Backward compatibility: /list_workflows, /workflow_metadata
    app.register_blueprint(media_bp)
    app.register_blueprint(execution_bp)  # Pipeline run history API: /api/runs/*
    app.register_blueprint(pipeline_bp)  # NEW: LivePipelineRecorder API: /api/pipeline/*
    app.register_blueprint(chat_bp)  # Session 82: Chat overlay helper: /api/chat/*
    app.register_blueprint(training_bp) # Session 99: LoRA Training
    app.register_blueprint(favorites_bp)  # Session 127: Footer Gallery Favorites
    app.register_blueprint(canvas_bp)  # Session 129: Canvas Workflow Builder: /api/canvas/*
    app.register_blueprint(dev_bp)  # Dev tools: /api/dev/*
    app.register_blueprint(text_bp)  # Session 176: Latent Text Lab proxy: /api/text/*
    app.register_blueprint(cross_aesthetic_bp)  # Session 177: Cross-Aesthetic proxy: /api/cross_aesthetic/*
    app.register_blueprint(latent_lab_recorder_bp)  # Latent Lab research data: /api/latent-lab/record/*
    app.register_blueprint(news_bp)  # Platform news: /api/news

    # Register static blueprint LAST (catch-all for SPA routing)
    app.register_blueprint(static_bp)
    
    # Configure logging filter for ComfyUI proxy
    class ComfyUIFilter(logging.Filter):
        def filter(self, record):
            # Suppress successful GET requests for the ComfyUI proxy to reduce log spam
            if "GET /comfyui/" in record.getMessage() and " 200 " in record.getMessage():
                return False
            return True
    
    log = logging.getLogger('werkzeug')
    log.addFilter(ComfyUIFilter())
    
    # Store pending exports in app context (in production, use a proper database)
    app.pending_exports = {}

    # Run legacy folder migration on startup if enabled
    _run_startup_migration()

    return app
