# DevServer Architecture

**Part 3: Three-Layer System**

---


### Layer 1: Chunks (Primitives)

**Purpose:** Atomic operations with template-based prompts
**Location:** `schemas/chunks/*.json`
**Count:** 3 core chunks (post-consolidation)

#### Chunk Types

**1. Processing Chunks** (Text transformation via LLM)
| Chunk Name | Backend | Purpose | Task Type |
|------------|---------|---------|-----------|
| `manipulate` | Ollama/OpenRouter | Universal text transformation | `standard` / `advanced` |

**2. Output Chunks** (Media generation via backends)
| Chunk Name | Backend | Purpose | Media Type |
|------------|---------|---------|-----------|
| `output_image_sd35_standard` | ComfyUI | SD3.5 Large image generation | Image |
| `output_audio_stable_audio` | ComfyUI | Stable Audio generation | Audio |
| `output_music_acestep` | ComfyUI | AceStep music (Tags + Lyrics) | Music |
| `output_3d_hunyuan3d` | GPU Service + Blender | Hunyuan3D-2 mesh gen + Eevee render | 3D |

**Note:**
- After consolidation, we have ONE text transformation chunk (`manipulate`) instead of multiple redundant chunks
- Output-Chunks contain complete ComfyUI API workflows embedded in JSON (not generated dynamically)
- Python-based chunks (HeartMuLa, Diffusers, Hunyuan3D) contain `execute()` functions — see "Output Chunk Types" below

#### Chunk Structure

**Type 1: Processing Chunk (LLM-based text transformation)**

```json
{
  "name": "manipulate",
  "type": "processing_chunk",
  "description": "Universal text transformation with instruction-based prompting",
  "template": "{{INSTRUCTION}}\n\nText to manipulate:\n\n{{PREVIOUS_OUTPUT}}",
  "backend_type": "ollama",
  "model": "task:standard",
  "parameters": {
    "temperature": 0.7,
    "top_p": 0.9,
    "stream": false
  },
  "meta": {
    "task_type": "standard",
    "output_format": "text",
    "estimated_duration": "medium"
  }
}
```

**Placeholder System:**
- `{{INSTRUCTION}}` - Complete instruction from config.context
- `{{INPUT_TEXT}}` - Original user input (first pipeline step)
- `{{PREVIOUS_OUTPUT}}` - Output from previous chunk (chaining)
- `{{USER_INPUT}}` - Original user input (available in all steps)

**Historical Note:** We removed `{{TASK}}` and `{{CONTEXT}}` placeholders - they were redundant aliases that caused instruction text to appear twice in rendered prompts.

---

#### Output Chunk Types

**IMPORTANT:** Stage4-JSON-Chunks are **DEPRECATED**. Only use JSON if there's a documented good reason.

**Standard (Python-Based Chunks):**
- Format: `output_*.py`
- Contains: Executable Python code with `execute()` function
- Examples: `output_music_heartmula.py`, `output_3d_hunyuan3d.py`
- Use for: ALL new Stage4 output chunks (HeartMuLa, Diffusers, Hunyuan3D, future backends)
- **3D chunks** return dict with `mesh_data` (base64 GLB) + optional `image_data` (base64 PNG thumbnail)

**Legacy (JSON-Based Chunks) - DEPRECATED:**
- Format: `output_*.json`
- Contains: Complete ComfyUI API workflow embedded in JSON
- Example: `output_image_sd35_large.json`, `output_audio_stable_audio.json`
- Status: Legacy pattern, being phased out
- Only use if: Documented good reason exists (e.g., pure ComfyUI passthrough without any Python logic)

---

**Type 2A: Output Chunk (ComfyUI - JSON Workflow)**

Output-Chunks contain **complete ComfyUI API workflows** embedded directly in the JSON, along with metadata for input/output mapping.

```json
{
  "name": "output_audio_stable_audio",
  "type": "output_chunk",
  "backend_type": "comfyui",
  "media_type": "audio",
  "description": "Stable Audio Open - 47 second audio generation",

  "workflow": {
    "3": {
      "inputs": {
        "seed": "{{SEED}}",
        "steps": "{{STEPS}}",
        "cfg": "{{CFG}}",
        "sampler_name": "{{SAMPLER}}",
        "scheduler": "{{SCHEDULER}}",
        "denoise": 1,
        "model": ["4", 0],
        "positive": ["6", 0],
        "negative": ["7", 0],
        "latent_image": ["11", 0]
      },
      "class_type": "KSampler",
      "_meta": {"title": "KSampler"}
    },
    "4": {
      "inputs": {
        "ckpt_name": "stable-audio-open-1.0.safetensors"
      },
      "class_type": "CheckpointLoaderSimple",
      "_meta": {"title": "Load Checkpoint"}
    },
    "6": {
      "inputs": {
        "text": "{{PROMPT}}",
        "clip": ["10", 0]
      },
      "class_type": "CLIPTextEncode",
      "_meta": {"title": "CLIP Text Encode (Prompt)"}
    },
    "7": {
      "inputs": {
        "text": "{{NEGATIVE_PROMPT}}",
        "clip": ["10", 0]
      },
      "class_type": "CLIPTextEncode",
      "_meta": {"title": "CLIP Text Encode (Negative)"}
    },
    "10": {
      "inputs": {
        "clip_name": "t5-base.safetensors",
        "type": "stable_audio",
        "device": "default"
      },
      "class_type": "CLIPLoader",
      "_meta": {"title": "Load CLIP"}
    },
    "11": {
      "inputs": {
        "seconds": "{{DURATION}}",
        "batch_size": 1
      },
      "class_type": "EmptyLatentAudio",
      "_meta": {"title": "Empty Latent Audio"}
    },
    "12": {
      "inputs": {
        "samples": ["3", 0],
        "vae": ["4", 2]
      },
      "class_type": "VAEDecodeAudio",
      "_meta": {"title": "VAE Decode Audio"}
    },
    "19": {
      "inputs": {
        "filename_prefix": "audio/ComfyUI",
        "quality": "V0",
        "audioUI": "",
        "audio": ["12", 0]
      },
      "class_type": "SaveAudioMP3",
      "_meta": {"title": "Save Audio (MP3)"}
    }
  },

  "input_mappings": {
    "prompt": {
      "node_id": "6",
      "field": "inputs.text",
      "source": "{{PREVIOUS_OUTPUT}}"
    },
    "negative_prompt": {
      "node_id": "7",
      "field": "inputs.text",
      "default": ""
    },
    "duration": {
      "node_id": "11",
      "field": "inputs.seconds",
      "default": 47.6
    },
    "steps": {
      "node_id": "3",
      "field": "inputs.steps",
      "default": 50
    },
    "cfg": {
      "node_id": "3",
      "field": "inputs.cfg",
      "default": 4.98
    },
    "seed": {
      "node_id": "3",
      "field": "inputs.seed",
      "default": "random"
    }
  },

  "output_mapping": {
    "node_id": "19",
    "output_type": "audio",
    "format": "mp3",
    "field": "filename_prefix"
  },

  "meta": {
    "estimated_duration": "30-60s",
    "requires_gpu": true,
    "model_file": "stable-audio-open-1.0.safetensors",
    "clip_file": "t5-base.safetensors"
  }
}
```

**Key Design Principles:**

1. **Embedded Workflows:** Complete ComfyUI API JSON workflow is stored in the chunk
   - No dynamic generation required
   - No dependency on `comfyui_workflow_generator.py` (deprecated)
   - Server simply fills placeholders and submits to ComfyUI

2. **Input Mappings:** Define where to inject data into the workflow
   - Maps semantic names (`prompt`, `duration`) to specific node fields
   - Supports defaults and placeholder replacement
   - DevServer knows where to put user input/pipeline output

3. **Output Mapping:** Define where to extract generated media
   - Identifies the SaveImage/SaveAudio node
   - Specifies expected format (png, mp3, wav)
   - Enables proper media retrieval after generation

4. **Backend Transparency:** Workflow could theoretically work with any ComfyUI-compatible backend
   - SwarmUI
   - ComfyUI forks
   - Any system that accepts ComfyUI API format

5. **Chunk Format Flexibility:** Output-Chunks can be JSON (ComfyUI) OR Python (.py)
   - ComfyUI backends: Use JSON chunks with embedded workflows
   - Python backends: Use .py chunks with execute() function
   - Router detects format automatically (.json vs .py)
   - See Type 2B below for Python chunk pattern

---

**Type 2B: Output Chunk (Python - Executable Code)**

Python-based Output-Chunks are `.py` files that contain the complete execution logic for non-ComfyUI backends.

```python
"""
Output Chunk: HeartMuLa Music Generation

Generates music from lyrics and style tags using HeartMuLa (heartlib).
This is a Python-based chunk - the code IS the chunk.

Input (from Stage 2/3 or direct):
    - lyrics (TEXT_1): Song lyrics with [Verse], [Chorus], [Bridge] markers
    - tags (TEXT_2): Comma-separated style tags (genre, mood, instruments)

Output:
    - MP3 audio bytes

Usage:
    result = await execute(lyrics="[Verse] Hello...", tags="pop, upbeat")
"""

async def execute(
    lyrics: str = None,
    tags: str = "",
    TEXT_1: str = None,  # Pipeline convention: first text input
    TEXT_2: str = None,  # Pipeline convention: second text input
    temperature: float = 1.0,
    topk: int = 250,
    cfg_scale: float = 1.0,
    max_audio_length_ms: int = 120000,
    seed: Optional[int] = None,
    **kwargs  # Ignore extra parameters from pipeline
) -> bytes:
    """
    Execute HeartMuLa music generation.

    Args:
        lyrics: Song lyrics with structure markers [Verse], [Chorus], [Bridge]
        tags: Comma-separated style tags (genre, mood, instruments, tempo)
        temperature: Creativity (0.1-2.0)
        topk: Token sampling parameter
        cfg_scale: Classifier-free guidance scale
        max_audio_length_ms: Maximum audio length in milliseconds
        seed: Seed for reproducibility (None = random)

    Returns:
        MP3 audio bytes (ready for storage/response)

    Raises:
        Exception: If generation fails or backend unavailable
    """
    from my_app.services.heartmula_backend import get_heartmula_backend

    # Map pipeline convention (TEXT_1, TEXT_2) to semantic names
    if lyrics is None and TEXT_1 is not None:
        lyrics = TEXT_1
    if not tags and TEXT_2 is not None:
        tags = TEXT_2

    backend = get_heartmula_backend()
    if not await backend.is_available():
        raise Exception("HeartMuLa backend not available")

    return await backend.generate_music(
        lyrics=lyrics,
        tags=tags,
        temperature=temperature,
        topk=topk,
        cfg_scale=cfg_scale,
        max_audio_length_ms=max_audio_length_ms,
        seed=seed,
        output_format="mp3"
    )
```

**Key Design Principles:**

1. **Self-Contained:** Chunk contains ALL execution logic
   - No delegation to central router code
   - Backend communication happens inside chunk
   - Clean separation of concerns

2. **Type-Safe:** Function signature declares inputs/outputs
   - No JSON parsing needed
   - IDE autocomplete works
   - Runtime type checking possible

3. **Async-First:** All execution is async/await compatible
   - Integrates with FastAPI routes
   - Non-blocking for concurrent requests

4. **No JSON Wrapper:** The `.py` file IS the chunk
   - No separate `.json` metadata file needed
   - Code is self-documenting (docstrings)
   - Simpler than JSON + separate code

5. **Backend Type:** ALL Python chunks use `backend_type='python'`
   - Generic type for all Python-based chunks
   - Chunk name determines specific implementation
   - No per-backend enum entries needed

---

### Layer 2: Pipelines (Input-Type Orchestration)

**Purpose:** Define structural flow based on INPUT requirements
**Location:** `schemas/pipelines/*.json`
**Count:** 4 core pipelines

#### Current Pipelines

| Pipeline | Input Type | Output Type | Use Cases |
|----------|------------|-------------|-----------|
| `text_transformation` | 1 text | Text | Dadaism, Bauhaus, translation, etc. (30 configs) |
| `single_text_media_generation` | 1 text | Image/Audio/Video | SD3.5, Flux1, Stable Audio (multiple configs) |
| `dual_text_media_generation` | 2 texts | Music | AceStep (Tags + Lyrics) |
| `image_text_media_generation` | Image + Text | Image | Inpainting, img2img, ControlNet (future) |

**Key Design:** Pipelines categorized by INPUT structure, not output medium!

#### Pipeline Structure

```json
{
  "name": "text_transformation",
  "description": "Single-step text transformation",
  "input_requirements": {
    "texts": 1
  },
  "chunks": ["manipulate"],
  "required_configs": ["manipulate_config"],
  "config_mappings": {
    "manipulate_config": "{{MANIPULATE_CONFIG}}"
  },
  "meta": {
    "workflow_type": "text_transformation",
    "reusable": true,
    "pre_translation": true,
    "steps": [
      {
        "step": 1,
        "chunk": "manipulate",
        "description": "Text transformation",
        "config_key": "manipulate_config"
      }
    ]
  }
}
```

**Design Principle:** Pipelines define HOW to process (structure), NOT WHAT to process (content).

**Key Field - `input_requirements`:**
Declares what inputs the pipeline expects. DevServer uses this for Stage 1 orchestration:
- `{"texts": 1}` - One text input (most configs: dada, bauhaus, overdrive, etc.)
- `{"texts": 2}` - Two text inputs (music_generation for AceStep: tags + lyrics)
- Future: `{"texts": 1, "images": 1}` for inpainting/img2img pipelines

DevServer reads this field and runs appropriate Stage 1 processing (translation + safety) for each input before executing the main pipeline.

---

### Layer 3: Configs (Content)

**Purpose:** User-facing configurations with complete instruction content
**Location:** `schemas/configs/*.json`
**Count:** 34+ configs

#### Config Types

**1. Text Transformation Configs (30 configs)**
- Pipeline: `text_transformation`
- Examples: dada.json, bauhaus.json, overdrive.json
- Purpose: Transform/optimize text according to specific approach

**2. Output Generation Configs (4+ configs, expanding)**
- Pipeline: `single_text_media_generation` or `dual_text_media_generation`
- Examples: sd35_standard.json, flux1_dev.json, acestep_standard.json
- Purpose: Generate media from text prompt(s)

#### Config Structure

```json
{
  "pipeline": "text_transformation",

  "name": {
    "en": "Dadaism",
    "de": "Dadaismus"
  },

  "description": {
    "en": "Transform prompts through Dadaist aesthetic",
    "de": "Prompt-Transformation durch dadaistische Ästhetik"
  },

  "category": {
    "en": "Art Movements",
    "de": "Kunstbewegungen"
  },

  "context": "You are an artist working in the spirit of Dadaism. Your task is to...",

  "parameters": {
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 2048
  },

  "media_preferences": {
    "default_output": "text",
    "supported_types": ["text", "image"]
  },

  "meta": {
    "stage": "interception",     // Required: "pre_interception" | "interception" | "pre_output" | "output"
    "task_type": "advanced",  // Optional: override chunk's task_type
    "requires_creativity": true,
    "legacy_source": "config.py.DADAISMUS_PROMPT"
  },

  "display": {
    "icon": "🎨",
    "color": "#FF6B6B",
    "category": "art",
    "difficulty": 3,
    "order": 1
  },

  "tags": {
    "en": ["art", "surreal", "avant-garde"],
    "de": ["kunst", "surreal", "avantgarde"]
  },

  "audience": {
    "workshop_suitable": true,
    "min_age": 14,
    "complexity": "intermediate"
  }
}
```

**Key Field - `context`:**
The `context` field contains the **complete instruction text** (formerly called "metaprompt"). This is the actual content that gets injected into chunk templates as `{{INSTRUCTION}}`.

**Key Field - `meta.stage`:**
The `stage` field identifies which stage of the 4-Stage Architecture this config belongs to:
- `"pre_interception"` - Stage 1 configs (translation, safety checks before main pipeline)
- `"interception"` - Stage 2 configs (main transformation: dada, bauhaus, overdrive, etc.)
- `"pre_output"` - Stage 3 configs (safety checks before media generation)
- `"output"` - Stage 4 configs (media generation: sd35_large, gpt5_image, stableaudio, etc.)

This field helps DevServer orchestrate the correct flow and enables future organization (e.g., moving output configs to separate folder).

---

