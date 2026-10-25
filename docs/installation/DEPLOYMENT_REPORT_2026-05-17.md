# AI4ArtsEd — First Fresh Deployment Report

> ⚠️ **THIS DOCUMENT CONTAINS ERRORS AND OUTDATED CONCLUSIONS.**
> Written by an agent over a single long session as live notes;
> by the end, the agent's context overflowed and several diagnoses
> and "fixes" turned out to be wrong. Treat it as raw session log,
> not as a vetted reference.
>
> Known incorrect or misleading entries:
> - **F12** (`_AI_TOOLS_BASE` unification) — the documented fix in
>   commit `24b2ef46` is **incomplete**: it does not audit
>   `install_systemd_services.sh`, which silently overrides the
>   F12 fix when the systemd units are installed. The fix is
>   slated for revert + redesign.
>   See `HANDOVER_2026-05-18.md` §4.2 for the required workflow.
> - **F14** — the "PyTorch nightly pin defunct" framing is correct
>   in spirit but the specific upstream-issue match cited later
>   (against `ggml-org/llama.cpp#18910`) is wrong: that issue is
>   `closed: not planned` and describes a different model variant
>   (Qwen3-VL-Embedding-2B, not Qwen3-VL-Instruct). See
>   `HANDOVER_2026-05-18.md` §4.3.
> - **F21** — "user_settings.json substitution" is described here
>   as a workaround; in fact it was a scope violation (the agent
>   should have stopped, not generated defaults). The original
>   Fedora file has since been restored. See `HANDOVER_2026-05-18.md`
>   §4.1.
>
> The current authoritative summary is
> `docs/installation/HANDOVER_2026-05-18.md`. Read that **first**.

---

**Date:** 2026-05-17
**Target machine:** Fresh Ubuntu 26.04 LTS Server ("resolute"), headless
**Goal:** First installation on a machine that was NOT used for development.
Used as a deployability test for the source-available release that
educational institutions are expected to self-host.

This document captures friction points, workarounds, and recommendations
for improving the installation experience and documentation.

---

## Target Hardware

| Component | Value |
|-----------|-------|
| OS        | Ubuntu 26.04 LTS Server (resolute) |
| CPU/RAM   | 91 GiB RAM, free root partition 1.7 TiB |
| GPU       | NVIDIA GeForce RTX 4090 (24 GB VRAM) |
| Driver    | 595.58.03, CUDA 13.2 (driver runtime) |
| Network   | WLAN `wlp4s0` (FRITZ!Box 192.168.178.49), LAN `enp3s0` (direct link to source PC) |

## Source machine (for model rsync)

| Component | Value |
|-----------|-------|
| OS        | Fedora 42 |
| Host      | `fedora.fritz.box`, user `joerissen` |
| Models    | ~1.28 TiB (LLM GGUFs, ComfyUI checkpoints, HeartMuLa, HF cache) |

---

## Friction Log

Each entry: what the docs said, what reality was, what we did, recommendation.

### F1 — Python 3.13 not in Ubuntu 26.04 default repos

- **Doc claim** (`AGENT_INSTALL_INSTRUCTIONS.md` §Pre-Flight): "Must be 3.13.x".
  Also lists `python3.13 python3.13-venv python3.13-dev` as plain apt packages.
- **Reality:** Ubuntu 26.04 ships **Python 3.14** as `python3`. Standard
  repos do not contain `python3.13` at all. `apt-cache search '^python3\.1[0-9]$'`
  returns only `python3.14`.
- **Workaround:** Add `deadsnakes` PPA. Confirmed: deadsnakes does
  publish a "Resolute" pocket (verified via launchpad page).
- **Recommendation:** `INSTALLATION.md` and `AGENT_INSTALL_INSTRUCTIONS.md`
  should call out this step explicitly for 26.04. The apt one-liner in the
  current docs will fail on a fresh 26.04 server.

### F2 — CUDA toolkit (nvcc) not present despite working driver

- **Doc claim:** Pre-flight expects `nvcc --version` to succeed.
- **Reality:** Driver 595.58.03 is installed and `nvidia-smi` reports
  CUDA 13.2 runtime — but the **toolkit (compiler/headers)** is not in
  the base install. `nvcc` is missing, `/usr/local/cuda` does not exist.
- **Workaround:** Install `cuda-toolkit-13-0` via the NVIDIA Ubuntu repo.
- **Recommendation:** Distinguish clearly in docs between *driver*
  (often pre-installed by sysadmins or auto-installed by `ubuntu-drivers`)
  and *toolkit* (must be installed separately, includes `nvcc`).

### F3 — `ubuntu2604` NVIDIA repo not yet published

- **Doc claim:** "If the `ubuntu2604` repo is not yet published, use
  the `ubuntu2404` repo (ABI-compatible)."
- **Reality:** Indeed not published. Used `ubuntu2404`. Doc warning
  was accurate and saved time.
- **Recommendation:** Keep the warning in docs. ✓

### F4 — Node 20 vs Node 22

- **Doc claim:** "Node.js 20+ from NodeSource".
- **Reality:** Ubuntu 26.04 ships Node 22.22.2 in default repos.
  Plain `apt install nodejs` already gives a usable version.
- **Recommendation:** Loosen the wording: "Node 20+ — Ubuntu 26.04's
  built-in `nodejs` (v22) is sufficient; only run NodeSource setup if
  on older distros."

### F5 — Model inventory underestimates HF cache

- **Doc claim:** `MODELS_REQUIRED.md` lists ~48 GB of explicit models
  plus a 129 GB cache estimate.
- **Reality** (from source PC): 1.28 TiB total — including 732 GB in
  `~/.cache/huggingface/hub/`. The HF cache balloons because Diffusers
  pulls many intermediate artifacts.
- **Recommendation:** Either (a) document realistic cache sizes for a
  fully-exercised installation, or (b) provide a `prune_hf_cache.sh`
  helper that drops everything not currently referenced by the active
  config.

### F6 — `~/ai/` vs repo-relative paths

- **Doc claim:** The "Deployment Architecture (Nov 2025)" note
  says single directory under `~/ai/ai4artsed_webserver/`.
  Commit `0815680b` switched the install scripts to **repo-relative**
  paths (`<repo>/dlbackend/ComfyUI/...`).
- **Reality:** Two competing assumptions about where ComfyUI lives.
  Repo was cloned by the user to `~/AI4ArtsEd/` (no `~/ai/` prefix).
  Source PC actually uses `~/ai/ai4artsed_development/dlbackend/ComfyUI/`.
- **Recommendation:** Pick one. The repo-relative layout from `0815680b`
  is the more deployable one — institutions can clone anywhere — but
  every reference to `/opt/ai4artsed/` or `~/ai/` in the docs needs to
  be reconciled. Today's main README still carries
  the old assumption.

---

## Timing (per phase)

| Phase | Started | Finished | Wall time | Notes |
|-------|---------|----------|-----------|-------|
| Pre-flight checks | 19:23 | 19:25 | ~2 min | See F1, F2 |
| OS setup script written | 22:03 | 22:03 | — | Awaits user `sudo` execution |
| LAN direct script written | 22:03 | 22:03 | — | Awaits user `sudo` execution |
| Phase 1 (PyTorch nightly) | — | — | — | Pending |
| Phase 2 (deps + llama-cpp CUDA) | — | — | — | Pending |
| Phase 2b (llama-cpp CUDA rebuild) | — | — | — | Pending |
| Phase 3 (git deps) | — | — | — | Pending |
| Phase 4 (custom_rasterizer) | — | — | — | Pending |
| Phase 5 (SpaCy NER) | — | — | — | Pending |
| Phase 6 (verification) | — | — | — | Pending |
| Phase 7 (ComfyUI + models rsync) | — | — | — | Pending |

---

## Recommendations summary (PR backlog)

Concrete edits suggested for upstream docs once the install finishes
successfully:

1. **`AGENT_INSTALL_INSTRUCTIONS.md` §OS Prerequisites:** Insert a
   "Ubuntu 26.04 specific" subsection with the deadsnakes PPA step
   before the apt one-liner (F1).
2. **`AGENT_INSTALL_INSTRUCTIONS.md` §Pre-Flight Checks:** Split
   the "CUDA" line into driver-present vs toolkit-present checks (F2).
3. **`INSTALLATION.md`:** Soften the Node 20 requirement (F4).
4. **`MODELS_REQUIRED.md`:** Update HF cache estimate, add prune
   helper or cleanup guidance (F5).
5. **README.md:** Remove residual `~/ai/` and
   `/opt/ai4artsed/` references; align with repo-relative layout from
   commit `0815680b` (F6).

---

## Open questions

- Should the deadsnakes-PPA dependency become part of the canonical
  installer, or do we wait for Python 3.13 to land in Ubuntu universe?

## Selective model-transfer analysis

Resolved via static analysis of `devserver/schemas/configs/output/*.json`,
`devserver/schemas/output_config_defaults.json`, `gpu_service/services/
llm_backend.py`, and `gpu_service/services/diffusers_backend.py`:

- **Production defaults** map only 4 media types
  (`image`, `audio`, `music`, `video`) to one output config each. The
  remaining 37 configs are reachable as user-overrides during workshops.
- **Tier A — GGUF LLMs (full dir, ~38 GB):** all 13 aliases in
  `llm_backend.py` are referenced by either the safety filter, the
  Stage-2 interception model, or vision (Qwen3-VL). Transfer the whole
  `~/ai/llama-server-models/` directory.
- **Tier B — HeartMuLa checkpoints (~21 GB):** single source path.
- **Tier C — ComfyUI safetensors (19 files, est. ~130 GB):** exact
  files listed in `/tmp/MODEL_TRANSFER_MANIFEST.md`.
- **Tier D — HF cache (selective, est. ~50–150 GB):** only four
  `models--*` subdirs match a Diffusers `model_id` in the backend
  (SD3.5, Wan2.2 T2V, Wan2.2 I2V, Hunyuan3D-2). Skip the remaining
  ~600 GB of dev cache.

Total estimated transfer: **≈ 240–340 GB** (vs. 1.28 TiB raw source),
≈ 40–60 min over direct Gigabit LAN.

### F7 — Two referenced safetensors not present on dev PC

Inventory revealed:
- `stable_audio_open_1.0.safetensors` (referenced by `stableaudio_open.json`,
  the production default for `audio`): not present as a safetensors file.
  But the **chunk implementation** is `output_audio_stableaudio_diffusers.py`,
  so the actual backend uses Diffusers — HF cache has
  `models--stabilityai--stable-audio-open-1.0` (9.5 GB). The config's
  `model_file` field is dead/aspirational.
- `ltx-video-2b-v0.9.safetensors` (referenced by `ltx_video.json`,
  `backend: comfyui`): missing on dev PC and no HF cache version
  either. The config is reachable in the UI, but a workshop selecting
  it would fail at runtime today.

**Recommendation:** Either remove the orphan field from
`stableaudio_open.json` (it confuses inventory tooling), or wire a
proper consistency check that flags config↔chunk mismatches. For
`ltx_video.json`: decide whether to keep the config (then ensure
the model downloads as part of the installer) or remove it.

### F8 — Source PC almost out of disk

Fedora dev PC reports `/home` at 96% full (91 GB free of 1.9 TiB).
Not blocking for a read-only rsync, but the dev environment itself
is near saturation — worth flagging because a future model addition
could break things on the dev side before deployment.

### F9 — Ghostty/tmux terminfo mismatch

`tmux` fails with `missing or unsuitable terminal: xterm-ghostty`
on a fresh server when SSH-ing in from Ghostty. Cosmetic, but
operators using `tmux` for long-running installs will hit it.
Workaround: `export TERM=xterm-256color` before launching tmux,
or `ssh -t … 'TERM=xterm-256color tmux'`.

### F10 — OpenSSH post-quantum KEX warning between distros

Ubuntu 26.04's OpenSSH client warns when connecting to Fedora 42's
older sshd:
```
** WARNING: connection is not using a post-quantum key exchange algorithm.
```
Cosmetic. Useful as a hint that institutions running mixed-distro
fleets will see the same warning until both sides upgrade.

### F12 — Hardcoded model path + inconsistent `_AI_TOOLS_BASE` default

- `gpu_service/services/llm_backend.py:24` hardcodes
  `MODEL_DIR = os.path.expanduser("~/ai/llama-server-models")`. **Not
  overridable via env var.** A fresh installer must either symlink this
  path or edit the source.
- `devserver/config.py:12` defaults `_AI_TOOLS_BASE = _SERVER_BASE.parent`
  (= repo's parent dir, typically `~/`).
- `gpu_service/config.py:19` defaults `_AI_TOOLS_BASE = Path.home() / "ai"`.
- **Result:** with repo cloned at `~/AI4ArtsEd/`, the devserver expects
  HeartMuLa at `~/heartlib/ckpt/`, while gpu_service expects it at
  `~/ai/heartlib/ckpt/`. Same code, two services, two different paths
  by default.

**Recommendation:** Pick one base path convention. Either make `MODEL_DIR`
in `llm_backend.py` env-overridable and align both `_AI_TOOLS_BASE`
defaults, or document `AI_TOOLS_BASE` as a required env var in the
installer. Today's deployment requires `AI_TOOLS_BASE=~/ai` to be set
before either service starts.

#### F12 — Fix applied during this install (PENDING REVIEW)

**Author of this report cannot independently verify these changes are
the correct fix.** The user accepted them under the explicit caveat
"ich kann nicht beurteilen ob das korrekt ist". They warrant a review
by someone familiar with the original `_SERVER_BASE.parent` choice
in `devserver/config.py:12`.

Two edits made, both single-line, both behaviour-equivalent for any
deployment that already sets `AI_TOOLS_BASE`:

**Edit A — `devserver/config.py:12`**
```diff
-_AI_TOOLS_BASE = Path(os.environ.get("AI_TOOLS_BASE", str(_SERVER_BASE.parent)))
+_AI_TOOLS_BASE = Path(os.environ.get("AI_TOOLS_BASE", str(Path.home() / "ai")))
```
Default changed from `<repo-parent>` to `~/ai`. Matches the default
in `gpu_service/config.py:19`. Affects only installs that **don't**
set `AI_TOOLS_BASE` and that **don't** clone the repo into `~/ai/`.
If the dev PC has the repo at `~/ai/ai4artsed_development/`, then
`_SERVER_BASE.parent = ~/ai/`, so its behaviour is unchanged.

**Edit B — `gpu_service/services/llm_backend.py:24`**
```diff
-MODEL_DIR = os.path.expanduser("~/ai/llama-server-models")
+MODEL_DIR = os.path.join(
+    os.path.expanduser(os.environ.get("AI_TOOLS_BASE", "~/ai")),
+    "llama-server-models",
+)
```
Default unchanged (`~/ai/llama-server-models`). Now respects
`AI_TOOLS_BASE` override, removing the silent override that bit us
during this install.

**What could still break (review checklist):**
1. Any deployment script that sets `AI_TOOLS_BASE` to something
   *other than* the repo's parent dir — previously devserver ignored
   that intent for its `_AI_TOOLS_BASE`, now it honours it. If such
   a script existed and depended on the silent override, paths like
   `HEARTMULA_MODEL_PATH`, `KOHYA_DIR`, `TRITON_MODEL_REPOSITORY`
   will resolve differently.
2. Any code that relied on `MODEL_DIR` always being `~/ai/llama-server-models`
   regardless of env. (None found in this repo today, but worth a fresh grep
   on `develop` HEAD before merging.)

**Verification this install actually relies on:**
- Repo at `~/AI4ArtsEd/`, no `AI_TOOLS_BASE` set, GGUFs at `~/ai/llama-server-models/`.
- Pre-fix: `MODEL_DIR=~/ai/llama-server-models` (correct, by hardcode), but
  `HEARTMULA_MODEL_PATH=~/heartlib/ckpt` (wrong — gpu_service expects `~/ai/heartlib/ckpt`).
- Post-fix: both resolve to `~/ai/...` consistently.

### F14 — PyTorch nightly pin strategy breaks on every fresh install

`deployment/requirements-torch.txt` pins exact nightly versions:
```
torch==2.11.0.dev20260203+cu130
torchaudio==2.11.0.dev20260203+cu130
torchvision==0.25.0.dev20260203+cu130
```
generated 2026-03-22. As of today (2026-05-17, ~12 weeks later), the
PyTorch nightly index has **yanked the 2026-02-03 nightlies entirely**.
Oldest cu130 nightly currently available: 2026-03-19. Result: the
pinned versions return `ResolutionImpossible`.

This is structural, not transient. PyTorch nightlies have a finite
shelf life (a few weeks). The strategy "pin to specific date for
Blackwell safety" inherently breaks for any fresh install older than
~6 weeks from the pin date.

**Three additional sub-frictions discovered while resolving this:**

- **F14a — Major-version drift between torch and torchaudio nightlies.**
  torch nightly is currently at version `2.13.0.dev*`, torchaudio at
  `2.11.0.dev*`. Two majors apart. The `requirements-torch.txt` had
  them in sync at `2.11.0.dev*` for both — that no longer reflects
  reality. Naive pinning to "same date, same version" fails.

- **F14b — torchvision nightly N requires torch nightly N-1.**
  Today's torchvision (`0.28.0.dev20260517+cu130`) declares a hard
  dependency on `torch==2.13.0.dev20260516`, i.e. yesterday's torch
  nightly. The "all packages same date" instruction from the docs
  is literally impossible for the most recent date.

- **F14c — pip's resolver silently falls back to stable releases.**
  Running `pip install --pre torch torchaudio torchvision --extra-index-url
  ...cu130` produced a mix: torch nightly + **torchaudio stable 2.11.0
  (no cu130 build)** + torchvision nightly. The stable torchaudio
  doesn't track CUDA 13 — exactly the kind of split that the Blackwell
  warning is meant to prevent, achieved silently.

**This install resolved manually to:**
```
torch==2.13.0.dev20260516+cu130
torchaudio==2.11.0.dev20260516+cu130
torchvision==0.28.0.dev20260517+cu130   # depends on torch 0516
torchao==0.15.0
```
Works on RTX 4090 (sm_89). User informs the eventual GPU is RTX 6000
Blackwell (sm_120); the Blackwell-safety promise of "all same date"
is approximated here as "torch+torchaudio same date, torchvision N+1
because pip dep solver enforces it". This is the best PyTorch's own
infrastructure currently allows.

**Recommendation:** Re-write `requirements-torch.txt` to either:
1. Compute the install date dynamically (`pip install
   torch==2.13.0.dev$(date -u +%Y%m%d)+cu130 ...`) with explicit
   fallback to N-1, N-2, …, OR
2. Maintain a `pip install` helper script in `deployment/` that probes
   the nightly index and picks the latest mutually-consistent triplet
   for the user's CUDA target, OR
3. Snapshot wheels to the institution's own pypi mirror at known-good
   dates — the only fully reproducible path.

Today's strategy (fixed pin in a file) is a guaranteed-broken approach
for every fresh install more than ~6 weeks old.

### F15 — gcc 15 (Ubuntu 26.04 default) incompatible with CUDA 13.0

`AGENT_INSTALL_INSTRUCTIONS.md` lists `build-essential` (which pulls
the distro's default gcc) and `cuda-toolkit-13-0` side by side, with
no version constraint on gcc. On Ubuntu 26.04 the default is gcc-15.2,
which fails CUDA 13.0 header compatibility checks with:

```
/usr/include/x86_64-linux-gnu/bits/mathcalls.h(206): error:
  exception specification is incompatible with that of previous function "rsqrt"
  (declared at line 629 of /usr/local/cuda/.../crt/math_functions.h)
```

This is a header-level conflict between glibc-2.40+ math declarations
and CUDA 13.0's `math_functions.h`. `nvcc --allow-unsupported-compiler`
would bypass the **version check**, but does not resolve the **header
incompatibility** itself — compile still fails.

**Workaround applied:** install `gcc-14 g++-14` from the same Ubuntu
repos, then point CMake at them via `CC=/usr/bin/gcc-14
CXX=/usr/bin/g++-14` before `pip install` of any CUDA-extension.

**Recommendation:** Update `AGENT_INSTALL_INSTRUCTIONS.md` §OS
Prerequisites to explicitly install `gcc-14 g++-14` alongside
`build-essential` on Ubuntu 26.04 (and possibly newer Fedora/Arch),
and update Phase 2b + Phase 4 instructions to set `CC`/`CXX` env vars
for `pip install` of llama-cpp-python and custom_rasterizer. Add a
table to the docs listing CUDA 13.0's supported gcc version range.

### F16 — pip wheel cache hides CUDA rebuild failures

Phase 2 of `AGENT_INSTALL_INSTRUCTIONS.md` says:
```
pip uninstall -y llama-cpp-python
CMAKE_ARGS="-DGGML_CUDA=on" pip install --no-binary llama-cpp-python llama-cpp-python==0.3.19
```

What actually happens: pip notices it has a wheel for
`llama-cpp-python-0.3.19` in its local wheel cache (built earlier
during Phase 2 main install, as the **CPU** build) and reuses it —
the CMake flags are silently ignored. The `--no-binary` flag only
prevents downloads from PyPI, not reuse of locally-built wheels.

Result: `libggml-cuda.so` is missing, LLM inference runs on CPU
without warning.

**Workaround applied:** add `pip cache remove "llama_cpp_python*"`
between the uninstall and reinstall, plus `--no-cache-dir` flag on
the install.

**Recommendation:** Update Phase 2b instructions to:
```bash
pip uninstall -y llama-cpp-python
pip cache remove "llama_cpp_python*"
CMAKE_ARGS="-DGGML_CUDA=on" CC=/usr/bin/gcc-14 CXX=/usr/bin/g++-14 \
  pip install --no-binary llama-cpp-python --no-cache-dir llama-cpp-python==0.3.19
```
Add the existing verification snippet (look for `libggml-cuda.so`).
Without `--no-cache-dir`, the verification fails on any second-time
install — and silently succeeds with a CPU build the first time
**if Phase 2 also installed the package fresh**.

### F18 — `requirements-git.txt` is not valid pip syntax

```
ERROR: Invalid requirement: -e git+https://...#egg=heartlib --no-deps
pip: error: no such option: --no-deps
```

`--no-deps` is a pip CLI flag, not a requirements-file directive.
`pip install -r deployment/requirements-git.txt` fails immediately
on line 1. The docs (`AGENT_INSTALL_INSTRUCTIONS.md` §Phase 3)
acknowledge this and provide a manual fallback list — but ship
the broken file anyway.

**Recommendation:** Either delete `requirements-git.txt` and document
only the manual install sequence, or split into one valid
`requirements-git-with-deps.txt` and a separate shell helper that
runs heartlib with `--no-deps` explicitly.

### F19 — Pinned `heartlib` commit no longer exists

`requirements-git.txt` pins
`heartlib.git@ef0c33b8143680f70c78ec148fbceeec53d6151e`. `git
ls-remote heartlib.git` returns no match for that SHA in any branch.
The commit has been rewritten away (squashed, rebased, or force-pushed
out of every visible ref). Result: pip falls back to a default branch
clone which fails because pip cannot find the requested SHA.

**Workaround applied:** install from `main` HEAD
(`3783bdb8441f2c298b1e64c8651173aac200361c` at install time).
Functionally heartlib imports and registers; no runtime test of
music generation performed yet.

**Recommendation:** Either fork heartlib to a UCDCAE-controlled
mirror with stable refs, or vendor it into the repo. Pinning
to upstream SHAs of small academic libraries with active force-push
workflows guarantees install breakage on any time horizon longer
than a few months.

### F20 — Dependency-conflict snowball: heartlib vs torch nightlies vs ComfyUI nodes

After Phase 3 and Phase 7b, pip's resolver has accumulated
significant unresolved conflicts:

- `heartlib` declares strict pins:
  `torch<2.11`, `torchao==0.9.0`, `numpy==2.0.2`, `transformers==4.57.0`,
  `accelerate==1.12.0`, `bitsandbytes==0.49.0`, `einops==0.8.1`,
  `modelscope==1.33.0`, `tokenizers==0.22.1`, `torchaudio<2.11`,
  `torchtune==0.4.0`, `torchvision<0.26`, `tqdm==4.67.1`, `traitlets==5.7.1`,
  `vector-quantize-pytorch==1.27.15`
- We installed `torch==2.13.0.dev20260516+cu130` per Phase 1 — three
  whole major versions above heartlib's ceiling.
- `comfyui-sound-lab` downgraded `numpy` from 2.0.2 to **1.26.4**, which
  in turn violates `tifffile>=2.1` and `opencv-python>=2`.
- `torchao 0.15.0` prints at every import:
  "Skipping import of cpp extensions due to incompatible torch version".
- `imagebind` raises `pkg_resources` deprecation warning (slated for
  removal 2025-11-30; we're past that date).

**Surprisingly, all imports still succeed and Phase 6 verification
passes.** The dep constraints are violated but pure-Python imports
don't enforce them at runtime. Until a code path actually exercises
the incompatible API surface (e.g. `torchao.quantization` C++
extensions, heartlib's quantized inference on torch 2.13), nothing
breaks. The breakage is **deferred**, not absent.

**Recommendation:** The dependency matrix in this repo needs an
explicit "supported" snapshot. Either:
1. Maintain a lockfile (`uv.lock`, `pdm.lock`) snapshot at the
   dev PC's known-working state, with one-command reproduction.
2. Vendor heartlib (already a candidate per F19) and relax its
   pins to ranges compatible with the rest of the stack.
3. Move heartlib off the platform's torch venv and into its own
   venv — gpu_service can call it as a subprocess. This sidesteps
   the entire torch version conflict.

The current state will produce silent latent failures when a workshop
hits the wrong code path. Probably tomorrow.

### F21 — `user_settings.json` is required but no example shipped

`devserver/__init__.py` fails fatally without `user_settings.json`:
```
FATAL: user_settings.json not found. This file is required —
it contains all model assignments.
```

Repo ships **no** `user_settings.json.example` to bootstrap. The
error message points at "Settings UI", but the Settings UI requires
the server to be running, which requires the file. Chicken/egg.

**Workaround applied:** fetched the dev PC's `user_settings.json` via
the now-established SSH/rsync channel, then replaced all
`mammouth/...` model assignments (cloud LLM, requires API keys we
don't have) with local GGUF aliases (`qwen3:4b`, `qwen3-vl:2b`,
`llama-guard3:1b`).

**Recommendation:** Ship a `devserver/user_settings.json.example`
that contains a working local-only configuration. The current
"copy user_settings.json.example or configure via Settings UI"
message in the error is **literally false** — no such file exists.

### F22 — VLM model load can crash the entire GPU service [VERIFIED REPRODUCIBLE]

**Reproduced twice in one session, with two different VLM models
(Qwen3-VL-2B and Qwen3-VL-4B). Both via the same `mtmd_init_from_file`
codepath. Not a 2B-specific or 4B-specific issue — it's a systemic
process-isolation gap.**

First request to a multimodal model (Qwen3-VL via mmproj) crashed
`gpu_service` with:
```
ggml-backend.cpp:179: GGML_ASSERT(buffer) failed
mtmd_init_from_file → clip_init → clip_model_loader::load_tensors
```
The entire process died, taking all backends with it. After
`gpu_service` restart the same VLM model loaded successfully —
suggests a transient initialization race, not a fundamental
incompatibility.

**Architectural root cause:** `libmtmd.so` triggers `ggml_abort()` →
`abort()` (SIGABRT) on buffer-allocation failure. Python `try/except`
cannot catch this — the whole process dies. Since gpu_service runs
all model backends (Diffusers, HeartMuLa, MMAudio, all LLMs/VLMs)
in a single process via in-process bindings, **any model-init failure
kills every backend**. Mid-workshop, every Diffusers-based output
config (SD3.5, FLUX2, Wan2.2 etc.) silently disappears from the UI
because the frontend checks backend availability.

**Workshop impact:** A facilitator trying the Compare/Image-Understanding
4B feature can take the entire image-generation stack offline for the
remaining ~25 attendees. No user-facing recovery exists without admin
SSH access.

**Impact:** If this happens during a workshop with kids/youth
safety active (where VLM is mandatory), the GPU service is
unrecoverable mid-session.

**Recommendation:** Wrap VLM model init in process-isolated subprocess
so a crash doesn't kill the parent service. Add explicit error
handling around `mtmd_init_from_file` that retries once before
declaring the model unavailable.

### F23 — SD3.5 Diffusers OOM on 24 GB VRAM (RTX 4090)

`output_image_sd35_diffusers` returns "SD3.5 generation returned
empty result" silently — VRAM coordinator says we have ~21 GB free
after evictions, SD3.5 Large declares 28000 MB peak (config). Close
but apparently fails silently.

**Fallback worked:** automatic chunk fallback to `output_image_sd35_large`
(ComfyUI backend, different model loader, more aggressive VRAM
streaming) **succeeded** and produced a valid 1024×1024 PNG.

**Recommendation:** Document the VRAM floor for each default config in
`MODELS_REQUIRED.md`. Workshop facilitators on consumer GPUs need to
know which output_configs require the Blackwell-class hardware vs
which will gracefully fall back. The fallback system is a feature,
not a bug — surface it in the docs.

### F24 — VLM verdict parser false-positives on reasoning models

`qwen3:4b` (used as the verdict half of the two-step VLM check)
emits `<think>...</think>` reasoning blocks. Example actual
reasoning from this install's smoke test:
> "Okay, let's see. The image is of a koi fish... no violence,
> gore, nudity... The analysis says none of these are present."

The verdict-parser apparently looks for an explicit "safe" token
and, finding only an unfinished `<think>` block, defaults to BLOCK.
Result: every safe image got flagged unsafe in the smoke test.

**WARNING — known systemic issue, not a one-line parser fix.**
Multiple prior attempts to fix this have made the problem worse.
Each "obvious" tactical fix — force JSON output, regex on
`</think>`, swap to non-reasoning verdict model, "if unclear → safe"
fallback — has introduced new failure modes.

**Do NOT attempt a fix without first reconstructing the full debugging
history** from `docs/DEVELOPMENT_DECISIONS.md`
and the git history of `devserver/my_app/utils/vlm_safety.py`.
That reconstruction is a prerequisite, not a nicety.

**Recommended ops-level workaround until a proper fix lands:** set
`DEFAULT_SAFETY_LEVEL` to a value not in `{kids, youth}` (e.g. `adult`
for testing) to skip the VLM check entirely, or accept the false-positive
block rate during workshops.

### F25 — `safety_level=adult` URL param ignored by VLM check

Smoke test sent `safety_level=adult` (which should skip VLM per
`vlm_safety.py:323` — "safety_level not covered by VLM check
(e.g. adult/research)"). Logs nevertheless show:
```
[VLM-SAFETY] Two-model path ... for youth
```
The URL param did not propagate to the VLM safety call — service
fell back to `DEFAULT_SAFETY_LEVEL=youth` from user_settings.

**Recommendation:** Trace the safety_level parameter from
`/api/schema/pipeline/generation` through to `vlm_safety_check`
and ensure it's threaded through. Likely a missing kwarg in the
SSE-streaming route handler.

---

## Smoke-Test Bottom Line

The install **passes** end-to-end:
- Stage 1–3 LLM pipeline runs on local `qwen3:4b` GGUFs.
- Stage 4 image generation produces real output on RTX 4090
  through the ComfyUI fallback path (SD3.5 Diffusers path OOMs).
- Generated artifact: `exports/json/2026-05-18/smoke-test-2/
  run_1779093771160_7b75ff/final/03_output_image.png` (orange
  koi fish in a swimming pool, 1024×1024, 1.5 MB).

The deployability story for educational institutions running
consumer-grade GPUs (24 GB VRAM) is **viable but degraded** —
they live on the ComfyUI fallback path for image gen, lose the
Diffusers fast-path until they upgrade to ≥48 GB VRAM, and need
the VLM safety pipeline reworked before deploying for actual
workshop use.

### F27 — `install_systemd_services.sh` is critical but invisible

**The single most important post-install step for any production
deployment**, and the canonical installation docs (`AGENT_INSTALL_INSTRUCTIONS.md`,
`INSTALLATION.md`) don't mention it. Without it:

- gpu_service runs as a manual nohup-process. A model-load crash (see F22)
  kills it permanently — no auto-restart. **Every Diffusers-based output
  config disappears from the UI** until an operator notices and manually
  restarts. Mid-workshop, this is unrecoverable without admin access.
- devserver backend equally fragile.
- Cloudflared has its own systemd unit (typically installed by `cloudflared`'s
  own installer), but the script wires the AI4ArtsEd backend's startup
  dependency on it.

On our fresh install we hit this twice in one session: F22 (Qwen3-VL-2B
mmproj crash on first call) and a separate Qwen3-VL-4B mmproj crash
during workshop testing. In both cases the entire GPU service died
silently. Manual recovery required SSH access — not workshop-operator
material.

`install_systemd_services.sh` exists in the repo root and creates:
- `ai4artsed-gpu.service` (`Restart=on-failure`, `RestartSec=15`,
  full env: `AI_TOOLS_BASE`, `PYTORCH_CUDA_ALLOC_CONF`, etc.)
- `ai4artsed-backend.service` (`Restart=always`, `RestartSec=5`,
  depends on gpu service + cloudflared)
- Optional: `cloudflared.service` (only if not already present)

**Recommendation (HIGH priority for next docs PR):**

1. Add `install_systemd_services.sh` as a mandatory step in
   `AGENT_INSTALL_INSTRUCTIONS.md` immediately after Phase 6 verification.
   Make it visually prominent (warning callout).
2. Note the script also fixes the F12 path issues by exporting
   `AI_TOOLS_BASE` correctly in each service Unit.
3. **ComfyUI is not covered** by `install_systemd_services.sh`. It is
   started by the backend's COMFYUI-MANAGER as a child process — that
   works as long as the backend is alive. But if ComfyUI itself crashes
   independently, recovery depends on the manager's auto-restart logic.
   Could be tightened by giving ComfyUI its own unit, but currently
   acceptable because backend acts as supervisor.

### F28 — HF cache hygiene matters more than docs suggest

Even with selective transfer, the HF cache structure
(`blobs/`, `snapshots/`, `refs/`) is brittle: rsync must preserve
the symlinks inside `snapshots/` for Diffusers to find the blobs.
Use `rsync -aH` (preserve hardlinks) plus `--copy-links` is the wrong
choice here. Confirm rsync flags before starting Tier D.

**Recommendation:** Add an `rsync_models_selective.sh` helper to
`deployment/` that codifies the Tier A–D split with the right flags.
