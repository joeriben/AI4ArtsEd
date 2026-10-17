<template>
  <section class="canvas-section">
    <div class="canvas-header">
      <svg xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 0 24 24" width="48" fill="currentColor" class="canvas-header-icon">
        <path d="M22 11V3h-7v3H9V3H2v8h7V8h2v10h4v3h7v-8h-7v3h-2V8h2v3z"/>
      </svg>
      <div>
        <h2>{{ t('docs.guideCanvas.canvasWorkflowSystem') }}</h2>
        <p class="section-intro">{{ t('docs.guideCanvas.canvasVisualResearchWorkbench') }}</p>
      </div>
    </div>
    <p class="section-intro" style="opacity: 0.7; font-style: italic;">{{ t('docs.guideCanvas.availableAtAllSafety') }}</p>

    <div class="canvas-card paradigm">
      <h3>{{ t('docs.guideCanvas.exploratoryResearch') }}</h3>
      <p>{{ t('docs.guideCanvas.canvasDesignedCollaborative') }}</p>
    </div>

    <div class="canvas-card interception">
      <h3>{{ t('docs.guideCanvas.promptInterception') }}</h3>
      <p>{{ t('docs.guideCanvas.conventionalAiInterfacesTurn') }}</p>
      <p class="pragmatic-note">{{ t('docs.guideCanvas.pragmaticallyInterceptionAlso') }}</p>
    </div>

    <div class="canvas-card recursive">
      <h3>{{ t('docs.guideCanvas.recursiveReflexiveWorkflows') }}</h3>
      <p>{{ t('docs.guideCanvas.aNoveltyWeDon') }}</p>
      <ul>
        <li>{{ t('docs.guideCanvas.biasesModels') }}</li>
        <li>{{ t('docs.guideCanvas.normativityVsCreativity') }}</li>
        <li>{{ t('docs.guideCanvas.ethicalAssessmentLlmOutputs') }}</li>
        <li>{{ t('docs.guideCanvas.comparativeAnalysesMassOutput') }}</li>
      </ul>
    </div>

    <div class="canvas-card" style="border-left: 3px solid #FF6F00;">
      <h3>{{ t('docs.guideCanvas.multimodality') }}</h3>
      <p>{{ t('docs.guideCanvas.canvasWorkflowsCanConnect') }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
