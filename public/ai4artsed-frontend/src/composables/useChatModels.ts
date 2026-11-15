/**
 * Shared chat model list for Compare Hub tabs.
 * Fetches available models from /api/chat/models on first use.
 * Cloud models always included; local models show availability + installable flag.
 *
 * Every entry also says where the text would GO — the service, what the register
 * records about that service, and the grounds it was recorded on. The three
 * states are the platform's own (`components/DsgvoBadge.vue`). Absent fields are
 * the third state, which claims nothing.
 *
 * Since 2026-10-27 the lists show neither: they offer what the settings choose
 * (`chosenModels`), the models of ONE external provider and this machine's, and
 * the settings show that provider and its record. Every list of language
 * models in the Latent Lab and on the Canvas offers a model under the same line
 * (`modelLabel`).
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { onInstallDone } from './useModelInstall'
import { onSettingsApplied } from '@/lib/settingsApplied'
import { bareName, isLocalModel, useModelRegister } from './useModelRegister'
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

/**
 * Which fetch is the latest. A list asked for earlier that answers later is
 * dropped rather than laid over the newer one: an install that completes while
 * a surface is being entered asks twice, and the answer from before the
 * install must not win.
 */
let _generation = 0

/** The latest fetch, while it is under way. */
let _inFlight: Promise<void> | null = null

/**
 * Asks for the list. Surfaces built together ask once: a fetch under way
 * answers for them -- unless the list is asked for `anew`, because an install
 * has completed or the settings were applied, and a fetch asked for before
 * that answers with the list from before.
 */
function _ask(anew: boolean): Promise<void> {
  if (anew || !_inFlight) {
    const fetching: Promise<void> = _fetchModels().finally(() => {
      if (_inFlight === fetching) _inFlight = null
    })
    _inFlight = fetching
  }
  return _settled()
}

/**
 * Until the latest fetch has answered. A fetch overtaken while it is awaited
 * hands its waiters on to the one that overtook it: its own answer is dropped
 * (`_generation`), and returning with it would return before the list.
 */
async function _settled(): Promise<void> {
  while (_inFlight) await _inFlight
}

// Auto-refresh when any model install completes, and when the settings are
// applied (lib/settingsApplied.ts).
onInstallDone(() => {
  void _ask(true)
})
onSettingsApplied(() => {
  void _ask(true)
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
  const mine = ++_generation
  try {
    const res = await fetch(`${apiBase()}/api/chat/models`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (mine !== _generation) return
    _models.value = (data.models || []).map(toOption)
    _chosenModels.value = Array.isArray(data.chosen_models) ? data.chosen_models.map(toOption) : null
    _gpuServiceUnreachable.value = data.gpu_service_unreachable === true
    _loadFailed.value = false
  } catch (e) {
    if (mine !== _generation) return
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
    if (mine === _generation) _loaded.value = true
  }
}

export function useChatModels() {
  const { t, locale } = useI18n()

  // Asked again whenever a surface that offers models is built, not once per
  // session: what the settings choose can change while the page stands open,
  // and a list from before a provider switch would offer the provider before,
  // and send to it.
  onMounted(() => {
    void _ask(false)
  })

  /** What the settings choose, the whole list while that is not known, in
   *  the order every list of models offers them in (useModelRegister.ordered). */
  const chosenModels = computed<ChatModelOption[]>(() => register.ordered(
    _chosenModels.value ?? _models.value,
    m => ({ local: isLocalModel(m.id), key: m.register || m.id, label: modelLabel(m) }),
    locale.value,
  ))

  /** What the settings choose, under the row „Default (Settings)". */
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
    ...chosenModels.value,
  ])

  /**
   * The models the platform actually offers, without the row that stands for
   * „whatever is configured", over every provider that holds a key: the
   * settings page reads it. A surface that offers models to compare reads
   * `chosenModels`.
   */
  const models = computed<ChatModelOption[]>(() => _models.value)

  const loading = computed(() => !_loaded.value)
  /** The list did not arrive. Cleared as soon as one does. */
  const loadFailed = computed(() => _loadFailed.value)
  const gpuServiceUnreachable = computed(() => _gpuServiceUnreachable.value)

  async function refresh(): Promise<void> {
    await _ask(false)
  }

  const register = useModelRegister()

  /**
   * The line a list offers a model under, the same on every surface
   * (useModelRegister.modelLabel): name, maker's country and year, size, and
   * for a model of this machine the word that says so.
   */
  function modelLabel(m: ChatModelOption): string {
    return register.modelLabel(
      m.register || m.id, m.label, locale.value,
      isLocalModel(m.id) ? t('compare.shared.localModel') : '',
    )
  }

  /**
   * What a native <select> says about a model: that line, and for a local model
   * not yet installed, that it is not. Until 2026-10-27 it said how open the
   * weights are, how big the model is in words, which service it reaches and
   * what is recorded about that service's data path.
   */
  function optionLabel(m: ChatModelOption): string {
    const name = modelLabel(m)
    if (!m.available) {
      if (m.installable) {
        return `${name} ⤓ ${t('compare.shared.install.downloadCta', { mb: m.approxDownloadMb })}`
      }
      return `${name} ${t('compare.shared.modelNotDownloaded')}`
    }
    return name
  }

  /**
   * Whether the list a select offers (`chatModels`) names this id. '' is the
   * row „Default (Settings)" and is always there. A surface that keeps a
   * chosen id across a refetch shows the id itself where this is false —
   * otherwise its select stands blank over a choice that is still sent.
   */
  function isListed(id: string): boolean {
    return !id || chosenModels.value.some(m => m.id === id)
  }

  return {
    chatModels, models, chosenModels, loading, loadFailed, gpuServiceUnreachable,
    refresh, optionLabel, modelLabel, isListed,
  }
}
