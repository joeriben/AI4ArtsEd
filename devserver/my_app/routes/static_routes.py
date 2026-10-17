"""
Flask routes for serving Vue.js SPA (Single Page Application)

This module handles:
1. Static assets (*.js, *.css, images) with explicit MIME types
2. Vue Router's HTML5 history mode (serving index.html for all non-file routes)
3. API route passthrough (handled by other blueprints)

Architecture:
- Production builds are served from dist/ folder (config.PUBLIC_DIR)
- ES modules require explicit MIME type setting for browser compatibility
- SPA routing requires serving index.html for all non-asset paths
"""
from flask import Blueprint, current_app, send_from_directory
import os
import mimetypes

import config

# Create blueprint
static_bp = Blueprint('static', __name__)


@static_bp.route('/exports/json/<path:path>')
def serve_exports(path):
    """
    Serve exported session files (JSON, images, videos)

    This endpoint makes /exports/json/* accessible for:
    - Session thumbnails
    - Session detail images
    - Session videos
    """
    from pathlib import Path
    import mimetypes

    # Security check
    if '..' in path or path.startswith('/'):
        return "Invalid path", 403

    # Construct full path
    exports_dir = Path(config.JSON_STORAGE_DIR)
    file_path = exports_dir / path

    # Check if file exists
    if not file_path.exists() or not file_path.is_file():
        return "File not found", 404

    # A path INTO a run's `final/` folder is the same picture the media routes
    # serve, reached by walking the directory instead of naming the entity. It
    # is asked the same question, at the same place. Shape of the folder:
    # <date>/<device_id>/<run_id>/final/<filename> (pipeline_recorder.py).
    # Two shapes: `<date>/<device>/<run>/final/<file>` for current runs, and
    # `<date>/<device>/<run>/<file>` for the runs recorded before the final/
    # subfolder existed, which is the shape the session detail view still
    # builds URLs in for those runs.
    parts = [p for p in path.split('/') if p]
    run_id = filename = None
    if len(parts) >= 3 and parts[-2] == 'final':
        run_id, filename = parts[-3], parts[-1]
    elif len(parts) >= 2 and parts[-1].count('.') and parts[-2].startswith('run_'):
        run_id, filename = parts[-2], parts[-1]
    if run_id:
        from my_app.services.pipeline_recorder import load_recorder, SafetyRefusal
        from config import JSON_STORAGE_DIR
        recorder = None
        try:
            recorder = load_recorder(run_id, base_path=Path(JSON_STORAGE_DIR))
        except Exception:
            recorder = None
        if recorder is None:
            # No record to ask. Text and data keep flowing; a picture without a
            # readable record is refused, because whether it was cleared is
            # exactly what cannot be established here.
            if file_path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
                return "Blocked", 403
        else:
            try:
                recorder.checked_path_for_filename(filename)
            except SafetyRefusal:
                return "Blocked", 403

    # Determine MIME type
    mime_type = mimetypes.guess_type(str(file_path))[0]
    if mime_type is None:
        if path.endswith('.png'):
            mime_type = 'image/png'
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif path.endswith('.gif'):
            mime_type = 'image/gif'
        elif path.endswith('.webp'):
            mime_type = 'image/webp'
        elif path.endswith('.mp4'):
            mime_type = 'video/mp4'
        elif path.endswith('.webm'):
            mime_type = 'video/webm'
        elif path.endswith('.json'):
            mime_type = 'application/json'
        elif path.endswith('.txt'):
            mime_type = 'text/plain'

    # Send file
    from flask import send_file
    return send_file(file_path, mimetype=mime_type)


@static_bp.route('/', defaults={'path': ''})
@static_bp.route('/<path:path>')
def serve_spa(path):
    """
    Serve Vue.js SPA with proper routing and MIME types

    Handles three cases:
    1. API routes (start with 'api/' or specific endpoints) → return 404 to let Flask try other blueprints
    2. Static assets (assets/*.js, assets/*.css, favicon.ico) → serve with explicit MIME type
    3. All other paths (Vue routes like /select, /execute/:id) → serve index.html

    Args:
        path: Request path (empty string for root)

    Returns:
        Flask response with correct MIME type or index.html for SPA routing
    """
    # Security check to prevent directory traversal attacks
    if '..' in path or path.startswith('/'):
        return "Invalid path", 403

    # Case 1: API routes - explicitly skip these so other blueprints can handle them
    # Flask catch-all routes match by specificity, not registration order,
    # so we must explicitly exclude API patterns here
    if (path.startswith('api/') or
        path.startswith('exports/json/') or
        path.startswith('pipeline_configs_') or
        path.startswith('list_workflows') or
        path.startswith('workflow_metadata') or
        path.startswith('comfyui/') or
        path.startswith('sse/')):
        # Return 404 to let Flask continue to other blueprints
        # Don't use abort(404) as that would stop routing entirely
        from flask import abort
        abort(404)

    # Case 2: Static assets - serve with explicit MIME type
    # Critical for ES modules (.js files) which must have correct Content-Type
    # PWA files: registerSW.js, sw.js, workbox-*.js, manifest.webmanifest, icons
    if (path.startswith('assets/') or
        path.startswith('workbox-') or
        path.startswith('logos/') or
        path.startswith('config-previews/') or
        # The pictures of the Canvas presets on the ring of "New"
        # (components/canvas/CanvasPresetOverlay.vue). Left to the SPA case
        # below, a picture is answered with index.html and 200, and the disc
        # shows its plain ground.
        path.startswith('canvas-presets/') or
        # The pictures the edutainment animations draw from (the bird
        # sprite of the forest game): until 2026-10-10 answered with the
        # app's page in production, where no dev server serves public/.
        path.startswith('images/') or
        path in ['favicon.ico', 'robots.txt', 'registerSW.js', 'sw.js',
                 'manifest.webmanifest', 'icon-192x192.png', 'icon-512x512.png',
                 'apple-touch-icon.png']):
        file_path = os.path.join(current_app.static_folder, path)
        if os.path.isfile(file_path):
            # Explicit MIME type setting (critical for ES modules)
            # Python's mimetypes.guess_type() returns (type, encoding)
            mime_type = mimetypes.guess_type(path)[0]

            # Fallback MIME types for common extensions if guess_type fails
            if mime_type is None:
                if path.endswith('.js'):
                    mime_type = 'application/javascript'
                elif path.endswith('.css'):
                    mime_type = 'text/css'
                elif path.endswith('.json'):
                    mime_type = 'application/json'
                elif path.endswith('.webmanifest'):
                    mime_type = 'application/manifest+json'
                elif path.endswith('.png'):
                    mime_type = 'image/png'
                elif path.endswith('.jpg') or path.endswith('.jpeg'):
                    mime_type = 'image/jpeg'
                elif path.endswith('.svg'):
                    mime_type = 'image/svg+xml'
                elif path.endswith('.ico'):
                    mime_type = 'image/x-icon'

            # Serve the file with explicit MIME type and cache headers
            # Assets have content hashes in filename (e.g., index-Bprq4S1F.js)
            # so they can be cached aggressively - new builds get new filenames
            response = send_from_directory(
                current_app.static_folder,
                path,
                mimetype=mime_type
            )

            # Set aggressive caching for hashed assets (overwrite Flask's default)
            if path.startswith('assets/') or path.startswith('workbox-'):
                # Cache for 1 year (immutable assets with content hash)
                # New builds generate new filenames, so old cached files become unused automatically
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            elif path in ['sw.js', 'registerSW.js']:
                # Service Worker files must NOT be cached (critical for updates)
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            else:
                # Shorter cache for other static files (favicon, icons, manifest)
                response.headers['Cache-Control'] = 'public, max-age=3600'

            return response

        # Asset file not found - return 404
        return "File not found", 404

    # Case 3: All other paths - serve index.html (SPA routing)
    # This includes:
    # - / (root)
    # - /select (property selection view)
    # - /execute/:configId (pipeline execution view)
    # - /about (about view)
    # Vue Router handles client-side routing after index.html loads

    # Important: index.html should NOT be cached aggressively
    # because it contains references to hashed assets that change with each build
    response = current_app.send_static_file('index.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response
