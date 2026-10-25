<script setup lang="ts">
/**
 * SURFACE CONFIRM — the one decision a surface asks before it acts.
 *
 * It stands OVER the surface, never inside the gear: behind a closed fixture
 * it would be a question nobody is shown. One row, one sentence, the acting
 * button and the cancel. Lifted out of `views/resona.vue` on 2026-09-22 when
 * the flow canvas asked the same question before clearing itself.
 *
 * The same row says that something standing has ended, with the one way on:
 * when the sign-in of a device's place has ended
 * (components/PlaceSignInEnded.vue, 2026-09-24).
 */
defineProps<{
  text: string
  yes: string
  cancel: string
  /** The acting button in the warning red: for what drops a record. */
  danger?: boolean
  /** The acting button held back — the surface says why in its own comment. */
  disabled?: boolean
  /** Over the whole app rather than over the surface: for a row that App.vue
   *  shows, and for a page that is a layer of its own (the course page,
   *  `position: fixed`), where the footer gallery would cover the row.
   *  Carried to the end of the document at z-index 1500, the row stands over
   *  everything inside `#app` (the page and its own dialogs, the header, the
   *  footer gallery, Help) and over a layer carried there below 1500 (the
   *  canvas's configuration picker, 1000); the layers carried there from 2000
   *  up (the settings, the dialogs, the info cards, fullscreen media, the
   *  voice's question field, the model-install notice) stand over it. It
   *  stands over the footer, where a surface without the plus has room. */
  overApp?: boolean
}>()
defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <Teleport to="body" :disabled="!overApp">
    <!-- A file dropped on the row opens nothing, as on the surfaces that keep
         the browser from opening it (views/resona.vue, views/x2x_flow.vue):
         carried to `body`, the row is outside them. -->
    <div
      class="action-confirm-row"
      :class="{ 'over-app': overApp }"
      @dragover.prevent
      @drop.prevent
    >
      <span class="action-confirm-text">{{ text }}</span>
      <button class="action-confirm-btn" :class="{ danger }" :disabled="disabled" @click="$emit('confirm')">
        {{ yes }}
      </button>
      <button class="action-confirm-btn cancel" @click="$emit('cancel')">{{ cancel }}</button>
    </div>
  </Teleport>
</template>

<style scoped>
.action-confirm-row {
  position: fixed; left: 50%; transform: translateX(-50%);
  bottom: calc(var(--flow-footer-clear, 54px) + var(--flow-glyph-plus) + 1.6rem);
  z-index: 70; pointer-events: auto; max-width: min(34rem, 92vw);
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px;
  background: rgb(var(--surface-2-rgb) / 0.97);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.55);
}
.action-confirm-row.over-app {
  bottom: calc(var(--flow-footer-clear, 54px) + 1.6rem);
  z-index: 1500;
}
.action-confirm-text { flex: 1; color: rgba(230, 230, 230, 0.75); font-size: 0.85rem; line-height: 1.35; }
.action-confirm-btn {
  background: transparent; border: 1px solid rgba(255, 255, 255, 0.2);
  color: #e6e6e6; border-radius: 6px; padding: 0.3rem 0.7rem; cursor: pointer;
  font-size: 0.85rem; white-space: nowrap;
}
.action-confirm-btn:hover { border-color: rgba(255, 255, 255, 0.4); }
.action-confirm-btn.danger { color: #e06b6b; border-color: rgba(224, 107, 107, 0.4); }
.action-confirm-btn.danger:hover { border-color: #e06b6b; }
.action-confirm-btn.cancel { color: rgba(230, 230, 230, 0.5); border-color: transparent; }
</style>
