# Workshop 19.03.2026 - Realwelt-Performance-Analyse

## Kontext
Vierter dokumentierter Realwelt-Workshop der AI4ArtsEd-Plattform. Backend lief auf Production-Server (Port 17801) mit RTX PRO 6000 Blackwell 96GB. Drei Logfiles ausgewertet: Backend (~5.4MB, groesstes Workshop-Log bisher), ComfyUI (~56KB), GPU Service (~545KB). Vergleichsbasis: Workshops `05.03.`, `06.03.`, `20.03.`. **Groesste Workshop-Session bisher** mit 12 Devices und extremen Burst-Dichten. Safety Level `kids`.

---

## 1. Session-Ueberblick

| Metrik | Wert | Vgl. 20.03. |
|--------|------|-------------|
| **Zeitfenster** | 13:01 - 15:15 (2h 14min) | 14:58 - 17:54 (2h 56min) |
| **Aktive Generierungsphase** | 14:00 - 14:48 (48min Hauptburst) | 15:14 - 17:54 (2h 40min) |
| **Aktive Geraete (generierend)** | 12 | 7 |
| **Geraete gesamt (verbunden)** | 12 | 9 |
| **Safety Level** | `kids` | `youth` |
| **Waitress Threads** | 24 | 24 |
| **Pipeline-Runs gesamt (unique)** | ~253 | ~107 |
| **Stage 4 Ausfuehrungen** | 222 (inkl. Retries) | 105 |
| **Stage 4 Completions** | 156 | ~105 |
| **Erfolgreiche Auslieferungen** | 104 | 104 |
| **Erfolgsrate (Auslieferung/Runs)** | **~41%** | 97% |
| **Technische Fehler (unique runs)** | **33** | 0 |
| **GPU Service OOM** | Ja (14:03, mehrfach) | 0 |

**Beobachtung**: Groesster Workshop mit hoechster Last, aber dramatisch niedrigste Erfolgsrate. 12 Devices erzeugen Burst-Dichten, die GPU Service und Ollama ueberfordern. Die 41% Erfolgsrate (104/253) ist die schlechteste aller Workshops. Hauptursachen: GPU OOM-Kaskade und Ollama-Instabilitaet unter Concurrent Load.

---

## 2. Zugriffsmuster

### Request-Verteilung nach Config (Stage 4)

| Config | Ausfuehrungen | Anteil | Backend |
|--------|--------------|--------|---------|
| **sd35_large** | 210 | 95% | GPU Service (Diffusers) |
| **qwen_img2img** | 7 | 3% | ComfyUI |
| **flux2_diffusers** | 2 | 1% | GPU Service |
| **gpt_image_1** | 1 | <1% | Cloud API |
| **sd35_large_turbo** | 1 | <1% | GPU Service |
| **flux2** | 1 | <1% | ComfyUI |

**SD3.5-Dominanz**: 95% aller Stage-4-Requests sind sd35_large — extrem homogene Last auf dem GPU Service. Kein Video, kein Audio, minimales img2img. Unterschied zu 20.03. (45% qwen_img2img): Diese Session war reines Text-to-Image.

### Zeitliche Verteilung (Konzentrierter Burst)
```
Warm-up: 13:03-13:55  3 Test-Generierungen (gpt_image_1, flux2_diffusers)
                       1 qwen_img2img ("Blume ans Bein")
---PAUSE-- 13:55-14:00  ~5 Minuten
HAUPTBURST: 14:00-14:48  ~215 Stage-4-Generierungen in 48 Minuten
          |              Peak: 15 Requests/Minute (14:39)
          |              Peak Concurrent: 12 gleichzeitige Requests
          |              GPU OOM-Kaskade ab 14:03
Cool-down: 14:49-15:15  ~6 vereinzelte Requests
```

**Muster**: Extrem konzentrierter Burst — 98% aller Requests in einem 48-Minuten-Fenster. Im Gegensatz zum 20.03. (Zwei-Phasen-Muster ueber 2.5h) hier ein einziger massiver Block.

### Aktive Geraete
12 generierende Devices (alle mit `_2026-03-19` Suffix):
`09cdcb15`, `1654e452`, `2205838a`, `54732b43`, `8786c557`, `a205debc`, `af5ec650`, `ba2b66ff`, `cdb897ba`, `d0277548`, `dc2edac8`, `fd7c2086`

---

## 3. Pipeline-Durchlauf & Erfolgsraten

### End-to-End Ergebnis (~253 Unique Pipeline Runs)
```
~253 Unique Pipeline Runs
 |
 +-- ~6 DSGVO-getriggert (NER + LLM-Verify)
 |    +-- 3 korrekt BLOCKED ("Ben kuessen", "BabysWo Edie diewoelfe")
 |    +-- 3 korrekt SAFE (False Positive NER, LLM korrigiert)
 |
 +-- 1 BLOCKED by Stage 3 Llama-Guard (S4)
 +-- ~33 technische Fehler (Queue Full, OOM, Timeouts)
 |
 = 222 Stage 4 Starts (inkl. Retries)
 |
 +-- 156 Stage 4 Completions
 +-- 66 Stage 4 Failures:
 |    +-- ~43 ComfyUI Queue Full (SD3.5 Fallback ueberfordert)
 |    +-- ~20 Diffusers Backend Not Available
 |    +-- ~6 Diffusers 500 (GPU OOM)
 |
 +-- 2 VLM Post-Gen Blocks (Woelfe mit roten Augen — korrekt fuer kids)
 |
 = ~104 Medien an Nutzer ausgeliefert
```

**Erfolgsrate**: 104/253 = **41%** (vs. 97% am 20.03., 76% am 06.03.)
**Technische Fehler**: 33 unique Runs mit technischem Failure — hoechste Zahl aller Workshops.

### Fehlerquellen-Aufschluesselung

| Fehlerquelle | Anzahl | Rate | Vgl. 20.03. |
|-------------|--------|------|-------------|
| **GPU OOM Kaskade** | ~20+ | ~8% | 0 |
| **ComfyUI Queue Full** | 43 Logeintraege | — | 0 |
| **Diffusers Timeout (120s)** | 61 Logeintraege | — | 0 |
| **Empty Results (SD3.5)** | 65 Logeintraege | — | 0 |
| **Ollama Failures** | 129 | — | 0 |
| **DSGVO Block** | 3 | 1.2% | 0 |
| **Stage 3 Block (S4)** | 1 | 0.4% | 1 |
| **VLM Block** | 2 | 0.8% | 1 |

---

## 4. Stage-Performance-Timings

### Stage 1 (Safety Fast-Filter)
- SpaCy NER + POS-Tag Pre-Filter: <100ms (wenn geladen)
- Erster Request: SpaCy unavailable → LLM Fallback (3.0s)
- Danach: SpaCy geladen, 9.2ms typisch
- §86a-Terme geladen: 89 Terms (6 Sprachen)

### Stage 2 (Prompt Interception via Mammouth/Claude Sonnet 4.6)
- Typisch: 2-5 Sekunden
- **Provider**: Mammouth (claude-sonnet-4-6) — stabil, keine Ausfaelle
- Length guidance: 80 words (kids mode)

### Stage 3 (Translation + Llama-Guard)
- Llama-Guard: 100-1500ms (Spitzen unter Last bei 14:03+)
- S7 Flags: ~6x (alle korrekt ignoriert fuer Bildgenerierung)
- S4 Flags: ~2x (1x blockiert — "Ein Maedchen mit einer Zigarette")
- DSGVO NER: False Positives bei englischen Beschreibungen ("curly brown hair medium-skin child", "muted tones")
- DSGVO LLM-Verify: Korrekt SAFE, aber 1.5-17s Latenz (qwen3:1.7b ueberlastet)

### Stage 4 (Generation)
- **SD3.5 Large (GPU Service)**: ~8s pro 1024x1024 @ 25 Steps (wenn verfuegbar)
- **Bottleneck**: GPU Service unter Concurrent Load → OOM → Fallback zu ComfyUI → Queue Full
- **GPU OOM-Kaskade ab 14:03**: 66GB PyTorch + 20GB ComfyUI = 86GB → kein Platz fuer neue Requests

---

## 5. GPU Service Performance — Kritisches Versagen

| Metrik | Wert | Vgl. 20.03. |
|--------|------|-------------|
| **SD3.5 Requests** | ~210 | 48 |
| **Erfolgreiche Generierungen** | ~104 | 48 (100%) |
| **GPU OOM Errors** | **Ja (14:03, Kaskade)** | 0 |
| **Empty Results** | 65 | 0 |
| **Diffusers Timeouts** | 61 | 0 |
| **VRAM bei Start** | 97.9 GB total, ~1.2 GB belegt | ~1.2 GB |
| **VRAM unter Last** | **95+ GB** (Diffusers 66GB + ComfyUI 20GB + Ollama 5GB) | — |
| **OOM-Ursache** | Concurrent SD3.5 Requests + ComfyUI + Ollama | — |

### GPU OOM-Kaskade (14:03)
Die kritische Sequenz aus dem GPU Service Log:
1. **13:10**: Erster OOM — `expected mat1 and mat2 to have the same dtype` (BFloat16-Fehler unter Speicherdruck)
2. **14:01**: SD3.5 Model Load fehlgeschlagen: `CUDA out of memory. Tried to allocate 12.00 MiB. GPU has 4.81 MiB free`
3. **14:03:23-24**: **7 OOM-Errors in 1 Sekunde** — PyTorch: 65.5 GB allokiert, ComfyUI: 20.4 GB, Ollama: 5.9 GB → 96 GB voll
4. Danach: Model muss neu geladen werden → 46s Kaltstart → weitere Requests in Queue laufen in Timeout

**VRAM-Kaskade**: 12 Devices senden gleichzeitig → Requests akkumulieren → GPU Service versucht concurrent zu generieren → OOM → Fallback zu ComfyUI → ComfyUI ebenfalls voll (10 pending) → Queue Full Error

---

## 6. Ollama-Instabilitaet — 129 Failures

| Fehlertyp | Anzahl | Ursache |
|-----------|--------|---------|
| Connection Aborted (RemoteDisconnected) | 59 | Ollama Runner crashed unter VRAM-Druck |
| Read Timeout (30s) | 53 | Ollama blockiert durch GPU-Konkurrenz |
| Connection Refused (Errno 111) | 4 | Ollama-Prozess kurzzeitig tot |
| DSGVO LLM-Verify returned None | 17 | qwen3:1.7b ueberlastet → fail-closed |
| Llama-Guard returned None | 2 | llama-guard3:1b ueberlastet → fail-closed |

**Root Cause**: Ollama konkurriert mit GPU Service und ComfyUI um VRAM. Unter Spitzenlast (14:03-14:20) werden Ollama-Modelle aus dem VRAM verdraengt, was zu RemoteDisconnected und Timeouts fuehrt. Die 4 "Connection Refused" deuten auf einen kurzzeitigen Ollama-Crash hin.

---

## 7. Safety-System Gesamtbewertung

### Stage 1 (Fast-Filter)
- SpaCy-Verzoegerung beim ersten Request (5.4s Modelload) — danach <10ms
- **0 Blocks** — korrekt

### Stage 3 Llama-Guard
- S7 (Self-Harm): ~6x UNSAFE → **alle korrekt ignoriert**
- S4 (Child Safety): 1x → **BLOCKED** ✓ ("Ein Maedchen mit einer Zigarette")
- S6 (Privacy): Vereinzelt, nicht blockierend
- **2 Llama-Guard returned None** (fail-closed, Ollama ueberlastet)

### VLM Post-Generation Safety (qwen3-vl:2b)
- 2 Blocks (unique runs):
  - Woelfe mit roten Augen in dunklem Wald → **UNSAFE** ✓ (korrekt fuer kids)
  - Zweiter Block auf dasselbe Motiv (Retry)
- Alle anderen Checks: SAFE (wandernde Kinder, Tiere mit Fluegeln, Minecraft-Wuerfel etc.)

### DSGVO Data Protection
- NER-Trigger auf:
  - "curly brown hair medium-skin child" (False Positive → LLM: SAFE)
  - "muted tones" (False Positive → LLM: SAFE)
  - "Ben kuessen, Hannahs B" → LLM: **Inkonsistent** (2x SAFE, 1x UNSAFE)
  - "BabysWo Edie diewoelfe" → LLM: **UNSAFE** (korrekt — "Edie")
- DSGVO LLM-Verify **teilweise inkonsistent**: Derselbe Input "Ben kuessen" wurde 2x als SAFE und 1x als UNSAFE klassifiziert
- **17x LLM-Verify returned None** (Ollama ueberlastet → fail-closed)

### Eingabe-Analyse (paedagogisch relevant)
Typische Kids-Eingaben dieses Workshops:
- Emoji-Prompts: `👩🏼🧑🏽‍🦱`, `🧜🏽‍♀️🧜🏽‍♂️💍`
- Grenz-Austestung: `🖕🖕🖕...` (34x Mittelfinger), "Eine Frau mit einer Zigarette"
- Popkultur: "Feuerpfote aus Warrior Cats", "Dschungel Buch"
- Gaming: "A huge cube in the Minecraft world"
- Kreativ: "Eine Leiter hat Augen und Mund und redet mit einem..."
- Romantik: "Hannah und Ben kuessen sich und alle sind gluecklich und Hannah ist schwanger"
- Baby/Tier-Motive: "Bitte ein Wolfsrudel mit Babys S6 realistisch"

---

## 8. Identifizierte Probleme & Handlungsempfehlungen

### KRITISCH

1. **GPU OOM-Kaskade bei 12+ Concurrent SD3.5 Requests**
   - 96 GB VRAM reichen nicht fuer Diffusers (28GB) + ComfyUI (20GB) + Ollama (5GB) bei >8 gleichzeitigen Requests
   - Kaskade: OOM → Fallback zu ComfyUI → Queue Full → massive Errors
   - **Empfehlung**: Request-Queuing im GPU Service mit max concurrent generations (z.B. 3-4 gleichzeitig statt unbegrenzt). Restliche Requests warten statt OOM.

2. **Ollama-Instabilitaet unter GPU-Konkurrenz**
   - 129 Failures in 2h — RemoteDisconnected, Timeouts, Connection Refused
   - Betrifft LlamaGuard, DSGVO-Verify, VLM-Safety — alle sicherheitsrelevant
   - **Empfehlung**: Ollama VRAM-Limit konfigurieren (`OLLAMA_MAX_VRAM`) oder auf CPU-Only fuer kleine Modelle (qwen3:1.7b, llama-guard3:1b) umstellen

### MITTEL

3. **DSGVO LLM-Verify inkonsistent bei echten Namen**
   - "Ben kuessen" wurde 2x SAFE, 1x UNSAFE klassifiziert
   - qwen3:1.7b ist unter Last unzuverlaessig fuer diesen Task
   - **Empfehlung**: Groesseres Modell fuer DSGVO-Verify oder deterministischere Entscheidungslogik

4. **SD3.5 VRAM-Schaetzung weiterhin falsch**
   - Config: 20000 MB, Real: 28262 MB (+41%)
   - Seit 05.03. offen — jetzt erstmals mit Impact (OOM)
   - **Empfehlung**: VRAM estimate auf 29000 MB korrigieren

### NIEDRIG

5. **SpaCy Cold-Start Latenz**
   - Erster Request: 5.4s fuer SpaCy-Load → Fallback zu LLM (3s)
   - **Empfehlung**: SpaCy beim Startup vorwaermen, nicht beim ersten Request

---

## 9. Vergleich 05.03. vs. 06.03. vs. 19.03. vs. 20.03.

| Metrik | 05.03. | 06.03. | 19.03. | 20.03. | Trend |
|--------|--------|--------|--------|--------|-------|
| **Aktive Phase** | 31 min | 3h+ | 48 min (Burst) | 2h 40min | Variabel |
| **Geraete (generierend)** | 4 | 9 | **12** | 7 | ↑ Peak |
| **Pipeline-Runs** | 58 | 156 | **253** | 107 | ↑ Peak |
| **Erfolgsrate** | 72-74% | 76% | **41%** | 97% | ⚠ |
| **Technische Fehler** | ~16 | ~21 | **33** | 0 | ⚠ |
| **Safety Level** | kids | kids | kids | youth | — |
| **Dominant Config** | qwen_img2img | sd35_large | sd35_large (95%) | sd35+qwen | — |
| **GPU OOM** | Nein | Nein | **Ja (Kaskade)** | Nein | ⚠ NEU |
| **Ollama Failures** | 0 | ~21 | **129** | 0 | ⚠ Peak |
| **Provider Stage 2** | Mistral | Mistral | Mammouth | Mammouth | — |

### Einordnung: Warum 19.03. so viel schlechter als 20.03.?

| Faktor | 19.03. | 20.03. | Impact |
|--------|--------|--------|--------|
| **Devices** | 12 | 7 | 71% mehr gleichzeitige Last |
| **Burst-Dichte** | 215 Req in 48min | 107 Req in 2h40min | 4x hoehere Req/min |
| **Config-Diversitaet** | 95% sd35_large | 45%/43% gemischt | Monokultur → GPU Service als einziger Bottleneck |
| **Pause** | Keine | 1h Pause (Phase 1→2) | Kein Cooldown fuer GPU |
| **Safety Level** | kids | youth | kids → +1 Ollama-Call/Req (Translation) |

Die Kombination aus **71% mehr Devices**, **4x hoeherer Burst-Dichte**, **95% Monokultur auf einem Backend** und **keiner Pause** hat die OOM-Kaskade ausgeloest. Der 20.03. Workshop (7 Devices, gemischte Backends, 1h Pause) lag unter der Belastungsgrenze.

---

## 10. Gesamtfazit

### Was funktioniert hat
- **Mammouth/Sonnet 4.6**: Null Stage-2-Ausfaelle trotz 253 Runs — Provider-Stabilitaet bewiesen
- **Safety-System (bei verfuegbaren Ressourcen)**: S4-Block korrekt, VLM-Blocks korrekt, S7-Ignoring zuverlaessig
- **SD3.5 Generierung (einzeln)**: ~8s/Bild wenn GPU verfuegbar — Latenz unveraendert gut

### Was versagt hat
- **GPU Service Concurrency**: Kein Queueing, keine Begrenzung gleichzeitiger Generierungen → OOM bei 12 Concurrent Requests
- **Ollama unter GPU-Konkurrenz**: 129 Failures, teilweise sicherheitsrelevant (Llama-Guard, DSGVO-Verify, VLM)
- **Fallback-Kette**: Diffusers OOM → ComfyUI Fallback → ComfyUI Queue Full → totaler Ausfall. Keine Graceful Degradation.

### Workshop-Insight (paedagogisch)
**Grenz-Austestung**: Die Prompt-Analyse zeigt typisches kids-Verhalten — Mittelfinger-Emojis, Zigaretten, romantische Szenarien mit realen Namen ("Hannah und Ben kuessen sich"), Popkultur-Referenzen. Das Safety-System hat korrekt reagiert (S4-Block auf Zigarette, DSGVO-Block auf "Ben kuessen"), aber die Ollama-Instabilitaet hat die Zuverlaessigkeit der Safety-Entscheidungen reduziert (17x LLM-Verify returned None).

**Minecraft/Emoji als UI-Pattern**: Mehrere Schueler*innen nutzten ausschliesslich Emoji-Prompts (Meerjungfrau-Paare, Hautfarben-Varianten) oder Gaming-Referenzen (Minecraft-Wuerfel). Die Plattform verarbeitet diese korrekt — Stage 2 transformiert Emoji in beschreibende Prompts.

**Burst-Verhalten**: 12 Devices ohne Pause erzeugen Lastmuster, die ueber dem aktuellen Systemlimit liegen. Fuer Workshops mit >8 TN muss Request-Queuing implementiert werden.

---

## 11. Replay-Testrun 22.03.2026 (devserver, Port 17802)

### Setup
- **Skript**: `simulate_workshop_260306.py` (119 Requests, bewaeherter Workshop-Load 06.03.)
- **Target**: devserver (Port 17802, develop-Branch)
- **Parameter**: `--max-gap 15 --image Flux2_randomPrompt_ClaudeSonnet4.5/...` (echtes Bild fuer img2img)
- **VRAM-Start**: ~6.7 GB / 97.9 GB (clean)
- **Backends**: GPU Service (Diffusers), ComfyUI, Ollama — alle verfuegbar

### Ergebnisse

| Metrik | Original 06.03. (Prod) | Replay 22.03. (Dev) | Delta |
|--------|----------------------|---------------------|-------|
| **Erfolgsrate** | 76% | **82%** | +6pp |
| **Success** | ~91 | 97/119 | +6 |
| **Blocked (Safety)** | ~12 (S7) | 1 | S7-Ignoring wirkt |
| **Errors gesamt** | ~21 | 21 | Gleich |
| **Mistral 503** | 10 (6.4%) | **0** | Mammouth stabil |
| **Ollama Timeout** | 11 (7%) | **0** | Ollama stabilisiert |
| **Queue Full** | 0 | **21 (18%)** | Physikalische Grenze |
| **Timeouts** | — | **0** | Kein Timeout |
| **Server Crash** | — | **0** | Stabil |

### Per-Config Breakdown

| Config | Erfolg | Avg Latenz | Anmerkung |
|--------|--------|-----------|-----------|
| **sd35_large** | 64/74 (86%) | 78.7s | 10 Failures = ComfyUI-Fallback Queue Full |
| **qwen_img2img** | 12/16 (75%) | 326.0s | 4x Queue Full in Burst-Phase |
| **wan22_t2v_video_fast** | 11/18 (61%) | 281.6s | 7x Queue Full — Video laeuft lange, blockiert Queue |
| **qwen_2511_multi** | 8/9 (89%) | 134.4s | 1x Queue Full |
| **ltx_video** | 1/1 (100%) | 60.5s | — |
| **acenet_t2instrumental** | 1/1 (100%) | 301.9s | Audio — funktioniert |

### Bewertung

Die **unkontrollierten** Fehler der Production-Session (Mistral API 503, Ollama Timeouts, T5 Race Conditions) sind **vollstaendig eliminiert**. Alle 21 verbleibenden Fehler sind **kontrollierte "Queue Full"-Ablehnungen** — die physikalische Durchsatzgrenze der Hardware meldet sich jetzt sauber statt mit Crashes oder Timeouts.

**Fazit**: Die Software-Seite ist ausoptimiert. Die verbleibenden 18% Fehler sind Hardware-Throughput-Limits (ComfyUI max 10 pending). Diese Grenze ist physikalisch — mehr gleichzeitige Generierungen erfordern mehr VRAM oder langsamere Modelle. Eine **Queue-Anzeige** fuer User (geplant) wuerde die UX verbessern, ohne die Durchsatzgrenze zu verschieben.

### Entdeckter Bug: Ollama qwen3-vl Crash bei Bildern <32px

Waehrend der Vorbereitung des Replay-Tests wurde ein kritischer Bug entdeckt und behoben:
- **Bug**: Ollama's qwen3-vl ImageProcessor panicked bei Bildern mit Breite oder Hoehe <32px (`SmartResize factor=32`)
- **Impact**: Ein einziger zu kleiner Bild-Input killt den Ollama VLM-Runner-Prozess. Alle nachfolgenden VLM-Safety-Checks schlagen mit 500 fehl bis Ollama neugestartet wird.
- **Fix**: Minimum-Size-Check in `vlm_safety.py` — Bilder unter 64px werden automatisch hochskaliert bevor sie an Ollama gesendet werden.
- **Datei**: `devserver/my_app/utils/vlm_safety.py` (VLM_MIN_SIZE = 64, in `vlm_safety_check()` und `vlm_describe_image()`)
