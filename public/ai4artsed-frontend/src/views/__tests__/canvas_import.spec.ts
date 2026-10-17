/**
 * A file the backend exported, opened by the Canvas.
 *
 * Every allegedly built apparatus is written to
 * disk in a format the Canvas can import, so that a run missing from the board
 * can be told apart from a run that was never built.
 *
 * "Importable" is a claim about two pieces of code that never meet, so it is
 * asserted here across the seam. The fixture is not written by hand: it is the
 * output of devserver/my_app/services/canvas_graph_authoring.to_canvas_workflow
 * on a real expanded apparatus (the same graph as
 * devserver/tests/test_canvas_graph_export.py), and what opens it is the very
 * function the Canvas's Import Workflow dialog calls —
 * canvas_workflow.vue:handleImportWorkflow -> canvasStore.loadWorkflow.
 *
 * The fixture is regenerated and compared by
 * devserver/tests/test_canvas_graph_export.py, so it cannot quietly go on
 * describing an exporter that has moved on. Its model names are deliberately
 * not real ones: an installation's roles come from user_settings.json, and a
 * fixture pinned to one machine's settings would break on the next.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCanvasStore } from '@/stores/canvas'
import { getNodeTypeDefinition, type CanvasWorkflow } from '@/types/canvas'
import exported from './fixtures/apparatus_export.json'

describe('an exported apparatus opens in the Canvas', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads every node and every connection', () => {
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    expect(store.nodes).toHaveLength(exported.nodes.length)
    expect(store.connections).toHaveLength(exported.connections.length)
    expect(store.nodes.map(n => n.id).sort()).toEqual(exported.nodes.map(n => n.id).sort())
  })

  it('gives every node a place the board can draw at', () => {
    // CanvasWorkspace.vue reads node.x / node.y straight into a style. A node
    // short of either renders at `left: undefinedpx`, which is where an
    // apparatus without a layout would have landed.
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    for (const n of store.nodes) {
      expect(Number.isFinite(n.x), `${n.id}.x`).toBe(true)
      expect(Number.isFinite(n.y), `${n.id}.y`).toBe(true)
    }
  })

  it('uses only node types the Canvas knows', () => {
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    for (const n of store.nodes) {
      expect(getNodeTypeDefinition(n.type), `unknown node type ${n.type}`).toBeDefined()
    }
  })

  it('keeps what the apparatus was authored with', () => {
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    const byId = Object.fromEntries(store.nodes.map(n => [n.id, n]))
    expect(byId.in!.promptText).toBe('ein Haus am Feldrand')
    expect(byId.lens!.contextPrompt).toBe('Sieh es als Ort.')
    expect(byId.genA!.configId).toBeTruthy()
    expect(byId.cmp!.comparisonCriteria).toBe('Was trennt sie?')
    // The seed the apparatus was given became its own source node during
    // expansion, and the Canvas reads it under the same two keys.
    const seed = store.nodes.find(n => n.type === 'seed')
    expect(seed?.seedMode).toBe('fixed')
    expect(seed?.seedValue).toBe(7)
  })

  it('names the workflow so it is findable after import', () => {
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    expect(store.workflow.name).toBe('Perspektive gegen Rohtext')
    expect(store.workflow.type).toBe('canvas_workflow')
  })

  it('arrives runnable, not just openable', () => {
    // The gate the imported file actually meets. Any one of these leaves Run
    // and Batch disabled, and an apparatus that opens with a dead Run button is
    // a picture of a run.
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    expect(store.validationErrors).toEqual([])
    expect(store.isWorkflowValid).toBe(true)
  })

  it('brings the collector the board insists on, holding the ends and the images', () => {
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    const collectors = store.nodes.filter(n => n.type === 'collector')
    expect(collectors).toHaveLength(1)
    const into = store.connections
      .filter(c => c.targetId === collectors[0]!.id)
      .map(c => c.sourceId)
      .sort()
    expect(into).toEqual(['cmp', 'genA', 'genB'])
  })

  it('lets the two readings arrive at numbered inputs', () => {
    // CanvasWorkspace routes a comparison's incoming edges by these labels.
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    const labels = store.connections
      .filter(c => c.targetId === 'cmp')
      .map(c => c.label)
      .sort()
    expect(labels).toEqual(['input-1', 'input-2'])
  })

  it('shows the question the apparatus was given', () => {
    // StageModule shows the question field only for the preset 'custom' and
    // otherwise prints a framework name, so a node carrying a question and no
    // preset would open claiming a framework it does not run.
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    const read = store.nodes.find(n => n.id === 'readA')
    expect(read?.imageEvaluationPreset).toBe('custom')
    expect(read?.imageEvaluationPrompt).toBe('Was steht da?')
  })

  it('names a model on every node that needs one', () => {
    const store = useCanvasStore()
    store.loadWorkflow(exported as unknown as CanvasWorkflow)
    for (const n of store.nodes) {
      if (n.type === 'interception' || n.type === 'translation') {
        expect(n.llmModel, `${n.id}.llmModel`).toBeTruthy()
      }
      if (n.type === 'image_evaluation') {
        expect(n.visionModel, `${n.id}.visionModel`).toBeTruthy()
      }
    }
  })
})
