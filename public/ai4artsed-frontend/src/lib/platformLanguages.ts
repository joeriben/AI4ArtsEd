/**
 * The languages the platform can be asked to translate into, by code and by
 * their own name, in the two groups the platform shows them in. The backend
 * names the same codes to a model in English (services/reading_frames.py).
 *
 * Read by the language comparison's chips (components/LanguageChipSelector.vue)
 * and column heads (views/compare/language_comparison.vue), and by the target
 * language of the Canvas translation node (components/canvas/StageModule.vue).
 * It stood inside LanguageChipSelector.vue until 2026-10-24.
 */
export interface PlatformLanguage {
  code: string
  label: string
}

export const PLATFORM_LANGUAGES: readonly PlatformLanguage[] = [
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

export const FURTHER_LANGUAGES: readonly PlatformLanguage[] = [
  { code: 'hsb', label: 'Hornjoserbšćina' },
  { code: 'dsb', label: 'Dolnoserbšćina' },
  { code: 'fry', label: 'Frysk' },
  { code: 'yo', label: 'Yorùbá' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'cy', label: 'Cymraeg' },
  { code: 'qu', label: 'Runasimi' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'ja', label: '日本語' },
  { code: 'zh', label: '中文' },
]
