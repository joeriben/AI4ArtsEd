"""
Legacy workflows: what a complete ComfyUI workflow JSON needs before the
websocket client submits it, when a chunk runs with execution_mode
"legacy_workflow" (schemas/engine/backend_router.py, _process_legacy_workflow):
the prompt injected by its input_mappings or by node title, and every
prompt-interception node pointed at the one Stage-2 model.

Until 2026-10-10 this module was a service with a door to ComfyUI of its own
(submit over aiohttp, poll /history, download /view) that nothing called: the
router borrowed the two helpers below through LegacyWorkflowService.__new__
and ran submission and waiting through the websocket client, which holds the
GPU lease. The door went; the two helpers stayed, as functions.
"""
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


def replace_llm_models(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Point every prompt-interception node at STAGE2_INTERCEPTION_MODEL.

    These nodes ARE the Prompt Interception -- an old workflow's class_type
    says so. Until 2026-08-17 they read a field of their own,
    STAGE4_LEGACY_MODEL, which let one operation run on two different models
    depending on which surface asked for it. The field is gone; there is one
    model for Prompt Interception.

    Args:
        workflow: Workflow definition

    Returns:
        Modified workflow
    """
    try:
        # Since 2026-09-12 the node calls the DevServer (/api/chat/proxy)
        # and names the role; the DevServer resolves the setting and
        # applies the fallback the settings page regulates.
        role_model = "platform/STAGE2_INTERCEPTION_MODEL"

        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'ai4artsed_prompt_interception':
                old_model = node_data.get('inputs', {}).get('model', 'unknown')
                node_data['inputs']['model'] = role_model
                logger.info(f"[LEGACY-LLM] Node {node_id}: {old_model} → {role_model}")

        return workflow

    except Exception as e:
        logger.error(f"[LEGACY-SERVICE] Failed to replace LLM models: {e}")
        return workflow  # Continue with original


def inject_prompt(
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
