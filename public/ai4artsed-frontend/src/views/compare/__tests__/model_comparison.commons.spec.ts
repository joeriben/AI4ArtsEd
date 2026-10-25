/**
 * The found-pictures row, now that its lookup travels on the platform's
 * streamed transport.
 *
 * POST /api/commons/lookup is the longest silent POST on this platform. At the
 * kids and youth levels it works through up to nine candidate pictures and each
 * of them costs two model calls by the service's own reckoning, on top of the
 * call that turns the prompt into a search term: up to nineteen model calls,
 * each queueing for the plant-wide GPU slot, inside a request that said nothing
 * — while the edge in front of this server ends one that has been silent for
 * about 100 seconds. The row was looked up, checked, and thrown away.
 *
 * Only the transport changed. What the row SAYS is the thing to keep: three of
 * its four states are findings about the participant's prompt and the fourth is
 * about this platform, and an outage may never be shown as one of the first
 * three. Every one of them is driven here.
 *
 * Nothing here reaches Wikimedia or a model: `fetch` is a stand-in throughout.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import ModelComparison from '../model_comparison.vue'

class NoWatcher {
  observe() {}
  unobserve() {}
  disconnect() {}
}
const browser = globalThis as any
browser.ResizeObserver ??= NoWatcher
browser.IntersectionObserver ??= NoWatcher
browser.requestAnimationFrame ??= (cb: (t: number) => void) =>
  setTimeout(() => cb(0), 0) as unknown as number
browser.cancelAnimationFrame ??= (id: number) => clearTimeout(id as never)
browser.matchMedia ??= () => ({
  matches: false,
  media: '',
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
})
browser.scrollTo ??= () => {}

const LOOKUP = '/api/commons/lookup'
const PROMPT = 'ein haus am feldrand'

const A_ROW = {
  state: 'ok',
  term: 'house',
  images: [{ title: 'A house at dusk.jpg', thumb_proxy: '/api/commons/image/abc' }],
}

function streamed(body: unknown, httpStatus = 200): Response {
  const frames = [
    ': heartbeat\n\n',
    'event: complete\ndata: ' + JSON.stringify({ http_status: httpStatus, body }) + '\n\n',
  ]
  const encoder = new TextEncoder()
  let i = 0
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'text/event-stream' },
    json: () => Promise.resolve(null),
    body: {
      getReader: () => ({
        read: () =>
          i < frames.length
            ? Promise.resolve({ done: false, value: encoder.encode(frames[i++]!) })
            : Promise.resolve({ done: true, value: undefined }),
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

/** The stream that never opened: the status line is the whole answer. */
function refusedBeforeTheStream(status: number, body: unknown): Response {
  return {
    ok: false,
    status,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve(body),
  } as unknown as Response
}

/**
 * The half-deployed pair: a 200 carrying one plain JSON body where the frames
 * were asked for.
 *
 * The bundle in the browser is built on a machine and the backend comes from
 * git, so for the minutes between the two a page that asks for the stream can
 * reach a server that answers this route with a single object — which is what
 * this route did until 2026-09-05.
 */
function notStreamed(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve(body),
    // Present, so the reader gets as far as looking at the content type: a
    // response with no body at all is a torn connection and a different case.
    body: {
      getReader: () => ({
        read: () => Promise.resolve({ done: true, value: undefined }),
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

function nothingInParticular(): Response {
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve({}),
  } as unknown as Response
}

const queued = new Map<string, (Response | Error)[]>()
const fetchMock = vi.fn(async (input: any) => {
  const url = String(input)
  for (const [route, answers] of queued) {
    if (!url.includes(route) || !answers.length) continue
    const next = answers.shift()!
    if (next instanceof Error) throw next
    return next
  }
  return nothingInParticular()
}) as unknown as ReturnType<typeof vi.fn>

function answerOn(route: string, answer: Response | Error) {
  const answers = queued.get(route) ?? []
  answers.push(answer)
  queued.set(route, answers)
}

function sentTo(route: string) {
  const call = (fetchMock as any).mock.calls.find((c: any[]) => String(c[0]).includes(route))
  expect(call, `nothing was sent to ${route}`).toBeTruthy()
  return { url: String(call[0]), body: JSON.parse(String(call[1]?.body)) }
}

let w: VueWrapper<any>
let vm: any

beforeEach(async () => {
  setActivePinia(createPinia())
  queued.clear()
  ;(fetchMock as any).mockClear()
  vi.stubGlobal('fetch', fetchMock)
  w = mount(ModelComparison, { global: { plugins: [i18n] } })
  vm = w.vm
  await new Promise((resolve) => setTimeout(resolve, 0))
  ;(fetchMock as any).mockClear()
})

afterEach(() => {
  w?.unmount()
  vi.unstubAllGlobals()
})

describe('the found-pictures row', () => {
  it('asks for the lookup on the stream and shows what came back', async () => {
    answerOn(LOOKUP, streamed({ success: true, ...A_ROW }))

    await vm.lookupFoundImages(PROMPT)

    expect(sentTo(LOOKUP).body).toEqual({
      prompt: PROMPT,
      // Both names of the one transport this client speaks.
      enable_streaming: true,
      enable_answer_streaming: true,
    })
    expect(vm.foundState).toBe('ok')
    expect(vm.foundTerm).toBe('house')
    expect(vm.foundImages).toEqual(A_ROW.images)
  })

  it('keeps the three findings about the prompt apart', async () => {
    for (const state of ['ok', 'no_motif', 'nothing_found']) {
      answerOn(LOOKUP, streamed({ success: true, state, term: 'house', images: [] }))
      await vm.lookupFoundImages(PROMPT)
      expect(vm.foundState).toBe(state)
    }
  })

  it('says an outage is an outage, and never a finding about the prompt', async () => {
    // The route answers 200 in all four outcomes; `error` is the one that says
    // something about US. It must not arrive as "nothing was found".
    answerOn(LOOKUP, streamed({ success: true, state: 'error', term: null, images: [] }))

    await vm.lookupFoundImages(PROMPT)

    expect(vm.foundState).toBe('error')
    expect(vm.foundImages).toEqual([])
  })

  it('reads a state it does not know as an outage rather than as a finding', async () => {
    answerOn(LOOKUP, streamed({ success: true, state: 'something new', images: [] }))

    await vm.lookupFoundImages(PROMPT)

    expect(vm.foundState).toBe('error')
  })

  it('says so when the stream never opened', async () => {
    answerOn(LOOKUP, refusedBeforeTheStream(503, { error: 'no GPU' }))

    await vm.lookupFoundImages(PROMPT)

    expect(vm.foundState).toBe('error')
    expect(vm.foundImages).toEqual([])
  })

  it('lets the status refuse an answer whose body would have read as a row', async () => {
    // What the `res.status >= 400` gate is FOR, and the only test here that can
    // tell whether it is still there: every status resolves on this call, so
    // the status is the one place a refusal is left to be read. The other tests
    // cannot see it — for each of them a refused answer and a 200 carrying the
    // same body both end at `error` anyway.
    //
    // The rule this pins: what the server refused is never shown as a finding
    // about the participant's prompt, whatever stands in its body.
    answerOn(LOOKUP, streamed({ success: true, ...A_ROW }, 503))

    await vm.lookupFoundImages(PROMPT)

    expect(vm.foundState).toBe('error')
    expect(vm.foundTerm).toBeNull()
    expect(vm.foundImages).toEqual([])
  })

  it('reads a plain body as the answer it is where the deploy is half done', async () => {
    // The row was found, checked and answered; only the WAY BACK is the one
    // this bundle stopped asking for. Reading it as a torn connection would put
    // an outage on the screen for an archive that had answered — which is the
    // shape that once let three image-check sites read a refusal the server had
    // delivered as a network failure.
    const complained = vi.spyOn(console, 'warn').mockImplementation(() => {})
    answerOn(LOOKUP, notStreamed({ success: true, ...A_ROW }))

    await vm.lookupFoundImages(PROMPT)

    expect(vm.foundState).toBe('ok')
    expect(vm.foundTerm).toBe('house')
    expect(vm.foundImages).toEqual(A_ROW.images)
    // Said out loud all the same, so whoever is deploying can see the two
    // halves differ. Nobody opens a console in a workshop, and the run has in
    // any case succeeded.
    expect(complained).toHaveBeenCalled()
    complained.mockRestore()
  })

  it('gives the row to the later of two lookups that overlap', async () => {
    // Two in flight at once, which is what a second press before the first
    // answer produces. The row is slower than the grid whenever a provider is
    // slow, so without `foundRunToken` the earlier answer lands last and the
    // row shows the previous prompt underneath the current pictures — with the
    // heading still reading "Found for this prompt".
    answerOn(LOOKUP, streamed({ success: true, state: 'ok', term: 'tree', images: [] }))
    answerOn(LOOKUP, streamed({ success: true, ...A_ROW }))

    const earlier = vm.lookupFoundImages('ein baum am feldrand')
    const later = vm.lookupFoundImages(PROMPT)
    await Promise.all([earlier, later])

    expect(vm.foundState).toBe('ok')
    expect(vm.foundTerm).toBe('house')
    expect(vm.foundImages).toEqual(A_ROW.images)
  })

  it('says so when the connection tore', async () => {
    answerOn(LOOKUP, new TypeError('Failed to fetch'))

    await vm.lookupFoundImages(PROMPT)

    expect(vm.foundState).toBe('error')
  })

  it('writes nothing where the row is no longer about this prompt', async () => {
    // The row is slower than the grid whenever a provider is slow. Without this
    // an earlier, slower answer lands after a later one and the row shows the
    // previous prompt underneath the current pictures.
    answerOn(LOOKUP, streamed({ success: true, ...A_ROW }))
    const stale = vm.lookupFoundImages(PROMPT)
    vm.clearFoundRow()
    await stale

    expect(vm.foundState).toBe('idle')
    expect(vm.foundImages).toEqual([])
  })
})
