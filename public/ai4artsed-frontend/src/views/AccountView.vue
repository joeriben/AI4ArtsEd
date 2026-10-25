<!--
  Personal area (placeholder). Route: /account  (any logged-in user)
  The real works/drafts/prompts UI arrives with P2. Kept minimal so the auth
  guard + routing are exercisable in P0. Page background via var(--bg-base) per rule.
-->
<script setup lang="ts">
import { useLabAuthStore } from '../stores/labAuth'
const auth = useLabAuthStore()
</script>

<template>
  <div class="placeholder-page">
    <div class="placeholder-card">
      <h1>{{ $t('account.title') }}</h1>
      <p class="who" v-if="auth.user">
        {{ auth.user.display_name || auth.user.identifier }}
      </p>
      <p class="soon">{{ $t('account.comingSoon') }}</p>
      <button class="ghost" @click="auth.logout()">{{ $t('auth.logout') }}</button>
    </div>
  </div>
</template>

<style scoped>
.placeholder-page {
  position: fixed; inset: 0;
  background: var(--bg-base);
  display: flex; align-items: center; justify-content: center;
  color: rgba(255, 255, 255, 0.92);
}
.placeholder-card {
  width: 420px; max-width: 90vw;
  background: var(--bg-base);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px; padding: 28px;
}
h1 { font-size: 1.3rem; margin: 0 0 8px; }
.who { font-size: 0.9rem; color: rgba(255, 255, 255, 0.6); margin: 0 0 16px; }
.soon { font-size: 0.85rem; color: rgba(255, 255, 255, 0.5); margin: 0 0 20px; }
.ghost {
  padding: 9px 14px; border-radius: 8px; cursor: pointer;
  background: transparent; color: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
</style>
