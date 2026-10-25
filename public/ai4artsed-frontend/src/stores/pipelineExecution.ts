import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { getConfig, getConfigContext, type ConfigMetadata } from '@/services/api'
import type { SupportedLanguage } from '@/i18n'

/**
 * Pinia Store for Phase 2 Pipeline Execution
 *
 * Manages:
 * - Selected config for execution
 * - User input text
 * - Meta-prompt (context) with edit tracking
 * - Execution settings (mode)
 * - Multilingual meta-prompt loading based on user language
 *
 * Phase 2 - Multilingual Context Editing Implementation
 */
export const usePipelineExecutionStore = defineStore('pipelineExecution', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  /** Selected config metadata */
  const selectedConfig = ref<ConfigMetadata | null>(null)

  /** User input text */
  const userInput = ref('')

  /** Meta-prompt (context) in current language */
  const metaPrompt = ref('')

  /** Original meta-prompt for comparison (detect modifications) */
  const originalMetaPrompt = ref('')

  /** Loading state */
  const isLoading = ref(false)

  /** Error state */
  const error = ref<string | null>(null)

  /** Transformed prompt (result of Stage 1+2) */
  const transformedPrompt = ref('')

  // ============================================================================
  // COMPUTED
  // ============================================================================

  /**
   * Whether meta-prompt has been modified from original
   */
  const metaPromptModified = computed(() => {
    return metaPrompt.value !== originalMetaPrompt.value && originalMetaPrompt.value !== ''
  })

  /**
   * Whether ready to execute (has config and user input)
   */
  const isReadyToExecute = computed(() => {
    return selectedConfig.value !== null && userInput.value.trim().length > 0
  })

  // ============================================================================
  // ACTIONS
  // ============================================================================

  /**
   * Set selected config and load its metadata
   *
   * @param configId - Config ID from Phase 1 selection
   */
  async function setConfig(configId: string) {
    isLoading.value = true
    error.value = null

    console.log(`[PipelineExecution] setConfig called with configId: "${configId}"`)

    try {
      // Load config metadata
      const config = await getConfig(configId)
      selectedConfig.value = config

      console.log(`[PipelineExecution] Config loaded successfully:`, {
        id: config.id,
        name: config.name,
        pipeline: config.pipeline
      })
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load config'
      console.error('[PipelineExecution] Error loading config:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Load meta-prompt (context) for selected language
   *
   * @param language - User's selected language
   */
  async function loadMetaPromptForLanguage(language: SupportedLanguage) {
    if (!selectedConfig.value) {
      console.warn('[PipelineExecution] loadMetaPromptForLanguage: No config selected')
      return
    }

    isLoading.value = true
    error.value = null

    console.log(`[PipelineExecution] loadMetaPromptForLanguage: configId="${selectedConfig.value.id}", language="${language}"`)

    try {
      // Fetch context from backend
      console.log(`[PipelineExecution] Fetching: GET /api/config/${selectedConfig.value.id}/context`)
      const contextData = await getConfigContext(selectedConfig.value.id)

      console.log(`[PipelineExecution] Context response:`, {
        config_id: contextData.config_id,
        contextType: typeof contextData.context,
        contextKeys: typeof contextData.context === 'object' ? Object.keys(contextData.context) : 'N/A'
      })

      // Extract context in selected language
      let contextText: string

      if (typeof contextData.context === 'string') {
        // Old format (not yet translated)
        console.log('[PipelineExecution] Context is string (old format)')
        contextText = contextData.context
      } else {
        // New format {en: "...", de: "..."}
        console.log(`[PipelineExecution] Context is object, extracting language: ${language}`)
        contextText = contextData.context[language] || contextData.context.en || ''
        console.log(`[PipelineExecution] Extracted ${language} context (${contextText.length} chars): ${contextText.substring(0, 80)}...`)
      }

      // Set meta-prompt
      metaPrompt.value = contextText
      originalMetaPrompt.value = contextText

      console.log(
        `[PipelineExecution] ✅ Meta-prompt set for ${selectedConfig.value.id} (${language}): ${contextText.substring(0, 50)}...`
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load meta-prompt'
      console.error('[PipelineExecution] ❌ Error loading meta-prompt:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Update user input text
   *
   * @param text - New user input
   */
  function updateUserInput(text: string) {
    userInput.value = text
  }

  /**
   * Update meta-prompt (user editing)
   *
   * @param text - New meta-prompt text
   */
  function updateMetaPrompt(text: string) {
    metaPrompt.value = text
  }

  /**
   * Reset meta-prompt to original value
   */
  function resetMetaPrompt() {
    metaPrompt.value = originalMetaPrompt.value
    console.log('[PipelineExecution] Meta-prompt reset to original')
  }

  /**
   * Update transformed prompt (result of Stage 1+2)
   *
   * @param text - Transformed prompt text
   */
  function updateTransformedPrompt(text: string) {
    transformedPrompt.value = text
    console.log('[PipelineExecution] Transformed prompt updated:', text.substring(0, 100) + '...')
  }

  /**
   * Clear transformed prompt
   */
  function clearTransformedPrompt() {
    transformedPrompt.value = ''
    console.log('[PipelineExecution] Transformed prompt cleared')
  }

  /**
   * Clear all state (for new session)
   */
  function clearAll() {
    selectedConfig.value = null
    userInput.value = ''
    metaPrompt.value = ''
    originalMetaPrompt.value = ''
    transformedPrompt.value = ''
    error.value = null
    console.log('[PipelineExecution] State cleared')
  }

  // ============================================================================
  // RETURN PUBLIC API
  // ============================================================================

  return {
    // State
    selectedConfig: computed(() => selectedConfig.value),
    userInput: computed(() => userInput.value),
    metaPrompt: computed(() => metaPrompt.value),
    originalMetaPrompt: computed(() => originalMetaPrompt.value),
    transformedPrompt: computed(() => transformedPrompt.value),
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),

    // Computed
    metaPromptModified,
    isReadyToExecute,

    // Actions
    setConfig,
    loadMetaPromptForLanguage,
    updateUserInput,
    updateMetaPrompt,
    resetMetaPrompt,
    updateTransformedPrompt,
    clearTransformedPrompt,
    clearAll
  }
})
