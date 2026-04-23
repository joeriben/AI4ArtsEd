<template>
  <Teleport to="body">
    <Transition name="install-toast">
      <div v-if="active" class="install-toast" :class="stateClass">
        <div class="toast-header">
          <span class="toast-title">{{ titleText }}</span>
          <button
            v-if="canDismiss"
            class="toast-dismiss"
            :aria-label="t('compare.shared.install.dismiss')"
            @click="dismiss"
          >×</button>
        </div>

        <div class="toast-model">{{ active.displayLabel }}</div>

        <div v-if="active.currentFile && active.state === 'downloading'" class="toast-file">
          {{ active.currentFile }}
        </div>

        <div v-if="active.state === 'downloading'" class="toast-progress">
          <div class="toast-progress-bar">
            <div class="toast-progress-fill" :style="{ width: progressPct + '%' }"></div>
          </div>
          <div class="toast-progress-text">
            {{ active.doneMb }} / {{ active.totalMb || '?' }} MB
            <span v-if="active.speedMbS > 0.1" class="toast-speed">· {{ active.speedMbS.toFixed(1) }} MB/s</span>
            <span v-if="etaText" class="toast-eta">· {{ etaText }}</span>
          </div>
        </div>

        <div v-else-if="active.state === 'error'" class="toast-error">
          {{ active.errorMessage || t('compare.shared.install.failed') }}
        </div>

        <div v-else-if="active.state === 'done'" class="toast-done">
          {{ t('compare.shared.install.done') }}
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useModelInstall } from '@/composables/useModelInstall'

const { t } = useI18n()
const { active, dismiss } = useModelInstall()

const stateClass = computed(() => {
  if (!active.value) return ''
  return `state-${active.value.state}`
})

const titleText = computed(() => {
  if (!active.value) return ''
  switch (active.value.state) {
    case 'starting': return t('compare.shared.install.starting')
    case 'downloading': return t('compare.shared.install.downloading')
    case 'done': return t('compare.shared.install.done')
    case 'error': return t('compare.shared.install.failed')
    default: return ''
  }
})

const canDismiss = computed(() => {
  return active.value?.state === 'done' || active.value?.state === 'error'
})

const progressPct = computed(() => {
  if (!active.value || !active.value.totalMb) return 0
  return Math.min(100, Math.round((active.value.doneMb / active.value.totalMb) * 100))
})

const etaText = computed(() => {
  if (!active.value) return ''
  const { doneMb, totalMb, speedMbS } = active.value
  if (speedMbS < 0.1 || totalMb === 0) return ''
  const remaining = Math.max(totalMb - doneMb, 0)
  const secs = remaining / speedMbS
  if (secs < 60) return t('compare.shared.install.etaSeconds', { s: Math.round(secs) })
  const mins = Math.round(secs / 60)
  return t('compare.shared.install.etaMinutes', { m: mins })
})
</script>

<style scoped>
.install-toast {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  z-index: 10000;
  min-width: 320px;
  max-width: 420px;
  padding: 0.9rem 1rem;
  background: #181818;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.85rem;
  direction: ltr;
}

.install-toast.state-error {
  border-color: rgba(244, 67, 54, 0.45);
}

.install-toast.state-done {
  border-color: rgba(76, 175, 80, 0.45);
}

.toast-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}

.toast-title {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
}

.toast-dismiss {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  font-size: 1.3rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.25rem;
}

.toast-dismiss:hover {
  color: rgba(255, 255, 255, 0.9);
}

.toast-model {
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.8rem;
  margin-bottom: 0.4rem;
}

.toast-file {
  color: rgba(255, 255, 255, 0.55);
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', monospace;
  margin-bottom: 0.4rem;
}

.toast-progress {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.toast-progress-bar {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.toast-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #81c784);
  transition: width 0.3s ease;
}

.toast-progress-text {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.65);
  font-variant-numeric: tabular-nums;
}

.toast-speed,
.toast-eta {
  margin-left: 0.25rem;
}

.toast-error {
  color: rgba(244, 67, 54, 0.9);
  font-size: 0.78rem;
  line-height: 1.35;
}

.toast-done {
  color: rgba(76, 175, 80, 0.9);
  font-size: 0.8rem;
}

.install-toast-enter-active,
.install-toast-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.install-toast-enter-from,
.install-toast-leave-to {
  transform: translateY(20px);
  opacity: 0;
}
</style>
