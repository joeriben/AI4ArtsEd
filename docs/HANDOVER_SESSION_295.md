# Handover: SD3.5 Encoding Transparency

## Ziel

Den SD3.5-Generierungsprozess als Abfolge sichtbarer Schritte darstellen — nicht als Daten-Dump, sondern als prozessuale Sequenz:

1. CLIP-L liest den Text
2. CLIP-G liest den Text
3. T5-XXL liest den Text
4. Embeddings werden erzeugt
5. Denoising startet (grosse Einblendung mit Preview)

## Was funktioniert (Backend)

Der GPU-Service-Endpoint `/api/diffusers/encode-info` wurde in Session 295 implementiert und funktionierte korrekt (verifiziert via curl). Er liefert Tokenisierung, Embedding-Normen und Encoder-Agreement. **Der Code wurde reverted**, muss also neu implementiert werden. Die Methode `encode_prompt_info()` in `diffusers_backend.py` und die Route in `diffusers_routes.py` koennen aus dem Git-Reflog (`1a13cd4`) wiederhergestellt werden.

Das DevServer SSE-Event `encoding_info` funktionierte ebenfalls (in `schema_pipeline_routes.py`, Diffusers-Polling-Block nach `stage4_start`).

## Was gescheitert ist (Frontend)

### Obstacle 1: Vue Transition mode="out-in" verschluckt schnelle Phasenwechsel

`DenoisingProgressView.vue` nutzt `<Transition name="phase-switch" mode="out-in">` mit zwei `v-if/v-else` Zweigen (Phase A: Model Card, Phase B: Denoising). Ein dritter Zweig (Phase A.5) wurde per `v-else-if` eingefuegt.

**Problem:** Bei SD3.5 mit geladenem Modell kommen `encoding_info` und `generation_progress` Events fast gleichzeitig an. Vue batcht die Reactive-Updates in einen Render-Cycle. Die `out-in` Transition geht direkt von Phase A zu Phase B — Phase A.5 wird nie gerendert.

**Workaround-Versuche (alle gescheitert):**
- Minimum Display Timer (4s `setTimeout` + `encodingHoldActive` ref): Progress-Bar wurde nur langsamer eingeblendet, Encoding-Phase nie sichtbar
- Encoding-Info innerhalb Phase A (gleiches div, kein Transition-Problem theoretisch): Nur Model Card sichtbar

### Obstacle 2: isModelLoading blockiert alles bei progress === 0

Fuer Diffusers gilt: `isModelLoading = progress === 0`. Das bedeutet Phase A (Model Card) ist IMMER sichtbar solange kein Denoising laeuft. Ein separater Encoding-Zustand kann nicht existieren, weil progress === 0 sowohl "Modell laedt" als auch "Encoding laeuft" bedeutet.

### Obstacle 3: Daten-Dump statt Prozess

Der erste Ansatz zeigte Token-Normen, Cosine-Similarity-Dots, Embedding-Dimensionen. Das ist Fachsprache, kein paedagogisches Erlebnis. Das Ziel ist: den **Prozess** sichtbar machen, nicht rohe Tensorstatistiken.

## Richtiger Ansatz (nicht implementiert)

**KEIN separates Phase A.5.** Stattdessen:

Die Encoding-Info gehoert **in Phase B** (die Denoising-View), als einfache Statuszeile die sich aktualisiert:

```
[Statuszeile aktualisiert sich sequentiell:]
CLIP-L liest deinen Text...
CLIP-G liest deinen Text...
T5-XXL liest deinen Text...
Embeddings werden erzeugt...
Denoising startet...        ← ab hier wird Preview gross eingeblendet
Step 3/25 · 12% · GPU 87W  ← normaler Denoising-Status
```

**Warum das funktioniert:**
- Kein Phasenwechsel noetig — alles innerhalb Phase B
- Kein Transition-Timing-Problem — es ist nur ein Text der sich aendert
- Die Statuszeile kann lokal im Frontend durch die Schritte animiert werden (basierend auf dem `encoding_info` Event), ohne auf separate SSE-Events fuer jeden Encoder zu warten
- Wenn `generation_progress` mit step > 0 ankommt, wechselt der Status zu "Step X/Y" und die Preview wird gross

**Technisch:**
- Phase A bleibt unveraendert (Model Card)
- Phase B (Denoising) bekommt eine Statuszeile oben die durch Encoding-Schritte animiert → dann Denoising-Steps anzeigt
- Die `encoding_info` Daten liefern die Fakten (welche Encoder, wie viele Tokens), die Animation ist Frontend-seitig
- Backend-Ansatz (SSE-Event) kann wiederverwendet werden

## Dateien

| Datei | Relevanz |
|---|---|
| `gpu_service/services/diffusers_backend.py` | `encode_prompt_info()` — Git Reflog `1a13cd4` |
| `gpu_service/routes/diffusers_routes.py` | `POST /api/diffusers/encode-info` — Git Reflog `1a13cd4` |
| `devserver/my_app/routes/schema_pipeline_routes.py` | SSE-Event `encoding_info` im Diffusers-Block — Git Reflog `1a13cd4` |
| `public/.../composables/useGenerationStream.ts` | `encodingInfo` ref + Handler |
| `public/.../components/edutainment/DenoisingProgressView.vue` | **Hier muss die Statuszeile hin** — innerhalb Phase B, NICHT als separater Zweig |
| `public/.../components/MediaOutputBox.vue` | `encodingInfo` Prop durchreichen |
| `public/.../views/image_transformation.vue` | `encodingInfo` aus Composable nutzen |

## Warnung

- Die `<Transition mode="out-in">` in DenoisingProgressView ist das Kernproblem. NICHT versuchen, einen dritten Transition-Zweig einzufuegen.
- `isModelLoading` fuer Diffusers NICHT aendern — das bricht die bestehende Model-Card-Anzeige.
- Die Encoding-Info muss innerhalb des bestehenden Phase-B-div leben, nicht als Alternative dazu.
