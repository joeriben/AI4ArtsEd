<template>
  <section class="info-section">
    <h3>{{ t('docs.guidePersona.developingIdeas') }}</h3>
    <p>{{ t('docs.guidePersona.whatAnswersHereNot') }}</p>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.guidePersona.howDoesWork') }}</h3>
    <div class="step-list">
      <div class="step-item">
        <span class="step-number">1</span>
        <div>
          <strong>{{ t('docs.guidePersona.startDialog') }}</strong>
          <p>{{ t('docs.guidePersona.describeWhatHaveMind') }}</p>
        </div>
      </div>
      <div class="step-item">
        <span class="step-number">2</span>
        <div>
          <strong>{{ t('docs.guidePersona.negotiate') }}</strong>
          <p>{{ t('docs.guidePersona.youCanDisagreeRedirect') }}</p>
        </div>
      </div>
      <div class="step-item">
        <span class="step-number">3</span>
        <div>
          <strong>{{ t('docs.guidePersona.generation') }}</strong>
          <p>{{ t('docs.guidePersona.whenMachineDecidesDialog') }}</p>
        </div>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.guidePersona.whyNotTool') }}</h3>
    <p>{{ t('docs.guidePersona.conventionalAiImageGeneration') }}</p>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.step-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.75rem;
}

.step-item {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.step-number {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(76, 175, 80, 0.15);
  color: #4CAF50;
  font-weight: 700;
  font-size: 0.85rem;
}

.step-item p {
  margin: 0.25rem 0 0 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.95rem;
  line-height: 1.5;
}
</style>
