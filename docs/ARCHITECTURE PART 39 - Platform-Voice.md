# ARCHITECTURE PART 39 — The Platform's Voice

Status 2026-08-09, with the paragraphs dated 2026-09-18 added that day.
Everything here is built and running unless a line says
otherwise. Related: `docs/DEVELOPMENT_DECISIONS.md` (2026-08-06, 2026-08-08,
2026-08-09), `docs/SPRACHSYNTHESE_PIPER_KONFIGURATION.md` (the field study that
chose the model), PART 32 (Persona / contesting).

## 1. What it is

One voice for the whole platform, synthesized on this machine. It is
**deliberately not** the browser's `speechSynthesis` API: that voice belongs to
the operating system, differs on every machine, and on most of them does not
exist at all for the languages this platform is used in.

**The voice is mixed, never picked.** The model ships ten preset voices, five
named male and five named female, and no third category. What speaks here is
always a linear combination of them, and the combination is the statement — no
mixture is a person.

## 2. Backend

| Piece | Where |
|---|---|
| Model | Supertonic 3 (Supertone Inc., ONNX, 44.1 kHz, 31 languages, OpenRAIL-M) |
| Engine | `devserver/my_app/services/supertonic_backend.py` |
| Chunk | `devserver/schemas/chunks/output_speech_supertonic.py` |
| Availability | `devserver/my_app/services/speech_availability.py` |
| Routes | `devserver/my_app/routes/speech_routes.py` — `POST /api/speech`, `GET /api/speech/status` |
| Settings | `config.py`: `SUPERTONIC_ENABLED`, `SUPERTONIC_VOICES`, `SUPERTONIC_SPEED`, `SUPERTONIC_MIN_F0_HZ`, `SUPERTONIC_F0_REDRAWS`, `SUPERTONIC_THREADS` |

**Where it runs: on the CPU.** `onnxruntime` in this venv offers
`CPUExecutionProvider` and `AzureExecutionProvider`, no CUDA. Speech therefore
never queues behind image generation — that is another process on the GPU, and
this one does not touch the GPU. Synthesis is serialized against *other
synthesis* by `_synth_lock`.

**Speed:** a 96-character sentence yields about 6.4 s of audio and takes
0.97 s / 4.63 s / 1.01 s to synthesize on three consecutive runs — the model
alternates a fast and a slow pass for reasons inside it (same text,
byte-identical output). Synthesis is faster than playback, so the pieces of an
utterance are ready before they are needed.

**Safety gate:** `ALLOWED_SAFETY_LEVELS = ("adult", "research")` in the chunk,
which is also what enforces it. Below that, the platform is silent.

**Languages:** nine of the ten platform languages have their own voice; only
**Hebrew** has none and is spoken in English. Which ones those are comes from
`/api/speech/status`, never from a list in frontend code. Russian is never a
substitute for Ukrainian.

## 3. The mixtures

Five, chosen by listening and fixed in `config.SUPERTONIC_VOICES`:

| Name | Mixture |
|---|---|
| `low` | F3 .60 · M2 .20 · M4 .20 |
| `even` | F3 .60 · M4 .40 |
| `mid` | F3 ⅓ · F4 ⅓ · M2 ⅓ |
| `clear` | F3 ⅓ · F4 ⅓ · M4 ⅓ |
| `bright` | F4 .60 · M2 .20 · M4 .20 |

**The rule: the female share of a mixture never drops below 60 percent.**
Enforced at import by `_validated()` — the server refuses to start on a breach.
It is not a target frequency; the criterion is that no run tips into the male
register. The reasoning belongs here and **not** in any prompt: design reasons
written into a prompt get recited by the figure.

**One mixture per sentence, never the one before.** A caller that names a voice
gets it; a caller that names none gets one drawn, excluding the previous
sentence's. An explicit seed switches to a purely seed-derived choice, so a seed
reproduces a whole utterance including which mixture spoke it. Module state
`_last_voice` carries "not the last one" across calls, because the platform
makes one call per sentence.

**Seed and F0 guard:** a fresh seed is drawn per utterance, logged and returned
(`X-Speech-Seed`, `X-Speech-Voice`). Without an explicit seed the backend may
redraw up to `SUPERTONIC_F0_REDRAWS` times, keeping the highest fundamental —
the guard against a run tipping male. Variance is wanted; reproducibility is
what the returned seed is for.

## 4. Frontend

`public/ai4artsed-frontend/src/composables/useSpeech.ts` — one composable,
module-scoped state, so starting an utterance ends the one before it. Two
voices at once was never meant.

**The cut: `splitForSpeech(text) → string[]`, at sentence ends and nowhere
else.** Handed a fragment the model does not speak the fragment, it invents a
continuation: 57 characters cut at a comma cost 16.3 s of synthesis for 15.0 s
of audio, against 4.7 s for a whole sentence half again as long. No clause
splitting, ever. A full stop after a one- or two-letter token is an
abbreviation, not a sentence end.

**Asking:** the opening sentence is asked for alone (everything behind one
lock, so asking for several at once puts the first word in a queue), then three
are kept in flight.

**While it is written (since 2026-09-18):** `feed(language, key)` is an
utterance whose pieces are handed over one at a time (`push`, `close`,
`cancel`, `done`); `speak()` is that with every piece pushed at once, and
`done` settles however the utterance ended — sounded to the end, a clip that
could not be had, cancelled, or the line taken by the next utterance or by
`stop()`. On top of it, `follow(language, key, over)` takes the standing text
of a reply as it grows (`update(text, whole)`) and hands a sentence to the
feed once the stream has begun the sentence after it, so the voice begins with
the first sentence while the rest is still being written. The last piece of a
text still arriving waits, because it may still grow, and goes with the
closing text. A text taken back (a tool round's preamble, a draft that failed
its evidence duty) takes its unspoken pieces with it, and the corrected text
starts over from its first sentence. A closing text that the delivery filter
shortened (an offered-choice sentence taken out, `resona_question_filter`)
goes on from where the voice is: what was handed over stays said, what the
closing text has beyond it follows, and the words, seeing a count that differs
from their own cut, read at reading pace. A turn whose voice is over is over
for good — stopped, spoken over by Help, the switch turned off, a clip that
could not be had — and its closing text starts nothing again. A closing text
that arrives whole, nothing handed over before it, is under speak()'s length
rule. `over` is called when the turn's voice is over, however it ended, and
again for every update that arrives after that; never after `drop()`. The
surfaces' side of this is `useSpokenTurn(language, askedKey)`: one follower
per turn, `hand(key, text, whole)` and `end()`, and the surface's `askedKey`
unsaid when the voice is over; both speaking surfaces stand on it. Before
2026-09-18 the voice began after the last byte of the reply.

**The gesture:** browsers sound audio only when a human asked for it.
`primeSpeech()` plays 50 ms of real silence inside a genuine click and marks the
element as the human's. It is spent on the click that switches the voice on, on
sending a message, and on the workshop's own send. Where playback is still
refused, the clip stays loaded and `blockedKey` says so — one tap plays it.

**State, read by three surfaces:**

| Ref | Says |
|---|---|
| `pendingKey` | being synthesized — the wait before the first sound |
| `speakingKey` | sounding, for the whole utterance |
| `blockedKey` | made, refused by the browser, waiting for a tap |
| `soundingPiece` | which piece of which utterance is audible: `{ key, index, text, total, durationMs }`; `total` is null while the utterance is still being handed over |

`soundingPiece` is set at the first `play()` of a piece that actually succeeds —
on the refused path only after the tap makes the gesture good — and cleared at
stop, on a clip that could not be had, and at the end of the utterance. Between
two pieces it is **not** cleared: it keeps naming the piece that just finished,
or the standing words would flicker away at the rhythm of synthesis. Locked by
tests in `composables/__tests__/useSpeech.spec.ts`.

## 5. Writing and speaking together

A text is split into sentences, each sentence gets its audio, and the two are
put out together. Sentence *i* enters at the moment its clip begins to sound;
whichever of the two finishes first releases the next. Nothing waits on a clock.

**Word-for-word alignment is not available and cannot be.** Asked of the ONNX
sessions directly, the four models have exactly four outputs — `duration` (one
number per text, shape `(1,)`), `text_emb`, `denoised_latent`, `wav_tts`.
Nothing maps a character to a time, and synthesizing single words is ruled out
by the fragment finding above.

**What replaces it: the measured span.** `durationMs` carries how long the
sounding piece lasts, read off the clip. The surface spreads the entrance of the
characters across exactly that span instead of a fixed budget, so a sentence is
finished being read at the moment it is finished being spoken. Inside the
sentence a single word is placed proportionally, not aligned — and the error
cannot accumulate, because every sentence starts from a newly measured span.

**Who waits and who does not.** The coupling carries a `pace` flag
(`components/ResonaVoice.vue`):

| Surface | `pace` | Why |
|---|---|---|
| Workshop, "speech and writing" | true (default) | writing and speaking are one thing there; a sentence appearing before it is spoken would be two |
| Contesting (`views/ai_persona.vue`) | **false** | the machine answers in one turn and what it says is read; metered at speaking pace, the last sentence of an eight-sentence answer stood about a minute after the answer had arrived |

## 6. The switch

`voiceChat` in `stores/userPreferences.ts` (localStorage, default **on**), with
a toggle in the main menu left of the colour selection.

**It is read in exactly one place:** `isAvailable` in `useSpeech.ts`, next to
whether the installation can speak at all. Everything that speaks goes through
the feed — `speak()` asks `isAvailable` before an utterance, the feed asks it
before every piece (since 2026-09-18, when a reply began to be spoken while it
is written), and everything that offers to speak asks it — so a surface cannot
keep a voice the listener has silenced, and no figure carries its own copy of
the question. Where a surface has its own way with the voice (the
workshop's writing and speaking modes), that choice sits under this one.

The switch never reaches the server: it decides whether **this browser** hears
the platform, and nothing else. Safety roles and captioning run on their own
paths in the backend and see none of it.

## 7. The surfaces

| Surface | Speaks | Notes |
|---|---|---|
| Contesting (`ai_persona.vue`) | automatically, every reply | words stand whole (§5); replay by tap |
| Workshop (`resona.vue`) | by the listener's mode: speech / speech and writing / writing | mode switch hidden when no voice is available |
| Help (`ChatOverlay.vue`) | automatically, every answer | closing the panel stops it |
| Comparison surfaces | no | they return before the voice note is assembled, deliberately |

## 8. What the figures are told

`_build_voice_context()` in `chat_routes.py` appends a **GIVEN VOICE** block at
the single common exit of `_compose_system_prompt`, so every figure over that
exit gets it. It states that these words can be said aloud, what is happening to
them this turn, and that the voice is mixed and moves between mixtures.

The state sentence is real, not assumed: it comes from
`voice_state_sentence()` in `speech_availability.py`, which reads the same facts
as the status endpoint. Absent a declared mode the sentence is silence — the
honest default, since most surfaces offer no way to hear anything. Surfaces
that do declare: contesting sends `on_request`, or `text` when the listener has
switched the voice off; the workshop sends the listener's mode.

**Two passages were struck (`6ac593ab`) and must not return:** that a
chosen voice "would set a person", and the 60-percent rule with its reasoning.
Both still hold in code. Design reasons in a prompt get recited.

## 9. Open

- **Placement.** In the workshop, GIVEN VOICE sits after the group material —
  same precedent as the CRITICAL language instruction, not a new one. The clean
  resolution comes when a shared figure preamble is built: GIVEN VOICE belongs
  in it, and the append at the exit falls away.
- **The manual.** The switch is user-facing and not yet described in
  `DokumentationModal.vue`.
