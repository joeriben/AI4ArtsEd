<template>
  <div dir="ltr" class="progress-animation-container">
    <div class="token-processing-scene">
      <!-- GPU Stats Bar -->
      <div class="stats-bar">
        <div class="stat">
          <span class="stat-label">{{ t('edutainment.pixel.grafikkarte') }}</span>
          <span class="stat-value">{{ Math.round(gpuPower) }}W / {{ Math.round(gpuTemp) }}°C<span class="cursor">_</span></span>
        </div>
        <div class="stat">
          <span class="stat-label">{{ t('edutainment.pixel.energieverbrauch') }}</span>
          <span class="stat-value">{{ (totalEnergy / 1000).toFixed(4) }}kWh</span>
        </div>
        <div class="stat">
          <span class="stat-label">{{ t('edutainment.pixel.co2Menge') }}</span>
          <span class="stat-value">{{ totalCo2.toFixed(1) }}g</span>
        </div>
        <div class="stat">
          <span class="stat-label">Pixel</span>
          <span class="stat-value">{{ processedPixels.size }}/196</span>
        </div>
      </div>

      <!-- Instructions overlay (fades after 5s) -->
      <Transition name="fade">
        <div v-if="showInstructions" class="instructions-overlay">
          <span class="instruction-text">{{ t('edutainment.pixel.clickToProcess') }}</span>
        </div>
      </Transition>

      <!-- Summary overlay (bottom, appears after 5s) -->
      <Transition name="fade">
        <div v-if="isShowingSummary" class="summary-box">
          <div class="summary-comparison">
            {{ t('edutainment.pixel.smartphoneComparison', { minutes: smartphoneMinutes }) }}
          </div>
        </div>
      </Transition>

      <!-- Input Grid (Left) - Clickable -->
      <div class="input-grid-container">
        <div class="canvas-grid clickable" @click="handleGridClick" ref="inputGridRef">
          <div
            v-for="(pixel, index) in inputPixels"
            :key="'input-' + index"
            class="pixel-token"
            :class="{
              hidden: processedPixels.has(index) || flyingPixels.has(index),
              clickable: !processedPixels.has(index) && !flyingPixels.has(index)
            }"
            :style="getInputPixelStyle(pixel, index)"
            :data-index="index"
          ></div>
        </div>
      </div>

      <!-- Processor Box (Center) -->
      <div class="processor-box" :class="{ active: flyingPixels.size > 0 || isProcessing }">
        <div class="processor-glow"></div>
        <div class="processor-core">
          <div class="neural-network">
            <div class="network-node node-1"></div>
            <div class="network-node node-2"></div>
            <div class="network-node node-3"></div>
            <div class="network-node node-4"></div>
            <div class="network-node node-5"></div>
            <div class="network-connection conn-1"></div>
            <div class="network-connection conn-2"></div>
            <div class="network-connection conn-3"></div>
            <div class="network-connection conn-4"></div>
          </div>
          <div class="processor-icon">GPU</div>
        </div>
      </div>

      <!-- Output Grid (Right) -->
      <div class="output-grid-container">
        <div class="canvas-grid">
          <div
            v-for="(pixel, index) in outputPixels"
            :key="'output-' + index"
            class="pixel-token"
            :class="{
              visible: processedPixels.has(index),
              flying: flyingPixels.has(index),
              dissolving: dissolvingPixels.has(index)
            }"
            :style="getOutputPixelStyle(pixel, index)"
          ></div>
        </div>
      </div>

      <!-- Progress Bar at Bottom -->
      <div class="progress-bar-container">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: progress + '%' }">
            <div class="progress-shine"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { tokenColors, imageTemplates, GRID_SIZE } from '@/data/pixelTemplates'

const { t } = useI18n()

const props = defineProps<{
  progress: number
  estimatedSeconds?: number
  gpuPower?: number
  gpuTemp?: number
  totalEnergy?: number
  totalCo2?: number
  isShowingSummary?: boolean
  smartphoneMinutes?: number
}>()

// Default values for GPU stats
const gpuPower = computed(() => props.gpuPower ?? 0)
const gpuTemp = computed(() => props.gpuTemp ?? 0)
const totalEnergy = computed(() => props.totalEnergy ?? 0)
const totalCo2 = computed(() => props.totalCo2 ?? 0)
const smartphoneMinutes = computed(() => {
  if (props.smartphoneMinutes !== undefined) return props.smartphoneMinutes
  return Math.round(totalCo2.value * 30)
})

const isProcessing = computed(() => props.progress > 0 && props.progress < 100)

// ==================== Interactive State ====================
const processedPixels = ref<Set<number>>(new Set())
const flyingPixels = ref<Set<number>>(new Set())
const gameState = ref<'playing' | 'completed' | 'transitioning'>('playing')
const dissolvingPixels = ref<Set<number>>(new Set())
const autoCompleted = ref(false)
const showInstructions = ref(true)
const inputGridRef = ref<HTMLElement | null>(null)

// ==================== Image Templates (imported from shared data) ====================

const imageKeys = Object.keys(imageTemplates)
const currentImageKey = ref('robot')
const currentPattern = computed(() => imageTemplates[currentImageKey.value])

// Input pixels (random colors)
const inputPixels = computed(() => {
  const pixels: Array<{ colorIndex: number; row: number; col: number }> = []
  for (let row = 0; row < GRID_SIZE; row++) {
    for (let col = 0; col < GRID_SIZE; col++) {
      const colorIndex = (row * GRID_SIZE + col) % 7 + 1
      pixels.push({ colorIndex, row, col })
    }
  }
  return pixels
})

// Output pixels (target image)
const outputPixels = computed(() => {
  const pattern = currentPattern.value
  const pixels: Array<{ colorIndex: number; row: number; col: number }> = []
  for (let row = 0; row < GRID_SIZE; row++) {
    for (let col = 0; col < GRID_SIZE; col++) {
      const colorIndex = pattern?.[row]?.[col] ?? 0
      pixels.push({ colorIndex, row, col })
    }
  }
  return pixels
})

// ==================== Click Handler ====================

function handleGridClick(event: MouseEvent) {
  if (gameState.value === 'transitioning') return

  if (gameState.value === 'completed') {
    startTransition()
    return
  }

  const grid = inputGridRef.value
  if (!grid) return

  const rect = grid.getBoundingClientRect()
  const cellSize = rect.width / GRID_SIZE
  const col = Math.floor((event.clientX - rect.left) / cellSize)
  const row = Math.floor((event.clientY - rect.top) / cellSize)

  if (row < 0 || row >= GRID_SIZE || col < 0 || col >= GRID_SIZE) return

  // Find 4-9 nearby unprocessed pixels
  const nearby = findNearbyUnprocessed(row, col, 4, 9)
  if (nearby.length === 0) return

  // Start flying animation
  nearby.forEach(idx => flyingPixels.value.add(idx))

  // After animation, mark as processed
  setTimeout(() => {
    nearby.forEach(idx => {
      flyingPixels.value.delete(idx)
      processedPixels.value.add(idx)
    })
    if (processedPixels.value.size >= GRID_SIZE * GRID_SIZE) {
      gameState.value = 'completed'
    }
  }, 600)
}

function startTransition() {
  gameState.value = 'transitioning'
  dissolvingPixels.value = new Set(processedPixels.value)

  setTimeout(() => {
    processedPixels.value.clear()
    flyingPixels.value.clear()
    dissolvingPixels.value.clear()
    const otherKeys = imageKeys.filter(k => k !== currentImageKey.value)
    const nextKey = otherKeys[Math.floor(Math.random() * otherKeys.length)]
    if (nextKey) currentImageKey.value = nextKey
    gameState.value = 'playing'
  }, 600)
}

function findNearbyUnprocessed(row: number, col: number, min: number, max: number): number[] {
  const candidates: Array<{ idx: number; dist: number }> = []

  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      const idx = r * GRID_SIZE + c
      if (processedPixels.value.has(idx) || flyingPixels.value.has(idx)) continue

      const dist = Math.abs(r - row) + Math.abs(c - col)
      candidates.push({ idx, dist })
    }
  }

  candidates.sort((a, b) => a.dist - b.dist)
  const count = Math.min(max, Math.max(min, candidates.length))
  return candidates.slice(0, count).map(c => c.idx)
}

// ==================== Auto-complete at 90% ====================

function autoCompleteRemaining() {
  const remaining: number[] = []
  const totalPixels = GRID_SIZE * GRID_SIZE
  for (let i = 0; i < totalPixels; i++) {
    if (!processedPixels.value.has(i) && !flyingPixels.value.has(i)) {
      remaining.push(i)
    }
  }

  if (remaining.length === 0) return

  // Fly in batches of 8-12 with stagger
  let delay = 0
  for (let i = 0; i < remaining.length; i += 10) {
    const batch = remaining.slice(i, i + 10)
    setTimeout(() => {
      batch.forEach(idx => flyingPixels.value.add(idx))
      setTimeout(() => {
        batch.forEach(idx => {
          flyingPixels.value.delete(idx)
          processedPixels.value.add(idx)
        })
        if (processedPixels.value.size >= GRID_SIZE * GRID_SIZE) {
          gameState.value = 'completed'
        }
      }, 600)
    }, delay)
    delay += 150
  }
}

watch(() => props.progress, (newProgress) => {
  if (newProgress >= 90 && !autoCompleted.value) {
    autoCompleted.value = true
    autoCompleteRemaining()
  }
})

// ==================== Styles ====================

function getInputPixelStyle(pixel: { colorIndex: number }, index: number) {
  const color = tokenColors[pixel.colorIndex - 1] ?? '#888'
  const stagger = flyingPixels.value.has(index) ? (index % 5) * 0.03 : 0
  return {
    backgroundColor: color,
    boxShadow: `0 0 6px ${color}80, inset 0 0 3px rgba(255,255,255,0.2)`,
    '--fly-delay': `${stagger}s`
  }
}

function getOutputPixelStyle(pixel: { colorIndex: number; row: number; col: number }, index: number) {
  const inputPixel = inputPixels.value[index]
  const isFlying = flyingPixels.value.has(index)
  const isDissolving = dissolvingPixels.value.has(index)

  if (isDissolving) {
    // Stagger based on distance from center (spiral outward)
    const centerRow = (GRID_SIZE - 1) / 2
    const centerCol = (GRID_SIZE - 1) / 2
    const dist = Math.sqrt(
      (pixel.row - centerRow) ** 2 + (pixel.col - centerCol) ** 2
    )
    const color = pixel.colorIndex > 0 ? (tokenColors[pixel.colorIndex - 1] ?? '#888') : 'transparent'
    return {
      backgroundColor: color,
      '--dissolve-delay': String(Math.round(dist)),
      opacity: pixel.colorIndex === 0 ? 0 : 1
    }
  }

  if (isFlying && inputPixel) {
    const fromColor = tokenColors[inputPixel.colorIndex - 1] ?? '#888'
    const toColor = pixel.colorIndex > 0 ? (tokenColors[pixel.colorIndex - 1] ?? '#888') : 'transparent'
    const stagger = (index % 5) * 0.03
    return {
      '--from-color': fromColor,
      '--to-color': toColor,
      '--fly-delay': `${stagger}s`,
      opacity: pixel.colorIndex === 0 ? 0 : 1
    }
  }

  const color = pixel.colorIndex > 0 ? (tokenColors[pixel.colorIndex - 1] ?? '#888') : 'transparent'
  return {
    backgroundColor: color,
    boxShadow: pixel.colorIndex > 0 ? `0 0 8px ${color}80` : 'none',
    opacity: pixel.colorIndex === 0 ? 0 : 1
  }
}

// ==================== Lifecycle ====================

onMounted(() => {
  const randomIndex = Math.floor(Math.random() * imageKeys.length)
  const selectedKey = imageKeys[randomIndex]
  if (selectedKey) currentImageKey.value = selectedKey

  // Hide instructions after 5s
  setTimeout(() => {
    showInstructions.value = false
  }, 5000)
})

// Reset when progress goes to 0
watch(() => props.progress, (newProgress, oldProgress) => {
  if (newProgress === 0 && oldProgress !== 0) {
    processedPixels.value.clear()
    flyingPixels.value.clear()
    dissolvingPixels.value.clear()
    autoCompleted.value = false
    gameState.value = 'playing'
    showInstructions.value = true
    setTimeout(() => { showInstructions.value = false }, 5000)
  }
})
</script>

<style scoped>
.progress-animation-container {
  width: 100%;
  height: 320px;
  position: relative;
  overflow: hidden;
}

.token-processing-scene {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 30px;
  padding: 20px;
  background: radial-gradient(ellipse at center, #1a1a2e 0%, #0a0a1a 100%);
  border-radius: 12px;
}

/* Stats bar */
.stats-bar {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 20px;
  z-index: 100;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-label {
  font-family: 'Courier New', monospace;
  font-size: 9px;
  color: rgba(0, 255, 0, 0.6);
  text-transform: uppercase;
}

.stat-value {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #0f0;
  font-weight: bold;
  text-shadow: 0 0 8px #0f0;
}

.cursor {
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  50.1%, 100% { opacity: 0; }
}

/* Instructions */
.instructions-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 150;
  pointer-events: none;
}

.instruction-text {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #0f0;
  text-shadow: 0 0 10px #0f0;
  background: rgba(0, 0, 0, 0.7);
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid rgba(0, 255, 0, 0.3);
}

/* Summary box - positioned below the progress bar */
.summary-box {
  position: absolute;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  background: rgba(0, 0, 0, 0.85);
  padding: 4px 20px;
  border-radius: 6px;
  border: 1px solid rgba(0, 255, 0, 0.4);
  backdrop-filter: blur(8px);
}

.summary-comparison {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #0f0;
  text-shadow: 0 0 8px #0f0;
  white-space: nowrap;
}

/* Fade transitions */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Input Grid */
.input-grid-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 160px;
}

.output-grid-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 160px;
}

/* Canvas Grid */
.canvas-grid {
  display: grid;
  grid-template-columns: repeat(14, 10px);
  grid-template-rows: repeat(14, 10px);
  gap: 1px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}

.canvas-grid.clickable {
  cursor: pointer;
}

/* Pixel Token */
.pixel-token {
  width: 10px;
  height: 10px;
  border-radius: 1px;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

/* Input pixels */
.input-grid-container .pixel-token.clickable:hover {
  transform: scale(1.3);
  z-index: 10;
}

.input-grid-container .pixel-token.hidden {
  transform: scale(0);
  opacity: 0;
}

/* Output pixels */
.output-grid-container .pixel-token {
  transform: scale(0);
  opacity: 0;
}

.output-grid-container .pixel-token.visible {
  transform: scale(1);
  opacity: 1;
}

.output-grid-container .pixel-token.flying {
  animation: pixel-fly-from-left 0.6s cubic-bezier(0.22, 1, 0.36, 1);
  animation-delay: var(--fly-delay, 0s);
  animation-fill-mode: forwards;
  z-index: 100;
}

.output-grid-container .pixel-token.dissolving {
  animation: pixel-dissolve 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  animation-delay: calc(var(--dissolve-delay, 0) * 8ms);
}

@keyframes pixel-dissolve {
  0% { transform: scale(1); opacity: 1; }
  30% { transform: scale(1.3) rotate(90deg); opacity: 0.9; }
  60% { transform: scale(1.5) rotate(200deg); opacity: 0.5; }
  100% { transform: scale(0) rotate(360deg); opacity: 0; }
}

@keyframes pixel-fly-from-left {
  0% {
    transform: translate(-350px, 0) scale(0.7) rotate(0deg);
    background-color: var(--from-color);
    opacity: 1;
    box-shadow: 0 0 25px var(--from-color);
  }
  20% {
    transform: translate(-210px, 0) scale(1.2) rotate(90deg);
    background-color: var(--from-color);
  }
  50% {
    transform: translate(-150px, -8px) scale(1.8) rotate(380deg);
    background-color: color-mix(in srgb, var(--from-color) 50%, var(--to-color) 50%);
  }
  100% {
    transform: translate(0, 0) scale(1) rotate(720deg);
    background-color: var(--to-color);
    box-shadow: 0 0 8px var(--to-color);
  }
}

/* Processor Box */
.processor-box {
  position: relative;
  width: 140px;
  height: 160px;
  background: linear-gradient(135deg, #1a1a3e 0%, #0f0f2a 100%);
  border: 3px solid #2d4a7c;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 20px rgba(45, 74, 124, 0.3);
  transition: all 0.3s ease;
}

.processor-box.active {
  border-color: #4a90e2;
  box-shadow: 0 0 40px rgba(74, 144, 226, 0.6);
}

.processor-glow {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 10px;
  background: radial-gradient(circle, rgba(74, 144, 226, 0.3) 0%, transparent 70%);
  opacity: 0;
}

.processor-box.active .processor-glow {
  opacity: 1;
  animation: processor-flicker 0.8s ease-in-out infinite;
}

@keyframes processor-flicker {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.15); opacity: 1; }
}

.processor-core {
  position: relative;
  width: 80%;
  height: 80%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.neural-network {
  position: absolute;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.network-node {
  position: absolute;
  width: 8px;
  height: 8px;
  background: #4a90e2;
  border-radius: 50%;
  opacity: 0.3;
  box-shadow: 0 0 8px #4a90e2;
}

.node-1 { top: 15%; left: 20%; animation: node-pulse 1.5s ease-in-out infinite; }
.node-2 { top: 50%; left: 10%; animation: node-pulse 1.5s ease-in-out infinite 0.3s; }
.node-3 { top: 80%; left: 25%; animation: node-pulse 1.5s ease-in-out infinite 0.6s; }
.node-4 { top: 30%; right: 20%; animation: node-pulse 1.5s ease-in-out infinite 0.9s; }
.node-5 { top: 70%; right: 15%; animation: node-pulse 1.5s ease-in-out infinite 1.2s; }

.processor-box.active .network-node {
  opacity: 0.8;
  animation-duration: 0.8s;
}

@keyframes node-pulse {
  0%, 100% { transform: scale(1); opacity: 0.3; }
  50% { transform: scale(1.6); opacity: 1; box-shadow: 0 0 20px #4a90e2; }
}

.network-connection {
  position: absolute;
  background: linear-gradient(90deg, transparent 0%, #4a90e2 50%, transparent 100%);
  height: 1px;
  opacity: 0.2;
}

.conn-1 { top: 25%; left: 20%; width: 60%; transform: rotate(15deg); }
.conn-2 { top: 55%; left: 10%; width: 70%; transform: rotate(-10deg); }
.conn-3 { top: 40%; left: 15%; width: 50%; transform: rotate(45deg); }
.conn-4 { top: 70%; left: 25%; width: 55%; transform: rotate(-20deg); }

.processor-box.active .network-connection {
  opacity: 0.6;
  animation: connection-pulse 1s ease-in-out infinite;
}

@keyframes connection-pulse {
  0%, 100% { opacity: 0.1; }
  50% { opacity: 0.8; }
}

.processor-icon {
  font-size: 44px;
  animation: processor-icon-pulse 1s ease-in-out infinite;
  z-index: 10;
}

.processor-box.active .processor-icon {
  animation: processor-icon-active 0.5s ease-in-out infinite;
}

@keyframes processor-icon-pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.05); opacity: 0.7; }
}

@keyframes processor-icon-active {
  0%, 100% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.25) rotate(-3deg); opacity: 1; }
}

/* Progress Bar */
.progress-bar-container {
  position: absolute;
  bottom: 38px;
  left: 50%;
  transform: translateX(-50%);
  width: 85%;
  max-width: 600px;
}

.progress-bar-bg {
  width: 100%;
  height: 8px;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3498db 0%, #2ecc71 50%, #f39c12 100%);
  border-radius: 10px;
  transition: width 0.3s ease-out;
}

.progress-shine {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.3) 50%, transparent 100%);
  animation: shine-move 2s ease-in-out infinite;
}

@keyframes shine-move {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}


/* Responsive */
@media (max-width: 768px) {
  .token-processing-scene {
    gap: 15px;
    padding: 15px 8px;
  }

  .input-grid-container, .output-grid-container {
    width: 130px;
  }

  .processor-box {
    width: 100px;
    height: 120px;
  }

  .processor-icon {
    font-size: 32px;
  }

  .canvas-grid {
    grid-template-columns: repeat(14, 8px);
    grid-template-rows: repeat(14, 8px);
    padding: 8px;
  }

  .pixel-token {
    width: 8px;
    height: 8px;
  }
}
</style>
