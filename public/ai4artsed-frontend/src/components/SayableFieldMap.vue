<template>
  <div class="field-map" :class="{ bare }">
    <div v-if="!bare" class="fm-head">{{ t('surrealizer.field.heading') }}</div>
    <canvas ref="cvRef" class="fm-canvas" width="700" height="410" aria-hidden="true"></canvas>
    <!-- The two coefficients ARE the fused core. -->
    <div class="fm-ro">V =
      <b :class="['fm-num', clipInv ? 'fm-inv' : 'fm-clip']">{{ fmt(kc) }}</b>·CLIP
      <b :class="['fm-num', t5Inv ? 'fm-inv' : 'fm-t5']">{{ kt < 0 ? '−' : '+' }} {{ fmt(Math.abs(kt)) }}</b>·T5
    </div>
    <div v-if="!bare" class="fm-note">{{ t('surrealizer.field.note') }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { alphaScaleFor, fusionWeights } from '@/lib/fusionWeights'
import type { FusionStrategy } from '@/lib/fusionWeights'

const props = defineProps<{
  alpha: number
  strategy?: FusionStrategy
  /**
   * How much of the card is drawn. 'bare' keeps the picture and the
   * coefficients and drops the heading and the note, for a column that names
   * the setting above the picture. Same idiom as MediaInputBox's `chrome`.
   */
  chrome?: 'full' | 'bare'
}>()
const bare = computed(() => props.chrome === 'bare')
const { t, locale } = useI18n()

const cvRef = ref<HTMLCanvasElement | null>(null)

/*
 * The stage. Its size is DERIVED, not chosen: over the whole range of both axes
 * the drawing reaches 301 px left, 315 right, 170 up and 162 down of the origin
 * (measured over every alpha at 0.02 / 0.1 steps, tip and joint alike), and the
 * margins are what the arrowhead, the dot and the 'V' need beside them. The
 * canvas was 680 x 450 with the origin in the middle, which left unused ground
 * at the bottom. The height is 40 px shorter now — and the rest of that room
 * went into the circle, which is why it no longer stands in an empty field.
 */
const O = { x: 348, y: 210 }
/*
 * CLIP lies to the LEFT and T5 to the RIGHT, in the same order as the slider
 * above the picture: its left end is CLIP alone, its right end is T5 alone.
 * The two once stood the other way round, and the picture then ran AGAINST
 * the hand — pushing the slider right swung V left, at every setting, because
 * "more T5, less CLIP" is a leftward move as long as T5 points left. The two
 * are still exactly orthogonal (dot product 0 to the digit), only mirrored in
 * x, so every length in the drawing is unchanged and the derived margins above
 * still hold (they swap sides: 315 left, 301 right, against 348 and 352
 * available).
 */
const CL = { x: -0.966, y: -0.259 }
const T5 = { x: 0.259, y: -0.966 }
const Lc = 70
const Lt = 44

/**
 * Where the compression starts, in WORLD units: a V no longer than this is
 * drawn true to scale. It is the meaning of the dashed circle and it does not
 * change with the scale the world is drawn at.
 */
const V0 = 90

/**
 * How large the true-to-scale world is DRAWN: the circle at 180%.
 * The circle therefore stands at S x V0 = 162 px while still meaning |V| = 90,
 * and everything inside it grows with it — the two anchors come out at 126 px
 * (only CLIP) and 79 px (only T5). What must NOT happen is R0 being raised
 * instead: that would move the threshold itself to |V| = 162, past the longest
 * V that centered fade can reach at all (147), and its arrow would never leave
 * the circle again.
 */
const S = 1.8
const R0 = S * V0
const MAXR = 315

/**
 * How hard the outside is bent. The whole outside is squeezed between R0 and
 * MAXR no matter what, so this only says WHERE in that band the middle of the
 * range lands: higher means the first steps out of the circle move further and
 * the last steps move less. At 4 the midpoint of the outer range sits at 58 %
 * of the band.
 */
const BEND = 4

// The numbers under the picture and the picture itself now come from the same
// place. They did not: the readout knew the strategy, worldV() below did not,
// so under centered_fade the arrows drew one thing and the line beneath them
// said another.
const weights = computed(() => fusionWeights(props.alpha, props.strategy))
const kc = computed(() => weights.value.clip)
const kt = computed(() => weights.value.t5)
const clipInv = computed(() => kc.value < 0)
const t5Inv = computed(() => kt.value < 0)

/**
 * Where the tip of V stands, in world units: the sum of the two legs, and
 * `ax`/`ay` is the joint the picture draws between them.
 */
function worldV() {
  const ax = kc.value * Lc * CL.x
  const ay = kc.value * Lc * CL.y
  const bx = kt.value * Lt * T5.x
  const by = kt.value * Lt * T5.y
  return { ax, ay, vx: ax + bx, vy: ay + by }
}

/**
 * The longest V this axis can reach — the further of its two ends.
 *
 * CLIP and T5 are drawn exactly orthogonal (their dot product is 0 to the digit),
 * so the length is the hypotenuse of the two legs and no vector is needed here.
 *
 * This is what the outer edge of the picture MEANS, and it is why the scale
 * cannot be a constant. Until 2026-08-22 the compression ran on a fixed
 * K = 125 px, which fit neither axis it had to serve:
 *
 *   - legacy/dual_alpha go to alpha +/-75. The arrow reached 314.6 of 315 px at
 *     alpha -10 already, so from there to the end of the slider - 86 % of its
 *     travel - the picture did not move at all.
 *   - centered_fade went to alpha +/-2. Its longest V was 147 px of world,
 *     which the same formula put at r = 172; the edge was never reached at any
 *     setting the slider offered. That axis opened to +/-75 on 2026-08-22.
 *
 * Now the end of the slider lands on the edge, in both. The near end of an
 * asymmetric axis stays short of it, because it IS shorter - the picture shows
 * length, and two settings of equal length must be drawn at equal radius
 * whatever their sign.
 */
const vMax = computed(() => {
  const { min, max } = alphaScaleFor(props.strategy)
  const len = (a: number) => {
    const w = fusionWeights(a, props.strategy)
    return Math.hypot(w.clip * Lc, w.t5 * Lt)
  }
  return Math.max(len(min), len(max))
})

function warp(px: number, py: number) {
  const dx = px - O.x
  const dy = py - O.y
  const d = Math.hypot(dx, dy)
  if (d < 0.5) return { x: O.x, y: O.y }
  // Inside the circle: true to scale, at the scale the circle is drawn at.
  const span = vMax.value - V0
  let rs = S * d
  if (d > V0 && span > 0) {
    const u = Math.min((d - V0) / span, 1)
    rs = R0 + (MAXR - R0) * ((1 - Math.exp(-BEND * u)) / (1 - Math.exp(-BEND)))
  }
  return { x: O.x + (dx / d) * rs, y: O.y + (dy / d) * rs }
}

function fmt(x: number) {
  return x.toFixed(2).replace('.', ',')
}

function arrow(ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number, col: string, wd: number) {
  ctx.strokeStyle = col
  ctx.fillStyle = col
  ctx.lineWidth = wd
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()
  const a = Math.atan2(y2 - y1, x2 - x1)
  const h = 9 + wd
  ctx.beginPath()
  ctx.moveTo(x2, y2)
  ctx.lineTo(x2 - h * Math.cos(a - 0.4), y2 - h * Math.sin(a - 0.4))
  ctx.lineTo(x2 - h * Math.cos(a + 0.4), y2 - h * Math.sin(a + 0.4))
  ctx.closePath()
  ctx.fill()
}

function dot(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, col: string) {
  ctx.fillStyle = col
  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  ctx.fill()
}

function label(ctx: CanvasRenderingContext2D, txt: string, x: number, y: number, col: string, sz: number, al: CanvasTextAlign) {
  ctx.fillStyle = col
  // Canvas text takes no CSS variable, so the platform's typeface is named
  // here in full. It is the same face as everywhere else (--font-sans).
  ctx.font = sz + "px 'Source Sans 3 Variable', 'Source Sans 3', system-ui, sans-serif"
  ctx.textAlign = al
  ctx.fillText(txt, x, y)
  ctx.textAlign = 'left'
}

function draw() {
  const cv = cvRef.value
  if (!cv) return
  const ctx = cv.getContext('2d')
  if (!ctx) return
  const dpr = window.devicePixelRatio || 1
  if (cv.width !== 700 * dpr) {
    cv.width = 700 * dpr
    cv.height = 410 * dpr
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, 700, 410)

  const g = ctx.createRadialGradient(O.x, O.y, 0, O.x, O.y, 405)
  g.addColorStop(0, '#2b3648')
  g.addColorStop(0.22, '#252f3f')
  g.addColorStop(0.5, '#131820')
  g.addColorStop(1, '#000000')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 700, 410)

  ctx.strokeStyle = 'rgba(90,200,170,0.55)'
  ctx.lineWidth = 1
  ctx.setLineDash([5, 5])
  ctx.beginPath()
  ctx.arc(O.x, O.y, R0, 0, Math.PI * 2)
  ctx.stroke()
  ctx.setLineDash([])

  // Nothing is written over the circle. Two lines once stood there and said
  // how the drawing had been scaled — inside true to scale, outside
  // compressed, the rim at the end of the slider. That is how the picture was
  // made, not what it shows, and it has no more business in it than the point
  // size of a letter has on the letter. The circle keeps its dashes and the
  // arrows their names.

  const pc = warp(O.x + Lc * CL.x, O.y + Lc * CL.y)
  const pt = warp(O.x + Lt * T5.x, O.y + Lt * T5.y)
  dot(ctx, pc.x, pc.y, 5, 'rgba(74,158,255,0.5)')
  label(ctx, t('surrealizer.field.onlyClip'), pc.x + 11, pc.y + 6, 'rgba(74,158,255,0.7)', 18, 'left')
  dot(ctx, pt.x, pt.y, 5, 'rgba(240,169,64,0.5)')
  label(ctx, t('surrealizer.field.onlyT5'), pt.x + 11, pt.y + 6, 'rgba(240,169,64,0.75)', 18, 'left')

  const w = worldV()
  const dV = Math.hypot(w.vx, w.vy)
  const out = dV > R0
  const tV = warp(O.x + w.vx, O.y + w.vy)
  const tA = warp(O.x + w.ax, O.y + w.ay)
  arrow(ctx, O.x, O.y, tA.x, tA.y, clipInv.value ? '#e0568a' : '#4a9eff', 3.5)
  arrow(ctx, tA.x, tA.y, tV.x, tV.y, t5Inv.value ? '#e0568a' : '#f0a940', 3.5)
  arrow(ctx, O.x, O.y, tV.x, tV.y, out ? '#e0568a' : '#eef2f8', 4.5)
  dot(ctx, tV.x, tV.y, 6, out ? '#e0568a' : '#eef2f8')
  label(ctx, 'V', tV.x + 13, tV.y + 6, out ? '#e0568a' : '#eef2f8', 24, 'left')
  dot(ctx, O.x, O.y, 5, '#9aa4b2')
  label(ctx, t('surrealizer.field.promptLabel'), O.x - 11, O.y + 26, '#9aa4b2', 19, 'right')
}

onMounted(draw)
// The five labels that stand INSIDE the picture are drawn, not rendered, so
// nothing re-runs draw() when the interface language changes: the heading above
// the canvas and the line below it switched, the words in it did not.
watch(() => [props.alpha, props.strategy, locale.value], draw)
</script>

<style scoped>
.field-map {
  width: 100%;
}
.fm-head {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 0.5rem;
}
.fm-canvas {
  width: 100%;
  height: auto;
  aspect-ratio: 700 / 410;
  display: block;
  border-radius: 12px;
}
.fm-ro {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 16px;
  margin: 0.7rem 0;
  color: rgba(255, 255, 255, 0.85);
}
/* In a column the picture has to fit the room it is GIVEN. With width:100% the
   aspect made the height follow the width, so at 880px of column the picture
   came out 580px tall in a 320px box and ran out of the bottom, painting over
   the lines under it and pushing the coefficients off the screen. Here the
   height leads and the width follows it. */
/* The floor is the PAGE's to set, through --fm-min: a scoped rule from outside
   cannot reach past this one's own specificity, and a map squeezed to 47px by a
   result surface pulled open is no longer a map. Default 0 — free to shrink, as
   it was. */
.field-map.bare {
  display: flex;
  flex-direction: column;
  min-height: var(--fm-min, 0);
}

/*
 * The drawing keeps its shape. This once said `flex: 1` with `width: auto`
 * and `max-width: 100%`: flex sets the HEIGHT, the aspect ratio then wants a
 * width to match, and the max-width cuts it off — so in every column taller
 * than 700:410 the 700 x 410 bitmap was stretched into a taller box and the
 * circle came out an egg.
 *
 * `object-fit: contain` is the fix and not a workaround: a canvas is replaced
 * content with an intrinsic size, so it letterboxes inside whatever box it is
 * given instead of being scaled unevenly into it. The box may then be any
 * shape; the picture in it stays round.
 */
.field-map.bare .fm-canvas {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: auto;
  object-fit: contain;
  margin: 0 auto;
}

/* Nothing follows the line in the slim form, so it does not carry a gap under
   it, and it sits at the size of the numbers around it in a column. */
.field-map.bare .fm-ro {
  font-size: 14px;
  margin: 0.55rem 0 0;
  text-align: center;
}
.fm-ro b {
  font-weight: 700;
}
.fm-clip {
  color: #4a9eff;
}
.fm-t5 {
  color: #f0a940;
}
.fm-inv {
  color: #e0568a;
}
.fm-note {
  font-size: 12.5px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.55;
  border-top: 0.5px solid rgba(255, 255, 255, 0.1);
  padding-top: 0.6rem;
}
</style>
