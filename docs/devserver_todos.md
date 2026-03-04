# DevServer Implementation TODOs
**Last Updated:** 2026-03-02
**Context:** Current priorities and active TODOs

---

## ✅ Kürzlich erledigt (Kurzreferenz)

| Session | Datum | Was |
|---------|-------|-----|
| 235 | 2026-03-02 | Proxy-Chunk-Pattern Elimination + Router Cleanup |
| 234 | 2026-03-01 | LoRA Support for Diffusers GPU Service |
| ~234 | 2026-03-01 | SpaCy Startup-Check + Prerequisites Script |
| 229 | 2026-02-27 | IONOS AI Model Hub Integration |
| 228 | 2026-02-27 | Diffusers JSON→Python Chunk Migration (8 Chunks) |
| 227-229 | 2026-02-26 | T5 Interpretability Research (Code + Analyse complete) |
| 203 | 2026-02-23 | T5 Interpretability Research — 7-Phase Pipeline implementiert |
| 202 | 2026-02-23 | LLM Inference Migration — Ollama → GPU Service |
| 201 | 2026-02-23 | Hebrew + Arabic RTL Support (9 Sprachen, CSS logical properties) |
| 199 | 2026-02-23 | i18n Split — per-language files + Batch Translation Workflow |

---

## 🔴 CRITICAL: Architektur-Verletzungen

### Remaining Router Cleanup (ex Output-Chunks + Proxy-Chunk)

**Datum:** 2026-02-02 | **Aktualisiert:** 2026-03-02
**Kontext:** Proxy-Chunk-Pattern ✅ eliminiert (Session 235), Diffusers-Chunk-Migration ✅ done (Session 228). Restarbeit:

- ✅ `_process_heartmula_chunk()` — bereits entfernt (Python-Chunk `output_music_heartmula.py` aktiv)
- `_process_stable_audio_chunk()` — GPU Service nutzt bereits Diffusers (`stable_audio_backend.py`), aber Chunk ist noch JSON (`output_audio_stableaudio_diffusers.json`). Migration: JSON→Python-Chunk, dann Router-Methode entfernen. ComfyUI-Pfad (`output_audio_stableaudio.json`) bleibt JSON.
- ✅ `_process_triton_chunk()` — deprecated, nie implementiert. Zwei tote Referenzen im Router (Enum + DIRECT_BACKENDS) können bei Gelegenheit entfernt werden.
- ComfyUI-Workflow-Logik (`_process_workflow_chunk()`, `_process_image_chunk_simple()`, `_build_simple_t2i_workflow()`, `_inject_lora_nodes()`, `_apply_encoder_type()`) — **nicht** in Python-Chunks migrieren (JSON-Graph-basiert, würde Infrastruktur duplizieren). Stattdessen: in zentrale `comfyui_handler.py` extrahieren, Router ruft nur noch Handler auf.

**Plan-Referenz:** `docs/plans/diffusers-chunk-migration.md`

---

## 🔴 HIGH Priority

### Video Generation Wan 2.1 — PoC pending

**Datum:** 2026-02-15
**Plan:** `docs/plans/video_generation_wan21_diffusers.md`

Code komplett implementiert. Was noch fehlt:

1. PoC-Test: `venv/bin/python test_wan21_video.py` — wartet auf Modell-Download
2. 1.3B-Modell: Download prüfen (`ls ~/.cache/huggingface/hub/models--Wan-AI--Wan2.1-T2V-1.3B-Diffusers/snapshots/`)
3. Integration Test: GPU Service → DevServer → Video Pipeline end-to-end
4. Frontend: Vue-Komponente für Video-Anzeige

### Canvas Execution Feedback

**Datum:** 2026-01-26 (Session 136)

User starren 5+ Minuten auf den Bildschirm ohne Feedback. Minimum: Spinner/"Generating..." während Execution. Ideal: SSE-Stream mit Live-Updates (Node X von Y, aktueller Stage).

**Technische Optionen:**
- **Option A: Polling** — Frontend pollt `/api/canvas/status/{run_id}` alle 2s
- **Option B: SSE Stream** — Backend sendet `node_started`, `node_completed`, `error` Events

**Betroffene Dateien:**
- `devserver/my_app/routes/canvas_routes.py`
- `public/ai4artsed-frontend/src/stores/canvas.ts`
- `public/ai4artsed-frontend/src/views/canvas_workflow.vue`

### Safety-Architektur Refactoring

**Datum:** 2026-01-26
**Handover:** `docs/HANDOVER_SAFETY_REFACTORING.md`
**Regression-Bugs** (fail-open parse, fail-open pipeline, JSON-Requirement): ✅ GEFIXT

1. **KRITISCH: context_prompt nicht geprüft** — User-editierbarer Meta-Prompt wird nirgends safety-geprüft
2. **Namens-Inkonsistenz**: `/interception` macht Stage 1 + Stage 2 (Architektur korrekt, Name irreführend)
3. **Code-Duplikation**: Stage 1 Safety in 4 Endpoints embedded (Funktionen zentralisiert, Callsites noch 4x)
4. ✅ ~~**Frontend Bug**: MediaInputBox ignoriert 'blocked' SSE Events~~ — gefixt (Handler Zeile 528-538)

### Stage 3 Negative Prompts nicht an Stage 4 weitergereicht

**Datum:** 2025-11-20 (Session 53) — **Bug besteht weiterhin** (Stand 2026-02-23 verifiziert)

Stage 3 generiert Negative Prompts basierend auf Safety Level (kids/youth), aber diese werden nie an Stage 4 übergeben:
- `safety_result['negative_prompt']` wird gespeichert aber nie verwendet
- Alle SD3.5 Images nutzen nur den hardcodierten Default: `"blurry, bad quality, watermark, text, distorted"`
- Kids/youth Safety-Filter sind damit nicht voll wirksam

**Fix:** `safety_result['negative_prompt']` an `pipeline_executor.execute_pipeline()` in Stage 4 übergeben.

### Frontend bleibt im Loading-State bei Backend-Fehler (Expert Mode)

**Datum:** 2026-02-28
**Status:** Offen

Wenn Stage 4 fehlschlägt (z.B. ComfyUI-Timeout), bleibt das Frontend in der Model-Card ("Modell wird geladen") hängen. Der `stage4_error` SSE-Event kommt nicht durch oder wird nicht behandelt. `isExecuting` wird nie auf `false` gesetzt. Zusätzlich: Model-Card-Höhe stimmt nicht mit MediaOutputBox-Höhe überein.

Zu untersuchen:
- Wie propagiert `schema_pipeline_routes.py` den Fehler via SSE?
- Wie reagiert die View (text_transformation.vue etc.) auf Error-Events?
- Wird `isExecuting` bei Fehler zurückgesetzt?

---

## 🟡 MEDIUM Priority

### source_view in Favorites für korrektes Restore-Routing

**Status:** Implementiert, funktioniert noch nicht — Debugging nötig
**Datum:** 2026-02-14

- `source_view` Feld im gesamten Stack hinzugefügt (Frontend Store → API → JSON → Restore)
- Restore-Routing nutzt `source_view` noch nicht korrekt
- **Dateien:** `src/stores/favorites.ts`, `favorites_routes.py`, alle 5 Views

### Rare Earth Minigame — Phase 4 Testing

**Datum:** 2026-02-03

Code fertig (Phase 1-3 committed), Testing ausstehend:
- [ ] Manual testing im Frontend
- [ ] Balance prüfen (Degradation vs. Cleanup rates)
- [ ] Inactivity timeout (30s) verifizieren
- [ ] Truck animation testen
- [ ] Mobile Responsiveness prüfen
- [ ] Vue type-check

### Latent Lab UX Improvements

**Datum:** 2026-02-21

- ✅ Seed defaults (fixed)
- ✅ Sticky sub-tabs (fixed)
- ✅ Parameter hints (fixed)
- ✅ Crossmodal Lab explanation toggle (fixed)
- [ ] **Streamline "Erweiterte Einstellungen" collapse state** — persist via localStorage
- [ ] **Scientific references with DOI** in all labs (MMAudio=CVPR 2025, ImageBind=CVPR 2023, Stable Audio=ICML 2024)

### MMAudio / ImageBind Downloads ausstehend

**Datum:** 2026-02-20

Bei Festnetz-Verbindung:
- MMAudio-Weights (~3.9 GB) + VAE (~1.2 GB) — laden automatisch beim GPU Service Neustart
- ImageBind Checkpoint: `imagebind_huge.pth` (~4.5 GB) — lädt beim ersten Tab-3-Aufruf
- Gesamt: ~14.5 GB ausstehend

---

## 📋 LOW / PLANNED / DEFERRED

### "optimization" → "adaptation" Rename

**Datum:** 2026-01-29
Alle Backend-Referenzen von "optimization/optimize" zu "adaptation/adapt" umbenennen (Chunk-Dateien + Python-Code).

### Provider Routing ohne Präfix-Parsing

**Datum:** 2026-01-23
Routing basierend auf `EXTERNAL_LLM_PROVIDER` statt Model-String-Präfixen (`openrouter/`). Single Source of Truth.
**Dateien:** `prompt_interception_engine.py`, `settings_routes.py`

### PyTorch Stable Migration

**Datum:** 2026-02-22
Nightly `2.11.0.dev20260203+cu130` → Stable `2.11.0` (sollte seit Feb 16 released sein). Eigene Test-Session planen — nicht nebenbei.

### Internationalization — Primary Language Selector

**Datum:** 2025-11-02
Template-System für Educational Error Messages (hardcoded German → konfigurierbar). Nicht blocking für aktuelles Deployment.

### Quick-Toggle UI Mode (Expert/Youth/Kids)

**Datum:** 2026-02-28
**Status:** Aufgeschoben — kein Blocker, nice-to-have

Idee: Schneller Schalter im Interface zum Wechseln zwischen UI-Modes (kids/youth/expert), ohne in die Settings zu müssen. Settings definiert den Default, User können spontan umschalten. Offene Frage: Wo elegant platzieren? Kandidaten wären MediaOutputBox-Header (kontextbezogen, nur während Generierung) oder App-Header (permanent sichtbar, aber 95% der Zeit irrelevant). Risiko: Workshop-Teilnehmer landen versehentlich in Expert-Mode.

### Debug-Stufen-System

**Plan:** `~/.claude/plans/dynamic-sprouting-stonebraker.md`
**Status:** DEFERRED

### Pipeline-Autonomie Check

**Datum:** 2026-02-02
Prüfen ob in schema-/pipeline-/chunk-bezogenen Python-Files Funktionen absorbiert wurden, die zwischen Pipelines und "ihren" Chunks hätten realisiert werden sollen. Hängt zusammen mit Proxy-Chunk und Output-Chunk Refactoring.

---

## 🎮 Minigames / Waiting Animations

### Design-Prinzipien (übergreifend)

**Kern-Prinzip: "Sisyphus der Systeme"**

Alle Minigames folgen einem gemeinsamen pädagogischen Ansatz:
- **Abwärtsdynamik:** Keine vollständige Heilung möglich
- **User kann handeln:** Aber systemische Zerstörung läuft schneller als individuelle Aktion
- **Sisyphus-Metapher:** Kämpfen gegen eine Übermacht (wie in "Papers, Please", "This War of Mine")

**Offene Designfragen:**
- Resignation vs. Ermächtigung — Braucht es Hoffnungsmomente?
- "Was kann ich wirklich tun?" Sektion nach jedem Spiel?
- Angemessenheit für Kids (8-12) / Youth (13-17)?
- Balance: ehrlicher Realismus vs. pädagogische Ermächtigung?

### Fair Culture (Web Scraping Ethics) — PLANNED

**Datum:** 2026-02-03

Pädagogischer Content über Web-Scraping für generative AI, Künstler-Kompensation.
- Game Mechanic noch nicht designt
- Nächste Schritte: Recherche, Mechanik-Design, Content, Frontend-Integration

---

## 📁 Archiv

- **Sessions 1-14 Full History:** `docs/archive/devserver_todos_sessions_1-14.md`
- **Alle erledigten Items:** Dokumentiert im `DEVELOPMENT_LOG.md` (Sessions 12-203)
- **Architektur-Dokumentation:** `docs/ARCHITECTURE PART 01-20.md`

---

**Created:** 2025-10-26
**Major Cleanups:** 2025-11-02 (Session 14), 2026-02-23 (von ~2100 auf ~220 Zeilen), 2026-03-02 (erledigte Items bereinigt)
