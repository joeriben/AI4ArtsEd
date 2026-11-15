<script setup lang="ts">
/**
 * The name of a language model under the axis of a chart: one `<text>`, one
 * `<tspan>` per line (`lib/modelAxisLabel.ts` cuts them and sets the step),
 * styled by `.lab-model-name` in assets/flow-stage.css. It stands inside the
 * chart's `<svg>`; whatever the chart sets under it moves down by
 * `modelLabelDrop`.
 */
import { computed } from 'vue'
import { modelLabelLine, modelLabelLines } from '@/lib/modelAxisLabel'

const props = defineProps<{ x: number; y: number; label: string }>()

const lines = computed(() => modelLabelLines(props.label))
const step = computed(() => (lines.value.length > 1 ? modelLabelLine() : 0))
</script>

<template>
  <text :x="x" :y="y" class="lab-model-name" text-anchor="middle">
    <tspan v-for="(line, i) in lines" :key="i" :x="x" :dy="i === 0 ? 0 : step">{{ line }}</tspan>
  </text>
</template>
