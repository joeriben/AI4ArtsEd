<template>
  <div
    ref="bubbleEl"
    :class="['property-bubble', { selected: isSelected, dragging: isDragging }]"
    :style="bubbleStyle"
    :title="tooltip"
    @click="handleClick"
    @mousedown="startDrag"
    @touchstart="startDragTouch"
    :data-property="property"
  >
    <!-- Icon based on property -->
    <span class="property-symbol">
      <!-- Technical Imaging -->
      <svg v-if="property === 'technical_imaging'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="M480-260q75 0 127.5-52.5T660-440q0-75-52.5-127.5T480-620q-75 0-127.5 52.5T300-440q0 75 52.5 127.5T480-260Zm0-80q-42 0-71-29t-29-71q0-42 29-71t71-29q42 0 71 29t29 71q0 42-29 71t-71 29ZM160-120q-33 0-56.5-23.5T80-200v-480q0-33 23.5-56.5T160-760h126l74-80h240l74 80h126q33 0 56.5 23.5T880-680v480q0 33-23.5 56.5T800-120H160Zm0-80h640v-480H638l-73-80H395l-73 80H160v480Zm320-240Z"/>
      </svg>
      <!-- Arts (Kunstgeschichte) -->
      <svg v-else-if="property === 'arts'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="M80-80v-80h80v-360H80v-80l400-280 400 280v80h-80v360h80v80H80Zm160-80h480-480Zm80-80h80v-160l80 120 80-120v160h80v-280h-80l-80 120-80-120h-80v280Zm400 80v-454L480-782 240-614v454h480Z"/>
      </svg>
      <!-- Attitudes (NEW) -->
      <svg v-else-if="property === 'attitudes'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="M360-340h240v-60H360v60Zm-20-280q-32 0-59.5 18T235-556l50 33q10-15 24-25.5t31-10.5q17 0 31 10.5t24 24.5l50-33q-18-27-45.5-45T340-620Zm280 0q-32 0-59.5 18T515-556l50 33q10-14 24-24.5t31-10.5q17 0 31.5 10t23.5 25l50-33q-18-28-45.5-46T620-620ZM480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-400Zm0 320q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Z"/>
      </svg>
      <!-- Critical Analysis -->
      <svg v-else-if="property === 'critical_analysis'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="M350-63q-46 0-82.5-24T211-153q-16 21-40.5 32.5T120-109q-51 0-85.5-35T0-229q0-43 28-77.5T99-346q-14-20-21.5-42.5T70-436q0-40 20.5-75t57.5-57q5 18 13.5 38.5T181-494q-14 11-22 26.5t-8 32.5q0 56 46 69t87 21l19 32q-11 32-19 54.5t-8 40.5q0 30 21.5 52.5T350-143q38 0 63-34t41-80q16-46 24.5-93t13.5-72l78 21q-9 45-22 103t-36.5 110.5Q488-135 449.5-99T350-63ZM120-189q17 0 28.5-11.5T160-229q0-17-11.5-28.5T120-269q-17 0-28.5 11.5T80-229q0 17 11.5 28.5T120-189Zm284-158q-46-41-83.5-76.5t-64.5-69q-27-33.5-41.5-67T200-629q0-65 44.5-109.5T354-783q4 0 7 .5t7 .5q-4-10-6-20t-2-21q0-50 35-85t85-35q50 0 85 35t35 85q0 11-2 20.5t-6 19.5h14q60 0 102 38.5t50 95.5q-18-3-40.5-3t-41.5 2q-7-23-25.5-38T606-703q-35 0-54.5 20.5T498-623h-37q-35-41-54.5-60.5T354-703q-32 0-53 21t-21 53q0 23 13 47.5t36.5 52q23.5 27.5 57 58.5t74.5 67l-57 57Zm76-436q17 0 28.5-11.5T520-823q0-17-11.5-28.5T480-863q-17 0-28.5 11.5T440-823q0 17 11.5 28.5T480-783ZM609-63q-22 0-43.5-6T524-88q11-14 22-33t20-35q11 7 22 10t22 3q32 0 53.5-22.5T685-219q0-19-8-41t-19-54l19-32q42-8 87.5-21t45.5-69q0-40-29.5-58T716-512q-42 0-98 16t-131 41l-21-78q78-25 139-42t112-17q69 0 121 41t52 115q0 25-7.5 47.5T861-346q43 5 71 39.5t28 77.5q0 50-34.5 85T840-109q-26 0-50.5-11.5T749-153q-20 42-56.5 66T609-63Zm232-126q17 0 28-11.5t11-28.5q0-17-11.5-29T840-270q-17 0-28.5 11.5T800-230q0 17 12 29t29 12Zm-721-40Zm360-594Zm360 593Z"/>
      </svg>
      <!-- Semantics -->
      <svg v-else-if="property === 'semantics'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="m440-803-83 83H240v117l-83 83 83 83v117h117l83 83 100-100 168 85-86-167 101-101-83-83v-117H523l-83-83Zm0-113 116 116h164v164l116 116-116 116 115 226q7 13 4 25.5T828-132q-8 8-20.5 11t-25.5-4L556-240 440-124 324-240H160v-164L44-520l116-116v-164h164l116-116Zm0 396Z"/>
      </svg>
      <!-- Research -->
      <svg v-else-if="property === 'research'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="M160-360q-50 0-85-35t-35-85q0-50 35-85t85-35v-80q0-33 23.5-56.5T240-760h120q0-50 35-85t85-35q50 0 85 35t35 85h120q33 0 56.5 23.5T800-680v80q50 0 85 35t35 85q0 50-35 85t-85 35v160q0 33-23.5 56.5T720-120H240q-33 0-56.5-23.5T160-200v-160Zm200-80q25 0 42.5-17.5T420-500q0-25-17.5-42.5T360-560q-25 0-42.5 17.5T300-500q0 25 17.5 42.5T360-440Zm240 0q25 0 42.5-17.5T660-500q0-25-17.5-42.5T600-560q-25 0-42.5 17.5T540-500q0 25 17.5 42.5T600-440ZM320-280h320v-80H320v80Zm-80 80h480v-480H240v480Zm240-240Z"/>
      </svg>
      <!-- Aesthetics/Magic Wand -->
      <svg v-else-if="property === 'aesthetics'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="m176-120-56-56 301-302-181-45 198-123-17-234 179 151 216-88-87 217 151 178-234-16-124 198-45-181-301 301Zm24-520-80-80 80-80 80 80-80 80Zm355 197 48-79 93 7-60-71 35-86-86 35-71-59 7 92-79 49 90 22 23 90Zm165 323-80-80 80-80 80 80-80 80ZM569-570Z"/>
      </svg>
      <!-- Freestyle/YOU -->
      <svg v-else-if="property === 'freestyle'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="m499-287 335-335-52-52-335 335 52 52Zm-261 87q-100-5-149-42T40-349q0-65 53.5-105.5T242-503q39-3 58.5-12.5T320-542q0-26-29.5-39T193-600l7-80q103 8 151.5 41.5T400-542q0 53-38.5 83T248-423q-64 5-96 23.5T120-349q0 35 28 50.5t94 18.5l-4 80Zm280 7L353-358l382-382q20-20 47.5-20t47.5 20l70 70q20 20 20 47.5T900-575L518-193Zm-159 33q-17 4-30-9t-9-30l33-159 165 165-159 33Z"/>
      </svg>
      <!-- Poetry (Materialkollision) -->
      <svg v-else-if="property === 'poetry'" xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
        <path d="M320-160q-33 0-56.5-23.5T240-240v-120h120v-90q-35-2-66.5-15.5T236-506v-44h-46L60-680q36-46 89-65t107-19q27 0 52.5 4t51.5 15v-55h480v520q0 50-35 85t-85 35H320Zm120-200h240v80q0 17 11.5 28.5T720-240q17 0 28.5-11.5T760-280v-440H440v24l240 240v56h-56L510-514l-8 8q-14 14-29.5 25T440-464v104ZM224-630h92v86q12 8 25 11t27 3q23 0 41.5-7t36.5-25l8-8-56-56q-29-29-65-43.5T256-684q-20 0-38 3t-36 9l42 42Zm376 350H320v40h286q-3-9-4.5-19t-1.5-21Zm-280 40v-40 40Z"/>
      </svg>
      <!-- Fallback to emoji if no match -->
      <span v-else>{{ symbol }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

/**
 * PropertyBubble - Individual property bubble component
 *
 * Part of the Phase 1 Property Quadrants interface: symbols, larger icons,
 * draggable.
 */

interface SymbolData {
  symbol: string
  label: string
  tooltip: string
}

interface Props {
  property: string
  color: string
  isSelected: boolean
  x: number  // Now percentage (0-100) instead of pixels
  y: number  // Now percentage (0-100) instead of pixels
  symbolData?: SymbolData  // NEW: Symbol, label, tooltip
}

const props = defineProps<Props>()

const emit = defineEmits<{
  toggle: [property: string]
  updatePosition: [property: string, x: number, y: number]
}>()

const bubbleEl = ref<HTMLElement | null>(null)
const isDragging = ref(false)
const hasDragged = ref(false)  // Track if actual dragging occurred
const touchStartPos = ref({ x: 0, y: 0 })  // Track initial touch position for tap detection

// Symbol and label from symbolData or fallback to i18n
const symbol = computed(() => props.symbolData?.symbol || '')
const label = computed(() => props.symbolData?.label || props.property)
const tooltip = computed(() => props.symbolData?.tooltip || '')

const BUBBLE_SIZE = 'calc(min(70vw, 70vh) * 0.12)'

const bubbleStyle = computed(() => ({
  left: `${props.x}%`,
  top: `${props.y}%`,
  width: BUBBLE_SIZE,
  height: BUBBLE_SIZE,
  '--bubble-color': props.color,
  '--bubble-shadow': props.isSelected ? `0 0 20px ${props.color}` : 'none',
  cursor: isDragging.value ? 'grabbing' : 'grab'
}))

function handleClick(event: MouseEvent) {
  // Prevent toggle if currently dragging or just finished dragging
  if (!isDragging.value && !hasDragged.value) {
    emit('toggle', props.property)
  }
}

// Draggable functionality (now with percentage calculations)
function startDrag(event: MouseEvent) {
  event.preventDefault()
  isDragging.value = true
  hasDragged.value = false  // Reset drag flag

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(event: MouseEvent) {
  if (!isDragging.value || !bubbleEl.value) return

  hasDragged.value = true  // Mark that dragging occurred

  // Get cluster-wrapper (parent container)
  const clusterWrapper = bubbleEl.value.parentElement
  if (!clusterWrapper) return

  const rect = clusterWrapper.getBoundingClientRect()

  // Calculate position relative to cluster-wrapper
  const relativeX = event.clientX - rect.left
  const relativeY = event.clientY - rect.top

  // Convert to percentage (0-100)
  const percentX = (relativeX / rect.width) * 100
  const percentY = (relativeY / rect.height) * 100

  emit('updatePosition', props.property, percentX, percentY)
}

function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)

  // Reset drag flag after short delay to prevent click event
  setTimeout(() => {
    hasDragged.value = false
  }, 100)
}

// Touch event handlers for iPad/mobile support (now with percentage calculations)
function startDragTouch(event: TouchEvent) {
  event.preventDefault()
  isDragging.value = true
  hasDragged.value = false  // Reset drag flag

  const touch = event.touches[0]
  if (!touch) return

  // Store initial touch position for tap detection
  touchStartPos.value = {
    x: touch.clientX,
    y: touch.clientY
  }

  document.addEventListener('touchmove', onDragTouch, { passive: false })
  document.addEventListener('touchend', stopDragTouch)
}

function onDragTouch(event: TouchEvent) {
  if (!isDragging.value || !bubbleEl.value) return
  event.preventDefault() // Prevent scrolling while dragging

  hasDragged.value = true  // Mark that dragging occurred

  const touch = event.touches[0]
  if (!touch) return

  // Get cluster-wrapper (parent container)
  const clusterWrapper = bubbleEl.value.parentElement
  if (!clusterWrapper) return

  const rect = clusterWrapper.getBoundingClientRect()

  // Calculate position relative to cluster-wrapper
  const relativeX = touch.clientX - rect.left
  const relativeY = touch.clientY - rect.top

  // Convert to percentage (0-100)
  const percentX = (relativeX / rect.width) * 100
  const percentY = (relativeY / rect.height) * 100

  emit('updatePosition', props.property, percentX, percentY)
}

function stopDragTouch(event: TouchEvent) {
  isDragging.value = false
  document.removeEventListener('touchmove', onDragTouch)
  document.removeEventListener('touchend', stopDragTouch)

  // Tap detection: if minimal movement, treat as tap/click
  if (!hasDragged.value) {
    const touch = event.changedTouches[0]
    if (touch) {
      const dx = Math.abs(touch.clientX - touchStartPos.value.x)
      const dy = Math.abs(touch.clientY - touchStartPos.value.y)
      const tapThreshold = 10 // pixels

      // If movement is less than threshold, treat as tap
      if (dx < tapThreshold && dy < tapThreshold) {
        emit('toggle', props.property)
      }
    }
  }

  // Reset drag flag after short delay
  setTimeout(() => {
    hasDragged.value = false
  }, 100)
}
</script>

<style scoped>
.property-bubble {
  position: absolute;
  width: 12%;
  aspect-ratio: 1 / 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: rgb(var(--surface-1-rgb) / 0.9);
  border: 2px solid var(--bubble-color);
  border-radius: 50%;
  color: var(--bubble-color);
  font-weight: 400;
  cursor: grab;
  transition: all 0.3s ease;
  user-select: none;
  box-shadow: var(--bubble-shadow);
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.property-symbol {
  width: 60%;
  height: 60%;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.property-symbol svg {
  width: 100%;
  height: 100%;
}

.property-label {
  font-size: 15px;
  white-space: nowrap;
  display: none;  /* Hide labels - icon-only view */
}

.property-bubble:hover:not(.dragging) {
  background: rgb(var(--surface-2-rgb) / 0.95);
  transform: translate(-50%, -50%) scale(1.08);
}

.property-bubble.dragging {
  cursor: grabbing;
  transform: translate(-50%, -50%) scale(1.1);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 1000;
}

.property-bubble.selected {
  background: var(--bubble-color);
  color: #0a0a0a;
  font-weight: 700;
  box-shadow: 0 0 24px var(--bubble-color);
  border-width: 3px;
}

.property-bubble.selected .property-symbol {
  filter: brightness(0.3);
}

.property-bubble.selected .property-label {
  font-weight: 700;
}
</style>
