<!--
  The front of an anchor: what a room worked out, small enough to stand beside
  the things it made without competing with them.

  It exists because the produced media were the only entities on the board,
  and a strategy the group kept, a note Resona wrote and a passage she opened
  left no trace at all. A name on the front, an excerpt on the back
  (ResonaEntityCardBack); the turning, the bar and the corner are FlowCard's.
-->
<template>
  <div class="ec">
    <div class="ec-kind">{{ kindLabel }}</div>
    <div class="ec-name">{{ name }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  kind: string
  name: string
}>()

const { t } = useI18n()

const KINDS = ['apparatus', 'note', 'document', 'page']

const kindLabel = computed(() =>
  KINDS.includes(props.kind) ? t(`resonaEntityCard.${props.kind}`) : props.kind
)
</script>

<style scoped>
.ec {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.6rem 0.7rem;
  height: 100%;
  box-sizing: border-box;
  color: rgba(230, 230, 230, 0.95);
}
.ec-kind {
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(230, 230, 230, 0.45);
}
.ec-name {
  font-size: 0.85rem;
  font-weight: 300;
  line-height: 1.35;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 6;
  line-clamp: 6;
}
</style>
