<!--
  FlowBubbles — the flow's model choice.

  x2x_flow drew this first: a long press on a medium glyph hangs a small column
  of names beside the create node, the resolved one lit.

  It was pulled out of that page so the re-enactment page could hang the same
  shape instead of a second copy of it. That page went its own way — with
  three machines and no fourth state, the names themselves stand in the node
  rather than behind a press — so x2x_flow is the only caller again. The split
  still holds for the next one: the LOOK lives here, the POSITION stays with
  the page, which measures its own stage and passes pixels.

  A name that carries `info` has the platform's card beside it when the pointer
  rests on it (`InfoCard` with `InfoCardFacts`); the others
  keep their `title`.
-->
<template>
  <div ref="root" class="bubbles-float" role="listbox" tabindex="-1">
    <button
      v-for="o in options"
      :key="o.id ?? '*'"
      class="bubble"
      :class="{ a: o.id === activeId, off: o.disabled }"
      role="option"
      :aria-selected="o.id === activeId"
      :aria-disabled="o.disabled || undefined"
      :disabled="o.disabled"
      :title="cardOf(o) ? undefined : o.title"
      @pointerenter="onEnter(o, $event)"
      @pointerleave="leave"
      @click="close(); $emit('pick', o.id)"
    >{{ o.label }}</button>
    <InfoCard :open="!!shown" :x="x" :y="y" :above="above">
      <InfoCardFacts v-if="shown" :info="shown" />
    </InfoCard>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import InfoCard from '@/components/InfoCard.vue'
import InfoCardFacts from '@/components/InfoCardFacts.vue'
import type { ChipInfo } from '@/components/ChipSelect.vue'
import { useInfoCard } from '@/composables/useInfoCard'

/** One choice. `id` is null for the choice that means "not chosen by hand". */
export interface FlowBubble {
  id: string | null
  label: string
  title?: string
  /** The model is not installed or its backend is down: shown, not choosable. */
  disabled?: boolean
  /** What the card beside the name says. A name that cannot be chosen keeps
      its `title`, which says why. */
  info?: ChipInfo
}

const props = defineProps<{
  options: FlowBubble[]
  /** The one that is in force — resolved or held; the page decides which. */
  activeId?: string | null
}>()

defineEmits<{ (e: 'pick', id: string | null): void }>()

// A pick closes the card at once: the list fades out for 180 ms, and a card
// left standing, or one whose wait runs out meanwhile, would hang over it.
const { shown, x, y, above, enter, leave, close } = useInfoCard<ChipInfo>()

function cardOf(o: FlowBubble): ChipInfo | undefined {
  return o.disabled ? undefined : o.info
}

// The name whose card stands. The page asks which models answer at the moment
// the list opens, so a name can turn unreachable under a resting pointer; its
// card goes then, as it cannot be chosen any more.
let cardFor: string | null = null
function onEnter(o: FlowBubble, e: PointerEvent) {
  cardFor = o.id
  enter(cardOf(o), e)
}
watch(
  () => props.options,
  (options) => {
    if (shown.value !== null && options.find((o) => o.id === cardFor)?.disabled) close()
  }
)

// Both callers hang this AFTER the whole band in the document, so Tab out of
// the line that opened it reached the button that starts the run — Enter there
// commits a generation nobody asked for. Taking the focus in is what makes the
// choice reachable at all by keyboard.
const root = ref<HTMLElement | null>(null)
onMounted(async () => {
  await nextTick()
  // A disabled button takes no focus, so the fallback skips it explicitly —
  // otherwise the keyboard lands nowhere and the list is unreachable.
  // Every model in this medium can be unreachable at once — then there is no
  // button to take the focus, and without the list itself taking it the
  // keyboard is left where the press came from, with a panel open over it.
  const el =
    root.value?.querySelector<HTMLElement>('.bubble.a:not(:disabled)') ??
    root.value?.querySelector<HTMLElement>('.bubble:not(:disabled)') ??
    root.value
  el?.focus({ preventScroll: true })
})
</script>

<style scoped>
.bubbles-float {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--surface-3);
  border-radius: 10px;
  background: var(--bg-base);
}
/* Not hidden: which models this platform has is part of what it says about
   itself. Struck through, because it is there and cannot be reached. */
.bubble.off {
  opacity: 0.4;
  text-decoration: line-through;
  cursor: default;
}
.bubble {
  padding: 8px 12px;
  border: 1px solid var(--surface-3);
  border-radius: 8px;
  /* A button does not inherit the page's font. */
  font: inherit;
  font-size: var(--flow-fs-hint);
  color: #aaa;
  cursor: pointer;
  background: transparent;
  text-align: start;
  white-space: nowrap;
}
.bubble:hover { border-color: #4a4a4a; }
.bubble:focus-visible { outline: 1px solid #7fb2ff; outline-offset: 1px; }
.bubble.a { border-color: #3a4a7a; background: #141d33; color: #cfe0ff; }
</style>
