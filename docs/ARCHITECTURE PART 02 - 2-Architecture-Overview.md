# DevServer Architecture

**Part 2: 2. Architecture Overview**

---


### Core Principle: Clean Three-Layer Architecture + Input-Type Pipelines

DevServer implements a **template-based pipeline system** with three distinct layers and **input-type-based pipeline routing**:

```
┌─────────────────────────────────────────────────────────┐
│                    Layer 3: CONFIGS                     │
│              (User-Facing Content + Metadata)           │
│  • Display names, descriptions, categories              │
│  • Complete instruction text (context field)            │
│  • Parameters, media preferences, backend selection     │
│  • 34+ configs in schemas/configs/*.json                │
└─────────────────────────────────────────────────────────┘
                            ↓ references
┌─────────────────────────────────────────────────────────┐
│                  Layer 2: PIPELINES                     │
│         (Input-Type-Based Orchestration)                │
│  • Chunk sequences (NO content, only structure)         │
│  • Differentiate by INPUT type (not output/backend)     │
│  • 4 core pipelines in schemas/pipelines/*.json         │
└─────────────────────────────────────────────────────────┘
                            ↓ uses
┌─────────────────────────────────────────────────────────┐
│                   Layer 1: CHUNKS                       │
│              (Primitive Operations)                     │
│  • Template strings with {{PLACEHOLDERS}}               │
│  • Backend type (ollama/comfyui/openrouter)             │
│  • Task-type metadata for model selection               │
│  • 3 chunks in schemas/chunks/*.json                    │
└─────────────────────────────────────────────────────────┘
```

**Design Principles:**
1. **No Fourth Layer:** Content belongs in configs, not external registries
2. **Input-Type Pipelines:** Pipelines categorized by what they consume, not what they produce
3. **Backend Transparency:** Same pipeline can use ComfyUI, OpenRouter, or Ollama
4. **Media Transparency:** Same pipeline can generate image, audio, or video
5. **Separation of Concerns:** Text transformation ≠ Media generation

---

