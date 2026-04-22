/**
 * Shared chat model list for Compare Hub tabs.
 * Fetches available models from /api/chat/models on first use.
 * Cloud models always included; local models show availability.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

export interface ChatModelOption {
  id: string
  label: string
  available: boolean
}

// Module-level cache: shared across all component instances
let _fetchPromise: Promise<void> | null = null
const _models = ref<ChatModelOption[]>([])
const _loaded = ref(false)

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

const CLOUD_FALLBACK: ChatModelOption[] = [
  { id: 'mammouth/claude-sonnet-4-6', label: 'Claude Sonnet 4.6', available: true },
  { id: 'mammouth/claude-opus-4-6', label: 'Claude Opus 4.6', available: true },
  { id: 'mammouth/claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5', available: true },
]

async function _fetchModels(): Promise<void> {
  try {
    const res = await fetch(`${getBaseUrl()}/api/chat/models`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    _models.value = (data.models || []).map((m: { id: string; label: string; available?: boolean }) => ({
      id: m.id,
      label: m.label,
      available: m.available !== false,
    }))
  } catch (e) {
    console.warn('[useChatModels] Failed to fetch models, using cloud fallback:', e)
    _models.value = CLOUD_FALLBACK
  } finally {
    _loaded.value = true
  }
}

export function useChatModels() {
  const { t } = useI18n()

  onMounted(() => {
    if (!_fetchPromise) {
      _fetchPromise = _fetchModels()
    }
  })

  const chatModels = computed<ChatModelOption[]>(() => [
    { id: '', label: t('compare.shared.defaultModel'), available: true },
    ..._models.value,
  ])

  const loading = computed(() => !_loaded.value)

  return { chatModels, loading }
}
