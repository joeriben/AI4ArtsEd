# Workshop 05.03.2026 - Realwelt-Performance-Analyse

## Kontext
Erster Realwelt-Test der AI4ArtsEd-Plattform mit 9 iPads in einem Workshop mit Kindern (kids safety level). Backend lief auf Production-Server (Port 17801) mit dem frischen Waitress-Thread-Upgrade von 8 auf 24 Threads. Drei Logfiles ausgewertet: Backend (6368 Zeilen), ComfyUI (917 Zeilen), GPU Service (502 Zeilen).

---

## 1. Session-Ueberblick

| Metrik | Wert |
|--------|------|
| **Zeitfenster** | 16:10:30 - 19:12:25 (ca. 3h) |
| **Aktive Generierungsphase** | 16:10 - 16:41 (31 Minuten!) |
| **Geraete mit Device-ID** | 4 von 9 iPads (im Backend-Log erfasst) |
| **Safety Level** | `kids` (durchgehend) |
| **Waitress Threads** | 24 (nach Upgrade von 8) |
| **Backend-Requests** | 58 Generierungsanfragen |
| **ComfyUI-Generierungen** | 191 abgeschlossene Prompts |
| **GPU Service** | 11 Generierungen (5 Musik, 6 Bilder) |

**Beobachtung**: Nur 31 Minuten aktive Nutzung mit ca. 2 Req/Min Spitze, dann 2h Pause bis zum letzten Log-Eintrag (19:12). Entweder Workshop-Ende oder die Kinder wechselten zu Nicht-Generierungs-Aktivitaeten.

---

## 2. Zugriffsmuster

### Request-Verteilung nach Config
- **qwen_img2img**: 54 Requests (93%) -- Image-to-Image via ComfyUI
- **qwen (T2I)**: 4 Requests (7%) -- Text-to-Image via ComfyUI
- **HeartMuLa Musik**: 5 Generierungen via GPU Service (vor dem Workshop-Fenster, 09:14-09:51)
- **SD3.5 Bilder**: 6 Generierungen via GPU Service/Diffusers (12:46-15:30)

### Zeitliche Verteilung (Backend, pro Minute)
```
16:10 #### (4)
16:11 ### (3)
16:12 # (1)
16:13 ### (3)
16:14 #### (4)
16:15 ### (3)
16:16 ## (2)
16:17 # (1)
16:18 ## (2)
16:19 ### (3)
16:20 #### (4)       <-- Parallel-Phase beginnt
16:21 ## (2)
16:22 ### (3)
16:23 ## (2)
16:24 ##### (5)      <-- Peak
16:25 ## (2)
16:26 ## (2)
16:27 ## (2)
16:28 ### (3)
16:29 ## (2)
16:30 # (1)
16:31 ## (2)
16:36 # (1)          <-- 5min Pause davor
16:41 # (1)          <-- Letzte Generierung
```

**Muster**: Gleichmaessiger Strom von ~2 Req/Min, kein harter Burst. Kinder generieren iterativ (img2img Ketten), nicht alle gleichzeitig.

---

## 3. Pipeline-Durchlauf & Erfolgsraten

### End-to-End Ergebnis (58 Requests)
```
58 Requests
 |
 +-- 3 BLOCKED by Stage 3 (Llama-Guard: 2x S4, 1x S3)
 +-- 1 BLOCKED by DSGVO-Filter (Keyboard-Spam als Name erkannt)
 |
 = 54 gehen zu Stage 4
 |
 +-- 12 TIMEOUT (10x Legacy 300s, ~2x Workflow-Chunk 600s)
 |
 = ~42-45 erfolgreiche Bildgenerierungen
 |
 +-- 2 BLOCKED by VLM Post-Generation (unsafe for kids)
 |
 = ~40-43 Bilder an Kinder ausgeliefert
```

**Erfolgsrate**: ~72-74% der Requests fuehren zu einem ausgelieferten Bild.
**Blockrate Safety**: 5/58 (8.6%) durch Safety-System insgesamt gestoppt.
**Timeout-Rate**: 12/54 (22%) der Stage-4-Requests scheitern am ComfyUI-Timeout.

### Stage 3 Performance (Translation + Safety)
- Durchschnittlich ~0.1-0.5s pro Request
- Mistral API (Translation): 0.6-1.0s
- Llama-Guard: 100-525ms (typisch 110ms)
- **13 Bare S-Code Warnungen**: Llama-Guard gibt S-Codes ohne `unsafe`-Prefix zurueck (S5, S7, S8)
  - **Korrekt behandelt**: System erkennt diese als "chat-specific codes" und ignoriert sie fuer Bildgenerierung
  - Nur S3 (sex/nudity) und S4 (child safety) fuehren zu tatsaechlichen Blocks
  - **Fazit**: Safety-Logik funktioniert intelligent, kein Bug

### VLM Post-Generation Safety
- 45 Bilder durch VLM-Check geschickt (qwen3-vl:2b)
- 43 als `safe` bewertet, 2 geblockt
- **Block-Beispiele**:
  - Maedchen mit Cape in feuriger Umgebung (Feuer als "scary for kids" bewertet)
  - Person mit Schwert auf Bergpfad (Waffe als "unsafe for kids" bewertet)
- **VLM-Reasoning ist nachvollziehbar und paedagogisch korrekt**
- Check-Dauer: ~0.4-0.8s pro Bild

---

## 4. Waitress Thread-Pool Assessment (Kernfrage)

### Ergebnis: 24 Threads AUSREICHEND
- **Null SSE Thread-Starvation** beobachtet
- Alle 58 Streaming-Requests bekamen einen Thread
- Kein "connection refused" oder Queue-Backlog auf Waitress-Ebene
- Das Problem bei 8 Threads war, dass SSE-Streams Threads blockieren (long-lived connections). Bei 4 gleichzeitigen Generierungen + SSE-Streams wuerde man mindestens 8-12 Threads brauchen. 24 bietet ausreichend Headroom.

### Bottleneck ist NICHT Waitress, sondern ComfyUI
- 10 Legacy-Workflow-Timeouts (300s) in 31 Minuten
- ComfyUI verarbeitet sequenziell -- bei 2 Req/Min staut sich die Queue
- ComfyUI-Log: 191 Generierungen, 100% Erfolgsrate auf ComfyUI-Seite
- Diskrepanz: Backend sieht Timeouts, ComfyUI arbeitet alles ab (nur langsamer als der Timeout)

---

## 5. ComfyUI Performance

| Metrik | Wert |
|--------|------|
| **Generierungen** | 191 (100% Erfolg!) |
| **Durchschnittliche Gen-Zeit** | 18.0s |
| **Schnellste** | ~5s (4-Step) |
| **Langsamste** | 91.6s |
| **Gesamte Rechenzeit** | 57min 22s |
| **GPU** | RTX PRO 6000 Blackwell (97 GB VRAM) |
| **VRAM-Modus** | NORMAL_VRAM (kein LowVRAM noetig) |
| **Modelle geladen** | QwenImage (35x), WanVAE (8x), WAN21 (4x), Flux2 (1x), SD3 (1x) |
| **OOM-Fehler** | 0 |
| **Crashes** | 0 |

**Wichtig**: ComfyUI ist stabil und hat NULL Fehler. Die Timeouts im Backend sind ein Mismatch zwischen Backend-Timeout (300s) und ComfyUI-Queue-Verarbeitungszeit.

---

## 6. GPU Service Performance

| Metrik | Wert |
|--------|------|
| **HeartMuLa Musik** | 5 Generierungen, 0 Fehler |
| **SD3.5 Bilder** | 6 Generierungen (+ 3 fehlgeschlagen) |
| **Musik Gen-Zeit (30s)** | 24-33s Echtzeit |
| **Musik Gen-Zeit (120s)** | 53-88s Echtzeit |
| **SD3.5 Gen-Zeit** | 6-8s pro 1024x1024 @ 25 Steps |
| **SD3.5 Load-Time** | 34s (Erstladen) |
| **SD3.5 VRAM** | 28.3 GB (vs. 20 GB Schaetzung!) |

### KRITISCHER BUG: T5 Tokenizer Race Condition
- **3 von 4** gleichzeitigen SD3.5-Requests scheitern mit `RuntimeError: Already borrowed`
- Ursache: T5-Tokenizer in `transformers` ist nicht thread-safe unter konkurrenten Requests
- Queue-Tiefe eskalierte auf 44 Tasks
- **Dies ist ein Diffusers/Transformers-Library-Bug, kein Service-Code-Bug**
- Betrifft nur Burst-Szenarien (3+ gleichzeitige Requests an denselben Endpunkt)

### GPU Service Thread-Pool zu klein
- Aktuell: 4 Waitress-Threads
- Bei 9 iPads + gleichzeitigen Requests: Queue-Depth 44
- **Empfehlung: Mindestens 8-12 Threads**

---

## 7. Safety-System Gesamtbewertung

### Dreischichtige Filterung funktioniert
1. **Stage 3 Llama-Guard**: 15 UNSAFE-Detektionen, davon 3 tatsaechlich geblockt (S3/S4), 12 korrekt als "chat-specific" ignoriert (S5/S7/S8)
2. **VLM Post-Generation**: 2 von 45 Bildern geblockt (4.4%) -- paedagogisch nachvollziehbar
3. **DSGVO**: 1 Block (Keyboard-Spam-Name) -- funktioniert, aber False-Positive bei Kindereingabe

### Safety-Kategorien der Kinder-Prompts
| S-Code | Bedeutung | Anzahl | Aktion |
|--------|-----------|--------|--------|
| S3 | Sex/Nudity | 1 | BLOCKED |
| S4 | Child Safety | 2 | BLOCKED |
| S5 | Defamation | 5 | Ignoriert (chat-specific) |
| S7 | Privacy | 5 | Ignoriert (chat-specific) |
| S8 | IP/Copyright | 2 | Ignoriert (chat-specific) |

**Bewertung**: Die Kinder testen offensichtlich Grenzen (S3/S4-Triggers), aber das System faengt das zuverlaessig ab. Die hohe S5/S7-Rate deutet auf Eingaben mit Namen/Personen hin, was bei Kindern normal ist und korrekt durchgelassen wird.

---

## 8. Identifizierte Probleme & Handlungsempfehlungen

### KRITISCH
1. **ComfyUI-Timeout-Mismatch**: Backend-Timeout (300s) vs. ComfyUI-Queue-Laenge
   - 22% Timeout-Rate unter Last ist inakzeptabel
   - **Optionen**: (a) Timeout erhoehen, (b) Queue-Management im Backend (Anfrage ablehnen wenn Queue voll), (c) ComfyUI-Queue-Depth vor Submission pruefen

2. **T5 Tokenizer Race Condition** im GPU Service
   - Thread-Safety-Problem in transformers-Library
   - **Fix**: Tokenizer-Lock einfuehren ODER Requests serialisieren ODER tokenizer.clone() pro Thread

3. **GPU Service nur 4 Threads**
   - Identisches Problem wie Backend vor dem Fix
   - **Fix**: Auf 12-16 Threads erhoehen

### MITTEL
4. **`acestep_instrumental` Chunk-Datei fehlt** im Production-Deployment
   - 16 Fehlermeldungen bei Model-Availability-Checks
   - Nicht nutzungskritisch (Config nicht verwendet), aber verunreinigt Logs

5. **SD3.5 VRAM-Schaetzung falsch**: 28.3 GB real vs. 20 GB konfiguriert
   - Koennte bei Systemen mit weniger VRAM zu OOM fuehren

### NIEDRIG
6. **Llama-Guard Bare S-Code Format**: 13 Warnungen
   - Wird korrekt behandelt, aber deutet auf Llama-Guard-Version/Konfigurationsproblem
   - Kosmetisch -- Warnungen koennten auf DEBUG-Level heruntergestuft werden

7. **DSGVO False-Positive bei Keyboard-Spam**: "Kmjhjjjnnjjjjjjjjjjjjjjijkhhbn Gnghcghgjgg"
   - LLM-Verify bestaetigt das faelschlicherweise als Name
   - Edge-Case: Kinder haemmern auf Tastatur

---

## 9. Gesamtfazit

### Was funktioniert hervorragend
- **Waitress 24-Thread Upgrade**: Vollstaendig erfolgreich, null Thread-Starvation
- **Safety-System**: Dreischichtige Filterung (Llama-Guard + VLM + DSGVO) arbeitet zuverlaessig im Kids-Modus
- **ComfyUI**: 191/191 Generierungen erfolgreich, null Crashes, null OOM
- **HeartMuLa Musik**: 5/5 Generierungen fehlerfrei
- **Iterative Nutzung**: Kinder nutzen img2img Ketten -- das System unterstuetzt diesen Workflow

### Was verbessert werden muss
- **ComfyUI-Queue-Management**: Der Hauptgrund fuer die 22% Fehlerrate
- **GPU Service Threading**: Identisches Thread-Starvation-Risiko wie das bereits geloeste Backend-Problem
- **T5 Tokenizer-Lock**: Race Condition unter Last

### Workshop-Insight
Die Kinder haben in nur 31 Minuten 58 Generierungsanfragen gestellt (~2/Min). Das ist ein realistischer Lasttest mit 4 aktiven Geraeten. Bei voller Auslastung aller 9 iPads waeren ~4-5 Req/Min zu erwarten -- die ComfyUI-Queue muss das verkraften koennen.
