import { describe, it, expect } from 'vitest'
import { findFreeSpot, type Rect, type Disc } from '../useFreeSpot'

// x2x-flow asks from a place: material from the plus lands on the free place
// nearest to where the plus puts it, and on a full view cascades from there.
const view: Rect = { x: 0, y: 0, w: 1000, h: 700 }
const W = 250
const H = 140
const GAP = 16
const near = { x: 300, y: 200 }

function touches(a: Rect, b: Rect) {
  return a.x < b.x + b.w + GAP && a.x + a.w + GAP > b.x && a.y < b.y + b.h + GAP && a.y + a.h + GAP > b.y
}

describe('findFreeSpot from a place', () => {
  it('lays the card on the place itself while the board is empty', () => {
    expect(findFreeSpot(view, [], W, H, { gap: GAP, near })).toEqual(near)
  })

  it('takes the nearest free place, and every nearer one is taken', () => {
    const occupied: Rect[] = [
      { x: 280, y: 180, w: 300, h: 200 },
      { x: 0, y: 400, w: 420, h: 80 },
      { x: 600, y: 0, w: 60, h: 700 },
    ]
    const step = 10
    const s = findFreeSpot(view, occupied, W, H, { gap: GAP, step, near })
    const card = { x: s.x, y: s.y, w: W, h: H }
    expect(occupied.some((r) => touches(card, r))).toBe(false)
    expect(s.x).toBeGreaterThanOrEqual(view.x + GAP)
    expect(s.y).toBeGreaterThanOrEqual(view.y + GAP)
    expect(s.x + W + GAP).toBeLessThanOrEqual(view.x + view.w)
    expect(s.y + H + GAP).toBeLessThanOrEqual(view.y + view.h)
    const d = Math.hypot(s.x - near.x, s.y - near.y)
    expect(d).toBeGreaterThan(0)
    for (let y = near.y - 70 * step; y <= view.h; y += step) {
      for (let x = near.x - 100 * step; x <= view.w; x += step) {
        const inView = x >= GAP && y >= GAP && x + W + GAP <= view.w && y + H + GAP <= view.h
        if (!inView || Math.hypot(x - near.x, y - near.y) >= d - 1e-9) continue
        expect(occupied.some((r) => touches({ x, y, w: W, h: H }, r))).toBe(true)
      }
    }
  })

  it('keeps clear of a disc as the circle it is, not as its bounding square', () => {
    const ring: Disc = { x: 500, y: 500, r: 200 }
    const at = { x: 100, y: 170 }
    const square = { x: ring.x - ring.r, y: ring.y - ring.r, w: 2 * ring.r, h: 2 * ring.r }
    expect(touches({ ...at, w: W, h: H }, square)).toBe(true)
    expect(findFreeSpot(view, [ring], W, H, { gap: GAP, near: at })).toEqual(at)
    const inside = findFreeSpot(view, [ring], W, H, { gap: GAP, step: 8, near: { x: 380, y: 380 } })
    const dx = Math.max(ring.x - (inside.x + W), 0, inside.x - ring.x)
    const dy = Math.max(ring.y - (inside.y + H), 0, inside.y - ring.y)
    expect(Math.hypot(dx, dy)).toBeGreaterThanOrEqual(ring.r + GAP)
  })

  it('looks no farther than `reach`, and cascades where nothing within it is free', () => {
    const wall: Rect[] = [{ x: 0, y: 0, w: 600, h: 700 }]
    const from = { x: 100, y: 100 }
    const opts = { gap: GAP, step: 8, near: from, cascade: 20 }
    const far = findFreeSpot(view, wall, W, H, { ...opts, reach: 600 })
    expect(far.x).toBeGreaterThanOrEqual(600 + GAP)
    expect(findFreeSpot(view, wall, W, H, { ...opts, reach: 300 })).toEqual({ x: 120, y: 120 })
  })

  it('cascades from the place down and to the right when nothing is free', () => {
    const full: Rect[] = [{ x: 0, y: 0, w: 1000, h: 700 }]
    const opts = { gap: GAP, near, cascade: 20 }
    const first = findFreeSpot(view, full, W, H, opts)
    expect(first).toEqual({ x: 320, y: 220 })
    const second = findFreeSpot(view, [...full, { ...first, w: W, h: H }], W, H, opts)
    expect(second).toEqual({ x: 340, y: 240 })
    const third = findFreeSpot(view, [...full, { ...first, w: W, h: H }, { ...second, w: W, h: H }], W, H, opts)
    expect(third).toEqual({ x: 360, y: 260 })
  })

  it('keeps a card on a full view out of the ring and in the view where the view has room', () => {
    const full: Rect[] = [{ x: 0, y: 0, w: 1000, h: 700 }]
    const inView = (s: { x: number; y: number }, w: number, h: number) =>
      s.x >= view.x + GAP && s.y >= view.y + GAP && s.x + w + GAP <= view.x + view.w && s.y + h + GAP <= view.y + view.h
    const clear = (s: { x: number; y: number }, ring: Disc, w: number, h: number) =>
      Math.hypot(Math.max(ring.x - (s.x + w), 0, s.x - ring.x), Math.max(ring.y - (s.y + h), 0, s.y - ring.y)) >=
      ring.r + GAP
    const opts = { gap: GAP, step: 8, cascade: 20 }
    // The place itself lies in the ring.
    const ring: Disc = { x: 400, y: 300, r: 150 }
    const a = findFreeSpot(view, [...full, ring], W, H, { ...opts, near })
    expect(clear(a, ring, W, H)).toBe(true)
    expect(inView(a, W, H)).toBe(true)
    // The ring lies on the way down and to the right, and past it is the edge:
    // a large card, as a document card on an iPad in landscape.
    const big = { w: 340, h: 280 }
    const wide: Disc = { x: 620, y: 420, r: 240 }
    const from = { x: 20, y: 50 }
    const b = findFreeSpot(view, [...full, wide], big.w, big.h, { ...opts, near: from })
    expect(clear(b, wide, big.w, big.h)).toBe(true)
    expect(inView(b, big.w, big.h)).toBe(true)
    // The place sits at the bottom right edge, so no step fits.
    const edge = findFreeSpot(view, full, W, H, { ...opts, near: { x: 700, y: 530 } })
    expect(inView(edge, W, H)).toBe(true)
    // The place lies above and left of the view: a card taller and wider than
    // the landing point is kept in from the edges.
    const tall = { w: 340, h: 300 }
    const out = findFreeSpot(view, [...full, wide], tall.w, tall.h, { ...opts, near: { x: -28, y: -58 } })
    expect(inView(out, tall.w, tall.h)).toBe(true)
    expect(clear(out, wide, tall.w, tall.h)).toBe(true)
  })

  it('lays a card that cannot step on where it covers the least, the nearest of those', () => {
    const full: Rect[] = [{ x: 0, y: 0, w: 1000, h: 700 }]
    const ring: Disc = { x: 800, y: 350, r: 150 }
    const promptBox: Rect = { x: 40, y: 400, w: 300, h: 200 }
    const sign: Rect = { x: 40, y: 40, w: 60, h: 60 }
    const s = findFreeSpot(view, [...full, ring, promptBox, sign], 340, 280, {
      gap: GAP,
      step: 8,
      near: { x: 40, y: 400 },
      cascade: 20,
    })
    expect(s).toEqual({ x: 40, y: 120 })
  })

  it('lays a card out of a ring that fills the view, off the view if need be', () => {
    const ring: Disc = { x: 500, y: 350, r: 800 }
    const s = findFreeSpot(view, [ring], W, H, { gap: GAP, step: 8, near, cascade: 20 })
    const dx = Math.max(ring.x - (s.x + W), 0, s.x - ring.x)
    const dy = Math.max(ring.y - (s.y + H), 0, s.y - ring.y)
    expect(Math.hypot(dx, dy)).toBeGreaterThanOrEqual(ring.r + GAP)
  })

  it('keeps the next card off the corner of the one laid there before', () => {
    const full: Rect[] = [{ x: 0, y: 0, w: 1000, h: 700 }]
    const ring: Disc = { x: 400, y: 300, r: 150 }
    const opts = { gap: GAP, step: 8, near, cascade: 20 }
    const first = findFreeSpot(view, [...full, ring], W, H, opts)
    const second = findFreeSpot(view, [...full, ring, { ...first, w: W, h: H }], W, H, opts)
    expect(Math.abs(second.x - first.x) >= 10 || Math.abs(second.y - first.y) >= 10).toBe(true)
  })

  it('keeps the scan from the top left without a place', () => {
    expect(findFreeSpot(view, [], W, H)).toEqual({ x: 28, y: 28 })
    expect(findFreeSpot(view, [{ x: 0, y: 0, w: 1000, h: 700 }], W, H)).toEqual({ x: 28, y: 728 })
  })
})
