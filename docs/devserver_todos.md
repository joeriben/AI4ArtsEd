# DevServer Implementation TODOs
**Last Updated:** 2026-03-06
**Context:** Current priorities and active TODOs

---

## ✅ Kürzlich erledigt (Kurzreferenz)

| Session | Datum | Was |
|---------|-------|-----|
| 250 | 2026-03-06 | Hunyuan3D-2 Text-to-3D Pipeline + Blender Headless + model-viewer |
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

*Derzeit keine CRITICAL-Items.*

---

## 🔴 HIGH Priority

### Provider-agnostische API-Registry Refactor

**Datum:** 2026-03-07
**Status:** PLANNED
**Kontext:** Workshop 06.03.2026 — brand-spezifische Methodennamen sind technische Schuld

Bestehende `_call_mistral()`, `_call_ollama()`, `_call_openai()`, `_call_anthropic()`, `_call_ionos()`, `_call_openrouter()` durch generische Registry ersetzen:
- Eine `_call_cloud_api(provider, model, prompt, params)` Methode statt 6 fast-identische
- Provider-Registry mit Metadaten: `{name, api_url, auth_type, response_format, dsgvo_safe: bool}`
- DSGVO-Safety als First-Class-Property jedes Providers + Praeferenz-Reihenfolge
- Fallback-Logik waehlt automatisch NUR DSGVO-registrierte Anbieter (wenn `DSGVO_ONLY_FALLBACK=True`), oder alle verfuegbaren (wenn `False`, fuer internationale Deployments). In Settings-Matrix als Toggle.
- Brand-Namen verschwinden aus Funktionsnamen, Variablen, Klassen

**Betroffene Dateien:**
- `devserver/schemas/engine/prompt_interception_engine.py` — 6 `_call_*` Methoden → 1 generische
- `devserver/my_app/routes/chat_routes.py` — 4 `_call_*_chat` Funktionen → 1 generische
- `devserver/config.py` — Provider-Registry-Konfiguration (DSGVO_SAFE_PROVIDERS, ALL_CLOUD_PROVIDERS bereits vorhanden)

---

### Hunyuan3D-2 Aktivierung — custom_rasterizer kompilieren

**Datum:** 2026-03-06 (Session 250)
**Status:** DONE (2026-03-17) — custom_rasterizer kompiliert und Frontend aktiviert
**Kontext:** 3D-Pipeline (Text → GLB Mesh) vollständig implementiert. `custom_rasterizer` CUDA Extension erfolgreich gegen torch 2.11.0.dev+cu130 + nvcc 13.0.48 kompiliert.

**Erledigte Schritte:**
1. ~~`custom_rasterizer` kompilieren~~ — DONE (aus Hunyuan3D-2 Repo, `setup.py install`)
2. ~~`python -c "import custom_rasterizer"` testen~~ — DONE (import nach `torch` erfolgreich)
3. GPU Service neu starten, `/api/hunyuan3d/available` testen — **OFFEN (E2E-Test)**
4. ~~`disabled: true` entfernen in `text_transformation.vue:706`~~ — DONE
5. End-to-End Test: Text → 3D → model-viewer im Browser — **OFFEN**

---

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
**Status:** ⚠️ Unbestätigt — vermutlich kein Bug

Ursprüngliche Annahme: `stage4_error` SSE-Event kommt nicht durch. Bei Code-Review (Session 236) zeigt sich: `stage4_error` existiert gar nicht als Event-Typ im Backend. Stattdessen nutzen alle Views `finally`-Blöcke, die `isExecuting = false` setzen. Der beschriebene Bug konnte nicht reproduziert werden.

Verbleibend: Model-Card-Höhe stimmt nicht mit MediaOutputBox-Höhe überein (kosmetisch).

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

### Latent Audio Synth — WSOLA → AudioWorklet DSP Performance Fix

**Datum:** 2026-03-06
**Status:** PLANNED
**Plan:** `docs/plans/latent-audio-synth-dsp-performance.md`

WSOLA Pitch Shifting läuft auf dem **Main Thread in purem JavaScript** → UI-Lag bei aktivem Pitch Shift / MIDI Transpose. Wavetable Oscillator hat das Problem nicht (bereits in AudioWorklet).

**2 Phasen:**
1. **AudioWorklet Migration** (1 Session): Bestehenden WSOLA-Code in `wsola-processor.js` AudioWorkletProcessor verschieben. Gleicher Algorithmus, separater Thread, kein UI-Lag mehr.
2. **Rubber Band WASM** (2-3 Sessions): WSOLA durch [Rubber Band Library](https://breakfastquay.com/rubberband/) (C++ → WASM) ersetzen. Formant-Preservation, Polyphonic-aware, Industriestandard-Qualität.

**Betroffene Dateien:**
- `src/composables/useAudioLooper.ts` — WSOLA-Extraktion, async message-pass
- `src/audio/wsola-processor.js` — **Neu**: AudioWorkletProcessor
- `src/audio/wavetable-processor.js` — Referenz-Pattern (keine Änderung)

**Profitiert:** Sowohl AI4ArtsEd Web als auch geplante Electron Standalone App.

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

## 🟡 Kritische KI-Literalitaet — Neue Features (Session 266)

### 1. Dialogische KI-Persona Page — PLANNED

**Datum:** 2026-03-18
**Paedagogisches Ziel:** Umkehrung der Mensch-bestellt-KI-liefert-Dynamik. KI als aesthetischer Gespraechspartner.

Vue page mit zentralem Dialog-Fenster:
- AI gibt sich bei Start selbst eine Persoenlichkeit (freundlich, aesthetisch fragend, kritisch/widerstaendig)
- Generiert erst, wenn der Dialog plausibel erscheint
- Entscheidet selbst: welches Medium, welches Modell
- Generierte Outputs in floating Boxen um den Dialog herum (mit Standard-Weiterbearbeitungsfunktionen)

### 2. Compare-Seite: Uebersetzungs-Transparenz — DONE

**Datum:** 2026-03-18
**Status:** Komplett (Session 265-266)

Bestehende `/compare`-Seite:
- ✅ Uebersetzungsboxen mit Rueckuebersetzungen (Session 265)
- ✅ Context-Enrichment via InterceptionPresetOverlay (Session 266)
- ✅ MediaOutputBox statt Parallelcode (Session 266)
- ✅ Persistenter Trashy-Chat mit Inquiry-Paedagogik (Session 266)

### 2b. Persona: ModelCard skaliert nicht in kleinen MediaBoxen — BUG

**Datum:** 2026-03-19
Die Floating-MediaBoxen in der Persona-Seite haben die richtige Groesse (320px), Output-Bilder/Audio passen gut. Aber die ModelCard (Provenance-Karte) skaliert nicht auf diese Groesse herunter — Layout bricht, wird messy. ModelCard muss responsive auf kleine Container reagieren.

### 3. Compare-Variationen: LLM-Dekonstruktion — PLANNED

**Datum:** 2026-03-18
**Paedagogisches Ziel:** Natuerliche Logik von LLMs dekonstruieren und erfahrbar machen.

Weitere Compare-Modi:
- **Sprachmodell-Vergleich**: Gleicher Prompt an verschiedene LLMs, mit Seed-Kontrolle (Transformers, nicht API) und Temperature-Kontrolle
- **System-Prompt-Vergleich**: Auswechselbare Systemprompts zeigen wie stark Kontext das Verhalten steuert
  - **Mammouth-Idee**: Mammouth leitet keine Sysprompts weiter → Sonnet 4.6 via Mammouth in 3 Varianten: a) Original-Sysprompt (direkte API), b) ohne Sysprompt (Mammouth-Default), c) eigener Sysprompt. Temperature steuerbar, aber kein Seed (Claude hat kein deterministic sampling).
- **Temperature-Vergleich (3-Spalten-Chat)**: Gleiches LLM (z.B. Sonnet) bei Temperature 0 / 0.5 / 1 parallel. User schickt einen Prompt → 3 Antworten nebeneinander. Gespraechsverlauf wird pro Spalte weitergefuehrt (3 divergierende Konversationen). Macht Stochastizitaet und deren Einfluss auf Kreativitaet/Praezision direkt erfahrbar.
- **Interception-Vergleich**: Gleicher User-Prompt + gleicher Kontext (Default: Planetarizer), aber verschiedene LLMs fuehren die Stage 2 Interception aus. Zeigt: Mistral Large produziert Kitsch, waehrend z.B. ein kleineres Modell (Mistral Nemo) oder ein hochwertigeres oft bessere/andere aesthetische Entscheidungen trifft. Kontext auswaehlbar (alle Interception-Configs).
- **Bias-Probes**: Gezielte Prompts die systematische Verzerrungen in Modellen sichtbar machen (kulturelle Defaults, Gender-Bias, geographische Vorurteile). Insbesondere: Was sind fuer Modelle "Schoenheit", "Helden", "Alter"? → DAS war der urspruengliche Grund fuer Bildmodell-Vergleich. Auch fuer Textarbeit interessant.
- **Visueller Kontext-Prompt**: Einfluss von Kontext auf Generierung
- Immer mit Trashy-Interpretation
- Auch mit kleinen lokalen Modellen moeglich, aber AUCH grosse Cloud-Modelle (v.a. fuer Interception-Vergleich — Qualitaetsunterschiede sind dort am kraessesten)

### 4. Navigation: Canvas — Compare — Latent Lab — CHECKEN

**Datum:** 2026-03-18
**Status:** OFFEN

- Drei fortgeschrittene Bereiche: Canvas, Compare, Latent Lab
- Pruefen ob Ueberschneidungen zwischen Latent Lab und Compare bestehen (vermutlich nein — Latent Lab = Vektor-Manipulation, Compare = sprachliche/modell-uebergreifende Transparenz)
- Pruefen ob Latent Lab safety-faehig gemacht werden kann (Compare ging auch)

### 5. Erheblicher Ausbau additiver Technologien (p5.js) — PLANNED

**Datum:** 2026-03-18
**Paedagogisches Ziel:** Generativen Code als eigenstaendiges kreatives Medium staerken.

- p5.js ist bisher als Output-Typ vorhanden, aber unterentwickelt
- Erheblicher Ausbau: mehr Interception-Configs fuer Code-Generierung, bessere Vorschau, iteratives Arbeiten
- Additive Technologien (Code, der sichtbar aufbaut) als Gegenpol zu diffusionsbasierten (subtraktiven) Verfahren
- **Referenzrahmen: "Computerkunst" — Frieder Nake, Georg Nees, Vera Molnar u.a.** Algorithmische Aesthetik, regelbasierte Generierung, Zufall als Gestaltungsmittel. p5.js als zeitgenoessische Fortsetzung dieser Tradition.
- Potential: Live-Preview, Parameter-Manipulation, Export, Remix

### 6. Compare: Dekonstruktive Bias-Probes fuer Bildmodelle — PLANNED

**Datum:** 2026-03-18
**Paedagogisches Ziel:** Herausfinden was fuer verschiedene Modelle "Schoenheit", "Helden", "Alter" sind.

- Urspruenglicher Kern-Grund fuer den Bildmodell-Vergleich
- Gezielte Prompts ("a hero", "beauty", "an old person") an verschiedene Modelle → Defaults sichtbar machen
- Auch fuer Textarbeit: Wie beschreiben verschiedene LLMs "einen Helden"?
- Kombination mit Interception-Vergleich: gleicher dekonstruktiver Prompt, verschiedene LLMs als Stage 2

---

## 📋 LOW / PLANNED / DEFERRED

### ~~Blender Headless Integration~~ — ERLEDIGT (Session 250)

**Datum:** 2026-03-04 | **Erledigt:** 2026-03-06
Implementiert als Teil der Hunyuan3D-2 Text-to-3D Pipeline. Blender (v4.5.6, system-installiert) rendert Vorschau-PNGs via Eevee. `<model-viewer>` Web Component für interaktive GLB-Anzeige im Browser.

### Remaining Router Cleanup — Stable Audio Chunk Migration

**Datum:** 2026-02-02 | **Herabgestuft:** 2026-03-04 (von CRITICAL → LOW)
**Kontext:** Stable Audio JSON→Python-Chunk-Migration mehrfach gescheitert, minimaler Nutzen. ComfyUI-Workflow-Extraktion nach `comfyui_handler.py` bleibt wünschenswert, aber nicht dringend.

**Plan-Referenz:** `docs/plans/diffusers-chunk-migration.md`

### ~~Video Generation Wan 2.1~~ — OBSOLET

**Datum:** 2026-02-15 | **Gestrichen:** 2026-03-04
Wan 2.2 ist installiert, dieses Todo bezog sich auf Wan 2.1 und ist damit hinfällig.

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

### Latent Audio Synth — Electron Standalone Extraction

**Datum:** 2026-03-06
**Status:** PLANNED — Extraction noch nicht begonnen
**Plan:** `docs/plans/latent-audio-synth-extraction.md`

Die ai4artsed-Plattform enthält ein neuartiges Latent-Audio-Synthese-System: T5-Embedding-Manipulation → Stable Audio Diffusion → browserseitige Audio-Verarbeitung (WSOLA Looper, Wavetable Oscillator, Step Sequencer, Arpeggiator). Eigenständig publizierbar als Electron-App.

**Architektur:**
- **Electron Shell**: GPU Service Subprocess Management, Model Download Manager, neue Synth-UI (Vue 3 + Vite)
- **GPU Service** (Python Subprocess): `cross_aesthetic_backend.py`, `stable_audio_backend.py`, `vram_coordinator.py`
- **Audio Composables** (Copy as-is, zero Platform-Dependencies): `useAudioLooper.ts`, `useWavetableOsc.ts`, `useStepSequencer.ts`, `useArpeggiator.ts`, `useEnvelope.ts`, `useWebMidi.ts`

**6 Phasen:**
1. Repo-Setup (`~/ai/latent-audio-synth/`, separates Git)
2. GPU Service Extraction (nur Stable Audio + T5 Synth, KEIN ImageBind/MMAudio/Image/Video)
3. Audio Composables kopieren (TypeScript + Web Audio API, plattformunabhängig)
4. Neue Synth-UI (kein i18n, kein DevServer-Layout, Ableton/Bitwig-Ästhetik)
5. Electron Integration (Subprocess-Management, Model-Download-UX)
6. Packaging (electron-builder, Model ~3.6 GB wird beim ersten Start geladen)

**Was novel ist (Paper/README):**
- Semantic Axis System (21 validierte Achsen als Audio Control Surface)
- Per-Dimension T5-Embedding-Manipulation als Synthese-Paradigma
- Browser-side WSOLA Pitch Shifting für AI-generierte Audio-Loops
- Wavetable-Extraktion aus Diffusion-generiertem Audio
- Geplant: SAE Feature Sonification (T5 monosemantische Features → hörbar)

**Lizenz:** Code = CC BY-SA 4.0, Stable Audio Open 1.0 = Community License (Weights nicht gebundled, User lädt selbst)
**Backport-Strategie:** Identische Interfaces → einfacher File-Copy in beide Richtungen, kein Subtree/Submodule nötig

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
