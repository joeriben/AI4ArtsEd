# Architektur-Verletzung: Proxy-Chunk-Pattern

**Datum:** 2026-02-02
**Behoben:** 2026-03-02 (Session 230)
**Status:** RESOLVED — Proxy-Chunks eliminiert, Pipelines nutzen `{{OUTPUT_CHUNK}}` direkt
**Betrifft:** `single_text_media_generation` Pipeline + `output_image.json` Proxy-Chunk

### Resolution Summary
- Pipelines umgestellt: `"chunks": ["output_image"]` → `"chunks": ["{{OUTPUT_CHUNK}}"]`
- Proxy-Chunks gelöscht: `output_image.json`, `output_legacy.json`
- Dead Code aus `backend_router.py` entfernt: ~492 Zeilen (2777 → 2285)
- Entfernte Methoden: `_process_heartmula_chunk`, `_process_triton_chunk`, `_process_ollama_request`, `_process_direct_request`, `_inject_legacy_prompt`, `_process_comfyui_legacy`
- Verwaiste Chunks gelöscht: `output_music_heartmula.json`, `output_image_sd35_large.json`, `output_image_sd35_triton.json`
- Template-Resolution via `config_loader._resolve_configs()` (Zeilen 307-323) — bereits Production-bewährt via `dual_text_media_generation`

---

## Das Problem

### 3-Ebenen-Architektur (Soll-Zustand)

| Ebene | Verantwortung |
|-------|---------------|
| **Pipeline** | Prozessstruktur - entscheidet welche Chunks in welcher Reihenfolge |
| **Config** | Parameter - liefert Werte für die Ausführung |
| **Chunk** | Ausführung - führt eine Einzelaufgabe aus, entscheidet NICHT |

### Ist-Zustand (Verletzung)

```
Pipeline: single_text_media_generation.json
    └── chunks: ["output_image"]  ← Proxy-Chunk, nicht konkreter Chunk

Config: sd35_large.json
    └── OUTPUT_CHUNK: "output_image_sd35_large"  ← Config entscheidet!

Proxy-Chunk: output_image.json
    └── output_chunk: "{{OUTPUT_CHUNK}}"  ← Routet zu anderem Chunk

Backend Router: backend_router.py:408
    └── Lädt den konkreten Chunk basierend auf Parameter
```

**Die Entscheidung welcher Chunk ausgeführt wird, kommt aus der Config statt aus der Pipeline.**

---

## Betroffene Dateien

### Pipeline
- `/devserver/schemas/pipelines/single_text_media_generation.json`

### Proxy-Chunks
- `/devserver/schemas/chunks/output_image.json`
- `/devserver/schemas/chunks/output_legacy.json`

### Configs die das Pattern nutzen (17 Stück)
- `sd35_large`, `flux2`, `flux2_fp8`, `flux2_img2img`
- `qwen`, `qwen_2511_multi`, `qwen_img2img`
- `gemini_3_pro_image`, `gpt_image_1`
- `stableaudio_open`
- `acestep_instrumental`, `acenet_t2instrumental`
- `ltx_video`, `wan22_video`, `wan22_i2v_video`
- `p5js_code`, `tonejs_code`

### Routing-Logik
- `/devserver/schemas/engine/backend_router.py` (Zeile 408-441)
- `/devserver/schemas/engine/chunk_builder.py` (Zeile 244-270)

---

## Warum das problematisch ist

1. **Chunks sollten nicht routen** - Ein Chunk führt aus, er entscheidet nicht welcher andere Chunk aufgerufen wird.

2. **Versteckte Indirektion** - Die Entscheidungslogik ist über mehrere Ebenen verstreut und schwer nachvollziehbar.

3. **Ungenutzte config_mappings** - Die Pipeline definiert:
   ```json
   "config_mappings": {
     "output_image": "{{MEDIA_TYPE}}_generation.{{MODEL_CONFIG}}"
   }
   ```
   Diese werden **nie genutzt**. Die tatsächliche Routing-Logik läuft über `OUTPUT_CHUNK`.

4. **Verwirrung bei Entwicklung** - Neue Backends (wie HeartMuLa) wurden falsch implementiert, weil das Pattern unklar ist.

---

## Zweites Problem: Output-Chunks ohne Ausführungslogik

### JSON-Chunks als Metadaten-Container (Architektur-Verletzung)

**Entdeckt:** 2026-02-02 bei HeartMuLa- und SD3.5-Analyse

**Das Problem:** Output-Chunks wurden im Lauf der Entwicklung von **Ausführungseinheiten** zu **Metadaten-Containern** degradiert.

#### Beispiel: SD3.5 Diffusers-Chunk

**Aktueller Zustand:**
```json
// devserver/schemas/chunks/output_image_sd35_large.json
{
  "name": "output_image_sd35_large",
  "type": "output_chunk",
  "backend_type": "diffusers",
  "diffusers_config": {
    "model_id": "stabilityai/stable-diffusion-3.5-large",
    "pipeline_class": "StableDiffusion3Pipeline",
    "torch_dtype": "float16"
  },
  "input_mappings": {...},
  "output_mapping": {...}
}
```

**Wo ist der ausführbare Code?** → Im Router!

```python
// devserver/schemas/engine/backend_router.py (Zeile ~1700+)
async def _process_diffusers_chunk(self, chunk_name, prompt, parameters, chunk):
    # 200+ Zeilen Diffusers-spezifische Ausführungslogik
    # Lädt Model, konfiguriert Pipeline, generiert Bild, speichert
    ...
```

**Warum ist das falsch?**

1. **Zentrale Datei überladen** - `backend_router.py` hat Backend-spezifische Logik für:
   - Diffusers (SD3.5, Flux, etc.)
   - HeartMuLa
   - ComfyUI
   - API-Backends
   - ... jedes neue Backend braucht neue Router-Funktion

2. **Chunk ist nur Container** - Enthält keine Ausführungslogik, nur Metadaten

3. **Nicht maintainbar** - Für jedes neue Backend muss zentraler Code geändert werden

4. **Verstößt gegen 3-Ebenen-Prinzip** - Chunk sollte ausführen, nicht nur beschreiben

#### Beispiel: HeartMuLa (gleiches Problem)

```json
// devserver/schemas/chunks/output_music_heartmula.json
{
  "name": "output_music_heartmula",
  "backend_type": "heartmula",
  "input_mappings": {...}
  // Keine Ausführungslogik!
}
```

Ausführungslogik wieder im Router:
```python
async def _process_heartmula_chunk(...):
    # HeartMuLa-spezifische Logik im Router
```

---

## Korrektes Pattern: Python-Chunks

**WICHTIG:** Stage4-JSON-Chunks sind **DEPRECATED**. Nur verwenden wenn dokumentierter guter Grund existiert.

### Standard (Python-Based Chunks)

Output-Chunks sollten **Python-Dateien** sein, die die komplette Ausführungslogik enthalten:

```python
# devserver/schemas/chunks/output_image_sd35_large.py

"""
Output Chunk: SD3.5 Large Image Generation

Generates images using Stable Diffusion 3.5 Large via Diffusers backend.
"""

async def execute(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 28,
    cfg_scale: float = 3.5,
    seed: Optional[int] = None,
    **kwargs
) -> bytes:
    """
    Execute SD3.5 Large image generation.

    Args:
        prompt: Main prompt
        negative_prompt: Negative prompt
        width: Image width
        height: Image height
        steps: Inference steps
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (optional)

    Returns:
        Image bytes (PNG format)
    """
    from my_app.services.diffusers_backend import get_diffusers_backend

    backend = get_diffusers_backend()
    if not backend.is_available():
        raise Exception("Diffusers backend not available")

    return await backend.generate_image(
        model_id="stabilityai/stable-diffusion-3.5-large",
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=cfg_scale,
        seed=seed
    )
```

**Vorteile:**

1. **Self-Contained** - Chunk enthält ALLE Ausführungslogik
2. **Type-Safe** - Funktion deklariert Inputs/Outputs explizit
3. **IDE-Support** - Autocomplete, Type-Checking funktioniert
4. **Kein Router-Code** - Backend-Logik bleibt wo sie hingehört
5. **Einfach zu testen** - Chunk kann direkt importiert und getestet werden

### Legacy (JSON-Based Chunks) - DEPRECATED

**Status:** Wird ausgemustert. Nur verwenden mit dokumentierter Begründung.

**Einziger valider Grund:** Pure ComfyUI-Workflow-Passthrough ohne jegliche Python-Logik.

**Beispiel (weiterhin akzeptabel):**
```json
// Reiner ComfyUI-Workflow ohne Python-Logik dazwischen
{
  "name": "output_video_ltx",
  "workflow": {
    // 20+ Nodes, komplettes ComfyUI API JSON
  }
}
```

**Warum akzeptabel:** Der Workflow SELBST ist der ausführbare Code. ComfyUI führt ihn aus, DevServer leitet nur weiter.

**Nicht akzeptabel:** JSON-Chunks die auf Python-Backends verweisen:
- ❌ Diffusers-Chunks (Python-Backend → `.py` Chunk)
- ❌ HeartMuLa-Chunks (Python-Backend → `.py` Chunk)
- ❌ API-Chunks (Python-Request-Logik → `.py` Chunk)

---

## Betroffene Backends (Refactoring nötig)

### High Priority (Python-Backends)
- **Diffusers** (SD3.5, Flux, etc.) - ~200 Zeilen Code im Router
- **HeartMuLa** - Bereits als `.py` implementiert (Referenz)
- **API-Backends** (OpenAI, OpenRouter) - Request-Logik im Router

### Medium Priority (ComfyUI-Passthrough)
- **ComfyUI-Chunks** - Können als JSON bleiben (Workflow = Code)
- Aber: Input/Output-Mapping-Logik könnte zu `.py` migriert werden

---

## Korrektes Pattern (Soll-Zustand)

Die Pipeline sollte direkt entscheiden welcher Chunk ausgeführt wird:

### Option A: Dynamischer Chunk-Name in Pipeline

```json
{
  "name": "single_text_media_generation",
  "chunks": ["{{OUTPUT_CHUNK}}"],
  "meta": {
    "note": "OUTPUT_CHUNK wird aus Config gelesen"
  }
}
```

Config liefert den Chunk-Namen, Pipeline verwendet ihn direkt - kein Proxy nötig.

### Option B: Pipeline mit expliziter Chunk-Auswahl

```json
{
  "name": "image_generation_sd35",
  "chunks": ["output_image_sd35_large"]
}
```

Separate Pipeline pro Backend - am klarsten, aber mehr Pipelines.

### Option C: Pipeline-Logik für Chunk-Auswahl

Die Pipeline enthält Logik die basierend auf Config-Parametern den richtigen Chunk auswählt. Dies erfordert Änderungen am Pipeline-Executor.

---

## Empfehlung

**Option A** ist der beste Kompromiss:
- Minimale Änderung am bestehenden System
- Config behält `OUTPUT_CHUNK` Parameter
- Pipeline verwendet den Wert direkt in `chunks` Array
- Kein Proxy-Chunk nötig
- Klare Verantwortlichkeiten

---

## Referenz-Implementierung

Die `dual_text_media_generation` Pipeline (für HeartMuLa/AceStep) wird als korrektes Beispiel implementiert - ohne Proxy-Chunk-Pattern.

Siehe: Session-Dokumentation für HeartMuLa-Integration.

---

## Historie

- **Ursprung:** Vermutlich als "flexible" Lösung gedacht um eine Pipeline für mehrere Backends zu nutzen
- **Problem:** Die Flexibilität wurde an der falschen Stelle (Chunk statt Pipeline) implementiert
- **Entdeckt:** 2026-02-02 bei HeartMuLa-Integration
