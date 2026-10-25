<!--
  ResonaVoice — the shared, pure-presentation "voice". The DUMB piece: no API,
  no markers, no store. Sole consumer today is Resona (/together); Persona and
  Träshy adopt it later.

  Paradigm, "am Objekt gesprochen":
    - Only the ACTIVE TURN is on screen: Resona's latest utterance, with the
      user's answer standing beneath it. Both STAND the whole turn.
    - And of that turn, ONE PARAGRAPH. When the next paragraph is spoken, the
      one before it is gone — not scrolled away, not folded up, not there. One
      listens and reads along and is present, instead of treating the machine
      as a text archive that makes one's own memory and thinking unnecessary:
      a counterpart, and a withdrawal. The
      model is told the same, so a paragraph is written as one: two to four
      sentences.
    - The words sit AT the object they are about (a fine thread to it), and track
      it under pan/zoom (screen-space getBoundingClientRect, transform-aware).
      With no object they stand at a parent-chosen free point ON the board
      (`spot`, a world point converted to screen) — situated in the scene, they
      pan and zoom with it either way. Never glued to the glass.
    - The NEXT turn REPLACES the block in place: the new content fades in while
      the pair it replaces fades off over it, so exactly two dialog texts stand
      and the screen never carries a third. "Ephemeral" = replaced-not-
      accumulated — still NEVER a bottom column that rolls up and fades. The
      fade belongs to the replacement and to nothing else: no timer, no
      fade-by-age, no dissolve show.
    - The two sides are set to opposite edges of the turn: the agent's words to
      the right, the human's line to the left. Aligned INSIDE the block, not
      pinned to the screen — the pair stands at the object it is about, and a
      line pulled to the glass would tear the thread off it.
    - Resona's words arrive SENTENCE BY SENTENCE, through the shared voice
      engine (@/lib/voiceText, @/assets/voiceText.css): standing sans
      entities in the AGENT'S colour (--figure-tint, the pigment its mask
      carries on this page), a per-grapheme entrance, air between them. The
      human's line answers in white — the one writing here that is no agent's. That treatment is
      the same wherever the platform speaks; the engine decides how the words
      READ, this component alone decides where they stand.
    - Where the human asked for BOTH the acoustic voice and the writing, the
      sentences no longer keep a rhythm of their own: each one enters at the
      instant its piece begins to SOUND, so what stands is what is being heard,
      and its characters are spread over the measured length of that piece, so
      that the reading and the hearing END together rather than irritating each
      other. Not word by word — the voice model predicts one duration for a
      whole sentence and decodes it in one piece, so there is no word to align
      to; the sentence is the unit that can be honestly matched.
      The cut into sentences is then the audio's own and is handed in by the
      parent (`coupling.segment`) — only the same cut makes sentence i and
      piece i the same thing. Here the words WAIT for the voice and never run
      ahead of it. What lets the rest of a turn stand is the voice having
      ENDED — refused by the browser, a clip that could not be had, stopped by
      the human, or spoken through to its last piece — and the human's own way
      out, which is to ask for writing alone.

  Positioning and the sentence DOM are IMPERATIVE (direct style/attribute
  writes, nodes built by hand), kept off Vue's reactive path on purpose: a
  reactive re-render would interrupt the entrance halfway through and pile up
  stale nodes.

  Contract:
    - Props IN:  trail (read-only render-copy of the utterances),
                 streamingId (which line is being spoken; the entrance is
                 paced by the engine, so `cadence` no longer does anything),
                 speak (idle | listening | speaking | blocked),
                 anchors [{id, getRect(), label}] (Faden targets = object boxes),
                 spot() (screen point of the board-situated resting place),
                 coupling (the sounding voice, where the words follow one).
    - Emits:     lift (human pulls Resona's line out to keep it), revealDone.

  Two hard rules this component obeys:
    1) Ephemeral = ONLY the voice. The lift button carries pointer-events; the
       standing words do not — clickable/persistent things live in the parent.
    2) Ephemeral = visual only. We never mutate the trail.

  Voice only: with `words` false the standing text gives way to
  being heard. What she says is not read; the turn keeps only what a human still
  has to be able to DO with it.

  NO PRESENCE IS DRAWN HERE, in any mode. A page carries exactly one agent and
  one mask for it, and that mask stands in the app-level overlay
  (components/ChatOverlay.vue), tinted for this page and fed this surface's own
  state through stores/pageFigure. A shape of this component's own would be a
  second agent standing beside the first one. The flowing circle that used to
  stand here is gone with that.

  What the circle also CARRIED stays, as chips: the way back to the line (the
  platform's one speaker control, the same one words mode shows beside "lift
  out") and keeping it. `sounding` says whether the acoustic voice is audible
  right now; that is a different thing from `speak`, which describes the turn.
-->
<template>
  <div ref="rootRef" class="resona-voice">
    <!-- Faden: one thread from Resona's line to the object it speaks about.
         Its `d` is written imperatively (empty when there is no object). -->
    <svg class="faden-layer" aria-hidden="true">
      <path ref="fadenPathEl" class="faden" d="" />
    </svg>

    <!-- The active turn — one persistent box; only its inner body is re-keyed so
         a new turn fades in and replaces the old. -->
    <div
      ref="turnEl"
      class="turn"
      :class="{ anchored: isAnchored, listening: speak === 'listening', 'voice-only': !words }"
    >
      <!-- The pair that has just been replaced, on its way out. Two dialog
           texts stand at a time and no more: this is a plain-text copy of what
           stood a moment ago, put up unanimated and faded off. It carries no
           ref and no per-character DOM — that belongs to the imperative render
           below and goes with the keyed body — and it is absolute, so the
           arriving turn is never pushed down by what is leaving. -->
      <div v-if="leaving" class="turn-body turn-leaving" aria-hidden="true">
        <div v-if="leaving.answer && leaving.answerAbove" class="turn-answer above">{{ leaving.answer }}</div>
        <div v-if="leaving.sentences.length" class="turn-said">
          <div class="sent-stack">
            <div v-for="(line, i) in leaving.sentences" :key="i" class="voice-sent">{{ line }}</div>
          </div>
        </div>
        <div v-if="leaving.answer && !leaving.answerAbove" class="turn-answer">{{ leaving.answer }}</div>
      </div>

      <!-- What has been said stands only once there is something said. The
           column around it stands always, because it carries the open line. -->
      <div
        v-if="said || isFirstTurnPending || !words || speak === 'listening'"
        class="turn-body"
        :key="said ? said.id : 'pending'"
      >
        <!-- The human's line of this exchange, in the order it was spoken: the
             question above the words it brought about, a line written since
             below them. -->
        <div
          v-if="answer && answerAbove"
          class="turn-answer above"
          :class="{ settling: settlingId !== null && answer.id === settlingId }"
        >{{ answer.text }}</div>

        <div v-if="words && said" class="turn-said">
          <!-- The sentences are built and revealed by hand (see
               renderSentences); Vue only owns the empty ground they stand
               on. No caret: the entrance itself is the liveness, and a
               caret would mime someone typing at a remote call. -->
          <div ref="sentStackEl" class="sent-stack"></div>
          <button
            v-if="said.liftable && said.id !== streamingId"
            class="lift-btn"
            @click="emit('lift', said)"
          >{{ liftLabel }}</button>
          <SpeakButton
            v-if="canReplay && said.id !== streamingId"
            :sounding="sounding"
            :waiting="preparing"
            :blocked="blocked"
            :label="blocked ? tapLabel : replayLabel"
            @press="emit('replay', said)"
          />
        </div>

        <!-- Voice only: nothing is written, the line is heard. No shape stands
             here — the page's one mask is its presence. What stays are the two
             things a human still has to be able to do with a spoken line: hear
             it again, and keep it. The speaker is the platform's one speaker
             control, exactly as words mode shows it beside "lift out"; keeping
             it is the human's decision, and a memo is a thing they asked for. -->
        <div v-if="!words" class="turn-voice-only">
          <SpeakButton
            v-if="said && canReplay && said.id !== streamingId"
            :sounding="sounding"
            :waiting="preparing"
            :blocked="blocked"
            :label="blocked ? tapLabel : replayLabel"
            @press="emit('replay', said)"
          />
          <button
            v-if="said && said.liftable"
            class="lift-btn lift-quiet"
            @click="emit('lift', said)"
          >{{ liftLabel }}</button>
        </div>

        <!-- What the human wrote always stands, in every mode. Voice only
             means RESONA is heard instead of read; it never means the room's
             own words vanish. -->
        <div
          v-if="answer && !answerAbove"
          class="turn-answer"
          :class="{ settling: settlingId !== null && answer.id === settlingId }"
        >{{ answer.text }}</div>
      </div>

      <!-- The line being written right now. It stands OUTSIDE the keyed body,
           because the body is rebuilt with every turn and the caret may not be
           torn out from under someone mid-word — and it stands directly under
           the agent's words, flush left, because it IS the human's line of this
           exchange, before it is sent. -->
      <div
        ref="writeLineEl"
        class="turn-writing"
        @focusin="lineFocused = true"
        @focusout="lineFocused = false"
      >
        <!-- A caret standing in an empty line, before anybody has touched it:
             it says that one may simply begin. The browser draws its own only
             once the line has the focus, and until then nothing on the surface
             said where writing happens. It goes as soon as the line is focused
             (the real caret takes over, in the same place) or written in. -->
        <span v-if="lineEmpty && !lineFocused" class="write-caret" aria-hidden="true"></span>
        <slot name="speakline" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import SpeakButton from '@/components/SpeakButton.vue'
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  buildVoiceSentence,
  revealVoiceSentence,
  splitVoiceSentences,
  voiceCharMode,
} from '@/lib/voiceText'
import '@/assets/voiceText.css'

export interface VoiceUtterance {
  id: string | number
  role: 'assistant' | 'user'
  text: string
  anchorId?: string
  liftable?: boolean
  /** Drafts this turn wrote and then took back, oldest first. They stand
   *  struck through above the version that replaced them; see
   *  .voice-sent.withdrawn in @/assets/voiceText.css. */
  withdrawn?: string[]
}
export interface VoiceAnchor {
  id: string
  getRect: () => DOMRect | null
  label?: string
}
export type SpeakState = 'idle' | 'listening' | 'speaking' | 'blocked'

/** The piece of an utterance that is sounding right now, numbered over the same
 *  pieces `VoiceCoupling.segment` returns. */
export interface VoicePiece {
  key: string | number
  index: number
  text: string
  /** How many pieces the utterance has; null while it is still being handed over. */
  total: number | null
  /** How long this piece sounds, measured on the clip; null when it cannot say. */
  durationMs: number | null
}
/**
 * The sounding voice, as far as the standing words need to know it: which piece
 * of which utterance is audible, which utterance has been asked for, is being
 * made, is sounding or is waiting for a tap, and how that voice cuts a text
 * into pieces.
 *
 * `askedKey` is the parent's own word and comes before all the others: the
 * speech may take until after this pass to know its own key, or never set one
 * at all, and by then the words would already be standing.
 *
 * Declared here and never imported from the speech composable: a surface with
 * no voice at all must be able to use this component, which is also why the
 * segmenter is handed IN rather than reached for.
 */
export interface VoiceCoupling {
  piece: VoicePiece | null
  askedKey: string | number | null
  pendingKey: string | number | null
  speakingKey: string | number | null
  blockedKey: string | number | null
  segment: (text: string) => string[]
}

const props = withDefaults(defineProps<{
  trail: VoiceUtterance[]
  streamingId?: string | number | null
  /** UNUSED since the words arrive sentence-wise: the entrance carries its own
   *  rhythm (see @/lib/voiceText). Kept so callers need not change. */
  cadence?: number
  speak?: SpeakState
  anchors?: VoiceAnchor[]
  liftLabel?: string
  zoom?: number
  words?: boolean
  sounding?: boolean
  canReplay?: boolean
  replayLabel?: string
  preparing?: boolean
  /** Synthesized, held back until a tap: the browser wants a human gesture. */
  blocked?: boolean
  tapLabel?: string
  /** Set only where the words follow a voice; null everywhere else, and then
   *  this component behaves exactly as it did before. Its fields are read at
   *  the moment they are needed, so a parent may hand in live accessors. */
  coupling?: VoiceCoupling | null
  /** The open line stands empty and can be written in: a caret is put up in it
   *  until somebody does. The host owns this — it is the host that holds the
   *  text of the line and knows whether the surface is busy. */
  lineEmpty?: boolean
}>(), {
  streamingId: null,
  cadence: 46,
  speak: 'idle',
  anchors: () => [],
  spot: null,
  liftLabel: 'lift out',
  zoom: 1,
  words: true,
  sounding: false,
  canReplay: false,
  replayLabel: 'hear this again',
  preparing: false,
  blocked: false,
  tapLabel: 'tap to hear it',
  coupling: null,
  lineEmpty: false,
})

const emit = defineEmits<{
  lift: [utterance: VoiceUtterance]
  revealDone: [id: string | number]
  replay: [utterance: VoiceUtterance]
}>()

const rootRef = ref<HTMLElement | null>(null)
const turnEl = ref<HTMLElement | null>(null)
const fadenPathEl = ref<SVGPathElement | null>(null)
const sentStackEl = ref<HTMLElement | null>(null)
const writeLineEl = ref<HTMLElement | null>(null)
// Whether the open line has the focus. Read here and not handed in, because it
// is the slot inside this wrapper that has it — the host would have to report
// a thing this element already sees.
const lineFocused = ref(false)

// ---- active turn: Resona's latest line + the user's answer beneath it ----
// The whole on-screen voice is exactly this one exchange. Everything earlier is
// gone from view (it lives in the parent's messages[], never here).
const said = computed<VoiceUtterance | null>(() => {
  for (let i = props.trail.length - 1; i >= 0; i--) {
    if (props.trail[i]!.role === 'assistant') return props.trail[i]!
  }
  return null
})
// Before Resona's very first reply there is no `said` to stand beneath — without
// this, the opening exchange rendered nothing at all until the reply landed, so
// the user's own line and Resona's reply appeared to arrive together. Once the
// user has spoken, stand the box up early (listening, no said text yet) so the
// wait itself is visible instead of silent.
const isFirstTurnPending = computed(() => !said.value && props.trail.some(u => u.role === 'user'))
// The human's line of THIS exchange. Two dialog texts stand at a time and they
// are the two of one exchange: the agent's words, and the human's line beside
// them. Which human line that is depends on where the exchange has got to — the
// one written SINCE the reply if there is one, otherwise the one that brought
// the reply about. That second case is the ordinary one, and leaving it out left
// the reply standing alone with the question that produced it nowhere on screen.
const answer = computed<VoiceUtterance | null>(() => {
  const s = said.value
  if (s) {
    const i = props.trail.findIndex(u => u.id === s.id)
    const nxt = i >= 0 ? props.trail[i + 1] : undefined
    if (nxt && nxt.role === 'user') return nxt
    for (let k = i - 1; k >= 0; k--) {
      if (props.trail[k]!.role === 'user') return props.trail[k]!
    }
    return null
  }
  if (!isFirstTurnPending.value) return null
  for (let i = props.trail.length - 1; i >= 0; i--) {
    if (props.trail[i]!.role === 'user') return props.trail[i]!
  }
  return null
})

// Where that line stands: ABOVE the agent's words when it came first — the
// question, then the answer, in the order they were spoken.
const answerAbove = computed(() => {
  const s = said.value
  const a = answer.value
  if (!s || !a) return false
  const i = props.trail.findIndex(u => u.id === s.id)
  const j = props.trail.findIndex(u => u.id === a.id)
  return i >= 0 && j >= 0 && j < i
})

// ---- what stands, and what is on its way out ----
// Never more than the two texts of one exchange. `standing` is the plain-text
// record of the pair currently up — kept because the sentence DOM is built
// imperatively and is torn down with the keyed body, so there would be nothing
// left to fade once the next turn arrives. `leaving` is that record put back up
// for the length of the fade, and then dropped.
interface TurnRecord {
  id: string | number
  sentences: string[]
  answer: string | null
  answerAbove: boolean
}
let standing: TurnRecord | null = null
const leaving = ref<TurnRecord | null>(null)
const LEAVE_MS = 620
let leaveTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => (said.value ? said.value.id : null),
  (nextId, prevId) => {
    if (prevId == null || prevId === nextId) return
    const gone = standing
    standing = null
    if (!gone || gone.id !== prevId) return
    if (!gone.sentences.length && !gone.answer) return
    if (leaveTimer) clearTimeout(leaveTimer)
    leaving.value = gone
    leaveTimer = setTimeout(() => {
      leaving.value = null
      leaveTimer = null
    }, LEAVE_MS)
  },
)

// ---- the standing words: sentence by sentence, built by hand ----
// The voice owns no API, so nothing here is SSE-bound; what arrives is the
// trail entry's text, and the turn's rhythm is made in this component.
// Sentence splitting, the sentence DOM and the entrance belong to the shared
// engine — the same words, treated the same way, wherever the platform speaks.

/** The line still being spoken, read live so a growing text is picked up. */
const streamingLiveText = computed(
  () => props.trail.find(u => u.id === props.streamingId)?.text ?? ''
)

/** The reply's language. No i18n here on purpose: the document's own lang is
 *  the same truth on this app, and the voice must not depend on its host. */
function voiceLocale(): string {
  return document.documentElement.lang || navigator.language || 'en'
}

// Which turn stands in the container, how many of its sentences are in it, and
// the text those sentences were made from — the last is what tells a pass that
// brought new words from one that only re-ran. Off the reactive path, with
// everything else imperative here.
//
// `split` is the turn's own cutter and `splitBy` says whose it is. Both are
// fixed at the turn's first pass and then held: re-cutting mid-turn would make
// sentences that already stand jump, and the cutter has to outlive the coupling
// it came from — the parent takes that away the instant the human switches to
// writing alone, with the turn's words still on screen.
interface RenderedFor {
  id: string | number | null
  /** Which paragraph of this turn is the one on the surface, -1 before the first. */
  para: number
  /** The last piece of it that has been reached, -1 before the first. */
  upTo: number
  /** The pieces that are ON the surface, in their order, as they were placed. */
  shown: string[]
  /** How many withdrawn drafts of this turn have already been shown. */
  struck: number
  text: string
  split: (text: string) => string[]
  splitBy: 'voice' | 'speech'
  /** One drift warning per turn, not one per pass. */
  warned: boolean
}
function freshRender(id: string | number | null, c: VoiceCoupling | null): RenderedFor {
  return {
    id,
    para: -1,
    upTo: -1,
    shown: [],
    struck: 0,
    text: '',
    split: c ? c.segment : (text: string) => splitVoiceSentences(text, voiceLocale()),
    splitBy: c ? 'speech' : 'voice',
    warned: false,
  }
}
let renderedFor: RenderedFor = freshRender(null, null)
// From inside there is no end-of-stream signal: quiet for long enough is what
// says the utterance is whole. `quietFor` is the turn the running wait belongs
// to, so a pass that brought nothing new can leave it alone.
const QUIET_MS = 900
let quietTimer: ReturnType<typeof setTimeout> | null = null
let quietFor: string | number | null = null
function stopQuiet() {
  if (quietTimer) clearTimeout(quietTimer)
  quietTimer = null
  quietFor = null
}
function startQuiet(id: string | number, done: () => void) {
  stopQuiet()
  quietFor = id
  quietTimer = setTimeout(() => {
    quietTimer = null
    quietFor = null
    done()
  }, QUIET_MS)
}

// WHERE NO VOICE SPEAKS, READING IS THE CLOCK. A paragraph stands for as long
// as it takes to read and is then replaced by the next one — the surface never
// releases a whole reply, not when the browser refuses to play, not in writing
// mode, not when the pieces of the audio and the pieces of the text disagree.
// Releasing everything is what an accumulating surface does, and this one does
// not accumulate.
let readTimer: ReturnType<typeof setTimeout> | null = null
let readDue = false
function stopRead() {
  if (readTimer) clearTimeout(readTimer)
  readTimer = null
  readDue = false
}
function readMs(text: string): number {
  return Math.max(2600, Math.min(16000, text.length * 55))
}

function appendSentence(
  stack: HTMLElement,
  text: string,
  index: number,
  delayMs: number,
  spanMs?: number,
) {
  const el = buildVoiceSentence(text, { charMode: voiceCharMode(voiceLocale()), spanMs })
  stack.appendChild(el)
  revealVoiceSentence(el, delayMs)
}

/**
 * How many sentences may stand together at the very most. THE SURFACE
 * guarantees the paragraph, not the writer: where a reply arrives without a
 * single blank line in it — and one that is still arriving has none yet at the
 * place it has reached — the whole turn would be one paragraph and would stand
 * whole, which is the accumulation this rule exists to end.
 */
const PARAGRAPH_MAX = 3

/**
 * Which paragraph each sentence of a turn belongs to.
 *
 * The text is cut into sentences ONCE, by the cutter the audio was cut with —
 * cutting paragraph by paragraph instead would make different pieces, and then
 * sentence i and clip i are no longer the same thing. So the sentences are
 * walked back over the text they came from, and every blank line passed on the
 * way starts a paragraph; PARAGRAPH_MAX starts one where the writer set none.
 * A sentence that cannot be found again (a cutter that rewrites rather than
 * slices) stays in the paragraph before it, which keeps it standing rather than
 * dropping it — and is counted towards the cap like any other.
 */
function paragraphOf(text: string, parts: string[]): number[] {
  const out: number[] = []
  let at = 0
  let para = 0
  let inPara = 0
  for (const part of parts) {
    const t = part.trim()
    const found = t ? text.indexOf(t, at) : -1
    const breaks = found < 0 ? null : text.slice(at, found).match(/\n[ \t]*\n/g)
    if (breaks || inPara >= PARAGRAPH_MAX) {
      para += 1
      inPara = 0
    }
    out.push(para)
    inPara += 1
    if (found >= 0) at = found + t.length
  }
  return out
}

function renderSentences() {
  const stack = sentStackEl.value
  const s = said.value
  const streaming = !!s && s.id === props.streamingId

  // Voice only, or nothing said yet: no words stand. The state is reset even
  // though the container is gone, or the words would not come back when the
  // human switches writing on again.
  if (!s || !props.words) {
    stopRead()
    stack?.replaceChildren()
    renderedFor = freshRender(null, null)
    standing = s
      ? { id: s.id, sentences: [], answer: answer.value ? answer.value.text : null, answerAbove: answerAbove.value }
      : null
    if (!streaming) { stopQuiet(); return }
    if (quietFor !== s.id) startQuiet(s.id, () => emit('revealDone', s.id))
    return
  }
  if (!stack) return

  const setStanding = (sentences: string[]) => {
    standing = {
      id: s.id,
      sentences,
      answer: answer.value ? answer.value.text : null,
      answerAbove: answerAbove.value,
    }
  }

  const fullText = streaming ? streamingLiveText.value : s.text
  const c = props.coupling
  if (renderedFor.id !== s.id) {
    stopQuiet()
    stopRead()
    stack.replaceChildren()
    renderedFor = freshRender(s.id, c)
  }

  // A draft that was taken back stands ALONE, struck through, in the place the
  // paragraph has. The corrected text takes that place with its first
  // paragraph, so the correction is read where it was made.
  const struckNow = s.withdrawn?.length ?? 0
  if (struckNow > renderedFor.struck) {
    const draft = s.withdrawn![struckNow - 1] ?? ''
    stack.replaceChildren()
    const el = buildVoiceSentence(draft, { charMode: false, extraClass: 'withdrawn' })
    stack.appendChild(el)
    revealVoiceSentence(el, 0)
    renderedFor.struck = struckNow
    renderedFor.para = -1
    renderedFor.upTo = -1
    renderedFor.shown = []
    renderedFor.text = ''
    setStanding([draft])
  }

  const grew = fullText !== renderedFor.text
  renderedFor.text = fullText

  const parts = renderedFor.split(fullText)
  const paras = paragraphOf(fullText, parts)
  // The last piece of a text that is still arriving may still grow, so it is
  // not a piece yet.
  const settled = streaming ? parts.length - 2 : parts.length - 1

  // HOW FAR THE TURN HAS COME. Where a voice speaks it, that is the piece which
  // is SOUNDING — nothing may stand that is not being heard. Where none does,
  // reading is the clock. There is no third case in which the whole reply is
  // handed over at once.
  const k = s.id
  let piece = c && c.piece && c.piece.key === k ? c.piece : null
  // A count of null is a count not known yet — the utterance is still being
  // handed over — and says nothing about the cut.
  let mismatched = false
  if (piece && !streaming && piece.total !== null && piece.total !== parts.length) {
    // The voice cut this text into a different number of pieces than the words
    // were cut into, so piece i and piece i are no longer the same thing. The
    // words fall back on the reading clock rather than on standing whole.
    if (!renderedFor.warned) {
      renderedFor.warned = true
      console.warn(`[VOICE] ${piece.total} spoken pieces against ${parts.length}`
        + ' written pieces — this turn is read at reading pace')
    }
    piece = null
    mismatched = true
  }
  // A sound the browser will not start without a gesture is not a clock: the
  // words go on at reading pace so the turn can be read at all. Should the
  // human then hand the gesture over, the voice takes the lead back and the
  // paragraph it begins in is the one that stands.
  const blocked = !!c && c.blockedKey === k
  // A voice whose cut differs from the words' is no clock for them, asked
  // for or not: held for it, the words would stand at one sentence while it
  // speaks the rest.
  const asked = !!c && !blocked && !mismatched && renderedFor.splitBy === 'speech'
    && (c.askedKey === k || c.pendingKey === k || c.speakingKey === k)

  let reached: number
  let span: number | undefined
  if (piece) {
    reached = Math.min(piece.index, parts.length - 1)
    span = piece.durationMs ?? undefined
    stopRead()
  } else if (asked) {
    // Asked, and no clip sounding yet: the first piece stands, so the turn is
    // visible at all while its opening clip is being made. Nothing follows it
    // until there is a voice to follow.
    reached = Math.max(renderedFor.upTo, 0)
    stopRead()
  } else {
    reached = Math.max(renderedFor.upTo, 0)
    if (readDue) {
      readDue = false
      reached = renderedFor.upTo + 1
    }
    reached = Math.min(reached, settled)
  }
  if (reached < 0 || reached >= parts.length) {
    // The text was taken back (a tool round's preamble, `discard`) below what
    // stood: nothing that stands is in it any more, so nothing stands. Left
    // as it was, the preamble stood through the whole tool run.
    if (reached >= parts.length && renderedFor.upTo >= 0) {
      stack.replaceChildren()
      renderedFor.shown = []
      renderedFor.para = -1
      renderedFor.upTo = -1
    }
    if (renderedFor.upTo < 0) setStanding([])
    return
  }

  // ONE PARAGRAPH STANDS, and only one. A paragraph is where the writer put a
  // blank line, and at the latest after PARAGRAPH_MAX pieces — one piece is one
  // sentence, and a single sentence at a time is too radical a cut. When the
  // next paragraph is reached, what stood is REMOVED: one listens and reads
  // along and is present, instead of treating the machine as a text archive
  // that makes one's own memory and thinking unnecessary. Only one paragraph
  // at a time stands: the AI is a counterpart here, and also a withdrawal.
  const para = paras[reached] ?? 0
  let from = reached
  while (from > 0 && paras[from - 1] === para) from--

  // What SHOULD stand is worked out first and then compared with what does.
  // Where the surface already carries the beginning of it, only the tail is
  // added, so that what is lit stays lit; in every other case — the next
  // paragraph, a piece that came out differently once the rest of the sentence
  // had arrived — the surface is cleared and set anew. There is no path on
  // which something stands that this pass did not ask for.
  const want = parts.slice(from, reached + 1)
  const kept =
    para === renderedFor.para &&
    want.length >= renderedFor.shown.length &&
    renderedFor.shown.every((t, i) => t === want[i])
  if (!kept) {
    stack.replaceChildren()
    renderedFor.shown = []
    renderedFor.para = para
  }
  for (let i = renderedFor.shown.length; i < want.length; i++) {
    const part = want[i]
    if (part === undefined) continue
    // The piece that is SOUNDING is handed the measured length of its own clip
    // and begins at once — there is nothing to wait for, the clip is already
    // running — so that it is finished being read at the moment it is finished
    // being heard.
    appendSentence(stack, part, from + i, 0, from + i === reached ? span : undefined)
    renderedFor.shown.push(part)
  }
  renderedFor.upTo = reached
  setStanding(want)

  if (!piece && !asked && renderedFor.upTo >= 0 && renderedFor.upTo < settled && !readTimer) {
    const held = parts[renderedFor.upTo] ?? ''
    readTimer = setTimeout(() => {
      readTimer = null
      readDue = true
      renderSentences()
    }, readMs(held))
  }

  if (!streaming) { stopQuiet(); return }
  // From inside there is no end-of-stream signal: quiet for long enough is what
  // says the utterance is whole. Only NEW TEXT restarts the wait — a pass that
  // brought nothing new (the parent rebuilt the trail, an anchor moved) leaves
  // the running wait alone, or a busy parent could postpone the end of the turn
  // indefinitely. The parent clears streamingId on it, which brings the last
  // piece into `settled` on the pass that follows.
  if (!grew && quietFor === s.id) return
  startQuiet(s.id, () => emit('revealDone', s.id))
}

// flush 'post': the keyed .turn-body is rebuilt for a new turn and the words
// mode adds or removes the container — the ref must already point at the DOM
// this pass is going to write into.
// The coupling is watched field by field, and whether there is one at all:
// what moves during a turn is the piece and the keys, while the object holding
// them may well stay the same one from the first sentence to the last.
watch(
  () => [
    said.value?.id, props.streamingId, props.words, streamingLiveText.value,
    !!props.coupling, props.coupling?.piece, props.coupling?.askedKey,
    props.coupling?.pendingKey, props.coupling?.speakingKey, props.coupling?.blockedKey,
  ],
  renderSentences,
  { flush: 'post' },
)

// ---- Faden + placement (IMPERATIVE — never touches a reactive ref) ----
// Screen-space getBoundingClientRect is transform-aware, so the words track the
// object under pan/zoom without ever reading the world transform.
function activeAnchor(): VoiceAnchor | null {
  const s = said.value
  if (!s || !s.anchorId) return null
  return (props.anchors ?? []).find(a => a.id === s.anchorId) ?? null
}
const isAnchored = computed(() => !!activeAnchor())

// ---- what the surface gives back for the effort of writing ----
// The human writes at twice the size everything here is read at, and the line
// SETTLES to that size the moment it is sent — before any answer to it exists,
// so the acknowledgement belongs to the writing and not to the reply. Only a
// line just written settles: a history restored from the journal arrives at its
// standing size, without ceremony. That is what the growth test is for — a
// trail that grew by exactly one, ending in the human's own line.
const SETTLE_MS = 560
const settlingId = ref<string | number | null>(null)
let trailLen = -1
let settleTimer: number | undefined
watch(
  () => props.trail.length,
  (n) => {
    const grewByOne = trailLen >= 0 && n === trailLen + 1
    trailLen = n
    if (!grewByOne) return
    const last = props.trail[n - 1]
    if (!last || last.role !== 'user') return
    settlingId.value = last.id
    window.clearTimeout(settleTimer)
    settleTimer = window.setTimeout(() => { settlingId.value = null }, SETTLE_MS)
  },
  { immediate: true },
)
onUnmounted(() => window.clearTimeout(settleTimer))

// Where the open line stands, as a fraction of the surface's height: a little
// below the middle, where a page is read from. Everything the turn carries
// grows UPWARD from it, so the human writes at the same height on the screen
// however long the exchange gets: every new input scrolls so that the user
// always writes at the vertical centre of the screen or slightly below.
const WRITE_LINE_AT = 0.55
/** Air between the surface's top edge and the turn standing under it. */
const TURN_TOP_GAP = 24

// ---- bottom guard: the words never cover the surface's own input line ----
// Resona's replies run to ten sentences; unguarded the stack grows straight
// down across the Werkstatt-Journal strip and the write line, and the chips
// standing after it land off-screen. So the stack is capped at the room
// between the turn's top edge and the speak-line, and what does not fit fades
// out at that edge. Nothing is lost with it: the whole utterance stays
// reachable through lift-out, the acoustic voice, and the journal.
// The surplus always leaves by the FOOT, wherever the turn stands. A reply is
// read from its first sentence — that is where it says what it is answering —
// so the head stays and the newest lines are the ones that fall away.
const STACK_FADE_BOTTOM = 'linear-gradient(180deg, #000 0, #000 calc(100% - 44px), transparent 100%)'
// ---- fitting the turn to its room ----
// A reply longer than the space over the open line used to lose its end. It
// does not have to: a column set for a short answer is holding width it could
// spend, air between sentences it can close, and leading it can narrow. The
// rungs go from the platform's own setting to the tightest that still reads;
// the first one that fits is the one that stands. Cutting is what happens when
// even the last rung is too small, and then it is the FOOT that goes.
const FIT_RUNGS = [
  { wide: 1.00, air: 0.55, lead: 1.60 },
  { wide: 1.16, air: 0.44, lead: 1.54 },
  { wide: 1.32, air: 0.33, lead: 1.47 },
  { wide: 1.48, air: 0.23, lead: 1.40 },
  { wide: 1.64, air: 0.14, lead: 1.35 },
]
// Re-measured when the turn, the number of sentences standing in it, or the
// room itself changes — never per frame: each rung costs a forced layout.
let fitKey = ''
function applyRung(el: HTMLElement, i: number) {
  const r = FIT_RUNGS[Math.max(0, Math.min(FIT_RUNGS.length - 1, i))]!
  el.style.setProperty('--voice-wide', String(r.wide))
  el.style.setProperty('--voice-air', `${r.air}em`)
  el.style.setProperty('--voice-lead', String(r.lead))
}
/**
 * @param room screen pixels the sentences may take
 * @returns whether they fit in it, on the rung now standing
 */
function fitToRoom(room: number): boolean {
  const t = turnEl.value
  const stack = sentStackEl.value
  if (!t || !stack) return true
  const z = props.zoom > 0 ? props.zoom : 1
  const key = `${renderedFor.id}|${renderedFor.para}.${renderedFor.shown.length}|${Math.round(room / 10)}`
  if (key === fitKey) return stack.scrollHeight * z <= room
  fitKey = key
  for (let i = 0; i < FIT_RUNGS.length; i++) {
    applyRung(t, i)
    // The measurement is of the stack ALONE; what else the turn carries (the
    // human's line, the air around it) is measured by the caller and already
    // taken off the room handed in here.
    if (stack.scrollHeight * z <= room) return true
  }
  return false
}

// What was last written, so a per-frame guard is a comparison and not a style
// write. The element is tracked with it: a new turn is a new .sent-stack (the
// keyed .turn-body rebuilds it) and that one carries no inline style yet.
let capEl: HTMLElement | null = null
let capWritten = -1
let capFaded = false
/**
 * @param room  screen pixels the stack may take, or null for as much as it wants
 */
function capStack(room: number | null) {
  const stack = sentStackEl.value
  if (!stack) return
  if (stack !== capEl) { capEl = stack; capWritten = -1; capFaded = false }
  // The turn is transform-scaled by zoom from its top left, so a screen
  // distance is that many CSS pixels only at 1:1. The cap is a length INSIDE
  // the scaled box and has to be divided by the scale.
  const z = props.zoom > 0 ? props.zoom : 1
  const cap = room === null ? Infinity : Math.max(0, room / z)
  if (cap !== capWritten && (cap === Infinity || Math.abs(cap - capWritten) >= 1)) {
    if (cap === Infinity) stack.style.removeProperty('max-height')
    else stack.style.maxHeight = `${Math.round(cap)}px`
    capWritten = cap
  }
  // The fade says "there is more"; it only appears when something is really
  // cut off. Always on, it would dim a line of every short reply.
  const cut = stack.scrollHeight > cap + 1
  if (cut !== capFaded) {
    if (cut) {
      stack.style.setProperty('-webkit-mask-image', STACK_FADE_BOTTOM)
      stack.style.setProperty('mask-image', STACK_FADE_BOTTOM)
    } else {
      stack.style.removeProperty('-webkit-mask-image')
      stack.style.removeProperty('mask-image')
    }
    capFaded = cut
  }
}

/** Last height written, so the per-frame placement is a comparison and not a
 *  style write — and reset when the turn changes hands to an object. */
let topWritten = -1e9
function place() {
  const root = rootRef.value
  const t = turnEl.value
  const p = fadenPathEl.value
  if (!root || !t) return
  const base = root.getBoundingClientRect()
  const a = activeAnchor()
  const r = a ? a.getRect() : null
  if (!a || !r) {
    // No object to stand at: the exchange stands in the middle of the surface,
    // and what is held still there is the OPEN LINE — not the block around it.
    // Whatever the turn carries above the line grows upward, so the human keeps
    // writing at the same height on the screen while the exchange gets longer.
    // Horizontally the box still centres itself in CSS; only the height is
    // measured, because only the height depends on what has been said.
    t.style.removeProperty('left')
    if (p) p.setAttribute('d', '')
    const z = props.zoom > 0 ? props.zoom : 1
    const stack = sentStackEl.value
    const tr0 = t.getBoundingClientRect()
    const wTop = writeLineEl.value ? writeLineEl.value.getBoundingClientRect().top : tr0.top
    // Everything above the open line, split into the stack and the rest of it
    // (the human's question, the air between). The rest is what the stack's cap
    // cannot change, so it is what the room for the stack is measured against.
    const stackNow = stack ? stack.getBoundingClientRect().height : 0
    const stackFull = stack ? stack.scrollHeight * z : 0
    const otherAbove = Math.max(0, wTop - tr0.top - stackNow)
    // Three things are given up before anything is cut, in this order, and
    // each one only once the one before it has run out:
    //   1. what the column itself holds — width, then the air between the
    //      sentences, then the leading (fitToRoom);
    //   2. the room BELOW the open line — the line rests at 0.55 and is pushed
    //      down from there, as far as the last place it can still stand whole
    //      ("in der Bildschirmmitte ODER LEICHT DARUNTER");
    //   3. only then the foot of the reply.
    const target = base.top + base.height * WRITE_LINE_AT
    fitToRoom(Math.max(0, target - (base.top + TURN_TOP_GAP) - otherAbove))
    const stackFull2 = stack ? stack.scrollHeight * z : 0
    const need = otherAbove + stackFull2
    // The lowest the open line may stand and still be whole above the surface's
    // own foot. Measured, because the line grows with what is written into it.
    const writeH = writeLineEl.value ? writeLineEl.value.getBoundingClientRect().height : 40
    const floorTop = base.bottom - writeH - 28
    const lineTop = Math.min(Math.max(target, base.top + TURN_TOP_GAP + need), floorTop)
    const room = Math.max(0, lineTop - (base.top + TURN_TOP_GAP))
    const fits = need <= room
    capStack(fits ? null : room - otherAbove)
    const top = fits ? lineTop - need - base.top : TURN_TOP_GAP
    if (Math.abs(top - topWritten) >= 1) {
      t.style.top = `${Math.round(top)}px`
      topWritten = top
    }
    return
  }
  topWritten = -1e9
  const tr = t.getBoundingClientRect()
  const bw = tr.width || 320
  const gap = 22
  const onRight = (base.right - r.right) > (bw + gap + 16)
  const left = onRight ? (r.right - base.left + gap) : (r.left - base.left - gap - bw)
  // No clamp: the words belong to the thing. If the thing leaves the view,
  // the words leave with it — never held back at the glass edge.
  const top = r.top - base.top
  t.style.left = `${Math.round(left)}px`
  t.style.top = `${Math.round(top)}px`
  // Same guard when the words stand at an object: the turn's top edge is the
  // anchor's, just written above — the rect for it is already in hand. There
  // the column hangs from the thing, so the foot of the surface is the limit.
  // No widening there: the column is beside the thing it speaks about, and a
  // wider one would cover it. It closes its air and narrows its leading only.
  const objRoom = root.getBoundingClientRect().bottom - 96 - r.top - 24
  fitToRoom(objRoom)
  capStack(objRoom)
  if (p) {
    const x1 = onRight ? tr.left - base.left : tr.right - base.left
    // 16px down the box = its first line of text; that point sits 16 * zoom
    // below the box top once the turn scales with the board.
    const y1 = tr.top - base.top + 16 * props.zoom
    // The thread must TOUCH the box border, not vanish into its middle. Aim at
    // the centre, then walk back out to where the centre->source line crosses
    // the rectangle: scale the direction by the nearer of the two axis limits
    // (s = min(halfW/|dx|, halfH/|dy|)). That crossing is the endpoint.
    const cx = (r.left + r.right) / 2 - base.left
    const cy = (r.top + r.bottom) / 2 - base.top
    const hw = (r.right - r.left) / 2 || 1
    const hh = (r.bottom - r.top) / 2 || 1
    const vx = x1 - cx
    const vy = y1 - cy
    const s = Math.min(hw / (Math.abs(vx) || 1e-6), hh / (Math.abs(vy) || 1e-6))
    const x2 = cx + vx * s
    const y2 = cy + vy * s
    // Bow the thread; the control point stays on the source side (outside the
    // box), so the curve approaches the border from outside and never dips in.
    const mx = (x1 + x2) / 2
    const my = (y1 + y2) / 2 - 20
    p.setAttribute('d', `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`)
  }
}

// The words are part of the scene: anchored or resting, they track the board
// every frame (pan / zoom / drag / growing text). Two or three rect reads and
// a handful of style writes per frame — the bottom guard writes only when its
// numbers actually change — negligible, and entirely off the reactive path.
let raf = 0
function loop() { place(); raf = requestAnimationFrame(loop) }
function startLoop() { if (!raf) raf = requestAnimationFrame(loop) }
function stopLoop() { if (raf) { cancelAnimationFrame(raf); raf = 0 } }
watch([said, answer], () => {
  place()
  // The human answers while the turn stands, and renderSentences does not run
  // for that — it watches the said line, not the answer. Without this the pair
  // would fade out missing the half the human wrote.
  if (standing && said.value && standing.id === said.value.id) {
    standing.answer = answer.value ? answer.value.text : null
    standing.answerAbove = answerAbove.value
  }
}, { flush: 'post' })

onMounted(() => {
  window.addEventListener('resize', place)
  place()
  startLoop()
  // A turn can already stand at mount (restored history): the watcher only
  // fires on change, so the first render is asked for here.
  renderSentences()
})
onUnmounted(() => {
  window.removeEventListener('resize', place)
  stopLoop()
  stopQuiet()
  if (leaveTimer) { clearTimeout(leaveTimer); leaveTimer = null }
})
</script>

<style scoped>
.resona-voice {
  position: relative; width: 100%; height: 100%;
  flex: 1 1 auto; min-height: 0;
  display: flex; flex-direction: column; justify-content: flex-end;
  background: transparent; color: #ece3d2;
}

/* ---- Faden ---- */
.faden-layer { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; z-index: 1; }
.faden { fill: none; stroke: rgba(255, 179, 0, 0.42); stroke-width: 1; stroke-dasharray: 3 4; }

/* ---- The active turn: stands at its object or its board spot ---- */
.turn {
  position: absolute; z-index: 2;
  /* Unanchored, the exchange stands in the MIDDLE of the surface: the two
     sides run under each other in one column, the agent's words pulled to its
     right edge and the human's line to its left. That opposition is only
     legible in a column that has a middle — pushed against the left of the
     screen, a right-aligned line means nothing. The spot the parent passes is
     already the centred top left (see place()); this is the no-spot fallback
     and centres the same way. */
  /* The three the turn gives up, in this order, when a reply is longer than
     the room over the open line: first the column widens, then the air between
     the sentences closes, then the leading narrows. Written by fitToRoom();
     the values here are the platform's own setting, which is what a reply that
     fits keeps. Type size is NOT among them — a workshop reads this from a
     distance, and the smaller it gets the less it is read at all. */
  --voice-wide: 1;
  --voice-air: 0.55em;
  --voice-lead: 1.6;
  --voice-col: min(calc(min(56ch, 40vw) * var(--voice-wide)), 74vw);
  left: calc((100% - var(--voice-col)) / 2);
  /* Only the frame before the first measurement uses this: place() writes the
     height in pixels, from where the OPEN LINE has to stand. */
  top: 40%;
  width: var(--voice-col);
  pointer-events: none;
  transform: scale(v-bind(zoom));
  transform-origin: top left;
}

/* ---- The ground the words are read on ----
   The board underneath carries cards, and one that comes to lie behind the turn
   takes the line with it — the human's own line above all, which is white on
   whatever happens to be there. What stands behind the block is a haze and not
   a card: it darkens and blurs the board and is masked away towards its own
   border, so there is a ground to read on and no frame around the words. The
   turn keeps standing ON the surface. */
.turn::before {
  content: '';
  position: absolute;
  inset: -1.5rem -1.9rem -1.2rem;
  z-index: -1;
  border-radius: 1.75rem;
  /* The board's OWN ground, not a panel: over the empty surface the plate is
     the colour that is already there and cannot be seen at all, and over a
     card it pulls the card back towards that ground. A panel tone would be
     lighter than the board and would stand there as a rectangle in mid-air
     whenever nothing lay behind the words. */
  background: rgb(var(--bg-base-rgb) / 0.62);
  -webkit-backdrop-filter: blur(14px) saturate(0.9);
  backdrop-filter: blur(14px) saturate(0.9);
  -webkit-mask-image: radial-gradient(115% 115% at 50% 50%, #000 52%, transparent 100%);
  mask-image: radial-gradient(115% 115% at 50% 50%, #000 52%, transparent 100%);
  pointer-events: none;
}
/* Standing at an object, the turn is placed in pixels by place() and keeps the
   board's scale from its top left — it belongs to the thing, not to the middle. */
.turn.anchored { width: min(40ch, 30vw); }
/* A row of chips is not a paragraph, and the human's own line beneath it is
   short. Keeping the paragraph's width here left them clinging to the corner of
   an invisible 40vw box. */
.turn.voice-only { width: min(30ch, 24vw); left: calc((100% - min(30ch, 24vw)) / 2); }
.turn.voice-only .turn-answer { margin-top: 0.9rem; padding-left: 0; }
.turn-body { animation: turnfade 0.55s ease both; }
@keyframes turnfade { from { opacity: 0; } to { opacity: 1; } }

/* The dialogue's two sides, set to opposite edges of the block the turn stands
   in: the agent's words right, the human's line left. Which side a line is on
   is the second thing that says who wrote it — the first is its colour (see
   @/assets/voiceText.css). Aligned inside the block, never against the screen:
   the turn stands at the object it speaks about. */
/* ONE right edge for everything the agent says. The sentences used to step in
   from it, one indent per sentence — a descending staircase, which was a form
   for a left-set block and, mirrored, gave every sentence its own right edge:
   the block read as ragged on both sides, which is not flush right at all. */
.turn-said { text-align: right; }

/* The pair the arriving turn replaced, fading off in place. Absolute, so what
   is going never pushes what is coming. */
.turn-leaving {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  animation: turnleave 0.62s ease forwards;
  pointer-events: none;
}
@keyframes turnleave { from { opacity: 1; } to { opacity: 0; } }

/* Bedenkzeit. While `speak` is 'listening' the finished exchange breathes:
   heard, and something forming — so the surface reads as alive, not hung.
   Carried by the standing words, per this component's own rule (ambient
   status is the words + the acoustic voice, never a chrome dot). No caret
   here on purpose: a caret would mime someone typing, and the call is
   remote anyway — there is nothing being typed. */
@keyframes resona-listen { from { opacity: 1; } to { opacity: 0.5; } }
.turn.listening .turn-body {
  animation: resona-listen 2.6s ease-in-out infinite alternate;
}
@media (prefers-reduced-motion: reduce) {
  .turn.listening .turn-body { animation: none; opacity: 0.75; }
}
/* How Resona's words READ is the shared voice's business
   (@/assets/voiceText.css) — nothing about their typography may be set here,
   or this surface would drift away from the platform's own voice again. What
   stays is the air between the sentences of one turn. The sentence nodes are
   built imperatively and carry no scope attribute, so :deep() is what reaches
   them. */
/* The cap itself is written per frame by capStack(); the clipping it needs is
   a constant and belongs here. */
.sent-stack { word-break: break-word; overflow: hidden; }
.sent-stack :deep(.voice-sent) { margin-bottom: var(--voice-air, 0.55em); }
/* The human's own line: white, and flush left. White because it is the one
   writing on this surface that belongs to no agent — every agent carries the
   pigment of the page it stands on, and the human is told apart from all of
   them by carrying none. */
/* Standing above the words it brought about, the line needs its air below it,
   not over it. */
.turn-answer.above { margin-top: 0; margin-bottom: 0.7rem; }
.turn-answer {
  margin-top: 0.7rem; padding-left: 0;
  text-align: left;
  font-size: 1rem; line-height: 1.55; color: #ffffff;
  word-break: break-word;
  animation: turnfade 0.5s ease both;
}
/* A line just written settles from the size it was written at down to the size
   it is read at. It scales from its own left top, so it keeps the edge it was
   written against and comes to rest exactly where it will stand. This is the
   whole of what the surface gives back for the writing, and it happens before
   any answer exists. */
@keyframes answersettle {
  from { transform: scale(2); opacity: 0; }
  35% { opacity: 1; }
  to { transform: scale(1); opacity: 1; }
}
.turn-answer.settling {
  transform-origin: left top;
  animation: answersettle 0.56s cubic-bezier(0.22, 0.75, 0.3, 1) both;
}
@media (prefers-reduced-motion: reduce) {
  .turn-answer.settling { animation: turnfade 0.5s ease both; }
}

/* ---- Voice only: what is left to DO with a line that is only heard ----
   No shape: the page's one mask is its presence (see the note at the top of
   this file). Just the two chips, on the row where the circle used to stand.
   Both carry their own state, so nothing here animates. */
/* The chips stand where the agent's words would: at the right edge. */
.turn-voice-only { display: flex; align-items: center; justify-content: flex-end; gap: 0.9rem; }
/* The lift button takes the pointer while the rest of the turn stays
   click-through, so it carries its own quiet state instead of waiting for a
   hover over something larger. */
.lift-quiet { opacity: 0.4; transition: opacity 0.2s ease; }
.lift-quiet:hover { opacity: 1; }

/* The turn is click-through so the board underneath still pans; every control
   inside it has to take the pointer back explicitly. The speaker lives in
   SpeakButton.vue and knew nothing about that, so it rendered and did nothing. */
:deep(.speak-btn) {
  pointer-events: auto;
}

.lift-btn {
  pointer-events: auto;
  display: inline-flex; align-items: center; margin-left: 0.6rem;
  padding: 0.1rem 0.6rem; border: 1px solid rgba(255, 179, 0, 0.28);
  border-radius: 999px; background: transparent; color: rgba(255, 179, 0, 0.82);
  font-family: var(--font-sans, system-ui); font-size: 0.72rem; cursor: pointer;
  transition: background 0.15s ease; vertical-align: middle;
}
.lift-btn:hover { background: rgba(255, 179, 0, 0.09); }

/* ---- Sprechzeile ---- */
/* The open line. No border, no bar, no field: what is being written looks like
   what has been written, because it is the same line one moment earlier. It is
   the one part of the turn that takes the pointer. */
.turn-writing {
  margin-top: 0.7rem;
  text-align: left;
  pointer-events: auto;
  position: relative;
}
/* The caret of an untouched line. It stands where the first character will
   stand — at the left edge, on the first line, in the size that line is
   written at — and in the colour the browser's own caret has there
   (caret-color on .write-line), so the one takes over from the other without
   moving or changing. It never takes a click: the line under it does. */
.write-caret {
  position: absolute;
  left: 0;
  top: 0.3rem;
  width: 2px;
  height: 2rem;
  background: #ffb300;
  pointer-events: none;
  animation: write-caret-blink 1.06s step-end infinite;
}
@keyframes write-caret-blink {
  0%, 50% { opacity: 1; }
  50.01%, 100% { opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .write-caret { animation: none; opacity: 1; }
}
</style>
