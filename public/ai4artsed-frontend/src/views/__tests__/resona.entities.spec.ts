/**
 * What a room worked out stands on the board, once.
 *
 * The produced media were once the only entities there,
 * and a strategy the group kept, a note Resona wrote and a passage she opened
 * left no trace. Each gets a small square card — a name on the front, an
 * excerpt on the back.
 *
 * A card is announced twice, like an apparatus: once when the tool returns, so
 * that a sentence cut mid-word cannot take it along, and once in the closing
 * payload for a surface that opened late. The board is meant to show one.
 *
 * Nothing here reaches the server: the chat stream is a stand-in.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'

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

vi.mock('@/composables/useCanvasRunStream', () => ({
  startCanvasRun: () => ({ done: new Promise(() => {}), runId: null, lastEventIndex: -1, cancel() {} }),
  fetchCanvasPartial: async () => null,
}))

import Resona from '../resona.vue'

const KEPT = {
  kind: 'apparatus',
  key: 'strategy:cw_03aacf6f:v1',
  name: 'Verniedlichung: Zufallsmotiv durch Harmonisierungs-Linse',
  detail: 'die Linse macht aus jedem Motiv etwas Freundliches',
  facts: ['cw_03aacf6f · v1', 'verwandlung'],
}

const PAGE = {
  kind: 'page',
  key: 'web:https://example.org/tagung',
  name: 'Kunst und Künstliche Intelligenz — Tagung',
  detail: '',
  facts: ['https://example.org/tagung'],
}

function done(extra: Record<string, unknown> = {}) {
  return {
    type: 'done', reply: 'Aufbewahrt.',
    thinking: null, context_used: false, run_id: null,
    generated_media: [], generated_graphs: [], generated_compositions: [],
    worked_entities: [], evidence_violations: [], broke_off: null, ...extra,
  }
}

async function open() {
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })))
  const w = mount(Resona, { global: { plugins: [i18n] } })
  await flushPromises()
  return w
}

async function say(w: any, text: string, frames: any[]) {
  chatFrames.length = 0
  chatFrames.push(...frames)
  const box = w.find('textarea')
  await box.setValue(text)
  await box.trigger('keydown.enter')
  await flushPromises()
  await flushPromises()
}

const names = (w: any) => w.findAll('.ec-name').map((e: any) => e.text())

describe('Together — the anchors for what a room worked out', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('lays a card down the moment the tool returns', async () => {
    const w = await open()
    await say(w, 'heb das auf', [{ type: 'entity', entity: KEPT }, done()])
    expect(names(w)).toEqual([KEPT.name])
  })

  it('shows one card when the event and the closing payload both carry it', async () => {
    const w = await open()
    await say(w, 'heb das auf', [
      { type: 'entity', entity: KEPT },
      done({ worked_entities: [KEPT] }),
    ])
    expect(names(w)).toEqual([KEPT.name])
  })

  it('shows the card from the closing payload alone', async () => {
    const w = await open()
    await say(w, 'heb das auf', [done({ worked_entities: [KEPT] })])
    expect(names(w)).toEqual([KEPT.name])
  })

  it('lays the same thing down once, however many turns touch it', async () => {
    const w = await open()
    await say(w, 'heb das auf', [{ type: 'entity', entity: KEPT }, done()])
    await say(w, 'und nochmal', [{ type: 'entity', entity: KEPT }, done()])
    expect(names(w)).toEqual([KEPT.name])
  })

  it('keeps a failed turn’s anchors', async () => {
    const w = await open()
    await say(w, 'heb das auf', [{
      type: 'error', error: 'Internal server error', details: 'boom',
      generated_media: [], generated_graphs: [], generated_compositions: [],
      worked_entities: [KEPT],
    }])
    expect(names(w)).toEqual([KEPT.name])
  })

  it('leaves an external page’s text on the page', async () => {
    const w = await open()
    await say(w, 'lies das', [{ type: 'entity', entity: PAGE }, done()])
    expect(names(w)).toEqual([PAGE.name])
    // Only the link travels; the body was never sent and is nowhere on the board.
    expect(w.text()).not.toContain('example.org/andere-seite')
  })

  it('passes over an entity with nothing to name it', async () => {
    const w = await open()
    await say(w, 'heb das auf', [
      { type: 'entity', entity: { kind: 'note', key: 'note:x', name: '' } },
      done(),
    ])
    expect(names(w)).toEqual([])
  })
})
