<!--
  PlatformVoice — the platform speaking LIVE on a real page.

  Not a study, not a staged demo: it asks the real /api/chat endpoint (general
  mode, neutral system prompt) with the page's real draft_context
  (pageContextStore.formatForLLM — same field ChatOverlay sends), and the real
  reply appears as distributed standing text over the real page. No chat box.

  Register: this is the PLATFORM voice — the milieu
  articulating itself — not Träshy/Resona/Persona. Its grounding is form, not
  capability limits: every utterance has a visible origin (the one mask +
  thread) and is always written (audio, when it comes, may never appear without
  this text).

  THE ORIGIN IS NOT DRAWN HERE. A page carries exactly one mask, it stands in
  the app-level overlay (ChatOverlay), and this voice speaks FROM it: the
  threads leave its centre and the asking place opens beside it. This component
  therefore draws no presence of its own — a second one would be a second agent
  on the page — and finds the mask by a document-level query, since it is not in
  this component's tree. Where there is no mask there is no thread: pointing
  from nowhere is worse than not pointing.

  Live v1 mechanics, deliberately simple and honest:
    - Presence (carrier 4): the page is never dimmed — the voice adds, it does
      not take away. Sentences stand on the page's own ground: docked directly
      below the element they speak about — above it when that element sits at
      the bottom edge of the viewport — or descending the left column beside
      the page's own content, never under it and never overlapping each other
      (greedy push-down). The user's first interaction with the page settles
      the turn: the words LEAVE, threads with them.
    - Aboutness: a sentence docks onto the first registered anchor whose
      match words appear in it (word-boundary match; anchor = a real page
      element passed by the host view as {id, selector, words}); everything
      else descends the left column — the page's own reading direction. This
      is a first solver, not the perceptual placement engine — per-view zones
      and learned speaking places come with selection.
    - Max 4 sentence places per turn (peripheral vision does not read);
      longer replies merge their tail into the last place.
    - Entrance: rubber-band per grapheme; ar/he locales and reduced-motion
      get whole-sentence fades (per-character spans break Arabic shaping).

  A host may also hand this voice WORDS instead of a question (see
  PlatformVoiceHandle below): what a page says about itself is authored text and
  is put up exactly as written. That path stops short of send() and therefore of
  /api/chat, so nothing about it can be paraphrased — and speak() builds DOM and
  nothing else, so nothing about it can sound.

  The utterance DOM is imperative (off Vue's reactive path), like ResonaVoice,
  and it is built by the shared voice engine (@/lib/voiceText): how the words
  read and arrive belongs to the voice wherever it speaks, where they stand
  belongs to this component. The text treatment is therefore styled unscoped
  (@/assets/voiceText.css), and the scoped rules here reach the imperative DOM
  via :deep() for placement alone. The ack highlight lands on elements the host
  view owns, so that one class is styled unscoped too (.pvl-live-ack).
-->
<template>
  <div ref="rootEl" class="pvl-layer" aria-live="polite">
    <svg ref="threadsEl" class="pvl-threads" aria-hidden="true"></svg>
    <div ref="voiceEl" class="pvl-voice"></div>
    <!-- The asking place, at the mask. Teleported to the body because it is
         positioned against a FIXED element and must not be clipped or
         re-anchored by whatever the host page transforms; placed each frame by
         placeAsk() while it is open, so it follows the mask when the mask is
         dragged. -->
    <Teleport to="body">
      <div v-if="asking || waiting" ref="askEl" class="pvl-ask" :style="askStyle">
        <form v-if="asking" class="pvl-askform" @submit.prevent="send">
          <input
            ref="inputEl"
            v-model="question"
            class="pvl-input"
            :placeholder="t('platformVoice.placeholder')"
            :aria-label="t('platformVoice.askTitle')"
            @keydown.enter.prevent="send"
            @keydown.esc="presence.closeVoiceAsk()"
          />
        </form>
        <span v-else class="pvl-state">{{ t('platformVoice.thinking') }}</span>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { chatTurn } from '@/lib/chatTurn'
import { usePageContextStore } from '@/stores/pageContext'
import { usePageFigureStore } from '@/stores/pageFigure'
import {
  buildVoiceSentence,
  fadeOutVoiceSentence,
  revealVoiceSentence,
  splitVoiceSentences,
  voiceCharMode,
} from '@/lib/voiceText'
import '@/assets/voiceText.css'

export interface VoiceAnchor {
  id: string
  selector: string
  /** Lowercase match words (any language) — aboutness data, not UI copy. */
  words: string[]
}

/**
 * What a host page may reach on this voice.
 *
 * Written out rather than inferred from the component, because it is the only
 * thing a page is allowed to touch here and saying so in one place is what
 * keeps it that way.
 */
export interface PlatformVoiceHandle {
  /** Set these words standing on the page, replacing whatever stands there.
   *  Words, not a question: this is the text path, it asks nothing of any
   *  model and it cannot sound. */
  speak: (text: string, dim?: boolean) => void
  /** Take the standing turn away — words and threads together. For a page that
   *  clears the ground the words were said on: what is left otherwise is a
   *  turn about a scene that is gone. */
  clear: () => void
  /** Whether an answer of this voice's OWN is standing on the page. A page that
   *  puts authored words up reads this first: speak() replaces the standing
   *  turn, and taking away an answer somebody asked for is not a thing to do
   *  behind their back. */
  hasAnswered: boolean
}

const props = defineProps<{ anchors: VoiceAnchor[] }>()

const { t, locale } = useI18n()
const route = useRoute()
const pageContextStore = usePageContextStore()
const presence = usePageFigureStore()

/** The one mask on the page — this voice's origin. Rendered by ChatOverlay from
 *  App.vue, so it is nowhere in this component's tree and is found by attribute
 *  rather than by import. */
const FIGURE_SELECTOR = '[data-figure-corner]'

const rootEl = ref<HTMLElement | null>(null)
const voiceEl = ref<HTMLElement | null>(null)
const threadsEl = ref<SVGSVGElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)
const askEl = ref<HTMLElement | null>(null)

const waiting = ref(false)
const question = ref('')

/** See PlatformVoiceHandle.hasAnswered. Set once and left set: a turn stays
 *  standing until the next one replaces it, so from the first answer onwards
 *  the ground belongs to the conversation. */
const hasAnswered = ref(false)

// The asking place is opened from outside this component — there is no button
// here to open it, because the presence it hung on is gone. It is help's own
// panel that hands a question over to this other mouth (ChatOverlay.askOnPage),
// and the store is the channel. While an answer is on its way the input gives
// way to the waiting line: one question at a time, as before.
const asking = computed(() => presence.voiceAsking && !waiting.value)

const ackedEls: HTMLElement[] = []

watch(asking, (open) => {
  if (!open) return
  question.value = presence.voiceDraft
  nextTick(() => {
    inputEl.value?.focus()
    placeAsk()
  })
})

/**
 * Where the asking place stands: at the mask, and following it.
 *
 * Beside the mask by default, centred on it; under it when there is no room
 * beside; over it when there is no room under either. Clamped into the viewport
 * last, which slides it along the mask and never away from it. Without a mask
 * it falls back to the corner the origin used to occupy, so the capability is
 * never silently unreachable.
 */
const askPos = ref<{ left: number; top: number } | null>(null)
const askStyle = computed(() =>
  askPos.value
    ? { left: `${askPos.value.left}px`, top: `${askPos.value.top}px` }
    : { left: '1rem', top: '0.75rem' },
)

const ASK_GAP = 8
const ASK_MARGIN = 10

function placeAsk(): void {
  const el = askEl.value
  const mask = document.querySelector<HTMLElement>(FIGURE_SELECTOR)
  if (!el || !mask) {
    askPos.value = null
    return
  }
  const m = mask.getBoundingClientRect()
  const w = el.offsetWidth
  const h = el.offsetHeight
  const vw = window.innerWidth
  const vh = window.innerHeight
  let left: number
  let top: number
  if (m.right + ASK_GAP + w <= vw - ASK_MARGIN) {
    left = m.right + ASK_GAP
    top = m.top + (m.height - h) / 2
  } else if (m.bottom + ASK_GAP + h <= vh - ASK_MARGIN) {
    left = m.left
    top = m.bottom + ASK_GAP
  } else if (m.top - ASK_GAP - h >= ASK_MARGIN) {
    left = m.left
    top = m.top - ASK_GAP - h
  } else {
    left = m.left - ASK_GAP - w
    top = m.top + (m.height - h) / 2
  }
  askPos.value = {
    left: Math.round(Math.max(ASK_MARGIN, Math.min(vw - w - ASK_MARGIN, left))),
    top: Math.round(Math.max(ASK_MARGIN, Math.min(vh - h - ASK_MARGIN, top))),
  }
}

// Tracked per frame, and only while it is open: the mask can be dragged under
// it, and its own position transitions over 0.6s afterwards. A watcher on the
// mask's offsets is not available from here — it is another component's box.
let askRaf = 0
function askLoop(): void {
  placeAsk()
  askRaf = requestAnimationFrame(askLoop)
}
watch(
  () => asking.value || waiting.value,
  (open) => {
    if (open && !askRaf) askRaf = requestAnimationFrame(askLoop)
    if (!open && askRaf) {
      cancelAnimationFrame(askRaf)
      askRaf = 0
    }
  },
)

async function send(): Promise<void> {
  // Read the DOM value as fallback: v-model misses value changes that arrive
  // without input events (some automation/assistive input paths).
  const q = (question.value || inputEl.value?.value || '').trim()
  if (!q || waiting.value) return
  presence.closeVoiceAsk()
  question.value = ''
  if (inputEl.value) inputEl.value.value = ''
  waiting.value = true
  // The mask is this voice's origin, so it is also where the wait is shown.
  presence.voiceWaiting = true
  try {
    // The reply stands as distributed sentences on a page that is mostly
    // occupied: length is a spatial constraint, not a style preference.
    const pageCtx = pageContextStore.formatForLLM(route.path)
    const register =
      'Du bist die Stimme der Plattform und sprichst direkt auf der Seite. ' +
      'Antworte in höchstens vier kurzen Sätzen. Keine Listen, kein Markdown, keine Emojis.'
    const data = await chatTurn('/api/chat/stream', {
      message: q,
      draft_context: (pageCtx ? pageCtx + '\n\n' : '') + register,
      language: locale.value,
    })
    speak(String(data.reply ?? ''))
  } catch (e) {
    console.error('[PlatformVoice] /api/chat/stream failed:', e)
    speak(t('platformVoice.error'), true)
  } finally {
    waiting.value = false
    presence.voiceWaiting = false
    // Either branch above has spoken by now — an answer or the line that says
    // none arrived. Both are this voice's own and both hold the ground.
    hasAnswered.value = true
  }
}

// Stem match with a LEFT word boundary: anchor words are stems ("generier",
// "verwandl") so one token covers German inflection; the left boundary keeps
// plain includes() failures out ("wie" no longer docks onto "sowie").
function wordHit(sentence: string, w: string): boolean {
  const esc = w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  try {
    return new RegExp('(^|\\P{L})' + esc, 'iu').test(sentence)
  } catch {
    return sentence.toLowerCase().includes(w)
  }
}

function anchorFor(sentence: string, used: Set<string>): { el: HTMLElement; id: string } | null {
  for (const a of props.anchors) {
    if (used.has(a.id)) continue
    if (!a.words.some((w) => wordHit(sentence, w))) continue
    const host = rootEl.value?.parentElement
    const el = host?.querySelector<HTMLElement>(a.selector)
    if (el) return { el, id: a.id }
  }
  return null
}

type Placed = { l: number; t: number; w: number; h: number }
/** Where a sentence would be put — before it has been measured or settled. */
type Geom = { l: number; t: number; w: number }

function intersects(a: Placed, b: Placed): boolean {
  return a.l < b.l + b.w && b.l < a.l + a.w && a.t < b.t + b.h && b.t < a.t + a.h
}

/* THE THREADS ARE NOT DRAWN. The dotted curves running across the surface to
   the mask are off. Everything that draws them stays exactly where it is — the
   geometry, the mask-wipe, the reveal — and this one switch decides whether it
   runs. Nothing here is to be deleted. */
const THREADS_DRAWN = false

const SVG_NS = 'http://www.w3.org/2000/svg'
/** Clearance between the mask's own edge and where its thread begins. */
const FIGURE_CLEARANCE = 7
let threadSeq = 0

/** A point on a quadratic Bezier. Needed twice: to find where the thread leaves
 *  the mask, and to cut the curve so that it BEGINS there. */
function quadAt(
  x0: number, y0: number,
  cx: number, cy: number,
  x1: number, y1: number,
  t: number,
): { x: number; y: number } {
  const m = 1 - t
  return {
    x: m * m * x0 + 2 * m * t * cx + t * t * x1,
    y: m * m * y0 + 2 * m * t * cy + t * t * y1,
  }
}

function drawThread(d: HTMLElement, si: number): void {
  const layer = threadsEl.value
  const root = rootEl.value
  // The one mask is the origin, and it lives outside this component's root —
  // hence the document-level query. Its rect is taken from the bounding rect,
  // so a fixed element converts into layer coordinates like any other.
  const orig = document.querySelector(FIGURE_SELECTOR)
  if (!layer || !root || !orig) return
  const rr = root.getBoundingClientRect()
  const or = orig.getBoundingClientRect()
  const dr = d.getBoundingClientRect()
  // The curve is CONSTRUCTED from the mask's centre — that is what it points
  // from — and then cut back to the mask's edge. What gets drawn therefore
  // starts at the figure's rim, never inside the figure it leaves.
  const x1 = or.left - rr.left + or.width / 2
  const y1 = or.top - rr.top + or.height / 2
  const x2 = dr.left - rr.left - 6
  const y2 = dr.top - rr.top + 14
  // The bow stands perpendicular to the run and scales with it; the sentences
  // of one turn bow to alternating sides. A control point held a fixed height
  // ABOVE the two ends flattens into a ruled line the moment the page is wide.
  const dx = x2 - x1
  const dy = y2 - y1
  const run = Math.hypot(dx, dy) || 1
  const bow = Math.min(run * 0.13, 110) * (si % 2 === 0 ? -1 : 1)
  const mx = (x1 + x2) / 2 - (dy / run) * bow
  const my = (y1 + y2) / 2 + (dx / run) * bow
  // Where the curve crosses the mask's edge is decided by the curve's own
  // shape, so it is searched on the curve. A straight line from centre to word
  // would cut the wrong point on every thread that is not itself straight.
  const bl = or.left - rr.left - FIGURE_CLEARANCE
  const br = or.right - rr.left + FIGURE_CLEARANCE
  const bt = or.top - rr.top - FIGURE_CLEARANCE
  const bb = or.bottom - rr.top + FIGURE_CLEARANCE
  const inFigure = (p: { x: number; y: number }): boolean =>
    p.x >= bl && p.x <= br && p.y >= bt && p.y <= bb
  // Words standing on the mask itself leave nothing to draw — and drawing it
  // anyway is exactly the thread-out-of-the-middle this cut exists to stop.
  if (inFigure({ x: x2, y: y2 })) return
  let lo = 0
  let hi = 1
  for (let i = 0; i < 22; i++) {
    const mid = (lo + hi) / 2
    if (inFigure(quadAt(x1, y1, mx, my, x2, y2, mid))) lo = mid
    else hi = mid
  }
  const s = quadAt(x1, y1, mx, my, x2, y2, hi)
  // De Casteljau: the tail [hi, 1] of a quadratic is itself a quadratic, with
  // this control point. The curve is re-cut, not merely begun later — so the
  // piece that is drawn is the same curve, minus the piece inside the mask.
  const ccx = (1 - hi) * mx + hi * x2
  const ccy = (1 - hi) * my + hi * y2
  const dAttr = `M${s.x},${s.y} Q${ccx},${ccy} ${x2},${y2}`

  // Dotted AND drawn on. One dash pattern cannot do both — the dots are the
  // line's own pattern — so the arrival is carried by a mask that uncovers
  // them. The movement runs while the sentence arrives and then stops: it says
  // the machine is working, and afterwards nothing is working.
  const id = `pvl-thread-${++threadSeq}`
  const mask = document.createElementNS(SVG_NS, 'mask')
  mask.setAttribute('id', id)
  mask.setAttribute('maskUnits', 'userSpaceOnUse')
  const wipe = document.createElementNS(SVG_NS, 'path')
  wipe.setAttribute('d', dAttr)
  // Inline, because the layer's own rule would otherwise reach this path too —
  // and its white, its width and its full opacity are what makes the mask
  // uncover anything at all.
  wipe.style.fill = 'none'
  wipe.style.stroke = '#fff'
  wipe.style.strokeWidth = '6'
  wipe.style.strokeLinecap = 'round'
  wipe.style.opacity = '1'
  mask.appendChild(wipe)
  const p = document.createElementNS(SVG_NS, 'path')
  p.setAttribute('class', 'pvl-thread')
  p.setAttribute('d', dAttr)
  p.setAttribute('mask', `url(#${id})`)
  layer.appendChild(mask)
  layer.appendChild(p)
  // Measured, never assumed. A dash length shorter than the thread does not
  // shorten the reveal — it cuts holes into everything beyond it, which is
  // what a fixed 600 did to every thread longer than 600px.
  const len = p.getTotalLength()
  wipe.style.strokeDasharray = String(len)
  wipe.style.strokeDashoffset = String(len)
  wipe.style.transition = `stroke-dashoffset 1.1s ease ${140 + si * 420}ms`
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      wipe.style.strokeDashoffset = '0'
    }),
  )
}

// Everything this voice put on the page goes. Called by a host that takes the
// ground away under it (the workshop's "new dialog" empties the board): the
// words were said about that scene, and they have nothing left to stand on once
// it is gone.
function clear(): void {
  const voice = voiceEl.value
  const layer = threadsEl.value
  clearAcks()
  if (layer) layer.innerHTML = ''
  if (voice) voice.querySelectorAll<HTMLElement>('.pvl-sent').forEach((n) => fadeOutVoiceSentence(n))
  hasAnswered.value = false
}

function clearAcks(): void {
  ackedEls.splice(0).forEach((el) => el.classList.remove('pvl-live-ack'))
}

// The turn is over when the user acts on the page: the words LEAVE, threads
// with them. They once sank to a quarter and stood on as a ghost — a second,
// dimmer text under the one turn the surface ever shows, which is a reading
// cost with nothing to buy for it. The dimming is superfluous since only one
// turn is ever seen; clicking on an empty spot fades the answer out.
function settle(): void {
  const voice = voiceEl.value
  const layer = threadsEl.value
  if (!voice || !layer) return
  voice.querySelectorAll<HTMLElement>('.pvl-sent').forEach((n) => fadeOutVoiceSentence(n))
  layer.innerHTML = ''
  clearAcks()
}

function speak(text: string, dim = false): void {
  const voice = voiceEl.value
  const layer = threadsEl.value
  const root = rootEl.value
  if (!voice || !layer || !root) return

  let sentences = splitVoiceSentences(text, String(locale.value || 'en'))
  if (!sentences.length) return
  const tailMerged = sentences.length > 4
  if (tailMerged) {
    sentences = [...sentences.slice(0, 3), sentences.slice(3).join(' ')]
  }

  // Speaking replaces: placement is deterministic, so anything left standing
  // would sit at the same coordinates as the new turn — text printed into
  // text. The previous turn fades out and leaves entirely. Nothing is replaced
  // before there is speech to replace it with, so the guard above comes first.
  voice.querySelectorAll<HTMLElement>('.pvl-sent').forEach((n) => fadeOutVoiceSentence(n))
  clearAcks()
  layer.innerHTML = ''

  const rr = root.getBoundingClientRect()
  // Free sentences begin under the origin — the one mask, wherever the human
  // has put it. Only while it stands in the upper third: dragged lower, taking
  // its bottom edge would start the column halfway down the page and push the
  // turn off the bottom, so there the column starts at the top instead.
  const origRect = document.querySelector(FIGURE_SELECTOR)?.getBoundingClientRect()
  const origBottom = origRect ? origRect.bottom - rr.top : 0
  const baseTop = origBottom > 0 && origBottom < rr.height / 3 ? origBottom + 28 : 72
  const used = new Set<string>()
  // THE COLUMN THIS PAGE IS READ IN. What the page says about itself is set in
  // it, like everything else on the surface — measured off the exchange where
  // one stands, so the two share an edge. (Each sentence once began a little
  // further right and lower than the one before; that stair offset is gone and
  // the text stands in the central column.)
  const turnRect = document.querySelector('.turn')?.getBoundingClientRect()
  // WIDER THAN THE EXCHANGE, AND READ TIGHTER (the leading is set on .pvl-sent
  // below). An address is four or five sentences that have to stand COMPLETE
  // above the open line; a turn may take the whole surface. Set in the
  // exchange's own measure the address ran to twice the height there is room
  // for and printed its last paragraph into the write line; so the column is
  // wider and the leading smaller.
  const columnWidth = Math.max(320, Math.min(760, Math.round(rr.width - 48)))
  // It BEGINS on the exchange's edge where there is room for that, so both are
  // read on one axis. Where the wider column would run off the right edge —
  // and wrap to one word a line — there is no shared edge left to keep, and it
  // is centred instead: pulled just far enough left it would sit hard against
  // the right edge with the whole left of the surface empty.
  const columnStart =
    turnRect && turnRect.width > 120
      ? Math.round(turnRect.left - rr.left)
      : Math.round((rr.width - Math.min(560, rr.width * 0.4)) / 2)
  const columnLeft =
    columnStart + columnWidth + 16 <= rr.width
      ? columnStart
      : Math.max(16, Math.round((rr.width - columnWidth) / 2))
  const placedRects: Placed[] = []
  const toThread: HTMLElement[] = []
  let freeSlot = 0

  // The page's own content, in layer coordinates: EVERY descendant of the
  // host, minus this component's own layer (the voice must not measure
  // itself). Real content sits arbitrarily deep — a card inside a pannable
  // table, an orb inside a nested component — so a depth-limited scan reports
  // free space where the page is solid. Full-page wrappers are dropped:
  // counting them as occupied would leave no free space anywhere.
  const occupied: Placed[] = []
  const host = root.parentElement
  if (host) {
    // Speech must not wait on measurement: a pathological page (thousands of
    // sized nodes) stops contributing rects here rather than stalling.
    const maxOccupied = 600
    for (const el of Array.from(host.querySelectorAll('*'))) {
      if (el.closest('.pvl-layer')) continue
      const b = el.getBoundingClientRect()
      if (b.width <= 60) continue
      // Wide, short bars (a write line, a journal strip) are instruments even
      // under the 40px floor — a sentence standing on them covers what the
      // user needs. Hairline dividers stay ignorable.
      if (b.height <= 40 && (b.width < rr.width * 0.5 || b.height <= 12)) continue
      if (b.width > rr.width * 0.9 && b.height > rr.height * 0.9) continue
      occupied.push({ l: b.left - rr.left, t: b.top - rr.top, w: b.width, h: b.height })
      if (occupied.length >= maxOccupied) break
    }
    // Everything the host NAMED as an anchor is occupied, whatever its size.
    // The page handed those elements over as the things this voice points at,
    // so standing on one covers the very thing being spoken about. The open
    // line is one of them, and in a narrow window it is neither tall enough nor
    // wide enough to pass the generic filter above.
    for (const a of props.anchors) {
      const el = host.querySelector<HTMLElement>(a.selector)
      if (!el) continue
      const b = el.getBoundingClientRect()
      if (b.width <= 0 || b.height <= 0) continue
      occupied.push({ l: b.left - rr.left, t: b.top - rr.top, w: b.width, h: b.height })
    }
  }

  // HOW MUCH ROOM THE ADDRESS HAS. From where it starts down to the first thing
  // on the page that stands in its column — the open line, as a rule. Below
  // that there is nothing to be gained: a sentence put there is either printed
  // into an instrument or faded out above it.
  // One number decides both whether the address fits and whether its foot is
  // faded out: with two, a block can clear the open line by four pixels and
  // still be faded for it.
  const FIT_SLACK = 6
  // The air between two blocks, set with the leading by the cascade below.
  let blockGap = 14
  let roomBottom = rr.height - 24
  for (const o of occupied) {
    if (o.t <= baseTop + 40 || o.t >= roomBottom) continue
    if (o.h >= rr.height * 0.7) continue
    const overlap = Math.min(o.l + o.w, columnLeft + columnWidth) - Math.max(o.l, columnLeft)
    if (overlap >= Math.min(120, columnWidth * 0.5)) roomBottom = o.t
  }

  // Set geometry at (l, t, maxWidth), measure, then push down until clear of
  // other sentences — WITHOUT claiming the ground: placedRects is untouched,
  // so a caller may look at where this would land and try elsewhere instead.
  // Called again with the same arguments and an unchanged placedRects, it
  // returns the same rect and leaves the element in the same state.
  function settleAt(d: HTMLElement, l: number, tTop: number, w: number): Placed {
    d.style.left = l + 'px'
    d.style.maxWidth = w + 'px'
    d.style.top = tTop + 'px'
    const r: Placed = { l, t: tTop, w: d.offsetWidth, h: d.offsetHeight }
    let guard = 0
    while (placedRects.some((p) => intersects(r, p)) && guard++ < 40) {
      const blocker = placedRects
        .filter((p) => intersects(r, p))
        .sort((a, b) => a.t - b.t)[0]
      if (!blocker) break
      r.t = blocker.t + blocker.h + blockGap
      d.style.top = r.t + 'px'
      r.h = d.offsetHeight
    }
    return r
  }

  // Place at (l, t, maxWidth), push down until clear of other sentences, and
  // keep the ground.
  function place(d: HTMLElement, l: number, tTop: number, w: number): void {
    placedRects.push(settleAt(d, l, tTop, w))
  }

  // A rect that begins at or left of l and still runs past the start area of a
  // sentence standing there covers the very point that sentence begins at — a
  // bottom bar, a card, a node column. Page-tall columns are exempt: a
  // full-height layout wrapper starting at the left edge would otherwise block
  // every band, while the content that genuinely occupies space inside it is
  // measured as its own child rects.
  function startsOnContent(l: number, top: number, h: number): boolean {
    const bottom = top + h
    for (const o of occupied) {
      if (o.t >= bottom || o.t + o.h <= top) continue
      if (o.l > l) continue
      if (o.h >= rr.height * 0.7) continue
      if (o.l + o.w > l + 40) return true
    }
    return false
  }

  // Width actually free to the right of x in the band a sentence would occupy
  // (120px is a deliberate over-estimate of one sentence's height). Measured
  // against page content, so a free sentence never runs under a card or a
  // node column.
  function freeWidthAt(x: number, yStart: number): number {
    const yEnd = yStart + 120
    // A band whose start point lies ON page content is not free at any width:
    // measuring outwards from a covered point reports room that does not exist.
    if (startsOnContent(x, yStart, 120)) return 0
    let nearest = Number.POSITIVE_INFINITY
    for (const o of occupied) {
      if (o.l <= x) continue
      if (o.t >= yEnd || o.t + o.h <= yStart) continue
      if (o.l < nearest) nearest = o.l
    }
    // Nothing to the right in this band: the sentence may use the layer.
    if (nearest === Number.POSITIVE_INFINITY) return Math.floor(rr.width - x - 24)
    return Math.floor(nearest - x - 16)
  }

  // Push-down knows only about other sentences, so where it stops says nothing
  // about the page: a sentence can be pushed onto a full-width bar or past the
  // bottom edge, where it is cut off. A landing is clear only when NO page
  // content intersects the sentence's whole rect — the start-edge test of the
  // band phase is not enough here, a bar beginning a few px right of the
  // column start still lies under the sentence. Page-tall wrappers stay
  // exempt; the last 60px belong to the page's own bottom bars.
  function landsClear(r: Placed): boolean {
    if (r.t + r.h > rr.height - 60) return false
    return !occupied.some((o) => o.h < rr.height * 0.7 && intersects(r, o))
  }

  // The band a free sentence would take in the column at cx: from yStart down,
  // the first band whose start point is on free ground and wide enough to read.
  function columnGeom(cx: number, yStart: number): Geom {
    let y = yStart
    let free = freeWidthAt(cx, y)
    if (free < 220) {
      const lastBand = rr.height - 160
      for (let probe = yStart + 40; probe <= lastBand; probe += 40) {
        const fw = freeWidthAt(cx, probe)
        if (fw >= 220) {
          y = probe
          free = fw
          break
        }
      }
    }
    // No band is wide enough: stay put and stay readable — overlapping the
    // page is better than a column too narrow to be a sentence.
    const w =
      free >= 220
        ? Math.min(columnWidth, free)
        : Math.min(columnWidth, Math.max(220, Math.floor(rr.width - cx - 24)))
    return { l: cx, t: y, w }
  }

  // A sentence's height is only known once it has its final width, so measure
  // it off-screen before the top of an above-dock can be computed.
  function topAbove(d: HTMLElement, l: number, w: number, anchorTop: number): number {
    d.style.left = l + 'px'
    d.style.maxWidth = w + 'px'
    d.style.top = '-9999px'
    // Bars stacked directly above the anchor (a journal strip over the write
    // line) belong to the same instrument: the dock stands above them all.
    let effTop = anchorTop
    for (let pass = 0; pass < 3; pass++) {
      let moved = false
      for (const o of occupied) {
        if (o.h < rr.height * 0.7 && o.w >= rr.width * 0.5 && o.t < effTop && o.t + o.h > effTop - 48) {
          effTop = o.t
          moved = true
        }
      }
      if (!moved) break
    }
    return Math.max(8, effTop - d.offsetHeight - 12)
  }

  // One decision for the whole turn: the sentences of an utterance arrive in
  // the same way, and nothing between build and reveal can change it anyway.
  const charMode = voiceCharMode(String(locale.value || ''))

  // THE ADDRESS FITS ITSELF INTO THAT ROOM. Set at the leading the platform
  // reads at, four or five sentences run past the open line on a narrow window
  // and the last of them is faded out above it — a page's address losing its
  // last paragraph is the one thing it cannot afford. So the same cascade the
  // exchange uses (ResonaVoice, --voice-lead): the whole turn is laid out, and
  // where its foot passes the room, it is laid out again a step tighter --
  // the leading and the air between the blocks together, so neither has to
  // carry the whole saving alone. 1.35 is the engine's floor; below it this
  // size stops reading.
  const RUNGS = [
    { lead: 1.42, gap: 14 },
    { lead: 1.38, gap: 11 },
    { lead: 1.35, gap: 8 },
  ]
  let laid: HTMLElement[] = []
  for (let li = 0; li < RUNGS.length; li++) {
    laid.forEach((e) => e.remove())
    laid = []
    placedRects.length = 0
    toThread.length = 0
    used.clear()
    freeSlot = 0
    clearAcks()
    const rung = RUNGS[li]!
    blockGap = rung.gap
    voice.style.setProperty('--voice-lead', String(rung.lead))
    sentences.forEach((s, si) => {
      const d = buildVoiceSentence(s, { dim, charMode, extraClass: 'pvl-sent' })
      // A merged tail is several sentences in one block: it is not about one
      // element, so any anchor word it contains is incidental. Docked into a
      // narrow channel such a block becomes a text wall taller than the viewport,
      // so it never docks — it takes the free-column path.
      const hit = tailMerged && si === sentences.length - 1 ? null : anchorFor(s, used)
      voice.appendChild(d)
      laid.push(d)
      if (hit) {
        used.add(hit.id)
        const ar = hit.el.getBoundingClientRect()
        const al = ar.left - rr.left
        const at = ar.top - rr.top
        // The sentence stands directly BELOW what it speaks about, left-aligned
        // with it — never over the anchor itself. An anchor at the bottom edge
        // has no room below it (140px of sentence, 70px of bottom-bar zone):
        // there the sentence stands ABOVE, or it would be cut off / covered.
        const dw = Math.min(460, Math.max(240, ar.width - 16))
        // The sentence must fit inside the layer: at an anchor near the right
        // edge, left-aligning with it would push the text past the edge, where
        // it wraps to one word per line and is clipped. Pulled left, the anchor
        // glow and the thread still carry the pointing.
        const dl = Math.max(8, Math.min(al + 8, rr.width - dw - 16))
        const dockAbove = ar.bottom + 140 > window.innerHeight - 70
        const dt = dockAbove ? topAbove(d, dl, dw, at) : at + ar.height + 12
        place(d, dl, dt, dw)
        d.classList.add('docked')
        hit.el.classList.add('pvl-live-ack')
        ackedEls.push(hit.el)
      } else {
        // Every sentence of the turn starts on the SAME edge and is offered the
        // same top; push-down is what sets them under one another. The column is
        // only as wide as the page leaves it: where content blocks the band, the
        // sentence steps down to the first band wide enough to read (220px),
        // rather than running under that content.
        const x = columnLeft
        const yStart = baseTop
        // One column does not hold a whole turn. With sentences already standing
        // in it, push-down carries the next one down over the page's own bottom
        // bar and off the layer while the middle of the page stands empty — so
        // the column moves right instead. The step has to clear a whole sentence
        // (220px is the narrowest column this code still calls one) plus a
        // gutter, or the retry stands inside the first column's text rather than
        // beside it. Every candidate keeps a readable column inside the layer.
        const maxLeft = Math.max(0, Math.floor(rr.width - 220))
        const columns: number[] = []
        for (const raw of [x]) {
          const cx = Math.min(raw, maxLeft)
          if (!columns.includes(cx)) columns.push(cx)
        }
        const geoms = columns.map((cx) => columnGeom(cx, yStart))
        let landed = false
        for (const g of geoms) {
          const r = settleAt(d, g.l, g.t, g.w)
          if (landsClear(r)) {
            placedRects.push(r)
            landed = true
            break
          }
        }
        // No column lands clear: the page is full and standing over content is
        // the last resort. But a wide instrument bar (write line) and the layer
        // edge stay inviolable — the column with the least overflow past them
        // wins (score ties keep the first candidate, so the same page still
        // speaks in the same place), and what does not fit fades out above the
        // bar instead of covering it.
        const g0 = geoms[0]
        if (!landed && g0) {
          const cutFor = (r: Placed): number => {
            let cut = rr.height - 24
            for (const o of occupied) {
              // Not only full-width bars: the open line is as wide as the column
              // it stands in and no wider, and a sentence printed into it is
              // exactly what this cut exists to stop. What decides is how much
              // of the sentence's own width the thing below actually takes.
              const overlap = Math.min(o.l + o.w, r.l + r.w) - Math.max(o.l, r.l)
              if (
                overlap >= Math.min(120, r.w * 0.5) &&
                o.h < rr.height * 0.7 &&
                o.t > r.t + 40 &&
                o.t < cut
              )
                cut = o.t
            }
            return cut
          }
          let bestG = g0
          let bestOver = Infinity
          for (const g of geoms) {
            const r = settleAt(d, g.l, g.t, g.w)
            const cut = cutFor(r)
            let over = Math.max(0, r.t + r.h - cut)
            // A stand whose own top is already at the bar cannot fade above it.
            if (r.t > cut - 48) over += 100000
            if (over < bestOver) {
              bestOver = over
              bestG = g
            }
          }
          const r = settleAt(d, bestG.l, bestG.t, bestG.w)
          placedRects.push(r)
          const cut = cutFor(r)
          if (r.t + r.h > cut - FIT_SLACK) {
            const visible = Math.max(48, cut - FIT_SLACK - r.t)
            const grad = `linear-gradient(180deg, #000 0, #000 ${Math.max(0, visible - 44)}px, transparent ${visible}px)`
            d.style.setProperty('-webkit-mask-image', grad)
            d.style.setProperty('mask-image', grad)
          }
        }
        freeSlot += 1
      }
      toThread.push(d)
    })
    const foot = placedRects.reduce((m, r) => Math.max(m, r.t + r.h), 0)
    if (foot <= roomBottom - FIT_SLACK) break
  }


  // The turn is paced here, not in the words: one sentence after another, at
  // the same interval the threads are drawn at.
  toThread.forEach((d, si) => {
    revealVoiceSentence(d, 180 + si * 420)
    if (THREADS_DRAWN) drawThread(d, si)
  })
}

// Any real page interaction ends the speaking moment. Capture phase, so it
// works regardless of host handlers; only our own controls are exempt.
const onPointerDown = (e: PointerEvent): void => {
  const el = e.target as HTMLElement | null
  // This voice's own controls are exempt, and so is its origin: reaching for
  // the mask is not the page interaction that ends a turn.
  if (el?.closest('.pvl-ask') || el?.closest(FIGURE_SELECTOR)) return
  settle()
}

// Placement and thread geometry are render-time; after a resize they point
// wrong, and stale pointing is worse than absence.
const onResize = (): void => {
  settle()
  if (threadsEl.value) threadsEl.value.innerHTML = ''
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  window.addEventListener('pointerdown', onPointerDown, true)
  // Says that THIS page can be spoken on, which is what puts the other mouth in
  // help's panel. Counted in the store, so the overlap during a route change
  // cannot leave it claiming a voice that has left.
  presence.registerVoice()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('pointerdown', onPointerDown, true)
  if (askRaf) {
    cancelAnimationFrame(askRaf)
    askRaf = 0
  }
  presence.unregisterVoice()
  clearAcks()
})

// Untyped on purpose: Vue unwraps the ref on the way out, so what a host holds
// is PlatformVoiceHandle — which is what a host declares its template ref as.
defineExpose({ speak, clear, hasAnswered })
</script>

<style scoped>
.pvl-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 50;
}
.pvl-threads {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
/* The visible thread only: the wipe path inside each thread's mask carries its
   own inline white and must never be reached from here. */
.pvl-threads :deep(path.pvl-thread) {
  fill: none;
  stroke: #f0c27a;
  /* Dots, not a ruled line: a dash of almost no length under a round cap is a
     round dot of stroke-width across, every 7px of curve. */
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-dasharray: 0.01 7;
  opacity: 0.36;
  transition: opacity 0.7s ease;
}
.pvl-voice {
  position: absolute;
  inset: 0;
}
/* How a sentence READS is the shared voice's business (@/assets/voiceText.css);
   what stays here is where it stands. The voice is pointer-transparent so it
   can never block a drag or a click on the page it speaks about. */
.pvl-voice :deep(.pvl-sent) {
  position: absolute;
  pointer-events: none;
  /* AT THE RIGHT EDGE OF ITS COLUMN, like everything this platform says in an
     exchange: the agent's words stand right, the human's line stands left
     (see .turn-answer / .turn-writing in components/ResonaVoice.vue). The
     address was the one place that still read flush left, and against the
     exchange under it that looked like a second, unrelated text. */
  text-align: right;
}
/* Docked words hold a 13px lift and let opacity alone carry their arrival,
   instead of travelling in from below like free-standing words: at an element
   they speak about, the words belong tight under it. This has to keep
   outranking the shared entrance — the moment it does not, docked words travel
   and land 13px lower than the dock was measured for. */
.pvl-voice :deep(.pvl-sent.docked .pvl-ch) {
  transform: translate(0, -13px) rotate(0deg);
  transition: transform 0.5s cubic-bezier(0.3, 1.45, 0.45, 1), opacity 0.3s ease;
}

/* The asking place. Not a presence and not a dock: a line to write in, standing
   at the mask, positioned per frame by placeAsk(). Teleported to the body, so
   it is fixed to the viewport the mask is fixed to. Nothing here draws a
   figure — the page has one, and it is the mask.

   No animation, and therefore nothing for prefers-reduced-motion to switch off:
   the waiting is said by the mask's own pulse and by the line below. */
.pvl-ask {
  position: fixed;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  pointer-events: auto;
  z-index: 10000;
}
.pvl-askform {
  margin: 0;
}
.pvl-input {
  width: min(340px, 60vw);
  background: var(--surface-1);
  border: 1px solid #3a3630;
  border-radius: 8px;
  color: #ffffff;
  font-size: 0.9rem;
  padding: 0.55rem 0.75rem;
}
.pvl-input:focus-visible {
  outline: 2px solid #f0c27a;
  outline-offset: 1px;
}
.pvl-state {
  font-size: 0.78rem;
  color: #8e8b84;
}
</style>

<style>
/* Lands on elements the host view owns (outside this component's DOM). */
.pvl-live-ack {
  border-color: rgba(240, 194, 122, 0.55) !important;
  box-shadow: 0 0 0 1px rgba(240, 194, 122, 0.1), 0 0 26px rgba(240, 194, 122, 0.07);
  transition: border-color 0.5s, box-shadow 0.5s;
}
</style>
