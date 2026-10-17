<template>
  <section class="workshop-section">
    <h2>{{ t('docs.workshop.forEducators') }}</h2>

    <div class="workshop-intro">
      <p>{{ t('docs.workshop.theUcdcaeAiLab') }}</p>
    </div>

    <div class="workshop-card">
      <h3>{{ t('docs.workshop.whatPlatformCanDo') }}</h3>
      <ul>
        <li>{{ t('docs.workshop.makeCreativeProcessesVisible') }}</li>
        <li>{{ t('docs.workshop.encourageReflectionDesign') }}</li>
        <li>{{ t('docs.workshop.openAiBlackBox') }}</li>
        <li>{{ t('docs.workshop.provideSpacesCritical') }}</li>
      </ul>
    </div>

    <div class="workshop-card">
      <h3>{{ t('docs.workshop.whatPlatformCannotDo') }}</h3>
      <ul>
        <li>{{ t('docs.workshop.replacePedagogicalGuidance') }}</li>
        <li>{{ t('docs.workshop.automaticallyLeadCritical') }}</li>
        <li>{{ t('docs.workshop.guaranteeBetterImages') }}</li>
      </ul>
    </div>

    <div class="workshop-card">
      <h3>{{ t('docs.workshop.reflectionQuestionsWorkshops') }}</h3>
      <ul class="question-list">
        <li>{{ t('docs.workshop.whyDidModelChoose') }}</li>
        <li>{{ t('docs.workshop.whatIfWeHad') }}</li>
        <li>{{ t('docs.workshop.whoseSignatureDoesImage') }}</li>
        <li>{{ t('docs.workshop.whatSurprisedWhatWas') }}</li>
      </ul>
    </div>

    <div class="workshop-card safety">
      <h3>{{ t('docs.workshop.safetyLevels') }}</h3>
      <p>{{ t('docs.workshop.theSafetySystemAddresses') }}</p>
      <ul>
        <li><strong>{{ t('docs.workshop.kids812') }}</strong> — {{ t('docs.workshop.allFiltersActive86a') }}</li>
        <li><strong>{{ t('docs.workshop.youth1317') }}</strong> — {{ t('docs.workshop.allFiltersActive86a2') }}</li>
        <li><strong>{{ t('docs.workshop.adults') }}</strong> — {{ t('docs.workshop.t86aGdprActiveNo') }}</li>
        <li><strong>{{ t('docs.workshop.research') }}</strong> — {{ t('docs.workshop.noFiltersActiveExclusively') }}</li>
      </ul>
      <p style="margin-top: 8px;"><em>{{ t('docs.workshop.theGdprCheckPersonal') }}</em></p>
      <p style="margin-top: 8px;"><em>{{ t('docs.workshop.importantLlmBasedSafety') }}</em></p>
    </div>

    <div class="workshop-card">
      <h3>{{ t('docs.workshop.llmConfiguration') }}</h3>
      <p>{{ t('docs.workshop.theLanguageModelsUsed') }}</p>
      <ul>
        <li>{{ t('docs.workshop.localModelsFullData') }}</li>
        <li>{{ t('docs.workshop.externalCloudProvidersMore') }}</li>
        <li>{{ t('docs.workshop.gdprCompliantOptionsMistral') }}</li>
      </ul>
    </div>

    <div class="workshop-card installation">
      <h3>{{ t('docs.workshop.installationOperation') }}</h3>
      <p>{{ t('docs.workshop.theUcdcaeAiLab2') }}</p>
      <p><strong>{{ t('docs.workshop.theUseAiCoding') }}</strong> — {{ t('docs.workshop.bothInitialInstallation') }}</p>
    </div>

    <div class="contact-box">
      <h3>{{ t('docs.workshop.contact') }}</h3>
      <p>{{ t('docs.workshop.forQuestionsAboutUse') }}</p>
      <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a>
      <p style="margin-top: 0.5rem">{{ t('docs.workshop.forLicenseInquiriesCommercial') }}</p>
      <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
