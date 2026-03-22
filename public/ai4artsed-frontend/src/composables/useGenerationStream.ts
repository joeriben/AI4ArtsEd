/**
 * useGenerationStream - SSE-based generation with real-time badge updates
 *
 * Session 148: Provides streaming generation with stage-by-stage events.
 * Used by text_transformation, image_transformation, multi_image_transformation.
 *
 * Events from backend:
 * - connected: Initial connection established
 * - stage3_start: Translation + Safety check starting
 * - stage3_complete: {safe, was_translated} - triggers badges
 * - blocked: Content blocked by safety (aborts)
 * - queue_position: {position, active} - queue transparency
 * - stage4_start: Media generation starting
 * - cancelled: Generation was cancelled (from another tab)
 * - complete: {media_output, run_id, loras, was_translated}
 * - error: Error occurred
 */

import { ref } from 'vue'
import { useSafetyEventStore } from '@/stores/safetyEvent'

export interface GenerationParams {
  prompt: string
  output_config: string
  seed?: number | null
  input_text?: string
  context_prompt?: string
  interception_result?: string
  interception_config?: string
  run_id?: string | null
  device_id?: string
  input_image?: string | null
  input_image1?: string | null
  input_image2?: string | null
  input_image3?: string | null
  alpha_factor?: number | null

  // Session 265: Comparison mode — skip Stage 3 translation (send prompt raw to model)
  skip_stage3_translation?: boolean

  // Session 273: Source tagging + comparison group linking
  source_view?: string
  comparison_group_id?: string
  comparison_language?: string
  comparison_original_prompt?: string

  // Session 151: Generation parameters (optional, ignored if config doesn't support them)
  width?: number
  height?: number
  steps?: number
  cfg?: number
  negative_prompt?: string
  sampler_name?: string
  scheduler?: string
  denoise?: number
}

export type GenerationErrorType = 'busy' | 'offline' | 'unknown'

export interface GenerationResult {
  status: 'success' | 'blocked' | 'error' | 'cancelled'
  media_output?: {
    media_type: string
    url: string
    run_id: string
    index: number
    seed: number
    code?: string
    mesh_url?: string
    thumbnail_url?: string
  }
  run_id?: string
  loras?: Array<{ name: string; strength: number }>
  was_translated?: boolean
  error?: string
  errorType?: GenerationErrorType
  blocked_reason?: string
  found_terms?: string[]
}

/**
 * Classify backend error messages into typed categories for i18n display.
 */
function classifyError(message: string): GenerationErrorType {
  if (/queue full|device.busy|previous.*generation.*running/i.test(message)) return 'busy'
  if (/not available|not reachable|connection refused|timeout/i.test(message)) return 'offline'
  return 'unknown'
}

export function useGenerationStream() {
  const safetyStore = useSafetyEventStore()

  // Badge states
  // TODO: showSafetyApprovedStamp and showTranslatedStamp are deprecated — kept for backward compat, unused in templates
  const showSafetyApprovedStamp = ref(false)
  const showTranslatedStamp = ref(false)
  const safetyChecks = ref<string[]>([])

  // Progress state
  const generationProgress = ref(0)
  const previewImage = ref<string | null>(null)
  const isExecuting = ref(false)
  const currentStage = ref<'idle' | 'stage3' | 'stage4' | 'complete'>('idle')
  const modelMeta = ref<Record<string, any> | null>(null)
  const stage4DurationMs = ref(0)
  let _stage4StartTime = 0

  // Queue transparency + per-device lock
  const queuePosition = ref(0)
  const deviceBusy = ref(false)
  const preChecking = ref(false)

  /**
   * Build SSE URL with query parameters
   */
  function buildSSEUrl(baseUrl: string, params: GenerationParams): string {
    const queryParams = new URLSearchParams()

    // Required params
    queryParams.set('prompt', params.prompt)
    queryParams.set('output_config', params.output_config)
    queryParams.set('enable_streaming', 'true')

    // Optional params
    if (params.seed !== null && params.seed !== undefined) {
      queryParams.set('seed', String(params.seed))
    }
    if (params.input_text) {
      queryParams.set('input_text', params.input_text)
    }
    if (params.context_prompt) {
      queryParams.set('context_prompt', params.context_prompt)
    }
    if (params.interception_result) {
      queryParams.set('interception_result', params.interception_result)
    }
    if (params.interception_config) {
      queryParams.set('interception_config', params.interception_config)
    }
    if (params.run_id) {
      queryParams.set('run_id', params.run_id)
    }
    if (params.device_id) {
      queryParams.set('device_id', params.device_id)
    }
    if (params.input_image) {
      queryParams.set('input_image', params.input_image)
    }
    if (params.input_image1) {
      queryParams.set('input_image1', params.input_image1)
    }
    if (params.input_image2) {
      queryParams.set('input_image2', params.input_image2)
    }
    if (params.input_image3) {
      queryParams.set('input_image3', params.input_image3)
    }
    if (params.alpha_factor !== null && params.alpha_factor !== undefined) {
      queryParams.set('alpha_factor', String(params.alpha_factor))
    }

    // Session 265: Comparison mode
    if (params.skip_stage3_translation) {
      queryParams.set('skip_stage3_translation', 'true')
    }

    // Session 273: Source tagging + comparison group linking
    if (params.source_view) {
      queryParams.set('source_view', params.source_view)
    }
    if (params.comparison_group_id) {
      queryParams.set('comparison_group_id', params.comparison_group_id)
    }
    if (params.comparison_language) {
      queryParams.set('comparison_language', params.comparison_language)
    }
    if (params.comparison_original_prompt) {
      queryParams.set('comparison_original_prompt', params.comparison_original_prompt)
    }

    // Session 151: Generation parameters (optional)
    if (params.width !== undefined) {
      queryParams.set('width', String(params.width))
    }
    if (params.height !== undefined) {
      queryParams.set('height', String(params.height))
    }
    if (params.steps !== undefined) {
      queryParams.set('steps', String(params.steps))
    }
    if (params.cfg !== undefined) {
      queryParams.set('cfg', String(params.cfg))
    }
    if (params.negative_prompt) {
      queryParams.set('negative_prompt', params.negative_prompt)
    }
    if (params.sampler_name) {
      queryParams.set('sampler_name', params.sampler_name)
    }
    if (params.scheduler) {
      queryParams.set('scheduler', params.scheduler)
    }
    if (params.denoise !== undefined) {
      queryParams.set('denoise', String(params.denoise))
    }

    return `${baseUrl}?${queryParams.toString()}`
  }

  /**
   * Execute generation with SSE streaming
   */
  async function executeWithStreaming(params: GenerationParams): Promise<GenerationResult> {
    // Determine base URL based on environment
    const isDev = import.meta.env.DEV
    const baseUrl = isDev
      ? 'http://localhost:17802/api/schema/pipeline/generation'
      : '/api/schema/pipeline/generation'

    const url = buildSSEUrl(baseUrl, params)
    console.log('[GENERATION-STREAM] Starting SSE connection:', url.substring(0, 100) + '...')

    isExecuting.value = true
    currentStage.value = 'stage3'
    generationProgress.value = 0
    previewImage.value = null
    modelMeta.value = null
    queuePosition.value = 0

    return new Promise((resolve, reject) => {
      const eventSource = new EventSource(url)

      eventSource.addEventListener('connected', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        console.log('[GENERATION-STREAM] Connected:', data)
      })

      eventSource.addEventListener('stage3_start', () => {
        console.log('[GENERATION-STREAM] Stage 3 started (Translation + Safety)')
        currentStage.value = 'stage3'
      })

      eventSource.addEventListener('stage3_complete', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        console.log('[GENERATION-STREAM] Stage 3 complete:', data)

        // Merge Stage 3 checks into safety badges
        if (data.checks_passed) {
          safetyChecks.value = [...safetyChecks.value, ...data.checks_passed]
        }

        // Trigger legacy badges
        if (data.safe) {
          showSafetyApprovedStamp.value = true
        }
        if (data.was_translated) {
          showTranslatedStamp.value = true
        }
      })

      eventSource.addEventListener('blocked', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        console.log('[GENERATION-STREAM] Blocked:', data)
        // Centralized: report block to safetyStore (Trashy integration)
        safetyStore.reportBlock(data.stage || 3, data.reason || 'Inhalt blockiert', data.found_terms || [], data.vlm_description)
        eventSource.close()
        isExecuting.value = false
        currentStage.value = 'idle'
        resolve({
          status: 'blocked',
          blocked_reason: data.reason,
          found_terms: data.found_terms || []
        })
      })

      // Queue transparency: how many generations are ahead
      eventSource.addEventListener('queue_position', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        console.log('[GENERATION-STREAM] Queue position:', data)
        queuePosition.value = data.position
      })

      eventSource.addEventListener('stage4_start', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        console.log('[GENERATION-STREAM] Stage 4 started (Media Generation)')
        currentStage.value = 'stage4'
        generationProgress.value = 0
        previewImage.value = null
        modelMeta.value = data.model_meta || null
        _stage4StartTime = Date.now()
      })

      eventSource.addEventListener('generation_progress', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        generationProgress.value = data.percent
        if (data.preview) {
          previewImage.value = data.preview
        }
      })

      // Cancelled: generation was cancelled (from another tab or cancel button)
      eventSource.addEventListener('cancelled', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        console.log('[GENERATION-STREAM] Cancelled:', data)
        eventSource.close()
        isExecuting.value = false
        currentStage.value = 'idle'
        resolve({ status: 'cancelled' })
      })

      eventSource.addEventListener('complete', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        console.log('[GENERATION-STREAM] Complete:', data)
        eventSource.close()
        isExecuting.value = false
        currentStage.value = 'complete'
        generationProgress.value = 100
        stage4DurationMs.value = _stage4StartTime ? Date.now() - _stage4StartTime : 0
        resolve({
          status: 'success',
          media_output: data.media_output,
          run_id: data.run_id,
          loras: data.loras || [],
          was_translated: data.was_translated
        })
      })

      eventSource.addEventListener('error', (e: MessageEvent) => {
        // Check if it's a custom error event or connection error
        if (e.data) {
          const data = JSON.parse(e.data)
          console.error('[GENERATION-STREAM] Error event:', data)
          eventSource.close()
          isExecuting.value = false
          currentStage.value = 'idle'
          const errorMsg = data.message || 'Unknown error'
          resolve({
            status: 'error',
            error: errorMsg,
            errorType: classifyError(errorMsg)
          })
        } else {
          // Connection error
          console.error('[GENERATION-STREAM] Connection error')
          eventSource.close()
          isExecuting.value = false
          currentStage.value = 'idle'
          reject(new Error('SSE connection failed'))
        }
      })

      // Handle native EventSource errors
      eventSource.onerror = () => {
        if (eventSource.readyState === EventSource.CLOSED) {
          // Normal close, ignore
          return
        }
        console.error('[GENERATION-STREAM] EventSource error')
        eventSource.close()
        isExecuting.value = false
        currentStage.value = 'idle'
        reject(new Error('SSE connection error'))
      }
    })
  }

  /**
   * Pre-check: is this device currently generating? (REST call)
   */
  async function checkDeviceActive(deviceId: string): Promise<void> {
    preChecking.value = true
    try {
      const isDev = import.meta.env.DEV
      const baseUrl = isDev ? 'http://localhost:17802' : ''
      const res = await fetch(`${baseUrl}/api/schema/pipeline/generation-active?device_id=${encodeURIComponent(deviceId)}`)
      const data = await res.json()
      deviceBusy.value = data.active
      queuePosition.value = data.queue_total || 0
    } catch (e) {
      console.error('[GENERATION-STREAM] Pre-check failed:', e)
      deviceBusy.value = false
    } finally {
      preChecking.value = false
    }
  }

  /**
   * Cancel a running generation for this device (REST call)
   */
  async function cancelGeneration(deviceId: string): Promise<boolean> {
    try {
      const isDev = import.meta.env.DEV
      const baseUrl = isDev ? 'http://localhost:17802' : ''
      const res = await fetch(`${baseUrl}/api/schema/pipeline/generation-cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId })
      })
      const data = await res.json()
      if (data.cancelled) {
        deviceBusy.value = false
      }
      return data.cancelled
    } catch (e) {
      console.error('[GENERATION-STREAM] Cancel failed:', e)
      return false
    }
  }

  /**
   * Reset all states for new generation
   */
  function reset() {
    showSafetyApprovedStamp.value = false
    showTranslatedStamp.value = false
    safetyChecks.value = []
    generationProgress.value = 0
    previewImage.value = null
    isExecuting.value = false
    currentStage.value = 'idle'
    modelMeta.value = null
    stage4DurationMs.value = 0
    _stage4StartTime = 0
    queuePosition.value = 0
  }

  return {
    // Badge states
    showSafetyApprovedStamp,
    showTranslatedStamp,
    safetyChecks,

    // Progress states
    generationProgress,
    previewImage,
    isExecuting,
    currentStage,
    modelMeta,
    stage4DurationMs,

    // Queue transparency + per-device lock
    queuePosition,
    deviceBusy,
    preChecking,

    // Methods
    executeWithStreaming,
    checkDeviceActive,
    cancelGeneration,
    reset
  }
}
