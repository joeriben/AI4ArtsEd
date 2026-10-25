/**
 * What the instruments of the Latent Lab do ALIKE when they send a run — the
 * post, the answer, the reasons a run did not come back, and the reading of a
 * field that can be emptied.
 *
 * The Audio Synth, MMAudio and ImageBind Guidance stood in one file until
 * 2026-09-05. Splitting them into three left each with its own copy of these
 * helpers, character for character, which is the second implementation Rule 13
 * forbids (docs/ELEMENT_STRUCTURE_REGISTRY.md). They live here once — and with
 * them the copies that stood in the raster instruments: `refusalKeyOf` in the
 * Fusion Workbench, Composable Diffusion, Concept Algebra, Feature Probing,
 * Decomposition and `composables/useRasterRun.ts`, `generationErrorFor` in the
 * Fusion Workbench and the Surrealizer, and `clamp` in Decomposition.
 *
 * Nothing about a particular instrument is in here: what a run IS, what it
 * sends and what it does with what comes back stays in the instrument, because
 * only the instrument knows that.
 */
import { nextTick, type Ref } from 'vue'
import { apiBase } from '@/services/labApi'
import { postStreamedRun } from '@/services/directRun'
import { blockedReason, classifyError, safetyBlockKey } from '@/composables/useGenerationStream'

/**
 * One POST to a cross-aesthetic route, streamed.
 *
 * The sound stands in the plant-wide queue before it is made, and the edge in
 * front of this server cuts a request whose origin has sent nothing for about
 * 100 seconds — so sound that had already been made reached nobody. The answer
 * arrives in the stream's terminal frame instead of as one body.
 *
 * A status outside 2xx throws the TRANSPORT's own rejection, which is shaped
 * like an axios one: `error.response.data` is the body the server sent and
 * `error.response.status` the code it sent it with (services/directRun.ts).
 * Until 2026-09-05 this accepted every status and threw a bare
 * `new Error("Error 503: …")` in its place, and a bare Error carries neither —
 * so `blockedReason` could not see a refusal and `generationErrorFor` could not
 * see a cause, and every failure on these surfaces read "Something went wrong.
 * Please try again."
 */
export async function apiPost(path: string, body: Record<string, unknown>): Promise<any> {
  const res = await postStreamedRun(path, body, {
    baseUrl: apiBase(),
    validateStatus: (status) => status >= 200 && status < 300,
  })
  return res.data
}

/**
 * The line that says why nothing came back, brought under the eye — the line of
 * the instrument that ASKED, handed over as its own template ref.
 *
 * It stands at the head of the preparing column (`.lab-prep-err`,
 * docs/ELEMENT_STRUCTURE_REGISTRY.md), and on these three surfaces that column
 * SCROLLS: it is longer than any window, 971 to 1234 px against 469 at
 * 900 x 700. The trigger is in the bar and stands still whatever the column
 * does, so someone who had scrolled down to the step count and then pressed it
 * got the answer at y −171 — above everything that was on the screen (measured
 * 2026-09-05). Putting the line at the head only helps if the column is at its
 * head too.
 *
 * `block: 'nearest'` moves as little as it can: where the line is already
 * readable nothing moves at all, and a column standing at its head is not
 * jogged. It runs after `nextTick` because the sentence is written into the
 * line in the frame after it was set.
 *
 * The ref is what makes it the RIGHT line. Until 2026-09-05 this asked the
 * document for `.lab-prep-err`, and the three instruments of the Crossmodal Lab
 * are kept alive behind one `<KeepAlive>`: a run that failed after someone had
 * switched surfaces scrolled the instrument they were LOOKING at to its own
 * error line. A ref belongs to one component, and a deactivated component's
 * element hangs outside the document, where scrolling it moves nothing.
 */
export async function bringFailureIntoView(line: Ref<HTMLElement | null>): Promise<void> {
  await nextTick()
  line.value?.scrollIntoView({
    block: 'nearest',
    behavior: 'smooth',
  })
}

/** A sound that came back as base64, as something a player can be given. */
export function base64ToDataUrl(b64: string, mime: string): string {
  return `data:${mime};base64,${b64}`
}

/**
 * What a failed run SAID, wherever it said it: the server's own `error` field
 * first — that is the sentence with the cause in it — then the message of the
 * rejection, then a raw string a call site hands over directly. '' where
 * nothing was said at all.
 */
function failureMessageOf(failure: unknown): string {
  if (typeof failure === 'string') return failure.trim()
  const e = failure as {
    response?: { data?: { error?: unknown } }
    message?: unknown
  }
  const said = e?.response?.data?.error
  if (typeof said === 'string' && said.trim()) return said.trim()
  if (typeof e?.message === 'string' && e.message.trim()) return e.message.trim()
  return ''
}

/**
 * The HTTP status a failure carries, where it carries one.
 *
 * The transport shapes its rejection like an axios one, so the code the server
 * answered with stands at `response.status` (services/directRun.ts). A raw
 * string handed over by a call site, and a stream that tore before its terminal
 * frame, carry none — null says so.
 */
function failureStatusOf(failure: unknown): number | null {
  const status = (failure as { response?: { status?: unknown } })?.response?.status
  return typeof status === 'number' ? status : null
}

/**
 * Why a run did not come back, in the reader's language.
 *
 * The reading is the platform's ONE classifier (`classifyError`, which
 * `failureKey` in useGenerationStream.ts switches on as well); a surface
 * matching the same states with regexes of its own drifts away from it. What
 * differs between the two is the REGISTER, not the reading: `failureKey`
 * answers a cell in a comparison, which has room for a short cause, while this
 * line stands in the preparing column and is a sentence.
 *
 * All five outcomes are answered. Until 2026-09-05 two of them were not — a
 * model that is not installed and a text where a picture was asked for both
 * came out as "Something went wrong. Please try again.", the one sentence that
 * is wrong for them: pressing again fails in exactly the same way.
 *
 * Everything the classifier has no sentence for gets the platform's own line
 * with the HTTP STATUS in it, and the status alone. The BODY stays in the log,
 * because what arrives in it is written for whoever reads logs: a Python
 * exception (`Expecting value: line 1 column 1 (char 0)`), an absolute server
 * path out of `uploads_tmp/`, `CUDA out of memory. Tried to allocate 2.00
 * GiB…`, a KeyError naming a model id, or the German sentence `prompt und
 * output_config sind erforderlich` on a Korean, Turkish or Arabic surface.
 * That body stood on the screen as `generationError.withMessage` until
 * 2026-09-05. The status is what the platform's own rule asks a failure to
 * carry, and it is a number in every language.
 *
 * `t` is handed in rather than taken from `useI18n()` here, the way
 * `durationLabel` and `queueWaitLabel` take it in useGenerationStream.ts: this
 * module is called from setup and from handlers, and a composable's injection
 * only holds in the first.
 */
export function generationErrorFor(
  t: (key: string, values?: Record<string, unknown>) => string,
  failure: unknown,
): string {
  const message = failureMessageOf(failure)
  const status = failureStatusOf(failure)
  // The sentence for a cause the classifier has no sentence for: the status
  // where the server sent one, and the platform's plain line where the failure
  // never reached a status at all.
  const unread = () => status === null
    ? t('generationError.unknown')
    : t('generationError.withStatus', { status })
  if (!message) return unread()
  switch (classifyError(message)) {
    case 'busy': return t('generationError.busy')
    case 'offline': return t('generationError.offline')
    case 'missing': return t('generationError.notHere')
    case 'text_not_image': return t('generationError.textNotImage')
    case 'rate_limited': return t('generationError.causeRateLimited')
    case 'repetition': return t('generationError.causeRepetition')
    default: return unread()
  }
}

/**
 * A refusal, as the key of the sentence that says so in the reader's language.
 * '' where the answer is no refusal — the platform's own reasons are German
 * developer strings and are never shown raw.
 *
 * It reads what a run brings back from `/api/schema/pipeline/direct`, where the
 * stage orchestrator marks a refused run `status: 'blocked'` and names the
 * stage that refused. **The cross-aesthetic routes carry no content check at
 * all** — neither devserver/my_app/routes/cross_aesthetic_routes.py, which only
 * forwards, nor gpu_service/routes/cross_aesthetic_routes.py — so nothing they
 * answer can ever be a refusal, and the three instruments that post there no
 * longer ask this question. They asked it until 2026-09-05, which is worse than
 * not asking: a reader that looks like a safety check and can never fire says
 * the check is there.
 */
export function refusalKeyOf(err: unknown): string {
  const reason = blockedReason(err)
  if (!reason) return ''
  // An axios error carries the payload under `response.data`; a streamed
  // `GenerationResult` IS the payload and names the stage `blocked_stage`.
  // Read both, or the picture check's refusal reads as the prompt's.
  type Payload = { stage?: string | number; blocked_stage?: string | number }
  const e = err as Payload & { response?: { data?: Payload } }
  const d = e?.response?.data ?? e
  return safetyBlockKey(reason, d?.stage ?? d?.blocked_stage)
}

/**
 * A number field can be emptied or overtyped, and what is sent has to be a
 * number either way. Every reader of such a field goes through here.
 */
export function clamp(v: unknown, lo: number, hi: number, fallback: number): number {
  const n = Number(v)
  if (!Number.isFinite(n)) return fallback
  return Math.min(hi, Math.max(lo, Math.round(n * 100) / 100))
}

/**
 * A written line put through ONE perspective — the ring in the corner of the
 * field (components/InterceptionPresetOverlay.vue).
 *
 * Streamed, not awaited in one silent POST: the interception is a cloud model
 * writing prose, and the edge in front of this server cuts a request whose
 * origin has sent nothing for about 100 seconds. Every status resolves here,
 * and this reads the outcome from the status — which is why this one keeps
 * `validateStatus: () => true` where `apiPost` above no longer does.
 *
 * Returns the line the perspective wrote, or one of two REASONS it wrote none,
 * so that the surface can say which of them happened. It returned null for both
 * until 2026-09-05, and a ring that spun and stopped in silence was everything a
 * participant got.
 */
export type InterceptionOutcome =
  /** `structured` where the answer was not a string (a two-part prompt), written as JSON. */
  | { written: string; structured?: true }
  /** The safety check refused the text: the KEY of the sentence that says so, the
   *  stage that refused where the answer names one, and the reason as the server
   *  wrote it (German; for the platform's own block banner, never for the line). */
  | { refusedKey: string; blockedAtStage?: number; reason: string }
  /** The server refused or failed: the status it answered with, and what it
   *  said where it said anything (the route's own `error`). */
  | { failed: number; said?: string }
  /** The server answered, and the answer carried no written line. */
  | { empty: true }

/**
 * A refusal of the written line, as the KEY of the sentence that says so in the
 * reader's language. Null where the answer is no refusal.
 *
 * Unlike `/api/cross_aesthetic/*`, `/api/schema/pipeline/stage2` IS checked:
 * Stage 1 runs over the text before any model writes on it, and a refusal comes
 * back 403 with `{success: false, error: <the German reason>, blocked_at_stage:
 * 1}` (devserver/my_app/routes/schema_pipeline_routes.py). Until 2026-09-05
 * every status past 400 was read as a failure here, so a participant whose text
 * the check refused read "Nothing came back from the perspective (403)." and
 * was never told that it had been refused, in any language. The other spelling
 * the platform uses for a block (`status: 'blocked'` beside `reason`) is read
 * as well, so a payload of either shape arrives.
 *
 * The reason itself stays out of sight: the backend writes those sentences in
 * German and only in German, and two of them are developer strings that would
 * put the matched terms back on the screen. `safetyBlockKey` says which of the
 * sentences the platform has for a refusal this one is.
 */
type Refusal = Extract<InterceptionOutcome, { refusedKey: string }>

function refusalOf(data: unknown): Refusal | null {
  const carried = blockedReason(data)
  const d = data as { blocked_at_stage?: unknown; error?: unknown; stage?: string | number }
  const blockedAtStage = typeof d?.blocked_at_stage === 'number' ? d.blocked_at_stage : undefined
  if (carried) return { refusedKey: safetyBlockKey(carried, d?.stage), blockedAtStage, reason: carried }
  if (d?.blocked_at_stage === undefined || d?.blocked_at_stage === null) return null
  const reason = typeof d.error === 'string' ? d.error : ''
  return { refusedKey: safetyBlockKey(reason, d.blocked_at_stage as number), blockedAtStage, reason }
}

export async function interceptPrompt(
  schema: string,
  text: string,
  deviceId: string | null,
  extra: { userLanguage?: string; skipOptimization?: boolean } = {},
): Promise<InterceptionOutcome> {
  // `skipOptimization`: the interception alone, no adaptation to a medium.
  // The comparison surfaces run the passthrough perspective this way as
  // their stage-2 gate; a refusal arrives as the block it is.
  const res = await postStreamedRun('/api/schema/pipeline/stage2', {
    schema,
    input_text: text,
    ...(deviceId ? { device_id: deviceId } : {}),
    ...(extra.userLanguage ? { user_language: extra.userLanguage } : {}),
    ...(extra.skipOptimization ? { skip_optimization: true } : {}),
  }, { baseUrl: apiBase(), validateStatus: () => true })
  const data = res.data
  // A refusal before a failure: it comes with a status past 400 as well, and
  // reading it as a failure is what silenced it.
  const refused = refusalOf(data)
  if (refused) return refused
  if (res.status >= 400) {
    const said = typeof data?.error === 'string' ? data.error.trim() : ''
    return said ? { failed: res.status, said } : { failed: res.status }
  }
  const result = data?.interception_result || data?.stage2_result
  if (!data?.success || !result) return { empty: true }
  return typeof result === 'string' ? { written: result } : { written: JSON.stringify(result), structured: true }
}

/**
 * The sentence for an outcome that wrote nothing, in the reader's language:
 * the refusal's own sentence, the failure with its status, or the empty
 * answer. Every ring that calls `interceptPrompt` puts this on the line under
 * its field, so the four outcomes read the same on every surface.
 */
export function perspectiveFailureText(
  t: (key: string, values?: Record<string, unknown>) => string,
  outcome: Exclude<InterceptionOutcome, { written: string }>,
): string {
  if ('refusedKey' in outcome) return t(outcome.refusedKey)
  // The server's own reason where it gave one (the voice comparison showed it
  // until the rings were consolidated on 2026-10-10); the status alone where
  // it said nothing.
  if ('failed' in outcome) return outcome.said || t('perspective.failed', { status: outcome.failed })
  return t('perspective.empty')
}
