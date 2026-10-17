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
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLabAuthStore } from '../stores/labAuth'

const auth = useLabAuthStore()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const tab = ref<'educator' | 'participant'>(openingTab())
const identifier = ref('')   // email or username (educator/admin)
const password = ref('')
const code = ref('')         // the code of a place (participant)
const localError = ref<string | null>(null)

const busy = computed(() => auth.loading)

/** The server's reasons for turning a code away, in the reader's words. */
const CODE_ERRORS: Record<string, string> = {
  invalid_code: 'auth.codeUnknown',
  access_closed: 'auth.courseClosed',
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

function openingTab(): 'educator' | 'participant' {
  const redirect = route.query.redirect
  if (typeof redirect !== 'string' || !redirect.startsWith('/')) return 'participant'
  const role = router.resolve(redirect).meta.requiresRole
  return role === 'educator' || role === 'admin' ? 'educator' : 'participant'
}

async function submit() {
  localError.value = null
  let ok = false
  if (tab.value === 'participant') {
    ok = await auth.participantLogin(code.value.trim())
  } else {
    ok = await auth.login(identifier.value.trim(), password.value)
  }
  if (!ok) return
  const redirect = (route.query.redirect as string) || defaultHome()
  router.push(redirect)
}

function defaultHome() {
  if (auth.isEducator) return '/educator'
  if (auth.isParticipant) return '/'
  return '/account'
}

function switchTab(t: 'educator' | 'participant') {
  tab.value = t
  auth.error = null
  localError.value = null
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
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

        <p v-if="errorText" class="error">{{ errorText }}</p>

        <button class="primary" type="submit" :disabled="busy">
          {{ busy ? $t('auth.loggingIn') : $t('auth.login') }}
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
  display: flex; align-items: center; justify-content: center;
  color: rgba(255, 255, 255, 0.92);
}
.login-card {
  width: 360px; max-width: 90vw;
  background: var(--bg-base);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px; padding: 28px;
}
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
