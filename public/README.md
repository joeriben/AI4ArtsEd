# AI4ArtsEd Frontend (New Architecture)

This directory contains the active frontend implementation(s) for the AI4ArtsEd DevServer.

## Architecture Principles

### Mandatory: Internationalization (i18n)

**ALL frontend code MUST be bilingual (German/English) and multilingual-ready.**

- ❌ **NEVER** hardcode German, English, or any language strings
- ✅ **ALWAYS** use language configuration dictionaries
- ✅ All UI strings pulled from i18n system

### Multiple Frontend Strategy

Different interfaces for different audiences:

1. **Advanced Frontend** - Full feature set with edit mode for advanced users
2. **Kids Frontend** - Simplified interface for younger users
3. **LLM-Dialog Frontend** - Conversational interface for alternative interaction

### Framework

Modern framework (React/Vue/Svelte) with:
- Built-in i18n support from day 1
- Workflow visualization (process steps as boxes)
- Real-time pipeline status polling
- Component-based architecture

## Backend API Integration

**Base URL:** `http://localhost:17801/api`

### Key Endpoints

- `POST /api/schema/pipeline/execute` - Execute pipeline, returns `run_id`
- `GET /api/pipeline/{run_id}/status` - Real-time status polling
- `GET /api/media/info/{prompt_id}` - Check media generation status
- `GET /api/media/image/{prompt_id}` - Serve generated images

### Real-time Polling

Frontend should:
1. Execute pipeline → receive `run_id`
2. Poll `/api/pipeline/{run_id}/status` every 1 second
3. Display progress: `stage`, `step`, `progress` percentage
4. Show entities as they complete
5. Stop when `current_state.stage === 'completed'`

## Development Status

**Current:** Empty - ready for new frontend development
**Last Updated:** 2025-11-05

## Related Documentation

- `docs/DEVELOPMENT_DECISIONS.md` - i18n requirements
- Backend polling API documented in LivePipelineRecorder

---

**Created:** 2025-11-05
