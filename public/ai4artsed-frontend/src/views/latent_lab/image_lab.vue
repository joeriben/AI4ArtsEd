<template>
  <div class="image-lab">
    <!-- Header -->
    <div class="page-header">
      <h2 class="page-title">{{ t('latentLab.imageLab.headerTitle') }}</h2>
      <p class="page-subtitle">{{ t('latentLab.imageLab.headerSubtitle') }}</p>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="setTab(tab.id)"
      >
        <span class="tab-label">{{ t(`latentLab.imageLab.tabs.${tab.id}.label`) }}</span>
        <span class="tab-short">{{ t(`latentLab.imageLab.tabs.${tab.id}.short`) }}</span>
      </button>
    </div>

    <!-- Conditional rendering of sub-components -->
    <DenoisingArchaeology v-if="activeTab === 'archaeology'" />
    <AttentionCartography v-else-if="activeTab === 'attention'" />
    <Surrealizer v-else-if="activeTab === 'fusion'" />
    <FeatureProbing v-else-if="activeTab === 'probing'" />
    <ConceptAlgebra v-else-if="activeTab === 'algebra'" />
    <ComposableDiffusion v-else-if="activeTab === 'composable'" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import DenoisingArchaeology from './denoising_archaeology.vue'
import AttentionCartography from './attention_cartography.vue'
import Surrealizer from '../surrealizer.vue'
import FeatureProbing from './feature_probing.vue'
import ConceptAlgebra from './concept_algebra.vue'
import ComposableDiffusion from './composable_diffusion.vue'

const { t } = useI18n()

type SubTabId = 'archaeology' | 'attention' | 'fusion' | 'probing' | 'algebra' | 'composable'

const STORAGE_KEY = 'latent_lab_image_tab'

const tabs: { id: SubTabId }[] = [
  { id: 'archaeology' },
  { id: 'attention' },
  { id: 'fusion' },
  { id: 'probing' },
  { id: 'algebra' },
  { id: 'composable' },
]

const activeTab = ref<SubTabId>('archaeology')

function setTab(tabId: SubTabId) {
  activeTab.value = tabId
  localStorage.setItem(STORAGE_KEY, tabId)
}

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved && tabs.some(t => t.id === saved)) {
    activeTab.value = saved as SubTabId
  }
})
</script>

<style scoped>
.image-lab {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
  color: #ffffff;
}

.page-header {
  margin-bottom: 2rem;
}

.page-title {
  font-size: 1.4rem;
  font-weight: 300;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}

.page-subtitle {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
}

/* Tab Navigation */
.tab-nav {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
}

.tab-btn {
  flex: 1;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}

.tab-btn.active {
  background: rgba(76, 175, 80, 0.1);
  border-color: rgba(76, 175, 80, 0.4);
  color: #ffffff;
}

.tab-label {
  font-size: 1rem;
  font-weight: 700;
  display: block;
  margin-bottom: 0.3rem;
}

.tab-short {
  font-size: 0.72rem;
  opacity: 0.7;
}
</style>
