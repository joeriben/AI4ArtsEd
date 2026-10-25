import { ref } from 'vue'
import { defineStore } from 'pinia'
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '../i18n'

const validCodes = SUPPORTED_LANGUAGES.map(l => l.code) as readonly string[]

// ============================================================================
// PAGE BACKGROUND TONES
// ============================================================================

/**
 * Darkness steps, labelled by how much black they carry: 96% black is the
 * historical page background (#0a0a0a), 90% and 80% are progressively dimmer
 * for bright rooms and projection.
 */
export const BACKGROUND_LEVELS = [
  { id: 'l96', lightness: 4 },
  { id: 'l90', lightness: 10 },
  { id: 'l80', lightness: 20 }
] as const

/** Colour cast applied to every darkness step. */
export const BACKGROUND_HUES = [
  { id: 'neutral', hue: 0, saturation: 0 },
  { id: 'cool', hue: 220, saturation: 0.2 },
  { id: 'warm', hue: 28, saturation: 0.17 }
] as const

/**
 * Lightness offsets (in HSL percentage points) of the four elevated surfaces
 * above the page background. At the 96% level they reproduce the values that
 * used to be hardcoded per component: #141414, #1a1a1a, #2a2a2a, #333333.
 */
const SURFACE_OFFSETS = [4.0, 6.3, 12.6, 16.0] as const

export interface BackgroundTint {
  id: string
  levelId: string
  hueId: string
  /** Page background. */
  base: string
  /** The four elevated surfaces, darkest first. */
  surfaces: string[]
  /** Space-separated RGB triplets for base + surfaces, for alpha use. */
  rgbs: string[]
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const lf = l / 100
  const a = s * Math.min(lf, 1 - lf)
  const channel = (n: number) => {
    const k = (n + h / 30) % 12
    return Math.round(255 * (lf - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))))
  }
  return [channel(0), channel(8), channel(4)]
}

function toHex(rgb: [number, number, number]): string {
  return `#${rgb.map(c => c.toString(16).padStart(2, '0')).join('')}`
}

function makeTint(id: string, levelId: string, hueId: string, hue: number, saturation: number, lightness: number): BackgroundTint {
  // The cast is damped as the page gets lighter -- the same saturation reads as
  // a tint at 4% lightness and as a colour at 20%.
  const s = saturation * (1 - lightness / 60)
  // Surfaces spread further apart on lighter bases, where a fixed lightness
  // step would no longer separate a panel from the page behind it.
  const spread = 1 + (lightness - 4) / 20
  const rgbs = [
    hslToRgb(hue, s, lightness),
    ...SURFACE_OFFSETS.map(o => hslToRgb(hue, s, Math.min(100, lightness + o * spread)))
  ]
  return {
    id,
    levelId,
    hueId,
    base: toHex(rgbs[0]!),
    surfaces: rgbs.slice(1).map(toHex),
    rgbs: rgbs.map(c => c.join(' '))
  }
}

export const BACKGROUND_TINTS: BackgroundTint[] = [
  makeTint('pure', 'pure', 'neutral', 0, 0, 0),
  ...BACKGROUND_LEVELS.flatMap(level =>
    BACKGROUND_HUES.map(h => makeTint(`${level.id}-${h.id}`, level.id, h.id, h.hue, h.saturation, level.lightness))
  )
]

const DEFAULT_TINT_ID = 'l96-neutral'
const BG_TINT_STORAGE_KEY = 'ai4artsed_bg_tint'
const VOICE_CHAT_STORAGE_KEY = 'ai4artsed_voice_chat'

export function findTint(id: string): BackgroundTint {
  return BACKGROUND_TINTS.find(t => t.id === id) ?? BACKGROUND_TINTS.find(t => t.id === DEFAULT_TINT_ID)!
}

/**
 * Pinia Store for Global User Preferences
 *
 * Manages:
 * - Global language selection for entire app
 * - Page background tone (--bg-base and the derived --surface-* tokens)
 * - Syncs with localStorage for persistence
 * - Syncs with vue-i18n locale for UI translations
 * - Used across all phases (Phase 1, 2, 3)
 *
 * Architecture Decision: Language selection is site-wide, not phase-specific
 */
export const useUserPreferencesStore = defineStore('userPreferences', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  /** Current language (default: German) */
  const language = ref<SupportedLanguage>('de')

  /** Current page background tone (default: neutral, 96% black) */
  const backgroundTint = ref<string>(DEFAULT_TINT_ID)

  /**
   * Whether this platform may speak here at all.
   *
   * ONE switch for the whole surface, not one per figure: it is one voice, and
   * somebody who does not want to be spoken to does not want it from Help
   * either. Where a surface has its own way with the voice — the workshop's
   * writing and speaking modes — that choice sits under this one.
   *
   * It says nothing about whether speech is possible: an installation can have
   * it switched off or be below the safety level for it, and then nothing
   * speaks however this stands.
   */
  const voiceChat = ref<boolean>(true)

  // ============================================================================
  // INITIALIZATION
  // ============================================================================

  /**
   * Load language from localStorage on store initialization
   */
  function initializeLanguage() {
    const savedLanguage = localStorage.getItem('ai4artsed_language')
    if (savedLanguage && validCodes.includes(savedLanguage)) {
      language.value = savedLanguage as SupportedLanguage
    }
  }

  /**
   * Load background tone from localStorage and push it into the DOM.
   */
  function initializeBackgroundTint() {
    const saved = localStorage.getItem(BG_TINT_STORAGE_KEY)
    if (saved && BACKGROUND_TINTS.some(t => t.id === saved)) {
      backgroundTint.value = saved
    }
    applyBackgroundTint(backgroundTint.value)
  }

  /**
   * Load the voice switch. Nothing stored means nobody has decided yet, and
   * this platform speaks unless it was told not to.
   */
  function initializeVoiceChat() {
    const saved = localStorage.getItem(VOICE_CHAT_STORAGE_KEY)
    if (saved !== null) voiceChat.value = saved === '1'
  }

  // ============================================================================
  // ACTIONS
  // ============================================================================

  /**
   * Set language and sync with localStorage
   */
  function setLanguage(newLanguage: SupportedLanguage) {
    language.value = newLanguage
    localStorage.setItem('ai4artsed_language', newLanguage)
    console.log(`[UserPreferences] Language set to: ${newLanguage}`)
  }

  /**
   * Cycle to the next language in SUPPORTED_LANGUAGES
   */
  function toggleLanguage() {
    const currentIndex = SUPPORTED_LANGUAGES.findIndex(l => l.code === language.value)
    const nextIndex = (currentIndex + 1) % SUPPORTED_LANGUAGES.length
    setLanguage(SUPPORTED_LANGUAGES[nextIndex]!.code)
  }

  /**
   * Write the chosen tone into --bg-base and the three --surface-* tokens on
   * <html>. Every full-surface background and panel in the app resolves through
   * those variables.
   */
  function applyBackgroundTint(id: string) {
    const tint = findTint(id)
    const root = document.documentElement
    root.style.setProperty('--bg-base', tint.base)
    tint.surfaces.forEach((hex, i) => root.style.setProperty(`--surface-${i + 1}`, hex))
    tint.rgbs.forEach((triplet, i) => {
      root.style.setProperty(i === 0 ? '--bg-base-rgb' : `--surface-${i}-rgb`, triplet)
    })
    root.setAttribute('data-bg-tint', tint.id)
  }

  /**
   * Set background tone and sync with localStorage
   */
  function setBackgroundTint(id: string) {
    backgroundTint.value = id
    localStorage.setItem(BG_TINT_STORAGE_KEY, id)
    applyBackgroundTint(id)
    console.log(`[UserPreferences] Background tint set to: ${id}`)
  }

  /** Let this platform speak here, or stop it. */
  function setVoiceChat(on: boolean) {
    voiceChat.value = on
    localStorage.setItem(VOICE_CHAT_STORAGE_KEY, on ? '1' : '0')
  }

  /** The currently selected tone (for swatches). */
  function currentTint(): BackgroundTint {
    return findTint(backgroundTint.value)
  }

  // Initialize from localStorage
  initializeLanguage()
  initializeBackgroundTint()
  initializeVoiceChat()

  // ============================================================================
  // RETURN PUBLIC API
  // ============================================================================

  return {
    language,
    setLanguage,
    toggleLanguage,
    backgroundTint,
    setBackgroundTint,
    currentTint,
    voiceChat,
    setVoiceChat
  }
})
