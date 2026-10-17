# ARCHITECTURE PART 23 - LoRA Training Studio

**Document:** Architecture Reference
**Created:** 2026-01-18
**Sessions:** 119, 121, 124
**Status:** Production Ready

---

## Overview

The LoRA Training Studio enables users to train custom Stable Diffusion LoRA models directly within AI4ArtsEd. Users can upload training images, configure parameters, and receive trained LoRA files that are automatically available for image generation.

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Vue)                            │
│  LoraTrainingStudio.vue                                      │
│  - Multi-image upload                                        │
│  - Training configuration form                               │
│  - Progress visualization                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP POST /api/training/start
                       │ SSE /api/training/progress
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  training_routes.py                                          │
│  - POST /api/training/start                                  │
│  - GET /api/training/progress/{job_id}                       │
│  - GET /api/training/status                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Training Service                             │
│  training_service.py                                         │
│  - Dataset preparation                                       │
│  - VRAM management                                           │
│  - Kohya-ss script execution                                 │
│  - Progress streaming                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Kohya-ss Trainer                           │
│  sd3_train_network.py                                        │
│  - SD3.5 Large base model                                    │
│  - LoRA network training                                     │
│  - Checkpoint saving                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Output                                    │
│  SwarmUI/Models/Lora/                                        │
│  - {name}.safetensors (trained LoRA)                         │
│  - epoch-{n}.safetensors (checkpoints)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration

### config.py Settings

```python
# LoRA Training Configuration
TRAINING_CONFIG = {
    "base_model": "sd3.5-large",
    "steps_per_image": 100,
    "learning_rate": 1e-4,
    "epochs": 6,
    "resolution": 1024,
    "network_dim": 32,
    "network_alpha": 16
}

# Paths
LORA_OUTPUT_DIR = "<AI_TOOLS_BASE>/SwarmUI/Models/Lora"
TRAINING_DATASET_DIR = "<repo>/training_data"
KOHYA_SS_DIR = "<AI_TOOLS_BASE>/kohya_ss"

# VRAM Management
TRAINING_VRAM_REQUIRED_GB = 18
```

---

## Training Flow

### 1. Dataset Preparation

When training starts:

```python
async def prepare_dataset(images: List[UploadFile], trigger_word: str):
    """
    1. Create job directory in TRAINING_DATASET_DIR
    2. Save uploaded images with sequential naming
    3. Create caption files with trigger word
    4. Generate dataset configuration
    """
    job_id = str(uuid.uuid4())
    job_dir = Path(TRAINING_DATASET_DIR) / job_id

    for idx, image in enumerate(images):
        # Save image
        image_path = job_dir / f"{idx:04d}.png"
        await save_image(image, image_path)

        # Create caption file
        caption_path = job_dir / f"{idx:04d}.txt"
        caption_path.write_text(trigger_word)

    return job_id, job_dir
```

### 2. VRAM Management

Before training:

```python
async def ensure_vram_available():
    """
    Check VRAM and unload models if needed.
    Training requires ~18GB, SD3.5 uses ~12GB.
    """
    available_vram = get_available_vram_gb()

    if available_vram < TRAINING_VRAM_REQUIRED_GB:
        logger.info("Unloading SD3.5 to free VRAM for training")
        await unload_swarmui_models()

        # Wait for VRAM to clear
        await asyncio.sleep(5)
```

### 3. Training Execution

```python
async def run_training(job_id: str, config: TrainingConfig):
    """
    Execute Kohya-ss training script with progress streaming.
    """
    cmd = [
        "python", f"{KOHYA_SS_DIR}/sd3_train_network.py",
        "--pretrained_model_name_or_path", config.base_model_path,
        "--train_data_dir", str(job_dir),
        "--output_dir", LORA_OUTPUT_DIR,
        "--output_name", config.lora_name,
        "--max_train_epochs", str(config.epochs),
        "--learning_rate", str(config.learning_rate),
        "--network_dim", str(config.network_dim),
        "--network_alpha", str(config.network_alpha),
        "--resolution", str(config.resolution),
        "--save_every_n_epochs", "1"
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Stream progress
    async for line in process.stdout:
        progress = parse_progress(line.decode())
        yield progress
```

### 4. Progress Streaming

```python
async def stream_training_progress(job_id: str):
    """
    SSE endpoint for real-time training updates.
    """
    async for progress in training_jobs[job_id].progress:
        yield f"data: {json.dumps({
            'status': 'training',
            'epoch': progress.epoch,
            'step': progress.step,
            'loss': progress.loss,
            'percent': progress.percent
        })}\n\n"

    yield f"data: {json.dumps({
        'status': 'complete',
        'lora_path': f'{LORA_OUTPUT_DIR}/{job_id}.safetensors'
    })}\n\n"
```

---

## API Endpoints

### POST /api/training/start

Start a new training job.

**Request:**
```json
{
  "name": "my_style",
  "trigger_word": "mystyle",
  "epochs": 6,
  "learning_rate": 0.0001,
  "images": [/* multipart file uploads */]
}
```

**Response:**
```json
{
  "job_id": "abc-123-def",
  "status": "started",
  "estimated_duration_minutes": 45
}
```

### GET /api/training/progress/{job_id}

SSE endpoint for progress updates.

**Events:**
```
event: progress
data: {"status": "training", "epoch": 2, "step": 150, "loss": 0.023}

event: complete
data: {"status": "complete", "lora_path": "/path/to/lora.safetensors"}
```

### GET /api/training/status

Get status of all training jobs.

**Response:**
```json
{
  "active_jobs": 1,
  "jobs": [
    {
      "job_id": "abc-123",
      "name": "my_style",
      "status": "training",
      "progress": 67
    }
  ]
}
```

---

## Frontend Component

### LoraTrainingStudio.vue

```vue
<template>
  <div class="training-studio">
    <!-- Image Upload Area -->
    <div class="upload-zone" @drop="handleDrop" @dragover.prevent>
      <p>Drag & drop training images (5-20 recommended)</p>
      <div class="image-grid">
        <div v-for="img in uploadedImages" :key="img.id" class="image-preview">
          <img :src="img.preview" />
          <button @click="removeImage(img.id)">×</button>
        </div>
      </div>
    </div>

    <!-- Configuration Form -->
    <form @submit.prevent="startTraining">
      <input v-model="config.name" placeholder="LoRA Name" required />
      <input v-model="config.triggerWord" placeholder="Trigger Word" required />
      <select v-model="config.epochs">
        <option value="4">4 epochs (faster, lighter)</option>
        <option value="6" selected>6 epochs (balanced)</option>
        <option value="8">8 epochs (more detail)</option>
      </select>
      <button type="submit" :disabled="isTraining">
        {{ isTraining ? 'Training...' : 'Start Training' }}
      </button>
    </form>

    <!-- Progress Display -->
    <div v-if="isTraining" class="progress">
      <div class="progress-bar" :style="{ width: progress + '%' }"></div>
      <p>Epoch {{ currentEpoch }}/{{ config.epochs }} - {{ progress }}%</p>
    </div>
  </div>
</template>
```

---

## LoRA Integration

### Config Schema

Trained LoRAs are associated with interception configs via the `meta` object:

```json
{
  "name": "cooked_negatives",
  "context_prompt": "Transform the image to look like developed film...",
  "meta": {
    "loras": [
      {
        "name": "sd3.5-large_cooked_negatives.safetensors",
        "strength": 0.6
      }
    ],
    "recommended_models": ["sd35_large"],
    "style_tags": ["film", "vintage", "analog"]
  }
}
```

### Injection at Runtime

During Stage 4, `backend_router.py` injects LoRAs into the workflow:

```python
async def _inject_lora_nodes(self, workflow: dict, loras: List[dict]):
    """
    Insert LoRALoader nodes into ComfyUI workflow.

    Flow: Checkpoint → LoRA1 → LoRA2 → ... → KSampler
    """
    # Find checkpoint node
    checkpoint_node_id = self._find_node_by_class(workflow, "CheckpointLoaderSimple")

    # Find model consumers
    consumers = self._find_model_consumers(workflow, checkpoint_node_id)

    # Insert LoRA chain
    last_model_output = (checkpoint_node_id, 0)

    for idx, lora in enumerate(loras):
        lora_node_id = str(max(int(k) for k in workflow.keys()) + 1)
        workflow[lora_node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": last_model_output,
                "lora_name": lora["name"],
                "strength_model": lora["strength"],
                "strength_clip": lora["strength"]
            }
        }
        last_model_output = (lora_node_id, 0)

    # Update consumers to use LoRA chain output
    for consumer_id in consumers:
        workflow[consumer_id]["inputs"]["model"] = last_model_output
```

---

## Best Practices

### Training Dataset
- **5-20 images** recommended for style LoRAs
- **Consistent style** across all images
- **High resolution** (1024x1024 or larger)
- **Varied compositions** to prevent overfitting

### Trigger Words
- Use **unique, memorable** words
- Support **multiple triggers** (comma-separated)
- Include trigger in generation prompts

### Epoch Selection
- **Epoch 4**: Good for preventing overfitting, lighter style
- **Epoch 6**: Balanced (default)
- **Epoch 8**: Stronger style, risk of overfitting

### Strength Tuning
- Start at **0.6** and adjust
- Lower for subtle styles (0.4-0.5)
- Higher for dominant styles (0.7-0.8)
- **Trade-off**: Higher strength = more style, less prompt adherence

---

## Troubleshooting

### VRAM Errors
If training fails with CUDA OOM:
1. Close SwarmUI manually
2. Wait 30 seconds
3. Retry training

### Training Too Long
- Reduce epochs (4 instead of 6)
- Use fewer images
- Lower resolution

### LoRA Not Appearing
1. Check output path: `SwarmUI/Models/Lora/`
2. Restart SwarmUI to refresh model list
3. Verify `.safetensors` file exists

---

## Files Reference

| File | Purpose |
|------|---------|
| `training_service.py` | Core training logic |
| `training_routes.py` | API endpoints |
| `LoraTrainingStudio.vue` | Frontend UI |
| `config.py` | Training configuration |

---

*Related: ARCHITECTURE PART 24 - SwarmUI Integration*

---

<sub>📝 *This documentation was automatically generated by Claude Code (January 2026).*</sub>
