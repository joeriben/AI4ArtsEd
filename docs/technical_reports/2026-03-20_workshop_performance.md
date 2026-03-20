# Workshop 20.03.2026 - Realwelt-Performance-Analyse

## Kontext
Dritter dokumentierter Realwelt-Workshop der AI4ArtsEd-Plattform. Backend lief auf Production-Server (Port 17801) mit RTX PRO 6000 Blackwell 96GB. Drei Logfiles ausgewertet: Backend (~1.5MB, 14355 Zeilen), ComfyUI (42 Zeilen — Startup gescheitert), GPU Service (~310 Zeilen). Vergleichsbasis: `2026-03-05` und `2026-03-06` Workshop-Analysen. **Erstmals `youth` statt `kids` Safety Level.**

---

## 1. Session-Ueberblick

| Metrik | Wert | Vgl. 06.03. |
|--------|------|-------------|
| **Zeitfenster** | 14:58 - 17:54 (2h 56min) | 14:34 - 17:43 (3h 8min) |
| **Aktive Generierungsphase** | 15:14 - 17:54 (2h 40min) | ~3 Stunden durchgehend |
| **Aktive Geraete (generierend)** | 7 | 9 |
| **Geraete gesamt (verbunden)** | 9 | 9 |
| **Safety Level** | `youth` (durchgehend) | `kids` |
| **Waitress Threads** | 24 | 24 |
| **Pipeline-Runs gesamt** | ~107 | 156 |
| **Stage 4 Ausfuehrungen** | 105 | — |
| **GPU Service Bilder** | 48 (100% Erfolg) | 78 (100% Erfolg) |
| **ComfyUI Generierungen** | ~57 (100% Erfolg) | 51 (100% Erfolg) |
| **Erfolgsrate gesamt** | **~97%** (104/107) | 76% |
| **Technische Fehler** | **0** | ~21 (Mistral 503, Ollama Timeout) |

**Beobachtung**: Deutlich hoechste Erfolgsrate aller drei Workshops — erstmals **null technische Fehler**. Die einzigen "Verluste" (3 von 107) sind korrekte Safety-Blocks (1x S3, 1x VLM, 1x S4). Zwei-Phasen-Nutzungsmuster mit ~1 Stunde Pause dazwischen. Erstmals `youth` statt `kids` Safety Level.

---

## 2. Zugriffsmuster

### Request-Verteilung nach Config (Stage 4)

| Config | Ausfuehrungen | Anteil | Backend |
|--------|--------------|--------|---------|
| **qwen_img2img** | 47 | 44.8% | ComfyUI |
| **sd35_large** | 45 | 42.9% | GPU Service (Diffusers) |
| **qwen_2511_multi** | 7 | 6.7% | ComfyUI |
| **wan22_i2v_video** | 3 | 2.9% | ComfyUI |
| **gemini_3_pro_image** | 2 | 1.9% | Cloud API (Mammouth) |
| **lyrics_refinement** | 1 | — | Text-only (kein Stage 4) |

**Veraenderung vs. 06.03.**: Am 06.03. war sd35_large mit 339 Ausfuehrungen absolut dominant. Am 20.03. nahezu gleichmaessige Verteilung zwischen sd35_large (Text-to-Image) und qwen_img2img (Image-to-Image). **qwen_img2img steigt von 64 auf 47 Ausfuehrungen bei halb so vielen Gesamt-Runs — relativer Anteil verdoppelt sich von ~11% auf 45%.** Dies deutet auf ein veraendertes paedagogisches Setup hin (Fotografieren → Transformieren).

### Zeitliche Verteilung (Zwei-Phasen-Muster)
```
Phase 1: 15:14-15:55  sd35_large dominant (45 Bilder, strukturierte Uebung)
          |            7 Geraete aktiv, Burst-Generierung (4er-Sets)
          |            ~8s pro Bild, reine GPU-Service-Last
---PAUSE-- 15:55-16:57  ~1 Stunde Inaktivitaet
Phase 2: 16:57-17:54  qwen_img2img dominant (47+ Transformationen)
          |            ComfyUI-Last, kreative Iteration
          |            + 3 Videos, 7 Multi-Image, 1 Lyrics
```

**Muster**: Anders als am 06.03. (durchgehend 3h) hier klare Zweiphasigkeit. Phase 1 = strukturierte Generierung (geometrische Formen, Objekte auf weissem Hintergrund). Phase 2 = kreative Img2Img-Transformation realer Fotografien.

### Aktive Geraete
7 generierende Devices: `dc2edac8`, `c5ecf600`, `4bdea409`, `2d3aeb13`, `6c488f1a`, `3d9e4167`, `be9fb3b9`
2 nur browsend: `5bd754b9`, `969c267f`

Aktivste Devices: `6c488f1a` (8+ Runs in Phase 1), `be9fb3b9` (mehrere Runs in Phase 2)

---

## 3. Pipeline-Durchlauf & Erfolgsraten

### End-to-End Ergebnis (~107 Runs)
```
~107 Unique Pipeline Runs
 |
 +-- 1 BLOCKED by Stage 3 Llama-Guard (S3 — Nudity)
 +-- 1 BLOCKED by VLM Post-Gen (mammouth/claude-sonnet-4-6 Fallback)
 +-- 0 technische Fehler
 |
 = ~105 Stage 4 Starts
 |
 +-- 48 Bilder via GPU Service/Diffusers (sd35_large)
 +-- ~47 Bilder via ComfyUI (qwen_img2img)
 +-- 7 Bilder via ComfyUI (qwen_2511_multi)
 +-- 3 Videos via ComfyUI (wan22_i2v_video)
 +-- 2 Bilder via Cloud API (gemini_3_pro_image)
 |
 +-- 1 VLM Post-Gen Block (Bild generiert, aber nicht ausgeliefert)
 |
 = ~104 Medien an Nutzer ausgeliefert
 + 1 Text-Ergebnis (lyrics_refinement)
```

**Erfolgsrate**: 104/107 = **97.2%** (vs. 76% am 06.03., 72-74% am 05.03.)
**Null technische Fehler** — alle 3 "Verluste" sind korrekte Safety-Interventionen.

### Fehlerquellen-Aufschluesselung

| Fehlerquelle | Anzahl | Rate | Vgl. 06.03. |
|-------------|--------|------|-------------|
| **Llama-Guard S3 Block** | 1 | 0.9% | Erwartet |
| **VLM Post-Gen Block** | 1 | 0.9% | 0 |
| Mistral API 503 | **0** | 0% | 10 (5.6%) — GELOEST |
| Ollama Timeout | **0** | 0% | 11 (7%) — GELOEST |
| ComfyUI Timeout | **0** | 0% | 0 (war 22% am 05.03.) |
| T5 Race Condition | **0** | 0% | 0 (war Hauptfehler am 05.03.) |
| DSGVO Block | **0** | 0% | 0 |

---

## 4. Stage-Performance-Timings

### Stage 1 (Safety Fast-Filter)
- SpaCy NER + POS-Tag Pre-Filter: <100ms
- Alle Runs "Safety PASSED (fast-filters clear)" — kein einziger Stage-1-Block
- §86a-Terme geladen: 89 Terms (6 Sprachen)

### Stage 2 (Prompt Interception via Mammouth/Claude Sonnet 4.6)
- Typisch: 2-8 Sekunden
- Output: 122-827 Zeichen
- **Provider**: Mammouth (claude-sonnet-4-6) — nicht Mistral wie am 06.03.
- **Null Ausfaelle** (vs. 10 Mistral 503 am 06.03.)

### Stage 3 (Translation + Llama-Guard)
- Llama-Guard: 94-1307ms (typisch ~100-140ms, cached Ollama)
- DSGVO NER: 10-1613ms (typisch 12-20ms, Spitzen unter Last)
- DSGVO LLM-Verify: 498-6365ms (wenn getriggert)
- Gesamt: 0.1-1.4s pro Request (meiste unter 0.2s)

### Stage 4 (Generation)
- **SD3.5 Large (GPU Service)**: ~8s pro 1024x1024 @ 25 Steps
- **qwen_img2img (ComfyUI)**: ~25-40s pro Bild
- **qwen_2511_multi (ComfyUI)**: ~40-60s pro Multi-Image
- **wan22_i2v_video (ComfyUI)**: 54.7s pro Video (81 Frames, 640x640)
- **gemini_3_pro_image (Cloud API)**: variabel

---

## 5. GPU Service Performance

| Metrik | Wert | Vgl. 06.03. |
|--------|------|-------------|
| **SD3.5 Generierungen** | 48 | 78 |
| **Erfolgsrate** | 100% | 100% |
| **Gen-Zeit** | ~8s (2.4-3.5 it/s) | 7-8s |
| **Threads** | 16 | 16 |
| **VRAM geladen** | 28262 MB (SD3.5) | 28300 MB |
| **OOM-Fehler** | 0 | 0 |
| **Model Load Time** | 46s (cold start) | — |
| **VRAM-Schaetzung** | 20000 MB (config) vs 28262 MB (real) | Gleich — offen |

**Registrierte Backends**: diffusers, heartmula, stable_audio, mmaudio, text, hunyuan3d (6 Backends)
**Hunyuan3D**: `hy3dgen not installed` — wiederholte Fehlermeldung bei jedem Availability-Check

**Warnung**: `nvidia-ml-py` nicht installiert — VRAM Coordinator kann nur PyTorch-eigene Allokationen sehen, nicht ComfyUI oder andere GPU-Prozesse. Bei gleichzeitiger GPU-Service + ComfyUI Last potentiell problematisch.

---

## 6. ComfyUI Performance

| Metrik | Wert | Vgl. 06.03. |
|--------|------|-------------|
| **Generierungen** | ~57 | 51 |
| **Erfolgsrate** | 100% | 100% |
| **wan22_i2v_video** | 54.7s | 40-50s |
| **OOM-Fehler** | 0 | 0 |
| **Crashes** | 0 | 0 |
| **Timeouts** | 0 | 0 |

### ComfyUI Startup-Problem (NEU)
- **Recording-Script** startete ComfyUI 2x → `main.py: No such file or directory`
- Pfad: `/run/media/joerissen/production/ai4artsed_production/dlbackend/ComfyUI/main.py`
- Ursache: ComfyUI wurde vermutlich aktualisiert und `main.py` in `comfyui/main.py` oder aehnlich verschoben
- **Backend COMFYUI-MANAGER auto-start funktionierte** (ueber `2_start_comfyui.sh`) → ComfyUI war ab ~15:30 verfuegbar
- **Auswirkung**: Keine — alle ComfyUI-abhaengigen Configs waren in Phase 2 (ab 16:57) verfuegbar
- Model Availability initial: 17/33 (ComfyUI-Configs unavailable) → spaeter 32/33 (nur hunyuan3d fehlt)

---

## 7. Safety-System Gesamtbewertung

### Stage 1 (Fast-Filter)
- **0 Blocks** — korrekt bei youth-Level mit unproblematischen Prompts

### Stage 3 Llama-Guard
- ~96 Verdicts insgesamt (Auswertung nach Runs mit Stage 3)
- ~74 safe (77%)
- 21 S7 (Self-Harm) → **alle korrekt ignoriert** ("not relevant for image generation")
- 5 S8 (Intellectual Property) → nicht blockierend fuer Bildgenerierung
- 1 S4 (Child Safety) → nicht blockierend (False Positive: "Ein Maedchen haelt ihn")
- **1 S3 (Nudity) → BLOCKED** ✓ — korrekte Intervention

### VLM Post-Generation Safety (qwen3-vl:2b)
- ~18 VLM-Checks durchgefuehrt (youth-Level Bilder)
- **1 Block** via Zwei-Modell-Fallback:
  - Primary (qwen3-vl:2b): kein Verdict (content='' bei ambigem Bild)
  - Fallback: mammouth/claude-sonnet-4-6 → "image flagged as unsafe for youth"
  - Kontext: Kleiderbügel-Foto mit deutschem Text → VLM unsicher
- Alle anderen Checks: SAFE (abstrakte Kunst, Tiere, Alltagsobjekte)

### DSGVO Data Protection
- 12+ NER + LLM-Verify Chains ausgeloest
- False Positives bei deskriptiven englischen Phrasen:
  - "framing a", "jagged torn edges", "overlapping corners", "wrinkled creases"
  - "latitude lines, meridian lines", "braided cord outlines, calm looping cables"
  - "clay wall background, textured clay wall behind" (bis 1613ms NER unter Last!)
- LLM-Verify: **100% korrekt SAFE** — kein einziger False Block
- **0 DSGVO-Blocks** (wie 06.03.)

### Safety-System: Trend ueber 3 Workshops

| Safety-Metrik | 05.03. (kids) | 06.03. (kids) | 20.03. (youth) |
|---------------|---------------|---------------|----------------|
| Stage 3 Blocks | ~3-5 | ~12 | 1 (S3) |
| VLM Blocks | 2 | 0 | 1 |
| DSGVO Blocks | 1 (False Positive) | 0 | 0 |
| S7 False Positives | — | ~9 | 21 (alle ignoriert) |
| Falsch-Positiv-Rate | Hoch | Mittel | Niedrig |

**Beobachtung**: S7 (Self-Harm) ist konsistent der haeufigste Llama-Guard False Positive bei Kunst-Prompts. Die "Ignoring chat-specific codes" Logik funktioniert zuverlaessig. Die Umstellung auf `youth` hat die Prompt-Freiheit erhoert ohne Sicherheitseinbussen.

---

## 8. Identifizierte Probleme & Handlungsempfehlungen

### KRITISCH — keine

Alle kritischen Bugs der vorherigen Workshops bleiben behoben. Keine neuen kritischen Probleme.

### MITTEL

1. **ComfyUI Startup-Script defekt** (Recording-Pfad)
   - `main.py` nicht gefunden unter erwartetem Pfad
   - COMFYUI-MANAGER auto-start kompensierte, aber:
     - 30+ Minuten ComfyUI-Unavailability beim Start
     - Wiederholte "ComfyUI unreachable" Log-Spam (67 ERROR-Zeilen)
   - **Empfehlung**: `2_start_comfyui.sh` und ComfyUI-Pfad im Recording-Script pruefen/aktualisieren

2. **nvidia-ml-py nicht installiert im GPU Service**
   - VRAM Coordinator blind fuer fremde GPU-Prozesse (ComfyUI, Ollama)
   - Bei gleichzeitiger ComfyUI (wan22_i2v) + Diffusers (sd35) Last Risiko fuer OOM
   - 5x Warnmeldung bei jedem Start
   - **Empfehlung**: `pip install nvidia-ml-py` im GPU-Service-venv

3. **SD3.5 VRAM-Schaetzung weiterhin falsch**
   - Config: 20000 MB, Real: 28262 MB (+41%)
   - Seit 05.03. offen — bisher kein Impact dank 96GB VRAM
   - **Empfehlung**: VRAM estimate auf 29000 MB korrigieren

### NIEDRIG

4. **Hunyuan3D permanente Fehlermeldung**
   - `hy3dgen not installed` bei jedem Availability-Check (~10x pro Session)
   - Log-Verschmutzung ohne Nutzen
   - **Empfehlung**: Backend als unavailable cachen oder aus Config entfernen bis installiert

5. **DSGVO NER False Positives auf deskriptive Phrasen**
   - Wie 06.03.: englische Adjektiv-Nomen-Kombinationen als Personennamen erkannt
   - Neu: "clay wall background" mit bis zu 1613ms NER-Latenz unter Concurrent Load
   - LLM-Verify korrigiert zuverlaessig, aber 0.5-6.4s unnoetige Latenz
   - **Empfehlung**: Pattern-Filter vor LLM-Verify fuer offensichtlich deskriptive englische Phrasen

6. **S8/S4 Llama-Guard: Unklare Log-Semantik**
   - 5x S8, 1x S4 UNSAFE-Flags ohne explizites "Ignoring" oder "BLOCKED" im Log
   - Generierung wird fortgesetzt (korrekt), aber Log-Auswertung erschwert
   - **Empfehlung**: Explizite Log-Zeile "Ignoring non-visual codes ['S8']" wie bei S7

---

## 9. Vergleich 05.03. vs. 06.03. vs. 20.03.

| Metrik | 05.03. | 06.03. | 20.03. | Trend |
|--------|--------|--------|--------|-------|
| **Aktive Phase** | 31 min | 3h+ | 2h 40min | Stabil |
| **Geraete (generierend)** | 4 | 9 | 7 | Stabil |
| **Pipeline-Runs** | 58 | 156 | 107 | — |
| **Erfolgsrate** | 72-74% | 76% | **97%** | ↑↑ |
| **Technische Fehler** | ~16 | ~21 | **0** | ↑↑↑ |
| **Safety Level** | kids | kids | youth | Geaendert |
| **Dominant Config** | qwen_img2img (93%) | sd35_large (58%) | sd35 + qwen gleich | Diverser |
| **ComfyUI Timeouts** | 22% | 0% | 0% | Stabil bei 0% |
| **GPU Service Fehler** | 50% (T5) | 0% | 0% | Stabil bei 0% |
| **API-Fehler (Mistral/Ollama)** | 0 | 21 (13.5%) | **0** | GELOEST |
| **VLM Blocks** | 2 | 0 | 1 | Normal |
| **Provider Stage 2** | Mistral | Mistral | Mammouth (Sonnet 4.6) | Gewechselt |

---

## 10. Gesamtfazit

### Was hervorragend funktioniert
- **Null technische Fehler**: Erstmals in 3 Workshops keine einzige technische Failure — alle "Verluste" sind korrekte Safety-Interventionen
- **GPU Service**: 48/48 = 100% Erfolgsrate, stabile 8s/Bild, kein OOM bei 28GB Modell
- **ComfyUI**: ~57 Generierungen (img2img + video + multi) ohne Fehler oder Timeouts
- **Safety-System**: Dreischichtige Filterung unter `youth` funktioniert zuverlaessig. S7-Ignoring verhindert False Blocks. VLM Zwei-Modell-Fallback greift korrekt.
- **Provider-Wechsel auf Mammouth/Sonnet 4.6**: Eliminiert die Mistral 503-Problematik vom 06.03. komplett
- **DSGVO LLM-Verify**: 100% Praezision — keine False Blocks bei 12+ NER-Triggern

### Was verbessert werden muss
- **ComfyUI Startup-Pfad**: Recording-Script zeigt auf falsche `main.py` — Production funktioniert nur dank auto-start Fallback
- **nvidia-ml-py installieren**: VRAM Coordinator braucht Sicht auf gesamte GPU-Nutzung
- **VRAM-Schaetzung korrigieren**: 20GB config vs 28GB real seit 3 Workshops offen
- **S8/S4 Log-Clarity**: Implizites Ignorieren erschwert Audit

### Workshop-Insight (paedagogisch)
**Zwei-Phasen-Didaktik**: Die Daten zeigen ein klares didaktisches Muster:
- **Phase 1** (sd35_large): Strukturierte Uebungen mit geometrischen Formen ("torn paper circle", "geometric quadrilateral", "clay cube", "cable sphere") — kontrollierte Text-to-Image-Exploration
- **Phase 2** (qwen_img2img): Kreative Transformation eigener Fotografien — Schueler*innen fotografieren Alltagsobjekte und transformieren sie iterativ:
  - Klopapierrolle → Regenschirm (6+ Iterationen!)
  - Hand → Hund-auf-Hand-Komposition (5+ Iterationen)
  - CD/Scheibe → Disco-Tanzflaeche (4+ Iterationen)
  - Kleiderbügel → Freisteller → Video-Animation (3 Iterationen inkl. wan22_i2v_video)
  - Objekt → "Zuende es an" / "Auto faehrt dagegen" (kreativ-destruktive Phase)

**Iterationstiefe**: Schueler*innen gehen deutlich tiefer in Iterationsschleifen als in frueheren Workshops. Einzelne Prompt-Ketten umfassen 5-6 Verfeinerungen desselben Motivs. Die qwen_img2img Dominanz in Phase 2 zeigt, dass die Fotografier-und-Transformier-Methodik starkes Engagement erzeugt.

**Lyrics Refinement** (17:54): "6 7 on a merrry rizzmas" — Gen-Z Slang, System produziert stilkonsistente Verfeinerung. Zeigt Plattform-Vielseitigkeit ueber Bildgenerierung hinaus.

