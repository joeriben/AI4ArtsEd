import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue'

/**
 * Who owns the middle of the shell bar right now.
 *
 * The bar has ONE place for a run, and more than one surface can be alive at
 * the same time: the Comparison hub holds its pages in `KeepAlive`, and so does
 * the Crossmodal Lab's dispatch since 2026-09-05, so a surface that has been
 * left is still there, with its state, its stream and its counter, and a route
 * change anywhere keeps the departing surface mounted for the moment the
 * arriving one takes to appear. Without a central claim a
 * trigger and a count would keep standing in the bar of whatever the visitor
 * opened next — a readout that belongs to a run nobody is looking at.
 *
 * A STACK rather than a single owner, because the order of the two lifecycle
 * calls is not fixed: switching instruments may activate the new one before it
 * deactivates the old, and a single owner would then be cleared by the departing
 * surface just after the arriving one claimed it. Whoever claimed LAST is on
 * top, and letting go removes a claim wherever it sits.
 */
const claims = ref<number[]>([])
let nextId = 0

export function useShellRunSlot() {
  const id = nextId++

  const claim = () => {
    if (!claims.value.includes(id)) claims.value = [...claims.value, id]
  }
  const release = () => {
    claims.value = claims.value.filter((other) => other !== id)
  }

  onMounted(claim)
  onActivated(claim)
  onDeactivated(release)
  onUnmounted(release)

  return computed(() => claims.value[claims.value.length - 1] === id)
}
