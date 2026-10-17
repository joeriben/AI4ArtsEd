<template>
  <!-- The frame (ground, head row, close) is OverlayFrame; the text is
       components/legal/DatenschutzText.vue, which the route /datenschutz renders too. -->
  <OverlayFrame
    :model-value="modelValue"
    :title="$t('legal.privacy.title')"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="modal-body">
      <DatenschutzText />
    </div>
  </OverlayFrame>
</template>

<script setup lang="ts">
import OverlayFrame from './OverlayFrame.vue'
import DatenschutzText from './legal/DatenschutzText.vue'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

<style scoped>
.modal-body {
  padding: 2rem;
  overflow-y: auto;
  flex: 1;
  color: #ffffff;
}

@media (max-width: 768px) {
  .modal-body {
    padding: 1.5rem;
  }
}
</style>
