<template>
  <div dir="ltr" class="facts-bubble-container" v-if="visible && gpuStats.available">
    <!-- Rising bubble with mini-visualization -->
    <Transition name="bubble-rise" @after-leave="onBubbleLeft">
      <div
        v-if="showBubble"
        :key="bubbleKey"
        class="fact-bubble"
        :class="[`viz-${vizType}`]"
      >
        <div class="bubble-content">
          <div class="mini-viz">
            <!-- Energy Bar -->
            <template v-if="vizType === 'energy'">
              <span class="viz-emoji">W</span>
              <div class="viz-bar">
                <div
                  class="viz-bar-fill energy-fill"
                  :style="{ width: `${powerPercent}%` }"
                ></div>
              </div>
              <span class="viz-value">{{ Math.round(gpuStats.power_draw_watts || 0) }}W</span>
            </template>

            <!-- VRAM Bar -->
            <template v-else-if="vizType === 'vram'">
              <span class="viz-emoji">GB</span>
              <div class="viz-bar">
                <div
                  class="viz-bar-fill vram-fill"
                  :style="{ width: `${gpuStats.memory_used_percent || 0}%` }"
                ></div>
              </div>
              <span class="viz-value">{{ usedGb }}/{{ totalGb }}GB</span>
            </template>

            <!-- Temperature -->
            <template v-else-if="vizType === 'temperature'">
              <span class="viz-emoji">°C</span>
              <div class="viz-thermometer">
                <div
                  class="thermometer-fill"
                  :style="{ height: `${tempPercent}%` }"
                  :class="{ hot: (gpuStats.temperature_celsius || 0) > 70 }"
                ></div>
              </div>
              <span class="viz-value">{{ gpuStats.temperature_celsius || 0 }}°C</span>
            </template>

            <!-- CO2 Counter -->
            <template v-else-if="vizType === 'co2'">
              <span class="viz-emoji">CO₂</span>
              <span class="viz-counter">{{ totalCo2.toFixed(1) }}</span>
              <span class="viz-label">g CO₂</span>
            </template>

            <!-- Energy Counter -->
            <template v-else-if="vizType === 'kwh'">
              <span class="viz-emoji">kWh</span>
              <span class="viz-counter">{{ (totalEnergy / 1000).toFixed(3) }}</span>
              <span class="viz-label">kWh</span>
            </template>
          </div>
        </div>

        <!-- Bubble tail pointing down -->
        <div class="bubble-tail"></div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { GpuRealtimeStats } from '@/composables/useEdutainmentFacts'

const props = defineProps<{
  gpuStats: GpuRealtimeStats
  totalEnergy: number  // Wh
  totalCo2: number     // grams
  visible?: boolean
}>()

const visible = computed(() => props.visible !== false)

// Bubble state for animations
const showBubble = ref(false)
const bubbleKey = ref(0)

// Visualization rotation
const VIZ_TYPES = ['energy', 'vram', 'temperature', 'co2', 'kwh'] as const
type VizType = typeof VIZ_TYPES[number]
const vizIndex = ref(0)
const vizType = computed<VizType>(() => VIZ_TYPES[vizIndex.value % VIZ_TYPES.length] ?? 'energy')

// Computed values for display
const powerPercent = computed(() => {
  const draw = props.gpuStats.power_draw_watts || 0
  const limit = props.gpuStats.power_limit_watts || 600
  return Math.min(100, (draw / limit) * 100)
})

const usedGb = computed(() => Math.round((props.gpuStats.memory_used_mb || 0) / 1024))
const totalGb = computed(() => Math.round((props.gpuStats.memory_total_mb || 0) / 1024))

const tempPercent = computed(() => {
  const temp = props.gpuStats.temperature_celsius || 0
  return Math.min(100, Math.max(0, ((temp - 30) / 70) * 100))
})

// Rotation interval
let rotationInterval: number | null = null

function rotateViz() {
  showBubble.value = false
  bubbleKey.value++
  vizIndex.value++

  setTimeout(() => {
    showBubble.value = true
  }, 100)
}

function onBubbleLeft() {
  // Called when bubble leaves
}

onMounted(() => {
  if (props.gpuStats.available) {
    showBubble.value = true
  }

  // Rotate every 4 seconds
  rotationInterval = window.setInterval(() => {
    rotateViz()
  }, 4000)
})

// Cleanup
import { onUnmounted } from 'vue'
onUnmounted(() => {
  if (rotationInterval) {
    clearInterval(rotationInterval)
  }
})
</script>

<style scoped>
.facts-bubble-container {
  position: absolute;
  top: 0px;
  left: 50%;
  transform: translateX(-50%);
  width: 200px;
  height: 100px;
  pointer-events: none;
  z-index: 50;
  overflow: visible;
}

.fact-bubble {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 14px;
  background: rgba(15, 15, 30, 0.95);
  border: 1px solid rgba(100, 150, 255, 0.3);
  border-radius: 12px;
  box-shadow:
    0 4px 20px rgba(0, 0, 0, 0.5),
    0 0 20px rgba(100, 150, 255, 0.1);
  backdrop-filter: blur(8px);
}

/* Category-specific glow */
.fact-bubble.viz-energy {
  border-color: rgba(255, 200, 50, 0.4);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(255, 200, 50, 0.2);
}

.fact-bubble.viz-vram {
  border-color: rgba(100, 150, 255, 0.4);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(100, 150, 255, 0.2);
}

.fact-bubble.viz-temperature {
  border-color: rgba(255, 100, 50, 0.4);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(255, 100, 50, 0.2);
}

.fact-bubble.viz-co2 {
  border-color: rgba(100, 200, 100, 0.4);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(100, 200, 100, 0.2);
}

.fact-bubble.viz-kwh {
  border-color: rgba(50, 200, 150, 0.4);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(50, 200, 150, 0.2);
}

.bubble-content {
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble-tail {
  position: absolute;
  bottom: -7px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-top: 7px solid rgba(15, 15, 30, 0.95);
}

/* Mini Visualizations */
.mini-viz {
  display: flex;
  align-items: center;
  gap: 8px;
}

.viz-emoji {
  font-size: 18px;
}

.viz-bar {
  width: 80px;
  height: 10px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 5px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.viz-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease-out;
}

.energy-fill {
  background: linear-gradient(90deg, #4CAF50 0%, #FFC107 50%, #FF5722 100%);
  box-shadow: 0 0 8px rgba(255, 193, 7, 0.4);
}

.vram-fill {
  background: linear-gradient(90deg, #2196F3 0%, #9C27B0 100%);
  box-shadow: 0 0 8px rgba(33, 150, 243, 0.4);
}

.viz-thermometer {
  width: 14px;
  height: 35px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 7px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.15);
  position: relative;
}

.thermometer-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(180deg, #FFC107 0%, #4CAF50 100%);
  border-radius: 0 0 6px 6px;
  transition: height 0.5s ease-out;
}

.thermometer-fill.hot {
  background: linear-gradient(180deg, #FF5722 0%, #FFC107 100%);
  box-shadow: 0 0 8px rgba(255, 87, 34, 0.5);
}

.viz-value {
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: #aaa;
  min-width: 50px;
}

.viz-counter {
  font-family: 'Courier New', monospace;
  font-size: 16px;
  font-weight: bold;
  color: #0f0;
  text-shadow: 0 0 6px #0f0;
}

.viz-label {
  font-size: 10px;
  color: #888;
}

/* Bubble Rise Animation */
.bubble-rise-enter-active {
  animation: bubble-rise-in 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.bubble-rise-leave-active {
  animation: bubble-rise-out 1.2s ease-out forwards;
}

@keyframes bubble-rise-in {
  0% {
    opacity: 0;
    transform: translateX(-50%) translateY(20px) scale(0.8);
  }
  100% {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}

@keyframes bubble-rise-out {
  0% {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateX(-50%) translateY(-60px) scale(0.9);
  }
}
</style>
