<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** Start X position */
  x1: number
  /** Start Y position */
  y1: number
  /** End X position */
  x2: number
  /** End Y position */
  y2: number
  /** Whether this is a temporary connection being drawn */
  temporary?: boolean
  /** Whether this connection is selected/highlighted */
  selected?: boolean
  /** Cable color (defaults to blue #3b82f6) */
  color?: string
}>()

const emit = defineEmits<{
  'click': []
}>()

/** CSS custom property for cable color */
const styleVars = computed(() => ({
  '--conn-color': props.color || '#3b82f6',
  '--conn-color-hover': props.color ? props.color : '#60a5fa'
}))

/**
 * Generate a smooth Bezier curve path between two points
 * Handles both left-to-right (forward) and right-to-left (backward) cables
 */
const pathD = computed(() => {
  const { x1, y1, x2, y2 } = props

  const dx = Math.abs(x2 - x1)
  const controlOffset = Math.min(dx * 0.5, 100)

  if (x2 >= x1) {
    // Forward cable: left-to-right S-curve
    const cx1 = x1 + controlOffset
    const cx2 = x2 - controlOffset
    return `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`
  } else {
    // Backward cable: right-to-left — flip control point direction
    const cx1 = x1 - controlOffset
    const cx2 = x2 + controlOffset
    return `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`
  }
})

/** Arrow indicator X position — accounts for cable direction */
const arrowCx = computed(() => {
  return props.x2 >= props.x1 ? props.x2 - 8 : props.x2 + 8
})
</script>

<template>
  <g class="connection-line" :class="{ temporary, selected }" :style="styleVars">
    <!-- Invisible wider path for easier clicking -->
    <path
      v-if="!temporary"
      :d="pathD"
      class="connection-hitarea"
      @click.stop="emit('click')"
    />
    <!-- Visible connection path -->
    <path
      :d="pathD"
      class="connection-path"
      vector-effect="non-scaling-stroke"
      @click.stop="emit('click')"
    />
    <!-- Arrow indicator at the end -->
    <circle
      v-if="!temporary"
      :cx="arrowCx"
      :cy="y2"
      r="3"
      class="connection-arrow"
    />
  </g>
</template>

<style scoped>
.connection-line {
  pointer-events: none;
}

.connection-hitarea {
  fill: none;
  stroke: transparent;
  stroke-width: 20;
  pointer-events: stroke;
  cursor: pointer;
}

.connection-path {
  fill: none;
  stroke: var(--conn-color, #3b82f6);
  stroke-width: 2;
  pointer-events: stroke;
  cursor: pointer;
  transition: stroke 0.15s, stroke-width 0.15s;
}

.connection-line:hover .connection-path,
.connection-line.selected .connection-path {
  stroke: var(--conn-color-hover, #60a5fa);
  stroke-width: 3;
}

.connection-line.temporary .connection-path {
  stroke: var(--conn-color, #3b82f6);
  stroke-dasharray: 5 5;
  opacity: 0.6;
  pointer-events: none;
}

.connection-arrow {
  fill: var(--conn-color, #3b82f6);
  pointer-events: none;
  transition: fill 0.15s;
}

.connection-line:hover .connection-arrow,
.connection-line.selected .connection-arrow {
  fill: var(--conn-color-hover, #60a5fa);
}

.connection-line.temporary .connection-arrow {
  display: none;
}
</style>
