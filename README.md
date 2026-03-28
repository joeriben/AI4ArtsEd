# AI4ArtsEd_lab

**Pedagogical Experimentation Platform for Critical Engagement with Generative AI**

Version 2.1 | January 2026

---

## What is AI4ArtsEd_lab?

AI4ArtsEd_lab is a pedagogical platform that makes AI transformation transparent by separating the creative process into visible, editable steps. Designed for cultural education (ages 8-17), it treats generative AI not as a tool to be optimized, but as a subject of critical and creative exploration.

### Key Features

- **WAS/WIE Separation**: Ideas and transformation rules are entered separately
- **4-Stage Pipeline**: Visible processing with editable breakpoints (Translation → Interception → Safety → Generation)
- **LLM as Co-Actor**: AI contributions are visible, not hidden
- **Multi-Provider LLM Support**: Ollama, OpenRouter, AWS Bedrock, Mistral
- **SwarmUI Integration**: Professional image generation via ComfyUI workflows
- **LoRA Training Studio**: Create custom styles
- **Canvas Workflow System**: Visual node-based AI workflow builder (NEW)

---

## Documentation

### Quick Start

| I want to... | Read... |
|--------------|---------|
| Understand the system | [Technical Whitepaper](docs/TECHNICAL_WHITEPAPER.md) |
| Browse all documentation | [Documentation Index](docs/00_MAIN_DOCUMENTATION_INDEX.md) |
| Understand the pedagogy | [Pedagogical Concept](docs/PEDAGOGICAL_CONCEPT.md) |
| See what's new | [What's New (Jan 2026)](docs/WHATS_NEW_2026_01.md) |
| Find current tasks | [Development Todos](docs/devserver_todos.md) |

### Architecture

The complete architecture is documented in 24+ parts:

- **[PART 01](docs/ARCHITECTURE%20PART%2001%20-%204-Stage%20Orchestration%20Flow.md)**: 4-Stage Pipeline (AUTHORITATIVE)
- **[PART 02](docs/ARCHITECTURE%20PART%2002%20-%202-Architecture-Overview.md)**: System Overview
- **[PART 03](docs/ARCHITECTURE%20PART%2003%20-%20ThreeLayer-System.md)**: Three-Layer System
- **[Full Index](docs/00_MAIN_DOCUMENTATION_INDEX.md)**: All 24 parts

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Vue 3 Frontend                        │
│            (TypeScript, Composition API, i18n)           │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP/SSE
┌─────────────────────────▼───────────────────────────────┐
│                  Flask DevServer                         │
│         (Orchestration, Pipeline Execution)              │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼──────────┐      ┌───────────▼────────────────┐
│    LLM Providers    │      │   SwarmUI (Port 7801)      │
│  - Ollama (local)   │      │   ┌────────────────────┐   │
│  - OpenRouter       │      │   │     ComfyUI        │   │
│  - AWS Bedrock      │      │   │   (Workflows)      │   │
│  - Mistral          │      │   └────────────────────┘   │
└─────────────────────┘      └────────────────────────────┘
```

**Backend**: Python 3.13, Flask, SSE streaming
**Frontend**: Vue 3, TypeScript, Vite
**Generation**: SwarmUI + ComfyUI
**LLMs**: Multi-provider (local + cloud)

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
2. **Use `devserver-architecture-expert` agent** for questions
3. **Update `DEVELOPMENT_LOG.md`** after each session

### Key Principles

- **NO WORKAROUNDS**: Fix root problems, not symptoms
- **Consistency is crucial**: Follow existing patterns
- **Clean, maintainable code**: Top priority

### Running Tests

```bash
# Backend tests
cd devserver
pytest

# Frontend type checking
cd public/ai4artsed-frontend
npm run type-check
```

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

**Institution**: Friedrich-Alexander-Universität Erlangen-Nürnberg
**Research Group**: AI4ArtsEd
**Principal Investigator**: Prof. Dr. Benjamin Jörissen

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

AI4ArtsEd integrates and builds upon:
- [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI) - Stable Diffusion interface
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Node-based workflow system
- [Ollama](https://ollama.ai/) - Local LLM runtime
- [Vue 3](https://vuejs.org/) - Progressive JavaScript framework

---

**Version**: 2.1
**Last Updated**: January 2026
**Status**: Active Development

<sub>📝 *This README was created during Session 134 (January 2026).*</sub>
