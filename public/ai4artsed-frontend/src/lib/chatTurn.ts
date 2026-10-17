/**
 * One chat turn, taken over the streaming endpoint and handed back whole.
 *
 * `/api/chat` and `/api/chat/stream` are two mouths on one generator
 * (`_chat_events` in routes/chat_routes.py): the same system prompt, the same
 * tool rounds, the same reply. What they differ in is when the first byte
 * leaves the server. That difference decides whether an answer arrives at all,
 * because the tunnel in front of this server ends any proxied request whose
 * origin has sent nothing for about a hundred seconds, and a turn that is
 * allowed up to ten model calls against a cloud provider regularly stays silent
 * for longer. The browser is then handed an HTTP 524 instead of the answer that
 * was on its way.
 *
 * So every surface reads the stream — including the ones that show the reply
 * whole. This function is for those. It drains the stream, drops the pieces as
 * they pass, and returns the closing payload: the very object `/api/chat`
 * answered with, minus the `type` marker that only the stream needs. Nothing
 * above the call has to change, and nobody watching the screen can tell.
 *
 * Surfaces that read ALONG while the reply is written (views/resona.vue,
 * views/ai_persona.vue) keep their own loop over `sseEvents`, because what a
 * page does with a token is that page's business.
 */
import { sseEvents, type SseOptions } from './sseStream'

/** The closing payload of one turn — the body `POST /api/chat` answered with. */
export type ChatTurnResult = {
  reply: string
  thinking: string | null
  context_used: boolean
  run_id: string | null
  generated_media: unknown[]
  generated_graphs: unknown[]
  generated_compositions: unknown[]
  evidence_violations: unknown[]
  /** Why the reply stream was cut, or null when the sentence was finished. */
  broke_off: string | null
}

/**
 * Everything `_chat_events` writes into the stream.
 *
 * `token`, `discard` and `withdraw` are the reading pace: a piece of the answer,
 * a round taken back because it turned out to be a tool call, a draft struck
 * through after it failed its evidence duty. `graph` carries an apparatus the
 * moment it is built, ahead of the sentence written about it; it is a workshop
 * event and no caller of this function reads it. `done` closes the turn, `error`
 * ends it.
 *
 * `done` is `Partial` on purpose. This is what ARRIVED, not what was promised:
 * a frame that says `done` and carries none of the eight fields is a shape this
 * type has to be able to describe, because `asTurn` below is where it is turned
 * away.
 */
type ChatEvent =
  | { type: 'token'; text: string }
  | { type: 'discard' }
  | { type: 'withdraw'; text: string }
  | ({ type: 'done' } & Partial<ChatTurnResult>)
  | { type: 'error'; error?: string; details?: string; status?: number }

/**
 * The turn was refused or failed, and the server said so inside the stream.
 *
 * This is what a non-2xx from `/api/chat` used to be: the status line has long
 * gone out by the time a turn breaks, so the refusal travels as an event. It is
 * a distinct type because a caller that used to read a non-2xx body as "no
 * reply" has to keep doing exactly that, and must not confuse it with a stream
 * that was cut. `status` is the code the blocking endpoint would have sent.
 */
export class ChatStreamError extends Error {
  status?: number
  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ChatStreamError'
    this.status = status
  }
}

/**
 * The stream ended and no turn was in it.
 *
 * Its own type, because the surfaces have to tell it from a connection that
 * tore. This is what a non-2xx body with no `reply` in it used to be at
 * `/api/chat`, and a column that showed "no response received" for that has to
 * keep showing it. `unreadableFrames` counts the frames that were not events at
 * all, which is the difference between a stream that stopped and one that
 * arrived corrupted.
 */
export class ChatNoReplyError extends Error {
  unreadableFrames: number
  constructor(message: string, unreadableFrames = 0) {
    super(message)
    this.name = 'ChatNoReplyError'
    this.unreadableFrames = unreadableFrames
  }
}

/**
 * One `done` frame as the turn it claims to be, or nothing.
 *
 * The eight fields are what `POST /api/chat` answered with, every one of them
 * present in every answer. A `done` frame short of them was handed on as it
 * arrived, and `{}` reached components/ChatOverlay.vue as `undefined`, which
 * was pushed into the conversation as the assistant's message: an empty bubble
 * where an answer belongs, and nothing anywhere saying why.
 *
 * A frame that carries no `reply` is not a turn and is turned away here. The
 * other seven are filled with the empty value the blocking endpoint would have
 * sent, so a caller counting `generated_media` still counts something.
 */
function asTurn(ev: { type: 'done' } & Partial<ChatTurnResult>): ChatTurnResult | null {
  if (typeof ev.reply !== 'string') return null
  return {
    reply: ev.reply,
    thinking: typeof ev.thinking === 'string' ? ev.thinking : null,
    context_used: ev.context_used === true,
    run_id: typeof ev.run_id === 'string' ? ev.run_id : null,
    generated_media: Array.isArray(ev.generated_media) ? ev.generated_media : [],
    generated_graphs: Array.isArray(ev.generated_graphs) ? ev.generated_graphs : [],
    generated_compositions: Array.isArray(ev.generated_compositions)
      ? ev.generated_compositions
      : [],
    evidence_violations: Array.isArray(ev.evidence_violations) ? ev.evidence_violations : [],
    broke_off: typeof ev.broke_off === 'string' && ev.broke_off ? ev.broke_off : null,
  }
}

/**
 * POST `body` to a chat stream `url` and return the finished turn.
 *
 * Throws `SseHttpError` when the stream never opened (the status line is still
 * there to be read), `ChatStreamError` when the server ended the turn itself,
 * and `ChatNoReplyError` when the stream stopped without a turn in it — each
 * carrying what actually went wrong, since a surface that only ever hears
 * "request failed" can tell the room nothing.
 */
export async function chatTurn(
  url: string,
  body: unknown,
  options: SseOptions = {},
): Promise<ChatTurnResult> {
  let done: ChatTurnResult | null = null
  let unreadable = 0
  for await (const raw of sseEvents<unknown>(url, body, options)) {
    // Not everything a stream can carry is an event. `data: null` parses to
    // null and `data: 4` to a number, and reading `.type` off either threw a
    // raw TypeError out of this function — a message naming a JavaScript
    // property where a broken reply should have named itself. Counted and
    // passed over; the count travels on the error at the end, because a stream
    // that went quiet and a stream that arrived corrupted are different things
    // to be told.
    if (!raw || typeof raw !== 'object') {
      unreadable++
      continue
    }
    const ev = raw as ChatEvent
    // The pieces are dropped on purpose: this caller shows the finished reply
    // in one piece, as it always has.
    if (ev.type === 'done') {
      const turn = asTurn(ev)
      if (!turn) {
        unreadable++
        continue
      }
      // The FIRST `done` is the turn, because `done` is what closes one. A
      // second is a producer writing two turns into one stream, and taking the
      // last let whatever followed overwrite an answer that was already whole.
      if (done) {
        console.warn('[chatTurn] a second done frame arrived after the turn had closed — ignored')
        continue
      }
      // A turn whose reply stream was cut carries half a sentence. The server
      // ships it now instead of losing the whole turn, and the workshop board
      // — which reads along, piece by piece — shows that half and says under it
      // that it stopped. Every caller HERE shows a finished reply in one piece
      // and has nowhere to say that. Ending the turn is what these surfaces did
      // before the server learned to hand a broken one over, and it stays what
      // they do: half an answer presented as the whole answer would be read as
      // the whole answer, spoken aloud, and written into the next turn's
      // history.
      if (turn.broke_off) throw new ChatStreamError(turn.broke_off)
      done = turn
    } else if (ev.type === 'error') {
      // Before the turn closed, this ends it — which is what a non-2xx from the
      // blocking endpoint did. AFTER it, it cannot un-write a reply that is
      // already complete: the journal write that failed is not the answer, and
      // discarding the answer over it left the room with nothing. The turn
      // stands and the contradiction goes where a developer will find it.
      if (done) {
        console.warn('[chatTurn] an error frame arrived after the turn had closed — '
          + 'the reply stands:', ev.details || ev.error)
        break
      }
      throw new ChatStreamError(ev.details || ev.error || 'chat stream error', ev.status)
    }
  }
  if (!done) {
    throw new ChatNoReplyError(
      'the reply stream ended without a reply'
        + (unreadable ? ` (${unreadable} frame(s) could not be read as a turn)` : ''),
      unreadable,
    )
  }
  // The blocking endpoint answers with these nine fields and nothing else, so
  // that is what is handed on: the caller gets the object it has always got.
  return done
}
