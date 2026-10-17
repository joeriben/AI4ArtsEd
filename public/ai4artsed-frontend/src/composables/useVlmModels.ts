/**
 * Shared VLM model list for the Compare Hub "Image Understanding" tab.
 * Fetches installed VLMs from /api/chat/vlm-models on first use.
 * Mirrors useChatModels.ts pattern.
 */
import { ref, computed, onMounted } from 'vue'
import { onInstallDone } from './useModelInstall'
import { apiBase } from '@/services/labApi'

export interface VlmModelOption {
  id: string
  label: string
  available: boolean
  installable: boolean
  approxDownloadMb: number
  /** Which GPU station serves it: the small local VLMs, or the large reader. */
  backend: string
}

let _fetchPromise: Promise<void> | null = null
const _models = ref<VlmModelOption[]>([])
const _loaded = ref(false)

// Auto-refresh when any model install completes.
onInstallDone(() => {
  _fetchPromise = _fetchModels()
})

async function _fetchModels(): Promise<void> {
  try {
    const res = await fetch(`${apiBase()}/api/chat/vlm-models`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    _models.value = (data.models || []).map((m: {
      id: string; label: string; available?: boolean; installable?: boolean
      approx_download_mb?: number; backend?: string
    }) => ({
      id: m.id,
      label: m.label,
      available: m.available !== false,
      installable: m.installable === true,
      approxDownloadMb: m.approx_download_mb || 0,
      backend: m.backend || 'llm',
    }))
  } catch (e) {
    console.warn('[useVlmModels] Failed to fetch VLM models:', e)
    _models.value = []
  } finally {
    _loaded.value = true
  }
}

export function useVlmModels() {
  onMounted(() => {
    if (!_fetchPromise) {
      _fetchPromise = _fetchModels()
    }
  })

  const vlmModels = computed<VlmModelOption[]>(() => _models.value)
  const loading = computed(() => !_loaded.value)

  async function refresh(): Promise<void> {
    _fetchPromise = _fetchModels()
    await _fetchPromise
  }

  return { vlmModels, loading, refresh }
}
