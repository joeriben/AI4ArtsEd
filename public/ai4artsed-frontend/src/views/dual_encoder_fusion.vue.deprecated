<template>
  <div class="text-transformation-view">

    <!-- Header with Return Button -->
    <header class="page-header">
      <button class="return-button" @click="$router.push('/')" title="Zurück zu Phase 1">
        ← Phase 1
      </button>
      <h1 class="page-title">AI4ArtsEd - AI-Lab</h1>
    </header>

    <!-- Single Continuous Flow (no phase transitions) -->
    <div class="phase-2a" ref="mainContainerRef">

        <!-- Section 1: Input + Context (Side by Side) -->
        <section class="input-context-section">
          <!-- Input Bubble -->
          <div class="input-bubble bubble-card" :class="{ filled: inputText }">
            <div class="bubble-header">
              <span class="bubble-icon">💡</span>
              <span class="bubble-label">Deine Idee: Worum soll es gehen?</span>
            </div>
            <textarea
              v-model="inputText"
              placeholder="Ein Fest in meiner Straße: ..."
              class="bubble-textarea"
              rows="6"
            ></textarea>
          </div>

          <!-- Context Bubble -->
          <div class="context-bubble bubble-card" :class="{ filled: contextPrompt, required: !contextPrompt }">
            <div class="bubble-header">
              <span class="bubble-icon">📋</span>
              <span class="bubble-label">Bestimme Regeln, Material, Besonderheiten</span>
            </div>
            <textarea
              v-model="contextPrompt"
              @input="handleContextPromptEdit"
              placeholder="Beschreibe alles so, wie es die Vögel auf den Bäumen wahrnehmen!"
              class="bubble-textarea"
              rows="6"
            ></textarea>
          </div>
        </section>

        <!-- START BUTTON #1: Trigger Interception (Between Context and Interception) -->
        <div class="start-button-container">
          <button
            class="start-button"
            :class="{ disabled: !inputText }"
            :disabled="!inputText"
            @click="runInterception()"
          >
            <span class="button-arrows button-arrows-left">>>></span>
            <span class="button-text">Start</span>
            <span class="button-arrows button-arrows-right">>>></span>
          </button>
        </div>

        <!-- Section 3: Interception Preview (filled after Start #1) -->
        <section class="interception-section">
          <div class="interception-preview bubble-card" :class="{ empty: !interceptionResult, loading: isInterceptionLoading }">
            <div class="bubble-header">
              <span class="bubble-icon">→</span>
              <span class="bubble-label">Idee + Regeln = Prompt</span>
            </div>
            <div v-if="isInterceptionLoading" class="preview-loading">
              <div class="spinner-large"></div>
              <p class="loading-text">Die KI kombiniert jetzt deine Idee mit den Regeln und erstellt einen kreativen Prompt, der zu deinem gewählten Kunststil passt.</p>
            </div>
            <textarea
              v-else
              ref="interceptionTextareaRef"
              v-model="interceptionResult"
              placeholder="Prompt erscheint nach Start-Klick (oder eigenen Text eingeben)"
              class="bubble-textarea auto-resize-textarea"
              rows="5"
            ></textarea>
          </div>
        </section>

        <!-- Section 2: Category Selection (Horizontal Row) - Always visible -->
        <section class="category-section">
          <h2 v-if="executionPhase !== 'initial'" class="section-title">Wähle ein Medium aus</h2>
          <div class="category-bubbles-row">
            <div
              v-for="category in availableCategories"
              :key="category.id"
              class="category-bubble"
              :class="{ selected: selectedCategory === category.id, disabled: category.disabled }"
              :style="{ '--bubble-color': category.color }"
              @click="!category.disabled && selectCategory(category.id)"
              role="button"
              :aria-pressed="selectedCategory === category.id"
              :aria-disabled="category.disabled"
              :tabindex="category.disabled ? -1 : 0"
              @keydown.enter="!category.disabled && selectCategory(category.id)"
              @keydown.space.prevent="!category.disabled && selectCategory(category.id)"
            >
              <div class="bubble-emoji-small">{{ category.emoji }}</div>
            </div>
          </div>
        </section>

        <!-- Section 2.5: Model Selection (Shows DIRECTLY under category, disabled until after interception) -->
        <section class="config-section">
          <h2 v-if="selectedCategory" class="section-title">wähle ein KI-Modell aus</h2>
          <div class="config-bubbles-container">
            <div class="config-bubbles-row">
              <div
                v-for="config in configsForCategory"
                :key="config.id"
                class="config-bubble"
                :class="{
                  selected: selectedConfig === config.id,
                  loading: config.id === selectedConfig && isOptimizationLoading,
                  'light-bg': config.lightBg,
                  disabled: !areModelBubblesEnabled
                }"
                :style="{ '--bubble-color': config.color }"
                @click="areModelBubblesEnabled && selectConfig(config.id)"
                role="button"
                :aria-pressed="selectedConfig === config.id"
                :aria-disabled="!areModelBubblesEnabled"
                :tabindex="areModelBubblesEnabled ? 0 : -1"
                @keydown.enter="areModelBubblesEnabled && selectConfig(config.id)"
                @keydown.space.prevent="areModelBubblesEnabled && selectConfig(config.id)"
              >
                <img v-if="config.logo" :src="config.logo" :alt="config.label" class="bubble-logo" />
                <div v-else class="bubble-emoji-medium">{{ config.emoji }}</div>
                <div class="bubble-label-medium">{{ config.label }}</div>
                <div v-if="config.id === selectedConfig && isOptimizationLoading" class="loading-indicator">
                  <div class="spinner"></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Section 4: Optimized Prompt Preview (Only shown if optimization was applied) -->
        <section v-if="hasOptimization" class="optimization-section">
          <div class="optimization-preview bubble-card" :class="{ empty: !optimizedPrompt, loading: isOptimizationLoading }">
            <div class="bubble-header">
              <span class="bubble-icon">✨</span>
              <span class="bubble-label">Modell-Optimierter Prompt</span>
            </div>
            <div v-if="isOptimizationLoading" class="preview-loading">
              <div class="spinner-large"></div>
              <p class="loading-text">Der Prompt wird jetzt für das gewählte KI-Modell angepasst. Jedes Modell versteht Beschreibungen etwas anders – die KI optimiert den Text für die beste Ausgabe.</p>
            </div>
            <textarea
              v-else
              ref="optimizationTextareaRef"
              v-model="optimizedPrompt"
              :placeholder="optimizedPrompt ? '' : 'Der optimierte Prompt erscheint nach Modellauswahl.'"
              class="bubble-textarea auto-resize-textarea"
              rows="5"
              :readonly="!optimizedPrompt"
            ></textarea>
          </div>
        </section>

        <!-- Info: No optimization needed for this model -->
        <div v-if="executionPhase === 'optimization_done' && !hasOptimization && selectedConfig" class="info-bubble">
          <span class="bubble-icon">ℹ️</span>
          <p><strong>{{ selectedConfig }}</strong> benötigt keine Prompt-Optimierung und interpretiert den kreativen Prompt direkt.</p>
        </div>

        <!-- START BUTTON #2: Trigger Generation (Between Optimized Prompt and Output) -->
        <div class="start-button-container">
          <button
            class="start-button"
            :class="{ disabled: (executionPhase !== 'optimization_done' && executionPhase !== 'generation_done') || !optimizedPrompt }"
            :disabled="(executionPhase !== 'optimization_done' && executionPhase !== 'generation_done') || !optimizedPrompt"
            @click="startGeneration()"
            ref="startButtonRef"
          >
            <span class="button-arrows button-arrows-left">>>></span>
            <span class="button-text">Start</span>
            <span class="button-arrows button-arrows-right">>>></span>
          </button>

          <transition name="fade">
            <div v-if="showSafetyApprovedStamp" class="safety-stamp">
              <div class="stamp-inner">
                <div class="stamp-icon">✓</div>
                <div class="stamp-text">Safety<br/>Approved</div>
              </div>
            </div>
          </transition>
        </div>

        <!-- Section 5: Pipeline Path (always visible, inactive until generation starts) -->
        <section class="pipeline-section" ref="pipelineSectionRef">
          <!-- Output Frame (Always visible) -->
          <div class="output-frame" :class="{ empty: !isPipelineExecuting && !outputImage, generating: isPipelineExecuting && !outputImage }">
            <!-- Generation Progress Animation -->
            <div v-if="isPipelineExecuting && !outputImage" class="generation-animation-container">
              <SpriteProgressAnimation :progress="generationProgress" />
            </div>

            <!-- Final Output -->
            <div v-else-if="outputImage" class="final-output">
              <img
                :src="outputImage"
                alt="Generiertes Bild"
                class="output-image"
                @click="showImageFullscreen(outputImage)"
              />
            </div>

            <!-- Placeholder -->
            <div v-else class="output-placeholder">
              <div class="placeholder-icon">🖼️</div>
              <p class="placeholder-text">Dein Bild erscheint hier</p>
            </div>
          </div>
        </section>

      </div>

    <!-- Fullscreen Image Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="fullscreenImage" class="fullscreen-modal" @click="fullscreenImage = null">
          <img :src="fullscreenImage" alt="Dein Bild" class="fullscreen-image" />
          <button class="close-fullscreen" @click="fullscreenImage = null">×</button>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { usePipelineExecutionStore } from '@/stores/pipelineExecution'
import axios from 'axios'
import SpriteProgressAnimation from '@/components/SpriteProgressAnimation.vue'

// ============================================================================
// Types
// ============================================================================

type StageStatus = 'waiting' | 'processing' | 'completed'

interface Category {
  id: string
  label: string
  emoji: string
  color: string
  disabled?: boolean
}

interface Config {
  id: string
  label: string
  emoji: string
  color: string
  description: string
  logo?: string
  lightBg?: boolean
}

interface PipelineStage {
  id: string
  label: string
  emoji: string
  color: string
  status: StageStatus
}

// ============================================================================
// State
// ============================================================================

// Form state
const inputText = ref('')
const contextPrompt = ref('')
const selectedCategory = ref<string | null>(null)
const selectedConfig = ref<string | null>(null)
const interceptionResult = ref('')
const isInterceptionLoading = ref(false)
const optimizedPrompt = ref('')
const isOptimizationLoading = ref(false)
const hasOptimization = ref(false)  // Track if optimization was applied

// Execution phase tracking
// 'initial' -> 'interception_done' -> 'optimization_done' -> 'generation_done'
const executionPhase = ref<'initial' | 'interception_done' | 'optimization_done' | 'generation_done'>('initial')

// Pipeline execution state
const isPipelineExecuting = ref(false)
const outputImage = ref<string | null>(null)
const fullscreenImage = ref<string | null>(null)
const showSafetyApprovedStamp = ref(false)
const generationProgress = ref(0)

// Refs for DOM elements and scrolling
const mainContainerRef = ref<HTMLElement | null>(null)
const startButtonRef = ref<HTMLElement | null>(null)
const pipelineSectionRef = ref<HTMLElement | null>(null)
const interceptionTextareaRef = ref<HTMLTextAreaElement | null>(null)
const optimizationTextareaRef = ref<HTMLTextAreaElement | null>(null)

// ============================================================================
// Data
// ============================================================================

const availableCategories: Category[] = [
  { id: 'image', label: 'Bild', emoji: '🖼️', color: '#4CAF50' },
  { id: 'video', label: 'Video', emoji: '🎬', color: '#9C27B0', disabled: true },
  { id: 'sound', label: 'Sound', emoji: '🔊', color: '#FF9800', disabled: true },
  { id: '3d', label: '3D', emoji: '🧊', color: '#00BCD4', disabled: true }
]

const configsByCategory: Record<string, Config[]> = {
  image: [
    { id: 'sd35_large', label: 'Stable\nDiffusion', emoji: '🎨', color: '#2196F3', description: 'Klassische Bildgenerierung', logo: '/logos/logo_stable_diffusion.png', lightBg: false },
    { id: 'gpt_image_1', label: 'GPT Image', emoji: '🌟', color: '#FFC107', description: 'Moderne KI-Bilder', logo: '/logos/ChatGPT-Logo.png', lightBg: true },
    { id: 'qwen', label: 'Qwen', emoji: '🌸', color: '#9C27B0', description: 'Qwen Vision Model', logo: '/logos/Qwen_logo.png', lightBg: false }
  ],
  video: [],
  sound: [],
  '3d': []
}

const pipelineStages = ref<PipelineStage[]>([
  { id: 'generation', label: 'Bild', emoji: '🎨', color: '#2196F3', status: 'waiting' }
])

// Computed: Pipeline stages with dynamic medium label
const displayPipelineStages = computed(() => {
  const stages = [...pipelineStages.value]

  // Update generation stage label based on selected category
  if (selectedCategory.value && stages[1]) {
    const category = availableCategories.find(c => c.id === selectedCategory.value)
    if (category) {
      stages[1] = {
        ...stages[1],
        label: category.label,
        emoji: category.emoji
      }
    }
  }

  return stages
})

// ============================================================================
// Computed
// ============================================================================

const configsForCategory = computed(() => {
  if (!selectedCategory.value) return []
  return configsByCategory[selectedCategory.value] || []
})

const truncatedInput = computed(() => {
  if (!inputText.value) return ''
  const maxLength = 100
  return inputText.value.length > maxLength
    ? inputText.value.substring(0, maxLength) + '...'
    : inputText.value
})

const truncatedContext = computed(() => {
  if (!contextPrompt.value) return ''
  const maxLength = 100
  return contextPrompt.value.length > maxLength
    ? contextPrompt.value.substring(0, maxLength) + '...'
    : contextPrompt.value
})

const truncatedInterception = computed(() => {
  if (!interceptionResult.value) return ''
  const maxLength = 150
  return interceptionResult.value.length > maxLength
    ? interceptionResult.value.substring(0, maxLength) + '...'
    : interceptionResult.value
})

const canStartPipeline = computed(() => {
  // Phase 1: Before interception - need input and category
  if (executionPhase.value === 'initial') {
    return inputText.value && selectedCategory.value && !isInterceptionLoading.value
  }
  // Phase 2: After optimization - need both prompts and config
  else if (executionPhase.value === 'optimization_done') {
    return interceptionResult.value && optimizedPrompt.value && selectedConfig.value && !isPipelineExecuting.value
  }
  // Otherwise disabled
  return false
})

const areModelBubblesEnabled = computed(() => {
  // Enable when interception result has content (from API or manual entry)
  return interceptionResult.value.trim().length > 0
})

// ============================================================================
// Route handling & Store
// ============================================================================

const route = useRoute()
const pipelineStore = usePipelineExecutionStore()

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(async () => {
  // Check if we're coming from Phase1 with a configId
  const configId = route.params.configId as string

  if (configId) {
    console.log('[Youth Flow] Received configId from Phase1:', configId)

    try {
      // STEP 1: Load config from backend
      await pipelineStore.setConfig(configId)
      console.log('[Youth Flow] Config loaded:', pipelineStore.selectedConfig?.id)

      // STEP 2: Load meta-prompt for German (Youth Flow is German-only)
      await pipelineStore.loadMetaPromptForLanguage('de')
      console.log('[Youth Flow] Meta-prompt loaded:', pipelineStore.metaPrompt?.substring(0, 50))

      // STEP 3: Initialize context prompt
      contextPrompt.value = pipelineStore.metaPrompt || ''

      // STEP 4: Find which category this config belongs to
      let foundCategory: string | null = null
      for (const [categoryId, configs] of Object.entries(configsByCategory)) {
        if (configs.some(config => config.id === configId)) {
          foundCategory = categoryId
          break
        }
      }

      if (foundCategory) {
        console.log('[Youth Flow] Auto-selecting category:', foundCategory, 'and config:', configId)
        selectedCategory.value = foundCategory
        selectedConfig.value = configId
      } else {
        console.warn('[Youth Flow] ConfigId not found in any category:', configId)
      }
    } catch (error) {
      console.error('[Youth Flow] Initialization error:', error)
    }
  }
})

// ============================================================================
// Methods
// ============================================================================

function selectCategory(categoryId: string) {
  selectedCategory.value = categoryId
  selectedConfig.value = null
  // Don't clear interception or optimization results when changing category
}

async function selectConfig(configId: string) {
  // Only allow selection after interception is done
  if (!areModelBubblesEnabled.value || isOptimizationLoading.value) return

  selectedConfig.value = configId

  // Automatically trigger optimization
  await runOptimization()
}

async function runInterception() {
  isInterceptionLoading.value = true

  try {
    // Call 1: Interception WITHOUT output_config
    const response = await axios.post('/api/schema/pipeline/stage2', {
      schema: pipelineStore.selectedConfig?.id || 'overdrive',
      input_text: inputText.value,
      context_prompt: contextPrompt.value || undefined,
      user_language: 'de',
      safety_level: 'youth'
      // NO output_config - this is pure interception
      // NO execution_mode - models come from config.py
    })

    if (response.data.success) {
      // Use interception_result if available (2-phase), otherwise stage2_result (backward compat)
      interceptionResult.value = response.data.interception_result || response.data.stage2_result || ''
      executionPhase.value = 'interception_done'
      console.log('[2-Phase] Interception complete:', interceptionResult.value.substring(0, 60))
    } else {
      alert(`Fehler: ${response.data.error}`)
    }
  } catch (error: any) {
    console.error('[2-Phase] Interception error:', error)
    // Show backend's detailed error message if available, otherwise generic Axios error
    const errorMessage = error.response?.data?.error || error.message
    alert(`Fehler: ${errorMessage}`)
  } finally {
    isInterceptionLoading.value = false
  }
}

async function runOptimization() {
  isOptimizationLoading.value = true

  try {
    // Call 2: Optimization WITH output_config and interception_result
    const response = await axios.post('/api/schema/pipeline/stage2', {
      schema: pipelineStore.selectedConfig?.id || 'overdrive',
      input_text: interceptionResult.value,  // Use interception result as input
      context_prompt: contextPrompt.value || undefined,
      user_language: 'de',
      safety_level: 'youth',
      output_config: selectedConfig.value  // NOW include output_config for optimization
      // NO execution_mode - models come from config.py
    })

    if (response.data.success) {
      // Use optimized_prompt if available (2-phase), otherwise stage2_result (backward compat)
      optimizedPrompt.value = response.data.optimized_prompt || response.data.stage2_result || ''
      hasOptimization.value = response.data.optimization_applied || false  // Track if optimization was applied
      executionPhase.value = 'optimization_done'
      console.log('[2-Phase] Optimization complete:', optimizedPrompt.value.substring(0, 60), '| Optimization applied:', hasOptimization.value)
    } else {
      alert(`Fehler: ${response.data.error}`)
    }
  } catch (error: any) {
    console.error('[2-Phase] Optimization error:', error)
    const errorMessage = error.response?.data?.error || error.message
    alert(`Fehler: ${errorMessage}`)
  } finally {
    isOptimizationLoading.value = false
  }
}

async function startGeneration() {
  // Check if model is selected
  if (!selectedConfig.value) {
    alert('Bitte wähle ein KI-Modell aus')
    return
  }

  isPipelineExecuting.value = true

  // Start pipeline execution (Stage 3-4)
  await executePipeline()
}

async function executePipeline() {
  // Reset UI state for fresh generation
  outputImage.value = ''  // Clear previous image
  showSafetyApprovedStamp.value = false  // Reset safety stamp
  generationProgress.value = 0  // Reset progress

  // Stage 1: Safety check (silent, shows stamp when complete)
  await new Promise(resolve => setTimeout(resolve, 300))
  showSafetyApprovedStamp.value = true

  // Stage 2: Generation with progress simulation

  const progressInterval = setInterval(() => {
    if (generationProgress.value < 85) {
      generationProgress.value += Math.random() * 15
      if (generationProgress.value > 85) {
        generationProgress.value = 85
      }
    }
  }, 500)

  try {
    const response = await axios.post('/api/schema/pipeline/execute', {
      schema: pipelineStore.selectedConfig?.id || 'overdrive',
      input_text: inputText.value,
      interception_result: optimizedPrompt.value,  // Use optimized prompt (not raw interception)
      context_prompt: contextPrompt.value || undefined,
      user_language: 'de',
      safety_level: 'youth',
      output_config: selectedConfig.value
      // NO execution_mode - models come from config.py
    })

    clearInterval(progressInterval)

    if (response.data.status === 'success') {
      // Complete progress
      generationProgress.value = 100

      // Get run_id from response to construct image URL
      const runId = response.data.media_output?.run_id || response.data.run_id
      if (runId) {
        // Use Vite proxy path: /api/media/image/{run_id}
        outputImage.value = `/api/media/image/${runId}`
        executionPhase.value = 'generation_done'
      } else if (response.data.outputs && response.data.outputs.length > 0) {
        // Fallback: use outputs array
        outputImage.value = `http://localhost:17802${response.data.outputs[0]}`
        executionPhase.value = 'generation_done'
      }
    } else {
      alert(`Generation fehlgeschlagen: ${response.data.error}`)
      generationProgress.value = 0
    }
  } catch (error: any) {
    clearInterval(progressInterval)
    console.error('Pipeline error:', error)
    const errorMessage = error.response?.data?.error || error.message
    alert(`Fehler: ${errorMessage}`)
    generationProgress.value = 0
  } finally {
    isPipelineExecuting.value = false
  }
}

function showImageFullscreen(imageUrl: string) {
  fullscreenImage.value = imageUrl
}

function handleContextPromptEdit() {
  pipelineStore.updateMetaPrompt(contextPrompt.value)
  console.log('[Youth Flow] Context prompt edited:', contextPrompt.value.substring(0, 50) + '...')
}

function autoResizeTextarea(textarea: HTMLTextAreaElement | null) {
  if (!textarea) return
  textarea.style.height = 'auto'
  // Add 4px buffer to prevent text cutoff
  textarea.style.height = (textarea.scrollHeight + 4) + 'px'
}

// Watch metaPrompt changes and sync to local state
watch(() => pipelineStore.metaPrompt, (newMetaPrompt) => {
  if (newMetaPrompt !== contextPrompt.value) {
    contextPrompt.value = newMetaPrompt || ''
    console.log('[Youth Flow] Meta-prompt synced from store')
  }
})

// Auto-resize textareas when content changes
watch(interceptionResult, async (newValue) => {
  await nextTick()
  autoResizeTextarea(interceptionTextareaRef.value)

  // Auto-advance phase when manual text is entered
  if (newValue.trim().length > 0 && executionPhase.value === 'initial') {
    executionPhase.value = 'interception_done'
  }
})

watch(optimizedPrompt, async () => {
  await nextTick()
  autoResizeTextarea(optimizationTextareaRef.value)
})
</script>

<style scoped>
/* ============================================================================
   Root Container
   ============================================================================ */

.text-transformation-view {
  position: fixed;
  inset: 0;
  background: #0a0a0a;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* ============================================================================
   Page Header
   ============================================================================ */

.page-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;

  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  padding: clamp(1rem, 2vh, 1.5rem) clamp(1rem, 3vw, 2rem);
  background: rgba(10, 10, 10, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.page-title {
  font-size: clamp(1.2rem, 3vw, 1.5rem);
  font-weight: 700;
  color: #ffffff;
  margin: 0;
  text-align: center;
  letter-spacing: 0.5px;
}

.return-button {
  position: absolute;
  left: clamp(1rem, 3vw, 2rem);

  padding: clamp(0.4rem, 1vw, 0.6rem) clamp(0.8rem, 2vw, 1.2rem);
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  color: #ffffff;
  font-size: clamp(0.85rem, 1.8vw, 0.95rem);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.return-button:hover {
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(102, 126, 234, 0.2);
  transform: translateX(-4px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.return-button:active {
  transform: translateX(-2px) scale(0.98);
}

/* ============================================================================
   Phase 2a: Vertical Flow
   ============================================================================ */

.phase-2a {
  max-width: clamp(320px, 90vw, 1100px);
  max-height: 90vh;
  width: 100%;
  padding: clamp(1rem, 3vw, 2rem);
  padding-top: clamp(5rem, 10vh, 7rem); /* Space for fixed header */

  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(1rem, 3vh, 2rem);

  overflow-y: auto;
  overflow-x: hidden;
}

/* Section Titles */
.section-title {
  font-size: clamp(1rem, 2.5vw, 1.2rem);
  font-weight: 700;
  text-align: center;
  margin: 0 0 1rem 0;
  color: transparent;
  -webkit-text-stroke: 2px #FFB300;
  text-stroke: 2px #FFB300;
  text-shadow: 0 0 10px rgba(255, 179, 0, 0.6),
               0 0 20px rgba(255, 179, 0, 0.4),
               0 0 30px rgba(255, 179, 0, 0.2);
  animation: neon-pulse 2s ease-in-out infinite;
}

@keyframes neon-pulse {
  0%, 100% {
    -webkit-text-stroke: 2px #FFB300;
    text-stroke: 2px #FFB300;
    text-shadow: 0 0 10px rgba(255, 179, 0, 0.6),
                 0 0 20px rgba(255, 179, 0, 0.4),
                 0 0 30px rgba(255, 179, 0, 0.2);
  }
  50% {
    -webkit-text-stroke: 2px #FF8F00;
    text-stroke: 2px #FF8F00;
    text-shadow: 0 0 15px rgba(255, 143, 0, 0.8),
                 0 0 30px rgba(255, 143, 0, 0.5),
                 0 0 45px rgba(255, 143, 0, 0.3);
  }
}

/* ============================================================================
   Section 1: Input + Context (Side by Side)
   ============================================================================ */

.input-context-section {
  display: flex;
  gap: clamp(1rem, 3vw, 2rem);
  width: 100%;
  justify-content: center;
  flex-wrap: wrap;
}

.bubble-card {
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  padding: clamp(1rem, 2.5vw, 1.5rem);
  transition: all 0.3s ease;
}

.bubble-card.filled {
  border-color: rgba(102, 126, 234, 0.6);
  background: rgba(102, 126, 234, 0.1);
}

.bubble-card.required {
  border-color: rgba(255, 193, 7, 0.6);
  background: rgba(255, 193, 7, 0.05);
  animation: pulse-required 2s ease-in-out infinite;
}

@keyframes pulse-required {
  0%, 100% {
    border-color: rgba(255, 193, 7, 0.6);
  }
  50% {
    border-color: rgba(255, 193, 7, 0.9);
  }
}

/* Expanded state for inline editing */
.bubble-card.expanded {
  min-height: clamp(200px, 30vh, 300px);
  z-index: 100;
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(102, 126, 234, 0.05);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Info bubble for no-optimization message */
.info-bubble {
  padding: 1rem 1.5rem;
  margin: 1rem 0;
  background: rgba(102, 126, 234, 0.1);
  border: 2px solid rgba(102, 126, 234, 0.3);
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.info-bubble .bubble-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.info-bubble p {
  margin: 0;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.95rem;
  line-height: 1.5;
}

.input-bubble,
.context-bubble {
  flex: 0 1 480px;
  width: 480px;
}

.bubble-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.bubble-icon {
  font-size: clamp(1.25rem, 3vw, 1.5rem);
  flex-shrink: 0;
}

.bubble-label {
  font-size: clamp(0.9rem, 2vw, 1rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.bubble-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: clamp(0.9rem, 2vw, 1rem);
  padding: clamp(0.5rem, 1.5vw, 0.75rem);
  resize: vertical;
  font-family: inherit;
  line-height: 1.4;
}

.bubble-textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(0, 0, 0, 0.4);
}

.bubble-textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.auto-resize-textarea {
  overflow-y: hidden;
  min-height: clamp(120px, 15vh, 150px);
  max-height: clamp(300px, 40vh, 500px);
  resize: none;
  padding: clamp(0.75rem, 2vw, 1rem) clamp(0.75rem, 2vw, 1rem);
}

/* Expanded textarea (inline editing) - unused, kept for potential future use */
.expanded-textarea {
  width: 100%;
  min-height: clamp(120px, 20vh, 180px);
  background: rgba(0, 0, 0, 0.4);
  border: 2px solid rgba(102, 126, 234, 0.6);
  border-radius: 8px;
  color: white;
  font-size: clamp(0.9rem, 2vw, 1rem);
  padding: clamp(0.75rem, 2vw, 1rem);
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
  transition: all 0.2s ease;
}

.expanded-textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.9);
  background: rgba(0, 0, 0, 0.5);
}

.expanded-textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

/* Context Preview Area */
.preview-area {
  min-height: clamp(60px, 10vh, 80px);
  cursor: pointer;
  padding: clamp(0.5rem, 1.5vw, 0.75rem);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.2);
  transition: background 0.2s ease;
  margin-bottom: 0.75rem;
}

.preview-area:hover {
  background: rgba(0, 0, 0, 0.3);
}

.preview-area.large {
  min-height: clamp(80px, 12vh, 100px);
}

.preview-text {
  color: rgba(255, 255, 255, 0.9);
  font-size: clamp(0.85rem, 1.8vw, 0.95rem);
  line-height: 1.5;
  margin: 0;
}

.placeholder-text {
  color: rgba(255, 255, 255, 0.4);
  font-size: clamp(0.85rem, 1.8vw, 0.95rem);
  font-style: italic;
  margin: 0;
}

/* ============================================================================
   Section 2: Category Bubbles (Horizontal Row)
   ============================================================================ */

.category-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.category-bubbles-row {
  display: flex;
  flex-direction: row;
  gap: clamp(1rem, 2.5vw, 1.5rem);
  justify-content: center;
  flex-wrap: wrap;
}

.category-bubble {
  width: clamp(70px, 12vw, 90px);
  height: clamp(70px, 12vw, 90px);

  display: flex;
  align-items: center;
  justify-content: center;

  background: rgba(30, 30, 30, 0.9);
  border: 3px solid var(--bubble-color, rgba(255, 255, 255, 0.3));
  border-radius: 50%;

  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.category-bubble:hover {
  transform: scale(1.08);
  box-shadow: 0 0 20px var(--bubble-color);
  border-width: 4px;
}

.category-bubble.selected {
  transform: scale(1.15);
  background: var(--bubble-color);
  box-shadow: 0 0 30px var(--bubble-color),
              0 0 60px var(--bubble-color);
  border-color: #ffffff;
}

.category-bubble:focus-visible {
  outline: 3px solid rgba(102, 126, 234, 0.8);
  outline-offset: 4px;
}

.category-bubble:active {
  transform: scale(0.95);
}

.category-bubble.disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
  filter: grayscale(1);
}

.bubble-emoji-small {
  font-size: clamp(2rem, 4.5vw, 2.5rem);
  line-height: 1;
  transition: filter 0.3s ease;
}

.category-bubble.selected .bubble-emoji-small {
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5));
}

/* ============================================================================
   Section 3: Config Bubbles (Horizontal Row Below Categories)
   ============================================================================ */

.config-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.config-bubbles-container {
  width: 100%;
  display: flex;
  justify-content: center;
}

.config-bubbles-row {
  display: inline-flex;
  flex-direction: row;
  gap: clamp(0.75rem, 2vw, 1rem);
  justify-content: center;
  flex-wrap: wrap;
  /* Configs centered below selected category */
  max-width: fit-content;
}

.config-bubble {
  position: relative;
  width: clamp(80px, 12vw, 100px);
  height: clamp(80px, 12vw, 100px);

  display: flex;
  align-items: center;
  justify-content: center;

  background: rgba(30, 30, 30, 0.9);
  border: 3px solid var(--bubble-color, rgba(255, 255, 255, 0.3));
  border-radius: 50%;

  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.config-bubble:hover {
  transform: scale(1.05);
  box-shadow: 0 0 20px var(--bubble-color);
}

.config-bubble.selected {
  transform: scale(1.1);
  background: var(--bubble-color);
  box-shadow: 0 0 30px var(--bubble-color);
  border-color: #ffffff;
}

.config-bubble.loading {
  pointer-events: none;
  opacity: 0.7;
}

.config-bubble.disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
  filter: grayscale(0.8);
}

.bubble-emoji-medium {
  font-size: clamp(2.5rem, 5vw, 3.5rem);
  line-height: 1;
}

.bubble-logo {
  width: clamp(72px, 11vw, 92px);
  height: clamp(72px, 11vw, 92px);
  object-fit: contain;
}

.config-bubble.light-bg {
  background: rgba(255, 255, 255, 0.95);
}

.config-bubble.light-bg .bubble-label-medium {
  color: #0a0a0a;
}

.config-bubble.light-bg.selected {
  background: var(--bubble-color);
}

.config-bubble.light-bg.selected .bubble-label-medium {
  color: #0a0a0a;
}

.bubble-label-medium {
  position: absolute;
  bottom: clamp(6px, 1.2vw, 10px);
  left: 50%;
  transform: translateX(-50%);
  width: 95%;
  font-size: clamp(0.65rem, 1.5vw, 0.75rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  text-align: center;
  line-height: 1.1;
  white-space: pre-line;
}

.config-bubble.selected .bubble-label-medium {
  color: #0a0a0a;
}

.loading-indicator {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
}

.spinner {
  width: clamp(20px, 3vw, 28px);
  height: clamp(20px, 3vw, 28px);
  border: 3px solid rgba(255, 255, 255, 0.2);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ============================================================================
   Section 3 & 3.5: Interception + Optimization Preview
   ============================================================================ */

.interception-section,
.optimization-section {
  width: 100%;
  display: flex;
  justify-content: center;
}

.interception-preview {
  width: 100%;
  max-width: 1000px;
  background: rgba(76, 175, 80, 0.15);
  border: 3px solid #4a8f4d;
  box-shadow: 0 0 30px rgba(76, 175, 80, 0.4);
  transition: all 0.3s ease;
}

.optimization-preview {
  width: 100%;
  max-width: 1000px;
  background: rgba(255, 152, 0, 0.15);
  border: 3px solid #FF9800;
  box-shadow: 0 0 30px rgba(255, 152, 0, 0.4);
  transition: all 0.3s ease;
}

.interception-preview.empty,
.optimization-preview.empty {
  background: rgba(20, 20, 20, 0.5);
  border: 2px dashed rgba(255, 255, 255, 0.3);
  box-shadow: none;
}

.interception-preview.loading,
.optimization-preview.loading {
  background: rgba(20, 20, 20, 0.7);
  border: 2px solid rgba(79, 172, 254, 0.4);
  box-shadow: 0 0 20px rgba(79, 172, 254, 0.3);
}

.interception-preview .bubble-label,
.optimization-preview .bubble-label {
  color: rgba(255, 255, 255, 0.9);
}

.interception-preview.empty .bubble-label,
.interception-preview.loading .bubble-label,
.optimization-preview.empty .bubble-label,
.optimization-preview.loading .bubble-label {
  color: rgba(255, 255, 255, 0.7);
}

.interception-preview .bubble-textarea,
.optimization-preview .bubble-textarea {
  background: rgba(0, 0, 0, 0.3);
  color: white;
}

.interception-preview.empty .bubble-textarea,
.optimization-preview.empty .bubble-textarea {
  background: rgba(0, 0, 0, 0.3);
  color: rgba(255, 255, 255, 0.5);
  cursor: not-allowed;
}

.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 2rem;
  min-height: 120px;
}

.spinner-large {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.2);
  border-top-color: #4facfe;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-text {
  color: rgba(255, 255, 255, 0.8);
  font-size: clamp(0.9rem, 2vw, 1rem);
  margin: 0;
}

/* ============================================================================
   Start Button Container
   ============================================================================ */

.start-button-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(1rem, 3vw, 2rem);
  flex-wrap: wrap;
}

/* ============================================================================
   Start Button
   ============================================================================ */

.start-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(0.5rem, 1.5vw, 0.75rem);
  padding: clamp(0.75rem, 2vw, 1rem) clamp(1.5rem, 4vw, 2.5rem);
  font-size: clamp(1rem, 2.5vw, 1.2rem);
  font-weight: 700;
  background: #000000;
  color: #FFB300;
  border: 3px solid #FFB300;
  border-radius: 16px;
  cursor: pointer;
  box-shadow: 0 0 20px rgba(255, 179, 0, 0.4),
              0 4px 15px rgba(0, 0, 0, 0.5);
  text-shadow: 0 0 10px rgba(255, 179, 0, 0.6);
  transition: all 0.3s ease;
}

.button-arrows {
  font-size: clamp(0.9rem, 2vw, 1.1rem);
}

.button-arrows-left {
  animation: arrow-pulse-left 1.5s ease-in-out infinite;
}

.button-arrows-right {
  animation: arrow-pulse-right 1.5s ease-in-out infinite;
}

.button-text {
  font-size: clamp(1rem, 2.5vw, 1.2rem);
}

@keyframes arrow-pulse-left {
  0%, 100% {
    opacity: 0.4;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

@keyframes arrow-pulse-right {
  0%, 100% {
    opacity: 1;
    transform: scale(1.2);
  }
  50% {
    opacity: 0.4;
    transform: scale(1);
  }
}

.start-button:hover {
  transform: scale(1.05) translateY(-2px);
  box-shadow: 0 0 30px rgba(255, 179, 0, 0.6),
              0 6px 25px rgba(0, 0, 0, 0.6);
  border-color: #FF8F00;
}

.start-button:active {
  transform: scale(0.98);
}

.start-button.disabled,
.start-button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
  filter: grayscale(0.8);
  box-shadow: none;
  text-shadow: none;
}

.start-button.disabled .button-arrows,
.start-button:disabled .button-arrows {
  animation: none;
  opacity: 0.3;
}

/* Safety Approved Stamp */
.safety-stamp {
  display: flex;
  justify-content: center;
  align-items: center;
}

.stamp-inner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: clamp(0.4rem, 1.5vw, 0.6rem) clamp(0.8rem, 2.5vw, 1.2rem);
  background: rgba(76, 175, 80, 0.15);
  border: 2px solid #4CAF50;
  border-radius: 12px;
  box-shadow: 0 0 20px rgba(76, 175, 80, 0.3);
  animation: stamp-appear 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes stamp-appear {
  0% {
    opacity: 0;
    transform: scale(0.5) rotate(-10deg);
  }
  100% {
    opacity: 1;
    transform: scale(1) rotate(0deg);
  }
}

.stamp-icon {
  font-size: clamp(1.2rem, 3vw, 1.5rem);
  color: #4CAF50;
  font-weight: bold;
  line-height: 1;
}

.stamp-text {
  font-size: clamp(0.65rem, 1.5vw, 0.75rem);
  font-weight: 700;
  color: #4CAF50;
  text-align: center;
  line-height: 1.2;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ============================================================================
   Phase 2b: Horizontal Pipeline
   ============================================================================ */

.phase-2b {
  width: 100%;
  max-width: clamp(800px, 90vw, 1200px);
  padding: clamp(2rem, 5vh, 3rem);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(2rem, 4vh, 3rem);
}

.pipeline-title {
  text-align: center;
  font-size: clamp(1.3rem, 3vw, 1.8rem);
  color: #ffffff;
  margin: 0;
}

.pipeline-stages {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(1rem, 2vw, 2rem);
  flex-wrap: wrap;
}

.stage-container {
  display: flex;
  align-items: center;
  gap: clamp(0.5rem, 1vw, 1rem);
}

.stage-bubble {
  position: relative;
  width: clamp(70px, 12vw, 90px);
  height: clamp(70px, 12vw, 90px);

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;

  background: rgba(30, 30, 30, 0.9);
  border: 3px solid rgba(255, 255, 255, 0.2);
  border-radius: 50%;

  transition: all 0.4s ease;
}

.stage-bubble.waiting {
  opacity: 0.5;
}

.stage-bubble.processing {
  border-color: var(--stage-color);
  box-shadow: 0 0 20px var(--stage-color);
  animation: pulse-glow 2s ease-in-out infinite;
}

.stage-bubble.completed {
  border-color: #4CAF50;
  background: rgba(76, 175, 80, 0.1);
  box-shadow: 0 0 15px rgba(76, 175, 80, 0.4);
}

@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 20px var(--stage-color);
  }
  50% {
    box-shadow: 0 0 40px var(--stage-color);
  }
}

.stage-emoji {
  font-size: clamp(1.5rem, 3.5vw, 2rem);
  line-height: 1;
}

.stage-label {
  font-size: clamp(0.65rem, 1.5vw, 0.75rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  text-align: center;
}

.status-indicator {
  position: absolute;
  bottom: clamp(8px, 1.5vw, 12px);
  right: clamp(8px, 1.5vw, 12px);
  width: clamp(20px, 3vw, 28px);
  height: clamp(20px, 3vw, 28px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-dot {
  width: 8px;
  height: 8px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
}

.status-spinner {
  width: clamp(16px, 2.5vw, 20px);
  height: clamp(16px, 2.5vw, 20px);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--stage-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.status-check {
  font-size: clamp(1.2rem, 2.5vw, 1.5rem);
  color: #4CAF50;
  font-weight: bold;
}

.stage-arrow {
  font-size: clamp(1.5rem, 3vw, 2rem);
  color: rgba(255, 255, 255, 0.4);
}

/* Output Frame (Always visible) */
.output-frame {
  width: 100%;
  max-width: 1000px;
  min-height: clamp(250px, 35vh, 400px);
  margin: clamp(1rem, 3vh, 2rem) auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(1.5rem, 3vh, 2rem);
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  transition: all 0.3s ease;
}

.output-frame.empty {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  background: rgba(20, 20, 20, 0.5);
}

.output-frame.generating {
  border: 2px solid rgba(76, 175, 80, 0.6);
  background: rgba(30, 30, 30, 0.9);
  box-shadow: 0 0 30px rgba(76, 175, 80, 0.3);
}

/* Output Placeholder */
.output-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  opacity: 0.4;
}

.placeholder-icon {
  font-size: clamp(3rem, 8vw, 5rem);
  opacity: 0.5;
}

.placeholder-text {
  font-size: clamp(0.9rem, 2vw, 1.1rem);
  color: rgba(255, 255, 255, 0.6);
  text-align: center;
  margin: 0;
}

/* Generation Animation Container */
.generation-animation-container {
  width: 100%;
  display: flex;
  justify-content: center;
}

/* Final Output */
.final-output {
  width: 100%;
  text-align: center;
}

.final-output h3 {
  margin: 0 0 1.5rem 0;
  font-size: clamp(1.1rem, 2.5vw, 1.4rem);
  color: #4CAF50;
}

.output-image {
  max-width: 100%;
  max-height: clamp(300px, 40vh, 500px);
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
  cursor: pointer;
  transition: transform 0.3s ease;
}

.output-image:hover {
  transform: scale(1.02);
}

/* Fullscreen Modal */
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
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
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

/* Slide Down */
.slide-down-enter-active {
  animation: slideDown 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Slide Up */
.slide-up-enter-active {
  animation: slideUp 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Fade */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Phase Transition */
.phase-transition-leave-active {
  transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.phase-transition-enter-active {
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1) 0.1s;
}

.phase-transition-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-20px);
}

.phase-transition-enter-from {
  opacity: 0;
  transform: scale(0.95) translateY(20px);
}

/* Modal Fade */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* ============================================================================
   Scrollbar Styling
   ============================================================================ */

.phase-2a::-webkit-scrollbar {
  width: 8px;
}

.phase-2a::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.phase-2a::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.phase-2a::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* ============================================================================
   Responsive: Mobile Adjustments
   ============================================================================ */

@media (max-width: 768px) {
  .input-context-section {
    flex-direction: column;
  }

  .pipeline-stages {
    flex-direction: column;
  }

  .stage-arrow {
    transform: rotate(90deg);
  }
}

/* iPad 1024×768 Optimization */
@media (min-width: 1024px) and (max-height: 768px) {
  .phase-2a {
    padding: 1.5rem;
    gap: 1.25rem;
  }
}
</style>
