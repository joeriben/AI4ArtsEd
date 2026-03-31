<template>
  <div
    dir="ltr"
    class="forest-game"
    @click="handleClick"
    @mouseenter="handleMouseEnter"
    @mousemove="handleMouseMove"
    @mouseleave="handleMouseLeave"
  >
    <!-- Sky -->
    <div class="sky" :style="skyStyle">
      <!-- Clouds -->
      <div
        v-for="(cloud, i) in clouds"
        :key="'cloud-' + i"
        class="cloud"
        :style="cloud.style"
      ></div>

      <!-- Flying bird (progress indicator: left to right) -->
      <div class="bird-container" :style="birdStyle">
        <div class="bird"></div>
      </div>
    </div>

    <!-- Ground -->
    <div class="ground"></div>

    <!-- Trees -->
    <div
      v-for="tree in trees"
      :key="tree.id"
      class="tree"
      :class="[`tree-${tree.type}`, { growing: tree.growing }]"
      :style="getTreeStyle(tree)"
    >
      <div class="tree-top"></div>
      <div class="tree-trunk"></div>
    </div>

    <!-- Factories -->
    <div
      v-for="factory in factories"
      :key="factory.id"
      class="factory"
      :style="getFactoryStyle(factory)"
    >
      <div class="factory-body"></div>
      <div class="factory-chimney">
        <div class="smoke" v-for="n in 3" :key="n" :style="{ animationDelay: `${n * 0.3}s` }"></div>
      </div>
    </div>

    <!-- Stats bar -->
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

    <!-- Plant instruction (visible until first tree planted) -->
    <Transition name="fade">
      <div v-if="showInstructions && treesPlanted === 0" class="plant-instruction">
        {{ t('edutainment.forest.clickToPlant') }}
      </div>
    </Transition>

    <!-- Game over (all trees destroyed) -->
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

    <!-- Summary overlay (bottom, styled box, appears after 5s) -->
    <Transition name="fade">
      <div v-if="!gameOver && isShowingSummary" class="summary-box">
        <span class="summary-detail">{{ totalCo2.toFixed(2) }}g CO₂</span>
        <span class="summary-comparison">{{ t('edutainment.forest.comparison', { minutes: treeMinutes }) }}</span>
        <span class="summary-trees">{{ t('edutainment.forest.treesPlanted', { count: treesPlanted }) }}</span>
      </div>
    </Transition>

    <!-- Custom flowerpot cursor -->
    <div v-if="showPotCursor" class="pot-cursor" :style="potCursorStyle">
      <svg width="32" height="48" viewBox="0 0 32 48" xmlns="http://www.w3.org/2000/svg">
        <!-- Seedling (grows from soil during cooldown) -->
        <g :transform="`translate(16, 24) scale(${seedlingGrowth}) translate(-16, -24)`">
          <line x1="16" y1="24" x2="16" y2="6" stroke="#2e7d32" stroke-width="2" stroke-linecap="round" />
          <ellipse cx="11" cy="14" rx="4" ry="2" fill="#4caf50" transform="rotate(-35, 11, 14)" />
          <ellipse cx="21" cy="10" rx="4" ry="2" fill="#66bb6a" transform="rotate(35, 21, 10)" />
          <ellipse cx="16" cy="5" rx="3" ry="4" fill="#43a047" />
        </g>
        <!-- Pot body (trapezoid) -->
        <path d="M7,26 L9,44 L23,44 L25,26 Z" fill="#c1440e" />
        <!-- Pot rim -->
        <rect x="5" y="23" width="22" height="4" rx="1" fill="#d4652a" />
        <!-- Soil -->
        <path d="M8,26 L9,32 L23,32 L24,26 Z" fill="#3e2723" />
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAnimationProgress } from '@/composables/useAnimationProgress'

const { t } = useI18n()

const props = defineProps<{
  progress?: number
  estimatedSeconds?: number
}>()

// ==================== Use Animation Progress Composable ====================
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

// Summary: shows after 5 seconds (when instructions fade), stays visible
const isShowingSummary = computed(() => summaryShown.value)

// Instructions visibility: visible at start, fades after 5 seconds
const showInstructions = ref(true)

// ==================== Tree Types ====================
const TREE_TYPES = ['pine', 'spruce', 'fir', 'oak', 'birch', 'maple', 'willow'] as const
type TreeType = typeof TREE_TYPES[number]

interface Tree {
  id: number
  x: number
  type: TreeType
  scale: number
  growing: boolean
  growthProgress: number
}

interface Factory {
  id: number
  x: number
  y: number
  scale: number
}

// ==================== State ====================
const trees = ref<Tree[]>([])
const factories = ref<Factory[]>([])
const plantCooldown = ref(0)
const treesPlanted = ref(0)
const gameOver = ref(false)
let nextId = 0

// ==================== Custom Cursor ====================
const mouseX = ref(0)
const mouseY = ref(0)
const showPotCursor = ref(false)

function handleMouseMove(event: MouseEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  mouseX.value = event.clientX - rect.left
  mouseY.value = event.clientY - rect.top
}

function handleMouseLeave() {
  showPotCursor.value = false
}

function handleMouseEnter() {
  showPotCursor.value = true
}

const seedlingGrowth = computed(() => {
  if (plantCooldown.value <= 0) return 1
  return 1 - plantCooldown.value
})

const potCursorStyle = computed(() => ({
  left: `${mouseX.value}px`,
  top: `${mouseY.value}px`
}))

// Bird animation (follows internalProgress from composable)
// Updated in game loop instead of separate RAF
const birdProgress = ref(0)

const birdStyle = computed(() => {
  const leftPos = 5 + birdProgress.value * 0.9
  return {
    left: `${leftPos}%`,
    top: `${15 + Math.sin(birdProgress.value * 0.3) * 5}%`
  }
})

// Cached sky style - only recompute when CO2 changes significantly
let cachedSkyStyleCo2 = -1
let cachedSkyStyle: { background: string } | null = null

const skyStyle = computed(() => {
  const co2Rounded = Math.round(totalCo2.value * 10) / 10
  if (cachedSkyStyle && Math.abs(co2Rounded - cachedSkyStyleCo2) < 0.5) {
    return cachedSkyStyle
  }

  cachedSkyStyleCo2 = co2Rounded
  const pollution = Math.min(1, totalCo2.value / 20)
  const r = Math.round(135 - pollution * 80)
  const g = Math.round(206 - pollution * 120)
  const b = Math.round(250 - pollution * 100)
  cachedSkyStyle = {
    background: `linear-gradient(180deg, rgb(${r}, ${g}, ${b}) 0%, rgb(${r + 40}, ${g + 30}, ${b - 20}) 100%)`
  }
  return cachedSkyStyle
})

// Clouds - memoized by cloud count
let cachedCloudCount = -1
let cachedClouds: Array<{ style: Record<string, string | number> }> = []

const clouds = computed(() => {
  const treeCount = trees.value.length
  const factoryCount = factories.value.length

  const pollutionRatio = factoryCount / Math.max(1, treeCount)
  const cloudCount = Math.min(12, Math.floor(pollutionRatio * 8) + Math.floor(factoryCount * 0.8))

  // Only regenerate if count changed
  if (cloudCount === cachedCloudCount && cachedClouds.length > 0) {
    return cachedClouds
  }

  if (cloudCount === 0) {
    cachedCloudCount = 0
    cachedClouds = []
    return []
  }

  cachedCloudCount = cloudCount
  const darkness = Math.min(0.9, pollutionRatio * 0.5)

  cachedClouds = Array.from({ length: cloudCount }, (_, i) => {
    const gray = Math.round(150 - darkness * 100)
    return {
      style: {
        left: `${5 + (i * 17 + i * i * 3) % 90}%`,
        top: `${8 + (i * 11) % 35}%`,
        opacity: 0.4 + darkness * 0.5,
        transform: `scale(${0.5 + (i % 4) * 0.25})`,
        backgroundColor: `rgba(${gray}, ${gray}, ${gray + 10}, ${0.6 + darkness * 0.3})`,
        animationDelay: `${i * 0.7}s`
      }
    }
  })

  return cachedClouds
})

// ==================== Game Logic ====================
let gameLoopInterval: number | null = null

function initForest() {
  trees.value = []
  factories.value = []

  const treeCount = 18 + Math.floor(Math.random() * 8)
  for (let i = 0; i < treeCount; i++) {
    trees.value.push({
      id: nextId++,
      x: 5 + Math.random() * 90,
      type: TREE_TYPES[Math.floor(Math.random() * TREE_TYPES.length)]!,
      scale: 0.6 + Math.random() * 0.8,
      growing: false,
      growthProgress: 1
    })
  }
}

function plantTree(x: number) {
  if (plantCooldown.value > 0 || gameOver.value) return

  // Hit detection based on actual factory width (scales with factory.scale)
  // Factory width ≈ 30 * scale pixels, assuming ~600px container → ~5% * scale
  const nearbyFactory = factories.value.find(f => {
    const hitRadius = 5 * f.scale
    return Math.abs(f.x - x) < hitRadius
  })
  if (nearbyFactory) {
    factories.value = factories.value.filter(f => f.id !== nearbyFactory.id)
  }

  trees.value.push({
    id: nextId++,
    x: x,
    type: TREE_TYPES[Math.floor(Math.random() * TREE_TYPES.length)]!,
    scale: 0.6 + Math.random() * 0.4,
    growing: true,
    growthProgress: 0.35  // Start larger so young trees are visible
  })

  treesPlanted.value++
  plantCooldown.value = 1.0
}

function handleClick(event: MouseEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * 100
  plantTree(x)
}

function gameLoop() {
  if (gameOver.value) return

  const dt = 0.1

  // Update bird position (moved from separate RAF loop)
  const target = internalProgress.value
  const diff = target - birdProgress.value
  if (Math.abs(diff) > 0.01) {
    birdProgress.value += diff * 0.08
  }

  if (plantCooldown.value > 0) {
    plantCooldown.value = Math.max(0, plantCooldown.value - dt)
  }

  for (const tree of trees.value) {
    if (tree.growing && tree.growthProgress < 1) {
      tree.growthProgress = Math.min(1, tree.growthProgress + dt * 0.15)
      if (tree.growthProgress >= 1) {
        tree.growing = false
      }
    }
  }

  // Factory spawn rate based on GPU power
  const factoryRate = (effectivePower.value / 450) * dt * 1.1

  if (Math.random() < factoryRate && factories.value.length < 30) {
    let newX = 10 + Math.random() * 80
    const minDistance = 12
    for (let attempt = 0; attempt < 5; attempt++) {
      const tooClose = factories.value.some(f => Math.abs(f.x - newX) < minDistance)
      if (!tooClose) break
      newX = 10 + Math.random() * 80
    }

    factories.value.push({
      id: nextId++,
      x: newX,
      y: Math.random() * 6,
      scale: 0.45 + Math.random() * 0.65
    })

    const matureTrees = trees.value.filter(t => !t.growing)
    if (matureTrees.length > 0 && Math.random() < 0.7) {
      const treeToRemove = matureTrees[Math.floor(Math.random() * matureTrees.length)]!
      trees.value = trees.value.filter(t => t.id !== treeToRemove.id)
    }
  }

  if (trees.value.length === 0 && factories.value.length > 3) {
    gameOver.value = true
  }
}

// ==================== Styling ====================
function getTreeStyle(tree: Tree) {
  const baseSize = 40 * tree.scale * tree.growthProgress
  return {
    left: `${tree.x}%`,
    bottom: '25%',
    width: `${baseSize}px`,
    height: `${baseSize * 1.5}px`,
    opacity: tree.growthProgress < 0.3 ? 0.5 : 1,
    zIndex: Math.floor(tree.x)
  }
}

function getFactoryStyle(factory: Factory) {
  const baseSize = 30 * factory.scale
  const bottomPos = 18 + (factory.y || 0)
  return {
    left: `${factory.x}%`,
    bottom: `${bottomPos}%`,
    width: `${baseSize}px`,
    height: `${baseSize * 1.2}px`,
    zIndex: Math.floor(100 - factory.y * 10)
  }
}

// ==================== Lifecycle ====================
onMounted(() => {
  initForest()
  // Single game loop handles everything including bird position
  gameLoopInterval = window.setInterval(gameLoop, 100)

  // Hide instructions after 5 seconds (summary appears at same time via composable)
  setTimeout(() => {
    showInstructions.value = false
  }, 5000)
})

onUnmounted(() => {
  if (gameLoopInterval) clearInterval(gameLoopInterval)
})

watch(() => props.progress, (newProgress) => {
  if (newProgress && newProgress > 0 && trees.value.length === 0) {
    initForest()
  }
})
</script>

<style scoped>
.forest-game {
  position: relative;
  width: 100%;
  height: 320px;
  border-radius: 12px;
  overflow: hidden;
  cursor: none;
  user-select: none;
}

.sky {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 75%;
  transition: background 1s ease;
}

.cloud {
  position: absolute;
  width: 50px;
  height: 20px;
  border-radius: 20px;
  transition: opacity 0.5s, background-color 0.5s;
  animation: float-cloud 10s ease-in-out infinite;
}

.cloud::before,
.cloud::after {
  content: '';
  position: absolute;
  background: inherit;
  border-radius: 50%;
}

.cloud::before {
  width: 20px;
  height: 20px;
  top: -10px;
  left: 8px;
}

.cloud::after {
  width: 28px;
  height: 28px;
  top: -14px;
  left: 20px;
}

@keyframes float-cloud {
  0%, 100% { transform: translateX(0) scale(var(--scale, 1)); }
  50% { transform: translateX(15px) scale(calc(var(--scale, 1) * 1.05)); }
}

.ground {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 30%;
  background: linear-gradient(180deg, #5a8f5a 0%, #3d6b3d 50%, #2d4a2d 100%);
}

.tree {
  position: absolute;
  transform: translateX(-50%);
  transition: opacity 0.3s, width 0.3s, height 0.3s;
}

.tree-top {
  width: 100%;
  height: 70%;
  position: relative;
}

.tree-trunk {
  width: 20%;
  height: 35%;
  margin: 0 auto;
  background: linear-gradient(90deg, #5d4037 0%, #8b6914 50%, #5d4037 100%);
  border-radius: 2px;
}

.tree-pine .tree-top { background: none; }
.tree-pine .tree-top::before,
.tree-pine .tree-top::after {
  content: '';
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  border-left: 50% solid transparent;
  border-right: 50% solid transparent;
}
.tree-pine .tree-top::before {
  bottom: 20%;
  border-bottom: 60% solid #2d5a2d;
  width: 80%;
}
.tree-pine .tree-top::after {
  bottom: 0;
  border-bottom: 70% solid #1e4a1e;
  width: 100%;
}

.tree-oak .tree-top {
  background: radial-gradient(ellipse at center, #3d7a3d 0%, #2d5a2d 70%, #1e4a1e 100%);
  border-radius: 50% 50% 40% 40%;
}

.tree-birch .tree-top {
  background: radial-gradient(ellipse at center, #7ab87a 0%, #5a9a5a 60%, #3d7a3d 100%);
  border-radius: 40% 40% 30% 30%;
}
.tree-birch .tree-trunk {
  background: linear-gradient(90deg, #f5f5f5 0%, #e0e0e0 30%, #bdbdbd 50%, #e0e0e0 70%, #f5f5f5 100%);
}

.tree-spruce .tree-top {
  background: none;
  clip-path: polygon(50% 0%, 15% 100%, 85% 100%);
  background: linear-gradient(180deg, #1a4a1a 0%, #2d5a2d 50%, #1e3a1e 100%);
}

.tree-fir .tree-top { background: none; }
.tree-fir .tree-top::before {
  content: '';
  position: absolute;
  bottom: 0;
  left: 10%;
  width: 80%;
  height: 100%;
  background: #1e4a2e;
  clip-path: polygon(50% 0%, 5% 35%, 20% 35%, 0% 70%, 25% 70%, 10% 100%, 90% 100%, 75% 70%, 100% 70%, 80% 35%, 95% 35%);
}

.tree-maple .tree-top {
  background: radial-gradient(ellipse at center, #5a8a4a 0%, #4a7a3a 50%, #3a6a2a 100%);
  border-radius: 45% 45% 40% 40%;
}
.tree-maple .tree-trunk {
  background: linear-gradient(90deg, #6d4c41 0%, #8d6e63 50%, #6d4c41 100%);
}

.tree-willow .tree-top {
  background: radial-gradient(ellipse 60% 80% at center top, #6a9a5a 0%, #4a7a4a 60%, #3a6a3a 100%);
  border-radius: 50% 50% 60% 60%;
  height: 80%;
}
.tree-willow .tree-trunk {
  height: 40%;
  background: linear-gradient(90deg, #5d4037 0%, #795548 50%, #5d4037 100%);
}

.tree.growing {
  animation: sway 2s ease-in-out infinite;
}

@keyframes sway {
  0%, 100% { transform: translateX(-50%) rotate(-1deg); }
  50% { transform: translateX(-50%) rotate(1deg); }
}

.factory {
  position: absolute;
  transform: translateX(-50%);
}

.factory-body {
  width: 100%;
  height: 70%;
  background: linear-gradient(180deg, #616161 0%, #424242 50%, #212121 100%);
  border-radius: 2px 2px 0 0;
}

.factory-chimney {
  position: absolute;
  bottom: 60%;
  left: 30%;
  width: 25%;
  height: 60%;
  background: #757575;
}

.smoke {
  position: absolute;
  bottom: 100%;
  left: 50%;
  width: 15px;
  height: 15px;
  background: rgba(100, 100, 100, 0.6);
  border-radius: 50%;
  animation: rise-smoke 2s ease-out infinite;
}

@keyframes rise-smoke {
  0% {
    transform: translateX(-50%) translateY(0) scale(0.5);
    opacity: 0.7;
  }
  100% {
    transform: translateX(-50%) translateY(-50px) scale(1.5);
    opacity: 0;
  }
}

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
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}

.stat-label {
  font-size: 8px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
}

.stat-value {
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: #fff;
  font-weight: bold;
}

.plant-instruction {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(76, 175, 80, 0.8);
  color: white;
  padding: 6px 14px;
  border-radius: 15px;
  font-size: 12px;
  font-weight: bold;
  transition: background 0.3s;
  min-width: 60px;
  text-align: center;
}

.pot-cursor {
  position: absolute;
  pointer-events: none;
  z-index: 200;
  transform: translate(-50%, -100%);
  filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.4));
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
}

.game-over-text {
  color: #ff5722;
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 8px;
}

.game-over-co2 {
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 6px;
}

.game-over-comparison {
  color: #4CAF50;
  font-size: 13px;
  font-style: italic;
  margin-bottom: 10px;
  max-width: 280px;
}

.game-over-stats {
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
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

/* Fade transition for instructions/summary */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.bird-container {
  position: absolute;
  z-index: 60;
}

.bird {
  background-image: url('https://s3-us-west-2.amazonaws.com/s.cdpn.io/174479/bird-cells.svg');
  background-size: auto 100%;
  width: 88px;
  height: 125px;
  will-change: background-position;
  animation: fly-cycle 1s steps(10) infinite;
  filter: brightness(0) invert(1) drop-shadow(0 0 4px rgba(255, 255, 255, 0.5));
  transform: scale(0.4);
}

@keyframes fly-cycle {
  0% { background-position: 0 0; }
  100% { background-position: -900px 0; }
}
</style>
