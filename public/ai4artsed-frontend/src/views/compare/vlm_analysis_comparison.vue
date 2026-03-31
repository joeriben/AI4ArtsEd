<template>
  <div class="compare-page">
    <div class="compare-main">
      <!-- Image Input Section -->
      <div class="input-section">
        <MediaInputBox
          icon="lightbulb"
          :label="t('compare.vlmAnalysis.imageLabel')"
          :value="uploadedImage ?? ''"
          @update:value="(val: string) => uploadedImage = val || undefined"
          input-type="image"
          :allow-sketch="true"
          :initial-image="uploadedImage"
          @image-uploaded="onImageUploaded"
          @image-removed="onImageRemoved"
          @copy="() => {}"
          @paste="() => {}"
          @clear="onImageRemoved"
        />

        <!-- Perspective selector -->
        <div class="perspective-row">
          <label class="perspective-label">{{ t('compare.vlmAnalysis.perspectiveLabel') }}</label>
          <select v-model="selectedPerspective" class="perspective-select">
            <option v-for="p in perspectives" :key="p.id" :value="p.id">
              {{ t(`compare.vlmAnalysis.perspectives.${p.id}`) }}
            </option>
          </select>
        </div>

        <!-- Free prompt input (only when perspective is 'free') -->
        <div v-if="selectedPerspective === 'free'" class="free-prompt-row">
          <textarea
            v-model="freePrompt"
            class="free-prompt-input"
            :placeholder="t('compare.vlmAnalysis.freePromptPlaceholder')"
            rows="3"
          />
        </div>

        <!-- VLM selection checkboxes -->
        <div class="vlm-selector">
          <label class="vlm-selector-label">{{ t('compare.vlmAnalysis.modelsLabel') }}</label>
          <div class="vlm-chips">
            <label
              v-for="vlm in VLM_MODELS"
              :key="vlm.id"
              class="vlm-chip"
              :class="{ active: selectedModels.includes(vlm.id) }"
            >
              <input
                type="checkbox"
                :value="vlm.id"
                v-model="selectedModels"
                class="vlm-chip-input"
              />
              <span class="vlm-chip-label">{{ vlm.label }}</span>
            </label>
          </div>
        </div>

        <GenerationButton
          :disabled="!canAnalyze"
          :executing="isAnalyzing"
          :label="t('compare.vlmAnalysis.analyzeBtn')"
          :executing-label="t('compare.vlmAnalysis.analyzing')"
          @click="startAnalysis"
        />
      </div>

      <!-- Results Grid -->
      <div v-if="results.length > 0" class="results-grid" :style="{ gridTemplateColumns: gridColumns }">
        <div
          v-for="(result, idx) in results"
          :key="result.model"
          class="result-card"
          :class="{
            'is-active': result.loading && idx === activeModelIdx,
            'is-waiting': result.loading && idx !== activeModelIdx,
            'is-done': !result.loading && !result.error,
            'is-error': !!result.error,
          }"
        >
          <div class="result-header">
            <span class="result-model">{{ getModelLabel(result.model) }}</span>
            <span v-if="result.latency_s != null" class="result-latency">{{ result.latency_s }}s</span>
            <span v-if="result.loading && idx === activeModelIdx" class="result-status active">
              <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
            </span>
            <span v-else-if="result.loading" class="result-status waiting">{{ t('compare.vlmAnalysis.waiting') }}</span>
          </div>
          <div v-if="result.error" class="result-error">{{ result.error }}</div>
          <div v-else-if="result.description" class="result-text">{{ result.description }}</div>
        </div>
      </div>
    </div>

    <!-- Trashy Chat Panel -->
    <ComparisonChat
      ref="chatRef"
      class="compare-chat-panel"
      compare-type="vlm-analysis"
      :comparison-context="comparisonContext"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import ComparisonChat from '@/components/ComparisonChat.vue'
import GenerationButton from '@/components/GenerationButton.vue'

const { t } = useI18n()

// --- VLM Models ---
const VLM_MODELS = [
  { id: 'qwen3-vl:2b', label: 'Qwen3-VL 2B' },
  { id: 'qwen3-vl:4b', label: 'Qwen3-VL 4B' },
  { id: 'qwen3-vl:32b', label: 'Qwen3-VL 32B' },
  { id: 'llama3.2-vision:latest', label: 'Llama 3.2 Vision' },
]

// --- Analysis Perspectives ---
const perspectives = [
  { id: 'free' },
  { id: 'neutral' },
  { id: 'safety' },
  { id: 'bildwissenschaftlich' },
  { id: 'ikonik' },
  { id: 'bildungstheoretisch' },
  { id: 'ethisch' },
  { id: 'kritisch' },
]

// Perspective → prompt mapping (backend prompts used for structured ones)
const PERSPECTIVE_PROMPTS: Record<string, string> = {
  neutral: 'Describe this image in 2-3 sentences. Focus on subject, composition, colors, and style.',
  safety: 'Examine this image for violence, nudity, hate symbols, or inappropriate content for children. Describe what you see and flag any concerns.',
}

// --- State ---
const uploadedImage = ref<string | undefined>(undefined)
const imagePath = ref<string | null>(null)
const selectedPerspective = ref('neutral')
const freePrompt = ref('')
const selectedModels = ref<string[]>(['qwen3-vl:2b', 'qwen3-vl:4b', 'qwen3-vl:32b', 'llama3.2-vision:latest'])
const isAnalyzing = ref(false)
const activeModelIdx = ref(-1)
const chatRef = ref<InstanceType<typeof ComparisonChat> | null>(null)
const comparisonContext = ref('')

interface AnalysisResult {
  model: string
  description: string
  latency_s: number | null
  loading: boolean
  error: string | null
}

const results = ref<AnalysisResult[]>([])

const gridColumns = computed(() => {
  const n = results.value.length || selectedModels.value.length
  if (n <= 1) return '1fr'
  if (n === 2) return 'repeat(2, 1fr)'
  if (n === 3) return 'repeat(3, 1fr)'
  return 'repeat(2, 1fr)' // 4+ → 2 columns, cards wrap
})

const canAnalyze = computed(() => {
  if (!imagePath.value) return false
  if (selectedModels.value.length === 0) return false
  if (selectedPerspective.value === 'free' && !freePrompt.value.trim()) return false
  return true
})

function getModelLabel(modelId: string): string {
  return VLM_MODELS.find(m => m.id === modelId)?.label ?? modelId
}

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

function onImageUploaded(data: { image_path: string; preview_url: string }) {
  imagePath.value = data.image_path
  uploadedImage.value = data.preview_url
}

function onImageRemoved() {
  imagePath.value = null
  uploadedImage.value = undefined
}

async function getAnalysisPrompt(): Promise<string> {
  if (selectedPerspective.value === 'free') {
    return freePrompt.value.trim()
  }

  // Check local mapping first (neutral, safety)
  if (PERSPECTIVE_PROMPTS[selectedPerspective.value]) {
    return PERSPECTIVE_PROMPTS[selectedPerspective.value]!
  }

  // For structured perspectives (bildwissenschaftlich, ikonik, etc.),
  // fetch from backend config
  try {
    const resp = await fetch(`${getBaseUrl()}/api/schema/compare/analysis-prompt?perspective=${selectedPerspective.value}`)
    if (resp.ok) {
      const data = await resp.json()
      return data.prompt
    }
  } catch {
    // Fallback
  }

  // Ultimate fallback
  return 'Analyze this image thoroughly.'
}

async function startAnalysis() {
  if (!canAnalyze.value || isAnalyzing.value) return

  isAnalyzing.value = true
  comparisonContext.value = ''  // Reset — prevents stale context triggering Trashy
  chatRef.value?.onNewRun()

  const prompt = await getAnalysisPrompt()
  const models = [...selectedModels.value]  // Snapshot — won't change mid-loop

  // Initialize result cards with loading state
  results.value = models.map(model => ({
    model,
    description: '',
    latency_s: null,
    loading: true,
    error: null,
  }))

  // Sequential execution — must swap VLMs one at a time (VRAM)
  for (let idx = 0; idx < models.length; idx++) {
    const model = models[idx]!
    activeModelIdx.value = idx
    try {
      const resp = await fetch(`${getBaseUrl()}/api/schema/compare/analyze-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_path: imagePath.value,
          model,
          prompt,
        }),
      })
      const data = await resp.json()
      if (data.status === 'success') {
        results.value[idx] = {
          model,
          description: data.description,
          latency_s: data.latency_s,
          loading: false,
          error: null,
        }
      } else {
        results.value[idx] = {
          model,
          description: '',
          latency_s: null,
          loading: false,
          error: data.error || 'Unknown error',
        }
      }
    } catch (e: any) {
      results.value[idx] = {
        model,
        description: '',
        latency_s: null,
        loading: false,
        error: e.message || 'Connection error',
      }
    }
  }
  isAnalyzing.value = false
  activeModelIdx.value = -1

  // Build comparison context for Trashy — only if >= 2 models succeeded
  const successful = results.value.filter(r => r.description)
  if (successful.length >= 2) {
    const descriptions = successful
      .map(r => `[${getModelLabel(r.model)} (${r.latency_s}s)]\n${r.description}`)
      .join('\n\n')
    const failed = results.value.filter(r => r.error)
    const failNote = failed.length > 0
      ? `\n\nFailed models: ${failed.map(r => getModelLabel(r.model)).join(', ')}`
      : ''
    comparisonContext.value = `generation_complete\n\nPerspective: ${selectedPerspective.value}\n\n${descriptions}${failNote}`
  }
}
</script>

<style scoped>
.compare-page {
  display: flex;
  gap: 1rem;
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
  min-height: calc(100vh - 120px);
}

.compare-main {
  flex: 1;
  min-width: 0;
  padding-bottom: 200px;
}

.compare-chat-panel {
  width: 300px;
  flex-shrink: 0;
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 120px);
}

/* Input Section */
.input-section {
  margin-bottom: 1.5rem;
}

.input-section :deep(.generation-button-container) {
  margin-top: 1.5rem;
}

.perspective-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.perspective-label {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.perspective-select {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.8rem;
  outline: none;
  font-family: inherit;
}

.perspective-select:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.perspective-select option {
  background: #1a1a1a;
}

.free-prompt-row {
  margin-top: 0.5rem;
}

.free-prompt-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.8rem;
  outline: none;
  resize: vertical;
  font-family: inherit;
}

.free-prompt-input:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.free-prompt-input::placeholder {
  color: rgba(255, 255, 255, 0.25);
}

/* VLM Selector */
.vlm-selector {
  margin-top: 1.5rem;
}

.vlm-selector-label {
  display: block;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.4rem;
}

.vlm-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.vlm-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.6rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.vlm-chip:hover {
  background: rgba(255, 255, 255, 0.08);
}

.vlm-chip.active {
  background: rgba(76, 175, 80, 0.15);
  border-color: rgba(76, 175, 80, 0.4);
}

.vlm-chip-input {
  display: none;
}

.vlm-chip-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.7);
  white-space: nowrap;
}

.vlm-chip.active .vlm-chip-label {
  color: rgba(255, 255, 255, 0.9);
}


/* Results Grid — columns set dynamically via :style binding */
.results-grid {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.result-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 0.75rem;
  transition: border-color 0.2s ease;
}

.result-card.is-active {
  border-color: rgba(76, 175, 80, 0.3);
}

.result-card.is-waiting {
  opacity: 0.4;
}

.result-card.is-error {
  border-color: rgba(244, 67, 54, 0.2);
}

.result-card:hover {
  border-color: rgba(255, 255, 255, 0.15);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.result-model {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.result-latency {
  margin-left: auto;
  font-size: 0.7rem;
  color: rgba(76, 175, 80, 0.7);
  font-variant-numeric: tabular-nums;
}

.result-status {
  margin-left: auto;
}

.result-status.waiting {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.25);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.typing-dots span {
  animation: typing 1.2s infinite;
  font-size: 1.2rem;
  color: rgba(255, 255, 255, 0.4);
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

.result-text {
  font-size: 0.78rem;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.7);
  white-space: pre-wrap;
}

.result-error {
  font-size: 0.78rem;
  color: rgba(244, 67, 54, 0.8);
}

/* Responsive */
@media (max-width: 900px) {
  .compare-page {
    flex-direction: column;
  }

  .compare-chat-panel {
    width: 100%;
    position: static;
    max-height: 400px;
  }
}

@media (max-width: 600px) {
  .results-grid {
    grid-template-columns: 1fr !important;
  }

  .compare-page {
    padding: 0.5rem;
  }
}
</style>
