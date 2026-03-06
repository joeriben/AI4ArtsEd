# DevServer Architecture

**Part 5: Pipeline → Chunk → Backend Routing**

---


### How Media Generation Works

**Key Concept:** Output-Pipelines (single_text_media_generation, dual_text_media_generation) are **backend-agnostic** and **media-agnostic**. They determine the right execution path based on:

1. **Config metadata** (`media_preferences.default_output`)
2. **Execution mode** (eco vs fast)
3. **Available backends** (local vs remote)

---

### Step-by-Step Routing Logic

#### Example: User generates an image using Dada + SD3.5

**Step 1: Text Transformation (Pre-Pipeline)**
```python
# User selects: Config "Dada" + Input "A red apple"
config = load_config("dada.json")
# → pipeline: "text_transformation"
# → context: "You are an artist working in the spirit of Dadaism..."

result = execute_pipeline(
    pipeline="text_transformation",
    chunks=["manipulate"],
    context="You are an artist working in Dadaism...",
    input_text="A red apple"
)
# → Output: "Ein roter Apfel in dadaistischer Ästhetik mit fragmentierter Form..."
```

**Step 2: Media Generation (Output-Pipeline)**
```python
# User clicks "Generate Image" → Server calls output-pipeline
config = load_config("sd35_standard.json")  # Or user-selected image config
# → pipeline: "single_text_media_generation"
# → media_preferences.default_output: "image"
# → meta.model: "sd3.5_large"
# → parameters: {cfg: 5.5, steps: 20, ...}

# Pipeline determines media_type from config
media_type = config.media_preferences.default_output  # "image"

# Pipeline checks execution mode
execution_mode = get_execution_mode()  # "eco" or "fast" (from frontend or server default)

# Pipeline routes to appropriate chunk
if execution_mode == "eco":
    chunk = select_chunk_for_local_generation(media_type)
    # → For "image": comfyui_image_generation
    # → For "audio": comfyui_audio_generation
    # → For "music": comfyui_music_generation
elif execution_mode == "fast":
    chunk = select_chunk_for_remote_generation(media_type)
    # → For "image": openrouter_image_generation (GPT-5)
    # → For "audio": fallback to local (no remote API yet)
    # → For "music": fallback to local (no remote API yet)

# Execute chunk
result = execute_chunk(
    chunk=chunk,
    input_text="Ein roter Apfel in dadaistischer Ästhetik...",
    config_params=config.parameters
)
# → ComfyUI generates image using SD3.5 Large workflow
# → Returns: prompt_id for polling
```

---

### Output-Config Selection Matrix

Server selects OUTPUT-CONFIGS (not chunks directly) using `output_config_defaults.json`:

| Media Type | eco Mode Config | fast Mode Config | Status |
|------------|-----------------|------------------|--------|
| **image** | `sd35_large` | `flux1_openrouter` | eco: ✅, fast: Planned |
| **audio** | `stable_audio` | `(fallback to eco)` | eco: ✅, fast: Not available |
| **music** | `acestep` | `(fallback to eco)` | eco: ✅, fast: Not available |
| **video** | `animatediff` | `sora2` | eco: Planned, fast: Planned |
| **3d** | `hunyuan3d_text_to_3d` | `(no remote)` | eco: ✅, fast: Not available |

**Implementation:** `schemas/output_config_defaults.json`

**Important:** Server selects CONFIGS, configs specify CHUNKS via OUTPUT_CHUNK parameter:
1. Server reads Interception-Config's `media_preferences.default_output` (e.g., "image")
2. Server reads `execution_mode` (eco/fast)
3. Server looks up `output_config_defaults["image"]["eco"]` → "sd35_large"
4. Server executes Output-Pipeline with config "sd35_large"
5. Config has `"OUTPUT_CHUNK": "output_image_sd35_large"`
6. Proxy-Chunk (output_image.json) receives this parameter
7. backend_router loads specialized Output-Chunk
8. Output-Chunk contains execution logic (ComfyUI workflow OR Python code)

---

### Output-Chunk Naming Convention

Output-Chunks are **highly specialized** for specific backend+model combinations:

**Format:** `output_[media]_[model]_[variant]`

**Examples:**
- ✅ `output_image_sd35_large` - SD3.5 Large via ComfyUI
- ✅ `output_image_gpt5` - GPT-5 Image via OpenRouter
- ✅ `output_audio_stable_audio` - Stable Audio via ComfyUI
- ✅ `output_music_acestep` - AceStep via ComfyUI

**NOT Config-Level Terms:**
- ❌ `output_image_sd35_standard` - "standard" is config concept, not chunk!

**Each Output-Chunk contains:**
- **JSON Chunks (.json):** Complete ComfyUI workflow + input_mappings + output_mapping
- **Python Chunks (.py):** execute() function with type-safe parameters
- Both types contain complete backend-specific execution logic

**Backend Type for Python Chunks:**
- ALL Python chunks use `backend_type='python'` (generic)
- Chunk name determines specific implementation (e.g., `output_music_heartmula`)
- No per-backend enum entries needed
- See ARCHITECTURE PART 03 for Python chunk pattern details

---

### Config → Pipeline → Chunk Example

**Config: stableaudio.json**
```json
{
  "pipeline": "single_text_media_generation",
  "media_preferences": {
    "default_output": "audio",
    "supported_types": ["audio"]
  },
  "meta": {
    "model": "stable_audio_open",
    "duration_seconds": 47
  },
  "parameters": {
    "cfg": 7.0,
    "steps": 100
  }
}
```

**Pipeline: single_text_media_generation.json**
```json
{
  "name": "single_text_media_generation",
  "description": "Single text → Media (image/audio/video)",
  "chunks": ["output_image"],
  "meta": {
    "input_type": "single_text",
    "output_types": ["image", "audio", "music", "video"],
    "backend_agnostic": true,
    "note": "Uses Proxy-Chunk system - NO manipulate (Output-Pipeline is primitive!)"
  }
}
```

**Key Design: Proxy-Chunk System**

Output-Pipeline uses a **Proxy-Chunk** (`output_image.json`) that delegates to specialized Output-Chunks:

**Proxy-Chunk: output_image.json**
```json
{
  "name": "output_image",
  "type": "processing_chunk",
  "backend_type": "comfyui",
  "template": "",
  "model": "",
  "parameters": {
    "output_chunk": "{{OUTPUT_CHUNK}}",
    "prompt": "{{PREVIOUS_OUTPUT}}",
    "negative_prompt": "{{NEGATIVE_PROMPT}}",
    "width": "{{WIDTH}}",
    "height": "{{HEIGHT}}"
  }
}
```

**Config Selection (Runtime):**
```python
# Server determines OUTPUT-CONFIG based on media_type + execution_mode
# Using output_config_defaults.json

media_type = interception_config.media_preferences.default_output  # "image"
execution_mode = "eco"  # From frontend or server default

# Lookup in output_config_defaults.json
output_config_name = output_config_defaults[media_type][execution_mode]
# → "sd35_large"

# Execute Output-Pipeline with selected config
result = executor.execute_pipeline(
    config_name="sd35_large",  # Output-Config
    input_text=transformed_text
)
```

**Output-Config: sd35_large.json**
```json
{
  "pipeline": "single_text_media_generation",
  "parameters": {
    "OUTPUT_CHUNK": "output_image_sd35_large",  // Specialized chunk
    "WIDTH": 1024,
    "HEIGHT": 1024,
    "STEPS": 25
  }
}
```

**Specialized Output-Chunk: output_image_sd35_large.json**
```json
{
  "name": "output_image_sd35_large",
  "type": "output_chunk",
  "backend_type": "comfyui",
  "media_type": "image",
  "workflow": {
    // Complete ComfyUI API workflow (11 nodes)
    // See Output-Chunk section for full structure
  },
  "input_mappings": {
    "prompt": {"node_id": "10", "field": "inputs.value", ...},
    "negative_prompt": {"node_id": "11", ...}
  }
}
```

---

### Why This Architecture?

**1. Backend Transparency:**
- Same pipeline `single_text_media_generation` works with any backend
- ComfyUI can be replaced with SwarmUI, Replicate, etc. without changing pipelines

**2. Media Transparency:**
- Pipeline doesn't care if output is image, audio, or video
- Differentiation happens at chunk selection (runtime)

**3. Easy Extension:**
- Add new media type (e.g., "3d_model")? → Create new chunk, no pipeline changes
- Add new backend (e.g., Replicate)? → Create new chunk, no pipeline changes

**4. Pedagogical Flexibility:**
- Teachers can switch between eco (free, slow) and fast (paid, fast) without changing workflows
- Students see same interface regardless of backend

---

