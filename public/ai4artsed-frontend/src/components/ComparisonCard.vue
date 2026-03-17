<template>
  <div class="comparison-card" :class="{ active: isExecuting, complete: !!outputImage }">
    <div class="card-header">
      <span class="lang-name">{{ languageName }}</span>
      <span class="lang-code">{{ languageCode }}</span>
      <span v-if="queuePosition > 0" class="queue-badge">{{ queuePosition }}/{{ queueTotal }}</span>
    </div>

    <!-- Prompt display (collapsible) -->
    <div v-if="prompt" class="prompt-section">
      <button class="prompt-toggle" @click="promptExpanded = !promptExpanded">
        <span class="prompt-preview" v-if="!promptExpanded">{{ prompt.slice(0, 60) }}{{ prompt.length > 60 ? '...' : '' }}</span>
        <span class="prompt-preview" v-else>{{ prompt }}</span>
        <span class="prompt-chevron" :class="{ open: promptExpanded }">&#9662;</span>
      </button>
    </div>

    <!-- Generation progress -->
    <div v-if="isExecuting && !outputImage" class="generating-state">
      <div class="progress-bar-track">
        <div class="progress-bar-fill" :class="{ indeterminate: progress <= 0 }" :style="{ width: progress > 0 ? progress + '%' : '100%' }"></div>
      </div>
      <span class="generating-label">{{ t('compare.generating') }}</span>
    </div>

    <!-- Waiting state -->
    <div v-else-if="!outputImage && !isExecuting && queuePosition > 0" class="waiting-state">
      <span class="waiting-label">{{ t('compare.waiting') }}</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="!outputImage && !isExecuting" class="empty-state"></div>

    <!-- Output image -->
    <div v-if="outputImage" class="output-area">
      <img :src="outputImage" alt="" class="comparison-image" />
    </div>

    <!-- Blocked state -->
    <div v-if="blockedReason" class="blocked-state">
      <span class="blocked-icon">&#9888;</span>
      <span class="blocked-text">{{ blockedReason }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

interface Props {
  languageCode: string
  languageName: string
  prompt: string
  outputImage: string | null
  isExecuting: boolean
  progress: number
  queuePosition: number
  queueTotal: number
  blockedReason: string | null
}

withDefaults(defineProps<Props>(), {
  prompt: '',
  outputImage: null,
  isExecuting: false,
  progress: 0,
  queuePosition: 0,
  queueTotal: 0,
  blockedReason: null,
})

const { t } = useI18n()
const promptExpanded = ref(false)
</script>

<style scoped>
.comparison-card {
  background: rgba(20, 20, 20, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.3s ease;
}

.comparison-card.active {
  border-color: rgba(76, 175, 80, 0.4);
}

.comparison-card.complete {
  border-color: rgba(255, 255, 255, 0.12);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.lang-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  flex: 1;
}

.lang-code {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.35);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.queue-badge {
  font-size: 0.65rem;
  color: rgba(255, 183, 77, 0.7);
  background: rgba(255, 183, 77, 0.1);
  padding: 0.1rem 0.4rem;
  border-radius: 8px;
}

/* Prompt section */
.prompt-section {
  padding: 0 0.75rem;
}

.prompt-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.3rem;
  width: 100%;
  background: none;
  border: none;
  padding: 0.4rem 0;
  cursor: pointer;
  text-align: left;
}

.prompt-preview {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  font-family: 'SF Mono', 'Fira Code', monospace;
  line-height: 1.4;
  flex: 1;
  word-break: break-word;
}

.prompt-chevron {
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.3);
  transition: transform 0.2s ease;
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.prompt-chevron.open {
  transform: rotate(180deg);
}

/* States */
.generating-state,
.waiting-state,
.empty-state {
  padding: 2rem 0.75rem;
  text-align: center;
}

.empty-state {
  min-height: 200px;
}

.generating-label,
.waiting-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}

.progress-bar-track {
  height: 2px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 1px;
  margin-bottom: 0.5rem;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: rgba(76, 175, 80, 0.6);
  border-radius: 1px;
  transition: width 0.3s ease;
}

.progress-bar-fill.indeterminate {
  animation: indeterminate 1.5s ease-in-out infinite;
}

@keyframes indeterminate {
  0% { transform: translateX(-100%); width: 30%; }
  50% { transform: translateX(100%); width: 30%; }
  100% { transform: translateX(-100%); width: 30%; }
}

/* Output */
.output-area {
  padding: 0;
}

.comparison-image {
  width: 100%;
  display: block;
  border-radius: 0 0 11px 11px;
}

/* Blocked */
.blocked-state {
  padding: 1rem 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.blocked-icon {
  color: rgba(239, 83, 80, 0.7);
  font-size: 1.1rem;
}

.blocked-text {
  font-size: 0.75rem;
  color: rgba(239, 83, 80, 0.7);
}
</style>
