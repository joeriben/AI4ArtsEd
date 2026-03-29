<template>
  <div class="seed-control">
    <label class="seed-label">
      Seed
      <input
        v-model.number="seedModel"
        type="number"
        min="0"
        :disabled="randomModel || disabled"
        class="seed-input"
      />
    </label>
    <label class="seed-checkbox">
      <input type="checkbox" v-model="randomModel" :disabled="disabled" />
      {{ t('latentLab.shared.randomVariation') }}
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  seed: number
  random: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:seed': [value: number]
  'update:random': [value: boolean]
}>()

const seedModel = computed({
  get: () => props.seed,
  set: (v: number) => emit('update:seed', v),
})

const randomModel = computed({
  get: () => props.random,
  set: (v: boolean) => emit('update:random', v),
})
</script>

<style scoped>
.seed-control {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.75rem;
}

.seed-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
}

.seed-input {
  width: 140px;
  padding: 0.35rem 0.5rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  color: #fff;
  font-size: 0.85rem;
  font-family: 'Fira Code', 'Consolas', monospace;
}

.seed-input:disabled {
  opacity: 0.4;
}

.seed-checkbox {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
}
</style>
