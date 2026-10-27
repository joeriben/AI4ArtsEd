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
import { PLATFORM_LANGUAGES, FURTHER_LANGUAGES } from '@/lib/platformLanguages'

interface Props {
  modelValue: string[]
  max?: number
  /** Locked while a run is out: a column added or removed mid-run has no cells. */
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), { max: 4, disabled: false })
const emit = defineEmits<{ 'update:modelValue': [langs: string[]] }>()
const { t } = useI18n()

// The list is lib/platformLanguages.ts; what it says on hover is this component's.
const descriptions = computed<Record<string, string>>(() => ({
  en: t('languageChips.description.en'),
  de: t('languageChips.description.de'),
  ar: t('languageChips.description.ar'),
  he: t('languageChips.description.he'),
  tr: t('languageChips.description.tr'),
  ko: t('languageChips.description.ko'),
  uk: t('languageChips.description.uk'),
  fr: t('languageChips.description.fr'),
  es: t('languageChips.description.es'),
  bg: t('languageChips.description.bg'),
  hsb: t('languageChips.description.hsb'),
  dsb: t('languageChips.description.dsb'),
  fry: t('languageChips.description.fry'),
  yo: t('languageChips.description.yo'),
  sw: t('languageChips.description.sw'),
  cy: t('languageChips.description.cy'),
  qu: t('languageChips.description.qu'),
  hi: t('languageChips.description.hi'),
  ja: t('languageChips.description.ja'),
  zh: t('languageChips.description.zh'),
}))

const platformLanguages = computed(() =>
  PLATFORM_LANGUAGES.map(l => ({ ...l, description: descriptions.value[l.code] })))

const furtherLanguages = computed(() =>
  FURTHER_LANGUAGES.map(l => ({ ...l, description: descriptions.value[l.code] })))

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
