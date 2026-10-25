<template>
  <section class="info-section">
    <h3>{{ t('docs.welcome.whatUcdcaeAiLab') }}</h3>
    <p>{{ t('docs.welcome.theUcdcaeAiLab') }}</p>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.welcome.whyPlatform') }}</h3>
    <p>{{ t('docs.welcome.generativeAiModelsPowerful') }}</p>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.welcome.culturalSensitivityBiases') }}</h3>
    <p>{{ t('docs.welcome.aCentralProjectGoal') }}</p>
  </section>

  <!-- Project Information -->
  <section class="info-section">
    <h3>{{ t('docs.welcome.theProject') }}</h3>
    <p>{{ t('docs.welcome.aiTransformingSocietyWorld') }}</p>
    <p>{{ t('docs.welcome.aParticipatoryDesignProcess') }}</p>
    <p>
      {{ t('docs.welcome.moreInformation') }}
      <a href="https://kubi-meta.de/ai4artsed" target="_blank" rel="noopener noreferrer">kubi-meta.de/ai4artsed</a>
    </p>
  </section>

  <section class="info-section">
    <h3>{{ t('docs.welcome.team') }}</h3>
    <div class="team-member">
      <div class="team-role">{{ t('docs.welcome.projectLead') }}</div>
      <strong>Prof. Dr. Benjamin Jörissen</strong>
      <p>{{ t('docs.welcome.instituteEducation') }}<br>
      {{ t('docs.welcome.chairEducationFocusCulture') }}<br>
      UNESCO Chair in Digital Culture and Arts in Education</p>
      <p>E-Mail: <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a></p>
    </div>
    <div class="team-member">
      <div class="team-role">{{ t('docs.welcome.researchAssociate') }}</div>
      <strong>Vanessa Baumann</strong>
      <p>{{ t('docs.welcome.instituteEducation2') }}<br>
      {{ t('docs.welcome.chairEducationFocusCulture2') }}<br>
      UNESCO Chair in Digital Culture and Arts in Education</p>
      <p>E-Mail: <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>
    </div>
  </section>

  <section class="info-section funding-section">
    <h3>{{ t('docs.welcome.funded') }}</h3>
    <div class="funding-logo">
      <a href="https://www.bmfsfj.de/" target="_blank" rel="noopener noreferrer">
        <img src="/logos/BMBFSFJ_logo.png" alt="BMBFSFJ" />
      </a>
    </div>
    <div class="project-logos">
      <a href="https://kubi-meta.de/ai4artsed" target="_blank" rel="noopener noreferrer" class="project-logo-link">
        <img src="/logos/ai4artsed_wordmark.png" alt="AI4ArtsEd" class="project-wordmark-img" />
        <img src="/logos/ai4artsed_logo.jpg" alt="" class="project-logo-img" />
      </a>
      <a href="https://comearts.eu" target="_blank" rel="noopener noreferrer">
        <img src="/logos/comearts_logo.jpg" alt="COMeARTS" class="project-logo-img" />
      </a>
    </div>
  </section>

  <section class="info-section contact-welcome">
    <h3>{{ t('docs.welcome.contact') }}</h3>
    <p>{{ t('docs.welcome.askTrShyDirectly') }}<a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.team-member {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
}

.team-role {
  font-size: 0.85rem;
  color: #4CAF50;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.team-member strong {
  color: #ffffff;
  font-size: 1rem;
}

.team-member p {
  margin: 0.25rem 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  line-height: 1.5;
}

.funding-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.funding-logo {
  margin-top: 0.75rem;
  text-align: center;
}

.funding-logo img {
  max-width: 350px;
  width: 100%;
  height: auto;
  background: white;
  padding: 0.75rem;
  border-radius: 8px;
}

.project-logos {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  margin-top: 1rem;
}

.project-logo-img {
  max-height: 50px;
  width: auto;
}

.project-logo-link {
  display: flex;
  align-items: center;
  text-decoration: none;
  gap: 0;
}

.project-wordmark-img {
  max-height: 50px;
  width: auto;
}
</style>
