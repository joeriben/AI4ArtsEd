# DevServer Architecture

**Part 18: Data Storage & Persistence**

> **Last Updated:** 2026-01-17
> **Status:** Current as of v2.0.0-alpha.1 (2026-01-17 Lab Export Fix)

---

## Overview

**v2.0.0-alpha.1 Status:** DevServer uses **four active data persistence systems**:

1. **Execution History** - Research data tracking [ACTIVE]
2. **LivePipelineRecorder** - Real-time entity tracking + media storage [PRIMARY]
3. **CanvasRecorder** - Canvas workflow recording [ACTIVE]
4. **LatentLabRecorder** - Latent Lab experiment recording [ACTIVE]
5. ~~**Unified Media Storage**~~ - **REMOVED** (merged into LivePipelineRecorder)

**Critical Architecture:** Both active systems use a **unified `run_id`**.

**Major Change:** MediaStorage completely removed from pipeline execution. LivePipelineRecorder now handles ALL real-time tracking and media storage, eliminating redundancy.

---

## 1. ~~Execution History System~~ **REMOVED 2026-10-10**

The package `devserver/execution_history` (`ExecutionTracker`, `storage.py`, `models.py`) and the routes `/api/runs/*` were removed. The tracker had been replaced by a `NoOpTracker` in `schema_pipeline_routes.py`, so nothing wrote `exports/pipeline_runs/` any more; the routes had no caller. The `LivePipelineRecorder` (section 3) is the only recording system.

---

## 2. ~~Unified Media Storage~~ **DEPRECATED - REMOVED**

### Historical Purpose

Backend-agnostic media file persistence with complete run metadata.

### Why It Was Removed

**Problem:** Dual-system redundancy between MediaStorage and LivePipelineRecorder:
- Both systems downloaded media from ComfyUI
- Both systems saved metadata
- LivePipelineRecorder had to copy from MediaStorage
- Complex coordination, duplicate code paths

**Solution:** Merge functionality into LivePipelineRecorder as single source of truth.

**Migration:** All MediaStorage functionality moved to LivePipelineRecorder.

### Legacy Architecture

```
exports/json/
└── {run_id}/
    ├── metadata.json
    ├── input_text.txt
    ├── transformed_text.txt
    └── output_image.png
```

**Note:** This storage location is now used by LivePipelineRecorder.

### Migration to LivePipelineRecorder

All MediaStorage functionality was moved to LivePipelineRecorder:
- Backend detection logic → LivePipelineRecorder
- Media download from ComfyUI → LivePipelineRecorder
- Metadata management → LivePipelineRecorder
- API endpoints → Now served by LivePipelineRecorder

**See Section 3 (LivePipelineRecorder)** for current implementation details.

---

## 3. LivePipelineRecorder

### Purpose

Real-time entity tracking with sequential numbering for frontend polling + media storage.

**v2.0.0-alpha.1 Status:** PRIMARY system for all real-time data and media storage.

### Problem Solved: Dual-ID Bug + Redundancy

**Before the unified run_id:**
```python
# OLD ExecutionTracker generated:
execution_id = f"exec_{timestamp}_{uuid8}"

# OLD MediaStorage generated:
run_id = str(uuid.uuid4())

# Result: Complete desynchronization!
```

**After the unified run_id:**
```python
# Generate ONCE at pipeline start:
run_id = str(uuid.uuid4())

# Pass to ALL systems:
execution_tracker = ExecutionTracker(execution_id=run_id)  # REMOVED with execution_history
media_storage.create_run(run_id)  # REMOVED with MediaStorage
pipeline_recorder = LivePipelineRecorder(run_id)
```

**After the MediaStorage removal:**
```python
# Generate ONCE at pipeline start:
run_id = str(uuid.uuid4())

# Pass to ACTIVE systems:
pipeline_recorder = LivePipelineRecorder(run_id)  # PRIMARY - handles media + tracking
# MediaStorage completely removed; ExecutionTracker removed 2026-10-10
```

### Architecture

**Storage Location:**
```
exports/json/              # PRIMARY LOCATION
└── {run_id}/
    ├── metadata.json
    ├── 01_input.txt
    ├── 02_translation.txt
    ├── 03_safety.json
    ├── 04_interception.txt
    ├── 05_safety_pre_output.json
    └── 06_output_image.png
```

**Sequential entity tracking:** 01 → 06 for easy frontend access.

**Note:** Storage path migrated from `pipeline_runs/{run_id}/` to `exports/json/{run_id}/` to unify with the legacy MediaStorage location.

### Data Model

#### Metadata.json
```json
{
  "run_id": "812ccc30-5de8-416e-bfe7-10e913916672",
  "schema": "dada",
  "execution_mode": "eco",
  "safety_level": "kids",
  "user_id": "DOE_J",
  "start_time": "2025-11-04T21:15:30",
  "status": "completed",
  "current_stage": 5,
  "current_step": "pipeline_complete",
  "progress": "6/6",
  "entities": {
    "01_input": {"type": "text", "available": true},
    "02_translation": {"type": "text", "available": true},
    "03_safety": {"type": "json", "available": true},
    "04_interception": {"type": "text", "available": true},
    "05_safety_pre_output": {"type": "json", "available": true},
    "06_output_image": {"type": "image", "available": true, "mime_type": "image/png"}
  }
}
```

### Entity Types

**Text Entities:**
- `01_input.txt` - Original user input
- `02_translation.txt` - Translated text
- `04_interception.txt` - Transformed prompt

**JSON Entities:**
- `03_safety.json` - Stage 1 safety check results
- `05_safety_pre_output.json` - Stage 3 safety check results

**Media Entities:**
- `06_output_image.png` - Generated image
- `06_output_audio.mp3` - Generated audio
- `06_output_video.mp4` - Generated video (future)

### The entities list IS the inventory (verified 2026-09-02)

**Current shape on disk.** The snippet above is the historical form.
Today a run lives at `exports/json/<date>/<device_id>/<run_id>/`, its files sit in
a `final/` subfolder, and `entities` is an ORDERED LIST:

```json
{
  "entities": [
    {"sequence": 1, "type": "context_prompt", "filename": "01_context_prompt.txt",
     "timestamp": "2026-01-31T13:10:56.752886", "metadata": {}},
    {"sequence": 4, "type": "output_image", "filename": "04_output_image.png",
     "timestamp": "2026-01-31T13:11:23.009356",
     "metadata": {"config": "qwen", "seed": 79904748, "format": "png",
                  "source_path": ".../ComfyUI/output/ai4artsed_qwen_00034_.png"}}
  ]
}
```

**Every reader resolves media through the list, never through the folder.**
`_find_entities_by_type()` (`media_routes.py`) filters `output_<kind>` and sorts by
`sequence`; `/api/media/image/<run>/<index>` indexes INTO that filtered list. The
research table, the favourites bar, the thumbnails and the Resona tools go the
same way. A file in `final/` that no entity names is invisible platform-wide.

**Two failure modes, both observed and repaired on 2026-09-02:**

| Failure | Seen | Effect | Repair |
|---|---|---|---|
| The list carries the wrong word for a file | 48 runs, 2026-02-01 to 2026-03-22: the music and film configs wrote `output_image` whatever the file held | sound and film were offered as pictures - no miniature, empty cell | `devserver/scripts/repair_sound_runs_typed_as_image.py` |
| The list is reset while the run continues | 1 run, 2026-01-31: the record was re-initialised mid-session, numbering restarted at 1 | 11 outputs including the session's only video went silent; a favourite pointed into nothing | `devserver/scripts/restore_entities_lost_from_record.py` |

**Rules any repair of a record must follow** (both scripts implement them):

1. **The word comes from the first bytes, never from the filename.** `NN_<type>.<ext>`
   is a good hint and has been wrong twice. Where name and bytes disagree, the run is
   left untouched and named.
2. **Which exact word is the platform's own answer** - what the same config recorded
   later of its own accord; where no later run exists, the file decides.
3. **mtimes order a folder only under two checks:** no two files may share one, and
   every SURVIVING entity's recorded timestamp must lie within 5 s of its file. An
   Attention Cartography plate can be set again after the run; such a run fails the
   check and is refused.
4. **What only the record knew stays gone.** Seed, config and source path are not
   substituted; a restored entity carries `recovered_from_file: true` and names
   `file_mtime` as the origin of its timestamp.
5. **`expected_outputs` stays as written.** It is a fixed six-slot schedule, read as
   the DENOMINATOR of a run's progress (`pipeline_recorder.py`, `completed/total`) and
   as a schedule (`next_expected`) - never an inventory of what was produced.
   `current_state` likewise is a live-run snapshot and stays.
6. **Drop the run's miniatures.** They are keyed by `run_id` and by
   `run_id`_`index`, and are served `immutable` for a year, so a changed index would
   show one picture under another's name (`thumbnails.drop_cached`).
7. **Restart the backend.** `load_recorder` caches the run in `_active_recorders` for
   the life of the process and writes that copy back when the run is touched again -
   a repair on disk is invisible, and at risk, until `systemctl restart
   ai4artsed-backend`.
8. **Back up outside every git working tree.** `exports/` is gitignored, but this repo
   has sibling worktrees next to it; the check walks all ancestors of the backup path
   looking for `.git`.

**Canvas runs record through their own pipeline** (`canvas_executor`) and legitimately
show the same shape - entities carrying `node_type` and no `type`. They are out of
scope for these repairs, and both scripts refuse them.

### Real-Time State Tracking

```python
# Update state throughout pipeline
recorder.update_state(
    stage=1,
    step='translation_and_safety',
    progress='1/6'
)

recorder.update_state(
    stage=2,
    step='interception',
    progress='3/6'
)

recorder.update_state(
    stage=4,
    step='media_generation',
    progress='5/6'
)
```

### Integration

**File:** `devserver/my_app/services/pipeline_recorder.py`

```python
from my_app.services.pipeline_recorder import get_recorder

# Initialize with unified run_id
recorder = get_recorder(
    run_id=run_id,  # Same as ExecutionTracker & MediaStorage
    schema=schema_name,
    execution_mode=execution_mode,
    safety_level=safety_level,
    user_id=user_id
)

# Save entities throughout pipeline
recorder.save_entity('input', input_text, metadata={...})
recorder.save_entity('translation', translation_output)
recorder.save_entity('safety', safety_result)
recorder.save_entity('interception', interception_output)
recorder.save_entity('safety_pre_output', safety_result)
# Media downloaded and saved by LivePipelineRecorder directly
await recorder.download_and_save_media(prompt_id, media_type='image')
```

### Media Polling Bug Fix (Critical Achievement)

**The Problem:**
ComfyUI generates images asynchronously. Calling `get_history(prompt_id)` immediately returns empty result.

**The Fix (in pipeline_recorder.py):**
```python
# OLD (BROKEN in MediaStorage):
# history = await client.get_history(prompt_id)

# NEW (FIXED in LivePipelineRecorder):
history = await client.wait_for_completion(prompt_id)
```

**Why This Matters:**
- `wait_for_completion()` polls every 2 seconds until workflow finishes
- **OLD ExecutionTracker identified this issue but FAILED to fix it for months**
- **The LivePipelineRecorder integration fixed it properly**
- **A subsequent media_type bugfix completed the stability**

### API Endpoints

See **ARCHITECTURE PART 11 (API-Routes)** for complete API documentation:
- `GET /api/pipeline/<run_id>/status` - Real-time execution state
- `GET /api/pipeline/<run_id>/entities` - List available entities
- `GET /api/pipeline/<run_id>/entity/<type>` - Fetch specific entity

---

## Unified run_id Architecture

### Critical: Single ID Across All Systems (Enhanced 2026-01-17)

**Lab Architecture Extension (2026-01-17):**

In the Lab paradigm, atomic endpoints (`/interception`, `/generation`) are called separately by the frontend. The `run_id` must be passed from the first endpoint to subsequent endpoints to maintain a unified export folder.

```
Frontend (text_transformation.vue)
       │
       ▼
POST /interception ────────────────────────────┐
       │                                       │
       │  Backend: get_recorder(run_id=new)    │
       │  Saves: input, safety, interception   │
       │                                       │
       ▼                                       │
Response: { run_id: "run_xxx_abc", ... }       │
       │                                       │
       │  Frontend stores currentRunId         │
       │                                       │
       ▼                                       │
POST /generation { run_id: "run_xxx_abc" } ────┘
       │
       │  Backend: load_recorder(run_id)
       │  Saves: optimized_prompt, output_image
       │
       ▼
All entities in ONE folder: exports/json/run_xxx_abc/
```

**v2.0.0-alpha.1 Implementation (Werkraum style):**
```python
# schema_pipeline_routes.py

# Generate ONCE at pipeline start
run_id = str(uuid.uuid4())

# Pass to the ACTIVE system (the LivePipelineRecorder; the ExecutionTracker
# that once stood here was removed 2026-10-10)

# MediaStorage REMOVED - no longer used
# media_storage.create_run(...)  # DEPRECATED

recorder = get_recorder(
    run_id=run_id,  # ← Same ID (PRIMARY system)
    schema=schema_name,
    execution_mode=execution_mode,
    safety_level=safety_level,
    user_id=user_id
)
```

**Lab Architecture Implementation (2026-01-17):**
```python
# /interception endpoint
recorder = get_recorder(run_id=run_id, ...)
recorder.save_entity('input', input_text)
recorder.save_entity('safety', safety_result)
recorder.save_entity('interception', interception_result)
# Return run_id to frontend

# /generation endpoint
if run_id:
    recorder = load_recorder(run_id)  # Load EXISTING recorder
else:
    recorder = get_recorder(run_id=new_run_id, ...)  # New recorder

# Save output entities to SAME folder
recorder.save_entity('output_image', image_data, metadata={...})
```

### Data Flow (v2.0.0-alpha.1)

```
1. Pipeline Start
   ↓
   run_id = uuid.uuid4()
   ↓
2. Initialize the ACTIVE system with that run_id
   └─→ LivePipelineRecorder(run_id)           # PRIMARY - media + tracking
   ↓
3. Execute Pipeline (Stages 1-4)
   ├─→ tracker.log_*()                        # Research data logging
   └─→ recorder.save_entity()                 # Real-time entity + media
   ↓
4. Finalize
   ├─→ tracker.finalize() → exports/pipeline_runs/exec_*.json
   └─→ recorder → exports/json/{run_id}/      # PRIMARY storage location
```

### Multi-Backend Image Saving (2026-01-17)

Different backends return outputs in different formats. The `/generation` endpoint handles all:

| Backend | Return Format | Handling |
|---------|--------------|----------|
| SwarmUI (SD3.5) | `swarmui_generated` + `image_paths` | Download via SwarmUI API |
| ComfyUI Workflow (QWEN, FLUX2) | `workflow_generated` + `filesystem_path` | Read from local filesystem |
| OpenRouter (Gemini) | Base64 inline or URL | Decode base64 / fetch URL |
| OpenAI (GPT-Image) | Base64 data URI | Strip prefix, decode base64 |

```python
# /generation endpoint - unified output handling
if output_value == 'swarmui_generated':
    # Download via SwarmUI API (existing code)
    ...
elif output_value == 'workflow_generated':
    # Check filesystem_path first (QWEN, FLUX2)
    filesystem_path = output_result.metadata.get('filesystem_path')
    if filesystem_path and os.path.exists(filesystem_path):
        with open(filesystem_path, 'rb') as f:
            file_data = f.read()
        recorder.save_entity(f'output_{media_type}', file_data, ...)
    elif media_files:
        # Legacy: binary data in metadata
        ...
elif is_url(output_value):
    # Download from URL (OpenRouter)
    response = requests.get(output_value)
    recorder.save_entity(f'output_{media_type}', response.content, ...)
elif is_base64(output_value):
    # Decode base64 (OpenAI, some OpenRouter)
    if output_value.startswith('data:'):
        output_value = output_value.split(',', 1)[1]
    file_data = base64.b64decode(output_value)
    recorder.save_entity(f'output_{media_type}', file_data, ...)
```

---

## 4. LatentLabRecorder

### Purpose

Research data export for Latent Lab experiments. The Latent Lab bypasses the 4-Stage Orchestrator, so `LivePipelineRecorder` cannot capture its data. `LatentLabRecorder` is a frontend-primary hybrid: the Vue composable POSTs parameters + base64 outputs to a lightweight backend recorder.

### Architecture

- **Frontend:** `useLatentLabRecorder(toolType)` composable with lazy start (no empty folders)
- **Backend:** `LatentLabRecorder` class writes to same folder structure as Canvas/Pipeline
- **Endpoints:** `POST /api/latent-lab/record/{start,save,end}`, `GET /api/latent-lab/run/<run_id>[/part/<i>]`
- **Folder:** `exports/json/YYYY-MM-DD/device_id/run_xxx/`
- **One folder per GENERATION** (2026-08-21): a sitting (one open tab) is not an
  address; a run is. `record()` writes a run folder and returns its id, and each
  run carries `session_id` + `generation`. This is what lets the Ablage
  (favorites) store the whole run — parameters and ordered parts — instead of the
  pipeline run's finished picture alone. See **PART 28**, "Sitting vs. Run".

### Key Difference from LivePipelineRecorder

| Aspect | LivePipelineRecorder | LatentLabRecorder |
|--------|---------------------|-------------------|
| Data source | Backend (orchestrator) | Frontend (POST) |
| Stage tracking | Yes (4 stages) | No |
| Expected outputs | Pre-declared | Dynamic |
| Lazy start | No (created at pipeline start) | Yes (created on first record) |
| metadata.type | varies | `"latent_lab"` |
| Restore shape | pipeline fields (input, interception, media) | `instrument` object (parameters, ordered parts, outputs) |

### Integration

7 Latent Lab views + Surrealizer. Each view imports the composable and calls `record()` after successful generation. See **ARCHITECTURE PART 28 (Latent Lab)** for per-tool details.

Two instruments have the SERVER write the run (the Vue composable opens the
sitting before the run, and the request names it under `record`): Mean Images
since 2026-09-04 (`routes/mean_images_routes.py`, `_record_cell`) and the
Denoising Archaeology since 2026-09-22 (`services/denoising_archaeology_record.py`,
called from the direct endpoint). The answer carries the written run's id, and
the surface calls `record()` only where the server refused or failed the record
(`record_refused` in the answer). The step frames stay IN the answer: an axis
that fetches a frame when it is selected shows the one before it until that
frame arrives.

### Files

| File | Purpose |
|------|---------|
| `devserver/my_app/services/latent_lab_recorder.py` | Recorder class + active registry |
| `devserver/my_app/routes/latent_lab_recorder_routes.py` | Flask blueprint (3 endpoints) |
| `public/.../composables/useLatentLabRecorder.ts` | Vue composable |

---

## Storage Locations Summary (v2.0.0-alpha.1)

```
Project Root
├── exports/
│   ├── json/                          # Shared location for ALL recorders
│   │   └── YYYY-MM-DD/
│   │       └── {device_id}/
│   │           ├── run_xxx/           # LivePipelineRecorder (4-Stage Pipeline)
│   │           │   ├── metadata.json
│   │           │   ├── final/
│   │           │   │   └── 01_output_image.png
│   │           │   └── prompting_process/
│   │           │       └── 001_input.txt
│   │           │
│   │           ├── run_yyy_canvas/    # CanvasRecorder (Canvas Workflows)
│   │           │   ├── metadata.json  # type: "canvas_workflow"
│   │           │   ├── workflow.json
│   │           │   └── final/
│   │           │
│   │           └── run_zzz/           # LatentLabRecorder (Latent Lab)
│   │               ├── metadata.json  # type: "latent_lab"
│   │               ├── final/
│   │               │   └── 01_output_image.png
│   │               └── prompting_process/
│   │                   ├── 001_parameters.json
│   │                   └── 002_step_01.jpg
│   │
│   └── pipeline_runs/                 # Execution History
│       └── exec_20251104_*.json      # Research data export format
│
└── # DEPRECATED locations:
    # pipeline_runs/{run_id}/ - REMOVED
    # MediaStorage system - REMOVED
```

---

## Key Design Decisions

### 1. Two Active Systems (v2.0.0-alpha.1)

Since 2026-10-10 one system remains: `execution_history` and `/api/runs/*` are removed (note at the top), and the `LivePipelineRecorder` is the only recording system. The rest of this subsection records the earlier state.

**Simplification:**
- ~~Three parallel systems~~ → **Two active systems**
- MediaStorage removed → LivePipelineRecorder handles all real-time data
- ExecutionHistory: Complete pedagogical journey for research
- LivePipelineRecorder: Real-time frontend tracking + media storage (PRIMARY)

**Why Two Systems Remain:**
- Different data models (sequential entities vs. research taxonomy)
- Different access patterns (real-time polling vs. export queries)
- ExecutionHistory proven valuable for research
- LivePipelineRecorder optimized for frontend needs

### 2. Unified run_id

**Critical Fix:** Prevents Dual-ID desynchronization bug.

**Single source of truth:** Generated once, used everywhere.

**Benefit:** Unified ID made MediaStorage removal clean and safe.

### 3. Flat Structures

**No hierarchical sessions:**
- Session entity doesn't exist yet technically
- UUID-based enables future queries via metadata
- Simpler than complex hierarchies

### 4. Atomic Research Units

**One folder = complete run:**
- All files for one pipeline execution in one location
- No split data across multiple directories
- Export-ready (zip one folder = complete data)

### 5. MediaStorage Removal

**Why removed:**
- Duplicate functionality with LivePipelineRecorder
- Complex coordination between systems
- Redundant media downloads
- LivePipelineRecorder proved more reliable

**Result:** Cleaner architecture, single source of truth for real-time data

---

## Related Documentation

- **API Endpoints:** ARCHITECTURE PART 11 (API-Routes)
- **4-Stage Pipeline:** ARCHITECTURE PART 01 (4-Stage Orchestration Flow)
- **Technical Details:**
  - `docs/EXECUTION_TRACKER_ARCHITECTURE.md` (1200+ lines)
  - `docs/ITEM_TYPE_TAXONOMY.md` (Item type taxonomy)
  - `docs/LIVE_PIPELINE_RECORDER.md` (Live recorder design, PRIMARY)
  - ~~`docs/UNIFIED_MEDIA_STORAGE.md`~~ (DEPRECATED, historical reference only)
- **Decision History:**
  - `docs/DEVELOPMENT_DECISIONS.md`

**v2.0.0-alpha.1 Migration Notes:**
- MediaStorage functionality fully migrated to LivePipelineRecorder
- Unified run_id architecture proven stable
- stage4_only feature operational

**2026-01-17 Lab Architecture Enhancement:**
- `run_id` now passed from `/interception` → frontend → `/generation`
- `load_recorder()` function loads existing Recorder from run_id
- Multi-backend image saving: filesystem_path, base64, URL all handled
- All image models (SD3.5, QWEN, FLUX2, Gemini, GPT-Image) export correctly

---

## Enhanced Research Data Export (2026-01-22/23)

### Complete Entity Set

The unified run folder now contains ALL data needed for research analysis:

```
exports/json/YYYY-MM-DD/{run_id}/
├── 01_input.txt              # Original user input (German)
├── 02_context_prompt.txt     # Meta-prompt/pedagogical rules (user-editable!)
├── 03_safety.txt             # Stage 1 safety result
├── 04_interception.txt       # Transformed text (German)
├── 05_translation_en.txt     # English translation for media generation (NEW!)
├── 06_optimized_prompt.txt   # Final prompt
├── 07_output_image.png       # Generated media
└── metadata.json             # Includes models_used (NEW!)
```

### Model Tracking (metadata.json)

New `models_used` field tracks which LLM was used at each pipeline stage:

```json
{
  "run_id": "run_1769122471728_362ba8",
  "config_name": "mad_world",
  "execution_mode": "eco",
  "safety_level": "youth",
  "models_used": {
    "stage2_interception": "local/gpt-OSS:20b",
    "stage3_translation": "local/gpt-OSS:20b",
    "stage3_safety": "shieldstral:3b",
    "stage4_output": "sd35_large"
  },
  "entities": [...]
}
```

- `stage3_translation`: the model Stage 3 asked to translate (`STAGE3_MODEL` as set when
  Stage 3 starts), where it did — at research and adult only when the translation is
  forced. A failed attempt counts. The entry records the setting, not a model the
  translation reports, so a change of the setting can put the wrong model in it: a
  translation reused from the one-hour cache that was made under an earlier setting, and
  the two SD3.5 encoder halves, which are translated after the check.
- `stage3_safety`: the model the check asked, whether or not it answered — the safety
  classifier (`SAFETY_MODEL`), which names itself in the result; for generated code on
  `/pipeline/interception`, `STAGE3_MODEL`, which the code check asks. Blocked runs in the
  Flow and on `/pipeline/interception` carry both as well; `/pipeline/generation` keeps no
  record of a blocked run. A Flow run that stops between the check and the generation —
  stopped by the visitor, or turned away because the device still has a generation
  running — records no Stage 3 model.
- `context_translation`: the model that translated a visitor-edited context
  (`/pipeline/interception`, Phase 2).

Records written before 2026-09-26 differ: `/pipeline/generation` wrote
`stage3_safety` = `STAGE3_MODEL`, and `/pipeline/interception` wrote `stage1_safety` =
`STAGE1_TEXT_MODEL`. Since the check chain moved to the classifier (494a659c, 2026-09-24),
both name a translation model, not the model that checked. Flow runs recorded no Stage 3
model, and their blocked-run error named `llamaguard` as the check.

This enables:
- **Reproducibility:** Know exact model versions used
- **Research Analysis:** Compare outputs across different models
- **Debugging:** Identify which stage/model caused issues

### Translation Entity

The `translation_en.txt` entity captures the Stage 3 translation output:
- Input: German transformed text from Stage 2
- Output: English prompt sent to media generation models
- Purpose: Research can analyze translation quality and its impact on outputs

### Unified Run Architecture (Fixed)

**Before the fix:**
```
run_123/        ← Interception endpoint creates
gen_456/        ← Generation endpoint creates SEPARATE folder!
```

**After the fix:**
```
run_123/        ← SINGLE folder for entire session
```

**Implementation:**
1. Frontend stores `run_id` from interception response
2. Frontend passes `run_id` to generation endpoint
3. Backend uses `load_recorder(run_id)` to append to existing folder

---

## Favorites System

### Purpose

Persistent bookmarking of generated outputs for:
- Session restore (reload exact input state)
- Cross-view transfer (T2I → I2I)
- Research data collection

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FooterGallery.vue                     │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                        │
│  │thumb│ │thumb│ │thumb│ │thumb│  [← Restore] [→ I2I]   │
│  └─────┘ └─────┘ └─────┘ └─────┘                        │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │ watches pendingRestoreData
                           │
┌──────────────────────────┴──────────────────────────────┐
│                    Pinia Store (favorites.ts)            │
│  - favorites: FavoriteItem[]                            │
│  - pendingRestoreData: RestoreData | null               │
│  - setRestoreData(data)                                 │
└─────────────────────────────────────────────────────────┘
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/favorites` | GET | List all favorites |
| `/api/favorites` | POST | Add favorite `{ run_id, media_type }` |
| `/api/favorites/<run_id>` | DELETE | Remove favorite |
| `/api/favorites/<run_id>/restore` | GET | Get complete restore data |

### Restore Data Structure

```typescript
interface RestoreData {
  run_id: string
  schema: string
  execution_mode: string
  timestamp: string
  input_text?: string           // Original input
  context_prompt?: string       // Meta-prompt/rules
  transformed_text?: string     // Interception result
  translation_en?: string       // English translation
  models_used?: ModelsUsed      // LLM models per stage
  media_outputs: MediaOutput[]  // Generated media URLs
  target_view: string           // 'text-transformation' | 'image-transformation'
}
```

`media_outputs` lists a run's `output_<kind>` entities AND the entities a runtime
records under its own name (`p5`, `tonejs`, `sonicpi`, `midi` — a sketch IS its
source text). Each carries its `type`, and a consumer picks BY TYPE: a run can
hold a sketch and a picture at once, so the first entry is not always the one
that was asked for.

### Store-Based Restore Pattern

**Why not sessionStorage?**
- Timing issues with `onMounted` hooks
- Data lost on page refresh
- Complex serialization/parsing

**Store-based solution:**
```typescript
// FooterGallery.vue - sets data
favoritesStore.setRestoreData(restoreData)
router.push('/text-transformation')

// text_transformation.vue - watches and consumes
watch(() => favoritesStore.pendingRestoreData, (data) => {
  if (!data) return
  inputText.value = data.input_text
  contextPrompt.value = data.context_prompt
  interceptionResult.value = data.transformed_text
  favoritesStore.setRestoreData(null) // Clear after consuming
}, { immediate: true })
```

**Benefits:**
- Reactive: Works even if already on target page
- Immediate: `{ immediate: true }` processes on mount
- Clean: No manual cleanup needed

### Files

| File | Purpose |
|------|---------|
| `src/components/FooterGallery.vue` | Fixed footer with thumbnail gallery |
| `src/stores/favorites.ts` | Pinia store for state management |
| `devserver/my_app/routes/favorites_routes.py` | REST API endpoints |

---
