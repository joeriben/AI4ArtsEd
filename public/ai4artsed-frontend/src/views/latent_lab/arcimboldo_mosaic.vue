<template>
  <div class="arcimboldo-mosaic">
    <!-- Header -->
    <div class="page-header">
      <h2 class="page-title">{{ t('latentLab.arcimboldo.headerTitle') }}</h2>
      <p class="page-subtitle">{{ t('latentLab.arcimboldo.headerSubtitle') }}</p>
      <details class="explanation-details" :open="explainOpen" @toggle="onExplainToggle">
        <summary>{{ t('latentLab.arcimboldo.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.arcimboldo.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.arcimboldo.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.arcimboldo.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.arcimboldo.explainHowText') }}</p>
          </div>
          <div class="explanation-section explanation-tech">
            <h4>{{ t('latentLab.arcimboldo.techTitle') }}</h4>
            <p>{{ t('latentLab.arcimboldo.techText') }}</p>
          </div>
        </div>
      </details>
    </div>

    <!-- Step 1: Input -->
    <div class="step-section">
      <h3 class="step-title">{{ t('latentLab.arcimboldo.step1Title') }}</h3>
      <textarea
        class="prompt-input"
        :placeholder="t('latentLab.arcimboldo.promptPlaceholder')"
        v-model="prompt"
        :disabled="phase !== 'input'"
        rows="2"
      />
      <div class="input-controls">
        <div class="grid-selector">
          <label class="control-label">{{ t('latentLab.arcimboldo.gridSizeLabel') }}</label>
          <select v-model.number="gridSize" :disabled="phase !== 'input'" class="grid-select">
            <option :value="8">8 × 8 (64 tiles)</option>
            <option :value="12">12 × 12 (144 tiles)</option>
            <option :value="16">16 × 16 (256 tiles)</option>
            <option :value="20">20 × 20 (400 tiles)</option>
            <option :value="30">30 × 30 (900 tiles)</option>
            <option :value="40">40 × 40 (1600 tiles)</option>
            <option :value="50">50 × 50 (2500 tiles)</option>
          </select>
        </div>
        <details class="settings-details">
          <summary>{{ t('latentLab.arcimboldo.settingsToggle') }}</summary>
          <div class="settings-body">
            <div class="settings-grid">
              <div class="setting-item">
                <label>{{ t('latentLab.arcimboldo.stepsLabel') }}</label>
                <input type="number" v-model.number="steps" min="1" max="50" :disabled="phase !== 'input'" class="setting-number" />
              </div>
              <div class="setting-item">
                <label>{{ t('latentLab.arcimboldo.cfgLabel') }}</label>
                <input type="number" v-model.number="cfgScale" min="1" max="20" step="0.5" :disabled="phase !== 'input'" class="setting-number" />
              </div>
              <div class="setting-item">
                <label>{{ t('latentLab.arcimboldo.seedLabel') }}</label>
                <input type="number" v-model.number="seed" min="-1" :disabled="phase !== 'input'" class="setting-number" />
              </div>
            </div>
          </div>
        </details>
      </div>
      <button class="action-btn" :disabled="!prompt.trim() || phase !== 'input'" @click="startGeneration">
        {{ t('latentLab.arcimboldo.generateBtn') }}
      </button>
    </div>

    <!-- Step 2: Segmentation Result -->
    <div v-if="phaseIndex >= 1" class="step-section">
      <h3 class="step-title">{{ t('latentLab.arcimboldo.step2Title') }}</h3>

      <div v-if="phase === 'generating'" class="status-box">
        <span class="spinner" /> {{ t('latentLab.arcimboldo.generatingStatus') }}
      </div>
      <div v-else-if="phase === 'segmenting'" class="status-box">
        <span class="spinner" /> {{ t('latentLab.arcimboldo.segmentingStatus') }}
      </div>

      <div v-if="mainImage && regions.length" class="segmentation-result">
        <div class="image-container">
          <img :src="`data:image/png;base64,${mainImage}`" class="main-image" alt="Generated image" />
        </div>
        <div class="region-chips">
          <span v-for="region in regions" :key="region.idx" class="region-chip"
                :style="{ borderColor: regionColor(region.idx) }">
            <span class="color-dot" :style="{ background: `rgb(${region.avg_color_rgb.join(',')})` }" />
            {{ region.label }} ({{ region.pixel_count }} px)
          </span>
        </div>
        <button class="action-btn" :disabled="phase !== 'reviewing'" @click="startTileGeneration">
          {{ t('latentLab.arcimboldo.generateTilesBtn') }}
        </button>
      </div>
    </div>

    <!-- Step 3: Tile Generation -->
    <div v-if="phaseIndex >= 2 && phase !== 'reviewing'" class="step-section">
      <h3 class="step-title">{{ t('latentLab.arcimboldo.step3Title') }}</h3>
      <div v-if="phase === 'tiles'" class="status-box">
        <span class="spinner" /> {{ t('latentLab.arcimboldo.tilesStatus', { done: tilesDone, total: tilesTotal }) }}
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${tilesTotal ? (tilesDone / tilesTotal * 100) : 0}%` }" />
        </div>
      </div>
    </div>

    <!-- Step 4: Result -->
    <div v-if="phase === 'result'" class="step-section">
      <h3 class="step-title">{{ t('latentLab.arcimboldo.step4Title') }}</h3>
      <div class="result-compare">
        <div class="compare-panel">
          <span class="compare-label">{{ t('latentLab.arcimboldo.originalLabel') }}</span>
          <img :src="`data:image/png;base64,${mainImage}`" class="compare-image" alt="Original" />
        </div>
        <div class="compare-panel">
          <span class="compare-label">{{ t('latentLab.arcimboldo.mosaicLabel') }}</span>
          <img :src="`data:image/png;base64,${mosaicImage}`" class="compare-image" alt="Mosaic" />
        </div>
      </div>
      <div class="result-controls">
        <div class="opacity-row">
          <label>{{ t('latentLab.arcimboldo.blendLabel') }}</label>
          <input type="range" min="0" max="1" step="0.05" v-model.number="blendOpacity" class="blend-slider" />
        </div>
        <div class="blend-preview" v-if="mainImage && mosaicImage">
          <img :src="`data:image/png;base64,${mosaicImage}`" class="blend-base" alt="Mosaic" />
          <img :src="`data:image/png;base64,${mainImage}`" class="blend-overlay" :style="{ opacity: blendOpacity }" alt="Original overlay" />
        </div>
        <div class="result-actions">
          <button class="download-btn" @click="downloadMosaic">{{ t('latentLab.arcimboldo.downloadBtn') }}</button>
          <button class="reset-btn" @click="reset">{{ t('latentLab.arcimboldo.resetBtn') }}</button>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="errorMessage" class="error-box">{{ errorMessage }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useDetailsState } from '@/composables/useDetailsState'

const { t } = useI18n()
const { record: labRecord } = useLatentLabRecorder('arcimboldo_mosaic')
const { isOpen: explainOpen, onToggle: onExplainToggle } = useDetailsState('ll_arcimboldo_explain')

type Phase = 'input' | 'generating' | 'segmenting' | 'reviewing' | 'tiles' | 'composing' | 'result'
const phase = ref<Phase>('input')
const phaseIndex = computed(() => {
  const order: Phase[] = ['input', 'generating', 'segmenting', 'reviewing', 'tiles', 'composing', 'result']
  return order.indexOf(phase.value)
})

// Input state
const prompt = ref('')
const gridSize = ref(16)
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(-1)

// Results
const mainImage = ref('')
const attentionData = ref<any>(null)
const regions = ref<any[]>([])
const gridAssignment = ref<number[][]>([])
const tilesDone = ref(0)
const tilesTotal = ref(0)
const tiles = ref<Record<string, string[]>>({})
const mosaicImage = ref('')
const blendOpacity = ref(0.3)
const errorMessage = ref('')
const actualSeed = ref<number | null>(null)

// Region colors for visual feedback
const REGION_COLORS = ['#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4', '#FF5722', '#8BC34A']
function regionColor(idx: number): string {
  return REGION_COLORS[idx % REGION_COLORS.length] ?? '#4CAF50'
}

// Session persistence
onMounted(() => {
  const saved = sessionStorage.getItem('lat_lab_arc_prompt')
  if (saved) prompt.value = saved
  const gs = sessionStorage.getItem('lat_lab_arc_grid')
  if (gs) gridSize.value = parseInt(gs)
})

function saveInput() {
  sessionStorage.setItem('lat_lab_arc_prompt', prompt.value)
  sessionStorage.setItem('lat_lab_arc_grid', String(gridSize.value))
}

function reset() {
  phase.value = 'input'
  mainImage.value = ''
  attentionData.value = null
  regions.value = []
  gridAssignment.value = []
  tiles.value = {}
  mosaicImage.value = ''
  errorMessage.value = ''
  tilesDone.value = 0
  tilesTotal.value = 0
}

const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
const gpuUrl = import.meta.env.DEV ? 'http://localhost:17803' : ''

async function startGeneration() {
  if (!prompt.value.trim()) return
  saveInput()
  phase.value = 'generating'
  errorMessage.value = ''

  try {
    // Step 1: Generate image + attention maps via existing endpoint
    const response = await axios.post(`${baseUrl}/api/schema/pipeline/legacy`, {
      prompt: prompt.value,
      output_config: 'attention_cartography_diffusers',
      steps: steps.value,
      cfg: cfgScale.value,
      seed: seed.value,
    })

    if (response.data.status !== 'success' || !response.data.attention_data) {
      throw new Error(response.data.error || 'Attention generation failed')
    }

    attentionData.value = response.data.attention_data
    mainImage.value = attentionData.value.image_base64
    actualSeed.value = response.data.media_output?.seed ?? null

    // Step 2: Segment
    phase.value = 'segmenting'

    const segResponse = await axios.post(`${gpuUrl}/api/diffusers/mosaic/segment`, {
      attention_maps: attentionData.value.attention_maps,
      tokens: attentionData.value.tokens,
      word_groups: attentionData.value.word_groups,
      spatial_resolution: attentionData.value.spatial_resolution,
      image_base64: mainImage.value,
      grid_size: gridSize.value,
    })

    if (!segResponse.data.success) {
      throw new Error(segResponse.data.error || 'Segmentation failed')
    }

    regions.value = segResponse.data.regions
    gridAssignment.value = segResponse.data.grid_assignment
    phase.value = 'reviewing'

  } catch (err: any) {
    errorMessage.value = err.response?.data?.error || err.message || 'Error'
    phase.value = 'input'
  }
}

let progressInterval: ReturnType<typeof setInterval> | null = null

function startProgressPolling() {
  if (progressInterval) clearInterval(progressInterval)
  progressInterval = setInterval(async () => {
    try {
      const resp = await axios.get(`${gpuUrl}/api/diffusers/progress`)
      if (resp.data?.active) {
        tilesDone.value = resp.data.step ?? 0
      }
    } catch { /* ignore polling errors */ }
  }, 1500)
}

function stopProgressPolling() {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

async function startTileGeneration() {
  phase.value = 'tiles'
  errorMessage.value = ''
  // Scale unique tiles per region to grid size — each tile should appear at most ~2x
  const totalCells = gridSize.value * gridSize.value
  const avgCellsPerRegion = Math.ceil(totalCells / Math.max(regions.value.length, 1))
  const tilesPerRegion = Math.max(4, Math.min(avgCellsPerRegion, 64))
  tilesTotal.value = regions.value.length * tilesPerRegion
  tilesDone.value = 0

  startProgressPolling()

  try {
    // Step 3: Generate tiles
    const tilesResponse = await axios.post(`${gpuUrl}/api/diffusers/mosaic/generate-tiles`, {
      regions: regions.value,
      tiles_per_region: tilesPerRegion,
      seed: actualSeed.value ?? -1,
    })

    stopProgressPolling()

    if (!tilesResponse.data.success) {
      throw new Error(tilesResponse.data.error || 'Tile generation failed')
    }

    tiles.value = tilesResponse.data.tiles
    tilesDone.value = tilesResponse.data.total_generated

    // Step 4: Compose mosaic
    phase.value = 'composing'

    const composeResponse = await axios.post(`${gpuUrl}/api/diffusers/mosaic/compose`, {
      grid_assignment: gridAssignment.value,
      tiles: tiles.value,
      original_image_base64: mainImage.value,
    })

    if (!composeResponse.data.success) {
      throw new Error(composeResponse.data.error || 'Composition failed')
    }

    mosaicImage.value = composeResponse.data.mosaic_base64
    phase.value = 'result'

    // Record for research export
    labRecord({
      parameters: {
        prompt: prompt.value,
        grid_size: gridSize.value,
        steps: steps.value,
        cfg: cfgScale.value,
        seed: seed.value,
        regions: regions.value.map(r => r.label),
      },
      results: {
        seed: actualSeed.value,
        region_count: regions.value.length,
        total_tiles: tilesTotal.value,
      },
      outputs: [
        { type: 'image', format: 'png', dataBase64: mosaicImage.value },
      ],
    })

  } catch (err: any) {
    stopProgressPolling()
    errorMessage.value = err.response?.data?.error || err.message || 'Error'
    phase.value = 'reviewing'
  }
}

function downloadMosaic() {
  if (!mosaicImage.value) return
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${mosaicImage.value}`
  link.download = `arcimboldo_mosaic_${actualSeed.value ?? 'unknown'}.png`
  link.click()
}
</script>

<style scoped>
.arcimboldo-mosaic {
  max-width: 900px;
  margin: 0 auto;
}

.page-header { margin-bottom: 1.5rem; }
.page-title {
  font-size: 1.2rem;
  font-weight: 300;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}
.page-subtitle {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
  margin-bottom: 0.8rem;
}

/* Explanation */
.explanation-details { margin-top: 0.5rem; }
.explanation-details summary {
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.8rem;
  cursor: pointer;
  user-select: none;
}
.explanation-body {
  margin-top: 0.8rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.explanation-section { margin-bottom: 1rem; }
.explanation-section:last-child { margin-bottom: 0; }
.explanation-section h4 {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 0.3rem;
}
.explanation-section p {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.5;
}
.explanation-tech {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 0.8rem;
}

/* Steps */
.step-section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
}
.step-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: rgba(76, 175, 80, 0.8);
  margin-bottom: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Prompt */
.prompt-input {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #ffffff;
  padding: 0.5rem;
  font-size: 0.85rem;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
  margin-bottom: 0.5rem;
}
.prompt-input:focus { outline: none; border-color: rgba(76, 175, 80, 0.4); }

.input-controls {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.8rem;
}

.control-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  display: block;
  margin-bottom: 0.2rem;
}

.grid-select {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #ffffff;
  padding: 0.3rem 0.5rem;
  font-size: 0.8rem;
}

/* Settings */
.settings-details summary {
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.8rem;
  cursor: pointer;
}
.settings-body { margin-top: 0.5rem; }
.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}
.setting-item label {
  display: block;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 0.2rem;
}
.setting-number {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  color: #ffffff;
  padding: 0.3rem;
  font-size: 0.8rem;
  box-sizing: border-box;
}

/* Buttons */
.action-btn {
  width: 100%;
  padding: 0.7rem;
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  border-radius: 8px;
  color: rgba(76, 175, 80, 0.9);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
}
.action-btn:hover:not(:disabled) { background: rgba(76, 175, 80, 0.25); }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Status */
.status-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.6);
}
.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(76, 175, 80, 0.3);
  border-top-color: rgba(76, 175, 80, 0.9);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Progress bar */
.progress-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: rgba(76, 175, 80, 0.7);
  transition: width 0.3s;
}

/* Segmentation result */
.image-container { margin-bottom: 0.8rem; }
.main-image {
  width: 100%;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.region-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.8rem;
}
.region-chip {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
}
.color-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Result */
.result-compare {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.8rem;
  margin-bottom: 1rem;
}
.compare-panel { text-align: center; }
.compare-label {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 0.3rem;
}
.compare-image {
  width: 100%;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.opacity-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.8rem;
}
.opacity-row label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  min-width: 4rem;
}
.blend-slider {
  flex: 1;
  accent-color: #4CAF50;
}

.blend-preview {
  position: relative;
  margin-bottom: 1rem;
}
.blend-base {
  width: 100%;
  border-radius: 8px;
  display: block;
}
.blend-overlay {
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  border-radius: 8px;
  pointer-events: none;
}

.result-actions {
  display: flex;
  gap: 0.5rem;
}
.download-btn, .reset-btn {
  flex: 1;
  padding: 0.5rem;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
}
.download-btn {
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  color: rgba(76, 175, 80, 0.9);
}
.reset-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.6);
}

/* Error */
.error-box {
  margin-top: 0.8rem;
  padding: 0.6rem;
  background: rgba(255, 80, 80, 0.1);
  border: 1px solid rgba(255, 80, 80, 0.3);
  border-radius: 6px;
  color: rgba(255, 120, 120, 0.9);
  font-size: 0.8rem;
}
</style>
