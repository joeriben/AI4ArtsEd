<!--
  The one speaker control on the platform.

  Persona and Resona show the same four states in the same shape, because it is
  the same act: a voice is waiting, sounding, held back, or offered. Two copies
  of this drifted apart once already — Persona's speaker got a visible wait and
  Resona's circle did not, so the same silence meant two different things
  depending on where you stood.
-->
<template>
  <button
    class="speak-btn"
    :class="{ sounding, waiting, blocked }"
    :title="label"
    :aria-label="label"
    @click.stop="emit('press')"
  >
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4.03v8.05A4.5 4.5 0 0 0 16.5 12z" />
    </svg>
  </button>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  /** Audible right now. */
  sounding?: boolean
  /** Being synthesized. Fifteen to sixty seconds, and the first one loads the model. */
  waiting?: boolean
  /** Finished, but the browser wants a tap before it sounds. */
  blocked?: boolean
  label?: string
}>(), {
  sounding: false,
  waiting: false,
  blocked: false,
  label: '',
})

const emit = defineEmits<{ press: [] }>()
</script>

<style scoped>
.speak-btn {
  display: inline-flex;
  align-items: center;
  margin-left: 0.4rem;
  padding: 0;
  border: none;
  background: none;
  color: rgba(255, 255, 255, 0.22);
  cursor: pointer;
  vertical-align: -0.15em;
  transition: color 0.2s ease;
}

.speak-btn svg {
  width: 16px;
  height: 16px;
}

.speak-btn:hover { color: rgba(255, 255, 255, 0.9); }

.speak-btn.sounding { color: #ffb300; }

/* The wait is 15 to 60 seconds, and the first one after a server restart also
   loads the model. At 22% white on black nobody could see that anything was
   happening at all — one clicked and hoped. It pulses in the platform's amber
   now, with a size change, because opacity alone is not visible at this size. */
.speak-btn.waiting {
  color: #ffb300;
  animation: speak-waiting 1.1s ease-in-out infinite;
}

/* Ready and held back: a steady offer, not a pulse. The pulse means "wait",
   and this is the opposite — nothing is coming until it is tapped. */
.speak-btn.blocked {
  color: #ffb300;
  opacity: 1;
  transform: scale(1.12);
}

@keyframes speak-waiting {
  0%, 100% { opacity: 0.4; transform: scale(0.88); }
  50% { opacity: 1; transform: scale(1.16); }
}

@media (prefers-reduced-motion: reduce) {
  .speak-btn.waiting { animation: none; opacity: 0.85; }
}
</style>
