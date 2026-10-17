<!--
  InfoCard — the little card that stands beside a thing and says what it is.

  It is drawn on the body, so it is placed by fixed coordinates instead of by an
  ancestor: the columns it appears over scroll, and a card inside one would be
  cut off at the column edge. It takes no pointer events — it must not be a
  thing the pointer can enter, or leaving the thing for the card would count as
  leaving both.

  `interactive` lifts exactly that, for a card whose text is longer than the
  card: an interception prompt runs to 3750 characters, and a card that cannot
  be entered cannot be scrolled, so its end would be cut off in silence. Such a
  card says when the pointer comes and goes (`enter`/`leave`) and the CALLER
  decides what that means — the resting half is the caller's either way. Left
  out, the card is what it was.

  The gesture that opens it is `composables/useInfoCard.ts`; WHAT it says comes
  through the slot and belongs to the caller. Built inside
  `components/ChipSelect.vue` on 2026-09-04 and lifted out on 2026-09-05, when
  the wall of Perspectives on a Template needed the same card on a disc.
-->
<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="info-card"
      :class="{ below: !above, interactive }"
      role="tooltip"
      :style="{ left: `${x}px`, top: `${y}px` }"
      @pointerenter="emit('enter')"
      @pointerleave="emit('leave')"
    >
      <slot />
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** Whether it stands at all. */
    open: boolean
    /** Where the thing it belongs to is, in window coordinates. */
    x: number
    y: number
    /** Hanging from above the thing, or standing under it. */
    above: boolean
    /** How wide it may grow. A card of facts is narrow; one of prose is not. */
    width?: number
    /** The pointer may enter it, so what is longer than the card can be read. */
    interactive?: boolean
  }>(),
  { width: 220, interactive: false }
)

/**
 * The room the card has in the direction it hangs. A card of prose is several
 * hundred pixels tall; above a thing near the top of the window it used to run
 * off the top edge, and the first lines were the ones that went.
 */
const roomStyle = computed(() =>
  props.above ? `${Math.max(140, props.y - 12)}px` : `calc(100vh - ${props.y}px - 12px)`
)

const emit = defineEmits<{
  /** The pointer came onto the card itself. Only ever from an interactive one. */
  enter: []
  /** And left it again. */
  leave: []
}>()
</script>

<style scoped>
.info-card {
  position: fixed;
  z-index: 3000;
  transform: translate(-50%, -100%);
  width: max-content;
  max-width: v-bind('`${width}px`');
  text-align: left;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 10px;
  padding: 0.5rem 0.6rem;
  box-shadow: 0 6px 22px rgba(0, 0, 0, 0.55);
  pointer-events: none;
  /* A card of prose is several hundred pixels tall, and one hung ABOVE a thing
     near the top of the window used to run off the top edge with its first
     lines. It may grow to the room it has and no further. */
  max-height: v-bind(roomStyle);
}

/* Below the thing where there is nothing above it to hang from. */
.info-card.below {
  transform: translate(-50%, 0);
}

.info-card.interactive {
  pointer-events: auto;
  /* Only an entered card can be rolled, so only there does the cap gain a way
     to the rest instead of cutting it off silently. */
  overflow-y: auto;
  overscroll-behavior: contain;
}
</style>
