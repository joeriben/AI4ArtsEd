/**
 * One reader for every event stream this platform opens with a POST body.
 *
 * `EventSource` can only ever ask with a GET and a query string, so everything
 * that has to send a whole request body — a chat turn with its history, its
 * board and its context — reads the stream by hand. That reading was written
 * out five separate times (services/directRun.ts, stores/canvas.ts,
 * views/compare/vlm_analysis_comparison.vue, composables/useModelInstall.ts,
 * and again per surface), and every copy re-invented the same three things:
 * where a frame ends, what to do with a half-arrived one, and how to stop.
 *
 * Here it is once. What a caller does with an event is the caller's; finding
 * the events is not.
 *
 * Frames are `data: <json>` separated by a blank line, the shape every SSE
 * route on this server writes. A route may also NAME a frame in an `event:`
 * line and number it in an `id:` line, and both travel with the payload: the
 * streamed run tells its terminal frame from the heartbeats before it by that
 * name, and the canvas run counts the index so a torn stream can re-attach
 * where it stopped. A route that writes no name puts one inside the JSON
 * instead, which is the chat stream shape, and that one stays the caller's to
 * read.
 *
 * A frame that is not JSON is skipped rather than thrown: a proxy that injects
 * a comment line must not end a reply mid-sentence. That silence is deliberate
 * and it stays, because five surfaces read through here and none of them should
 * write a line about another's stream — so a caller that wants to hear about
 * ITS OWN passes `onSkipped`, and a caller that passes nothing is as quiet as
 * before.
 *
 * composables/useModelInstall.ts is the one that wants to hear. A download whose
 * progress frames stop arriving looks, on its bar, exactly like a download that
 * died, and one line on the console is what tells the two apart. It kept a whole
 * reader of its own to keep that line; it passes `onSkipped` now, and this file
 * is the only frame reader left in the frontend.
 */
import { clearRunPlace, noteRunPlace } from '@/composables/useRunPlace'

export interface SseOptions {
  /** Aborts the request AND the reading. */
  signal?: AbortSignal
  /** Extra headers. Content-Type is set for you. */
  headers?: Record<string, string>
  /**
   * Told about a frame this reader dropped because its payload was not JSON:
   * the payload text it tried, and what `JSON.parse` threw.
   *
   * A dropped frame is otherwise indistinguishable from a stream that simply
   * went quiet, and for a progress bar those two look the same and mean
   * opposite things. Pass nothing and the reader stays silent, which is what
   * every surface but one wants: a page must not write console lines about a
   * stream another page is reading.
   */
  onSkipped?: (payload: string, error: unknown) => void
}

/**
 * Thrown when the answer is not a stream at all: the server replied with one
 * plain body, and its content type says so. `body` is that body, read as JSON.
 *
 * This is a deploy state here rather than a fault. The frontend bundle is built
 * on a machine and the backend comes from git, so for the minutes between the
 * two a page that asks for a stream can reach a server that answers the same
 * route with a single JSON object. What came back is still the ANSWER, so it is
 * carried on this error rather than discarded — a caller that can read it
 * should, and one that cannot at least learns what it got instead of being told
 * the connection tore.
 */
export class SseNotStreamedError extends Error {
  status: number
  body: unknown
  contentType: string
  constructor(status: number, body: unknown, contentType: string) {
    super(`Not a stream: ${contentType || 'no content type'}`)
    this.name = 'SseNotStreamedError'
    this.status = status
    this.body = body
    this.contentType = contentType
  }
}

/** Thrown when the stream never opened. `status` is the HTTP status. */
export class SseHttpError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(`HTTP ${status}`)
    this.name = 'SseHttpError'
    this.status = status
    this.body = body
  }
}

/**
 * One frame of a stream: the payload, and what the route wrote around it.
 *
 * `event` and `id` are the SSE lines of those names, absent when the route
 * wrote neither. A non-numeric `id` is dropped rather than carried, because the
 * one reader of it counts with it.
 */
export interface SseFrame<T = any> {
  event?: string
  data: T
  id?: number
}

/**
 * Is this frame the model line rather than something a caller reads?
 *
 * `model_place` is transport and not content: it says which model the run
 * behind this stream has just been sent to, and the bar of the Latent Lab is
 * its one reader (composables/useRunPlace.ts). It is read HERE, where every
 * stream this frontend frames for itself passes through, so the reading exists
 * once instead of once per consumer (rule 13), and it is swallowed — no caller
 * below has ever been handed it.
 */
function tookThePlace(frame: SseFrame<any>, owner: object): boolean {
  if (frame.event !== 'model_place') return false
  noteRunPlace(frame.data, owner)
  return true
}

/**
 * POST `body` to `url` and hand back every frame of the answer as it arrives,
 * whole: its name, its payload and its index.
 *
 * Errors BEFORE the first byte are thrown as SseHttpError, carrying whatever
 * the server said — the status line is still there to be read. Once the stream
 * is open there is no status left to change, so a server-side failure arrives
 * as an event like any other and it is the caller who knows what it means.
 */
export async function* sseFrames<T = any>(
  url: string,
  body: unknown,
  options: SseOptions = {},
): AsyncGenerator<SseFrame<T>, void, void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    body: JSON.stringify(body),
    // The session travels, as it does on every other credentialed call of this
    // platform (services/labApi.ts, stores/labAuth.ts, stores/safetyLevel.ts).
    // fetch's default drops the cookie the moment the call is cross-origin.
    // Under `npm run dev` that is every call site which passes an explicit
    // base — the labs on 5173 posting to the backend on 17802 — while a site
    // posting a RELATIVE path goes through Vite's own /api proxy and was
    // same-origin all along. For a route that resolves the safety level the
    // difference decided the level: no cookie, no course, and the answer came
    // back at the installation's level, so a browser signed into a kids course
    // was served at `open`. Deployed, where everything is same-origin, this is
    // what the default already did.
    credentials: 'include',
    signal: options.signal,
  })

  if (!response.ok || !response.body) {
    throw new SseHttpError(response.status, await response.json().catch(() => null))
  }

  // A content type that NAMES something other than an event stream is the
  // server saying it did not stream: a Flask route answering with jsonify sends
  // application/json, and its body is one object where the frames would be.
  // Read as frames it yields none, and the caller then reports a torn
  // connection for an answer that arrived intact. Only a STATED content type
  // decides here — a response that names none is read as frames exactly as
  // before, because the framing has to keep working for a stream whose route
  // wrote no header.
  const contentType = response.headers?.get('content-type') ?? ''
  if (contentType && !contentType.includes('text/event-stream')) {
    throw new SseNotStreamedError(
      response.status,
      await response.json().catch(() => null),
      contentType,
    )
  }

  yield* readSseFrames<T>(response.body, { onSkipped: options.onSkipped })
}

/**
 * The same stream, read for its payloads alone.
 *
 * The surfaces that read a chat turn are served by a route that names its
 * frames inside the JSON rather than in an `event:` line, so the name is
 * already in what they are handed and the envelope would only stand in the way.
 */
export async function* sseEvents<T = any>(
  url: string,
  body: unknown,
  options: SseOptions = {},
): AsyncGenerator<T, void, void> {
  for await (const frame of sseFrames<T>(url, body, options)) yield frame.data
}

/**
 * The frames of a stream that is already open.
 *
 * Held apart from the POST above because not every stream here is opened with
 * one: the canvas run re-attaches to a torn run with a GET and a cursor, and
 * reads what comes back with the same eyes. Whoever opened the response says
 * what its status meant; from here on there is only framing.
 */
export async function* readSseFrames<T = any>(
  stream: ReadableStream<Uint8Array>,
  options: Pick<SseOptions, 'onSkipped'> = {},
): AsyncGenerator<SseFrame<T>, void, void> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  // This stream's identity for the model line: it may take away only what it
  // put there. A page runs several streams at once and the short ones end
  // first — a back-translation, the check on a dropped picture — and an
  // unowned clear emptied the line of the run that was still working.
  const thisRun = {}
  // Where the next search for a frame end may start. Without it every arriving
  // chunk would rescan the buffer from the front, and the terminal frame of a
  // Latent Lab run carries base64 images: megabytes, arriving in many small
  // pieces.
  let scanned = 0
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // Frames are taken off the FRONT, one at a time. Scanning from the last
      // separator instead would drop every frame that shared a chunk with a
      // later one — which is what a fast model does for whole sentences at a
      // time. The search starts one character behind what has already been
      // scanned, because the blank line may straddle the join between chunks.
      let cut = buffer.indexOf('\n\n', Math.max(0, scanned - 1))
      while (cut !== -1) {
        const frame = buffer.slice(0, cut)
        buffer = buffer.slice(cut + 2)
        const parsed = parseFrame<T>(frame, options.onSkipped)
        if (parsed !== undefined && !tookThePlace(parsed, thisRun)) yield parsed
        cut = buffer.indexOf('\n\n')
      }
      scanned = buffer.length
    }
    // A stream that ended without its last blank line still said something.
    const tail = parseFrame<T>(buffer, options.onSkipped)
    if (tail !== undefined && !tookThePlace(tail, thisRun)) yield tail
  } finally {
    // However this stream ended — its last frame, a tear, a caller that broke
    // out of the loop — no model of THIS stream is at work any more.
    clearRunPlace(thisRun)
    reader.cancel().catch(() => {})
  }
}

function parseFrame<T>(
  frame: string,
  onSkipped?: (payload: string, error: unknown) => void,
): SseFrame<T> | undefined {
  let event: string | undefined
  let id: number | undefined
  const pieces: string[] = []
  for (const line of frame.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.startsWith('event:')) {
      event = trimmed.slice(6).trim() || undefined
    } else if (trimmed.startsWith('id:')) {
      // A non-numeric id is dropped and the frame still stands: the cursor it
      // feeds is a count, and a caller that reads no id is unaffected either way.
      const n = parseInt(trimmed.slice(3).trim(), 10)
      if (!Number.isNaN(n)) id = n
    } else if (trimmed.startsWith('data:')) {
      // EVERY data: line, joined by newlines — which is what the SSE
      // specification says one frame's payload IS. Reading only the first threw
      // the rest of a value away and left what remained unparseable, so the
      // frame was dropped whole and silently. No producer on this platform
      // writes such a frame today: every route here puts one `json.dumps` on
      // one line, and the two SSE passthroughs re-frame the upstream line by
      // line, which would split a multi-line frame apart before it ever
      // arrived. It costs nothing to read what any conforming producer may
      // send.
      pieces.push(trimmed.slice(5).trim())
    }
  }
  // A frame carrying no payload is no frame. That is how the heartbeat comment
  // the server breathes with, and the `[DONE]` sentinel some routes close on,
  // pass without reaching anybody.
  const payload = pieces.join('\n')
  if (!payload || payload === '[DONE]') return undefined
  try {
    return { event, data: JSON.parse(payload) as T, id }
  } catch (error) {
    // Skipped rather than thrown, for the reason given at the top of this file
    // — and named to the one caller that asked to be told about its own stream.
    onSkipped?.(payload, error)
    return undefined
  }
}
