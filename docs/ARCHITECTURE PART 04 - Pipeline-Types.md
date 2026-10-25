# DevServer Architecture

**Part 4: Pipeline Types**

---


### 1. Text Transformation Pipeline

**Purpose:** Transform text according to specific instructions
**Input:** One text prompt
**Output:** Transformed text
**Pipeline:** `text_transformation`

**Data Flow:**
```
User Input → Config (e.g., dada.json)
  → text_transformation Pipeline
    → manipulate Chunk
      → Ollama LLM
        → Optimized Text
```

**Use Cases:**
- Artistic transformations (Dadaism, Bauhaus, Renaissance)
- Translation (with specific cultural preservation)
- Style modifications (Youth Slang, Overdrive, PigLatin)
- Prompt optimization (for downstream media generation)

---

### 2. Single Prompt Generation Pipeline

**Purpose:** Generate media from one text prompt
**Input:** One text prompt
**Output:** Image, Audio, Music, or Video
**Pipeline:** `single_text_media_generation`

**Data Flow:**
```
Text Prompt → Config (e.g., sd35_large.json)
  → single_text_media_generation Pipeline
    → Proxy-Chunk (output_image.json)
      → Backend Router (loads OUTPUT_CHUNK from config)
        → Specialized Output-Chunk (output_image_sd35_large.json)
          → ComfyUI API OR OpenRouter API
            → Media Output (Image/Audio/etc.)
```

**Use Cases:**
- Image generation (SD3.5, Flux1, DALL-E)
- Audio generation (Stable Audio)
- Music generation (simple single-prompt models)
- Video generation (future)

**Backend Flexibility:**
- Same pipeline works with ComfyUI (local) or OpenRouter (cloud)
- Config determines backend via `meta.backend` field

---

### 3. Dual Prompt Generation Pipeline

**Purpose:** Generate media from two text prompts
**Input:** Two text prompts (e.g., Tags + Lyrics)
**Output:** Music
**Pipeline:** `dual_text_media_generation`

**Data Flow:**
```
Prompt 1 (Tags) + Prompt 2 (Lyrics) → Config (acestep_standard.json)
  → dual_text_media_generation Pipeline
    → Backend Router
      → ComfyUI AceStep Workflow
        → input_mapping: prompt_1 → tags_node, prompt_2 → lyrics_node
          → Music Output (WAV)
```

**Config input_mapping:**
```json
{
  "input_mapping": {
    "prompt_1": "tags_node",     // Maps to ComfyUI Node ID
    "prompt_2": "lyrics_node"    // Maps to ComfyUI Node ID
  }
}
```

**Use Cases:**
- AceStep music generation (Tags + Lyrics)
- Future: Other multi-input scenarios

---

### 4. Image Plus Text Generation Pipeline

**Purpose:** Generate/modify image using input image + text
**Input:** Image file + Text prompt
**Output:** Modified image
**Pipeline:** `image_text_media_generation`

**Data Flow:**
```
Input Image + Text Prompt → Config (inpainting_sd35.json)
  → image_text_media_generation Pipeline
    → Backend Router
      → ComfyUI Inpainting Workflow
        → image → image_node, text → prompt_node
          → Modified Image Output
```

**Use Cases (Future):**
- Inpainting (modify parts of an image)
- Image-to-Image (transform existing image)
- ControlNet (structure-guided generation)
- Style Transfer

**Status:** Pipeline exists, configs not yet implemented

---


## Pipeline Structure Metadata (Phase 2 Dynamic UI)

**Added:** 2025-11-08
**Purpose:** Enable frontend to dynamically render appropriate UI based on pipeline structure

All pipelines now expose structural metadata that describes their input/output requirements:

### Metadata Fields

```json
{
  "pipeline_type": "prompt_interception",
  "pipeline_stage": "2",
  "requires_interception_prompt": true,
  "input_requirements": {
    "texts": 1,
    "images": 0
  }
}
```

### Field Descriptions

**`pipeline_type`** (string, optional)
- Semantic classification of pipeline
- Examples: `"prompt_interception"`, `"media_generation"`, `"multi_prompt"`, `"music_generation"`
- Used for UI adaptation and categorization

**`pipeline_stage`** (string, optional)
- Which stage of 4-Stage Pre-Interception system
- Values: `"1"`, `"2"`, `"3"`, `"4"`
- Stage 2: Interception/Transformation
- Stage 4: Output/Media Generation

**`requires_interception_prompt`** (boolean, default: false)
- Whether this pipeline uses a meta-prompt/context for transformation
- `true`: Show context editing bubble in Phase 2 UI
- `false`: Hide context bubble (pure media generation)

**`input_requirements`** (object, optional)
- Specifies how many inputs of each type the pipeline needs
- `{"texts": N, "images": M}`
- Frontend renders N text input bubbles, M image upload components

### Examples by Pipeline Type

**Text Transformation (Stage 2 Interception):**
```json
{
  "name": "text_transformation",
  "pipeline_type": "prompt_interception",
  "pipeline_stage": "2",
  "requires_interception_prompt": true,
  "input_requirements": {"texts": 1}
}
```
- Phase 2 UI: 1 text input + 1 context bubble

**Music Generation (Multi-Prompt):**
```json
{
  "name": "music_generation",
  "pipeline_type": "music_generation",
  "pipeline_stage": "2",
  "requires_interception_prompt": false,
  "input_requirements": {"texts": 2}
}
```
- Phase 2 UI: 2 text inputs (Tags + Lyrics), no context bubble

**Single Text Media Generation (Stage 4 Output):**
```json
{
  "name": "single_text_media_generation",
  "pipeline_type": "single_text_media_generation",
  "pipeline_stage": "4",
  "requires_interception_prompt": false,
  "input_requirements": {"texts": 1}
}
```
- Phase 2 UI: 1 text input, no context bubble

**Future: Image+Text Pipeline:**
```json
{
  "name": "image_text_media_generation",
  "pipeline_type": "inpainting",
  "pipeline_stage": "4",
  "requires_interception_prompt": false,
  "input_requirements": {"texts": 1, "images": 1}
}
```
- Phase 2 UI: 1 text input + 1 image upload, no context bubble

### Backend Implementation

**Pipeline Dataclass** (`schemas/engine/config_loader.py`):
```python
@dataclass
class Pipeline:
    name: str
    description: str
    chunks: List[str]
    
    # Phase 2: Pipeline structure metadata
    pipeline_type: Optional[str] = None
    pipeline_stage: Optional[str] = None
    requires_interception_prompt: bool = False
    input_requirements: Optional[Dict[str, int]] = None
```

**API Endpoint:**
```
GET /api/config/<config_id>/pipeline

Returns:
{
  "config_id": "dada",
  "pipeline_name": "text_transformation",
  "pipeline_type": "prompt_interception",
  "pipeline_stage": "2",
  "requires_interception_prompt": true,
  "input_requirements": {"texts": 1},
  "description": "Text Transformation Pipeline..."
}
```

### Frontend Integration

Phase 2 UI dynamically renders components based on `input_requirements`:

```typescript
// Fetch pipeline metadata
const metadata = await getPipelineMetadata(configId)

// Render N text input bubbles
for (let i = 0; i < metadata.input_requirements.texts; i++) {
  renderTextInputBubble(i)
}

// Show context bubble only if required
if (metadata.requires_interception_prompt) {
  renderContextBubble()
}
```

### Current Pipeline Summary

| Pipeline | Stage | Context | Input | Description |
|----------|-------|---------|-------|-------------|
| `text_transformation` | 2 | ✅ | 1 text | Interception (Dada, Bauhaus, etc.) |
| `text_transformation_recursive` | 2 | ✅ | 1 text | Recursive Interception (Stille Post) |
| `music_generation` | 2 | ❌ | **2 texts** | Multi-prompt (Tags + Lyrics) |
| `single_text_media_generation` | 4 | ❌ | 1 text | Direct media output |
| `image_generation` | 4 | ❌ | 1 text | Image generation |
| `video_generation` | 4 | ❌ | 1 text | Video generation |

### Pedagogical Benefits

**Flexibility:**
- System can handle future pipelines with complex input structures
- No hardcoded UI assumptions about "one text input + context"
- Supports split-prompts, vector operations, multi-modal inputs

**Transparency:**
- Pipeline structure is explicit, not hidden
- Students/teachers understand what inputs are required
- Educational: Different AI approaches need different inputs

**Extensibility:**
- New pipeline types can be added without frontend changes
- `input_requirements` can be extended: `{"texts": 2, "images": 1, "audio": 1}`
- Frontend automatically adapts to new structures

---
