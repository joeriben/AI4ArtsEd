<template>
  <div class="agreement-page">
    <div class="agreement-container">
      <h1>{{ $t('usageAgreement.title') }}</h1>
      <p class="agreement-text">{{ $t('usageAgreement.text') }}</p>

      <h2>{{ $t('usageAgreement.responsibilities.title') }}</h2>
      <ul class="responsibilities-list">
        <li>{{ $t('usageAgreement.responsibilities.supervision') }}</li>
        <li>{{ $t('usageAgreement.responsibilities.ageAppropriate') }}</li>
        <li>{{ $t('usageAgreement.responsibilities.misuse') }}</li>
        <li>{{ $t('usageAgreement.responsibilities.context') }}</li>
        <li>{{ $t('usageAgreement.responsibilities.noGuarantee') }}</li>
      </ul>

      <div class="agreement-action">
        <label class="agreement-checkbox">
          <input type="checkbox" v-model="agreed" />
          <span>{{ $t('usageAgreement.checkbox') }}</span>
        </label>
        <button
          class="agree-button"
          :disabled="!agreed"
          @click="acceptAgreement"
        >
          {{ $t('usageAgreement.acceptButton') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const agreed = ref(false)

function acceptAgreement() {
  const expires = new Date(Date.now() + 24 * 60 * 60 * 1000).toUTCString()
  document.cookie = `usage_agreement_accepted=1; expires=${expires}; path=/; SameSite=Lax`
  const redirect = route.query.redirect as string
  router.push(redirect || '/')
}
</script>

<style scoped>
.agreement-page {
  min-height: 100vh;
  background: #0a0a0a;
  color: #e0e0e0;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem 1rem;
}

.agreement-container {
  max-width: 520px;
  width: 100%;
}

h1 {
  font-size: 1.4rem;
  color: #ffffff;
  margin-bottom: 1.25rem;
}

.agreement-text {
  line-height: 1.7;
  color: #bbb;
  margin-bottom: 2rem;
}

.agreement-action {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  align-items: flex-start;
}

.agreement-checkbox {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  cursor: pointer;
  line-height: 1.5;
  color: #ccc;
}

.agreement-checkbox input[type="checkbox"] {
  margin-top: 0.25rem;
  width: 18px;
  height: 18px;
  accent-color: #2980b9;
  cursor: pointer;
}

.agree-button {
  padding: 0.65rem 2rem;
  background: #2980b9;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.2s;
}

.agree-button:hover:not(:disabled) {
  background: #3498db;
}

h2 {
  font-size: 1.1rem;
  color: #ffffff;
  margin-top: 1.75rem;
  margin-bottom: 0.5rem;
}

.responsibilities-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem 0;
}

.responsibilities-list li {
  padding: 0.4rem 0 0.4rem 1.25rem;
  position: relative;
  line-height: 1.6;
  color: #bbb;
}

.responsibilities-list li::before {
  content: '\2014';
  position: absolute;
  left: 0;
  color: #666;
}

.agree-button:disabled {
  background: #333;
  color: #666;
  cursor: not-allowed;
}
</style>
