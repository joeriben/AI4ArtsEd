/**
 * How wide a column of a picture raster is, in pixels — and nothing else.
 *
 * The raster (`.lab-grid` / `.lab-series`, assets/flow-stage.css) caps its rows
 * with this number so that the space a surface leaves over stands as ONE strip
 * below the grid instead of as a margin around every single picture. Built
 * inside Cultural (Un)Known on 2026-08-24, moved here on 2026-08-29 when the
 * LoRA Explorer instrument needed the same raster (Rule 13).
 *
 * ⚠️ A measured HEIGHT would be a feedback loop. These surfaces take their
 * height from their own content, so rows with an explicit height push the
 * surface TALLER and the next measurement measures what it has just caused —
 * four rows at 222 px made a 936 px surface out of a 709 px window and kept the
 * 222 (seen 2026-08-24). The width has no such loop: a column's track is set by
 * the grid's width, which the rows cannot move. The height side stays where it
 * always was, in the rows themselves (`minmax(0, 1fr)`), which can only ever
 * divide what the surface gives.
 *
 * Why it is measured at all: the cap has to be ONE number for the whole grid,
 * and in CSS a column knows its width only inside a container query at that
 * column — while the column of names is `auto`, as wide as the longest name, so
 * it would answer differently, cap differently, and its names would stop
 * standing beside the pictures they name.
 */
import { onBeforeUnmount, onMounted, ref, watch, nextTick, type Ref } from 'vue'

export interface GridCellWidth {
  /** Put on the element that carries `.lab-grid`. */
  gridEl: Ref<HTMLElement | null>
  /** The measured width of a picture column, 0 until the first measurement. */
  cellPx: Ref<number>
  /** Measure now. Called by the observer, by `resize` and by the watch below. */
  measure: () => void
}

/**
 * @param counts What changes a column's track without changing the size of the
 *   grid the observer watches — the number of columns and the number of rows.
 */
export interface GridCellWidthOptions {
  /**
   * WHICH `.lab-series` gives the width. Left out, the first PICTURE column
   * does — which is [1] on a labelled grid and [0] without names, and that is
   * what every raster wanted until a grid put a READING column between the
   * names and the pictures (Interception across Models, 2026-09-03). Measured
   * there, [1] is the text and its width would cap the rows several hundred
   * pixels too high.
   */
  seriesIndex?: number
}

export function useGridCellWidth(
  counts: () => unknown[],
  options: GridCellWidthOptions = {},
): GridCellWidth {
  const gridEl = ref<HTMLElement | null>(null)
  const cellPx = ref(0)
  let ro: ResizeObserver | null = null

  function measure(): void {
    const grid = gridEl.value
    if (!grid) return
    const series = grid.querySelectorAll<HTMLElement>('.lab-series')
    // [0] is the column of names where the grid carries one; the first PICTURE
    // column gives the width. A raster without names has its pictures at [0].
    const img =
      options.seriesIndex !== undefined
        ? series[options.seriesIndex]
        : grid.classList.contains('labelled')
          ? series[1]
          : series[0]
    if (!img) return
    const w = img.clientWidth
    if (w > 0) cellPx.value = Math.floor(w)
  }

  /**
   * Three ways in, because no single one of them hears everything:
   * - the observer at the grid, for the window and for anything that changes
   *   the surface without passing through the component;
   * - `resize`, because an observer is not delivered everywhere (in the browser
   *   this was sighted in, neither a `resize` event nor a `ResizeObserver`
   *   arrives when the viewport is set from outside, and the grid would keep
   *   the width it was measured at);
   * - and a column added or a row chosen, which changes the track width without
   *   changing the size of the grid the observer is watching.
   */
  onMounted(() => {
    measure()
    ro = new ResizeObserver(measure)
    if (gridEl.value) ro.observe(gridEl.value)
    window.addEventListener('resize', measure)
  })

  watch(counts, () => {
    void nextTick(measure)
  })

  onBeforeUnmount(() => {
    ro?.disconnect()
    ro = null
    window.removeEventListener('resize', measure)
  })

  return { gridEl, cellPx, measure }
}
