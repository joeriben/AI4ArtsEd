<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import '@/assets/generation-button.css'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  disabled?: boolean
  executing?: boolean
  checkingSafety?: boolean
  label?: string
  checkingLabel?: string
  executingLabel?: string
  showArrows?: boolean
  errorMessage?: string
  // Queue transparency + per-device lock
  queuePosition?: number
  deviceBusy?: boolean
  preChecking?: boolean
}>(), {
  disabled: false,
  executing: false,
  checkingSafety: false,
  label: 'Start',
  checkingLabel: '',
  executingLabel: '',
  showArrows: true,
  errorMessage: '',
  queuePosition: 0,
  deviceBusy: false,
  preChecking: false
})

const emit = defineEmits<{
  click: []
  cancel: []
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
    if (!props.disabled && !props.executing && !props.deviceBusy && !props.preChecking) {
      emit('click')
    }
  }
})

function handleClick() {
  // Device busy: clicking the button triggers cancel
  if (props.deviceBusy) {
    emit('cancel')
    return
  }
  if (props.checkingSafety) {
    // Queue the click intent — will fire when safety completes
    pendingClick.value = true
    return
  }
  if (props.disabled || props.executing || props.preChecking) return
  emit('click')
}

const isBlocked = computed(() =>
  props.disabled || props.executing || props.checkingSafety || props.preChecking
)

const displayLabel = computed(() => {
  if (props.preChecking) return '. . .'
  if (props.deviceBusy) return t('mediaInput.cancelPrevious')
  if (props.checkingSafety) return props.checkingLabel || props.label
  if (props.executing) return props.executingLabel || props.label
  return props.label
})

const buttonClasses = computed(() => ({
  'generation-button': true,
  'disabled': props.disabled && !props.checkingSafety && !props.executing && !props.preChecking && !props.deviceBusy,
  'checking-safety': props.checkingSafety,
  'executing': props.executing,
  'pre-checking': props.preChecking,
  'device-busy': props.deviceBusy,
  'error-flash': !!props.errorMessage
}))
</script>

<template>
  <div class="generation-button-container">
    <slot name="before" />
    <button
      :class="buttonClasses"
      :disabled="isBlocked && !deviceBusy"
      @click.prevent="handleClick"
    >
      <span v-if="showArrows && !preChecking" class="button-arrows button-arrows-left">&gt;&gt;&gt;</span>
      <span class="button-text">{{ displayLabel }}</span>
      <span v-if="showArrows && !preChecking" class="button-arrows button-arrows-right">&gt;&gt;&gt;</span>
    </button>
    <!-- Queue position info (shown during execution when others are generating) -->
    <div v-if="executing && queuePosition > 0" class="queue-info">
      {{ t('mediaInput.queueAhead', { count: queuePosition }, queuePosition) }}
    </div>
    <!-- Device busy info -->
    <div v-if="deviceBusy && !executing" class="device-busy-info">
      {{ t('mediaInput.deviceBusy') }}
    </div>
    <!-- Default slot for badges (SafetyBadges, LoRA, etc.) -->
    <slot />
    <!-- Error message display -->
    <div v-if="errorMessage" class="generation-error-message">
      {{ errorMessage }}
    </div>
  </div>
</template>
