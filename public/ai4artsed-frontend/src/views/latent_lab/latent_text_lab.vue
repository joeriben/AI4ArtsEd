<!--
  The Latent Text Lab's six instruments, and nothing else.

  Every one of them brings its own frame (`.lab-main`/`.lab-stage`/`.lab-work`)
  and its own trigger in the frame's bar, so this file only says which one is
  open. Representation Engineering was the last one still written out inline
  here; it moved into its own file on 2026-08-24, with the rebuild, and this
  wrapper lost the model panel, the contrast-pair editor and some 600 lines of
  style along with it.

  Page context is set here only for the instruments that do not set their own —
  Representation Engineering, System Prompts and Model Comparison each own
  theirs, because they have something to put in it.
-->
<template>
  <div class="latent-text-lab" :class="{ 'ltl-grows': activeTab === 'repeng' || activeTab === 'systemprompt' || activeTab === 'systemprompt-models' }">
    <RepresentationEngineering v-if="activeTab === 'repeng'" />

    <!-- Bias-Archaeologie steht seit 2026-08-19 in der Form von Encoder Fusion:
         Band, zwei Flaechen, und die Grafik baut sich auf, waehrend die Antworten
         eintreffen. Eigene Datei, wie Encoder Fusion eine hat. -->
    <BiasArchaeology v-else-if="activeTab === 'bias'" />

    <CoreferenceTest v-else-if="activeTab === 'coref'" />

    <!-- Der Sprachvergleich der Zerlegung. Er loest ein Versprechen ein, das
         die Ueberblickskarte „Tokenisierung und Embedding" seit dem 2026-08-26
         macht: ihr Exkurs zeigt, dass derselbe Satz je nach Sprache verschieden
         viele Token kostet - hier kann man es mit dem eigenen Satz nachpruefen. -->
    <TokenizationComparison v-else-if="activeTab === 'tokens'" />

    <!-- System Prompts, with Randomness. Stood in Compare until 2026-08-22 and
         moved here with ONE temperature for all three columns. It brings its own
         frame, like the others. -->
    <SystemPromptComparison v-else-if="activeTab === 'systemprompt'" />

    <!-- System Prompts with the two axes exchanged (2026-10-27): one system
         prompt for all three columns, a model per column. Its own frame, like
         the others. -->
    <SystemPromptAcrossModels v-else-if="activeTab === 'systemprompt-models'" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import RepresentationEngineering from './representation_engineering.vue'
import BiasArchaeology from './bias_archaeology.vue'
import CoreferenceTest from './coreference_test.vue'
import TokenizationComparison from './tokenization_comparison.vue'
// Kept in views/compare/: what moved is the category, not the folder.
import SystemPromptComparison from '../compare/system_prompt_comparison.vue'
import SystemPromptAcrossModels from './system_prompt_across_models.vue'

const props = defineProps<{ tab: string }>()

type TabId = 'repeng' | 'bias' | 'coref' | 'systemprompt' | 'systemprompt-models' | 'tokens'
// The left column owns the choice; the name stays activeTab so everything that
// hangs off it below reads unchanged.
const activeTab = computed(() => props.tab as TabId)

/** The instruments that say for themselves what stands on them. */
const OWNS_ITS_CONTEXT: TabId[] = ['repeng', 'systemprompt', 'systemprompt-models']

const pageContextStore = usePageContextStore()

// The catalogue (platform_items.json) is keyed to activeViewType, and carries
// what this place says about its own technology.
const pageContext = computed<PageContext | null>(() =>
  OWNS_ITS_CONTEXT.includes(activeTab.value)
    ? null
    : { activeViewType: `latent_text_lab.${activeTab.value}`, pageContent: {} }
)

// After the render, not before it: leaving an instrument that sets its own
// context unmounts it in that render, and its unmount clears the context. Set
// before, the next instrument's context was cleared by the one going, and
// Help stood without one (Representation Engineering, System Prompts and
// Model Comparison, each to any of the other three).
watch(pageContext, (ctx) => {
  if (ctx) pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true, flush: 'post' })

onBeforeUnmount(() => {
  pageContextStore.clearContext()
})
</script>

<style scoped>
/* Each instrument fills the shell with its own frame; this wrapper only holds
   the place. Until 2026-08-24 there was a centred reading column here as well,
   for the one instrument that was written out inline. */
.latent-text-lab {
  height: 100%;
  color: #ffffff;
}

/* Representation Engineering added a row per press and took its height from its
   content until 2026-08-26; the work area (`.shell-main.lab-scroll`) then
   scrolled the whole surface, pairs and axis included. It fills the frame now
   and scrolls its two columns for itself, so what is left here is the height
   that lets it do that. System Prompts came the same way on 2026-09-02, where
   the height had been taken from the WINDOW and the three columns ended 30 px
   below the frame. Model Comparison stands in the same frame. */
.latent-text-lab.ltl-grows {
  height: 100%;
  min-height: 0;
}
</style>
