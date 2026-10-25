import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCanvasStore } from '../canvas'

/**
 * The batch run reads its progress with the platform's shared SSE reader
 * (lib/sseStream). These tests hold that reading to what the hand-written loop
 * it replaced did: the frames are taken however the chunks fall, a frame that
 * cannot be read is stepped over rather than ending the batch, and a request
 * that never opened still says which status refused it.
 */

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

function frame(name: string, data: unknown): string {
  return 'event: ' + name + '\ndata: ' + JSON.stringify(data) + '\n\n'
}

/** A response whose body hands out the given chunks and then ends. */
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
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

describe('canvas store — executeBatch', () => {
  it('reads the run through, whichever chunk boundary the frames fall on', async () => {
    const wire =
      frame('batch_started', { batch_id: 'b-1', total_runs: 2 }) +
      frame('run_start', { run_index: 0, total_runs: 2 }) +
      frame('run_complete', { run_index: 0, export_path: '/x/run0.json' }) +
      frame('run_start', { run_index: 1, total_runs: 2 }) +
      frame('run_complete', { run_index: 1, export_path: '/x/run1.json' }) +
      frame('batch_complete', { export_paths: ['/x/run0.json', '/x/run1.json'], total_runs: 2 })
    // Cut mid-frame on purpose: the edge delivers what it has, and a reader
    // that scanned only whole chunks would lose the frame straddling the seam.
    const cut = wire.indexOf('run_complete') + 4
    fetchMock.mockResolvedValue(sseResponse([wire.slice(0, cut), wire.slice(cut)]))

    const store = useCanvasStore()
    await store.executeBatch(2)

    expect(store.batchId).toBe('b-1')
    expect(store.batchCurrentRun).toBe(1)
    expect(store.batchExportPaths).toEqual(['/x/run0.json', '/x/run1.json'])
    expect(store.batchCompletedRuns).toBe(2)
    expect(store.error).toBeNull()
    expect(store.isBatchExecuting).toBe(false)
  })

  it('steps over a frame it cannot read and still finishes the batch', async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        frame('batch_started', { batch_id: 'b-2', total_runs: 1 }),
        'event: run_start\ndata: {"run_index": 0, oops\n\n',
        frame('batch_complete', { export_paths: ['/x/only.json'], total_runs: 1 }),
      ]),
    )

    const store = useCanvasStore()
    await store.executeBatch(1)

    expect(store.batchId).toBe('b-2')
    expect(store.batchExportPaths).toEqual(['/x/only.json'])
    expect(store.batchCompletedRuns).toBe(1)
    expect(store.error).toBeNull()
  })

  it('says which status refused a batch that never opened', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'SERVICE UNAVAILABLE',
    } as unknown as Response)

    const store = useCanvasStore()
    await store.executeBatch(1)

    expect(store.error).toBe('HTTP 503: SERVICE UNAVAILABLE')
    expect(store.isBatchExecuting).toBe(false)
  })

  it('says so when a 200 arrives with no body to read', async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, statusText: 'OK' } as unknown as Response)

    const store = useCanvasStore()
    await store.executeBatch(1)

    expect(store.error).toBe('No response body')
  })
})
