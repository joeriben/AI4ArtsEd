<template>
  <div dir="ltr" class="random-edutainment">
    <!-- Pixel Animation (GPU Stats + Smartphone) -->
    <EdutainmentProgressAnimation
      v-if="selectedAnimation === 'pixel'"
      :progress="progress"
      :estimated-seconds="estimatedSeconds"
    />

    <!-- Iceberg Animation (Arctic Ice Melt) -->
    <IcebergAnimation
      v-else-if="selectedAnimation === 'iceberg'"
      :progress="progress"
      :estimated-seconds="estimatedSeconds"
    />

    <!-- Forest Mini-Game (Tree Planting) -->
    <ForestMiniGame
      v-else-if="selectedAnimation === 'forest'"
      :progress="progress"
      :estimated-seconds="estimatedSeconds"
    />

    <!-- Rare Earth Mini-Game (Environmental Mining) - DISABLED -->
    <!--
    <RareEarthMiniGame
      v-else-if="selectedAnimation === 'rareearth'"
      :progress="progress"
      :estimated-seconds="estimatedSeconds"
    />
    -->
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import EdutainmentProgressAnimation from './EdutainmentProgressAnimation.vue'
import IcebergAnimation from './IcebergAnimation.vue'
import ForestMiniGame from './ForestMiniGame.vue'
// import RareEarthMiniGame from './RareEarthMiniGame.vue' // DISABLED

defineProps<{
  progress: number
  estimatedSeconds?: number
}>()

// Available animations (rareearth DISABLED)
const ANIMATIONS = ['pixel', 'iceberg', 'forest'] as const
type AnimationType = typeof ANIMATIONS[number]

// Randomly select on mount (stays same for entire generation)
const selectedAnimation = ref<AnimationType>('pixel')

onMounted(() => {
  const randomIndex = Math.floor(Math.random() * ANIMATIONS.length)
  selectedAnimation.value = ANIMATIONS[randomIndex]!
  console.log('[RandomEdutainment] Selected:', selectedAnimation.value)
})
</script>

<style scoped>
.random-edutainment {
  width: 100%;
  height: 100%;
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
