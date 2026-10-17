import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { postDirectRun, postStreamedRun } from '../directRun'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

function sseResponse(chunks: string[]): Response {
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
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

/**
 * What a server WITHOUT the streaming branch answers on the same route: one
 * plain JSON body, and a content type that says so. This is a deploy state
 * here, not a fault — the bundle is built on a machine and the backend comes
 * from git, so the two can differ by minutes.
 */
function plainJson(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === 'content-type' ? 'application/json' : null,
    },
    json: () => Promise.resolve(body),
    body: {
      getReader: () => ({
        read: () => Promise.resolve({ done: true, value: undefined }),
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

/** The terminal frame the server writes: the answer a plain POST would have
 *  given, with its status beside it. */
function complete(body: unknown, httpStatus = 200): string {
  return 'event: complete\ndata: ' + JSON.stringify({ http_status: httpStatus, body: body }) + '\n\n'
}

describe('postStreamedRun', () => {
  it('asks for the stream and answers with the body and status of the complete frame', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([complete({ image: 'x.png' })]))
    const res = await postStreamedRun('/api/latent-lab/mean-images/variants', { prompt: 'a house' })
    expect(res).toEqual({ data: { image: 'x.png' }, status: 200 })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/latent-lab/mean-images/variants')
    // Both names of the one transport this client speaks. Most routes read
    // `enable_streaming`; /pipeline/interception reads that word as an older
    // Stage-1-and-2 protocol of its own and takes `enable_answer_streaming` for
    // this one. Saying both is this client stating which it means.
    expect(JSON.parse(String(init?.body))).toEqual({
      prompt: 'a house',
      enable_streaming: true,
      enable_answer_streaming: true,
    })
  })

  it('prefixes baseUrl and reads past everything the run says on the way', async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        ': heartbeat\n\n',
        'event: status\ndata: {"message":"queued"}\n\n',
        ': heartbeat\n\n' + complete({ done: true }),
      ])
    )
    const res = await postStreamedRun('/api/x', {}, { baseUrl: 'http://dev:17802' })
    expect(res).toEqual({ data: { done: true }, status: 200 })
    expect(String(fetchMock.mock.calls[0]![0])).toBe('http://dev:17802/api/x')
  })

  it('throws an axios-shaped error when the terminal status is a failure', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([complete({ error: 'the model refused' }, 422)]))
    // mean_images reads exactly these three off the rejection.
    const err = await postStreamedRun('/api/x', {}).catch((e) => e)
    expect(err.response.status).toBe(422)
    expect(err.response.data.error).toBe('the model refused')
    expect(err.message).toBe('Request failed with status code 422')
  })

  it('throws with the real status when the stream never opened', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: 'no GPU' }),
    } as unknown as Response)
    const err = await postStreamedRun('/api/x', {}).catch((e) => e)
    expect(err.response.status).toBe(503)
    expect(err.response.data.error).toBe('no GPU')
  })

  it('validateStatus decides what resolves, for a terminal frame and for a dead stream alike', async () => {
    const accepts = (status: number) => status < 500
    fetchMock.mockResolvedValueOnce(sseResponse([complete({ blocked: true }, 403)]))
    expect(await postStreamedRun('/api/x', {}, { validateStatus: accepts })).toEqual({
      data: { blocked: true },
      status: 403,
    })
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: 'no such run' }),
    } as unknown as Response)
    expect(await postStreamedRun('/api/x', {}, { validateStatus: accepts })).toEqual({
      data: { error: 'no such run' },
      status: 404,
    })
  })

  it('a stream that ends without its complete frame is a torn connection', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(['event: status\ndata: {"message":"working"}\n\n']))
    await expect(postStreamedRun('/api/x', {})).rejects.toThrow(
      'Network error: the run stream ended without a result'
    )
  })
})

/**
 * Stage 2, translate and the quick safety check were moved onto this transport
 * on 2026-09-04. What their call sites read out of the answer did not change,
 * so what has to hold is that the answer is the same object it was.
 */
describe('the three pipeline routes converted onto this transport', () => {
  it('hands a Stage 2 answer through unchanged, nested fields and all', async () => {
    const answer = {
      success: true,
      interception_result: 'a street, seen from below',
      stage2_result: 'a street, seen from below, for an image model',
      wikipedia_terms: [{ term: 'street', lang: 'en', found: true }],
      passthrough: false,
    }
    fetchMock.mockResolvedValueOnce(sseResponse([complete(answer)]))
    const res = await postStreamedRun('/api/schema/pipeline/stage2', { schema: 'dada' })
    expect(res.data).toEqual(answer)
    expect(JSON.parse(String(fetchMock.mock.calls[0]![1]?.body))).toEqual({
      schema: 'dada',
      enable_streaming: true,
      enable_answer_streaming: true,
    })
  })

  it('keeps the status AND the body of a refusal for a caller that accepts every status', async () => {
    // What the interception series and the voice surface read: which of the two
    // texts was refused stands in the body, and 403 stands in the status. A
    // throw would take one of the two away.
    fetchMock.mockResolvedValueOnce(
      sseResponse([complete({ success: false, blocked_on: 'context_prompt', error: 'refused' }, 403)])
    )
    const res = await postStreamedRun('/api/schema/pipeline/stage2', {}, {
      validateStatus: () => true,
    })
    expect(res.status).toBe(403)
    expect(res.data.blocked_on).toBe('context_prompt')
  })

  it('reads a plain JSON answer from a server without the streaming branch AS the answer', async () => {
    // This assertion used to run the other way, and called the throw a
    // deliberate loudness that made a half-deployed pair findable. It made
    // something else findable too: three image-check call sites catch a throw
    // here and fail OPEN, so a refusal the server had actually delivered became
    // a picture on screen. A client that asked for a stream and received an
    // ordinary answer has been answered.
    fetchMock.mockResolvedValueOnce(plainJson({ status: 'success', translated_text: 'a house' }))
    const res = await postStreamedRun('/api/schema/pipeline/translate', {})
    expect(res).toEqual({ data: { status: 'success', translated_text: 'a house' }, status: 200 })
  })

  it('keeps the status and the body of a plain JSON refusal, for a caller that accepts every status', async () => {
    // The shape the quick image check reads: the refusal stands in the body
    // under a status the caller has said it will accept. Both halves survive
    // the deploy window, exactly as they do through a terminal frame.
    fetchMock.mockResolvedValueOnce(
      plainJson({ safe: false, error_message: 'blocked for this room' }, 403)
    )
    const res = await postStreamedRun('/api/schema/pipeline/safety/quick', {}, {
      validateStatus: () => true,
    })
    expect(res.status).toBe(403)
    expect(res.data.safe).toBe(false)
  })

  it('a plain JSON answer a caller does not accept still throws, axios-shaped', async () => {
    // The status gate is the same one a terminal frame passes through: what
    // changed is where the answer came from, not which statuses resolve.
    fetchMock.mockResolvedValueOnce(plainJson({ error: 'the model refused' }, 200))
    const err = await postStreamedRun('/api/x', {}, {
      validateStatus: (status: number) => status === 201,
    }).catch((e) => e)
    expect(err.response.status).toBe(200)
    expect(err.response.data.error).toBe('the model refused')
    expect(err.message).toBe('Request failed with status code 200')
  })

  it('a stream that really did tear is still a torn stream', async () => {
    // Unchanged, and it has to stay unchanged: the fix above is keyed on a
    // STATED content type, so a real event stream that stops before its
    // terminal frame still fails, and fails loudly.
    fetchMock.mockResolvedValueOnce(sseResponse(['event: status\ndata: {"message":"working"}\n\n']))
    await expect(postStreamedRun('/api/schema/pipeline/translate', {})).rejects.toThrow(
      'Network error: the run stream ended without a result'
    )
  })

  it('keeps the status and the body when the stream never opened, for such a caller too', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ status: 'error', error: 'the translator is down' }),
    } as unknown as Response)
    const res = await postStreamedRun('/api/schema/pipeline/translate', {}, {
      validateStatus: () => true,
    })
    expect(res.status).toBe(500)
    expect(res.data.error).toBe('the translator is down')
  })
})

describe('postDirectRun', () => {
  it('is the same call with the direct run path in it', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([complete({ ok: true })]))
    expect(await postDirectRun({ prompt: 'x' })).toEqual({ data: { ok: true }, status: 200 })
    expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/schema/pipeline/direct')
  })
})

// ---------------------------------------------------------------------------
// A half-deployed pair says so
// ---------------------------------------------------------------------------

describe('a server that answers this route without the streaming branch', () => {
  it('writes one line on the console while it reads the answer anyway', async () => {
    // Reading the plain body is right — the client asked for a stream and was
    // ANSWERED, and throwing was what let three image-check call sites read a
    // delivered refusal as a network failure. But the throw was also the only
    // thing that made the mismatch findable, and a run that silently repairs a
    // deploy state hides the deploy state. One console line keeps it findable
    // for whoever is deploying and stays out of a workshop.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce(plainJson({ status: 'success' }))
    const res = await postStreamedRun('/api/schema/pipeline/stage2', {})
    expect(res).toEqual({ data: { status: 'success' }, status: 200 })
    expect(warn).toHaveBeenCalledTimes(1)
    const said = String(warn.mock.calls[0]![0])
    expect(said).toContain('/api/schema/pipeline/stage2')
    expect(said).toContain('application/json')
    warn.mockRestore()
  })

  it('says it for a refusal the caller reads out of the body, too', async () => {
    // How the image checks call this: every status resolves, and the refusal is
    // read from the body. The mismatch is just as worth knowing there.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce(plainJson({ status: 'blocked', reason: 'x' }))
    const res = await postStreamedRun('/api/schema/pipeline/stage2', {},
      { validateStatus: () => true })
    expect(res.data).toEqual({ status: 'blocked', reason: 'x' })
    expect(warn).toHaveBeenCalledTimes(1)
    warn.mockRestore()
  })

  it('says nothing about a non-2xx, which never looked like a stream', async () => {
    // The line above is about a mismatch that can be SEEN: a 200 whose content
    // type says the answer is one plain object. A non-2xx arrives as an
    // SseHttpError from either backend, old or new, so there is nothing here to
    // tell apart and nothing to say.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce(plainJson({ error: 'blocked' }, 403))
    await expect(postStreamedRun('/api/schema/pipeline/stage2', {})).rejects.toThrow()
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })

  it('reads past a frame it has no use for', async () => {
    // Everything before the terminal frame is somebody else's business: the
    // heartbeat, and whatever a route writes onto it.
    fetchMock.mockResolvedValueOnce(sseResponse([
      ': heartbeat\n\n',
      'event: stage_start\ndata: {"model":"local/qwen3"}\n\n',
      complete({ status: 'success' }),
    ]))
    const res = await postStreamedRun('/api/schema/pipeline/stage2', {})
    expect(res.data).toEqual({ status: 'success' })
  })

  it('stays silent when the answer really was a stream', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce(sseResponse([complete({ status: 'success' })]))
    await postStreamedRun('/api/schema/pipeline/stage2', {})
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })
})
