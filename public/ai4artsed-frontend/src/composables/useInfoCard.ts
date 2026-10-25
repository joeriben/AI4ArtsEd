import { onBeforeUnmount, ref, type Ref } from 'vue'
import { useHold } from '@/composables/useHold'

/**
 * The card that stands beside a thing and says what it is.
 *
 * It waits before it appears: a pointer crossing a row of twelve fields on its
 * way somewhere else would otherwise flash twelve cards. On a touch screen
 * there is nothing to rest a pointer on, so a long press opens it instead — the
 * same silent gesture as the picture dragged into any input field, and like
 * that one it carries no badge, because it holds everywhere.
 *
 * The press half IS the platform's hold (`useHold`, 450 ms, and the click that
 * ends it is swallowed); what this adds is the resting half, and where the card
 * is put. Built inline in `components/ChipSelect.vue` on 2026-09-04 and lifted
 * out on 2026-09-05, when the wall of Perspectives on a Template needed the
 * same card on a disc instead of a field (Rule 13).
 *
 * What the card SAYS is the caller's: this hands out a payload of whatever type
 * the caller keeps and never looks into it.
 */
export function useInfoCard<T>() {
  const HOVER_DELAY_MS = 350

  /** What the card shows, or nothing while it is down. */
  const shown = ref<T | null>(null) as Ref<T | null>
  const x = ref(0)
  const y = ref(0)
  const above = ref(true)

  let timer: ReturnType<typeof setTimeout> | undefined
  /** The card is up from a long press and no pointer is resting on anything, so
   *  nothing will take it away — the next touch anywhere does. Kept apart from
   *  the hold's own flag, which the click that ends the press consumes: tied to
   *  that one, the card stayed up for good. */
  let heldOpen = false

  /** The thing the card standing right now belongs to. */
  let ownerEl: HTMLElement | null = null

  function place(el: HTMLElement) {
    ownerEl = el
    const r = el.getBoundingClientRect()
    // Above the thing where there is room for the card, below it otherwise —
    // the top row of a column has nothing above it but the window edge.
    above.value = r.top > 140
    x.value = r.left + r.width / 2
    y.value = above.value ? r.top - 8 : r.bottom + 8
  }

  const hold = useHold<{ el: HTMLElement; payload: T }>(({ el, payload }) => {
    // The thing can be gone before the press lands — a second finger removes it
    // while the first one holds it. A detached element measures as an
    // all-zero rect, which would stand the card in the corner of the window.
    if (!el.isConnected) return
    place(el)
    shown.value = payload
    heldOpen = true
  })

  function close() {
    clearTimeout(timer)
    clearTimeout(leaveTimer)
    hold.cancel()
    // And the flag a press left standing: the click that belongs to THAT press
    // has long gone. Kept, it was consumed by the next click from any other
    // device, which was then swallowed with nothing to show for it.
    hold.consumeHeld()
    shown.value = null
    heldOpen = false
    ownerEl = null
  }

  /**
   * A card that may be ENTERED does not shut the moment the pointer leaves the
   * thing: it waits, and the pointer arriving on the card cancels the wait.
   * Before anything is up there is nothing to walk to, so the wait is skipped —
   * otherwise a pointer crossing a row would leave a card standing behind it for
   * as long as the delay lasts. Lifted out of `components/PerspectivePicks.vue`
   * on 2026-09-23, when the discs of the flow board needed the same grace.
   */
  let leaveTimer: ReturnType<typeof setTimeout> | undefined
  const LEAVE_GRACE_MS = 160

  /** The pointer left the thing. */
  function leave() {
    clearTimeout(leaveTimer)
    if (!shown.value) {
      close()
      return
    }
    leaveTimer = setTimeout(close, LEAVE_GRACE_MS)
  }
  /** It arrived on the card instead. */
  function keep() {
    clearTimeout(leaveTimer)
  }
  /** And left the card. */
  function dismiss() {
    clearTimeout(leaveTimer)
    close()
  }

  /** A pointer came to rest here. */
  function enter(payload: T | undefined, event: Event) {
    if (payload === undefined || payload === null) return
    const el = event.currentTarget as HTMLElement | null
    if (!el) return
    // A finger reports itself as a pointer entering; that one is the long press
    // below, not a rest, and opening on it would make every tap flash a card.
    if (event instanceof PointerEvent && event.pointerType === 'touch') return
    // Back from the card on to the thing it belongs to: the grace is called off
    // and the card stays as it is.
    if (el === ownerEl && shown.value !== null) {
      clearTimeout(leaveTimer)
      return
    }
    // A DIFFERENT thing. The card of the one the pointer left goes now, and its
    // grace with it: left running, it fires 160 ms into this thing's waiting
    // time, takes that timer down with it, and no card comes at all. Two discs
    // side by side are crossed in less than that.
    clearTimeout(leaveTimer)
    if (shown.value !== null) close()
    clearTimeout(timer)
    timer = setTimeout(() => {
      if (!el.isConnected) return
      place(el)
      shown.value = payload
    }, HOVER_DELAY_MS)
  }

  /** A finger went down here. */
  function down(payload: T | undefined, event: PointerEvent) {
    if (payload === undefined || payload === null) return
    if (event.pointerType !== 'touch') return
    const el = event.currentTarget as HTMLElement | null
    if (!el) return
    hold.start({ el, payload })
  }

  /** It came up again. */
  function up() {
    clearTimeout(timer)
    hold.cancel()
    // The card stays up after the finger leaves — there is no pointer to rest,
    // so the next touch anywhere is what takes it away.
    if (!hold.held.value) shown.value = null
  }

  /**
   * Reads whether a long press opened the card and clears it. The click that
   * ends such a press belongs to the press — ask this first in whatever the
   * click otherwise does, and return early when it is true.
   */
  function consumePress(): boolean {
    return hold.consumeHeld()
  }

  if (typeof window !== 'undefined') {
    const away = () => { if (heldOpen) close() }
    window.addEventListener('touchstart', away, { passive: true })
    onBeforeUnmount(() => window.removeEventListener('touchstart', away))
  }

  onBeforeUnmount(() => {
    clearTimeout(timer)
    clearTimeout(leaveTimer)
  })

  return { shown, x, y, above, enter, down, up, leave, keep, dismiss, close, consumePress }
}
