/**
 * TypeScript interfaces for LLM Model Matrix settings
 *
 * New structure (Session 155):
 * - Vision models are ALWAYS local and VRAM-dependent
 * - LLM models can be local (VRAM-dependent) or cloud (provider-dependent)
 * - Matrix is split into 3 lookup tables: vision_presets, llm_presets, local_llm_presets
 */

/** Model field identifiers - the 9 application areas */
export type ModelField =
  | 'STAGE1_TEXT_MODEL'
  | 'STAGE1_VISION_MODEL'
  | 'STAGE2_INTERCEPTION_MODEL'
  | 'STAGE2_OPTIMIZATION_MODEL'
  | 'STAGE3_MODEL'
  | 'STAGE4_LEGACY_MODEL'
  | 'CHAT_HELPER_MODEL'
  | 'IMAGE_ANALYSIS_MODEL'
  | 'CODING_MODEL'

/** Vision model fields (always local) */
export type VisionModelField = 'STAGE1_VISION_MODEL' | 'IMAGE_ANALYSIS_MODEL'

/** LLM model fields (can be local or cloud) */
export type LLMModelField = Exclude<ModelField, VisionModelField>

/** VRAM tier identifiers */
export type VramTier = 'vram_8' | 'vram_16' | 'vram_24' | 'vram_32' | 'vram_48' | 'vram_96'

/** Cloud provider identifiers (bedrock removed) */
export type CloudProvider = 'none' | 'local' | 'mistral' | 'ionos' | 'anthropic' | 'openai' | 'openrouter'

/** Row definition for matrix display */
export interface MatrixRow {
  field: ModelField
  label: string
  stage: string
}

/** Vision preset - VRAM-dependent vision models */
export interface VisionPreset {
  STAGE1_VISION_MODEL: string
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

/** Merged preset result (for applying to settings) */
export interface MergedPreset {
  label: string
  EXTERNAL_LLM_PROVIDER: string
  DSGVO_CONFORMITY: boolean
  vram_tier: VramTier
  models: Record<ModelField, string>
}

// Legacy types for backwards compatibility (deprecated)
/** @deprecated Use HardwareMatrix instead */
export interface MatrixColumn {
  id: string
  label: string
  type: 'local' | 'cloud'
  dsgvoCompliant: boolean
}

/** @deprecated Use CloudLLMPreset or LocalLLMPreset instead */
export interface PresetData {
  label: string
  models: Record<ModelField, string>
  EXTERNAL_LLM_PROVIDER: CloudProvider
  DSGVO_CONFORMITY: boolean
}
