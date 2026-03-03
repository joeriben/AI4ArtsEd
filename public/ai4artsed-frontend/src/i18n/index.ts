import { createI18n } from 'vue-i18n'
import { de } from './de'
import { en } from './en'
import { tr } from './tr'
import { ko } from './ko'
import { uk } from './uk'
import { fr } from './fr'
import { es } from './es'
import { he } from './he'
import { ar } from './ar'
import { bg } from './bg'

export const SUPPORTED_LANGUAGES = [
  { code: 'ar', label: 'العربية', dir: 'rtl' as const },
  { code: 'bg', label: 'Български', dir: 'ltr' as const },
  { code: 'de', label: 'Deutsch', dir: 'ltr' as const },
  { code: 'en', label: 'English', dir: 'ltr' as const },
  { code: 'es', label: 'Español', dir: 'ltr' as const },
  { code: 'fr', label: 'Français', dir: 'ltr' as const },
  { code: 'he', label: 'עברית', dir: 'rtl' as const },
  { code: 'tr', label: 'Türkçe', dir: 'ltr' as const },
  { code: 'uk', label: 'Українська', dir: 'ltr' as const },
  { code: 'ko', label: '한국어', dir: 'ltr' as const },
] as const

export type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number]['code']

/** Localized string object — en is mandatory, all others optional with fallback */
export type LocalizedString = { en: string; [key: string]: string }

/** Resolve a localized string for the given locale, falling back to English */
export function localized(obj: Record<string, string>, locale: string): string {
  return obj[locale] || obj.en || ''
}

/** Get text direction for a language code */
export function getLanguageDir(code: string): 'ltr' | 'rtl' {
  const lang = SUPPORTED_LANGUAGES.find(l => l.code === code)
  return lang?.dir ?? 'ltr'
}

const messages = { de, en, tr, ko, uk, fr, es, he, ar, bg }

// Cast locale to SupportedLanguage so vue-i18n accepts all supported languages
// (ko/tr messages are intentionally partial — fallbackLocale handles gaps)
export default createI18n({
  legacy: false,
  locale: 'de' as SupportedLanguage,
  fallbackLocale: 'en',
  messages
})
