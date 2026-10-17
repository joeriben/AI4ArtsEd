<!--
  RingKind — a KIND on the bubble ring: the named circle that what hangs in it
  blooms around once it is open.

  It was `.lp-kind` in `components/LoraPickOverlay.vue` until 2026-10-02, when
  the Canvas's ready-made workflows were given the same ring
  (components/canvas/CanvasPresetOverlay.vue) and a second copy of the button
  would have been a parallel structure (Rule 13). The perspectives' own kinds
  are `PropertyBubble`, which carries a sign and a colour per category; a kind
  that has neither — a kind of adapter, a kind of workflow — is this.

  It carries nothing but its name. The host places it (left, top, width and
  height in percent of the ring's square, `bubbleStyle` in its own file) and
  sets its font size, which is measured off the bubble and not off the disc;
  `data-ring-bubble` marks it for `BubbleRingFrame`, so a click on it never
  closes the ring. A kind with nothing in it yet is `disabled` by its host and
  stands dimmed, without the answer to a pointer. See
  docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<template>
  <button class="ring-kind" :class="{ open }" type="button" data-ring-bubble>
    <span class="ring-kind-name"><slot /></span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  /** This kind is the one whose pieces stand around it. */
  open?: boolean
}>()
</script>

<style scoped>
/* A kind: the bubble of the ring, named. It carries no sign — the kinds of the
   perspectives have one each, and a sign invented for a kind of adapter or of
   workflow would say something the platform has not said. */
.ring-kind {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.2rem;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  background: rgb(var(--surface-1-rgb) / 0.9);
  color: rgba(255, 255, 255, 0.78);
  line-height: 1.15;
  overflow-wrap: anywhere;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.ring-kind:hover:not(:disabled) {
  border-color: rgba(167, 139, 250, 0.7);
  color: #fff;
}

.ring-kind:disabled {
  opacity: 0.45;
  cursor: default;
}

.ring-kind.open {
  border: 2px solid #a78bfa;
  color: #fff;
  box-shadow: 0 0 18px rgba(167, 139, 250, 0.35);
}

.ring-kind-name {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
</style>
