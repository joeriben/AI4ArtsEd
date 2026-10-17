/**
 * The two cell helpers the series rasters share (components/InterceptionSeriesGrid.vue
 * and InterceptionSeriesWall.vue carried them letter for letter until 2026-10-10).
 */
import type { RasterCell } from '@/composables/useRasterRun'
import type { SeriesGridColumn, SeriesRow } from '@/composables/useInterceptionSeries'
import { downloadMedia, mediaFileName, runStem } from '@/lib/downloadMedia'

/**
 * The cell's place in the raster, under the picture when it stands large: the
 * row's name and the model's. What made the picture stands beside it, on the
 * cell's own back (components/MediaGridCell.vue, since 2026-09-22).
 */
export function placeOf(row: SeriesRow | undefined, column: SeriesGridColumn): string {
  return [row?.label, column.label].filter(Boolean).join(' · ')
}

/**
 * The picture of one cell onto the disk. The raster does it itself rather than
 * handing it up: it holds everything the name is made of - the model, the row's
 * own key, the seed and the run - and a surface asked for it would answer with
 * the same four.
 */
export function saveCell(
  column: SeriesGridColumn,
  cell: RasterCell,
  row: SeriesRow | undefined,
  fileStem: string | undefined,
): void {
  if (!cell.url) return
  void downloadMedia(
    cell.url,
    mediaFileName(fileStem || 'series', [
      runStem(cell.runId),
      column.id,
      row?.key,
      `seed${cell.seed}`,
    ]),
  )
}
