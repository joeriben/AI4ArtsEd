<template>
  <div dir="ltr" class="sketch-canvas-wrapper" ref="wrapperRef">
    <!-- Toolbar -->
    <div class="sketch-toolbar">
      <div class="tool-group">
        <button
          class="tool-btn"
          :class="{ active: tool === 'pen' }"
          @click="tool = 'pen'"
          :title="t('sketchCanvas.pen')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M200-200h57l391-391-57-57-391 391v57Zm-80 80v-170l528-527q12-11 26.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T817-647L290-120H120Zm640-584-56-56 56 56Zm-141 85-28-29 57 57-29-28Z"/>
          </svg>
        </button>
        <button
          class="tool-btn"
          :class="{ active: tool === 'eraser' }"
          @click="tool = 'eraser'"
          :title="t('sketchCanvas.eraser')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M690-240h190v80H610l80-80Zm-500 80-85-85q-23-23-23.5-57t22.5-58l440-456q23-24 56.5-24t56.5 23l199 199q23 23 23 57t-23 57L520-160H190Zm296-80 314-322-198-198-442 456 86 86h176l64-22Zm-52-280Z"/>
          </svg>
        </button>
      </div>

      <div class="tool-group brush-sizes">
        <button
          class="size-btn"
          :class="{ active: brushSize === 3 }"
          @click="brushSize = 3"
          :title="t('sketchCanvas.brushSmall')"
        >
          <span class="size-dot size-small"></span>
        </button>
        <button
          class="size-btn"
          :class="{ active: brushSize === 8 }"
          @click="brushSize = 8"
          :title="t('sketchCanvas.brushMedium')"
        >
          <span class="size-dot size-medium"></span>
        </button>
        <button
          class="size-btn"
          :class="{ active: brushSize === 16 }"
          @click="brushSize = 16"
          :title="t('sketchCanvas.brushLarge')"
        >
          <span class="size-dot size-large"></span>
        </button>
      </div>

      <div class="tool-group">
        <button
          class="tool-btn"
          @click="undo"
          :disabled="undoStack.length === 0"
          :title="t('sketchCanvas.undo')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M280-200v-80h284q63 0 109.5-40T720-420q0-60-46.5-100T564-560H312l104 104-56 56-200-200 200-200 56 56-104 104h252q97 0 166.5 63T800-420q0 94-69.5 157T564-200H280Z"/>
          </svg>
        </button>
        <button
          class="tool-btn"
          @click="clearCanvas"
          :disabled="undoStack.length === 0"
          :title="t('sketchCanvas.clear')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z"/>
          </svg>
        </button>
      </div>

      <button
        class="done-btn"
        @click="submitSketch"
        :disabled="undoStack.length === 0 || isUploading"
        :title="t('sketchCanvas.done')"
      >
        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="M382-240 154-468l57-57 171 171 367-367 57 57-424 424Z"/>
        </svg>
        {{ t('sketchCanvas.done') }}
      </button>
    </div>

    <!-- Canvas Area -->
    <div class="canvas-container" ref="containerRef">
      <canvas
        ref="canvasRef"
        :width="canvasWidth"
        :height="canvasHeight"
        @pointerdown="startDrawing"
        @pointermove="continueDrawing"
        @pointerup="finishDrawing"
        @pointerleave="finishDrawing"
        :class="{ drawing: isDrawing, erasing: tool === 'eraser' }"
      />

      <!-- Instruction overlay (shown when canvas is empty) -->
      <div v-if="undoStack.length === 0 && !isDrawing" class="canvas-instructions">
        <span>{{ t('sketchCanvas.drawHere') }}</span>
      </div>

      <!-- Upload spinner overlay -->
      <div v-if="isUploading" class="upload-overlay">
        <div class="spinner-small"></div>
      </div>

      <!-- Preview after upload -->
      <div v-if="uploadedPreview" class="uploaded-preview">
        <img :src="uploadedPreview" alt="Sketch preview" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { uploadImageFile, quickImageSafetyCheck } from '@/composables/useMaterialIntake'

const { t } = useI18n()
const safetyStore = useSafetyEventStore()

// Emits — identical interface to ImageUploadWidget
const emit = defineEmits<{
  'image-uploaded': [data: {
    image_id: string
    image_path: string
    filename: string
    preview_url: string
    upload_info: any
  }]
  'image-removed': []
}>()

// Refs
const wrapperRef = ref<HTMLDivElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWidth = ref(600)
const canvasHeight = ref(400)

// Drawing state
const isDrawing = ref(false)
const tool = ref<'pen' | 'eraser'>('pen')
const brushSize = ref(3)
const undoStack = ref<ImageData[]>([])
const MAX_UNDO = 20

// Upload state
const isUploading = ref(false)
const uploadedPreview = ref<string | null>(null)

/**
 * Save current canvas state to undo stack
 */
function saveSnapshot() {
  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!ctx || !canvas) return

  const snapshot = ctx.getImageData(0, 0, canvas.width, canvas.height)
  undoStack.value.push(snapshot)

  // Trim to max
  if (undoStack.value.length > MAX_UNDO) {
    undoStack.value.shift()
  }
}

/**
 * Undo last stroke
 */
function undo() {
  if (undoStack.value.length === 0) return

  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!ctx || !canvas) return

  undoStack.value.pop()

  const lastSnapshot = undoStack.value[undoStack.value.length - 1]
  if (lastSnapshot) {
    ctx.putImageData(lastSnapshot, 0, 0)
  } else {
    // Back to blank white canvas
    fillWhite(ctx, canvas)
  }
}

/**
 * Clear canvas completely
 */
function clearCanvas() {
  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!ctx || !canvas) return

  fillWhite(ctx, canvas)
  undoStack.value = []

  // If we had uploaded a sketch, signal removal
  if (uploadedPreview.value) {
    uploadedPreview.value = null
    emit('image-removed')
  }
}

/**
 * Fill canvas with white background
 */
function fillWhite(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement) {
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
}

/**
 * Get canvas coordinates from pointer event
 */
function getCanvasPoint(event: PointerEvent): { x: number; y: number } {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }

  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height

  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY
  }
}

/**
 * Start drawing on pointer down
 */
function startDrawing(event: PointerEvent) {
  if (uploadedPreview.value) return // Canvas locked after upload

  isDrawing.value = true

  // Save state before this stroke for undo
  saveSnapshot()

  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!ctx) return

  const point = getCanvasPoint(event)

  ctx.beginPath()
  ctx.moveTo(point.x, point.y)
  ctx.lineWidth = brushSize.value
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  if (tool.value === 'eraser') {
    ctx.strokeStyle = '#ffffff'
  } else {
    ctx.strokeStyle = '#000000'
  }

  // Draw a dot for single clicks
  ctx.lineTo(point.x + 0.1, point.y + 0.1)
  ctx.stroke()

  // Capture pointer for smooth drawing
  ;(event.target as HTMLCanvasElement).setPointerCapture(event.pointerId)
}

/**
 * Continue drawing on pointer move
 */
function continueDrawing(event: PointerEvent) {
  if (!isDrawing.value) return

  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!ctx) return

  const point = getCanvasPoint(event)
  ctx.lineTo(point.x, point.y)
  ctx.stroke()
}

/**
 * Finish drawing on pointer up/leave
 */
function finishDrawing(event: PointerEvent) {
  if (!isDrawing.value) return
  isDrawing.value = false

  // Release pointer capture
  try {
    ;(event.target as HTMLCanvasElement).releasePointerCapture(event.pointerId)
  } catch {
    // Ignore if pointer capture was already released
  }
}

/**
 * Export canvas as PNG blob and upload to server
 */
async function submitSketch() {
  const canvas = canvasRef.value
  if (!canvas || isUploading.value) return

  isUploading.value = true

  try {
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/png')
    })

    if (!blob) {
      console.error('[SketchCanvas] Failed to create blob from canvas')
      isUploading.value = false
      return
    }

    const up = await uploadImageFile(new File([blob], 'sketch.png', { type: 'image/png' }))

    // VLM safety check (same shared path as the board intake)
    const safety = await quickImageSafetyCheck(up.path)
    if (!safety.safe) {
      safetyStore.reportBlock(
        'vlm_input',
        safety.errorMessage || '',
        [],
        safety.vlmDescription,
        // Whether the check judged the drawing or could not run at all.
        safety.operational,
      )
      isUploading.value = false
      return
    }
    if (safety.vlmDescription) safetyStore.reportAnalysis(safety.vlmDescription, true)

    // Show preview and lock canvas
    const previewUrl = canvas.toDataURL('image/png')
    uploadedPreview.value = previewUrl

    emit('image-uploaded', {
      image_id: up.imageId,
      image_path: up.path,
      filename: up.filename ?? 'sketch.png',
      preview_url: previewUrl,
      upload_info: up.raw
    })
  } catch (err) {
    console.error('[SketchCanvas] Upload error:', err)
  } finally {
    isUploading.value = false
  }
}

/**
 * Resize canvas to fit container while preserving content
 */
function resizeCanvas() {
  if (!containerRef.value) return

  const rect = containerRef.value.getBoundingClientRect()
  const newWidth = Math.floor(rect.width)
  const newHeight = Math.max(300, Math.floor(rect.width * 0.667)) // ~3:2 aspect

  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!ctx || !canvas) return

  // Save current content
  let imageData: ImageData | null = null
  if (undoStack.value.length > 0) {
    imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
  }

  canvasWidth.value = newWidth
  canvasHeight.value = newHeight

  // Restore after resize (next tick for DOM update)
  nextTick(() => {
    const c = canvasRef.value
    const cx = c?.getContext('2d')
    if (!cx || !c) return

    fillWhite(cx, c)

    if (imageData) {
      // Create temp canvas with old dimensions, draw onto new
      const tmp = document.createElement('canvas')
      tmp.width = imageData.width
      tmp.height = imageData.height
      tmp.getContext('2d')!.putImageData(imageData, 0, 0)
      cx.drawImage(tmp, 0, 0, tmp.width, tmp.height, 0, 0, c.width, c.height)
    }
  })
}

// Lifecycle
onMounted(() => {
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)

  // Initialize white background
  nextTick(() => {
    const canvas = canvasRef.value
    const ctx = canvas?.getContext('2d')
    if (ctx && canvas) {
      fillWhite(ctx, canvas)
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas)
})
</script>

<style scoped>
.sketch-canvas-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
}

/* Toolbar */
.sketch-toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.tool-group {
  display: flex;
  gap: 0.25rem;
  padding: 0.25rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.15s ease;
}

.tool-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

.tool-btn.active {
  background: rgba(102, 126, 234, 0.3);
  border-color: rgba(102, 126, 234, 0.6);
  color: white;
}

.tool-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.tool-btn svg {
  width: 20px;
  height: 20px;
}

/* Brush Size Buttons */
.brush-sizes {
  gap: 0.35rem;
}

.size-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}

.size-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.size-btn.active {
  background: rgba(102, 126, 234, 0.3);
  border-color: rgba(102, 126, 234, 0.6);
}

.size-dot {
  display: block;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.8);
}

.size-small {
  width: 4px;
  height: 4px;
}

.size-medium {
  width: 8px;
  height: 8px;
}

.size-large {
  width: 14px;
  height: 14px;
}

/* Done Button */
.done-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-inline-start: auto;
  padding: 0.4rem 1rem;
  border: 1px solid rgba(76, 175, 80, 0.5);
  border-radius: 8px;
  background: rgba(76, 175, 80, 0.2);
  color: #81c784;
  font-size: var(--flow-fs-label);
  font-weight: 400;
  cursor: pointer;
  transition: all 0.2s ease;
}

.done-btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.35);
  border-color: rgba(76, 175, 80, 0.7);
}

.done-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.done-btn svg {
  width: 18px;
  height: 18px;
}

/* Canvas Container */
.canvas-container {
  position: relative;
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  overflow: hidden;
  background: #ffffff;
}

canvas {
  display: block;
  width: 100%;
  height: auto;
  cursor: crosshair;
  touch-action: none;
}

canvas.drawing {
  cursor: none;
}

canvas.erasing {
  cursor: cell;
}

/* Instructions Overlay */
.canvas-instructions {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.canvas-instructions span {
  color: rgba(0, 0, 0, 0.3);
  font-size: var(--flow-fs-display);
  font-weight: 400;
  background: rgba(255, 255, 255, 0.8);
  padding: 0.5rem 1rem;
  border-radius: 8px;
}

/* Upload Overlay */
.upload-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.7);
}

.spinner-small {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-top-color: rgba(102, 126, 234, 0.8);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Uploaded Preview */
.uploaded-preview {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
}

.uploaded-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
</style>
