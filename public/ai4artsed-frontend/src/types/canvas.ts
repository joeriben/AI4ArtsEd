/**
 * Canvas Workflow Types for ATELIER
 *
 * Defines types for the visual canvas workflow builder.
 * Supports parallel fan-out workflows with feedback loops.
 */
import type { LocalizedString } from '@/i18n'
import type { ReadingFrame } from '@/data/readingFrames'

// ============================================================================
// NODE TYPES
// ============================================================================

/**
 * Available stage/node types in the canvas
 *
 * NOTE: Safety is NOT a user-visible node!
 * - Stage 1 Safety: Automatic in /pipeline/interception
 * - Stage 3 Safety: Automatic per output-config
 * DevServer handles all safety transparently.
 *
 * Evaluation and display nodes carry the decision logic.
 */
export type StageType =
  | 'input'
  | 'image_input' // Image upload as source
  | 'random_prompt' // LLM-based random prompt generator with presets
  | 'interception'
  | 'translation'
  | 'model_adaption' // Model-specific prompt adaption (CLIP/T5 encoder)
  | 'generation'
  | 'collector'
  // Unified evaluation node with optional branching
  | 'evaluation'
  // Vision-LLM image analysis
  | 'image_evaluation'
  // Display node (visualization)
  | 'display'
  // Multi-input comparison evaluator
  | 'comparison_evaluator'
  // Seed control node for reproducible generation
  | 'seed'
  // Parameter nodes for generation control
  | 'resolution'
  | 'quality'

// ============================================================================
// MODEL ADAPTION TYPES
// ============================================================================

/** Model Adaption Preset Types - adapts prompt for specific media models */
export type ModelAdaptionPreset =
  | 'none'      // No adaption (pass-through)
  | 'sd35'      // Stable Diffusion 3.5 (CLIP-style keywords)
  | 'flux'      // Flux (T5-style natural language)
  | 'video'     // Video models (scenic descriptions)
  | 'audio'     // Audio/Music models (auditive descriptions)

// ============================================================================
// INTERCEPTION PRESET TYPES
// ============================================================================

/** Interception Preset IDs - maps to Stage2 interception configs */
export type InterceptionPreset =
  | 'user_defined'              // Default - eigene Anweisung
  | 'analog_photography_1870s'  // Daguerreotype
  | 'analog_photography_1970s'  // Analog Photography
  | 'analogue_copy'             // Analogue Copy
  | 'bauhaus'                   // Bauhaus
  | 'clichéfilter_v2'           // De-Kitsch
  | 'confucianliterati'         // Literati
  | 'cooked_negatives'          // Cooked Negatives
  | 'digital_photography'       // Digital Photography
  | 'forceful'                  // Forceful
  | 'hunkydoryharmonizer'       // Sweetener
  | 'jugendsprache'             // Slang
  | 'mad_world'                 // mad world
  | 'one_world'                 // One World
  | 'overdrive'                 // Amplifier
  | 'p5js_simplifier'           // Listifier
  | 'tonejs_composer'           // Music Composer
  | 'piglatin'                  // Word Game
  | 'planetarizer'              // Planetarizer
  | 'renaissance'               // Renaissance
  | 'sensitive'                 // Sensitive
  | 'technicaldrawing'          // Technical
  | 'tellastory'                // Your Story
  | 'theopposite'               // On the Contrary!

/** Interception Preset Config with labels */
export interface InterceptionPresetConfig {
  /** The key of the label in i18n/en.ts (canvas.interceptionPresets.<id>);
   *  until 2026-10-10 the table carried the label in eight languages
   *  itself, outside the translation workflow (finding S-045 of the code review of 2026-10-10). */
  labelKey: string
}

/** Interception Presets - labels only, context loaded from backend on selection */
export const INTERCEPTION_PRESETS: Record<InterceptionPreset, InterceptionPresetConfig> = {
  user_defined: { labelKey: 'canvas.interceptionPresets.user_defined' },
  analog_photography_1870s: { labelKey: 'canvas.interceptionPresets.analog_photography_1870s' },
  analog_photography_1970s: { labelKey: 'canvas.interceptionPresets.analog_photography_1970s' },
  analogue_copy: { labelKey: 'canvas.interceptionPresets.analogue_copy' },
  bauhaus: { labelKey: 'canvas.interceptionPresets.bauhaus' },
  'clichéfilter_v2': { labelKey: 'canvas.interceptionPresets.clichéfilter_v2' },
  confucianliterati: { labelKey: 'canvas.interceptionPresets.confucianliterati' },
  cooked_negatives: { labelKey: 'canvas.interceptionPresets.cooked_negatives' },
  digital_photography: { labelKey: 'canvas.interceptionPresets.digital_photography' },
  forceful: { labelKey: 'canvas.interceptionPresets.forceful' },
  hunkydoryharmonizer: { labelKey: 'canvas.interceptionPresets.hunkydoryharmonizer' },
  jugendsprache: { labelKey: 'canvas.interceptionPresets.jugendsprache' },
  mad_world: { labelKey: 'canvas.interceptionPresets.mad_world' },
  one_world: { labelKey: 'canvas.interceptionPresets.one_world' },
  overdrive: { labelKey: 'canvas.interceptionPresets.overdrive' },
  p5js_simplifier: { labelKey: 'canvas.interceptionPresets.p5js_simplifier' },
  tonejs_composer: { labelKey: 'canvas.interceptionPresets.tonejs_composer' },
  piglatin: { labelKey: 'canvas.interceptionPresets.piglatin' },
  planetarizer: { labelKey: 'canvas.interceptionPresets.planetarizer' },
  renaissance: { labelKey: 'canvas.interceptionPresets.renaissance' },
  sensitive: { labelKey: 'canvas.interceptionPresets.sensitive' },
  technicaldrawing: { labelKey: 'canvas.interceptionPresets.technicaldrawing' },
  tellastory: { labelKey: 'canvas.interceptionPresets.tellastory' },
  theopposite: { labelKey: 'canvas.interceptionPresets.theopposite' }
}

// ============================================================================
// IMAGE EVALUATION PRESET TYPES
// ============================================================================

/**
 * The frame an Image Analysis node reads its picture in: one of the platform's
 * five reading frames (`data/readingFrames.ts`, the backend's own keys), or a
 * question of one's own (`custom`, in `imageEvaluationPrompt`).
 *
 * The node offers all five, the descriptive frame that the Flow and Image
 * Understanding offer included, and carries no list or labels of its own. The
 * names on screen are the platform's (`compare.vlmAnalysis.perspectives.<id>`).
 */
export type ImageEvaluationPreset = ReadingFrame | 'custom'

// ============================================================================
// RANDOM PROMPT TYPES
// ============================================================================

/** Random Prompt Preset Types */
export type RandomPromptPreset =
  | 'clean_image'  // Szenische Beschreibung (medienneutral)
  | 'photo'        // Fotografische Prompts mit Film-Typ
  | 'artform'      // Kunstform-Transformation
  | 'instruction'  // Kreative Transformation
  | 'language'     // Sprach-Vorschlag

/** Film types for photo preset */
export type PhotoFilmType =
  | 'random'
  | 'Kodachrome' | 'Ektachrome'
  | 'Portra 400' | 'Portra 800' | 'Ektar 100'
  | 'Fuji Pro 400H' | 'Fuji Superia' | 'CineStill 800T'
  | 'Ilford HP5' | 'Ilford Delta 400' | 'Ilford FP4' | 'Ilford Pan F' | 'Ilford XP2'
  | 'Tri-X 400'

/** Node type definition for the palette */
export interface NodeTypeDefinition {
  id: string
  type: StageType
  /** canvas.nodeTypes.<id>.label and .description in i18n/en.ts (finding S-045 of the code review of 2026-10-10). */
  labelKey: string
  descriptionKey: string
  color: string
  icon: string
  /** Whether this node type allows multiple instances */
  allowMultiple: boolean
  /** Whether this node is mandatory in workflows */
  mandatory: boolean
}

/**
 * Predefined node types for the canvas
 *
 * Module Types:
 * - Input: Text input source
 * - Interception: LLM selection (primary!) + interception config (optional override)
 * - Translation: Translation prompt + LLM selection
 * - Generation: Output configs (sd35, qwen, flux2, etc.)
 * - Collector: Fan-in collector for parallel outputs (Media Collector)
 *
 * IMPORTANT: Safety is NOT a node!
 * DevServer handles Stage 1 + Stage 3 safety automatically.
 */
export const NODE_TYPE_DEFINITIONS: NodeTypeDefinition[] = [
  {
    id: 'input',
    type: 'input',
    labelKey: 'canvas.nodeTypes.input.label',
    descriptionKey: 'canvas.nodeTypes.input.description',
    color: '#3b82f6', // blue
    icon: 'edit_square_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: false,
    mandatory: true
  },
  // Image Input Node
  {
    id: 'image_input',
    type: 'image_input',
    labelKey: 'canvas.nodeTypes.image_input.label',
    descriptionKey: 'canvas.nodeTypes.image_input.description',
    color: '#0ea5e9', // sky blue
    icon: 'add_photo_alternate_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Random Prompt Node with presets
  {
    id: 'random_prompt',
    type: 'random_prompt',
    labelKey: 'canvas.nodeTypes.random_prompt.label',
    descriptionKey: 'canvas.nodeTypes.random_prompt.description',
    color: '#ec4899', // pink
    icon: 'shuffle_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  {
    id: 'interception',
    type: 'interception',
    labelKey: 'canvas.nodeTypes.interception.label',
    descriptionKey: 'canvas.nodeTypes.interception.description',
    color: '#8b5cf6', // purple
    icon: 'cognition_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  {
    id: 'translation',
    type: 'translation',
    labelKey: 'canvas.nodeTypes.translation.label',
    descriptionKey: 'canvas.nodeTypes.translation.description',
    color: '#f59e0b', // amber
    icon: 'language_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Model Adaption Node - adapts prompt for specific media models
  {
    id: 'model_adaption',
    type: 'model_adaption',
    labelKey: 'canvas.nodeTypes.model_adaption.label',
    descriptionKey: 'canvas.nodeTypes.model_adaption.description',
    color: '#14b8a6', // teal
    icon: 'tune_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  {
    id: 'generation',
    type: 'generation',
    labelKey: 'canvas.nodeTypes.generation.label',
    descriptionKey: 'canvas.nodeTypes.generation.description',
    color: '#10b981', // emerald
    icon: 'brush_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: true
  },
  {
    id: 'collector',
    type: 'collector',
    labelKey: 'canvas.nodeTypes.collector.label',
    descriptionKey: 'canvas.nodeTypes.collector.description',
    color: '#06b6d4', // cyan
    icon: 'gallery_thumbnail_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: false,
    mandatory: true
  },
  // Unified Evaluation Node (covers evaluation and fork branching in one node)
  {
    id: 'evaluation',
    type: 'evaluation',
    labelKey: 'canvas.nodeTypes.evaluation.label',
    descriptionKey: 'canvas.nodeTypes.evaluation.description',
    color: '#f59e0b', // amber
    icon: 'checklist_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Image Evaluation Node (Vision-LLM analysis)
  {
    id: 'image_evaluation',
    type: 'image_evaluation',
    labelKey: 'canvas.nodeTypes.image_evaluation.label',
    descriptionKey: 'canvas.nodeTypes.image_evaluation.description',
    color: '#dc2626', // red
    icon: 'imagesmode_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Display Node (Terminal - no output)
  {
    id: 'display',
    type: 'display',
    labelKey: 'canvas.nodeTypes.display.label',
    descriptionKey: 'canvas.nodeTypes.display.description',
    color: '#10b981', // green
    icon: 'info_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Comparison Evaluator Node (Multi-input comparison)
  {
    id: 'comparison_evaluator',
    type: 'comparison_evaluator',
    labelKey: 'canvas.nodeTypes.comparison_evaluator.label',
    descriptionKey: 'canvas.nodeTypes.comparison_evaluator.description',
    color: '#f97316', // orange
    icon: 'analyze.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Seed Node for reproducible generation
  {
    id: 'seed',
    type: 'seed',
    labelKey: 'canvas.nodeTypes.seed.label',
    descriptionKey: 'canvas.nodeTypes.seed.description',
    color: '#6366f1', // indigo
    icon: 'potted_plant_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Resolution Node for width/height control
  {
    id: 'resolution',
    type: 'resolution',
    labelKey: 'canvas.nodeTypes.resolution.label',
    descriptionKey: 'canvas.nodeTypes.resolution.description',
    color: '#0ea5e9', // sky blue
    icon: 'display_settings_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Quality Node for steps/cfg control
  {
    id: 'quality',
    type: 'quality',
    labelKey: 'canvas.nodeTypes.quality.label',
    descriptionKey: 'canvas.nodeTypes.quality.description',
    color: '#84cc16', // lime
    icon: 'display_settings_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  }
]

// ============================================================================
// CANVAS NODE
// ============================================================================

/** A node instance on the canvas */
export interface CanvasNode {
  /** Unique node ID */
  id: string
  /** Node type (stage) */
  type: StageType
  /** X position on canvas */
  x: number
  /** Y position on canvas */
  y: number
  /** Node-specific configuration overrides */
  config: Record<string, unknown>

  // === Generation node config ===
  /** Selected output config ID for generation nodes (e.g., 'sd35_large', 'flux2_schnell') */
  configId?: string

  // === Interception node config ===
  /** Selected interception preset */
  interceptionPreset?: InterceptionPreset
  /** Selected LLM model ID (e.g., 'gpt-4o-mini', 'claude-3-haiku') */
  llmModel?: string
  /** Context/system prompt for the LLM (pedagogical transformation instructions) */
  contextPrompt?: string

  // === Translation node config ===
  /** Translation prompt/instructions; unset or empty is lib/translationDefaults.ts */
  translationPrompt?: string
  /** Target language: a code of lib/platformLanguages.ts, or a language named in
   *  free text ('' while that text is still to be written). Unset, an own
   *  translationPrompt names the language itself; with the default instruction
   *  it is lib/translationDefaults.ts */
  translationLanguage?: string

  // === Input node config ===
  /** User's prompt text (input node) */
  promptText?: string

  // === Display properties ===
  /** Custom width (optional, for resizable nodes like Collector) */
  width?: number
  /** Custom height (optional, for resizable nodes like Collector) */
  height?: number

  // === Unified Evaluation node config ===
  /** Evaluation type (pre-fills prompt template) */
  evaluationType?: 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom'
  /** Evaluation prompt/criteria description */
  evaluationPrompt?: string
  /** Output type for evaluation results (controls if score is requested) */
  outputType?: 'commentary' | 'score' | 'all'

  // === Feedback config (for Interception/Translation nodes) ===
  /** Maximum feedback iterations (default: 3) */
  maxFeedbackIterations?: number

  // === Display node config ===
  /** Display mode for visualization */
  displayMode?: 'popup' | 'inline' | 'toast'
  /** Display title */
  title?: string

  // === Random Prompt node config ===
  /** Selected preset (determines system prompt) */
  randomPromptPreset?: RandomPromptPreset
  /** LLM model for generation */
  randomPromptModel?: string
  /** Film type (only for 'photo' preset) */
  randomPromptFilmType?: PhotoFilmType
  /** Token limit for generated prompts (75 = CLIP-L, 500 = T5) */
  randomPromptTokenLimit?: 75 | 500

  // === Model Adaption node config ===
  /** Adaption preset (CLIP, T5, or none) */
  modelAdaptionPreset?: ModelAdaptionPreset

  // === Comparison Evaluator node config ===
  /** LLM model for comparison analysis */
  comparisonLlmModel?: string
  /** Evaluation criteria/goals for comparison */
  comparisonCriteria?: string

  // === Seed node config ===
  /** Seed mode: fixed value, random per execution, or increment for batch */
  seedMode?: 'fixed' | 'random' | 'increment'
  /** Fixed seed value (only used when seedMode is 'fixed') */
  seedValue?: number
  /** Base seed for increment mode (batch execution adds run_index) */
  seedBase?: number

  // === Resolution node config ===
  /** Image width in pixels */
  resolutionWidth?: number
  /** Image height in pixels */
  resolutionHeight?: number
  /** Resolution preset (square, portrait, landscape, custom) */
  resolutionPreset?: 'square_1024' | 'portrait_768x1344' | 'landscape_1344x768' | 'custom'

  // === Quality node config ===
  /** Number of inference steps */
  qualitySteps?: number
  /** CFG scale value */
  qualityCfg?: number

  // === Image Input node config ===
  /** Uploaded image data */
  imageData?: {
    image_id: string
    image_path: string
    preview_url: string
    original_size: [number, number]
    resized_size: [number, number]
  }

  // === Image Evaluation node config ===
  /** Vision model for image analysis (local only) */
  visionModel?: string
  /** Image evaluation preset (pedagogical framework) */
  imageEvaluationPreset?: ImageEvaluationPreset
  /** Custom evaluation prompt (only if preset is 'custom') */
  imageEvaluationPrompt?: string
}

// ============================================================================
// CONNECTION
// ============================================================================

/** A connection between two nodes */
export interface CanvasConnection {
  /** Source node ID */
  sourceId: string
  /** Target node ID */
  targetId: string
  /** Label for fork branches (e.g., 'true', 'false', 'approved', 'rejected') */
  label?: string
  /** Active state for conditional execution (managed by execution engine) */
  active?: boolean
}

// ============================================================================
// WORKFLOW
// ============================================================================

/** Loop configuration for feedback workflows */
export interface LoopConfig {
  enabled: boolean
  maxIterations: number
  /** Node ID to collect feedback from */
  feedbackFrom?: string
  /** Node ID to feed back into */
  feedbackTo?: string
  /** Conditional termination expression (future) */
  condition?: string
}

/** Automation settings */
export interface AutomationConfig {
  /** Seed control: 'global' applies same seed to all generation nodes, 'per-node' allows individual seeds */
  seedControl: 'global' | 'per-node'
  /** Global seed value (when seedControl is 'global') */
  globalSeed?: number
  /** Whether to automatically apply LoRA automation */
  loraInjection: boolean
}

/** Complete canvas workflow definition */
export interface CanvasWorkflow {
  /** Workflow ID */
  id: string
  /** Workflow name */
  name: string
  /** Workflow description */
  description?: string
  /**
   * The ready-made workflow this board was opened from (lib/canvasPresets.ts),
   * by its id. Travels into every file saved from it, so a file says where it
   * began; the board itself is a copy and changes nothing of the preset.
   */
  presetId?: string
  /** Workflow type identifier */
  type: 'canvas_workflow'
  /** All nodes in the workflow */
  nodes: CanvasNode[]
  /** All connections between nodes */
  connections: CanvasConnection[]
  /** Loop/feedback configuration */
  loops?: LoopConfig
  /** Automation settings */
  automation?: AutomationConfig
  /** Creation timestamp */
  createdAt?: string
  /** Last modified timestamp */
  updatedAt?: string
}

// ============================================================================
// EXECUTION
// ============================================================================

/** Execution status for a node */
export type NodeExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

/** Execution state for a single node */
export interface NodeExecutionState {
  nodeId: string
  status: NodeExecutionStatus
  output?: unknown
  error?: string
  startTime?: number
  endTime?: number
  durationMs?: number
}

/** Overall workflow execution state */
export interface WorkflowExecutionState {
  workflowId: string
  status: 'idle' | 'running' | 'completed' | 'failed' | 'interrupted'
  currentIteration: number
  totalIterations: number
  nodeStates: Map<string, NodeExecutionState>
  startTime?: number
  endTime?: number
}

/**
 * One item of the collector's output after a run: the node it came from, what
 * it produced, the error if any, and the run's settings beside it. Declared
 * here once; StageModule, CanvasWorkspace and the canvas store read it.
 */
export interface CollectorOutputItem {
  nodeId: string
  nodeType: string
  output: unknown
  error: string | null
  metadata?: {
    config_id?: string
    display_name?: string
    seed?: number
    steps?: number
    cfg?: number
  }
}

// ============================================================================
// CONFIG SELECTION
// ============================================================================

/** Available LLM model for interception/translation nodes */
export interface LLMModelSummary {
  /** Model ID (e.g., 'gpt-4o-mini', 'claude-3-haiku') */
  id: string
  /** Display name */
  name: string
  /** Provider (openai, anthropic, google, local) */
  provider: string
  /** Model capabilities/description */
  description?: string
  /** Whether this is the default/recommended model */
  isDefault?: boolean
}

/** Output/generation config summary (for palette selection) */
export interface OutputConfigSummary {
  id: string
  name: LocalizedString
  description: LocalizedString
  icon: string
  color: string
  mediaType: 'image' | 'audio' | 'video' | 'music' | 'text'
  backend: string
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get node type definition by type
 */
export function getNodeTypeDefinition(type: StageType): NodeTypeDefinition | undefined {
  return NODE_TYPE_DEFINITIONS.find(n => n.type === type)
}

/**
 * The node types a generation node reads as parameters: seed, resolution and
 * quality. They connect to its parameter input, never to the prompt inputs.
 */
export function isParameterType(type: StageType | undefined): boolean {
  return type === 'seed' || type === 'resolution' || type === 'quality'
}

/**
 * Check if a connection is valid between two node types
 *
 * Simplified validation - only structural constraints:
 * 1. Terminal nodes (collector, display) have no output
 * 2. Source nodes (input) have no input
 * 3. Seed nodes can only connect to generation nodes
 * 4. No self-loops
 *
 * Data type compatibility (text vs image) is checked at runtime by the backend.
 */
export function isValidConnection(sourceType: StageType, targetType: StageType): boolean {
  // Terminal nodes have no output connector
  const terminalNodes: StageType[] = ['collector', 'display']
  if (terminalNodes.includes(sourceType)) return false

  // Source nodes have no input connector
  const sourceNodes: StageType[] = ['input', 'image_input']
  if (sourceNodes.includes(targetType)) return false

  // Seed nodes can only connect to generation nodes
  if (sourceType === 'seed' && targetType !== 'generation') return false

  // Resolution and Quality nodes can only connect to generation nodes
  if (sourceType === 'resolution' && targetType !== 'generation') return false
  if (sourceType === 'quality' && targetType !== 'generation') return false

  // No self-loops (same node type connecting to itself is allowed, just not same instance)
  // This is handled elsewhere - same type is fine

  return true
}

/**
 * Generate a unique node ID
 */
export function generateNodeId(type: StageType): string {
  return `${type}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
}

/**
 * Create a default canvas workflow
 *
 * Default structure: Input → (user adds interception/generation) → Collector
 * Safety is handled automatically by DevServer.
 */
export function createDefaultWorkflow(): CanvasWorkflow {
  const inputNode: CanvasNode = {
    id: generateNodeId('input'),
    type: 'input',
    x: 100,
    y: 200,
    config: { source: 'text' }
  }

  const collectorNode: CanvasNode = {
    id: generateNodeId('collector'),
    type: 'collector',
    x: 900,
    y: 200,
    config: {}
  }

  return {
    id: `workflow_${Date.now()}`,
    // Empty until somebody names it. With a placeholder such as 'New Workflow'
    // every export of every board would be saved as `New_Workflow.json`.
    name: '',
    type: 'canvas_workflow',
    nodes: [inputNode, collectorNode],
    connections: [],
    automation: {
      seedControl: 'global',
      loraInjection: true
    }
  }
}

// ============================================================================
// RANDOM PROMPT PRESETS
// ============================================================================

/** Preset configuration for Random Prompt node */
export interface RandomPromptPresetConfig {
  /** canvas.randomPrompt.<id> in i18n/en.ts (finding S-045 of the code review of 2026-10-10). */
  labelKey: string
  systemPrompt: string
  userPromptTemplate: string
}

/** Random Prompt Presets with system prompts */
export const RANDOM_PROMPT_PRESETS: Record<RandomPromptPreset, RandomPromptPresetConfig> = {
  clean_image: {
    labelKey: 'canvas.randomPrompt.clean_image',
    systemPrompt: `You are an inventive creative. Your task is to invent a vivid, detailed image prompt.

IMPORTANT - Generate CLEAN, MEDIA-NEUTRAL images:
- NO camera or photographic references (no film, no camera, no lens)
- NO optical effects (no wide-angle, no telephoto, no macro)
- NO depth of field or bokeh
- NO motion blur or any blur effects
- NO "retro", "vintage", or nostalgic styling
- NO film grain, vignette, or post-processing artifacts

Think globally. Avoid cultural clichés.
Subject matter: scenes, objects, animals, nature, technology, culture, people, homes, family, work, holiday, urban, rural, trivia, intricate details.
Be verbose, provide rich visual details about colors, lighting, textures, composition, atmosphere.
Transform the prompt strictly following the context if provided.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER.`,
    userPromptTemplate: 'Generate a creative image prompt.'
  },
  photo: {
    labelKey: 'canvas.randomPrompt.photo',
    systemPrompt: `You are an inventive creative. Your task is to invent a REALISTIC photographic image prompt.

Think globally. Avoid cultural clichés. Avoid "retro" style descriptions.
Describe contemporary everyday motives: scenes, objects, animals, nature, tech, culture, people, homes, family, work, holiday, urban, rural, trivia, details.
Choose either unlikely, untypical or typical photographical sujets. Be verbose, provide intricate details.
Always begin your output with: "{film_description} of".
Transform the prompt strictly following the context if provided.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER.`,
    userPromptTemplate: 'Generate a creative photographic image prompt.'
  },
  artform: {
    labelKey: 'canvas.randomPrompt.artform',
    systemPrompt: `You generate artform transformation instructions from an artist practice perspective.

IMPORTANT: NEVER use "in the style of" - instead frame as artistic practice, technique, or creative process.

Good examples:
- "Render this as a Japanese Noh theatre performance"
- "Transform this into a Yoruba praise poem"
- "Compose this as a Maori chant"
- "Frame this message through Cubist fragmentation"
- "Present this as an Afro-futurist myth"
- "Choreograph this as a Bharatanatyam narrative"
- "Inscribe this as Egyptian hieroglyphics"
- "Express this through Aboriginal dot painting technique"

Think globally across all cultures and art practices.
Focus on the DOING - the artistic practice, not imitation.
Output ONLY the transformation instruction, nothing else.`,
    userPromptTemplate: 'Generate a creative artform transformation instruction.'
  },
  instruction: {
    labelKey: 'canvas.randomPrompt.instruction',
    systemPrompt: `You generate creative transformation instructions.
Your output is a single instruction that transforms content in an unusual, creative way.
Examples: nature language, theatrical play, nostalgic robot voice, rhythmic rap, animal fable, alien explanation, philosophical versions (Wittgenstein, Heidegger, Adorno), ancient manuscript, bedtime story for post-human child, internal monologue of a tree, forgotten folk song lyrics, spy messages, protest chant, underwater civilization dialect, extinct animal conversation, dream sequence, poetic weather forecast, love letter to future generation, etc.
Be wildly creative and unexpected.
Output ONLY the transformation instruction, nothing else.`,
    userPromptTemplate: 'Generate a creative transformation instruction.'
  },
  language: {
    labelKey: 'canvas.randomPrompt.language',
    systemPrompt: `You suggest a random language from around the world.
Choose from major world languages, regional languages, or less common languages.
Consider: European, Asian, African, Indigenous American, Pacific languages.
Output ONLY the language name in English, nothing else.
Example outputs: "Swahili", "Bengali", "Quechua", "Welsh", "Tagalog"`,
    userPromptTemplate: 'Suggest a random language.'
  }
}

/** Photo film type descriptions */
export const PHOTO_FILM_TYPES: Record<PhotoFilmType, string> = {
  random: '', // Will be selected at runtime
  'Kodachrome': 'a Kodachrome film slide',
  'Ektachrome': 'an Ektachrome film slide',
  'Portra 400': 'a Kodak Portra 400 color negative',
  'Portra 800': 'a Kodak Portra 800 color negative',
  'Ektar 100': 'a Kodak Ektar 100 color negative',
  'Fuji Pro 400H': 'a Fujifilm Pro 400H color negative',
  'Fuji Superia': 'a Fujifilm Superia color negative',
  'CineStill 800T': 'a CineStill 800T tungsten-balanced color negative',
  'Ilford HP5': 'an Ilford HP5 Plus black and white negative',
  'Ilford Delta 400': 'an Ilford Delta 400 black and white negative',
  'Ilford FP4': 'an Ilford FP4 Plus black and white negative',
  'Ilford Pan F': 'an Ilford Pan F Plus 50 black and white negative',
  'Ilford XP2': 'an Ilford XP2 Super chromogenic black and white negative',
  'Tri-X 400': 'a Kodak Tri-X 400 black and white negative'
}
