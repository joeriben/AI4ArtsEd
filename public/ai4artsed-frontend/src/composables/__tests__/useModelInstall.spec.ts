/**
 * The model install, reading its progress through the platform's own SSE reader.
 *
 * It kept a hand-written reader — the last one in this frontend — for one
 * reason: the `console.warn` it wrote on a frame it could not parse. A download
 * whose progress frames stop arriving looks, on the bar, exactly like a
 * download that died, and that line is what tells the two apart; the shared
 * reader is deliberately silent, because five surfaces read through it and none
 * of them should write a line about another's stream. The silence is now
 * optional and this composable is the one caller that opts out of it.
 *
 * Nothing here reaches the GPU service: fetch is a stand-in and the wire is
 * written by hand.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useModelInstall } from '../useModelInstall'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  useModelInstall().dismiss()
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
    headers: {
      get: (name: string) =>
        name.toLowerCase() === 'content-type' ? 'text/event-stream' : null,
    },
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

function frame(ev: unknown): string {
  return `data: ${JSON.stringify(ev)}\n\n`
}

describe('useModelInstall', () => {
  it('drives the bar from the frames and ends on done', async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        frame({ type: 'start', file: 'a.gguf', total_mb: 100 }),
        ': heartbeat\n\n',
        frame({ type: 'progress', file: 'a.gguf', done_mb: 50, total_mb: 100, speed_mb_s: 5 }),
        frame({ type: 'done' }),
      ]),
    )
    const { install, active } = useModelInstall()
    await install('local/a-model', 'A Model')
    expect(active.value?.state).toBe('done')
    expect(active.value?.currentFile).toBe('a.gguf')
    expect(active.value?.doneMb).toBe(50)
    expect(active.value?.totalMb).toBe(100)
  })

  it('says on the console which frame it could not read, and keeps reading', async () => {
    // The whole reason this composable had a reader of its own.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        frame({ type: 'start', file: 'b.gguf', total_mb: 20 }),
        'data: {not json\n\n',
        frame({ type: 'done' }),
      ]),
    )
    const { install, active } = useModelInstall()
    await install('local/b-model', 'B Model')
    expect(warn).toHaveBeenCalled()
    expect(String(warn.mock.calls[0]![0])).toContain('[useModelInstall]')
    expect(String(warn.mock.calls[0]![1])).toBe('{not json')
    // And the frames after the unreadable one still arrived.
    expect(active.value?.state).toBe('done')
  })

  it('shows the status when the stream never opened', async () => {
    // `SseHttpError` carries the message `HTTP <status>`, which is the string
    // this composable showed while it threw that error itself.
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: 'the GPU service is down' }),
    } as unknown as Response)
    const { install, active } = useModelInstall()
    await install('local/c-model', 'C Model')
    expect(active.value?.state).toBe('error')
    expect(active.value?.errorMessage).toBe('HTTP 503')
  })

  it('calls a stream that stopped mid-download an error, as it always did', async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([frame({ type: 'start', file: 'd.gguf', total_mb: 20 })]),
    )
    const { install, active } = useModelInstall()
    await install('local/d-model', 'D Model')
    expect(active.value?.state).toBe('error')
    expect(active.value?.errorMessage).toBe('Stream ended unexpectedly')
  })

  it('carries the error a frame of its own reported', async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([frame({ type: 'error', message: 'no space left on the card' })]),
    )
    const { install, active } = useModelInstall()
    await install('local/e-model', 'E Model')
    expect(active.value?.state).toBe('error')
    expect(active.value?.errorMessage).toBe('no space left on the card')
  })
})
