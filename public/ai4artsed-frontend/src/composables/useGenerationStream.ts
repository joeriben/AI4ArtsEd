/**
 * useGenerationStream - SSE-based generation with real-time badge updates
 *
 * Provides streaming generation with stage-by-stage events.
 * Used by text_transformation, image_transformation, multi_image_transformation.
 *
 * Events from backend:
 * - connected: Initial connection established
 * - stage3_start: Translation + Safety check starting
 * - stage3_complete: {safe, was_translated} - triggers badges
 * - blocked: Content blocked by safety (aborts)
 * - queue_position: {position, active, wait_s} - queue transparency
 * - stage4_start: Media generation starting
 * - cancelled: Generation was cancelled (from another tab)
 * - complete: {media_output, run_id, loras, lora_triggers, was_translated}
 * - error: Error occurred
 */

import { ref, onUnmounted } from 'vue'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import i18n from '@/i18n'
import { isOperationalReason } from './useMaterialIntake'
import { clearRunPlace, noteRunPlace } from './useRunPlace'

export interface GenerationParams {
  prompt: string
  output_config: string
  seed?: number | null
  input_text?: string
  context_prompt?: string
  interception_result?: string
  interception_config?: string
  run_id?: string | null
  device_id?: string
  input_image?: string | null
  input_image1?: string | null
  input_image2?: string | null
  input_image3?: string | null
  alpha_factor?: number | null

  // Comparison mode — skip Stage 3 translation (send prompt raw to model)
  skip_stage3_translation?: boolean

  // x2x flow — model always gets the English translation (the flow has no translate button)
  force_translation?: boolean

  /**
   * The second text of a model that reads two, as it was written: the style
   * tags of a HeartMuLa song beside its lyrics. The server takes it only for
   * a config that reads two texts, checks both as written and hands neither
   * to the model translated, a forced translation notwithstanding. Sent when
   * empty too: with no style the chunk reads the lyrics as its tags and
   * sings no lyrics.
   */
  secondary_text?: string

  /**
   * The LoRA tiles in the Flow's ring, `[{name, strength}]` with the file as
   * name and the strength as the model reads it (0.7 for 70 %). Resolved at
   * the register on the server and applied where the config's workflow loads
   * them; their trigger words go in front of the prompt there, after Stage 3.
   */
  loras?: Array<{ name: string; strength: number }>
  /**
   * The course the register is asked for, where the session's own binding
   * does not say: an educator leads several, and the one the client is in
   * (labAuth.activeCourseId) is the one whose adapters the run may load. A
   * participant's course is fixed on the server and this is ignored there.
   */
  course_id?: number | null

  // Source tagging + comparison group linking
  source_view?: string
  comparison_group_id?: string
  comparison_language?: string
  comparison_original_prompt?: string

  // Generation parameters (optional, ignored if config doesn't support them)
  width?: number
  height?: number
  steps?: number
  cfg?: number
  negative_prompt?: string
  sampler_name?: string
  scheduler?: string
  denoise?: number
}

export type GenerationErrorType =
  | 'busy'
  | 'offline'
  | 'missing'
  | 'text_not_image'
  | 'rate_limited'
  | 'repetition'
  | 'unknown'

/**
 * What the card said about itself when it turned a run away.
 *
 * The gate keeps four refusals apart — a long hold (a training), a queue that
 * is full, a wait that ran out, memory that stayed short — and the surface
 * chooses its sentence from `reason`, never from the message text. Read off
 * the text, all four said "queue full", and so did the six hours a LoRA
 * training once held the card.
 *
 * `remaining_s` is present only where it was measured. Absent means unknown,
 * and the surface has a sentence for that; a zero would read as "any moment".
 */
export interface BusyNote {
  reason: 'long_hold' | 'queue_full' | 'wait_timeout' | 'no_memory' | 'busy'
  holder_kind?: string
  waiting?: number
  remaining_s?: number
}

export interface GenerationResult {
  /**
   * `busy` is not an error and carries no message. The device already holds a
   * run; that is a state of the machine, not something the learner did wrong,
   * and it is answered by showing what is — never by a sentence that arrives
   * after a press and explains the press away.
   */
  status: 'success' | 'blocked' | 'error' | 'cancelled' | 'busy'
  media_output?: {
    media_type: string
    url: string
    run_id: string
    index: number
    seed: number
    code?: string
    mesh_url?: string
    thumbnail_url?: string
  }
  run_id?: string
  /** What the register applied: the config's own adapters and the requested ones, as `[{name, strength}]`. */
  loras?: Array<{ name: string; strength: number }>
  /** The trigger tags the register put in front of the prompt, in their order. */
  lora_triggers?: string[]
  was_translated?: boolean
  error?: string
  errorType?: GenerationErrorType
  /** Present when the card refused the run — see BusyNote. */
  busy?: BusyNote
  /** For `busy`: what the run already going on this device is making. */
  busyMedium?: string
  blocked_reason?: string
  /**
   * Which stage refused, as the backend marks it (`vlm_input`, `vlm_safety`,
   * or a number). `safetyBlockKey` reads it, and for the image check it is
   * the ONLY way there: `VLM_CONTENT_BLOCK_MESSAGE` carries none of the words
   * the reason-matching looks for, so a refused PICTURE without the stage
   * reads as a refused PROMPT and tells the reader to rewrite a line the
   * platform itself just called fine.
   */
  blocked_stage?: string | number
  found_terms?: string[]
}

/**
 * Classify backend error messages into typed categories for i18n display.
 *
 * `missing` is the one class that must never be answered with "try again": a
 * chunk, a workflow or a config that is not on this installation is a state of
 * the installation, and every further press fails in the same way. That is why
 * it stands apart from `offline`, where the service is there and silent — the
 * two ask different things of whoever is looking at the box.
 *
 * Exported because the classifier must stay single: a view that matched the
 * same strings again with its own regexes would drift away from this one.
 */
/**
 * Which of the platform's short cause sentences a run that brought back no
 * medium is. It stands beside `classifyError` for the same reason that one
 * exists: a second surface matching the same states with its own words would
 * drift away from this one, and a cell in a comparison has room for a cause,
 * not for a paragraph.
 *
 * `cancelled` and `busy` are states of the machine and end a run just as
 * surely as an error does; a row that leaves their cells empty invites a
 * count that is quietly short.
 */
export function failureKey(status: string, message: string, busy?: BusyNote): string {
  if (status === 'cancelled') return 'generationError.causeAborted'
  // The run this device already has. A cell whose column names the medium
  // needs no second naming of it, so this is the plain wording.
  if (status === 'busy') return 'mediaInput.deviceBusyPlain'
  if (busy) return busyCauseKey(busy)
  switch (classifyError(message)) {
    case 'busy': return 'generationError.causeQueueFull'
    case 'offline': return 'generationError.causeUnreachable'
    case 'missing': return 'generationError.causeNoModel'
    case 'text_not_image': return 'generationError.textNotImage'
    case 'rate_limited': return 'generationError.causeRateLimited'
    case 'repetition': return 'generationError.causeRepetition'
    default: return 'generationError.unknown'
  }
}

/**
 * Which cause sentence a refusal from the card is.
 *
 * One place, because two surfaces show it: the flow's box states the cause and
 * an instruction under it, a comparison cell has room for the cause alone.
 *
 * "Queue full" is said ONLY where the queue is in fact full. A long hold by
 * something other than a training, and a refusal that names no reason at all,
 * get the neutral sentence: the card is taken, and that is everything that is
 * known. Borrowing the queue's sentence for them is how the platform came to
 * tell a visitor the queue was full while a single training sat on the card
 * for six and a half hours with nobody else waiting.
 */
export function busyCauseKey(busy: BusyNote): string {
  switch (busy.reason) {
    case 'long_hold':
      return busy.holder_kind === 'lora_training'
        ? 'generationError.causeTraining'
        : 'generationError.causeBusy'
    case 'queue_full': return 'generationError.causeQueueFull'
    case 'wait_timeout': return 'generationError.causeWaited'
    case 'no_memory': return 'generationError.causeMemory'
    default: return 'generationError.causeBusy'
  }
}

/**
 * A measured wait, split into the unit it should be read in.
 *
 * Rounded to five seconds below a minute, to whole minutes above it, and to
 * hours past an hour and a half — a training holds the card for hours, and a
 * count of 130 minutes stops being read as a duration. The rounding decides
 * the branch, not the raw value: otherwise 88 seconds reads "about 90 s" and
 * 90 seconds reads "about 2 min", two names for one duration.
 *
 * Null below five seconds and for anything unmeasured: an invented number is
 * worse than none.
 */
export function waitParts(s: number | null | undefined): { unit: 's' | 'min' | 'h'; n: number; m?: number } | null {
  if (s === null || s === undefined || !isFinite(s) || s < 5) return null
  const r = Math.round(s / 5) * 5
  if (r < 60) return { unit: 's', n: r }
  const min = Math.max(1, Math.round(s / 60))
  if (min < 90) return { unit: 'min', n: min }
  const rounded = Math.round(min / 5) * 5
  return { unit: 'h', n: Math.floor(rounded / 60), m: rounded % 60 }
}

/**
 * The same span as bare number and unit, for the places that put it inside a
 * sentence of their own. A whole hour is said as one — "2 h 0 min" is a number
 * nobody writes.
 */
export function durationLabel(t: (k: string, v?: any) => string, s: number | null | undefined): string {
  const p = waitParts(s)
  if (!p) return ''
  if (p.unit === 'h') {
    return p.m ? t('x2xFlow.durH', { h: p.n, m: p.m }) : t('x2xFlow.durHOnly', { h: p.n })
  }
  return p.unit === 's' ? t('x2xFlow.durS', { n: p.n }) : t('x2xFlow.durMin', { n: p.n })
}

/**
 * How long until this run reaches the card, in words — empty while the gate has
 * no measurement for what is queued.
 */
export function queueWaitLabel(t: (k: string, v?: any) => string, s: number | null | undefined): string {
  const p = waitParts(s)
  if (!p) return ''
  if (p.unit === 'h') {
    return p.m
      ? t('x2xFlow.queueWaitHours', { hours: p.n, minutes: p.m })
      : t('x2xFlow.queueWaitHoursOnly', { hours: p.n })
  }
  return p.unit === 's'
    ? t('x2xFlow.queueWaitSeconds', { seconds: p.n })
    : t('x2xFlow.queueWaitMinutes', { minutes: p.n })
}

export function classifyError(message: string): GenerationErrorType {
  // A cloud model's provider turning the request away for the moment. The
  // streaming client passes the provider's status on as "API Error: 429"
  // (devserver/my_app/services/openai_style_stream.py), and the body behind
  // it says "rate-limited upstream" (Mammouth, OpenRouter, Mistral).
  if (/API Error: 429|rate.?limit/i.test(message)) return 'rate_limited'
  // The repetition guard at the local generation loop stopped a model that
  // kept writing the same passage (comfyui_nodes/ai4artsed_comfyui/
  // _repetition_guard.py). The node gives "repetition" as its finish reason
  // (_local_llm.py), and the interception engine writes that into the error
  // it raises for the empty answer (schemas/engine/prompt_interception_engine.py).
  if (/finish_reason=repetition/.test(message)) return 'repetition'
  if (/queue full|device.busy|previous.*generation.*running/i.test(message)) return 'busy'
  // `could not be reached` is the submission's own wording for a ComfyUI that
  // never answered; `cannot connect to host` is what aiohttp puts inside it.
  if (
    /not available|not reachable|could not be reached|cannot connect to host|connection refused|timeout/i.test(
      message
    )
  )
    return 'offline'
  if (
    // `not in list` is ComfyUI's own wording, arriving through the
    // submission's refusal: a file it was asked for (checkpoint, LoRA, VAE)
    // that this installation does not have. Its sibling — a custom node that
    // is not installed — says "Node 'X' not found. The custom node may not be
    // installed.", which `not found` above already catches. Both are states of
    // the installation, so both belong here rather than in `unknown`, whose
    // answer is "try again"; pressing again installs nothing.
    /not found|not implemented|nicht implementiert|no workflow|no output_chunk|missing execute|failed to load python chunk|not in list/i.test(
      message
    )
  )
    return 'missing'
  if (/returned text instead of an image/i.test(message)) return 'text_not_image'
  // A request that never reached the server: `Failed to fetch` (Chromium),
  // `NetworkError when attempting to fetch` (Firefox), `Load failed` (Safari),
  // and the torn stream's own `Network error` (services/directRun.ts). The
  // service cannot be reached, which is what `offline` says; until the second
  // review of 2026-10-10 this read as "something went wrong, try again".
  if (/failed to fetch|networkerror|network error|load failed/i.test(message)) return 'offline'
  return 'unknown'
}

/**
 * The raw reason a blocked run carries — for CLASSIFYING it, never for showing
 * it. The backend writes these sentences in German and only in German
 * (`utils/vlm_safety.py`, `schemas/engine/stage_orchestrator.py`: the
 * `user_language` a run sends steers term matching, not the wording), and two
 * of the Stage-3 ones are developer strings that would put the matched
 * forbidden terms back on the screen. Put the result through
 * `safetyBlockKey()` and render THAT.
 *
 * Takes either an axios error or the payload itself, and reads both spellings
 * the platform uses: the route's `reason` and the stream's `blocked_reason`.
 */
export function blockedReason(e: any): string | null {
  const d = e?.response?.data ?? e
  if (!d || typeof d !== 'object' || d.status !== 'blocked') return null
  for (const key of ['reason', 'blocked_reason']) {
    const v = d[key]
    if (typeof v === 'string' && v.trim()) return v
  }
  return null
}

/**
 * Which sentence a block event gets — the reading every surface uses.
 *
 * Take this one wherever a block ARRIVES, and `safetyBlockKey` only where there
 * is nothing but a reason. The difference is the event's `operational`: the
 * surface that watched its own check fail states the case as a fact, and no
 * sentence match can reach it, because the client has no German reason to match
 * and a translated one belongs to no language the matcher knows.
 */
export function safetyBlockKeyForEvent(
  event: { reason?: string | null; stage?: string | number | null; operational?: boolean },
): string {
  // The carried case first: a check that could not be carried out is stated by
  // the surface that saw it fail, and a sentence match cannot reach it — the
  // client has no German reason to match, and a translated one belongs to no
  // language the matcher knows. Safety checks never fail open; the corollary
  // is that a fault must not be read back as a content rating.
  if (event.operational) return 'safetyBlocked.systemUnavailable'
  return safetyBlockKey(event.reason, event.stage)
}

/**
 * Which of the platform's `safetyBlocked.*` sentences a reason is, so that the
 * reader gets it in their own language. The mapping is the one the companion
 * has used since the safety wording existed (`components/ChatOverlay.vue`);
 * it lives here so both read the same block the same way.
 *
 * `stage` is the backend's stage marker where a run has one ('vlm_input',
 * 'vlm_safety', or a number). Pass it: without the stage an image the platform
 * refused reads as a refused prompt, and the reader is told to reword what was
 * never the subject.
 */
export function safetyBlockKey(reason: string | null | undefined, stage?: string | number | null): string {
  const r = reason || ''
  // Operational failure first, before any stage-keyed branch: a fail-closed
  // block whose cause is a technical fault must never read as a content rating.
  // The markers are the intake's, so one list answers this question in both
  // places — the quick route's DSGVO branch says „Sicherheitsprüfung nicht
  // verfügbar" under a DSGVO prefix, and read by the prefix it accused the
  // writer of naming a person while the check had not run at all.
  if (isOperationalReason(r)) return 'safetyBlocked.systemUnavailable'
  if (stage === 'vlm_input') return 'safetyBlocked.inputImage'
  if (r.includes('VLM') || stage === 'vlm_safety') return 'safetyBlocked.vlm'
  if (r.includes('§86a')) return 'safetyBlocked.para86a'
  if (r.includes('DSGVO') || r.includes('Persönliche Daten')) return 'safetyBlocked.dsgvo'
  if (r.includes('Kids-Filter') || r.includes('Kinder-Schutzfilter')) return 'safetyBlocked.kids'
  if (r.includes('Youth-Filter') || r.includes('Jugendschutzfilter')) return 'safetyBlocked.youth'
  return 'safetyBlocked.generic'
}

/**
 * Read one SSE payload.
 *
 * A throw inside a listener skips everything that stands after it in that
 * listener — the close, the state reset, the resolve. The promise then never
 * settles and `isExecuting` stays true for the rest of the session: the start
 * button of that page says "generating" forever, with nothing running. One
 * malformed payload must not be able to do that, so an unreadable one comes
 * back as null and every listener decides what that means for it.
 */
function ssePayload(e: MessageEvent): any | null {
  try {
    return JSON.parse(e.data)
  } catch {
    console.error('[GENERATION-STREAM] Unreadable payload:', e.data)
    return null
  }
}

export function useGenerationStream() {
  const safetyStore = useSafetyEventStore()

  // Badge states
  // showTranslatedStamp: read by the flow's run box (x2x_flow.vue).
  const showTranslatedStamp = ref(false)
  const safetyChecks = ref<string[]>([])

  // Progress state
  const generationProgress = ref(0)
  const previewImage = ref<string | null>(null)
  const isExecuting = ref(false)
  const currentStage = ref<'idle' | 'stage3' | 'stage4' | 'complete'>('idle')
  /** The model stage 3 translates and checks with, as the backend reports it. */
  const stage3Model = ref('')
  const modelMeta = ref<Record<string, any> | null>(null)
  const stage4DurationMs = ref(0)
  let _stage4StartTime = 0

  // Encoding transparency (SD3.5 process visibility)
  const encodingInfo = ref<Record<string, any> | null>(null)
  // The denoising step counter, kept as numbers and not only as a percentage:
  // a view can only name the phase it is in (encoding / denoising / decoding)
  // if it knows whether the steps have started and whether they are done.
  const genStep = ref(0)
  const genTotalSteps = ref(0)

  // Queue transparency + per-device lock
  const queuePosition = ref(0)
  // What the run already going on this device is making, so the line about it
  // can name it. Empty when the backend did not say.
  const busyMedium = ref('')
  // How long until this run reaches the card, in seconds. null when the
  // gate has no measurement for the models in the queue — a number here
  // would be invented, and a wrong minute is worse than none.
  const queueWaitS = ref<number | null>(null)
  const deviceBusy = ref(false)
  const preChecking = ref(false)
  let _busyPollInterval: ReturnType<typeof setInterval> | null = null

  /**
   * Clean up polling on component unmount.
   *
   * The open stream is deliberately NOT closed here. Leaving a page while a
   * generation runs is allowed, and closing the stream would reach the backend
   * as a client disconnect: it releases the slot and stops the run before the
   * piece is recorded. The run belongs to the learner, not to the page they
   * happen to be looking at — it finishes, and it lands in the gallery.
   */
  onUnmounted(() => {
    if (_busyPollInterval) {
      clearInterval(_busyPollInterval)
      _busyPollInterval = null
    }
  })

  /**
   * Build SSE URL with query parameters
   */
  function buildSSEUrl(baseUrl: string, params: GenerationParams): string {
    const queryParams = new URLSearchParams()

    // Required params
    queryParams.set('prompt', params.prompt)
    queryParams.set('output_config', params.output_config)
    queryParams.set('enable_streaming', 'true')

    // Optional params
    if (params.seed !== null && params.seed !== undefined) {
      queryParams.set('seed', String(params.seed))
    }
    if (params.input_text) {
      queryParams.set('input_text', params.input_text)
    }
    if (params.context_prompt) {
      queryParams.set('context_prompt', params.context_prompt)
    }
    if (params.interception_result) {
      queryParams.set('interception_result', params.interception_result)
    }
    if (params.interception_config) {
      queryParams.set('interception_config', params.interception_config)
    }
    if (params.run_id) {
      queryParams.set('run_id', params.run_id)
    }
    if (params.device_id) {
      queryParams.set('device_id', params.device_id)
    }
    if (params.input_image) {
      queryParams.set('input_image', params.input_image)
    }
    if (params.input_image1) {
      queryParams.set('input_image1', params.input_image1)
    }
    if (params.input_image2) {
      queryParams.set('input_image2', params.input_image2)
    }
    if (params.input_image3) {
      queryParams.set('input_image3', params.input_image3)
    }
    if (params.alpha_factor !== null && params.alpha_factor !== undefined) {
      queryParams.set('alpha_factor', String(params.alpha_factor))
    }

    // Comparison mode
    if (params.skip_stage3_translation) {
      queryParams.set('skip_stage3_translation', 'true')
    }

    // translation-for-generation on every level
    if (params.force_translation) {
      queryParams.set('force_translation', 'true')
    }

    if (params.secondary_text !== undefined && params.secondary_text !== null) {
      queryParams.set('secondary_text', params.secondary_text)
    }

    // The LoRAs of the ring, as one JSON list: an EventSource has no body.
    if (params.loras && params.loras.length) {
      queryParams.set('loras', JSON.stringify(params.loras))
    }
    if (params.course_id !== null && params.course_id !== undefined) {
      queryParams.set('course_id', String(params.course_id))
    }

    // Source tagging + comparison group linking
    if (params.source_view) {
      queryParams.set('source_view', params.source_view)
    }
    if (params.comparison_group_id) {
      queryParams.set('comparison_group_id', params.comparison_group_id)
    }
    if (params.comparison_language) {
      queryParams.set('comparison_language', params.comparison_language)
    }
    if (params.comparison_original_prompt) {
      queryParams.set('comparison_original_prompt', params.comparison_original_prompt)
    }

    // Generation parameters (optional)
    if (params.width !== undefined) {
      queryParams.set('width', String(params.width))
    }
    if (params.height !== undefined) {
      queryParams.set('height', String(params.height))
    }
    if (params.steps !== undefined) {
      queryParams.set('steps', String(params.steps))
    }
    if (params.cfg !== undefined) {
      queryParams.set('cfg', String(params.cfg))
    }
    if (params.negative_prompt) {
      queryParams.set('negative_prompt', params.negative_prompt)
    }
    if (params.sampler_name) {
      queryParams.set('sampler_name', params.sampler_name)
    }
    if (params.scheduler) {
      queryParams.set('scheduler', params.scheduler)
    }
    if (params.denoise !== undefined) {
      queryParams.set('denoise', String(params.denoise))
    }

    return `${baseUrl}?${queryParams.toString()}`
  }

  /**
   * Execute generation with SSE streaming
   */
  async function executeWithStreaming(params: GenerationParams): Promise<GenerationResult> {
    // Determine base URL based on environment
    const baseUrl = '/api/schema/pipeline/generation'

    const url = buildSSEUrl(baseUrl, params)
    console.log('[GENERATION-STREAM] Starting SSE connection:', url.substring(0, 100) + '...')

    isExecuting.value = true
    // This device's run is now ours. Anything the last pre-check knew about a
    // foreign one is stale from here on; the backend says so again if it isn't.
    deviceBusy.value = false
    currentStage.value = 'stage3'
    generationProgress.value = 0
    previewImage.value = null
    modelMeta.value = null
    queuePosition.value = 0
    queueWaitS.value = null

    // Every way out of a run ends its queue line with it. Without this the
    // last thing the gate said stays on screen beside the finished picture —
    // "queue position: 3", a wait of two minutes — for a run that is over.
    const endRun = () => {
      isExecuting.value = false
      queuePosition.value = 0
      queueWaitS.value = null
      // And with it the model line: blocked, cancelled, complete and error all
      // come through here, and none of them leaves a model at work. Only THIS
      // run's line — a page fires short calls beside its long ones, and each
      // of them ends first (composables/useRunPlace.ts).
      clearRunPlace(thisRun)
    }

    // This run's identity for the model line: it may take away only what it
    // put there (composables/useRunPlace.ts).
    const thisRun = {}

    return new Promise((resolve, reject) => {
      const eventSource = new EventSource(url)

      eventSource.addEventListener('connected', (e: MessageEvent) => {
        console.log('[GENERATION-STREAM] Connected:', ssePayload(e))
      })

      // Which model the server has this run at, written into its heartbeat
      // (devserver/my_app/services/streaming_response.py). It arrives within
      // two seconds of the dispatch and names what is RUNNING, where the
      // finished answer could only name what has run.
      //
      // Of the eleven events this stream speaks, this is the only one that
      // touches the line, and `endRun` is the only thing that takes it away.
      // The others deliberately leave it alone: `connected`, `stage3_start`,
      // `stage3_complete`, `queue_position`, `stage4_start`, `encoding_info`
      // and `generation_progress` are all statements about a STAGE, and a stage
      // is not a model. Reading them as one is what broke this the first time
      // round: `queue_position` goes out while the run is drawing — the gate
      // answers "nought ahead" and that is still an answer — so clearing on it
      // emptied the bar in the middle of the very generation it was naming.
      eventSource.addEventListener('model_place', (e: MessageEvent) => {
        noteRunPlace(ssePayload(e), thisRun)
      })

      eventSource.addEventListener('stage3_start', (e: MessageEvent) => {
        const data = ssePayload(e)
        console.log('[GENERATION-STREAM] Stage 3 started (Translation + Safety)')
        currentStage.value = 'stage3'
        // Which model translates and checks. The two steps before this one name
        // theirs; this one used to stand there as the only unattributed station.
        if (data && typeof data.model === 'string') stage3Model.value = data.model
      })

      eventSource.addEventListener('stage3_complete', (e: MessageEvent) => {
        const data = ssePayload(e)
        if (!data) return
        console.log('[GENERATION-STREAM] Stage 3 complete:', data)

        // Merge Stage 3 checks into safety badges
        if (data.checks_passed) {
          safetyChecks.value = [...safetyChecks.value, ...data.checks_passed]
        }

        // Trigger legacy badges
        if (data.was_translated) {
          showTranslatedStamp.value = true
        }
      })

      eventSource.addEventListener('blocked', (e: MessageEvent) => {
        // A block ends the run whether or not its reason can be read.
        const data = ssePayload(e) ?? {}
        console.log('[GENERATION-STREAM] Blocked:', data)
        // Centralized: report block to safetyStore (Trashy integration)
        safetyStore.reportBlock(data.stage || 3, data.reason || 'Inhalt blockiert', data.found_terms || [], data.vlm_description)
        eventSource.close()
        endRun()
        currentStage.value = 'idle'
        resolve({
          status: 'blocked',
          blocked_reason: data.reason,
          blocked_stage: data.stage,
          found_terms: data.found_terms || []
        })
      })

      // Queue transparency: how many generations are ahead
      eventSource.addEventListener('queue_position', (e: MessageEvent) => {
        const data = ssePayload(e)
        if (!data) return
        console.log('[GENERATION-STREAM] Queue position:', data)
        queuePosition.value = data.position
        queueWaitS.value = (typeof data.wait_s === 'number') ? data.wait_s : null
      })

      eventSource.addEventListener('stage4_start', (e: MessageEvent) => {
        const data = ssePayload(e) ?? {}
        console.log('[GENERATION-STREAM] Stage 4 started (Media Generation)')
        currentStage.value = 'stage4'
        generationProgress.value = 0
        previewImage.value = null
        genStep.value = 0
        genTotalSteps.value = 0
        modelMeta.value = data.model_meta || null
        _stage4StartTime = Date.now()
      })

      eventSource.addEventListener('encoding_info', (e: MessageEvent) => {
        const data = ssePayload(e)
        if (!data) return
        console.log('[GENERATION-STREAM] Encoding info received:', Object.keys(data))
        encodingInfo.value = data
      })

      eventSource.addEventListener('generation_progress', (e: MessageEvent) => {
        const data = ssePayload(e)
        if (!data) return
        generationProgress.value = data.percent
        // The card is drawing THIS run — whatever place in the queue it last
        // held is over. Nothing else clears it here: once steps arrive every
        // few hundred milliseconds the server's idle heartbeat, which is where
        // the queue line is refreshed, never comes round again, and the last
        // position stayed on screen through the whole generation.
        queuePosition.value = 0
        queueWaitS.value = null
        if (typeof data.step === 'number') genStep.value = data.step
        if (typeof data.total_steps === 'number') genTotalSteps.value = data.total_steps
        if (data.preview) {
          previewImage.value = data.preview
        }
      })

      // Cancelled: generation was cancelled (from another tab or cancel button)
      eventSource.addEventListener('cancelled', (e: MessageEvent) => {
        console.log('[GENERATION-STREAM] Cancelled:', ssePayload(e))
        eventSource.close()
        endRun()
        currentStage.value = 'idle'
        resolve({ status: 'cancelled' })
      })

      eventSource.addEventListener('complete', (e: MessageEvent) => {
        const data = ssePayload(e)
        console.log('[GENERATION-STREAM] Complete:', data)
        eventSource.close()
        endRun()
        if (!data) {
          // The run finished, but what it finished with did not arrive readable.
          // It ends as an error, not as a run that never comes back. No message
          // of its own: every caller already has a translated one for this.
          currentStage.value = 'idle'
          resolve({ status: 'error', error: '', errorType: 'unknown' })
          return
        }
        currentStage.value = 'complete'
        generationProgress.value = 100
        stage4DurationMs.value = _stage4StartTime ? Date.now() - _stage4StartTime : 0
        resolve({
          status: 'success',
          media_output: data.media_output,
          run_id: data.run_id,
          loras: data.loras || [],
          lora_triggers: data.lora_triggers || [],
          was_translated: data.was_translated
        })
      })

      eventSource.addEventListener('error', (e: MessageEvent) => {
        // Check if it's a custom error event or connection error
        if (e.data) {
          const data = ssePayload(e) ?? {}
          console.error('[GENERATION-STREAM] Error event:', data)
          eventSource.close()
          endRun()
          currentStage.value = 'idle'
          if (data.code === 'device_busy') {
            busyMedium.value = data.media_type || ''
            // Not an error and not a message: the device already holds a run.
            // The control that offered this press learns the state and shows
            // it; nobody gets told off for having pressed.
            deviceBusy.value = true
            // And it clears itself: the poll asks the backend every 3 s and
            // stops when the other run is done. This flag is never left for
            // somebody else to reset — that is how the mode menu died.
            if (params.device_id) void checkDeviceActive(params.device_id)
            resolve({ status: 'busy' })
            return
          }
          const errorMsg = data.message || 'Unknown error'
          // The state comes from the backend where the backend named it, and
          // only from the message where it did not.
          const busy: BusyNote | undefined =
            data.code === 'gpu_busy' && data.busy ? (data.busy as BusyNote) : undefined
          const errorType = busy ? 'busy' : classifyError(errorMsg)
          resolve({
            status: 'error',
            // Backend messages are English; this one actionable case gets the translated wording
            error: errorType === 'text_not_image'
              ? (i18n.global.t('generationError.textNotImage') as string)
              : errorMsg,
            errorType,
            busy
          })
        } else {
          // Connection error
          console.error('[GENERATION-STREAM] Connection error')
          eventSource.close()
          endRun()
          currentStage.value = 'idle'
          reject(new Error('SSE connection failed'))
        }
      })

      // Handle native EventSource errors
      eventSource.onerror = () => {
        if (eventSource.readyState === EventSource.CLOSED) {
          // Normal close, ignore
          return
        }
        console.error('[GENERATION-STREAM] EventSource error')
        eventSource.close()
        endRun()
        currentStage.value = 'idle'
        reject(new Error('SSE connection error'))
      }
    })
  }

  /**
   * Pre-check: is this device currently generating? (REST call)
   */
  async function checkDeviceActive(deviceId: string): Promise<void> {
    preChecking.value = true
    try {
      const baseUrl = ''
      const res = await fetch(`${baseUrl}/api/schema/pipeline/generation-active?device_id=${encodeURIComponent(deviceId)}`)
      const data = await res.json()
      deviceBusy.value = data.active
      busyMedium.value = (data.active && data.media_type) || ''
      queuePosition.value = data.queue_total || 0

      // Poll while busy — auto-clears when generation finishes
      if (data.active && !_busyPollInterval) {
        _busyPollInterval = setInterval(async () => {
          try {
            const r = await fetch(`${baseUrl}/api/schema/pipeline/generation-active?device_id=${encodeURIComponent(deviceId)}`)
            const d = await r.json()
            deviceBusy.value = d.active
            busyMedium.value = (d.active && d.media_type) || ''
            if (!d.active && _busyPollInterval) {
              clearInterval(_busyPollInterval)
              _busyPollInterval = null
            }
          } catch { /* ignore polling errors */ }
        }, 3000)
      } else if (!data.active && _busyPollInterval) {
        clearInterval(_busyPollInterval)
        _busyPollInterval = null
      }
    } catch (e) {
      console.error('[GENERATION-STREAM] Pre-check failed:', e)
      deviceBusy.value = false
    } finally {
      preChecking.value = false
    }
  }

  /**
   * Cancel a running generation for this device (REST call)
   */
  async function cancelGeneration(deviceId: string): Promise<boolean> {
    try {
      const baseUrl = ''
      const res = await fetch(`${baseUrl}/api/schema/pipeline/generation-cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId })
      })
      const data = await res.json()
      if (data.cancelled) {
        deviceBusy.value = false
      }
      return data.cancelled
    } catch (e) {
      console.error('[GENERATION-STREAM] Cancel failed:', e)
      return false
    }
  }

  /**
   * Reset all states for new generation
   */
  function reset() {
    showTranslatedStamp.value = false
    safetyChecks.value = []
    generationProgress.value = 0
    previewImage.value = null
    isExecuting.value = false
    currentStage.value = 'idle'
    stage3Model.value = ''
    modelMeta.value = null
    encodingInfo.value = null
    stage4DurationMs.value = 0
    _stage4StartTime = 0
    genStep.value = 0
    genTotalSteps.value = 0
    queuePosition.value = 0
    queueWaitS.value = null
  }

  return {
    // Badge states
    showTranslatedStamp,
    safetyChecks,

    // Progress states
    generationProgress,
    previewImage,
    isExecuting,
    currentStage,
    stage3Model,
    modelMeta,
    stage4DurationMs,
    encodingInfo,
    genStep,
    genTotalSteps,

    // Queue transparency + per-device lock
    queuePosition,
    queueWaitS,
    deviceBusy,
    busyMedium,
    preChecking,

    // Methods
    executeWithStreaming,
    checkDeviceActive,
    cancelGeneration,
    reset
  }
}
