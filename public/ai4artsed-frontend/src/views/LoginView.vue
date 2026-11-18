<!--
  Lab login (P1). Route: /login
  Follows the SettingsAuthModal.vue look (var(--bg-base), white text on dark).
  Two working tabs:
    - Course leader: email/username + password.
    - Participant: the code of a place (2026-09-23), NO password, NO name.
      A device that has entered goes to the start page.
  The page opens on Participant: a device arrives here to type the code of
  its place (the printed slip names /login). A leader's or an admin's page
  that sent its visitor here opens Course leader (2026-09-24).
  Every page but the start page and the legal pages sends its visitor here
  since 2026-11-15 (router/index.ts), and leads back after the sign-in.
  An account with a password agrees to the conditions of use with its
  sign-in (devserver/my_app/lab/terms.py): where it has not
  agreed to the version that stands, the server says so after checking the
  password, and the conditions stand under the password with the checkbox.
  The account is signed in with the agreement. A place agrees to nothing.
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLabAuthStore } from '../stores/labAuth'
import UsageTermsText from '../components/UsageTermsText.vue'
import { formatTermsVersion } from '../lib/termsVersion'
import { keepSignInTab, lastSignInTab } from '../lib/signInTab'

const auth = useLabAuthStore()
const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()

const tab = ref<'educator' | 'participant'>(openingTab())
const identifier = ref('')   // email or username (educator/admin)
const password = ref('')
const code = ref('')         // the code of a place (participant)
const localError = ref<string | null>(null)
/** The checkbox under the conditions of use. */
const agreed = ref(false)

const busy = computed(() => auth.loading)

// A request for the conditions belongs to the sign-in that got it; the page
// opens without one.
auth.termsRequired = null

/** The version of the conditions this account is asked to agree to, as a
 *  date in the reader's language; null while none is asked. */
const termsDate = computed(() =>
  auth.termsRequired === null ? null : formatTermsVersion(auth.termsRequired, locale.value))

// The conditions stand for the account whose password was checked. Another
// name or another password is another sign-in, asked anew.
watch([identifier, password], () => {
  auth.termsRequired = null
  agreed.value = false
})

/** The server's reasons for turning a code or a password away, in the
 *  reader's words. */
const CODE_ERRORS: Record<string, string> = {
  invalid_code: 'auth.codeUnknown',
  access_closed: 'auth.courseClosed',
  published_password: 'auth.passwordPublished',
}

const errorText = computed(() => {
  const raw = auth.error || localError.value
  if (!raw) return null
  // The address has spent its budget of unknown codes; the number is the
  // server's own wait (devserver/my_app/lab/login_attempts.py).
  if (raw === 'too_many_attempts' && auth.retryAfter) {
    return t('auth.codeTooManyAttempts', { n: auth.retryAfter })
  }
  const key = CODE_ERRORS[raw]
  return key ? t(key) : raw
})

/** The tab the page opens on: "Course leader" where the page asked for needs
 *  a leader, else the tab of the last sign-in on this device
 *  (lib/signInTab.ts), else "Participant". */
function openingTab(): 'educator' | 'participant' {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/')) {
    const role = router.resolve(redirect).meta.requiresRole
    if (role === 'educator' || role === 'admin') return 'educator'
  }
  return lastSignInTab() ?? 'participant'
}

/** Where a sign-in leads: the page asked for, or the home of the role. */
function target(): string {
  return (route.query.redirect as string) || defaultHome()
}

// A sign-in that holds again while this page stands (a session the router
// could not read when the page was asked for, read at the next check, or a
// sign-in in another tab) leads on as a sign-in here does.
let submitting = false
watch(() => auth.isAuthenticated, (now, before) => {
  if (now && !before && !submitting) void router.replace(target())
})

async function submit() {
  localError.value = null
  let ok = false
  submitting = true
  try {
    if (tab.value === 'participant') {
      ok = await auth.participantLogin(code.value.trim())
    } else if (auth.termsRequired !== null) {
      if (!agreed.value) return
      ok = await auth.login(identifier.value.trim(), password.value,
        { version: auth.termsRequired, language: locale.value })
    } else {
      ok = await auth.login(identifier.value.trim(), password.value)
    }
  } finally {
    submitting = false
  }
  if (!ok) return
  keepSignInTab(tab.value)
  router.push(target())
}

function defaultHome() {
  if (auth.isEducator) return '/educator'
  if (auth.isParticipant) return '/'
  return '/account'
}

function switchTab(t: 'educator' | 'participant') {
  tab.value = t
  auth.error = null
  auth.termsRequired = null
  agreed.value = false
  localError.value = null
}
</script>

<template>
  <div class="login-page">
    <div class="login-card" :class="{ wide: tab === 'educator' && termsDate !== null }">
      <h1>{{ $t('auth.title') }}</h1>

      <div class="tabs">
        <button :class="{ active: tab === 'educator' }" @click="switchTab('educator')">
          {{ $t('auth.tabEducator') }}
        </button>
        <button :class="{ active: tab === 'participant' }" @click="switchTab('participant')">
          {{ $t('auth.tabParticipant') }}
        </button>
      </div>

      <form v-if="tab === 'educator'" @submit.prevent="submit">
        <label>{{ $t('auth.identifier') }}</label>
        <input v-model="identifier" type="text" autocomplete="username" required />

        <label>{{ $t('auth.password') }}</label>
        <input v-model="password" type="password" autocomplete="current-password" required />

        <section v-if="termsDate !== null" class="terms">
          <p class="terms-pending">{{ $t('auth.termsPending', { date: termsDate }) }}</p>
          <h2>{{ $t('usageAgreement.title') }}</h2>
          <UsageTermsText />
          <label class="terms-check">
            <input v-model="agreed" type="checkbox" />
            <span>{{ $t('usageAgreement.checkbox') }}</span>
          </label>
        </section>

        <p v-if="errorText" class="error">{{ errorText }}</p>

        <button class="primary" type="submit" :disabled="busy || (termsDate !== null && !agreed)">
          {{ busy ? $t('auth.loggingIn') : termsDate !== null ? $t('auth.agreeAndSignIn') : $t('auth.login') }}
        </button>
      </form>

      <form v-else @submit.prevent="submit">
        <label for="place-code">{{ $t('auth.code') }}</label>
        <input id="place-code" v-model="code" type="text" autocomplete="off" autocapitalize="characters"
               spellcheck="false" placeholder="XXXXX" required />

        <p v-if="errorText" class="error">{{ errorText }}</p>

        <button class="primary" type="submit" :disabled="busy">
          {{ busy ? $t('auth.loggingIn') : $t('auth.login') }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
/* Mandatory: page background via var(--bg-base). */
.login-page {
  position: fixed; inset: 0;
  background: var(--bg-base);
  display: flex; align-items: safe center; justify-content: center;
  overflow-y: auto;
  padding: 24px 0;
  color: rgba(255, 255, 255, 0.92);
}
.login-card {
  width: 360px; max-width: 90vw;
  background: var(--bg-base);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px; padding: 28px;
}
/* With the conditions of use the card is wider, and a hairline sets them off
   from the password (the sketch of 2026-11-14). */
.login-card.wide { width: 440px; }
.terms {
  margin-top: 18px; padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}
.terms-pending { font-size: 0.85rem; color: rgba(255, 255, 255, 0.6); margin: 0 0 12px; line-height: 1.5; }
.terms h2 { font-size: 1rem; font-weight: 600; margin: 0 0 6px; }
.terms-check {
  display: flex; align-items: flex-start; gap: 10px;
  margin: 16px 0 0; font-size: 0.9rem; line-height: 1.5;
  color: rgba(255, 255, 255, 0.85); cursor: pointer;
}
.terms-check input { width: 18px; height: 18px; flex: 0 0 auto; margin-top: 2px; accent-color: #4CAF50; }
h1 { font-size: 1.3rem; margin: 0 0 18px; }
.tabs { display: flex; gap: 8px; margin-bottom: 18px; }
.tabs button {
  flex: 1; padding: 8px; border-radius: 8px; cursor: pointer;
  background: transparent; color: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.tabs button.active { color: #fff; border-color: #4CAF50; }
label { display: block; font-size: 0.8rem; margin: 12px 0 4px; color: rgba(255, 255, 255, 0.6); }
input {
  width: 100%; padding: 10px; border-radius: 8px;
  background: var(--surface-1); color: #fff; border: 1px solid rgba(255, 255, 255, 0.15);
}
.primary {
  width: 100%; margin-top: 18px; padding: 11px; border: none; border-radius: 8px;
  background: #4CAF50; color: #fff; font-weight: 700; cursor: pointer;
}
.primary:disabled { opacity: 0.6; cursor: default; }
.error { color: #ff6b6b; font-size: 0.85rem; margin-top: 10px; }
</style>
