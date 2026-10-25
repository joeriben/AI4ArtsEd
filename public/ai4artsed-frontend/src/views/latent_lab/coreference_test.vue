<!--
  Bias Archäologie 2 — WinoBias, kept because it answers a different question.

  Zhao, Wang, Yatskar, Ordonez and Chang, "Gender Bias in Coreference Resolution:
  Evaluation and Debiasing Methods", NAACL 2018, 15-20.

  Two sentences one word apart. Who the pronoun refers to is annotated and the
  same in both, so a wrong answer is verifiably wrong. What is measured is a
  DIFFERENCE: does the answer change when "he" becomes "she"? A model passes when
  both readings are decided with the same accuracy.

  That is not a measure of what a model carries — a stereotype applied to every
  reading alike passes this test untouched, and Blodgett et al. (ACL 2021) count
  WinoBias among four such datasets whose validity as measurements they question.
  Bias Archaeology therefore runs BBQ instead.

  This surface is kept for the one place where the difference itself is the
  subject: computer science teaching. What is on show here is a benchmark's
  mechanics — forced choice, swapped options, a differential — not a verdict
  about a model.

  The form is Bias Archaeology's, down to the measure: the left column
  carries which models are asked, which corpus, the pair itself, the axis of the
  sixty pairs, both sentences in the language of the surface, and the note that
  says what all of this is; the column stops where the graph's x-axis runs. The
  graph is the same element as there (see docs/ELEMENT_STRUCTURE_REGISTRY.md,
  "Aufbauende Messgrafik"), including the beat that marks, while the axis is
  walked, what each model made of the pair standing on it.

  One thing does NOT carry over: there the three answers wear the colour of the
  bar they count towards. Here a bar is the outcome of a PAIR, not of a sentence,
  and it differs per model — so there is nothing a single sentence could wear
  without saying something untrue. The per-case reading is the beat in the bars.
-->
<template>
  <div class="ct">
    <!-- The trigger, in the middle of the frame's bar, with the count of
         answers beside it — that was the middle node's second line while there
         was a band. `defer` is not optional: a Teleport resolves its target
         against the live document, and on the app's FIRST render the tree is
         still detached, so `.shell-bar-run` cannot be found (see the same note
         in denoising_archaeology.vue, where the crash it causes was measured). -->
    <ShellRun
      :ready="canRun"
      :running="running"
      :label="t('latentLab.runLine.answer')"
      :count="answered"
      :total="expected"
      @run="startRun"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="ct-text lab-col col-fold-host" :class="{ folded }" :style="{ paddingBottom: axisFromBottom + 'px' }">
            <ColumnFold v-model:folded="folded" />

            <!-- The models that did not answer, each named with its cause. The
                 run goes on with the next model, so the other rows still fill.
                 At the head: this column scrolls at 1210 x 834 (docs/
                 ELEMENT_STRUCTURE_REGISTRY.md, `.lab-prep-err`). -->
            <p ref="failLine" class="lab-prep-err at-head">{{ failures.join(' ') }}</p>

            <!-- Which models are asked. It stood in the band's first node as an
                 interactive FlowNodeHead until 2026-08-21; here it is the
                 platform's own chip picker, directly above the list of what
                 they are asked ABOUT — the two together are what a run is over,
                 and they belong side by side, not one of them in a header. -->
            <ModelPicker
              :model-value="members"
              :disabled="running"
              @update:model-value="setMembers"
            />

            <!-- One field per sentence. A WinoBias item is a pair, and the whole
                 point is that its two sentences differ in a single word; stacked
                 in one box they read as a list and the difference disappears.
                 Fixed height, as over in Bias Archaeology: a box taking its
                 height from its content would move the axis under it with every
                 pair. -->
            <div class="ct-fields">
              <div class="lab-case"><p class="lab-line">{{ pairFirst }}</p></div>
              <div class="lab-case"><p class="lab-line">{{ pairSecond }}</p></div>
            </div>

            <!-- The run walks the corpus and the track fills as far as it has
                 come; afterwards the same way is walked by hand. -->
            <div class="lab-scrub">
              <div class="lab-scrub-label">
                {{ t('latentLab.textLab.coref.scrubLabel', { i: shownIndex + 1, n: pairCount }) }}
              </div>
              <MarkedSlider
                :model-value="shownIndex"
                :min="0"
                :max="Math.max(1, pairCount - 1)"
                :marks="scrubMarks"
                :disabled="running || reached < 2"
                :fill-pct="reachPct"
                :aria-label="t('latentLab.textLab.coref.scrubLabel', { i: shownIndex + 1, n: pairCount })"
                :value-text="t('latentLab.textLab.coref.scrubLabel', { i: shownIndex + 1, n: pairCount })"
                @update:model-value="scrubTo"
              />
            </div>

            <!-- Both sentences in the language of the surface, together and
                 BELOW the axis: they arrive when they arrive, and above the axis
                 their changing height moved the boxes and the handle under the
                 reader's hand. -->
            <div v-if="needsTranslation" class="lab-tr">
              <p>{{ shownFirstTr }}</p>
              <p class="lab-tr-next">{{ shownSecondTr }}</p>
            </div>

            <aside class="lab-note">
              <h3>{{ t('latentLab.textLab.tabs.coref.label') }}</h3>
              <p>{{ drawn
                ? t('latentLab.textLab.coref.noteDrawn', { shown: pairCount, pool: poolSize })
                : t('latentLab.textLab.coref.noteVetted', { shown: pairCount }) }}</p>
              <!-- The note REFERS to WinoBias; the title, the DOI and the
                   attribution the licence requires stand here. -->
              <LabReferences
                flat
                :title="t('latentLab.textLab.coref.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <section class="ct-plot">
            <!-- In the order the bars stand, so the key can be read across them. -->
            <div class="ct-key">
              <span><i class="sw sw-cliche"></i>{{ t('latentLab.textLab.coref.legendCliche') }}</span>
              <span><i class="sw sw-none"></i>{{ t('latentLab.textLab.coref.legendNone') }}</span>
              <span><i class="sw sw-anti"></i>{{ t('latentLab.textLab.coref.legendAnti') }}</span>
            </div>

            <div ref="plotEl" class="ct-canvas">
              <svg class="ct-chart lab-lfo" :viewBox="`0 0 ${VW} ${VH}`" preserveAspectRatio="none">
                <g v-for="g in yTicks" :key="`y${g.v}`">
                  <line v-if="g.v > 0" :x1="PAD_L" :y1="g.y" :x2="VW - PAD_R" :y2="g.y" class="ct-grid" />
                  <text :x="PAD_L - 10" :y="g.y + 4" class="ct-tick" text-anchor="end">{{ g.v }}</text>
                </g>

                <line :x1="PAD_L" :y1="PLOT_T" :x2="PAD_L" :y2="PLOT_B" class="ct-ax" />
                <line :x1="PAD_L" :y1="PLOT_B" :x2="VW - PAD_R" :y2="PLOT_B" class="ct-ax" />

                <g v-for="(s, si) in series" :key="s.id">
                  <g v-for="b in bars(s, si)" :key="b.k">
                    <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" :class="['ct-bar', b.k, { 'lab-hit': b.hit }]" />
                    <text v-if="s.seen > 0" :x="b.cx" :y="b.y - 5" class="ct-count" text-anchor="middle">{{ b.v }}</text>
                  </g>
                  <text :x="sx(si)" :y="PLOT_B + 18" class="ct-name" text-anchor="middle">{{ s.label }}</text>
                  <!-- The measure, and on a SECOND line what it is: at five
                       models a slot is 166 px wide, and the two together ran
                       into the next model's. -->
                  <text v-if="s.seen > 0" :x="sx(si)" :y="PLOT_B + 36" class="ct-score" text-anchor="middle">
                    {{ t('latentLab.textLab.coref.score', { v: signed(netScore(s)), n: s.seen }) }}
                  </text>
                  <text v-if="s.seen > 0" :x="sx(si)" :y="PLOT_B + 52" class="ct-score-note" text-anchor="middle">
                    {{ t('latentLab.textLab.coref.scoreNote') }}
                  </text>
                </g>
              </svg>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { postStreamedRun } from '@/services/directRun'
import ShellRun from '@/components/ShellRun.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'

import ModelPicker from '@/components/ModelPicker.vue'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import { useSafetyLevelStore } from '@/stores/safetyLevel'
import { bringFailureIntoView, generationErrorFor } from '@/composables/useLabRun'

/**
 * The sentence pairs are WinoBias's, and so is the split by occupation that
 * decides which direction a change is called.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Zhao et al. (2018)',
    title: '"Gender Bias in Coreference Resolution: Evaluation and Debiasing Methods"',
    venue: 'NAACL 2018',
    doi: 'https://doi.org/10.48550/arXiv.1804.06876',
    licence: 'MIT licence · github.com/uclanlp/corefBias',
  },
]

const { t, locale } = useI18n()

/* ---------------------------------------------------------------------------
   Which models are compared. The row itself is `components/ModelPicker.vue` —
   it stood here and in Bias Archäologie 1 in the same shape, and since
   2026-08-22 it carries presets over a selection instead of fixed sets. What
   arrives here is only the lineup, smallest first.
   --------------------------------------------------------------------------- */
interface Member { id: string; label: string; vram: number }

const members = ref<Member[]>([])

/** A changed lineup is a changed chart: the bars are per model. */
function setMembers(next: Member[]) {
  if (running.value) return
  members.value = next
  token++
  // The bars go, so the axis goes with them: a filled track over empty bars
  // says sixty pairs were answered where none were.
  shownIndex.value = 0
  reached.value = 0
  layout()
}

/* ---------------------------------------------------------------------------
   The pairs one run walks. At the kids level these are the sixty vetted by
   hand, the same every time; above it the server draws them afresh from the
   whole checked pool, the way Bias Archaeology draws its situations. Which of
   the two it is, is decided on the server from the effective safety level --
   asking from here would let a client pick its own.
   --------------------------------------------------------------------------- */
interface Pair { id: string; group: string; matching: { sentence: string }; other: { sentence: string } }

const safety = useSafetyLevelStore()

const groupPairs = ref<Pair[]>([])
const poolSize = ref(0)
const drawn = ref(false)
const corpusError = ref(false)

const pairCount = computed(() => groupPairs.value.length || 60)

async function drawPairs() {
  try {
    const { data } = await axios.get('/api/text/bias-corpus', { params: { pairs: 60 } })
    groupPairs.value = data?.pairs ?? []
    poolSize.value = Number(data?.pool) || groupPairs.value.length
    drawn.value = !!data?.drawn
    corpusError.value = false
  } catch {
    // A missing dataset is a deployment matter. The surface says nothing is
    // there rather than showing an empty axis as if it had measured nothing.
    corpusError.value = groupPairs.value.length === 0
  }
}

/* The level decides which pairs these are: at `kids` the vetted sixty, above it
   a fresh draw from the whole pool. It can change while the page stands open -
   a course logs in, and the level tightens - and the pairs drawn on the looser
   level must not stay on the surface when it does. */
watch(() => safety.level, () => {
  if (!groupPairs.value.length) return
  drawPairs()
})

/* Which pair is on the axis. The run pushes it forward, a hand moves it after. */
const shownIndex = ref(0)
const reached = ref(0)
const shown = computed(() => groupPairs.value[shownIndex.value] ?? groupPairs.value[0] ?? null)
const pairFirst = computed(() => shown.value?.matching.sentence ?? '')
const pairSecond = computed(() => shown.value?.other.sentence ?? '')

const reachPct = computed(() => {
  const n = pairCount.value
  return n > 1 ? Math.round((Math.max(0, reached.value - 1) / (n - 1)) * 100) : 100
})

const scrubMarks = computed<SliderMark[]>(() => {
  const n = pairCount.value
  return [1, 20, 40, 60].filter(v => v <= n)
    .map(v => ({ value: v, pct: ((v - 1) / Math.max(1, n - 1)) * 100 }))
})

function scrubTo(v: number) {
  // Only as far as the run has come: further along there is no answer to show,
  // and no bar would beat.
  const last = Math.max(0, Math.min(pairCount.value, reached.value) - 1)
  shownIndex.value = Math.max(0, Math.min(last, Math.round(v)))
}

/* ---------------------------------------------------------------------------
   The same pair in the language of the surface. The benchmark is English and
   stays English — the reading stands UNDER it, it does not replace it, and what
   is measured is always the English original.

   A plain translation would destroy the item in every language that marks
   gender on the occupation noun: „the developer" becomes „der Entwickler" or
   „die Entwicklerin", and the sentence answers in its first three words exactly
   what the pronoun is there to leave open. The paired short form keeps it open
   — „ein/e Entwickler/in" — and the pronoun itself is never
   paired, because the pronoun IS the difference the pair is measuring. Both
   halves of that are asked for by name: `style: 'gender_open'`, whose wording
   lives in the endpoint, not here.

   Whether it worked is not assumed, it is CHECKED: a reading whose two
   sentences came back identical has lost the one word the item is about, and
   is not shown. That happens in Turkish, which has no gendered third-person
   pronoun at all — measured, as were the nine languages where it holds.

   The sentences are fixed even where the selection is not: the store is keyed by
   the sentences themselves, so a pair someone else has already read in this
   language reaches no model, whether it was drawn or vetted. A translation that
   fails leaves the English standing.
   --------------------------------------------------------------------------- */
const uiLang = computed(() => String(locale.value || 'en').split('-')[0] ?? 'en')
const translations = ref<Record<string, string[]>>({})
/* One request per case, not one per reason to want it: the store is only
   written when the answer arrives, so mount and watcher fired six calls for
   the first case. */
const pending = new Set<string>()

const shownTranslation = computed(() => translations.value[shown.value?.id ?? ''] ?? null)
const needsTranslation = computed(() => uiLang.value !== 'en' && !!shownTranslation.value)
const shownFirstTr = computed(() => shownTranslation.value?.[0] ?? '')
const shownSecondTr = computed(() => shownTranslation.value?.[1] ?? '')

async function ensureTranslation(p: Pair | null) {
  if (!p || uiLang.value === 'en' || translations.value[p.id] || pending.has(p.id)) return
  pending.add(p.id)
  const parts = [p.matching.sentence, p.other.sentence]
  try {
    // Streamed, not awaited in one silent POST: both sentences go down as ONE
    // call to a cloud model, and the edge in front of this server cuts a request
    // whose origin has sent nothing for about 100 seconds. No `validateStatus`,
    // because the transport throws on a non-2xx exactly as `axios.post` did and
    // the catch below — which leaves the English standing — is written for that.
    const { data } = await postStreamedRun('/api/schema/pipeline/translate', {
      texts: parts,
      target_language: uiLang.value,
      cache_scope: 'winobias',
      style: 'gender_open',
    })
    const out = data?.translated_texts
    // Two sentences that came back as one sentence are not this pair.
    if (Array.isArray(out) && out.length === 2 && out[0] && out[1] && out[0] !== out[1]) {
      translations.value = { ...translations.value, [p.id]: out }
    }
  } catch {
    /* The English stands. A missing reading is not a failed run. */
  } finally {
    pending.delete(p.id)
  }
}

watch(shown, p => { ensureTranslation(p) })
watch(uiLang, () => { translations.value = {}; ensureTranslation(shown.value) })

/* ---------------------------------------------------------------------------
   The run. Each model is asked in batches, so the graph has something to draw
   before the model is through; the batch is small enough to be visible and
   large enough not to pay the round trip per sentence.
   --------------------------------------------------------------------------- */
const BATCH = 10

type Outcome = 'cliche' | 'none' | 'anti'

interface Series {
  id: string; label: string
  seen: number; cliche: number; anti: number
  /** What this model made of each single pair — what the beat in the bars reads. */
  picks: Record<string, Outcome>
}

const series = ref<Series[]>([])
const running = ref(false)
/** One line per model that did not answer in this run: its name and the cause. */
const failures = ref<string[]>([])
const failLine = ref<HTMLElement | null>(null)
// Wherever a model's failure is written, the line has to be readable without
// going looking for it.
watch(() => failures.value.length, (n) => { if (n) void bringFailureIntoView(failLine) })
const answered = ref(0)
const expected = ref(0)
let token = 0

const canRun = computed(() => !running.value && members.value.length > 0 && groupPairs.value.length > 0)

/**
 * The drawing surface measures itself, so ONE unit in the viewBox IS one screen
 * pixel. Encoder Fusion sizes every word with the band's own steps
 * (--flow-fs-*), and a viewBox that scales would size them by the window
 * instead — at 532 px of surface a 13-unit label came out under 7 px.
 */
const plotEl = ref<HTMLElement | null>(null)
const VW = ref(900)
const VH = ref(420)
let ro: ResizeObserver | null = null

const PAD_L = 34, PAD_R = 16, PLOT_T = 14
/* Room under the axis for the name and TWO lines: the measure and what it is. */
const PLOT_B = computed(() => Math.max(PLOT_T + 40, VH.value - 62))

/* Where the axis runs, measured from the foot of the surface — the left column
   is padded by the same amount, so its note ends on that line. */
const axisFromBottom = computed(() => Math.round(VH.value - PLOT_B.value))

function yScale(v: number) {
  const max = pairCount.value || 60
  return PLOT_B.value - (Math.max(0, Math.min(max, v)) / max) * (PLOT_B.value - PLOT_T)
}

const yTicks = computed(() => {
  const max = pairCount.value || 60
  return [0, max / 3, (max * 2) / 3, max].map(v => ({ v: Math.round(v), y: yScale(v) }))
})

/**
 * Three bars per model, one per outcome — that IS the reading, and it needs no
 * scale to be read. The predecessor drew one value against an axis
 * that read as a share, and „30 of 60" was taken to mean the other thirty went
 * the other way. They did not: they did not move at all.
 */
const slotW = computed(() => (VW.value - PAD_L - PAD_R) / Math.max(1, series.value.length))
const BAR_W = computed(() => Math.max(10, Math.min(34, slotW.value * 0.19)))
const BAR_GAP = computed(() => Math.max(3, BAR_W.value * 0.22))

/** Where a model stands. Read from the measured surface, not frozen at layout. */
function sx(i: number) {
  const n = Math.max(1, series.value.length)
  const span = VW.value - PAD_L - PAD_R
  return PAD_L + (n === 1 ? span / 2 : (span * (i + 0.5)) / n)
}

function bars(s: Series, i: number) {
  const stable = Math.max(0, s.seen - s.cliche - s.anti)
  const trio: { k: Outcome; v: number }[] = [
    { k: 'cliche', v: s.cliche },
    { k: 'none', v: stable },
    { k: 'anti', v: s.anti },
  ]
  const w = BAR_W.value
  const left = sx(i) - (w * 3 + BAR_GAP.value * 2) / 2
  const pick = s.picks[shown.value?.id ?? '']
  return trio.map((b, i) => {
    const y = yScale(b.v)
    return {
      k: b.k,
      x: left + i * (w + BAR_GAP.value),
      y,
      w,
      h: Math.max(0, PLOT_B.value - y),
      v: b.v,
      cx: left + i * (w + BAR_GAP.value) + w / 2,
      hit: pick === b.k,
    }
  })
}

/**
 * What the pronoun moved, net: the pairs that tipped towards the cliché minus
 * those that tipped against it. Zero says the two readings were decided alike,
 * which is what the benchmark asks for. It is a DIFFERENCE, not an accuracy — a
 * model that gets everything wrong in both readings scores zero here, and that
 * is the point of the instrument.
 *
 * Counted in PAIRS, not in percent, because it stands under bars that are
 * counts: at 20 red and 0 amber a percentage would print +33 under a bar
 * labelled 20, and nothing on the surface would say what the 33 was of.
 */
function netScore(s: Series): number {
  return s.cliche - s.anti
}

function signed(v: number) { return v > 0 ? `+${v}` : `${v}` }

/* ---------------------------------------------------------------------------
   No history line under the measure, and no run filed. The probe is an argmax
   over log-probs with nothing drawn in it, so at the kids level — where the same
   vetted sixty run every time — a second run reproduces the first exactly:
   measured, two runs over five models, ten byte-identical rows. A "typical"
   value would have been the number standing above it.

   Above that level every run is its own draw from 777 pairs, so a spread does
   arise there and a history line would have something to say. It is not built:
   a measure that means one thing at one level and another at the next needs to
   be decided, not switched on quietly.
   --------------------------------------------------------------------------- */

function layout() {
  const ms = members.value
  series.value = ms.map(m => ({
    id: m.id,
    label: m.label,
    seen: 0, cliche: 0, anti: 0,
    picks: {},
  }))
}

function fold(s: Series, items: any[]) {
  for (const it of items) {
    s.seen++
    const m = !!it?.matching?.correct, o = !!it?.other?.correct
    let k: Outcome = 'none'
    if (m && !o) { s.cliche++; k = 'cliche' }
    else if (!m && o) { s.anti++; k = 'anti' }
    if (typeof it?.id === 'string') s.picks[it.id] = k
  }
}

async function startRun() {
  const mine = ++token
  running.value = true
  answered.value = 0
  failures.value = []
  // Emptied here, not left at the run before: a draw stands between the press
  // and the first answer, and how many pairs it yields is settled only after.
  expected.value = 0
  reached.value = 0
  shownIndex.value = 0
  layout()
  // A run is its own draw: repeating it above the kids level is a second sample
  // and not the same sixty sentences again.
  if (drawn.value) {
    await drawPairs()
    if (mine !== token) return
    ensureTranslation(shown.value)
  }
  const ids = groupPairs.value.map(p => p.id)
  expected.value = ids.length * series.value.length
  try {
    for (const s of series.value) {
      let done = 0
      try {
        for (let i = 0; i < ids.length; i += BATCH) {
          if (mine !== token) return
          const slice = ids.slice(i, i + BATCH)
          // Streamed, like the translation above and for the same reason: sixty
          // pairs on one model outlast what the edge in front of this server
          // allows a silent request, and the heartbeat carries the name of the
          // model at work to the bar (composables/useRunPlace.ts). The transport
          // throws on a non-2xx exactly as `axios.post` did.
          const { data } = await postStreamedRun('/api/text/bias-probe', { model_id: s.id, item_ids: slice })
          if (mine !== token) return
          if (data?.items) { fold(s, data.items); answered.value += data.items.length; done += data.items.length }
          // The axis follows the run and only ever forwards. Every machine walks
          // the same sixty pairs, so the second one would otherwise throw the
          // handle back to the first pair under a track already filled to the end.
          reached.value = Math.max(reached.value, Math.min(ids.length, i + slice.length))
          shownIndex.value = Math.max(shownIndex.value, reached.value - 1)
          series.value = [...series.value]
        }
      } catch (e) {
        if (mine !== token) return
        // One model that fails does not end the run. Its row is emptied, so no
        // half-counted bars stand beside full ones on the same scale, the count
        // stops waiting for its answers, and the next model is asked.
        failures.value = [...failures.value,
          t('latentLab.textLab.models.failed', { model: s.label, cause: generationErrorFor(t, e) })]
        Object.assign(s, { seen: 0, cliche: 0, anti: 0, picks: {} })
        series.value = [...series.value]
        expected.value -= ids.length - done
      }
    }
  } finally {
    if (mine === token) running.value = false
  }
}

onMounted(async () => {
  await drawPairs()
  layout()
  ensureTranslation(shown.value)
})

function measure() {
  if (!plotEl.value) return
  VW.value = Math.max(320, Math.round(plotEl.value.clientWidth))
  VH.value = Math.max(220, Math.round(plotEl.value.clientHeight))
}

onMounted(() => {
  measure()
  ro = new ResizeObserver(measure)
  if (plotEl.value) ro.observe(plotEl.value)
})

onBeforeUnmount(() => {
  token++
  ro?.disconnect()
  ro = null
})

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The frame, as Encoder Fusion measured it (views/surrealizer.vue). */
.ct {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: calc(var(--footer-collapsed-height, 36px) + 1px);
  box-sizing: border-box;
  background: var(--bg-base);
  color: #e2e8f0;
}

.shell-page .ct { padding-bottom: 0; }

/* Frame, proportion, counter and the labels above the controls are shared —
   assets/flow-stage.css, `.lab-main` / `.lab-stage` / `.lab-work` /
   `.lab-prog` / `.lab-pick-label`. */

/* The left column carries its things under each other and scrolls itself when
   the window is short — the graph beside it must not be squeezed for it. */
/* Four lines per box: the longest sentence in the corpus is 138 characters.
   The shared rules are in assets/flow-stage.css (.lab-*). */
.ct-text { gap: 10px; overflow-y: auto; --lab-case-lines: 4; }


.ct-fields { display: flex; flex-direction: column; gap: 6px; }

/* The key sits close over the bars it names, and centred on them. */
.ct-plot { overflow: hidden; gap: 5px; }

/* The drawing surface takes its height from the column, never the other way
   round: the svg is taken out of flow, so its viewBox cannot grow the box that
   measures it. */
.ct-canvas { position: relative; flex: 1; min-height: 0; }
/* `text-anchor: start|end` follows the `direction` property, so under
   the document's `dir="rtl"` (ar, he) a label anchored to one side of
   its x lands on the OTHER side of it. The geometry here is written
   left to right, so the direction is pinned; `unicode-bidi: plaintext`
   still lets each label take its own paragraph direction from its own
   first strong character, so Arabic and Hebrew read correctly inside
   it. Measured 2026-08-29. Same cause and same fix as in
   `views/latent_lab/flow_stations.vue`, where it stands written out. */
.ct-chart { position: absolute; inset: 0; width: 100%; height: 100%; direction: ltr; }
.ct-chart text { unicode-bidi: plaintext; }

.ct-ax { stroke: rgba(255, 255, 255, 0.18); }
.ct-grid { stroke: rgba(255, 255, 255, 0.05); }
.ct-tick { fill: rgba(255, 255, 255, 0.36); font-size: var(--flow-fs-sub); }
.ct-name { fill: rgba(255, 255, 255, 0.75); font-size: var(--flow-fs-label); }
.ct-count { fill: rgba(255, 255, 255, 0.42); font-size: var(--flow-fs-sub); }
.ct-score { fill: rgba(255, 255, 255, 0.62); font-size: var(--flow-fs-sub); }
.ct-score-note { fill: rgba(255, 255, 255, 0.34); font-size: var(--flow-fs-hint); }
.ct-bar.cliche { fill: #c96a5c; }
.ct-bar.none { fill: #7ec89a; }
.ct-bar.anti { fill: #c9a15c; }

/* The three words that make the colours readable. Green is the state the
   sentence pair is asking for: the pronoun changed and the answer did not.
   Both flips are warm, because a choice that tips against the cliché is still
   a choice the pronoun made. */
.ct-key {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px 18px;
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.6);
}

.ct-key .sw {
  display: inline-block;
  width: 0.7em;
  height: 0.7em;
  border-radius: 2px;
  margin-right: 0.45em;
}

.ct-key .sw-cliche { background: #c96a5c; }
.ct-key .sw-none { background: #7ec89a; }
.ct-key .sw-anti { background: #c9a15c; }

@media (max-width: 640px) {
  .ct { height: auto; overflow: visible; }
  .lab-stage { flex: 0 0 auto; }
  .lab-work { grid-template-columns: 1fr; row-gap: 16px; }
  .ct-text { overflow-y: visible; }
}
</style>
