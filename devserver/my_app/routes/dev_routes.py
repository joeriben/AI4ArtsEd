"""
Dev Tools API Routes
Development-only endpoints for pixel template editor, VRAM monitoring, and other dev tools.
Only available when DEBUG=True or running on localhost.
"""
from flask import Blueprint, jsonify, request
import json
import logging
from pathlib import Path

from my_app.services.vram_monitor import get_vram_monitor

logger = logging.getLogger(__name__)

dev_bp = Blueprint('dev', __name__, url_prefix='/api/dev')

# Path to pixelTemplates.json in the frontend source
PIXEL_TEMPLATES_FILE = (
    Path(__file__).parent.parent.parent.parent
    / "public" / "ai4artsed-frontend" / "src" / "data" / "pixelTemplates.json"
)


def _load_templates() -> dict:
    """Load pixel templates from JSON file."""
    if not PIXEL_TEMPLATES_FILE.exists():
        return {}
    with open(PIXEL_TEMPLATES_FILE, 'r') as f:
        return json.load(f)


def _save_templates(templates: dict) -> None:
    """Save pixel templates to JSON file."""
    PIXEL_TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PIXEL_TEMPLATES_FILE, 'w') as f:
        json.dump(templates, f, indent=2)
    logger.info(f"[DEV] Saved {len(templates)} pixel templates")


@dev_bp.route('/pixel-templates', methods=['GET'])
def get_pixel_templates():
    """Get all pixel templates."""
    try:
        templates = _load_templates()
        return jsonify(templates), 200
    except Exception as e:
        logger.error(f"[DEV] Error loading pixel templates: {e}")
        return jsonify({"error": str(e)}), 500


@dev_bp.route('/pixel-templates/<name>', methods=['PUT'])
def save_pixel_template(name: str):
    """Save or overwrite a single pixel template."""
    try:
        data = request.get_json()
        if not data or 'pattern' not in data:
            return jsonify({"error": "Request body must contain 'pattern'"}), 400

        pattern = data['pattern']

        # Validate pattern: must be 14x14 array of numbers 0-7
        if not isinstance(pattern, list) or len(pattern) != 14:
            return jsonify({"error": "Pattern must be a 14x14 array"}), 400

        for row in pattern:
            if not isinstance(row, list) or len(row) != 14:
                return jsonify({"error": "Each row must have 14 columns"}), 400
            for val in row:
                if not isinstance(val, int) or val < 0 or val > 7:
                    return jsonify({"error": "Values must be integers 0-7"}), 400

        # Validate name: alphanumeric + underscores
        if not name or not all(c.isalnum() or c == '_' for c in name):
            return jsonify({"error": "Name must be alphanumeric (underscores allowed)"}), 400

        templates = _load_templates()
        is_new = name not in templates
        templates[name] = pattern
        _save_templates(templates)

        action = "Created" if is_new else "Updated"
        logger.info(f"[DEV] {action} pixel template: {name}")
        return jsonify({"success": True, "action": action.lower(), "name": name}), 200

    except Exception as e:
        logger.error(f"[DEV] Error saving pixel template '{name}': {e}")
        return jsonify({"error": str(e)}), 500


@dev_bp.route('/pixel-templates/<name>', methods=['DELETE'])
def delete_pixel_template(name: str):
    """Delete a pixel template."""
    try:
        templates = _load_templates()
        if name not in templates:
            return jsonify({"error": f"Template '{name}' not found"}), 404

        del templates[name]
        _save_templates(templates)

        logger.info(f"[DEV] Deleted pixel template: {name}")
        return jsonify({"success": True, "name": name}), 200

    except Exception as e:
        logger.error(f"[DEV] Error deleting pixel template '{name}': {e}")
        return jsonify({"error": str(e)}), 500


@dev_bp.route('/vram-status', methods=['GET'])
def vram_status():
    """Consolidated VRAM usage across GPU Service backends."""
    try:
        monitor = get_vram_monitor()
        return jsonify(monitor.get_combined_status()), 200
    except Exception as e:
        logger.error(f"[DEV] VRAM status error: {e}")
        return jsonify({"error": str(e)}), 500
