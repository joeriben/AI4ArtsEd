/**
 * Shared chat model list for Compare Hub tabs.
 * Fetches available models from /api/chat/models on first use.
 * Cloud models always included; local models show availability + installable flag.
 *
 * Every entry also says where the text would GO — the service, what the register
 * records about that service, and the grounds it was recorded on. The three
 * states are the platform's own (`components/DsgvoBadge.vue`), so a surface that
 * offers models can show the mark without making a data-protection statement of
 * its own. Absent fields are the third state, which claims nothing.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { onInstallDone } from './useModelInstall'
import { bareName, useModelRegister } from './useModelRegister'
import { providerName } from '@/data/providers'
import { dsgvoWord } from '@/lib/dsgvoRecord'
import { apiBase } from '@/services/labApi'

export interface ChatModelOption {
  id: string
  label: string
  /** The name the register (useModelRegister) and its lineups key on. Not
   *  always the last segment of the id: a provider may publish a model under
   *  another name, and the backend says which register entry that is. */
  register: string
  available: boolean
  installable: boolean
  approxDownloadMb: number
  /** Which service the id reaches: `local`, or the cloud provider's name. */
  service: string
  /** What the register records about that service: true, false, or nothing. */
  dsgvoRecorded: boolean | null
  /** The grounds the record was set on. Empty where nothing is recorded. */
  dsgvoNote: string
}

// Module-level cache: shared across all component instances
let _fetchPromise: Promise<void> | null = null
const _models = ref<ChatModelOption[]>([])
const _loaded = ref(false)
/**
 * Whether the station that knows the LOCAL models answered. Without it, an
 * installation whose GPU service is down looks exactly like one that offers no
 * local model at all — and a person who picked a model that exists is told they
 * picked one that does not.
 */
const _gpuServiceUnreachable = ref(false)
/**
 * Whether the last attempt to fetch the list came back at all. An empty list and
 * a list that never arrived look the same on a surface, and a surface that shows
 * neither models nor a reason says nothing about either.
 */
const _loadFailed = ref(false)
/**
 * What a surface offers that offers only what the settings choose: this
 * machine's models and every model of the ONE external provider set there
 * (`EXTERNAL_LLM_PROVIDER`), through that provider. The server builds it
 * (`chosen_models`): the full list holds one route per model, and a model the
 * chosen provider reaches can stand there under another provider's id. null
 * while it is not known -- the list did not come, came from a server that
 * does not build it yet, or the server caught the settings mid-save.
 */
const _chosenModels = ref<ChatModelOption[] | null>(null)

// Auto-refresh when any model install completes.
onInstallDone(() => {
  _fetchPromise = _fetchModels()
})

function toOption(m: {
  id: string; label: string; register?: string; available?: boolean
  installable?: boolean; approx_download_mb?: number; service?: string
  dsgvo_recorded?: boolean | null; dsgvo_note?: string
}): ChatModelOption {
  return {
    id: m.id,
    label: m.label,
    register: m.register || bareName(m.id),
    available: m.available !== false,
    installable: m.installable === true,
    approxDownloadMb: m.approx_download_mb || 0,
    service: m.service || '',
    dsgvoRecorded: typeof m.dsgvo_recorded === 'boolean' ? m.dsgvo_recorded : null,
    dsgvoNote: m.dsgvo_note || '',
  }
}

async function _fetchModels(): Promise<void> {
  try {
    const res = await fetch(`${apiBase()}/api/chat/models`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    _models.value = (data.models || []).map(toOption)
    _chosenModels.value = Array.isArray(data.chosen_models) ? data.chosen_models.map(toOption) : null
    _gpuServiceUnreachable.value = data.gpu_service_unreachable === true
    _loadFailed.value = false
  } catch (e) {
    // No substitute list. Which models exist is the platform's answer, and it did not
    // arrive -- naming models here would offer choices that cannot be dispatched. The
    // configured default stays selectable; it is prepended in chatModels.
    console.warn('[useChatModels] Failed to fetch models, offering the configured default only:', e)
    _models.value = []
    _loadFailed.value = true
    _chosenModels.value = null
    // What the station said is untouched: the whole answer is missing, so
    // whether the LOCAL half is reachable is not something this knows either
    // way, and claiming it in either direction would name the wrong cause.
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
    {
      id: '',
      label: t('compare.shared.defaultModel'),
      register: '',
      available: true,
      installable: false,
      approxDownloadMb: 0,
      service: '',
      dsgvoRecorded: null,
      dsgvoNote: '',
    },
    ..._models.value,
  ])

  /**
   * The models the platform actually offers, without the row that stands for
   * „whatever is configured". A surface that DISPATCHES a named model has no
   * use for that row: it is not an id, and sending it would name nothing.
   */
  const models = computed<ChatModelOption[]>(() => _models.value)

  const loading = computed(() => !_loaded.value)
  /** The list did not arrive. Cleared as soon as one does. */
  const loadFailed = computed(() => _loadFailed.value)
  const gpuServiceUnreachable = computed(() => _gpuServiceUnreachable.value)
  /** What the settings choose; the whole list while that is not known. */
  const chosenModels = computed<ChatModelOption[]>(() => _chosenModels.value ?? _models.value)

  async function refresh(): Promise<void> {
    _fetchPromise = _fetchModels()
    await _fetchPromise
  }

  const register = useModelRegister()

  /**
   * What a native <select> can say about a model, in one line: its name; where
   * the register knows it, how open its weights are and how big it is; where
   * it leaves the machine, through which service and what the register records
   * about that service's data path. A local model not yet installed says so
   * instead. The three compare tabs each kept a copy of the first half until
   * 2026-09-12.
   */
  function optionLabel(m: ChatModelOption): string {
    if (!m.available) {
      if (m.installable) {
        return `${m.label} ⤓ ${t('compare.shared.install.downloadCta', { mb: m.approxDownloadMb })}`
      }
      return `${m.label} ${t('compare.shared.modelNotDownloaded')}`
    }
    const parts = [m.label]
    const facts = register.qualification(m.register || m.id, t)
    if (facts) parts.push(facts)
    if (m.service && m.service !== 'local') {
      parts.push(t('modelInfo.via', { provider: providerName(m.service) }))
      parts.push(dsgvoWord(m.dsgvoRecorded, t))
    }
    return parts.join(' · ')
  }

  /**
   * Whether the list names this id. '' is the row „Default (Settings)" and is
   * always there. A surface that keeps a chosen id across a refetch shows the
   * id itself where this is false — otherwise its select stands blank over
   * a choice that is still sent.
   */
  function isListed(id: string): boolean {
    return !id || _models.value.some(m => m.id === id)
  }

  return {
    chatModels, models, chosenModels, loading, loadFailed, gpuServiceUnreachable,
    refresh, optionLabel, isListed,
  }
}
