<!--
  PerspectiveInfo — what a perspective SAYS, inside an InfoCard: its name and
  the prompt it hands the writing model.

  The card is `InfoCard`, the gesture `useInfoCard`; this is the CONTENT, the
  same two lines wherever a perspective is the thing the card stands beside —
  the strip of picks (`components/PerspectivePicks.vue`). The discs on the
  flow board (`views/x2x_flow.vue`) carried it from 2026-09-23 to 2026-09-26;
  there a disc has one box now, and its click opens it. It sits
  beside `InfoCardFacts`, which carries the other kind of content: a model's
  name and one line of plain facts.

  The body is capped and scrolls: half of the given perspectives are over 1200 characters
  long.
-->
<template>
  <div class="pi-name">{{ name }}</div>
  <p v-if="text" class="pi-text">{{ text }}</p>
</template>

<script setup lang="ts">
defineProps<{ name: string; text?: string }>()
</script>

<style scoped>
.pi-name {
  font-size: var(--flow-fs-label);
  line-height: 1.35;
  color: rgba(255, 255, 255, 0.95);
  margin-bottom: 0.3rem;
}

.pi-text {
  margin: 0;
  max-height: 260px;
  overflow-y: auto;
  overscroll-behavior: contain;
  white-space: pre-wrap;
  font-size: var(--flow-fs-body);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.72);
}
</style>
