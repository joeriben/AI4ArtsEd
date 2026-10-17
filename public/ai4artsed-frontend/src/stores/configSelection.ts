import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { LocalizedString } from '@/i18n'

// Type definitions
export interface ConfigMetadata {
  id: string
  name: LocalizedString
  description: LocalizedString
  short_description: LocalizedString
  /**
   * What the config file itself files this config under. The route has always
   * sent it; it was typed here when Perspectives on a Template grouped its
   * chips by it. That surface chooses through the platform's own
   * overlay now and nothing reads the field; it stays typed because the route
   * sends it and a reader of this type should find it named.
   */
  category?: LocalizedString
  properties: string[]
  pipeline: string
  /**
   * The lines of a checklist preset, verbatim as they stand in its own context,
   * by the dimension they belong to. They are the source's own wording and are
   * not translated, so there is one set of them and no language to pick. Only
   * the two poles of the VisionReward checklist carry it; the route sends it
   * where a config has it and leaves it out where it has not
   * (`meta.dimension_lines`, `pipeline_configs_with_properties`).
   *
   * No surface reads them: Aesthetic Poles composes the line for the step the
   * axis stands at out of `dimension_scales`,
   * and at the outermost step it composes exactly this one. They stay because
   * they are what the preset's own context prints, and `devserver/tests/
   * test_dimension_lines.py` holds prose and data to each other by them.
   */
  dimension_lines?: Record<string, string>
  /**
   * The order that checklist is READ in, as a list. The route serialises a JSON
   * object with its keys sorted, so the order of `dimension_lines` does not
   * survive the wire; the list does, and it is the one a surface reads the
   * checklist in — the order the draw and the properties under the axis stand
   * in (`meta.dimensions_verbatim`, sent beside the lines and left out with
   * them).
   */
  dimension_order?: string[]
  /**
   * The ordered scale each dimension is ranked on, the entry the ranking counts
   * from, and the option word this pole stands at — the source's own wording
   * throughout (`meta.dimensions_verbatim`). A surface that lets the axis swing
   * by one or two steps reads the words for those steps off here, and composes
   * its line from them; the one line in `dimension_lines` carries the outermost
   * step alone.
   */
  dimension_scales?: Record<string, { scale: string[]; neutral: string; option: string }>
  /**
   * The frame text with the token `{PROPERTIES}` where the list of properties
   * stands — for a surface that DRAWS the properties itself and hands the whole
   * thing over as its own context. Multilingual, beside `context`, which is
   * what runs wherever the preset is used as an ordinary perspective.
   */
  context_frame?: Record<string, string>
  media_preferences?: {
    default_output?: string
  }
  /**
   * The adapters a perspective brings with it (`meta.loras` of its config,
   * sent by the route): the file as `name`, and the
   * strength the config sets. The Flow reads it to put the automatic on the
   * model that carries the adapter, and to mark the perspective's disc.
   */
  loras?: Array<{ name: string; strength: number }>
  // Backend sends icon/color as top-level fields
  icon?: string
  color?: string
  difficulty?: number
  meta?: {
    stage?: string
  }
}

export interface SymbolData {
  symbol: string
  label: string
  tooltip: string
}

export interface ConfigsResponse {
  configs: ConfigMetadata[]
}

/**
 * Pinia store that loads the interception configs from
 * /pipeline_configs_with_properties and keeps their symbols by category.
 * The property selection it once carried (XOR over property pairs) went with
 * the property canvas; what remains is the catalogue the perspective overlay,
 * the flow and the aesthetic poles read.
 */
export const useConfigSelectionStore = defineStore('configSelection', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  /** All available configs from API */
  const availableConfigs = ref<ConfigMetadata[]>([])

  /** Symbol data map (property name -> SymbolData) */
  const symbolDataMap = ref<Map<string, SymbolData>>(new Map())

  /** Loading state */
  const isLoading = ref(false)

  /** Error state */
  const error = ref<string | null>(null)

  // ============================================================================
  // COMPUTED
  // ============================================================================

  // ============================================================================
  // ACTIONS
  // ============================================================================

  /**
   * Load configs from API; the symbol map is built from config.icon.
   */
  async function loadConfigs() {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/pipeline_configs_with_properties')

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`)
      }

      const data: ConfigsResponse = await response.json()

      // An answer without its list is an error, and it leaves the list that
      // stands in place: assigned first, `undefined` would stand where every
      // reader expects an array (the perspective catalogue reads it in a
      // computed and throws on every update).
      if (!Array.isArray(data?.configs)) {
        throw new Error('API answer carries no configs')
      }

      availableConfigs.value = data.configs


      // Build symbol data map from config.icon (top-level field from backend)
      const newSymbolMap = new Map<string, SymbolData>()
      data.configs.forEach(config => {
        const category = config.properties[0] // Single category value

        if (category && config.icon && !newSymbolMap.has(category)) {
          newSymbolMap.set(category, {
            symbol: config.icon,
            label: '', // No labels - symbol only
            tooltip: ''
          })
        }
      })
      symbolDataMap.value = newSymbolMap

      console.log('[ConfigSelection] Symbol map:', Array.from(newSymbolMap.entries()))


    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error loading configs'
      console.error('[ConfigSelection] Error loading configs:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Get symbol data for a property
   */
  function getSymbolData(property: string): SymbolData | undefined {
    return symbolDataMap.value.get(property)
  }

  // ============================================================================
  // RETURN PUBLIC API
  // ============================================================================

  return {
    // State
    availableConfigs: computed(() => availableConfigs.value),
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),

    // Actions
    loadConfigs,
    getSymbolData
  }
})
