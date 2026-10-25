<template>
  <div dir="ltr" class="pixel-editor-page">
    <h1>Pixel Template Editor</h1>
    <p class="subtitle">Create and edit 14x14 pixel templates for the Bits &amp; Pixels animation</p>

    <div class="editor-layout">
      <!-- Gallery (left) -->
      <div class="gallery-panel">
        <h2>Templates ({{ templateCount }})</h2>
        <button class="btn btn-new" @click="newTemplate">+ New</button>
        <div class="gallery-grid">
          <div
            v-for="(pattern, name) in templates"
            :key="name"
            class="gallery-item"
            :class="{ active: currentName === name }"
            @click="loadTemplate(String(name), pattern as number[][])"
          >
            <canvas
              :ref="(el) => setThumbnailRef(String(name), el as HTMLCanvasElement | null)"
              width="42"
              height="42"
              class="gallery-canvas"
            ></canvas>
            <span class="gallery-label">{{ name }}</span>
            <button
              class="btn-delete"
              @click.stop="deleteTemplate(String(name))"
              title="Delete"
            >&times;</button>
          </div>
        </div>
      </div>

      <!-- Editor Grid (center) -->
      <div class="editor-panel">
        <div
          class="editor-grid"
          @mousedown="startPaint"
          @mousemove="continuePaint"
          @mouseup="stopPaint"
          @mouseleave="stopPaint"
        >
          <div
            v-for="(cell, index) in flatGrid"
            :key="index"
            class="editor-cell"
            :style="cellStyle(cell)"
            :data-index="index"
          ></div>
        </div>
      </div>

      <!-- Tools (right) -->
      <div class="tools-panel">
        <!-- Color Palette -->
        <h3>Palette</h3>
        <div class="palette">
          <div
            v-for="i in 8"
            :key="i - 1"
            class="swatch"
            :class="{ active: activeColor === i - 1 }"
            :style="swatchStyle(i - 1)"
            @click="activeColor = i - 1"
          >
            <span v-if="i === 1" class="eraser-label">x</span>
          </div>
        </div>

        <!-- Template Name -->
        <h3>Name</h3>
        <input
          v-model="currentName"
          class="name-input"
          placeholder="template_name"
          @keydown.enter="saveTemplate"
        />

        <!-- Buttons -->
        <div class="action-buttons">
          <button class="btn btn-save" @click="saveTemplate" :disabled="!currentName">Save</button>
          <button class="btn btn-undo" @click="undo" :disabled="history.length === 0">Undo</button>
          <button class="btn btn-clear" @click="clearGrid">Clear</button>
          <button class="btn btn-export" @click="exportToClipboard">Copy JSON</button>
        </div>

        <!-- Emoji Input -->
        <h3>Emoji Import</h3>
        <div class="emoji-input-row">
          <input
            v-model="emojiInput"
            class="emoji-text-input"
            placeholder="e.g. 🏠"
            @keydown.enter="convertEmoji"
          />
          <button class="btn btn-convert" @click="convertEmoji">Convert</button>
        </div>

        <!-- Image Upload -->
        <h3>Image Import</h3>
        <input
          type="file"
          accept="image/*"
          class="file-input"
          @change="handleImageUpload"
          ref="fileInputRef"
        />

        <!-- Status -->
        <div v-if="statusMessage" class="status-message" :class="statusClass">
          {{ statusMessage }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { tokenColors, GRID_SIZE, MAX_COLOR_INDEX, type PixelPattern } from '@/data/pixelTemplates'
import { apiBase } from '@/services/labApi'

const API_BASE = apiBase()

// ==================== State ====================
const templates = ref<Record<string, PixelPattern>>({})
const grid = ref<PixelPattern>(createEmptyGrid())
const currentName = ref('')
const activeColor = ref(1)
const isPainting = ref(false)
const emojiInput = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const statusMessage = ref('')
const statusClass = ref('')
const history = ref<PixelPattern[]>([])
const thumbnailRefs = ref<Record<string, HTMLCanvasElement | null>>({})

const templateCount = computed(() => Object.keys(templates.value).length)

const flatGrid = computed(() => {
  const flat: number[] = []
  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      flat.push(grid.value[r]?.[c] ?? 0)
    }
  }
  return flat
})

// ==================== Grid helpers ====================

function createEmptyGrid(): PixelPattern {
  return Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(0))
}

function cloneGrid(g: PixelPattern): PixelPattern {
  return g.map(row => [...row])
}

function pushHistory() {
  history.value.push(cloneGrid(grid.value))
  if (history.value.length > 50) history.value.shift()
}

function undo() {
  const prev = history.value.pop()
  if (prev) grid.value = prev
}

function clearGrid() {
  pushHistory()
  grid.value = createEmptyGrid()
}

// ==================== Painting ====================

function getCellIndex(e: MouseEvent): number | null {
  const target = e.target as HTMLElement
  const idx = target.dataset.index
  return idx !== undefined ? parseInt(idx, 10) : null
}

function paintAt(index: number) {
  const row = Math.floor(index / GRID_SIZE)
  const col = index % GRID_SIZE
  if (row >= 0 && row < GRID_SIZE && col >= 0 && col < GRID_SIZE) {
    if (grid.value[row]![col] !== activeColor.value) {
      grid.value[row]![col] = activeColor.value
    }
  }
}

function startPaint(e: MouseEvent) {
  pushHistory()
  isPainting.value = true
  const idx = getCellIndex(e)
  if (idx !== null) paintAt(idx)
}

function continuePaint(e: MouseEvent) {
  if (!isPainting.value) return
  const idx = getCellIndex(e)
  if (idx !== null) paintAt(idx)
}

function stopPaint() {
  isPainting.value = false
}

// ==================== Styles ====================

function cellStyle(colorIndex: number) {
  if (colorIndex === 0) {
    return {
      backgroundColor: '#1a1a2e',
      backgroundImage: 'linear-gradient(45deg, #252540 25%, transparent 25%, transparent 75%, #252540 75%), linear-gradient(45deg, #252540 25%, transparent 25%, transparent 75%, #252540 75%)',
      backgroundSize: '10px 10px',
      backgroundPosition: '0 0, 5px 5px'
    }
  }
  const color = tokenColors[colorIndex - 1] ?? '#888'
  return {
    backgroundColor: color,
    boxShadow: `inset 0 0 4px rgba(255,255,255,0.15)`
  }
}

function swatchStyle(colorIndex: number) {
  if (colorIndex === 0) {
    return { backgroundColor: '#1a1a2e', border: '2px dashed #555' }
  }
  return { backgroundColor: tokenColors[colorIndex - 1] ?? '#888' }
}

// ==================== Thumbnails ====================

function setThumbnailRef(name: string, el: HTMLCanvasElement | null) {
  thumbnailRefs.value[name] = el
}

function renderThumbnail(name: string, pattern: PixelPattern) {
  const canvas = thumbnailRefs.value[name]
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const cellSize = 3 // 14 * 3 = 42px
  ctx.clearRect(0, 0, 42, 42)

  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      const val = pattern[r]?.[c] ?? 0
      if (val === 0) {
        ctx.fillStyle = '#1a1a2e'
      } else {
        ctx.fillStyle = tokenColors[val - 1] ?? '#888'
      }
      ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize)
    }
  }
}

function renderAllThumbnails() {
  nextTick(() => {
    for (const [name, pattern] of Object.entries(templates.value)) {
      renderThumbnail(name, pattern)
    }
  })
}

// ==================== API ====================

async function fetchTemplates() {
  try {
    const res = await fetch(`${API_BASE}/api/dev/pixel-templates`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    templates.value = await res.json()
    renderAllThumbnails()
  } catch (e) {
    showStatus(`Failed to load templates: ${e}`, 'error')
  }
}

async function saveTemplate() {
  if (!currentName.value) return
  try {
    const res = await fetch(`${API_BASE}/api/dev/pixel-templates/${currentName.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern: grid.value })
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    showStatus(`Saved "${currentName.value}"`, 'success')
    await fetchTemplates()
  } catch (e) {
    showStatus(`Save failed: ${e}`, 'error')
  }
}

async function deleteTemplate(name: string) {
  if (!confirm(`Delete template "${name}"?`)) return
  try {
    const res = await fetch(`${API_BASE}/api/dev/pixel-templates/${name}`, {
      method: 'DELETE'
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    showStatus(`Deleted "${name}"`, 'success')
    if (currentName.value === name) {
      currentName.value = ''
      grid.value = createEmptyGrid()
    }
    await fetchTemplates()
  } catch (e) {
    showStatus(`Delete failed: ${e}`, 'error')
  }
}

function loadTemplate(name: string, pattern: PixelPattern) {
  pushHistory()
  currentName.value = name
  grid.value = cloneGrid(pattern)
}

function newTemplate() {
  pushHistory()
  currentName.value = ''
  grid.value = createEmptyGrid()
}

function exportToClipboard() {
  const json = JSON.stringify(grid.value)
  navigator.clipboard.writeText(json).then(() => {
    showStatus('Copied to clipboard', 'success')
  }).catch(() => {
    showStatus('Clipboard copy failed', 'error')
  })
}

// ==================== Emoji / Image Conversion ====================

function quantizeToGrid(imageData: ImageData): PixelPattern {
  // Step 1: Parse palette colors to RGB
  const paletteRGB = tokenColors.map(hex => {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return { r, g, b }
  })

  const result = createEmptyGrid()
  const data = imageData.data

  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      const idx = (r * GRID_SIZE + c) * 4
      const pr = data[idx]!
      const pg = data[idx + 1]!
      const pb = data[idx + 2]!
      const pa = data[idx + 3]!

      // Transparent → 0
      if (pa < 128) {
        result[r]![c] = 0
        continue
      }

      // Find nearest palette color by RGB distance
      let bestDist = Infinity
      let bestIdx = 0
      for (let i = 0; i < paletteRGB.length; i++) {
        const p = paletteRGB[i]!
        const dr = pr - p.r
        const dg = pg - p.g
        const db = pb - p.b
        const dist = dr * dr + dg * dg + db * db
        if (dist < bestDist) {
          bestDist = dist
          bestIdx = i
        }
      }
      result[r]![c] = bestIdx + 1 // 1-based
    }
  }

  return result
}

function renderSourceToGrid(source: HTMLCanvasElement | HTMLImageElement, sourceWidth: number, sourceHeight: number) {
  // 2-stage downsampling: source → 56x56 → 14x14
  const mid = document.createElement('canvas')
  mid.width = 56
  mid.height = 56
  const midCtx = mid.getContext('2d')!
  midCtx.drawImage(source, 0, 0, sourceWidth, sourceHeight, 0, 0, 56, 56)

  const final = document.createElement('canvas')
  final.width = GRID_SIZE
  final.height = GRID_SIZE
  const finalCtx = final.getContext('2d')!
  finalCtx.drawImage(mid, 0, 0, 56, 56, 0, 0, GRID_SIZE, GRID_SIZE)

  const imageData = finalCtx.getImageData(0, 0, GRID_SIZE, GRID_SIZE)
  pushHistory()
  grid.value = quantizeToGrid(imageData)
}

function convertEmoji() {
  const emoji = emojiInput.value.trim()
  if (!emoji) return

  const canvas = document.createElement('canvas')
  canvas.width = 128
  canvas.height = 128
  const ctx = canvas.getContext('2d')!

  ctx.clearRect(0, 0, 128, 128)
  // Canvas text takes no CSS variable, so the platform's typeface is named
  // here in full. It is the same face as everywhere else (--font-sans).
  ctx.font = "100px 'Source Sans 3 Variable', 'Source Sans 3', system-ui, sans-serif"
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(emoji, 64, 68)

  renderSourceToGrid(canvas, 128, 128)
  showStatus(`Converted emoji "${emoji}"`, 'success')
}

function handleImageUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const img = new Image()
  img.onload = () => {
    const canvas = document.createElement('canvas')
    canvas.width = img.width
    canvas.height = img.height
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(img, 0, 0)
    renderSourceToGrid(canvas, img.width, img.height)
    showStatus(`Imported "${file.name}"`, 'success')
  }
  img.src = URL.createObjectURL(file)
}

// ==================== Status ====================

let statusTimeout: ReturnType<typeof setTimeout> | null = null

function showStatus(msg: string, type: 'success' | 'error') {
  statusMessage.value = msg
  statusClass.value = type
  if (statusTimeout) clearTimeout(statusTimeout)
  statusTimeout = setTimeout(() => {
    statusMessage.value = ''
  }, 3000)
}

// ==================== Keyboard shortcuts ====================

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
    e.preventDefault()
    undo()
  }
}

// ==================== Lifecycle ====================

onMounted(() => {
  fetchTemplates()
  document.addEventListener('keydown', handleKeydown)
})

// Watch for template changes to re-render thumbnails
watch(templates, () => {
  renderAllThumbnails()
}, { deep: true })
</script>

<style scoped>
.pixel-editor-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  color: #eee;
  font-family: var(--font-sans);
}

h1 {
  font-size: 1.6em;
  margin-bottom: 4px;
}

.subtitle {
  color: #888;
  margin-bottom: 24px;
  font-size: 0.9em;
}

h2 { font-size: 1.1em; margin: 0 0 8px 0; }
h3 { font-size: 0.95em; margin: 16px 0 6px 0; color: #aaa; }

.editor-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

/* ==================== Gallery ==================== */
.gallery-panel {
  width: 200px;
  flex-shrink: 0;
}

.gallery-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 600px;
  overflow-y: auto;
  padding-right: 4px;
}

.gallery-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
  cursor: pointer;
  background: rgba(255,255,255,0.03);
  border: 1px solid transparent;
  transition: background 0.15s;
  position: relative;
}

.gallery-item:hover { background: rgba(255,255,255,0.08); }
.gallery-item.active { border-color: #4a90e2; background: rgba(74,144,226,0.1); }

.gallery-canvas {
  border-radius: 3px;
  flex-shrink: 0;
  image-rendering: pixelated;
}

.gallery-label {
  font-size: 0.8em;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-delete {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  border: none;
  background: rgba(231, 76, 60, 0.7);
  color: white;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0;
  opacity: 0;
  transition: opacity 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.gallery-item:hover .btn-delete { opacity: 1; }

/* ==================== Editor Grid ==================== */
.editor-panel {
  flex-shrink: 0;
}

.editor-grid {
  display: grid;
  grid-template-columns: repeat(14, 30px);
  grid-template-rows: repeat(14, 30px);
  gap: 1px;
  background: var(--surface-1);
  padding: 2px;
  border-radius: 8px;
  border: 2px solid var(--surface-4);
  cursor: crosshair;
  user-select: none;
}

.editor-cell {
  width: 30px;
  height: 30px;
  border-radius: 2px;
  transition: transform 0.08s;
}

.editor-cell:hover {
  transform: scale(1.1);
  z-index: 10;
}

/* ==================== Tools ==================== */
.tools-panel {
  width: 220px;
  flex-shrink: 0;
}

.palette {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.swatch {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: transform 0.1s, border-color 0.1s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.swatch:hover { transform: scale(1.15); }
.swatch.active { border-color: #fff; transform: scale(1.15); }

.eraser-label {
  color: #666;
  font-size: 14px;
  font-weight: 700;
}

.name-input {
  width: 100%;
  padding: 8px 10px;
  background: #1a1a2e;
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  color: #eee;
  font-size: 0.9em;
  box-sizing: border-box;
}

.action-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: 10px;
}

.btn {
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85em;
  font-weight: 400;
  transition: background 0.15s;
}

.btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.btn-new { background: #2ecc71; color: var(--surface-1); margin-bottom: 10px; width: 100%; }
.btn-new:hover { background: #27ae60; }
.btn-save { background: #3498db; color: white; }
.btn-save:hover:not(:disabled) { background: #2980b9; }
.btn-undo { background: #555; color: white; }
.btn-undo:hover:not(:disabled) { background: #666; }
.btn-clear { background: #e74c3c; color: white; }
.btn-clear:hover { background: #c0392b; }
.btn-export { background: #9b59b6; color: white; }
.btn-export:hover { background: #8e44ad; }
.btn-convert { background: #f39c12; color: var(--surface-1); flex-shrink: 0; }
.btn-convert:hover { background: #e67e22; }

.emoji-input-row {
  display: flex;
  gap: 6px;
}

.emoji-text-input {
  flex: 1;
  padding: 8px 10px;
  background: #1a1a2e;
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  color: #eee;
  font-size: 1.1em;
}

.file-input {
  width: 100%;
  font-size: 0.8em;
  color: #aaa;
}

.file-input::file-selector-button {
  background: #555;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  margin-right: 8px;
}

.status-message {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85em;
}

.status-message.success { background: rgba(46, 204, 113, 0.15); color: #2ecc71; }
.status-message.error { background: rgba(231, 76, 60, 0.15); color: #e74c3c; }

/* ==================== Responsive ==================== */
@media (max-width: 900px) {
  .editor-layout {
    flex-direction: column;
  }

  .gallery-panel {
    width: 100%;
  }

  .gallery-grid {
    flex-direction: row;
    flex-wrap: wrap;
    max-height: none;
  }

  .tools-panel {
    width: 100%;
  }
}
</style>
