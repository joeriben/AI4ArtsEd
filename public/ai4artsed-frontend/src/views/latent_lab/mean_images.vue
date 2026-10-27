<!--
  Mean Images — the average of a model's answer to a seed and a text.

  A picture is computed from two fixed quantities: the starting noise, which the
  seed sets, and the text. The surface holds one of them still and lets the other
  move, generates a set of pictures that way, and lays the set over each other.

    seed fixed    the seed stays, the text moves — n variants of one sentence
    prompt fixed  the text stays, the seed moves — n drawn seeds

  Every row is a model. Each cell holds the whole set, in one of three readings:
  the contact sheet of the single pictures, their mean, or the high-pass stack —
  the fine texture the set shares. Measured on 2026-09-03: with the seed held and
  the text varied, twenty SD 3.5 pictures share composition and fine texture
  (high-pass residuals correlate 0.82–0.93 in flat regions); with the text held
  and the seed varied, the mean dissolves into a composite of the Galton kind.

  The name is Hito Steyerl's. She calls generated pictures mean images —
  statistical averages that stand as single photographs — and the instrument
  gives that average back as an average.

  Nothing here is a form of its own: the stage of a measuring instrument
  (`.lab-main` / `.lab-stage` / `.lab-work`, assets/flow-stage.css), the picture
  raster with row names and column heads (`.lab-grid` / `.lab-series`, same
  file), the square surface around every cell (assets/instrument-surface.css)
  and components/MediaGridCell.vue inside it — the structure of
  views/latent_lab/lora_reach.vue, and the written field with its ready list and
  its perspective ring from views/compare/model_comparison.vue. See
  docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<template>
  <div class="lab-page">
    <ShellRun
      :ready="canRun"
      :running="busy"
      :title="t('latentLab.meanImages.generate')"
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

            <PromptExamples
              :items="promptExamples"
              :current="promptText"
              :disabled="busy"
              @pick="applyExample"
            />
            <MediaInputBox
              chrome="bare"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              v-model:value="promptText"
              input-type="text"
              :rows="4"
              :is-filled="!!promptText"
              :is-loading="readingPicture"
              :disabled="busy || readingPicture"
              :show-preset-button="true"
              :preset-busy="enriching"
              @copy="copyPrompt"
              @paste="pastePrompt"
              @clear="clearPrompt"
              @open-preset-selector="showPresetOverlay = true"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />
            <!-- The reading of a dropped picture, where it did not come back. -->
            <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <!-- The set size stood as three fixed offers and is a slider now.
                 It is a COUNT, and the
                 number therefore stands in the label as well: between two
                 notches the handle alone does not say 37. The top of the axis
                 is the route's own ceiling (MAX_PER_CELL); under two there is
                 no mean to take, only the picture. -->
            <label class="lab-pick-label mi-per-cell">
              {{ t('latentLab.meanImages.perCellLabel') }}<b>{{ perCellCount }}</b>
            </label>
            <MarkedSlider
              v-model="perCell"
              :min="PER_CELL_MIN"
              :max="PER_CELL_MAX"
              :step="1"
              :marks="perCellMarks"
              :disabled="busy"
              :aria-label="t('latentLab.meanImages.perCellLabel')"
              :value-text="String(perCellCount)"
            />

            <label class="lab-pick-label">{{ t('latentLab.meanImages.rowsLabel') }}</label>
            <ChipSelect
              :model-value="chosenModels"
              :options="modelChoices"
              :columns="2"
              multiple
              :disabled="busy"
              @update:model-value="v => (chosenModels = v as string[])"
            />

            <!-- Which reading of the finished cells stands in them: the single
                 pictures as a contact sheet, their mean, their high-pass stack.
                 It starts nothing and costs nothing, and it stood over the
                 raster for that reason until the rule for the one-plus-three
                 column surfaces took hold: every control stands in the left
                 column. So it stands here, last of them, under the
                 choices that make the run. It takes hold once a cell holds
                 something: with the raster empty there is no reading to pick. -->
            <label class="lab-pick-label">{{ t('latentLab.meanImages.viewLabel') }}</label>
            <ChipSelect
              :model-value="view"
              :options="viewChoices"
              :columns="3"
              :disabled="!anyCell"
              @update:model-value="v => (view = v as View)"
            />

            <!-- The seed stands where every instrument of this suite keeps it:
                 shut, under the run's own settings. It is drawn at the press
                 unless somebody opens this and sets one. -->
            <details class="advanced-settings">
              <summary>{{ t('latentLab.meanImages.advancedLabel') }}</summary>
              <div class="settings-grid">
                <SeedControl v-model:seed="seed" v-model:random="randomSeed" :disabled="busy" />
              </div>
            </details>

            <!-- Every picture of the run is made from one of these lines. They
                 stand as they go to the model: plain text, numbered, in the
                 order the run uses them — and shut, because the raster is not
                 read against them. What the raster is read against is the
                 number over the column, and that stands open. -->
            <details v-if="showVariants" class="advanced-settings">
              <summary>{{ t('latentLab.meanImages.variantsLabel') }}</summary>
              <ol class="mi-variants">
                <li v-for="(line, i) in variants" :key="i">{{ line }}</li>
              </ol>
              <!-- A count, not a fault: the state line of the platform answers a
                   condition of the input and asks for nothing. It stands with the
                   lines it is about — the column head already says how many
                   variants the run actually ran with. -->
              <p v-if="shortfall > 0" class="ef-warn">
                {{ t('latentLab.meanImages.variantsShortfall', { n: shortfall }, shortfall) }}
              </p>
            </details>

            <p v-if="errorMessage" class="lab-prep-err">{{ errorMessage }}</p>

            <aside class="lab-note">
              <h3>{{ t('latentLab.imageLab.tabs.mean.label') }}</h3>
              <!-- Steyerl's own account of the mean image. It stands as soon as
                   there is a text for it. -->
              <p v-if="steyerlText">
                <template v-for="(part, i) in steyerlParts" :key="i">
                  <em v-if="i % 2 === 1">{{ part }}</em>
                  <template v-else>{{ part }}</template>
                </template>
              </p>
              <p>
                <template v-for="(part, i) in originParts" :key="i">
                  <em v-if="i % 2 === 1">{{ part }}</em>
                  <template v-else>{{ part }}</template>
                </template>
              </p>

              <LabReferences
                :title="t('latentLab.meanImages.referencesTitle')"
                :items="references"
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
              <!-- Which model a row is, and how far it has come. -->
              <div class="lab-grid-col">
                <div class="lab-grid-head"></div>
                <div class="lab-series">
                  <div v-for="row in rows" :key="row.id" class="lab-grid-rowname stacked">
                    <span>{{ row.label }}</span>
                    <span class="mi-rowline">{{ rowLine(row.id) }}</span>
                  </div>
                </div>
              </div>
              <div v-for="axis in columns" :key="axis" class="lab-grid-col">
                <div class="lab-grid-head">
                  {{ t(`latentLab.meanImages.col.${axis}`) }}
                  <span class="lab-grid-headsub">{{ headSub(axis) }}</span>
                </div>
                <div class="lab-series">
                  <div v-for="row in rows" :key="`${row.id}|${axis}`" class="instr-frame">
                    <div class="instr-stack">
                      <MediaGridCell
                        :url="cellUrl(row.id, axis)"
                        :is-executing="cellExecuting(row.id, axis)"
                        :progress="cellProgress(row.id, axis)"
                        :preview-image="cellPreview(row.id, axis)"
                        :run-id="labRunId"
                        :prompt="translationEn"
                        :config-id="row.id"
                        :created-at="cellMadeAt(row.id, axis)"
                        :facts="cellFacts(row.id, axis)"
                        :note="cellNote(row.id, axis)"
                        :is-favorited="isFavorited"
                        :label="cellPlace(row, axis)"
                        @toggle-favorite="toggleFavorite"
                        @download="downloadCell(row.id, axis)"
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
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import axios from 'axios'
import { postDirectRun, postStreamedRun } from '@/services/directRun'
import {
  generationErrorFor,
  generationErrorKeyFor,
  interceptPrompt,
  perspectiveFailureText,
  type GenerationErrorKey,
} from '@/composables/useLabRun'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import SeedControl from '@/components/SeedControl.vue'
import { useSeedAutomatic } from '@/composables/useSeedAutomatic'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { downloadMedia, mediaFileName, runStem } from '@/lib/downloadMedia'
import MediaGridCell from '@/components/MediaGridCell.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'
import { useGridCellWidth } from '@/composables/useGridCellWidth'
import { useRasterRun, type RasterCell } from '@/composables/useRasterRun'
import { failureKey, safetyBlockKey } from '@/composables/useGenerationStream'
import { useModelAvailability } from '@/composables/useModelAvailability'
import {
  fetchInstrumentRun,
  useLatentLabRecorder,
  type InstrumentRun,
  type RecordOutput,
} from '@/composables/useLatentLabRecorder'
import { useFavoritesStore } from '@/stores/favorites'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { apiBase } from '@/services/labApi'

const { t, locale } = useI18n()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const deviceId = useDeviceId()
const favoritesStore = useFavoritesStore()
const pageContextStore = usePageContextStore()
const { record: labRecord, startSession, sessionId } = useLatentLabRecorder('mean_images')

const baseUrl = apiBase()

/**
 * Where the technique and the name come from. ONE title: the instrument runs
 * Steyerl's figure and nothing else, and a list of what it does not run would be
 * a list of what it cannot be read against.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Steyerl, H. (2025)',
    title: '\u201cMean Images\u201d',
    venue: 'in: Medium Hot: Images in the Age of Heat. Verso',
  },
]

/**
 * The German page quotes the German edition, with that edition's pages, and
 * names it here. Every other language cites the English edition.
 */
const REFERENCES_DE: LabReference[] = [
  {
    authors: 'Steyerl, H. (2025)',
    title: '„Gemeine Durchschnittsbilder“',
    venue: 'in: Medium Hot: Bilder in Zeiten der Hitze. Übers. von Sabine Schulz. Diaphanes',
  },
]
const references = computed(() => (locale.value === 'de' ? REFERENCES_DE : REFERENCES))

/**
 * The two axes a set is made along: one quantity held still, the other moved.
 * Both stand on every raster — the instrument IS the comparison of the two, so
 * there is nothing to pick between them and no chips over them.
 *
 * A third column stood here and is gone: the single
 * picture on the base text and the run's own seed, called the reference. Fifty
 * generated pictures have no reference, and the single pictures of every set
 * stand in the contact sheet already.
 */
type Axis = 'seedFixed' | 'promptFixed'
const AXES: Axis[] = ['seedFixed', 'promptFixed']

type View = 'images' | 'mean' | 'relief'

/**
 * The models a row can be, in the shape Model Comparison holds them (`PRESETS`,
 * views/compare/model_comparison.vue). All five run on this place's own cards.
 *
 * NO PAID MODEL STANDS HERE. Gemini 3
 * Pro Image was offered for a day and is gone: one press on this surface asks for
 * a whole SET per row, so a paid row costs up to fifty calls where the Model
 * Comparison's costs one — and this platform keeps a paid model out of anything a
 * press multiplies. It is not a default that was turned off here, it is not in
 * the list at all.
 *
 * The ORDER is fastest to slowest. The rows of the raster and
 * the model chips both follow this list, so the row that fills soonest stands at
 * the top.
 *
 * The labels are the short forms of the configs' own names, which is how the
 * comparing surfaces write them.
 */
interface ModelOption { id: string; label: string }
const MODELS: ModelOption[] = [
  // The two SD 3.5 rows are the ones whose chunks honour `keep_latent`, so
  // they carry the latent mean this surface is for. The others are
  // averaged in pixels.
  { id: 'sd35_large_turbo', label: 'SD 3.5 Large Turbo' },
  { id: 'commoncanvas_xl_c', label: 'CommonCanvas XL C' },
  { id: 'flux3', label: 'Flux 3 Klein' },
  { id: 'sd35_large', label: 'SD 3.5 Large' },
  { id: 'flux2', label: 'Flux 2' },
]
/**
 * What stands marked when the surface opens: the fastest row, alone. One
 * press asks every
 * marked row for a whole set per column, so five rows marked by default make a
 * press of up to five hundred generations out of a surface nobody has touched.
 * The other rows are marked by hand, for the comparison they are there for.
 */
const OPENING_MODELS = [MODELS[0]!.id]

/**
 * Which of them this installation can actually run.
 *
 * `/api/models/availability` (asked through composables/useModelAvailability.ts,
 * which the Flow and the model choice of five instruments share) walks every
 * output config file that EXISTS and answers `id: true` where every model that
 * config needs is reachable — the card is up and the weights are on disk, or it
 * is a cloud model whose provider holds a key (for Mammouth AI a key it has
 * not refused, with no budget used up that the check finds or that Mammouth
 * AI names; a balance that could not be read for another reason leaves the
 * config `true`). A config that was never installed here is absent from the
 * answer altogether. So
 * `true` is the condition, not the presence of a key: a row that cannot run is
 * not offered, and nobody is told about a model this place does not have.
 *
 * TWO cases keep the list exactly as the constant has it, both because an empty
 * row of chips says less than a row that cannot run: no answer has come yet
 * (the requests failed, or the service is down; a later failure keeps the last
 * answer), and the check came back with nothing available (every backend down
 * at once — a restart, not an installation).
 */
const present = ref<Set<string>>(new Set(MODELS.map(m => m.id)))

/**
 * Whether what stands here came out of the storage. A restored run keeps ITS
 * models: the composites were made and stored, they are on the surface, and a
 * model that has gone missing since must not take its row away — the row is a
 * record, not an offer.
 */
const restored = ref(false)

const { availability, refresh: refreshAvailability } = useModelAvailability()

onMounted(async () => {
  await refreshAvailability()
  const running = Object.entries(availability.value)
    .filter(([, ok]) => ok === true)
    .map(([id]) => id)
  if (!running.length) return
  // A restored run's own models stand beside what is running, so its rows keep
  // their names and its chips keep their marks.
  present.value = new Set(restored.value ? [...running, ...chosenModels.value] : running)
  if (restored.value) return
  // The order stays the list's, never the click order — and a model that cannot
  // run goes out of the selection with it.
  chosenModels.value = chosenModels.value.filter(id => present.value.has(id))
  if (!chosenModels.value.length) {
    // The opening row is the fastest one, and this installation may not carry
    // it. Then the fastest it DOES carry opens the surface, in the list's order.
    const first = MODELS.find(m => present.value.has(m.id))
    chosenModels.value = first ? [first.id] : []
  }
})

/**
 * The ends of the axis the set size is moved along. The top is the route's own
 * ceiling (`MAX_PER_CELL`, routes/mean_images_routes.py) and a test holds the
 * two together; below two pictures there is nothing to average — a set of one
 * IS its picture.
 */
const PER_CELL_MIN = 2
const PER_CELL_MAX = 50

/** The number the surface opens with. */
const OPENING_SEED = 424242

// ---------------------------------------------------------------------------
// What is set before a press
// ---------------------------------------------------------------------------
const promptText = ref('')

/**
 * A picture dropped onto the prompt field is read as a description, and the
 * reading then stands in the field, where it can be worked on further
 * (`composables/usePictureTemplate.ts`). This way in belongs on every FREE
 * prompt field of the lab, and the hint over the field names it.
 */
const {
  reading: readingPicture,
  readingFailedKey,
  handlePicture,
  dropPicture,
} = usePictureTemplate(promptText)
const seed = ref(OPENING_SEED)
/**
 * The seed is drawn at the press unless somebody sets one. Held, every press
 * of this surface starts from
 * the same noise, and two rasters of the same text differ only by the variants
 * the language model happened to write for the second one. Unticked, the
 * platform's seed automatic decides (`composables/useSeedAutomatic.ts`).
 */
const randomSeed = ref(true)
const perCell = ref(5)
const chosenModels = ref<string[]>([...OPENING_MODELS])
const view = ref<View>('mean')

/** The named places on the set-size axis; between them every whole number. */
const perCellMarks = computed<SliderMark[]>(() =>
  [PER_CELL_MIN, 10, 20, 30, 40, PER_CELL_MAX].map(v => ({
    value: v,
    pct: ((v - PER_CELL_MIN) / (PER_CELL_MAX - PER_CELL_MIN)) * 100,
  }))
)
const modelChoices = computed(() =>
  MODELS.filter(m => present.value.has(m.id)).map(m => ({ value: m.id, label: m.label }))
)
const viewChoices = computed(() =>
  (['images', 'mean', 'relief'] as View[]).map(v => ({
    value: v,
    label: t(`latentLab.meanImages.view.${v}`),
  }))
)

/** The columns and the rows of the raster, in the order the constants give. */
const columns = AXES
const rows = computed<ModelOption[]>(() =>
  MODELS.filter(m => present.value.has(m.id) && chosenModels.value.includes(m.id))
)

/**
 * What the run actually asks for: the axis is held inside its own ends, so a
 * size restored from a stored run cannot carry the surface past the route.
 */
const perCellCount = computed(() =>
  Math.min(PER_CELL_MAX, Math.max(PER_CELL_MIN, Math.round(perCell.value)))
)

/**
 * Steyerl's own account of the mean image, where there is one. The key is empty
 * until the text is written, and an empty paragraph would stand as a gap in
 * the box.
 */
/**
 * The second paragraph carries one emphasis, marked *so* in the string; every
 * odd segment is set in italics. The paragraph is text, so the mark stays out
 * of the message and out of the translators' way.
 */
const originParts = computed(() => t('latentLab.meanImages.origin').split('*'))

const steyerlText = computed(() => {
  // Read through the locale fallback: a language without the key shows the
  // English paragraph, as every other line here does. `te` looks at the
  // current language alone and would hide the paragraph until it is translated.
  const key = 'latentLab.meanImages.steyerl'
  const text = t(key)
  return text === key ? '' : text.trim()
})

/**
 * The German paragraph quotes the German edition with its italics, marked *so*
 * in the string as in the second paragraph.
 */
const steyerlParts = computed(() => steyerlText.value.split('*'))

/** Two lines this platform already offers elsewhere, and no third one here. */
const promptExamples = usePromptPresets(['house', 'street'])

function applyExample(item: { fill: string[] }): void {
  promptText.value = item.fill[0] ?? ''
}

function copyPrompt(): void { copyToClipboard(promptText.value) }
function pastePrompt(): void { promptText.value = pasteFromClipboard() }
function clearPrompt(): void { promptText.value = '' }

// ---------------------------------------------------------------------------
// The perspective in the field's corner — the platform's mandatory pair with a
// written field (registry, Rule #13).
// ---------------------------------------------------------------------------
const showPresetOverlay = ref(false)
const enriching = ref(false)

// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!promptText.value.trim()) return

  enriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, promptText.value, deviceId)
    if ('written' in outcome) {
      // A perspective takes minutes, and a run started meanwhile reads this field
      // at every single picture. What comes back after the press is dropped.
      if (!running.value) promptText.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = false
  }
}

// ---------------------------------------------------------------------------
// What a run is made of
// ---------------------------------------------------------------------------
/**
 * The English text every picture of the run is made from, and the variants of it
 * the left-hand column uses. `variants[0]` IS the translation and the first seed
 * of the list IS the run's own, so the first picture of the two columns is one
 * and the same request.
 */
const translationEn = ref('')
const variants = ref<string[]>([])
const shortfall = ref(0)
/**
 * The variants are written while the pictures of the prompt as entered are
 * already being made. `variantsPending` says the call is still out, so a row
 * with one column in does not read as done; `variantsFailed` is the reason
 * where the call came back with nothing, and the column that varies the text
 * says it instead of a set. The reason is kept as the key of its sentence, so
 * a run read back says it in the reader's language.
 */
const variantsPending = ref(false)
const variantsFailed = ref<GenerationErrorKey | null>(null)
/** The seed the run actually worked with; the automatic writes it into the box. */
const runSeed = ref(OPENING_SEED)

/**
 * What a fresh press goes out with except its seed, as one key: what the seed
 * automatic compares the next fresh press with. A completing press draws no
 * seed and is not compared.
 */
function inputsKey(): string {
  return JSON.stringify([promptText.value.trim(), perCellCount.value, rows.value.map(r => r.id)])
}
// null: this instrument keeps none of its fields, so the yardstick starts afresh with them.
const seedAutomatic = useSeedAutomatic(seed, randomSeed, null)
const madeAt = ref(0)

const errorMessage = ref('')
const preparing = ref(false)
/**
 * The CELL the card is working on right now — `model|axis`, or ''.
 *
 * The cell and not the picture: the two columns share their first picture, so a
 * key would light both of them at once on the very first result and the raster
 * would claim two runs where one is out.
 */
const inFlight = ref('')

const {
  cells: singles,
  running,
  done,
  expected,
  start,
  stop,
  recordImage,
  recordBlocked,
  recordFailed,
} = useRasterRun()

/** The raster is being written into the storage and read back from it. */
const storing = ref(false)

const busy = computed(() => preparing.value || running.value || storing.value)

/** One picture of a set: the text it is made from and the seed it is made on. */
interface Single { key: string; prompt: string; seed: number }

/**
 * What identifies ONE picture: the model, the seed and the text. NOT its column.
 * The two columns share their first picture — same model, same seed, same
 * English text — and a key by column would generate that picture twice and call
 * the two copies a comparison.
 */
function singleKey(model: string, prompt: string, atSeed: number): string {
  return `${model}|${atSeed}|${prompt}`
}

function singlesFor(model: string, axis: Axis): Single[] {
  const text = translationEn.value
  if (!text) return []
  if (axis === 'seedFixed') {
    return variants.value.map(line => ({
      key: singleKey(model, line, runSeed.value),
      prompt: line,
      seed: runSeed.value,
    }))
  }
  // Drawn at the press (`drawSeeds`), or read back from a stored run. Before
  // either, the column has no set yet. The list is taken WHOLE: it was drawn
  // with the set size of its own press, and a stored run comes back with the
  // size it was made at. Cutting it to the size the chips carry NOW took a
  // restored run of nine down to five on the card backs while the column head
  // still said nine, and the two sizes agree again only by accident once the
  // offered sizes change.
  return seedList.value.map(at => ({ key: singleKey(model, text, at), prompt: text, seed: at }))
}

/**
 * The variants belong to the column that varies the text. With that column off,
 * the run asks for the translation alone and the list would be one line long
 * saying nothing the field above it does not already say.
 */
const showVariants = computed(
  () => columns.includes('seedFixed') && (variants.value.length > 1 || shortfall.value > 0)
)

/**
 * The seeds the right-hand column runs on: the run's own seed first, then
 * randomly drawn ones, all distinct. Drawn once per press and written into the
 * run's parameters, so a stored run carries the numbers it was made with.
 */
const seedList = ref<number[]>([])

function drawSeeds(n: number): number[] {
  const drawn = new Set<number>([runSeed.value])
  while (drawn.size < n) drawn.add(Math.floor(Math.random() * 1_000_000_000))
  return [...drawn]
}

function cellKey(model: string, axis: Axis): string {
  return `${model}|${axis}`
}

/** The row name of a model, for a place that has the id and not the row. */
function modelLabel(model: string): string {
  return MODELS.find(m => m.id === model)?.label ?? model
}

/**
 * What ONE cell is, in English, in one paragraph.
 *
 * The same account the overlay route writes into the cell's own run
 * (`cell_account`, routes/mean_images_routes.py). It stands here as well
 * because Help is told what is on the surface without opening anything, and a
 * mean image says by looking at it neither what was held still nor what moved.
 */
function cellAccount(model: string, axis: Axis, count: number, kind: 'latent' | 'pixel'): string {
  const label = modelLabel(model)
  const one = count === 1
  // Which mean, in the same words the route writes into the cell's own run.
  const meant =
    kind === 'latent'
      ? `Mean of ${count} pictures, taken before the decoder: their latents were averaged and decoded once.`
      : `Mean image of ${count} pictures, averaged pixel by pixel.`
  const head = one ? 'The single picture of this cell.' : meant
  let made: string
  if (axis === 'seedFixed') {
    made = one
      ? `${label} generated it from an English rewording of one prompt, on seed ${runSeed.value}.`
      : `${label} generated them from ${count} English rewordings of one prompt, all on seed ${runSeed.value}.`
  } else {
    made = one
      ? `${label} generated it from the prompt as entered, on one random seed.`
      : `${label} generated them from the prompt as entered, each on a different random seed.`
  }
  // Single typographic quotes, because Help sets this whole account inside
  // double quotes of its own: with double quotes here the line ended `"."`.
  return `${head} ${made} The prompt in English: ‘${translationEn.value}’.`
}

/**
 * A set laid over each other, as the surface shows it. The three readings are
 * URLs by the time they are here — a data URL while the run is still on the
 * surface, and the stored run's own address once it has been written.
 */
interface Composite {
  sheet: string
  mean: string
  relief: string
  count: number
  resized: boolean
  /**
   * Which mean the cell shows. `latent` where every picture of the set kept its
   * final latent, those were averaged and decoded once; `pixel` where the
   * finished pictures were averaged. The route decides it per set and says so,
   * and the surface reads it from there.
   */
  meanKind: 'latent' | 'pixel'
  /**
   * The run this composite was written as, the moment it was made. A cell that
   * exists is a cell that can be LOOKED at: the whole raster is written down
   * once, at the end, and until then Help had no address for anything on the
   * page. Null where the writing failed — the picture stands either way.
   */
  runId: string | null
  /**
   * Where each of the three pictures lies inside that run, keyed by the view it
   * shows. The route hands these back because the numbering is its to know: a
   * picture that could not be written moves the ones after it up, so an address
   * counted off here would name a neighbouring picture. Empty where the cell
   * was not recorded. A restored run fills these in from the addresses its
   * composites came back at, so a later press that writes the raster again
   * hands the recorder a place to copy from.
   */
  refs?: Record<string, string>
  /**
   * When this cell was made. Per cell and not per raster: a completing press
   * adds a row hours after the first ones were made, and one time over the whole
   * surface would be a lie for one half of it either way.
   */
  madeAt: number
}
const composites = ref<Record<string, Composite>>({})

/**
 * Whether anything on the raster can be READ yet. The three readings are
 * readings of a finished cell, so until one stands the switch over them changes
 * what is shown in nothing at all and is held.
 */
const anyCell = computed(() => Object.keys(composites.value).length > 0)

/**
 * What a cell shows while its set is still being made: the mean of the latents
 * that are already in, drawn as the tensor it is, undecoded.
 *
 * The pictures of a cell arrive over minutes and the cell stands empty until
 * the last of them is laid over the rest. This is the same arithmetic one step
 * earlier and without the decoder — no card, no queue, no wait — so the cell
 * can show what the set is doing while it does it: one picture at the first
 * step, settling onto what the set shares with every further picture.
 *
 * It stands in the place a run's forming picture has always stood on this
 * platform: `preview-image`, on the card, over the bar and the model's name.
 * So it is never the cell's MEDIUM — it cannot be enlarged, it is never
 * stored, it cannot be taken for one of the three readings, and the cell goes
 * on saying that it is running while it shows it. It is gone the moment the
 * cell has something of its own, a composite or a reason.
 *
 * The route answers nothing for rows that keep no latents, so this map stays
 * empty there. At the levels that check pictures it draws the runs whose
 * pictures the check cleared.
 */
const previews = ref<Record<string, string>>({})

/** The cells whose drawing is out. One request per cell at a time: a slow disk
 *  would otherwise stack a request per picture on a fifty-picture set. */
const previewOut = new Set<string>()

/** The cells the platform has answered with no drawing that a further picture
 *  would change — a row that keeps no latents, a set of two measures. Those are
 *  properties of the run, so the cell is not asked again in this press. A
 *  picture the check has not judged yet is a property of the moment and is
 *  asked again (`why: 'not_yet'`). */
const previewNone = new Set<string>()

/** Each of the first pictures IN is drawn, then every fourth. Past the tenth
 *  one more moves the drawing by a grey level or two, and the request re-reads
 *  the whole set to show it. Counted in latents that came back, not in steps
 *  taken: a step that brought nothing changes no drawing. */
const PREVIEW_EVERY_STEP_UNTIL = 8
const PREVIEW_EVERY = 4

/**
 * What the stored run said about each cell, as it was read back. Live, the
 * raster holds the single pictures itself; restored, the raster is empty and
 * this record is the only place the run ids of a cell still stand.
 */
/**
 * What became of one single picture, where that was not a picture. A run id in
 * `run_ids` says the picture is there; this says the other two answers — turned
 * back by the check, or nothing came back and why. Without it a run read back
 * out of the storage shows a refused cell as a bare plate with nothing under it,
 * and a press onto that raster asks the model for the refused picture again.
 */
interface SingleState { blocked?: string; failed?: string }
interface StoredCell {
  run_id?: string | null
  run_ids?: (string | null)[]
  run_states?: (SingleState | null)[]
}
const storedCells = ref<Record<string, StoredCell>>({})

/**
 * The cells whose overlay is OUT, and the cells whose overlay came back with
 * nothing.
 *
 * Between the last picture of a set and the composite made from it there is a
 * request, and on a loaded card it can stand for a minute. Without this the cell
 * read "Nothing came back" for that whole minute — every picture had a state and
 * no composite existed yet — under nine pictures that had all succeeded (seen in
 * the run of 2026-09-03). A cell whose overlay is out is still filling and says
 * nothing; a cell whose overlay FAILED says why, because the pictures are there
 * and it is the laying-over that did not happen.
 */
const overlayOut = ref<Set<string>>(new Set())
const overlayFailed = ref<Record<string, string>>({})

/**
 * The cells whose MEAN was refused, as a key each.
 *
 * The mean of a latent set is a picture the platform made, and it goes through
 * the image check like any generated picture. A refusal stands apart from a
 * failure: the pictures that went into the mean all passed, and what was turned
 * back is the picture made FROM them. It goes where a failed overlay's
 * sentence goes, and it is carried as a KEY, so the reasons — German developer
 * strings — reach the reader translated.
 */
const overlayBlocked = ref<Record<string, string>>({})

/**
 * The composites as they came back, before they were stored. They go into the
 * recorder as the run's outputs and are dropped as soon as the run is written,
 * so a composite exists in exactly one place afterwards.
 */
const fresh = new Map<string, { mean: string; sheet: string; relief: string }>()

/**
 * The addresses the composites are shown at while the run is still on the
 * surface. A composite is made HERE and has no address until the run is
 * written, and the raster shows pictures as a URL rather than as base64
 * (docs/ELEMENT_STRUCTURE_REGISTRY.md, `Serienraster`) — so each one gets an
 * address of its own in this tab, and gives it back as soon as the stored run
 * answers with its served one.
 */
const heldUrls: string[] = []

function pngUrl(b64: string): string {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  const url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }))
  heldUrls.push(url)
  return url
}

function releaseUrls(): void {
  for (const url of heldUrls.splice(0)) URL.revokeObjectURL(url)
}

/**
 * Whether this tab is still standing. A run is up to ninety-nine pictures
 * per row and many minutes; leaving the instrument in the middle of one drops the loop, and what
 * is still in flight comes back to a component nobody is looking at. Two things
 * hang on it: an overlay that resolves afterwards gives its addresses back at
 * once instead of leaking them, and a dropped run is never written down as if it
 * had finished.
 */
let alive = true

/**
 * Which press is the current one. `useRasterRun` guards the picture LOOP with a
 * token of its own, but that token is taken when `start()` is called — and by
 * then the translation has already been waited for, and the variants come
 * back while the loop runs. Leaving
 * the instrument during that first call, or pressing again, would come back to a
 * fresh token and set the whole plan going: up to four hundred and ninety-five
 * generations on a card nobody is watching.
 */
let press = 0

const { gridEl, cellPx } = useGridCellWidth(() => [columns.length, rows.value.length])

const canRun = computed(
  () =>
    !busy.value &&
    !enriching.value &&
    !!promptText.value.trim() &&
    rows.value.length > 0
)

// ---------------------------------------------------------------------------
// What a cell shows
// ---------------------------------------------------------------------------
function cellUrl(model: string, axis: Axis): string {
  const held = composites.value[cellKey(model, axis)]
  if (!held) return ''
  if (view.value === 'relief') return held.relief
  // `sheet` already stands at the mean where the set held one picture — a sheet
  // of one IS that picture, and it is written down once, not twice.
  if (view.value === 'images') return held.sheet
  return held.mean
}

/**
 * The set as it stands, drawn from its latents, for the cell that is making it.
 *
 * Only while the cell RUNS: the card shows a forming picture and nothing else
 * does, and a drawing left standing in a cell that has stopped would cover the
 * reason it stopped for.
 */
function cellPreview(model: string, axis: Axis): string | null {
  if (!cellExecuting(model, axis)) return null
  return previews.value[cellKey(model, axis)] || null
}

/**
 * EXACTLY ONE cell shows a run: the one the run is on. Every other cell keeps
 * its empty plate — the four states of a cell stay apart, and a raster of nine
 * cards all claiming to be computing says nothing about where the run has got
 * to.
 *
 * "On" covers the whole time the cell is working, not only the moment a request
 * for one of its pictures is out: the gap between two pictures, and the wait
 * for the card while the set is laid over. Both are the cell working, and in
 * both the card stands.
 *
 * A COMPLETION can put two cells at work at once, and truthfully: the column
 * being generated, and the other column of that row, whose pictures were all
 * inherited and which is being laid over beside it. Two cards, two things
 * happening.
 */
function cellExecuting(model: string, axis: Axis): boolean {
  if (!running.value) return false
  const key = cellKey(model, axis)
  if (composites.value[key]) return false
  // It came back with a reason. That is the cell's, and it is not working.
  if (overlayBlocked.value[key] || overlayFailed.value[key]) return false
  if (overlayOut.value.has(key)) return true
  if (key !== inFlight.value) return false
  // The marker stays on a cell between two of its pictures, so it alone does
  // not say the cell is working: a set whose pictures are all back — every one
  // of them refused, or every one of them without a run id, so that no
  // laying-over is even attempted — is DONE, and what it has to show is its
  // reason. A card over it would hide that reason behind an empty bar.
  return singlesFor(model, axis).some(single => !singles.value[single.key])
}

/** When this cell was made; while it is being made, when its press started. */
function cellMadeAt(model: string, axis: Axis): number {
  return composites.value[cellKey(model, axis)]?.madeAt || madeAt.value
}

function cellProgress(model: string, axis: Axis): number {
  // A run read back has no single pictures behind it on this surface, and its
  // set is complete by definition — its composites are what was stored.
  if (composites.value[cellKey(model, axis)]) return 100
  const set = singlesFor(model, axis)
  if (!set.length) return 0
  const back = set.filter(s => singles.value[s.key]).length
  return Math.round((back / set.length) * 100)
}

/** The back of the card: what this set is, and what went into it. */
function cellFacts(model: string, axis: Axis): string[] {
  const set = singlesFor(model, axis)
  const held = composites.value[cellKey(model, axis)]
  const seeds = [...new Set(set.map(s => s.seed))]
  const seedText =
    seeds.length > 1
      ? t('latentLab.meanImages.colSub.promptFixed', { n: seeds.length })
      : `${t('latentLab.meanImages.seedLabel')} ${seeds[0] ?? runSeed.value}`
  const facts = [
    MODELS.find(m => m.id === model)?.label ?? model,
    t(`latentLab.meanImages.col.${axis}`),
    `n ${held?.count ?? set.length}`,
    seedText,
  ]
  // Which mean the front of the card IS — where there IS one. A set of one is
  // a single picture, and a way of averaging it would name an operation that
  // did not happen.
  if (held && held.count > 1) {
    facts.push(t(`latentLab.meanImages.meanKindLong.${held.meanKind}`))
  }
  // The base text stands as the card's prompt, because every picture of every
  // column derives from it. Where the column VARIED it, the facts say how many
  // texts there were and carry the two ends of the list — the whole list would
  // be fifty lines on the back of a card.
  if (axis === 'seedFixed' && set.length) {
    facts.push(t('latentLab.meanImages.colSub.seedFixed', { n: set.length }))
    facts.push(set[0]!.prompt)
    if (set.length > 1) facts.push(set[set.length - 1]!.prompt)
  }
  return facts.filter(Boolean)
}

/**
 * What stands in a cell instead of a set. A refusal is carried as a KEY until
 * here; the reasons themselves are German developer strings and are never shown
 * raw. A cell says so only once every picture of its set has come back one way
 * or the other — until then it is still filling.
 */
function cellNote(model: string, axis: Axis): string {
  if (composites.value[cellKey(model, axis)]) return ''
  // The mean itself was refused: the pictures that went into it all passed, and
  // what was turned back is the picture made FROM them. It is read ahead of
  // everything below, because a raster taken back out of the storage has no
  // single pictures behind it at all and the gates below would hold the reason
  // back for want of states a restore never has.
  const overlayRefusal = overlayBlocked.value[cellKey(model, axis)]
  if (overlayRefusal) return t(overlayRefusal)
  const set = singlesFor(model, axis)
  // The variants never came back, so this column has no set in this press.
  if (!set.length && axis === 'seedFixed' && variantsFailed.value) {
    return variantsFailedText(variantsFailed.value)
  }
  if (!set.length) return ''
  const states = set
    .map(s => singles.value[s.key])
    .filter((cell): cell is RasterCell => !!cell)
  if (states.length < set.length) return ''
  // Every picture is in and the laying-over is still out: the cell is filling.
  if (overlayOut.value.has(cellKey(model, axis))) return ''
  // It came back with nothing. That, and not the pictures, is why the cell is
  // empty, so it is what the cell says.
  const overlayCause = overlayFailed.value[cellKey(model, axis)]
  if (overlayCause) return t('latentLab.meanImages.runFailed', { m: overlayCause })
  const blocked = states.find(s => s.blockedKey)
  if (blocked) return t(blocked.blockedKey)
  // The cause the run gave, where it gave one: the card is taken, the model is
  // not installed here, the queue is full. One sentence beats "nothing came
  // back" for every one of them.
  const failed = states.find(s => s.failedKey)
  if (failed?.failedKey) return t(failed.failedKey)
  return t('latentLab.meanImages.cellFailed')
}

/** Under a column head: what this column holds still and what it moves. */
function headSub(axis: Axis): string {
  if (axis === 'seedFixed') {
    // What RAN, not what was asked for: a model that answered with fewer
    // distinct variants makes a shorter set, and the head is what the reader
    // counts the pictures against.
    // Variants that did not come back ran nothing.
    const n = variantsFailed.value ? 0 : (variants.value.length || perCellCount.value)
    return t('latentLab.meanImages.colSub.seedFixed', { n })
  }
  return t('latentLab.meanImages.colSub.promptFixed', { n: seedList.value.length || perCellCount.value })
}

/**
 * Beside a row name: how far this model has come.
 *
 * A run READ BACK — from the gallery, or from the storage right after it was
 * written — has no single pictures behind it on this surface; what it has is its
 * composites. So the row is read from those first: a model whose cells all stand
 * is done, and "waiting" under a full raster would be plainly untrue.
 */
function rowState(model: string): string {
  const cells = columns.map(axis => composites.value[cellKey(model, axis)])
  // Whether or not a run is going: a row whose cells all stand IS done, and on a
  // completing press it is a row nothing is being asked of — the pictures the
  // count below would fall back to belong to a press that is over.
  if (cells.length && cells.every(Boolean)) {
    return t('latentLab.meanImages.rowState.done')
  }
  const keys = new Set<string>()
  for (const axis of columns) {
    for (const s of singlesFor(model, axis)) keys.add(s.key)
  }
  // While the variants are still being written, the column that varies the
  // text has no set yet, and a row whose other column is in would read as done.
  // It counts as the set that was asked for: the variants less the first, which
  // is the picture both columns share.
  const total = keys.size + (variantsPending.value ? perCellCount.value - 1 : 0)
  if (!total) return t('latentLab.meanImages.rowState.waiting')
  const back = [...keys].filter(k => singles.value[k]).length
  if (!back) return t('latentLab.meanImages.rowState.waiting')
  if (back < total) return t('latentLab.meanImages.rowState.running', { done: back, total })
  return t('latentLab.meanImages.rowState.done')
}

/**
 * Which mean this row shows, once it shows one.
 *
 * The kind belongs to the SET — the route decides it per cell — but a row is one
 * model, so its cells agree. Where they disagree the row says nothing: naming
 * one of two kinds for the whole row would be the only untrue reading of it.
 */
function rowMeanKind(model: string): '' | 'latent' | 'pixel' {
  const kinds = new Set(
    columns
      .map(axis => composites.value[cellKey(model, axis)])
      // A set of one says nothing about the row: where one picture is all that
      // came back, no averaging happened in that cell, and letting it speak
      // would put a kind on the row line that names no operation.
      .filter((c): c is Composite => !!c && c.count > 1)
      .map(c => c.meanKind)
  )
  return kinds.size === 1 ? [...kinds][0]! : ''
}

/**
 * The second line of a row name: how far the row has come, and which mean it
 * shows. The two SD 3.5 rows are averaged before the decoder and the other rows
 * pixel by pixel, so a raster holds both kinds at once and the row is where the
 * difference belongs.
 */
function rowLine(model: string): string {
  const kind = rowMeanKind(model)
  const state = rowState(model)
  return kind ? `${state} · ${t(`latentLab.meanImages.meanKind.${kind}`)}` : state
}

// ---------------------------------------------------------------------------
// The run
// ---------------------------------------------------------------------------
/**
 * One picture of the plan, and the cell it is being made FOR. A picture that
 * several columns share is computed once, under the column that asked first;
 * that column is the one whose cell stands as running while it is out.
 */
type PlanStep =
  | { kind: 'picture'; model: string; axis: Axis; single: Single }
  | { kind: 'close'; model: string }

/**
 * The text the material on the surface was made from, as it stood at that
 * press. A completion is a completion only while the field still says it.
 */
let madeFrom = ''

/**
 * Whether that press drew its seed or was given one. Switching the automatic
 * seed on after a run by hand leaves the run's own number standing in
 * `runSeed`, and a completion would then add rows under a seed the reader has
 * just said they no longer want fixed.
 */
let madeRandom = false

/**
 * Whether this cell has been made. A picture and a refusal are both results —
 * the cell was generated, and what came of it stands there. Only an empty cell
 * and one that failed are still to do.
 */
function cellDone(model: string, axis: Axis): boolean {
  const key = cellKey(model, axis)
  // The mean itself was turned back. That is a verdict on the picture this set
  // makes, and the set does not change: nothing here comes out differently.
  if (overlayBlocked.value[key]) return true
  const set = singlesFor(model, axis)
  if (!set.length) return false
  const states = set.map(single => singles.value[single.key])
  // Every picture is SETTLED: it came back, or it was turned back. A failure is
  // not settled — a taken card, a model that was down, a full queue all answer
  // differently a minute later, and asking again is what a completing press is
  // for. So a cell whose composite rests on three of five pictures is not done:
  // the other two are asked for, and the cell is laid over again with all five.
  if (!states.every(state => state && (state.runId || state.blockedKey))) return false
  if (composites.value[key]) return true
  // Settled, and not one picture to lay over: every one of them was turned back.
  // No composite and no refused mean will ever stand here, and read as "still to
  // do" this cell would hold the whole surface in completion mode, where a press
  // draws no seed, asks for no text, and puts the identical request to the
  // identical model for as long as the reader keeps pressing.
  return !states.some(state => state?.runId)
}

/**
 * Whether this press ADDS to what stands instead of starting over.
 *
 * A press EXTENDS the existing run; a complete regeneration happens only where
 * everything on the surface has already been generated. A row switched on
 * after a run costs that row and nothing else; a cell that failed is asked for
 * again; a press onto a raster where everything has been made is a new run.
 *
 * What is added has to come out of the SAME material as what stands, or one
 * raster would hold two runs and the difference between two rows would be the
 * material rather than the model: the same English text, the same variants, the
 * same seeds, the same set size. So the material has to be there, it has to
 * belong to the text in the field NOW, and the numbers have to be where they
 * were. Any of that moved and the press is a fresh run.
 */
function completingPress(): boolean {
  if (!translationEn.value) return false
  if (madeFrom !== promptText.value.trim()) return false
  // The set size moved: the two columns would come out of two sizes.
  if (seedList.value.length !== perCellCount.value) return false
  // A seed set by hand and then changed is a different run, and so is the
  // switch between drawing one and giving one. With the automatic seed on, the
  // field cannot be typed into, so the number itself is not read.
  if (madeRandom !== randomSeed.value) return false
  if (!randomSeed.value && runSeed.value !== seed.value) return false
  // A record that kept no variants while means of them stand: the variants
  // those means were made from are gone, and anything added would be made from
  // others. Such a press is a fresh run.
  if (columns.includes('seedFixed') && !variants.value.length && rows.value.some(row => {
    const key = cellKey(row.id, 'seedFixed')
    return composites.value[key] || overlayBlocked.value[key]
  })) return false
  // Variants that never came back do not make the press a fresh run: they are
  // asked for again from the run's own English text, and the column of the
  // prompt as entered stays as it is (`wantsVariants` in `startRun`).
  return rows.value.some(row => columns.some(axis => !cellDone(row.id, axis)))
}

/**
 * A picture that already lies in the storage, as the address the recorder
 * copies from (`/api/media/...`). Empty for anything else: the blob address of
 * a cell whose own write failed names no place inside the storage.
 */
function storedRef(url?: string): string {
  if (!url || !url.startsWith('/api/media/')) return ''
  // WITHOUT the version query. A served address carries `?v=<mtime>` so that one
  // file cannot sit in two caches under one name, and the recorder's pattern for
  // a run address is anchored and admits no query: handed one it refuses the
  // picture, writes a line into the log, and the cell falls out of the record
  // while the surface goes on showing it.
  return url.split(/[?#]/)[0] ?? ''
}

/**
 * Where the single pictures of a cell lie. Live, the raster holds them; on a
 * completion the standing cells were made in an earlier press, and if that
 * press is what was read back, the record of it is where their addresses are.
 */
function keptRunIds(key: string, set: Single[]): (string | null)[] {
  const live = set.map(single => singles.value[single.key]?.runId ?? null)
  if (live.some(Boolean)) return live
  const kept = storedCells.value[key]?.run_ids
  return Array.isArray(kept) ? kept : live
}

/**
 * What became of each single picture of a cell, in the order of its set —
 * alongside `run_ids`, which says where the ones that arrived lie.
 */
function keptStates(key: string, set: Single[]): (SingleState | null)[] {
  const live = set.map(single => {
    const cell = singles.value[single.key]
    if (!cell) return null
    if (cell.blockedKey) return { blocked: cell.blockedKey }
    if (cell.failed) return { failed: cell.failedKey || '' }
    return null
  })
  if (live.some(Boolean)) return live
  const kept = storedCells.value[key]?.run_states
  return Array.isArray(kept) ? kept : live
}

/**
 * Which PICTURES a stored run carries, as `model|axis|view`. Per view and not
 * per cell: the recorder writes each picture on its own and passes over one it
 * cannot write, so a cell can come back holding two of its three readings — and
 * counted per cell it would pass for whole, while the reading it lost stands on
 * the surface as an empty plate with no reason under it and no bytes left
 * anywhere.
 */
function viewsHeldBy(obj: InstrumentRun): Set<string> {
  const keys = new Set<string>()
  for (const out of obj.outputs || []) {
    const meta = (out.meta || {}) as Record<string, unknown>
    if (typeof meta.model === 'string' && typeof meta.axis === 'string'
        && typeof meta.view === 'string' && out.url) {
      keys.add(`${meta.model}|${meta.axis}|${meta.view}`)
    }
  }
  return keys
}

function requestMessage(err: unknown): string {
  // The status travels; the response body stays in the log (useLabRun).
  return generationErrorFor(t, err)
}

/** The line for variants that did not come back, in the reader's language. */
function variantsFailedText(cause: GenerationErrorKey): string {
  return t('latentLab.meanImages.runFailed', { m: t(cause.key, cause.params) })
}

async function startRun(): Promise<void> {
  if (!canRun.value) return
  errorMessage.value = ''
  // Fill what is missing, or start over: as long as a cell of the current
  // selection has not been made, this press makes THAT cell and leaves
  // everything else standing.
  const completing = completingPress()
  // What the raster on the surface will have been made from, once this press
  // has brought a picture.
  const pressInputs = inputsKey()
  const pressPrompt = promptText.value
  // The drawings belong to the press and not to the raster: a cell being filled
  // now must not open with the last press's picture of a different set.
  previews.value = {}
  previewOut.clear()
  previewNone.clear()
  // A cell that failed is one this press asks for again, so its reason goes.
  overlayFailed.value = {}
  // The raster on the screen stops being the run that was written the moment
  // this press starts. Held, the star would stand lit over cells the stored run
  // does not contain, and pressing it would favourite the raster WITHOUT the row
  // being added. The run this press makes gets its own id when it is written;
  // a press that writes nothing gives the star back to the run it found.
  const runBefore = labRunId.value
  labRunId.value = null
  // A press asks for the variants again where they did not come, so the
  // reason of the last call goes with it.
  variantsPending.value = false
  variantsFailed.value = null
  if (!completing) {
    composites.value = {}
    storedCells.value = {}
    overlayOut.value = new Set()
    overlayBlocked.value = {}
    variants.value = []
    translationEn.value = ''
    shortfall.value = 0
    fresh.clear()
    releaseUrls()
    // What the last press left in the cells is dropped with it: kept, a set
    // whose pictures all happened to carry over would be laid over the PREVIOUS
    // run's pictures before the new ones had arrived.
    singles.value = {}

    // The seed automatic: the same seed when something changed since the
    // raster on the surface was made, a new one when nothing did, the field's
    // when it was typed, a new one on every press under the tick. The seed goes
    // into the field.
    runSeed.value = seedAutomatic.seedForRun(pressInputs)
    seedList.value = drawSeeds(perCellCount.value)
    madeFrom = promptText.value.trim()
    madeRandom = randomSeed.value
  }
  // When THIS press ran. Each cell that stands keeps the time it was made at, so
  // this is what a cell falls back to only while it is still being made.
  madeAt.value = Date.now()
  // On a completion nothing else of the material moves — text, variants, seeds,
  // the seed itself — because what is added stands beside what is there.

  // What the counter counts, before anything is asked for. The translation
  // takes a model call of its own, and until it is back the bar would otherwise
  // read 0 / 0 while plainly running. `start()` sets the exact number a moment
  // later, off the plan it actually builds; where the variants are still being
  // written, `stepsAsTheyCome` sets it when they are back.
  expected.value = perCellCount.value * rows.value.reduce(
    (n, row) => n + columns.filter(axis => !completing || !cellDone(row.id, axis)).length,
    0,
  )

  // The English text FIRST. Every row is made from one and the same text, so a
  // difference between two rows is the model.
  preparing.value = true
  const mine = ++press
  // The variants of that text are written beside the first pictures, not
  // before them (`writeVariants`). A large set is collected in rounds, one
  // model call each, and waiting for the whole list left the card idle for as
  // long as the rounds took, while the column of the prompt as entered needs
  // nothing but the translation. A completion asks for them only where the
  // call of its run came back with nothing, from that run's English text.
  const wantsVariants = columns.includes('seedFixed') && perCellCount.value > 1 && !variants.value.length
  try {
    // The sitting is opened before the first picture, so the run it is written
    // into belongs to the press that made it.
    await startSession()
    // A completion asks no model for material: the text and the variants of the
    // run it completes ARE its material, and new ones would make the added rows
    // a second run standing in the same raster. Variants the run never got are
    // the exception: there are none standing that new ones could differ from.
    if (!completing) {
      // The translation alone (a set of one). Answered as a stream all the
      // same, because the route is one that can take minutes: measured on
      // 2026-09-04, one press for a large set was out for 21 min 50 s and the
      // tunnel in front of the server had cut the POST after about 100 s. The
      // client resolves and throws like the `axios.post` it replaces.
      const { data } = await postStreamedRun('/api/latent-lab/mean-images/variants', {
        prompt: pressPrompt,
        n: 1,
      }, { baseUrl })
      // A press that overtook this one, or a run brought in from the gallery
      // while the call was out, owns the text now.
      if (!alive || mine !== press) return
      translationEn.value = data?.translation_en || ''
      // Where no variants are asked for, this IS the material of the column.
      if (!wantsVariants) variants.value = Array.isArray(data?.variants) ? data.variants : []
    }
  } catch (err) {
    // Nothing will run, so the bar stops counting towards a number it will never
    // reach.
    expected.value = 0
    done.value = 0
    errorMessage.value = t('latentLab.meanImages.runFailed', { m: requestMessage(err) })
    return
  } finally {
    preparing.value = false
  }

  // The tab left, or a second press overtook this one, while the text was out.
  if (!alive || mine !== press) return

  if (!translationEn.value) {
    expected.value = 0
    done.value = 0
    errorMessage.value = t('latentLab.meanImages.runFailed', { m: t('latentLab.meanImages.noEnglishText') })
    return
  }

  const variantsOut = wantsVariants
    ? writeVariants(mine, pressPrompt, translationEn.value, perCellCount.value)
    : null

  // One picture at a time, model by model, so a card holds one model's weights
  // for a whole row instead of exchanging them at every second picture. A
  // picture that several columns share is computed once.
  const plan: PlanStep[] = []
  const seen = new Set<string>()
  const asked = new Set<string>()
  for (const row of rows.value) {
    for (const axis of columns) {
      // A cell that has been made is not made a second time.
      if (completing && cellDone(row.id, axis)) continue
      for (const single of singlesFor(row.id, axis)) {
        if (seen.has(single.key)) continue
        seen.add(single.key)
        // Nor is a picture that already came back, or one that was turned back:
        // the two columns share their first one, a completion inherits every
        // picture of the run it completes, and a refusal is a verdict on this
        // model, this seed and this text, none of which a completion changes.
        // What FAILED is asked for again — a taken card answers differently a
        // minute later.
        const state = completing ? singles.value[single.key] : undefined
        if (state?.runId || state?.blockedKey) continue
        asked.add(row.id)
        plan.push({ kind: 'picture', model: row.id, axis, single })
      }
    }
  }
  // A row that is asked for nothing and is still not done: its pictures were
  // all inherited, or the laying-over is what failed last time. The laying-over
  // is then the whole of this row's work and goes into the plan AS a step of the
  // run — outside it, `running` is false, so there would be no bar, no card over
  // the cell, and a live button under a surface that is decoding.
  //
  // Every other row lays its sets over inside `runOne`, after each of its
  // pictures, and needs no step of its own.
  for (const row of rows.value) {
    if (asked.has(row.id)) continue
    // A column still waiting for its variants has no set yet; its pictures
    // join the run when the variants are back.
    if (columns.some(axis => !cellDone(row.id, axis) && singlesFor(row.id, axis).length)) {
      plan.push({ kind: 'close', model: row.id })
    }
  }
  // AFTER the plan, because the plan is built from what is done. A cell that is
  // being asked for pictures again has a composite resting on the set as it was
  // — three of five, where two came back with nothing — and `closeSets` leaves a
  // cell that has one alone. So the old picture goes now, with the request for
  // the new ones: the cell says it is filling instead of showing a mean its set
  // no longer matches, and it is laid over again with everything that is in.
  // Its bytes stay in `fresh` until the raster is written, so a laying-over that
  // fails again still stores the picture the cell had.
  let dropped = false
  if (completing) {
    const kept = { ...composites.value }
    for (const row of rows.value) {
      for (const axis of columns) {
        const key = cellKey(row.id, axis)
        if (!kept[key] || cellDone(row.id, axis)) continue
        delete kept[key]
        dropped = true
      }
    }
    if (dropped) composites.value = kept
  }

  // A plan still being written has no length to count from: the pictures of the
  // variants count as the set that was asked for until they are back.
  if (variantsOut) expected.value = plan.length + rows.value.length * (perCellCount.value - 1)
  await start(variantsOut ? stepsAsTheyCome(plan, seen, variantsOut, mine) : plan, step => runStep(step))
  // A press given up while its variants were out comes back here only once they
  // are, and by then the marker may be a newer press's.
  if (mine === press) inFlight.value = ''
  // A raster to which this press brought a picture is the one the next press is
  // compared with. Pictures a completion inherited do not count.
  const brought = plan.some(step => step.kind === 'picture' && !!singles.value[step.single.key]?.runId)
  if (alive && mine === press && brought) seedAutomatic.arrived(pressInputs, runSeed.value)
  // A run that was DROPPED — the tab left the instrument mid-way — comes back
  // here with its loop abandoned and its plan half done. `useRasterRun` returns
  // silently in that case, so the two things that say it are the tab itself and
  // the counter: a finished run has every step of its plan behind it.
  if (!alive || mine !== press || done.value < expected.value) return
  // Nothing new to write and nothing taken off the surface, as after a
  // completion whose variants failed again: what stands is the run that was
  // read back, and the star and Help belong to it again.
  if (!fresh.size && !dropped && !brought) {
    labRunId.value = runBefore
    return
  }
  await writeRun(mine)
}

/**
 * The variants of a fresh press, asked for while its first pictures are made.
 *
 * The English text goes back to the route with the request, so the variants
 * are written from the very sentence the other column runs on: `variants[0]`
 * IS that sentence, and the first picture of the two columns stays one request.
 * It never throws. A call that comes back with nothing leaves its reason with
 * the column that varies the text, and the rest of the run goes on.
 */
async function writeVariants(mine: number, prompt: string, translation: string, n: number): Promise<void> {
  variantsPending.value = true
  try {
    const { data } = await postStreamedRun('/api/latent-lab/mean-images/variants', {
      prompt,
      translation_en: translation,
      n,
    }, { baseUrl })
    if (!alive || mine !== press) return
    const got: string[] = Array.isArray(data?.variants) ? data.variants : []
    // A backend from before `translation_en` translates the prompt again, and
    // the list may then open with another English sentence: the shared first
    // picture is made a second time. Said in the console, as the transport says
    // a deploy mismatch (services/directRun.ts); the list is used as it came.
    if (got.length && got[0] !== translation) {
      console.warn(
        '[mean images] The variants came back from another English sentence than the one ' +
        'sent. The bundle in this browser and the backend are probably not the same deploy.',
      )
    }
    variants.value = got
    shortfall.value = Number(data?.shortfall) || 0
  } catch (err) {
    if (!alive || mine !== press) return
    variantsFailed.value = generationErrorKeyFor(err)
    errorMessage.value = variantsFailedText(variantsFailed.value)
  } finally {
    if (mine === press) variantsPending.value = false
  }
}

/**
 * The plan of a fresh press, handed to the loop one step at a time while the
 * variants are still being written.
 *
 * At the press the plan holds the pictures of the prompt as entered; the
 * pictures of the variants join the moment the variants are back. Until then
 * the run goes on through what IS planned and waits only where nothing else is
 * left. The next step is one for the model of the step before, where there is
 * one, so variants that come back in the middle of a row are made before the
 * run moves on. A row the run has already left loads its model once more for
 * its variants.
 *
 * Every step added is also written into `plan`, so what the press asked for
 * can be read off the plan afterwards, as it can for a list.
 */
async function* stepsAsTheyCome(
  plan: PlanStep[],
  seen: Set<string>,
  variantsOut: Promise<void>,
  mine: number,
): AsyncGenerator<PlanStep> {
  const order = rows.value.map(row => row.id)
  const pending = [...plan]
  let back = false
  let taken = false
  void variantsOut.finally(() => { back = true })
  let last = ''
  while (alive && mine === press) {
    if (back && !taken) {
      taken = true
      for (const model of order) {
        const set = singlesFor(model, 'seedFixed')
        let added = false
        for (const single of set) {
          if (seen.has(single.key)) continue
          seen.add(single.key)
          // A picture the raster already holds is not made again: on a
          // completion, the one the two columns share.
          const state = singles.value[single.key]
          if (state?.runId || state?.blockedKey) continue
          const step: PlanStep = { kind: 'picture', model, axis: 'seedFixed', single }
          plan.push(step)
          pending.push(step)
          added = true
        }
        // A set with nothing left to make: the variants came back as the
        // translation alone, whose picture the other column already has. It is
        // laid over as a step of its own, or it would wait for a picture of this
        // model that never comes.
        if (set.length && !added && !cellDone(model, 'seedFixed')) {
          const step: PlanStep = { kind: 'close', model }
          plan.push(step)
          pending.push(step)
        }
      }
      // The rows in the order of the raster; within a row, the order planned.
      pending.sort((a, b) => order.indexOf(a.model) - order.indexOf(b.model))
      expected.value = plan.length
    }
    if (pending.length) {
      const at = Math.max(0, pending.findIndex(step => step.model === last))
      const step = pending.splice(at, 1)[0]!
      last = step.model
      yield step
      continue
    }
    if (taken) return
    // Nothing is left but what the variants will bring, and no cell is being
    // worked on while they are written.
    inFlight.value = ''
    await variantsOut
  }
}

async function runStep(step: PlanStep): Promise<void> {
  if (step.kind === 'close') {
    inFlight.value = ''
    await closeSets(step.model)
    return
  }
  await runOne(step.model, step.axis, step.single)
}

async function runOne(model: string, axis: Axis, single: Single): Promise<void> {
  inFlight.value = cellKey(model, axis)
  try {
    // The text is English by now and reaches the model as it stands.
    const res = await postDirectRun(
      {
        prompt: single.prompt,
        output_config: model,
        seed: single.seed,
        user_language: 'en',
        device_id: deviceId,
        // The picture keeps its final latent, so a set can be averaged BEFORE
        // the decoder. Every row asks for it; a config whose chunk keeps no
        // latent ignores the flag, and its cells are averaged pixel by pixel.
        keep_latent: true,
      },
      { baseUrl }
    )
    if (recordImage(single.key, single.seed, res.data)) {
      // The line under the controls names the LAST reason and goes as soon as a
      // picture arrives.
      errorMessage.value = ''
    } else {
      recordFailed(single.key, single.seed, 'latentLab.meanImages.cellFailed')
    }
  } catch (err) {
    if (!recordBlocked(single.key, single.seed, err)) {
      // Nothing came back at all. The run keeps going: the remaining pictures
      // are worth having, and a set that lost one is laid over the rest with
      // the cell saying how many went in. WHY it did not come back travels with
      // it — the card is taken, the model is not installed here, the queue is
      // full — in the same wording the comparison surfaces use.
      const e = err as { response?: { status?: number; data?: Record<string, unknown> } }
      const status = e?.response?.status === 503 ? 'busy' : 'error'
      recordFailed(single.key, single.seed, failureKey(status, requestMessage(err)))
      errorMessage.value = t('latentLab.meanImages.runFailed', { m: requestMessage(err) })
    }
  }
  // The marker stays on this cell: the laying-over below is this cell still
  // working, and the next picture moves it on. Cleared where the run ends.
  await closeSets(model)
  // After the laying-over, not before it: a set that just closed has its
  // composite, and its drawing would be a picture the cell no longer needs.
  void refreshPreview(model, axis)
}

/**
 * The drawing of a cell that is still filling, brought up to the pictures that
 * are in.
 *
 * Fire and forget: the run does not wait for it, and a drawing that does not
 * come leaves the cell as it was. The answer is dropped where the surface has
 * moved on — a second press, the tab gone, or the composite already there,
 * which is the picture this one stands in for.
 */
async function refreshPreview(model: string, axis: Axis): Promise<void> {
  const key = cellKey(model, axis)
  if (!alive) return
  if (previewOut.has(key) || previewNone.has(key) || composites.value[key]) return
  // The cell has its answer already, and it is not a picture. Asking would
  // re-read the whole set for a drawing nothing would show.
  if (overlayBlocked.value[key] || overlayFailed.value[key]) return
  const ids = singlesFor(model, axis)
    .map(single => singles.value[single.key]?.runId)
    .filter((id): id is string => !!id)
  if (!ids.length) return
  if (ids.length > PREVIEW_EVERY_STEP_UNTIL && ids.length % PREVIEW_EVERY !== 0) return
  previewOut.add(key)
  const mine = press
  try {
    // The platform's ORDINARY client, not the streamed one: this route answers
    // one JSON body, and asking a plain route for a stream makes its own client
    // report a deploy mismatch on every picture — the one line that says a
    // browser and a backend have come apart would then never mean anything
    // again. `withCredentials` is what carries the session, and the session is
    // what carries the course whose level decides whether there is a drawing at
    // all.
    const { data } = await axios.post(
      `${baseUrl}/api/latent-lab/mean-images/latent-preview`,
      { run_ids: ids },
      { withCredentials: true },
    )
    if (!alive || mine !== press || composites.value[key]) return
    const drawn = typeof data?.preview === 'string' ? data.preview : ''
    if (!drawn) {
      // `why` tells a property of the run from a property of the moment: a row
      // that keeps no latent and a set of two measures never draw, a picture
      // the check has not judged yet draws at the next step.
      if (data?.why !== 'not_yet') previewNone.add(key)
      return
    }
    previews.value = { ...previews.value, [key]: `data:image/png;base64,${drawn}` }
  } catch {
    // A cell that keeps its empty plate for another picture's worth of time.
    // Nothing here is a result, so nothing here is a failure to report.
  } finally {
    previewOut.delete(key)
  }
}

/** The drawing of a cell goes when the cell itself arrives. */
function dropPreview(key: string): void {
  if (!previews.value[key]) return
  const rest = { ...previews.value }
  delete rest[key]
  previews.value = rest
}

/** Every set of this model whose pictures are all in gets laid over at once. */
async function closeSets(model: string): Promise<void> {
  for (const axis of columns) {
    const key = cellKey(model, axis)
    // A cell that HAS its composite is through, and so is one whose mean was
    // refused. The retry below this line was written for a request that FAILED
    // — that is the case which can come out differently a moment later. A
    // refusal is a verdict on THIS set, and the set does not change for the
    // rest of the run: coming back after every further picture of the row would
    // decode the same latents on the card and put the same picture to the check
    // again, up to ninety-eight times at fifty pictures per cell.
    if (composites.value[key] || overlayBlocked.value[key]) continue
    // One at a time per cell. Nothing in an ordinary run asks twice, but a
    // second press arriving while the first is still waiting for the card would
    // decode the same latents again, put the same picture to the check again,
    // and write the same cell twice.
    if (overlayOut.value.has(key)) continue
    const set = singlesFor(model, axis)
    if (!set.length) continue
    if (set.some(s => !singles.value[s.key])) continue
    await overlay(model, axis)
  }
}

async function overlay(model: string, axis: Axis): Promise<void> {
  const set = singlesFor(model, axis)
  const runIds = set
    .map(s => singles.value[s.key]?.runId)
    .filter((id): id is string => !!id)
  if (!runIds.length) return
  const key = cellKey(model, axis)
  overlayOut.value = new Set([...overlayOut.value, key])
  // A further picture of this model brings `closeSets` back here, so a cell whose
  // overlay failed gets another attempt. The earlier reason goes with the
  // attempt: it would otherwise stand under a cell that is trying again.
  if (overlayFailed.value[key]) {
    const rest = { ...overlayFailed.value }
    delete rest[key]
    overlayFailed.value = rest
  }
  try {
    // What a SET cell is travels with the request, so its composite is written
    // as a run of its own the moment it exists and Help has an address for it
    // while the rest of the raster is still filling. The sitting is the one the
    // whole raster is written into at the end.
    //
    // Answered as a stream, for the same reason the variants are: a latent mean
    // waits FIFO for the plant-wide GPU slot before it can decode anything, and
    // a wait longer than about 100 s used to end as a 524 on a decode that had
    // already happened. The refusal below still arrives as the 200 it is.
    const { data } = await postStreamedRun('/api/latent-lab/mean-images/overlay', {
      run_ids: runIds,
      record: {
        session_id: sessionId.value,
        model,
        model_label: modelLabel(model),
        axis,
        seed: runSeed.value,
        translation_en: translationEn.value,
      },
    }, { baseUrl })
    // The tab may have gone while this was out. Its addresses are made here and
    // released nowhere else, so they are given back at once rather than left to
    // a component that no longer exists.
    if (!alive) {
      releaseUrls()
      return
    }
    // The check refused the mean. The route answers that with a 200 and records
    // nothing, so it arrives here and not in the catch, and the cell says it
    // instead of showing a picture. The stage is known without being sent: the
    // only thing this route checks is the picture it just made, so the refusal
    // is the image check's and reads as one — without it the reader would be
    // told to rewrite a prompt the platform itself had just passed.
    if (data?.status === 'blocked') {
      // The platform's own sentence for a refused picture ends in "just try
      // again, every generation is different" — true of a generation, untrue
      // here: a mean is a decode of latents that are already on disk, so the
      // same press gives the same picture and the same verdict. The refusal of
      // a MEAN therefore gets this surface's wording. An operational fault is
      // a different matter and keeps the platform's sentence for it.
      const said = safetyBlockKey(data.reason, 'vlm_safety')
      overlayBlocked.value = {
        ...overlayBlocked.value,
        [key]: said === 'safetyBlocked.vlm' ? 'latentLab.meanImages.meanBlocked' : said,
      }
      return
    }
    fresh.set(key, { mean: data.mean, sheet: data.sheet ?? '', relief: data.relief })
    // A set of one carries no contact sheet — the mean IS that picture, and the
    // route says so with a null rather than computing a second copy of it.
    const mean = pngUrl(data.mean)
    composites.value = {
      ...composites.value,
      [key]: {
        mean,
        sheet: data.sheet ? pngUrl(data.sheet) : mean,
        relief: pngUrl(data.relief),
        count: Number(data.count) || runIds.length,
        resized: data.resized === true,
        meanKind: data.mean_kind === 'latent' ? 'latent' : 'pixel',
        runId: typeof data.run_id === 'string' ? data.run_id : null,
        refs: data.refs && typeof data.refs === 'object' ? { ...data.refs } : {},
        madeAt: Date.now(),
      },
    }
    dropPreview(key)
  } catch (err) {
    if (!alive) return
    const cause = requestMessage(err)
    // The drawing goes with the attempt: the cell now has a reason to show, and
    // a card standing over it would hide that reason behind a picture of a set
    // that never closed.
    dropPreview(key)
    overlayFailed.value = { ...overlayFailed.value, [key]: cause }
    errorMessage.value = t('latentLab.meanImages.runFailed', { m: cause })
  } finally {
    // Off the list either way, and off it even where the tab left in between —
    // a cell left marked as filling would never say anything again.
    const rest = new Set(overlayOut.value)
    rest.delete(key)
    overlayOut.value = rest
  }
}

// ---------------------------------------------------------------------------
// The run, written down
// ---------------------------------------------------------------------------
const labRunId = ref<string | null>(null)

/**
 * The cells in the order they are stored. The FACE goes first, because the
 * gallery shows a stored run by its first picture: the mean of the first model's
 * left-hand column, the one that holds the seed and moves the text.
 */
function storingOrder(): { model: string; axis: Axis }[] {
  const cells = rows.value.flatMap(row => columns.map(axis => ({ model: row.id, axis })))
  const firstModel = rows.value[0]?.id
  const face =
    cells.find(c => c.model === firstModel && c.axis === 'seedFixed') ?? cells[0]
  if (!face) return cells
  return [face, ...cells.filter(c => c !== face)]
}

/**
 * The whole run into the platform's storage, once, at the end.
 *
 * The composites go in as the outputs. The single pictures stay out of it:
 * each of them is a pipeline run of its own with its own address, and putting
 * them in as well would carry a few hundred pictures up through the browser for
 * nothing. What is written instead is where they lie — the run ids, the text
 * and the seed of every single picture, per cell, in the results.
 */
async function writeRun(mine: number): Promise<void> {
  if (!fresh.size) return
  // The button stays out while this runs. It is a write and a read-back, both
  // over the network, and a press landing in between would build its plan from
  // a raster that is halfway through being replaced by its own stored copy.
  storing.value = true
  try {
    await storeRun(mine)
  } finally {
    storing.value = false
  }
}

async function storeRun(mine: number): Promise<void> {
  const outputs: RecordOutput[] = []
  for (const { model, axis } of storingOrder()) {
    const key = cellKey(model, axis)
    const raw = fresh.get(key)
    const held = composites.value[key]
    // A COMPLETION writes the WHOLE raster, not only what it added: the run is
    // read back onto the surface afterwards, and a record holding the new rows
    // alone would take the standing ones off the screen. The cells written in
    // an earlier press travel as addresses — they are runs of their own already.
    if (!raw && !held) continue
    // The cell is a run of its own already, so its pictures travel as ADDRESSES.
    // The route says under which view each one lies (`refs`), because the
    // numbering is its to know: a picture that could not be written moves the
    // ones after it up. An address hands the recorder a place inside the
    // storage; the recorder reads that file and copies the bytes into the
    // raster run, so the raster stands complete on its own and what is saved is
    // the round trip — the browser neither holds these pictures nor sends them
    // up a further time. A view with no address sends its bytes.
    const cellRefs = held?.refs ?? {}
    const image = (view: string, data?: string, standing?: string): RecordOutput | null => {
      const ref = cellRefs[view] || (raw ? '' : storedRef(standing))
      if (ref) return { type: 'image', format: 'png', ref, meta: { model, axis, view } }
      if (data) return { type: 'image', format: 'png', dataBase64: data, meta: { model, axis, view } }
      // Neither fresh nor written: a standing cell out of a run whose own write
      // failed. It keeps its line in `results.cells` below and carries no
      // picture here.
      return null
    }

    const mean = image('mean', raw?.mean, held?.mean)
    if (mean) outputs.push(mean)
    // A set of one IS its own contact sheet, and the mean above is that picture,
    // so the route computes none and there is none to store. A cell read back
    // out of the storage shows that one picture under both readings — the sheet
    // is filled in from the mean on the way in — and writing it again here would
    // store the same bytes twice and hand back a record claiming a contact sheet
    // that was never made.
    const ownSheet = raw ? !!raw.sheet : !!held && held.sheet !== held.mean
    const sheet = ownSheet ? image('images', raw?.sheet, held?.sheet) : null
    if (sheet) outputs.push(sheet)
    const relief = image('relief', raw?.relief, held?.relief)
    if (relief) outputs.push(relief)
  }
  if (!outputs.length) return

  const cellRecords: Record<string, unknown> = {}
  for (const row of rows.value) {
    for (const axis of columns) {
      const set = singlesFor(row.id, axis)
      const key = cellKey(row.id, axis)
      cellRecords[key] = {
        model: row.id,
        axis,
        // The run the composite of this cell was written as, so a restored
        // raster can name its cells again — the single pictures below it are a
        // pipeline run each and stand in `run_ids`.
        run_id: composites.value[key]?.runId ?? null,
        run_ids: keptRunIds(key, set),
        run_states: keptStates(key, set),
        prompts: set.map(s => s.prompt),
        seeds: set.map(s => s.seed),
        count: composites.value[key]?.count ?? 0,
        // Which mean the cell was: a restored raster shows the composites that
        // were stored, and reading the kind off the model instead would name
        // the wrong one for every run made before the latents were kept.
        mean_kind: composites.value[key]?.meanKind ?? null,
        // And where there is no mean: WHY. Without this a refused cell is
        // stored as an empty one, and the raster read back out of the storage
        // shows a hole that says nothing.
        mean_blocked: overlayBlocked.value[key] ?? null,
        blocked: set.filter(s => singles.value[s.key]?.blockedKey).map(s => s.prompt),
        failed: set.filter(s => singles.value[s.key]?.failed).map(s => s.prompt),
        resized: composites.value[key]?.resized ?? false,
      }
    }
  }

  const id = await labRecord({
    parameters: {
      prompt: promptText.value,
      translation_en: translationEn.value,
      seed: runSeed.value,
      random_seed: randomSeed.value,
      n: perCellCount.value,
      columns: [...columns],
      models: rows.value.map(r => r.id),
      variants: [...variants.value],
      seeds: [...seedList.value],
    },
    // Where the variants call came back with nothing, its reason travels with
    // the run as the key of its sentence, so a raster read back says why the
    // column is empty, in the language it is read in.
    results: { cells: cellRecords, shortfall: shortfall.value, variants_failed: variantsFailed.value },
    outputs,
  })

  if (!alive || mine !== press) return
  labRunId.value = id
  // The bytes are let go only once they are somewhere else. A write that failed
  // leaves this raster's pictures in the browser and nowhere else, and a cell
  // dropped here would be gone from every later press's record too — it travels
  // by address, and it has none.
  if (!id) return
  fresh.clear()
  // What is on the surface from here on is what the storage holds: the stored
  // run is read straight back, so the cells stand at their served addresses and
  // a favourite of this run restores to exactly this picture.
  const stored = await fetchInstrumentRun(id)
  // What comes back REPLACES what stands, so every cell of the raster the reader
  // is looking at has to be in it: a write that could not carry one would
  // otherwise take that cell off the screen. Of the raster they are looking at —
  // a model switched off after an earlier press leaves its composites behind,
  // and counting those in would hold the read-back off for good.
  const shown: string[] = []
  for (const row of rows.value) {
    for (const axis of columns) {
      const key = cellKey(row.id, axis)
      if (composites.value[key]) shown.push(key)
    }
  }
  const carried = stored ? viewsHeldBy(stored) : new Set<string>()
  const whole = shown.every(key => {
    const cell = composites.value[key]
    if (!cell) return true
    const needs: string[] = []
    if (cell.mean) needs.push('mean')
    if (cell.relief) needs.push('relief')
    // A set of one is its own contact sheet — the same picture under both
    // readings — and there is no second copy of it to come back.
    if (cell.sheet && cell.sheet !== cell.mean) needs.push('images')
    return needs.every(view => carried.has(`${key}|${view}`))
  })
  if (stored && alive && mine === press && whole) {
    // The written field is the visitor's and stays theirs: they may already be
    // typing the next run while this one is being stored, and putting the stored
    // prompt back would take those keystrokes away. A run brought in from the
    // gallery is the other case — there the whole run is what is being restored,
    // the field included.
    applyInstrumentRun(stored, { takeThePrompt: false, ownRun: true })
    releaseUrls()
  }
}

/**
 * A run taken back out of the storage — from the gallery, or read back after it
 * was just written. Everything the surface shows is in the object: the settings
 * in the parameters, the composites in the outputs, each one saying which model,
 * which column and which reading it is. Nothing is generated.
 */
function applyInstrumentRun(
  obj: InstrumentRun,
  opts: { takeThePrompt?: boolean; ownRun?: boolean } = {},
): void {
  const p = (obj.parameters || {}) as Record<string, unknown>
  const takeThePrompt = opts.takeThePrompt !== false
  // This run is the one this tab has just made and is reading back, rather than
  // one brought in from the gallery. What is on the surface came out of it.
  const ownRun = opts.ownRun === true

  // What the last run left behind goes with it. These two are cleared when a
  // PRESS starts, and a restore is not a press: a raster brought in from the
  // gallery into a tab that has just run would otherwise carry that run's
  // refusals and failures into the cells of a different one.
  overlayBlocked.value = {}
  overlayFailed.value = {}
  previews.value = {}
  // The bytes of the run being replaced. They belong to a raster that is about
  // to leave the screen, and kept, the next write would carry them into a record
  // of cells they are not.
  fresh.clear()

  if (takeThePrompt && typeof p.prompt === 'string') promptText.value = p.prompt
  // What this run's material was made from, so that a press onto a restored
  // raster can tell "the rows that are missing" from "the text has changed".
  madeFrom = typeof p.prompt === 'string' ? p.prompt.trim() : ''
  if (typeof p.translation_en === 'string') translationEn.value = p.translation_en
  const storedSeed = Number.isFinite(Number(p.seed)) ? Number(p.seed) : null
  if (storedSeed !== null) runSeed.value = storedSeed
  randomSeed.value = p.random_seed === true
  madeRandom = randomSeed.value
  // Whether every input the run went out with is read back onto the surface.
  // Where one is not, the surface's settings are not the raster's, and the seed
  // automatic counts the next press as a change.
  let readWhole = takeThePrompt && typeof p.prompt === 'string'
  // The size a stored run ran with, held where the axis can stand it.
  const storedPerCell = Number(p.n)
  if (Number.isFinite(storedPerCell)) perCell.value = storedPerCell
  else readWhole = false
  let modelsRead = false
  if (Array.isArray(p.models)) {
    const kept = (p.models as unknown[]).filter(
      (m): m is string => typeof m === 'string' && MODELS.some(x => x.id === m)
    )
    if (kept.length) {
      chosenModels.value = kept
      // The rows of a stored run stand whatever this installation carries today:
      // their pictures were made and kept, and a model uninstalled since would
      // otherwise take a row of the record away.
      present.value = new Set([...present.value, ...kept])
      modelsRead = true
    }
  }
  if (!modelsRead) readWhole = false
  // The automatic writes the seed into the field and compares the next press
  // with this raster. A run this tab has just made and reads back was settled
  // when its pictures came (`startRun`).
  if (!ownRun) seedAutomatic.laidBack(readWhole ? inputsKey() : null, storedSeed)
  variants.value = Array.isArray(p.variants) ? (p.variants as string[]) : []
  variantsPending.value = false
  const variantsSaid = (obj.results as Record<string, unknown> | undefined)?.variants_failed as
    | { key?: unknown; params?: unknown }
    | null
    | undefined
  variantsFailed.value = typeof variantsSaid?.key === 'string'
    ? {
        key: variantsSaid.key,
        params: variantsSaid.params && typeof variantsSaid.params === 'object'
          ? (variantsSaid.params as Record<string, unknown>)
          : {},
      }
    : null
  seedList.value = Array.isArray(p.seeds)
    ? (p.seeds as unknown[]).map(Number).filter(n => Number.isFinite(n))
    : []
  shortfall.value = Number((obj.results as Record<string, unknown>)?.shortfall) || 0
  madeAt.value = Date.parse(obj.timestamp || '') || Date.now()

  const counts = ((obj.results || {}) as Record<string, unknown>).cells as
    | Record<
        string,
        StoredCell & {
          count?: number
          resized?: boolean
          mean_kind?: string
          mean_blocked?: string | null
        }
      >
    | undefined
  // The raster is empty on a restore, so this record is where the run ids of
  // the single pictures still stand.
  storedCells.value = counts ?? {}

  // A refused mean was never written as a picture, so the record is the only
  // place its reason still stands. Without this a restored raster shows an
  // empty cell beside full ones and leaves the reader to guess.
  const refused: Record<string, string> = {}
  for (const [key, cell] of Object.entries(counts ?? {})) {
    const said = cell?.mean_blocked
    if (typeof said === 'string' && said) refused[key] = said
  }
  overlayBlocked.value = refused

  const held: Record<string, Composite> = {}
  for (const out of obj.outputs || []) {
    const meta = (out.meta || {}) as Record<string, unknown>
    const model = typeof meta.model === 'string' ? meta.model : ''
    const axis = typeof meta.axis === 'string' ? (meta.axis as Axis) : null
    const which = typeof meta.view === 'string' ? (meta.view as View) : null
    if (!model || !axis || !which || !out.url) continue
    const key = cellKey(model, axis)
    const cell =
      held[key] ??
      (held[key] = {
        mean: '',
        sheet: '',
        relief: '',
        count: counts?.[key]?.count ?? 0,
        resized: counts?.[key]?.resized ?? false,
        // A run stored before the latents were kept carries no kind at all, and
        // every mean up to then was a pixel mean.
        meanKind: counts?.[key]?.mean_kind === 'latent' ? 'latent' : 'pixel',
        runId: counts?.[key]?.run_id ?? null,
        refs: {},
        // A record keeps one time for the whole RUN, and a completing press
        // writes cells made hours apart into one. So a cell this tab already has
        // keeps the hour it was made in, and only the ones coming in from
        // elsewhere take the run's.
        madeAt: (ownRun ? composites.value[key]?.madeAt : 0) || madeAt.value,
      })
    if (which === 'mean') cell.mean = out.url
    else if (which === 'images') cell.sheet = out.url
    else if (which === 'relief') cell.relief = out.url
    const ref = storedRef(out.url)
    if (ref && cell.refs) cell.refs[which] = ref
  }
  // A set of one carries no sheet of its own; its picture stands for it.
  for (const cell of Object.values(held)) {
    if (!cell.sheet) cell.sheet = cell.mean
  }
  composites.value = held

  // The single pictures this run was made from, put back where the surface looks
  // for them — and ONLY for a run brought in from the gallery. A press onto a
  // restored raster would otherwise find the LAST run's pictures under these
  // keys (a cell is keyed by model, seed and text, so a restored run on the same
  // three collides with them) and would generate a cell whose pictures are all
  // on disk a second time.
  //
  // A run this tab has just made and is reading back keeps what it has: the live
  // states are richer than any record — the seed each picture ACTUALLY ran with,
  // and the reason under a cell that was turned back or never came. Written over
  // by the record, a refused cell went blank and silent the moment its run
  // finished, its row said "waiting" under a raster that had stopped, and the
  // next press re-asked the model for the very picture it had just refused.
  if (!ownRun) {
    const restored: Record<string, RasterCell> = {}
    for (const [key, cell] of Object.entries(counts ?? {})) {
      const ids = Array.isArray(cell?.run_ids) ? cell.run_ids : []
      const said = Array.isArray(cell?.run_states) ? cell.run_states : []
      const at = key.indexOf('|')
      const model = at === -1 ? '' : key.slice(0, at)
      const axis = key.slice(at + 1) as Axis
      if (!model || (axis !== 'seedFixed' && axis !== 'promptFixed')) continue
      singlesFor(model, axis).forEach((single, index) => {
        const runId = ids[index]
        const state = said[index]
        const base = { key: single.key, seed: single.seed, url: '' }
        if (typeof runId === 'string' && runId) {
          restored[single.key] = { ...base, blockedKey: '', failed: false, runId }
        } else if (state?.blocked) {
          restored[single.key] = { ...base, blockedKey: state.blocked, failed: false }
        } else if (typeof state?.failed === 'string') {
          restored[single.key] = {
            ...base, blockedKey: '', failed: true, failedKey: state.failed || undefined,
          }
        }
      })
    }
    singles.value = restored
  }

  labRunId.value = obj.run_id
}

/**
 * The way back in from the platform's storage. The gallery sets the restore data
 * and then navigates here, so this looks once on arrival as well as on every
 * later change. Only runs this instrument made are taken.
 */
watch(
  () => favoritesStore.pendingRestoreData,
  (restoreData) => {
    const instrument = restoreData?.instrument
    if (!instrument || instrument.tool !== 'mean_images') return
    // This fires during setup, BEFORE the availability check has answered. The
    // flag is what tells that check to leave a restored run's rows alone.
    restored.value = true
    // A run that is still going loses its ground here: the restore replaces the
    // text, the variants, the seeds and the rows the plan was built from, so
    // every further picture would be generated into a raster that is somebody
    // else's, and the counter would then write THAT raster down under these
    // parameters. The loop is given up first, and the press it belongs to
    // stops counting as the current one: what is still out of it (the text, a
    // laying-over, the write) lands in a raster it did not make, and the seed
    // automatic would take that press for the one on the surface.
    stop()
    press++
    applyInstrumentRun(instrument)
    favoritesStore.setRestoreData(null)
  },
  { immediate: true }
)

/**
 * The star keeps the INSTRUMENT run, not one composite: what is worth keeping
 * here is the whole raster with the settings that made it, and every cell of a
 * run therefore carries the same star.
 */
const isFavorited = computed(() => (labRunId.value ? favoritesStore.isFavorited(labRunId.value) : false))

async function toggleFavorite(): Promise<void> {
  const id = labRunId.value
  if (!id) return
  await favoritesStore.toggleFavorite(id, 'image', deviceId, 'anonymous', 'mean-images')
}

// ---------------------------------------------------------------------------
// One composite, out of the browser
// ---------------------------------------------------------------------------
/**
 * The picture a cell is showing, saved under a name that leads back to its run.
 *
 * What is saved is what STANDS there — the reading the switch is on. The three
 * readings are three pictures of one set, and the one in front of the reader is
 * the one they are asking for.
 *
 * The card back has carried this button since the raster was built, and for a
 * while nothing stood behind it.
 */
async function downloadCell(model: string, axis: Axis): Promise<void> {
  const url = cellUrl(model, axis)
  if (!url) return
  // The cell's own run first: on this surface a cell IS a run, and its number
  // leads to the folder holding the pictures the mean was made from. The
  // raster's run, and then the sitting, for a cell written under neither.
  const source =
    composites.value[cellKey(model, axis)]?.runId || labRunId.value || sessionId.value
  const failed = await downloadMedia(
    url,
    mediaFileName('meanimg', [runStem(source), model, axis, view.value]),
  )
  if (failed) errorMessage.value = t('latentLab.meanImages.runFailed', { m: failed })
}

// ---------------------------------------------------------------------------
// The place of a composite in the raster, under it when it stands large
// ---------------------------------------------------------------------------
function cellPlace(row: ModelOption, axis: Axis): string {
  return `${row.label} · ${t(`latentLab.meanImages.col.${axis}`)} · ${t(`latentLab.meanImages.view.${view.value}`)}`
}

// ---------------------------------------------------------------------------
// What Help is told stands here
// ---------------------------------------------------------------------------
/**
 * How many runs this surface names at once. The chat lists at most twelve, and
 * five models by two columns is the largest raster there is — so a full raster
 * fits and nothing is silently dropped at the other end.
 */
const SURFACE_RUNS_LISTED = 12

/**
 * The address of ONE cell, live or restored.
 *
 * A cell shows a composite, which is a run this surface had written the moment
 * it was made. Restored, the raster is empty and the address comes out of the
 * stored record.
 */
function cellRunId(model: string, axis: Axis): string {
  const key = cellKey(model, axis)
  const held = composites.value[key]?.runId
  if (typeof held === 'string' && held) return held
  // Where a restored raster carried no picture for a cell there is no composite, only the record.
  const stored = storedCells.value[key]?.run_id
  return typeof stored === 'string' && stored ? stored : ''
}

/**
 * The runs standing on the surface, in raster order — the directory Help opens
 * a picture from.
 *
 * Until 2026-09-04 this was the WHOLE raster's run and nothing else, and that
 * run is written at the very end: a question about a finished cell while the
 * rest was still filling was answered with "the pictures are not visible here",
 * because there was no address to open.
 */
const surfaceRuns = computed<{ runId: string; label: string }[]>(() => {
  const out: { runId: string; label: string }[] = []
  // The whole raster's run goes FIRST wherever a set cell that stands on the
  // surface has no run of its own. A run stored before the cells were recorded
  // carries the ids of the single pictures and no cell runs at all, so the
  // raster run is the only address that holds its means.
  const setCellWithoutARun = rows.value.some(row =>
    columns.some(axis => !cellRunId(row.id, axis))
  )
  if (labRunId.value && setCellWithoutARun) {
    out.push({ runId: labRunId.value, label: t('latentLab.meanImages.view.mean') })
  }
  for (const row of rows.value) {
    for (const axis of columns) {
      const id = cellRunId(row.id, axis)
      if (!id) continue
      const column = t(`latentLab.meanImages.col.${axis}`)
      out.push({
        runId: id,
        label: `${row.label} · ${column} · ${t('latentLab.meanImages.view.mean')}`,
      })
      if (out.length >= SURFACE_RUNS_LISTED) return out
    }
  }
  return out
})

/**
 * What stands on the surface in words. The pictures cost a vision call each and
 * are opened on request; this costs nothing and travels whole, so a question
 * about what a cell IS is answered without opening anything at all.
 */
const surfaceAccounts = computed<{ label: string; text: string }[]>(() => {
  const out: { label: string; text: string }[] = []
  for (const row of rows.value) {
    for (const axis of columns) {
      const cell = composites.value[cellKey(row.id, axis)]
      if (!cell) continue
      out.push({
        label: `${row.label} · ${t(`latentLab.meanImages.col.${axis}`)}`,
        text: cellAccount(row.id, axis, cell.count, cell.meanKind),
      })
    }
  }
  // Generations, not cells: the two columns share their first picture by design,
  // so one generation serves both of them. A finished raster is counted off the
  // pictures it RESTS on rather than off the last press — a press that added a
  // row added that row alone, and the raster standing there is the whole of both
  // presses.
  const behind = Object.values(singles.value).filter(cell => cell.runId).length
  out.push({
    label: 'Run',
    text: running.value
      ? `in progress: ${done.value} of ${expected.value} steps`
      : `complete: ${behind} generations (the two columns share their first picture)`,
  })
  if (showVariants.value && variants.value.length) {
    out.push({
      label: 'Prompt variants',
      text: variants.value.map((line, i) => `${i + 1}. ${line}`).join('\n'),
    })
  }
  out.push({ label: 'View', text: view.value })
  return out
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'mean_images',
  pageContent: {
    inputText: promptText.value,
    contextPrompt: translationEn.value,
    // Cell by cell, with the whole raster's own run ahead of them wherever a
    // cell on the surface has none — `surfaceRuns` decides that, so that the
    // raster run is listed where it holds something no cell address does.
    surfaceMedia: surfaceRuns.value,
    instrumentRuns: surfaceAccounts.value,
  },
  offer: Object.keys(composites.value).length ? { label: t('compare.ask.sign') } : null,
}))

watch(pageContext, (ctx) => { pageContextStore.setPageContext(ctx) }, { immediate: true, deep: true })

onBeforeUnmount(() => {
  alive = false
  pageContextStore.clearContext()
  releaseUrls()
})

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page, the stage, the raster and the cell are shared and stand in
   assets/flow-stage.css and assets/instrument-surface.css. What is left here is
   what this surface needs beyond them and no other does. */

/* The set size carries its number in its own label: the count is what a run is
   planned with, and the handle of an axis says it only where a notch stands. */
.mi-per-cell {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.mi-per-cell b {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
}


/* The head sub-line and the stacked row name moved into assets/flow-stage.css
   when Decomposition became the second raster to carry both
   (`.lab-grid-headsub` / `.lab-grid-rowname.stacked`;
   docs/ELEMENT_STRUCTURE_REGISTRY.md). */

.mi-rowline {
  font-size: var(--flow-fs-hint);
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: rgba(255, 255, 255, 0.45);
}

/* The lines every picture of the run is made from, as they go to the model.
   They lie in a klappe, so the list carries the air under its own summary. */
.mi-variants {
  margin: 0.4rem 0 0;
  padding-left: 1.6em;
  font-size: var(--flow-fs-hint);
  font-family: 'SF Mono', 'Fira Code', monospace;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.6);
}

.mi-variants li { margin-bottom: 2px; }

/* The klappe of the instruments is the platform's and stands in
   assets/flow-stage.css (`details.advanced-settings` + `.settings-grid`). The
   field inside it is drawn by SeedControl, because a page's scoped CSS reaches
   a component's root element and nothing under it. */
</style>
