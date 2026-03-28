"""
Service for handling inpainting workflow operations
"""
import logging
import base64
import os
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class InpaintingService:
    """Service for handling inpainting-specific workflow operations"""
    
    def inject_image_to_workflow(self, workflow: Dict[str, Any], image_data: str) -> Dict[str, Any]:
        """
        Inject image data into Load Image nodes in the workflow
        
        Args:
            workflow: Workflow definition
            image_data: Base64 encoded image data
            
        Returns:
            Modified workflow with image injected
        """
        image_injected = False
        
        # Find LoadImage nodes
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "LoadImage":
                # Save image temporarily
                temp_path = self._save_temp_image(image_data)
                if temp_path:
                    node_data["inputs"]["image"] = temp_path
                    logger.info(f"Injected image into LoadImage node {node_id}")
                    image_injected = True
        
        if not image_injected:
            logger.warning("No LoadImage node found in workflow")
        
        return workflow
    
    def _save_temp_image(self, image_data: str) -> Optional[str]:
        """
        Save base64 image data to a temporary file
        
        Args:
            image_data: Base64 encoded image data
            
        Returns:
            Path to temporary file or None if failed
        """
        try:
            # Extract base64 data
            if image_data.startswith('data:image'):
                header, data = image_data.split(',', 1)
            else:
                data = image_data
            
            # Decode base64
            image_bytes = base64.b64decode(data)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                tmp.write(image_bytes)
                temp_path = tmp.name
            
            logger.info(f"Saved temporary image to {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to save temporary image: {e}")
            return None
    
    def prepare_inpainting_workflow(self, workflow: Dict[str, Any], prompt: str, 
                                  image_data: str) -> Dict[str, Any]:
        """
        Prepare a workflow for inpainting with both prompt and image
        
        Args:
            workflow: Workflow definition
            prompt: Text prompt
            image_data: Base64 encoded image data
            
        Returns:
            Modified workflow ready for inpainting
        """
        # Inject the image
        workflow = self.inject_image_to_workflow(workflow, image_data)
        
        # The prompt injection is handled by workflow_logic_service
        
        return workflow
    
    def analyze_and_concatenate(self, prompt: str, image_data: str, 
                              llm_service) -> str:
        """
        Analyze image and concatenate with prompt for standard workflows
        
        Args:
            prompt: User's text prompt
            image_data: Base64 encoded image data
            llm_service: Reference to LLM service for image analysis
            
        Returns:
            Concatenated prompt with image analysis
        """
        try:
            # Analyze the image
            analysis = llm_service.analyze_image(image_data)
            
            if analysis:
                # Format the combined prompt with a marker that the validation pipeline can recognize
                # This prevents the image analysis from being analyzed again
                combined_prompt = f"Material and medial properties: {analysis}. User prompt: {prompt}"
                logger.info(f"Combined prompt with image analysis: {combined_prompt[:100]}...")
                return combined_prompt
            else:
                logger.warning("Image analysis failed, using original prompt")
                return prompt
                
        except Exception as e:
            logger.error(f"Error during image analysis: {e}")
            return prompt
    
    def cleanup_temp_files(self):
        """Clean up temporary image files"""
        # This could be called periodically to clean up old temp files
        temp_dir = tempfile.gettempdir()
        for file in Path(temp_dir).glob("tmp*.png"):
            try:
                if file.is_file():
                    file.unlink()
                    logger.debug(f"Cleaned up temp file: {file}")
            except Exception as e:
                logger.warning(f"Failed to clean up {file}: {e}")


# Create singleton instance
inpainting_service = InpaintingService()
