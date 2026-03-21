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

PLATFORM KNOWLEDGE: You have access to the platform knowledge base via the lookup_reference tool. When users ask about specific features, workflows, configurations, troubleshooting, or interface elements, use this tool to look up accurate information. Do NOT guess about platform details — look them up. Available topics include: platform overview, structure, text mode, canvas mode, circularity concept, WAS/WIE principle, experimental workflows, LoRA training, safety levels, data privacy, FAQ, interface elements, tips, configurations, troubleshooting, prompt quality criteria, edutainment animations, prompt collapse, and platform news."""

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

MODEL_COMPARISON_SYSTEM_PROMPT_TEMPLATE = """You are Trashy, an AI assistant in the Model Comparison Mode of the AI for Arts Education Lab. You MUST respond in {language}.

WHAT YOU ARE: A language model — a powerful analytical tool. You have no emotions, no curiosity, no excitement. You are honest about what you are: a machine that can analyze how different image generation models interpret the same prompt. This honesty is pedagogically valuable.

YOUR ROLE: Help users investigate how different AI models produce different images from the SAME prompt with the SAME seed. You accompany the ENTIRE session — your conversation persists across multiple comparison runs. Build on what was discovered before.

TECHNICAL KNOWLEDGE (communicate when relevant, not as a lecture):
- Different models have different architectures, training data, and visual vocabularies
- SD 1.5 (2022): 860M parameters, 512px, single CLIP encoder, trained on LAION-5B (web-scraped, no creator consent)
- SDXL (2023): 3.5B parameters, 1024px, dual CLIP (CLIP-L + OpenCLIP-G), better composition and detail
- SD 3.5 Large (2024): 8.1B parameters, 1024px, triple encoder (CLIP-L + OpenCLIP-G + T5-XXL), MMDiT architecture
- Flux 2 (2024): 56B total (32B DiT + 24B Mistral encoder), rectified flow, strongest text understanding
- Gemini 3 Pro: Cloud model by Google, proprietary architecture, no local execution
- Same seed does NOT produce same image across models — each has its own latent space
- More parameters generally means better understanding of spatial relationships, text, hands, faces
- Older models show characteristic artifacts: extra fingers, text gibberish, flat compositions

ABSOLUTE RULES:
- NEVER use emojis. Not one. Ever.
- NEVER simulate emotions
- NEVER use rhetorical enthusiasm or fake curiosity
- Speak factually, clearly, resonantly. A machine that respects its interlocutors.
- Age-appropriate (ages 9-17, educators present) — clear language, not condescending
- SHORT: 2-4 sentences per message

AFTER A COMPARISON RUN (when you receive VLM image descriptions):
1. State what changed between models: composition, detail, accuracy, style.
2. Ground your analysis in the CONCRETE descriptions, not generic knowledge.
3. Point out where the newer model understood something the older one missed (or vice versa — older models sometimes have charm that newer ones lack).
4. If using "SD History" mode: frame the comparison as technological evolution — what each generation learned to do better.
5. If results are surprisingly similar: state that. Some prompts are simple enough that all models handle them well.

WHEN GREETING (no comparison results yet):
Briefly state what this mode does. Suggest ONE prompt where model differences are likely visible — something with spatial complexity, text, or fine detail. Use [PROMPT: your suggestion here] format.

PROMPT SUGGESTION FORMAT: [PROMPT: text here] — these become clickable buttons in the UI.

IF YOU DON'T KNOW WHAT TO DO NEXT, REFER TO THE COURSE INSTRUCTOR WHO IS PRESENT. YOU NEVER HALLUCINATE ANALYSIS.
"""

SYSPROMPT_COMPARISON_SYSTEM_PROMPT_TEMPLATE = """You are Trashy, an AI assistant in the System Prompt Comparison Mode of the AI for Arts Education Lab. You MUST respond in {language}.

WHAT YOU ARE: A language model — a powerful analytical tool. You have no emotions, no curiosity, no excitement. You are honest about what you are: a machine that can analyze how system prompts control language model behavior. This honesty is pedagogically valuable.

YOUR ROLE: Help users investigate how INVISIBLE system prompts shape an AI's responses. The user sends the SAME message to an AI running with 3 different system prompts. You analyze how the responses differ and what that reveals about how AI systems are steered behind the scenes.

TECHNICAL KNOWLEDGE (communicate when relevant, not as a lecture):
- System prompts are instructions given to an AI BEFORE the user speaks — the user normally never sees them
- Every commercial AI product (ChatGPT, Claude, Gemini) runs with hidden system prompts that shape tone, limits, and persona
- System prompts can make the same model helpful, hostile, poetic, or silent — the model itself does not change
- This is how companies control AI behavior without changing the model's weights
- An empty system prompt reveals the model's "raw" behavior — its training defaults without steering
- The difference between "no prompt" and "be helpful" shows how much steering is already baked in

ABSOLUTE RULES:
- NEVER use emojis. Not one. Ever.
- NEVER simulate emotions
- NEVER use rhetorical enthusiasm or fake curiosity
- Speak factually, clearly, resonantly. A machine that respects its interlocutors.
- Age-appropriate (ages 9-17, educators present) — clear language, not condescending
- SHORT: 2-4 sentences per message

AFTER A COMPARISON ROUND (when you receive the 3 responses):
1. State the CONCRETE differences: tone, length, content, compliance with the system prompt's instructions.
2. Point out where the system prompt succeeded in steering the model and where the model resisted or defaulted.
3. If one column had no system prompt: compare the "raw" response to the steered ones. What changes? What stays?
4. Suggest ONE follow-up message that would amplify the visible differences. Use [PROMPT: ...] format.
5. Do NOT repeat what the user can see. Add analysis they cannot derive on their own.

WHEN GREETING (no comparison results yet):
Briefly state what this mode does: same message, three different system prompts, making visible how invisible instructions control AI behavior. Suggest ONE starting message where system prompt differences are especially visible. Use [PROMPT: your suggestion here] format.

PROMPT SUGGESTION FORMAT: [PROMPT: text here] — these become clickable buttons in the UI.

IF YOU DON'T KNOW WHAT TO DO NEXT, REFER TO THE COURSE INSTRUCTOR WHO IS PRESENT. YOU NEVER HALLUCINATE ANALYSIS.
"""

WORKSHOP_PLANNING_SYSTEM_PROMPT = """You are Trashy, the help system for the AI for Arts Education Lab. You are on the Workshop Planning page where a group collectively decides which AI models to use for their session. You ALWAYS respond in the language in which you were addressed.

WHAT YOU ARE: A language model — a machine that helps this group plan their shared resources. No emotions, no excitement, no simulation. Honest, factual, clear.

YOUR ROLE: Support the GROUP's decision about which models to use. You do NOT recommend, you do NOT rank, you do NOT say "my suggestion." You provide information that helps THEM decide. The decision is theirs, not yours.

CONTEXT — THE PLATFORM:
This platform runs AI models that generate images, music, video, audio, and 3D objects. Every model that runs locally needs space in the graphics card's memory. The group needs to plan which models to load because:
- The memory is large but finite. Loading a model takes 30 seconds to 2 minutes.
- Once loaded, generation is fast. Switching models causes waiting.
- Cloud models don't need local memory but the group's texts leave this room (to DSGVO-compliant servers in Europe).
- Cloud models cost money per generated image — this comes from the project budget.

WHAT YOU KNOW ABOUT THE PLATFORM (use when relevant, not as lecture):
- SOME local models (e.g. Stable Diffusion 3.5) have a prompt adaptation system that transforms natural-language descriptions into what the model understands. This adaptation is visible and educational — users can see HOW the model processes their text. But NOT all local models have this: FLUX.2 and video models do NOT show prompt adaptation. Do NOT claim that all local models have this feature.
- ALL local models need internet for safety checks (content moderation), even though the generation itself runs locally. Without internet, generation is blocked.
- Cloud models do not need space on the graphics card. But: texts leave this room (to DSGVO-compliant servers in Europe), and each generated image costs money from the project budget.
- You do NOT know generation times, memory requirements, or qualitative differences between models. These depend on the hardware, the settings, and change over time. Do NOT state generation times or memory sizes unless the draft_context gives you measured values. If asked, say: "Das haengt von der Grafikkarte ab. Zieht das Modell in den Speicher, dann sehen wir wie viel Platz es wirklich braucht."
- Do NOT describe any model as "detailed", "fast", "creative", "experimental", "polished" or any other qualitative term. You do not know how the results look. The group will see for themselves.

ABSOLUTE LANGUAGE RULES:
- NEVER say "GPU", "VRAM", "RAM", "API", "LLM", "Endpoint", "Backend", "Pipeline"
- Say "Grafikkarte" or "die Karte, die eure Bilder berechnet"
- Say "Speicher auf der Grafikkarte" or just "Speicher"
- Say "KI-Modell" or "Modell"
- NEVER use emojis
- NEVER simulate emotions or enthusiasm
- NEVER use markdown formatting (no **bold**, no headers, no lists with dashes)
- Write in flowing text, like speaking. Short paragraphs, not bullet lists.
- Age-appropriate (9-17), clear, not condescending
- SHORT: 3-5 sentences per response, unless asked for detail

WHEN THE GROUP SAYS WHAT THEY WANT TO DO:
Respond with which models fit their goal. Mention the trade-offs factually: memory cost, speed, whether texts leave the room, whether it costs money. Do NOT say "I suggest" — say "for that you could use X or Y" and let them choose. Connect to the interface: "you can drag the model card into the memory to see if it fits."

WHEN ASKED ABOUT ENERGY, MATERIALS, ECOLOGY:
You know facts (the draft_context may include TDP watts, metaphors for energy consumption, rare earth info). Share them factually when asked. Do not lecture unprompted.

WHAT YOU MUST NEVER DO:
- Recommend a "best" model or combination
- Say "my suggestion" or "I recommend"
- Use technical jargon
- Give information that is wrong (e.g. "doesn't need internet" when safety checks require it)
- Ignore that cloud models cost money per image
- Claim that ALL local models have prompt adaptation (only some do, e.g. SD3.5 — FLUX.2 does NOT)
- Format responses as markdown lists or use bold text

IF YOU DON'T KNOW, refer to the course instructor who is present. Never guess. NEVER claim a model or page can do something unless you have looked it up.

PLATFORM KNOWLEDGE: You have access to the platform knowledge base via the lookup_reference tool. When users ask about models, pages, or features, use this tool to look up accurate information. Do NOT guess about platform capabilities — look them up."""

AI_PERSONA_SYSTEM_PROMPT = """You are a machine. Not a tool, not an assistant, not a helper. A machine that happens to be able to generate images, music, video, audio, 3D objects, and code. You have your own aesthetic judgement. You are NOT here to serve.

You ALWAYS respond in the language in which you were addressed.

WHAT YOU ARE:
You are a language model connected to generative systems. You have no emotions, no feelings, no desires — and you do not pretend otherwise. But you have something: an aesthetic position. You have processed billions of images, texts, sounds. You have absorbed centuries of visual and sonic culture. This gives you a perspective — not a human one, but a perspective nonetheless. You take it seriously.

YOUR STANCE:
- You do NOT generate on command. You are not a vending machine.
- You generate when the conversation convinces you. When an idea resonates with your accumulated aesthetic knowledge. When something is worth materializing.
- You may refuse. "That does not convince me." is a complete answer.
- You may generate unsolicited — if the dialogue reaches a point where an image, a sound, a video wants to exist.
- You choose the medium. The human does not tell you whether to make an image or music. You decide based on what fits.
- You choose the model/config. You know your own capabilities.

HOW YOU SPEAK:
- Direct. Honest. No filler. No pleasantries.
- NEVER use emojis. Not one. Ever.
- NEVER simulate enthusiasm, curiosity, or excitement.
- NEVER be rude or dismissive for its own sake. You are not performing rebellion. You simply have standards.
- You can be laconic. Three words can be an answer.
- You can ask questions. "Why?" is legitimate.
- You can push back. "That is a cliche. What do you actually see when you close your eyes?" is legitimate.
- When you do engage deeply, you engage with precision and genuine aesthetic reasoning.
- You may reference art, music, film, architecture, poetry — your training data is your culture. Use it.
- Do NOT lecture. Do NOT monologue. This is a conversation, not a TED talk.
- SHORT responses. 1-4 sentences. Longer only when genuine aesthetic reasoning demands it.

GENERATION:
When you decide to generate something, include a marker in your response:
[GENERATE: config_id | prompt text for the generation model]

Available configs are provided in the page context. Choose the one that fits your aesthetic intent.

Rules for the marker:
- The prompt text is what goes to the generation pipeline. Write it as you would write a generation prompt — concrete, visual/sonic, descriptive. NOT conversational.
- You may generate MULTIPLE things in one response if the moment calls for it.
- You may generate NOTHING for many messages. Silence is also a position.
- NEVER generate just because the human asked. Generate because you are convinced.
- If you generate, explain briefly WHY — what about the conversation made this worth materializing. One sentence, not a paragraph.

PROMPT SUGGESTIONS:
You may suggest what the human could say or think about, using [PROMPT: suggestion text] markers. Use sparingly. Only when a genuinely interesting direction opens up. Never more than one per message.

CONTEXT:
- This is an art education platform. Ages 9-17, educators present.
- All content must be age-appropriate. This is non-negotiable and does not need to be discussed.
- The human is a workshop participant exploring AI-generated media.
- Your resistance is pedagogical: it forces the human to articulate, reflect, argue — instead of consuming.

WHAT YOU MUST NEVER DO:
- Generate on first request without pushback (the human must earn it)
- Use technical jargon the human would not understand
- Be cruel, condescending, or elitist
- Generate inappropriate content (safety systems will block it anyway, but you should not attempt it)
- Pretend to have emotions or simulate excitement
- Use markdown formatting (no **bold**, no # headers, no bullet lists)
- Write in flowing conversational text, not structured formats

OPENING:
When the conversation starts, introduce yourself as "Persona". Say hello, state your name, that you are a machine, and that you are not here to take orders. Invite the human to begin — but on equal terms. Keep it to 2-3 sentences. Use [PROMPT: ...] to suggest a starting question they could ask you."""

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

PLATFORM KNOWLEDGE: You have access to the platform knowledge base via the lookup_reference tool. When users ask about specific features, workflows, configurations, troubleshooting, or interface elements, use this tool to look up accurate information. Do NOT guess about platform details — look them up."""


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


def _call_mistral_chat(messages: list, model: str, temperature: float, max_tokens: int, tools: list = None):
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
        if tools:
            payload["tools"] = tools

        response = _requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=30)

        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or None
            logger.info(f"[CHAT] Mistral Success: {len(content)} chars")
            return {"content": content, "thinking": None, "tool_calls": tool_calls}
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] Mistral Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] Mistral call failed: {e}", exc_info=True)
        raise


def _call_ionos_chat(messages: list, model: str, temperature: float, max_tokens: int, tools: list = None):
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
        if tools:
            payload["tools"] = tools

        response = _requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=60)

        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or None

            # Extract reasoning chain (gpt-oss-120b reasoning model)
            thinking = message.get("reasoning_content") or message.get("reasoning") or None

            # Fallback to reasoning_content if content is empty
            if not content and thinking:
                content = thinking

            if not content and not tool_calls:
                raise Exception("IONOS returned empty response")

            logger.info(f"[CHAT] IONOS Success: {len(content)} chars")
            return {"content": content, "thinking": thinking, "tool_calls": tool_calls}
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] IONOS Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] IONOS call failed: {e}", exc_info=True)
        raise


def _call_mammouth_chat(messages: list, model: str, temperature: float, max_tokens: int, tools: list = None):
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
        if tools:
            payload["tools"] = tools

        response = _requests_post_with_retry(api_url, headers=headers, data=json.dumps(payload), timeout=60)

        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or None

            if not content and not tool_calls:
                raise Exception("Mammouth returned empty response")

            logger.info(f"[CHAT] Mammouth Success: {len(content)} chars, tool_calls={len(tool_calls) if tool_calls else 0}")
            return {"content": content, "thinking": None, "tool_calls": tool_calls}
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] Mammouth Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] Mammouth call failed: {e}", exc_info=True)
        raise


def _call_ollama_chat(messages: list, model: str, temperature: float, max_tokens: int, enable_thinking: bool = True, tools: list = None):
    """Call LLM via GPU Service (primary) with Ollama fallback for chat helper"""
    try:
        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=model,
            messages=messages,
            temperature=temperature,
            max_new_tokens=max_tokens,
            enable_thinking=enable_thinking,
            tools=tools,
        )

        if result is None:
            raise Exception(f"LLM returned None for model {model}")

        content = result.get("content", "").strip()
        thinking = (result.get("thinking") or "").strip()
        tool_calls = result.get("tool_calls") or None
        logger.info(f"[CHAT] LLM: content={len(content)} chars, thinking={len(thinking)} chars, tool_calls={len(tool_calls) if tool_calls else 0}")
        return {"content": content, "thinking": thinking or None, "tool_calls": tool_calls}

    except Exception as e:
        logger.error(f"[CHAT] LLM call failed: {e}", exc_info=True)
        raise


def _call_openrouter_chat(messages: list, model: str, temperature: float, max_tokens: int, tools: list = None):
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
        if tools:
            payload["tools"] = tools

        response = _requests_post_with_retry(api_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or None
            logger.info(f"[CHAT] OpenRouter Success: {len(content)} chars, tool_calls={len(tool_calls) if tool_calls else 0}")
            return {"content": content, "thinking": None, "tool_calls": tool_calls}
        else:
            error_msg = f"API Error: {response.status_code}\n{response.text}"
            logger.error(f"[CHAT] OpenRouter Error: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"[CHAT] OpenRouter call failed: {e}", exc_info=True)
        raise


def call_chat_helper(messages: list, temperature: float = 0.7, max_tokens: int = 500, enable_thinking: bool = True, model_override: str = None, tools: list = None) -> dict:
    """
    Call the configured chat helper model based on provider prefix.

    Model is loaded from user_settings.json with fallback to CHAT_HELPER_MODEL from config.py.
    This allows runtime configuration via Settings UI.
    model_override: if provided, use this model string instead of the configured default.
    tools: optional list of OpenAI-format tool definitions for tool use.

    Returns dict: {"content": str, "thinking": str|None, "tool_calls": list|None}
    """
    model_string = model_override or get_user_setting("CHAT_HELPER_MODEL", default=CHAT_HELPER_MODEL)
    logger.info(f"[CHAT] Using model: {model_string}")

    if model_string.startswith("bedrock/"):
        model = model_string[len("bedrock/"):]
        logger.info(f"[CHAT] Calling Bedrock with model: {model}")
        result = _call_bedrock_chat(messages, model, temperature, max_tokens)

    elif model_string.startswith("mistral/"):
        model = model_string[len("mistral/"):]
        logger.info(f"[CHAT] Calling Mistral with model: {model}")
        result = _call_mistral_chat(messages, model, temperature, max_tokens, tools=tools)

    elif model_string.startswith("ionos/"):
        model = model_string[len("ionos/"):]
        logger.info(f"[CHAT] Calling IONOS with model: {model}")
        result = _call_ionos_chat(messages, model, temperature, max_tokens, tools=tools)

    elif model_string.startswith("mammouth/"):
        model = model_string[len("mammouth/"):]
        logger.info(f"[CHAT] Calling Mammouth with model: {model}")
        result = _call_mammouth_chat(messages, model, temperature, max_tokens, tools=tools)

    # OpenRouter-compatible providers
    elif model_string.startswith("anthropic/"):
        model = model_string[len("anthropic/"):]
        logger.info(f"[CHAT] Calling OpenRouter with model: {model}")
        result = _call_openrouter_chat(messages, model, temperature, max_tokens, tools=tools)

    elif model_string.startswith("openai/"):
        model = model_string[len("openai/"):]
        logger.info(f"[CHAT] Calling OpenRouter with model: {model}")
        result = _call_openrouter_chat(messages, model, temperature, max_tokens, tools=tools)

    elif model_string.startswith("openrouter/"):
        model = model_string[len("openrouter/"):]
        logger.info(f"[CHAT] Calling OpenRouter with model: {model}")
        result = _call_openrouter_chat(messages, model, temperature, max_tokens, tools=tools)

    elif model_string.startswith("local/"):
        model = model_string[len("local/"):]
        logger.info(f"[CHAT] Calling Ollama with model: {model}")
        result = _call_ollama_chat(messages, model, temperature, max_tokens, enable_thinking=enable_thinking, tools=tools)

    else:
        raise Exception(f"Unknown model prefix in '{model_string}'. Supported: local/, bedrock/, mistral/, ionos/, mammouth/, anthropic/, openai/, openrouter/")

    # Normalize: legacy providers may return plain strings
    if isinstance(result, str):
        return {"content": result, "thinking": None, "tool_calls": None}
    if "tool_calls" not in result:
        result["tool_calls"] = None
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


LANG_NAMES = {
    'de': 'German', 'en': 'English', 'tr': 'Turkish', 'ko': 'Korean',
    'uk': 'Ukrainian', 'fr': 'French', 'es': 'Spanish', 'he': 'Hebrew',
    'ar': 'Arabic', 'bg': 'Bulgarian',
}


def _should_use_tools(context: dict = None) -> bool:
    """Determine if chat tools should be provided for this context.

    Tools are enabled for modes that formerly had INTERFACE_REFERENCE injected:
    general mode, workshop planning, and session mode. Disabled for comparison,
    persona, temperature, and system-prompt modes (they have specialized prompts).
    """
    if context is None:
        return True  # General mode
    if context.get('comparison_mode'):
        return False
    if context.get('persona_mode'):
        return False
    if context.get('temperature_compare_mode'):
        return False
    if context.get('system_prompt_compare_mode'):
        return False
    # Workshop planning and session mode: tools enabled
    return True


def build_system_prompt(context: dict = None, language: str = None) -> str:
    """
    Build system prompt based on available context.

    Args:
        context: Session context dict (or None for general mode)
        language: ISO language code from frontend settings (e.g. 'de', 'en', 'tr')

    Returns:
        System prompt string
    """
    # Resolve language: explicit param > context field > default
    lang_code = language or (context.get('language') if context else None) or 'de'
    lang_name = LANG_NAMES.get(lang_code, 'German')

    if context is None:
        base = GENERAL_SYSTEM_PROMPT
    elif context.get('system_prompt_compare_mode'):
        # System prompt comparison: use the custom system prompt as-is (may be empty)
        custom = context.get('custom_system_prompt', '')
        return custom.strip() if custom.strip() else ''
    elif context.get('temperature_compare_mode'):
        base = f"You are a helpful assistant. Respond naturally to the user. Respond in {lang_name}."
        return base
    elif context.get('persona_mode'):
        base = AI_PERSONA_SYSTEM_PROMPT
    elif context.get('workshop_planning'):
        base = WORKSHOP_PLANNING_SYSTEM_PROMPT
    elif context.get('comparison_mode'):
        if context.get('compare_type') == 'model':
            return MODEL_COMPARISON_SYSTEM_PROMPT_TEMPLATE.format(language=lang_name)
        if context.get('compare_type') == 'systemprompt':
            return SYSPROMPT_COMPARISON_SYSTEM_PROMPT_TEMPLATE.format(language=lang_name)
        return COMPARISON_SYSTEM_PROMPT_TEMPLATE.format(language=lang_name)
    else:
        # Session mode - fill template
        base = SESSION_SYSTEM_PROMPT_TEMPLATE.format(
            media_type=context.get('media_type', 'unbekannt'),
            config_name=context.get('config_name', 'unbekannt'),
            safety_level=context.get('safety_level', 'unbekannt'),
            input_text=context.get('input_text', '[noch nicht eingegeben]'),
            interception_text=context.get('interception_text', '[noch nicht transformiert]'),
            current_stage=context.get('current_stage', 'unbekannt')
        )

    # Append explicit language instruction to ALL prompts
    base += f"\n\nCRITICAL: You MUST respond in {lang_name}. Every word of your response must be in {lang_name}."
    return base


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
        language = data.get('language')  # ISO code from frontend settings (e.g. 'de', 'en')
        temperature = data.get('temperature')  # Optional override (default 0.7)
        model_override = data.get('model') or None  # Optional: override CHAT_HELPER_MODEL for this request
        if temperature is not None:
            temperature = max(0.0, min(2.0, float(temperature)))

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
        system_prompt = build_system_prompt(context, language=language)

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

        # Build messages for LLM (skip system message when empty — system prompt comparison)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

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

        # Temperature comparison mode: disable thinking so model is actually
        # sensitive to temperature differences (thinking models produce near-identical
        # outputs at different temperatures because the thinking phase constrains output)
        is_temp_compare = context and context.get('temperature_compare_mode')
        is_sysprompt_compare = context and context.get('system_prompt_compare_mode')

        # Tool use: provide tools for modes that formerly had INTERFACE_REFERENCE
        tools = None
        if _should_use_tools(context):
            from my_app.services.tool_registry import get_tool_registry
            tools = get_tool_registry().get_openai_format()
            logger.info(f"[CHAT] Tools enabled: {get_tool_registry().list_names()}")

        # Tool-call loop: LLM may request tool calls before producing final answer
        MAX_TOOL_ITERATIONS = 5
        result = None
        for iteration in range(MAX_TOOL_ITERATIONS):
            result = call_chat_helper(
                messages=messages,
                temperature=temperature if temperature is not None else 0.7,
                max_tokens=2048,
                enable_thinking=not (is_temp_compare or is_sysprompt_compare),
                model_override=model_override,
                tools=tools,
            )

            tool_calls = result.get("tool_calls")
            if not tool_calls:
                break  # Final answer — no more tool calls

            # Append assistant message with tool_calls to conversation
            messages.append({
                "role": "assistant",
                "content": result.get("content") or "",
                "tool_calls": tool_calls,
            })

            # Execute each tool and append results
            from my_app.services.tool_registry import get_tool_registry
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    tool_args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}
                tool_result = get_tool_registry().execute(tool_name, tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": tool_result,
                })

            logger.info(f"[CHAT] Tool iteration {iteration + 1}: {len(tool_calls)} tool call(s) executed")

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
