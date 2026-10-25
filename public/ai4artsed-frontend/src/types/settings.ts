/**
 * TypeScript interfaces for LLM Model Matrix settings
 *
 * Structure:
 * - Vision models are ALWAYS local and VRAM-dependent
 * - LLM models can be local (VRAM-dependent) or cloud (provider-dependent)
 * - Matrix is split into 3 lookup tables: vision_presets, llm_presets, local_llm_presets
 */

/** Model field identifiers - the ten model roles the settings surfaces configure */
export type ModelField =
  | 'STAGE1_TEXT_MODEL'
  | 'STAGE2_INTERCEPTION_MODEL'
  | 'STAGE2_OPTIMIZATION_MODEL'
  | 'STAGE3_MODEL'
  | 'CHAT_HELPER_MODEL'
  | 'PERSONA_MODEL'
  | 'RESONA_MODEL'
  | 'IMAGE_ANALYSIS_MODEL'
  | 'CODING_MODEL'
  | 'KNOWLEDGE_PROCESSING_MODEL'

/** Vision model fields (always local) */
export type VisionModelField = 'IMAGE_ANALYSIS_MODEL'

/** LLM model fields (can be local or cloud) */
export type LLMModelField = Exclude<ModelField, VisionModelField>

/** VRAM tier identifiers */
export type VramTier = 'vram_8' | 'vram_16' | 'vram_24' | 'vram_32' | 'vram_48' | 'vram_96'

/** Row definition for matrix display */
export interface MatrixRow {
  field: ModelField
  label: string
}

/** Vision preset - VRAM-dependent vision models */
export interface VisionPreset {
  IMAGE_ANALYSIS_MODEL: string
}

/** LLM preset for cloud providers */
export interface CloudLLMPreset {
  label: string
  EXTERNAL_LLM_PROVIDER: string
  DSGVO_CONFORMITY: boolean
  models: Partial<Record<LLMModelField, string>>
}

/** LLM preset for local providers (VRAM-dependent) */
export interface LocalLLMPreset {
  label: string
  EXTERNAL_LLM_PROVIDER: 'none'
  DSGVO_CONFORMITY: true
  models: Partial<Record<LLMModelField, string>>
}

/** New matrix structure with separated lookup tables */
export interface HardwareMatrix {
  /** Vision models by VRAM tier (always local) */
  vision_presets: Record<VramTier, VisionPreset>
  /** Cloud LLM presets by provider */
  llm_presets: Record<string, CloudLLMPreset>
  /** Local LLM presets by VRAM tier */
  local_llm_presets: Record<VramTier, LocalLLMPreset>
}

