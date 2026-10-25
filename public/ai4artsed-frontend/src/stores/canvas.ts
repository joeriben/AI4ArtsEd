import { ref, computed } from 'vue'
import i18n from '@/i18n'
import { defineStore } from 'pinia'
import { useDeviceId } from '@/composables/useDeviceId'
import { startCanvasRun } from '@/composables/useCanvasRunStream'
import { readSseFrames } from '@/lib/sseStream'
import { canvasFileStem, givenName } from '@/lib/canvasFile'
import { nodeDefaults } from '@/lib/canvasNodeDefaults'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import type {
  CanvasNode,
  CanvasConnection,
  CanvasWorkflow,
  StageType,
  NodeExecutionState,
  WorkflowExecutionState,
  LLMModelSummary,
  OutputConfigSummary,
  CollectorOutputItem
} from '@/types/canvas'
import {
  generateNodeId,
  createDefaultWorkflow,
  getNodeTypeDefinition,
  isParameterType,
  isValidConnection
} from '@/types/canvas'

/**
 * Pinia Store for Canvas Workflow Builder
 *
 * Manages:
 * - Workflow state (nodes, connections)
 * - Node selection and editing
 * - Available configs (interception, output)
 * - Workflow execution state
 */
export const useCanvasStore = defineStore('canvas', () => {
  const deviceId = useDeviceId()

  // ============================================================================
  // STATE
  // ============================================================================

  /** Current workflow being edited */
  const workflow = ref<CanvasWorkflow>(createDefaultWorkflow())

  /** Currently selected node ID */
  const selectedNodeId = ref<string | null>(null)

  /** Node being connected (source of new connection) */
  const connectingFromId = ref<string | null>(null)

  /** Label for the connection being created (passthrough/commented/commentary) */
  const connectingLabel = ref<string | null>(null)

  /** Current mouse position (for connection preview) */
  const mousePosition = ref({ x: 0, y: 0 })

  /** Available LLM models for interception/translation nodes */
  const llmModels = ref<LLMModelSummary[]>([])

  /** Available Vision models for image_evaluation nodes */
  const visionModels = ref<LLMModelSummary[]>([])

  /** Available output/generation configs */
  const outputConfigs = ref<OutputConfigSummary[]>([])

  /** Loading state */
  const isLoading = ref(false)

  /** Error state */
  const error = ref<string | null>(null)

  /** Workflow execution state */
  const executionState = ref<WorkflowExecutionState | null>(null)

  /** Whether we're in execution mode (read-only canvas) */
  const isExecuting = ref(false)

  /** Execution results from backend (nodeId -> result) */
  const executionResults = ref<Record<string, {
    type: string
    output: unknown
    error: string | null
    model?: string
  }>>({})

  /** Collector output (aggregated from all connected nodes) */
  const collectorOutput = ref<CollectorOutputItem[]>([])

  /**
   * What each generation node's card shows on its BACK, keyed by node id:
   * the prompt, the model's sheet, the time, and the sub-run the media URL
   * carries. It arrives in its own key of the completion event rather than in
   * the node result or the collected item, because both of those are in that
   * event twice — see services/canvas_executor.py, _execute_generation.
   */
  /**
   * The words the outputs of the last run are saved under: the board as it was
   * when the run started (lib/canvasFile.ts). Taken then, because the outputs
   * stay in the drawer while the board is renamed, changed, or replaced by
   * another one.
   */
  const collectorStem = ref('')

  /**
   * The titles the nodes of the last run carried (a ready-made workflow names
   * its nodes: "Link 3 · Image", a model's name), by node id. Taken when the
   * run starts, like `collectorStem` and for the same reason: its cards stay in
   * the drawer while another board, with other nodes, is opened.
   */
  const collectorTitles = ref<Record<string, string>>({})

  /**
   * The favourite that holds this board, and the board as it was kept
   * (views/canvas_workflow.vue). Held here rather than in the page: the board
   * outlives the page, and a star held by the page went dark on every visit
   * elsewhere while the board stood unchanged.
   */
  const keptBoard = ref<{ runId: string; state: string } | null>(null)

  function setKeptBoard(value: { runId: string; state: string } | null) {
    keptBoard.value = value
  }

  /**
   * The ready-made workflow the board was opened from, and the board as it
   * opened (lib/canvasPresets.ts `presetFingerprint`). While the board still
   * matches it, it holds no work of anybody's: opening another one throws
   * nothing away. Cleared by every other way a board is replaced.
   */
  const presetBoard = ref<{ presetId: string; state: string } | null>(null)

  function setPresetBoard(value: { presetId: string; state: string } | null) {
    presetBoard.value = value
  }

  const cardMeta = ref<Record<string, {
    prompt?: string
    model_meta?: Record<string, any> | null
    created_at?: number
    run_id?: string
  }>>({})

  /** Active node for bubble animation (shows one at a time) */
  const activeNodeId = ref<string | null>(null)

  /** Execution order for replay animation */
  const executionOrder = ref<string[]>([])

  /** Hidden results for staged animation release */
  const hiddenResults = ref<Record<string, {
    type: string
    output: unknown
    error: string | null
    model?: string
  }>>({})

  /** Current progress during streaming execution */
  const currentProgress = ref<{
    node_id: string
    node_type: string
    status: string
    message: string
  } | null>(null)

  /** Total nodes for progress display */
  const totalNodes = ref(0)

  /** Completed nodes count for progress display */
  const completedNodes = ref(0)

  // Batch execution state
  /** Whether batch execution is active */
  const isBatchExecuting = ref(false)

  /** Current batch ID */
  const batchId = ref<string | null>(null)

  /** Total runs in current batch */
  const batchTotalRuns = ref(0)

  /** Completed runs in current batch */
  const batchCompletedRuns = ref(0)

  /** Current run index (0-based) */
  const batchCurrentRun = ref(0)

  /** Export paths from completed batch runs */
  const batchExportPaths = ref<string[]>([])

  /** Animation timer reference */
  let animationTimer: ReturnType<typeof setTimeout> | null = null

  // ============================================================================
  // COMPUTED
  // ============================================================================

  /** All nodes in the workflow */
  const nodes = computed(() => workflow.value.nodes)

  /** All connections in the workflow */
  const connections = computed(() => workflow.value.connections)

  /** Currently selected node */
  const selectedNode = computed(() => {
    if (!selectedNodeId.value) return null
    return workflow.value.nodes.find(n => n.id === selectedNodeId.value) ?? null
  })

  /** Whether a connection is being created */
  const isConnecting = computed(() => connectingFromId.value !== null)

  /**
   * Check if workflow is valid (has required nodes and connections)
   *
   * Generation is optional for text-only workflows.
   * Valid workflows:
   * - Input → Interception/Translation → Collector (text only)
   * - Input → Interception → Generation → Collector (with media)
   *
   * NOTE: Safety is NOT checked here - DevServer handles it automatically
   */
  const isWorkflowValid = computed(() => {
    const hasInput = workflow.value.nodes.some(n => n.type === 'input')
    // image_input is also a valid source
    const hasImageInput = workflow.value.nodes.some(n => n.type === 'image_input')
    const hasCollector = workflow.value.nodes.some(n => n.type === 'collector')

    // Check all generation nodes have configs selected (if any exist)
    const generationNodes = workflow.value.nodes.filter(n => n.type === 'generation')
    const allGenerationConfigured = generationNodes.every(n => n.configId)

    // Check all interception nodes have LLM selected
    const interceptionNodes = workflow.value.nodes.filter(n => n.type === 'interception')
    const allInterceptionConfigured = interceptionNodes.every(n => n.llmModel)

    // Check all translation nodes have LLM selected
    const translationNodes = workflow.value.nodes.filter(n => n.type === 'translation')
    const allTranslationConfigured = translationNodes.every(n => n.llmModel)

    // Check all random_prompt nodes have preset and LLM selected
    const randomPromptNodes = workflow.value.nodes.filter(n => n.type === 'random_prompt')
    const allRandomPromptConfigured = randomPromptNodes.every(n => n.randomPromptPreset && n.randomPromptModel)

    // Check all image_evaluation nodes have vision model selected
    const imageEvaluationNodes = workflow.value.nodes.filter(n => n.type === 'image_evaluation')
    const allImageEvaluationConfigured = imageEvaluationNodes.every(n => n.visionModel)

    // Check all image_input nodes have image uploaded
    const imageInputNodes = workflow.value.nodes.filter(n => n.type === 'image_input')
    const allImageInputConfigured = imageInputNodes.every(n => n.imageData?.image_path)

    // Need a source: input, image_input, OR standalone random_prompt
    const hasSource = hasInput || hasImageInput || randomPromptNodes.length > 0

    return hasSource && hasCollector &&
           allGenerationConfigured && allInterceptionConfigured && allTranslationConfigured &&
           allRandomPromptConfigured && allImageEvaluationConfigured && allImageInputConfigured
  })

  /**
   * Get validation errors
   *
   * Generation is optional for text-only workflows.
   * NOTE: Safety is NOT validated here - DevServer handles it automatically
   */
  const validationErrors = computed(() => {
    const errors: string[] = []

    const hasInput = workflow.value.nodes.some(n => n.type === 'input')
    // image_input is also a valid source
    const hasImageInput = workflow.value.nodes.some(n => n.type === 'image_input')
    const randomPromptNodes = workflow.value.nodes.filter(n => n.type === 'random_prompt')

    // Need a source: input, image_input, OR random_prompt
    if (!hasInput && !hasImageInput && randomPromptNodes.length === 0) {
      errors.push('Missing source node (Input, Image Input, or Random Prompt)')
    }
    if (!workflow.value.nodes.some(n => n.type === 'collector')) {
      errors.push('Missing collector node')
    }

    const interceptionNodes = workflow.value.nodes.filter(n => n.type === 'interception')
    const translationNodes = workflow.value.nodes.filter(n => n.type === 'translation')
    const generationNodes = workflow.value.nodes.filter(n => n.type === 'generation')
    // Image nodes
    const imageInputNodes = workflow.value.nodes.filter(n => n.type === 'image_input')
    const imageEvaluationNodes = workflow.value.nodes.filter(n => n.type === 'image_evaluation')

    generationNodes.forEach(n => {
      if (!n.configId) {
        errors.push(`Generation node missing output config`)
      }
    })

    interceptionNodes.forEach(n => {
      if (!n.llmModel) {
        errors.push(`Interception node needs LLM selection`)
      }
    })
    translationNodes.forEach(n => {
      if (!n.llmModel) {
        errors.push(`Translation node needs LLM selection`)
      }
    })

    // Random Prompt validation
    randomPromptNodes.forEach(n => {
      if (!n.randomPromptModel) {
        errors.push(`Random Prompt node needs LLM selection`)
      }
      if (!n.randomPromptPreset) {
        errors.push(`Random Prompt node needs preset selection`)
      }
    })

    // Image Input validation
    imageInputNodes.forEach(n => {
      if (!n.imageData?.image_path) {
        errors.push(`Image Input node needs image upload`)
      }
    })

    // Image Evaluation validation
    imageEvaluationNodes.forEach(n => {
      if (!n.visionModel) {
        errors.push(`Image Analysis node needs Vision model selection`)
      }
    })

    return errors
  })

  // ============================================================================
  // NODE ACTIONS
  // ============================================================================

  /**
   * Add a new node to the canvas
   */
  function addNode(type: StageType, x: number, y: number, configId?: string): CanvasNode {
    const node: CanvasNode = {
      id: generateNodeId(type),
      type,
      x,
      y,
      configId,
      config: {},
      // The configured language model and the parameter nodes' starting values
      // (lib/canvasNodeDefaults.ts, shared with the ready-made workflows).
      ...nodeDefaults(type, llmModels.value),
    }

    workflow.value.nodes.push(node)
    console.log(`[Canvas] Added ${type} node at (${x}, ${y})`)
    return node
  }

  /**
   * Update a node's position
   */
  function updateNodePosition(nodeId: string, x: number, y: number) {
    const node = workflow.value.nodes.find(n => n.id === nodeId)
    if (node) {
      node.x = x
      node.y = y
    }
  }

  /**
   * Update a node's config
   */
  function updateNodeConfig(nodeId: string, configId: string) {
    const node = workflow.value.nodes.find(n => n.id === nodeId)
    if (node) {
      node.configId = configId
      console.log(`[Canvas] Updated node ${nodeId} config to ${configId}`)
    }
  }

  /**
   * Update node properties
   */
  function updateNode(nodeId: string, updates: Partial<CanvasNode>) {
    const node = workflow.value.nodes.find(n => n.id === nodeId)
    if (node) {
      Object.assign(node, updates)
    }
  }

  /**
   * Delete a node
   */
  function deleteNode(nodeId: string) {
    // Collector cannot be deleted
    const node = workflow.value.nodes.find(n => n.id === nodeId)
    if (node?.type === 'collector') return

    // Remove all connections to/from this node
    workflow.value.connections = workflow.value.connections.filter(
      c => c.sourceId !== nodeId && c.targetId !== nodeId
    )

    // Remove the node
    workflow.value.nodes = workflow.value.nodes.filter(n => n.id !== nodeId)

    // Deselect if it was selected
    if (selectedNodeId.value === nodeId) {
      selectedNodeId.value = null
    }

    console.log(`[Canvas] Deleted node ${nodeId}`)
    return true
  }

  /**
   * Select a node
   */
  function selectNode(nodeId: string | null) {
    selectedNodeId.value = nodeId
  }

  // ============================================================================
  // CONNECTION ACTIONS
  // ============================================================================

  /**
   * Start creating a connection from a node
   * The optional label parameter carries the output label of evaluation nodes
   */
  function startConnection(nodeId: string, label?: string) {
    connectingFromId.value = nodeId
    connectingLabel.value = label || null
  }

  /**
   * Cancel connection creation
   */
  function cancelConnection() {
    connectingFromId.value = null
    connectingLabel.value = null
  }

  /**
   * Complete a connection to a target node
   */
  function completeConnection(targetId: string): boolean {
    if (!connectingFromId.value) return false
    if (connectingFromId.value === targetId) {
      cancelConnection()
      return false
    }

    const sourceNode = workflow.value.nodes.find(n => n.id === connectingFromId.value)
    const targetNode = workflow.value.nodes.find(n => n.id === targetId)

    if (!sourceNode || !targetNode) {
      cancelConnection()
      return false
    }

    // Validate connection types
    if (!isValidConnection(sourceNode.type, targetNode.type)) {
      console.warn(`[Canvas] Invalid connection: ${sourceNode.type} -> ${targetNode.type}`)
      cancelConnection()
      return false
    }

    // Check if connection already exists
    const exists = workflow.value.connections.some(
      c => c.sourceId === connectingFromId.value && c.targetId === targetId
    )

    if (exists) {
      console.warn(`[Canvas] Connection already exists`)
      cancelConnection()
      return false
    }

    // Add the connection
    // Include label if present (for evaluation nodes)
    const newConnection: CanvasConnection = {
      sourceId: connectingFromId.value,
      targetId
    }
    if (connectingLabel.value) {
      newConnection.label = connectingLabel.value
      console.log(`[Canvas] Added labeled connection: ${connectingFromId.value} -> ${targetId} (${connectingLabel.value})`)
    } else {
      console.log(`[Canvas] Added connection: ${connectingFromId.value} -> ${targetId}`)
    }
    workflow.value.connections.push(newConnection)

    cancelConnection()
    return true
  }

  /**
   * Complete a connection to a feedback input (always uses 'feedback' label)
   */
  function completeConnectionFeedback(targetId: string): boolean {
    if (!connectingFromId.value) return false
    if (connectingFromId.value === targetId) {
      cancelConnection()
      return false
    }

    const sourceNode = workflow.value.nodes.find(n => n.id === connectingFromId.value)
    const targetNode = workflow.value.nodes.find(n => n.id === targetId)

    if (!sourceNode || !targetNode) {
      cancelConnection()
      return false
    }

    // Feedback input only valid for interception/translation nodes
    if (!['interception', 'translation'].includes(targetNode.type)) {
      console.warn(`[Canvas] Feedback input only valid for interception/translation nodes`)
      cancelConnection()
      return false
    }

    // Check if feedback connection already exists
    const exists = workflow.value.connections.some(
      c => c.sourceId === connectingFromId.value && c.targetId === targetId && c.label === 'feedback'
    )

    if (exists) {
      console.warn(`[Canvas] Feedback connection already exists`)
      cancelConnection()
      return false
    }

    // Add the feedback connection
    const newConnection: CanvasConnection = {
      sourceId: connectingFromId.value,
      targetId,
      label: 'feedback'
    }
    console.log(`[Canvas] Added feedback connection: ${connectingFromId.value} -> ${targetId}`)
    workflow.value.connections.push(newConnection)

    cancelConnection()
    return true
  }

  /**
   * Complete a connection to a numbered input (comparison_evaluator)
   */
  function completeConnectionToInput(targetId: string, inputLabel: string): boolean {
    if (!connectingFromId.value) return false
    if (connectingFromId.value === targetId) {
      cancelConnection()
      return false
    }

    const sourceNode = workflow.value.nodes.find(n => n.id === connectingFromId.value)
    const targetNode = workflow.value.nodes.find(n => n.id === targetId)

    if (!sourceNode || !targetNode) {
      cancelConnection()
      return false
    }

    // Numbered inputs only valid for comparison_evaluator and generation nodes
    if (targetNode.type !== 'comparison_evaluator' && targetNode.type !== 'generation') {
      console.warn(`[Canvas] Numbered inputs only valid for comparison_evaluator and generation nodes`)
      cancelConnection()
      return false
    }

    // The same type check the plain input makes: a seed, resolution or quality
    // node connects to a generation node and nowhere else.
    if (!isValidConnection(sourceNode.type, targetNode.type)) {
      console.warn(`[Canvas] Invalid connection: ${sourceNode.type} -> ${targetNode.type}`)
      cancelConnection()
      return false
    }

    const nodeType = (id: string) => workflow.value.nodes.find(n => n.id === id)?.type
    let label = inputLabel
    let exists: boolean
    if (targetNode.type === 'generation' && isParameterType(sourceNode.type)) {
      // The parameter input takes seed, resolution and quality, one of each:
      // the backend reads one value per type, and a second seed would silently
      // replace the first. A parameter node dropped on 1 or 2 lands here too.
      label = 'params'
      exists = workflow.value.connections.some(
        c => c.targetId === targetId && nodeType(c.sourceId) === sourceNode.type
      )
    } else if (targetNode.type === 'generation' && inputLabel === 'params') {
      console.warn(`[Canvas] The parameter input takes seed, resolution and quality only`)
      cancelConnection()
      return false
    } else {
      // A prompt input holds one connection. A parameter node that an older
      // graph connected there does not occupy it: it is read as a parameter.
      exists = workflow.value.connections.some(
        c => c.targetId === targetId && c.label === inputLabel
          && !(targetNode.type === 'generation' && isParameterType(nodeType(c.sourceId)))
      )
    }

    if (exists) {
      console.warn(`[Canvas] Connection to ${label} already exists`)
      cancelConnection()
      return false
    }

    // Add the connection with input label
    const newConnection: CanvasConnection = {
      sourceId: connectingFromId.value,
      targetId,
      label
    }
    console.log(`[Canvas] Added connection to ${label}: ${connectingFromId.value} -> ${targetId}`)
    workflow.value.connections.push(newConnection)

    cancelConnection()
    return true
  }

  /**
   * Delete a connection
   */
  function deleteConnection(sourceId: string, targetId: string) {
    workflow.value.connections = workflow.value.connections.filter(
      c => !(c.sourceId === sourceId && c.targetId === targetId)
    )
    console.log(`[Canvas] Deleted connection: ${sourceId} -> ${targetId}`)
  }

  /**
   * Update mouse position (for connection preview)
   */
  function updateMousePosition(x: number, y: number) {
    mousePosition.value = { x, y }
  }

  // ============================================================================
  // WORKFLOW ACTIONS
  // ============================================================================

  /**
   * Create a new workflow
   */
  function newWorkflow() {
    workflow.value = createDefaultWorkflow()
    presetBoard.value = null
    selectedNodeId.value = null
    connectingFromId.value = null
    error.value = null
    console.log('[Canvas] Created new workflow')
  }

  /**
   * Load a workflow from JSON
   * Includes migration for old connection label names
   */
  function loadWorkflow(data: CanvasWorkflow) {
    // Migrate old evaluation connection labels: passthrough→pass, commented→fail
    if (data.connections) {
      for (const conn of data.connections) {
        if (conn.label === 'passthrough') conn.label = 'pass'
        else if (conn.label === 'commented') conn.label = 'fail'
      }
    }
    // Strip removed branching fields from evaluation nodes
    if (data.nodes) {
      for (const node of data.nodes) {
        if (node.type === 'evaluation') {
          delete (node as any).enableBranching
          delete (node as any).branchCondition
          delete (node as any).thresholdValue
          delete (node as any).trueLabel
          delete (node as any).falseLabel
        }
      }
    }
    // The name a board carried before anybody could give it one ('New
    // Workflow') is no name, and must not become the name of the next file.
    workflow.value = { ...data, name: givenName(data) }
    presetBoard.value = null
    selectedNodeId.value = null
    connectingFromId.value = null
    error.value = null
    console.log(`[Canvas] Loaded workflow: ${data.name}`)
  }

  /**
   * Export workflow as JSON
   */
  function exportWorkflow(): CanvasWorkflow {
    return {
      ...workflow.value,
      updatedAt: new Date().toISOString()
    }
  }

  /**
   * Update workflow metadata
   */
  function updateWorkflowMeta(name?: string, description?: string) {
    if (name !== undefined) workflow.value.name = name
    if (description !== undefined) workflow.value.description = description
    workflow.value.updatedAt = new Date().toISOString()
  }

  // ============================================================================
  // CONFIG LOADING
  // ============================================================================

  /**
   * Load available LLM models from backend
   */
  async function loadLLMModels() {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/canvas/llm-models')
      if (!response.ok) {
        throw new Error(`Failed to load LLM models: ${response.statusText}`)
      }
      const data = await response.json()
      llmModels.value = data.models || []
      console.log(`[Canvas] Loaded ${llmModels.value.length} LLM models`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load LLM models'
      console.error('[Canvas] Error loading LLM models:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Load available output/generation configs from backend
   */
  async function loadOutputConfigs() {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/canvas/output-configs')
      if (!response.ok) {
        throw new Error(`Failed to load output configs: ${response.statusText}`)
      }
      const data = await response.json()
      outputConfigs.value = data.configs || []
      console.log(`[Canvas] Loaded ${outputConfigs.value.length} output configs`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load configs'
      console.error('[Canvas] Error loading output configs:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Load available Vision models from backend
   */
  async function loadVisionModels() {
    try {
      const response = await fetch('/api/canvas/vision-models')
      if (!response.ok) {
        throw new Error(`Failed to load vision models: ${response.statusText}`)
      }
      const data = await response.json()
      visionModels.value = data.models || []
      console.log(`[Canvas] Loaded ${visionModels.value.length} vision models`)
    } catch (err) {
      console.error('[Canvas] Error loading vision models:', err)
      // Non-critical - don't set error state
    }
  }

  /**
   * Load all configs
   */
  async function loadAllConfigs() {
    await Promise.all([
      loadLLMModels(),
      loadOutputConfigs(),
      loadVisionModels()
    ])
  }

  // ============================================================================
  // EXECUTION (placeholder for Phase 3)
  // ============================================================================

  /**
   * Animate bubbles through execution order
   * Shows each node's bubble sequentially to visualize data flow
   * Results are released progressively so the animation matches the data flow
   */
  function startBubbleAnimation() {
    // Clear any existing animation
    if (animationTimer) {
      clearTimeout(animationTimer)
      animationTimer = null
    }
    activeNodeId.value = null
    executionResults.value = {}  // Clear for fresh animation

    // Filter out duplicates and terminal nodes (collector/display) for cleaner animation
    const uniqueNodes = [...new Set(executionOrder.value)].filter(nodeId => {
      const node = workflow.value.nodes.find(n => n.id === nodeId)
      return node && node.type !== 'collector' && node.type !== 'display'
    })

    if (uniqueNodes.length === 0) {
      // No animation nodes, just show all results immediately
      executionResults.value = { ...hiddenResults.value }
      return
    }

    const BUBBLE_DURATION = 800  // ms per bubble
    let index = 0

    function showNextBubble() {
      if (index < uniqueNodes.length) {
        const nodeId = uniqueNodes[index]
        if (nodeId && hiddenResults.value[nodeId]) {
          // Release this node's result - create new object for Vue reactivity
          executionResults.value = {
            ...executionResults.value,
            [nodeId]: hiddenResults.value[nodeId]
          }
          activeNodeId.value = nodeId
          console.log(`[Canvas Animation] Showing bubble for: ${nodeId}`)
        }
        index++
        animationTimer = setTimeout(showNextBubble, BUBBLE_DURATION)
      } else {
        // Animation complete - release any remaining results
        executionResults.value = { ...hiddenResults.value }
        activeNodeId.value = null
        console.log('[Canvas Animation] Complete')
      }
    }

    // Start animation
    showNextBubble()
  }

  /**
   * Stop bubble animation
   * Shows all results immediately when stopped
   */
  function stopBubbleAnimation() {
    if (animationTimer) {
      clearTimeout(animationTimer)
      animationTimer = null
    }
    // Show all results immediately when animation stopped
    executionResults.value = { ...hiddenResults.value }
    activeNodeId.value = null
  }

  /**
   * Start workflow execution with SSE streaming
   * Real-time progress updates arrive via SSE
   */
  async function executeWorkflow() {
    if (!isWorkflowValid.value) {
      error.value = 'Workflow is not valid'
      console.error('[Canvas] Cannot execute invalid workflow:', validationErrors.value)
      return
    }

    isExecuting.value = true
    error.value = null
    executionResults.value = {}
    collectorOutput.value = []
    collectorStem.value = canvasFileStem(workflow.value)
    collectorTitles.value = Object.fromEntries(
      workflow.value.nodes
        .filter(n => (n.title || '').trim())
        .map(n => [n.id, (n.title || '').trim()]))
    cardMeta.value = {}
    currentProgress.value = null
    totalNodes.value = 0
    completedNodes.value = 0

    executionState.value = {
      workflowId: workflow.value.id,
      status: 'running',
      currentIteration: 1,
      totalIterations: workflow.value.loops?.maxIterations || 1,
      nodeStates: new Map(),
      startTime: Date.now()
    }

    console.log('[Canvas] Starting streaming workflow execution...')

    try {
      const handle = startCanvasRun(
        {
          nodes: workflow.value.nodes,
          connections: workflow.value.connections,
          device_id: deviceId,  // Consistent folder structure
          // A reading node writes in the language the surface is in.
          lang: i18n.global.locale.value,
          workflow: {
            id: workflow.value.id,
            name: workflow.value.name
          }
        },
        {
          onEvent: (event) => {
            console.log(`[Canvas SSE] ${event.type}:`, event.data)

            switch (event.type) {
              case 'started': {
                const data = event.data as { total_nodes: number }
                totalNodes.value = data.total_nodes
                console.log(`[Canvas] Execution started with ${data.total_nodes} nodes`)
                break
              }

              case 'progress': {
                const data = event.data as {
                  node_id: string
                  node_type: string
                  status: string
                  message: string
                }
                currentProgress.value = data
                console.log(`[Canvas] Progress: ${data.message}`)
                break
              }

              case 'node_complete': {
                const data = event.data as {
                  node_id: string
                  node_type: string
                  output_preview?: unknown
                }
                completedNodes.value++
                console.log(`[Canvas] Node complete: ${data.node_id} (${completedNodes.value}/${totalNodes.value})`)
                break
              }

              case 'complete': {
                const data = event.data as {
                  results: Record<string, unknown>
                  collectorOutput: Array<{
                    nodeId: string
                    nodeType: string
                    output: unknown
                    error: string | null
                  }>
                  cardMeta?: Record<string, {
                    prompt?: string
                    model_meta?: Record<string, any> | null
                    created_at?: number
                    run_id?: string
                  }>
                  executionOrder: string[]
                }

                // Store results hidden for staged animation release
                hiddenResults.value = data.results as typeof hiddenResults.value || {}
                executionResults.value = {}  // Keep empty - animation will populate
                collectorOutput.value = data.collectorOutput || []
                cardMeta.value = data.cardMeta || {}
                executionOrder.value = data.executionOrder || []

                if (executionState.value) {
                  executionState.value.status = 'completed'
                  executionState.value.endTime = Date.now()
                }

                currentProgress.value = null
                console.log('[Canvas] Execution completed:', data.executionOrder)
                console.log('[Canvas] Collector output:', collectorOutput.value)

                // Start bubble animation replay (progressively releases results)
                startBubbleAnimation()
                break
              }

              case 'error': {
                // A failed run is a record too, the same one 'complete' carries
                // (services/canvas_run_service.py): what its other branches made
                // stays in the drawer, and the node that stopped shows why; the
                // message alone would show nothing of that.
                const data = event.data as {
                  message: string
                  errors?: Array<{
                    node_id: string
                    node_type: string
                    error: string
                    blocked?: {
                      stage: number | string
                      reason: string
                      found_terms?: string[]
                      vlm_description?: string | null
                      operational?: boolean
                    }
                  }>
                  results?: Record<string, unknown>
                  collectorOutput?: typeof collectorOutput.value
                  cardMeta?: typeof cardMeta.value
                  executionOrder?: string[]
                }
                error.value = data.message || 'Execution failed'
                hiddenResults.value = (data.results as typeof hiddenResults.value) || {}
                executionResults.value = {}
                collectorOutput.value = data.collectorOutput || []
                cardMeta.value = data.cardMeta || {}
                executionOrder.value = data.executionOrder || []
                if (executionState.value) {
                  executionState.value.status = 'failed'
                  executionState.value.endTime = Date.now()
                }
                currentProgress.value = null
                console.error('[Canvas] Execution error:', data.message)
                // A refusal of the platform's checks goes where every surface
                // sends one: the safety window, in the reader's language.
                const block = (data.errors || []).find(e => e.blocked)?.blocked
                if (block) {
                  useSafetyEventStore().reportBlock(
                    block.stage, block.reason, block.found_terms || [],
                    block.vlm_description || undefined, !!block.operational,
                  )
                }
                startBubbleAnimation()
                break
              }
            }
          }
        }
      )

      const outcome = await handle.done
      if (outcome.kind === 'transport_error' || (outcome.kind === 'torn' && outcome.error)) {
        // Legacy behavior: every thrown transport failure funnels into one error path.
        // outcome.error is the RAW thrown value (unknown), so the instanceof branch
        // below is live for non-Error throws — exactly the pre-refactor semantics.
        const err = outcome.error
        error.value = err instanceof Error ? err.message : 'Network error'
        if (executionState.value) {
          executionState.value.status = 'failed'
          executionState.value.endTime = Date.now()
        }
        currentProgress.value = null
        console.error('[Canvas] Execution fetch error:', err)  // logs the raw value, as before
      }
      // 'complete' / 'server_error': state was already set inside onEvent.
      // torn WITHOUT error (clean EOF, no terminal event): legacy no-op — error
      // stays null and executionState stays 'running' (preserved quirk).
      // 'aborted' cannot occur (this consumer never calls cancel()).
    } finally {
      isExecuting.value = false
    }
  }

  /**
   * Execute workflow in batch mode
   *
   * @param count Number of runs (for seed variance)
   * @param prompts Optional list of prompts (overrides count if provided)
   * @param baseSeed Optional base seed for reproducibility
   */
  async function executeBatch(count: number = 1, prompts?: string[], baseSeed?: number) {
    if (isBatchExecuting.value) {
      console.warn('[Canvas] Batch already executing')
      return
    }

    // Reset batch state
    isBatchExecuting.value = true
    batchId.value = null
    batchTotalRuns.value = prompts?.length || count
    batchCompletedRuns.value = 0
    batchCurrentRun.value = 0
    batchExportPaths.value = []
    error.value = null

    console.log(`[Canvas] Starting batch execution: ${batchTotalRuns.value} runs`)

    try {
      const response = await fetch('/api/canvas/execute-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow: {
            // Recorded with each run, so a kept output opens its board under its name.
            name: workflow.value.name,
            nodes: workflow.value.nodes,
            connections: workflow.value.connections
          },
          device_id: deviceId,  // Consistent folder structure
          count: prompts ? undefined : count,
          prompts: prompts,
          base_seed: baseSeed,
          // Same as the single run: a reading writes in the surface's language.
          lang: i18n.global.locale.value
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      // Handle SSE stream
      if (!response.body) {
        throw new Error('No response body')
      }

      // Where a frame ends is the shared reader's business, not this store's.
      // The batch route names its events in an `event:` line, but this loop has
      // always told them apart by which fields the payload carries, and that
      // reading is unchanged below — so the name is not asked for here.
      for await (const frame of readSseFrames<any>(response.body)) {
        const data = frame.data
        // A payload that is not an object says nothing this loop can read.
        // Reaching into it would end the whole batch on a single bad frame,
        // where the reading it replaces skipped that frame and went on.
        if (!data || typeof data !== 'object') continue

        // Handle different event types
        if (data.batch_id) {
          batchId.value = data.batch_id
        }
        if (data.run_index !== undefined) {
          batchCurrentRun.value = data.run_index
        }
        if (data.export_path) {
          batchExportPaths.value.push(data.export_path)
          batchCompletedRuns.value = batchExportPaths.value.length
        }
        if (data.error) {
          console.error(`[Canvas] Batch run ${data.run_index} error:`, data.error)
        }
        if (data.export_paths) {
          // Batch complete
          batchExportPaths.value = data.export_paths
          batchCompletedRuns.value = data.total_runs
        }
      }

      console.log(`[Canvas] Batch complete: ${batchCompletedRuns.value}/${batchTotalRuns.value} runs`)

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Batch execution failed'
      console.error('[Canvas] Batch error:', err)
    } finally {
      isBatchExecuting.value = false
    }
  }

  /**
   * Abort a running batch execution
   */
  async function abortBatch() {
    if (!batchId.value || !isBatchExecuting.value) {
      console.warn('[Canvas] No batch to abort')
      return false
    }

    try {
      const response = await fetch('/api/canvas/abort-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: batchId.value })
      })

      if (response.ok) {
        console.log(`[Canvas] Abort requested for batch ${batchId.value}`)
        return true
      } else {
        console.error('[Canvas] Abort request failed:', await response.text())
        return false
      }
    } catch (err) {
      console.error('[Canvas] Abort error:', err)
      return false
    }
  }

  // ============================================================================
  // RETURN PUBLIC API
  // ============================================================================

  return {
    // State
    workflow: computed(() => workflow.value),
    nodes,
    connections,
    selectedNodeId: computed(() => selectedNodeId.value),
    selectedNode,
    connectingFromId: computed(() => connectingFromId.value),
    mousePosition: computed(() => mousePosition.value),
    llmModels: computed(() => llmModels.value),
    outputConfigs: computed(() => outputConfigs.value),
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),
    executionState: computed(() => executionState.value),
    isExecuting: computed(() => isExecuting.value),
    executionResults: computed(() => executionResults.value),
    collectorOutput: computed(() => collectorOutput.value),
    collectorStem: computed(() => collectorStem.value),
    collectorTitles: computed(() => collectorTitles.value),
    keptBoard: computed(() => keptBoard.value),
    presetBoard: computed(() => presetBoard.value),
    setKeptBoard,
    setPresetBoard,
    cardMeta: computed(() => cardMeta.value),
    activeNodeId: computed(() => activeNodeId.value),  // For bubble animation
    connectingLabel: computed(() => connectingLabel.value),  // For cable color during drag
    currentProgress: computed(() => currentProgress.value),  // SSE streaming progress
    totalNodes: computed(() => totalNodes.value),  // Total nodes count
    completedNodes: computed(() => completedNodes.value),  // Completed nodes count

    // Computed
    isConnecting,
    isWorkflowValid,
    validationErrors,

    // Node actions
    addNode,
    updateNodePosition,
    updateNodeConfig,
    updateNode,
    deleteNode,
    selectNode,

    // Connection actions
    startConnection,
    cancelConnection,
    completeConnection,
    completeConnectionFeedback,
    completeConnectionToInput,
    deleteConnection,
    updateMousePosition,

    // Workflow actions
    newWorkflow,
    loadWorkflow,
    exportWorkflow,
    updateWorkflowMeta,

    // Config loading
    loadLLMModels,
    loadOutputConfigs,
    loadVisionModels,
    loadAllConfigs,
    visionModels: computed(() => visionModels.value),

    // Execution
    executeWorkflow,

    // Batch execution
    isBatchExecuting: computed(() => isBatchExecuting.value),
    batchId: computed(() => batchId.value),
    batchTotalRuns: computed(() => batchTotalRuns.value),
    batchCompletedRuns: computed(() => batchCompletedRuns.value),
    batchCurrentRun: computed(() => batchCurrentRun.value),
    batchExportPaths: computed(() => batchExportPaths.value),
    executeBatch,
    abortBatch  // Batch abort
  }
})
