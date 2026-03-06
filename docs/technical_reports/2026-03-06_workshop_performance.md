# Workshop 06.03.2026 - Realwelt-Performance-Analyse

## Kontext
Zweiter Realwelt-Test der AI4ArtsEd-Plattform, einen Tag nach dem ersten Workshop (05.03.). Backend lief auf Production-Server (Port 17801) mit 24 Waitress-Threads. GPU Service nun mit 16 Threads (vorher 4). Drei Logfiles ausgewertet: Backend (~1.8MB), ComfyUI, GPU Service. Vergleichsbasis: `2026-03-05_workshop_performance.md`.

---

## 1. Session-Ueberblick

| Metrik | Wert | Vgl. 05.03. |
|--------|------|-------------|
| **Zeitfenster** | 14:34:49 - 17:43:12 (3h 8min) | 16:10-19:12 (3h) |
| **Aktive Generierungsphase** | ~3 Stunden durchgehend | 31 Minuten! |
| **Aktive Geraete** | 9 | 4 von 9 |
| **Safety Level** | `kids` (durchgehend) | `kids` |
| **Waitress Threads** | 24 | 24 |
| **Unique Generierungslaeufe** | 156 | 58 |
| **ComfyUI-Generierungen** | 51 (100% Erfolg) | 191 (100% Erfolg) |
| **GPU Service Bilder** | 78 (100% Erfolg) | 6 Bilder + 5 Musik |
| **Erfolgsrate gesamt** | ~76% | 72-74% |

**Beobachtung**: Voellig anderes Nutzungsmuster als am Vortag. Am 5.3. nur 31 Minuten konzentrierte Nutzung, am 6.3. ueber 3 Stunden aktive Generierung mit deutlich mehr Geraeten und Medienvielfalt. Die Last hat sich vom ComfyUI-Backend (191 -> 51) zum GPU Service/Diffusers (11 -> 78) verschoben.

---

## 2. Zugriffsmuster

### Request-Verteilung nach Config
| Config | Ausfuehrungen | Anteil | Backend |
|--------|--------------|--------|---------|
| **sd35_large** | 339 | Dominant | GPU Service (Diffusers) |
| **wan22_t2v_video_fast** | 106 | Video | ComfyUI |
| **qwen_img2img** | 64 | Img2Img | ComfyUI |
| **qwen_2511_multi** | 36 | Multi-Modal | ComfyUI |
| **ltx_video** | 6 | Video | ComfyUI |
| **acenet_t2instrumental** | 6 | Audio | ComfyUI |
| **tonejs_code** | 2 | Code-Gen | LLM |
| **stableaudio_open** | 2 | Audio | GPU Service |
| **flux2** | 1 | Bild | ComfyUI |
| **gemini_3_pro_image** | 1 | Bild | Cloud API |
| **p5js_code** | 1 | Code-Gen | LLM |

**Veraenderung vs. 05.03.**: Am Vortag 93% qwen_img2img. Jetzt breite Nutzung aller verfuegbaren Medientypen — erstmals Video-Generierung (Wan 2.1 + LTX) und Code-Generierung im Workshop.

### Zeitliche Verteilung
```
14:34-15:19  Ramp-up, leichte Last
15:19-15:23  Erster Burst (~300-800 Log-Zeilen/Min)
15:24-16:53  Sustained Activity (100-300 Log-Zeilen/Min)
17:00-17:14  PEAK: 630-948 Log-Zeilen/Min, Ollama-Ueberlast
17:15-17:43  Wind-down
```

**Muster**: Deutlich laengere und intensivere Nutzung als am 5.3. (31min burst vs. 3h sustained). Peak bei 17:00-17:14 mit geschaetzt 10-16 gleichzeitigen Requests.

---

## 3. Pipeline-Durchlauf & Erfolgsraten

### End-to-End Ergebnis (156 Runs)
```
156 Unique Runs
 |
 +-- ~10 FAILED in Stage 2 (Mistral API 503 Burst)
 +-- ~12 BLOCKED by Stage 3 (Llama-Guard, S7 dominant)
 +-- ~11 FAILED by Ollama Timeout (Stage 1/DSGVO, Peak-Phase)
 |
 = ~119 erfolgreiche Stage-4-Completions
 |
 +-- 99 Bilder (83%)
 +-- 19 Videos (16%)
 +-- 1 Audio (<1%)
 |
 +-- 0 VLM Post-Gen Blocks
 |
 = 119 Medien an Nutzer ausgeliefert
```

**Erfolgsrate**: 119/156 = **76%** (vs. 72-74% am 05.03.)
**Verbesserung trotz 2.7x hoeherer Last.**

### Fehlerquellen-Aufschluesselung
| Fehlerquelle | Anzahl | Rate | Neu vs. 05.03.? |
|-------------|--------|------|-----------------|
| Mistral API 503 | 10 | 5.6% | NEU |
| Ollama Timeout | 11 | 7% | NEU |
| Llama-Guard Block | ~12 | 7.7% | Erwartet |
| ComfyUI Timeout | 0 | 0% | GELOEST (war 22%) |
| T5 Race Condition | 0 | 0% | GELOEST |
| DSGVO Block | 0 | 0% | Verbessert |
| VLM Block | 0 | 0% | Verbessert |

---

## 4. Stage-Performance-Timings

### Stage 1 (Safety Fast-Filter)
- SpaCy NER + POS-Tag Pre-Filter: <100ms
- 61 explizite "Safety PASSED" Events geloggt

### Stage 2 (Prompt Interception via Mistral)
- Typisch: 2-5 Sekunden
- Output: 615-949 Zeichen
- **Ausfaelle**: 10 Mistral 503 in 74s (15:20:26-15:21:40)

### Stage 3 (Translation + Llama-Guard)
- Translation: 0.6-1.0s
- Llama-Guard: 92-1635ms (typisch ~110ms)
- Gesamt: 1.0-2.4s pro Request

### Stage 4 (Generation)
- SD3.5 (GPU Service): 7-8s pro 1024x1024 @ 25 Steps
- Wan 2.1 Video: 40-50s
- ACEnet Audio: ~47s
- ComfyUI avg: 20.1s (Median 12.7s)

---

## 5. GPU Service Performance

| Metrik | Wert | Vgl. 05.03. |
|--------|------|-------------|
| **SD3.5 Generierungen** | 78 | 6 |
| **Erfolgsrate** | 100% | 50% (3/6 T5 Race) |
| **Gen-Zeit** | 7-8s (3.2-3.5 it/s) | 6-8s |
| **Max Concurrent** | 8 simultane Requests | Queue-Depth 44 (!) |
| **Threads** | 16 | 4 |
| **VRAM geladen** | 28.3 GB (SD3.5) | 28.3 GB |
| **OOM-Fehler** | 0 | 0 |
| **T5 Race Conditions** | 0 | 3 Failures |
| **HeartMuLa Musik** | 0 (nur Health-Checks) | 5 Generierungen |

**Kernaussage**: GPU Service ist von der Problemquelle zur zuverlaessigsten Komponente geworden. 78 Bilder ohne einen Fehler, 8 gleichzeitige Requests problemlos verarbeitet.

### T5 Tokenizer: Bug behoben
- 2 Prompt-Truncation-Warnings (CLIP max 77 Tokens) — das ist normales Verhalten, kein Fehler
- Prompt-Splitting funktioniert korrekt: CLIP bekommt 77 Tokens, T5-XXL den vollen Prompt
- **Keine Race Conditions** mehr (war 3/4 Failures am 05.03.)

---

## 6. ComfyUI Performance

| Metrik | Wert | Vgl. 05.03. |
|--------|------|-------------|
| **Generierungen** | 51 | 191 |
| **Erfolgsrate** | 100% | 100% |
| **Durchschnittliche Gen-Zeit** | 20.1s | 18.0s |
| **Median Gen-Zeit** | 12.7s | — |
| **Schnellste** | ~0s (Skipped) | ~5s |
| **Langsamste** | 57.9s | 91.6s |
| **OOM-Fehler** | 0 | 0 |
| **Crashes** | 0 | 0 |
| **Timeouts (Backend-Seite)** | 0 | 12 (22%) |

**Modelle im Einsatz**: QwenImage (11x), WAN 2.1 (16x), Flux2 (2x), LTXV, ACEStep, Mochi — deutlich hoehere Modellvielfalt als am 5.3. (nur QwenImage + SD3).

**ComfyUI Timeout-Problem geloest**: 0 Timeouts (vs. 22% am 05.03.). Hauptgrund: Lastverlagerung auf GPU Service/Diffusers fuer SD3.5, weniger Queue-Druck auf ComfyUI.

---

## 7. Safety-System Gesamtbewertung

### Stage 3 Llama-Guard
- 115 Verdicts insgesamt
- 103 safe (89.6%)
- ~12 unsafe (S7 dominant mit 8.7%)
- S5: 1, S7: 9, S8: 2-5

### VLM Post-Generation Safety
- 171 Bild-Checks via qwen3-vl:2b
- **0 Blocks** (vs. 2/45 am 05.03.)
- Alle Checks bestanden — entweder zahmere Prompts oder weniger grenzwertige Generierungen

### DSGVO Data Protection
- 20+ NER + LLM-Verify Chains
- NER: 4-159ms pro Prompt
- LLM-Verify: 429-3186ms pro Entity-Set
- **0 Blocks** (vs. 1 False Positive am 05.03.)
- False Positives bei deskriptiven Phrasen ("shadow gradient:1.2", "tomato souse") — LLM-Verify erkennt korrekt als SAFE

---

## 8. Identifizierte Probleme & Handlungsempfehlungen

### KRITISCH — keine

Alle kritischen Bugs vom 05.03. sind behoben. Am 06.03. keine neuen kritischen Probleme.

### MITTEL
1. **Mistral API 503 Burst** (10 Events in 74s)
   - Ursache: Proxy-Saettigung bei hoher Concurrency
   - **Empfehlung**: Exponential Backoff + Retry (max 3 Versuche, 1s/2s/4s)
   - Selbstheilung funktioniert, aber 10 verlorene Requests sind vermeidbar

2. **Ollama Queue-Ueberlast** (11 Timeouts bei Peak)
   - Ursache: 30s Read-Timeout bei 10+ gleichzeitigen Requests an qwen3:1.7b
   - Peak: 8 Failures in 3 Sekunden (17:00:57)
   - **Empfehlung**: `OLLAMA_NUM_PARALLEL` von 3 auf 6-8 erhoehen

3. **acestep_instrumental Chunk fehlt** (weiterhin, seit 05.03.)
   - 16+ Warnungen bei Model-Availability-Checks
   - Nicht nutzungskritisch, aber Log-Verschmutzung

### NIEDRIG
4. **DSGVO NER False Positives** auf deskriptive Phrasen
   - "shadow gradient:1.2", "tomato souse", "digging stances" als Personennamen geflaggt
   - LLM-Verify korrigiert (SAFE), aber 1-4s Latenz pro unnoetigem Verify
   - **Empfehlung**: Numerische Suffixe und offensichtlich deskriptive Patterns vor LLM-Verify filtern

5. **SD3.5 VRAM-Schaetzung** — 28.3 GB real vs. 20 GB konfiguriert (offen seit 05.03.)

---

## 9. Vergleich 05.03. vs. 06.03. — Zusammenfassung

| Metrik | 05.03. | 06.03. | Delta |
|--------|--------|--------|-------|
| **Aktive Phase** | 31 min | 3h+ | 6x laenger |
| **Geraete** | 4 | 9 | +125% |
| **Requests** | 58 | 156 | +169% |
| **Erfolgsrate** | 72-74% | 76% | +3-4pp |
| **ComfyUI Timeouts** | 22% | 0% | GELOEST |
| **T5 Race Condition** | 75% Failure bei Burst | 0% | GELOEST |
| **GPU Service Threads** | 4 (Starvation) | 16 (stabil) | GELOEST |
| **Medientypen** | 2 (Bild, Musik) | 5+ (Bild, Video, Musik, Audio, Code) | Volle Vielfalt |
| **VLM False Positives** | 2 | 0 | Verbessert |
| **Neue Probleme** | — | Mistral 503, Ollama Peak | Mittelschwer |

---

## 10. Gesamtfazit

### Was hervorragend funktioniert
- **GPU Service**: Von der Problemquelle zur zuverlaessigsten Komponente (78/78 = 100%)
- **ComfyUI**: 51/51 Generierungen erfolgreich, 0 Timeouts (vorher 22%)
- **Safety-System**: Dreischichtige Filterung funktioniert stabil unter 3x hoeherer Last
- **Medienvielfalt**: Erstmals Bilder, Videos, Audio UND Code-Generierung im Workshop
- **Skalierung**: 9 Geraete ueber 3+ Stunden bei 76% Erfolgsrate

### Was verbessert werden muss
- **Mistral API Resilienz**: Retry-Logik fuer 503-Bursts
- **Ollama Concurrency**: Peak-Last ueberschreitet aktuelle Queue-Kapazitaet
- **DSGVO NER Praezision**: Unnoetige LLM-Verify-Aufrufe reduzieren

### Workshop-Insight
Die Plattform hat den Sprung von "funktioniert grundsaetzlich" (05.03.) zu "workshop-tauglich unter Reallast" (06.03.) geschafft. Alle drei kritischen Bugs des Vortages wurden behoben. Die verbleibenden Probleme sind mittelschwer und betreffen externe Service-Kapazitaeten unter Spitzenlast — keine strukturellen Defekte mehr.
