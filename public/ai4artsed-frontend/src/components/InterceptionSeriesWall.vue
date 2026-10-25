<!--
  The WALL of an interception series: one image model, one picture per row, laid
  side by side and wrapped.

  The sister of `components/InterceptionSeriesGrid.vue`, and the same run behind
  both (`composables/useInterceptionSeries.ts`). Where the raster asks what
  SEVERAL image models make of the same text, the wall asks what MANY
  perspectives do to the same template — and there the pictures are the point:
  the raster's third column is a reading, and at twelve rows its cells were 110
  px, and at that size too little of a picture is visible.

  So the text steps out of the raster and hangs on the SYMBOL: resting on a
  row's disc — holding it, on the reference device — opens the card with what
  that perspective wrote, marked words and all. The card is the platform's own
  (`components/InfoCard.vue`), the same one a model field carries.

  Transposed, the rows run across; wrapped, because twelve large pictures in one
  band would leave the window. The reading direction of the wall is the order of
  the rows, which is the order the perspectives were chosen in.

  What a row IS stays the surface's, as it is in the raster: the disc comes
  through the slot.
-->
<template>
  <div class="lab-wall" :style="{ '--wall-min': `${minCell}px` }">
    <!-- A picture that was not made here, where the surface passes one: the
         picture the template was read from. It stands first because it comes
         before everything beside it, and it carries a name and nothing else -
         there is no run behind it to open. -->
    <div v-if="lead" class="lab-wall-item">
      <div class="instr-frame">
        <div class="instr-stack">
          <div
            class="instr-square lab-wall-lead"
            :style="{ backgroundImage: `url(${lead.url})` }"
          ></div>
        </div>
      </div>
      <div class="lab-wall-badge">
        <span class="lab-wall-name">{{ lead.label }}</span>
      </div>
    </div>

    <div
      v-for="(cell, i) in column.cells"
      :key="cell.key"
      class="lab-wall-item"
      :class="{ ground: rows[i]?.reference }"
    >
      <div class="instr-frame">
        <div class="instr-stack">
          <MediaGridCell
            :url="cell.url"
            :run-id="cell.runId ?? null"
            :prompt="adapted[cell.key] || ''"
            :intercepted="rows[i]?.text || ''"
            :intercepted-label="interceptedLabel"
            :config-id="column.id"
            :created-at="cell.createdAt"
            :model-meta="cell.modelMeta ?? null"
            :duration-ms="cell.durationMs ?? 0"
            :facts="[`seed ${cell.seed}`]"
            :note="note(cell)"
            :label="place(rows[i], column)"
            @download="save(column, cell, rows[i])"
          />
        </div>
      </div>

      <!-- Which row this is, on the foot of its picture: the disc, and the name
           beside it. The card hangs on this, not on the picture — the picture is
           the answer, the disc is the question it was asked. -->
      <div
        class="lab-wall-badge"
        @pointerenter="openCard(rows[i], $event)"
        @pointerleave="closeCard"
        @pointerdown="pressCard(rows[i], $event)"
        @pointerup="releaseCard"
        @pointercancel="releaseCard"
      >
        <div class="lab-wall-face"><slot name="row-face" :row="rows[i]" /></div>
        <span class="lab-wall-name">{{ rows[i]?.label }}</span>
      </div>
    </div>

    <InfoCard :open="!!shown" :x="x" :y="y" :above="above" :width="340">
      <template v-if="shown">
        <div class="lab-wall-card-name">{{ shown.label }}</div>
        <!-- What the row was ASKED, where that is more than its name. The
             perspectives are one word and need none of this; a checklist set
             property by property is what the row IS, and it stands over what
             the model wrote from it. -->
        <div v-if="$slots['row-card']" class="lab-wall-card-lines">
          <slot name="row-card" :row="shown" />
        </div>
        <p v-if="shown.text" class="lab-wall-card-text">
          <span
            v-for="(seg, si) in shown.segments"
            :key="si"
            :class="{ 'ilm-hit': seg.hit }"
            >{{ seg.t }}</span
          >
        </p>
        <span v-else class="lab-wall-card-said">{{
          shown.failedKey ? t(shown.failedKey) : notYetRunLabel
        }}</span>
      </template>
    </InfoCard>
  </div>
</template>

<script setup lang="ts" generic="T extends SeriesRow">
import { useI18n } from 'vue-i18n'
import MediaGridCell from '@/components/MediaGridCell.vue'
import InfoCard from '@/components/InfoCard.vue'
import { useInfoCard } from '@/composables/useInfoCard'
import type { RasterCell } from '@/composables/useRasterRun'
import type { SeriesGridColumn, SeriesRow } from '@/composables/useInterceptionSeries'
import { placeOf, saveCell } from '@/lib/seriesGridCells'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    rows: T[]
    /** The ONE image model. A wall compares perspectives, never models. */
    column: SeriesGridColumn
    /** What a row that has not run yet says, on the card. */
    notYetRunLabel: string
    /** What the picture in a cell was made from, by cell key. */
    adapted: Record<string, string>
    /**
     * How this page names the text Prompt Interception wrote. Given, the card's
     * back carries that text over the adapted one; left out, the back is what
     * it was. The text itself is the row's own (`SeriesRow.text`).
     */
    interceptedLabel?: string
    /** What stands in a cell instead of a medium, already in the reader's language. */
    note: (cell: RasterCell) => string
    /**
     * A picture that stands FIRST and is not a run - the one the template
     * was read from. Left out, the wall begins with its first cell.
     */
    lead?: { url: string; label: string } | null
    /** How small a picture may get before the wall takes a column away. */
    minCell?: number
    /**
     * The first word of a saved picture's file name - the surface it came from.
     * Two instruments share this wall, and in a downloads folder their files
     * would otherwise be one undifferentiated series.
     */
    fileStem?: string
  }>(),
  { minCell: 260 }
)

// The cell's place and its download are the raster's two helpers in
// lib/seriesGridCells, shared with the other series raster.
function place(row: T | undefined, column: SeriesGridColumn): string {
  return placeOf(row, column)
}

function save(column: SeriesGridColumn, cell: RasterCell, row: T | undefined): void {
  saveCell(column, cell, row, props.fileStem)
}

defineSlots<{
  /** The disc a row is shown as, in the corner of its picture. A surface whose
      rows wear none - a setting is carried by its name - passes nothing here. */
  'row-face'?(props: { row: T | undefined }): unknown
  /** What the row was asked, on its card, over what the model wrote. */
  'row-card'(props: { row: T | undefined }): unknown
}>()

const {
  shown,
  x,
  y,
  above,
  enter: openCard,
  down: pressCard,
  up: releaseCard,
  close: closeCard,
} = useInfoCard<T>()
</script>

<style scoped>
/* As many pictures per line as fit at the size they are meant to be seen at,
   and the rest on the next line. It scrolls in ITSELF: `.lab-plot` clips, and
   what a wall shows is longer than a screen as soon as a dozen perspectives
   stand in it. */
.lab-wall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--wall-min, 260px)), 1fr));
  gap: 12px;
  align-content: start;
  max-height: 100%;
  overflow-y: auto;
  padding-right: 4px;
}

/* One picture, square, with its badge on its foot. The square is the platform's
   own surface (`.instr-frame`/`.instr-stack`); here the item is square already,
   so the frame has a square to measure. */
.lab-wall-item {
  position: relative;
  aspect-ratio: 1;
  min-width: 0;
  display: flex;
}

/* The leading picture. It is not a cell of the run, so it carries the edge
   and the radius of one rather than the cell itself. */
.lab-wall-lead {
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: var(--surface-2) center / cover no-repeat;
}

.lab-wall :deep(.media-grid-cell) {
  width: 100%;
  min-height: 0;
}

/* The row that is the GROUND of the comparison rather than one of its cases is
   marked, in the lab's own green and quietly — the same distinction the raster
   draws with `.lab-grid-head.bare`. ONE ring: the mark stood as a SECOND border
   next to the cell's own — 1 px of green at a radius of 8 px against 1 px of
   white at 6 px, a pixel apart — so the cell's edge steps back and the mark
   takes its place, at its radius (2026-09-05). An outline rather than a border,
   because a border on the item would take 2 px off this picture and leave it
   narrower than every other picture on the wall. */
.lab-wall-item.ground {
  outline: 1px solid rgb(76 175 80 / 0.45);
  outline-offset: -1px;
  border-radius: 6px;
}

.lab-wall-item.ground :deep(.media-grid-cell) {
  border-color: transparent;
}

/* On the foot of the picture, so the picture keeps its whole square. It is not
   a caption under the cell: a row of captions between the lines would cost a
   line of pictures. */
.lab-wall-badge {
  position: absolute;
  left: 8px;
  bottom: 8px;
  /* As wide as the disc and the name, never wider: the card hangs on THIS, and
     a strip running to the far edge would open it over empty picture. */
  width: fit-content;
  max-width: calc(100% - 16px);
  display: flex;
  align-items: center;
  gap: 8px;
  pointer-events: auto;
}

.lab-wall-face {
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  display: flex;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.7));
}

/* A row whose face the surface leaves empty gets no hole where a disc would be:
   the name then stands alone on the foot of the picture. */
.lab-wall-face:empty {
  display: none;
}

.lab-wall-name {
  min-width: 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.25;
  color: rgba(255, 255, 255, 0.92);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* What stands in the card: the name of the perspective, and under it what it
   wrote. Prose, so it may be wider than a card of facts. */
/* The setting a row was run with, over what the model wrote from it. */
.lab-wall-card-lines {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-bottom: 6px;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.6);
}

.lab-wall-card-name {
  font-size: 0.8rem;
  line-height: 1.35;
  color: rgba(255, 255, 255, 0.95);
  margin-bottom: 0.25rem;
}

.lab-wall-card-text {
  margin: 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.72);
}

.lab-wall-card-said {
  font-size: var(--flow-fs-hint);
  font-style: italic;
  color: #7d8da3;
}

/* A word of the perspective that made it into the text, in the lab's own green
   at low alpha: it marks, it does not shout. The raster paints it the same. */
.ilm-hit {
  background: rgb(76 175 80 / 0.25);
  border-radius: 2px;
  padding: 0 1px;
}
</style>
