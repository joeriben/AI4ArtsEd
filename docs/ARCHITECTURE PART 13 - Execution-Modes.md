# DevServer Architecture

**Part 13: Execution Modes**

---

## ⚠️ DEPRECATED (2025-11-23)

**This document is OBSOLETE.**

**Reason:** The execution_mode parameter system ('eco', 'fast', 'local', 'remote') has been COMPLETELY REMOVED from the codebase. Model selection is now handled CENTRALLY via `devserver/config.py` constants.

**Migration:** See `ARCHITECTURE PART 01 - Section 2: Model Selection Architecture` for the new centralized system.

**Retained for historical reference only.**

---


### Eco Mode (Default)

**Characteristics:**
- Uses local Ollama models
- Free (no API costs)
- Privacy-preserving (DSGVO-compliant)
- Slower inference (~2-5 seconds per request)
- Unlimited usage

**Model Examples:**
- mistral-nemo:latest (12B, general)
- llama3.2:latest (3B, fast)
- gemma2:9b (9B, quality)
- qwen2.5-translator (translation)

**Use Cases:**
- Workshops with students
- Experimentation
- Privacy-sensitive content
- High-volume usage

---

### Fast Mode

**Characteristics:**
- Uses cloud APIs (OpenRouter)
- Paid (API costs per request)
- Faster inference (~0.5-2 seconds)
- Higher quality outputs
- Rate limited by API provider

**Model Examples:**
- claude-3.5-haiku (fast, high quality)
- gemini-2.5-pro (advanced reasoning)
- mistralai/mistral-nemo (balanced)

**Use Cases:**
- Production deployments
- Time-sensitive tasks
- Quality-critical outputs
- Low-volume usage

**Exception:** Security and Vision tasks always use local models (DSGVO compliance)

---

