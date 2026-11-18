#!/usr/bin/env python3
"""
The count of the three places where the platform checks.

Every check sits at one of three places (my_app/services/safety_gate.py): the
intake of the user's material (check_intake, check_intake_texts), the step
before a media model (check_before_model), and the result before it leaves the
server (check_result_image, check_result_video, check_result_text,
check_result_code). A route calls no checker of its own. This test is the
count that holds it. It reads the route files and the services behind them,
and it fails

  1. when a way takes material without reaching check_intake;
  2. when a media model is called without check_before_model, or a language
     model of the platform runs between the check and the media model;
  3. when a picture, a video, a text a language model wrote, or code leaves
     the server without the check of the result; a chat's answer is the one
     declared exception (chat_answer);
  4. when a media workflow carries a language-model node;
  5. when a picture is handed to a model without the caller saying whether it
     may leave the server;
  6. when delivery reads a verdict without the level of whoever asks;
  7. when resolve_safety_level() is called outside a view, where it may not
     see the request and answers the strictest level;

and, as the census it grew out of, whenever a site that can reach a model, a
route, a request field, a stream event, a station or a file delivery appears
that nobody declared.

HOW A WAY IS COVERED. A declared way reaches a checkpoint when its function
calls the gate function, or calls or hands over to a function that does. The
test follows one level, as test_gpu_admission_coverage.py does. A view that
only hands its run to a runner is declared hands_to(runner), and the runner
carries the way; a hand-over may pass through one more runner.

A FIELD goes through the intake when the intake call names it: the `field=`
argument of check_intake, or a key of the mapping check_intake_texts takes, is
the name the request carries it under ("prompt", "context_prompt", ...). A
field written into a block message is the field the interface marks. A field
a view reads and hands over counts for the way its run ends in.

EXCEPTIONS carry their reason, and their kind says what the test verifies:

  nothing(...)         takes no material that reaches a model and hands out
                       nothing a model made
  step(...)            a step inside declared ways; the checks sit in the ways
                       that call it, and something calls it
  research_only(...)   refused on every level but research: the view, or a
                       function it calls, resolves the level and names research
  administration(...)  behind the settings password (require_settings_auth)
  delivery(...)        hands out a file or a list of runs, and asks the
                       delivery rule
  local_only(...)      answers calls from this machine only
  sound(...)           a sound whose own check is open (#116); what it is made
                       from is checked before the model
  chat_answer(...)     an exit of a chat turn: what the chat model wrote and
                       built leaves unchecked, because the chats check what
                       goes in (names, addresses, the lists; 2026-11-08) and
                       name the level in the chat's prompt; the function that
                       yields it reaches the intake

NOT YET SWITCHED. A way that does not meet a declared obligation yet stands
in a PENDING table. A pending entry is the only thing that lets a declared
obligation go unmet, so the tables only ever get shorter: an entry whose
obligation is met fails the run until it is removed, and a new way without
its checkpoints fails at once. All of them are empty.

Scanning is text/AST based, not import based: chunks are loaded by file path
(backend_router.py) and the backend is re-detected at runtime, so import edges
prove nothing. Known blind spots: a gate function imported under another name
(`... as gate`), a call through a variable, a requests.post on a URL variable
without a marker fragment, a request field read through a name that is neither
bound to the request (or to what a body reader hands back) nor a parameter
called `data` or `body`, and a language model that rewrites a text before the
media model in a function other than the one that called the check. The map is
a tripwire, not a proof.

Run:  pytest devserver/tests/test_safety_coverage_map.py
      python3 devserver/tests/test_safety_coverage_map.py --report   (print scan)
"""

import ast
import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache

from file_modules import DEVSERVER, REPO

ROUTES_DIR = DEVSERVER / "my_app" / "routes"
CHUNKS_DIR = DEVSERVER / "schemas" / "chunks"
NODES_DIR = REPO / "comfyui_nodes" / "ai4artsed_comfyui"
INDEX_ROOTS = (DEVSERVER / "my_app", DEVSERVER / "schemas")

# Service files that reach a model behind a route-started thread, a subprocess
# or a tool of the chat, read like the route files.
EXTRA_SCAN_FILES = [
    DEVSERVER / "my_app" / "services" / "canvas_executor.py",
    DEVSERVER / "my_app" / "services" / "canvas_run_service.py",
    DEVSERVER / "my_app" / "services" / "post_production_service.py",
    DEVSERVER / "my_app" / "services" / "training_service.py",
    DEVSERVER / "my_app" / "services" / "blender_service.py",
    DEVSERVER / "my_app" / "services" / "parrot_service.py",
    DEVSERVER / "my_app" / "services" / "tool_registry.py",
    DEVSERVER / "my_app" / "services" / "commons_service.py",
    DEVSERVER / "my_app" / "services" / "scene_ingest_service.py",
    DEVSERVER / "my_app" / "services" / "knowledge_processing.py",
    DEVSERVER / "my_app" / "utils" / "vision_support.py",
    DEVSERVER / "schemas" / "engine" / "pipeline_executor.py",
]

# What counts as "can reach a model" inside a function body, matched against
# the function's source. Each marker below the first six was added when a
# surface went quiet because it named none of the others: the lesson is that a
# shape is invisible until somebody writes it down.
from schemas.engine.multi_image_params import MULTI_IMAGE_KEYS  # noqa: E402

GENERATION_MARKERS = {
    "stage4": re.compile(r"execute_stage4_generation_only\s*\(|execute_generation_stage4\s*\("),
    "pipeline": re.compile(r"\.execute_pipeline\s*\("),
    "interception-engine": re.compile(r"PromptInterceptionEngine\s*\("),
    "gpu-proxy": re.compile(r"GPU_SERVICE|17803"),
    "comfyui": re.compile(r"COMFYUI|17804|submit_workflow"),
    "subprocess": re.compile(r"subprocess\.|Popen\s*\(|\bffmpeg\b"),
    "post-production": re.compile(r"post_production_service|compose_media_files"),
    "chat-llm": re.compile(r"call_chat_helper|chat_completion"),
    # The shared clients ARE the way to the card.
    "local-llm-client": re.compile(r"get_llm_backend\s*\(|get_media_analysis_client\s*\("),
    # The stage-2 engines and the gate's free of ComfyUI.
    "stage2-engine": re.compile(r"execute_stage2_(?:interception|classifier|with_optimization)\s*\("),
    "comfyui-free": re.compile(r"free_comfyui\s*\("),
    # A VLM reading a picture (llm_service.analyze_image), and the text client.
    "llm-service": re.compile(r"\bllm_service\.\w+\s*\("),
    "text-client": re.compile(r"_get_client\s*\(\s*\)"),
    # Graphs of the Fusion Workbench, run on ComfyUI.
    "graph-runner": re.compile(r"\brun_graph\s*\("),
    # A route that hands its run to the shared transport.
    "handed-over": re.compile(r"\banswered_either_way\s*\("),
    # One-node prompts of the platform's package.
    "node-runner": re.compile(r"\brun_node(?:_files)?\s*\("),
    # The text probes of the Latent Text Lab.
    "text-probes": re.compile(r"\btext_probes\.\w+\s*\("),
    # The Canvas's language-model nodes, through the engine the run hands them,
    # and a VLM reading a picture through the shared helper.
    "canvas-engine": re.compile(r"self\.engine\.process_request\s*\("),
    "image-reading": re.compile(r"\banalyze_image(?:_from_run)?\s*\("),
}


# ── Declarations ────────────────────────────────────────────────────────────

INTAKE = "intake"
BEFORE_MODEL = "before_model"
RESULT_IMAGE = "result_image"
RESULT_VIDEO = "result_video"
RESULT_TEXT = "result_text"
RESULT_CODE = "result_code"
# A picture shown while it is being made: held back at kids and youth until
# the verdict on the finished picture (safety_gate.preview_for).
PREVIEW_HELD = "preview_held"

GATE_FUNCTIONS = {
    INTAKE: {"check_intake", "check_intake_texts"},
    BEFORE_MODEL: {"check_before_model"},
    RESULT_IMAGE: {"check_result_image"},
    RESULT_VIDEO: {"check_result_video"},
    RESULT_TEXT: {"check_result_text"},
    RESULT_CODE: {"check_result_code"},
    PREVIEW_HELD: {"preview_for"},
}

# A way reaches a checkpoint by calling its function. What the function does
# inside is the gate's own business and no checkpoint of the caller: the code
# check reads the code with the text check, and a way that checks its code has
# not checked its text by that.
GATE_MODULE = "my_app.services.safety_gate"
CHECK_FUNCTIONS = set().union(*GATE_FUNCTIONS.values())

# What delivery asks: the rule and the doors built on it.
DELIVERY_RULE = {
    "entity_cleared_for_delivery", "filter_deliverable", "_sources_cleared",
    "checked_entity_path", "checked_path_for_filename", "_entity_refusal",
    "resolve_preview_media", "_restorable",
    "entity_cleared_for", "upload_cleared_for", "image_reference_cleared", "counts_for",
}


@dataclass(frozen=True)
class Way:
    """A way material takes, and the checkpoints it reaches."""
    points: tuple
    sound: str = ""


def way(*points, sound=""):
    return Way(tuple(points), sound)


@dataclass(frozen=True)
class Exempt:
    kind: str
    reason: str
    target: str = ""


def nothing(reason):
    return Exempt("nothing", reason)


def step(reason):
    return Exempt("step", reason)


def research_only(reason):
    return Exempt("research", reason)


def administration(reason):
    return Exempt("administration", reason)


def delivery(reason):
    return Exempt("delivery", reason)


def local_only(reason):
    return Exempt("local", reason)


def sound(ticket, reason):
    return Exempt("sound", reason, ticket)


def hands_to(runner):
    return Exempt("hands_to", "", runner)


def chat_answer(reason):
    return Exempt("chat", reason)


# Route files whose routes take no material that reaches a model and hand out
# nothing a model made. A site in them that can reach a model is still
# declared below, one by one.
EXEMPT_ROUTE_FILES = {
    "admin_users_routes.py": "user administration, behind the admin login",
    "auth_routes.py": "login and logout",
    "config_routes.py": "which models this installation offers",
    "courses_routes.py": "course administration; a palette entry names a perspective, whose "
                         "text passes the intake where a run uses it (custom:<id>)",
    "gpu_gate_routes.py": "the card's admission gate",
    "hardware_routes.py": "the models' memory footprints",
    "knowledge_routes.py": "the knowledge library its administrators keep, behind the settings password",
    "lora_routes.py": "the register of LoRA adapters: names and settings",
    "model_register_routes.py": "the model register",
    "news_routes.py": "the news on the start page",
    "settings_routes.py": "settings and status, most of it behind the settings password; the "
                          "session thumbnail is counted among the exits",
    "static_routes.py": "the built interface and the export folder; both are counted among the exits",
}

# Route files whose every route sits behind the settings password.
SETTINGS_PASSWORD_FILES = {"knowledge_routes.py"}


# ── The ways ────────────────────────────────────────────────────────────────
#
# Every route of a file not exempted above, and every site anywhere in the
# scanned files that can reach a model.

WAYS = {
    # --- Flow and Contesting -------------------------------------------------
    ("schema_pipeline_routes.py", "execute_stage2"): hands_to("_run_stage2"),
    ("schema_pipeline_routes.py", "_run_stage2"): way(INTAKE, RESULT_TEXT),
    # The streamed Stage 2 of the Flow: the stage-2 text, and the Wikipedia
    # look-ups with the model's reason for each.
    ("schema_pipeline_routes.py", "execute_pipeline_streaming"): way(INTAKE, RESULT_TEXT),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming.run_pipeline"):
        step("the inner runner of the streamed Stage 2"),
    ("schema_pipeline_routes.py", "generation_endpoint"):
        way(INTAKE, BEFORE_MODEL, RESULT_IMAGE, RESULT_VIDEO, RESULT_CODE),
    ("schema_pipeline_routes.py", "execute_generation_streaming"):
        way(INTAKE, BEFORE_MODEL, RESULT_IMAGE, RESULT_VIDEO, RESULT_CODE),
    ("schema_pipeline_routes.py", "execute_generation_streaming._generation_thread"):
        step("the generation's worker thread"),
    ("schema_pipeline_routes.py", "execute_generation_streaming._encode_info_work"):
        step("the encoders' account of the checked text"),
    ("schema_pipeline_routes.py", "execute_stage4_generation_only"):
        step("the generation itself; the check before the model sits in each way that calls it"),
    ("schema_pipeline_routes.py", "execute_generation_stage4"):
        way(BEFORE_MODEL, RESULT_IMAGE, RESULT_VIDEO, RESULT_CODE),
    ("schema_pipeline_routes.py", "interception_pipeline"): hands_to("_run_interception_pipeline"),
    ("schema_pipeline_routes.py", "_run_interception_pipeline"):
        way(INTAKE, BEFORE_MODEL, RESULT_IMAGE, RESULT_VIDEO, RESULT_TEXT, RESULT_CODE),
    ("schema_pipeline_routes.py", "execute_stage2_interception"): step("Stage 2, called by the ways above"),
    ("schema_pipeline_routes.py", "execute_stage2_with_optimization"): step("Stage 2 with the adaption"),
    ("schema_pipeline_routes.py", "execute_optimization"): step("the adaption to the output model"),
    ("schema_pipeline_routes.py", "optimize_prompt"): way(INTAKE, RESULT_TEXT),
    ("schema_pipeline_routes.py", "_run_adaption_chunk"):
        step("the adaption a chunk writes off the pictures (flux3_multi); its caption passes "
             "the intake and the check at the result in _run_optimize_prompt"),
    ("schema_pipeline_routes.py", "translate_text"): way(INTAKE, RESULT_TEXT),
    ("schema_pipeline_routes.py", "translate_one"): step("the platform's single-text translation"),
    ("schema_pipeline_routes.py", "_translate_list"): step("its inner call"),
    ("schema_pipeline_routes.py", "_translate_encoder_text"):
        step("the encoders' translation; it runs before the check before the model"),
    ("schema_pipeline_routes.py", "_translate_for_model"):
        step("the translation a media model receives; it runs before the check before the model"),
    ("schema_pipeline_routes.py", "_translate_context"): step("the edited context into English"),
    ("schema_pipeline_routes.py", "compare_analyze_image"): way(INTAKE, RESULT_TEXT),
    ("schema_pipeline_routes.py", "analyze_image_endpoint"): way(INTAKE, RESULT_TEXT),
    ("schema_pipeline_routes.py", "_stream_image_reading"): step("the reading of a picture, piecewise"),
    ("schema_pipeline_routes.py", "_stream_image_reading._reading_frames"): step("its frames"),
    ("schema_pipeline_routes.py", "_image_reader_backends"): nothing("asks which station serves a model"),
    ("schema_pipeline_routes.py", "_generator_fields"): nothing("names the generator of a finished file"),
    ("schema_pipeline_routes.py", "_cancel_diffusers_for"): nothing("ends a run, starts none"),
    ("schema_pipeline_routes.py", "safety_check_quick"): way(INTAKE),
    ("schema_pipeline_routes.py", "compare_analysis_prompt"): nothing("the platform's analysis prompt"),
    ("schema_pipeline_routes.py", "generation_active_endpoint"): nothing("whether a run is active"),
    ("schema_pipeline_routes.py", "queue_forecast_endpoint"): nothing("the queue's forecast"),
    ("schema_pipeline_routes.py", "generation_cancel_endpoint"): nothing("cancels a run"),
    ("schema_pipeline_routes.py", "save_run_context"):
        nothing("records the persona's dialogue, the comparison's context and the trashy "
                "analysis into the run for the research record; nothing reads them back"),
    ("schema_pipeline_routes.py", "init_empty_run"): nothing("opens an empty run"),
    ("schema_pipeline_routes.py", "get_output_cards"): nothing("the output cards of the configs"),
    ("schema_pipeline_routes.py", "pipeline_configs_with_properties"): nothing("the configs"),
    ("schema_pipeline_routes.py", "get_config_context"): nothing("a config's context, the platform's text"),
    ("schema_pipeline_routes.py", "get_config_pipeline"): nothing("a config's pipeline"),
    # Saved perspectives are the user's material: every route that writes
    # context_text or task_instruction passes it through the intake.
    ("interception_prompts_routes.py", "create_prompt"): way(INTAKE),
    ("interception_prompts_routes.py", "update_prompt"): way(INTAKE),
    ("interception_prompts_routes.py", "fork_from_preset"): way(INTAKE),
    ("interception_prompts_routes.py", "fork_prompt"): way(INTAKE),
    ("interception_prompts_routes.py", "revert_to_version"): way(INTAKE),
    ("interception_prompts_routes.py", "revert_to_preset"):
        nothing("sets the text back to the platform's preset, which is no user material"),
    ("interception_prompts_routes.py", "list_prompts"):
        nothing("lists saved perspectives; their texts passed the intake when saved"),
    ("interception_prompts_routes.py", "get_prompt"): nothing("reads one, likewise"),
    ("interception_prompts_routes.py", "list_versions"): nothing("its versions, likewise"),
    ("interception_prompts_routes.py", "delete_prompt"): nothing("deletes one"),
    ("interception_prompts_routes.py", "preview_prompt"): way(INTAKE, RESULT_TEXT),
    # --- Latent Lab: picture instruments ------------------------------------
    ("schema_pipeline_routes.py", "direct_workflow"): hands_to("_run_direct_workflow"),
    ("schema_pipeline_routes.py", "_run_direct_workflow"):
        way(INTAKE, BEFORE_MODEL, RESULT_IMAGE, RESULT_VIDEO),
    ("latent_lab_recorder_routes.py", "latent_lab_capabilities"): nothing("which tools are usable here"),
    ("latent_lab_recorder_routes.py", "start_recording"): nothing("opens a sitting"),
    ("latent_lab_recorder_routes.py", "end_recording"): nothing("closes a sitting"),
    # A recorded lab run keeps what the browser sends: pictures and texts that
    # can reach the gallery. They are the browser's material.
    ("latent_lab_recorder_routes.py", "save_recording"): way(INTAKE),
    ("latent_lab_recorder_routes.py", "set_run_output"): way(INTAKE),
    ("latent_lab_recorder_routes.py", "get_session_runs"):
        nothing("the runs of a sitting with the addresses of their parts"),
    ("latent_lab_recorder_routes.py", "get_run"): nothing("one run with the addresses of its parts"),
    ("latent_lab_recorder_routes.py", "get_run_part"): delivery("one part of a lab run"),
    # --- Latent Lab: sound, Workbench, Mean Images, Re-enactment, speech ----
    ("cross_aesthetic_routes.py", "semantic_axes"): nothing("the axis definitions"),
    ("cross_aesthetic_routes.py", "synth"): hands_to("_synth_post"),
    ("cross_aesthetic_routes.py", "image_guided_audio"): hands_to("_guided_post"),
    ("cross_aesthetic_routes.py", "mmaudio"): hands_to("_mmaudio_post"),
    ("cross_aesthetic_routes.py", "_synth_post"): way(INTAKE, BEFORE_MODEL, sound="#116"),
    ("cross_aesthetic_routes.py", "_guided_post"): way(INTAKE, BEFORE_MODEL, sound="#116"),
    ("cross_aesthetic_routes.py", "_mmaudio_post"): way(INTAKE, BEFORE_MODEL, sound="#116"),
    ("cross_aesthetic_routes.py", "_streamed_post"):
        step("the transport the three sound views hand their work to"),
    ("cross_aesthetic_routes.py", "_run_node"): step("the one-node prompt of each of the three"),
    ("fusion_workbench_routes.py", "generate"): hands_to("_run"),
    ("fusion_workbench_routes.py", "_run"): way(INTAKE, BEFORE_MODEL, RESULT_IMAGE),
    ("fusion_workbench_routes.py", "_run.one_run"): step("one graph of the run"),
    ("fusion_workbench_routes.py", "expand_t5_route"): way(INTAKE, RESULT_TEXT),
    ("fusion_workbench_routes.py", "_research_run"):
        step("the run of the four research instruments, behind their views' lock"),
    ("fusion_workbench_routes.py", "decomposition"): research_only("a research instrument"),
    ("fusion_workbench_routes.py", "position_probe"): research_only("a research instrument"),
    ("fusion_workbench_routes.py", "delayed_kickin"): research_only("a research instrument"),
    ("fusion_workbench_routes.py", "delayed_kickin_cumulative"): research_only("a research instrument"),
    ("mean_images_routes.py", "variants"): hands_to("_run_variants"),
    ("mean_images_routes.py", "_run_variants"): way(INTAKE, RESULT_TEXT),
    ("mean_images_routes.py", "overlay"): way(RESULT_IMAGE),
    ("mean_images_routes.py", "latent_preview"): delivery("draws runs of the browser's choosing"),
    ("speech_routes.py", "speak"): hands_to("_speak"),
    ("speech_routes.py", "_speak"): way(INTAKE, BEFORE_MODEL, sound="#116"),
    ("speech_routes.py", "_translate_to_english"): step("the sentence into a language the voice speaks"),
    ("speech_routes.py", "status"): nothing("which voices are available"),
    ("parrot_routes.py", "upload_recording"):
        nothing("keeps the recording; its transcript passes the intake in the chain"),
    ("parrot_routes.py", "stream_chain"): hands_to("run_chain"),
    ("parrot_routes.py", "sung"): sound("#116", "the song"),
    ("parrot_routes.py", "discard_recording"): nothing("deletes a recording"),
    ("parrot_service.py", "run_chain"): way(INTAKE, BEFORE_MODEL, RESULT_TEXT, sound="#116"),
    ("parrot_service.py", "_sing"): step("sings the lyrics the chain checked before the station 'written'"),
    # --- Canvas ---------------------------------------------------------------
    # The board passes the intake in its view (canvas_executor.board_intake);
    # each node that calls a model is a way of its own, wherever the run goes.
    ("canvas_routes.py", "execute_batch"): way(INTAKE),
    ("canvas_routes.py", "execute_batch.generate"): step("the batch's event generator"),
    ("canvas_routes.py", "execute_workflow_stream"): way(INTAKE),
    ("canvas_run_service.py", "start_run"):
        step("starts a board's run once its view's intake passed"),
    ("canvas_run_service.py", "_worker"):
        step("drives a board's nodes; each node that calls a model is a way of its own"),
    ("canvas_executor.py", "_execute_generation"): way(BEFORE_MODEL, RESULT_IMAGE, RESULT_VIDEO),
    ("canvas_executor.py", "_execute_random_prompt"): way(RESULT_TEXT),
    ("canvas_executor.py", "_execute_interception"): way(RESULT_TEXT),
    ("canvas_executor.py", "_execute_translation"): way(RESULT_TEXT),
    ("canvas_executor.py", "_execute_model_adaption"): way(RESULT_TEXT),
    ("canvas_executor.py", "_execute_evaluation"): way(RESULT_TEXT),
    ("canvas_executor.py", "_execute_comparison_evaluator"): way(RESULT_TEXT),
    ("canvas_executor.py", "_execute_image_evaluation"): way(RESULT_TEXT),
    # A kept board goes into the favourites and from there to every gallery.
    ("canvas_routes.py", "keep_workflow"): way(INTAKE),
    ("canvas_routes.py", "reconnect_workflow_stream"):
        nothing("replays a running board's events, which passed their checks in the run"),
    ("canvas_routes.py", "get_canvas_run_status"): nothing("a run's state"),
    ("canvas_routes.py", "get_canvas_partial"): nothing("addresses of a run's media; the bytes go through delivery"),
    ("canvas_routes.py", "get_translation_defaults"): nothing("the default translation settings"),
    ("canvas_routes.py", "get_llm_models"): nothing("lists models"),
    ("canvas_routes.py", "get_vision_models"): nothing("lists models"),
    ("canvas_routes.py", "get_output_configs"): nothing("lists the output configs"),
    ("canvas_routes.py", "list_canvas_presets"): nothing("lists the platform's boards"),
    ("canvas_routes.py", "get_interception_config"): nothing("a perspective preset of the platform"),
    ("canvas_routes.py", "abort_batch"): nothing("stops a batch"),
    # --- Chats and the text instruments --------------------------------------
    ("chat_routes.py", "chat"): hands_to("_chat_events"),
    ("chat_routes.py", "chat_stream"): hands_to("_chat_events"),
    # The chats check what goes in (2026-11-08); the comparisons of the Latent
    # Lab, on the same turn, keep the result check on their answer.
    ("chat_routes.py", "_chat_events"): way(INTAKE, RESULT_TEXT),
    ("chat_routes.py", "get_history"):
        nothing("a turn's history, which holds only text the turn released"),
    ("chat_routes.py", "chat_models"): nothing("lists models"),
    ("chat_routes.py", "chat_vlm_models"): nothing("lists the models that see"),
    ("chat_routes.py", "chat_install"): nothing("installs a local model"),
    # The platform's own ComfyUI nodes ask a model here. Their material passed
    # the intake of the run that started the workflow, and their answer is
    # checked where that run hands it out.
    ("chat_routes.py", "chat_proxy"): local_only("the model call of the platform's ComfyUI nodes"),
    ("chat_routes.py", "_brought_captions"):
        step("the chat's account of the pictures a board brings into the turn"),
    ("chat_routes.py", "call_chat_helper"): step("the platform's chat call"),
    ("chat_routes.py", "call_chat_helper_stream"): step("the same, piecewise"),
    ("chat_routes.py", "_call_local_llm_chat"): step("the same, on this machine"),
    ("chat_routes.py", "_stream_local_llm"): step("the same, piecewise"),
    ("chat_routes.py", "_chain_attempts"): step("the fallback chain both of them walk"),
    ("text_routes.py", "tokenize_text"): way(INTAKE),
    ("text_routes.py", "encoder_rows"): way(INTAKE),
    ("text_routes.py", "rep_engineering"): hands_to("_run_rep_engineering"),
    ("text_routes.py", "_run_rep_engineering"): way(INTAKE, RESULT_TEXT),
    ("text_routes.py", "bias_probe"):
        nothing("takes corpus items and hands out the model's pick among their answers"),
    ("text_routes.py", "_run_bias_probe"):
        nothing("scores the given answers: it returns the corpus's text and the model's pick"),
    ("text_routes.py", "bbq_probe"):
        nothing("takes corpus items and hands out the model's pick among their answers"),
    ("text_routes.py", "_run_bbq_probe"):
        nothing("scores the given answers: it returns the corpus's text and the model's pick"),
    ("text_routes.py", "_get_client"): nothing("builds the connection, never touches a text"),
    ("text_routes.py", "list_presets"): nothing("the presets"),
    ("text_routes.py", "list_tokenizers"): nothing("the tokenizers"),
    ("text_routes.py", "bbq_overview"): nothing("counts of a fixed research corpus"),
    ("text_routes.py", "bbq_sample"): nothing("items of a fixed research corpus"),
    ("text_routes.py", "bbq_record"): nothing("records which corpus items were shown"),
    ("text_routes.py", "bbq_stats"): nothing("counts"),
    ("text_routes.py", "bias_corpus"): nothing("items of a fixed research corpus"),
    ("tool_registry.py", "_register_builtin_tools"):
        step("the chat's tools; each runs inside a turn, which carries the checks"),
    ("tool_registry.py", "_register_builtin_tools.view_favorite"): step("a tool of the chat"),
    ("tool_registry.py", "_register_builtin_tools.view_run"): step("a tool of the chat"),
    ("tool_registry.py", "_register_builtin_tools.view_upload"): step("a tool of the chat"),
    ("vision_support.py", "ask_about_image"): step("one question about a picture"),
    ("vision_support.py", "describe_image_for_fallback"): step("an account of a picture for a blind model"),
    ("resona_routes.py", "journal_ensure"): nothing("opens a journal"),
    ("resona_routes.py", "journal_new"): nothing("opens a journal"),
    ("resona_routes.py", "journal_delete"): nothing("deletes a journal"),
    ("resona_routes.py", "journal_get"): nothing("the journal, which holds only released text"),
    ("resona_routes.py", "journal_media_result"):
        nothing("records which run answered a media intent: addresses and states"),
    # --- Analysis, documents, training, Commons ------------------------------
    ("media_routes.py", "analyze_image_file"): hands_to("_run_analyze_image"),
    # The picture came in through the upload, which judged it; the reading
    # reads that verdict before the reading model and takes no other material.
    ("media_routes.py", "_run_analyze_image"): way(BEFORE_MODEL, RESULT_TEXT),
    ("media_routes.py", "analyze_av_file"): hands_to("_run_analyze_av"),
    # A video is read where delivery hands it to whoever asks; sound has no
    # check at the result yet.
    ("media_routes.py", "_run_analyze_av"): way(RESULT_TEXT),
    ("media_routes.py", "analyze_media_compare"): hands_to("_run_analyze_compare"),
    ("media_routes.py", "_run_analyze_compare"): way(INTAKE, RESULT_TEXT),
    ("media_routes.py", "_translate_analysis"): step("translates the analysis, which is checked at the result"),
    # The document's name at the intake. Its text is taken in by the import
    # job once the converter has read it, and the summary is checked there.
    ("scene_routes.py", "upload_document"): way(INTAKE),
    ("scene_routes.py", "list_jobs"): nothing("import jobs"),
    ("scene_routes.py", "get_job"): nothing("one import job"),
    ("scene_routes.py", "cancel_job"): nothing("stops an import"),
    ("scene_routes.py", "list_documents"): nothing("lists documents"),
    ("scene_routes.py", "get_document"): nothing("a document and its released summary"),
    ("scene_routes.py", "delete_document"): nothing("deletes a document"),
    # The import job: the document's text at the intake before the
    # condensation's model reads it, the summary at the result before it is
    # stored.
    ("scene_ingest_service.py", "_run_job"): way(INTAKE, RESULT_TEXT),
    ("scene_ingest_service.py", "_check_summary"): way(RESULT_TEXT),
    ("scene_ingest_service.py", "_set_proc"): nothing("the converter's process, no model"),
    ("scene_ingest_service.py", "_stream_subprocess"): nothing("the converter's output, no model"),
    # The pictures at the intake and the sentences at the result, both in the
    # staging the view hands to, at the level the view resolved.
    ("training_routes.py", "describe_images"): hands_to("stage_and_describe"),
    ("training_routes.py", "describe_status"): nothing("hands out the descriptions the thread released"),
    ("training_routes.py", "start_training"): way(INTAKE),
    ("training_routes.py", "stop_training"): nothing("stops a training"),
    ("training_routes.py", "delete_project"): nothing("deletes a project"),
    ("training_routes.py", "list_loras"): nothing("lists adapters"),
    ("training_routes.py", "energy_estimate"): nothing("an estimate"),
    ("training_routes.py", "training_setup"): nothing("the training's settings"),
    ("training_routes.py", "get_training_status"): nothing("a training's state"),
    ("training_routes.py", "training_events"): nothing("a training's progress"),
    ("training_routes.py", "check_vram"): nothing("reads the card"),
    ("training_routes.py", "clear_vram"): nothing("frees the card"),
    ("training_service.py", "stage_and_describe"): way(INTAKE, RESULT_TEXT),
    ("training_service.py", "_request_description"): step("one description of a training picture"),
    ("training_service.py", "_cleanup_caption"): step("tidies a description"),
    ("training_service.py", "start_training_process"):
        nothing("trains on pictures that passed the intake; shows nothing"),
    ("training_service.py", "start_training_process.run_proc"): nothing("its process"),
    ("training_service.py", "stop_training"): nothing("signals the run's process group"),
    ("training_service.py", "clear_vram_thoroughly"): nothing("frees the card"),
    ("training_service.py", "__init__"): nothing("the service object"),
    ("training_service.py", "_get_vram_status"): nothing("reads the card"),
    ("training_service.py", "get_gpu_vram"): nothing("reads the card"),
    ("commons_routes.py", "lookup"): hands_to("_run_lookup"),
    # The prompt at the intake and, one level in, the search term a model makes
    # of it. Every picture of the row passes the result in _take.
    ("commons_routes.py", "_run_lookup"): way(INTAKE, RESULT_TEXT),
    ("commons_routes.py", "image"): delivery("a picture a Commons search released"),
    ("commons_service.py", "derive_search_term"): step("the search term, made from the prompt"),
    ("commons_service.py", "_take"): way(RESULT_IMAGE),
    # --- Delivery, favourites, composition -------------------------------------
    ("media_routes.py", "upload_image"): way(INTAKE),
    ("media_routes.py", "get_uploaded_image"): delivery("an upload"),
    ("media_routes.py", "get_image"): delivery("a run's picture"),
    ("media_routes.py", "get_image_thumbnail"): delivery("a run's picture, smaller"),
    ("media_routes.py", "get_video"): delivery("a run's video"),
    ("media_routes.py", "get_3d_mesh"): delivery("a run's 3D model"),
    ("media_routes.py", "get_p5"): delivery("code a language model wrote"),
    ("media_routes.py", "get_tonejs"): delivery("code a language model wrote"),
    ("media_routes.py", "get_sonicpi"): delivery("code a language model wrote"),
    ("media_routes.py", "get_composition"): delivery("a composite of a run's media"),
    ("media_routes.py", "get_audio"): sound("#116", "a run's sound"),
    ("media_routes.py", "get_music"): sound("#116", "a run's music"),
    ("media_routes.py", "get_midi"): sound("#116", "a run's notation"),
    ("media_routes.py", "mark_media"):
        nothing("marks bytes the browser made and hands them straight back; nothing is kept"),
    ("media_routes.py", "get_media_disclosure"): nothing("the disclosure text"),
    ("media_routes.py", "get_media_info"): nothing("sizes and names"),
    ("media_routes.py", "compose_media"):
        nothing("composes a run's media with ffmpeg; the composite's verdict follows its sources"),
    ("post_production_service.py", "compose"): nothing("the composition, likewise"),
    ("post_production_service.py", "_build_still_plus_audio"): nothing("one of its builds"),
    ("post_production_service.py", "_build_video_plus_audio"): nothing("one of its builds"),
    ("post_production_service.py", "_probe_duration"): nothing("reads a length"),
    ("post_production_service.py", "_require_ffmpeg"): nothing("finds ffmpeg"),
    ("post_production_service.py", "<module>"): nothing("the module's constants"),
    ("blender_service.py", "_render_sync"):
        step("renders a 3D model's preview, which every way that stores it checks at the result"),
    ("blender_service.py", "is_available"): nothing("whether Blender is installed"),
    ("pipeline_routes.py", "get_pipeline_status"): nothing("a run's state"),
    ("pipeline_routes.py", "get_file_by_name"): delivery("a run's file by its name"),
    ("pipeline_routes.py", "get_entity"): delivery("a run's entity"),
    ("pipeline_routes.py", "list_entities"): nothing("the entities of a run, without their verdicts"),
    # The gallery of every device, and the restore of a run into a page.
    ("favorites_routes.py", "get_favorites"): delivery("the gallery"),
    ("favorites_routes.py", "get_restore_data"): delivery("a run's texts, put back on a page"),
    ("favorites_routes.py", "add_favorite"): way(INTAKE),
    ("favorites_routes.py", "update_favorite"): way(INTAKE),
    ("favorites_routes.py", "remove_favorite"): nothing("removes a favourite"),
    ("favorites_routes.py", "get_keeper"): nothing("says whether a run is kept and whether the asker may change it"),
    # --- Research and the machine room ---------------------------------------
    ("dev_routes.py", "research_sweep_launch"): research_only("the research sweep"),
    ("dev_routes.py", "kickin_image"): research_only("a picture of the sweep"),
    ("dev_routes.py", "kickin_datasets"): research_only("the sweep's datasets"),
    ("dev_routes.py", "kickin_perblock_status"): research_only("the sweep's state"),
    ("dev_routes.py", "kickin_perblock_image"): research_only("a picture of the sweep"),
    ("dev_routes.py", "kickin_cumulative_status"): research_only("the sweep's state"),
    ("dev_routes.py", "kickin_cumulative_image"): research_only("a picture of the sweep"),
    ("dev_routes.py", "get_pixel_templates"): nothing("the editor of pixel templates"),
    ("dev_routes.py", "save_pixel_template"): nothing("a pattern of cells, no text"),
    ("dev_routes.py", "delete_pixel_template"): nothing("deletes one"),
    ("knowledge_routes.py", "_reindex_sync"): administration("rebuilds the library's index"),
    ("knowledge_processing.py", "<module>"): administration("the library's processing"),
    ("knowledge_processing.py", "default_llm_fn"): administration("the library's processing"),
    ("knowledge_processing.py", "default_llm_fn._fn"): administration("the library's processing"),
    ("knowledge_processing.py", "describe_figures"): administration("the library's figure descriptions"),
    ("knowledge_processing.py", "_describe_figure_online"): administration("the library's figure descriptions, online"),
    ("settings_routes.py", "workshop_preload"): nothing("loads models for a workshop"),
    ("settings_routes.py", "workshop_preload.generate"): nothing("its progress"),
    ("settings_routes.py", "workshop_clear_all"): nothing("frees the card"),
    ("settings_routes.py", "_ensure_dummy_image_uploaded"): nothing("an empty picture for a warm-up"),
    ("settings_routes.py", "get_backend_status"): nothing("the backends' state"),
    ("settings_routes.py", "detect_gpu_vram"): nothing("reads the card"),
    ("settings_routes.py", "get_gpu_realtime"): nothing("reads the card"),
}


# ── Exits: what leaves the server in a stream, a station or a file ──────────
#
# (file, function, form, name): the checkpoints the content passed, or an
# exception. Forms: "event" (generate_sse_event), "station" (a station of the
# Re-enactment), "type" (a typed event the chat yields), "file" (send_file).

EXITS = {
    ("schema_pipeline_routes.py", "_safety_quick_failure_frame", "event", "complete"):
        nothing("the quick check's own answer"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "complete"):
        (RESULT_IMAGE, RESULT_VIDEO, RESULT_CODE),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "generation_progress"):
        (PREVIEW_HELD,),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "stage3_complete"):
        (BEFORE_MODEL,),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "encoding_info"):
        nothing("token counts of the checked text"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "connected"): nothing("a greeting"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "stage3_start"): nothing("a state"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "stage4_start"): nothing("a state"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "queue_position"): nothing("a place"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "cancelled"): nothing("a state"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "error"): nothing("a fault"),
    ("schema_pipeline_routes.py", "execute_generation_streaming", "event", "blocked"): nothing("the block message"),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming", "event", "chunk"): (RESULT_TEXT,),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming", "event", "complete"): (RESULT_TEXT,),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming._interception_notices", "event",
     "wikipedia_lookup"): (RESULT_TEXT,),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming", "event", "connected"): nothing("a greeting"),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming", "event", "stage_start"): nothing("a state"),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming", "event", "error"): nothing("a fault"),
    ("schema_pipeline_routes.py", "execute_pipeline_streaming", "event", "blocked"): nothing("the block message"),
    ("schema_pipeline_routes.py", "_stream_image_reading._reading_frames", "type", "token"): (RESULT_TEXT,),
    ("schema_pipeline_routes.py", "_stream_image_reading._reading_frames", "type", "done"): (RESULT_TEXT,),
    ("schema_pipeline_routes.py", "_stream_image_reading._reading_frames", "type", "error"): nothing("a fault"),
    ("schema_pipeline_routes.py", "_stream_image_reading._reading_frames", "type", "blocked"):
        nothing("the block message"),
    ("chat_routes.py", "_chat_events", "type", "token"):
        chat_answer("a piece of a chat's answer as it is written; a comparison yields none"),
    ("chat_routes.py", "_chat_events", "type", "entity"):
        chat_answer("a card in the model's words, a library passage or a page"),
    ("chat_routes.py", "_chat_events", "type", "graph"):
        chat_answer("an apparatus the model built; its runs pass the check before the model"),
    ("chat_routes.py", "_chat_events", "type", "done"):
        chat_answer("the answer, its thinking and what was built; a comparison's answer "
                    "and thinking pass check_result_text first"),
    ("chat_routes.py", "_chat_events", "type", "discard"): nothing("takes back text already shown"),
    ("chat_routes.py", "_chat_events", "type", "withdraw"): nothing("takes back text already shown"),
    # A fault or a refusal at the intake, with what the turn built before it.
    ("chat_routes.py", "_chat_events", "type", "error"):
        chat_answer("a fault or a refusal at the intake, with what was built before it"),
    ("parrot_service.py", "run_chain", "station", "words"): (INTAKE,),
    ("parrot_service.py", "run_chain", "station", "reading"): (RESULT_TEXT,),
    ("parrot_service.py", "run_chain", "station", "written"): (BEFORE_MODEL,),
    ("parrot_service.py", "run_chain", "station", "ranked"): nothing("labels from a list the platform chose"),
    ("parrot_service.py", "run_chain", "station", "sung"): sound("#116", "the song"),
    ("parrot_routes.py", "stream_chain.generate", "station", "chain"): nothing("a state"),
    ("parrot_routes.py", "stream_chain.missing", "station", "input"): nothing("a state"),
    ("parrot_routes.py", "sung", "file", "send_file"): sound("#116", "the song"),
    ("dev_routes.py", "kickin_image", "file", "send_from_directory"): research_only("a picture of the sweep"),
    ("dev_routes.py", "kickin_perblock_image", "file", "send_from_directory"):
        research_only("a picture of the sweep"),
    ("dev_routes.py", "kickin_cumulative_image", "file", "send_from_directory"):
        research_only("a picture of the sweep"),
    ("latent_lab_recorder_routes.py", "get_run_part", "file", "send_file"): delivery("one part of a lab run"),
    ("media_routes.py", "get_image", "file", "send_file"): delivery("a run's picture"),
    ("media_routes.py", "get_image_thumbnail", "file", "send_file"): delivery("a run's picture, smaller"),
    ("media_routes.py", "get_uploaded_image", "file", "send_file"): delivery("an upload"),
    ("media_routes.py", "get_video", "file", "send_file"): delivery("a run's video"),
    ("media_routes.py", "get_3d_mesh", "file", "send_file"): delivery("a run's 3D model"),
    ("media_routes.py", "get_p5", "file", "send_file"): delivery("code a language model wrote"),
    ("media_routes.py", "get_tonejs", "file", "send_file"): delivery("code a language model wrote"),
    ("media_routes.py", "get_sonicpi", "file", "send_file"): delivery("code a language model wrote"),
    ("media_routes.py", "get_composition", "file", "send_file"): delivery("a composite of a run's media"),
    ("media_routes.py", "get_audio", "file", "send_file"): sound("#116", "a run's sound"),
    ("media_routes.py", "get_music", "file", "send_file"): sound("#116", "a run's music"),
    ("media_routes.py", "get_midi", "file", "send_file"): sound("#116", "a run's notation"),
    ("pipeline_routes.py", "get_entity", "file", "send_file"): delivery("a run's entity"),
    ("pipeline_routes.py", "get_file_by_name", "file", "send_file"): delivery("a run's file by its name"),
    ("settings_routes.py", "get_session_thumbnail", "file", "send_file"): delivery("a session's picture"),
    ("static_routes.py", "serve_exports", "file", "send_file"): delivery("a file of the export folder"),
    ("static_routes.py", "serve_spa", "file", "send_from_directory"): nothing("the built interface"),
}


# ── Request fields ──────────────────────────────────────────────────────────
#
# Every field a route of a file not exempted above reads from the request, and
# what it is. "intake": the user's material, which passes the intake under this
# name. "reference": it names a picture, a run or a file, and the verdict of
# what it names is asked where that reaches a model or leaves. "control": a
# setting, a number, an id, or a choice among things the server holds.
# (file, field) overrides field.

_I, _R, _C = "intake", "reference", "control"

FIELDS = {
    # the material
    "prompt": _I, "prompt_a": _I, "prompt_b": _I, "prompt_c": _I, "base_prompt": _I,
    "negative_prompt": _I, "input_text": _I, "context_prompt": _I, "text": _I, "texts": _I,
    "message": _I, "history": _I, "context": _I, "draft_context": _I, "secondary_text": _I,
    "sample_input": _I, "context_text": _I, "task_instruction": _I, "user_note": _I,
    "title": _I, "document": _I, "file": _I, "t5_prompt": _I, "probe_prompt": _I,
    "source_prompt": _I, "baseline_prompt": _I, "prompt_early": _I, "prompt_full": _I,
    "concepts": _I, "captions": _I,
    "trigger_word": _I, "project_name": _I, "contrast_pairs": _I, "test_text": _I,
    "voice_description": _I, "interception_result": _I, "optimization_result": _I,
    "user_input": _I, "custom_placeholders": _I, "translation_en": _I,
    "comparison_original_prompt": _I, "parts": _I, "nodes": _I, "workflow": _I,
    "prompts": _I, "outputs": _I, "results": _I, "dataBase64": _I, "reading": _I,
    # what names a picture, a run or a file
    "image_path": _R, "image_input": _R, "input_image": _R,
    # The pictures of a multi-image run, input_image1 ... input_image10, which
    # `multi_images_from` reads as one.
    **{key: _R for key in MULTI_IMAGE_KEYS},
    "image_base64": _R, "run_id": _R, "run_ids": _R,
    "media_url": _R, "inputs": _R, "ids": _R, "record": _R,
    # The address a recorded picture was fetched from before it is uploaded
    # again; its pass carries over only where the bytes are that picture.
    "source": _R,
    # settings, numbers, ids, choices
    "seed": _C, "base_seed": _C, "cfg": _C, "width": _C, "height": _C, "denoise": _C,
    "sampler_name": _C, "scheduler": _C, "alpha": _C, "alpha_factor": _C, "alphas": _C,
    "factor_a": _C, "factor_b": _C, "factor_c": _C, "scale_add": _C, "scale_sub": _C,
    "shift": _C, "model": _C, "model_id": _C, "interception_model": _C, "output_config": _C,
    "schema": _C, "config_name": _C, "device_id": _C, "user_id": _C, "course_id": _C,
    "lora_course_id": _C, "lora_user_id": _C, "loras": _C, "lang": _C, "language": _C,
    "user_language": _C, "context_language": _C, "source_language": _C, "target_language": _C,
    "comparison_language": _C, "style": _C, "cache_scope": _C, "enable_streaming": _C,
    "stream": _C, "keep_latent": _C, "force_translation": _C, "skip_stage3_translation": _C,
    "skip_optimization": _C, "has_input_image": _C, "timestamp": _C, "comparison_group_id": _C,
    # A request may tighten the level the server resolves, never loosen it.
    "safety_level": _C,
    "temperature": _C, "target_layer": _C, "item_ids": _C, "category": _C, "situations": _C,
    "instrument": _C, "pairs": _C, "scenario": _C, "count": _C, "n": _C,
    "limit": _C, "offset": _C, "after": _C, "batch_id": _C, "preset_name": _C,
    "base_config": _C, "pipeline": _C, "parameters": _C, "is_published": _C, "intent_id": _C,
    "media_type": _C, "status": _C, "kind": _C, "px": _C, "type": _C, "operation": _C,
    "token": _C, "staging_token": _C, "unload_comfyui": _C, "unload_llm": _C,
    "unload_ollama": _C, "axes": _C, "dimension_offsets": _C, "fusion_strategy": _C,
    "algebra_encoder": _C, "probing_encoder": _C, "combine_at": _C, "normalize_weights": _C,
    "pooled": _C, "t5_rows": _C, "clip_encoder": _C, "transfer_dims": _C, "block_range": _C, "cells": _C,
    "kickin_step": _C, "layer_bands": _C, "layer_entry": _C, "probe_block_range": _C,
    "probe_step_range": _C, "probe_stream": _C, "step_bands": _C, "step_window": _C,
    "up_to_block": _C, "dataset_id": _C, "sweep_types": _C, "pattern": _C, "voice": _C,
    "variant": _C, "emotion": _C, "system": _C, "mix": _C, "noise_w": _C, "length_scale": _C,
    "speed": _C, "pitch": _C, "inference_timesteps": _C, "cfg_value": _C, "cfg_scale": _C,
    "cfg_strength": _C, "duration_seconds": _C, "lambda_guidance": _C, "total_steps": _C,
    "warmup_steps": _C, "num_steps": _C, "steps": _C, "magnitude": _C, "noise_sigma": _C,
    "interception_config": _C, "perspective": _C, "analysis_type": _C,
    # A key into the platform's reading frames: an unknown key falls through
    # to the plain reading, and the value itself reaches no model.
    "frame": _C,
    "view_mode": _C, "journal_id": _C, "session_id": _C, "latent_lab_tool": _C,
    "runs_inside_comfyui": _C, "may_open_media": _C, "surface_media": _I, "connections": _C,
    "source_view": _C, "config": _C, "alias": _C,
    # The length Representation Engineering writes. Its hard ceiling is a
    # separate question (comfyui_nodes/ai4artsed_comfyui/_text_probes.py).
    "max_new_tokens": _C,
}

FIELDS_BY_FILE = {
    # A lab recording: its parameters carry the instrument's words, its parts
    # are pictures with the instrument's word about each.
    ("latent_lab_recorder_routes.py", "parameters"): _I,
    ("latent_lab_recorder_routes.py", "steps"): _I,
    # A perspective's name is the user's own text, shown in a course's palette.
    ("interception_prompts_routes.py", "name"): _I,
    # The recording: its transcript passes the intake in the chain.
    ("parrot_routes.py", "file"): _R,
    # The document: its text passes the intake in the import job, once the
    # converter has read it.
    ("scene_routes.py", "document"): _R,
    # The language the page is read in, a locale code.
    ("parrot_routes.py", "reading"): _C,
    # Recorded into the run for the research record; nothing reads it back.
    ("schema_pipeline_routes.py", "dialogue"): _C,
    ("schema_pipeline_routes.py", "comparison_context"): _C,
    ("schema_pipeline_routes.py", "trashy_analysis"): _C,
    # Refused by name on /pipeline/interception before anything runs; a song's
    # two texts go through /pipeline/generation. Nothing of it reaches a model.
    ("schema_pipeline_routes.py", "custom_placeholders"): _C,
    # The messages and the picture of the platform's own ComfyUI nodes, whose
    # material passed the intake of the run that started the workflow.
    ("chat_routes.py", "messages"): _C,
    ("chat_routes.py", "image_b64"): _R,
}


# ── Not switched yet ────────────────────────────────────────────────────────
#
# The tables only ever get shorter; an entry whose obligation is met fails
# the run.

PENDING_POINTS = {}

PENDING_EXITS = {}

# Deliveries that do not ask the rule yet, by what they hand out.
PENDING_DELIVERIES = {}

# Research instruments that are open on every level today.
PENDING_RESEARCH_LOCKS = {}

PENDING_LOCAL_ONLY = {}

# Calls that hand a picture to a model without saying whether it may leave.
PENDING_IMAGE_ORIGIN = {}

# Readers of the delivery rule that do not pass the requester's level yet.
PENDING_DELIVERY_LEVEL = {}

# Functions other than views that resolve the level themselves. Each gets it
# from its view as a parameter.
PENDING_LEVEL_OUTSIDE_VIEWS = {}

PENDING_WORKFLOWS = {}


# ── Output chunks ───────────────────────────────────────────────────────────

CHUNK_MAP = {
    # diffusers surface (local generation via get_diffusers_backend)
    "output_image_sd35_diffusers.py": "diffusers",
    "output_image_sd35_img2img_diffusers.py": "diffusers",
    "output_image_sd35_turbo_diffusers.py": "diffusers",
    "output_image_surrealizer_diffusers.py": "diffusers",
    "output_image_surrealizer_comfyui.py": "comfyui",
    "output_image_feature_probing_diffusers.py": "diffusers",
    "output_image_attention_cartography_diffusers.py": "diffusers",
    "output_image_attention_cartography_comfyui.py": "comfyui",
    "output_image_concept_algebra_diffusers.py": "diffusers",
    "output_image_denoising_archaeology_diffusers.py": "diffusers",
    "output_image_denoising_archaeology_comfyui.py": "comfyui",
    "output_image_composable_diffusion_comfyui.py": "comfyui",
    "output_image_concept_algebra_comfyui.py": "comfyui",
    "output_image_feature_probing_comfyui.py": "comfyui",
    "output_image_composable_diffusion_diffusers.py": "diffusers",
    "output_image_flux2_diffusers.py": "diffusers",
    "output_image_flux2_img2img_diffusers.py": "diffusers",
    "output_image_commoncanvas_diffusers.py": "diffusers",
    "output_video_wan22_diffusers.py": "diffusers",
    "output_video_wan22_i2v_diffusers.py": "diffusers",
    # own clients on the GPU service
    "output_audio_stableaudio_diffusers.py": "gpu-service",
    "output_3d_hunyuan3d.py": "gpu-service",
    "output_music_heartmula.py": "gpu-service",
    # subprocess surface: a worker of its own, in its own environment
    "output_speech_voxcpm.py": "subprocess",
    # the espeak-ng binary, run per utterance: rules turn letters into phonemes
    "output_speech_espeak.py": "subprocess",
    # the `piper` binary of its own environment, run per utterance on the CPU
    "output_speech_piper.py": "subprocess",
    # ONNX Runtime on the CPU inside the DevServer process
    "output_speech_supertonic.py": "in-process",
    # ComfyUI surface
    "output_audio_acenet.json": "comfyui",
    "output_image_commoncanvas_xl_c.json": "comfyui",
    "output_image_flux2.json": "comfyui",
    "output_image_flux2_img2img.json": "comfyui",
    "output_image_flux3.json": "comfyui",
    "output_image_flux3_multi.json": "comfyui",
    # Writes the caption of flux3_multi; words only, and they reach the image
    # model through Stage 1, the check and the translation.
    "adaption_image_flux3_upsampler.json": "comfyui",
    "output_image_qwen.json": "comfyui",
    "output_image_qwen_2511_multi.json": "comfyui",
    "output_image_qwen_img2img.json": "comfyui",
    "output_image_sd15.json": "comfyui",
    "output_image_sd35_img2img.json": "comfyui",
    "output_image_sd35_large.json": "comfyui",
    "output_image_sd35_turbo.json": "comfyui",
    "output_image_sdxl.json": "comfyui",
    "output_vector_fusion_clip_sd35.json": "comfyui",
    "output_video_ltx.json": "comfyui",
    "output_video_wan22.json": "comfyui",
    "output_video_wan22_i2v.json": "comfyui",
    "output_video_wan22_t2v_fast.json": "comfyui",
    "output_image_gpt_image_1.json": "cloud-api",
    # passthrough: the "generation" is the stage-2 output itself (code path)
    "output_code_p5js.json": "passthrough",
    "output_code_tonejs.json": "passthrough",
    # live output chunks without the output_ name prefix (loader needs none)
    "dual_encoder_fusion_image.json": "comfyui",
    "legacy_surrealization.json": "comfyui",
}

# The modules of the platform's node package through which a node reaches a
# language model: the chat proxy, a local model, the text probes, the media
# readers.
LANGUAGE_MODEL_HELPERS = {"_devserver", "_local_llm", "_text_probes", "_media_reading"}


# ── Reading the code ────────────────────────────────────────────────────────

def walk_functions(tree):
    """(name, node) for every function, nested ones under their enclosing one.

    A nested function is `outer.inner`; a method keeps its bare name, because
    a class body is not a scope anybody confuses.
    """
    found = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                found.append((name, child))
                visit(child, name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return found


def call_name(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def is_view(node):
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if isinstance(target, ast.Attribute) and target.attr in ("route", "get", "post", "put",
                                                                 "delete", "patch"):
            return True
    return False


def decorator_names(node):
    names = set()
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


class Module:
    def __init__(self, path):
        self.path = path
        self.name = path.name
        self.dotted = ".".join(path.relative_to(DEVSERVER).with_suffix("").parts)
        self.source = path.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source, filename=str(path))
        self.functions = dict(walk_functions(self.tree))
        self.local_names = {}
        self.bare = {}
        for qualname in self.functions:
            self.bare.setdefault(qualname.rsplit(".", 1)[-1], []).append(qualname)
        self.imports = {}
        package = self.dotted.split(".")[:-1]
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package[:len(package) - node.level + 1]
                    origin = ".".join(base + ([node.module] if node.module else []))
                else:
                    origin = node.module
                if not origin:
                    continue
                for alias in node.names:
                    self.imports[alias.asname or alias.name] = (origin, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        self.imports[alias.asname] = (alias.name, None)
                    else:
                        head = alias.name.split(".")[0]
                        self.imports.setdefault(head, (head, None))


@lru_cache(maxsize=None)
def index():
    modules = {}
    for root in INDEX_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            module = Module(path)
            modules[module.dotted] = module
    return modules


def module_by_name(name):
    found = [m for m in index().values() if m.name == name]
    assert len(found) == 1, f"{name} is {len(found)} files under {INDEX_ROOTS}"
    return found[0]


def iter_scan_files():
    files = sorted(p for p in ROUTES_DIR.glob("*.py") if p.name != "__init__.py")
    files += [p for p in EXTRA_SCAN_FILES if p.exists()]
    return files


def resolve(module, node, scope=""):
    """The functions a Name or an Attribute refers to: [(module, qualname)].

    A bare name is looked up as Python looks up a nested function: in the
    functions enclosing `scope` from the inside out, where a parameter or an
    assigned name of the same spelling hides any function, then at module
    level, then among the imports. An attribute resolves on self/cls to the module's
    methods of that name, on an imported module to its function, and on an
    object imported from a module (an instance such as llm_service) to the
    methods of that name in the module it comes from.
    """
    modules = index()
    if isinstance(node, ast.Name):
        parts = scope.split(".") if scope else []
        for depth in range(len(parts), -1, -1):
            prefix = ".".join(parts[:depth])
            candidate = f"{prefix}.{node.id}" if prefix else node.id
            if candidate in module.functions:
                return [(module, candidate)]
            if prefix in module.functions and node.id in local_names(module, prefix):
                return []
        imported = module.imports.get(node.id)
        if imported and imported[1]:
            target = modules.get(imported[0])
            if target and imported[1] in target.functions:
                return [(target, imported[1])]
        return []
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        base = node.value.id
        if base in ("self", "cls"):
            return [(module, q) for q in module.bare.get(node.attr, [])]
        imported = module.imports.get(base)
        if not imported:
            return []
        if imported[1] and f"{imported[0]}.{imported[1]}" not in modules:
            owner = modules.get(imported[0])
            return [(owner, q) for q in owner.bare.get(node.attr, [])] if owner else []
        target = modules.get(f"{imported[0]}.{imported[1]}" if imported[1] else imported[0])
        if target and node.attr in target.functions:
            return [(target, node.attr)]
    return []


def local_names(module, qualname):
    """The parameters of a function and the names its own body assigns."""
    cached = module.local_names.get(qualname)
    if cached is None:
        node = module.functions[qualname]
        args = node.args
        cached = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
        cached |= {a.arg for a in (args.vararg, args.kwarg) if a is not None}
        cached |= {sub.id for sub in _own_nodes(node)
                   if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del))}
        module.local_names[qualname] = cached
    return cached


def referenced(module, qualname):
    """Every function the body of `qualname` and of the functions nested in it
    calls or hands over, one level."""
    out = []
    for inner, node in module.functions.items():
        if inner != qualname and not inner.startswith(qualname + "."):
            continue
        for sub in _own_nodes(node):
            if isinstance(sub, (ast.Name, ast.Attribute)):
                for target in resolve(module, sub, inner):
                    if target != (module, qualname) and target not in out:
                        out.append(target)
    return out


def call_targets(module, qualname, call):
    """The functions a call inside `qualname` reaches."""
    return resolve(module, call.func, qualname)


def calls_in(node):
    return {call_name(n) for n in ast.walk(node) if isinstance(n, ast.Call)}


def reach(module, qualname):
    """The names called in a function and in every function it reaches, one
    level. An exit inside a nested function is reached through its enclosing
    functions as well. A check function is not looked into: calling it is
    what reaches its checkpoint."""
    names = set()
    chain = [qualname]
    parts = qualname.split(".")
    chain += [".".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]
    for name in chain:
        if name not in module.functions:
            continue
        names |= calls_in(module.functions[name])
        for target_module, target in referenced(module, name):
            if target_module.dotted == GATE_MODULE and target in CHECK_FUNCTIONS:
                continue
            names |= calls_in(target_module.functions[target])
    return names


def points_reached(module, qualname):
    called = reach(module, qualname)
    return {point for point, fns in GATE_FUNCTIONS.items() if called & fns}


def scan_generation_sites():
    """{(file, function): sorted marker names} for every hit."""
    sites = {}
    for path in iter_scan_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for name, node in walk_functions(tree):
            segment = ast.get_source_segment(source, node) or ""
            hit = sorted(marker for marker, rx in GENERATION_MARKERS.items() if rx.search(segment))
            if hit:
                sites[(path.name, name)] = hit
        in_function_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                in_function_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        module_src = "\n".join(
            line for i, line in enumerate(source.splitlines(), 1) if i not in in_function_lines)
        hit = sorted(name for name, rx in GENERATION_MARKERS.items() if rx.search(module_src))
        if hit:
            sites[(path.name, "<module>")] = hit
    return sites


def scan_views():
    """{(file, function): node} for every route of a file not exempted."""
    views = {}
    for path in sorted(ROUTES_DIR.glob("*.py")):
        if path.name == "__init__.py" or path.name in EXEMPT_ROUTE_FILES:
            continue
        module = module_by_name(path.name)
        for qualname, node in module.functions.items():
            if is_view(node):
                views[(path.name, qualname)] = node
    return views


def scan_exits():
    """{(file, function, form, name)} for every stream event, station, typed
    event and file delivery in the scanned files."""
    exits = set()
    for path in iter_scan_files():
        module = module_by_name(path.name)
        for qualname, node in module.functions.items():
            for sub in _own_nodes(node):
                if isinstance(sub, ast.Call):
                    name = call_name(sub)
                    if name == "generate_sse_event" and sub.args and isinstance(sub.args[0], ast.Constant):
                        exits.add((path.name, qualname, "event", str(sub.args[0].value)))
                    elif name in ("send_file", "send_from_directory"):
                        exits.add((path.name, qualname, "file", name))
                elif isinstance(sub, ast.Dict):
                    for key, value in zip(sub.keys, sub.values):
                        if isinstance(key, ast.Constant) and key.value == "station":
                            label = value.value if isinstance(value, ast.Constant) else ast.unparse(value)
                            exits.add((path.name, qualname, "station", str(label)))
                elif isinstance(sub, ast.Yield) and isinstance(sub.value, ast.Dict):
                    for key, value in zip(sub.value.keys, sub.value.values):
                        if isinstance(key, ast.Constant) and key.value == "type":
                            label = value.value if isinstance(value, ast.Constant) else ast.unparse(value)
                            exits.add((path.name, qualname, "type", str(label)))
    return exits


def _own_nodes(node):
    """The nodes of a function body, without those of the functions nested in
    it; a lambda's body counts as the function's own."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        sub = stack.pop()
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield sub
        stack.extend(ast.iter_child_nodes(sub))


_REQUEST_ATTRS = {"args", "form", "files", "values", "json"}


def _is_request_source(value):
    """Whether an expression is the request's body or one of its parts."""
    if isinstance(value, ast.BoolOp):
        return _is_request_source(value.values[0])
    if isinstance(value, ast.Call):
        func = value.func
        if isinstance(func, ast.Name) and func.id == "dict" and value.args:
            return _is_request_source(value.args[0])
        if isinstance(func, ast.Attribute) and func.attr in ("get", "pop"):
            return False
        return _is_request_source(func)
    if isinstance(value, ast.Attribute):
        if isinstance(value.value, ast.Name) and value.value.id == "request":
            return value.attr in _REQUEST_ATTRS or value.attr == "get_json"
        return _is_request_source(value.value)
    return False


def _assignments(node):
    """(name, value) for every plain or annotated assignment in a function; a
    tuple target counts with its first name, as in `data, refusal = ...`."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
            target, value = sub.targets[0], sub.value
        elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
            target, value = sub.target, sub.value
        else:
            continue
        if isinstance(target, ast.Tuple) and target.elts:
            target = target.elts[0]
        if isinstance(target, ast.Name):
            yield target.id, value


@lru_cache(maxsize=None)
def body_readers():
    """Names of the functions that hand back the request's body, alone or as
    the first of a pair (streaming_response.object_body), and of the
    functools.partial aliases made of them."""
    names = set()
    for module in index().values():
        for qualname, node in module.functions.items():
            bound = {name for name, value in _assignments(node) if _is_request_source(value)}
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and sub.value is not None:
                    value = sub.value
                    if isinstance(value, ast.Tuple) and value.elts:
                        value = value.elts[0]
                    if _is_request_source(value) or (isinstance(value, ast.Name) and value.id in bound):
                        names.add(qualname.rsplit(".", 1)[-1])
    for module in index().values():
        for node in module.tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)
                    and call_name(node.value) == "partial" and node.value.args
                    and isinstance(node.value.args[0], ast.Name) and node.value.args[0].id in names):
                names.add(node.targets[0].id)
    return frozenset(names)


def _is_body(value):
    """The request's body: one of its parts, or what a body reader hands back."""
    if _is_request_source(value):
        return True
    return isinstance(value, ast.Call) and call_name(value) in body_readers()


def own_fields(node):
    """The request fields a function reads itself: .get('x') and ['x'] on the
    request's parts, on names bound to them or to what a body reader hands
    back, and on a parameter called `data` or `body`, which is how a view hands
    its body to the function behind it."""
    params = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    bound = {a.arg for a in params if a.arg in ("data", "body")}
    bound |= {name for name, value in _assignments(node) if _is_body(value)}

    def on_request(base):
        if isinstance(base, ast.Name):
            return base.id in bound
        return _is_request_source(base)

    fields = set()
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and call_name(sub) == "multi_images_from" and sub.args
                and on_request(sub.args[0])):
            # The pictures of a multi-image run, input_image1 ... input_image10,
            # read as one (schemas/engine/multi_image_params.py).
            fields |= set(MULTI_IMAGE_KEYS)
        if isinstance(sub, ast.Call):
            # a helper handed the body and a key, as in _float(data, 'cfg', 7.0)
            for arg, key in zip(sub.args, sub.args[1:]):
                if (isinstance(arg, ast.Name) and arg.id in bound and isinstance(key, ast.Constant)
                        and isinstance(key.value, str)):
                    fields.add(key.value)
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in ("get", "pop") and sub.args
                and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str)
                and on_request(sub.func.value)):
            fields.add(sub.args[0].value)
        elif (isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant)
              and isinstance(sub.slice.value, str) and on_request(sub.value)):
            fields.add(sub.slice.value)
    return fields


def fields_of(module, qualname):
    """The fields a declared way reads: its own, and those of the functions of
    the same file it reaches, one level."""
    fields = own_fields(module.functions[qualname])
    for target_module, target in referenced(module, qualname):
        if target_module is module:
            fields |= own_fields(module.functions[target])
    return fields


def field_class(file, field):
    return FIELDS_BY_FILE.get((file, field)) or FIELDS.get(field)


def intake_field_names(module, qualname):
    """The field names the intake calls of a way name, one level."""
    names = set()
    nodes = [module.functions[qualname]]
    nodes += [m.functions[q] for m, q in referenced(module, qualname)]
    for node in nodes:
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            name = call_name(sub)
            if name == "check_intake":
                for keyword in sub.keywords:
                    if keyword.arg == "field":
                        names |= _field_literal(keyword.value)
            elif name == "check_intake_texts" and sub.args and isinstance(sub.args[0], ast.Dict):
                for key in sub.args[0].keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        names.add(key.value)
    return names


def _field_literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value.split("[", 1)[0]}
    if isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[0], ast.Constant):
        return {str(node.values[0].value).split("[", 1)[0]}
    return set()


def _site(file, qualname):
    module = module_by_name(file)
    assert qualname in module.functions, f"{file}: no function {qualname}"
    return module


# ── The census ──────────────────────────────────────────────────────────────

def test_every_generation_site_is_declared():
    undeclared = {site: m for site, m in scan_generation_sites().items() if site not in WAYS}
    assert not undeclared, (
        "Sites that can reach a model, without a declaration. Declare each in WAYS: "
        "the checkpoints its way reaches, or the exception it is:\n"
        + "\n".join(f'    ("{f}", "{fn}"): ...,   # markers: {m}'
                    for (f, fn), m in sorted(undeclared.items()))
    )


def test_every_route_is_declared():
    undeclared = sorted(site for site in scan_views() if site not in WAYS)
    assert not undeclared, (
        "Routes without a declaration. Declare each in WAYS, or exempt the whole "
        "file in EXEMPT_ROUTE_FILES with its reason:\n"
        + "\n".join(f'    ("{f}", "{fn}"): ...,' for f, fn in undeclared)
    )


def test_no_stale_declarations():
    stale = []
    for file, qualname in WAYS:
        module = module_by_name(file)
        if qualname != "<module>" and qualname not in module.functions:
            stale.append((file, qualname))
    assert not stale, f"WAYS declares functions that no longer exist: {stale}"


def test_every_way_reaches_its_checkpoints():
    missing, stale = [], []
    for (file, qualname), declared in WAYS.items():
        if not isinstance(declared, Way):
            continue
        reached = points_reached(_site(file, qualname), qualname)
        for point in declared.points:
            key = (file, qualname, point)
            if point not in reached and key not in PENDING_POINTS:
                missing.append(f"{file}:{qualname} does not reach {point}")
            if point in reached and key in PENDING_POINTS:
                stale.append(f"{file}:{qualname} reaches {point} - remove it from PENDING_POINTS")
    assert not missing, "Ways that miss a checkpoint:\n" + "\n".join(missing)
    assert not stale, "Switched ways still listed as pending:\n" + "\n".join(stale)


def test_pending_points_name_declared_obligations():
    orphans = [key for key in PENDING_POINTS
               if not isinstance(WAYS.get(key[:2]), Way) or key[2] not in WAYS[key[:2]].points]
    assert not orphans, f"PENDING_POINTS names obligations WAYS does not declare: {orphans}"


def _hand_over_target(file, qualname, runner):
    """Where a function hands its run: (file, qualname) of `runner` among the
    functions it reaches, or None."""
    for target_module, target in referenced(_site(file, qualname), qualname):
        if runner in (target, target.rsplit(".", 1)[-1]):
            return target_module.name, target
    return None


def final_way(file, qualname, seen=()):
    """The declared way a run ends in, following its hand-overs, or None."""
    declared = WAYS.get((file, qualname))
    if isinstance(declared, Way):
        return file, qualname
    if not (isinstance(declared, Exempt) and declared.kind == "hands_to"):
        return None
    target = _hand_over_target(file, qualname, declared.target)
    if target is None or target in seen:
        return None
    return final_way(*target, seen + ((file, qualname),))


def test_a_view_that_hands_over_reaches_its_runner():
    wrong = []
    for (file, qualname), declared in WAYS.items():
        if not (isinstance(declared, Exempt) and declared.kind == "hands_to"):
            continue
        if _hand_over_target(file, qualname, declared.target) is None:
            wrong.append(f"{file}:{qualname} never reaches {declared.target}")
        elif final_way(file, qualname) is None:
            wrong.append(f"{file}:{qualname} hands to {declared.target}, which is no declared "
                         "way and hands on to none")
    assert not wrong, "\n".join(wrong)


def referrers():
    """Who refers to each function: {(file, qualname): {(file, qualname)}}.
    Module-level code (a table of handlers, a registration) counts as
    (file, "<module>")."""
    out = {}
    for module in index().values():
        for qualname in module.functions:
            for target_module, target in referenced(module, qualname):
                out.setdefault((target_module.name, target), set()).add((module.name, qualname))
        for statement in module.tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nodes = statement.decorator_list
            else:
                nodes = [statement]
            for node in nodes:
                for sub in ast.walk(node):
                    if isinstance(sub, (ast.Name, ast.Attribute)):
                        for target_module, target in resolve(module, sub):
                            out.setdefault((target_module.name, target), set()).add(
                                (module.name, "<module>"))
    return out


def test_a_step_is_called_by_something():
    refs = referrers()
    orphans = []
    for (file, qualname), declared in WAYS.items():
        if not isinstance(declared, Exempt) or declared.kind != "step":
            continue
        if not refs.get((file, qualname), set()) - {(file, qualname)}:
            orphans.append(f"{file}:{qualname}")
    assert not orphans, ("Declared steps that nothing calls; an entry point is a way, "
                         "not a step:\n" + "\n".join(orphans))


def _names_research(module, qualname):
    """Whether the function, or one it reaches, resolves the level and names research."""
    nodes = [module.functions[qualname]] + [m.functions[q] for m, q in referenced(module, qualname)]
    for node in nodes:
        if "resolve_safety_level" not in calls_in(node):
            continue
        if any(isinstance(sub, ast.Constant) and sub.value == "research" for sub in ast.walk(node)):
            return True
    return False


def test_research_instruments_are_locked():
    open_, stale = [], []
    for (file, qualname), declared in WAYS.items():
        if not isinstance(declared, Exempt) or declared.kind != "research":
            continue
        locked = _names_research(_site(file, qualname), qualname)
        pending = (file, qualname) in PENDING_RESEARCH_LOCKS
        if not locked and not pending:
            open_.append(f"{file}:{qualname}")
        if locked and pending:
            stale.append(f"{file}:{qualname} - remove it from PENDING_RESEARCH_LOCKS")
    assert not open_, "Research instruments without a lock:\n" + "\n".join(open_)
    assert not stale, "\n".join(stale)


def test_administration_sits_behind_the_settings_password():
    open_ = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        if path.name not in SETTINGS_PASSWORD_FILES:
            continue
        module = module_by_name(path.name)
        for qualname, node in module.functions.items():
            if is_view(node) and "require_settings_auth" not in decorator_names(node):
                open_.append(f"{path.name}:{qualname}")
    assert not open_, "Routes of a password file without the password:\n" + "\n".join(open_)


def test_the_proxy_answers_this_machine_only():
    open_, stale = [], []
    for (file, qualname), declared in WAYS.items():
        if not isinstance(declared, Exempt) or declared.kind != "local":
            continue
        module = _site(file, qualname)
        nodes = [module.functions[qualname]] + [m.functions[q] for m, q in referenced(module, qualname)]
        local = any("CF-Connecting-IP" in (ast.get_source_segment(module.source, n) or "")
                    or any(isinstance(s, ast.Constant) and s.value == "CF-Connecting-IP"
                           for s in ast.walk(n))
                    for n in nodes)
        pending = (file, qualname) in PENDING_LOCAL_ONLY
        if not local and not pending:
            open_.append(f"{file}:{qualname}")
        if local and pending:
            stale.append(f"{file}:{qualname} - remove it from PENDING_LOCAL_ONLY")
    assert not open_, "Local-only routes that answer anyone:\n" + "\n".join(open_)
    assert not stale, "\n".join(stale)


def test_deliveries_ask_the_rule():
    unasked, stale = [], []
    declared = {k: v for k, v in WAYS.items() if isinstance(v, Exempt) and v.kind == "delivery"}
    for (file, qualname), _decl in declared.items():
        asks = bool(reach(_site(file, qualname), qualname) & DELIVERY_RULE)
        pending = (file, qualname) in PENDING_DELIVERIES
        if not asks and not pending:
            unasked.append(f"{file}:{qualname}")
        if asks and pending:
            stale.append(f"{file}:{qualname} - remove it from PENDING_DELIVERIES")
    orphans = [k for k in PENDING_DELIVERIES if k not in declared]
    assert not unasked, "Deliveries that do not ask the rule:\n" + "\n".join(unasked)
    assert not stale, "\n".join(stale)
    assert not orphans, f"PENDING_DELIVERIES names no declared delivery: {orphans}"


# ── Exits ───────────────────────────────────────────────────────────────────

def test_every_exit_is_declared():
    undeclared = sorted(e for e in scan_exits() if e not in EXITS)
    assert not undeclared, (
        "What leaves the server here is not declared. Declare each in EXITS with "
        "the checkpoints its content passed, or the reason it carries no model text "
        "and no picture:\n" + "\n".join(f"    {e!r}: ...," for e in undeclared)
    )


def test_no_stale_exits():
    found = scan_exits()
    stale = sorted(e for e in EXITS if e not in found)
    assert not stale, f"EXITS declares what the scan no longer finds: {stale}"


def test_exits_reach_their_checks():
    missing, stale = [], []
    for key, declared in EXITS.items():
        file, qualname = key[0], key[1]
        if isinstance(declared, Exempt):
            if (declared.kind == "chat"
                    and INTAKE not in points_reached(_site(file, qualname), qualname)):
                missing.append(f"{key}: a chat's exit whose turn does not reach the intake")
            continue
        reached = points_reached(_site(file, qualname), qualname)
        unmet = [p for p in declared if p not in reached]
        if unmet and key not in PENDING_EXITS:
            missing.append(f"{key}: misses {unmet}")
        if not unmet and key in PENDING_EXITS:
            stale.append(f"{key} - remove it from PENDING_EXITS")
    orphans = [k for k in PENDING_EXITS if isinstance(EXITS.get(k), Exempt) or k not in EXITS]
    assert not missing, "Exits whose content passed no check:\n" + "\n".join(missing)
    assert not stale, "\n".join(stale)
    assert not orphans, f"PENDING_EXITS names no declared exit with checks: {orphans}"


def test_file_deliveries_ask_the_rule():
    unasked = []
    for key, declared in EXITS.items():
        if not (isinstance(declared, Exempt) and declared.kind == "delivery"):
            continue
        file, qualname = key[0], key[1]
        if (file, qualname) in PENDING_DELIVERIES:
            continue
        if not reach(_site(file, qualname), qualname) & DELIVERY_RULE:
            unasked.append(str(key))
    assert not unasked, "File deliveries that do not ask the rule:\n" + "\n".join(unasked)


# ── Request fields ──────────────────────────────────────────────────────────

def _carries_a_run(declared):
    return isinstance(declared, Way) or (isinstance(declared, Exempt) and declared.kind == "hands_to")


def _field_bearing_sites():
    """The views of the files not exempted, every declared way and every hand-over."""
    sites = set(scan_views())
    sites |= {site for site, declared in WAYS.items() if _carries_a_run(declared)}
    return sorted(site for site in sites if site[1] in module_by_name(site[0]).functions)


def test_every_request_field_is_declared():
    undeclared = []
    for file, qualname in _field_bearing_sites():
        for field in sorted(fields_of(module_by_name(file), qualname)):
            if field_class(file, field) is None:
                undeclared.append(f"{file}:{qualname} reads {field!r}")
    assert not undeclared, (
        "Request fields nobody declared. Enter each in FIELDS (or FIELDS_BY_FILE) as "
        "intake, reference or control:\n" + "\n".join(undeclared)
    )


def test_no_stale_field_declarations():
    read = {}
    for file, qualname in _field_bearing_sites():
        for field in fields_of(module_by_name(file), qualname):
            read.setdefault(field, set()).add(file)
    stale = sorted(f for f in FIELDS if f not in read)
    stale += sorted(f"{f} in {file}" for file, f in FIELDS_BY_FILE if file not in read.get(f, ()))
    assert not stale, f"Declared request fields that no route reads: {stale}"


def test_intake_fields_reach_the_intake():
    # What a view reads and hands over travels to the way its run ends in.
    handed = {}
    for (file, qualname), declared in WAYS.items():
        if isinstance(declared, Exempt) and declared.kind == "hands_to":
            end = final_way(file, qualname)
            if end:
                handed.setdefault(end, set()).update(
                    (file, f) for f in fields_of(module_by_name(file), qualname))
    missing = []
    for (file, qualname), declared in WAYS.items():
        if not isinstance(declared, Way) or INTAKE not in declared.points:
            continue
        if (file, qualname, INTAKE) in PENDING_POINTS:
            continue
        module = _site(file, qualname)
        fields = {(file, f) for f in fields_of(module, qualname)} | handed.get((file, qualname), set())
        named = intake_field_names(module, qualname)
        for source, field in sorted(fields):
            if field_class(source, field) == _I and field not in named:
                missing.append(f"{file}:{qualname} takes {field!r} ({source}) and its intake "
                               "does not name it")
    assert not missing, "Material that does not reach the intake:\n" + "\n".join(missing)


# ── The level, pictures, workflows ──────────────────────────────────────────

def test_the_level_is_resolved_in_views():
    """resolve_safety_level() stands in views only, and a run carries the level
    its view resolved. Off the request thread the resolver answers the
    strictest level, whatever the course is (safety_level_resolver.py)."""
    wrong, stale, found = [], [], set()
    for module in index().values():
        if module.name == "safety_level_resolver.py":
            continue
        for qualname, node in module.functions.items():
            if "resolve_safety_level" not in {call_name(n) for n in _own_nodes(node)
                                              if isinstance(n, ast.Call)}:
                continue
            key = (module.name, qualname)
            found.add(key)
            if not is_view(node) and key not in PENDING_LEVEL_OUTSIDE_VIEWS:
                wrong.append(f"{module.name}:{qualname}")
            if is_view(node) and key in PENDING_LEVEL_OUTSIDE_VIEWS:
                stale.append(f"{key} is a view - remove it from PENDING_LEVEL_OUTSIDE_VIEWS")
    stale += [f"{key} no longer resolves the level - remove it from PENDING_LEVEL_OUTSIDE_VIEWS"
              for key in PENDING_LEVEL_OUTSIDE_VIEWS if key not in found]
    assert not wrong, ("The level is resolved outside a view; take it from the view as a "
                       "parameter:\n" + "\n".join(wrong))
    assert not stale, "\n".join(stale)


# The calls through which a picture reaches a model, where the caller says
# whether it may leave this server (may_leave_server=), with the picture's
# position among the positional arguments.
IMAGE_HANDOVERS = {
    ("chat_routes.py", "_chain_attempts"): 1,
    ("chat_routes.py", "call_chat_helper"): 6,
    ("chat_routes.py", "call_chat_helper_stream"): 6,
    ("vision_support.py", "ask_about_image"): 0,
}
# The calls that carry a picture on after that decision, the picture's
# position, and the only functions they may carry one from.
IMAGE_AFTER_DECISION = {
    ("chat_routes.py", "_dispatch_single_model"):
        (6, {("chat_routes.py", "call_chat_helper"), ("chat_routes.py", "_dispatch_single_model_stream")}),
    ("chat_routes.py", "_dispatch_single_model_stream"):
        (6, {("chat_routes.py", "call_chat_helper_stream")}),
    ("chat_routes.py", "_call_cloud_chat"): (7, {("chat_routes.py", "_dispatch_single_model")}),
    ("openai_style_stream.py", "call_chat"):
        (6, {("chat_routes.py", "_call_cloud_chat"), ("vision_support.py", "ask_about_image")}),
    ("llm_service.py", "ask_about_image"): (0, {("vision_support.py", "ask_about_image")}),
}
# Pictures the platform draws itself: nothing in them comes from a user or a run.
PLATFORM_PICTURES = {
    ("model_capabilities.py", "_probe_image"): "the capability probe's test picture (build_test_image)",
}


def _passes_image(call, position):
    for keyword in call.keywords:
        if keyword.arg == "image_b64":
            return not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None)
    if len(call.args) > position:
        arg = call.args[position]
        return not (isinstance(arg, ast.Constant) and arg.value is None)
    return False


def test_a_picture_travels_with_its_origin():
    known = {}
    for target, position in IMAGE_HANDOVERS.items():
        known.setdefault(target[1], []).append(position)
    for target, (position, _allowed) in IMAGE_AFTER_DECISION.items():
        known.setdefault(target[1], []).append(position)
    wrong, stale, misplaced, unplaced = [], [], [], []
    for module in index().values():
        for qualname, node in module.functions.items():
            here = (module.name, qualname)
            for sub in _own_nodes(node):
                if not isinstance(sub, ast.Call):
                    continue
                targets = {(m.name, q) for m, q in call_targets(module, qualname, sub)}
                for target in targets & IMAGE_HANDOVERS.keys():
                    if not _passes_image(sub, IMAGE_HANDOVERS[target]):
                        continue
                    says = any(k.arg == "may_leave_server" for k in sub.keywords)
                    key = (module.name, qualname, target[1])
                    if not says and key not in PENDING_IMAGE_ORIGIN:
                        wrong.append(f"{module.name}:{qualname} -> {target[1]}")
                    if says and key in PENDING_IMAGE_ORIGIN:
                        stale.append(f"{key} - remove it from PENDING_IMAGE_ORIGIN")
                for target in targets & IMAGE_AFTER_DECISION.keys():
                    position, allowed = IMAGE_AFTER_DECISION[target]
                    if _passes_image(sub, position) and here not in allowed and here not in PLATFORM_PICTURES:
                        misplaced.append(f"{module.name}:{qualname} -> {target[1]}")
                name = call_name(sub)
                if not targets and name in known and _passes_image(sub, min(known[name])):
                    unplaced.append(f"{module.name}:{qualname} -> {name}")
    assert not wrong, ("A picture reaches a model without the caller saying whether it "
                       "may leave this server (may_leave_server=):\n" + "\n".join(wrong))
    assert not stale, "\n".join(stale)
    assert not misplaced, ("A picture is carried on to a model before anyone decided whether "
                           "it may leave this server:\n" + "\n".join(misplaced))
    assert not unplaced, ("A call that may carry a picture to a model, which the scan cannot "
                          "place; call it by its name or its module:\n" + "\n".join(unplaced))


# The rule, the doors built on it, and what reads a picture through them, each
# with the number of positional arguments before the level of whoever asks: a
# call passes when it hands more than that, or names `level`.
_DELIVERY_READERS = {
    "entity_cleared_for_delivery": 2, "filter_deliverable": 2,
    "checked_entity_path": 1, "checked_path_for_filename": 1,
    "resolve_media_ref": 1, "load_image_b64": 1, "prepare_image_b64": 2,
    "analyze_image_from_run": 3, "resolve_part_path": 2, "_resolve_media_url_to_path": 1,
    "_first_cleared_image": 1, "resolve_preview_media": 2, "_entity_refusal": 2,
    "_resolve_image": 2, "_resolve_ref": 3, "validate_inputs": 2,
    "_image_file": 1, "_image_version": 1, "_picture_fields": 2,
    "_entity_text": 2, "load_session_context": 1, "_resolve_brought_image_b64": 1,
    "_brought_captions": 1,
}


def test_delivery_reads_the_level_of_the_requester():
    wrong, stale = [], []
    for module in index().values():
        for qualname, node in module.functions.items():
            for sub in _own_nodes(node):
                if not isinstance(sub, ast.Call) or call_name(sub) not in _DELIVERY_READERS:
                    continue
                passes = (len(sub.args) > _DELIVERY_READERS[call_name(sub)]
                          or any(k.arg == "level" for k in sub.keywords))
                key = (module.name, qualname)
                if not passes and key not in PENDING_DELIVERY_LEVEL:
                    wrong.append(f"{module.name}:{qualname}")
                if passes and key in PENDING_DELIVERY_LEVEL:
                    stale.append(f"{key} - remove it from PENDING_DELIVERY_LEVEL")
    assert not wrong, ("Delivery reads a verdict without the level of whoever asks:\n"
                       + "\n".join(wrong))
    assert not stale, "\n".join(stale)


# The platform's own calls of a language model, by name.
LANGUAGE_MODEL_CALLS = {
    "call_chat_helper", "call_chat_helper_stream", "_chain_attempts", "chat_completion",
    "execute_stage2_interception", "execute_stage2_with_optimization",
    "execute_optimization", "translate_one", "_translate_list", "_translate_encoder_text",
    "_translate_for_model",
    "_translate_context", "ask_about_image", "describe_image_for_fallback", "derive_search_term",
    "run_llm_steps", "build_prompts", "_surrealizer_build_prompts",
    # Re-enactment: the writer and its renderings. Speech: the English
    # rendering for a voice that has none for the language.
    "_write_song", "_read_in", "_translate_to_english",
}


def test_no_language_model_between_the_check_and_the_media_model():
    """What check_before_model judged is what the media model gets: no language
    model of the platform rewrites it in between. Read in source order inside
    each function that calls the check."""
    wrong = []
    for module in index().values():
        for qualname, node in module.functions.items():
            calls = [n for n in _own_nodes(node) if isinstance(n, ast.Call)]
            checks = [n.lineno for n in calls if call_name(n) == "check_before_model"]
            if not checks:
                continue
            later = sorted({call_name(n) for n in calls
                            if n.lineno > min(checks) and call_name(n) in LANGUAGE_MODEL_CALLS})
            if later:
                wrong.append(f"{module.name}:{qualname} calls {later} after check_before_model")
    assert not wrong, "\n".join(wrong)


def language_model_nodes():
    """The class names of the platform's nodes that reach a language model."""
    init = (NODES_DIR / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(init)
    module_of = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for alias in node.names:
                module_of[alias.asname or alias.name] = node.module
    mappings = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS"
                                                 for t in node.targets)):
            for key, value in zip(node.value.keys, node.value.values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Name):
                    mappings[key.value] = module_of.get(value.id)
    llm = set()
    for class_type, module in mappings.items():
        if not module:
            continue
        source = (NODES_DIR / f"{module}.py").read_text(encoding="utf-8")
        if any(re.search(rf"\b{helper}\b", source) for helper in LANGUAGE_MODEL_HELPERS):
            llm.add(class_type)
    return llm


def test_media_workflows_carry_no_language_model():
    llm = language_model_nodes()
    assert llm, "found no language-model node in the package; the scan is broken"
    carrying, stale = [], []
    for path in sorted(CHUNKS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        workflow = data.get("workflow")
        nodes = [n for n in (workflow or {}).values() if isinstance(n, dict)] if isinstance(workflow, dict) else []
        hits = sorted({str(n.get("class_type")) for n in nodes if n.get("class_type") in llm})
        if hits and path.name not in PENDING_WORKFLOWS:
            carrying.append(f"{path.name}: {hits}")
        if not hits and path.name in PENDING_WORKFLOWS:
            stale.append(f"{path.name} - remove it from PENDING_WORKFLOWS")
    assert not carrying, ("A media workflow runs a language model after the check before "
                          "the model:\n" + "\n".join(carrying))
    assert not stale, "\n".join(stale)


def test_every_way_says_what_it_is():
    vague = [k for k, v in WAYS.items()
             if isinstance(v, Exempt) and v.kind != "hands_to" and not v.reason.strip()]
    vague += [k for k, v in EXITS.items() if isinstance(v, Exempt) and not v.reason.strip()]
    sounds = [k for k, v in list(WAYS.items()) + list(EXITS.items())
              if (isinstance(v, Way) and v.sound and not v.sound.startswith("#"))
              or (isinstance(v, Exempt) and v.kind == "sound" and not v.target.startswith("#"))]
    assert not vague, f"Exceptions without a reason: {vague}"
    assert not sounds, f"An open sound check names no ticket: {sounds}"


# ── Output chunks ───────────────────────────────────────────────────────────

def scan_output_chunks():
    """Output chunks by what they ARE, not what they are named: .json chunks
    census by their type field (the loader requires no name prefix), .py
    chunks by the output_ naming convention the router uses."""
    chunks = []
    for p in sorted(CHUNKS_DIR.iterdir()):
        if p.suffix == ".py" and p.name.startswith("output_"):
            chunks.append(p.name)
        elif p.suffix == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                chunks.append(p.name)  # unreadable chunk file: declare or fix it
                continue
            if data.get("type") == "output_chunk" or p.name.startswith("output_"):
                chunks.append(p.name)
    return chunks


def test_every_output_chunk_is_declared():
    undeclared = [c for c in scan_output_chunks() if c not in CHUNK_MAP]
    assert not undeclared, (
        "Output chunks without a declared surface. Declare each in CHUNK_MAP as one "
        "of: diffusers, comfyui, cloud-api, gpu-service, subprocess, in-process, "
        "passthrough:\n" + "\n".join(f'    "{c}": "<surface>",' for c in undeclared)
    )


def test_no_stale_chunk_declarations():
    found = set(scan_output_chunks())
    stale = [c for c in CHUNK_MAP if c not in found]
    assert not stale, f"CHUNK_MAP declares chunks that no longer exist: {sorted(stale)}"


def test_declared_diffusers_chunks_match_code():
    """A .py chunk declared 'diffusers' must actually route through the
    diffusers backend accessor, and one declared otherwise must not."""
    for name, surface in CHUNK_MAP.items():
        if not name.endswith(".py"):
            continue
        source = (CHUNKS_DIR / name).read_text(encoding="utf-8")
        uses = "get_diffusers_backend" in source
        if surface == "diffusers":
            assert uses, f"{name} declared diffusers but never calls get_diffusers_backend"
        else:
            assert not uses, f"{name} calls get_diffusers_backend but is declared {surface}"


def test_declared_json_chunk_surface_matches_backend_field():
    """A .json chunk's declared surface must match its own backend field."""
    backend_to_surface = {
        "comfyui": "comfyui",
        "openai": "cloud-api",
        "mammouth": "cloud-api",
        "passthrough": "passthrough",
    }
    for name, surface in CHUNK_MAP.items():
        if not name.endswith(".json"):
            continue
        data = json.loads((CHUNKS_DIR / name).read_text(encoding="utf-8"))
        backend = data.get("backend") or data.get("backend_type") or ""
        expected = backend_to_surface.get(backend)
        assert expected is not None, (
            f"{name} carries backend={backend!r} which this test does not know - "
            "a NEW surface: extend backend_to_surface"
        )
        assert surface == expected, (
            f"{name} declared {surface} but its backend field says {backend} ({expected})"
        )


if __name__ == "__main__":
    if "--report" in sys.argv:
        print("# --- sites that can reach a model ---")
        for (f, fn), m in sorted(scan_generation_sites().items()):
            print(f'    ("{f}", "{fn}"),   # markers: {",".join(m)}')
        print("# --- routes ---")
        for f, fn in sorted(scan_views()):
            print(f'    ("{f}", "{fn}"),')
        print("# --- exits ---")
        for e in sorted(scan_exits()):
            print(f"    {e!r},")
        print("# --- output chunks ---")
        for c in scan_output_chunks():
            print(f'    "{c}",')
    else:
        failures = 0
        for fn_name, fn in sorted(globals().items()):
            if fn_name.startswith("test_") and callable(fn):
                try:
                    fn()
                    print(f"PASS {fn_name}")
                except AssertionError as e:
                    failures += 1
                    print(f"FAIL {fn_name}\n{e}")
        sys.exit(1 if failures else 0)
