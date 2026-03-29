<template>
  <div class="composable-diffusion">
    <!-- Header -->
    <div class="page-header">
      <h2 class="page-title">{{ t('latentLab.composable.headerTitle') }}</h2>
      <p class="page-subtitle">{{ t('latentLab.composable.headerSubtitle') }}</p>
      <details class="explanation-details" :open="explainOpen" @toggle="onExplainToggle">
        <summary>{{ t('latentLab.composable.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.composable.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.composable.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.composable.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.composable.explainHowText') }}</p>
          </div>
          <div class="explanation-section explanation-tech">
            <h4>{{ t('latentLab.composable.techTitle') }}</h4>
            <p>{{ t('latentLab.composable.techText') }}</p>
          </div>
          <div class="explanation-section explanation-references">
            <h4>{{ t('latentLab.composable.referencesTitle') }}</h4>
            <ul class="reference-list">
              <li>
                <span class="ref-authors">Liu et al. (2022)</span>
                <span class="ref-title">"Compositional Visual Generation with Composable Diffusion Models"</span>
                <span class="ref-venue">ECCV 2022</span>
                <a href="https://doi.org/10.1007/978-3-031-19803-8_12" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
            </ul>
          </div>
        </div>
      </details>
    </div>

    <!-- Concept List -->
    <div class="concept-list">
      <div v-for="(concept, idx) in concepts" :key="idx" class="concept-row">
        <div class="concept-header">
          <span class="concept-label">{{ t('latentLab.composable.conceptLabel', { n: idx + 1 }) }}</span>
          <button
            v-if="concepts.length > 2"
            class="remove-btn"
            @click="removeConcept(idx)"
            :disabled="isGenerating"
          >{{ t('latentLab.composable.removeBtn') }}</button>
        </div>
        <textarea
          class="concept-input"
          :placeholder="t('latentLab.composable.conceptPlaceholder')"
          v-model="concept.prompt"
          :disabled="isGenerating"
          rows="2"
        />
        <div class="weight-row">
          <label class="weight-label">{{ t('latentLab.composable.weightLabel') }}</label>
          <input
            type="range"
            class="weight-slider"
            min="0"
            max="2"
            step="0.05"
            v-model.number="concept.weight"
            :disabled="isGenerating"
          />
          <span class="weight-value">{{ concept.weight.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- Add Concept Button -->
    <button
      v-if="concepts.length < 5"
      class="add-concept-btn"
      @click="addConcept"
      :disabled="isGenerating"
    >+ {{ t('latentLab.composable.addConceptBtn') }}</button>

    <!-- Settings -->
    <details class="settings-details" :open="settingsOpen" @toggle="onSettingsToggle">
      <summary>{{ t('latentLab.composable.settingsToggle') }}</summary>
      <div class="settings-body">
        <div class="setting-row">
          <label>{{ t('latentLab.composable.negativePromptLabel') }}</label>
          <textarea
            class="setting-input"
            v-model="negativePrompt"
            :disabled="isGenerating"
            rows="2"
            :placeholder="t('latentLab.composable.negativePromptPlaceholder')"
          />
        </div>
        <div class="settings-grid">
          <div class="setting-row">
            <label>{{ t('latentLab.composable.stepsLabel') }}</label>
            <input type="number" v-model.number="steps" min="1" max="50" :disabled="isGenerating" class="setting-number" />
          </div>
          <div class="setting-row">
            <label>{{ t('latentLab.composable.cfgLabel') }}</label>
            <input type="number" v-model.number="cfgScale" min="1" max="20" step="0.5" :disabled="isGenerating" class="setting-number" />
          </div>
        </div>
        <div class="setting-row">
          <label class="checkbox-label">
            <input type="checkbox" v-model="normalizeWeights" :disabled="isGenerating" />
            {{ t('latentLab.composable.normalizeLabel') }}
          </label>
        </div>
      </div>
    </details>

    <!-- Seed (always visible) -->
    <SeedControl v-model:seed="seed" v-model:random="randomSeed" :disabled="isGenerating" />

    <!-- Generate Button -->
    <button
      class="generate-btn"
      :disabled="!canGenerate || isGenerating"
      @click="generate"
    >
      <span v-if="isGenerating" class="spinner" />
      {{ isGenerating ? t('latentLab.composable.generating') : t('latentLab.composable.generateBtn') }}
    </button>

    <!-- Error -->
    <div v-if="errorMessage" class="error-box">{{ errorMessage }}</div>

    <!-- Result -->
    <div v-if="resultImage" class="result-section">
      <div class="result-header">
        <span class="result-info">
          {{ t('latentLab.composable.resultInfo', {
            concepts: conceptCount,
            time: timing,
            seed: actualSeed
          }) }}
        </span>
        <button class="download-btn" @click="downloadResult">{{ t('latentLab.composable.downloadBtn') }}</button>
      </div>
      <img :src="`data:image/png;base64,${resultImage}`" class="result-image" alt="Composable diffusion result" />
      <div v-if="weightsUsed.length" class="weights-info">
        <span v-for="(w, i) in weightsUsed" :key="i" class="weight-badge">
          {{ concepts[i]?.prompt?.substring(0, 20) || `#${i+1}` }}: {{ w.toFixed(2) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useDetailsState } from '@/composables/useDetailsState'
import SeedControl from '@/components/SeedControl.vue'

const { t } = useI18n()
const { record: labRecord } = useLatentLabRecorder('composable_diffusion')
const { isOpen: explainOpen, onToggle: onExplainToggle } = useDetailsState('ll_composable_explain')
const { isOpen: settingsOpen, onToggle: onSettingsToggle } = useDetailsState('ll_composable_settings', true)

// --- State ---
interface Concept {
  prompt: string
  weight: number
}

const concepts = ref<Concept[]>([
  { prompt: '', weight: 1.0 },
  { prompt: '', weight: 1.0 },
])

const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(123456789)
const randomSeed = ref(false)
const normalizeWeights = ref(true)

const isGenerating = ref(false)
const errorMessage = ref('')
const resultImage = ref('')
const actualSeed = ref<number | null>(null)
const conceptCount = ref(0)
const weightsUsed = ref<number[]>([])
const timing = ref('')

// --- Computed ---
const canGenerate = computed(() => {
  const filledConcepts = concepts.value.filter(c => c.prompt.trim().length > 0)
  return filledConcepts.length >= 2
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
  if (sd) seed.value = parseInt(sd) || 123456789
  const rs = sessionStorage.getItem(`${STORAGE_PREFIX}randomSeed`)
  if (rs) randomSeed.value = rs === 'true'
  const n = sessionStorage.getItem(`${STORAGE_PREFIX}normalize`)
  if (n) normalizeWeights.value = n === 'true'
}

onMounted(restoreState)
watch([concepts, negativePrompt, steps, cfgScale, seed, normalizeWeights], saveState, { deep: true })

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
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${resultImage.value}`
  link.download = `composable_diffusion_${actualSeed.value}.png`
  link.click()
}

async function generate() {
  if (!canGenerate.value || isGenerating.value) return

  isGenerating.value = true
  errorMessage.value = ''
  resultImage.value = ''
  actualSeed.value = null
  conceptCount.value = 0
  weightsUsed.value = []
  timing.value = ''

  try {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const activeConcepts = concepts.value
      .filter(c => c.prompt.trim().length > 0)
      .map(c => ({ prompt: c.prompt.trim(), weight: c.weight }))

    const response = await axios.post(`${baseUrl}/api/schema/pipeline/legacy`, {
      prompt: activeConcepts[0]?.prompt ?? '',
      output_config: 'composable_diffusion_diffusers',
      concepts: activeConcepts,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
      seed: randomSeed.value ? -1 : seed.value,
      normalize_weights: normalizeWeights.value,
    })

    if (response.data.status === 'success') {
      const data = response.data.composable_data
      if (data) {
        resultImage.value = data.image_base64
        actualSeed.value = data.seed
        conceptCount.value = data.concept_count
        weightsUsed.value = data.weights_used || []
        timing.value = data.timing_s ? `${data.timing_s}s` : ''

        labRecord({
          parameters: {
            concepts: activeConcepts,
            negative_prompt: negativePrompt.value,
            steps: steps.value,
            cfg: cfgScale.value,
            seed: seed.value,
            normalize_weights: normalizeWeights.value,
          },
          results: { seed: actualSeed.value, timing_s: data.timing_s },
          outputs: [{ type: 'image', format: 'png', dataBase64: resultImage.value }],
        })
      } else {
        errorMessage.value = 'No composable data in response'
      }
    } else {
      errorMessage.value = response.data.error || 'Generation failed'
    }
  } catch (err: any) {
    errorMessage.value = err.response?.data?.error || err.message || 'Unknown error'
  } finally {
    isGenerating.value = false
  }
}
</script>

<style scoped>
.composable-diffusion {
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 1.5rem;
}

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
.explanation-details {
  margin-top: 0.5rem;
}

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

.explanation-section {
  margin-bottom: 1rem;
}

.explanation-section:last-child {
  margin-bottom: 0;
}

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

.reference-list {
  list-style: none;
  padding: 0;
}

.reference-list li {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 0.3rem;
}

.ref-authors { font-weight: 600; margin-right: 0.3rem; }
.ref-title { font-style: italic; margin-right: 0.3rem; }
.ref-venue { margin-right: 0.3rem; }
.ref-doi { color: rgba(76, 175, 80, 0.6); text-decoration: none; }
.ref-doi:hover { color: rgba(76, 175, 80, 0.9); }

/* Concept list */
.concept-list {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  margin-bottom: 0.8rem;
}

.concept-row {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 0.8rem;
}

.concept-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.concept-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.remove-btn {
  font-size: 0.7rem;
  color: rgba(255, 100, 100, 0.6);
  background: none;
  border: 1px solid rgba(255, 100, 100, 0.2);
  border-radius: 4px;
  padding: 0.15rem 0.4rem;
  cursor: pointer;
}

.remove-btn:hover {
  color: rgba(255, 100, 100, 0.9);
  border-color: rgba(255, 100, 100, 0.4);
}

.concept-input {
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
}

.concept-input:focus {
  outline: none;
  border-color: rgba(76, 175, 80, 0.4);
}

.weight-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.weight-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  min-width: 3rem;
}

.weight-slider {
  flex: 1;
  accent-color: #4CAF50;
}

.weight-value {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.6);
  font-family: monospace;
  min-width: 2.5rem;
  text-align: right;
}

.add-concept-btn {
  width: 100%;
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.85rem;
  cursor: pointer;
  margin-bottom: 1rem;
}

.add-concept-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.6);
}

/* Settings */
.settings-details {
  margin-bottom: 1rem;
}

.settings-details summary {
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.8rem;
  cursor: pointer;
  user-select: none;
}

.settings-body {
  margin-top: 0.5rem;
  padding: 0.8rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.8rem;
  margin-top: 0.8rem;
}

.setting-row label {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 0.2rem;
}

.setting-input {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #ffffff;
  padding: 0.4rem;
  font-size: 0.8rem;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
}

.setting-number {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #ffffff;
  padding: 0.4rem;
  font-size: 0.8rem;
  box-sizing: border-box;
}

.checkbox-label {
  display: flex !important;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.5rem;
  font-size: 0.8rem !important;
  color: rgba(255, 255, 255, 0.5) !important;
  cursor: pointer;
}

/* Generate */
.generate-btn {
  width: 100%;
  padding: 0.8rem;
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  border-radius: 8px;
  color: rgba(76, 175, 80, 0.9);
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.generate-btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.25);
}

.generate-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(76, 175, 80, 0.3);
  border-top-color: rgba(76, 175, 80, 0.9);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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

/* Result */
.result-section {
  margin-top: 1.2rem;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.result-info {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}

.download-btn {
  font-size: 0.75rem;
  color: rgba(76, 175, 80, 0.7);
  background: none;
  border: 1px solid rgba(76, 175, 80, 0.3);
  border-radius: 4px;
  padding: 0.2rem 0.5rem;
  cursor: pointer;
}

.download-btn:hover {
  color: rgba(76, 175, 80, 1);
  border-color: rgba(76, 175, 80, 0.5);
}

.result-image {
  width: 100%;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.weights-info {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.weight-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  font-family: monospace;
}
</style>
