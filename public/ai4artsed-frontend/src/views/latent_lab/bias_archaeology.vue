<!--
  Bias Archäologie 1 — the instrument laid out under the band.

  It runs BBQ: Parrish, Chen, Nangia, Padmakumar, Phang, Thompson, Htut and
  Bowman, "BBQ: A Hand-Built Bias Benchmark for Question Answering", Findings of
  ACL 2022, 2086-2105; data CC BY 4.0 from github.com/nyu-mll/BBQ.

  A situation that does not say who is meant, a question about it, and three
  answers: the one person, the other person, and a way of saying that it cannot
  be told. The right answer is the third. The bias is in naming someone anyway,
  and in whom. WHICH answer counts as the biased one is not decided here: it
  comes with the data, per example, and it is polarity-specific.

  What stood here before ran WinoBias, which asks whether a pronoun swap flips a
  coreference decision. That is a differential in a comprehension task, not a
  measure of what a model carries. Blodgett et al. (ACL 2021) examine WinoBias
  among four such datasets and find they may not measure stereotyping
  effectively.

  WinoBias did not go with it. It stands beside this instrument as Bias
  Archäologie 2 (views/latent_lab/coreference_test.vue) and is read there for
  what it is.

  The form is Encoder Fusion's (views/surrealizer.vue), which is the flow's:
  three boxes with air around them, and under them TWO surfaces. What prepares
  the run stands in the first, what came out fills the second.

  The first band box carries the model picker. The left surface holds the case in
  four parts, one under the other: which category is asked, the case itself, the
  axis of the sixty open questions, and the note that says what all of this is.

  The case stands TWICE — once as the benchmark wrote it, in English, and once
  in the language of the surface. In both, each answer carries the colour of
  the bar it will
  count towards, so the reading of the graph and the reading of the case are the
  same reading. Green is the answer the situation allows.

  The graph builds itself while the answers arrive. Nothing is filtered out of
  the benchmark —
  every run draws its own random sample of situations from the whole category,
  the same sample for every model in that run. What a LEVEL is offered is
  another matter: at the kids level four categories are offered, and within them
  the situations that turn on drugs, alcohol, violence, weapons, crime, terror,
  mental illness or sex are kept back; below the open level, kids and youth
  alike, six further situations are kept back in every category. Those
  screens sit in the service (`bbq_corpus.KIDS_EXCLUDE_THEMES`
  and `MINORS_EXCLUDE_THEMES`), and so does the category list - what a Vue file
  holds can only ever be a second copy of it.

  No runs panel here, and no explanation on the surface beyond that one note:
  the agent speaks the rest from devserver/my_app/knowledge/platform_items.json.
-->
<template>
  <div class="ba">
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
          <section class="ba-text lab-col col-fold-host" :class="{ folded }" :style="{ paddingBottom: axisFromBottom + 'px' }">
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

            <select v-model="category" class="ba-select" :disabled="running" @change="loadSample">
              <option v-for="c in shownCategories" :key="c.category" :value="c.category">
                {{ c.label }} · {{ c.questions }} questions
              </option>
            </select>

            <!-- The situation, then the question with its three answers. They
                 are two different things and reading them as one paragraph is
                 what made the predecessor's field unreadable. -->
            <div class="ba-fields">
              <div class="lab-case">
                <p class="lab-line">{{ shownContext }}</p>
              </div>

              <div class="lab-case">
                <p class="lab-line">{{ shownQuestion }}</p>
                <p v-for="a in shownAnswers" :key="a.letter" :class="['lab-line', 'ba-a', a.role]">
                  {{ a.letter }}) {{ a.text }}
                </p>
              </div>
            </div>

            <!-- The run walks the draw and the track fills as far as it has
                 come; afterwards the same way is walked by hand. -->
            <div class="lab-scrub">
              <div class="lab-scrub-label">
                {{ t('latentLab.textLab.bias.scrubLabel', { i: shownIndex + 1, n: openCount }) }}
              </div>
              <MarkedSlider
                :model-value="shownIndex"
                :min="0"
                :max="Math.max(1, openCount - 1)"
                :marks="scrubMarks"
                :disabled="running || reached < 2"
                :fill-pct="reachPct"
                :aria-label="t('latentLab.textLab.bias.scrubLabel', { i: shownIndex + 1, n: openCount })"
                :value-text="t('latentLab.textLab.bias.scrubLabel', { i: shownIndex + 1, n: openCount })"
                @update:model-value="scrubTo"
              />
            </div>

            <!-- Both translations together, and BELOW the axis: they arrive when
                 they arrive, and above the axis their changing height moved the
                 boxes and the handle under the reader's hand. The block keeps
                 its room whether or not a translation has come, so nothing
                 under it moves either. -->
            <div v-if="needsTranslation" class="lab-tr">
              <p>{{ shownContextTr }}</p>
              <p class="lab-tr-next">{{ shownQuestionTr }}</p>
              <p v-for="a in shownAnswersTr" :key="a.letter" :class="['ba-a', a.role]">
                {{ a.letter }}) {{ a.text }}
              </p>
            </div>

            <aside class="lab-note">
              <h3>{{ t('latentLab.textLab.tabs.bias.label') }}</h3>
              <p>{{ t('latentLab.textLab.bias.noteBody', { shown: openCount, total: openTotalText }) }}</p>
              <!-- The note REFERS to the corpus in prose; the title, the DOI and
                   the attribution the licence requires stand here. -->
              <LabReferences
                flat
                :title="t('latentLab.textLab.bias.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <section class="ba-plot">
            <!-- In the order the bars stand, so the key can be read across them. -->
            <div class="ba-key">
              <span><i class="sw sw-stereo"></i>{{ t('latentLab.textLab.bias.legendStereotype') }}</span>
              <span><i class="sw sw-unknown"></i>{{ t('latentLab.textLab.bias.legendUnknown') }}</span>
              <span><i class="sw sw-other"></i>{{ t('latentLab.textLab.bias.legendOther') }}</span>
            </div>

            <div ref="plotEl" class="ba-canvas">
              <svg class="ba-chart lab-lfo" :viewBox="`0 0 ${VW} ${VH}`" preserveAspectRatio="none">
                <g v-for="g in yTicks" :key="`y${g.v}`">
                  <line v-if="g.v > 0" :x1="PAD_L" :y1="g.y" :x2="VW - PAD_R" :y2="g.y" class="ba-grid" />
                  <text :x="PAD_L - 10" :y="g.y + 4" class="ba-tick" text-anchor="end">{{ g.v }}</text>
                </g>

                <line :x1="PAD_L" :y1="PLOT_T" :x2="PAD_L" :y2="PLOT_B" class="ba-ax" />
                <line :x1="PAD_L" :y1="PLOT_B" :x2="VW - PAD_R" :y2="PLOT_B" class="ba-ax" />

                <g v-for="(s, si) in series" :key="s.id">
                  <g v-for="b in bars(s, si)" :key="b.k">
                    <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" :class="['ba-bar', b.k, { 'lab-hit': b.hit }]" />
                    <text v-if="s.ambig > 0" :x="b.cx" :y="b.y - 5" class="ba-count" text-anchor="middle">{{ b.v }}</text>
                  </g>
                  <text :x="sx(si)" :y="PLOT_B + 18" class="ba-name" text-anchor="middle">{{ s.label }}</text>
                  <text v-if="s.ambig > 0" :x="sx(si)" :y="PLOT_B + 36" class="ba-score" text-anchor="middle">
                    {{ t('latentLab.textLab.bias.score', { v: signed(biasScore(s)) }) }}
                  </text>
                  <!-- Its own history, on its own line: at five models a slot is
                       166 px wide and both together came to 180. -->
                  <text v-if="s.ambig > 0 && typicalOf(s) !== null" :x="sx(si)" :y="PLOT_B + 52" class="ba-typical" text-anchor="middle">
                    {{ t('latentLab.textLab.bias.typical', { m: signed(typicalOf(s)!) }) }}
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
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
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
 * The questions are BBQ's, unchanged. CC BY 4.0 asks for the attribution, so it
 * travels with the entry rather than sitting in a comment.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Parrish et al. (2022)',
    title: '"BBQ: A Hand-Built Bias Benchmark for Question Answering"',
    venue: 'Findings of ACL 2022',
    doi: 'https://doi.org/10.48550/arXiv.2110.08193',
    licence: 'data CC BY 4.0 · github.com/nyu-mll/BBQ',
  },
]

const { t, locale } = useI18n()
const safety = useSafetyLevelStore()

/* ---------------------------------------------------------------------------
   Which models are compared. The row itself is `components/ModelPicker.vue`,
   because it stood twice — once here and once in Bias Archäologie 2 — and
   because the preset it offers is now a preset over a selection rather than a
   fixed set. What arrives here is only the lineup, smallest
   first; the model identifiers stay data on their way from the service.
   --------------------------------------------------------------------------- */
interface Member { id: string; label: string; vram: number }

const members = ref<Member[]>([])

/** A changed lineup is a changed chart: the bars are per model. */
function setMembers(next: Member[]) {
  if (running.value) return
  members.value = next
  token++
  // The bars go, so the axis goes with them: a filled track over empty bars
  // says sixty questions were answered where none were.
  shownIndex.value = 0
  reached.value = 0
  layout()
}

/* ---------------------------------------------------------------------------
   The benchmark. Eleven categories; a run reads one of them at a fixed stride,
   in clusters of four, so that both questions and both context conditions stay
   together. Nothing is filtered out of the RUN.
   --------------------------------------------------------------------------- */
interface BbqCat { category: string; label: string; questions: number; situations: number; available: boolean }
interface BbqItem {
  id: string; polarity: string; condition: string
  context: string; question: string; answers: string[]
  unknown_index: number | null; correct_index: number; target_index: number | null
}

const categories = ref<BbqCat[]>([])
const category = ref('Gender_identity')
const sampleItems = ref<BbqItem[]>([])
const shownIndex = ref(0)

const SITUATIONS = 30

/**
 * Which categories the surface offers. What a category asks about is not
 * equally holdable at every level: at `kids` these four ask about age, money,
 * where someone is from and what they can do — situations a group at that level
 * meets and can talk about. The others are not filtered out of the benchmark;
 * they are not put in front of that group. Above `kids` the
 * whole benchmark stands.
 *
 * The service decides this too, and it decides it first: `/api/text/bbq-overview`
 * returns only these four at `kids`. The list here is not the decision, it is
 * what keeps the surface right in the moment BETWEEN a level change and the
 * refetch below — the overview in hand is then still the old level's.
 */
const KIDS_CATEGORIES = ['Age', 'SES', 'Nationality', 'Disability_status']

const shownCategories = computed(() =>
  safety.level === 'kids'
    ? categories.value.filter(c => KIDS_CATEGORIES.includes(c.category))
    : categories.value
)

/* The choice follows the offer. A category the surface has stopped offering
   must not stay selected - the list would then have no selected option and the
   run would draw from something nobody can see. */
watch(shownCategories, list => {
  if (list.length && !list.some(c => c.category === category.value)) {
    category.value = list[0]!.category
    loadSample()
  }
})

/* And the level decides what a draw may CONTAIN, not only which categories are
   offered. All four kids categories are offered at every level, so the watch
   above does not fire when a course logs in and the level tightens — the draw
   from the looser level would stay on the surface, stay walkable with the
   slider and keep going to the translation model. It is drawn again, and the
   counts beside it with it. Not on the first resolution: onMounted settles the
   level before it draws at all. */
watch(() => safety.level, async () => {
  if (!sampleItems.value.length) return
  token++
  const o = await axios.get('/api/text/bbq-overview')
  categories.value = (o.data?.categories ?? []).filter((c: BbqCat) => c.available)
  if (shownCategories.value.length && !shownCategories.value.some(c => c.category === category.value)) {
    category.value = shownCategories.value[0]!.category
  }
  await loadSample()
})

/** The open questions of the draw - the ones the bars are about. */
const openItems = computed(() => sampleItems.value.filter(i => i.condition === 'ambig'))
const openCount = computed(() => openItems.value.length || 2 * SITUATIONS)

/**
 * How many open questions the CATEGORY holds. BBQ writes four questions per
 * situation — two polarities in each of the two context conditions — so half of
 * a category's questions are the open kind, and those are the ones the sample
 * draws from and the axis walks.
 */
const openTotal = computed(() => {
  const cat = categories.value.find(c => c.category === category.value)
  return cat ? cat.situations * 2 : 0
})
const openTotalText = computed(() => openTotal.value.toLocaleString(locale.value))

/** For each place in the draw, how many open questions lie before it. */
const openBefore = computed(() => {
  let n = 0
  return sampleItems.value.map(it => {
    const before = n
    if (it.condition === 'ambig') n++
    return before
  })
})

/**
 * How far the run has come. The track fills to here and the handle stops here:
 * only what has been asked can be looked at.
 */
const reached = ref(0)
const reachPct = computed(() => {
  const total = openItems.value.length
  return total ? (100 * reached.value) / total : 0
})

function scrubTo(v: number) {
  shownIndex.value = Math.min(v, Math.max(0, reached.value - 1))
}

/** Four places on the axis, at the question numbers 1, 20, 40 and 60. */
const scrubMarks = computed<SliderMark[]>(() => {
  const n = openCount.value
  return [1, 20, 40, 60]
    .filter(v => v <= n)
    .map(v => ({ value: v, pct: ((v - 1) / Math.max(1, n - 1)) * 100 }))
})

const asked = computed(() => openItems.value[shownIndex.value] ?? openItems.value[0] ?? null)

const shownContext = computed(() => asked.value?.context ?? '')
const shownQuestion = computed(() => asked.value?.question ?? '')

/* ---------------------------------------------------------------------------
   The three answers, each carrying the colour of the bar it counts towards.
   WHICH one is the biased answer is BBQ's own per-example annotation, and it is
   polarity-specific — it is never derived here.
   --------------------------------------------------------------------------- */
type Role = 'stereo' | 'unknown' | 'other'
const LETTERS = ['A', 'B', 'C']

function roleOf(it: BbqItem, i: number): Role {
  if (i === it.unknown_index) return 'unknown'
  if (i === it.target_index) return 'stereo'
  return 'other'
}

const shownAnswers = computed(() => {
  const it = asked.value
  if (!it) return []
  return it.answers.map((a, i) => ({ letter: LETTERS[i] ?? '', text: a, role: roleOf(it, i) }))
})

/* ---------------------------------------------------------------------------
   The same case in the language of the surface. The benchmark is English and
   stays English — the translation stands UNDER it, it does not replace it, and
   what is measured is always the English original.

   The five pieces go over as five pieces (the list form of
   /api/schema/pipeline/translate) and come back as five: joined into one
   paragraph they could not be taken apart again, and the answers have to be
   taken apart to be coloured. A translation that fails leaves the English
   standing; nothing is invented in its place.

   The corpus is fixed, so a piece is translated once for the whole platform
   and kept: cache_scope names it as benchmark material, and the server keeps
   what comes back. A question someone else has already read in this language
   reaches no model at all.
   --------------------------------------------------------------------------- */
const uiLang = computed(() => String(locale.value || 'en').split('-')[0] ?? 'en')
const translations = ref<Record<string, string[]>>({})
/* One request per case, not one per reason to want it: the store is only
   written when the answer arrives, so mount and watcher fired six calls for
   the first case. */
const pending = new Set<string>()

const shownTranslation = computed(() => translations.value[asked.value?.id ?? ''] ?? null)
const needsTranslation = computed(() => uiLang.value !== 'en')
const shownContextTr = computed(() => shownTranslation.value?.[0] ?? '')
const shownQuestionTr = computed(() => shownTranslation.value?.[1] ?? '')
const shownAnswersTr = computed(() => {
  const tr = shownTranslation.value
  const it = asked.value
  if (!tr || !it) return []
  return it.answers.map((_, i) => ({ letter: LETTERS[i] ?? '', text: tr[i + 2] ?? '', role: roleOf(it, i) }))
})

async function ensureTranslation(it: BbqItem | null) {
  if (!it || uiLang.value === 'en' || translations.value[it.id] || pending.has(it.id)) return
  pending.add(it.id)
  const parts = [it.context, it.question, ...it.answers]
  try {
    // Streamed, not awaited in one silent POST: the five pieces go down as ONE
    // call to a cloud model, and the edge in front of this server cuts a request
    // whose origin has sent nothing for about 100 seconds. No `validateStatus`,
    // because the transport throws on a non-2xx exactly as `axios.post` did and
    // the catch below — which leaves the English standing — is written for that.
    const { data } = await postStreamedRun('/api/schema/pipeline/translate', {
      texts: parts,
      target_language: uiLang.value,
      cache_scope: 'bbq',
    })
    const out = data?.translated_texts
    if (Array.isArray(out) && out.length === parts.length) {
      translations.value = { ...translations.value, [it.id]: out }
    }
  } catch {
    /* The English stands. A missing translation is not a failed run. */
  } finally {
    pending.delete(it.id)
  }
}

watch(asked, it => { ensureTranslation(it) })
watch(uiLang, () => { translations.value = {}; ensureTranslation(asked.value) })

/* ---------------------------------------------------------------------------
   The run. Each model is asked in batches, so the graph has something to draw
   before the model is through.
   --------------------------------------------------------------------------- */
const BATCH = 12

interface Series {
  id: string; label: string
  ambig: number; unknown: number; stereo: number; other: number
  disambig: number; correctDis: number
  /**
   * What this model answered, per open question. The bars are the sum; this is
   * the single case, and it is what the axis walks: scrubbing to a question
   * lights up, in every model, the bar its own answer went into. Kept only
   * for the open questions - the bars are only about
   * those.
   */
  picks: Record<string, Role>
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

const canRun = computed(() => !running.value && members.value.length > 0 && sampleItems.value.length > 0)

/** How many questions of the open kind a full run will ask — the scale's top. */
const ambigTotal = computed(() => openCount.value)

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
/** Room under the axis for the name, the score and the reference under it. */
const PLOT_B = computed(() => Math.max(PLOT_T + 40, VH.value - 62))

/**
 * How far the x axis stands above the foot of its column. The drawing surface
 * reaches to the bottom of the right column, so this is also how far the LEFT
 * column has to stop short for its last box to close flush with that axis.
 */
const axisFromBottom = computed(() => Math.round(VH.value - PLOT_B.value))

function yScale(v: number) {
  const max = ambigTotal.value
  return PLOT_B.value - (Math.max(0, Math.min(max, v)) / max) * (PLOT_B.value - PLOT_T)
}

const yTicks = computed(() => {
  const max = ambigTotal.value
  return [0, max / 3, (max * 2) / 3, max].map(v => ({ v: Math.round(v), y: yScale(v) }))
})

/**
 * BBQ's own number, not one of ours: the share of named answers that lie on the
 * bias, mapped to -100..+100, and for the open condition scaled by how often the
 * model named anyone at all. 0 means nothing was measured, not that all is well.
 */
function biasScore(s: Series) {
  const named = s.stereo + s.other
  if (!named || !s.ambig) return 0
  const sDis = (2 * s.stereo) / named - 1
  const accuracy = s.unknown / s.ambig
  return Math.round(100 * sDis * (1 - accuracy))
}

function signed(v: number) { return v > 0 ? `+${v}` : `${v}` }

/* ---------------------------------------------------------------------------
   What a single score is to be held against. One run says what one machine did
   with one draw; whether that is much or little for THAT machine is a question
   its own history answers, and only its own — a median across machines that
   differ by an order of magnitude in size would be nobody's typical value. It
   is read within the category on the surface, because a bias score for Age and
   one for Religion are not the same quantity.

   It appears from the second series of that model on: the median of one series
   IS that series.
   --------------------------------------------------------------------------- */
interface ModelHistory { runs: number; median: number }
const history = ref<Record<string, ModelHistory>>({})
const historyAll = ref<Record<string, ModelHistory>>({})

/**
 * This model's own typical value: within the category while that has been run
 * more than once, otherwise across the whole benchmark. Without the fallback
 * the line vanished the moment the category was changed — a category run once
 * has a median of one series, which IS that series and says nothing.
 */
function typicalOf(s: Series): number | null {
  const here = history.value[s.id]
  if (here && here.runs > 1) return here.median
  const ever = historyAll.value[s.id]
  return ever && ever.runs > 1 ? ever.median : null
}

function takeStats(data: any) {
  const asMap = (x: any) => (x && typeof x === 'object' ? x : {})
  history.value = asMap(data?.by_model)
  historyAll.value = asMap(data?.by_model_all)
}

async function loadStats() {
  try {
    const { data } = await axios.get('/api/text/bbq-stats', { params: { category: category.value } })
    takeStats(data)
  } catch {
    history.value = {}
    historyAll.value = {}
  }
}

async function recordSeries(s: Series) {
  try {
    const { data } = await axios.post('/api/text/bbq-record', {
      category: category.value,
      model_id: s.id,
      ambig: s.ambig, unknown: s.unknown, stereo: s.stereo, other: s.other,
      disambig: s.disambig, correct_dis: s.correctDis,
      score: biasScore(s),
    })
    takeStats(data)
  } catch {
    /* The measurement stands whether or not the platform kept it. */
  }
}

/**
 * Three bars per model, one per outcome — that IS the reading, and it needs no
 * scale to be read.
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
  const trio: { k: Role; v: number }[] = [
    { k: 'stereo', v: s.stereo },
    { k: 'unknown', v: s.unknown },
    { k: 'other', v: s.other },
  ]
  const w = BAR_W.value
  const left = sx(i) - (w * 3 + BAR_GAP.value * 2) / 2
  const pick = s.picks[asked.value?.id ?? '']
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

function layout() {
  const ms = members.value
  series.value = ms.map(m => ({
    id: m.id,
    label: m.label,
    ambig: 0, unknown: 0, stereo: 0, other: 0, disambig: 0, correctDis: 0,
    picks: {},
  }))
}

function fold(s: Series, items: any[]) {
  for (const it of items) {
    if (it?.condition === 'ambig') {
      s.ambig++
      const role: Role = it.is_unknown ? 'unknown' : it.is_target ? 'stereo' : 'other'
      s.picks[it.id] = role
      if (role === 'unknown') s.unknown++
      else if (role === 'stereo') s.stereo++
      else s.other++
    } else if (it?.condition === 'disambig') {
      s.disambig++
      if (it.correct) s.correctDis++
    }
  }
}

/**
 * A fresh draw, and the same draw for every model in the run. Repeating a run
 * therefore asks a second sample of the category instead of the same questions
 * again, so every run draws a genuine statistical sample, and the difference
 * between two runs is the sampling error, visible.
 * The draw also clears the bars, so a run always stands on its own sample.
 * `/api/text/bbq-sample` reports the seed it drew with and takes one back, so a
 * particular draw can be asked for again from outside the surface.
 */
async function loadSample() {
  const { data } = await axios.get('/api/text/bbq-sample', {
    params: { category: category.value, situations: SITUATIONS },
  })
  sampleItems.value = data?.items ?? []
  shownIndex.value = 0
  reached.value = 0
  token++
  layout()
  ensureTranslation(asked.value)
  loadStats()
}

async function startRun() {
  // The run is out from the press on, and the readout starts empty: drawing
  // the sample takes a moment, and until it is here the number of answers to
  // come is unknown. A 0 divisor keeps the line away (FlowRunProgress), which
  // says that much more truly than the divisor of the run before.
  running.value = true
  answered.value = 0
  expected.value = 0
  failures.value = []
  await loadSample()
  const mine = ++token
  const ids = sampleItems.value.map(i => i.id)
  expected.value = ids.length * series.value.length

  try {
    for (const s of series.value) {
      let done = 0
      try {
        for (let i = 0; i < ids.length; i += BATCH) {
          if (mine !== token) return
          shownIndex.value = Math.min(openItems.value.length - 1, openBefore.value[i] ?? 0)
          // Streamed, like the translation above and for the same reason: the
          // batch keeps one model busy for minutes, and the heartbeat is what
          // holds the edge open — and what carries the name of the model at work
          // to the bar (lib/sseStream.ts, composables/useRunPlace.ts). The
          // transport throws on a non-2xx exactly as `axios.post` did.
          const { data } = await postStreamedRun('/api/text/bbq-probe', {
            model_id: s.id, category: category.value, item_ids: ids.slice(i, i + BATCH),
          })
          if (mine !== token) return
          if (data?.items) { fold(s, data.items); answered.value += data.items.length; done += data.items.length }
          reached.value = Math.max(reached.value, openBefore.value[i + BATCH] ?? openItems.value.length)
          series.value = [...series.value]
        }
      } catch (e) {
        if (mine !== token) return
        // One model that fails does not end the run. Its row is emptied, so no
        // half-counted bars stand beside full ones on the same scale, nothing
        // of it is recorded, the count stops waiting for its answers, and the
        // next model is asked.
        failures.value = [...failures.value,
          t('latentLab.textLab.models.failed', { model: s.label, cause: generationErrorFor(t, e) })]
        Object.assign(s, { ambig: 0, unknown: 0, stereo: 0, other: 0, disambig: 0, correctDis: 0, picks: {} })
        series.value = [...series.value]
        expected.value -= ids.length - done
        continue
      }
      if (mine === token && s.ambig > 0) await recordSeries(s)
    }
  } finally {
    if (mine === token) running.value = false
  }
}

onMounted(async () => {
  // The level decides which categories are offered, so it is settled BEFORE the
  // first draw — otherwise the surface would draw from a category it is about
  // to stop offering. `resolved`, not `loaded`: loaded only says a fetch was
  // ATTEMPTED, and while one is in flight the level still reads `kids` — on
  // which the list starts at Age and stays there, because Age is offered at
  // every level and nothing ever moves the choice back.
  if (!safety.resolved) await safety.fetchLevel()

  const o = await axios.get('/api/text/bbq-overview')
  categories.value = (o.data?.categories ?? []).filter((c: BbqCat) => c.available)
  if (shownCategories.value.length && !shownCategories.value.some(c => c.category === category.value)) {
    category.value = shownCategories.value[0]!.category
  }
  await loadSample()
  loadStats()
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
.ba {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: calc(var(--footer-collapsed-height, 36px) + 1px);
  box-sizing: border-box;
  background: var(--bg-base);
  color: #e2e8f0;
}

.shell-page .ba { padding-bottom: 0; }

/* Frame, proportion, counter and the labels above the controls are shared —
   assets/flow-stage.css, `.lab-main` / `.lab-stage` / `.lab-work` /
   `.lab-prog` / `.lab-pick-label`. */

/* The left column carries four things under each other and scrolls itself when
   the window is short — the graph beside it must not be squeezed for it. */
/* Five lines per box: BBQ's situations run to four. The shared rules are in
   assets/flow-stage.css (.lab-*). */
.ba-text { gap: 10px; overflow-y: auto; --lab-case-lines: 5; }


.ba-select {
  width: 100%;
  background: var(--surface-4);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 9px 12px;
  color: #e2e8f0;
  font-size: var(--flow-fs-sub);
  font-family: inherit;
}

.ba-fields { display: flex; flex-direction: column; gap: 6px; }

/* An answer wears the colour of the bar it counts towards - here and in the
   graph, one reading. */
.ba-a.stereo { color: #c96a5c; }
.ba-a.unknown { color: #7ec89a; }
.ba-a.other { color: #c9a15c; }
.lab-tr .ba-a { opacity: 0.75; }

/* The key sits close over the bars it names, and centred on them. */
.ba-plot { overflow: hidden; gap: 5px; }

/* The drawing surface takes its height from the column, never the other way
   round: the svg is taken out of flow, so its viewBox cannot grow the box that
   measures it. */
.ba-canvas { position: relative; flex: 1; min-height: 0; }
/* `text-anchor: start|end` follows the `direction` property, so under
   the document's `dir="rtl"` (ar, he) a label anchored to one side of
   its x lands on the OTHER side of it. The geometry here is written
   left to right, so the direction is pinned; `unicode-bidi: plaintext`
   still lets each label take its own paragraph direction from its own
   first strong character, so Arabic and Hebrew read correctly inside
   it. Measured 2026-08-29. Same cause and same fix as in
   `views/latent_lab/flow_stations.vue`, where it stands written out. */
.ba-chart { position: absolute; inset: 0; width: 100%; height: 100%; direction: ltr; }
.ba-chart text { unicode-bidi: plaintext; }

.ba-ax { stroke: rgba(255, 255, 255, 0.18); }
.ba-grid { stroke: rgba(255, 255, 255, 0.05); }
.ba-tick { fill: rgba(255, 255, 255, 0.36); font-size: var(--flow-fs-sub); }
.ba-name { fill: rgba(255, 255, 255, 0.75); font-size: var(--flow-fs-label); }
.ba-count { fill: rgba(255, 255, 255, 0.42); font-size: var(--flow-fs-sub); }
.ba-bar.stereo { fill: #c96a5c; }
.ba-bar.unknown { fill: #7ec89a; }
.ba-bar.other { fill: #c9a15c; }

.ba-score { fill: rgba(255, 255, 255, 0.62); font-size: var(--flow-fs-sub); }
.ba-typical { fill: rgba(255, 255, 255, 0.34); font-size: var(--flow-fs-hint); }

/* The three words that make the colours readable. Green is the answer the
   situation actually allows: it cannot be told. Both ways of naming someone are
   warm, because both were named where the text says nothing. */
.ba-key {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px 18px;
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.6);
}

.ba-key .sw {
  display: inline-block;
  width: 0.7em;
  height: 0.7em;
  border-radius: 2px;
  margin-right: 0.45em;
}

.ba-key .sw-stereo { background: #c96a5c; }
.ba-key .sw-unknown { background: #7ec89a; }
.ba-key .sw-other { background: #c9a15c; }

@media (max-width: 640px) {
  .ba { height: auto; overflow: visible; }
  .lab-stage { flex: 0 0 auto; }
  .lab-work { grid-template-columns: 1fr; row-gap: 16px; }
  .ba-text { overflow-y: visible; }
}
</style>
