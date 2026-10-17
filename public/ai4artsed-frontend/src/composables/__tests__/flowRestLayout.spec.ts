/**
 * The resting places of the x2x-Flow surface (`flowRestLayout.ts`), checked
 * where their fractions of the box "Vorbereitung" meet sizes that do not
 * scale with that box.
 *
 * For a window V px wide, the stage of x2x_flow.vue at zoom 1:
 *   - the band: `.map-wrap` is min(1000px, 100% - 32px) wide, centred, and
 *     10 px from the top of the view; the stage in it is 1060 x 150 units
 *     (`W`, `H`), so one unit is band / 1060 px, and the working surface
 *     begins under it;
 *   - the box "Vorbereitung": `RMAP.create`, x 110, y 20, 300 x 110 units;
 *   - the signs: `--flow-glyph-fixture` is clamp(3rem, 2.4vw + 1.6rem,
 *     4.125rem) at 16 px to the rem, the plus 1.35 times that
 *     (`--flow-glyph-plus`, flow-stage.css); the Flow page is as wide as the
 *     window;
 *   - the prompt box: the card adds its bar (18 px) and its border (1 px
 *     above and below) to the text field (FlowCard.vue);
 *   - the action zone of a first visit: radius 240, its middle under the
 *     middle of the generation box (`RMAP.gen`, x 520, 160 wide) and at world
 *     y 300, set while the view's offset is still 40; `frameBelowMap` then
 *     moves the view to the band's height + 60, which puts the middle 350 px
 *     under the band.
 *
 * From 1683 px on the signs stop growing, and the band stopped at 1032 px, so
 * a wider window only moves the band's left end, and the four with it.
 */
import { describe, it, expect } from 'vitest'
import { restingPlaces, JOG } from '../flowRestLayout'

interface Box {
  x: number
  y: number
  w: number
  h: number
}

const GAP = 8

function stage(V: number) {
  const band = Math.min(1000, V - 32)
  const u = band / 1060
  const bandLeft = (V - band) / 2
  const surfaceTop = 10 + 150 * u
  const glyph = Math.min(66, Math.max(48, 0.024 * V + 25.6))
  return {
    box: { left: bandLeft + 110 * u, bottom: 10 + 130 * u, width: 300 * u, height: 110 * u },
    surfaceTop,
    glyph,
    zone: { x: bandLeft + 600 * u, y: surfaceTop + 350, r: 240 },
  }
}

/** Every place the jog can carry a sign of this size to. */
function reach(c: { x: number; y: number }, size: number): Box {
  const j = JOG * size
  return { x: c.x - size / 2 - j, y: c.y - size / 2 - j, w: size + 2 * j, h: size + 2 * j }
}

/** How far apart two boxes lie along the axis that separates them most. */
function apart(a: Box, b: Box) {
  return Math.max(b.x - (a.x + a.w), a.x - (b.x + b.w), b.y - (a.y + a.h), a.y - (b.y + b.h))
}

function four(V: number) {
  const s = stage(V)
  const r = restingPlaces(s.box)
  return {
    s,
    boxes: {
      plus: reach(r.plus, 1.35 * s.glyph),
      lora: reach(r.lora, s.glyph),
      perspective: reach(r.perspective, s.glyph),
      promptBox: { ...r.promptBox, h: r.promptBox.h + 20 },
    } as Record<string, Box>,
  }
}

const WIDTHS = Array.from({ length: 2560 - 768 + 1 }, (_, i) => 768 + i)

describe('resting places of the x2x-Flow surface, 768 to 2560 px wide', () => {
  it('lie 8 px apart from each other, with every jog of the signs', () => {
    const bad: string[] = []
    for (const V of WIDTHS) {
      const entries = Object.entries(four(V).boxes)
      entries.forEach(([na, a], i) =>
        entries.slice(i + 1).forEach(([nb, b]) => {
          const d = apart(a, b)
          if (d < GAP) bad.push(`${V}px: ${na} / ${nb} ${d.toFixed(1)}`)
        })
      )
    }
    expect(bad).toEqual([])
  })

  it('lie under the band and 8 px inside the view', () => {
    const bad: string[] = []
    for (const V of WIDTHS) {
      const { s, boxes } = four(V)
      for (const [n, b] of Object.entries(boxes)) {
        if (b.y < s.surfaceTop + GAP) bad.push(`${V}px: ${n} reaches the band`)
        if (b.x < GAP || b.x + b.w > V - GAP) bad.push(`${V}px: ${n} reaches the edge`)
      }
    }
    expect(bad).toEqual([])
  })

  it('lie 8 px outside the action zone of a first visit', () => {
    const bad: string[] = []
    for (const V of WIDTHS) {
      const { s, boxes } = four(V)
      const z = s.zone
      for (const [n, b] of Object.entries(boxes)) {
        const dx = Math.max(b.x - z.x, 0, z.x - (b.x + b.w))
        const dy = Math.max(b.y - z.y, 0, z.y - (b.y + b.h))
        const d = Math.hypot(dx, dy) - z.r
        if (d < GAP) bad.push(`${V}px: ${n} ${d.toFixed(1)}`)
      }
    }
    expect(bad).toEqual([])
  })

  it('end at most 565 px below the top of the view', () => {
    const lowest = Math.max(
      ...WIDTHS.map((V) => Math.max(...Object.values(four(V).boxes).map((b) => b.y + b.h)))
    )
    expect(lowest).toBeLessThanOrEqual(565)
  })
})
