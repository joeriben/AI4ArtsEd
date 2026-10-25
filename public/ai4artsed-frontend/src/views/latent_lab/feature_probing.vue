<!--
  Dimension Explorer — which dimensions of the text embedding carry the
  difference between two prompts, and what the picture does when they are moved
  over. Built as Feature Probing and renamed on 2026-09-27; the file, the config
  id, the tab id and the source written with runs and favorites keep the old
  name.

  Two prompts go in. The analysis encodes both, takes the mean absolute
  deviation across the token positions and ranks the dimensions by it; the run
  also makes the picture prompt A stands for. A range of those ranks is then
  chosen and transferred from B into A, at the SAME seed, so the second picture
  differs from the first in the chosen dimensions and in nothing else.

  Rebuilt on 2026-09-05 into the frame the Latent Lab's instruments share, and
  it brings nothing of its own where the platform has it: the page skeleton and
  the stage proportion from assets/flow-stage.css (`.lab-page` / `.lab-main` /
  `.lab-stage` / `.lab-work` / `.lab-prep` / `.lab-col` / `.lab-plot` /
  `.lab-pick-label` / `.lab-prep-err`), the picture raster with a head over
  every column (`.lab-grid` / `.lab-grid-col` / `.lab-grid-head`), the square
  surface around a picture (assets/instrument-surface.css), both triggers in the
  frame's bar, numbered (components/ShellRun.vue), the encoder choice as fields
  (components/ChipSelect.vue). See docs/ELEMENT_STRUCTURE_REGISTRY.md.

  EVERY control stands in the left column: the two prompts, the encoder, the
  run's settings, and the rank selection with the list it is read against. The
  right side carries only what came out, at one seed: prompt A's picture, the
  same picture with the transferred dimensions in the middle, and prompt B's
  own picture on the right.
-->
<template>
  <div class="fp lab-page">
    <!-- Two runs, both started from the bar, each triangle with its number in
         it: 1 measures and makes prompt A's picture, 2 makes
         prompt B's picture when none stands for it, then carries the chosen
         dimensions of B over and makes the mix. 2 stays
         dimmed until 1 has measured. 1 measures on every encoder at once, so a
         change of encoder switches the list and runs nothing.
         The second trigger stood at the foot of
         the column before, under the list. `defer` is not optional: a
         Teleport resolves its target against the live document, and on the
         app's FIRST render the tree is still detached, so `.shell-bar-run`
         cannot be found. -->
    <ShellRun
      :steps="runSteps"
      :running="isGenerating"
      @run="runStep"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- A PAIR, not two offers: what this instrument shows is the
                 difference between two prompts, so one pick fills both fields. -->
            <PromptExamples
              :items="promptExamples"
              :current="promptA"
              :disabled="isGenerating"
              @pick="applyExample"
            />

            <label class="lab-pick-label">{{ t('latentLab.probing.promptALabel') }}</label>
            <MediaInputBox
              chrome="bare"
              :placeholder="t('latentLab.probing.promptAPlaceholder')"
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

            <label class="lab-pick-label">{{ t('latentLab.probing.promptBLabel') }}</label>
            <MediaInputBox
              chrome="bare"
              :placeholder="t('latentLab.probing.promptBPlaceholder')"
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

            <!-- Which encoder is probed. SD 3.5 carries three, and the fourth
                 field is all of them together. -->
            <label class="lab-pick-label">{{ t('latentLab.probing.encoderLabel') }}</label>
            <ChipSelect
              :model-value="selectedEncoder"
              :options="encoderChoices"
              :columns="2"
              :disabled="isGenerating"
              @update:model-value="v => (selectedEncoder = v as EncoderId)"
            />

            <details class="advanced-settings" :open="advancedOpen" @toggle="onAdvancedToggle">
              <summary>{{ t('latentLab.probing.advancedLabel') }}</summary>
              <div class="settings-grid">
                <label>
                  {{ t('latentLab.probing.negativeLabel') }}
                  <input v-model="negativePrompt" type="text" class="setting-input" />
                </label>
                <label>
                  {{ t('latentLab.probing.stepsLabel') }}
                  <input v-model.number="steps" type="number" min="10" max="50" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.probing.cfgLabel') }}
                  <input v-model.number="cfgScale" type="number" min="1" max="20" step="0.5" class="setting-input setting-small" />
                </label>
                <SeedControl v-model:seed="seed" v-model:random="randomSeed" />
              </div>
            </details>

            <!-- The selection, and the list it is made against. It stands under
                 the settings because it is only reachable after a run, and it
                 is a control: which ranks go over into the second picture. -->
            <div class="fp-select" :class="{ disabled: !listMatchesEncoder }">
              <label class="lab-pick-label">{{ t('latentLab.probing.sliderLabel') }}</label>

              <!-- The ranks are read as the UNION of up to four ranges. The track
                   itself is the platform's (components/RangeTrack.vue); what
                   stands beside its numbers is what only this instrument does
                   with them. -->
              <RangeTrack
                v-model="ranges"
                :max="nonzeroDimCount"
                :max-ranges="MAX_RANGES"
                :disabled="!listMatchesEncoder"
              >
                <template #actions>
                  <button class="mini-btn" @click="selectAll" :disabled="!listMatchesEncoder">{{ t('latentLab.probing.selectAll') }}</button>
                  <button class="mini-btn" @click="selectNone" :disabled="!listMatchesEncoder">{{ t('latentLab.probing.selectNone') }}</button>
                  <button class="mini-btn" @click="toggleSort" :disabled="!listMatchesEncoder">
                    {{ sortAscending ? t('latentLab.probing.sortAsc') : t('latentLab.probing.sortDesc') }}
                  </button>
                </template>
              </RangeTrack>

              <p class="fp-selection">
                {{ t('latentLab.probing.selectionDesc', { count: selectedDimCount, ranges: selectionRangesText, total: nonzeroDimCount }) }}
              </p>

              <!-- The list the ranks are counted in. It scrolls in itself: at
                   four thousand dimensions the column would otherwise be the
                   page, and everything above it out of reach. -->
              <p class="lab-pick-label">{{ t('latentLab.probing.listTitle', { count: nonzeroDimCount }) }}</p>

              <div class="fp-dims" v-if="displayDims.length > 0">
                <div v-for="dim in sortedDisplayDims" :key="dim.index" class="dim-row" :class="dimRowClass(dim.rank)">
                  <label class="dim-checkbox">
                    <input type="checkbox" :checked="isInAnyRange(dim.rank)" @click.prevent />
                  </label>
                  <span class="dim-rank">{{ dim.rank + 1 }}</span>
                  <span class="dim-index">d{{ dim.index }}</span>
                  <div class="dim-bar-container">
                    <div class="dim-bar" :style="{ width: `${(dim.value / maxDiffValue) * 100}%` }" :class="dimRowClass(dim.rank)"></div>
                  </div>
                  <span class="dim-value">{{ dim.value.toFixed(3) }}</span>
                </div>
              </div>

              <p class="ef-warn" v-if="analysisComplete && measured[selectedEncoder] && displayDims.length === 0">
                {{ t('latentLab.probing.noDifference') }}
              </p>
            </div>

            <p v-if="errorMessage" class="lab-prep-err">{{ errorMessage }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>
          </section>

          <!-- What came out, at one seed: the picture prompt A makes, the same
               picture with the chosen dimensions of B in it, and the picture
               prompt B makes. -->
          <section class="lab-plot">
            <div class="lab-grid one-row" :style="{ '--lab-grid-cols': 3 }">
              <div class="lab-grid-col">
                <div class="lab-grid-head">{{ t('latentLab.probing.originalLabel') }}</div>
                <div class="instr-frame">
                  <div class="instr-stack">
                    <MediaGridCell
                      :url="originalImage ? `data:image/png;base64,${originalImage}` : ''"
                      :run-id="originalRunId"
                      :prompt="originalPrompt"
                      :config-id="OUTPUT_CONFIG"
                      :created-at="originalMadeAt"
                      :facts="originalFacts"
                      :note="originalNote"
                      :is-favorited="isFavorited(originalRunId)"
                      :label="t('latentLab.probing.originalLabel')"
                      @toggle-favorite="toggleFavorite(originalRunId)"
                      @download="downloadOriginal"
                    />
                  </div>
                </div>
              </div>

              <div class="lab-grid-col">
                <div class="lab-grid-head">{{ t('latentLab.probing.modifiedLabel') }}</div>
                <div class="instr-frame">
                  <div class="instr-stack">
                    <MediaGridCell
                      :url="modifiedImage ? `data:image/png;base64,${modifiedImage}` : ''"
                      :run-id="modifiedRunId"
                      :prompt="modifiedPrompt"
                      :config-id="OUTPUT_CONFIG"
                      :created-at="modifiedMadeAt"
                      :facts="modifiedFacts"
                      :note="modifiedNote"
                      :is-favorited="isFavorited(modifiedRunId)"
                      :label="t('latentLab.probing.modifiedLabel')"
                      @toggle-favorite="toggleFavorite(modifiedRunId)"
                      @download="downloadModified"
                    />
                  </div>
                </div>
              </div>

              <div class="lab-grid-col">
                <div class="lab-grid-head">{{ t('latentLab.probing.originalBLabel') }}</div>
                <div class="instr-frame">
                  <div class="instr-stack">
                    <MediaGridCell
                      :url="originalBImage ? `data:image/png;base64,${originalBImage}` : ''"
                      :run-id="originalBRunId"
                      :prompt="originalBPrompt"
                      :config-id="OUTPUT_CONFIG"
                      :created-at="originalBMadeAt"
                      :facts="originalBFacts"
                      :note="originalBNote"
                      :is-favorited="isFavorited(originalBRunId)"
                      :label="t('latentLab.probing.originalBLabel')"
                      @toggle-favorite="toggleFavorite(originalBRunId)"
                      @download="downloadOriginalB"
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
import RangeTrack, { type RangeSelection } from '@/components/RangeTrack.vue'
import ShellRun from '@/components/ShellRun.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { refusalKeyOf, generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { downloadMedia } from '@/lib/downloadMedia'
import { useDeviceId } from '@/composables/useDeviceId'
import { useFavoritesStore } from '@/stores/favorites'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import { useDetailsState } from '@/composables/useDetailsState'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'
import { apiBase } from '@/services/labApi'

const { t } = useI18n()
const pageContextStore = usePageContextStore()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const deviceId = useDeviceId()
const favoritesStore = useFavoritesStore()
const { record: labRecord } = useLatentLabRecorder('feature_probing')

/**
 * The runs of this instrument, in the frame's strip. Three kinds stand there
 * side by side and that IS the comparison this instrument is for: the picture as
 * prompt A made it, the same picture with a range of dimensions taken over from
 * B, and the picture as prompt B made it. The card's bar says which, and which
 * dimensions.
 */
const { addRun } = useInstrumentRuns('feature_probing', cardFor, {
  shell: { sourceView: 'latent-lab/feature-probing' },
})

function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const image = (run.outputs || []).find(o => o.type === 'image')
  if (!image?.url) return null
  const transfer = params.action === 'transfer'
  // Prompt B's own picture carries B's words where the others carry A's.
  const ownPrompt = String((params.action === 'original_b' ? params.prompt_b : params.prompt_a) ?? '')
  const dims = Array.isArray(params.transfer_dims) ? params.transfer_dims.length : 0
  return {
    id: run.run_id,
    // The instrument's own two words, as the parameters name them - the button's
    // label is a whole sentence and says nothing at 240 px.
    label: transfer
      ? `transfer · ${dims}`
      : (params.action === 'original_b' ? 'B · ' : '') + ownPrompt.trim().split(/\s+/).slice(0, 4).join(' '),
    sub: String(params.encoder ?? ''),
    meta: [
      `seed: ${results.seed ?? params.seed ?? ''}`,
      `cfg: ${params.cfg ?? ''}`,
      `B: ${String(params.prompt_b ?? '')}`,
    ],
    prompt: ownPrompt,
    configId: OUTPUT_CONFIG,
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: run.run_id,
    output: { url: image.url, media_type: 'image' },
    error: null,
  }
}

/** A run just made, laid as a card through the same reader that reads one back. */
async function keepRun(
  parameters: Record<string, unknown>,
  results: Record<string, unknown>,
  imageBase64: string,
) {
  const runId = await labRecord({
    parameters,
    results,
    outputs: imageBase64 ? [{ type: 'image', format: 'png', dataBase64: imageBase64 }] : undefined,
  })
  if (!runId || !imageBase64) return null
  addRun(cardFor({
    run_id: runId,
    tool: 'feature_probing',
    timestamp: new Date().toISOString(),
    parameters,
    results,
    outputs: [{ type: 'image', format: 'png', url: `/api/media/image/${runId}/0`, meta: {} }],
  }))
  return runId
}

/**
 * The perspective in the corner of a field. A ready list over a written field
 * and the perspective in it are the platform's mandatory combination for an
 * instrument surface (docs/ELEMENT_STRUCTURE_REGISTRY.md, Rule #13). ONE
 * overlay serves both fields; which one opened it decides where the answer is
 * written back.
 */
type Field = 'a' | 'b'

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
  const field = which === 'a' ? promptA : promptB
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
const { isOpen: advancedOpen, onToggle: onAdvancedToggle } = useDetailsState('ll_probing_advanced')

// Constants
const OUTPUT_CONFIG = 'feature_probing'
const MAX_RANGES = 4
// The selection a session starts with: ranks 13 to 1156. With all encoders
// this range turns the house-by-the-lake standard prompt into a blue-red
// mixed house.
const DEFAULT_RANGE: RangeSelection = { from: 13, to: 1156 }

// Encoder options
type EncoderId = 'all' | 'clip_l' | 'clip_g' | 't5'
const encoders: { id: EncoderId; labelKey: string }[] = [
  { id: 'all', labelKey: 'encoderAll' },
  { id: 'clip_l', labelKey: 'encoderClipL' },
  { id: 'clip_g', labelKey: 'encoderClipG' },
  { id: 't5', labelKey: 'encoderT5' },
]

/** The same four, as the fields ChipSelect draws. */
const encoderChoices = computed(() =>
  encoders.map(e => ({ value: e.id, label: t(`latentLab.probing.${e.labelKey}`) })),
)

// State
const promptA = ref('')
const promptB = ref('')
const selectedEncoder = ref<EncoderId>('all')
const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(STANDARD_SEED)
const randomSeed = ref(false)

/**
 * What ▶ 1 goes out with except its seed, as one key: what the seed automatic
 * compares the next press with. The encoder is not in it: ▶ 1 measures on every
 * encoder at once and makes prompt A's picture whichever is chosen. ▶ 2 takes
 * no seed of its own; it runs at the seed of the measurement.
 */
function inputsKey(): string {
  return JSON.stringify([promptA.value, promptB.value, negativePrompt.value, steps.value,
    cfgScale.value])
}
const seedAutomatic = useSeedAutomatic(seed, randomSeed, 'lat_lab_fp_seed_yardstick')

const isAnalyzing = ref(false)
const isTransferring = ref(false)
const errorMessage = ref('')
const analysisComplete = ref(false)
const sortAscending = ref(false)

// Result data
const originalImage = ref('')
const modifiedImage = ref('')
// A cell IS a run: it carries that run's id, so the star keeps it and the back
// of the card shows its facts.
const originalRunId = ref<string | null>(null)
const modifiedRunId = ref<string | null>(null)
const originalMadeAt = ref(0)
const modifiedMadeAt = ref(0)
// A refusal belongs at the cell it refused, and never in the words it arrives
// in: the reasons are German developer strings (composables/useGenerationStream.ts).
const originalBlockedKey = ref('')
const modifiedBlockedKey = ref('')
// Prompt B's own picture, at the seed of the measurement. ▶ 2
// makes it first and then the mix; while what it is made from stands as it did,
// the next ▶ 2 makes only the mix. Prompt B is the obvious input; seed, steps,
// CFG and the negative prompt make the picture as well, so they count too.
const originalBImage = ref('')
const originalBRunId = ref<string | null>(null)
const originalBMadeAt = ref(0)
const originalBFacts = ref<string[]>([])
const originalBPrompt = ref('')
const originalBBlockedKey = ref('')
const originalBMadeFrom = ref('')
const originalBSeed = ref<number | null>(null)
// The recipe prompt B's picture was refused for; ▶ 2 stays dimmed while it stands.
const originalBRefusedFor = ref('')
const isMakingB = ref(false)
const actualSeed = ref<number | null>(null)
// ▶ 1 measures on every encoder at once, and the list is the one of the encoder
// the field shows: a change of encoder switches the list and runs nothing.
// Before, ▶ 2 on CLIP-G made prompt A's picture again only to measure. Its
// ranks name dimensions of THAT encoder: CLIP-L has 768, CLIP-G 1280, and a
// ranking of All names higher ones, so ▶ 2 failed on CLIP-L and CLIP-G after
// a measurement with All. A run that answers for one encoder only fills that
// one.
const measured = ref<Partial<Record<EncoderId, { index: number; value: number }[]>>>({})
const topDims = computed(() => measured.value[selectedEncoder.value] ?? [])

// Ranges (up to MAX_RANGES). They stay as they are set across a new prompt and a
// new run; the run and the line under the track
// count only the ranks the list has.
const ranges = ref<RangeSelection[]>([{ ...DEFAULT_RANGE }])

// Computed
const isGenerating = computed(() => isAnalyzing.value || isTransferring.value)
const hasAnalysis = computed(() => displayDims.value.length > 0)
/** The first triangle in the bar: two prompts written, and nothing else out. */
const canAnalyze = computed(() => !isGenerating.value && !!promptA.value.trim() && !!promptB.value.trim())
/** A list for the encoder the field shows: the selection acts on it, and ▶ 2 carries from it. */
const listMatchesEncoder = computed(() => hasAnalysis.value)
/** The second triangle in the bar: such a list, and something chosen in it. */
const canTransfer = computed(() =>
  listMatchesEncoder.value && !isGenerating.value && selectedDimCount.value > 0
  && originalBRefusedFor.value !== originalBRecipe())
/** The two triangles in the bar, in the order they are pressed. */
const runSteps = computed(() => [
  { ready: canAnalyze.value, running: isAnalyzing.value, title: t('latentLab.probing.analyzeBtn') },
  { ready: canTransfer.value, running: isTransferring.value, title: t('latentLab.probing.transferBtn') },
])
const maxDiffValue = computed(() => {
  if (topDims.value.length === 0) return 1
  return topDims.value[0]?.value ?? 1
})
const displayDims = computed(() => topDims.value.filter(d => d.value > 1e-6))
const nonzeroDimCount = computed(() => displayDims.value.length)
const sortedDisplayDims = computed(() => {
  const withRank = displayDims.value.map((d, idx) => ({ ...d, rank: idx }))
  return sortAscending.value ? [...withRank].reverse() : withRank
})

// Selected dimensions from union of all ranges
const selectedDims = computed(() => {
  const dims = new Set<number>()
  for (const range of ranges.value) {
    if (range.to < range.from) continue
    const f = Math.max(0, range.from - 1)
    const end = Math.min(displayDims.value.length, range.to)
    for (let i = f; i < end; i++) {
      dims.add(displayDims.value[i]!.index)
    }
  }
  return dims
})
const selectedDimCount = computed(() => selectedDims.value.size)

// Human-readable range description for i18n
const selectionRangesText = computed(() => {
  // The ranks the run reads: a range reaching past the list ends with it.
  const total = nonzeroDimCount.value
  const active = ranges.value
    .map(r => ({ from: r.from, to: Math.min(r.to, total) }))
    .filter(r => r.to >= r.from)
  if (active.length === 0) return '–'
  return active.map(r => `${r.from}–${r.to}`).join(', ')
})

// Range color assignment for a given rank (0-based)
// Returns the LAST matching range so later-added ranges dominate in overlaps
/**
 * What stands on the back of a cell: the seed the picture was made at, which
 * encoder was read, and - for the second picture - how many dimensions were
 * carried over. This is where the seed line under the column went.
 *
 * Written down when the picture comes back, NEVER computed from what the
 * controls say now: the back of a card is the record of the run that made it,
 * and a chip changed afterwards would rewrite the finished picture's own
 * account of itself.
 */
const originalFacts = ref<string[]>([])
const modifiedFacts = ref<string[]>([])
// The same for the prompt on the back, and for the same reason.
const originalPrompt = ref('')
const modifiedPrompt = ref('')

function encoderLabel(encoder: EncoderId = selectedEncoder.value): string {
  const key = encoders.find(e => e.id === encoder)?.labelKey
  return key ? t(`latentLab.probing.${key}`) : ''
}

/**
 * What a cell says when it holds no picture: why it was refused, that a run is
 * out, or - on the second plate - what it fills from. A cell holds a medium or
 * one of these, never both (components/MediaGridCell.vue).
 */
const originalNote = computed(() => {
  if (originalBlockedKey.value) return t(originalBlockedKey.value)
  return isAnalyzing.value ? t('latentLab.probing.analyzing') : ''
})

const modifiedNote = computed(() => {
  if (modifiedBlockedKey.value) return t(modifiedBlockedKey.value)
  // While ▶ 2 makes prompt B's picture first, the mix is not out yet.
  if (isMakingB.value) return ''
  if (isTransferring.value) return t('latentLab.probing.transferring')
  return modifiedImage.value ? '' : t('latentLab.probing.modifiedHint')
})

const originalBNote = computed(() => {
  if (originalBBlockedKey.value) return t(originalBBlockedKey.value)
  return isMakingB.value ? t('latentLab.probing.generatingB') : ''
})

function isFavorited(runId: string | null): boolean {
  return runId ? favoritesStore.isFavorited(runId) : false
}

async function toggleFavorite(runId: string | null): Promise<void> {
  if (!runId) return
  await favoritesStore.toggleFavorite(runId, 'image', deviceId, 'anonymous', 'feature-probing')
}

function rangeColorIndex(rank: number): number {
  let result = -1
  for (let rIdx = 0; rIdx < ranges.value.length; rIdx++) {
    const r = ranges.value[rIdx]!
    if (rank >= r.from - 1 && rank < r.to) result = rIdx
  }
  return result
}

function isInAnyRange(rank: number): boolean {
  return rangeColorIndex(rank) >= 0
}

function dimRowClass(rank: number): string {
  const idx = rangeColorIndex(rank)
  return idx >= 0 ? `in-range in-range-${idx}` : ''
}

function selectAll() {
  ranges.value = [{ from: 1, to: nonzeroDimCount.value }]
}

function selectNone() {
  for (const r of ranges.value) {
    r.from = 1
    r.to = 0
  }
}

function toggleSort() {
  sortAscending.value = !sortAscending.value
}

// Session persistence — restore on mount
onMounted(() => {
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  if (s('lat_lab_fp_promptA')) promptA.value = s('lat_lab_fp_promptA')!
  if (s('lat_lab_fp_promptB')) promptB.value = s('lat_lab_fp_promptB')!
  const enc = s('lat_lab_fp_encoder')
  if (enc && ['all', 'clip_l', 'clip_g', 't5'].includes(enc)) selectedEncoder.value = enc as EncoderId
  if (s('lat_lab_fp_negative')) negativePrompt.value = s('lat_lab_fp_negative')!
  if (s('lat_lab_fp_steps')) steps.value = parseFloat(s('lat_lab_fp_steps')!) || 25
  if (s('lat_lab_fp_cfg')) cfgScale.value = parseFloat(s('lat_lab_fp_cfg')!) || 4.5
  // parseInt, not `|| 123456789`: a seed of 0 is a seed.
  const keptSeed = parseInt(s('lat_lab_fp_seed') || '')
  if (Number.isInteger(keptSeed) && keptSeed >= 0) seed.value = keptSeed
  if (s('lat_lab_fp_random_seed')) randomSeed.value = s('lat_lab_fp_random_seed') === 'true'
  const rs = s('lat_lab_fp_ranges')
  if (rs) {
    try {
      const stored: unknown = JSON.parse(rs)
      if (Array.isArray(stored) && stored.length >= 1 && stored.length <= MAX_RANGES
        && stored.every(r => Number.isInteger(r?.from) && r.from >= 1 && Number.isInteger(r?.to) && r.to >= 0)) {
        ranges.value = stored.map(r => ({ from: r.from, to: r.to }))
      }
    } catch { /* a stored selection that does not parse leaves DEFAULT_RANGE */ }
  }
})

// Session persistence — save on change
watch(promptA, v => sessionStorage.setItem('lat_lab_fp_promptA', v))
watch(promptB, v => sessionStorage.setItem('lat_lab_fp_promptB', v))
watch(selectedEncoder, v => sessionStorage.setItem('lat_lab_fp_encoder', v))
watch(ranges, v => sessionStorage.setItem('lat_lab_fp_ranges', JSON.stringify(v)), { deep: true })
watch([negativePrompt, steps, cfgScale, seed, randomSeed], () => {
  sessionStorage.setItem('lat_lab_fp_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_fp_steps', String(steps.value))
  sessionStorage.setItem('lat_lab_fp_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_fp_seed', String(seed.value))
  sessionStorage.setItem('lat_lab_fp_random_seed', String(randomSeed.value))
})

function copyPromptA() { copyToClipboard(promptA.value) }
function pastePromptA() { promptA.value = pasteFromClipboard() }
function clearPromptA() { promptA.value = ''; sessionStorage.removeItem('lat_lab_fp_promptA') }
function copyPromptB() { copyToClipboard(promptB.value) }
function pastePromptB() { promptB.value = pasteFromClipboard() }
function clearPromptB() { promptB.value = ''; sessionStorage.removeItem('lat_lab_fp_promptB') }

/**
 * A PAIR, not two offers. What this instrument shows is the difference between
 * two prompts, and two lists side by side would leave it to the reader to guess
 * which entry belongs with which. One entry so far: the pair this page has
 * always shown behind its own two fields.
 */
const promptExamples = computed(() => [
  {
    id: 'houses',
    label: t('latentLab.probing.promptExamples.housesLabel'),
    fill: [
      t('latentLab.probing.promptExamples.housesA'),
      t('latentLab.probing.promptExamples.housesB'),
    ],
  },
  {
    id: 'street',
    label: t('latentLab.probing.promptExamples.streetLabel'),
    fill: [
      t('latentLab.probing.promptExamples.streetA'),
      t('latentLab.probing.promptExamples.streetB'),
    ],
  },
  {
    id: 'time',
    label: t('latentLab.probing.promptExamples.timeLabel'),
    fill: [
      t('latentLab.probing.promptExamples.timeA'),
      t('latentLab.probing.promptExamples.timeB'),
    ],
  },
])

function applyExample(item: { fill: string[] }) {
  promptA.value = item.fill[0] ?? ''
  promptB.value = item.fill[1] ?? ''
}

function downloadOriginal() {
  if (!originalImage.value) return
  void downloadMedia(`data:image/png;base64,${originalImage.value}`, `dimension_explorer_original_${actualSeed.value}.png`)
}
function downloadModified() {
  if (!modifiedImage.value) return
  void downloadMedia(`data:image/png;base64,${modifiedImage.value}`, `dimension_explorer_modified_${actualSeed.value}.png`)
}
function downloadOriginalB() {
  if (!originalBImage.value) return
  void downloadMedia(`data:image/png;base64,${originalBImage.value}`, `dimension_explorer_original_b_${originalBSeed.value}.png`)
}

/** The fields a run is made with, read once when its trigger is pressed. */
interface RunSettings {
  /** `null`: a new seed for this run. */
  seed: number | null
  negative: string
  steps: number
  cfg: number
  promptA: string
  promptB: string
  encoder: EncoderId
}

function settingsNow(at: number | null = randomSeed.value ? null : seed.value): RunSettings {
  return {
    seed: at,
    negative: negativePrompt.value,
    steps: steps.value,
    cfg: cfgScale.value,
    promptA: promptA.value,
    promptB: promptB.value,
    encoder: selectedEncoder.value,
  }
}

/** What prompt B's picture is made from, at the seed `at`. */
function originalBRecipe(at: number | null = actualSeed.value ?? seed.value, s: RunSettings = settingsNow()): string {
  return JSON.stringify([s.promptB, at, s.steps, s.cfg, s.negative])
}

function clearOriginalB(): void {
  originalBImage.value = ''
  originalBRunId.value = null
  originalBMadeAt.value = 0
  originalBFacts.value = []
  originalBPrompt.value = ''
  originalBBlockedKey.value = ''
  originalBMadeFrom.value = ''
  originalBSeed.value = null
}

/**
 * Prompt B's own picture: the measurement's run with the two prompts swapped and
 * nothing carried over, so the picture is B's embedding as it is, at the seed of
 * A's picture. Says whether the picture came back.
 */
/** What one press of ▶ 2 sends, taken at the press. */
interface TransferPress {
  seed: number
  negative: string
  steps: number
  cfg: number
  dims: number[]
  promptA: string
  promptB: string
  encoder: EncoderId
  /** What prompt B's picture is made from (`originalBRecipe`). */
  recipe: string
}

/** How prompt B's run ended: its picture, a refusal, or another failure. */
type OriginalBOutcome = 'made' | 'refused' | 'failed'

async function makeOriginalB(press: TransferPress): Promise<OriginalBOutcome> {
  clearOriginalB()
  isMakingB.value = true
  try {
    const baseUrl = apiBase()
    const response = await postDirectRun({
      prompt: press.promptB,
      output_config: OUTPUT_CONFIG,
      seed: press.seed,
      negative_prompt: press.negative,
      steps: press.steps,
      cfg: press.cfg,
      prompt_b: press.promptA,
      probing_encoder: press.encoder,
    }, { baseUrl })
    const image = response.data.status === 'success' ? response.data.probing_data?.image_base64 : ''
    if (image) {
      const bSeed: number = response.data.media_output?.seed ?? press.seed
      originalBImage.value = image
      originalBMadeFrom.value = press.recipe
      originalBSeed.value = bSeed
      originalBMadeAt.value = Date.now()
      originalBPrompt.value = press.promptB
      originalBFacts.value = [`${t('latentLab.probing.seedLabel')}: ${bSeed}`]
      originalBRunId.value = await keepRun(
        {
          action: 'original_b',
          prompt_a: press.promptA, prompt_b: press.promptB,
          negative_prompt: press.negative,
          steps: press.steps, cfg: press.cfg, seed: press.seed,
        },
        { seed: bSeed },
        image,
      )
      return 'made'
    }
    const key = refusalKeyOf(response.data)
    if (key) {
      originalBBlockedKey.value = key
      return 'refused'
    }
    errorMessage.value = t('latentLab.probing.promptBFailed', {
      m: generationErrorFor(t, response.data.error || response.data.message || ''),
    })
    return 'failed'
  } catch (err: any) {
    const key = refusalKeyOf(err)
    if (key) {
      originalBBlockedKey.value = key
      return 'refused'
    }
    errorMessage.value = t('latentLab.probing.promptBFailed', { m: generationErrorFor(t, err) })
    return 'failed'
  } finally {
    isMakingB.value = false
  }
}

async function analyze() {
  if (!promptA.value.trim() || !promptB.value.trim() || isGenerating.value) return
  // The seed automatic (composables/useSeedAutomatic): the same seed when
  // something changed since the picture on the surface was made, a new one
  // when nothing did, the field's when it was typed, a new one on every run
  // under the tick. The seed goes into the field.
  const runInputs = inputsKey()
  const runSeed = seedAutomatic.seedForRun(runInputs)
  const s = settingsNow(runSeed)

  isAnalyzing.value = true
  errorMessage.value = ''
  originalImage.value = ''
  modifiedImage.value = ''
  // The run that stood here is over. Its id, its star and its facts go with its
  // picture, or the card that stands while the new one is out carries the old
  // run - and the star would keep THAT one.
  originalRunId.value = null
  modifiedRunId.value = null
  originalMadeAt.value = 0
  modifiedMadeAt.value = 0
  originalFacts.value = []
  modifiedFacts.value = []
  originalBlockedKey.value = ''
  modifiedBlockedKey.value = ''
  measured.value = {}
  analysisComplete.value = false
  actualSeed.value = null
  const encoder = s.encoder
  // Prompt B's picture stays only while it is the one the next ▶ 2 would make.
  if (s.seed === null || originalBMadeFrom.value !== originalBRecipe(s.seed, s)) clearOriginalB()

  try {
    const baseUrl = apiBase()
    const response = await postDirectRun({
      prompt: s.promptA,
      output_config: OUTPUT_CONFIG,
      seed: runSeed,
      negative_prompt: s.negative,
      steps: s.steps,
      cfg: s.cfg,
      prompt_b: s.promptB,
      probing_encoder: encoder,
    }, { baseUrl })

    if (response.data.status === 'success') {
      const probData = response.data.probing_data
      if (probData) {
        if (probData.image_base64) {
          originalImage.value = probData.image_base64
        }

        actualSeed.value = response.data.media_output?.seed ?? runSeed
        // Prompt A's picture is now the one the next ▶ 1 is compared with.
        if (originalImage.value) seedAutomatic.arrived(runInputs, actualSeed.value)

        type Said = { top_dims?: number[]; top_values?: number[] }
        const listOf = (m: Said) =>
          (m.top_dims || []).map((dimIdx, i) => ({ index: dimIdx, value: m.top_values?.[i] ?? 0 }))
        const lists: Partial<Record<EncoderId, { index: number; value: number }[]>> = {}
        for (const [name, m] of Object.entries((probData.by_encoder ?? {}) as Record<string, Said>)) {
          if (encoders.some(e => e.id === name)) lists[name as EncoderId] = listOf(m)
        }
        lists[encoder] = listOf(probData)
        measured.value = lists

        analysisComplete.value = true
        if (originalBMadeFrom.value !== originalBRecipe(actualSeed.value ?? s.seed, s)) clearOriginalB()

        // Record analysis for research export
        originalMadeAt.value = Date.now()
        originalPrompt.value = s.promptA
        originalFacts.value = [
          `${t('latentLab.probing.seedLabel')}: ${actualSeed.value ?? runSeed}`,
          encoderLabel(encoder),
        ]
        originalRunId.value = await keepRun(
          {
            action: 'analyze',
            prompt_a: s.promptA, prompt_b: s.promptB,
            encoder, negative_prompt: s.negative,
            steps: s.steps, cfg: s.cfg, seed: runSeed,
          },
          { seed: actualSeed.value, top_dims_count: topDims.value.length },
          originalImage.value,
        )
      } else {
        errorMessage.value = t('generationError.unknown')
      }
    } else {
      const key = refusalKeyOf(response.data)
      if (key) originalBlockedKey.value = key
      else errorMessage.value = generationErrorFor(t, response.data.error || response.data.message || '')
    }
  } catch (err: any) {
    // A refusal is not a fault: it stands at the cell it refused, in the
    // reader's language, and the reasons are German developer strings.
    const key = refusalKeyOf(err)
    if (key) originalBlockedKey.value = key
    else errorMessage.value = generationErrorFor(t, err)
  } finally {
    isAnalyzing.value = false
  }
}

async function transfer() {
  if (!canTransfer.value) return
  // Taken at the press: prompt B's run and the mix stand on the same values,
  // even when a field changes while they are out.
  const at = actualSeed.value ?? seed.value
  const s = settingsNow(at)
  const press: TransferPress = {
    seed: at,
    negative: s.negative,
    steps: s.steps,
    cfg: s.cfg,
    dims: Array.from(selectedDims.value),
    promptA: s.promptA,
    promptB: s.promptB,
    encoder: s.encoder,
    recipe: originalBRecipe(at, s),
  }

  isTransferring.value = true
  errorMessage.value = ''
  modifiedImage.value = ''
  modifiedRunId.value = null
  modifiedMadeAt.value = 0
  modifiedFacts.value = []
  modifiedBlockedKey.value = ''

  // Prompt B's picture first, when none stands for what it would be made from.
  // A refusal of it stops the mix too, which carries B's dimensions, and keeps
  // ▶ 2 dimmed until prompt B or a setting changes; any other failure leaves
  // the mix to run.
  if (originalBMadeFrom.value !== press.recipe) {
    const outcome = await makeOriginalB(press)
    if (outcome === 'refused') {
      originalBRefusedFor.value = press.recipe
      modifiedBlockedKey.value = 'latentLab.probing.stoppedByB'
      isTransferring.value = false
      return
    }
  }

  try {
    const baseUrl = apiBase()
    const response = await postDirectRun({
      prompt: press.promptA,
      output_config: OUTPUT_CONFIG,
      seed: press.seed,
      negative_prompt: press.negative,
      steps: press.steps,
      cfg: press.cfg,
      prompt_b: press.promptB,
      probing_encoder: press.encoder,
      transfer_dims: press.dims,
    }, { baseUrl })

    if (response.data.status === 'success') {
      const probData = response.data.probing_data
      if (probData?.image_base64) {
        modifiedImage.value = probData.image_base64

        // Record transfer for research export
        modifiedMadeAt.value = Date.now()
        modifiedPrompt.value = press.promptA
        modifiedFacts.value = [
          `${t('latentLab.probing.seedLabel')}: ${press.seed}`,
          encoderLabel(press.encoder),
          `${t('latentLab.probing.transferAction')} · ${press.dims.length}`,
        ]
        modifiedRunId.value = await keepRun(
          {
            action: 'transfer',
            prompt_a: press.promptA, prompt_b: press.promptB,
            encoder: press.encoder, transfer_dims: press.dims,
            steps: press.steps, cfg: press.cfg, seed: press.seed,
          },
          { dims_transferred: press.dims.length },
          modifiedImage.value,
        )
      } else {
        errorMessage.value = t('generationError.unknown')
      }
    } else {
      const key = refusalKeyOf(response.data)
      if (key) modifiedBlockedKey.value = key
      else errorMessage.value = generationErrorFor(t, response.data.error || response.data.message || '')
    }
  } catch (err: any) {
    const key = refusalKeyOf(err)
    if (key) modifiedBlockedKey.value = key
    else errorMessage.value = generationErrorFor(t, err)
  } finally {
    isTransferring.value = false
  }
}

/** Which of the two triangles was pressed: 0 measures, 1 carries over. */
function runStep(step?: number) {
  if (step === 1) transfer()
  else analyze()
}

// Trashy Page Context
const trashyFocusHint = computed<FocusHint>(() => {
  if (isGenerating.value || originalImage.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  return { x: 8, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'feature_probing',
  pageContent: {
    inputText: `A: ${promptA.value}\nB: ${promptB.value}`,
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
   needs: the four-range track, the list of dimensions it is read against, and
   the rank selection, which is this instrument alone. The cells are the
   platform's own (components/MediaGridCell.vue) and bring their plate, their
   save and their back with them. */

/* --- the result columns ---------------------------------------------------- */

/* The square takes the narrower side of its field, which here is the WIDTH of a
   column — so the height it does not use is left over. It stands as ONE strip
   below the row rather than as a band above and below each picture: empty
   vertical bands around each picture gain nothing. The
   platform's picture raster caps its series for the same reason; with a single
   row there is nothing to cap, so the frame stops centring. */

/* --- the run's own settings ------------------------------------------------ */

/* The klappe of the instruments is the platform's and stands in
   assets/flow-stage.css (`details.advanced-settings` + `.settings-grid`). */

/* --- the selection, and the list it is made against ------------------------ */

/* Nothing to select from until a run has been analysed. The block stays where
   it is and says so by standing back, rather than appearing out of nowhere
   under the reader's hand. */
.fp-select {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
}
.fp-select.disabled { opacity: 0.35; pointer-events: none; }

.fp-selection {
  margin: 0 0 6px;
  font-size: var(--flow-fs-hint);
  color: rgba(124, 77, 255, 0.85);
}

/* The list scrolls in ITSELF. At four thousand dimensions a column that grew
   with it would put the trigger under it out of reach, and the column already
   scrolls as a whole for the settings above. */
.fp-dims {
  display: flex;
  flex-direction: column;
  gap: 1px;
  max-height: clamp(160px, 32vh, 420px);
  overflow-y: auto;
  padding-right: 0.35rem;
}

/* The track with its ranges is components/RangeTrack.vue —
   it stood here inline and the Fusion Workbench would have been the second
   copy. What is left below is the LIST the ranks are read against, which is
   this instrument's alone (docs/ELEMENT_STRUCTURE_REGISTRY.md). */

/* `.mini-btn` moved into assets/flow-stage.css when Decomposition became
   the second column to carry it (docs/ELEMENT_STRUCTURE_REGISTRY.md). */

/* === The dimensions, one row each === */
.dim-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  transition: background 0.1s ease;
  opacity: 0.35;
}

.dim-row.in-range { opacity: 1; }
.dim-row.in-range-0 { background: rgba(124, 77, 255, 0.06); }
.dim-row.in-range-1 { background: rgba(0, 188, 212, 0.06); }
.dim-row.in-range-2 { background: rgba(255, 152, 0, 0.06); }
.dim-row.in-range-3 { background: rgba(102, 187, 106, 0.06); }

.dim-checkbox { display: flex; align-items: center; cursor: default; }
.dim-checkbox input { accent-color: #7C4DFF; cursor: default; margin: 0; }

.dim-rank {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.65rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  min-width: 30px;
  text-align: right;
}
.dim-row.in-range-0 .dim-rank { color: rgba(124, 77, 255, 0.6); }
.dim-row.in-range-1 .dim-rank { color: rgba(0, 188, 212, 0.6); }
.dim-row.in-range-2 .dim-rank { color: rgba(255, 152, 0, 0.6); }
.dim-row.in-range-3 .dim-rank { color: rgba(102, 187, 106, 0.6); }

.dim-index {
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.65rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  min-width: 40px;
  text-align: right;
}

.dim-bar-container {
  flex: 1;
  min-width: 0;
  height: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 2px;
  overflow: hidden;
}

.dim-bar {
  height: 100%;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 2px;
  transition: background 0.15s ease;
}
.dim-bar.in-range-0 { background: rgba(124, 77, 255, 0.5); }
.dim-bar.in-range-1 { background: rgba(0, 188, 212, 0.5); }
.dim-bar.in-range-2 { background: rgba(255, 152, 0, 0.5); }
.dim-bar.in-range-3 { background: rgba(102, 187, 106, 0.5); }

.dim-value {
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.65rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  min-width: 42px;
  text-align: right;
}
.dim-row.in-range .dim-value { color: rgba(255, 255, 255, 0.6); }

/* Narrow windows: the two surfaces stand under each other and the page scrolls
   in the work area, as every instrument of this frame does. */
@media (max-width: 640px) {
  .lab-stage { flex: 0 0 auto; }
  .lab-work { grid-template-columns: 1fr; }
}
</style>
