import { reactive, ref, computed } from 'vue'

export interface PanZoomOptions {
  /** Where the world sits when the view is reset. */
  initialPan?: { x: number; y: number }
  minZoom?: number
  maxZoom?: number
}

/**
 * The minimal geometry a board node must expose for the shared drag/resize/
 * z-order engine. Consumers keep their own richer item model (x2x' AsmItem,
 * Resona's product nodes); the engine only ever reads/writes these fields.
 */
export interface BoardItem {
  id: string
  x: number
  y: number
  w: number
  h: number
  /**
   * Stacking order. The engine writes it on bringToFront; a consumer that does
   * not bind it to z-index (x2x-flow) is visually unchanged.
   */
  z?: number
}

/**
 * How a resize handle behaves: 'aspect' keeps the width/height ratio (images,
 * video), 'free' lets both axes follow the pointer (prose, cards).
 */
export type ResizeMode = 'aspect' | 'free'

export interface ItemResizeOptions {
  mode?: ResizeMode
  minW?: number
  maxW?: number
  minH?: number
  maxH?: number
}

/**
 * Pan/zoom + item-interaction core — a fixed viewport onto a larger, pannable
 * and zoomable world. ONE `translate()scale()` transform on the world element;
 * only the world moves and scales (the deliberate Miro metaphor). Zoom moves
 * toward the cursor. Items are dragged and resized in world space (screen delta
 * ÷ zoom), lifted to the front on drag (z-order), and tracked for selection.
 *
 * The consumer's world element MUST carry `transform-origin: 0 0` in CSS — the
 * cursor-anchored zoom math assumes the origin is the world's top-left.
 *
 * Extracted from useAssemblageBoard so the assemblage board, the planning canvas
 * and the DAG canvas share one implementation instead of several (Rule #13 — no
 * parallel element structures). Pan/zoom behaviour is verbatim the board's;
 * consumers vary it through the options (initial pan, zoom bounds) and opt into
 * z-order/selection by binding `item.z` and `selectedId`.
 */
export function usePanZoom(opts: PanZoomOptions = {}) {
  const initialPan = opts.initialPan ?? { x: 0, y: 0 }
  const MIN_ZOOM = opts.minZoom ?? 0.4
  const MAX_ZOOM = opts.maxZoom ?? 2

  const pan = reactive({ x: initialPan.x, y: initialPan.y })
  const zoom = ref(1)

  const worldStyle = computed(() => ({
    transform: `translate(${Math.round(pan.x)}px, ${Math.round(pan.y)}px) scale(${zoom.value})`,
  }))

  function zoomBy(factor: number, cx?: number, cy?: number) {
    const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom.value * factor))
    if (next === zoom.value) return
    if (cx !== undefined && cy !== undefined) {
      // The world point under (cx, cy) stays put — zoom moves toward the cursor.
      pan.x = cx - ((cx - pan.x) / zoom.value) * next
      pan.y = cy - ((cy - pan.y) / zoom.value) * next
    }
    zoom.value = next
  }
  function reset() {
    zoom.value = 1
    pan.x = initialPan.x
    pan.y = initialPan.y
  }

  // Pan: drag on the empty board background.
  let panning = false
  let panX = 0
  let panY = 0
  function onPanMove(e: PointerEvent) {
    if (!panning) return
    pan.x += e.clientX - panX
    pan.y += e.clientY - panY
    panX = e.clientX
    panY = e.clientY
  }
  function endPan() {
    panning = false
    window.removeEventListener('pointermove', onPanMove)
    window.removeEventListener('pointerup', endPan)
    window.removeEventListener('pointercancel', endPan)
  }
  function startPan(e: PointerEvent) {
    panning = true
    panX = e.clientX
    panY = e.clientY
    window.addEventListener('pointermove', onPanMove)
    window.addEventListener('pointerup', endPan)
    window.addEventListener('pointercancel', endPan)
  }

  // Trackpads speak two dialects: a pinch arrives as wheel+ctrlKey, a two-finger
  // swipe as a plain wheel. The pinch zooms — smoothly, scaled by its own delta,
  // toward the cursor; the swipe pans. A mouse wheel pans too (zoom: ctrl+wheel
  // or the corner buttons). preventDefault keeps the browser's page zoom out.
  function onWheelZoom(e: WheelEvent) {
    e.preventDefault()
    const unit = e.deltaMode === 1 ? 16 : 1
    if (e.ctrlKey) {
      const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
      const factor = Math.min(1.25, Math.max(0.8, Math.exp(-e.deltaY * unit * 0.01)))
      zoomBy(factor, e.clientX - r.left, e.clientY - r.top)
    } else {
      pan.x -= e.deltaX * unit
      pan.y -= e.deltaY * unit
    }
  }

  // Selection + z-order — the Miro primitives a free planning canvas needs and
  // the assemblage board did without. `selectedId` drives a focus ring in the
  // consumer's template; `bringToFront` (run on drag start) stamps a rising `z`.
  // A consumer that binds neither is visually unchanged.
  const selectedId = ref<string | null>(null)
  let zCounter = 0
  function bringToFront(it: BoardItem) {
    zCounter += 1
    it.z = zCounter
  }
  function select(id: string | null) {
    selectedId.value = id
  }
  /**
   * After restoring persisted nodes, lift the counter above their highest `z`
   * so the next bringToFront still lands on top.
   */
  function primeZOrder(nodes: { z?: number }[]) {
    for (const n of nodes) if (n.z && n.z > zCounter) zCounter = n.z
  }

  // Item drag: screen delta ÷ zoom = world delta. Drag selects the node and
  // lifts it to the front; consumers that ignore z/selection see only the move.
  let dragged: BoardItem | null = null
  let dragX = 0
  let dragY = 0
  function onItemMove(e: PointerEvent) {
    if (!dragged) return
    dragged.x += (e.clientX - dragX) / zoom.value
    dragged.y += (e.clientY - dragY) / zoom.value
    dragX = e.clientX
    dragY = e.clientY
  }
  function endItemDrag() {
    dragged = null
    window.removeEventListener('pointermove', onItemMove)
    window.removeEventListener('pointerup', endItemDrag)
    window.removeEventListener('pointercancel', endItemDrag)
  }
  function startItemDrag(e: PointerEvent, it: BoardItem) {
    select(it.id)
    bringToFront(it)
    dragged = it
    dragX = e.clientX
    dragY = e.clientY
    window.addEventListener('pointermove', onItemMove)
    window.addEventListener('pointerup', endItemDrag)
    window.addEventListener('pointercancel', endItemDrag)
  }

  // Item resize: same screen→world conversion as the drag. In 'aspect' mode
  // width is the handle and height keeps the ratio; in 'free' mode both axes
  // follow the pointer. Bounds are per-call so a consumer can widen the ceiling.
  const DEFAULT_MIN_W = 80
  const DEFAULT_MAX_W = 1400
  const DEFAULT_MIN_H = 48
  const DEFAULT_MAX_H = 1400
  let resized: BoardItem | null = null
  let resizeMode: ResizeMode = 'aspect'
  let rMinW = DEFAULT_MIN_W
  let rMaxW = DEFAULT_MAX_W
  let rMinH = DEFAULT_MIN_H
  let rMaxH = DEFAULT_MAX_H
  let resizeX = 0
  let resizeY = 0
  function onItemResize(e: PointerEvent) {
    if (!resized) return
    const next = Math.min(rMaxW, Math.max(rMinW, resized.w + (e.clientX - resizeX) / zoom.value))
    if (resizeMode === 'free') {
      resized.h = Math.round(
        Math.min(rMaxH, Math.max(rMinH, resized.h + (e.clientY - resizeY) / zoom.value))
      )
    } else if (resized.w > 0 && resized.h > 0) {
      resized.h = Math.round((resized.h / resized.w) * next)
    }
    resized.w = Math.round(next)
    resizeX = e.clientX
    resizeY = e.clientY
  }
  function endItemResize() {
    resized = null
    window.removeEventListener('pointermove', onItemResize)
    window.removeEventListener('pointerup', endItemResize)
    window.removeEventListener('pointercancel', endItemResize)
  }
  function startItemResize(e: PointerEvent, it: BoardItem, opts: ItemResizeOptions = {}) {
    resized = it
    resizeMode = opts.mode ?? 'aspect'
    rMinW = opts.minW ?? DEFAULT_MIN_W
    rMaxW = opts.maxW ?? DEFAULT_MAX_W
    rMinH = opts.minH ?? DEFAULT_MIN_H
    rMaxH = opts.maxH ?? DEFAULT_MAX_H
    resizeX = e.clientX
    resizeY = e.clientY
    window.addEventListener('pointermove', onItemResize)
    window.addEventListener('pointerup', endItemResize)
    window.addEventListener('pointercancel', endItemResize)
  }

  return {
    pan,
    zoom,
    worldStyle,
    zoomBy,
    reset,
    startPan,
    onWheelZoom,
    selectedId,
    select,
    bringToFront,
    primeZOrder,
    startItemDrag,
    startItemResize,
  }
}
