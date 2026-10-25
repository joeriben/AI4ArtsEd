import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  readSseFrames,
  sseEvents,
  sseFrames,
  SseHttpError,
  SseNotStreamedError,
  type SseFrame,
} from '../sseStream'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

/** A response whose body hands out the given chunks and then ends. `cancels`
 *  counts the reader cancellations, which is how leaving a stream early is
 *  observed from outside. */
function sseResponse(chunks: string[], cancels?: { n: number }): Response {
  const encoder = new TextEncoder()
  let i = 0
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(null),
    body: {
      getReader: () => ({
        read: () =>
          i < chunks.length
            ? Promise.resolve({ done: false, value: encoder.encode(chunks[i++]) })
            : Promise.resolve({ done: true, value: undefined }),
        cancel: () => {
          if (cancels) cancels.n++
          return Promise.resolve()
        },
      }),
    },
  } as unknown as Response
}

function stream(chunks: string[], cancels?: { n: number }): ReadableStream<Uint8Array> {
  return sseResponse(chunks, cancels).body as ReadableStream<Uint8Array>
}

async function collect<T>(frames: AsyncGenerator<T, void, void>): Promise<T[]> {
  const out: T[] = []
  for await (const frame of frames) out.push(frame)
  return out
}

// ---------------------------------------------------------------------------
// readSseFrames
// ---------------------------------------------------------------------------

describe('readSseFrames', () => {
  it('delivers the name a route wrote in its event: line', async () => {
    const frames = await collect(readSseFrames(stream(['event: complete\ndata: {"ok":true}\n\n'])))
    expect(frames).toEqual([{ event: 'complete', data: { ok: true }, id: undefined }])
  })

  it('delivers a frame that carries no event: line at all', async () => {
    // The chat stream writes the name INSIDE the JSON and no event: line, so a
    // frame without one is not malformed and must still arrive.
    const frames = await collect(readSseFrames(stream(['data: {"type":"token","text":"hi"}\n\n'])))
    expect(frames).toEqual([{ event: undefined, data: { type: 'token', text: 'hi' }, id: undefined }])
  })

  it('carries a numeric id: and drops a non-numeric one, keeping the frame', async () => {
    const frames = await collect(
      readSseFrames(stream(['id: 7\nevent: status\ndata: {}\n\nid: seven\nevent: status\ndata: {}\n\n']))
    )
    expect(frames.map((f) => f.id)).toEqual([7, undefined])
    expect(frames).toHaveLength(2)
  })

  it('skips a malformed frame without ending the stream', async () => {
    const frames = await collect(
      readSseFrames(stream(['event: bad\ndata: {broken\n\nevent: good\ndata: {"ok":true}\n\n']))
    )
    expect(frames).toEqual([{ event: 'good', data: { ok: true }, id: undefined }])
  })

  it('passes over the heartbeat comment and the [DONE] sentinel', async () => {
    const frames = await collect(
      readSseFrames(stream([': heartbeat\n\ndata: [DONE]\n\nevent: complete\ndata: {}\n\n']))
    )
    expect(frames.map((f) => f.event)).toEqual(['complete'])
  })

  it('re-assembles a frame split across chunks', async () => {
    const frames = await collect(readSseFrames(stream(['id: 0\nevent: status\ndata: {"a":', '1}\n\n'])))
    expect(frames).toEqual([{ event: 'status', data: { a: 1 }, id: 0 }])
  })

  it('delivers several frames of one chunk in order', async () => {
    const frames = await collect(
      readSseFrames(stream(['event: a\ndata: 1\n\nevent: b\ndata: 2\n\nevent: c\ndata: 3\n\n']))
    )
    expect(frames.map((f) => f.event)).toEqual(['a', 'b', 'c'])
    expect(frames.map((f) => f.data)).toEqual([1, 2, 3])
  })

  it('still delivers a last frame that arrived without its blank line', async () => {
    const frames = await collect(readSseFrames(stream(['event: complete\ndata: {"ok":true}'])))
    expect(frames).toEqual([{ event: 'complete', data: { ok: true }, id: undefined }])
  })

  it('cancels the reader when the caller leaves the stream early', async () => {
    const cancels = { n: 0 }
    const seen: SseFrame[] = []
    for await (const frame of readSseFrames(
      stream(['event: a\ndata: 1\n\nevent: b\ndata: 2\n\n'], cancels)
    )) {
      seen.push(frame)
      break
    }
    expect(seen.map((f) => f.event)).toEqual(['a'])
    expect(cancels.n).toBe(1)
  })
})

// ---------------------------------------------------------------------------
// sseFrames
// ---------------------------------------------------------------------------

describe('sseFrames', () => {
  it('POSTs the body as JSON, with the caller headers and signal', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(['event: complete\ndata: {}\n\n']))
    const controller = new AbortController()
    await collect(
      sseFrames('/api/thing', { a: 1 }, { headers: { 'X-Test': 'y' }, signal: controller.signal })
    )
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/thing')
    expect(init?.method).toBe('POST')
    expect(init?.headers).toEqual({ 'Content-Type': 'application/json', 'X-Test': 'y' })
    expect(JSON.parse(String(init?.body))).toEqual({ a: 1 })
    expect(init?.signal).toBe(controller.signal)
  })

  it('throws SseHttpError with the status and the body when the stream never opened', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 429,
      json: () => Promise.resolve({ error: 'too many' }),
    } as unknown as Response)
    const err = await collect(sseFrames('/api/thing', {})).catch((e) => e)
    expect(err).toBeInstanceOf(SseHttpError)
    expect((err as SseHttpError).status).toBe(429)
    expect((err as SseHttpError).body).toEqual({ error: 'too many' })
  })

  it('throws SseNotStreamedError when the content type says the answer is not a stream', async () => {
    // A Flask route answering with jsonify sends application/json and one
    // object where the frames would be. Reading that as frames yields none, and
    // the caller then reports a torn connection for an answer that arrived
    // whole. The body travels on the error, because it IS the answer.
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === 'content-type' ? 'application/json' : null,
      },
      json: () => Promise.resolve({ status: 'success' }),
      body: {
        getReader: () => ({
          read: () => Promise.resolve({ done: true, value: undefined }),
          cancel: () => Promise.resolve(),
        }),
      },
    } as unknown as Response)
    const err = await collect(sseFrames('/api/thing', {})).catch((e) => e)
    expect(err).toBeInstanceOf(SseNotStreamedError)
    expect((err as SseNotStreamedError).status).toBe(200)
    expect((err as SseNotStreamedError).body).toEqual({ status: 'success' })
    expect((err as SseNotStreamedError).contentType).toBe('application/json')
  })

  it('reads an answer that names NO content type as frames, exactly as before', async () => {
    // The narrowness of the rule above, and the reason it is worded as "names
    // something else" rather than "does not name an event stream": only a
    // STATED content type decides, so a stream from a route that wrote no
    // header keeps being read as the stream it is.
    fetchMock.mockResolvedValueOnce(sseResponse(['event: complete\ndata: {"ok":true}\n\n']))
    expect(await collect(sseFrames('/api/thing', {}))).toEqual([
      { event: 'complete', data: { ok: true }, id: undefined },
    ])
  })

  it('throws SseHttpError when a 200 arrives with no body to read', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: null,
      json: () => Promise.resolve(null),
    } as unknown as Response)
    const err = await collect(sseFrames('/api/thing', {})).catch((e) => e)
    expect(err).toBeInstanceOf(SseHttpError)
    expect((err as SseHttpError).status).toBe(200)
  })
})

// ---------------------------------------------------------------------------
// sseEvents
// ---------------------------------------------------------------------------

describe('sseEvents', () => {
  it('hands on the payload alone, frame for frame', async () => {
    // What the chat surfaces read. The name is inside the JSON here, and the
    // envelope around it would only stand in their way.
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'data: {"type":"token","text":"a"}\n\n',
        ': heartbeat\n\ndata: {"type":"done","reply":"ab"}\n\n',
      ])
    )
    expect(await collect(sseEvents('/api/chat/stream', {}))).toEqual([
      { type: 'token', text: 'a' },
      { type: 'done', reply: 'ab' },
    ])
  })
})

// ---------------------------------------------------------------------------
// The wire a surface reads once its own reader is gone
// ---------------------------------------------------------------------------

describe('readSseFrames — the VLM reading stream', () => {
  it('delivers a reading whole when a chunk is cut inside a payload', async () => {
    // views/compare/vlm_analysis_comparison.vue fills one card token by token
    // from bare `data:` frames that name their event inside the JSON. It read
    // those frames itself until this reader took the framing over, so what it
    // now rests on is held here: every token arrives, in order, however the
    // chunks fall.
    const wire =
      'data: {"type":"token","text":"a b"}\n\n' +
      'data: {"type":"token","text":" c"}\n\n' +
      'data: {"type":"done","latency_s":2.5,"char_count":4}\n\n'
    const cut = wire.indexOf('" c"') + 2
    const frames = await collect(
      readSseFrames<Record<string, unknown>>(stream([wire.slice(0, cut), wire.slice(cut)])),
    )
    expect(frames.map(f => f.data)).toEqual([
      { type: 'token', text: 'a b' },
      { type: 'token', text: ' c' },
      { type: 'done', latency_s: 2.5, char_count: 4 },
    ])
  })
})

// ---------------------------------------------------------------------------
// A frame whose payload stands on more than one data: line
// ---------------------------------------------------------------------------

describe('readSseFrames — the payload of one frame', () => {
  it('joins every data: line of a frame, as the specification says', async () => {
    // Reading only the first line threw the rest of the value away and left
    // what remained unparseable, so the whole frame was dropped in silence.
    const frames = await collect(
      readSseFrames(stream(['event: complete\ndata: {"a":1,\ndata: "b":2}\n\n'])),
    )
    expect(frames).toEqual([{ event: 'complete', data: { a: 1, b: 2 }, id: undefined }])
  })

  it('keeps the newline between the lines, which is what joins them', async () => {
    const frames = await collect(
      readSseFrames<string>(stream(['data: "first\\nsecond"\n\n'])),
    )
    expect(frames[0]!.data).toBe('first\nsecond')
  })

  it('still drops a one-line heartbeat and a one-line [DONE]', async () => {
    // The narrowness of the change: nothing that passed before may now arrive.
    const frames = await collect(
      readSseFrames(stream([': heartbeat\n\ndata: [DONE]\n\ndata: {"ok":true}\n\n'])),
    )
    expect(frames.map((f) => f.data)).toEqual([{ ok: true }])
  })

  it('is what every route on this platform writes today: one line', async () => {
    // Checked so the change is understood for what it is — spec compliance,
    // not a fix for a frame anyone here sends. Every route writes one
    // json.dumps on one line, and the two SSE passthroughs re-frame the
    // upstream line by line, which would split a multi-line frame apart before
    // it ever arrived.
    const frames = await collect(
      readSseFrames(stream(['data: {"type":"token","text":"a\\nb"}\n\n'])),
    )
    expect(frames[0]!.data).toEqual({ type: 'token', text: 'a\nb' })
  })
})

// ---------------------------------------------------------------------------
// Being told about a frame that was skipped
// ---------------------------------------------------------------------------

describe('onSkipped', () => {
  it('says nothing at all when the caller passes nothing', async () => {
    // The silence five surfaces depend on: a page must not write console lines
    // about a stream another page is reading.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    await collect(readSseFrames(stream(['data: {broken\n\ndata: {"ok":true}\n\n'])))
    expect(warn).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
    warn.mockRestore()
    error.mockRestore()
  })

  it('hands the caller the payload it could not read, and the reason', async () => {
    const skipped: Array<[string, unknown]> = []
    const frames = await collect(
      readSseFrames(stream(['data: {broken\n\ndata: {"ok":true}\n\n']), {
        onSkipped: (payload, error) => skipped.push([payload, error]),
      }),
    )
    expect(frames.map((f) => f.data)).toEqual([{ ok: true }])
    expect(skipped).toHaveLength(1)
    expect(skipped[0]![0]).toBe('{broken')
    expect(skipped[0]![1]).toBeInstanceOf(Error)
  })

  it('is not called for a heartbeat, which is not a skipped frame', async () => {
    // A frame that carries no payload is no frame, and never was one. Reporting
    // it would put a line on the console every two seconds of every run.
    const skipped: string[] = []
    await collect(
      readSseFrames(stream([': heartbeat\n\n: heartbeat\n\ndata: {"ok":true}\n\n']), {
        onSkipped: (payload) => skipped.push(payload),
      }),
    )
    expect(skipped).toEqual([])
  })

  it('reaches through sseFrames and sseEvents from the caller options', async () => {
    const skipped: string[] = []
    fetchMock.mockResolvedValueOnce(
      sseResponse(['data: not json\n\ndata: {"type":"done"}\n\n']),
    )
    const seen = await collect(
      sseEvents('/api/thing', {}, { onSkipped: (payload) => skipped.push(payload) }),
    )
    expect(seen).toEqual([{ type: 'done' }])
    expect(skipped).toEqual(['not json'])
  })
})
