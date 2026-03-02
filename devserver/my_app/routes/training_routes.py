import time
import json
import traceback
import subprocess
import requests
from typing import List
from flask import Blueprint, request, jsonify, Response, stream_with_context
from my_app.services.training_service import training_service
from config import OLLAMA_API_BASE_URL

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
    - unload_ollama: bool (default True)
    """
    try:
        data = request.get_json(silent=True) or {}
        unload_comfyui = data.get('unload_comfyui', True)
        unload_ollama = data.get('unload_ollama', True)

        results = {
            "comfyui": None,
            "ollama": None,
            "errors": []
        }

        # Unload ComfyUI models via /free endpoint
        if unload_comfyui:
            try:
                # ComfyUI's /free endpoint clears all loaded models
                from config import COMFYUI_PORT
                response = requests.post(
                    f"http://127.0.0.1:{COMFYUI_PORT}/free",
                    json={"unload_models": True},
                    timeout=30
                )
                if response.status_code == 200:
                    results["comfyui"] = "Models unloaded successfully"
                else:
                    results["comfyui"] = f"Warning: Status {response.status_code}"
            except requests.exceptions.ConnectionError:
                results["comfyui"] = "ComfyUI not running (OK)"
            except Exception as e:
                results["errors"].append(f"ComfyUI: {str(e)}")

        # Unload Ollama models via keep_alive=0
        if unload_ollama:
            try:
                # First get list of loaded models
                loaded_response = requests.get(
                    f"{OLLAMA_API_BASE_URL}/api/ps",
                    timeout=10
                )

                if loaded_response.status_code == 200:
                    loaded_data = loaded_response.json()
                    models = loaded_data.get("models", [])

                    if not models:
                        results["ollama"] = "No models loaded"
                    else:
                        unloaded = []
                        for model_info in models:
                            model_name = model_info.get("name", "")
                            if model_name:
                                # Send request with keep_alive=0 to unload
                                unload_payload = {
                                    "model": model_name,
                                    "prompt": "",
                                    "keep_alive": 0,
                                    "stream": False
                                }
                                try:
                                    requests.post(
                                        f"{OLLAMA_API_BASE_URL}/api/generate",
                                        json=unload_payload,
                                        timeout=30
                                    )
                                    unloaded.append(model_name)
                                except:
                                    pass

                        results["ollama"] = f"Unloaded: {', '.join(unloaded)}" if unloaded else "No models to unload"
                else:
                    results["ollama"] = "Could not query loaded models"

            except requests.exceptions.ConnectionError:
                results["ollama"] = "Ollama not running (OK)"
            except Exception as e:
                results["errors"].append(f"Ollama: {str(e)}")

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

@training_bp.route('/api/training/start', methods=['POST'])
def start_training():
    try:
        project_name = request.form.get('project_name')
        trigger_word = request.form.get('trigger_word', '')
        
        if not project_name:
            return jsonify({"message": "project_name is required"}), 400
            
        if 'images' not in request.files:
            return jsonify({"message": "No images provided"}), 400
            
        uploaded_files = request.files.getlist('images')
        
        class FileWrapper:
            def __init__(self, storage):
                self.filename = storage.filename
                self.file = storage.stream

        wrapped_images = [FileWrapper(f) for f in uploaded_files]

        result = training_service.create_project(project_name, wrapped_images, trigger_word)
        
        success = training_service.start_training_process(project_name)
        
        if not success:
            return jsonify({"message": "Training could not be started (already running?)"}), 400
            
        return jsonify({"message": "Training started", "details": result})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": str(e)}), 500

@training_bp.route('/api/training/stop', methods=['POST'])
def stop_training():
    success = training_service.stop_training()
    return jsonify({"message": "Training stopped", "success": success})

@training_bp.route('/api/training/delete', methods=['POST'])
def delete_project():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400
            
        project_name = data.get('project_name')
        if not project_name:
            return jsonify({"message": "Project name required"}), 400
            
        success = training_service.delete_project_files(project_name)
        if success:
            return jsonify({"message": "Project files deleted successfully"})
        else:
            return jsonify({"message": "Could not delete files (training in progress?)"}), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500

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