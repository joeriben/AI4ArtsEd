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
          {{ t(`compare.tabs.${tab.id}`) }}
        </button>
      </div>
    </div>

    <LanguageComparison v-if="activeTab === 'language'" />
    <TemperatureComparison v-else-if="activeTab === 'temperature'" />
    <ModelComparison v-else-if="activeTab === 'model'" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageComparison from './compare/language_comparison.vue'
import TemperatureComparison from './compare/temperature_comparison.vue'
import ModelComparison from './compare/model_comparison.vue'

const { t } = useI18n()

type TabId = 'language' | 'temperature' | 'model'

const STORAGE_KEY = 'compare_hub_tab'

const tabs: { id: TabId }[] = [
  { id: 'language' },
  { id: 'temperature' },
  { id: 'model' },
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
