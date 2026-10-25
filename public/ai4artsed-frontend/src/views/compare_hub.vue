<!--
  The five comparison instruments, in the frame the Latent Lab holds.

  Which five has changed twice in two days. On 2026-08-22 System Prompts moved
  to the Latent Text Lab and took the one temperature with it, and Randomness
  was taken apart into a surface that varied the guidance scale. On 2026-08-23
  that surface, having failed, was removed outright, and Cultural (Un)Known
  came in from the Image Lab, where it had
  been called Default Census. It is the one instrument here that is not a comparison
  of systems: it compares what ONE model returns to a line of text and to the
  same line with one word added.

  This file used to be a page with a switch of its own: a sticky row of buttons
  above the surface. The left column of the lab is that switch now, for every
  category at once, so the row is gone and the choice arrives as a prop. The
  views underneath are untouched — each one still names itself to the page
  context, so help knows which instrument is open.
-->
<template>
  <div class="compare-hub-page">
    <KeepAlive>
      <LanguageComparison v-if="activeTab === 'language'" />
      <ModelComparison v-else-if="activeTab === 'model'" />
      <CulturalBias v-else-if="activeTab === 'census'" />
      <VlmAnalysisComparison v-else-if="activeTab === 'vlm-analysis'" />
      <VoiceComparison v-else-if="activeTab === 'voice'" />
    </KeepAlive>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import LanguageComparison from './compare/language_comparison.vue'
import ModelComparison from './compare/model_comparison.vue'
// The instrument keeps its file where it was built and its id `census`, which is
// the workshop shorthand the lab switches on. Only what a visitor reads moved.
import CulturalBias from './latent_lab/default_census.vue'
import VlmAnalysisComparison from './compare/vlm_analysis_comparison.vue'
import VoiceComparison from './compare/voice_comparison.vue'

type TabId = 'language' | 'model' | 'census' | 'vlm-analysis' | 'voice'

const props = defineProps<{ tab: string }>()

// The left column owns the choice. The name stays activeTab so the chain of
// v-ifs above reads exactly as it did when the row of buttons wrote it.
const activeTab = computed(() => props.tab as TabId)
</script>

<style scoped>
/* The frame gives this box a height (`.shell-main`, flex: 1) and it has to
   pass that height on, or an instrument written to FILL the work area gets a
   percentage of nothing and grows to its content instead. Measured on
   2026-08-26 at a work area of 667 px: Cultural (Un)Known came out 763 tall
   and Voices 1161, both scrolling the frame instead of standing on one
   screen, although both write `height: 100%` on their own root. Language
   Understanding and Model Comparison were scrolling pages of their own
   until 2026-09-07 and fill the work area since, so all five instruments
   in here now stand on one screen and this box has to pass the height on
   to every one of them. */
.compare-hub-page {
  position: relative;
  height: 100%;
  background: transparent;
}
</style>
