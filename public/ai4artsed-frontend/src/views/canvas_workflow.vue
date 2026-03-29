<script setup lang="ts">
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCanvasStore } from '@/stores/canvas'
import CanvasWorkspace from '@/components/canvas/CanvasWorkspace.vue'
import ModulePalette from '@/components/canvas/ModulePalette.vue'
import ZoomControls from '@/components/canvas/ZoomControls.vue'
import OutputDrawer from '@/components/canvas/OutputDrawer.vue'
import ConfigSelectorModal from '@/components/canvas/ConfigSelectorModal.vue'
import type { StageType, RandomPromptPreset, PhotoFilmType, ModelAdaptionPreset, InterceptionPreset, ImageEvaluationPreset } from '@/types/canvas'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

const { t, locale } = useI18n()
const canvasStore = useCanvasStore()

// Config selector modal state (only for generation nodes now)
const showConfigSelector = ref(false)
const configSelectorNodeId = ref<string | null>(null)

// Workflow name editing
const isEditingName = ref(false)
const editingNameValue = ref('')

// Panel visibility
const showPalette = ref(true)

// Session 256: Output Drawer state
const drawerCollapsed = ref(true)
const highlightedNodeId = ref<string | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

// Session 256: Canvas workspace ref for zoom/pan control
const canvasWorkspaceRef = ref<InstanceType<typeof CanvasWorkspace> | null>(null)

// Session 149: Batch modal state
const showBatchModal = ref(false)
const batchCount = ref(3)
const batchBaseSeed = ref<number | undefined>(undefined)
const batchUseSeed = ref(false)

onMounted(async () => {
  // Load available configs
  await canvasStore.loadAllConfigs()
})

// Session 256: Auto-expand drawer when collector output arrives
watch(() => canvasStore.collectorOutput, (items) => {
  if (items && items.length > 0) {
    drawerCollapsed.value = false
  }
})

// Event handlers
function handleAddNodeAt(type: StageType, x: number, y: number) {
  const node = canvasStore.addNode(type, x, y)

  // Only generation nodes need config selector modal
  if (type === 'generation') {
    openConfigSelector(node.id)
  }
  // Interception and translation nodes have inline LLM selection
}

function handleAddNodeFromPalette(type: StageType) {
  // Add node at a default position
  const x = 400 + Math.random() * 100
  const y = 200 + Math.random() * 100
  handleAddNodeAt(type, x, y)
}

function openConfigSelector(nodeId: string) {
  configSelectorNodeId.value = nodeId
  showConfigSelector.value = true
}

function handleSelectConfig(nodeId: string) {
  const node = canvasStore.nodes.find(n => n.id === nodeId)
  if (!node) return

  // Only generation nodes use the config selector modal
  if (node.type === 'generation') {
    openConfigSelector(nodeId)
  }
}

function handleConfigSelected(configId: string) {
  if (configSelectorNodeId.value) {
    canvasStore.updateNodeConfig(configSelectorNodeId.value, configId)
  }
}

// Session 256: Highlight node from Output Drawer click
function highlightNode(nodeId: string) {
  if (highlightTimer) clearTimeout(highlightTimer)
  highlightedNodeId.value = nodeId

  // Pan canvas to the node
  canvasWorkspaceRef.value?.panToNode(nodeId)

  // Clear highlight after 2s
  highlightTimer = setTimeout(() => {
    highlightedNodeId.value = null
  }, 2000)
}

// Handlers for inline node editing (interception/translation)
function handleUpdateNodeLLM(nodeId: string, llmModel: string) {
  canvasStore.updateNode(nodeId, { llmModel })
}

function handleUpdateNodeContextPrompt(nodeId: string, prompt: string) {
  canvasStore.updateNode(nodeId, { contextPrompt: prompt })
}

function handleUpdateNodeTranslationPrompt(nodeId: string, prompt: string) {
  canvasStore.updateNode(nodeId, { translationPrompt: prompt })
}

function handleUpdateNodePromptText(nodeId: string, text: string) {
  canvasStore.updateNode(nodeId, { promptText: text })
}

function handleUpdateNodeSize(nodeId: string, width: number, height: number) {
  canvasStore.updateNode(nodeId, { width, height })
}

// Session 134: Display node handlers
function handleUpdateNodeDisplayTitle(nodeId: string, title: string) {
  canvasStore.updateNode(nodeId, { title })
}

function handleUpdateNodeDisplayMode(nodeId: string, mode: 'popup' | 'inline' | 'toast') {
  canvasStore.updateNode(nodeId, { displayMode: mode })
}

// Session 134 Refactored: Unified evaluation node handlers
function handleUpdateNodeEvaluationType(nodeId: string, type: 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom') {
  canvasStore.updateNode(nodeId, { evaluationType: type })
}

function handleUpdateNodeEvaluationPrompt(nodeId: string, prompt: string) {
  canvasStore.updateNode(nodeId, { evaluationPrompt: prompt })
}

function handleUpdateNodeOutputType(nodeId: string, outputType: 'commentary' | 'score' | 'all') {
  canvasStore.updateNode(nodeId, { outputType })
}

// Session 140: Random Prompt node handlers
function handleUpdateNodeRandomPromptPreset(nodeId: string, preset: string) {
  canvasStore.updateNode(nodeId, { randomPromptPreset: preset as RandomPromptPreset })
}

function handleUpdateNodeRandomPromptModel(nodeId: string, model: string) {
  canvasStore.updateNode(nodeId, { randomPromptModel: model })
}

function handleUpdateNodeRandomPromptFilmType(nodeId: string, filmType: string) {
  canvasStore.updateNode(nodeId, { randomPromptFilmType: filmType as PhotoFilmType })
}

function handleUpdateNodeRandomPromptTokenLimit(nodeId: string, limit: number) {
  canvasStore.updateNode(nodeId, { randomPromptTokenLimit: limit as 75 | 500 })
}

// Session 145: Model Adaption node handler
function handleUpdateNodeModelAdaptionPreset(nodeId: string, preset: string) {
  canvasStore.updateNode(nodeId, { modelAdaptionPreset: preset as ModelAdaptionPreset })
}

// Session 146: Interception Preset handler
function handleUpdateNodeInterceptionPreset(nodeId: string, preset: string, context: string) {
  canvasStore.updateNode(nodeId, {
    interceptionPreset: preset as InterceptionPreset,
    contextPrompt: context
  })
}

// Session 147: Comparison Evaluator handlers
function handleUpdateNodeComparisonLlm(nodeId: string, model: string) {
  canvasStore.updateNode(nodeId, { comparisonLlmModel: model })
}

function handleUpdateNodeComparisonCriteria(nodeId: string, criteria: string) {
  canvasStore.updateNode(nodeId, { comparisonCriteria: criteria })
}

// Session 150: Seed node handlers
function handleUpdateNodeSeedMode(nodeId: string, mode: 'fixed' | 'random' | 'increment') {
  canvasStore.updateNode(nodeId, { seedMode: mode })
}

function handleUpdateNodeSeedValue(nodeId: string, value: number) {
  canvasStore.updateNode(nodeId, { seedValue: value })
}

function handleUpdateNodeSeedBase(nodeId: string, base: number) {
  canvasStore.updateNode(nodeId, { seedBase: base })
}

// Session 151: Resolution node handlers
function handleUpdateNodeResolutionPreset(nodeId: string, preset: 'square_1024' | 'portrait_768x1344' | 'landscape_1344x768' | 'custom') {
  const updates: Record<string, unknown> = { resolutionPreset: preset }
  // Apply preset dimensions
  if (preset === 'square_1024') {
    updates.resolutionWidth = 1024
    updates.resolutionHeight = 1024
  } else if (preset === 'portrait_768x1344') {
    updates.resolutionWidth = 768
    updates.resolutionHeight = 1344
  } else if (preset === 'landscape_1344x768') {
    updates.resolutionWidth = 1344
    updates.resolutionHeight = 768
  }
  canvasStore.updateNode(nodeId, updates)
}

function handleUpdateNodeResolutionWidth(nodeId: string, width: number) {
  canvasStore.updateNode(nodeId, { resolutionWidth: width })
}

function handleUpdateNodeResolutionHeight(nodeId: string, height: number) {
  canvasStore.updateNode(nodeId, { resolutionHeight: height })
}

// Session 151: Quality node handlers
function handleUpdateNodeQualitySteps(nodeId: string, steps: number) {
  canvasStore.updateNode(nodeId, { qualitySteps: steps })
}

function handleUpdateNodeQualityCfg(nodeId: string, cfg: number) {
  canvasStore.updateNode(nodeId, { qualityCfg: cfg })
}

// Session 152: Image Input/Evaluation handlers
function handleUpdateNodeImageData(nodeId: string, imageData: { image_id: string; image_path: string; preview_url: string; original_size: [number, number]; resized_size: [number, number] }) {
  canvasStore.updateNode(nodeId, { imageData })
}

function handleUpdateNodeVisionModel(nodeId: string, model: string) {
  canvasStore.updateNode(nodeId, { visionModel: model })
}

function handleUpdateNodeImageEvaluationPreset(nodeId: string, preset: string) {
  canvasStore.updateNode(nodeId, { imageEvaluationPreset: preset as ImageEvaluationPreset })
}

function handleUpdateNodeImageEvaluationPrompt(nodeId: string, prompt: string) {
  canvasStore.updateNode(nodeId, { imageEvaluationPrompt: prompt })
}

function startEditingName() {
  editingNameValue.value = canvasStore.workflow.name
  isEditingName.value = true
}

function finishEditingName() {
  if (editingNameValue.value.trim()) {
    canvasStore.updateWorkflowMeta(editingNameValue.value.trim())
  }
  isEditingName.value = false
}

function handleNewWorkflow() {
  if (confirm(t('canvas.discardWorkflow'))) {
    canvasStore.newWorkflow()
  }
}

function handleExportWorkflow() {
  const workflow = canvasStore.exportWorkflow()
  const json = JSON.stringify(workflow, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${workflow.name.replace(/\s+/g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// Session 149: Start batch execution
function handleStartBatch() {
  const seed = batchUseSeed.value ? batchBaseSeed.value : undefined
  canvasStore.executeBatch(batchCount.value, undefined, seed)
  showBatchModal.value = false
}

function handleImportWorkflow() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const workflow = JSON.parse(text)
      canvasStore.loadWorkflow(workflow)
    } catch (err) {
      console.error('Failed to import workflow:', err)
      alert(t('canvas.importError'))
    }
  }
  input.click()
}

// Computed helpers
const currentConfigId = computed(() => {
  if (!configSelectorNodeId.value) return undefined
  const node = canvasStore.nodes.find(n => n.id === configSelectorNodeId.value)
  return node?.configId
})

// Session 256: Zoom level from workspace (reactive via expose)
const currentZoomLevel = computed(() => canvasWorkspaceRef.value?.zoomLevel ?? 1)

// Page Context for Trashy (Session 133)
// Canvas: Trashy stays bottom-left to avoid interfering with workspace
const pageContextStore = usePageContextStore()

const trashyFocusHint = computed<FocusHint>(() => {
  // If palette is visible, move up slightly
  if (showPalette.value) {
    return { x: 2, y: 70, anchor: 'bottom-left' }
  }
  return { x: 2, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'canvas_workflow',
  pageContent: {
    workflowName: canvasStore.workflow.name,
    workflowNodes: canvasStore.nodes.map(n => ({
      id: n.id,
      type: n.type,
      configId: n.configId,
      llmModel: n.llmModel
    })),
    selectedNodeId: canvasStore.selectedNodeId,
    connectionCount: canvasStore.connections.length
  },
  focusHint: trashyFocusHint.value
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onUnmounted(() => {
  pageContextStore.clearContext()
  if (highlightTimer) clearTimeout(highlightTimer)
})
</script>

<template>
  <div dir="ltr" class="canvas-workflow-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- Toggle palette -->
        <button
          class="toolbar-btn"
          :class="{ active: showPalette }"
          @click="showPalette = !showPalette"
          :title="$t('canvas.toggleSidebar')"
        >
          <img src="@/assets/icons/thumbnail_bar_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.png" alt="" class="toolbar-icon" />
        </button>

        <!-- Workflow name -->
        <div class="workflow-name" @dblclick="startEditingName">
          <template v-if="isEditingName">
            <input
              v-model="editingNameValue"
              type="text"
              class="name-input"
              @blur="finishEditingName"
              @keyup.enter="finishEditingName"
              @keyup.escape="isEditingName = false"
              autofocus
            />
          </template>
          <template v-else>
            <span class="name-text">{{ canvasStore.workflow.name }}</span>
            <span class="name-hint">{{ $t('canvas.editNameHint') }}</span>
          </template>
        </div>
      </div>

      <div class="toolbar-center">
        <!-- Validation status -->
        <div
          class="validation-status"
          :class="{ valid: canvasStore.isWorkflowValid, invalid: !canvasStore.isWorkflowValid }"
        >
          <span v-if="canvasStore.isWorkflowValid">{{ $t('canvas.ready') }}</span>
          <span v-else>{{ canvasStore.validationErrors.length }} {{ $t('canvas.errors') }}</span>
        </div>
      </div>

      <div class="toolbar-right">
        <!-- DSGVO Warning Badge -->
        <span
          class="dsgvo-badge"
          :title="$t('canvas.dsgvoTooltip')"
        >
          <s>DS-GVO</s>
        </span>

        <!-- New workflow -->
        <button
          class="toolbar-btn"
          @click="handleNewWorkflow"
          :title="$t('canvas.newWorkflow')"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm4 18H6V4h7v5h5v11z"/></svg>
        </button>

        <!-- Import -->
        <button
          class="toolbar-btn"
          @click="handleImportWorkflow"
          :title="$t('canvas.importWorkflow')"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
        </button>

        <!-- Export -->
        <button
          class="toolbar-btn"
          @click="handleExportWorkflow"
          :title="$t('canvas.exportWorkflow')"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
        </button>

        <!-- Execute -->
        <button
          class="toolbar-btn primary"
          :disabled="!canvasStore.isWorkflowValid || canvasStore.isExecuting || canvasStore.isBatchExecuting"
          @click="canvasStore.executeWorkflow()"
          :title="$t('canvas.execute')"
        >
          {{ $t('canvas.execute') }}
        </button>

        <!-- Session 149: Batch Execute -->
        <button
          class="toolbar-btn batch"
          :disabled="!canvasStore.isWorkflowValid || canvasStore.isExecuting || canvasStore.isBatchExecuting"
          @click="showBatchModal = true"
          :title="$t('canvas.batchExecute')"
        >
          Batch
        </button>
      </div>
    </div>

    <!-- Session 149: Batch Progress Indicator -->
    <div v-if="canvasStore.isBatchExecuting" class="batch-progress-bar">
      <div class="batch-progress-info">
        <span>{{ $t('canvas.batchExecution') }}: {{ canvasStore.batchCompletedRuns }}/{{ canvasStore.batchTotalRuns }}</span>
        <span v-if="canvasStore.batchCurrentRun >= 0">
          (Run {{ canvasStore.batchCurrentRun + 1 }})
        </span>
        <!-- Session 150: Batch Abort Button -->
        <button
          class="batch-abort-btn"
          @click="canvasStore.abortBatch()"
          :title="$t('canvas.batchAbort')"
        >
          {{ $t('canvas.abort') }}
        </button>
      </div>
      <div class="batch-progress-track">
        <div
          class="batch-progress-fill"
          :style="{ width: `${(canvasStore.batchCompletedRuns / canvasStore.batchTotalRuns) * 100}%` }"
        ></div>
      </div>
    </div>

    <!-- Main content -->
    <div class="main-content">
      <!-- Palette panel -->
      <div v-if="showPalette" class="palette-panel">
        <ModulePalette @add-node="handleAddNodeFromPalette" />
      </div>

      <!-- Session 256: Canvas + Output Drawer column -->
      <div class="canvas-and-drawer">
        <!-- Canvas with zoom controls -->
        <div class="canvas-container">
          <CanvasWorkspace
            ref="canvasWorkspaceRef"
            :nodes="canvasStore.nodes"
            :connections="canvasStore.connections"
            :selected-node-id="canvasStore.selectedNodeId"
            :connecting-from-id="canvasStore.connectingFromId"
            :mouse-position="canvasStore.mousePosition"
            :llm-models="canvasStore.llmModels"
            :vision-models="canvasStore.visionModels"
            :execution-results="canvasStore.executionResults"
            :collector-output="canvasStore.collectorOutput"
            :output-configs="canvasStore.outputConfigs"
            :active-node-id="canvasStore.activeNodeId"
            :connecting-label="canvasStore.connectingLabel"
            :highlighted-node-id="highlightedNodeId"
            @select-node="canvasStore.selectNode"
            @update-node-position="canvasStore.updateNodePosition"
            @delete-node="canvasStore.deleteNode"
            @add-connection="canvasStore.completeConnection"
            @delete-connection="canvasStore.deleteConnection"
            @start-connection="canvasStore.startConnection"
            @cancel-connection="canvasStore.cancelConnection"
            @complete-connection="canvasStore.completeConnection"
            @complete-connection-feedback="canvasStore.completeConnectionFeedback"
            @update-mouse-position="canvasStore.updateMousePosition"
            @add-node-at="handleAddNodeAt"
            @select-config="handleSelectConfig"
            @update-node-llm="handleUpdateNodeLLM"
            @update-node-context-prompt="handleUpdateNodeContextPrompt"
            @update-node-translation-prompt="handleUpdateNodeTranslationPrompt"
            @update-node-prompt-text="handleUpdateNodePromptText"
            @update-node-size="handleUpdateNodeSize"
            @update-node-display-title="handleUpdateNodeDisplayTitle"
            @update-node-display-mode="handleUpdateNodeDisplayMode"
            @update-node-evaluation-type="handleUpdateNodeEvaluationType"
            @update-node-evaluation-prompt="handleUpdateNodeEvaluationPrompt"
            @update-node-output-type="handleUpdateNodeOutputType"
            @update-node-random-prompt-preset="handleUpdateNodeRandomPromptPreset"
            @update-node-random-prompt-model="handleUpdateNodeRandomPromptModel"
            @update-node-random-prompt-film-type="handleUpdateNodeRandomPromptFilmType"
            @update-node-random-prompt-token-limit="handleUpdateNodeRandomPromptTokenLimit"
            @update-node-model-adaption-preset="handleUpdateNodeModelAdaptionPreset"
            @update-node-interception-preset="handleUpdateNodeInterceptionPreset"
            @update-node-comparison-llm="handleUpdateNodeComparisonLlm"
            @update-node-comparison-criteria="handleUpdateNodeComparisonCriteria"
            @update-node-seed-mode="handleUpdateNodeSeedMode"
            @update-node-seed-value="handleUpdateNodeSeedValue"
            @update-node-seed-base="handleUpdateNodeSeedBase"
            @update-node-resolution-preset="handleUpdateNodeResolutionPreset"
            @update-node-resolution-width="handleUpdateNodeResolutionWidth"
            @update-node-resolution-height="handleUpdateNodeResolutionHeight"
            @update-node-quality-steps="handleUpdateNodeQualitySteps"
            @update-node-quality-cfg="handleUpdateNodeQualityCfg"
            @end-connect-input-1="(nodeId: string) => canvasStore.completeConnectionToInput(nodeId, 'input-1')"
            @end-connect-input-2="(nodeId: string) => canvasStore.completeConnectionToInput(nodeId, 'input-2')"
            @end-connect-input-3="(nodeId: string) => canvasStore.completeConnectionToInput(nodeId, 'input-3')"
            @update-node-image-data="handleUpdateNodeImageData"
            @update-node-vision-model="handleUpdateNodeVisionModel"
            @update-node-image-evaluation-preset="handleUpdateNodeImageEvaluationPreset"
            @update-node-image-evaluation-prompt="handleUpdateNodeImageEvaluationPrompt"
          />

          <!-- Session 256: Floating zoom controls -->
          <div class="zoom-controls-float">
            <ZoomControls
              :zoom-level="currentZoomLevel"
              @zoom-in="canvasWorkspaceRef?.zoomIn()"
              @zoom-out="canvasWorkspaceRef?.zoomOut()"
              @zoom-reset="canvasWorkspaceRef?.zoomReset()"
              @fit-to-content="canvasWorkspaceRef?.fitToContent()"
            />
          </div>
        </div>

        <!-- Session 256: Output Drawer -->
        <OutputDrawer
          :items="canvasStore.collectorOutput"
          :is-collapsed="drawerCollapsed"
          :highlighted-node-id="highlightedNodeId"
          @toggle-collapse="drawerCollapsed = !drawerCollapsed"
          @highlight-node="highlightNode"
        />
      </div>
    </div>

    <!-- Config selector modal (only for generation nodes) -->
    <ConfigSelectorModal
      :visible="showConfigSelector"
      :output-configs="canvasStore.outputConfigs"
      :current-config-id="currentConfigId"
      @close="showConfigSelector = false"
      @select="handleConfigSelected"
    />

    <!-- Loading overlay -->
    <div v-if="canvasStore.isLoading" class="loading-overlay">
      <div class="loading-spinner">
        {{ $t('canvas.loading') }}
      </div>
    </div>

    <!-- Execution progress overlay (Session 141) -->
    <div v-if="canvasStore.isExecuting" class="execution-overlay">
      <div class="execution-progress">
        <div class="progress-spinner-ring"></div>
        <div class="progress-content">
          <div class="progress-title">
            {{ $t('canvas.executingWorkflow') }}
          </div>
          <div v-if="canvasStore.currentProgress" class="progress-detail">
            <span class="progress-message">{{ canvasStore.currentProgress.message }}</span>
          </div>
          <div v-else class="progress-detail">
            <span class="progress-message">{{ $t('canvas.starting') }}</span>
          </div>
          <div v-if="canvasStore.totalNodes > 0" class="progress-counter">
            {{ canvasStore.completedNodes }} / {{ canvasStore.totalNodes }}
            {{ $t('canvas.nodes') }}
          </div>
        </div>
      </div>
    </div>

    <!-- Session 149: Batch Modal -->
    <div v-if="showBatchModal" class="modal-overlay" @click.self="showBatchModal = false">
      <div class="batch-modal">
        <div class="batch-modal-header">
          <h3>{{ $t('canvas.batchExecution') }}</h3>
          <button class="close-btn" @click="showBatchModal = false">&times;</button>
        </div>
        <div class="batch-modal-content">
          <div class="batch-field">
            <label>{{ $t('canvas.batchRunCount') }}</label>
            <input type="number" v-model.number="batchCount" min="1" max="100" />
          </div>
          <div class="batch-field checkbox">
            <label>
              <input type="checkbox" v-model="batchUseSeed" />
              {{ $t('canvas.batchUseSeed') }}
            </label>
          </div>
          <div v-if="batchUseSeed" class="batch-field">
            <label>{{ $t('canvas.batchBaseSeed') }}</label>
            <input type="number" v-model.number="batchBaseSeed" placeholder="123456789" />
            <small>{{ $t('canvas.batchSeedHint') }}</small>
          </div>
        </div>
        <div class="batch-modal-footer">
          <button class="btn secondary" @click="showBatchModal = false">
            {{ $t('canvas.cancel') }}
          </button>
          <button class="btn primary" @click="handleStartBatch">
            {{ $t('canvas.batchStart') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.canvas-workflow-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0a0a0a;
  color: #e2e8f0;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: #141414;
  border-bottom: 1px solid #334155;
  gap: 1rem;
}

.toolbar-left,
.toolbar-center,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.toolbar-left {
  flex: 1;
}

.toolbar-right {
  flex: 1;
  justify-content: flex-end;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.75rem;
  background: #334155;
  border: none;
  border-radius: 6px;
  color: #e2e8f0;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s;
}

.toolbar-btn:hover:not(:disabled) {
  background: #475569;
}

.toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar-btn.active {
  background: #3b82f6;
}

.toolbar-btn.primary {
  background: #3b82f6;
}

.toolbar-btn.primary:hover:not(:disabled) {
  background: #2563eb;
}

.dsgvo-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.5rem;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.4);
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  color: #f87171;
  cursor: help;
  letter-spacing: 0.025em;
}

.dsgvo-badge:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.6);
}

.toolbar-icon {
  width: 20px;
  height: 20px;
  opacity: 0.9;
}

.workflow-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
}

.workflow-name:hover {
  background: rgba(255, 255, 255, 0.05);
}

.name-text {
  font-weight: 500;
}

.name-hint {
  font-size: 0.75rem;
  color: #64748b;
}

.name-input {
  padding: 0.25rem 0.5rem;
  background: #0a0a0a;
  border: 1px solid #3b82f6;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.875rem;
  font-weight: 500;
}

.name-input:focus {
  outline: none;
}

.validation-status {
  padding: 0.375rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
}

.validation-status.valid {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.validation-status.invalid {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.palette-panel {
  width: 240px;
  background: #141414;
  border-right: 1px solid #334155;
  overflow-y: auto;
}

/* Session 256: Canvas + Drawer column layout */
.canvas-and-drawer {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.canvas-container {
  flex: 1;
  position: relative;
  min-width: 0;
  min-height: 0;
}

/* Session 256: Floating zoom controls */
.zoom-controls-float {
  position: absolute;
  bottom: 12px;
  right: 12px;
  z-index: 50;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 10, 10, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.loading-spinner {
  padding: 1rem 2rem;
  background: #141414;
  border-radius: 8px;
  font-size: 1rem;
}

/* Session 141: Execution Progress Overlay */
.execution-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 10, 10, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  backdrop-filter: blur(4px);
}

.execution-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
  padding: 2rem 3rem;
  background: linear-gradient(145deg, #141414, #0a0a0a);
  border-radius: 16px;
  border: 1px solid #334155;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  min-width: 300px;
}

.progress-spinner-ring {
  width: 60px;
  height: 60px;
  border: 4px solid #334155;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.progress-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  text-align: center;
}

.progress-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #f1f5f9;
}

.progress-detail {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.progress-message {
  font-size: 0.9375rem;
  color: #94a3b8;
  font-weight: 500;
}

.progress-counter {
  font-size: 0.8125rem;
  color: #64748b;
  padding: 0.25rem 0.75rem;
  background: rgba(51, 65, 85, 0.5);
  border-radius: 12px;
  margin-top: 0.25rem;
}

/* Session 149: Batch UI Styles */
.toolbar-btn.batch {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-color: #6366f1;
}

.toolbar-btn.batch:hover:not(:disabled) {
  background: linear-gradient(135deg, #818cf8 0%, #a78bfa 100%);
}

.batch-progress-bar {
  background: rgba(99, 102, 241, 0.2);
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #334155;
}

.batch-progress-info {
  font-size: 0.875rem;
  color: #c7d2fe;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Session 150: Batch Abort Button */
.batch-abort-btn {
  margin-left: auto;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  background: #dc2626;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.batch-abort-btn:hover {
  background: #b91c1c;
}

.batch-progress-track {
  height: 4px;
  background: #334155;
  border-radius: 2px;
  overflow: hidden;
}

.batch-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  transition: width 0.3s ease;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.batch-modal {
  background: #141414;
  border: 1px solid #334155;
  border-radius: 12px;
  width: 400px;
  max-width: 90vw;
}

.batch-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #334155;
}

.batch-modal-header h3 {
  margin: 0;
  font-size: 1.125rem;
  color: #f1f5f9;
}

.close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #f1f5f9;
}

.batch-modal-content {
  padding: 1.25rem;
}

.batch-field {
  margin-bottom: 1rem;
}

.batch-field label {
  display: block;
  font-size: 0.875rem;
  color: #94a3b8;
  margin-bottom: 0.5rem;
}

.batch-field.checkbox label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.batch-field input[type="number"] {
  width: 100%;
  padding: 0.625rem;
  background: #0a0a0a;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #f1f5f9;
  font-size: 1rem;
}

.batch-field input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
}

.batch-field small {
  display: block;
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.batch-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid #334155;
}

.btn {
  padding: 0.625rem 1.25rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn.primary {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border: none;
  color: white;
}

.btn.primary:hover {
  background: linear-gradient(135deg, #818cf8 0%, #a78bfa 100%);
}

.btn.secondary {
  background: transparent;
  border: 1px solid #334155;
  color: #94a3b8;
}

.btn.secondary:hover {
  background: rgba(51, 65, 85, 0.5);
  color: #f1f5f9;
}
</style>
