import axios, { type AxiosInstance } from 'axios'
import type { SupportedLanguage, LocalizedString } from '@/i18n'

/**
 * Centralized API Service for ATELIER
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

export interface ConfigsWithPropertiesResponse {
  configs: ConfigMetadata[]
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
  // Pipeline visualization data
  pipeline_visualization?: PipelineVisualization
  execution_steps?: ExecutionStep[]
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

// Request interceptor (cache-busting)
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
    return config
  },
  (error) => {
    console.error('[API] Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor (error handling)
apiClient.interceptors.response.use(
  (response) => response,
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
 * Model Availability Check
 *
 * Queries backend to check model/backend availability across all backends:
 * - ComfyUI configs: checks /object_info for installed models
 * - GPU service configs (Diffusers, HeartMuLa): checks GPU service endpoints
 * - Cloud API configs: available while their provider holds a key; for a
 *   provider whose entry in devserver/config/llm_providers.json names the
 *   LiteLLM account API also one it accepts, with credit left
 *   (devserver/my_app/services/provider_account.py)
 */
export interface ModelAvailability {
  [configId: string]: boolean
}

export interface ModelAvailabilityResponse {
  status: 'success' | 'error'
  availability: ModelAvailability
  /**
   * The cloud configs among the unavailable ones whose provider holds no key,
   * refuses it, or reports no credit left. A surface names that cause instead
   * of the one for a model that is not installed.
   */
  account_missing?: string[]
  /** config id -> the provider it sends to, for each of those. */
  account_provider?: Record<string, string>
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

/**
 * What the card beside an output config says: its name by language, and from
 * the output chunk it names the quality rating, the estimated duration and the
 * VRAM it loads (`GET /api/schema/output-cards`,
 * devserver/my_app/routes/schema_pipeline_routes.py). A value the chunk does
 * not carry is null.
 */
export interface OutputCard {
  name: Record<string, string>
  quality_rating: number | null
  estimated_duration_seconds: string | number | null
  gpu_vram_mb: number | null
}

/** The cards of these configs. Throws when the question fails, so the caller
    can ask again. */
export async function getOutputCards(ids: string[]): Promise<Record<string, OutputCard>> {
  const response = await apiClient.get<Record<string, OutputCard>>('/api/schema/output-cards', {
    params: { ids: ids.join(',') },
  })
  return response.data
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
}
