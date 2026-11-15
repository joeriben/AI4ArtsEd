import type { Ref } from 'vue'
import type { AsmItem } from './useAssemblageBoard'
import { postStreamedRun } from '@/services/directRun'
import { apiBase } from '@/services/labApi'
import { safetyBlockOf, type SafetyBlock } from '@/composables/useGenerationStream'

/**
 * Material intake — the canonical, view-independent way material reaches a
 * board: DataTransfer drop dispatch (artifact → favorite → held prompt → OS
 * files), favorite restore, user image ingestion (preview → upload → VLM input
 * check) and artifact drag-out. Views plug their board world in through the
 * adapter; view-specific placement semantics (x2x: fall dormancy, zone law)
 * stay in the views.
 */

/** Artifacts travel by run_id: that is what post-production can resolve. */
export const ARTIFACT_DT = 'application/x-ai4artsed-artifact'
/** Favorites travel the same way; the gallery writes this payload. */
export const FAVORITE_DT = 'application/x-ai4artsed-favorite'
/** A held (paused) machine prompt dragged onto a board becomes text material. */
export const PROMPT_DT = 'application/x-ai4artsed-prompt'

export interface IntakePoint {
  x: number
  y: number
}

export interface UploadedImage {
  /** response.image_id */
  imageId: string
  /** response.image_path — what the backend reads */
  path: string
  /** `/api/media/uploads/${image_id}` — what the canvas shows */
  servedUrl: string
  /** response.filename (pass-through for emit payloads) */
  filename?: string
  /** full server response (SketchCanvas upload_info) */
  raw: Record<string, unknown>
}

/**
 * The upload refused the picture rather than failing as a transfer: the
 * server's intake check judged it, or could not be carried out. `safety` is
 * that refusal as the quick check hands one over, so a surface reports it the
 * way it reports a refusal of the quick check.
 */
export class UploadRefused extends Error {
  readonly safety: QuickSafetyResult

  constructor(safety: QuickSafetyResult) {
    super('safety_blocked')
    this.name = 'UploadRefused'
    this.safety = safety
  }
}

/** The refusal an upload ended in, or null where it failed in any other way. */
export function uploadRefusal(err: unknown): QuickSafetyResult | null {
  return err instanceof UploadRefused ? err.safety : null
}

/**
 * What the upload route takes: `media_routes.ALLOWED_EXTENSIONS` by name and
 * `upload_gate.ALLOWED_IMAGE_SIGNATURES` by content. Kept in sync with both.
 */
const UPLOADABLE_TYPES: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/webp': 'webp',
}
const UPLOADABLE_NAME = /\.(png|jpe?g|webp)$/i
/** The route scales to this longest side (`_resize_image_to_supported_resolution`). */
const UPLOAD_MAX_SIDE = 2048

/**
 * The file as the upload route takes it.
 *
 * An iPhone stores its photos as HEIC by default, and Safari shows a HEIC on the board
 * while the route refuses it by name and by content. The photo then stood on
 * the board as a preview that never reached the server, and nothing that reads
 * the board (Resona among them) ever saw it. Any picture this browser can
 * display is therefore redrawn here as a JPEG, at the size the route would
 * scale it to anyway, so what is on the board is what is uploaded. A format
 * the browser cannot display stays as it is and is refused by the route.
 */
async function asUploadable(file: File): Promise<File> {
  const ext = UPLOADABLE_TYPES[file.type]
  if (ext) {
    return UPLOADABLE_NAME.test(file.name)
      ? file
      : new File([file], `${file.name || 'image'}.${ext}`, { type: file.type })
  }
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = url
    try {
      await img.decode()
    } catch {
      return file
    }
    const w0 = img.naturalWidth
    const h0 = img.naturalHeight
    if (!w0 || !h0) return file
    const scale = Math.min(1, UPLOAD_MAX_SIDE / Math.max(w0, h0))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(w0 * scale))
    canvas.height = Math.max(1, Math.round(h0 * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    // The route flattens transparency onto white as well.
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
    if (!blob) return file
    const base = (file.name || 'image').replace(/\.[^.]*$/, '') || 'image'
    return new File([blob], `${base}.jpg`, { type: 'image/jpeg' })
  } finally {
    URL.revokeObjectURL(url)
  }
}

/**
 * POST /api/media/upload/image. THE single upload implementation.
 * Body moved verbatim from x2x_flow's ingestImage — res.json() runs
 * BEFORE the !res.ok check, and this order MUST be preserved.
 * Consequence: an HTTP failure with a non-JSON body (proxy 413/502 HTML
 * page) throws the parse error from res.json(); a JSON body with !res.ok
 * or success:false throws Error(data.error || 'upload failed'), with what
 * the server said under `said` where it said anything. All callers catch
 * generically, so both failure shapes behave identically.
 *
 * The server checks the PICTURE where it comes in (media_routes.upload_image)
 * and refuses it there with 403 and the block message. That refusal throws an
 * `UploadRefused`, which carries it in the shape the quick check hands a
 * refusal over in; `uploadCheckedImage` turns it back into an answer.
 *
 * `source` is the address of the recorded picture the file was fetched from.
 * Where the bytes are that picture, the server hands its verdict on instead of
 * asking again.
 */
export async function uploadImageFile(file: File, source?: string): Promise<UploadedImage> {
  const form = new FormData()
  form.append('file', await asUploadable(file))
  if (source) form.append('source', source)
  const res = await fetch('/api/media/upload/image', { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok || !data.success) {
    if (safetyBlockOf(data)) throw new UploadRefused(readRefusal({ safe: false }, data))
    const refused = new Error(data.error || 'upload failed') as Error & { said?: string }
    if (typeof data.error === 'string' && data.error) refused.said = data.error
    throw refused
  }
  return {
    imageId: data.image_id,
    path: data.image_path,
    servedUrl: `/api/media/uploads/${data.image_id}`,
    filename: data.filename,
    raw: data,
  }
}

/**
 * Re-upload a platform artifact image (by URL) so it carries the server path
 * i2x reads.
 *
 * It uploads and nothing else. Whether the picture is checked afterwards is the
 * CALLER's question and is answered at each call: a favourite carries the level
 * of the session that made it, which need not be the level of the surface it is
 * dropped on, and Stage 3 checks an image only at kids and youth level anyway.
 * A note here once said the platform's own output needs no input check, and
 * the boards read that as licence to place one unjudged.
 */
export async function uploadImageFromUrl(url: string, filename: string): Promise<UploadedImage> {
  const blob = await (await fetch(url)).blob()
  return uploadImageFile(new File([blob], filename, { type: blob.type || 'image/png' }), url)
}

/**
 * A picture's way onto a surface, as one step: the upload, which checks the
 * picture where it comes in, and the quick check, which reads the verdict the
 * upload kept, at the level of whoever asks, and asks no model again.
 *
 * `up` is null where the upload refused the picture; `safety` then says why,
 * as it does where the quick check refuses. Every other failure of the upload
 * throws, as `uploadImageFile` does, and the callers catch it as before.
 */
export async function uploadCheckedImage(
  file: File,
  source?: string,
): Promise<{ up: UploadedImage | null; safety: QuickSafetyResult }> {
  let up: UploadedImage
  try {
    up = await uploadImageFile(file, source)
  } catch (err) {
    const refused = uploadRefusal(err)
    if (refused) return { up: null, safety: refused }
    throw err
  }
  return { up, safety: await quickImageSafetyCheck(up.path) }
}

/** `uploadCheckedImage` for a picture this platform serves, fetched by its address. */
export async function uploadCheckedImageFromUrl(
  url: string,
  filename: string,
): Promise<{ up: UploadedImage | null; safety: QuickSafetyResult }> {
  const blob = await (await fetch(url)).blob()
  return uploadCheckedImage(new File([blob], filename, { type: blob.type || 'image/png' }), url)
}

/**
 * A run as the server keeps it — what a favourite resolves to. One place asks
 * for it, because a run means the same thing wherever it lands: on a board, in
 * a field, in the strip's large view.
 */
export interface RunData {
  input_text?: string
  transformed_text?: string
  schema?: string
  media_outputs?: Array<{ type?: string; url?: string; filename?: string }>
  /** A Latent Lab run keeps its own object here: parameters, parts, outputs. */
  instrument?: {
    tool?: string
    parameters?: Record<string, unknown>
    outputs?: Array<{ type?: string; url?: string; format?: string }>
  }
  [key: string]: unknown
}

/** GET /api/favorites/<run>/restore. Null when the run cannot be resolved. */
export async function fetchRunData(runId: string): Promise<RunData | null> {
  try {
    const res = await fetch(`/api/favorites/${runId}/restore`)
    const d = await res.json()
    return res.ok ? (d as RunData) : null
  } catch {
    return null
  }
}

/** What a receiving place IS, and therefore what it asks a run for. */
export type MaterialWant = 'text' | 'image' | 'audio' | 'video'

/** The one thing that came out of a run for the place that asked. */
export type ResolvedMaterial =
  | { kind: 'text'; text: string }
  | { kind: 'image'; image: UploadedImage }
  | { kind: 'media'; src: string }
  /** The picture was refused where it came in: the upload's intake check. */
  | { kind: 'refused'; safety: QuickSafetyResult }

/**
 * Take ONE thing out of a run — the thing the receiving place is. The place
 * decides, so this asks rather than chooses: a text field asks for text and
 * gets the prompt the run was made from, a picture field asks for a picture and
 * gets it re-uploaded, carrying the server path i2x reads. Null when the run
 * holds nothing of that kind.
 *
 * Board-free on purpose. `dropFavorite` below does the same for a board, where
 * placement and the board's own laws come in; a field has neither.
 */
/**
 * The kinds a run records under the RUNTIME's own name rather than as an
 * `output_`: a sketch IS its source text. They read as an output like any
 * other and must never be mistaken for one — a `.js` handed to an <img> or an
 * upload is a broken picture.
 */
const RUNTIME_KINDS = ['p5', 'tonejs', 'sonicpi', 'midi']

/**
 * The words a Latent Lab run was made from, where the run has no single
 * `prompt`. Concept Algebra runs on three prompts, Feature Probing on two,
 * Composable Diffusion on a list of concepts, the audio synth on two — and the
 * favourites route only ever looked for `prompt`, so a card from four of those
 * instruments dropped into a text field did nothing at all. Order is the order
 * an instrument writes them, and the separator is the one those instruments
 * already show between two prompts.
 */
function labPrompt(d: RunData): string {
  const params = d.instrument?.parameters
  if (!params) return ''
  const parts: string[] = []
  for (const key of ['prompt', 'prompt_a', 'prompt_b', 'prompt_c', 'concepts', 'text']) {
    const value = params[key]
    if (typeof value === 'string' && value.trim()) parts.push(value.trim())
    else if (Array.isArray(value)) {
      for (const one of value) {
        if (typeof one === 'string' && one.trim()) parts.push(one.trim())
        else if (one && typeof one === 'object') {
          const inner = (one as Record<string, unknown>).text ?? (one as Record<string, unknown>).prompt
          if (typeof inner === 'string' && inner.trim()) parts.push(inner.trim())
        }
      }
    }
  }
  return parts.join(' / ')
}

export async function resolveRunAs(
  runId: string,
  want: MaterialWant
): Promise<ResolvedMaterial | null> {
  const d = await fetchRunData(runId)
  if (!d) return null

  if (want === 'text') {
    // The words the run was MADE from, which is what the large view of a run
    // shows. `transformed_text` came first here and is a different text in 53
    // of 55 stored favourites — the intercepted English, several hundred
    // characters of it, where the tile said "a silly parrot". What is shown and
    // what is handed over have to be the same words.
    const text = d.input_text || d.transformed_text || labPrompt(d) || ''
    return text ? { kind: 'text', text } : null
  }

  // A Latent Lab run says which of its outputs is which AND numbers them by
  // kind; the favourites list flattens every image to index 0, so a run that
  // recorded its reference picture before its result handed over the reference.
  const outs = [
    ...(d.instrument?.outputs || []),
    ...(d.media_outputs || []),
  ].filter((o) => !!o?.url) as Array<{ type?: string; url?: string; filename?: string }>
  // The kind that was asked for, if the run says which of its outputs is which;
  // otherwise the first one, which is what a single-medium run has — and never
  // a sketch, whose source text answers no request for a picture or a sound.
  const out =
    outs.find((o) => (o.type || '').startsWith(want)) ||
    outs.find((o) => !RUNTIME_KINDS.includes(o.type || ''))
  if (!out?.url) return null

  if (want === 'image') {
    try {
      return { kind: 'image', image: await uploadImageFromUrl(out.url, out.filename || `${runId}.png`) }
    } catch (err) {
      // A picture refused where it came in is a verdict the place that asked
      // has to report, not a run that holds no picture.
      const refused = uploadRefusal(err)
      return refused ? { kind: 'refused', safety: refused } : null
    }
  }
  return { kind: 'media', src: out.url }
}

export interface QuickSafetyResult {
  /** !!response.safe — a parseable body without safe:true BLOCKS */
  safe: boolean
  /** response.error_message */
  errorMessage?: string
  /** response.vlm_description */
  vlmDescription?: string
  /** response.safety_block — the block message, where the check refused. */
  block?: SafetyBlock
  /**
   * response.checks_passed — which checks the route says it carried out. The
   * text check reads it; the picture check has no reader for it.
   */
  checks?: string[]
  /**
   * The check did not run to an answer at all — the server unreachable, the
   * body unreadable, the stream torn before its verdict. The material is held
   * back either way; this says the fault was the platform's and not a rating of
   * the picture, so the caller can say which of the two it is.
   */
  operational?: boolean
}

/**
 * A refusal's block message, and whether it says the check could not be
 * CARRIED OUT rather than that it judged the material (`reason_key`
 * `unavailable`). A fault of this platform must never reach anyone as a rating
 * of what they made. Until 2026-10-30 that was read out of the server's German
 * wording, with a list of the sentences it says it in.
 */
function readRefusal(result: QuickSafetyResult, body: unknown): QuickSafetyResult {
  const block = safetyBlockOf(body)
  if (block) result.block = block
  if (block?.reason_key === 'unavailable') result.operational = true
  return result
}

/**
 * POST /api/schema/pipeline/safety/quick with { image_path }. THE single
 * quick-check implementation.
 *
 * Fails CLOSED in every direction. A check that could not be carried out is not
 * a pass — it is no judgement at all, and material nobody has judged stays out.
 * There are no fail-open checks, and that binds every session. Before this
 * rule the function resolved `{ safe: true }` on any transport or parse
 * error, which is the first of the four patterns that have broken this
 * platform's check chain since 2025: a verdict that fails to arrive becomes a
 * permission.
 *
 * `operational` separates the two refusals — the check judged the picture, or
 * the check did not run. The platform makes that distinction on the server as
 * well (VLM_CONTENT_BLOCK_MESSAGE against VLM_OPERATIONAL_BLOCK_MESSAGE),
 * because a technical fault must never read as a rating of what someone made.
 */
export async function quickImageSafetyCheck(imagePath: string): Promise<QuickSafetyResult> {
  // No path is no picture, and a request without one is not a check: the route
  // answers it `{"checks_passed": [], "safe": true}` — measured through the
  // tunnel — and an upload whose answer carried no `image_path`
  // reached exactly that, because an undefined field leaves the JSON body
  // altogether. Nothing in that answer is a verdict.
  if (!imagePath) return { safe: false, operational: true }
  try {
    // Streamed, not awaited in one silent POST: a vision model reads the
    // picture and waits its turn in the plant-wide queue, while the edge in
    // front of this server cuts a request whose origin has sent nothing for
    // about 100 seconds — and that cut is what used to leave a picture on the
    // board with no verdict on it at all.
    //
    // Every status resolves. The check fails CLOSED on the server and says so in
    // the BODY (`safe: false`) under a 200, and the transport hands a gateway
    // page or an error body back as a body rather than throwing — so most
    // operational failures arrive HERE, not in the catch, and the verdict has
    // to be read as a verdict rather than assumed.
    const sres = await postStreamedRun('/api/schema/pipeline/safety/quick', {
      image_path: imagePath,
    }, { validateStatus: () => true })
    const safety = sres.data
    // A body that carries no verdict IS no verdict: `safe` has to be a boolean,
    // or nothing in this answer permits the picture.
    if (!safety || typeof safety.safe !== 'boolean') return { safe: false, operational: true }
    const result: QuickSafetyResult = {
      safe: safety.safe,
      errorMessage: safety.error_message,
      vlmDescription: safety.vlm_description,
    }
    // The server's own operational refusal reaches the surfaces under the same
    // marker as this client's, so neither has to be matched out of German
    // wording at the far end.
    return safety.safe ? result : readRefusal(result, safety)
  } catch {
    // Nothing came back that could permit this picture, so it does not go on.
    return { safe: false, operational: true }
  }
}

/**
 * The same check for TEXT: POST /api/schema/pipeline/safety/quick with
 * { text, user_language }. THE single text quick-check implementation, and
 * fail-closed in every direction, exactly as the picture one is.
 *
 * Text carries a level too. A memo brought onto a board from another session
 * reaches the chat model the same way a typed line does, and until this stood
 * here only the typed line was checked.
 */
export async function quickTextSafetyCheck(
  text: string,
  userLanguage: string,
): Promise<QuickSafetyResult> {
  if (!text.trim()) return { safe: false, operational: true }
  try {
    // Streamed, not awaited in one silent POST: where the name recogniser hits,
    // this check asks a model whether the name is a real person, and the edge in
    // front of this server cuts a request whose origin has sent nothing for
    // about 100 seconds.
    const baseUrl = apiBase()
    const res = await postStreamedRun('/api/schema/pipeline/safety/quick', {
      text, user_language: userLanguage,
    }, { baseUrl, validateStatus: () => true })
    const data = res.data
    if (!data || typeof data.safe !== 'boolean') return { safe: false, operational: true }
    const result: QuickSafetyResult = {
      safe: data.safe,
      errorMessage: data.error_message,
      checks: data.checks_passed || [],
    }
    return data.safe ? result : readRefusal(result, data)
  } catch {
    // Nothing came back that judged this text.
    return { safe: false, operational: true }
  }
}

export interface MaterialIntakeAdapter {
  /** Screen (client) → board world coordinates; null when no board is mounted. */
  toWorldPoint(e: { clientX: number; clientY: number }): IntakePoint | null
  /**
   * Where a PICKED image lands — a pick has no pointer event to read a place
   * from, so the view puts each card down itself, once it exists and has its
   * size (x2x-flow: on the free place nearest its plus). Absent: the intake's
   * own fan-out, as before.
   */
  placePicked?(it: AsmItem): void
  /** Board mutators — the canonical useAssemblageBoard adders (or equivalents). */
  addText(x?: number, y?: number): AsmItem
  addImage(src: string, x?: number, y?: number): AsmItem
  addMedia(kind: 'audio' | 'video', src: string, runId: string, x?: number, y?: number): AsmItem
  removeItem(id: string): void
  /**
   * Place a restored platform image artifact. The VIEW decides placement
   * semantics (x2x: fallImage — deliberate drop, fell=false, re-upload) AND
   * runs the input check on it: a favourite carries the level of the session
   * that made it, not the level of the surface it lands on. Awaited by
   * dropFavorite.
   */
  placeArtifactImage(
    runId: string,
    url: string,
    meta: AsmItem['meta'],
    at: IntakePoint | null
    // x2x's fallImage hands back the uploaded server path (a chained run needs
    // it). Nothing here reads that — the return is deliberately unconstrained.
  ): void | Promise<unknown>
  /** Place a restored platform audio/video artifact (x2x: fallMedia). */
  placeArtifactMedia(
    kind: 'audio' | 'video',
    src: string,
    runId: string,
    meta: AsmItem['meta'],
    at: IntakePoint | null
  ): void
  /**
   * Place a restored sketch (x2x: fallCode). Optional: a surface without a
   * place for running code leaves such a run where it is rather than laying
   * something else down in its stead.
   */
  placeArtifactCode?(
    code: string,
    kind: 'p5js' | 'tonejs',
    runId: string,
    meta: AsmItem['meta'],
    at: IntakePoint | null
  ): void
  /** Current drag-out source of the view's output node; null disables drag-out. */
  artifactDragSource(): { runId: string; src: string } | null
  /** Fired once per accepted user image intake batch (x2x: clearManualChoice). Optional. */
  onUserImageIntake?(): void
  /** A user image was blocked by the input check (item already removed). */
  reportSafetyBlocked(result: QuickSafetyResult): void
  /** The input check passed and produced a VLM description. */
  reportSafetyAnalysis(description: string): void
}

export interface MaterialIntakeOptions {
  adapter: MaterialIntakeAdapter
  /** The hidden <input type="file"> the view renders; pickImage() clicks it. */
  fileInput: Ref<HTMLInputElement | null>
}

export interface MaterialIntake {
  pickImage(): void
  onFilePick(e: Event): void
  readImages(files: FileList, at?: IntakePoint | null, place?: (it: AsmItem) => void): void
  ingestImage(
    file: File,
    index: number,
    at?: IntakePoint | null,
    place?: (it: AsmItem) => void
  ): Promise<void>
  dropFavorite(runId: string, mediaType: string, at: IntakePoint | null): Promise<void>
  onDrop(e: DragEvent): void
  onArtifactDrag(e: DragEvent, kind: 'audio' | 'video'): void
}

/** Height per width of a picture once it is decoded; null where it cannot be read. */
function pictureRatio(src: string): Promise<number | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img.naturalWidth ? img.naturalHeight / img.naturalWidth : null)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
    reader.onerror = () => reject(new Error('read failed'))
    reader.readAsDataURL(file)
  })
}

export function useMaterialIntake(options: MaterialIntakeOptions): MaterialIntake {
  const { adapter } = options

  function pickImage() {
    options.fileInput.value?.click()
  }

  /**
   * An image that lands on the canvas is uploaded at once. The data URL is only a
   * preview — the pipelines are handed the server path, because a base64 blob in
   * the SSE GET query string never reaches the backend. Once the upload is served
   * back, the preview switches to that URL and no base64 is kept or persisted.
   */
  async function ingestImage(
    file: File,
    i: number,
    at?: IntakePoint | null,
    place?: (it: AsmItem) => void
  ) {
    let it: AsmItem
    let ratio: number | null = null
    try {
      const src = await readAsDataUrl(file)
      // A placed card is as tall as its picture, and a picture has no height
      // before it is decoded: without this the view would place the card at
      // the board's default height and a portrait photo would grow over
      // whatever lies below it.
      if (!at && place) ratio = await pictureRatio(src)
      it = adapter.addImage(src, 100 + i * 24, 90 + i * 24)
    } catch {
      return
    }
    if (at) {
      // Centered under the pointer; several files fan out from there.
      it.x = Math.round(at.x - it.w / 2) + i * 24
      it.y = Math.round(at.y - it.h / 2) + i * 24
    } else if (place) {
      if (ratio) it.h = Math.round(it.w * ratio)
      place(it)
    }
    it.uploading = true
    try {
      // The platform's intake of a picture, the one the upload widget takes:
      // checked where it comes in, the verdict read once more. It holds the
      // picture back both when the check refuses it and when the check could
      // not be carried out.
      // Canvas images now really reach a pipeline, so the check travels with them.
      const { up, safety } = await uploadCheckedImage(file)
      if (!up || !safety.safe) {
        adapter.removeItem(it.id)
        adapter.reportSafetyBlocked(safety)
        return
      }
      if (safety.vlmDescription) adapter.reportSafetyAnalysis(safety.vlmDescription)

      it.imageId = up.imageId
      it.path = up.path
      it.src = up.servedUrl
      it.uploading = false
    } catch {
      it.uploading = false
      it.failed = true
    }
  }

  function readImages(files: FileList, at?: IntakePoint | null, place?: (it: AsmItem) => void) {
    const accepted = Array.from(files).filter((f) => f.type.startsWith('image/'))
    if (!accepted.length) return
    // A new image is the one event that hands routing back to the automatic rule.
    adapter.onUserImageIntake?.()
    accepted.forEach((f, i) => void ingestImage(f, i, at, place))
  }

  function onFilePick(e: Event) {
    const input = e.target as HTMLInputElement
    if (input.files) readImages(input.files, null, adapter.placePicked)
    input.value = ''
  }

  /**
   * A favorite dragged from the gallery becomes material on the table — the
   * moment returns with its provenance. Images re-upload for the server path
   * i2x reads; sound and video keep their run URL like any fallen artifact.
   */
  async function dropFavorite(runId: string, mediaType: string, at: IntakePoint | null) {
    try {
      const d = await fetchRunData(runId)
      if (!d) return
      if (mediaType === 'text') {
        const it = adapter.addText(at ? at.x : 80, at ? at.y : 80)
        // MATERIAL, so the same words the plate and the large view of that run
        // show, exactly as `resolveRunAs` hands them to a field. `dropFavorite`
        // was extracted from x2x_flow with the reverse order and kept it, so
        // one gesture gave two answers depending on where it landed: the tile
        // said "a silly parrot", the board got the intercepted English.
        // The PROVENANCE of an artifact is a different thing and keeps the
        // generation prompt below (`meta.prompt`), which is what a card that
        // fell out of a run carries too (x2x_flow `finalPrompt`).
        it.text = d.input_text || d.transformed_text || ''
        return
      }
      const meta: AsmItem['meta'] = {
        prompt: d.transformed_text || d.input_text || undefined,
        config: d.schema || undefined,
        mediaType,
      }
      // The output of the kind that was kept. A run can hold more than one —
      // a sketch that also recorded a still — and the first is not always the
      // one that was starred.
      const outs = (d.media_outputs || []) as Array<{ type?: string; url?: string }>
      const out =
        outs.find((o) => o.type === mediaType && !!o.url) ||
        outs.find((o) => !!o.url && !RUNTIME_KINDS.includes(o.type || ''))
      if (!out?.url) return
      if (mediaType === 'p5' || mediaType === 'tonejs') {
        // A sketch comes back as what it is: its source, running on the table
        // again. Without a place for it the table stays as it was.
        if (!adapter.placeArtifactCode) return
        const res = await fetch(out.url)
        if (!res.ok) return
        const code = await res.text()
        if (!code) return
        adapter.placeArtifactCode(code, mediaType === 'tonejs' ? 'tonejs' : 'p5js', runId, meta, at)
      } else if (mediaType === 'image') {
        await adapter.placeArtifactImage(runId, out.url, meta, at)
      } else if (mediaType === 'video' || mediaType === 'composition') {
        // A composition is an mp4 and lies on the table as a film.
        adapter.placeArtifactMedia('video', out.url, runId, meta, at)
      } else if (mediaType === 'audio' || mediaType === 'music' || mediaType === 'sound') {
        adapter.placeArtifactMedia('audio', out.url, runId, meta, at)
      }
      // 3d, midi, sonicpi: nothing on this table can hold them yet
    } catch {
      /* an unresolvable favorite leaves the table unchanged */
    }
  }

  function onDrop(e: DragEvent) {
    const at = adapter.toWorldPoint(e)
    const raw = e.dataTransfer?.getData(ARTIFACT_DT)
    if (raw) {
      try {
        const a = JSON.parse(raw) as { kind: 'audio' | 'video'; runId: string; src: string }
        if ((a.kind === 'audio' || a.kind === 'video') && a.runId && a.src) {
          const it = adapter.addMedia(a.kind, a.src, a.runId)
          if (at) {
            it.x = Math.round(at.x - it.w / 2)
            it.y = Math.round(at.y - it.h / 2)
          }
        }
      } catch {
        /* not our payload */
      }
      return
    }
    const fav = e.dataTransfer?.getData(FAVORITE_DT)
    if (fav) {
      try {
        const f = JSON.parse(fav) as { run_id: string; media_type: string }
        if (f.run_id) void dropFavorite(f.run_id, f.media_type, at)
      } catch {
        /* not our payload */
      }
      return
    }
    const held = e.dataTransfer?.getData(PROMPT_DT)
    if (held) {
      // The held prompt becomes table text where it lands - a user gesture,
      // so it counts like any laid material.
      const it = adapter.addText(at ? Math.round(at.x - 125) : 80, at ? Math.round(at.y - 60) : 80)
      it.text = held
      return
    }
    if (e.dataTransfer?.files) readImages(e.dataTransfer.files, at)
  }

  function onArtifactDrag(e: DragEvent, kind: 'audio' | 'video') {
    const src = adapter.artifactDragSource()
    if (!src) return
    e.dataTransfer?.setData(ARTIFACT_DT, JSON.stringify({ kind, runId: src.runId, src: src.src }))
    if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
  }

  return { pickImage, onFilePick, readImages, ingestImage, dropFavorite, onDrop, onArtifactDrag }
}
