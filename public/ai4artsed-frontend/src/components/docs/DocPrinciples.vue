<template>
  <section class="concept-section">
    <h2>{{ t('docs.principles.t8PedagogicalPrinciples') }}</h2>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">1</span>
        <h3>{{ t('docs.principles.whatHowSeparation') }}</h3>
      </div>
      <p>{{ t('docs.principles.ideaRulesEnteredSeparately') }}</p>
      <div class="example-box">
        <strong>{{ t('docs.principles.example') }}</strong>
        {{ t('docs.principles.whatTreeHowFrom') }}
      </div>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">2</span>
        <h3>{{ t('docs.principles.promptInterceptionLlmCo') }}</h3>
      </div>
      <p>{{ t('docs.principles.conventionalAiInterfacesTurn') }}</p>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">3</span>
        <h3>{{ t('docs.principles.criticalExploration') }}</h3>
      </div>
      <p>{{ t('docs.principles.howDoDifferentModels') }}</p>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">4</span>
        <h3>{{ t('docs.principles.visibilityProcessing') }}</h3>
      </div>
      <p>{{ t('docs.principles.everyIntermediateStepVisible') }}</p>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">5</span>
        <h3>{{ t('docs.principles.circularity') }}</h3>
      </div>
      <p>{{ t('docs.principles.resultsCanBecomeInputs') }}</p>
      <div class="circularity-chain">
        <span>{{ t('docs.principles.idea') }}</span> →
        <span>{{ t('docs.principles.description') }}</span> →
        <span>{{ t('docs.principles.image') }}</span> →
        <span>{{ t('docs.principles.newIdea') }}</span> → ...
      </div>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">6</span>
        <h3>{{ t('docs.principles.pedagogicalIntegration') }}</h3>
      </div>
      <p>{{ t('docs.principles.thePlatformDesignedPart') }}</p>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">7</span>
        <h3>{{ t('docs.principles.knowledgeAboutWorld') }}</h3>
      </div>
      <p>{{ t('docs.principles.artisticProcessesRequireNot') }}</p>
      <div class="example-box">
        <strong>{{ t('docs.principles.theWikipediaBadgeW') }}</strong>
        {{ t('docs.principles.showsAllResearchAttempts') }}
      </div>
      <div class="tension-box">
        <span class="tension-label">{{ t('docs.principles.invitation') }}</span>
        {{ t('docs.principles.theWikipediaLinksInvite') }}
      </div>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">8</span>
        <h3>{{ t('docs.principles.collaboration') }}</h3>
      </div>
      <p>{{ t('docs.principles.theFavoritesSystemAt') }}</p>
      <div class="example-box">
        <strong>{{ t('docs.principles.personal') }}</strong>
        {{ t('docs.principles.saveMultipleVariationsImage') }}
      </div>
      <div class="example-box">
        <strong>{{ t('docs.principles.collaborative') }}</strong>
        {{ t('docs.principles.seeInterestingWorkFrom') }}
      </div>
      <div class="tension-box">
        <span class="tension-label">{{ t('docs.principles.workshopContext') }}</span>
        {{ t('docs.principles.switchingBetweenMineAll') }}
      </div>
    </div>

    <div class="principle-card">
      <div class="principle-header">
        <span class="principle-number">9</span>
        <h3>{{ t('docs.principles.aVoiceThatIsNoOne') }}</h3>
      </div>
      <p>{{ t('docs.principles.thisPlatformCanSpeak') }}</p>
      <div class="example-box">
        <strong>{{ t('docs.principles.switchingItOff') }}</strong>
        {{ t('docs.principles.theIconInTheMainMenu') }}
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
