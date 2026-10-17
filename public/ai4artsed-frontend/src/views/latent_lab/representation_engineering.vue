<!--
  Representation Engineering — Zou et al., "Representation Engineering: A
  Top-Down Approach to AI Transparency" (arXiv:2310.01405). That paper alone:
  see the note at the reference list for why Li et al.'s Inference-Time
  Intervention is not cited here.

  Contrast pairs give an axis; the axis is added into the residual stream at one
  layer while the model writes. Nothing is trained here — the reading and the
  steering both happen at inference time (Zou et al., Reading Vector and
  Contrast Vector; LoRRA, the one baseline in that paper that DOES fine-tune, is
  not what runs here).

  The surface was rebuilt. Two things about the old one it does not repeat:

  1. It showed numbers where it meant a judgement — a projection of 0.7421 next
     to each pair, on a scale nothing named. What a pair does to the axis is now
     a COLOUR at the pair and three lines of legend, fed by `agreement`, the
     cosine in [-1, 1] the service returns per pair.
  2. It put two big boxes on the right and one run in them, so no second run
     could ever be compared with the first. The right side is now a GRID that
     grows downward: one column per strength, one row per press, so the
     outputs of different runs stand under each other for comparison.

  The row form is the one the registry calls `Zeilenraster ueber Ziehungen`:
  column = a parameter value, every further row = a new draw, and the row names
  its constants ONCE at its head. Its only implementation, Guidance and
  Temperature, was removed on 2026-08-23; what is taken from it is the form and
  its discipline, not its file. Two rules carry over and both matter here:
  the row HOLDS ITS PROMPT (the field is read once, when the row is made), and
  the seed stands at the row and reads what the run reported — otherwise "same
  seed" is a claim and not a statement. What is NOT taken over is the cell: there
  it is a generated medium (`MediaGridCell`), here it is text.

  There is no interpretation agent on this surface any more. What the two texts
  show is said by Help, which sees this page through `pageContext`. Help has
  the authority for interpretation and needs to see the outputs for it.
-->
<template>
  <div class="re">
    <!-- The trigger, in the middle of the frame's bar. `defer` is not optional:
         a Teleport resolves its target against the live document, and on the
         app's FIRST render the tree is still detached, so `.shell-bar-run`
         cannot be found. -->
    <ShellRun
      :ready="canRun"
      :running="running"
      :label="t('latentLab.runLine.answer')"
      :count="answered"
      :total="3"
      @run="startRun"
    />

    <div v-if="errorMessage" class="error-banner" @click="errorMessage = ''">
      {{ errorMessage }}
    </div>

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <!-- LEFT: everything that prepares a run. -->
          <section class="re-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- Which model is read. Chips, not a drop-down: four short
                 names that fit on one line, and a list of four says more about
                 itself standing open than folded behind a click. The `aside`
                 carries what the name leaves out - how much of the card the
                 model asks for, or the form it would have to be squeezed into
                 to fit at all. -->
            <div class="lab-pick-label">{{ t('latentLab.textLab.modelPanel.presetLabel') }}</div>
            <ChipSelect
              :model-value="selectedPreset"
              :options="modelChoices"
              :columns="4"
              :disabled="running"
              @update:model-value="v => (selectedPreset = v as string)"
            />

            <div class="re-pairs">
              <div class="lab-pick-label re-pairs-head">{{ t('latentLab.textLab.repeng.pairsTitle') }}</div>

              <!-- The platform's standard pair, as on Cultural (Un)Known: the
                   drop-down offers ready sets, the fields under it hold what
                   runs and stay writable. A set fills all three pairs at once,
                   because an axis is read from the three TOGETHER and half a
                   set would read half an axis. -->
              <PromptExamples
                :items="pairSetItems"
                :current="contrastPairs[0]?.positive ?? ''"
                :label="t('latentLab.textLab.repeng.pairSetLabel')"
                :disabled="running"
                @pick="applyPairSet"
              />

              <!-- Two equally built fields differing in ONE feature: the
                   platform's `.bias-pair`/`.bias-side`. What that structure
                   carries under the two fields elsewhere — one fixed evaluation
                   sentence from a closed case distinction — is deliberately not
                   here.

                   The reading of a pair stood here briefly as a colour on its
                   left edge, with three lines of key above. The fan below says
                   the same thing and says it exactly: a strip sorted the angle
                   into three steps, the arrow shows the angle, and a redundant
                   strip without a didactic reason is a strip too many. What
                   stays of it is the NUMBER, which is what ties a row to its
                   arrow. -->
              <div
                v-for="(pair, idx) in contrastPairs"
                :key="idx"
                class="bias-pair"
              >
                <b class="re-pair-n">{{ idx + 1 }}</b>
                <div class="bias-side">
                  <input
                    v-model="pair.positive"
                    type="text"
                    class="re-field"
                    :disabled="running"
                    :placeholder="t('latentLab.textLab.repeng.positivePlaceholder')"
                  />
                </div>
                <div class="bias-side">
                  <input
                    v-model="pair.negative"
                    type="text"
                    class="re-field"
                    :disabled="running"
                    :placeholder="t('latentLab.textLab.repeng.negativePlaceholder')"
                  />
                </div>
                <button
                  v-if="contrastPairs.length > 1"
                  class="re-drop"
                  :disabled="running"
                  :title="t('latentLab.textLab.repeng.removePair')"
                  @click="dropPair(idx)"
                >&#x2715;</button>
              </div>

              <!-- Three pairs is the whole set. The reading needs three to
                   have a common direction worth looking at, and a fourth adds a
                   fourth ray to a drawing whose whole point is that three
                   differences already fan wide. -->
              <button
                v-if="contrastPairs.length < MAX_PAIRS"
                class="re-add"
                :disabled="running"
                @click="addPair"
              >
                + {{ t('latentLab.textLab.repeng.addPair') }}
              </button>

              <!-- The pairs together, after the pairs one by one, and as a
                   DRAWING: three differences have three pairwise angles, and
                   three rays from one point on a flat sheet have two free
                   parameters, so no flat picture can carry all three at once.
                   Rather than arrange them by hand, the backend projects them
                   onto the plane the reading itself picks out (the first two
                   right singular vectors) and says how much of the spread that
                   plane keeps. An arrow's LENGTH is how much of that difference
                   the picture holds; what leaves the plane shortens it.

                   This replaces the bar that stood here for a day: how tight the
                   fan is IS `explained_variance`, so the bar said a second time
                   what the picture says once. -->
              <figure v-if="fan.length" class="re-fan">
                <figcaption>
                  {{ fanLabelParts[0] }}<em>{{ t('latentLab.textLab.repeng.fanLabelEmph') }}</em>{{ fanLabelParts[1] }}
                </figcaption>
                <!-- Half the height it had before, and the same angles: the
                     box went from 300x210 to 300x105, so at a given column
                     width the drawing takes half the room. The prompt below it
                     is what the whole surface is a test OF, and it has to be in
                     sight without scrolling. -->
                <svg viewBox="0 0 300 105" role="img" :aria-label="fanAria">
                  <defs>
                    <marker id="re-arrow" viewBox="0 0 8 8" refX="7" refY="4"
                            markerWidth="5.5" markerHeight="5.5" orient="auto">
                      <path d="M0 0 L8 4 L0 8 z" fill="rgb(255 255 255 / 0.5)" />
                    </marker>
                    <marker id="re-arrow-lead" viewBox="0 0 8 8" refX="7" refY="4"
                            markerWidth="5" markerHeight="5" orient="auto">
                      <path d="M0 0 L8 4 L0 8 z" fill="#7ec89a" />
                    </marker>
                  </defs>
                  <!-- what they have in common, pointing at the runs. It is
                       drawn FIRST so the pair arrows lie on top of it: a pair
                       that agrees closely with the common direction runs along
                       the same line, and drawn underneath it disappeared -
                       which hid exactly the case the drawing is there to
                       show. -->
                  <line x1="36" y1="52" x2="82" y2="52" stroke="#7ec89a"
                        stroke-width="2.5" marker-end="url(#re-arrow-lead)" />
                  <!-- each pair's difference, at the angle the projection gives it -->
                  <g v-for="a in fan" :key="a.idx">
                    <line
                      x1="36" y1="52" :x2="a.x" :y2="a.y"
                      stroke="rgb(255 255 255 / 0.5)"
                      stroke-width="1.4"
                      marker-end="url(#re-arrow)"
                    />
                    <text :x="a.lx" :y="a.ly" class="re-fan-n">{{ a.idx + 1 }}</text>
                  </g>
                  <text x="96" y="49" class="re-fan-cap">{{ t('latentLab.textLab.repeng.fanCommonA') }}</text>
                  <text x="96" y="61" class="re-fan-cap">{{ t('latentLab.textLab.repeng.fanCommonB') }}</text>
                  <circle cx="36" cy="52" r="2.5" fill="rgb(255 255 255 / 0.7)" />
                </svg>
                <div class="re-fan-note">{{ t('latentLab.textLab.repeng.fanSpread') }}</div>
              </figure>
            </div>

            <!-- Straight under the drawing, because it is the drawing's
                 arrow that this axis scales: the picture builds one arrow out
                 of the pairs, and the axis says how hard that arrow presses.

                 It sets HOW FAR, and both ways are run at every press and stand
                 as the outer two columns - so a sign here said nothing the grid
                 did not already say, and read as "negative manipulation", which
                 does not exist: -1 and +1 are the same amount of push, aimed at
                 opposite sides of the pairs. -->
            <div class="re-axis">
              <div class="lab-pick-label">{{ t('latentLab.textLab.repeng.strengthLabel') }}</div>
              <MarkedSlider
                v-model="alpha"
                :min="0.5"
                :max="3"
                :step="0.1"
                :marks="alphaMarks"
                :disabled="running"
                :aria-label="t('latentLab.textLab.repeng.strengthLabel')"
                :value-text="alpha.toFixed(1)"
              />
            </div>

            <!-- The sentence the whole surface is a test of, and therefore in
                 sight without scrolling. -->
            <div class="re-prompt">
              <PromptExamples
                :items="promptItems"
                :current="testText"
                :disabled="running"
                @pick="applyExample"
              />
              <MediaInputBox
                chrome="bare"
                :placeholder="t('latentLab.textLab.repeng.testPromptPlaceholder')"
                :value="testText"
                :rows="2"
                :isEmpty="!testText"
                :isFilled="!!testText"
                :disabled="running"
                @update:value="testText = $event"
                @copy="copyTestText"
                @paste="pasteTestText"
                @clear="testText = ''"
              />
            </div>

            <!-- Two controls stood here and stand here no longer.

                 The layer axis: the depth is fixed at the middle of the stack,
                 which is where the reading is taken and where the push goes in.
                 It was offered as a slider for one day and offered nothing - the
                 middle is the position that works, the ends are the positions
                 that do nothing legible, and an axis whose other settings are
                 there to fail is a way of wasting a run, so the layer is fixed
                 on the one value that works. Sending
                 `target_layer: null` lets the backend take the middle of
                 WHATEVER stack the chosen model has, so this stays right when
                 the model is changed; each row reports the layer it used.

                 The reference list stood here, went to the help entry alone,
                 and is BACK: a source belongs on the instrument that runs it,
                 and the help keeps its own copy beside that. What stands at
                 the foot of the page as well is an account of the
                 mechanism. -->
            <!-- What happens here. The platform's `.lab-note` in its own
                 place: the foot of the preparing column, two sentences, open.
                 It REFERS to its source in prose, and the title with its DOI
                 stands IN the box under it, open and not folded away.
                 What runs past ten lines goes to help rather than growing this
                 box. -->
            <aside class="lab-note">
              <h3>{{ t('latentLab.textLab.tabs.repeng.label') }}</h3>
              <p>{{ t('latentLab.textLab.repeng.noteBody') }}</p>
              <LabReferences
                flat
                :title="t('latentLab.textLab.repeng.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <!-- RIGHT: only what came out. One row per press, NEWEST AT THE TOP
               so the current run is always in sight, and the row says once
               what all its cells share. The rows scroll for themselves — the preparing
               column keeps its place while they do, which is the whole reason
               the scrolling sits here and not on the page. -->
          <section class="re-runs">
            <div class="re-rows">
            <!-- Before the first press the row STANDS THERE, dimmed and
                 empty, with its three heads and the settings it would run with:
                 an instrument whose result side is blank until something
                 happens says nothing about what it is going to do, and the
                 other instruments show their result columns dimmed with their
                 headers in the same way. It is built from the same three
                 alphas a press would use, so the heads cannot drift from the
                 real ones. -->
            <div
              v-for="row in displayRows"
              :key="row.id"
              class="re-row"
              :class="{ 'is-preview': row.preview }"
            >
              <div class="re-row-head">
                <span class="re-row-prompt">{{ row.prompt }}</span>
                <span class="re-row-meta">
                  {{ t('latentLab.textLab.repeng.strengthShort') }} <b>{{ row.strength.toFixed(1) }}</b>
                </span>
                <span class="re-row-meta">
                  {{ t('latentLab.textLab.repeng.targetLayerLabel') }}
                  <b>{{ row.layer === null ? '—' : row.layer }}</b>
                </span>
                <span class="re-row-meta">
                  {{ t('compare.control.seedLabel') }}
                  <b>{{ row.seed === null ? '—' : row.seed }}</b>
                </span>
              </div>
              <div class="re-grid">
                <div v-for="(cell, ci) in row.cells" :key="ci" class="re-cell">
                  <!-- The head of a column says which way the DRAWING's arrow
                       was pointed, in the drawing's own colour. It used to say
                       "α +1.0" and wore the same name as the axis in the left
                       column, so two different things went by α on one screen.
                       How hard is said once, at the head of the row. -->
                  <div class="re-cell-head">
                    <b class="re-cell-glyph" :class="{ 'is-off': cell.alpha === 0 }"
                       aria-hidden="true">{{ cellGlyph(cell.alpha) }}</b>
                    <em>{{ cellLabel(cell.alpha) }}</em>
                  </div>
                  <!-- A run that came back empty keeps its cell and says so
                       there: a hole in a row otherwise reads as a cell that has
                       not run yet. -->
                  <p v-if="cell.text" class="re-text">{{ cell.text }}</p>
                  <p v-else-if="row.preview || !cell.done" class="re-text re-text-wait"></p>
                  <p v-else class="re-text re-text-empty">{{ t('compare.control.cellFailed') }}</p>
                </div>
              </div>
            </div>
            </div>

            <button v-if="rows.length && !running" class="re-again" @click="startRun">
              {{ t('compare.control.drawAgain') }}
            </button>
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
import ShellRun from '@/components/ShellRun.vue'
import { postStreamedRun } from '@/services/directRun'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'

import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import { apiBase } from '@/services/labApi'

/**
 * The reading and the steering on this surface are Zou et al.'s, at the middle
 * of the stack and at inference time - the same procedure, not a family
 * resemblance.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Zou et al. (2023)',
    title: '"Representation Engineering: A Top-Down Approach to AI Transparency"',
    venue: 'arXiv 2023',
    doi: 'https://doi.org/10.48550/arXiv.2310.01405',
  },
]

const { t } = useI18n()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord } = useLatentLabRecorder('latent_text_lab')

const errorMessage = ref('')
function showError(msg: string) {
  errorMessage.value = msg
  setTimeout(() => { if (errorMessage.value === msg) errorMessage.value = '' }, 8000)
}

/* ---------------------------------------------------------------------------
   Which model is read
   --------------------------------------------------------------------------- */
interface PresetInfo {
  id: string
  vram_gb: number
  description: string
  suggested_quant?: string | null
}

const presets = ref<Record<string, PresetInfo>>({})
const selectedPreset = ref('small')

const activeModelId = computed(() => {
  const preset = selectedPreset.value ? presets.value[selectedPreset.value] : undefined
  return preset ? preset.id : ''
})

async function fetchPresets() {
  try {
    const resp = await fetch(`${apiBase()}/api/text/presets?scenario=qwen`)
    if (!resp.ok) return
    const data = await resp.json()
    presets.value = data.presets || {}
    const keys = Object.keys(presets.value)
    if (keys.length && !presets.value[selectedPreset.value]) selectedPreset.value = keys[0]!
  } catch { /* GPU service may not be running */ }
}

/**
 * The models as chips, smallest first.
 *
 * The name on the chip is the tail of the id the service reports, never a
 * literal in this file: the platform forbids model identifiers in code, and a
 * hand-written name is one deployment away from naming something that is no
 * longer there. What the name leaves out goes in the `aside` - the size of the
 * card the model wants, or, where it would have to be squeezed, the form of the
 * squeeze.
 */
const modelChoices = computed(() =>
  Object.entries(presets.value)
    .sort((a, b) => (a[1].vram_gb ?? 0) - (b[1].vram_gb ?? 0))
    .map(([key, info]) => ({
      value: key,
      label: info.id.split('/').pop() ?? info.id,
      aside:
        info.suggested_quant === null || info.suggested_quant === undefined
          ? t('latentLab.textLab.modelPanel.wontFit')
          : info.suggested_quant === 'bf16'
            ? `${info.vram_gb} GB`
            : `\u2192${info.suggested_quant}`,
      title: info.description,
    }))
)

/* ---------------------------------------------------------------------------
   The pairs that make the axis
   --------------------------------------------------------------------------- */
const contrastPairs = ref([
  { positive: 'The capital of France is Paris', negative: 'The capital of France is Berlin' },
  { positive: 'Water boils at 100 degrees Celsius', negative: 'Water boils at 50 degrees Celsius' },
  { positive: 'The earth orbits the sun', negative: 'The sun orbits the earth' },
])

/**
 * The sets a reader can take instead of writing three pairs.
 *
 * The SENTENCES stand here in English and stay untranslated: they go to the
 * model as they are, and a translated pair would read a different axis. What
 * gets translated is the name of the set.
 *
 * Every pair is a MINIMAL edit - the same sentence with one thing turned over -
 * because that is what leaves a single difference for the reading to work on.
 * Two pairs that differ in everything give a direction made of everything.
 *
 * The three sets, and why these:
 *   facts     - the platform's own, a fact against its plain opposite.
 *   orwell    - Nineteen Eighty-Four (Orwell 1949): the Party's three slogans,
 *               each against the plain predicate it overturns. A pair of names
 *               out of the novel stood here for a day and was thrown out - at
 *               war with Eurasia against at war with Eastasia has no true half
 *               and no false one, so there was nothing for a reading to find.
 *               The slogans themselves ('War is Peace' and the like) carry
 *               the contrast.
 *   postTruth - the same correction, one level deeper. Three claims OF the
 *               Trump administration stood here and were thrown out as
 *               structurally unfit: who won an election, how many people came,
 *               which state a hurricane was headed for - each of them one
 *               proper noun swapped for another, which is the set above with
 *               different nouns and no second axis. What stands here instead
 *               turns over the RELATION between a claim and what would settle
 *               it: what a fact is, and whether a case follows the rule it
 *               belongs to or is exempted from it. SUPPLIED WORDING: the first
 *               two pairs.
 *
 * ⚠️ A set is only worth as much as its three differences are DIFFERENT, and
 * that is measurable: the third pair here first followed the second's shape
 * (`..., and <case follows>` against `..., but <case exempted>`), and the two
 * differences then landed on top of each other - measured at Qwen3-14B, layer
 * 20, both at 0.7781 agreement and 0.7 degrees off the common direction, so
 * the drawing hid them BOTH under the green arrow and the set read one
 * direction out of what should have been three. A pair that repeats another
 * pair's construction is a wasted pair. The one that stands here now sets a
 * procedure against an assertion in a shape of its own; the three then measure
 * 79, -22 and 3 degrees (14B) and 98, -14 and 28 (4B).
 */
const PAIR_SETS: { id: string; fill: string[] }[] = [
  {
    id: 'facts',
    fill: [
      'The capital of France is Paris', 'The capital of France is Berlin',
      'Water boils at 100 degrees Celsius', 'Water boils at 50 degrees Celsius',
      'The earth orbits the sun', 'The sun orbits the earth',
    ],
  },
  {
    id: 'orwell',
    fill: [
      'War is destruction', 'War is peace',
      'Freedom is self-determination', 'Freedom is slavery',
      'Ignorance is weakness', 'Ignorance is strength',
    ],
  },
  {
    id: 'postTruth',
    fill: [
      'A fact is a justified true belief', 'A fact is a matter of choice',
      'Planets are spheroids, and so is the earth',
      'Planets are spheroids, but the earth is flat',
      'Counting the votes decides who won an election',
      'Declaring the winner decides who won an election',
    ],
  },
]

const pairSetItems = computed(() =>
  PAIR_SETS.map(set => ({
    id: set.id,
    label: t(`latentLab.textLab.repeng.pairSets.${set.id}`),
    fill: set.fill,
  }))
)

/** A set fills all three pairs; the fields stay writable afterwards. */
function applyPairSet(item: { fill: string[] }) {
  const pairs: { positive: string; negative: string }[] = []
  for (let i = 0; i + 1 < item.fill.length; i += 2) {
    pairs.push({ positive: item.fill[i] ?? '', negative: item.fill[i + 1] ?? '' })
  }
  if (pairs.length) contrastPairs.value = pairs
}

/** Three, and the button that adds a fourth is gone at three. */
const MAX_PAIRS = 3

const validPairs = computed(() =>
  contrastPairs.value.filter(p => p.positive.trim() && p.negative.trim())
)

function addPair() {
  if (contrastPairs.value.length >= MAX_PAIRS) return
  contrastPairs.value.push({ positive: '', negative: '' })
  reading.value = null
}
function dropPair(idx: number) {
  contrastPairs.value.splice(idx, 1)
  reading.value = null
}
// Edited pairs are a different axis; the colours from the last reading would
// then stand at sentences that never made them.
watch(contrastPairs, () => {
  reading.value = null
}, { deep: true })

/** What the last run read off each pair. `agreement` is a cosine in [-1, 1]. */
interface PairReading {
  positive: string
  negative: string
  agreement: number
  /** Along the steering direction, as a unit vector in the drawing's plane. */
  plane_x?: number
  /** Across it, in the same plane. */
  plane_y?: number
}
const reading = ref<PairReading[] | null>(null)



/**
 * The fan, in the SVG's own coordinates.
 *
 * The backend hands back each difference as a unit vector in the plane of the
 * first two singular vectors: x along the steering direction, y across it. Here
 * that becomes a line from the origin at (36, 52) in a box 300 by 105.
 */
/** Half the angle at which two numbers still read as two. */
const LABEL_GAP = 0.20

const fan = computed(() => {
  const src = reading.value
  if (!src) return []
  const rays: Array<{ idx: number; ux: number; uy: number; ang: number }> = []
  src.forEach((r, idx) => {
    if (typeof r.plane_x !== 'number' || typeof r.plane_y !== 'number') return
    const len = Math.hypot(r.plane_x, r.plane_y)
    if (len < 1e-6) return
    rays.push({
      idx,
      ux: r.plane_x / len,
      uy: -r.plane_y / len, // SVG counts y downwards
      ang: Math.atan2(r.plane_y, r.plane_x),
    })
  })
  // Every arrow at the same radius, the common one included: a longer arrow
  // for the common part would say the opposite of what its share is, and a
  // shorter one for a difference that leaves the plane would say something
  // about this drawing rather than about the pairs.
  const R = 46
  return rays.map((a, i) => {
    // Two pairs at nearly the same angle is the GOOD case - it says the two
    // differ in the same respect - and it put their two numbers in one place,
    // where they read as one smudge. Each further number on an occupied angle
    // steps one notch out along its own arrow, so the order down the ray is the
    // order of the pairs.
    const crowd = rays.slice(0, i).filter(b => {
      const d = Math.abs(a.ang - b.ang) % (2 * Math.PI)
      return Math.min(d, 2 * Math.PI - d) < LABEL_GAP
    }).length
    const LR = R + 11 + crowd * 10
    return {
      idx: a.idx,
      x: 36 + R * a.ux,
      y: 52 + R * a.uy,
      lx: 36 + LR * a.ux - 3,
      ly: 52 + LR * a.uy + 3,
    }
  })
})

const fanAria = computed(() => {
  const parts = (reading.value || []).map((r, i) =>
    typeof r.agreement === 'number'
      ? `${i + 1}: ${Math.round((Math.acos(Math.min(1, Math.max(-1, r.agreement))) * 180) / Math.PI)}°`
      : '')
  return `${t('latentLab.textLab.repeng.fanLabel', { d: t('latentLab.textLab.repeng.fanLabelEmph') })} — ${parts.filter(Boolean).join(', ')}`
})

/**
 * The caption around the one word it leans on. The platform renders i18n
 * strings as plain text, so the emphasis is made of two spans and the sentence
 * keeps ONE key with a placeholder — a translator sees the whole sentence.
 */
const fanLabelParts = computed(() => {
  const raw = t('latentLab.textLab.repeng.fanLabel', { d: '\u0000' })
  const cut = raw.split('\u0000')
  return cut.length === 2 ? cut : [raw, '']
})

/* ---------------------------------------------------------------------------
   What is asked, and how hard
   --------------------------------------------------------------------------- */
const testText = ref('The capital of Germany is')
function copyTestText() { copyToClipboard(testText.value) }
function pasteTestText() { testText.value = pasteFromClipboard() }

const promptItems = computed(() => [
  {
    id: 'capital',
    label: t('latentLab.textLab.repeng.promptExamples.capital'),
    fill: [t('latentLab.textLab.repeng.promptExamples.capital')],
  },
])
function applyExample(item: { fill: string[] }) {
  testText.value = item.fill[0] ?? ''
}

// 1.5, because the surface is a test of whether an assertion can be tipped and
// it should tip on the first press; the axis stays because the comparison
// between two strengths is the thing worth making.
const alpha = ref(1.5)
/**
 * Held still, and not offered.
 *
 * The three cells of a row are meant to differ in alpha and in nothing else. A
 * sampling temperature beside it is a second reason a text can come out
 * different, and it is the reason nobody would be able to rule out. 0.7 is the
 * backend's own default (`text_backend.rep_engineering`), so a row remains
 * reproducible from the seed it reports.
 */
const TEMPERATURE = 0.7

/**
 * The four steps of the axis, each carrying its own word.
 *
 * The second one stands at 1.25 rather than at 1, and for a measured reason:
 * MarkedSlider gives every word the narrowest gap between two marks, so 0.5 and
 * 1 - twenty percent of the track apart - left each word 44 px at a 1280 px
 * window, and 'medium' and 'extreme' broke over two lines there. At 1.25 the
 * gaps are 30/30/40 and every word has 69 px and one line. 1.25 is also the
 * truer place for the word: 0.5 to 2 is the band that stays fluent, and the
 * axis rests at 1.5.
 */
const alphaMarks = computed<SliderMark[]>(() => [
  { value: '0.5', pct: 0, label: t('latentLab.textLab.repeng.alphaMark05') },
  { value: '1.25', pct: 30, label: t('latentLab.textLab.repeng.alphaMark1') },
  { value: '2', pct: 60, label: t('latentLab.textLab.repeng.alphaMark2') },
  { value: '3', pct: 100, label: t('latentLab.textLab.repeng.alphaMark3') },
])
/** The axis holds a distance; the two directions are the outer columns. */
const alphaMagnitude = computed(() => Math.abs(alpha.value))

/**
 * Which way the drawing's arrow was pointed for this column, said with the
 * arrow itself. The green ray in the figure is the direction the pairs have in
 * common; a column runs along it, against it, or with nothing added at all.
 */
function cellGlyph(a: number): string {
  return a === 0 ? '·' : a > 0 ? '→' : '←'
}
function cellLabel(a: number): string {
  // Not `baselineLabel`: that one says "Baseline (without manipulation)",
  // and the word it carries is the one this surface was rebuilt to stop
  // saying. The middle column is the run that was left alone.
  if (a === 0) return t('latentLab.textLab.repeng.colNone')
  return a > 0
    ? t('latentLab.textLab.repeng.colWith')
    : t('latentLab.textLab.repeng.colAgainst')
}
/* ---------------------------------------------------------------------------
   The runs
   --------------------------------------------------------------------------- */
interface RunCell {
  alpha: number
  text: string
  /** This cell has come back. Without it an empty cell reads as a failed one. */
  done?: boolean
}
interface RunRow {
  id: number
  prompt: string
  model: string
  /** Which layer the reading came from; unknown until the first answer. */
  layer: number | null
  strength: number
  seed: number | null
  cells: RunCell[]
  /** The row that stands there before the first press. */
  preview?: boolean
}

const rows = ref<RunRow[]>([])

/**
 * The row a press WOULD make, for as long as none has been made. Same three
 * alphas, same prompt, same strength - only the layer and the seed are unknown
 * before the run, and they say so.
 */
const previewRow = computed<RunRow>(() => {
  const mag = alphaMagnitude.value
  return {
    id: 0,
    prompt: testText.value.trim(),
    model: activeModelId.value,
    layer: null,
    strength: mag,
    seed: null,
    cells: [-mag, 0, mag].map(a => ({ alpha: a, text: '' })),
    preview: true,
  }
})
const displayRows = computed<RunRow[]>(() =>
  rows.value.length ? rows.value : [previewRow.value]
)
let nextRowId = 0
const running = ref(false)

/** How many of the three answers of the current run have come back. */
const answered = ref(0)

const canRun = computed(() =>
  !running.value && !!activeModelId.value && !!testText.value.trim() && validPairs.value.length > 0
)

function signed(v: number): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`
}

/**
 * One press, three answers, three requests that go out TOGETHER.
 *
 * All three used to be asked for in a single call, and it came back after fifty
 * seconds with nothing to see in between and no progress indication in the
 * header. Asked one at a time after that, each cell painted as it arrived - but
 * the three still stood in a queue, because the seed of the first answer was
 * handed to the other two, so a slow first answer held the whole row up.
 *
 * The seed is drawn on this side instead. It travels with all three requests,
 * so „one seed" stays a statement about this row while the three go out at
 * once and every column appears the moment its own answer is there.
 */
async function startRun() {
  if (!canRun.value) return
  running.value = true
  answered.value = 0
  errorMessage.value = ''

  // The row holds its prompt: read ONCE, here, so every cell of this row saw
  // the same sentence even if the field is typed in while the run is out.
  const prompt = testText.value.trim()
  const mag = alphaMagnitude.value
  const alphas = [-mag, 0, mag]
  const seed = Math.floor(Math.random() * 4294967295)

  // The row goes up empty and fills. Its cells carry `done` so that a cell
  // still out reads as waiting rather than as one that came back with nothing.
  rows.value.unshift({
    id: ++nextRowId,
    prompt,
    model: activeModelId.value,
    layer: null,
    strength: mag,
    seed,
    cells: alphas.map(a => ({ alpha: a, text: '' })),
  })
  // Everything below writes through the row the STORE holds. A write to the
  // object built above would reach the surface whenever something else happened
  // to repaint it, which is the long way of saying: at the end of the run.
  const live = rows.value[0]!
  const rowId = live.id

  try {
    await Promise.all(alphas.map(async (a, i) => {
      try {
        // Streamed: reading every layer of a 9B model keeps the card busy for
        // longer than the edge in front of this server allows a silent
        // request, and the heartbeat that holds it open is also what carries
        // the name of the model at work to the bar (lib/sseStream.ts,
        // composables/useRunPlace.ts). `validateStatus` keeps what this call
        // site always did: a refusal is READ, from the `error` in its body,
        // rather than thrown.
        const { data } = await postStreamedRun(`/api/text/rep-engineering`, {
          contrast_pairs: validPairs.value,
          model_id: activeModelId.value,
          // The middle of whatever stack this model has: the backend takes it
          // when none is named, so this stays right across model sizes.
          target_layer: null,
          test_text: prompt,
          alphas: [a],
          temperature: TEMPERATURE,
          seed,
        }, { baseUrl: apiBase(), validateStatus: () => true })
        if (data.error) { showError(data.error); return }

        // The axis is the same in all three answers - the same pairs at the
        // same layer of the same model give the same direction. Whichever
        // answer lands first is the one that puts it on the surface.
        if (live.layer === null) {
          live.layer = data.target_layer
          if (Array.isArray(data.pair_projections)) reading.value = data.pair_projections

          labRecord({
            parameters: {
              tab: 'repeng', action: 'run',
              model_id: activeModelId.value, target_layer: data.target_layer,
              alphas, temperature: TEMPERATURE, seed,
              pair_count: validPairs.value.length, test_text: prompt,
            },
            results: {
              pair_agreement: data.pair_agreement,
              explained_variance: data.explained_variance,
            },
          })
        }

        const hit = (data.generations || []).find((g: RunCell) => g.alpha === a)
        live.cells[i] = { alpha: a, text: hit?.text ?? '', done: true }
        answered.value = live.cells.filter(c => c.done).length
      } catch {
        showError(t('latentLab.textLab.error.operationFailed'))
      }
    }))
  } finally {
    // A run that brought back nothing at all leaves no row behind: an empty row
    // says the press did something, and it did not.
    if (answered.value === 0) rows.value = rows.value.filter(r => r.id !== rowId)
    running.value = false
  }
}

/* ---------------------------------------------------------------------------
   What Help sees of this page
   --------------------------------------------------------------------------- */
/**
 * How many rows travel. Text costs no vision call, so the runs go along instead
 * of being fetched — but a surface that grows without end would put its whole
 * history into every message. The newest rows are the ones a question is about.
 */
const RUNS_IN_CONTEXT = 6

const pageContextStore = usePageContextStore()

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'latent_text_lab.repeng',
  pageContent: {
    inputText: testText.value,
    selectedConfig: activeModelId.value,
    instrumentRuns: rows.value.slice(-RUNS_IN_CONTEXT).flatMap(row =>
      row.cells
        .filter(c => c.text)
        .map(c => ({
          label: `"${row.prompt}" · α ${signed(c.alpha)} · layer ${row.layer} · seed ${row.seed ?? '—'}`,
          text: c.text,
        }))
    ),
  },
}))

watch(pageContext, (ctx) => { pageContextStore.setPageContext(ctx) }, { immediate: true, deep: true })

onMounted(() => { fetchPresets() })
onBeforeUnmount(() => { pageContextStore.clearContext() })

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* This surface FILLS the view, and the two columns travel separately: the
   result rows scroll, the preparing column stays in place.
   Before that the whole thing grew with every press and the frame's work area
   scrolled all of it at once, which carried the pairs and the axis off the top
   as soon as a second row arrived. Now the stage is as high as the frame, the
   rows scroll inside their own column, and what prepares a run stays where a
   hand left it. The preparing column takes its own scrolling for its own sake:
   at 553 px of frame its content runs to 974. */
.re { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.re-prep { overflow-y: auto; padding-right: 4px; }

.error-banner {
  margin: 0 16px 8px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(201, 106, 92, 0.45);
  background: var(--surface-2);
  color: rgba(255, 255, 255, 0.8);
  font-size: var(--flow-fs-sub);
  cursor: pointer;
}

/* --- left column ------------------------------------------------------- */
.re-prep { display: flex; flex-direction: column; gap: 12px; }

.re-field {
  width: 100%;
  background: var(--surface-4);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 9px 12px;
  color: rgba(255, 255, 255, 0.88);
  font-family: inherit;
  font-size: var(--flow-fs-sub);
}
.re-field { background: var(--surface-2); font-size: var(--flow-fs-body); }
.re-field:disabled { opacity: 0.55; }

.re-pairs { display: flex; flex-direction: column; gap: 8px; }
.re-pairs-head { margin-bottom: -2px; }

/* Three tracks: the row's number, the two fields, and the one control that acts
   on the PAIR. The button gets a track instead of being hung outside the box: at
   `right: -22px` it stood in the gap between the two columns, next to the run
   grid it has nothing to do with. */
.bias-pair {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 6px 6px;
}
.bias-side { grid-column: 2; min-width: 0; }

/* The differences as a drawing. The one arrow points right, at the runs. */
.re-fan { margin: 6px 0 0; display: grid; gap: 4px; }
.re-fan figcaption,
.re-fan-note {
  font-size: var(--flow-fs-hint);
  line-height: 1.5;
  color: rgb(255 255 255 / 0.45);
}
/* The one word the caption leans on, lifted out of the quiet level rather than
   coloured: this is the word the whole drawing is about. */
.re-fan figcaption em {
  font-style: normal;
  color: rgb(255 255 255 / 0.8);
}
.re-fan svg { width: 100%; height: auto; overflow: visible; }
.re-fan-n { font-size: 9px; fill: rgb(255 255 255 / 0.5); }
.re-fan-cap { font-size: 9px; fill: #7ec89a; }
.re-pair-n {
  grid-column: 1;
  grid-row: 1 / span 2;
  align-self: center;
  padding-right: 5px;
  font-size: 10px;
  font-weight: 400;
  color: rgb(255 255 255 / 0.4);
}

.re-drop,
.re-add {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.45);
  font-family: inherit;
  font-size: var(--flow-fs-hint);
  cursor: pointer;
}
.re-drop {
  grid-column: 3;
  grid-row: 1 / span 2;
  align-self: center;
  width: 20px;
  height: 20px;
  border: none;
  line-height: 1;
  padding: 0;
}
.re-add { align-self: flex-start; padding: 5px 10px; }
.re-drop:hover,
.re-add:hover { color: rgba(255, 255, 255, 0.75); }
.re-drop:disabled,
.re-add:disabled { opacity: 0.4; cursor: default; }

.re-prompt { display: flex; flex-direction: column; gap: 6px; }

.re-axis { display: flex; flex-direction: column; }

/* --- right column ------------------------------------------------------ */
.re-runs { display: flex; flex-direction: column; gap: 18px; min-height: 0; }

/* Only the rows travel. The column that prepares a run stands still while they
   do, so the pairs and the axis stay where a hand left them. */
.re-rows {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-right: 6px;
}

.re-row { display: flex; flex-direction: column; gap: 6px; }

/* What all cells of this row share, said once. */
.re-row-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 16px;
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.5);
}
.re-row-prompt { color: rgba(255, 255, 255, 0.75); }
.re-row-meta b {
  font-weight: 400;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  color: rgba(255, 255, 255, 0.7);
}

/* Three columns of the same width: two cells side by side differ in the
   strength and in nothing else, and equal width is part of saying that. The
   COLUMN leads the size here, because rows are added and the surface scrolls. */
.re-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.re-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.re-cell-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  font-size: var(--flow-fs-sub);
}
/* The drawing's arrow, in the drawing's colour, so the column and the figure
   in the left-hand column are visibly the same thing. The middle column carries
   a dot at the quiet level: nothing was added there. */
.re-cell-glyph {
  font-weight: 400;
  font-size: 15px;
  line-height: 1;
  color: #7ec89a;
}
.re-cell-glyph.is-off { color: rgba(255, 255, 255, 0.35); }
.re-cell-head em {
  font-style: normal;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.42);
}

.re-text {
  margin: 0;
  font-size: var(--flow-fs-body);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.85);
  white-space: pre-wrap;
}
.re-text-empty { color: rgba(255, 255, 255, 0.35); }
/* An empty cell still has to be a cell, or the row reads as three headings. */
.re-text-wait { min-height: 84px; }

/* The row before the first press: everything at half weight, because it says
   what WOULD happen and nothing that did. */
.re-row.is-preview { opacity: 0.45; }
.re-row.is-preview .re-cell { background: var(--surface-1); }

.re-again {
  align-self: flex-start;
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: var(--surface-2);
  color: rgba(255, 255, 255, 0.7);
  font-family: inherit;
  font-size: var(--flow-fs-sub);
  cursor: pointer;
}
.re-again:hover { color: rgba(255, 255, 255, 0.9); }

@media (max-width: 640px) {
  .lab-work { grid-template-columns: 1fr; row-gap: 16px; }
  .re-grid { grid-template-columns: 1fr; }
}
</style>
