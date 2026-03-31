<template>
  <div ref="containerRef" dir="ltr" class="forest-game-canvas">
    <!-- Climate background (sky, sun, clouds) - reused from IcebergAnimation -->
    <ClimateBackground
      :power-watts="effectivePower"
      :power-limit="450"
      :co2-grams="totalCo2"
      :temperature="effectiveTemp"
    />

    <canvas
      ref="canvasRef"
      @click="handleClick"
    ></canvas>

    <!-- UI Overlays (same as original) -->
    <div class="stats-bar">
      <div class="stat">
        <span class="stat-label">{{ t('edutainment.pixel.grafikkarte') }}</span>
        <span class="stat-value">{{ Math.round(effectivePower) }}W / {{ Math.round(effectiveTemp) }}°C</span>
      </div>
      <div class="stat">
        <span class="stat-label">{{ t('edutainment.forest.trees') }}</span>
        <span class="stat-value">{{ trees.length }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">{{ t('edutainment.pixel.co2Menge') }}</span>
        <span class="stat-value">{{ totalCo2.toFixed(1) }}g</span>
      </div>
      <div v-if="estimatedSeconds" class="stat">
        <span class="stat-label">~</span>
        <span class="stat-value">{{ estimatedSeconds }}s</span>
      </div>
    </div>

    <!-- Plant instruction / Cooldown -->
    <Transition name="fade">
      <div v-if="showInstructions" class="plant-instruction" :class="{ cooldown: plantCooldown > 0 }">
        <template v-if="treesPlanted === 0">
          {{ t('edutainment.forest.clickToPlant') }}
        </template>
        <template v-else-if="plantCooldown > 0">
          {{ plantCooldown.toFixed(1) }}s
        </template>
      </div>
    </Transition>

    <!-- Game over -->
    <div v-if="gameOver" class="game-over">
      <div class="game-over-text">{{ t('edutainment.forest.gameOver') }}</div>
      <div class="game-over-co2">{{ totalCo2.toFixed(1) }}g CO₂</div>
      <div class="game-over-comparison">
        {{ t('edutainment.forest.comparison', { minutes: treeMinutes }) }}
      </div>
      <div class="game-over-stats">
        {{ t('edutainment.forest.treesPlanted', { count: treesPlanted }) }}
      </div>
    </div>

    <!-- Summary -->
    <Transition name="fade">
      <div v-if="!gameOver && isShowingSummary" class="summary-box">
        <span class="summary-detail">{{ totalCo2.toFixed(2) }}g CO₂</span>
        <span class="summary-comparison">{{ t('edutainment.forest.comparison', { minutes: treeMinutes }) }}</span>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAnimationProgress } from '@/composables/useAnimationProgress'
import { useCanvasRenderer } from '@/composables/useCanvasRenderer'
import { useGameLoop } from '@/composables/useGameLoop'
import { useCanvasDrawing } from '@/composables/useCanvasDrawing'
import { useCanvasObjects, type CanvasObject } from '@/composables/useCanvasObjects'
import ClimateBackground from './ClimateBackground.vue'

const { t } = useI18n()

const props = defineProps<{
  progress?: number
  estimatedSeconds?: number
}>()

// ==================== Animation Progress ====================
const {
  internalProgress,
  summaryShown,
  totalCo2,
  effectivePower,
  effectiveTemp,
  treeMinutes
} = useAnimationProgress({
  estimatedSeconds: computed(() => props.estimatedSeconds || 30),
  isActive: computed(() => (props.progress ?? 0) > 0)
})

const isShowingSummary = computed(() => summaryShown.value)
const showInstructions = ref(true)

// ==================== Tree Types ====================
const TREE_TYPES = ['pine', 'spruce', 'fir', 'oak', 'birch', 'maple', 'willow', 'park', 'forest_icon', 'nature'] as const

// SVG tree paths (outer only — no compound subpaths = solid fill)
// All from Google Material Icons, viewBox 0 -960 960 960, bottom y=-80, height 800, center x≈480
const SVG_TREE_PATHS = {
  park: new Path2D('M558-80H402v-160H120l160-240h-80l280-400 280 400h-80l160 240H558v160Z'),
  forest_icon: new Path2D('M280-80v-160H0l154-240H80l280-400 120 172 120-172 280 400h-74l154 240H680v160H520v-160h-80v160H280Z'),
  nature: new Path2D('M200-80v-80h240v-160h-80q-83 0-141.5-58.5T160-520q0-60 33-110.5t89-73.5q9-75 65.5-125.5T480-880q76 0 132.5 50.5T678-704q56 23 89 73.5T800-520q0 83-58.5 141.5T600-320h-80v160h240v80H200Z'),
} as const
const SVG_SCALE = 50 / 800  // 800 SVG units → 50px canvas (matches geometric tree sizes)
type TreeType = typeof TREE_TYPES[number]

interface Tree extends CanvasObject {
  type: TreeType
  scale: number
  growing: boolean
  growthProgress: number
}

interface Factory extends CanvasObject {
  scale: number
  smoke: SmokeParticle[]
}

interface SmokeParticle {
  x: number
  y: number
  vy: number
  opacity: number
  life: number
}

// ==================== State ====================
const { objects: trees, addObject: addTree, clear: clearTrees } = useCanvasObjects<Tree>()
const { objects: factories, addObject: addFactory, clear: clearFactories } = useCanvasObjects<Factory>()

const plantCooldown = ref(0)
const treesPlanted = ref(0)
const gameOver = ref(false)
const birdProgress = ref(0)
let birdFrame = 0
let birdFrameTimer = 0

// Load bird sprite sheet
const birdImage = new Image()
birdImage.crossOrigin = 'anonymous'
birdImage.src = 'https://s3-us-west-2.amazonaws.com/s.cdpn.io/174479/bird-cells.svg'

let nextId = 0

// ==================== Canvas Setup ====================
const containerRef = ref<HTMLElement | null>(null)

// Let useCanvasRenderer auto-size to container (no hardcoded dimensions)
const { canvasRef, getRenderContext, width: canvasWidth, height: canvasHeight } = useCanvasRenderer(containerRef, {})

const { createCachedGradient, drawCircle, interpolateColor } = useCanvasDrawing()

// ==================== Colors & Constants ====================
const GROUND_COLOR_TOP = '#5a8f5a'
const GROUND_COLOR_BOTTOM = '#2d4a2d'
const GROUND_HEIGHT = 0.3  // 30% of canvas height

// Tree colors by type and health
const TREE_COLORS = {
  healthy: {
    foliage: '#2d5a2d',
    trunk: '#5d4037'
  },
  sick: {
    foliage: '#8b6914',
    trunk: '#4a3f2f'
  },
  dead: {
    foliage: '#4a4a4a',
    trunk: '#2a2a2a'
  }
}

// ==================== Init Forest ====================
function initForest() {
  clearTrees()
  clearFactories()
  nextId = 0
  treesPlanted.value = 0
  plantCooldown.value = 0
  gameOver.value = false
  birdProgress.value = 0

  // Initial trees with perspective + non-overlapping
  const treeCount = 18 + Math.floor(Math.random() * 8)
  for (let i = 0; i < treeCount; i++) {
    let treeY = Math.random() * 10
    let treeScale = 1.0 - (treeY / 10) * 0.45  // Perspective: front=1.0, horizon=0.55
    let treeX = 5 + Math.random() * 90

    // Non-overlapping placement (10 attempts)
    for (let attempt = 0; attempt < 10; attempt++) {
      const overlaps = trees.value.some(t => {
        const avgScale = (t.scale + treeScale) / 2
        return Math.abs(t.x - treeX) < 5 * avgScale && Math.abs(t.y - treeY) < 3
      })
      if (!overlaps) break
      treeX = 5 + Math.random() * 90
      treeY = Math.random() * 10
      treeScale = 1.0 - (treeY / 10) * 0.45
    }

    const tree: Tree = {
      id: nextId++,
      x: treeX,
      y: treeY,
      type: TREE_TYPES[Math.floor(Math.random() * TREE_TYPES.length)]!,
      scale: treeScale,
      growing: false,
      growthProgress: 1,
      render: (ctx) => renderTree(ctx, tree),
      update: (dt) => {
        if (tree.growing && tree.growthProgress < 1) {
          tree.growthProgress = Math.min(1, tree.growthProgress + dt * 2)
          if (tree.growthProgress >= 1) {
            tree.growing = false
          }
        }
      }
    }
    addTree(tree)
  }
}

// ==================== Rendering ====================
function renderGround(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const groundY = height * 0.7
  const groundH = height * GROUND_HEIGHT

  const grad = createCachedGradient(ctx, 0, groundY, 0, groundY + groundH, [
    [0, GROUND_COLOR_TOP],
    [1, GROUND_COLOR_BOTTOM]
  ], 'ground')

  ctx.fillStyle = grad
  ctx.fillRect(0, groundY, width, groundH)
}

function renderBird(ctx: CanvasRenderingContext2D, width: number, height: number) {
  if (!birdImage.complete) return

  const x = (5 + birdProgress.value * 0.9) / 100 * width
  const y = (15 + Math.sin(birdProgress.value * 0.3) * 5) / 100 * height

  // Sprite sheet: 10 frames, each 88px wide, 125px tall (total 900×125)
  const frameWidth = 88
  const frameHeight = 125
  const drawScale = 0.4  // Match original CSS transform: scale(0.4)
  const drawW = frameWidth * drawScale
  const drawH = frameHeight * drawScale

  ctx.save()
  // Match original: filter: brightness(0) invert(1) = white silhouette
  ctx.filter = 'brightness(0) invert(1) drop-shadow(0 0 4px rgba(255,255,255,0.5))'
  ctx.drawImage(
    birdImage,
    birdFrame * frameWidth, 0, frameWidth, frameHeight,  // Source rect (sprite frame)
    x - drawW / 2, y - drawH / 2, drawW, drawH           // Dest rect (centered)
  )
  ctx.filter = 'none'
  ctx.restore()
}

function renderTree(ctx: CanvasRenderingContext2D, tree: Tree) {
  const { width, height } = getRenderContext()
  const x = (tree.x / 100) * width
  // Depth positioning: base 18% from bottom + Y offset (same system as factories)
  const bottomOffset = (18 + tree.y) / 100 * height
  const y = height - bottomOffset

  ctx.save()
  ctx.translate(x, y)
  ctx.scale(tree.scale * tree.growthProgress, tree.scale * tree.growthProgress)

  const svgPath = SVG_TREE_PATHS[tree.type as keyof typeof SVG_TREE_PATHS]

  if (svgPath) {
    // SVG tree types (park, forest_icon, nature)
    ctx.save()
    ctx.scale(SVG_SCALE, SVG_SCALE)
    ctx.translate(-480, 80)  // Bottom-center of SVG (480, -80) → origin

    // Foliage fill
    ctx.fillStyle = TREE_COLORS.healthy.foliage
    ctx.fill(svgPath)

    // Trunk: brown rectangles over trunk areas
    ctx.fillStyle = TREE_COLORS.healthy.trunk
    if (tree.type === 'park') {
      ctx.fillRect(402, -240, 156, 160)
    } else if (tree.type === 'forest_icon') {
      ctx.fillRect(280, -240, 160, 160)
      ctx.fillRect(520, -240, 160, 160)
    } else if (tree.type === 'nature') {
      ctx.fillRect(430, -320, 100, 240)
    }

    // Outline
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.25)'
    ctx.lineWidth = 1 / SVG_SCALE  // Compensate for SVG scale
    ctx.stroke(svgPath)

    ctx.restore()
  } else {
    // Geometric tree types (pine, spruce, fir, oak, maple, birch, willow)
    // Trunk
    ctx.fillStyle = TREE_COLORS.healthy.trunk
    ctx.fillRect(-3, -10, 6, 15)

    // Foliage
    ctx.fillStyle = TREE_COLORS.healthy.foliage
    ctx.beginPath()

    switch (tree.type) {
      case 'pine':
      case 'spruce':
      case 'fir':
        ctx.moveTo(0, -30)
        ctx.lineTo(-15, 0)
        ctx.lineTo(15, 0)
        break
      case 'oak':
      case 'maple':
        ctx.arc(0, -20, 18, 0, Math.PI * 2)
        break
      case 'birch':
      case 'willow':
        ctx.ellipse(0, -20, 12, 20, 0, 0, Math.PI * 2)
        break
    }

    ctx.closePath()
    ctx.fill()

    // Outline
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.25)'
    ctx.lineWidth = 1
    ctx.stroke()
  }

  ctx.restore()
}

function renderFactory(ctx: CanvasRenderingContext2D, factory: Factory) {
  const { width, height } = getRenderContext()
  const x = (factory.x / 100) * width
  const groundY = height * 0.7
  // Bottom position: base 18% from bottom + Y offset (0-6%)
  const bottomOffset = (18 + factory.y) / 100 * height
  const y = height - bottomOffset

  const factoryWidth = 40 * factory.scale
  const factoryHeight = 30 * factory.scale

  ctx.save()

  // Position: x = center, y = bottom of factory
  ctx.translate(x, y)

  // SVG viewBox 0 -960 960 960: path spans x:80-880 (800u), y:-561 to -80 (481u)
  // NO Y-flip needed: SVG y=-80 (bottom) maps to canvas y (ground), y=-561 (top) maps upward
  // Flipping Y would reverse path winding → nonzero fill rule makes factory invisible!
  const scaleX = factoryWidth / 800
  const scaleY = factoryHeight / 481
  ctx.scale(scaleX, scaleY)

  // Translate so SVG bottom-center (480, -80) maps to canvas origin (0, 0)
  ctx.translate(-480, 80)

  // Outer silhouette only (no compound subpaths = no holes = SOLID fill)
  const factoryPath = new Path2D('M80-80v-481l280-119v80l200-80v120h320v480H80Z')

  // Gradient in SVG coordinate space
  const gradient = ctx.createLinearGradient(80, -561, 880, -80)
  gradient.addColorStop(0, '#616161')
  gradient.addColorStop(0.5, '#424242')
  gradient.addColorStop(1, '#212121')

  ctx.fillStyle = gradient
  ctx.fill(factoryPath)

  // Windows as dark rectangles
  ctx.fillStyle = 'rgba(0, 0, 0, 0.3)'
  ctx.fillRect(200, -320, 80, 160)
  ctx.fillRect(360, -320, 80, 160)
  ctx.fillRect(520, -320, 80, 160)

  ctx.restore()

  // Smoke particles (in world coordinates)
  factory.smoke.forEach(particle => {
    ctx.fillStyle = `rgba(100, 100, 100, ${particle.opacity})`
    drawCircle(ctx, particle.x, particle.y, 3, ctx.fillStyle)
  })
}

function render() {
  const { ctx, width, height, clear } = getRenderContext()
  clear()
  // Sky + clouds handled by ClimateBackground component (DOM overlay)

  // Canvas: ground, trees, factories, bird
  renderGround(ctx, width, height)
  ;[...trees.value].sort((a, b) => b.y - a.y).forEach(tree => tree.render(ctx))
  ;[...factories.value].sort((a, b) => b.y - a.y).forEach(factory => factory.render(ctx))
  renderBird(ctx, width, height)
}

// ==================== Game Loop ====================
function gameTick(dt: number) {
  if (gameOver.value) return

  // Update cooldown
  if (plantCooldown.value > 0) {
    plantCooldown.value = Math.max(0, plantCooldown.value - dt)
  }

  // Update bird progress (smooth interpolation, 0-100 matching internalProgress)
  const target = internalProgress.value
  birdProgress.value += (target - birdProgress.value) * 0.08

  // Bird sprite animation: 10 frames at ~10fps = cycle every 1s
  birdFrameTimer += dt
  if (birdFrameTimer >= 0.1) {
    birdFrameTimer = 0
    birdFrame = (birdFrame + 1) % 10
  }

  // Update trees
  trees.value.forEach(tree => tree.update?.(dt))

  // Update factories (smoke particles)
  factories.value.forEach(factory => {
    factory.smoke.forEach(particle => {
      particle.y -= particle.vy * dt * 60
      particle.opacity -= dt * 0.5
      particle.life -= dt
    })

    // Remove dead particles
    factory.smoke = factory.smoke.filter(p => p.life > 0)

    // Spawn new particles from factory chimney area
    if (Math.random() < 0.3) {
      const { width, height } = getRenderContext()
      const factoryX = (factory.x / 100) * width
      const factoryWidth = 40 * factory.scale
      const factoryHeight = 30 * factory.scale
      const bottomOffset = (18 + factory.y) / 100 * height
      const factoryY = height - bottomOffset

      // Smoke spawns from left side (chimney area) at top of factory
      const smokeX = factoryX - factoryWidth * 0.2  // Left side
      const smokeY = factoryY - factoryHeight  // Top

      factory.smoke.push({
        x: smokeX + (Math.random() - 0.5) * 5,
        y: smokeY,
        vy: 0.5 + Math.random() * 0.5,
        opacity: 0.6,
        life: 2
      })
    }
  })

  // Factory spawn rate based on GPU power (matches original formula)
  const factoryRate = (effectivePower.value / 450) * dt * 1.1

  if (factories.value.length < 30 && Math.random() < factoryRate) {
    // Pick Y first (0-10), then derive scale from depth (perspective)
    let newY = Math.random() * 10
    let newScale = 1.0 - (newY / 10) * 0.45  // y=0 (front) → 1.0, y=10 (horizon) → 0.55

    // Find non-overlapping position (10 attempts)
    let newX = 10 + Math.random() * 80
    let placed = false
    for (let attempt = 0; attempt < 10; attempt++) {
      const overlaps = factories.value.some(f => {
        const dx = Math.abs(f.x - newX)
        const dy = Math.abs(f.y - newY)
        const minX = 6 * (f.scale + newScale)  // Scale-aware X gap
        return dx < minX && dy < 3
      })
      if (!overlaps) { placed = true; break }
      newX = 10 + Math.random() * 80
      newY = Math.random() * 10
      newScale = 1.0 - (newY / 10) * 0.45
    }
    if (!placed) return  // Skip if no room

    const factory: Factory = {
      id: nextId++,
      x: newX,
      y: newY,
      scale: newScale,
      smoke: [],
      render: (ctx) => renderFactory(ctx, factory)
    }
    addFactory(factory)

    // Tree destruction: Remove a random mature tree (70% chance)
    const matureTrees = trees.value.filter(t => !t.growing && t.growthProgress >= 1)
    if (matureTrees.length > 0 && Math.random() < 0.7) {
      const treeToRemove = matureTrees[Math.floor(Math.random() * matureTrees.length)]!
      const index = trees.value.findIndex(t => t.id === treeToRemove.id)
      if (index !== -1) {
        trees.value.splice(index, 1)
      }
    }
  }

  // Check game over
  if (trees.value.length === 0) {
    gameOver.value = true
  }

  // Render
  render()
}

useGameLoop({
  mode: 'interval',
  fps: 10,
  onTick: gameTick,
  isActive: computed(() => !gameOver.value && (props.progress ?? 0) > 0)
})

// ==================== Click Handler ====================
function handleClick(e: MouseEvent) {
  if (gameOver.value || plantCooldown.value > 0) return

  const rect = canvasRef.value!.getBoundingClientRect()
  const clickX = ((e.clientX - rect.left) / rect.width) * 100  // Convert to percentage

  // Factory hit detection: Check if click is near a factory
  const nearbyFactory = factories.value.find(f => {
    const hitRadius = 5 * f.scale  // Factory width ~5% per scale unit
    return Math.abs(f.x - clickX) < hitRadius
  })

  // Determine tree position: at factory if hit, otherwise front row
  let treeX = clickX
  let treeY = Math.random() * 2  // Front row (0-2) for normal clicks

  if (nearbyFactory) {
    // Remove factory, plant tree at factory's position
    treeX = nearbyFactory.x
    treeY = nearbyFactory.y
    const index = factories.value.findIndex(f => f.id === nearbyFactory.id)
    if (index !== -1) {
      factories.value.splice(index, 1)
    }
  }

  const treeScale = 1.0 - (treeY / 10) * 0.45  // Perspective scale

  // Plant tree
  const tree: Tree = {
    id: nextId++,
    x: treeX,
    y: treeY,
    type: TREE_TYPES[Math.floor(Math.random() * TREE_TYPES.length)]!,
    scale: treeScale,
    growing: true,
    growthProgress: 0,
    render: (ctx) => renderTree(ctx, tree),
    update: (dt) => {
      if (tree.growing && tree.growthProgress < 1) {
        tree.growthProgress = Math.min(1, tree.growthProgress + dt)  // dt * 1 = 1 second growth
        if (tree.growthProgress >= 1) {
          tree.growing = false
        }
      }
    }
  }

  addTree(tree)
  treesPlanted.value++
  plantCooldown.value = 1  // 1 second cooldown (same as growth time)
}

// ==================== Lifecycle ====================
onMounted(() => {
  initForest()

  setTimeout(() => {
    showInstructions.value = false
  }, 5000)
})
</script>

<style scoped>
.forest-game-canvas {
  position: relative;
  width: 100%;
  height: 320px;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  user-select: none;
}

canvas {
  position: absolute;
  top: 0;
  left: 0;
  display: block;
  width: 100%;
  height: 100%;
  z-index: 10;
}

/* UI Overlays - same as original */
.stats-bar {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 15px;
  background: rgba(0, 0, 0, 0.6);
  padding: 6px 14px;
  border-radius: 15px;
  backdrop-filter: blur(4px);
  z-index: 100;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}

.stat-label {
  font-size: 0.5rem;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
}

.stat-value {
  font-family: 'Courier New', monospace;
  font-size: 0.7rem;
  color: #fff;
  font-weight: bold;
}

.plant-instruction {
  position: absolute;
  bottom: 3%;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(76, 175, 80, 0.8);
  color: white;
  padding: 2% 4%;
  border-radius: 15px;
  font-size: 0.75rem;
  font-weight: bold;
  transition: background 0.3s;
  min-width: 20%;
  text-align: center;
  z-index: 90;
}

.plant-instruction.cooldown {
  background: rgba(158, 158, 158, 0.8);
}

.game-over {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.8);
  padding: 20px 30px;
  border-radius: 12px;
  text-align: center;
  z-index: 110;
}

.game-over-text {
  color: #ff5722;
  font-size: 1.25rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.game-over-co2 {
  color: #fff;
  font-size: 1rem;
  font-weight: bold;
  margin-bottom: 0.4rem;
}

.game-over-comparison,
.game-over-stats {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.75rem;
  margin-top: 0.3rem;
}

.summary-box {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 16px;
  pointer-events: none;
  z-index: 80;
  background: rgba(30, 86, 49, 0.9);
  padding: 6px 20px;
  border-radius: 8px;
  border: 1px solid rgba(76, 175, 80, 0.5);
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  max-width: 90%;
}

.summary-detail {
  color: #c8e6c9;
  font-size: 12px;
  font-family: 'Georgia', 'Times New Roman', serif;
  white-space: nowrap;
}

.summary-comparison {
  color: #a5d6a7;
  font-size: 12px;
  font-family: 'Georgia', 'Times New Roman', serif;
  font-style: italic;
  white-space: nowrap;
}

.summary-trees {
  color: #81c784;
  font-size: 11px;
  font-family: 'Georgia', 'Times New Roman', serif;
  white-space: nowrap;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
