# AI4ArtsEd Technical Whitepaper

**System Architecture and Implementation Guide**

*Version 2.1 - January 2026*

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Pedagogical Foundation](#2-pedagogical-foundation)
3. [Architecture](#3-architecture)
4. [The 4-Stage Pipeline](#4-the-4-stage-pipeline)
5. [Three-Layer Configuration System](#5-three-layer-configuration-system)
6. [Frontend (Vue 3)](#6-frontend-vue-3)
7. [Backend (Flask/DevServer)](#7-backend-flaskdevserver)
8. [SwarmUI/ComfyUI Integration](#8-swarmuicomfyui-integration)
9. [LLM Providers](#9-llm-providers)
10. [LoRA Training Studio](#10-lora-training-studio)
11. [Additional Features](#11-additional-features)
12. [API Reference](#12-api-reference)
13. [Deployment](#13-deployment)
14. [Development Guide](#14-development-guide)

---

## 1. System Overview

### What is AI4ArtsEd?

AI4ArtsEd is a pedagogical experimentation platform for critical engagement with generative AI. It separates the creative process into visible, editable steps, making AI transformation transparent.

### Components

- **Frontend**: Vue 3 SPA with TypeScript
- **Backend**: Flask-based orchestration server (DevServer)
- **Generation Backend**: SwarmUI with ComfyUI workflows (separate installation)
- **LLM Layer**: Multi-provider support (Ollama, OpenRouter, Bedrock, Mistral)

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| WAS/WIE Separation | User provides idea (WAS) + rules (WIE) separately |
| Visible Processing | 4-stage pipeline with editable breakpoints |
| LLM as Co-Actor | LLM contribution visible, not hidden |
| Original Language | Processing in user's language until final translation |

### Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Vue 3 Frontend                        │
│            (TypeScript, Composition API, i18n)           │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP/SSE
┌─────────────────────────▼───────────────────────────────┐
│                  Flask DevServer                         │
│         (Orchestration, Pipeline Execution)              │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼──────────┐      ┌───────────▼────────────────┐
│    LLM Providers    │      │   SwarmUI (Port 7801)      │
│  - Ollama (local)   │      │   ┌────────────────────┐   │
│  - OpenRouter       │      │   │     ComfyUI        │   │
│  - AWS Bedrock      │      │   │   (Workflows)      │   │
│  - Mistral          │      │   └────────────────────┘   │
└─────────────────────┘      └────────────────────────────┘
```

---

## 2. Pedagogical Foundation

### The Problem

Generative AI presents three challenges for education:

1. **Black Box**: Users input text, receive output. The process is invisible.
2. **Passivity**: AI becomes wish-fulfillment machine. Humans become commissioners, not creators.
3. **Superficiality**: "Prompt engineering" reduces creativity to keyword optimization.

### The 6 Principles

AI4ArtsEd addresses these through six design principles:

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **WAS/WIE Separation** | Idea (WAS) and rules (WIE) are entered separately. This makes decisions visible. |
| 2 | **LLM as Co-Actor** | The LLM is not a tool but a visible participant. Its contributions are shown, not hidden. |
| 3 | **Critical Exploration** | Systematic experimentation to understand model capabilities and limits. |
| 4 | **Visibility of Processing** | Every step is visible and editable. The "black box" is opened. |
| 5 | **Circularity** | Results become inputs. Iteration, not linear production. |
| 6 | **Pedagogical Guidance** | The platform supports learning processes through accompanying reflection. |

### WAS/WIE in Practice

```
┌─────────────────────────────────────────────────────────┐
│  WAS (Idea)              │  WIE (Rules)                 │
│  "A breakfast table"     │  "From a child's perspective"│
│                          │  "In Bauhaus style"          │
│                          │  "As technical drawing"      │
└─────────────────────────────────────────────────────────┘
                           ↓
              Same idea + different rules = different results
```

The separation makes creative decisions **explicit and learnable**.

---

## 3. Architecture

### Directory Structure

**AI4ArtsEd Development** (`~/ai/ai4artsed_development/`):
```
ai4artsed_development/
├── devserver/                    # Backend
│   ├── my_app/
│   │   ├── routes/              # API endpoints
│   │   │   ├── schema_pipeline_routes.py  # Main orchestration
│   │   │   ├── chat_routes.py             # Träshy chat
│   │   │   ├── training_routes.py         # LoRA training
│   │   │   └── ...
│   │   ├── engine/
│   │   │   └── pipeline_executor.py       # Pipeline execution
│   │   └── services/
│   │       ├── swarmui_manager.py         # Auto-recovery
│   │       └── training_service.py        # LoRA training
│   ├── schemas/
│   │   ├── pipelines/           # Stage 2 pipeline definitions
│   │   ├── chunks/              # Reusable pipeline chunks
│   │   └── configs/
│   │       ├── interception/    # Rule configurations (WIE)
│   │       └── output/          # Output model configs
│   └── config.py                # Centralized configuration
│
├── public/ai4artsed-frontend/   # Frontend
│   ├── src/
│   │   ├── views/               # Page components
│   │   ├── components/          # Reusable components
│   │   └── composables/         # Vue composables
│   └── dist/                    # Built frontend (gitignored)
│
├── docs/                        # Documentation
└── *.sh                         # Startup scripts (1-5)
```

**SwarmUI** (separate installation, `~/ai/SwarmUI/`):
```
SwarmUI/
├── dlbackend/
│   └── ComfyUI/
│       ├── custom_nodes/
│       │   └── ai4artsed_comfyui/    # Custom nodes
│       │       ├── ai4artsed_vector_dimension_eliminator.py
│       │       ├── ai4artsed_t5_clip_fusion.py
│       │       ├── ai4artsed_conditioning_fusion.py
│       │       └── ...
│       └── models/
├── Models/
│   └── Lora/                         # Trained LoRAs go here
└── launch-linux.sh
```

**Important**: SwarmUI is a **separate installation**. Communication via HTTP (Port 7801).

### Core Pattern

**DevServer = Smart Orchestrator | PipelineExecutor = Dumb Engine**

DevServer decides:
- Which stages to execute
- Which LLM for each stage
- Safety level enforcement
- When to translate

PipelineExecutor simply executes what it's told.

---

## 4. The 4-Stage Pipeline

### Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Stage 1   │───▶│   Stage 2   │───▶│   Stage 3   │───▶│   Stage 4   │
│   Safety    │    │ Interception│    │ Optimize +  │    │ Generation  │
│(orig. lang) │    │ (Pädagogik) │    │Translate+Safe│   │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Stage 1: Pre-Interception Safety

**Purpose**: Check user input against §86a safety rules

**Key characteristics**:
- Runs in **original language** (German or English)
- NO translation happens here
- Bilingual safety filter (works in both languages)

**Input**: User's raw idea
**Output**: Safety status (passed/blocked)

**Configurable LLM**: `STAGE1_MODEL` in config.py

### Stage 2: Interception (Pedagogical Transformation)

**Purpose**: Transform user idea according to selected rules

- Combines WAS (idea) with WIE (rules)
- Uses `config.context` (the meta-prompt)
- Model: `STAGE2_INTERCEPTION_MODEL`
- Output: Transformed text in **original language**

**Result is visible and editable** before proceeding.

### Stage 3: Optimization + Translation + Pre-Output Safety

**Purpose**: Prepare prompt for generation

**Three-Phase Execution**:

1. **Optimization** (Model-specific, if needed)
   - Adapts prompt for target generation model
   - Uses `output_config.optimization_instruction`
   - **When applied**: SD3.5 (needs keyword style), video, audio, p5.js
   - **When skipped**: GPT Image, Gemini, QWEN (have strong language models)

2. **Translation**: German → English (generation models need English)

3. **Pre-Output Safety**: Final safety check on translated prompt

**Configurable LLM**: `STAGE3_OPTIMIZATION_MODEL` in config.py

### Stage 4: Media Generation

**Purpose**: Generate final media output

**Input**: English prompt from Stage 3
**Output**: Image, video, audio, or code

**Targets**:
- SwarmUI/ComfyUI (SD3.5, video, audio)
- External APIs (GPT Image, Gemini, QWEN)

---

## 5. Three-Layer Configuration System

### Overview

Trennung von Struktur und Inhalt mit transparenter Ausführung:

```
Layer 3: CONFIGS (34+ JSON files)
    "Inhalt: Was soll transformiert werden"
    ↓ references
Layer 2: PIPELINES (4 core definitions)
    "Struktur: Wie wird orchestriert"
    ↓ uses
Layer 1: CHUNKS (3 primitives)
    "Abstraktion: Transparente atomare Operationen"
```

**Prinzip**: Configs definieren den Inhalt (Regeln, Kontext), Pipelines definieren die Struktur (Ablauf), Chunks ermöglichen Transparenz in der Ausführung.

### Layer 1: Chunks

**Location**: `devserver/schemas/chunks/`

Atomic operations with template-based prompts:

```json
{
  "name": "manipulate",
  "type": "processing_chunk",
  "template": "{{INSTRUCTION}}\n\nText:\n{{PREVIOUS_OUTPUT}}",
  "backend_type": "ollama",
  "model": "STAGE2_INTERCEPTION_MODEL"
}
```

**Placeholders**:
- `{{INSTRUCTION}}` - From config.context
- `{{INPUT_TEXT}}` - Original user input
- `{{PREVIOUS_OUTPUT}}` - Output from previous chunk

### Layer 2: Pipelines

**Location**: `devserver/schemas/pipelines/`

Define structural flow based on INPUT requirements:

| Pipeline | Input | Description |
|----------|-------|-------------|
| `text_transformation` | 1 text | Standard transformation |
| `image_transformation` | 1 image + text | Image-based transformation |
| `multi_image` | 3 images + text | Multi-image fusion |

```json
{
  "name": "text_transformation",
  "input_requirements": {"texts": 1},
  "chunks": ["manipulate"],
  "meta": {"workflow_type": "standard"}
}
```

### Layer 3: Configs (Interception Rules)

**Location**: `devserver/schemas/configs/interception/`

User-facing configurations with complete instruction content:

```json
{
  "id": "bauhaus",
  "name": {"de": "Bauhaus", "en": "Bauhaus"},
  "description": {"de": "Reduziert auf geometrische Formen..."},
  "context": "Du bist ein Künstler im Geiste des Bauhaus...",
  "category": "art_history",
  "meta": {
    "loras": [{"name": "bauhaus.safetensors", "strength": 0.6}]
  }
}
```

---

## 6. Frontend (Vue 3)

### Lab Paradigm

The frontend orchestrates the pipeline flow using atomic backend services:

```typescript
// Step 1: Run Stage 1+2
const interceptionResult = await fetch('/api/schema/pipeline/stage2', {
  method: 'POST',
  body: JSON.stringify({ schema: 'bauhaus', input_text: userInput })
});

// User can edit the result here...

// Step 2: Run Stage 3+4
const generationResult = await fetch('/api/schema/pipeline/stage3-4', {
  method: 'POST',
  body: JSON.stringify({ prompt: editedPrompt, output_config: 'sd35_large' })
});
```

### Key Views

| View | Route | Purpose |
|------|-------|---------|
| `PropertyQuadrantsView.vue` | `/select` | Rule selection (start page) |
| `text_transformation.vue` | `/text-transformation` | Text mode |
| `image_transformation.vue` | `/image-transformation` | Image mode |
| `multi_image_transformation.vue` | `/multi-image-transformation` | Multi-image mode |
| `surrealizer.vue` | `/surrealizer` | T5-CLIP interpolation |
| `split_and_combine.vue` | `/split-and-combine` | Vector fusion |
| `partial_elimination.vue` | `/partial-elimination` | Dimension elimination |
| `TrainingView.vue` | `/training` | LoRA training |

### Naming Convention

Vue components for pipelines named EXACTLY after the pipeline:
```
Pipeline: text_transformation → Vue: text_transformation.vue
```

---

## 7. Backend (Flask/DevServer)

### Blueprint Structure

| Blueprint | URL Prefix | Purpose |
|-----------|-----------|---------|
| `schema_bp` | `/api/schema` | Pipeline orchestration |
| `chat_bp` | `/api/chat` | Träshy assistant |
| `media_bp` | `/api/media` | Media delivery |
| `settings_bp` | `/api/settings` | Settings |
| `training_bp` | (root) | LoRA training |

### Centralized Configuration

All models configured in `devserver/config.py`:

```python
STAGE1_MODEL = "llama-guard-3-8b"
STAGE2_INTERCEPTION_MODEL = "mistral-nemo"
STAGE3_OPTIMIZATION_MODEL = "qwen2.5:14b"
```

### Request Queueing

Concurrent LLM requests limited:
```python
_llm_semaphore = threading.Semaphore(3)  # Max 3 concurrent
```

Queue status streamed to frontend (red spinner feedback).

### Safety System

| Level | Age | Description |
|-------|-----|-------------|
| `kids` | 8-12 | Most restricted |
| `youth` | 12-17 | Default |
| `open` | 18+ | Least restricted |

Safety NOT configurable by users. Set by educator.

---

## 8. SwarmUI/ComfyUI Integration

### Architecture

```
DevServer ──HTTP──▶ SwarmUI (7801) ──▶ ComfyUI (7821)
     │                    │
     │              Auto-Recovery
     │                    │
     ▼                    ▼
SwarmUIManager     Health Checks
 (Singleton)       (Dual-port)
```

### Auto-Recovery System

**Pattern**: Lazy Recovery (Start only when needed)

```python
class SwarmUIManager:
    async def ensure_swarmui_available(self):
        if await self.is_healthy():
            return True
        async with self._lock:  # Prevent race conditions
            return await self._start_and_wait()
```

**Health Checks**:
- Port 7801: SwarmUI REST API
- Port 7821: ComfyUI backend

**Timeout**: 120 seconds with 2-second polling

### Custom ComfyUI Nodes

**Location**: `~/ai/SwarmUI/dlbackend/ComfyUI/custom_nodes/ai4artsed_comfyui/`

| Node | Purpose |
|------|---------|
| `ai4artsed_vector_dimension_eliminator.py` | Partial Elimination |
| `ai4artsed_t5_clip_fusion.py` | Surrealizer (dual-encoder) |
| `ai4artsed_conditioning_fusion.py` | Split & Combine |

### Experimental Workflows

| Workflow | Description |
|----------|-------------|
| Surrealizer | Mix CLIP and T5 embeddings |
| Split & Combine | Separate and recombine concepts |
| Partial Elimination | Zero out embedding dimensions |

---

## 9. LLM Providers

### Supported Providers

| Provider | Use Case | Local/Cloud |
|----------|----------|-------------|
| Ollama | Fast, private | Local |
| OpenRouter | Many models | Cloud |
| AWS Bedrock | Enterprise | Cloud |
| Mistral | European | Cloud |

### Configuration

```python
# config.py
OLLAMA_BASE_URL = "http://localhost:11434"
OPENROUTER_API_KEY = "..."  # From .key file
```

---

## 10. LoRA Training Studio

### Overview

Users can train custom LoRA models directly in AI4ArtsEd.

### Training Flow

1. **Upload**: 5-20 training images
2. **Configure**: Name, trigger word, epochs (4-8)
3. **VRAM Check**: Unload SD3.5 if needed (~18GB required)
4. **Training**: Kohya-ss backend with progress streaming
5. **Output**: LoRA in `SwarmUI/Models/Lora/`

### Config-Based LoRA Injection

LoRAs associated with interception configs:

```json
{
  "id": "cooked_negatives",
  "meta": {
    "loras": [
      {"name": "cooked_negatives.safetensors", "strength": 0.6}
    ]
  }
}
```

Automatically injected during Stage 4.

### Best Practices

- **Epoch 4**: Less overfitting, lighter style
- **Epoch 6**: Balanced (default)
- **Strength 0.6**: Good starting point
- Higher strength = more style, less prompt adherence

---

## 11. Additional Features

### AI-Origin Disclosure (EU AI Act Art. 50 Compliance)

**Status: planned / in implementation.** This section describes the target design, not an existing feature. A previous attempt (Session 118, January 2026) was reverted; see `docs/sessions/FAILED_SESSION_118_WATERMARK_ATTEMPT.md` for the post-mortem.

The platform addresses the upcoming legal requirement under EU AI Act Article 50 to mark AI-generated visual content in a **machine-readable format**. Because the platform is deployed by arbitrary educational providers, the design is deliberately **vendor-neutral**: it does not embed a "AI4ArtsEd" or any other provider brand. Operators are responsible for their own compliance; the platform supplies the default mechanics.

**Two layers, separately configurable:**

1. **Machine-readable metadata (default ON, the compliance core)**
   - Images: PNG `iTXt` chunks / JPEG XMP, including `XMP-iptcExt:DigitalSourceType=trainedAlgorithmicMedia` (the ISO/IPTC-standard marker for AI-generated content), `CreateDate`, model name, and optionally prompt hash and seed.
   - Videos: MP4 container metadata (`creation_time`, `description="AI-generated, model=…"`) via ffmpeg, no re-encode required.
   - Prompt itself is **not** embedded by default (workshop prompts may be personal data — opt-in only).

2. **Visible mark (default OFF, optional per deployment)**
   - Configurable text (default: "AI-generated"), corner position, opacity.
   - Implemented via Pillow for images and ffmpeg `drawtext` for videos.
   - Operators who want a visible KI-Hinweis can enable it; those who only need legal disclosure rely on layer 1.

**Configuration** lives in `user_settings.json` under the `watermark` key. **Implementation location** (planned): `devserver/my_app/services/watermark_service.py`, hooked into `pipeline_recorder.save_entity()` so all generation paths (Diffusers, ComfyUI, OpenAI Images, Mammouth) are covered uniformly.

C2PA Content Credentials are not part of this design.

### SSE Text Streaming

Stage 2 transformation results stream in real-time with a typewriter effect.

**Implementation**:
```typescript
// Frontend uses EventSource
const eventSource = new EventSource('/api/schema/pipeline/stage2/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'token') {
    displayedText.value += data.content;  // Typewriter effect
  }
};
```

**Benefits**:
- Visual feedback during LLM processing
- Red spinner indicates queue position (request queueing active)
- Progressive disclosure of transformation result

### Export Functionality

Session results exportable in multiple formats:

| Format | Content | Use Case |
|--------|---------|----------|
| **JSON** | Complete session data | Programmatic access, backup |
| **PDF** | Formatted report with images | Documentation, portfolios |
| **ZIP** | All files bundled | Complete archive |

**Export Location**: `/run_data/{run_id}/exports/`

**API**:
```
GET /api/media/export/{run_id}?format=pdf
GET /api/media/export/{run_id}?format=json
GET /api/media/export/{run_id}?format=zip
```

### Icon System (Material Design)

**Migration (Session 117)**: Emoji icons replaced with Material Design SVG icons.

**Principles**:
- Consistent visual language across all views
- Scalable vector graphics (no pixelation)
- Semantic naming (e.g., `mdi-image-filter-drama` for creative transformation)
- Color theming via CSS variables

**Component Location**: `src/components/icons/`

**Usage**:
```vue
<template>
  <MaterialIcon name="transform" size="24" class="text-primary" />
</template>
```

---

## 12. API Reference

### Pipeline Endpoints (Lab Atomic Services)

| Endpoint | Stages | Purpose |
|----------|--------|---------|
| `POST /api/schema/pipeline/stage2` | 1+2 | Safety + Interception |
| `POST /api/schema/pipeline/stage3-4` | 3+4 | Translate + Generate |
| `POST /api/schema/pipeline/generation` | 4 | Direct generation |
| `POST /api/schema/pipeline/legacy` | 1+4 | Experimental workflows |
| `GET /api/schema/schemas` | - | List configs |

### Stage 2 Request

```json
{
  "schema": "bauhaus",
  "input_text": "Eine Blume auf der Wiese",
  "safety_level": "youth",
  "run_id": "uuid"
}
```

### Stage 3-4 Request

```json
{
  "prompt": "Im Geiste des Bauhauses...",
  "output_config": "sd35_large",
  "safety_level": "youth",
  "run_id": "uuid-from-stage2"
}
```

### Media Endpoints

- `GET /api/media/image/{run_id}`
- `GET /api/media/video/{run_id}`
- `GET /api/media/audio/{run_id}`
- `GET /api/media/p5/{run_id}`

### Chat Endpoint

```json
POST /api/chat
{
  "message": "Was ist Interception?",
  "history": []
}
```

---

## 13. Deployment

### Development

```bash
# Terminal 1: Backend
cd devserver && python run.py  # Port 17802

# Terminal 2: Frontend
cd public/ai4artsed-frontend && npm run dev  # Port 5173

# Terminal 3: SwarmUI (separate directory!)
cd ~/ai/SwarmUI && ./launch-linux.sh --launch_mode none  # Port 7801
```

### Production

```bash
# Build frontend
cd public/ai4artsed-frontend && npm run build

# Start with production port
export PORT=17801
python run.py
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 17802 | DevServer port |
| `OLLAMA_BASE_URL` | localhost:11434 | Ollama endpoint |
| `SWARMUI_HOST` | localhost | SwarmUI host |
| `SWARMUI_PORT` | 7801 | SwarmUI port |

---

## 14. Development Guide

### Adding a New Interception Config

1. Create JSON in `devserver/schemas/configs/interception/`
2. Include: id, name (de/en), description (de/en), context, category
3. Restart DevServer
4. Appears on start page automatically

### Adding a New Output Model

1. Configure workflow in SwarmUI
2. Create config in `devserver/schemas/configs/output/`
3. Test with various prompts

### Code Style

- Python: Black formatter, type hints
- TypeScript: ESLint, Prettier
- Vue: Composition API, `<script setup>`

### Testing

```bash
cd public/ai4artsed-frontend
npm run type-check  # MANDATORY before commits
```

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **WAS** | User's idea (WHAT to transform) |
| **WIE** | Rules/meta-prompt (HOW to transform) |
| **Interception** | Stage 2 - combining WAS + WIE |
| **Co-Actor** | LLM as visible participant |
| **Breakpoint** | Point where user can edit |
| **Config** | Rule set for transformation |

---

## Appendix B: File Reference

| Need to... | Look in... |
|------------|------------|
| Add a rule | `devserver/schemas/configs/interception/` |
| Add output model | `devserver/schemas/configs/output/` |
| Change LLM | `devserver/config.py` |
| Edit pipeline logic | `my_app/routes/schema_pipeline_routes.py` |
| Add ComfyUI node | `~/ai/SwarmUI/dlbackend/ComfyUI/custom_nodes/ai4artsed_comfyui/` |

---

## Appendix C: Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-18 | Initial version |
| 2.0 | 2026-01-20 | Complete rewrite: correct stage flow, Lab paradigm, Three-Layer system |
| 2.1 | 2026-01-21 | Added Pedagogical Foundation (6 Principles), Section 11 (Additional Features), fixed Stage 3 description, updated diagrams |

---

*This whitepaper reflects the architecture as of January 2026. For authoritative details, see `docs/ARCHITECTURE PART 01-24.md`.*

---

<sub>This documentation was automatically generated by Claude Code during the Documentation Marathon (Session 126, January 2026).</sub>
