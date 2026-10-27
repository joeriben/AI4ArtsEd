#!/usr/bin/env python3
"""
Coverage-map guard: every place that can trigger generation must carry a
declared check class (work order A11, docs/WORK_ORDER_CONTENT_CHECKING.md).

The platform generates on five separate surfaces, and past coverage reports
drifted because nothing failed when a new generating path appeared. This test
is that failure: it scans the route files and the chunk folder, and any
generation site or output chunk it finds that the declared map below does not
name FAILS the run with instructions.

Scanning is deliberately text/AST based, not import based: chunks are loaded
by file path (backend_router.py) and the backend is re-detected at runtime,
so import edges prove nothing (work order §4).

The declared class documents what checks stand on that path TODAY. It is a
statement of fact, not of intent — when A6 (the shared door) lands, the
classes tighten. Declaring a site "unchecked-proxy" does not make it safe;
it makes the gap visible and reviewed instead of silent.

If this test fails:
  (a) a new generation site: add it to ROUTE_MAP with the check class that
      actually protects it (read the work order first), or
  (b) a new output chunk: add it to CHUNK_MAP with its surface, or
  (c) a site/chunk disappeared: remove the stale declaration.

Run:  pytest devserver/tests/test_safety_coverage_map.py
      python3 devserver/tests/test_safety_coverage_map.py --report   (print scan)
"""

import ast
import re
import sys

from file_modules import DEVSERVER

ROUTES_DIR = DEVSERVER / "my_app" / "routes"
CHUNKS_DIR = DEVSERVER / "schemas" / "chunks"

# Service files that execute generation behind a route-started thread or a
# subprocess (work order §4: Unterprozesse are the fifth surface).
EXTRA_SCAN_FILES = [
    DEVSERVER / "my_app" / "services" / "canvas_executor.py",
    DEVSERVER / "my_app" / "services" / "canvas_run_service.py",
    DEVSERVER / "my_app" / "services" / "post_production_service.py",
    DEVSERVER / "my_app" / "services" / "training_service.py",
    DEVSERVER / "my_app" / "services" / "blender_service.py",
]

# What counts as "can trigger generation" inside a function body.
# Markers are matched against the function's source segment.
# Known blind spots (adversarial review 2026-08-08): an aliased import
# (`... as gen`) and a requests.post on a URL variable without these name
# fragments stay invisible — the map is a tripwire, not a proof.
GENERATION_MARKERS = {
    "stage4": re.compile(r"execute_stage4_generation_only\s*\(|execute_generation_stage4\s*\("),
    "pipeline": re.compile(r"\.execute_pipeline\s*\("),
    "interception-engine": re.compile(r"PromptInterceptionEngine\s*\("),
    "gpu-proxy": re.compile(r"GPU_SERVICE|17803"),
    "comfyui": re.compile(r"COMFYUI|17804|submit_workflow"),
    "subprocess": re.compile(r"subprocess\.|Popen\s*\(|\bffmpeg\b"),
    "post-production": re.compile(r"post_production_service|compose_media_files"),
    "chat-llm": re.compile(r"call_chat_helper|chat_completion"),
    # The clients ARE the way to the GPU service. A route that stops naming
    # GPU_SERVICE and calls the shared client instead must not thereby drop out
    # of this census -- that is exactly how a surface goes quiet.
    "local-llm-client": re.compile(r"get_llm_backend\s*\(|get_media_analysis_client\s*\("),
    # The stage-2 engines and the gate's free of ComfyUI: a route that calls
    # them names no station and must not thereby drop out of this census
    # (second review of 2026-10-10).
    "stage2-engine": re.compile(r"execute_stage2_(?:interception|classifier|with_optimization)\s*\("),
    "comfyui-free": re.compile(r"free_comfyui\s*\("),
    # The same lesson twice more, found by a safety review on 2026-09-03.
    # `llm_service.analyze_image` reads a user's uploaded picture with a VLM and
    # names none of the fragments above, so /media/analyze/image sat outside
    # this census entirely; `_get_client()` in text_routes hands user text to
    # the GPU service for embeddings, attention and tokenisation and did the
    # same. A shape is invisible until somebody writes it down.
    "llm-service": re.compile(r"\bllm_service\.\w+\s*\("),
    "text-client": re.compile(r"_get_client\s*\(\s*\)"),
    # The lesson a third time, at stage 4 of the move to ComfyUI (2026-09-14):
    # the Fusion Workbench stopped naming GPU_SERVICE and runs its graphs
    # through `latent_lab_context_graphs.run_graph`, which submits to ComfyUI.
    "graph-runner": re.compile(r"\brun_graph\s*\("),
    # And a fourth time, the same day: a route that hands its work to
    # `answered_either_way` names no marker of its own and reaches the card
    # through the function it hands over. The research routes of the Fusion
    # Workbench stood in this map by hand and fell out of it when their
    # docstring stopped naming 17803.
    "handed-over": re.compile(r"\banswered_either_way\s*\("),
    # A fifth time, at stage 6 (2026-09-14): the Crossmodal Lab's routes
    # stopped naming GPU_SERVICE and queue their one-node prompts through
    # `LLMClient.run_node_files`, the node transport every local inference of
    # the platform goes through since stage 3.
    "node-runner": re.compile(r"\brun_node(?:_files)?\s*\("),
    # A fifth time, at stage 5 of the move (2026-09-14): the coreference
    # contrast, BBQ and Representation Engineering stopped calling the text
    # client and run their model through `text_probes.<probe>(...)`, one
    # prompt of a node on ComfyUI.
    "text-probes": re.compile(r"\btext_probes\.\w+\s*\("),
}

# ---------------------------------------------------------------------------
# THE MAP — (route file, function) -> declared check class.
# Classes in use today (work order §3 table):
#   stage1+stage3+vlm   full chain (entry check, pre-generation check, lookback)
#   stage3+vlm          pre-generation check + image lookback
#   stage1+stage3       entry + pre-generation, no lookback on this path
#   stage1              entry check only (stage 2 ends this path)
#   vlm                 image lookback only
#   safety-quick        the /pipeline/safety/quick checks themselves
#   course-level-only   safety level resolved, content checks elsewhere/absent
#   unchecked-proxy     direct pass-through — work order §4, closed by A6/A7
#   subprocess          runs a local tool (ffmpeg, blender, training) on run
#                       artifacts or datasets; no content check of its own —
#                       the fifth surface of work order §4, A6/A8 territory
#   not-generating      matches a marker but produces no media (translation,
#                       status, config lookup, media serving, ...)
#   dead                registered nowhere / no caller (work order §4)
#
# CHUNK_MAP surfaces: diffusers, comfyui, cloud-api, gpu-service, subprocess,
# passthrough — the five of work order §4 plus the stage-2 passthrough — and
# `in-process` for the one chunk that generates inside this very process
# (Supertonic on the CPU). A new surface belongs in the work order's §4 table
# as well as here.
# ---------------------------------------------------------------------------
ROUTE_MAP = {
    # --- the generation core (work order §3 coverage table) ---
    ("schema_pipeline_routes.py", "generation_endpoint"): "stage3+vlm",
    ("schema_pipeline_routes.py", "execute_generation_stage4"): "stage3+vlm",
    # A run with a second text (secondary_text, the Flow's song since
    # 2026-10-06) passes Stage 1 here as well, for its prompt and that text.
    ("schema_pipeline_routes.py", "execute_generation_streaming"): "stage3+vlm",
    ("schema_pipeline_routes.py", "execute_generation_streaming._generation_thread"): "stage3+vlm",
    # The image encoding, split out of the same route when it was put on the
    # shared transport. Same route, same class as its parent.
    ("schema_pipeline_routes.py", "execute_generation_streaming._encode_info_work"): "stage3+vlm",
    ("schema_pipeline_routes.py", "execute_stage4_generation_only"): "stage3+vlm",
    # /pipeline/direct (until 2026-08-24 /pipeline/legacy). Declared at the inner
    # runner, because that is where the scan finds the generation site and where
    # the three checks are actually called; the view function only routes to it.
    ("schema_pipeline_routes.py", "_run_direct_workflow"): "stage1+stage3+vlm",
    # /pipeline/interception. The route was split on 2026-09-04 so that one run
    # can be answered either as a JSON body or as a stream that outlives the
    # edge's 100-second cut, and the run — with every marker this census looks
    # for — moved into `_run_interception_pipeline`. Same path, same checks; the
    # view function `interception_pipeline` now only parses the request, resolves
    # the safety level and chooses the way back.
    ("schema_pipeline_routes.py", "_run_interception_pipeline"): "stage1+stage3",
    ("schema_pipeline_routes.py", "execute_pipeline_streaming"): "stage1",  # A5: unified stage 1; path ends after stage 2
    ("schema_pipeline_routes.py", "execute_pipeline_streaming.run_pipeline"): "stage1",  # inner runner of /pipeline/stage2 (unified stage 1 at entry)
    ("schema_pipeline_routes.py", "execute_stage2_interception"): "helper",  # checks live at the calling route
    ("schema_pipeline_routes.py", "execute_stage2_classifier"): "helper",  # the kids/youth gate, called by _run_stage2
    ("schema_pipeline_routes.py", "execute_stage2_with_optimization"): "helper",  # interception + adaption, called by the routes above
    ("schema_pipeline_routes.py", "execute_optimization"): "helper",
    ("schema_pipeline_routes.py", "compare_analyze_image"): "unchecked-proxy",  # analysis, user media to GPU service
    ("schema_pipeline_routes.py", "_image_reader_backends"): "not-generating",  # asks which station serves a model
    ("schema_pipeline_routes.py", "_generator_fields"): "not-generating",  # names the generator of a finished file
    ("schema_pipeline_routes.py", "_stream_image_reading"): "unchecked-proxy",  # same reading, handed over piecewise
    # The frames of that same reading, split out when it went onto the shared
    # transport. One reading, one class.
    ("schema_pipeline_routes.py", "_stream_image_reading._reading_frames"): "unchecked-proxy",
    # /pipeline/stage2: stage 1 at entry, over BOTH texts the client sent.
    # Until 2026-08-29 it ran after the context translation and only over
    # input_text; a context_prompt in another language had been through a local
    # LLM before anything was checked. Order reversed and context_prompt added
    # to the gate (`_stage1_check_texts`); same for the streaming path and for
    # interception_pipeline, which had the identical hole.
    # /pipeline/stage2. The view function became a branch on 2026-09-04, when
    # the route gained the platform's SSE transport so that a long interception
    # survives the edge's 100-second cut; the run — and with it the model call
    # this census looks for — moved into `_run_stage2`. Same path, same checks,
    # a different function to name them under.
    ("schema_pipeline_routes.py", "_run_stage2"): "stage1",
    ("interception_prompts_routes.py", "preview_prompt"): "stage1",  # a kept perspective's dry run: stage 1 over the sample, then stage 2
    ("schema_pipeline_routes.py", "_cancel_diffusers_for"): "not-generating",  # ends a run, starts none
    ("schema_pipeline_routes.py", "_translate_context"): "not-generating",  # the edited context into English, no medium
    # `_gate_plan` used to be here: it read the GPU service's queue over HTTP, so
    # the scan found it. Since stage 7 of the move to ComfyUI it asks the gate in
    # this process (services/gpu_gate.py), and the scan no longer sees a call.
    # --- canvas surface (stage 3 before every generation since 2026-10-02,
    # canvas_executor.canvas_stage3_verdict; image lookback runs; course level d053cac0) ---
    ("canvas_routes.py", "execute_batch"): "stage3+vlm",
    ("canvas_routes.py", "execute_batch.generate"): "stage3+vlm",  # inner SSE generator of execute_batch
    ("canvas_executor.py", "_execute_generation"): "stage3+vlm",
    ("canvas_run_service.py", "_worker"): "stage3+vlm",
    # --- text/chat surface (work order §3: no checks — A6/A7 territory) ---
    # The turn itself. /api/chat drains it, /api/chat/stream forwards it, and
    # neither view function reaches a model any more — so the declaration sits
    # where the orchestration is: user text (and images) to a cloud or local
    # model, plus the post-production compose, with no content check anywhere
    # on the path.
    ("chat_routes.py", "_chat_events"): "unchecked-proxy",
    ("chat_routes.py", "call_chat_helper"): "unchecked-proxy",
    ("chat_routes.py", "call_chat_helper_stream"): "unchecked-proxy",  # same call, handed over piecewise
    ("chat_routes.py", "_call_local_llm_chat"): "unchecked-proxy",
    ("chat_routes.py", "_stream_local_llm"): "unchecked-proxy",  # same, on the station on this machine
    ("chat_routes.py", "_chain_attempts"): "unchecked-proxy",  # the fallback chain both of the above walk
    # /api/chat/proxy: the platform's own ComfyUI nodes reach a model through
    # call_chat_helper here, with the same absence of checks as the chat turn.
    ("chat_routes.py", "chat_proxy"): "unchecked-proxy",
    ("chat_routes.py", "_brought_captions"): "unchecked-proxy",  # board images to the VLM, no check
    ("chat_routes.py", "chat_vlm_models"): "not-generating",
    # list_chat_models, chat_install (and its SSE generator) and
    # chat_install_precheck stood here while they asked the GPU service over
    # HTTP; since stage 3 of the move to ComfyUI they read the table of local
    # models and run the installer in this process, and the scan sees no call.
    # The class is the truth and it is thin. `speak()` takes free-form POST
    # `text` from any client. The only gate on the way to a synthesiser is
    # `level not in chunk.ALLOWED_SAFETY_LEVELS` (speech_routes.py ~460), and
    # that branch cannot be reached from this route: all four speech chunks
    # allow all five levels, and resolve_safety_level never returns an unknown
    # one — every failure path in it yields the STRICTEST level. So nothing
    # here checks the text, and nothing here enforces that it came from a
    # checked path; the level is resolved and that is all.
    ("speech_routes.py", "_speak"): "course-level-only",
    ("speech_routes.py", "_translate_to_english"): "helper",
    # --- direct proxies past all five surfaces (work order §4, closed by A6/A7) ---
    # Stage 6 of the move to ComfyUI (2026-09-14): the Crossmodal Lab's three
    # runs (synthesis, image-guided audio, MMAudio) are one-node prompts of
    # the platform's package, queued by _run_node; the sound comes back the
    # way a picture does. The prompt goes to the node as it was typed, past
    # stage 2, as it went to the GPU service's station before.
    ("cross_aesthetic_routes.py", "_run_node"): "unchecked-proxy",
    # The Fusion Workbench and the research scripts of the embedding series:
    # the operand goes to ComfyUI as it was typed, past stage 2 by design.
    ("fusion_workbench_routes.py", "_run"): "unchecked-proxy",
    ("fusion_workbench_routes.py", "_run.one_run"): "unchecked-proxy",
    # /api/text/* — the Latent Text Lab's own surface. Every one of these hands
    # the GPU service something a client posted, and none of them checks it:
    # the work order files them under "on the way in through the input fields",
    # which is the frontend's safety-quick call on MediaInputBox and holds only
    # for a client that uses the page. Declared like compare_analyze_image, the
    # same shape on the image side. Four of them also GENERATE text.
    ("text_routes.py", "tokenize_text"): "unchecked-proxy",
    # Same move as the three image readings below, on 2026-09-09 and for the
    # same reason: the shared SSE transport took over /api/text/rep-engineering,
    # /bias-probe and /bbq-probe, so the work runs on a worker thread in
    # `_run_*` and the view function above it only decides how the answer
    # travels back. The class is unchanged; only the site that carries it moved.
    ("text_routes.py", "_run_rep_engineering"): "unchecked-proxy",  # generates
    # The rest of that surface carries no client text at all: the service's own
    # state, or an id and a count into a fixed research corpus.
    # Not a helper: a helper is a step of a checked route, and every route that
    # calls this one is declared unchecked-proxy above. It is a client factory —
    # it builds the connection and never touches the text.
    ("text_routes.py", "_get_client"): "not-generating",
    ("text_routes.py", "encoder_rows"): "not-generating",  # lists the encoders a station serves
    ("text_routes.py", "list_tokenizers"): "not-generating",
    ("text_routes.py", "_run_bias_probe"): "not-generating",  # item ids into the corpus
    ("text_routes.py", "bias_corpus"): "not-generating",
    ("text_routes.py", "_run_bbq_probe"): "not-generating",   # ids, a category, a count
    ("text_routes.py", "bbq_overview"): "not-generating",
    ("text_routes.py", "bbq_sample"): "not-generating",
    # A user's uploaded picture, read by a VLM. Invisible to this census until
    # 2026-09-03 because it names none of the markers: the call is
    # `llm_service.analyze_image`.
    # The three moved out of their view functions on 2026-09-04, when the shared
    # SSE transport took over these routes: the reading is what runs on the
    # worker thread, and the view above it now only decides how the answer
    # travels back.
    ("media_routes.py", "_run_analyze_image"): "unchecked-proxy",
    ("media_routes.py", "_run_analyze_av"): "unchecked-proxy",
    ("media_routes.py", "_run_analyze_compare"): "unchecked-proxy",
    # --- workflow passthrough (course level since A4/d053cac0, no content check) ---
    # --- infrastructure, no user content generated ---
    # `hardware_routes._detect_gpu` used to be here: it called the GPU service
    # over HTTP, so the scan found it. Since 07.09.2026 it asks `gpu_card`,
    # which reaches ComfyUI on its own, and the scan no longer sees a call.
    ("settings_routes.py", "workshop_preload.generate"): "not-generating",  # workshop preload SSE
    # `get_backend_status._check_gpu_health` and `gpu_vram_status` used to be
    # here: they read the GPU service's health over HTTP. Since stage 7 they read
    # the gate in this process, and the scan no longer sees a call.
    ("settings_routes.py", "_ensure_dummy_image_uploaded"): "not-generating",
    ("settings_routes.py", "get_backend_status"): "not-generating",
    ("settings_routes.py", "workshop_preload"): "not-generating",
    ("settings_routes.py", "workshop_clear_all"): "not-generating",  # frees the card
    ("training_routes.py", "clear_vram"): "not-generating",
    ("training_routes.py", "check_vram"): "not-generating",
    # --- the view functions that hand their run to `answered_either_way` ---
    # Since 2026-09-04 a run that may outlive the tunnel's 100 seconds is
    # answered either as one JSON body or as a stream, and the view function
    # hands the run to that transport. The class is the run's own: the view
    # function adds no check and takes none away. Each row names what is handed.
    ("commons_routes.py", "lookup"): "vlm",  # _run_lookup: the prompt to the term model unchecked; the found pictures through the image check at kids/youth
    ("cross_aesthetic_routes.py", "_streamed_post"): "unchecked-proxy",  # _synth_post, _guided_post, _mmaudio_post -> _run_node
    ("fusion_workbench_routes.py", "generate"): "unchecked-proxy",  # _run
    ("fusion_workbench_routes.py", "_research_run"): "course-level-only",  # _run, behind the research level alone (docstring there)
    ("mean_images_routes.py", "overlay"): "vlm",  # _run_overlay: the decoded mean, a picture nobody checked, through the image check at kids/youth (_refused)
    ("mean_images_routes.py", "variants"): "unchecked-proxy",  # _run_variants
    ("media_routes.py", "analyze_av_file"): "unchecked-proxy",  # _run_analyze_av
    ("media_routes.py", "analyze_image_file"): "unchecked-proxy",  # _run_analyze_image
    ("media_routes.py", "analyze_media_compare"): "unchecked-proxy",  # _run_analyze_compare
    ("schema_pipeline_routes.py", "direct_workflow"): "stage1+stage3+vlm",  # _run_direct_workflow
    ("schema_pipeline_routes.py", "execute_stage2"): "stage1",  # _run_stage2
    ("schema_pipeline_routes.py", "interception_pipeline"): "stage1+stage3",  # _run_interception_pipeline
    ("schema_pipeline_routes.py", "optimize_prompt"): "unchecked-proxy",  # _run_optimize_prompt: the adaption, neither stage 1 nor stage 3 (see _translate_encoder_text)
    ("schema_pipeline_routes.py", "translate_text"): "unchecked-proxy",  # _run_translate -> translate_one
    ("text_routes.py", "bbq_probe"): "not-generating",  # _run_bbq_probe
    ("text_routes.py", "bias_probe"): "not-generating",  # _run_bias_probe
    ("text_routes.py", "rep_engineering"): "unchecked-proxy",  # _run_rep_engineering
    # --- translation/interpretation text tools (user text to LLM, no checks) ---
    # THE platform's single-text translation. It stood inside the view function
    # `translate_text` until 2026-09-03 and was lifted out of it so that Mean
    # Images could translate without going through HTTP; the call, the text and
    # the absence of a check moved with it, and the view function itself now
    # carries no marker.
    ("schema_pipeline_routes.py", "translate_one"): "unchecked-proxy",
    ("schema_pipeline_routes.py", "_translate_list"): "unchecked-proxy",  # its inner call; same texts, same absence of a check
    # Mean Images asks for the English text and for variants of it. Both are
    # TEXT: what the instrument then generates from them goes over
    # /pipeline/direct, which runs stage 1 and, at kids/youth, stage 3 and the
    # image lookback. Client text nevertheless reaches a model here with no
    # check of its own, and the class says so.
    # The route was split on 2026-09-04 so that one run can be answered either as
    # a JSON body or as a stream that outlives the tunnel's 100 seconds. The model
    # call moved into `_run_variants` with it, and the view function itself now
    # carries no marker.
    ("mean_images_routes.py", "_run_variants"): "unchecked-proxy",
    # Translates one text to English through `pre_output/translation_en`. Two of
    # its three callers sit after stage 3 (execute_generation_streaming,
    # execute_generation_stage4) — but the third does not: _fit_encoder_window
    # is called by `_run_optimize_prompt`, the run behind POST /pipeline/optimize
    # (the view function `optimize_prompt` has been the branch between a stream
    # and one JSON body since 2026-09-04, and the helper carried the older name
    # _fit_prompt_to_window when this note was written),
    # which runs neither stage 1 nor stage 3. Client text therefore reaches a
    # model here with no check at all, and the class says so; the two checked
    # callers do not make the path checked.
    ("schema_pipeline_routes.py", "_translate_encoder_text"): "unchecked-proxy",
    ("media_routes.py", "_translate_analysis"): "not-generating",  # translates system-produced analysis text
    # --- subprocess surface (work order §4: Unterprozesse; no content check) ---
    ("media_routes.py", "compose_media"): "subprocess",  # ffmpeg composes already-checked run artifacts
    ("post_production_service.py", "compose"): "subprocess",
    ("post_production_service.py", "_build_still_plus_audio"): "subprocess",
    ("post_production_service.py", "_build_video_plus_audio"): "subprocess",
    ("post_production_service.py", "_probe_duration"): "not-generating",
    ("post_production_service.py", "_require_ffmpeg"): "not-generating",
    ("post_production_service.py", "<module>"): "not-generating",
    ("blender_service.py", "_render_sync"): "subprocess",  # converts checked 3D runs to preview renders
    ("blender_service.py", "is_available"): "not-generating",
    ("training_service.py", "start_training_process"): "subprocess",  # LoRA training
    ("training_service.py", "start_training_process.run_proc"): "subprocess",
    ("training_service.py", "_request_description"): "unchecked-proxy",  # user training images to the VLM, no check
    ("training_service.py", "_cleanup_caption"): "unchecked-proxy",
    ("training_service.py", "stop_training"): "not-generating",  # signals the run's process group
    ("training_service.py", "clear_vram_thoroughly"): "not-generating",  # frees the card before a training run
    ("training_service.py", "__init__"): "not-generating",
    ("training_service.py", "_get_vram_status"): "not-generating",
    ("training_service.py", "get_gpu_vram"): "not-generating",
    ("dev_routes.py", "research_sweep_launch"): "subprocess",  # research image sweeps with user prompts
    ("knowledge_routes.py", "_reindex_sync"): "not-generating",  # docling reindex
    ("settings_routes.py", "detect_gpu_vram"): "not-generating",
    ("settings_routes.py", "get_gpu_realtime"): "not-generating",
}

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
    # own clients on the GPU service (work order §4: one each)
    "output_audio_stableaudio_diffusers.py": "gpu-service",
    "output_3d_hunyuan3d.py": "gpu-service",
    "output_music_heartmula.py": "gpu-service",
    # subprocess surface: speaks by asking a worker of its own, in its own
    # environment, over localhost. Nothing of it runs in this process.
    "output_speech_voxcpm.py": "subprocess",
    # The espeak-ng binary, run per utterance (services/espeak_backend.py:218).
    # No model and no service: rules turn letters into phonemes.
    "output_speech_espeak.py": "subprocess",
    # The `piper` binary of its own environment, run per utterance on the CPU
    # (services/piper_backend.py); back since 2026-09-18 as the fourth machine
    # of the voices comparison.
    "output_speech_piper.py": "subprocess",
    # A SIXTH surface, and the work order's §4 table does not name it: the
    # platform's own voice runs ONNX Runtime on the CPU INSIDE the DevServer
    # process (services/supertonic_backend.py) — no GPU service, no subprocess,
    # no HTTP. Declared for what it is rather than filed under a neighbour.
    "output_speech_supertonic.py": "in-process",
    # ComfyUI surface
    "output_audio_acenet.json": "comfyui",
    # Arrived with CommonCanvas XL C and went undeclared; the chunk says
    # `backend_type: comfyui` itself.
    "output_image_commoncanvas_xl_c.json": "comfyui",
    "output_image_flux2.json": "comfyui",
    "output_image_flux2_img2img.json": "comfyui",
    "output_image_flux3.json": "comfyui",
    "output_image_qwen.json": "comfyui",
    "output_image_qwen_2511_multi.json": "comfyui",
    "output_image_qwen_img2img.json": "comfyui",
    "output_image_sd15.json": "comfyui",
    "output_image_sd35_img2img.json": "comfyui",
    "output_image_sd35_large.json": "comfyui",
    "output_image_sd35_turbo.json": "comfyui",
    "output_image_commoncanvas_xl_c.json": "comfyui",
    "output_image_sdxl.json": "comfyui",
    "output_vector_fusion_clip_sd35.json": "comfyui",
    "output_video_ltx.json": "comfyui",
    "output_video_wan22.json": "comfyui",
    "output_video_wan22_i2v.json": "comfyui",
    "output_video_wan22_t2v_fast.json": "comfyui",
    # cloud surface (work order decision 3 pending)
    "output_image_gemini_3_pro.json": "cloud-api",
    "output_image_gemini_nano_banana_2_1.json": "cloud-api",
    "output_image_gpt_image_1.json": "cloud-api",
    # passthrough: the "generation" is the stage-2 output itself (code path)
    "output_code_p5js.json": "passthrough",
    "output_code_tonejs.json": "passthrough",
    # live output chunks without the output_ name prefix (loader needs none)
    "dual_encoder_fusion_image.json": "comfyui",
    "legacy_surrealization.json": "comfyui",
}


def iter_scan_files():
    files = sorted(p for p in ROUTES_DIR.glob("*.py") if p.name != "__init__.py")
    files += [p for p in EXTRA_SCAN_FILES if p.exists()]
    return files


def walk_functions(tree):
    """(name, node) for every function, nested ones under their enclosing one.

    `generate` appears twice in chat_routes.py — the SSE generator of
    chat_install and the one inside chat_stream — and keyed by the bare name
    they were one entry in the map. A marker appearing in the second would then
    have been absorbed by the declaration written for the first, which is the
    one thing this census exists to prevent. Nested functions are therefore
    `outer.inner`; methods keep their bare name, because a class body is not a
    scope anybody confuses.
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


def scan_generation_sites():
    """Return {(file, function): sorted marker names} for all hits."""
    sites = {}
    for path in iter_scan_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for name, node in walk_functions(tree):
            segment = ast.get_source_segment(source, node) or ""
            hit = sorted(marker for marker, rx in GENERATION_MARKERS.items()
                         if rx.search(segment))
            if hit:
                sites[(path.name, name)] = hit
        # module level (outside any def)
        in_function_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                in_function_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        module_lines = [
            line for i, line in enumerate(source.splitlines(), 1) if i not in in_function_lines
        ]
        module_src = "\n".join(module_lines)
        hit = sorted(name for name, rx in GENERATION_MARKERS.items() if rx.search(module_src))
        if hit:
            sites[(path.name, "<module>")] = hit
    return sites


def scan_output_chunks():
    """Output chunks by what they ARE, not what they are named: .json chunks
    census by their type field (the loader requires no name prefix — four
    live output chunks carry legacy_*/dual_* names), .py chunks by the
    output_ naming convention the router uses."""
    import json
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


def test_every_generation_site_is_declared():
    undeclared = {site: m for site, m in scan_generation_sites().items() if site not in ROUTE_MAP}
    assert not undeclared, (
        "Generation sites without a declared check class (work order A11).\n"
        "Read docs/WORK_ORDER_CONTENT_CHECKING.md, then declare each in ROUTE_MAP:\n"
        + "\n".join(f'    ("{f}", "{fn}"): "<check-class>",   # markers: {m}'
                    for (f, fn), m in sorted(undeclared.items()))
    )


def test_no_stale_route_declarations():
    found = scan_generation_sites()
    stale = [site for site in ROUTE_MAP if site not in found]
    assert not stale, (
        "ROUTE_MAP declares sites the scan no longer finds — remove them so the "
        f"map stays honest: {sorted(stale)}"
    )


def test_every_output_chunk_is_declared():
    undeclared = [c for c in scan_output_chunks() if c not in CHUNK_MAP]
    assert not undeclared, (
        "Output chunks without a declared surface (work order A11 / §4 table).\n"
        "Declare each in CHUNK_MAP as one of: diffusers, comfyui, cloud-api, "
        "gpu-service, subprocess, dead:\n"
        + "\n".join(f'    "{c}": "<surface>",' for c in undeclared)
    )


def test_no_stale_chunk_declarations():
    found = set(scan_output_chunks())
    stale = [c for c in CHUNK_MAP if c not in found]
    assert not stale, f"CHUNK_MAP declares chunks that no longer exist: {sorted(stale)}"


def test_declared_diffusers_chunks_match_code():
    """A .py chunk declared 'diffusers' must actually route through the
    diffusers backend accessor — and one declared otherwise must not."""
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
    import json
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
            f"{name} carries backend={backend!r} which this test does not know — "
            "a NEW surface: extend backend_to_surface AND the work order §4 table"
        )
        assert surface == expected, (
            f"{name} declared {surface} but its backend field says {backend} ({expected})"
        )


if __name__ == "__main__":
    if "--report" in sys.argv:
        print("# --- generation sites found ---")
        for (f, fn), m in sorted(scan_generation_sites().items()):
            print(f'    ("{f}", "{fn}"): "",   # markers: {",".join(m)}')
        print("# --- output chunks found ---")
        for c in scan_output_chunks():
            print(f'    "{c}": "",')
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
