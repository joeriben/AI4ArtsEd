<template>
  <div dir="ltr" class="environment-animation">
    <!-- Sky gradient changes with energy use -->
    <div class="sky" :style="skyStyle">
      <!-- Sun grows with power consumption -->
      <div class="sun" :style="sunStyle">
        <div class="sun-rays"></div>
      </div>

      <!-- Clouds appear and darken with CO2 -->
      <div class="clouds-container">
        <div
          v-for="(cloud, i) in clouds"
          :key="i"
          class="cloud"
          :style="cloud.style"
        ></div>
      </div>
    </div>

    <!-- Landscape -->
    <div class="landscape">
      <!-- Hills -->
      <div class="hills">
        <div class="hill hill-back"></div>
        <div class="hill hill-mid"></div>
        <div class="hill hill-front"></div>
      </div>

      <!-- Power plant / Factory (source of emissions) -->
      <div class="factory">
        <div class="factory-building"></div>
        <div class="chimney">
          <div class="smoke-container">
            <div
              v-for="n in smokeParticles"
              :key="n"
              class="smoke"
              :style="getSmokeStyle(n)"
            ></div>
          </div>
        </div>
      </div>

      <!-- Fire/heat indicator -->
      <div class="heat-zone" :class="{ active: temperature > 50 }">
        <div class="heat-waves">
          <div class="heat-wave" v-for="n in 3" :key="n"></div>
        </div>
        <div class="fire" v-if="temperature > 60">
          <div class="flame flame-1"></div>
          <div class="flame flame-2"></div>
          <div class="flame flame-3"></div>
        </div>
      </div>
    </div>

    <!-- Stats overlay -->
    <div class="stats-overlay">
      <div class="stat">
        <span class="stat-icon">W</span>
        <span class="stat-value">{{ Math.round(powerWatts) }}W</span>
      </div>
      <div class="stat">
        <span class="stat-icon">CO₂</span>
        <span class="stat-value">{{ co2Grams.toFixed(1) }}g</span>
      </div>
      <div class="stat">
        <span class="stat-icon">°C</span>
        <span class="stat-value">{{ temperature }}°C</span>
      </div>
    </div>

    <!-- Progress bar -->
    <div class="progress-container">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${progress}%` }"></div>
      </div>
      <div class="progress-text">{{ Math.round(progress) }}%</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  progress: number
  powerWatts: number
  temperature: number
  co2Grams: number
  powerLimit?: number
}>()

const powerLimit = computed(() => props.powerLimit || 600)

// Sun size based on power consumption (30-80px)
const sunSize = computed(() => {
  const ratio = Math.min(1, props.powerWatts / powerLimit.value)
  return 30 + ratio * 50
})

const sunStyle = computed(() => ({
  width: `${sunSize.value}px`,
  height: `${sunSize.value}px`,
  boxShadow: `0 0 ${sunSize.value}px ${sunSize.value / 2}px rgba(255, 200, 50, ${0.3 + (props.powerWatts / powerLimit.value) * 0.4})`
}))

// Sky color darkens with CO2
const skyStyle = computed(() => {
  const co2Ratio = Math.min(1, props.co2Grams / 10) // Darken as CO2 increases
  const r = Math.round(135 - co2Ratio * 50)
  const g = Math.round(206 - co2Ratio * 80)
  const b = Math.round(235 - co2Ratio * 60)
  return {
    background: `linear-gradient(180deg, rgb(${r}, ${g}, ${b}) 0%, rgb(${r + 30}, ${g + 20}, ${b - 30}) 100%)`
  }
})

// Cloud generation based on CO2
const clouds = computed(() => {
  const count = Math.min(8, Math.floor(props.co2Grams / 0.5) + 1)
  const darkness = Math.min(0.8, props.co2Grams / 15)

  return Array.from({ length: count }, (_, i) => ({
    style: {
      left: `${10 + (i * 12) % 80}%`,
      top: `${10 + (i * 7) % 30}%`,
      opacity: 0.5 + darkness * 0.5,
      transform: `scale(${0.6 + (i % 3) * 0.3})`,
      backgroundColor: `rgba(${100 - darkness * 50}, ${100 - darkness * 50}, ${100 - darkness * 50}, ${0.7 + darkness * 0.3})`,
      animationDelay: `${i * 0.5}s`
    }
  }))
})

// Smoke particles based on power
const smokeParticles = computed(() => Math.min(6, Math.floor(props.powerWatts / 100) + 1))

function getSmokeStyle(n: number) {
  const delay = n * 0.3
  const opacity = Math.min(0.8, props.powerWatts / 400)
  return {
    animationDelay: `${delay}s`,
    opacity
  }
}

const temperature = computed(() => props.temperature || 0)
</script>

<style scoped>
.environment-animation {
  width: 100%;
  height: 320px;
  position: relative;
  overflow: hidden;
  border-radius: 12px;
}

/* Sky */
.sky {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 60%;
  transition: background 1s ease;
}

/* Sun */
.sun {
  position: absolute;
  top: 20px;
  right: 40px;
  border-radius: 50%;
  background: radial-gradient(circle, #fff7e0 0%, #ffd93d 50%, #ff9500 100%);
  transition: all 0.5s ease;
}

.sun-rays {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 150%;
  height: 150%;
  background: radial-gradient(circle, rgba(255, 200, 50, 0.3) 0%, transparent 70%);
  animation: pulse-rays 2s ease-in-out infinite;
}

@keyframes pulse-rays {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.5; }
  50% { transform: translate(-50%, -50%) scale(1.2); opacity: 0.8; }
}

/* Clouds */
.clouds-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.cloud {
  position: absolute;
  width: 60px;
  height: 25px;
  border-radius: 20px;
  transition: all 0.5s ease;
  animation: float-cloud 8s ease-in-out infinite;
}

.cloud::before,
.cloud::after {
  content: '';
  position: absolute;
  background: inherit;
  border-radius: 50%;
}

.cloud::before {
  width: 25px;
  height: 25px;
  top: -12px;
  left: 10px;
}

.cloud::after {
  width: 35px;
  height: 35px;
  top: -18px;
  left: 25px;
}

@keyframes float-cloud {
  0%, 100% { transform: translateX(0) scale(1); }
  50% { transform: translateX(10px) scale(1.05); }
}

/* Landscape */
.landscape {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 50%;
}

.hills {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 100%;
}

.hill {
  position: absolute;
  bottom: 0;
  border-radius: 50% 50% 0 0;
}

.hill-back {
  left: -10%;
  width: 60%;
  height: 70%;
  background: #3d5a3d;
}

.hill-mid {
  right: -5%;
  width: 50%;
  height: 80%;
  background: #4a6b4a;
}

.hill-front {
  left: 20%;
  width: 80%;
  height: 60%;
  background: #5a7d5a;
}

/* Factory */
.factory {
  position: absolute;
  bottom: 30%;
  left: 15%;
}

.factory-building {
  width: 50px;
  height: 40px;
  background: #444;
  border-radius: 2px 2px 0 0;
}

.chimney {
  position: absolute;
  bottom: 35px;
  left: 15px;
  width: 20px;
  height: 50px;
  background: #555;
}

.smoke-container {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
}

.smoke {
  position: absolute;
  width: 20px;
  height: 20px;
  background: rgba(100, 100, 100, 0.6);
  border-radius: 50%;
  animation: rise-smoke 3s ease-out infinite;
}

@keyframes rise-smoke {
  0% {
    transform: translateY(0) scale(0.5);
    opacity: 0.8;
  }
  100% {
    transform: translateY(-80px) translateX(20px) scale(2);
    opacity: 0;
  }
}

/* Heat zone */
.heat-zone {
  position: absolute;
  bottom: 10%;
  right: 20%;
  width: 80px;
  height: 60px;
  opacity: 0;
  transition: opacity 0.5s ease;
}

.heat-zone.active {
  opacity: 1;
}

.heat-waves {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
}

.heat-wave {
  position: absolute;
  bottom: 0;
  width: 40px;
  height: 2px;
  background: rgba(255, 100, 50, 0.5);
  animation: wave 1s ease-in-out infinite;
}

.heat-wave:nth-child(2) {
  animation-delay: 0.3s;
  bottom: 10px;
}

.heat-wave:nth-child(3) {
  animation-delay: 0.6s;
  bottom: 20px;
}

@keyframes wave {
  0%, 100% { transform: translateX(-50%) scaleX(1); opacity: 0.5; }
  50% { transform: translateX(-50%) scaleX(1.5); opacity: 0.8; }
}

/* Fire */
.fire {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
}

.flame {
  position: absolute;
  bottom: 0;
  border-radius: 50% 50% 20% 20%;
  animation: flicker 0.5s ease-in-out infinite alternate;
}

.flame-1 {
  left: -8px;
  width: 16px;
  height: 30px;
  background: linear-gradient(180deg, #ff6b00 0%, #ffcc00 100%);
}

.flame-2 {
  left: 0;
  width: 20px;
  height: 40px;
  background: linear-gradient(180deg, #ff4500 0%, #ff8c00 100%);
  animation-delay: 0.1s;
}

.flame-3 {
  left: 8px;
  width: 14px;
  height: 25px;
  background: linear-gradient(180deg, #ff6b00 0%, #ffcc00 100%);
  animation-delay: 0.2s;
}

@keyframes flicker {
  0% { transform: scaleY(1) scaleX(1); }
  100% { transform: scaleY(1.1) scaleX(0.9); }
}

/* Stats overlay */
.stats-overlay {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: rgba(0, 0, 0, 0.5);
  padding: 8px 12px;
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-icon {
  font-size: 14px;
}

.stat-value {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #fff;
}

/* Progress bar */
.progress-container {
  position: absolute;
  bottom: 15px;
  left: 50%;
  transform: translateX(-50%);
  width: 80%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50 0%, #FFC107 50%, #FF5722 100%);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #fff;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}
</style>
