<!--
  The conditions of use as one text (2026-11-15): the introduction, the
  responsibilities of the course leader and their list, unchanged from the
  page "Usage Agreement" that stood before every page until that day. An
  account with a password agrees to them with its sign-in
  (views/LoginView.vue), and "My area" shows them with the agreement
  (views/AccountView.vue), where the conditions stay readable
  (docs/DEVELOPMENT_DECISIONS.md, 2026-11-15).

  The version of the text is TERMS_VERSION in devserver/my_app/lab/terms.py,
  the date its wording was last changed. A change of the wording gets a new
  date there, and every account agrees again at its next sign-in; "My area"
  then has to show the wording an older agreement was given to, which this
  component does not keep yet.

  The heading and the sentence at the checkbox are the parent's: the sign-in
  asks with the sentence, "My area" quotes it.
-->
<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="usage-terms">
    <p class="usage-terms-text">{{ t('usageAgreement.text') }}</p>
    <h3 class="usage-terms-head">{{ t('usageAgreement.responsibilities.title') }}</h3>
    <ul class="usage-terms-list">
      <li>{{ t('usageAgreement.responsibilities.supervision') }}</li>
      <li>{{ t('usageAgreement.responsibilities.ageAppropriate') }}</li>
      <li>{{ t('usageAgreement.responsibilities.misuse') }}</li>
      <li>{{ t('usageAgreement.responsibilities.context') }}</li>
      <li>{{ t('usageAgreement.responsibilities.noGuarantee') }}</li>
    </ul>
  </div>
</template>

<style scoped>
/* Sizes and spacing of the sketch of 2026-11-14
   (docs/analysis/lieferungen/anmeldung_vereinbarung_skizze_2026-11-14/). */
.usage-terms {
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.85rem;
  line-height: 1.5;
}

.usage-terms-text {
  margin: 0 0 8px;
}

.usage-terms-head {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  margin: 10px 0 4px;
}

.usage-terms-list {
  margin: 0 0 10px;
  padding-inline-start: 18px;
}

.usage-terms-list li {
  margin-bottom: 3px;
}
</style>
