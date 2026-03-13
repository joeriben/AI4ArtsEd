"""
Settings API Routes
Configuration management for AI4ArtsEd DevServer
"""
from flask import Blueprint, jsonify, request, session
from functools import wraps
import json
import logging
from pathlib import Path
from datetime import datetime, date
import secrets
import string
from werkzeug.security import generate_password_hash, check_password_hash
import config
import os
import subprocess
import requests
import sys
import threading
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
    """Save hardware matrix to JSON file"""
    try:
        with open(MATRIX_FILE, 'w') as f:
            json.dump(matrix_data, f, indent=2)
        return True, "Matrix saved successfully"
    except Exception as e:
        logger.error(f"[SETTINGS] Failed to save hardware matrix: {e}")
        return False, str(e)

# Path to API key files
OPENROUTER_KEY_FILE = Path(__file__).parent.parent.parent / "openrouter.key"
ANTHROPIC_KEY_FILE = Path(__file__).parent.parent.parent / "anthropic.key"
OPENAI_KEY_FILE = Path(__file__).parent.parent.parent / "openai.key"
MISTRAL_KEY_FILE = Path(__file__).parent.parent.parent / "mistral.key"
IONOS_KEY_FILE = Path(__file__).parent.parent.parent / "ionos.key"
MAMMOUTH_KEY_FILE = Path(__file__).parent.parent.parent / "mammouth.key"

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

def generate_strong_password(length=24):
    """Generate a cryptographically secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


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
        provider: "local", "mistral", "anthropic", "openai", "openrouter"
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
    remote_addr = request.remote_addr
    host = request.host.split(':')[0]  # Remove port
    return remote_addr in ('127.0.0.1', '::1') or host in ('localhost', '127.0.0.1')


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


@settings_bp.route('/logout', methods=['POST'])
def logout():
    """Clear settings authentication"""
    session.pop('settings_authenticated', None)
    logger.info("[SETTINGS] User logged out")
    return jsonify({"success": True}), 200


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
    """Public endpoint: returns current safety level for frontend feature gating."""
    return jsonify({'safety_level': config.DEFAULT_SAFETY_LEVEL})


@settings_bp.route('/ui-mode', methods=['GET'])
def get_ui_mode():
    """Public endpoint: returns current UI mode for frontend adaptation."""
    return jsonify({'ui_mode': config.UI_MODE})


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
    """Proxy generation step progress from GPU service."""
    try:
        resp = requests.get(f"{config.GPU_SERVICE_URL}/api/diffusers/progress", timeout=2)
        if resp.ok:
            return jsonify(resp.json())
    except Exception:
        pass
    return jsonify({"step": 0, "total_steps": 0, "active": False})


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


@settings_bp.route('/change-password', methods=['POST'])
@require_settings_auth
def change_password():
    """Change admin password (requires current password)"""
    try:
        data = request.get_json()
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')

        # Validation
        if not current_password or not new_password:
            return jsonify({"error": "Both current and new password required"}), 400

        if len(new_password) < 12:
            return jsonify({"error": "New password must be at least 12 characters"}), 400

        # Verify current password
        if not SETTINGS_PASSWORD_FILE.exists():
            return jsonify({"error": "Password file not found"}), 500

        current_hash = SETTINGS_PASSWORD_FILE.read_text().strip()
        if not check_password_hash(current_hash, current_password):
            logger.warning("[SETTINGS] Password change failed - incorrect current password")
            return jsonify({"error": "Current password is incorrect"}), 403

        # Generate and store new password hash
        new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        SETTINGS_PASSWORD_FILE.write_text(new_hash)
        SETTINGS_PASSWORD_FILE.chmod(0o600)

        logger.info("[SETTINGS] Password changed successfully")
        return jsonify({"success": True, "message": "Password changed successfully"}), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Password change error: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/', methods=['GET'])
@require_settings_auth
def get_settings():
    """Get current configuration and hardware matrix"""
    try:
        # Collect all current config values
        current = {
            # General Settings
            "UI_MODE": config.UI_MODE,
            "DEFAULT_SAFETY_LEVEL": config.DEFAULT_SAFETY_LEVEL,
            "DEFAULT_LANGUAGE": config.DEFAULT_LANGUAGE,

            # Model Configuration
            "STAGE1_TEXT_MODEL": config.STAGE1_TEXT_MODEL,
            "STAGE1_VISION_MODEL": config.STAGE1_VISION_MODEL,
            "STAGE2_INTERCEPTION_MODEL": config.STAGE2_INTERCEPTION_MODEL,
            "STAGE2_OPTIMIZATION_MODEL": config.STAGE2_OPTIMIZATION_MODEL,
            "STAGE3_MODEL": config.STAGE3_MODEL,
            "STAGE4_LEGACY_MODEL": config.STAGE4_LEGACY_MODEL,
            "CHAT_HELPER_MODEL": config.CHAT_HELPER_MODEL,
            "IMAGE_ANALYSIS_MODEL": config.IMAGE_ANALYSIS_MODEL,
            "CODING_MODEL": config.CODING_MODEL,
            "SAFETY_MODEL": config.SAFETY_MODEL,
            "DSGVO_VERIFY_MODEL": config.DSGVO_VERIFY_MODEL,
            "VLM_SAFETY_MODEL": config.VLM_SAFETY_MODEL,

            # API Configuration
            "LLM_PROVIDER": config.LLM_PROVIDER,
            "OLLAMA_API_BASE_URL": config.OLLAMA_API_BASE_URL,
            "LMSTUDIO_API_BASE_URL": config.LMSTUDIO_API_BASE_URL,
            "EXTERNAL_LLM_PROVIDER": config.EXTERNAL_LLM_PROVIDER,
            "DSGVO_CONFORMITY": config.DSGVO_CONFORMITY,
        }

        return jsonify({
            "current": current,
            "matrix": get_hardware_matrix()
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

        # Extract API Keys if present (saved separately for security)
        openrouter_key = data.pop('OPENROUTER_API_KEY', None)
        if openrouter_key:
            OPENROUTER_KEY_FILE.parent.mkdir(exist_ok=True)
            with open(OPENROUTER_KEY_FILE, 'w') as f:
                f.write(openrouter_key.strip())
            logger.info("[SETTINGS] OpenRouter API Key updated")

        anthropic_key = data.pop('ANTHROPIC_API_KEY', None)
        if anthropic_key:
            ANTHROPIC_KEY_FILE.parent.mkdir(exist_ok=True)
            with open(ANTHROPIC_KEY_FILE, 'w') as f:
                f.write(anthropic_key.strip())
            logger.info("[SETTINGS] Anthropic API Key updated")

        openai_key = data.pop('OPENAI_API_KEY', None)
        if openai_key:
            OPENAI_KEY_FILE.parent.mkdir(exist_ok=True)
            with open(OPENAI_KEY_FILE, 'w') as f:
                f.write(openai_key.strip())
            logger.info("[SETTINGS] OpenAI API Key updated")

        mistral_key = data.pop('MISTRAL_API_KEY', None)
        if mistral_key:
            MISTRAL_KEY_FILE.parent.mkdir(exist_ok=True)
            with open(MISTRAL_KEY_FILE, 'w') as f:
                f.write(mistral_key.strip())
            logger.info("[SETTINGS] Mistral API Key updated")

        ionos_key = data.pop('IONOS_API_KEY', None)
        if ionos_key:
            IONOS_KEY_FILE.parent.mkdir(exist_ok=True)
            with open(IONOS_KEY_FILE, 'w') as f:
                f.write(ionos_key.strip())
            logger.info("[SETTINGS] IONOS API Key updated")

        mammouth_key = data.pop('MAMMOUTH_API_KEY', None)
        if mammouth_key:
            MAMMOUTH_KEY_FILE.parent.mkdir(exist_ok=True)
            with open(MAMMOUTH_KEY_FILE, 'w') as f:
                f.write(mammouth_key.strip())
            logger.info("[SETTINGS] Mammouth API Key updated")

        # Write all other settings to user_settings.json
        SETTINGS_FILE.parent.mkdir(exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"[SETTINGS] Saved {len(data)} settings to {SETTINGS_FILE.name}")

        return jsonify({
            "success": True,
            "message": "Configuration saved. Backend restart required to apply changes."
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error saving config: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/openrouter-key', methods=['GET'])
@require_settings_auth
def get_openrouter_key():
    """Get masked OpenRouter API Key for display"""
    try:
        if not OPENROUTER_KEY_FILE.exists():
            return jsonify({"exists": False}), 200

        with open(OPENROUTER_KEY_FILE) as f:
            key = f.read().strip()

        # Return masked version (show only first 7 and last 4 chars)
        if len(key) > 11:
            masked = f"{key[:7]}...{key[-4:]}"
        else:
            masked = "***"

        return jsonify({
            "exists": True,
            "masked": masked
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error reading OpenRouter key: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/anthropic-key', methods=['GET'])
@require_settings_auth
def get_anthropic_key():
    """Get masked Anthropic API Key for display"""
    try:
        if not ANTHROPIC_KEY_FILE.exists():
            return jsonify({"exists": False}), 200

        with open(ANTHROPIC_KEY_FILE) as f:
            key = f.read().strip()

        # Return masked version (show only first 7 and last 4 chars)
        if len(key) > 11:
            masked = f"{key[:7]}...{key[-4:]}"
        else:
            masked = "***"

        return jsonify({
            "exists": True,
            "masked": masked
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error reading Anthropic key: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/openai-key', methods=['GET'])
@require_settings_auth
def get_openai_key():
    """Get masked OpenAI API Key for display"""
    try:
        if not OPENAI_KEY_FILE.exists():
            return jsonify({"exists": False}), 200

        with open(OPENAI_KEY_FILE) as f:
            key = f.read().strip()

        # Return masked version (show only first 7 and last 4 chars)
        if len(key) > 11:
            masked = f"{key[:7]}...{key[-4:]}"
        else:
            masked = "***"

        return jsonify({
            "exists": True,
            "masked": masked
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error reading OpenAI key: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/mistral-key', methods=['GET'])
@require_settings_auth
def get_mistral_key():
    """Get masked Mistral API Key for display"""
    try:
        if not MISTRAL_KEY_FILE.exists():
            return jsonify({"exists": False}), 200

        with open(MISTRAL_KEY_FILE) as f:
            key = f.read().strip()

        # Return masked version (show only first 7 and last 4 chars)
        if len(key) > 11:
            masked = f"{key[:7]}...{key[-4:]}"
        else:
            masked = "***"

        return jsonify({
            "exists": True,
            "masked": masked
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error reading Mistral key: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/ionos-key', methods=['GET'])
@require_settings_auth
def get_ionos_key():
    """Get masked IONOS API Key (JWT Token) for display"""
    try:
        if not IONOS_KEY_FILE.exists():
            return jsonify({"exists": False}), 200

        with open(IONOS_KEY_FILE) as f:
            # Skip comment lines
            key = ""
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    key = line
                    break

        if not key:
            return jsonify({"exists": False}), 200

        # Return masked version (show only first 7 and last 4 chars)
        if len(key) > 11:
            masked = f"{key[:7]}...{key[-4:]}"
        else:
            masked = "***"

        return jsonify({
            "exists": True,
            "masked": masked
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error reading IONOS key: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/mammouth-key', methods=['GET'])
@require_settings_auth
def get_mammouth_key():
    """Get masked Mammouth API Key for display"""
    try:
        if not MAMMOUTH_KEY_FILE.exists():
            return jsonify({"exists": False}), 200

        with open(MAMMOUTH_KEY_FILE) as f:
            # Skip comment lines
            key = ""
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    key = line
                    break

        if not key:
            return jsonify({"exists": False}), 200

        # Return masked version (show only first 7 and last 4 chars)
        if len(key) > 11:
            masked = f"{key[:7]}...{key[-4:]}"
        else:
            masked = "***"

        return jsonify({
            "exists": True,
            "masked": masked
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error reading Mammouth key: {e}")
        return jsonify({"error": str(e)}), 500


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
        exports_path = Path(__file__).parent.parent.parent.parent / "exports" / "json"

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
        sort_field = request.args.get('sort', 'timestamp')
        sort_order = request.args.get('order', 'desc')

        # Path to exports/json
        exports_path = Path(__file__).parent.parent.parent.parent / "exports" / "json"

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

                # Read config_used.json for pipeline and output info
                config_used_file = session_dir / "01_config_used.json"
                stage2_pipeline = None
                output_mode = None
                has_input_image = False

                # Check for input image in entities
                for entity in metadata.get('entities', []):
                    if entity.get('type') == 'input_image':
                        has_input_image = True
                        break

                if config_used_file.exists():
                    try:
                        with open(config_used_file) as f:
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

                # Count media files and find first media for thumbnail
                media_count = 0
                thumbnail_path = None
                thumbnail_type = None
                for entity in metadata.get('entities', []):
                    entity_type = entity.get('type', '')
                    if entity_type.startswith('output_'):
                        media_count += 1
                        # Find first media (image or video) for thumbnail
                        if thumbnail_path is None:
                            filename = entity.get('filename')
                            if filename:
                                # Check if file is in final/ subdirectory (new structure) or direct (old structure)
                                file_path_final = session_dir / "final" / filename
                                if file_path_final.exists():
                                    file_subpath = f"final/{filename}"
                                else:
                                    file_subpath = filename

                                if entity_type == 'output_image':
                                    thumbnail_path = f"/exports/json/{metadata_info.relative_path}/{file_subpath}"
                                    thumbnail_type = 'image'
                                elif entity_type == 'output_video':
                                    thumbnail_path = f"/exports/json/{metadata_info.relative_path}/{file_subpath}"
                                    thumbnail_type = 'video'

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
                    'thumbnail_type': thumbnail_type
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

        return jsonify({
            "sessions": paginated_sessions,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "filters": {
                "devices": unique_devices,
                "configs": unique_configs,
                "safety_levels": unique_safety_levels
            }
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting sessions: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/sessions/<run_id>', methods=['GET'])
@require_settings_auth
def get_session_detail(run_id):
    """Get detailed information for a specific session"""
    try:
        exports_path = Path(__file__).parent.parent.parent.parent / "exports" / "json"

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
            entity_copy = entity.copy()
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


@settings_bp.route('/restart-backend', methods=['POST'])
@require_settings_auth
def restart_backend():
    """Restart backend server using appropriate start script based on context"""
    try:
        # Get current directory to determine context (development vs production)
        current_dir = Path(__file__).resolve().parent.parent.parent.parent
        current_path_str = str(current_dir)

        # Determine which script to use
        if "develop" in current_path_str.lower():
            script_name = "3_start_backend_dev.sh"
            context = "development"
        elif "production" in current_path_str.lower():
            script_name = "5_start_backend_prod.sh"
            context = "production"
        else:
            return jsonify({
                "error": "Cannot determine context (development/production) from path",
                "path": current_path_str
            }), 400

        script_path = current_dir / script_name

        # Verify script exists
        if not script_path.exists():
            return jsonify({
                "error": f"Start script not found: {script_name}",
                "path": str(script_path)
            }), 404

        logger.info(f"[SETTINGS] Backend restart requested ({context})")
        logger.info(f"[SETTINGS] Will execute: {script_path}")

        # Function to execute restart after delay (allows response to be sent)
        def delayed_restart():
            import time
            time.sleep(1)  # Wait 1 second for response to be sent
            try:
                logger.info(f"[SETTINGS] Executing restart script: {script_path}")

                # Try to open in a new terminal window for visibility
                terminal_commands = [
                    ['ptyxis', '--', 'bash', str(script_path)],  # Fedora 42 default
                    ['gnome-terminal', '--', 'bash', str(script_path)],
                    ['xterm', '-e', 'bash', str(script_path)],
                    ['konsole', '-e', 'bash', str(script_path)],
                ]

                terminal_opened = False
                for cmd in terminal_commands:
                    try:
                        subprocess.Popen(cmd, cwd=str(current_dir))
                        terminal_opened = True
                        logger.info(f"[SETTINGS] Opened restart script in terminal: {cmd[0]}")
                        break
                    except FileNotFoundError:
                        continue

                # Fallback: Execute directly if no terminal found
                if not terminal_opened:
                    logger.warning("[SETTINGS] No terminal emulator found, executing directly")
                    subprocess.Popen(
                        ['bash', str(script_path)],
                        cwd=str(current_dir),
                        start_new_session=True
                    )

            except Exception as e:
                logger.error(f"[SETTINGS] Error executing restart script: {e}")

        # Start restart in background thread
        restart_thread = threading.Thread(target=delayed_restart, daemon=True)
        restart_thread.start()

        return jsonify({
            "success": True,
            "message": f"Backend restart initiated ({context})",
            "script": script_name,
            "note": "Backend will restart in 1 second. Please wait for reconnection."
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error in restart_backend: {e}")
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


@settings_bp.route('/preset/<provider>', methods=['GET'])
@require_settings_auth
def get_preset_for_provider(provider):
    """
    Get merged preset for a provider, using detected VRAM for vision models.

    The preset merges:
    - LLM models from the specified provider
    - Vision models from the detected VRAM tier (always local)

    Args:
        provider: "local", "mistral", "anthropic", "openai", "openrouter"

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
                "STAGE1_VISION_MODEL": "local/qwen3-vl:32b",
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

        # Validate provider
        valid_providers = ['local', 'none', 'mistral', 'ionos', 'mammouth', 'anthropic', 'openai', 'openrouter']
        if provider not in valid_providers:
            return jsonify({"error": f"Invalid provider: {provider}"}), 400

        # Get merged preset
        preset = get_merged_preset(provider, vram_tier)
        preset['vram_tier'] = vram_tier

        return jsonify(preset), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error getting preset for {provider}: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/apply-preset', methods=['POST'])
@require_settings_auth
def apply_preset():
    """Apply a provider preset to runtime config AND persist to user_settings.json.

    Solves the sync bug where UI preset switches updated runtime config
    but were lost on restart because user_settings.json was never written.
    """
    try:
        data = request.get_json()
        if not data or 'provider' not in data:
            return jsonify({"error": "Request must contain 'provider'"}), 400

        provider = data['provider']
        vram_tier = data.get('vram_tier')

        if not vram_tier:
            gpu_info = detect_gpu_vram()
            vram_tier = gpu_info.get('vram_tier', 'vram_16')

        # Get merged preset
        preset = get_merged_preset(provider, vram_tier)
        models = preset.get('models', {})

        # 1. Apply to runtime config
        applied = []
        for key, value in models.items():
            if hasattr(config, key):
                setattr(config, key, value)
                applied.append(key)

        # Also apply provider-level settings
        if preset.get('EXTERNAL_LLM_PROVIDER'):
            config.EXTERNAL_LLM_PROVIDER = preset['EXTERNAL_LLM_PROVIDER']
            applied.append('EXTERNAL_LLM_PROVIDER')
        if 'DSGVO_CONFORMITY' in preset:
            config.DSGVO_CONFORMITY = preset['DSGVO_CONFORMITY']
            applied.append('DSGVO_CONFORMITY')

        # 2. Persist to user_settings.json
        settings = {}
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE) as f:
                settings = json.load(f)

        settings.update(models)
        if preset.get('EXTERNAL_LLM_PROVIDER'):
            settings['EXTERNAL_LLM_PROVIDER'] = preset['EXTERNAL_LLM_PROVIDER']
        if 'DSGVO_CONFORMITY' in preset:
            settings['DSGVO_CONFORMITY'] = preset['DSGVO_CONFORMITY']

        SETTINGS_FILE.parent.mkdir(exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)

        logger.info(
            f"[SETTINGS] Preset '{provider}' applied ({len(applied)} settings) "
            f"and persisted to {SETTINGS_FILE.name}"
        )
        return jsonify({
            "success": True,
            "provider": provider,
            "vram_tier": vram_tier,
            "applied": applied,
        }), 200

    except Exception as e:
        logger.error(f"[SETTINGS] Error applying preset: {e}")
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
            "message": "Settings applied successfully"
        }), 200
    except Exception as e:
        logger.error(f"[SETTINGS] Error reloading settings: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/backend-status', methods=['GET'])
def get_backend_status():
    """
    Aggregated backend status for the dashboard tab.

    Returns status of all backends: GPU Service sub-backends, ComfyUI, Ollama,
    cloud API key status, GPU hardware, and output configs grouped by backend_type.

    Query parameters:
        force_refresh: Bypass all caches (default: false)
    """
    from concurrent.futures import ThreadPoolExecutor
    import asyncio

    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

    # --- GPU Hardware ---
    gpu_hardware = detect_gpu_vram()

    # --- GPU Service (port 17803) ---
    gpu_service = {"reachable": False, "url": config.GPU_SERVICE_URL, "sub_backends": {}, "gpu_info": None}

    # Check GPU service health + all sub-backend availability in parallel
    def _check_gpu_health():
        try:
            resp = requests.get(f"{config.GPU_SERVICE_URL}/api/health", timeout=5)
            if resp.ok:
                return resp.json()
        except Exception:
            pass
        return None

    def _check_sub_backend(name, path):
        try:
            resp = requests.get(f"{config.GPU_SERVICE_URL}{path}", timeout=3)
            if resp.ok:
                return name, resp.json()
        except Exception:
            pass
        return name, {"available": False}

    def _check_text_models():
        """Text backend has no /available endpoint — check via /api/text/models."""
        try:
            resp = requests.get(f"{config.GPU_SERVICE_URL}/api/text/models", timeout=3)
            if resp.ok:
                data = resp.json()
                presets = data.get("presets", {})
                model_names = list(presets.keys()) if presets else []
                return "text", {"available": True, "models": model_names}
        except Exception:
            pass
        return "text", {"available": False, "models": []}

    sub_backend_checks = [
        ("diffusers", "/api/diffusers/available"),
        ("heartmula", "/api/heartmula/available"),
        ("stable_audio", "/api/stable_audio/available"),
        ("cross_aesthetic", "/api/cross_aesthetic/available"),
        ("mmaudio", "/api/cross_aesthetic/mmaudio/available"),
    ]

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        futures["health"] = executor.submit(_check_gpu_health)
        for name, path in sub_backend_checks:
            futures[name] = executor.submit(_check_sub_backend, name, path)
        futures["text"] = executor.submit(_check_text_models)

        # Collect results (10s timeout prevents hanging)
        try:
            health_data = futures["health"].result(timeout=10)
        except Exception:
            health_data = None
        if health_data:
            gpu_service["reachable"] = True
            gpu_service["gpu_info"] = health_data.get("gpu")
            gpu_service["vram_coordinator"] = health_data.get("vram_coordinator")

        for name, _path in sub_backend_checks:
            try:
                result_name, result_data = futures[name].result(timeout=10)
            except Exception:
                result_name, result_data = name, {"available": False}
            gpu_service["sub_backends"][result_name] = result_data

        try:
            text_name, text_data = futures["text"].result(timeout=10)
        except Exception:
            text_name, text_data = "text", {"available": False, "models": []}
        gpu_service["sub_backends"]["text"] = text_data

    # --- ComfyUI + Config Availability (single event loop) ---
    comfyui_status = {"reachable": False, "url": f"http://127.0.0.1:{config.COMFYUI_PORT}", "models": {}}
    config_availability = {}
    try:
        from my_app.services.model_availability_service import ModelAvailabilityService
        service = ModelAvailabilityService()
        loop = asyncio.new_event_loop()
        try:
            if force_refresh:
                service.invalidate_caches()

            # ComfyUI check — failure must NOT prevent config availability check
            try:
                models = loop.run_until_complete(service.get_comfyui_models(force_refresh=force_refresh))
                if models:
                    comfyui_status["reachable"] = True
                    comfyui_status["models"] = models
            except Exception as e:
                logger.info(f"[BACKEND-STATUS] ComfyUI unreachable (non-critical): {e}")

            config_availability = loop.run_until_complete(service.check_all_configs())
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"[BACKEND-STATUS] Availability service check failed: {e}")

    # --- Ollama ---
    ollama_status = {"reachable": False, "url": config.OLLAMA_API_BASE_URL, "models": []}
    try:
        resp = requests.get(f"{config.OLLAMA_API_BASE_URL}/api/tags", timeout=5)
        if resp.ok:
            ollama_status["reachable"] = True
            ollama_models = resp.json().get("models", [])
            for model in ollama_models:
                name = model.get("name", "")
                size_bytes = model.get("size", 0)
                size_gb = size_bytes / (1024 ** 3)
                size_str = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{size_bytes / (1024 ** 2):.0f} MB"
                ollama_status["models"].append({"name": name, "size": size_str})
            ollama_status["models"].sort(key=lambda x: x["name"])
    except Exception as e:
        logger.warning(f"[BACKEND-STATUS] Ollama check failed: {e}")

    # --- Cloud APIs ---
    aws_env_script = Path(__file__).parent.parent.parent / "setup_aws_env.sh"
    cloud_apis = {
        "openrouter":  {"key_configured": OPENROUTER_KEY_FILE.exists(), "dsgvo_compliant": False, "region": "US"},
        "openai":      {"key_configured": OPENAI_KEY_FILE.exists(),     "dsgvo_compliant": False, "region": "US"},
        "anthropic":   {"key_configured": ANTHROPIC_KEY_FILE.exists(),  "dsgvo_compliant": False, "region": "US"},
        "mistral":     {"key_configured": MISTRAL_KEY_FILE.exists(),    "dsgvo_compliant": True,  "region": "EU"},
        "ionos":       {"key_configured": IONOS_KEY_FILE.exists(),      "dsgvo_compliant": True,  "region": "EU"},
        "mammouth":    {"key_configured": MAMMOUTH_KEY_FILE.exists(),   "dsgvo_compliant": True,  "region": "EU"},
        "aws_bedrock": {"key_configured": aws_env_script.exists(),      "dsgvo_compliant": True,  "region": "EU"},
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
                hidden = cfg.get("display", {}).get("hidden", False)
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
            "ollama": ollama_status,
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


@settings_bp.route('/ollama-models', methods=['GET'])
def get_ollama_models():
    """
    Get list of available Ollama models for dropdown selection.

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
        # Get Ollama URL from config or user settings
        ollama_url = config.OLLAMA_API_BASE_URL

        # Call Ollama API to list models
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)

        if response.status_code != 200:
            logger.warning(f"[SETTINGS] Ollama API returned {response.status_code}")
            return jsonify({
                "success": False,
                "error": f"Ollama API error: {response.status_code}",
                "models": []
            }), 200

        data = response.json()
        ollama_models = data.get('models', [])

        # Format models for frontend dropdown
        models = []
        for model in ollama_models:
            name = model.get('name', '')
            size_bytes = model.get('size', 0)

            # Convert size to human-readable format
            size_gb = size_bytes / (1024 ** 3)
            if size_gb >= 1:
                size_str = f"{size_gb:.0f} GB"
            else:
                size_mb = size_bytes / (1024 ** 2)
                size_str = f"{size_mb:.0f} MB"

            models.append({
                'id': f'local/{name}',
                'name': name,
                'size': size_str
            })

        # Sort by name
        models.sort(key=lambda x: x['name'])

        logger.info(f"[SETTINGS] Found {len(models)} Ollama models")
        return jsonify({
            "success": True,
            "models": models
        }), 200

    except requests.exceptions.ConnectionError:
        logger.warning("[SETTINGS] Cannot connect to Ollama")
        return jsonify({
            "success": False,
            "error": "Ollama not running",
            "models": []
        }), 200
    except Exception as e:
        logger.error(f"[SETTINGS] Error getting Ollama models: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "models": []
        }), 200
