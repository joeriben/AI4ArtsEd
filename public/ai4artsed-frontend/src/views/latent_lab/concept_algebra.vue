<!--
  Concept Algebra — the word arithmetic of Mikolov et al., done on a diffusion
  model's conditioning: A minus B plus C, and the picture that comes out of the
  sum.

  Two pictures stand side by side and the pair IS the reading: the reference is
  what prompt A alone makes, the result is what the sum makes, at the SAME seed
  and the same settings — so the difference between them is the arithmetic and
  nothing else. How far each side is scaled is a setting, and the L2 distance
  between the two conditionings says how far the sum moved from A.

  Rebuilt on 2026-09-05 into the frame the Latent Lab's instruments share, and
  it brings nothing of its own where the platform has it: the page skeleton and
  the stage proportion from assets/flow-stage.css (`.lab-page` / `.lab-main` /
  `.lab-stage` / `.lab-work` / `.lab-prep` / `.lab-col` / `.lab-plot` /
  `.lab-pick-label` / `.lab-prep-err`), the picture raster with a head over
  every column (`.lab-grid` / `.lab-grid-col` / `.lab-grid-head`), the square
  surface around a picture (assets/instrument-surface.css), the trigger in the
  frame's bar (components/ShellRun.vue), and the encoder choice as fields
  (components/ChipSelect.vue). See docs/ELEMENT_STRUCTURE_REGISTRY.md.

  EVERY control stands in the left column; the right side carries only what
  came out.
-->
<template>
  <div class="ca lab-page">
    <!-- `defer` is not optional: a Teleport resolves its target against the live
         document, and on the app's FIRST render the tree is still detached, so
         `.shell-bar-run` cannot be found. -->
    <ShellRun
      :ready="canRun"
      :running="isGenerating"
      :title="t('latentLab.algebra.generateBtn')"
      @run="compute"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- The whole calculation, ready to pick: one entry fills all three
                 fields, because the three operands only demonstrate anything
                 together. -->
            <PromptExamples
              :items="promptExamples"
              :current="promptA"
              :disabled="isGenerating"
              @pick="applyExample"
            />

            <label class="lab-pick-label">{{ t('latentLab.algebra.promptALabel') }}</label>
            <MediaInputBox
              chrome="bare"
              :placeholder="t('latentLab.algebra.promptAPlaceholder')"
              v-model:value="promptA"
              input-type="text"
              :rows="3"
              :is-filled="!!promptA"
              resize-type="auto"
              :disabled="isGenerating"
              :show-preset-button="true"
              :preset-busy="enriching === 'a'"
              @open-preset-selector="openPreset('a')"
              @copy="copyPromptA"
              @paste="pastePromptA"
              @clear="clearPromptA"
            />

            <!-- The sum the three fields stand in, written out once. -->
            <p class="ca-formula">{{ t('latentLab.algebra.formulaLabel') }}</p>

            <label class="lab-pick-label">{{ t('latentLab.algebra.promptBLabel') }}</label>
            <MediaInputBox
              chrome="bare"
              :placeholder="t('latentLab.algebra.promptBPlaceholder')"
              v-model:value="promptB"
              input-type="text"
              :rows="3"
              :is-filled="!!promptB"
              resize-type="auto"
              :disabled="isGenerating"
              :show-preset-button="true"
              :preset-busy="enriching === 'b'"
              @open-preset-selector="openPreset('b')"
              @copy="copyPromptB"
              @paste="pastePromptB"
              @clear="clearPromptB"
            />

            <label class="lab-pick-label">{{ t('latentLab.algebra.promptCLabel') }}</label>
            <MediaInputBox
              chrome="bare"
              :placeholder="t('latentLab.algebra.promptCPlaceholder')"
              v-model:value="promptC"
              input-type="text"
              :rows="3"
              :is-filled="!!promptC"
              resize-type="auto"
              :disabled="isGenerating"
              :show-preset-button="true"
              :preset-busy="enriching === 'c'"
              @open-preset-selector="openPreset('c')"
              @copy="copyPromptC"
              @paste="pastePromptC"
              @clear="clearPromptC"
            />

            <label class="lab-pick-label">{{ t('latentLab.algebra.encoderLabel') }}</label>
            <ChipSelect
              :model-value="selectedEncoder"
              :options="encoderChoices"
              :columns="2"
              :disabled="isGenerating"
              @update:model-value="v => (selectedEncoder = v as EncoderId)"
            />

            <details class="advanced-settings" :open="advancedOpen" @toggle="onAdvancedToggle">
              <summary>{{ t('latentLab.algebra.advancedLabel') }}</summary>
              <div class="settings-grid">
                <label>
                  {{ t('latentLab.algebra.negativeLabel') }}
                  <input v-model="negativePrompt" type="text" class="setting-input" />
                </label>
                <label>
                  {{ t('latentLab.algebra.stepsLabel') }}
                  <input v-model.number="steps" type="number" min="10" max="50" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.algebra.cfgLabel') }}
                  <input v-model.number="cfgScale" type="number" min="1" max="20" step="0.5" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.algebra.scaleSubLabel') }}
                  <input v-model.number="scaleSub" type="number" min="0" max="3" step="0.1" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.algebra.scaleAddLabel') }}
                  <input v-model.number="scaleAdd" type="number" min="0" max="3" step="0.1" class="setting-input setting-small" />
                </label>
                <SeedControl v-model:seed="seed" v-model:random="randomSeed" />
              </div>
            </details>

            <p v-if="errorMessage" class="lab-prep-err">{{ errorMessage }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <aside class="lab-note">
              <LabReferences
                flat
                :title="t('latentLab.algebra.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <section class="lab-plot">
            <div class="lab-grid one-row" :style="{ '--lab-grid-cols': 2 }">
              <div class="lab-grid-col">
                <div class="lab-grid-head">{{ t('latentLab.algebra.referenceLabel') }}</div>
                <div class="instr-frame">
                  <div class="instr-stack">
                    <MediaGridCell
                      :url="referenceImage ? `data:image/png;base64,${referenceImage}` : ''"
                      :run-id="runId"
                      :prompt="runPrompt"
                      :config-id="OUTPUT_CONFIG"
                      :created-at="madeAt"
                      :facts="referenceFacts"
                      :note="referenceNote"
                      :is-favorited="isFavorited"
                      :label="t('latentLab.algebra.referenceLabel')"
                      @toggle-favorite="toggleFavorite"
                      @download="downloadReference"
                    />
                  </div>
                </div>
              </div>

              <div class="lab-grid-col">
                <div class="lab-grid-head">{{ t('latentLab.algebra.resultLabel') }}</div>
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
                      :label="t('latentLab.algebra.resultLabel')"
                      @toggle-favorite="toggleFavorite"
                      @download="downloadResult"
                    />
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { postDirectRun, postStreamedRun } from '@/services/directRun'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediaGridCell from '@/components/MediaGridCell.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import SeedControl from '@/components/SeedControl.vue'
import { useSeedAutomatic, STANDARD_SEED } from '@/composables/useSeedAutomatic'
import ChipSelect from '@/components/ChipSelect.vue'
import ShellRun from '@/components/ShellRun.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { refusalKeyOf, generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { downloadMedia } from '@/lib/downloadMedia'
import { useDeviceId } from '@/composables/useDeviceId'
import { useFavoritesStore } from '@/stores/favorites'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useDetailsState } from '@/composables/useDetailsState'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'
import { apiBase } from '@/services/labApi'

/**
 * The word arithmetic is Mikolov et al.'s, and Liu et al. is what carries it
 * over to a diffusion model's conditioning.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Mikolov et al. (2013)',
    title: '"Distributed Representations of Words and Phrases and their Compositionality"',
    venue: 'NeurIPS 2013',
    doi: 'https://doi.org/10.48550/arXiv.1310.4546',
  },
  {
    authors: 'Liu et al. (2022)',
    title: '"Compositional Visual Generation with Composable Diffusion Models"',
    venue: 'ECCV 2022',
    doi: 'https://doi.org/10.1007/978-3-031-19803-8_12',
  },
]

const { t } = useI18n()
const pageContextStore = usePageContextStore()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const deviceId = useDeviceId()
const favoritesStore = useFavoritesStore()
const { record: labRecord } = useLatentLabRecorder('concept_algebra')

/**
 * The runs of this instrument, in the frame's strip. What tells two of them
 * apart is the sum they were asked - A minus B plus C - and how far each side
 * was scaled, so that is what the card's bar says.
 *
 * The card shows the RESULT. A run records the reference picture first and the
 * result second, and the last image of the run is the one it was made for.
 */
const { addRun } = useInstrumentRuns('concept_algebra', cardFor, {
  shell: { sourceView: 'latent-lab/concept-algebra' },
})

function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const images = (run.outputs || []).filter(o => o.type === 'image')
  const image = images[images.length - 1]
  if (!image?.url) return null
  const head = (text: unknown) => String(text ?? '').trim().split(/\s+/).slice(0, 3).join(' ')
  return {
    id: run.run_id,
    label: `${head(params.prompt_a)} − ${head(params.prompt_b)} + ${head(params.prompt_c)}`,
    sub: `−${Number(params.scale_sub ?? 0).toFixed(2)} · +${Number(params.scale_add ?? 0).toFixed(2)}`,
    meta: [
      `seed: ${results.seed ?? params.seed ?? ""}`,
      `L2: ${typeof results.l2_distance === "number" ? results.l2_distance.toFixed(3) : "—"}`,
      `encoder: ${params.encoder ?? ""}`,
    ],
    prompt: String(params.prompt_a ?? ''),
    configId: OUTPUT_CONFIG,
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: run.run_id,
    output: { url: image.url, media_type: 'image' },
    error: null,
  }
}
const { isOpen: advancedOpen, onToggle: onAdvancedToggle } = useDetailsState('ll_algebra_advanced')

// Encoder options
type EncoderId = 'all' | 'clip_l' | 'clip_g' | 't5'
const OUTPUT_CONFIG = 'concept_algebra'

const encoders: { id: EncoderId; labelKey: string }[] = [
  { id: 'all', labelKey: 'encoderAll' },
  { id: 'clip_l', labelKey: 'encoderClipL' },
  { id: 'clip_g', labelKey: 'encoderClipG' },
  { id: 't5', labelKey: 'encoderT5' },
]

/** The same four, as the fields ChipSelect draws. */
const encoderChoices = computed(() =>
  encoders.map(e => ({ value: e.id, label: t(`latentLab.algebra.${e.labelKey}`) })),
)

// State
const promptA = ref('')
const promptB = ref('')
const promptC = ref('')
const selectedEncoder = ref<EncoderId>('all')
const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(STANDARD_SEED)
const randomSeed = ref(false)
const scaleSub = ref(1.0)
const scaleAdd = ref(1.0)

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with.
 */
function inputsKey(): string {
  return JSON.stringify([promptA.value, promptB.value, promptC.value, selectedEncoder.value,
    negativePrompt.value, steps.value, cfgScale.value, scaleSub.value, scaleAdd.value])
}
const seedAutomatic = useSeedAutomatic(seed, randomSeed, 'lat_lab_ca_seed_yardstick')

const isGenerating = ref(false)
const errorMessage = ref('')

// Result data
const referenceImage = ref('')
const resultImage = ref('')
const actualSeed = ref<number | null>(null)
const l2Distance = ref<number | null>(null)
// Both cells are the SAME run - one calculation makes the pair - so they carry
// one id, one star, and the same time.
const runId = ref<string | null>(null)
const madeAt = ref(0)
// A refusal belongs at the cell it refused, and never in the words it arrives
// in: the reasons are German developer strings (composables/useGenerationStream.ts).
const blockedKey = ref('')

// Computed
/** The trigger in the bar: three operands written, and nothing else out. */
const canRun = computed(() =>
  !isGenerating.value && !!promptA.value.trim() && !!promptB.value.trim() && !!promptC.value.trim(),
)

// Session persistence — restore on mount
onMounted(() => {
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  if (s('lat_lab_ca_promptA')) promptA.value = s('lat_lab_ca_promptA')!
  if (s('lat_lab_ca_promptB')) promptB.value = s('lat_lab_ca_promptB')!
  if (s('lat_lab_ca_promptC')) promptC.value = s('lat_lab_ca_promptC')!
  const enc = s('lat_lab_ca_encoder')
  if (enc && ['all', 'clip_l', 'clip_g', 't5'].includes(enc)) selectedEncoder.value = enc as EncoderId
  if (s('lat_lab_ca_negative')) negativePrompt.value = s('lat_lab_ca_negative')!
  if (s('lat_lab_ca_steps')) steps.value = parseFloat(s('lat_lab_ca_steps')!) || 25
  if (s('lat_lab_ca_cfg')) cfgScale.value = parseFloat(s('lat_lab_ca_cfg')!) || 4.5
  // parseInt, not `|| 123456789`: a seed of 0 is a seed.
  const keptSeed = parseInt(s('lat_lab_ca_seed') || '')
  if (Number.isInteger(keptSeed) && keptSeed >= 0) seed.value = keptSeed
  if (s('lat_lab_ca_random_seed')) randomSeed.value = s('lat_lab_ca_random_seed') === 'true'
  if (s('lat_lab_ca_scaleSub')) scaleSub.value = parseFloat(s('lat_lab_ca_scaleSub')!) || 1.0
  if (s('lat_lab_ca_scaleAdd')) scaleAdd.value = parseFloat(s('lat_lab_ca_scaleAdd')!) || 1.0
})

// Session persistence — save on change
watch(promptA, v => sessionStorage.setItem('lat_lab_ca_promptA', v))
watch(promptB, v => sessionStorage.setItem('lat_lab_ca_promptB', v))
watch(promptC, v => sessionStorage.setItem('lat_lab_ca_promptC', v))
watch(selectedEncoder, v => sessionStorage.setItem('lat_lab_ca_encoder', v))
watch([negativePrompt, steps, cfgScale, seed, randomSeed, scaleSub, scaleAdd], () => {
  sessionStorage.setItem('lat_lab_ca_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_ca_steps', String(steps.value))
  sessionStorage.setItem('lat_lab_ca_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_ca_seed', String(seed.value))
  sessionStorage.setItem('lat_lab_ca_random_seed', String(randomSeed.value))
  sessionStorage.setItem('lat_lab_ca_scaleSub', String(scaleSub.value))
  sessionStorage.setItem('lat_lab_ca_scaleAdd', String(scaleAdd.value))
})

// Clipboard helpers
/**
 * What stands on the back of a cell: the number both pictures were drawn on,
 * which encoder was read, and - on the result - how far the sum moved from A.
 * This is where the two lines under the column went.
 *
 * Written down when the pictures come back, NEVER computed from what the
 * controls say now: the back of a card is the record of the run that made it,
 * and a chip changed afterwards would rewrite the finished picture's own
 * account of itself.
 */
const referenceFacts = ref<string[]>([])
const resultFacts = ref<string[]>([])
// The same for the prompt on the back, and for the same reason.
const runPrompt = ref('')

function encoderLabel(): string {
  const key = encoders.find(e => e.id === selectedEncoder.value)?.labelKey
  return key ? t(`latentLab.algebra.${key}`) : ''
}

/**
 * What a cell says when it holds no picture: why it was refused, that a run is
 * out, or - on the result plate - what it fills from. A cell holds a medium or
 * one of these, never both (components/MediaGridCell.vue).
 */
const referenceNote = computed(() => {
  if (blockedKey.value) return t(blockedKey.value)
  return isGenerating.value ? t('latentLab.algebra.generating') : ''
})

const resultNote = computed(() => {
  if (blockedKey.value) return t(blockedKey.value)
  if (isGenerating.value) return t('latentLab.algebra.generating')
  return resultImage.value ? '' : t('latentLab.algebra.resultHint')
})

/**
 * ONE star for both cells: what is worth keeping here is the CALCULATION, and
 * both pictures are that one run - as every cell of a raster carries the run's
 * star in Mean Images. The platform's favourite addresses a run's FIRST output,
 * which is why the result is written down first below: the result is what this
 * instrument makes, the reference is its control.
 */
const isFavorited = computed(() =>
  runId.value ? favoritesStore.isFavorited(runId.value) : false,
)

async function toggleFavorite(): Promise<void> {
  const id = runId.value
  if (!id) return
  await favoritesStore.toggleFavorite(id, 'image', deviceId, 'anonymous', 'concept-algebra')
}

/**
 * The perspective in the corner of a field. A ready list over a written field
 * and the perspective in it are the platform's mandatory combination for an
 * instrument surface (docs/ELEMENT_STRUCTURE_REGISTRY.md, Rule #13). ONE
 * overlay serves all three fields; which one opened it decides where the answer
 * is written back.
 */
type Field = 'a' | 'b' | 'c'

const showPresetOverlay = ref(false)
const enriching = ref<Field | ''>('')
let presetTarget: Field = 'a'

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
  payload: { configId: string; context: string; configName: string },
): Promise<void> {
  showPresetOverlay.value = false
  const which = presetTarget
  const field = which === 'a' ? promptA : which === 'b' ? promptB : promptC
  if (!field.value.trim()) return

  enriching.value = which
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, field.value, deviceId)
    if ('written' in outcome) {
      field.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = ''
  }
}

function copyPromptA() { copyToClipboard(promptA.value) }
function pastePromptA() { promptA.value = pasteFromClipboard() }
function clearPromptA() { promptA.value = ''; sessionStorage.removeItem('lat_lab_ca_promptA') }
function copyPromptB() { copyToClipboard(promptB.value) }
function pastePromptB() { promptB.value = pasteFromClipboard() }
function clearPromptB() { promptB.value = ''; sessionStorage.removeItem('lat_lab_ca_promptB') }
function copyPromptC() { copyToClipboard(promptC.value) }
function pastePromptC() { promptC.value = pasteFromClipboard() }
function clearPromptC() { promptC.value = ''; sessionStorage.removeItem('lat_lab_ca_promptC') }

/**
 * A TRIPLE, because the instrument is one operation and not three prompts: what
 * it demonstrates only holds if the three operands belong together. So one entry
 * fills all three fields, and the list reads as the calculation it performs.
 * One entry so far: the one this page has always shown behind its own fields.
 */
const promptExamples = computed(() => [
  {
    id: 'river',
    label: t('latentLab.algebra.promptExamples.riverLabel'),
    fill: [
      t('latentLab.algebra.promptExamples.riverA'),
      t('latentLab.algebra.promptExamples.riverB'),
      t('latentLab.algebra.promptExamples.riverC'),
    ],
  },
  {
    id: 'child',
    label: t('latentLab.algebra.promptExamples.childLabel'),
    fill: [
      t('latentLab.algebra.promptExamples.childA'),
      t('latentLab.algebra.promptExamples.childB'),
      t('latentLab.algebra.promptExamples.childC'),
    ],
  },
  {
    id: 'lonely',
    label: t('latentLab.algebra.promptExamples.lonelyLabel'),
    fill: [
      t('latentLab.algebra.promptExamples.lonelyA'),
      t('latentLab.algebra.promptExamples.lonelyB'),
      t('latentLab.algebra.promptExamples.lonelyC'),
    ],
  },
])

function applyExample(item: { fill: string[] }) {
  promptA.value = item.fill[0] ?? ''
  promptB.value = item.fill[1] ?? ''
  promptC.value = item.fill[2] ?? ''
}

function downloadReference() {
  if (!referenceImage.value) return
  void downloadMedia(`data:image/png;base64,${referenceImage.value}`, `concept_algebra_reference_${actualSeed.value}.png`)
}

function downloadResult() {
  if (!resultImage.value) return
  void downloadMedia(`data:image/png;base64,${resultImage.value}`, `concept_algebra_result_${actualSeed.value}.png`)
}

async function compute() {
  if (!promptA.value.trim() || !promptB.value.trim() || !promptC.value.trim() || isGenerating.value) return

  isGenerating.value = true
  errorMessage.value = ''
  referenceImage.value = ''
  resultImage.value = ''
  actualSeed.value = null
  l2Distance.value = null
  // The run that stood here is over. Its id, its star and its facts go with its
  // pictures, or the plates that stand while the new one is out would carry the
  // old run - and the star would keep THAT one.
  runId.value = null
  madeAt.value = 0
  referenceFacts.value = []
  resultFacts.value = []
  blockedKey.value = ''

  // The seed automatic (composables/useSeedAutomatic): the same seed when
  // something changed since the picture on the surface was made, a new one
  // when nothing did, the field's when it was typed, a new one on every run
  // under the tick. The seed goes into the field.
  const runInputs = inputsKey()
  const runSeed = seedAutomatic.seedForRun(runInputs)

  try {
    const baseUrl = apiBase()
    const response = await postDirectRun({
      prompt: promptA.value,
      output_config: OUTPUT_CONFIG,
      seed: runSeed,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
      prompt_b: promptB.value,
      prompt_c: promptC.value,
      algebra_encoder: selectedEncoder.value,
      scale_sub: scaleSub.value,
      scale_add: scaleAdd.value,
    }, { baseUrl })

    if (response.data.status === 'success') {
      const algData = response.data.algebra_data
      if (algData) {
        referenceImage.value = algData.reference_image || ''
        resultImage.value = algData.result_image || ''
        l2Distance.value = algData.l2_distance ?? null
        actualSeed.value = response.data.media_output?.seed ?? algData.seed ?? null
        // This pair is now the one the next press is compared with.
        if (referenceImage.value || resultImage.value) seedAutomatic.arrived(runInputs, actualSeed.value ?? runSeed)

        // Record for research export
        // The RESULT first, the reference after it: the platform's favourite and
        // the card in the strip both address a run's FIRST output, and what this
        // instrument makes is the result - the reference is its control.
        const outputs: { type: 'image'; format: string; dataBase64: string }[] = []
        if (resultImage.value) outputs.push({ type: 'image', format: 'png', dataBase64: resultImage.value })
        if (referenceImage.value) outputs.push({ type: 'image', format: 'png', dataBase64: referenceImage.value })
        const parameters = {
          prompt_a: promptA.value, prompt_b: promptB.value, prompt_c: promptC.value,
          encoder: selectedEncoder.value, negative_prompt: negativePrompt.value,
          steps: steps.value, cfg: cfgScale.value, seed: runSeed,
          scale_sub: scaleSub.value, scale_add: scaleAdd.value,
        }
        const results = { seed: actualSeed.value, l2_distance: l2Distance.value }
        madeAt.value = Date.now()
        runPrompt.value = promptA.value
        referenceFacts.value = [
          `${t('latentLab.algebra.seedLabel')}: ${actualSeed.value ?? runSeed}`,
          encoderLabel(),
        ]
        resultFacts.value = l2Distance.value === null
          ? [...referenceFacts.value]
          : [...referenceFacts.value, `${t('latentLab.algebra.l2Label')}: ${l2Distance.value.toFixed(4)}`]
        const recorded = await labRecord({ parameters, results, outputs })
        runId.value = recorded
        if (recorded && outputs.length) {
          // Through the same reader that reads a run back after a reload.
          addRun(cardFor({
            run_id: recorded,
            tool: 'concept_algebra',
            timestamp: new Date().toISOString(),
            parameters,
            results,
            outputs: outputs.map((_, index) => ({
              type: 'image',
              format: 'png',
              url: `/api/media/image/${recorded}/${index}`,
              meta: {},
            })),
          }))
        }
      } else {
        errorMessage.value = t('generationError.unknown')
      }
    } else {
      const key = refusalKeyOf(response.data)
      if (key) blockedKey.value = key
      else errorMessage.value = generationErrorFor(t, response.data.error || response.data.message || '')
    }
  } catch (err: unknown) {
    // A refusal is not a fault: it stands at the cells it refused, in the
    // reader's language, and the reasons are German developer strings.
    const key = refusalKeyOf(err)
    if (key) blockedKey.value = key
    else errorMessage.value = generationErrorFor(t, err)
  } finally {
    isGenerating.value = false
  }
}

// Trashy Page Context
const trashyFocusHint = computed<FocusHint>(() => {
  if (isGenerating.value || resultImage.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  return { x: 8, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'concept_algebra',
  pageContent: {
    inputText: `A: ${promptA.value}\nB: ${promptB.value}\nC: ${promptC.value}`,
  },
  focusHint: trashyFocusHint.value,
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onUnmounted(() => {
  pageContextStore.clearContext()
})

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page skeleton, the stage proportion, the picture raster and the square
   surface are shared and stand in assets/flow-stage.css and
   assets/instrument-surface.css. What is here is what this instrument alone
   needs. */

/* The square takes the narrower side of its field, which here is the WIDTH of a
   column — so the height it does not use is left over. It stands as ONE strip
   below the pair rather than as a band above and below each picture. */

/* The stack is the square and the one button that saves the picture; that
   button's height has to come off the square (assets/instrument-surface.css,
   `--instr-reserve`). */

/* The sum, between the field it starts from and the two it is made of. */
.ca-formula {
  margin: 2px 0;
  text-align: center;
  font-size: var(--flow-fs-sub);
  font-family: 'Fira Code', 'Consolas', monospace;
  color: rgba(255, 255, 255, 0.55);
  letter-spacing: 0.08em;
}

/* The titles with their DOI, at the foot of the column. The box is the
   platform's note box; there is no prose above them on this surface, so it
   carries the references alone. */
.lab-note { flex: 0 0 auto; }

/* The klappe of the instruments is the platform's and stands in
   assets/flow-stage.css (`details.advanced-settings` + `.settings-grid`). */

/* Narrow windows: the two surfaces stand under each other and the page scrolls
   in the work area, as every instrument of this frame does. */
@media (max-width: 640px) {
  .lab-stage { flex: 0 0 auto; }
  .lab-work { grid-template-columns: 1fr; }
}
</style>
