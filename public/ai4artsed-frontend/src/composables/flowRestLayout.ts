/**
 * Where the four things a fresh x2x-Flow surface starts with rest: the plus,
 * the LoRA sign, the perspective sign and the prompt box. The three signs
 * stand as a triangle, the plus on top, the LoRA sign lower left of it and the
 * perspective sign lower right; the prompt box lies under the three.
 *
 * Every place is a fraction of the box "Vorbereitung": x of its width,
 * measured from its left edge, y of its height, measured from its bottom edge.
 * The band scales that box with the window, so the arrangement is the same at
 * every window width, only scaled. What does not scale with the box is the
 * size of the signs (`--flow-glyph-fixture`, 3 to 4.125 rem), the band's cap
 * of 1000 px and the action zone of a first visit (radius 240 px). Against
 * these, `__tests__/flowRestLayout.spec.ts` checks the fractions below for
 * every window width from 768 px up.
 */

export interface RestBox {
  left: number
  bottom: number
  width: number
  height: number
}

/**
 * The left end of the band: the box stands 110 of the stage's 1060 in
 * (`RMAP.create` in x2x_flow.vue), and is 300 wide.
 */
const BAND_LEFT = -110 / 300
const PROMPT_BOX_W = 0.8
/** The plus stands over the middle of the prompt box. */
const MIDDLE = BAND_LEFT + PROMPT_BOX_W / 2

/** The middles of the three signs. */
export const PLUS = { x: MIDDLE, y: 1.064 }
export const LORA = { x: MIDDLE - 0.25, y: 2.214 }
export const PERSPECTIVE = { x: MIDDLE + 0.25, y: 2.214 }
/**
 * The prompt box: its upper left corner under the left end of the band, its
 * width, and the height of its text field. The card adds its bar to that.
 */
export const PROMPT_BOX = { x: BAND_LEFT, y: 2.814, w: PROMPT_BOX_W, h: 1.156 }

/**
 * How far each sign is moved off its place on a visit, as a fraction of its
 * own size, each way (`drift` in x2x_flow.vue).
 */
export const JOG = 0.18

/** The places above in the coordinates the box is given in. */
export function restingPlaces(box: RestBox) {
  const at = (f: { x: number; y: number }) => ({
    x: box.left + f.x * box.width,
    y: box.bottom + f.y * box.height,
  })
  return {
    plus: at(PLUS),
    lora: at(LORA),
    perspective: at(PERSPECTIVE),
    promptBox: {
      ...at(PROMPT_BOX),
      w: PROMPT_BOX.w * box.width,
      h: PROMPT_BOX.h * box.height,
    },
  }
}
