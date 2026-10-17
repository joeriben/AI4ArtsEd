/**
 * What a chat turn does with a terminal frame that is not one.
 *
 * Written on 2026-09-04, after the change that moved every surface reading a
 * reply onto `/api/chat/stream`. The blocking endpoint answered with one body
 * and there was nothing between the answer and the caller; the stream has
 * frames, and four shapes a frame can take were losing a reply that had
 * arrived, or replacing it with something no one could read:
 *
 *   - a `done` frame whose payload is `null` threw a raw TypeError naming a
 *     JavaScript property;
 *   - a `done` frame short of its fields was handed on as `{}`, which reached
 *     components/ChatOverlay.vue as `undefined` and was pushed into the
 *     conversation as the assistant's message;
 *   - two `done` frames silently took the LAST, so anything written after a
 *     complete turn overwrote it;
 *   - an `error` frame after a `done` discarded a reply that was already whole.
 *
 * And what the comparison surfaces show for a column that failed: three
 * endings that read as "no response" while they came over the blocking
 * endpoint, and have to keep reading as that.
 *
 * Nothing here reaches a server: fetch is a stand-in and the wire is written by
 * hand.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { chatTurn, ChatStreamError, ChatNoReplyError } from '../chatTurn'
import { SseHttpError } from '../sseStream'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
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

/** The nine fields `POST /api/chat` answered with, every one of them. */
const FULL = {
  type: 'done',
  reply: 'the answer',
  thinking: 'a thought',
  context_used: true,
  run_id: 'run-1',
  generated_media: [{ a: 1 }],
  generated_graphs: [],
  generated_compositions: [],
  evidence_violations: [],
  broke_off: null,
}

function wire(...events: unknown[]): string[] {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`)
}

function serves(...events: unknown[]) {
  fetchMock.mockResolvedValueOnce(sseResponse(wire(...events)))
}

// ---------------------------------------------------------------------------
// The turn that arrives whole
// ---------------------------------------------------------------------------

describe('chatTurn', () => {
  it('returns the nine fields the blocking endpoint answered with', async () => {
    serves({ type: 'token', text: 'the ' }, { type: 'token', text: 'answer' }, FULL)
    expect(await chatTurn('/api/chat/stream', {})).toEqual({
      reply: 'the answer',
      thinking: 'a thought',
      context_used: true,
      run_id: 'run-1',
      generated_media: [{ a: 1 }],
      generated_graphs: [],
      generated_compositions: [],
      evidence_violations: [],
      broke_off: null,
    })
  })

  it('drops the pieces and the rounds taken back', async () => {
    serves(
      { type: 'token', text: 'a' },
      { type: 'discard' },
      { type: 'withdraw', text: 'a' },
      FULL,
    )
    expect((await chatTurn('/api/chat/stream', {})).reply).toBe('the answer')
  })
})

// ---------------------------------------------------------------------------
// The four shapes a terminal frame can take and still not be a turn
// ---------------------------------------------------------------------------

describe('a terminal frame that is not a turn', () => {
  it('passes over a payload that is not an object at all, and says how many', async () => {
    // `data: null` parses to null and `data: 4` to a number. Reading `.type`
    // off either threw a TypeError out of this function, which named a
    // JavaScript property where a broken reply should have named itself.
    serves(null, 4, 'a string')
    const err = await chatTurn('/api/chat/stream', {}).catch((e) => e)
    expect(err).toBeInstanceOf(ChatNoReplyError)
    expect((err as ChatNoReplyError).unreadableFrames).toBe(3)
    expect((err as ChatNoReplyError).message).toContain('3 frame(s)')
  })

  it('turns away a done frame that carries no reply', async () => {
    // A frame with no `reply` is not a turn. Handed on, `{}` reached the chat
    // overlay as `undefined` and was pushed into the conversation as the
    // assistant's message: an empty bubble, and nothing saying why.
    serves({ type: 'done' })
    await expect(chatTurn('/api/chat/stream', {})).rejects.toBeInstanceOf(ChatNoReplyError)
  })

  it('fills the eight other fields when a done frame is short of them', async () => {
    // The type says they are there and callers count them, so they are there:
    // the empty value the blocking endpoint would have sent, not `undefined`.
    serves({ type: 'done', reply: 'short' })
    expect(await chatTurn('/api/chat/stream', {})).toEqual({
      reply: 'short',
      thinking: null,
      context_used: false,
      run_id: null,
      generated_media: [],
      generated_graphs: [],
      generated_compositions: [],
      evidence_violations: [],
      broke_off: null,
    })
  })

  it('ends the turn when the reply stream was cut', async () => {
    // The server ships a turn whose closing sentence was reset, so that the
    // apparatus it built and the half sentence it wrote are not lost with it.
    // The workshop board reads along and says under the half sentence that it
    // stopped; every caller HERE shows a finished reply in one piece and has
    // nowhere to say that. Presented as the whole answer, half of one is read
    // as the whole answer, spoken aloud, and written into the next turn's
    // history — which is what these surfaces did NOT do before the server
    // learned to hand a broken turn over, and must go on not doing.
    serves({ ...FULL, reply: 'Ich habe zwei Wege nebeneinand',
             broke_off: "ConnectionResetError(104, 'Connection reset by peer')" })
    await expect(chatTurn('/api/chat/stream', {}))
      .rejects.toThrow("Connection reset by peer")
  })

  it('reads an empty broke_off as a turn that was finished', async () => {
    // The server writes the reason or None. An empty string is neither, and a
    // turn is not ended over one.
    serves({ ...FULL, broke_off: '' })
    expect((await chatTurn('/api/chat/stream', {})).broke_off).toBe(null)
  })

  it('keeps the FIRST done frame when two arrive', async () => {
    // `done` closes the turn. Taking the last let a second turn — or a
    // fragment of one — overwrite an answer that was already complete.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    serves(FULL, { ...FULL, reply: 'a later, emptier turn' })
    expect((await chatTurn('/api/chat/stream', {})).reply).toBe('the answer')
    expect(warn).toHaveBeenCalled()
  })

  it('keeps the reply when an error frame follows a done frame', async () => {
    // An error after the turn closed cannot un-write it. The journal write that
    // failed is not the answer, and discarding the answer over it left the room
    // with nothing.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    serves(FULL, { type: 'error', error: 'journal write failed' })
    expect((await chatTurn('/api/chat/stream', {})).reply).toBe('the answer')
    expect(warn).toHaveBeenCalled()
  })

  it('still ends the turn on an error frame that comes BEFORE any done', async () => {
    // Which is what a non-2xx from the blocking endpoint did, and the reason
    // ChatStreamError is its own type.
    serves({ type: 'token', text: 'a' },
           { type: 'error', error: 'Internal server error', details: 'the model refused', status: 403 })
    const err = await chatTurn('/api/chat/stream', {}).catch((e) => e)
    expect(err).toBeInstanceOf(ChatStreamError)
    expect((err as ChatStreamError).message).toBe('the model refused')
    expect((err as ChatStreamError).status).toBe(403)
  })
})

// ---------------------------------------------------------------------------
// What a failed column is told, which decides the wording it shows
// ---------------------------------------------------------------------------

describe('the three endings a comparison column reads as "no response"', () => {
  it('a stream that never opened is an SseHttpError carrying the status', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: 'the model is down' }),
    } as unknown as Response)
    const err = await chatTurn('/api/chat/stream', {}).catch((e) => e)
    expect(err).toBeInstanceOf(SseHttpError)
    expect((err as SseHttpError).status).toBe(503)
  })

  it('a turn the server ended itself is a ChatStreamError', async () => {
    serves({ type: 'error', error: 'Internal server error', status: 500 })
    await expect(chatTurn('/api/chat/stream', {})).rejects.toBeInstanceOf(ChatStreamError)
  })

  it('a stream that stopped with no terminal event is a ChatNoReplyError', async () => {
    // Its own type and not a plain Error, because the surfaces classify on it:
    // this is what a non-2xx body with no `reply` in it used to be, and the
    // column showed "no response received" for that.
    serves({ type: 'token', text: 'half a sentence' })
    const err = await chatTurn('/api/chat/stream', {}).catch((e) => e)
    expect(err).toBeInstanceOf(ChatNoReplyError)
    expect(err).not.toBeInstanceOf(ChatStreamError)
    expect((err as ChatNoReplyError).unreadableFrames).toBe(0)
  })

  it('a connection that tore is none of the three and still reaches the error branch', async () => {
    // The one this must not swallow: a column showing "no response" for a
    // network failure would say the model answered nothing when nothing asked
    // it.
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const err = await chatTurn('/api/chat/stream', {}).catch((e) => e)
    expect(err).toBeInstanceOf(TypeError)
    expect(err).not.toBeInstanceOf(ChatNoReplyError)
    expect(err).not.toBeInstanceOf(SseHttpError)
  })
})
