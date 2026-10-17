"""
Prompt Interception Engine - Backend Proxy for Local LLM/OpenRouter

ROLE: Backend proxy layer (NOT a chunk or pipeline)
- Routes requests to local LLM / OpenRouter APIs
- Handles model fallbacks and error recovery
- Called by BackendRouter for all LOCAL_LLM/OpenRouter chunks

ARCHITECTURE:
  Chunk (manipulate.json)
    → ChunkBuilder → BackendRouter.route()
      → PromptInterceptionEngine (THIS) → LLM Backend / OpenRouter API

USAGE:
  1. backend_router.py:74 - Main routing (LOCAL_LLM/OpenRouter backends)
  2. schema_pipeline_routes.py:1049 - Direct test endpoint

Uses centralized ModelSelector for all model operations
"""

import os
import json
import re
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Import centralized model selector
from .model_selector import model_selector

# Import config module for live UI_MODE access (not cached copy)
import config as _config
from my_app.services.usage_tracker import get_usage_tracker, extract_usage
# Every cloud call this engine makes goes through the platform's one reader.
# It asks with stream=True, so the provider writes its first bytes within
# seconds and the request cannot sit silent long enough for an edge to give up
# on it: nine HTTP 524s in the week before 2026-09-03 came from exactly that
# silence, and four of them killed a run outright. Which dialect a provider
# speaks — OpenAI chat-completions or Anthropic messages — is the reader's
# business, read from config/llm_providers.json; this engine names the provider.
from my_app.services.openai_style_stream import call_chat
from my_app.services.llm_providers import (
    BEDROCK, provider as provider_entry, provider_of,
)

# The length guidance that used to live here is now an instruction rather than
# a cap, in instruction_selector.READING_VOLUME_WORDS. It is keyed on UI_MODE:
# the interface setting decides who the text is written for, the safety setting
# decides safety.
#
# A hard safety ceiling (UI_MODE_MAX_TOKENS_SAFETY) briefly lived here too
# (2026-08-05): it kept unbounded Stage-2 output from overflowing Llama-Guard's
# n_ctx at Stage 3, whose failure was read as a pass. Both halves of that hole
# are fixed at the source (work order A1): the guard call checks long text in
# bounded windows, and a missing verdict stops the run. No cap belongs here.

@dataclass
class PromptInterceptionRequest:
    """Request für Prompt Interception Engine

    Fields:
    - input_prompt: The user's input text to transform
    - input_context: Additional context (usually empty)
    - style_prompt: Style-specific rules from config.context (WHAT style)
    - task_instruction: Meta-instruction from instruction_selector (HOW to transform)
    - model: Which LLM to use
    - debug: Enable debug output
    - unload_model: Unload model after request
    - parameters: Generation parameters from config (temperature, max_tokens, etc.)
    - usage_stage: What the usage tracker books this call's tokens under
      (stage1..stage4), set by the executor from the config's meta.stage
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
    usage_stage: str = "stage2"

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
    # The id of the branch that ACTUALLY ran, service prefix included, written
    # after the dispatch rather than before it. model_used above is the name the
    # backend was called with once the prefix was stripped, so it names a model
    # but not a service, and the routing below does not always follow the prefix
    # it was handed: a bare name standing in the live local list goes to the GPU
    # service whatever it looks like. A caller comparing what it asked for
    # against what ran needs the string that ran.
    dispatched_model: Optional[str] = None

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
        self.local_models = self.model_selector.get_local_models()

    # _requests_post_with_retry stood here until 2026-09-04. Its last caller
    # was _call_anthropic, which sent its request and then waited for the whole
    # answer, so a 429 or a 5xx there ended the run unless something asked
    # again. Anthropic now streams through the shared reader in
    # my_app/services/openai_style_stream.py, which asks again itself: the same
    # twelve statuses (429, 502, 503, 504 and Cloudflare's 520-527), the same
    # three attempts, the same exponential backoff — and, unlike this loop, only
    # BEFORE the first byte. That is the half this loop got wrong for a streamed
    # request: once bytes are flowing, asking again pays for the first part of
    # an answer twice. Do not reintroduce it around a streamed call.

    def extract_model_name(self, full_model_string: str) -> str:
        """Extract model name using centralized selector"""
        return self.model_selector.extract_model_name(full_model_string)
    
    def build_full_prompt(self, input_prompt: str, input_context: str = "",
                          style_prompt: str = "", task_instruction: str = "") -> str:
        """Baut vollständigen Prompt nach ComfyUI Prompt Interception Pattern

        Architecture:
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

        # Formatting rules are part of the instruction. Die beiden Zweige
        # schreiben verschiedene Marken -- der neue "Prompt:", der alte
        # "Input:" -- und eine Regel, die die falsche Marke nennt, nennt nichts.
        FORMATTING_RULES = ("ALWAYS reply in the language of the input. Write plain running text: "
                            "sentences in paragraphs, and that is the whole reply.")
        FORMATTING_RULES_PROMPT = ("ALWAYS reply in the language of the Prompt. Write plain running text: "
                                   "sentences in paragraphs, and that is the whole reply.")

        if task_instruction:
            # New architecture: Instruction contains task + rules
            full_instruction = f"{task_instruction.strip()}\n\n{FORMATTING_RULES_PROMPT}"
            # "Prompt:", not "Input:": the task instruction names the mark it
            # expects, and schemas/chunks/manipulate.json writes "Prompt:". Two
            # assemblies with two different marks meant the instruction pointed
            # at nothing on this path (2026-09-07).
            return (
                f"Instruction:\n{full_instruction}\n\n"
                f"Prompt:\n{input_prompt.strip()}\n\n"
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
            self.local_models = self.model_selector.get_local_models()

            # Route by the provider the model id names (explicit routing).
            # Canvas and other components select specific providers via prefix.
            # Which service each branch reaches is recorded as the branch is
            # taken, rather than derived from the prefix afterwards: the local
            # branch is entered on the live local list too, so a bare name and a
            # prefixed one arrive at the same place while looking different.
            #
            # The provider is the first segment of the id and the table
            # (config/llm_providers.json) says whether that segment names one.
            # A prefixed cloud id is a cloud id: it is not looked up in the
            # local list, so a local model that happens to share a path with a
            # cloud one cannot catch it. Until 2026-09-12 a ladder of eight
            # prefixes stood here.
            #
            # A cloud branch asks for real_model_name, the extractor's answer:
            # the path after the provider with a ' [tag]' the register may
            # append cut off. Sliced off the raw id, the tag went to the
            # provider.
            params = request.parameters or {}
            provider = provider_of(request.model)
            if provider is None and (request.model.startswith("local/")
                                     or real_model_name in self.local_models):
                dispatched_service = "local"
                output_text, model_used = await self._call_local_llm(
                    full_prompt, real_model_name, request.debug, request.unload_model,
                    parameters=params
                )
            elif provider is not None and provider_entry(provider).get("dialect") == BEDROCK:
                dispatched_service = provider
                output_text, model_used = await self._call_aws_bedrock(
                    full_prompt, real_model_name, request.debug, parameters=params,
                    usage_stage=request.usage_stage,
                )
            elif provider is not None:
                dispatched_service = provider
                output_text, model_used = await self._call_cloud(
                    provider, full_prompt, real_model_name, request.debug,
                    parameters=params, usage_stage=request.usage_stage,
                )
            elif real_model_name in self.openrouter_models:
                dispatched_service = "openrouter"
                output_text, model_used = await self._call_cloud(
                    "openrouter", full_prompt, real_model_name, request.debug,
                    parameters=params, usage_stage=request.usage_stage,
                )
            else:
                return PromptInterceptionResponse(
                    output_str="", output_float=0.0, output_int=0, output_binary=False,
                    success=False, error=f"Unbekanntes Modell-Format: {request.model}"
                )
            
            # The name a branch hands back still carries its prefix wherever the
            # extractor does not strip that prefix, so the service is prepended
            # only where it is missing.
            dispatched_model = (
                model_used if str(model_used).startswith(f"{dispatched_service}/")
                else f"{dispatched_service}/{model_used}"
            )

            # Output-Formatierung (alle vier Formate)
            output_str, output_float, output_int, output_binary = self._format_outputs(output_text)
            
            return PromptInterceptionResponse(
                output_str=output_str,
                output_float=output_float,
                output_int=output_int,
                output_binary=output_binary,
                success=True,
                model_used=model_used,
                dispatched_model=dispatched_model
            )
            
        except Exception as e:
            # The request fails as the request it was. No substitute model answers in
            # its place: a caller that asked for one model and silently got another
            # cannot tell the two apart afterwards.
            logger.error(f"Prompt Interception Fehler: {e}")
            return PromptInterceptionResponse(
                output_str="", output_float=0.0, output_int=0, output_binary=False,
                success=False, error=str(e)
            )
    
    @staticmethod
    def _refuse_a_truncated_answer(label: str, model: str, result: dict):
        """Refuse an answer the model did not finish writing.

        What leaves this engine travels on through a pipeline as if a person had
        written it, so half of it is not a smaller version of it. A Stage-3
        translation cut mid-sentence reaches the image model as a fragment, and
        the §86a word list then runs on that fragment rather than on the text —
        the words it looks for can sit in the half that never arrived.

        The provider says so in finish_reason, and 'length' is the word in both
        dialects: the reader translates Anthropic's max_tokens to it precisely
        so that one guard can read both. The local node has a second word,
        'repetition', for an answer it stopped because the model had begun to
        loop; what stood by then is a fragment of the same kind. Raised rather
        than returned, because every caller of this engine reads a raised
        failure as a failed request and a returned string as an intercepted
        text.

        This is held here and not at the two call sites, because two copies of
        one guard are how one of them comes to be forgotten (project rule 13).
        """
        reason = result.get("finish_reason")
        if reason == "length":
            raise Exception(
                f"{label} answer was cut off for model {model} "
                f"(finish_reason=length): a truncated text is not an "
                f"intercepted text")
        if reason == "repetition":
            raise Exception(
                f"{label} answer was stopped for model {model} because it had "
                f"begun to repeat itself (finish_reason=repetition): a text "
                f"that loops is not an intercepted text")

    # ------------------------------------------------------------------
    # The cloud providers, whichever dialect they speak
    # ------------------------------------------------------------------
    async def _call_cloud(self, provider: str, prompt: str, model: str, debug: bool,
                          parameters: Optional[Dict[str, Any]] = None,
                          usage_stage: str = "stage2") -> Tuple[str, str]:
        """One request to a cloud provider, streamed and assembled.

        Until 2026-09-12 this stood as six methods, one per provider, over a
        shared body and a second one for Anthropic's dialect. They differed in
        the label they logged, in whether the routing prefix still had to come
        off the model id, and in one provider-specific request field. The label
        comes from the table now, the id arrives with its prefix already off
        (the caller splits it by the table), and the field is declared in the
        provider's entry. The dialect is the reader's business.

        `model` is the path the provider publishes, which is what the provider
        is asked for and what comes back: a caller comparing what it requested
        against what ran needs its own string.

        Temperature: only what a config asked for is passed on. The reader
        fills in 0.7 for a chat-completions provider, the default this engine
        has always sent there, and leaves the field out for the messages
        dialect, where the model applies its own — quietly sending 0.7 there
        would change what every existing config on it produces. max_tokens the
        same: nothing is sent unless a config asks for it, the model's own
        ceiling is the right ceiling, and where an API requires the field the
        reader fills in the ceiling, not a budget.
        """
        entry = provider_entry(provider) or {}
        label = entry.get("label", provider)
        logger.info(f"[BACKEND] ☁️  {label} Request: {model}")
        params = parameters or {}
        extra: Optional[Dict[str, Any]] = None
        if params.get("enable_thinking") is False and entry.get("thinking_off_payload"):
            # A provider whose reasoning models cannot be told to stop
            # reasoning, but can be told to keep it short, declares the field
            # that says so in its table entry (IONOS: reasoning_effort=low).
            # Sent only where a config switched thinking off, so a structured
            # answer (JSON, a rating) is not spent on a train of thought.
            extra = dict(entry["thinking_off_payload"])
            logger.info(f"[BACKEND] {label}: {extra} (enable_thinking=False)")
        try:
            result = call_chat(
                provider,
                [{"role": "user", "content": prompt}],
                model,
                temperature=params.get("temperature"),
                max_tokens=params.get("max_tokens"),
                stage=usage_stage,
                extra_payload=extra,
            )
        except Exception as e:
            logger.error(f"{label} API call failed: {e}")
            raise

        output_text = result.get("content") or ""
        if not output_text:
            # Reasoning is not an answer, and this engine will not pass one off
            # as the other: what comes out of here goes on into a pipeline as an
            # intercepted text. A model that thought and then wrote nothing has
            # failed this request; its chain-of-thought is counted in the log and
            # dropped. The chat surface makes the opposite decision at its own
            # call site, which is why the reader hands the two fields over
            # separately instead of choosing for either of us.
            thinking = result.get("thinking") or ""
            if thinking:
                logger.warning(f"[BACKEND] {label}: content empty, "
                               f"thinking={len(thinking)} chars (NOT used as output)")
            raise Exception(f"{label} returned empty response for model {model}")

        self._refuse_a_truncated_answer(label, model, result)

        logger.info(f"[BACKEND] ✅ {label} Success: {model} ({len(output_text)} chars)")

        if debug:
            self._log_debug(label, model, prompt, output_text)

        return output_text, model

    async def _call_local_llm(self, prompt: str, model: str, debug: bool, unload_model: bool,
                           parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """One request to a local model: the prompt as the one user message
        of a conversation, through the model's chat template.

        The shape the cloud branch sends (`_call_cloud`: one user message
        since 3151a667, 2025-10-18), so a prompt written once is read the
        same way on either side. From ac047ceb (2026-02-23) to 2026-09-16
        this branch sent the prompt raw, with no chat template around it
        (under Ollama before that, the Modelfile's template wrapped it). An
        instruct model given raw text continues it instead of answering it.
        Measured 16.09.2026, the kids replay (58 requests, all of them the
        config pre_output/translation_en) with the 9B as STAGE3_MODEL: Qwen
        3.5 on the node opened a train of thought on the translation prompt,
        39 of 43 answers were stopped inside it by the repetition guard
        (7-121 s each), and the raw path partitions no think block, so what
        stood by then went on as the answer -- a 2405-character monologue as
        a translation, a 1710-character one as far as the image model. 0 of
        58 requests answered in the 21 minutes until the client left, 17 of
        them refused by the gate at once.

        `enable_thinking` comes from the config's parameters and reaches
        the template: False closes the think block, and the two adaption
        endpoints the surface uses and the translation config say so; a
        config that says nothing gets the template's own default, thinking
        on, as the chat surface does. What the model thought is not the
        answer: content empty is a failed request, as on the cloud branch,
        said with what came instead and why the model stopped; and an
        answer the model did not finish -- the window full, or stopped for
        looping -- is refused by the same guard.
        """
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
                gen_kwargs["enable_thinking"] = bool(params["enable_thinking"])

            if gen_kwargs:
                logger.info(f"[BACKEND] Generation params: {gen_kwargs}")

            from my_app.services.llm_backend import get_llm_backend
            result = get_llm_backend().chat(
                model=model, messages=[{"role": "user", "content": prompt}], **gen_kwargs)

            if result is None:
                # The client logs the cause on its own line ([LLM-CLIENT]
                # Chat failed) and hands back None; this is not an empty
                # answer, and until 2026-09-16 it was reported as one.
                raise Exception(f"LLM call failed for {model}: no answer from the local "
                                f"model (the [LLM-CLIENT] line above carries the cause)")

            output = result.get("content") or ""
            if not output:
                # Reasoning is not an answer (see _call_cloud). The sentence
                # carries what came instead and the node's word for why the
                # model stopped: a train of thought the repetition guard
                # ended is the measured local failure (Nr. 119, Nr. 122),
                # and "empty response" alone hid it.
                thinking = result.get("thinking") or ""
                reason = result.get("finish_reason")
                if thinking:
                    logger.warning(f"[BACKEND] LLM: content empty, "
                                   f"thinking={len(thinking)} chars (NOT used as output)")
                    raise Exception(f"LLM returned no answer for {model}: {len(thinking)} "
                                    f"chars of thinking and no content "
                                    f"(finish_reason={reason})")
                raise Exception(f"LLM returned empty response for {model} "
                                f"(finish_reason={reason})")

            self._refuse_a_truncated_answer("LLM", model, result)

            logger.info(f"[BACKEND] LLM Success: {model} ({len(output)} chars)")

            if debug:
                self._log_debug("LLM", model, prompt, output)

            return output, model

        except Exception as e:
            if debug:
                logger.error(f"LLM Modell {model} fehlgeschlagen: {e}")

            raise

    async def _call_aws_bedrock(self, prompt: str, model: str, debug: bool,
                                parameters: Optional[Dict[str, Any]] = None,
                                usage_stage: str = "stage2") -> Tuple[str, str]:
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
                # required by this API; a ceiling, not a budget
                "max_tokens": params.get("max_tokens", _config.ANTHROPIC_MAX_TOKENS_CEILING),
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

            inp, out = extract_usage(response_body, "bedrock")
            if inp or out:
                get_usage_tracker().log(model=model, provider="bedrock",
                                        stage=usage_stage, input_tokens=inp, output_tokens=out)

            if debug:
                self._log_debug("AWS Bedrock", model, prompt, output_text)

            return output_text, model

        except Exception as e:
            logger.error(f"AWS Bedrock API call failed: {e}")
            raise e

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
