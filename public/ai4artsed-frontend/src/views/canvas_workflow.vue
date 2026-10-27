<script setup lang="ts">
import { ref, onMounted, computed, watch, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCanvasStore } from '@/stores/canvas'
import CanvasWorkspace from '@/components/canvas/CanvasWorkspace.vue'
import ModulePalette from '@/components/canvas/ModulePalette.vue'
import ZoomControls from '@/components/canvas/ZoomControls.vue'
import OutputDrawer, { type DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import FlowRunButton from '@/components/FlowRunButton.vue'
import ConfigSelectorModal from '@/components/canvas/ConfigSelectorModal.vue'
import CanvasPresetOverlay from '@/components/canvas/CanvasPresetOverlay.vue'
import type { CanvasWorkflow, StageType, RandomPromptPreset, PhotoFilmType, ModelAdaptionPreset, InterceptionPreset, ImageEvaluationPreset } from '@/types/canvas'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'
import { useFavoritesStore } from '@/stores/favorites'
import { useDeviceId } from '@/composables/useDeviceId'
import {
  CANVAS_FILE_ACCEPT,
  NotACanvasFile,
  canvasPrompt,
  givenName,
  readCanvasFile,
  saveCanvasFile,
  toCanvasWorkflow,
} from '@/lib/canvasFile'
import {
  fetchCanvasPresets,
  foldName,
  openPreset,
  presetFingerprint,
  presetNames,
  type CanvasPreset,
} from '@/lib/canvasPresets'
import { lensContext } from '@/lib/lensContext'
import { useChatModels } from '@/composables/useChatModels'
import { lineupMembers, registerLoaded } from '@/composables/useModelRegister'

const { t, locale } = useI18n()
const canvasStore = useCanvasStore()

// Config selector modal state (only for generation nodes now)
const showConfigSelector = ref(false)
const configSelectorNodeId = ref<string | null>(null)

// Panel visibility
const showPalette = ref(true)

// Output Drawer state
const drawerCollapsed = ref(true)
const highlightedNodeId = ref<string | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

// Canvas workspace ref for zoom/pan control
const canvasWorkspaceRef = ref<InstanceType<typeof CanvasWorkspace> | null>(null)

// Batch modal state
const showBatchModal = ref(false)
const batchCount = ref(3)
const batchBaseSeed = ref<number | undefined>(undefined)
const batchUseSeed = ref(false)

// The models the board's nodes are offered from. A ready-made workflow keeps
// only a model the board offers (lib/canvasPresets.ts), so one opened before
// they have arrived waits for them rather than finding none.
let configsLoaded: Promise<void> = Promise.resolve()

onMounted(async () => {
  // The ready-made workflows are asked for beside the configs, so "New" has
  // its ring ready when it is pressed.
  void loadPresets()
  // Load available configs
  configsLoaded = canvasStore.loadAllConfigs()
  await configsLoaded
})

// Auto-expand drawer when collector output arrives
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

/**
 * The collector's items in the drawer's own terms. The drawer used to be typed
 * on the shape below, which is why no other surface could open one without
 * pretending to be a canvas; the mapping is here now, where the canvas words
 * belong.
 */
const drawerItems = computed<DrawerItem[]>(() =>
  canvasStore.collectorOutput.map(o => {
    // Facts for the card's back. The config is passed on its own below and
    // stands there already, so it is not repeated here.
    const meta: string[] = []
    const seed = o.metadata?.seed ?? (
      o.output && typeof o.output === 'object' && 'seed' in (o.output as Record<string, unknown>)
        ? ((o.output as Record<string, unknown>).seed as number)
        : null
    )
    if (seed != null) meta.push(`seed: ${seed}`)
    const card = canvasStore.cardMeta[o.nodeId]
    // A node with a title (a ready-made workflow names its nodes: "Link 3 ·
    // Image", a model's name) puts it on its card, and the title alone tells
    // two cards apart. The title the node had when the run started: the
    // board may be another one by now.
    const title = canvasStore.collectorTitles[o.nodeId] || ''
    return {
      id: o.nodeId,
      label: title || o.nodeType,
      sub: title ? '' : o.nodeId.split('-').slice(-1)[0],
      meta,
      output: o.output,
      error: o.error,
      // The card's back side. It travels in its own key of the completion
      // event, keyed by node — a run recorded before 2026-08-19 has none, and
      // its card simply has no back.
      prompt: card?.prompt,
      configId: o.metadata?.display_name || o.metadata?.config_id,
      createdAt: card?.created_at,
      modelMeta: card?.model_meta ?? null,
      runId: card?.run_id,
    }
  })
)

/** The × on a card takes exactly that run off the surface. */
function removeDrawerItem(index: number) {
  canvasStore.collectorOutput.splice(index, 1)
}

// Highlight node from Output Drawer click
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

function handleUpdateNodeTranslationPrompt(nodeId: string, prompt: string | undefined) {
  canvasStore.updateNode(nodeId, { translationPrompt: prompt })
}

function handleUpdateNodeTranslationLanguage(nodeId: string, language: string | undefined) {
  canvasStore.updateNode(nodeId, { translationLanguage: language })
}

function handleUpdateNodePromptText(nodeId: string, text: string) {
  canvasStore.updateNode(nodeId, { promptText: text })
}

function handleUpdateNodeSize(nodeId: string, width: number, height: number) {
  canvasStore.updateNode(nodeId, { width, height })
}

// Display node handlers
// Unified evaluation node handlers
function handleUpdateNodeEvaluationType(nodeId: string, type: 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom') {
  canvasStore.updateNode(nodeId, { evaluationType: type })
}

function handleUpdateNodeEvaluationPrompt(nodeId: string, prompt: string) {
  canvasStore.updateNode(nodeId, { evaluationPrompt: prompt })
}

function handleUpdateNodeOutputType(nodeId: string, outputType: 'commentary' | 'score' | 'all') {
  canvasStore.updateNode(nodeId, { outputType })
}

// Random Prompt node handlers
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

// Model Adaption node handler
function handleUpdateNodeModelAdaptionPreset(nodeId: string, preset: string) {
  canvasStore.updateNode(nodeId, { modelAdaptionPreset: preset as ModelAdaptionPreset })
}

// Interception Preset handler
function handleUpdateNodeInterceptionPreset(nodeId: string, preset: string, context: string) {
  canvasStore.updateNode(nodeId, {
    interceptionPreset: preset as InterceptionPreset,
    contextPrompt: context
  })
}

// Comparison Evaluator handlers
function handleUpdateNodeComparisonLlm(nodeId: string, model: string) {
  canvasStore.updateNode(nodeId, { comparisonLlmModel: model })
}

function handleUpdateNodeComparisonCriteria(nodeId: string, criteria: string) {
  canvasStore.updateNode(nodeId, { comparisonCriteria: criteria })
}

// Seed node handlers
function handleUpdateNodeSeedMode(nodeId: string, mode: 'fixed' | 'random' | 'increment') {
  canvasStore.updateNode(nodeId, { seedMode: mode })
}

function handleUpdateNodeSeedValue(nodeId: string, value: number) {
  canvasStore.updateNode(nodeId, { seedValue: value })
}

function handleUpdateNodeSeedBase(nodeId: string, base: number) {
  canvasStore.updateNode(nodeId, { seedBase: base })
}

// Resolution node handlers
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

// Quality node handlers
function handleUpdateNodeQualitySteps(nodeId: string, steps: number) {
  canvasStore.updateNode(nodeId, { qualitySteps: steps })
}

function handleUpdateNodeQualityCfg(nodeId: string, cfg: number) {
  canvasStore.updateNode(nodeId, { qualityCfg: cfg })
}

// Image Input/Evaluation handlers
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

// ============================================================================
// New: the empty board, or a ready-made workflow (lib/canvasPresets.ts)
// ============================================================================

const showPresets = ref(false)
const presets = ref<CanvasPreset[]>([])
const presetsLoading = ref(false)
const presetsError = ref('')

async function loadPresets() {
  if (presetsLoading.value) return
  presetsLoading.value = true
  presetsError.value = ''
  try {
    presets.value = await fetchCanvasPresets()
  } catch (err) {
    console.error('[Canvas] The ready-made workflows could not be read:', err)
    presetsError.value = err instanceof Error ? err.message : String(err)
  } finally {
    presetsLoading.value = false
  }
}

/** "New" opens the ring; a ring that came up empty asks again. */
function handleNewWorkflow() {
  if (!presets.value.length) void loadPresets()
  showPresets.value = true
}

/**
 * The pick that is to become the board. Opening a preset waits for the models
 * and the lenses it names; a pick made in that time -- another preset, the
 * empty board -- is the one the user meant, and the earlier one, when it is
 * ready, gives way to it.
 */
let pickCount = 0

function handlePickEmpty() {
  // Counted once it is the board: a refused discard leaves a preset still
  // being made ready to arrive and ask for itself.
  if (holdsWork() && !confirm(t('canvas.discardWorkflow'))) return
  pickCount++
  canvasStore.newWorkflow()
}

// What a lineup of the Latent Lab reaches here is read off the chat list, as the
// Language Model Comparison reads it.
const { models: chatModels, refresh: refreshChatModels } = useChatModels()

async function handlePickPreset(preset: CanvasPreset) {
  const pick = ++pickCount
  let workflow: CanvasWorkflow
  try {
    await Promise.all([configsLoaded, refreshChatModels(), registerLoaded()])
    workflow = await openPreset(preset, {
      llmModels: canvasStore.llmModels,
      visionModels: canvasStore.visionModels,
      lineupMembers: (id) => lineupMembers(id, chatModels.value),
      lensContext: (id) => lensContext(id, locale.value),
      t: (key, args) => (args ? t(key, args) : t(key)),
      locale: locale.value,
    })
  } catch (err) {
    console.error(`[Canvas] The preset '${preset.info.id}' could not be opened:`, err)
    if (pick === pickCount) alert(t('canvas.presets.openError'))
    return
  }
  if (pick !== pickCount) return
  // Asked now, with the preset ready, not at the pick: what was written on the
  // board while it was being made ready is work too.
  if (holdsWork() && !confirm(t('canvas.discardWorkflow'))) return
  canvasStore.loadWorkflow(workflow)
  canvasStore.setPresetBoard({ presetId: preset.info.id, state: presetFingerprint(canvasStore.workflow) })
  // A chain like Telephone is wider than the window; the whole of it is
  // what has just been opened.
  await nextTick()
  canvasWorkspaceRef.value?.fitToContent()
}

/** The workflow as a `.atcanvas` file, named by its name and the minute (lib/canvasFile.ts). */
function handleExportWorkflow() {
  saveCanvasFile(canvasStore.exportWorkflow())
}

// Start batch execution
function handleStartBatch() {
  const seed = batchUseSeed.value ? batchBaseSeed.value : undefined
  canvasStore.executeBatch(batchCount.value, undefined, seed)
  showBatchModal.value = false
}

function handleImportWorkflow() {
  const input = document.createElement('input')
  input.type = 'file'
  // `.atcanvas`, and `.json` for the exports from before it existed.
  input.accept = CANVAS_FILE_ACCEPT
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      canvasStore.loadWorkflow(readCanvasFile(text))
    } catch (err) {
      console.error('Failed to import workflow:', err)
      alert(t(err instanceof NotACanvasFile ? 'canvas.importNotCanvas' : 'canvas.importError'))
    }
  }
  input.click()
}

// ============================================================================
// The workflow in the favourites strip
// ============================================================================

const favoritesStore = useFavoritesStore()
const deviceId = useDeviceId()

/**
 * What the board holds, as far as keeping it is concerned. The star is lit
 * while the board is the one that was kept; a node moved, a prompt changed or
 * a name given makes it another workflow, and the star goes dark.
 */
function boardState(): string {
  const w = canvasStore.workflow
  return JSON.stringify({ name: w.name, nodes: w.nodes, connections: w.connections })
}

const keeping = ref(false)

/**
 * The line before the name field: why the star did not keep the board. It
 * replaces the dialog the star raised until 2026-10-02 and stands where the
 * cause is — the name.
 */
const keepNote = ref('')
const nameInput = ref<HTMLInputElement | null>(null)

// The note is about the board it was given on. Every other board -- new, a
// preset, an import, a favourite -- comes in through the store as a workflow
// of its own, and the note goes with the one it was about.
watch(() => canvasStore.workflow, () => { keepNote.value = '' })

/** Every name a ready-made workflow carries, in every language (lib/canvasPresets.ts). */
const takenNames = computed(() => presetNames(presets.value.map(p => p.info)))

/** The run that holds the workflow kept from this board (stores/canvas.ts `keptBoard`). */
const isKept = computed(() => {
  const kept = canvasStore.keptBoard
  return !!kept && favoritesStore.isFavorited(kept.runId) && kept.state === boardState()
})

/**
 * The star in the bar. Keeping is a deliberate act (the star):
 * nothing here keeps a workflow on its own account. A favourite is a run, so
 * the server first records the workflow as a run of its own, and the strip then
 * keeps that run like any other. A lit star takes exactly that favourite away.
 */
async function handleKeepWorkflow() {
  if (keeping.value) return
  const kept = canvasStore.keptBoard
  if (isKept.value && kept) {
    await favoritesStore.removeFavorite(kept.runId, deviceId)
    return
  }
  // A kept workflow under a preset's name would stand in the favourites beside
  // that preset, and could not be told from it — so the name goes first.
  const name = foldName(givenName(canvasStore.workflow))
  if (name && takenNames.value.has(name)) {
    keepNote.value = t('canvas.keepPresetName')
    nameInput.value?.focus()
    nameInput.value?.select()
    return
  }
  keeping.value = true
  keepNote.value = ''
  try {
    const workflow = canvasStore.exportWorkflow()
    const state = boardState()
    const answer = await fetch('/api/canvas/keep', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow, device_id: deviceId }),
    })
    const body = await answer.json().catch(() => ({}))
    if (!answer.ok || !body.run_id) {
      throw new Error(body.error || `${answer.status} ${answer.statusText}`)
    }
    const kept = await favoritesStore.addFavorite(body.run_id, 'canvas', deviceId, 'anonymous', 'canvas')
    if (!kept) throw new Error(favoritesStore.error || 'not kept')
    canvasStore.setKeptBoard({ runId: body.run_id, state })
  } catch (err) {
    console.error('[Canvas] Keeping the workflow failed:', err)
    keepNote.value = t('canvas.keepError')
  } finally {
    keeping.value = false
  }
}

/**
 * Whether the board holds work that opening another one would throw away:
 * anything beyond the empty board's input and collector, and not kept as it
 * stands — nor a ready-made workflow as it opened, with nothing done to it but
 * moving its pieces about.
 */
function holdsWork(): boolean {
  const w = canvasStore.workflow
  if (isKept.value) return false
  const opened = canvasStore.presetBoard
  if (opened && opened.state === presetFingerprint(w)) return false
  return w.connections.length > 0 || !!givenName(w) || !!canvasPrompt(w) ||
    w.nodes.some(n => n.type !== 'input' && n.type !== 'collector')
}

/**
 * A workflow opened from the favourites strip ("Open in its instrument"): a kept
 * workflow, or the one behind a kept output of a Canvas run. It replaces the
 * board, after the same question "New workflow" asks where the board holds
 * work. A kept workflow of this device opens with its star lit; one kept by
 * another device (the strip in "All") opens dark, because its favourite is not
 * this device's to take away, and the star keeps a copy of its own.
 */
watch(
  () => favoritesStore.pendingRestoreData,
  (restoreData) => {
    const stored = restoreData?.canvas_workflow
    if (!stored) return
    favoritesStore.setRestoreData(null)
    if (holdsWork() && !confirm(t('canvas.discardWorkflow'))) return
    try {
      canvasStore.loadWorkflow(toCanvasWorkflow(stored))
    } catch (err) {
      console.error('[Canvas] The kept workflow could not be read:', err)
      alert(t('canvas.importNotCanvas'))
      return
    }
    const favorite = favoritesStore.favorites.find(f => f.run_id === restoreData.run_id)
    const own = !!favorite && (!favorite.device_id || favorite.device_id === deviceId)
    canvasStore.setKeptBoard(
      favorite?.media_type === 'canvas' && own ? { runId: favorite.run_id, state: boardState() } : null
    )
  },
  { immediate: true }
)

function handleRename(event: Event) {
  canvasStore.updateWorkflowMeta((event.target as HTMLInputElement).value)
  keepNote.value = ''
}

// Computed helpers
const currentConfigId = computed(() => {
  if (!configSelectorNodeId.value) return undefined
  const node = canvasStore.nodes.find(n => n.id === configSelectorNodeId.value)
  return node?.configId
})

// Zoom level from workspace (reactive via expose)
const currentZoomLevel = computed(() => canvasWorkspaceRef.value?.zoomLevel ?? 1)

// Page Context for Trashy
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
  <div dir="ltr" class="shell-page">
    <!-- Toolbar -->
    <div class="shell-bar">
      <div class="shell-bar-left">
        <!-- Toggle palette -->
        <button
          class="shell-btn"
          @click="showPalette = !showPalette"
          :title="$t('canvas.toggleSidebar')"
        >
          <img v-if="showPalette" src="@/assets/icons/left_panel_close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="" class="shell-icon" />
          <img v-else src="@/assets/icons/left_panel_open_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="" class="shell-icon" />
        </button>

        <!-- Toggle output panel -->
        <button
          class="shell-btn"
          @click="drawerCollapsed = !drawerCollapsed"
          :title="$t('canvas.outputDrawer.title')"
        >
          <img v-if="!drawerCollapsed" src="@/assets/icons/bottom_panel_close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="" class="shell-icon" />
          <img v-else src="@/assets/icons/bottom_panel_open_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="" class="shell-icon" />
        </button>
      </div>

      <!-- The middle of the bar starts the run, as it does in the Latent Lab.
           It held a badge reading "Ready" whenever the workflow was valid, which
           is the one thing a live trigger says by itself, so that badge was
           redundant and went. What the badge said and the button cannot is the
           OTHER case, so the error count stayed. -->
      <div class="shell-bar-center">
        <div v-if="!canvasStore.isWorkflowValid" class="validation-status invalid">
          {{ canvasStore.validationErrors.length }} {{ $t('canvas.errors') }}
        </div>

        <FlowRunButton
          :ready="canvasStore.isWorkflowValid && !canvasStore.isExecuting && !canvasStore.isBatchExecuting"
          :running="canvasStore.isExecuting || canvasStore.isBatchExecuting"
          :title="$t('canvas.execute')"
          @click="canvasStore.executeWorkflow()"
        />

        <!-- The same run, several times over: it belongs beside the trigger it
             varies, not among the file actions on the right. -->
        <button
          class="shell-btn batch"
          :disabled="!canvasStore.isWorkflowValid || canvasStore.isExecuting || canvasStore.isBatchExecuting"
          @click="showBatchModal = true"
          :title="$t('canvas.batchExecute')"
        >
          Batch
        </button>
      </div>

      <div class="shell-bar-right">
        <!-- Why the star did not keep the board, directly before the cause. -->
        <span v-if="keepNote" class="canvas-name-note" role="status" :title="keepNote">{{ keepNote }}</span>

        <!-- The workflow's name. Every file of this board is named by it, the
             workflow itself as well as what it renders (lib/canvasFile.ts).
             Written in place, as a perspective's name is on the Flow board. -->
        <input
          ref="nameInput"
          class="canvas-name"
          type="text"
          maxlength="120"
          :value="canvasStore.workflow.name"
          :placeholder="$t('canvas.workflowName')"
          :aria-label="$t('canvas.workflowName')"
          @input="handleRename"
        />

        <!-- New workflow -->
        <button
          class="shell-btn"
          @click="handleNewWorkflow"
          :title="$t('canvas.newWorkflow')"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm4 18H6V4h7v5h5v11z"/></svg>
        </button>

        <!-- Import -->
        <button
          class="shell-btn"
          @click="handleImportWorkflow"
          :title="$t('canvas.importWorkflow')"
        >
          <img src="@/assets/icons/file_open_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="" class="shell-icon" />
        </button>

        <!-- Export -->
        <button
          class="shell-btn"
          @click="handleExportWorkflow"
          :title="$t('canvas.exportWorkflow')"
        >
          <img src="@/assets/icons/file_save_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="" class="shell-icon" />
        </button>

        <!-- Keep in the favourites strip. The star and its colours are the
             platform's (MediaActionBar). -->
        <button
          class="shell-btn keep"
          :class="{ kept: isKept }"
          :disabled="keeping"
          @click="handleKeepWorkflow"
          :title="isKept ? $t('gallery.unfavorite') : $t('gallery.favorite')"
        >
          <svg v-if="isKept" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="m233-120 65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Z"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="m354-287 126-76 126 77-33-144 111-96-146-13-58-136-58 135-146 13 111 97-33 143ZM233-120l65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Zm247-350Z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Batch Progress Indicator -->
    <div v-if="canvasStore.isBatchExecuting" class="batch-progress-bar">
      <div class="batch-progress-info">
        <span>{{ $t('canvas.batchExecution') }}: {{ canvasStore.batchCompletedRuns }}/{{ canvasStore.batchTotalRuns }}</span>
        <span v-if="canvasStore.batchCurrentRun >= 0">
          (Run {{ canvasStore.batchCurrentRun + 1 }})
        </span>
        <!-- Batch Abort Button -->
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
    <div class="shell-body">
      <!-- Palette panel -->
      <div v-if="showPalette" class="shell-rail">
        <ModulePalette draggable @select="handleAddNodeFromPalette($event as StageType)" />
      </div>

      <!-- Canvas + Output Drawer column -->
      <div class="shell-work">
        <!-- Canvas with zoom controls -->
        <div class="shell-main">
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
            @update-node-translation-language="handleUpdateNodeTranslationLanguage"
            @update-node-prompt-text="handleUpdateNodePromptText"
            @update-node-size="handleUpdateNodeSize"
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
            @end-connect-params="(nodeId: string) => canvasStore.completeConnectionToInput(nodeId, 'params')"
            @update-node-image-data="handleUpdateNodeImageData"
            @update-node-vision-model="handleUpdateNodeVisionModel"
            @update-node-image-evaluation-preset="handleUpdateNodeImageEvaluationPreset"
            @update-node-image-evaluation-prompt="handleUpdateNodeImageEvaluationPrompt"
          />

          <!-- Floating zoom controls -->
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

        <!-- Output Drawer -->
        <OutputDrawer
          :items="drawerItems"
          :is-collapsed="drawerCollapsed"
          :highlighted-id="highlightedNodeId"
          :file-stem="canvasStore.collectorStem"
          selectable
          @toggle-collapse="drawerCollapsed = !drawerCollapsed"
          @select="highlightNode"
          @remove="removeDrawerItem"
        />
      </div>
    </div>

    <!-- "New": the empty board and the ready-made workflows, on the ring. -->
    <CanvasPresetOverlay
      v-model="showPresets"
      :presets="presets"
      :loading="presetsLoading"
      :error="presetsError"
      @pick="handlePickPreset"
      @empty="handlePickEmpty"
    />

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

    <!-- Execution progress overlay -->
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

    <!-- Batch Modal -->
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
/* The workflow's name, written in place as a perspective's name is on the Flow
   board (`.pe-name-input` in x2x_flow.vue): no frame and no ground, a line
   under it while the pointer is on it and the violet line of that field while
   it is written in. The text and the resting line take the bar's colours, so
   the name reads as the bar's own and not as a form field dropped into it. */
.canvas-name {
  width: 16rem;
  min-width: 6rem;
  flex: 0 1 auto;
  padding: 0.375rem 0;
  background: transparent;
  border: none;
  border-bottom: 1px solid transparent;
  border-radius: 0;
  outline: none;
  color: #e2e8f0;
  font-size: 0.875rem;
  font-family: inherit;
}
.canvas-name::placeholder { color: rgba(226, 232, 240, 0.45); }
.canvas-name:hover { border-bottom-color: var(--surface-4); }
.canvas-name:focus { border-bottom-color: #7f77dd; }

/* The star's answer, before the name it is about, in two lines at the size
   of a node's error line (StageModule `.module-error`): on one line the
   sentence is 330 px, and the bar leaves it 120 px beside the name at 1024 px
   and 220 px at 1366 px. While it stands, the name gives way to it down to a
   short field -- the field has the focus and its text selected, so typing
   replaces it. At 1024 px that leaves the note 167 px, two lines of about 60
   characters (WORK_ORDERS.md, WO-2026-10-02-A). */
.canvas-name-note {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 18rem;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  white-space: normal;
  line-height: 1.25;
  color: #94a3b8;
  font-size: 0.6875rem;
}
.canvas-name-note + .canvas-name {
  flex-shrink: 4;
  min-width: 3rem;
}

/* The kept star in the platform's colours (MediaActionBar, from x2x_flow). */
.shell-btn.keep.kept { color: #ffb300; }




.validation-status {
  padding: 0.375rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 400;
}

/* Only the failing state is drawn. The passing one was a badge saying "Ready"
   beside a trigger that already stands ready. */
.validation-status.invalid {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

/* Floating zoom controls */
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
  background: rgb(var(--bg-base-rgb) / 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.loading-spinner {
  padding: 1rem 2rem;
  background: var(--surface-1);
  border-radius: 8px;
  font-size: 1rem;
}

/* Execution Progress Overlay */
.execution-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgb(var(--bg-base-rgb) / 0.85);
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
  background: linear-gradient(145deg, var(--surface-1), var(--bg-base));
  border-radius: 16px;
  border: 1px solid var(--surface-4);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  min-width: 300px;
}

.progress-spinner-ring {
  width: 60px;
  height: 60px;
  border: 4px solid var(--surface-4);
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
  font-weight: 700;
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
  font-weight: 400;
}

.progress-counter {
  font-size: 0.8125rem;
  color: #64748b;
  padding: 0.25rem 0.75rem;
  background: rgb(var(--surface-4-rgb) / 0.5);
  border-radius: 12px;
  margin-top: 0.25rem;
}

/* Batch UI Styles */
.shell-btn.batch {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-color: #6366f1;
}

.shell-btn.batch:hover:not(:disabled) {
  background: linear-gradient(135deg, #818cf8 0%, #a78bfa 100%);
}

.batch-progress-bar {
  background: rgba(99, 102, 241, 0.2);
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--shell-line, var(--surface-4));
}

.batch-progress-info {
  font-size: 0.875rem;
  color: #c7d2fe;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Batch Abort Button */
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
  background: var(--surface-4);
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
  background: rgb(var(--bg-base-rgb) / 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.batch-modal {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  border-radius: 12px;
  width: 400px;
  max-width: 90vw;
}

.batch-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--surface-4);
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
  background: var(--bg-base);
  border: 1px solid var(--surface-4);
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
  border-top: 1px solid var(--surface-4);
}

.btn {
  padding: 0.625rem 1.25rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 400;
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
  border: 1px solid var(--surface-4);
  color: #94a3b8;
}

.btn.secondary:hover {
  background: rgb(var(--surface-4-rgb) / 0.5);
  color: #f1f5f9;
}
</style>
