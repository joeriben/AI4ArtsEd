import { ref, computed, type Ref } from 'vue'
import { usePanZoom } from './usePanZoom'

export type AsmKind = 'text' | 'image' | 'audio' | 'video' | 'source' | 'code'

export interface AsmItem {
  id: string
  kind: AsmKind
  x: number
  y: number
  w: number
  h: number
  text?: string
  /** What the canvas shows: a data URL while uploading, then the served upload. */
  src?: string
  /** What the backend reads. Absolute server path from /api/media/upload/image. */
  path?: string
  imageId?: string
  /** A generated sketch: which runtime runs the code that lies in `text`. */
  codeKind?: 'p5js' | 'tonejs'
  /**
   * One still picture of what a sketch draws, taken once when it fell, as a
   * small data URL. Absent for Tone.js — there is nothing to see — and for a
   * sketch whose canvas could not be read; the card then shows the runtime's
   * name instead.
   */
  thumb?: string
  /**
   * Artifacts dragged off the output box carry the run that produced them. That
   * run_id is what post-production resolves; an uploaded file has no run, which
   * is why only sound and video can be dragged back onto the board.
   */
  runId?: string
  uploading?: boolean
  /** Upload failed: the image is visible, marked, and blocks the run. */
  failed?: boolean
  /**
   * The artifact fell onto the table by itself when its run finished. Fallen
   * material lies ready but is read only once it is placed into the zone;
   * material the user placed (upload, sketch, drag) counts as before.
   */
  fell?: boolean
  /**
   * A box the run itself laid down and wrote into while it worked: the reading
   * a perspective made of the material, or the adaption made of that reading
   * for the model. Such a box says so in its bar instead of calling itself a
   * prompt. Absent on every box a person wrote.
   */
  station?: 'interception' | 'adaption'
  /**
   * What this box's bar says, where the station's own name would not say why
   * the box is there. A box that carries a text something was DONE to names the
   * doing — and the number it can be checked against.
   */
  title?: string
  /**
   * Which run on this board laid the box down, counted from 1. It stands in the
   * bar and does two things at once: the boxes of one run carry the same
   * number, and the boxes of the run before carry a different one.
   */
  run?: number
  /**
   * Provenance captured when the artifact fell: what was submitted, which
   * model made it, under which perspective. The back side (fullscreen
   * inspect) reads it; an upload has none.
   */
  meta?: {
    prompt?: string
    config?: string
    preset?: string
    /** The LoRAs the run loaded, named with their strength where it was not the trained one. */
    loras?: string
    mediaType?: string
    /** The checks THIS run passed. */
    safety?: string[]
  }
  /**
   * A source a perspective looked up while it was reading. Evidence, not
   * material: it lies beside the ring, and no run reads it. The text it holds
   * already went into that perspective's reading, on the server — the card is
   * where somebody can see what that was.
   */
  source?: {
    /** What was searched for. This is what the front of the card shows. */
    term: string
    /** The article that was found, or the term again when nothing was. */
    title: string
    /** Empty when the lookup found nothing — the card then says so. */
    url: string
    /** The opening summary that was retrieved, capped by the service at 2000 chars. */
    extract: string
    /** Which Wikipedia was read. The whole point of the lookup is that it need not be en. */
    lang: string
    /** The perspective that went looking. Empty for a run with no perspective. */
    perspective: string
    /**
     * Why the model looked this up, in its own words. Taken verbatim from the
     * marker and never checked — a reason we had filtered would be ours, and
     * the point is to make the model's estimate of its own limits readable.
     */
    why: string
  }
}

let _seq = 0
function nextId(): string {
  _seq += 1
  return 'a' + _seq
}

/**
 * Assemblage board — a fixed viewport (the stage) onto a larger, pannable and
 * zoomable world (the montage). Material objects (text, image) live in world
 * coordinates and are dragged freely. UI chrome around the board stays at screen
 * scale; only the world (the material) zooms — the deliberate Miro metaphor,
 * distinct from the flow map's fixed geometry.
 */
export function useAssemblageBoard() {
  const items: Ref<AsmItem[]> = ref([])

  // The world's pan/zoom AND the item drag/resize/z-order engine — the shared
  // usePanZoom core (Rule #13 — no parallel element structures). resetView
  // returns the board to its initial 40,40 offset. The board binds neither
  // z-index nor a focus ring, so the extracted selection/z-order primitives run
  // but stay invisible here (x2x-flow unchanged); the planning canvas binds them.
  const {
    pan,
    zoom,
    worldStyle,
    zoomBy,
    reset: resetView,
    startPan,
    onWheelZoom,
    startItemDrag,
    startItemResize: startItemResizeCore,
  } = usePanZoom({
    initialPan: { x: 40, y: 40 },
    minZoom: 0.4,
    maxZoom: 2,
  })

  /**
   * Both adders return the *reactive* item, not the raw object they pushed.
   * Callers mutate the result after an await (an upload resolving, a seed being
   * written); mutating the raw object would bypass the proxy and never render.
   */
  function addText(x = 70, y = 60): AsmItem {
    const it: AsmItem = { id: nextId(), kind: 'text', x, y, w: 250, h: 120, text: '' }
    items.value.push(it)
    return items.value[items.value.length - 1]!
  }
  function addImage(src: string, x = 90, y = 90): AsmItem {
    const it: AsmItem = { id: nextId(), kind: 'image', x, y, w: 190, h: 150, src }
    items.value.push(it)
    return items.value[items.value.length - 1]!
  }
  /** A finished artifact returning to the board as material (sound, video). */
/**
   * A looked-up source, laid on the board by the perspective that read it.
   * Deliberately not `addText`: a source is a quotation with an origin, and a
   * text item — editable, and read by the next run — would lose both halves.
   */
  function addSource(source: NonNullable<AsmItem['source']>, x = 40, y = 40): AsmItem {
    const it: AsmItem = { id: nextId(), kind: 'source', x, y, w: 200, h: 90, source }
    items.value.push(it)
    return items.value[items.value.length - 1]!
  }
    /**
   * A generated sketch. The code lies in `text` — to the board it is the same
   * thing a written idea is, characters — but the kind is what decides how it
   * is treated: no run reads it (`combinedText` takes `kind === 'text'` only),
   * and a click runs it instead of putting a cursor in it.
   */
  function addCode(
    code: string,
    codeKind: 'p5js' | 'tonejs',
    runId: string,
    x = 120,
    y = 120
  ): AsmItem {
    const it: AsmItem = {
      id: nextId(),
      kind: 'code',
      x,
      y,
      w: 240,
      h: 200,
      text: code,
      codeKind,
      runId,
    }
    items.value.push(it)
    return items.value[items.value.length - 1]!
  }
  function addMedia(kind: 'audio' | 'video', src: string, runId: string, x = 120, y = 120): AsmItem {
    const it: AsmItem =
      kind === 'audio'
        ? { id: nextId(), kind, x, y, w: 260, h: 56, src, runId }
        : { id: nextId(), kind, x, y, w: 280, h: 170, src, runId }
    items.value.push(it)
    return items.value[items.value.length - 1]!
  }
  function removeItem(id: string) {
    items.value = items.value.filter((i) => i.id !== id)
  }
  function setItems(next: AsmItem[]) {
    items.value = next
    const maxSeq = next.reduce((m, i) => {
      const n = parseInt(i.id.replace(/^a/, ''), 10)
      return Number.isFinite(n) && n > m ? n : m
    }, _seq)
    _seq = maxSeq
  }

  // Item drag comes straight from the engine (screen delta ÷ zoom = world delta,
  // plus select + bring-to-front). Resize needs the board's one bit of item
  // semantics: prose grows on both axes, everything else keeps its aspect ratio.
  // A looked-up source counts as prose: its back is the article's text, read in
  // a card as tall as its front, so the card has to be pulled taller.
  function startItemResize(e: PointerEvent, it: AsmItem) {
    // A sound is the third case: its card is exactly as tall as the native
    // player and nothing on the page draws it from `h`, so `h` stays the 56 it
    // was born with. Under the aspect ratio it grew with the width — the number
    // moved, the card did not, and the midpoint the zone reads (`y + h / 2`)
    // walked out from under the sound lying visibly inside the circle.
    if (it.kind === 'audio') {
      startItemResizeCore(e, it, { mode: 'free', minH: it.h, maxH: it.h })
      return
    }
    startItemResizeCore(e, it, { mode: it.kind === 'text' || it.kind === 'source' ? 'free' : 'aspect' })
  }

  // The prompt handed to the flow: all text material, joined.
  const combinedText = computed(() =>
    items.value
      .filter((i) => i.kind === 'text' && i.text && i.text.trim())
      .map((i) => i.text!.trim())
      .join('\n\n')
  )
  // Ordered image material — for routing (t2x / i2x / mi2x) and marking surplus.
  const imageItems = computed(() => items.value.filter((i) => i.kind === 'image' && i.src))

  // What the backend consumes: server paths, never the base64 preview. A data URL
  // in a GET query string never survives, so `src` must not reach a pipeline.
  const imagePaths = computed(() => imageItems.value.filter((i) => i.path).map((i) => i.path!))
  // Composable material: artifacts of the platform, addressed by their run.
  const audioItems = computed(() => items.value.filter((i) => i.kind === 'audio' && i.runId))
  const videoItems = computed(() => items.value.filter((i) => i.kind === 'video' && i.runId))
  const uploadsPending = computed(() => imageItems.value.some((i) => i.uploading))
  const uploadsFailed = computed(() => imageItems.value.some((i) => i.failed))
  const textCount = computed(
    () => items.value.filter((i) => i.kind === 'text' && i.text && i.text.trim()).length
  )

  return {
    items,
    pan,
    zoom,
    worldStyle,
    addText,
    addSource,
    addImage,
    addCode,
    addMedia,
    removeItem,
    setItems,
    zoomBy,
    resetView,
    startPan,
    startItemDrag,
    startItemResize,
    // The engine's own resize, for a card standing on the board that is not
    // material and carries no kind — the Flow's scene strip. The caller names the
    // mode, because the kind the wrapper above reads it from does not exist here.
    startCardResize: startItemResizeCore,
    onWheelZoom,
    combinedText,
    imageItems,
    audioItems,
    videoItems,
    imagePaths,
    uploadsPending,
    uploadsFailed,
    textCount,
  }
}
