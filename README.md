# ATELIER — UCDCAE AI Lab

**AI Toolkit for Experiential Learning and Inquiry-based Educational Research**

Pedagogical-artistic experimentation platform of the [UNESCO Chair in Digital Culture and Arts in Education](https://www.ucdcae.fau.de/) (UCDCAE) at Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), for the explorative use of generative artificial intelligence in cultural-aesthetic media education.

ATELIER is a platform for inquiry-based learning with and about generative AI. In an adaptable environment, children, young people and adults learn to use generative AI and to question it critically. ATELIER opens the "black box" of AI and makes it accessible for art and teaching.

Developed within the research project **[AI4ArtsEd](https://kubi-meta.de/ai4artsed)** (Artificial Intelligence for Arts Education). AI4ArtsEd is funded by the German Federal Ministry of Education, Family Affairs, Senior Citizens, Women and Youth ([BMBFSFJ](https://www.bmfsfj.de/)), originally by the Federal Ministry of Education and Research (BMBF), within the funding priority "Kulturelle Bildung in gesellschaftlichen Transformationen" ([kubi-meta](https://kubi-meta.de)).

**ComeArts Across**, a subproject of [ComeArts](https://comearts.uni-due.de) in the competence network [lernen:digital](https://lernen.digital/), is responsible only for some multimodal modules: the cross-aesthetic modules in the Crossmodal Lab of the Latent Lab.

Code, paths and service names carry the identifier `ai4artsed`, after the AI4ArtsEd project in which the platform was developed.

---

## An Experimental System for Culture and Arts Education

Generative AI produces images, texts and music from statistical processing that is largely opaque. For Culture and Arts Education, the first question is therefore which relations young people enter into in the process, and only after that how they handle a tool. ATELIER is therefore not a production tool and not a learning environment like Moodle, but an experimental system for experiential learning and for asking generative AI inquiring questions.

## Prompt Interception: Decoupling Control from Output

Commercial generative AI treats a prompt as a command and the output as a result to be optimised. ATELIER places a step of its own between input and generation, the Prompt Interception: a language model reads the input through a perspective, a historical or contemporary position or stance that shapes, changes or questions the idea. The choices include the visual language of the Bauhaus, the poetry of Hölderlin, or a chain translation through several randomly chosen languages. Instead of offering style filters for copying the signature styles of famous artists, ATELIER relies on artistic positions: one perspective reads an input from a situation in which familiar meanings no longer hold, after historical Dadaism. Only then is an image, a sound, music, a 3D model or a video generated. The zone between idea and product becomes the place of learning.

## Flow: Visibility Instead of a Black Box

Why a model brings forth exactly this image cannot be traced in principle; ATELIER does, however, make the processing accessible as a process. The working surface Flow (`/x2x-flow`) is an open work area with a circle of action: whatever is placed in it, an idea as text, an image or a sketch, is processed. A run shows its stages: the rewriting by the perspective, safety check and translation, the medium, the generating model, the result. The rewritten text lies on the surface, editable, and the next run can start from it. The perspectives can be read and edited; one's own can be written and added.

## The Other Surfaces

- **Latent Lab** (`/latent-lab`). The Latent Lab carries the view of the process into the models. With 27 comparative and deconstructive instruments in six groups, the otherwise hidden intermediate stages of the models can be explored aesthetically through direct intervention. One example: several image models receive the same prompt once on its own and once with a culture in it, such as "Yoruba" or "Sámi". The six groups are Cultural Knowledge & Stereotypes, Diffusion Lab, Transformers Lab, Crossmodal Lab, Prompt Interception Lab and LoRA Training; the count covers their instruments, without the overview map.
- **LoRA Training**. A group trains an add-on to an image model with its own images, without changing the model itself. The training is a curatorial act: the selection of images decides which representations the model learns and which it does not. That it noticeably reduces the model's stereotypes is unlikely; the attempt itself is instructive, including its failure.
- **Together** (`/together`). Together accompanies teaching projects with AI in three phases: preparation, accompaniment in the course, follow-up. It lays generated fragments and small experimental set-ups built from the platform's working steps onto the shared surface as offers.
- **Contesting** (`/contesting`). A resistant counterpart: it makes itself known as a machine, does not generate on command, and decides itself whether and in which medium it generates something. Its resistance is meant to bring a group to articulate and justify its ideas. It does not simulate feelings or enthusiasm.
- **Canvas Workflow** (`/canvas`). A group connects working steps such as rewriting, translating, generating and evaluating into workflows of its own, also branched and in loops. An evaluating module can fail a text and send it, together with its reasons, down another path, for instance back to a rewriting or translation module. This makes it possible to try out what happens when models correct each other.

## Low-Threshold Use

- **Access.** Participants create no account and need no password; a browser on their devices is enough. In courses, a device signs in with a five-character place code; the place carries neither a name nor an email address.
- **Courses and perspectives.** Educators set up courses and places themselves (`/educator`) and decide until when a course is open. For each course they put together a selection of perspectives, including ones they have written themselves, without programming. Together accompanies them in planning.

## Responsible with Minors

Culture and Arts Education with generative AI for children and young people means a duty of care; ATELIER takes it on as a technical structure.

- **Youth protection.** The server enforces safety levels for children and young people. A course can only tighten the level an institution has set. In case of doubt, the strictest level applies.
- **Rewriting.** When a perspective is chosen, at these levels the Prompt Interception itself already rejects racist, dehumanising, terrorist, violence-glorifying, sexist or pornographic inputs, implied ones included. This also holds for a self-written perspective.
- **Checking texts and images.** When something is generated in Flow or in the Canvas Workflow, ATELIER first checks, at these levels, the text it is generated from for symbols punishable under § 86a of the German Criminal Code (StGB). It also checks this text and every generated image for violence, weapons, armed conflict, abuse, nudity, sexual content, racism, dehumanisation and terrorism, and for children also for depictions of horror. If the check cannot run, the image is held back.
- **Data protection.** Before the perspective in Flow rewrites an idea that was entered, ATELIER checks it on its own server for the full name of a private person, and holds it back if it recognises one or if the check cannot run; names from art and cultural history remain allowed. What a group changes in or adds to the text after the rewriting is no longer checked for this.
- **AI labelling.** By default, ATELIER writes a machine-readable label of their AI origin into generated images, videos, sounds and 3D models, under Article 50 of the AI Act, Regulation (EU) 2024/1689.
- **Research mode.** Under the license, the level without filters is reserved for research institutions with a documented research purpose, where applicable under the supervision of an ethics committee or a comparable body. Its outputs may never be shown to minors or to learners in an educational context. Anyone who uses Research mode outside research breaches the license, loses the royalty-free right of use and must expect a substantial claim for usage fees, in addition to further legal consequences.

## Participation and Sustainability

- **Ten languages.** The training data of widespread image AI comes predominantly from the English-language internet. ATELIER works in ten languages, two of them written from right to left: Arabic, Bulgarian, English, French, German, Hebrew, Korean, Spanish, Turkish and Ukrainian.
- **Energy and CO₂.** During a run in Flow on its own server, ATELIER shows how much power the graphics card draws and how much CO₂ that has caused, by estimate, since the run began. Resource consumption is part of education.
- **No feigned person.** Where the platform speaks in conversation, it speaks of itself in the third person, in the plural where needed: several separate models work in one conversational turn. When it speaks aloud, the voice changes from sentence to sentence between mixtures of preset voices; no mixture has a name or is a character.

## Connection to the AI Literacy Framework of the OECD and the EU

ATELIER supports 44 of the 57 learning scenarios of the new AILit framework (2026), in all four competence domains:

| Domain | Supported scenarios |
|---|---|
| Engage with AI | 15 of 21 |
| Create with AI | 12 of 12 |
| Manage AI | 9 of 12 |
| Shape AI | 8 of 12 |

16 scenarios run as described in the framework, 28 with a subject of their own. The mapping is the project's own, as of 27.09.2026; the counting basis is the framework's 57 learning scenarios, one per competence and level; the framework provides for adapting them to one's own subject (p. 25). Source: OECD / European Union (2026), *Empowering learners for the age of AI: An AI literacy framework for primary and secondary education*, OECD Publishing, Paris, https://doi.org/10.1787/65cd27d4-en (CC BY 4.0).

## Use in an Institution

- **License.** Free of charge for non-commercial educational institutions, for instance public schools, universities, museums, libraries and non-profit foundations. An institution may provide ATELIER internally. Whoever passes it on or operates it for other institutions needs written permission from the author; commercial use needs a written agreement with him. Details under [License](#license).
- **Own operation.** An institution can run all language models on its own server; ATELIER comes with ready-made presets for this. Whoever hands single working steps to external providers finds presets for providers in the EU and sees, for each provider, whether a GDPR status is recorded and which.
- **Technology.** For on-site operation, a Linux server with an NVIDIA graphics card of the type RTX 5090 or RTX PRO 6000 (see [Installation](#installation)).

ATELIER sees itself as a contribution to cultural resilience: the capacity of communities to co-determine their symbolic, artistic and pedagogical practices in techno-social environments themselves, also at the technical level.

Platform as of 18 October 2026.

---

## Four-Stage Processing

The processing of a prompt is built in four stages; depending on the filter level and the surface, a run can skip some of them. The DevServer orchestrates the stages; the pipeline executor carries out what a pipeline defines.

1. **Safety check of the input**, in the language it was written in: a filter for symbols prohibited under §86a StGB, and the detection of personal names (GDPR).
2. **Prompt Interception**: the step in which the platform writes a prompt over again through a perspective, the rules chosen or written for the run.
3. **Safety check before generation**, at every filter level below Adult; depending on the level and the surface, the model receives the prompt in English translation.
4. **Generation**, once per output configuration.

What runs is defined in three layers under `devserver/schemas/`: chunks (single operations), pipelines (sequences of chunks) and configs.

The installation is set to one of four filter levels: Kids, Youth, Adult or Research ([LICENSE.md](LICENSE.md), §3(e)). A course can set a stricter level than the installation, never a looser one. Research mode disables all safety mechanisms and may only be activated under the conditions of the license.

The platform marks the AI-generated images, videos, sounds and 3D models it hands out in the file itself, at the metadata layer; an invisible mark on images can be switched on. [ARCHITECTURE PART 36](docs/ARCHITECTURE%20PART%2036%20-%20Watermarking%20%26%20Provenance.md) gives the reasons, the cases without a mark, and the wording of Article 50 of Regulation (EU) 2024/1689.

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

We are glad to demonstrate ATELIER in 15 minutes, on site or online.

---

## Acknowledgments

The platform builds upon:
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI): node-based workflow system
- [Diffusers](https://github.com/huggingface/diffusers): diffusion pipelines
- [Transformers](https://github.com/huggingface/transformers): the local language and vision models
- [llama.cpp](https://github.com/ggml-org/llama.cpp): the safety classifier
- Generative models for images, video, sound, music, speech and 3D, among them Stable Diffusion 3.5, Flux 2, Qwen Image Edit, Wan 2.2, LTX Video, Stable Audio 3, [HeartMuLa](https://github.com/HeartMuLa/heartlib), VoxCPM2, Supertonic 3 and Hunyuan3D-2, and in the Crossmodal Lab [MMAudio](https://github.com/hkchengrex/MMAudio) and [ImageBind](https://github.com/facebookresearch/ImageBind)
- [Vue 3](https://vuejs.org/): progressive JavaScript framework

The models the platform uses are listed with their sources in [MODELS_REQUIRED.md](docs/installation/MODELS_REQUIRED.md).

## Funding

AI4ArtsEd (grant reference 01JKT2408A, 01/2024–12/2026) is funded by the **German Federal Ministry of Education, Family Affairs, Senior Citizens, Women and Youth (BMBFSFJ)**, originally by the Federal Ministry of Education and Research (BMBF), within the funding priority "Kulturelle Bildung in gesellschaftlichen Transformationen" ([kubi-meta](https://kubi-meta.de)).

ComeArts is part of the competence network [lernen:digital](https://lernen.digital/). It is financed by the European Union (NextGenerationEU) and funded by the BMBFSFJ.

---

**Last Updated**: October 2026
**Status**: Active Development
