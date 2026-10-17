"""
Central configuration file for the AI4ArtsEd Web Server

Runtime-configurable settings live in _SETTINGS_DEFAULTS (bottom of this section).
Actual values come from user_settings.json, editable via Settings UI.
"""
import os
from pathlib import Path

# Base paths (defined early because used throughout config)
_SERVER_BASE = Path(__file__).parent.parent  # devserver parent = ai4artsed_development
_AI_TOOLS_BASE = Path(os.environ.get("AI_TOOLS_BASE", str(_SERVER_BASE)))  # default: nested under repo (same convention as dlbackend/ComfyUI); override only for external partitions

# ============================================================================
# SERVER SETTINGS (static — not in Settings UI)
# ============================================================================
HOST = "0.0.0.0"
PORT = 17802  # Development: 17802, Production: 17801
# One participant's generation now parks a thread for the queue wait as well as
# the render, so a workshop group can hold a dozen at once — and this same pool
# serves the pages, the assets and the polls of everyone who is waiting.
THREADS = 64

# Warm the next model on the card while the current run is still working.
# The gate decides whether there is measured room; this only switches the
# worker that acts on it. See my_app/services/gpu_warm_ahead.py.
GPU_WARM_AHEAD = os.environ.get("GPU_WARM_AHEAD", "true").lower() == "true"

# --- GPU admission (plant-wide serialization of heavy operations) ---
# One heavy operation on the card at a time, across processes: every ComfyUI
# run, the VoxCPM worker, Blender and a LoRA training hold a lease on the gate
# for their length. The gate lives in this process since stage 7 of the move
# to ComfyUI (my_app/services/gpu_gate.py); until then it was a module of the
# GPU service, and these settings stood in gpu_service/config.py under the
# same names. All overridable by environment.
# The hard ceiling on one wait — a backstop against a wedged plant, NOT a
# patience budget. Whoever waits keeps their place; a wait that ends in a refusal
# would send them to the back of the line on the next press, while everybody who
# arrived later moves up past them. So this sits far above any real queue.
GPU_ADMISSION_ACQUIRE_TIMEOUT_S = float(os.environ.get("GPU_ADMISSION_ACQUIRE_TIMEOUT_S", "5400"))
# Starting assumption for how long one heavy run takes, until the gate has
# measured a few. Replaced by a moving average of real holds, and REPORTED only:
# nobody is turned away on an estimate.
GPU_ADMISSION_ASSUMED_RUN_S = float(os.environ.get("GPU_ADMISSION_ASSUMED_RUN_S", "90"))
# Generously above the worst delay a heartbeat can suffer on a busy thread
# pool: a lease reaped while its generation is still running means two
# processes allocate at once, which is the failure this whole gate exists to
# prevent.
GPU_ADMISSION_HEARTBEAT_TIMEOUT_S = float(os.environ.get("GPU_ADMISSION_HEARTBEAT_TIMEOUT_S", "120"))
# A lease whose holder never reported in at all is a holder that left before
# the token reached it (a client that dropped its connection while it waited).
# It is collected after this grace instead of the full timeout above: the
# in-process holders beat every 10 s, the GPU service every 5 s.
GPU_ADMISSION_FIRST_BEAT_GRACE_S = float(os.environ.get("GPU_ADMISSION_FIRST_BEAT_GRACE_S", "30"))
GPU_ADMISSION_REAPER_INTERVAL_S = float(os.environ.get("GPU_ADMISSION_REAPER_INTERVAL_S", "5"))
# A waiting request parks a worker thread, so there has to be an end somewhere —
# but this is a limit of THREADS above, not a group size, and it is set high
# enough that an ordinary course never meets it. Turning somebody away costs them
# their place in the line, so this is a last resort against a
# silted-up pool, not a policy about how many may take part.
GPU_ADMISSION_MAX_WAITERS = int(os.environ.get("GPU_ADMISSION_MAX_WAITERS", "40"))
# How many consecutive unanswered sensor readings count as a lost sensor.
GPU_ADMISSION_BLIND_SAMPLES = int(os.environ.get("GPU_ADMISSION_BLIND_SAMPLES", "3"))
# How long the gate reads the card after asking ComfyUI to unload its models,
# waiting for the room an operation asked for. ComfyUI answers /free at once
# and unloads on its prompt worker, after the prompt that is executing if one
# is; the driver reports the memory back once that has happened.
GPU_ADMISSION_FREE_WAIT_S = float(os.environ.get("GPU_ADMISSION_FREE_WAIT_S", "30"))

# --- Dequeue policy: group runs that need the same model ---
# A model swap costs a load (SD3.5 Large measured at 110 s) and everybody still
# in line pays it, so a run whose model is already loaded may go ahead of one
# that would force a swap. Bounded in both directions: nobody is passed more
# than MAX_OVERTAKES times, and nobody waits longer than AFFINITY_MAX_WAIT_S
# before going next regardless of what is resident. Set AFFINITY=false for
# strict arrival order.
GPU_ADMISSION_AFFINITY = os.environ.get("GPU_ADMISSION_AFFINITY", "true").lower() == "true"
GPU_ADMISSION_MAX_OVERTAKES = int(os.environ.get("GPU_ADMISSION_MAX_OVERTAKES", "3"))
GPU_ADMISSION_AFFINITY_MAX_WAIT_S = float(os.environ.get("GPU_ADMISSION_AFFINITY_MAX_WAIT_S", "300"))
# A load and the run it was made for are one thing. The load releases the slot
# a moment before its own run asks for it, and without this the card starts a
# different model in exactly that moment — the load is then paid for nothing.
GPU_ADMISSION_POST_LOAD_RESERVE_S = float(os.environ.get("GPU_ADMISSION_POST_LOAD_RESERVE_S", "5"))

# --- Speculative prefetch --- OFF, and it must stay off until three things
# are fixed. While one run holds the card, the model the NEXT run needs could
# be loaded beside it, so its turn starts warm. That deliberately allocates
# next to a running operation — the one thing the gate otherwise prevents —
# and the arithmetic that was supposed to make it safe does not hold:
#
#   1. The measured footprint is a LOWER BOUND, not a size. free-at-admit is
#      read before the run evicts, the low-water mark is sampled every 5 s and
#      usually misses the peak, and a model that was already resident measures
#      only its activations. The live file has held 4802 MB, past the trust
#      threshold, for a model whose measured peak is 30253 MiB.
#   2. A ComfyUI warm is QUEUED, not executed. ComfyUI runs it minutes later,
#      after the gate has already admitted somebody else against the free
#      memory the warm had not taken yet.
#   3. get_queue_status() answers total=0 on any error, including a timeout
#      while ComfyUI streams weights off disk — so "the warm is done" is
#      reported while it is still loading, and the claim is released.
#
# Turning this on before those are settled reproduces the OOM the gate exists
# to prevent. Everything else here — the affinity ordering, the post-load
# reservation, the measured statistics, the forecast — runs without it.
GPU_ADMISSION_PREFETCH = os.environ.get("GPU_ADMISSION_PREFETCH", "false").lower() == "true"
GPU_ADMISSION_PREFETCH_HEADROOM_MB = float(os.environ.get("GPU_ADMISSION_PREFETCH_HEADROOM_MB", "10240"))
GPU_ADMISSION_PREFETCH_MIN_REMAINING_S = float(os.environ.get("GPU_ADMISSION_PREFETCH_MIN_REMAINING_S", "45"))

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
#   "local/model-name" → Local LLM
#   "<provider>/<the path the provider publishes>" → an external provider; the
#   names are the keys of config/llm_providers.json
#
_SETTINGS_DEFAULTS = {
    # UI & safety defaults (non-model)
    'UI_MODE': 'medium',
    'DEFAULT_SAFETY_LEVEL': 'kids',
    'DEFAULT_LANGUAGE': 'de',
    'DEFAULT_INTERCEPTION_CONFIG': 'user_defined',
    'EXTERNAL_LLM_PROVIDER': 'none',
    'DSGVO_CONFORMITY': True,
    # Model roles — NO hardcoded model names. Actual values come from user_settings.json.
    # Empty strings here ensure hasattr() works for import compatibility.
    # If user_settings.json is missing, server will NOT start (see __init__.py).
    'STAGE1_TEXT_MODEL': '',
    'STAGE2_INTERCEPTION_MODEL': '',
    'STAGE2_OPTIMIZATION_MODEL': '',
    'STAGE3_MODEL': '',
    'CHAT_HELPER_MODEL': '',
    # Knowledge Verdichtung (BIBLIOTHEK.md §3): the strong model that condenses a
    # raw document into the compact library form. Empty here -> resolved after
    # settings load to the strongest available STAGE model (see the resolver at
    # the bottom of reload_user_settings). The UNESCO corpus is public / not
    # DSGVO-critical, so a strong cloud model is appropriate — NOT a tiny local.
    'KNOWLEDGE_PROCESSING_MODEL': '',
    # Query translation for the library search (cross-lingual recall): a
    # micro-task served by the LOCAL Ollama line via the GPU service —
    # llm_service cannot route provider-prefixed cloud models.
    'KNOWLEDGE_QUERY_TRANSLATION_MODEL': 'qwen3:4b',
    'PERSONA_MODEL': '',
    'RESONA_MODEL': '',
    'CODING_MODEL': '',
    'IMAGE_ANALYSIS_MODEL': '',
    'SAFETY_MODEL': '',
    # AI-Origin Disclosure (EU AI Act Art. 50). Nested dict, see watermark_service.py.
    # Metadata layer is the compliance core (machine-readable AI-origin marker).
    # Visible layer is optional and deployment-configurable.
    'WATERMARK': {
        'metadata_image': True,
        'metadata_video': True,
        'metadata_audio': True,
        'metadata_3d': True,
        'metadata_svg': True,
        'metadata_code': True,
        'metadata_include_model': True,
        'metadata_include_date': True,
        'metadata_include_prompt': False,
        'metadata_include_seed': False,
        'software_name': '',
        'visible_image': False,
        'visible_video': False,
        'visible_text': 'AI-generated',
        'visible_position': 'bottom-right',
        'visible_opacity': 0.3,
        'invisible_image': False,
        'invisible_payload': 'AI-generated',
    },
}

# UI_MODE was named after age groups (kids/youth/expert) until 2026-08-12 and
# was read as an age setting, which it never was — it decides how much the
# interface shows and how long a text it asks for. The old names stay readable
# so an installation that has not been resaved keeps its level instead of
# falling through to "no limit".
_UI_MODE_LEGACY = {'kids': 'easy', 'youth': 'medium'}


def normalise_ui_mode(value) -> str:
    """The current name for a UI_MODE value, legacy names included."""
    if not isinstance(value, str):
        return ''
    value = value.strip().lower()
    return _UI_MODE_LEGACY.get(value, value)


# Pre-initialize module globals for imports (overwritten by reload_user_settings at startup)
for _k, _v in _SETTINGS_DEFAULTS.items():
    globals()[_k] = _v
del _k, _v

# Populated by reload_user_settings(): the subset of _SETTINGS_DEFAULTS keys that
# were explicitly present in user_settings.json (vs. silently running on the coded
# default above). Surfaced by GET /api/settings/ so a default in use is never silent.
_USER_CONFIGURED_KEYS = set()


# Stage 5: Image Analysis Prompts (4 Theoretical Frameworks)
# Die vier Leserahmen stehen als Text in schemas/reading_frames/ und werden
# ueber my_app/services/reading_frames.py gelesen: was ein Rahmen vom Bild
# wissen will, ist Prompt-Inhalt und gehoert dorthin, wo Prompts stehen.

# ============================================================================
# STATIC CONFIGURATION (not in Settings UI — change only if you know what you're doing)
# ============================================================================

# Base paths
THIS_FILE = Path(__file__).resolve()
BASE_DIR = THIS_FILE.parent.parent
PUBLIC_DIR = Path(__file__).parent.parent / "public" / "ai4artsed-frontend" / "dist"
EXPORTS_DIR = BASE_DIR / "exports"
JSON_STORAGE_DIR = EXPORTS_DIR / "json"
UPLOADS_TMP_DIR = EXPORTS_DIR / "uploads_tmp"  # Temporary image uploads for img2img
# Scratch for readings, deliberately NOT under uploads_tmp: 2_start_comfyui.sh
# empties that directory wholesale, and the DevServer starts ComfyUI itself.
ANALYSIS_TMP_DIR = EXPORTS_DIR / "analysis_tmp"

# ============================================================================
# KNOWLEDGE LIBRARY (Wissensbibliothek — Tier F committed, Tier O operator)
# ============================================================================
# Two roots, decided 2026-10-10 (finding S-055 of the code review of 2026-10-10). EXPORTS_DIR and JSON_STORAGE_DIR
# above, at the repository root, hold the run data (the recorder, the legacy
# migration, the session routes, the thumbnails). The tree under devserver/
# holds what the knowledge scripts (devserver/scripts/knowledge_ingest.py,
# build_knowledge_index.py), the knowledge library, the Resona stores and the
# canvas stores write (devserver/exports), and the translation cache, the
# usage log and the BBQ runs (devserver/data). Merging the two would move
# data on every installed machine. A service names its root from HERE and
# never derives it from its own __file__ (finding S-077 of the code review of 2026-10-10).
DEVSERVER_DIR = THIS_FILE.parent  # .../ai4artsed_development/devserver
DEVSERVER_EXPORTS_DIR = DEVSERVER_DIR / "exports"
DEVSERVER_JSON_DIR = DEVSERVER_EXPORTS_DIR / "json"
DEVSERVER_DATA_DIR = DEVSERVER_DIR / "data"
KNOWLEDGE_LIBRARY_DIR = DEVSERVER_DIR / "my_app" / "knowledge" / "library"      # Tier F (committed)
KNOWLEDGE_TIER_O_DIR = DEVSERVER_EXPORTS_DIR / "knowledge_library"              # Tier O uploads + derivatives (gitignored)
KNOWLEDGE_ORIGINALS_DIR = BASE_DIR / "resources" / "knowledge_originals"         # original PDFs (gitignored, resources/-idiom)
KNOWLEDGE_INDEX_DB = DEVSERVER_EXPORTS_DIR / "knowledge_index.sqlite"           # FTS index (gitignored, rebuildable)
KNOWLEDGE_GLOSSARY_OVERRIDES = DEVSERVER_JSON_DIR / "knowledge_glossary_overrides.json"  # operator glossary redaction
KNOWLEDGE_INGEST_SCRIPT = DEVSERVER_DIR / "scripts" / "knowledge_ingest.py"
KNOWLEDGE_INDEX_SCRIPT = DEVSERVER_DIR / "scripts" / "build_knowledge_index.py"

# Interpreter for the OFFLINE ingest (Docling + torch live in a separate venv so
# they are NEVER a devserver runtime dependency, BIBLIOTHEK.md §3). Default is
# the documented ingest venv on the GPU host (~/ai/venvs/knowledge/bin/python);
# override via env for other layouts. If the interpreter is missing at runtime
# the ingest job fails with a clear "Docling-venv fehlt" log line (Deployment
# failure class), it does NOT crash the server.
KNOWLEDGE_INGEST_PYTHON = os.environ.get(
    "KNOWLEDGE_INGEST_PYTHON",
    str(Path.home() / "ai" / "venvs" / "knowledge" / "bin" / "python"),
)
# Interpreter for the index rebuild (stdlib-only script — the devserver's own
# venv is sufficient; sibling "venv" of the repo root, per PATH convention).
KNOWLEDGE_INDEX_PYTHON = os.environ.get(
    "KNOWLEDGE_INDEX_PYTHON",
    str(BASE_DIR / "venv" / "bin" / "python"),
)

# Env override for the Verdichtung model (ENV-override idiom): a value here wins
# over user_settings.json and the STAGE fallback below. Empty by default.
KNOWLEDGE_PROCESSING_MODEL_ENV = os.environ.get("AI4ARTSED_KNOWLEDGE_PROCESSING_MODEL", "").strip()


def resolve_knowledge_processing_model() -> str:
    """The effective model string for knowledge Verdichtung, in precedence order:
      1) AI4ARTSED_KNOWLEDGE_PROCESSING_MODEL (env),
      2) KNOWLEDGE_PROCESSING_MODEL (user_settings.json / Settings UI),
      3) the strongest available STAGE model (STAGE2_INTERCEPTION → STAGE1 →
         STAGE3 → STAGE4), 4) CHAT_HELPER_MODEL.
    Called by reload_user_settings after settings are applied so the resolved
    value lands on config.KNOWLEDGE_PROCESSING_MODEL for the role lookup."""
    for cand in (
        KNOWLEDGE_PROCESSING_MODEL_ENV,
        globals().get("KNOWLEDGE_PROCESSING_MODEL", ""),
        globals().get("STAGE2_INTERCEPTION_MODEL", ""),
        globals().get("STAGE1_TEXT_MODEL", ""),
        globals().get("STAGE3_MODEL", ""),
        globals().get("CHAT_HELPER_MODEL", ""),
    ):
        if (cand or "").strip():
            return cand.strip()
    return ""

# There is no hardcoded provider fallback. Two lists used to live here, naming a
# provider order and one model literal per provider; they let a failed request answer
# from a different model than the one that was asked for, without the caller learning
# which. The only fallback the platform has is the chat chain in
# my_app/routes/chat_routes.py (build_model_candidate_chain), and that one reads
# hardware_matrix.json -- provider order, per-provider models and the DSGVO gate all
# come from the matrix. Do not re-add a list here.
COMFYUI_PORT = "17804"  # AI4ArtsEd embedded ComfyUI (17801=prod, 17802=dev, 17803=GPU, 17804=ComfyUI)
# The base URL the DevServer reaches ComfyUI under; twelve sites spelled it out
# from the port until 2026-10-10. Not overridable on its own: the manager
# (my_app/services/comfyui_manager.py) starts ComfyUI on COMFYUI_PORT, and a
# URL pointing elsewhere would point past the process it starts.
COMFYUI_URL = f"http://127.0.0.1:{COMFYUI_PORT}"

# ============================================================================
# COMFYUI AUTO-RECOVERY CONFIGURATION
# ============================================================================
# Controls automatic startup of ComfyUI when needed
COMFYUI_AUTO_START = os.environ.get("COMFYUI_AUTO_START", "true").lower() == "true"
COMFYUI_STARTUP_TIMEOUT = int(os.environ.get("COMFYUI_STARTUP_TIMEOUT", "120"))  # seconds
COMFYUI_HEALTH_CHECK_INTERVAL = float(os.environ.get("COMFYUI_HEALTH_CHECK_INTERVAL", "2.0"))  # seconds

# ============================================================================
# HEARTMULA BACKEND CONFIGURATION
# ============================================================================
# HeartMuLa - Music generation from lyrics and tags using LLM + Audio Codec
# Model: HeartMuLa 3B (open-source, multilingual)
# VRAM: ~12-16GB recommended
#
HEARTMULA_ENABLED = os.environ.get("HEARTMULA_ENABLED", "true").lower() == "true"



# ============================================================================
# SUPERTONIC SPEECH SYNTHESIS
# ============================================================================
# The platform's speaking voice. Supertonic 3 is non-autoregressive — flow
# matching plus a speech autoencoder — so it speaks the text it was handed and
# cannot continue past it. Runs on the CPU; the GPU stays free for image and
# video. See DEVELOPMENT_DECISIONS.md, 2026-08-08, for the search and the
# voice policy.
SUPERTONIC_ENABLED = os.environ.get("SUPERTONIC_ENABLED", "true").lower() == "true"
SUPERTONIC_MODEL = os.environ.get("SUPERTONIC_MODEL", "supertonic-3")

# Measured 2026-08-08 on the 24-core dev machine: letting ONNX Runtime take all
# cores made the first sentence three times slower (1.42 s instead of 0.44 s),
# and 16 threads was worse still at 2.64 s. The contention costs more than the
# parallelism brings.
SUPERTONIC_THREADS = int(os.environ.get("SUPERTONIC_THREADS", "4"))

# Flow steps. Below four the voice turns tinny. Time rises with the count:
# 2 -> 0.47 s, 4 -> 0.71 s, 8 -> 1.35 s on a short first sentence.
# Four is the lowest count that still sounds acceptable to the ear:
# measured through /api/speech on sentences of 35/82/123/177 characters,
# 4 steps 0.43/0.58/0.75/0.95 s against 8 steps 0.57/0.90/1.2/1.6 s, the
# register unchanged.
SUPERTONIC_FLOW_STEPS = int(os.environ.get("SUPERTONIC_FLOW_STEPS", "4"))
SUPERTONIC_SPEED = float(os.environ.get("SUPERTONIC_SPEED", "1.0"))

# One loudness for the whole utterance (EBU R128). Deliberately not per
# sentence: the platform speaks sentence by sentence so the first words arrive
# quickly, and per-piece peak normalisation makes the loudness jump between them.
SUPERTONIC_LOUDNESS_LUFS = float(os.environ.get("SUPERTONIC_LOUDNESS_LUFS", "-18.0"))

# Die fuenf festgelegten Mischungen:
# F3 und F4 gekreuzt mit M2 und M4, in allen Kombinationen, die die
# 60-Prozent-Regel halten. Nicht neu suchen, nicht ersetzen.
SUPERTONIC_VOICES = {
    "low":    {"F3": 0.60, "M2": 0.20, "M4": 0.20},
    "even":   {"F3": 0.60, "M4": 0.40},
    "mid":    {"F3": 1 / 3, "F4": 1 / 3, "M2": 1 / 3},
    "clear":  {"F3": 1 / 3, "F4": 1 / 3, "M4": 1 / 3},
    "bright": {"F4": 0.60, "M2": 0.20, "M4": 0.20},
}

# Used only when a caller names no voice AND asks for no rotation.
SUPERTONIC_DEFAULT_VOICE = os.environ.get("SUPERTONIC_DEFAULT_VOICE", "clear")

# The floor under which a run counts as having fallen into the male range, and
# is drawn again.
#
# The rule on the weighting is necessary but not sufficient. Supertonic is flow
# matching: every call starts from a freshly drawn noise sample, so the same
# weighting on the same sentence does not land in the same place twice. Measured
# 2026-08-08, twenty runs per voice on one sentence, share of runs below this
# floor: clear 1/20, bright 3/20, low 4/20, mid 4/20, even 9/20 — and the
# mixtures containing M2 threw single runs at 97, 102 and 115 Hz, which is not
# near the line but on the male preset.
#
# 140 Hz is where the gap sits: the pure presets measure 86-137 Hz for the male
# five and 157-197 Hz for the female five. Nothing of this model lands between.
#
# A seed does NOT solve this. It fixes which sample is drawn, not where the
# result for a new sentence lands. Drawing again does, and costs one further
# synthesis on the rare occasion.
SUPERTONIC_MIN_F0_HZ = float(os.environ.get("SUPERTONIC_MIN_F0_HZ", "140.0"))
SUPERTONIC_F0_REDRAWS = int(os.environ.get("SUPERTONIC_F0_REDRAWS", "3"))

# NOT seeded, on purpose. The noise comes from np.random.randn in
# supertonic/core.py; seeding immediately before the call gives byte-identical
# output (checked: six runs, spread 0 Hz). A voice that is never quite the same
# is a voice that claims no subject.


# ============================================================================
# ESPEAK NG SPEECH SYNTHESIS
# ============================================================================
# The computer voice from before AI, and the first column of the voices
# comparison. Nothing here was trained and nobody was recorded: rules turn the
# letters of a language into phonemes, and every phoneme is played as a handful
# of resonances. Written as `speak` for Acorn/RISC OS from 1995 by Jonathan
# Duddington, rewritten as eSpeak in 2007, forked to eSpeak NG in late 2015.
# See my_app/services/espeak_backend.py.
#
# Not downloaded and not vendored: it is a system package (`dnf install
# espeak-ng` / `apt install espeak-ng`), a few megabytes for over a hundred
# languages, running on the CPU. Piper embedded it as its phonemiser, so any
# machine that ran Piper has it already.
#
# Not the platform's voice; a caller reaches it only by naming it.
ESPEAK_ENABLED = os.environ.get("ESPEAK_ENABLED", "true").lower() == "true"

ESPEAK_BIN = os.environ.get("ESPEAK_BIN", "/usr/bin/espeak-ng")
ESPEAK_DATA_DIR = os.environ.get(
    "ESPEAK_DATA_DIR", "/usr/share/espeak-ng-data")

# The same loudness the other two are finished with. Three systems in one
# player, so a comparison between them cannot be a comparison of levels.
ESPEAK_LOUDNESS_LUFS = float(
    os.environ.get("ESPEAK_LOUDNESS_LUFS", str(SUPERTONIC_LOUDNESS_LUFS)))

# ============================================================================
# PIPER SPEECH SYNTHESIS
# ============================================================================
# The second machine of the voices comparison, in the third of its five
# columns, beside eSpeak NG. One
# file per voice, trained on one recorded dataset (VITS, 2021; Piper begun
# 2022 for the Rhasspy project, the installed 1.6.0 from the Home Assistant
# authors, 2025), and no control over emotion or register anywhere in it: the
# speaker heard is the recorded one. Not the platform's voice; a caller
# reaches it only by naming it. See my_app/services/piper_backend.py.
#
# Runs as a separate process in its own environment: a downloaded technology
# like every model here, fetched by download_piper.sh, with nothing of it in
# this repository. The separate environment also keeps its onnxruntime and
# espeak-ng data away from the platform's. On the CPU, 0.03-0.22 s per
# sentence (measured 2026-09-17); the card is never touched.
#
# Every platform language has an installed voice — Hebrew, which Supertonic
# lacks, and Bulgarian and Ukrainian, which VoxCPM2 answers in English.
PIPER_ENABLED = os.environ.get("PIPER_ENABLED", "true").lower() == "true"

# The binary of that environment, and the directory of .onnx voices beside
# their sidecar JSONs. download_piper.sh creates both.
PIPER_BIN = os.environ.get(
    "PIPER_BIN", os.path.expanduser("~/ai/piper/venv/bin/piper"))
PIPER_MODEL_DIR = os.environ.get(
    "PIPER_MODEL_DIR", os.path.expanduser("~/ai/piper/models"))

# Which voice speaks when a caller names none, where the language matches.
# For every other language the backend takes that language's first installed
# voice. The German default is the Multilingual LibriSpeech model: the only
# German voice in this catalogue above 16 kHz, and the only one trained from
# scratch rather than retrained from an English base voice.
PIPER_DEFAULT_VOICE = os.environ.get(
    "PIPER_DEFAULT_VOICE", "de_DE-mls-medium")

# The same loudness target the other three are finished with, so that a
# comparison between the four in one player is a comparison of voices and not
# of levels. `speech_audio.to_wav` then scales a voice whose peaks would clip
# back to 0.99, which leaves it below the target (measured 2026-09-18 on the
# returned audio: the German corpus voice at −21.2 LUFS, the US English one at
# −18.0, against −18). Piper's own per-sentence peak normalisation is switched
# off at the source (`--no-normalize`), see
# docs/SPRACHSYNTHESE_PIPER_KONFIGURATION.md.
PIPER_LOUDNESS_LUFS = float(
    os.environ.get("PIPER_LOUDNESS_LUFS", str(SUPERTONIC_LOUDNESS_LUFS)))

# ----------------------------------------------------------------------------
# VOXCPM2 — the synthesiser that is asked for a voice in words
# ----------------------------------------------------------------------------
# The third procedure for asking a machine for a feeling, next to Supertonic's
# mixture over fixed presets and Piper's nothing-to-ask-for. Here the speaker
# is described in words INSIDE the utterance — "(A young woman, gentle and
# sweet voice)Guten Tag." — so the model decides for itself which part of the
# string is an instruction and which part is what to say. Left empty, nothing
# is asked and it reads the delivery off the sentence.
#
# It is here because Qwen3-TTS is gone: a transformers upgrade elsewhere in the
# platform's environment broke it on 2026-08-12. This one therefore does not
# live in that environment at all. `voxcpm` pins datasets<4 and gradio>=6
# against the platform's 4.5.0 and 5.50.0, so it runs as a separate process in
# its own venv, like Piper — but resident, because loading 2 B parameters onto
# the GPU costs about 25 seconds against 0.3 seconds of speaking.
#
# Not the platform's voice; a caller reaches it only by naming it.
# download_voxcpm.sh installs it, voxcpm_service/server.py is the worker,
# 2_start_voxcpm.sh starts it. See my_app/services/voxcpm_backend.py.
VOXCPM_ENABLED = os.environ.get("VOXCPM_ENABLED", "true").lower() == "true"

# 17801=prod, 17802=dev, 17803=GPU, 17804=ComfyUI, 17805=VoxCPM2 worker.
VOXCPM_URL = os.environ.get("VOXCPM_URL", "http://127.0.0.1:17805")

# Started on demand, like ComfyUI and the GPU service. The timeout covers a
# cold load of the model, not a synthesis: nothing here caps how long speaking
# may take.
VOXCPM_AUTO_START = os.environ.get("VOXCPM_AUTO_START", "true").lower() == "true"
VOXCPM_STARTUP_TIMEOUT = int(os.environ.get("VOXCPM_STARTUP_TIMEOUT", "300"))
VOXCPM_HEALTH_CHECK_INTERVAL = float(
    os.environ.get("VOXCPM_HEALTH_CHECK_INTERVAL", "2.0"))

# The two settings the model card documents, at the values its own examples
# use. cfg_value is how closely the diffusion follows what was asked for;
# inference_timesteps is how many steps it takes to get there.
VOXCPM_CFG_VALUE = float(os.environ.get("VOXCPM_CFG_VALUE", "2.0"))
VOXCPM_INFERENCE_TIMESTEPS = int(
    os.environ.get("VOXCPM_INFERENCE_TIMESTEPS", "10"))

# The same loudness as the others, for the same reason.
VOXCPM_LOUDNESS_LUFS = float(
    os.environ.get("VOXCPM_LOUDNESS_LUFS", str(SUPERTONIC_LOUDNESS_LUFS)))

# ============================================================================
# GPU SERVICE (Media inference only: Diffusers, HeartMuLa, StableAudio)
# ============================================================================
# GPU Service handles media generation AND LLM inference (llama-cpp-python in-process).
#
GPU_SERVICE_URL = os.environ.get("GPU_SERVICE_URL", "http://localhost:17803")
GPU_SERVICE_TIMEOUT = 60      # Health checks, status


# --- Blender (headless mesh rendering) ---
BLENDER_PATH = os.environ.get("BLENDER_PATH", "/usr/bin/blender")
BLENDER_SCRIPTS_PATH = os.environ.get("BLENDER_SCRIPTS_PATH", str(Path(__file__).parent / "blender_scripts"))


# Local LLM concurrency limit (Python-side semaphore).
LLM_MAX_CONCURRENT = int(os.environ.get("LLM_MAX_CONCURRENT", "6"))

# Output caps are forbidden on this platform except where a provider API
# refuses the request without one. Anthropic's Messages API, direct and over
# Bedrock, requires max_tokens, so a caller that passes no cap sends this
# model ceiling: a smaller number cuts a text off mid-sentence, and a
# reasoning model spends it on chain-of-thought before a line of the answer
# is written.
ANTHROPIC_MAX_TOKENS_CEILING = 64000


NO_TRANSLATE = False  # Set to True to skip translation of prompts
ENABLE_LEGACY_MIGRATION = os.environ.get("ENABLE_LEGACY_MIGRATION", "true").lower() == "true"  # Auto-migrate legacy export folders on startup

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
LOCAL_TO_OPENROUTER_MAP = {
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

OPENROUTER_TO_LOCAL_MAP = {v: k for k, v in LOCAL_TO_OPENROUTER_MAP.items()}

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
# Every LLM call, provider or local, as (connect, read): 10 s to connect, so
# an unreachable provider or a dead GPU service fails fast; no read timeout,
# because a slow answer is still an answer and a truncated one is not. 90 s
# used to cut off reasoning models mid-thought, and a cut-off read failed the
# safety verifies closed on a prompt that was fine.
LLM_TIMEOUT = (10, None)
COMFYUI_TIMEOUT = 480  # 8 minutes for data-rich workflows
POLLING_TIMEOUT = 15

# ComfyUI queue management — reject submissions when queue is too deep.
# Shallow queue = fast "busy" feedback (good UX) vs deep queue = long silent waits + timeouts.
# At depth 10 with avg ~45s/job, worst-case wait is ~450s (within 480s COMFYUI_TIMEOUT).
# Frontend shows friendly i18n message on queue-full (generationError.busy).
COMFYUI_MAX_QUEUE_DEPTH = int(os.environ.get("COMFYUI_MAX_QUEUE_DEPTH", "10"))

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
CAPTION_VLM_MODEL = "qwen3-vl:8b"
# Extracts the caption from a VLM answer that reasoned first; a model of the
# local table (config/local_llm_weights.json), asked not to think
# (training_service._cleanup_caption). "mistral-nemo:latest" stood here until
# 2026-10-10 and was in no table, so the cleanup failed and the raw reasoning
# became the caption (finding S-009 of the code review of 2026-10-10).
CAPTION_CLEANUP_MODEL = "qwen3:4b"
CAPTION_ENABLED = True

# Model paths for training and ComfyUI inference
_COMFYUI_MODELS_PATH = Path(COMFYUI_BASE_PATH) / "models"
SD35_LARGE_MODEL_PATH = _COMFYUI_MODELS_PATH / "checkpoints" / "OfficialStableDiffusion" / "sd3.5_large.safetensors"
CLIP_L_PATH = _COMFYUI_MODELS_PATH / "clip" / "clip_l.safetensors"
CLIP_G_PATH = _COMFYUI_MODELS_PATH / "clip" / "clip_g.safetensors"
T5XXL_PATH = _COMFYUI_MODELS_PATH / "clip" / "t5xxl_fp16.safetensors"

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
