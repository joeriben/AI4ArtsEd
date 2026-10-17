<template>
  <div dir="ltr" class="climate-background" :style="skyStyle">
    <!-- Sun - size based on power consumption -->
    <div class="sun" :style="sunStyle">
      <div class="sun-glow" :style="sunGlowStyle"></div>
      <div class="sun-core"></div>
      <div class="sun-rays">
        <div class="ray" v-for="n in 8" :key="n" :style="getRayStyle(n)"></div>
      </div>
    </div>

    <!-- Clouds - count and darkness based on CO2 -->
    <div class="clouds" :style="cloudContainerStyle">
      <div
        v-for="(cloud, index) in clouds"
        :key="index"
        class="cloud"
        :style="cloud.style"
      >
        <div class="cloud-puff cloud-puff-1"></div>
        <div class="cloud-puff cloud-puff-2"></div>
        <div class="cloud-puff cloud-puff-3"></div>
      </div>
    </div>

    <!-- Smog overlay at high CO2 levels -->
    <div class="smog-overlay" :style="smogStyle"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  powerWatts: number
  powerLimit: number
  co2Grams: number
  temperature?: number
}>()

// Sun calculations
const powerRatio = computed(() => Math.min(1, props.powerWatts / props.powerLimit))

const sunSize = computed(() => {
  // Size from 50px (idle) to 150px (full power) - dramatic effect
  return 50 + powerRatio.value * 100
})

const sunStyle = computed(() => ({
  width: `${sunSize.value}px`,
  height: `${sunSize.value}px`,
  top: `${15 - powerRatio.value * 5}%`, // Rises slightly with more power
  right: `${10 + powerRatio.value * 5}%`
}))

const sunGlowStyle = computed(() => {
  const intensity = 0.3 + powerRatio.value * 0.4
  const spread = sunSize.value * (1 + powerRatio.value * 0.5)
  return {
    boxShadow: `0 0 ${spread}px ${spread / 2}px rgba(255, 200, 50, ${intensity})`
  }
})

function getRayStyle(n: number) {
  const angle = (n - 1) * 45
  const length = 15 + powerRatio.value * 40  // Longer rays at high power
  const radius = sunSize.value / 2
  return {
    transform: `rotate(${angle}deg) translateY(${radius}px)`,
    height: `${length}px`,
    opacity: 0.5 + powerRatio.value * 0.5  // More visible
  }
}

// Cloud calculations — separated into stable positions + dynamic darkness
const co2Ratio = computed(() => Math.min(1, props.co2Grams / 5)) // Max effect at 5g

// Cloud count changes rarely (only when co2Grams crosses 0.15 thresholds)
const cloudCount = computed(() => Math.min(12, Math.floor(props.co2Grams / 0.15) + 2))

// Cloud positions: only recomputed when cloudCount changes (not every second)
const clouds = computed(() => {
  return Array.from({ length: cloudCount.value }, (_, i) => {
    // Deterministic but varied positions
    const seed = (i * 17) % 100
    const left = 5 + (seed * 0.85) % 80
    const top = 5 + (i * 11) % 25
    const scale = 0.6 + (i % 3) * 0.25

    return {
      style: {
        left: `${left}%`,
        top: `${top}%`,
        transform: `scale(${scale})`,
        animationDelay: `${i * 0.7}s`
      }
    }
  })
})

// Darkness changes every second but is applied via CSS variable on container
// instead of recreating cloud objects
const cloudDarkness = computed(() => Math.min(0.8, co2Ratio.value))
const cloudContainerStyle = computed(() => {
  const gray = Math.round(200 - cloudDarkness.value * 120)
  return {
    '--cloud-color': `rgb(${gray}, ${gray}, ${gray})`,
    '--cloud-opacity': 0.4 + cloudDarkness.value * 0.5
  }
})

// Sky gradient - blue to smoggy gray-brown
const skyStyle = computed(() => {
  const co2Factor = Math.min(1, props.co2Grams / 8)

  // Base colors (clean sky)
  const cleanTopR = 135, cleanTopG = 206, cleanTopB = 235
  const cleanBotR = 176, cleanBotG = 224, cleanBotB = 230

  // Smoggy colors (polluted sky)
  const smogTopR = 169, smogTopG = 160, smogTopB = 140
  const smogBotR = 180, smogBotG = 165, smogBotB = 145

  // Interpolate based on CO2
  const topR = Math.round(cleanTopR + (smogTopR - cleanTopR) * co2Factor)
  const topG = Math.round(cleanTopG + (smogTopG - cleanTopG) * co2Factor)
  const topB = Math.round(cleanTopB + (smogTopB - cleanTopB) * co2Factor)

  const botR = Math.round(cleanBotR + (smogBotR - cleanBotR) * co2Factor)
  const botG = Math.round(cleanBotG + (smogBotG - cleanBotG) * co2Factor)
  const botB = Math.round(cleanBotB + (smogBotB - cleanBotB) * co2Factor)

  return {
    background: `linear-gradient(180deg,
      rgb(${topR}, ${topG}, ${topB}) 0%,
      rgb(${botR}, ${botG}, ${botB}) 100%)`
  }
})

// Smog overlay for heavy pollution
const smogStyle = computed(() => {
  const opacity = Math.max(0, (props.co2Grams - 3) / 10) // Starts appearing at 3g
  return {
    opacity: Math.min(0.4, opacity)
  }
})
</script>

<style scoped>
.climate-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 60%;
  overflow: hidden;
  transition: background 1s ease;
}

/* Sun */
.sun {
  position: absolute;
  border-radius: 50%;
  transition: all 0.5s ease;
}

.sun-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  border-radius: 50%;
  transition: box-shadow 0.5s ease;
}

.sun-core {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: radial-gradient(circle,
    #fff7e0 0%,
    #ffd93d 40%,
    #ff9500 100%
  );
}

.sun-rays {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
}

.ray {
  position: absolute;
  top: 50%;
  left: 50%;
  margin-left: -4px;
  width: 8px;
  background: linear-gradient(
    rgba(255, 220, 100, 0.9),
    transparent
  );
  transform-origin: center 0;
  border-radius: 4px;
  transition: all 0.5s ease;
}

/* Clouds */
.clouds {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.cloud {
  position: absolute;
  width: 80px;
  height: 30px;
  opacity: var(--cloud-opacity, 0.4);
  transition: opacity 0.5s ease;
  animation: cloud-float 15s ease-in-out infinite;
}

.cloud-puff {
  position: absolute;
  border-radius: 50%;
  background: var(--cloud-color, rgb(200, 200, 200));
  transition: background 0.5s ease;
}

.cloud-puff-1 {
  width: 40px;
  height: 40px;
  bottom: 0;
  left: 0;
}

.cloud-puff-2 {
  width: 50px;
  height: 50px;
  bottom: 5px;
  left: 25px;
}

.cloud-puff-3 {
  width: 35px;
  height: 35px;
  bottom: 0;
  left: 55px;
}

@keyframes cloud-float {
  0%, 100% {
    transform: var(--cloud-transform, scale(1)) translateX(0);
  }
  50% {
    transform: var(--cloud-transform, scale(1)) translateX(15px);
  }
}

/* Smog overlay */
.smog-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(180deg,
    rgba(100, 80, 60, 0.3) 0%,
    rgba(120, 100, 80, 0.2) 100%
  );
  pointer-events: none;
  transition: opacity 1s ease;
}
</style>
