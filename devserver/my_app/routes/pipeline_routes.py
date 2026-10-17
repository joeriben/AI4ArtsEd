"""
Pipeline Routes - Live Pipeline Recorder API Endpoints

These endpoints provide real-time access to pipeline execution data:
- Status polling for frontend progress display
- Entity file serving (text, JSON, images)
"""
from flask import Blueprint, send_file, jsonify
import logging
from pathlib import Path

from my_app.services.pipeline_recorder import load_recorder, SafetyRefusal

logger = logging.getLogger(__name__)

# Blueprint definition
pipeline_bp = Blueprint('pipeline', __name__, url_prefix='/api/pipeline')

# Base path for pipeline_runs directory (/exports/json/)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import JSON_STORAGE_DIR
PIPELINE_BASE_PATH = JSON_STORAGE_DIR


@pipeline_bp.route('/<run_id>/status', methods=['GET'])
def get_pipeline_status(run_id: str):
    """
    Get current pipeline status for frontend polling

    Returns the complete metadata.json including:
    - current_state: {stage, step, progress}
    - entities: array of completed entities
    - expected_outputs: what entities should appear

    Args:
        run_id: UUID of the pipeline run

    Returns:
        JSON with pipeline status or 404 error

    Example Response:
        {
            "run_id": "528e5af9-59b3-4551-b101-27e13dd6e43e",
            "timestamp": "2025-11-04T20:12:37.568803",
            "config_name": "stillepost",
            "safety_level": "kids",
            "user_id": "anonymous",
            "expected_outputs": ["input", "translation", "safety", "interception", ...],
            "current_state": {
                "stage": 2,
                "step": "interception",
                "progress": "4/6"
            },
            "entities": [
                {
                    "sequence": 1,
                    "type": "input",
                    "filename": "01_input.txt",
                    "timestamp": "2025-11-04T20:12:37.569096",
                    "metadata": {}
                },
                ...
            ]
        }
    """
    try:
        recorder = load_recorder(run_id, base_path=PIPELINE_BASE_PATH)
        if not recorder:
            return jsonify({'error': f'Run {run_id} not found'}), 404

        # Get complete status from recorder
        status = recorder.get_status()
        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting pipeline status for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@pipeline_bp.route('/<run_id>/file/<filename>', methods=['GET'])
def get_file_by_name(run_id: str, filename: str):
    """
    Serve specific file by filename from run folder

    Enables fetching multiple entities of the same type by their unique filename.

    Args:
        run_id: UUID of the pipeline run
        filename: Filename (e.g., '09_output_image.png', '12_output_image_composite.png')

    Returns:
        File content with appropriate MIME type or 404 error
    """
    try:
        recorder = load_recorder(run_id, base_path=PIPELINE_BASE_PATH)
        if not recorder:
            return jsonify({'error': f'Run {run_id} not found'}), 404

        # Files are in final/ subfolder
        try:
            file_path = recorder.checked_path_for_filename(filename)
        except SafetyRefusal as refusal:
            return jsonify({'error': 'safety_blocked', 'detail': refusal.reason,
                            'run_id': run_id}), 403
        if not file_path.exists():
            return jsonify({'error': f'File {filename} not found in run {run_id}'}), 404

        # Determine MIME type from file extension
        extension = file_path.suffix.lower()
        mimetype_map = {
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.mp4': 'video/mp4',
        }
        mimetype = mimetype_map.get(extension, 'application/octet-stream')

        # Serve file
        return send_file(str(file_path), mimetype=mimetype)

    except Exception as e:
        logger.error(f"Error serving file {filename} for run {run_id}: {e}")
        return jsonify({'error': str(e)}), 500

@pipeline_bp.route('/<run_id>/entity/<entity_type>', methods=['GET'])
def get_entity(run_id: str, entity_type: str):
    """
    Serve entity file to frontend

    Serves the actual file content for a given entity type.
    Automatically determines content type based on file extension.

    Args:
        run_id: UUID of the pipeline run
        entity_type: Type of entity (e.g., 'input', 'translation', 'safety', 'interception',
                                      'output_image', 'output_audio', 'output_video')

    Returns:
        File content with appropriate MIME type or 404 error

    Examples:
        GET /api/pipeline/528e5af9.../entity/input
            -> Returns text/plain: "the recorded input text"

        GET /api/pipeline/528e5af9.../entity/safety
            -> Returns application/json: {"safe": true, ...}

        GET /api/pipeline/528e5af9.../entity/output_image
            -> Returns image/png: (binary PNG data)
    """
    try:
        recorder = load_recorder(run_id, base_path=PIPELINE_BASE_PATH)
        if not recorder:
            return jsonify({'error': f'Run {run_id} not found'}), 404

        # Get entity file path — asked with its verdict, so that a refusal can
        # say so instead of arriving as a missing file.
        entity_path = None
        for candidate in recorder.metadata.get('entities', []):
            if candidate.get('type') == entity_type:
                try:
                    entity_path = recorder.checked_entity_path(candidate)
                except SafetyRefusal as refusal:
                    return jsonify({'error': 'safety_blocked', 'detail': refusal.reason,
                                    'run_id': run_id}), 403
                break
        if not entity_path or not entity_path.exists():
            return jsonify({'error': f'Entity {entity_type} not found for run {run_id}'}), 404

        # Determine MIME type from file extension
        extension = entity_path.suffix.lower()
        mimetype_map = {
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
        }
        mimetype = mimetype_map.get(extension, 'application/octet-stream')

        # Serve file
        return send_file(
            entity_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=entity_path.name
        )

    except Exception as e:
        logger.error(f"Error serving entity {entity_type} for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@pipeline_bp.route('/<run_id>/entities', methods=['GET'])
def list_entities(run_id: str):
    """
    List all available entities for a run

    Returns metadata about all entities that have been created so far.
    Useful for discovering what entities are available without polling status.

    Args:
        run_id: UUID of the pipeline run

    Returns:
        JSON array of entity metadata or 404 error

    Example Response:
        {
            "run_id": "528e5af9-59b3-4551-b101-27e13dd6e43e",
            "entity_count": 4,
            "entities": [
                {
                    "sequence": 1,
                    "type": "input",
                    "filename": "01_input.txt",
                    "timestamp": "2025-11-04T20:12:37.569096",
                    "metadata": {},
                    "url": "/api/pipeline/528e5af9.../entity/input"
                },
                ...
            ]
        }
    """
    try:
        recorder = load_recorder(run_id, base_path=PIPELINE_BASE_PATH)
        if not recorder:
            return jsonify({'error': f'Run {run_id} not found'}), 404

        # Get status to access entities
        status = recorder.get_status()
        entities = status.get('entities', [])

        # Add URL for each entity
        for entity in entities:
            entity['url'] = f'/api/pipeline/{run_id}/entity/{entity["type"]}'

        return jsonify({
            'run_id': run_id,
            'entity_count': len(entities),
            'entities': entities
        })

    except Exception as e:
        logger.error(f"Error listing entities for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
