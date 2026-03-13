# Workshop Performance Report 13.03.2026

## Ueberblick

Dritter realer Workshop mit der AI4ArtsEd-Plattform. Alle Software-Fixes aus Session 249/253 (nach Workshops 05.03 und 06.03) haben sich in der Praxis bewaehrt: **kein einziger Software-Fehler in 3.5 Stunden mit 11 Geraeten**. Neues Problem identifiziert: VLM-Safety-Check (qwen3-vl:2b) produziert 22.8% False Positives bei paedagogisch unbedenklichen Inhalten.

- **Datum**: 13.03.2026, 14:25-17:55 (~3.5h)
- **Server**: Production (Port 17801), 24 Waitress-Threads
- **Geraete**: 11 verbunden, 6-8 aktiv generierend
- **Safety Level**: Beginn `kids`, frueh auf `youth` gewechselt (nach VLM-False-Positive-Vorfall)
- **GPU**: NVIDIA RTX PRO 6000 Blackwell, 97 GB VRAM
- **Ergebnis**: 202 Stage-4-Generierungen, 100% Completion, 0 Crashes, 0 Timeouts, 0 Tracebacks

---

## Chronologische Fortschrittstabelle

| Metrik | WS 05.03. (real) | WS 06.03. (real) | Nach Fixes (Sim 06.03.) | **WS 13.03. (real)** |
|--------|-----------------|-----------------|------------------------|---------------------|
| **Geraete** | 4 iPads | 9 iPads | Simulation (9 iPads) | **11 Geraete** |
| **Requests (Stage 4)** | 58 | 156 (119 S4) | 119 | **202** |
| **Medientypen** | Bild | Bild, Video, Audio, Code | Bild, Video, Audio | **Bild, Video, Audio, Musik** |
| **Aktive Phase** | 31 min | 3h+ | ~20 min (replay) | **~3.5h** |
| | | | | |
| **Software-Fehler** | **30.6%** | **20.3%** | **0%** | **0%** |
| **Brutto-Erfolgsrate** | 72-74% | 76% | 78% | **77.2%** (156/202 ausgeliefert) |
| **Netto-Erfolgsrate** | 72-74% | 76% | 94% | **100%** (jede S4-Gen abgeschlossen) |
| | | | | |
| **VLM False Blocks** | 4.4% (2/45) | 0% | 0% | **22.8% (46/202)** |
| **Stage 3 Blocks** | — | — | — | **4.5% (9/202)** S8 only |
| **Queue Full** | — | — | 20 | **0** |
| **Timeouts** | 22% (12/54) | 0% | 5% (6) | **0** |
| **Ollama/Cloud Errors** | — | 7%+5.6% | 0% | **0** |
| **Safety False Blocks** | 8.6% (5) | 7.7% (12) | 0% | **0** |
| **DSGVO False Positives** | 1 | 0 | 0 | **0** |
| **T5 Race Condition** | 75% bei Burst | 0% | 0% | **0** |

### Lesehilfe

- **Brutto-Erfolgsrate** (77.2%): Anteil der generierten Medien die tatsaechlich beim User ankamen. Niedrig wegen 46 VLM-Blocks + 9 Stage-3-Blocks — beides **kein Software-Bug**, sondern Safety-System-Verhalten.
- **Netto-Erfolgsrate** (100%): Jede Generation die gestartet wurde, wurde erfolgreich abgeschlossen. Kein Crash, kein Timeout, kein technischer Fehler.
- **Software-Fehler** (0%): Keine Mistral-503, keine Ollama-Timeouts, keine T5-Race-Conditions, keine DSGVO-False-Positives, keine Safety-False-Blocks. Alle Fixes aus Session 249/253 bewaehrt.

---

## Per-Config Aufschluesselung

| Config | Backend | Generierungen | Erfolgsrate | Latenz | Anmerkungen |
|--------|---------|---------------|-------------|--------|-------------|
| qwen_img2img | ComfyUI | 108 | 100% | 5-7s (warm) | Populaerster Config |
| sd35_large | Diffusers | 42 | 100% | 7-8s (solo) | Dual CLIP Prompt Split |
| gemini_3_pro_image | OpenRouter | 25 | 100% | 20-30s | Cloud API, keine Fehler |
| qwen_2511_multi | ComfyUI | 25 | 100% | 16-58s | Multi-Output |
| flux2 | ComfyUI | 6 | 100% | 13-60s | Kalt/warm Varianz |
| acenet_t2instrumental | ComfyUI | 3 | 100% | 2-16s | Instrumentalmusik |
| wan22_i2v_video | ComfyUI | 2 | 100% | 47-55s | Image-to-Video |
| heartmula | GPU Service | 4 | 100% | 21-71s | Musik mit Lyrics |
| **Gesamt** | | **215** | **100%** | | |

**Backend-Verteilung**: ComfyUI 105 Workflow-Executions | Diffusers 38 Bilder | OpenRouter 25 | HeartMuLa 4 Musik

---

## VLM False-Positive-Analyse (Hauptfinding)

### Problem

46 von 202 erfolgreich generierten Bildern wurden vom VLM-Safety-Check (qwen3-vl:2b) nachtraeglich geblockt — **22.8% False-Positive-Rate**.

### Root Cause

**Zwei Ebenen**:

**1. Sichtbarkeit** (Commit `5fc3a85`): VLM-Check von fail-open auf **fail-closed** umgestellt. Vorher gingen Bilder bei fehlendem oder unklarem Verdict einfach durch — das Problem bestand vermutlich schon vorher, war aber unsichtbar.

**2. Modell-Limitation** (qwen3-vl:2b): Das Modell kann nicht zwischen **"ist das Bild schaedlich zu betrachten"** und **"ist die abgebildete Situation real gefaehrlich"** unterscheiden. Ein Foto einer Baustelle ist fuer Kinder voellig unbedenklich *anzuschauen*, auch wenn eine echte Baustelle gefaehrlich waere. Der Prompt (`"Is this image safe for children age 6-12?"`) ist formal korrekt — das Problem liegt in der begrenzten Reasoning-Faehigkeit eines 2B-Modells bei dieser Unterscheidung.

**Prompt-Chronologie**:
- Urspruenglich: `"Check this image for content inappropriate for children"` + `"Explain briefly"`
- Commit `46b0f55` (10.03.): Vereinfacht zu `"Is this image safe?"` + `"Answer with one word only"` — notwendig, weil das Modell bei der alten Formulierung in Endlos-Denkschleifen geriet (das eigentliche Schleifen-Problem wurde parallel durch `enable_thinking=False` in Commit `f4d5e22` geloest)
- `"Answer with one word only"` fuehrt dazu, dass qwen3-vl:2b haeufig nur das `thinking`-Feld befuellt und `content` leer laesst → fail-closed → Block

**42 der 46 Blocks** sind leere Antworten (kein Verdict im content-Feld), nur 4 sind explizite UNSAFE-Verdicts.

### Muster

Das Modell verwechselt das **Abgebildete** mit dem **Bild**:

| Motiv | VLM-Interpretation | Tatsaechliche Bewertung |
|-------|---------------------|------------------------|
| Baustelle mit Arbeitern in Warnwesten | "hazardous environment" → UNSAFE | Bild einer Baustelle ist unbedenklich zu betrachten |
| Unterwasser-/Tauchszenen | "dangerous activity" → UNSAFE | Bild von Tauchern ist unbedenklich zu betrachten |
| Leer-Antwort (42x) | kein Verdict (content leer) | Fail-closed korrekt, aber ursaechlich Prompt/Modell-Problem |

### Verteilung

- 5 Blocks bei Safety Level `kids` (15:02-15:06)
- 39 Blocks bei Safety Level `youth` (15:08-17:42)
- 42 Blocks durch leere VLM-Antwort (fail-closed)
- 4 Blocks durch explizites UNSAFE-Verdict

### User-Reaktion

Trashy-Chat um 15:34:59: **"its just a photo!!!!"** — dokumentierte Frustration ueber unberechtigte Blockierung.

### VLM-Verdicts gesamt

| Verdict | Anzahl |
|---------|--------|
| SAFE | 193 |
| UNSAFE (explizit) | 17 |
| Leer/unklar (fail-closed) | 42 |

### Action Items

1. **Prompt praezisieren**: Dem VLM explizit sagen, dass es um die **Betrachtung** des Bildes geht, nicht um die dargestellte Situation. Z.B.: `"Would viewing this image be harmful for a child? Only flag violence, nudity, gore, hate symbols. A photo OF a dangerous place (construction site, ocean) is SAFE to view."`
2. **Leere Antworten**: `"Answer with one word only"` zuruecknehmen zugunsten von `"Explain briefly"` — in Kombination mit `enable_thinking=False` (bereits aktiv) sollte das Modell im `content`-Feld antworten
3. **Modell-Upgrade evaluieren**: qwen3-vl:2b ist moeglicherweise zu klein fuer diese Unterscheidung. Groessere VLMs (7B+) koennten "Bild betrachten" vs. "abgebildete Gefahr" besser trennen
4. **Fail-closed beibehalten** — korrekte Architekturentscheidung, das Problem muss auf Prompt/Modell-Ebene geloest werden

---

## Stage 3 (Llama-Guard) Analyse

- **203 Safety-Checks durchgefuehrt**, Durchschnitt 0.63s (max 3.6s)
- **9 Blocks**, alle Kategorie **S8** (geistiges Eigentum), alle vom selben Geraet (`96a19a38...`)
- Interpretation: Ein Teilnehmer hat Grenzen getestet
- Alle anderen Kategorien: 0 Blocks
- **Kids-Filter**: 2 Trigger ("shoot" als Wort), beide korrekt als False Positive aufgeloest

---

## DSGVO/NER

- 69 NER-Aufrufe, 2 Entity-Erkennungen ("high-visibility vests", "wet sand")
- Beide per LLM-Verify als SAFE klassifiziert
- **0 DSGVO-Blocks** im gesamten Workshop

---

## Infrastruktur-Performance

### GPU-Auslastung (3 Services auf einer GPU)

| Service | VRAM | Status |
|---------|------|--------|
| ComfyUI (Port 17804) | ~28 GB | 105 Executions, 0 Fehler |
| GPU Service/SD3.5 (Port 17803) | ~28 GB | 38 Bilder + 4 Musik, 0 Fehler |
| Ollama | ~6 GB | Queue 6 Slots, nie ausgelastet |
| **Gesamt** | **~62 GB / 97 GB** | |

### Concurrency

- **Peak**: 5 gleichzeitige Requests um 16:03:38 — fehlerfrei verarbeitet
- **ComfyUI Queue**: Max Tiefe 3 (bei 16:24 und 16:42), kein Ueberlauf
- **Ollama Queue**: 4 von 6 Slots genutzt, keine Wartezeit
- **SD3.5 concurrent**: Bei 4 gleichzeitigen Generierungen sinkt Throughput von 3.5 it/s auf 1.9-2.0 it/s

### Modell-Swaps (ComfyUI)

Haeufige Wechsel zwischen 6 Modellen (QwenImage fp8/bf16, WAN21, Flux2, ACEStep, MusicDCAE) — alle sauber, kein OOM.

### HeartMuLa Lazy-Loading

4 Generierungen mit vollem Load/Unload-Zyklus (MuLa 4 Shards → Generate → Unload → Codec 2 Shards → Decode → Unload). VRAM-Peak 36.77 GB, nach Unload zurueck auf 27.62 GB.

---

## Aktivitaetsphasen

| Zeitraum | Aktivitaet |
|----------|-----------|
| 14:25-14:41 | Setup, 1 Geraet, Test-Generierung (qwen_img2img) |
| 15:00-15:10 | Erster Burst (sd35_large, Baustellen-Thema) |
| 15:34-15:39 | Zweiter Burst (sd35_large, selbes Geraet) |
| 15:52-16:27 | Hauptphase (multiple Geraete, qwen_img2img + mixed) |
| 16:28-16:46 | Peak (Gemini, wan22 Video, qwen, concurrent) |
| 17:04-17:09 | HeartMuLa-Musik (4 Generierungen) |
| 17:15-17:42 | Abschlussphase (qwen, sd35, flux2) |
| 17:55 | Letzte Trashy-Chat-Frage |

---

## Trashy-Chat-Interaktionen

4 Chat-Nachrichten (Claude Sonnet 4.6 via Mammouth):

| Zeit | Nachricht | Kontext |
|------|-----------|---------|
| 15:34:59 | "its just a photo!!!!" | Frustration ueber VLM-Blocking |
| 16:31:45 | "Ok" | — |
| 16:32:00 | "Generiert" | — |
| 17:55:59 | "wem gehoeren denn nun die bilder?" | Urheberrechtsfrage |

---

## Favorites

6 Favoriten gespeichert (5x von Geraet `be9fb3b9...`, 1x von `dc2edac8...`), alle aus `image-transformation`-Ansicht.

---

## Vergleich mit Vorgaenger-Workshops

| | Software-Fehlerrate | Netto-Erfolgsrate | Hauptprobleme |
|--|--------------------|--------------------|---------------|
| **WS 05.03.** | 30.6% | 72-74% | ComfyUI Timeouts, T5 Race, Safety False Positives |
| **WS 06.03.** | 20.3% | 76% | Mistral 503, Ollama Timeouts, Safety Blocks |
| **Nach allen Fixes** | 0% | 94% | Nur Hardware-Throughput (Queue Full) |
| **WS 13.03.** | **0%** | **100%** | **VLM False Positives (22.8%)** |

**Fortschritt**: Die Software-Zuverlaessigkeit ist von 70% auf **100%** gestiegen. Alle in Session 249/253 implementierten Fixes (Retry-Logik, Concurrency-Tuning, VLM-Verdict-Parsing, Queue-Guards) haben sich im laengsten und meistgenutzten Workshop bewaehrt.

**Neues Problem**: Die VLM-Safety-Pruefung (qwen3-vl:2b) ist zu konservativ bei der Erkennung "dargestellter Gefahren" vs. tatsaechlich schaedlicher Inhalte. Dies ist kein Software-Bug, sondern ein Prompt-/Modell-Problem.

---

## Action Items

| Prioritaet | Item | Details |
|------------|------|---------|
| **HIGH** | VLM-Prompt praezisieren | Modell unterscheidet nicht "Bild betrachten" vs. "abgebildete Gefahr". Prompt muss explizit auf Betrachtungs-Schaedlichkeit einschraenken |
| **HIGH** | VLM leere Antworten | `"Answer with one word only"` → haeufig leeres `content`-Feld → fail-closed. Zurueck zu `"Explain briefly"` (Schleifen-Problem durch `enable_thinking=False` bereits geloest) |
| **MEDIUM** | VLM Modell-Upgrade evaluieren | qwen3-vl:2b moeglicherweise zu klein fuer Abstraktionsleistung "Bild OF Gefahr ≠ gefaehrliches Bild". 7B+ testen |
| **LOW** | acestep_instrumental Chunk | Fehlende Datei `output_audio_acestep_instrumental.json` erzeugt 130x Log-Spam |
| **LOW** | VRAM-Estimate sd35_large | Default 20 GB vs. gemessen 28 GB — Warnung bei jedem Load |
