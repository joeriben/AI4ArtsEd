<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MediaOutputBox from '@/components/MediaOutputBox.vue'

const { t } = useI18n()
const router = useRouter()

interface CollectorOutputItem {
  nodeId: string
  nodeType: string
  output: unknown
  error: string | null
  metadata?: {
    config_id?: string
    display_name?: string
    seed?: number
    steps?: number
    cfg?: number
  }
}

// Internal box state: position + size per item
interface BoxState {
  x: number
  y: number
  w: number
  h: number
}

const props = defineProps<{
  items: CollectorOutputItem[]
  isCollapsed: boolean
  highlightedNodeId?: string | null
}>()

const emit = defineEmits<{
  'toggle-collapse': []
  'highlight-node': [nodeId: string]
}>()

// Fullscreen image modal
const fullscreenImage = ref<string | null>(null)

// Box positions/sizes keyed by item index
const boxStates = ref<Map<number, BoxState>>(new Map())
const DEFAULT_W = 360
const DEFAULT_H = 400
const BOX_GAP = 16

// Assign default positions when items change
watch(() => props.items, (items) => {
  items.forEach((_, idx) => {
    if (!boxStates.value.has(idx)) {
      boxStates.value.set(idx, {
        x: BOX_GAP + idx * (DEFAULT_W + BOX_GAP),
        y: BOX_GAP,
        w: DEFAULT_W,
        h: DEFAULT_H
      })
    }
  })
}, { immediate: true })

function getBoxStyle(idx: number) {
  const s = boxStates.value.get(idx)
  if (!s) return {}
  return {
    left: `${s.x}px`,
    top: `${s.y}px`,
    width: `${s.w}px`,
    height: `${s.h}px`
  }
}

// --- Drag to move (on node label) ---
let dragState: { idx: number; offsetX: number; offsetY: number } | null = null

function startDrag(idx: number, e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.closest('.action-btn') || target.closest('button') || target.closest('.box-resize-handle')) return
  const s = boxStates.value.get(idx)
  if (!s) return
  dragState = { idx, offsetX: e.clientX - s.x, offsetY: e.clientY - s.y }
}

function onMouseMove(e: MouseEvent) {
  if (dragState) {
    const s = boxStates.value.get(dragState.idx)
    if (!s) return
    s.x = Math.max(0, e.clientX - dragState.offsetX)
    s.y = Math.max(0, e.clientY - dragState.offsetY)
    return
  }
  if (resizeState) {
    const s = boxStates.value.get(resizeState.idx)
    if (!s) return
    s.w = Math.max(240, resizeState.startW + (e.clientX - resizeState.startX))
    s.h = Math.max(200, resizeState.startH + (e.clientY - resizeState.startY))
  }
}

function onMouseUp() {
  dragState = null
  resizeState = null
}

// --- Resize (on corner handle) ---
let resizeState: { idx: number; startX: number; startY: number; startW: number; startH: number } | null = null

function startBoxResize(idx: number, e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  const s = boxStates.value.get(idx)
  if (!s) return
  resizeState = { idx, startX: e.clientX, startY: e.clientY, startW: s.w, startH: s.h }
}

onMounted(() => {
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})

// --- Drawer resize (top edge) ---
const drawerHeight = ref(520)
const isResizing = ref(false)
const resizeStartY = ref(0)
const resizeStartHeight = ref(0)
const MIN_HEIGHT = 200
const MAX_HEIGHT_RATIO = 0.7

function startDrawerResize(e: MouseEvent) {
  e.preventDefault()
  isResizing.value = true
  resizeStartY.value = e.clientY
  resizeStartHeight.value = drawerHeight.value

  function onMove(e: MouseEvent) {
    const delta = resizeStartY.value - e.clientY
    const maxH = window.innerHeight * MAX_HEIGHT_RATIO
    drawerHeight.value = Math.max(MIN_HEIGHT, Math.min(maxH, resizeStartHeight.value + delta))
  }

  function onUp() {
    isResizing.value = false
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }

  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

const drawerStyle = computed(() => {
  if (props.isCollapsed) return { height: '40px' }
  return { height: `${drawerHeight.value}px` }
})

// --- Data helpers ---

function getOutputUrl(item: CollectorOutputItem): string | null {
  const output = item.output as Record<string, unknown> | null
  if (output && typeof output === 'object' && 'url' in output) {
    return output.url as string
  }
  return null
}

function getMediaType(item: CollectorOutputItem): string {
  const output = item.output as Record<string, unknown> | null
  if (output && typeof output === 'object' && 'media_type' in output) {
    return output.media_type as string
  }
  return 'text'
}

function getTextOutput(item: CollectorOutputItem): string | null {
  if (typeof item.output === 'string') return item.output
  const output = item.output as Record<string, unknown> | null
  if (output && typeof output === 'object' && 'text' in output) {
    return output.text as string
  }
  return null
}

function getSeed(item: CollectorOutputItem): number | null {
  if (item.metadata?.seed != null) return item.metadata.seed
  const output = item.output as Record<string, unknown> | null
  if (output && typeof output === 'object' && 'seed' in output) {
    return output.seed as number
  }
  return null
}

// --- Actions ---

async function handleDownload(item: CollectorOutputItem) {
  const url = getOutputUrl(item)
  if (!url) return
  try {
    const extensions: Record<string, string> = {
      image: 'png', audio: 'wav', video: 'mp4', music: 'mp3', '3d': 'glb'
    }
    const ext = extensions[getMediaType(item)] || 'bin'
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Download failed: ${response.status}`)
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = `canvas_output_${item.nodeId}.${ext}`
    link.click()
    URL.revokeObjectURL(blobUrl)
  } catch (error) {
    console.error('[OutputDrawer] Download error:', error)
  }
}

function handleForward(item: CollectorOutputItem) {
  const url = getOutputUrl(item)
  if (!url || getMediaType(item) !== 'image') return
  const runIdMatch = url.match(/\/api\/media\/image\/(.+)$/)
  localStorage.setItem('i2i_transfer_data', JSON.stringify({
    imageUrl: url,
    runId: runIdMatch ? runIdMatch[1] : null,
    timestamp: Date.now()
  }))
  router.push('/image-transformation')
}

function handlePrint(item: CollectorOutputItem) {
  const url = getOutputUrl(item)
  if (!url) return
  const printWindow = window.open(url, '_blank')
  if (printWindow) {
    printWindow.onload = () => printWindow.print()
  }
}
</script>

<template>
  <div dir="ltr" class="output-drawer" :style="drawerStyle" :class="{ collapsed: isCollapsed }">
    <!-- Drawer resize handle -->
    <div v-if="!isCollapsed" class="resize-handle" @mousedown="startDrawerResize">
      <div class="resize-grip" />
    </div>

    <!-- Header -->
    <div class="drawer-header" @click="emit('toggle-collapse')">
      <div class="header-left">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" class="chevron" :class="{ rotated: !isCollapsed }">
          <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
        </svg>
        <span class="header-title">{{ t('canvas.outputDrawer.title') }}</span>
        <span v-if="items.length > 0" class="item-count">{{ items.length }}</span>
      </div>
    </div>

    <!-- Content: free-positioning area -->
    <div v-if="!isCollapsed" class="drawer-content">
      <div v-if="items.length === 0" class="empty-state">
        {{ t('canvas.outputDrawer.emptyState') }}
      </div>

      <div v-else class="boxes-area">
        <div
          v-for="(item, idx) in items"
          :key="idx"
          class="floating-output-box"
          :class="{ highlighted: item.nodeId === highlightedNodeId, error: !!item.error }"
          :style="getBoxStyle(idx)"
          @mousedown.prevent="startDrag(idx, $event)"
        >
          <!-- Node label (clickable to highlight in canvas) -->
          <div class="box-label" @click="emit('highlight-node', item.nodeId)">
            {{ item.nodeType }}
            <span class="node-id">{{ item.nodeId.split('-').slice(-1)[0] }}</span>
            <span v-if="item.metadata?.config_id" class="meta-config">
              {{ item.metadata.display_name || item.metadata.config_id }}
            </span>
            <span v-if="getSeed(item) != null" class="meta-seed">
              seed: {{ getSeed(item) }}
            </span>
          </div>

          <!-- MediaOutputBox for URL-based media -->
          <div v-if="!item.error && getOutputUrl(item)" class="box-media">
            <MediaOutputBox
              :output-image="getOutputUrl(item)"
              :media-type="getMediaType(item)"
              :is-executing="false"
              :progress="0"
              ui-mode="expert"
              @image-click="fullscreenImage = $event"
              @download="handleDownload(item)"
              @forward="handleForward(item)"
              @print="handlePrint(item)"
            />
          </div>

          <!-- Text-only output -->
          <div v-else-if="!item.error && getTextOutput(item)" class="box-text">
            <div class="text-content">{{ getTextOutput(item) }}</div>
          </div>

          <!-- Error state -->
          <div v-else-if="item.error" class="box-text">
            <div class="error-text">{{ item.error }}</div>
          </div>

          <!-- Resize handle (bottom-right corner) -->
          <div class="box-resize-handle" @mousedown="startBoxResize(idx, $event)" />
        </div>
      </div>
    </div>
  </div>

  <!-- Fullscreen image modal -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="fullscreenImage" class="fullscreen-modal" @click="fullscreenImage = null">
        <img :src="fullscreenImage" alt="" class="fullscreen-image" />
        <button class="close-fullscreen" @click.stop="fullscreenImage = null">&times;</button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.output-drawer {
  background: #0a0a0a;
  border-top: 1px solid #334155;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: height 0.2s ease;
  overflow: hidden;
}

.output-drawer.collapsed {
  height: 40px !important;
}

.resize-handle {
  height: 6px;
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.resize-handle:hover {
  background: rgba(59, 130, 246, 0.2);
}

.resize-grip {
  width: 40px;
  height: 2px;
  background: #475569;
  border-radius: 1px;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  cursor: pointer;
  flex-shrink: 0;
  user-select: none;
}

.drawer-header:hover {
  background: rgba(255, 255, 255, 0.03);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chevron {
  color: #64748b;
  transition: transform 0.2s;
}

.chevron.rotated {
  transform: rotate(180deg);
}

.header-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.item-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: #3b82f6;
  border-radius: 10px;
  font-size: 0.6875rem;
  font-weight: 600;
  color: white;
}

.drawer-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #475569;
  font-size: 0.875rem;
}

/* Free-positioning area for floating boxes */
.boxes-area {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: auto;
}

/* Floating output box — freely movable + resizable */
.floating-output-box {
  position: absolute;
  background: #141414;
  border: 1px solid #1e293b;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  cursor: grab;
  user-select: none;
  z-index: 10;
  transition: border-color 0.2s;
}

.floating-output-box:active {
  cursor: grabbing;
  z-index: 20;
}

.floating-output-box:hover {
  border-color: #334155;
}

.floating-output-box.highlighted {
  border-color: #3b82f6;
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.3);
}

.floating-output-box.error {
  border-color: rgba(239, 68, 68, 0.4);
}

/* Box header label */
.box-label {
  padding: 0.375rem 0.625rem;
  font-size: 0.6875rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-bottom: 1px solid #1e293b;
  flex-shrink: 0;
}

.box-label:hover {
  color: #3b82f6;
}

.node-id {
  font-size: 0.5625rem;
  color: #475569;
  font-weight: 400;
}

.meta-config {
  font-size: 0.5625rem;
  color: #64748b;
  font-weight: 500;
  margin-inline-start: auto;
}

.meta-seed {
  font-size: 0.5rem;
  color: #475569;
  font-variant-numeric: tabular-nums;
}

/* MediaOutputBox container — fills remaining box space */
.box-media {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.box-media :deep(.pipeline-section) {
  width: 100%;
  height: 100%;
}

.box-media :deep(.output-frame) {
  margin: 0;
  height: 100%;
  border-radius: 0;
  border: none;
}

/* Text output */
.box-text {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 0.75rem;
}

.text-content {
  font-size: 0.8125rem;
  color: #e2e8f0;
  line-height: 1.5;
  white-space: pre-wrap;
}

.error-text {
  font-size: 0.8125rem;
  color: #ef4444;
  line-height: 1.5;
}

/* Resize handle — bottom-right corner */
.box-resize-handle {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  z-index: 30;
}

.box-resize-handle::after {
  content: '';
  position: absolute;
  bottom: 3px;
  right: 3px;
  width: 8px;
  height: 8px;
  border-right: 2px solid #475569;
  border-bottom: 2px solid #475569;
}

.box-resize-handle:hover::after {
  border-color: #94a3b8;
}

/* ---------- Fullscreen modal ---------- */

.fullscreen-modal {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}

.fullscreen-image {
  max-width: 95vw;
  max-height: 95vh;
  object-fit: contain;
}

.close-fullscreen {
  position: absolute;
  top: 1rem;
  right: 1.5rem;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 2rem;
  cursor: pointer;
  line-height: 1;
}

.close-fullscreen:hover {
  color: white;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
