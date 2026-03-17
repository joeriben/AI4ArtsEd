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
          :title="lang.description"
        >
          <span class="chip-label">{{ lang.label }}</span>
          <span class="chip-code">{{ lang.code }}</span>
        </button>
      </div>
    </div>

    <div v-if="furtherLanguages.length" class="chip-group">
      <span class="chip-group-label">{{ t('compare.furtherLanguages') }}</span>
      <div class="chip-row">
        <button
          v-for="lang in furtherLanguages"
          :key="lang.code"
          class="lang-chip further"
          :class="{ selected: modelValue.includes(lang.code), disabled: !modelValue.includes(lang.code) && modelValue.length >= max }"
          @click="toggle(lang.code)"
          :disabled="!modelValue.includes(lang.code) && modelValue.length >= max"
          :title="lang.description"
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
  description?: string
}

interface Props {
  modelValue: string[]
  max?: number
}

const props = withDefaults(defineProps<Props>(), { max: 4 })
const emit = defineEmits<{ 'update:modelValue': [langs: string[]] }>()
const { t } = useI18n()

const platformLanguages: LanguageOption[] = [
  { code: 'en', label: 'English', description: 'CLIP primary training language — strongest encoding' },
  { code: 'de', label: 'Deutsch', description: 'German — well-represented in T5, weak in CLIP' },
  { code: 'ar', label: 'العربية', description: 'Arabic — RTL script, limited CLIP training data' },
  { code: 'he', label: 'עברית', description: 'Hebrew — RTL script, very limited in CLIP' },
  { code: 'tr', label: 'Türkçe', description: 'Turkish — agglutinative grammar, limited CLIP data' },
  { code: 'ko', label: '한국어', description: 'Korean — Hangul script, moderate T5 coverage' },
  { code: 'uk', label: 'Українська', description: 'Ukrainian — Cyrillic, limited CLIP training' },
  { code: 'fr', label: 'Français', description: 'French — well-represented in both CLIP and T5' },
  { code: 'es', label: 'Español', description: 'Spanish — well-represented in both CLIP and T5' },
  { code: 'bg', label: 'Български', description: 'Bulgarian — Cyrillic, very limited CLIP data' },
]

const furtherLanguages: LanguageOption[] = [
  { code: 'hsb', label: 'Hornjoserbšćina', description: 'Upper Sorbian — Slavic minority language in Germany, ~20K speakers' },
  { code: 'dsb', label: 'Dolnoserbšćina', description: 'Lower Sorbian — Slavic minority language in Brandenburg, ~7K speakers' },
  { code: 'fry', label: 'Frysk', description: 'West Frisian — Germanic language in the Netherlands, ~500K speakers' },
  { code: 'yo', label: 'Yorùbá', description: 'Yoruba — West African language (Nigeria), ~50M speakers' },
  { code: 'sw', label: 'Kiswahili', description: 'Swahili — East African lingua franca, ~100M speakers' },
  { code: 'cy', label: 'Cymraeg', description: 'Welsh — Celtic language in Wales, ~500K speakers' },
  { code: 'qu', label: 'Runasimi', description: 'Quechua — Indigenous Andean language, ~10M speakers' },
  { code: 'hi', label: 'हिन्दी', description: 'Hindi — Indo-Aryan, Devanagari script, ~600M speakers' },
  { code: 'ja', label: '日本語', description: 'Japanese — logographic + syllabic scripts, ~125M speakers' },
  { code: 'zh', label: '中文', description: 'Chinese — logographic script, ~1.1B speakers' },
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

.lang-chip.further {
  border-style: dashed;
}

.lang-chip.further.selected {
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
