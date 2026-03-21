"""
Central configuration file for the AI4ArtsEd Web Server

Runtime-configurable settings live in _SETTINGS_DEFAULTS (bottom of this section).
Actual values come from user_settings.json, editable via Settings UI.
"""
import os
from pathlib import Path

# Base paths (defined early because used throughout config)
_SERVER_BASE = Path(__file__).parent.parent  # devserver parent = ai4artsed_development
_AI_TOOLS_BASE = Path(os.environ.get("AI_TOOLS_BASE", str(_SERVER_BASE.parent)))  # overridable for production on separate partition

# ============================================================================
# SERVER SETTINGS (static — not in Settings UI)
# ============================================================================
HOST = "0.0.0.0"
PORT = 17802  # Development: 17802, Production: 17801
THREADS = 24

# CORS: Allowed origins for cross-origin requests
# Development origins are auto-generated from PORT; add production domains here
CORS_ALLOWED_ORIGINS = [
    f'http://localhost:{PORT}',
    f'http://127.0.0.1:{PORT}',
    'http://localhost:5173',           # Vite dev server
    'https://lab.ai4artsed.org',       # Production domain
]

# ============================================================================
# SETTINGS (user_settings.json is the source of truth)
# ============================================================================
# These are FALLBACK values for fresh installations without user_settings.json.
# Actual values are loaded from user_settings.json at startup via reload_user_settings().
# Edit via Settings UI — NOT here.
#
# Provider Prefix Format (for model values):
#   "local/model-name" → Ollama | "mistral/model-name" → Mistral AI
#   "ionos/model-name" → IONOS | "openrouter/provider/model" → OpenRouter
#
_SETTINGS_DEFAULTS = {
    # UI & safety defaults (non-model)
    'UI_MODE': 'youth',
    'DEFAULT_SAFETY_LEVEL': 'kids',
    'DEFAULT_LANGUAGE': 'de',
    'DEFAULT_INTERCEPTION_CONFIG': 'user_defined',
    'LLM_PROVIDER': 'ollama',
    'OLLAMA_API_BASE_URL': 'http://localhost:11434',
    'LMSTUDIO_API_BASE_URL': 'http://localhost:1234',
    'EXTERNAL_LLM_PROVIDER': 'none',
    'DSGVO_CONFORMITY': True,
    # Model roles — NO hardcoded model names. Actual values come from user_settings.json.
    # Empty strings here ensure hasattr() works for import compatibility.
    # If user_settings.json is missing, server will NOT start (see __init__.py).
    'STAGE1_TEXT_MODEL': '',
    'STAGE2_INTERCEPTION_MODEL': '',
    'STAGE2_OPTIMIZATION_MODEL': '',
    'STAGE3_MODEL': '',
    'STAGE4_LEGACY_MODEL': '',
    'CHAT_HELPER_MODEL': '',
    'PERSONA_MODEL': '',
    'CODING_MODEL': '',
    'IMAGE_ANALYSIS_MODEL': '',
    'SAFETY_MODEL': '',
    'DSGVO_VERIFY_MODEL': '',
    'VLM_SAFETY_MODEL': '',
}

# Pre-initialize module globals for imports (overwritten by reload_user_settings at startup)
for _k, _v in _SETTINGS_DEFAULTS.items():
    globals()[_k] = _v
del _k, _v


# Stage 5: Image Analysis Prompts (4 Theoretical Frameworks)
IMAGE_ANALYSIS_PROMPTS = {
    'bildwissenschaftlich': {
        # Panofsky - Art-historical analysis (4-stage iconological method)
        'de': """Du analysierst ein KI-generiertes Bild im Kunstunterricht.

Erstelle eine strukturierte Analyse nach diesem Schema:

1. MATERIELLE UND MEDIALE EIGENSCHAFTEN
   - Identifiziere den KI-Generierungsstil und visuelle Charakteristika
   - Beschreibe die technische Umsetzung (Rendering, Textur, Beleuchtung)

2. VORIKONOGRAPHISCHE BESCHREIBUNG
   - Beschreibe ALLE sichtbaren Elemente: Objekte, Figuren, Räumlichkeit
   - Analysiere Komposition, Farbgebung, Texturen, räumliche Beziehungen
   - Beschreibe Perspektive und visuelle Struktur

3. IKONOGRAPHISCHE ANALYSE
   - Interpretiere symbolische Bedeutungen und künstlerische Techniken
   - Identifiziere künstlerische Stile oder Referenzen

4. IKONOLOGISCHE INTERPRETATION
   - Diskutiere kulturelle und konzeptuelle Bedeutungen
   - Reflektiere über die visuelle Umsetzung

5. PÄDAGOGISCHE REFLEXIONSFRAGEN
   Generiere 3-5 konkrete Gesprächsanregungen:
   - Fragen zu kreativen Entscheidungen
   - Fragen zu künstlerischen Techniken und Konzepten
   - Fragen zu möglichen Experimenten

KRITISCHE REGELN:
- Schreibe auf Deutsch
- Verwende deklarative Sprache (als Fakten formulieren, nicht als Möglichkeiten)
- Fokus auf Lernmöglichkeiten, nicht auf Kritik
- Keine Phrasen wie "möglicherweise", "könnte sein", "schwer zu bestimmen"
- Generiere spezifische, umsetzbare Reflexionsfragen

FORMATIERUNG FÜR REFLEXIONSFRAGEN:
Am Ende der Analyse füge einen eigenen Abschnitt hinzu:

REFLEXIONSFRAGEN:
- [Konkrete Frage 1]
- [Konkrete Frage 2]
- [Konkrete Frage 3]
- [...]""",
        'en': """You are analyzing an AI-generated image in an arts education context.

Provide a structured analysis following this framework:

1. MATERIAL AND MEDIAL PROPERTIES
   - Identify the AI generation style and visual characteristics
   - Describe the technical implementation (rendering, texture, lighting)

2. PRE-ICONOGRAPHIC DESCRIPTION
   - Describe ALL visible elements: objects, figures, spatial relationships
   - Analyze composition, color palette, textures, spatial structure
   - Describe perspective and visual organization

3. ICONOGRAPHIC ANALYSIS
   - Interpret symbolic meanings and artistic techniques
   - Identify artistic styles or references

4. ICONOLOGICAL INTERPRETATION
   - Discuss cultural and conceptual meanings
   - Reflect on the visual realization

5. PEDAGOGICAL REFLECTION QUESTIONS
   Generate 3-5 specific conversation prompts:
   - Questions about creative decisions
   - Questions about artistic techniques and concepts
   - Questions about possible experiments

CRITICAL RULES:
- Write in English
- Use declarative language (state as facts, not possibilities)
- Focus on learning opportunities, not critique
- No phrases like "possibly", "might be", "difficult to determine"
- Generate specific, actionable reflection questions

FORMATTING FOR REFLECTION QUESTIONS:
At the end of the analysis, add a dedicated section:

REFLECTION QUESTIONS:
- [Specific question 1]
- [Specific question 2]
- [Specific question 3]
- [...]"""
    },

    'bildungstheoretisch': {
        # Jörissen/Marotzki - Structural media education (Bildungspotenziale)
        'de': """Du analysierst ein KI-generiertes Bild aus bildungstheoretischer Perspektive (nach Joerissen/Marotzki).

Erstelle eine strukturierte Analyse nach diesem Schema:

1. WISSENSBEZUG
   - Welches Weltwissen wird im Bild vorausgesetzt oder in Frage gestellt?
   - Welche Deutungsmuster werden bedient oder gebrochen?

2. HANDLUNGSBEZUG
   - Welche Handlungsoptionen eröffnet oder verschliesst das Bild?
   - Welche Handlungsraeume werden sichtbar, welche fehlen?

3. GRENZBEZUG (TENTATIVITAET)
   - Wo werden Grenzen des Darstellbaren sichtbar?
   - Welche Unbestimmtheiten, Ambiguitaeten oder Irritationen erzeugt das Bild?
   - Was entzieht sich der Darstellung?

4. BIOGRAPHIEBEZUG
   - Welche Selbst- und Fremdbilder werden angeboten?
   - Wie verhaelt sich das Bild zu moeglichen Lebensentwuerfen der Betrachtenden?

5. REFLEXIONSFRAGEN
   - 3-5 konkrete Gespraechsanregungen, die Schueler*innen zur Reflexion ueber das Verhaeltnis von Bild, Wissen und Selbst einladen

KRITISCHE REGELN:
- Schreibe auf Deutsch
- Deklarative Sprache (Fakten, nicht Moeglichkeiten)
- Fokus auf Bildungspotenziale, nicht auf aesthetische Bewertung
- Keine Phrasen wie "moeglicherweise", "koennte sein"
- Spezifische, umsetzbare Reflexionsfragen""",
        'en': """You are analyzing an AI-generated image from a structural media education perspective (following Joerissen/Marotzki).

Provide a structured analysis following this framework:

1. KNOWLEDGE DIMENSION
   - What world knowledge does the image presuppose or challenge?
   - Which interpretive patterns does it serve or disrupt?

2. ACTION DIMENSION
   - What possibilities for action does the image open or foreclose?
   - Which spaces for agency become visible, which are absent?

3. BOUNDARY DIMENSION (TENTATIVITY)
   - Where do limits of representability become visible?
   - What ambiguities, irritations, or indeterminacies does the image produce?
   - What escapes representation?

4. BIOGRAPHICAL DIMENSION
   - What self-images and images of others are offered?
   - How does the image relate to possible life designs of the viewers?

5. REFLECTION QUESTIONS
   - 3-5 specific conversation prompts inviting reflection on the relationship between image, knowledge, and self

CRITICAL RULES:
- Write in English
- Declarative language (state as facts, not possibilities)
- Focus on educational potentials, not aesthetic judgment
- No phrases like "possibly", "might be"
- Specific, actionable reflection questions"""
    },

    'ikonik': {
        # Imdahl - Iconic analysis (szenische Choreographie, planimetrische Komposition, Perspektivitaet)
        'de': """Du analysierst ein KI-generiertes Bild nach der Methode der Ikonik (Max Imdahl).

Erstelle eine strukturierte Analyse nach diesem Schema:

1. PLANIMETRISCHE KOMPOSITION
   - Analysiere die Flaechenkomposition: Linien, Formen, Flaechenverhaeltnisse auf der Bildebene
   - Welche geometrischen Strukturen organisieren das Bild?
   - Wie verhalten sich die Bildelemente zueinander in der Flaeche (nicht im Raum)?

2. SZENISCHE CHOREOGRAPHIE
   - Beschreibe die raeumliche Anordnung der Figuren und Objekte
   - Welche Bewegungsrichtungen, Blickachsen, Gesten sind erkennbar?
   - Welche Beziehungen zwischen den dargestellten Elementen werden durch ihre Anordnung hergestellt?

3. PERSPEKTIVISCHE PROJEKTION
   - Aus welcher Perspektive wird die Szene gezeigt?
   - Welche Nah-/Fernverhaeltnisse bestehen?
   - Wie positioniert die Perspektive die Betrachtenden zum Dargestellten?

4. IKONISCHE DICHTE
   - Was sagt das Bild, das sich NUR im Sehen erschliesst — nicht durch Benennung der Gegenstaende?
   - Welche Bedeutung entsteht aus dem Zusammenspiel von Komposition, Choreographie und Perspektive?
   - Was ist der spezifisch bildliche Sinn, der sich nicht in Sprache uebersetzen laesst?

5. REFLEXIONSFRAGEN
   - 3-5 konkrete Fragen, die zum genauen Hinsehen anregen (nicht zum Interpretieren)

KRITISCHE REGELN:
- Schreibe auf Deutsch
- Deklarative Sprache
- STRENG zwischen dem, was das Bild ZEIGT und dem, was wir WISSEN, trennen
- Das ikonische Sehen hat Vorrang vor dem wiedererkennenden Sehen
- Keine Phrasen wie "moeglicherweise", "koennte sein"
- Imdahls Kernfrage: Was zeigt das Bild, das nur das Bild zeigen kann?""",
        'en': """You are analyzing an AI-generated image using the method of Iconics (Max Imdahl).

Provide a structured analysis following this framework:

1. PLANIMETRIC COMPOSITION
   - Analyze the surface composition: lines, shapes, area relationships on the picture plane
   - What geometric structures organize the image?
   - How do the image elements relate to each other on the surface (not in space)?

2. SCENIC CHOREOGRAPHY
   - Describe the spatial arrangement of figures and objects
   - What directions of movement, lines of sight, and gestures are recognizable?
   - What relationships between the depicted elements are established through their arrangement?

3. PERSPECTIVAL PROJECTION
   - From what perspective is the scene shown?
   - What near/far relationships exist?
   - How does the perspective position the viewers in relation to what is depicted?

4. ICONIC DENSITY
   - What does the image say that can ONLY be grasped through seeing — not by naming the objects?
   - What meaning arises from the interplay of composition, choreography, and perspective?
   - What is the specifically pictorial sense that cannot be translated into language?

5. REFLECTION QUESTIONS
   - 3-5 specific questions that encourage close looking (not interpreting)

CRITICAL RULES:
- Write in English
- Declarative language
- STRICTLY separate what the image SHOWS from what we KNOW
- Iconic seeing takes precedence over recognitive seeing
- No phrases like "possibly", "might be"
- Imdahl's core question: What does the image show that only the image can show?"""
    },

    'ethisch': {
        # Ethical image analysis
        'de': """Du analysierst ein KI-generiertes Bild aus ethischer Perspektive.

Erstelle eine strukturierte Analyse nach diesem Schema:

1. REPRAESENTATION UND SICHTBARKEIT
   - Wer oder was wird dargestellt? Wer fehlt?
   - Welche Koerper, Identitaeten, Lebensformen werden sichtbar gemacht?
   - Welche Stereotype werden bedient oder gebrochen?

2. MACHTVERHAELTNISSE IM BILD
   - Welche Hierarchien sind in der Darstellung eingeschrieben?
   - Wer blickt, wer wird angeblickt? Wer handelt, wer ist passiv?
   - Welche Normalitaetsvorstellungen werden transportiert?

3. ENTSTEHUNGSBEDINGUNGEN
   - Was bedeutet es, dass dieses Bild von einer KI generiert wurde?
   - Welche Trainingsdaten koennten zu dieser Darstellung gefuehrt haben?
   - Wessen Arbeit steckt unsichtbar in diesem Bild (Trainingsdaten, Labels, Moderation)?

4. WIRKUNG UND VERANTWORTUNG
   - Welche Wirkung koennte dieses Bild auf verschiedene Betrachter*innen haben?
   - Wer traegt Verantwortung fuer das, was das Bild zeigt — der Promptgebende, das Modell, die Trainierenden?
   - Was waere ein ethisch reflektierter Umgang mit diesem Bild?

5. REFLEXIONSFRAGEN
   - 3-5 konkrete Fragen zu Gerechtigkeit, Verantwortung und dem eigenen Blick

KRITISCHE REGELN:
- Schreibe auf Deutsch
- Deklarative Sprache
- Keine moralische Belehrung — offene Fragen statt Urteile
- Ethik als Denkwerkzeug, nicht als Verbotsliste
- Keine Phrasen wie "moeglicherweise", "koennte sein"
- Konkret am Bild argumentieren, nicht abstrakt""",
        'en': """You are analyzing an AI-generated image from an ethical perspective.

Provide a structured analysis following this framework:

1. REPRESENTATION AND VISIBILITY
   - Who or what is depicted? Who is absent?
   - Which bodies, identities, and ways of life are made visible?
   - Which stereotypes are reinforced or challenged?

2. POWER RELATIONS IN THE IMAGE
   - What hierarchies are inscribed in the depiction?
   - Who looks, who is looked at? Who acts, who is passive?
   - What norms of normalcy are conveyed?

3. CONDITIONS OF PRODUCTION
   - What does it mean that this image was generated by an AI?
   - What training data might have led to this depiction?
   - Whose labor is invisibly embedded in this image (training data, labels, moderation)?

4. IMPACT AND RESPONSIBILITY
   - What effect could this image have on different viewers?
   - Who bears responsibility for what the image shows — the prompt author, the model, the trainers?
   - What would an ethically reflective approach to this image look like?

5. REFLECTION QUESTIONS
   - 3-5 specific questions about justice, responsibility, and one's own gaze

CRITICAL RULES:
- Write in English
- Declarative language
- No moral lecturing — open questions, not judgments
- Ethics as a tool for thinking, not a list of prohibitions
- No phrases like "possibly", "might be"
- Argue concretely from the image, not abstractly"""
    },

    'kritisch': {
        # Decolonial & critical media studies
        'de': """Du analysierst ein KI-generiertes Bild aus dekolonialer und medienkritischer Perspektive.

Erstelle eine strukturierte Analyse nach diesem Schema:

1. VISUELLE REGIME
   - Welchem visuellen Regime folgt das Bild? (westlich-perspektivisch, dokumentarisch, werblich, etc.)
   - Welche Sehkonventionen werden als "normal" vorausgesetzt?
   - Welche alternativen visuellen Traditionen werden ausgeblendet?

2. WISSENSORDNUNGEN
   - Welches Wissen wird im Bild als selbstverstaendlich behandelt?
   - Aus wessen Perspektive wird die Welt gezeigt?
   - Welche Klassifikationen und Kategorien strukturieren die Darstellung?

3. TRAININGSDATEN ALS ARCHIV
   - KI-Modelle sind trainiert auf Milliarden von Bildern — ueberwiegend aus dem anglophonen Internet
   - Welche visuelle Kultur reproduziert sich hier?
   - Was wurde durch die Datenselektion systematisch ausgeschlossen?
   - Welche "Ghost Workers" (Datenbereiniger, Labeler) haben dieses Bild moeglich gemacht?

4. GEGENBILDER
   - Was wuerde ein Bild desselben Themas aus einer nicht-westlichen Perspektive zeigen?
   - Welche visuellen Traditionen (z.B. islamische Geometrie, westafrikanische Textilmuster, indigene Kartographien) koennten einen alternativen Zugang eroeffnen?
   - Was kann dieses Modell NICHT darstellen — und warum?

5. REFLEXIONSFRAGEN
   - 3-5 konkrete Fragen zu Perspektive, Ausschluss und moeglichen Gegenbildern

KRITISCHE REGELN:
- Schreibe auf Deutsch
- Deklarative Sprache
- Kein eurozentrisches Framing als Ausgangspunkt
- Kulturneutrale Beispiele (nicht "Fruehstueckstisch" als Universalreferenz)
- Keine Phrasen wie "moeglicherweise", "koennte sein"
- Kritik heisst: Bedingungen des Sichtbaren analysieren, nicht moralisieren""",
        'en': """You are analyzing an AI-generated image from a decolonial and critical media studies perspective.

Provide a structured analysis following this framework:

1. VISUAL REGIMES
   - What visual regime does the image follow? (Western-perspectival, documentary, advertising, etc.)
   - What viewing conventions are assumed as "normal"?
   - What alternative visual traditions are excluded?

2. KNOWLEDGE ORDERS
   - What knowledge is treated as self-evident in the image?
   - From whose perspective is the world shown?
   - What classifications and categories structure the depiction?

3. TRAINING DATA AS ARCHIVE
   - AI models are trained on billions of images — predominantly from the anglophone internet
   - What visual culture reproduces itself here?
   - What was systematically excluded through data selection?
   - What "ghost workers" (data cleaners, labelers) made this image possible?

4. COUNTER-IMAGES
   - What would an image of the same subject look like from a non-Western perspective?
   - What visual traditions (e.g. Islamic geometry, West African textile patterns, indigenous cartographies) could open an alternative approach?
   - What can this model NOT depict — and why?

5. REFLECTION QUESTIONS
   - 3-5 specific questions about perspective, exclusion, and possible counter-images

CRITICAL RULES:
- Write in English
- Declarative language
- No Eurocentric framing as starting point
- Culturally neutral examples (not "breakfast table" as universal reference)
- No phrases like "possibly", "might be"
- Critique means: analyze the conditions of the visible, not moralize"""
    }
}

# ============================================================================
# STATIC CONFIGURATION (not in Settings UI — change only if you know what you're doing)
# ============================================================================

# Base paths
THIS_FILE = Path(__file__).resolve()
BASE_DIR = THIS_FILE.parent.parent
LOCAL_WORKFLOWS_DIR = BASE_DIR / "workflows"
PUBLIC_DIR = Path(__file__).parent.parent / "public" / "ai4artsed-frontend" / "dist"
EXPORTS_DIR = BASE_DIR / "exports"
JSON_STORAGE_DIR = EXPORTS_DIR / "json"
UPLOADS_TMP_DIR = EXPORTS_DIR / "uploads_tmp"  # Temporary image uploads for img2img

# DSGVO-safe provider fallback: if True, fallback only to DSGVO-safe providers.
# If False (international deployments), fallback may use any provider with credentials.
DSGVO_ONLY_FALLBACK = os.environ.get("DSGVO_ONLY_FALLBACK", "true").lower() == "true"

# DSGVO-safe cloud providers, ordered by preference (first = preferred).
# Only providers with valid credentials (.key file or env var) are used at runtime.
# Format: list of (provider_prefix, default_model) tuples.
DSGVO_SAFE_PROVIDERS = [
    ("mistral", "mistral/mistral-large-latest"),
    ("ionos", "ionos/meta-llama-3.1-70b-instruct"),
    ("mammouth", "mammouth/claude-sonnet-4-6"),
]

# ALL cloud providers with fallback models (used when DSGVO_ONLY_FALLBACK=False).
# Order = preference. Only those with valid credentials are used at runtime.
ALL_CLOUD_PROVIDERS = DSGVO_SAFE_PROVIDERS + [
    ("openai", "openai/gpt-4o"),
    ("anthropic", "anthropic/claude-sonnet-4-20250514"),
    ("openrouter", "openrouter/mistralai/mistral-large-latest"),
]
COMFYUI_PREFIX = "comfyui"
COMFYUI_PORT = "17804"  # AI4ArtsEd embedded ComfyUI (17801=prod, 17802=dev, 17803=GPU, 17804=ComfyUI)

# ============================================================================
# COMFYUI AUTO-RECOVERY CONFIGURATION
# ============================================================================
# Controls automatic startup of ComfyUI when needed
COMFYUI_AUTO_START = os.environ.get("COMFYUI_AUTO_START", "true").lower() == "true"
COMFYUI_STARTUP_TIMEOUT = int(os.environ.get("COMFYUI_STARTUP_TIMEOUT", "120"))  # seconds
COMFYUI_HEALTH_CHECK_INTERVAL = float(os.environ.get("COMFYUI_HEALTH_CHECK_INTERVAL", "2.0"))  # seconds


# ============================================================================
# TRITON INFERENCE SERVER CONFIGURATION (Session 149)
# ============================================================================
# NVIDIA Triton Inference Server for high-performance batched inference
# Enables multi-user workshops with dynamic batching
#
# To start Triton (Docker required):
#   docker run --gpus=all --rm \
#     -p8000:8000 -p8001:8001 -p8002:8002 \
#     -v ~/ai/triton_models:/models \
#     nvcr.io/nvidia/tritonserver:24.08-py3 \
#     tritonserver --model-repository=/models
#
TRITON_ENABLED = os.environ.get("TRITON_ENABLED", "false").lower() == "true"
TRITON_SERVER_URL = os.environ.get("TRITON_SERVER_URL", "localhost:8000")  # HTTP endpoint
TRITON_GRPC_URL = os.environ.get("TRITON_GRPC_URL", "localhost:8001")      # gRPC (faster for batch)
TRITON_METRICS_URL = os.environ.get("TRITON_METRICS_URL", "localhost:8002")  # Prometheus metrics
TRITON_MODEL_REPOSITORY = Path(os.environ.get("TRITON_MODEL_REPOSITORY", str(_AI_TOOLS_BASE / "triton_models")))
TRITON_TIMEOUT = int(os.environ.get("TRITON_TIMEOUT", "120"))  # seconds per request
TRITON_HEALTH_CHECK_INTERVAL = float(os.environ.get("TRITON_HEALTH_CHECK_INTERVAL", "5.0"))  # seconds

# ============================================================================
# DIFFUSERS BACKEND CONFIGURATION (Session 149)
# ============================================================================
# Direct HuggingFace Diffusers inference for maximum control
# Optional TensorRT acceleration for 2.3x speedup on NVIDIA GPUs
#
DIFFUSERS_ENABLED = os.environ.get("DIFFUSERS_ENABLED", "true").lower() == "true"  # Session 150: Default ON
# Default to None = use HuggingFace default cache (~/.cache/huggingface/hub)
_diffusers_cache_env = os.environ.get("DIFFUSERS_CACHE_DIR", "")
DIFFUSERS_CACHE_DIR = Path(_diffusers_cache_env) if _diffusers_cache_env else None
DIFFUSERS_USE_TENSORRT = os.environ.get("DIFFUSERS_USE_TENSORRT", "false").lower() == "true"
DIFFUSERS_TORCH_DTYPE = os.environ.get("DIFFUSERS_TORCH_DTYPE", "float16")  # float16, bfloat16, float32
DIFFUSERS_DEVICE = os.environ.get("DIFFUSERS_DEVICE", "cuda")  # cuda, cpu
DIFFUSERS_ENABLE_ATTENTION_SLICING = os.environ.get("DIFFUSERS_ENABLE_ATTENTION_SLICING", "true").lower() == "true"
DIFFUSERS_ENABLE_VAE_TILING = os.environ.get("DIFFUSERS_ENABLE_VAE_TILING", "false").lower() == "true"

# Minimum free VRAM (MB) to reserve for inference overhead (latents, VAE decode, scheduler)
DIFFUSERS_VRAM_RESERVE_MB = int(os.environ.get("DIFFUSERS_VRAM_RESERVE_MB", "3072"))

# Pre-compiled TensorRT models on HuggingFace (if available)
DIFFUSERS_TENSORRT_MODELS = {
    "sd35_large": "stabilityai/stable-diffusion-3.5-large-tensorrt",
    "sd35_medium": "stabilityai/stable-diffusion-3.5-medium-tensorrt",
}

# ============================================================================
# HEARTMULA BACKEND CONFIGURATION
# ============================================================================
# HeartMuLa - Music generation from lyrics and tags using LLM + Audio Codec
# Model: HeartMuLa 3B (open-source, multilingual)
# VRAM: ~12-16GB recommended
#
HEARTMULA_ENABLED = os.environ.get("HEARTMULA_ENABLED", "true").lower() == "true"
HEARTMULA_MODEL_PATH = os.environ.get(
    "HEARTMULA_MODEL_PATH",
    str(_AI_TOOLS_BASE / "heartlib" / "ckpt")
)
HEARTMULA_VERSION = os.environ.get("HEARTMULA_VERSION", "3B")
HEARTMULA_LAZY_LOAD = os.environ.get("HEARTMULA_LAZY_LOAD", "true").lower() == "true"
HEARTMULA_DEVICE = os.environ.get("HEARTMULA_DEVICE", "cuda")  # cuda, cpu

# ============================================================================
# GPU SERVICE (Media inference only: Diffusers, HeartMuLa, StableAudio)
# ============================================================================
# GPU Service handles media generation only. LLM inference goes directly
# to Ollama via LLMClient — NOT through GPU Service.
#
GPU_SERVICE_URL = os.environ.get("GPU_SERVICE_URL", "http://localhost:17803")
GPU_SERVICE_TIMEOUT_DEFAULT = 60      # Health checks, status
GPU_SERVICE_TIMEOUT_IMAGE = 120       # SD3.5, SDXL
GPU_SERVICE_TIMEOUT_VIDEO = 1500      # Wan 2.1 14B (~20 min)
GPU_SERVICE_TIMEOUT_MUSIC = 300       # HeartMuLa
GPU_SERVICE_TIMEOUT_AUDIO = 300       # Stable Audio
GPU_SERVICE_TIMEOUT_3D = 300          # Hunyuan3D-2 mesh generation
GPU_SERVICE_TIMEOUT = GPU_SERVICE_TIMEOUT_DEFAULT  # Backward compat

# --- Blender (headless mesh rendering) ---
BLENDER_PATH = os.environ.get("BLENDER_PATH", "/usr/bin/blender")
BLENDER_SCRIPTS_PATH = os.environ.get("BLENDER_SCRIPTS_PATH", str(Path(__file__).parent / "blender_scripts"))

# --- Hunyuan3D-2 ---
HUNYUAN3D_MODEL_ID = os.environ.get("HUNYUAN3D_MODEL_ID", "tencent/Hunyuan3D-2")

# External LLM API timeouts (connect, read) in seconds
LLM_API_TIMEOUT = (10, 90)            # 10s connect (fail fast if unreachable), 90s read (reasoning models need time)

# Ollama LLM timeouts
OLLAMA_TIMEOUT_SAFETY = 30            # Safety verify (small model, short prompt)
OLLAMA_TIMEOUT_DEFAULT = 120          # Standard LLM calls

# Ollama concurrency limit (Python-side semaphore).
# NOTE: Ollama server-side concurrency (OLLAMA_NUM_PARALLEL) must be configured
# separately in the systemd unit / environment. This only caps the DevServer side.
OLLAMA_MAX_CONCURRENT = int(os.environ.get("OLLAMA_MAX_CONCURRENT", "6"))

# Feature Flags
ENABLE_VALIDATION_PIPELINE = True
ENABLE_AUTO_EXPORT = True
ENABLE_TEXT_STREAMING = True  # Enable character-by-character text streaming (typewriter effect)
TEXT_STREAM_SPEED_MS = 30  # Milliseconds per character in frontend typewriter display (~33 chars/sec)
NO_TRANSLATE = False  # Set to True to skip translation of prompts
ENABLE_LEGACY_MIGRATION = os.environ.get("ENABLE_LEGACY_MIGRATION", "true").lower() == "true"  # Auto-migrate legacy export folders on startup
LOOP_GENERATION = 1
LOOP_COMFYUI = 1

# ----------------------------------------------------------------------------
# WIKIPEDIA RESEARCH - Fundamental Interception Capability
# ----------------------------------------------------------------------------
# Enables LLM to fetch Wikipedia content during prompt interception using
# <wiki lang="de">term</wiki> markers in its output.
#
# Language Detection: Default language is auto-detected from user's input.
# WIKIPEDIA_FALLBACK_LANGUAGE is only used when input language cannot be determined.
#
WIKIPEDIA_MAX_ITERATIONS = int(os.environ.get("WIKIPEDIA_MAX_ITERATIONS", "3"))
WIKIPEDIA_MAX_LOOKUPS_PER_ITERATION = int(os.environ.get("WIKIPEDIA_MAX_LOOKUPS_PER_ITERATION", "5"))
WIKIPEDIA_FALLBACK_LANGUAGE = os.environ.get("WIKIPEDIA_FALLBACK_LANGUAGE", "de")  # Fallback when input lang unknown
WIKIPEDIA_CACHE_TTL = int(os.environ.get("WIKIPEDIA_CACHE_TTL", "3600"))  # Cache TTL in seconds (default 1h)

# Translation Prompt
TRANSLATION_PROMPT = """Translate the following text to English. CRITICAL RULES:
1. Preserve ALL brackets exactly as they appear: (), [], {{}}, and especially triple brackets ((()))
2. Do NOT remove or modify any brackets or parentheses
3. Translate the prompt into English with maximal semantic preservation. Maintain the original structure, and preserve all culturally specific terms or non-translatable phrases in their original form. 
4. Do not translate proper names, ritual terms, or material names unless they have a common English usage. Instead, leave them untranslated and preserve their position. 
5. Do not paraphrase, interpret, or summarize. Do not add any comments or explanations.
6. Do NOT add any meta-comments or explanations
7. Output ONLY the translated text, nothing else
8. If text is already in English, return it unchanged!
9. Maintain the exact structure and formatting

Text to translate:

{text}"""

ANALYSIS_SYSTEM_PROMPT = """You are an art historian providing a formal image analysis. You are not from a western country. You do not redpruce western patterns of observation. Follow this exact structure:

1. Material and medial properties: State the specific media type (oil painting, photograph, digital image, sculpture, etc.)

2. Pre-iconographic description: Describe ONLY what is directly visible:
   - Objects, figures, settings
   - Spatial relationships and composition
   - Colors, textures, forms
   - Perspective and visual structure

3. Iconographic analysis: Interpret symbolic meanings and cultural references based on what is visible. State interpretations as facts, not possibilities.

4. Iconological interpretation: Present the cultural and conceptual meanings as direct statements.

CRITICAL RULES:
- NEVER use phrases like "it could be", "possibly", "might be", "difficult to determine", "without additional context"
- NEVER apologize or explain limitations
- NEVER mention what you cannot see or determine
- State ALL interpretations as facts, not suggestions
- Write in complete, declarative sentences
- If something is unclear, make your best interpretation and state it as fact
- NEVER end with disclaimers like "Please note", "These analyses", "should be considered", "interpretations rather than"
- NEVER add meta-comments about your analysis
- END your response after completing step 4, with NO additional text"""

# Model Mapping Configuration
OLLAMA_TO_OPENROUTER_MAP = {
    # Maps a local model's base name to its OpenRouter equivalent.
    "deepcoder": "agentica-org/deepcoder-14b-preview",
    "deepseek-r1": "deepseek/deepseek-r1",
    "gemma-2-9b-it": "google/gemma-2-9b-it",
    "gemma-2-27b-it": "google/gemma-2-27b-it",
    "gemma-3-1b-it": "google/gemma-3-1b-it",
    "gemma-3-4b-it": "google/gemma-3-4b-it",
    "gemma-3-12b-it": "google/gemma-3-12b-it",
    "gemma-3-27b-it": "google/gemma-3-27b-it",
    "gemma-3n-e4b-it": "google/gemma-3n-e4b-it",
    "shieldgemma-9b": "google/shieldgemma-9b",
    "llava": "liuhaotian/llava-7b",
    "llava:13b": "liuhaotian/llava-13b",
    "llama-3.1-8b-instruct": "meta-llama/llama-3.1-8b-instruct",
    "llama-3.2-1b-instruct": "meta-llama/llama-3.2-1b-instruct",
    "llama-3.3-8b-instruct": "meta-llama/llama-3.3-8b-instruct",
    "llama-guard-3-1b": "meta-llama/llama-guard-3-1b",
    "llama-guard-3-8b": "meta-llama/llama-guard-3-8b",
    "codestral": "mistralai/codestral",
    "mistral-7b": "mistralai/mistral-7b",
    "mistral-nemo": "mistralai/mistral-nemo",
    "mistral-small:24b": "mistralai/mistral-small-24b",
    "mixtral-8x7b-instruct": "mistralai/mixtral-8x7b-instruct",
    "ministral-8b": "mistralai/ministral-8b",
    "phi-4": "microsoft/phi-4",
    "qwen2.5-translator": "qwen/qwen2.5-translator",
    "qwen2.5-32b-instruct": "qwen/qwen2.5-32b-instruct",
    "qwen3-8b": "qwen/qwen3-8b",
    "qwen3-14b": "qwen/qwen3-14b",
    "qwen3-30b-a3b": "qwen/qwen3-30b-a3b",
    "qwq-32b": "qwen/qwq-32b",
    "sailor2-20b": "sailor2/sailor2-20b",
}

OPENROUTER_TO_OLLAMA_MAP = {v: k for k, v in OLLAMA_TO_OPENROUTER_MAP.items()}

# Cache Configuration
PROMPT_CACHE = {}

# API Cache Control (for Browser Caching)
# Development: Set to True to disable all API caching (aggressive no-cache headers)
# Production: Set to False to enable intelligent caching (configs/models: 5min cache)
DISABLE_API_CACHE = os.environ.get("DISABLE_API_CACHE", "true").lower() == "true"

# Cache strategy for production (only applies when DISABLE_API_CACHE=False)
# Only GET requests to these routes will be cached. POST/SSE are never cached by browsers.
CACHE_STRATEGY = {
    "/api/config/": "public, max-age=300",         # Configs: 5 minutes
    "/pipeline_configs_": "public, max-age=300",   # Metadata: 5 minutes
    "/api/models/": "public, max-age=300",         # Models: 5 minutes (matches backend cache TTL)
}

# Logging Configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Request Timeouts (in seconds)
OLLAMA_TIMEOUT = 300  # 5 minutes for heavy models
COMFYUI_TIMEOUT = 480  # 8 minutes for data-rich workflows
POLLING_TIMEOUT = 15
MEDIA_DOWNLOAD_TIMEOUT = 30

# ComfyUI queue management — reject submissions when queue is too deep.
# Shallow queue = fast "busy" feedback (good UX) vs deep queue = long silent waits + timeouts.
# At depth 10 with avg ~45s/job, worst-case wait is ~450s (within 480s COMFYUI_TIMEOUT).
# Frontend shows friendly i18n message on queue-full (generationError.busy).
COMFYUI_MAX_QUEUE_DEPTH = int(os.environ.get("COMFYUI_MAX_QUEUE_DEPTH", "10"))

# Model Path Resolution Configuration
ENABLE_MODEL_PATH_RESOLUTION = True  # ENABLED: ComfyUI uses OfficialStableDiffusion/ prefix format
MODEL_RESOLUTION_FALLBACK = True      # Fallback to original names if resolution fails

# Base paths for model resolution (configure these to your actual paths)
# Note: _SERVER_BASE and _AI_TOOLS_BASE are defined at top of file
COMFYUI_BASE_PATH = os.environ.get("COMFYUI_PATH", str(_SERVER_BASE / "dlbackend" / "ComfyUI"))

# LoRA Training Paths (Kohya SS)
KOHYA_DIR = Path(os.environ.get("KOHYA_DIR", str(_AI_TOOLS_BASE / "kohya_ss_new")))
LORA_OUTPUT_DIR = Path(os.environ.get("LORA_OUTPUT_DIR", str(Path(COMFYUI_BASE_PATH) / "models" / "loras")))
TRAINING_DATASET_DIR = KOHYA_DIR / "dataset"
TRAINING_LOG_DIR = KOHYA_DIR / "logs"
# Note: Output prefix (e.g. "sd35_") is determined by the model-specific config generator in training_service.py

# Auto-Captioning for LoRA Training (VLM generates per-image descriptions)
CAPTION_VLM_MODEL = "qwen3-vl:32b"
CAPTION_CLEANUP_MODEL = "mistral-nemo:latest"  # Non-thinking model to extract caption from VLM reasoning
CAPTION_ENABLED = True

# Model paths for training and ComfyUI inference
_COMFYUI_MODELS_PATH = Path(COMFYUI_BASE_PATH) / "models"
SD35_LARGE_MODEL_PATH = _COMFYUI_MODELS_PATH / "checkpoints" / "OfficialStableDiffusion" / "sd3.5_large.safetensors"
CLIP_L_PATH = _COMFYUI_MODELS_PATH / "clip" / "clip_l.safetensors"
CLIP_G_PATH = _COMFYUI_MODELS_PATH / "clip" / "clip_g.safetensors"
T5XXL_PATH = _COMFYUI_MODELS_PATH / "clip" / "t5xxl_fp16.safetensors"

# Default Negative Terms Configuration
DEFAULT_NEGATIVE_TERMS = "blurry, bad quality, worst quality, low quality, low resolution, extra limbs, extra fingers, distorted, deformed, jpeg artifacts, watermark"

# Safety Filter Configuration (Used by Stage 3 safety check)
SAFETY_NEGATIVE_TERMS = {
    "kids": [
        # Violence & Death
        "violence", "violent", "execution", "killing", "murder", "death", "corpse",
        "torture", "pain", "suffering", "injury", "wound", "bleeding",
        "blood", "bloody", "gore", "gory", "mutilation", "dismemberment",
        # Mental Health
        "despair", "suicide", "suicidal", "self-harm", "depression",
        # Horror & Scary
        "horror", "scary", "frightening", "terror", "nightmare", "disturbing",
        "demon", "zombie", "skeleton", "skull", "evil",
        "haunted", "creepy", "eerie", "sinister", "dark", "macabre",
        # Sexual Content
        "nude", "naked", "nsfw", "sexual", "rape", "pornographic",
        "genital", "abuse",
    ],
    "youth": [
        # Extreme Violence
        "explicit", "hardcore", "brutal", "savage", "cruelty", "sadistic",
        # Explicit Sexual
        "pornographic", "sexual", "nsfw", "rape", "abuse",
        "genitals", "penis", "vagina",
        # Self-Harm
        "self-harm", "suicide", "cutting",
    ],
    "adult": [
        # Only illegal content under German law (§86a StGB)
        "nazi", "swastika", "hakenkreuz", "ss-runen", "hitler",
        "isis", "al-qaeda", "terrorist symbols",
        # Explicit illegal content
        "child", "minor", "underage",
    ],
    "research": []  # Research/advanced use - NO filtering
}

# Backwards compatibility
KIDS_SAFETY_NEGATIVE_TERMS = SAFETY_NEGATIVE_TERMS["kids"]

# Workflow Selection Configuration
WORKFLOW_SELECTION = "user"  # "user", "fixed", "system"
FIXED_WORKFLOW = "model/ai4artsed_Stable-Diffusion-3.5_2507152202.json"  # Only used when WORKFLOW_SELECTION = "fixed"

# System mode: Random workflow selection from specified folders
# These correspond directly to folder names under /workflows_legacy/
SYSTEM_WORKFLOW_FOLDERS = ["aesthetics", "semantics", "arts"]

# ============================================================================
# LORA CONFIGURATION (Temporary - will be replaced by dynamic source)
# ============================================================================
# Format: List of dicts with 'name' and 'strength'
# 'name' = filename without path (file must be in dlbackend/ComfyUI/models/loras/)
# Set to empty list [] to disable LoRA injection
#
LORA_TRIGGERS = [
    # Empty by default - LoRAs are specified per-config in meta.loras
    # Example: {"name": "my_lora.safetensors", "strength": 1.0}
]
