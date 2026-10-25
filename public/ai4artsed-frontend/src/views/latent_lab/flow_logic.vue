<!--
  Flow Logic — the flow of a generative run, drawn, with the Latent Lab's
  instruments marked where they reach into it.

  Sixteen versions of ONE drawing tried to hold every station, every space and
  every marker of all three procedures at once and stayed unreadable. A survey
  of eleven published representations of the same subject says why: not one of
  them puts everything on one surface. So the load is split — three procedures,
  three columns, four boxes each — and what a box holds in detail is behind a
  press on it.

  IT RUNS DOWNWARD, IN COLUMNS. The first build laid each procedure out as a row
  and stacked the three rows, and that is a page of bands, not a map. The
  architecture figure in "Attention Is All You Need" (Vaswani et al. 2017)
  stacks its boxes vertically and sets the two stacks side by side, which is
  what the three procedures need: they are parallel, not sequential, and only
  the boxes WITHIN one of them are in an order.

  AND THE BOXES CARRY THE DRAWING. They held two words and a subtitle, with
  the drawing itself hidden behind a press. Now the small form of each drawing
  IS the closed box, and the press opens the large one.

  The page carries no prose. The brief for it was graphic, and help is this
  platform's authority for factual explanation — a paragraph about what a
  denoiser is belongs there. Here it is shown, and the instruments sit on the
  drawing at the place they act.

  What belongs where is DATA (`marks`), never a marker positioned by hand in the
  layout. A marker is a POINT, and it carries neither a number nor a name: the
  numbers needed a footnote under every open box that repeated what the column
  on the left already lists. Pointing
  at a marker lights its instruments in that column instead, and the light stays
  on until another marker is pointed at, so the pointer can be walked over to
  the name and pressed.
-->
<template>
  <div class="fl-logic">
    <!-- The three headings, in the columns' own proportions: the same width
         expression the stage carries, and columns of 324 in 1100 with 64
         between, written as percentages so the two cannot drift apart.
         Each stands on two lines: the name of the procedure, and under it what
         it does. They were one line with a colon between them; two lines
         tell the two halves apart at a glance. -->
    <div class="fl-titles" :style="drawnW ? { width: `${drawnW}px` } : undefined">
      <div v-for="c in COLUMNS" :key="c.id" class="fl-title">
        <h2>{{ t(`latentLab.flowLogic.${c.id}.title`) }}</h2>
        <p>{{ t(`latentLab.flowLogic.${c.id}.sub`) }}</p>
      </div>
    </div>

    <!-- ONE stage for all twelve boxes, so an opened one can take the width of
         the whole map instead of the width of its own column. It does not cover
         them completely — a strip of the top and bottom rows and a sliver of
         the outer columns stay out — and that is fine: a press there opens that
         box directly, which is what somebody reaching for it wants. It opens INSIDE
         the stage's own world (30 to 430 of 528), so nothing overhangs and the
         page cannot grow at the moment of a press: the boxes enlarge as an
         overlay and never push the page down. (30 to 450 of 576.) -->
    <div class="fl-stage" :style="{ aspectRatio: STAGE_RATIO }">
      <FlowHeader
        ref="hdr"
        :world="WORLD"
        :nodes="bandNodes"
        :zones="open ? null : ZONES"
        connect
        fill
        placement="inline"
      >
        <template v-for="n in NODES" #[n.id] :key="n.id">
          <div v-if="open === n.id" class="st">
            <div class="st-head">
              <span>{{ t(`latentLab.flowLogic.${n.id}.name`) }}</span>
              <button ref="closeBtn" type="button" class="st-close" @click.stop="close()">
                {{ t('latentLab.flowLogic.close') }}
              </button>
            </div>
            <FlowStation
              :id="n.id"
              :marks="marksOf(n)"
              class="st-draw"
              @mark="emit('highlight', $event)"
              @pick="emit('reveal', $event)"
            />
          </div>

          <template v-else>
            <!-- The name is TYPE and stays out of the drawing: inside the SVG it
                 would ride the map's scale, and at a 1150 px window that is 11 px
                 falling to 8 by 1024. A rem step has a floor. -->
            <span class="fl-name">{{ t(`latentLab.flowLogic.${n.id}.name`) }}</span>
            <FlowStation
              :id="n.id"
              :marks="marksOf(n)"
              mini
              class="st-mini"
              @mark="emit('highlight', $event)"
              @pick="emit('reveal', $event)"
            />
          </template>
        </template>
      </FlowHeader>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import FlowHeader, {
  type FlowNode,
  type FlowZone,
} from '@/components/FlowHeader.vue'
import FlowStation, { type StationMark } from './flow_stations.vue'

const props = defineProps<{
  /**
   * Instrument id → its name, from the lab's own catalogue.
   *
   * Not drawn anywhere. It is what a marker SAYS when it is read aloud, and
   * what the page needs so the drawing does not have to know the catalogue.
   */
  labels: Record<string, string>
}>()

const emit = defineEmits<{
  /** A marker was pointed at or focused: light these in the column on the left. */
  (e: 'highlight', hosts: string[]): void
  /** A marker was pressed: put the column up and take me to the first of these. */
  (e: 'reveal', hosts: string[]): void
}>()

const { t } = useI18n()

/**
 * The map's own world.
 *
 * Three columns of 324 with 64 between them, in 1100. Four boxes of 300 x 108
 * per column, 28 apart, and 52 under the last row for the way back out of
 * Sampling and its label.
 *
 * 108 and not 96, which is the height the small drawings are drawn in. A box
 * SHORTER than its drawing's proportion makes the drawing height-bound inside
 * it: measured at the 1000 px cap, a 96-unit box came out 87 px high, the
 * drawing was scaled to 0.80 px per unit to fit that, and its captions arrived
 * at 9.6 px. At 108 the box is taller than the drawing needs, the drawing is
 * WIDTH-bound instead — 0.88 px per unit, captions at 10.6 and names at 13.2 —
 * and what is left over is margin above and below. Text too small in these
 * boxes is the complaint this page has already had once.
 */
const WORLD = { w: 1100, h: 576 }
/**
 * The same two numbers as the stage's proportion, so the box the map is fitted
 * into cannot disagree with the world it holds.
 */
const STAGE_RATIO = `${WORLD.w} / ${WORLD.h}`
const COL_X = [0, 388, 776]
const ROW_Y = [8, 144, 280, 416]
const BOX = { dx: 12, w: 300, h: 108 }
/**
 * An opened box takes the whole map and stays INSIDE it. The old band had to
 * hang out of its stage and over the band below, which meant a strip of
 * reserved room under the last one; here there is nothing to reserve.
 */
const OPEN = { x: 40, y: 30, w: 1020, h: 420 }

interface LogicNode {
  /** `<column>.<station>`, which is also the i18n path and the slot name. */
  id: string
  col: number
  row: number
  kind?: 'mix' | 'op' | 'out'
  /** Which places in the drawing instruments reach into, by name. */
  marks: { at: string; hosts: string[] }[]
  /** What the connector into this box carries, when it carries anything. */
  edge?: string
  /** First box of its column: the step into it from the box above is not one. */
  breakBefore?: boolean
}

interface Column {
  id: 'diffusion' | 'transformer' | 'crossings'
  /** The trained space behind the boxes, in the map's own coordinates. Its
   *  lower edge falls THROUGH the last box on purpose: the decoder and the
   *  sampling step are the doors out, and a door is on the boundary. */
  zone?: { y: number; h: number }
}

const COLUMNS: Column[] = [
  // The upper edge stands 26 units clear of the box below it, not 20: the zone's
  // name sits just inside that edge at a rem step that does NOT shrink with the
  // map, and at 20 its descenders ran under the box at narrow windows.
  { id: 'diffusion', zone: { y: 254, h: 206 } },
  { id: 'transformer', zone: { y: 118, h: 342 } },
  { id: 'crossings' },
]

const NODES: LogicNode[] = [
  // Both instruments at this point work on the written line and nothing else:
  // one exchanges the language it is written in, the other one word in it.
  {
    id: 'diffusion.prompt', col: 0, row: 0, kind: 'mix',
    marks: [{ at: 'language', hosts: ['language', 'census'] }],
  },
  {
    id: 'diffusion.encoder', col: 0, row: 1,
    marks: [
      { at: 'mix', hosts: ['fusion', 'workbench'] },
      { at: 'conditioning', hosts: ['probing', 'algebra', 'synth'] },
    ],
  },
  {
    id: 'diffusion.loop', col: 0, row: 2, edge: 'conditioning',
    marks: [
      // LoRA Training and LoRA Explorer joined this point on 2026-09-02: a
      // trained adapter is low-rank weights added into the denoiser itself,
      // the same layer Composable Diffusion and Attention Cartography already
      // reach into -- not a step of its own between encoding and denoising.
      { at: 'denoiser', hosts: ['composable', 'attention', 'lora', 'reach'] },
      // Denoising Archaeology reads the state the loop starts from and every
      // state it reaches; Mean Images holds that starting noise still and
      // varies the text, or holds the text and varies the noise. Since
      // 2026-09-04 Mean Images ALSO marks the decoder's door, because for the
      // two SD 3.5 rows its mean is taken on the latents the loop hands over.
      { at: 'state', hosts: ['archaeology', 'mean'] },
      // Outside the dashed edge, at its own corner: what reaches in here is
      // not a step INSIDE the loop but a claim about the model doing the
      // denoising itself. Model Comparison sets several diffusion models
      // against each other; Voice Comparison does the same for text-to-speech,
      // and two of its three systems are themselves flow-matching or
      // diffusion-autoregressive decoders, so it marks the same place.
      { at: 'compare', hosts: ['model', 'voice'] },
    ],
  },
  {
    id: 'diffusion.decoder', col: 0, row: 3, kind: 'out',
    // Mean Images marks here: for the two SD 3.5 rows it averages
    // the final latents of a set and decodes that one, so it reaches in at the
    // door of the VAE and not inside it.
    marks: [{ at: 'latent', hosts: ['mean'] }],
  },

  {
    id: 'transformer.prompt', col: 1, row: 0, kind: 'mix', breakBefore: true,
    marks: [{ at: 'provider', hosts: ['systemprompt'] }],
  },
  {
    id: 'transformer.vectors',
    col: 1,
    row: 1,
    // Der Exkurs der Karte behauptet einen Sprachvergleich; das markierte
    // Instrument rechnet ihn nach.
    marks: [{ at: 'languages', hosts: ['tokens'] }],
  },
  {
    id: 'transformer.block', col: 1, row: 2,
    marks: [
      { at: 'writeback', hosts: ['repeng'] },
      { at: 'learned', hosts: ['bias', 'coref'] },
    ],
  },
  {
    id: 'transformer.sampling', col: 1, row: 3, kind: 'out',
    // For a while nothing reached in here. `temperature` was taken apart, what
    // its text row became, `control`, was removed after it, and the place stood
    // without a marker — the honest picture then: a knob the lab had no
    // instrument on.
    //
    // System Prompts sets it again, and on an axis: its randomness IS this
    // setting, the one the station's own line names, and it flattens or
    // steepens these bars before one of them is drawn from, so the overview
    // links to System Prompts at this station. The
    // marker sits at `chance`, on the bars themselves, because that is what the
    // setting changes; the instrument's other marker, at the prompt of the
    // station above, is about what goes IN.
    marks: [{ at: 'chance', hosts: ['systemprompt'] }],
  },

  // A set, not an order: four ways one kind of material becomes another have no
  // first and no last, so every one of them breaks the connector into it.
  {
    id: 'crossings.i2t', col: 2, row: 0, breakBefore: true,
    marks: [{ at: 'edge', hosts: ['vlm-analysis'] }],
  },
  // `crossings.t2a` stood here and is gone. Text -> Klang crosses nothing:
  // one model generating from a prompt is the base case the Diffusion column
  // already shows, and this column asks what happens when SEVERAL AIs are
  // connected; text to sound is not crossmodal in that sense. It carried
  // Latent Audio Synth, which loses nothing -- it is marked at the
  // Embedding-Prozess station under `conditioning`, where embedding
  // manipulation belongs. The Stimmen-Vergleich, which was pinned here for
  // want of anywhere else, moved again: its two AI systems denoise like any
  // diffusion model does, so it now marks the Diffusion loop, beside Model
  // Comparison.
  {
    id: 'crossings.i2a', col: 2, row: 1, breakBefore: true,
    marks: [
      { at: 'toSound', hosts: ['mmaudio'] },
      { at: 'guide', hosts: ['guidance'] },
    ],
  },
  {
    id: 'crossings.chain', col: 2, row: 2, breakBefore: true,
    marks: [{ at: 'whole', hosts: ['reenactment'] }],
  },
]

/** A node's marks, with the instrument names read off the catalogue. */
function marksOf(n: LogicNode): StationMark[] {
  return n.marks.map(m => ({
    at: m.at,
    hosts: m.hosts,
    label: m.hosts.map(h => props.labels[h] ?? h).join(', '),
  }))
}

/**
 * How wide the map is ACTUALLY drawn.
 *
 * The stage fills whatever box it gets and fits the world into it, so the
 * drawing is width-bound at a wide window and height-bound at a short one. The
 * headings have to stand over their columns in BOTH cases, and a percentage of
 * the container is only right in the first — so they take the drawn width in
 * pixels and centre in the same box.
 */
const hdr = ref<{ scale: number } | null>(null)
const drawnW = computed(() => Math.round(WORLD.w * (hdr.value?.scale ?? 0)))

/** The two trained spaces, behind the boxes that lie in them. */
const ZONES = computed<FlowZone[]>(() =>
  COLUMNS.flatMap((c, i) =>
    c.zone
      ? [{
          id: `${c.id}-space`,
          rect: { x: COL_X[i] ?? 0, y: c.zone.y, w: 324, h: c.zone.h },
          label: t(`latentLab.flowLogic.${c.id}.space`),
        }]
      : [],
  ),
)

/** One box open at a time on the whole page, so it stays one page long. */
const open = ref<string>('')

/**
 * Whether the boxes may animate yet.
 *
 * `.nd.op.anim` transitions left/width/height, and on the first paint there is
 * nothing to transition FROM — the boxes crawled out of the top-left corner
 * every time the page loaded. The class goes on one frame later, when the
 * geometry is already standing, so the only movement it ever carries is the
 * pull.
 */
const ready = ref(false)

/**
 * A press anywhere off the boxes folds the open one away.
 *
 * The test is `.nd` and not `.nd.open`, so that the three other kinds of press
 * keep working: on a marker or the close button INSIDE the open box (it stays
 * open until its own handler decides — the marker's stops the event there and
 * goes to the column on the left), and on a closed box (its own handler moves
 * the opening over to it, and this one must not race it shut in between; a
 * marker in a CLOSED box lets the press through for exactly that reason).
 * A box that is folding back in has `pointer-events: none`, so a press can
 * never have it as its target and this test never sees one.
 *
 * IN THE CAPTURE PHASE, and that is not a detail. Registered on the bubble, it
 * runs AFTER the box's own handler — and between two listeners of one dispatch
 * the stack empties, so Vue has already re-rendered by then. The label that was
 * pressed is gone from the document at that point, and `closest('.nd')` on a
 * detached node answers null: the guard read its own box as "somewhere else"
 * and shut it again three milliseconds after opening it. A press on the text
 * in a box did nothing, and only a press on an empty spot opened it: pressing
 * the bare box worked because the box
 * itself stays in the document. In the capture phase nothing has re-rendered
 * yet, and `open` still holds what it held before the press, which is exactly
 * what this test wants to know.
 */
function onDocumentPress(e: MouseEvent) {
  if (!open.value) return
  const el = e.target as Element | null
  if (el?.closest?.('.nd')) return
  close()
}

/**
 * The boxes that are folding back in, for as long as each of them takes.
 *
 * An open box covers most of the map, and for the 0.42 s it takes to fold back
 * it is still lying wide across its neighbours. Every press that lands on it in
 * that time is a press meant for one of them, so a folding box takes no press
 * at all (`.nd.folding`, `pointer-events: none` in FlowHeader) and the press
 * reaches whatever is actually underneath. The KEYBOARD keeps working on it
 * throughout — nothing is lying under a keyboard.
 *
 * A SET and one timer per box, not one of each. Two boxes can be folding at the
 * same time: press A, press B while A is still moving, press C while B is still
 * moving. With a single timer, starting B's fold cleared A's, and A came back
 * to life with 300 ms of movement left — wide across the row, taking presses
 * meant for the boxes it was passing over, and opening itself instead.
 */
const FOLD_MS = 440
const folding = ref<Set<string>>(new Set())
const foldTimers = new Map<string, ReturnType<typeof setTimeout>>()

/** Where a box does not move, there is nothing to wait out. */
function moves(): boolean {
  return !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

function letGo(id: string) {
  if (!moves()) return
  folding.value.add(id)
  clearTimeout(foldTimers.get(id))
  foldTimers.set(id, setTimeout(() => {
    folding.value.delete(id)
    foldTimers.delete(id)
  }, FOLD_MS))
}

function close() {
  if (!open.value) return
  letGo(open.value)
  open.value = ''
  // Folding the box away takes its light with it.
  emit('highlight', [])
}

function openBox(id: string) {
  if (open.value === id) return
  if (open.value) letGo(open.value)
  folding.value.delete(id)
  clearTimeout(foldTimers.get(id))
  foldTimers.delete(id)
  open.value = id
}

/** Escape closes, wherever the focus happens to be. */
function onEscape(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) { e.stopPropagation(); close() }
}

/**
 * Where the focus goes.
 *
 * Opening a box replaces its whole content, so the element that was under the
 * focus is gone and the browser drops the focus to the document. Without this a
 * keyboard user opens a box and is put back at the start of the page. The close
 * button takes it on the way in, the box itself takes it back on the way out —
 * which is where the person was, and the box is still a tab stop while it folds.
 */
const closeBtn = ref<HTMLButtonElement | HTMLButtonElement[] | null>(null)

watch(open, async (now, was) => {
  await nextTick()
  if (now) {
    const b = closeBtn.value
    ;(Array.isArray(b) ? b[0] : b)?.focus()
  } else if (was) {
    const el = document.querySelector<HTMLElement>(`.fl-stage [data-node="${was}"]`)
    el?.focus()
  }
})

onMounted(() => {
  nextTick(() => { ready.value = true })
  document.addEventListener('click', onDocumentPress, true)
  document.addEventListener('keydown', onEscape, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentPress, true)
  document.removeEventListener('keydown', onEscape, true)
  foldTimers.forEach(clearTimeout)
  foldTimers.clear()
})

/** Every instrument that reaches into a station, in the order its marks stand. */
function hostsOf(n: (typeof NODES)[number]): string[] {
  return [...new Set(n.marks.flatMap(m => m.hosts))]
}

const bandNodes = computed<FlowNode[]>(() =>
  NODES.map((n) => {
    const isOpen = open.value === n.id
    return {
      id: n.id,
      kind: n.kind ?? 'op',
      rect: {
        x: (COL_X[n.col] ?? 0) + BOX.dx,
        y: ROW_Y[n.row] ?? 0,
        w: BOX.w,
        h: BOX.h,
      },
      openRect: isOpen ? OPEN : null,
      raised: isOpen,
      breakBefore: n.breakBefore,
      edgeLabel: n.edge
        ? t(`latentLab.flowLogic.${n.id.split('.')[0]}.${n.edge}`)
        : undefined,
      attrs: {
        'data-node': n.id,
        class: { anim: ready.value, open: isOpen, folding: folding.value.has(n.id) },
        // The box is the button in BOTH states, and says which one it is in.
        // Dropping the role while it is open takes the control out of the
        // accessibility tree at the moment it expands, which is the moment a
        // screen reader has something to say about it; and a box that cannot be
        // closed from the keyboard is a box a keyboard cannot leave.
        role: 'button',
        tabindex: 0,
        'aria-expanded': String(isOpen),
        onClick: () => { isOpen ? close() : openBox(n.id) },
        // The whole box lights its instruments, not only the ~20 px discs of
        // the markers inside it. Before, the light came up on some boxes and
        // not on others purely by whether the pointer happened to cross a
        // marker on its way in — and a box with no marker at all could never
        // light anything. A marker inside still narrows the light to its own
        // hosts.
        onPointerenter: () => emit('highlight', hostsOf(n)),
        // And it goes out again with the pointer. It used to stay lit so it
        // could be walked over to the column; the press path (`reveal`) is
        // what leads there now, and a light left burning sits on an entry
        // nobody is pointing at.
        onPointerleave: () => emit('highlight', []),
        onKeydown: (e: KeyboardEvent) => {
          if (e.key !== 'Enter' && e.key !== ' ') return
          e.preventDefault()
          isOpen ? close() : openBox(n.id)
        },
      },
    }
  }),
)
</script>

<style scoped>
/* The page is the map. No width cap and no cap on the flow's own scale: the
   columns take the window, and what the removed legend used to occupy under
   them is height the drawing gets instead.
   A column of exactly the height it is given, so the stage can be told to take
   what is left over and the page still does not scroll.

   The headings and the map are ONE figure, and the figure is what stands
   centred in the free height. Before, the stage alone took every pixel that
   was free and the fit centred the drawing inside it, so wherever
   the window had more height than the columns can use — 2000 x 1500, or an
   iPad held upright — the headings stayed at the top, the columns sank to the
   middle, and the leftover stood between the two. Now the stage stops where
   the drawing stops (`aspect-ratio`, below), and what is free lies above the
   headings and under the last row. */
.fl-logic {
  box-sizing: border-box;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 1.25rem 1rem 1.25rem;
}

/* The columns' own proportions, written once: 324 of 1100 per column and 64
   between, which is 29.4545 % and 5.8182 %. The stage inside carries the same
   width expression, so a heading always stands over its own column. */
.fl-titles {
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  column-gap: 5.8182%;
}

/* Over the middle of its own column, not against its left edge. */
.fl-title {
  text-align: center;
}

.fl-title h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.35;
  color: #e2e8f0;
}

/* The second line carries the sentence the name used to drag behind a colon.
   It steps back a little in size and in brightness, so the three names read as
   a row and the three sentences as the row under it. */
.fl-title p {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 400;
  letter-spacing: 0.02em;
  line-height: 1.3;
  color: rgba(226, 232, 240, 0.72);
}

/* Same width expression as the map inside it, so the two cannot disagree. The
   opened box lives in the map's own world and does not stick out of it, so
   this element needs no room reserved under it and the page never moves.

   As high as the world is at this width and no higher: the proportion is the
   world's own, bound in the template from WORLD. At a short window the box
   gives way instead (it may shrink to nothing) and the fit inside it is
   height-bound, exactly as before; at a tall one the box ends with the drawing,
   so no free height can open between the headings and the first row. */
.fl-stage {
  width: 100%;
  margin: 0.6rem auto 0;
  flex: 0 1 auto;
  min-height: 0;
}

/* `fill` on the header: the map takes the stage box and useFlowStage fits the
   world into it — min(cw/1100, ch/576), centred. Width-bound at a wide window,
   height-bound at a short one, and never cut off either way. The 1000 px cap in
   flow-stage.css is the design width of a BAND standing in a column, and this
   page is not that. */

/* The closed box: its name, and under it its drawing. The name keeps a rem step
   and its own floor; the drawing takes whatever height is left. */
.fl-name {
  font-size: var(--flow-fs-label);
  font-weight: 400;
  color: #e2e8f0;
  line-height: 1.2;
  text-align: center;
  align-self: stretch;
  padding: 0 6px;
  box-sizing: border-box;
}
.st-mini {
  width: 100%;
  flex: 1;
  min-height: 0;
}

/* The opened box. Everything the station shows hangs in a single full-size
   element, for the same reason. */
.st {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 12px 8px;
  box-sizing: border-box;
  text-align: start;
}
.st-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  font-size: var(--flow-fs-label);
  font-weight: 400;
  color: #e2e8f0;
}
.st-close {
  font: inherit;
  font-size: var(--flow-fs-hint);
  font-weight: 400;
  color: #93a1b5;
  background: none;
  border: none;
  padding: 2px 4px;
  cursor: pointer;
}
.st-close:hover { color: #e2e8f0; }
.st-draw { flex: 1; min-height: 0; }

@media (max-width: 640px) {
  .fl-logic { padding: 1rem 0.75rem 2rem; }
  .st { height: auto; }
  .st-draw { height: 200px; }
}
</style>
