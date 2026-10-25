"""
Service for interacting with ComfyUI API
"""
import json
import logging
import requests
import uuid
from typing import Dict, Optional, Any, List

from config import (
    COMFYUI_PORT,
    POLLING_TIMEOUT,
)

from my_app.services.comfyui_ws_client import (
    ComfyUISubmitError,
    _read_comfyui_refusal,
)

logger = logging.getLogger(__name__)


class ComfyUIService:
    """Service class for ComfyUI API interactions"""
    
    def __init__(self):
        self.base_url = f"http://localhost:{COMFYUI_PORT}"
        
    def submit_workflow(self, workflow: Dict[str, Any]) -> str:
        """Submit a workflow to ComfyUI for execution, or raise with the cause.

        The synchronous twin of `comfyui_ws_client._submit_workflow`, on the
        same endpoint. It used to answer every refusal with `None`, and its
        three callers each invented a sentence for that silence — one of them
        in German, on a screen where the only thing that helps is the name of
        the checkpoint ComfyUI could not find. Same exception as the twin now,
        read by the same reader.
        """
        try:
            # Debug logging for workflow submission
            logger.info(f"[COMFYUI SUBMIT] Workflow summary:")
            for node_id, node_data in workflow.items():
                class_type = node_data.get("class_type", "Unknown")
                logger.info(f"  Node {node_id}: {class_type}")
                if class_type == "KSampler":
                    inputs = node_data.get("inputs", {})
                    logger.info(f"    KSampler settings: steps={inputs.get('steps')}, cfg={inputs.get('cfg')}, "
                              f"sampler={inputs.get('sampler_name')}, scheduler={inputs.get('scheduler')}, denoise={inputs.get('denoise')}")
                elif class_type == "CLIPTextEncode":
                    text = node_data.get("inputs", {}).get("text", "")
                    if isinstance(text, str):
                        logger.info(f"    Prompt: {text[:150]}...")

            payload = {
                "prompt": workflow,
                "client_id": str(uuid.uuid4())
            }
            
            response = requests.post(
                f"{self.base_url}/prompt",
                json=payload,
                # Bounded like the twin, and for the same reason: /prompt is
                # a handshake that answers in under a second, and it runs
                # inside a GPU slot that a silent ComfyUI would hold forever.
                timeout=(10, 120)
            )

            if response.status_code != 200:
                detail = _read_comfyui_refusal(response.text)
                logger.error(
                    f"[COMFYUI SUBMIT] Refused: {response.status_code} \u2014 {detail}")
                logger.error(
                    f"[COMFYUI SUBMIT] ComfyUI said, in full: {response.text[:4000]}")
                raise ComfyUISubmitError(response.status_code, detail)

            # Parsed from the text, not through `response.json()`: that one
            # raises on a body that is not JSON, and the raise leaves through
            # the RequestException branch below, which reports status 0 --
            # "could not be reached", said about an answer that arrived.
            try:
                data = json.loads(response.text)
            except Exception:
                data = None
            prompt_id = data.get("prompt_id") if isinstance(data, dict) else None

            if not prompt_id:
                logger.error(f"[COMFYUI SUBMIT] 200 without a prompt_id: {response.text[:4000]}")
                raise ComfyUISubmitError(
                    200,
                    f"no prompt_id in the answer \u2014 {_read_comfyui_refusal(response.text)}")
                
            logger.info(f"Successfully submitted workflow to ComfyUI: {prompt_id}")
            return prompt_id

        except ComfyUISubmitError:
            raise
        except requests.exceptions.RequestException as e:
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    logger.error(f"ComfyUI API error response: {error_details}")
                except:
                    error_details = e.response.text
                    logger.error(f"ComfyUI API raw response: {error_details}")
            logger.error(f"ComfyUI request failed: {error_details}")
            
            # Log the workflow that failed for debugging
            logger.error(f"Failed workflow submission. First 500 chars: {str(workflow)[:500]}")
            
            # Check for specific Concatenate nodes
            for node_id, node_data in workflow.items():
                if node_data.get("class_type") == "Concatenate":
                    logger.error(f"Found Concatenate node {node_id}: {node_data}")

            # The body, where the station sent one: `error_details` above holds
            # it, and the exception is the only thing that leaves this function.
            said = _read_comfyui_refusal(error_details) if isinstance(error_details, str) else ""
            raise ComfyUISubmitError(
                0, f"{type(e).__name__}: {e}" + (f" — {said}" if said else "")) from e
    
    def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution history for a specific prompt_id
        
        Args:
            prompt_id: The prompt ID to get history for
            
        Returns:
            History data or None if not found/failed
        """
        try:
            response = requests.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=POLLING_TIMEOUT
            )
            
            if response.status_code == 404:
                # Workflow not ready yet
                return None
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get history for {prompt_id}: {e}")
            return None
    
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get the current queue status from ComfyUI
        
        Returns:
            Dictionary with queue status information
        """
        try:
            response = requests.get(
                f"{self.base_url}/queue",
                timeout=POLLING_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract queue length
            queue_running = len(data.get("queue_running", []))
            queue_pending = len(data.get("queue_pending", []))
            total_queue = queue_running + queue_pending
            
            return {
                "queue_running": queue_running,
                "queue_pending": queue_pending,
                "total": total_queue
            }
            
        except Exception as e:
            # DEBUG level: ComfyUI not running is expected when using API-only workflows (GPT-5, etc.)
            logger.debug(f"ComfyUI queue status unavailable (expected if using API-only workflows): {e}")
            return {
                "queue_running": 0,
                "queue_pending": 0,
                "total": 0
            }


# Create a singleton instance
comfyui_service = ComfyUIService()
