"""
Dev Tools API Routes
Development-only endpoints for pixel template editor, VRAM monitoring, and other dev tools.
Only available when DEBUG=True or running on localhost.
"""
from flask import Blueprint, jsonify, request, send_from_directory, abort
import json
import logging
import re
import shlex
import subprocess
import time
from pathlib import Path


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



KICKIN_BANDS = {
    "flach":  Path("/tmp/kickin_band_flach_iso_s123"),
    "mittel": Path("/tmp/kickin_band_mittel_iso_s123"),
    "tief":   Path("/tmp/kickin_band_tief_iso_s123"),
}


@dev_bp.route('/kickin/<band>/<path:filename>', methods=['GET'])
def kickin_image(band, filename):
    if band not in KICKIN_BANDS:
        abort(404)
    base = KICKIN_BANDS[band]
    if not base.exists():
        abort(404)
    if filename != "strip.png" and not filename.startswith("kickin_"):
        abort(404)
    return send_from_directory(str(base), filename)


KICKIN_RESEARCH_BASE = Path(__file__).resolve().parents[2] / "research_data" / "kickin"
PERBLOCK_NUM_BLOCKS = 38


def _dataset_dir(ds_id: str) -> Path:
    return KICKIN_RESEARCH_BASE / ds_id


def _safe_dataset_id(ds_id: str) -> bool:
    return bool(ds_id) and "/" not in ds_id and ".." not in ds_id


def _scan_status(base: Path, dir_prefix: str):
    completed = []
    in_progress = []
    if base.exists():
        for idx in range(PERBLOCK_NUM_BLOCKS):
            d = base / f"{dir_prefix}_{idx:02d}"
            if not d.exists():
                continue
            if (d / "summary.json").exists():
                completed.append(idx)
            else:
                in_progress.append(idx)
    return completed, in_progress


def _read_metadata(ds_id: str) -> dict:
    meta_file = _dataset_dir(ds_id) / "metadata.json"
    if not meta_file.exists():
        return {"id": ds_id}
    try:
        with open(meta_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[DEV] Failed to read metadata for {ds_id}: {e}")
        return {"id": ds_id}


def _slugify_dataset_id(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9_-]', '_', s)
    s = re.sub(r'__+', '_', s)
    s = s.strip('_-')[:64]
    return s


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SWEEP_SCRIPTS = {
    "perblock":  PROJECT_ROOT / "devserver" / "testfiles" / "run_perblock_kickin.py",
    "cumulative": PROJECT_ROOT / "devserver" / "testfiles" / "run_cumulative_kickin.py",
}


@dev_bp.route('/research-sweep/launch', methods=['POST'])
def research_sweep_launch():
    """Spawn a kickin sweep (per-block, cumulative, or both) as a detached
    subprocess. Output streams to a log file under /tmp.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSON body required"}), 400

    dataset_id = _slugify_dataset_id(data.get('dataset_id', ''))
    if not dataset_id:
        return jsonify({"success": False, "error": "dataset_id required (used as run identifier)"}), 400

    prompt_early = (data.get('prompt_early') or '').strip()
    prompt_full = (data.get('prompt_full') or '').strip()
    if not prompt_early or not prompt_full:
        return jsonify({"success": False, "error": "prompt_early and prompt_full required"}), 400

    seed = int(data.get('seed', -1))
    if seed < 0:
        import random
        seed = random.randint(0, 2147483647)

    sweep_types = data.get('sweep_types') or ['perblock']
    if not isinstance(sweep_types, list) or not sweep_types:
        return jsonify({"success": False, "error": "sweep_types must be a non-empty list"}), 400
    for st in sweep_types:
        if st not in SWEEP_SCRIPTS:
            return jsonify({"success": False, "error": f"unknown sweep_type: {st}"}), 400

    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if not venv_python.exists():
        return jsonify({"success": False, "error": f"venv python not found at {venv_python}"}), 500

    cmds = []
    for st in sweep_types:
        cmd_parts = [
            str(venv_python),
            str(SWEEP_SCRIPTS[st]),
            "--dataset-id", dataset_id,
            "--prompt-early", prompt_early,
            "--prompt-full", prompt_full,
            "--seed", str(seed),
        ]
        cmds.append(" ".join(shlex.quote(p) for p in cmd_parts))

    full_cmd = " && ".join(cmds)
    log_file = f"/tmp/sweep_{dataset_id}_{int(time.time())}.log"
    bash_cmd = f"cd {shlex.quote(str(PROJECT_ROOT))} && ({full_cmd}) > {shlex.quote(log_file)} 2>&1"

    try:
        subprocess.Popen(
            ["bash", "-c", bash_cmd],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.error(f"[DEV-SWEEP-LAUNCH] Spawn failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    logger.info(f"[DEV-SWEEP-LAUNCH] dataset={dataset_id} seed={seed} types={sweep_types} log={log_file}")
    return jsonify({
        "success": True,
        "dataset_id": dataset_id,
        "seed": seed,
        "sweep_types": sweep_types,
        "log_file": log_file,
    })


@dev_bp.route('/kickin-research/datasets', methods=['GET'])
def kickin_datasets():
    """List all kickin research datasets with their metadata."""
    datasets = []
    if KICKIN_RESEARCH_BASE.exists():
        for child in sorted(KICKIN_RESEARCH_BASE.iterdir()):
            if not child.is_dir():
                continue
            ds_id = child.name
            meta = _read_metadata(ds_id)
            meta["id"] = ds_id
            datasets.append(meta)
    return jsonify({"datasets": datasets})


@dev_bp.route('/kickin-research/<ds_id>/perblock/status', methods=['GET'])
def kickin_perblock_status(ds_id):
    if not _safe_dataset_id(ds_id):
        abort(400)
    base = _dataset_dir(ds_id) / "perblock"
    completed, in_progress = _scan_status(base, "block")
    meta = _read_metadata(ds_id)
    return jsonify({
        "dataset_id": ds_id,
        "completed_blocks": completed,
        "in_progress_blocks": in_progress,
        "total_blocks": PERBLOCK_NUM_BLOCKS,
        "kickin_steps": meta.get("kickin_steps", [0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 14, 18, 23]),
    })


@dev_bp.route('/kickin-research/<ds_id>/perblock/<int:block>/<path:filename>', methods=['GET'])
def kickin_perblock_image(ds_id, block, filename):
    if not _safe_dataset_id(ds_id):
        abort(400)
    if block < 0 or block >= PERBLOCK_NUM_BLOCKS:
        abort(404)
    bdir = _dataset_dir(ds_id) / "perblock" / f"block_{block:02d}"
    if not bdir.exists():
        abort(404)
    if not filename.startswith("kickin_") or not filename.endswith(".png"):
        abort(404)
    return send_from_directory(str(bdir), filename)


@dev_bp.route('/kickin-research/<ds_id>/cumulative/status', methods=['GET'])
def kickin_cumulative_status(ds_id):
    if not _safe_dataset_id(ds_id):
        abort(400)
    base = _dataset_dir(ds_id) / "cumulative"
    completed, in_progress = _scan_status(base, "upto")
    meta = _read_metadata(ds_id)
    return jsonify({
        "dataset_id": ds_id,
        "completed_blocks": completed,
        "in_progress_blocks": in_progress,
        "total_blocks": PERBLOCK_NUM_BLOCKS,
        "kickin_steps": meta.get("kickin_steps", [0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 14, 18, 23]),
    })


@dev_bp.route('/kickin-research/<ds_id>/cumulative/<int:upto>/<path:filename>', methods=['GET'])
def kickin_cumulative_image(ds_id, upto, filename):
    if not _safe_dataset_id(ds_id):
        abort(400)
    if upto < 0 or upto >= PERBLOCK_NUM_BLOCKS:
        abort(404)
    bdir = _dataset_dir(ds_id) / "cumulative" / f"upto_{upto:02d}"
    if not bdir.exists():
        abort(404)
    if not filename.startswith("kickin_") or not filename.endswith(".png"):
        abort(404)
    return send_from_directory(str(bdir), filename)
