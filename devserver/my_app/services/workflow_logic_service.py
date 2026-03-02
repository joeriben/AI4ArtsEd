"""
Service for workflow manipulation and logic
"""
import logging
import json
import random
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from config import (
    LOCAL_WORKFLOWS_DIR,
    OLLAMA_TO_OPENROUTER_MAP,
    OPENROUTER_TO_OLLAMA_MAP,
    ENABLE_VALIDATION_PIPELINE,
    SAFETY_NEGATIVE_TERMS,
    DEFAULT_NEGATIVE_TERMS,
    ENABLE_MODEL_PATH_RESOLUTION,
    MODEL_RESOLUTION_FALLBACK,
    COMFYUI_BASE_PATH
)
from my_app.utils.helpers import (
    calculate_dimensions,
    parse_model_name,
)
from my_app.utils.negative_terms import normalize_negative_terms
from my_app.utils.workflow_node_injection import inject_concatenate_for_safety_terms
from my_app.services.model_path_resolver import ModelPathResolver

logger = logging.getLogger(__name__)


class WorkflowLogicService:
    """Service for handling workflow logic and manipulation"""
    
    def __init__(self):
        self.workflows_dir = LOCAL_WORKFLOWS_DIR
        self.metadata_path = self.workflows_dir / "metadata.json"
        self.metadata = None
        self._load_metadata()
        
        # Initialize model path resolver if enabled
        if ENABLE_MODEL_PATH_RESOLUTION and COMFYUI_BASE_PATH:
            self.model_resolver = ModelPathResolver(
                comfyui_base=COMFYUI_BASE_PATH
            )
            logger.info("Model path resolver initialized")
        else:
            self.model_resolver = None
            if ENABLE_MODEL_PATH_RESOLUTION:
                logger.warning("Model path resolution enabled but paths not configured")
            else:
                logger.info("Model path resolution disabled")
    
    
    def _load_metadata(self):
        """Load workflow metadata from metadata.json"""
        try:
            if self.metadata_path.exists():
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info("Workflow metadata loaded successfully")
            else:
                logger.warning(f"Metadata file not found at {self.metadata_path}")
                self.metadata = {"categories": {}, "workflows": {}, "ui": {}}
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            self.metadata = {"categories": {}, "workflows": {}, "ui": {}}
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get workflow metadata"""
        if self.metadata is None:
            self._load_metadata()
        return self.metadata or {"categories": {}, "workflows": {}, "ui": {}}
    
    def get_random_workflow_from_folders(self, folders: Optional[List[str]] = None) -> Optional[str]:
        """
        Get a random workflow from specified folders.
        
        Args:
            folders: List of folder names under /workflows_legacy/ 
                    (defaults to SYSTEM_WORKFLOW_FOLDERS from config)
                    
        Returns:
            Workflow filename like "aesthetics/workflow.json" or None if no workflows found
        """
        if folders is None:
            from config import SYSTEM_WORKFLOW_FOLDERS
            folders = SYSTEM_WORKFLOW_FOLDERS
        
        eligible_workflows = []
        
        for folder in folders:
            folder_path = self.workflows_dir / folder
            if folder_path.exists():
                # Collect all .json files in this folder
                for workflow_file in folder_path.glob("*.json"):
                    # Skip metadata.json and hidden files
                    if workflow_file.name == "metadata.json" or workflow_file.name.startswith("."):
                        continue
                    # Create relative path: "aesthetics/workflow.json"
                    relative_path = f"{folder}/{workflow_file.name}"
                    eligible_workflows.append(relative_path)
                    
            else:
                logger.warning(f"Workflow folder '{folder}' does not exist")
        
        if eligible_workflows:
            selected = random.choice(eligible_workflows)
            logger.info(f"Random workflow selected from {folders}: {selected}")
            return selected
        else:
            logger.error(f"No workflows found in folders: {folders}")
            return None
    
    def load_workflow(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a workflow file by name
        
        Args:
            workflow_name: Name of the workflow file
            
        Returns:
            Workflow dictionary or None if not found
        """
        # Security check
        if ".." in workflow_name or workflow_name.startswith("/"):
            logger.error(f"Invalid workflow name: {workflow_name}")
            return None
        
        workflow_path = self.workflows_dir / workflow_name
        
        try:
            with open(workflow_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Workflow not found: {workflow_name}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in workflow {workflow_name}: {e}")
            return None
    
    def list_workflows(self) -> list:
        """
        List all available workflow files from subdirectories
        
        Returns:
            List of workflow filenames (including subdirectory paths)
        """
        try:
            workflows = []
            
            # Get all json files from subdirectories
            for json_file in self.workflows_dir.rglob("*.json"):
                # Skip metadata.json and hidden files
                if json_file.name == "metadata.json" or json_file.name.startswith("."):
                    continue
                    
                # Get relative path from workflows directory
                relative_path = json_file.relative_to(self.workflows_dir)
                workflows.append(str(relative_path))
            
            return sorted(workflows)
        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return []
    
    def check_safety_node(self, workflow_name: str) -> bool:
        """
        Check if a workflow contains the safety node
        
        Args:
            workflow_name: Name of the workflow file
            
        Returns:
            True if workflow contains safety node, False otherwise
        """
        workflow = self.load_workflow(workflow_name)
        if not workflow:
            return False
        
        # Check if any node has the safety switch class type
        for node_data in workflow.values():
            if node_data.get("class_type") == "ai4artsed_switch_promptsafety":
                return True
        
        return False
    
    def is_inpainting_workflow(self, workflow_name: str) -> bool:
        """
        Check if a workflow is an inpainting/image editing workflow.
        Requires both an appropriate model AND a LoadImage node.
        
        Args:
            workflow_name: Name of the workflow file
            
        Returns:
            True if workflow is for inpainting/image editing, False otherwise
        """
        workflow = self.load_workflow(workflow_name)
        if not workflow:
            return False
        
        has_inpainting_model = False
        has_load_image = False
        
        # Check for both conditions
        for node_data in workflow.values():
            class_type = node_data.get("class_type")
            
            # Check for inpainting/image editing models
            if class_type == "CheckpointLoaderSimple":
                ckpt_name = node_data.get("inputs", {}).get("ckpt_name", "").lower()
                if "inpaint" in ckpt_name or "omnigen2" in ckpt_name:
                    has_inpainting_model = True
            elif class_type == "UNETLoader":
                # OmniGen2 uses UNETLoader instead of CheckpointLoaderSimple
                unet_name = node_data.get("inputs", {}).get("unet_name", "").lower()
                if "omnigen2" in unet_name:
                    has_inpainting_model = True
            
            # Check for LoadImage node
            if class_type in ["LoadImage", "LoadImageMask"]:
                has_load_image = True
        
        # Both conditions must be met
        return has_inpainting_model and has_load_image
    
    def get_workflow_info(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get comprehensive workflow information
        
        Args:
            workflow_name: Name of the workflow file
            
        Returns:
            Dict with workflow information
        """
        workflow = self.load_workflow(workflow_name)
        if not workflow:
            return {
                "isInpainting": False,
                "hasLoadImageNode": False,
                "requiresBothInputs": False,
                "error": "Workflow not found"
            }
        
        has_inpainting_model = False
        has_load_image = False
        
        # Check for inpainting/image editing models and load image nodes
        for node_data in workflow.values():
            class_type = node_data.get("class_type")
            
            # Check for inpainting/image editing models
            if class_type == "CheckpointLoaderSimple":
                ckpt_name = node_data.get("inputs", {}).get("ckpt_name", "").lower()
                if "inpaint" in ckpt_name or "omnigen2" in ckpt_name:
                    has_inpainting_model = True
            elif class_type == "UNETLoader":
                # OmniGen2 uses UNETLoader instead of CheckpointLoaderSimple
                unet_name = node_data.get("inputs", {}).get("unet_name", "").lower()
                if "omnigen2" in unet_name:
                    has_inpainting_model = True
            
            # Check for load image node
            if class_type in ["LoadImage", "LoadImageMask"]:
                has_load_image = True
        
        # Only consider it an inpainting workflow if BOTH conditions are met
        is_inpainting = has_inpainting_model and has_load_image
        
        return {
            "isInpainting": is_inpainting,
            "hasLoadImageNode": has_load_image,
            "requiresBothInputs": is_inpainting  # Inpainting requires both inputs
        }
    
    def switch_to_eco_mode(self, workflow: Dict[str, Any]) -> Tuple[Dict[str, Any], list]:
        """
        Switch workflow to eco mode (local models)
        
        Args:
            workflow: Workflow definition
            
        Returns:
            Tuple of (modified workflow, status updates)
        """
        status_updates = ["Eco-Modus aktiviert. Alle Modelle werden lokal ausgeführt."]
        
        for node_data in workflow.values():
            if node_data.get("class_type") == "ai4artsed_prompt_interception":
                current_model_full = node_data["inputs"].get("model", "")
                
                if current_model_full.startswith("openrouter/"):
                    openrouter_model_name = current_model_full[11:].split(' ')[0]
                    local_model = OPENROUTER_TO_OLLAMA_MAP.get(openrouter_model_name)
                    
                    if local_model:
                        node_data["inputs"]["model"] = f"local/{local_model}"
                        logger.info(f"Swapped {current_model_full} to {node_data['inputs']['model']}")
                        status_updates.append(
                            f"Cloud-Modell '{openrouter_model_name}' durch lokales Modell '{local_model}' ersetzt."
                        )
                    else:
                        logger.warning(f"No local equivalent found for {current_model_full}")
                        status_updates.append(
                            f"Warnung: Kein lokales Äquivalent für '{openrouter_model_name}' gefunden."
                        )
        
        return workflow, status_updates
    
    def switch_to_fast_mode(self, workflow: Dict[str, Any]) -> Tuple[Dict[str, Any], list]:
        """
        Switch workflow to fast mode (cloud models)
        
        Args:
            workflow: Workflow definition
            
        Returns:
            Tuple of (modified workflow, status updates)
        """
        status_updates = ["Schnell-Modus aktiviert. Suche nach Cloud-basierten Modell-Äquivalenten..."]
        
        for node_data in workflow.values():
            if node_data.get("class_type") == "ai4artsed_prompt_interception":
                current_model_full = node_data["inputs"].get("model", "")
                
                if current_model_full.startswith("local/"):
                    local_model_raw = current_model_full[6:]
                    local_model_with_tag = re.split(r'\s*\[', local_model_raw)[0].strip()
                    
                    # Try for exact match first
                    exact_match = (
                        OLLAMA_TO_OPENROUTER_MAP.get(local_model_with_tag) or 
                        OLLAMA_TO_OPENROUTER_MAP.get(local_model_with_tag.split(':')[0])
                    )
                    
                    # Apply intelligent fallback logic
                    req_base, req_size = parse_model_name(local_model_with_tag)
                    
                    if 7 <= req_size <= 32 and "mistral-nemo" in OLLAMA_TO_OPENROUTER_MAP and local_model_with_tag != "mistral-nemo":
                        if exact_match == "mistralai/mistral-small-24b" or not exact_match:
                            openrouter_model = OLLAMA_TO_OPENROUTER_MAP["mistral-nemo"]
                            status_updates.append(
                                f"Using Mistral Nemo (14b) as intelligent fallback for {req_size}b model."
                            )
                        else:
                            openrouter_model = exact_match
                            status_updates.append(f"Using exact match: '{exact_match}'.")
                    elif exact_match:
                        openrouter_model = exact_match
                        status_updates.append(f"Using exact match: '{exact_match}'.")
                    else:
                        # Intelligent fallback
                        openrouter_model = self._find_fallback_model(local_model_with_tag, req_base, req_size)
                        if openrouter_model:
                            status_updates.append(f"Found fallback: '{openrouter_model}'.")
                        else:
                            status_updates.append(f"No fallback found for '{local_model_with_tag}'.")
                    
                    if openrouter_model:
                        node_data["inputs"]["model"] = f"openrouter/{openrouter_model}"
                        logger.info(f"Swapped {current_model_full} to {node_data['inputs']['model']}")
        
        return workflow, status_updates
    
    def _find_fallback_model(self, model_name: str, req_base: str, req_size: int) -> Optional[str]:
        """Find a suitable fallback model for fast mode"""
        # For medium-sized models, prefer Mistral Nemo
        if 7 <= req_size <= 32 and "mistral-nemo" in OLLAMA_TO_OPENROUTER_MAP:
            return OLLAMA_TO_OPENROUTER_MAP["mistral-nemo"]
        
        # Find candidates in the same family
        candidates = []
        for map_key in OLLAMA_TO_OPENROUTER_MAP.keys():
            cand_base, cand_size = parse_model_name(map_key)
            if (req_base.startswith(cand_base) or cand_base.startswith(req_base)) and cand_size >= req_size:
                candidates.append((map_key, cand_size))
        
        if candidates:
            candidates.sort(key=lambda x: x[1])
            return OLLAMA_TO_OPENROUTER_MAP[candidates[0][0]]
        
        # Ultimate fallback
        return OLLAMA_TO_OPENROUTER_MAP.get("mistral-nemo")
    
    def inject_prompt(self, workflow: Dict[str, Any], prompt: str) -> bool:
        """
        Inject a prompt into the workflow
        
        Args:
            workflow: Workflow definition
            prompt: Prompt text to inject
            
        Returns:
            True if injection successful, False otherwise
        """
        for node_data in workflow.values():
            if node_data.get("_meta", {}).get("title") == "ai4artsed_text_prompt":
                target_input = "value" if "value" in node_data["inputs"] else "text"
                if target_input in node_data["inputs"]:
                    node_data["inputs"][target_input] = prompt
                    logger.info("Injected prompt into workflow")
                    return True
        
        logger.warning("Could not find prompt injection node in workflow")
        return False
    
    def update_dimensions(self, workflow: Dict[str, Any], aspect_ratio: str):
        """
        Update image dimensions in workflow based on aspect ratio
        
        Args:
            workflow: Workflow definition
            aspect_ratio: Aspect ratio string (e.g., "16:9")
        """
        dims = calculate_dimensions("1024", aspect_ratio)
        
        for node_data in workflow.values():
            if node_data["class_type"] == "EmptyLatentImage":
                if not isinstance(node_data["inputs"].get("width"), list):
                    node_data["inputs"]["width"] = dims["width"]
                if not isinstance(node_data["inputs"].get("height"), list):
                    node_data["inputs"]["height"] = dims["height"]
    
    def apply_seed_control(self, workflow: Dict[str, Any], seed_mode: str, custom_seed: Optional[int] = None) -> int:
        """
        Apply seed control to ALL seed-sensitive nodes in the workflow
        Ignores external seed connections and applies the same seed everywhere
        
        Args:
            workflow: Workflow definition
            seed_mode: 'random', 'standard', or 'fixed'
            custom_seed: Custom seed value for 'fixed' mode
            
        Returns:
            The seed value that was used
        """
        # Determine the seed value to use
        if seed_mode == 'standard':
            seed_value = 123456789
        elif seed_mode == 'fixed' and custom_seed is not None:
            seed_value = custom_seed
        else:  # random
            seed_value = random.randint(0, 2**32 - 1)
        
        # List of all sampler node types
        sampler_types = [
            "KSampler", "KSamplerAdvanced", "SamplerCustom",
            "StableAudioSampler", "MusicGenGenerate",
            "AudioScheduledSampler"  # Add more sampler types as needed
        ]
        
        # Apply seed to all sampler nodes
        for node_data in workflow.values():
            # Check if it's a sampler
            if node_data.get("class_type") in sampler_types:
                if "inputs" in node_data and "seed" in node_data["inputs"]:
                    # Override seed, regardless of connections
                    node_data["inputs"]["seed"] = seed_value
                    logger.info(f"Set seed {seed_value} in {node_data.get('class_type')} node")
        
        return seed_value
    
    def apply_safety_level(self, workflow: Dict[str, Any], safety_level: str) -> bool:
        """
        Apply safety level to the workflow if the safety node exists
        
        Args:
            workflow: Workflow definition
            safety_level: Safety level ('research', 'youth', or 'kids')

        Returns:
            True if safety node was found and updated, False otherwise
        """
        # Look for the safety switch node
        safety_node_found = False
        
        for node_data in workflow.values():
            if node_data.get("class_type") == "ai4artsed_switch_promptsafety":
                # Found the safety node, update its filter_level
                if "inputs" in node_data:
                    node_data["inputs"]["filter_level"] = safety_level
                    logger.info(f"Applied safety level '{safety_level}' to workflow")
                    safety_node_found = True
        
        if not safety_node_found:
            logger.info("No safety node found in workflow, safety level not applied")
        
        return safety_node_found
    
    def enhance_negative_prompts(self, workflow: Dict[str, Any], safety_level: str, input_negative_terms: str = "") -> int:
        """
        Enhance negative prompts with default, input, and safety terms
        
        Args:
            workflow: Workflow definition
            safety_level: Safety level ('kids' or 'youth')
            input_negative_terms: Additional negative terms from user input
            
        Returns:
            Number of negative prompts enhanced
        """
        input_negative_terms = normalize_negative_terms(input_negative_terms)
        enhanced_count = 0
        
        logger.info(f"=== Starting {safety_level} safety enhancement ===")
        logger.info(f"Total nodes in workflow: {len(workflow)}")
        
        # First, identify which CLIPTextEncode nodes are connected to negative inputs of KSamplers
        negative_clip_nodes = set()
        
        # List of sampler node types that have negative conditioning
        sampler_types = ["KSampler", "KSamplerAdvanced", "SamplerCustom"]
        
        # Find all sampler nodes and trace their negative inputs
        for node_id, node_data in workflow.items():
            node_type = node_data.get("class_type")
            logger.debug(f"Checking node {node_id}: type={node_type}")
            
            if node_type in sampler_types:
                logger.info(f"Found sampler node {node_id} of type {node_type}")
                # Check if this sampler has a negative input
                inputs = node_data.get("inputs", {})
                logger.debug(f"Sampler inputs: {list(inputs.keys())}")
                
                if "negative" in inputs:
                    negative_input = inputs["negative"]
                    logger.info(f"Sampler node {node_id} has negative input: {negative_input}")
                    
                    # If it's a connection (list with node_id and output_index)
                    if isinstance(negative_input, list) and len(negative_input) >= 2:
                        connected_node_id = str(negative_input[0])
                        negative_clip_nodes.add(connected_node_id)
                        logger.info(f"Added node {connected_node_id} to negative_clip_nodes")
                    else:
                        logger.warning(f"Negative input is not a proper connection: {negative_input}")
        
        logger.info(f"Found {len(negative_clip_nodes)} nodes connected to negative inputs: {negative_clip_nodes}")
        
        # Build the additional terms to add in order:
        # 1. DEFAULT_NEGATIVE_TERMS (from config)
        # 2. INPUT_NEGATIVE_TERMS (from user)
        # 3. SAFETY_NEGATIVE_TERMS (based on safety level)
        
        terms_to_add = []
        
        # Add DEFAULT_NEGATIVE_TERMS if not empty
        if DEFAULT_NEGATIVE_TERMS and DEFAULT_NEGATIVE_TERMS.strip():
            terms_to_add.append(DEFAULT_NEGATIVE_TERMS.strip())
            logger.info(f"Adding DEFAULT_NEGATIVE_TERMS: {DEFAULT_NEGATIVE_TERMS[:50]}...")
        
        # Add INPUT_NEGATIVE_TERMS if provided
        if input_negative_terms:
            terms_to_add.append(input_negative_terms)
            logger.info(f"Adding INPUT_NEGATIVE_TERMS: {input_negative_terms[:50]}...")
        
        # Add SAFETY_NEGATIVE_TERMS based on safety level
        if safety_level in ["kids", "youth"]:
            safety_terms = ", ".join(SAFETY_NEGATIVE_TERMS.get(safety_level, []))
            if safety_terms:
                terms_to_add.append(safety_terms)
                logger.info(f"Adding SAFETY_NEGATIVE_TERMS for {safety_level} (length: {len(safety_terms)} chars)")
        
        # Combine all terms
        all_additional_terms = ", ".join(terms_to_add) if terms_to_add else ""
        logger.info(f"Total additional terms to add (length: {len(all_additional_terms)} chars)")
        
        for node_id in negative_clip_nodes:
            if node_id in workflow:
                node_data = workflow[node_id]
                node_type = node_data.get("class_type")
                logger.info(f"Processing negative node {node_id} with class_type: {node_type}")
                
                if node_type == "CLIPTextEncode":
                    current_text = node_data.get("inputs", {}).get("text", "")
                    logger.info(f"Current negative prompt input type: {type(current_text)}")
                    
                    # Check if it's a node connection (list) or a string
                    if isinstance(current_text, list) and len(current_text) >= 2:
                        # It's a node connection [node_id, output_idx]
                        logger.info(f"Node {node_id} has a connection: {current_text}")
                        
                        if all_additional_terms:
                            # Use our new helper to inject a StringConcatenate node
                            success = inject_concatenate_for_safety_terms(
                                workflow=workflow,
                                target_node_id=node_id,
                                target_input_name="text",
                                source_connection=current_text,
                                safety_terms=all_additional_terms,
                                title=f"Safety Terms ({safety_level})"
                            )
                            
                            if success:
                                logger.info(f"Successfully injected StringConcatenate node for negative prompt in node {node_id}")
                                enhanced_count += 1
                            else:
                                logger.error(f"Failed to inject StringConcatenate node for node {node_id}")
                        else:
                            logger.info(f"No additional terms to add for node {node_id}")
                    
                    elif isinstance(current_text, str):
                        # It's a regular string, use existing logic
                        logger.info(f"Current negative prompt text: '{current_text}'")
                        
                        # Append additional terms if we have any
                        if all_additional_terms:
                            # Check if the terms are not already present
                            if all_additional_terms not in current_text:
                                # Append terms with proper separation
                                if current_text.strip():
                                    new_text = f"{current_text}, {all_additional_terms}"
                                else:
                                    new_text = all_additional_terms
                                
                                node_data["inputs"]["text"] = new_text
                                logger.info(f"Enhanced negative prompt in node {node_id}")
                                logger.info(f"New text (first 200 chars): '{new_text[:200]}...'")
                                enhanced_count += 1
                            else:
                                logger.info(f"Additional terms already present in node {node_id}")
                        else:
                            logger.info(f"No additional terms to add for node {node_id}")
                    else:
                        logger.warning(f"Unexpected text input type in node {node_id}: {type(current_text)}")
                else:
                    logger.warning(f"Node {node_id} is not a CLIPTextEncode, it's a {node_type}")
            else:
                logger.error(f"Node {node_id} not found in workflow!")
        
        logger.info(f"=== Enhancement complete. Enhanced {enhanced_count} negative prompts for {safety_level} safety ===")
        return enhanced_count
    
    def apply_sampler_parameters(self, workflow: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, int]:
        """
        Apply multiple parameters to sampler nodes
        
        Args:
            workflow: Workflow definition
            parameters: Dictionary of parameters to apply (e.g., {'cfg': 7.5, 'steps': 20})
            
        Returns:
            Dict with counts of updated nodes per parameter
        """
        # Define which parameters apply to which node types
        SAMPLER_PARAM_MAPPING = {
            'cfg': {'type': float, 'nodes': ['KSampler', 'KSamplerAdvanced', 'SamplerCustom']},
            'steps': {'type': int, 'nodes': ['KSampler', 'KSamplerAdvanced', 'SamplerCustom']},
            'denoise': {'type': float, 'nodes': ['KSampler', 'KSamplerAdvanced']},
            'sampler_name': {'type': str, 'nodes': ['KSampler', 'KSamplerAdvanced']},
            'scheduler': {'type': str, 'nodes': ['KSampler', 'KSamplerAdvanced']}
        }
        
        update_counts = {}
        
        for param_name, param_value in parameters.items():
            if param_name not in SAMPLER_PARAM_MAPPING:
                logger.warning(f"Unknown sampler parameter: {param_name}")
                continue
                
            param_config = SAMPLER_PARAM_MAPPING[param_name]
            target_nodes = param_config['nodes']
            param_type = param_config['type']
            
            # Value is already typed by parse_hidden_commands, but double-check
            try:
                typed_value = param_type(param_value)
            except (ValueError, TypeError):
                logger.error(f"Invalid value for {param_name}: {param_value}")
                continue
            
            # Apply to all matching nodes
            count = 0
            for node_data in workflow.values():
                if node_data.get("class_type") in target_nodes:
                    if "inputs" in node_data and param_name in node_data["inputs"]:
                        node_data["inputs"][param_name] = typed_value
                        count += 1
            
            update_counts[param_name] = count
            if count > 0:
                logger.info(f"Set {param_name}={typed_value} in {count} nodes")
        
        return update_counts
    
    def _resolve_model_paths(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve model paths in the workflow using the model path resolver
        
        Args:
            workflow: Workflow definition
            
        Returns:
            Modified workflow with resolved model paths
        """
        if not self.model_resolver:
            logger.debug("Model resolver not available, skipping path resolution")
            return workflow
            
        try:
            # Create a deep copy to avoid modifying the original
            import copy
            workflow_copy = copy.deepcopy(workflow)
            resolved_count = 0
            
            # Find all CheckpointLoaderSimple nodes
            for node_id, node_data in workflow_copy.items():
                if node_data.get("class_type") == "CheckpointLoaderSimple":
                    original_name = node_data.get("inputs", {}).get("ckpt_name", "")
                    
                    if original_name:
                        # Always try to resolve the model path
                        # ModelPathResolver will handle paths correctly
                        resolved_path = self.model_resolver.find_model(original_name)
                        
                        if resolved_path and resolved_path != original_name:
                            node_data["inputs"]["ckpt_name"] = resolved_path
                            logger.info(f"Node {node_id}: Resolved '{original_name}' -> '{resolved_path}'")
                            resolved_count += 1
                        else:
                            logger.warning(f"Node {node_id}: Could not resolve path for '{original_name}'")
            
            if resolved_count > 0:
                logger.info(f"Successfully resolved {resolved_count} model path(s)")
            else:
                logger.info("No model paths needed resolution")
                
            return workflow_copy
            
        except Exception as e:
            logger.error(f"Error resolving model paths: {e}")
            if MODEL_RESOLUTION_FALLBACK:
                logger.info("Using original workflow due to resolution error (fallback mode)")
                return workflow
            else:
                raise
    
    def prepare_workflow(self, workflow_name: str, prompt: str, aspect_ratio: str, mode: str, 
                        seed_mode: str = "random", custom_seed: Optional[int] = None,
                        safety_level: str = "research", input_negative_terms: str = "",
                        hidden_commands: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Prepare a workflow for execution
        
        Args:
            workflow_name: Name of the workflow
            prompt: Prompt text
            aspect_ratio: Aspect ratio
            mode: DEPRECATED — eco/fast removed in Session 65, unused
            seed_mode: Seed control mode ('random', 'standard', or 'fixed')
            custom_seed: Custom seed value for 'fixed' mode
            safety_level: Safety level ('research', 'youth', or 'kids')
            input_negative_terms: Additional negative terms from user input
            hidden_commands: Hidden commands parsed from the prompt
            
        Returns:
            Dictionary with workflow, status_updates, used_seed, and success flag
        """
        input_negative_terms = normalize_negative_terms(input_negative_terms)

        # Load workflow
        workflow = self.load_workflow(workflow_name)
        if not workflow:
            return {"success": False, "error": f"Workflow '{workflow_name}' nicht gefunden."}
        
        # Remove Note nodes - they are GUI-only and not executable by ComfyUI
        nodes_to_remove = []
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get("class_type") == "Note":
                nodes_to_remove.append(node_id)
        
        for node_id in nodes_to_remove:
            del workflow[node_id]
            logger.info(f"Removed Note node {node_id} from workflow")
        
        status_updates = []
        
        # DEPRECATED: eco/fast mode switching removed in Session 65. Dead code, pending removal.
        if mode == 'eco':
            workflow, mode_updates = self.switch_to_eco_mode(workflow)
            status_updates.extend(mode_updates)
        elif mode == 'fast':
            workflow, mode_updates = self.switch_to_fast_mode(workflow)
            status_updates.extend(mode_updates)
        
        # Inject prompt
        if not self.inject_prompt(workflow, prompt):
            return {"success": False, "error": "Workflow hat keinen vorgesehenen Prompt-Eingabeknoten."}
        
        # Update dimensions and apply seed control
        self.update_dimensions(workflow, aspect_ratio)
        used_seed = self.apply_seed_control(workflow, seed_mode, custom_seed)
        
        # Apply safety level if safety node exists (failsafe)
        safety_applied = self.apply_safety_level(workflow, safety_level)
        if safety_applied and safety_level != "research":
            status_updates.append(f"Sicherheitsstufe '{safety_level}' aktiviert.")
        
        # Enhance negative prompts if we have any terms to add
        # (DEFAULT_NEGATIVE_TERMS, input_negative_terms, or safety terms)
        should_enhance = (
            (DEFAULT_NEGATIVE_TERMS and DEFAULT_NEGATIVE_TERMS.strip()) or
            (input_negative_terms) or
            safety_level in ["kids", "youth"]
        )
        
        if should_enhance:
            logger.info(f"Enhancing negative prompts (safety_level: {safety_level}, has_input_terms: {bool(input_negative_terms)})")
            enhanced_count = self.enhance_negative_prompts(workflow, safety_level, input_negative_terms)
            if enhanced_count > 0:
                status_messages = []
                
                # Add messages based on what was added
                if DEFAULT_NEGATIVE_TERMS and DEFAULT_NEGATIVE_TERMS.strip():
                    status_messages.append("Standard-Negativ-Begriffe")
                
                if input_negative_terms:
                    status_messages.append("benutzerdefinierte Negativ-Begriffe")
                
                if safety_level == "kids":
                    status_messages.append("Kindersicherheitsbegriffe")
                elif safety_level == "youth":
                    status_messages.append("Jugendschutzbegriffe")
                
                if status_messages:
                    message = f"Negative Prompts wurden erweitert mit: {', '.join(status_messages)} ({enhanced_count} Nodes)."
                    status_updates.append(message)
                    logger.info(f"Enhanced {enhanced_count} negative prompts")
            else:
                logger.warning("Negative prompt enhancement was requested but no prompts were enhanced!")
        
        # Resolve model paths if enabled
        if ENABLE_MODEL_PATH_RESOLUTION:
            try:
                workflow = self._resolve_model_paths(workflow)
                logger.info("Model paths resolved successfully")
            except Exception as e:
                logger.warning(f"Model path resolution failed: {e}")
                if not MODEL_RESOLUTION_FALLBACK:
                    return {"success": False, "error": f"Model-Pfad-Auflösung fehlgeschlagen: {str(e)}"}
                # If fallback is enabled, continue with original workflow
                status_updates.append("Warnung: Model-Pfad-Auflösung fehlgeschlagen, verwende Original-Pfade.")
        
        # Apply hidden commands at the end (these override UI settings)
        if hidden_commands:
            logger.info(f"Applying hidden commands: {hidden_commands}")
            
            # Handle seed override
            if 'seed' in hidden_commands:
                # Override the seed that was set earlier
                used_seed = self.apply_seed_control(workflow, 'fixed', hidden_commands['seed'])
                status_updates.append(f"Seed durch Hidden Command auf {used_seed} überschrieben.")
            
            # Apply other sampler parameters
            sampler_params = {k: v for k, v in hidden_commands.items() 
                            if k not in ['seed', 'notranslate']}  # Exclude already processed
            
            if sampler_params:
                update_counts = self.apply_sampler_parameters(workflow, sampler_params)
                for param, count in update_counts.items():
                    if count > 0:
                        status_updates.append(f"Parameter '{param}' durch Hidden Command in {count} Nodes gesetzt.")
        
        return {
            "success": True,
            "workflow": workflow,
            "status_updates": status_updates,
            "used_seed": used_seed
        }


# Create a singleton instance
workflow_logic_service = WorkflowLogicService()
