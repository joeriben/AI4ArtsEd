# ARCHITECTURE PART 33 — Compare Hub

## Overview

The Compare Hub (`/compare`) provides three comparison modes for investigating how AI systems produce different outputs from controlled variations. Each mode varies exactly one dimension while keeping everything else constant.

## Three Comparison Modes

### 1. Language Comparison
**Varies**: Input language (columns) and, since 2026-09-21, image model (rows) | **Constant**: Prompt, seed
- User enters a prompt in any language and ticks the image models (SD 3.5 Large, SD 3.5 Large Turbo, Flux 2, Gemini 3 Pro; default SD 3.5 Large + Flux 2)
- Prompt is translated to all selected languages via `/api/schema/pipeline/translate` (LLM auto-detects source)
- Every ticked model generates one image per language on the run's seed, one row per model, on the Latent Lab series grid (`views/compare/language_comparison.vue`); Gemini's interface takes no seed
- Reveals the language bias of each model's text parts — CLIP/T5 in SD 3.5, a vision-language model in Flux 2 — whose visual culture the model absorbed

### 2. Model Comparison
**Varies**: Image generation model | **Constant**: Prompt, seed
- Two preset lineups:
  - **Current Top Models**: SD 3.5 Large (diffusers), Flux 2 (ComfyUI), Gemini 3 Pro (cloud)
  - **SD History**: SD 1.5 (2022), SDXL (2023), SD 3.5 Large (2024)
- Same prompt + seed across all models
- Note: Same seed ≠ same image cross-model (different latent spaces). Seed ensures reproducibility within a model.

### 3. Temperature Comparison
Removed: the tab on 2026-08-23, the view file `views/compare/temperature_comparison.vue` on 2026-10-10. The hub's tabs since are Language, Model, Cultural Bias, VLM Analysis and Voices (section 4).

## 4. Voices — **V 1.03**, 2026-09-19 (V 1.02 2026-09-18; V 1.01 2026-08-27; V 1.0 2026-08-26; added 2026-08-14/15)

Not a fourth "comparison mode" in the sense of the three above: nothing is
generated twice and compared. Four speech synthesisers stand side by side and
are given the same text, and what is being compared is **what each of them can
be asked for**. The columns are in ascending order of that.

| Column | What it is | What can be asked |
|---|---|---|
| eSpeak NG 1.51.1 (1995) | Formant synthesis, from `speak` (1995). Nothing trained, nobody recorded. A system package, CPU, all ten platform languages | A variant (twelve settings of the same machinery), speed, pitch — none of them a feeling |
| Piper 1.6.0 (2022) | VITS (2021), non-autoregressive (one pass per sentence), ONNX. One file per voice, trained on one recorded dataset; most of the installed files fine-tuned from an English base voice (MODEL_CARD). A separate process in its own environment (`~/ai/piper`), CPU, all ten platform languages from recordings, so it never takes the English fallback | Which installed file speaks, in three steps (V 1.03): the language, then the voices of that language, then, in the German corpus file, which of its 236 speakers (`emotion`, the platform's drop-down, each entry with what the corpus documents; what the two are is said in the note box). Under the choice stands one line: who was recorded, where the dataset says so. Any of the fifteen files can be named for any sentence; what one of another language makes of it is its phonemiser's business, heard or refused with the cause. The API also takes `length_scale` and `noise_w`; the column sends neither. The speaker heard is the recorded one; pitch and rhythm are sampled anew at every run |
| Supertonic 3 (2026) | 99M parameters, non-autoregressive, ONNX. Input longer than 300 characters is cut at sentence boundaries before synthesis, each passage spoken on its own and joined with 0.3 s of silence (`chunk_text`, supertonic 1.3.1 `utils.py`), so nothing carries across a passage boundary — which the fairy tales, 1418 to 2986 characters, reach every time | Ten voices, linearly mixable; the platform's own voice is always a mixture and never one of them |
| VoxCPM2 (2026) | 2B, tokenizer-free, diffusion-autoregressive: each piece is denoised into place and conditions how the one after it is read, across sentence boundaries too | Nothing structural. The voice is described **in words inside the utterance**, `(description)text`, and the model decides which part is the instruction |

**What V 1.0 is** (2026-08-26). The surface is a grid that fills the work area:
one column per machine plus the asking column on the left, no page scroll at
1440x900, 1194x834 or stacked below 900 px of work area (a container query, not
a media query — the instrument rail is 240 px and can be folded away).

- **Every recording stays in the column of the machine that made it.** There is
  no shared list underneath: what is to be compared is what a machine did with
  the same sentence, and a list would sort that back together.
- **One tone per machine**, on the three places that belong to it alone: the
  edge of the column, the name, and the trigger. The tones are the platform's,
  the trigger is `FlowRunButton` with a filled body — the outline form
  disappeared against the column.
- **The year stands behind every name** (1995 / 2022 / 2026 / 2026). eSpeak NG carries
  the year of its origin, not of its version: `speak` for Acorn/RISC OS, 1995.
- **The descriptions stand once, at the foot of the asking column**, in
  the wording supplied for them; the long form is in the documentation (Compare guide,
  section Voices) and in Help, which reads
  `devserver/my_app/knowledge/platform_items.json`. Before 2026-08-26 Help knew
  nothing of the three systems: the build step harvests one activation sentence
  for Compare pages, and Voices has none. It now reads the page's own block.
- **The asking column lays itself out** and takes none of the machines' rows.
  It shared them until 2026-08-26, and then the field's own drag handle moved
  all four columns at once. The field takes the room the column has left and
  grows into it; the note box hangs at the foot with the height of its text.

**What V 1.01 changed** (2026-08-27). No new feature; the second decimal
marks that. Three corrections, all of them to what was already there.

- **A long text is spoken in sense units, each one the continuation of the one
  before.** VoxCPM2 reads a long text faster than a short one and keeps getting
  faster, on the Bremen tale by two to three times. It is
  the model's own behaviour, reported and open at OpenBMB (VoxCPM#297), and the
  makers prescribe splitting and joining for long-form. The context has no part
  in it: at 6.25 steps per second and 160 ms of audio per step, that tale's 978
  text tokens leave room for nineteen minutes against a recording of eighty-five
  seconds. `voxcpm_service/server.py` now gathers whole sentences to about 150
  tokens (ceiling 220) and hands each segment the previous one as its anchor.
  **A piece still conditions how the one after it is read, across sentence
  boundaries and across a cut** — that is what the anchor carries, and the line
  in the machine table above stands unchanged. What one single pass had on top
  of that is the whole text present while the first sound is made; a segment has
  its own text and the anchor. A cut inside a sentence happens only where one
  sentence is over the ceiling by itself, and then at its own clause
  punctuation.
- **The spoken text under a recording stands on one line, cut with an ellipsis.**
  A fairy tale ran to dozens of lines under every player and pushed them apart.
  The line is there to tell two recordings apart, and the first words do that;
  the whole text stands in the field above. `.vc-sample` needed `min-width: 0`
  for it: a grid item takes the width of its widest content, and with the line
  set to `nowrap` the box grew to 15085 px, which clipped the text instead of
  ending it and gave the list a sideways scrollbar.
- **The word under a running trigger is gone.** It said that the machine was
  working while the trigger beside it already said so.

**What V 1.02 added** (2026-09-18). Piper is back, as the second machine.
It stood first until 2026-08-14
and was wrong THERE: begun 2022 over VITS (2021) for the Rhasspy project, the
installed 1.6.0 from the Home Assistant authors (OHF-Voice/piper1-gpl, 2025),
it had been chosen as the historical reference, which eSpeak NG then became.
Read by what can be asked of it, it stands between eSpeak NG and Supertonic
3: more than twelve settings of one machinery, less than a mixture of voices.
The years give the same order. The three columns already on the surface are
unchanged; the note at the foot of the asking column carries a second
paragraph and renumbers the two after it, and the page's address
(`compare.address.voice.*`) counts four systems. Backend, chunk and output
config are the ones removed on 2026-08-14, restored under the current rules
(all five safety levels in the chunk, no seed — `RandomNormalLike` sits in the
exported graph —, declared as a subprocess starter in
`test_gpu_admission_coverage.py`, and never the platform's voice:
`is_platform_voice: false`, reachable only by `system: "piper"`). What the
datasets say about who was recorded moved from a map in the backend into the
copy (`compare.voice.piper.recordings.<dataset>`, en.ts), keyed by the
dataset the voice file names in its sidecar, so the line is translated like
every other line of the column. A named voice of another language than the
text's is refused (`resolve_voice`), a language outside the ten is refused
without the English rendering being fetched (`english_fallback: False` in
the chunk, read by `_spoken_language`), and `/api/speech/status` reports
under `default_voices` which file speaks per language when none is named.

**What V 1.03 changed** (2026-09-18/19). Every language has a chip, the
interface's language is preselected, the 236 speakers trained into the corpus
file are reachable, and the choice is laid out the way the products that use
Piper lay it out. The Piper column chooses in the three steps of Piper's own sample
page (rhasspy/piper-samples: Language, Voice, Quality, Speaker) and of Home
Assistant's Wyoming integration (the voices of a language; the speaker as an
option): the language as chips carrying the code, the name on hover, the
interface's language lit where a file exists for it; then the voices of that
language, one chip per row, named by the dataset the sidecar names with the
region beside it and the file and quality level on hover; then, in the German
corpus file alone, one of its 236 speakers in the platform's drop-down
(`.vc-select`, registry: Klapplisten), sent under `emotion`. The grouped list
of all fifteen files in a 12-rem scroll block that stood here for a few hours
on the 18th is gone with it. A file of another language is spoken, not
refused: `resolve_voice` takes any installed name, `synthesize` looks the
text's language up only for the default, and the chunk refuses a language
outside the ten with or without a named voice and a platform language without
a file only when none is named. What the file then does was measured with
`PiperVoice.phonemize` of the installed piper-tts 1.6.0 and stands in the
backend's module docstring: fourteen files phonemise with eSpeak NG set to
the file's language, which applies that language's rules to the words it
reads in it, switches language for others (a Latin-script sentence under the
Arabic, Bulgarian, Korean or Ukrainian file goes to English) or spells a word
in a script it has no rules for; the file speaks the phonemes its id map has.
The Hebrew file (`phoneme_type: "hebrew"`) phonemises with Piper's own Hebrew
phonemiser, which keeps Hebrew letters only, and `synthesize` refuses it a
text of which fewer than half the letters are Hebrew, with the cause rather
than voiced spaces. A line
under the choice said this per file for some hours on the 19th (`foreign` /
`foreignHebrew`) and is gone, see below.

**What the speaker entries say, and where it comes from.** The corpus file
names its speakers by their Multilingual LibriSpeech number and its sidecar
says nothing else about them; a list of 236 bare numbers gives nothing to
choose by. The corpus documents them: its `metainfo.txt` records, one row
per chapter, each speaker's gender and the minutes recorded.
`download_piper.sh` fetches that file to `<stem>.metainfo.txt` beside the
model, `PiperVoiceModel._read_speaker_info` sums the minutes per speaker, and
`describe()` reports both under `speaker_info`, so an entry reads „2422 (0) ·
male · 601 h" - the speaker as the sample page names it (name and index),
then what the corpus records. Without the file the entries carry number and
index alone. The corpus's terms forbid identifying the speakers ("You agree to not
attempt to determine the identity of speakers in this dataset"), so the
number is shown and nothing is resolved from it. `describe()` also carries
`region` and `quality` from the sidecar, which the voice chips show.

**What stands under the choice** (2026-09-19). The stack under the Piper
choice was too long for the column, the speaker information belongs in the
note box, and the Supertonic column did not say that voices can be mixed.
A stack of notes stood under the Piper choice: the
rubric "Selected model" with the file's name (`selected`), its export
version, sample rate and quality level (`fileMeta`), its speaker count
(`speakers`), what the drop-down's entries carry (`speakerInfoNote`), who
was recorded (`recordings.<dataset>`), and what a file of another language
does with the sentence (`foreign` / `foreignHebrew`). One remains: who was
recorded, where the dataset says so, without the years of the recordings. It
is the line the page's own purpose names (`compare.address.voice.purpose`:
"under the chosen file stands who was recorded, where the dataset says so").
The file's name stands on the chip's hover card and on every card of a run;
the speaker count is the drop-down; what its entries carry is said in the
note box at the foot of the asking column, in three sentences at the end of
the Piper paragraph of the note text (`about.body`, after its bracket); export
version, sample rate and quality level said nothing about what can be asked
of the machine, and the quality level stays on the chip's hover card; what a
file of another language does is heard, or refused with the cause in the
column. The Supertonic column says above its chips, as an imperative with
its consequence, that the platform mixes several chosen voices in equal
shares (`supertonic.mixNote`; `weightsFor` sends 1/n per chosen voice, and
`supertonic_backend.py` sums the style vectors with those weights), which
the note box said and the column did not. The
eSpeak column's block (`selected`, the variant, `engineMeta` with version and
sample rate) is of 2026-08-14 and stands as it was.

**The Clear button is gone** (2026-09-19). The other instruments keep
every run, and a button that discards a lesson's recordings on one wrong
click is a special case none of them has. It stood since 49ecf34b
(2026-08-09) over the shared results list (`clearSamples`, everything at
once) and since 0d03fbd4 (2026-08-26) in each column head (`clearSystem`),
an underlined word that dropped the column's recordings and its last card.
The head carries the name, the year and the pitch of the last run, and every
recording stays, as the V 1.0 rule above says.

Sighted at 1210×834 with the rail open: the settings row at 388 px for all
four columns (the Supertonic and VoxCPM2 bodies scroll inside it);
`de_DE-mls-medium / 2422` speaks the English sentence (143 Hz); the
interface switched to English lights EN and `cori`, and under `pavoque` the
one line reads „Stefan Röttig, trained actor and baritone, recorded for
PAVOQUE, a project of the research institute DFKI"; no Clear in any head.
The nine other languages carry the strings of the morning's translation
(c19eaf2b) until the next run: the German `pavoque` line still ends
„veröffentlicht 2013", and `mixNote` and the three sentences in the note
box read in English there.

**Key files.** `views/compare/voice_comparison.vue`;
`my_app/routes/speech_routes.py` (`SPEECH_SYSTEMS`, one chunk per system);
`services/espeak_backend.py`, `services/piper_backend.py`,
`services/supertonic_backend.py`, `services/voxcpm_backend.py`;
`voxcpm_service/server.py` (own worker, own GPU lock, port 17805). All four
are finished through the same `speech_audio.to_wav` — a comparison between
differently normalised audio would be a comparison of the normalisation.
`download_piper.sh` fetches Piper and its voices into `~/ai/piper`;
`docs/installation/MODELS_REQUIRED.md` tabulates the installed voices with
dataset and licence; `docs/SPRACHSYNTHESE_PIPER_KONFIGURATION.md` (2026-08-08)
describes the German catalogue and Piper's parameters.

**The texts.** `src/data/voiceTestSentences.ts` holds built sentences on two
axes (neutral, emotional) plus one long text per language. The long texts are
fairy tales, one per language, each from its own tradition and its own public
domain — **never a translation**, because prosody over twenty lines is a
property of a language, not of a meaning. Korean is the single exception, is a
translation, and says so on its source line; the reason is in the file.

---

## Safety

All modes go through the platform's safety system:
- **Stage 3**: Llama Guard S1-S13 check runs for ALL generation requests (even with `skip_stage3_translation=true`, safety check still executes — only translation is skipped)
- **Stage 4 VLM**: Post-generation image check for kids/youth safety levels
- Older models (SD 1.5, SDXL) have no built-in safety, but platform safety wraps around them

## Trashy (ComparisonChat) — Mode-Aware

`ComparisonChat.vue` accepts a `compare-type` prop (`'language'` | `'model'`), forwarded via `context.compare_type` in the chat request.

Backend routing in `build_system_prompt()`:
- `compare_type == 'model'` → `MODEL_COMPARISON_SYSTEM_PROMPT_TEMPLATE` (architecture evolution, parameter counts, training data differences)
- Default → `COMPARISON_SYSTEM_PROMPT_TEMPLATE` (CLIP/T5 encoding bias, language representation gaps)
- `temperature_compare_mode` has its own path (minimal system prompt, no comparison context)

## Pictures on the surface — the agent looks, and only when asked (2026-08-23)

The `Image Understanding` tab is gone: upload a picture, have four Qwen-VL sizes read
it side by side. Route, view, system prompt and model picker were removed with it. Its
descriptions came back empty because of the WORDING of the request, not the model —
measured against `qwen3-vl:4b`: "… Focus on subject, composition, colors, and style."
returned 0 characters in 3 of 3 tries, "Describe this image in 2-3 sentences." returned
327. The reading moved to the agent that already stands beside the pictures.

Three information layers, kept apart by their TRANSPORT — the point is not to overload
Help:

| Layer | Example | Transport |
|-------|---------|-----------|
| general platform knowledge | the library, other places | PULL — the `lookup_*` tools |
| page-specific | the page's own catalogue entry, its address | PUSH — a few lines in the system prompt |
| situational media | the pictures made HERE, just now | the DIRECTORY is pushed, the CONTENT is pulled |

- The surface sends `surface_media` (`[{runId, label}]`, capped at `SURFACE_MEDIA_MAX`
  = 12) and `may_open_media`. `_build_surface_media_context()` puts the LIST into the
  system prompt — model or language per picture — plus the sentence that none of them
  has been looked at, and that nothing is said about a picture until `view_run` has
  returned one.
- Looking is a separate step: `view_run(run_id)`, Resona's existing tool with its
  anti-fabrication rule and `describe_image_neutral` behind it. It reaches the compare
  agent through the `surface` scope in `tool_registry.py` — deliberately NOT through
  `default`, which would break the universal/Resona scope invariant guarded by
  `test_resona_memory.py::test_scope_overlap_is_exactly_the_granted_lookups`.
- Only a turn a PERSON started may open pictures: `sendMessage` passes
  `mayOpenMedia = true`; the greeting and the comment after a run pass `false`, and
  their prompts say what could be looked at instead of claiming what is in the frames.
  The silent describe loop after every generation is gone — it cost three VLM calls per
  run and returned nothing.
- The magnifier on a `MediaOutputBox` reaches the surface agent, not Help: the surface
  claims its runs (`analysisEventStore.ownRuns`), `ChatOverlay` steps aside for runs a
  surface has claimed (`isOwnedBySurface`), and the surface answers with
  `compare.lookAtThis`. See PART 35.

## Key Files

| File | Purpose |
|------|---------|
| `views/compare_hub.vue` | Tab container (Language → Model → Cultural Bias → VLM Analysis → Voices) |
| `views/compare/language_comparison.vue` | Language comparison with chip selector |
| `views/compare/model_comparison.vue` | Model comparison with preset toggle |
| `components/ComparisonChat.vue` | Trashy sidebar (shared, mode-aware via prop) |
| `chat_routes.py` | System prompts: `COMPARISON_SYSTEM_PROMPT_TEMPLATE`, `MODEL_COMPARISON_SYSTEM_PROMPT_TEMPLATE` |
| `schema_pipeline_routes.py` | `/pipeline/translate` (LLM auto-detect), `/pipeline/generation` (SSE streaming) |
| `schemas/configs/output/sd15.json` | SD 1.5 output config (ComfyUI, 512px) |
| `schemas/configs/output/sdxl.json` | SDXL output config (ComfyUI, 1024px) |

## Translation Endpoint

`/api/schema/pipeline/translate` is a generic translator:
- Receives `text` + `target_language`
- LLM auto-detects source language
- Handles any source→target pair including same-language (returns unchanged)
- `enable_thinking=False` prevents reasoning leak in translation output
- No hardcoded source language assumptions
