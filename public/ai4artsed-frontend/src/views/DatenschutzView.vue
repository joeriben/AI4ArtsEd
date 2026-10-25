<template>
  <div class="legal-page">
    <div class="legal-container">
      <h1>{{ $t('legal.privacy.title') }}</h1>
      <DatenschutzText />
    </div>
  </div>
</template>

<script setup lang="ts">
import DatenschutzText from '@/components/legal/DatenschutzText.vue'
</script>

<style scoped>
.legal-page {
  min-height: 100%;
  background: var(--bg-base);
  padding: 2rem;
  color: #ffffff;
}

.legal-container {
  max-width: 900px;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 2.5rem;
}

h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 2rem;
  color: #ffffff;
  border-bottom: 2px solid rgba(76, 175, 80, 0.3);
  padding-bottom: 0.5rem;
}

@media (max-width: 768px) {
  .legal-page {
    padding: 1rem;
  }

  .legal-container {
    padding: 1.5rem;
  }

  h1 {
    font-size: 1.5rem;
  }
}
</style>
