<template>
  <div dir="ltr" class="edutainment-animation-wrapper">
    <!-- Original Pixel Animation with GPU Stats -->
    <SpriteProgressAnimation
      :progress="internalProgress"
      :estimated-seconds="estimatedSeconds"
      :gpu-power="effectivePower"
      :gpu-temp="effectiveTemp"
      :total-energy="totalEnergy"
      :total-co2="totalCo2"
      :is-showing-summary="isShowingSummary"
      :smartphone-minutes="smartphoneMinutes"
    />

    <!-- Rising GPU Stats Bubble (optional visual effect) -->
    <AIFactsBubble
      :gpu-stats="gpuStats"
      :total-energy="totalEnergy"
      :total-co2="totalCo2"
      :visible="isGenerating"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SpriteProgressAnimation from '@/components/SpriteProgressAnimation.vue'
import AIFactsBubble from './AIFactsBubble.vue'
import { useAnimationProgress } from '@/composables/useAnimationProgress'

const props = defineProps<{
  progress: number
  estimatedSeconds?: number
}>()

// Use the unified animation progress composable
const {
  internalProgress,
  summaryShown,
  gpuStats,
  totalEnergy,
  totalCo2,
  effectivePower,
  effectiveTemp,
  smartphoneMinutes
} = useAnimationProgress({
  estimatedSeconds: computed(() => props.estimatedSeconds || 30),
  isActive: computed(() => props.progress > 0)
})

// Summary: shows after 5 seconds elapsed (when instructions fade), stays visible
const isShowingSummary = computed(() => summaryShown.value)
const isGenerating = computed(() => props.progress > 0 && !summaryShown.value)
</script>

<style scoped>
.edutainment-animation-wrapper {
  position: relative;
  width: 100%;
}
</style>
