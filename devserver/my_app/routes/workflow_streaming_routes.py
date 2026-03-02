"""
Streaming workflow routes to prevent Cloudflare timeouts
"""
import logging
import json
import time
from flask import Blueprint, jsonify, request, current_app, Response

from config import (
    ENABLE_VALIDATION_PIPELINE,
    COMFYUI_PREFIX,
    POLLING_TIMEOUT
)
from my_app.services.ollama_service import ollama_service
from my_app.services.comfyui_service import comfyui_service
from my_app.services.workflow_logic_service import workflow_logic_service
from my_app.services.export_manager import export_manager
from my_app.services.streaming_response import create_streaming_response
from my_app.services.inpainting_service import inpainting_service
from my_app.utils.negative_terms import normalize_negative_terms

logger = logging.getLogger(__name__)

# Create blueprint
workflow_streaming_bp = Blueprint('workflow_streaming', __name__)


@workflow_streaming_bp.route('/run_workflow_stream', methods=['POST'])
def execute_workflow_stream():
    """Execute a workflow with streaming response to prevent timeouts"""
    
    def execute_workflow_internal():
        """Internal function to execute the workflow"""
        try:
            data = request.json
            workflow_name = data.get('workflow')
            original_prompt = data.get('prompt', '').strip()
            aspect_ratio = data.get('aspectRatio', '1:1')
            mode = data.get('mode', 'eco')  # DEPRECATED: eco/fast removed in Session 65, unused
            seed_mode = data.get('seedMode', 'random')
            custom_seed = data.get('customSeed', None)
            safety_level = data.get('safetyLevel', 'research')
            input_negative_terms = normalize_negative_terms(data.get('inputNegativeTerms'))
            
            # New dual input parameters
            image_data = data.get('imageData')
            input_mode = data.get('inputMode', 'standard')
            requires_image_analysis = data.get('requiresImageAnalysis', False)
            
            if not workflow_name:
                return {"error": "Kein Workflow angegeben."}
            
            # Handle different input modes
            if input_mode == 'inpainting':
                # Inpainting mode requires both prompt and image
                if not original_prompt or not image_data:
                    return {"error": "Inpainting-Workflows erfordern sowohl einen Prompt als auch ein Bild."}
                workflow_prompt = original_prompt
                
            elif input_mode == 'standard_combined' and requires_image_analysis:
                # Standard workflow with both prompt and image - need to analyze and concatenate
                if not image_data:
                    return {"error": "Bildanalyse angefordert, aber kein Bild bereitgestellt."}
                
                # Analyze image and concatenate with prompt
                workflow_prompt = inpainting_service.analyze_and_concatenate(
                    original_prompt, image_data, ollama_service
                )
                logger.info(f"Combined prompt after image analysis: {workflow_prompt[:50]}...")
                
            else:
                # Standard mode with just prompt
                if not original_prompt:
                    return {"error": "Kein Prompt angegeben."}
                workflow_prompt = original_prompt
            
            logger.info(f"Executing workflow: {workflow_name} in mode: {input_mode}")
            
            # Validate prompt if enabled
            if ENABLE_VALIDATION_PIPELINE:
                validation_result = ollama_service.validate_and_translate_prompt(workflow_prompt)
                
                if not validation_result["success"]:
                    return {"error": validation_result.get("error", "Prompt-Validierung fehlgeschlagen.")}
                
                workflow_prompt = validation_result["translated_prompt"]
            
            # Prepare workflow
            result = workflow_logic_service.prepare_workflow(
                workflow_name, workflow_prompt, aspect_ratio, mode, seed_mode, custom_seed, safety_level, input_negative_terms
            )
            
            if not result["success"]:
                return {"error": result["error"]}
            
            workflow = result["workflow"]
            status_updates = result.get("status_updates", [])
            used_seed = result.get("used_seed")
            
            # Handle inpainting workflows - inject image data
            if input_mode == 'inpainting' and image_data:
                logger.info("Injecting image into inpainting workflow")
                workflow = inpainting_service.inject_image_to_workflow(workflow, image_data)
                status_updates.append("Bild wurde in Inpainting-Workflow eingefügt.")
            
            # Submit to ComfyUI
            import asyncio
            from my_app.services.comfyui_ws_client import get_comfyui_ws_client
            ws_client = get_comfyui_ws_client()
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    prompt_id = comfyui_service.submit_workflow(workflow)
                else:
                    prompt_id = loop.run_until_complete(ws_client._submit_workflow(workflow))
            except RuntimeError:
                prompt_id = asyncio.run(ws_client._submit_workflow(workflow))

            if not prompt_id:
                return {"error": "ComfyUI hat kein Prompt-ID zurückgegeben."}
            
            # Store pending export info
            current_app.pending_exports[prompt_id] = {
                "workflow_name": workflow_name,
                "prompt": original_prompt,  # Always store the original prompt
                "translated_prompt": workflow_prompt,  # Store the workflow prompt (translated or original)
                "used_seed": used_seed,
                "safety_level": safety_level,
                "timestamp": time.time()
            }
            
            # Wait for completion with periodic checks
            max_wait_time = 480  # 8 minutes
            check_interval = 5   # Check every 5 seconds
            start_time = time.time()
            
            while (time.time() - start_time) < max_wait_time:
                # Use sync comfyui_service for polling (works in both modes — same port)
                history = comfyui_service.get_history(prompt_id)
                
                if history and prompt_id in history:
                    session_data = history[prompt_id]
                    outputs = session_data.get("outputs", {})
                    
                    if outputs:
                        # Workflow completed
                        # Trigger auto-export if enabled
                        if prompt_id in current_app.pending_exports:
                            export_info = current_app.pending_exports[prompt_id]
                            export_manager.auto_export_session(
                                prompt_id,
                                export_info["workflow_name"],
                                export_info["prompt"],
                                export_info.get("translated_prompt"),
                                export_info.get("used_seed"),
                                export_info.get("safety_level", "research")
                            )
                            del current_app.pending_exports[prompt_id]
                        
                        return {
                            "success": True,
                            "prompt_id": prompt_id,
                            "status": "completed",
                            "outputs": outputs,
                            "status_updates": status_updates,
                            "translated_prompt": workflow_prompt,
                            "used_seed": used_seed
                        }
                
                time.sleep(check_interval)
            
            # Timeout reached
            return {
                "error": "Workflow-Timeout erreicht",
                "prompt_id": prompt_id,
                "status": "timeout"
            }
            
        except Exception as e:
            logger.error(f"Error executing workflow: {e}")
            return {"error": f"Workflow-Ausführung fehlgeschlagen: {str(e)}"}
    
    # Create and return streaming response
    return create_streaming_response(execute_workflow_internal)


@workflow_streaming_bp.route('/workflow-status-poll/<prompt_id>', methods=['GET'])
def workflow_status_poll(prompt_id):
    """Fast polling endpoint for workflow status"""
    try:
        # Quick check without blocking (sync comfyui_service works for both modes)
        history = comfyui_service.get_history(prompt_id)

        if not history or prompt_id not in history:
            return jsonify({"status": "pending", "timestamp": time.time()})
        
        session_data = history[prompt_id]
        outputs = session_data.get("outputs", {})
        
        if outputs:
            return jsonify({
                "status": "completed",
                "outputs": outputs,
                "timestamp": time.time()
            })
        else:
            return jsonify({"status": "processing", "timestamp": time.time()})
            
    except Exception as e:
        logger.error(f"Error checking workflow status: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }), 500
