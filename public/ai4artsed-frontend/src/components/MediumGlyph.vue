<template>
  <!-- The filled form: Material Symbols, as the canvas draws a config's medium
       (canvas/StageModule.vue, canvas/ConfigSelectorModal.vue), in px. -->
  <svg
    v-if="filledPath"
    xmlns="http://www.w3.org/2000/svg"
    :height="size"
    viewBox="0 -960 960 960"
    :width="size"
    fill="currentColor"
    aria-hidden="true"
  >
    <path :d="filledPath" />
  </svg>
  <svg
    v-else
    viewBox="0 0 24 24"
    width="1em"
    height="1em"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="id === 'image'">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.6" />
      <path d="M21 15.5 15.5 10 5 20.5" />
    </template>
    <template v-else-if="id === 'video'">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M10 8.7 15.5 12 10 15.3Z" fill="currentColor" stroke="none" />
    </template>
    <template v-else-if="id === 'sound'">
      <path d="M9 17.5V6l10-2v10" />
      <circle cx="6.5" cy="17.5" r="2.5" />
      <circle cx="16.5" cy="15.5" r="2.5" />
    </template>
    <template v-else-if="id === 'text'">
      <path d="M4 6.5h16" />
      <path d="M4 11.5h16" />
      <path d="M4 16.5h10.5" />
    </template>
    <template v-else-if="id === 'code'">
      <path d="M8.5 8 4.5 12l4 4" />
      <path d="M15.5 8l4 4-4 4" />
      <path d="M13.4 5.5 10.6 18.5" />
    </template>
    <template v-else>
      <path d="M12 2.8 20.5 7v10L12 21.2 3.5 17V7Z" />
      <path d="M3.5 7 12 11.6 20.5 7" />
      <path d="M12 11.6V21.2" />
    </template>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MediumId } from '@/composables/useMediumInference'

const props = withDefaults(defineProps<{
  id: MediumId
  /** `filled`: the Material form, `size` px square; `line`: the stroke glyph at 1em. */
  variant?: 'line' | 'filled'
  size?: number
}>(), { variant: 'line', size: 24 })

const FILLED: Partial<Record<MediumId, string>> = {
  image: 'M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Z',
  video: 'm380-300 280-180-280-180v360ZM160-160q-33 0-56.5-23.5T80-240v-480q0-33 23.5-56.5T160-800h640q33 0 56.5 23.5T880-720v480q0 33-23.5 56.5T800-160H160Zm0-80h640v-480H160v480Zm0 0v-480 480Z',
  sound: 'M400-120q-66 0-113-47t-47-113q0-66 47-113t113-47q23 0 42.5 5.5T480-418v-422h240v160H560v400q0 66-47 113t-113 47Z',
  text: 'M280-160v-520H80v-120h520v120H400v520H280Zm360 0v-320H520v-120h360v120H760v320H640Z',
}

/** The filled path, where the variant asks for it and the medium has one. */
const filledPath = computed(() => props.variant === 'filled' ? FILLED[props.id] : undefined)
</script>
