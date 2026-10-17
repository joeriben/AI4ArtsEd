# Architecture Part 32: Dialogic AI Persona

## 1. Concept

The AI Persona page (`/persona`) inverts the standard generation flow. Instead of "user writes prompt, machine generates", the machine is an aesthetically opinionated conversation partner that decides autonomously:
- **Whether** to generate (it may refuse)
- **What** to generate (it chooses the prompt)
- **Which medium** to generate (image, audio, video, 3D, code)
- **Which model** to use (it chooses the output config)

The human's role shifts from consumer to interlocutor. This is pedagogically intentional: it forces articulation, reflection, and argumentation rather than consumption.

## 2. Architecture

### 2.1 No New Endpoints

The entire page is built from existing infrastructure:
- **Chat**: `/api/chat` with `context.persona_mode = true`
- **Generation**: `/api/schema/pipeline/generation` via `useGenerationStream`
- **Favorites**: `/api/favorites` via `useFavoritesStore`

### 2.2 System Prompt Routing

```
chat_routes.py:build_system_prompt()
  ├── context.persona_mode     → AI_PERSONA_SYSTEM_PROMPT
  ├── context.workshop_planning → WORKSHOP_PLANNING_SYSTEM_PROMPT
  ├── context.comparison_mode   → COMPARISON_SYSTEM_PROMPT_TEMPLATE
  └── run_id / default          → SESSION / GENERAL prompt
```

### 2.3 Generation Trigger Flow

```
1. User sends message → /api/chat (persona_mode)
2. LLM responds with text + optional [GENERATE: config_id | prompt]
3. Frontend parses markers via regex
4. For each marker: spawnGeneration(configId, prompt)
   → useGenerationStream().executeWithStreaming()
   → new floating MediaOutputBox appears
5. Text (sans markers) is spoken by the platform voice (see PART 39)
```

### 2.4 Available Configs

The system prompt receives available configs via `draft_context`:
```
sd35_large, flux2_diffusers, gemini_3_pro_image, gpt_image_1,
stableaudio_open, heartmula_standard, p5js_code, tonejs_code,
wan22_t2v_video_fast, ltx_video, hunyuan3d_text_to_3d
```

The LLM chooses based on aesthetic intent. Not all configs work with single-prompt input (e.g. `heartmula_standard` requires dual input). The generation pipeline handles validation.

## 3. Frontend Architecture

### 3.1 Floating MediaOutputBoxes

Each generation spawns a draggable `MediaOutputBox` at an auto-calculated position.

**Reactivity pattern**: `shallowRef<MediaBox[]>` + `triggerRef`
- `shallowRef` prevents Vue from deep-unwrapping `Ref` types inside `useGenerationStream()` return values
- `triggerRef(mediaBoxes)` after in-place mutations (drag, favorite, generation complete)
- Array replacement for add/remove (`[...mediaBoxes.value, box]`, `.filter()`)

**Placement algorithm**: Grid-based, 320x340px boxes, 20px margins, viewport-clamped. First free position in left-to-right, top-to-bottom scan. Dragging overrides auto-position.

### 3.2 Marker Parsing

Two marker types:
- `[PROMPT: suggestion]` — rendered as clickable button (fills input)
- `[GENERATE: config_id | prompt text]` — stripped from display, triggers generation

### 3.3 Speech

NOT the browser's `speechSynthesis` API - that voice belongs to the operating
system and does not exist for most of the languages this platform is used in.
The reply is spoken by the platform voice over `POST /api/speech`, sentence by
sentence; see PART 39 for the model, the mixtures and the switch.

Markers are stripped before speaking. Every reply is spoken by itself here, and
the words do NOT wait for it: they stand whole as soon as the reply arrives, and
the voice runs alongside (`pace: false` on the coupling). The switch that
silences it is in the main menu, not in this page.

## 4. Persona Identity

The system prompt defines a machine that:
- Has aesthetic judgement (from training data) but no emotions
- Generates only when the conversation convinces it
- May refuse ("That does not convince me.")
- May generate unsolicited when dialogue becomes inspiring
- Chooses medium and model autonomously
- Speaks directly, without filler or pleasantries
- Pushes back on cliches
- References art, music, film from its training data

All content remains age-appropriate (9-17, educators present). Safety systems apply normally.

## 5. Files

| File | Role |
|------|------|
| `src/views/ai_persona.vue` | Page component |
| `devserver/my_app/routes/chat_routes.py` | `AI_PERSONA_SYSTEM_PROMPT` + routing |
| `src/router/index.ts` | `/persona` route |
| `src/assets/icons/volume_up_*.svg` | TTS on icon |
| `src/assets/icons/volume_off_*.svg` | TTS off icon |

---

## Motivation & Gebrauchsmuster: Resona als Begleiter (2026-07-09)

> Ausführliche Design-Entscheidung: `docs/DEVELOPMENT_DECISIONS.md` (2026-07-09).

Resona ist ein pädagogischer **Begleiter** für Werkstätten — keine Interception-Persona, kein Prompt-Optimierer, kein Assistenz-Chatbot, sondern eine dritte Persona-Rolle (`resona_mode`).

**Motivation:** Eine Werkstatt braucht keine weitere optimierende Funktion, sondern eine *Präsenz*, die den Prozess begleitet (mitdenkt, spiegelt, orientiert), ohne die Arbeit abzunehmen oder "besser" zu machen — zugleich ein Gegenüber, das die verstreuten Fähigkeiten der Plattform kennt und im Moment einbringt statt als Menü.

**Kern — der Dreiklang:** Verhältnis zu sich selbst, zu Anderen, zur Sache (alle drei konstitutiv). Haltung: *Präsenz zur Sache* — verbotene Pole sind Rigorismus (Schweigen aus Risikoscheu) und Anbiederung (Beziehungspflege). Keine Frage-Pflicht; Text zum Redigieren, kein Urteil.

**Gebrauchsmuster:**
- *Situiert:* Situationsblöcke (`context.resona_situation`, z.B. `nachklapp`) steuern Register und Beitrag.
- *Nachbereitung:* sieht über geteilte Favoriten (`view_favorite`), was entstanden ist, und hilft ordnen — ohne zu bewerten.
- *Graphen sprechen:* komponiert/vorschlägt Canvas-Workflows (`run_canvas_graph`, `canvas_graph_library`) — Vorschlag als ausführbarer Prozess.
- *Mit den Mitteln:* erzeugt im Rahmen explizit gewährter Capabilities selbst Medien, schlägt Referenzen/Interception-Modi nach und erklärt sie.

**Grenze — benannte Instrumente vs. generische Modelle:** `generate_media` erreicht ausschließlich generische Bild-/Ton-/Video-Modelle (kuratierte Liste `resona_media_configs`, `tool_registry.py`); die *benannten* Latent-Lab-Instrumente (Surrealizer, Feature Probing, Concept Algebra, Attention Cartography, Denoising Archaeology, Composable Diffusion) stehen dort bewusst NICHT. Ein benanntes Instrument wird nur über `run_canvas_graph` unter seiner eigenen `configId` angeboten (`RESONA_CANVAS_CONFIGS`, `canvas_graph_authoring.py`) — für `surrealization_diffusers` mit inline `alpha_factor` (-75..+75) und `fusion_strategy` (`legacy` | `dual_alpha`; `normalized` bewusst nicht exponiert, wird entfernt), surrealizer-only validiert und durchgereicht `canvas_executor → execute_stage4_generation_only → Chunk`. Ein generisches Modell wird nie für ein benanntes Instrument eingesetzt; die Provenienz-Karte nennt immer das Modell, das tatsächlich erzeugt hat — ein flux2-Bild unter „Surrealizer"-Banner wäre eine Provenienz-Lüge auf genau der Lehrfläche, die Provenienz-Ehrlichkeit vermitteln soll. (Regel im `RESONA_CORE_PROMPT` verankert; Befund + Entscheidung: `DEVELOPMENT_DECISIONS.md`, 2026-07-13.)

**Persona-Reichweite (Abgrenzung):** Persona trägt dieses Risiko strukturell NICHT. `_should_use_tools()` liefert für `persona_mode` `False` (`chat_routes.py`) → Persona läuft mit `tools = None` und hat keinen Zugriff auf `generate_media`/`run_canvas_graph` (alle instrument-erreichenden Tools sind `scopes=["resona"]`). Persona erzeugt nur über `[GENERATE: config_id | prompt]`-Marker aus einer generischen Config-Liste (§2.4), kennt die benannten Instrumente nicht und hat keinen Auftrag, sie anzubieten — generisch-per-Design ist korrekt, kein Fix nötig.

---

## Together — **V 1.0**, 2026-09-10 (as Resona since 2026-07-09; the path was `/workshop` until 2026-08-18)

Together is the page at `/together` (`views/resona.vue`), the accompanying
conversation for a group's work. Persona (§1–5) and Together share the chat
route and the platform voice; the tool scope separates them. Persona runs with
`tools = None` (see "Persona-Reichweite" above); Together is the only surface
that hands out the `resona` scope.

**What V 1.0 is.** One turn is a stream of events out of a single generator
(`_chat_events`, `chat_routes.py`): `/api/chat/stream` sends them, and
`/api/chat` drains the same generator and returns the `done` payload. Seven
kinds travel — `token`, `discard`, `withdraw`, `graph`, `entity`, `done`,
`error`. The work area beside the conversation carries four kinds of card:
media (`mediaBoxes`), composition (`compositionBoxes`), apparatus run
(`graphBoxes`) and entity anchor (`entityCards`). All four are `FlowCard`, the
platform's card, with the reverse under its `back` slot.

The `resona`-scoped set in `tool_registry.py` is what Resona can reach:
`lookup_reference`, `lookup_interception` and `lookup_place` (shared with the
default scope), `generate_media`, `compose_media`, `remember`, `recall`,
`lookup_shared_favorites`, `view_favorite`, `view_upload`, `view_run`,
`run_canvas_graph`, `canvas_graph_library`, `search_websites`, `read_webpage`,
`lookup_knowledge`, `read_knowledge`.

An apparatus Resona authors leaves the conversation in the Canvas's own export
format and opens there ready to run: the model roles are filled from the
configured settings, the authored question stands on the surface, the inputs of
a comparison are numbered, and a collector gathers every node that feeds nothing
further plus every generation node (`canvas_graph_authoring.py`). What the turn
worked with — an apparatus, a note, a library document, a web page — gets a
square anchor on the board, the name on the front, an excerpt and the reference
on the back (`resona_entities.py`, `ResonaEntityCard` / `ResonaEntityCardBack`).

**What V 1.0 fixed rather than offered.** The platform's own notices — a reply
that did not arrive, a reply that broke off — used to be written into the
assistant's line. That line went back as history, and the model imitated it: the
group read "The answer did not arrive. Please send it again." as the answer,
turn after turn. The notice is now a field beside the line (`notice` on
`ChatMsg`), it never enters the history, and before the request the backend
drops empty and `system` turns and merges same-role neighbours.

**Open at V 1.0.** Self-activation is not built: Together is turn-bound, with no
timer and no push (`docs/plans/resona/CAPABILITY_ROADMAP.md`, stage R3). The
named Latent Lab instruments stay out of `generate_media` and are reachable only
under their own `configId` through `run_canvas_graph` (see "Grenze" above). Runs,
favourites and uploads that Resona opens get no anchor; they stay in the evidence
ledger of the turn.

**Why the mark stands here.** The version list in
`ARCHITECTURE PART 28 - Latent-Lab.md` renders the left column of the Latent Lab
(`GROUPS` in `views/latent_lab.vue`) together with the Comparison Modes.
Together is a page of its own and has no row there.
