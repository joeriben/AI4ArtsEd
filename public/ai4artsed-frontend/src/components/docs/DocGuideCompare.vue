<template>
  <section class="info-section">
    <h3>{{ t('docs.guideCompare.comparisonModesMakingVisible') }}</h3>
    <p>{{ t('docs.guideCompare.generativeAisAlwaysProduce') }}</p>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.guideCompare.languageComparison') }}</h3>
    <p>{{ t('docs.guideCompare.theSamePromptDifferent') }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ t('docs.guideCompare.linguisticBiases') }}</strong>
        <p>{{ t('docs.guideCompare.theLanguageComparisonEnables') }}</p>
      </div>
      <div class="insight-item">
        <strong>{{ t('docs.guideCompare.culturalAssociations') }}</strong>
        <p>{{ t('docs.guideCompare.languageCarriesCulturalLayers') }}</p>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.guideCompare.modelComparison') }}</h3>
    <p>{{ t('docs.guideCompare.differentModelsInterpretSame') }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ t('docs.guideCompare.currentTopModels') }}</strong>
        <p>{{ t('docs.guideCompare.sd35Large') }}</p>
      </div>
      <div class="insight-item">
        <strong>{{ t('docs.guideCompare.historicalComparison') }}</strong>
        <p>{{ t('docs.guideCompare.sd152022') }}</p>
      </div>
    </div>
  </section>

  <!-- Cultural (Un)Known. How the grid is built - which prompt sits in which
       column, what a row is in either row mode. It stood in the surface's own
       note box and moved here word for word: the box carries the matter, the
       help carries the handling. -->
  <section class="info-section">
    <h3>{{ t('docs.guideCompare.culturalUnderstanding') }}</h3>
    <p>{{ t('docs.guideCompare.culturalUnderstandingBody') }}</p>
  </section>

  <!-- Two sections stood here and both had stopped being true: „Temperature
       Comparison" described an instrument that was taken apart, and „System
       Prompt Comparison" listed a Latent Text Lab instrument as a comparison
       mode. The surface that replaced the first has no section yet: a section
       says what the place is, and that text has not been supplied. -->
  <!-- Voices. Der Abschnitt kam hinzu, als die drei Beschreibungen aus den
       Spalten genommen wurden, damit dort Platz fuer die erzeugten Aufnahmen
       ist.

       Die Texte werden aus `compare.voice.kind.*` gelesen und NICHT hierher
       kopiert: es ist wortgleich derselbe Inhalt, er steht in sechs Sprachen,
       und eine zweite Fassung davon waere eine, die irgendwann abweicht. -->
  <section class="info-section">
    <h3>{{ t('docs.guideCompare.voices') }}</h3>
    <p>{{ t('compare.voice.about.title') }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>eSpeak NG (1995)</strong>
        <p>{{ t('compare.voice.kind.espeak') }}</p>
      </div>
      <!-- Piper, back since 2026-09-18; the order is the order of the
           columns, ascending by what can be asked of a machine. -->
      <div class="insight-item">
        <strong>Piper (2022)</strong>
        <p>{{ t('compare.voice.kind.piper') }}</p>
      </div>
      <div class="insight-item">
        <strong>Supertonic 3 (2026)</strong>
        <p>{{ t('compare.voice.kind.supertonic') }}</p>
      </div>
      <div class="insight-item">
        <strong>VoxCPM2 (2026)</strong>
        <p>{{ t('compare.voice.kind.voxcpm') }}</p>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.guideCompare.aiAssistedAnalysis') }}</h3>
    <!-- The line that stood here promised the companion „in all four
         comparison modes". There are five, and the new one does not have it. -->
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ t('docs.guideCompare.notJustSeeingBut') }}</strong>
        <p>{{ t('docs.guideCompare.theComparisonAloneShows') }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.insight-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.75rem;
}

.insight-item {
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border-inline-start: 3px solid rgba(76, 175, 80, 0.3);
}

.insight-item strong {
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.95rem;
}

.insight-item p {
  margin: 0.25rem 0 0 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  line-height: 1.5;
}
</style>
