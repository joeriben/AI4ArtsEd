/**
 * How the codes of a course's places stand on a projector
 * (components/PlaceCodesBoard.vue, 2026-11-14): as many columns as give the
 * largest code, computed from the window and the number of places. The board
 * sets the lines and the border of its tiles from the numbers here, so the
 * tile computed is the tile drawn.
 */

/** The board's padding, the head row with the course and where a code is
 *  entered, and the gap between the tiles, in pixels. */
export const BOARD_PAD = 24
export const BOARD_HEAD = 64
export const BOARD_GAP = 12

/** The lines of a tile, in code sizes: the code's line, and the place's
 *  line, whose type is 0.3 of the code's. */
export const CODE_LINE = 1.15
export const PLACE_SIZE = 0.3
export const PLACE_LINE = 1.3

/** A tile's border, in pixels, on each side. */
export const TILE_BORDER = 1

/** A tile inside its border, in code sizes. Across: five characters of a
 *  monospace face, 0.6 em each and each followed by 0.12 em of spacing, which
 *  is given back at the start (3.72 em), and 0.24 em of room on either side.
 *  Down: the code's line and the place's line (1.54 em), and 0.28 em of room
 *  above and below. */
const TILE_W_EM = 4.2
const TILE_H_EM = CODE_LINE + PLACE_SIZE * PLACE_LINE + 0.56

/** The code stops growing where a course has very few places. */
const MAX_SIZE = 200

export interface BoardLayout {
  cols: number
  /** The code's font size in pixels. */
  size: number
}

export function boardLayout(count: number, width: number, height: number): BoardLayout {
  const n = Math.max(1, Math.floor(count))
  const w = Math.max(0, width - 2 * BOARD_PAD)
  const h = Math.max(0, height - 2 * BOARD_PAD - BOARD_HEAD)
  let best: BoardLayout = { cols: 1, size: 0 }
  for (let cols = 1; cols <= n; cols++) {
    const rows = Math.ceil(n / cols)
    const tileW = (w - (cols - 1) * BOARD_GAP) / cols - 2 * TILE_BORDER
    const tileH = (h - (rows - 1) * BOARD_GAP) / rows - 2 * TILE_BORDER
    const size = Math.min(tileW / TILE_W_EM, tileH / TILE_H_EM)
    if (size > best.size) best = { cols, size }
  }
  // At least one pixel: a window too small for its places still gets a size.
  return { cols: best.cols, size: Math.max(1, Math.floor(Math.min(MAX_SIZE, best.size))) }
}

/** Where a code is entered, as the printed slips and the board name it. */
export function signInAddress(): string {
  return `${location.host}/login`
}
