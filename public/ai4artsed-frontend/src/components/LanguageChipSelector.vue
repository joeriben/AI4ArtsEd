<template>
  <div dir="ltr" class="language-chip-selector">
    <ChipGroups
      multiple
      :model-value="modelValue"
      :groups="groups"
      :min-width="130"
      :max="max"
      :disabled="disabled"
      @update:model-value="v => emit('update:modelValue', v as string[])"
    />

    <p class="chip-hint">{{ t('compare.selectHint', { count: modelValue.length, max }) }}</p>
  </div>
</template>

<script setup lang="ts">
/**
 * Which languages a comparison runs in: several at once, up to a ceiling.
 *
 * The fields themselves are `ChipSelect` since 2026-08-24 - it is the platform's
 * grid of clickable fields, and this was the second implementation of it; the
 * GROUPS around them are `ChipGroups` since 2026-09-04, when the instruments of
 * the Prompt Interception group needed the same frame. What stays here is what
 * is this component's own: which two groups there are, the list of languages,
 * and the line that counts. Both groups are handed the WHOLE selection, so the
 * ceiling counts across them and a language chosen in one is seen by the other.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ChipGroups, { type ChipGroup } from '@/components/ChipGroups.vue'

interface LanguageOption {
  code: string
  label: string
  description?: string
}

interface Props {
  modelValue: string[]
  max?: number
  /** Locked while a run is out: a column added or removed mid-run has no cells. */
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), { max: 4, disabled: false })
const emit = defineEmits<{ 'update:modelValue': [langs: string[]] }>()
const { t } = useI18n()

const platformLanguages = computed<LanguageOption[]>(() => [
  { code: 'en', label: 'English', description: t('languageChips.description.en') },
  { code: 'de', label: 'Deutsch', description: t('languageChips.description.de') },
  { code: 'ar', label: 'العربية', description: t('languageChips.description.ar') },
  { code: 'he', label: 'עברית', description: t('languageChips.description.he') },
  { code: 'tr', label: 'Türkçe', description: t('languageChips.description.tr') },
  { code: 'ko', label: '한국어', description: t('languageChips.description.ko') },
  { code: 'uk', label: 'Українська', description: t('languageChips.description.uk') },
  { code: 'fr', label: 'Français', description: t('languageChips.description.fr') },
  { code: 'es', label: 'Español', description: t('languageChips.description.es') },
  { code: 'bg', label: 'Български', description: t('languageChips.description.bg') },
])

const furtherLanguages = computed<LanguageOption[]>(() => [
  { code: 'hsb', label: 'Hornjoserbšćina', description: t('languageChips.description.hsb') },
  { code: 'dsb', label: 'Dolnoserbšćina', description: t('languageChips.description.dsb') },
  { code: 'fry', label: 'Frysk', description: t('languageChips.description.fry') },
  { code: 'yo', label: 'Yorùbá', description: t('languageChips.description.yo') },
  { code: 'sw', label: 'Kiswahili', description: t('languageChips.description.sw') },
  { code: 'cy', label: 'Cymraeg', description: t('languageChips.description.cy') },
  { code: 'qu', label: 'Runasimi', description: t('languageChips.description.qu') },
  { code: 'hi', label: 'हिन्दी', description: t('languageChips.description.hi') },
  { code: 'ja', label: '日本語', description: t('languageChips.description.ja') },
  { code: 'zh', label: '中文', description: t('languageChips.description.zh') },
])

const platformOptions = computed(() =>
  platformLanguages.value.map(l => ({
    value: l.code,
    label: l.label,
    aside: l.code,
    title: l.description,
  }))
)

/** The further languages carry the row's other tone, which is what the dashed
 *  border used to say: these are not the platform's own ten. */
const furtherOptions = computed(() =>
  furtherLanguages.value.map(l => ({
    value: l.code,
    label: l.label,
    aside: l.code,
    title: l.description,
    tone: 'amber' as const,
  }))
)

const groups = computed<ChipGroup[]>(() => [
  ...(platformLanguages.value.length
    ? [{ id: 'platform', label: t('compare.platformLanguages'), options: platformOptions.value }]
    : []),
  ...(furtherLanguages.value.length
    ? [{ id: 'further', label: t('compare.furtherLanguages'), options: furtherOptions.value }]
    : []),
])
</script>

<style scoped>
.language-chip-selector {
  margin: 0.75rem 0;
}

/* A language name stands on ONE line. ChipSelect breaks a
   name inside the word where it is wider than its share of the row, which is
   right for a list of models and wrong here: „Deutsch" read as „Deuts / ch".
   The width above is what makes the break unnecessary — the longest name on
   the list, Hornjoserbšćina with its code, measures 127 px, and 130 px gives
   two fields of 134 px in the 274 px preparation column. This line is the
   guarantee: a name added later that outgrows the field runs past it and is
   seen, rather than quietly falling apart. */
.language-chip-selector :deep(.chip-select-option) {
  white-space: nowrap;
  overflow-wrap: normal;
}

.chip-hint {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 0.3rem;
}
</style>
