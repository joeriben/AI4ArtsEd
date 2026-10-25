<!--
  BubbleRingFrame — THE layer a choice on the bubble ring is made on: a dark
  ground over the page and a DISC on it, with the square the bubbles stand in
  inside. The frame follows what stands in it, so it is a disc and not a
  window: it holds the same field in the short side of the screen and gives
  back the dead ground a full-width rectangle kept on the left and the right.
  There is no header — the ring says what it is, and a click into the open
  ground closes it.

  It was the private shell of `components/InterceptionPresetOverlay.vue` until
  the LoRAs were given the same circle and a second copy would have been a
  parallel structure (docs/ELEMENT_STRUCTURE_REGISTRY.md).

  Two sizes. Without `diameter` the disc is as large as the window allows and
  the square is the 0.84 of it the perspectives have always used. With
  `diameter` and `square` (both px, from `fitRing` in
  `composables/useBubbleRing.ts`) the disc is as wide as what stands in it —
  few kinds and few pieces make a small circle, as flexible in extent as
  possible.

  What closes it: the ground, Escape, and anything inside the disc that is not
  a bubble. A BUBBLE IS MARKED `data-ring-bubble` by whoever puts it in the
  slot — the frame knows no class names of its hosts. The press is remembered,
  because a bubble dragged and released over open ground raises its click on
  the common ancestor, which is the ground; without that the chooser would shut
  every time somebody moved a bubble.
  See docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="visible"
        class="ring-ground"
        @pointerdown="onGroundPointerDown"
        @click="onGroundClick"
      >
        <div class="ring-disc" :class="{ fitted: !!diameter }" :style="discStyle">
          <div class="ring-canvas">
            <div class="ring-field" :style="fieldStyle">
              <slot />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  visible: boolean
  /** The disc in px. Left out, it is as large as the window allows. */
  diameter?: number | null
  /** The square the bubbles stand in, in px. Goes with `diameter`. */
  square?: number | null
}>()

const emit = defineEmits<{ close: [] }>()

const discStyle = computed(() =>
  props.diameter ? { width: `${props.diameter}px`, height: `${props.diameter}px` } : undefined
)
const fieldStyle = computed(() =>
  props.square ? { '--square-size': `${props.square}px` } : undefined
)

/** Where the press began (see the comment at the top). */
let pressedOnGround = false

function isBubble(target: EventTarget | null): boolean {
  return !!(target as HTMLElement | null)?.closest?.('[data-ring-bubble]')
}

function onGroundPointerDown(e: PointerEvent): void {
  pressedOnGround = !isBubble(e.target)
}

function onGroundClick(e: MouseEvent): void {
  if (isBubble(e.target)) return
  if (!pressedOnGround) return
  emit('close')
}

function onEscape(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.visible) emit('close')
}

onMounted(() => window.addEventListener('keydown', onEscape))
onBeforeUnmount(() => window.removeEventListener('keydown', onEscape))
</script>

<style scoped>
.ring-ground {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.ring-disc {
  width: min(calc(100vw - 2rem), calc(100vh - 2rem));
  aspect-ratio: 1;
  background: var(--bg-base);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.ring-canvas {
  width: 100%;
  height: 100%;
  padding: 1rem;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* A fitted disc is exactly as wide as its field: the rim is already in the
   field's own reckoning, and a padding on top of it would cut the field. */
.ring-disc.fitted .ring-canvas {
  padding: 0;
}

.ring-field {
  position: relative;
  /* Explicit square: both dimensions the SAME value. Measured off the disc
     rather than off the viewport, so the field scales with its frame. */
  --square-size: calc(min(100vw - 2rem, 100vh - 2rem) * 0.84);
  width: var(--square-size);
  height: var(--square-size);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
