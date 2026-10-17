import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCanvasStore } from '../canvas'

/**
 * The generation node's parameter input (2026-09-27). Before it, the node had
 * two inputs of one connection each: with the prompt on 1, one of seed,
 * resolution and quality fitted on 2 and the other two could not be connected.
 */

beforeEach(() => {
  setActivePinia(createPinia())
})

function connect(store: ReturnType<typeof useCanvasStore>, from: string, to: string, input: string) {
  store.startConnection(from)
  return store.completeConnectionToInput(to, input)
}

function graph() {
  const store = useCanvasStore()
  const text = store.addNode('input', 0, 0)
  const gen = store.addNode('generation', 400, 0)
  const seed = store.addNode('seed', 0, 200)
  const res = store.addNode('resolution', 0, 300)
  const quality = store.addNode('quality', 0, 400)
  return { store, text: text.id, gen: gen.id, seed: seed.id, res: res.id, quality: quality.id }
}

describe('canvas store: the parameter input of a generation node', () => {
  it('takes seed, resolution and quality next to a prompt', () => {
    const g = graph()
    expect(connect(g.store, g.text, g.gen, 'input-1')).toBe(true)
    expect(connect(g.store, g.seed, g.gen, 'params')).toBe(true)
    expect(connect(g.store, g.res, g.gen, 'params')).toBe(true)
    expect(connect(g.store, g.quality, g.gen, 'params')).toBe(true)
    const labels = g.store.workflow.connections
      .filter(c => c.targetId === g.gen)
      .map(c => c.label)
    expect(labels).toEqual(['input-1', 'params', 'params', 'params'])
  })

  it('puts a parameter node dropped on a prompt input on the parameter input', () => {
    const g = graph()
    expect(connect(g.store, g.seed, g.gen, 'input-2')).toBe(true)
    expect(g.store.workflow.connections.at(-1)?.label).toBe('params')
    // ... and input 2 is still free for text
    expect(connect(g.store, g.text, g.gen, 'input-2')).toBe(true)
  })

  it('refuses a second node of the same parameter type', () => {
    const g = graph()
    const seed2 = g.store.addNode('seed', 0, 500).id
    expect(connect(g.store, g.seed, g.gen, 'params')).toBe(true)
    expect(connect(g.store, seed2, g.gen, 'params')).toBe(false)
  })

  it('refuses text on the parameter input', () => {
    const g = graph()
    expect(connect(g.store, g.text, g.gen, 'params')).toBe(false)
  })

  it('refuses a parameter node on a comparison', () => {
    const g = graph()
    const cmp = g.store.addNode('comparison_evaluator', 400, 300).id
    expect(connect(g.store, g.seed, cmp, 'input-1')).toBe(false)
  })
})
