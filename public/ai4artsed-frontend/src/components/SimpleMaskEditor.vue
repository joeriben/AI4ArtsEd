<!--
  DEPRECATED 2025-12-15
  This component is no longer actively used.
  QWEN Image Edit and Flux2 IMG2IMG support text-guided editing without explicit masks.
  Masks are only needed for very precise pixel-level control, which is not required
  for the current kunstpädagogische use cases.

  Kept for reference in case precise mask-based inpainting is needed in the future.
-->
<template>
  <div dir="ltr" class="mask-editor">
    <!-- Header mit Tool-Auswahl -->
    <div class="editor-header">
      <h3>Maske malen</h3>
      <div class="tool-buttons">
        <button
          :class="{ active: currentTool === 'brush' }"
          @click="currentTool = 'brush'"
          title="Pinsel"
        >
          🖌️ Pinsel
        </button>
        <button
          :class="{ active: currentTool === 'eraser' }"
          @click="currentTool = 'eraser'"
          title="Radiergummi"
        >
          Radiergummi
        </button>
      </div>
    </div>

    <!-- Pinselgröße-Slider -->
    <div class="brush-size-control">
      <label>Pinselgröße: {{ brushSize }}px</label>
      <input
        type="range"
        v-model="brushSize"
        min="5"
        max="100"
        step="5"
      />
    </div>

    <!-- Canvas-Container -->
    <div class="canvas-container" ref="containerRef">
      <canvas
        ref="imageCanvas"
        class="background-canvas"
        :width="canvasWidth"
        :height="canvasHeight"
      />
      <canvas
        ref="maskCanvas"
        class="mask-canvas"
        :width="canvasWidth"
        :height="canvasHeight"
        @mousedown="startDrawing"
        @mousemove="draw"
        @mouseup="stopDrawing"
        @mouseleave="stopDrawing"
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="stopDrawing"
      />
    </div>

    <!-- Controls -->
    <div class="editor-controls">
      <button @click="clearMask" class="btn-clear">
        🗑️ Maske löschen
      </button>
      <button @click="handleCancel" class="btn-cancel">
        Abbrechen
      </button>
      <button @click="handleSave" class="btn-save">
        Speichern
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Props {
  imageUrl: string
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: 1024,
  height: 1024
})

const emit = defineEmits<{
  save: [maskBlob: Blob]
  cancel: []
}>()

// Refs
const containerRef = ref<HTMLElement | null>(null)
const imageCanvas = ref<HTMLCanvasElement | null>(null)
const maskCanvas = ref<HTMLCanvasElement | null>(null)

// State
const currentTool = ref<'brush' | 'eraser'>('brush')
const brushSize = ref(20)
const isDrawing = ref(false)
const canvasWidth = ref(props.width)
const canvasHeight = ref(props.height)

// Canvas contexts
let imageCtx: CanvasRenderingContext2D | null = null
let maskCtx: CanvasRenderingContext2D | null = null

onMounted(async () => {
  if (!imageCanvas.value || !maskCanvas.value) return

  imageCtx = imageCanvas.value.getContext('2d', { willReadFrequently: false })
  maskCtx = maskCanvas.value.getContext('2d', { willReadFrequently: false })

  if (!imageCtx || !maskCtx) return

  // Load image
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    if (!imageCtx) return

    // Draw image scaled to canvas
    imageCtx.drawImage(img, 0, 0, canvasWidth.value, canvasHeight.value)
  }
  img.src = props.imageUrl

  // Initialize mask canvas (black background)
  maskCtx.fillStyle = 'black'
  maskCtx.fillRect(0, 0, canvasWidth.value, canvasHeight.value)

  // Set mask opacity for preview
  if (maskCanvas.value) {
    maskCanvas.value.style.opacity = '0.5'
  }
})

function getCanvasCoordinates(event: MouseEvent | Touch): { x: number; y: number } {
  if (!maskCanvas.value) return { x: 0, y: 0 }

  const rect = maskCanvas.value.getBoundingClientRect()
  const scaleX = canvasWidth.value / rect.width
  const scaleY = canvasHeight.value / rect.height

  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY
  }
}

function startDrawing(event: MouseEvent) {
  isDrawing.value = true
  const coords = getCanvasCoordinates(event)
  drawAt(coords.x, coords.y)
}

function draw(event: MouseEvent) {
  if (!isDrawing.value) return
  const coords = getCanvasCoordinates(event)
  drawAt(coords.x, coords.y)
}

function stopDrawing() {
  isDrawing.value = false
}

function handleTouchStart(event: TouchEvent) {
  event.preventDefault()
  const touch = event.touches.item(0)
  if (touch) {
    isDrawing.value = true
    const coords = getCanvasCoordinates(touch)
    drawAt(coords.x, coords.y)
  }
}

function handleTouchMove(event: TouchEvent) {
  event.preventDefault()
  if (!isDrawing.value) return
  const touch = event.touches.item(0)
  if (touch) {
    const coords = getCanvasCoordinates(touch)
    drawAt(coords.x, coords.y)
  }
}

function drawAt(x: number, y: number) {
  if (!maskCtx) return

  maskCtx.globalCompositeOperation =
    currentTool.value === 'brush' ? 'source-over' : 'destination-out'

  maskCtx.fillStyle = 'white'
  maskCtx.beginPath()
  maskCtx.arc(x, y, brushSize.value, 0, Math.PI * 2)
  maskCtx.fill()
}

function clearMask() {
  if (!maskCtx) return

  // Reset to black
  maskCtx.fillStyle = 'black'
  maskCtx.fillRect(0, 0, canvasWidth.value, canvasHeight.value)
}

async function handleSave() {
  if (!maskCanvas.value) return

  // Convert canvas to blob
  maskCanvas.value.toBlob((blob) => {
    if (blob) {
      emit('save', blob)
    }
  }, 'image/png')
}

function handleCancel() {
  emit('cancel')
}
</script>

<style scoped>
.mask-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a1a;
  color: white;
  border-radius: 8px;
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: #2a2a2a;
  border-bottom: 1px solid #404040;
}

.tool-buttons {
  display: flex;
  gap: 0.5rem;
}

.tool-buttons button {
  padding: 0.5rem 1rem;
  background: #333;
  border: 2px solid #555;
  color: white;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
}

.tool-buttons button.active {
  background: #4a9eff;
  border-color: #4a9eff;
}

.brush-size-control {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background: #2a2a2a;
}

.brush-size-control input[type="range"] {
  width: 100%;
}

.canvas-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #1a1a1a;
}

.background-canvas,
.mask-canvas {
  position: absolute;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.background-canvas {
  z-index: 1;
}

.mask-canvas {
  z-index: 2;
  cursor: crosshair;
}

.editor-controls {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  background: #2a2a2a;
  border-top: 1px solid #404040;
  justify-content: flex-end;
}

.editor-controls button {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-clear {
  background: #666;
  color: white;
}

.btn-cancel {
  background: #666;
  color: white;
}

.btn-save {
  background: #4caf50;
  color: white;
}

.btn-save:hover {
  background: #45a049;
}
</style>
