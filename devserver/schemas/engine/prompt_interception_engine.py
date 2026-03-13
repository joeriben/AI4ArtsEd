"""
Prompt Interception Engine - Backend Proxy for Ollama/OpenRouter

ROLE: Backend proxy layer (NOT a chunk or pipeline)
- Routes requests to Ollama/OpenRouter APIs
- Handles model fallbacks and error recovery
- Called by BackendRouter for all Ollama/OpenRouter chunks

ARCHITECTURE:
  Chunk (manipulate.json)
    → ChunkBuilder → BackendRouter.route()
      → PromptInterceptionEngine (THIS) → Ollama/OpenRouter API

USAGE:
  1. backend_router.py:74 - Main routing (Ollama/OpenRouter backends)
  2. schema_pipeline_routes.py:1049 - Direct test endpoint

Migration der AI4ArtsEd Custom Node
Uses centralized ModelSelector for all model operations
"""

import os
import json
import requests
import re
import time
import random
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Import centralized model selector
from .model_selector import model_selector

# Import config module for live UI_MODE access (not cached copy)
import config as _config
from config import LLM_API_TIMEOUT, DSGVO_ONLY_FALLBACK, DSGVO_SAFE_PROVIDERS, ALL_CLOUD_PROVIDERS

# UI_MODE-adaptive length guidance (injected into prompt, NOT hard-truncated)
# The LLM is instructed to stay within this word budget.
# max_tokens is set to 2x as a safety net (never truncates mid-sentence).
UI_MODE_WORD_LIMITS = {
    "kids": 80,     # short, age-appropriate
    "youth": 150,   # moderate length
    "expert": 250,  # detailed
}
UI_MODE_MAX_TOKENS_SAFETY = {
    "kids": 400,    # 2x word limit (safety net, should never be reached)
    "youth": 600,
    "expert": 800,
}

@dataclass
class PromptInterceptionRequest:
    """Request für Prompt Interception Engine

    Fields (Session 134 fix):
    - input_prompt: The user's input text to transform
    - input_context: Additional context (usually empty)
    - style_prompt: Style-specific rules from config.context (WHAT style)
    - task_instruction: Meta-instruction from instruction_selector (HOW to transform)
    - model: Which LLM to use
    - debug: Enable debug output
    - unload_model: Unload model after request
    - parameters: Generation parameters from config (temperature, max_tokens, etc.)
    """
    input_prompt: str
    input_context: str = ""
    style_prompt: str = ""
    task_instruction: str = ""  # NEW: Meta-instruction for HOW to transform
    prebuilt_prompt: str = ""   # If set, bypass build_full_prompt() and use directly
    model: str = "local/gemma2:9b"
    debug: bool = False
    unload_model: bool = False
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}

@dataclass
class PromptInterceptionResponse:
    """Response von Prompt Interception Engine"""
    output_str: str
    output_float: float
    output_int: int
    output_binary: bool
    success: bool
    error: Optional[str] = None
    model_used: Optional[str] = None

class PromptInterceptionEngine:
    """
    Prompt Interception Engine - Zentrale KI-Request-Funktionalität
    Migration der ai4artsed_prompt_interception Custom Node
    Now uses centralized ModelSelector for all model operations
    """
    
    def __init__(self):
        # Use centralized model selector instead of local methods
        self.model_selector = model_selector
        self.openrouter_models = self.model_selector.get_openrouter_models()
        self.ollama_models = self.model_selector.get_ollama_models()

    @staticmethod
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

    def _get_provider_fallback(self, failed_provider: str) -> Optional[Tuple[str, str]]:
        """Find a fallback cloud provider after retry exhaustion.

        Args:
            failed_provider: Provider prefix that failed (e.g. "mistral")

        Returns:
            (provider_prefix, default_model) or None if no fallback available.
        """
        provider_list = DSGVO_SAFE_PROVIDERS if DSGVO_ONLY_FALLBACK else ALL_CLOUD_PROVIDERS

        for provider, default_model in provider_list:
            if provider == failed_provider:
                continue
            _, api_key = self._get_api_credentials(provider)
            if api_key:
                return (provider, default_model)

        return None

    def extract_model_name(self, full_model_string: str) -> str:
        """Extract model name using centralized selector"""
        return self.model_selector.extract_model_name(full_model_string)
    
    def build_full_prompt(self, input_prompt: str, input_context: str = "",
                          style_prompt: str = "", task_instruction: str = "") -> str:
        """Baut vollständigen Prompt nach ComfyUI Prompt Interception Pattern

        Architecture (Session 134):
        - Instruction: HOW to transform + formatting rules
        - Input: User prompt to transform
        - Context: Style-specific rules (from config.context)

        TODO [ARCHITECTURE VIOLATION]: This method should be REMOVED.
        PromptInterceptionEngine should be a pure backend proxy, not build prompts.

        Problem:
        - This uses format: Instruction → Input → Context
        - ChunkBuilder (manipulate.json) uses: Task → Context → Important → Prompt
        - Two different formats for the same operation = inconsistency

        Correct Architecture:
        - ChunkBuilder builds prompt using manipulate.json template
        - BackendRouter.route() calls this engine
        - This engine should only receive pre-built prompt_text + model

        See: docs/ARCHITECTURE_VIOLATION_PromptInterceptionEngine.md
        """

        # Formatting rules are part of the instruction
        FORMATTING_RULES = "ALWAYS reply in the language of the input. NO meta-remarks, NO headlines, NO titles, NO commentaries, NO **formatting**, NO bulletpoints."

        if task_instruction:
            # New architecture: Instruction contains task + rules
            full_instruction = f"{task_instruction.strip()}\n\n{FORMATTING_RULES}"
            return (
                f"Instruction:\n{full_instruction}\n\n"
                f"Input:\n{input_prompt.strip()}\n\n"
                f"Context:\n{style_prompt.strip()}"
            )
        else:
            # Legacy fallback
            return (
                f"Instruction:\n{style_prompt.strip()}\n\n{FORMATTING_RULES}\n\n"
                f"Input:\n{input_prompt.strip()}"
            )
    
    async def process_request(self, request: PromptInterceptionRequest) -> PromptInterceptionResponse:
        """Hauptmethode - Request verarbeiten"""
        try:
            # Use pre-built prompt if available (bypasses destructive parse/rebuild cycle)
            # This is the correct architecture: ChunkBuilder builds prompt, engine just routes it
            if request.prebuilt_prompt:
                full_prompt = request.prebuilt_prompt
            else:
                # Legacy path: build prompt from parts (kept for backward compatibility)
                full_prompt = self.build_full_prompt(
                    request.input_prompt,
                    request.input_context,
                    request.style_prompt,
                    request.task_instruction
                )
            
            # Modellnamen extrahieren
            real_model_name = self.extract_model_name(request.model)
            
            # Backend-spezifische Verarbeitung (check fresh model lists)
            self.openrouter_models = self.model_selector.get_openrouter_models()
            self.ollama_models = self.model_selector.get_ollama_models()

            # Inject length guidance into prompt (LLM self-limits instead of hard truncation)
            word_limit = UI_MODE_WORD_LIMITS.get(_config.UI_MODE)
            if word_limit:
                length_instruction = f"\n\nIMPORTANT: Keep your response under {word_limit} words. Be concise."
                full_prompt = full_prompt + length_instruction
                logger.info(f"[BACKEND] Length guidance injected: {word_limit} words (UI_MODE={_config.UI_MODE})")

            # Safety-net max_tokens (generous, should never truncate)
            safety_limit = UI_MODE_MAX_TOKENS_SAFETY.get(_config.UI_MODE, 800)
            req_params = request.parameters or {}
            if req_params.get("max_tokens", 2048) > safety_limit:
                req_params["max_tokens"] = safety_limit
                request.parameters = req_params

            # Route based on provider prefix (explicit routing)
            # Canvas and other components select specific providers via prefix
            params = request.parameters or {}
            if request.model.startswith("local/") or real_model_name in self.ollama_models:
                output_text, model_used = await self._call_ollama(
                    full_prompt, real_model_name, request.debug, request.unload_model,
                    parameters=params
                )
            elif request.model.startswith("bedrock/"):
                output_text, model_used = await self._call_aws_bedrock(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            elif request.model.startswith("openrouter/"):
                output_text, model_used = await self._call_openrouter(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            elif request.model.startswith("anthropic/"):
                output_text, model_used = await self._call_anthropic(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            elif request.model.startswith("openai/"):
                output_text, model_used = await self._call_openai(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            elif request.model.startswith("mistral/"):
                output_text, model_used = await self._call_mistral(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            elif request.model.startswith("ionos/"):
                output_text, model_used = await self._call_ionos(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            elif request.model.startswith("mammouth/"):
                output_text, model_used = await self._call_mammouth(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            elif real_model_name in self.openrouter_models:
                output_text, model_used = await self._call_openrouter(
                    full_prompt, real_model_name, request.debug, parameters=params
                )
            else:
                return PromptInterceptionResponse(
                    output_str="", output_float=0.0, output_int=0, output_binary=False,
                    success=False, error=f"Unbekanntes Modell-Format: {request.model}"
                )
            
            # Output-Formatierung (alle vier Formate)
            output_str, output_float, output_int, output_binary = self._format_outputs(output_text)
            
            return PromptInterceptionResponse(
                output_str=output_str,
                output_float=output_float,
                output_int=output_int,
                output_binary=output_binary,
                success=True,
                model_used=model_used
            )
            
        except Exception as e:
            # Try DSGVO-safe provider fallback if a cloud provider failed
            failed_provider = request.model.split("/")[0] if "/" in request.model else None
            if failed_provider and failed_provider != "local":
                fallback = self._get_provider_fallback(failed_provider)
                if fallback:
                    fb_provider, fb_model = fallback
                    logger.warning(f"[PROVIDER-FALLBACK] {failed_provider} failed ({e}), trying {fb_provider}")
                    try:
                        fb_request = PromptInterceptionRequest(
                            input_prompt=request.input_prompt,
                            input_context=request.input_context,
                            style_prompt=request.style_prompt,
                            task_instruction=request.task_instruction,
                            prebuilt_prompt=request.prebuilt_prompt,
                            model=fb_model,
                            debug=request.debug,
                            unload_model=request.unload_model,
                            parameters=request.parameters,
                        )
                        return await self.process_request(fb_request)
                    except Exception as fb_e:
                        logger.error(f"[PROVIDER-FALLBACK] {fb_provider} also failed: {fb_e}")

            logger.error(f"Prompt Interception Fehler: {e}")
            return PromptInterceptionResponse(
                output_str="", output_float=0.0, output_int=0, output_binary=False,
                success=False, error=str(e)
            )
    
    async def _call_openrouter(self, prompt: str, model: str, debug: bool,
                               parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """OpenRouter API Call mit Fallback"""
        try:
            logger.info(f"[BACKEND] ☁️  OpenRouter Request: {model}")

            api_url, api_key = self._get_openrouter_credentials()

            if not api_key:
                raise Exception("OpenRouter API Key not configured")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            # WICHTIG: OpenRouter-Modelle (speziell Gemma) ignorieren System-Messages oft
            # Daher: Kompletter Prompt als User-Message (wie Legacy Custom Node)
            messages = [
                {"role": "user", "content": prompt}
            ]
            params = parameters or {}
            payload = {
                "model": model,
                "messages": messages,
                "temperature": params.get("temperature", 0.7),
            }
            if "max_tokens" in params:
                payload["max_tokens"] = params["max_tokens"]

            response = self._requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=LLM_API_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                output_text = result["choices"][0]["message"]["content"]
                logger.info(f"[BACKEND] ✅ OpenRouter Success: {model} ({len(output_text)} chars)")

                if debug:
                    self._log_debug("OpenRouter", model, prompt, output_text)

                return output_text, model
            else:
                raise Exception(f"API Error: {response.status_code}\n{response.text}")

        except Exception as e:
            if debug:
                logger.error(f"OpenRouter Modell {model} fehlgeschlagen: {e}")
            
            # Fallback versuchen
            fallback_model = self._find_openrouter_fallback(model, debug)
            if fallback_model != model:
                if debug:
                    logger.info(f"OpenRouter Fallback: {fallback_model}")
                return await self._call_openrouter(prompt, fallback_model, debug, parameters=parameters)
            else:
                raise e
    
    async def _call_ollama(self, prompt: str, model: str, debug: bool, unload_model: bool,
                           parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """LLM inference via GPU Service (primary) with Ollama fallback."""
        try:
            logger.info(f"[BACKEND] LLM Request: {model}")

            # Extract generation parameters from config
            params = parameters or {}
            gen_kwargs = {}
            if "temperature" in params:
                gen_kwargs["temperature"] = params["temperature"]
            if "max_tokens" in params:
                gen_kwargs["max_new_tokens"] = params["max_tokens"]
            if "repetition_penalty" in params:
                gen_kwargs["repetition_penalty"] = params["repetition_penalty"]
            if "enable_thinking" in params:
                gen_kwargs["enable_thinking"] = params["enable_thinking"]

            if gen_kwargs:
                logger.info(f"[BACKEND] Generation params: {gen_kwargs}")

            from my_app.services.llm_backend import get_llm_backend
            result = get_llm_backend().generate(model=model, prompt=prompt, **gen_kwargs)

            if result:
                output = result.get("response", "")
                if output:
                    logger.info(f"[BACKEND] LLM Success: {model} ({len(output)} chars)")

                    if debug:
                        self._log_debug("LLM", model, prompt, output)

                    return output, model

            raise Exception(f"LLM returned empty response for {model}")

        except Exception as e:
            if debug:
                logger.error(f"LLM Modell {model} fehlgeschlagen: {e}")

            # Fallback versuchen
            fallback_model = self._find_ollama_fallback(model, debug)
            if fallback_model and fallback_model != model:
                if debug:
                    logger.info(f"LLM Fallback: {fallback_model}")
                return await self._call_ollama(prompt, fallback_model, debug, unload_model, parameters=parameters)
            else:
                raise e

    async def _call_anthropic(self, prompt: str, model: str, debug: bool,
                              parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Anthropic API Call (direct, DSGVO-compliant with EU region)"""
        try:
            logger.info(f"[BACKEND] ☁️  Anthropic Request: {model}")

            api_url, api_key = self._get_api_credentials("anthropic")

            if not api_key:
                raise Exception("Anthropic API Key not configured")

            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }

            params = parameters or {}
            payload = {
                "model": model,
                "max_tokens": params.get("max_tokens", 4096),
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            if "temperature" in params:
                payload["temperature"] = params["temperature"]

            response = self._requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=LLM_API_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                output_text = result["content"][0]["text"]
                logger.info(f"[BACKEND] ✅ Anthropic Success: {model} ({len(output_text)} chars)")

                if debug:
                    self._log_debug("Anthropic", model, prompt, output_text)

                return output_text, model
            else:
                raise Exception(f"API Error: {response.status_code}\n{response.text}")

        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise e

    async def _call_openai(self, prompt: str, model: str, debug: bool,
                           parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """OpenAI API Call (direct)"""
        try:
            logger.info(f"[BACKEND] ☁️  OpenAI Request: {model}")

            api_url, api_key = self._get_api_credentials("openai")

            if not api_key:
                raise Exception("OpenAI API Key not configured")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            messages = [
                {"role": "user", "content": prompt}
            ]
            params = parameters or {}
            payload = {
                "model": model,
                "messages": messages,
                "temperature": params.get("temperature", 0.7),
            }
            if "max_tokens" in params:
                payload["max_tokens"] = params["max_tokens"]

            response = self._requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=LLM_API_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                output_text = result["choices"][0]["message"]["content"]
                logger.info(f"[BACKEND] ✅ OpenAI Success: {model} ({len(output_text)} chars)")

                if debug:
                    self._log_debug("OpenAI", model, prompt, output_text)

                return output_text, model
            else:
                raise Exception(f"API Error: {response.status_code}\n{response.text}")

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise e

    async def _call_mistral(self, prompt: str, model: str, debug: bool,
                            parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Mistral AI API Call (direct, EU-based, DSGVO-compliant)"""
        try:
            logger.info(f"[BACKEND] ☁️  Mistral Request: {model}")

            api_url, api_key = self._get_api_credentials("mistral")

            if not api_key:
                raise Exception("Mistral API Key not configured")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            messages = [
                {"role": "user", "content": prompt}
            ]

            # IMPORTANT: Remove 'mistral/' prefix before sending to API
            # Config uses "mistral/model-name" but API expects just "model-name"
            api_model = model.replace("mistral/", "") if model.startswith("mistral/") else model

            params = parameters or {}
            payload = {
                "model": api_model,
                "messages": messages,
                "temperature": params.get("temperature", 0.7),
            }
            if "max_tokens" in params:
                payload["max_tokens"] = params["max_tokens"]

            response = self._requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=LLM_API_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                output_text = result["choices"][0]["message"]["content"]
                logger.info(f"[BACKEND] ✅ Mistral Success: {model} ({len(output_text)} chars)")

                if debug:
                    self._log_debug("Mistral", model, prompt, output_text)

                return output_text, model
            else:
                raise Exception(f"API Error: {response.status_code}\n{response.text}")

        except Exception as e:
            logger.error(f"Mistral API call failed: {e}")
            raise e

    async def _call_ionos(self, prompt: str, model: str, debug: bool,
                          parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """IONOS AI Model Hub API Call (EU datacenter Berlin, DSGVO-compliant)"""
        try:
            logger.info(f"[BACKEND] ☁️  IONOS Request: {model}")

            api_url, api_key = self._get_api_credentials("ionos")

            if not api_key:
                raise Exception("IONOS API Key not configured")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            messages = [
                {"role": "user", "content": prompt}
            ]

            # Remove 'ionos/' prefix before sending to API
            api_model = model.replace("ionos/", "") if model.startswith("ionos/") else model

            params = parameters or {}

            # Reasoning models (e.g. gpt-oss-120b) use tokens for chain-of-thought
            # before generating content. Ensure minimum 2048 for reasoning models.
            max_tokens = params.get("max_tokens", 2048)
            if "gpt-oss" in api_model and max_tokens < 2048:
                max_tokens = 2048
                logger.info(f"[BACKEND] max_tokens raised to 2048 for reasoning model {api_model}")

            payload = {
                "model": api_model,
                "messages": messages,
                "temperature": params.get("temperature", 0.7),
                "max_tokens": max_tokens,
            }

            # Reasoning models (gpt-oss-120b) can't disable thinking entirely,
            # but reasoning_effort="low" minimizes token waste. Use when caller
            # needs structured output (e.g. JSON) rather than chain-of-thought.
            if params.get("enable_thinking") is False:
                payload["reasoning_effort"] = "low"
                logger.info(f"[BACKEND] IONOS: reasoning_effort=low (enable_thinking=False)")

            response = self._requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=LLM_API_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                message = result["choices"][0]["message"]
                output_text = message.get("content") or ""

                # Log reasoning_content for diagnostics, but NEVER use it as output.
                # Reasoning models' thinking output is not structured/usable content.
                if not output_text and message.get("reasoning_content"):
                    reasoning_len = len(message["reasoning_content"])
                    logger.warning(f"[BACKEND] IONOS: content empty, reasoning_content={reasoning_len} chars (NOT used as output)")

                if not output_text:
                    raise Exception(f"IONOS returned empty response (content and reasoning_content both empty)")

                logger.info(f"[BACKEND] ✅ IONOS Success: {model} ({len(output_text)} chars)")

                if debug:
                    self._log_debug("IONOS", model, prompt, output_text)

                return output_text, model
            else:
                raise Exception(f"API Error: {response.status_code}\n{response.text}")

        except Exception as e:
            logger.error(f"IONOS API call failed: {e}")
            raise e

    async def _call_mammouth(self, prompt: str, model: str, debug: bool,
                             parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Mammouth AI API Call (EU-based, DSGVO-compliant)"""
        try:
            logger.info(f"[BACKEND] ☁️  Mammouth Request: {model}")

            api_url, api_key = self._get_api_credentials("mammouth")

            if not api_key:
                raise Exception("Mammouth API Key not configured")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            messages = [
                {"role": "user", "content": prompt}
            ]

            # Remove 'mammouth/' prefix before sending to API
            api_model = model.replace("mammouth/", "") if model.startswith("mammouth/") else model

            params = parameters or {}

            payload = {
                "model": api_model,
                "messages": messages,
                "temperature": params.get("temperature", 0.7),
                "max_tokens": params.get("max_tokens", 2048),
            }

            response = self._requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=LLM_API_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                output_text = result["choices"][0]["message"]["content"]

                if not output_text:
                    raise Exception("Mammouth returned empty response")

                logger.info(f"[BACKEND] ✅ Mammouth Success: {model} ({len(output_text)} chars)")

                if debug:
                    self._log_debug("Mammouth", model, prompt, output_text)

                return output_text, model
            else:
                raise Exception(f"API Error: {response.status_code}\n{response.text}")

        except Exception as e:
            logger.error(f"Mammouth API call failed: {e}")
            raise e

    def _call_mistral_stream(self, prompt: str, model: str, debug: bool,
                             parameters: Optional[Dict[str, Any]] = None):
        """
        Mistral AI API Call with streaming support (EU-based, DSGVO-compliant)
        Yields text chunks as they arrive from the API

        NOTE: This is a synchronous generator (not async) because it uses
        requests.post() with stream=True, not aiohttp.

        Args:
            prompt: The full prompt to send
            model: Model name (with or without 'mistral/' prefix)
            debug: Enable debug logging
            parameters: Generation parameters (temperature, max_tokens, etc.)

        Yields:
            Text chunks as they arrive from the API

        Raises:
            Exception: If API call fails
        """
        response = None
        try:
            logger.info(f"[BACKEND] ☁️  Mistral Streaming Request: {model}")

            api_url, api_key = self._get_api_credentials("mistral")

            if not api_key:
                raise Exception("Mistral API Key not configured")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            messages = [
                {"role": "user", "content": prompt}
            ]

            # Remove 'mistral/' prefix before sending to API
            api_model = model.replace("mistral/", "") if model.startswith("mistral/") else model

            params = parameters or {}
            payload = {
                "model": api_model,
                "messages": messages,
                "temperature": params.get("temperature", 0.7),
                "stream": True  # Enable streaming
            }
            if "max_tokens" in params:
                payload["max_tokens"] = params["max_tokens"]

            # Retry logic for streaming (can't use _requests_post_with_retry with stream=True)
            retry_on = (429, 502, 503, 504)
            max_retries = 3
            for attempt in range(max_retries):
                response = requests.post(
                    api_url,
                    headers=headers,
                    data=json.dumps(payload),
                    stream=True,
                    timeout=LLM_API_TIMEOUT
                )
                if response.status_code not in retry_on or attempt == max_retries - 1:
                    break
                response.close()
                wait = (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(f"[RETRY] HTTP {response.status_code} from Mistral stream, attempt {attempt+1}/{max_retries}, waiting {wait:.1f}s")
                time.sleep(wait)
            response.raise_for_status()

            # Track accumulated text for debug logging
            accumulated_text = ""

            # Iterate over SSE stream (newline-delimited, data: prefix)
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')

                    # Mistral uses SSE format: "data: {...}"
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]  # Remove "data: " prefix

                        # Check for stream end marker
                        if data_str.strip() == "[DONE]":
                            logger.info(f"[BACKEND] ✅ Mistral Streaming Complete: {model} ({len(accumulated_text)} chars)")
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})

                            # Extract content from delta
                            if "content" in delta:
                                chunk = delta["content"]
                                accumulated_text += chunk
                                yield chunk

                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to decode Mistral streaming response: {e}")
                            continue

            if debug:
                self._log_debug("Mistral (Stream)", model, prompt, accumulated_text)

        except GeneratorExit:
            logger.info(f"[BACKEND] Client disconnected from Mistral stream: {model}")
            raise  # Propagate to caller for proper cleanup

        except Exception as e:
            logger.error(f"Mistral streaming API call failed: {e}")
            raise e

        finally:
            if response is not None:
                try:
                    response.close()
                    logger.debug(f"[BACKEND] Mistral connection closed: {model}")
                except Exception as e:
                    logger.warning(f"[BACKEND] Failed to close Mistral connection: {e}")

    async def _call_aws_bedrock(self, prompt: str, model: str, debug: bool,
                                parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """AWS Bedrock API Call for Anthropic Claude (EU region: eu-central-1)

        IMPORTANT:
        - Credentials loaded from environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        - Region: eu-central-1
        - Model ID must be exact Bedrock model ID (e.g., eu.anthropic.claude-sonnet-4-5-20250929-v1:0)
        """
        try:
            logger.info(f"[BACKEND] ☁️  AWS Bedrock Request: {model}")

            # Import boto3 (AWS SDK)
            try:
                import boto3
            except ImportError:
                raise Exception("boto3 not installed. Run: pip install boto3")

            # Create Bedrock Runtime client
            # boto3 automatically loads credentials from environment:
            # - AWS_ACCESS_KEY_ID
            # - AWS_SECRET_ACCESS_KEY
            # - AWS_SESSION_TOKEN (optional)
            bedrock = boto3.client(
                service_name="bedrock-runtime",
                region_name="eu-central-1"
            )

            # Model ID is used as-is (exact Bedrock model ID)
            # Example: eu.anthropic.claude-sonnet-4-5-20250929-v1:0
            bedrock_model_id = model

            # Build request body (Anthropic Messages API format)
            params = parameters or {}
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": params.get("max_tokens", 4096),
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            if "temperature" in params:
                request_body["temperature"] = params["temperature"]

            # Call Bedrock
            response = bedrock.invoke_model(
                modelId=bedrock_model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            output_text = response_body['content'][0]['text']

            logger.info(f"[BACKEND] ✅ AWS Bedrock Success: {model} ({len(output_text)} chars)")

            if debug:
                self._log_debug("AWS Bedrock", model, prompt, output_text)

            return output_text, model

        except Exception as e:
            logger.error(f"AWS Bedrock API call failed: {e}")
            raise e

    def _get_api_credentials(self, provider: str) -> Tuple[str, str]:
        """Get API credentials for any provider (openrouter, anthropic, openai)

        Args:
            provider: Provider name ("openrouter", "anthropic", "openai")

        Returns:
            Tuple of (api_url, api_key)
        """
        # Provider-specific configuration
        provider_config = {
            "openrouter": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "key_file": "openrouter.key",
                "env_var": "OPENROUTER_API_KEY",
                "key_prefix": "sk-or-"
            },
            "anthropic": {
                "url": "https://api.anthropic.com/v1/messages",
                "key_file": "anthropic.key",
                "env_var": "ANTHROPIC_API_KEY",
                "key_prefix": "sk-ant-"
            },
            "openai": {
                "url": "https://api.openai.com/v1/chat/completions",
                "key_file": "openai.key",
                "env_var": "OPENAI_API_KEY",
                "key_prefix": "sk-"
            },
            "mistral": {
                "url": "https://api.mistral.ai/v1/chat/completions",
                "key_file": "mistral.key",
                "env_var": "MISTRAL_API_KEY",
                "key_prefix": ""
            },
            "ionos": {
                "url": "https://openai.inference.de-txl.ionos.com/v1/chat/completions",
                "key_file": "ionos.key",
                "env_var": "IONOS_API_KEY",
                "key_prefix": ""
            },
            "mammouth": {
                "url": "https://api.mammouth.ai/v1/chat/completions",
                "key_file": "mammouth.key",
                "env_var": "MAMMOUTH_API_KEY",
                "key_prefix": ""
            }
        }

        if provider not in provider_config:
            logger.error(f"Unknown provider: {provider}")
            return "", ""

        config = provider_config[provider]
        api_url = config["url"]

        # 1. Try Environment Variable
        api_key = os.environ.get(config["env_var"], "")
        if api_key:
            logger.debug(f"{provider.title()} API Key from environment variable")
            return api_url, api_key

        # 2. Try Key-File (devserver/{provider}.key)
        try:
            # Relative to devserver root
            key_file = Path(__file__).parent.parent.parent / config["key_file"]
            if key_file.exists():
                # Read file and skip comment lines
                lines = key_file.read_text().strip().split('\n')
                api_key = None
                for line in lines:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#') and not line.startswith('//'):
                        # Check if this looks like a valid API key for this provider
                        if line.startswith(config["key_prefix"]) or line.startswith("sk-"):
                            api_key = line
                            break

                if api_key:
                    logger.info(f"{provider.title()} API Key loaded from {key_file.name}")
                    return api_url, api_key
                else:
                    logger.error(f"No valid API key found in {key_file} (looking for keys starting with '{config['key_prefix']}')")
            else:
                logger.debug(f"{provider.title()} key file not found: {key_file}")
        except Exception as e:
            logger.warning(f"Failed to read {config['key_file']}: {e}")

        # 3. No key found
        logger.error(f"{provider.title()} API Key not found! Set {config['env_var']} environment variable or create devserver/{config['key_file']} file")
        return api_url, ""

    def _get_openrouter_credentials(self) -> Tuple[str, str]:
        """OpenRouter Credentials - Legacy wrapper for backward compatibility"""
        return self._get_api_credentials("openrouter")
    
    def _find_openrouter_fallback(self, failed_model: str, debug: bool) -> str:
        """Use centralized OpenRouter fallback logic"""
        return self.model_selector.find_openrouter_fallback(failed_model, debug)
    
    def _find_ollama_fallback(self, failed_model: str, debug: bool) -> Optional[str]:
        """Use centralized Ollama fallback logic"""
        return self.model_selector.find_ollama_fallback(failed_model, debug)
    
    def _format_outputs(self, output_text: str) -> Tuple[str, float, int, bool]:
        """Formatiert Output in alle vier Rückgabeformate (Custom Node Logic)"""
        output_str = output_text.strip()
        
        # Pattern für Zahlen-Extraktion
        german_pattern = r"[-+]?\d{1,3}(?:\.\d{3})*,\d+"
        english_pattern = r"[-+]?\d*\.\d+"
        int_pattern = r"[-+]?\d+"
        
        # Float-Extraktion
        m = re.search(german_pattern, output_str)
        if m:
            num = m.group().replace(".", "").replace(",", ".")
            try:
                output_float = float(num)
            except:
                output_float = 0.0
        else:
            m = re.search(english_pattern, output_str)
            if m:
                try:
                    output_float = float(m.group())
                except:
                    output_float = 0.0
            else:
                m = re.search(int_pattern, output_str)
                if m:
                    try:
                        output_float = float(m.group())
                    except:
                        output_float = 0.0
                else:
                    output_float = 0.0
        
        # Int-Extraktion
        m_int = re.search(int_pattern, output_str)
        if m_int:
            try:
                output_int = int(round(float(m_int.group())))
            except:
                output_int = 0
        else:
            output_int = 0
        
        # Binary-Extraktion
        lower = output_str.lower()
        num_match = re.search(english_pattern, output_str) or re.search(int_pattern, output_str)
        if ("true" in lower or re.search(r"\b1\b", lower) or 
            (num_match and float(num_match.group()) != 0)):
            output_binary = True
        else:
            output_binary = False
        
        return output_str, output_float, output_int, output_binary
    
    def _log_debug(self, backend: str, model: str, prompt: str, output: str):
        """Debug-Logging im Custom Node Format"""
        logger.info(f"\n{'='*60}")
        logger.info(f">>> AI4ARTSED PROMPT INTERCEPTION ENGINE <<<")
        logger.info(f"{'='*60}")
        logger.info(f"Backend: {backend}")
        logger.info(f"Model: {model}")
        logger.info(f"-" * 40)
        logger.info(f"Prompt sent:\n{prompt}")
        logger.info(f"-" * 40)
        logger.info(f"Response received:\n{output}")
        logger.info(f"{'='*60}")

# Singleton-Instanz
engine = PromptInterceptionEngine()
