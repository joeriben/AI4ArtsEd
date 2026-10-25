import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * GPU Realtime Stats from /api/settings/gpu-realtime
 */
export interface GpuRealtimeStats {
  available: boolean
  gpu_name?: string
  power_draw_watts?: number
  power_limit_watts?: number
  temperature_celsius?: number
  utilization_percent?: number
  memory_used_mb?: number
  memory_total_mb?: number
  memory_used_percent?: number
  co2_per_kwh_grams?: number
  error?: string
}

/**
 * Edutainment fact with interpolated values
 */
export interface EdutainmentFact {
  key: string
  text: string
  category: 'energy' | 'data' | 'model' | 'ethics' | 'environment'
  emoji: string
}

/**
 * UI Mode determines content complexity
 */
export type UiMode = 'easy' | 'medium' | 'expert'

// Rotation intervals by UI mode (ms)
const ROTATION_INTERVALS: Record<UiMode, number> = {
  easy: 10000,    // 10 seconds - more time to read
  medium: 8000,   // 8 seconds
  expert: 6000    // 6 seconds - faster for engaged users
}

// Fact categories and their keys per level
const FACT_KEYS: Record<string, string[]> = {
  energy_kids: ['kids_1', 'kids_2', 'kids_3'],
  energy_youth: ['youth_1', 'youth_2', 'youth_3'],
  energy_expert: ['expert_1', 'expert_2', 'expert_3'],
  data_kids: ['kids_1', 'kids_2', 'kids_3'],
  data_youth: ['youth_1', 'youth_2', 'youth_3'],
  data_expert: ['expert_1', 'expert_2', 'expert_3'],
  model_kids: ['kids_1', 'kids_2', 'kids_3'],
  model_youth: ['youth_1', 'youth_2', 'youth_3'],
  model_expert: ['expert_1', 'expert_2', 'expert_3'],
  ethics_kids: ['kids_1', 'kids_2', 'kids_3'],
  ethics_youth: ['youth_1', 'youth_2', 'youth_3'],
  ethics_expert: ['expert_1', 'expert_2', 'expert_3'],
  environment_kids: ['kids_1', 'kids_2', 'kids_3'],
  environment_youth: ['youth_1', 'youth_2', 'youth_3'],
  environment_expert: ['expert_1', 'expert_2', 'expert_3'],
}

const CATEGORIES = ['energy', 'data', 'model', 'ethics', 'environment'] as const

/**
 * Composable for managing edutainment facts during AI generation
 *
 * Features:
 * - Fetches live GPU stats from /api/settings/gpu-realtime
 * - Rotates facts based on UI mode (easy/medium/expert)
 * - Interpolates real GPU values into fact strings
 * - Calculates CO2 emissions in realtime
 */
export function useEdutainmentFacts(uiMode: UiMode = 'medium') {
  const { t } = useI18n()

  // State
  const gpuStats = ref<GpuRealtimeStats>({ available: false })
  const currentFact = ref<EdutainmentFact | null>(null)
  const isPolling = ref(false)
  const elapsedSeconds = ref(0)
  const totalEnergyWh = ref(0)
  const totalCo2Grams = ref(0)

  // Internal — single consolidated interval replaces 3 separate timers
  let consolidatedInterval: number | null = null
  let tickCount = 0
  let factIndex = 0
  let categoryIndex = 0

  // Computed
  const rotationDelay = computed(() => ROTATION_INTERVALS[uiMode] || 8000)

  // kids/youth here are the names of the fact levels in the translation files
  // (energy.kids_1, data.youth_2, ...) across ten locales. The UI mode was
  // renamed to easy/medium/expert on 2026-08-12; the i18n keys keep their
  // names, so the mode is mapped onto them here.
  const levelKey = computed(() => {
    if (uiMode === 'easy') return 'kids'
    if (uiMode === 'medium') return 'youth'
    return 'expert'
  })

  /**
   * Fetch GPU realtime stats from backend
   */
  async function fetchGpuStats(): Promise<void> {
    try {
      const response = await fetch('/api/settings/gpu-realtime')
      if (response.ok) {
        gpuStats.value = await response.json()
      }
    } catch (error) {
      console.warn('[Edutainment] Failed to fetch GPU stats:', error)
      gpuStats.value = { available: false, error: 'Fetch failed' }
    }
  }

  /**
   * Interpolate variables into fact string
   */
  function interpolateFact(text: string): string {
    const stats = gpuStats.value
    if (!stats.available) return text

    // Calculate derived values
    const kwhUsed = totalEnergyWh.value / 1000
    const co2PerKwh = stats.co2_per_kwh_grams || 400
    const vramGb = stats.memory_total_mb ? Math.round(stats.memory_total_mb / 1024) : 0
    const usedGb = stats.memory_used_mb ? Math.round(stats.memory_used_mb / 1024) : 0
    const powerPercent = stats.power_limit_watts && stats.power_draw_watts
      ? Math.round((stats.power_draw_watts / stats.power_limit_watts) * 100)
      : 0

    // Calculate CO2 for 1000 images estimate
    const co2Per1000 = (totalCo2Grams.value * 1000) / Math.max(1, elapsedSeconds.value / 30)
    const co2Kg = (co2Per1000 / 1000).toFixed(1)

    return text
      .replace('{watts}', String(Math.round(stats.power_draw_watts || 0)))
      .replace('{tdp}', String(Math.round(stats.power_limit_watts || 0)))
      .replace('{temp}', String(stats.temperature_celsius || 0))
      .replace('{util}', String(stats.utilization_percent || 0))
      .replace('{kwh}', kwhUsed.toFixed(4))
      .replace('{vram}', String(vramGb))
      .replace('{used}', String(usedGb))
      .replace('{total}', String(vramGb))
      .replace('{percent}', String(stats.memory_used_percent || powerPercent))
      .replace('{co2}', totalCo2Grams.value.toFixed(2))
      .replace('{totalKg}', co2Kg)
      .replace('{seconds}', String(elapsedSeconds.value))
  }

  /**
   * Get next fact from rotation
   */
  function getNextFact(): EdutainmentFact {
    // Cycle through categories
    const category = CATEGORIES[categoryIndex % CATEGORIES.length] ?? 'energy'
    const keyPrefix = `${category}_${levelKey.value}`
    const keys = FACT_KEYS[keyPrefix] || []
    const key = keys[factIndex % keys.length] || 'kids_1'

    // Get translated text
    const i18nKey = `edutainment.${category}.${key}`
    let text = t(i18nKey)

    // Interpolate live values
    text = interpolateFact(text)

    // Extract emoji from start of text
    const emojiMatch = text.match(/^([\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}])/u)
    const emoji = emojiMatch ? emojiMatch[0] : '💡'

    // Advance indices
    factIndex++
    if (factIndex >= keys.length) {
      factIndex = 0
      categoryIndex++
    }

    return {
      key: i18nKey,
      text,
      category,
      emoji
    }
  }

  /**
   * Rotate to next fact
   */
  function rotateFact(): void {
    currentFact.value = getNextFact()
  }

  /**
   * Update energy calculations based on current power draw
   */
  function updateEnergy(): void {
    elapsedSeconds.value++

    const watts = gpuStats.value.power_draw_watts || 0
    const co2PerKwh = gpuStats.value.co2_per_kwh_grams || 400

    // Energy: Watts * 1 second / 3600 = Wh
    const whThisSecond = watts / 3600
    totalEnergyWh.value += whThisSecond

    // CO2: Wh / 1000 * g/kWh = grams
    const co2ThisSecond = (whThisSecond / 1000) * co2PerKwh
    totalCo2Grams.value += co2ThisSecond
  }

  /**
   * Start fact rotation and GPU polling
   * Uses a single 1s interval instead of 3 separate timers
   */
  function startRotation(): void {
    if (isPolling.value) return

    isPolling.value = true
    factIndex = 0
    categoryIndex = 0
    tickCount = 0
    elapsedSeconds.value = 0
    totalEnergyWh.value = 0
    totalCo2Grams.value = 0

    // Initial fetch and fact
    fetchGpuStats().then(() => {
      rotateFact()
    })

    // Single consolidated 1s interval handles all concerns:
    // - Energy update: every tick (1s)
    // - GPU polling: every 2nd tick (2s)
    // - Fact rotation: every Nth tick (based on rotationDelay)
    const rotationTicks = Math.round(rotationDelay.value / 1000)
    consolidatedInterval = window.setInterval(() => {
      tickCount++
      updateEnergy()
      if (tickCount % 2 === 0) {
        fetchGpuStats()
      }
      if (tickCount % rotationTicks === 0) {
        rotateFact()
      }
    }, 1000)
  }

  /**
   * Stop consolidated interval
   */
  function stopRotation(): void {
    isPolling.value = false

    if (consolidatedInterval !== null) {
      clearInterval(consolidatedInterval)
      consolidatedInterval = null
    }
  }

  /**
   * Reset counters
   */
  function reset(): void {
    elapsedSeconds.value = 0
    totalEnergyWh.value = 0
    totalCo2Grams.value = 0
    factIndex = 0
    categoryIndex = 0
  }

  // Cleanup on unmount
  onUnmounted(() => {
    stopRotation()
  })

  return {
    // State
    gpuStats,
    currentFact,
    isPolling,
    elapsedSeconds,
    totalEnergyWh,
    totalCo2Grams,

    // Actions
    startRotation,
    stopRotation,
    rotateFact,
    fetchGpuStats,
    reset
  }
}
