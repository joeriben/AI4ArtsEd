<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import '@/assets/generation-button.css'

const props = withDefaults(defineProps<{
  disabled?: boolean
  executing?: boolean
  checkingSafety?: boolean
  label?: string
  checkingLabel?: string
  executingLabel?: string
  showArrows?: boolean
  errorMessage?: string
}>(), {
  disabled: false,
  executing: false,
  checkingSafety: false,
  label: 'Start',
  checkingLabel: '',
  executingLabel: '',
  showArrows: true,
  errorMessage: ''
})

const emit = defineEmits<{
  click: []
}>()

// Click-queuing for blur-safety race condition:
// If user clicks while checkingSafety is true, queue the intent
// and fire when safety check completes.
const pendingClick = ref(false)

watch(() => props.checkingSafety, (newVal, oldVal) => {
  if (oldVal && !newVal && pendingClick.value) {
    pendingClick.value = false
    // Safety check just finished, fire the queued click
    // (only if not disabled by other conditions)
    if (!props.disabled && !props.executing) {
      emit('click')
    }
  }
})

function handleClick() {
  if (props.checkingSafety) {
    // Queue the click intent — will fire when safety completes
    pendingClick.value = true
    return
  }
  if (props.disabled || props.executing) return
  emit('click')
}

const displayLabel = computed(() => {
  if (props.checkingSafety) return props.checkingLabel || props.label
  if (props.executing) return props.executingLabel || props.label
  return props.label
})

const buttonClasses = computed(() => ({
  'generation-button': true,
  'disabled': props.disabled && !props.checkingSafety && !props.executing,
  'checking-safety': props.checkingSafety,
  'executing': props.executing,
  'error-flash': !!props.errorMessage
}))
</script>

<template>
  <div class="generation-button-container">
    <slot name="before" />
    <button
      :class="buttonClasses"
      :disabled="disabled || executing || checkingSafety"
      @click.prevent="handleClick"
    >
      <span v-if="showArrows" class="button-arrows button-arrows-left">&gt;&gt;&gt;</span>
      <span class="button-text">{{ displayLabel }}</span>
      <span v-if="showArrows" class="button-arrows button-arrows-right">&gt;&gt;&gt;</span>
    </button>
    <!-- Default slot for badges (SafetyBadges, LoRA, etc.) -->
    <slot />
    <!-- Error message display -->
    <div v-if="errorMessage" class="generation-error-message">
      {{ errorMessage }}
    </div>
  </div>
</template>
