# AI4ArtsEd DevServer - Architecture Requirements

This document specifies the infrastructure, software dependencies, and model requirements for the AI4ArtsEd DevServer system.

---

## SwarmUI/ComfyUI Backend

### Overview

AI4ArtsEd DevServer uses **SwarmUI** (v0.9.7.3) as the primary AI image/video generation interface, with **ComfyUI** embedded as the execution backend. SwarmUI is installed at `<AI_TOOLS_BASE>/SwarmUI` and runs on port **7801** in production.

### Model Storage Architecture

**Directory Structure:**
```
<AI_TOOLS_BASE>/SwarmUI/
├── Models/                          (334GB - Single source of truth)
│   ├── Stable-Diffusion/
│   │   ├── Flux1/
│   │   │   └── flux2_dev_fp8mixed.safetensors (23GB)
│   │   ├── OfficialStableDiffusion/
│   │   │   └── sd3.5_large.safetensors (16GB)
│   │   ├── ltxv-13b-0.9.7-distilled-fp8.safetensors (15GB)
│   │   └── ace_step_v1_3.5b.safetensors (7.2GB)
│   ├── diffusion_models/
│   │   ├── qwen_image_fp8_e4m3fn.safetensors (20GB)
│   │   ├── wan2.2_ti2v_5B_fp16.safetensors (9.4GB)
│   │   ├── wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors (14GB)
│   │   └── wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors (14GB)
│   ├── clip/                        (~74GB - Shared text encoders)
│   │   ├── clip_g.safetensors (1.3GB - SD3.5 + FLUX)
│   │   ├── t5xxl_fp16.safetensors (9.8GB - SD3.5)
│   │   ├── t5xxl_enconly.safetensors (4.6GB - LTX-Video)
│   │   ├── mistral_3_small_flux2_fp8.safetensors (17GB - FLUX2)
│   │   ├── qwen_2.5_vl_7b_fp8_scaled.safetensors (7.8GB - Qwen)
│   │   └── umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.3GB - Wan 2.2)
│   ├── vae/                         (2.3GB - VAE encoders, lowercase standard)
│   │   ├── Flux/
│   │   │   ├── ae.safetensors (320MB)
│   │   │   └── flux2-vae.safetensors (320MB)
│   │   ├── QwenImage/
│   │   │   └── qwen_image_vae.safetensors (242MB)
│   │   ├── wan2.2_vae.safetensors (1.3GB)
│   │   └── wan_2.1_vae.safetensors (242MB)
│   └── loras/                       (7.4GB - LoRA adapters, lowercase standard)
│       ├── Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors (810MB)
│       ├── wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors
│       ├── wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors
│       └── test_lora.safetensors (218MB)
│
└── dlbackend/ComfyUI/
    └── models/                      (56GB - ComfyUI-specific files + symlinks)
        ├── checkpoints/             (Directory with ComfyUI-specific models)
        │   ├── ltxv-13b-0.9.7-distilled-fp8.safetensors (15GB)
        │   ├── stable-audio-open-1.0.safetensors (4.6GB)
        │   └── OfficialStableDiffusion@ -> ../../../Models/Stable-Diffusion/OfficialStableDiffusion/
        ├── clip/                    (Directory with individual file symlinks)
        │   ├── clip_g.safetensors (1.3GB)
        │   ├── t5xxl_fp16.safetensors (9.8GB)
        │   ├── t5xxl_enconly.safetensors (4.6GB)
        │   ├── t5-base.safetensors (419MB)
        │   └── qwen_2.5_vl_7b_fp8_scaled.safetensors@ -> ../../../../Models/clip/...
        ├── diffusion_models/        (Directory with individual file symlinks)
        │   ├── wan2.2_ti2v_5B_fp16.safetensors (9.4GB)
        │   └── qwen_image_edit_fp8_e4m3fn.safetensors@ -> ../../../../Models/...
        ├── vae/                     (Directory with individual file symlinks)
        │   ├── qwen_image_vae.safetensors@ -> ../../../../Models/vae/QwenImage/...
        │   ├── wan2.2_vae.safetensors@ -> ../../../../Models/vae/...
        │   └── wan_2.1_vae.safetensors@ -> ../../../../Models/vae/...
        ├── loras/                   (Directory with individual file symlinks)
        │   ├── test_lora.safetensors (218MB)
        │   └── [symlinks to Models/loras/]
        ├── stableaudio/             (15GB - ComfyUI-specific)
        │   └── stable-audio-open-1.0/
        └── musicgen/                (6.1GB - ComfyUI-specific)
```

### Critical Symlink Strategy

**IMPORTANT: ComfyUI requires DIRECTORIES, not directory-level symlinks!**

❌ **WRONG (causes errors):**
```bash
ComfyUI/models/clip → (symlink) → Models/clip
```

✅ **CORRECT:**
```bash
ComfyUI/models/clip/ (real directory)
├── clip_g.safetensors (real file)
└── qwen_2.5_vl_7b_fp8_scaled.safetensors → (symlink) → Models/clip/...
```

**Rationale:**
- ComfyUI expects real directories in its `models/` folder
- Individual files can be symlinks to `SwarmUI/Models/`
- ComfyUI-specific models (checkpoints/, stableaudio/, musicgen/) remain in ComfyUI
- Shared models (clip/, diffusion_models/) use symlinks to avoid duplication

### Model Requirements by Media Type

#### Image Generation Models

**SD3.5 Large** (Active - Primary)
- Model: `sd3.5_large.safetensors` (16GB)
- CLIP: `clip_l.safetensors`, `clip_g.safetensors` (1.3GB), `t5xxl_fp16.safetensors` (9.8GB)
- Location: `Models/Stable-Diffusion/OfficialStableDiffusion/`
- Used in: `sd35_large.json`, `sd35_img2img.json`

**FLUX 2 Dev** (Active - Secondary)
- Model: `flux2_dev_fp8mixed.safetensors` (23GB)
- CLIP: `mistral_3_small_flux2_fp8.safetensors` (17GB), `clip_g.safetensors` (1.3GB)
- VAE: `flux2-vae.safetensors` (320MB)
- Location: `Models/Stable-Diffusion/Flux1/`
- Used in: `flux2.json`, `flux2_img2img.json`

**Qwen 2.5 Vision** (Active - Multimodal)
- Model: `qwen_image_fp8_e4m3fn.safetensors` (20GB)
- CLIP: `qwen_2.5_vl_7b_fp8_scaled.safetensors` (7.8GB)
- VAE: `qwen_image_vae.safetensors` (242MB)
- Location: `Models/diffusion_models/`
- Used in: `qwen.json`, `qwen_img2img.json`, `qwen_2511_multi.json`
- **Note:** VAE must be accessible as `vae/qwen_image_vae.safetensors` in ComfyUI via symlink

#### Video Generation Models

**LTX-Video** (Active - Fast Video)
- Model: `ltxv-13b-0.9.7-distilled-fp8.safetensors` (15GB)
- Text Encoder: `t5xxl_enconly.safetensors` (4.6GB)
- Location: `Models/Stable-Diffusion/` or `ComfyUI/models/checkpoints/`
- Used in: `ltx_video.json`
- Generation time: 4-10 seconds

**Wan 2.2 Video** (Active - High Quality)
- Text-to-Video: `wan2.2_ti2v_5B_fp16.safetensors` (9.4GB)
- Image-to-Video:
  - `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` (14GB)
  - `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` (14GB)
- VAE: `wan2.2_vae.safetensors` (1.3GB)
- Text Encoder: `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (6.3GB)
- LoRAs (optional):
  - `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors`
  - `wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors`
- Location: `Models/diffusion_models/`
- Used in: `wan22_video.json`, `wan22_i2v_video.json`
- Resolution: 720p

#### Audio Generation Models

**ACE Step v1.3.5b** (retired 2026-10-10)
- Model: `ace_step_v1_3.5b.safetensors` (7.2GB)
- Location: `Models/Stable-Diffusion/`
- Used in: `acenet_t2instrumental.json`, `acestep_*.json` configs, all three
  `.json.disabled` since 2026-10-10 (S-010 of the code review of that day:
  the two `acestep_*` configs ran HeartMuLa under this model's name)
- Quality: High

**Stable Audio Open 1.0** (removed 2026-10-01)
- Replaced by Stable Audio 3 medium: `stableaudio_open.json`, `stableaudio_music.json`, `stableaudio_sfx.json`

### Ollama LLMs (External)

**Not stored in SwarmUI/ComfyUI - managed by Ollama:**

- **gpt-OSS:20b** (~21GB)
  - Used in: Stage 1 (translation), Stage 3 (safety validation)
  - Config: `STAGE1_TEXT_MODEL`, `STAGE3_MODEL`, `TRANSLATION_MODEL`, `SAFETY_MODEL`

- **llama3.2-vision:latest** (~8GB)
  - Used in: Stage 1 (image analysis), Stage 5 (image reflexion)
  - Config: `STAGE1_VISION_MODEL`, `IMAGE_ANALYSIS_MODEL`, `ANALYSIS_MODEL`

### ComfyUI Extensions & Additional Software

**Required Python Packages** (in ComfyUI venv):

```
comfy-kitchen==0.2.5                         # FP8/FP4 quantization support (CRITICAL for FLUX2)
comfyui-embedded-docs==0.2.4                 # Documentation integration
comfyui_frontend_package==1.34.9             # Web UI frontend
comfyui_workflow_templates==0.7.69           # Workflow templates
comfyui-workflow-templates-core==0.3.77      # Core template functionality
comfyui-workflow-templates-media-api==0.3.34 # Media API templates
comfyui-workflow-templates-media-image==0.3.50   # Image generation templates
comfyui-workflow-templates-media-video==0.3.33   # Video generation templates
comfyui-workflow-templates-media-other==0.3.68   # Other media templates
```

**Installation (if missing):**
```bash
cd <AI_TOOLS_BASE>/SwarmUI/dlbackend/ComfyUI
source venv/bin/activate
pip install comfy-kitchen  # Essential for FLUX2 FP8 support
```

**Note:** Without `comfy-kitchen`, FLUX2 will fail with:
```
AttributeError: 'NoneType' object has no attribute 'Params'
```

### Storage Statistics (After Cleanup - January 2026)

**Before Cleanup:**
- SwarmUI/Models/: **545GB**
- ComfyUI/models/: **93GB**
- **Total: 638GB**

**After Cleanup:**
- SwarmUI/Models/: **334GB** (-211GB, -38.7%)
- ComfyUI/models/: **56GB** (-37GB, -39.8%)
- **Total: 390GB** (-248GB, -38.9%)

**Archived (Recoverable):**
- Location: `<downloads>/0_Modelle/`
- Duplicates: 36GB (SD3.5 Large x2, Qwen Image x2, VAE/LoRA duplicates)
- Deprecated: 33GB (old `split_files/` directory)
- Unused models: 176GB (FLUX 1 variants, SD3.5 Medium/Turbo, SDXL, old Qwen variants, OmniGen2)
- ComfyUI backup: 23GB (temporary backup of replaced symlinks)
- **Total archived: 279GB**

**Cleanup Benefits:**
- **248GB disk space saved** (38.9% reduction)
- Single source of truth for each model
- Consistent naming conventions (lowercase: `vae/`, `loras/`)
- Clear separation: SwarmUI owns files, ComfyUI uses symlinks
- Only actively used models remain in production
- All archived files are recoverable (no deletions, only moves)

### Model Naming Conventions

**CRITICAL: Use lowercase for shared directories**

- ✅ `vae/` (lowercase - STANDARD)
- ✅ `loras/` (lowercase - STANDARD)
- ❌ `VAE/` (uppercase - DEPRECATED, causes broken symlinks)
- ❌ `Lora/` (uppercase - DEPRECATED, causes broken symlinks)

**Background:** During Phase 3 cleanup, all uppercase directories (`VAE/`, `Lora/`) were merged into lowercase equivalents (`vae/`, `loras/`) to match ComfyUI's expected convention. Any existing symlinks pointing to uppercase paths must be updated.

### Rollback Procedures

All cleanup operations used `mv` (move), never `rm` (delete). To rollback:

1. **Restore archived models:**
   ```bash
   mv <downloads>/0_Modelle/unused/flux1/* \
      <AI_TOOLS_BASE>/SwarmUI/Models/Stable-Diffusion/Flux1/
   ```

2. **Restore duplicates:**
   ```bash
   mv <downloads>/0_Modelle/duplicates/* \
      <AI_TOOLS_BASE>/SwarmUI/dlbackend/ComfyUI/models/checkpoints/
   ```

3. **Restore deprecated files:**
   ```bash
   mv <downloads>/0_Modelle/deprecated/split_files \
      <AI_TOOLS_BASE>/SwarmUI/Models/Stable-Diffusion/
   ```

4. **Recreate original symlinks:**
   ```bash
   cat /tmp/comfyui_symlinks_backup.txt  # View original symlinks
   ```

### Hardware Requirements

**GPU:**
- NVIDIA RTX PRO 6000 Blackwell Workstation Edition
- VRAM: 95.59 GiB total
- Required minimum: ~24GB VRAM for FLUX2, 16GB for SD3.5

**Storage:**
- Minimum: 400GB for active models
- Recommended: 700GB (including archived models for quick restoration)
- Fast SSD strongly recommended for model loading performance

**RAM:**
- Current system: 62.16 GiB
- Recommended minimum: 32GB

**CPU:**
- Current system: 24 cores
- Recommended minimum: 8 cores (for Ollama LLM inference)

### Port Configuration

**SwarmUI:**
- Default: 7801 (production)
- Development: 7801 (same port, controlled by startup script)
- Port override: Set `PORT=17801` environment variable in startup script

**ComfyUI Backend:**
- Port: 7821 (embedded backend, auto-started by SwarmUI)
- Not directly accessible from outside

**DevServer:**
- Production: 17801 (proxied through Cloudflare Tunnel)
- Development: 17802 (local testing)

---

## Related Documentation

- [ARCHITECTURE PART 09 - Model Selection](./ARCHITECTURE%20PART%2009%20-%20Model-Selection.md)
- [ARCHITECTURE PART 08 - Backend Routing](./ARCHITECTURE%20PART%2008%20-%20Backend-Routing.md)
- [PORT_ARCHITECTURE_DECISION.md](./PORT_ARCHITECTURE_DECISION.md)

---

**Document Version:** 1.0
**Last Updated:** 2026-01-09
**Maintainer:** AI4ArtsEd Development Team
