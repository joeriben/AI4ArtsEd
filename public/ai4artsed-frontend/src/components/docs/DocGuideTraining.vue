<template>
  <section class="info-section">
    <h2>LoRA Training</h2>
    <p>{{ t('docs.guideTraining.theLoraTrainingStudio') }}</p>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">1</span>
        <h3>{{ t('docs.guideTraining.uploadImages') }}</h3>
      </div>
      <p>{{ t('docs.guideTraining.youUploadSetOwn') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">2</span>
        <h3>{{ t('docs.guideTraining.startTraining') }}</h3>
      </div>
      <p>{{ t('docs.guideTraining.trainingTakes13') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">3</span>
        <h3>{{ t('docs.guideTraining.useModel') }}</h3>
      </div>
      <p>{{ t('docs.guideTraining.theTrainedLoraModel') }}</p>
    </div>

    <div class="concept-card">
      <h3>{{ t('docs.guideTraining.whyDoesMatter') }}</h3>
      <p>{{ t('docs.guideTraining.generativeImageModelsClosed') }}</p>
      <p style="margin-top: 0.75rem;">{{ t('docs.guideTraining.loraOpensCrackHere') }}</p>
      <p style="margin-top: 0.75rem;">{{ t('docs.guideTraining.atSameTimeBecomes') }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
