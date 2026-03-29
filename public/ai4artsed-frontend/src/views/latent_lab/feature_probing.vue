<template>
  <div class="feature-probing">
    <!-- Header (always visible) -->
    <div class="page-header">
      <h2 class="page-title">
        {{ t('latentLab.probing.headerTitle') }}
      </h2>
      <p class="page-subtitle">{{ t('latentLab.probing.headerSubtitle') }}</p>
      <details class="explanation-details" :open="explainOpen" @toggle="onExplainToggle">
        <summary>{{ t('latentLab.probing.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.probing.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.probing.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.probing.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.probing.explainHowText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.probing.explainReadTitle') }}</h4>
            <p>{{ t('latentLab.probing.explainReadText') }}</p>
          </div>
          <div class="explanation-section explanation-tech">
            <h4>{{ t('latentLab.probing.techTitle') }}</h4>
            <p>{{ t('latentLab.probing.techText') }}</p>
          </div>
          <div class="explanation-section explanation-references">
            <h4>{{ t('latentLab.probing.referencesTitle') }}</h4>
            <ul class="reference-list">
              <li>
                <span class="ref-authors">Belinkov (2022)</span>
                <span class="ref-title">"Probing Classifiers: Promises, Shortcomings, and Advances"</span>
                <span class="ref-venue">Computational Linguistics</span>
                <a href="https://doi.org/10.1162/coli_a_00422" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
              <li>
                <span class="ref-authors">Zou et al. (2023)</span>
                <span class="ref-title">"Representation Engineering: A Top-Down Approach to AI Transparency"</span>
                <span class="ref-venue">arXiv</span>
                <a href="https://doi.org/10.48550/arXiv.2310.01405" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
              <li>
                <span class="ref-authors">Bau et al. (2020)</span>
                <span class="ref-title">"Understanding the Role of Individual Units in a Deep Neural Network"</span>
                <span class="ref-venue">ECCV 2020</span>
                <a href="https://doi.org/10.1007/978-3-030-58452-8_21" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
            </ul>
          </div>
        </div>
      </details>
    </div>

    <!-- Input Section -->
    <div class="input-section">
      <div class="input-pair">
        <MediaInputBox
          icon="💡"
          :label="t('latentLab.probing.promptALabel')"
          :placeholder="t('latentLab.probing.promptAPlaceholder')"
          v-model:value="promptA"
          input-type="text"
          :rows="2"
          resize-type="auto"
          :is-filled="!!promptA"
          :disabled="isGenerating"
          @copy="copyPromptA"
          @paste="pastePromptA"
          @clear="clearPromptA"
          @focus="focusedField = 'promptA'"
          @blur="() => {}"
        />
        <MediaInputBox
          icon="💡"
          :label="t('latentLab.probing.promptBLabel')"
          :placeholder="t('latentLab.probing.promptBPlaceholder')"
          v-model:value="promptB"
          input-type="text"
          :rows="2"
          resize-type="auto"
          :is-filled="!!promptB"
          :disabled="isGenerating"
          @copy="copyPromptB"
          @paste="pastePromptB"
          @clear="clearPromptB"
          @focus="focusedField = 'promptB'"
          @blur="() => {}"
        />
      </div>

      <!-- Encoder Toggle + Analyze Button -->
      <div class="action-row">
        <div class="control-group">
          <label class="control-label">{{ t('latentLab.probing.encoderLabel') }}</label>
          <div class="layer-toggles">
            <button
              v-for="enc in encoders"
              :key="enc.id"
              class="layer-btn"
              :class="{ active: selectedEncoder === enc.id }"
              @click="selectedEncoder = enc.id"
              :disabled="isGenerating"
            >
              {{ t(`latentLab.probing.${enc.labelKey}`) }}
            </button>
          </div>
          <div class="control-hint">{{ t('latentLab.probing.encoderHint') }}</div>
        </div>
        <button
          class="generate-btn"
          :disabled="isGenerating || !promptA.trim() || !promptB.trim()"
          @click="analyze"
        >
          <span v-if="isAnalyzing" class="spinner"></span>
          <span v-else>{{ t('latentLab.probing.analyzeBtn') }}</span>
        </button>
      </div>

      <!-- Advanced Settings (collapsible) -->
      <details class="advanced-settings" :open="advancedOpen" @toggle="onAdvancedToggle">
        <summary>{{ t('latentLab.probing.advancedLabel') }}</summary>
        <div class="settings-grid">
          <label>
            {{ t('latentLab.probing.negativeLabel') }}
            <input v-model="negativePrompt" type="text" class="setting-input" />
            <div class="control-hint">{{ t('latentLab.shared.negativeHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.probing.stepsLabel') }}
            <input v-model.number="steps" type="number" min="10" max="50" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.shared.stepsHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.probing.cfgLabel') }}
            <input v-model.number="cfgScale" type="number" min="1" max="20" step="0.5" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.shared.cfgHint') }}</div>
          </label>
          <SeedControl v-model:seed="seed" v-model:random="randomSeed" />
        </div>
      </details>
    </div>

    <!-- Side-by-Side Image Comparison (always visible) -->
    <div class="comparison-section" :class="{ disabled: !hasAnalysis && !isGenerating }">
      <div class="image-pair">
        <div class="image-panel">
          <div class="panel-label">{{ t('latentLab.probing.originalLabel') }}</div>
          <div class="image-frame" :class="{ empty: !originalImage }">
            <img v-if="originalImage" :src="`data:image/png;base64,${originalImage}`" class="result-image" />
            <div v-else-if="isAnalyzing" class="image-placeholder">
              <div class="progress-spinner"></div>
              <p>{{ t('latentLab.probing.analyzing') }}</p>
            </div>
          </div>
          <button v-if="originalImage" class="download-btn" @click="downloadOriginal">
            {{ t('latentLab.probing.downloadOriginal') }}
          </button>
        </div>
        <div class="image-panel">
          <div class="panel-label">{{ t('latentLab.probing.modifiedLabel') }}</div>
          <div class="image-frame" :class="{ empty: !modifiedImage }">
            <img v-if="modifiedImage" :src="`data:image/png;base64,${modifiedImage}`" class="result-image" />
            <div v-else-if="isTransferring" class="image-placeholder">
              <div class="progress-spinner"></div>
              <p>{{ t('latentLab.probing.transferring') }}</p>
            </div>
            <div v-else class="image-placeholder-hint">
              <p>{{ t('latentLab.probing.modifiedHint') }}</p>
            </div>
          </div>
          <button v-if="modifiedImage" class="download-btn" @click="downloadModified">
            {{ t('latentLab.probing.downloadModified') }}
          </button>
        </div>
      </div>

      <button
        class="generate-btn transfer-btn"
        :disabled="!hasAnalysis || isTransferring || selectedDimCount === 0"
        @click="transfer"
      >
        <span v-if="isTransferring" class="spinner"></span>
        <span v-else>{{ t('latentLab.probing.transferBtn') }} ({{ selectedDimCount }})</span>
      </button>
      <div class="control-hint">{{ t('latentLab.probing.transferHint') }}</div>

      <div v-if="actualSeed !== null" class="seed-display">
        Seed: {{ actualSeed }}
      </div>
    </div>

    <!-- Dimension Analysis Section (always visible, disabled before analysis) -->
    <div class="analysis-section" :class="{ disabled: !hasAnalysis }">
      <!-- Slider label -->
      <div class="slider-label">{{ t('latentLab.probing.sliderLabel') }}</div>
      <div class="control-hint">{{ t('latentLab.probing.sliderHint') }}</div>

      <!-- Unified slider: visual fills + all handles in one track -->
      <div class="unified-slider">
        <div class="slider-track">
          <div v-for="(range, rIdx) in ranges" :key="`fill-${rIdx}`"
            class="slider-fill" :class="`range-color-${rIdx}`"
            :style="fillStyle(range)">
          </div>
        </div>
        <template v-for="(range, rIdx) in ranges" :key="`handles-${rIdx}`">
          <input type="range" class="slider-handle" :class="`handle-color-${rIdx}`"
            :style="{ zIndex: rIdx * 2 + 1 }" min="1" :max="nonzeroDimCount || 1" step="1"
            v-model.number="range.from" :disabled="!hasAnalysis" @input="clampRange(rIdx)" />
          <input type="range" class="slider-handle" :class="`handle-color-${rIdx}`"
            :style="{ zIndex: rIdx * 2 + 2 }" min="1" :max="nonzeroDimCount || 1" step="1"
            v-model.number="range.to" :disabled="!hasAnalysis" @input="clampRange(rIdx)" />
        </template>
      </div>

      <!-- Ranges row: all number fields in one horizontal line -->
      <div class="ranges-row">
        <div v-for="(range, rIdx) in ranges" :key="`rg-${rIdx}`" class="range-group" :class="`range-color-${rIdx}`">
          <span class="range-tag">{{ rIdx + 1 }}</span>
          <input type="number" v-model.number="range.from" :min="1" :max="range.to || 1" class="range-input"
            :disabled="!hasAnalysis" @change="clampRange(rIdx)" @focus="($event.target as HTMLInputElement).select()" />
          <span class="range-sep">&ndash;</span>
          <input type="number" v-model.number="range.to" :min="range.from" :max="nonzeroDimCount || 0" class="range-input"
            :disabled="!hasAnalysis" @change="clampRange(rIdx)" @focus="($event.target as HTMLInputElement).select()" />
          <button v-if="ranges.length > 1" class="remove-btn" @click="removeRange(rIdx)" :disabled="!hasAnalysis">&times;</button>
        </div>
        <button v-if="ranges.length < MAX_RANGES" class="mini-btn add-btn" :disabled="!hasAnalysis" @click="addRange">+</button>
        <div class="selection-actions">
          <button class="mini-btn" @click="selectAll" :disabled="!hasAnalysis">{{ t('latentLab.probing.selectAll') }}</button>
          <button class="mini-btn" @click="selectNone" :disabled="!hasAnalysis">{{ t('latentLab.probing.selectNone') }}</button>
        </div>
      </div>

      <!-- Prominent list header — directly above the dimension list -->
      <div class="analysis-list-header">
        <h3 class="list-title">
          {{ t('latentLab.probing.listTitle', { count: nonzeroDimCount }) }}
        </h3>
        <p class="list-subtitle">
          {{ t('latentLab.probing.selectionDesc', { count: selectedDimCount, ranges: selectionRangesText, total: nonzeroDimCount }) }}
        </p>
      </div>

      <!-- Sort toggle -->
      <div class="dim-list-controls" v-if="displayDims.length > 0">
        <button class="mini-btn sort-btn" @click="toggleSort">
          {{ sortAscending ? t('latentLab.probing.sortAsc') : t('latentLab.probing.sortDesc') }}
        </button>
      </div>

      <!-- Dimension Bars -->
      <div class="dimension-bars" v-if="displayDims.length > 0">
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

      <div class="no-diff-message" v-if="analysisComplete && displayDims.length === 0">
        <p>{{ t('latentLab.probing.noDifference') }}</p>
      </div>
    </div>

    <!-- Error Display -->
    <div class="error-display" v-if="errorMessage">
      <p>{{ errorMessage }}</p>
      <button @click="errorMessage = ''" class="dismiss-btn">&times;</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import MediaInputBox from '@/components/MediaInputBox.vue'
import SeedControl from '@/components/SeedControl.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useDetailsState } from '@/composables/useDetailsState'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

const { t } = useI18n()
const pageContextStore = usePageContextStore()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord } = useLatentLabRecorder('feature_probing')
const { isOpen: explainOpen, onToggle: onExplainToggle } = useDetailsState('ll_probing_explain')
const { isOpen: advancedOpen, onToggle: onAdvancedToggle } = useDetailsState('ll_probing_advanced')

// Constants
const MAX_RANGES = 4

// Encoder options
type EncoderId = 'all' | 'clip_l' | 'clip_g' | 't5'
const encoders: { id: EncoderId; labelKey: string }[] = [
  { id: 'all', labelKey: 'encoderAll' },
  { id: 'clip_l', labelKey: 'encoderClipL' },
  { id: 'clip_g', labelKey: 'encoderClipG' },
  { id: 't5', labelKey: 'encoderT5' },
]

// Range type
interface RangeSelection {
  from: number
  to: number
}

// State
const promptA = ref('')
const promptB = ref('')
const selectedEncoder = ref<EncoderId>('all')
const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(123456789)
const randomSeed = ref(false)
const isAnalyzing = ref(false)
const isTransferring = ref(false)
const errorMessage = ref('')
const analysisComplete = ref(false)
const sortAscending = ref(false)
const focusedField = ref<string>('')

// Result data
const originalImage = ref('')
const modifiedImage = ref('')
const actualSeed = ref<number | null>(null)
const topDims = ref<{ index: number; value: number }[]>([])

// Ranges (up to MAX_RANGES)
const ranges = ref<RangeSelection[]>([{ from: 1, to: 0 }])

// Computed
const isGenerating = computed(() => isAnalyzing.value || isTransferring.value)
const hasAnalysis = computed(() => displayDims.value.length > 0)
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
  const active = ranges.value.filter(r => r.to >= r.from)
  if (active.length === 0) return '\u2013'
  return active.map(r => `${r.from}\u2013${r.to}`).join(', ')
})

// Range color assignment for a given rank (0-based)
// Returns the LAST matching range so later-added ranges dominate in overlaps
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

function fillStyle(range: RangeSelection): Record<string, string> {
  if (nonzeroDimCount.value <= 0 || range.to < range.from) return { left: '0%', width: '0%' }
  const left = (range.from - 1) / nonzeroDimCount.value * 100
  const width = (range.to - range.from + 1) / nonzeroDimCount.value * 100
  return { left: `${left}%`, width: `${width}%` }
}

function clampRange(rIdx: number) {
  const r = ranges.value[rIdx]!
  if (r.from < 1) r.from = 1
  if (r.to > nonzeroDimCount.value) r.to = nonzeroDimCount.value
  if (r.from > r.to && r.to > 0) r.from = r.to
}

function addRange() {
  if (ranges.value.length < MAX_RANGES) {
    ranges.value.push({ from: 1, to: 0 })
  }
}

function removeRange(rIdx: number) {
  if (ranges.value.length > 1) {
    ranges.value.splice(rIdx, 1)
  }
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
  if (s('lat_lab_fp_seed')) seed.value = parseFloat(s('lat_lab_fp_seed')!) || 123456789
  if (s('lat_lab_fp_random_seed')) randomSeed.value = s('lat_lab_fp_random_seed') === 'true'
})

// Session persistence — save on change
watch(promptA, v => sessionStorage.setItem('lat_lab_fp_promptA', v))
watch(promptB, v => sessionStorage.setItem('lat_lab_fp_promptB', v))
watch(selectedEncoder, v => sessionStorage.setItem('lat_lab_fp_encoder', v))
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

function downloadOriginal() {
  if (!originalImage.value) return
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${originalImage.value}`
  link.download = `feature_probing_original_${actualSeed.value}.png`
  link.click()
}
function downloadModified() {
  if (!modifiedImage.value) return
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${modifiedImage.value}`
  link.download = `feature_probing_modified_${actualSeed.value}.png`
  link.click()
}

async function analyze() {
  if (!promptA.value.trim() || !promptB.value.trim() || isGenerating.value) return

  isAnalyzing.value = true
  errorMessage.value = ''
  originalImage.value = ''
  modifiedImage.value = ''
  topDims.value = []
  analysisComplete.value = false
  actualSeed.value = null
  ranges.value = [{ from: 1, to: 0 }]

  try {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const response = await axios.post(`${baseUrl}/api/schema/pipeline/legacy`, {
      prompt: promptA.value,
      output_config: 'feature_probing_diffusers',
      seed: randomSeed.value ? -1 : seed.value,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
      prompt_b: promptB.value,
      probing_encoder: selectedEncoder.value,
    })

    if (response.data.status === 'success') {
      const probData = response.data.probing_data
      if (probData) {
        if (probData.image_base64) {
          originalImage.value = probData.image_base64
        }

        actualSeed.value = response.data.media_output?.seed ?? null

        const dims = probData.top_dims || []
        const vals = probData.top_values || []
        topDims.value = dims.map((dimIdx: number, i: number) => ({
          index: dimIdx,
          value: vals[i] ?? 0,
        }))

        // Default: select all nonzero dimensions
        const nonzero = topDims.value.filter((d: { value: number }) => d.value > 1e-6).length
        ranges.value = [{ from: 1, to: nonzero }]

        analysisComplete.value = true

        // Record analysis for research export
        labRecord({
          parameters: {
            action: 'analyze',
            prompt_a: promptA.value, prompt_b: promptB.value,
            encoder: selectedEncoder.value, negative_prompt: negativePrompt.value,
            steps: steps.value, cfg: cfgScale.value, seed: seed.value,
          },
          results: { seed: actualSeed.value, top_dims_count: topDims.value.length },
          outputs: originalImage.value
            ? [{ type: 'image', format: 'png', dataBase64: originalImage.value }]
            : undefined,
        })
      } else {
        errorMessage.value = 'No probing data in response'
      }
    } else {
      errorMessage.value = response.data.error || response.data.message || 'Analysis failed'
    }
  } catch (err: any) {
    errorMessage.value = err.response?.data?.error || err.message || 'Network error'
  } finally {
    isAnalyzing.value = false
  }
}

async function transfer() {
  if (selectedDimCount.value === 0 || isGenerating.value) return

  isTransferring.value = true
  errorMessage.value = ''
  modifiedImage.value = ''

  try {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const response = await axios.post(`${baseUrl}/api/schema/pipeline/legacy`, {
      prompt: promptA.value,
      output_config: 'feature_probing_diffusers',
      seed: actualSeed.value ?? seed.value,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
      prompt_b: promptB.value,
      probing_encoder: selectedEncoder.value,
      transfer_dims: Array.from(selectedDims.value),
    })

    if (response.data.status === 'success') {
      const probData = response.data.probing_data
      if (probData?.image_base64) {
        modifiedImage.value = probData.image_base64

        // Record transfer for research export
        labRecord({
          parameters: {
            action: 'transfer',
            prompt_a: promptA.value, prompt_b: promptB.value,
            encoder: selectedEncoder.value, transfer_dims: Array.from(selectedDims.value),
            steps: steps.value, cfg: cfgScale.value, seed: actualSeed.value ?? seed.value,
          },
          results: { dims_transferred: selectedDims.value.size },
          outputs: [{ type: 'image', format: 'png', dataBase64: modifiedImage.value }],
        })
      } else {
        errorMessage.value = 'No image in transfer response'
      }
    } else {
      errorMessage.value = response.data.error || response.data.message || 'Transfer failed'
    }
  } catch (err: any) {
    errorMessage.value = err.response?.data?.error || err.message || 'Network error'
  } finally {
    isTransferring.value = false
  }
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
</script>

<style scoped>
.feature-probing {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1.5rem 1.5rem 3rem;
}

/* === Page Header === */
.page-header { margin-bottom: 1.5rem; }
.page-title { color: #667eea; font-size: 1.2rem; font-weight: 700; margin: 0 0 0.5rem; }
.page-subtitle { color: rgba(255, 255, 255, 0.7); font-size: 0.95rem; line-height: 1.6; margin: 0 0 0.75rem; }

.explanation-details {
  background: rgba(102, 126, 234, 0.06);
  border: 1px solid rgba(102, 126, 234, 0.15);
  border-radius: 10px;
  overflow: hidden;
}
.explanation-details summary {
  padding: 0.65rem 1rem;
  color: rgba(102, 126, 234, 0.8);
  font-size: 0.85rem;
  cursor: pointer;
  user-select: none;
}
.explanation-details summary:hover { color: #667eea; }
.explanation-body { padding: 0 1rem 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
.explanation-section h4 { color: rgba(255, 255, 255, 0.85); font-size: 0.85rem; margin: 0 0 0.25rem; }
.explanation-section p { color: rgba(255, 255, 255, 0.6); font-size: 0.82rem; line-height: 1.6; margin: 0; }
.explanation-tech { background: rgba(0, 0, 0, 0.2); border-radius: 8px; padding: 0.75rem; }
.explanation-tech p { font-size: 0.78rem; }

.reference-list { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.reference-list li { margin-bottom: 0.4rem; font-size: 0.8rem; color: rgba(255,255,255,0.6); }
.ref-authors { font-weight: 500; color: rgba(255,255,255,0.8); }
.ref-title { font-style: italic; }
.ref-venue { color: rgba(255,255,255,0.5); }
.ref-doi { color: rgba(102,126,234,0.8); text-decoration: none; margin-left: 0.3rem; }
.ref-doi:hover { text-decoration: underline; }

/* === Input Section === */
.input-section { display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1.5rem; }

.input-pair {
  display: flex;
  gap: clamp(1rem, 3vw, 2rem);
  width: 100%;
  justify-content: center;
  flex-wrap: wrap;
}


.action-row { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.control-group { display: flex; align-items: center; gap: 0.75rem; flex: 1; }
.control-label { color: rgba(255, 255, 255, 0.5); font-size: 0.8rem; flex-shrink: 0; }
.layer-toggles { display: flex; gap: 0.35rem; }

.layer-btn {
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s ease;
}
.layer-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.layer-btn.active { background: rgba(102, 126, 234, 0.2); border-color: rgba(102, 126, 234, 0.5); color: #667eea; }

.generate-btn {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 10px;
  color: white;
  font-weight: 700;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  min-height: 42px;
}
.generate-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3); }
.generate-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.transfer-btn {
  margin-top: 1rem;
  width: 100%;
  background: linear-gradient(135deg, #7C4DFF, #651FFF);
}
.transfer-btn:hover:not(:disabled) { box-shadow: 0 4px 12px rgba(124, 77, 255, 0.3); }

.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Advanced Settings */
.advanced-settings { margin-top: 0.25rem; }
.advanced-settings summary { color: rgba(255, 255, 255, 0.5); font-size: 0.8rem; cursor: pointer; padding: 0.25rem 0; }
.settings-grid { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem; }
.settings-grid label { display: flex; flex-direction: column; gap: 0.25rem; color: rgba(255, 255, 255, 0.5); font-size: 0.75rem; }
.setting-input {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  color: white;
  font-size: 0.85rem;
}
.setting-small { width: 80px; }
.setting-seed { width: 14ch; }

/* === Disabled state === */
.comparison-section.disabled,
.analysis-section.disabled { opacity: 0.35; pointer-events: none; }

/* === Comparison Section === */
.comparison-section { margin-bottom: 1.5rem; }
.image-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.image-panel { display: flex; flex-direction: column; gap: 0.35rem; }
.panel-label { color: rgba(255, 255, 255, 0.5); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }

.image-frame {
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  aspect-ratio: 1 / 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.image-frame.empty { border-style: dashed; border-color: rgba(255, 255, 255, 0.15); }
.result-image { width: 100%; height: 100%; object-fit: cover; display: block; }

.image-placeholder { text-align: center; color: rgba(102, 126, 234, 0.7); padding: 2rem; }
.image-placeholder p { font-size: 0.85rem; margin-top: 0.75rem; }
.image-placeholder-hint { text-align: center; padding: 2rem 1.5rem; }
.image-placeholder-hint p { color: rgba(255, 255, 255, 0.3); font-size: 0.8rem; line-height: 1.5; margin: 0; }

.progress-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(102, 126, 234, 0.2);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}

.seed-display {
  margin-top: 0.5rem;
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.7rem;
  font-family: 'Fira Code', 'Consolas', monospace;
}

/* === Analysis Section === */
.analysis-section { margin-top: 1rem; }

.analysis-list-header {
  background: rgba(124, 77, 255, 0.08);
  border: 1px solid rgba(124, 77, 255, 0.2);
  border-radius: 10px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}
.list-title { color: rgba(255, 255, 255, 0.9); font-size: 1rem; font-weight: 700; margin: 0 0 0.25rem; }
.list-subtitle { color: rgba(124, 77, 255, 0.85); font-size: 0.85rem; margin: 0; }

.slider-label { color: rgba(255, 255, 255, 0.5); font-size: 0.8rem; margin-bottom: 0.25rem; }

/* === Unified Slider (all handles in one track) === */
.unified-slider {
  position: relative;
  height: 40px;
  margin: 0.5rem 0;
}

.slider-track {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  left: 0;
  right: 0;
  height: 20px;
  background: rgba(30, 30, 30, 0.8);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  overflow: hidden;
}

.slider-fill {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 8px;
  transition: left 0.1s ease, width 0.1s ease;
}

.slider-fill.range-color-0 {
  background: linear-gradient(135deg, rgba(124, 77, 255, 0.5), rgba(101, 31, 255, 0.5));
  box-shadow: 0 0 6px rgba(124, 77, 255, 0.3);
}
.slider-fill.range-color-1 {
  background: linear-gradient(135deg, rgba(0, 188, 212, 0.5), rgba(0, 151, 167, 0.5));
  box-shadow: 0 0 6px rgba(0, 188, 212, 0.3);
}
.slider-fill.range-color-2 {
  background: linear-gradient(135deg, rgba(255, 152, 0, 0.5), rgba(245, 124, 0, 0.5));
  box-shadow: 0 0 6px rgba(255, 152, 0, 0.3);
}
.slider-fill.range-color-3 {
  background: linear-gradient(135deg, rgba(102, 187, 106, 0.5), rgba(67, 160, 71, 0.5));
  box-shadow: 0 0 6px rgba(102, 187, 106, 0.3);
}

/* Handle inputs — overlaid on the track */
.slider-handle {
  position: absolute;
  width: 100%;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  margin: 0;
  padding: 0;
  height: 20px;
}

.slider-handle::-webkit-slider-runnable-track {
  height: 20px;
  background: transparent;
  border-radius: 10px;
}
.slider-handle::-moz-range-track {
  height: 20px;
  background: transparent;
  border-radius: 10px;
}

/* Common thumb base */
.slider-handle::-webkit-slider-thumb {
  pointer-events: all;
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid white;
  cursor: grab;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
  transition: transform 0.15s ease;
}
.slider-handle::-webkit-slider-thumb:hover { transform: scale(1.2); }
.slider-handle::-webkit-slider-thumb:active { cursor: grabbing; }

.slider-handle::-moz-range-thumb {
  pointer-events: all;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid white;
  cursor: grab;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
}

/* Per-range handle colors */
.handle-color-0::-webkit-slider-thumb { background: linear-gradient(135deg, #7C4DFF, #651FFF); }
.handle-color-0::-moz-range-thumb { background: linear-gradient(135deg, #7C4DFF, #651FFF); }
.handle-color-1::-webkit-slider-thumb { background: linear-gradient(135deg, #00BCD4, #0097A7); }
.handle-color-1::-moz-range-thumb { background: linear-gradient(135deg, #00BCD4, #0097A7); }
.handle-color-2::-webkit-slider-thumb { background: linear-gradient(135deg, #FF9800, #F57C00); }
.handle-color-2::-moz-range-thumb { background: linear-gradient(135deg, #FF9800, #F57C00); }
.handle-color-3::-webkit-slider-thumb { background: linear-gradient(135deg, #66BB6A, #43A047); }
.handle-color-3::-moz-range-thumb { background: linear-gradient(135deg, #66BB6A, #43A047); }

/* === Ranges Row (number fields in one line) === */
.ranges-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.range-group {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.range-group + .range-group {
  margin-left: 0.15rem;
  padding-left: 0.5rem;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
}

.range-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 0.65rem;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.range-color-0 .range-tag { background: #7C4DFF; }
.range-color-1 .range-tag { background: #00BCD4; }
.range-color-2 .range-tag { background: #FF9800; }
.range-color-3 .range-tag { background: #66BB6A; }

.range-input {
  width: 65px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  padding: 0.3rem 0.4rem;
  color: white;
  font-size: 0.8rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  text-align: center;
}

.range-sep {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.9rem;
}

.remove-btn {
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
.remove-btn:hover { color: #ef5350; border-color: rgba(244, 67, 54, 0.3); }

.add-btn {
  width: 24px;
  height: 24px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: 700;
}

.selection-actions {
  display: flex;
  gap: 0.35rem;
  margin-left: auto;
}

.mini-btn {
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s ease;
}
.mini-btn:hover { background: rgba(255, 255, 255, 0.1); color: white; }
.mini-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Sort controls */
.dim-list-controls { display: flex; align-items: center; margin-bottom: 0.35rem; }
.sort-btn { font-size: 0.7rem; }

/* === Dimension Bars === */
.dimension-bars {
  display: flex;
  flex-direction: column;
  gap: 1px;
  max-height: 600px;
  overflow-y: auto;
  padding-right: 0.5rem;
}

.dim-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.15rem 0.4rem;
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
.dim-checkbox input { accent-color: #7C4DFF; cursor: default; }

.dim-rank {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.65rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  min-width: 35px;
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
  min-width: 45px;
  text-align: right;
}

.dim-bar-container {
  flex: 1;
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
  min-width: 50px;
  text-align: right;
}
.dim-row.in-range .dim-value { color: rgba(255, 255, 255, 0.6); }

/* === States === */
.no-diff-message { text-align: center; padding: 2rem; color: rgba(255, 193, 7, 0.7); font-size: 0.9rem; }

.error-display {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(244, 67, 54, 0.1);
  border: 1px solid rgba(244, 67, 54, 0.3);
  border-radius: 8px;
  color: #ef5350;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.dismiss-btn { background: none; border: none; color: rgba(244, 67, 54, 0.6); font-size: 1.2rem; cursor: pointer; }

.download-btn {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  width: 100%;
}
.download-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

/* === Responsive === */
@media (max-width: 768px) {
  .input-pair { flex-direction: column; }
}
@media (max-width: 640px) {
  .image-pair { grid-template-columns: 1fr; }
  .action-row { flex-direction: column; align-items: stretch; }
  .control-group { flex-direction: column; align-items: flex-start; }
}

.control-hint {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.7rem;
  line-height: 1.4;
}


</style>

<style>
.feature-probing .input-pair .media-input-box {
  flex: 1 1 0 !important;
  width: 100% !important;
  max-width: 480px !important;
}
</style>
