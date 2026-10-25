<template>
  <!-- Every instrument of the Image Lab is now laid out in surfaces under the
       shell's band and fills the work area, so this file is what it says it is:
       the dispatcher that hands the chosen tab its instrument. The narrow
       wrapper the old-design instruments stood in went with the last of them
       (Decomposition, 2026-09-05). -->
  <Surrealizer v-if="activeTab === 'fusion'" />
  <DenoisingArchaeology v-else-if="activeTab === 'archaeology'" />
  <AttentionCartography v-else-if="activeTab === 'attention'" />
  <MeanImages v-else-if="activeTab === 'mean'" />
  <FeatureProbing v-else-if="activeTab === 'probing'" />
  <ConceptAlgebra v-else-if="activeTab === 'algebra'" />
  <ComposableDiffusion v-else-if="activeTab === 'composable'" />
  <FusionWorkbench v-else-if="activeTab === 'workbench'" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DenoisingArchaeology from './denoising_archaeology.vue'
import AttentionCartography from './attention_cartography.vue'
import MeanImages from './mean_images.vue'
import Surrealizer from '../surrealizer.vue'
import FeatureProbing from './feature_probing.vue'
import ConceptAlgebra from './concept_algebra.vue'
import ComposableDiffusion from './composable_diffusion.vue'
import FusionWorkbench from './fusion_workbench.vue'


type SubTabId = 'archaeology' | 'attention' | 'mean' | 'fusion' | 'probing' | 'algebra' | 'composable' | 'workbench'

const props = defineProps<{ tab: string }>()

// The left column owns the choice. The name stays activeTab so the chain of
// v-ifs below — and everything the instruments hang off it — reads unchanged.
const activeTab = computed(() => props.tab as SubTabId)
</script>
