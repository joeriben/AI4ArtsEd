# AI4ArtsEd DevServer Documentation

**Main Documentation Index**
**Last Updated:** 2026-04-21

---

## >>> AKTIVER PLAN <<<

**→ [docs/installation/CURRENT_DEPLOYMENT_PLAN.md](installation/CURRENT_DEPLOYMENT_PLAN.md)**

Multi-Tier-Installer-Strategie (Profile B/C/E, Werkraum für schwache Rechner, Cloud-Safety-Tradeoff für Profil C). Nicht umgesetzt — wartet auf Implementierungsstart. Vor jeder Änderung an `install.sh`, `check_prerequisites.sh`, `download_models.sh`, `install_systemd_services.sh` **zuerst diesen Plan lesen**.

---

## Quick Start

| Need to... | Read... |
|------------|---------|
| Understand the system | ARCHITECTURE PART 01 |
| See recent changes | WHATS_NEW_2026_01.md |
| Track development | DEVELOPMENT_LOG.md |
| Find current tasks | devserver_todos.md |
| Understand decisions | DEVELOPMENT_DECISIONS.md |

---

## Core Documentation

### Architecture (PART 01-24)

**Foundation:**
| Part | Title | Description |
|------|-------|-------------|
| 01 | 4-Stage Orchestration Flow | The core pipeline system + SSE Streaming (AUTHORITATIVE) |
| 02 | Architecture Overview | System-wide patterns |
| 03 | Three-Layer System | Chunks → Pipelines → Configs |
| 04 | Pipeline Types | Stage 2 pipeline capabilities |
| 05 | Pipeline-Chunk-Backend Routing | Request routing logic |
| 06 | Data Flow Patterns | How data moves through system |

**Engine & Backend:**
| Part | Title | Description |
|------|-------|-------------|
| 07 | Engine Modules | Core engine components |
| 08 | Backend Routing | SwarmUI, Ollama routing |
| 09 | Model Selection | LLM model configuration |
| 11 | API Routes | REST endpoint reference |
| 13 | Execution Modes | eco/fast mode system |

**Frontend:**
| Part | Title | Description |
|------|-------|-------------|
| 12 | Frontend Architecture | Vue component structure |
| 21 | Frontend Icons & Navigation | Material Design icon system |

**Testing & Deployment:**
| Part | Title | Description |
|------|-------|-------------|
| 14 | Testing | Test strategies |
| 15 | Key Design Decisions | Why things work this way |
| 17 | Documentation & Logging | Logging workflow |
| 18 | Data Storage & Persistence | Run folders, exports |

**Advanced:**
| Part | Title | Description |
|------|-------|-------------|
| 20 | Stage2 Pipeline Capabilities | Transform-only vs full pipelines |
| 22 | Legacy Workflow Architecture | SwarmUI workflow routing |
| 23 | LoRA Training Studio | Custom style training |
| 24 | SwarmUI Integration | Auto-recovery & health checks |
| 25 | Watermarking & Content Credentials | AI provenance tracking |
| 26 | Canvas Workflow System | Visual node-based workflow builder |
| 27 | VRAM Management & Model Preloading | Three-tier GPU/CPU/disk memory |
| 28 | Latent Lab | Deconstructive introspection: Image (Attention, Probing, Algebra, Denoising) + Text (RepEng, CKA, Bias Archaeology, LLM Interpretation) |
| **29** | **Safety System** | Levels, filters, enforcement points, legal basis (AUTHORITATIVE) |

---

## Development Tracking

### Active Development
- **DEVELOPMENT_LOG.md** - Chronological session log (Sessions 111-125)
- **devserver_todos.md** - Current tasks and priorities
- **DEVELOPMENT_DECISIONS.md** - Architectural decision records

### What's New
- **WHATS_NEW_2026_01.md** - January 2026 features changelog

### Session Handovers
Located in `docs/` root:
- HANDOVER_Session_*.md - Context for specific sessions

---

## Reference Documents

### Technical Specifications
- ARCHITECTURE_REQUIREMENTS.md - System requirements
- ARCHITECTURE_STAGE2_SEPARATION.md - Stage 2 design details

### Archived
Located in `docs/archive/`:
- SESSION_*_SUMMARY.md - Completed session summaries
- devserver_todos_sessions_1-14.md - Historical task tracking
- DEVELOPMENT_LOG_Sessions_1-110.md - Earlier sessions

---

## Key Concepts

### 4-Stage Pipeline
```
Stage 1: Translation + Safety Check
Stage 2: Prompt Interception (pedagogical transformation)
Stage 3: Pre-output Safety + Translation
Stage 4: Media Generation
```

### Lab Paradigm (Frontend Flow)
```
/interception → /optimize → /generation
     ↓              ↓            ↓
 Transform    Enhance text   Create media
```

### Three-Layer System
```
Chunks      → Atomic operations (translate, manipulate, generate)
Pipelines   → Ordered chunk sequences
Configs     → Pipeline + parameters + context
```

### Provenance Tracking (NEW)
All generated images automatically receive:
- **Invisible Watermark**: "AI4ArtsEd" embedded via DWT-DCT (no quality loss)
- **C2PA Ready**: Content Credentials infrastructure prepared

Verify watermark: `WatermarkService("AI4ArtsEd").extract_watermark(image_bytes)`

---

## File Locations

**Backend:**
```
devserver/
├── config.py                    # Central configuration
├── my_app/
│   ├── routes/                  # API endpoints
│   └── services/                # Business logic
└── schemas/
    ├── chunks/                  # Atomic operations
    ├── pipelines/               # Chunk sequences
    └── configs/                 # Interception configs
```

**Frontend:**
```
public/ai4artsed-frontend/src/
├── views/                       # Page components
├── components/                  # Reusable components
├── services/                    # API client
└── stores/                      # Pinia state
```

---

## Documentation Rules

1. **NO CREATIVE ENHANCEMENTS** - Architecture docs are authoritative
2. **PART 01 is AUTHORITATIVE** - 4-Stage flow is the source of truth
3. **Update DEVELOPMENT_LOG.md** - Document every session
4. **Use devserver-architecture-expert agent** - Before making changes

---

**Document Status:** Current and complete
**Next Review:** After Session 125+

---

<sub>📝 *This documentation was automatically generated by Claude Code during the Documentation Marathon (Session 126, January 2026).*</sub>
