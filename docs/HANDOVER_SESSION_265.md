# Handover: Session 265 — Kritische Transparenz-Features

## Was wurde gebaut

### Feature 1: Model Provenance Card — FERTIG
- `provenance`-Felder in 5 Output-Configs (sd35_large, sd35_large_turbo, gpt_image_1, heartmula_standard, stableaudio_open)
- `ModelProvenanceCard.vue` — aufklappbar, kids/youth/expert, integriert in MediaOutputBox
- i18n-Keys in en.ts + Work Order
- **Status**: Funktioniert

### Feature 2: Dialogischer Sprachvergleich `/compare` — TEILWEISE FUNKTIONAL, BUGS

**Was funktioniert:**
- Seite `/compare` mit MediaInputBox, LanguageChipSelector (10 Plattform + 10 weitere Sprachen mit Tooltips), Modellauswahl (SD3.5, SD3.5 Turbo, Flux 2, GPT-Image-1)
- Übersetzung über `/api/schema/pipeline/translate` (erweitert für beliebige Zielsprachen)
- Generierung über `useGenerationStream` Composable (korrekt)
- Bilder werden generiert und angezeigt (media_output.url korrekt geparsed)
- `skip_stage3_translation`-Flag in GenerationParams + Backend
- Kompakte Slot-Darstellung (Bild + Fortschrittsbalken)
- Seed wird angezeigt

**BUGS:**

1. **ComparisonChat `/api/chat` — gefixt (d9d3986) aber UNGETESTET**
   - War: falsches Request-Format (`messages` array statt `message` + `history`), falsches Response-Feld (`content` statt `reply`)
   - Trashy war komplett nicht dialogfähig

2. **`/api/schema/compare/describe` — UNGETESTET**
   - VLM-Bildbeschreibung für Trashy-Kommentare
   - `vlm_describe_image()` in `vlm_safety.py`
   - LivePipelineRecorder safety_level-Fix committed
   - Braucht Backend-Neustart

3. **Trashy auto-comment nach Generierung — UNGETESTET**
   - Trigger: `comparisonContext` watcher reagiert auf `generation_complete`
   - Sendet VLM-Beschreibungen mit Sprachzuordnung

## Architektur-Entscheidungen

- **Kein Stage 2/3**: Prompts gehen roh an CLIP/T5 — zeigt Encoding-Bias
- **Selber Seed für alle Sprachen**: Unterschiede nur von der Sprache
- **ComparisonChat ist NICHT ChatOverlay**: Eigene Komponente in der /compare-Seite
- **Übersetzung über bestehenden `/pipeline/translate`**: Erweitert für beliebige Zielsprachen
- **VLM-Bildbeschreibung kopiert Pattern aus Safety Stage 4**

## Offene Punkte

1. End-to-End testen (Backend neustarten, voller Flow)
2. Trashy auto-comment + Dialog verifizieren
3. Landing-Page Feature-Card für `/compare`
4. i18n Work Order aktualisieren
5. `ComparisonCard.vue` löschen (unused)
6. `/api/schema/compare/translate` Endpoint löschen (unused, Übersetzung läuft über `/pipeline/translate`)
7. Deferred: Modellvergleich, Bias-Probes, Interception-Vergleich

## Kritische Dateien

- `views/comparative_generation.vue` — Hauptseite
- `components/ComparisonChat.vue` — Trashy Chat
- `components/LanguageChipSelector.vue` — Sprachwahl
- `components/ModelProvenanceCard.vue` — Feature 1
- `composables/useGenerationStream.ts` — `skip_stage3_translation`
- `routes/schema_pipeline_routes.py` — Translate-Erweiterung, Describe-Endpoint, Skip-Flag
- `routes/chat_routes.py` — COMPARISON_SYSTEM_PROMPT_TEMPLATE
- `utils/vlm_safety.py` — `vlm_describe_image()`

## Lessons

- **IMMER bestehende Patterns lesen** bevor neuer Code geschrieben wird
- **KEINE Parallelstrukturen** — bestehende Endpoints erweitern
- **Testen vor Commit**
