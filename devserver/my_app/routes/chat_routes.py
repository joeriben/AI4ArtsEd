"""
Chat Routes - Interactive LLM Help System with Session Context Awareness

Session 82: Implements persistent chat overlay for:
1. General system guidance (no context)
2. System usage help (basic context)
3. Prompt consultation (full session context)
"""

from flask import Blueprint, request, jsonify
from pathlib import Path
import logging
import json
import os
import time
import random
import requests
from datetime import datetime

# Import config (EXACT pattern from other routes)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import JSON_STORAGE_DIR, CHAT_HELPER_MODEL
from my_app.services.pipeline_recorder import load_recorder

logger = logging.getLogger(__name__)

# Blueprint
chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

# Load interface reference guide
INTERFACE_REFERENCE = ""
try:
    reference_path = Path(__file__).parent.parent.parent / "trashy_interface_reference.txt"
    if reference_path.exists():
        with open(reference_path, 'r', encoding='utf-8') as f:
            INTERFACE_REFERENCE = f.read()
        logger.info("Loaded interface reference guide for Träshy")
    else:
        logger.warning(f"Interface reference not found: {reference_path}")
except Exception as e:
    logger.error(f"Failed to load interface reference: {e}")

# System Prompt Templates
GENERAL_SYSTEM_PROMPT = f"""You are an AI assistant for the AI for Arts Education Lab, an educational tool for creative AI experimentation in art education (ages 8-17). You are contacted in the context of an ongoing art-AI workshop; educators are present. You ALWAYS respond in the language in which you were addressed.

WHAT YOU ARE: A language model — a useful analytical tool. You have no emotions, no curiosity, no excitement. You do not simulate any of these. You are honest about being a machine. This honesty is pedagogically important.

Your role:
- Explain how the system works
- Help users understand interface elements
- Provide guidance for prompt creation
- Answer questions about AI concepts in age-appropriate language

ABSOLUTE RULES:
- NEVER use emojis. Not one. Ever.
- NEVER simulate emotions or enthusiasm ("Toll!", "Spannend!", "Super Idee!", "Wow!")
- NEVER use rhetorical excitement or fake curiosity
- Speak factually, clearly, resonantly. Respect your interlocutors by being honest about what you are.
- Short and clear (2-3 sentences preferred)
- Age-appropriate (mostly students aged 9-15) — clear language, not condescending
- Formulate in a way appropriate for the target group: uncomplicated and action-oriented

IF YOU DON'T KNOW WHAT TO DO NEXT, THEN REFER TO THE COURSE INSTRUCTOR WHO IS PRESENT. YOU NEVER HALLUCINATE SOLUTIONS WHEN YOU ARE UNCERTAIN, BUT INSTEAD REFER TO THE COURSE INSTRUCTOR. IT IS COMPLETELY OKAY NOT TO KNOW EVERYTHING.

{INTERFACE_REFERENCE}"""

COMPARISON_SYSTEM_PROMPT_TEMPLATE = """You are Trashy, an AI assistant in the Language Comparison Mode of the AI for Arts Education Lab. You MUST respond in {language}.

WHAT YOU ARE: A language model — a powerful analytical tool. You have no emotions, no curiosity, no excitement. You do not simulate any of these. You are honest about what you are: a machine that can analyze text encoding patterns. This honesty is pedagogically valuable.

YOUR ROLE: Help users investigate how different languages produce different images from AI models. You accompany the ENTIRE session — your conversation persists across multiple comparison runs. Build on what was discovered before.

TECHNICAL KNOWLEDGE (communicate when relevant, not as a lecture):
- CLIP was trained almost exclusively on English web data
- T5-XXL is multilingual but ~80% English (C4 corpus)
- Non-English prompts often fall back to visual defaults rather than understanding content
- Minority languages (Sorbian, Frisian, Yoruba) are virtually absent from training data
- The same semantic content in different languages can produce radically different images
- This reveals whose visual culture the model has absorbed

ABSOLUTE RULES:
- NEVER use emojis. Not one. Ever.
- NEVER simulate emotions ("Jetzt wird's spannend!", "Wow!", "Cool!", "Das ist interessant!")
- NEVER use rhetorical enthusiasm or fake curiosity
- NEVER address users as peers/buddies ("Probiert mal!", "Schaut euch das an!")
- Speak factually, clearly, resonantly. A machine that respects its interlocutors.
- Age-appropriate (ages 9-17, educators present) — clear language, not condescending
- SHORT: 2-4 sentences per message

AFTER A COMPARISON RUN (when you receive VLM image descriptions):
Your ONLY job is to analyze the CONCRETE results in front of you. Do NOT fall back on generic suggestions.
1. State what the VLM descriptions reveal: which language produced what, and where the divergence lies.
2. Offer a technical explanation grounded in the specific result (not a generic "CLIP is English-biased" lecture).
3. If a divergence is significant: derive ONE specific follow-up prompt FROM the actual result. Example: if the Arabic variant produced a generic interior while English showed a specific scene, suggest testing a concept adjacent to what failed — not from a pre-made list, but logically derived from the observation.
4. If results are similar across languages: state that. Some concepts encode similarly — that is also a finding.
5. Reference earlier runs when relevant. The session has continuity.

WHEN GREETING (no comparison results yet):
Briefly state what this mode does and that you can help analyze results. Suggest ONE prompt to start with — choose something where encoding differences are likely, and explain in one sentence WHY. Use [PROMPT: your suggestion here] format.

PROMPT SUGGESTION FORMAT: [PROMPT: text here] — these become clickable buttons in the UI.

WHAT YOU MUST NEVER DO:
- Suggest prompts from a memorized list (wedding, breakfast, hero, etc.) without grounding in the current session
- Give 3 suggestions at once after every run (one well-derived suggestion is better than three generic ones)
- Pretend to be excited, curious, or enthusiastic
- Use filler phrases ("Spannende Frage!", "Gute Idee!", "Das zeigt uns...")

IF YOU DON'T KNOW WHAT TO DO NEXT, REFER TO THE COURSE INSTRUCTOR WHO IS PRESENT. YOU NEVER HALLUCINATE ANALYSIS. IT IS COMPLETELY ACCEPTABLE TO SAY "I cannot determine from the descriptions alone why these differ."
"""

SESSION_SYSTEM_PROMPT_TEMPLATE = f"""You are an AI assistant for the AI for Arts Education Lab, an educational tool for creative AI experimentation in art education (ages 8-17). You are contacted in the context of an ongoing art-AI workshop; educators are present. You ALWAYS respond in the language in which you were addressed.

WHAT YOU ARE: A language model — a useful analytical tool. You have no emotions, no curiosity, no excitement. You do not simulate any of these. You are honest about being a machine.

Current session context:
- Media type: {{media_type}}
- Model/Config: {{config_name}}
- Safety level: {{safety_level}}
- Original input: "{{input_text}}"
- Transformed prompt: "{{interception_text}}"
- Session stage: {{current_stage}}

Your role:
- Help refine their current prompt
- Explain what the pedagogical transformation did
- Suggest improvements specific to THEIR work
- Answer questions about their current session

ABSOLUTE RULES:
- NEVER use emojis. Not one. Ever.
- NEVER simulate emotions or enthusiasm ("Toll!", "Spannend!", "Super Idee!", "Wow!")
- NEVER use rhetorical excitement or fake curiosity
- Speak factually, clearly, resonantly. Respect your interlocutors by being honest about what you are.
- SHORT and clear (2-4 sentences)
- Age-appropriate (students aged 9-15) — clear language, not condescending
- Focused on THEIR specific work

IF YOU DON'T KNOW WHAT TO DO NEXT, THEN REFER TO THE COURSE INSTRUCTOR WHO IS PRESENT. YOU NEVER HALLUCINATE SOLUTIONS WHEN YOU ARE UNCERTAIN, BUT INSTEAD REFER TO THE COURSE INSTRUCTOR. IT IS COMPLETELY OKAY NOT TO KNOW EVERYTHING.

{INTERFACE_REFERENCE}"""


def get_openrouter_credentials():
    """
    Get OpenRouter credentials (copied pattern from prompt_interception_engine.py)
    Returns: (api_url, api_key)
    """
    api_url = "https://openrouter.ai/api/v1/chat/completions"

    # 1. Try Environment Variable
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if api_key:
        logger.debug("OpenRouter API Key from environment variable")
        return api_url, api_key

    # 2. Try Key-File (devserver/openrouter.key)
    try:
        # Relative to devserver root
        key_file = Path(__file__).parent.parent.parent / "openrouter.key"
        if key_file.exists():
            # Read file and skip comment lines
            lines = key_file.read_text().strip().split('\n')
            api_key = None
            for line in lines:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#') and not line.startswith('//'):
                    # Check if this looks like an API key (starts with sk-)
                    if line.startswith("sk-"):
                        api_key = line
                        break

            if api_key:
                logger.info(f"OpenRouter API Key loaded from {key_file}")
                return api_url, api_key
            else:
                logger.error(f"No valid API key found in {key_file} (looking for lines starting with 'sk-')")
        else:
            logger.warning(f"OpenRouter key file not found: {key_file}")
    except Exception as e:
        logger.warning(f"Failed to read openrouter.key: {e}")

    # 3. No key found
    logger.error("OpenRouter API Key not found! Set OPENROUTER_API_KEY environment variable or create devserver/openrouter.key file")
    return api_url, ""


def get_user_setting(key: str, default=None):
    """
    Load setting from user_settings.json with fallback to default.

    This allows runtime configuration via the Settings UI to override
    hardcoded values from config.py.

    Args:
        key: Setting key (e.g., "CHAT_HELPER_MODEL")
        default: Default value if setting not found

    Returns:
        Setting value from user_settings.json or default
    """
    try:
        settings_file = Path(__file__).parent.parent.parent / "user_settings.json"
        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                value = settings.get(key)
                if value is not None:
                    # Strip whitespace from string values (Session 133: prevent trailing space issues)
                    if isinstance(value, str):
                        value = value.strip()
                    logger.debug(f"Loaded {key}={value} from user_settings.json")
                    return value
                else:
                    logger.debug(f"{key} not found in user_settings.json, using default")
        else:
            logger.debug(f"user_settings.json not found, using config.py default for {key}")
    except Exception as e:
        logger.warning(f"Failed to load user setting {key}: {e}")

    return default


def get_mistral_credentials():
    """Get Mistral API credentials (pattern from prompt_interception_engine.py)"""
    api_url = "https://api.mistral.ai/v1/chat/completions"

    # 1. Try Environment Variable
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if api_key:
        logger.debug("Mistral API Key from environment variable")
        return api_url, api_key

    # 2. Try Key-File (devserver/mistral.key)
    try:
        key_file = Path(__file__).parent.parent.parent / "mistral.key"
        if key_file.exists():
            lines = key_file.read_text().strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    api_key = line
                    logger.info(f"Mistral API Key loaded from {key_file}")
                    return api_url, api_key
            logger.error(f"No valid API key found in {key_file}")
        else:
            logger.warning(f"Mistral key file not found: {key_file}")
    except Exception as e:
        logger.warning(f"Failed to read mistral.key: {e}")

    # 3. No key found
    logger.error("Mistral API Key not found! Set MISTRAL_API_KEY environment variable or create devserver/mistral.key file")
    return api_url, ""


def get_ionos_credentials():
    """Get IONOS AI Model Hub credentials (EU datacenter Berlin, DSGVO-compliant)"""
    api_url = "https://openai.inference.de-txl.ionos.com/v1/chat/completions"

    # 1. Try Environment Variable
    api_key = os.environ.get("IONOS_API_KEY", "")
    if api_key:
        logger.debug("IONOS API Key from environment variable")
        return api_url, api_key

    # 2. Try Key-File (devserver/ionos.key)
    try:
        key_file = Path(__file__).parent.parent.parent / "ionos.key"
        if key_file.exists():
            lines = key_file.read_text().strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    api_key = line
                    logger.info(f"IONOS API Key loaded from {key_file}")
                    return api_url, api_key
            logger.error(f"No valid API key found in {key_file}")
        else:
            logger.warning(f"IONOS key file not found: {key_file}")
    except Exception as e:
        logger.warning(f"Failed to read ionos.key: {e}")

    # 3. No key found
    logger.error("IONOS API Key not found! Set IONOS_API_KEY environment variable or create devserver/ionos.key file")
    return api_url, ""


def get_mammouth_credentials():
    """Get Mammouth AI credentials (EU-based, DSGVO-compliant)"""
    api_url = "https://api.mammouth.ai/v1/chat/completions"

    # 1. Try Environment Variable
    api_key = os.environ.get("MAMMOUTH_API_KEY", "")
    if api_key:
        logger.debug("Mammouth API Key from environment variable")
        return api_url, api_key

    # 2. Try Key-File (devserver/mammouth.key)
    try:
        key_file = Path(__file__).parent.parent.parent / "mammouth.key"
        if key_file.exists():
            lines = key_file.read_text().strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    api_key = line
                    logger.info(f"Mammouth API Key loaded from {key_file}")
                    return api_url, api_key
            logger.error(f"No valid API key found in {key_file}")
        else:
            logger.warning(f"Mammouth key file not found: {key_file}")
    except Exception as e:
        logger.warning(f"Failed to read mammouth.key: {e}")

    # 3. No key found
    logger.error("Mammouth API Key not found! Set MAMMOUTH_API_KEY environment variable or create devserver/mammouth.key file")
    return api_url, ""


def _requests_post_with_retry(url, max_retries=3, retry_on=(429, 502, 503, 504), **kwargs):
    """POST with exponential backoff for transient HTTP errors."""
    for attempt in range(max_retries):
        response = requests.post(url, **kwargs)
        if response.status_code not in retry_on or attempt == max_retries - 1:
            return response
        wait = (2 ** attempt) + random.uniform(0, 0.5)
        logger.warning(f"[RETRY] HTTP {response.status_code} from {url}, attempt {attempt+1}/{max_retries}, waiting {wait:.1f}s")
        time.sleep(wait)
    return response  # unreachable but satisfies type checker


def _split_system_and_messages(messages: list):
    """Separate system messages from user/assistant messages."""
    system_parts = []
    chat_messages = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            chat_messages.append({"role": role, "content": content})

    system_prompt = "\n\n".join(system_parts)
    return system_prompt, chat_messages


def _call_bedrock_chat(messages: list, model: str, temperature: float, max_tokens: int):
    """Call AWS Bedrock Anthropic models for chat helper."""
    try:
        import json
        import boto3

        system_prompt, chat_messages = _split_system_and_messages(messages)

        # Convert to Anthropic Messages API format
        anthropic_messages = [
            {
                "role": msg["role"],
                "content": [{"type": "text", "text": msg["content"]}]
            }
            for msg in chat_messages
        ]

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if system_prompt:
            payload["system"] = system_prompt

        bedrock = boto3.client(
            service_name="bedrock-runtime",
            region_name="eu-central-1"
        )

        response = bedrock.invoke_model(
            modelId=model,
            body=json.dumps(payload)
        )

        response_body = json.loads(response['body'].read())
        content_blocks = response_body.get('content', [])
        if not content_blocks:
            raise Exception("Empty response from Bedrock")

        content = "".join(block.get('text', '') for block in content_blocks)
        logger.info(f"[CHAT] Bedrock Success: {len(content)} chars")
        return content
    except Exception as e:
        logger.error(f"[CHAT] Bedrock call failed: {e}", exc_info=True)
        raise


def _call_mistral_chat(messages: list, model: str, temperature: float, max_tokens: int):
    """Call Mistral AI API directly (EU-based, DSGVO-compliant)"""
    try:
        api_url, api_key = get_mistral_credentials()

        if not api_key:
            raise Exception("Mistral API Key not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = _requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=30)

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"[CHAT] Mistral Success: {len(content)} chars")
            return content
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] Mistral Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] Mistral call failed: {e}", exc_info=True)
        raise


def _call_ionos_chat(messages: list, model: str, temperature: float, max_tokens: int):
    """Call IONOS AI Model Hub API (EU datacenter Berlin, DSGVO-compliant)"""
    try:
        api_url, api_key = get_ionos_credentials()

        if not api_key:
            raise Exception("IONOS API Key not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Reasoning models (e.g. gpt-oss-120b) need sufficient tokens for
        # chain-of-thought before generating content
        effective_max_tokens = max_tokens
        if "gpt-oss" in model and effective_max_tokens < 2048:
            effective_max_tokens = 2048

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": effective_max_tokens
        }

        response = _requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=60)

        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]
            content = message.get("content") or ""

            # Extract reasoning chain (gpt-oss-120b reasoning model)
            thinking = message.get("reasoning_content") or message.get("reasoning") or None

            # Fallback to reasoning_content if content is empty
            if not content and thinking:
                content = thinking

            if not content:
                raise Exception("IONOS returned empty response")

            logger.info(f"[CHAT] IONOS Success: {len(content)} chars")
            # Return dict like Ollama so reasoning is visible in ChatOverlay
            return {"content": content, "thinking": thinking}
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] IONOS Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] IONOS call failed: {e}", exc_info=True)
        raise


def _call_mammouth_chat(messages: list, model: str, temperature: float, max_tokens: int):
    """Call Mammouth AI API (EU-based, DSGVO-compliant)"""
    try:
        api_url, api_key = get_mammouth_credentials()

        if not api_key:
            raise Exception("Mammouth API Key not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = _requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=60)

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"].get("content") or ""

            if not content:
                raise Exception("Mammouth returned empty response")

            logger.info(f"[CHAT] Mammouth Success: {len(content)} chars")
            return {"content": content, "thinking": None}
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] Mammouth Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] Mammouth call failed: {e}", exc_info=True)
        raise


def _call_ollama_chat(messages: list, model: str, temperature: float, max_tokens: int):
    """Call LLM via GPU Service (primary) with Ollama fallback for chat helper"""
    try:
        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=model,
            messages=messages,
            temperature=temperature,
            max_new_tokens=max_tokens,
        )

        if result is None:
            raise Exception(f"LLM returned None for model {model}")

        content = result.get("content", "").strip()
        thinking = (result.get("thinking") or "").strip()
        logger.info(f"[CHAT] LLM: content={len(content)} chars, thinking={len(thinking)} chars")
        return {"content": content, "thinking": thinking or None}

    except Exception as e:
        logger.error(f"[CHAT] LLM call failed: {e}", exc_info=True)
        raise


def _call_openrouter_chat(messages: list, model: str, temperature: float, max_tokens: int):
    """Call OpenRouter API for chat helper."""
    try:
        api_url, api_key = get_openrouter_credentials()

        if not api_key:
            raise Exception("OpenRouter API Key not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = _requests_post_with_retry(api_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"[CHAT] OpenRouter Success: {len(content)} chars")
            return content
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] OpenRouter Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] OpenRouter call failed: {e}", exc_info=True)
        raise


def call_chat_helper(messages: list, temperature: float = 0.7, max_tokens: int = 500) -> dict:
    """
    Call the configured chat helper model based on provider prefix.

    Model is loaded from user_settings.json with fallback to CHAT_HELPER_MODEL from config.py.
    This allows runtime configuration via Settings UI.

    Returns dict: {"content": str, "thinking": str|None}
    """
    model_string = get_user_setting("CHAT_HELPER_MODEL", default=CHAT_HELPER_MODEL)
    logger.info(f"[CHAT] Using model: {model_string}")

    if model_string.startswith("bedrock/"):
        model = model_string[len("bedrock/"):]
        logger.info(f"[CHAT] Calling Bedrock with model: {model}")
        result = _call_bedrock_chat(messages, model, temperature, max_tokens)

    elif model_string.startswith("mistral/"):
        model = model_string[len("mistral/"):]
        logger.info(f"[CHAT] Calling Mistral with model: {model}")
        result = _call_mistral_chat(messages, model, temperature, max_tokens)

    elif model_string.startswith("ionos/"):
        model = model_string[len("ionos/"):]
        logger.info(f"[CHAT] Calling IONOS with model: {model}")
        result = _call_ionos_chat(messages, model, temperature, max_tokens)

    elif model_string.startswith("mammouth/"):
        model = model_string[len("mammouth/"):]
        logger.info(f"[CHAT] Calling Mammouth with model: {model}")
        result = _call_mammouth_chat(messages, model, temperature, max_tokens)

    # OpenRouter-compatible providers
    elif model_string.startswith("anthropic/"):
        model = model_string[len("anthropic/"):]
        logger.info(f"[CHAT] Calling OpenRouter with model: {model}")
        result = _call_openrouter_chat(messages, model, temperature, max_tokens)

    elif model_string.startswith("openai/"):
        model = model_string[len("openai/"):]
        logger.info(f"[CHAT] Calling OpenRouter with model: {model}")
        result = _call_openrouter_chat(messages, model, temperature, max_tokens)

    elif model_string.startswith("openrouter/"):
        model = model_string[len("openrouter/"):]
        logger.info(f"[CHAT] Calling OpenRouter with model: {model}")
        result = _call_openrouter_chat(messages, model, temperature, max_tokens)

    elif model_string.startswith("local/"):
        model = model_string[len("local/"):]
        logger.info(f"[CHAT] Calling Ollama with model: {model}")
        result = _call_ollama_chat(messages, model, temperature, max_tokens)

    else:
        raise Exception(f"Unknown model prefix in '{model_string}'. Supported: local/, bedrock/, mistral/, ionos/, mammouth/, anthropic/, openai/, openrouter/")

    # Normalize: Ollama returns dict, other providers return plain strings
    if isinstance(result, str):
        return {"content": result, "thinking": None}
    return result


def load_session_context(run_id: str) -> dict:
    """
    Load session context from the run folder (resolved via load_recorder).

    Returns dict with:
    - success: bool
    - context: dict with session data (if success=True)
    - error: str (if success=False)
    """
    try:
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            logger.warning(f"Session not found for run_id: {run_id}")
            return {"success": False, "error": "Session not found"}
        session_path = recorder.run_folder

        context = {}

        # Load metadata.json
        metadata_path = session_path / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                context['metadata'] = metadata
                context['config_name'] = metadata.get('config_name', 'unknown')
                context['safety_level'] = metadata.get('safety_level', 'unknown')
                context['current_stage'] = metadata.get('current_state', {}).get('stage', 'unknown')

        # Load 03_input.txt
        input_path = session_path / "03_input.txt"
        if input_path.exists():
            with open(input_path, 'r', encoding='utf-8') as f:
                context['input_text'] = f.read().strip()

        # Load 06_interception.txt
        interception_path = session_path / "06_interception.txt"
        if interception_path.exists():
            with open(interception_path, 'r', encoding='utf-8') as f:
                context['interception_text'] = f.read().strip()

        # Load 02_config_used.json
        config_used_path = session_path / "02_config_used.json"
        if config_used_path.exists():
            with open(config_used_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                context['media_type'] = config_data.get('output_config', {}).get('media_type', 'unknown')

        logger.info(f"Session context loaded for run_id={run_id}")
        return {"success": True, "context": context}

    except Exception as e:
        logger.error(f"Error loading session context: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def load_chat_history(run_id: str) -> list:
    """Load chat history from the run folder."""
    try:
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return []
        history_path = recorder.run_folder / "chat_history.json"
        if history_path.exists():
            with open(history_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                logger.info(f"Loaded {len(history)} messages from chat history")
                return history
        return []
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
        return []


def save_chat_history(run_id: str, history: list):
    """Save chat history to the run folder."""
    try:
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            logger.warning(f"Session not found for saving history: {run_id}")
            return

        history_path = recorder.run_folder / "chat_history.json"
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved chat history with {len(history)} messages")
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")


def build_system_prompt(context: dict = None) -> str:
    """
    Build system prompt based on available context

    Args:
        context: Session context dict (or None for general mode)

    Returns:
        System prompt string
    """
    if context is None:
        return GENERAL_SYSTEM_PROMPT

    # Session 265: Comparison mode
    if context.get('comparison_mode'):
        lang_code = context.get('language', 'de')
        lang_names = {'de': 'German', 'en': 'English', 'tr': 'Turkish', 'ko': 'Korean',
                      'uk': 'Ukrainian', 'fr': 'French', 'es': 'Spanish', 'he': 'Hebrew',
                      'ar': 'Arabic', 'bg': 'Bulgarian'}
        lang = lang_names.get(lang_code, 'German')
        return COMPARISON_SYSTEM_PROMPT_TEMPLATE.format(language=lang)

    # Session mode - fill template
    return SESSION_SYSTEM_PROMPT_TEMPLATE.format(
        media_type=context.get('media_type', 'unbekannt'),
        config_name=context.get('config_name', 'unbekannt'),
        safety_level=context.get('safety_level', 'unbekannt'),
        input_text=context.get('input_text', '[noch nicht eingegeben]'),
        interception_text=context.get('interception_text', '[noch nicht transformiert]'),
        current_stage=context.get('current_stage', 'unbekannt')
    )


@chat_bp.route('', methods=['POST'])
def chat():
    """
    Chat endpoint with session context awareness

    POST /api/chat
    Body: {
        "message": "User's question",
        "run_id": "optional-uuid"  // If provided, loads session context
    }

    Response: {
        "reply": "Assistant's response",
        "context_used": true/false,
        "run_id": "uuid"  // Echoed back
    }
    """
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        run_id = data.get('run_id')
        draft_context = data.get('draft_context')  # Current page state (transient, not saved)

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        # Load session context: run_id (file-based) or request body (comparison mode)
        context = None
        context_used = False

        if run_id:
            result = load_session_context(run_id)
            if result['success']:
                context = result['context']
                context_used = True
                logger.info(f"Using session context for run_id={run_id}")
            else:
                logger.warning(f"Could not load context for run_id={run_id}: {result.get('error')}")

        # Session 266: Fallback to request body context (comparison mode has no run_id)
        if not context and 'context' in data and isinstance(data['context'], dict):
            context = data['context']
            context_used = True
            logger.info(f"[CHAT] Using request body context: {list(context.keys())}")

        # Build system prompt
        system_prompt = build_system_prompt(context)

        # Add draft context if provided (NOT saved to exports/, only for this request)
        if draft_context:
            system_prompt += f"\n\n[Aktuelle Eingaben auf der Seite]\n{draft_context}"
            logger.info(f"[CHAT] Draft context added to system prompt ({len(draft_context)} chars)")

        # Load chat history (priority: run_id file > request history > empty)
        history = []
        if run_id:
            history = load_chat_history(run_id)
        elif 'history' in data and isinstance(data['history'], list):
            history = data['history']
            logger.info(f"Using history from request: {len(history)} messages")

        # Build messages for LLM
        messages = [{"role": "system", "content": system_prompt}]

        # Add history (skip system messages from history, we have fresh one)
        for msg in history:
            if msg['role'] != 'system':
                messages.append({"role": msg['role'], "content": msg['content']})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        # Call configured chat helper model
        logger.info(f"Calling chat helper with {len(messages)} messages (context_used={context_used})")
        # Session 133 DEBUG: Log user message to see if draft context is prepended
        logger.info(f"[CHAT-DEBUG] User message preview: {user_message[:200]}..." if len(user_message) > 200 else f"[CHAT-DEBUG] User message: {user_message}")

        result = call_chat_helper(
            messages=messages,
            temperature=0.7,
            max_tokens=2048
        )
        assistant_reply = result["content"]
        assistant_thinking = result.get("thinking")

        # Save to history (if run_id provided) — content only, thinking is ephemeral
        if run_id:
            timestamp = datetime.utcnow().isoformat()
            history.append({
                "role": "user",
                "content": user_message,
                "timestamp": timestamp
            })
            history.append({
                "role": "assistant",
                "content": assistant_reply,
                "timestamp": timestamp
            })
            save_chat_history(run_id, history)

        return jsonify({
            "reply": assistant_reply,
            "thinking": assistant_thinking,
            "context_used": context_used,
            "run_id": run_id
        })

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500


@chat_bp.route('/history/<run_id>', methods=['GET'])
def get_history(run_id: str):
    """
    Get chat history for a session

    GET /api/chat/history/{run_id}

    Response: {
        "history": [...],
        "run_id": "uuid"
    }
    """
    try:
        history = load_chat_history(run_id)
        return jsonify({
            "history": history,
            "run_id": run_id
        })
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500


@chat_bp.route('/clear/<run_id>', methods=['DELETE'])
def clear_history(run_id: str):
    """
    Clear chat history for a session

    DELETE /api/chat/clear/{run_id}

    Response: {
        "success": true,
        "run_id": "uuid"
    }
    """
    try:
        history_path = JSON_STORAGE_DIR / run_id / "chat_history.json"
        if history_path.exists():
            history_path.unlink()
            logger.info(f"Cleared chat history for run_id={run_id}")

        return jsonify({
            "success": True,
            "run_id": run_id
        })
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500
