"""
Media Routes - Serving images, audio, video from LOCAL STORAGE
Unified Media Storage: All media served from exports/json/ regardless of backend

Migration Status (Session 37):
- Updated to use LivePipelineRecorder metadata format (entities array)
- No longer depends on MediaStorage
- Supports both numbered filenames (06_output_image.png) and legacy (output_image.png)

Session 80: Added image upload endpoint for img2img workflow
"""
from flask import Blueprint, send_file, jsonify, request
import logging
from pathlib import Path
import uuid
import os
from werkzeug.utils import secure_filename
from PIL import Image

from my_app.services.pipeline_recorder import load_recorder
from config import JSON_STORAGE_DIR, UPLOADS_TMP_DIR

logger = logging.getLogger(__name__)

# Blueprint erstellen
media_bp = Blueprint('media', __name__, url_prefix='/api/media')


def _find_entity_by_type(entities: list, media_type: str, latest: bool = True) -> dict:
    """
    Find entity in entities array by media type.

    Args:
        entities: List of entity records from metadata
        media_type: Type to search for ('image', 'audio', 'video')
        latest: If True (default), return the LATEST (last) entity. If False, return first.

    Returns:
        Entity dict or None
    """
    found = []

    # Search for output_TYPE entities (e.g., output_image, output_audio)
    for entity in entities:
        entity_type = entity.get('type', '')
        if entity_type == f'output_{media_type}':
            found.append(entity)

    # Fallback: Search for just the type (legacy compatibility)
    if not found:
        for entity in entities:
            if entity.get('type') == media_type:
                found.append(entity)

    if not found:
        return None

    # Return latest (last) or first based on parameter
    return found[-1] if latest else found[0]


def _find_entities_by_type(entities: list, media_type: str) -> list:
    """
    Find ALL entities in entities array by media type.

    Args:
        entities: List of entity records from metadata
        media_type: Type to search for ('image', 'audio', 'video')

    Returns:
        List of entity dicts (empty list if none found)
    """
    results = []

    # Search for output_TYPE entities (e.g., output_image, output_audio)
    for entity in entities:
        entity_type = entity.get('type', '')
        if entity_type == f'output_{media_type}':
            results.append(entity)

    # Sort by sequence number (ensures chronological order)
    # Fallback to file_index for legacy workflows
    results.sort(key=lambda e: e.get('sequence', e.get('metadata', {}).get('file_index', 0)))

    return results


# Image upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
SUPPORTED_RESOLUTIONS = [512, 768, 1024, 1280]  # SD3.5 Large supported resolutions


def _allowed_file(filename: str) -> bool:
    """Check if filename has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _resize_image_to_supported_resolution(image: Image.Image, max_size: int = 2048) -> Image.Image:
    """
    Resize image to fit within supported resolution while maintaining aspect ratio.

    Args:
        image: PIL Image object
        max_size: Maximum dimension (default 2048 for Flux2/QWEN)

    Returns:
        Resized PIL Image object
    """
    width, height = image.size

    # If image is already within bounds, return as-is
    if width <= max_size and height <= max_size:
        return image

    # Calculate scaling factor to fit within max_size
    if width > height:
        new_width = max_size
        new_height = int((height / width) * max_size)
    else:
        new_height = max_size
        new_width = int((width / height) * max_size)

    # Resize with high-quality Lanczos filter
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")

    return resized


@media_bp.route('/upload/image', methods=['POST'])
def upload_image():
    """
    Upload image for img2img processing.

    Automatically resizes images to fit within supported model resolutions.

    Request body (multipart/form-data):
        - file: Image file (PNG, JPG, JPEG, WEBP) - REQUIRED
        - mask: Mask image file (PNG) - DEPRECATED (not used, text-guided editing sufficient)
        - run_id: Optional run ID to associate with (for organization)

    Returns:
        JSON with:
        - success: Boolean
        - image_id: Unique identifier for this upload
        - image_path: Absolute path to uploaded image (for backend)
        - filename: Secure filename with UUID
        - original_filename: Original filename from upload
        - original_size: Original dimensions [width, height]
        - resized_size: Final dimensions after resize [width, height]
        - file_size_bytes: File size in bytes
        - has_mask: Boolean (always False, deprecated feature)
        - mask_url: URL to retrieve mask (always None, deprecated feature)
    """
    try:
        # Check if file part exists
        if 'file' not in request.files:
            return jsonify({"error": "No file part in request"}), 400

        file = request.files['file']

        # Check if file was selected
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Validate file type
        if not _allowed_file(file.filename):
            return jsonify({
                "error": f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400

        # Load image to check size and resize
        try:
            image = Image.open(file.stream)
            original_size = image.size  # (width, height)

            # Convert RGBA to RGB if needed (for JPEG compatibility)
            if image.mode == 'RGBA':
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[3])  # Use alpha channel as mask
                image = rgb_image

            # Resize image to supported resolution
            resized_image = _resize_image_to_supported_resolution(image, max_size=2048)
            resized_size = resized_image.size

        except Exception as e:
            return jsonify({"error": f"Invalid image file: {str(e)}"}), 400

        # Generate unique image ID
        image_id = str(uuid.uuid4())

        # Secure filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()

        # Force PNG for consistency (lossless)
        if file_extension in ['jpg', 'jpeg']:
            file_extension = 'png'

        # Create filename with UUID to avoid collisions
        new_filename = f"{image_id}.{file_extension}"

        # Ensure uploads directory exists
        UPLOADS_TMP_DIR.mkdir(parents=True, exist_ok=True)

        # Save resized image
        file_path = UPLOADS_TMP_DIR / new_filename
        resized_image.save(str(file_path), format='PNG' if file_extension == 'png' else 'JPEG', quality=95)

        # Get final file size
        file_size = file_path.stat().st_size

        logger.info(f"Image uploaded: {new_filename} | Original: {original_size} → Resized: {resized_size} | Size: {file_size / 1024:.1f}KB")

        # DEPRECATED 2025-12-15: Process mask if provided (not used, text-guided editing sufficient)
        # QWEN Image Edit and Flux2 IMG2IMG support text-guided editing without explicit masks
        mask_path = None
        has_mask = False
        # if 'mask' in request.files:
        #     mask_file = request.files['mask']
        #     if mask_file.filename != '':
        #         try:
        #             mask_path = _process_and_save_mask(mask_file, image_id)
        #             has_mask = True
        #             logger.info(f"Mask uploaded for {image_id}: {mask_path}")
        #         except Exception as e:
        #             logger.warning(f"Failed to process mask: {e}")
        #             # Continue without mask (non-critical)

        # Return response
        return jsonify({
            "success": True,
            "image_id": image_id,
            "image_path": str(file_path),  # Absolute path for backend
            "filename": new_filename,
            "original_filename": original_filename,
            "original_size": list(original_size),
            "resized_size": list(resized_size),
            "file_size_bytes": file_size,
            "has_mask": has_mask,
            "mask_url": f'/api/media/masks/{image_id}' if has_mask else None
        }), 200

    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _process_and_save_mask(mask_file, image_uuid: str) -> str:
    """
    DEPRECATED 2025-12-15: Not actively used (text-guided editing sufficient)

    Process and save mask image for inpainting.

    Args:
        mask_file: File upload from request.files
        image_uuid: UUID of associated image

    Returns:
        Absolute path to saved mask file

    Raises:
        Exception if processing fails
    """
    try:
        # Load mask image
        mask_img = Image.open(mask_file.stream)

        # Convert to grayscale (L mode)
        if mask_img.mode != 'L':
            # If RGBA, use alpha channel or convert
            if mask_img.mode == 'RGBA':
                # Extract alpha channel or convert based on brightness
                mask_img = mask_img.convert('L')
            else:
                mask_img = mask_img.convert('L')

        # Resize to standard size (1024x1024)
        mask_img = mask_img.resize((1024, 1024), Image.Resampling.LANCZOS)

        # Ensure masks directory exists
        masks_dir = UPLOADS_TMP_DIR / 'masks'
        masks_dir.mkdir(parents=True, exist_ok=True)

        # Save mask as PNG
        mask_filename = f"{image_uuid}_mask.png"
        mask_path = masks_dir / mask_filename
        mask_img.save(str(mask_path), format='PNG')

        logger.info(f"Mask saved: {mask_filename} | Size: {mask_img.size}")

        return str(mask_path)

    except Exception as e:
        logger.error(f"Error processing mask: {e}")
        raise


@media_bp.route('/masks/<image_uuid>', methods=['GET'])
def get_mask(image_uuid: str):
    """
    DEPRECATED 2025-12-15: Not actively used (text-guided editing sufficient)

    Retrieve mask for given image UUID.

    Args:
        image_uuid: UUID of the image

    Returns:
        Mask PNG file or 404 error
    """
    try:
        mask_path = UPLOADS_TMP_DIR / 'masks' / f"{image_uuid}_mask.png"

        if not mask_path.exists():
            return jsonify({'error': 'Mask not found'}), 404

        return send_file(
            str(mask_path),
            mimetype='image/png',
            as_attachment=False,
            download_name=f'{image_uuid}_mask.png'
        )

    except Exception as e:
        logger.error(f"Error serving mask for {image_uuid}: {e}")
        return jsonify({'error': str(e)}), 500


@media_bp.route('/uploads/<image_id>', methods=['GET'])
def get_uploaded_image(image_id: str):
    """
    Session 152: Serve uploaded image by image_id.

    Used by image_input nodes to display preview.

    Args:
        image_id: UUID of the uploaded image

    Returns:
        Image file or 404 error
    """
    try:
        # Look for image in uploads directory (supports multiple extensions)
        for ext in ['png', 'jpg', 'jpeg', 'webp']:
            file_path = UPLOADS_TMP_DIR / f"{image_id}.{ext}"
            if file_path.exists():
                mimetype = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
                return send_file(
                    str(file_path),
                    mimetype=mimetype,
                    as_attachment=False,
                    download_name=f'{image_id}.{ext}'
                )

        return jsonify({'error': 'Image not found'}), 404

    except Exception as e:
        logger.error(f"Error serving uploaded image {image_id}: {e}")
        return jsonify({'error': str(e)}), 500


@media_bp.route('/image/<run_id>', methods=['GET'])
@media_bp.route('/image/<run_id>/<int:index>', methods=['GET'])
def get_image(run_id: str, index: int = -1):
    """
    Serve image from local storage by run_id (optionally by index for multi-output).

    Args:
        run_id: UUID of the pipeline run
        index: Image index. Default -1 returns the LATEST (most recent) image.
               Use explicit index (0, 1, 2...) for specific images.

    Returns:
        Image file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find ALL image entities
        image_entities = _find_entities_by_type(recorder.metadata.get('entities', []), 'image')

        if not image_entities:
            return jsonify({"error": f"No images found for run {run_id}"}), 404

        # Handle negative index (Python-style: -1 = last element)
        if index < 0:
            index = len(image_entities) + index  # -1 becomes len-1 (last)

        # Validate index
        if index < 0 or index >= len(image_entities):
            return jsonify({"error": f"Invalid index {index}. Available: 0-{len(image_entities)-1}"}), 404

        # Get requested image entity
        image_entity = image_entities[index]
        logger.info(f"[MEDIA] Serving image {index} of {len(image_entities)} for run {run_id}")

        # Get file path
        filename = image_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"Image file not found: {filename}"}), 404

        # Determine mimetype from format (from entity metadata or filename extension)
        file_format = image_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'webp': 'image/webp',
            'gif': 'image/gif'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'image/png')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}_{index}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving image for run {run_id} (index {index}): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/images/<run_id>', methods=['GET'])
def get_images(run_id: str):
    """
    Get metadata for ALL images from a run (for multi-output workflows).

    Args:
        run_id: UUID of the pipeline run

    Returns:
        JSON array with image metadata:
        {
            "run_id": "...",
            "total_images": 3,
            "images": [
                {
                    "index": 0,
                    "filename": "06_output_image.png",
                    "url": "/api/media/image/<run_id>/0",
                    "file_size_bytes": 1234567,
                    "node_id": "123",
                    "file_index": 0,
                    "total_files": 3,
                    "metadata": {...}
                },
                ...
            ]
        }
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find ALL image entities
        image_entities = _find_entities_by_type(recorder.metadata.get('entities', []), 'image')

        if not image_entities:
            return jsonify({"error": f"No images found for run {run_id}"}), 404

        # Build response
        images = []
        for idx, entity in enumerate(image_entities):
            filename = entity['filename']
            file_path = recorder.final_folder / filename

            if not file_path.exists():
                logger.warning(f"Image file not found: {filename}")
                continue

            file_size = file_path.stat().st_size
            entity_meta = entity.get('metadata', {})

            images.append({
                'index': idx,
                'filename': filename,
                'url': f'/api/media/image/{run_id}/{idx}',
                'file_size_bytes': file_size,
                'node_id': entity_meta.get('node_id', 'unknown'),
                'node_title': entity_meta.get('node_title', 'unknown'),
                'file_index': entity_meta.get('file_index', idx),
                'total_files': entity_meta.get('total_files', len(image_entities)),
                'metadata': entity_meta
            })

        return jsonify({
            'run_id': run_id,
            'total_images': len(images),
            'images': images
        })

    except Exception as e:
        logger.error(f"Error getting images for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/audio/<run_id>', methods=['GET'])
@media_bp.route('/audio/<run_id>/<int:index>', methods=['GET'])
def get_audio(run_id: str, index: int = 0):
    """
    Serve audio from local storage by run_id

    Args:
        run_id: UUID of the pipeline run
        index: Optional index (for consistency with image API, currently ignored)

    Returns:
        Audio file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find audio entity (try both 'audio' and 'music' types)
        audio_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'audio')
        if not audio_entity:
            audio_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'music')

        if not audio_entity:
            return jsonify({"error": f"No audio found for run {run_id}"}), 404

        # Get file path
        filename = audio_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"Audio file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = audio_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'flac': 'audio/flac'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'audio/mpeg')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving audio for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/music/<run_id>', methods=['GET'])
@media_bp.route('/music/<run_id>/<int:index>', methods=['GET'])
def get_music(run_id: str, index: int = 0):
    """
    Serve music from local storage by run_id

    Args:
        run_id: UUID of the pipeline run
        index: Optional index (for consistency with image API, currently ignored)

    Returns:
        Music file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find music entity (try 'music' first, then 'audio', then 'output_image' with mp3 format)
        music_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'music')
        if not music_entity:
            music_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'audio')
        if not music_entity:
            # Legacy: all media stored as 'output_image' - check for audio formats
            for entity in recorder.metadata.get('entities', []):
                if entity.get('type') == 'output_image' and entity.get('filename', '').endswith(('.mp3', '.wav', '.ogg', '.flac')):
                    music_entity = entity
                    break

        if not music_entity:
            return jsonify({"error": f"No music found for run {run_id}"}), 404

        # Get file path
        filename = music_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"Music file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = music_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'flac': 'audio/flac'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'audio/mpeg')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving music for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/video/<run_id>', methods=['GET'])
@media_bp.route('/video/<run_id>/<int:index>', methods=['GET'])
def get_video(run_id: str, index: int = 0):
    """
    Serve video from local storage by run_id

    Args:
        run_id: UUID of the pipeline run

    Returns:
        Video file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find video entity
        video_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'video')
        if not video_entity:
            return jsonify({"error": f"No video found for run {run_id}"}), 404

        # Get file path
        filename = video_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"Video file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = video_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'video/mp4')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving video for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/3d/<run_id>', methods=['GET'])
def get_3d(run_id: str):
    """
    Serve 3D model from local storage by run_id

    Args:
        run_id: UUID of the pipeline run

    Returns:
        3D model file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find 3D entity
        model_entity = _find_entity_by_type(recorder.metadata.get('entities', []), '3d')
        if not model_entity:
            return jsonify({"error": f"No 3D model found for run {run_id}"}), 404

        # Get file path
        filename = model_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"3D model file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = model_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'gltf': 'model/gltf+json',
            'glb': 'model/gltf-binary',
            'obj': 'model/obj',
            'stl': 'model/stl',
            'fbx': 'application/octet-stream',
            'usd': 'model/vnd.usd+zip',
            'usdz': 'model/vnd.usdz+zip'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'application/octet-stream')

        # Serve file — inline by default for <model-viewer>, download if ?download=true
        from flask import request as flask_request
        as_download = flask_request.args.get('download', 'false').lower() == 'true'
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=as_download,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving 3D model for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/midi/<run_id>', methods=['GET'])
def get_midi(run_id: str):
    """
    Serve MIDI file from local storage by run_id

    Args:
        run_id: UUID of the pipeline run

    Returns:
        MIDI file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find MIDI entity
        midi_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'midi')
        if not midi_entity:
            return jsonify({"error": f"No MIDI file found for run {run_id}"}), 404

        # Get file path
        filename = midi_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"MIDI file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = midi_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'mid': 'audio/midi',
            'midi': 'audio/midi'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'audio/midi')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving MIDI for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/sonicpi/<run_id>', methods=['GET'])
def get_sonicpi(run_id: str):
    """
    Serve Sonic Pi code from local storage by run_id

    Args:
        run_id: UUID of the pipeline run

    Returns:
        Sonic Pi file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find Sonic Pi entity
        sonicpi_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'sonicpi')
        if not sonicpi_entity:
            return jsonify({"error": f"No Sonic Pi code found for run {run_id}"}), 404

        # Get file path
        filename = sonicpi_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"Sonic Pi file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = sonicpi_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'rb': 'text/x-ruby',
            'txt': 'text/plain'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'text/x-ruby')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving Sonic Pi code for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/p5/<run_id>', methods=['GET'])
def get_p5(run_id: str):
    """
    Serve p5.js code from local storage by run_id

    Args:
        run_id: UUID of the pipeline run

    Returns:
        p5.js file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find p5 entity
        p5_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'p5')
        if not p5_entity:
            return jsonify({"error": f"No p5.js code found for run {run_id}"}), 404

        # Get file path
        filename = p5_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"p5.js file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = p5_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'js': 'text/javascript',
            'html': 'text/html',
            'txt': 'text/plain'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'text/javascript')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving p5.js code for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/tonejs/<run_id>', methods=['GET'])
def get_tonejs(run_id: str):
    """
    Serve Tone.js code from local storage by run_id

    Args:
        run_id: UUID of the pipeline run

    Returns:
        Tone.js file or 404 error
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Find tonejs entity
        tonejs_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'tonejs')
        if not tonejs_entity:
            return jsonify({"error": f"No Tone.js code found for run {run_id}"}), 404

        # Get file path
        filename = tonejs_entity['filename']
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            return jsonify({"error": f"Tone.js file not found: {filename}"}), 404

        # Determine mimetype from format
        file_format = tonejs_entity.get('metadata', {}).get('format', filename.split('.')[-1])
        mimetype_map = {
            'js': 'text/javascript',
            'html': 'text/html',
            'txt': 'text/plain'
        }
        mimetype = mimetype_map.get(file_format.lower(), 'text/javascript')

        # Serve file directly from disk
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=f'{run_id}.{file_format}'
        )

    except Exception as e:
        logger.error(f"Error serving Tone.js code for run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@media_bp.route('/info/<run_id>', methods=['GET'])
def get_media_info(run_id: str):
    """
    Get metadata about media for a run

    Args:
        run_id: UUID of the pipeline run

    Returns:
        JSON with media metadata
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Build response
        media_info = {
            'run_id': run_id,
            'schema': recorder.metadata.get('config_name', 'unknown'),
            'timestamp': recorder.metadata.get('timestamp', ''),
            'outputs': []
        }

        # Add output entities (filter for output_* types)
        for entity in recorder.metadata.get('entities', []):
            entity_type = entity.get('type', '')
            if entity_type.startswith('output_'):
                entity_meta = entity.get('metadata', {})
                # Get file size from disk
                file_path = recorder.final_folder / entity['filename']
                file_size = file_path.stat().st_size if file_path.exists() else 0

                media_info['outputs'].append({
                    'type': entity_type.replace('output_', ''),  # output_image → image
                    'filename': entity['filename'],
                    'backend': entity_meta.get('backend', 'unknown'),
                    'config': entity_meta.get('config', ''),
                    'file_size_bytes': file_size,
                    'format': entity_meta.get('format', ''),
                    'width': entity_meta.get('width'),
                    'height': entity_meta.get('height'),
                    'duration_seconds': entity_meta.get('duration_seconds')
                })

        return jsonify(media_info)

    except Exception as e:
        logger.error(f"Error getting media info for run {run_id}: {e}")
        return jsonify({"error": str(e)}), 500


@media_bp.route('/run/<run_id>', methods=['GET'])
def get_run_metadata(run_id: str):
    """
    Get complete run metadata including input/output text and media

    Args:
        run_id: UUID of the pipeline run

    Returns:
        JSON with complete run metadata
    """
    try:
        # Load recorder from disk
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({"error": f"Run {run_id} not found"}), 404

        # Build response
        result = {
            'run_id': recorder.run_id,
            'user_id': recorder.metadata.get('user_id', 'anonymous'),
            'timestamp': recorder.metadata.get('timestamp', ''),
            'schema': recorder.metadata.get('config_name', 'unknown'),
            'current_state': recorder.metadata.get('current_state', {}),
            'expected_outputs': recorder.metadata.get('expected_outputs', []),
            'entities': recorder.metadata.get('entities', [])
        }

        # Add text content from entities if available
        for entity in result['entities']:
            if entity['type'] == 'input':
                input_file = recorder.final_folder / entity['filename']
                if input_file.exists():
                    result['input_text'] = input_file.read_text(encoding='utf-8')
            elif entity['type'] == 'interception':
                output_file = recorder.final_folder / entity['filename']
                if output_file.exists():
                    result['transformed_text'] = output_file.read_text(encoding='utf-8')

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting run metadata for {run_id}: {e}")
        return jsonify({"error": str(e)}), 500
