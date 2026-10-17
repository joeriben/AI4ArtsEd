<template>
  <div class="ac">
    <!-- The switch for the result surface: it goes into the frame's bar where
         there is one, and stands on its own where there is not. Same as
         Denoising Archaeology, and `defer` for the same reason — a Teleport
         resolves its target against the live document, and on the app's first
         render the whole tree is still detached. -->
    <Teleport defer to=".shell-bar-slot" :disabled="!inShellFrame">
      <button
        class="shell-btn ac-drawer-btn"
        :title="t('canvas.outputDrawer.title')"
        @click="drawerCollapsed = !drawerCollapsed"
      >
        <img
          v-if="!drawerCollapsed"
          src="@/assets/icons/bottom_panel_close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg"
          alt=""
          class="shell-icon"
        />
        <img
          v-else
          src="@/assets/icons/bottom_panel_open_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg"
          alt=""
          class="shell-icon"
        />
      </button>
    </Teleport>

    <!-- The trigger, in the middle of the frame's bar, breathing while a run is
         out. Every denoising step is captured here, so the counter beside it
         says how much of the map already exists. -->
    <ShellRun
      :ready="canRun"
      :running="isGenerating"
      :title="t('latentLab.attention.generate')"
      :label="t('latentLab.runLine.step')"
      :count="runStep"
      :total="runTotalSteps || steps"
      :note="runSettled ? t('latentLab.runLine.transfer') : undefined"
      @run="generate"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <!-- Left: what the run is asked with, and what the finished map is
               read with. Both are the hand's business; the right surface is the
               picture and nothing else. -->
          <section class="ac-text lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <PromptExamples
              :items="promptExamples"
              :current="promptText"
              :disabled="isGenerating"
              @pick="applyExample"
            />
            <MediaInputBox
              chrome="bare"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              v-model:value="promptText"
              input-type="text"
              :rows="2"
              resize-type="auto"
              :is-loading="readingPicture"
              :disabled="isGenerating || readingPicture"
              :show-preset-button="true"
              :preset-busy="isEnriching"
              @open-preset-selector="showPresetOverlay = true"
              @copy="copyInputText"
              @paste="pasteInputText"
              @clear="clearInputText"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />
            <!-- The reading of a dropped picture, where it did not come back. -->
            <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <details class="advanced-settings" :open="advancedOpen" @toggle="onAdvancedToggle">
              <summary>{{ t('latentLab.attention.advancedLabel') }}</summary>
              <div class="settings-grid">
                <label>
                  {{ t('latentLab.attention.negativeLabel') }}
                  <input v-model="negativePrompt" type="text" class="setting-input" />
                </label>
                <label>
                  {{ t('latentLab.attention.stepsLabel') }}
                  <input v-model.number="steps" type="number" min="10" max="50" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.attention.cfgLabel') }}
                  <input v-model.number="cfgScale" type="number" min="1" max="20" step="0.5" class="setting-input setting-small" />
                </label>
                <SeedControl v-model:seed="seed" v-model:random="randomSeed" />
              </div>
            </details>

            <!-- What the finished map is read with. It stands dimmed until a run
                 has been made, so the surface shows beforehand what it offers. -->
            <div class="ac-read" :class="{ 'is-disabled': !imageData }">
              <div class="control-row" v-if="hasT5Data">
                <label class="control-label">{{ t('latentLab.attention.encoderLabel') }}</label>
                <div class="layer-toggles">
                  <button
                    class="layer-btn"
                    :class="{ active: isEncoderActive('clip') }"
                    @click="toggleEncoder('clip')"
                  >
                    {{ t('latentLab.attention.encoderClipLG') }}
                  </button>
                  <button
                    class="layer-btn"
                    :class="{ active: isEncoderActive('t5') }"
                    @click="toggleEncoder('t5')"
                  >
                    {{ t('latentLab.attention.encoderT5') }}
                  </button>
                </div>
              </div>

              <!-- One word list for both encoders, so a chip survives the
                   switch and the two readings can be held against each other. -->
              <div class="token-section">
                <div class="token-label">{{ t('latentLab.attention.tokensLabel') }}</div>
                <div class="token-chips">
                  <div
                    v-for="(entry, gIdx) in mergedWords"
                    :key="gIdx"
                    class="word-group"
                    :class="{ selected: isWordSelected(gIdx), [`color-${selectedWordColorIndex(gIdx) % 8}`]: isWordSelected(gIdx) }"
                    @click="toggleWord(gIdx)"
                  >
                    <span
                      v-if="isWordSelected(gIdx)"
                      class="color-dot"
                      :style="{ background: tokenColorCSS(selectedWordColorIndex(gIdx)) }"
                    ></span>
                    <span class="word-text">{{ entry.label }}</span>
                    <span v-if="activeSubtokenCount(entry) > 1" class="subtoken-hint">({{ activeSubtokenCount(entry) }})</span>
                  </div>
                </div>
              </div>

              <div class="control-row">
                <label class="control-label">{{ t('latentLab.attention.timestepLabel') }}</label>
                <div class="slider-container">
                  <input
                    type="range"
                    v-model.number="selectedStep"
                    :min="0"
                    :max="captureSteps.length - 1"
                    :step="1"
                    class="control-slider"
                  />
                  <span class="slider-value">{{ t('latentLab.attention.step') }} {{ captureSteps[selectedStep] ?? 0 }} / {{ totalSteps }}</span>
                </div>
              </div>

              <div class="control-row">
                <label class="control-label">{{ t('latentLab.attention.layerLabel') }}</label>
                <div class="layer-toggles">
                  <button
                    v-for="(layer, idx) in captureLayers"
                    :key="layer"
                    class="layer-btn"
                    :class="{ active: selectedLayer === idx }"
                    @click="selectedLayer = idx"
                  >
                    {{ layerLabels[idx] }}
                  </button>
                  <button
                    class="layer-btn"
                    :class="{ active: selectedLayer === 'all' }"
                    @click="selectedLayer = 'all'"
                  >
                    {{ t('latentLab.attention.layerAll') }}
                  </button>
                </div>
              </div>

              <div class="control-row">
                <label class="control-label">{{ t('latentLab.attention.opacityLabel') }}</label>
                <div class="slider-container">
                  <input
                    type="range"
                    v-model.number="heatmapOpacity"
                    min="0"
                    max="1"
                    step="0.05"
                    class="control-slider"
                  />
                  <span class="slider-value">{{ Math.round(heatmapOpacity * 100) }}%</span>
                </div>
              </div>

              <div class="control-row">
                <label class="control-label">{{ t('latentLab.attention.baseImageLabel') }}</label>
                <div class="layer-toggles">
                  <button
                    v-for="(mode, idx) in baseImageModes"
                    :key="mode"
                    class="layer-btn"
                    :class="{ active: baseImageMode === mode }"
                    @click="baseImageMode = mode"
                  >
                    {{ baseImageModeLabels[idx] }}
                  </button>
                </div>
              </div>
            </div>

            <p v-if="errorMessage" class="ac-err">{{ errorMessage }}</p>

            <aside class="lab-note">
              <h3>{{ t('latentLab.imageLab.tabs.attention.label') }}</h3>
              <!-- The two papers this instrument reads FROM. They stood under the
                   page title until the two-column rebuild took the title with it,
                   and were left in the help entry alone; the help keeps its copy,
                   this is the one that belongs to the instrument. -->
              <LabReferences
                flat
                :title="t('latentLab.attention.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <!-- Right: the picture with the map over it, as large as the surface
               allows. What this view IS gets kept as the run's own plate —
               composed while the view stands, written when the run is made and
               again when it is starred (see composeReading). Keeping a picture
               is the favourites' business; this surface hands out nothing. -->
          <section class="ac-view">
            <div class="ac-frame instr-frame">
              <div class="ac-stack instr-stack">
                <div class="ac-shot instr-square">
                  <img
                    v-if="imageData"
                    :src="`data:image/png;base64,${imageData}`"
                    class="generated-image"
                    :class="{ grayscale: baseImageMode === 'bw', hidden: baseImageMode === 'off' }"
                    ref="imageRef"
                    @load="onImageLoad"
                  />
                  <canvas
                    ref="heatmapCanvas"
                    class="heatmap-overlay"
                    :style="{ opacity: heatmapOpacity }"
                  ></canvas>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <!-- One card per run, so several stand NEXT to each other rather than one
         after the other: what the strip is for is holding two readings of this
         instrument side by side. Each card carries the map as it was read, so
         the comparison is on the card itself and needs no run to be repeated.
         The key in a card's bar is that run's name here, not a control — this
         surface cannot stand an earlier reading up again, because the maps
         behind it are gone (see runs below). -->
    <OutputDrawer
      :items="runs"
      :is-collapsed="drawerCollapsed"
      :title="t('latentLab.shared.runsTitle')"
      :empty-text="t('latentLab.shared.runsEmpty')"
      :default-height="340"
      :box-width="240"
      :box-height="260"
      source-view="latent-lab/attention-cartography"
      :before-favorite="writeReadingBeforeKeep"
      @toggle-collapse="drawerCollapsed = !drawerCollapsed"
      @remove="removeRun"
    />

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
import { ref, computed, inject, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { useRoute } from 'vue-router'
import { postDirectRun } from '@/services/directRun'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import SeedControl from '@/components/SeedControl.vue'
import { useSeedAutomatic, STANDARD_SEED } from '@/composables/useSeedAutomatic'
import ShellRun from '@/components/ShellRun.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'

import OutputDrawer, { type DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import { useDetailsState } from '@/composables/useDetailsState'
import { useDeviceId } from '@/composables/useDeviceId'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'
import { useGenerationSteps } from '@/composables/useGenerationSteps'
import { apiBase } from '@/services/labApi'

/**
 * What this instrument reads FROM. Hertz et al. set the cross-attention path
 * that makes a word's map readable at all; Tang et al. turned it into the
 * per-word attribution this surface draws. Both were checked against what runs
 * here before they were written down, and the check is why they stayed when
 * feature probing's three did not.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Hertz et al. (2022)',
    title: '"Prompt-to-Prompt Image Editing with Cross Attention Control"',
    venue: 'ICLR 2023',
    doi: 'https://doi.org/10.48550/arXiv.2208.01626',
  },
  {
    authors: 'Tang et al. (2022)',
    title: '"What the DAAM: Interpreting Stable Diffusion Using Cross Attention"',
    venue: 'ACL 2023',
    doi: 'https://doi.org/10.48550/arXiv.2210.04885',
  },
]

const { t } = useI18n()
const route = useRoute()
const pageContextStore = usePageContextStore()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord } = useLatentLabRecorder('attention_cartography')

/** The config this instrument runs. Named once; the card's back says it too. */
const OUTPUT_CONFIG = 'attention_cartography'
const { isOpen: advancedOpen, onToggle: onAdvancedToggle } = useDetailsState('ll_attention_advanced')
const deviceId = useDeviceId()
const showPresetOverlay = ref(false)
const isEnriching = ref(false)

// State
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
const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(STANDARD_SEED)
const randomSeed = ref(false)

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with.
 */
function inputsKey(): string {
  return JSON.stringify([promptText.value, negativePrompt.value, steps.value, cfgScale.value])
}
const seedAutomatic = useSeedAutomatic(seed, randomSeed, 'lat_lab_ac_seed_yardstick')

const isGenerating = ref(false)
const errorMessage = ref('')

/** Standing in the Latent Lab's frame, or on this instrument's own route. */
const inShellFrame = inject('shellFrame', false)
const canRun = computed(() => !!promptText.value.trim() && !isGenerating.value)
/**
 * The step a RUNNING pass is on, asked of the GPU service while one is out.
 * Every step is captured here, so the count is also how much of the map
 * already exists.
 */
const {
  step: runStep,
  totalSteps: runTotalSteps,
  settled: runSettled,
} = useGenerationSteps(isGenerating)

// Result data
const imageData = ref('')
const tokens = ref<string[]>([])
const wordGroups = ref<number[][]>([])  // [[0,1], [2], [3,4]] — subtoken indices per word
const tokensT5 = ref<string[]>([])
const wordGroupsT5 = ref<number[][]>([])
const clipTokenCount = ref(0)
const attentionMaps = ref<Record<string, Record<string, number[][]>>>({})
const spatialResolution = ref<[number, number]>([64, 64])
const captureLayers = ref<number[]>([3, 9, 17])
const captureSteps = ref<number[]>([])
const totalSteps = ref(25)
const actualSeed = ref(0)
/** The net's own sheet, as the run reported it — the plate names it. */
const modelMeta = ref<Record<string, any> | null>(null)

/** The runs of this sitting, as the Ablage holds them. */
/**
 * The runs of this instrument, newest first, as this strip has always laid
 * them. They come back after a reload: `cardFor` turns a recorded run into its
 * card again.
 *
 * A card of this instrument carries the READING - the map over the render, at
 * the words, the depth, the step and the strength it was read at - because that
 * is what a run of this instrument is, and what two of them can be compared by.
 * The maps themselves are gone (some 17 MB a run), so no card puts an earlier
 * reading back on the surface; each card is one reading, and it says on its
 * back which.
 */
const { runs, removeRun: dropRun } = useInstrumentRuns('attention_cartography', cardFor, { newestFirst: true })
const drawerCollapsed = ref(true)
/** Which run the surface is showing, so its plate can be set from what stands. */
const currentRunId = ref<string | null>(null)

// Encoder selection — the two column groups of SD3.5's encoder_hidden_states.
// Columns 0..76 carry CLIP-L AND CLIP-G together: diffusers concatenates the two
// on the FEATURE axis (pipeline_stable_diffusion_3.py, `cat([...], dim=-1)`), so
// they share the same 77 token slots and no separate CLIP-G column exists.
// Columns 77.. carry T5-XXL. Both groups may be active at once — their weights
// come out of one softmax, so they add up.
type EncoderKey = 'clip' | 't5'
const selectedEncoders = ref<EncoderKey[]>(['clip', 't5'])
const hasT5Data = computed(() => tokensT5.value.length > 0)

function isEncoderActive(enc: EncoderKey): boolean {
  if (enc === 't5' && !hasT5Data.value) return false
  return selectedEncoders.value.includes(enc)
}

function toggleEncoder(enc: EncoderKey) {
  const pos = selectedEncoders.value.indexOf(enc)
  if (pos >= 0) {
    if (selectedEncoders.value.length === 1) return
    selectedEncoders.value.splice(pos, 1)
  } else {
    selectedEncoders.value.push(enc)
  }
}

// ONE word list for both encoders, so switching an encoder leaves every chip
// standing and the same word can be compared across the two directly. CLIP-BPE
// and T5-SentencePiece split the same sentence differently, so words are paired
// by a normalised label; whatever has no counterpart is carried along on its own.
type WordEntry = { label: string; clip: number[]; t5: number[] }

function normalizeLabel(s: string): string {
  return s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')
}

const mergedWords = computed<WordEntry[]>(() => {
  const labelOf = (g: number[], src: string[]) => g.map(i => src[i] ?? '').join('')
  const t5Groups = wordGroupsT5.value
  const taken = new Set<number>()
  const out: WordEntry[] = []
  for (const g of wordGroups.value) {
    const label = labelOf(g, tokens.value)
    const key = normalizeLabel(label)
    let match = -1
    if (key) {
      for (let j = 0; j < t5Groups.length; j++) {
        if (taken.has(j)) continue
        const tg = t5Groups[j]
        if (tg && normalizeLabel(labelOf(tg, tokensT5.value)) === key) { match = j; break }
      }
    }
    if (match >= 0) taken.add(match)
    out.push({ label, clip: g, t5: match >= 0 ? (t5Groups[match] ?? []) : [] })
  }
  for (let j = 0; j < t5Groups.length; j++) {
    if (taken.has(j)) continue
    const tg = t5Groups[j]
    if (!tg) continue
    out.push({ label: labelOf(tg, tokensT5.value), clip: [], t5: tg })
  }
  return out
})

function activeSubtokenCount(entry: WordEntry): number {
  return (isEncoderActive('clip') ? entry.clip.length : 0)
    + (isEncoderActive('t5') ? entry.t5.length : 0)
}

// Interaction state — selectedWords stores indices into mergedWords (not token indices)
const selectedWords = ref<number[]>([])
const selectedStep = ref(0)
/**
 * The denoising step the surface opens on. Late enough that the picture has
 * settled into places a word can be read against, early enough to be short of
 * the last touches. The index is looked up once the run says which steps it
 * captured; where 17 was not captured, the nearest one below it stands in.
 */
const OPENING_STEP = 17
// One depth at a time, or all of them at once as a fourth position of the
// same switch — the three are read against each other, not stacked by hand.
type LayerSelection = number | 'all'
const selectedLayer = ref<LayerSelection>('all')
const heatmapOpacity = ref(1)
const baseImageModes = ['color', 'bw', 'off'] as const
type BaseImageMode = typeof baseImageModes[number]
const baseImageMode = ref<BaseImageMode>('off')
const baseImageModeLabels = computed(() => [
  t('latentLab.attention.baseColor'),
  t('latentLab.attention.baseBW'),
  t('latentLab.attention.baseOff'),
])

// Refs
const imageRef = ref<HTMLImageElement | null>(null)
const heatmapCanvas = ref<HTMLCanvasElement | null>(null)

const layerLabels = computed(() => [
  t('latentLab.attention.layerEarly'),
  t('latentLab.attention.layerMid'),
  t('latentLab.attention.layerLate'),
])

// Color palette for multi-token heatmaps (8 distinct colors)
const tokenColors = [
  [255, 0, 0],     // red
  [0, 150, 255],   // blue
  [0, 255, 100],   // green
  [255, 200, 0],   // yellow
  [255, 0, 255],   // magenta
  [255, 128, 0],   // orange
  [0, 255, 255],   // cyan
  [180, 0, 255],   // purple
]

// Word-level helpers — gIdx indexes into mergedWords
function isWordSelected(gIdx: number): boolean {
  return selectedWords.value.includes(gIdx)
}

function selectedWordColorIndex(gIdx: number): number {
  return selectedWords.value.indexOf(gIdx)
}

function tokenColorCSS(selIdx: number): string {
  const c = tokenColors[selIdx % tokenColors.length]
  return c ? `rgb(${c[0]}, ${c[1]}, ${c[2]})` : 'white'
}

function toggleWord(gIdx: number) {
  const pos = selectedWords.value.indexOf(gIdx)
  if (pos >= 0) {
    selectedWords.value.splice(pos, 1)
  } else {
    selectedWords.value.push(gIdx)
  }
  nextTick(() => renderHeatmap())
}


// Session persistence — restore on mount
onMounted(() => {
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  if (s('lat_lab_ac_prompt')) promptText.value = s('lat_lab_ac_prompt')!
  if (s('lat_lab_ac_negative')) negativePrompt.value = s('lat_lab_ac_negative')!
  if (s('lat_lab_ac_steps')) steps.value = parseFloat(s('lat_lab_ac_steps')!) || 25
  if (s('lat_lab_ac_cfg')) cfgScale.value = parseFloat(s('lat_lab_ac_cfg')!) || 4.5
  // parseInt, not `|| 123456789`: a seed of 0 is a seed.
  const keptSeed = parseInt(s('lat_lab_ac_seed') || '')
  if (Number.isInteger(keptSeed) && keptSeed >= 0) seed.value = keptSeed
  if (s('lat_lab_ac_random_seed')) randomSeed.value = s('lat_lab_ac_random_seed') === 'true'
  const enc = s('lat_lab_ac_encoder')
  if (enc) {
    const keys = enc.split(',').filter((k): k is EncoderKey => k === 'clip' || k === 't5')
    if (keys.length > 0) selectedEncoders.value = keys
    else if (enc === 'clip_l') selectedEncoders.value = ['clip']
  }
})

// Session persistence — save on change
watch(promptText, v => sessionStorage.setItem('lat_lab_ac_prompt', v))
watch([negativePrompt, steps, cfgScale, seed, randomSeed], () => {
  sessionStorage.setItem('lat_lab_ac_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_ac_steps', String(steps.value))
  sessionStorage.setItem('lat_lab_ac_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_ac_seed', String(seed.value))
  sessionStorage.setItem('lat_lab_ac_random_seed', String(randomSeed.value))
})
watch(selectedEncoders, v => sessionStorage.setItem('lat_lab_ac_encoder', v.join(',')), { deep: true })

function copyInputText() { copyToClipboard(promptText.value) }
function pasteInputText() { promptText.value = pasteFromClipboard() }
function clearInputText() { promptText.value = ''; sessionStorage.removeItem('lat_lab_ac_prompt') }

/**
 * What this instrument can be asked, ready to pick. One entry so far: the prompt
 * this page has always shown behind its own field as the example.
 */
const promptExamples = usePromptPresets()

function applyExample(item: { fill: string[] }) {
  promptText.value = item.fill[0] ?? ''
}

/** What the two rows of switches stand at, as the drawer card words it. */
function legendSettings(): string {
  const encoders = ([['clip', t('latentLab.attention.encoderClipLG')],
                     ['t5', t('latentLab.attention.encoderT5')]] as const)
    .filter(([k]) => isEncoderActive(k))
    .map(([, label]) => label)
    .join(' + ')
  const depth = selectedLayer.value === 'all'
    ? t('latentLab.attention.layerAll')
    : (layerLabels.value[selectedLayer.value] ?? '')
  const step = `${t('latentLab.attention.step')} ${captureSteps.value[selectedStep.value] ?? 0}/${totalSteps.value}`
  return [encoders, depth, step, `Seed ${actualSeed.value}`].filter(Boolean).join('  ·  ')
}


/**
 * What the plate SAYS — the reading it is, in the run's own record.
 *
 * A heat map with no statement of which words at which depth and step it shows
 * is uninterpretable, and once the maps are gone the plate is all that is left
 * of the run. The sheet the download button used to typeset carried these same
 * facts; with the button gone they belong in the record instead, where the card
 * and the favourite can read them back.
 */
function readingRecord(): Record<string, unknown> {
  return {
    words: selectedWords.value
      .map(index => mergedWords.value[index]?.label ?? '')
      .filter(Boolean),
    encoders: selectedEncoders.value.slice(),
    depth: selectedLayer.value === 'all'
      ? 'all'
      : (captureLayers.value[selectedLayer.value] ?? null),
    step: captureSteps.value[selectedStep.value] ?? null,
    total_steps: totalSteps.value,
    opacity: heatmapOpacity.value,
    base_image: baseImageMode.value,
    legend: legendSettings(),
  }
}

/**
 * The picture this run is SHOWN by: the map as it stands on the surface.
 *
 * A run of this instrument is a READING — which words, read through which
 * encoders, at which depth, at which step, how strongly, over which ground.
 * The bare render carries none of that, and the bare render was what went into
 * the strip and into the favourites. This composes what the eye has: the
 * surface's own ground, the render in the mode the surface is set to, the map
 * over it at its strength.
 *
 * Returns the picture base64-encoded, without the data-URL head, which is what
 * the recorder takes. Null while there is nothing to compose.
 */
function composeReading(): string | null {
  const img = imageRef.value
  const overlay = heatmapCanvas.value
  if (!img || !imageData.value || !img.naturalWidth) return null
  // With the render hidden AND no word chosen the surface shows a bare ground,
  // and a plate of it would be a rectangle nothing downstream could tell from a
  // picture. Every other combination is a reading and is composed: the render
  // alone is what a surface with nothing selected shows, and that is as true of
  // it as a map is.
  const overlayStands = selectedWords.value.length > 0
  if (baseImageMode.value === 'off' && !overlayStands) return null

  const out = document.createElement('canvas')
  out.width = img.naturalWidth
  out.height = img.naturalHeight
  const ctx = out.getContext('2d')
  if (!ctx) return null

  // The ground is read off the surface rather than named here: how dark the
  // platform stands is a setting (assets/base.css, stores/userPreferences), and
  // a colour written in would be one tone only. Walking up because the square
  // may be transparent and the tone come from the frame around it.
  let ground = ''
  for (let el = img.parentElement, depth = 0; el && depth < 4; el = el.parentElement, depth++) {
    const bg = getComputedStyle(el).backgroundColor
    if (bg && bg !== 'transparent' && !bg.startsWith('rgba(0, 0, 0, 0)')) {
      ground = bg
      break
    }
  }
  ctx.fillStyle = ground || '#000000'
  ctx.fillRect(0, 0, out.width, out.height)

  if (baseImageMode.value !== 'off') {
    if (baseImageMode.value === 'bw') {
      // Pixel by pixel, NOT through the canvas filter. `'filter' in ctx` says
      // the property is there, never that it takes effect — where it does not,
      // the screen shows grey (CSS does that separately) and the file comes out
      // in colour, with nothing to notice it by. This is the research record;
      // it may not depend on a property that answers a different question.
      const flat = document.createElement('canvas')
      flat.width = out.width
      flat.height = out.height
      const fctx = flat.getContext('2d')
      if (fctx) {
        fctx.drawImage(img, 0, 0, flat.width, flat.height)
        const pixels = fctx.getImageData(0, 0, flat.width, flat.height)
        const d = pixels.data
        for (let i = 0; i < d.length; i += 4) {
          const grey = 0.2126 * (d[i] ?? 0) + 0.7152 * (d[i + 1] ?? 0) + 0.0722 * (d[i + 2] ?? 0)
          d[i] = grey
          d[i + 1] = grey
          d[i + 2] = grey
        }
        fctx.putImageData(pixels, 0, 0)
        ctx.drawImage(flat, 0, 0)
      } else {
        ctx.drawImage(img, 0, 0, out.width, out.height)
      }
    } else {
      ctx.drawImage(img, 0, 0, out.width, out.height)
    }
  }

  if (overlay && overlay.width > 0 && overlay.height > 0) {
    ctx.globalAlpha = heatmapOpacity.value
    ctx.drawImage(overlay, 0, 0, out.width, out.height)
    ctx.globalAlpha = 1
  }

  return out.toDataURL('image/png').split(',')[1] ?? null
}

/**
 * Before a run of this instrument is kept: its plate is set from the reading
 * that stands.
 *
 * The strip's star keeps a RUN, and what a favourite then shows is the run's
 * first picture. For this instrument that picture has to be the map as it was
 * read — the run was written with the opening reading on it, and by the time
 * the star is pressed the eye may be on other words entirely, so the kept
 * picture is the overlay exactly as it was seen.
 *
 * Only for the run the surface is actually showing; an older card has no
 * reading standing anywhere and keeps the plate it was written with. Throwing
 * here leaves the run unkept, which is the honest outcome: a favourite pointing
 * at the wrong picture would be worse than none.
 */
async function writeReadingBeforeKeep(item: DrawerItem): Promise<void> {
  if (!item.runId || item.runId !== currentRunId.value) return
  const reading = composeReading()
  // Nothing stands on the surface — the render hidden and no word chosen. There
  // is no reading to keep, so the run is not kept under one.
  if (!reading) throw new Error(`Nothing stands on the surface of ${item.runId} to keep`)

  const baseUrl = apiBase()
  const res = await fetch(`${baseUrl}/api/latent-lab/run/${item.runId}/output/0`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataBase64: reading, device_id: deviceId, reading: readingRecord() }),
  })
  // Every refusal leaves the run unkept. 409 says this run carries no plate at
  // all — its picture failed to come together when it was written — and keeping
  // it would put the bare render behind a card whose back names a reading. The
  // status travels with the message, because the causes are different things:
  // 403 another device's run, 413 too large, 500 the write itself.
  if (!res.ok) {
    let reason = ''
    try { reason = (await res.json())?.reason || '' } catch { /* no body */ }
    throw new Error(`The plate of ${item.runId} was not set (${res.status}${reason ? ` ${reason}` : ''})`)
  }

  // A miniature is answered as immutable, so the card asks for the new picture
  // by name; without this the strip would go on showing the old reading for a
  // year (media_routes.get_image_thumbnail).
  const { version } = await res.json()
  const card = runs.value.find(entry => entry.id === item.runId)
  if (card && version) {
    card.output = { url: `/api/media/image/${item.runId}/0?v=${version}`, media_type: 'image' }
    // And what the card SAYS follows what it shows: the line on its back names
    // the encoders, the depth and the step, and those are what just changed.
    card.meta = [`${t('latentLab.attention.seedLabel')}: ${actualSeed.value}`, legendSettings()]
  }
}

async function generate() {
  if (!promptText.value.trim() || isGenerating.value) return

  isGenerating.value = true
  errorMessage.value = ''
  imageData.value = ''
  tokens.value = []
  wordGroups.value = []
  tokensT5.value = []
  wordGroupsT5.value = []
  clipTokenCount.value = 0
  attentionMaps.value = {}
  selectedWords.value = []
  selectedEncoders.value = ['clip', 't5']

  // The seed automatic (composables/useSeedAutomatic): the same seed when
  // something changed since the picture on the surface was made, a new one
  // when nothing did, the field's when it was typed, a new one on every run
  // under the tick. The seed goes into the field.
  const runInputs = inputsKey()
  const runSeed = seedAutomatic.seedForRun(runInputs)

  try {
    const response = await postDirectRun({
      prompt: promptText.value,
      output_config: OUTPUT_CONFIG,
      seed: runSeed,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
    })

    if (response.data.status === 'success') {
      // Attention data (including image_base64) is included directly in the response
      const attData = response.data.attention_data
      if (attData) {
        // Use image_base64 directly — no separate media fetch needed
        if (attData.image_base64) {
          imageData.value = attData.image_base64
        }
        tokens.value = attData.tokens || []
        wordGroups.value = attData.word_groups || []
        tokensT5.value = attData.tokens_t5 || []
        wordGroupsT5.value = attData.word_groups_t5 || []
        clipTokenCount.value = attData.clip_token_count || 0
        attentionMaps.value = attData.attention_maps || {}
        spatialResolution.value = attData.spatial_resolution || [64, 64]
        captureLayers.value = attData.capture_layers || [3, 9, 17]
        captureSteps.value = attData.capture_steps || []
        selectedStep.value = openingStepIndex(captureSteps.value)
        totalSteps.value = steps.value
        actualSeed.value = attData.seed ?? response.data.media_output?.seed ?? runSeed
        // This picture is now the one the next press is compared with.
        if (imageData.value) seedAutomatic.arrived(runInputs, actualSeed.value)
        modelMeta.value = response.data.model_meta ?? null

        // Diagnostic logging
        const mapKeys = Object.keys(attData.attention_maps || {})
        const firstStep = mapKeys[0]
        const firstLayerKeys = firstStep ? Object.keys(attData.attention_maps[firstStep]) : []
        const sampleMap = firstStep && firstLayerKeys[0] ? attData.attention_maps[firstStep][firstLayerKeys[0]] : null
        console.log('[AC] Attention data received:', {
          tokens: attData.tokens,
          captureSteps: attData.capture_steps,
          captureLayers: attData.capture_layers,
          mapStepKeys: mapKeys,
          mapLayerKeys: firstLayerKeys,
          sampleMapRows: sampleMap?.length,
          sampleMapCols: sampleMap?.[0]?.length,
          spatialRes: attData.spatial_resolution,
          imageBase64Length: attData.image_base64?.length,
        })

        // The surface opens on the two words that steer it most differently,
        // read off this very run — see openingWords().
        selectedWords.value = openingWords()

        // The plate is the READING, so the map has to stand before it is made:
        // the picture decoded, the overlay drawn once. Without this the strip
        // and the favourites would carry the bare render again, which says
        // nothing about what was read.
        await nextTick()
        try {
          await imageRef.value?.decode()
        } catch {
          /* a picture replaced while it decoded; the render below stands in */
        }
        renderHeatmap()
        const reading = composeReading()

        // Recorded for research. The attention maps themselves are too large to
        // keep (some 17 MB a run); what is kept is the reading as a picture and
        // the render behind it.
        const labRunId = (reading || imageData.value) ? await labRecord({
          parameters: {
            prompt: promptText.value, negative_prompt: negativePrompt.value,
            steps: steps.value, cfg: cfgScale.value, seed: runSeed,
            output_config: OUTPUT_CONFIG,
          },
          results: {
            seed: actualSeed.value,
            token_count_clip: tokens.value.length,
            token_count_t5: tokensT5.value.length,
            capture_steps: captureSteps.value,
            capture_layers: captureLayers.value,
          },
          outputs: [
            // The reading FIRST: it is what the strip, the favourites and the
            // big view show. The render follows it and stays in the run whole —
            // nothing the model made is traded away for the plate.
            // `plate: 'reading'` is the mark the server checks before it lets
            // this picture be set again. Without it nothing here is replaceable
            // — which is exactly right for the render on the line below.
            ...(reading
              ? [{
                  type: 'image' as const,
                  format: 'png',
                  dataBase64: reading,
                  meta: { plate: 'reading', reading: readingRecord() },
                }]
              : []),
            ...(imageData.value ? [{ type: 'image' as const, format: 'png', dataBase64: imageData.value }] : []),
          ],
        }) : ''

        // The card carries the served file, as every other card on the platform
        // does — favouriting, forwarding and the big view all pass a URL on.
        const runId = labRunId || response.data.run_id || `ac_${actualSeed.value}`
        currentRunId.value = runId
        const mediaUrl = labRunId
          ? `/api/media/image/${labRunId}/0`
          : (response.data.media_output?.url || '')
        runs.value.unshift({
          id: runId,
          label: promptText.value.trim().split(/\s+/).slice(0, 4).join(' '),
          sub: `${t('latentLab.attention.stepsLabel')} ${steps.value} · ${t('latentLab.attention.cfgLabel')} ${cfgScale.value}`,
          meta: [
            `${t('latentLab.attention.seedLabel')}: ${actualSeed.value}`,
            legendSettings(),
          ],
          prompt: promptText.value,
          configId: OUTPUT_CONFIG,
          createdAt: Date.now(),
          modelMeta: response.data.model_meta ?? null,
          runId,
          output: { url: mediaUrl, media_type: 'image' },
          error: null,
        })
      } else {
        errorMessage.value = t('generationError.unknown')
      }
    } else {
      errorMessage.value = generationErrorFor(t, response.data.error || response.data.message || '')
    }
  } catch (err: any) {
    errorMessage.value = generationErrorFor(t, err)
  } finally {
    isGenerating.value = false
  }
}

function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const image = (run.outputs || []).find(o => o.type === 'image')
  if (!image?.url) return null
  const prompt = String(params.prompt ?? '')
  // The line the card carries on its back. A plate was written together with
  // the reading it shows, so a card that came back after a reload says the same
  // as the one that was laid when the run was made.
  const plate = (image.meta || {}) as Record<string, unknown>
  const kept = (plate.reading || {}) as Record<string, unknown>
  const facts = [`${t('latentLab.attention.seedLabel')}: ${results.seed ?? params.seed ?? ''}`]
  if (typeof kept.legend === 'string' && kept.legend) facts.push(kept.legend)
  return {
    id: run.run_id,
    label: prompt.trim().split(/\s+/).slice(0, 4).join(' '),
    sub: `${t('latentLab.attention.stepsLabel')} ${params.steps ?? ''} · ${t('latentLab.attention.cfgLabel')} ${params.cfg ?? ''}`,
    meta: facts,
    prompt,
    // The config the run went through, as the record names it. A record made
    // before the recorder wrote the config carries none, and the card's back
    // then names none.
    configId: typeof params.output_config === 'string' ? params.output_config : '',
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: run.run_id,
    output: { url: image.url, media_type: 'image' },
    error: null,
  }
}

function removeRun(index: number) {
  const gone = runs.value[index]
  // Through the strip's own memory, so the card stays gone after a reload.
  dropRun(index)
  if (!gone) return
  if (currentRunId.value === gone.id) currentRunId.value = null
}

/**
 * A perspective rewrites the prompt, in the platform's one way: the interception
 * pipeline answers, and its answer replaces the text in the field. Written out
 * the same as Denoising Archaeology (views/latent_lab/denoising_archaeology.vue)
 * and Encoder Fusion — the three are the same field with the same four actions.
 */
// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!promptText.value.trim()) return

  isEnriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, promptText.value, deviceId)
    if ('written' in outcome) {
      promptText.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    isEnriching.value = false
  }
}

/** The index of OPENING_STEP among the captured steps, or the nearest below. */
function openingStepIndex(steps: number[]): number {
  if (steps.length === 0) return 0
  let best = 0
  for (let i = 0; i < steps.length; i++) {
    const v = steps[i]
    if (v === undefined) continue
    if (v <= OPENING_STEP) best = i
    else break
  }
  return best
}

function onImageLoad() {
  renderHeatmap()
}

// Watch for changes that should trigger heatmap re-render
// deep: true needed because selectedWords is mutated in-place (splice/push)
watch([selectedWords, selectedStep, selectedLayer, heatmapOpacity, selectedEncoders], () => {
  nextTick(() => renderHeatmap())
}, { deep: true })

/** The layer maps behind the view as it stands — one per active depth. */
function activeLayerMaps(): number[][][] | null {
  const stepKey = `step_${captureSteps.value[selectedStep.value] ?? 0}`
  const stepData = attentionMaps.value[stepKey]
  if (!stepData) return null
  // On 'all' every depth contributes and the maps are summed. Each layer's map
  // is its own softmax, and what is drawn is normalised to its own maximum, so
  // summing and averaging come out the same on screen.
  const layerIdxs = selectedLayer.value === 'all'
    ? captureLayers.value.map((_, i) => i)
    : [selectedLayer.value]
  const maps = layerIdxs
    .map(i => stepData[`layer_${captureLayers.value[i] ?? 9}`])
    .filter((m): m is number[][] => Array.isArray(m))
  return maps.length > 0 ? maps : null
}

/** The columns one word owns in the active encoders. T5 sits behind CLIP. */
function activeColumns(entry: WordEntry): number[] {
  const columns: number[] = []
  if (isEncoderActive('clip')) columns.push(...entry.clip)
  if (isEncoderActive('t5')) columns.push(...entry.t5.map(i => i + clipTokenCount.value))
  return columns
}

/** One word's attention over the patch grid, its columns and depths summed. */
function wordAttention(entry: WordEntry, layerMaps: number[][][], numPixels: number): Float64Array {
  const out = new Float64Array(numPixels)
  const columns = activeColumns(entry)
  if (columns.length === 0) return out
  for (const layerData of layerMaps) {
    for (let i = 0; i < numPixels; i++) {
      const row = layerData[i]
      if (!row) continue
      let sum = 0
      for (const colIdx of columns) {
        const v = row[colIdx]
        if (v !== undefined) sum += v
      }
      out[i] = (out[i] ?? 0) + sum
    }
  }
  return out
}

/**
 * The two words the surface opens on, chosen from the run itself rather than
 * from the sentence's word order.
 *
 * Every word's map is normalised to a distribution over the patch grid and held
 * against the MEAN word of this run (Kullback-Leibler). The comparison against
 * the mean is what makes it work: it takes off the ground pattern every word
 * shares, and what is left is what THIS word does differently. Measured on „Ein
 * Haus steht in einer Landschaft, umgeben von landwirtschaftlichen Flaechen,
 * Natur und Tieren." (seed 123456789, step 17, all depths, both encoders) the
 * two criteria that suggest themselves both fail: raw attention mass ranks by
 * how many subtokens a word broke into and puts „landwirtschaftlichen" (ten of
 * them) first, and spatial concentration lets „ein" and „in" through in second
 * and third place. The divergence against the mean gives haus, natur, flaechen.
 *
 * The second pick is discounted by its overlap with the first, so the surface
 * opens on two places rather than twice on one. Punctuation carries no word and
 * stands out of the field.
 *
 * Deterministic: prompt, seed, step, depths and encoders fix the answer.
 */
function openingWords(): number[] {
  const words = mergedWords.value
  const layerMaps = activeLayerMaps()
  const [spatialH, spatialW] = spatialResolution.value
  const numPixels = spatialH * spatialW
  if (words.length === 0 || !layerMaps || numPixels === 0) return []

  const cands: { idx: number; p: Float64Array; kl: number }[] = []
  for (let i = 0; i < words.length; i++) {
    const entry = words[i]
    if (!entry || !normalizeLabel(entry.label)) continue
    const m = wordAttention(entry, layerMaps, numPixels)
    let total = 0
    for (let k = 0; k < numPixels; k++) total += m[k] ?? 0
    if (total <= 0) continue
    const p = new Float64Array(numPixels)
    for (let k = 0; k < numPixels; k++) p[k] = (m[k] ?? 0) / total
    cands.push({ idx: i, p, kl: 0 })
  }
  const first = cands[0]
  if (!first) return []
  if (cands.length === 1) return [first.idx]

  const mean = new Float64Array(numPixels)
  for (const c of cands) {
    for (let k = 0; k < numPixels; k++) mean[k] = (mean[k] ?? 0) + (c.p[k] ?? 0) / cands.length
  }
  for (const c of cands) {
    let kl = 0
    for (let k = 0; k < numPixels; k++) {
      const v = c.p[k] ?? 0
      const b = mean[k] ?? 0
      if (v > 0 && b > 0) kl += v * Math.log(v / b)
    }
    c.kl = kl
  }
  cands.sort((a, b) => b.kl - a.kl)

  const lead = cands[0]
  if (!lead) return []
  let second: { idx: number; p: Float64Array; kl: number } | null = null
  let bestScore = -Infinity
  for (let j = 1; j < cands.length; j++) {
    const c = cands[j]
    if (!c) continue
    let dot = 0, na = 0, nb = 0
    for (let k = 0; k < numPixels; k++) {
      const x = c.p[k] ?? 0
      const y = lead.p[k] ?? 0
      dot += x * y
      na += x * x
      nb += y * y
    }
    const cos = na > 0 && nb > 0 ? dot / Math.sqrt(na * nb) : 0
    const score = c.kl * (1 - cos)
    if (score > bestScore) {
      bestScore = score
      second = c
    }
  }
  return second ? [lead.idx, second.idx] : [lead.idx]
}

function renderHeatmap() {
  const canvas = heatmapCanvas.value
  const img = imageRef.value
  if (!canvas || !img || !imageData.value) return
  if (selectedWords.value.length === 0) {
    const ctx = canvas.getContext('2d')
    if (ctx) {
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
    return
  }

  const [spatialH, spatialW] = spatialResolution.value
  const layerMaps = activeLayerMaps()
  if (!layerMaps) return

  canvas.width = img.naturalWidth
  canvas.height = img.naturalHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // For each selected word, sum attention across its subtokens, the active
  // encoders and the active network depths. T5 columns sit behind the CLIP ones.
  for (let wIdx = 0; wIdx < selectedWords.value.length; wIdx++) {
    const wordIdx = selectedWords.value[wIdx]
    if (wordIdx === undefined) continue
    const entry = mergedWords.value[wordIdx]
    if (!entry) continue
    if (activeColumns(entry).length === 0) continue
    const colorArr = tokenColors[wIdx % tokenColors.length]
    if (!colorArr) continue
    const color: [number, number, number] = [colorArr[0] ?? 0, colorArr[1] ?? 0, colorArr[2] ?? 0]

    const numPixels = spatialH * spatialW
    const attnValues = wordAttention(entry, layerMaps, numPixels)

    // Normalize to [0, 1]
    let maxVal = 1e-8
    for (let i = 0; i < numPixels; i++) {
      const v = attnValues[i] ?? 0
      if (v > maxVal) maxVal = v
    }

    // Render to temporary canvas at patch resolution, then upscale
    const tmpCanvas = document.createElement('canvas')
    tmpCanvas.width = spatialW
    tmpCanvas.height = spatialH
    const tmpCtx = tmpCanvas.getContext('2d')
    if (!tmpCtx) continue

    const imgDataTmp = tmpCtx.createImageData(spatialW, spatialH)
    for (let i = 0; i < numPixels; i++) {
      const intensity = (attnValues[i] ?? 0) / maxVal
      const pixIdx = i * 4
      imgDataTmp.data[pixIdx] = color[0]
      imgDataTmp.data[pixIdx + 1] = color[1]
      imgDataTmp.data[pixIdx + 2] = color[2]
      imgDataTmp.data[pixIdx + 3] = Math.floor(intensity * 200)
    }
    tmpCtx.putImageData(imgDataTmp, 0, 0)

    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'
    ctx.globalCompositeOperation = wIdx === 0 ? 'source-over' : 'lighter'
    ctx.drawImage(tmpCanvas, 0, 0, canvas.width, canvas.height)
  }
}

// ============================================================================
// Träshy Page Context
// ============================================================================
const trashyFocusHint = computed<FocusHint>(() => {
  if (isGenerating.value || imageData.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  return { x: 8, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'attention_cartography',
  pageContent: {
    inputText: promptText.value
  },
  focusHint: trashyFocusHint.value
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
/* --------------------------------------------------------------------------
   The frame is the Latent Lab's own — `.lab-main` / `.lab-stage` / `.lab-work`
   / `.lab-col` / `.lab-note` come from assets/flow-stage.css, where the column
   proportion (1fr : 2.0467fr) and its meaning are set once: what prepares and
   reads a run on the left, what came out of it on the right. What stands here
   is only what this instrument adds on top.

   What used to be here and is gone, with Denoising Archaeology's reasons:
    - The page's own title. The frame's bar carries the name.
    - The two research references under the page title. They stand in the
      box at the foot of the left column since 2026-08-25.
    - The generate button, the progress block and the empty state. The bar says
      all three: the triangle runs it, the counter beside it breathes while it
      runs, and the surface dims what cannot be read yet.
    - The seed line. Every run is a card in the result surface, with its seed on
      the back.
    - The download. Keeping a picture is the favourites' business, on every
      surface of the platform. What the run IS gets composed all the same —
      the chosen words at the chosen depth and step, over the picture, at the
      opacity on screen — and becomes the run's own plate, because the
      attention maps are too large to keep and cannot be drawn again.
   -------------------------------------------------------------------------- */
.ac {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* Through its own route this instrument is the whole page and has to keep the
     favourites strip's room free itself; in the Latent Lab's frame the page
     already does (assets/shell.css). */
  padding-bottom: calc(var(--footer-collapsed-height, 36px) + 1px);
  box-sizing: border-box;
  background: var(--bg-base);
  color: #e2e8f0;
}

.shell-page .ac {
  padding-bottom: 0;
}

/* On the route where there is no bar to teleport into, the two stand on their
   own above the stage. Inside the frame this never applies. */
.ac > .ac-drawer-btn { align-self: flex-start; margin: 8px 0 2px 4px; }
.ac > :deep(.fl-run) { align-self: flex-start; margin: 8px 0 2px 4px; }

.ac-text {
  gap: 12px;
  /* When the result surface is pulled far open, the settings drawer, the
     reading controls and the error line stay reachable instead of being clipped
     by the page's own `overflow: hidden`. */
  overflow-y: auto;
}

.ac-err {
  flex: 0 0 auto;
  margin: 0;
  font-size: var(--flow-fs-sub);
  line-height: 1.45;
  color: #f87171;
}

.ac-view {
  gap: 10px;
  overflow-y: auto;
}

/* Under 200 px the map is no longer readable; then the column may scroll
   instead of shrinking the picture further. */
.ac-frame {
  min-height: 200px;
}

.ac-shot {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-1);
}

.generated-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: filter 0.3s ease;
}

.generated-image.grayscale {
  filter: grayscale(1);
}

.generated-image.hidden {
  opacity: 0;
}

.heatmap-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* Settings. The klappe is the platform's, fold and all
   (`details.advanced-settings` + `.settings-grid`, assets/flow-stage.css). It
   went by `.ac-settings` before and carried the shared summary rule a
   second time, character for character — a copy that survived only because the
   `<details>` had another class name, which is the parallel structure
   docs/ELEMENT_STRUCTURE_REGISTRY.md forbids. What is
   left here is the field, which keeps the metrics it was drawn at — and the
   step the shared block puts above every klappe, which this one never had: as
   `.ac-settings` it took no `margin-top` at all, and taking the shared name
   moved the fold from y 326.19 to 330.19 and this column's scroll height from
   781 px to 785 (measured 2026-09-05, 1210 x 834). Denoising Archaeology and the
   Surrealizer say the same thing for the same reason. */
.advanced-settings {
  margin-top: 0;
}

.setting-input {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  color: white;
  font-size: 0.85rem;
  /* The field stands at the width of its content here, where the shared block
     lets it fill the row. Said out loud so the two do not mix. */
  width: auto;
}

.setting-small {
  width: 80px;
}

/* What the finished map is read with. */
.ac-read {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  transition: opacity 0.2s ease;
}

.ac-read.is-disabled {
  opacity: 0.35;
  pointer-events: none;
}

/* Token Chips */
.token-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.token-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.color-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
  flex-shrink: 0;
}

.word-group {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: 'Fira Code', 'Consolas', monospace;
}

.word-group:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.word-group.selected {
  border-color: currentColor;
  font-weight: 700;
}

.word-text {
  white-space: nowrap;
}

.subtoken-hint {
  font-size: 0.6rem;
  opacity: 0.5;
  margin-left: 3px;
}

.word-group.color-0.selected { color: #ff4444; background: rgba(255, 68, 68, 0.15); }
.word-group.color-1.selected { color: #44aaff; background: rgba(68, 170, 255, 0.15); }
.word-group.color-2.selected { color: #44ff88; background: rgba(68, 255, 136, 0.15); }
.word-group.color-3.selected { color: #ffcc00; background: rgba(255, 204, 0, 0.15); }
.word-group.color-4.selected { color: #ff44ff; background: rgba(255, 68, 255, 0.15); }
.word-group.color-5.selected { color: #ff8800; background: rgba(255, 136, 0, 0.15); }
.word-group.color-6.selected { color: #00ffff; background: rgba(0, 255, 255, 0.15); }
.word-group.color-7.selected { color: #b844ff; background: rgba(184, 68, 255, 0.15); }

/* Controls. The column is narrower than the page this instrument used to be,
   so a row that no longer fits beside its label wraps under it. */
.control-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.control-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
  min-width: 80px;
  flex-shrink: 0;
  padding-top: 0.35rem;
}

.slider-container {
  flex: 1;
  min-width: 180px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.control-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}

.control-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: #667eea;
  border-radius: 50%;
  cursor: pointer;
}

.slider-value {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.75rem;
  min-width: 70px;
  text-align: right;
  font-family: 'Fira Code', 'Consolas', monospace;
}

.layer-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.layer-btn {
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.layer-btn.active {
  background: rgba(102, 126, 234, 0.2);
  border-color: rgba(102, 126, 234, 0.5);
  color: #667eea;
}

@media (max-width: 900px) {
  :deep(.lab-work) { grid-template-columns: 1fr; row-gap: 16px; }
}
</style>
