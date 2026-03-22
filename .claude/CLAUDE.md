# AI4ArtsEd DevServer - Claude Instructions

## Core Architecture (Quick Reference)

### 4-Stage Orchestration (Overdrive Pipeline)
1. **Stage 1**: Translation + initial safety check
2. **Stage 2**: Prompt Interception (pedagogical transformation)
3. **Stage 3**: Safety validation + translation to English
4. **Stage 4**: Media generation (runs once per output_config)

**Key Pattern**: DevServer = Smart Orchestrator | PipelineExecutor = Dumb Engine

### Critical Concepts
- **Three-Layer System**: Chunks → Pipelines → Configs
- **Media-specific configs**: Use config ID (e.g., `sd35_large`), NOT pipeline name
- **Safety levels**: kids, youth, open (hardcoded in DevServer, not pipelines)
- **Model selection**: ~~Execution modes (eco/fast) REMOVED in Session 65~~ → Now centralized in `devserver/config.py` (STAGE1_MODEL, STAGE2_INTERCEPTION_MODEL, etc.)
- **Prompt Interception**: Pedagogical transformation, not optimization - DO NOT BREAK THIS

### File Locations
- **Schemas**: `my_app/config/*.json` (overdrive.json, kids.json, youth.json, open.json)
- **Routes**: `my_app/routes/schema_pipeline_routes.py` (orchestrator logic)
- **Pipelines**: `my_app/engine/pipeline_executor.py` (execution engine)
- **Configs**: `my_app/config/output_configs/*.json` (sd35_large.json, gpt5_image.json)

### Common Pitfalls
- ❌ Using pipeline name instead of config ID for Stage 4
- ❌ "Optimizing" Prompt Interception (breaks pedagogy)
- ❌ Adding redundant safety checks (already in DevServer)
- ❌ Treating DevServer as a CRUD app (it's a pedagogical tool)

### Vue Naming Convention for Stage2 Pipelines (CRITICAL)

**Principle**: Jede Vue-Komponente für Stage2-Pipelines wird EXAKT nach der Pipeline benannt.

**Beispiele**:
- Pipeline: `text_transformation` → Vue: `text_transformation.vue`
- Pipeline: `text_transformation_recursive` → Vue: `text_transformation_recursive.vue`
- Pipeline: `vector_fusion_generation` → Vue: `vector_fusion_generation.vue`

**Architekturprinzip**: Stage2-Pipelines bestimmen den kompletten Flow, den DevServer orchestriert - nicht DevServer, nicht Frontend. Die Pipeline ist die Single Source of Truth für:
- Welche Chunks ausgeführt werden
- In welcher Reihenfolge
- Mit welcher Struktur (sequential, recursive, etc.)

DevServer orchestriert, was die Pipeline definiert.
Frontend visualisiert, was die Pipeline strukturiert.

### Deployment Architecture (November 2025)

**Single Directory Approach:**
- **Location**: `~/ai/ai4artsed_webserver/` (no /opt/ production directory)
- **PORT Configuration**: config.py has PORT=17802 (default), production script exports PORT=17801
- **Branch Strategy**: develop (work) → main (production), always fast-forward merge (`git merge --ff-only develop` on main)
- **Frontend Build**: `/dist` is gitignored, must be built locally before deployment
- **No Merge Conflicts**: PORT override via environment variable, not hardcoded per branch

**Key Change from Previous Architecture:**
- ❌ OLD: Two directories (`~/ai/` dev + `/opt/` prod) with PORT conflicts
- ✅ NEW: One directory, startup script determines runtime mode

## Documentation
- **For architecture details**: See `docs/ARCHITECTURE PART 01-20.md`
- **For current tasks**: See `docs/devserver_todos.md`
- **For decisions**: See `docs/DEVELOPMENT_DECISIONS.md`
- **For history**: See `DEVELOPMENT_LOG.md`

## Available Agents (Always consult before coding!)
- `devserver-architecture-expert` - Architecture questions
- `vue-education-designer` - Frontend/UI issues
- `documentation-curator` - Documentation organization
- `cloudflare-tunnel-expert` - Port/routing/404 issues

## Rules
1. **NO CODE CHANGES WITHOUT USER CONSULTATION** (especially when starting fresh)
2. **ALWAYS UPDATE** `DEVELOPMENT_LOG.md` at end of session
3. **NO WORKAROUNDS**: Fix root problems, not symptoms
4. **CONSISTENCY IS CRUCIAL**: Follow existing patterns
5. **MANDATORY: CONSULT DOCUMENTATION BEFORE CODING**
   - Architecture documentation exists in `/docs` (ARCHITECTURE PART 01-20.md, dev logs, design decisions)
   - ALWAYS use `devserver-architecture-expert` agent for questions about the system
   - Read relevant documentation BEFORE making architectural decisions or code changes
6. **VUE TYPE CHECK**: When programming Vue pages, ALWAYS run `npm run type-check` and fix any type errors before considering the task complete
7. **NO COLORED BACKGROUNDS**: All page backgrounds MUST be black (`#0a0a0a`). Blue gradients, colored gradients, or any non-black backgrounds are FORBIDDEN. This has been violated repeatedly — do not introduce them.
8. **GIT MERGE STRATEGY**: When merging develop→main, ALWAYS use `git merge --ff-only develop` (fast-forward only). This prevents merge-commit noise that causes "develop is N commits behind main". If ff-only fails, rebase develop onto main first.
9. **i18n WORKFLOW**: When adding or modifying user-facing strings:
   - Edit ONLY `src/i18n/en.ts` (English). NEVER edit de/tr/ko/uk/fr.ts directly.
   - Append a work order to `src/i18n/WORK_ORDERS.md` listing all new/changed keys with context.
   - The `i18n-translator` agent handles all non-English translations in batch.
   - Fallback to English works at runtime, so English-only keys are immediately functional.
10. **CONCURRENT SESSION AWARENESS**: Before committing, check `git status` and `git log` for changes from other sessions running in parallel. NEVER stage or commit files you didn't modify. If you see unexpected changes (from another Claude session or the user), ASK before including them in your commit.
11. **WORKSHOP REPLAY SCRIPTS** (in `devserver/testfiles/simulate_workshop_*.py`):
    - **ORIGINAL PROMPTS ONLY**: Extract REAL prompts from the backend log (`[CHUNK-CONTEXT] input_text:` for pre-interception German, `[STAGE4-GEN]` for passthrough configs). NEVER invent synthetic prompts.
    - **CHECK EVERY CONFIG'S INPUT REQUIREMENTS**: Image-to-image (`qwen_img2img`) AND image-to-video (`wan22_i2v_video`) BOTH need `input_image`. Read the output config JSON and chunk to understand what parameters each config needs. Don't assume text-only.
    - **VERIFY ALL BACKENDS BEFORE RUNNING**: Check ComfyUI (`127.0.0.1:17804/system_stats`), GPU Service (`localhost:17803`), and DevServer are running. DevServer has COMFYUI-MANAGER auto-start but verify anyway.
    - **Template**: Follow `simulate_workshop_260306.py` structure exactly.
