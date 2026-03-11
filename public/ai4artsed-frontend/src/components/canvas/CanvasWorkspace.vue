<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import StageModule from './StageModule.vue'
import ConnectionLine from './ConnectionLine.vue'
import type { CanvasNode, CanvasConnection, StageType, LLMModelSummary, OutputConfigSummary } from '@/types/canvas'
import { localized } from '@/i18n'

const { locale } = useI18n()

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
  nodes: CanvasNode[]
  connections: CanvasConnection[]
  selectedNodeId: string | null
  connectingFromId: string | null
  mousePosition: { x: number; y: number }
  llmModels: LLMModelSummary[]
  /** Session 152: Vision models for image_evaluation nodes */
  visionModels?: LLMModelSummary[]
  /** Execution results per node (nodeId -> result) */
  executionResults?: Record<string, {
    type: string
    output: unknown
    error: string | null
    model?: string
  }>
  /** Collector output for collector nodes */
  collectorOutput?: CollectorOutputItem[]
  /** Available output configs for generation nodes */
  outputConfigs?: OutputConfigSummary[]
  /** Session 135: Active node for bubble animation */
  activeNodeId?: string | null
  /** Label of the connector being dragged (for color + position of temp connection) */
  connectingLabel?: string | null
  /** Session 256: Highlighted node for Output Drawer click-to-highlight */
  highlightedNodeId?: string | null
}>()

/**
 * Get config info for a node's configId
 */
function getConfigInfo(configId: string | undefined): { name: string; mediaType: string } | undefined {
  if (!configId || !props.outputConfigs) return undefined
  const config = props.outputConfigs.find(c => c.id === configId)
  if (!config) return undefined
  return {
    name: localized(config.name, locale.value),
    mediaType: config.mediaType
  }
}

const emit = defineEmits<{
  'select-node': [id: string | null]
  'update-node-position': [id: string, x: number, y: number]
  'delete-node': [id: string]
  'add-connection': [sourceId: string, targetId: string]
  'delete-connection': [sourceId: string, targetId: string]
  'start-connection': [nodeId: string, label?: string]
  'cancel-connection': []
  'complete-connection': [targetId: string]
  'complete-connection-feedback': [targetId: string]
  'update-mouse-position': [x: number, y: number]
  'add-node-at': [type: StageType, x: number, y: number]
  'select-config': [nodeId: string]
  'update-node-llm': [nodeId: string, llmModel: string]
  'update-node-context-prompt': [nodeId: string, prompt: string]
  'update-node-translation-prompt': [nodeId: string, prompt: string]
  'update-node-prompt-text': [nodeId: string, text: string]
  'update-node-size': [nodeId: string, width: number, height: number]
  'update-node-display-title': [nodeId: string, title: string]
  'update-node-display-mode': [nodeId: string, mode: 'popup' | 'inline' | 'toast']
  // Session 134 Refactored: Unified evaluation events
  'update-node-evaluation-type': [nodeId: string, type: 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom']
  'update-node-evaluation-prompt': [nodeId: string, prompt: string]
  'update-node-output-type': [nodeId: string, outputType: 'commentary' | 'score' | 'all']
  // Session 140: Random Prompt events
  'update-node-random-prompt-preset': [nodeId: string, preset: string]
  'update-node-random-prompt-model': [nodeId: string, model: string]
  'update-node-random-prompt-film-type': [nodeId: string, filmType: string]
  'update-node-random-prompt-token-limit': [nodeId: string, limit: number]
  // Session 145: Model Adaption event
  'update-node-model-adaption-preset': [nodeId: string, preset: string]
  // Session 146: Interception Preset event
  'update-node-interception-preset': [nodeId: string, preset: string, context: string]
  // Session 147: Comparison Evaluator events
  'update-node-comparison-llm': [nodeId: string, model: string]
  'update-node-comparison-criteria': [nodeId: string, criteria: string]
  // Session 147: Numbered input connector events
  'end-connect-input-1': [nodeId: string]
  'end-connect-input-2': [nodeId: string]
  'end-connect-input-3': [nodeId: string]
  // Session 150: Seed node events
  'update-node-seed-mode': [nodeId: string, mode: 'fixed' | 'random' | 'increment']
  'update-node-seed-value': [nodeId: string, value: number]
  'update-node-seed-base': [nodeId: string, base: number]
  // Session 151: Resolution node events
  'update-node-resolution-preset': [nodeId: string, preset: 'square_1024' | 'portrait_768x1344' | 'landscape_1344x768' | 'custom']
  'update-node-resolution-width': [nodeId: string, width: number]
  'update-node-resolution-height': [nodeId: string, height: number]
  // Session 151: Quality node events
  'update-node-quality-steps': [nodeId: string, steps: number]
  'update-node-quality-cfg': [nodeId: string, cfg: number]
  // Session 152: Image Input/Evaluation events
  'update-node-image-data': [nodeId: string, imageData: { image_id: string; image_path: string; preview_url: string; original_size: [number, number]; resized_size: [number, number] }]
  'update-node-vision-model': [nodeId: string, model: string]
  'update-node-image-evaluation-preset': [nodeId: string, preset: string]
  'update-node-image-evaluation-prompt': [nodeId: string, prompt: string]
}>()

const canvasRef = ref<HTMLElement | null>(null)
const draggingNodeId = ref<string | null>(null)
const dragOffset = ref({ x: 0, y: 0 })

// Session 256: Pan/Zoom state
const panOffset = ref({ x: 0, y: 0 })
const zoomLevel = ref(1)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })
const panStartOffset = ref({ x: 0, y: 0 })

/**
 * Node dimensions by type
 * Wide nodes: input, interception, translation, evaluation, display, collector
 * Narrow nodes: generation
 */
const NARROW_WIDTH = 180
const WIDE_WIDTH = 280
const DEFAULT_HEIGHT = 80

/**
 * Get node width based on type
 */
function getNodeWidth(node: CanvasNode): number {
  // Use custom width if set (resizable nodes)
  if (node.width) return node.width

  // Wide types: input, random_prompt, interception, translation, evaluation, display, collector, comparison_evaluator
  const wideTypes: StageType[] = ['input', 'random_prompt', 'interception', 'translation', 'evaluation', 'display', 'collector', 'comparison_evaluator']
  return wideTypes.includes(node.type) ? WIDE_WIDTH : NARROW_WIDTH
}

/**
 * Get node height
 */
function getNodeHeight(node: CanvasNode): number {
  return node.height || DEFAULT_HEIGHT
}

/**
 * Session 256: Convert screen coordinates to canvas coordinates (accounting for pan+zoom)
 */
function screenToCanvas(screenX: number, screenY: number): { x: number; y: number } {
  const rect = canvasRef.value!.getBoundingClientRect()
  return {
    x: (screenX - rect.left - panOffset.value.x) / zoomLevel.value,
    y: (screenY - rect.top - panOffset.value.y) / zoomLevel.value
  }
}

/**
 * Session 256: Transform style for the pan/zoom layer
 */
const transformStyle = computed(() => ({
  transform: `translate(${panOffset.value.x}px, ${panOffset.value.y}px) scale(${zoomLevel.value})`,
  transformOrigin: '0 0'
}))

/**
 * Get connector position from node data (no DOM queries)
 * All connectors positioned in HEADER area (fixed Y offset from top)
 * This ensures connectors don't move when nodes resize
 */
const HEADER_CONNECTOR_Y = 24  // Fixed offset from top (middle of header)

function getConnectorPosition(node: CanvasNode, connectorType: string): { x: number; y: number } {
  const width = getNodeWidth(node)

  if (connectorType === 'input') {
    // Left edge, header height
    return { x: node.x, y: node.y + HEADER_CONNECTOR_Y }
  } else if (connectorType === 'input-1') {
    // Session 147: First numbered input
    return { x: node.x, y: node.y + HEADER_CONNECTOR_Y }
  } else if (connectorType === 'input-2') {
    // Session 147: Second numbered input
    return { x: node.x, y: node.y + HEADER_CONNECTOR_Y + 20 }
  } else if (connectorType === 'input-3') {
    // Session 147: Third numbered input
    return { x: node.x, y: node.y + HEADER_CONNECTOR_Y + 40 }
  } else if (connectorType === 'feedback-input') {
    // Right edge, slightly below header for feedback loops
    return { x: node.x + width, y: node.y + HEADER_CONNECTOR_Y + 20 }
  } else {
    // Output connectors: right edge, header height
    return { x: node.x + width, y: node.y + HEADER_CONNECTOR_Y }
  }
}

/**
 * Get center point of a node's output connector
 */
function getNodeOutputCenter(nodeId: string, label?: string): { x: number; y: number } {
  const node = props.nodes.find(n => n.id === nodeId)
  if (!node) return { x: 0, y: 0 }

  // Evaluation: pass + commentary on RIGHT, fail/FB on LEFT
  if (label && node.type === 'evaluation') {
    const width = getNodeWidth(node)
    if (label === 'pass') {
      return { x: node.x + width, y: node.y + HEADER_CONNECTOR_Y }
    } else if (label === 'fail') {
      // FB port is on the LEFT side, below the input connector
      return { x: node.x, y: node.y + HEADER_CONNECTOR_Y + 20 }
    } else {
      // commentary: right side, second position
      return { x: node.x + width, y: node.y + HEADER_CONNECTOR_Y + 20 }
    }
  }

  return getConnectorPosition(node, 'output')
}

/**
 * Get center point of a node's input connector
 * Session 147: Added label parameter for numbered inputs
 */
function getNodeInputCenter(nodeId: string, label?: string): { x: number; y: number } {
  const node = props.nodes.find(n => n.id === nodeId)
  if (!node) return { x: 0, y: 0 }

  // Session 147: Handle numbered inputs for comparison_evaluator
  if (label && node.type === 'comparison_evaluator') {
    if (label === 'input-1') return getConnectorPosition(node, 'input-1')
    if (label === 'input-2') return getConnectorPosition(node, 'input-2')
    if (label === 'input-3') return getConnectorPosition(node, 'input-3')
  }

  // Generation: dual input connectors (primary + secondary)
  if (label && node.type === 'generation') {
    if (label === 'input-1') return getConnectorPosition(node, 'input-1')
    if (label === 'input-2') return getConnectorPosition(node, 'input-2')
  }

  return getConnectorPosition(node, 'input')
}

/**
 * Get center point of a node's feedback input connector
 */
function getNodeFeedbackInputCenter(nodeId: string): { x: number; y: number } {
  const node = props.nodes.find(n => n.id === nodeId)
  if (!node) return { x: 0, y: 0 }
  return getConnectorPosition(node, 'feedback-input')
}

/**
 * Connection paths for rendering
 * Pure data-based calculation - no DOM queries
 */
const connectionPaths = computed(() => {
  return props.connections.map(conn => {
    // For evaluation outputs with labels, use the specific labeled connector
    let outputLabel: string | undefined
    if (['pass', 'fail', 'commentary'].includes(conn.label || '')) {
      outputLabel = conn.label!
    } else if (conn.label === 'feedback') {
      // Feedback connections FROM evaluation nodes originate at the 'fail' port
      const sourceNode = props.nodes.find(n => n.id === conn.sourceId)
      if (sourceNode?.type === 'evaluation') {
        outputLabel = 'fail'
      }
    }
    const source = getNodeOutputCenter(conn.sourceId, outputLabel)

    // Use feedback input position for connections with label 'feedback'
    const target = conn.label === 'feedback'
      ? getNodeFeedbackInputCenter(conn.targetId)
      : getNodeInputCenter(conn.targetId, conn.label)

    // Red for backward cables (fail, feedback), blue (default) for forward
    const color = (conn.label === 'fail' || conn.label === 'feedback')
      ? '#ef4444'
      : undefined

    return {
      ...conn,
      x1: source.x,
      y1: source.y,
      x2: target.x,
      y2: target.y,
      color
    }
  })
})

/**
 * Temporary connection path (when connecting)
 */
const tempConnection = computed(() => {
  if (!props.connectingFromId) return null
  const label = props.connectingLabel || undefined
  const source = getNodeOutputCenter(props.connectingFromId, label)
  const color = (label === 'fail' || label === 'feedback')
    ? '#ef4444'
    : undefined
  return {
    x1: source.x,
    y1: source.y,
    x2: props.mousePosition.x,
    y2: props.mousePosition.y,
    color
  }
})

// Event handlers
function onCanvasClick(e: MouseEvent) {
  // Only deselect if clicking the workspace background itself (not the transform layer)
  const target = e.target as HTMLElement
  if (target === canvasRef.value || target.classList.contains('canvas-transform-layer')) {
    emit('select-node', null)
    if (props.connectingFromId) {
      emit('cancel-connection')
    }
  }
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  const nodeType = e.dataTransfer?.getData('nodeType') as StageType | undefined
  if (nodeType && canvasRef.value) {
    // Session 256: Convert drop coordinates through pan/zoom transform
    const pos = screenToCanvas(e.clientX, e.clientY)
    emit('add-node-at', nodeType, pos.x, pos.y)
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  e.dataTransfer!.dropEffect = 'copy'
}

function startNodeDrag(nodeId: string, e: MouseEvent) {
  const node = props.nodes.find(n => n.id === nodeId)
  if (!node || !canvasRef.value) return

  // Session 256: Convert through pan/zoom
  const pos = screenToCanvas(e.clientX, e.clientY)

  draggingNodeId.value = nodeId
  dragOffset.value = {
    x: pos.x - node.x,
    y: pos.y - node.y
  }
  emit('select-node', nodeId)
}

/**
 * Session 256: Mouse down handler — middle button starts panning
 */
function onCanvasMouseDown(e: MouseEvent) {
  if (e.button === 1) {
    // Middle mouse button → start panning
    e.preventDefault()
    isPanning.value = true
    panStart.value = { x: e.clientX, y: e.clientY }
    panStartOffset.value = { ...panOffset.value }
  }
}

function onMouseMove(e: MouseEvent) {
  if (!canvasRef.value) return

  // Session 256: Handle panning (middle mouse drag)
  if (isPanning.value) {
    panOffset.value = {
      x: panStartOffset.value.x + (e.clientX - panStart.value.x),
      y: panStartOffset.value.y + (e.clientY - panStart.value.y)
    }
    return
  }

  // Convert through pan/zoom for canvas coordinates
  const pos = screenToCanvas(e.clientX, e.clientY)
  emit('update-mouse-position', pos.x, pos.y)

  if (draggingNodeId.value) {
    const newX = pos.x - dragOffset.value.x
    const newY = pos.y - dragOffset.value.y
    emit('update-node-position', draggingNodeId.value, Math.max(0, newX), Math.max(0, newY))
  }
}

function onMouseUp() {
  draggingNodeId.value = null
  isPanning.value = false
}

/**
 * Session 256: Wheel handler — Ctrl+Wheel = zoom, plain Wheel = pan
 */
function onWheel(e: WheelEvent) {
  if (!canvasRef.value) return

  if (e.ctrlKey || e.metaKey) {
    // Zoom toward cursor
    e.preventDefault()
    const rect = canvasRef.value.getBoundingClientRect()
    const cursorX = e.clientX - rect.left
    const cursorY = e.clientY - rect.top

    const delta = e.deltaY > 0 ? 0.9 : 1.1
    const newZoom = Math.max(0.25, Math.min(2.0, zoomLevel.value * delta))
    const scale = newZoom / zoomLevel.value

    // Adjust pan so zoom centers on cursor position
    panOffset.value = {
      x: cursorX - scale * (cursorX - panOffset.value.x),
      y: cursorY - scale * (cursorY - panOffset.value.y)
    }
    zoomLevel.value = newZoom
  } else {
    // Plain wheel = vertical pan (shift+wheel = horizontal)
    panOffset.value = {
      x: panOffset.value.x - (e.shiftKey ? e.deltaY : e.deltaX),
      y: panOffset.value.y - (e.shiftKey ? 0 : e.deltaY)
    }
  }
}

function onKeyDown(e: KeyboardEvent) {
  // Delete selected node on Delete key only (not Backspace - too easy to trigger in text fields)
  if (e.key === 'Delete' && props.selectedNodeId) {
    emit('delete-node', props.selectedNodeId)
  }
  // Cancel connection on Escape
  if (e.key === 'Escape' && props.connectingFromId) {
    emit('cancel-connection')
  }
}

// Session 256: Exposed methods for parent (zoom controls, highlight pan-to-node)
function zoomIn() {
  const newZoom = Math.min(2.0, zoomLevel.value * 1.2)
  zoomLevel.value = newZoom
}

function zoomOut() {
  const newZoom = Math.max(0.25, zoomLevel.value / 1.2)
  zoomLevel.value = newZoom
}

function zoomReset() {
  zoomLevel.value = 1
  panOffset.value = { x: 0, y: 0 }
}

function fitToContent() {
  if (props.nodes.length === 0 || !canvasRef.value) return

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const node of props.nodes) {
    minX = Math.min(minX, node.x)
    minY = Math.min(minY, node.y)
    maxX = Math.max(maxX, node.x + getNodeWidth(node))
    maxY = Math.max(maxY, node.y + getNodeHeight(node))
  }

  const rect = canvasRef.value.getBoundingClientRect()
  const padding = 60
  const contentW = maxX - minX + padding * 2
  const contentH = maxY - minY + padding * 2

  const scaleX = rect.width / contentW
  const scaleY = rect.height / contentH
  const newZoom = Math.max(0.25, Math.min(2.0, Math.min(scaleX, scaleY)))

  zoomLevel.value = newZoom
  panOffset.value = {
    x: (rect.width - contentW * newZoom) / 2 - (minX - padding) * newZoom,
    y: (rect.height - contentH * newZoom) / 2 - (minY - padding) * newZoom
  }
}

function panToNode(nodeId: string) {
  const node = props.nodes.find(n => n.id === nodeId)
  if (!node || !canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  const nodeW = getNodeWidth(node)
  const nodeH = getNodeHeight(node)
  panOffset.value = {
    x: rect.width / 2 - (node.x + nodeW / 2) * zoomLevel.value,
    y: rect.height / 2 - (node.y + nodeH / 2) * zoomLevel.value
  }
}

defineExpose({ zoomIn, zoomOut, zoomReset, fitToContent, panToNode, zoomLevel })

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div
    ref="canvasRef"
    dir="ltr"
    class="canvas-workspace"
    @click="onCanvasClick"
    @drop="onDrop"
    @dragover="onDragOver"
    @mousedown="onCanvasMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseUp"
    @wheel="onWheel"
  >
    <!-- Session 256: Transform layer for pan/zoom -->
    <div class="canvas-transform-layer" :style="transformStyle">
      <!-- Connections SVG layer -->
      <svg class="connections-layer">
        <!-- Existing connections -->
        <ConnectionLine
          v-for="conn in connectionPaths"
          :key="`${conn.sourceId}-${conn.targetId}`"
          :x1="conn.x1"
          :y1="conn.y1"
          :x2="conn.x2"
          :y2="conn.y2"
          :color="conn.color"
          @click="emit('delete-connection', conn.sourceId, conn.targetId)"
        />

        <!-- Temporary connection being drawn -->
        <ConnectionLine
          v-if="tempConnection"
          :x1="tempConnection.x1"
          :y1="tempConnection.y1"
          :x2="tempConnection.x2"
          :y2="tempConnection.y2"
          :color="tempConnection.color"
          temporary
        />
      </svg>

      <!-- Nodes -->
      <StageModule
        v-for="node in nodes"
        :key="node.id"
        :node="node"
        :selected="node.id === selectedNodeId"
        :highlighted="node.id === highlightedNodeId"
        :llm-models="llmModels"
        :vision-models="visionModels"
        :config-name="getConfigInfo(node.configId)?.name"
        :config-media-type="getConfigInfo(node.configId)?.mediaType"
        :execution-result="executionResults?.[node.id]"
        :collector-output="node.type === 'collector' ? collectorOutput : undefined"
        :is-active="node.id === activeNodeId"
        @mousedown="startNodeDrag(node.id, $event)"
        @start-connect="emit('start-connection', node.id)"
        @start-connect-labeled="(label) => emit('start-connection', node.id, label)"
        @end-connect="emit('complete-connection', node.id)"
        @end-connect-feedback="emit('complete-connection-feedback', node.id)"
        @delete="emit('delete-node', node.id)"
        @select-config="emit('select-config', node.id)"
        @update-llm="emit('update-node-llm', node.id, $event)"
        @update-context-prompt="emit('update-node-context-prompt', node.id, $event)"
        @update-translation-prompt="emit('update-node-translation-prompt', node.id, $event)"
        @update-prompt-text="emit('update-node-prompt-text', node.id, $event)"
        @update-size="(width, height) => emit('update-node-size', node.id, width, height)"
        @update-display-title="emit('update-node-display-title', node.id, $event)"
        @update-display-mode="emit('update-node-display-mode', node.id, $event)"
        @update-evaluation-type="emit('update-node-evaluation-type', node.id, $event)"
        @update-evaluation-prompt="emit('update-node-evaluation-prompt', node.id, $event)"
        @update-output-type="emit('update-node-output-type', node.id, $event)"
        @update-random-prompt-preset="emit('update-node-random-prompt-preset', node.id, $event)"
        @update-random-prompt-model="emit('update-node-random-prompt-model', node.id, $event)"
        @update-random-prompt-film-type="emit('update-node-random-prompt-film-type', node.id, $event)"
        @update-random-prompt-token-limit="emit('update-node-random-prompt-token-limit', node.id, $event)"
        @update-model-adaption-preset="emit('update-node-model-adaption-preset', node.id, $event)"
        @update-interception-preset="(preset, context) => emit('update-node-interception-preset', node.id, preset, context)"
        @update-comparison-llm="emit('update-node-comparison-llm', node.id, $event)"
        @update-comparison-criteria="emit('update-node-comparison-criteria', node.id, $event)"
        @update-seed-mode="emit('update-node-seed-mode', node.id, $event)"
        @update-seed-value="emit('update-node-seed-value', node.id, $event)"
        @update-seed-base="emit('update-node-seed-base', node.id, $event)"
        @update-resolution-preset="emit('update-node-resolution-preset', node.id, $event)"
        @update-resolution-width="emit('update-node-resolution-width', node.id, $event)"
        @update-resolution-height="emit('update-node-resolution-height', node.id, $event)"
        @update-quality-steps="emit('update-node-quality-steps', node.id, $event)"
        @update-quality-cfg="emit('update-node-quality-cfg', node.id, $event)"
        @end-connect-input-1="emit('end-connect-input-1', node.id)"
        @end-connect-input-2="emit('end-connect-input-2', node.id)"
        @end-connect-input-3="emit('end-connect-input-3', node.id)"
        @update-image-data="emit('update-node-image-data', node.id, $event)"
        @update-vision-model="emit('update-node-vision-model', node.id, $event)"
        @update-image-evaluation-preset="emit('update-node-image-evaluation-preset', node.id, $event)"
        @update-image-evaluation-prompt="emit('update-node-image-evaluation-prompt', node.id, $event)"
      />

      <!-- Empty state -->
      <div v-if="nodes.length === 0" class="empty-state">
        <p v-if="locale === 'de'">
          Ziehe Module aus der Palette hierher
        </p>
        <p v-else>
          Drag modules from the palette here
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.canvas-workspace {
  width: 100%;
  height: 100%;
  position: relative;
  background:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 20px 20px;
  background-color: #0a0a0a;
  overflow: hidden;
  cursor: default;
}

.canvas-transform-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  overflow: visible;
}

.connections-layer > :deep(*) {
  pointer-events: auto;
}

.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}

.empty-state p {
  color: #64748b;
  font-size: 1rem;
  margin: 0;
}
</style>
