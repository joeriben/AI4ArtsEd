// Shared SSE run-stream client for /api/canvas/execute-stream.
// State-neutral: no Vue reactivity. Consumers own ALL state; this module owns
// transport, the reconnect cursor and the reconnect/status loop. The framing is
// not its own: readSseFrames in lib/sseStream finds the frames of every stream
// this platform reads, including the two this module opens.
// Extracted from stores/canvas.ts (executeWorkflow) and views/resona.vue
// (spawnGraphRun) — Rule #13 consolidation.

import { readSseFrames } from '@/lib/sseStream'

/** One parsed SSE frame. `id` is the running event index from the `id:` line
 *  (lossless reconnect cursor, emitted by canvas_routes.py iter_events). */
export interface CanvasSSEEvent {
  type: string
  data: unknown
  id?: number
}

export interface CanvasRunStartPayload {
  nodes: unknown[]
  connections: unknown[]
  device_id: string
  /** canvas_workflow sends workflow identity; resona does not.
   *  Serialized ONLY when provided (keeps both request bodies byte-identical). */
  workflow?: { id: string; name: string }
  /** Which language a reading node on this canvas writes in. Serialized ONLY
   *  when provided; without it the run takes the instance language. */
  lang?: string
}

export type CanvasRunOutcome =
  /** Terminal SSE `complete` received. */
  | { kind: 'complete' }
  /** Terminal SSE `error` received. */
  | { kind: 'server_error' }
  /** Stream ended/tore without a terminal event. `error` present = thrown
   *  network tear; absent = clean EOF, reconnects exhausted/disabled. The
   *  Error type is safe: the tear predicate only matches Error instances. */
  | { kind: 'torn'; error?: Error }
  /** cancel() / AbortError. */
  | { kind: 'aborted' }
  /** HTTP !ok, missing body, or any non-tear throw. RAW thrown value, never
   *  wrapped — consumers' `instanceof Error` fallbacks ('Network error'
   *  literal for non-Error throws) must keep firing. */
  | { kind: 'transport_error'; error: unknown }

export interface CanvasRunStreamOptions {
  /** Prefix for every endpoint. Default ''. resona passes its dev base URL. */
  baseUrl?: string
  /** Enable torn-stream reconnect (GET execute-stream/<runId>?after=<cursor>,
   *  gated by status polls). Default false — canvas store behavior. */
  reconnect?: boolean
  /** Reconnect backoff schedule in ms. Default [1000, 2000, 4000, 8000, 15000]. */
  reconnectBackoffsMs?: number[]
  /** Invoked once per parsed SSE event, in stream order, AFTER the core has
   *  updated its cursor/runId bookkeeping. Terminal events are delivered too. */
  onEvent: (event: CanvasSSEEvent) => void
}

export interface CanvasRunHandle {
  /** Resolves with the final outcome. NEVER rejects. */
  done: Promise<CanvasRunOutcome>
  /** run_id captured from the `run_started` event; null until received. */
  readonly runId: string | null
  /** Highest SSE `id:` seen; -1 before the first indexed event. */
  readonly lastEventIndex: number
  /** Abort the POST/GET transport and the reconnect loop. */
  cancel(): void
}

const DEFAULT_RECONNECT_BACKOFFS_MS = [1000, 2000, 4000, 8000, 15000]

export function startCanvasRun(
  payload: CanvasRunStartPayload,
  options: CanvasRunStreamOptions
): CanvasRunHandle {
  const controller = new AbortController()
  const signal = controller.signal
  const baseUrl = options.baseUrl ?? ''
  const backoffsMs = options.reconnectBackoffsMs ?? DEFAULT_RECONNECT_BACKOFFS_MS

  let runId: string | null = null
  let lastEventIndex = -1

  // Outcome of one connection attempt. torn → the stream died without a
  // terminal event (e.g. server restart mid-run).
  type ConsumeOutcome = 'complete' | 'server_error' | 'torn'

  // Drive one live connection to exhaustion. The backend sends run_started
  // FIRST (carrying run_id) so a torn stream can reconnect/recover by run_id
  // even if it tears before `complete`.
  async function consume(response: Response): Promise<ConsumeOutcome> {
    if (!response.body) throw new Error('No response body for streaming')
    for await (const frame of readSseFrames(response.body)) {
      // This route names every frame it writes. An unnamed one belongs to some
      // other conversation, and there is no case below that would answer it.
      if (frame.event === undefined) continue
      const event: CanvasSSEEvent = { type: frame.event, data: frame.data, id: frame.id }
      if (typeof event.id === 'number' && event.id > lastEventIndex) {
        lastEventIndex = event.id
      }
      if (event.type === 'run_started') {
        const d = event.data as { run_id?: unknown } | null
        if (d && typeof d.run_id === 'string') runId = d.run_id
      }
      options.onEvent(event)
      // Stop consuming immediately on a terminal event: the backend closes the
      // stream right after it, so nothing observable can follow. Leaving the
      // loop here closes the reader with it.
      if (event.type === 'complete') return 'complete'
      if (event.type === 'error') return 'server_error'
    }
    // The stream ended without a terminal event: torn.
    return 'torn'
  }

  async function run(): Promise<CanvasRunOutcome> {
    try {
      const body: Record<string, unknown> = {
        nodes: payload.nodes,
        connections: payload.connections,
        device_id: payload.device_id,
      }
      if (payload.workflow) body.workflow = payload.workflow
      if (payload.lang) body.lang = payload.lang
      const response = await fetch(`${baseUrl}/api/canvas/execute-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        // The session, for the same reason lib/sseStream.ts carries it: this
        // stream opens its own response rather than going through that reader,
        // so the one-line fix there does not reach here. `/api/canvas/execute
        // -stream` resolves the safety level at its boundary and hands it to
        // the whole run — without the cookie it found no course, and a canvas
        // run started from a browser signed into a kids course went at the
        // installation's level.
        credentials: 'include',
        signal,
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)

      let outcome: ConsumeOutcome = await consume(response)

      if (options.reconnect) {
        // Reconnect loop: on a torn stream, re-attach by run_id from the last
        // event index we saw (lossless within a live process). Bounded retries
        // with backoff. Between attempts, ask the status endpoint: a finished/
        // interrupted/errored run needs no more streaming.
        for (let attempt = 0; outcome === 'torn' && attempt < backoffsMs.length; attempt++) {
          const state = runId ? await fetchCanvasRunStatus(runId, baseUrl) : 'unreachable'
          if (state === 'complete') {
            // It finished between our drops — reconnect once to collect `complete`.
          } else if (state === 'interrupted' || state === 'error') {
            break // hard stop server-side; the consumer recovers what it can
          } else if (state === 'unreachable' && attempt >= 2) {
            break // backend stayed down across several tries
          }
          await new Promise((res) => setTimeout(res, backoffsMs[attempt]))
          if (signal.aborted) return { kind: 'aborted' }
          try {
            const rc = await fetch(
              `${baseUrl}/api/canvas/execute-stream/${runId}?after=${lastEventIndex}`,
              { credentials: 'include', signal },
            )
            if (rc.ok) outcome = await consume(rc)
          } catch {
            // stay 'torn'; loop will back off and retry (or exhaust)
          }
        }
      }

      if (outcome === 'complete') return { kind: 'complete' }
      if (outcome === 'server_error') return { kind: 'server_error' }
      return { kind: 'torn' }
    } catch (e) {
      if ((e as { name?: string })?.name === 'AbortError' || signal.aborted) {
        return { kind: 'aborted' }
      }
      // Network-tear wording differs across browsers (Safari "Load failed",
      // Chrome "Failed to fetch"). A thrown tear does NOT enter the reconnect
      // loop (legacy semantics: consumers go straight to partial recovery).
      const rawMsg = e instanceof Error ? e.message : ''
      const streamTorn =
        e instanceof TypeError ||
        rawMsg === 'Load failed' ||
        rawMsg === 'Failed to fetch' ||
        rawMsg.includes('NetworkError')
      if (streamTorn) return { kind: 'torn', error: e as Error }
      // RAW thrown value, never wrapped (consumers re-derive their fallbacks).
      return { kind: 'transport_error', error: e }
    }
  }

  return {
    done: run(),
    get runId() {
      return runId
    },
    get lastEventIndex() {
      return lastEventIndex
    },
    cancel() {
      controller.abort()
    },
  }
}

export interface CanvasPartialItem {
  kind: string
  url: string
  index: number
  node_label?: string
}
export interface CanvasPartialBody {
  state?: string
  items?: CanvasPartialItem[]
  prompts_pending?: number
}

/** GET <baseUrl>/api/canvas/partial/<runId>.
 *  Returns the raw body, or null on non-OK / network failure. No filtering —
 *  what counts as "recovered" is consumer policy. */
export async function fetchCanvasPartial(
  runId: string,
  baseUrl: string = ''
): Promise<CanvasPartialBody | null> {
  try {
    const r = await fetch(`${baseUrl}/api/canvas/partial/${runId}`,
                          { credentials: 'include' })
    if (!r.ok) return null
    return (await r.json()) as CanvasPartialBody
  } catch {
    return null
  }
}

/** GET <baseUrl>/api/canvas/runs/<runId>/status.
 *  Returns body.state, 'unknown' when the field is missing, 'unreachable' on
 *  non-OK / network failure. Used internally by the reconnect loop. */
export async function fetchCanvasRunStatus(runId: string, baseUrl: string = ''): Promise<string> {
  try {
    const r = await fetch(`${baseUrl}/api/canvas/runs/${runId}/status`,
                          { credentials: 'include' })
    if (!r.ok) return 'unreachable'
    const body = (await r.json()) as { state?: string }
    return body.state || 'unknown'
  } catch {
    return 'unreachable'
  }
}
