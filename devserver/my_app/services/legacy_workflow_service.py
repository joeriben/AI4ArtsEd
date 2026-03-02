"""
Legacy Workflow Service - Handles complete ComfyUI workflow execution

This service encapsulates legacy workflow logic:
- Direct ComfyUI API access
- Prompt injection using title-based node search
- LLM model name replacement
- Polling until completion
- Downloading ALL media outputs

Architecture: Separates legacy workflow concerns from Backend-Router
"""
import logging
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LegacyWorkflowService:
    """Service for executing legacy ComfyUI workflows"""

    def __init__(self, comfyui_base_url: Optional[str] = None):
        """
        Initialize Legacy Workflow Service

        Args:
            comfyui_base_url: Optional override. If None, determined by config.
        """
        if comfyui_base_url:
            self.base_url = comfyui_base_url
        else:
            try:
                from config import COMFYUI_PORT
                self.base_url = f"http://127.0.0.1:{COMFYUI_PORT}"
            except ImportError:
                self.base_url = "http://127.0.0.1:17804"
            logger.info(f"[LEGACY-SERVICE] Using ComfyUI at {self.base_url}")

        self.timeout = aiohttp.ClientTimeout(total=300)  # 5 min for long workflows

        # Initialize ComfyUI Manager for auto-recovery
        from my_app.services.comfyui_manager import get_comfyui_manager
        self.comfyui_manager = get_comfyui_manager()

    async def execute_workflow(
        self,
        workflow: Dict[str, Any],
        prompt: str,
        chunk_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute complete legacy workflow: submit → poll → download

        Args:
            workflow: ComfyUI workflow definition
            prompt: User prompt to inject
            chunk_config: Chunk configuration (with prompt_injection settings)

        Returns:
            {
                'media_files': List[bytes],  # Downloaded binary data
                'prompt_id': str,
                'workflow_json': Dict,
                'outputs_metadata': List[Dict]  # Metadata for each file
            }
        """
        try:
            logger.info(f"[DEBUG-PROMPT] Legacy service received prompt: '{prompt[:200]}...'" if prompt else f"[DEBUG-PROMPT] ⚠️ Legacy service received EMPTY prompt: {repr(prompt)}")

            # Step 1: Replace LLM model names
            workflow = self._replace_llm_models(workflow)

            # Step 2: Inject prompt
            logger.info(f"[DEBUG-PROMPT] Starting prompt injection...")
            workflow, injection_success = self._inject_prompt(workflow, prompt, chunk_config)
            if not injection_success:
                logger.warning("[LEGACY-SERVICE] Prompt injection failed, continuing anyway")

            # Step 2.5: Ensure ComfyUI is available
            logger.info("[LEGACY-SERVICE] Ensuring ComfyUI is available...")
            if not await self.comfyui_manager.ensure_comfyui_available():
                raise Exception("Failed to start ComfyUI - cannot submit workflow")

            # Step 3: Submit workflow
            prompt_id = await self._submit_workflow(workflow)
            if not prompt_id:
                raise Exception("Failed to submit workflow to ComfyUI")

            logger.info(f"[LEGACY-SERVICE] Workflow submitted: {prompt_id}")

            # Step 4: Poll until complete
            outputs = await self._poll_until_complete(prompt_id, timeout=300)
            if not outputs:
                raise Exception(f"Workflow {prompt_id} did not complete or has no outputs")

            logger.info(f"[LEGACY-SERVICE] Workflow completed with {len(outputs)} output nodes")

            # Step 5: Download ALL media
            media_files, outputs_metadata = await self._download_all_media(outputs)

            logger.info(f"[LEGACY-SERVICE] Downloaded {len(media_files)} media file(s)")

            return {
                'media_files': media_files,
                'prompt_id': prompt_id,
                'workflow_json': workflow,
                'outputs_metadata': outputs_metadata
            }

        except Exception as e:
            logger.error(f"[LEGACY-SERVICE] Workflow execution failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _replace_llm_models(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace LLM model names with STAGE4_LEGACY_MODEL from config

        Args:
            workflow: Workflow definition

        Returns:
            Modified workflow
        """
        try:
            from config import STAGE4_LEGACY_MODEL

            for node_id, node_data in workflow.items():
                if node_data.get('class_type') == 'ai4artsed_prompt_interception':
                    old_model = node_data.get('inputs', {}).get('model', 'unknown')
                    node_data['inputs']['model'] = STAGE4_LEGACY_MODEL
                    logger.info(f"[LEGACY-LLM] Node {node_id}: {old_model} → {STAGE4_LEGACY_MODEL}")

            return workflow

        except Exception as e:
            logger.error(f"[LEGACY-SERVICE] Failed to replace LLM models: {e}")
            return workflow  # Continue with original

    def _inject_prompt(
        self,
        workflow: Dict[str, Any],
        prompt: str,
        chunk_config: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Inject prompt using input_mappings (modern) or title-based search (legacy fallback)

        Args:
            workflow: Workflow definition
            prompt: Prompt text to inject
            chunk_config: Chunk config with input_mappings or legacy prompt_injection settings

        Returns:
            (modified_workflow, success_bool)
        """
        try:
            # Method 0: Use input_mappings if available (modern approach, consistent with input_image)
            input_mappings = chunk_config.get('input_mappings', {})
            prompt_mapping = input_mappings.get('prompt')

            if prompt_mapping:
                node_id = prompt_mapping.get('node_id')
                field = prompt_mapping.get('field', 'inputs.prompt')

                if node_id and node_id in workflow:
                    # Parse field path (e.g., "inputs.prompt" → ["inputs", "prompt"])
                    field_parts = field.split('.')
                    target = workflow[node_id]

                    # Navigate to parent object
                    for part in field_parts[:-1]:
                        target = target.setdefault(part, {})

                    # Inject prompt
                    target[field_parts[-1]] = prompt
                    logger.info(f"[LEGACY-INJECT] ✓ Injected prompt into node {node_id}.{field} via input_mappings")
                    logger.info(f"[LEGACY-INJECT] ✓ Prompt preview: '{prompt[:100]}...'")
                    return workflow, True
                else:
                    logger.warning(f"[LEGACY-INJECT] input_mappings specified node_id={node_id} but not found in workflow")

            # Fallback: Get prompt_injection config from legacy_config
            legacy_config = chunk_config.get('legacy_config', {})
            prompt_injection = legacy_config.get('prompt_injection', {})
            target_title = prompt_injection.get('target_title', 'ai4artsed_text_prompt')
            fallback_node_id = prompt_injection.get('fallback_node_id')
            fallback_field = prompt_injection.get('fallback_field', 'value')

            logger.info(f"[LEGACY-INJECT] No input_mappings found, searching for node with title '{target_title}'")
            logger.info(f"[DEBUG-PROMPT] Prompt to inject: '{prompt[:200]}...'" if prompt else f"[DEBUG-PROMPT] ⚠️ Prompt is EMPTY: {repr(prompt)}")

            # Method 1: Search by _meta.title (preferred)
            node_titles_found = []
            for node_id, node_data in workflow.items():
                meta_title = node_data.get('_meta', {}).get('title')
                if meta_title:
                    node_titles_found.append(f"{node_id}:'{meta_title}'")
                if meta_title == target_title:
                    inputs = node_data.get('inputs', {})

                    # Try 'value' field first
                    if 'value' in inputs:
                        node_data['inputs']['value'] = prompt
                        logger.info(f"[LEGACY-INJECT] ✓ Injected prompt into node {node_id}.inputs.value (title match)")
                        logger.info(f"[LEGACY-INJECT] ✓ Prompt preview: '{prompt[:100]}...'")
                        return workflow, True

                    # Try 'text' field
                    elif 'text' in inputs:
                        node_data['inputs']['text'] = prompt
                        logger.info(f"[LEGACY-INJECT] ✓ Injected prompt into node {node_id}.inputs.text (title match)")
                        logger.info(f"[LEGACY-INJECT] ✓ Prompt preview: '{prompt[:100]}...'")
                        return workflow, True

            # Method 2: Fallback to node_id if configured
            logger.info(f"[DEBUG-PROMPT] Title match failed. Available node titles: {', '.join(node_titles_found[:10])}")
            logger.info(f"[DEBUG-PROMPT] Trying fallback: node_id={fallback_node_id}, field={fallback_field}")

            if fallback_node_id and fallback_node_id in workflow:
                node_data = workflow[fallback_node_id]
                inputs = node_data.get('inputs', {})
                logger.info(f"[DEBUG-PROMPT] Fallback node {fallback_node_id} has fields: {list(inputs.keys())}")

                if fallback_field in inputs:
                    logger.info(f"[DEBUG-PROMPT] Before injection: node {fallback_node_id}.inputs.{fallback_field} = '{inputs.get(fallback_field)}'")
                    node_data['inputs'][fallback_field] = prompt
                    logger.info(f"[DEBUG-PROMPT] After injection: node {fallback_node_id}.inputs.{fallback_field} = '{node_data['inputs'][fallback_field][:100]}...'")
                    logger.info(f"[LEGACY-INJECT] ✓ Injected prompt into fallback node {fallback_node_id}.inputs.{fallback_field}")
                    logger.info(f"[LEGACY-INJECT] ✓ Prompt preview: '{prompt[:100]}...'")
                    return workflow, True

            logger.error(f"[LEGACY-INJECT] ✗ Could not find injection target")
            return workflow, False

        except Exception as e:
            logger.error(f"[LEGACY-INJECT] Error: {e}")
            return workflow, False

    async def _submit_workflow(self, workflow: Dict[str, Any]) -> Optional[str]:
        """
        Submit workflow to ComfyUI

        Args:
            workflow: Workflow definition

        Returns:
            prompt_id if successful, None otherwise
        """
        try:
            import uuid

            payload = {
                "prompt": workflow,
                "client_id": str(uuid.uuid4())
            }

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/prompt",
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[LEGACY-SUBMIT] Failed: {response.status} - {error_text}")
                        return None

                    data = await response.json()
                    prompt_id = data.get("prompt_id")

                    if not prompt_id:
                        logger.error("[LEGACY-SUBMIT] No prompt_id in response")
                        return None

                    logger.info(f"[LEGACY-SUBMIT] ✓ Submitted: {prompt_id}")
                    return prompt_id

        except Exception as e:
            logger.error(f"[LEGACY-SUBMIT] Error: {e}")
            return None

    async def _poll_until_complete(
        self,
        prompt_id: str,
        timeout: int = 300,
        poll_interval: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        Poll ComfyUI history until workflow completes

        Args:
            prompt_id: Workflow prompt ID
            timeout: Max seconds to wait
            poll_interval: Seconds between polls

        Returns:
            outputs dict if completed, None otherwise
        """
        start_time = asyncio.get_event_loop().time()
        logger.info(f"[LEGACY-POLL] Starting poll for {prompt_id} (timeout={timeout}s)")

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.error(f"[LEGACY-POLL] Timeout after {timeout}s for {prompt_id}")
                return None

            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(
                        f"{self.base_url}/history/{prompt_id}"
                    ) as response:
                        if response.status == 404:
                            # Not ready yet
                            await asyncio.sleep(poll_interval)
                            continue

                        if response.status != 200:
                            logger.error(f"[LEGACY-POLL] Error: {response.status}")
                            await asyncio.sleep(poll_interval)
                            continue

                        history = await response.json()

                        if prompt_id not in history:
                            logger.debug(f"[LEGACY-POLL] prompt_id not in history yet, keys: {list(history.keys())[:5]}")
                            await asyncio.sleep(poll_interval)
                            continue

                        session_data = history[prompt_id]
                        outputs = session_data.get("outputs", {})
                        status = session_data.get("status", {})

                        # Debug: Log what we got
                        logger.info(f"[LEGACY-POLL] Status: {status.get('status_str', 'unknown')}, outputs: {list(outputs.keys()) if outputs else 'empty'}")

                        if outputs:
                            logger.info(f"[LEGACY-POLL] ✓ Completed after {elapsed:.1f}s")
                            return outputs

                        # Check if workflow failed
                        if status.get("status_str") == "error":
                            logger.error(f"[LEGACY-POLL] Workflow failed: {status}")
                            return None

                        await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"[LEGACY-POLL] Error: {e}")
                await asyncio.sleep(poll_interval)

    async def _download_all_media(
        self,
        outputs: Dict[str, Any]
    ) -> Tuple[List[bytes], List[Dict[str, Any]]]:
        """
        Download ALL media files from ComfyUI outputs (1:1 from legacy server)

        Args:
            outputs: Outputs dict from ComfyUI history

        Returns:
            (media_files, metadata_list)
        """
        media_files = []
        metadata_list = []

        logger.info(f"[LEGACY-DOWNLOAD] Processing {len(outputs)} output nodes")
        logger.info(f"[LEGACY-DOWNLOAD] Output node IDs: {list(outputs.keys())}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                for node_id, output in outputs.items():
                    logger.info(f"[LEGACY-DOWNLOAD] Node {node_id} output keys: {list(output.keys())}")
                    # Handle images
                    if output.get("images"):
                        for idx, img in enumerate(output["images"]):
                            try:
                                # Build URL (exact legacy format)
                                url = f"{self.base_url}/view?filename={img['filename']}&subfolder={img.get('subfolder', '')}&type={img.get('type', 'output')}"

                                async with session.get(url) as response:
                                    if response.status == 200:
                                        file_data = await response.read()
                                        media_files.append(file_data)
                                        metadata_list.append({
                                            'node_id': node_id,
                                            'type': 'image',
                                            'filename': img['filename'],
                                            'subfolder': img.get('subfolder', ''),
                                            'index': idx
                                        })
                                        logger.info(f"[LEGACY-DOWNLOAD] ✓ Image from node {node_id}: {img['filename']}")
                                    else:
                                        logger.error(f"[LEGACY-DOWNLOAD] Failed to download image: {response.status}")

                            except Exception as e:
                                logger.error(f"[LEGACY-DOWNLOAD] Error downloading image: {e}")

                    # Handle audio
                    if output.get("audio"):
                        for idx, aud in enumerate(output["audio"]):
                            try:
                                url = f"{self.base_url}/view?filename={aud['filename']}&subfolder={aud.get('subfolder', '')}&type={aud.get('type', 'output')}"

                                async with session.get(url) as response:
                                    if response.status == 200:
                                        file_data = await response.read()
                                        media_files.append(file_data)
                                        metadata_list.append({
                                            'node_id': node_id,
                                            'type': 'audio',
                                            'filename': aud['filename'],
                                            'subfolder': aud.get('subfolder', ''),
                                            'index': idx
                                        })
                                        logger.info(f"[LEGACY-DOWNLOAD] ✓ Audio from node {node_id}: {aud['filename']}")

                            except Exception as e:
                                logger.error(f"[LEGACY-DOWNLOAD] Error downloading audio: {e}")

                    # Handle videos
                    if output.get("videos"):
                        for idx, vid in enumerate(output["videos"]):
                            try:
                                url = f"{self.base_url}/view?filename={vid['filename']}&subfolder={vid.get('subfolder', '')}&type={vid.get('type', 'output')}"

                                async with session.get(url) as response:
                                    if response.status == 200:
                                        file_data = await response.read()
                                        media_files.append(file_data)
                                        metadata_list.append({
                                            'node_id': node_id,
                                            'type': 'video',
                                            'filename': vid['filename'],
                                            'subfolder': vid.get('subfolder', ''),
                                            'index': idx
                                        })
                                        logger.info(f"[LEGACY-DOWNLOAD] ✓ Video from node {node_id}: {vid['filename']}")
                                    else:
                                        logger.error(f"[LEGACY-DOWNLOAD] Failed to download video: {response.status}")

                            except Exception as e:
                                logger.error(f"[LEGACY-DOWNLOAD] Error downloading video: {e}")

                    # Handle gifs (alternative video output format used by some nodes)
                    if output.get("gifs"):
                        for idx, gif in enumerate(output["gifs"]):
                            try:
                                url = f"{self.base_url}/view?filename={gif['filename']}&subfolder={gif.get('subfolder', '')}&type={gif.get('type', 'output')}"

                                async with session.get(url) as response:
                                    if response.status == 200:
                                        file_data = await response.read()
                                        media_files.append(file_data)
                                        metadata_list.append({
                                            'node_id': node_id,
                                            'type': 'video',
                                            'filename': gif['filename'],
                                            'subfolder': gif.get('subfolder', ''),
                                            'index': idx
                                        })
                                        logger.info(f"[LEGACY-DOWNLOAD] ✓ Video/GIF from node {node_id}: {gif['filename']}")
                                    else:
                                        logger.error(f"[LEGACY-DOWNLOAD] Failed to download video/gif: {response.status}")

                            except Exception as e:
                                logger.error(f"[LEGACY-DOWNLOAD] Error downloading video/gif: {e}")

                    # Handle text outputs (save as metadata, not binary)
                    if output.get("text"):
                        metadata_list.append({
                            'node_id': node_id,
                            'type': 'text',
                            'content': "\n".join(output["text"])
                        })

            return media_files, metadata_list

        except Exception as e:
            logger.error(f"[LEGACY-DOWNLOAD] Error: {e}")
            return media_files, metadata_list


# Singleton instance
_legacy_workflow_service: Optional[LegacyWorkflowService] = None


def get_legacy_workflow_service() -> LegacyWorkflowService:
    """Get singleton Legacy Workflow Service instance"""
    global _legacy_workflow_service
    if _legacy_workflow_service is None:
        _legacy_workflow_service = LegacyWorkflowService()
    return _legacy_workflow_service
