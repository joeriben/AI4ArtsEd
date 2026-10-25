import time
import json
import traceback
import subprocess
import requests
from typing import List
from flask import Blueprint, request, jsonify, Response, stream_with_context
from my_app.services.training_service import training_service

# Define Blueprint
training_bp = Blueprint('training', __name__)


# ============================================================================
# VRAM MANAGEMENT ENDPOINTS
# ============================================================================

@training_bp.route('/api/training/check-vram', methods=['GET'])
def check_vram():
    """
    Check current GPU VRAM status.
    Returns total, used, and free VRAM in GB.
    """
    try:
        # Query nvidia-smi for memory info
        result = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            encoding="utf-8"
        )

        lines = result.strip().split('\n')
        if not lines:
            return jsonify({"error": "No GPU detected"}), 500

        # Parse first GPU
        parts = lines[0].strip().split(', ')
        total_mib = int(parts[0])
        used_mib = int(parts[1])
        free_mib = int(parts[2])

        # Convert to GB
        total_gb = round(total_mib / 1024, 1)
        used_gb = round(used_mib / 1024, 1)
        free_gb = round(free_mib / 1024, 1)
        usage_percent = round((used_mib / total_mib) * 100, 1)

        # Check if enough VRAM for training (SD3.5 Large needs ~50GB minimum)
        # The training loads: MMDiT (~8GB), CLIP-L, CLIP-G, T5XXL (~10GB), VAE, plus LoRA network
        # With gradient checkpointing and batch_size=1, total ~48GB peak usage
        min_required_gb = 50
        can_train = free_gb >= min_required_gb

        return jsonify({
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "usage_percent": usage_percent,
            "can_train": can_train,
            "min_required_gb": min_required_gb,
            "recommendation": None if can_train else f"Free {min_required_gb - free_gb:.1f} GB VRAM to start training"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route('/api/training/clear-vram', methods=['POST'])
def clear_vram():
    """
    Unload models from VRAM to free space for training.
    Options in request body:
    - unload_comfyui: bool (default True)
    - unload_llm: bool (default True)
    """
    try:
        data = request.get_json(silent=True) or {}
        unload_comfyui = data.get('unload_comfyui', True)
        unload_llm = data.get('unload_llm', data.get('unload_ollama', True))

        results = {
            "comfyui": None,
            "llm": None,
            "errors": []
        }

        # Unload ComfyUI models via /free endpoint
        if unload_comfyui:
            try:
                # Through the gate, with the card held (services/gpu_gate.free_comfyui).
                from my_app.services.gpu_gate import free_comfyui
                from my_app.services.gpu_lease_client import GpuBusyError
                response = free_comfyui("training: clear VRAM", timeout=30, wait_s=60)
                if response.status_code == 200:
                    results["comfyui"] = "Models unloaded successfully"
                else:
                    results["comfyui"] = f"Warning: Status {response.status_code}"
            except GpuBusyError as e:
                results["errors"].append(f"ComfyUI: the card is held, nothing was unloaded ({e})")
            except requests.exceptions.ConnectionError:
                results["comfyui"] = "ComfyUI not running (OK)"
            except Exception as e:
                results["errors"].append(f"ComfyUI: {str(e)}")

        # The local language models are ComfyUI's since stage 3 of the move
        # (services/llm_client): the /free above took them off the card with
        # everything else ComfyUI held.
        if unload_llm:
            results["llm"] = ("held by ComfyUI, unloaded with its models"
                              if unload_comfyui else
                              "held by ComfyUI; unload ComfyUI's models to free them")

        # Wait a moment for VRAM to actually free
        time.sleep(2)

        # Get new VRAM status
        try:
            result = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used,memory.free",
                 "--format=csv,noheader,nounits"],
                encoding="utf-8"
            )
            parts = result.strip().split(', ')
            results["new_used_gb"] = round(int(parts[0]) / 1024, 1)
            results["new_free_gb"] = round(int(parts[1]) / 1024, 1)
        except:
            pass

        return jsonify({
            "success": len(results["errors"]) == 0,
            "results": results
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

class _FileWrapper:
    """What create_project reads from an upload: a name and a stream."""
    def __init__(self, storage):
        self.filename = storage.filename
        self.file = storage.stream


@training_bp.route('/api/training/describe', methods=['POST'])
def describe_images():
    """Take the dropped images and start saying what is on them.

    Returns at once with a token and the file list; the sentences arrive one
    by one and are read back from /describe/<token>. What a model writes here
    is what the trainer learns the images as, so it is shown before a run
    starts rather than written into a file nobody opens.
    """
    try:
        if 'images' not in request.files:
            return jsonify({"error": "No images provided"}), 400
        wrapped = [_FileWrapper(f) for f in request.files.getlist('images')]
        token = request.form.get('token') or None
        return jsonify(training_service.stage_and_describe(wrapped, token=token))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@training_bp.route('/api/training/describe/<token>', methods=['GET'])
def describe_status(token):
    """How far the describing got. 404 once the staged set is gone — swept
    after six hours, or moved into a project by a started run."""
    state = training_service.description_status(token)
    if state is None:
        return jsonify({"error": "unknown or expired"}), 404
    return jsonify(state)


@training_bp.route('/api/training/start', methods=['POST'])
def start_training():
    try:
        project_name = request.form.get('project_name')
        trigger_word = request.form.get('trigger_word', '')
        staging_token = request.form.get('staging_token') or None

        if not project_name:
            return jsonify({"error": "project_name is required"}), 400

        captions = None
        wrapped_images = []
        if staging_token:
            # The images are already here. What comes with the request are the
            # sentences as they now stand — corrected by hand or not.
            raw = request.form.get('captions')
            try:
                captions = json.loads(raw) if raw else []
            except ValueError:
                return jsonify({"error": "captions must be a JSON list"}), 400
            if not isinstance(captions, list):
                return jsonify({"error": "captions must be a JSON list"}), 400
        else:
            if 'images' not in request.files:
                return jsonify({"error": "No images provided"}), 400
            wrapped_images = [_FileWrapper(f) for f in request.files.getlist('images')]

        # Who trains, and in which course: a participant's course is the
        # session's, an educator names the one they lead (the platform's rule
        # for a course named by the client, `lora_register.session_scope`).
        owner_id = None
        course_id = None
        try:
            from my_app.services.lora_register import session_scope
            course_id, owner_id = session_scope(request.form.get('course_id'))
        except Exception:
            owner_id = None
            course_id = None

        result = training_service.create_project(
            project_name, wrapped_images, trigger_word,
            staging_token=staging_token, captions=captions,
            owner_id=owner_id, course_id=course_id,
        )
        
        success = training_service.start_training_process(project_name)
        
        if not success:
            return jsonify({"error": "Training could not be started (already running?)"}), 400
            
        return jsonify({"message": "Training started", "details": result})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@training_bp.route('/api/training/stop', methods=['POST'])
def stop_training():
    success = training_service.stop_training()
    return jsonify({"message": "Training stopped", "success": success})

@training_bp.route('/api/training/delete', methods=['POST'])
def delete_project():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
            
        project_name = data.get('project_name')
        if not project_name:
            return jsonify({"error": "Project name required"}), 400
            
        success = training_service.delete_project_files(project_name)
        if success:
            return jsonify({"message": "Project files deleted successfully"})
        else:
            return jsonify({"error": "Could not delete files (training in progress?)"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@training_bp.route('/api/training/loras', methods=['GET'])
def list_loras():
    """What this place has trained, so that it can be used.

    Until this existed, a finished adapter reached image generation only if
    somebody entered it into a configuration file on the server.
    """
    try:
        return jsonify({"loras": training_service.list_trained_loras()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@training_bp.route('/api/training/energy-estimate', methods=['GET'])
def energy_estimate():
    """What a run costs, read before anybody starts one.

    `estimate` is null when the card's power limit is unreadable; the page
    then shows nothing rather than an invented number.
    """
    return jsonify({"estimate": training_service.energy_estimate()})


@training_bp.route('/api/training/setup', methods=['GET'])
def training_setup():
    """The settings a run will use, read out of the config a run gets.

    The page states them; stating them from anywhere but the configuration
    itself would mean a number that drifts away from what runs.
    """
    return jsonify({"setup": training_service.training_setup()})


@training_bp.route('/api/training/status', methods=['GET'])
def get_training_status():
    return jsonify(training_service.get_status())

@training_bp.route('/api/training/events')
def training_events():
    def event_stream():
        last_log_index = 0
        while True:
            status = training_service.get_status()
            
            # Check for new logs
            logs = status["log_lines"]
            if len(logs) > last_log_index:
                new_lines = logs[last_log_index:]
                last_log_index = len(logs)
                
                # Send log batch
                yield f"event: log\ndata: {json.dumps(new_lines)}\n\n"
            
            # Send status update
            yield f"event: status\ndata: {json.dumps({'is_training': status['is_training'], 'error': status['error']})}\n\n"
            
            if not status["is_training"] and len(logs) == last_log_index:
                yield f"event: done\ndata: {json.dumps({'message': 'Training finished'})}\n\n"
                break
                
            time.sleep(1)

    return Response(stream_with_context(event_stream()), content_type='text/event-stream')