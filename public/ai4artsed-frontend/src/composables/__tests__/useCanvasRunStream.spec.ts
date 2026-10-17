import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  startCanvasRun,
  fetchCanvasPartial,
  fetchCanvasRunStatus,
  type CanvasRunStartPayload,
  type CanvasSSEEvent,
} from '../useCanvasRunStream'

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

function frame(type: string, data: unknown, id?: number): string {
  const idLine = id === undefined ? '' : 'id: ' + id + '\n'
  return idLine + 'event: ' + type + '\ndata: ' + JSON.stringify(data) + '\n\n'
}

/** Response whose body streams the given chunks, then EOF. */
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  let i = 0
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    body: {
      getReader: () => ({
        read: () =>
          i < chunks.length
            ? Promise.resolve({ done: false, value: encoder.encode(chunks[i++]) })
            : Promise.resolve({ done: true, value: undefined }),
        // A real ReadableStreamDefaultReader has this, and the shared reader
        // calls it on the way out. The fake did without it while the framing
        // was a function over a string and no reader was ever held.
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, statusText: 'status ' + status, json: () => Promise.resolve(body) } as Response
}

const PAYLOAD: CanvasRunStartPayload = {
  nodes: [{ id: 'n1' }],
  connections: [{ from: 'n1', to: 'n2' }],
  device_id: 'dev-1',
}

// ---------------------------------------------------------------------------
// startCanvasRun
// ---------------------------------------------------------------------------

describe('startCanvasRun', () => {
  it('POSTs nodes/connections/device_id — workflow only when provided', async () => {
    fetchMock.mockResolvedValue(sseResponse([frame('complete', {}, 0)]))
    await startCanvasRun(PAYLOAD, { onEvent: () => {} }).done
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/canvas/execute-stream')
    expect(fetchMock.mock.calls[0]![1]?.method).toBe('POST')
    let body = JSON.parse(String(fetchMock.mock.calls[0]![1]?.body))
    // exact equality: no workflow key when the payload has none
    expect(body).toEqual({
      nodes: [{ id: 'n1' }],
      connections: [{ from: 'n1', to: 'n2' }],
      device_id: 'dev-1',
    })

    await startCanvasRun(
      { ...PAYLOAD, workflow: { id: 'wf1', name: 'My Flow' } },
      { onEvent: () => {} }
    ).done
    body = JSON.parse(String(fetchMock.mock.calls[1]![1]?.body))
    expect(body.workflow).toEqual({ id: 'wf1', name: 'My Flow' })
  })

  it('dispatches events in order, tracks runId and the id cursor, completes cleanly', async () => {
    const events: CanvasSSEEvent[] = []
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        frame('run_started', { run_id: 'r9' }, 0),
        frame('status', { message: 'stage 1' }, 1) + frame('node_result', { node: 'a' }, 2),
        frame('complete', { ok: true }, 3),
      ])
    )
    const handle = startCanvasRun(PAYLOAD, { onEvent: (e) => events.push(e) })
    expect(handle.runId).toBeNull() // before run_started arrives
    expect(await handle.done).toEqual({ kind: 'complete' })
    expect(events.map((e) => e.type)).toEqual(['run_started', 'status', 'node_result', 'complete'])
    expect(handle.runId).toBe('r9')
    expect(handle.lastEventIndex).toBe(3)
  })

  it('re-assembles a frame split across two chunks', async () => {
    const events: CanvasSSEEvent[] = []
    fetchMock.mockResolvedValueOnce(
      sseResponse(['id: 0\nevent: status\ndata: {"a":', '1}\n\n' + frame('complete', {}, 1)])
    )
    expect(await startCanvasRun(PAYLOAD, { onEvent: (e) => events.push(e) }).done).toEqual({
      kind: 'complete',
    })
    expect(events[0]).toEqual({ type: 'status', data: { a: 1 }, id: 0 })
  })

  it('stops consuming at the terminal event — nothing after it is delivered', async () => {
    const events: CanvasSSEEvent[] = []
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        frame('run_started', { run_id: 'r1' }, 0) +
          frame('complete', {}, 1) +
          frame('status', { late: true }, 2),
      ])
    )
    const handle = startCanvasRun(PAYLOAD, { onEvent: (e) => events.push(e) })
    expect(await handle.done).toEqual({ kind: 'complete' })
    expect(events.map((e) => e.type)).toEqual(['run_started', 'complete'])
    expect(handle.lastEventIndex).toBe(1) // the late frame never advanced the cursor
  })

  it('classifies a terminal error event as server_error (and still delivers it)', async () => {
    const events: CanvasSSEEvent[] = []
    fetchMock.mockResolvedValueOnce(
      sseResponse([frame('run_started', { run_id: 'r1' }, 0) + frame('error', { message: 'boom' }, 1)])
    )
    expect(await startCanvasRun(PAYLOAD, { onEvent: (e) => events.push(e) }).done).toEqual({
      kind: 'server_error',
    })
    expect(events[events.length - 1]!.type).toBe('error')
  })

  it('clean EOF without a terminal event is torn, with no thrown error attached', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([frame('run_started', { run_id: 'r1' }, 0)]))
    const outcome = await startCanvasRun(PAYLOAD, { onEvent: () => {} }).done
    expect(outcome).toEqual({ kind: 'torn' })
    expect((outcome as { error?: Error }).error).toBeUndefined()
  })

  it('a thrown network tear is torn with the error attached (tear predicate)', async () => {
    const tear = new TypeError('Failed to fetch')
    fetchMock.mockRejectedValueOnce(tear)
    const outcome = await startCanvasRun(PAYLOAD, { onEvent: () => {} }).done
    expect(outcome.kind).toBe('torn')
    expect((outcome as { error?: Error }).error).toBe(tear)
  })

  it('HTTP !ok is a transport error carrying the raw thrown value', async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500, statusText: 'Server Error' } as unknown as Response)
    const outcome = await startCanvasRun(PAYLOAD, { onEvent: () => {} }).done
    expect(outcome.kind).toBe('transport_error')
    const error = (outcome as { error: unknown }).error
    expect(error).toBeInstanceOf(Error)
    expect((error as Error).message).toBe('HTTP 500: Server Error')
  })

  it('a missing response body is a transport error, not a tear', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, statusText: 'OK', body: null } as unknown as Response)
    const outcome = await startCanvasRun(PAYLOAD, { onEvent: () => {} }).done
    expect(outcome.kind).toBe('transport_error')
    expect(((outcome as { error: unknown }).error as Error).message).toBe('No response body for streaming')
  })

  it('an AbortError resolves aborted', async () => {
    fetchMock.mockRejectedValueOnce(
      Object.assign(new Error('The user aborted a request.'), { name: 'AbortError' })
    )
    expect(await startCanvasRun(PAYLOAD, { onEvent: () => {} }).done).toEqual({ kind: 'aborted' })
  })

  it('reconnects a torn stream from the id cursor and collects the completion', async () => {
    const events: CanvasSSEEvent[] = []
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url === '/api/canvas/execute-stream') {
        // the live stream tears (EOF) after two events
        return Promise.resolve(
          sseResponse([frame('run_started', { run_id: 'r7' }, 0) + frame('status', { message: 'working' }, 1)])
        )
      }
      if (url === '/api/canvas/runs/r7/status') {
        return Promise.resolve(jsonResponse({ state: 'running' }))
      }
      if (url === '/api/canvas/execute-stream/r7?after=1') {
        return Promise.resolve(sseResponse([frame('node_result', { node: 'a' }, 2) + frame('complete', {}, 3)]))
      }
      return Promise.reject(new Error('unexpected fetch: ' + url))
    })
    const handle = startCanvasRun(PAYLOAD, {
      reconnect: true,
      reconnectBackoffsMs: [1, 1],
      onEvent: (e) => events.push(e),
    })
    expect(await handle.done).toEqual({ kind: 'complete' })
    expect(events.map((e) => e.type)).toEqual(['run_started', 'status', 'node_result', 'complete'])
    expect(handle.lastEventIndex).toBe(3)
  })

  it('does not reconnect past a server-side hard stop (interrupted)', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url === '/api/canvas/execute-stream') {
        return Promise.resolve(sseResponse([frame('run_started', { run_id: 'r8' }, 0)]))
      }
      if (url === '/api/canvas/runs/r8/status') {
        return Promise.resolve(jsonResponse({ state: 'interrupted' }))
      }
      return Promise.reject(new Error('unexpected fetch: ' + url))
    })
    const outcome = await startCanvasRun(PAYLOAD, {
      reconnect: true,
      reconnectBackoffsMs: [1],
      onEvent: () => {},
    }).done
    expect(outcome).toEqual({ kind: 'torn' })
    // no reconnect GET was attempted
    const urls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(urls).toEqual(['/api/canvas/execute-stream', '/api/canvas/runs/r8/status'])
  })
})

// ---------------------------------------------------------------------------
// fetchCanvasRunStatus / fetchCanvasPartial
// ---------------------------------------------------------------------------

describe('fetchCanvasRunStatus', () => {
  it('returns body.state from the prefixed endpoint', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ state: 'complete' }))
    expect(await fetchCanvasRunStatus('r1', 'http://dev:17802')).toBe('complete')
    // With the session: the canvas routes resolve the safety level from it, and
    // cross-origin (the dev split, 5173 -> 17802) fetch drops the cookie unless
    // it is asked for.
    expect(fetchMock).toHaveBeenCalledWith(
      'http://dev:17802/api/canvas/runs/r1/status',
      { credentials: 'include' },
    )
  })

  it("is 'unknown' without a state field, 'unreachable' on HTTP or network failure", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    expect(await fetchCanvasRunStatus('r1')).toBe('unknown')
    fetchMock.mockResolvedValueOnce({ ok: false, status: 404 } as unknown as Response)
    expect(await fetchCanvasRunStatus('r1')).toBe('unreachable')
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    expect(await fetchCanvasRunStatus('r1')).toBe('unreachable')
  })
})

describe('fetchCanvasPartial', () => {
  it('returns the raw body from the prefixed endpoint', async () => {
    const body = {
      state: 'interrupted',
      items: [{ kind: 'image', url: '/x.png', index: 0 }],
      prompts_pending: 2,
    }
    fetchMock.mockResolvedValueOnce(jsonResponse(body))
    expect(await fetchCanvasPartial('r1', 'http://dev:17802')).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://dev:17802/api/canvas/partial/r1',
      { credentials: 'include' },
    )
  })

  it('is null on HTTP or network failure', async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 404 } as unknown as Response)
    expect(await fetchCanvasPartial('r1')).toBeNull()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    expect(await fetchCanvasPartial('r1')).toBeNull()
  })
})
