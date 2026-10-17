<template>
  <span :class="stateClass">{{ word }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { dsgvoWord } from '@/lib/dsgvoRecord'

/**
 * What is RECORDED about the data path of ONE service: conform, not conform, or
 * nothing at all. The third state is not a weaker red -- AWS Bedrock is conform
 * only if the AWS account is restricted to European regions, and the platform
 * cannot see that. See docs/ELEMENT_STRUCTURE_REGISTRY.md.
 *
 * The value always comes from the register (hardware_matrix.json, read by
 * settings_routes._recorded_conformity), never from a claim written in frontend
 * code -- two tables carried their own hardcoded flags until 2026-08-17.
 */
const props = defineProps<{ recorded?: boolean | null }>()
const { t } = useI18n()

const stateClass = computed(() => {
  if (props.recorded === true) return 'dsgvo-ok'
  if (props.recorded === false) return 'dsgvo-no'
  return 'dsgvo-none'
})

const word = computed(() => dsgvoWord(props.recorded, t))
</script>

<style scoped>
span {
  font-weight: 400;
  font-size: 12px;
}
.dsgvo-ok {
  color: #66bb6a;
}
.dsgvo-no {
  color: #ef5350;
}
.dsgvo-none {
  color: #b8b8b8;
}
</style>
