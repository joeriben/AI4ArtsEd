<template>
  <div class="cover">
    <!-- The band: the recording, the run, the song. Same three nodes every
         flow page stands under; here they carry a chain nobody picks a model
         for, which the band handles by showing what IS rather than a choice.

         It lives in a strip of its own because this page, unlike the flow it
         came from, is a column that scrolls. A header that scrolls away stops
         being one: the strip holds still and .below moves under it. The strip
         is also what .map-wrap positions itself against. -->
    <div
      class="band-slot"
      :class="{ open: runOpen }"
      :style="{
        '--band-ratio': BAND_WORLD.h / BAND_WORLD.w,
        '--band-open': (GEN_WIDE.y + GEN_WIDE.h - BAND_WORLD.h) / BAND_WORLD.w,
      }"
    >
      <FlowHeader
        :world="BAND_WORLD"
        :rects="BAND"
        :gen-attrs="{ class: { live: !!runningStation, wide: runOpen, anim: stageSettled } }"
        :gen-rect="runOpen ? GEN_WIDE : null"
        :output-attrs="{ class: { failed: status.sung === 'failed' } }"
        :active-target="activeTarget"
      >
        <!-- The flow's input node: the glyph row — one glyph deep, sound, because this
             page makes nothing else — and under it the machines this page
             offers, ALL FOUR OF THEM, named in the node. The set is fixed, so
             it is shown rather than hidden behind a click that nothing
             announced.

             None is lit before a run, and that is the honest state: which one
             runs is decided by what the first station HEARS (the routing
             table: music and text, music alone, speech alone, neither),
             and nothing has been heard yet. The chain names the machine it took
             on its own event and the node lights it from there. A hand-pick
             beats the table, holds across runs, and carries the flow's own
             underline; then it is lit from the moment it is picked.

             What MAKES the material is not in here. In the flow a plus lying free
             on the surface puts a card on the board; on a page that is a column,
             material is taken in the box the whole platform takes it in, and
             that box is below. -->
        <template #create>
          <div class="cr-media">
            <MediumGlyph id="sound" class="g primary" />
          </div>
          <div class="cr-models" role="group" :aria-label="t('coverBand.sung.pick')">
            <button
              v-for="s in SINGERS"
              :key="s.id"
              class="cr-model"
              :class="{ a: s.id === litSinger, held: s.id === heldSinger }"
              :aria-pressed="s.id === litSinger"
              :disabled="busy || launched"
              :title="s.id === heldSinger ? t('coverBand.sung.held') : t('coverBand.sung.pick')"
              @click="heldSinger = s.id"
            >{{ s.label }}</button>
          </div>
        </template>

        <template #generate>
          <!-- The flow's gesture, for the flow's reason: while the chain is the
               only thing happening, this box takes the room of all three and
               says what is running, on which machine, and what came out of it.
               It lets go when the song arrives — from there on the box on the
               right is the one that matters. The readable boxes below are
               thrown out of here as their stations answer.

               Closed, it is the station that STARTS the chain, with the ▶ every
               action node in the band has. Nothing runs off the back of
               stopping the recorder any more: a recording that has only been
               handed over can be listened to, deleted, and made again, and the
               chain begins when somebody says so. -->
          <FlowRunPanel v-if="runOpen" :stations="runStations" />
          <template v-else>
            <div class="lbl">{{ t('coverBand.run.name') }}</div>
            <div v-if="bandState" class="sub">{{ bandState }}</div>
            <!-- Gone once it has been pressed, rather than greyed: the
                 recording it would send no longer exists, and a button that
                 can never be pressed again is not a state this box should
                 hold open. What is left to do then is below, and says so. -->
            <button
              v-if="!launched"
              class="go"
              :disabled="!canRun"
              :title="t('coverBand.run.start')"
              @click="startChain"
            >▶</button>
          </template>
        </template>

        <!-- The flow's out node holds the produced media itself (see .out-media
             and .out-audio in views/x2x_flow.vue), so this one holds the song.
             The name stays when it arrives: it is what ties this box to the
             chain, and without it the finished state is a bare player. -->
        <template #output>
          <div class="lbl">{{ t('coverBand.sung.name') }}</div>
          <audio
            v-if="sungUrl"
            class="band-audio"
            :src="sungUrl"
            controls
            controlsList="nodownload noplaybackrate"
            @contextmenu.prevent
          ></audio>
          <!-- The only place the last machine is ever named — the other three
               are named on the backs of the boxes they filled. -->
          <div v-if="sungUrl && stationModel.sung" class="band-by">
            {{ t('coverBand.sung.madeBy', {
              model: stationModel.sung,
              s: (stationMs.sung / 1000).toFixed(1),
            }) }}
          </div>
        </template>
      </FlowHeader>
    </div>

    <div class="below" :class="{ 'footer-open': favorites.isGalleryExpanded }">
      <!-- Directly over the box that causes it. "No microphone" changes
           nothing else on the page — the box simply does not start — so this
           line is the whole answer, and at the foot of the column it was below
           the fold on a workshop screen. -->
      <p v-if="error" class="err band-err">{{ error }}</p>

      <!-- The board. Every box that answers is thrown onto it and finds a place
           that is free — reading order out of the corner, never on top of
           another. Positions are computed from the boxes' MEASURED heights, not
           written down, because the text in them is as long as the machines
           made it. -->
      <!-- Measured on this strip, not on the board: it has the board's width
           and no height, so the height pack() writes can never move what pack()
           reads. Same separation the flow stage keeps — there the observer only
           measures and the size comes from CSS. -->
      <div ref="probeEl" class="board-probe" aria-hidden="true"></div>
      <div ref="boardEl" class="board" :style="boardStyle">

      <!-- Where the recording is made, and where it lies once it exists: the
           box this platform takes material in, with audio as its third kind
           (components/MediaInputBox.vue, components/AudioRecordWidget.vue). It
           stands first in the column, in the reading measure the take card had
           (34rem) — NOT at the column's width: on every other page this box
           sits in half columns and grid cells, and the zone's size on the
           image side is a drop target and a preview. Audio has nothing to
           drop; a page-wide click switch was covered by nothing.

           The trash in its header is the whole reason the chain no longer
           starts by itself. A recording that ran straight into four machines
           could not be listened to, could not be discarded, and could not be
           done again without having cost a song first.

           It is also the ONLY way back, since the button for recording
           something else is off the page. So it hides only while the
           machines are working and comes back when they stop — before that
           change it stayed hidden for the rest of the visit and the page could
           not be used a second time without a reload. The same trash takes the
           song and the three read boxes with it.

           The BOX stays disabled after the run, and that is not the same
           question: recording straight over a finished take would leave the
           previous song and its four boxes standing next to a new recording.
           The trash goes through reset(), which clears both. -->
      <div class="slot" :ref="slotRef.rec" :style="slotStyle('rec')">
      <MediaInputBox
        icon="mic"
        class="rec-box"
        :label="t('coverBand.record.name')"
        input-type="audio"
        value=""
        :audio-src="takeUrl"
        :max-seconds="MAX_SECONDS"
        :disabled="busy || uploading || launched"
        :is-filled="!!takeUrl"
        :show-clear="!!takeUrl && !busy && !uploading"
        @audio-recorded="onTake"
        @mic-error="error = t('coverBand.errors.noMic')"
        @clear="reset()"
      />
      </div>

      <!-- Three sentences stood here (the length, the deletion, the
           invitation) and are gone. They are in the help, in the module entry
           and in the page entry, both of which carry the terms in full. The
           page states nothing for itself. -->

      <!-- The three that can be READ. Each one leaves the middle box when its
           station answers and lands here — before that it is not on the page at
           all. An empty box promises something; a box that arrives shows where
           it came from, and the middle box says what is still on its way. -->
      <div v-if="shown('ranked')" class="slot" :ref="slotRef.ranked"
           :style="slotStyle('ranked')">
      <FlowCard
          class="station ranked thrown"
          :class="stationClass('ranked')"
        >
          <div class="st-head">
            <span class="st-name">{{ t('coverBand.ranked.name') }}</span>
            <span class="st-note">{{ t('coverBand.ranked.note') }}</span>
          </div>

          <ol v-if="ranking.length" class="ranking">
            <li v-for="entry in rankingHead" :key="entry.label">
              <span class="score">{{ fmt(entry.score) }}</span>
              <span class="label">{{ entry.label }}</span>
            </li>
          </ol>
          <p v-if="rankingTail" class="tail">
            {{ t('coverBand.ranked.last') }}
            <span class="score">{{ fmt(rankingTail.score) }}</span>
            <span class="label">{{ rankingTail.label }}</span>
          </p>

          <div v-if="secondHead.length" class="second">
            <p class="hint">{{ t('coverBand.ranked.secondMachine', { model: secondModel }) }}</p>
            <ol class="ranking">
              <li v-for="entry in secondHead" :key="entry.label">
                <span class="score">{{ fmt(entry.score) }}</span>
                <span class="label">{{ entry.label }}</span>
              </li>
            </ol>
            <p class="hint">{{ t('coverBand.ranked.secondWhy') }}</p>
          </div>
          <p v-else-if="secondFailed" class="err">
            {{ t('coverBand.ranked.secondFailed', secondFailed) }}
          </p>

          <p v-if="ranking.length" class="hint">
            {{ t('coverBand.ranked.ourList', { n: ranking.length }) }}
          </p>
          <p v-if="ranking.length" class="hint context">
            {{ t('coverBand.ranked.culturalLimit', { model: rankingModel }) }}
            <a
              class="src"
              href="https://transactions.ismir.net/articles/10.5334/tismir.341"
              target="_blank"
              rel="noopener noreferrer"
            >{{ t('coverBand.ranked.culturalLimitSource') }}</a>
          </p>
          <p v-else class="placeholder">{{ stationPlaceholder('ranked') }}</p>

        <template #back>
          <div class="im-head">{{ t('coverBand.back.head') }}</div>
          <div v-for="r in backRows('ranked')" :key="r.k" class="im-row">
            <span class="im-k">{{ r.k }}</span>
            <span class="im-v">{{ r.v }}</span>
          </div>
        </template>
        </FlowCard>
      </div>

      <div v-if="shown('words')" class="slot" :ref="slotRef.words"
           :style="slotStyle('words')">
      <FlowCard
          class="station words thrown"
          :class="stationClass('words')"
        >
          <div class="st-head">
            <span class="st-name">{{ t('coverBand.words.name') }}</span>
            <span class="st-note">{{ t('coverBand.words.note') }}</span>
          </div>

          <p v-if="words !== null && words !== ''" class="transcript">{{ words }}</p>
          <p v-else-if="words === ''" class="transcript none">
            {{ t('coverBand.words.returnedNothing') }}
          </p>
          <p v-else class="placeholder">{{ stationPlaceholder('words') }}</p>

          <!-- A warning here would be defensive. The word "recognised" in
               the caption below does the work, and this line states what the
               machine does rather than what it does not prove. -->
          <p v-if="words" class="hint">{{ t('coverBand.words.notProof') }}</p>

          <p v-if="wordsRead" class="transcript reading">{{ wordsRead }}</p>
          <p v-if="wordsRead" class="hint">{{ t('coverBand.words.inReadingLanguage') }}</p>
          <!-- `words !== null`, not truthiness: an empty transcription is the
               empty-room case this page invites, and the language the machine
               invented before it chose a single word is the most legible thing
               it produces there. Truthiness hid it exactly then. -->
          <p v-if="words !== null && heardLanguage" class="hint">
            {{ t('coverBand.words.whichLanguage', { language: heardLanguage }) }}
          </p>

        <template #back>
          <div class="im-head">{{ t('coverBand.back.head') }}</div>
          <div v-for="r in backRows('words')" :key="r.k" class="im-row">
            <span class="im-k">{{ r.k }}</span>
            <span class="im-v">{{ r.v }}</span>
          </div>
        </template>
        </FlowCard>
      </div>

      <!-- The one that invents ------------------------------------------- -->
      <div v-if="shown('written')" class="slot" :ref="slotRef.written"
           :style="slotStyle('written')">
      <FlowCard
        class="station written thrown"
        :class="stationClass('written')"
      >
        <div class="st-head">
          <span class="st-name">{{ t('coverBand.written.name') }}</span>
          <span class="st-note">{{ t('coverBand.written.note') }}</span>
        </div>

        <template v-if="lyrics">
          <p class="tags"><span class="k">{{ t('coverBand.written.tagsLabel') }}</span> {{ tags }}</p>
          <pre class="lyrics">{{ lyrics }}</pre>
          <p class="hint">{{ t('coverBand.written.readAlong') }}</p>
        </template>
        <p v-else class="placeholder">{{ stationPlaceholder('written') }}</p>

      <template #back>
        <div class="im-head">{{ t('coverBand.back.head') }}</div>
        <div v-for="r in backRows('written')" :key="r.k" class="im-row">
          <span class="im-k">{{ r.k }}</span>
          <span class="im-v">{{ r.v }}</span>
        </div>
      </template>
      </FlowCard>
      </div>
      </div>

      <!-- The last station's box, in the column with the other four and not in
           the node above it. It is the only one that cannot be read, so it says
           so, and the terms it stands under are the ones that hold for it
           alone: this one is not kept and cannot be taken away. -->
      <!-- It sends the reader to the box at the top of the page, so it waits
           for there to be something up there to send them to. -->
      <p v-if="lyrics" class="hint">{{ t('coverBand.sung.note') }}</p>
      <p v-if="sungUrl" class="hint">{{ t('coverBand.sung.notKept') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watchEffect } from 'vue'
import FlowCard from '@/components/FlowCard.vue'
import FlowHeader from '@/components/FlowHeader.vue'
import FlowRunPanel from '@/components/FlowRunPanel.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediumGlyph from '@/components/MediumGlyph.vue'
import { useFavoritesStore } from '@/stores/favorites'
import { usePageContextStore } from '@/stores/pageContext'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()

// The footer gallery is fixed over the bottom of every page and has two
// heights. Now that .below is the only scroller, its range ends at the viewport
// bottom, so whatever the footer covers cannot be scrolled out from under it.
const favorites = useFavoritesStore()

// The explanation takes no fixed space on the page; Träshy offers it on a
// symbolic act. So the
// page hands over the QUESTION and Träshy answers it from what it already knows
// — the interface reference names this page, and every station's state is in the
// context below. Nothing about the chain is written out twice.
const pageContext = usePageContextStore()

type Station = 'ranked' | 'words' | 'written' | 'sung'
type Status = 'idle' | 'running' | 'done' | 'failed'
type Ranked = { label: string; score: number }

// Two waits, not one. `uploading` is the recording being handed over, `busy` is
// the chain running — and between them sits the moment the page now has: a
// recording that exists, has been listened to, and has not been sent anywhere.
const uploading = ref(false)
const busy = ref(false)
/** The take itself, playable where it lies. Local only; nothing is uploaded twice. */
const takeUrl = ref('')
const error = ref('')

const recordingId = ref<string | null>(null)

// The four machines station 5 can end on, in the order of the routing
// table. The ids are output configs, so a change to one of those files
// reaches here. Must stay in step with SOUND_CONFIGS in
// devserver/my_app/services/parrot_service.py — that is the side that decides;
// this side only names and offers.
const SINGERS = [
  { id: 'heartmula_standard', label: 'HeartMuLa' },
  { id: 'stableaudio_music', label: 'SA3 Music' },
  { id: 'stableaudio_sfx', label: 'SA3 SFX' },
  { id: 'voxcpm_standard', label: 'VoxCPM2' },
]

/** A hand-pick. Null until somebody makes one; then it holds across runs. */
const heldSinger = ref<string | null>(null)

/** The machine the chain took, off its own event. Cleared with the page. */
const ranSinger = ref<string | null>(null)

/**
 * The one the node lights. A hand-pick from the moment it is made; otherwise
 * whatever the chain resolved, and nothing at all before that — which is the
 * true state, since the choice is made from what the recording turns out to be.
 */
const litSinger = computed(() => heldSinger.value ?? ranSinger.value)

const status = ref<Record<Station, Status>>({
  ranked: 'idle', words: 'idle', written: 'idle', sung: 'idle',
})
const ranking = ref<Ranked[]>([])
const rankingModel = ref('')
// The second machine is shown, not hidden behind a toggle: the disagreement is
// the point, and a disagreement nobody opens is not one.
const secondModel = ref('')
const secondRanking = ref<Ranked[]>([])
// The second machine that did not answer, and the reason it gave.
const secondFailed = ref<{ model: string; cause: string } | null>(null)
const words = ref<string | null>(null)
const heardLanguage = ref('')
// Which machine, and how long the station took. Both come off the chain's own
// events and were dropped on the floor until the middle box started reporting
// the run.
//
// What the number is, so nobody reads more into it than it holds: wall time for
// the whole station, measured in parrot_service. It INCLUDES loading the model
// if it was not already resident, so the same station can differ by an order of
// magnitude between a cold and a warm box; the sorting box covers two machines,
// not one; and the singing scales with the recording, because the song comes
// back as long as the recording did. Four numbers in a row invite a comparison
// between the machines, and only the roughest one — seconds against minutes —
// is one the numbers can carry.
const stationModel = ref<Record<Station, string>>({
  ranked: '', words: '', written: '', sung: '',
})
const stationMs = ref<Record<Station, number>>({
  ranked: 0, words: 0, written: 0, sung: 0,
})
// Present only where the transcriber named a language and it is not the one
// selected for the platform. The words above stay exactly as they came back;
// this is an aid, not a correction — and it names its own machine, because on
// this page every machine that produces text is named.
const wordsRead = ref('')
const readModel = ref('')
const tags = ref('')
const lyrics = ref('')
const sungUrl = ref('')

// The head is what the group reads and what the writing station was given —
// deliberately the same slice, so the page does not show one thing and feed
// the model another.
const rankingHead = computed(() => ranking.value.slice(0, 8))
// The last place is not decoration. Which word a model puts at the bottom,
// every single time, is the most legible thing on this page.
const rankingTail = computed(() => ranking.value.length ? ranking.value[ranking.value.length - 1] : null)

const secondHead = computed(() => secondRanking.value.slice(0, 5))

const fmt = (n: number) => (n >= 0 ? '+' : '') + n.toFixed(2)

// What the band's middle node says when it is NOT open — before a recording
// and after the song. While the chain runs it says considerably more; see
// runStations.
// Wider boxes than the flow's own. The three nodes here hold a control row, a
// state line and an audio player, not glyphs — at the flow's 220/160/160 the
// recording row wrapped and pushed its own label out of the box.
// Passed explicitly rather than left to the component's default, because the
// strip's height in CSS is computed from these same two numbers and nothing in
// the language can tie them together. They are next to each other so a change to
// one is a change in sight of the other.
const BAND_WORLD = { w: 1060, h: 150 }

const BAND = {
  create: { x: 40, y: 14, w: 360, h: 122 },
  gen: { x: 452, y: 14, w: 190, h: 122 },
  output: { x: 694, y: 14, w: 326, h: 122 },
}

const ORDER: Station[] = ['ranked', 'words', 'written', 'sung']
const runningStation = computed(() => ORDER.find(s => status.value[s] === 'running') ?? null)

/**
 * The middle box open, over all three. Same rectangle the flow's takes and for
 * the same reason — while the chain runs, nothing else on the strip is doing
 * anything. It stays inside the world box: the flow's grows taller than a node
 * and reaches over its canvas, but here a scrolling column sits directly under
 * the strip and would be covered by the overhang.
 */
const GEN_WIDE = {
  x: BAND.create.x,
  y: BAND.gen.y,
  w: BAND.output.x + BAND.output.w - BAND.create.x,
  // Taller than a node, like the flow's. Four stations of three lines each do
  // not fit into 122, and a box that cannot fit its content does not clip it —
  // .gr-v has overflow:hidden, so under flexbox its minimum height is zero and
  // it is sliced or erased instead. Measured at 768px before this: the model
  // names were 8px tall inside a 13px line.
  //
  // It reaches past the world box, and .band-slot grows by exactly the overhang
  // while it is open (see --band-open).
  h: 190,
}

// Open from the first station until the song is there. Not `runningStation`
// alone: the gaps between stations would snap it shut and open it again.
const runOpen = computed(() => busy.value && !sungUrl.value)

/**
 * The box must not glide into place on load, and must not lag behind its two
 * neighbours while a window is being resized — only those two move instantly,
 * because only this one has a transition. Same guard the flow keeps, hung on
 * the cause rather than on a measured stage.
 */
const stageSettled = ref(false)
let settleTimer: ReturnType<typeof setTimeout> | null = null
function settle() {
  stageSettled.value = false
  if (settleTimer) clearTimeout(settleTimer)
  settleTimer = setTimeout(() => { stageSettled.value = true }, 220)
}
onMounted(() => {
  settle()
  window.addEventListener('resize', settle)
})


/* ---------------------------------------------------------------------------
 * The board
 *
 * The boxes go onto the canvas as in the Flow, in order from the top left to
 * the right and the centre, not at rigid positions but by fit; no box over
 * another.
 *
 * A grid could not do it. Its cells are assigned in advance, so the box that
 * answers second sits under an empty cell if the first one was short, and the
 * long list and the two short ones cannot share a column without one of them
 * being cut. What decides here is the MEASURED height of what the machines
 * wrote: each box goes to the column that currently ends highest — ties to the
 * left, which is what makes the order read out of the top left corner — and
 * starts where that column ends. Nothing can land on anything.
 *
 * Measured, not estimated: the text is as long as the machines made it, and it
 * reflows on every width. A ResizeObserver on each box and on the board is the
 * only thing that stays true through a translation, a long ranking or a phone.
 */
const BOX_KEYS = ['rec', 'ranked', 'words', 'written'] as const
type BoxKey = (typeof BOX_KEYS)[number]

const boardEl = ref<HTMLElement | null>(null)
const probeEl = ref<HTMLElement | null>(null)
const boardH = ref(0)
const colW = ref(0)
const slots = new Map<BoxKey, HTMLElement>()
const place = ref<Record<string, { x: number; y: number }>>({})

// The measure the boxes need, not the width the screen offers: two columns of
// half a stage are narrower than the text wants below the stage's own width.
const GAP = 20
const MIN_COL = 380

// --col-w stays off the board until there is a measurement. Emitting 0px would
// give the boxes no width to wrap in, and the heights read in the first pass
// would be the heights of text in a zero-wide column. The CSS fallback (100%)
// is the one-column layout, and it measures true.
const boardStyle = computed(() => (colW.value
  ? { height: `${boardH.value}px`, '--col-w': `${colW.value}px` }
  : { height: `${boardH.value}px` }))

// One function per box, built once. An inline arrow in the template is a new
// identity on every render, so Vue unbinds and rebinds it and calls setSlot
// twice per box per render; with a layout pass on the end of setSlot that is a
// closed loop on its own, with no resize involved at all.
const slotRef = Object.fromEntries(
  BOX_KEYS.map(key => [key, (el: unknown) => setSlot(key, el)]),
) as Record<BoxKey, (el: unknown) => void>

function setSlot(key: BoxKey, el: unknown) {
  const node = (el as HTMLElement | null) ?? null
  if (node) {
    slots.set(key, node)
    slotWatch?.observe(node)
  } else {
    const gone = slots.get(key)
    if (gone) slotWatch?.unobserve(gone)
    slots.delete(key)
  }
  schedulePack()
}

function slotStyle(key: BoxKey) {
  const p = place.value[key]
  // Before the first measurement a box has no place yet. Hidden rather than
  // stacked in the corner: one frame of four boxes on top of each other is
  // exactly the thing this layout exists to prevent.
  if (!p) return { visibility: 'hidden' as const }
  // A transform and nothing else. A width written here would resize the very
  // elements slotWatch observes, and the observer would ask for another pass.
  // The column width reaches the boxes as --col-w on the board instead.
  return { transform: `translate(${p.x}px, ${p.y}px)` }
}

/** True when the new placement differs from the one already on the board. */
function moved(next: Record<string, { x: number; y: number }>) {
  const cur = place.value
  const keys = Object.keys(next)
  if (keys.length !== Object.keys(cur).length) return true
  return keys.some(k => {
    const a = cur[k]
    const b = next[k]
    return !a || !b || a.x !== b.x || a.y !== b.y
  })
}

function pack() {
  // The strip, not the board: reading the board would mean reading an element
  // whose height this function sets.
  const probe = probeEl.value
  if (!probe) return
  const width = probe.clientWidth
  if (!width) return
  const cols = Math.max(1, Math.min(2, Math.floor((width + GAP) / (MIN_COL + GAP))))
  const w = Math.floor((width - GAP * (cols - 1)) / cols)
  const ends = new Array(cols).fill(0)
  const next: Record<string, { x: number; y: number }> = {}
  for (const key of BOX_KEYS) {
    const el = slots.get(key)
    if (!el) continue
    // The column that ends highest, ties to the left.
    let c = 0
    for (let i = 1; i < cols; i += 1) if (ends[i] < ends[c] - 1) c = i
    next[key] = { x: c * (w + GAP), y: ends[c] }
    ends[c] += el.offsetHeight + GAP
  }
  const h = Math.max(0, ...ends.map(e => e - GAP))
  // Written only on a real difference. A pass that computes the same numbers
  // must not hand out a fresh object, because a fresh object is a change to
  // Vue and would render again — and rendering asks for another pass.
  if (w !== colW.value) colW.value = w
  if (h !== boardH.value) boardH.value = h
  if (moved(next)) place.value = next
}

let slotWatch: ResizeObserver | null = null
let boardWatch: ResizeObserver | null = null
let packFrame = 0

// One pass per frame. A single change reaches the observers more than once —
// the box arrives, the column width follows, the text reflows — and each of
// those would otherwise be its own full pass.
function schedulePack() {
  if (packFrame) return
  packFrame = requestAnimationFrame(() => {
    packFrame = 0
    pack()
  })
}

onMounted(() => {
  slotWatch = new ResizeObserver(schedulePack)
  boardWatch = new ResizeObserver(schedulePack)
  if (probeEl.value) boardWatch.observe(probeEl.value)
  slots.forEach(el => slotWatch?.observe(el))
  pack()
})
onBeforeUnmount(() => {
  if (packFrame) cancelAnimationFrame(packFrame)
  packFrame = 0
  slotWatch?.disconnect()
  boardWatch?.disconnect()
  slotWatch = boardWatch = null
})

/** A station is on the page once it has answered — or once it has not. */
function shown(s: Station) {
  return status.value[s] === 'done' || status.value[s] === 'failed'
}

/**
 * The run, station by station: what is happening and on which machine. It says
 * how far the chain has got and what each step cost, and NOTHING about what
 * came back — that belongs in the box the station throws out.
 *
 * It held one line of each result until 2026-08-09: the top label, the language
 * the transcriber decided on, the style words. Every one of those is a
 * confabulation the page exists to hold up, and each is carried by a sentence
 * that only stands in its own box ("It always picks a best match, even from
 * silence"; "Nobody told it which language to listen for"). Up here, while
 * HeartMuLa runs for minutes and this is the one thing above the fold, they
 * read as findings.
 */
// The panel speaks the flow's vocabulary for a station's state. This chain
// has one the flow does not: any of its four can simply not answer.
const RUN_STATE = {
  idle: 'todo', running: 'live', done: 'done', failed: 'failed',
} as const

const runStations = computed(() =>
  ORDER.map(id => ({
    id,
    label: t(`coverBand.${id}.name`),
    detail: machineFor(id) || t(status.value[id] === 'running' ? 'coverBand.working' : 'coverBand.waiting'),
    time: stationMs.value[id]
      ? t('coverBand.run.took', { s: (stationMs.value[id] / 1000).toFixed(1) })
      : '',
    state: RUN_STATE[status.value[id]],
  }))
)

function machineFor(s: Station) {
  // Both rankers, because both of them answered and the page says so everywhere
  // else it mentions them.
  if (s === 'ranked') {
    return [stationModel.value.ranked, secondModel.value].filter(Boolean).join(' \u00b7 ')
  }
  return stationModel.value[s]
}


const failedStation = computed(() => ORDER.find(s => status.value[s] === 'failed') ?? null)

// What the retracted box says. A running station is not among the cases: while
// anything runs the box is open and says considerably more. A break is, and it
// names the station — "this machine did not answer" without saying which one
// leaves the group with a red line and no idea where the chain stopped.
const bandState = computed(() => {
  if (status.value.sung === 'done') return t('coverBand.band.done')
  const f = failedStation.value
  if (f) return t('coverBand.stationFailedNamed', { station: t(`coverBand.${f}.name`) })
  // Nothing. The ▶ under this line says what is missing better than a word for
  // standing still does, and it says whether it can be pressed yet.
  return ''
})


/**
 * A box's back: which machine, what it was given, what it cost. The same three
 * rows the flow puts on the back of a piece of material — perspective, model,
 * the prompt that was submitted (views/x2x_flow.vue). It is written once for
 * all four boxes so that the four backs cannot drift apart.
 */
const GOT: Record<Station, string> = {
  ranked: 'coverBand.back.gotRecording',
  words: 'coverBand.back.gotRecording',
  written: 'coverBand.back.gotStations',
  sung: 'coverBand.back.gotWritten',
}
function backRows(s: Station): { k: string; v: string }[] {
  const rows: { k: string; v: string }[] = []
  const machine = s === 'ranked' ? machineFor('ranked') : stationModel.value[s]
  if (machine) rows.push({ k: t('coverBand.back.machine'), v: machine })
  // A station that did not answer made nothing. The machine was asked, so it
  // can be named; "it got" and "it took" would be the back of the card
  // asserting a provenance for a result the front says does not exist.
  if (status.value[s] === 'failed') return rows
  if (s === 'words' && readModel.value) {
    rows.push({ k: t('coverBand.back.translation'), v: readModel.value })
  }
  rows.push({ k: t('coverBand.back.got'), v: t(GOT[s]) })
  if (stationMs.value[s]) {
    rows.push({
      k: t('coverBand.back.took'),
      v: t('coverBand.back.seconds', { s: (stationMs.value[s] / 1000).toFixed(1) }),
    })
  }
  return rows
}

// Which connector is lit: into the run while it runs, into the song once there
// is one.
const activeTarget = computed<'create' | 'gen' | 'output' | null>(() => {
  if (runningStation.value === 'sung' || sungUrl.value) return 'output'
  if (runningStation.value) return 'gen'
  return null
})

// No `running` here: a section only exists once shown() is true, which is
// done or failed. A rule for a state the element cannot be in is a rule nobody
// can find the bug in.
// Only `failed` is a state of its own. A box exists at all only once its
// station has answered or has not, so `done` is the normal case — and the box a
// station answered into is simply the flow's card, with the flow's border.
// Giving `done` a border here would be the page restating the card a second
// time, which is what moving to FlowCard removed.
function stationClass(s: Station) {
  return { failed: status.value[s] === 'failed' }
}

function stationPlaceholder(s: Station) {
  // No 'running' branch: a placeholder only renders inside a card, and a card
  // only exists from `done` or `failed` on (see shown()). A rule for a state
  // the element cannot be in is a rule nobody can find the bug in.
  if (status.value[s] === 'failed') return t('coverBand.stationFailed')
  return t('coverBand.waiting')
}

// --- the take --------------------------------------------------------------
// The microphone, the clock, the ceiling and the conversion to wav belong to
// AudioRecordWidget now — to the box that takes the recording, not to this
// page. What is left here is the page's own part: what happens to a finished
// wav.

// Recordings are capped at 240 s. The same number the
// song tops out at (SONG_MAX_MS in parrot_service), so the recording cannot run
// past what can be sung back. The box is handed the number and holds to it.
const MAX_SECONDS = 240

/** Set when the page is left, and read across every await below. */
let left = false

async function onTake(wav: Blob) {
  // Nothing should reach this line while a take is already lying here — the box
  // refuses to record over one. But the cost if it did is a recording on the
  // server that nobody holds the id of any more, and the staging sweep only
  // runs when the next person records.
  if (recordingId.value) {
    abandon()
    recordingId.value = null
  }
  releaseTake()
  uploading.value = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('file', wav, 'recording.wav')
    const res = await fetch('/api/parrot/recording', { method: 'POST', body: form })
    // A proxy answers a body it will not carry with a 413 and an HTML page, not
    // with this route's JSON. Read the status first, or the actionable answer
    // ("that is longer than four minutes") is lost in the generic one.
    if (!res.ok) {
      error.value = t(res.status === 413 ? 'coverBand.errors.tooLong' : 'coverBand.errors.upload')
      uploading.value = false
      return
    }
    const data = await res.json()
    if (!data.success) {
      // The one failure the group can do something about, now that nothing
      // stops the recording for them.
      error.value = t(data.code === 'too_long'
        ? 'coverBand.errors.tooLong'
        : 'coverBand.errors.upload')
      uploading.value = false
      return
    }
    // The page can be gone by now: three awaits stand between the recording
    // ending and this line, and `left` was last read before the first of them.
    // Nobody would be holding this id, and the staging sweep only runs when the
    // next person records — so the recording this page promises to delete would
    // have sat there for the rest of the day.
    if (left) {
      void fetch(`/api/parrot/discard/${data.recording_id}`, {
        method: 'POST',
        keepalive: true,
      }).catch(() => {})
      return
    }
    recordingId.value = data.recording_id
    takeUrl.value = URL.createObjectURL(wav)
    uploading.value = false
  } catch {
    error.value = t('coverBand.errors.upload')
    uploading.value = false
  }
}

// --- the chain -------------------------------------------------------------
let source: EventSource | null = null

/**
 * Whether this recording has been let go. Not derived from the stations: the
 * server deletes the uploaded wav when the stream ends, whatever ended it
 * (parrot_routes.py, the stream route's finally), so a recording can be sent
 * exactly once and a second ▶ could only ever answer "recording not found".
 *
 * Reading it off the stations instead had it both ways and both were wrong: a
 * chain that broke at a station left the ▶ dead over a recording that still
 * looked usable, and a chain that died BEFORE its first station left every
 * status at idle — so the ▶ lit up again, over a file that was already gone,
 * and invited the same press for as long as anyone kept pressing.
 */
const launched = ref(false)
const canRun = computed(
  () =>
    !!recordingId.value &&
    !uploading.value &&
    !busy.value &&
    !launched.value
)

function startChain() {
  const id = recordingId.value
  if (!id || !canRun.value) return
  launched.value = true
  busy.value = true
  runChain(id)
}

function runChain(id: string) {
  source?.close()
  // The language of the page, so an unreadable transcription can be read.
  // This is not handed to the transcriber — see parrot_service.run_chain.
  source = new EventSource(
    `/api/parrot/stream/${id}?reading=${encodeURIComponent(locale.value)}` +
      (heldSinger.value ? `&config=${encodeURIComponent(heldSinger.value)}` : '')
  )
  source.onmessage = event => {
    const e = JSON.parse(event.data)

    // Arrives after the words themselves and only sometimes — see run_chain.
    // It is not a station: nothing on the strip waits for it.
    if (e.station === 'reading') {
      wordsRead.value = e.text || ''
      readModel.value = e.model || ''
      return
    }

    if (e.station === 'chain') {
      if (e.status === 'complete') { busy.value = false; source?.close(); source = null }
      if (e.status === 'failed') {
        // NOT e.error: a station's failure carries a sentence written for
        // people, but this one carries str(exception) from the route's except
        // branch — a Python message, in English, on a page for children.
        error.value = t('coverBand.errors.chain')
        stopRunning()
      }
      return
    }

    const station = e.station as Station
    if (station in status.value) status.value[station] = e.status
    // On the running event too: the box says which machine is at work, and the
    // one that takes minutes is the one that most needs naming while it does.
    if (e.model && station in stationModel.value) stationModel.value[station] = e.model
    // Carried on the running event as well as the done one, so the node lights
    // the machine while it is working and not only once it has finished.
    if (station === 'sung' && e.config) ranSinger.value = e.config

    if (e.status === 'done') {
      stationModel.value[station] = e.model || ''
      stationMs.value[station] = e.ms || 0
      if (station === 'ranked') {
        ranking.value = e.ranking || []
        rankingModel.value = e.model || ''
        secondModel.value = e.second?.model || ''
        secondRanking.value = e.second?.ranking || []
        secondFailed.value = e.second_failed
          ? { model: e.second_failed.model || '', cause: e.second_failed.error || '' }
          : null
      }
      if (station === 'words') {
        words.value = e.text ?? ''
        heardLanguage.value = e.language || ''
        wordsRead.value = ''
        readModel.value = ''
      }
      if (station === 'written') { tags.value = e.tags || ''; lyrics.value = e.lyrics || '' }
      if (station === 'sung') sungUrl.value = `/api/parrot/sung/${id}?t=${Date.now()}`
    }
    if (e.status === 'failed' && e.error) error.value = e.error
  }
  source.onerror = () => {
    source?.close(); source = null
    if (busy.value) { error.value = t('coverBand.errors.chain'); busy.value = false }
    stopRunning()
  }
}

/**
 * A station the chain will never come back to. Without this the status stayed
 * 'running' after a chain-level break: `runningStation` never cleared, so the
 * middle node kept its livepulse and the connector its fast dash, and the band
 * read as working for good, next to the line saying it had broken off.
 */
function stopRunning() {
  for (const s of ORDER) {
    if (status.value[s] === 'running') status.value[s] = 'failed'
  }
}

// --- leaving ---------------------------------------------------------------
function reset() {
  // Unconditionally, and this used to take a flag. startRecording passed false,
  // so pressing Record straight after a song — rather than "record something
  // else" — dropped the previous id without telling the server, and that song
  // sat in staging until the next sweep. The page promises the opposite. There
  // is no case where this discards a live run: the button is disabled while
  // one is on.
  abandon()
  source?.close(); source = null
  recordingId.value = null
  status.value = { ranked: 'idle', words: 'idle', written: 'idle', sung: 'idle' }
  stationModel.value = { ranked: '', words: '', written: '', sung: '' }
  ranSinger.value = null
  stationMs.value = { ranked: 0, words: 0, written: 0, sung: 0 }
  ranking.value = []
  rankingModel.value = ''
  secondModel.value = ''
  secondRanking.value = []
  secondFailed.value = null
  words.value = null
  heardLanguage.value = ''
  wordsRead.value = ''
  readModel.value = ''
  tags.value = ''
  lyrics.value = ''
  sungUrl.value = ''
  error.value = ''
  launched.value = false
  releaseTake()
}

/**
 * Restored from the back/forward cache. `pagehide` discarded the recording on
 * the way out, but the page itself was kept whole — so without this the group
 * comes back to a take card with a working player, a line saying how long the
 * recording is, and a ▶ over a file the server deleted.
 */
function onPageShow(e: PageTransitionEvent) {
  if (e.persisted) reset()
}
window.addEventListener('pageshow', onPageShow)

/** The take's object URL. Held only while the take is on the page. */
function releaseTake() {
  if (!takeUrl.value) return
  URL.revokeObjectURL(takeUrl.value)
  takeUrl.value = ''
}

// Nothing outlives the visit — and the visit ends in more ways than one.
// onBeforeUnmount covers navigating inside the app; it does NOT run on a tab
// close or a reload, and the staging sweep only runs when the next person
// records, so without this the song sat on disk indefinitely.
function abandon() {
  const id = recordingId.value
  if (!id) return
  const url = `/api/parrot/discard/${id}`
  // sendBeacon is optional-chained everywhere else in this file, which means a
  // browser without it kept the song. keepalive is the same guarantee.
  if (navigator.sendBeacon) navigator.sendBeacon(url)
  else void fetch(url, { method: 'POST', keepalive: true }).catch(() => {})
}
window.addEventListener('pagehide', abandon)

// The context is set once and then follows the run, so what Träshy is asked
// about is the page as it stands at that moment and not as it loaded.
watchEffect(() => {
  pageContext.setPageContext({
    activeViewType: 'cover_band',
    // Nothing here is kept, and that has to hold for what Träshy is told as
    // well: the transcription and the lyrics go into the question's context.
    ephemeral: true,
    pageContent: {
      inputText: words.value ?? '',
      interceptionResult: lyrics.value,
      // NOT selectedConfig: that field renders to Help as "Modell/Config",
      // and these are the style words the writing station produced, not a model.
      selectedCategory: tags.value || null,
    },
    offer: {
      label: t('coverBand.ask.sign'),
      question: t('coverBand.ask.question'),
    },
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', settle)
  if (settleTimer) clearTimeout(settleTimer)
  pageContext.clearContext()
  // The box stops its own microphone and refuses to hand anything over after
  // an unmount. This flag is the page's half of the same guarantee: an upload
  // already in flight must not end up holding an id nobody can discard.
  left = true
  releaseTake()
  abandon()
  window.removeEventListener('pagehide', abandon)
  window.removeEventListener('pageshow', onPageShow)
  source?.close()
})
</script>

<style scoped>
/* A held strip with a scrolling column under it. The band cannot scroll away —
   it is the page's orientation — and this page, unlike the flow the band came
   from, is not a canvas. So the scrolling happens INSIDE .below and the strip
   stays where it is. */
.cover {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-base);
  color: #e8e8e8;
}

/* NOTE (2026-08-18): the band's WIDTH is capped at its container since the
   stage moved into the Latent Lab's work area; this height is still figured
   from the window, and a height cannot take a percentage of a width. Inside the
   Latent Lab the strip is therefore reserved a little too tall — a gap under the
   band, where it used to be a cut-off node. To be squared away with this page's
   own column layout, which is planned separately.

   The strip's height is the stage's own: BAND_WORLD drawn at
   min(--flow-map-w, 100vw - 32px), plus the 10px the band sits down from the
   top and the same again below it. .map-wrap is absolute against THIS.

   --band-ratio comes from BAND_WORLD itself (see the template) rather than
   being written out here a second time. Written out, the two were free to
   drift, and a strip that disagrees with its stage either clips the band or
   floats above it. */
.below.footer-open { padding-bottom: calc(var(--flow-footer-clear) + 141px); }

.band-slot {
  position: relative;
  flex: 0 0 auto;
  height: calc(min(var(--flow-map-w), 100vw - 32px) * var(--band-ratio) + 20px);
  /* Same curve and duration as the box that causes it (FlowHeader .nd.op.anim),
     so the strip opens WITH the box and not after it. */
  transition: height 0.42s cubic-bezier(0.34, 1.28, 0.64, 1);
}
/* The opened box is taller than a node — four stations with three lines each do
   not fit into one, the same wall the flow hit and answered by growing. The
   flow could let its box hang over its canvas; here a scrolling column starts
   directly under the strip, so the strip takes the extra room and gives it back.
   --band-open is the overhang as a fraction of the world width, computed in the
   template from the same two rectangles, because a second copy of these numbers
   in CSS is a second thing to keep in step. */
.band-slot.open {
  height: calc(min(var(--flow-map-w), 100vw - 32px) * (var(--band-ratio) + var(--band-open)) + 20px);
}
@media (prefers-reduced-motion: reduce) {
  .band-slot { transition: none; }
}

/* Nothing in the column shrinks — the column scrolls. .below is a flex column
   with a definite height, so it distributes NEGATIVE space when its content is
   taller than the viewport, and a child may only refuse if its automatic minimum
   size is content-based. FlowCard carries overflow:hidden, which sets that
   minimum to zero: without this rule the boxes holding a flow card were the only
   ones that could give way, so the lyrics were squeezed and clipped — and no
   scrollbar appeared, because after the squeeze nothing overflowed. */
.below > * { flex-shrink: 0; }

.below {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  /* This container is what scrolls, and the board's height decides whether it
     does. Without a reserved gutter that decision changes the width the packer
     measures, and the layout can drive itself across the two-column edge. */
  scrollbar-gutter: stable;
  padding-block: clamp(1rem, 2.5vw, 2rem);
  /* The content column IS the band's column: the same width the stage takes
     (min(--flow-map-w, 100vw - 32px)), centred the same way, done as padding
     so the element itself stays viewport-wide and the scrollbar stays at the
     screen edge. Left-anchored content in a full-width column put the
     recording box on the page margin while the band floated in the middle —
     nothing lined up with anything. t2i's .below is this
     same column, as width, because it is not a scroller. */
  padding-inline: max(16px, calc((100% - var(--flow-map-w)) / 2));
  /* The footer gallery is fixed over the bottom of every page. Collapsed
     height here, expanded below — 140px of gallery plus its padding and
     border, measured off FooterGallery's own .gallery-content. Open, it was
     covering the last 117px of the column, the last of which is the button
     that starts again. */
  padding-bottom: var(--flow-footer-clear);
  transition: padding-bottom 0.2s;

}

/* The board itself has no layout: pack() gives every box a place, and the box
   is moved there rather than laid out. The height comes from the packer too —
   absolutely positioned children cannot give a scroller anything to scroll. */
.board { position: relative; width: 100%; }
/* No height, so the board's height cannot move it — this is what pack() reads. */
.board-probe { width: 100%; height: 0; }
.slot {
  position: absolute;
  top: 0;
  left: 0;
  /* The column width arrives from the board. Writing it per box would resize
     the elements the observer watches. */
  width: var(--col-w, 100%);
  /* Moved, not re-laid-out: a box that already lies on the board slides to its
     new place when a longer one arrives above it, instead of jumping. */
  transition: transform 0.32s cubic-bezier(0.34, 1.1, 0.64, 1);
}
@media (prefers-reduced-motion: reduce) {
  .slot { transition: none; }
}

/* On every other page this box sits in half columns and grid cells, and that
   is what it has here now — half the board. Page width promised a drop target
   audio does not have. */
.rec-box { max-width: 100%; }

/* The player of the flow's own out node (.out-audio in views/x2x_flow.vue),
   at its width, not at a second one. */
.band-audio { width: 92%; height: 34px; }
.band-by { font-size: var(--flow-fs-hint); color: rgba(255, 255, 255, 0.66); text-align: center;
  padding: 0 6px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; }
.lbl { font-size: var(--flow-fs-label); font-weight: 400; color: #e8e8e8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
/* The machines' names and the ▶: the band's own shapes. .cr-model is the
   flow's line (views/x2x_flow.vue), plus what a button needs to look like one.
   The ▶ is sized by the flow's own token (--flow-play, assets/flow-stage.css),
   the one that sizes the flow's start triangle. */
/* The flow's own glyph row (views/x2x_flow.vue), one glyph deep. */
.cr-media { display: flex; align-items: center; gap: 0.34em; font-size: var(--flow-glyph-medium); color: #5a5470; }
.cr-media .g { transition: color 0.25s; }
.cr-media .g.primary { color: #e9e6fb; }

/* The three machines, side by side in the node. Bright is the one that will
   run; the other two stand back without disappearing — they are the choice
   this box exists to offer, so they have to stay readable on the node's own
   #2b2450 (the glyph row's #5a5470 came to 1.97:1 there, which is a shape, not
   a word).

   NEVER wrap. The node has a fixed height and clips what it holds
   (components/FlowHeader.vue), and it clips from both ends, so a second line
   costs the node its own label — measured at 641–648px on a 16px root font,
   and at every width above 640 on a 32px one, where the box is frozen at the
   stage's design width while the type step keeps growing. One line that
   shrinks is what the single name it replaced did, for the same reason.

   The price is paid knowingly between 641 and about 700px: the type step
   floors at 10px while the node keeps shrinking with the viewport, so the
   three names ellipsise there. Below 641 the band destacks and they read in
   full again. The alternatives were a second copy of FlowHeader's destacking
   rule in this page, or a type size below the platform's own floor. */
.cr-models { display: flex; flex-wrap: nowrap; align-items: baseline; justify-content: center;
  gap: 0 0.45em; max-width: 100%; }
.cr-model { font: inherit; font-size: var(--flow-fs-sub); font-weight: 400; color: #a8a2c6;
  min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  background: none; border: none; padding: 0; cursor: pointer; }
/* :not(.a) — without it this beats .cr-model.a on specificity and the pointer
   makes the chosen machine DIMMER than it was. */
.cr-model:hover:not(:disabled):not(.a) { color: #e9e6fb; }
.cr-model.a { color: #cfe0ff; }
.cr-model.held { text-decoration: underline; text-underline-offset: 3px; text-decoration-color: #7f77dd; }
.cr-model:focus-visible { outline: 1px solid #7fb2ff; outline-offset: 2px; }
/* While the chain runs the pick is fixed. The one that IS running stays
   legible — it is the answer to "what is making this" — and the two that are
   not recede rather than all three going flat. */
.cr-model:disabled { cursor: default; }
.cr-model:disabled:not(.a) { color: #6f6a8a; }
.sub { font-size: var(--flow-fs-sub); color: rgba(255, 255, 255, 0.72); text-align: center; padding: 0 6px;
  overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
/* Sized by the flow's own start-triangle step (--flow-play), so it grows with
   the stage the way the flow's does instead of standing at one fixed rem. */
.go { font: inherit; margin-top: 2px; background: none; border: none; color: #7fb2ff; font-size: var(--flow-play); line-height: 1; cursor: pointer; padding: 0 6px; }
.go:disabled { color: #3a4a5e; cursor: default; }

/* A box's back. Same rows as the flow's provenance panel, same reading order. */
/* The provenance rows the flow puts on the back of its own material
   (views/x2x_flow.vue) — its shape and its two colours, not a
   second drawing of them. The heading is this page's addition: the flow's
   backs carry one kind of thing, these carry a station. */
.im-head { font-size: var(--flow-fs-sub); color: #8a8a8a; margin-bottom: 0.45rem; }
.im-row { display: flex; flex-direction: column; gap: 2px; font-size: var(--flow-fs-sub); line-height: 1.5; }
.im-k { color: #8a84a8; }
.im-v { color: #cfc9f2; overflow-wrap: anywhere; }

/* The opened middle box is FlowRunPanel. The one thing it cannot know is the
   band it is standing in: below 640px FlowHeader takes the three nodes off the
   stage and stacks them, so the panel is no longer a quarter of a strip and its
   row has to fold. A context the component has no way to see, reached the way
   Vue provides for exactly that. */
@media (max-width: 640px) {
  /* .gr is the panel's ROOT: a child component's root carries this page's
     scope id too, so it is reachable from here. Everything inside it is not.
     Doubled deliberately: `.gr[data-v-page]` and the panel's own
     `.gr[data-v-panel]` have the SAME specificity, so which one wins would be
     decided by the order two emitted stylesheets happen to land in. */
  .gr.gr { height: auto; }
  .gr :deep(.gr-row) { flex-wrap: wrap; }
  .gr :deep(.gr-st) { flex: 1 1 42%; }
}

/* Thrown out of the middle box: it arrives from where the run is, overshoots
   its place and settles — the same tug the middle box opens with, and the flow's
   own curve. The element only exists once its station has answered, so the
   animation runs on insert and never again. */
/* Short travel on purpose: the card's background is opaque, so every pixel it
   starts above its place is a pixel of the notes column it paints over on the
   way in. Far enough to read as arriving from the band, not far enough to take
   a line of text with it. */
@keyframes thrown {
  from { opacity: 0; transform: translateY(-14px) scale(0.97); }
  to { opacity: 1; transform: none; }
}
/* `backwards`, not `both`: the forward fill holds this animation's last frame —
   `transform: none` — in the animation origin, and that beats anything the
   stylesheet declares. The card's turn (`.asm-item.two.flipped`) is a transform,
   so it was overwritten before it could be seen: holding a station did nothing
   and its back side, with the provenance of the step, could not be reached. The
   backward fill is the one that is needed here anyway (nothing may show before
   the throw starts); at rest the card carries its own identity transform. */
.station.thrown { animation: thrown 0.42s cubic-bezier(0.34, 1.28, 0.64, 1) backwards; }
@media (prefers-reduced-motion: reduce) {
  .station.thrown { animation: none; }
}

/* The box is FlowCard — the same one x2x_flow's nodes throw their output into.
   What is left here is what this page adds to it: room to read in, and the one
   state the flow's cards do not have, a station that did not answer. */
.station { padding: clamp(0.7rem, 1.4vw, 1.1rem); }
/* The failed border the flow already has, in both of its shared components
   (FlowHeader .nd.failed, FlowRunPanel .gr-st.failed). A third red here was a
   third answer to a question the platform had answered twice. */
.station.failed { border-color: #a04040; }

.st-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.6rem; margin-bottom: 0.55rem; }
.st-name { font-size: var(--flow-fs-head); font-weight: 700; }
.st-note { font-size: var(--flow-fs-hint); color: #9a948a; max-width: 70ch; line-height: 1.45; }

/* The page keeps its board; it is not flattened into a single vertical
   column. The boxes had once been
   flattened into one 34rem column that ran down the left edge of a 1000px
   page — a single measure for everything, and half the page empty beside it.
   The board above answers it: half a stage each, and the tall box and the
   short ones on opposite sides so neither column runs out first. */
/* Under 640px the band leaves the stage and stands in the flow (see
   FlowHeader), so the strip stops reserving a fixed height for it. */
/* ...and stops being a header at all: three stacked boxes are not a strip worth
   holding, and holding them cost 29% of a 375x812 screen. The page goes back to
   one document scroll and the band travels with it. */
@media (max-width: 640px) {
  .cover { height: auto; overflow: visible; }
  /* .open too, or it wins on specificity and puts a stage height back on a
     strip that no longer has a stage. */
  .band-slot, .band-slot.open { height: auto; padding-top: 10px; }
  .below { overflow-y: visible; }
}

.band-err { margin: 0; }

.hint.context { border-top: 1px solid rgba(255, 255, 255, 0.09); margin-top: 0.6rem; padding-top: 0.5rem; }
.hint.context .src { color: inherit; text-decoration: underline; text-underline-offset: 2px; white-space: nowrap; }
.ranking { list-style: none; margin: 0; padding: 0; }
.second { margin-top: 0.9rem; padding-top: 0.7rem; border-top: 1px dashed rgba(255, 255, 255, 0.14); }
.second .ranking { margin: 0.35rem 0 0.5rem; opacity: 0.82; }
.ranking li { display: flex; gap: 0.7rem; padding: 0.12rem 0; font-size: var(--flow-fs-sub); }
.score { font-variant-numeric: tabular-nums; color: #8fa88f; min-width: 3.6rem; }
.tail { margin: 0.5rem 0 0; padding-top: 0.45rem; border-top: 1px dashed var(--surface-4); display: flex; gap: 0.5rem; align-items: baseline; flex-wrap: wrap; font-size: var(--flow-fs-sub); color: #b0a898; }
.tail .score { color: #a8776f; }

.transcript { margin: 0; font-size: var(--flow-fs-body); line-height: 1.55; }
.transcript.none { color: #8a857c; font-style: italic; }
.transcript.reading {
  color: #a49d92;
  /* Logical, not physical: ar and he render right-to-left. */
  border-inline-start: 2px solid rgba(255, 255, 255, 0.11);
  padding-inline-start: 0.7rem;
  margin-top: 0.55rem;
}

.tags { margin: 0 0 0.5rem; font-size: var(--flow-fs-sub); color: #b0a898; }
.tags .k { color: #8a857c; }
/* Written material gets the voice font wherever this platform shows it — the
   flow's .asm-ta, .hp-text and .pe-text all stand in it. The one page whose
   product IS a text was rendering it in the UI font. */
.lyrics { margin: 0; white-space: pre-wrap; font-family: var(--font-sans);
  font-size: var(--flow-fs-body); line-height: 1.5; }

.hint { margin: 0.5rem 0 0; font-size: var(--flow-fs-hint); color: #857f76; line-height: 1.45; max-width: 72ch; }
.placeholder { margin: 0; color: #5f5b55; font-size: var(--flow-fs-sub); }
/* The flow's own error colour (.gi-err in views/x2x_flow.vue). */
.err { margin: 0.5rem 0 0; color: #e0568a; font-size: var(--flow-fs-hint); }
</style>
