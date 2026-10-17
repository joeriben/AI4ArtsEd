/**
 * The bubble ring: THE arrangement in which this platform puts something up for
 * choice — the kinds on a ring around the middle, and what hangs in a kind
 * blooming around it once it is open.
 *
 * The arithmetic was private to `components/InterceptionPresetOverlay.vue`
 * until the LoRAs were given the same circle, with its circumference as
 * flexible as possible. A second copy of it would have been a parallel
 * structure (docs/ELEMENT_STRUCTURE_REGISTRY.md), so it stands here and both
 * choosers read it.
 *
 * Every length is PERCENT OF THE SQUARE the bubbles stand in, which is what
 * `components/BubbleRingFrame.vue` draws. Two ways in:
 *  - the caller names the percentages it wants (the perspectives keep the ones
 *    they have always had: ring 35, kind 12, piece 14.5, bloom 14 to 30);
 *  - or `fitRing` is told how wide a piece should be IN PIXELS and how many of
 *    everything there is, and answers with the diameter the disc needs for it.
 *    Few kinds and few pieces make a small circle; what would leave the window
 *    is scaled down until it fits, which is why the percentages come back from
 *    the same call.
 */

export type RingPos = { x: number; y: number }

/**
 * Where the kinds stand: a ring around the middle, the first one up and to the
 * right (the ring starts at −π/4). A radius of 0 puts the one kind there is in
 * the middle.
 */
export function ringPositions(count: number, radiusPct: number, centre = 50): RingPos[] {
  if (count <= 0) return []
  const step = (2 * Math.PI) / count
  return Array.from({ length: count }, (_, i) => {
    const angle = i * step - Math.PI / 4
    return {
      x: centre + Math.cos(angle) * radiusPct,
      y: centre + Math.sin(angle) * radiusPct,
    }
  })
}

/**
 * How far from its kind the pieces of that kind stand. The ring widens with
 * what stands in it: a piece is `itemPct` wide, so neighbours need at least
 * that much room between them. Below `minPct` the ring would sit inside its
 * kind; beyond `maxPct` it would leave the square, and there it stops growing
 * and the pieces begin to cover one another.
 */
export function bloomDistancePct(
  count: number,
  itemPct: number,
  minPct: number,
  maxPct: number
): number {
  const gap = itemPct / (2 * Math.sin(Math.PI / Math.max(count, 2)))
  return Math.min(maxPct, Math.max(minPct, gap))
}

/**
 * Where the pieces of an open kind stand. The ring starts straight up — which
 * for a kind near the top edge is off the square, so those start downwards
 * instead: the same ring, mirrored.
 */
export function bloomPosition(
  cat: RingPos,
  count: number,
  distancePct: number,
  index: number
): RingPos {
  const angle = (index * 2 * Math.PI) / Math.max(count, 1) + (cat.y < 40 ? Math.PI / 2 : -Math.PI / 2)
  return {
    x: cat.x + Math.cos(angle) * distancePct,
    y: cat.y + Math.sin(angle) * distancePct,
  }
}

/** The whole ring at once, for a host that draws all of it. */
export function bloomPositions(cat: RingPos, count: number, distancePct: number): RingPos[] {
  if (count <= 0) return []
  return Array.from({ length: count }, (_, i) => bloomPosition(cat, count, distancePct, i))
}

/** What `fitRing` answers with: pixels for the frame, percent for the bubbles. */
export type FittedRing = {
  /** The disc, in px. */
  diameter: number
  /** The square the bubbles stand in, in px. */
  square: number
  ringPct: number
  catPct: number
  itemPct: number
  /** One bloom distance per kind, in the order the kinds were given. */
  bloomPct: number[]
}

/**
 * The proportions the perspectives' circle has always had, read off its
 * percentages and held in units of ONE PIECE so a fitted circle looks like the
 * one the platform already draws.
 */
const CAT_OF_ITEM = 12 / 14.5
const MIN_BLOOM = 14 / 14.5
/**
 * Where the kinds stand, in units of one piece. Two things set it: two kind
 * bubbles must not touch, and an open kind's ring must not swallow the kinds
 * next to it. Neither is capped, because a FITTED circle answers a crowd by
 * growing — where the perspectives let their pieces pass over their
 * neighbours, they do it to stay inside a disc whose size is already fixed.
 */
function ringRadius(kinds: number, widestBloom: number, centre: boolean): number {
  if (kinds <= 1 && !centre) return 0
  const chord = kinds > 1 ? 2 * Math.sin(Math.PI / kinds) : 2
  const apart = (CAT_OF_ITEM * 1.3) / chord
  const clear = (widestBloom + 0.5 + CAT_OF_ITEM / 2) / chord
  if (!centre) return Math.max(apart, clear)
  // A piece of its own stands in the middle, as wide as any other. An open
  // kind's ring reaches towards it as far as towards anything else, so the
  // kinds stand far enough out that the nearest piece of that ring keeps a
  // quarter of a piece of ground between itself and the middle one.
  const middle = widestBloom + 0.5 + 0.5 + 0.25
  return Math.max(apart, clear, middle)
}

/** Between the outermost piece and the rim, so nothing sits on the edge. */
const RIM = 0.25
/** How wide a piece is when the window leaves room for the size it wants. */
const ITEM_MIN_PX = 76
const ITEM_MAX_PX = 108
const ITEM_OF_VIEWPORT = 0.118

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

/**
 * The circle that fits what stands in it. `counts` is the number of pieces per
 * kind, in the order the kinds stand; `viewportPx` is the short side of the
 * window, which the disc may not leave.
 */
export function fitRing(opts: {
  counts: number[]
  viewportPx: number
  itemPx?: number
  /**
   * A piece stands in the middle of the disc (the Canvas's empty board, where
   * the perspectives hang "Du bestimmst!"). The kinds then stand on a ring even
   * when there is only one of them, and far enough out that no open kind's
   * ring covers the middle.
   */
  centre?: boolean
}): FittedRing {
  const { counts, viewportPx, centre = false } = opts
  // The disc may not leave the window — not even a window so short that what
  // is left is too small to be of use. A floor here would be a disc wider than
  // the screen it stands on.
  const cap = Math.max(1, viewportPx - 32)
  const wanted = opts.itemPx ?? clamp(ITEM_OF_VIEWPORT * viewportPx, ITEM_MIN_PX, ITEM_MAX_PX)
  const kinds = counts.length

  // In units of one piece: the bloom of each kind, the widest of them, and the
  // ring the kinds stand on.
  // No ceiling: at the perspectives' 30 % the pieces begin to cover one
  // another from thirteen on, and a covered piece cannot be taken. Here the
  // disc grows instead, and only the window ends that.
  const blooms = counts.map((n) => bloomDistancePct(n, 1, MIN_BLOOM, Infinity))
  const widest = blooms.length ? Math.max(...blooms) : MIN_BLOOM
  const ring = ringRadius(kinds, widest, centre)

  const radius = ring + widest + 0.5 + RIM
  let item = wanted
  let diameter = 2 * radius * item
  if (diameter > cap) {
    item = cap / (2 * radius)
    diameter = cap
  }
  const square = diameter
  const pct = (units: number) => ((units * item) / square) * 100
  return {
    diameter,
    square,
    ringPct: pct(ring),
    catPct: pct(CAT_OF_ITEM),
    itemPct: pct(1),
    bloomPct: blooms.map(pct),
  }
}
