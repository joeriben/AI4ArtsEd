/**
 * A platform notice is not something the model said.
 *
 * On 2026-09-09 Together answered a whole turn with "The answer did not arrive.
 * Please send it again." — this platform's own notice for a failed request. The
 * notice had been written into the assistant's line, the surface sends its lines
 * as history, and the model read its own supposed last utterance and went on in
 * that style (backend log 23:29:21: 48 chars, finish_reason=stop, no tool call,
 * no error anywhere).
 *
 * So a notice stands on the line and stays out of what is sent. Both halves are
 * asserted here: it is READ, and it is not HANDED BACK.
 *
 * Nothing here reaches the server: the chat stream is a stand-in that speaks the
 * frames the route writes.
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
const sent: any[] = []

vi.mock('@/lib/sseStream', () => ({
  sseEvents: async function* (_url: string, body: any) {
    sent.push(body)
    for (const ev of chatFrames) yield ev
  },
}))

vi.mock('@/composables/useCanvasRunStream', () => ({
  startCanvasRun: () => ({ done: new Promise(() => {}), runId: null, lastEventIndex: -1, cancel() {} }),
  fetchCanvasPartial: async () => null,
}))

import Resona from '../resona.vue'

function done(extra: Record<string, unknown> = {}) {
  return {
    type: 'done', reply: 'Zwei Wege, nebeneinandergestellt.',
    thinking: null, context_used: false, run_id: null,
    generated_media: [], generated_graphs: [], generated_compositions: [],
    evidence_violations: [], broke_off: null, ...extra,
  }
}

const FAILS = {
  type: 'error', error: 'Internal server error', details: 'boom',
  generated_media: [], generated_graphs: [], generated_compositions: [],
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

/** The turns the last request carried, in the shape the model receives them. */
function historyOfLastRequest(): Array<{ role: string; content: string }> {
  return (sent[sent.length - 1]?.history ?? []) as Array<{ role: string; content: string }>
}

describe('Together — what the platform says about a turn stays the platform’s', () => {
  beforeEach(() => { vi.clearAllMocks(); sent.length = 0 })

  it('reads the notice on the line when the request failed', async () => {
    // The first sentence: the line stands up sentence by sentence, and the rest
    // of a two-sentence notice is still on its way at this point.
    const opening = i18n.global.t('resona.connectionError').split(/(?<=\.)\s/)[0]!
    const w = await open()
    await say(w, 'bau uns einen kleinen Apparat', [FAILS])
    expect(w.text()).toContain(opening)
  })

  it('leaves the notice out of the next request', async () => {
    const w = await open()
    await say(w, 'bau uns einen kleinen Apparat', [FAILS])
    await say(w, 'und nun?', [done()])
    const history = historyOfLastRequest()
    expect(history.some(m => m.content.includes(i18n.global.t('resona.connectionError')))).toBe(false)
    expect(history.some(m => m.role === 'assistant')).toBe(false)
    expect(history.map(m => m.content)).toEqual(['bau uns einen kleinen Apparat'])
  })

  it('leaves the placeholder for an empty reply out of it too', async () => {
    const w = await open()
    await say(w, 'bau uns einen kleinen Apparat', [done({ reply: '' })])
    expect(w.text()).toContain(i18n.global.t('resona.noResponse'))
    await say(w, 'und nun?', [done()])
    const history = historyOfLastRequest()
    expect(history.some(m => m.content.includes(i18n.global.t('resona.noResponse')))).toBe(false)
  })

  it('leaves the broke-off notice out of it too', async () => {
    const w = await open()
    await say(w, 'bau uns einen kleinen Apparat', [
      done({ reply: 'Ich habe zwei Wege nebeneinand',
             broke_off: "ConnectionResetError(104, 'Connection reset by peer')" }),
    ])
    expect(w.text()).toContain(i18n.global.t('resona.replyBrokeOff'))
    await say(w, 'und nun?', [done()])
    const history = historyOfLastRequest()
    expect(history.some(m => m.content.includes(i18n.global.t('resona.replyBrokeOff')))).toBe(false)
    // What the turn actually wrote before it stopped is a turn, and it travels.
    expect(history.some(m => m.role === 'assistant'
                             && m.content === 'Ich habe zwei Wege nebeneinand')).toBe(true)
  })

  it('hands back what was really said', async () => {
    const w = await open()
    await say(w, 'bau uns einen kleinen Apparat', [done()])
    await say(w, 'und nun?', [done()])
    const history = historyOfLastRequest()
    expect(history).toEqual([
      { role: 'user', content: 'bau uns einen kleinen Apparat' },
      { role: 'assistant', content: 'Zwei Wege, nebeneinandergestellt.' },
    ])
  })
})
