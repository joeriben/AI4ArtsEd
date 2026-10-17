<!--
  Composable Diffusion — every concept gets its own pass through the transformer,
  at every denoising step, and each one pulls the picture for itself.

  That is the denoiser, one of the two places the surface offers since
  2026-09-26. The other is the embedding: there the concepts' embeddings are
  interpolated into one before the run and the sampler makes an ordinary CFG run
  on it. Two to five concepts stand under each other, each with
  a weight. In the denoiser a negative weight subtracts instead of adding, and
  as soon as one concept is negated the weights are read as per-concept guidance
  temperatures rather than as a mixture (Liu et al., Eq. 11/15) — which is why
  the surface says afterwards which reading it ran. In the embedding a weight
  acts through its ratio to the others, so there is one reading; a weight whose
  sign differs from the others sends that share outside [0, 1] and the
  interpolation runs PAST the other concepts, which is the estrangement Split &
  Combine had and this surface keeps.

  Rebuilt into the frame the Latent Lab's instruments share, and
  it brings nothing of its own where the platform has it: the page skeleton and
  the stage proportion from assets/flow-stage.css (`.lab-page` / `.lab-main` /
  `.lab-stage` / `.lab-work` / `.lab-prep` / `.lab-col` / `.lab-plot` /
  `.lab-pick-label` / `.lab-prep-err` / `.lab-note`), the square surface around
  the picture (assets/instrument-surface.css), the trigger in the frame's bar
  (components/ShellRun.vue) and the axis with its marks
  (components/MarkedSlider.vue). See docs/ELEMENT_STRUCTURE_REGISTRY.md.

  EVERY control stands in the left column, and what the last
  run settled on stands under them — how many concepts went in, what each was
  weighted at in the end, which composition it ran, and the number it was drawn
  on. The right side carries the picture alone.
-->
<template>
  <div class="cd lab-page">
    <!-- `defer` is not optional: a Teleport resolves its target against the live
         document, and on the app's FIRST render the tree is still detached, so
         `.shell-bar-run` cannot be found. -->
    <ShellRun
      :ready="canRun"
      :running="isGenerating"
      :title="t('latentLab.composable.generateBtn')"
      @run="generate"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <PromptExamples
              :items="promptExamples"
              :current="concepts[0]?.prompt ?? ''"
              :disabled="isGenerating"
              @pick="applyExample"
            />

            <div v-for="(concept, idx) in concepts" :key="idx" class="cd-concept">
              <div class="cd-concept-head">
                <label class="lab-pick-label">{{ t('latentLab.composable.conceptLabel', { n: idx + 1 }) }}</label>
                <button
                  v-if="concepts.length > 2"
                  class="cd-remove"
                  :title="t('latentLab.composable.removeBtn')"
                  @click="removeConcept(idx)"
                  :disabled="isGenerating"
                >&times;</button>
              </div>
              <MediaInputBox
                chrome="bare"
                :placeholder="t('latentLab.composable.conceptPlaceholder')"
                :value="concept.prompt"
                @update:value="concept.prompt = $event"
                input-type="text"
                :rows="2"
                :is-filled="!!concept.prompt"
                resize-type="auto"
                :disabled="isGenerating"
                :show-preset-button="true"
                :preset-busy="enriching === concept"
                @open-preset-selector="openPreset(idx)"
                @copy="copyConcept(idx)"
                @paste="pasteConcept(idx)"
                @clear="clearConcept(idx)"
              />
              <!-- The weight, on the platform's axis. Below zero the concept is
                   subtracted instead of added, and the mark beside the number
                   says which of the two this one is. -->
              <label class="lab-pick-label cd-weight-label">
                {{ t('latentLab.composable.weightLabel') }}
                <span class="cd-weight-value">{{ concept.weight.toFixed(2) }}</span>
                <span class="cd-op" :class="concept.weight < 0 ? 'op-not' : 'op-and'">
                  {{ concept.weight < 0 ? t('latentLab.composable.operatorNot') : t('latentLab.composable.operatorAnd') }}
                </span>
              </label>
              <MarkedSlider
                :model-value="concept.weight"
                :min="-2"
                :max="2"
                :step="0.05"
                :marks="WEIGHT_MARKS"
                :disabled="isGenerating"
                :aria-label="t('latentLab.composable.weightLabel')"
                :value-text="concept.weight.toFixed(2)"
                @update:model-value="v => (concept.weight = v)"
              />
            </div>

            <button
              v-if="concepts.length < MAX_CONCEPTS"
              class="cd-add"
              @click="addConcept"
              :disabled="isGenerating"
            >+ {{ t('latentLab.composable.addConceptBtn') }}</button>

            <!-- Where the concepts are combined. Both fields carry the word the
                 Flow Logic map uses for that place ('embedding' from
                 latentLab.flow.loop.cond, 'Denoiser' from .denoiser), and the
                 reading order is the machine's: first the embedding the denoiser
                 receives, then the denoiser. Two fields on the platform's own
                 selector (components/ChipSelect.vue,
                 docs/ELEMENT_STRUCTURE_REGISTRY.md). -->
            <div class="cd-combine">
              <label class="lab-pick-label">{{ t('latentLab.composable.combineLabel') }}</label>
              <ChipSelect
                :model-value="combineAt"
                :options="combineOptions"
                :columns="2"
                :disabled="isGenerating"
                @update:model-value="v => (combineAt = v as 'score' | 'conditioning')"
              />
              <p class="lab-hint">{{ t('latentLab.composable.combineHint') }}</p>

            </div>

            <details class="advanced-settings" :open="settingsOpen" @toggle="onSettingsToggle">
              <summary>{{ t('latentLab.composable.settingsToggle') }}</summary>
              <div class="settings-grid">
                <label class="cd-wide">
                  {{ t('latentLab.composable.negativePromptLabel') }}
                  <textarea
                    class="setting-input"
                    v-model="negativePrompt"
                    :disabled="isGenerating"
                    rows="2"
                    :placeholder="t('latentLab.composable.negativePromptPlaceholder')"
                  />
                </label>
                <label>
                  {{ t('latentLab.composable.stepsLabel') }}
                  <input type="number" v-model.number="steps" min="1" max="50" :disabled="isGenerating" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.composable.cfgLabel') }}
                  <input type="number" v-model.number="cfgScale" min="1" max="20" step="0.5" :disabled="isGenerating" class="setting-input setting-small" />
                </label>
                <SeedControl v-model:seed="seed" v-model:random="randomSeed" :disabled="isGenerating" />
                <label class="cd-check cd-wide">
                  <input type="checkbox" v-model="normalizeWeights"
                         :disabled="isGenerating || hasNegativeWeight || combineAt === 'conditioning'" />
                  {{ t('latentLab.composable.normalizeLabel') }}
                </label>
              </div>
            </details>

            <p v-if="errorMessage" class="lab-prep-err">{{ errorMessage }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <!-- What the last run settled on. The weights are the ones the run
                 USED, which is not what the axes say once they were normalised. -->
            <template v-if="resultImage">
              <p class="cd-fact">
                {{ t('latentLab.composable.resultInfo', { concepts: conceptCount, time: timing, seed: actualSeed }) }}
              </p>
              <p v-if="weightsUsed.length" class="cd-weights">
                <span v-for="(w, i) in weightsUsed" :key="i" class="cd-weight-badge">
                  {{ promptsUsed[i]?.substring(0, 20) || `#${i + 1}` }}: {{ w.toFixed(2) }}
                </span>
              </p>
              <p v-if="modeLine" class="cd-mode">
                {{ modeLine }}
                <span v-if="compositionMode === 'temperature' && negatedCount > 0"> {{ t('latentLab.composable.negatedInfo', { n: negatedCount }) }}</span>
              </p>
            </template>

            <aside class="lab-note">
              <LabReferences
                flat
                :title="t('latentLab.composable.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <!-- What came out. One picture, as large as the surface allows, in
               the platform's own cell: it brings its plate, its save and the
               back with the run's facts (components/MediaGridCell.vue). -->
          <section class="lab-plot">
            <div class="instr-frame">
              <div class="instr-stack">
                <MediaGridCell
                  :url="resultImage ? `data:image/png;base64,${resultImage}` : ''"
                  :run-id="runId"
                  :prompt="runPrompt"
                  :config-id="OUTPUT_CONFIG"
                  :created-at="madeAt"
                  :facts="resultFacts"
                  :note="resultNote"
                  :is-favorited="isFavorited"
                  @toggle-favorite="toggleFavorite"
                  @download="downloadResult"
                />
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
import { ref, shallowRef, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { postDirectRun, postStreamedRun } from '@/services/directRun'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useDetailsState } from '@/composables/useDetailsState'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { refusalKeyOf, generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { downloadMedia } from '@/lib/downloadMedia'
import { useDeviceId } from '@/composables/useDeviceId'
import { useFavoritesStore } from '@/stores/favorites'
import SeedControl from '@/components/SeedControl.vue'
import { useSeedAutomatic, STANDARD_SEED } from '@/composables/useSeedAutomatic'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediaGridCell from '@/components/MediaGridCell.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import ShellRun from '@/components/ShellRun.vue'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import ChipSelect, { type ChipOption } from '@/components/ChipSelect.vue'
import { apiBase } from '@/services/labApi'

/** The composition this surface runs is Liu et al.'s, term for term. */
const REFERENCES: LabReference[] = [
  {
    authors: 'Liu et al. (2022)',
    title: '"Compositional Visual Generation with Composable Diffusion Models"',
    venue: 'ECCV 2022',
    doi: 'https://doi.org/10.1007/978-3-031-19803-8_12',
  },
]

/**
 * The axis of a weight. Zero is named because it is the place where a concept
 * stops taking part at all, and the two ends because they are where subtraction
 * and addition are at their strongest; the numbers between them read off the
 * value beside the label.
 */
const WEIGHT_MARKS: SliderMark[] = [
  { value: '−2', pct: 0 },
  { value: '−1', pct: 25 },
  { value: '0', pct: 50 },
  { value: '1', pct: 75 },
  { value: '2', pct: 100 },
]


const OUTPUT_CONFIG = 'composable_diffusion'

const { t } = useI18n()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const deviceId = useDeviceId()
const favoritesStore = useFavoritesStore()
const { record: labRecord } = useLatentLabRecorder('composable_diffusion')

/**
 * The runs of this instrument, in the frame's strip; the cards come back after a
 * reload from what the recorder wrote.
 *
 * What tells two runs of THIS instrument apart is the set of concepts and their
 * weights - that is what the card's bar says.
 */
const { addRun } = useInstrumentRuns('composable_diffusion', cardFor, {
  shell: { sourceView: 'latent-lab/composable-diffusion' },
})

function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const image = (run.outputs || []).find(o => o.type === 'image')
  if (!image?.url) return null
  const parts = Array.isArray(params.concepts) ? (params.concepts as Concept[]) : []
  const prompt = parts.map(c => c.prompt).filter(Boolean).join(' + ')
  return {
    id: run.run_id,
    label: parts.map(c => `${c.prompt?.slice(0, 12) ?? ''} ${Number(c.weight ?? 0).toFixed(2)}`).join(' · ') || prompt,
    // The place belongs beside the reading: two runs that differ in it alone
    // carry the same concepts, the same weights and the same seed.
    sub: [
      String(params.composition_mode ?? ''),
      params.combine_at === 'conditioning'
        ? t('latentLab.composable.combineEmbedding')
        : params.combine_at === 'score'
          ? t('latentLab.composable.combineDenoiser')
          : '',
    ].filter(Boolean).join(' · '),
    meta: [
      `${t('latentLab.composable.seedLabel')}: ${results.seed ?? params.seed ?? ''}`,
      `${t('latentLab.composable.cfgLabel')}: ${params.cfg ?? ''}`,
    ],
    prompt,
    configId: OUTPUT_CONFIG,
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: run.run_id,
    output: { url: image.url, media_type: 'image' },
    error: null,
  }
}
const { isOpen: settingsOpen, onToggle: onSettingsToggle } = useDetailsState('ll_composable_settings', true)

// --- State ---
interface Concept {
  prompt: string
  weight: number
}

/** How many concepts this instrument holds at once. */
const MAX_CONCEPTS = 5

const concepts = ref<Concept[]>([
  { prompt: '', weight: 1.0 },
  { prompt: '', weight: 1.0 },
])

const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(STANDARD_SEED)
const randomSeed = ref(false)
const normalizeWeights = ref(true)

/**
 * WHERE the concepts are combined. `score` is the place this instrument ran in
 * alone until 2026-09-26: one pass per concept at every step, the predictions
 * added with the weights. `conditioning` interpolates between the same
 * concepts' embeddings before the run and leaves the sampler an ordinary CFG
 * run on that one embedding; there only the ratio of the weights acts. The node
 * reads both under the same seed, sampler, scheduler and step count
 * (comfyui_nodes/ai4artsed_composable_diffusion.py, `combine_at`).
 */
const combineAt = ref<'score' | 'conditioning'>('score')

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with. The concepts are the ones sent.
 */
function inputsKey(sent: Concept[]): string {
  return JSON.stringify([sent, negativePrompt.value, steps.value, cfgScale.value,
    normalizesHere.value, combineAt.value])
}
const seedAutomatic = useSeedAutomatic(seed, randomSeed, 'lat_lab_cd_seed_yardstick')


/**
 * The two fields, in the order of the machine. Both names are the map's:
 * `latentLab.flow.loop` calls what the denoiser receives the embedding and the
 * station itself the Denoiser.
 */
const combineOptions = computed<ChipOption[]>(() => [
  { value: 'conditioning', label: t('latentLab.composable.combineEmbedding') },
  { value: 'score', label: t('latentLab.composable.combineDenoiser') },
])

const isGenerating = ref(false)
// Which run is the current one. The trigger is released before the record is
// written, so a second run can be out while the first is still being recorded,
// and only the run that started last owns `runId` and the star on the plate.
let runToken = 0
const errorMessage = ref('')
const resultImage = ref('')
const actualSeed = ref<number | null>(null)
const conceptCount = ref(0)
const weightsUsed = ref<number[]>([])
// The prompts the LAST RUN was made of. The badges under the picture are that
// run's account of itself; reading them off the fields would relabel a finished
// picture as soon as anybody touches a field.
const promptsUsed = ref<string[]>([])
const compositionMode = ref('')
// The place the LAST RUN was combined in, like the weights beside it: reading
// it off the switch would relabel a finished picture as soon as it is flipped.
const combineAtUsed = ref<'score' | 'conditioning'>('score')

// What the run will actually do with the weights, which is what the record has
// to carry: a negated concept switches the shares off, and in the embedding
// there is nothing to normalize at all.
const normalizesHere = computed(
  () => normalizeWeights.value && !hasNegativeWeight.value && combineAt.value !== 'conditioning')
const negatedCount = ref(0)
const timing = ref('')
// The cell IS the run: its id carries the star and the back of the card.
const runId = ref<string | null>(null)
const madeAt = ref(0)
// A refusal belongs at the cell it refused, and never in the words it arrives
// in: the reasons are German developer strings (composables/useGenerationStream.ts).
const blockedKey = ref('')

/**
 * What this instrument can be asked, ready to pick. An entry carries one prompt
 * per concept: what this page demonstrates is a COMBINATION, and a single
 * concept on its own demonstrates nothing. A wider curated set belongs here.
 *
 * The LINE in the list is the entry itself, joined by the sign this instrument
 * writes its concepts with (`conceptLine`). A key of its own would be one more
 * string to hold in step with the prompts across ten languages, and from the day
 * it is added until the batch catches up it stands in English over fields that
 * are not - the line would name something other than what the fields receive.
 */
const promptExamples = computed(() =>
  [
    {
      id: 'house_ship',
      fill: [
        t('latentLab.composable.promptExamples.house'),
        t('latentLab.composable.promptExamples.ship'),
      ],
    },
    {
      id: 'child_adult',
      fill: [
        t('latentLab.composable.promptExamples.childAdult'),
        t('latentLab.composable.promptExamples.childAdult2'),
      ],
    },
    {
      id: 'tree_house',
      fill: [
        t('latentLab.composable.promptExamples.treeHouse'),
        t('latentLab.composable.promptExamples.treeHouse2'),
      ],
    },
    {
      id: 'apple_tree',
      fill: [
        t('latentLab.composable.promptExamples.appleTree'),
        t('latentLab.composable.promptExamples.appleTree2'),
      ],
    },
  ].map(entry => ({ ...entry, label: entry.fill.join(' + ') })),
)

/**
 * An entry BECOMES the concept list, the way a set of pairs does on
 * Representation Engineering (`applyPairSet`; see
 * docs/ELEMENT_STRUCTURE_REGISTRY.md): a row here is a prompt
 * AND an energy, so writing only the prompts would leave the weights of
 * whatever stood there standing under the new words - the list would then read
 * as the entry while the run was something else. The rows arrive with the even
 * weighting the entry is meant to show, and stay writable afterwards. An entry
 * that cannot fill two concepts is nothing this instrument can run, and is
 * left alone.
 */
function applyExample(item: { fill: string[] }) {
  const picked = item.fill.filter(prompt => prompt.trim().length > 0)
  if (picked.length >= 2) {
    concepts.value = picked.map(prompt => ({ prompt, weight: 1.0 }))
  }
}

/** The concepts as one line — what made this picture, for the card's back. */
function conceptLine(): string {
  return concepts.value.map(c => c.prompt.trim()).filter(Boolean).join(' + ')
}

/**
 * What stands on the back of the cell: the number the picture was drawn on and
 * which of the two compositions ran. The weights and the mode stand under the
 * controls as well, because they are what this instrument READS.
 *
 * Written down when the picture comes back, NEVER computed from what the
 * controls say now: the back of a card is the record of the run that made it,
 * and a weight moved afterwards would rewrite the finished picture's own
 * account of itself.
 */
const resultFacts = ref<string[]>([])
const runPrompt = ref('')

/**
 * What the cell says when it holds no picture: why it was refused, or that a
 * run is out. A cell holds a medium or one of these, never both
 * (components/MediaGridCell.vue).
 */
const resultNote = computed(() => {
  if (blockedKey.value) return t(blockedKey.value)
  return isGenerating.value ? t('latentLab.composable.generating') : ''
})

const isFavorited = computed(() =>
  runId.value ? favoritesStore.isFavorited(runId.value) : false,
)

async function toggleFavorite(): Promise<void> {
  const id = runId.value
  if (!id) return
  await favoritesStore.toggleFavorite(id, 'image', deviceId, 'anonymous', 'composable-diffusion')
}

/**
 * The perspective in the corner of a field. A ready list over a written field
 * and the perspective in it are the platform's mandatory combination for an
 * instrument surface (docs/ELEMENT_STRUCTURE_REGISTRY.md, Rule #13). ONE
 * overlay serves every concept; which one opened it decides where the answer is
 * written back — and a concept removed while it was out is simply not there to
 * write to.
 */
const showPresetOverlay = ref(false)
// The ROW, not its place in the list: `splice` keeps a concept's identity and
// shifts every index after it, so a row removed above the one being enriched
// would make the answer land in its neighbour.
const enriching = shallowRef<Concept | null>(null)
let presetTarget: Concept | null = null

function openPreset(idx: number): void {
  presetTarget = concepts.value[idx] ?? null
  showPresetOverlay.value = true
}

// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(
  payload: { configId: string; context: string; configName: string },
): Promise<void> {
  showPresetOverlay.value = false
  const row = presetTarget
  if (!row || !row.prompt.trim()) return

  enriching.value = row
  // WHAT was asked. A pick from the list, or a hand on the field, can change the
  // row while the cloud model writes; the answer belongs to the prompt it was
  // asked about, so it goes back only while that prompt still stands there.
  const asked = row.prompt
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, row.prompt, deviceId)
    if ('written' in outcome) {
      // Written into the ROW that was enriched, and only while it is still in
      // the list AND still holds what was asked about: a concept removed, or
      // overwritten meanwhile, is not there to write to.
      if (concepts.value.includes(row) && row.prompt === asked) row.prompt = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = null
  }
}

function copyConcept(idx: number) { copyToClipboard(concepts.value[idx]?.prompt ?? '') }
function pasteConcept(idx: number) {
  // An empty clipboard is not an instruction to empty the field.
  const text = pasteFromClipboard()
  const row = concepts.value[idx]
  if (text && row) row.prompt = text
}
function clearConcept(idx: number) {
  const row = concepts.value[idx]
  if (row) row.prompt = ''
}

// --- Computed ---
const canGenerate = computed(() => {
  const filledConcepts = concepts.value.filter(c => c.prompt.trim().length > 0)
  return filledConcepts.length >= 2
})

/** The trigger in the bar: two concepts written, and nothing else out. */
const canRun = computed(() => canGenerate.value && !isGenerating.value)

// A signed mixture has no meaning: as soon as one concept is negated, the
// weights are read as per-concept guidance temperatures (Liu et al., Eq. 11/15).
// Only the concepts that GO INTO a run count: an empty row keeps the weight it
// was left at, and an empty row must not decide how the written ones are read.
const hasNegativeWeight = computed(() =>
  concepts.value.some(c => c.prompt.trim().length > 0 && c.weight < 0),
)


/**
 * How the last run read the weights, said for the place it ran in. In the
 * denoiser a weight is a share of the CFG value or a strength of its own; in
 * the embedding only the ratio acts, so there is one reading and one sentence.
 */
const modeLine = computed(() => {
  // On the mode the run REPORTED, never on the place alone: a ComfyUI older
  // than the node file samples the place it knows and reports its own reading,
  // and a run stored before 2026-09-27 carries one of the other two.
  if (compositionMode.value === 'interpolated') {
    return t('latentLab.composable.modeEmbedding')
  }
  if (compositionMode.value === 'temperature') {
    return t('latentLab.composable.modeTemperature')
  }
  if (compositionMode.value === 'mixture') {
    return t('latentLab.composable.modeMixture')
  }
  return ''
})

// --- Session persistence ---
const STORAGE_PREFIX = 'lat_lab_cd_'

function saveState() {
  sessionStorage.setItem(`${STORAGE_PREFIX}concepts`, JSON.stringify(concepts.value))
  sessionStorage.setItem(`${STORAGE_PREFIX}negPrompt`, negativePrompt.value)
  sessionStorage.setItem(`${STORAGE_PREFIX}steps`, String(steps.value))
  sessionStorage.setItem(`${STORAGE_PREFIX}cfg`, String(cfgScale.value))
  sessionStorage.setItem(`${STORAGE_PREFIX}seed`, String(seed.value))
  sessionStorage.setItem(`${STORAGE_PREFIX}randomSeed`, String(randomSeed.value))
  sessionStorage.setItem(`${STORAGE_PREFIX}normalize`, String(normalizeWeights.value))
  sessionStorage.setItem(`${STORAGE_PREFIX}combineAt`, combineAt.value)
}

function restoreState() {
  const saved = sessionStorage.getItem(`${STORAGE_PREFIX}concepts`)
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed) && parsed.length >= 2) {
        concepts.value = parsed
      }
    } catch { /* ignore */ }
  }
  negativePrompt.value = sessionStorage.getItem(`${STORAGE_PREFIX}negPrompt`) || ''
  const s = sessionStorage.getItem(`${STORAGE_PREFIX}steps`)
  if (s) steps.value = parseInt(s)
  const c = sessionStorage.getItem(`${STORAGE_PREFIX}cfg`)
  if (c) cfgScale.value = parseFloat(c)
  const sd = sessionStorage.getItem(`${STORAGE_PREFIX}seed`)
  // parseInt, not `|| 123456789`: a seed of 0 is a seed.
  const keptSeed = parseInt(sd || '')
  if (Number.isInteger(keptSeed) && keptSeed >= 0) seed.value = keptSeed
  const rs = sessionStorage.getItem(`${STORAGE_PREFIX}randomSeed`)
  if (rs) randomSeed.value = rs === 'true'
  const n = sessionStorage.getItem(`${STORAGE_PREFIX}normalize`)
  if (n) normalizeWeights.value = n === 'true'
  const place = sessionStorage.getItem(`${STORAGE_PREFIX}combineAt`)
  if (place === 'score' || place === 'conditioning') combineAt.value = place
}

onMounted(restoreState)
watch([concepts, negativePrompt, steps, cfgScale, seed, randomSeed, normalizeWeights, combineAt], saveState, { deep: true })

// --- Actions ---
function addConcept() {
  if (concepts.value.length < 5) {
    concepts.value.push({ prompt: '', weight: 1.0 })
  }
}

function removeConcept(idx: number) {
  if (concepts.value.length > 2) {
    concepts.value.splice(idx, 1)
  }
}

function downloadResult() {
  if (!resultImage.value) return
  void downloadMedia(`data:image/png;base64,${resultImage.value}`, `composable_diffusion_${actualSeed.value}.png`)
}

async function generate() {
  if (!canGenerate.value || isGenerating.value) return

  isGenerating.value = true
  const mine = ++runToken
  errorMessage.value = ''
  resultImage.value = ''
  actualSeed.value = null
  conceptCount.value = 0
  weightsUsed.value = []
  promptsUsed.value = []
  compositionMode.value = ''
  combineAtUsed.value = combineAt.value
  negatedCount.value = 0
  timing.value = ''
  // The run that stood here is over. Its id, its star and its facts go with its
  // picture, or the plate that stands while the new one is out would carry the
  // old run - and the star would keep THAT one.
  runId.value = null
  madeAt.value = 0
  resultFacts.value = []
  blockedKey.value = ''

  try {
    const baseUrl = apiBase()
    const activeConcepts = concepts.value
      .filter(c => c.prompt.trim().length > 0)
      .map(c => ({ prompt: c.prompt.trim(), weight: c.weight }))

    // The seed automatic (composables/useSeedAutomatic): the same seed when
    // something changed since the picture on the surface was made, a new one
    // when nothing did, the field's when it was typed, a new one on every run
    // under the tick. The seed goes into the field.
    const runInputs = inputsKey(activeConcepts)
    const runSeed = seedAutomatic.seedForRun(runInputs)

    const response = await postDirectRun({
      prompt: activeConcepts[0]?.prompt ?? '',
      output_config: OUTPUT_CONFIG,
      concepts: activeConcepts,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
      seed: runSeed,
      normalize_weights: normalizesHere.value,
      combine_at: combineAt.value,
    }, { baseUrl })

    if (response.data.status === 'success') {
      const data = response.data.composable_data
      if (data) {
        resultImage.value = data.image_base64
        actualSeed.value = data.seed ?? runSeed
        // This picture is now the one the next press is compared with.
        if (resultImage.value) seedAutomatic.arrived(runInputs, actualSeed.value)
        conceptCount.value = data.concept_count
        weightsUsed.value = data.weights_used || []
        // The badges belong to THIS run: the prompts as they were sent.
        promptsUsed.value = activeConcepts.map(c => c.prompt)
        compositionMode.value = data.composition_mode || ''
        combineAtUsed.value = data.combine_at === 'conditioning' ? 'conditioning' : 'score'
        negatedCount.value = data.negated_count || 0
        timing.value = data.timing_s ? `${data.timing_s}s` : ''

        const parameters = {
          concepts: activeConcepts,
          negative_prompt: negativePrompt.value,
          steps: steps.value,
          cfg: cfgScale.value,
          seed: runSeed,
          normalize_weights: normalizesHere.value,
          composition_mode: data.composition_mode,
          combine_at: combineAtUsed.value,
          guidance_used: data.guidance_used,
        }
        const results = { seed: actualSeed.value, timing_s: data.timing_s }
        madeAt.value = Date.now()
        runPrompt.value = conceptLine()
        resultFacts.value = [
          `${t('latentLab.composable.seedLabel')}: ${actualSeed.value ?? runSeed}`,
          ...(modeLine.value ? [modeLine.value] : []),
        ]
        // The run is over here: the picture stands and its facts are read. What
        // follows is bookkeeping, and it is not quick -- the record carries the
        // image back UP to the server that just made it, 2.2 MB as base64, which
        // took 10.6 s in one measurement, with the trigger staying dark long
        // after the picture was there. Holding the trigger and every field
        // through that locks a surface that is done.
        isGenerating.value = false
        // The picture is ALREADY a run of this platform: the direct endpoint
        // saved it under `run_id` before it answered. So the record carries the
        // address of that file and the recorder copies it where it lies, rather
        // than the browser sending 2.2 MB back up to the machine that just made
        // them (`ref` in composables/useLatentLabRecorder.ts; the same round
        // trip was taken out of the Denoising Archaeology on 2026-09-22, where
        // it cost 79 s of a 25-step run). Where the answer names no run, the
        // bytes travel as before, which is that instrument's rule too.
        const stored = response.data.run_id
        const recorded = await labRecord({
          parameters,
          results,
          outputs: [stored
            ? { type: 'image', format: 'png', ref: `/api/media/image/${stored}/0` }
            : { type: 'image', format: 'png', dataBase64: resultImage.value }],
        })
        // The card is built from the RECORD, through the same reader that reads
        // one back after a reload - so a run looks the same whether it was just
        // made or fetched.
        if (mine === runToken) runId.value = recorded
        if (recorded) {
          addRun(cardFor({
            run_id: recorded,
            tool: 'composable_diffusion',
            timestamp: new Date().toISOString(),
            parameters,
            results,
            outputs: [{ type: 'image', format: 'png', url: `/api/media/image/${recorded}/0`, meta: {} }],
          }))
        }
      } else {
        errorMessage.value = t('generationError.unknown')
      }
    } else {
      const key = refusalKeyOf(response.data)
      if (key) blockedKey.value = key
      else errorMessage.value = generationErrorFor(t, response.data.error || '')
    }
  } catch (err: any) {
    // A refusal is not a fault: it stands at the cell it refused, in the
    // reader's language, and the reasons are German developer strings.
    const key = refusalKeyOf(err)
    if (key) blockedKey.value = key
    else errorMessage.value = generationErrorFor(t, err)
  } finally {
    isGenerating.value = false
  }
}
const pageContextStore = usePageContextStore()

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'composable_diffusion',
  pageDescription:
    'Composable Diffusion — die siebte Kachel im Diffusion Lab. Statt den ganzen ' +
    'Prompt als einen Vektor zu kodieren, bekommt jeder Begriff seinen eigenen ' +
    'Durchgang durch den Transformer, bei jedem Entrauschungsschritt, und jeder ' +
    'zieht das Bild für sich. Jeder Begriff trägt ein Gewicht; ein negatives ' +
    'Gewicht zieht ab statt hinzu. Zwei Orte stehen zur Wahl, an denen ein ' +
    'Lauf dieselben Begriffe zusammenführt: im Denoiser, wo bei jedem ' +
    'Schritt ein Durchgang je Begriff läuft und die Vorhersagen mit den ' +
    'Gewichten addiert werden, oder im Embedding, wo vor dem Lauf zwischen ' +
    'den Embeddings der Begriffe interpoliert wird; dort wirkt ein Gewicht ' +
    'über sein Verhältnis zu den anderen, und ab drei Begriffen wirkt auch ' +
    'ihre Reihenfolge.',
  pageContent: {
    inputText: concepts.value.map(c => `${c.prompt} (${c.weight})`).join('\n'),
  },
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  pageContextStore.clearContext()
})

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page skeleton, the stage proportion and the square surface are shared and
   stand in assets/flow-stage.css and assets/instrument-surface.css. What is here
   is what this instrument alone needs: a concept with its axis, and the plate
   the one picture stands on. */

/* --- a concept ------------------------------------------------------------- */

.cd-concept {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.cd-concept-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.cd-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.4);
  border-radius: 50%;
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1;
}
.cd-remove:hover { color: #ef5350; border-color: rgba(244, 67, 54, 0.3); }
.cd-remove:disabled { opacity: 0.4; cursor: not-allowed; }

/* The label of the axis carries the value and the mark, because between two
   notches the handle alone does not say −0,35. */
.cd-weight-label {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}

.cd-weight-value {
  font-family: 'Fira Code', 'Consolas', monospace;
  color: rgba(255, 255, 255, 0.75);
}

/* Which side of zero this concept is on. Two tones, the platform's own: green
   for what is added, amber for what is taken away. */
.cd-op {
  margin-left: auto;
  padding: 0 6px;
  border-radius: 4px;
  font-size: var(--flow-fs-hint);
  line-height: 1.6;
}
.cd-op.op-and { background: rgba(76, 175, 80, 0.18); color: #7ec89a; }
.cd-op.op-not { background: rgb(255 179 0 / 0.18); color: #ffb300; }

.cd-add {
  flex: 0 0 auto;
  padding: 0.35rem 0.5rem;
  border: 1px dashed rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  background: none;
  color: rgba(255, 255, 255, 0.5);
  font-family: inherit;
  font-size: var(--flow-fs-sub);
  cursor: pointer;
}
.cd-add:hover:not(:disabled) { color: rgba(255, 255, 255, 0.85); border-color: rgba(255, 255, 255, 0.35); }
.cd-add:disabled { opacity: 0.4; cursor: not-allowed; }

/* --- where the concepts are combined ---------------------------------------- */

.cd-combine {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

/* The gloss under the two fields is `.lab-hint` from assets/flow-stage.css
   (docs/ELEMENT_STRUCTURE_REGISTRY.md); a page-local copy of those four
   declarations stood here before. */

/* --- what the last run settled on ------------------------------------------ */

.cd-fact,
.cd-mode {
  margin: 0;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.5;
}

.cd-fact { font-family: 'Fira Code', 'Consolas', monospace; }

.cd-weights {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.cd-weight-badge {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  font-size: var(--flow-fs-hint);
  font-family: 'Fira Code', 'Consolas', monospace;
  color: rgba(255, 255, 255, 0.55);
}


/* --- the run's own settings ------------------------------------------------ */

/* The klappe of the instruments is the platform's and stands in
   assets/flow-stage.css (`details.advanced-settings` + `.settings-grid`). */

/* The negative prompt and the switch take the whole width of the klappe; the
   numbers stand beside each other. */
.cd-wide { flex: 1 1 100%; }

.cd-check {
  flex-direction: row !important;
  align-items: center;
  gap: 0.4rem;
}

/* The klappe is the platform's (assets/flow-stage.css). What stays here is what
   only this surface needs: its settings are WRITTEN into, in textareas, and a
   textarea keeps the browser's own face and its own resize grip unless it is
   told otherwise. */
.setting-input {
  font-family: inherit;
  resize: vertical;
}

/* Narrow windows: the two surfaces stand under each other and the page scrolls
   in the work area, as every instrument of this frame does. */
@media (max-width: 640px) {
  .lab-stage { flex: 0 0 auto; }
  .lab-work { grid-template-columns: 1fr; }
}
</style>
