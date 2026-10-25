<template>
  <section class="guide-section">
    <h2>{{ t('docs.guideFlow.title') }}</h2>

    <div class="concept-card highlight">
      <h3>{{ t('docs.guideFlow.surfaceTitle') }}</h3>
      <p>{{ t('docs.guideFlow.surfaceBody') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">1</span>
        <h3>{{ t('docs.guideFlow.mediumTitle') }}</h3>
      </div>
      <p>{{ t('docs.guideFlow.mediumBody') }}</p>
      <p class="note">{{ t('docs.guideFlow.mediumNote') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">2</span>
        <h3>{{ t('docs.guideFlow.perspectiveTitle') }}</h3>
      </div>
      <p>{{ t('docs.guideFlow.perspectiveBody') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">3</span>
        <h3>{{ t('docs.guideFlow.stagesTitle') }}</h3>
      </div>
      <p>{{ t('docs.guideFlow.stagesBody') }}</p>
      <div class="mode-list">
        <div class="mode-item">
          <strong>{{ t('docs.guideFlow.withAdaption') }}</strong>
          <p>{{ t('docs.guideFlow.withAdaptionBody') }}</p>
        </div>
        <div class="mode-item">
          <strong>{{ t('docs.guideFlow.withoutAdaption') }}</strong>
          <p>{{ t('docs.guideFlow.withoutAdaptionBody') }}</p>
        </div>
      </div>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">4</span>
        <h3>{{ t('docs.guideFlow.stopTitle') }}</h3>
      </div>
      <p>{{ t('docs.guideFlow.stopNote') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">5</span>
        <h3>{{ t('docs.guideFlow.codeTitle') }}</h3>
      </div>
      <p>{{ t('docs.guideFlow.codeBody') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">6</span>
        <h3>{{ t('docs.guideFlow.readingTitle') }}</h3>
      </div>
      <p>{{ t('docs.guideFlow.readingBody') }}</p>
      <p>{{ t('docs.guideFlow.readingFrames') }}</p>
      <p class="note">{{ t('docs.guideFlow.readingLimit') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">7</span>
        <h3>{{ t('docs.guideFlow.wikipediaTitle') }}</h3>
      </div>
      <p>{{ t('docs.guideFlow.wikipediaBody') }}</p>
      <p>{{ t('docs.guideFlow.wikipediaWhy') }}</p>
      <p class="note">{{ t('docs.guideFlow.wikipediaUnchecked') }}</p>
    </div>

    <div class="concept-card highlight">
      <h3>{{ t('docs.guideFlow.circularTitle') }}</h3>
      <p>{{ t('docs.guideFlow.circularBody') }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
