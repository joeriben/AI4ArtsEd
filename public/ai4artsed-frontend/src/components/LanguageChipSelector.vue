<template>
  <div dir="ltr" class="language-chip-selector">
    <div v-if="platformLanguages.length" class="chip-group">
      <span class="chip-group-label">{{ t('compare.platformLanguages') }}</span>
      <div class="chip-row">
        <button
          v-for="lang in platformLanguages"
          :key="lang.code"
          class="lang-chip"
          :class="{ selected: modelValue.includes(lang.code), disabled: !modelValue.includes(lang.code) && modelValue.length >= max }"
          @click="toggle(lang.code)"
          :disabled="!modelValue.includes(lang.code) && modelValue.length >= max"
        >
          <span class="chip-label">{{ lang.label }}</span>
          <span class="chip-code">{{ lang.code }}</span>
        </button>
      </div>
    </div>

    <div v-if="minorityLanguages.length" class="chip-group">
      <span class="chip-group-label">{{ t('compare.minorityLanguages') }}</span>
      <div class="chip-row">
        <button
          v-for="lang in minorityLanguages"
          :key="lang.code"
          class="lang-chip minority"
          :class="{ selected: modelValue.includes(lang.code), disabled: !modelValue.includes(lang.code) && modelValue.length >= max }"
          @click="toggle(lang.code)"
          :disabled="!modelValue.includes(lang.code) && modelValue.length >= max"
        >
          <span class="chip-label">{{ lang.label }}</span>
          <span class="chip-code">{{ lang.code }}</span>
        </button>
      </div>
    </div>

    <p class="chip-hint">{{ t('compare.selectHint', { count: modelValue.length, max }) }}</p>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

interface LanguageOption {
  code: string
  label: string
}

interface Props {
  modelValue: string[]
  max?: number
}

const props = withDefaults(defineProps<Props>(), { max: 4 })
const emit = defineEmits<{ 'update:modelValue': [langs: string[]] }>()
const { t } = useI18n()

const platformLanguages: LanguageOption[] = [
  { code: 'en', label: 'English' },
  { code: 'de', label: 'Deutsch' },
  { code: 'ar', label: 'العربية' },
  { code: 'he', label: 'עברית' },
  { code: 'tr', label: 'Türkçe' },
  { code: 'ko', label: '한국어' },
  { code: 'uk', label: 'Українська' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
  { code: 'bg', label: 'Български' },
]

const minorityLanguages: LanguageOption[] = [
  { code: 'hsb', label: 'Hornjoserbšćina' },
  { code: 'fry', label: 'Frysk' },
  { code: 'yo', label: 'Yorùbá' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'cy', label: 'Cymraeg' },
  { code: 'qu', label: 'Runasimi' },
]

function toggle(code: string) {
  const current = [...props.modelValue]
  const idx = current.indexOf(code)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else if (current.length < props.max) {
    current.push(code)
  }
  emit('update:modelValue', current)
}
</script>

<style scoped>
.language-chip-selector {
  margin: 0.75rem 0;
}

.chip-group {
  margin-bottom: 0.75rem;
}

.chip-group-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.4);
  display: block;
  margin-bottom: 0.4rem;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.lang-chip {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.6rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.lang-chip:hover:not(.disabled) {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.08);
}

.lang-chip.selected {
  border-color: rgba(76, 175, 80, 0.6);
  background: rgba(76, 175, 80, 0.12);
  color: rgba(255, 255, 255, 0.95);
}

.lang-chip.disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.lang-chip.minority {
  border-style: dashed;
}

.lang-chip.minority.selected {
  border-style: solid;
  border-color: rgba(255, 183, 77, 0.6);
  background: rgba(255, 183, 77, 0.1);
}

.chip-code {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.35);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.chip-hint {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 0.3rem;
}
</style>
