<template>
  <label class="seed-control">
    Seed
    <input
      v-model.number="seedModel"
      type="number"
      min="0"
      :disabled="randomModel || disabled"
      class="setting-input setting-seed"
    />
    <label class="seed-random-toggle">
      <input type="checkbox" v-model="randomModel" :disabled="disabled" />
      {{ t('latentLab.shared.randomVariation') }}
    </label>
  </label>
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
.seed-random-toggle {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
}
</style>
