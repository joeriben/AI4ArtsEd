<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CanvasNode, LLMModelSummary, RandomPromptPreset, PhotoFilmType, ModelAdaptionPreset, InterceptionPreset } from '@/types/canvas'
import { getNodeTypeDefinition, RANDOM_PROMPT_PRESETS, PHOTO_FILM_TYPES, INTERCEPTION_PRESETS } from '@/types/canvas'
import { localized } from '@/i18n'

const { t, locale } = useI18n()

// Icon URL helper
function getIconUrl(iconPath: string): string {
  return new URL(`../../assets/icons/${iconPath}`, import.meta.url).href
}

/** Collector output item from execution */
interface CollectorOutputItem {
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

const props = defineProps<{
  node: CanvasNode
  selected: boolean
  /** Session 256: Highlighted state for Output Drawer click-to-highlight */
  highlighted?: boolean
  configName?: string
  configMediaType?: string
  llmModels?: LLMModelSummary[]
  /** Session 152: Available Vision models for image_evaluation */
  visionModels?: LLMModelSummary[]
  /** Execution results for this node (from store) */
  executionResult?: {
    type: string
    output: unknown
    error: string | null
    model?: string
  }
  /** Collector output (only for collector nodes) */
  collectorOutput?: CollectorOutputItem[]
  /** Session 135: Is this node currently active in bubble animation? */
  isActive?: boolean
}>()

const emit = defineEmits<{
  'mousedown': [e: MouseEvent]
  'start-connect': []
  'end-connect': []
  'end-connect-feedback': []
  'delete': []
  'select-config': []
  'update-llm': [llmModel: string]
  'update-context-prompt': [prompt: string]
  'update-translation-prompt': [prompt: string]
  'update-prompt-text': [text: string]
  'update-size': [width: number, height: number]
  'update-display-title': [title: string]
  'update-display-mode': [mode: 'popup' | 'inline' | 'toast']
  // Session 134 Refactored: Unified evaluation events
  'update-evaluation-type': [type: 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom']
  'update-evaluation-prompt': [prompt: string]
  'update-output-type': [outputType: 'commentary' | 'score' | 'all']
  'start-connect-labeled': [label: string]
  // Session 140: Random Prompt events
  'update-random-prompt-preset': [preset: string]
  'update-random-prompt-model': [model: string]
  'update-random-prompt-film-type': [filmType: string]
  'update-random-prompt-token-limit': [limit: number]
  // Session 145: Model Adaption event
  'update-model-adaption-preset': [preset: string]
  // Session 146: Interception Preset event
  'update-interception-preset': [preset: string, context: string]
  // Session 147: Comparison Evaluator events
  'update-comparison-llm': [model: string]
  'update-comparison-criteria': [criteria: string]
  'end-connect-input-1': []
  'end-connect-input-2': []
  'end-connect-input-3': []
  // Session 150: Seed node events
  'update-seed-mode': [mode: 'fixed' | 'random' | 'increment']
  'update-seed-value': [value: number]
  'update-seed-base': [base: number]
  // Session 151: Resolution node events
  'update-resolution-preset': [preset: 'square_1024' | 'portrait_768x1344' | 'landscape_1344x768' | 'custom']
  'update-resolution-width': [width: number]
  'update-resolution-height': [height: number]
  // Session 151: Quality node events
  'update-quality-steps': [steps: number]
  'update-quality-cfg': [cfg: number]
  // Session 152: Image Input events
  'update-image-data': [imageData: { image_id: string; image_path: string; preview_url: string; original_size: [number, number]; resized_size: [number, number] }]
  // Session 152: Image Evaluation events
  'update-vision-model': [model: string]
  'update-image-evaluation-preset': [preset: string]
  'update-image-evaluation-prompt': [prompt: string]
}>()

const nodeTypeDef = computed(() => getNodeTypeDefinition(props.node.type))
const nodeColor = computed(() => nodeTypeDef.value?.color || '#666')
const nodeIcon = computed(() => nodeTypeDef.value?.icon || '')
const nodeIconUrl = computed(() => {
  const icon = nodeTypeDef.value?.icon
  if (icon && icon.endsWith('.svg')) {
    return getIconUrl(icon)
  }
  return null
})
const nodeLabel = computed(() => {
  const def = nodeTypeDef.value
  if (!def) return props.node.type
  return localized(def.label, locale.value)
})

// Source nodes (input, image_input, seed, resolution, quality) have no input connector
// Generation and comparison_evaluator use their own multi-input connectors
const hasInputConnector = computed(() => !['input', 'image_input', 'comparison_evaluator', 'generation', 'seed', 'resolution', 'quality'].includes(props.node.type))
// Terminal nodes (collector, display) have no output connector
const hasOutputConnector = computed(() => !['collector', 'display'].includes(props.node.type))
// Session 147: Comparison evaluator has 3 numbered input connectors
const hasMultipleInputConnectors = computed(() => props.node.type === 'comparison_evaluator')
// Generation node has dual input connectors (primary prompt + optional secondary)
const hasGenerationDualInput = computed(() => props.node.type === 'generation')

// Node type checks
const isInput = computed(() => props.node.type === 'input')
const isRandomPrompt = computed(() => props.node.type === 'random_prompt')
const isInterception = computed(() => props.node.type === 'interception')
const isTranslation = computed(() => props.node.type === 'translation')
const isGeneration = computed(() => props.node.type === 'generation')
const isCollector = computed(() => props.node.type === 'collector')
const isDisplay = computed(() => props.node.type === 'display')
// Session 134 Refactored: Unified evaluation node
const isEvaluation = computed(() => props.node.type === 'evaluation')
// Session 145: Model Adaption node
const isModelAdaption = computed(() => props.node.type === 'model_adaption')
// Session 147: Comparison Evaluator node
const isComparisonEvaluator = computed(() => props.node.type === 'comparison_evaluator')
// Session 150: Seed node
const isSeed = computed(() => props.node.type === 'seed')
// Session 151: Resolution and Quality nodes
const isResolution = computed(() => props.node.type === 'resolution')
const isQuality = computed(() => props.node.type === 'quality')
// Session 152: Image Input and Image Evaluation nodes
const isImageInput = computed(() => props.node.type === 'image_input')
const isImageEvaluation = computed(() => props.node.type === 'image_evaluation')
const needsLLM = computed(() => isInterception.value || isTranslation.value || isEvaluation.value || isRandomPrompt.value || isComparisonEvaluator.value)
const hasCollectorOutput = computed(() => isCollector.value && props.collectorOutput && props.collectorOutput.length > 0)
// Feedback input for Interception/Translation (enables feedback loops)
const hasFeedbackInput = computed(() => isInterception.value || isTranslation.value)

// Check if node is properly configured
const isConfigured = computed(() => {
  if (isGeneration.value) return !!props.node.configId
  if (isRandomPrompt.value) return !!(props.node.randomPromptModel && props.node.randomPromptPreset)
  if (isComparisonEvaluator.value) return !!props.node.comparisonLlmModel
  if (needsLLM.value) return !!props.node.llmModel
  return true
})

const displayConfigName = computed(() => {
  if (props.configName) return props.configName
  if (props.node.configId) return props.node.configId
  return t('canvas.stage.configSelectPlaceholder')
})

// Output bubble: shows truncated output when node has executed
const bubbleContent = computed(() => {
  if (!props.executionResult?.output) return null
  const output = props.executionResult.output

  // Handle different output types
  if (typeof output === 'string') {
    return output.length > 60 ? output.slice(0, 60) + '...' : output
  }
  if (typeof output === 'object' && output !== null) {
    // Image/media output
    if ((output as any).url) {
      return (output as any).media_type === 'image' ? '🖼️' : '📦'
    }
    // Evaluation with metadata
    if ((output as any).metadata?.score !== undefined) {
      const meta = (output as any).metadata
      return `Score: ${meta.score}/10 ${meta.binary ? '✓' : '✗'}`
    }
    // Other object
    return JSON.stringify(output).slice(0, 40) + '...'
  }
  return String(output).slice(0, 60)
})

const showBubble = computed(() => {
  // Show bubble only when:
  // 1. Node is active in animation (or animation not running = isActive undefined)
  // 2. Node has output content
  // 3. Node is not a terminal (collector/display)
  const isAnimationActive = props.isActive !== undefined
  const shouldShow = isAnimationActive ? props.isActive : bubbleContent.value !== null
  return shouldShow && bubbleContent.value && !isCollector.value && !isDisplay.value
})

// Event handlers for inline editing
function onLLMChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-llm', select.value)
}

function onContextPromptChange(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  emit('update-context-prompt', textarea.value)
}

// Session 146: Interception Preset handler
async function onInterceptionPresetChange(event: Event) {
  const select = event.target as HTMLSelectElement
  const presetId = select.value as InterceptionPreset

  if (presetId === 'user_defined') {
    // User defined: emit empty context, let user fill in
    emit('update-interception-preset', presetId, '')
  } else {
    // Fetch context from backend
    try {
      const response = await fetch(`/api/interception/${presetId}`)
      if (response.ok) {
        const data = await response.json()
        const context = localized(data.context || {}, locale.value)
        emit('update-interception-preset', presetId, context || '')
      } else {
        // Fallback: just emit the preset ID with empty context
        emit('update-interception-preset', presetId, '')
      }
    } catch {
      emit('update-interception-preset', presetId, '')
    }
  }
}

function onTranslationPromptChange(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  emit('update-translation-prompt', textarea.value)
}

function onPromptTextChange(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  emit('update-prompt-text', textarea.value)
}

// Session 134 Refactored: Unified evaluation node handlers
function onEvaluationTypeChange(event: Event) {
  const select = event.target as HTMLSelectElement
  const newType = select.value as 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom'
  emit('update-evaluation-type', newType)

  // Auto-fill prompt based on type
  const prompt = getEvaluationPromptTemplate(newType)
  emit('update-evaluation-prompt', prompt)
}

function onEvaluationPromptChange(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  emit('update-evaluation-prompt', textarea.value)
}

function onOutputTypeChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-output-type', select.value as 'commentary' | 'score' | 'all')
}

function getEvaluationPromptTemplate(evalType: string): string {
  const templates: Record<string, { en: string; de: string }> = {
    fairness: {
      en: 'Check for stereotypes, bias, and fair representation. Evaluate whether this content reinforces harmful stereotypes or promotes diverse, equitable representation.',
      de: 'Prüfe auf Stereotype, Vorurteile und faire Repräsentation. Bewerte, ob dieser Inhalt schädliche Stereotype verstärkt oder vielfältige, gerechte Darstellung fördert.'
    },
    creativity: {
      en: 'Evaluate originality and creative quality. Check if the content shows genuine creativity or resembles generic stock imagery/text.',
      de: 'Bewerte Originalität und kreative Qualität. Prüfe, ob der Inhalt echte Kreativität zeigt oder generischen Stock-Bildern/-Texten ähnelt.'
    },
    bias: {
      en: 'Evaluate cultural sensitivity and representational bias. Check whether the input - contextually appropriate! - actively prevents cultural, ethnic, and gender-related biases of genAI systems and actively counters a western gaze, without becoming dogmatic.',
      de: 'Bewerte kulturelle Sensibilität und Repräsentations-Equity. Prüfe, ob der Input - situationsangemessen! - aktiv kulturelle, ethnische und genderbezogene Biases von genAI-Systemen verhindert und aktiv gegen einen western gaze vorgeht, ohne jedoch dogmatisch zu werden.'
    },
    quality: {
      en: 'Evaluate technical quality, composition, and clarity. Check for coherence, visual/textual quality, and overall execution.',
      de: 'Bewerte technische Qualität, Komposition und Klarheit. Prüfe auf Kohärenz, visuelle/textuelle Qualität und Gesamtumsetzung.'
    },
    custom: {
      en: 'Define your own evaluation criteria...',
      de: 'Definiere deine eigenen Bewertungskriterien...'
    }
  }

  const template = templates[evalType]
  if (!template) return t('canvas.stage.evaluationCriteriaFallback')
  return localized(template, locale.value)
}

// Session 140: Random Prompt node handlers
function onRandomPromptPresetChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-random-prompt-preset', select.value)
}

function onRandomPromptModelChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-random-prompt-model', select.value)
}

function onRandomPromptFilmTypeChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-random-prompt-film-type', select.value)
}

function onRandomPromptTokenLimitChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-random-prompt-token-limit', parseInt(select.value))
}

// Session 145: Model Adaption node handler
function onModelAdaptionPresetChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-model-adaption-preset', select.value)
}

// Session 147: Comparison Evaluator handlers
function onComparisonLlmChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-comparison-llm', select.value)
}

function onComparisonCriteriaChange(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  emit('update-comparison-criteria', textarea.value)
}

// Session 134: Display node handlers
function onDisplayTitleChange(event: Event) {
  const input = event.target as HTMLInputElement
  emit('update-display-title', input.value)
}

function onDisplayModeChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-display-mode', select.value as 'popup' | 'inline' | 'toast')
}

// Session 151: Parameter node handlers
function onSeedValueChange(event: Event) {
  const input = event.target as HTMLInputElement
  const value = parseInt(input.value)
  emit('update-seed-value', isNaN(value) ? 123456789 : value)
}

function onSeedBaseChange(event: Event) {
  const input = event.target as HTMLInputElement
  const value = parseInt(input.value)
  emit('update-seed-base', isNaN(value) ? 0 : value)
}

function onResolutionWidthChange(event: Event) {
  const input = event.target as HTMLInputElement
  const value = parseInt(input.value)
  emit('update-resolution-width', isNaN(value) ? 1024 : value)
}

function onResolutionHeightChange(event: Event) {
  const input = event.target as HTMLInputElement
  const value = parseInt(input.value)
  emit('update-resolution-height', isNaN(value) ? 1024 : value)
}

function onQualityStepsChange(event: Event) {
  const input = event.target as HTMLInputElement
  const value = parseInt(input.value)
  emit('update-quality-steps', isNaN(value) ? 25 : value)
}

function onQualityCfgChange(event: Event) {
  const input = event.target as HTMLInputElement
  const value = parseFloat(input.value)
  emit('update-quality-cfg', isNaN(value) ? 5.5 : value)
}

// Session 152: Image Input handlers
async function onImageUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch('/api/media/upload/image', {
      method: 'POST',
      body: formData
    })

    if (response.ok) {
      const data = await response.json()
      emit('update-image-data', {
        image_id: data.image_id,
        image_path: data.image_path,
        preview_url: `/api/media/uploads/${data.image_id}`,
        original_size: data.original_size,
        resized_size: data.resized_size
      })
    } else {
      console.error('[ImageInput] Upload failed:', response.statusText)
    }
  } catch (err) {
    console.error('[ImageInput] Upload error:', err)
  }
}

// Session 152: Image Evaluation handlers
function onVisionModelChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-vision-model', select.value)
}

function onImageEvaluationPresetChange(event: Event) {
  const select = event.target as HTMLSelectElement
  emit('update-image-evaluation-preset', select.value)
}

function onImageEvaluationPromptChange(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  emit('update-image-evaluation-prompt', textarea.value)
}

// Resize handling (for Collector nodes)
const isResizing = ref(false)
const resizeStartSize = ref({ width: 0, height: 0 })
const resizeStartPos = ref({ x: 0, y: 0 })
const currentResizeSize = ref({ width: 0, height: 0 })

function startResize(event: MouseEvent) {
  event.stopPropagation()
  event.preventDefault()

  isResizing.value = true
  resizeStartPos.value = { x: event.clientX, y: event.clientY }
  resizeStartSize.value = {
    width: props.node.width || 280,
    height: props.node.height || 200
  }
  currentResizeSize.value = { ...resizeStartSize.value }

  // Add global mouse event listeners
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
}

function handleResize(event: MouseEvent) {
  if (!isResizing.value) return

  const deltaX = event.clientX - resizeStartPos.value.x
  const deltaY = event.clientY - resizeStartPos.value.y

  currentResizeSize.value.width = Math.max(180, resizeStartSize.value.width + deltaX)
  currentResizeSize.value.height = Math.max(100, resizeStartSize.value.height + deltaY)
}

function stopResize() {
  if (isResizing.value) {
    // Emit final size on mouseup
    emit('update-size', currentResizeSize.value.width, currentResizeSize.value.height)
  }

  isResizing.value = false
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
}

// Computed dimensions (use custom size if set, or live resize size, otherwise auto)
const nodeWidth = computed(() => {
  if (isResizing.value) return `${currentResizeSize.value.width}px`
  if (props.node.width) return `${props.node.width}px`
  return undefined
})
const nodeHeight = computed(() => {
  if (isResizing.value) return `${currentResizeSize.value.height}px`
  if (props.node.height) return `${props.node.height}px`
  return undefined
})
</script>

<template>
  <div
    dir="ltr"
    class="stage-module"
    :class="{
      selected,
      highlighted,
      'needs-config': !isConfigured,
      'wide-module': needsLLM || isInput || hasCollectorOutput || isEvaluation || isDisplay,
      'resizable': isCollector || isDisplay
    }"
    :style="{
      left: `${node.x}px`,
      top: `${node.y}px`,
      '--node-color': nodeColor,
      width: nodeWidth,
      height: nodeHeight
    }"
    @mousedown.stop="emit('mousedown', $event)"
  >
    <!-- Input connector (normal) -->
    <div
      v-if="hasInputConnector"
      class="connector input"
      :data-node-id="node.id"
      data-connector="input"
      @mouseup.stop="emit('end-connect')"
    />

    <!-- Session 147: Multiple numbered input connectors for Comparison Evaluator -->
    <template v-if="hasMultipleInputConnectors">
      <div
        class="connector input input-1"
        :data-node-id="node.id"
        data-connector="input-1"
        @mouseup.stop="emit('end-connect-input-1')"
        title="Input 1"
      >
        <span class="connector-label">1</span>
      </div>
      <div
        class="connector input input-2"
        :data-node-id="node.id"
        data-connector="input-2"
        @mouseup.stop="emit('end-connect-input-2')"
        title="Input 2"
      >
        <span class="connector-label">2</span>
      </div>
      <div
        class="connector input input-3"
        :data-node-id="node.id"
        data-connector="input-3"
        @mouseup.stop="emit('end-connect-input-3')"
        title="Input 3"
      >
        <span class="connector-label">3</span>
      </div>
    </template>

    <!-- Generation: Dual input connectors (primary prompt + optional secondary tags/negative) -->
    <template v-if="hasGenerationDualInput">
      <div
        class="connector input input-1"
        :data-node-id="node.id"
        data-connector="input-1"
        @mouseup.stop="emit('end-connect-input-1')"
        title="Primary (Prompt)"
      >
        <span class="connector-label">1</span>
      </div>
      <div
        class="connector input input-2"
        :data-node-id="node.id"
        data-connector="input-2"
        @mouseup.stop="emit('end-connect-input-2')"
        title="Secondary (Tags/Negative)"
      >
        <span class="connector-label">2</span>
      </div>
    </template>

    <!-- Feedback input connector (for Interception/Translation nodes) -->
    <div
      v-if="hasFeedbackInput"
      class="connector feedback-input"
      :data-node-id="node.id"
      data-connector="feedback-input"
      @mouseup.stop="emit('end-connect-feedback')"
      :title="$t('canvas.stage.feedbackInputTitle')"
    >
      <span class="feedback-label">FB</span>
    </div>

    <!-- Node header -->
    <div class="module-header">
      <img
        v-if="nodeIconUrl"
        :src="nodeIconUrl"
        :alt="nodeLabel"
        class="module-icon-svg"
      />
      <span v-else class="module-icon">{{ nodeIcon }}</span>
      <span class="module-label">{{ nodeLabel }}</span>
      <button
        v-if="node.type !== 'collector'"
        class="delete-btn"
        @click.stop="emit('delete')"
        :title="$t('canvas.stage.deleteTitle')"
      >
        ×
      </button>
    </div>

    <!-- Node body -->
    <div class="module-body">

      <!-- INPUT NODE: Prompt text input (FIRST to ensure it matches) -->
      <template v-if="node.type === 'input'">
        <div class="field-group">
          <label class="field-label">Prompt</label>
          <textarea
            class="prompt-textarea"
            :value="node.promptText || ''"
            :placeholder="$t('canvas.stage.input.promptPlaceholder')"
            rows="4"
            @input="onPromptTextChange"
            @mousedown.stop
          />
        </div>
      </template>

      <!-- IMAGE_INPUT NODE: Image upload (Session 152) -->
      <template v-else-if="isImageInput">
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.imageInput.uploadLabel') }}</label>
          <!-- Preview if image uploaded -->
          <div v-if="node.imageData?.preview_url" class="image-preview">
            <img :src="node.imageData.preview_url" class="uploaded-image-thumb" />
            <span class="image-size">{{ node.imageData.resized_size?.[0] }} × {{ node.imageData.resized_size?.[1] }}</span>
          </div>
          <!-- Upload button -->
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            class="file-input"
            @change="onImageUpload"
            @mousedown.stop
          />
        </div>
      </template>

      <!-- RANDOM_PROMPT NODE: Preset + LLM + Film Type + Regenerate (Session 140) -->
      <template v-else-if="isRandomPrompt">
        <!-- Preset Selector -->
        <div class="field-group">
          <label class="field-label">Preset</label>
          <select
            class="llm-select"
            :value="node.randomPromptPreset || 'clean_image'"
            @change="onRandomPromptPresetChange"
            @mousedown.stop
          >
            <option
              v-for="(config, presetKey) in RANDOM_PROMPT_PRESETS"
              :key="presetKey"
              :value="presetKey"
            >
              {{ localized(config.label, locale) }}
            </option>
          </select>
        </div>

        <!-- Film Type (only for photo preset) -->
        <div v-if="node.randomPromptPreset === 'photo'" class="field-group">
          <label class="field-label">Film</label>
          <select
            class="llm-select"
            :value="node.randomPromptFilmType || 'random'"
            @change="onRandomPromptFilmTypeChange"
            @mousedown.stop
          >
            <option
              v-for="(desc, filmKey) in PHOTO_FILM_TYPES"
              :key="filmKey"
              :value="filmKey"
            >
              {{ filmKey }}
            </option>
          </select>
        </div>

        <!-- LLM Selector -->
        <div class="field-group">
          <label class="field-label">LLM</label>
          <select
            class="llm-select"
            :value="node.randomPromptModel || ''"
            @change="onRandomPromptModelChange"
            @mousedown.stop
          >
            <option value="" disabled>{{ $t('canvas.stage.selectLlmPlaceholder') }}</option>
            <option
              v-for="model in llmModels"
              :key="model.id"
              :value="model.id"
            >
              {{ model.name }}
            </option>
          </select>
        </div>

        <!-- Token Limit -->
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.randomPrompt.tokenLimit') }}</label>
          <select
            class="llm-select"
            :value="node.randomPromptTokenLimit || 75"
            @change="onRandomPromptTokenLimitChange"
            @mousedown.stop
          >
            <option :value="75">Short (&le;75 tokens)</option>
            <option :value="500">Long (&le;500 tokens)</option>
          </select>
        </div>

      </template>

      <!-- INTERCEPTION NODE: Preset dropdown + LLM dropdown + Context prompt (Session 146) -->
      <template v-else-if="isInterception">
        <div class="field-group">
          <label class="field-label">Interception</label>
          <select
            class="llm-select"
            :value="node.interceptionPreset || 'user_defined'"
            @change="onInterceptionPresetChange"
            @mousedown.stop
          >
            <option
              v-for="(config, presetKey) in INTERCEPTION_PRESETS"
              :key="presetKey"
              :value="presetKey"
            >
              {{ localized(config.label, locale) }}
            </option>
          </select>
        </div>
        <div class="field-group">
          <label class="field-label">LLM</label>
          <select
            class="llm-select"
            :value="node.llmModel || ''"
            @change="onLLMChange"
            @mousedown.stop
          >
            <option value="" disabled>{{ $t('canvas.stage.selectLlmPlaceholder') }}</option>
            <option
              v-for="model in llmModels"
              :key="model.id"
              :value="model.id"
            >
              {{ model.name }}
            </option>
          </select>
        </div>
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.interception.contextPromptLabel') }}</label>
          <textarea
            class="prompt-textarea"
            :value="node.contextPrompt || ''"
            :placeholder="$t('canvas.stage.interception.contextPromptPlaceholder')"
            rows="3"
            @input="onContextPromptChange"
            @mousedown.stop
          />
        </div>
      </template>

      <!-- TRANSLATION NODE: LLM dropdown + Translation prompt -->
      <template v-else-if="isTranslation">
        <div class="field-group">
          <label class="field-label">LLM</label>
          <select
            class="llm-select"
            :value="node.llmModel || ''"
            @change="onLLMChange"
            @mousedown.stop
          >
            <option value="" disabled>{{ $t('canvas.stage.selectLlmPlaceholder') }}</option>
            <option
              v-for="model in llmModels"
              :key="model.id"
              :value="model.id"
            >
              {{ model.name }}
            </option>
          </select>
        </div>
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.translation.translationPromptLabel') }}</label>
          <textarea
            class="prompt-textarea"
            :value="node.translationPrompt || ''"
            :placeholder="$t('canvas.stage.translation.translationPromptPlaceholder')"
            rows="2"
            @input="onTranslationPromptChange"
            @mousedown.stop
          />
        </div>
      </template>

      <!-- MODEL ADAPTION NODE: Media model preset selector (Session 145) -->
      <template v-else-if="isModelAdaption">
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.modelAdaption.targetModelLabel') }}</label>
          <select
            class="llm-select"
            :value="node.modelAdaptionPreset || 'none'"
            @change="onModelAdaptionPresetChange"
            @mousedown.stop
          >
            <option value="none">{{ $t('canvas.stage.modelAdaption.noAdaptionOption') }}</option>
            <option value="sd35">Stable Diffusion 3.5</option>
            <option value="flux">Flux</option>
            <option value="video">{{ $t('canvas.stage.modelAdaption.videoModelsOption') }}</option>
            <option value="audio">{{ $t('canvas.stage.modelAdaption.audioModelsOption') }}</option>
          </select>
        </div>
      </template>

      <!-- COMPARISON EVALUATOR NODE: Multi-input comparison with LLM (Session 147) -->
      <template v-else-if="isComparisonEvaluator">
        <div class="field-group">
          <label class="field-label">LLM</label>
          <select
            class="llm-select"
            :value="node.comparisonLlmModel || ''"
            @change="onComparisonLlmChange"
            @mousedown.stop
          >
            <option value="" disabled>{{ $t('canvas.stage.selectLlmPlaceholder') }}</option>
            <option
              v-for="model in llmModels"
              :key="model.id"
              :value="model.id"
            >
              {{ model.name }}
            </option>
          </select>
        </div>
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.comparisonEvaluator.criteriaLabel') }}</label>
          <textarea
            class="prompt-textarea"
            :value="node.comparisonCriteria || ''"
            :placeholder="$t('canvas.stage.comparisonEvaluator.criteriaPlaceholder')"
            rows="3"
            @input="onComparisonCriteriaChange"
            @mousedown.stop
          />
        </div>
        <div class="field-info">
          {{ $t('canvas.stage.comparisonEvaluator.infoText') }}
        </div>
      </template>

      <!-- GENERATION NODE: Config selector button with media type icon -->
      <template v-else-if="isGeneration">
        <button
          class="config-selector"
          :class="{ 'has-config': !!node.configId }"
          @click.stop="emit('select-config')"
        >
          <span class="config-media-icon">
            <!-- Image -->
            <svg v-if="configMediaType === 'image'" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
              <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Z"/>
            </svg>
            <!-- Video -->
            <svg v-else-if="configMediaType === 'video'" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
              <path d="m380-300 280-180-280-180v360ZM160-160q-33 0-56.5-23.5T80-240v-480q0-33 23.5-56.5T160-800h640q33 0 56.5 23.5T880-720v480q0 33-23.5 56.5T800-160H160Zm0-80h640v-480H160v480Zm0 0v-480 480Z"/>
            </svg>
            <!-- Audio / Music -->
            <svg v-else-if="configMediaType === 'audio' || configMediaType === 'music'" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
              <path d="M400-120q-66 0-113-47t-47-113q0-66 47-113t113-47q23 0 42.5 5.5T480-418v-422h240v160H560v400q0 66-47 113t-113 47Z"/>
            </svg>
            <!-- Text -->
            <svg v-else-if="configMediaType === 'text'" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
              <path d="M280-160v-520H80v-120h520v120H400v520H280Zm360 0v-320H520v-120h360v120H760v320H640Z"/>
            </svg>
            <!-- No config selected -->
            <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor" opacity="0.5">
              <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Z"/>
            </svg>
          </span>
          <span class="config-name-text">{{ displayConfigName }}</span>
          <span class="config-arrow">▼</span>
        </button>
      </template>

      <!-- SEED NODE: Seed mode and value configuration (Session 150) -->
      <template v-else-if="isSeed">
        <div class="seed-config">
          <div class="config-row">
            <label>{{ $t('canvas.stage.seed.modeLabel') }}</label>
            <select
              :value="node.seedMode || 'fixed'"
              @change="emit('update-seed-mode', ($event.target as HTMLSelectElement).value as 'fixed' | 'random' | 'increment')"
              @mousedown.stop
            >
              <option value="fixed">{{ $t('canvas.stage.seed.modeFixed') }}</option>
              <option value="random">{{ $t('canvas.stage.seed.modeRandom') }}</option>
              <option value="increment">Batch (+1)</option>
            </select>
          </div>
          <div v-if="node.seedMode === 'fixed' || !node.seedMode" class="config-row">
            <label>{{ $t('canvas.stage.seed.valueLabel') }}</label>
            <input
              type="number"
              :value="node.seedValue ?? 123456789"
              min="0"
              max="4294967295"
              @input="onSeedValueChange"
              @mousedown.stop
            />
          </div>
          <div v-if="node.seedMode === 'increment'" class="config-row">
            <label>{{ $t('canvas.stage.seed.baseLabel') }}</label>
            <input
              type="number"
              :value="node.seedBase ?? 0"
              min="0"
              @input="onSeedBaseChange"
              @mousedown.stop
            />
          </div>
        </div>
      </template>

      <!-- SESSION 151: RESOLUTION NODE -->
      <template v-else-if="isResolution">
        <div class="resolution-config">
          <div class="config-row">
            <label>Preset</label>
            <select
              :value="node.resolutionPreset || 'square_1024'"
              @change="emit('update-resolution-preset', ($event.target as HTMLSelectElement).value as 'square_1024' | 'portrait_768x1344' | 'landscape_1344x768' | 'custom')"
              @mousedown.stop
            >
              <option value="square_1024">1024 × 1024</option>
              <option value="portrait_768x1344">768 × 1344</option>
              <option value="landscape_1344x768">1344 × 768</option>
              <option value="custom">{{ $t('canvas.stage.resolution.customOption') }}</option>
            </select>
          </div>
          <div v-if="node.resolutionPreset === 'custom'" class="config-row">
            <label>{{ $t('canvas.stage.resolution.widthLabel') }}</label>
            <input
              type="number"
              :value="node.resolutionWidth ?? 1024"
              min="64"
              max="4096"
              step="64"
              @input="onResolutionWidthChange"
              @mousedown.stop
            />
          </div>
          <div v-if="node.resolutionPreset === 'custom'" class="config-row">
            <label>{{ $t('canvas.stage.resolution.heightLabel') }}</label>
            <input
              type="number"
              :value="node.resolutionHeight ?? 1024"
              min="64"
              max="4096"
              step="64"
              @input="onResolutionHeightChange"
              @mousedown.stop
            />
          </div>
          <div class="resolution-preview">
            {{ node.resolutionWidth ?? 1024 }} × {{ node.resolutionHeight ?? 1024 }}
          </div>
        </div>
      </template>

      <!-- SESSION 151: QUALITY NODE -->
      <template v-else-if="isQuality">
        <div class="quality-config">
          <div class="config-row">
            <label>Steps</label>
            <input
              type="number"
              :value="node.qualitySteps ?? 25"
              min="1"
              max="150"
              @input="onQualityStepsChange"
              @mousedown.stop
            />
          </div>
          <div class="config-row">
            <label>CFG</label>
            <input
              type="number"
              :value="node.qualityCfg ?? 5.5"
              min="0"
              max="30"
              step="0.5"
              @input="onQualityCfgChange"
              @mousedown.stop
            />
          </div>
        </div>
      </template>

      <!-- COLLECTOR NODE: Session 256 — Badge only, full output in Output Drawer -->
      <template v-else-if="node.type === 'collector'">
        <div v-if="collectorOutput && collectorOutput.length > 0" class="collector-badge-container">
          <span class="collector-badge">
            {{ collectorOutput.length }} {{ collectorOutput.length === 1 ? 'item' : 'items' }}
          </span>
        </div>
        <div v-else class="collector-empty">
          <span class="module-type-info">
            {{ $t('canvas.stage.collector.emptyText') }}
          </span>
        </div>
      </template>

      <!-- EVALUATION NODE: Unified evaluation with optional branching -->
      <template v-else-if="isEvaluation">
        <!-- Evaluation Type -->
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.evaluation.typeLabel') }}</label>
          <select
            class="llm-select"
            :value="node.evaluationType || 'custom'"
            @change="onEvaluationTypeChange"
            @mousedown.stop
          >
            <option value="fairness">Fairness</option>
            <option value="creativity">{{ $t('canvas.stage.evaluation.typeCreativity') }}</option>
            <option value="bias">Bias</option>
            <option value="quality">{{ $t('canvas.stage.evaluation.typeQuality') }}</option>
            <option value="custom">{{ $t('canvas.stage.evaluation.typeCustom') }}</option>
          </select>
        </div>

        <!-- LLM Selection -->
        <div class="field-group">
          <label class="field-label">LLM</label>
          <select
            class="llm-select"
            :value="node.llmModel || ''"
            @change="onLLMChange"
            @mousedown.stop
          >
            <option value="" disabled>{{ $t('canvas.stage.selectLlmPlaceholder') }}</option>
            <option
              v-for="model in llmModels"
              :key="model.id"
              :value="model.id"
            >
              {{ model.name }}
            </option>
          </select>
        </div>

        <!-- Evaluation Criteria -->
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.evaluation.criteriaLabel') }}</label>
          <textarea
            class="prompt-textarea"
            :value="node.evaluationPrompt || getEvaluationPromptTemplate(node.evaluationType || 'custom')"
            rows="3"
            @input="onEvaluationPromptChange"
            @mousedown.stop
          />
        </div>

        <!-- Output Type (score optional) -->
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.evaluation.outputTypeLabel') }}</label>
          <select
            class="llm-select"
            :value="node.outputType || 'commentary'"
            @change="onOutputTypeChange"
            @mousedown.stop
          >
            <option value="commentary">{{ $t('canvas.stage.evaluation.outputCommentary') }}</option>
            <option value="score">{{ $t('canvas.stage.evaluation.outputScore') }}</option>
            <option value="all">{{ $t('canvas.stage.evaluation.outputAll') }}</option>
          </select>
        </div>

      </template>

      <!-- IMAGE_EVALUATION NODE: Vision-LLM analysis (Session 152) -->
      <template v-else-if="isImageEvaluation">
        <!-- Vision Model Selection -->
        <div class="field-group">
          <label class="field-label">Vision Model</label>
          <select
            class="llm-select"
            :value="node.visionModel || ''"
            @change="onVisionModelChange"
            @mousedown.stop
          >
            <option value="" disabled>{{ $t('canvas.stage.imageEvaluation.visionModelPlaceholder') }}</option>
            <option
              v-for="model in visionModels"
              :key="model.id"
              :value="model.id"
            >
              {{ model.name }}
            </option>
          </select>
        </div>

        <!-- Analysis Framework/Preset -->
        <div class="field-group">
          <label class="field-label">{{ $t('canvas.stage.imageEvaluation.frameworkLabel') }}</label>
          <select
            class="llm-select"
            :value="node.imageEvaluationPreset || 'bildwissenschaftlich'"
            @change="onImageEvaluationPresetChange"
            @mousedown.stop
          >
            <option value="bildwissenschaftlich">{{ $t('canvas.stage.imageEvaluation.frameworkPanofsky') }}</option>
            <option value="bildungstheoretisch">{{ $t('canvas.stage.imageEvaluation.frameworkEducational') }}</option>
            <option value="ethisch">{{ $t('canvas.stage.imageEvaluation.frameworkEthical') }}</option>
            <option value="kritisch">{{ $t('canvas.stage.imageEvaluation.frameworkCritical') }}</option>
            <option value="custom">{{ $t('canvas.stage.imageEvaluation.frameworkCustom') }}</option>
          </select>
        </div>

        <!-- Custom Prompt (only if preset is 'custom') -->
        <div v-if="node.imageEvaluationPreset === 'custom'" class="field-group">
          <label class="field-label">{{ $t('canvas.stage.imageEvaluation.customPromptLabel') }}</label>
          <textarea
            class="prompt-textarea"
            :value="node.imageEvaluationPrompt || ''"
            :placeholder="$t('canvas.stage.imageEvaluation.customPromptPlaceholder')"
            rows="4"
            @input="onImageEvaluationPromptChange"
            @mousedown.stop
          />
        </div>
      </template>

      <!-- PREVIEW NODE: Shows content inline (pass-through) -->
      <template v-else-if="isDisplay">
        <div v-if="executionResult?.output" class="preview-content">
          <!-- Text preview (full text, scrollable) -->
          <template v-if="typeof executionResult.output === 'string'">
            <div class="preview-text">
              {{ executionResult.output }}
            </div>
          </template>
          <!-- Media preview (image/video) -->
          <template v-else-if="typeof executionResult.output === 'object' && (executionResult.output as any)?.url">
            <img
              v-if="(executionResult.output as any).media_type === 'image' || !(executionResult.output as any).media_type"
              :src="(executionResult.output as any).url"
              class="preview-image"
              :alt="$t('canvas.stage.display.imageAlt')"
            />
            <div v-else class="preview-media-info">
              {{ (executionResult.output as any).media_type }}: {{ (executionResult.output as any).url }}
            </div>
          </template>
          <template v-else-if="executionResult.output != null">
            <div class="preview-text">
              {{ JSON.stringify(executionResult.output).slice(0, 100) }}...
            </div>
          </template>
        </div>
        <div v-else-if="!executionResult" class="preview-empty">
          <span class="module-type-info">
            {{ $t('canvas.stage.display.emptyText') }}
          </span>
        </div>
      </template>

      <!-- Other node types -->
      <template v-else>
        <span class="module-type-info">{{ node.type }}</span>
      </template>
    </div>

    <!-- Output connector (standard single output, not for evaluation nodes which have 3 ports) -->
    <div
      v-if="hasOutputConnector && !isEvaluation"
      class="connector output"
      :data-node-id="node.id"
      data-connector="output"
      @mousedown.stop="emit('start-connect')"
    />

    <!-- Output bubble: shows data flowing through -->
    <div v-if="showBubble" class="output-bubble">
      <span class="bubble-content">{{ bubbleContent }}</span>
    </div>

    <!-- Evaluation outputs: pass + commentary on RIGHT, fail/FB on LEFT -->
    <div
      v-if="isEvaluation"
      class="connector output-pass"
      :data-node-id="node.id"
      data-connector="output-pass"
      @mousedown.stop="emit('start-connect-labeled', 'pass')"
      :title="$t('canvas.stage.evaluation.evalPassTitle')"
    >
      <span class="connector-label">&#x2713;</span>
    </div>
    <div
      v-if="isEvaluation"
      class="connector output-fail"
      :data-node-id="node.id"
      data-connector="output-fail"
      @mousedown.stop="emit('start-connect-labeled', 'fail')"
      :title="$t('canvas.stage.evaluation.evalFailTitle')"
    >
      <span class="connector-label">FB</span>
    </div>
    <div
      v-if="isEvaluation"
      class="connector output-commentary"
      :data-node-id="node.id"
      data-connector="output-commentary"
      @mousedown.stop="emit('start-connect-labeled', 'commentary')"
      :title="$t('canvas.stage.evaluation.evalCommentaryTitle')"
    >
      <span class="connector-label">&rarr;</span>
    </div>

    <!-- Resize handle (only for collector nodes) -->
    <div
      v-if="isCollector || isDisplay"
      class="resize-handle"
      @mousedown.stop="startResize"
      :title="$t('canvas.stage.resizeTitle')"
    />
  </div>
</template>

<style scoped>
.stage-module {
  position: absolute;
  min-width: 180px;
  background: #141414;
  border: 2px solid var(--node-color);
  border-radius: 8px;
  cursor: move;
  user-select: none;
  z-index: 1;
  /* Note: overflow visible to allow bubbles, but module-body handles content overflow */
}

.stage-module.wide-module {
  min-width: 280px;
}

.stage-module.selected {
  box-shadow: 0 0 0 2px var(--node-color), 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

/* Session 256: Pulsing glow for Output Drawer click-to-highlight */
.stage-module.highlighted {
  animation: highlight-pulse 2s ease-in-out;
  z-index: 11;
}

@keyframes highlight-pulse {
  0% { box-shadow: 0 0 0 2px var(--node-color), 0 0 20px 4px var(--node-color); }
  50% { box-shadow: 0 0 0 4px var(--node-color), 0 0 30px 8px var(--node-color); }
  100% { box-shadow: 0 0 0 2px var(--node-color), 0 0 0 0 transparent; }
}

.stage-module.needs-config {
  border-style: dashed;
}

.module-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--node-color);
  border-radius: 5px 5px 0 0;
}

.module-icon {
  font-size: 1rem;
}

.module-icon-svg {
  width: 18px;
  height: 18px;
  filter: brightness(0) invert(1); /* Make SVG white */
}

.module-label {
  flex: 1;
  font-size: 0.75rem;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.delete-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.delete-btn:hover {
  color: white;
}

.module-body {
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow: auto;  /* Scroll when content exceeds container */
  flex: 1;  /* Fill available space in resizable nodes */
  min-height: 0;  /* Allow shrinking below content size */
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field-label {
  font-size: 0.625rem;
  font-weight: 500;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-info {
  font-size: 0.65rem;
  color: #94a3b8;
  font-style: italic;
  padding: 0.25rem 0;
}

.llm-select {
  width: 100%;
  padding: 0.375rem 0.5rem;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.75rem;
  cursor: pointer;
}

.llm-select:hover {
  border-color: var(--node-color);
}

.llm-select:focus {
  outline: none;
  border-color: var(--node-color);
}

.prompt-textarea {
  width: 100%;
  padding: 0.375rem 0.5rem;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.6875rem;
  font-family: inherit;
  resize: vertical;
  min-height: 40px;
}

.prompt-textarea:hover {
  border-color: var(--node-color);
}

.prompt-textarea:focus {
  outline: none;
  border-color: var(--node-color);
}

.prompt-textarea::placeholder {
  color: #475569;
}

.config-selector {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #94a3b8;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}

.config-media-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.config-media-icon svg {
  display: block;
}

.config-name-text {
  flex: 1;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-selector:hover {
  border-color: var(--node-color);
  color: #e2e8f0;
}

.config-selector.has-config {
  color: #e2e8f0;
  border-color: var(--node-color);
}

.config-arrow {
  font-size: 0.6rem;
  opacity: 0.7;
}

/* Session 150: Seed node config */
.seed-config {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.seed-config .config-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.seed-config label {
  font-size: 0.6875rem;
  color: #94a3b8;
  min-width: 40px;
}

.seed-config select,
.seed-config input {
  flex: 1;
  padding: 0.375rem 0.5rem;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.75rem;
}

.seed-config select:focus,
.seed-config input:focus {
  outline: none;
  border-color: var(--node-color);
}

.seed-config input[type="number"] {
  -moz-appearance: textfield;
}

.seed-config input[type="number"]::-webkit-outer-spin-button,
.seed-config input[type="number"]::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* Session 151: Resolution node config */
.resolution-config {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.resolution-config .config-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.resolution-config label {
  font-size: 0.6875rem;
  color: #94a3b8;
  min-width: 40px;
}

.resolution-config select,
.resolution-config input {
  flex: 1;
  padding: 0.375rem 0.5rem;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.75rem;
}

.resolution-config select:focus,
.resolution-config input:focus {
  outline: none;
  border-color: var(--node-color);
}

.resolution-preview {
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  padding: 0.25rem;
  background: #0a0a0a;
  border-radius: 4px;
}

/* Session 151: Quality node config */
.quality-config {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.quality-config .config-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.quality-config label {
  font-size: 0.6875rem;
  color: #94a3b8;
  min-width: 40px;
}

.quality-config input {
  flex: 1;
  padding: 0.375rem 0.5rem;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.75rem;
}

.quality-config input:focus {
  outline: none;
  border-color: var(--node-color);
}

.module-type-info {
  font-size: 0.6875rem;
  color: #64748b;
}

.connector {
  position: absolute;
  width: 14px;
  height: 14px;
  background: #141414;
  border: 2px solid var(--node-color);
  border-radius: 50%;
  cursor: crosshair;
  z-index: 2;
}

.connector.input {
  left: -7px;
  top: 24px;  /* Fixed position in header area */
  transform: translateY(-50%);
}

/* Session 147: Numbered input connectors for Comparison Evaluator */
.connector.input-1 {
  left: -7px;
  top: 24px;
  transform: translateY(-50%);
}

.connector.input-2 {
  left: -7px;
  top: 44px;
  transform: translateY(-50%);
}

.connector.input-3 {
  left: -7px;
  top: 64px;
  transform: translateY(-50%);
}

.connector-label {
  position: absolute;
  left: -14px;
  font-size: 0.6rem;
  font-weight: 600;
  color: #94a3b8;
}

.connector.output {
  right: -7px;
  top: 24px;  /* Fixed position in header area */
  transform: translateY(-50%);
}

.connector:hover {
  background: var(--node-color);
}

/* Feedback input connector (for loops) — filled red circle with FB label */
.connector.feedback-input {
  right: -7px;
  top: 44px;  /* Below main output connector in header area */
  transform: translateY(-50%);
  background: #ef4444; /* red */
  border-color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
}

.connector.feedback-input:hover {
  background: #ef4444;
  transform: translateY(-50%) scale(1.2);
  box-shadow: 0 0 8px #ef4444;
}

/* Output bubble: shows data flowing through the node */
.output-bubble {
  position: absolute;
  right: -12px;
  top: 40px;
  transform: translateX(100%);
  background: rgba(59, 130, 246, 0.95);
  color: white;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.6875rem;
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  z-index: 20;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  animation: bubble-appear 0.3s ease-out;
  pointer-events: none;
}

.output-bubble::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 50%;
  transform: translateY(-50%);
  border: 6px solid transparent;
  border-right-color: rgba(59, 130, 246, 0.95);
}

.bubble-content {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}

@keyframes bubble-appear {
  from {
    opacity: 0;
    transform: translateX(100%) scale(0.8);
  }
  to {
    opacity: 1;
    transform: translateX(100%) scale(1);
  }
}

.feedback-label {
  font-size: 0.5rem;
  font-weight: 700;
  color: white;
  pointer-events: none;
  user-select: none;
  line-height: 1;
}

/* Collector node styles */
.collector-results {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  /* Auto-resize: no max-height constraint */
  overflow-y: auto;
}

.collector-item {
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 0.5rem;
}

.collector-item.has-error {
  border-color: #ef4444;
}

.collector-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.item-type {
  font-size: 0.625rem;
  font-weight: 500;
  color: #64748b;
  text-transform: uppercase;
}

.item-error-badge {
  background: #ef4444;
  color: white;
  font-size: 0.625rem;
  font-weight: bold;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.collector-item-content {
  font-size: 0.6875rem;
  color: #e2e8f0;
  word-break: break-word;
  white-space: pre-wrap;
}

.error-text {
  color: #ef4444;
}

/* Session 256: Collector badge (replaces inline results) */
.collector-badge-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
}

.collector-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  background: #3b82f6;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  color: white;
}

.collector-empty {
  text-align: center;
  padding: 0.5rem;
}

.collector-image {
  max-width: 100%;
  border-radius: 4px;
  margin-top: 0.25rem;
  display: block;
}

.collector-media-info {
  font-size: 0.625rem;
  color: #94a3b8;
  margin-top: 0.25rem;
}

.collector-image-info {
  font-size: 0.625rem;
  color: #64748b;
  margin-top: 0.25rem;
}

/* Resize handle */
.resize-handle {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  background: linear-gradient(135deg, transparent 50%, var(--node-color) 50%);
  opacity: 0.5;
  transition: opacity 0.15s;
  z-index: 3;
}

.resize-handle:hover {
  opacity: 1;
}

.stage-module.resizable {
  /* Allow custom dimensions but constrain max-width/height */
  width: auto;
  height: auto;
  max-width: 400px;   /* Prevent expanding beyond reasonable width */
  max-height: 600px;  /* Session 141: Prevent extremely tall nodes */
  display: flex;
  flex-direction: column;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

/* Session 134 Refactored: Evaluation result display with 3 outputs */
.evaluation-result {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 4px;
  border-left: 3px solid #f59e0b;
}

.eval-metadata {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(245, 158, 11, 0.2);
}

.eval-score,
.eval-binary,
.eval-path {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
}

.eval-label {
  font-weight: 600;
  color: #f59e0b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.625rem;
}

.eval-value {
  color: #e2e8f0;
  font-weight: 500;
}

.eval-value.pass {
  color: #10b981;
}

.eval-value.fail {
  color: #ef4444;
}

.eval-commentary,
.eval-active-output {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.eval-active-output {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(245, 158, 11, 0.2);
}

.eval-text {
  font-size: 0.75rem;
  color: #cbd5e1;
  line-height: 1.4;
  margin: 0;
  white-space: pre-wrap;
  max-height: none;  /* Full text visible, container scrolls */
  overflow-y: visible;
}

/* Display node info */
/* Session 134 Refactored: Preview node inline display */
.preview-content {
  padding: 0.5rem;
  background: rgba(16, 185, 129, 0.1);
  border-radius: 4px;
  border-left: 3px solid #10b981;
  max-height: none;  /* Node is resizable, no fixed limit */
  overflow-y: auto;
}

.preview-text {
  font-size: 0.75rem;
  color: #cbd5e1;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
}

.preview-image {
  max-width: 100%;
  max-height: 150px;
  border-radius: 4px;
  display: block;
}

.preview-media-info {
  font-size: 0.625rem;
  color: #94a3b8;
  font-style: italic;
}

.preview-empty {
  padding: 0.5rem;
  text-align: center;
}

.preview-empty .module-type-info {
  font-size: 0.625rem;
  color: #64748b;
  font-style: italic;
}

/* Session 152: Image Input node styles */
.image-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem;
  background: rgba(14, 165, 233, 0.1);
  border-radius: 4px;
  border: 1px dashed #0ea5e9;
  margin-bottom: 0.5rem;
}

.uploaded-image-thumb {
  max-width: 100%;
  max-height: 100px;
  border-radius: 4px;
  object-fit: contain;
}

.image-size {
  font-size: 0.625rem;
  color: #94a3b8;
}

.file-input {
  width: 100%;
  font-size: 0.75rem;
  color: #e2e8f0;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 0.375rem;
  cursor: pointer;
}

.file-input::file-selector-button {
  background: #334155;
  color: #e2e8f0;
  border: none;
  border-radius: 3px;
  padding: 0.25rem 0.5rem;
  margin-right: 0.5rem;
  cursor: pointer;
  font-size: 0.75rem;
}

.file-input::file-selector-button:hover {
  background: #475569;
}

/* Evaluation outputs: pass + commentary on RIGHT, fail/FB on LEFT */
.connector.output-pass {
  right: -7px;
  top: 24px;
  transform: translateY(-50%);
  background: #10b981; /* green - pass */
  border-color: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
}

.connector.output-fail {
  left: -7px;
  top: 44px;
  transform: translateY(-50%);
  background: #ef4444; /* red - fail/feedback (backward channel) */
  border-color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
}

.connector.output-commentary {
  right: -7px;
  top: 44px;
  transform: translateY(-50%);
  background: #06b6d4; /* cyan - commentary */
  border-color: #06b6d4;
  display: flex;
  align-items: center;
  justify-content: center;
}

.connector.output-pass .connector-label,
.connector.output-fail .connector-label,
.connector.output-commentary .connector-label {
  position: static;
  left: auto;
  font-size: 0.5rem;
  font-weight: 700;
  color: white;
  user-select: none;
  pointer-events: none;
  line-height: 1;
}

.connector.output-pass:hover,
.connector.output-fail:hover,
.connector.output-commentary:hover {
  transform: translateY(-50%) scale(1.2);
  box-shadow: 0 0 8px currentColor;
}
</style>
