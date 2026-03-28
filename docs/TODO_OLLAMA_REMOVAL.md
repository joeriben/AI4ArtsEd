# Ollama Removal — Handover-Todo

**Context**: Session 27.03.2026 hat Ollama durch in-process llama-cpp-python im GPU Service ersetzt (Commit `10a6dac`). Die Kern-Infrastruktur ist migriert, aber 188+ Referenzen verbleiben im Codebase.

**Grund**: Ollama 0.18.2 berechnet `default_num_ctx` aus TOTAL VRAM (95GB), nicht aus AVAILABLE. Auf der Blackwell RTX PRO 6000 allokierte es 28GB KV-Cache fuer ein 2B-Modell → 12 konsekutive OOM-Crashes.

---

## Bereits erledigt (Session 27.03.2026)

- [x] `gpu_service/services/llm_backend.py` — In-process LLM mit VRAM-Coordinator
- [x] `gpu_service/routes/llm_routes.py` — `/api/llm/chat`, `/api/llm/generate`
- [x] `devserver/my_app/services/llm_client.py` — Ruft GPU Service statt Ollama
- [x] `devserver/my_app/services/llm_service.py` — Ersetzt OllamaService
- [x] `devserver/my_app/utils/llm_watchdog.py` — Ersetzt ollama_watchdog
- [x] `devserver/config.py` — LLAMA_SERVER_URL + Backward-Aliases
- [x] `devserver/user_settings.json` — LLM_PROVIDER/LMSTUDIO entfernt
- [x] Settings-Routes, Training-Routes, VRAM-Monitor, Model-Selector Endpoints migriert

---

## P0: Frontend Settings-Page

### SettingsView.vue
- `ollamaModels` ref und `/api/settings/ollama-models` fetch → auf GPU Service `/api/llm/models` umstellen
- LLM Provider Dropdown (`<option value="ollama">Ollama</option>`) → entfernen, es gibt nur noch einen lokalen Provider
- "Ollama API URL" Eingabefeld → entfernen
- "LM Studio API URL" Eingabefeld → entfernen
- Datalist `ollama-models-*` → auf GPU Service Modelle umstellen

### BackendStatusTab.vue
- Ollama Status-Sektion (Zeilen 206-223) → auf GPU Service `/api/llm/health` + `/api/llm/models` umstellen

### TrainingView.vue
- `vramClearResult.ollama` Display → Umbenennen ("LLM" statt "Ollama")
- `unload_ollama: true` Payload-Key → `unload_llm: true`

### i18n (alle 9 Sprachen)
- `ollamaAvailable` Key → umbenennen oder entfernen
- `ollama: 'Ollama'` Label → entfernen
- **Regel**: Nur `en.ts` editieren, Work Order in `WORK_ORDERS.md`

---

## P1: Backend-Type System

### BackendType Enum (`backend_router.py`)
- `BackendType.OLLAMA = "ollama"` → `BackendType.LOCAL_LLM = "local_llm"` (oder equivalent)
- `initialize(self, ollama_service=None, ...)` → Parameter umbenennen
- Alle `BackendType.OLLAMA` Referenzen in pipeline_executor.py, schema_pipeline_routes.py

### Chunk JSON-Dateien
- `"backend_type": "ollama"` in 6 Chunk-JSONs → `"backend_type": "local_llm"`
  - `optimize_t5_prompt.json`
  - `optimize_clip_prompt_*.json` (3 Dateien)
  - `translate.json`
  - `manipulate.json` (pruefen)
- `"keep_alive": "10m"` in Chunk-JSONs → entfernen (llama-cpp-python hat kein keep_alive)

### Model Mapping Tables
- `OLLAMA_TO_OPENROUTER_MAP` → `LOCAL_TO_OPENROUTER_MAP` (config.py, model_selector.py)
- `OPENROUTER_TO_OLLAMA_MAP` → `OPENROUTER_TO_LOCAL_MAP`
- Alle Referenzen in workflow_logic_service.py, model_selector.py

---

## P2: Error Messages (User-Facing)

### schema_pipeline_routes.py
- `'DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte Ollama neustarten: sudo systemctl restart ollama'`
  → `'DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte GPU Service neustarten.'`
- Drei Stellen (Zeilen 1791, 2262, 2266)

### settings_routes.py
- `"error": "Ollama not running"` → `"error": "LLM backend not running"`

### training_routes.py / training_service.py
- `results["ollama"]` Key → `results["llm"]`
- `"Ollama not running (OK)"` → `"LLM not running (OK)"`

---

## P3: GPU Service Reste

### vlm_proxy_backend.py
- Direkter Ollama `/api/chat` Aufruf (Zeile 146) → auf llm_backend.chat() umstellen
- `keep_alive`-Logik entfernen
- `config.OLLAMA_API_URL` Referenzen

### gpu_service/config.py
- `OLLAMA_API_URL` → entfernen (LLM laeuft jetzt in-process)

### vram_coordinator.py
- `/api/ps` Aufruf an Ollama (Zeile 224) → entfernen (LLM-Modelle sind jetzt im Coordinator registriert)

### health_routes.py
- `if "ollama" in cmdline:` Prozess-Check → entfernen

---

## P4: Prompt Interception Engine

### prompt_interception_engine.py
- `self.ollama_models` → `self.local_models`
- `_call_ollama()` → `_call_local_llm()`
- `_find_ollama_fallback()` → `_find_local_fallback()`

### canvas_routes.py
- `ollama_count`, `get_ollama_models()` → umbenennen
- `f"local/{model_name}"` Prefix bleibt (das ist das Backend-Routing-Schema, nicht Ollama-spezifisch)

---

## P5: Config Cleanup

### devserver/config.py
- Backward-Aliases entfernen: `OLLAMA_TIMEOUT_SAFETY`, `OLLAMA_TIMEOUT_DEFAULT`, `OLLAMA_MAX_CONCURRENT`, `OLLAMA_API_BASE_URL`, `OLLAMA_TIMEOUT`
- Alle Caller auf `LLM_TIMEOUT_SAFETY`, `LLM_TIMEOUT_DEFAULT`, `LLM_MAX_CONCURRENT` umstellen
- `LLAMA_SERVER_URL` → kann auch weg (LLM ist jetzt im GPU Service, nicht separat)

### stage_orchestrator.py
- 8 Stellen mit `OLLAMA_TIMEOUT_SAFETY` → `LLM_TIMEOUT_SAFETY`

### schema_pipeline_routes.py
- `OLLAMA_MAX_CONCURRENT` → `LLM_MAX_CONCURRENT`
- `ollama_queue_semaphore` → `llm_queue_semaphore`

---

## P6: Setup & Tests

### 0_setup_ollama_watchdog.sh
- Umbenennen oder entfernen (Ollama systemd-Unit wird nicht mehr gebraucht)

### Test-Dateien
- `test_production_safety.py` — `check_ollama()` → GPU Service Health-Check
- `test_adversarial_safety_e2e.py` — `check_ollama_available()` → GPU Service
- `test_pipeline_execution.py` — `OllamaService` Import → `LLMService`

---

## P7: Dokumentation

Ollama-Referenzen in Docs sind historisch korrekt und koennen bleiben.
Nur aktive Anleitungen muessen aktualisiert werden:
- `README.md` — Port-Tabelle (11434 nicht mehr relevant)
- `README_INSTALL.md` — Ollama-Installationsanleitung entfernen
- `deployment/INSTALL_GUIDE.md` — Ollama-Setup entfernen
- `ARCHITECTURE PART 08` — Backend-Routing aktualisieren
- `ARCHITECTURE PART 31` — GPU Service Architektur aktualisieren

---

## Hinweise

- **`local/` Prefix bleibt** — das ist das Backend-Routing-Schema fuer lokale Modelle, nicht Ollama-spezifisch
- **Ollama systemd-Unit kann deaktiviert werden**: `sudo systemctl disable --now ollama`
- **Sudoers-Regel kann entfernt werden**: `sudo rm /etc/sudoers.d/ai4artsed-ollama`
- **GGUF-Modelle liegen in** `~/ai/llama-server-models/` (unabhaengig von Ollama-Blobs)
