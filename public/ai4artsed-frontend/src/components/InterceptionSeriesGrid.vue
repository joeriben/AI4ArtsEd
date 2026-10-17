<!--
  The raster of an interception series: the row names, the READING, and one
  column of squares per image model.

  Lifted out of Interception across Models (views/latent_lab/interception_models
  .vue) on 2026-09-04, when the second instrument of the group needed the same
  raster with another row axis. It is the same markup, moved — `.lab-grid
  .labelled.reading` with its three kinds of column — and the class names it
  carries are the ones it was written under.

  WHAT IS READ IS THE TEXT. The pictures stand beside the texts as their
  illustration, which is why the reading takes the width it needs and the
  squares share what is left.

  The HEAD of a row comes from the surface through the slot: what stands beside
  a row's name — the mark of a service, the disc of a perspective, the picture a
  line was read from — is what that surface's rows ARE, and it is the one thing
  the two instruments do not share. The box around it is here, so the rows keep
  standing beside the cells they name.
-->
<template>
  <div
    ref="gridEl"
    class="lab-grid labelled reading"
    :style="{
      '--lab-grid-cols': columns.length,
      '--lab-grid-rows': rows.length,
      '--lab-grid-cell': cellPx ? `${cellPx}px` : '',
    }"
  >
    <!-- Which row a row is, said once at its left end. -->
    <div class="lab-grid-col">
      <div class="lab-grid-head"></div>
      <div class="lab-series">
        <div
          v-for="row in rows"
          :key="row.key"
          class="lab-grid-rowname"
          :class="[headClass, { bare: row.reference }]"
        >
          <slot name="row-head" :row="row" />
        </div>
      </div>
    </div>

    <!-- What is read. It scrolls inside its own field, as the reading columns
         of Image Understanding do: a cell that grew with the longest text would
         push the last row off the surface, and the side-by-side is the whole
         point. -->
    <div class="lab-grid-col">
      <div class="lab-grid-head">{{ interceptedLabel }}</div>
      <div class="lab-series">
        <div
          v-for="row in rows"
          :key="row.key"
          class="ilm-text"
          :class="{ pending: !row.text }"
        >
          <p v-if="row.text">
            <span
              v-for="(seg, i) in row.segments"
              :key="i"
              :class="{ 'ilm-hit': seg.hit }"
              >{{ seg.t }}</span
            >
          </p>
          <span v-else-if="row.failedKey" class="ilm-said">{{ t(row.failedKey) }}</span>
          <span v-else class="ilm-said">{{ notYetRunLabel }}</span>
        </div>
      </div>
    </div>

    <!-- One column per image model. The cell is the platform's own
         (components/MediaGridCell.vue) in its square surface. -->
    <div v-for="col in columns" :key="col.id" class="lab-grid-col">
      <div class="lab-grid-head">{{ col.label }}</div>
      <div class="lab-series">
        <div v-for="(cell, ri) in col.cells" :key="cell.key" class="instr-frame">
          <div class="instr-stack">
            <MediaGridCell
              :url="cell.url"
              :run-id="cell.runId ?? null"
              :prompt="adapted[cell.key] || ''"
              :config-id="col.id"
              :created-at="cell.createdAt"
              :model-meta="cell.modelMeta ?? null"
              :duration-ms="cell.durationMs ?? 0"
              :facts="[`seed ${cell.seed}`]"
              :note="note(cell)"
              :label="place(rows[ri], col)"
              @download="save(col, cell, rows[ri])"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends SeriesRow">
import { useI18n } from 'vue-i18n'
import MediaGridCell from '@/components/MediaGridCell.vue'
import { useGridCellWidth } from '@/composables/useGridCellWidth'
import type { RasterCell } from '@/composables/useRasterRun'
import type { SeriesGridColumn, SeriesRow } from '@/composables/useInterceptionSeries'
import { placeOf, saveCell } from '@/lib/seriesGridCells'

const { t } = useI18n()

const props = defineProps<{
  rows: T[]
  columns: SeriesGridColumn[]
  /** What the reading column is called. */
  interceptedLabel: string
  /** What a row that has not run yet says. */
  notYetRunLabel: string
  /** What the picture in a cell was made from, by cell key. */
  adapted: Record<string, string>
  /** What stands in a cell instead of a medium, already in the reader's language. */
  note: (cell: RasterCell) => string
  /** What the surface calls its row heads, so it can lay them out itself. */
  headClass?: string
  /**
   * The first word of a saved picture's file name - the surface it came from.
   * Three instruments share this raster, and in a downloads folder their files
   * would otherwise be one undifferentiated series.
   */
  fileStem?: string
}>()

// The cell's place and its download are the raster's two helpers in
// lib/seriesGridCells, shared with the other series raster.
function place(row: T | undefined, column: SeriesGridColumn): string {
  return placeOf(row, column)
}

function save(column: SeriesGridColumn, cell: RasterCell, row: T | undefined): void {
  saveCell(column, cell, row, props.fileStem)
}

defineSlots<{
  /** What stands at a row's left end, beside and under its name. */
  'row-head'(props: { row: T }): unknown
}>()

/**
 * How wide a picture column is. The raster measures ITSELF: the cap has to be
 * one number for the whole grid, and only the element that carries it can be
 * asked (composables/useGridCellWidth.ts). The reading stands between the names
 * and the pictures, so the first PICTURE column is the third series.
 */
const { gridEl, cellPx } = useGridCellWidth(
  () => [props.columns.length, props.rows.length],
  { seriesIndex: 2 },
)
</script>

<style scoped>
/* The page skeleton, the frame, the raster and the square cell are shared and
   stand in assets/flow-stage.css and assets/instrument-surface.css. What is
   here is what this raster alone needs. */

/* The row that is the GROUND of the comparison rather than one of its cases
   says so more quietly — the same distinction `.lab-grid-head.bare` draws. */
.lab-grid-rowname.bare {
  color: rgba(255, 255, 255, 0.45);
  font-style: italic;
}

/* What is read. It takes the height its row gives it and scrolls inside, as the
   reading columns of Image Understanding do. Its ground is the surface stack,
   never a literal. */
.ilm-text {
  min-height: 0;
  overflow-y: auto;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 6px 9px;
}

.ilm-text p {
  margin: 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.72);
}

.ilm-text.pending {
  display: grid;
  place-items: center;
  opacity: 0.45;
}

.ilm-said {
  font-size: var(--flow-fs-hint);
  font-style: italic;
  color: #7d8da3;
  text-align: center;
}

/* A word of the perspective that made it into the text, in the lab's own green
   at low alpha: it marks, it does not shout. */
.ilm-hit {
  background: rgb(76 175 80 / 0.25);
  border-radius: 2px;
  padding: 0 1px;
}
</style>
