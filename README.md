# UCDCAE AI LAB

**Pedagogical-Artistic Experimentation Platform for Critical Engagement with Generative AI**

Developed within the **AI4ArtsEd** and **COMeARTS** research projects at the [UNESCO Chair in Digital Culture and Arts in Education](https://cris.fau.de/projects/318044853/) (UCDCAE), Friedrich-Alexander-Universitat Erlangen-Nurnberg.

**Funded by the [Federal Ministry for Family Affairs, Senior Citizens, Women and Youth](https://www.bmfsfj.de/) (BMFSFJ)** as part of the research programme "Kulturelle Bildung in gesellschaftlichen Transformationen" (kubi-meta).

- **[AI4ArtsEd](https://kubi-meta.de/ai4artsed)** — Artificial Intelligence for Arts Education
- **[COMeARTS](https://comearts.eu)** — Community-Based Arts Projects

---

## What is the UCDCAE AI LAB?

The UCDCAE AI LAB is a pedagogical-artistic experimentation platform for the explorative use of generative artificial intelligence in cultural-aesthetic media education. It makes AI transformation transparent by separating the creative process into visible, editable steps. Designed for cultural education (ages 6-17), it treats generative AI not as a tool to be optimized, but as a subject of critical and creative exploration.

### Key Features

- **WAS/WIE Separation**: Ideas and transformation rules are entered separately
- **4-Stage Pipeline**: Visible processing with editable breakpoints (Translation → Interception → Safety → Generation)
- **LLM as Co-Actor**: AI contributions are visible, not hidden
- **Multi-Provider LLM Support**: Local (llama-cpp-python) and cloud (Mammouth, AWS Bedrock)
- **GPU Service**: Diffusers-based image generation (SD3.5) + ComfyUI fallback
- **Music Generation**: HeartMuLa integration for AI music creation
- **Canvas Workflow System**: Visual node-based AI workflow builder
- **Latent Lab**: Interactive experiments with diffusion model internals
- **9 Languages**: DE, EN, TR, KO, UK, FR, ES, HE, AR (with RTL support)

---

## Documentation

### Quick Start

| I want to... | Read... |
|--------------|---------|
| Understand the system | [Technical Whitepaper](docs/TECHNICAL_WHITEPAPER.md) |
| Understand the pedagogy | [Pedagogical Concept](docs/PEDAGOGICAL_CONCEPT.md) |

### Architecture

The complete architecture is documented in 24+ parts:

- **[PART 01](docs/ARCHITECTURE%20PART%2001%20-%204-Stage%20Orchestration%20Flow.md)**: 4-Stage Pipeline (AUTHORITATIVE)
- **[PART 02](docs/ARCHITECTURE%20PART%2002%20-%202-Architecture-Overview.md)**: System Overview
- **[PART 03](docs/ARCHITECTURE%20PART%2003%20-%20ThreeLayer-System.md)**: Three-Layer System

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Vue 3 Frontend                        │
│         (TypeScript, Composition API, i18n x9)           │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP/SSE
┌─────────────────────────▼───────────────────────────────┐
│                  Flask DevServer                         │
│      (4-Stage Orchestration, Pipeline Execution)         │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼──────────┐      ┌───────────▼────────────────┐
│   GPU Service       │      │      ComfyUI               │
│  (Port 17803)       │      │    (Port 17804)            │
│  - Diffusers (SD3.5)│      │    (Fallback path)         │
│  - HeartMuLa (Music)│      └────────────────────────────┘
│  - LLM (Safety)     │
│  - Stable Audio     │      ┌────────────────────────────┐
└─────────────────────┘      │    Cloud LLM Providers     │
                              │  - Mammouth (DSGVO)       │
                              │  - AWS Bedrock             │
                              └────────────────────────────┘
```

**Backend**: Python 3.13, Flask, SSE streaming
**Frontend**: Vue 3, TypeScript, Vite
**Generation**: Diffusers (SD3.5 Large) + ComfyUI fallback
**LLMs**: Local (llama-cpp-python) + Cloud (Mammouth, AWS Bedrock)

---

## Installation & Deployment

### Prerequisites

```bash
# Check prerequisites
./check_prerequisites.sh

# Download required models
./download_models.sh

# Install ComfyUI nodes
./install_comfyui_nodes.sh
```

### Development Mode

```bash
# Terminal 1: Start SwarmUI
./2_start_swarmui.sh

# Terminal 2: Start backend (port 17802)
./3_start_backend_dev.sh

# Terminal 3: Start frontend (port 5173)
./4_start_frontend_dev.sh
```

Access at: `http://localhost:5173`

### Production Mode

```bash
# Pull latest changes and deploy
./5_pullanddeploy.sh

# Or manually:
./2_start_swarmui.sh       # Terminal 1
./5_start_backend_prod.sh  # Terminal 2 (port 17801)
```

Access at: `http://localhost:17801`

**Port Configuration:**
- Development: Backend 17802, Frontend 5173
- Production: Backend 17801 (serves built frontend)

### Stop All Services

```bash
./1_stop_all.sh
```

---

## Project Structure

```
ai4artsed_development/
├── devserver/              # Flask backend
│   ├── config.py           # Central configuration
│   ├── my_app/
│   │   ├── routes/         # API endpoints
│   │   └── services/       # Business logic
│   └── schemas/
│       ├── chunks/         # Atomic operations
│       ├── pipelines/      # Chunk sequences
│       └── configs/        # Interception configs
├── public/ai4artsed-frontend/  # Vue 3 frontend
│   └── src/
│       ├── views/          # Page components
│       ├── components/     # Reusable components
│       └── stores/         # Pinia state
├── docs/                   # Architecture & guides
└── exports/                # Generated content
```

---

## Development Workflow

### Before Starting

1. **Consult architecture documentation** in `/docs`
2. **Record decisions** in `docs/DEVELOPMENT_DECISIONS.md`

### Key Principles

- **NO WORKAROUNDS**: Fix root problems, not symptoms
- **Consistency is crucial**: Follow existing patterns
- **Clean, maintainable code**: Top priority

### Running Tests

```bash
# DevServer tests (devserver/pytest.ini keeps testfiles/ out of the collection)
cd devserver
pytest

# GPU service tests
cd gpu_service
pytest tests

# Frontend unit tests and type checking
cd public/ai4artsed-frontend
npm run test:unit
npm run type-check
```

See `docs/ARCHITECTURE PART 14 - Testing.md` for the four suites and the pre-commit gates.

---

## License

This software is licensed under a **Source-Available Non-Commercial License**.

**Permitted:**
- Viewing and studying the source code
- Educational and non-commercial research purposes
- Personal experimentation and learning

**Prohibited:**
- Commercial use without explicit permission
- Redistribution or sublicensing
- SaaS/hosting services

For licensing inquiries and commercial use permissions, contact:
**benjamin.joerissen@fau.de**

See [LICENSE](LICENSE) for full terms.

---

## Research & Development

**Institution**: Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)
**Chair**: UNESCO Chair in Digital Culture and Arts in Education (UCDCAE)
**Principal Investigator**: Prof. Dr. Benjamin Jörissen
**Research Associate**: Vanessa Baumann

### Projects

- **[AI4ArtsEd](https://kubi-meta.de/ai4artsed)** — Artificial Intelligence for Arts Education. Explores opportunities, conditions, and limits of pedagogical use of AI in culturally diversity-sensitive settings of cultural education.
- **[COMeARTS](https://comearts.eu)** — Community-Based Arts Projects. European cooperation project for community-based artistic practice with digital media.

### Publications & Resources

- [Technical Whitepaper](docs/TECHNICAL_WHITEPAPER.md) - Complete system documentation
- [Pedagogical Concept](docs/PEDAGOGICAL_CONCEPT.md) - Theoretical foundation
- [Project Website Content](docs/PROJECT_WEBSITE_CONTENT.md) - Public-facing materials

---

## Contributing

This is a research project with a restrictive license. Contributions are currently limited to authorized collaborators.

For questions or collaboration inquiries, please contact:
**benjamin.joerissen@fau.de**

---

## Acknowledgments

The UCDCAE AI LAB integrates and builds upon:
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Node-based workflow system
- [Stable Diffusion 3.5](https://huggingface.co/stabilityai/stable-diffusion-3.5-large) - Image generation
- [HeartMuLa](https://github.com/nichuanfang/heartlib) - Music generation
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) - Local LLM inference
- [Vue 3](https://vuejs.org/) - Progressive JavaScript framework

## Funding

This project is funded by the **Federal Ministry for Family Affairs, Senior Citizens, Women and Youth (BMFSFJ)** as part of the research programme "Kulturelle Bildung in gesellschaftlichen Transformationen" ([kubi-meta](https://kubi-meta.de)).

---

**Last Updated**: April 2026
**Status**: Active Development
