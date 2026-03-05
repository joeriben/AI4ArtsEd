import axios, { type AxiosInstance } from 'axios'
import type { SupportedLanguage, LocalizedString } from '@/i18n'

/**
 * Centralized API Service for AI4ArtsEd DevServer
 *
 * Provides type-safe API methods for:
 * - Phase 1: Config fetching with properties
 * - Phase 2: Pipeline execution with multilingual context
 * - Phase 3: Entity retrieval and status polling
 *
 * Phase 2 - Multilingual Context Editing Implementation
 */

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

/** Config metadata from /pipeline_configs_with_properties */
export interface ConfigMetadata {
  id: string
  name: LocalizedString
  description: LocalizedString
  short_description: LocalizedString
  properties: string[]
  pipeline: string
  media_preferences?: {
    default_output?: string
  }
  loras?: Array<{ name: string; strength: number }>
}

export type PropertyPair = [string, string]

// Session 40: Property symbols support
export interface PropertyPairV2 {
  id: number
  pair: [string, string]
  symbols: { [key: string]: string }
  labels: {
    de: { [key: string]: string }
    en: { [key: string]: string }
  }
  tooltips: {
    de: { [key: string]: string }
    en: { [key: string]: string }
  }
}

export interface ConfigsWithPropertiesResponse {
  configs: ConfigMetadata[]
  property_pairs: PropertyPair[] | PropertyPairV2[]
  symbols_enabled?: boolean
}

/** Pipeline execution request (Phase 2) */
export interface PipelineExecuteRequest {
  schema: string
  input_text: string
  user_input?: string // Original user input (for Phase 2 media generation)
  user_language?: SupportedLanguage
  context_prompt?: string // Optional: user-edited meta-prompt
  context_language?: SupportedLanguage // Language of context_prompt
  custom_placeholders?: Record<string, string> // Optional: custom placeholder values for multi-stage workflows
  output_config?: string // Output config for Stage 4 media generation
  stage4_only?: boolean // Skip Stage 1-3, only execute Stage 4
  seed?: number // Random seed for reproducible media generation
}

/** Pipeline step execution result */
export interface ExecutionStep {
  step_number: number
  chunk_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output?: any
  duration_ms?: number
}

/** Pipeline step definition */
export interface PipelineStepDefinition {
  step_number: number
  chunk_name: string
  label: string
  description: string
  icon: string
  output_type: string
  inputs?: Record<string, string>
}

/** Pipeline visualization metadata */
export interface PipelineVisualization {
  pipeline_name: string
  pipeline_type: string
  visualization_type: string
  steps: PipelineStepDefinition[]
}

/** Pipeline execution response */
export interface PipelineExecuteResponse {
  status: 'success' | 'error'
  final_output?: string
  media_output?: {
    output?: string // prompt_id for media polling
    run_id?: string
    media_type?: string
    media_stored?: boolean
    status?: string
    config?: string
    metadata?: Record<string, any> // Media generation metadata (e.g., seed)
    mesh_url?: string
    thumbnail_url?: string
  }
  error?: string
  run_id?: string
  schema?: string
  config_name?: string
  input_text?: string
  steps_completed?: number
  execution_time?: number
  metadata?: Record<string, any>
  // Session 49: Pipeline visualization data
  pipeline_visualization?: PipelineVisualization
  execution_steps?: ExecutionStep[]
}

/** Transform request (Phase 2 - Stage 1+2 only) */
export interface TransformRequest {
  schema: string
  input_text: string
  user_language: SupportedLanguage
  context_prompt?: string // Optional: user-edited meta-prompt
  context_language?: SupportedLanguage // Language of context_prompt
  output_config?: string // Optional: Media type selection for Stage 2 optimization (Session 58)
}

/** Transform response (Stage 1+2 output) */
export interface TransformResponse {
  success: boolean
  transformed_prompt: string
  stage1_output: {
    translation: string
    safety_passed: boolean
    safety_level: string
    safety_message?: string
    execution_time_ms: number
  }
  stage2_output: {
    interception_result: string
    model_used: string | null
    backend_used: string | null
    execution_time_ms: number
  }
  execution_time_ms: number
  error?: string
  blocked_at_stage?: number
}

/** Media info response (polling) */
export interface MediaInfoResponse {
  type: 'image' | 'audio' | 'video' | 'music'
  files: string[]
  prompt_id: string
}

/** Entity response (from exports) */
export interface EntityResponse {
  name: string
  content: string
  stage?: string
}

// ============================================================================
// AXIOS CLIENT
// ============================================================================

/** Base axios instance with default config */
const apiClient: AxiosInstance = axios.create({
  baseURL: '/', // DevServer serves on same origin
  timeout: 120000, // 2 minutes for long-running pipelines
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor (cache-busting + logging)
apiClient.interceptors.request.use(
  (config) => {
    // Add cache-busting timestamp to all GET requests
    // This prevents Cloudflare Edge + Safari from serving cached responses
    if (config.method?.toLowerCase() === 'get') {
      config.params = {
        ...config.params,
        _t: Date.now()
      }
    }

    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.params || '')
    return config
  },
  (error) => {
    console.error('[API] Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor (cache header verification + error handling)
apiClient.interceptors.response.use(
  (response) => {
    console.log(`[API] Response ${response.status} ${response.config.url}`)

    // Debug: Log cache headers to verify no-cache is working
    if (response.config.url?.includes('/api/')) {
      const cacheControl = response.headers['cache-control']
      console.log(`[API] Cache-Control header:`, cacheControl || 'MISSING ⚠️')
    }

    return response
  },
  (error) => {
    console.error('[API] Response error:', error.response?.status, error.response?.data)
    return Promise.reject(error)
  }
)

// ============================================================================
// API METHODS
// ============================================================================

/**
 * Get all configs with properties (Phase 1)
 */
export async function getConfigsWithProperties(): Promise<ConfigsWithPropertiesResponse> {
  const response = await apiClient.get<ConfigsWithPropertiesResponse>(
    '/pipeline_configs_with_properties'
  )
  return response.data
}

/**
 * Get single config by ID
 */
export async function getConfig(configId: string): Promise<ConfigMetadata> {
  // This endpoint may not exist yet - fetch all and filter
  const data = await getConfigsWithProperties()
  const config = data.configs.find((c) => c.id === configId)
  if (!config) {
    throw new Error(`Config not found: ${configId}`)
  }
  return config
}

/**
 * Get config context (meta-prompt) for Phase 2
 *
 * Returns multilingual context: {en: "...", de: "..."} or string
 */
export interface ConfigContextResponse {
  config_id: string
  context: string | Record<string, string>
}

export async function getConfigContext(configId: string): Promise<ConfigContextResponse> {
  const response = await apiClient.get<ConfigContextResponse>(`/api/config/${configId}/context`)
  return response.data
}

/**
 * Get pipeline structure metadata for a config (Phase 2 - Dynamic UI)
 *
 * Returns pipeline metadata to determine:
 * - How many input bubbles to show (input_requirements)
 * - Whether to show context editing bubble (requires_interception_prompt)
 * - Pipeline stage and type for UI adaptation
 */
export interface PipelineMetadataResponse {
  config_id: string
  pipeline_name: string
  pipeline_type: string | null
  pipeline_stage: string | null
  requires_interception_prompt: boolean
  input_requirements: {
    texts?: number
    images?: number
  }
  description: string
}

export async function getPipelineMetadata(configId: string): Promise<PipelineMetadataResponse> {
  const response = await apiClient.get<PipelineMetadataResponse>(
    `/api/config/${configId}/pipeline`
  )
  return response.data
}

/**
 * Execute pipeline (Phase 2)
 *
 * Supports multilingual context editing:
 * - If context_prompt provided, backend uses user-edited context
 * - If context_language != 'en', backend translates to English
 * - Both versions saved to exports/{run_id}/json/
 */
export async function executePipeline(
  request: PipelineExecuteRequest
): Promise<PipelineExecuteResponse> {
  const response = await apiClient.post<PipelineExecuteResponse>(
    '/api/schema/pipeline/execute',
    request
  )
  return response.data
}

/**
 * Get media info (Phase 3 polling)
 *
 * Returns 404 if not ready yet
 */
export async function getMediaInfo(promptId: string): Promise<MediaInfoResponse> {
  const response = await apiClient.get<MediaInfoResponse>(`/api/media/info/${promptId}`)
  return response.data
}

/**
 * Get media URL for display (Phase 3)
 */
export function getMediaUrl(promptId: string, type: 'image' | 'audio' | 'video' = 'image'): string {
  return `/api/media/${type}/${promptId}`
}

/**
 * Get entity from exports (Phase 3)
 *
 * Entities: input, translation, safety, interception, etc.
 */
export async function getEntity(runId: string, entityName: string): Promise<EntityResponse> {
  const response = await apiClient.get<EntityResponse>(`/api/entities/${runId}/${entityName}`)
  return response.data
}

/**
 * Get pipeline status (if implemented)
 */
export async function getPipelineStatus(runId: string): Promise<any> {
  const response = await apiClient.get(`/api/pipeline/status/${runId}`)
  return response.data
}

/**
 * Model Availability Check (Session 91+, extended Session 176)
 *
 * Queries backend to check model/backend availability across all backends:
 * - ComfyUI configs: checks /object_info for installed models
 * - GPU service configs (Diffusers, HeartMuLa): checks GPU service endpoints
 * - Cloud API configs: always available
 */
export interface ModelAvailability {
  [configId: string]: boolean
}

export interface ModelAvailabilityResponse {
  status: 'success' | 'error'
  availability: ModelAvailability
  comfyui_reachable: boolean
  gpu_service_reachable?: boolean
  cached?: boolean
  cache_age_seconds?: number
  error?: string
}

export async function getModelAvailability(): Promise<ModelAvailabilityResponse> {
  try {
    const response = await apiClient.get<ModelAvailabilityResponse>('/api/models/availability')
    return response.data
  } catch (error) {
    console.error('Failed to fetch model availability:', error)
    // Return empty availability on error (strict mode)
    return {
      status: 'error',
      availability: {},
      comfyui_reachable: false,
      gpu_service_reachable: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    }
  }
}

// ============================================================================
// EXPORT DEFAULT (for convenience imports)
// ============================================================================

export default {
  getConfigsWithProperties,
  getConfig,
  getConfigContext,
  getPipelineMetadata,
  executePipeline,
  getMediaInfo,
  getMediaUrl,
  getEntity,
  getPipelineStatus
}
