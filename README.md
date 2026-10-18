# ATELIER — UCDCAE AI Lab

**AI Toolkit for Experiential Learning and Inquiry-based Educational Research**

Pedagogical-artistic experimentation platform of the [UNESCO Chair in Digital Culture and Arts in Education](https://www.ucdcae.fau.de/) (UCDCAE) at Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), for the explorative use of generative artificial intelligence in cultural-aesthetic media education.

Developed within the research project **[AI4ArtsEd](https://kubi-meta.de/ai4artsed)** (Artificial Intelligence for Arts Education). AI4ArtsEd is funded by the German Federal Ministry of Education, Family Affairs, Senior Citizens, Women and Youth ([BMBFSFJ](https://www.bmfsfj.de/)), originally by the Federal Ministry of Education and Research (BMBF), within the funding priority "Kulturelle Bildung in gesellschaftlichen Transformationen" ([kubi-meta](https://kubi-meta.de)).

**ComeArts Across**, a subproject of [ComeArts](https://comearts.uni-due.de) in the competence network [lernen:digital](https://lernen.digital/), is responsible only for some multimodal modules: the cross-aesthetic modules in the Crossmodal Lab of the Latent Lab.

Code, paths and service names carry the identifier `ai4artsed`, after the AI4ArtsEd project in which the platform was developed.

---

## Purpose

The platform was developed for Culture and Arts Education. It is tried out in workshops with children and young people and developed further on the basis of that experience. Its aim is to make the process of image generation visible, understandable and shapeable, and to treat generative AI as a subject of critical and creative exploration.

The [Pedagogical Concept](docs/PEDAGOGICAL_CONCEPT.md) (German) names six design principles:

1. **Separation of WHAT and HOW**: the idea and the rules are entered separately.
2. **The language model as co-actor**: the language model is a visible co-designer, not invisible magic.
3. **Visibility of processing**: every intermediate step can be observed and changed.
4. **Critical exploration**: the limits and peculiarities of the models are explored.
5. **Circularity**: iteration and reuse instead of linear production.
6. **Pedagogical accompaniment**: the platform unfolds its value through reflective accompaniment.

---

## Surfaces

The start page leads to five surfaces:

| Surface | Route | Description |
|---|---|---|
| **Together** | `/together` | Planning a workshop, holding it, looking back at it |
| **Contesting** | `/contesting` | Challenging and sharpening ideas |
| **Flow** | `/x2x-flow` | Bringing ideas together on one surface and working on them |
| **Latent Lab** | `/latent-lab` | Making the workings of generative AI reachable |
| **Canvas** | `/canvas` | Composing AI building blocks freely — with branches and loops |

The Latent Lab groups its instruments under six titles: Cultural Knowledge & Stereotypes, Prompt Interception Lab, Diffusion Lab, Transformers Lab, Crossmodal Lab and LoRA Training.

Educators manage courses at `/educator`.

The interface is available in ten languages: Arabic, Bulgarian, English, French, German, Hebrew, Korean, Spanish, Turkish and Ukrainian, with Arabic and Hebrew set right to left.

---

## Four-Stage Processing

The processing of a prompt is built in four stages; depending on the filter level and the surface, a run can skip some of them. The DevServer orchestrates the stages; the pipeline executor carries out what a pipeline defines.

1. **Safety check of the input**, in the language it was written in: a filter for symbols prohibited under §86a StGB, and the detection of personal names (GDPR).
2. **Prompt Interception**: the step in which the platform writes a prompt over again through a perspective, the rules chosen or written for the run.
3. **Safety check before generation**, at every filter level below Adult; depending on the level and the surface, the model receives the prompt in English translation.
4. **Generation**, once per output configuration.

What runs is defined in three layers under `devserver/schemas/`: chunks (single operations), pipelines (sequences of chunks) and configs.

The installation is set to one of four filter levels: Kids (ages 8–12), Youth (ages 13–17), Adult or Research ([LICENSE.md](LICENSE.md), §3(e)). A course can set a stricter level than the installation, never a looser one. Research mode disables all safety mechanisms and may only be activated under the conditions of the license.

The platform marks the AI-generated images, videos and audio files it hands out in the file itself, at the metadata layer; an invisible mark on images can be switched on. [ARCHITECTURE PART 36](docs/ARCHITECTURE%20PART%2036%20-%20Watermarking%20%26%20Provenance.md) gives the reasons, the cases without a mark, and the wording of Article 50 of Regulation (EU) 2024/1689.

---

## Architecture

```
Browser: Vue 3 frontend (TypeScript, Vite, Pinia, vue-i18n)
    │ HTTP, SSE
DevServer: Flask on Waitress (devserver/), port 17801 in production, 17802 in development
    │ orchestrates the four stages, holds the GPU admission gate
    ├── ComfyUI (port 17804): the generation workflows, and the platform's own nodes
    │   (comfyui_nodes/), among them those for the local language and vision models
    ├── GPU service (port 17803, gpu_service/): Diffusers pipelines and further models
    │   outside ComfyUI, among them the safety classifier
    ├── VoxCPM worker (port 17805, voxcpm_service/): the speech model VoxCPM2
    └── external providers: OpenRouter, Anthropic, OpenAI, Mistral AI, IONOS,
        Mammouth AI, AWS Bedrock
```

The GPU admission gate in the DevServer admits the heavy operations of the processes that share the graphics card one at a time. [ARCHITECTURE PART 40](docs/ARCHITECTURE%20PART%2040%20-%20GPU-Admission-Gate.md) describes the rule and its exceptions.

---

## Installation

The platform runs on NVIDIA Blackwell GPUs (compute capability 12.0, `sm_120`): RTX 5090 or RTX PRO 6000 Blackwell. The canonical installation is a headless Ubuntu 26.04 LTS server.

| Document | Content |
|---|---|
| [UBUNTU_SERVER_FRESH_INSTALL.md](docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md) | Installation phase by phase, as a fresh install or as a migration from an existing server |
| [SYSTEM_REQUIREMENTS.md](docs/installation/SYSTEM_REQUIREMENTS.md) | Hardware requirements |
| [MODELS_REQUIRED.md](docs/installation/MODELS_REQUIRED.md) | Model files, sizes and sources |

`README_INSTALL.md` and the documents marked deprecated in [docs/installation/README.md](docs/installation/README.md) describe an earlier stack.

Helper scripts in the repository root:

| Script | Purpose |
|---|---|
| `check_prerequisites.sh` | Checks the system requirements, including the compute capability |
| `setup.sh` | Creates the venv, installs the Python dependencies, creates the exports directory, builds the frontend |
| `download_*.sh` | Download model weights, benchmark datasets and source documents, one script per group |
| `install_comfyui_nodes.sh` | Installs the ComfyUI custom nodes, the platform's own among them |
| `install_systemd_services.sh` | Installs the systemd units for the GPU service, the DevServer and cloudflared |
| `update.sh` | Pulls the latest code, updates the dependencies, rebuilds the frontend, restarts the DevServer unit |

---

## Operation

In operation, the GPU service and the DevServer run as systemd units (`ai4artsed-gpu`, `ai4artsed-backend`). The DevServer starts ComfyUI when a call that needs it finds it unreachable (`COMFYUI_AUTO_START` in `devserver/config.py`); where ComfyUI runs as a unit of its own, it is `ai4artsed-comfyui`. `0_start_all.sh` starts the three units through `systemctl`; `1_stop_all.sh` stops them, together with the frontend dev server and the app tunnel.

Starting single services by hand:

| Script | Port | Service |
|---|---|---|
| `2_start_gpu_service.sh` | 17803 | GPU service |
| `2_start_comfyui.sh` | 17804 | ComfyUI |
| `2_start_voxcpm.sh` | 17805 | VoxCPM worker |
| `3_start_backend_dev.sh` | 17802 | DevServer, development |
| `4_start_frontend_dev.sh` | 5173 | Builds the frontend, then starts the Vite dev server |
| `5_start_backend_prod.sh` | 17801 | DevServer, production; serves the built frontend |

Development: `http://localhost:5173`. Production: `http://localhost:17801`.

On the production machine, `5_pullanddeploy.sh` pulls `main`, builds the frontend and restarts the systemd units.

---

## Project Structure

```
devserver/                  Flask backend (DevServer)
├── config.py               central configuration
├── config/                 tables: external providers, local model weights, backends, model register and others
├── my_app/
│   ├── routes/             API endpoints
│   ├── services/           business logic
│   └── knowledge/          platform descriptions and the reference library
├── schemas/
│   ├── chunks/             single operations
│   ├── pipelines/          sequences of chunks
│   ├── configs/            interception, pre-interception, pre-output, output and user configs
│   └── engine/             pipeline executor and stage orchestration
└── tests/                  test suite
gpu_service/                GPU service (port 17803)
comfyui_nodes/              the platform's own ComfyUI nodes
voxcpm_service/             VoxCPM worker (port 17805)
public/ai4artsed-frontend/  Vue 3 frontend
└── src/
    ├── views/              page components
    ├── components/         reusable components
    ├── stores/             Pinia state
    └── i18n/               interface languages
deployment/                 pinned requirements and install instructions
scripts/                    repository tools and git hooks
docs/                       architecture, decisions, installation
exports/                    runs and generated media (not in git)
```

---

## Development

### Documentation

- **Architecture**: `docs/ARCHITECTURE PART NN - <subject>.md`, among them [PART 01](docs/ARCHITECTURE%20PART%2001%20-%204-Stage%20Orchestration%20Flow.md) (four-stage orchestration), [PART 03](docs/ARCHITECTURE%20PART%2003%20-%20ThreeLayer-System.md) (three-layer system), [PART 24](docs/ARCHITECTURE%20PART%2024%20-%20ComfyUI-Integration.md) (ComfyUI), [PART 26](docs/ARCHITECTURE%20PART%2026%20-%20Canvas-Workflow-System.md) (Canvas), [PART 28](docs/ARCHITECTURE%20PART%2028%20-%20Latent-Lab.md) (Latent Lab), [PART 31](docs/ARCHITECTURE%20PART%2031%20-%20GPU-Service.md) (GPU service), [PART 37](docs/ARCHITECTURE%20PART%2037%20-%20t2x-Flow-Assemblage.md) (Flow), [PART 40](docs/ARCHITECTURE%20PART%2040%20-%20GPU-Admission-Gate.md) (GPU admission gate)
- **Decisions**: [docs/DEVELOPMENT_DECISIONS.md](docs/DEVELOPMENT_DECISIONS.md)
- **Interface elements**: [docs/ELEMENT_STRUCTURE_REGISTRY.md](docs/ELEMENT_STRUCTURE_REGISTRY.md)
- **Interface copy**: [docs/COPY_RULES.md](docs/COPY_RULES.md)

### Key Principles

- **NO WORKAROUNDS**: Fix root problems, not symptoms
- **Consistency is crucial**: Follow existing patterns
- **Clean, maintainable code**: Top priority

### Running Tests

From the repository root:

```bash
# DevServer tests (devserver/pytest.ini keeps testfiles/ out of the collection)
(cd devserver && pytest)

# GPU service tests
(cd gpu_service && pytest tests)

# Frontend unit tests and type checking
(cd public/ai4artsed-frontend && npm run test:unit && npm run type-check)
```

See `docs/ARCHITECTURE PART 14 - Testing.md` for the four suites and the pre-commit gates.

---

## License

The software is source-available under the license in [LICENSE.md](LICENSE.md) (version 1.0, February 2026). The German version is legally binding.

**Permitted:**
- Downloading the software and studying the source code
- Installation and use by non-commercial educational institutions in their educational offerings
- Referencing and citing the software in academic publications, and installing and using it for non-commercial scientific purposes

**Not permitted without written permission of the author:**
- Modifying, adapting or extending the software, or creating derivative works (§3(a); permission or a Contributor License Agreement, §5)
- Redistributing, publishing or mirroring it (§3(b)); internal provision within one non-commercial educational institution is excepted

**Commercial use** requires a separate written agreement with the author (§3(c)). Every use credits the author and carries the designation "AI Lab of the UNESCO Chair in Digital Culture and Arts in Education" (§3(d)).

Requests for permissions and commercial use: **benjamin.joerissen@fau.de**

Third-party assets: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)

---

## Research & Development

**Institution**: Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)
**Chair**: UNESCO Chair in Digital Culture and Arts in Education (UCDCAE)
**Project Lead**: Prof. Dr. Benjamin Jörissen
**Research Associate**: Vanessa Baumann

### Projects

- **[AI4ArtsEd](https://kubi-meta.de/ai4artsed)** — Artificial Intelligence for Arts Education. Explores opportunities, conditions, and limits of pedagogical use of AI in culturally diversity-sensitive settings of Culture and Arts Education.
- **ComeArts Across**, a subproject of [ComeArts](https://comearts.uni-due.de) — responsible only for the cross-aesthetic modules in the Crossmodal Lab of the Latent Lab.

### Publications

The publications that document the educational-theoretical foundations of the software are listed in the preamble of [LICENSE.md](LICENSE.md).

---

## Contributing

This is a research project with a restrictive license. Contributions are currently limited to authorized collaborators.

For questions or collaboration inquiries, please contact:
**benjamin.joerissen@fau.de**

---

## Acknowledgments

The platform builds upon:
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI): node-based workflow system
- [Diffusers](https://github.com/huggingface/diffusers): diffusion pipelines
- [Transformers](https://github.com/huggingface/transformers): the local language and vision models
- [llama.cpp](https://github.com/ggml-org/llama.cpp): the safety classifier
- [Stable Diffusion 3.5](https://huggingface.co/stabilityai/stable-diffusion-3.5-large): image generation
- [HeartMuLa](https://github.com/HeartMuLa/heartlib): music generation
- [MMAudio](https://github.com/hkchengrex/MMAudio): audio for images and video
- [ImageBind](https://github.com/facebookresearch/ImageBind): multimodal embeddings
- [Vue 3](https://vuejs.org/): progressive JavaScript framework

The models the platform uses are listed with their sources in [MODELS_REQUIRED.md](docs/installation/MODELS_REQUIRED.md).

## Funding

AI4ArtsEd is funded by the **German Federal Ministry of Education, Family Affairs, Senior Citizens, Women and Youth (BMBFSFJ)**, originally by the Federal Ministry of Education and Research (BMBF), within the funding priority "Kulturelle Bildung in gesellschaftlichen Transformationen" ([kubi-meta](https://kubi-meta.de)).

ComeArts is part of the competence network [lernen:digital](https://lernen.digital/). It is financed by the European Union (NextGenerationEU) and funded by the BMBFSFJ.

---

**Last Updated**: October 2026
**Status**: Active Development
