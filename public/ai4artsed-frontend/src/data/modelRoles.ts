/**
 * The model roles — one list, one order, for every surface that shows them.
 *
 * Three surfaces show the same roles: the configuration page, the model matrix,
 * and the model assignments of the API management tab. Each of them used to
 * carry its own list, and the backend carried a fourth with English labels of
 * its own — which is how the assignments table came to read "Code generation"
 * inside a German page, in alphabetical order rather than in the set order
 * (Flask sorts JSON keys, so the backend's order never arrived).
 *
 * The order: first the three places where somebody talks to a model, then the
 * run in the order it happens, then the models asked for a single piece of work.
 *
 * `field` is the key in user_settings.json, `labelKey` the i18n key of the name
 * the interface uses for that role.
 */
import type { ModelField } from '@/types/settings'

export interface ModelRole {
  field: ModelField
  labelKey: string
}

export const MODEL_ROLES: readonly ModelRole[] = [
  { field: 'CHAT_HELPER_MODEL', labelKey: 'settings.models.chatHelper' },
  { field: 'RESONA_MODEL', labelKey: 'settings.models.resona' },
  { field: 'PERSONA_MODEL', labelKey: 'settings.models.persona' },
  { field: 'STAGE1_TEXT_MODEL', labelKey: 'settings.models.stage1Text' },
  { field: 'STAGE2_INTERCEPTION_MODEL', labelKey: 'settings.models.stage2Interception' },
  { field: 'STAGE2_OPTIMIZATION_MODEL', labelKey: 'settings.models.stage2Optimization' },
  { field: 'STAGE3_MODEL', labelKey: 'settings.models.stage3' },
  { field: 'IMAGE_ANALYSIS_MODEL', labelKey: 'settings.models.imageAnalysis' },
  { field: 'CODING_MODEL', labelKey: 'settings.models.coding' },
  { field: 'KNOWLEDGE_PROCESSING_MODEL', labelKey: 'settings.models.knowledgeProcessing' },
]
