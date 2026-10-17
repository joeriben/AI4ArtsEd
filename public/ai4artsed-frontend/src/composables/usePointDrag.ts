/**
 * THE FREE FIXTURE'S GESTURE — a sign lying on a view, moved by the pointer.
 *
 * WHAT THIS IS
 *   Every frameless sign the platform lays ON a view rather than into a bar is
 *   movable, and they all move the same way: press it, drag it, and the click
 *   that ends the drag does NOT count as a click. This is that gesture, once,
 *   for all of them. It works in SCREEN coordinates — these signs belong to the
 *   view, not to a world that pans and zooms under it.
 *
 * WHO USES IT
 *   The header fixtures of the flow canvas (`views/x2x_flow.vue`: the
 *   perspective sign and the plus), and the fixtures of the talking surfaces
 *   (`components/IntakePlus.vue`, `components/SurfaceGear.vue`). One gesture,
 *   one place, so a sign does not learn a different feel depending on which
 *   page it is standing on.
 *
 * THE CLICK GUARD
 *   `dragMoved()` stays true from the moment a gesture really moved something
 *   until the next gesture begins. Every handler that opens something on a
 *   click asks it first. A host with gestures of its own (a card being dragged
 *   across a board, say) folds them into the same guard with `markMoved()` and
 *   `resetMoved()`, so one flag answers for the whole view.
 */

/** Reads a length token off the document root; CSS owns the sizes. */
export function readCssPx(token: string, fallback: number): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(token)
  const n = parseFloat(raw)
  return Number.isFinite(n) ? n : fallback
}

/** The fixed footer gallery covers the bottom edge of every page. */
export function footerClear(): number {
  return readCssPx('--footer-collapsed-height', 36) + readCssPx('--flow-gutter', 18)
}

export interface PointDragOptions {
  /**
   * The box a fixture may not leave, in screen pixels. Defaults to the window.
   */
  bounds?: () => { width: number; height: number }
  /** Room kept free at the foot. Defaults to the footer gallery's. */
  inset?: () => number
  /** Called once per gesture, the moment it stops being a press and is a drag. */
  onMoved?: () => void
}

export function usePointDrag(opts: PointDragOptions = {}) {
  let obj: { x: number; y: number } | null = null
  let size = 96
  let lastX = 0
  let lastY = 0
  let startX = 0
  let startY = 0
  let slop = 4
  let moved = false
  let inset = 0

  function onMove(e: PointerEvent) {
    if (!obj) return
    const dx = e.clientX - lastX
    const dy = e.clientY - lastY
    // Measured from where the gesture STARTED, not per frame: a slow drag moves
    // 2px at a time and would never count. A finger never lands still, so its
    // slop has to be wider than a mouse's — at 3px per frame nearly every tap
    // on a fixture read as a drag, and the click at the end of it was swallowed.
    if (Math.abs(e.clientX - startX) > slop || Math.abs(e.clientY - startY) > slop) {
      if (!moved) opts.onMoved?.()
      moved = true
    }
    const b = opts.bounds?.() ?? { width: window.innerWidth, height: window.innerHeight }
    const maxX = Math.max(0, b.width - size)
    const maxY = Math.max(0, b.height - size - inset)
    obj.x = Math.min(Math.max(0, obj.x + dx), maxX)
    obj.y = Math.min(Math.max(0, obj.y + dy), maxY)
    lastX = e.clientX
    lastY = e.clientY
  }

  function onUp() {
    obj = null
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }

  /** Take hold of a point and move it with the pointer until it is let go. */
  function startPointDrag(e: PointerEvent, point: { x: number; y: number }) {
    obj = point
    // The dragged fixtures are sized by responsive CSS clamps; measure, don't guess.
    size = (e.currentTarget as HTMLElement | null)?.offsetWidth || 96
    lastX = e.clientX
    lastY = e.clientY
    startX = e.clientX
    startY = e.clientY
    slop = e.pointerType === 'touch' ? 10 : 4
    moved = false
    inset = (opts.inset ?? footerClear)() // read once; onMove runs per frame
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return {
    startPointDrag,
    /** True while the last gesture was a drag — ask before acting on a click. */
    dragMoved: () => moved,
    /** For a host whose own gestures answer to the same guard. */
    markMoved: () => { moved = true },
    resetMoved: () => { moved = false },
  }
}
