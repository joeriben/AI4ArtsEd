/**
 * The three long POSTs of the flow, now that they travel on the platform's
 * streamed transport.
 *
 * All three asked a long route for a plain answer and read it with
 * `res.json()`: the two adaptions (POST /api/schema/pipeline/optimize, a cloud
 * model each, one of them on every single run) and the song (POST
 * /api/schema/pipeline/interception, the whole pipeline plus a music generation
 * behind the plant-wide GPU queue). The edge in front of this server ends a
 * proxied request whose origin has sent nothing for about 100 seconds and hands
 * the browser a 524, so those runs finished on the server and their answers were
 * thrown away.
 *
 * Only the transport changed, and this file is about that word "only": every
 * branch each of them took — the answer, the refusal, the failure, and the
 * spinner that has to go out on all of them — is driven here against a stand-in
 * that speaks the frames the server writes.
 *
 * The song left that POST on 2026-10-06. It goes on the generation stream every
 * run of the page that generates opens (finishRun), with the style tags as its
 * second text, and the box reads its queue place, its checks and a device that holds
 * another run from there. What it sends and what comes back is driven below
 * against a stand-in of that stream.
 *
 * Nothing here reaches a model or the server: `fetch` is a stand-in throughout —
 * one that answers by ROUTE, because the view asks for several things of its own
 * while it mounts — and the Stage 1 + 2 stream in front of the song and the
 * generation stream it goes on are stand-in EventSources.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import { safetyBlockKey } from '@/composables/useGenerationStream'
import X2X from '../x2x_flow.vue'

// What jsdom does not bring and the flow stage asks for on mount. Assigned
// rather than stubbed, so a timer the view left behind still finds them after
// this file's environment is torn down.
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

const OPTIMIZE = '/api/schema/pipeline/optimize'
const INTERCEPTION = '/api/schema/pipeline/interception'
const GENERATION = '/api/schema/pipeline/generation'
const LYRICS = 'ein haus am feldrand, und niemand geht hinein'

/** What the generation stream says, frame by frame, to the run that opens it. */
let generationFrames: [string, unknown][] = []
/** Every stream the view opened, by URL. */
const opened: string[] = []

/**
 * The Stage 1 + 2 stream in front of the song, and the generation stream it
 * goes on, which speaks the frames a test has queued. A frame without data
 * is the connection tearing.
 */
class StandInEventSource {
  static CLOSED = 2
  readyState = 1
  private listeners: Record<string, ((ev: any) => void)[]> = {}
  onerror: (() => void) | null = null
  constructor(public url: string) {
    opened.push(url)
    setTimeout(() => {
      if (url.includes(GENERATION)) {
        for (const [name, data] of generationFrames) this.emit(name, data)
        return
      }
      this.emit('chunk', { text_chunk: LYRICS })
      this.emit('complete', {})
    }, 0)
  }
  addEventListener(name: string, fn: (ev: any) => void) {
    ;(this.listeners[name] ||= []).push(fn)
  }
  removeEventListener() {}
  emit(name: string, data: unknown) {
    const payload = data === undefined ? undefined : JSON.stringify(data)
    for (const fn of this.listeners[name] || []) fn({ data: payload })
  }
  close() {}
}

/** The answer as the server writes it: a beat, then the terminal frame carrying
 *  the body and status a plain POST would have returned. */
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

/** Anything the view asks for that this file is not about. */
function nothingInParticular(): Response {
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve({}),
    text: () => Promise.resolve('{}'),
  } as unknown as Response
}

// The answers this test has queued, by route. Everything else the view asks for
// while it mounts — the model availability, the device pre-check — is answered
// with nothing in particular, so the calls under test can be found by NAME
// rather than by their place in a list this file does not control.
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

/**
 * What a person at the table can read once the call has returned: the run's own
 * judgement, and the face of the generation box that shows it.
 *
 * This file recorded those values through a synchronous watch until 2026-09-05
 * and asserted what it had caught IN PASSING — which was green while the
 * surface showed nothing at all, because the board's own watch cleared all four
 * the moment the run let the box go (x2x_flow.vue, the watch above
 * `onGenClick`, which had `busy` in its source). A refusal that vanishes before
 * anybody can read it is the defect there, so what is asserted here is what
 * STANDS.
 */
async function theSurface() {
  await flushPromises()
  const box = w.find('.gi')
  return {
    safetyState: vm.safetyState as string,
    blockedReason: vm.blockedReason as string,
    blockedStage: vm.blockedStage as number | null,
    error: vm.generationErrorMessage as string,
    /** The info face of the generation box, empty where it is not shown. */
    text: box.exists() ? box.text() : '',
  }
}

let w: VueWrapper<any>
let vm: any

beforeEach(async () => {
  setActivePinia(createPinia())
  queued.clear()
  generationFrames = []
  opened.length = 0
  ;(fetchMock as any).mockClear()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('EventSource', StandInEventSource)
  w = mount(X2X, { global: { plugins: [i18n] } })
  vm = w.vm
  // Let what the view asks for on mount settle, so it cannot be mistaken for
  // what a test asks for.
  await new Promise((resolve) => setTimeout(resolve, 0))
  ;(fetchMock as any).mockClear()
})

afterEach(() => {
  w?.unmount()
  vi.unstubAllGlobals()
})

describe('recaption — the caption for the text that is actually going', () => {
  it('asks the adaption on the stream and hands back the half it wrote', async () => {
    answerOn(
      OPTIMIZE,
      streamed({
        success: true,
        triple_prompt: { clip: 'a house', t5: 'a house at the edge of a field' },
      })
    )

    expect(await vm.recaption('a house at the edge of a field', 'sd35_large')).toBe('a house')

    expect(sentTo(OPTIMIZE).body).toEqual({
      input_text: 'a house at the edge of a field',
      output_config: 'sd35_large',
      // Both names of the one transport this client speaks.
      enable_streaming: true,
      enable_answer_streaming: true,
    })
  })

  it('hands back nothing when the adaption failed, and does not throw for it', async () => {
    // The status resolves and the body is read, which is what this call did
    // when it read `res.json()` without looking at `res.ok`.
    answerOn(OPTIMIZE, streamed({ success: false, error: 'no model' }, 500))
    expect(await vm.recaption('a house', 'sd35_large')).toBe('')
  })

  it('takes the caption out of a body the status refused', async () => {
    // What `validateStatus: () => true` is FOR, and the only test here that can
    // tell whether it is still there. This call reads the caption out of the
    // BODY and never looked at the status — `readHalves(await res.json())`,
    // before the transport changed — so a half the model did write is a half
    // that goes, whatever the route said about the request as a whole. Under
    // the default gate the answer throws before `readHalves` is reached and the
    // caption is lost; the three tests below cannot see the difference, because
    // for each of them the answer is '' either way.
    answerOn(
      OPTIMIZE,
      streamed({ triple_prompt: { clip: 'a house', t5: 'a house at the edge of a field' } }, 500)
    )
    expect(await vm.recaption('a house at the edge of a field', 'sd35_large')).toBe('a house')
  })

  it('hands back nothing when the stream never opened', async () => {
    answerOn(OPTIMIZE, refusedBeforeTheStream(503, { error: 'no GPU' }))
    expect(await vm.recaption('a house', 'sd35_large')).toBe('')
  })

  it('hands back nothing when the connection tore', async () => {
    answerOn(OPTIMIZE, new TypeError('Failed to fetch'))
    expect(await vm.recaption('a house', 'sd35_large')).toBe('')
  })
})

describe('adaptFor — the adaption every run goes through', () => {
  it('reads what the model wrote, and names the model that wrote it', async () => {
    answerOn(
      OPTIMIZE,
      streamed({
        success: true,
        model: 'the-adaption-model',
        optimized_prompt: 'a house at the edge of a field',
        triple_prompt: { clip: 'a house', t5: 'a house at the edge of a field' },
      })
    )
    const token = vm.beginRun()

    expect(await vm.adaptFor('a house', 'sd35_large', token)).toEqual({
      prompt: 'a house at the edge of a field',
      halves: { clip: 'a house', t5: 'a house at the edge of a field' },
      condensed: '',
    })
    expect(vm.adaptionModel).toBe('the-adaption-model')
    expect(vm.adapting).toBe(false)
    expect(sentTo(OPTIMIZE).body).toEqual({
      input_text: 'a house',
      output_config: 'sd35_large',
      enable_streaming: true,
      enable_answer_streaming: true,
    })
  })

  it('says a picture is going with it where one is', async () => {
    answerOn(OPTIMIZE, streamed({ success: true, unchanged: true, optimized_prompt: 'make it rain' }))
    const token = vm.beginRun()

    await vm.adaptFor('make it rain', 'qwen_img2img', token, true)
    expect(sentTo(OPTIMIZE).body).toMatchObject({ has_input_image: true })
  })

  it('takes an unchanged answer as a plain prompt with no halves', async () => {
    answerOn(OPTIMIZE, streamed({ success: true, unchanged: true, optimized_prompt: 'a house' }))
    const token = vm.beginRun()

    expect(await vm.adaptFor('a house', 'commoncanvas_xl_c', token)).toEqual({
      prompt: 'a house',
      halves: null,
      condensed: '',
    })
  })

  it('says how far a text was shortened, and what was left of it', async () => {
    answerOn(
      OPTIMIZE,
      streamed({
        success: true,
        optimized_prompt: 'a house',
        shortened_to_window: true,
        condensed_tokens: 77,
        condensed_text: 'a house at the edge',
      })
    )
    const token = vm.beginRun()

    const out = await vm.adaptFor('a very long text', 'sd35_large', token)
    expect(out.condensed).toBe('a house at the edge')
    expect(vm.condensedTokens).toBe(77)
  })

  it('comes back empty and lets the spinner go when the connection tore', async () => {
    answerOn(OPTIMIZE, new TypeError('Failed to fetch'))
    const token = vm.beginRun()

    expect(await vm.adaptFor('a house', 'sd35_large', token)).toEqual({
      prompt: '',
      halves: null,
      condensed: '',
    })
    expect(vm.adapting).toBe(false)
  })

  it('answers nothing at all where the run has moved on', async () => {
    answerOn(OPTIMIZE, streamed({ success: true, optimized_prompt: 'a house' }))
    const stale = vm.beginRun()
    vm.beginRun()

    expect(await vm.adaptFor('a house', 'sd35_large', stale)).toBeNull()
  })
})

describe('runMusic — the song, the longest run on this page', () => {
  /** The query the song opened the generation stream with. */
  function songQuery(): URLSearchParams {
    const url = opened.find((u) => u.includes(GENERATION))
    expect(url, 'the song opened no generation stream').toBeTruthy()
    return new URL(url!, 'http://flow.test').searchParams
  }

  it('goes on the generation stream with both texts, and puts the song on the table', async () => {
    generationFrames = [
      ['stage3_complete', { safe: true, was_translated: false, checks_passed: ['llm_safety_check'] }],
      ['complete', { media_output: { media_type: 'audio', run_id: 'run-1', index: 0 }, run_id: 'run-1' }],
    ]

    await vm.runMusic({ lyrics: LYRICS, style: 'slow, sparse' })
    await flushPromises()

    const query = songQuery()
    expect(query.get('output_config')).toBe('heartmula_standard')
    expect(query.get('prompt')).toBe(LYRICS)
    expect(query.get('secondary_text')).toBe('slow, sparse')
    expect(query.get('device_id')).toBeTruthy()
    // The interception route sees the Stage 1 + 2 stream of the lyrics and
    // nothing else: no POST of the song's own.
    expect((fetchMock as any).mock.calls.filter((c: any[]) => String(c[0]).includes(INTERCEPTION))).toEqual([])
    expect(vm.mediaType).toBe('audio')
    expect(vm.mediaUrl).toBe('/api/media/audio/run-1/0')
    expect(vm.currentRunId).toBe('run-1')
    expect(vm.directRunning).toBe(false)
  })

  it('sends an empty style as a second text that is empty', async () => {
    generationFrames = [['complete', { media_output: { media_type: 'audio', run_id: 'run-2', index: 0 }, run_id: 'run-2' }]]

    await vm.runMusic({ lyrics: LYRICS, style: '' })
    await flushPromises()

    const query = songQuery()
    expect(query.has('secondary_text')).toBe(true)
    expect(query.get('secondary_text')).toBe('')
  })

  it('leaves the refusal standing, with the stage it was refused at', async () => {
    generationFrames = [['blocked', { stage: 1, reason: 'gesperrt', found_terms: [] }]]

    await vm.runMusic({ lyrics: LYRICS, style: 'slow, sparse' })
    const surface = await theSurface()

    expect(surface.safetyState).toBe('blocked')
    expect(surface.blockedReason).toBe('gesperrt')
    expect(surface.blockedStage).toBe(1)
    // And on the box, which is where somebody has to be able to read it. The
    // backend writes its reasons in German and only in German, so the surface
    // shows the platform's own sentence for this one, never the raw string.
    expect(surface.text).toContain(i18n.global.t('x2xFlow.blocked'))
    expect(surface.text).toContain(i18n.global.t(safetyBlockKey('gesperrt', 1)))
    // A refusal is not a failure, and nothing of the song reached the table.
    expect(surface.error).toBe('')
    expect(vm.mediaUrl).toBe('')
    expect(vm.mediaType).toBe('')
    expect(vm.currentRunId).toBeNull()
  })

  it('leaves the failure standing, and says what failed', async () => {
    generationFrames = [['error', { message: 'GPU service unreachable' }]]

    await vm.runMusic({ lyrics: LYRICS, style: '' })
    const surface = await theSurface()

    // A failure is not a refusal, and the cause is named.
    expect(surface.error).toBeTruthy()
    expect(surface.safetyState).not.toBe('blocked')
    expect(surface.text).toContain(surface.error)
    expect(vm.mediaUrl).toBe('')
  })

  it('leaves the failure standing when the connection tore, and lets the spinner go', async () => {
    generationFrames = [['error', undefined]]

    await vm.runMusic({ lyrics: LYRICS, style: '' })
    const surface = await theSurface()

    expect(surface.error).toBeTruthy()
    expect(surface.text).toContain(surface.error)
    expect(vm.mediaUrl).toBe('')
    expect(vm.isExecuting).toBe(false)
  })

  it('takes a device that holds another run as that state, not as a failure', async () => {
    // What the song said as "GPU busy" while it went over its own POST.
    answerOn('/api/schema/pipeline/generation-active', {
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ active: true, media_type: 'image' }),
    } as unknown as Response)
    generationFrames = [['error', { code: 'device_busy', media_type: 'image', message: 'Your previous generation is still running' }]]

    await vm.runMusic({ lyrics: LYRICS, style: 'slow, sparse' })
    const surface = await theSurface()

    expect(surface.error).toBe('')
    expect(vm.deviceBusy).toBe(true)
    expect(surface.text).toContain(vm.deviceBusyLine)
  })

  it('lets the next change to the board answer the refusal, and nothing before it', async () => {
    // The other half of the claim above. A judgement is about the board as it
    // stood, so a board that is another one answers it — and without this test
    // a run whose judgement simply never arrived would pass the three above.
    generationFrames = [['blocked', { stage: 3, reason: 'gesperrt', found_terms: [] }]]

    await vm.runMusic({ lyrics: LYRICS, style: '' })
    expect((await theSurface()).safetyState).toBe('blocked')

    vm.addText().text = 'ein anderes haus'
    const after = await theSurface()

    expect(after.safetyState).toBe('idle')
    expect(after.blockedReason).toBe('')
    expect(after.blockedStage).toBeNull()
  })
})
