/**
 * useCurrentSession - Global session state management
 *
 * Provides shared state for current run_id across all components.
 * Used by ChatOverlay to get session context, and by views to register new sessions.
 */

import { ref, readonly } from 'vue'

export interface SessionState {
  runId: string | null
  mediaType: string | null
  configName: string | null
}

// Singleton state (shared across all component instances)
const sessionState = ref<SessionState>({
  runId: null,
  mediaType: null,
  configName: null
})

/**
 * Composable for managing current session state
 *
 * Usage in views (e.g., text_transformation.vue):
 * ```ts
 * const { updateSession } = useCurrentSession()
 *
 * // After pipeline execution:
 * const response = await axios.post('/api/schema/pipeline/stream', ...)
 * const runId = response.data.run_id
 * updateSession(runId, {
 *   mediaType: 'image',
 *   configName: selectedConfig.value
 * })
 * ```
 *
 * Usage in ChatOverlay:
 * ```ts
 * const { currentSession } = useCurrentSession()
 *
 * // Send message with context:
 * await axios.post('/api/chat', {
 *   message: userInput,
 *   run_id: currentSession.value.runId
 * })
 * ```
 */
export function useCurrentSession() {
  /**
   * Update current session
   *
   * @param runId - The run_id from pipeline execution
   * @param metadata - Optional metadata (mediaType, configName)
   */
  function updateSession(runId: string, metadata?: { mediaType?: string; configName?: string }) {
    sessionState.value = {
      runId,
      mediaType: metadata?.mediaType || null,
      configName: metadata?.configName || null
    }
    console.log('[useCurrentSession] Session updated:', sessionState.value)
  }

  /**
   * Clear current session (e.g., when navigating away)
   */
  function clearSession() {
    sessionState.value = {
      runId: null,
      mediaType: null,
      configName: null
    }
    console.log('[useCurrentSession] Session cleared')
  }

  /**
   * Check if a session is currently active
   */
  function hasActiveSession(): boolean {
    return sessionState.value.runId !== null
  }

  // Return readonly version to prevent direct mutation
  return {
    currentSession: readonly(sessionState),
    updateSession,
    clearSession,
    hasActiveSession
  }
}
