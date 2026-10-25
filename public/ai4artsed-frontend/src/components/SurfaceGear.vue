<script setup lang="ts">
/**
 * SURFACE GEAR — what a talking surface is set to, out of the way.
 *
 * WHAT THIS IS
 *   A free fixture lying on the surface, drawn at the platform's fixture step
 *   (the same one the plus is drawn at, `assets/flow-stage.css`) but in a
 *   withheld grey: it is not an invitation, it is where the settings of this
 *   surface wait until somebody looks for them. What it carries is slotted —
 *   the recording of the workshop journal, ending a dialogue, whatever the
 *   surface keeps out of the exchange itself.
 *
 * WHY IT EXISTS
 *   These settings used to stand in a bar at the foot of the surface, in the
 *   reading path of every exchange. The exchange is what the surface is for;
 *   its settings are not, and they are read once a session.
 *
 * IT MOVES
 *   Like every sign of its kind on this platform, it is put where the hand
 *   wants it — the shared gesture of `composables/usePointDrag.ts`, the same
 *   one the flow canvas's fixtures answer to. Until it is first moved it keeps
 *   the resting place its surface gave it in CSS; from the first drag on it
 *   carries its own place, seeded from where it was standing, so nothing jumps.
 */
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { usePointDrag } from '@/composables/usePointDrag'

defineProps<{ title: string }>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)

// Where the hand has put it. Empty until the first drag — see IntakePlus.
const at = reactive({ x: 0, y: 0 })
const placed = ref(false)
const { startPointDrag, dragMoved } = usePointDrag()

function grab(e: PointerEvent) {
  if (!placed.value) {
    const r = rootEl.value?.getBoundingClientRect()
    if (!r) return
    at.x = Math.round(r.left)
    at.y = Math.round(r.top)
    placed.value = true
  }
  startPointDrag(e, at)
}

function toggle() {
  // A click that ended a drag is not a click.
  if (dragMoved()) return
  if (!open.value) below.value = (rootEl.value?.getBoundingClientRect().top ?? 0) < window.innerHeight * 0.4
  open.value = !open.value
}

// What it holds opens above it, because it rests low. Carried up the surface it
// opens downward instead, or the panel would stand off the top edge.
const below = ref(false)

const D_GEAR =
  'm370-80-16-128q-13-5-24.5-12T307-235l-119 50L78-375l103-78q-1-7-1-13.5v-27q0-6.5 1-13.5L78-585l110-190 119 50q11-8 23-15t24-12l16-128h220l16 128q13 5 24.5 12t22.5 15l119-50 110 190-103 78q1 7 1 13.5v27q0 6.5-2 13.5l103 78-110 190-118-50q-11 8-23 15t-24 12L590-80H370Zm70-80h79l14-106q31-8 57.5-23.5T639-327l99 41 39-68-86-65q5-14 7-29.5t2-31.5q0-16-2-31.5t-7-29.5l86-65-39-68-99 42q-22-23-48.5-38.5T533-694l-13-106h-79l-14 106q-31 8-57.5 23.5T321-633l-99-41-39 68 86 64q-5 15-7 30t-2 32q0 16 2 31t7 30l-86 65 39 68 99-42q22 23 48.5 38.5T427-266l13 106Zm42-180q58 0 99-41t41-99q0-58-41-99t-99-41q-59 0-99.5 41T342-480q0 58 40.5 99t99.5 41Zm-2-140Z'

function onDocPointerDown(e: PointerEvent) {
  if (!open.value) return
  const root = rootEl.value
  if (root && e.target instanceof Node && root.contains(e.target)) return
  open.value = false
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) open.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, true)
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocPointerDown, true)
  document.removeEventListener('keydown', onKeydown)
})

defineExpose({ close: () => { open.value = false } })
</script>

<template>
  <div
    ref="rootEl"
    class="sg"
    :class="{ placed }"
    :style="placed ? { left: at.x + 'px', top: at.y + 'px' } : undefined"
  >
    <!-- What it holds opens ABOVE it, because the fixture rests low on the
         surface — and below it where a hand has carried it up. -->
    <div v-if="open" class="sg-panel" :class="{ below }">
      <slot />
    </div>

    <button
      type="button"
      class="sg-mark"
      :class="{ open }"
      :title="title"
      :aria-label="title"
      :aria-expanded="open"
      @pointerdown.stop.prevent="grab"
      @click="toggle"
    >
      <svg viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true">
        <path :d="D_GEAR" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.sg { position: relative; display: block; width: var(--flow-glyph-fixture); height: var(--flow-glyph-fixture); }
/* Once a hand has moved it, the sign holds its own place on the view. */
.sg.placed { position: fixed; right: auto; bottom: auto; z-index: 62; }

/* Withheld: it holds its place without asking to be used. No breath — the
   plus invites, this one waits. */
.sg-mark {
  display: flex; padding: 0; border: none; background: transparent;
  color: rgba(255, 255, 255, 0.22); cursor: pointer;
  transition: color 0.2s ease;
}
.sg-mark svg { width: var(--flow-glyph-fixture); height: var(--flow-glyph-fixture); transition: transform 0.4s ease; }
.sg-mark:hover, .sg-mark.open { color: rgba(255, 255, 255, 0.55); }
.sg-mark.open svg { transform: rotate(60deg); }

/* One action the panel holds, as the surfaces write it: `<button class="gear-action">`.
   Styled here so that a third surface does not copy it a third time. */
.sg-panel :slotted(.gear-action) {
  padding: 0.4rem 0.7rem; background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px;
  color: rgba(230, 230, 230, 0.7); font-size: 0.8rem; text-align: left;
  cursor: pointer;
}
.sg-panel :slotted(.gear-action:hover) { color: #e6e6e6; border-color: rgba(255, 255, 255, 0.3); }

.sg-panel.below { top: calc(100% + 10px); bottom: auto; }
.sg-panel {
  position: absolute; right: 0; bottom: calc(100% + 10px);
  z-index: 30; min-width: 15rem; max-width: 22rem;
  display: flex; flex-direction: column; gap: 0.55rem;
  padding: 0.8rem 0.9rem;
  background: rgb(var(--surface-2-rgb) / 0.97);
  border: 1px solid var(--surface-3);
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.55);
}

@media (prefers-reduced-motion: reduce) {
  .sg-mark svg { transition: none; }
  .sg-mark.open svg { transform: none; }
}
</style>
