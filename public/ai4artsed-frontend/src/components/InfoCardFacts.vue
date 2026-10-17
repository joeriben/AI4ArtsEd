<!--
  InfoCardFacts — what a model has to say inside an InfoCard: its name, one
  line of plain facts, one marked state, and the route it is reached by.

  The card is `InfoCard`, the gesture `useInfoCard`; this is the CONTENT, the
  same lines wherever a model is the thing beside which the card stands: the
  fields of `ChipSelect` (the image models, three lines: their list names no
  service, so there is no route) and the row heads of Interception across
  Models (the writing models, with the route). Until 2026-09-12 the three
  lines stood inline in ChipSelect, and a row head that wanted the same card
  would have had to copy them.

  The route line is the one that says where the text GOES: which service, and
  what the register records about that service's data path — the platform's
  own three-state mark (`DsgvoBadge`), never a verdict of this component's.

  Since 2026-09-27 it can also carry what the t2x page's hover card carried:
  quality and speed in five stars each and the estimated time of the
  generation (the Flow's
  model choice, `composables/useOutputCards.ts`).
-->
<template>
  <div class="chip-info-name">{{ info.name }}</div>
  <div v-if="info.line" class="chip-info-line">{{ info.line }}</div>
  <div v-if="info.mark" class="chip-info-mark">
    <span class="chip-info-dot" :class="`level-${info.mark.level}`"></span>
    <span :class="`level-${info.mark.level}`">{{ info.mark.text }}</span>
  </div>
  <div v-if="info.route" class="chip-info-route">
    <span>{{ t('modelInfo.via', { provider: info.route.via }) }}</span>
    <DsgvoBadge :recorded="info.route.recorded" />
  </div>
  <div v-if="info.stars?.quality" class="chip-info-stars">
    <span class="chip-info-key">{{ t('modelInfo.quality') }}</span>
    <span class="chip-info-on">{{ stars(info.stars.quality)[0] }}</span><span class="chip-info-off">{{ stars(info.stars.quality)[1] }}</span>
  </div>
  <div v-if="info.stars?.speed" class="chip-info-stars">
    <span class="chip-info-key">{{ t('modelInfo.speed') }}</span>
    <span class="chip-info-on">{{ stars(info.stars.speed)[0] }}</span><span class="chip-info-off">{{ stars(info.stars.speed)[1] }}</span>
  </div>
  <div v-if="info.seconds" class="chip-info-line">⏱ {{ t('modelInfo.seconds', { range: info.seconds }) }}</div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DsgvoBadge from '@/components/DsgvoBadge.vue'
import type { ChipInfo } from '@/components/ChipSelect.vue'

defineProps<{ info: ChipInfo }>()

const { t } = useI18n()

/** Filled and empty stars of five, the count held to 1..5. */
function stars(n: number): [string, string] {
  const k = Math.max(1, Math.min(5, Math.round(n)))
  return ['★'.repeat(k), '☆'.repeat(5 - k)]
}
</script>

<style scoped>
.chip-info-name {
  font-size: 0.8rem;
  line-height: 1.35;
  color: rgba(255, 255, 255, 0.95);
}

.chip-info-line {
  font-size: 0.74rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.6);
}

.chip-info-mark,
.chip-info-route {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  margin-top: 0.15rem;
  font-size: 0.74rem;
  line-height: 1.45;
}

.chip-info-route {
  color: rgba(255, 255, 255, 0.6);
}

/* The badge sets its own 12 px; on this card it takes the card's size. */
.chip-info-route :deep(span) {
  font-size: 0.74rem;
}

.chip-info-dot {
  flex: 0 0 auto;
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  transform: translateY(-0.05rem);
}

.chip-info-dot.level-full { background: rgb(76 175 80 / 0.9); }
.chip-info-dot.level-partial { background: rgb(255 179 0 / 0.85); }
.chip-info-dot.level-none { background: rgba(255, 255, 255, 0.28); }

span.level-full { color: rgba(160, 220, 160, 0.95); }
span.level-partial { color: rgba(255, 210, 120, 0.95); }
span.level-none { color: rgba(255, 255, 255, 0.5); }

.chip-info-stars {
  display: flex;
  align-items: baseline;
  font-size: 0.74rem;
  line-height: 1.45;
}

.chip-info-key {
  min-width: 3.2rem;
  color: rgba(255, 255, 255, 0.6);
}

.chip-info-on { color: rgba(255, 255, 255, 0.9); }
.chip-info-off { color: rgba(255, 255, 255, 0.3); }
</style>
