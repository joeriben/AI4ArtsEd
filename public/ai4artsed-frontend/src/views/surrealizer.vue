<template>
  <div class="direct-view">
    <!-- Main Content -->
    <div class="main-container">
      <!-- Info Box -->
      <div class="info-box" :class="{ 'expanded': infoExpanded }">
        <div class="info-header" @click="infoExpanded = !infoExpanded">
          <span class="info-icon">ℹ️</span>
          <span class="info-title">{{ t('surrealizer.infoTitle') }}</span>
          <span class="info-toggle">{{ infoExpanded ? '▲' : '▼' }}</span>
        </div>
        <div v-if="infoExpanded" class="info-content">
          <p>{{ t('surrealizer.infoDescription') }}</p>
          <div class="info-purpose">
            <strong>{{ t('surrealizer.purposeTitle') }}</strong>
            <p>{{ t('surrealizer.purposeText') }}</p>
          </div>
          <div class="info-tech">
            <strong>{{ t('surrealizer.techTitle') }}</strong>
            <p class="tech-text">{{ t('surrealizer.techText') }}</p>
          </div>
        </div>
      </div>

      <!-- Input Section -->
      <section class="input-section">
        <MediaInputBox
          icon="💡"
          label="Dein Input"
          placeholder="Beschreibe deine Idee..."
          v-model:value="inputText"
          input-type="text"
          :rows="6"
          @copy="copyInputText"
          @paste="pasteInputText"
          @clear="clearInputText"
        />

        <!-- T5 Prompt Expansion Toggle (directly under input) -->
        <div class="expand-toggle-row">
          <label class="expand-toggle" :class="{ suggest: isShortPrompt && !expandPrompt }">
            <input type="checkbox" v-model="expandPrompt" />
            <span class="expand-toggle-label">{{ t('surrealizer.expandLabel') }}</span>
          </label>
          <div v-if="isShortPrompt && !expandPrompt" class="expand-suggest">
            {{ t('surrealizer.expandSuggest') }}
          </div>
          <div v-else-if="expandPrompt && isShortPrompt" class="expand-hint">
            {{ t('surrealizer.expandHint', { count: estimatedTokens }) }}
          </div>
        </div>

        <!-- T5 Expansion Result (shown after generation) -->
        <div v-if="expandedT5Text" class="expand-result-box">
          <div class="expand-result-header">
            <span class="expand-result-icon">T5</span>
            <span class="expand-result-label">{{ t('surrealizer.expandResultLabel') }}</span>
          </div>
          <div class="expand-result-text">{{ expandedT5Text }}</div>
        </div>

        <!-- Extrapolation Slider -->
        <div class="section-card">
          <div class="card-header">
            <span class="card-icon">🎚️</span>
            <span class="card-label">{{ t('surrealizer.sliderLabel') }}</span>
          </div>
          <div class="slider-container">
            <div class="slider-labels">
              <span class="slider-label-left">{{ t('surrealizer.sliderExtremeWeird') }}</span>
              <span class="slider-label-mid-left">{{ t('surrealizer.sliderWeird') }}</span>
              <span class="slider-label-center">{{ t('surrealizer.sliderNormal') }}</span>
              <span class="slider-label-mid-right">{{ t('surrealizer.sliderCrazy') }}</span>
              <span class="slider-label-right">{{ t('surrealizer.sliderExtremeCrazy') }}</span>
            </div>
            <div class="slider-wrapper">
              <input
                type="range"
                min="-75"
                max="75"
                step="0.1"
                v-model.number="alphaFaktor"
                class="slider"
              />
            </div>
            <div class="slider-value">α = {{ alphaFaktor }}</div>
            <div class="slider-hint">{{ t('surrealizer.sliderHint') }}</div>
          </div>
        </div>

        <!-- Fusion Strategy (central control) -->
        <div class="section-card">
          <div class="card-header">
            <span class="card-icon">🔬</span>
            <span class="card-label">{{ t('surrealizer.fusionStrategyLabel') }}</span>
          </div>
          <div class="strategy-selector">
            <button
              v-for="s in strategies"
              :key="s.value"
              class="strategy-button"
              :class="{ active: fusionStrategy === s.value }"
              @click="fusionStrategy = s.value"
            >
              {{ t('surrealizer.fusion_' + s.value) }}
            </button>
          </div>
          <div class="strategy-description">{{ t('surrealizer.fusionHint_' + fusionStrategy) }}</div>
        </div>

        <!-- Advanced Settings (collapsible) -->
        <details class="advanced-settings">
          <summary>{{ t('surrealizer.advancedLabel') }}</summary>
          <div class="settings-grid">
            <label>
              {{ t('surrealizer.negativeLabel') }}
              <input v-model="negativePrompt" type="text" class="setting-input" />
            </label>
            <label>
              {{ t('surrealizer.cfgLabel') }}
              <input v-model.number="cfgScale" type="number" min="1" max="15" step="0.1" class="setting-input setting-small" />
            </label>
            <label>
              {{ t('surrealizer.seedLabel') }}
              <input v-model="seedInputText" type="text" inputmode="numeric" class="setting-input setting-small" placeholder="-1" />
              <span class="setting-hint">{{ t('surrealizer.seedHint') }}</span>
            </label>
          </div>
        </details>

        <!-- Execute Button -->
        <GenerationButton
          :disabled="!inputText.trim()"
          :executing="isExecuting"
          :label="t('surrealizer.executeButton')"
          :executing-label="isExpanding ? t('surrealizer.expandActive') : t('surrealizer.executingButton')"
          :error-message="generationErrorMessage"
          :show-arrows="true"
          @click="executeWorkflow"
        />
      </section>

      <!-- Output Section -->
      <section class="output-section">
        <MediaOutputBox
          ref="pipelineSectionRef"
          :output-image="primaryOutput?.url || null"
          media-type="image"
          :is-executing="isExecuting"
          :progress="generationProgress"
          :is-analyzing="isAnalyzing"
          :show-analysis="showAnalysis"
          :analysis-data="imageAnalysis"
          :run-id="currentRunId"
          :is-favorited="isFavorited"
          forward-button-title="Weiterreichen zu Bild-Transformation"
          @save="saveMedia"
          @print="printImage"
          @forward="sendToI2I"
          @download="downloadMedia"
          @analyze="analyzeImage"
          @image-click="showImageFullscreen"
          @close-analysis="showAnalysis = false"
          @toggle-favorite="toggleFavorite"
        />
      </section>
    </div>

    <!-- Fullscreen Image Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="fullscreenImage" class="fullscreen-modal" @click="fullscreenImage = null">
          <img :src="fullscreenImage" alt="Fullscreen" class="fullscreen-image" />
          <button class="close-fullscreen" @click="fullscreenImage = null">×</button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import SpriteProgressAnimation from '@/components/SpriteProgressAnimation.vue'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useDeviceId } from '@/composables/useDeviceId'
import { usePageContextStore } from '@/stores/pageContext'
import { useFavoritesStore } from '@/stores/favorites'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

// ============================================================================
// i18n
// ============================================================================

const { t } = useI18n()

// ============================================================================
// Types
// ============================================================================

interface OutputConfig {
  id: string
  label: string
}

interface WorkflowOutput {
  type: 'image' | 'text' | 'json' | 'unknown'
  filename: string
  url?: string
  content?: string
}

// ============================================================================
// STATE
// ============================================================================

// Info box expansion state
const infoExpanded = ref(false)

// Global clipboard
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord, isRecording, recordCount } = useLatentLabRecorder('surrealizer')

// Router for navigation
const router = useRouter()

// Favorites support
const favoritesStore = useFavoritesStore()
const deviceId = useDeviceId()
const currentRunId = ref<string | null>(null)
const isFavorited = computed(() => currentRunId.value ? favoritesStore.isFavorited(currentRunId.value) : false)

const inputText = ref('')
const alphaFaktor = ref<number>(0)  // Slider (-75 to +75), default 0 = normal/balanced
const fusionStrategy = ref<string>('dual_alpha')  // 'legacy', 'dual_alpha', 'normalized'
const strategies = [
  { value: 'dual_alpha' },
  { value: 'normalized' },
  { value: 'legacy' },
] as const
const isExecuting = ref(false)
const generationErrorMessage = ref('')
const outputs = ref<WorkflowOutput[]>([])
const fullscreenImage = ref<string | null>(null)
const generationProgress = ref(0)
const primaryOutput = ref<WorkflowOutput | null>(null)

// Seed management: stable when any parameter changes, new seed on repeated identical run
const previousPrompt = ref('')
const previousAlpha = ref<number>(0)
const previousCfg = ref<number>(5.5)
const previousNegative = ref('watermark')
const currentSeed = ref<number | null>(null)

// Advanced settings
const negativePrompt = ref('watermark')
const cfgScale = ref(5.5)
const seedInputText = ref('-1')  // Text-based to avoid number spinner
const seedInput = computed(() => {
  const n = parseInt(seedInputText.value)
  return isNaN(n) ? -1 : n
})
// T5 prompt expansion
const expandPrompt = ref(false)
const expandedT5Text = ref('')
const isExpanding = ref(false)  // True only during an active LLM expansion call

// Image analysis state (for Stage 5)
const isAnalyzing = ref(false)
const imageAnalysis = ref<{
  analysis: string
  reflection_prompts: string[]
  insights: string[]
  success: boolean
} | null>(null)
const showAnalysis = ref(false)

// Session persistence — restore on mount
onMounted(() => {
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  if (s('lat_lab_ef_prompt')) inputText.value = s('lat_lab_ef_prompt')!
  if (s('lat_lab_ef_alpha')) alphaFaktor.value = parseFloat(s('lat_lab_ef_alpha')!) || 0
  if (s('lat_lab_ef_negative')) negativePrompt.value = s('lat_lab_ef_negative')!
  if (s('lat_lab_ef_cfg')) cfgScale.value = parseFloat(s('lat_lab_ef_cfg')!) || 5.5
  if (s('lat_lab_ef_expand')) expandPrompt.value = s('lat_lab_ef_expand') === 'true'
  if (s('lat_lab_ef_fusion')) fusionStrategy.value = s('lat_lab_ef_fusion')!
  if (s('lat_lab_ef_seed')) seedInputText.value = s('lat_lab_ef_seed')!
})

// Session persistence — save on change
watch(inputText, v => sessionStorage.setItem('lat_lab_ef_prompt', v))
watch([alphaFaktor, negativePrompt, cfgScale, expandPrompt, fusionStrategy, seedInputText], () => {
  sessionStorage.setItem('lat_lab_ef_alpha', String(alphaFaktor.value))
  sessionStorage.setItem('lat_lab_ef_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_ef_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_ef_expand', String(expandPrompt.value))
  sessionStorage.setItem('lat_lab_ef_fusion', fusionStrategy.value)
  sessionStorage.setItem('lat_lab_ef_seed', seedInputText.value)
})

// Page Context for Träshy (Session 133)
const pageContextStore = usePageContextStore()

const trashyFocusHint = computed<FocusHint>(() => {
  // During/after execution: bottom-right
  if (isExecuting.value || primaryOutput.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  // Default: bottom-left
  return { x: 2, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'surrealizer',
  pageContent: {
    inputText: inputText.value
  },
  focusHint: trashyFocusHint.value
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onUnmounted(() => {
  pageContextStore.clearContext()
})

// ============================================================================
// Computed
// ============================================================================

const canExecute = computed(() => {
  return inputText.value.trim().length > 0 && !isExecuting.value
})

const wordCount = computed(() => inputText.value.trim().split(/\s+/).filter(w => w).length)
const estimatedTokens = computed(() => Math.round(wordCount.value * 1.3))
const isShortPrompt = computed(() => wordCount.value > 0 && wordCount.value < 40)

const hasOutputs = computed(() => {
  return outputs.value.length > 0
})

// Slider percentage for CSS variable (0-100%)
// Map -75 to 0%, 0 to 50%, +75 to 100%
const alphaPercentage = computed(() => {
  return ((alphaFaktor.value + 75) / 150) * 100
})

// Alpha value is used directly (no mapping needed)
// Slider range: -75 (weird/CLIP) to 0 (normal/balanced) to +75 (crazy/T5)
const mappedAlpha = computed(() => {
  return alphaFaktor.value
})

// ============================================================================
// Methods
// ============================================================================

async function executeWorkflow() {
  if (!canExecute.value) return

  isExecuting.value = true
  outputs.value = []
  primaryOutput.value = null
  generationProgress.value = 0
  generationErrorMessage.value = ''

  // Only expand if: checkbox on AND (no existing expansion OR prompt changed)
  const promptChanged = inputText.value !== previousPrompt.value
  const needsExpansion = expandPrompt.value && (!expandedT5Text.value || promptChanged)
  isExpanding.value = needsExpansion

  // Progress simulation (60s base + 10s if expanding prompt)
  const durationSeconds = (needsExpansion ? 70 : 60) * 0.9
  const targetProgress = 98
  const updateInterval = 100
  const totalUpdates = (durationSeconds * 1000) / updateInterval
  const progressPerUpdate = targetProgress / totalUpdates

  const progressInterval = setInterval(() => {
    if (generationProgress.value < targetProgress) {
      generationProgress.value += progressPerUpdate
      if (generationProgress.value > targetProgress) {
        generationProgress.value = targetProgress
      }
    }
  }, updateInterval)

  try {
    // Seed logic: fixed seed from user OR auto-seed (keep on param change, new on repeat)
    if (seedInput.value >= 0) {
      // User specified a fixed seed
      currentSeed.value = seedInput.value
      console.log('[Seed Logic] Fixed seed from user:', currentSeed.value)
    } else {
      const promptChanged = inputText.value !== previousPrompt.value
      const alphaChanged = alphaFaktor.value !== previousAlpha.value
      const cfgChanged = cfgScale.value !== previousCfg.value
      const negativeChanged = negativePrompt.value !== previousNegative.value

      if (currentSeed.value === null) {
        currentSeed.value = Math.floor(Math.random() * 2147483647)
        console.log('[Seed Logic] First run → seed:', currentSeed.value)
      } else if (promptChanged || alphaChanged || cfgChanged || negativeChanged) {
        console.log('[Seed Logic] Parameter changed → keeping seed:', currentSeed.value)
      } else {
        currentSeed.value = Math.floor(Math.random() * 2147483647)
        console.log('[Seed Logic] No changes → new seed:', currentSeed.value)
      }
    }
    previousPrompt.value = inputText.value
    previousAlpha.value = alphaFaktor.value
    previousCfg.value = cfgScale.value
    previousNegative.value = negativePrompt.value

    // Lab Architecture: /legacy = Stage 1 (Safety) + Direct ComfyUI workflow
    // No Stage 2/3 needed - legacy workflows handle prompt directly
    const response = await axios.post('/api/schema/pipeline/legacy', {
      prompt: inputText.value,
      output_config: 'surrealization_diffusers',
      alpha_factor: mappedAlpha.value,
      seed: currentSeed.value,
      expand_prompt: needsExpansion,
      negative_prompt: negativePrompt.value,
      cfg: cfgScale.value,
      fusion_strategy: fusionStrategy.value
    })

    if (response.data.status === 'success') {
      // Capture T5 expansion text if returned
      if (response.data.t5_expansion) {
        expandedT5Text.value = response.data.t5_expansion
      }

      // Get run_id to fetch all entities
      const runId = response.data.run_id

      if (runId) {
        currentRunId.value = runId
        clearInterval(progressInterval)
        generationProgress.value = 100

        // Fetch all entities from pipeline recorder
        await fetchAllOutputs(runId)

        // Set primary output (first image)
        const imageOutput = outputs.value.find(o => o.type === 'image')
        if (imageOutput) {
          primaryOutput.value = imageOutput
        }

        // Record for research export (image already saved by pipeline recorder)
        labRecord({
          parameters: {
            prompt: inputText.value, alpha_factor: mappedAlpha.value,
            seed: currentSeed.value, expand_prompt: expandPrompt.value,
            negative_prompt: negativePrompt.value, cfg: cfgScale.value,
            fusion_strategy: fusionStrategy.value,
          },
          results: { run_id: runId, t5_expansion: expandedT5Text.value || null },
        })
      } else {
        clearInterval(progressInterval)
        console.error('[Direct] No run_id in response')
        generationErrorMessage.value = t('generationError.unknown')
      }
    } else {
      clearInterval(progressInterval)
      const msg = response.data.error || ''
      if (/queue full/i.test(msg)) generationErrorMessage.value = t('generationError.busy')
      else if (/not available|not reachable/i.test(msg)) generationErrorMessage.value = t('generationError.offline')
      else generationErrorMessage.value = t('generationError.unknown')
    }
  } catch (error: any) {
    clearInterval(progressInterval)
    console.error('[Direct] Execution error:', error)
    const errorMsg = error.response?.data?.error || error.message || ''
    if (/queue full/i.test(errorMsg)) generationErrorMessage.value = t('generationError.busy')
    else if (/not available|not reachable/i.test(errorMsg)) generationErrorMessage.value = t('generationError.offline')
    else generationErrorMessage.value = t('generationError.unknown')
  } finally {
    isExecuting.value = false
    isExpanding.value = false
  }
}

async function fetchAllOutputs(runId: string) {
  try {
    // Fetch entities metadata
    const entitiesResponse = await axios.get(`/api/pipeline/${runId}/entities`)
    const entities = entitiesResponse.data.entities || []

    console.log('[Direct] Entities:', entities)

    // Process each entity and add to outputs
    for (const entity of entities) {
      const output = await processEntity(runId, entity)
      if (output) {
        outputs.value.push(output)
      }
    }
  } catch (error: any) {
    console.error('[Direct] Error fetching outputs:', error)
  }
}

async function processEntity(runId: string, entity: any): Promise<WorkflowOutput | null> {
  try {
    const entityType = entity.type
    const filename = entity.filename

    // FAILSAFE: Only show final outputs (entities with prefix 'output_')
    // This filters out all intermediate results:
    // - config_used, input, stage1_output, interception, safety, safety_pre_output, etc.
    if (!entityType.startsWith('output_')) {
      return null
    }

    // Fetch entity content
    const response = await axios.get(`/api/pipeline/${runId}/entity/${entityType}`, {
      responseType: 'blob' // Get as blob to handle binary data
    })

    const contentType = response.headers['content-type']

    // Determine output type from content-type
    if (contentType.startsWith('image/')) {
      // Image output
      const url = URL.createObjectURL(response.data)
      return {
        type: 'image',
        filename,
        url
      }
    } else if (contentType.includes('application/json')) {
      // JSON output
      const text = await response.data.text()
      return {
        type: 'json',
        filename,
        content: text
      }
    } else if (contentType.includes('text/')) {
      // Text output
      const text = await response.data.text()
      return {
        type: 'text',
        filename,
        content: text
      }
    } else {
      // Unknown type
      return {
        type: 'unknown',
        filename
      }
    }
  } catch (error: any) {
    console.error(`[Direct] Error processing entity:`, error)
    return null
  }
}

function formatJSON(jsonString: string): string {
  try {
    const obj = JSON.parse(jsonString)
    return JSON.stringify(obj, null, 2)
  } catch {
    return jsonString
  }
}

function showImageFullscreen(imageUrl: string) {
  fullscreenImage.value = imageUrl
}

// ============================================================================
// Textbox Actions (Copy/Paste/Delete)
// ============================================================================

function copyInputText() {
  copyToClipboard(inputText.value)
  console.log('[Direct] Input copied to clipboard')
}

function pasteInputText() {
  inputText.value = pasteFromClipboard()
  console.log('[Direct] Text pasted from clipboard')
}

function clearInputText() {
  inputText.value = ''
  sessionStorage.removeItem('lat_lab_ef_prompt')
  console.log('[Direct] Input cleared')
}

// ============================================================================
// Media Actions (Universal for all media types)
// ============================================================================

async function toggleFavorite() {
  if (!currentRunId.value) return
  await favoritesStore.toggleFavorite(currentRunId.value, 'image', deviceId, 'anonymous', 'surrealizer')
}

function saveMedia() {
  // TODO: Implement save/bookmark feature for all media types
  console.log('[Media Actions] Save media (not yet implemented)')
  alert('Merken-Funktion kommt bald!')
}

function printImage() {
  if (!primaryOutput.value?.url) return

  // Open image in new window and print
  const printWindow = window.open(primaryOutput.value.url, '_blank')
  if (printWindow) {
    printWindow.onload = () => {
      printWindow.print()
    }
  }
}

function sendToI2I() {
  if (!primaryOutput.value?.url || primaryOutput.value.type !== 'image') return

  // Extract run_id from URL: /api/media/image/run_123 -> run_123
  const runIdMatch = primaryOutput.value.url.match(/\/api\/.*\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : null

  // Store image data in localStorage for cross-component transfer
  const transferData = {
    imageUrl: primaryOutput.value.url,  // For display
    runId: runId,  // For backend reference
    timestamp: Date.now()
  }

  localStorage.setItem('i2i_transfer_data', JSON.stringify(transferData))

  console.log('[Image Actions] Transferring to i2i:', transferData)

  // Navigate to image transformation
  router.push('/image-transformation')
}

async function downloadMedia() {
  if (!primaryOutput.value?.url || !primaryOutput.value.type) return

  try {
    // Extract run_id from URL: /api/media/{type}/{run_id}
    const runIdMatch = primaryOutput.value.url.match(/\/api\/.*\/(.+)$/)
    const runId = runIdMatch ? runIdMatch[1] : 'media'

    // Determine file extension based on media type
    const extensions: Record<string, string> = {
      'image': 'png',
      'audio': 'mp3',
      'video': 'mp4',
      'music': 'mp3',
      'code': 'js',
      '3d': 'glb'
    }
    const ext = extensions[primaryOutput.value.type] || 'bin'
    const filename = `ai4artsed_${runId}.${ext}`

    // Fetch and download
    const response = await fetch(primaryOutput.value.url)
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)

    console.log('[Download] Media downloaded:', filename)

  } catch (error) {
    console.error('[Download] Error:', error)
    alert('Download fehlgeschlagen. Bitte versuche es erneut.')
  }
}

// ============================================================================
// Stage 5: Image Analysis (Pedagogical Reflection)
// ============================================================================

async function analyzeImage() {
  if (!primaryOutput.value?.url || primaryOutput.value.type !== 'image') {
    console.warn('[Stage 5] Can only analyze images')
    return
  }

  // Extract run_id from URL: /api/media/image/run_abc123
  const runIdMatch = primaryOutput.value.url.match(/\/api\/.*\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : null

  if (!runId) {
    alert('Error: Cannot determine image ID')
    return
  }

  isAnalyzing.value = true
  imageAnalysis.value = null
  console.log('[Stage 5] Starting image analysis for run_id:', runId)

  try {
    // NEW: Call universal image analysis endpoint
    const response = await fetch('/api/image/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_id: runId,
        analysis_type: 'bildwissenschaftlich'  // Default: Panofsky framework
        // Can be changed to: bildungstheoretisch, ethisch, kritisch
        // No prompt parameter = uses default from config.py
      })
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || `HTTP ${response.status}`)
    }

    const data = await response.json()

    if (data.success && data.analysis) {
      // Parse analysis text into structured format
      imageAnalysis.value = {
        analysis: data.analysis,
        reflection_prompts: extractReflectionPrompts(data.analysis),
        insights: extractInsights(data.analysis),
        success: true
      }
      showAnalysis.value = true
      console.log('[Stage 5] Analysis complete')
    } else {
      throw new Error(data.error || 'Unknown error')
    }

  } catch (error: any) {
    console.error('[Stage 5] Error:', error)
    alert(`Image analysis failed: ${error.message || error}`)
  } finally {
    isAnalyzing.value = false
  }
}

// Helper functions for parsing analysis text
function extractReflectionPrompts(analysisText: string): string[] {
  const match = analysisText.match(/REFLEXIONSFRAGEN:|REFLECTION QUESTIONS:([\s\S]*?)(?:\n\n|$)/i)
  if (match && match[1]) {
    return match[1]
      .split('\n')
      .filter(line => line.trim().startsWith('-'))
      .map(line => line.replace(/^-\s*/, '').trim())
      .filter(q => q.length > 0)
  }
  return []
}

function extractInsights(analysisText: string): string[] {
  const keywords = ['Komposition', 'Farbe', 'Licht', 'Perspektive', 'Stil',
                   'Composition', 'Color', 'Light', 'Perspective', 'Style']
  return keywords.filter(kw =>
    analysisText.toLowerCase().includes(kw.toLowerCase())
  )
}

// ============================================================================
// Restore from Favorites
// ============================================================================

watch(() => favoritesStore.pendingRestoreData, (restoreData) => {
  if (!restoreData) return

  console.log('[Surrealizer Restore] Processing:', Object.keys(restoreData))

  if (restoreData.input_text) {
    inputText.value = restoreData.input_text
  }

  // Restore surrealizer-specific parameters from current_state
  const state = restoreData.current_state || {}
  if (state.alpha_factor !== undefined) alphaFaktor.value = Number(state.alpha_factor)
  if (state.negative_prompt !== undefined) negativePrompt.value = String(state.negative_prompt)
  if (state.cfg !== undefined) cfgScale.value = Number(state.cfg)
  if (state.fusion_strategy !== undefined) fusionStrategy.value = String(state.fusion_strategy)

  favoritesStore.setRestoreData(null)
}, { immediate: true })
</script>

<style scoped>
/* ============================================================================
   Root Container
   ============================================================================ */

.direct-view {
  min-height: 100vh;
  background: #0a0a0a;
  color: #ffffff;
  display: flex;
  flex-direction: column;
}

/* ============================================================================
   Main Container
   ============================================================================ */

.main-container {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* ============================================================================
   Sections
   ============================================================================ */

.input-section,
.output-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.section-card {
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  padding: 1.5rem;
  transition: all 0.3s ease;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.card-icon {
  font-size: 1.5rem;
}

.card-label {
  font-size: 1.1rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.bubble-actions {
  display: flex;
  gap: 0.25rem;
  margin-left: auto;
}

.bubble-actions .action-btn {
  background: transparent;
  border: none;
  font-size: 0.9rem;
  opacity: 0.4;
  cursor: pointer;
  transition: opacity 0.2s;
  padding: 0.25rem;
}

.bubble-actions .action-btn:hover {
  opacity: 0.8;
}

/* ============================================================================
   Input Elements
   ============================================================================ */

.input-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: 1rem;
  padding: 0.75rem;
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
  min-height: 150px;
}

.input-textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(0, 0, 0, 0.4);
}

.config-select {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: 1rem;
  padding: 0.75rem;
  cursor: pointer;
  font-family: inherit;
}

.config-select:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
}

/* ============================================================================
   Slider
   ============================================================================ */

.slider-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.slider-label-left {
  color: rgba(147, 51, 234, 0.9); /* Purple for "very weird" */
}

.slider-label-mid-left {
  color: rgba(120, 80, 240, 0.8); /* Purple-Blue for "weird" */
  font-size: 0.9rem;
  font-weight: 500;
}

.slider-label-center {
  color: rgba(59, 130, 246, 0.9); /* Blue for "normal" */
  font-weight: 700;
}

.slider-label-mid-right {
  color: rgba(180, 100, 200, 0.8); /* Blue-Pink for "crazy" */
  font-size: 0.9rem;
  font-weight: 500;
}

.slider-label-right {
  color: rgba(236, 72, 153, 0.9); /* Pink for "really crazy" */
}

.slider-wrapper {
  width: 100%;
  padding: 0.5rem 0;
}

.slider {
  width: 100%;
  -webkit-appearance: none;
  appearance: none;
  height: 16px; /* Double thickness */
  background: linear-gradient(
    to right,
    rgba(147, 51, 234, 0.6) 0%,    /* Purple (weird) */
    rgba(59, 130, 246, 0.6) 50%,   /* Blue (normal) */
    rgba(236, 72, 153, 0.6) 100%   /* Pink (crazy) */
  );
  border-radius: 8px;
  outline: none;
  transition: all 0.3s ease;
  cursor: pointer;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(99, 102, 241, 0.95));
  cursor: grab;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  transition: all 0.3s ease;
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.6);
  cursor: grabbing;
}

.slider::-webkit-slider-thumb:active {
  cursor: grabbing;
  transform: scale(1.05);
}

.slider::-moz-range-thumb {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(99, 102, 241, 0.95));
  cursor: grab;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  transition: all 0.3s ease;
}

.slider::-moz-range-thumb:hover {
  transform: scale(1.15);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.6);
  cursor: grabbing;
}

.slider::-moz-range-thumb:active {
  cursor: grabbing;
  transform: scale(1.05);
}

/* Value display centered below slider */
.slider-value {
  text-align: center;
  font-size: 1.5rem;
  font-weight: 700;
  color: rgba(59, 130, 246, 0.95); /* Blue color matching thumb */
  margin-top: 0.5rem;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

/* Algorithm hint below slider value */
.slider-hint {
  text-align: center;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 0.25rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  line-height: 1.4;
}

.setting-hint {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 0.25rem;
  line-height: 1.4;
}

/* ============================================================================
   Strategy Selector
   ============================================================================ */

.strategy-selector {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.strategy-button {
  flex: 1;
  padding: 0.6rem 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.strategy-button:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}

.strategy-button.active {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.5);
  color: rgba(59, 130, 246, 0.95);
  font-weight: 600;
}

.strategy-description {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.5;
}

/* ============================================================================
   Advanced Settings (Latent Lab Standard)
   ============================================================================ */

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

/* ============================================================================
   T5 Expand Toggle
   ============================================================================ */

.expand-toggle-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.expand-toggle {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  padding: 0.75rem 1rem;
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.expand-toggle:hover {
  border-color: rgba(102, 126, 234, 0.4);
}

.expand-toggle.suggest {
  border-color: rgba(102, 126, 234, 0.45);
  animation: suggest-pulse 2.5s ease-in-out infinite;
}

@keyframes suggest-pulse {
  0%, 100% { border-color: rgba(102, 126, 234, 0.45); box-shadow: 0 0 0 0 rgba(102, 126, 234, 0); }
  50% { border-color: rgba(102, 126, 234, 0.7); box-shadow: 0 0 8px 0 rgba(102, 126, 234, 0.15); }
}

.expand-toggle input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #667eea;
  cursor: pointer;
}

.expand-toggle-label {
  font-size: 0.95rem;
  color: rgba(255, 255, 255, 0.8);
}

.expand-suggest {
  font-size: 0.78rem;
  color: rgba(102, 126, 234, 0.7);
  padding: 0 0.25rem;
  line-height: 1.4;
}

.expand-hint {
  font-size: 0.8rem;
  color: rgba(102, 126, 234, 0.8);
  padding: 0.5rem 1rem;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 8px;
  line-height: 1.4;
}

.expand-result-box {
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(102, 126, 234, 0.3);
  border-radius: 12px;
  padding: 1rem 1.25rem;
}

.expand-result-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

.expand-result-icon {
  font-size: 0.7rem;
  font-weight: 700;
  color: rgba(102, 126, 234, 0.95);
  background: rgba(102, 126, 234, 0.15);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.05em;
}

.expand-result-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
}

.expand-result-text {
  font-size: 0.85rem;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.6);
  max-height: 10rem;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(102, 126, 234, 0.3) transparent;
}

/* Execute button styles now in GenerationButton.vue + generation-button.css */

/* ============================================================================
   Fullscreen Modal
   ============================================================================ */

.fullscreen-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.95);
  backdrop-filter: blur(8px);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.fullscreen-image {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
}

.close-fullscreen {
  position: absolute;
  top: 2rem;
  right: 2rem;
  width: 4rem;
  height: 4rem;
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid white;
  color: white;
  font-size: 2.5rem;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.close-fullscreen:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.1);
}

/* ============================================================================
   Transitions
   ============================================================================ */

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* ============================================================================
   Responsive
   ============================================================================ */

@media (max-width: 768px) {
  .main-container {
    padding: 1rem;
  }

  .return-button {
    left: 1rem;
  }

  .page-title {
    font-size: 1.2rem;
  }
}

/* ============================================================================
   Info Box
   ============================================================================ */

.info-box {
  background: rgba(59, 130, 246, 0.1);
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.info-header {
  display: flex;
  align-items: center;
  padding: 1rem 1.5rem;
  cursor: pointer;
  gap: 0.75rem;
}

.info-header:hover {
  background: rgba(59, 130, 246, 0.15);
}

.info-icon {
  font-size: 1.25rem;
}

.info-title {
  flex: 1;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.info-toggle {
  color: rgba(255, 255, 255, 0.5);
}

.info-content {
  padding: 0 1.5rem 1.5rem;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
}

.info-purpose {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.info-purpose strong {
  color: rgba(255, 255, 255, 0.9);
}

.info-purpose p {
  margin: 0;
}

.info-tech {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(102, 126, 234, 0.15);
  border-radius: 8px;
  border-left: 3px solid rgba(102, 126, 234, 0.6);
}

.info-tech strong {
  color: rgba(255, 255, 255, 0.8);
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.85rem;
}

.info-tech .tech-text {
  margin: 0;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.7);
  user-select: all;
}
</style>
