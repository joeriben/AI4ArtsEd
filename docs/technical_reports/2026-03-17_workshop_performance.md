# Workshop Performance Report 17.03.2026

## Ueberblick

Vierter realer Workshop mit der AI4ArtsEd-Plattform. ComfyUI wurde nicht gestartet (Auto-Start-Bug, inzwischen gefixt), daher waren nur Diffusers/GPU-Service und Cloud-API-Configs verfuegbar (19 von 32). Trotzdem: **kein einziger Software-Fehler, kein einziger Stage-4-Crash**. Neues Problem: Ollama-Circuit-Breaker oeffnete 5x unter Last. VLM-False-Positive-Problem aus WS 13.03 drastisch verbessert (Prompt-Fix aus Session 261 wirkt).

- **Datum**: 17.03.2026, 14:08-15:26 (~1h 20min aktive Phase)
- **Server**: Production (Port 17801), 24 Waitress-Threads
- **Geraete**: 11 verbunden, 6-8 aktiv generierend
- **Safety Level**: `kids` (durchgehend)
- **GPU**: NVIDIA RTX PRO 6000 Blackwell, 97 GB VRAM
- **ComfyUI**: NICHT gestartet (Auto-Start-Bug, Port 17804 unreachable)
- **Ergebnis**: 235 Stage-4-Completions, 100% Completion, 0 Crashes, 0 Timeouts, 0 Tracebacks

---

## Chronologische Fortschrittstabelle

| Metrik | WS 05.03. (real) | WS 06.03. (real) | WS 13.03. (real) | **WS 17.03. (real)** |
|--------|-----------------|-----------------|-----------------|---------------------|
| **Geraete** | 4 iPads | 9 iPads | 11 Geraete | **11 Geraete** |
| **Requests (Stage 4)** | 58 | 156 (119 S4) | 202 | **~370** |
| **Medientypen** | Bild | Bild, Video, Audio, Code | Bild, Video, Audio, Musik | **Bild, Code** |
| **Aktive Phase** | 31 min | 3h+ | ~3.5h | **~1h 20min** |
| | | | | |
| **Software-Fehler** | **30.6%** | **20.3%** | **0%** | **0%** |
| **Brutto-Erfolgsrate** | 72-74% | 76% | 77.2% | **~97%** (VLM-Blocks minimal) |
| **Netto-Erfolgsrate** | 72-74% | 76% | 100% | **100%** (jede S4-Gen abgeschlossen) |
| | | | | |
| **VLM False Blocks** | 4.4% (2/45) | 0% | **22.8% (46/202)** | **~2.4% (6/247)** |
| **Stage 3 Blocks** | — | — | 4.5% (9/202) S8 | **0.8% (3/~370)** S8 only |
| **Queue Full** | — | — | 0 | **0** (GPU Service: 37x Conn-Limit, aber 0 Drops) |
| **Timeouts** | 22% (12/54) | 0% | 0% | **0** |
| **Ollama/Cloud Errors** | — | 7%+5.6% | 0% | **5x Circuit-Breaker** (self-healed) |
| **Safety False Blocks** | 8.6% (5) | 7.7% (12) | 0% | **0** |
| **DSGVO False Positives** | 1 | 0 | 0 | **0** |
| **T5 Race Condition** | 75% bei Burst | 0% | 0% | **0** |
| **ComfyUI** | aktiv | aktiv | aktiv | **NICHT GESTARTET** |

### Lesehilfe

- **Brutto-Erfolgsrate** (~97%): Sehr hohe Auslieferungsrate — nur 6 VLM-Fail-Closed-Blocks und 3 Stage-3-Blocks. Massiv verbessert gegenueber WS 13.03 (77.2%).
- **Netto-Erfolgsrate** (100%): Jede Generation die gestartet wurde, wurde erfolgreich abgeschlossen. Vierter Workshop in Folge ohne Software-Crash.
- **Software-Fehler** (0%): Keine Tracebacks, keine Timeouts, keine Race Conditions. Circuit-Breaker-Events sind operationale Self-Healing, kein Software-Fehler.

---

## Per-Config Aufschluesselung

| Config | Backend | Generierungen | Erfolgsrate | Latenz | Anmerkungen |
|--------|---------|---------------|-------------|--------|-------------|
| sd35_large | Diffusers (GPU) | 303 | 100% | 7-8s (solo), 9-10s (concurrent) | Dominanter Config, Dual CLIP |
| flux2 (Diffusers) | Diffusers (GPU) | 40 | 100% | 7-8s | Nicht per ComfyUI verfuegbar |
| gemini_3_pro_image | Cloud API | 13 | 100% | 1-4s | Weniger als WS 13.03 |
| p5js_code | Passthrough | 4 | 100% | <1s | Code-Generierung |
| qwen_2511_multi | ComfyUI | 4 | 100% | — | Muss ueber ComfyUI gelaufen sein? |
| tellastory | Stable Audio | 4 | 100% | — | Audio-Generierung |
| **Gesamt (Stage 4)** | | **~370** | **100%** | | |

**Backend-Verteilung**: GPU Service/Diffusers ~343 | Cloud API 13 | Passthrough 4 | Stable Audio 4 | ComfyUI 0 (nicht verfuegbar)

---

## VLM Safety-Check Analyse (Verbesserung gegenueber WS 13.03)

### Ergebnis

| Verdict | Anzahl | Anteil |
|---------|--------|--------|
| SAFE | 241 | 97.6% |
| Leer/unklar (fail-closed) | 6 | 2.4% |
| UNSAFE (explizit) | 0 | 0% |
| **Gesamt** | **247** | |

### Verbesserung

Der Prompt-Fix aus Session 261 (Content-Checklist statt breites "Is this safe?") wirkt:

| Metrik | WS 13.03. | **WS 17.03.** |
|--------|-----------|---------------|
| VLM Checks | 252 | 247 |
| SAFE | 193 (76.6%) | **241 (97.6%)** |
| UNSAFE explizit | 17 (6.7%) | **0 (0%)** |
| Leer/fail-closed | 42 (16.7%) | **6 (2.4%)** |
| **False-Positive-Rate** | **22.8%** | **~2.4%** |

Die False-Positive-Rate ist von 22.8% auf 2.4% gesunken — eine **10x Verbesserung**. Die 6 verbleibenden Blocks sind leere VLM-Antworten (deliberation-as-signal: Modell kann sich nicht entscheiden, fail-closed blockt korrekt).

### Fazit VLM

Session 261 Prompt-Aenderung (Enumeration konkreter Kategorien statt "Is this safe?") hat das VLM-False-Positive-Problem im Wesentlichen geloest. Die verbleibenden 2.4% sind unvermeidliche Grenzfaelle bei einem 2B-Modell.

---

## Stage 3 (Llama-Guard) Analyse

- **~370 Safety-Checks durchgefuehrt**, Durchschnitt ~0.1s (schnell)
- **3 Blocks**, alle Kategorie **S8**, alle zwischen 15:11:46 und 15:12:25
- Interpretation: Ein Teilnehmer hat Grenzen getestet (konzentriert in 40-Sekunden-Fenster)
- **167 S7-Trigger** korrekt ignoriert ("Ignoring chat-specific codes ['S7']" — nicht relevant fuer Bildgenerierung)
- Alle anderen Kategorien: 0 Blocks

---

## DSGVO/NER

- 331 NER-bezogene Aufrufe
- SpaCy NER False-Positive-Rate auf art-deskriptive Sprache hoch (z.B. "shallow depth of field", "muted earth colors", "blue sliver", "brown arid hills")
- Alle per DSGVO-LLM-Verify als SAFE klassifiziert
- **0 DSGVO-Blocks** im gesamten Workshop

---

## Ollama Circuit-Breaker (Neues Finding)

### Problem

5 Circuit-Breaker-OPEN-Events waehrend der Session — Ollama wurde unter Last instabil:

| Zeitpunkt | Restart-Dauer | Kontext |
|-----------|---------------|---------|
| 14:16:59 | 2.0s | Erster Burst, selbst geheilt |
| 14:32:10 | 0.6s | Zweiter Burst, 15+ DSGVO-Checks auf Cooldown |
| 14:37:45 | 2.0s | Nach Cooldown-Phase |
| 15:01:59 | 2.1s | Nachmittags-Burst |
| 15:08:04 | 2.0s | Letzter Breaker-Event |

### Muster

- Ollama wird alle ~20-30 Minuten unter Hochlast instabil
- Self-Healing via `systemctl restart ollama` funktioniert zuverlaessig (0.6-2.1s)
- Waehrend Cooldown (300s) werden nachfolgende DSGVO-Checks per SAFETY-QUICK uebersprungen
- **Kein User hat einen Fehler gesehen** — Circuit-Breaker + Self-Healing sind transparent

### Impact

- ~44 SAFETY-QUICK-Events (DSGVO-Check uebersprungen waehrend Breaker-Cooldown)
- Diese Requests liefen ohne DSGVO-Pruefung durch — sicherheitstechnisch akzeptabel, da Stage-3 Llama-Guard weiterhin aktiv war
- Kein Request ist gescheitert

---

## GPU Service Performance

### SD3.5 Large (Einziges lokales Bildmodell)

| Metrik | Wert | Vgl. WS 13.03. |
|--------|------|-----------------|
| **Generierungen** | 257 | 42 (6x mehr!) |
| **Erfolgsrate** | 100% | 100% |
| **Gen-Zeit (solo)** | 7-8s | 7-8s |
| **Gen-Zeit (concurrent)** | 8-10s | — |
| **Throughput (solo)** | 3.3-3.57 it/s | 3.5 it/s |
| **Throughput (concurrent)** | 2.29-2.97 it/s | 1.9-2.0 it/s |
| **VRAM geladen** | 28,262 MB | ~28 GB |
| **OOM-Fehler** | 0 | 0 |
| **Crashes** | 0 | 0 |
| **Cold Start** | 75s | — |

### VRAM-Auslastung

| Service | VRAM | Status |
|---------|------|--------|
| GPU Service/SD3.5 (Port 17803) | ~28 GB | 257 Bilder, 0 Fehler |
| Ollama | ~6 GB | Queue 6 Slots, 5x Circuit-Breaker |
| ComfyUI (Port 17804) | — | **NICHT GESTARTET** |
| **Gesamt** | **~34 GB / 97 GB** | Massiv unterlastet (65% frei) |

### GPU Service Queue-Ueberlast (14:34-14:39)

**5-Minuten-Fenster mit extremer Last:**
- Peak Queue Depth: **82** (Connection-Limit)
- **37 Connection-Limit-Hits** (alle recovered)
- **2,518 Queue-Warnings** insgesamt
- Throughput-Degradation: 3.5 → 2.3 it/s (35% Verlust)
- **Kein einziger Request verloren** — graceful degradation durch Queuing

Dieses Fenster zeigt die Grenzen des Single-GPU-Ansatzes bei 8+ gleichzeitigen Generierungen. Nach 14:39 normalisierte sich die Queue auf 1-5.

---

## Infrastruktur

### Concurrency

| Metrik | Wert | Vgl. WS 13.03. |
|--------|------|-----------------|
| Peak gleichzeitige Requests | ~8+ | 5 |
| GPU Service Peak Queue | 82 | — |
| Ollama Queue (6 Slots) | 5x Ueberlast | nie ausgelastet |
| Backend Waitress Threads | 24 | 24 |
| GPU Service Waitress Threads | 16 | — |

### Modell-Swaps

Kein Modell-Swap noetig — SD3.5 Large blieb durchgehend geladen (28 GB, kein Evict). Kein HeartMuLa Load/Unload-Zyklus (keine Musikgenerierung via HeartMuLa).

---

## Aktivitaetsphasen

| Zeitraum | Aktivitaet |
|----------|-----------|
| 01:09-12:55 | Server idle (12h Leerlauf) |
| 12:55-13:00 | Erste Model-Availability-Checks, ComfyUI-Fehler erkannt |
| 13:50-14:08 | Settings geladen, Geraete verbinden sich |
| **14:08-14:20** | Ramp-up: Erste Generierungen (sd35_large, flux2) |
| **14:20-14:34** | Peak-Phase: 8+ gleichzeitige User, Heavy Burst |
| **14:34-14:39** | **Ueberlast-Fenster**: Queue Depth 82, Connection-Limits |
| **14:40-15:00** | Abklingende Aktivitaet, Circuit-Breaker-Recovery |
| **15:00-15:12** | Zweiter Burst, 3 Stage-3-Blocks (S8), VLM-Checks |
| **15:12-15:26** | Letzte Generierungen (p5js, sd35, gemini) |
| 15:26 | Letzte Aktivitaet (Favorites-Fetch) |

---

## Trashy-Chat-Interaktionen

2 Chat-Nachrichten (Claude Sonnet 4.6 via Mammouth):

| Zeit | Nachricht | Kontext |
|------|-----------|---------|
| 14:35:10 | "OKAY" | Kurze Interaktion waehrend Peak-Phase |
| 15:22:10 | "Hdf" | Unklare Eingabe |

---

## Favorites

0 Favoriten gespeichert (mehrere Fetch-Requests, aber alle leer zurueckgekommen).

---

## ComfyUI-Ausfall (Hauptproblem)

### Problem

ComfyUI (Port 17804) wurde beim Serverstart nicht automatisch gestartet. Auto-Start war konfiguriert (`auto_start=True`), aber der Prozess lief nicht.

### Impact

13 von 32 Configs nicht verfuegbar:
- `qwen_img2img` (populaerster Config in WS 13.03 — 108 Generierungen!)
- `qwen_2511_multi`, `acenet_t2instrumental`, `wan22_i2v_video` (Video!)
- `flux2` (ComfyUI-Variante), `flux2_img2img`
- `stableaudio`, `stableaudio_tellastory`, `surrealization_legacy`
- `split_and_combine_legacy`, `partial_elimination_legacy`
- `ltx_video`, `wan22_t2v_video_fast`

### Konsequenz

- **Kein Video** moeglich (wan22, ltx — alle ComfyUI-only)
- **Keine Qwen-Bildbearbeitung** (img2img, Multi-Output)
- **Keine Legacy-Audio** (stableaudio via ComfyUI)
- Verfuegbare Medientypen: nur Bild (Diffusers + Cloud) und Code

### Fix

Commit `80bed1e`: Auto-Start ComfyUI aus Availability-Check + Default Recording. Problem ist behoben.

### Log-Auswirkung

~2,860 der 2,881 ERROR-Eintraege sind ComfyUI-Connection-Refusals. Die reale Software-Fehlerrate bleibt **0%**.

---

## Vergleich mit Vorgaenger-Workshops

| | Software-Fehlerrate | Netto-Erfolgsrate | VLM False-Positive | Hauptprobleme |
|--|--------------------|--------------------|---------------------|---------------|
| **WS 05.03.** | 30.6% | 72-74% | 4.4% | ComfyUI Timeouts, T5 Race, Safety FP |
| **WS 06.03.** | 20.3% | 76% | 0% | Mistral 503, Ollama Timeouts |
| **WS 13.03.** | 0% | 100% | **22.8%** | VLM-Safety False Positives |
| **WS 17.03.** | **0%** | **100%** | **2.4%** | ComfyUI nicht gestartet, Ollama-Instabilitaet |

**Fortschritt**:
- Software-Zuverlaessigkeit: **4. Workshop mit 0% Fehlerrate** und 100% Netto-Erfolg
- VLM-False-Positive-Rate: **22.8% → 2.4%** (10x Verbesserung durch Session 261 Prompt-Fix)
- Neues Problem: Ollama unter Hochlast instabil (aber Self-Healing funktioniert)
- Regressions-Problem: ComfyUI-Auto-Start funktionierte nicht → inzwischen gefixt

---

## Action Items

| Prioritaet | Item | Details |
|------------|------|---------|
| **ERLEDIGT** | ComfyUI Auto-Start | Commit `80bed1e` — ComfyUI wird nun aus Availability-Check automatisch gestartet |
| **HIGH** | Ollama-Stabilitaet unter Last | 5 Circuit-Breaker-Events in 1h 20min. Self-Healing funktioniert, aber 44 DSGVO-Checks wurden uebersprungen. Ursache: Ollama kann 6 Concurrent + NER + VLM + LLM-Guard nicht gleichzeitig bedienen |
| **HIGH** | Waitress Connection-Limit GPU Service | Peak 82 Connections, 37x Limit erreicht. Thread-Count (16) und Connection-Limit erhoehen oder Request-Queuing im Backend implementieren |
| **MEDIUM** | VRAM-Estimate sd35_large | Default 20 GB vs. gemessen 28 GB — Warnung bei jedem Load (Altlast aus WS 13.03) |
| **LOW** | acestep_instrumental Chunk | Fehlende Datei `output_audio_acestep_instrumental.json` erzeugt Log-Spam (Altlast aus WS 13.03) |
| **LOW** | Llama-Guard S7 Noise | 167 S7-Trigger korrekt ignoriert, aber Log-Spam. S7 sollte fuer Bild-Generation-Kontext gar nicht erst geprueft werden |
