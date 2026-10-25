"""
Settings API Routes
Configuration management for AI4ArtsEd DevServer
"""
from flask import Blueprint, jsonify, request, session, send_file
from functools import wraps
import json
import logging
from pathlib import Path
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from my_app.services.safety_level_resolver import resolve_safety_level
from my_app.services.model_capabilities import is_local
# The miniatures themselves are made platform-wide in one place (2026-08-25).
from my_app.services.thumbnails import can_build_thumbnail, cached_thumbnail
# What counts as a medium a run produced. A run may also keep its final latent,
# which is numpy and nothing anybody is handed — see media_ref.
from my_app.utils.media_ref import is_media_entity
import config
from schemas.engine.config_loader import config_is_hidden
import subprocess
import requests
import sys
from dataclasses import dataclass
import re
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')

# Path to user_settings.json
SETTINGS_FILE = Path(__file__).parent.parent.parent / "user_settings.json"

# Path to hardware_matrix.json
MATRIX_FILE = Path(__file__).parent.parent.parent / "hardware_matrix.json"

# Path to the shipped recommendation set. MATRIX_FILE is the live copy the
# Settings UI edits; this one never changes at runtime and is what
# "Reset to our recommendations" restores.
DEFAULT_MATRIX_FILE = Path(__file__).parent.parent.parent / "hardware_matrix.defaults.json"


def load_default_hardware_matrix():
    """Load the shipped recommendation matrix, without its documentation keys."""
    if not DEFAULT_MATRIX_FILE.exists():
        return None, f"Missing {DEFAULT_MATRIX_FILE.name}"
    try:
        with open(DEFAULT_MATRIX_FILE, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"[SETTINGS] Failed to load default hardware matrix: {e}")
        return None, str(e)
    if not isinstance(data, dict):
        return None, "Default matrix must be a JSON object"
    return {k: v for k, v in data.items() if not k.startswith('_')}, None


def load_hardware_matrix():
    """Load hardware matrix from JSON file, with fallback to empty dict"""
    if MATRIX_FILE.exists():
        try:
            with open(MATRIX_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[SETTINGS] Failed to load hardware matrix: {e}")
    return {}


def save_hardware_matrix(matrix_data):
    """Save hardware matrix to JSON file, every cell carrying its service."""
    try:
        _prefix_cells(matrix_data)
        with open(MATRIX_FILE, 'w') as f:
            json.dump(matrix_data, f, indent=2)
        return True, "Matrix saved successfully"
    except Exception as e:
        logger.error(f"[SETTINGS] Failed to save hardware matrix: {e}")
        return False, str(e)

# What a provider is -- its key file, its label, its dialect -- is the provider
# table's answer (config/llm_providers.json), not a list spelled out here.
from my_app.services.llm_providers import (
    has_key, key_file_path, key_in_file, names as provider_names,
    provider as provider_entry, providers as provider_table, split_provider,
)


def _with_service(service: str, value):
    """'<service>/<path>' for a cell that holds a path; anything else as it came."""
    if not isinstance(value, str):
        return value
    path = value.strip()
    if not path or path.startswith(f"{service}/"):
        return path or value
    return f"{service}/{path}"


def _prefix_cells(matrix_data) -> None:
    """Put the service in front of every model cell, in place.

    The platform's id of a model is '<service>/<path>': the column's provider
    for a cloud cell, 'local' for the local and the vision cells. The operator
    types the path as the provider publishes it into the provider's column;
    the prefix is never shown and never asked for, so it goes
    on here, on the way into the file, and the file carries the ids the way
    it ships (hardware_matrix.defaults.json writes every cell with its
    service). It has to: every consumer of the matrix reads the full id. A
    cloud cell typed without '/' was a LOCAL model to is_local() in
    model_capabilities, recorded as a data path that never leaves the
    installation and refused by the dispatchers.

    Only the COLUMN's own prefix is tested for and added: a provider's path may
    itself start with another provider's name (IONOS publishes
    'openai/gpt-oss-120b', OpenRouter 'anthropic/claude-sonnet-5'), and until
    2026-09-12 such a cell typed bare went to OpenAI with the OpenAI key. A cell
    that already carries its column's prefix is left as it is, and so is a
    'local/' id in a cloud column: no provider publishes a path starting with
    'local/', and such a cell is a working configuration that stays on this
    machine. Anything that is not a string, and a preset that is not a dict,
    is written as it came: this composes, it does not validate. A provider's
    `chat_models` are cells of the same kind and take the same prefix.
    """
    if not isinstance(matrix_data, dict):
        return
    presets = matrix_data.get('llm_presets')
    if isinstance(presets, dict):
        for provider, preset in presets.items():
            if provider not in provider_table() or not isinstance(preset, dict):
                continue
            models = preset.get('models')
            if not isinstance(models, dict):
                continue
            for field, value in models.items():
                if isinstance(value, str) and value.strip().startswith("local/"):
                    continue
                models[field] = _with_service(provider, value)
            chat = preset.get('chat_models')
            if isinstance(chat, list):
                preset['chat_models'] = [
                    m if isinstance(m, str) and m.strip().startswith("local/")
                    else _with_service(provider, m) for m in chat]
    local = matrix_data.get('local_llm_presets')
    if isinstance(local, dict):
        for preset in local.values():
            models = preset.get('models') if isinstance(preset, dict) else None
            if isinstance(models, dict):
                for field, value in models.items():
                    models[field] = _with_service('local', value)
    vision = matrix_data.get('vision_presets')
    if isinstance(vision, dict):
        for tier in vision.values():
            if isinstance(tier, dict):
                for field, value in tier.items():
                    tier[field] = _with_service('local', value)

# Path to settings password file (stores password hash)
SETTINGS_PASSWORD_FILE = Path(__file__).parent.parent.parent / "settings_password.key"


# ============================================================================
# Session Export Folder Discovery (for nested folder structure)
# ============================================================================

@dataclass
class MetadataInfo:
    """Info about a session's metadata file location"""
    metadata_path: Path          # Full path to metadata.json
    run_id: str                  # Extracted from metadata
    run_folder: Path             # Directory containing metadata.json
    relative_path: str           # Relative path from exports/json/ (for URLs)


# Module-level cache for metadata files
_metadata_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 60  # seconds
}


def find_all_metadata_files(base_path: Path, max_depth: int = 4) -> List[MetadataInfo]:
    """
    Recursively find all metadata.json files.

    Handles:
    - New: YYYY-MM-DD/device_id/run_xxx/metadata.json (depth 4)
    - Legacy migrated: YYYY-MM-DD/legacy_XXX/old_folder/metadata.json (depth 4)
    - Unmigrated: YYYY-MM-DD/old_folder/metadata.json (depth 3)
    - Flat legacy: old_folder/metadata.json (depth 2)

    Args:
        base_path: Base directory to search (exports/json/)
        max_depth: Maximum directory depth to traverse

    Returns:
        List of MetadataInfo objects for each found session
    """
    results = []

    def traverse(current_path: Path, depth: int):
        if depth > max_depth:
            return

        # Check if current directory has metadata.json
        metadata_file = current_path / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)

                run_id = metadata.get('run_id')
                if not run_id:
                    return  # Skip invalid entries

                results.append(MetadataInfo(
                    metadata_path=metadata_file,
                    run_id=run_id,
                    run_folder=current_path,
                    relative_path=str(current_path.relative_to(base_path))
                ))
            except Exception as e:
                logger.debug(f"Error reading {metadata_file}: {e}")
                return

        # Recurse into subdirectories
        try:
            for item in current_path.iterdir():
                if item.is_dir():
                    traverse(item, depth + 1)
        except PermissionError:
            pass  # Skip inaccessible directories

    traverse(base_path, 0)
    return results


def get_cached_metadata_files(base_path: Path) -> List[MetadataInfo]:
    """Get metadata files with simple in-memory caching"""
    now = time.time()
    if _metadata_cache['data'] is None or (now - _metadata_cache['timestamp']) > _metadata_cache['ttl']:
        _metadata_cache['data'] = find_all_metadata_files(base_path)
        _metadata_cache['timestamp'] = now
    return _metadata_cache['data']


# Preview thumbnails for the research-data table. The stored output files are
# full-size renders (megabytes each); the table shows them at 60x60. The
# miniatures themselves are made in ONE place for the whole platform since
# 2026-08-25, when the favourites strip needed them too — see
# services/thumbnails.py. What stays here is the question which file of a
# session is the one to preview.


def resolve_preview_media(session_dir: Path, metadata: dict):
    """
    First output image or video of a session - the one the table previews.

    Returns (absolute_path, subpath_below_session_dir, 'image'|'video'),
    or None when the session produced neither.
    """
    from my_app.services.pipeline_recorder import entity_cleared_for_delivery
    for entity in metadata.get('entities', []):
        entity_type = entity.get('type', '')
        if entity_type not in ('output_image', 'output_video'):
            continue
        filename = entity.get('filename')
        if not filename:
            continue
        # The preview is a smaller copy of the same picture, so it is the same
        # question. A refused picture is passed over here rather than refused
        # outright: the next output of the session becomes the preview, and a
        # session whose every picture was refused simply previews nothing.
        cleared, _ = entity_cleared_for_delivery(entity, metadata)
        if not cleared:
            continue
        # New structure keeps outputs in final/, the old one beside metadata.json.
        candidate = session_dir / "final" / filename
        subpath = "final/%s" % filename
        if not candidate.exists():
            candidate = session_dir / filename
            subpath = filename
        kind = 'image' if entity_type == 'output_image' else 'video'
        return candidate, subpath, kind
    return None


def find_metadata_by_run_id(base_path: Path, run_id: str) -> Optional[Path]:
    """
    Find metadata.json for a specific run_id.

    Uses timestamp extraction optimization when possible.

    Args:
        base_path: Base directory to search (exports/json/)
        run_id: The run_id to find

    Returns:
        Path to metadata.json file, or None if not found
    """
    # Try to extract timestamp from run_id for optimization
    timestamp_match = re.match(r'run_(\d+)_', run_id)
    if timestamp_match:
        timestamp_ms = int(timestamp_match.group(1))
        timestamp_s = timestamp_ms / 1000
        dt = datetime.fromtimestamp(timestamp_s)
        date_str = dt.strftime('%Y-%m-%d')

        # Try searching in the date folder first (fast path)
        date_folder = base_path / date_str
        if date_folder.exists():
            for metadata_info in find_all_metadata_files(date_folder):
                if metadata_info.run_id == run_id:
                    return metadata_info.metadata_path

    # Fallback: search all (slower but guaranteed)
    for metadata_info in find_all_metadata_files(base_path):
        if metadata_info.run_id == run_id:
            return metadata_info.metadata_path

    return None


# ============================================================================
# Settings Routes
# ============================================================================


def initialize_password():
    """Initialize password - use fixed password for all instances (dev/prod/ports)"""
    # FIXED PASSWORD: Same for all instances (17801, 17802, all domains)
    # Solves password manager confusion between dev/prod/ports
    FIXED_PASSWORD = "mkjdU4dz8H3!F"

    if not SETTINGS_PASSWORD_FILE.exists():
        # Generate hash from fixed password
        password_hash = generate_password_hash(FIXED_PASSWORD, method='pbkdf2:sha256')

        # Store hash
        SETTINGS_PASSWORD_FILE.write_text(password_hash)
        SETTINGS_PASSWORD_FILE.chmod(0o600)  # Restrict to owner only

        # Log confirmation (not the password itself for security)
        logger.info("[SETTINGS] Settings password initialized with fixed password")
        logger.info("[SETTINGS] Password is centrally managed (same for all instances)")

        return FIXED_PASSWORD
    return None


# Initialize password on module load
initialize_password()


def detect_gpu_vram() -> dict:
    """
    Detect GPU VRAM using nvidia-smi

    Returns:
        dict with:
        - vram_mb: Total VRAM in MB (int)
        - vram_gb: Total VRAM in GB (int, rounded)
        - vram_tier: Matching tier key (vram_96, vram_32, etc.)
        - gpu_name: GPU model name
        - detected: True if GPU was detected
    """
    try:
        # Query GPU memory and name
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total,name', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0:
            logger.warning("[SETTINGS] nvidia-smi failed, GPU detection unavailable")
            return {"detected": False, "error": "nvidia-smi not available"}

        # Parse output (format: "memory_mb, gpu_name")
        line = result.stdout.strip().split('\n')[0]  # First GPU
        parts = line.split(', ')
        vram_mb = int(parts[0].strip())
        gpu_name = parts[1].strip() if len(parts) > 1 else "Unknown GPU"

        vram_gb = round(vram_mb / 1024)

        # Map to tier (find closest tier that fits)
        tier_thresholds = [
            (80, "vram_96"),   # 80+ GB → 96 tier (qwen2.5vl:72b single model)
            (40, "vram_48"),   # 40-79 GB → 48 tier (qwen2.5vl:72b single model)
            (28, "vram_32"),   # 28-39 GB → 32 tier (qwen3:32b + vision:11b)
            (20, "vram_24"),   # 20-27 GB → 24 tier (qwen3:14b + vision:11b)
            (12, "vram_16"),   # 12-19 GB → 16 tier (mistral-nemo + vision:11b)
            (0, "vram_8"),     # 0-11 GB → 8 tier
        ]

        vram_tier = "vram_8"  # Default
        for threshold, tier in tier_thresholds:
            if vram_gb >= threshold:
                vram_tier = tier
                break

        logger.info(f"[SETTINGS] GPU detected: {gpu_name} with {vram_gb}GB VRAM → {vram_tier}")

        return {
            "detected": True,
            "vram_mb": vram_mb,
            "vram_gb": vram_gb,
            "vram_tier": vram_tier,
            "gpu_name": gpu_name
        }

    except subprocess.TimeoutExpired:
        logger.warning("[SETTINGS] nvidia-smi timed out")
        return {"detected": False, "error": "nvidia-smi timeout"}
    except Exception as e:
        logger.warning(f"[SETTINGS] GPU detection failed: {e}")
        return {"detected": False, "error": str(e)}


# Hardware Matrix - loaded from JSON file for editability
# See hardware_matrix.json in devserver directory
def get_hardware_matrix():
    """Get the current hardware matrix (loads from file each time for fresh data)"""
    return load_hardware_matrix()


def get_merged_preset(provider: str, vram_tier: str) -> dict:
    """
    Get a merged preset combining LLM models and Vision models.

    The matrix has three lookup tables:
    - vision_presets[vram_tier]: Vision models (always local, VRAM-dependent)
    - llm_presets[provider]: Cloud LLM models (VRAM-independent)
    - local_llm_presets[vram_tier]: Local LLM models (VRAM-dependent)

    For "local" provider: Uses local_llm_presets + vision_presets
    For cloud providers: Uses llm_presets + vision_presets (vision from detected VRAM)

    Args:
        provider: "local" or a name in config/llm_providers.json
        vram_tier: "vram_8", "vram_16", "vram_24", "vram_32", "vram_48", "vram_96"

    Returns:
        dict with all 9 model fields + metadata (label, EXTERNAL_LLM_PROVIDER, DSGVO_CONFORMITY)
    """
    matrix = get_hardware_matrix()

    # Get vision models (always VRAM-dependent)
    vision_preset = matrix.get('vision_presets', {}).get(vram_tier, {})

    if provider == 'local' or provider == 'none':
        # Local: both LLM and Vision from VRAM tier
        llm_preset = matrix.get('local_llm_presets', {}).get(vram_tier, {})
        label = llm_preset.get('label', f'Local ({vram_tier})')
        external_provider = 'none'
        dsgvo = True
    else:
        # Cloud: LLM from provider, Vision from VRAM tier
        llm_preset = matrix.get('llm_presets', {}).get(provider, {})
        label = llm_preset.get('label', provider.capitalize())
        external_provider = llm_preset.get('EXTERNAL_LLM_PROVIDER', provider)
        dsgvo = llm_preset.get('DSGVO_CONFORMITY', False)

    # Merge models
    models = {}
    if 'models' in llm_preset:
        models.update(llm_preset['models'])
    models.update(vision_preset)  # Vision overwrites any conflicting keys

    return {
        'label': label,
        'EXTERNAL_LLM_PROVIDER': external_provider,
        'DSGVO_CONFORMITY': dsgvo,
        'models': models
    }


# Hardware Matrix - loaded dynamically from hardware_matrix.json
HARDWARE_MATRIX = get_hardware_matrix()


# Localhost detection for auto-login
def is_localhost_request():
    """Check if request comes from localhost (for auto-login in development)"""
    if request.headers.get('CF-Connecting-IP'):
        return False
    # The address alone decides. The Host header is the client's to choose,
    # and "Host: localhost" from another machine on the network used to pass.
    return request.remote_addr in ('127.0.0.1', '::1')


# Authentication decorator
def require_settings_auth(f):
    """Decorator to protect settings routes - auto-login for localhost"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Auto-authenticate localhost requests (no password needed for local dev)
        if is_localhost_request():
            session['settings_authenticated'] = True
            return f(*args, **kwargs)

        if not session.get('settings_authenticated', False):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


@settings_bp.route('/auth', methods=['POST'])
def authenticate():
    """Authenticate with settings password (using password hash)"""
    try:
        data = request.get_json()
        password = data.get('password', '')

        # Password file should always exist (created by initialize_password)
        if not SETTINGS_PASSWORD_FILE.exists():
            logger.error("[SETTINGS] Password file missing! Run initialize_password()")
            return jsonify({"error": "Authentication system not initialized"}), 500

        # Read password hash
        password_hash = SETTINGS_PASSWORD_FILE.read_text().strip()

        # Verify password against hash
        if check_password_hash(password_hash, password):
            session['settings_authenticated'] = True
            session.permanent = True  # Remember across browser restarts
            logger.info("[SETTINGS] Authentication successful")
            return jsonify({"success": True}), 200
        else:
            logger.warning("[SETTINGS] Authentication failed - incorrect password")
            return jsonify({"error": "Incorrect password"}), 403

    except Exception as e:
        logger.error(f"[SETTINGS] Authentication error: {e}")
        return jsonify({"error": str(e)}), 500



@settings_bp.route('/check-auth', methods=['GET'])
def check_auth():
    """Check if currently authenticated - auto-auth for localhost"""
    # Auto-authenticate localhost requests
    if is_localhost_request():
        session['settings_authenticated'] = True
        return jsonify({"authenticated": True, "auto_login": True}), 200

    authenticated = session.get('settings_authenticated', False)
    return jsonify({"authenticated": authenticated}), 200


@settings_bp.route('/safety-level', methods=['GET'])
def get_safety_level():
    """Public endpoint: the effective safety level for frontend feature gating.

    Effective, not the raw setting: a session bound to a course reports the
    course level when that is stricter, so the interface cannot offer a group
    something its course does not allow.
    """
    return jsonify({'safety_level': resolve_safety_level()})


@settings_bp.route('/ui-mode', methods=['GET'])
def get_ui_mode():
    """Public endpoint: returns current UI mode for frontend adaptation."""
    # Legacy names are translated here, so the interface only ever sees the
    # current vocabulary.
    return jsonify({'ui_mode': config.normalise_ui_mode(config.UI_MODE)})


def _service_reached(model_string: str) -> str:
    """The service a configured model string actually reaches.

    Not a statement about the shape of the string — this is the platform's own
    dispatch. schemas/engine/prompt_interception_engine.py branches on exactly
    these prefixes to pick the backend, and model_capabilities.is_local carries
    the same split for the GPU service: a role setting holds a local model with
    the prefix or bare, and either way it stays on this machine.
    """
    if is_local(model_string):
        return 'local'
    return model_string.strip().lower().split('/', 1)[0]


def _recorded_conformity(service: str, presets: Optional[dict] = None) -> Optional[bool]:
    """What the platform records about a service. None when it records nothing.

    Callers that already hold the presets pass them in. Reading the file a second
    time would answer from a different instant: a failed read yields None for every
    service, and None compares equal to None -- a gate built on two reads opens
    exactly when one of them fails.

    Conformity is a property of the service, never of a prefix. Nothing leaves
    the installation for 'local'; every other service is looked up in
    hardware_matrix.json — the same entry the settings page shows. A service
    with no entry there gets no verdict in either direction.

    An entry consists of two halves: DSGVO_CONFORMITY and DSGVO_NOTE, the
    grounds it was set on. A flag standing on its own is not read as a verdict —
    somebody has to answer for a status, and the matrix editor refuses to save
    one without grounds. AWS Bedrock is why the third value exists at all: it is
    conform only if the AWS account is restricted to European regions, which
    this platform cannot see, so it ships recorded as nothing.
    """
    if service == 'local':
        return True
    if presets is None:
        presets = get_hardware_matrix().get('llm_presets', {})
    preset = (presets or {}).get(service)
    if not preset:
        return None
    if preset.get('DSGVO_CONFORMITY') is None:
        return None
    if not str(preset.get('DSGVO_NOTE') or '').strip():
        return None
    return bool(preset.get('DSGVO_CONFORMITY', False))


def _local_conformity_notes(matrix: Optional[dict] = None,
                            defaults: Optional[dict] = None) -> str:
    """The recorded grounds for calling a local model conform.

    'local' is not a provider and has no entry under llm_presets; its grounds
    stand on the local presets, one per VRAM tier, which say the same sentence
    on every card. Every DISTINCT sentence is returned, joined -- never one
    picked out of several, and never nothing while one exists. An empty note
    beside a True flag is the shape _recorded_conformity refuses everywhere
    else: a status somebody has to answer for, standing on its own.

    A register whose local section was emptied or deleted falls back to the
    shipped one, which is where the platform's own sentence lives. A caller
    asking this for a whole list of models hands that shipped register in, read
    once for the list: read here instead, it is read once per model.
    """
    if matrix is None:
        matrix = get_hardware_matrix()
    for source in (matrix, defaults):
        if source is None:
            source, _err = load_default_hardware_matrix()
            if not source:
                break
        notes = []
        for preset in (source.get('local_llm_presets') or {}).values():
            note = str(preset.get('DSGVO_NOTE') or '').strip()
            if note and note not in notes:
                notes.append(note)
        if notes:
            return '; '.join(notes)
    return ''


def data_path_of(model_string: str, matrix: Optional[dict] = None,
                 defaults: Optional[dict] = None) -> dict:
    """Where ONE model id sends text, and what the register records about it.

    _dsgvo_review() answers this for the roles the platform CONFIGURES. This
    answers it for a model somebody names -- a picker offering models, an
    instrument running one -- so that surface renders a statement instead of
    deriving one of its own. The three states are the same everywhere: True,
    False, and None for a service the platform records nothing about.

    The grounds travel with the state, because _recorded_conformity refuses to
    read a flag that has none: wherever a status can be shown, its note exists.
    That holds for 'local' too, and it is the one service _recorded_conformity
    cannot check it for -- 'local' has no entry under llm_presets, and its
    grounds stand on the per-tier local presets this function already reads. A
    register whose local section is empty and a shipped one that could not be
    read leave no grounds anywhere, and then the answer is the third state, not
    a flag standing on its own.
    """
    if matrix is None:
        matrix = get_hardware_matrix()
    presets = matrix.get('llm_presets', {})
    service = _service_reached(model_string)
    if service == 'local':
        note = _local_conformity_notes(matrix, defaults)
        recorded = True if note else None
    else:
        note = str(((presets or {}).get(service) or {}).get('DSGVO_NOTE') or '').strip()
        recorded = _recorded_conformity(service, presets)
    return {
        'service': service,
        'dsgvo_recorded': recorded,
        'dsgvo_note': note,
    }


# Every role that names a model, and therefore names a data path: the ten the
# interface configures for the pipeline, plus the safety classifier. A safety
# check that leaves the machine is as much of a data path as a transformation,
# and the checks were left out of the settings page's warning for as long as that
# warning matched prefixes — their model is a bare local name (shieldstral:3b)
# and would have read as not conform. Resolving the service instead of the
# prefix is what makes it listable. One field, because the checks of prompts,
# images and person names all ask the one classifier
# (my_app/services/safety_classifier.py). The verdict on flagged generated code
# asks STAGE3_MODEL, which the list already holds.
DSGVO_REVIEWED_FIELDS = (
    'STAGE1_TEXT_MODEL', 'STAGE2_INTERCEPTION_MODEL', 'STAGE2_OPTIMIZATION_MODEL',
    'STAGE3_MODEL', 'CHAT_HELPER_MODEL', 'PERSONA_MODEL',
    'RESONA_MODEL', 'IMAGE_ANALYSIS_MODEL', 'CODING_MODEL', 'KNOWLEDGE_PROCESSING_MODEL',
    'SAFETY_MODEL',
)


# What the user set themselves, kept apart from what a provider preset wrote. One
# click on a column head in the model matrix overwrites every model row at once; this
# record is what makes that switch reversible.
#
# Its own file, for the same reason model_capabilities.py keeps one: POST /api/settings/
# rewrites user_settings.json from the keys the form renders, config knows only the
# settings it declares, and a record that survives a save must not depend on either.
LAST_USER_SETTING_FILE = Path(__file__).parent.parent.parent / "last_user_setting.json"

# The roles the model matrix shows -- the ones a column click can overwrite. The local
# safety model is set in its own section and no preset touches it. Derived from the
# list above so the two cannot drift apart.
_SAFETY_SECTION_FIELDS = ('SAFETY_MODEL',)
RECORDED_ROLE_FIELDS = tuple(f for f in DSGVO_REVIEWED_FIELDS
                             if f not in _SAFETY_SECTION_FIELDS)


def _model_world(active: Optional[str] = None) -> dict:
    """What a role field's value is resolved against, read once per save:
    the names the local station lists (`local`, the bare names), and the
    cloud routes with the order they are taken in (`routes`, `order`;
    chat_routes._cloud_routes). `active` is the provider this save makes
    active, so a model is ranked by the state being saved and not by the one
    on disk."""
    from my_app.routes.chat_routes import _cloud_routes, list_chat_models
    models, _station_unreachable, matrix = list_chat_models()
    local = []
    for m in models:
        model_id = str(m.get('id') or '')
        if m.get('service') == 'local' and model_id:
            local.append(model_id[len('local/'):] if model_id.startswith('local/') else model_id)
    order, routes = _cloud_routes(matrix, active=active)
    return {'local': local, 'order': order, 'routes': routes}


def resolve_role_model(typed: str, world: Optional[dict] = None) -> str:
    """The platform id for what somebody wrote into a role field.

    The settings page shows a model the way its provider names it and never
    the prefix that makes it a platform id (internal paths are not exposed in
    the UI; the prefix is added in the record so the fallbacks work). So what
    arrives here is a provider's own path ('z-ai/glm-5.3',
    'openai/gpt-5.6-terra' copied from OpenRouter), the register's name
    ('glm-5.3'), a local model's name, or an id the page read back.

    What is resolved is the MODEL, and the route is the platform's: the one
    the pickers offer for that model (conform first, then the active provider,
    then the table). In this order:

    1. A name the local station lists is a local model, stored as written
       (with or without the 'local/' the canvas writes), whatever a provider
       calls one of its own.
    2. A path any provider publishes for a register model -- keyed or not, so
       a path copied from a site this installation holds no key for still
       says which model it means -- names that model; so does '<provider>/
       <path>' of any provider, and so does the register's name. The model
       is then stored through the first provider in the order that reaches
       it. 'openai/gpt-5.6-terra' is OpenRouter's path AND OpenAI's own id
       for the same model; both name the model, and the route is the list's.
    3. Anything else is stored as written: a platform id of a keyed provider
       outside the register is a route the gate takes as it is; a name
       nobody reaches, the gate names at run time (schema_pipeline_routes),
       and the page says under the field that no provider carries it.
    """
    value = (typed or '').strip()
    if not value:
        return value
    if world is None:
        world = _model_world()
    wanted = value.casefold()
    bare = wanted[len('local/'):] if wanted.startswith('local/') else wanted
    for name in world.get('local') or []:
        if str(name).casefold() == bare:
            # The station's own spelling, in the form it was written.
            return f"local/{name}" if wanted.startswith('local/') else str(name)
    routes = world.get('routes') or {}
    order = world.get('order') or []
    provider, path = split_provider(value)
    model = None
    for name, per_provider in routes.items():
        for p, p_path in (per_provider or {}).items():
            p_path = str(p_path).casefold()
            if p_path == wanted or (p == provider and p_path == path.casefold()):
                model = name
                break
        if model is not None:
            break
    if model is None:
        model = next((n for n in routes if str(n).casefold() == wanted), None)
    if model is None:
        return value
    for p in order:
        if p in routes[model]:
            return f"{p}/{routes[model][p]}"
    # Named, but reached by no provider with a key: stored as written.
    return value


def _read_last_user_setting() -> dict:
    """{"models": {field: model}, "EXTERNAL_LLM_PROVIDER": str} -- empty if none yet."""
    if not LAST_USER_SETTING_FILE.exists():
        return {}
    try:
        with open(LAST_USER_SETTING_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"[SETTINGS] {LAST_USER_SETTING_FILE.name} not readable: {e}")
        return {}


def _write_last_user_setting(record: dict) -> None:
    LAST_USER_SETTING_FILE.parent.mkdir(exist_ok=True)
    with open(LAST_USER_SETTING_FILE, 'w') as f:
        json.dump(record, f, indent=2)


def _read_settings_file() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[SETTINGS] {SETTINGS_FILE.name} not readable: {e}")
        return {}


def _dsgvo_review():
    """Per configured role: which service it reaches, and what is recorded there.

    The one rule. The public header endpoint below counts these entries; the
    settings page (behind the settings password) is handed the same list and
    names them. Two screens, one statement — which is what the prefix allowlist
    in views/SettingsView.vue could not deliver, because it was a second rule.
    """
    review = []
    for field in DSGVO_REVIEWED_FIELDS:
        value = (getattr(config, field, '') or '').strip()
        if not value:
            continue
        service = _service_reached(value)
        review.append({
            'field': field,
            'model': value,
            'service': service,
            'recorded': _recorded_conformity(service),
        })
    return review


@settings_bp.route('/dsgvo-setting', methods=['GET'])
def get_dsgvo_setting():
    """Public endpoint: what the platform records about the session's data path.

    Reads _dsgvo_review() and adds the configured provider preset, which decides
    what a place is OFFERED when it names no model of its own. It derives
    nothing from the form of a model id and says nothing about a service the
    platform has not recorded.

    Not the stored DSGVO_CONFORMITY flag: it drifts away from the matrix.

    Answers `state`: conform · preset_not_conform · models_flagged · unknown.
    Not knowing is amber, never red. Public, so the answer carries no model ids,
    no role names and no provider name — the settings page that names them sits
    behind the settings password.
    """
    provider = (config.EXTERNAL_LLM_PROVIDER or 'none').strip().lower()
    preset_service = 'local' if provider in ('local', 'none') else provider
    preset_conform = _recorded_conformity(preset_service)
    if preset_conform is None:
        # A provider the matrix does not record. Nothing is claimed about it.
        return jsonify({'state': 'unknown'})

    review = _dsgvo_review()
    flagged = [r for r in review if r['recorded'] is False]
    unrecorded = [r for r in review if r['recorded'] is None]

    if flagged:
        # The count, not the model ids: this endpoint is public, the settings
        # page that names them is behind the settings password.
        return jsonify({'state': 'models_flagged', 'flagged_count': len(flagged)})
    if not preset_conform:
        return jsonify({'state': 'preset_not_conform'})
    if unrecorded:
        return jsonify({'state': 'unknown'})
    return jsonify({'state': 'conform',
                    'local_only': preset_service == 'local'
                                  and all(r['service'] == 'local' for r in review)})


@settings_bp.route('/gpu-info', methods=['GET'])
def get_gpu_info():
    """
    Detect GPU and return VRAM information for auto-selection

    No authentication required - just hardware info

    Returns:
        {
            "detected": true,
            "vram_mb": 97887,
            "vram_gb": 96,
            "vram_tier": "vram_96",
            "gpu_name": "NVIDIA RTX 5090"
        }
    """
    gpu_info = detect_gpu_vram()
    return jsonify(gpu_info), 200


@settings_bp.route('/generation-progress', methods=['GET'])
def get_generation_progress():
    """{step, total_steps, active}: which denoising step the card is on, as
    the ComfyUI client hears it (services/comfyui_ws_client.py step_now).
    Until stage 4 of the move to ComfyUI this relayed the GPU service's
    progress reading, the pair of a Diffusers run."""
    from my_app.services.comfyui_ws_client import step_now
    return jsonify(step_now())


@settings_bp.route('/gpu-realtime', methods=['GET'])
def get_gpu_realtime():
    """
    Get realtime GPU statistics for edutainment display.

    No authentication required - just hardware monitoring data.

    Uses nvidia-smi to fetch:
    - power.draw: Current power consumption (Watts)
    - power.limit: TDP/Power limit (Watts)
    - temperature.gpu: Current temperature (Celsius)
    - utilization.gpu: GPU utilization (%)
    - memory.used: VRAM currently used (MB)
    - memory.total: Total VRAM (MB)

    Also calculates:
    - co2_per_kwh: CO2 emissions factor (g/kWh, default: German grid 400g)

    Returns:
        {
            "available": true,
            "gpu_name": "NVIDIA RTX 6000",
            "power_draw_watts": 285.32,
            "power_limit_watts": 600,
            "temperature_celsius": 72,
            "utilization_percent": 98,
            "memory_used_mb": 32456,
            "memory_total_mb": 49152,
            "memory_used_percent": 66.1,
            "co2_per_kwh_grams": 400
        }
    """
    try:
        # Query comprehensive GPU stats
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=name,power.draw,power.limit,temperature.gpu,utilization.gpu,memory.used,memory.total',
                '--format=csv,noheader,nounits'
            ],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0:
            logger.warning("[GPU-REALTIME] nvidia-smi failed")
            return jsonify({
                "available": False,
                "error": "nvidia-smi not available or failed"
            }), 200

        # Parse output (format: "name, power.draw, power.limit, temp, util, mem_used, mem_total")
        line = result.stdout.strip().split('\n')[0]  # First GPU
        parts = [p.strip() for p in line.split(', ')]

        if len(parts) < 7:
            logger.warning(f"[GPU-REALTIME] Unexpected nvidia-smi output: {line}")
            return jsonify({
                "available": False,
                "error": "Unexpected nvidia-smi output format"
            }), 200

        gpu_name = parts[0]
        power_draw = float(parts[1]) if parts[1] not in ['[N/A]', 'N/A', ''] else 0.0
        power_limit = float(parts[2]) if parts[2] not in ['[N/A]', 'N/A', ''] else 0.0
        temperature = int(float(parts[3])) if parts[3] not in ['[N/A]', 'N/A', ''] else 0
        utilization = int(float(parts[4])) if parts[4] not in ['[N/A]', 'N/A', ''] else 0
        memory_used = int(float(parts[5])) if parts[5] not in ['[N/A]', 'N/A', ''] else 0
        memory_total = int(float(parts[6])) if parts[6] not in ['[N/A]', 'N/A', ''] else 1

        # Calculate memory percentage
        memory_percent = round((memory_used / memory_total) * 100, 1) if memory_total > 0 else 0

        # CO2 factor: German electricity grid average ~400g CO2/kWh (2024)
        # This could be made configurable in the future
        co2_per_kwh = 400

        return jsonify({
            "available": True,
            "gpu_name": gpu_name,
            "power_draw_watts": power_draw,
            "power_limit_watts": power_limit,
            "temperature_celsius": temperature,
            "utilization_percent": utilization,
            "memory_used_mb": memory_used,
            "memory_total_mb": memory_total,
            "memory_used_percent": memory_percent,
            "co2_per_kwh_grams": co2_per_kwh
        }), 200

    except subprocess.TimeoutExpired:
        logger.warning("[GPU-REALTIME] nvidia-smi timed out")
        return jsonify({
            "available": False,
            "error": "nvidia-smi timed out"
        }), 200
    except Exception as e:
        logger.error(f"[GPU-REALTIME] Error: {e}")
        return jsonify({
            "available": False,
            "error": str(e)
        }), 200



@settings_bp.route('/', methods=['GET'])
@require_settings_auth
def get_settings():
    """Get current configuration and hardware matrix"""
    try:
        # Collect all current config values
        current = {
            # General Settings
            # Normalised, so an installation whose user_settings.json still
            # holds the pre-2026-08-12 name arrives at an option the select
            # actually has, instead of showing an empty field.
            "UI_MODE": config.normalise_ui_mode(config.UI_MODE),
            "DEFAULT_SAFETY_LEVEL": config.DEFAULT_SAFETY_LEVEL,
            "DEFAULT_LANGUAGE": config.DEFAULT_LANGUAGE,

            # Model Configuration
            "STAGE1_TEXT_MODEL": config.STAGE1_TEXT_MODEL,
            "STAGE2_INTERCEPTION_MODEL": config.STAGE2_INTERCEPTION_MODEL,
            "STAGE2_OPTIMIZATION_MODEL": config.STAGE2_OPTIMIZATION_MODEL,
            "STAGE3_MODEL": config.STAGE3_MODEL,
            "CHAT_HELPER_MODEL": config.CHAT_HELPER_MODEL,
            "PERSONA_MODEL": config.PERSONA_MODEL,
            "RESONA_MODEL": config.RESONA_MODEL,
            "IMAGE_ANALYSIS_MODEL": config.IMAGE_ANALYSIS_MODEL,
            "CODING_MODEL": config.CODING_MODEL,
            "KNOWLEDGE_PROCESSING_MODEL": config.KNOWLEDGE_PROCESSING_MODEL,
            "SAFETY_MODEL": config.SAFETY_MODEL,

            # API Configuration
            "EXTERNAL_LLM_PROVIDER": config.EXTERNAL_LLM_PROVIDER,
            "DSGVO_CONFORMITY": config.DSGVO_CONFORMITY,
        }

        # Model roles running on config.py's coded default rather than an
        # explicit user_settings.json entry. A silent fallback like this is
        # exactly what broke Resona's translation: Settings should
        # always be able to show when one is active, not just the value it
        # resolved to.
        _non_model_keys = {
            "UI_MODE", "DEFAULT_SAFETY_LEVEL", "DEFAULT_LANGUAGE",
            "EXTERNAL_LLM_PROVIDER", "DSGVO_CONFORMITY",
        }
        _configured = getattr(config, "_USER_CONFIGURED_KEYS", set())
        defaults_in_use = [k for k in current if k not in _non_model_keys and k not in _configured]

        return jsonify({
            "current": current,
            "matrix": get_hardware_matrix(),
            "defaults_in_use": defaults_in_use,
            # Not a config attribute: this one records what was set, not what is in
            # force. Each row is handed over WITH its service and what is recorded
            # about it, so the page never derives a data-protection statement of its own.
            "last_user_models": {
                field: {
                    "model": model,
                    "service": _service_reached(model),
                    "recorded": _recorded_conformity(_service_reached(model)),
                }
                for field, model in (_read_last_user_setting().get('models') or {}).items()
                if str(model or '').strip()
            },
            # Behind the settings password, so this one names the roles, the
            # models and the services. The public header endpoint counts the
            # same list. The page must not raise a rule of its own over it.
            "dsgvo_review": _dsgvo_review()
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting config: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/', methods=['POST'])
@require_settings_auth
def save_settings():
    """Save all settings to user_settings.json"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        # API keys travel in the same form under the provider's env-var name
        # (OPENROUTER_API_KEY, ...) and are saved separately, each into the key
        # file the provider table names for it. Popped whether or not a value
        # came, so no key ever lands in user_settings.json.
        for _name in provider_names():
            _entry = provider_entry(_name) or {}
            _var, _path = _entry.get("env_var"), key_file_path(_name)
            if not _var or _path is None:
                continue
            _key = data.pop(_var, None)
            if _key:
                _path.parent.mkdir(exist_ok=True)
                with open(_path, 'w') as f:
                    f.write(_key.strip())
                logger.info(f"[SETTINGS] {_entry.get('label', _name)} API Key updated")

        # A role names a model the way its provider names it, or the way the
        # register does; the platform id with the provider in front is made
        # here and never typed. What was resolved goes back
        # to the page, which shows the same field again from the saved id.
        # Only a value this save CHANGES is resolved: a field that still holds
        # what the page read back -- the file's value, or config's where the
        # file holds none (defaults_in_use) -- stays as it is, whatever the
        # list would route the same model through today. The
        # rows a column click staged are the preset's own platform ids and
        # stay what the column says; the world is read once per save, ranked
        # by the provider this save makes active.
        previous = _read_settings_file()
        resolved = {}
        staged = {f for f in (data.get('PRESET_SWITCH_FIELDS') or [])
                  if isinstance(f, str)}
        world = None
        for field in DSGVO_REVIEWED_FIELDS:
            typed = str(data.get(field) or '').strip()
            if not typed or field in staged:
                continue
            unchanged = {str(previous.get(field) or '').strip(),
                         str(getattr(config, field, '') or '').strip()}
            if typed in unchanged:
                continue
            if world is None:
                world = _model_world(active=str(data.get('EXTERNAL_LLM_PROVIDER') or '').strip() or None)
            model_id = resolve_role_model(typed, world)
            if model_id != typed:
                data[field] = model_id
                resolved[field] = model_id

        # Which rows of this save came from a click on a column head. Those carry a
        # provider's preset, not the user's own pick -- so for them the record keeps
        # what the switch REPLACES. Every other changed row is the user's own act and
        # goes into the record as it stands. A save that names no rows is an ordinary
        # save, which is also what any client that does not know the field sends.
        switched = {f for f in (data.pop('PRESET_SWITCH_FIELDS', None) or [])
                    if f in RECORDED_ROLE_FIELDS}
        record = _read_last_user_setting()
        models = dict(record.get('models') or {})
        for field in RECORDED_ROLE_FIELDS:
            new = str(data.get(field) or '').strip()
            old = str(previous.get(field) or '').strip()
            if field in switched:
                # Only if nothing is recorded for this row yet: a second switch must
                # not record the first switch's models as the user's own.
                if field not in models and old:
                    models[field] = old
            elif new and (new != old or field not in models):
                models[field] = new
        if switched:
            recorded_provider = (record.get('EXTERNAL_LLM_PROVIDER')
                                 or previous.get('EXTERNAL_LLM_PROVIDER') or '')
        else:
            recorded_provider = str(data.get('EXTERNAL_LLM_PROVIDER') or '').strip()
        if models:
            _write_last_user_setting({
                'models': models,
                'EXTERNAL_LLM_PROVIDER': recorded_provider,
            })

        # Write all other settings to user_settings.json
        SETTINGS_FILE.parent.mkdir(exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"[SETTINGS] Saved {len(data)} settings to {SETTINGS_FILE.name}")

        return jsonify({
            "success": True,
            "message": "Configuration saved. Backend restart required to apply changes.",
            "resolved": resolved,
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error saving config: {e}")
        return jsonify({"error": str(e)}), 500


def _masked_key(provider: str) -> str:
    """The key of one provider as the page may show it: first seven and last
    four characters -- '***' for a key of eleven characters or fewer, which
    says there is one without showing it -- or '' where the file holds none.
    Read the way the platform reads it: a line the platform would not take
    as the key is not shown as one either."""
    key = key_in_file(provider)
    if not key:
        return ""
    return f"{key[:7]}...{key[-4:]}" if len(key) > 11 else "***"


@settings_bp.route('/aws-credentials', methods=['POST'])
@require_settings_auth
def upload_aws_credentials():
    """Upload AWS credentials CSV (from AWS IAM Console)"""
    try:
        if 'csv' not in request.files:
            return jsonify({"error": "No CSV file provided"}), 400

        file = request.files['csv']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Read CSV content
        import csv
        import io

        # Decode and remove BOM if present
        content = file.read().decode('utf-8-sig')  # utf-8-sig automatically strips BOM
        csv_reader = csv.DictReader(io.StringIO(content))

        # Parse AWS credentials (format: Access key ID,Secret access key)
        # Be flexible with column names (spaces, case)
        credentials = None
        for row in csv_reader:
            # Normalize column names (strip, lowercase)
            normalized_row = {k.strip().lower(): v.strip() for k, v in row.items()}

            # Look for access key and secret key (flexible matching)
            access_key = (
                normalized_row.get('access key id') or
                normalized_row.get('accesskeyid') or
                normalized_row.get('access_key_id')
            )
            secret_key = (
                normalized_row.get('secret access key') or
                normalized_row.get('secretaccesskey') or
                normalized_row.get('secret_access_key')
            )

            if access_key and secret_key:
                credentials = {
                    'access_key_id': access_key,
                    'secret_access_key': secret_key
                }
                break

        if not credentials:
            return jsonify({"error": "Invalid CSV format. Expected columns: 'Access key ID', 'Secret access key'"}), 400

        # Save credentials to setup_aws_env.sh
        env_script_path = Path(__file__).parent.parent.parent / "setup_aws_env.sh"
        env_script_content = f'''#!/bin/bash
# AWS Bedrock Environment Setup (Auto-generated from Settings Page)
# USAGE: source devserver/setup_aws_env.sh

export AWS_ACCESS_KEY_ID="{credentials['access_key_id']}"
export AWS_SECRET_ACCESS_KEY="{credentials['secret_access_key']}"
export AWS_DEFAULT_REGION="eu-central-1"

echo "✅ AWS Bedrock environment variables set"
echo "   Region: $AWS_DEFAULT_REGION"
'''

        with open(env_script_path, 'w') as f:
            f.write(env_script_content)

        # Make executable
        import stat
        env_script_path.chmod(env_script_path.stat().st_mode | stat.S_IEXEC)

        logger.info(f"[SETTINGS] AWS credentials saved to {env_script_path.name}")

        return jsonify({
            "success": True,
            "message": "AWS credentials saved. Run 'source devserver/setup_aws_env.sh' and restart server."
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error uploading AWS credentials: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/sessions/available-dates', methods=['GET'])
@require_settings_auth
def get_available_dates():
    """Get list of dates that have sessions with counts"""
    try:
        exports_path = Path(config.JSON_STORAGE_DIR)

        if not exports_path.exists():
            return jsonify({"dates": []}), 200

        # Collect dates with session counts
        date_counts = {}

        # Use helper to find all metadata files (handles nested structure)
        metadata_files = get_cached_metadata_files(exports_path)

        for metadata_info in metadata_files:
            try:
                with open(metadata_info.metadata_path) as f:
                    metadata = json.load(f)

                timestamp_str = metadata.get('timestamp', '')
                timestamp_dt = datetime.fromisoformat(timestamp_str)
                date_str = timestamp_dt.date().isoformat()

                date_counts[date_str] = date_counts.get(date_str, 0) + 1
            except:
                continue

        # Convert to sorted list
        available_dates = [
            {"date": date_str, "count": count}
            for date_str, count in sorted(date_counts.items(), reverse=True)
        ]

        return jsonify({"dates": available_dates}), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting available dates: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/sessions', methods=['GET'])
@require_settings_auth
def get_sessions():
    """
    Get list of all sessions from /exports/json with pagination and filtering

    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 50, max: 500)
    - date_from: Filter by start date (YYYY-MM-DD)
    - date_to: Filter by end date (YYYY-MM-DD)
    - device_id: Filter by device ID
    - config_name: Filter by config name
    - safety_level: Filter by safety level
    - search: Search in run_id
    - sort: Sort field (timestamp, device_id, config_name, default: timestamp)
    - order: Sort order (asc, desc, default: desc)
    """
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 500)
        date_from = request.args.get('date_from', None)
        date_to = request.args.get('date_to', None)
        device_filter = request.args.get('device_id', None)
        config_filter = request.args.get('config_name', None)
        safety_filter = request.args.get('safety_level', None)
        search_filter = request.args.get('search', None)
        source_view_filter = request.args.get('source_view', None)
        sort_field = request.args.get('sort', 'timestamp')
        sort_order = request.args.get('order', 'desc')

        # Path to exports/json
        exports_path = Path(config.JSON_STORAGE_DIR)

        if not exports_path.exists():
            return jsonify({
                "sessions": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            }), 200

        # Collect all sessions
        all_sessions = []

        # Use helper to find all metadata files (handles nested structure)
        metadata_files = get_cached_metadata_files(exports_path)

        for metadata_info in metadata_files:
            try:
                with open(metadata_info.metadata_path) as f:
                    metadata = json.load(f)

                # Set session_dir to run_folder for reading other files
                session_dir = metadata_info.run_folder

                # Parse timestamp
                timestamp_str = metadata.get('timestamp', '')
                try:
                    timestamp_dt = datetime.fromisoformat(timestamp_str)
                except:
                    continue

                # The run's config_used entity, for the pipeline; the recorder
                # numbers its files per run, so the name is read off the entity,
                # not guessed (finding S-007 of the code review of 2026-10-10).
                config_used_file = None
                for entity in metadata.get('entities', []):
                    if entity.get('type') == 'config_used':
                        config_used_file = session_dir / 'final' / entity['filename']
                        break
                # The output mode is NOT read off that file: its
                # media_preferences.default_output is the interception config's
                # default, not what the run produced, and a song made under a
                # perspective whose default is the image would read
                # "text2image". The mode comes from the run's outputs below, as
                # it did for every current run until 2026-10-10, when the lookup
                # here only ever found the root-level file of the older layout;
                # that file is still read the way it was.
                legacy_config_file = session_dir / "01_config_used.json"
                stage2_pipeline = None
                output_mode = None
                has_input_image = False

                # Check for input image in entities
                for entity in metadata.get('entities', []):
                    if entity.get('type') == 'input_image':
                        has_input_image = True
                        break

                if not legacy_config_file.exists() and config_used_file is not None and config_used_file.exists():
                    try:
                        with open(config_used_file) as f:
                            stage2_pipeline = json.load(f).get('pipeline')
                    except Exception:
                        pass

                if legacy_config_file.exists():
                    try:
                        with open(legacy_config_file) as f:
                            config_used = json.load(f)
                            stage2_pipeline = config_used.get('pipeline')
                            output_type = config_used.get('media_preferences', {}).get('default_output', 'unknown')

                            # Determine output mode
                            if output_type == 'image':
                                if has_input_image:
                                    output_mode = 'image+text2image'
                                else:
                                    output_mode = 'text2image'
                            elif output_type == 'video':
                                if has_input_image:
                                    output_mode = 'image+text2video'
                                else:
                                    output_mode = 'text2video'
                            elif output_type == 'audio':
                                output_mode = 'text2audio'
                            else:
                                output_mode = output_type
                    except:
                        pass

                # Fallback: Infer output mode from entity types (for old sessions without config_used.json)
                if output_mode is None:
                    for entity in metadata.get('entities', []):
                        entity_type = entity.get('type', '')
                        if entity_type == 'output_image':
                            output_mode = 'image+text2image' if has_input_image else 'text2image'
                            break
                        elif entity_type == 'output_video':
                            output_mode = 'image+text2video' if has_input_image else 'text2video'
                            break
                        elif entity_type == 'output_audio':
                            output_mode = 'text2audio'
                            break

                # Apply date range filter
                session_date = timestamp_dt.date()
                if date_from:
                    try:
                        from_date = datetime.fromisoformat(date_from).date()
                        if session_date < from_date:
                            continue
                    except:
                        pass

                if date_to:
                    try:
                        to_date = datetime.fromisoformat(date_to).date()
                        if session_date > to_date:
                            continue
                    except:
                        pass

                # Apply device filter
                if device_filter and metadata.get('device_id') != device_filter:
                    continue

                # Apply config filter
                if config_filter and metadata.get('config_name') != config_filter:
                    continue

                # Apply safety level filter
                if safety_filter and metadata.get('safety_level') != safety_filter:
                    continue

                # Apply search filter
                if search_filter and search_filter.lower() not in metadata.get('run_id', '').lower():
                    continue

                # Apply source_view filter
                if source_view_filter and metadata.get('source_view') != source_view_filter:
                    continue

                # Count media files and find first media for thumbnail
                media_count = sum(
                    1 for entity in metadata.get('entities', [])
                    if is_media_entity(entity.get('type'))
                )
                thumbnail_path = None
                thumbnail_type = None
                thumbnail_url = None
                preview = resolve_preview_media(session_dir, metadata)
                if preview:
                    _, file_subpath, thumbnail_type = preview
                    # The full-size file, kept as the fallback the table uses
                    # when this server cannot build a miniature.
                    thumbnail_path = f"/exports/json/{metadata_info.relative_path}/{file_subpath}"
                    if can_build_thumbnail(thumbnail_type):
                        thumbnail_url = f"/api/settings/sessions/{metadata.get('run_id')}/thumbnail"

                # Build session summary
                session_summary = {
                    'run_id': metadata.get('run_id'),
                    'timestamp': timestamp_str,
                    'config_name': metadata.get('config_name'),
                    'stage2_pipeline': stage2_pipeline,
                    'output_mode': output_mode,
                    'safety_level': metadata.get('safety_level'),
                    'device_id': metadata.get('device_id'),
                    'stage': metadata.get('current_state', {}).get('stage'),
                    'step': metadata.get('current_state', {}).get('step'),
                    'entity_count': len(metadata.get('entities', [])),
                    'media_count': media_count,
                    'session_dir': metadata_info.relative_path,
                    'thumbnail': thumbnail_path,
                    'thumbnail_url': thumbnail_url,
                    'thumbnail_type': thumbnail_type,
                    'source_view': metadata.get('source_view'),
                }

                all_sessions.append(session_summary)

            except Exception as e:
                logger.error(f"[SETTINGS] Error reading metadata from {metadata_info.relative_path}: {e}")
                continue

        # Sort sessions
        reverse = (sort_order == 'desc')
        if sort_field in ['timestamp', 'device_id', 'config_name', 'safety_level']:
            all_sessions.sort(key=lambda x: x.get(sort_field, ''), reverse=reverse)

        # Pagination
        total = len(all_sessions)
        total_pages = (total + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        paginated_sessions = all_sessions[start:end]

        # Collect unique values for filters
        unique_devices = sorted(set(s['device_id'] for s in all_sessions if s.get('device_id')))
        unique_configs = sorted(set(s['config_name'] for s in all_sessions if s.get('config_name')))
        unique_safety_levels = sorted(set(s['safety_level'] for s in all_sessions if s.get('safety_level')))
        unique_source_views = sorted(set(s['source_view'] for s in all_sessions if s.get('source_view')))

        return jsonify({
            "sessions": paginated_sessions,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "filters": {
                "devices": unique_devices,
                "configs": unique_configs,
                "safety_levels": unique_safety_levels,
                "source_views": unique_source_views
            }
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting sessions: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/sessions/<run_id>/thumbnail', methods=['GET'])
@require_settings_auth
def get_session_thumbnail(run_id):
    """
    A small JPEG preview of the session's first output medium.

    The table would otherwise pull the full render - megabytes per row - to
    show it at 60x60. Miniatures are built once and cached; an export is
    immutable once written, so a cache entry newer than its source is served
    as is, and the browser is told it may keep it.
    """
    try:
        exports_path = Path(config.JSON_STORAGE_DIR)

        # The cached tree walk is shared with the session list; only a session
        # written within the cache TTL needs the slower targeted lookup.
        metadata_path = None
        for metadata_info in get_cached_metadata_files(exports_path):
            if metadata_info.run_id == run_id:
                metadata_path = metadata_info.metadata_path
                break
        if metadata_path is None:
            metadata_path = find_metadata_by_run_id(exports_path, run_id)
        if not metadata_path:
            return jsonify({"error": "Session not found"}), 404

        with open(metadata_path) as f:
            metadata = json.load(f)

        preview = resolve_preview_media(metadata_path.parent, metadata)
        if not preview:
            return jsonify({"error": "Session has no preview medium"}), 404

        source, _, kind = preview
        if not source.exists():
            return jsonify({"error": "Media file not found"}), 404
        if not can_build_thumbnail(kind):
            return jsonify({"error": f"No thumbnail support for {kind}"}), 415

        cache_file = cached_thumbnail(source, kind, run_id)
        if cache_file is None:
            return jsonify({"error": "Thumbnail could not be built"}), 500

        response = send_file(str(cache_file), mimetype='image/jpeg', conditional=True)
        # Exports do not change after the run, so the browser may keep this;
        # the marker exempts it from the app-wide no-store policy.
        response.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
        response.headers['X-Immutable-Asset'] = '1'
        return response

    except Exception as e:
        logger.error(f"[SETTINGS] Error building thumbnail for {run_id}: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/sessions/<run_id>', methods=['GET'])
@require_settings_auth
def get_session_detail(run_id):
    """Get detailed information for a specific session"""
    try:
        exports_path = Path(config.JSON_STORAGE_DIR)

        # Use helper to find session by run_id (handles nested structure)
        metadata_path = find_metadata_by_run_id(exports_path, run_id)

        if not metadata_path:
            return jsonify({"error": "Session not found"}), 404

        session_dir = metadata_path.parent
        relative_path = str(session_dir.relative_to(exports_path))

        with open(metadata_path) as f:
            metadata = json.load(f)

        # Read all entity files
        entities_with_content = []
        for entity in metadata.get('entities', []):
            from my_app.services.pipeline_recorder import public_entity
            entity_copy = public_entity(entity).copy()
            filename = entity.get('filename')
            if filename:
                # Try final/ subdirectory first (new structure), then direct (old structure)
                file_path = session_dir / "final" / filename
                file_subpath = f"final/{filename}"

                if not file_path.exists():
                    # Fallback to direct path for older sessions
                    file_path = session_dir / filename
                    file_subpath = filename

                if file_path.exists():
                    # For images, provide URL path
                    if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                        entity_copy['image_url'] = f"/exports/json/{relative_path}/{file_subpath}"
                        entity_copy['media_type'] = 'image'
                    # For videos, provide URL path
                    elif file_path.suffix.lower() in ['.mp4', '.webm', '.mov']:
                        entity_copy['video_url'] = f"/exports/json/{relative_path}/{file_subpath}"
                        entity_copy['media_type'] = 'video'
                    # For text files, read content
                    elif file_path.suffix in ['.txt', '.json']:
                        try:
                            with open(file_path) as f:
                                entity_copy['content'] = f.read()
                        except:
                            entity_copy['content'] = None
            entities_with_content.append(entity_copy)

        metadata['entities'] = entities_with_content

        return jsonify(metadata), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting session detail: {e}")
        return jsonify({"error": str(e)}), 500



@settings_bp.route('/hardware-matrix', methods=['POST'])
@require_settings_auth
def save_matrix():
    """
    Save hardware matrix to JSON file (developer feature).

    Expects JSON body with the complete matrix structure.
    Validates JSON before saving.
    """
    try:
        matrix_data = request.get_json()
        if not matrix_data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        # Basic validation: check if it's a dict with expected keys
        if not isinstance(matrix_data, dict):
            return jsonify({"success": False, "error": "Matrix must be a JSON object"}), 400

        # New structure validation: vision_presets, llm_presets, local_llm_presets
        expected_sections = ['vision_presets', 'llm_presets', 'local_llm_presets']
        for section in expected_sections:
            if section not in matrix_data:
                logger.warning(f"[SETTINGS] Matrix missing section: {section}")

        success, message = save_hardware_matrix(matrix_data)
        if success:
            logger.info("[SETTINGS] Hardware matrix saved successfully")
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500

    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"Invalid JSON: {e}"}), 400
    except Exception as e:
        logger.error(f"[SETTINGS] Error saving matrix: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route('/providers', methods=['GET'])
@require_settings_auth
def list_providers():
    """The provider table for the settings page, in table order: name, label,
    dialect, whether the provider keeps a key file and where (`key_path`,
    relative to the repository, for the note under the field), what a key of
    this provider starts with (`key_prefix`, the field's placeholder), the
    settings field its key is sent under, whether a key is present on this
    installation (for a provider without a key file -- AWS Bedrock, whose SDK
    finds its own credentials -- that is always true, as has_key says), and
    the key as the page may show it (`masked`: first seven and last four
    characters, '' where there is none). Never the key itself. Until
    2026-09-12 the page kept that list itself, three times over, and asked
    for the masked keys one route per provider."""
    rows = []
    for name, entry in provider_table().items():
        key_file = entry.get("key_file")
        try:
            masked = _masked_key(name) if key_file else ""
        except Exception as e:
            logger.error(f"[SETTINGS] Error reading {name} key: {e}")
            masked = ""
        rows.append({
            "name": name,
            "label": entry.get("label", name),
            "dialect": entry.get("dialect"),
            "key_file": bool(key_file),
            "key_path": f"devserver/{key_file}" if key_file else "",
            "key_prefix": entry.get("key_prefix", ""),
            # The settings field a new key is sent under (save_settings reads
            # it by this name and writes the file).
            "key_field": entry.get("env_var"),
            "has_key": has_key(name),
            "masked": masked,
        })
    return jsonify({"providers": rows})



@settings_bp.route('/hardware-matrix/reset', methods=['POST'])
@require_settings_auth
def reset_matrix():
    """Overwrite the live hardware matrix with the shipped recommendation set."""
    defaults, error = load_default_hardware_matrix()
    if error:
        return jsonify({"success": False, "error": error}), 500

    success, message = save_hardware_matrix(defaults)
    if not success:
        return jsonify({"success": False, "error": message}), 500

    logger.info("[SETTINGS] Hardware matrix reset to shipped recommendations")
    return jsonify({
        "success": True,
        "message": "Matrix reset to our recommendations",
        "matrix": defaults,
    })


@settings_bp.route('/preset/<provider>', methods=['GET'])
@require_settings_auth
def get_preset_for_provider(provider):
    """
    Get merged preset for a provider, using detected VRAM for vision models.

    The preset merges:
    - LLM models from the specified provider
    - Vision models from the detected VRAM tier (always local)

    Args:
        provider: "local" or a name in config/llm_providers.json

    Query params:
        vram_tier: Override detected VRAM (optional)

    Returns:
        {
            "label": "Anthropic Direct API",
            "EXTERNAL_LLM_PROVIDER": "anthropic",
            "DSGVO_CONFORMITY": false,
            "vram_tier": "vram_96",
            "models": {
                "STAGE1_TEXT_MODEL": "anthropic/claude-haiku-4-5",
                "IMAGE_ANALYSIS_MODEL": "local/qwen3-vl:32b",
                ...
            }
        }
    """
    try:
        # Get VRAM tier (from query param or detect)
        vram_tier = request.args.get('vram_tier')
        if not vram_tier:
            gpu_info = detect_gpu_vram()
            vram_tier = gpu_info.get('vram_tier', 'vram_16')

        # Validate provider: this machine, none, or a name the table carries
        valid_providers = ['local', 'none', *provider_names()]
        if provider not in valid_providers:
            return jsonify({"error": f"Invalid provider: {provider}"}), 400

        # Get merged preset
        preset = get_merged_preset(provider, vram_tier)
        preset['vram_tier'] = vram_tier

        return jsonify(preset), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting preset for {provider}: {e}")
        return jsonify({"error": str(e)}), 500



@settings_bp.route('/apply-last-user-models', methods=['POST'])
@require_settings_auth
def apply_last_user_models():
    """Put the recorded user setting back into force, row by row.

    Applying a preset writes a provider's whole column; this one writes back
    what the user had set before doing so. The record can span
    providers, so the provider marker is not derived from the restored models -- it was
    recorded together with them and is written back as it was.
    """
    try:
        record = _read_last_user_setting()
        recorded = record.get('models') or {}
        if not recorded:
            return jsonify({"success": False, "error": "Nothing recorded yet"}), 400

        settings = _read_settings_file()
        applied = []
        for key, value in recorded.items():
            if hasattr(config, key):
                setattr(config, key, value)
            settings[key] = value
            applied.append(key)

        provider_set = str(record.get('EXTERNAL_LLM_PROVIDER') or '').strip()
        if provider_set:
            config.EXTERNAL_LLM_PROVIDER = provider_set
            settings['EXTERNAL_LLM_PROVIDER'] = provider_set

        SETTINGS_FILE.parent.mkdir(exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)

        logger.info(f"[SETTINGS] Recorded user setting restored ({len(applied)} rows), "
                    f"provider {provider_set or 'none recorded, left unchanged'}")
        return jsonify({
            "success": True,
            "applied": applied,
            "provider": provider_set,
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error restoring recorded user setting: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/reload-settings', methods=['POST'])
@require_settings_auth
def reload_settings():
    """Hot-reload user settings without server restart"""
    try:
        from my_app import reload_user_settings
        reload_user_settings()
        logger.info("[SETTINGS] Settings reloaded successfully")
        return jsonify({
            "success": True,
            "message": "Settings applied successfully",
            # config is fresh as of the line above, so the page can take the new
            # review from here rather than asking again.
            "dsgvo_review": _dsgvo_review()
        }), 200
    except Exception as e:
        logger.error(f"[SETTINGS] Error reloading settings: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/backend-status', methods=['GET'])
def get_backend_status():
    """
    Aggregated backend status for the dashboard tab.

    Returns status of all backends: GPU Service sub-backends, ComfyUI, local LLM,
    cloud API key status, GPU hardware, and output configs grouped by backend_type.

    Query parameters:
        force_refresh: Bypass all caches (default: false)
    """
    from concurrent.futures import ThreadPoolExecutor
    
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

    # --- GPU Hardware ---
    gpu_hardware = detect_gpu_vram()

    # --- The card and the media stations ---
    # The block the settings page draws under this name: the media stations'
    # rows, the card's memory bar and the models resident on it. Until stage 7
    # of the move to ComfyUI all of it was one call on the GPU service's
    # /api/health. The stations are read from ComfyUI (stage 6), the card
    # through the gate (services/gpu_gate.py), which reads the driver for
    # memory and processes and ComfyUI for its resident models. `url` names
    # ComfyUI, where the stations and the models are; `reachable` says whether
    # ComfyUI answered for its models.
    gpu_service = {"reachable": False, "url": config.COMFYUI_URL,
                   "sub_backends": {}, "gpu_info": None}

    def _check_gpu_health():
        from my_app.services.gpu_gate import get_gpu_gate
        gate = get_gpu_gate()
        status = gate.vram_status()
        total_mb, free_mb = status.get("total_mb"), status.get("free_mb")
        gpu_info = None
        if total_mb:
            gpu_info = {
                "gpu_name": gate.card_name(),
                "total_vram_gb": round(total_mb / 1024, 2),
                "free_gb": round((free_mb or 0) / 1024, 2),
                "used_gb": round((total_mb - (free_mb or 0)) / 1024, 2),
            }
        return {"reachable": bool((status.get("comfyui") or {}).get("reachable")),
                "gpu": gpu_info, "vram_coordinator": status}

    # The rows of the media stations -- HeartMuLa, Stable Audio, the
    # Crossmodal Lab (Stable Audio with ImageBind), MMAudio -- are what the
    # platform's node package reports on ComfyUI (services/media_stations):
    # whether the station's library imports there and which weight folders
    # are whole. Until stage 6 of the move to ComfyUI each row was a call on
    # the GPU service's /api/<station>/available. No `diffusers` row since
    # stage 4: no surface runs the Diffusers station any more, and asking
    # after it is a call on the old way. Its twin configs go with the station
    # in stage 8. No `text` row since stage 5: the Text Lab's models are
    # folders under models/llm/ that ComfyUI runs (config/text_presets.json);
    # the Text Lab's own routes (text_routes.list_models, list_presets) say
    # which are installed.
    media_rows = ("heartmula", "stable_audio", "cross_aesthetic", "mmaudio")

    def _media_station_rows():
        from my_app.services import media_stations
        stations = media_stations.read()

        def row(*names):
            return {
                "available": all(media_stations.available(n, stations) for n in names),
                "models": [f for n in names for f in media_stations.installed(n, stations)],
            }
        return {
            "heartmula": row("heartmula"),
            "stable_audio": row("stable_audio"),
            "cross_aesthetic": row("stable_audio", "imagebind"),
            "mmaudio": row("mmaudio"),
        }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        futures["health"] = executor.submit(_check_gpu_health)
        futures["stations"] = executor.submit(_media_station_rows)

        # Collect results (10s timeout prevents hanging)
        try:
            health_data = futures["health"].result(timeout=10)
        except Exception as e:
            logger.warning(f"[BACKEND-STATUS] the card could not be read: {type(e).__name__}: {e}")
            health_data = None
        if health_data:
            gpu_service["reachable"] = bool(health_data.get("reachable"))
            gpu_service["gpu_info"] = health_data.get("gpu")
            gpu_service["vram_coordinator"] = health_data.get("vram_coordinator")

        try:
            rows = futures["stations"].result(timeout=10)
        except Exception as e:
            logger.warning(f"[BACKEND-STATUS] the media stations went unread: {e}")
            rows = {}
        for name in media_rows:
            gpu_service["sub_backends"][name] = rows.get(name) or {"available": False}

    # --- ComfyUI + Config Availability (each coroutine on a loop of its own,
    # services/own_loop.py) ---
    comfyui_status = {"reachable": False, "url": config.COMFYUI_URL, "models": {}}
    config_availability = {}
    try:
        from my_app.services.model_availability_service import ModelAvailabilityService
        from my_app.services.own_loop import run_blocking
        service = ModelAvailabilityService()
        if force_refresh:
            service.invalidate_caches()

        # ComfyUI check — failure must NOT prevent config availability check
        try:
            models = run_blocking(service.get_comfyui_models(force_refresh=force_refresh))
            if models:
                comfyui_status["reachable"] = True
                comfyui_status["models"] = models
        except Exception as e:
            logger.info(f"[BACKEND-STATUS] ComfyUI unreachable (non-critical): {e}")

        config_availability = run_blocking(service.check_all_configs())
    except Exception as e:
        logger.warning(f"[BACKEND-STATUS] Availability service check failed: {e}")

    # --- Local LLM (run by ComfyUI; the installed ones off the table of
    # local models, config/local_llm_weights.json) ---
    llm_status = {"reachable": comfyui_status["reachable"], "url": comfyui_status["url"], "models": []}
    try:
        from my_app.services import local_llm_weights
        for name in local_llm_weights.installed_aliases():
            size_gb = (local_llm_weights.entry(name) or {}).get("size_gb")
            llm_status["models"].append({"name": name, "size": f"{size_gb} GB" if size_gb else ""})
        llm_status["models"].sort(key=lambda x: x["name"])
    except Exception as e:
        logger.warning(f"[BACKEND-STATUS] Local LLM list failed: {e}")

    # --- Cloud APIs ---
    # This list decides only WHICH services have a key file here. What is
    # recorded about them comes from the one register, hardware_matrix.json —
    # the same entries the model matrix edits and the header chip reads.
    #
    # The conformity once stood here as a second hand-kept list, and it said
    # `aws_bedrock: dsgvo_compliant: True, region: "EU"`. That is a promise
    # this installation cannot make: Bedrock is conform only if the AWS
    # account is restricted to European regions, and the platform cannot see
    # that account. The region column went with it: a region stood in no
    # register, only as a fixed mapping in this file. The grounds a
    # status was recorded on stay in the register and are read on the badge in
    # the model matrix. They are not spelled out on a surface.
    aws_env_script = Path(__file__).parent.parent.parent / "setup_aws_env.sh"
    cloud_key_files = [
        # (name shown, service in the register, key present). Bedrock keeps no
        # key file; its credentials come with the AWS environment script.
        (name, name,
         aws_env_script.exists() if key_file_path(name) is None else key_file_path(name).exists())
        for name in provider_names()
    ]
    cloud_apis = {}
    for shown, service, key_configured in cloud_key_files:
        cloud_apis["aws_bedrock" if shown == "bedrock" else shown] = {
            "key_configured": key_configured,
            "dsgvo_recorded": _recorded_conformity(service),
        }

    # --- Output Configs by Backend ---
    configs_dir = Path(__file__).parent.parent.parent / "schemas" / "configs" / "output"
    by_backend = {}
    total_configs = 0
    available_count = 0

    if configs_dir.exists():
        for config_file in sorted(configs_dir.glob("*.json")):
            try:
                with open(config_file) as f:
                    cfg = json.load(f)

                config_id = config_file.stem
                meta = cfg.get("meta", {})
                backend_type = meta.get("backend_type", "comfyui")
                name_obj = cfg.get("name", {})
                display_name = name_obj.get("en", config_id)
                is_available = config_availability.get(config_id, False)
                hidden = config_is_hidden(cfg)
                media_type = cfg.get("media_preferences", {}).get("default_output", "unknown")

                if backend_type not in by_backend:
                    by_backend[backend_type] = []

                by_backend[backend_type].append({
                    "id": config_id,
                    "name": display_name,
                    "available": is_available,
                    "hidden": hidden,
                    "media_type": media_type,
                })

                total_configs += 1
                if is_available:
                    available_count += 1

            except Exception as e:
                logger.warning(f"[BACKEND-STATUS] Error reading config {config_file.name}: {e}")

    return jsonify({
        "local_infrastructure": {
            "gpu_service": gpu_service,
            "comfyui": comfyui_status,
            "llm": llm_status,
            "gpu_hardware": gpu_hardware,
        },
        "cloud_apis": cloud_apis,
        "output_configs": {
            "by_backend": by_backend,
            "summary": {
                "total": total_configs,
                "available": available_count,
                "unavailable": total_configs - available_count,
            }
        }
    }), 200


# --- Workshop Model Preloading ---
# Maps physical model IDs to load mechanisms.
# type: 'gpu_service' → POST to GPU service load endpoint
# type: 'comfyui'     → fake-run: build minimal workflow from chunk, submit to ComfyUI
#
# Removed 2026-06-19: stable_audio and acestep.
#   Stable Audio 1.0 is being replaced by Stable Audio 3 — re-add when SA3 lands.
#   ACE-Step then becomes redundant for our workshop scope and is dropped.
#   Probe on the 4090 (2026-06-03) also exposed a now-moot routing bug in the
#   `acestep_simple` / `acestep_longnarrativeprompts` configs: both reference
#   pipeline=music_generation, which hardcodes the heartmula chunk. The correct
#   ACE-Step config (acenet_t2instrumental → output_audio_acenet) was wired
#   correctly; the misnamed configs would have needed cleanup but disappear
#   along with this catalog entry. Treat as a deployment lesson: schema configs
#   should reference real chunks, not pipelines that ignore OUTPUT_CHUNK.

# Human-readable names for Trashy chat
_MODEL_NAMES = {
    'sd35_large': 'Stable Diffusion 3.5 Large',
    'flux2': 'FLUX.2',
    'wan22_t2v': 'Wan 2.2 Text→Video',
    'wan22_i2v': 'Wan 2.2 Image→Video',
    'ltx_video': 'LTX Video',
    'qwen_i2i': 'Qwen Image Edit',
    'qwen_multi': 'Qwen Multi-Image',
    'heartmula': 'HeartMuLa',
}

_WORKSHOP_LOAD_MAP = {
    # The platform's own node, run with its preload_only input: the song
    # models go on the card without a song (services/heartmula_client.
    # preload_workflow). Until stage 6 of the move to ComfyUI this posted the
    # GPU service's heartmula load route.
    'heartmula': {'type': 'comfyui', 'node': 'heartmula'},
    # ComfyUI fake-runs (load models via tiny generation)
    'sd35_large': {'type': 'comfyui', 'chunk': 'output_image_sd35_large'},
    'flux2':      {'type': 'comfyui', 'chunk': 'output_image_flux2'},
    'wan22_t2v':  {'type': 'comfyui', 'chunk': 'output_video_wan22_t2v_fast'},
    'wan22_i2v':  {'type': 'comfyui', 'chunk': 'output_video_wan22_i2v'},
    'ltx_video':  {'type': 'comfyui', 'chunk': 'output_video_ltx'},
    'qwen_i2i':   {'type': 'comfyui', 'chunk': 'output_image_qwen_img2img'},
    'qwen_multi': {'type': 'comfyui', 'chunk': 'output_image_qwen_2511_multi'},
}


# Chunks directory
_CHUNKS_DIR = Path(__file__).parent.parent.parent / "schemas" / "chunks"

# 1x1 white PNG (base64) for LoadImage dummy — uploaded to ComfyUI on first use
_DUMMY_IMAGE_UPLOADED = False
_DUMMY_IMAGE_NAME = "preload_dummy.png"


def _ensure_dummy_image_uploaded():
    """Upload a 1x1 dummy PNG to ComfyUI input/ folder (once per session)."""
    global _DUMMY_IMAGE_UPLOADED
    if _DUMMY_IMAGE_UPLOADED:
        return True
    try:
        import base64
        # 1x1 white PNG
        png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        png_data = base64.b64decode(png_b64)
        comfyui_url = config.COMFYUI_URL
        resp = requests.post(
            f"{comfyui_url}/upload/image",
            files={"image": (_DUMMY_IMAGE_NAME, png_data, "image/png")},
            data={"overwrite": "true"},
            timeout=10,
        )
        _DUMMY_IMAGE_UPLOADED = resp.ok
        return resp.ok
    except Exception as e:
        logger.warning(f"[WORKSHOP] Failed to upload dummy image: {e}")
        return False


def _build_comfyui_preload_workflow(chunk_name: str) -> Optional[dict]:
    """
    Load chunk JSON and build a minimal-cost workflow for model preloading.

    Deep-copies the workflow, then applies overrides to minimize generation cost:
    - Tiny resolution (128x128), 1 step, short prompts
    - LoadImage nodes get a 1x1 dummy PNG
    - Full graph stays intact (ComfyUI requires output nodes)
    """
    import copy

    chunk_path = _CHUNKS_DIR / f"{chunk_name}.json"
    if not chunk_path.exists():
        logger.error(f"[WORKSHOP] Chunk not found: {chunk_path}")
        return None

    try:
        with open(chunk_path) as f:
            chunk = json.load(f)
    except Exception as e:
        logger.error(f"[WORKSHOP] Failed to load chunk {chunk_name}: {e}")
        return None

    workflow = copy.deepcopy(chunk.get("workflow", {}))
    if not workflow:
        return None

    # Ensure dummy image is available for LoadImage nodes
    _ensure_dummy_image_uploaded()

    for _node_id, node in workflow.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        if ct == "EmptyLatentImage":
            inputs["width"] = 128
            inputs["height"] = 128
            inputs["batch_size"] = 1

        elif ct == "EmptySD3LatentImage":
            inputs["width"] = 128
            inputs["height"] = 128
            inputs["batch_size"] = 1

        elif ct in ("Wan22ImageToVideoLatent", "WanImageToVideo"):
            if "width" in inputs:
                inputs["width"] = 128
            if "height" in inputs:
                inputs["height"] = 128
            if "length" in inputs:
                inputs["length"] = 1

        elif ct == "EmptyLTXVLatentVideo":
            inputs["width"] = 128
            inputs["height"] = 128
            inputs["length"] = 1

        elif ct == "EmptyAceStepLatentAudio":
            inputs["seconds"] = 1

        elif ct == "KSampler":
            inputs["steps"] = 1

        elif ct == "KSamplerAdvanced":
            inputs["steps"] = 1
            inputs["end_at_step"] = 1

        elif ct == "LTXVScheduler":
            inputs["steps"] = 1

        elif ct == "SamplerCustom":
            # SamplerCustom doesn't have 'steps' directly; handled by LTXVScheduler
            pass

        elif ct == "CLIPTextEncode":
            # Only override if text is a plain string (not a node reference)
            if isinstance(inputs.get("text"), str):
                inputs["text"] = "preload"

        elif ct == "TextEncodeAceStepAudio":
            inputs["tags"] = "ambient"
            inputs["lyrics"] = "[instrumental]"

        elif ct in ("TextEncodeQwenImageEdit", "TextEncodeQwenImageEditPlus"):
            if isinstance(inputs.get("text"), str):
                inputs["text"] = "preload"

        elif ct == "PrimitiveStringMultiline":
            inputs["value"] = "preload"

        elif ct == "PrimitiveString":
            # Only override if value is a plain string
            if isinstance(inputs.get("value"), str):
                inputs["value"] = "preload"

        elif ct == "LoadImage":
            inputs["image"] = _DUMMY_IMAGE_NAME

        elif ct == "ImageScaleToTotalPixels":
            inputs["megapixels"] = 0.01  # tiny

    return workflow


def _preload_node_workflow(node: str) -> Optional[dict]:
    """The one-node prompt that puts a station's models on the card without
    a generation, for the entries of _WORKSHOP_LOAD_MAP that name a node
    instead of a chunk: HeartMuLa's node takes a preload_only input for this
    (services/heartmula_client.preload_workflow). None when nothing of the
    station is whole, or for a node this map does not know."""
    if node == 'heartmula':
        from my_app.services.heartmula_backend import get_heartmula_backend
        return get_heartmula_backend().preload_workflow()
    return None


def _generate_sse_event(event_type: str, data: dict) -> str:
    """Generate SSE formatted event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@settings_bp.route('/workshop/preload', methods=['POST'])
def workshop_preload():
    """
    Preload selected models into GPU memory via SSE streaming.

    Body: { "models": ["sd35_large", "heartmula", "flux2", ...] }
    Returns: SSE stream with events: model_start, model_complete, model_error, done
    """
    from flask import Response
    from my_app.services.comfyui_service import ComfyUIService

    data = request.get_json(silent=True) or {}
    model_ids = data.get('models', [])
    if not model_ids:
        return jsonify({"error": "models list required"}), 400

    def generate():
        comfyui = ComfyUIService()

        for mid in model_ids:
            load_info = _WORKSHOP_LOAD_MAP.get(mid)
            name = _MODEL_NAMES.get(mid, mid)

            if load_info is None:
                # Cloud model — skip
                yield _generate_sse_event('model_complete', {
                    'model_id': mid, 'name': name, 'skipped': True,
                })
                continue

            yield _generate_sse_event('model_start', {'model_id': mid, 'name': name})

            load_type = load_info.get('type', 'gpu_service')

            if load_type == 'gpu_service':
                try:
                    resp = requests.post(
                        f"{config.GPU_SERVICE_URL}{load_info['path']}",
                        json=load_info.get('body', {}),
                        # Connect side only: the load may be queued behind another
                        # participant's render, and a read cap would report a
                        # failure for a load that is about to happen.
                        timeout=(60, None),
                    )
                    if resp.ok:
                        yield _generate_sse_event('model_complete', {
                            'model_id': mid, 'name': name,
                        })
                    else:
                        yield _generate_sse_event('model_error', {
                            'model_id': mid, 'name': name,
                            'error': f"HTTP {resp.status_code}",
                        })
                except requests.Timeout:
                    yield _generate_sse_event('model_error', {
                        'model_id': mid, 'name': name, 'error': 'timeout (180s)',
                    })
                except Exception as e:
                    yield _generate_sse_event('model_error', {
                        'model_id': mid, 'name': name, 'error': str(e),
                    })

            elif load_type == 'comfyui':
                chunk_name = load_info.get('chunk', '')
                workflow = (_build_comfyui_preload_workflow(chunk_name) if chunk_name
                            else _preload_node_workflow(load_info.get('node', '')))
                if not workflow:
                    yield _generate_sse_event('model_error', {
                        'model_id': mid, 'name': name,
                        'error': (f'chunk {chunk_name} not found' if chunk_name
                                  else f'nothing to preload for {mid}'),
                    })
                    continue

                # The preload runs a real workflow on the card, so it queues
                # behind whatever else is generating instead of landing on top
                # of it. The wait happens on a helper thread so the stream
                # stays audible — a byte-silent wait gets the stream closed by
                # the tunnel while the lease is still granted later, warming a
                # model for a dialog that no longer exists.
                import threading as _threading
                from my_app.services.gpu_lease_client import gpu_lease_sync, GpuBusyError
                # The handshake is locked: exactly ONE side ends up owning the
                # lease — the helper (dialog already dead when the grant lands)
                # or this generator (its finally below). Without the lock, a
                # grant landing in the instant the dialog dies leaked the lease
                # with a live heartbeat, which no reaper ever collects.
                _acq_lock = _threading.Lock()
                _acq = {"cm": None, "err": None, "abandoned": False}
                def _acquire_lease():
                    try:
                        # Named by the checkpoint it loads, not by the chunk.
                        # A name of its own matches nothing, so the preload can
                        # never be grouped with the runs it was made for, and
                        # the gate would afterwards believe a model called
                        # "preload-…" is on the card.
                        from my_app.services.comfyui_ws_client import _checkpoint_of
                        _preload_model = _checkpoint_of(workflow) or f"preload-{chunk_name}"
                        # "comfyui-load", not "comfyui": this holds the card
                        # to put weights on it, and its duration belongs with
                        # the other load measurements, not among the runs. As a
                        # run it dragged the run average toward "warming a
                        # model" — and ComfyUI, whose load happens inside the
                        # submitted workflow, had no load figure at all.
                        cm = gpu_lease_sync("comfyui-load", _preload_model, 0)
                        cm.__enter__()
                        with _acq_lock:
                            if _acq["abandoned"]:
                                give_back = True
                            else:
                                _acq["cm"] = cm
                                give_back = False
                        if give_back:
                            # Granted after the dialog died: straight back —
                            # but as a FAILED lease. A clean exit here recorded
                            # a queue-to-grant millisecond hold as a valid
                            # comfyui-load sample and armed the post-load
                            # reservation for a model that was never warmed.
                            _gone = RuntimeError("preload abandoned before grant")
                            cm.__exit__(RuntimeError, _gone, None)
                    except Exception as e:
                        _acq["err"] = e
                _acq_thread = _threading.Thread(target=_acquire_lease, daemon=True)
                _acq_thread.start()
                prompt_id = None
                success = False
                _cleaned = False
                try:
                    while _acq_thread.is_alive():
                        _acq_thread.join(timeout=2.0)
                        if _acq_thread.is_alive():
                            yield ': waiting\n\n'
                    if _acq["err"] is not None:
                        # One model that could not be warmed is a line in the
                        # list, not the end of the list.
                        yield _generate_sse_event('model_error', {
                            'model_id': mid, 'name': name, 'error': str(_acq["err"]),
                        })
                        continue
                    if _acq["cm"] is None:
                        yield _generate_sse_event('model_error', {
                            'model_id': mid, 'name': name,
                            'error': 'GPU lease not acquired',
                        })
                        continue
                    try:
                        prompt_id = comfyui.submit_workflow(workflow)
                    except Exception as _submit_err:
                        # ComfyUI's own words. "ComfyUI rejected workflow" told
                        # whoever was preloading nothing they did not already
                        # see; the name of the file it could not find does.
                        yield _generate_sse_event('model_error', {
                            'model_id': mid, 'name': name,
                            'error': str(_submit_err),
                        })
                        continue

                    # Poll history until complete (2s interval, 180s timeout)
                    poll_start = time.time()
                    while time.time() - poll_start < 180:
                        time.sleep(2)
                        # Keeps the stream audible, and makes a closed dialog
                        # noticeable here instead of after the full 180 s.
                        yield ': waiting\n\n'
                        history = comfyui.get_history(prompt_id)
                        if history and prompt_id in history:
                            entry = history[prompt_id]
                            status_info = entry.get("status", {})
                            if status_info.get("completed", False) or status_info.get("status_str") == "success":
                                success = True
                                break
                            if status_info.get("status_str") == "error":
                                yield _generate_sse_event('model_error', {
                                    'model_id': mid, 'name': name,
                                    'error': 'ComfyUI execution error',
                                })
                                break
                    if prompt_id and not success:
                        # Timeout/error with the dialog still open: stop the
                        # warmup and wait AUDIBLY for the card to empty — the
                        # silent variant in the finally is only for a stream
                        # that is already dead.
                        try:
                            import asyncio as _asyncio
                            from my_app.services.comfyui_ws_client import get_comfyui_ws_client
                            _asyncio.run(get_comfyui_ws_client().cancel_job(prompt_id))
                        except Exception as _e:
                            logger.warning(f"[WORKSHOP-PRELOAD] Warmup cancel failed: {_e}")
                        _drain_start = time.time()
                        while time.time() - _drain_start < 180:
                            try:
                                if (comfyui.get_queue_status() or {}).get('total', 0) == 0:
                                    break
                            except Exception:
                                break
                            yield ': waiting\n\n'
                            time.sleep(2)
                        _cleaned = True
                finally:
                    # Take ownership of the lease atomically; if the grant has
                    # not landed yet, the helper sees `abandoned` and gives it
                    # straight back itself.
                    with _acq_lock:
                        _acq["abandoned"] = True
                        _lease_cm = _acq["cm"]
                        _acq["cm"] = None
                    # The lease must not be handed back while ComfyUI is still
                    # rendering the warmup — the next participant would allocate
                    # on top of it. Stop the job first, then release.
                    if _lease_cm is not None and prompt_id and not success and not _cleaned:
                        try:
                            import asyncio as _asyncio
                            from my_app.services.comfyui_ws_client import get_comfyui_ws_client
                            _asyncio.run(get_comfyui_ws_client().cancel_job(prompt_id))
                            logger.info(f"[WORKSHOP-PRELOAD] Warmup job cancelled: {prompt_id}")
                        except Exception as _e:
                            logger.warning(f"[WORKSHOP-PRELOAD] Warmup cancel failed: {_e}")
                        # The interrupt is asynchronous, and a model-load node
                        # finishes before it takes effect. Hold the lease until
                        # the job has actually left the card — releasing earlier
                        # would let the next run allocate on top of the load.
                        # While this lease is held, the warmup is the only
                        # thing ComfyUI can be running — an empty queue means
                        # the card is really free. get_queue_status returns
                        # counts, and it returns zeros when ComfyUI is down.
                        _drain_start = time.time()
                        while time.time() - _drain_start < 180:
                            try:
                                if (comfyui.get_queue_status() or {}).get('total', 0) == 0:
                                    break
                            except Exception:
                                break
                            time.sleep(2)
                    if _lease_cm is not None:
                        try:
                            if success:
                                _lease_cm.__exit__(None, None, None)
                            else:
                                # A warmup that did not complete must not be
                                # released as a completed load: it would enter
                                # the load statistics with up to 360 s of
                                # poll-and-drain time and arm the post-load
                                # reservation for a model that never arrived.
                                _err = RuntimeError("preload did not complete")
                                _lease_cm.__exit__(RuntimeError, _err, None)
                        except Exception:
                            pass

                if success:
                    yield _generate_sse_event('model_complete', {
                        'model_id': mid, 'name': name,
                    })
                elif time.time() - poll_start >= 180:
                    yield _generate_sse_event('model_error', {
                        'model_id': mid, 'name': name,
                        'error': 'ComfyUI timeout (180s)',
                    })

        yield _generate_sse_event('done', {'total': len(model_ids)})

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response



@settings_bp.route('/workshop/clear-all', methods=['POST'])
def workshop_clear_all():
    """
    Clear ALL GPU memory: unload all GPU service models + free ComfyUI.
    """
    errors = []

    # 1. The GPU service is asked to unload nothing any more: the Diffusers
    #    station no longer since stage 4 of the move to ComfyUI (no surface
    #    loads it), HeartMuLa and Stable Audio no longer since stage 6 --
    #    both are ComfyUI's models now and go with its /free below.

    # 2. ComfyUI — interrupt + free, through the gate with the card held
    #    (services/gpu_gate.free_comfyui); a card held by a run answers busy.
    try:
        from my_app.services.gpu_gate import free_comfyui
        free_comfyui("workshop: clear all", interrupt=True, free_memory=True,
                     timeout=10, wait_s=60)
    except Exception as e:
        errors.append(f"ComfyUI: {e}")

    if errors:
        logger.warning(f"[WORKSHOP] Clear-all partial errors: {errors}")

    return jsonify({"success": len(errors) == 0, "errors": errors})


@settings_bp.route('/llm-models', methods=['GET'])
def get_llm_models():
    """
    Get list of available local LLM models for dropdown selection.

    No authentication required - just model list.
    Returns models with 'local/' prefix for direct use in settings.

    Response:
    {
        "success": true,
        "models": [
            {"id": "local/qwen3-vl:32b", "name": "qwen3-vl:32b", "size": "20 GB"},
            {"id": "local/qwen2.5vl:72b", "name": "qwen2.5vl:72b", "size": "48 GB"},
            ...
        ]
    }
    """
    try:
        # The installed local models, off the table (config/
        # local_llm_weights.json): the pickers carry no availability flag of
        # their own, so a registered but undownloaded alias stays out.
        from my_app.services import local_llm_weights

        models = []
        for name in local_llm_weights.installed_aliases():
            size_gb = (local_llm_weights.entry(name) or {}).get("size_gb")
            models.append({
                'id': f'local/{name}',
                'name': name,
                'size': f"{size_gb} GB" if size_gb else ''
            })

        # Sort by name
        models.sort(key=lambda x: x['name'])

        logger.info(f"[SETTINGS] Found {len(models)} local LLM models")
        return jsonify({
            "success": True,
            "models": models
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting LLM models: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "models": []
        }), 200



# ============================================================================
# API Usage & Billing
# ============================================================================

# The account behind each provider's key is read by
# services/provider_account.read_account, by the account API the provider's
# entry in config/llm_providers.json names. The availability check reads
# through the same function and keeps a reading of its own, made with the key
# the run uses (the environment variable first); this tab reads with the key
# file's key.


@settings_bp.route('/api-usage', methods=['GET'])
@require_settings_auth
def api_usage():
    """API usage: the account behind every provider key in a key file, local
    token tracking, the provider table and the model assignments.

    `accounts` holds one entry per provider whose key file holds a key, in
    the order of config/llm_providers.json: {"provider", "reading"}, where
    the reading is what provider_account.read_account gives, None for a
    provider whose entry names no account API. The API Management tab shows
    a block for each."""
    from my_app.services.usage_tracker import get_usage_tracker
    from concurrent.futures import ThreadPoolExecutor
    # Imported here, behind the settings login: tests/test_provider_account.py
    # holds where it may be used.
    from my_app.services.provider_account import read_account

    days = request.args.get('days', 30, type=int)
    date_from = request.args.get('from')  # ISO date string YYYY-MM-DD
    date_to = request.args.get('to')      # ISO date string YYYY-MM-DD

    # --- The accounts, read in parallel ---
    keys = {}
    for name in provider_names():
        if key_file_path(name) is None:
            continue
        key = key_in_file(name)
        if key:
            keys[name] = key
    readings = {}
    if keys:
        with ThreadPoolExecutor(max_workers=len(keys)) as pool:
            futures = {name: pool.submit(read_account, name, key) for name, key in keys.items()}
            readings = {name: future.result() for name, future in futures.items()}
    accounts = [{"provider": name, "reading": readings[name]} for name in keys]

    # --- Local usage tracking ---
    local_usage = get_usage_tracker().get_aggregated(days=days, date_from=date_from, date_to=date_to)

    # --- Provider key status + credits ---
    # What is recorded about a provider's data path comes from the register
    # (hardware_matrix.json), never from a flag written here: an admin can change
    # the register, and a hardcoded boolean would then contradict it. It also
    # cannot say "nothing recorded", which is a state of its own -- see
    # _recorded_conformity. The region was a second hand-kept claim and is gone.
    providers = {}
    for name in provider_names():
        if key_file_path(name) is None:
            continue
        # Balance only. What the key has spent is a usage figure and is shown
        # in the provider's account block, not in the credits column.
        reading = readings.get(name)
        providers[name] = {
            "key_configured": name in keys,
            "dsgvo_recorded": _recorded_conformity(name),
            "credits": (
                {"remaining": reading["remaining"]}
                if reading and not reading.get("error")
                and reading.get("remaining") is not None else None),
        }

    # --- Active provider + model assignments ---
    settings = {}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                settings = json.load(f)
        except Exception:
            pass

    active_provider = settings.get("EXTERNAL_LLM_PROVIDER", "none")

    # Field names, not labels. Until 2026-08-17 this dict carried English role
    # names of its own, which the German page then displayed verbatim -- a fifth
    # set of names for the same ten roles. Their order did not survive either:
    # Flask sorts JSON object keys, so the surface received them alphabetically.
    # The names and the order live once, in src/data/modelRoles.ts.
    model_role_fields = (
        "CHAT_HELPER_MODEL",
        "RESONA_MODEL",
        "PERSONA_MODEL",
        "STAGE1_TEXT_MODEL",
        "STAGE2_INTERCEPTION_MODEL",
        "STAGE2_OPTIMIZATION_MODEL",
        "STAGE3_MODEL",
        "IMAGE_ANALYSIS_MODEL",
        "CODING_MODEL",
        "KNOWLEDGE_PROCESSING_MODEL",
    )
    model_assignments = {}
    for key in model_role_fields:
        val = settings.get(key, "") or getattr(config, key, "")
        if val:
            model_assignments[key] = val

    return jsonify({
        "accounts": accounts,
        "local_usage": local_usage,
        "providers": providers,
        "active_provider": active_provider,
        "model_assignments": model_assignments,
    })


@settings_bp.route('/frontier-image-accounts', methods=['GET'])
@require_settings_auth
def frontier_image_accounts():
    """The external frontier image models and the accounts they run on, for
    the rows under the key fields in the API table: every output
    config whose meta marks it `frontier_image`, with its name, the provider
    its chunk sends to, whether a key is present there, and the account's
    balance, read afresh because the operator is looking at it, where the
    check judges the provider's account (`judged`). Which model
    and which provider stand in the rows comes from the configs and their
    chunks, not from here.
    Where the balance could not be read, `error` names why: the HTTP status,
    with the proxy's name for the refusal where it gives one, "timeout", the
    class of an exception, or an English sentence of
    provider_account.read_account or of its LiteLLM reader (no address in
    the provider table, no account in the answer); for a config whose chunk
    names no provider, that. `used_up` names the first of the three budgets that binds
    the key and is used up ('account', 'key', 'team', in that order), where
    one is. The reading is stored as well, and the availability check acts on
    it for five minutes while the key stays the same
    (services/provider_account.py): it takes the config off the Flow and the
    model choice of five instruments where there is no key, the provider
    refuses the key, or a budget that binds the key is used up."""
    from my_app.services import provider_account
    from my_app.services.model_availability_service import ModelAvailabilityService
    service = ModelAvailabilityService()
    configs, states = [], {}
    for path in sorted(service.config_dir.glob("*.json")):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"[SETTINGS] {path.name} not read: {e}")
            continue
        if not isinstance(data, dict) or (data.get("meta") or {}).get("frontier_image") is not True:
            continue
        name = service.api_provider(path.stem)
        if not name:
            configs.append({"config_id": path.stem, "name": data.get("name"), "provider": None,
                            "has_key": None, "judged": False, "balance": None, "used_up": None,
                            "error": f"{path.stem} names no provider"})
            continue
        if name not in states:
            states[name] = provider_account.account(name, fresh=True)
        state = states[name]
        configs.append({
            "config_id": path.stem,
            "name": data.get("name"),
            "provider": name,
            "has_key": state["has_key"],
            "judged": state["judged"],
            "balance": state["balance"],
            "used_up": state["used_up"],
            "error": state["error"],
        })
    return jsonify({"configs": configs})


# ============================================================================
# MODEL CAPABILITIES — what a model can actually be handed
# ============================================================================
# Whether a model takes an image, or reaches for a tool, used to be guessed from its
# provider prefix. The guess was wrong for mammouth/glm-5.2 (CHAT_HELPER_MODEL), whose
# refusal is a final 404 rather than a retriable error -- so every image turn died
# with a 500. These endpoints let the operator measure it instead, in the model table,
# with probes the platform builds itself. The verdict is written down; the request
# path only ever reads it. See my_app/services/model_capabilities.


@settings_bp.route('/model-capabilities', methods=['GET'])
@require_settings_auth
def get_model_capabilities():
    """Per role: what it needs, and what is known about every model that can hold it."""
    from my_app.services.model_capabilities import role_overview, CAPABILITIES
    try:
        return jsonify({"roles": role_overview(), "capabilities": list(CAPABILITIES)}), 200
    except Exception as e:
        logger.error(f"[CAPABILITIES] listing failed: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/model-capabilities/check', methods=['POST'])
@require_settings_auth
def check_model_capability():
    """Measure a capability.

    {"model": "...", "capability": "image"} measures one string the operator typed --
    which need not be saved yet, because the verdict is a fact about the model either
    way. {"role": "CHAT_HELPER_MODEL"} measures the model that role is set to, and
    quietly measures the others its request path can currently be routed to as well --
    they are handed the same image and the same tool definitions, so they have to be
    measured, but they belong to no row and are named in none.
    """
    from my_app.services.model_capabilities import (
        probe, role_overview, reachable_models, get_recorded, CAPABILITIES)
    try:
        data = request.get_json(silent=True) or {}
        capability = (data.get("capability") or "image").strip()
        if capability not in CAPABILITIES:
            return jsonify({"error": f"unknown capability: {capability}"}), 400

        model = (data.get("model") or "").strip()
        role = (data.get("role") or "").strip()
        if model:
            targets = [model]
        elif role:
            entry = role_overview().get(role)
            if not entry:
                return jsonify({"error": f"unknown role: {role}"}), 400
            if not entry["model"]:
                return jsonify({"error": f"no model configured for {role}"}), 400
            targets = [entry["model"]]
        else:
            return jsonify({"error": "No model or role given"}), 400

        results = [probe(m, capability) for m in targets]

        # The rest of what this role can reach, measured but not reported: an unmeasured
        # model is never handed an image, so leaving them out would quietly downgrade
        # every route but the first. Only the ones nothing is known about yet, so
        # pressing the button twice does not spend the same calls again.
        if role:
            for other in reachable_models(role, targets[0]):
                if other == targets[0] or get_recorded(other, capability) is not None:
                    continue
                try:
                    outcome = probe(other, capability)
                    logger.info("[CAPABILITIES] also measured %s for %s: %s",
                                capability, other, outcome["verdict"])
                except Exception as e:
                    logger.warning("[CAPABILITIES] could not measure %s for %s: %s",
                                   capability, other, e)

        logger.info("[CAPABILITIES] checked %s for %d model(s): %s", capability, len(results),
                    ", ".join(f"{r['model']}={r['verdict']}" for r in results))
        return jsonify({"results": results}), 200
    except Exception as e:
        logger.error(f"[CAPABILITIES] check failed: {e}")
        return jsonify({"error": str(e)}), 500


