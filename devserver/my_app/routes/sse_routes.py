"""
Server-Sent Events routes for real-time updates and connection keep-alive
"""
import json
import time
import logging
import uuid
from flask import Blueprint, Response, request, session
from collections import defaultdict
from threading import Lock

from my_app.services.comfyui_service import comfyui_service

logger = logging.getLogger(__name__)


def _get_queue_status() -> dict:
    """Get ComfyUI queue status via WebSocket client."""
    import asyncio
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    client = get_comfyui_ws_client()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context — use sync fallback
            return comfyui_service.get_queue_status()
        return loop.run_until_complete(client.get_queue_status())
    except RuntimeError:
        # No event loop — create one
        return asyncio.run(client.get_queue_status())

# Create blueprint
sse_bp = Blueprint('sse', __name__)

# Active connections tracking
active_connections = defaultdict(set)
connections_lock = Lock()

# User activity tracking
user_activity = {}
activity_lock = Lock()


def track_user_activity(user_id: str):
    """Track user activity timestamp"""
    with activity_lock:
        user_activity[user_id] = time.time()


def get_active_users_count():
    """Get count of active users (active in last 5 minutes)"""
    with activity_lock:
        current_time = time.time()
        timeout = 300  # 5 minutes
        
        # Clean up old entries
        expired_users = [
            user_id for user_id, last_seen in user_activity.items()
            if current_time - last_seen > timeout
        ]
        for user_id in expired_users:
            del user_activity[user_id]
        
        return len(user_activity)


def generate_sse_event(event_type: str, data: dict):
    """Generate SSE formatted event"""
    event = f"event: {event_type}\n"
    event += f"data: {json.dumps(data)}\n\n"
    return event


@sse_bp.route('/sse/connect')
def sse_connect():
    """SSE endpoint for real-time updates"""
    
    # Get or create session ID
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user_id = session['user_id']
    
    def generate():
        """Generator function for SSE stream"""
        connection_id = str(uuid.uuid4())
        
        # Track this connection
        with connections_lock:
            active_connections[user_id].add(connection_id)
        
        # Track user activity
        track_user_activity(user_id)
        
        try:
            # Send initial connection event with queue status
            try:
                queue_status = _get_queue_status()
            except Exception as e:
                logger.error(f"Error getting initial queue status: {e}")
                queue_status = {"total": 0, "queue_running": 0, "queue_pending": 0}
            
            yield generate_sse_event('connected', {
                'user_id': user_id,
                'queue_status': queue_status
            })
            
            # Keep connection alive with periodic updates
            last_update = time.time()
            update_interval = 10  # Send update every 10 seconds
            heartbeat_interval = 15  # Send heartbeat every 15 seconds
            last_heartbeat = time.time()
            
            while True:
                current_time = time.time()
                
                # Send periodic queue status updates
                if current_time - last_update >= update_interval:
                    track_user_activity(user_id)
                    
                    # Get queue status with error handling
                    try:
                        queue_status = _get_queue_status()
                        yield generate_sse_event('queue_update', {
                            'queue_status': queue_status,
                            'timestamp': current_time
                        })
                    except Exception as e:
                        # DEBUG level: ComfyUI unavailable is expected for API-only workflows
                        logger.debug(f"ComfyUI status update unavailable (expected for API-only workflows): {e}")
                        # Send silent zero-state (ComfyUI not needed for API workflows)
                        yield generate_sse_event('queue_update', {
                            'queue_status': {"total": 0, "queue_running": 0, "queue_pending": 0},
                            'timestamp': current_time,
                            'error': False  # Not an error - just unavailable
                        })
                    
                    last_update = current_time
                
                # Send heartbeat to keep connection alive
                if current_time - last_heartbeat >= heartbeat_interval:
                    yield generate_sse_event('heartbeat', {
                        'timestamp': current_time
                    })
                    last_heartbeat = current_time
                
                # Short sleep to prevent CPU spinning
                time.sleep(1)
                
        except GeneratorExit:
            # Clean up when connection closes
            with connections_lock:
                active_connections[user_id].discard(connection_id)
                if not active_connections[user_id]:
                    del active_connections[user_id]
            logger.info(f"SSE connection closed for user {user_id}")
        except Exception as e:
            logger.error(f"Unexpected error in SSE generator: {e}")
            # Clean up on any error
            with connections_lock:
                active_connections[user_id].discard(connection_id)
                if not active_connections[user_id]:
                    del active_connections[user_id]
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
    return response


@sse_bp.route('/sse/upload-progress', methods=['POST'])
def report_upload_progress():
    """Endpoint to report upload progress (keeps connection alive during uploads)"""
    
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user_id = session['user_id']
    track_user_activity(user_id)
    
    data = request.json
    progress = data.get('progress', 0)
    status = data.get('status', 'uploading')
    
    return json.dumps({
        'success': True,
        'user_id': user_id,
        'active_users': get_active_users_count()
    })


@sse_bp.route('/api/active-users')
def get_active_users():
    """Simple endpoint to get active users count"""
    
    # Track this request as user activity
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user_id = session['user_id']
    track_user_activity(user_id)
    
    return json.dumps({
        'active_users': get_active_users_count(),
        'timestamp': time.time()
    })


@sse_bp.route('/api/queue-status')
def get_queue_status_endpoint():
    """Simple endpoint to get ComfyUI queue status"""
    
    # Track this request as user activity
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user_id = session['user_id']
    track_user_activity(user_id)
    
    queue_status = _get_queue_status()

    return json.dumps({
        **queue_status,
        'timestamp': time.time()
    })
