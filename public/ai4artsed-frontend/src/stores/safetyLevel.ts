import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { apiBase } from '@/services/labApi'

export const useSafetyLevelStore = defineStore('safetyLevel', () => {
  const level = ref<string>('kids') // safest default until fetch completes
  const loaded = ref(false)
  // `loaded` means the fetch has been attempted, so nobody fetches twice.
  // `resolved` means an answer actually arrived. The `kids` above is the
  // safe default for GATING and a claim a display must not make: until this
  // is true, nothing here has been told what filter holds.
  const resolved = ref(false)

  async function fetchLevel() {
    try {
      const baseUrl = apiBase()
      // withCredentials, like every call in labAuth.ts: without the session
      // cookie the endpoint reports the anonymous installation level, so a
      // course-bound participant would be gated as if not logged in.
      const { data } = await axios.get(`${baseUrl}/api/settings/safety-level`, { withCredentials: true })
      level.value = data.safety_level
      resolved.value = true
      loaded.value = true
    } catch (e) {
      console.error('[SafetyLevel] Failed to fetch safety level:', e)
      // Keep 'kids' as safe default
      loaded.value = true
    }
  }

  // The lock on the Canvas and the Latent Lab that read `isAdvancedMode`,
  // `isResearchMode` and a per-session research confirmation was never
  // activated (no route carried its meta, no feature its flag) and went on
  // 2026-10-10 (S-061; docs/DEVELOPMENT_DECISIONS.md).
  return { level, loaded, resolved, fetchLevel }
})
