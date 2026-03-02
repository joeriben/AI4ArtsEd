"""
Pipeline execution streaming routes for real-time progress updates
"""
import json
import time
import logging
import base64
import requests
from flask import Blueprint, Response
from pathlib import Path

from my_app.services.comfyui_service import comfyui_service
from my_app.services.pipeline_recorder import get_recorder

logger = logging.getLogger(__name__)

# Create blueprint
pipeline_stream_bp = Blueprint('pipeline_stream', __name__)


def generate_sse_event(event_type: str, data: dict):
    """Generate SSE formatted event"""
    event = f"event: {event_type}\n"
    event += f"data: {json.dumps(data)}\n\n"
    return event


def _get_comfyui_base_url() -> str:
    """Get ComfyUI base URL from the WebSocket client."""
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    return get_comfyui_ws_client().base_url


@pipeline_stream_bp.route('/api/pipeline/<run_id>/stream')
def stream_pipeline_progress(run_id: str):
    """
    Server-Sent Events stream for pipeline execution progress

    Streams real-time progress updates including:
    - Progress percentage (0-100%)
    - Preview images (base64 encoded)
    - Status updates
    - Final result

    Args:
        run_id: The pipeline execution run ID

    Returns:
        SSE stream with progress updates
    """
    def generate():
        """Generator function for SSE stream"""
        try:
            # Get recorder for this run
            from config import JSON_STORAGE_DIR
            recorder = get_recorder(
                run_id=run_id,
                config_name='unknown',  # Will be loaded from existing run
                safety_level='kids',
                user_id='anonymous',
                base_path=JSON_STORAGE_DIR
            )

            # Check if run exists
            if not recorder.run_folder.exists():
                yield generate_sse_event('error', {
                    'message': f'Run {run_id} not found'
                })
                return

            # Send initial connection event
            yield generate_sse_event('connected', {
                'run_id': run_id,
                'status': 'streaming'
            })

            # Get prompt_id from recorder metadata
            try:
                metadata_path = recorder.run_folder / 'metadata.json'
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        prompt_ids = metadata.get('comfyui_prompt_ids', [])

                        if not prompt_ids:
                            logger.warning(f"[STREAM] No prompt_id found for run {run_id}, cannot stream progress")
                            yield generate_sse_event('error', {
                                'message': 'No ComfyUI prompt_id found for this run'
                            })
                            return

                        prompt_id = prompt_ids[-1]['prompt_id']
                else:
                    logger.warning(f"[STREAM] No metadata found for run {run_id}")
                    yield generate_sse_event('error', {
                        'message': 'Run metadata not found'
                    })
                    return

                logger.info(f"[STREAM] Starting progress stream for run {run_id}, prompt_id {prompt_id}")

            except Exception as e:
                logger.error(f"[STREAM] Error loading run data: {e}")
                yield generate_sse_event('error', {
                    'message': f'Error loading run data: {str(e)}'
                })
                return

            # Poll ComfyUI for progress updates
            base_url = _get_comfyui_base_url()
            max_poll_time = 300  # 5 minutes max
            poll_interval = 1.0  # Poll every second
            start_time = time.time()
            last_progress = 0

            while True:
                # Check timeout
                if time.time() - start_time > max_poll_time:
                    yield generate_sse_event('error', {
                        'message': 'Generation timeout exceeded'
                    })
                    break

                try:
                    # Get history from ComfyUI (direct HTTP, works for both modes)
                    response = requests.get(
                        f"{base_url}/history/{prompt_id}",
                        timeout=10
                    )

                    if response.status_code == 200:
                        history = response.json()

                        if prompt_id in history:
                            prompt_data = history[prompt_id]
                            status = prompt_data.get('status', {})
                            status_str = status.get('status_str', 'pending')

                            if status_str == 'success':
                                outputs = prompt_data.get('outputs', {})

                                # Download final image
                                final_image = None
                                for node_id, node_output in outputs.items():
                                    if 'images' in node_output and len(node_output['images']) > 0:
                                        image_info = node_output['images'][0]
                                        try:
                                            params = {
                                                'filename': image_info['filename'],
                                                'subfolder': image_info.get('subfolder', ''),
                                                'type': image_info.get('type', 'output')
                                            }

                                            img_response = requests.get(
                                                f"{base_url}/view",
                                                params=params,
                                                timeout=10
                                            )

                                            if img_response.status_code == 200:
                                                image_data = img_response.content
                                                final_image = base64.b64encode(image_data).decode('utf-8')
                                                logger.info(f"[STREAM] Downloaded final image: {len(image_data)} bytes")
                                                break
                                            else:
                                                logger.error(f"[STREAM] Failed to download image: HTTP {img_response.status_code}")
                                        except Exception as e:
                                            logger.error(f"[STREAM] Error downloading final image: {e}")

                                yield generate_sse_event('complete', {
                                    'progress': 100,
                                    'status': 'completed',
                                    'final_image': f'data:image/png;base64,{final_image}' if final_image else None
                                })
                                break

                            elif status_str == 'error':
                                yield generate_sse_event('error', {
                                    'message': 'Generation failed',
                                    'details': status
                                })
                                break

                            else:
                                # Still executing — estimate progress
                                elapsed = time.time() - start_time
                                estimated_total = 30

                                progress = min(int((elapsed / estimated_total) * 90), 90)

                                if progress > last_progress:
                                    yield generate_sse_event('progress', {
                                        'progress': progress,
                                        'status': 'generating',
                                        'elapsed': elapsed
                                    })
                                    last_progress = progress

                        else:
                            yield generate_sse_event('progress', {
                                'progress': 0,
                                'status': 'queued'
                            })

                except Exception as e:
                    logger.error(f"[STREAM] Error polling ComfyUI: {e}")

                time.sleep(poll_interval)

        except GeneratorExit:
            logger.info(f"[STREAM] Client disconnected from stream {run_id}")
        except Exception as e:
            logger.error(f"[STREAM] Unexpected error in SSE generator: {e}")
            yield generate_sse_event('error', {
                'message': f'Stream error: {str(e)}'
            })

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
    return response
