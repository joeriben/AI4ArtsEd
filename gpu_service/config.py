"""
GPU Service Configuration

Shared GPU inference service for media generation (Diffusers, HeartMuLa, StableAudio)
and local LLM/VLM inference (supervised llama-server children).
Runs as a standalone Flask/Waitress process on port 17803.
Both dev (17802) and prod (17801) backends call this via HTTP REST.
"""

import os
from pathlib import Path

# --- Server ---
HOST = "127.0.0.1"  # Localhost only — NEVER expose to network
PORT = int(os.environ.get("GPU_SERVICE_PORT", "17803"))
THREADS = 64  # Waiting for the GPU slot parks a thread; the safety checks and the
              # lease heartbeats must still get one. A workshop group presses
              # generate in the same minute, so the queue can be a dozen deep and
              # the pool has to be wider than the queue. Threads are cheap, the
              # card is not.

# --- Generation ---
# A generous CEILING, not a tuning cap: a generation stops when the model emits
# its end token, long before this. It exists so a run that never emits one has
# an end at all. Anything smaller silently cuts a sentence in half, which is how
# the Text Lab spent its first months showing answers that broke off mid-word.
GENERATION_TOKEN_CEILING = 65536

# --- AI Tools Base ---
_SERVER_BASE = Path(__file__).parent.parent  # gpu_service/.. = repo root
_AI_TOOLS_BASE = Path(os.environ.get("AI_TOOLS_BASE", str(_SERVER_BASE)))  # default: nested under repo (same convention as dlbackend/ComfyUI); override only for external partitions

# --- Diffusers ---
DIFFUSERS_ENABLED = os.environ.get("DIFFUSERS_ENABLED", "true").lower() == "true"
_diffusers_cache_env = os.environ.get("DIFFUSERS_CACHE_DIR", "")
DIFFUSERS_CACHE_DIR = Path(_diffusers_cache_env) if _diffusers_cache_env else None
DIFFUSERS_USE_TENSORRT = os.environ.get("DIFFUSERS_USE_TENSORRT", "false").lower() == "true"
DIFFUSERS_TORCH_DTYPE = os.environ.get("DIFFUSERS_TORCH_DTYPE", "float16")
DIFFUSERS_DEVICE = os.environ.get("DIFFUSERS_DEVICE", "cuda")
DIFFUSERS_ENABLE_ATTENTION_SLICING = os.environ.get("DIFFUSERS_ENABLE_ATTENTION_SLICING", "true").lower() == "true"
DIFFUSERS_ENABLE_VAE_TILING = os.environ.get("DIFFUSERS_ENABLE_VAE_TILING", "false").lower() == "true"
DIFFUSERS_VRAM_RESERVE_MB = int(os.environ.get("DIFFUSERS_VRAM_RESERVE_MB", "3072"))
LORA_DIR = Path(os.environ.get("LORA_DIR", str(_SERVER_BASE / "dlbackend" / "ComfyUI" / "models" / "loras")))
DIFFUSERS_FLUX2_QUANTIZE = os.environ.get("DIFFUSERS_FLUX2_QUANTIZE", "fp8")  # bf16 or fp8
DIFFUSERS_WAN22_QUANTIZE = os.environ.get("DIFFUSERS_WAN22_QUANTIZE", "bf16")  # bf16 or fp8
# The model a Diffusers request runs on when its body names none. The routes
# and the backend read it from here; until 2026-10-10 the same id stood in the
# routes nine times and in the backend eleven times (finding S-026 of the code review of 2026-10-10).
DEFAULT_MODEL_ID = "stabilityai/stable-diffusion-3.5-large"

# Peak VRAM (MB) during inference — measured 2026-03-18 on RTX PRO 6000
# Blackwell 96GB via nvidia-smi peak monitoring. CPU-offloaded models report ~0 via
# torch.cuda.memory_allocated(), so these static values are used by the coordinator.
MODEL_PEAK_VRAM_MB = {
    # heartmula loads lazily: the real peak lands in the forward pass, not at
    # load time. Estimate — 16 GB is the chunk's declared reserve, measured
    # 11.1 GB at 30s/cfg1.0. Worth re-measuring on a long, high-cfg run.
    "heartmula": 16_000,
    "sd35_large_fp16": 30_000,    # measured: 30253 MiB
    "sd35_large_bf16": 30_000,
    "sd35_medium_fp16": 15_000,   # estimated: 2.5B-param MMDiT, ~11-13GB base + Latent Lab hooks
    "sd35_medium_bf16": 15_000,
    # This entry is Denoising Archaeology's, and it is the expensive case: the
    # VAE is upcast to float32 for every captured step. It stopped being the
    # only diffusers user of the SDXL pipeline class when CommonCanvas arrived,
    # which is why that one has its own entry below rather than sharing this.
    "sdxl_fp16": 25_000,          # measured: 25198 MiB (25 steps, 1024x1024, every step captured)
    "sdxl_bf16": 25_000,
    # CommonCanvas XL C loads under the same pipeline class as SDXL and does not
    # cost the same: it is a plain generation, with no step capture and no VAE
    # upcast. Sharing the entry above would have evicted models it does not
    # displace, and on a 24 GB card it crosses the total and forces CPU offload
    # on weights that fit three times over.
    "commoncanvas_fp16": 12_000,  # measured: 11406 MiB (cold load + 30 steps, 1024x1024)
    "commoncanvas_bf16": 12_000,
    "flux2_bf16": 55_000,         # measured via ComfyUI: 54712 MiB peak
    "flux2_fp8": 33_000,          # measured via Diffusers FP8: 32055 MiB (gen failed, min peak)
    "wan22_t2v_bf16": 39_000,     # measured via ComfyUI: 39290 MiB peak
    "wan22_t2v_fp8": 20_000,
    "wan22_t2v_moe_bf16": 39_000, # measured via ComfyUI (A14B MoE): 39290 MiB peak
    "wan22_t2v_moe_fp8": 22_000,
    "wan22_i2v_bf16": 39_000,     # estimated same arch as T2V
    "wan22_i2v_fp8": 20_000,
    "wan22_i2v_moe_bf16": 39_000,
    "wan22_i2v_moe_fp8": 24_000,
}


# --- Stable Audio (SA3 via stable-audio-tools; was SA Open 1.0 / diffusers) ---
# Model selection is VRAM-tiered and lives in services/stable_audio_model.py (the single
# source of truth): medium on >=50 GB cards, small-music below; SFX is always small-sfx.
# Override per machine with env AI4ARTSED_STABLE_AUDIO_MODEL=medium|small. No model-id
# constant here on purpose — config.py is not the model source of truth.
STABLE_AUDIO_DEVICE = os.environ.get("STABLE_AUDIO_DEVICE", "cuda")
# float32 = correctness-first for the rectified-flow sampler. Half-precision tuning = Task #4.
STABLE_AUDIO_DTYPE = os.environ.get("STABLE_AUDIO_DTYPE", "float32")
STABLE_AUDIO_LAZY_LOAD = os.environ.get("STABLE_AUDIO_LAZY_LOAD", "true").lower() == "true"
# UX/safety cap for the t2a path (stable_audio_backend.max_duration). SA3 medium's native max is
# ~380s (sample_size 16777216 / 44100). 240s because the re-enactment page gives back a sound as
# long as the recording, and its own frame reaches 240s (parrot_service.SONG_MAX_MS), so a lower
# ceiling here silently broke that promise — the backend clamps without saying so. 120s was the
# earlier practical ceiling, chosen for workshop GPU turnaround. The Latent Synth keeps its own
# shorter cap (cross_aesthetic_backend, 47s).
STABLE_AUDIO_MAX_DURATION = 240.0  # seconds
STABLE_AUDIO_SAMPLE_RATE = 44100

# --- Crossmodal Lab ---

# ImageBind (gradient guidance)
IMAGEBIND_MODEL_ID = os.environ.get("IMAGEBIND_MODEL_ID", "facebook/imagebind-huge")

# MMAudio (CVPR 2025 Video-to-Audio)
MMAUDIO_MODEL = os.environ.get("MMAUDIO_MODEL", "large_44k_v2")
MMAUDIO_REPO = os.environ.get("MMAUDIO_REPO", str(_AI_TOOLS_BASE / "MMAudio"))

# --- LLM/VLM engine (safety chain, DSGVO check, image readings) ---
# Which engine serves /api/llm/*:
#   "child"     one supervised llama-server process per alias, owned by this
#               service (services/llm_child.py, services/llm_child_backend.py)
#   "inprocess" the older llama-cpp-python engine in services/llm_backend.py
# Exactly one of the two is ever constructed; see llm_child_backend.get_llm_backend().
LLM_ENGINE = os.environ.get("LLM_ENGINE", "child").strip().lower()

# The llama-server binary, built from the pinned llama.cpp clone. Follows the
# AI_TOOLS_BASE convention of every other external tool here: repo-nested by
# default (the clone itself is gitignored), overridable for external partitions.
LLAMA_SERVER_BIN = os.environ.get(
    "LLAMA_SERVER_BIN",
    str(_AI_TOOLS_BASE / "llama.cpp" / "build" / "bin" / "llama-server"),
)

# Derived from this service's own port, so two GPU services on one box start
# from different offsets: 17810-17849 for the default 17803. Ranges that do
# overlap are not a problem — a port is bind-probed before a child is given it,
# and a child that loses the race to another process between the probe and its
# own bind is started once more on the next port.
LLM_CHILD_PORT_BASE = PORT + 7
LLM_CHILD_PORT_COUNT = 40

# A liveness bound on the SUPERVISOR, not a budget for a model call. A child
# that for this long writes nothing, reads nothing through a read() call and
# does not move its own per-PID NVML figure, while /health still refuses, has
# stopped loading. All three signals are there because none of them covers the
# whole load on its own, and the order of their usefulness is not obvious:
#   * the BYTES THE CHILD WRITES carry the copy phase — llama.cpp prints its
#     load bar as dots with no newline, so this moves while a LINE counter
#     stands perfectly still. Do not reduce it to counting lines.
#   * its NVML FIGURE moves as the buffers are allocated.
#   * /proc/<pid>/io rchar is the weakest: it counts read() calls, and a
#     memory-mapped load — the default — brings the weights in through page
#     faults, so it stops moving after the header. It earns its place for a
#     load with mmap turned off, where it is the only one that moves at all.
#
# The same bound is applied a second time, to a GENERATION that has stopped
# moving: a child holding a request that for this long sends no frame, writes no
# line and moves no GPU memory is ended, and the request fails with what was
# reached. It is NOT a read timeout and must not be turned into one — a long
# answer is an ordinary event, and any deadline on the answer itself would cut
# good readings in half. What is bounded is progress, in both places.
LLM_CHILD_STALL_S = 180.0

# The wall clock of ONE load attempt, whatever progress it shows. The stall
# bound above cannot end a child that writes a line every second and never
# becomes healthy, and such a child holds the plant-wide load lock — with it,
# every content check on the platform. Fifteen minutes is far beyond the
# slowest cold load measured here and far below "forever".
LLM_CHILD_LOAD_CEILING_S = 900.0

# The load-time vision warm-up, bounded the same way: no frame, no work line and
# no movement in the child's own slots for this long while it encodes ONE image,
# and the child is ended and the load refused. Also progress, not a deadline on
# the answer — but a much shorter one than the 180 s above, and it can be:
# encoding at the token cap was measured at 2.2-3.5 s on this card, and this
# particular wait blocks the plant-wide load lock, so every content check on the
# platform stands behind it.
LLM_CHILD_WARMUP_STALL_S = 60.0

# The child's own socket read/write timeout (-to), 600 s by default. A reading
# that runs for an hour is an ordinary event here, and cpp-httplib does not read
# 0 as "no timeout" — so the ceiling is set far above any reading (30 days)
# instead of being disabled.
LLM_CHILD_SOCKET_TIMEOUT_S = 2592000


# Where llm_children.json lives. The file records the PIDs and ports of this
# machine and is rewritten on every child registry change, so it belongs outside
# the working tree — one inside a checkout would sit one `git add` away from a
# repository. The value is CHECKED where it is used (services/llm_child.py,
# resolve_state_dir): a bad path must cost the LLM engine and leave image
# generation, the safety chain and the health endpoint running, which a raise at
# `from config import ...` would not.
LLM_CHILD_STATE_DIR = (
    os.environ.get("LLM_CHILD_STATE_DIR", "").strip()
    or str(Path.home() / ".cache" / "ai4artsed" / f"gpu-service-{PORT}")
)

# --- VRAM Watchdog ---
VRAM_USE_NVML = os.environ.get("VRAM_USE_NVML", "true").lower() == "true"
VRAM_FOREIGN_OVERHEAD_MB = int(os.environ.get("VRAM_FOREIGN_OVERHEAD_MB", "2048"))  # CUDA context + driver overhead
VRAM_BLACKLISTED_PORTS = [7801, 7821, 8188]  # SwarmUI ports — NEVER tolerated
# Where ComfyUI keeps its weights. The gate's model_id for a ComfyUI lease is
# the path BELOW models/checkpoints ("OfficialStableDiffusion/sd15.safetensors"),
# so this plus that id is a real file - which is what lets the page-cache
# warming resolve them at all.
COMFYUI_MODELS_DIR = Path(os.environ.get(
    "COMFYUI_MODELS_DIR",
    str(Path(__file__).resolve().parent.parent / "dlbackend" / "ComfyUI" / "models")))

# Read the next queued model off the disk while the card works on the current
# one. Costs no VRAM - it fills the kernel's page cache and nothing else.
#
# DEFAULTS TO FALSE, and the reasons are measurements, not caution. Two
# independent checks on 2026-08-26, both against the running platform:
#
#   * The saving is small. mmap page faults reach the disk at 2832 MiB/s in
#     the real load order, sequential reading at 2645 MiB/s - a factor of ONE,
#     not the fifteen a MADV_RANDOM measurement had suggested. Of the 111 s
#     cold penalty on wan2.2, the disk accounts for 12.4 s; the rest is model
#     initialisation, fp8 handling and the transfer to the card.
#   * The cost is not small, and it lands at the worst moment. The advice
#     fires within 5 s of a run being admitted - i.e. during that run's own
#     loading phase - and a concurrent sequential read drops its fault-driven
#     load from 3324 to 660 MiB/s. Factor 5.03, on the line the waiting person
#     depends on.
#   * The occasion barely arises: over 607 runs in 9 days, 5 were both
#     resolvable and long enough to be worth warming.
#
# The lever that actually turns wan2.2's 132.1 s into 21.0 s is already there:
# keeping the model resident by affinity ordering in the admission gate.
GPU_PAGE_CACHE_WARM = os.environ.get("GPU_PAGE_CACHE_WARM", "false").strip().lower() \
    in ("true", "1", "yes")

COMFYUI_PORT = int(os.environ.get("COMFYUI_PORT", "17804"))  # Expected ComfyUI
COMFYUI_SYSTEMD_UNIT = os.environ.get("COMFYUI_SYSTEMD_UNIT", "ai4artsed-comfyui.service")  # emergency reclaim when the VRAM sensor goes blind

# --- GPU admission (plant-wide serialization of heavy operations) ---
# One heavy operation on the card at a time, across processes: the backends here
# take the slot directly, the DevServer holds a lease for each ComfyUI run. See
# services/gpu_admission.py. All overridable by environment.
# The hard ceiling on one wait — a backstop against a wedged plant, NOT a
# patience budget. Whoever waits keeps their place; a wait that ends in a refusal
# would send them to the back of the line on the next press, while everybody who
# arrived later moves up past them. So this sits far above any real queue, and
# above GPU_ADMISSION_MAX_HOLD_S below, which releases a wedged holder long
# before any waiter reaches this.
GPU_ADMISSION_ACQUIRE_TIMEOUT_S = float(os.environ.get("GPU_ADMISSION_ACQUIRE_TIMEOUT_S", "5400"))
# Starting assumption for how long one heavy run takes, until the gate has
# measured a few. Replaced by a moving average of real holds, and REPORTED only:
# nobody is turned away on an estimate.
GPU_ADMISSION_ASSUMED_RUN_S = float(os.environ.get("GPU_ADMISSION_ASSUMED_RUN_S", "90"))
# Generously above the worst queueing delay a heartbeat can suffer in the thread
# pool: a lease reaped while its generation is still running means two processes
# allocate at once, which is the failure this whole gate exists to prevent.
GPU_ADMISSION_HEARTBEAT_TIMEOUT_S = float(os.environ.get("GPU_ADMISSION_HEARTBEAT_TIMEOUT_S", "120"))
GPU_ADMISSION_REAPER_INTERVAL_S = float(os.environ.get("GPU_ADMISSION_REAPER_INTERVAL_S", "5"))
# A waiting request parks a worker thread, so there has to be an end somewhere —
# but this is a limit of THREADS above, not a group size, and it is set high
# enough that an ordinary course never meets it. Turning somebody away costs them
# their place in the line, so this is a last resort against a
# silted-up pool, not a policy about how many may take part.
GPU_ADMISSION_MAX_WAITERS = int(os.environ.get("GPU_ADMISSION_MAX_WAITERS", "40"))
# A local operation cannot heartbeat; this is how long it may hold the slot
# before the gate stops believing it is alive.
GPU_ADMISSION_MAX_HOLD_S = float(os.environ.get("GPU_ADMISSION_MAX_HOLD_S", "2400"))
# How many consecutive unanswered sensor readings count as a lost sensor.
GPU_ADMISSION_BLIND_SAMPLES = int(os.environ.get("GPU_ADMISSION_BLIND_SAMPLES", "3"))

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
# How long before a blind gate may force a known state again. Without a cooldown
# the choice is between restarting ComfyUI on every generation and never trying
# again after the first attempt — the first thrashes, the second leaves the plant
# refusing every heavy operation until somebody restarts it by hand.
GPU_ADMISSION_RECLAIM_COOLDOWN_S = float(os.environ.get("GPU_ADMISSION_RECLAIM_COOLDOWN_S", "600"))


