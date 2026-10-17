<template>
  <!--
    THE remove mark of the platform: the small × in the corner of a tile or a
    card that takes THAT one entry away.

    It is not a handle. What lies under it usually moves — by pointer (the
    boards) or by the browser's own drag (the favourites strip) — and a press
    on the mark must start neither, or the entry travels instead of leaving.

    The mark places itself in the top right corner; the container around it
    carries `position: relative`.
  -->
  <button
    class="remove-badge"
    type="button"
    :title="title"
    :aria-label="title"
    @pointerdown.stop
    @dragstart.stop.prevent
    @click.stop="emit('remove')"
  >×</button>
</template>

<script setup lang="ts">
defineProps<{
  /** What letting go means here. Also the hover text — the mark has no label. */
  title?: string
}>()

const emit = defineEmits<{ remove: [] }>()
</script>

<style scoped>
/* The drawing is the one on Resona's memo card (`.memo-x`), unchanged, because
   it was the best formed of the hand-rolled ones. It stands INSIDE the corner:
   the containers that carry it clip whatever lies outside them. */
.remove-badge {
  position: absolute;
  top: 3px;
  right: 3px;
  z-index: 2;
  width: 20px;
  height: 20px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgb(var(--surface-2-rgb) / 0.85);
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.75rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-badge:hover {
  background: rgba(200, 80, 80, 0.55);
  color: #fff;
}
</style>
