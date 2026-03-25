# DevServer Architecture

**Part 35: Trashy Image Analysis — Vision-basierte Bildreflexion**

---

## Ueberblick

Trashy (der paedagogische Chat-Assistent) kann generierte Bilder direkt sehen und prozessorientiert kommentieren. Das Feature war seit Session ~100 geplant und wurde in Session 289 implementiert.

## Architektur

```
User klickt Analyse-Icon (MediaOutputBox)
          |
          v
analysisEventStore.requestReflection(runId)
          |
          v
ChatOverlay (Watcher)
  - expandiert Trashy
  - baut safety-level-adaptierten Prompt (kids/youth/expert)
  - liest User-Input aus pageContextStore
          |
          v
POST /api/chat { message: prompt, image_path: runId }
          |
          v
Backend: vision_support.py
  - prepare_image_b64(run_id) → base64
  - is_vision_capable(model) → true/false
          |
     +---------+----------+
     |                    |
  Vision-faehig      Text-only Modell
     |                    |
  _inject_image_       describe_image_for_fallback()
  into_messages()      → lokaler VLM beschreibt
  (openai/anthropic/   → Text in Message injiziert
   ollama Format)      → Bild bleibt lokal
     |                    |
     v                    v
  call_chat_helper(image_b64=...)
          |
          v
ChatOverlay zeigt Antwort in Trashy
```

## Komponenten

### Frontend

**MediaOutputBox.vue** — Zentrale Komponente. Analyse-Button dispatcht `runId` an analysisEventStore. Kein Emit, keine per-View Logik.

**ChatOverlay.vue** — Faengt analysisEvent, expandiert, ruft `/api/chat` mit `image_path`. Baut Prompt via:
- `pageContextStore.pageContent.inputText` (User-Eingabe)
- `uiModeStore.mode` (kids/youth/expert)

**analysisEvent.ts** — Pinia Store, gleiche Architektur wie safetyEventStore. Felder: `runId` (required), `analysisText`, `userPrompt`, `viewType` (optional, fuer Logging).

### Backend

**vision_support.py** — Drei Funktionen:
- `prepare_image_b64(image_source?, run_id?)`: Resolved run_id → Bild → resize (max 768px) → JPEG q80 → base64
- `is_vision_capable(model_string)`: Cloud = True, IONOS = False, Local = Namens-Heuristik (vl, vision, llava, pixtral)
- `describe_image_for_fallback(image_b64)`: Lokaler VLM (IMAGE_ANALYSIS_MODEL) beschreibt Bild als Text

**chat_routes.py** — `/api/chat` Endpoint akzeptiert optionales `image_path`:
- `_inject_image_into_messages(messages, image_b64, format)`: Provider-spezifisch (openai, anthropic, ollama)
- `call_chat_helper(..., image_b64=)`: Alle 6 Provider-Funktionen akzeptieren `image_b64`
- Vision-Check + Fallback vor dem Tool-Call-Loop
- Bild nur im ersten Loop-Durchlauf (danach `None`)

## Safety-Level-Prompts

| Mode | Laenge | Fokus |
|------|--------|-------|
| kids | 3-4 Saetze | Was siehst du? Passt es zum Input? Was als naechstes? |
| youth | 5-8 Saetze | Prompt-Bild-Beziehung, unerwartete Qualitaeten, kritisch denken |
| expert | 6-10 Saetze | Prompt-Chain-Analyse, Critical Reading, Bias, Aesthetic Defaults |

Alle Prompts enthalten eine strikte Anti-Preamble-Regel (Sonnet neigt zu "Okay let me..." als Content).

## Datenschutz-Design

- **Generierte Bilder**: Duerfen an externe Provider (Mammouth/Anthropic, DSGVO-konform)
- **Hochgeladene Bilder**: Bleiben IMMER lokal (VLM Safety Check, nie an Cloud)
- **Fallback-Pfad**: Wenn Chat-Modell nicht vision-faehig → lokaler VLM beschreibt → nur Text geht an Cloud

## Resizable Chat Window

Trashy-Fenster ist an allen 4 Ecken draggable/resizable. Min 300x350, Max 700x900. Groesse persistiert in localStorage (`trashy-size`).
