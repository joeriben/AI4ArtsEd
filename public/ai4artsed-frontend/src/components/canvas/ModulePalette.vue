<!--
  The left column's contents: grouped entries, one of which may be the one the
  surface is currently showing.

  Two surfaces stand on it. Canvas hands in nothing and gets its module tiles —
  coloured, icon-bearing, draggable onto the workspace. The Latent Lab hands in
  its instruments, which carry no colour, and gets plain rows with the active one
  marked. The difference is in the DATA, not in a variant flag: an entry with a
  colour is a tile, an entry without one is a row.

  Registry: docs/ELEMENT_STRUCTURE_REGISTRY.md, family SEITENRAHMEN.
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NODE_TYPE_DEFINITIONS, type StageType, type NodeTypeDefinition } from '@/types/canvas'

const { t } = useI18n()

/** One entry in the column. */
export interface RailItem {
  id: string
  label: string
  /** Hover text. The short line an instrument already carries, if it has one. */
  title?: string
  /** Emoji, or the file name of an SVG under assets/icons/. */
  icon?: string
  /**
   * Several marks in the SAME slot as `icon`, for an entry that touches more
   * than one medium (image/text/voice/audio). Not a second channel: one entry
   * uses `icon` or `icons`, and both are drawn in one place at one size — two
   * positions would put a big mark left of some rows and a small one right of
   * others, in one column.
   */
  icons?: string[]
  /** Given: the entry is a filled tile in this colour. Absent: a plain row. */
  color?: string
  disabled?: boolean
}

export interface RailGroup {
  id: string
  label: string
  items: RailItem[]
}

const props = defineProps<{
  /** The whole column. Absent: Canvas's module catalogue, built below. */
  groups?: RailGroup[]
  /** Which entry the surface is showing. Rows only — tiles are actions. */
  activeId?: string | null
  /** Heading above the groups. */
  heading?: string
  /** A line under the groups. */
  hint?: string
  /** Entries can be dragged out of the column and onto a canvas. */
  draggable?: boolean
  /**
   * Entries to light, beside whichever one is active.
   *
   * The Latent Lab's overview map points at instruments without naming them:
   * its markers carry no labels, and the names they mean are the ones already
   * standing here. Rows only, like `activeId` — a tile is an action.
   */
  highlightIds?: string[]
}>()

const highlighted = computed(() => new Set(props.highlightIds ?? []))

const emit = defineEmits<{
  select: [id: string]
}>()

// Icon URL helper
function getIconUrl(iconPath: string): string {
  return new URL(`../../assets/icons/${iconPath}`, import.meta.url).href
}

/** An entry's marks, however it spelled them: one `icon`, or several `icons`. */
function marksOf(item: RailItem): string[] {
  if (item.icons?.length) return item.icons
  return item.icon ? [item.icon] : []
}

/**
 * Canvas's module catalogue, used when no groups are handed in.
 *
 * NOTE: Safety is NOT shown here - DevServer handles it automatically
 * The unified evaluation node replaces 5 eval + 2 fork nodes
 */
const CANVAS_CATEGORIES: { id: string; labelKey: string; types: StageType[] }[] = [
  { id: 'input', labelKey: 'canvas.palette.input',
    types: ['input', 'image_input', 'random_prompt'] },
  { id: 'interception', labelKey: 'canvas.palette.interception',
    types: ['interception', 'evaluation', 'image_evaluation', 'comparison_evaluator'] },
  { id: 'adaption', labelKey: 'canvas.palette.adaption',
    types: ['translation', 'model_adaption'] },
  { id: 'generate', labelKey: 'canvas.palette.generate',
    types: ['generation'] },
  // Parameter nodes (seed, resolution, quality) + display under Tools
  { id: 'tools', labelKey: 'canvas.palette.tools',
    types: ['seed', 'resolution', 'quality', 'display'] },
]

function getNodeDef(type: StageType): NodeTypeDefinition | undefined {
  return NODE_TYPE_DEFINITIONS.find(n => n.type === type)
}

const canvasGroups = computed<RailGroup[]>(() =>
  CANVAS_CATEGORIES.map(cat => ({
    id: cat.id,
    label: t(cat.labelKey),
    items: cat.types.map(type => {
      const def = getNodeDef(type)
      return {
        id: type,
        label: def ? t(def.labelKey) : type,
        title: def ? t(def.descriptionKey) : '',
        icon: def?.icon,
        color: def?.color,
      }
    }),
  }))
)

const shownGroups = computed<RailGroup[]>(() => props.groups ?? canvasGroups.value)
const shownHeading = computed(() => props.heading ?? t('canvas.modules'))
const shownHint = computed(() => props.hint ?? t('canvas.dragHint'))

const root = ref<HTMLElement | null>(null)

/** The lit rows, in the order they stand in the column. */
function litRows(): HTMLElement[] {
  return [...(root.value?.querySelectorAll<HTMLElement>('.module-btn.lit') ?? [])]
}

/**
 * The column's own scroll box, and nothing above it.
 *
 * `scrollIntoView` walks every scroll parent it finds; the surface behind this
 * one must not move because a pointer crossed a marker on a map. Three levels
 * at most, and never the document.
 */
function scrollBox(): HTMLElement | null {
  let box = root.value?.parentElement ?? null
  for (let up = 0; box && up < 3; up++) {
    if (box === document.body) return null
    const oy = getComputedStyle(box).overflowY
    if ((oy === 'auto' || oy === 'scroll') && box.scrollHeight > box.clientHeight) return box
    box = box.parentElement
  }
  return null
}

/**
 * Bring the lit rows into the column.
 *
 * ALL of them when they fit together — three instruments can light at one
 * marker and they are not always neighbours, and a caller that only pulled the
 * first into view would leave the others lighting below the fold, seen by
 * nobody. When the run is taller than the column, the first one wins.
 */
function revealLit(): void {
  const rows = litRows()
  const box = scrollBox()
  if (!rows.length || !box) return
  const c = box.getBoundingClientRect()
  const pad = 28
  const rects = rows.map(r => r.getBoundingClientRect())
  const top = Math.min(...rects.map(r => r.top))
  const bottom = Math.max(...rects.map(r => r.bottom))
  const fits = bottom - top <= c.height - pad * 2
  let over = 0
  if (top < c.top + pad) over = top - c.top - pad
  else if (fits ? bottom > c.bottom - pad : top > c.bottom - pad) {
    over = fits ? bottom - c.bottom + pad : top - c.top - pad
  }
  // Instant, not smooth: the name has to be standing there when the eye
  // arrives, and a hover can be gone again before an animation ends.
  if (over) box.scrollTop += over
}

watch(() => props.highlightIds, ids => {
  if (!ids?.length) return
  nextTick(revealLit)
})

/**
 * Put the focus on the first lit entry that can actually be opened.
 *
 * The surface that lights an entry from outside (the Latent Lab's map) has no
 * handle on this column; without this, pressing a marker would light a name and
 * leave the visitor to find it. A locked entry is focused only if every lit one
 * is locked — then its hover text is the reason, and that is what there is to
 * read.
 */
function focusHighlighted(): void {
  const rows = litRows()
  const first = rows[0]
  if (!first) return
  revealLit()
  const open = rows.find(r => r.getAttribute('aria-disabled') !== 'true')
  // `preventScroll`, because a bare `.focus()` hands the browser a scroll into
  // view up EVERY ancestor — and `revealLit` above exists precisely so that
  // nothing but this column moves.
  ;(open ?? first).focus({ preventScroll: true })
}

defineExpose({ focusHighlighted })

function onSelect(item: RailItem) {
  if (item.disabled) return
  emit('select', item.id)
}

function onDragStart(e: DragEvent, id: string) {
  if (!props.draggable) return
  e.dataTransfer?.setData('nodeType', id)
  e.dataTransfer!.effectAllowed = 'copy'
}
</script>

<template>
  <div ref="root" class="module-palette" :class="{ 'palette-rows': !!groups }">
    <h3 v-if="shownHeading">{{ shownHeading }}</h3>

    <div
      v-for="cat in shownGroups"
      :key="cat.id"
      class="category"
    >
      <!-- A group may have no title. The first entry of the Latent Lab column
           is the overview of the whole lab: it stands over the categories, not
           in one, so a heading above it would have to invent a category name
           for a single entry. Rendered unconditionally the empty string left a
           blank line and an aria-labelledby pointing at nothing. -->
      <h4 v-if="cat.label" :id="`rail-grp-${cat.id}`">{{ cat.label }}</h4>
      <div
        class="module-list"
        role="group"
        :aria-labelledby="cat.label ? `rail-grp-${cat.id}` : undefined"
      >
        <button
          v-for="item in cat.items"
          :key="item.id"
          class="module-btn"
          :class="{
            plain: !item.color,
            active: item.id === activeId,
            lit: highlighted.has(item.id),
          }"
          :style="item.color ? { '--node-color': item.color } : undefined"
          :title="item.title || ''"
          :aria-disabled="item.disabled ? 'true' : undefined"
          :aria-current="item.id === activeId ? 'true' : undefined"
          :draggable="draggable && !item.disabled"
          @dragstart="onDragStart($event, item.id)"
          @click="onSelect(item)"
        >
          <span v-if="marksOf(item).length" class="module-marks">
            <template v-for="mark in marksOf(item)" :key="mark">
              <img
                v-if="mark.endsWith('.svg')"
                :src="getIconUrl(mark)"
                alt=""
                class="module-icon-svg"
              />
              <span v-else class="module-icon">{{ mark }}</span>
            </template>
          </span>
          <span class="module-label">{{ item.label }}</span>
        </button>
      </div>
    </div>

    <div v-if="shownHint" class="palette-help">
      <p>{{ shownHint }}</p>
    </div>
  </div>
</template>

<style scoped>
.module-palette {
  color: #e2e8f0;
  padding: 0.75rem 1rem;
}

h3 {
  font-size: 0.875rem;
  font-weight: 700;
  margin: 0 0 1rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
}

.category {
  margin-bottom: 0.6rem;
}

h4 {
  font-size: 0.6875rem;
  font-weight: 400;
  margin: 0 0 0.35rem;
  color: #64748b;
  text-transform: uppercase;
}

.module-list {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.module-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: var(--node-color);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 0.8125rem;
  font-weight: 400;
  text-align: left;
  cursor: grab;
  /* Named properties, never `all`. `all` puts font-size, min-height and padding
     under a transition too, and a length written in container units (see the
     rows-mode block below) is then FROZEN at whatever it resolved to on the
     first style pass - before the container had been laid out, so at the floor
     of its own clamp. The row read 11.5px where its rule says 13, and nothing
     later moved it. Nothing here needs a size to travel; what changes on hover
     and on the active row is colour, tint, bar and shift. */
  transition:
    background-color 0.15s,
    border-color 0.15s,
    box-shadow 0.15s,
    color 0.15s,
    filter 0.15s,
    transform 0.15s;
}

.module-btn:hover {
  filter: brightness(1.1);
  transform: translateX(2px);
}

.module-btn:active {
  cursor: grabbing;
}

/* An entry without a colour: a row in a menu, not a tile to be dragged. It
   reaches the column's edges, so the mark of the active one sits at the very
   left and the label still lines up with the group titles above it. */
/* Tighter vertical padding than the base .module-btn: with ~25 rows in
   the Latent Lab column, the base rhythm pushed the last groups below the
   fold. */
.module-btn.plain {
  margin: 0 -1rem;
  padding: 0.22rem 1rem 0.22rem calc(1rem - 3px);
  border-left: 3px solid transparent;
  border-radius: 0;
  background: transparent;
  color: rgba(255, 255, 255, 0.62);
  font-weight: 400;
  cursor: pointer;
}

/* THE RAIL COLUMN OF A SHELL PAGE (the Latent Lab hands in its own groups;
   Canvas uses the catalogue above). Twenty-nine rows under six rubrics have to
   stand on one page without a scroll: on the reference iPad's 1210x834 window
   the rail is 667px tall, and this column measures 656.

   A list has ONE rhythm. This one once took the rail's full height and handed
   the surplus back to the gaps between rows - each group grew with the number
   of rows it held, and inside a group the rows spread over what the group got.
   On a tall window that drove the rows apart while every rubric stayed welded
   to the row above it, so the air landed everywhere except where a reader
   needs it: huge gaps between the entries and no spacing at the categories.
   The rhythm is fixed now and the column stands at its own height, the same on
   every window: rows close together, a clear step above every rubric.

   What pays for that step is the MARK: 17px at the reference window instead of
   the 20 the Canvas tiles carry. Three pixels a row over twenty-nine rows is
   the whole step, and the three pixels of width it frees are what keep the
   longest English label on ONE line. Scoped to the rows mode, so the coloured,
   draggable tiles of Canvas keep the rhythm they have. */
.module-palette.palette-rows {
  /* EVERY measure in this column is a fraction of the rail's own height
     (`cqh`, against the size container .shell-rail sets), so the column keeps
     one proportion on every screen instead of one pixel count on one window.
     The numbers are set at the reference iPad, where the rail is 667px tall,
     and they are set for THIRTY-ONE rows: the twenty-nine that stand here plus
     two reserved for instruments to come. The column fits by construction, and
     what the two reserved rows leave standing empty today is the tail below
     the last entry.

     The clamps are the two ends where a proportion stops being one: under a
     short rail the type would fall below reading size, so it holds at the floor
     and the column scrolls; over a tall one a menu that kept growing would end
     up shouting, so it holds at the ceiling and lets the rail run out under it.
     A menu that ENDS is the right picture there - the surplus stays out of the
     gaps between the rows, which is where it used to go. */
  --rail-mark: clamp(13px, 2.4cqh, 22px);
  --rail-fs: clamp(11.5px, 1.87cqh, 16px);
  --rail-rubric-fs: clamp(9px, 1.58cqh, 13px);
  --rail-step: clamp(6px, 1.58cqh, 24px);
  --rail-lead: clamp(1px, 0.3cqh, 5px);
  /* The air INSIDE a row, over and above the mark, and the last thing served.
     Under a rail of about 917px every pixel of height is already spoken for:
     the mark is still growing with the rail, and thirty-one rows of it plus the
     rubrics come to the whole column. Air there would be taken off the two rows
     held in reserve, so there is none. Above it the mark stands at its 22px
     ceiling and stops asking, and what the rail gains from then on goes into
     the rows - up to 4px a side, so that a very tall window opens the leading
     rather than growing one long hole under the last entry. */
  --rail-air: clamp(0px, calc(1.4cqh - 12.85px), 4px);

  display: flex;
  flex-direction: column;
  min-height: 100%;
  box-sizing: border-box;
  padding-top: clamp(2px, 0.6cqh, 8px);
  padding-bottom: clamp(2px, 1.2cqh, 16px);
}

.module-palette.palette-rows .category {
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  margin-bottom: 0;
}

/* The step between two groups, and the only real piece of leading in the
   column. It sits ABOVE the rubric, so the rubric reads with the rows under it
   rather than with the group it follows. */
.module-palette.palette-rows .category + .category {
  margin-top: var(--rail-step);
}

.module-palette.palette-rows h4 {
  font-size: var(--rail-rubric-fs);
  margin-bottom: var(--rail-lead);
  line-height: 1.1;
}

.module-palette.palette-rows .module-list {
  gap: 0;
}

/* A row is as tall as its mark and no taller; the label sits in a line of 1.15
   and stays inside that. The right edge gives up 6px and the space before the
   label 2px - width the labels need more than the rail's margin does. */
.module-palette.palette-rows .module-btn.plain {
  padding-top: var(--rail-air);
  padding-bottom: var(--rail-air);
  padding-right: 0.625rem;
  gap: 0.375rem;
  min-height: var(--rail-mark);
  font-size: var(--rail-fs);
  line-height: 1.15;
}

.module-palette.palette-rows .module-icon-svg {
  width: var(--rail-mark);
  height: var(--rail-mark);
}

.module-palette.palette-rows .module-icon {
  font-size: calc(var(--rail-mark) * 0.82);
}

/* A name too long for the width even so (French and Spanish) takes a second
   line rather than being cut off: the column scrolls in those languages and the
   name stays readable. */
.module-palette.palette-rows .module-label {
  min-width: 0;
}

.module-btn.plain:hover {
  filter: none;
  transform: none;
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.module-btn.plain.active {
  background: rgba(76, 175, 80, 0.1);
  border-left-color: #4CAF50;
  color: #ffffff;
}

/* Pointed at from somewhere else on the surface. Brighter than `active`, and
   its bar is on the right, so an entry that is both does not lose either. */
.module-btn.plain.lit {
  background: rgba(76, 175, 80, 0.2);
  box-shadow: inset -3px 0 0 #4CAF50;
  color: #ffffff;
}

/* A LOCKED entry still lights: it IS the instrument being pointed at, and the
   marker cannot know that this card has no VRAM for it. It keeps the dim text
   and the barred cursor, and — this is the bug it fixes — pointing AT it must
   not put the light out, which the plain locked hover rule below did. */
.module-btn.plain.lit[aria-disabled='true'],
.module-btn.plain.lit[aria-disabled='true']:hover {
  background: rgba(76, 175, 80, 0.1);
  color: rgba(255, 255, 255, 0.4);
}

.module-btn.plain[aria-disabled='true'] {
  color: rgba(255, 255, 255, 0.28);
  cursor: not-allowed;
}

.module-btn.plain[aria-disabled='true']:hover {
  background: transparent;
  color: rgba(255, 255, 255, 0.28);
}

.module-icon {
  font-size: 1rem;
}

.module-icon-svg {
  width: 20px;
  height: 20px;
  filter: brightness(0) invert(1); /* Make SVG white */
}

/* The marks of one entry, side by side in the slot ahead of the label. Tighter
   than the button's own gap, so two marks read as one group and not as two
   things with the label pushed off.

   The slot is sized to what it holds, NOT to two marks. Reserving the width of
   two (20 + 4 + 20) lines every label up at one x, and was measured worse: it
   takes 24 px off every single-mark row's text and pushed six names in this
   column onto a second line, which makes the whole column taller and busier
   than the ragged left edge it tidies. Four rows out of twenty-two start a
   mark's width further right; that is the cheaper of the two. */
.module-marks {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.module-label {
  flex: 1;
}

.palette-help {
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--shell-line, var(--surface-4));
}

.palette-help p {
  font-size: 0.75rem;
  color: #64748b;
  margin: 0;
  line-height: 1.4;
}
</style>
