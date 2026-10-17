/**
 * What a Canvas node of a type carries when it is laid on the board: the
 * configured language model for the nodes that write, and the starting values
 * of the parameter nodes.
 *
 * It stood inside `addNode` (stores/canvas.ts) until the ready-made workflows
 * (lib/canvasPresets.ts) had to give their nodes the same defaults wherever
 * the file names nothing of its own (docs/ELEMENT_STRUCTURE_REGISTRY.md).
 */
import type { CanvasNode, LLMModelSummary, StageType } from '@/types/canvas'

const WRITING_NODES: StageType[] = ['random_prompt', 'interception', 'translation', 'evaluation', 'comparison_evaluator']

export function nodeDefaults(type: StageType, llmModels: readonly LLMModelSummary[]): Partial<CanvasNode> {
  const defaults: Partial<CanvasNode> = {}

  // Set default LLM for LLM-based nodes
  if (WRITING_NODES.includes(type)) {
    const defaultModel = llmModels.find(m => m.isDefault) || llmModels[0]
    if (defaultModel) {
      if (type === 'random_prompt') {
        defaults.randomPromptModel = defaultModel.id
        defaults.randomPromptPreset = 'clean_image' // Default preset
        defaults.randomPromptTokenLimit = 75 // Default: short (CLIP-L)
      } else if (type === 'comparison_evaluator') {
        defaults.comparisonLlmModel = defaultModel.id
      } else {
        defaults.llmModel = defaultModel.id
      }
    }
  }

  // Set defaults for parameter nodes
  if (type === 'resolution') {
    defaults.resolutionPreset = 'square_1024'
    defaults.resolutionWidth = 1024
    defaults.resolutionHeight = 1024
  } else if (type === 'quality') {
    defaults.qualitySteps = 25
    defaults.qualityCfg = 5.5
  }

  return defaults
}
