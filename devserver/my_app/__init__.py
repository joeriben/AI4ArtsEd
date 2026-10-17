"""
Flask application factory and initialization
"""
import logging
import os
import secrets
import sys
from pathlib import Path
from flask import Flask, request
from flask_cors import CORS
from flask_compress import Compress

from config import LOG_LEVEL, LOG_FORMAT, PUBLIC_DIR, DISABLE_API_CACHE, CACHE_STRATEGY, ENABLE_LEGACY_MIGRATION, CORS_ALLOWED_ORIGINS, JSON_STORAGE_DIR


# --- Session signing key -----------------------------------------------------
# The session cookie lives in the browser and is only SIGNED, not encrypted.
# Whoever knows this key can mint a cookie carrying any user_id, role or
# settings_authenticated value, so it must never fall back to a literal: until
# 2026-08-18 it fell back to a boilerplate string that no start script overrode.
SESSION_KEY_FILE = Path(__file__).parent.parent / "session_signing.key"
PREVIOUS_SESSION_KEY_FILE = Path(__file__).parent.parent / "session_signing_previous.key"


def _load_session_signing_key() -> str:
    """Return the key used to sign session cookies.

    Order: SECRET_KEY from the environment, then session_signing.key beside the
    other *.key files, otherwise a freshly generated key written to that file.
    A key that cannot be persisted would silently change on every restart and
    drop every session, so a failing write aborts startup instead.
    """
    from_env = os.environ.get("SECRET_KEY")
    if from_env:
        return from_env

    if SESSION_KEY_FILE.exists():
        existing = SESSION_KEY_FILE.read_text().strip()
        if existing:
            return existing

    generated = secrets.token_hex(32)
    try:
        SESSION_KEY_FILE.write_text(generated + "\n")
        SESSION_KEY_FILE.chmod(0o600)
    except OSError as e:
        raise RuntimeError(
            f"Cannot write the session signing key to {SESSION_KEY_FILE}: {e}. "
            "Set SECRET_KEY in the environment instead."
        ) from e

    logging.warning(
        "[SESSION] Generated a new signing key at %s - existing sessions are logged out",
        SESSION_KEY_FILE,
    )
    return generated


def _load_previous_signing_key():
    """Return a superseded key that should still VERIFY cookies, or None.

    Flask >= 3.1 takes these via SECRET_KEY_FALLBACKS: they never sign, they only
    keep cookies issued before a rotation valid. Delete the file after one
    PERMANENT_SESSION_LIFETIME. A key that leaked belongs nowhere near it.
    """
    if not PREVIOUS_SESSION_KEY_FILE.exists():
        return None
    return PREVIOUS_SESSION_KEY_FILE.read_text().strip() or None



def _run_startup_migration():
    """Run legacy folder migration on startup if needed."""
    if not ENABLE_LEGACY_MIGRATION:
        logging.debug("[MIGRATION] Legacy migration disabled via config")
        return

    try:
        from pathlib import Path
        from my_app.utils.legacy_migration import is_legacy_folder, run_migration, run_migration_async

        # The run data's root, named in config (finding S-077 of the code review of 2026-10-10).
        export_base = Path(JSON_STORAGE_DIR)

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


def reload_user_settings(settings_file=None):
    """Load user settings from user_settings.json and override config.py defaults.

    Can be called at startup or anytime to hot-reload settings without restart.
    Only the keys of config._SETTINGS_DEFAULTS are taken, the set the
    settings page writes; every other key in the file is reported and
    dropped. Until 2026-10-10 any name config.py had an attribute for was
    taken, the static server settings and config's functions among them
    (finding S-056 of the code review of 2026-10-10). `settings_file` names another file, for a test.
    """
    try:
        import json
        from pathlib import Path
        import config

        if settings_file is None:
            settings_file = Path(__file__).parent.parent / "user_settings.json"
        settings_file = Path(settings_file)

        if not settings_file.exists():
            logging.error(
                f"[CONFIG] FATAL: {settings_file.name} not found. "
                "This file is required — it contains all model assignments. "
                "Copy user_settings.json.example or configure via Settings UI."
            )
            sys.exit(1)

        with open(settings_file) as f:
            data = json.load(f)

        if not data:
            logging.info("[CONFIG] user_settings.json is empty, using defaults")
            config._USER_CONFIGURED_KEYS = set()
            return

        logging.info(f"[CONFIG] Loading user settings from {settings_file.name}")

        # Override config values
        count = 0
        for key, value in data.items():
            if key in config._SETTINGS_DEFAULTS:
                setattr(config, key, value)
                count += 1
            else:
                logging.warning(f"[CONFIG] Unknown setting '{key}' ignored")

        # Track which keys came from the file itself (vs. config.py's coded
        # defaults) so Settings can flag "running on default, never explicitly
        # configured" instead of showing a value with no indication either way.
        config._USER_CONFIGURED_KEYS = set(data.keys())

        logging.info(f"[CONFIG] {count} user settings applied successfully")

        # Resolve the knowledge Verdichtung model: env > setting > strongest STAGE
        # model > chat helper (BIBLIOTHEK.md §3). Lands on the config attr so the
        # role lookup in call_chat_helper(role="KNOWLEDGE_PROCESSING_MODEL") works.
        try:
            resolved = config.resolve_knowledge_processing_model()
            if resolved and resolved != getattr(config, "KNOWLEDGE_PROCESSING_MODEL", ""):
                config.KNOWLEDGE_PROCESSING_MODEL = resolved
                logging.info(f"[CONFIG] KNOWLEDGE_PROCESSING_MODEL resolved to {resolved}")
        except Exception as e:
            logging.warning(f"[CONFIG] could not resolve KNOWLEDGE_PROCESSING_MODEL: {e}")

        # Normalize legacy safety level values
        if getattr(config, 'DEFAULT_SAFETY_LEVEL', '') == 'off':
            config.DEFAULT_SAFETY_LEVEL = 'research'
            logging.info("[CONFIG] Normalized safety level 'off' → 'research'")

    except Exception as e:
        logging.error(f"[CONFIG] Error loading user settings: {e}")


def _check_required_models():
    """Verify the core 4-stage pipeline's model roles are configured. Abort if any
    are blank -- they ship as '' in config.py's _SETTINGS_DEFAULTS purely so
    hasattr() works before user_settings.json loads; every request needs a real
    value for all four. A blank one used to fall through to a hardcoded local
    micro-model deep in the canvas path -- fail at boot instead,
    matching how a missing user_settings.json already aborts startup above."""
    import config

    required = {
        'STAGE1_TEXT_MODEL': 'Translation, written prompt',
        'STAGE2_INTERCEPTION_MODEL': 'Prompt Interception',
        'STAGE2_OPTIMIZATION_MODEL': 'Media adaption',
        'STAGE3_MODEL': 'Translation, final prompt; verdict on flagged code',
    }
    missing = [
        f"{attr} ({label})" for attr, label in required.items()
        if not (getattr(config, attr, "") or "").strip()
    ]
    if missing:
        logging.error(
            "[STARTUP] FATAL: required model role(s) not configured: "
            + ", ".join(missing)
            + ". Set them in user_settings.json or via the Settings UI (Model Matrix)."
        )
        sys.exit(1)

    logging.info(f"[STARTUP] Core model roles OK: {', '.join(required.keys())}")


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

    # Verify the core pipeline's model roles are configured (a blank one used
    # to fall through to a hardcoded local micro-model in the canvas path)
    _check_required_models()

    # Verify DSGVO-critical SpaCy models are available
    _check_spacy_models()

    # A prompt of the local language model that the previous process left
    # running when it ended stays in ComfyUI's history, conversation and
    # pictures included: taken out once per start, on a thread of its own.
    from my_app.services.llm_client import forget_left_prompts_in_background
    forget_left_prompts_in_background()

    # Create Flask app
    # static_url_path=None disables Flask's automatic static file serving
    # We handle static files manually in static_routes.py for SPA support
    app = Flask(__name__, static_folder=str(PUBLIC_DIR), static_url_path=None)

    # An integer in a path ends where SQLite's INTEGER ends; a larger one
    # matches no route (my_app/utils/url_ids.py). Before the first blueprint.
    from my_app.utils.url_ids import install_row_id_converter
    install_row_id_converter(app)
    
    # Configure session
    app.secret_key = _load_session_signing_key()
    _previous_key = _load_previous_signing_key()
    if _previous_key:
        app.config['SECRET_KEY_FALLBACKS'] = [_previous_key]
    # Production (PORT=17801) uses HTTPS via Cloudflare → Secure cookies required
    # Development (PORT=17802) uses HTTP → Secure=False
    is_production = os.environ.get('PORT') == '17801'
    app.config['SESSION_COOKIE_SECURE'] = is_production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_PATH'] = '/'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

    @app.before_request
    def _fresh_generation_context():
        """A request starts with no output config on its thread.

        Today this guards an invariant rather than fixing a leak: every
        setter of CURRENT_OUTPUT_CONFIG sits inside a coroutine, and a
        coroutine runs in a context copy that dies with its task — nothing
        set there reaches the worker thread. But waitress serves one request
        after another on the same thread, and the day someone sets the var
        synchronously in a route — the pattern CURRENT_RUN_ID already uses,
        with a token only discipline remembers to reset — the previous
        request’s value would still be standing when the next one arrives,
        and a hold would be recorded under a neighbour’s config: a poisoned
        measurement, not a coarse one. This boundary makes that impossible
        instead of unlikely.
        """
        try:
            from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
            CURRENT_OUTPUT_CONFIG.set("")
        except Exception:
            pass

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
        # DS-03: Security-Header auf ALLE Antworten
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # A response may declare itself immutable content - a cached miniature of
        # an export that never changes again. Its own Cache-Control then stands,
        # in development too, because there is no stale data to guard against.
        if response.headers.pop('X-Immutable-Asset', None):
            return response

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
    from my_app.routes.static_routes import static_bp
    from my_app.routes.config_routes import config_bp
    from my_app.routes.schema_pipeline_routes import schema_bp, schema_compat_bp
    from my_app.routes.media_routes import media_bp
    from my_app.routes.pipeline_routes import pipeline_bp  # NEW: LivePipelineRecorder API
    from my_app.routes.chat_routes import chat_bp  # Chat overlay helper
    from my_app.routes.settings_routes import settings_bp  # Settings configuration API
    from my_app.routes.training_routes import training_bp # LoRA Training
    from my_app.routes.favorites_routes import favorites_bp  # Footer Gallery Favorites
    from my_app.routes.canvas_routes import canvas_bp  # Canvas Workflow Builder
    from my_app.routes.parrot_routes import parrot_bp  # Silly Parrot re-enactment
    from my_app.routes.speech_routes import speech_bp  # speech synthesis
    from my_app.routes.resona_routes import resona_bp  # Resona Werkstatt-Journal
    from my_app.routes.dev_routes import dev_bp  # Dev tools: pixel template editor
    from my_app.routes.text_routes import text_bp  # Latent Text Lab
    from my_app.routes.cross_aesthetic_routes import cross_aesthetic_bp  # Cross-Aesthetic proxy
    from my_app.routes.fusion_workbench_routes import fusion_workbench_bp  # Fusion Workbench: scheduled-fusion research proxy
    from my_app.routes.latent_lab_recorder_routes import latent_lab_recorder_bp  # Latent Lab research data export
    from my_app.routes.mean_images_routes import mean_images_bp  # Latent Lab: Mean Images overlays
    from my_app.routes.news_routes import news_bp  # Platform news items
    from my_app.routes.hardware_routes import hardware_bp  # GPU model footprints + capabilities
    from my_app.routes.knowledge_routes import knowledge_bp  # Wissensbibliothek Tier-O curation (Phase 2)
    from my_app.routes.scene_routes import scene_bp  # Szenen-Kapsel-Pipeline: /api/scene/* (UCD-132)
    from my_app.routes.commons_routes import commons_bp  # Wikimedia Commons comparison row
    from my_app.routes.model_register_routes import model_register_bp  # what a model is
    from my_app.routes.gpu_gate_routes import gpu_gate_bp  # the gate on HTTP: leases, plan, the card

    # Register API blueprints FIRST (before static catch-all)
    app.register_blueprint(config_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(schema_bp)  # New API: /api/schema/*
    app.register_blueprint(schema_compat_bp)  # Backward compatibility: /list_workflows, /workflow_metadata
    app.register_blueprint(media_bp)
    app.register_blueprint(pipeline_bp)  # NEW: LivePipelineRecorder API: /api/pipeline/*
    app.register_blueprint(chat_bp)  # Chat overlay helper: /api/chat/*
    app.register_blueprint(training_bp) # LoRA Training
    app.register_blueprint(favorites_bp)  # Footer Gallery Favorites
    app.register_blueprint(canvas_bp)  # Canvas Workflow Builder: /api/canvas/*
    app.register_blueprint(parrot_bp)  # Silly Parrot re-enactment: /api/parrot/*
    app.register_blueprint(speech_bp)  # speech synthesis: /api/speech/*
    app.register_blueprint(resona_bp)  # Resona Werkstatt-Journal: /api/resona/*
    app.register_blueprint(dev_bp)  # Dev tools: /api/dev/*
    app.register_blueprint(text_bp)  # Latent Text Lab proxy: /api/text/*
    app.register_blueprint(cross_aesthetic_bp)  # Cross-Aesthetic proxy: /api/cross_aesthetic/*
    app.register_blueprint(fusion_workbench_bp)  # Fusion Workbench proxy: /api/fusion_workbench/*
    app.register_blueprint(latent_lab_recorder_bp)  # Latent Lab research data: /api/latent-lab/record/*
    app.register_blueprint(mean_images_bp)  # Mean Images: /api/latent-lab/mean-images/*
    app.register_blueprint(news_bp)  # Platform news: /api/news
    app.register_blueprint(hardware_bp)  # GPU model footprints: /api/hardware/*
    app.register_blueprint(knowledge_bp)  # Wissensbibliothek Tier-O curation: /api/knowledge/*
    app.register_blueprint(scene_bp)  # Szenen-Kapsel-Pipeline: /api/scene/* (UCD-132)
    app.register_blueprint(commons_bp)  # Found-images row in Model Comparison: /api/commons/*
    app.register_blueprint(model_register_bp)  # maker/year/openness/size: /api/models/*
    app.register_blueprint(gpu_gate_bp)  # one heavy operation on the card at a time: /api/gate/*

    # Lab user/course system (Phase 0 + P1): DB + seed admin + /api/auth/*,
    # /api/admin/users/* and /api/courses/* blueprints.
    # FAIL-SAFE — a DB/import error degrades ONLY the lab feature and must NOT
    # prevent server start; the existing platform stays fully usable without login.
    try:
        from my_app.lab import init_lab
        from my_app.routes.auth_routes import auth_bp
        from my_app.routes.admin_users_routes import admin_users_bp
        from my_app.routes.courses_routes import courses_bp
        init_lab(app)
        app.register_blueprint(auth_bp)          # /api/auth/*
        app.register_blueprint(admin_users_bp)   # /api/admin/users/* (P1)
        app.register_blueprint(courses_bp)       # /api/courses/* (P1)

        # Keeping a perspective (P3) in a try of its own: it sits on top of the
        # lab, nothing else depends on it, and an import error here must not take
        # login and courses down with it.
        try:
            from my_app.routes.interception_prompts_routes import prompts_bp
            app.register_blueprint(prompts_bp)   # /api/interception-prompts/*
        except Exception as _pe:
            logging.warning(f"[LAB] kept perspectives unavailable: {_pe}")

        # The LoRA register (issue #70) lives in the same DB, beside the kept
        # perspectives, and is as separable: without it the Flow offers no
        # adapters and everything else stands.
        try:
            from my_app.routes.lora_routes import loras_bp
            app.register_blueprint(loras_bp)     # /api/loras/*
            # The adapters the platform's own perspectives bring get their row
            # once, so a fresh install applies them as before there was a
            # register; a row an admin changed stands.
            from my_app.services.lora_register import seed_from_presets
            seed_from_presets()
        except Exception as _le:
            logging.warning(f"[LAB] LoRA register unavailable: {_le}")
    except Exception as _e:
        logging.warning(f"[LAB] user/course system skipped (server continues): {_e}")

    # Register static blueprint LAST (catch-all for SPA routing)
    app.register_blueprint(static_bp)

    # Run legacy folder migration on startup if enabled
    _run_startup_migration()

    # Restart detection for canvas runs: any run whose status.json still
    # says 'running' was orphaned by a process that died mid-run. Re-mark it
    # 'interrupted' so a client that reconnects/polls afterward gets an
    # honest state plus its partial results (served via /api/media/...).
    try:
        from my_app.services.canvas_run_service import mark_orphans_interrupted
        mark_orphans_interrupted()
    except Exception as _e:
        logging.warning(f"[CANVAS-RUN] orphan startup scan skipped: {_e}")

    # Warm the next model while the current one is still working, whenever the
    # gate reports measured room for it. Purely an accelerator — if it never
    # runs, models are simply loaded when their turn comes, as before.
    try:
        from my_app.services.gpu_warm_ahead import start_warm_ahead_worker
        start_warm_ahead_worker()
    except Exception as _e:
        logging.warning(f"[WARM-AHEAD] not started: {_e}")

    return app
