<template>
  <div class="compare-hub-page">
    <div class="tab-toggle-container">
      <div class="tab-toggle">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-btn"
          :class="{ active: activeTab === tab.id }"
          @click="setTab(tab.id)"
        >
          <svg v-if="IMAGE_TABS.has(tab.id)" xmlns="http://www.w3.org/2000/svg" height="16" viewBox="0 -960 960 960" width="16" fill="currentColor" class="tab-icon">
            <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Z"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" height="16" viewBox="0 -960 960 960" width="16" fill="currentColor" class="tab-icon">
            <path d="M320-240h320v-80H320v80Zm0-160h320v-80H320v80ZM240-80q-33 0-56.5-23.5T160-160v-640q0-33 23.5-56.5T240-880h320l240 240v480q0 33-23.5 56.5T720-80H240Zm280-520v-200H240v640h480v-440H520ZM240-800v200-200 640-640Z"/>
          </svg>
          {{ t(`compare.tabs.${tab.id}`) }}
        </button>
      </div>
    </div>

    <KeepAlive>
      <LanguageComparison v-if="activeTab === 'language'" />
      <TemperatureComparison v-else-if="activeTab === 'temperature'" />
      <ModelComparison v-else-if="activeTab === 'model'" />
      <SystemPromptComparison v-else-if="activeTab === 'systemprompt'" />
      <VlmAnalysisComparison v-else-if="activeTab === 'vlm-analysis'" />
      <LlmModelComparison v-else-if="activeTab === 'llm-model'" />
    </KeepAlive>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageComparison from './compare/language_comparison.vue'
import TemperatureComparison from './compare/temperature_comparison.vue'
import ModelComparison from './compare/model_comparison.vue'
import SystemPromptComparison from './compare/system_prompt_comparison.vue'
import VlmAnalysisComparison from './compare/vlm_analysis_comparison.vue'
import LlmModelComparison from './compare/llm_model_comparison.vue'

const { t } = useI18n()

type TabId = 'language' | 'temperature' | 'model' | 'systemprompt' | 'vlm-analysis' | 'llm-model'

const STORAGE_KEY = 'compare_hub_tab'

const IMAGE_TABS = new Set<TabId>(['model', 'language', 'vlm-analysis'])

const tabs: { id: TabId }[] = [
  // Image comparisons
  { id: 'model' },
  { id: 'language' },
  { id: 'vlm-analysis' },
  // Text comparisons
  { id: 'llm-model' },
  { id: 'systemprompt' },
  { id: 'temperature' },
]

const activeTab = ref<TabId>('language')

function setTab(tabId: TabId) {
  activeTab.value = tabId
  localStorage.setItem(STORAGE_KEY, tabId)
}

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved && tabs.some(t => t.id === saved)) {
    activeTab.value = saved as TabId
  }
})
</script>

<style scoped>
.compare-hub-page {
  min-height: 100vh;
  position: relative;
  background: transparent;
}

.tab-toggle-container {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  justify-content: center;
  padding: 1rem 1rem 0.5rem;
  background: inherit;
}

.tab-toggle {
  display: inline-flex;
  gap: 0.2rem;
  padding: 0.25rem;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  border: 1px solid rgba(76, 175, 80, 0.15);
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 1rem;
  font-size: 0.8rem;
  font-weight: 600;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  white-space: nowrap;
}

.tab-icon {
  opacity: 0.6;
  flex-shrink: 0;
}

.tab-btn:hover:not(.active) {
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  background: rgba(76, 175, 80, 0.25);
  color: #4CAF50;
  box-shadow: 0 2px 8px rgba(76, 175, 80, 0.2);
}
</style>
