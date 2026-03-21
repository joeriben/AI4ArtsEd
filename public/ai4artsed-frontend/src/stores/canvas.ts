import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useDeviceId } from '@/composables/useDeviceId'
import type {
  CanvasNode,
  CanvasConnection,
  CanvasWorkflow,
  StageType,
  NodeExecutionState,
  WorkflowExecutionState,
  LLMModelSummary,
  OutputConfigSummary
} from '@/types/canvas'
import {
  generateNodeId,
  createDefaultWorkflow,
  getNodeTypeDefinition,
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
 *
 * Session 129: Phase 1 Implementation
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

  /** Session 134 Phase 3b: Label for the connection being created (passthrough/commented/commentary) */
  const connectingLabel = ref<string | null>(null)

  /** Current mouse position (for connection preview) */
  const mousePosition = ref({ x: 0, y: 0 })

  /** Available LLM models for interception/translation nodes */
  const llmModels = ref<LLMModelSummary[]>([])

  /** Session 152: Available Vision models for image_evaluation nodes */
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
  const collectorOutput = ref<Array<{
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
  }>>([])

  /** Session 135: Active node for bubble animation (shows one at a time) */
  const activeNodeId = ref<string | null>(null)

  /** Session 135: Execution order for replay animation */
  const executionOrder = ref<string[]>([])

  /** Session 136: Hidden results for staged animation release */
  const hiddenResults = ref<Record<string, {
    type: string
    output: unknown
    error: string | null
    model?: string
  }>>({})

  /** Session 141: Current progress during streaming execution */
  const currentProgress = ref<{
    node_id: string
    node_type: string
    status: string
    message: string
  } | null>(null)

  /** Session 141: Total nodes for progress display */
  const totalNodes = ref(0)

  /** Session 141: Completed nodes count for progress display */
  const completedNodes = ref(0)

  // Session 149: Batch execution state
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

  /** Session 135: Animation timer reference */
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
   * Session 133: Generation is now optional for text-only workflows
   * Valid workflows:
   * - Input → Interception/Translation → Collector (text only)
   * - Input → Interception → Generation → Collector (with media)
   *
   * NOTE: Safety is NOT checked here - DevServer handles it automatically
   */
  const isWorkflowValid = computed(() => {
    const hasInput = workflow.value.nodes.some(n => n.type === 'input')
    // Session 152: image_input is also a valid source
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

    // Session 140: Check all random_prompt nodes have preset and LLM selected
    const randomPromptNodes = workflow.value.nodes.filter(n => n.type === 'random_prompt')
    const allRandomPromptConfigured = randomPromptNodes.every(n => n.randomPromptPreset && n.randomPromptModel)

    // Session 152: Check all image_evaluation nodes have vision model selected
    const imageEvaluationNodes = workflow.value.nodes.filter(n => n.type === 'image_evaluation')
    const allImageEvaluationConfigured = imageEvaluationNodes.every(n => n.visionModel)

    // Session 152: Check all image_input nodes have image uploaded
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
   * Session 133: Generation is now optional for text-only workflows
   * NOTE: Safety is NOT validated here - DevServer handles it automatically
   */
  const validationErrors = computed(() => {
    const errors: string[] = []

    const hasInput = workflow.value.nodes.some(n => n.type === 'input')
    // Session 152: image_input is also a valid source
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
    // Session 152: Image nodes
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

    // Session 140: Random Prompt validation
    randomPromptNodes.forEach(n => {
      if (!n.randomPromptModel) {
        errors.push(`Random Prompt node needs LLM selection`)
      }
      if (!n.randomPromptPreset) {
        errors.push(`Random Prompt node needs preset selection`)
      }
    })

    // Session 152: Image Input validation
    imageInputNodes.forEach(n => {
      if (!n.imageData?.image_path) {
        errors.push(`Image Input node needs image upload`)
      }
    })

    // Session 152: Image Evaluation validation
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
      config: {}
    }

    // Set default LLM for LLM-based nodes
    const llmNodeTypes: StageType[] = ['random_prompt', 'interception', 'translation', 'evaluation', 'comparison_evaluator']
    if (llmNodeTypes.includes(type)) {
      const defaultModel = llmModels.value.find(m => m.isDefault) || llmModels.value[0]
      if (defaultModel) {
        if (type === 'random_prompt') {
          node.randomPromptModel = defaultModel.id
          node.randomPromptPreset = 'clean_image' // Default preset
          node.randomPromptTokenLimit = 75 // Default: short (CLIP-L)
        } else if (type === 'comparison_evaluator') {
          node.comparisonLlmModel = defaultModel.id
        } else {
          node.llmModel = defaultModel.id
        }
      }
    }

    // Session 151: Set defaults for parameter nodes
    if (type === 'resolution') {
      node.resolutionPreset = 'square_1024'
      node.resolutionWidth = 1024
      node.resolutionHeight = 1024
    } else if (type === 'quality') {
      node.qualitySteps = 25
      node.qualityCfg = 5.5
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
   * Session 134 Phase 3b: Added label parameter for evaluation node outputs
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
    // Session 134 Phase 3b: Include label if present (for evaluation nodes)
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
   * Session 147: Complete a connection to a numbered input (comparison_evaluator)
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

    // Check if connection to this input already exists
    const exists = workflow.value.connections.some(
      c => c.targetId === targetId && c.label === inputLabel
    )

    if (exists) {
      console.warn(`[Canvas] Connection to ${inputLabel} already exists`)
      cancelConnection()
      return false
    }

    // Add the connection with input label
    const newConnection: CanvasConnection = {
      sourceId: connectingFromId.value,
      targetId,
      label: inputLabel
    }
    console.log(`[Canvas] Added connection to ${inputLabel}: ${connectingFromId.value} -> ${targetId}`)
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
    workflow.value = data
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
   * Session 152: Load available Vision models from backend
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
   * Session 135/136: Animate bubbles through execution order
   * Shows each node's bubble sequentially to visualize data flow
   * Session 136: Now progressively releases results for proper animation
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
   * Session 136: Now shows all results immediately when stopped
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
   * Parse SSE event from text chunk
   * Session 141: Helper for streaming execution
   */
  function parseSSEEvents(text: string): Array<{ type: string; data: unknown }> {
    const events: Array<{ type: string; data: unknown }> = []
    const lines = text.split('\n')

    let currentEvent: { type?: string; data?: string } = {}

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent.type = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        currentEvent.data = line.slice(6)
      } else if (line === '' && currentEvent.type && currentEvent.data) {
        // Empty line = end of event
        try {
          events.push({
            type: currentEvent.type,
            data: JSON.parse(currentEvent.data)
          })
        } catch (e) {
          console.warn('[Canvas] Failed to parse SSE data:', currentEvent.data)
        }
        currentEvent = {}
      }
    }

    return events
  }

  /**
   * Start workflow execution with SSE streaming
   * Session 141: Real-time progress updates via SSE
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
      const response = await fetch('/api/canvas/execute-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: workflow.value.nodes,
          connections: workflow.value.connections,
          device_id: deviceId,  // Session 150: Consistent folder structure
          workflow: {
            id: workflow.value.id,
            name: workflow.value.name
          }
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('No response body for streaming')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse complete events from buffer
        const events = parseSSEEvents(buffer)

        // Keep incomplete event data in buffer
        const lastDoubleNewline = buffer.lastIndexOf('\n\n')
        if (lastDoubleNewline !== -1) {
          buffer = buffer.slice(lastDoubleNewline + 2)
        }

        // Handle each event
        for (const event of events) {
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
                executionOrder: string[]
              }

              // Session 136: Store results hidden for staged animation release
              hiddenResults.value = data.results as typeof hiddenResults.value || {}
              executionResults.value = {}  // Keep empty - animation will populate
              collectorOutput.value = data.collectorOutput || []
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
              const data = event.data as { message: string }
              error.value = data.message || 'Execution failed'
              if (executionState.value) {
                executionState.value.status = 'failed'
                executionState.value.endTime = Date.now()
              }
              currentProgress.value = null
              console.error('[Canvas] Execution error:', data.message)
              break
            }
          }
        }
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Network error'
      if (executionState.value) {
        executionState.value.status = 'failed'
        executionState.value.endTime = Date.now()
      }
      currentProgress.value = null
      console.error('[Canvas] Execution fetch error:', err)
    } finally {
      isExecuting.value = false
    }
  }

  /**
   * Session 149: Execute workflow in batch mode
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
            nodes: workflow.value.nodes,
            connections: workflow.value.connections
          },
          device_id: deviceId,  // Session 150: Consistent folder structure
          count: prompts ? undefined : count,
          prompts: prompts,
          base_seed: baseSeed
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      // Handle SSE stream
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event:')) {
            const eventType = line.substring(7).trim()
            continue
          }
          if (line.startsWith('data:')) {
            const dataStr = line.substring(5).trim()
            if (!dataStr) continue

            try {
              const data = JSON.parse(dataStr)

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
            } catch {
              // Skip invalid JSON
            }
          }
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
   * Interrupt workflow execution
   */
  function interruptExecution() {
    if (executionState.value) {
      executionState.value.status = 'interrupted'
      executionState.value.endTime = Date.now()
    }
    isExecuting.value = false
    console.log('[Canvas] Execution interrupted')
  }

  /**
   * Reset execution state
   */
  function resetExecution() {
    executionState.value = null
    isExecuting.value = false
  }

  /**
   * Abort a running batch execution (Session 150)
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
    activeNodeId: computed(() => activeNodeId.value),  // Session 135: For bubble animation
    connectingLabel: computed(() => connectingLabel.value),  // For cable color during drag
    currentProgress: computed(() => currentProgress.value),  // Session 141: SSE streaming progress
    totalNodes: computed(() => totalNodes.value),  // Session 141: Total nodes count
    completedNodes: computed(() => completedNodes.value),  // Session 141: Completed nodes count

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
    interruptExecution,
    resetExecution,

    // Session 149: Batch execution
    isBatchExecuting: computed(() => isBatchExecuting.value),
    batchId: computed(() => batchId.value),
    batchTotalRuns: computed(() => batchTotalRuns.value),
    batchCompletedRuns: computed(() => batchCompletedRuns.value),
    batchCurrentRun: computed(() => batchCurrentRun.value),
    batchExportPaths: computed(() => batchExportPaths.value),
    executeBatch,
    abortBatch  // Session 150: Batch abort
  }
})
