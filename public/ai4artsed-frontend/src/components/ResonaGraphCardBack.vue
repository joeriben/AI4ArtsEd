<!--
  The back of an apparatus card: why Resona built it (motivation), what the
  pipeline does (summary), how many nodes, when it ran, and the canvas run id.

  It used to be a face of ResonaGraphCard, which turned itself over with its own
  rotateY and its own pair of buttons — the second such copy in the workshop.
  The turning is FlowCard's now (no parallel structures); what
  is left here is the content.
-->
<template>
  <div class="gb">
    <div class="gb-label">{{ t('resonaGraphCard.apparatus') }}</div>
    <p class="gb-motivation">{{ box.motivation || t('resonaGraphCard.motivationMissing') }}</p>

    <div class="gb-label">{{ t('resonaGraphCard.summaryLabel') }}</div>
    <p class="gb-summary">{{ box.summary }}</p>

    <div class="gb-meta">
      <span>{{ t('resonaGraphCard.nodeCount', { n: nodeCount }) }}</span>
      <span>{{ t('resonaGraphCard.startedAt') }}: {{ startedText }}</span>
      <span v-if="box.finishedAt">{{ t('resonaGraphCard.finishedAt') }}: {{ finishedText }}</span>
    </div>
    <div v-if="box.runId" class="gb-runid">{{ box.runId }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { GraphRunBox } from '@/views/resona_graph_types'

const props = defineProps<{
  box: GraphRunBox
}>()

const { t } = useI18n()

const nodeCount = computed(() => props.box.workflow?.nodes?.length ?? 0)

const startedText = computed(() =>
  new Date(props.box.startedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
)
const finishedText = computed(() =>
  props.box.finishedAt
    ? new Date(props.box.finishedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''
)
</script>

<style scoped>
.gb {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.7rem 0.9rem;
  color: rgba(230, 230, 230, 0.95);
}
.gb-label {
  margin-top: 0.5rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(230, 230, 230, 0.5);
}
.gb-label:first-child { margin-top: 0; }
.gb-motivation { margin: 0; font-size: 0.95rem; line-height: 1.55; }
.gb-summary {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: rgba(230, 230, 230, 0.85);
  white-space: pre-wrap;
  word-break: break-word;
}
.gb-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1rem;
  margin-top: 0.6rem;
  font-size: 0.75rem;
  color: rgba(230, 230, 230, 0.5);
}
.gb-runid {
  margin-top: 0.3rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.7rem;
  color: rgba(230, 230, 230, 0.4);
  word-break: break-all;
}
</style>
