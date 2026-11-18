<!--
  "My area". Route: /account (any signed-in session, places included). The
  menu of the sign-in field in the header leads here (components/SignInField.vue).
  For an account with a password it shows when the account agreed to which
  version of the conditions of use, and their text
  (devserver/my_app/lab/terms.py; docs/DEVELOPMENT_DECISIONS.md, 2026-11-15),
  as in the sketch of 2026-11-14
  (docs/analysis/lieferungen/anmeldung_vereinbarung_skizze_2026-11-14/).
  Page background via var(--bg-base) per rule.
-->
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLabAuthStore } from '../stores/labAuth'
import UsageTermsText from '../components/UsageTermsText.vue'
import { formatAgreedAt, formatTermsVersion } from '../lib/termsVersion'

const auth = useLabAuthStore()
const router = useRouter()
const { locale } = useI18n()

/** The latest agreement, in the reader's language; null for a place. */
const agreement = computed(() => {
  const terms = auth.terms
  if (terms === null) return null
  return {
    at: formatAgreedAt(terms.accepted_at, locale.value),
    version: formatTermsVersion(terms.version, locale.value),
  }
})

// The sign-in itself answers with the account alone; the agreement comes
// with the session (/api/auth/me).
onMounted(() => { void auth.fetchMe() })

async function signOut(): Promise<void> {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="placeholder-page">
    <div class="placeholder-card">
      <h1>{{ $t('account.title') }}</h1>
      <p class="who" v-if="auth.user">
        {{ auth.user.display_name || auth.user.identifier }}
      </p>

      <section v-if="agreement !== null" class="terms">
        <h2>{{ $t('usageAgreement.title') }}</h2>
        <p v-if="agreement.at !== null" class="terms-when">
          {{ $t('account.termsAgreedAt', { date: agreement.at.date, time: agreement.at.time, version: agreement.version }) }}
        </p>
        <UsageTermsText />
        <p class="terms-sentence">
          {{ $t('account.termsAgreedSentence', { sentence: $t('usageAgreement.checkbox') }) }}
        </p>
      </section>

      <button class="ghost" @click="signOut">{{ $t('auth.logout') }}</button>
    </div>
  </div>
</template>

<style scoped>
.placeholder-page {
  position: fixed; inset: 0;
  background: var(--bg-base);
  display: flex; align-items: safe center; justify-content: center;
  overflow-y: auto;
  padding: 24px 0;
  color: rgba(255, 255, 255, 0.92);
}
.placeholder-card {
  width: 520px; max-width: 90vw;
  background: var(--bg-base);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px; padding: 28px;
}
h1 { font-size: 1.3rem; margin: 0 0 8px; }
.who { font-size: 0.9rem; color: rgba(255, 255, 255, 0.6); margin: 0 0 16px; }
.terms {
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding-top: 14px;
  margin: 4px 0 22px;
}
.terms h2 { font-size: 1rem; font-weight: 600; margin: 0 0 6px; }
.terms-when { font-size: 0.85rem; color: rgba(255, 255, 255, 0.6); margin: 0 0 10px; }
.terms-sentence { font-size: 0.85rem; line-height: 1.5; color: rgba(255, 255, 255, 0.85); margin: 10px 0 0; }
.ghost {
  padding: 9px 14px; border-radius: 8px; cursor: pointer;
  background: transparent; color: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
</style>
