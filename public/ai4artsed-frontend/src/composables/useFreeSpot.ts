/**
 * Where a new card is put down.
 *
 * The workshop board had this right and nothing else did: a product lands on a
 * FREE area of what is currently in view — never on top of another card, and
 * never under the standing words, because the voice is part of the scene. The
 * contesting surface rastered from a fixed corner and only avoided other cards,
 * so every card it made landed on the sentence the machine had just said. The
 * cards are dealt onto EMPTY areas.
 *
 * The rule is the same on every surface; only the coordinate system differs —
 * world coordinates under a pan/zoom board, plain page pixels without one. So
 * it is a pure function over rectangles and each surface hands in its own.
 *
 * The flow board asks from a place: what its plus brings in
 * lands on the free place nearest to where the plus puts it, and only on a
 * full view on that place itself, cascaded down and to the right past what
 * already lies there, as far as the view and its circles allow; past that it
 * lies where it covers the least. Until then every card from the plus fell
 * onto the same spot, one on top of the other.
 */
export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

/** A round obstacle, kept clear of as the circle it is drawn as (the flow board's ring). */
export interface Disc {
  x: number
  y: number
  r: number
}

export interface FreeSpotOptions {
  /** Clearance kept to every occupied rectangle, and to the edge of the view. */
  gap?: number
  /** Raster of the scan. Smaller finds tighter gaps and costs more. */
  step?: number
  /**
   * Where the card would lie on an empty board (its top-left). Given, the scan
   * runs outward from there and takes the free place NEAREST to it; a full
   * view puts the card on this place itself, shifted down and to the right in
   * `cascade` steps past what already has its corner there, as far as the view
   * and the circles in it allow.
   */
  near?: { x: number; y: number }
  /** How far from `near` a free place may lie. Default: anywhere in the view. */
  reach?: number
  /** One step of that shift. Default: the gap. */
  cascade?: number
}

function intersects(x: number, y: number, w: number, h: number, o: Rect | Disc, gap: number) {
  if ('r' in o) {
    const dx = Math.max(o.x - (x + w), 0, x - o.x)
    const dy = Math.max(o.y - (y + h), 0, y - o.y)
    return dx * dx + dy * dy < (o.r + gap) * (o.r + gap)
  }
  return x < o.x + o.w + gap && x + w + gap > o.x && y < o.y + o.h + gap && y + h + gap > o.y
}

/**
 * Scan the view top-left → bottom-right for a w×h place that touches nothing.
 * If the view is full, continue the scene just below its lowest occupant —
 * off-view, but reachable by panning, and in the order things were made.
 * With `near`, the scan and the fallback both start from that place instead.
 */
export function findFreeSpot(
  view: Rect,
  occupied: (Rect | Disc)[],
  w: number,
  h: number,
  opts: FreeSpotOptions = {}
): { x: number; y: number } {
  const gap = opts.gap ?? 28
  const step = opts.step ?? 40
  const x0 = view.x + gap
  const y0 = view.y + gap
  const xMax = view.x + view.w - w - gap
  const yMax = view.y + view.h - h - gap
  const free = (x: number, y: number) => !occupied.some(r => intersects(x, y, w, h, r, gap))
  const near = opts.near
  if (near) {
    // The raster runs through `near` itself, so an empty board gives exactly
    // that place; its points are tried nearest first.
    const reach = opts.reach ?? Infinity
    const spots: { x: number; y: number; d: number }[] = []
    for (let j = Math.ceil((y0 - near.y) / step); near.y + j * step <= yMax; j++) {
      for (let i = Math.ceil((x0 - near.x) / step); near.x + i * step <= xMax; i++) {
        const d = (i * i + j * j) * step * step
        if (d <= reach * reach) spots.push({ x: near.x + i * step, y: near.y + j * step, d })
      }
    }
    spots.sort((a, b) => a.d - b.d)
    const spot = spots.find(s => free(s.x, s.y))
    if (spot) return { x: spot.x, y: spot.y }
    // Nothing free: the place itself, one step down and to the right, and one
    // more for as long as something already has its corner on that step. The
    // steps stay in the view and clear of every round obstacle (on the flow
    // board the ring: a card inside it would change what the next run reads).
    // Where the next step would leave the view or reach a circle, the card
    // takes the place in the view that lies in no circle and covers the least
    // area of the rectangles handed in (summed, so a rectangle handed in twice
    // weighs twice), the nearest of those. Stepping on past the ring laid a
    // document card below the view on an iPad in landscape, and the nearest
    // place laid it over the prompt box.
    const c = opts.cascade ?? gap
    const inDisc = (x: number, y: number) =>
      occupied.some(o => 'r' in o && intersects(x, y, w, h, o, gap))
    const stacked = (x: number, y: number) =>
      occupied.some(o => !('r' in o) && Math.abs(o.x - x) < c / 2 && Math.abs(o.y - y) < c / 2)
    for (let k = 1; c > 0; k++) {
      const x = near.x + k * c
      const y = near.y + k * c
      if (x < x0 || y < y0 || x > xMax || y > yMax || inDisc(x, y)) break
      if (!stacked(x, y)) return { x, y }
    }
    const covered = (x: number, y: number) => {
      let a = 0
      for (const o of occupied) {
        if ('r' in o) continue
        const ow = Math.min(x + w, o.x + o.w) - Math.max(x, o.x)
        const oh = Math.min(y + h, o.y + o.h) - Math.max(y, o.y)
        if (ow > 0 && oh > 0) a += ow * oh
      }
      return a
    }
    let best: { x: number; y: number } | null = null
    let least = Infinity
    for (const s of spots) {
      if (inDisc(s.x, s.y)) continue
      const a = covered(s.x, s.y)
      if (a < least) {
        best = s
        least = a
      }
    }
    if (best) return { x: best.x, y: best.y }
    // No place in the view lies outside every circle (a view zoomed in until
    // the ring fills it): out of the circle before in the view, stepping down
    // and to the right until no circle reaches the card.
    let k = 0
    while (c > 0 && inDisc(near.x + k * c, near.y + k * c)) k++
    return { x: near.x + k * c, y: near.y + k * c }
  }
  for (let y = y0; y <= yMax; y += step) {
    for (let x = x0; x <= xMax; x += step) {
      if (free(x, y)) return { x, y }
    }
  }
  let bottom = y0
  for (const o of occupied) bottom = Math.max(bottom, 'r' in o ? o.y + o.r : o.y + o.h)
  return { x: x0, y: bottom + gap }
}
