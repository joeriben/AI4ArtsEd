import { ref, computed, onMounted, onBeforeUnmount, type Ref } from 'vue'

export interface FlowRect {
  x: number
  y: number
  w: number
  h: number
}

/**
 * Flow stage layout — the resolution-aware counterpart to flow-stage.css.
 *
 * The map container is sized purely by CSS (--flow-map-h / --flow-map-h-receded);
 * this composable only measures it (ResizeObserver) and converts world-space
 * node geometry into real screen pixels. No CSS transform is involved, so text
 * inside nodes keeps its --flow-fs-* size at every map size — including while
 * the map recedes (the observer tracks the height transition frame by frame).
 */
// From a rectangle's centre, walk along (dx,dy) to the border; the nearer of
// the two axis limits is the crossing. Unit-agnostic (world px or screen px).
function borderPoint(cx: number, cy: number, hw: number, hh: number, dx: number, dy: number) {
  const s = Math.min(hw / (Math.abs(dx) || 1e-6), hh / (Math.abs(dy) || 1e-6))
  return { x: cx + dx * s, y: cy + dy * s }
}

/**
 * The two points where the straight centre-to-centre line crosses each box's
 * border. A connector should touch both edges HERE. Pinning an endpoint to a
 * side's mid-height only looks right for a horizontal neighbour; on a diagonal
 * it reads as aiming at the box's middle. Pass world rects or screen rects; the
 * returned units match the input.
 */
export function edgeBetween(
  a: { x: number; y: number; w: number; h: number },
  b: { x: number; y: number; w: number; h: number },
): [number, number, number, number] {
  const acx = a.x + a.w / 2
  const acy = a.y + a.h / 2
  const bcx = b.x + b.w / 2
  const bcy = b.y + b.h / 2
  const dx = bcx - acx
  const dy = bcy - acy
  const pa = borderPoint(acx, acy, a.w / 2, a.h / 2, dx, dy)
  const pb = borderPoint(bcx, bcy, b.w / 2, b.h / 2, -dx, -dy)
  return [pa.x, pa.y, pb.x, pb.y]
}

export function useFlowStage(worldW: number, worldH: number) {
  const mapEl: Ref<HTMLElement | null> = ref(null)
  const cw = ref(0)
  const ch = ref(0)

  let ro: ResizeObserver | null = null
  onMounted(() => {
    if (!mapEl.value) return
    const measure = () => {
      if (!mapEl.value) return
      cw.value = mapEl.value.clientWidth
      ch.value = mapEl.value.clientHeight
    }
    measure()
    ro = new ResizeObserver(measure)
    ro.observe(mapEl.value)
  })
  onBeforeUnmount(() => {
    ro?.disconnect()
  })

  const scale = computed(() => {
    if (!cw.value || !ch.value) return 0
    return Math.min(cw.value / worldW, ch.value / worldH)
  })
  const offX = computed(() => (cw.value - worldW * scale.value) / 2)
  const offY = computed(() => (ch.value - worldH * scale.value) / 2)

  function rect(r: FlowRect) {
    return {
      left: Math.round(offX.value + r.x * scale.value),
      top: Math.round(offY.value + r.y * scale.value),
      width: Math.round(r.w * scale.value),
      height: Math.round(r.h * scale.value),
    }
  }

  function rectStyle(r: FlowRect): Record<string, string> {
    const s = rect(r)
    return {
      left: `${s.left}px`,
      top: `${s.top}px`,
      width: `${s.width}px`,
      height: `${s.height}px`,
    }
  }

  /** Edge in screen px: the two natural border crossings of the centre-to-centre
      line (edgeBetween), so it touches the node edges instead of a side mid-height.
      Stroke stays 1px at every scale. */
  function line(a: FlowRect, b: FlowRect): [number, number, number, number] {
    const ra = rect(a)
    const rb = rect(b)
    return edgeBetween(
      { x: ra.left, y: ra.top, w: ra.width, h: ra.height },
      { x: rb.left, y: rb.top, w: rb.width, h: rb.height },
    )
  }

  /** Screen x of a node's center — anchor for the panel connector. */
  function anchorX(r: FlowRect): number {
    const s = rect(r)
    return s.left + Math.round(s.width / 2)
  }

  /** Below this on-screen width a node has no room for its label. */
  function isCompact(r: FlowRect): boolean {
    return r.w * scale.value < 76
  }

  return { mapEl, cw, ch, scale, rect, rectStyle, line, anchorX, isCompact }
}
