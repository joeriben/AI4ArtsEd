/**
 * A SERIES over the platform's own central operation: one line, and several
 * rows that differ in exactly one thing — the model that writes, or the
 * perspective that is written with. Everything else is held equal, so that the
 * difference between two rows is the one thing that was varied.
 *
 * Built inside Interception across Models (views/latent_lab/interception_models
 * .vue) on 2026-09-03 and gathered here on 2026-09-04, when the second
 * instrument of the group needed the same run with another row axis
 * (views/latent_lab/perspectives_template.vue). Rule 13: what was word for word
 * the same on both stands here once.
 *
 * What a surface keeps for itself: WHAT its rows are (which model, which
 * perspective), what its heads say, and what it puts in the record beyond the
 * fields below. What is here is the run: two phases, one request at a time.
 *
 * Phase 1 — every row that carries a request has its interception written
 * (POST /api/schema/pipeline/stage2). The platform's Stage 1 gate, the safety
 * prefixes and the reading-volume clause stand exactly as they do for every
 * other request; a text coming back is the proof that the LINE passed the gate.
 *
 * A row may also bring its text WITH it and carry no request: the reference row
 * does, because it is the line as written. Such a row skips phase 1 and goes to
 * phase 2 with what the surface put in it.
 *
 * A row may instead bring its PERSPECTIVE (`request.contextPrompt`, since
 * 2026-09-04): phase 1 then writes it under a text the surface composed rather
 * than under the preset's own. Aesthetic Poles does that — it sets each pole's
 * frame text around the properties IT drew, because the draw belongs to the
 * surface and both poles get the same one. The text travels as `context_prompt`
 * and passes the same gate as every other text. What it does NOT skip is the gate: a press whose
 * writing calls established nothing about the line computes no cell at all, so
 * a surface whose rows are ALL text-only would compute nothing, which is right
 * — there would be nothing that had passed Stage 1.
 *
 * Phase 2 — every cell: the output config's own adaption
 * (POST /api/schema/pipeline/optimize) and the generation from what it wrote.
 * The adaption runs on the platform's configured model for EVERY row, so the
 * rows go to the image model prepared in exactly the same way.
 *
 * The cells are grouped by IMAGE MODEL rather than by row, for the reason
 * Cultural (Un)Known groups its own by model: going the other way round would
 * change the model at every single picture and make the card load and drop the
 * weights once per cell. Where a result lands is untouched by the order — a
 * cell is keyed by its ROW, the output config and the seed.
 */
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDeviceId } from '@/composables/useDeviceId'
import { useModelAvailability } from '@/composables/useModelAvailability'
import { useRasterRun, type RasterCell } from '@/composables/useRasterRun'
import { postStreamedRun } from '@/services/directRun'
import {
  failureKey,
  safetyBlockKey,
  useGenerationStream,
  type GenerationResult,
} from '@/composables/useGenerationStream'
import { STANDARD_SEED } from '@/composables/useSeedAutomatic'
import { apiBase } from '@/services/labApi'

/**
 * The number every picture in these series is made with — THE PLATFORM'S own,
 * the one that stands as the default in the generation chunks themselves and
 * that Cultural (Un)Known and LoRA Explorer compute their rasters with. A
 * series that made up its own would compare its pictures against nothing anybody
 * else can reproduce, and the rows would differ in the draw as well.
 */
export const SERIES_SEED = STANDARD_SEED

/**
 * One term the interception had to look up while writing: the word, the language
 * it was looked up in, and whether an article answered.
 */
export interface WikipediaTerm {
  term: string
  lang: string
  found: boolean
}

/** What the route answers when a model has written its interception. */
export interface Stage2Answer {
  success?: boolean
  interception_result?: string
  stage2_result?: string
  interception_model?: string
  wikipedia_terms?: { term?: string; lang?: string; found?: boolean }[]
  passthrough?: boolean
  error?: string
  /** What a refusal refused FOR, in the route's own vocabulary. */
  cause?: string
  blocked_at_stage?: number
  /**
   * WHICH text the gate refused: `input_text`, the line the visitor wrote, or
   * `context_prompt`, the perspective the surface sent with the row. The two
   * are different facts and are said differently.
   */
  blocked_on?: string
}

/** What the route answers when an output config has adapted a text. */
export interface OptimizeAnswer {
  success?: boolean
  optimized_prompt?: string
  error?: string
}

export interface RowResult {
  text: string
  /** The model that ACTUALLY wrote it, as the route reports it back. */
  dispatched: string
  wikipediaTerms: WikipediaTerm[]
  /**
   * The run handed the prompt through UNCHANGED: a preset with an empty context
   * and nothing looked up owes the prompt verbatim, so the step ran, its answer
   * was discarded, and the text of this row is the line as it was written. It
   * belongs in the record of the run rather than on the surface. A missing field
   * is false.
   */
  passthrough: boolean
  /** Why the row stayed empty, as an i18n key. */
  failedKey: string
}

/** A piece of a row's text: marked, or not. */
export interface Segment {
  t: string
  hit: boolean
}

/** What produces ONE row's text. Absent on the reference row, which runs none. */
export interface SeriesRequest {
  /** The perspective that writes — a config id, or a `custom:` key. */
  schema: string
  /** The model that is to write it. Empty leaves it to the platform's own. */
  interceptionModel?: string
  /** A perspective written by hand, where the row carries one. */
  contextPrompt?: string
}

/**
 * ONE row of the series. What is above the line is the surface's — it says what
 * this row IS; what is below it the run fills in.
 */
export interface SeriesRow {
  /**
   * What identifies this row's WORK — never its place. A row taken off the list
   * and put back finds its text still there, and a row added after a run costs
   * its own row and leaves every other picture standing.
   */
  key: string
  /** The line AS WRITTEN, with no step between it and the image models. */
  reference: boolean
  /**
   * A row that is READ and no longer RUN: a run the surface keeps in sight
   * after the choice that produced it was changed. It stands in the raster
   * like any other row and takes no part in a press: it is not written again,
   * its pictures are not computed again, and what it says holds for the line,
   * the perspective and the language of its OWN press.
   */
  inert?: boolean
  /**
   * What the row is called. The HEAD of the row is the surface's own — a mark
   * beside the name, a disc, the picture the line was read from — and it goes
   * into the raster through its slot; the name is here because the raster names
   * the cell's place under an enlarged picture with it.
   */
  label: string
  /**
   * What produces the row's text. Null where the surface brings the text with
   * it — the reference row, and a row a surface composes itself.
   */
  request: SeriesRequest | null
  // ---- what the run fills in, or what the surface brings where there is no
  //      request: the text of such a row is the surface's and stands here ----
  text: string
  segments: Segment[]
  failedKey: string
}

export interface SeriesColumn {
  id: string
  label: string
}

export interface SeriesGridColumn extends SeriesColumn {
  cells: RasterCell[]
}

export interface InterceptionSeriesOptions {
  /** The line every row starts from. */
  line: () => string
  /** The rows, in the order they stand, the reference row first. */
  rows: () => SeriesRow[]
  /** The image models. They are the columns. */
  columns: () => SeriesColumn[]
  /** Which surface a generation is tagged with. */
  sourceView: string
  /**
   * What this surface puts in the run's own record beyond the fields every
   * series records. None of it is shown — it is what makes a picture readable
   * again months later.
   */
  context?: (row: SeriesRow, column: SeriesColumn) => Record<string, unknown>
}

/**
 * Which of the platform's own sentences a refusal is, by the cause the route
 * names. The route's message is English maintainer prose and is never shown;
 * reading a cause off its wording is what the platform forbids (see
 * `BusyNote.reason`), and `cause` is what makes that unnecessary.
 *
 * Two of the causes the platform already says in its own words wherever a
 * generation meets them. A second wording of the same fact would be a second
 * thing to translate and a second thing to keep true.
 */
const REFUSED: Record<string, string> = {
  not_a_string: 'latentLab.interception.models.refused.not_a_string',
  unknown_model: 'latentLab.interception.models.refused.unknown_model',
  provider_without_key: 'latentLab.interception.models.refused.provider_without_key',
  preset_binds_model: 'latentLab.interception.models.refused.preset_binds_model',
  not_interception_preset: 'latentLab.interception.models.refused.not_interception_preset',
  no_interception_step: 'latentLab.interception.models.refused.no_interception_step',
  register_broken: 'latentLab.interception.models.refused.register_broken',
  chunk_template_missing: 'latentLab.interception.models.refused.chunk_template_missing',
  not_installed: 'generationError.causeNoModel',
  gpu_unreachable: 'generationError.causeUnreachable',
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * The words of a perspective, where the perspective IS a list of words. Many of
 * them are exactly that — a slash-separated collection the model collides the
 * line with — and there it can be counted through the text which of them
 * arrived. A perspective written as prose is an instruction and not a set of
 * words, so nothing is marked in that case.
 */
export function perspectiveTerms(context: string): string[] {
  const parts = (context || '')
    .split(' / ')
    .map(s => s.trim())
    .filter(Boolean)
  return parts.length >= 5 ? parts : []
}

/**
 * The text, cut into what is marked and what is not. Cut and set as TEXT nodes,
 * never as markup: what a model wrote is untrusted, and the only element in the
 * result is the span the template writes (the platform's rule for highlighting,
 * see components/EmphasisText.vue).
 */
export function markTerms(text: string, terms: string[]): Segment[] {
  if (!text) return []
  if (!terms.length) return [{ t: text, hit: false }]
  const alt = terms
    .slice()
    .sort((a, b) => b.length - a.length)
    .map(escapeRe)
    .join('|')
  let re: RegExp
  try {
    // Whole terms only, and letters of any script count as part of a word: a
    // list holding `nine` must not light up inside `ninety`.
    re = new RegExp(`(?<![\\p{L}\\p{N}])(?:${alt})(?![\\p{L}\\p{N}])`, 'giu')
  } catch {
    return [{ t: text, hit: false }]
  }
  const out: Segment[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ t: text.slice(last, m.index), hit: false })
    out.push({ t: m[0], hit: true })
    last = m.index + m[0].length
    // A term that matched empty would never move the cursor.
    if (m[0].length === 0) re.lastIndex++
  }
  if (last < text.length) out.push({ t: text.slice(last), hit: false })
  return out
}

export interface InterceptionSeries {
  /** What each row's request brought back, by the row's key. */
  results: Ref<Record<string, RowResult>>
  /** Phase 1 is out; the raster's own `running` carries phase 2. */
  writing: Ref<boolean>
  writingDone: Ref<number>
  writingTotal: Ref<number>
  running: Ref<boolean>
  done: Ref<number>
  expected: Ref<number>
  busy: ComputedRef<boolean>
  /** The last reason a cell did not come back, as a sentence. */
  errorMessage: Ref<string>
  /** The columns with their cells, one cell per row. */
  gridColumns: ComputedRef<SeriesGridColumn[]>
  /** What the picture in a cell was made from — the config's own adaption. */
  adapted: Ref<Record<string, string>>
  /** What stands in a cell instead of a medium, in the reader's language. */
  cellNote: (cell: RasterCell) => string
  /** Rows whose request has not brought a text back yet. */
  pendingRows: ComputedRef<SeriesRow[]>
  /** Cells that have a text to compute from and no picture yet. */
  pendingCells: ComputedRef<{ column: SeriesColumn; row: SeriesRow }[]>
  /** There is something to compute, and nothing running. */
  hasWork: ComputedRef<boolean>
  startRun: () => Promise<void>
  /** This surface is gone. The run stops where it is. */
  release: () => void
}

export function useInterceptionSeries(options: InterceptionSeriesOptions): InterceptionSeries {
  const { t, locale } = useI18n()
  const deviceId = useDeviceId()
  const baseUrl = apiBase()
  const { accountMissing, accountParams } = useModelAvailability()

  /**
   * This surface is still the one the run belongs to. The raster keeps its own
   * token for phase 2 (composables/useRasterRun.ts); phase 1 is a plain sequence
   * of calls and needs this.
   */
  let alive = true
  function release(): void {
    alive = false
  }

  const results = ref<Record<string, RowResult>>({})

  function putResult(key: string, value: RowResult): void {
    results.value = { ...results.value, [key]: value }
  }

  const {
    cells: grid,
    running,
    done,
    expected,
    start,
    live,
    recordImage,
    recordFailed,
  } = useRasterRun()

  /**
   * Why a cell brought nothing back, per cell and as an i18n key. The raster's
   * own record keeps a refusal (`blockedKey`) and the bare fact of a failure; a
   * queue that is full, a service that is silent and a config that is absent ask
   * three different things of whoever is looking, so the cause is held beside it.
   */
  const cellFailures = ref<Record<string, string>>({})
  /** The values the sentence of a cause names, per cell, where it names any. */
  const cellFailureParams = ref<Record<string, Record<string, string>>>({})

  /**
   * What the picture in a cell was made from: the output config's own adaption of
   * the row's text. Between the row's text and the image model stands a second
   * model, so the back of the card names this and not the row's text.
   */
  const adapted = ref<Record<string, string>>({})

  /**
   * What identifies a cell: its ROW, the output config and the seed. NOT its
   * place — so a row added after a run leaves every other picture standing. And
   * NOT the text: two rows can carry the same text — a perspective that hands
   * the line through unchanged stands beside the reference row word for word,
   * and two refused interceptions are both empty — and keyed by the text those
   * rows would share one cell, one picture and one record between them.
   */
  function cellKey(row: SeriesRow, config: string): string {
    return `${config}|${SERIES_SEED}|${row.key}`
  }

  const gridColumns = computed<SeriesGridColumn[]>(() =>
    options.columns().map(c => ({
      ...c,
      cells: options.rows().map(r => {
        const key = cellKey(r, c.id)
        return grid.value[key] ?? { key, seed: SERIES_SEED, url: '', blockedKey: '', failed: false }
      }),
    })),
  )

  function cellNote(cell: RasterCell): string {
    if (cell.blockedKey) return t(cell.blockedKey)
    if (cell.failed) {
      return t(cellFailures.value[cell.key] || 'latentLab.interception.models.cellFailed',
        cellFailureParams.value[cell.key] ?? {})
    }
    return ''
  }

  // -------------------------------------------------------------------------
  // The run. Two phases, one request at a time, never in parallel.
  // -------------------------------------------------------------------------

  const errorMessage = ref('')

  const writing = ref(false)
  const writingDone = ref(0)
  const writingTotal = ref(0)
  /**
   * A press is out, from the press to the end of its last picture. Between
   * the two phases neither `writing` nor `running` holds, and a choice that
   * waits for the end of a run (composables/useModelAvailability.ts) would
   * change there under the press.
   */
  const pressing = ref(false)
  const busy = computed(() => pressing.value || writing.value || running.value)

  const stream = useGenerationStream()

  /**
   * The rows a press works on. An inert row is a run the surface still shows
   * (`SeriesRow.inert`) and takes no part in one: it is not written again, its
   * pictures are not computed again, and its text says nothing about the line
   * that stands in the field now.
   */
  function workRows(): SeriesRow[] {
    return options.rows().filter(r => !r.inert)
  }

  const pendingRows = computed<SeriesRow[]>(() =>
    workRows().filter(r => r.request && !results.value[r.key]?.text),
  )

  const pendingCells = computed<{ column: SeriesColumn; row: SeriesRow }[]>(() =>
    gridColumns.value.flatMap(column =>
      workRows()
        .filter(r => r.text && !grid.value[cellKey(r, column.id)]?.url)
        .map(row => ({ column, row })),
    ),
  )

  // A cell whose image model is switched off for want of an account is no
  // work: a press would only mark it (runCell).
  const hasWork = computed(
    () =>
      !busy.value &&
      (pendingRows.value.length > 0 || pendingCells.value.some(c => !accountMissing(c.column.id))),
  )

  /**
   * What the platform's gate has let through for THIS line: a row that came back
   * with a text. Stage 1 runs on the line BEFORE the interception, so a text is
   * the proof that the line passed it. The results are keyed by what the row IS,
   * so a text from an earlier press of the same line counts and a changed line
   * proves nothing.
   */
  const linePassedGate = computed(() =>
    workRows().some(r => !!r.request && !!results.value[r.key]?.text),
  )

  /**
   * The two phases, and phase 2 only on what phase 1 established.
   *
   * Stage 1 runs inside the interception call and NOWHERE else on these
   * surfaces: the adaption is a model call with no gate of its own, and the
   * generation is handed a finished interception. So a press whose writing calls
   * established nothing about the line ends after phase 1 — otherwise a line the
   * gate refused would still be written on by the adaption and drawn by every
   * image model, through the reference row, which carries the line as it stands.
   */
  async function startRun(): Promise<void> {
    if (busy.value) return
    errorMessage.value = ''
    pressing.value = true
    try {
      const blockedKey = await runWriting()
      if (!alive) return
      // The gate refused the LINE. It is one fact about the run and not one per
      // row, so it stands once, in the platform's own words.
      if (blockedKey) {
        errorMessage.value = t(blockedKey)
        return
      }
      // Nothing passed: every writing call was refused before Stage 1 ran, or the
      // service never answered. The rows name their causes; there is nothing to add
      // here and nothing that may be computed.
      if (!linePassedGate.value) return
      // Only what is missing, and the texts of this press are already in the rows.
      await start(pendingCells.value, step => runCell(step.column, step.row))
    } finally {
      if (alive) pressing.value = false
    }
  }

  /**
   * Phase 1: every row that carries a request has its interception written.
   * Answers with the key of a SAFETY block where the gate refused the line, and
   * with nothing where it did not.
   */
  async function runWriting(): Promise<string> {
    const todo = pendingRows.value.slice()
    let blockedKey = ''
    if (!todo.length) return blockedKey
    writing.value = true
    writingDone.value = 0
    writingTotal.value = todo.length
    try {
      for (const row of todo) {
        if (!alive) return blockedKey
        const blocked = await intercept(row)
        if (blocked && !blockedKey) blockedKey = blocked
        if (!alive) return blockedKey
        writingDone.value++
      }
    } finally {
      if (alive) writing.value = false
    }
    return blockedKey
  }

  function refusalKey(status: number, body: Stage2Answer | null): string {
    // The Stage-1 gate. Its reasons are German developer strings and are never
    // shown raw. What it refused decides which sentence is true: the line is the
    // visitor's, and the sentences of the platform's safety block speak to them;
    // the perspective is the surface's own text, and a refusal of it says
    // nothing about what the visitor wrote.
    if (status === 403) {
      return blockedOnContext(body)
        ? 'latentLab.interception.models.refusedPerspective'
        : safetyBlockKey(body?.error, body?.blocked_at_stage)
    }
    const named = typeof body?.cause === 'string' ? REFUSED[body.cause] : ''
    if (named) return named
    // A backend that names no cause. Then the status is everything there is, and
    // the six causes it keeps apart under 400 fall together into the one sentence
    // that is true of all of them.
    if (status === 409) return 'generationError.causeNoModel'
    if (status === 503) return 'generationError.causeUnreachable'
    if (status === 400) return 'latentLab.interception.models.refusedRequest'
    // Any other status the route can end on — a full queue, a service that went
    // silent, a fault while writing — is read the way a failed generation is
    // read, and says what it was.
    return failureKey('error', typeof body?.error === 'string' ? body.error : '')
  }

  /** Whether a refusal was about the PERSPECTIVE this row carries. */
  function blockedOnContext(body: Stage2Answer | null): boolean {
    return body?.blocked_on === 'context_prompt'
  }

  /**
   * ONE row's interception of the line. Answers with the key of a SAFETY block
   * where the gate refused the LINE — that is a fact about the line, which every
   * row starts from, and holds the whole run back — and with nothing in every
   * other case, the gate's refusal of one row's own perspective included: that
   * belongs to its row and stops nothing else. A refusal at stage 2 is the
   * MODEL's, under this row's perspective and prefix (the backend answers it
   * as a block since 2026-10-10): it belongs to its row too.
   */
  async function intercept(row: SeriesRow): Promise<string> {
    const request = row.request
    if (!request) return ''
    const key = row.key
    // A row that asked to bring its own perspective and brought an empty one.
    // Sent as it is, the route would run the preset's OWN context — a different
    // text, at the full price of the row — and nothing would show it.
    if (request.contextPrompt !== undefined && !request.contextPrompt.trim()) {
      putResult(key, {
        text: '',
        dispatched: '',
        wikipediaTerms: [],
        passthrough: false,
        failedKey: 'latentLab.interception.models.cellFailed',
      })
      return ''
    }
    const empty: RowResult = {
      text: '',
      dispatched: '',
      wikipediaTerms: [],
      passthrough: false,
      failedKey: '',
    }
    try {
      // Streamed, not awaited in one silent POST: a row is a cloud model
      // writing prose, and a whole series of them sits behind the edge in front
      // of this server, which cuts a request whose origin has sent nothing for
      // about 100 seconds. Every status resolves, because a refusal is READ
      // here — `refusalKey` is given the status and the body, and both have to
      // survive to say which of the two texts a row was refused for.
      const res = await postStreamedRun<Stage2Answer | null>('/api/schema/pipeline/stage2', {
        schema: request.schema,
        input_text: options.line().trim(),
        user_language: locale.value,
        ...(request.interceptionModel ? { interception_model: request.interceptionModel } : {}),
        ...(request.contextPrompt ? { context_prompt: request.contextPrompt } : {}),
        device_id: deviceId,
      }, { baseUrl, validateStatus: () => true })
      const data = res.data ?? null
      if (res.status >= 400) {
        const why = refusalKey(res.status, data)
        putResult(key, { ...empty, failedKey: why })
        return res.status === 403 && !blockedOnContext(data) && data?.blocked_at_stage !== 2 ? why : ''
      }
      const text = String(data?.interception_result || data?.stage2_result || '').trim()
      if (!data?.success || !text) {
        // An answer the route stands behind that carries no text. This is the one
        // case "nothing came back" is true of.
        putResult(key, { ...empty, failedKey: 'latentLab.interception.models.cellFailed' })
        return ''
      }
      putResult(key, {
        text,
        dispatched: typeof data.interception_model === 'string' ? data.interception_model : '',
        // Kept, not shown: a text resting on retrieved articles is not the same
        // kind of text as one written from the model alone, and the record of the
        // run is where that belongs.
        wikipediaTerms: Array.isArray(data.wikipedia_terms)
          ? data.wikipedia_terms.map(w => ({
              term: String(w?.term ?? ''),
              lang: String(w?.lang ?? ''),
              found: w?.found === true,
            }))
          : [],
        passthrough: data.passthrough === true,
        failedKey: '',
      })
      return ''
    } catch (err: unknown) {
      // The request never reached an answer. That is the same kind of fact a
      // failed generation carries and is read the same way — a full queue, a
      // service that is silent — instead of falling into "nothing came back".
      const e = err as { message?: string }
      putResult(key, { ...empty, failedKey: failureKey('error', e?.message || '') })
      return ''
    }
  }

  /**
   * Phase 2, one cell: the output config's own adaption of this row's text, then
   * the generation from what it wrote.
   *
   * The adaption is asked for EVERY row, the reference row included, and it runs
   * on the platform's configured model — so the rows go to the image model
   * prepared in exactly the same way and differ in the one varied thing alone. An
   * adaption that brought nothing back therefore ends the cell: sending the
   * unadapted text on would make that one cell the only one prepared differently.
   */
  async function runCell(column: SeriesColumn, row: SeriesRow): Promise<void> {
    const key = cellKey(row, column.id)
    // An image model switched off for want of an account, before the run or
    // while it was out, is not asked, and no adaption is written for it. The
    // cell carries the sentence; when the run ends, the choice gives way to the
    // model the surface opens with, unless a picture of this one keeps it
    // (composables/useModelAvailability.ts).
    if (accountMissing(column.id)) {
      cellFailures.value = { ...cellFailures.value, [key]: 'x2xFlow.accountMissing' }
      cellFailureParams.value = { ...cellFailureParams.value, [key]: accountParams(column.id) }
      recordFailed(key, SERIES_SEED)
      return
    }
    let prepared = ''
    let adaptionFailure = ''
    try {
      // Streamed, for the reason the row above it is: a cell is a cloud model
      // writing, one per cell for the whole series, and the edge in front of
      // this server cuts a request whose origin has sent nothing for about 100
      // seconds. Every status resolves, because the refusal is read out of the
      // BODY here and has to survive to be read.
      const res = await postStreamedRun<OptimizeAnswer | null>(
        '/api/schema/pipeline/optimize',
        { input_text: row.text, output_config: column.id },
        { baseUrl, validateStatus: () => true },
      )
      const j = res.data ?? null
      if (res.status < 400) {
        if (j?.success && typeof j.optimized_prompt === 'string') prepared = j.optimized_prompt.trim()
      } else {
        // What refused the adaption is read the way a refused generation is read,
        // so a full queue and a service that went silent say so here as well.
        adaptionFailure = failureKey('error', typeof j?.error === 'string' ? j.error : '')
      }
    } catch (err: unknown) {
      const e = err as { message?: string }
      adaptionFailure = failureKey('error', e?.message || '')
    }
    if (!prepared) {
      cellFailures.value = {
        ...cellFailures.value,
        [key]: adaptionFailure || 'latentLab.interception.models.cellFailed',
      }
      recordFailed(key, SERIES_SEED)
      return
    }
    // The adaption is a model call and takes its time. The step loop asks between
    // two steps whether this run is still the one; a step that itself makes two
    // calls has to ask in the middle, or a surface the reader has left starts one
    // more generation after they are gone.
    if (!alive || !live()) return
    adapted.value = { ...adapted.value, [key]: prepared }

    stream.reset()
    try {
      const result: GenerationResult = await stream.executeWithStreaming({
        // What the model reads. Where the adaption answers in two parts (SD 3.5
        // writes one JSON object for its two encoders), the route takes it apart
        // itself and reads the long form off `interception_result`.
        prompt: prepared,
        output_config: column.id,
        seed: SERIES_SEED,
        input_text: options.line().trim(),
        interception_result: row.text,
        // The reference row ran no interception, so it names no perspective.
        ...(row.request ? { interception_config: row.request.schema } : {}),
        device_id: deviceId,
        source_view: options.sourceView,
      })
      if (!alive) return

      if (result.status === 'success' && result.media_output?.url) {
        recordImage(key, SERIES_SEED, {
          media_output: result.media_output,
          run_id: result.run_id,
          model_meta: stream.modelMeta.value,
          duration_ms: stream.stage4DurationMs.value,
        })
        recordRow(result.media_output.run_id || result.run_id || '', column, row, prepared)
        errorMessage.value = ''
        return
      }
      if (result.status === 'blocked') {
        // A refusal belongs at the cell it refused; the rest of the run is
        // unaffected and stays readable.
        grid.value = {
          ...grid.value,
          [key]: {
            key,
            seed: SERIES_SEED,
            url: '',
            blockedKey: safetyBlockKey(result.blocked_reason, result.blocked_stage),
            failed: false,
          },
        }
        return
      }
      const why = failureKey(result.status, result.error || '', result.busy)
      cellFailures.value = { ...cellFailures.value, [key]: why }
      recordFailed(key, SERIES_SEED)
      errorMessage.value = t('latentLab.interception.models.runFailed', { m: t(why) })
    } catch (err: unknown) {
      const e = err as { message?: string }
      const why = failureKey('error', e?.message || '')
      cellFailures.value = { ...cellFailures.value, [key]: why }
      recordFailed(key, SERIES_SEED)
      errorMessage.value = t('latentLab.interception.models.runFailed', { m: t(why) })
    }
  }

  /**
   * What this cell's row WAS, written into the run's own record: what wrote it,
   * the text it wrote and the terms it had to look up while writing. None of it
   * is shown on the surface — it is what makes a picture readable again months
   * later.
   */
  function recordRow(
    runId: string,
    column: SeriesColumn,
    row: SeriesRow,
    preparedPrompt: string,
  ): void {
    if (!runId) return
    const r = results.value[row.key]
    void fetch(`${baseUrl}/api/schema/pipeline/run/${runId}/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        comparison_context: {
          original_prompt: options.line().trim(),
          interception_config: row.request?.schema || '',
          dispatched_model: (row.request && r?.dispatched) || '',
          interception_result: row.text,
          // What the image model actually read. Between the row's text and the
          // picture stands the output config's own adaption, so the record that
          // names only the row's text names a text the picture was not made from.
          adapted_prompt: preparedPrompt,
          wikipedia_terms: (row.request && r?.wikipediaTerms) || [],
          passthrough: !!row.request && r?.passthrough === true,
          output_config: column.id,
          seed: SERIES_SEED,
          ...(options.context ? options.context(row, column) : {}),
        },
      }),
    }).catch(() => {
      /* fire-and-forget: the record is worth having, the run does not hang on it */
    })
  }

  return {
    results,
    writing,
    writingDone,
    writingTotal,
    running,
    done,
    expected,
    busy,
    errorMessage,
    gridColumns,
    adapted,
    cellNote,
    pendingRows,
    pendingCells,
    hasWork,
    startRun,
    release,
  }
}
