<template>
  <!-- Authentication Modal -->
  <SettingsAuthModal v-model="showAuthModal" @authenticated="onAuthenticated" />

  <!-- Settings Content (only show if authenticated) -->
  <div v-if="authenticated" class="settings-container">
    <div class="settings-header">
      <h1>{{ $t('settings.title') }}</h1>
      <div class="tabs">
        <button
          :class="['tab-btn', { active: activeTab === 'config' }]"
          @click="activeTab = 'config'"
        >
          {{ $t('settings.tabs.config') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'matrix' }]"
          @click="activeTab = 'matrix'"
        >
          {{ $t('settings.tabs.matrix') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'api' }]"
          @click="activeTab = 'api'"
        >
          {{ $t('settings.tabs.api') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'status' }]"
          @click="activeTab = 'status'"
        >
          {{ $t('settings.tabs.status') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'export' }]"
          @click="activeTab = 'export'"
        >
          {{ $t('settings.tabs.export') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'demos' }]"
          @click="activeTab = 'demos'"
        >
          {{ $t('settings.tabs.demos') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'knowledge' }]"
          @click="activeTab = 'knowledge'"
        >
          {{ $t('settings.tabs.knowledge') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'loras' }]"
          @click="activeTab = 'loras'"
        >
          {{ $t('settings.tabs.loras') }}
        </button>
      </div>
    </div>

    <!-- API Management Tab -->
    <div v-if="activeTab === 'api'">
      <ApiManagementTab />
    </div>

    <!-- Backend Status Tab -->
    <div v-if="activeTab === 'status'">
      <BackendStatusTab />
    </div>

    <!-- Session Export Tab -->
    <div v-if="activeTab === 'export'">
      <SessionExportView />
    </div>

    <!-- Configuration Tab -->
    <div v-if="activeTab === 'config'">
      <div v-if="loading" class="loading">{{ $t('settings.loading') }}</div>
      <div v-else-if="error" class="error">{{ $t('common.error') }}: {{ error }}</div>

      <div v-else class="settings-content">
      <!-- General Settings -->
      <div class="section">
        <h2>{{ $t('settings.general.title') }}</h2>
        <table class="config-table">
          <tbody>
            <tr>
              <td class="label-cell">{{ $t('settings.general.uiMode') }}</td>
              <td class="value-cell">
                <select v-model="settings.UI_MODE">
                  <option value="easy">{{ $t('settings.general.easy') }}</option>
                  <option value="medium">{{ $t('settings.general.medium') }}</option>
                  <option value="expert">{{ $t('settings.general.expert') }}</option>
                </select>
                <span class="help-text">{{ $t('settings.general.uiModeHelp') }}</span>
                <ul class="help-list">
                  <li>{{ $t('settings.general.uiModeEffectLength') }}</li>
                  <li>{{ $t('settings.general.uiModeEffectStructure') }}</li>
                  <li>{{ $t('settings.general.uiModeEffectStyle') }}</li>
                </ul>
                <span class="help-text">{{ $t('settings.general.uiModeNotSafety') }}</span>
              </td>
            </tr>
            <tr>
              <td class="label-cell">{{ $t('settings.general.safetyLevel') }}</td>
              <td class="value-cell">
                <select v-model="settings.DEFAULT_SAFETY_LEVEL">
                  <option value="kids">Kids</option>
                  <option value="youth">Youth</option>
                  <option value="adult">Adult</option>
                  <option value="research">Research</option>
                </select>

                <div v-if="settings.DEFAULT_SAFETY_LEVEL === 'kids'" class="info-box info-box-success" style="margin-top: 8px; padding: 8px 12px;">
                  <strong style="margin-bottom: 4px;">{{ $t('settings.safety.kidsTitle') }}</strong>
                  <p style="margin: 2px 0;">{{ $t('settings.safety.kidsDesc') }}</p>
                </div>
                <div v-else-if="settings.DEFAULT_SAFETY_LEVEL === 'youth'" class="info-box info-box-success" style="margin-top: 8px; padding: 8px 12px;">
                  <strong style="margin-bottom: 4px;">{{ $t('settings.safety.youthTitle') }}</strong>
                  <p style="margin: 2px 0;">{{ $t('settings.safety.youthDesc') }}</p>
                </div>
                <div v-else-if="settings.DEFAULT_SAFETY_LEVEL === 'adult'" class="info-box" style="margin-top: 8px; padding: 8px 12px; border-color: #ff9800;">
                  <strong style="margin-bottom: 4px;">{{ $t('settings.safety.adultTitle') }}</strong>
                  <p style="margin: 2px 0;">{{ $t('settings.safety.adultDesc') }}</p>
                </div>
                <div v-else-if="settings.DEFAULT_SAFETY_LEVEL === 'research'" class="info-box" style="margin-top: 8px; padding: 8px 12px; border-color: #c62828; border-inline-start: 4px solid #c62828; background: rgba(229, 57, 53, 0.14);">
                  <strong style="margin-bottom: 4px; color: #ff7b72;">{{ $t('settings.safety.researchTitle') }}</strong>
                  <p style="margin: 2px 0;">{{ $t('settings.safety.researchDesc') }}</p>
                </div>
              </td>
            </tr>
            <tr>
              <td class="label-cell">{{ $t('settings.general.defaultLanguage') }}</td>
              <td class="value-cell">
                <select v-model="settings.DEFAULT_LANGUAGE">
                  <option value="ar">{{ $t('settings.general.arabicAr') }}</option>
                  <option value="bg">{{ $t('settings.general.bulgarianBg') }}</option>
                  <option value="de">{{ $t('settings.general.germanDe') }}</option>
                  <option value="en">{{ $t('settings.general.englishEn') }}</option>
                  <option value="es">{{ $t('settings.general.spanishEs') }}</option>
                  <option value="fr">{{ $t('settings.general.frenchFr') }}</option>
                  <option value="he">{{ $t('settings.general.hebrewHe') }}</option>
                  <option value="tr">{{ $t('settings.general.turkishTr') }}</option>
                  <option value="uk">{{ $t('settings.general.ukrainianUk') }}</option>
                  <option value="ko">{{ $t('settings.general.koreanKo') }}</option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Safety Model (local only) -->
      <div class="section">
        <h2>{{ $t('settings.safetyModels.title') }}</h2>
        <p class="help">{{ $t('settings.safetyModels.help') }}</p>
        <table class="config-table">
          <tbody>
            <tr>
              <td class="label-cell">{{ $t('settings.safetyModels.safetyModel') }}</td>
              <td class="value-cell">
                <!-- The checks of prompts, images and person names ask this one model
                     (my_app/services/safety_classifier.py), and the GPU service takes
                     only a model its registry declares a classifier
                     (gpu_service/services/llm_backend.py, "classifier": True). The
                     options are those models. A stored value that is none of them is
                     shown as itself: an empty box would hide what the checks ask. -->
                <select v-model="settings.SAFETY_MODEL">
                  <option value="shieldstral:3b">shieldstral:3b</option>
                  <option
                    v-if="settings.SAFETY_MODEL && settings.SAFETY_MODEL !== 'shieldstral:3b'"
                    :value="settings.SAFETY_MODEL"
                  >{{ settings.SAFETY_MODEL }}</option>
                </select>
                <span class="help-text">{{ $t('settings.safetyModels.safetyModelHelp') }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- What the platform records about the services these roles reach.
           The rule is the backend's (settings_routes._dsgvo_review): which
           service a model id reaches, and what hardware_matrix.json records
           about that service. This page reads that answer and names the parts.
           It must not raise a rule of its own -- the prefix allowlist that used
           to stand here was exactly that, and it held every bare local model
           name for not conform. -->
      <div v-if="hasDsgvoWarning || unrecordedRoles.length" class="section dsgvo-warning">
        <h2>{{ $t('settings.dsgvo.title') }}</h2>

        <template v-if="nonDsgvoModels.length">
          <MarkdownLiteText :text="$t('settings.dsgvo.notCompliant')" />
          <ul>
            <li v-for="entry in nonDsgvoModels" :key="entry.field">
              {{ entry.label }}: <code>{{ modelShort(entry.model) }}</code> &rarr; {{ providerName(entry.service) }}
            </li>
          </ul>
        </template>

        <template v-if="unrecordedRoles.length">
          <p>{{ $t('settings.dsgvo.notRecorded') }}</p>
          <ul>
            <li v-for="entry in unrecordedRoles" :key="entry.field">
              {{ entry.label }}: <code>{{ modelShort(entry.model) }}</code> &rarr; {{ providerName(entry.service) }}
            </li>
          </ul>
        </template>

        <p class="help">
          {{ $t('settings.dsgvo.compliantHint') }}
          <span v-for="(service, idx) in conformServices" :key="service"
            ><span v-if="idx"> | </span><code>{{ service }}</code></span
          >
        </p>
      </div>

      <!-- Model Configuration -->
      <div class="section">
        <h2>{{ $t('settings.models.title') }}</h2>
        <div class="help">
          <MarkdownLiteText :text="$t('settings.presets.help')" />
          <span v-if="gpuInfo.detected" class="gpu-detected" style="display: block; margin-top: 8px;">
            {{ gpuInfo.gpu_name }} ({{ gpuInfo.vram_gb }} GB)
          </span>
        </div>
        <button @click="activeTab = 'matrix'" class="action-btn" style="margin-bottom: 12px;">
          {{ $t('settings.presets.openMatrix') }}
        </button>
        <p class="help">{{ $t('settings.models.help') }}</p>
        <p v-if="llmModels.length > 0" class="help" style="color: #4CAF50;">
          {{ $t('settings.models.localModelsAvailable', { count: llmModels.length }) }}
        </p>

        <table class="config-table">
          <thead>
            <tr>
              <th class="label-cell cap-corner">{{ $t('settings.models.roleColumn') }}</th>
              <th class="value-cell cap-corner">
                <div class="model-row">
                  <span class="model-field">{{ $t('settings.models.modelColumn') }}</span>
                  <span class="cap-head-group">
                    <span class="cap-caption">{{ $t('settings.capabilities.columnCaption') }}</span>
                    <CapabilityStrip head :capabilities="capabilities" />
                  </span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(label, key) in modelLabels" :key="key">
              <td class="label-cell">
                {{ label }}
                <span
                  v-if="defaultsInUse.includes(key)"
                  class="default-badge"
                  title="Running on the platform default -- not explicitly set."
                >DEFAULT</span>
              </td>
              <td class="value-cell">
                <div class="model-row">
                  <!-- The field shows a model the way its provider names it, or
                       by the register's name; the platform id with the provider
                       in front is made by the backend on save and never
                       typed. Which provider it goes through stands
                       under the field once it is saved. The field holds its own
                       draft: what is typed goes into the settings as it stands,
                       and what the settings hold comes back stripped of the
                       prefix -- bound to the settings directly, a re-render of
                       the page (a capability check finishing, the GPU answering)
                       would write the stored value over the text being typed. -->
                  <span class="model-field">
                    <input
                      type="text"
                      v-model="roleDrafts[key]"
                      class="text-input"
                      :list="'llm-models-' + key"
                      @input="onRoleInput(key)"
                    />
                    <datalist :id="'llm-models-' + key">
                      <option v-for="model in llmModels" :key="model.id" :value="model.name">
                        {{ model.name }} ({{ model.size }})
                      </option>
                      <option v-for="m in cloudChoices" :key="m.id" :value="m.path">
                        {{ m.register }} · {{ providerName(m.service) }}
                      </option>
                    </datalist>
                    <span v-if="roleRoute(key)" class="help-text">{{ $t('modelInfo.via', { provider: roleRoute(key) }) }} <DsgvoBadge :recorded="roleRecord(key)" /></span>
                    <span v-else-if="roleWarning(key)" class="help-text cap-note">{{ roleWarning(key) }}</span>
                  </span>
                  <CapabilityStrip
                    :entry="roleEntry(key)"
                    :capabilities="capabilities"
                    :busy="busyFor(key)"
                    @check="cap => checkCapability(key, cap)"
                  />
                </div>
                <p v-for="note in rowNotes(key)" :key="note" class="cap-note">{{ note }}</p>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="capLoadError" class="cap-error">{{ $t('settings.capabilities.loadFailed') }}</p>
      </div>

      <!-- API Configuration -->
      <div class="section">
        <h2>{{ $t('settings.api.title') }}</h2>
        <table class="config-table">
          <tbody>
            <tr v-if="false">
            <!-- LLM Provider selection removed — now using in-process llama-cpp-python via GPU Service -->
          </tr>
          <tr>
            <td class="label-cell">{{ $t('settings.api.externalProvider') }}</td>
            <td class="value-cell">
              <select v-model="settings.EXTERNAL_LLM_PROVIDER">
                <option value="none">{{ $t('settings.api.providerNone') }}</option>
                <option v-for="id in EXTERNAL_PROVIDERS" :key="id" :value="id">{{ providerName(id) }}</option>
              </select>
              <span class="help-text">{{ $t('settings.api.cloudProvider') }}</span>

              <!-- What is recorded about this provider's data path. It is READ from
                   the register (hardware_matrix.json, the same entry the model
                   matrix edits), under the same rule the backend applies: a flag
                   without grounds is not a statement. Six hardcoded verdicts
                   stood here until 2026-09-10, and OpenRouter kept saying "NOT
                   DSGVO-compliant" months after the register said otherwise. -->
              <div v-if="settings.EXTERNAL_LLM_PROVIDER !== 'none'" class="info-box info-box-plain" style="margin-top: 12px;">
                <div class="provider-head">
                  <strong>{{ providerName(settings.EXTERNAL_LLM_PROVIDER) }}</strong>
                  <DsgvoBadge :recorded="providerRecord.recorded" />
                </div>
                <p v-if="providerRecord.note">{{ providerRecord.note }}</p>
                <template v-if="settings.EXTERNAL_LLM_PROVIDER === 'mistral'">
                  <p>API Base URL: https://api.eu.mistral.ai/v1 (Regional Inference EU)</p>
                  <p>API Key: <a href="https://console.mistral.ai/" target="_blank">console.mistral.ai</a></p>
                </template>
                <template v-if="settings.EXTERNAL_LLM_PROVIDER === 'ionos'">
                  <p>API Base URL: https://openai.inference.de-txl.ionos.com/v1</p>
                  <p>Token: <a href="https://dcd.ionos.com/" target="_blank">DCD Token Manager</a></p>
                </template>
                <template v-if="settings.EXTERNAL_LLM_PROVIDER === 'mammouth'">
                  <p>API Base URL: https://api.mammouth.ai/v1</p>
                  <p>API Key: <a href="https://mammouth.ai" target="_blank">mammouth.ai</a></p>
                </template>
              </div>
            </td>
          </tr>
          <!-- One row per provider that keeps a key file, whether or not it is
               the active one: the model list is built over every provider with
               a key, so every key has its field. -->
          <tr v-for="p in keyProviders" :key="p.name">
            <td class="label-cell">{{ $t('settings.api.keyOf', { provider: p.label }) }}</td>
            <td class="value-cell">
              <input
                type="password"
                v-model="providerKeys[p.name]"
                :placeholder="p.key_prefix ? `${p.key_prefix}…` : '…'"
                class="text-input"
              />
              <span class="help-text" v-if="p.masked">{{ $t('settings.api.currentKey') }}: {{ p.masked }}</span>
              <span class="help-text">{{ $t('settings.api.storedIn') }} {{ p.key_path }}</span>
            </td>
          </tr>
          <!-- The external frontier image models and the accounts they run on,
               one row each, built for Gemini 3 Pro Image:
               every output config whose meta marks it `frontier_image`, under
               its own name, with the provider its chunk sends to
               (/api/settings/frontier-image-accounts). The model's route stands
               in its chunk and does not follow the provider above, so the rows
               set nothing. Without a key or credit the model is switched off in the
               Flow and in the model choice of five instruments; a provider of
               its own for it is issue #100. -->
          <tr v-if="frontierFailed">
            <td class="label-cell">{{ $t('settings.api.frontierImageLabel') }}</td>
            <td class="value-cell">{{ $t('settings.apiManagement.billingError') }}: {{ frontierFailed }}</td>
          </tr>
          <template v-for="f in frontierConfigs" :key="f.config_id">
            <tr>
              <td class="label-cell">{{ $t('settings.api.frontierImageLabel') }}</td>
              <td class="value-cell">{{ f.name ? localized(f.name, locale) : f.config_id }}</td>
            </tr>
            <tr>
              <td class="label-cell">{{ $t('settings.api.frontierProviderLabel') }}</td>
              <td class="value-cell">{{ f.provider ? providerName(f.provider) : (f.error || '—') }}</td>
            </tr>
            <tr>
              <td class="label-cell">{{ $t('settings.api.frontierKeyLabel') }}</td>
              <td class="value-cell">{{ f.has_key ? '✓' : '—' }}</td>
            </tr>
            <!-- Only for a provider whose account the check reads and judges
                 (`judged`): for any other its balance would read as
                 unlimited. -->
            <tr v-if="f.judged">
              <td class="label-cell">{{ $t('settings.api.frontierBalanceLabel', { provider: providerName(f.provider) }) }}</td>
              <td class="value-cell">{{ frontierBalanceText(f) }}</td>
            </tr>
          </template>

          </tbody>
        </table>
      </div>

      <!-- Save & Apply Button -->
      <div class="button-row">
        <button @click="saveAndApply" class="save-btn" :disabled="saveInProgress">
          {{ saveInProgress ? $t('settings.save.saving') : $t('settings.save.saveApply') }}
        </button>
        <span v-if="saveMessage" :class="{'save-message': true, 'error-message': !saveSuccess}">
          {{ saveMessage }}
        </span>
      </div>
      </div>
    </div>

    <!-- Minigame Demo Tab -->
    <div v-if="activeTab === 'demos'" class="settings-content">
      <div class="section">
        <h2>{{ $t('settings.testingTools.title') }}</h2>
        <p class="help">
          {{ $t('settings.testingTools.help') }}
        </p>
        <button @click="$router.push('/animation-test')" class="action-btn" style="margin-top: 10px;">
          {{ $t('settings.testingTools.openPreview') }}
        </button>
        <button @click="$router.push('/dev/pixel-editor')" class="action-btn" style="margin-top: 10px; margin-inline-start: 10px;">
          {{ $t('settings.testingTools.pixelEditor') }}
        </button>
        <p class="help" style="margin-top: 10px; font-size: 12px; color: #9a9a9a;">
          {{ $t('settings.testingTools.includes') }}
        </p>
      </div>
    </div>

    <!-- Model Matrix Tab -->
    <div v-if="activeTab === 'matrix'">
      <!-- Only the first load has nothing to show. A reload after an action keeps the
           matrix mounted, so the message about that action stays on screen. -->
      <div v-if="loading && !matrixLoaded" class="loading">{{ $t('settings.loading') }}</div>
      <div v-else-if="error" class="error">{{ $t('common.error') }}: {{ error }}</div>
      <ModelMatrixTab
        v-else
        :matrix="matrix"
        :currentSettings="settings"
        :selectedProvider="settings.EXTERNAL_LLM_PROVIDER || 'none'"
        :detectedVramTier="gpuInfo.vram_tier || null"
        :defaultsInUse="defaultsInUse"
        :lastUserModels="lastUserModels"
        @apply-preset="handleMatrixPresetApply"
        @matrix-updated="loadSettings"
      />
    </div>

    <!-- Knowledge Library Tab -->
    <div v-if="activeTab === 'knowledge'">
      <KnowledgeLibraryTab />
    </div>

    <!-- LoRA register (issue #70): what the Flow offers, to whom, under which model -->
    <div v-if="activeTab === 'loras'">
      <LoraRegisterTab />
    </div>
  </div>
</template>

<script setup>
import SessionExportView from '../components/SessionExportView.vue'
import SettingsAuthModal from '../components/SettingsAuthModal.vue'
import MarkdownLiteText from '../components/MarkdownLiteText.vue'
import ModelMatrixTab from '../components/ModelMatrixTab.vue'
import BackendStatusTab from '../components/BackendStatusTab.vue'
import ApiManagementTab from '../components/ApiManagementTab.vue'
import KnowledgeLibraryTab from '../components/KnowledgeLibraryTab.vue'
import LoraRegisterTab from '../components/LoraRegisterTab.vue'
import CapabilityStrip from '../components/CapabilityStrip.vue'
import DsgvoBadge from '../components/DsgvoBadge.vue'
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { MODEL_ROLES } from '@/data/modelRoles'
import { providerName } from '@/data/providers'
import { localized } from '@/i18n'
import { readDsgvoRecord } from '@/lib/dsgvoRecord'
import { modelShort } from '@/lib/modelPlace'
import { useChatModels } from '@/composables/useChatModels'

const { t, locale } = useI18n()

// Authentication state
const authenticated = ref(false)
const showAuthModal = ref(false)

// The password prompt closed without a password: as a page this left an
// empty page, as a layer (App.vue, since 2026-09-17) it would leave an empty
// frame. The layer closes on this.
const emit = defineEmits(['close'])
watch(showAuthModal, (open) => {
  if (!open && !authenticated.value) emit('close')
})

const activeTab = ref('config')
const loading = ref(true)
const error = ref(null)
const settings = ref({})
const matrix = ref({})
const matrixLoaded = computed(() => Object.keys(matrix.value || {}).length > 0)
const defaultsInUse = ref([])
// What the user set themselves, per row, as recorded by the backend. Read only here --
// the page never derives the DSGVO half of it.
const lastUserModels = ref({})
// True between a column click in the matrix and the save that follows it: that save
// carries the preset's models, so it must not overwrite the record of the user's own
// setting. Cleared by the save itself.
// The rows a click on a column head staged into the form. They travel with the
// next save so the record can keep what they replace instead of them.
const presetStagedFields = ref([])
const gpuInfo = ref({ detected: false, error: null })
// The provider table as the backend serves it (/api/settings/providers): one
// row per provider, with the field its key is sent under, where the key file
// sits and the key as it may be shown. Six pairs of refs and six fetches stood
// here until 2026-09-12, one per provider, and a seventh provider would have
// been a seventh copy.
const providers = ref([])
const keyProviders = computed(() => providers.value.filter(p => p.key_file))
// A new key per provider, typed and not yet saved. Emptied by the save.
const providerKeys = ref({})

async function loadProviders() {
  try {
    const response = await fetch('/api/settings/providers', { credentials: 'include' })
    if (response.ok) {
      const data = await response.json()
      providers.value = data.providers || []
    }
  } catch (e) {
    console.warn('[Settings] Provider table not loaded:', e)
  }
}

// The external frontier image models and the accounts behind them, for their
// rows under the key fields: read by the same check that switches a model off
// in the Flow and in the model choice of five instruments where there is no
// key, the key is refused, or no credit is left
// (devserver/my_app/services/provider_account.py). Which models these are and
// which provider each runs through comes from the output configs and their
// chunks. Empty while they are being read; the rows then stand out of the
// table, since a dash would read as "no key". Where a reading failed, the
// balance row shows the cause the route names in place of a dash: the HTTP
// status, with the proxy's name for the refusal where it gives one, "timeout",
// the class of an exception, or an English sentence of the server. Where the
// route itself failed, one row shows its HTTP status or the browser's message.
// The balance row stands only for a provider whose account the check judges;
// for a config whose chunk names no provider, the provider row shows the
// route's sentence.
const frontierConfigs = ref([])
const frontierFailed = ref('')
// Counts the loads, so that the answer to an earlier one, which reads every
// provider afresh and can arrive after a later one, does not overwrite it.
let frontierLoad = 0

async function loadFrontierAccounts() {
  const mine = ++frontierLoad
  frontierConfigs.value = []
  frontierFailed.value = ''
  try {
    const response = await fetch('/api/settings/frontier-image-accounts', { credentials: 'include' })
    const configs = response.ok ? (await response.json()).configs || [] : null
    if (mine !== frontierLoad) return
    if (configs) frontierConfigs.value = configs
    else frontierFailed.value = `HTTP ${response.status}`
  } catch (e) {
    if (mine !== frontierLoad) return
    console.warn('[Settings] Frontier image accounts not loaded:', e)
    frontierFailed.value = e?.message || String(e)
  }
}

// The account's balance. An account without a budget reads as unlimited, the
// way the API Management tab writes its budget limit; the dash stays for no key.
// Where the check found one of the three budgets it judges used up
// (`used_up`), the row names which one, beside the balance or, for an account
// without a budget, in its place: the key's own budget or its team's can be
// spent while the account's balance stands above zero, and a balance closer
// to zero than half a cent reads $0.00 either way.
function frontierBalanceText(a) {
  const usedUp = a.used_up ? t(`settings.api.frontierUsedUp.${a.used_up}`) : ''
  if (a.balance != null) {
    const shown = `$${(Math.abs(a.balance) < 0.005 ? 0 : a.balance).toFixed(2)}`
    return usedUp ? `${shown} · ${usedUp}` : shown
  }
  if (a.error) return a.error
  if (usedUp) return usedUp
  return a.has_key ? t('settings.apiManagement.unlimited') : '—'
}

// The cloud models the platform offers, for the list under a role field: each
// the way its provider names it, with the provider's name beside it.
const { models: chatModels } = useChatModels()
const cloudChoices = computed(() =>
  chatModels.value
    .filter(m => m.available && m.service && m.service !== 'local')
    .map(m => ({
      id: m.id,
      register: m.register,
      service: m.service,
      path: modelShort(m.id),
    }))
)

/** The provider a saved id goes through, from the id's first segment. */
function roleProvider(key) {
  const value = String(settings.value?.[key] || '')
  return providers.value.find(p => value.startsWith(`${p.name}/`))
}

/** The fields somebody typed into since the page last read the file. What
 *  stands in them is a draft, and the notes under them wait for the save: a
 *  path is judged when it is stored, not letter by letter. */
const typedKeys = ref(new Set())

function onRoleInput(key) {
  typedKeys.value.add(key)
  // A row typed into is the user's own act, whatever a column click put
  // there before: it is resolved and recorded as such, not as the switch.
  presetStagedFields.value = presetStagedFields.value.filter(k => k !== key)
  settings.value[key] = String(roleDrafts.value[key] || '').trim()
}

/** The model as the field shows it: the provider's own path, never the
 *  platform id -- and never the 'local/' the canvas writes in front of a
 *  local model's name (lib/modelPlace, the platform's one reading of an id). */
function roleShown(key) {
  const value = String(settings.value?.[key] || '')
  if (roleProvider(key) || value.startsWith('local/')) return modelShort(value)
  return value
}

/** The provider's name under a SAVED value, or nothing for a local model, a
 *  value still being typed, a path nobody routes, or a provider without a
 *  key here -- the note under the field says those (`roleWarning`). */
function roleRoute(key) {
  if (typedKeys.value.has(key)) return ''
  const p = roleProvider(key)
  return p && p.has_key ? p.label : ''
}

/** What the register records about the data path of the provider a saved
 *  value goes through: true, false, or null for nothing recorded. */
function roleRecord(key) {
  const p = roleProvider(key)
  return p ? readDsgvoRecord(matrix.value?.llm_presets?.[p.name]).recorded : null
}

/** What a field says under itself about a saved value nobody can route: a
 *  path whose first segment is no provider of the table, or a provider the
 *  installation holds no key for. Empty while the value is being typed, and
 *  where it is a route, a local model, or a bare name (which the backend
 *  takes for a local model). */
function roleWarning(key) {
  if (typedKeys.value.has(key)) return ''
  const value = String(settings.value?.[key] || '')
  if (!value.includes('/') || value.startsWith('local/')) return ''
  const head = value.split('/', 1)[0]
  const p = providers.value.find(p => p.name === head)
  if (!p) return t('settings.models.noRoute')
  if (!p.has_key) return t('settings.models.noKey', { provider: p.label })
  return ''
}

const saveMessage = ref('')
const saveSuccess = ref(true)
const saveInProgress = ref(false)
const llmModels = ref([])  // Local LLM model dropdown

// What a role needs of its model, and what was measured about the models that can
// hold it -- see devserver/my_app/services/model_capabilities.
const capabilities = ref([])
const capabilityRoles = ref({})
const capResults = ref({})
const capBusy = ref(new Set())
const capLoadError = ref(false)

// The names and the order come from the one list every surface reads.
const modelLabelKeys = Object.fromEntries(
  MODEL_ROLES.map(role => [role.field, role.labelKey])
)

// What each role field shows: the saved id without its prefix (`roleShown`),
// written whenever the settings change under the field -- the load, a column
// click in the matrix, the save's answer -- and left alone for a field that
// was typed into, until the page reads the file again.
const roleDrafts = ref({})
function refreshDrafts() {
  for (const key of Object.keys(modelLabelKeys)) {
    if (typedKeys.value.has(key)) continue
    roleDrafts.value[key] = roleShown(key)
  }
}
watch(settings, refreshDrafts, { deep: true, immediate: true })

const modelLabels = computed(() => {
  const result = {}
  for (const [key, i18nKey] of Object.entries(modelLabelKeys)) {
    result[key] = t(i18nKey)
  }
  return result
})

// The data-path review, as the backend answered it: per configured role the
// service it reaches and what hardware_matrix.json records about that service.
// Read, never re-derived here -- see the note on the warning box above.
const dsgvoReview = ref([])

// The providers the settings can be switched to are the ones the register
// defines -- llm_presets in hardware_matrix.json -- and what is recorded about
// each one's data path is read from that same entry. Neither the list nor the
// verdict is written here.
const EXTERNAL_PROVIDERS = computed(() => Object.keys(matrix.value?.llm_presets || {}))
const providerRecord = computed(() =>
  readDsgvoRecord(matrix.value?.llm_presets?.[settings.value?.EXTERNAL_LLM_PROVIDER])
)

// Labels for the review. It covers the safety model as well, so it cannot use
// modelLabelKeys: that map also drives the rows of the model table, and the
// safety model has its own table above.
const dsgvoRoleLabelKeys = {
  ...modelLabelKeys,
  'SAFETY_MODEL': 'settings.safetyModels.safetyModel'
}

function namedReview(predicate) {
  return dsgvoReview.value
    .filter(predicate)
    .map(entry => ({
      ...entry,
      label: dsgvoRoleLabelKeys[entry.field] ? t(dsgvoRoleLabelKeys[entry.field]) : entry.field
    }))
}

// Recorded as not conform.
const nonDsgvoModels = computed(() => namedReview(entry => entry.recorded === false))
// Nothing recorded either way. Not knowing is not a verdict, so these are named
// separately rather than folded into the warning above.
const unrecordedRoles = computed(() => namedReview(entry => entry.recorded === null))

const hasDsgvoWarning = computed(() => nonDsgvoModels.value.length > 0)

// What the matrix records as conform, instead of a list of prefixes typed out
// by hand: this installation, plus every provider preset that carries the flag.
const conformServices = computed(() => {
  const presets = (matrix.value && matrix.value.llm_presets) || {}
  return ['local', ...Object.keys(presets).filter(key => presets[key] && presets[key].DSGVO_CONFORMITY)]
})

// Load available local LLM models for dropdown
async function loadLlmModels() {
  try {
    const response = await fetch('/api/settings/llm-models')
    if (response.ok) {
      const data = await response.json()
      if (data.success && data.models) {
        llmModels.value = data.models
        console.log(`[Settings] Loaded ${data.models.length} local LLM models`)
      }
    }
  } catch (e) {
    console.warn('[Settings] Could not load LLM models:', e)
  }
}

function roleEntry(role) {
  return capabilityRoles.value[role] || null
}

function hasModel(role) {
  const entry = roleEntry(role)
  return !!entry && !!entry.model
}

function busyFor(role) {
  return capabilities.value.filter(cap => capBusy.value.has(role + ':' + cap))
}

// A row speaks about the model in its own field. Which model a request reaches when
// that one fails is decided at request time out of the model matrix -- naming one here
// would print a fallback the platform does not have.
function rowNotes(role) {
  const entry = roleEntry(role)
  if (!entry) return []
  const notes = []
  if (hasModel(role) && isUnsaved(role)) notes.push(t('settings.capabilities.unsaved'))
  for (const capability of entry.measurable || []) {
    const result = capResults.value[role + ':' + capability]
    if (result) notes.push(result)
  }
  return notes
}

// The slot describes the model the backend has, not the text in the field: the field
// can be edited without saving, and a measurement belongs to a model string, not to a
// draft. Say so rather than letting the two drift silently.
function isUnsaved(role) {
  const entry = roleEntry(role)
  if (!entry) return false
  return (settings.value[role] || '').trim() !== (entry.model || '').trim()
}

async function loadCapabilities() {
  try {
    const response = await fetch('/api/settings/model-capabilities', { credentials: 'include' })
    if (response.ok) {
      const data = await response.json()
      capabilities.value = data.capabilities || []
      capabilityRoles.value = data.roles || {}
      capLoadError.value = false
    }
    else {
      capLoadError.value = true
    }
  } catch (e) {
    console.warn('[Settings] Could not load model capabilities:', e)
    capLoadError.value = true
  }
}

function capVerdictText(result) {
  const evidence = result.evidence || ''
  if (result.verdict === 'can') return ''
  if (result.verdict === 'cannot') return t('settings.capabilities.verdictCannot', { model: result.model, evidence })
  if (result.verdict === 'unreachable') return t('settings.capabilities.verdictUnreachable', { model: result.model, evidence })
  return t('settings.capabilities.verdictUnclear', { model: result.model, evidence })
}

async function checkCapability(role, capability) {
  const marker = role + ':' + capability
  const busy = new Set(capBusy.value)
  busy.add(marker)
  capBusy.value = busy
  try {
    const response = await fetch('/api/settings/model-capabilities/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ role, capability })
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    const notes = (data.results || []).map(capVerdictText).filter(Boolean)
    capResults.value = { ...capResults.value, [marker]: notes.join(' · ') }
    await loadCapabilities()
  } catch (e) {
    // Silence here left the page byte-identical after a click: a 401, a 400 from the
    // backend and a dead network all looked like nothing having happened.
    console.error('[Settings] Capability check failed:', e)
    capResults.value = {
      ...capResults.value,
      [marker]: t('settings.capabilities.checkFailed', { reason: e.message || String(e) })
    }
  } finally {
    const done = new Set(capBusy.value)
    done.delete(marker)
    capBusy.value = done
  }
}

// The matrix column showing what the user set themselves is the only part of the
// page the save changes without the form knowing. Read it back on its own rather than
// reloading the whole page, which would throw away the form the user is looking at.
async function refreshLastUserModels() {
  try {
    const response = await fetch('/api/settings/', { credentials: 'include' })
    if (!response.ok) return
    const data = await response.json()
    lastUserModels.value = data.last_user_models || {}
  } catch {
    // The record is a display, not a precondition -- a failed read leaves the old one.
  }
}

async function loadSettings() {
  try {
    loading.value = true
    error.value = null

    // Load current settings and matrix
    const response = await fetch('/api/settings/', {  // Trailing slash to match Flask route
      credentials: 'include'
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    // The provider table first, with the keys as they may be shown: the role
    // fields strip a saved id's prefix by it, and they are drawn the moment
    // the settings arrive.
    await loadProviders()
    typedKeys.value = new Set()
    settings.value = data.current
    matrix.value = data.matrix
    defaultsInUse.value = data.defaults_in_use || []
    lastUserModels.value = data.last_user_models || {}
    dsgvoReview.value = data.dsgvo_review || []
    loadCapabilities()
    loadFrontierAccounts()

  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function detectGpu() {
  try {
    const response = await fetch('/api/settings/gpu-info')
    if (response.ok) {
      const data = await response.json()
      gpuInfo.value = data

      if (data.detected && data.vram_tier) {
        console.log(`[Settings] GPU detected: ${data.gpu_name} (${data.vram_gb} GB) → ${data.vram_tier}`)
      }
    }
  } catch (e) {
    console.warn('[Settings] GPU detection failed:', e)
    gpuInfo.value = { detected: false, error: e.message }
  }
}

// fillFromPreset is now handled by handleMatrixPresetApply

// Handler for Matrix tab preset application (new structure)
async function handleMatrixPresetApply(provider) {
  try {
    // Fetch merged preset from backend
    const response = await fetch(`/api/settings/preset/${provider}`, {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const preset = await response.json()

    // Apply all model fields from preset. A row the column sets is the
    // column's again, whatever was typed into it before.
    const staged = []
    Object.keys(modelLabelKeys).forEach(key => {
      if (preset.models && preset.models[key]) {
        typedKeys.value.delete(key)
        settings.value[key] = preset.models[key]
        staged.push(key)
      }
    })
    presetStagedFields.value = [...new Set([...presetStagedFields.value, ...staged])]
    refreshDrafts()

    // Apply provider setting
    settings.value.EXTERNAL_LLM_PROVIDER = preset.EXTERNAL_LLM_PROVIDER

    saveMessage.value = `✓ ${t('settings.save.presetApplied', { preset: preset.label })}`
    saveSuccess.value = true
    setTimeout(() => { saveMessage.value = '' }, 3000)

    // Switch to config tab to show filled values
    activeTab.value = 'config'

  } catch (e) {
    saveMessage.value = `Error applying preset: ${e.message}`
    saveSuccess.value = false
    setTimeout(() => { saveMessage.value = '' }, 5000)
  }
}

async function saveAndApply() {
  try {
    saveInProgress.value = true
    saveMessage.value = t('settings.save.saving')
    saveSuccess.value = true

    // Build payload
    const payload = { ...settings.value }

    // A save right after a column click in the matrix carries that preset's models.
    // The record keeps what they replace, so switching provider during an outage
    // stays reversible.
    payload.PRESET_SWITCH_FIELDS = presetStagedFields.value

    // A new key travels under the field the provider table names for it.
    for (const p of keyProviders.value) {
      const key = String(providerKeys.value[p.name] || '').trim()
      if (key && p.key_field) payload[p.key_field] = key
    }

    // Step 1: Save settings
    const saveResponse = await fetch('/api/settings/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload)
    })

    if (!saveResponse.ok) {
      throw new Error(`Save failed: HTTP ${saveResponse.status}`)
    }
    // What the backend made of the role fields -- the platform ids with the
    // provider in front -- so the fields show the saved state.
    const saved = await saveResponse.json()
    typedKeys.value = new Set()
    Object.assign(settings.value, saved.resolved || {})
    // Also for a typed value the backend stored as written: nothing changed
    // under the field then, and the field still shows the letters typed.
    refreshDrafts()
    presetStagedFields.value = []
    await refreshLastUserModels()

    // Step 2: Apply settings (hot-reload)
    saveMessage.value = t('settings.save.applying')
    const applyResponse = await fetch('/api/settings/reload-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    })

    if (!applyResponse.ok) {
      throw new Error(`Apply failed: HTTP ${applyResponse.status}`)
    }

    // The review describes the applied configuration, not the unsaved state of
    // the form. It comes back with the hot-reload that made it current.
    const applied = await applyResponse.json()
    dsgvoReview.value = applied.dsgvo_review || dsgvoReview.value

    saveMessage.value = `✓ ${t('settings.save.success')}`
    saveSuccess.value = true

    // The slots describe the saved model, so they are stale the moment a new one is
    // saved -- and the note telling the operator to save would otherwise stay up
    // after they did.
    await loadCapabilities()

    // The typed keys are saved; the table shows them masked from now on.
    providerKeys.value = {}
    await loadProviders()
    loadFrontierAccounts()

    setTimeout(() => {
      saveMessage.value = ''
    }, 3000)

  } catch (e) {
    saveMessage.value = 'Error: ' + e.message
    saveSuccess.value = false
  } finally {
    saveInProgress.value = false
  }
}

async function checkAuth() {
  try {
    const response = await fetch('/api/settings/check-auth', {
      credentials: 'include'
    })
    if (response.ok) {
      const data = await response.json()
      authenticated.value = data.authenticated
      if (!authenticated.value) {
        showAuthModal.value = true
      } else {
        // The same as after a fresh sign-in: the settings and the model
        // list. Until 2026-10-10 this path loaded the settings alone, and
        // the list stayed empty for a session that was already open (finding S-040 of the code review of 2026-10-10).
        onAuthenticated()
      }
    } else {
      showAuthModal.value = true
    }
  } catch (e) {
    console.error('Auth check failed:', e)
    showAuthModal.value = true
  }
}

function onAuthenticated() {
  authenticated.value = true
  showAuthModal.value = false
  // Load settings after authentication
  loadSettings()
  // Load local LLM models for dropdown (no auth required)
  loadLlmModels()
}

onMounted(() => {
  checkAuth()
  // Detect GPU immediately (no auth required)
  detectGpu()
})
</script>

<style scoped>
* {
  box-sizing: border-box;
}

.settings-container {
  min-height: 100%;
  background: var(--bg-base);
  /* native controls (select popups, date pickers, scrollbars) follow the dark surface */
  color-scheme: dark;
  padding: 20px;
  padding-bottom: 120px;
  font-family: var(--font-sans);
  color: #fff;
}

.settings-header {
  border-bottom: 2px solid var(--surface-4);
  margin-bottom: 20px;
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
}

.settings-header h1 {
  margin: 0;
  padding: 15px 15px 0 15px;
  font-size: 20px;
  font-weight: 700;
  color: #e0e0e0;
}

.tabs {
  display: flex;
  gap: 0;
  padding: 0 15px;
  margin-top: 10px;
}

.tab-btn {
  padding: 10px 20px;
  background: var(--bg-base);
  border: 1px solid var(--surface-4);
  border-bottom: none;
  cursor: pointer;
  font-size: 14px;
  color: #b0b0b0;
  font-weight: 400;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: var(--surface-2);
}

.tab-btn.active {
  background: var(--surface-1);
  color: #e0e0e0;
  font-weight: 700;
  border-top: 3px solid #007bff;
  padding-top: 8px;
}

.loading, .error {
  padding: 15px;
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  margin-bottom: 20px;
  color: #e0e0e0;
}

.error {
  color: #ff6b6b;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  padding: 15px;
}

.section.dsgvo-warning {
  background: rgba(255, 152, 0, 0.12);
  border: 2px solid #ffc107;
  border-inline-start: 5px solid #ff9800;
}

.section.dsgvo-warning h2 {
  color: #e0b64a;
}

.section.dsgvo-warning ul {
  margin: 10px 0;
  padding-inline-start: 20px;
}

.section.dsgvo-warning li {
  color: #ff9e9e;
  font-family: monospace;
  font-size: 12px;
  margin: 4px 0;
}

.section.dsgvo-warning code {
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 6px;
  border-radius: 3px;
}

.section h2 {
  margin: 0 0 10px 0;
  font-size: 16px;
  font-weight: 700;
  color: #e0e0e0;
}

.section .help {
  margin: 0 0 10px 0;
  font-size: 13px;
  color: #b0b0b0;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--surface-4);
}

.config-table tr {
  border-bottom: 1px solid var(--surface-4);
}

.config-table tr:last-child {
  border-bottom: none;
}

.label-cell {
  width: 250px;
  padding: 8px 12px;
  background: var(--surface-2);
  font-weight: 400;
  font-size: 13px;
  color: #f2f2f2;
  vertical-align: middle;
  text-align: start;
  border-inline-end: 1px solid var(--surface-4);
}

.value-cell {
  padding: 8px 12px;
  background: var(--surface-1);
  text-align: start;
  color: #f2f2f2;
}

.value-cell select,
.value-cell input.text-input {
  padding: 6px 8px;
  border: 1px solid var(--surface-4);
  font-size: 13px;
  font-family: monospace;
  background: var(--surface-1);
  color: #f2f2f2;
  width: 100%;
  max-width: 600px;
}

.value-cell input[type="radio"] {
  margin-inline-end: 5px;
}

.value-cell label {
  margin-inline-end: 15px;
  color: #f2f2f2;
}

.cap-corner {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: #9a9a9a;
}

/* The model field keeps its width; the requirements live in the rest of the same
   column, one fixed slot each, so a slot can be read down the table as a column. */
.model-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.model-field {
  flex: 0 0 320px;
}

.model-field .text-input {
  width: 100%;
}

.cap-head-group {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.cap-caption {
  font-size: 9px;
  letter-spacing: 0.3px;
  color: #8a8a8a;
  text-transform: none;
  font-weight: 400;
}

.cap-error {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.4;
  color: #ff7b72;
}

.cap-note {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.4;
  color: #9a9a9a;
}

.default-badge {
  display: inline-block;
  font-size: 8px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 700;
  background: #ff9800;
  color: #fff;
  margin-inline-start: 6px;
}

.help-text {
  margin-inline-start: 10px;
  color: #b0b0b0;
  font-size: 12px;
}

.help-list {
  margin: 4px 0 6px;
  padding-inline-start: 26px;
  color: #b0b0b0;
  font-size: 12px;
  line-height: 1.5;
}

.action-btn {
  background: var(--surface-4);
  color: #fff;
  border: 1px solid var(--surface-4);
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 400;
}

.action-btn:hover {
  background: #777;
}

.button-row {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
}

.save-btn {
  background: #666;
  color: #fff;
  border: 1px solid var(--surface-4);
  padding: 8px 20px;
  font-size: 14px;
  cursor: pointer;
  font-weight: 400;
}

.save-btn:hover {
  background: #888;
}


.save-message {
  font-size: 13px;
  color: #e0e0e0;
}

.error-message {
  color: #ff6b6b;
}


.info-box {
  padding: 12px 15px;
  background: rgba(255, 152, 0, 0.12);
  border: 1px solid #ffa500;
  border-inline-start: 4px solid #ffa500;
  border-radius: 4px;
  font-size: 13px;
  color: #e0e0e0;
  line-height: 1.5;
}

/* The box carries facts now, and the mark carries the verdict -- so the ground
   is neutral instead of the warning orange that stood under every provider. */
.info-box-plain {
  background: rgb(var(--surface-2-rgb) / 0.6);
  border-color: var(--surface-4);
  border-inline-start-color: var(--surface-4);
}

.provider-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}

.provider-head strong {
  margin-bottom: 0;
}

.info-box-success {
  background: rgba(76, 175, 80, 0.14);
  border-color: #4CAF50;
  border-inline-start-color: #4CAF50;
}

.info-box strong {
  display: block;
  margin-bottom: 8px;
  color: #f2f2f2;
  font-size: 14px;
}

.info-box p {
  margin: 6px 0;
}

.info-box code {
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.info-box ul {
  margin: 8px 0;
  padding-inline-start: 20px;
}

.info-box li {
  margin: 4px 0;
}

.gpu-detected {
  color: #66bb6a !important;
  font-weight: 400;
}

</style>
