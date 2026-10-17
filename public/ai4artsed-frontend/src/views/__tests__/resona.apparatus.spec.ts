/**
 * One apparatus per built apparatus, however often the turn announces it.
 *
 * A turn now says what it built TWICE: once the moment `run_canvas_graph`
 * returns, so that a closing sentence cut mid-word cannot take the built thing
 * with it, and once again in the closing `done` payload — which the blocking
 * mouth of the chat endpoint reads, and which a surface opened late still gets.
 * Both sightings carry the same server-minted intent id, and the board is meant
 * to show one card.
 *
 * Nothing here reaches the server: the chat stream is a stand-in that speaks the
 * frames the route writes, and the canvas run client is a stand-in that starts
 * nothing.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'

// What jsdom lacks and the board asks for while it mounts.
class NoWatcher { observe() {} unobserve() {} disconnect() {} }
const browser = globalThis as any
browser.ResizeObserver ??= NoWatcher
browser.IntersectionObserver ??= NoWatcher
browser.requestAnimationFrame ??= (cb: (t: number) => void) => setTimeout(() => cb(0), 0) as unknown as number
browser.cancelAnimationFrame ??= (id: number) => clearTimeout(id as never)
browser.matchMedia ??= () => ({ matches: false, media: '', addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} })
browser.scrollTo ??= () => {}

const chatFrames: any[] = []

vi.mock('@/lib/sseStream', () => ({
  sseEvents: async function* () {
    for (const ev of chatFrames) yield ev
  },
}))

// The run is somebody else's subject. Started here, it would reach for the
// network; what this file asks is what the BOARD does with an announcement.
vi.mock('@/composables/useCanvasRunStream', () => ({
  startCanvasRun: () => ({
    done: new Promise(() => {}),
    runId: null,
    lastEventIndex: -1,
    cancel() {},
  }),
  fetchCanvasPartial: async () => null,
}))

import Resona from '../resona.vue'

const GRAPH = {
  title: 'Perspektive gegen Rohtext',
  motivation: 'zwei Wege auf dasselbe Motiv',
  intent_id: 'gi_deadbeef',
  summary: 'input -> interception -> generation',
  workflow: {
    nodes: [
      { id: 'i', type: 'input', promptText: 'ein Haus' },
      { id: 'g', type: 'generation', configId: 'sd35_large' },
    ],
    connections: [{ sourceId: 'i', targetId: 'g' }],
  },
}

function done(extra: Record<string, unknown> = {}) {
  return {
    type: 'done', reply: 'Ich habe zwei Wege nebeneinandergestellt.',
    thinking: null, context_used: false, run_id: null,
    generated_media: [], generated_graphs: [], generated_compositions: [],
    evidence_violations: [], broke_off: null, ...extra,
  }
}

async function turn(frames: any[]) {
  chatFrames.length = 0
  chatFrames.push(...frames)
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })))
  const w = mount(Resona, { global: { plugins: [i18n] } })
  await flushPromises()
  const box = w.find('textarea')
  await box.setValue('bau uns einen kleinen Apparat')
  await box.trigger('keydown.enter')
  await flushPromises()
  await flushPromises()
  return w
}

describe('Together — an apparatus announced twice stands once', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('shows one card when the graph event and the closing payload both carry it', async () => {
    const w = await turn([
      { type: 'graph', graph: GRAPH },
      done({ generated_graphs: [GRAPH] }),
    ])
    expect(w.findAll('.graph-title').map(e => e.text())).toEqual([GRAPH.title])
  })

  it('shows the card from the graph event alone', async () => {
    // The closing payload carries NOTHING here, which is the case the event
    // exists for: everything the turn built used to travel only in `done`, and
    // a `done` that never came took the built apparatus with it.
    const w = await turn([
      { type: 'graph', graph: GRAPH },
      done(),
    ])
    expect(w.findAll('.graph-title').map(e => e.text())).toEqual([GRAPH.title])
  })

  it('says under the half sentence that the reply stopped', async () => {
    const w = await turn([
      { type: 'graph', graph: GRAPH },
      done({ reply: 'Ich habe zwei Wege nebeneinand', generated_graphs: [GRAPH],
             broke_off: "ConnectionResetError(104, 'Connection reset by peer')" }),
    ])
    expect(w.findAll('.graph-title')).toHaveLength(1)
    expect(w.text()).toContain(i18n.global.t('resona.replyBrokeOff'))
  })

  it('shows the card when a failed turn hands its built work over', async () => {
    const w = await turn([
      { type: 'error', error: 'Internal server error', details: 'boom',
        generated_media: [], generated_graphs: [GRAPH], generated_compositions: [] },
    ])
    expect(w.findAll('.graph-title')).toHaveLength(1)
  })
})
