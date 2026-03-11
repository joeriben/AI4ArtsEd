<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

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

const props = defineProps<{
  items: CollectorOutputItem[]
  isCollapsed: boolean
  highlightedNodeId?: string | null
}>()

const emit = defineEmits<{
  'toggle-collapse': []
  'highlight-node': [nodeId: string]
  'download': [item: CollectorOutputItem]
}>()

// Drag-resize state
const drawerHeight = ref(240)
const isResizing = ref(false)
const resizeStartY = ref(0)
const resizeStartHeight = ref(0)
const MIN_HEIGHT = 120
const MAX_HEIGHT_RATIO = 0.5

function startResize(e: MouseEvent) {
  e.preventDefault()
  isResizing.value = true
  resizeStartY.value = e.clientY
  resizeStartHeight.value = drawerHeight.value

  function onMouseMove(e: MouseEvent) {
    const delta = resizeStartY.value - e.clientY
    const maxH = window.innerHeight * MAX_HEIGHT_RATIO
    drawerHeight.value = Math.max(MIN_HEIGHT, Math.min(maxH, resizeStartHeight.value + delta))
  }

  function onMouseUp() {
    isResizing.value = false
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

const drawerStyle = computed(() => {
  if (props.isCollapsed) return { height: '40px' }
  return { height: `${drawerHeight.value}px` }
})

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

function handleDownload(item: CollectorOutputItem) {
  const url = getOutputUrl(item)
  if (!url) return
  const a = document.createElement('a')
  a.href = url
  a.download = `canvas_output_${item.nodeId}.${getMediaType(item) === 'audio' ? 'wav' : 'png'}`
  a.click()
}
</script>

<template>
  <div dir="ltr" class="output-drawer" :style="drawerStyle" :class="{ collapsed: isCollapsed }">
    <!-- Resize handle -->
    <div v-if="!isCollapsed" class="resize-handle" @mousedown="startResize">
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

    <!-- Content -->
    <div v-if="!isCollapsed" class="drawer-content">
      <div v-if="items.length === 0" class="empty-state">
        {{ t('canvas.outputDrawer.emptyState') }}
      </div>

      <div v-else class="items-scroll">
        <div
          v-for="(item, idx) in items"
          :key="idx"
          class="output-card"
          :class="{ highlighted: item.nodeId === highlightedNodeId, error: !!item.error }"
        >
          <!-- Node label (clickable) -->
          <div class="card-node-label" @click="emit('highlight-node', item.nodeId)">
            {{ item.nodeType }}
            <span class="node-id">{{ item.nodeId.split('-').slice(-1)[0] }}</span>
          </div>

          <!-- Media preview -->
          <div class="card-preview">
            <template v-if="item.error">
              <div class="error-text">{{ item.error }}</div>
            </template>
            <template v-else-if="getOutputUrl(item)">
              <img
                v-if="getMediaType(item) === 'image' || !getMediaType(item)"
                :src="getOutputUrl(item)!"
                class="preview-image"
                :alt="t('canvas.outputDrawer.imageAlt')"
              />
              <audio
                v-else-if="getMediaType(item) === 'audio'"
                :src="getOutputUrl(item)!"
                controls
                class="preview-audio"
              />
              <video
                v-else-if="getMediaType(item) === 'video'"
                :src="getOutputUrl(item)!"
                controls
                class="preview-video"
              />
            </template>
            <template v-else-if="getTextOutput(item)">
              <div class="preview-text">{{ getTextOutput(item)!.slice(0, 200) }}</div>
            </template>
          </div>

          <!-- Attribution info -->
          <div class="card-meta">
            <span v-if="item.metadata?.config_id" class="meta-config">
              {{ item.metadata.display_name || item.metadata.config_id }}
            </span>
            <span v-if="getSeed(item) != null" class="meta-seed">
              seed: {{ getSeed(item) }}
            </span>
          </div>

          <!-- Actions -->
          <div class="card-actions">
            <button
              v-if="getOutputUrl(item)"
              class="action-btn"
              :title="t('canvas.outputDrawer.download')"
              @click="handleDownload(item)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
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

.items-scroll {
  display: flex;
  gap: 0.75rem;
  padding: 0.5rem 1rem 0.75rem;
  overflow-x: auto;
  overflow-y: hidden;
  height: 100%;
  align-items: stretch;
}

.items-scroll::-webkit-scrollbar {
  height: 4px;
}

.items-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.items-scroll::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 2px;
}

.output-card {
  flex-shrink: 0;
  width: 200px;
  background: #141414;
  border: 1px solid #1e293b;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: border-color 0.2s;
}

.output-card:hover {
  border-color: #334155;
}

.output-card.highlighted {
  border-color: #3b82f6;
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.3);
}

.output-card.error {
  border-color: rgba(239, 68, 68, 0.4);
}

.card-node-label {
  padding: 0.375rem 0.625rem;
  font-size: 0.6875rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.375rem;
  border-bottom: 1px solid #1e293b;
}

.card-node-label:hover {
  color: #3b82f6;
}

.node-id {
  font-size: 0.5625rem;
  color: #475569;
  font-weight: 400;
}

.card-preview {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0.375rem;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.preview-audio {
  width: 100%;
  height: 32px;
}

.preview-video {
  max-width: 100%;
  max-height: 100%;
  border-radius: 4px;
}

.preview-text {
  font-size: 0.6875rem;
  color: #94a3b8;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  padding: 0.25rem;
}

.error-text {
  font-size: 0.6875rem;
  color: #ef4444;
  padding: 0.25rem;
}

.card-meta {
  padding: 0.25rem 0.625rem;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  border-top: 1px solid #1e293b;
}

.meta-config {
  font-size: 0.625rem;
  color: #64748b;
  font-weight: 500;
}

.meta-seed {
  font-size: 0.5625rem;
  color: #475569;
  font-variant-numeric: tabular-nums;
}

.card-actions {
  display: flex;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  border-top: 1px solid #1e293b;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #e2e8f0;
}
</style>
