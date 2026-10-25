<!--
  LoRA Explorer — how far an adapter carries, and where it stops.

  Built and named LoRA Reach, renamed before the address was used anywhere.
  The file, the component name and the i18n keys
  (`latentLab.loraReach.*`) stay the workshop shorthand — this codebase's own
  rule (views/latent_lab.vue) is that those never track a display name, only
  the label and the address do.

  The surface runs ONE comparison in four rows, and the four rows are the
  protocol the literature uses for a fine-tuned concept (Ruiz et al. 2023): the
  same prompt, the same seed, the same model, crossed WITH and WITHOUT the
  trigger the adapter was trained under, and WITH and WITHOUT the adapter.

    row 1  model, no trigger    what the model does with this motif anyway
    row 2  model, trigger       how much of the effect the WORDS already carry
    row 3  adapter, trigger     what the training added
    row 4  adapter, no trigger  whether it also works when it is not called

  Row 3 read against row 2 is the reach. Row 4 read against row 1 is the limit:
  there it shows whether the adapter overwrites what the model knew, rather than
  adding to it — the drift that prior preservation was introduced against and
  that later work finds it does not fully prevent (Kim et al. 2025).

  Row 2 is the control the comparison stands on. A trigger like `solarization`
  is an ordinary English word and the base model already answers to it; without
  that row an effect from the words alone would be read as an effect of the
  training.

  The form is the platform's, not a new one: the stage of a measuring instrument
  (`.lab-main` / `.lab-stage` / `.lab-work`, assets/flow-stage.css), the picture
  raster with row names and column heads (`.lab-grid` / `.lab-series`, same
  file), the square surface around every cell (assets/instrument-surface.css)
  and components/MediaGridCell.vue inside it. See
  docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<template>
  <div class="lab-page">
    <!-- `defer` is not optional: a Teleport resolves its target against the live
         document, and on the app's FIRST render the tree is still detached, so
         `.shell-bar-run` cannot be found. -->
    <ShellRun
      :ready="canRun"
      :running="running"
      :title="t('latentLab.loraReach.generate')"
      :label="t('latentLab.runLine.image')"
      :count="done"
      :total="expected"
      @run="startRun"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- Which adapter is compared. ONE at a time: the four rows are the
                 four states of a single adapter, and a second one would be a
                 second comparison rather than a further row. -->
            <label class="lab-pick-label">{{ t('latentLab.loraReach.adapterLabel') }}</label>
            <!-- ONE per line: a project name is a sentence of underscores and
                 wraps to two lines in a narrower field, where a model name in
                 the comparing surfaces does not. -->
            <ChipSelect
              :model-value="adapter"
              :options="adapterChoices"
              :columns="1"
              :disabled="running"
              @update:model-value="v => pickAdapter(v as string)"
            />
            <p v-if="!adapters.length" class="lr-empty">
              {{ t('latentLab.loraReach.noAdapters') }}
            </p>

            <!-- The word the images were captioned under. It comes from the
                 project the adapter was trained in and stays writable: what the
                 trigger IS is a question the surface may be asked to test.

                 FOUR lines, where the comparing surfaces need three: a trigger
                 is several tags (`19th_century_photography, landscape, historic
                 photograph`), the symbols in the corner are cut out of the TEXT
                 so the first line runs short, and on three lines the last word
                 stood half below the edge. It is the one field here whose exact
                 wording IS the measurement, so it is read at a glance. -->
            <label class="lab-pick-label">{{ t('latentLab.loraReach.triggerLabel') }}</label>
            <PromptExamples
              :items="triggerExamples"
              :current="trigger"
              :disabled="running"
              @pick="applyTrigger"
            />
            <MediaInputBox
              chrome="bare"
              v-model:value="trigger"
              input-type="text"
              :rows="4"
              :is-filled="!!trigger"
              :disabled="running"
              :show-preset-button="true"
              :preset-busy="enriching === 'trigger'"
              @copy="copyTrigger"
              @paste="pasteTrigger"
              @clear="clearTrigger"
              @open-preset-selector="openPreset('trigger')"
            />

            <!-- One motif per line, and they become the COLUMNS. A motif close
                 to the training material and one far from it in the same run is
                 what separates an adapter that carries a manner from one that
                 brings its own subjects along. Picking APPENDS a line, because
                 a run compares several of them at once. -->
            <label class="lab-pick-label">{{ t('latentLab.loraReach.motifsLabel') }}</label>
            <PromptExamples
              :items="motifExamples"
              :current="motifs"
              :disabled="running"
              @pick="appendMotif"
            />
            <MediaInputBox
              chrome="bare"
              v-model:value="motifs"
              input-type="text"
              :rows="5"
              :is-filled="!!motifs"
              :disabled="running"
              :show-preset-button="true"
              :preset-busy="enriching === 'motifs'"
              @copy="copyMotifs"
              @paste="pasteMotifs"
              @clear="clearMotifs"
              @open-preset-selector="openPreset('motifs')"
            />

            <label class="lab-pick-label">{{ t('latentLab.loraReach.strengthLabel') }}</label>
            <MarkedSlider
              v-model="strengthPct"
              :min="50"
              :max="100"
              :step="1"
              :marks="strengthMarks"
              :disabled="running"
              :aria-label="t('latentLab.loraReach.strengthLabel')"
              :value-text="`${strengthPct}%`"
            />

            <p v-if="errorMessage" class="lab-prep-err">{{ errorMessage }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <aside class="lab-note">
              <h3>{{ t('latentLab.loraLab.tabs.reach.label') }}</h3>
              <p>{{ t('latentLab.loraReach.noteBody') }}</p>

              <!-- The note refers in prose; the titles with their DOI stand
                   here. -->
              <LabReferences
                :title="t('latentLab.loraReach.referencesTitle')"
                :items="REFERENCES"
                flat
              />
            </aside>
          </section>

          <section class="lab-plot">
            <div
              ref="gridEl"
              class="lab-grid labelled"
              :style="{
                '--lab-grid-cols': columns.length,
                '--lab-grid-rows': rows.length,
                '--lab-grid-cell': cellPx ? `${cellPx}px` : '',
              }"
            >
              <!-- Which of the four states a row is, said once at its left end. -->
              <div class="lab-grid-col">
                <div class="lab-grid-head"></div>
                <div class="lab-series">
                  <div v-for="row in rows" :key="row.key" class="lab-grid-rowname">
                    {{ row.label }}
                  </div>
                </div>
              </div>
              <div v-for="col in columns" :key="col.key" class="lab-grid-col">
                <div class="lab-grid-head">{{ col.head }}</div>
                <div class="lab-series">
                  <div v-for="(cell, ri) in col.cells" :key="cell.key" class="instr-frame">
                    <div class="instr-stack">
                      <MediaGridCell
                        :url="cell.url"
                        :run-id="cell.runId ?? null"
                        :prompt="cellPrompt(col, rows[ri])"
                        :config-id="OUTPUT_CONFIG"
                        :created-at="cell.createdAt"
                        :model-meta="cell.modelMeta ?? null"
                        :duration-ms="cell.durationMs ?? 0"
                        :facts="cellFacts(cell, rows[ri])"
                        :note="cellNote(cell)"
                        :label="rows[ri]?.label"
                        @download="downloadCell(col, cell, rows[ri])"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      single
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import axios from 'axios'
import { postDirectRun, serverSentence } from '@/services/directRun'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { failureKey } from '@/composables/useGenerationStream'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import MediaGridCell from '@/components/MediaGridCell.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'
import { useGridCellWidth } from '@/composables/useGridCellWidth'
import { useRasterRun, uniqueLines, type RasterCell } from '@/composables/useRasterRun'
import { downloadMedia, mediaFileName, runStem } from '@/lib/downloadMedia'

import { STANDARD_SEED } from '@/composables/useSeedAutomatic'
import { apiBase } from '@/services/labApi'
const { t } = useI18n()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const deviceId = useDeviceId()

const baseUrl = apiBase()

/**
 * The adapters trained here are SD 3.5 Large adapters, so the run takes the
 * platform's SD 3.5 Large path and no configuration of its own.
 */
const OUTPUT_CONFIG = 'sd35_large'

/**
 * The seed every picture is made with — THE PLATFORM'S number, the one standing
 * as the default in the generation chunks themselves
 * (`schemas/chunks/output_image_sd35_large.json`), as in Cultural (Un)Known.
 *
 * Here it is a real control, and more of one than it is there: all sixteen
 * pictures come from ONE model on one card, so the same number is the same
 * noise, and what separates two cells is the prompt and the adapter scale
 * alone.
 */
const SEED = STANDARD_SEED

/**
 * What the research the four rows come from actually is. Only what this surface
 * runs: the adapter and its scale, the protocol of the four rows, and the
 * finding that row 4 is looking for.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Hu et al. (2022)',
    title: '"LoRA: Low-Rank Adaptation of Large Language Models"',
    venue: 'ICLR 2022',
    doi: 'https://doi.org/10.48550/arXiv.2106.09685',
  },
  {
    authors: 'Ruiz et al. (2023)',
    title:
      '"DreamBooth: Fine Tuning Text-to-Image Diffusion Models for Subject-Driven Generation"',
    venue: 'CVPR 2023',
    doi: 'https://doi.org/10.48550/arXiv.2208.12242',
  },
  {
    authors: 'Kim et al. (2025)',
    title:
      '"Preserve and Personalize: Personalized Text-to-Image Diffusion Models without Distributional Drift"',
    doi: 'https://doi.org/10.48550/arXiv.2505.19519',
  },
]

/**
 * The motifs the drop-down offers ready-made. They are plain and name no place
 * and no people (`promptExamples.presets.house` is the platform's own line of
 * this kind), because what is under test here is the ADAPTER — a motif that
 * carried a culture of its own would put a second variable into every column.
 *
 * They are deliberately of two kinds: some a trained manner can plausibly cover
 * (a landscape, a street), some it was never shown (a bowl of fruit, a machine).
 * An adapter that answers the second kind with the subjects of its training set
 * rather than with its manner has shown its limit, and the run says so without
 * anybody having to score it.
 */
const MOTIFS: string[] = [
  'a landscape',
  'a busy street',
  'a room with a window',
  'a person',
  'a person at work',
  'first meal of the day',
  'a bowl of fruit',
  'a machine',
]

/** What stands in the motif field when the instrument opens. */
const OPENING_MOTIFS = ['a landscape', 'a person', 'a bowl of fruit']

/**
 * The strength axis, in the design LoRA Explorer takes from Representation
 * Engineering's own axis (`MarkedSlider`, `views/latent_lab/
 * representation_engineering.vue`) — a continuous scale with named notches
 * rather than a closed set of chips.
 *
 * Held as a PERCENT of the adapter's trained strength — 100 % is the strength
 * it was trained at, and what is below it is the dose, read downwards from the
 * full effect rather than upwards from none. The axis runs 50–100 %, a notch
 * every 10 %, moved by the finger in steps of 1 %. Sent to the backend as a
 * fraction (`strengthScale`), the shape `loras[].strength` has always taken.
 *
 * ONE axis, not a second one for each row: a second scale would double the
 * rows and ask a different question (how much), where this surface asks
 * whether and where.
 */
const strengthPct = ref(100)
const strengthScale = computed(() => strengthPct.value / 100)

const strengthMarks = computed<SliderMark[]>(() =>
  [50, 60, 70, 80, 90, 100].map(v => ({
    value: `${v}%`,
    pct: ((v - 50) / (100 - 50)) * 100,
  }))
)

interface LoraEntry {
  file: string
  project: string
  epoch: number | null
  size_mb: number
  modified: number
  /** The word the project's captions were written under; empty if unknown. */
  trigger?: string
}

const adapters = ref<LoraEntry[]>([])
const adapter = ref('')
const trigger = ref('')
const motifs = ref<string>(OPENING_MOTIFS.join('\n'))

/**
 * What is in the cells and the loop that fills them — the same driver Cultural
 * (Un)Known runs on (composables/useRasterRun.ts).
 */
const {
  cells: grid,
  running,
  done,
  expected,
  start,
  recordImage,
  recordBlocked,
  recordFailed,
} = useRasterRun()

const errorMessage = ref('')

/**
 * One entry per project: the finished adapter, or the furthest epoch where a
 * run has no finished one yet. The intermediate epochs are reachable in the
 * Training Studio; here a project IS one adapter, because the four rows are
 * already the comparison.
 */
const finals = computed<LoraEntry[]>(() => {
  const byProject = new Map<string, LoraEntry>()
  for (const entry of adapters.value) {
    const held = byProject.get(entry.project)
    if (!held) {
      byProject.set(entry.project, entry)
      continue
    }
    if (held.epoch === null) continue
    if (entry.epoch === null || entry.epoch > held.epoch) byProject.set(entry.project, entry)
  }
  return [...byProject.values()].sort((a, b) => a.project.localeCompare(b.project))
})

const adapterChoices = computed(() =>
  finals.value.map(e => ({ value: e.file, label: e.project }))
)

const triggerExamples = computed(() =>
  finals.value
    .filter(e => !!e.trigger)
    .map(e => ({ id: e.project, label: e.trigger!, fill: [e.trigger!] }))
)

const motifExamples = computed(() => MOTIFS.map(x => ({ id: x, label: x, fill: [x] })))

/** Every trigger this place has trained, so a field still holding one of them
 *  may be replaced when the adapter changes and a written one may not. */
const knownTriggers = computed(() => new Set(finals.value.map(e => e.trigger).filter(Boolean)))

function pickAdapter(file: string): void {
  adapter.value = file
  const entry = finals.value.find(e => e.file === file)
  const held = trigger.value.trim()
  // A trigger written by hand is the visitor's and stays. One that is still
  // another adapter's, or none at all, is replaced — the field belongs to the
  // adapter above it.
  if (entry?.trigger && (!held || knownTriggers.value.has(held))) {
    trigger.value = entry.trigger
  }
}

/** One motif per line — and each becomes a column. */
const motifLines = computed<string[]>(() => uniqueLines(motifs.value))

function applyTrigger(item: { fill: string[] }): void {
  trigger.value = item.fill[0] ?? ''
}

function appendMotif(item: { fill: string[] }): void {
  const line = item.fill[0] ?? ''
  if (!line) return
  const held = motifs.value.replace(/\s+$/, '')
  motifs.value = held ? `${held}\n${line}` : line
}

function copyTrigger(): void { copyToClipboard(trigger.value) }
function pasteTrigger(): void { trigger.value = pasteFromClipboard() }
function clearTrigger(): void { trigger.value = '' }
function copyMotifs(): void { copyToClipboard(motifs.value) }
function pasteMotifs(): void { motifs.value = pasteFromClipboard() }
function clearMotifs(): void { motifs.value = '' }

/**
 * The perspective in the field's corner. A ready list over a written field and
 * the perspective in it are the platform's mandatory combination for an
 * instrument surface (docs/ELEMENT_STRUCTURE_REGISTRY.md, Rule #13). ONE
 * overlay serves both fields; which one opened it decides where the answer is
 * written back.
 */
type Field = 'trigger' | 'motifs'

const showPresetOverlay = ref(false)
const enriching = ref<Field | ''>('')
let presetTarget: Field = 'motifs'

function openPreset(which: Field): void {
  presetTarget = which
  showPresetOverlay.value = true
}

// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(
  payload: { configId: string; context: string; configName: string }
): Promise<void> {
  showPresetOverlay.value = false
  const which = presetTarget
  const field = which === 'trigger' ? trigger : motifs
  if (!field.value.trim()) return

  enriching.value = which
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, field.value, deviceId)
    if ('written' in outcome) {
      // Only if nothing is being generated. A perspective can take minutes, and
      // a run that started meanwhile reads this field at every single cell —
      // the half of the raster after the answer would be made from another
      // prompt than the half before it, under labels that say otherwise.
      if (!running.value) field.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = ''
  }
}

// ---------------------------------------------------------------------------
// The four rows, the columns, the cells.
// ---------------------------------------------------------------------------
interface Row {
  key: string
  label: string
  /** Whether the trigger stands in front of the motif in this row's prompt. */
  withTrigger: boolean
  /** The LoRA scale. 0 is the model without the adapter — s. `runCell`. */
  scale: number
}

const rows = computed<Row[]>(() => {
  const s = strengthScale.value
  return [
    { key: 'model-plain', label: t('latentLab.loraReach.rowModelPlain'), withTrigger: false, scale: 0 },
    { key: 'model-trigger', label: t('latentLab.loraReach.rowModelTrigger'), withTrigger: true, scale: 0 },
    { key: 'lora-trigger', label: t('latentLab.loraReach.rowLoraTrigger'), withTrigger: true, scale: s },
    { key: 'lora-plain', label: t('latentLab.loraReach.rowLoraPlain'), withTrigger: false, scale: s },
  ]
})

interface Column { key: string; head: string; motif: string; cells: RasterCell[] }

/**
 * The prompt of a cell: the trigger in front of the motif, joined by a comma,
 * exactly as the training captions were written (`{trigger}, {caption}` in
 * services/training_service.py). A row without the trigger is the motif alone.
 */
function cellPrompt(col: Column, row: Row | undefined): string {
  if (!row) return col.motif
  const word = trigger.value.trim()
  return row.withTrigger && word ? `${word}, ${col.motif}` : col.motif
}

/**
 * What identifies a cell: the prompt, the scale, whether the row asked for the
 * trigger, and — only where the scale is above zero — which adapter. NOT its
 * place in the raster. That is what lets a press compute only what is missing:
 * a motif added gives its column new keys and leaves every other cell where it
 * is, and the two rows at scale 0 are the bare model, so they hold across a
 * change of adapter.
 *
 * The trigger flag is in the key even though the prompt normally carries the
 * trigger already. Normally — with the field EMPTY the two prompts of a column
 * are the same string, and without the flag rows 1 and 2 would share one key
 * and rows 3 and 4 another: four rows, two pictures, and two labels naming a
 * trigger that is not there. It happens on the first paint before the adapters
 * have loaded, it happens for good where a project directory is gone and no
 * trigger can be read, and it happens whenever the field is cleared after a
 * run.
 */
function cellKey(prompt: string, scale: number, withTrigger: boolean): string {
  const who = scale > 0 ? adapter.value : 'none'
  return `${who}|${scale}|${withTrigger ? 't' : 'p'}|${prompt}`
}

const columns = computed<Column[]>(() => {
  const out: Column[] = motifLines.value.map(m => ({ key: m, head: m, motif: m, cells: [] }))
  return out.map(c => ({
    ...c,
    cells: rows.value.map(r => {
      const key = cellKey(cellPrompt(c, r), r.scale, r.withTrigger)
      return grid.value[key] ?? { key, url: '', blockedKey: '', failed: false, seed: SEED }
    }),
  }))
})

const { gridEl, cellPx } = useGridCellWidth(() => [columns.value.length, rows.value.length])

/** The back of the card says which state made this picture. */
function cellFacts(cell: RasterCell, row: Row | undefined): string[] {
  const facts = [`seed ${cell.seed}`]
  if (row) facts.push(row.scale > 0 ? `LoRA ${Math.round(row.scale * 100)}%` : 'LoRA 0')
  return facts
}

/**
 * What stands in a cell instead of a medium. The refusal is carried as a KEY
 * until here; the reasons themselves are German developer strings and are
 * never shown raw. A failure stands as the keyed cause where the platform's
 * classifier knows the state, else as the sentence the run answered with, in
 * the wording of the route; the house sentence only where the reply carried no
 * sentence at all.
 */
function cellNote(cell: RasterCell): string {
  if (cell.blockedKey) return t(cell.blockedKey)
  if (cell.failed) return cell.failedKey ? t(cell.failedKey) : (cell.failedText || t('latentLab.loraReach.cellFailed'))
  return ''
}

/**
 * What a press would have to compute: every cell that holds no picture. Row by
 * row, so the two rows at scale 0 run together and the two with the adapter
 * run together — the card then loads the adapter once instead of at every
 * second picture. Where a result lands is untouched by the order; the key is
 * the prompt and the scale.
 */
const pending = computed<{ col: Column; row: Row }[]>(() =>
  rows.value.flatMap(r =>
    columns.value
      .filter(c => !grid.value[cellKey(cellPrompt(c, r), r.scale, r.withTrigger)]?.url)
      .map(c => ({ col: c, row: r }))
  )
)

const canRun = computed(
  () =>
    !running.value &&
    // A perspective is out: what it writes back would land in the middle of the
    // run and change the prompt of every cell after it.
    !enriching.value &&
    !!adapter.value &&
    !!trigger.value.trim() &&
    columns.value.length > 0 &&
    pending.value.length > 0
)

// ---------------------------------------------------------------------------
// The adapters this place has trained.
// ---------------------------------------------------------------------------
async function loadAdapters(): Promise<void> {
  try {
    const res = await axios.get(`${baseUrl}/api/training/loras`)
    adapters.value = res.data?.loras ?? []
  } catch {
    adapters.value = []
    return
  }
  if (finals.value.length && !finals.value.some(e => e.file === adapter.value)) {
    pickAdapter(finals.value[0]!.file)
  }
}

onMounted(loadAdapters)

// ---------------------------------------------------------------------------
// The run. One cell at a time, so the card is asked for one picture at a time.
// ---------------------------------------------------------------------------
const pageContextStore = usePageContextStore()

onBeforeUnmount(() => {
  pageContextStore.clearContext()
})

/**
 * What Help is told stands here. The view name is what the catalogue
 * (platform_items.json) is keyed to; the pictures travel as a directory of
 * runs, one line per cell that came back.
 */
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'lora_reach',
  pageContent: {
    inputText: trigger.value,
    contextPrompt: motifLines.value.join(' · '),
    surfaceMedia: columns.value.flatMap(col =>
      col.cells.flatMap((cell, ri) =>
        cell.runId && cell.url
          ? [{ runId: cell.runId, label: `${col.head} · ${rows.value[ri]?.label ?? ''}` }]
          : [],
      ),
    ),
  },
  offer: columns.value.some(col => col.cells.some(cell => cell.url))
    ? { label: t('compare.ask.sign') }
    : null,
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

async function startRun(): Promise<void> {
  if (!canRun.value) return
  errorMessage.value = ''
  await start(pending.value, step => runCell(step.col, step.row))
}

async function runCell(col: Column, row: Row): Promise<void> {
  const prompt = cellPrompt(col, row)
  const key = cellKey(prompt, row.scale, row.withTrigger)
  try {
    // BOTH kinds of row carry the adapter, the reference rows at scale 0. That
    // keeps them on the same route through the platform: a run WITHOUT the
    // parameter takes the diffusers backend and one with it takes ComfyUI, and
    // the pictures would then differ by the backend as well as by the adapter.
    // At scale 0 the loader hands model and encoders on untouched.
    const res = await postDirectRun({
      prompt,
      output_config: OUTPUT_CONFIG,
      seed: SEED,
      loras: [{ name: adapter.value, strength: row.scale }],
    }, { baseUrl })
    if (!recordImage(key, SEED, res.data)) {
      recordFailed(key, SEED)
      return
    }
    errorMessage.value = ''
  } catch (err: unknown) {
    if (recordBlocked(key, SEED, err)) return
    // Not a refusal, so nothing came through. That lands in its cell as well —
    // otherwise the hole it leaves looks exactly like a cell that has not run.
    // The cell carries the cause: the platform's keyed sentence where the
    // classifier knows the state, else the sentence the run answered with;
    // `unknown` is the classifier's house sentence and is not passed on. The
    // run does NOT stop: the remaining cells are worth having, and the line
    // underneath names the last reason and goes as soon as a picture arrives.
    const e = err as { message?: string }
    const said = serverSentence(err)
    const why = failureKey('error', said ?? e?.message ?? '')
    recordFailed(key, SEED, why === 'generationError.unknown' ? undefined : why, said)
    errorMessage.value = t('latentLab.loraReach.runFailed', { m: generationErrorFor(t, err) })
  }
}

/**
 * The picture of one cell onto the disk. The four states of this comparison are
 * what the reader holds apart, so the row's own key stands in the name.
 */
function downloadCell(col: Column, cell: RasterCell, row: Row | undefined): void {
  if (!cell.url) return
  void downloadMedia(
    cell.url,
    mediaFileName('lorareach', [runStem(cell.runId), col.motif, row?.key, `seed${cell.seed}`]),
  )
}

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* Everything this surface stands on is shared and stands in
   assets/flow-stage.css: the page skeleton (`.lab-page` / `.lab-prep` /
   `.lab-prep-err` / `.lab-plot`), the stage proportion (`.lab-main` /
   `.lab-stage` / `.lab-work` / `.lab-col`) and the picture raster
   (`.lab-grid` / `.lab-series`). What is left here is the one line this
   instrument needs and no other does. */

/* The line that says nothing has been trained yet, where the chips would be. */
.lr-empty { margin: 0; font-size: var(--flow-fs-hint); color: rgba(255, 255, 255, 0.5); }
</style>
