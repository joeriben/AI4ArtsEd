/**
 * The client for this platform's streamed answers: a POST whose reply arrives as
 * an SSE stream and which resolves, and throws, like the plain POST it replaces.
 *
 * It was written for /api/schema/pipeline/direct — the Latent Lab's run endpoint,
 * the way in on which the prompt reaches the model unchanged. That one answered to
 * /api/schema/pipeline/legacy until 2026-08-24; that name meant the legacy
 * ComfyUI workflows it first ran, not an old API, and it said the wrong thing
 * about the newest surfaces on the platform. The old route stays as an alias.
 *
 * That endpoint says nothing from the moment the request arrives until the image
 * is saved, and some of its runs are long: Encoder Fusion's Original Fusion has
 * an LLM write its two encoder prompts before anything is generated, which on
 * 2026-08-23 took 122 s and 18 s next to 8 s of generation. Cloudflare closes an
 * origin connection that has sent nothing for 100 seconds, so those runs finished
 * on the server, saved their image, and the browser got a 524 and showed the
 * generic error. The identical run over an SSH tunnel, with no edge in between,
 * came back — which is what named the cause.
 *
 * So the request asks for the platform's stream instead of one JSON body: the
 * backend sends a heartbeat every two seconds while it works and puts the answer
 * it would have returned into the terminal `complete` event, with its HTTP status
 * beside it. That is the same heartbeat the generation stream and the canvas run
 * stream have always sent; the frames are read with the platform's SSE parser
 * rather than a second one.
 *
 * Everything above the transport stays as it was. This resolves and throws
 * exactly like the `axios.post` it replaces, so call sites keep reading
 * `response.data`, keep reading `response.status`, and keep classifying a
 * refusal with `blockedReason(error)`.
 *
 * The transport serves MORE THAN ONE endpoint. `postStreamedRun` takes the path
 * it posts to; `postDirectRun` is that same call with the direct run's path in
 * it. The Mean Images instrument sends its two long routes this way as well —
 * the variants call, measured at 21 min 50 s inside a single POST, and the
 * overlay, which waits FIFO for the plant-wide GPU slot before it can decode a
 * mean. On the server one loop answers all of them, in
 * my_app/services/streaming_response.py.
 */
import { sseFrames, SseHttpError, SseNotStreamedError } from '@/lib/sseStream'

export interface DirectRunResponse<T = any> {
  data: T
  status: number
}

export interface DirectRunOptions {
  /** Sent with the request. */
  headers?: Record<string, string>
  /** Prefix for the endpoint. Lab views pass their cross-origin dev base. */
  baseUrl?: string
  /** Which HTTP statuses resolve instead of throwing — axios's option, same
   *  meaning and the same default (everything below 400). */
  validateStatus?: (status: number) => boolean
  /** Drops the connection. The run itself keeps going and still saves its image. */
  signal?: AbortSignal
}

/** An axios-shaped rejection, so `error.response.data` keeps working. */
function httpError(res: DirectRunResponse): Error & { response: DirectRunResponse } {
  const e = new Error(`Request failed with status code ${res.status}`) as Error & {
    response: DirectRunResponse
  }
  e.response = res
  return e
}

/**
 * The sentence the platform answered a failed run with, where it answered with
 * one. The routes put the cause into `error` (a ComfyUI node that failed, a
 * model file that is missing); the throw above carries only the status code,
 * so a surface that shows `err.message` shows "Request failed with status code
 * 500" in place of the cause. Undefined where the reply carries no sentence (a
 * torn stream, a body that is not the platform's), so the caller keeps its own
 * wording for that case instead of showing the transport's.
 */
export function serverSentence(err: unknown): string | undefined {
  const e = err as { response?: { data?: { error?: unknown; message?: unknown } } }
  for (const said of [e?.response?.data?.error, e?.response?.data?.message]) {
    if (typeof said === 'string' && said.trim()) return said.trim()
  }
  return undefined
}

async function sendStreamedRun<T = any>(
  path: string,
  body: Record<string, unknown>,
  options: DirectRunOptions = {}
): Promise<DirectRunResponse<T>> {
  const baseUrl = options.baseUrl ?? ''
  const accepts = options.validateStatus ?? ((status: number) => status < 400)

  let result: DirectRunResponse<T> | null = null
  try {
    // The answer is the frame the server NAMED `complete`; everything before it
    // is the heartbeat that keeps the edge from cutting a run that is still
    // working. Breaking here closes the reader, which is what the platform
    // reader does on the way out.
    for await (const frame of sseFrames<{ http_status?: number; body?: T } | null>(
      `${baseUrl}${path}`,
      // Both names of the one transport this client speaks. Most routes here
      // read `enable_streaming`; /pipeline/interception reads that same word as
      // an older Stage-1-and-2 protocol of its own and takes
      // `enable_answer_streaming` for this one. Saying both is this client
      // stating which transport it means, rather than a route having to guess
      // from a word that means two things on this platform.
      { ...body, enable_streaming: true, enable_answer_streaming: true },
      { signal: options.signal, headers: options.headers }
    )) {
      if (frame.event !== 'complete') continue
      result = { data: frame.data?.body as T, status: frame.data?.http_status ?? 200 }
      break
    }
  } catch (e) {
    // The server answered, but not as a stream: one plain JSON body where the
    // frames would be. That happens during a deploy here, because the bundle is
    // built locally and the backend comes from git, so the two can differ by
    // minutes — and a client that asked for a stream and got an ordinary answer
    // has been ANSWERED. It is returned in the same shape and through the same
    // status gate as a terminal frame. Throwing instead is what let three
    // image-check call sites read a refusal the server had actually delivered
    // as a network failure and fail open on it, which put a picture the check
    // had withheld in front of a child.
    if (e instanceof SseNotStreamedError) {
      // Said out loud, because reading the answer anyway is right AND hides the
      // mismatch that produced it. Throwing was what made a half-deployed pair
      // findable; a console line keeps it findable for whoever is deploying and
      // stays out of a workshop, where nobody opens a console and the run has
      // in any case succeeded.
      console.warn(
        `[directRun] ${path} answered ${e.contentType} instead of a stream. The ` +
        'bundle in this browser and the backend it is talking to are not the same ' +
        'deploy — the answer was read as a plain body.',
      )
      const plain: DirectRunResponse<T> = { data: e.body as T, status: e.status }
      if (accepts(plain.status)) return plain
      throw httpError(plain)
    }
    // The stream never opened, so no `complete` event can follow and the HTTP
    // status is the whole answer. Anything else thrown here tore or was
    // aborted, and belongs to the caller unchanged.
    if (!(e instanceof SseHttpError)) throw e
    const failed: DirectRunResponse<T> = { data: e.body as T, status: e.status }
    if (accepts(failed.status)) return failed
    throw httpError(failed)
  }

  if (!result) {
    // The stream ended without its terminal event: the connection tore. Worded
    // like a network failure because that is what it is — the views classify it
    // through the platform's error classifier, not by this string.
    throw new Error('Network error: the run stream ended without a result')
  }
  if (accepts(result.status)) return result
  throw httpError(result)
}

/** The same call, under the name every streamed pipeline route is reached by. */
export async function postStreamedRun<T = any>(
  path: string,
  body: Record<string, unknown>,
  options: DirectRunOptions = {}
): Promise<DirectRunResponse<T>> {
  return sendStreamedRun<T>(path, body, options)
}

/**
 * The direct run, which is where this transport started, and which every Latent
 * Lab instrument reaches it through. Its call sites see no difference: the same
 * two arguments, the same answer, the same throw.
 */
export async function postDirectRun<T = any>(
  body: Record<string, unknown>,
  options: DirectRunOptions = {}
): Promise<DirectRunResponse<T>> {
  return postStreamedRun<T>('/api/schema/pipeline/direct', body, options)
}
