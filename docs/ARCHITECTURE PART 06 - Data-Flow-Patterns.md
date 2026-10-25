# DevServer Architecture

**Part 6: Data Flow Patterns**

---


### Pattern 1: Text-Only Transformation

```
User Input: "A surreal dream"
  ↓
Config: dada.json (pipeline: text_transformation)
  ↓
Pipeline: text_transformation
  ↓
Chunk: manipulate (with Dadaism instruction)
  ↓
Ollama LLM: mistral-nemo (eco mode) or claude-3.5-haiku (fast mode)
  ↓
Output: "Ein surrealistischer Traum in dadaistischer Ästhetik mit absurden juxtapositionen..."
```

---

### Pattern 2: Text → Optimized Text → Image

```
Step 1 (Text Transformation):
  User Input: "A red apple"
    ↓
  Config: dada.json
    ↓
  Output: "Ein roter Apfel in dadaistischer Ästhetik mit fragmentierter Form..."

Step 2 (Media Generation):
  Optimized Text: "Ein roter Apfel in dadaistischer..."
    ↓
  Config: sd35_standard.json (pipeline: single_text_media_generation)
    ↓
  Backend Router: ComfyUI
    ↓
  Workflow: sd35_standard (Dual CLIP: clip_g + t5xxl, CFG:5.5, Steps:20)
    ↓
  Output: Image (PNG)
```

**Server Orchestration:**
```python
# Step 1
result1 = executor.execute_pipeline(
    config_name="dada",
    input_text="A red apple"
)
optimized_text = result1.final_output

# Step 2
result2 = executor.execute_pipeline(
    config_name="sd35_standard",
    input_text=optimized_text
)
image_prompt_id = result2.media_output.prompt_id
```

---

### Pattern 3: Direct Media Generation (No Text Optimization)

```
User Input: "A red apple on a wooden table"
  ↓
Config: sd35_standard.json (pipeline: single_text_media_generation)
  ↓
Backend Router: ComfyUI
  ↓
Workflow: sd35_standard
  ↓
Output: Image (PNG)
```

---

### Pattern 4: Dual Prompt → Music

```
User provides:
  - Tags: "upbeat, electronic, 120bpm"
  - Lyrics: "Dancing through the night, feeling so alive..."
    ↓
Config: acestep_standard.json (pipeline: dual_text_media_generation)
  ↓
Backend Router: ComfyUI
  ↓
Workflow: acestep_music
  ↓
Input Mapping:
  - prompt_1 (Tags) → Node 123 (tags input)
  - prompt_2 (Lyrics) → Node 456 (lyrics input)
  ↓
Output: Music (WAV, 47 seconds)
```

---

### Pattern 5: Auto-Media Generation (Text Transformation + Auto Output)

**Purpose:** Text transformation configs (like dada.json) can suggest a media type for automatic media generation after text transformation completes.

**Architecture Principle:** **Separation of Concerns**
- Pre-pipeline configs (dada.json) suggest media type via `media_preferences.default_output`
- Pre-pipeline configs DO NOT choose specific models or output configs
- DevServer uses a central `output_config_defaults.json` to map media types to output configs

**Data Flow:**
```
User Input: "A surreal dream"
  ↓
Config: dada.json (pipeline: text_transformation)
  media_preferences.default_output = "image"
  ↓
Pipeline: text_transformation
  ↓
Output: "Ein surrealistischer Traum in dadaistischer Ästhetik..."
  ↓
DevServer Auto-Media Logic:
  1. Read: config.media_preferences.default_output = "image"
  2. Read: execution_mode = "eco"
  3. Lookup: output_config_defaults["image"]["eco"] → "sd35_large"
  4. Execute: single_text_media_generation pipeline with sd35_large config
  ↓
Output: Image (PNG) generated via SD3.5 Large
```

**output_config_defaults.json Structure:**
```json
{
  "image": {
    "eco": "sd35_large",
    "fast": "flux1_openrouter"
  },
  "audio": {
    "eco": "stable_audio",
    "fast": "stable_audio_api"
  },
  "music": {
    "eco": "acestep",
    "fast": null
  },
  "video": {
    "eco": "animatediff",
    "fast": null
  }
}
```

**Why This Architecture:**

1. **Separation of Concerns:** Text manipulation configs don't know about specific models
2. **Centralized Defaults:** One file defines system-wide output defaults
3. **Easy Maintenance:** Change default image model by editing one line
4. **Pedagogically Clear:** Dada says "I produce visual content" not "I use SD3.5 Large"
5. **Execution Mode Aware:** Different defaults for eco (local) vs fast (cloud)

**User Override Options:**

Users can override the auto-media generation:
- `#image#` tag in input → force image generation
- `#audio#` tag → force audio generation
- `#music#` tag → force music generation
- `#video#` tag → force video generation
- No tag + `default_output = "text"` → no auto-media, return text only

**Implementation Location:**
- File: `schemas/output_config_defaults.json`
- Loader: `my_app/routes/schema_pipeline_routes.py` (`load_output_config_defaults`, `lookup_output_config`; the engine twin `schemas/engine/output_config_selector.py` had no caller and was removed 2026-10-10)
- Usage: `my_app/routes/schema_pipeline_routes.py` (auto-media generation logic)
- API Endpoint: `/api/schema/pipeline/execute`
- Note: Replaced deprecated `workflow_routes.py` as of 2025-10-28

**DevServer Media Awareness:**

DevServer tracks expected output types throughout execution:

```python
# ExecutionContext tracks media generation
class ExecutionContext:
    config_name: str
    execution_mode: str
    expected_media_type: str  # "image", "audio", "music", "video", "text"
    generated_media: List[MediaOutput]  # Collect all media generated
    text_outputs: List[str]  # Track text at each step

@dataclass
class MediaOutput:
    media_type: str  # From Output-Chunk
    prompt_id: str   # ComfyUI queue ID
    output_mapping: dict  # How to extract media
    config_name: str  # Which output config was used
    status: str  # "queued", "generating", "completed", "failed"
```

**Why DevServer Needs Awareness:**
1. **Media Collection** - Track all media in multi-step processes
2. **Presentation Logic** - Format response based on media type
3. **Pipeline Chaining** - Reuse context for additional generations
4. **Error Handling** - Different validation per media type
5. **Frontend Communication** - Tell UI what to expect/display

**Data Flow with Awareness:**
```
1. schema_pipeline_routes.py receives request at /api/schema/pipeline/execute
2. Loads config → reads media_preferences.default_output
3. Executes Interception-Pipeline (text transformation)
4. Auto-Media Detection: checks if media output requested
5. Looks up Output-Config via output_config_defaults.json
6. Loads Output-Config → reads OUTPUT_CHUNK parameter
7. Executes Output-Pipeline with transformed text
8. Loads Output-Chunk → reads media_type field
9. Submits workflow to ComfyUI (or API backend)
10. Returns response with final_output (text) + media_output (prompt_id)
```

---

