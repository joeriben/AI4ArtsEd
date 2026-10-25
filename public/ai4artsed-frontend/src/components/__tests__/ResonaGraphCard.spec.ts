/**
 * The apparatus card and what reaches it.
 *
 * Resona authors an apparatus, the platform runs it, and the card is where the
 * room watches that happen. It never did: the box was a plain object inside a
 * shallowRef, the card takes it as ONE prop, and a plain object mutated in
 * place keeps its identity — so Vue compared the child's props, found them
 * unchanged and skipped the card. Every apparatus stood at "wird aufgebaut"
 * for the whole of its run and past the end of it, while the run itself
 * completed on the server and wrote its images to disk (measured 2026-09-07).
 *
 * These tests are written against the BOX, not against the run: what is pinned
 * is that a change to the box is a change on the card.
 */
import { describe, it, expect } from 'vitest'
import { shallowReactive, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import i18n from '@/i18n'
import ResonaGraphCard from '../ResonaGraphCard.vue'
import type { GraphRunBox } from '@/views/resona_graph_types'

function freshBox(): GraphRunBox {
  return shallowReactive({
    id: 'graph-test',
    intentId: 'gi_test',
    title: 'Perspektive gegen Rohtext',
    motivation: null,
    summary: 'input → interception → generation',
    workflow: { nodes: [], connections: [] },
    status: 'running',
    progress: [],
    results: [],
    lastEventIndex: -1,
    recovered: [],
    startedAt: Date.now(),
  }) as GraphRunBox
}

function card(box: GraphRunBox) {
  return mount(ResonaGraphCard, { props: { box }, global: { plugins: [i18n] } })
}

describe('ResonaGraphCard — the apparatus at work', () => {
  it('shows a step the moment the run reports it', async () => {
    const box = freshBox()
    const w = card(box)
    expect(w.findAll('.progress-row').length).toBe(1) // the waiting line

    box.progress = [{ nodeId: 'motiv', nodeType: 'input', message: 'Processing Input' }]
    await nextTick()
    expect(w.text()).toContain('input')

    box.progress = [...box.progress, { nodeId: 'linse', nodeType: 'interception' }]
    await nextTick()
    expect(w.text()).toContain('interception')
    expect(w.findAll('.progress-row').length).toBe(2)
    w.unmount()
  })

  it('turns from running to finished, and shows what was made', async () => {
    const box = freshBox()
    const w = card(box)
    expect(w.find('.results-list').exists()).toBe(false)

    box.results = [
      { nodeId: 'bild', nodeType: 'generation', kind: 'image', url: '/api/media/image/run_x/0' },
      { nodeId: 'vergleich', nodeType: 'comparison_evaluator', kind: 'text', text: 'Die beiden Bilder …' },
    ]
    box.status = 'complete'
    await nextTick()

    expect(w.find('.results-list').exists()).toBe(true)
    expect(w.find('.result-image').attributes('src')).toBe('/api/media/image/run_x/0')
    expect(w.text()).toContain('Die beiden Bilder')
    w.unmount()
  })

  it('says so when the run broke', async () => {
    const box = freshBox()
    const w = card(box)
    box.status = 'error'
    box.error = 'Execution failed'
    await nextTick()
    expect(w.find('.graph-status').classes()).toContain('status-error')
    w.unmount()
  })
})
