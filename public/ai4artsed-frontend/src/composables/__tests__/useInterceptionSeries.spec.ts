/**
 * The adaption a series asks for once per cell, now that it travels on the
 * platform's streamed transport.
 *
 * Phase 2 of every series runs the output config's own adaption
 * (POST /api/schema/pipeline/optimize) before the picture is made — a cloud
 * model, once per cell, for the whole raster. It was awaited in one silent
 * POST, and the edge in front of this server ends a proxied request whose
 * origin has sent nothing for about 100 seconds: the adaption finished on the
 * server, and nothing here writes it down, so there was nothing to fetch again.
 *
 * Only the transport changed, and the three branches this call has always had
 * are what say so: an adaption that came back, one the route refused with a
 * cause of its own, and a connection that tore. The refusal is the one that
 * cost something to keep — it is read out of the BODY, and the status has to
 * survive the trip for the cell to say a full queue rather than "nothing came
 * back".
 *
 * Nothing here reaches a model: `fetch` is a stand-in and the generation is one
 * too.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import i18n from '@/i18n'
import { failureKey } from '@/composables/useGenerationStream'
import {
  useInterceptionSeries,
  SERIES_SEED,
  type InterceptionSeries,
  type SeriesRow,
} from '../useInterceptionSeries'

const generation = vi.fn()

// The picture itself is not what this file is about. The generation is replaced
// so that a cell ends where the adaption ends, and `failureKey` — which the
// cell's own wording is read through — stays the platform's own.
vi.mock('@/composables/useGenerationStream', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    useGenerationStream: () => ({ reset: () => {}, executeWithStreaming: generation }),
  }
})

const STAGE2 = '/api/schema/pipeline/stage2'
const OPTIMIZE = '/api/schema/pipeline/optimize'

const LINE = 'ein haus am feldrand'
const WRITTEN = 'a house at the edge of a field, seen from the road'
const ADAPTED = 'a house at the edge of a field, late light'

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

const REFERENCE: SeriesRow = {
  key: 'as-written',
  reference: true,
  label: 'as written',
  request: null,
  text: LINE,
  segments: [],
  failedKey: '',
}

/** A row that carries a request, so the LINE passes the platform's gate and the
 *  series has something it may compute at all. */
const WITH_A_PERSPECTIVE: SeriesRow = {
  key: 'dada',
  reference: false,
  label: 'dada',
  request: { schema: 'dada' },
  text: '',
  segments: [],
  failedKey: '',
}

const COLUMN = { id: 'sd35_large', label: 'SD 3.5 Large' }

let series: InterceptionSeries
let host: ReturnType<typeof mount>

function aSeries() {
  const Host = defineComponent({
    setup(_props, { expose }) {
      const s = useInterceptionSeries({
        line: () => LINE,
        rows: () => [REFERENCE, WITH_A_PERSPECTIVE],
        columns: () => [COLUMN],
        sourceView: 'test',
      })
      expose({ s })
      return () => null
    },
  })
  host = mount(Host, { global: { plugins: [i18n] } })
  series = (host.vm as any).s
  return series
}

/** The cell of the reference row in the one column — the cell whose adaption
 *  every test here is about. */
const CELL = `${COLUMN.id}|${SERIES_SEED}|${REFERENCE.key}`

beforeEach(() => {
  queued.clear()
  ;(fetchMock as any).mockClear()
  generation.mockReset()
  generation.mockResolvedValue({ status: 'success', media_output: { url: '/api/x.png' } })
  vi.stubGlobal('fetch', fetchMock)
  // The line has to pass the gate before anything may be computed.
  answerOn(STAGE2, streamed({ success: true, interception_result: WRITTEN }))
  aSeries()
})

afterEach(() => {
  series?.release()
  host?.unmount()
  vi.unstubAllGlobals()
})

describe('the adaption a series asks for once per cell', () => {
  it('asks for it on the stream, and makes the picture from what came back', async () => {
    answerOn(OPTIMIZE, streamed({ success: true, optimized_prompt: ADAPTED }))

    await series.startRun()

    expect(sentTo(OPTIMIZE).body).toEqual({
      input_text: LINE,
      output_config: COLUMN.id,
      // Both names of the one transport this client speaks.
      enable_streaming: true,
      enable_answer_streaming: true,
    })
    expect(series.adapted.value[CELL]).toBe(ADAPTED)
    // What the image model reads is the adaption, not the row's text.
    expect(generation.mock.calls[0]![0]).toMatchObject({
      prompt: ADAPTED,
      output_config: COLUMN.id,
      seed: SERIES_SEED,
    })
  })

  it('reads a refusal out of the body and says what refused, not "nothing came back"', async () => {
    // The status travels with the answer, and the cause is read off the body:
    // a cell that flattened this into its own sentence would tell a room that a
    // model said nothing when in fact the queue was full.
    answerOn(OPTIMIZE, streamed({ success: false, error: 'model not found' }, 500))

    await series.startRun()

    const cell = series.gridColumns.value[0]!.cells.find((c) => c.key === CELL)!
    expect(cell.failed).toBe(true)
    expect(series.cellNote(cell)).toBe(i18n.global.t(failureKey('error', 'model not found')))
    expect(series.cellNote(cell)).not.toBe(
      i18n.global.t('latentLab.interception.models.cellFailed')
    )
    // An adaption that brought nothing back ends the cell: sending the
    // unadapted text on would make this one cell the only one prepared
    // differently.
    expect(generation).not.toHaveBeenCalled()
    expect(series.adapted.value[CELL]).toBeUndefined()
  })

  it('says a torn connection is a torn connection', async () => {
    answerOn(OPTIMIZE, new TypeError('Failed to fetch'))

    await series.startRun()

    const cell = series.gridColumns.value[0]!.cells.find((c) => c.key === CELL)!
    expect(cell.failed).toBe(true)
    expect(series.cellNote(cell)).toBe(i18n.global.t(failureKey('error', 'Failed to fetch')))
    expect(generation).not.toHaveBeenCalled()
  })

  it('ends the cell when the adaption came back empty', async () => {
    answerOn(OPTIMIZE, streamed({ success: true, optimized_prompt: '   ' }))

    await series.startRun()

    const cell = series.gridColumns.value[0]!.cells.find((c) => c.key === CELL)!
    expect(cell.failed).toBe(true)
    expect(series.cellNote(cell)).toBe(
      i18n.global.t('latentLab.interception.models.cellFailed')
    )
    expect(generation).not.toHaveBeenCalled()
  })
})

/**
 * A run a surface keeps in sight after the question has moved on: it carries a
 * text, and that text was written under an EARLIER line. It may take no part in
 * a press — and above all it is no proof that the line standing in the field
 * now has passed the platform's Stage 1 gate, which is what phase 2 rests on.
 */
describe('a run kept in sight', () => {
  const KEPT_TEXT = 'what an earlier line was written into'

  function keptOrNot(inert: boolean): SeriesRow {
    return {
      key: 'kept',
      reference: false,
      inert,
      label: 'kept',
      request: { schema: 'dada' },
      text: KEPT_TEXT,
      segments: [],
      failedKey: '',
    }
  }

  function aSeriesWith(row: SeriesRow) {
    series.release()
    host.unmount()
    const Host = defineComponent({
      setup(_props, { expose }) {
        const s = useInterceptionSeries({
          line: () => LINE,
          rows: () => [REFERENCE, row],
          columns: () => [COLUMN],
          sourceView: 'test',
        })
        expose({ s })
        return () => null
      },
    })
    host = mount(Host, { global: { plugins: [i18n] } })
    series = (host.vm as any).s
    return series
  }

  function sentTimesTo(route: string): number {
    return (fetchMock as any).mock.calls.filter((c: any[]) => String(c[0]).includes(route)).length
  }

  it('is not written again, is not drawn, and proves nothing about the line', async () => {
    aSeriesWith(keptOrNot(true))

    await series.startRun()

    // Phase 1 asked nothing: the one row that carries a request is kept.
    expect(sentTimesTo(STAGE2)).toBe(0)
    // And with nothing written, phase 2 may not run at all — the kept text is
    // not proof that the line now in the field passed the gate. The reference
    // row carries that line, so this is the row that must stay empty.
    expect(sentTimesTo(OPTIMIZE)).toBe(0)
    expect(generation).not.toHaveBeenCalled()
    expect(series.gridColumns.value[0]!.cells[0]!.url).toBe('')
  })

  it('is the keeping that holds it back, and nothing else', async () => {
    aSeriesWith(keptOrNot(false))

    await series.startRun()

    // The same row, not kept: written in phase 1, and phase 2 goes on to ask
    // for the adaption. Every assertion above rests on the one flag.
    expect(sentTimesTo(STAGE2)).toBe(1)
    expect(sentTimesTo(OPTIMIZE)).toBeGreaterThan(0)
  })
})

describe('a refusal of one row', () => {
  function sentTimesTo(route: string): number {
    return (fetchMock as any).mock.calls.filter((c: any[]) => String(c[0]).includes(route)).length
  }

  it('at the gate, of the line, holds the whole series back', async () => {
    queued.clear()
    answerOn(STAGE2, streamed({
      success: false, status: 'blocked', error: 'Kids-Filter: nicht erlaubt',
      blocked_at_stage: 1, checks_passed: ['fast_filter'],
    }, 403))

    await series.startRun()

    expect(sentTimesTo(STAGE2)).toBe(1)
    expect(series.errorMessage.value).not.toBe('')
    expect(sentTimesTo(OPTIMIZE)).toBe(0)
  })

  it('by the model at stage 2 belongs to its row and holds nothing else back', async () => {
    // The backend answers a model-written refusal as a block at stage 2 since
    // 2026-10-10: the MODEL refused under THIS row's perspective, which says
    // nothing about the line another row starts from. Two rows carry a
    // request; the first is refused, the second is written, and the series
    // goes on to the pictures of what was written.
    series.release()
    host.unmount()
    const ANOTHER: SeriesRow = { ...WITH_A_PERSPECTIVE, key: 'bauhaus', label: 'bauhaus', request: { schema: 'bauhaus' } }
    const Host = defineComponent({
      setup(_props, { expose }) {
        const s = useInterceptionSeries({
          line: () => LINE,
          rows: () => [REFERENCE, WITH_A_PERSPECTIVE, ANOTHER],
          columns: () => [COLUMN],
          sourceView: 'test',
        })
        expose({ s })
        return () => null
      },
    })
    host = mount(Host, { global: { plugins: [i18n] } })
    series = (host.vm as any).s
    queued.clear()
    answerOn(STAGE2, streamed({
      success: false, status: 'blocked', error: 'the model refused under the prefix',
      reason: 'the model refused under the prefix', blocked_at_stage: 2, checks_passed: [],
    }, 403))
    answerOn(STAGE2, streamed({ success: true, interception_result: WRITTEN }))

    await series.startRun()

    expect(sentTimesTo(STAGE2)).toBe(2)
    expect(series.errorMessage.value).toBe('')
    expect(sentTimesTo(OPTIMIZE)).toBeGreaterThan(0)
  })
})
