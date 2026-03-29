<template>
  <div class="denoising-archaeology">
    <!-- Header -->
    <div class="page-header">
      <h2 class="page-title">
        {{ t('latentLab.archaeology.headerTitle') }}
      </h2>
      <p class="page-subtitle">{{ t('latentLab.archaeology.headerSubtitle') }}</p>
      <details class="explanation-details" :open="explainOpen" @toggle="onExplainToggle">
        <summary>{{ t('latentLab.archaeology.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.archaeology.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.archaeology.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.archaeology.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.archaeology.explainHowText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.archaeology.explainReadTitle') }}</h4>
            <p>{{ t('latentLab.archaeology.explainReadText') }}</p>
          </div>
          <div class="explanation-section explanation-tech">
            <h4>{{ t('latentLab.archaeology.techTitle') }}</h4>
            <p>{{ t('latentLab.archaeology.techText') }}</p>
          </div>
          <div class="explanation-section explanation-references">
            <h4>{{ t('latentLab.archaeology.referencesTitle') }}</h4>
            <ul class="reference-list">
              <li>
                <span class="ref-authors">Kwon et al. (2023)</span>
                <span class="ref-title">"Diffusion Models Already Have a Semantic Latent Space"</span>
                <span class="ref-venue">ICLR 2023</span>
                <a href="https://doi.org/10.48550/arXiv.2210.10960" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
              <li>
                <span class="ref-authors">Ho et al. (2020)</span>
                <span class="ref-title">"Denoising Diffusion Probabilistic Models"</span>
                <span class="ref-venue">NeurIPS 2020</span>
                <a href="https://doi.org/10.48550/arXiv.2006.11239" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
            </ul>
          </div>
        </div>
      </details>
    </div>

    <!-- Input Section -->
    <div class="input-section">
      <MediaInputBox
        icon="lightbulb"
        :label="t('latentLab.archaeology.promptLabel')"
        :placeholder="t('latentLab.archaeology.promptPlaceholder')"
        v-model:value="promptText"
        input-type="text"
        :rows="2"
        resize-type="auto"
        :disabled="isGenerating"
        @copy="copyInputText"
        @paste="pasteInputText"
        @clear="clearInputText"
      />
      <button
        class="generate-btn"
        :disabled="isGenerating || !promptText.trim()"
        @click="generate"
      >
        <span v-if="isGenerating" class="spinner"></span>
        <span v-else>{{ t('latentLab.archaeology.generate') }}</span>
      </button>

      <!-- Advanced Settings -->
      <details class="advanced-settings" :open="advancedOpen" @toggle="onAdvancedToggle">
        <summary>{{ t('latentLab.archaeology.advancedLabel') }}</summary>
        <div class="settings-grid">
          <label>
            {{ t('latentLab.archaeology.negativeLabel') }}
            <input v-model="negativePrompt" type="text" class="setting-input" />
            <div class="control-hint">{{ t('latentLab.shared.negativeHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.archaeology.stepsLabel') }}
            <input v-model.number="steps" type="number" min="10" max="50" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.shared.stepsHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.archaeology.cfgLabel') }}
            <input v-model.number="cfgScale" type="number" min="1" max="20" step="0.5" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.shared.cfgHint') }}</div>
          </label>
        </div>
      </details>

      <!-- Seed (always visible) -->
      <div class="seed-row">
        <label>
          {{ t('latentLab.archaeology.seedLabel') }}
          <input v-model.number="seed" type="number" min="0" :disabled="randomSeed" class="setting-input setting-seed" />
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="randomSeed" />
          {{ t('latentLab.shared.randomVariation') }}
        </label>
      </div>
    </div>

    <!-- Visualization -->
    <div class="visualization-section" :class="{ 'is-disabled': stepImages.length === 0 }">
      <!-- Full-size viewer -->
      <div class="viewer-container">
        <template v-if="stepImages.length > 0">
          <img
            :src="currentImageSrc"
            class="viewer-image"
            :alt="currentStepLabel"
          />
          <div class="phase-badge" :style="{ background: currentPhaseColor }">
            {{ currentPhaseLabel }}
          </div>
        </template>
        <div v-else class="placeholder-image"></div>
      </div>

      <!-- Phase description -->
      <div class="phase-description" :style="{ color: currentPhaseColor }">
        {{ currentPhaseDesc }}
      </div>

      <!-- Timeline slider -->
      <div class="timeline-section">
        <div class="timeline-control">
          <label class="control-label">{{ t('latentLab.archaeology.timelineLabel') }}</label>
          <div class="slider-container">
            <input
              type="range"
              v-model.number="selectedStepIndex"
              :min="0"
              :max="stepImages.length"
              :step="1"
              class="control-slider"
            />
            <span class="slider-value">{{ currentStepLabel }}</span>
          </div>
          <div class="control-hint">{{ t('latentLab.archaeology.timelineHint') }}</div>
        </div>
        <!-- Phase markers -->
        <div class="phase-markers">
          <div class="phase-marker phase-early" :style="{ width: earlyPhaseWidth + '%' }">
            {{ t('latentLab.archaeology.phaseEarly') }}
          </div>
          <div class="phase-marker phase-mid" :style="{ width: midPhaseWidth + '%' }">
            {{ t('latentLab.archaeology.phaseMid') }}
          </div>
          <div class="phase-marker phase-late" :style="{ width: latePhaseWidth + '%' }">
            {{ t('latentLab.archaeology.phaseLate') }}
          </div>
        </div>
      </div>

      <!-- Filmstrip -->
      <div class="filmstrip-section">
        <div class="filmstrip-label">{{ t('latentLab.archaeology.filmstripLabel') }}</div>
        <div class="filmstrip-scroll" ref="filmstripRef">
          <div
            v-for="(img, idx) in stepImages"
            :key="idx"
            class="filmstrip-item"
            :class="{
              selected: selectedStepIndex === idx,
              'phase-early': getPhase(idx) === 'early',
              'phase-mid': getPhase(idx) === 'mid',
              'phase-late': getPhase(idx) === 'late'
            }"
            @click="selectedStepIndex = idx"
          >
            <img :src="`data:image/jpeg;base64,${img.image_base64}`" class="filmstrip-thumb" />
            <span class="filmstrip-step">{{ img.step + 1 }}</span>
          </div>
          <!-- Final image thumbnail -->
          <div
            class="filmstrip-item filmstrip-final"
            :class="{ selected: selectedStepIndex === stepImages.length }"
            @click="selectedStepIndex = stepImages.length"
          >
            <img :src="`data:image/png;base64,${finalImage}`" class="filmstrip-thumb" />
            <span class="filmstrip-step">&#x2713;</span>
          </div>
        </div>
      </div>

      <!-- Seed + Download -->
      <div class="seed-row">
        <div class="seed-display">Seed: {{ actualSeed }}</div>
        <button class="download-btn" @click="downloadImage">
          {{ t('latentLab.archaeology.download') }}
        </button>
      </div>
    </div>

    <!-- Empty State Hint (shown over disabled visualization) -->
    <div class="empty-state-overlay" v-if="stepImages.length === 0 && !isGenerating">
      <p>{{ t('latentLab.archaeology.emptyHint') }}</p>
    </div>

    <!-- Generation Progress -->
    <div class="progress-state" v-if="isGenerating">
      <div class="progress-spinner"></div>
      <p>{{ t('latentLab.archaeology.generating') }}</p>
    </div>

    <!-- Error Display -->
    <div class="error-display" v-if="errorMessage">
      <p>{{ errorMessage }}</p>
      <button @click="errorMessage = ''" class="dismiss-btn">&times;</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import MediaInputBox from '@/components/MediaInputBox.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useDetailsState } from '@/composables/useDetailsState'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

const { t } = useI18n()
const pageContextStore = usePageContextStore()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord } = useLatentLabRecorder('denoising_archaeology')
const { isOpen: explainOpen, onToggle: onExplainToggle } = useDetailsState('ll_archaeology_explain')
const { isOpen: advancedOpen, onToggle: onAdvancedToggle } = useDetailsState('ll_archaeology_advanced')

interface StepImage {
  step: number
  timestep: number
  image_base64: string
}

// State
const promptText = ref('')
const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(123456789)
const randomSeed = ref(false)
const isGenerating = ref(false)
const errorMessage = ref('')

// Result data
const stepImages = ref<StepImage[]>([])
const finalImage = ref('')
const totalSteps = ref(25)
const actualSeed = ref(0)

// Interaction state
// 0..stepImages.length-1 = step thumbnails, stepImages.length = final image
const selectedStepIndex = ref(0)

// Phase helpers
function getPhase(idx: number): 'early' | 'mid' | 'late' {
  const total = stepImages.value.length
  if (total === 0) return 'early'
  const ratio = idx / total
  if (ratio < 0.33) return 'early'
  if (ratio < 0.67) return 'mid'
  return 'late'
}

const currentPhaseColor = computed(() => {
  if (selectedStepIndex.value >= stepImages.value.length) return '#4CAF50'
  const phase = getPhase(selectedStepIndex.value)
  if (phase === 'early') return '#FF9800'
  if (phase === 'mid') return '#00BCD4'
  return '#4CAF50'
})

const currentPhaseLabel = computed(() => {
  if (selectedStepIndex.value >= stepImages.value.length) {
    return t('latentLab.archaeology.finalImageLabel')
  }
  const phase = getPhase(selectedStepIndex.value)
  if (phase === 'early') return t('latentLab.archaeology.phaseEarly')
  if (phase === 'mid') return t('latentLab.archaeology.phaseMid')
  return t('latentLab.archaeology.phaseLate')
})

const currentPhaseDesc = computed(() => {
  if (selectedStepIndex.value >= stepImages.value.length) return ''
  const phase = getPhase(selectedStepIndex.value)
  if (phase === 'early') return t('latentLab.archaeology.phaseEarlyDesc')
  if (phase === 'mid') return t('latentLab.archaeology.phaseMidDesc')
  return t('latentLab.archaeology.phaseLateDesc')
})

const currentImageSrc = computed(() => {
  if (selectedStepIndex.value >= stepImages.value.length) {
    return `data:image/png;base64,${finalImage.value}`
  }
  const img = stepImages.value[selectedStepIndex.value]
  return img ? `data:image/jpeg;base64,${img.image_base64}` : ''
})

const currentStepLabel = computed(() => {
  if (selectedStepIndex.value >= stepImages.value.length) {
    return t('latentLab.archaeology.finalImageLabel')
  }
  const img = stepImages.value[selectedStepIndex.value]
  return img ? `${t('latentLab.archaeology.timelineLabel')} ${img.step + 1} / ${totalSteps.value}` : ''
})

// Phase width percentages for marker bar
const earlyPhaseWidth = computed(() => Math.round(33))
const midPhaseWidth = computed(() => Math.round(34))
const latePhaseWidth = computed(() => Math.round(33))

// Filmstrip scroll ref
const filmstripRef = ref<HTMLDivElement | null>(null)

// Auto-scroll filmstrip when slider changes
watch(selectedStepIndex, (idx) => {
  const el = filmstripRef.value
  if (!el) return
  const child = el.children[idx] as HTMLElement | undefined
  if (child) {
    child.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }
})

// Session persistence — restore on mount
onMounted(() => {
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  if (s('lat_lab_da_prompt')) promptText.value = s('lat_lab_da_prompt')!
  if (s('lat_lab_da_negative')) negativePrompt.value = s('lat_lab_da_negative')!
  if (s('lat_lab_da_steps')) steps.value = parseFloat(s('lat_lab_da_steps')!) || 25
  if (s('lat_lab_da_cfg')) cfgScale.value = parseFloat(s('lat_lab_da_cfg')!) || 4.5
  if (s('lat_lab_da_seed')) seed.value = parseFloat(s('lat_lab_da_seed')!) || 123456789
  if (s('lat_lab_da_random_seed')) randomSeed.value = s('lat_lab_da_random_seed') === 'true'
})

// Session persistence — save on change
watch(promptText, v => sessionStorage.setItem('lat_lab_da_prompt', v))
watch([negativePrompt, steps, cfgScale, seed, randomSeed], () => {
  sessionStorage.setItem('lat_lab_da_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_da_steps', String(steps.value))
  sessionStorage.setItem('lat_lab_da_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_da_seed', String(seed.value))
  sessionStorage.setItem('lat_lab_da_random_seed', String(randomSeed.value))
})

function copyInputText() { copyToClipboard(promptText.value) }
function pasteInputText() { promptText.value = pasteFromClipboard() }
function clearInputText() { promptText.value = ''; sessionStorage.removeItem('lat_lab_da_prompt') }

function downloadImage() {
  const isStepImage = selectedStepIndex.value < stepImages.value.length
  const imgSrc = isStepImage
    ? stepImages.value[selectedStepIndex.value]?.image_base64
    : finalImage.value
  if (!imgSrc) return
  const format = isStepImage ? 'jpeg' : 'png'
  const link = document.createElement('a')
  link.href = `data:image/${format};base64,${imgSrc}`
  link.download = `denoising_step_${selectedStepIndex.value}_seed_${actualSeed.value}.${format}`
  link.click()
}

async function generate() {
  if (!promptText.value.trim() || isGenerating.value) return

  isGenerating.value = true
  errorMessage.value = ''
  stepImages.value = []
  finalImage.value = ''
  selectedStepIndex.value = 0

  try {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const response = await axios.post(`${baseUrl}/api/schema/pipeline/legacy`, {
      prompt: promptText.value,
      output_config: 'denoising_archaeology_diffusers',
      seed: randomSeed.value ? -1 : seed.value,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
    })

    if (response.data.status === 'success') {
      const archData = response.data.archaeology_data
      if (archData) {
        stepImages.value = archData.step_images || []
        finalImage.value = archData.image_base64 || ''
        totalSteps.value = archData.total_steps || steps.value
        actualSeed.value = archData.seed || response.data.media_output?.seed || 0
        // Start at first step
        selectedStepIndex.value = 0

        // Record for research export
        labRecord({
          parameters: {
            prompt: promptText.value,
            negative_prompt: negativePrompt.value,
            steps: steps.value,
            cfg: cfgScale.value,
            seed: seed.value,
          },
          results: { seed: actualSeed.value, total_steps: totalSteps.value },
          outputs: finalImage.value
            ? [{ type: 'image', format: 'png', dataBase64: finalImage.value }]
            : undefined,
          steps: stepImages.value.map(s => ({
            format: 'jpg',
            dataBase64: s.image_base64,
          })),
        })
      } else {
        errorMessage.value = 'No archaeology data in response'
      }
    } else {
      errorMessage.value = response.data.error || response.data.message || 'Generation failed'
    }
  } catch (err: any) {
    errorMessage.value = err.response?.data?.error || err.message || 'Network error'
  } finally {
    isGenerating.value = false
  }
}

// Page Context for Trashy
const trashyFocusHint = computed<FocusHint>(() => {
  if (isGenerating.value || stepImages.value.length > 0) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  return { x: 8, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'denoising_archaeology',
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
</script>

<style scoped>
.denoising-archaeology {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1.5rem 1.5rem 3rem;
}

/* Page Header */
.page-header {
  margin-bottom: 1.5rem;
}

.page-title {
  color: #667eea;
  font-size: 1.2rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.page-subtitle {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.95rem;
  line-height: 1.6;
  margin: 0 0 0.75rem;
}

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

.explanation-details summary:hover {
  color: #667eea;
}

.explanation-body {
  padding: 0 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.explanation-section h4 {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.85rem;
  margin: 0 0 0.25rem;
}

.explanation-section p {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.82rem;
  line-height: 1.6;
  margin: 0;
}

.explanation-tech {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 0.75rem;
}

.explanation-tech p {
  font-size: 0.78rem;
}

.reference-list { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.reference-list li { margin-bottom: 0.4rem; font-size: 0.8rem; color: rgba(255,255,255,0.6); }
.ref-authors { font-weight: 500; color: rgba(255,255,255,0.8); }
.ref-title { font-style: italic; }
.ref-venue { color: rgba(255,255,255,0.5); }
.ref-doi { color: rgba(102,126,234,0.8); text-decoration: none; margin-left: 0.3rem; }
.ref-doi:hover { text-decoration: underline; }

/* Input Section */
.input-section {
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

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
  min-height: 48px;
}

.generate-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Advanced Settings */
.advanced-settings {
  margin-top: 0.75rem;
}

.advanced-settings summary {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
  cursor: pointer;
  padding: 0.25rem 0;
}

.settings-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.settings-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem;
}

.setting-input {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  color: white;
  font-size: 0.85rem;
}

.setting-small {
  width: 80px;
}

.setting-seed {
  width: 14ch;
}

/* Visualization */
.visualization-section {
  margin-top: 1rem;
}

.viewer-container {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
}

.viewer-image {
  display: block;
  width: 100%;
  height: auto;
}

.phase-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  color: white;
  font-size: 0.8rem;
  font-weight: 700;
  backdrop-filter: blur(4px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.phase-description {
  font-size: 0.82rem;
  margin-top: 0.5rem;
  min-height: 1.2em;
}

/* Timeline */
.timeline-section {
  margin-top: 1.25rem;
}

.timeline-control {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.control-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
  min-width: 50px;
  flex-shrink: 0;
}

.slider-container {
  flex: 1;
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
  min-width: 120px;
  text-align: right;
  font-family: 'Fira Code', 'Consolas', monospace;
}

/* Phase markers below slider */
.phase-markers {
  display: flex;
  margin-top: 0.35rem;
  margin-left: 50px;
  padding-left: 1rem;
  gap: 0;
}

.phase-marker {
  text-align: center;
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.2rem 0;
  border-radius: 3px;
}

.phase-early {
  color: #FF9800;
  background: rgba(255, 152, 0, 0.1);
}

.phase-mid {
  color: #00BCD4;
  background: rgba(0, 188, 212, 0.1);
}

.phase-late {
  color: #4CAF50;
  background: rgba(76, 175, 80, 0.1);
}

/* Filmstrip */
.filmstrip-section {
  margin-top: 1.25rem;
}

.filmstrip-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.filmstrip-scroll {
  display: flex;
  gap: 0.4rem;
  overflow-x: auto;
  padding: 0.5rem 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(102, 126, 234, 0.3) transparent;
}

.filmstrip-scroll::-webkit-scrollbar {
  height: 6px;
}

.filmstrip-scroll::-webkit-scrollbar-thumb {
  background: rgba(102, 126, 234, 0.3);
  border-radius: 3px;
}

.filmstrip-item {
  flex-shrink: 0;
  width: 80px;
  cursor: pointer;
  border-radius: 6px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: all 0.15s ease;
  position: relative;
}

.filmstrip-item:hover {
  border-color: rgba(255, 255, 255, 0.3);
}

.filmstrip-item.selected {
  border-color: #667eea;
  box-shadow: 0 0 8px rgba(102, 126, 234, 0.4);
}

.filmstrip-item.selected.phase-early {
  border-color: #FF9800;
  box-shadow: 0 0 8px rgba(255, 152, 0, 0.4);
}

.filmstrip-item.selected.phase-mid {
  border-color: #00BCD4;
  box-shadow: 0 0 8px rgba(0, 188, 212, 0.4);
}

.filmstrip-item.selected.phase-late {
  border-color: #4CAF50;
  box-shadow: 0 0 8px rgba(76, 175, 80, 0.4);
}

.filmstrip-final {
  border-color: rgba(76, 175, 80, 0.3);
}

.filmstrip-final.selected {
  border-color: #4CAF50;
  box-shadow: 0 0 8px rgba(76, 175, 80, 0.4);
}

.filmstrip-thumb {
  display: block;
  width: 80px;
  height: 80px;
  object-fit: cover;
}

.filmstrip-step {
  display: block;
  text-align: center;
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.5);
  padding: 0.15rem 0;
  background: rgba(0, 0, 0, 0.4);
  font-family: 'Fira Code', 'Consolas', monospace;
}

.seed-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.75rem;
}

.seed-row .checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
  cursor: pointer;
}

.seed-display {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.7rem;
  font-family: 'Fira Code', 'Consolas', monospace;
}

.download-btn {
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.download-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

/* Empty / Progress / Error States */
.visualization-section.is-disabled {
  opacity: 0.35;
  pointer-events: none;
}

.placeholder-image {
  width: 100%;
  aspect-ratio: 1/1;
  max-width: 512px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
}

.empty-state-overlay {
  text-align: center;
  padding: 2rem;
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.95rem;
  margin-top: -2rem;
}

.progress-state {
  text-align: center;
  padding: 3rem 2rem;
  color: rgba(102, 126, 234, 0.7);
}

.progress-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(102, 126, 234, 0.2);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 1rem;
}

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

.dismiss-btn {
  background: none;
  border: none;
  color: rgba(244, 67, 54, 0.6);
  font-size: 1.2rem;
  cursor: pointer;
}

.control-hint {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.7rem;
  line-height: 1.4;
}

</style>
