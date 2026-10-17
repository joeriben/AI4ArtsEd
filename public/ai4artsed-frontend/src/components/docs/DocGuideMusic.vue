<template>
  <section class="guide-section">
    <h2>{{ t('docs.guideMusic.musicGeneration') }}</h2>

    <div class="concept-card highlight">
      <h3>{{ t('docs.guideMusic.aiGeneratedMusicTags') }}</h3>
      <p>{{ t('docs.guideMusic.musicGenerationWorks') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">1</span>
        <h3>{{ t('docs.guideMusic.chooseTags') }}</h3>
      </div>
      <p>{{ t('docs.guideMusic.tagsDescribeMusicalStyle') }}</p>
      <div class="mode-list">
        <div class="mode-item">
          <strong>Genre</strong>
          <p>{{ t('docs.guideMusic.popRockJazzElectronic') }}</p>
        </div>
        <div class="mode-item">
          <strong>Mood</strong>
          <p>{{ t('docs.guideMusic.happyMelancholicEnergeticCalm') }}</p>
        </div>
        <div class="mode-item">
          <strong>Instrument</strong>
          <p>{{ t('docs.guideMusic.pianoGuitarSynthesizerDrums') }}</p>
        </div>
        <div class="mode-item">
          <strong>{{ t('docs.guideMusic.moreDimensions') }}</strong>
          <p>{{ t('docs.guideMusic.timbreSoundColorGender') }}</p>
        </div>
      </div>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">2</span>
        <h3>{{ t('docs.guideMusic.enterGenerateLyrics') }}</h3>
      </div>
      <p>{{ t('docs.guideMusic.youCanWriteOwn') }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">3</span>
        <h3>{{ t('docs.guideMusic.generateSong') }}</h3>
      </div>
      <p>{{ t('docs.guideMusic.theMusicModelGenerates') }}</p>
    </div>

    <div class="concept-card highlight">
      <h3>{{ t('docs.guideMusic.experimentationTips') }}</h3>
      <p>{{ t('docs.guideMusic.tryContradictoryTag') }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
