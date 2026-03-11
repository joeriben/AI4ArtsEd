<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  zoomLevel: number
}>()

const emit = defineEmits<{
  'zoom-in': []
  'zoom-out': []
  'zoom-reset': []
  'fit-to-content': []
}>()
</script>

<template>
  <div dir="ltr" class="zoom-controls">
    <button
      class="zoom-btn"
      :title="t('canvas.zoomControls.zoomOut')"
      @click="emit('zoom-out')"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 13H5v-2h14v2z"/>
      </svg>
    </button>

    <button
      class="zoom-btn zoom-level"
      :title="t('canvas.zoomControls.resetZoom')"
      @click="emit('zoom-reset')"
    >
      {{ Math.round(zoomLevel * 100) }}%
    </button>

    <button
      class="zoom-btn"
      :title="t('canvas.zoomControls.zoomIn')"
      @click="emit('zoom-in')"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
      </svg>
    </button>

    <div class="zoom-divider" />

    <button
      class="zoom-btn"
      :title="t('canvas.zoomControls.fitToContent')"
      @click="emit('fit-to-content')"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M3 5v4h2V5h4V3H5c-1.1 0-2 .9-2 2zm2 10H3v4c0 1.1.9 2 2 2h4v-2H5v-4zm14 4h-4v2h4c1.1 0 2-.9 2-2v-4h-2v4zm0-16h-4v2h4v4h2V5c0-1.1-.9-2-2-2z"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
.zoom-controls {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  background: rgba(20, 20, 20, 0.9);
  border: 1px solid #334155;
  border-radius: 8px;
  backdrop-filter: blur(8px);
}

.zoom-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 0.75rem;
  font-weight: 500;
}

.zoom-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.zoom-btn.zoom-level {
  width: auto;
  min-width: 48px;
  padding: 0 6px;
  font-variant-numeric: tabular-nums;
}

.zoom-divider {
  width: 1px;
  height: 20px;
  background: #334155;
  margin: 0 2px;
}
</style>
