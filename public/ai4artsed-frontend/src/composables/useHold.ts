/**
 * Press and hold.
 *
 * The gesture the flow already carries under a medium glyph: keep the finger
 * down for a moment and something opens; let go, and the click that follows is
 * swallowed, so a hold never also picks. The timer sat inline in x2x_flow until
 * the preset circles needed the same gesture to show their name.
 *
 * ONE duration and ONE meaning, since 2026-09-22: holding shows what lies
 * behind a thing — the info card beside it, the back of a card, the written
 * side of a preset, the description of a config. It ran at four durations and
 * four meanings until then, which is why it could not be learnt and why every
 * object seemed to need a mark of its own. It carries no mark: what an object
 * owes is the answer that the press arrived, and that is `holding` below: the
 * shared `.hold-progress` ring in assets/base.css draws it, and draws it in
 * CSS, so the 450 ms here and the 450 ms there are one number in two places.
 *
 * The one hold that is NOT this gesture stays where it is: holding to stop a
 * run (x2x_flow, 800 ms) triggers rather than shows, says so in words on the
 * box, and draws its own line.
 */
import { getCurrentScope, onScopeDispose, ref } from 'vue'

/**
 * The 450 ms are not a default a caller may override: the ring in
 * assets/base.css runs for the same 450 ms, and a second number here would
 * part the two silently.
 */
const HOLD_MS = 450

export function useHold<T = void>(onHold: (arg: T) => void) {
  /** True from the moment the hold fires until somebody consumes it. */
  const held = ref(false)
  /** A press is down and its moment has not come yet. The ring hangs on this. */
  const holding = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  /**
   * Let go before the moment is up, and nothing happened. A hold that has
   * ALREADY fired stays held on purpose: the click that follows the release
   * still has to be able to consume it, or the hold would also pick.
   */
  function cancel() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    holding.value = false
  }

  function start(arg: T) {
    cancel()
    held.value = false
    holding.value = true
    timer = setTimeout(() => {
      timer = null
      holding.value = false
      held.value = true
      onHold(arg)
    }, HOLD_MS)
  }

  /**
   * Reads the flag and clears it. A click arriving after a hold belongs to the
   * hold, not to a selection — ask this first and return early when it is true.
   */
  function consumeHeld(): boolean {
    const was = held.value
    held.value = false
    return was
  }

  /**
    * A press that outlives its component. The host can be taken off the page
    * mid-hold — a route change, a panel closing under the finger — and the
    * timer then fired into a torn-down instance. Two consumers cancelled
    * nothing of their own, so it is cancelled here, for all of them.
    */
  if (getCurrentScope()) onScopeDispose(cancel)

  return { held, holding, start, cancel, consumeHeld }
}
