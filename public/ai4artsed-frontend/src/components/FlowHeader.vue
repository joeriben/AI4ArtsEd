<!--
  FlowHeader — the band of nodes a page stands under.

  The flow's header is the standard band. This is that band, taken out of
  x2x_flow so that more than one page can stand under the same one.

  It owns only what every band has in common: the fixed stage, the node shells
  in their world geometry, the connectors between them, and the reserved
  rectangle that keeps canvas gestures from reaching behind the boxes.

  t2i stands under four stations — Eingabe, Start, Result,
  Erzeugen — so the band is an ordered LIST now (`nodes`), consecutive nodes
  joined by a connector. The original three-prop form still builds the
  create/gen/output band, so cover-band is untouched by the change.

  Everything INSIDE a node is the page's, handed in through a slot. Everything a
  node REACTS to is the page's too, handed in per node as `attrs` —
  v-bind takes class, title and onClick alike, so this component never has to
  enumerate the interactions of every page that adopts it.

  The stage goes back out through defineExpose. A page that draws its own things
  in the band's coordinates — x2x-flow positions its long-press bubbles and its
  paused-prompt panel there — reads rect()/line()/anchorX() off the component
  instead of measuring the map a second time. Two stages measuring one element
  is how the positions drift apart.

  The default geometry is the band x2x-flow drew first, because that is the
  shape being standardised. A page with a different band passes its own.
-->
<template>
  <div class="map-wrap" :class="[placement, { fill }]">
    <div
      ref="mapEl"
      class="fl-map"
      :class="{ fill }"
      :style="fill ? undefined : { aspectRatio: worldRatio }"
    >
      <div
        v-for="z in zones ?? []"
        :key="z.id"
        class="fl-zone"
        :style="rectStyle(z.rect)"
      >
        <span v-if="z.label">{{ z.label }}</span>
      </div>

      <svg class="edges" :width="cw" :height="ch">
        <path
          v-for="(b, i) in backLines"
          :key="`b${i}`"
          class="back"
          :d="b.d"
          fill="none"
        />
        <text
          v-for="(b, i) in backLines.filter(x => x.label)"
          :key="`bt${i}`"
          class="edge-label"
          text-anchor="middle"
          :x="b.lx"
          :y="b.ly"
        >{{ b.label }}</text>
        <line
          v-for="(e, i) in edgeLines"
          :key="i"
          :class="{ on: e.on }"
          :x1="e.p[0]"
          :y1="e.p[1]"
          :x2="e.p[2]"
          :y2="e.p[3]"
        />
        <!-- Beside a connector that runs DOWN, above one that runs across.
             The original placement — centred on the midpoint, seven pixels up —
             puts the words inside the box above when the two boxes are stacked,
             because the segment then starts at the lower edge of that box. -->
        <text
          v-for="(e, i) in edgeLabels"
          :key="`t${i}`"
          class="edge-label"
          :text-anchor="e.upright ? 'start' : 'middle'"
          :x="e.upright ? (e.p[0] + e.p[2]) / 2 + 9 : (e.p[0] + e.p[2]) / 2"
          :y="e.upright ? (e.p[1] + e.p[3]) / 2 + 4 : e.p[1] - 7"
        >{{ e.label }}</text>
      </svg>

      <div class="lock-rect" :style="lockRectStyle"></div>

      <div
        v-for="n in bandNodes"
        :key="n.id"
        class="nd"
        v-bind="n.attrs"
        :class="[n.kind, { compact: n.compact }]"
        :style="[rectStyle(n.openRect ?? n.rect), n.raised ? { zIndex: 3 } : {}]"
      >
        <slot :name="n.slot" />
      </div>
    </div>

    <slot name="overlay" />
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useFlowStage, type FlowRect } from '@/composables/useFlowStage'

type NodeId = 'create' | 'gen' | 'output'

/**
 * One box in the band. A page that has other than the three original stations
 * hands in its own list; the band then draws exactly these, in this order, with
 * a connector between each pair.
 */
export interface FlowNode {
  /** Matches `activeTarget`, and names the slot unless `slot` says otherwise. */
  id: string
  /** Which shell: the input box, an action box, a result box. Default 'op'. */
  kind?: 'mix' | 'op' | 'out'
  rect: FlowRect
  /** Live rectangle while the page animates THIS node open. */
  openRect?: FlowRect | null
  attrs?: Record<string, unknown>
  /** Slot name when it differs from the id — the original band's `generate`. */
  slot?: string
  /** Override the measured compactness. Default: measured from `rect`. */
  compact?: boolean
  /**
   * What the connector INTO this node is called.
   *
   * A connector is not always a mere adjacency. On the diffusion band the step
   * from the encoders into the denoiser is conditioning, and conditioning is
   * exactly not a station: nothing is computed there, the encoder outputs are
   * assembled and handed over. Drawn as a box it claims an activity it has not
   * got; written on the arrow it says what the arrow carries.
   */
  edgeLabel?: string
  /**
   * No connector INTO this node, in a band that otherwise draws them.
   *
   * A band is one order as long as it is one run. A band that carries several
   * runs side by side is still one list — the boxes are laid out in one
   * coordinate system and open into one another's room — but the step from the
   * last box of one run to the first box of the next is not a step at all. The
   * connector there would assert a sequence across two procedures that have
   * nothing to do with each other.
   */
  breakBefore?: boolean
  /**
   * Lift this node above its siblings.
   *
   * A band with ONE action box never needed this: its z-index sat on the node
   * itself so that a box still retracting was not painted under the neighbours
   * it was passing over. With TWO action boxes at the same z-index the opened
   * one is painted under whichever comes after it in the list, and the box it
   * is covering shows through its own panel. The page raises it, because only
   * the page knows when the retraction has finished — the class that opens the
   * box comes off a full transition before the box has arrived.
   */
  raised?: boolean
}

/**
 * A region of the band, drawn behind the nodes.
 *
 * Not every part of a flow is a station. A trained space is the medium the
 * process runs IN — as one more box in the row it would read as a step that
 * happens once, which is the one thing it is not. So it is an area, and the
 * nodes that sit inside it are literally inside it.
 */
export interface FlowZone {
  id: string
  rect: FlowRect
  label?: string
}

/**
 * A connector that runs BACKWARDS, from a later node to an earlier one.
 *
 * The one thing a row of boxes cannot say. A transformer writes one word and
 * then reads everything again including that word; drawn as a chain it looks
 * like a run that ends, which is the opposite of what it is. So the return is
 * drawn as what it is: out of the lower box, down, around the side, and back
 * into the upper one. Same dash and same animation as the forward connectors,
 * because the animation IS the direction here — no arrowhead exists anywhere in
 * this band.
 */
export interface FlowFeedback {
  from: string
  to: string
  label?: string
}

const props = withDefaults(
  defineProps<{
    world?: { w: number; h: number }
    /**
     * The band, as an ordered list. When given, it is the whole band and the
     * three legacy props below are not read. When absent, those three build the
     * original create/gen/output band, so a page written against them is
     * unaffected by this component knowing about longer bands.
     */
    nodes?: FlowNode[] | null
    rects?: Record<NodeId, FlowRect>
    /** The generation node's live rectangle when the page animates it open. */
    genRect?: FlowRect | null
    /** Which node the run is currently reaching for; lights the edge into it. */
    activeTarget?: string | null
    /**
     * Where the band stands.
     *
     * 'float' is the original: absolutely positioned, hanging over a canvas,
     * which is why every page carrying one has had to reserve its height in a
     * strip of its own (cover_band's `.band-slot`). That strip has to compute a
     * height from a width, which CSS cannot do, so it is written out in window
     * units — and a band that no longer spans the window then reserves the
     * wrong amount.
     *
     * 'inline' is the band in the flow of a column: it takes its own height
     * from the stage's aspect ratio and needs no strip at all. The page's own
     * padding is the distance to the edge, so the 16 px per side the floating
     * form carries are not taken a second time here.
     */
    placement?: 'float' | 'inline'
    /**
     * Whether consecutive nodes are joined.
     *
     * A band is usually an order, and then the connectors ARE the statement.
     * A band can also be a set — four ways one modality is turned into another
     * have no first and no last — and there a connector would assert a sequence
     * that does not exist.
     */
    connect?: boolean
    /**
     * Whether the map takes the box it is given instead of bringing its own
     * height from the world's proportions.
     *
     * Off, the map is as wide as it may be and as high as the world says — one
     * band standing in a column, at the design width the whole platform draws
     * bands at. On, it fills width AND height, and useFlowStage fits the world
     * into that box: width-bound at a wide window, height-bound at a short one.
     * For a surface that IS the map rather than carrying one, where the height
     * that is free is height the drawing should have.
     */
    fill?: boolean
    /** Areas behind the nodes: the spaces the process runs in. */
    zones?: FlowZone[] | null
    /** Connectors that run back up the band. */
    feedback?: FlowFeedback[] | null
    createAttrs?: Record<string, unknown>
    genAttrs?: Record<string, unknown>
    outputAttrs?: Record<string, unknown>
  }>(),
  {
    world: () => ({ w: 1060, h: 150 }),
    rects: () => ({
      create: { x: 140, y: 20, w: 220, h: 110 },
      gen: { x: 480, y: 20, w: 160, h: 110 },
      output: { x: 760, y: 20, w: 160, h: 110 },
    }),
    nodes: null,
    genRect: null,
    activeTarget: null,
    connect: true,
    fill: false,
    zones: null,
    feedback: null,
    createAttrs: () => ({}),
    genAttrs: () => ({}),
    outputAttrs: () => ({}),
    placement: 'float',
  },
)

// useFlowStage takes the world ONCE, at setup, and closes over it. So the box
// must not be allowed to change shape underneath it: the aspect ratio is frozen
// from the same two numbers rather than bound to the live prop, which would give
// a container that reshapes while every node rect is still computed against the
// old world.
const worldRatio = `${props.world.w} / ${props.world.h}`

// Read ONCE, on purpose: useFlowStage takes plain numbers and the aspect-ratio
// is frozen with them, so those two can never disagree. The cost is that a
// reactive `world` would be a silent no-op — the container would keep the old
// ratio and every rect would keep scaling against the old world — so in dev it
// says so rather than drawing the wrong band quietly.
if (import.meta.env.DEV) {
  watch(
    () => `${props.world.w}x${props.world.h}`,
    (now, before) => {
      console.warn(
        `[FlowHeader] world changed ${before} -> ${now} after setup and was ignored. ` +
        'The stage is measured once; pass a constant, or remount the header with a key.',
      )
    },
  )
}

const stage = useFlowStage(props.world.w, props.world.h)
const { mapEl, cw, ch, rect, rectStyle, line, anchorX, isCompact, scale } = stage

/**
 * The band as drawn. Either the page's own list, or the original three built
 * from the legacy props — after this point the component knows only the list.
 *
 * `compact` is settled HERE and not in the template because the original band
 * measured it for two of its three boxes and never for the middle one. A page
 * styling `.nd.compact` from its own sheet would see the middle box change
 * appearance the day this component started measuring it too, which is not a
 * change this refactor is entitled to make.
 */
const bandNodes = computed(() => {
  const list: FlowNode[] = props.nodes?.length
    ? props.nodes
    : [
        { id: 'create', kind: 'mix', rect: props.rects.create, attrs: props.createAttrs },
        { id: 'gen', kind: 'op', slot: 'generate', rect: props.rects.gen,
          openRect: props.genRect, attrs: props.genAttrs, compact: false },
        { id: 'output', kind: 'out', rect: props.rects.output, attrs: props.outputAttrs },
      ]

  return list.map(n => ({
    id: n.id,
    kind: n.kind ?? 'op',
    slot: n.slot ?? n.id,
    rect: n.rect,
    openRect: n.openRect ?? null,
    raised: n.raised ?? false,
    attrs: n.attrs ?? {},
    edgeLabel: n.edgeLabel ?? '',
    breakBefore: n.breakBefore ?? false,
    compact: n.compact ?? isCompact(n.rect),
  }))
})

// The connectors run between the RESTING rectangles. When a node animates open
// it moves out from under its own edges on purpose — an edge that followed it
// would draw a line across the opened card.
const edgeLines = computed(() => {
  const ns = bandNodes.value
  const out: Array<{
    p: [number, number, number, number]
    on: boolean
    label: string
    upright: boolean
  }> = []
  if (!props.connect) return out
  for (let i = 0; i + 1 < ns.length; i++) {
    const from = ns[i]
    const to = ns[i + 1]
    if (!from || !to) continue
    if (to.breakBefore) continue
    const p = line(from.rect, to.rect)
    out.push({
      p,
      on: props.activeTarget === to.id,
      label: to.edgeLabel,
      upright: Math.abs(p[3] - p[1]) > Math.abs(p[2] - p[0]),
    })
  }
  return out
})

// Split out rather than v-if'd in the template: v-for and v-if on one element
// is not allowed, and the labelled connectors are the minority.
const edgeLabels = computed(() => edgeLines.value.filter(e => e.label))

// The way back, routed rather than drawn straight: a line from the lower box to
// the upper one would cross everything between them. Out of the bottom, down
// into the clear strip under the band, along to a channel left of the boxes,
// up, and in at the side of the target. The channel is measured off the
// NARROWEST left edge of the two, so it never runs through either box.
const backLines = computed(() => {
  const by = new Map(bandNodes.value.map(n => [n.id, n]))
  const out: Array<{ d: string; label: string; lx: number; ly: number }> = []
  for (const f of props.feedback ?? []) {
    const a = by.get(f.from)
    const b = by.get(f.to)
    if (!a || !b) continue
    const ra = rect(a.rect)
    const rb = rect(b.rect)
    const drop = Math.round(ra.height * 0.26)
    const foot = ra.top + ra.height + drop
    // Never off the left edge: two boxes in the FIRST column would put the
    // channel at a negative x, where the whole path is drawn and then clipped
    // away by the SVG's own bounds, so the return simply would not be there.
    const chan = Math.max(4, Math.min(ra.left, rb.left) - drop)
    const midY = rb.top + Math.round(rb.height / 2)
    const cx = ra.left + Math.round(ra.width / 2)
    out.push({
      d: `M ${cx} ${ra.top + ra.height} L ${cx} ${foot} L ${chan} ${foot} L ${chan} ${midY} L ${rb.left} ${midY}`,
      label: f.label ?? '',
      lx: cx,
      // Inside the stage even when the stage is small: the label sits under the
      // foot of the path, and 16 px is a fixed distance in a box whose height
      // scales with the window.
      ly: Math.min(foot + 16, ch.value - 3),
    })
  }
  return out
})

// Of the whole band, only this — hugging the three boxes, width flexible — is
// locked out of whatever lies behind. Everything else in the band stays
// reachable material space.
const lockRectStyle = computed(() => {
  const ns = bandNodes.value
  const pad = 8
  const boxes = ns.map(n => rect(n.rect))
  if (!boxes.length) return { display: 'none' }
  // The bounding box of ALL of them. Reading the first and the last only holds
  // for a band that runs left to right in one row; a band laid out in columns
  // has its last box under its first, and the strip then covered one row.
  const l = Math.min(...boxes.map(x => x.left))
  const t = Math.min(...boxes.map(x => x.top))
  const r = Math.max(...boxes.map(x => x.left + x.width))
  const b = Math.max(...boxes.map(x => x.top + x.height))
  return {
    left: `${l - pad}px`,
    top: `${t - pad}px`,
    width: `${r - l + pad * 2}px`,
    height: `${b - t + pad * 2}px`,
  }
})

// mapEl goes out too: x2x-flow reads clientHeight off the real element in two
// places where a measured rect() is still 0, and there must not be a second
// element for it to read.
//
// NOTE for whoever moves x2x-flow onto this component: what comes back through
// a template ref is UNWRAPPED. Vue puts the exposed object behind proxyRefs, so
// it is `headerRef.value.mapEl` — an element or null — and NOT `.mapEl.value`.
// x2x-flow's existing call sites are written `mapEl.value`; moved verbatim they
// read undefined, which does not throw: its guard silently returns so the
// action zone never gets its position, and clientHeight becomes 0, so the
// material rides up over the three boxes. It is also null through the parent's
// whole setup and first render, non-null from its onMounted onward.
defineExpose({ mapEl, rect, rectStyle, line, anchorX, isCompact, cw, ch, scale })
</script>

<style scoped>
.map-wrap {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3;
  width: min(var(--flow-map-w), calc(100% - 32px));
  pointer-events: none;
}

/* The band standing IN a column instead of over a canvas: it stops floating and
   brings its own height (aspect-ratio on .fl-map).

   Its SIZE does not change with that: the sizes, the height above all, are part
   of the template and must be kept. The width cap from assets/flow-stage.css
   therefore stays on .fl-map, and with it the scale the nodes are drawn at: at
   the cap 1000 / 1060 = 0.9434, so a node is 104 px high wherever a band
   stands. Let the map take the whole width instead and the scale rides the
   window — at 1888 px the same node comes out 196 px high, which is what this
   page once showed. What a page may decide is where the band stands, not how
   big the flow's boxes are.

   A page whose columns must line up under the nodes gives them the same width
   expression the map has, min(var(--flow-map-w), 100%). */
.map-wrap.inline {
  position: static;
  width: 100%;
  margin: 0;
  transform: none;
}

.lock-rect { position: absolute; pointer-events: auto; background: transparent; }
.fl-map { background: transparent; overflow: visible; }
/* A percentage height needs a definite one above it, and the wrap between the
   page's element and the map is auto-high — so the fill mode is written on
   both, or the map measures zero and every node collapses to a dot. */
.map-wrap.fill { height: 100%; }
.fl-map.fill { width: 100%; height: 100%; }

/* Behind the nodes, and out of the way of every gesture: an area says where
   something is, it is never a thing to press. */
.fl-zone {
  position: absolute;
  box-sizing: border-box;
  pointer-events: none;
  border: 1px dashed rgb(var(--surface-4-rgb) / 0.9);
  border-radius: 12px;
  background: rgb(var(--surface-2-rgb) / 0.55);
}
.fl-zone span {
  position: absolute;
  left: 12px;
  top: 2px;
  font-size: var(--flow-fs-hint);
  letter-spacing: 0.05em;
  color: #8b8b8b;
  white-space: nowrap;
}

/* `text-anchor: start|end` follows the `direction` property, so under
   the document's `dir="rtl"` (ar, he) a label anchored to one side of
   its x lands on the OTHER side of it. The geometry here is written
   left to right, so the direction is pinned; `unicode-bidi: plaintext`
   still lets each label take its own paragraph direction from its own
   first strong character, so Arabic and Hebrew read correctly inside
   it. Measured 2026-08-29. Same cause and same fix as in
   `views/latent_lab/flow_stations.vue`, where it stands written out. */
.edges { position: absolute; left: 0; top: 0; pointer-events: none; direction: ltr; }
.edges .edge-label { fill: #8b8b8b; font-size: 10px; letter-spacing: 0.03em; unicode-bidi: plaintext; }
.edges line, .edges .back { stroke: #5a5a5a; stroke-width: 1; stroke-dasharray: 3 6; animation: dashf 3.2s linear infinite; }
.edges line.on { stroke: #7fb2ff; animation-duration: 0.7s; }
@keyframes dashf { to { stroke-dashoffset: -18; } }

/* The node SHELLS only. Anything that reaches into what a node contains stays
   with the page: slot content is compiled in the page's scope, so a descendant
   selector written here would not match it (`.nd.compact .lbl` is the one that
   caught this). */
.nd { position: absolute; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; min-width: 0; padding: 4px; border-radius: 10px; border: 1px solid #4a4270; overflow: hidden; transition: border-color 0.2s; pointer-events: auto; }
.nd.mix { background: #2b2450; border-color: #7f77dd; border-width: 1.5px; }
/* The pull: the box takes the room of all three and gives it back. Left/width
   are animated, not a transform — the text inside must keep its --flow-fs-*
   size at every step of the movement. The small overshoot is the tug. */
/* z-index HERE and not on .wide: the class comes off in the same tick as the
   geometry, but left/width keep animating for another 0.42s, so on the way back
   the still-wide box was painted UNDER its two neighbours and the record button
   and the audio player drew straight through it. Opening was never asymmetric
   this way; retracting was. At rest the three boxes do not overlap, so a
   standing z-index costs nothing. */
.nd.op { background: #1d2f45; border-color: #3f6a9c; cursor: pointer; z-index: 2; }
/* TOP is in this list, and it has to be. Every band before the Latent Lab's
   overview map was ONE row, so a box opening kept the y it had and nobody
   noticed the omission. On a map laid out in columns the rows sit at 8, 144,
   280 and 416 and the opened rectangle at 30: without `top` the box SNAPS to
   the new y in one frame while left, width and height glide for 0.42 s — on the
   way out it flashes at its old column in the top row, and on the way back it
   takes its full open height down to the bottom row, hanging 236 px below the
   map across the legend and, for those 0.42 s, growing the page.

   And on .nd rather than .nd.op, because on this map all three kinds open. The
   two others snapped in both directions while the eight `op` boxes moved, and
   the page's lock — which holds a box shut for as long as it is still moving
   under the hand — held them dead for 0.42 s with nothing to see for it. */
.nd.anim { transition: border-color 0.2s, left 0.42s cubic-bezier(0.34, 1.28, 0.64, 1),
    top 0.42s cubic-bezier(0.34, 1.28, 0.64, 1),
    width 0.42s cubic-bezier(0.34, 1.28, 0.64, 1), height 0.42s cubic-bezier(0.34, 1.28, 0.64, 1); }
.nd.op.wide { cursor: default; }
.nd.op:not(.ready):not([role='button']) { cursor: default; }
.nd.out { background: #4a2b2f; border-color: #7a4046; }
.nd:hover { border-color: #b8c2d8; }
/* A node a page has made pressable, and the one whose detail is showing. Both
   are states of the SHELL, so they live here: slot content is compiled in the
   page's scope and a rule written there would never reach the box itself. The
   page says which node is which through `attrs` and does not have to reach in. */
.nd[role='button'] { cursor: pointer; }
.nd.open { border-color: #b8c2d8; box-shadow: inset 0 0 0 1px rgb(184 194 216 / 0.3); }
/* A box on its way back in takes no press. For the 0.42 s it is folding it is
   still lying wide across its neighbours, and every press that lands on it is a
   press meant for one of them: it either does nothing at all (the box has moved
   out from under its own handler) or opens the wrong box. The POINTER is what
   this is about — a keyboard has nothing lying under it, so the node keeps its
   role, its tab stop and its key handler throughout. */
.nd.folding { pointer-events: none; z-index: 2; }
.nd.live { border-color: #7fb2ff; animation: livepulse 1.2s ease-in-out infinite; }
/* A node whose station did not answer. Slot content can say so in words, but
   only a rule written HERE reaches the node itself — the element belongs to
   this component's scope, so an adopting page cannot style it from its own. */
.nd.failed { border-color: #a04040; }
@keyframes livepulse { 0%, 100% { border-color: #7fb2ff; } 50% { border-color: #2e4a6a; } }

/* Everything in this band that moves, for whoever has asked not to be moved.
   The pull is the largest movement on the page — a box the width of the whole
   band, on an overshoot curve — and it was the one thing here with no guard,
   while a card entrance a fifth its size had one. */
@media (prefers-reduced-motion: reduce) {
  .nd.anim { transition: border-color 0.2s; }
  .nd.live { animation: none; border-color: #7fb2ff; }
  .edges line, .edges .back { animation: none; }
}

/* Below this width the band cannot stay a band. The stage keeps a fixed aspect
   ratio while the text inside the nodes is rem-clamped and does NOT shrink with
   it, so on a phone the boxes reach ~116x39 CSS px around content needing more
   than three times that, and overflow:hidden simply cuts it off. So the three
   nodes leave the stage and stack: same nodes, same order, no geometry. The
   connectors and the reserved rectangle only mean anything in the geometry and
   go with it. A page that uses this must let its strip grow (height: auto). */
@media (max-width: 640px) {
  .map-wrap { position: static; width: auto; transform: none; padding: 0 12px; box-sizing: border-box; }
  .fl-map { aspect-ratio: auto !important; width: auto; display: flex; flex-direction: column; gap: 8px; }
  .edges, .lock-rect, .fl-zone { display: none; }
  .nd { position: static !important; width: auto !important; height: auto !important;
        min-height: 3.4rem; padding: 8px; gap: 5px; }
  .nd.op.anim { transition: border-color 0.2s; }
}
</style>
