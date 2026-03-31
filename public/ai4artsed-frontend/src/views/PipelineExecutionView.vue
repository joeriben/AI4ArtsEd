<template>
  <div class="pipeline-execution-view">
    <!-- Loading state -->
    <div v-if="isLoading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>{{ $t('phase2.loadingConfig') }}</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <div class="error-icon">❌</div>
      <h2>{{ $t('phase2.errorLoadingConfig') }}</h2>
      <p>{{ error }}</p>
      <button class="retry-button" @click="handleRetry">
        {{ $t('phase2.retry') || 'Retry' }}
      </button>
    </div>

    <!-- Main execution interface -->
    <div v-else-if="pipelineStore.selectedConfig" class="execution-container">
      <!-- Header -->
      <div class="page-header">
        <div class="header-left">
          <button class="back-button" @click="handleBack">← {{ $t('phase2.back') || 'Zurück' }}</button>
          <h1 class="config-name">
            {{ getConfigName(pipelineStore.selectedConfig) }}
          </h1>
        </div>
        <div class="header-right">
          <!-- Language toggle -->
          <button class="language-toggle" @click="userPreferences.toggleLanguage()">
            {{ userPreferences.language.toUpperCase() }}
          </button>
        </div>
      </div>

      <!-- Three bubbles layout -->
      <div class="bubbles-container">
        <!-- Bubble 1: User Input -->
        <EditableBubble
          icon="✍️"
          :title="$t('phase2.userInput')"
          v-model="localUserInput"
          :default-value="''"
          :max-chars="500"
          :placeholder="$t('phase2.userInputPlaceholder')"
          class="bubble user-input-bubble"
        />

        <!-- Bubble 2: Meta-Prompt (Context) -->
        <EditableBubble
          icon=""
          :title="$t('phase2.metaPrompt')"
          v-model="localMetaPrompt"
          :default-value="pipelineStore.originalMetaPrompt"
          :max-chars="5000"
          :placeholder="$t('phase2.metaPromptPlaceholder')"
          class="bubble meta-prompt-bubble"
        />

        <!-- Bubble 3: Result (shown after execution) -->
        <div v-if="executionResult" class="bubble result-bubble">
          <div class="bubble-header">
            <div class="header-left">
              <span class="bubble-icon"></span>
              <h3 class="bubble-title">{{ $t('phase2.result') }}</h3>
            </div>
          </div>
          <div class="result-content">
            <p>{{ executionResult }}</p>
            <!-- Media display if available -->
            <img
              v-if="mediaPromptId"
              :src="getMediaUrl(mediaPromptId)"
              alt="Generated media"
              class="generated-media"
            />
          </div>
        </div>
      </div>

      <!-- Execute button -->
      <div class="execute-section">
        <button
          class="execute-button"
          :disabled="!pipelineStore.isReadyToExecute || isExecuting"
          @click="handleExecute"
        >
          <span v-if="!isExecuting">{{ $t('phase2.execute') }}</span>
          <span v-else>{{ $t('phase2.executing') }}</span>
        </button>

        <div class="execution-settings">
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePipelineExecutionStore } from '@/stores/pipelineExecution'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import EditableBubble from '@/components/phase2/EditableBubble.vue'
import { executePipeline, getMediaUrl, type ConfigMetadata } from '@/services/api'

/**
 * PipelineExecutionView - Phase 2 Main View
 *
 * Organic flow with three editable bubbles:
 * 1. User Input (✍️)
 * 2. Meta-Prompt/Context (🧠)
 * 3. Result (✨)
 *
 * Features:
 * - Multilingual meta-prompt loading based on user language
 * - Inline editing with modified detection
 * - Execute pipeline with user-edited context
 * - Backend translates non-English contexts automatically
 *
 * Phase 2 - Multilingual Context Editing Implementation
 */

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

// Stores
const pipelineStore = usePipelineExecutionStore()
const userPreferences = useUserPreferencesStore()

// Local state
const localUserInput = ref('')
const localMetaPrompt = ref('')
const isLoading = ref(false)
const isExecuting = ref(false)
const error = ref<string | null>(null)

const executionResult = ref<string | null>(null)
const mediaPromptId = ref<string | null>(null)

// ============================================================================
// COMPUTED
// ============================================================================

function getConfigName(config: ConfigMetadata): string {
  const lang = userPreferences.language
  return config.name[lang] || config.name.en || config.id
}

// ============================================================================
// METHODS
// ============================================================================

async function initializeView() {
  const configId = route.params.configId as string

  if (!configId) {
    error.value = 'No config ID provided'
    return
  }

  // Load config
  isLoading.value = true
  await pipelineStore.setConfig(configId)

  if (pipelineStore.error) {
    error.value = pipelineStore.error
    isLoading.value = false
    return
  }

  // Load meta-prompt for current language
  await pipelineStore.loadMetaPromptForLanguage(userPreferences.language)

  if (pipelineStore.error) {
    error.value = pipelineStore.error
    isLoading.value = false
    return
  }

  // Initialize local state from store
  localUserInput.value = pipelineStore.userInput
  localMetaPrompt.value = pipelineStore.metaPrompt
  isLoading.value = false
}

// ============================================================================
// LIFECYCLE
// ============================================================================

onMounted(() => {
  initializeView()
})

// ============================================================================
// WATCHERS
// ============================================================================

// Watch language changes and reload meta-prompt
watch(
  () => userPreferences.language,
  async (newLang) => {
    await pipelineStore.loadMetaPromptForLanguage(newLang)
    localMetaPrompt.value = pipelineStore.metaPrompt
  }
)

// Sync local state to store
watch(localUserInput, (newValue) => pipelineStore.updateUserInput(newValue))
watch(localMetaPrompt, (newValue) => pipelineStore.updateMetaPrompt(newValue))
// ============================================================================
// METHODS
// ============================================================================

async function handleExecute() {
  if (!pipelineStore.selectedConfig || !pipelineStore.isReadyToExecute) {
    return
  }

  isExecuting.value = true
  executionResult.value = null
  mediaPromptId.value = null

  try {
    // Prepare execution request
    const request = {
      schema: pipelineStore.selectedConfig.id,
      input_text: pipelineStore.userInput,
      user_language: userPreferences.language,
      // Include context_prompt if modified
      ...(pipelineStore.metaPromptModified && {
        context_prompt: pipelineStore.metaPrompt,
        context_language: userPreferences.language
      })
    }

    console.log('[Phase2] Executing pipeline:', request)

    // Execute pipeline
    const response = await executePipeline(request)

    if (response.status !== 'success') {
      throw new Error(response.error || 'Execution failed')
    }

    // Handle result
    executionResult.value = response.final_output || 'No text output'

    // Handle media output if available
    if (response.media_output?.output) {
      mediaPromptId.value = response.media_output.output
      // TODO: Poll for media availability (Phase 3)
    }

    console.log('[Phase2] Execution successful:', response)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Execution failed'
    console.error('[Phase2] Execution error:', err)
  } finally {
    isExecuting.value = false
  }
}

function handleBack() {
  router.push({ name: 'property-selection' })
}

function handleRetry() {
  error.value = null
  // Reload the view
  initializeView()
}
</script>

<style scoped>
.pipeline-execution-view {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: #0a0a0a;
  color: #ffffff;
}

/* Loading/Error states */
.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 20px;
}

.loading-spinner {
  width: 60px;
  height: 60px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-icon {
  font-size: 48px;
}

.error-state h2 {
  margin: 0;
  font-size: 24px;
}

.error-state p {
  margin: 0;
  color: rgba(255, 255, 255, 0.6);
}

.retry-button {
  padding: 12px 24px;
  background: rgba(96, 165, 250, 0.2);
  color: #60a5fa;
  border: 2px solid #60a5fa;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.retry-button:hover {
  background: #60a5fa;
  color: #0a0a0a;
  transform: scale(1.05);
}

/* Main container */
.execution-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 40px 60px;
}

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 40px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-button {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.back-button:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
}

.config-name {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: #ffffff;
}

.language-toggle {
  width: 48px;
  height: 48px;
  padding: 0;
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  font-size: 24px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.language-toggle:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.1);
}

/* Bubbles layout */
.bubbles-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-bottom: 32px;
}

.bubble {
  width: 100%;
}

/* Execute section */
.execute-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.execute-button {
  padding: 16px 48px;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: #ffffff;
  border: none;
  border-radius: 12px;
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 16px rgba(96, 165, 250, 0.3);
}

.execute-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(96, 165, 250, 0.4);
}

.execute-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.execution-settings {
  display: flex;
  gap: 12px;
}

.setting-select {
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.setting-select:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
}

/* Result bubble */
.result-bubble {
  background: rgba(30, 30, 30, 0.8);
  border: 2px solid rgba(96, 165, 250, 0.5);
  border-radius: 16px;
  padding: 20px;
  backdrop-filter: blur(10px);
}

.bubble-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bubble-icon {
  font-size: 24px;
}

.bubble-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.result-content {
  padding: 16px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
}

.result-content p {
  margin: 0 0 16px 0;
  line-height: 1.6;
}

.generated-media {
  width: 100%;
  max-width: 600px;
  border-radius: 8px;
  margin-top: 16px;
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .execution-container {
    padding: 20px;
  }

  .config-name {
    font-size: 20px;
  }

  .execute-button {
    width: 100%;
    padding: 14px 24px;
    font-size: 16px;
  }

  .execution-settings {
    width: 100%;
    flex-direction: column;
  }

  .setting-select {
    width: 100%;
  }
}
</style>
