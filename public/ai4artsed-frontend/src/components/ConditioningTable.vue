<!--
  The conditioning table of SD 3.5 under three factors — the drawing of the
  Encoder Fusion instrument.

  What is drawn is the table the model conditions on: 589 rows by 4096
  columns. On top the block the two CLIP encoders fill, 77 rows, its columns
  2048..4095 zero; under it the T5 block, 512 rows, all columns. The rows are
  drawn to scale (77 : 512), which is why the CLIP block is the thin band: that
  proportion is part of what the drawing says. The columns split at 2048.

  Which rows the T5 block holds is the drawing's fourth input, `t5Rows`:
  `full`, rows 0..511, the head 0..76 the block's own top; or `tail`, rows
  77..511 alone, the earlier layout of the Surrealizer. Under `tail` the block
  starts two units under the head, at row 77, and ends where the full block
  ends; the head stands apart between the blocks, unfilled, and only the arrow
  b carries it into the CLIP block, which is where it then exists.

  The pooled vector is the drawing's fifth input, `pooled`: the bar over the
  CLIP block, as wide as columns 0..2047. CLIP-L and CLIP-G compute it, 768
  and 1280 numbers joined, and the
  model reads it beside the table, in the modulation of every block (Esser et
  al. 2024, section 4: embeddings of the timestep and of this vector are the
  inputs to the modulation mechanism); T5 computes none. Under `clip` the bar
  is filled and the vector goes to the model as computed; under `zero` the
  bar stands empty and zeros of the same shape go in its place, which is what
  ComfyUI itself puts there when no CLIP encoder runs
  (comfy/text_encoders/sd3_clip.py).

  The three factors of the sliders under it are the three things that can be
  done to this table, and each is drawn where it acts: a fills the CLIP block,
  b fills the CLIP block a second time with T5's colour (its right half from
  nothing, since CLIP leaves those columns zero) and stands at the arrow that
  carries T5's rows 0..76 up into the block, c fills the T5 block. A fill's
  opacity is the factor's magnitude, capped at 1; a negative factor lays a
  hatch over its block, and the sign is in the number beside the slider. The
  arrow keeps a floor of 0.3 so the operation stays visible at b = 0.

  Colours: CLIP #3f6a9c and the number blue of the station drawings, T5
  #9c6a3f; green is not used here (docs/latent_lab_station_design.md, R19).
  CLIP and T5 are proper nouns and stay as they are in every language.
-->
<template>
  <svg
    class="ct"
    :viewBox="`0 0 ${W} ${H}`"
    role="img"
    :aria-label="t('surrealizer.tableLabel')"
  >
    <defs>
      <pattern :id="hatchId" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(255,255,255,0.35)" stroke-width="1" />
      </pattern>
    </defs>

    <!-- the columns -->
    <text :x="left" y="9" class="ct-dim">{{ t('surrealizer.table.columnsClip') }}</text>
    <text :x="left + half + 4" y="9" class="ct-dim">{{ t('surrealizer.table.columnsRest') }}</text>

    <!-- the pooled vector: the bar over the CLIP block, as wide as the columns
         CLIP fills; filled while the model reads the vector, empty under zeros -->
    <rect :x="left" :y="yPool" :width="half" :height="poolH" fill="#3f6a9c" :fill-opacity="zeroPool ? 0 : 1" />
    <rect :x="left" :y="yPool" :width="half" :height="poolH" fill="none" stroke="#6a7a8c" stroke-width="1" />
    <text :x="left + half + 4" :y="yPool + poolH - 0.5" class="ct-dim">{{ t(zeroPool ? 'surrealizer.table.poolZero' : 'surrealizer.table.poolClip') }}</text>
    <text :x="left - 4" :y="yPool + poolH - 0.5" class="ct-dim" text-anchor="end">{{ t('surrealizer.table.pool') }}</text>

    <!-- the CLIP block: a on the block, b of T5 over it, the right half T5's alone -->
    <rect :x="left" :y="yClip" :width="half" :height="clipH" fill="#3f6a9c" :fill-opacity="op(fa)" />
    <rect :x="left" :y="yClip" :width="half" :height="clipH" fill="#9c6a3f" :fill-opacity="op(fb) * 0.55" />
    <rect v-if="fa < 0" :x="left" :y="yClip" :width="half" :height="clipH" :fill="`url(#${hatchId})`" />
    <rect :x="left + half" :y="yClip" :width="gw - half" :height="clipH" fill="#9c6a3f" :fill-opacity="op(fb)" />
    <rect v-if="fb < 0" :x="left + half" :y="yClip" :width="gw - half" :height="clipH" :fill="`url(#${hatchId})`" />
    <rect :x="left" :y="yClip" :width="gw" :height="clipH" fill="none" stroke="#6a7a8c" stroke-width="1" />
    <line :x1="left + half" :y1="yClip" :x2="left + half" :y2="yClip + clipH" stroke="#6a7a8c" stroke-dasharray="2 2" />
    <text :x="left + 4" :y="yClip + clipH / 2 + 3.5" class="ct-formula">a·CLIP + b·T5</text>
    <text :x="left + half + 4" :y="yClip + clipH / 2 + 3.5" class="ct-formula">0 + b·T5</text>

    <!-- the T5 block: c on the block, its rows 0..76 marked as the head b
         takes. Under the full layout the head is the block's top; under the
         tail layout the block starts below it, at row 77, and the head
         stands apart. -->
    <rect :x="left" :y="yBlock" :width="gw" :height="blockH" fill="#9c6a3f" :fill-opacity="op(fc)" />
    <rect v-if="fc < 0" :x="left" :y="yBlock" :width="gw" :height="blockH" :fill="`url(#${hatchId})`" />
    <rect :x="left" :y="yBlock" :width="gw" :height="blockH" fill="none" stroke="#8c7a6a" stroke-width="1" />
    <rect :x="left" :y="yT5" :width="gw" :height="headH" fill="none" stroke="#e0c9a6" stroke-width="1" stroke-dasharray="3 2" />
    <text :x="left + 4" :y="yT5 + headH / 2 + 3.5" class="ct-formula">{{ t('surrealizer.table.t5Head') }}</text>
    <text :x="left + 4" :y="yBlock + blockH / 2 + 12" class="ct-formula">c·T5</text>

    <!-- the rows, numbered at the edges of each block -->
    <g class="ct-dim" text-anchor="end">
      <text :x="left - 4" :y="yClip + 8">0</text>
      <text :x="left - 4" :y="yClip + clipH - 1">76</text>
      <text :x="left - 4" :y="yT5 + 8">0</text>
      <text :x="left - 4" :y="yT5 + headH - 1">76</text>
      <text v-if="tail" :x="left - 4" :y="yBlock + 8">77</text>
      <text :x="left - 4" :y="yT5 + t5H - 1">511</text>
    </g>
    <g class="ct-name">
      <text :x="left + gw + 3" :y="yClip + clipH / 2 + 3">CLIP</text>
      <text :x="left + gw + 3" :y="yBlock + blockH / 2 + 3">T5</text>
    </g>

    <!-- b: T5's rows 0..76 up into the CLIP block -->
    <g stroke="#e0c9a6" fill="#e0c9a6" :stroke-opacity="arrowOp" :fill-opacity="arrowOp">
      <line :x1="left + gw - 10" :y1="yT5 + headH / 2" :x2="left + gw - 10" :y2="yClip + clipH - 3" stroke-width="1.5" />
      <polygon :points="`${left + gw - 10},${yClip + clipH - 5} ${left + gw - 14},${yClip + clipH + 1} ${left + gw - 6},${yClip + clipH + 1}`" />
    </g>
    <text :x="left + gw - 16" :y="yT5 + headH / 2 + 3" class="ct-b" text-anchor="end">b</text>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(defineProps<{
  a: number
  b: number
  c: number
  /** Which rows the T5 block holds: all 512, or rows 77..511 alone. */
  t5Rows?: 'full' | 'tail'
  /** The pooled vector beside the table: as CLIP computes it, or zeros in its place. */
  pooled?: 'clip' | 'zero'
}>(), { t5Rows: 'full', pooled: 'clip' })
const { t } = useI18n()

// One pattern id per instance: two drawings on one page would otherwise share
// one <pattern>, and the second would draw the first's.
const hatchId = `ct-neg-${Math.random().toString(36).slice(2, 8)}`

/*
 * The geometry, in the drawing's own units. The SVG scales to the width it is
 * given (`width: 100%`), so nothing here is a pixel; at 303 units of width the
 * drawing renders 1:1 in the column it was designed for.
 */
const W = 303
const H = 168
const left = 34
// the bar of the pooled vector stands in the head band, over the blocks
const yPool = 12
const poolH = 6
const top = 22
const right = 26
const bottom = 6
const gap = 5
const gw = W - left - right
const gh = H - top - bottom
// rows to scale: 77 CLIP rows over 512 T5 rows
const unit = (gh - gap) / (77 + 512)
const clipH = 77 * unit
const t5H = 512 * unit
const headH = 77 * unit
// columns split at 2048 of 4096
const half = gw * 2048 / 4096
const yClip = top
const yT5 = top + clipH + gap

const tail = computed(() => props.t5Rows === 'tail')
// The block's extent: all 512 rows, or rows 77..511 alone, two units under
// the head that then stands apart. The head itself never moves.
const yBlock = computed(() => tail.value ? yT5 + headH + 2 : yT5)
const blockH = computed(() => tail.value ? t5H - headH - 2 : t5H)
// The bar over the CLIP block: filled with the vector, empty under zeros.
const zeroPool = computed(() => props.pooled === 'zero')

const fa = computed(() => Number.isFinite(props.a) ? props.a : 0)
const fb = computed(() => Number.isFinite(props.b) ? props.b : 0)
const fc = computed(() => Number.isFinite(props.c) ? props.c : 0)

/** A fill's opacity is the factor's magnitude, capped at 1. */
function op(v: number): number {
  return Math.min(1, Math.abs(v))
}
const arrowOp = computed(() => Math.max(0.3, op(fb.value)))
</script>

<style scoped>
.ct {
  display: block;
  width: 100%;
  height: auto;
  /* The drawing runs left to right in every language: the row numbers stand
     at the left edge of the blocks and the names at the right. */
  direction: ltr;
}
.ct text {
  font-family: inherit;
  unicode-bidi: plaintext;
}
.ct-dim {
  font-size: 9px;
  fill: rgba(255, 255, 255, 0.5);
}
.ct-formula {
  font-size: 9px;
  fill: #e8eef5;
}
.ct-name {
  font-size: 8px;
  fill: rgba(255, 255, 255, 0.6);
}
.ct-b {
  font-size: 9px;
  fill: #e0c9a6;
}
</style>
