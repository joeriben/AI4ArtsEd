<template>
  <div dir="ltr" class="iceberg-animation">
    <!-- Climate background (sky, sun, clouds) -->
    <ClimateBackground
      :power-watts="effectivePower"
      :power-limit="gpuStats.power_limit_watts || 600"
      :co2-grams="totalCo2"
      :temperature="effectiveTemp"
    />

    <!-- Water area -->
    <div class="water-area" :style="waterStyle"></div>

    <!-- Iceberg canvas (drawing or display) -->
    <div class="iceberg-container" ref="containerRef">
      <canvas
        ref="icebergCanvasRef"
        :width="canvasWidth"
        :height="canvasHeight"
        @pointerdown="handlePointerDown"
        @pointermove="handlePointerMove"
        @pointerup="handlePointerUp"
        @pointerleave="handlePointerUp"
        :class="{ drawing: drawingState === 'drawing' && isPointerDown }"
      />

      <!-- Drawing instructions (visible first 5 seconds, then fades) -->
      <Transition name="fade">
        <div v-if="showInstructions && drawingState === 'idle'" class="state-overlay instructions">
          <span class="instruction">{{ t('edutainment.iceberg.drawPrompt') }}</span>
        </div>
      </Transition>

      <!-- Melted message (when all icebergs have melted) -->
      <div v-if="drawingState === 'melted'" class="state-overlay melted center">
        <span class="status">{{ t('edutainment.iceberg.melted') }}</span>
      </div>
    </div>

    <!-- Summary overlay (bottom, styled box, appears after 5s) -->
    <Transition name="fade">
      <div v-if="isShowingSummary" class="summary-box">
        <span class="summary-detail">{{ t('edutainment.iceberg.meltedMessage', { co2: totalCo2.toFixed(2) }) }}</span>
        <span class="summary-comparison">{{ t('edutainment.iceberg.comparison', { volume: iceMeltVolume }) }}</span>
        <span class="summary-info">{{ t('edutainment.iceberg.comparisonInfo') }}</span>
      </div>
    </Transition>

    <!-- Stats overlay with labels -->
    <div class="stats-bar">
      <div class="stat" :title="t('edutainment.iceberg.gpuPower')">
        <span class="stat-label">{{ t('edutainment.pixel.grafikkarte') }}</span>
        <span class="stat-value">{{ Math.round(effectivePower) }}W / {{ Math.round(effectiveTemp) }}°C</span>
      </div>
      <div class="stat">
        <span class="stat-label">{{ t('edutainment.pixel.energieverbrauch') }}</span>
        <span class="stat-value">{{ (totalEnergy / 1000).toFixed(4) }}kWh</span>
      </div>
      <div class="stat" :title="t('edutainment.iceberg.co2Info')">
        <span class="stat-label">{{ t('edutainment.pixel.co2Menge') }}</span>
        <span class="stat-value">{{ totalCo2.toFixed(1) }}g</span>
      </div>
      <div v-if="estimatedSeconds" class="stat">
        <span class="stat-label">~</span>
        <span class="stat-value">{{ estimatedSeconds }}s</span>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ClimateBackground from './ClimateBackground.vue'
import {
  type Point,
  simplifyPolygon,
  calculateArea,
  calculateCentroid
} from '@/composables/useIcebergPhysics'
import { useAnimationProgress } from '@/composables/useAnimationProgress'

const { t } = useI18n()

// Props
const props = defineProps<{
  autoStart?: boolean
  progress?: number
  estimatedSeconds?: number
}>()

// ==================== Use Animation Progress Composable ====================
const {
  internalProgress,
  summaryShown,
  gpuStats,
  totalEnergy,
  totalCo2,
  effectivePower,
  effectiveTemp,
  iceMeltVolume
} = useAnimationProgress({
  estimatedSeconds: computed(() => props.estimatedSeconds || 30),
  isActive: computed(() => (props.progress ?? 0) > 0)
})

// Summary: shows after 5 seconds (when instructions fade), stays visible
const isShowingSummary = computed(() => summaryShown.value)

// Instructions visibility: visible at start, fades after 5 seconds
const showInstructions = ref(true)

// ==================== Drawing State ====================
type DrawingState = 'idle' | 'drawing' | 'melting' | 'melted'
const drawingState = ref<DrawingState>('idle')

// Canvas (responsive)
const icebergCanvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const canvasWidth = ref(600)
const canvasHeight = ref(320)
const waterLineY = computed(() => canvasHeight.value * 0.6)

// Smooth ship position (interpolates towards internalProgress)
const shipProgress = ref(0)

// Debounced resize
let resizeTimeout: number | null = null

function resizeCanvas() {
  if (resizeTimeout) clearTimeout(resizeTimeout)
  resizeTimeout = window.setTimeout(() => {
    if (containerRef.value) {
      const rect = containerRef.value.getBoundingClientRect()
      canvasWidth.value = Math.floor(rect.width)
    }
  }, 100)
}

// Drawing state
const isPointerDown = ref(false)
const currentPath = ref<Point[]>([])

// Iceberg type with polygon and physics
interface Iceberg {
  polygon: Point[]
  x: number
  y: number
  angle: number
  vx: number
  vy: number
  vAngle: number
}

const icebergs = ref<Iceberg[]>([])

// Physics constants
const SPECIFIC_GRAVITY = 0.85
const TIME_SCALE = 0.5
const DAMPING_AIR = 0.98
const DAMPING_WATER = 0.94

// Single unified animation loop
let renderLoopId: number | null = null
let lastFrameTime = 0

// Cached water style (only update when energy changes significantly)
let cachedWaterStyleEnergy = -1
let cachedWaterStyle: { background: string } | null = null

const waterStyle = computed(() => {
  // Only recompute if energy changed by more than 0.1
  const energyRounded = Math.round(totalEnergy.value * 10) / 10
  if (cachedWaterStyle && Math.abs(energyRounded - cachedWaterStyleEnergy) < 0.1) {
    return cachedWaterStyle
  }

  cachedWaterStyleEnergy = energyRounded
  const warmth = Math.min(1, totalEnergy.value / 10)
  const r = Math.round(0 + warmth * 50)
  const g = Math.round(100 - warmth * 30)
  const b = Math.round(200 - warmth * 50)
  cachedWaterStyle = {
    background: `linear-gradient(180deg,
      rgba(${r}, ${g}, ${b}, 0.6) 0%,
      rgba(${r - 20}, ${g - 20}, ${b + 20}, 0.8) 100%)`
  }
  return cachedWaterStyle
})

// ==================== Physics Engine ====================

function getTransformedPolygon(iceberg: Iceberg): Point[] {
  const { x, y, angle, polygon } = iceberg
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)

  return polygon.map(p => ({
    x: x + p.x * cos - p.y * sin,
    y: y + p.x * sin + p.y * cos
  }))
}

function getSubmergedPolygon(polygon: Point[]): Point[] {
  const submerged: Point[] = []
  const wl = waterLineY.value

  for (let i = 0; i < polygon.length; i++) {
    const curr = polygon[i]
    const next = polygon[(i + 1) % polygon.length]
    if (!curr || !next) continue

    if (curr.y >= wl) {
      submerged.push(curr)
    }

    if ((curr.y < wl && next.y >= wl) || (curr.y >= wl && next.y < wl)) {
      const t = (wl - curr.y) / (next.y - curr.y)
      submerged.push({
        x: curr.x + t * (next.x - curr.x),
        y: wl
      })
    }
  }

  return submerged
}

function updateIcebergPhysics(iceberg: Iceberg, dtScale: number) {
  const polygon = getTransformedPolygon(iceberg)
  if (polygon.length < 3) return

  const totalArea = calculateArea(polygon)
  if (totalArea < 10) return

  const pc = calculateCentroid(polygon)
  const submerged = getSubmergedPolygon(polygon)
  const submergedArea = calculateArea(submerged)
  const submergedRatio = submergedArea / totalArea

  let forceY = 1
  const fb = submergedRatio / SPECIFIC_GRAVITY
  forceY -= fb

  let torque = 0
  if (submergedArea > 0 && submerged.length >= 3) {
    const pcSubmerged = calculateCentroid(submerged)
    torque = fb * (pcSubmerged.x - pc.x)
  }

  const rotationalInertia = Math.sqrt(totalArea) * 0.5

  iceberg.vy += forceY * TIME_SCALE * dtScale
  iceberg.vAngle += (torque / rotationalInertia) * TIME_SCALE * dtScale

  const baseDamping = DAMPING_AIR * (1 - submergedRatio) + DAMPING_WATER * submergedRatio
  const damping = Math.pow(baseDamping, dtScale)
  const rotDamping = Math.pow(baseDamping - 0.1, dtScale)

  iceberg.vx *= damping
  iceberg.vy *= damping
  iceberg.vAngle *= Math.max(0.5, rotDamping)

  iceberg.x += iceberg.vx * dtScale
  iceberg.y += iceberg.vy * dtScale
  iceberg.angle += iceberg.vAngle * dtScale

  const minY = 30
  const maxY = canvasHeight.value - 30
  if (iceberg.y < minY) iceberg.vy += (minY - iceberg.y) * 0.02 * dtScale
  if (iceberg.y > maxY) iceberg.vy -= (iceberg.y - maxY) * 0.02 * dtScale
}

function updateAllPhysics(dt: number) {
  const dtScale = Math.min(dt, 100) / 50
  for (const iceberg of icebergs.value) {
    updateIcebergPhysics(iceberg, dtScale)
  }
}

function createIceberg(drawnPolygon: Point[]): Iceberg {
  const centroid = calculateCentroid(drawnPolygon)
  return {
    polygon: drawnPolygon.map(p => ({
      x: p.x - centroid.x,
      y: p.y - centroid.y
    })),
    x: centroid.x,
    y: centroid.y,
    angle: 0,
    vx: 0,
    vy: 0,
    vAngle: 0
  }
}

// ==================== Drawing ====================

function handlePointerDown(event: PointerEvent) {
  drawingState.value = 'drawing'
  isPointerDown.value = true
  currentPath.value = []

  const point = getCanvasPoint(event)
  currentPath.value.push(point)

  // Start render loop if not running
  startRenderLoop()

  ;(event.target as HTMLCanvasElement).setPointerCapture(event.pointerId)
}

function handlePointerMove(event: PointerEvent) {
  if (!isPointerDown.value) return

  const point = getCanvasPoint(event)
  const lastPoint = currentPath.value[currentPath.value.length - 1]

  if (lastPoint) {
    const dist = Math.sqrt((point.x - lastPoint.x) ** 2 + (point.y - lastPoint.y) ** 2)
    if (dist > 3) {
      currentPath.value.push(point)
      // Render loop will handle drawing
    }
  }
}

function handlePointerUp(event: PointerEvent) {
  if (!isPointerDown.value) return

  isPointerDown.value = false
  ;(event.target as HTMLCanvasElement).releasePointerCapture(event.pointerId)

  if (currentPath.value.length >= 5) {
    const simplified = simplifyPolygon(currentPath.value, 3)
    if (simplified.length >= 3) {
      icebergs.value.push(createIceberg(simplified))
      currentPath.value = []
      if (drawingState.value !== 'melting') {
        drawingState.value = 'melting'
      }
      return
    }
  }

  currentPath.value = []
  drawingState.value = 'idle'
}

function getCanvasPoint(event: PointerEvent): Point {
  const canvas = icebergCanvasRef.value
  if (!canvas) return { x: 0, y: 0 }

  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height

  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY
  }
}

// ==================== Unified Render Loop ====================

function startRenderLoop() {
  if (renderLoopId) return
  lastFrameTime = performance.now()
  renderLoopId = requestAnimationFrame(renderLoop)
}

function stopRenderLoop() {
  if (renderLoopId) {
    cancelAnimationFrame(renderLoopId)
    renderLoopId = null
  }
}

function renderLoop(currentTime: number) {
  const dt = Math.min(currentTime - lastFrameTime, 100)
  lastFrameTime = currentTime

  // Update ship position (smooth interpolation)
  const target = internalProgress.value
  const diff = target - shipProgress.value
  if (Math.abs(diff) > 0.01) {
    shipProgress.value += diff * 0.08
  }

  // Update physics if melting
  if (drawingState.value === 'melting') {
    const temp = effectiveTemp.value

    for (const iceberg of icebergs.value) {
      meltIcebergPolygon(iceberg, temp, dt)
    }
    updateAllPhysics(dt)

    icebergs.value = icebergs.value.filter(iceberg =>
      calculateArea(iceberg.polygon) >= 50
    )

    if (icebergs.value.length === 0) {
      drawingState.value = 'melted'
    }
  }

  // Render everything
  renderCanvas()

  // Continue loop if needed
  const needsAnimation =
    drawingState.value === 'drawing' ||
    drawingState.value === 'melting' ||
    icebergs.value.length > 0 ||
    Math.abs(diff) > 0.01

  if (needsAnimation) {
    renderLoopId = requestAnimationFrame(renderLoop)
  } else {
    renderLoopId = null
  }
}

function renderCanvas() {
  const canvas = icebergCanvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!ctx || !canvas) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  drawWaterLine(ctx)
  drawShip(ctx)

  // Draw icebergs
  for (const iceberg of icebergs.value) {
    drawSingleIceberg(ctx, iceberg)
  }

  // Draw current path if user is drawing
  if (isPointerDown.value && currentPath.value.length >= 2) {
    const firstPoint = currentPath.value[0]!
    ctx.beginPath()
    ctx.moveTo(firstPoint.x, firstPoint.y)
    for (let i = 1; i < currentPath.value.length; i++) {
      const point = currentPath.value[i]
      if (point) ctx.lineTo(point.x, point.y)
    }
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.stroke()

    // Start point indicator
    ctx.beginPath()
    ctx.arc(firstPoint.x, firstPoint.y, 5, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
    ctx.fill()
  }
}

function drawWaterLine(ctx: CanvasRenderingContext2D) {
  const canvas = icebergCanvasRef.value
  if (!canvas) return

  ctx.setLineDash([8, 4])
  ctx.beginPath()
  ctx.moveTo(0, waterLineY.value)
  ctx.lineTo(canvas.width, waterLineY.value)
  ctx.strokeStyle = 'rgba(100, 180, 255, 0.4)'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.setLineDash([])
}

function drawShip(ctx: CanvasRenderingContext2D) {
  const canvas = icebergCanvasRef.value
  if (!canvas) return

  // Ship is always visible (at left edge when progress is 0)
  const progress = Math.max(0, shipProgress.value)

  const shipWidth = 24
  const shipHeight = 16
  const margin = 20

  const x = margin + (progress / 100) * (canvas.width - 2 * margin - shipWidth)
  const y = waterLineY.value - shipHeight / 2

  ctx.save()

  ctx.beginPath()
  ctx.moveTo(x, y + shipHeight * 0.4)
  ctx.lineTo(x + shipWidth * 0.15, y + shipHeight)
  ctx.lineTo(x + shipWidth * 0.85, y + shipHeight)
  ctx.lineTo(x + shipWidth, y + shipHeight * 0.4)
  ctx.closePath()
  ctx.fillStyle = '#5D4037'
  ctx.fill()

  const mastX = x + shipWidth * 0.45
  ctx.beginPath()
  ctx.moveTo(mastX, y + shipHeight * 0.4)
  ctx.lineTo(mastX, y - shipHeight * 0.6)
  ctx.strokeStyle = '#4E342E'
  ctx.lineWidth = 2
  ctx.stroke()

  ctx.beginPath()
  ctx.moveTo(mastX + 1, y - shipHeight * 0.5)
  ctx.lineTo(mastX + shipWidth * 0.45, y + shipHeight * 0.2)
  ctx.lineTo(mastX + 1, y + shipHeight * 0.3)
  ctx.closePath()
  ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
  ctx.fill()

  ctx.restore()
}

// Cached gradient colors (static, no need to recreate per frame)
const ICEBERG_GRADIENT_COLORS = [
  { stop: 0, color: 'rgba(230, 245, 255, 0.95)' },
  { stop: 0.5, color: 'rgba(200, 230, 255, 0.9)' },
  { stop: 1, color: 'rgba(150, 200, 255, 0.85)' }
]

function drawSingleIceberg(ctx: CanvasRenderingContext2D, iceberg: Iceberg) {
  const polygon = getTransformedPolygon(iceberg)
  if (polygon.length < 3) return

  const firstPoint = polygon[0]
  if (!firstPoint) return

  const submerged = getSubmergedPolygon(polygon)
  if (submerged.length >= 3) {
    const subFirst = submerged[0]
    if (subFirst) {
      ctx.beginPath()
      ctx.moveTo(subFirst.x, subFirst.y)
      for (let i = 1; i < submerged.length; i++) {
        const p = submerged[i]
        if (p) ctx.lineTo(p.x, p.y)
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(100, 180, 220, 0.4)'
      ctx.fill()
    }
  }

  ctx.beginPath()
  ctx.moveTo(firstPoint.x, firstPoint.y)
  for (let i = 1; i < polygon.length; i++) {
    const point = polygon[i]
    if (point) ctx.lineTo(point.x, point.y)
  }
  ctx.closePath()

  // Create gradient (this is unavoidable as it depends on centroid position)
  const centroid = calculateCentroid(polygon)
  const gradient = ctx.createRadialGradient(centroid.x, centroid.y, 0, centroid.x, centroid.y, 100)
  for (const { stop, color } of ICEBERG_GRADIENT_COLORS) {
    gradient.addColorStop(stop, color)
  }

  ctx.fillStyle = gradient
  ctx.fill()
  ctx.strokeStyle = 'rgba(100, 180, 220, 0.8)'
  ctx.lineWidth = 2
  ctx.stroke()
}

function meltIcebergPolygon(iceberg: Iceberg, temp: number, dt: number) {
  if (iceberg.polygon.length < 3) return

  const MELT_THRESHOLD = 45
  if (temp < MELT_THRESHOLD) return

  const tempAboveThreshold = temp - MELT_THRESHOLD
  const meltRate = (tempAboveThreshold / 40) * (dt / 16.67) * 0.002

  iceberg.polygon = iceberg.polygon.map(point => {
    const worldY = iceberg.y + point.y
    const isAboveWater = worldY < waterLineY.value
    const meltMultiplier = isAboveWater ? 2.0 : 1.0
    const factor = 1 - meltRate * meltMultiplier

    return {
      x: point.x * factor,
      y: point.y * factor
    }
  })
}

// ==================== Start ship when inference begins ====================
watch(() => props.progress, (newProgress) => {
  if (newProgress && newProgress > 0) {
    startRenderLoop()
  }
})

// ==================== Lifecycle ====================

onMounted(() => {
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)

  // Initial render (ensures ship is visible immediately)
  setTimeout(() => {
    renderCanvas()
  }, 10)

  // Hide instructions after 5 seconds (summary appears at same time via composable)
  setTimeout(() => {
    showInstructions.value = false
  }, 5000)
})

onUnmounted(() => {
  stopRenderLoop()
  window.removeEventListener('resize', resizeCanvas)
  if (resizeTimeout) {
    clearTimeout(resizeTimeout)
    resizeTimeout = null
  }
})
</script>

<style scoped>
.iceberg-animation {
  position: relative;
  width: 100%;
  height: 320px;
  border-radius: 12px;
  overflow: hidden;
  background: #0a1628;
}

.water-area {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40%;
  transition: background 1s ease;
}

.iceberg-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.iceberg-container canvas {
  cursor: crosshair;
  touch-action: none;
}

.iceberg-container canvas.drawing {
  cursor: none;
}

.state-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
  z-index: 10;
}

.state-overlay.instructions {
  top: 50%;
}

.state-overlay.melted.center {
  top: 50%;
}

/* Summary box at bottom - wide and compact */
.summary-box {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 16px;
  pointer-events: none;
  z-index: 50;
  background: rgba(0, 40, 80, 0.85);
  padding: 6px 20px;
  border-radius: 8px;
  border: 1px solid rgba(100, 180, 255, 0.4);
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  max-width: 90%;
}

.summary-detail {
  color: #e0f0ff;
  font-size: 12px;
  font-family: var(--font-sans);
  white-space: nowrap;
}

.summary-comparison {
  color: #a0d0ff;
  font-size: 12px;
  font-family: var(--font-sans);
  font-style: italic;
  white-space: nowrap;
}

.summary-info {
  color: #80b0d0;
  font-size: 10px;
  font-family: var(--font-sans);
  opacity: 0.8;
  white-space: nowrap;
}

/* Fade transition for instructions/summary */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.instruction {
  color: #1a5276;
  font-size: 16px;
  font-family: var(--font-sans);
  font-style: italic;
  font-weight: 400;
  letter-spacing: 0.5px;
  line-height: 1.6;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5);
  max-width: 300px;
}

.status {
  display: block;
  color: #1a5276;
  font-size: 18px;
  font-family: var(--font-sans);
  font-style: italic;
  font-weight: 700;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5);
  margin-bottom: 10px;
}

.comparison {
  display: block;
  color: #1a5276;
  font-size: 14px;
  font-family: var(--font-sans);
  font-style: italic;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5);
  margin-bottom: 5px;
}


.stats-bar {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 15px;
  background: rgba(0, 0, 0, 0.5);
  padding: 8px 16px;
  border-radius: 20px;
  backdrop-filter: blur(4px);
  pointer-events: none;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-label {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #fff;
  font-weight: 700;
}
</style>
