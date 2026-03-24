# AI4ArtsEd — Required AI Models

Complete inventory of all AI models used by the platform.
**Updated:** 2026-03-24

---

## Overview

| Category | Size | Purpose |
|----------|------|---------|
| **Ollama Models** | ~16 GB | Safety, DSGVO, VLM, translation, interception |
| **HuggingFace / Diffusers** | ~129 GB | Image, video, audio generation (GPU Service) |
| **HuggingFace / Text (Latent Lab)** | ~65 GB | Bias Archaeology, Representation Engineering |
| **SwarmUI / ComfyUI** | ~450 GB | ComfyUI fallback models |
| **GPU Service Weights** | ~6 GB | MMAudio (video-to-audio) |
| **HeartMuLa** | ~21 GB | Music generation checkpoint |
| **Total** | **~685 GB** | |

---

## 1. Ollama Models (Local LLM Inference)

Referenced in `devserver/config.py`. Stored at `/usr/share/ollama/.ollama/models/`.

### Required (Production)

| Model | Config Variable | Purpose | Size |
|-------|----------------|---------|------|
| `llama-guard3:1b` | `SAFETY_MODEL` | Stage 1/3 content filtering, DSGVO | 1.6 GB |
| `qwen3:1.7b` | `DSGVO_VERIFY_MODEL` | NER verification (is this a person name?) | 1.4 GB |
| `qwen3-vl:2b` | `VLM_SAFETY_MODEL` | Post-generation image safety check | 1.9 GB |
| `qwen3:4b` | `LOCAL_DEFAULT_MODEL` | Stages 1-4, chat, interception | 3.0 GB |
| `llama3.2-vision:latest` | `LOCAL_VISION_MODEL` | Image analysis, Stage 1 vision | 7.8 GB |
| **Total** | | | **~16 GB** |

### Install

```bash
ollama pull llama-guard3:1b
ollama pull qwen3:1.7b
ollama pull qwen3-vl:2b
ollama pull qwen3:4b
ollama pull llama3.2-vision:latest
```

### Verify

```bash
ollama list
# Should show all 5 models
```

---

## 2. HuggingFace / Diffusers Models (GPU Service)

Used by the GPU Service (`gpu_service/services/diffusers_backend.py`).
Stored at `~/.cache/huggingface/hub/` (content-addressable, directly portable).

### Image Generation

| Model | HF ID | Size | Purpose |
|-------|-------|------|---------|
| SD 3.5 Large | `stabilityai/stable-diffusion-3.5-large` | 26 GB | Primary image generation |
| SD 3.5 Large Turbo | `stabilityai/stable-diffusion-3.5-large-turbo` | 55 GB | Fast image generation |

### Video Generation

| Model | HF ID | Size | Purpose |
|-------|-------|------|---------|
| Wan 2.2 TI2V 5B | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | 32 GB | Text/image-to-video |

### Audio Generation

| Model | HF ID | Size | Purpose |
|-------|-------|------|---------|
| Stable Audio Open 1.0 | `stabilityai/stable-audio-open-1.0` | 9.5 GB | Text-to-audio |

### Encoders / Utility

| Model | HF ID | Size | Purpose |
|-------|-------|------|---------|
| CLIP ViT-L/14 | `openai/clip-vit-large-patch14` | 1.6 GB | Cross-aesthetic, Hallucinator fusion |
| DFN5B CLIP ViT-H-14 | `apple/DFN5B-CLIP-ViT-H-14-384` | 3.7 GB | Cross-aesthetic generation |
| BigVGAN v2 44kHz | `nvidia/bigvgan_v2_44khz_128band_512x` | 467 MB | Audio vocoder |

### HF Cache Portability

The HuggingFace cache is directly portable between machines:
1. Copy `~/.cache/huggingface/hub/models--org--name/` directories
2. Place at the same path on target machine
3. `from_pretrained()` finds cached models automatically (sha256-based blob storage)

### Extra Diffusers Caches

These are duplicates in non-standard locations (referenced by `config.py`):
- `~/ai/models/diffusers/` — SD 3.5 Large Turbo (~16 GB)
- `~/ai/diffusers_cache/` — SD 3.5 Large (~1.6 GB, partial)

---

## 2b. HuggingFace / Text Models (Latent Text Lab)

Used by the GPU Service text backend (`gpu_service/services/text_backend.py`) for Bias Archaeology
and Representation Engineering. These require direct logit access via HuggingFace transformers
(not Ollama). Stored at `~/.cache/huggingface/hub/`.

Two preset scenarios are available (toggle in the Bias Archaeology tab):

### Scenario "Qwen family" — Same family, different sizes

Isolates how model scale affects bias patterns.

| Model | HF ID | Size (bf16) | Purpose |
|-------|-------|-------------|---------|
| Qwen3 1.7B | `Qwen/Qwen3-1.7B` | ~4 GB | Fast iteration |
| Qwen3 4B | `Qwen/Qwen3-4B` | ~8 GB | Good balance |
| Qwen3 8B | `Qwen/Qwen3-8B` | ~16 GB | Strong mid-range |
| Qwen3 14B | `Qwen/Qwen3-14B` | ~28 GB | Best quality |

### Scenario "Mixed families" — Different families, similar sizes

Isolates how tokenizer and training data affect bias patterns.

| Model | HF ID | Size (bf16) | Purpose |
|-------|-------|-------------|---------|
| Qwen3 4B | `Qwen/Qwen3-4B` | ~8 GB | Qwen tokenizer |
| Phi 3.5 Mini | `microsoft/Phi-3.5-mini-instruct` | ~8 GB | Microsoft tokenizer |
| Llama 3.2 3B | `meta-llama/Llama-3.2-3B-Instruct` | ~7 GB | Meta tokenizer |
| Gemma 2 2B | `google/gemma-2-2b-it` | ~5 GB | Google tokenizer |

**Total unique models: 7** (~65 GB bf16, less with quantization)

### Pre-download

```bash
# Qwen family scenario
huggingface-cli download Qwen/Qwen3-1.7B
huggingface-cli download Qwen/Qwen3-4B
huggingface-cli download Qwen/Qwen3-8B
huggingface-cli download Qwen/Qwen3-14B

# Mixed families scenario (Qwen3-4B already above)
huggingface-cli download microsoft/Phi-3.5-mini-instruct
huggingface-cli download meta-llama/Llama-3.2-3B-Instruct
huggingface-cli download google/gemma-2-2b-it
```

**Note:** Models are auto-downloaded on first use, but pre-downloading avoids delays during workshops.
The VRAM coordinator handles loading/eviction at runtime — only one model is loaded at a time.

---

## 3. HeartMuLa (Music Generation)

Checkpoint at `~/ai/heartlib/ckpt/`. Installed as editable package: `pip install --no-deps -e ~/ai/heartlib`.

| File | Size |
|------|------|
| `HeartMuLa-oss-3B/model-0000{1-4}-of-00004.safetensors` | 14.7 GB |
| `HeartCodec-oss/model-0000{1-2}-of-00002.safetensors` | 6.2 GB |
| `tokenizer.json` | 8.7 MB |
| **Total** | **~21 GB** |

**Critical notes:**
- Vocab/codebook mismatch: MuLa vocab=8197, codec codebook=8192. Clamp fix in `flow_matching.py:75`
- DO NOT wrap `self._pipeline()` in `torch.autocast` — heartlib handles autocast internally

---

## 4. GPU Service Weights (MMAudio)

Stored in `gpu_service/weights/` and `gpu_service/ext_weights/`.

| File | Size | Purpose |
|------|------|---------|
| `weights/mmaudio_large_44k_v2.pth` | 3.9 GB | MMAudio main model |
| `ext_weights/v1-44.pth` | 1.2 GB | Visual encoder |
| `ext_weights/synchformer_state_dict.pth` | 907 MB | Sync model |
| **Total** | **~6 GB** | |

---

## 5. SwarmUI / ComfyUI Models (Fallback)

Stored at `~/ai/SwarmUI/Models/`. Used as ComfyUI fallback when Diffusers GPU Service is unavailable.

### Stable-Diffusion/ (~169 GB)

| File | Size |
|------|------|
| `Flux1/flux2-dev.safetensors` | 61 GB |
| `Flux1/flux2_dev_fp8mixed.safetensors` | 34 GB |
| `OfficialStableDiffusion/sd3.5_large.safetensors` | 16 GB |
| `ltxv-13b-0.9.7-dev-fp8.safetensors` | 15 GB |
| `ace_step_v1_3.5b.safetensors` | 7.2 GB |
| `OfficialStableDiffusion/stableaudio_model.safetensors` | 4.6 GB |

### clip/ (~134 GB)

| File | Size |
|------|------|
| `mistral_3_small_flux2_bf16.safetensors` | 34 GB |
| `mistral_3_small_flux2_fp8.safetensors` | 17 GB |
| `qwen_image_official/.../qwen_2.5_vl_7b.safetensors` | 16 GB |
| `t5xxl_fp16.safetensors` | 9.2 GB |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | 8.8 GB |
| `qwen_3_4b.safetensors` | 7.5 GB |
| `t5xxl_enconly.safetensors` | 4.6 GB |
| `clip_g.safetensors` | 1.3 GB |
| `clip_l.safetensors` | 235 MB |
| (+ weitere) | |

### diffusion_models/ (~118 GB)

| File | Size |
|------|------|
| `qwen_image_official/.../qwen_image_bf16.safetensors` | 39 GB |
| `qwen_image_fp8_e4m3fn.safetensors` | 20 GB |
| `qwen_image_edit_2511_fp8mixed.safetensors` | 20 GB |
| `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | 14 GB |
| `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | 14 GB |
| `wan2.2_ti2v_5B_fp16.safetensors` | 9.4 GB |

### vae/ (~5.4 GB)

| File | Size |
|------|------|
| `LTXV/ltxv_vae.safetensors` | 2.4 GB |
| `wan2.2_vae.safetensors` | 1.4 GB |
| `diffusion_pytorch_model.safetensors` | 596 MB |
| `Flux/flux2-vae.safetensors` | 321 MB |
| `wan_2.1_vae.safetensors` | 243 MB |

### loras/ (~9.8 GB)

| File | Size |
|------|------|
| `wan2.2_*_lightx2v_4steps_lora_*.safetensors` | 4.8 GB (4 files) |
| `Qwen-Image-Edit-Lightning-*.safetensors` | 1.6 GB (2 files) |
| `sd35_solarization*.safetensors` | 1.6 GB (5 files) |
| `sd3.5-large_cooked_negatives*.safetensors` | 1.6 GB (5 files) |
| `flux2_berthe_morisot.safetensors` | 373 MB |

---

## 6. Python Dependencies

See `requirements.txt` for the full list. Key packages:

| Package | Version | Purpose |
|---------|---------|---------|
| `torch` | 2.11.0.dev (nightly, cu130) | GPU compute (Blackwell CUDA 13.0) |
| `diffusers` | 0.36.0 | HuggingFace image/video/audio generation |
| `transformers` | 4.57.0 | Text encoders |
| `spacy` | 3.8.11 | NER for DSGVO check |
| `de_core_news_lg` | 3.8.0 | German NER model |
| `xx_ent_wiki_sm` | 3.8.0 | Multilingual NER model |

**PyTorch install (Blackwell GPUs):**
```bash
pip install --pre torch torchaudio torchvision --index-url https://download.pytorch.org/whl/nightly/cu130
```

**SpaCy models:**
```bash
python -m spacy download de_core_news_lg
python -m spacy download xx_ent_wiki_sm
```

Only these 2 SpaCy models are needed. Adding more causes cross-language false positives.

---

## Cloud API Models (not local)

These are accessed via API and do not require local storage:

| Config Variable | Model | Provider |
|----------------|-------|----------|
| `REMOTE_FAST_MODEL` | claude-haiku-4-5 | AWS Bedrock EU |
| `REMOTE_ADVANCED_MODEL` | claude-sonnet-4-5 | AWS Bedrock EU |
| `REMOTE_EXTREME_MODEL` | claude-opus-4-5 | AWS Bedrock EU |
| `REMOTE_MULTIMODAL_MODEL` | gemini-2.5-flash-lite | OpenRouter |
| `CODING_MODEL` | codestral-latest | Mistral API |

API keys stored in `devserver/*.key` files (gitignored).
