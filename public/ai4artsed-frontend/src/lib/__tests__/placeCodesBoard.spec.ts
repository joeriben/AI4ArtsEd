import { describe, expect, it } from 'vitest'
import {
  BOARD_GAP,
  BOARD_HEAD,
  BOARD_PAD,
  CODE_LINE,
  PLACE_LINE,
  PLACE_SIZE,
  TILE_BORDER,
  boardLayout,
} from '../placeCodesBoard'

/** What a tile of code size `size` takes, in pixels, as PlaceCodesBoard.vue
 *  draws it: across, five characters of 0.6 em with 0.12 em of spacing after
 *  each, the spacing given back at the start and 0.24 em of room on either
 *  side; down, the code's line and the place's line and 0.28 em of room above
 *  and below; around both, the border. */
function tileTakes(size: number): { w: number; h: number } {
  return {
    w: size * (5 * (0.6 + 0.12) + 0.12 + 2 * 0.24) + 2 * TILE_BORDER,
    h: size * (CODE_LINE + PLACE_SIZE * PLACE_LINE + 2 * 0.28) + 2 * TILE_BORDER,
  }
}

describe('boardLayout', () => {
  it('sets thirty places on a 1920 x 1080 projector in six columns, at about 70 px', () => {
    expect(boardLayout(30, 1920, 1080)).toEqual({ cols: 6, size: 71 })
  })

  it('sets a hundred places in ten columns, at about 40 px', () => {
    expect(boardLayout(100, 1920, 1080)).toEqual({ cols: 10, size: 40 })
  })

  it('holds a few places at the largest size', () => {
    expect(boardLayout(1, 3840, 2160).size).toBe(200)
  })

  it('keeps every tile inside the window, from a phone to a projector, for 1 to 100 places', () => {
    const windows: Array<[number, number]> = [
      [375, 667], [667, 375], [390, 844], [800, 600], [1024, 768],
      [1180, 820], [1366, 768], [1920, 1080], [3840, 2160],
    ]
    for (const [w, h] of windows) {
      for (let n = 1; n <= 100; n++) {
        const { cols, size } = boardLayout(n, w, h)
        const rows = Math.ceil(n / cols)
        const tile = tileTakes(size)
        expect(cols * tile.w + (cols - 1) * BOARD_GAP).toBeLessThanOrEqual(w - 2 * BOARD_PAD)
        expect(rows * tile.h + (rows - 1) * BOARD_GAP).toBeLessThanOrEqual(h - 2 * BOARD_PAD - BOARD_HEAD)
      }
    }
  })

  it('answers a window too small with one pixel, not with nothing', () => {
    expect(boardLayout(40, 100, 100).size).toBe(1)
  })
})
