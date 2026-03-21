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
          :class="['tab-btn', { active: activeTab === 'demos' }]"
          @click="activeTab = 'demos'"
        >
          {{ $t('settings.tabs.demos') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'export' }]"
          @click="activeTab = 'export'"
        >
          {{ $t('settings.tabs.export') }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'status' }]"
          @click="activeTab = 'status'"
        >
          {{ $t('settings.tabs.status') }}
        </button>
      </div>
    </div>

    <!-- Session Export Tab -->
    <div v-if="activeTab === 'export'">
      <SessionExportView />
    </div>

    <!-- Backend Status Tab -->
    <div v-if="activeTab === 'status'">
      <BackendStatusTab />
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
                  <option value="kids">{{ $t('settings.general.kids') }}</option>
                  <option value="youth">{{ $t('settings.general.youth') }}</option>
                  <option value="expert">{{ $t('settings.general.expert') }}</option>
                </select>
                <span class="help-text">{{ $t('settings.general.uiModeHelp') }}</span>
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
                <div v-else-if="settings.DEFAULT_SAFETY_LEVEL === 'research'" class="info-box" style="margin-top: 8px; padding: 8px 12px; border-color: #c62828; border-inline-start: 4px solid #c62828; background: #ffebee;">
                  <strong style="margin-bottom: 4px; color: #c62828;">{{ $t('settings.safety.researchTitle') }}</strong>
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

      <!-- Safety Models (local Ollama only) -->
      <div class="section">
        <h2>{{ $t('settings.safetyModels.title') }}</h2>
        <p class="help">{{ $t('settings.safetyModels.help') }}</p>
        <table class="config-table">
          <tbody>
            <tr>
              <td class="label-cell">{{ $t('settings.safetyModels.safetyModel') }}</td>
              <td class="value-cell">
                <select v-model="settings.SAFETY_MODEL">
                  <option value="llama-guard3:1b">llama-guard3:1b ({{ $t('settings.safetyModels.fast') }})</option>
                  <option value="llama-guard3:latest">llama-guard3:latest</option>
                  <option value="llama-guard3:8b">llama-guard3:8b</option>
                </select>
                <span class="help-text">{{ $t('settings.safetyModels.safetyModelHelp') }}</span>
              </td>
            </tr>
            <tr>
              <td class="label-cell">{{ $t('settings.safetyModels.dsgvoModel') }}</td>
              <td class="value-cell">
                <select v-model="settings.DSGVO_VERIFY_MODEL">
                  <option value="qwen3:1.7b">qwen3:1.7b (~1.5 GB VRAM, {{ $t('settings.safetyModels.recommended') }})</option>
                  <option value="gemma3:1b">gemma3:1b (~1.0 GB VRAM)</option>
                  <option value="qwen2.5:1.5b">qwen2.5:1.5b (~1.2 GB VRAM)</option>
                  <option value="llama3.2:1b">llama3.2:1b (~1.3 GB VRAM)</option>
                  <option value="qwen3:0.6b">qwen3:0.6b (~0.6 GB VRAM, minimal)</option>
                </select>
                <span class="help-text">{{ $t('settings.safetyModels.dsgvoModelHelp') }}</span>
              </td>
            </tr>
            <tr>
              <td class="label-cell">{{ $t('settings.safetyModels.vlmModel') }}</td>
              <td class="value-cell">
                <select v-model="settings.VLM_SAFETY_MODEL">
                  <option value="qwen3-vl:2b">qwen3-vl:2b (~2 GB VRAM, {{ $t('settings.safetyModels.recommended') }})</option>
                  <option value="qwen3-vl:8b">qwen3-vl:8b (~5 GB VRAM)</option>
                  <option value="llama3.2-vision:latest">llama3.2-vision:latest (~8 GB VRAM)</option>
                </select>
                <span class="help-text">{{ $t('settings.safetyModels.vlmModelHelp') }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- DSGVO Warning -->
      <div v-if="hasDsgvoWarning" class="section dsgvo-warning">
        <h2>{{ $t('settings.dsgvo.title') }}</h2>
        <p v-html="$t('settings.dsgvo.notCompliant')"></p>
        <ul>
          <li v-for="model in nonDsgvoModels" :key="model">{{ model }}</li>
        </ul>
        <p class="help">{{ $t('settings.dsgvo.compliantHint') }} <code>local/*</code> | <code>mistral/*</code> | <code>ionos/*</code> | <code>mammouth/*</code></p>
      </div>

      <!-- Model Configuration -->
      <div class="section">
        <h2>{{ $t('settings.models.title') }}</h2>
        <p class="help">
          <span v-html="$t('settings.presets.help')"></span>
          <span v-if="gpuInfo.detected" class="gpu-detected" style="display: block; margin-top: 8px;">
            {{ gpuInfo.gpu_name }} ({{ gpuInfo.vram_gb }} GB)
          </span>
        </p>
        <button @click="activeTab = 'matrix'" class="action-btn" style="margin-bottom: 12px;">
          {{ $t('settings.presets.openMatrix') }}
        </button>
        <p class="help">{{ $t('settings.models.help') }}</p>
        <p v-if="ollamaModels.length > 0" class="help" style="color: #4CAF50;">
          {{ $t('settings.models.ollamaAvailable', { count: ollamaModels.length }) }}
        </p>

        <table class="config-table">
          <tbody>
            <tr v-for="(label, key) in modelLabels" :key="key">
              <td class="label-cell">{{ label }}</td>
              <td class="value-cell">
                <input
                  type="text"
                  v-model="settings[key]"
                  class="text-input"
                  :list="'ollama-models-' + key"
                />
                <datalist :id="'ollama-models-' + key">
                  <option v-for="model in ollamaModels" :key="model.id" :value="model.id">
                    {{ model.name }} ({{ model.size }})
                  </option>
                </datalist>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- API Configuration -->
      <div class="section">
        <h2>{{ $t('settings.api.title') }}</h2>
        <table class="config-table">
          <tbody>
            <tr>
              <td class="label-cell">{{ $t('settings.api.llmProvider') }}</td>
            <td class="value-cell">
              <select v-model="settings.LLM_PROVIDER">
                <option value="ollama">Ollama</option>
                <option value="lmstudio">LM Studio</option>
              </select>
              <span class="help-text">{{ $t('settings.api.localFramework') }}</span>
            </td>
          </tr>
          <tr>
            <td class="label-cell">Ollama API URL</td>
            <td class="value-cell">
              <input type="text" v-model="settings.OLLAMA_API_BASE_URL" class="text-input" />
            </td>
          </tr>
          <tr>
            <td class="label-cell">LM Studio API URL</td>
            <td class="value-cell">
              <input type="text" v-model="settings.LMSTUDIO_API_BASE_URL" class="text-input" />
            </td>
          </tr>
          <tr>
            <td class="label-cell">{{ $t('settings.api.externalProvider') }}</td>
            <td class="value-cell">
              <select v-model="settings.EXTERNAL_LLM_PROVIDER">
                <option value="none">{{ $t('settings.api.noneLocal') }}</option>
                <option value="mistral">{{ $t('settings.api.mistralEu') }}</option>
                <option value="ionos">{{ $t('settings.api.ionosEu') }}</option>
                <option value="mammouth">{{ $t('settings.api.mammouthEu') }}</option>
                <option value="anthropic">{{ $t('settings.api.anthropicDirect') }}</option>
                <option value="openai">{{ $t('settings.api.openaiDirect') }}</option>
                <option value="openrouter">{{ $t('settings.api.openrouterDirect') }}</option>
              </select>
              <span class="help-text">{{ $t('settings.api.cloudProvider') }}</span>

              <!-- Provider info boxes -->
              <div v-if="settings.EXTERNAL_LLM_PROVIDER === 'mistral'" class="info-box info-box-success" style="margin-top: 12px;">
                <strong>{{ $t('settings.api.mistralInfo') }}</strong>
                <p>{{ $t('settings.api.mistralDsgvo') }}</p>
                <p>API Base URL: https://api.mistral.ai/v1</p>
                <p>API Key: <a href="https://console.mistral.ai/" target="_blank">console.mistral.ai</a></p>
              </div>

              <div v-if="settings.EXTERNAL_LLM_PROVIDER === 'ionos'" class="info-box info-box-success" style="margin-top: 12px;">
                <strong>{{ $t('settings.api.ionosInfo') }}</strong>
                <p>{{ $t('settings.api.ionosDsgvo') }}</p>
                <p>API Base URL: https://openai.inference.de-txl.ionos.com/v1</p>
                <p>Token: <a href="https://dcd.ionos.com/" target="_blank">DCD Token Manager</a></p>
              </div>

              <div v-if="settings.EXTERNAL_LLM_PROVIDER === 'mammouth'" class="info-box info-box-success" style="margin-top: 12px;">
                <strong>{{ $t('settings.api.mammouthInfo') }}</strong>
                <p>{{ $t('settings.api.mammouthDsgvo') }}</p>
                <p>API Base URL: https://api.mammouth.ai/v1</p>
                <p>API Key: <a href="https://mammouth.ai" target="_blank">mammouth.ai</a></p>
              </div>

              <div v-if="settings.EXTERNAL_LLM_PROVIDER === 'anthropic'" class="info-box" style="margin-top: 12px; border-color: #ff9800;">
                <strong>{{ $t('settings.api.anthropicInfo') }}</strong>
                <p>{{ $t('settings.api.anthropicNotDsgvo') }}</p>
                <p>{{ $t('settings.api.anthropicWarning') }}</p>
              </div>

              <div v-if="settings.EXTERNAL_LLM_PROVIDER === 'openai'" class="info-box" style="margin-top: 12px; border-color: #ff9800;">
                <strong>{{ $t('settings.api.openaiInfo') }}</strong>
                <p>{{ $t('settings.api.openaiNotDsgvo') }}</p>
                <p>{{ $t('settings.api.openaiWarning') }}</p>
              </div>

              <div v-if="settings.EXTERNAL_LLM_PROVIDER === 'openrouter'" class="info-box" style="margin-top: 12px; border-color: #ff9800;">
                <strong>{{ $t('settings.api.openrouterInfo') }}</strong>
                <p>{{ $t('settings.api.openrouterNotDsgvo') }}</p>
                <p>{{ $t('settings.api.openrouterWarning') }}</p>
              </div>
            </td>
          </tr>
          <!-- API Key field - conditional based on selected provider -->
          <tr v-if="settings.EXTERNAL_LLM_PROVIDER === 'openrouter'">
            <td class="label-cell">OpenRouter API Key</td>
            <td class="value-cell">
              <input
                type="password"
                v-model="openrouterKey"
                placeholder="sk-or-v1-..."
                class="text-input"
              />
              <span class="help-text" v-if="openrouterKeyMasked">{{ $t('settings.api.currentKey') }}: {{ openrouterKeyMasked }}</span>
              <span class="help-text">{{ $t('settings.api.storedIn') }} devserver/openrouter.key</span>
            </td>
          </tr>

          <tr v-if="settings.EXTERNAL_LLM_PROVIDER === 'anthropic'">
            <td class="label-cell">Anthropic API Key</td>
            <td class="value-cell">
              <input
                type="password"
                v-model="anthropicKey"
                placeholder="sk-ant-api03-..."
                class="text-input"
              />
              <span class="help-text" v-if="anthropicKeyMasked">{{ $t('settings.api.currentKey') }}: {{ anthropicKeyMasked }}</span>
              <span class="help-text">{{ $t('settings.api.storedIn') }} devserver/anthropic.key</span>
            </td>
          </tr>

          <tr v-if="settings.EXTERNAL_LLM_PROVIDER === 'openai'">
            <td class="label-cell">OpenAI API Key</td>
            <td class="value-cell">
              <input
                type="password"
                v-model="openaiKey"
                placeholder="sk-proj-..."
                class="text-input"
              />
              <span class="help-text" v-if="openaiKeyMasked">{{ $t('settings.api.currentKey') }}: {{ openaiKeyMasked }}</span>
              <span class="help-text">{{ $t('settings.api.storedIn') }} devserver/openai.key</span>
            </td>
          </tr>

          <tr v-if="settings.EXTERNAL_LLM_PROVIDER === 'mistral'">
            <td class="label-cell">Mistral API Key</td>
            <td class="value-cell">
              <input
                type="password"
                v-model="mistralKey"
                placeholder="..."
                class="text-input"
              />
              <span class="help-text" v-if="mistralKeyMasked">{{ $t('settings.api.currentKey') }}: {{ mistralKeyMasked }}</span>
              <span class="help-text">{{ $t('settings.api.storedIn') }} devserver/mistral.key</span>
            </td>
          </tr>

          <tr v-if="settings.EXTERNAL_LLM_PROVIDER === 'ionos'">
            <td class="label-cell">IONOS Token Value</td>
            <td class="value-cell">
              <input
                type="password"
                v-model="ionosKey"
                placeholder="eyJ0eXAi..."
                class="text-input"
              />
              <span class="help-text" v-if="ionosKeyMasked">{{ $t('settings.api.currentKey') }}: {{ ionosKeyMasked }}</span>
              <span class="help-text">{{ $t('settings.api.storedIn') }} devserver/ionos.key</span>
            </td>
          </tr>

          <tr v-if="settings.EXTERNAL_LLM_PROVIDER === 'mammouth'">
            <td class="label-cell">Mammouth API Key</td>
            <td class="value-cell">
              <input
                type="password"
                v-model="mammouthKey"
                placeholder="..."
                class="text-input"
              />
              <span class="help-text" v-if="mammouthKeyMasked">{{ $t('settings.api.currentKey') }}: {{ mammouthKeyMasked }}</span>
              <span class="help-text">{{ $t('settings.api.storedIn') }} devserver/mammouth.key</span>
            </td>
          </tr>

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
        <p class="help" style="margin-top: 10px; font-size: 12px; color: #888;">
          {{ $t('settings.testingTools.includes') }}
        </p>
      </div>
    </div>

    <!-- Model Matrix Tab -->
    <div v-if="activeTab === 'matrix'">
      <div v-if="loading" class="loading">{{ $t('settings.loading') }}</div>
      <div v-else-if="error" class="error">{{ $t('common.error') }}: {{ error }}</div>
      <ModelMatrixTab
        v-else
        :matrix="matrix"
        :currentSettings="settings"
        :selectedProvider="settings.EXTERNAL_LLM_PROVIDER || 'none'"
        :detectedVramTier="gpuInfo.vram_tier || null"
        @apply-preset="handleMatrixPresetApply"
        @matrix-updated="loadSettings"
      />
    </div>
  </div>
</template>

<script setup>
import SessionExportView from '../components/SessionExportView.vue'
import SettingsAuthModal from '../components/SettingsAuthModal.vue'
import ModelMatrixTab from '../components/ModelMatrixTab.vue'
import BackendStatusTab from '../components/BackendStatusTab.vue'
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Authentication state
const authenticated = ref(false)
const showAuthModal = ref(false)

const activeTab = ref('config')
const loading = ref(true)
const error = ref(null)
const settings = ref({})
const matrix = ref({})
const gpuInfo = ref({ detected: false, error: null })
const openrouterKey = ref('')
const openrouterKeyMasked = ref('')
const anthropicKey = ref('')
const anthropicKeyMasked = ref('')
const openaiKey = ref('')
const openaiKeyMasked = ref('')
const mistralKey = ref('')
const mistralKeyMasked = ref('')
const ionosKey = ref('')
const ionosKeyMasked = ref('')
const mammouthKey = ref('')
const mammouthKeyMasked = ref('')
const awsCredentialsConfigured = ref(false)
const saveMessage = ref('')
const saveSuccess = ref(true)
const saveInProgress = ref(false)
const ollamaModels = ref([])  // Session 133: Ollama model dropdown

const modelLabelKeys = {
  'STAGE1_TEXT_MODEL': 'settings.models.stage1Text',
  'STAGE2_INTERCEPTION_MODEL': 'settings.models.stage2Interception',
  'STAGE2_OPTIMIZATION_MODEL': 'settings.models.stage2Optimization',
  'STAGE3_MODEL': 'settings.models.stage3',
  'STAGE4_LEGACY_MODEL': 'settings.models.stage4Legacy',
  'CHAT_HELPER_MODEL': 'settings.models.chatHelper',
  'PERSONA_MODEL': 'settings.models.persona',
  'IMAGE_ANALYSIS_MODEL': 'settings.models.imageAnalysis',
  'CODING_MODEL': 'settings.models.coding'
}

const modelLabels = computed(() => {
  const result = {}
  for (const [key, i18nKey] of Object.entries(modelLabelKeys)) {
    result[key] = t(i18nKey)
  }
  return result
})

// Check for non-DSGVO-compliant models
// DSGVO-compliant: local/ (local models), mistral/ (EU-based)
// NOT DSGVO-compliant: anthropic/, openai/, openrouter/, google/, etc.
const nonDsgvoModels = computed(() => {
  const problematic = []
  const labels = modelLabels.value
  Object.keys(modelLabelKeys).forEach(key => {
    const modelValue = settings.value[key] || ''
    if (modelValue && !modelValue.startsWith('local/') && !modelValue.startsWith('mistral/') && !modelValue.startsWith('ionos/') && !modelValue.startsWith('mammouth/')) {
      problematic.push(`${labels[key]}: ${modelValue}`)
    }
  })
  return problematic
})

const hasDsgvoWarning = computed(() => {
  return nonDsgvoModels.value.length > 0
})

// Session 133: Load available Ollama models for dropdown
async function loadOllamaModels() {
  try {
    const response = await fetch('/api/settings/ollama-models')
    if (response.ok) {
      const data = await response.json()
      if (data.success && data.models) {
        ollamaModels.value = data.models
        console.log(`[Settings] Loaded ${data.models.length} Ollama models`)
      }
    }
  } catch (e) {
    console.warn('[Settings] Could not load Ollama models:', e)
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
    settings.value = data.current
    matrix.value = data.matrix

    // Load API key statuses
    const keyResponse = await fetch('/api/settings/openrouter-key', {
      credentials: 'include'
    })
    if (keyResponse.ok) {
      const keyData = await keyResponse.json()
      if (keyData.exists) {
        openrouterKeyMasked.value = keyData.masked
      }
    }

    const anthropicResponse = await fetch('/api/settings/anthropic-key', {
      credentials: 'include'
    })
    if (anthropicResponse.ok) {
      const anthropicData = await anthropicResponse.json()
      if (anthropicData.exists) {
        anthropicKeyMasked.value = anthropicData.masked
      }
    }

    const openaiResponse = await fetch('/api/settings/openai-key', {
      credentials: 'include'
    })
    if (openaiResponse.ok) {
      const openaiData = await openaiResponse.json()
      if (openaiData.exists) {
        openaiKeyMasked.value = openaiData.masked
      }
    }

    const mistralResponse = await fetch('/api/settings/mistral-key', {
      credentials: 'include'
    })
    if (mistralResponse.ok) {
      const mistralData = await mistralResponse.json()
      if (mistralData.exists) {
        mistralKeyMasked.value = mistralData.masked
      }
    }

    const ionosResponse = await fetch('/api/settings/ionos-key', {
      credentials: 'include'
    })
    if (ionosResponse.ok) {
      const ionosData = await ionosResponse.json()
      if (ionosData.exists) {
        ionosKeyMasked.value = ionosData.masked
      }
    }

    const mammouthResponse = await fetch('/api/settings/mammouth-key', {
      credentials: 'include'
    })
    if (mammouthResponse.ok) {
      const mammouthData = await mammouthResponse.json()
      if (mammouthData.exists) {
        mammouthKeyMasked.value = mammouthData.masked
      }
    }

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

    // Apply all model fields from preset
    Object.keys(modelLabelKeys).forEach(key => {
      if (preset.models && preset.models[key]) {
        settings.value[key] = preset.models[key]
      }
    })

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

async function handleAwsCsvUpload(event) {
  const file = event.target.files[0]
  if (!file) return

  try {
    const text = await file.text()
    const formData = new FormData()
    formData.append('csv', file)

    const response = await fetch('/api/settings/aws-credentials', {
      method: 'POST',
      body: formData
    })

    const result = await response.json()

    if (response.ok) {
      awsCredentialsConfigured.value = true
      saveMessage.value = '✓ AWS credentials uploaded successfully. Click "Apply Settings" to activate.'
      saveSuccess.value = true
    } else {
      throw new Error(result.error || 'Upload failed')
    }
  } catch (err) {
    saveMessage.value = `Error uploading AWS credentials: ${err.message}`
    saveSuccess.value = false
  }

  setTimeout(() => { saveMessage.value = '' }, 5000)
}

async function saveAndApply() {
  try {
    saveInProgress.value = true
    saveMessage.value = t('settings.save.saving')
    saveSuccess.value = true

    // Build payload
    const payload = { ...settings.value }

    // Add API keys if provided
    if (openrouterKey.value) {
      payload.OPENROUTER_API_KEY = openrouterKey.value
    }
    if (anthropicKey.value) {
      payload.ANTHROPIC_API_KEY = anthropicKey.value
    }
    if (openaiKey.value) {
      payload.OPENAI_API_KEY = openaiKey.value
    }
    if (mistralKey.value) {
      payload.MISTRAL_API_KEY = mistralKey.value
    }
    if (ionosKey.value) {
      payload.IONOS_API_KEY = ionosKey.value
    }
    if (mammouthKey.value) {
      payload.MAMMOUTH_API_KEY = mammouthKey.value
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

    saveMessage.value = `✓ ${t('settings.save.success')}`
    saveSuccess.value = true

    // Clear API key inputs and reload masked versions after successful save
    if (openrouterKey.value) {
      openrouterKey.value = ''
      const keyResponse = await fetch('/api/settings/openrouter-key', {
        credentials: 'include'
      })
      if (keyResponse.ok) {
        const keyData = await keyResponse.json()
        if (keyData.exists) {
          openrouterKeyMasked.value = keyData.masked
        }
      }
    }

    if (anthropicKey.value) {
      anthropicKey.value = ''
      const anthropicResponse = await fetch('/api/settings/anthropic-key', {
        credentials: 'include'
      })
      if (anthropicResponse.ok) {
        const anthropicData = await anthropicResponse.json()
        if (anthropicData.exists) {
          anthropicKeyMasked.value = anthropicData.masked
        }
      }
    }

    if (openaiKey.value) {
      openaiKey.value = ''
      const openaiResponse = await fetch('/api/settings/openai-key', {
        credentials: 'include'
      })
      if (openaiResponse.ok) {
        const openaiData = await openaiResponse.json()
        if (openaiData.exists) {
          openaiKeyMasked.value = openaiData.masked
        }
      }
    }

    if (mistralKey.value) {
      mistralKey.value = ''
      const mistralResponse = await fetch('/api/settings/mistral-key', {
        credentials: 'include'
      })
      if (mistralResponse.ok) {
        const mistralData = await mistralResponse.json()
        if (mistralData.exists) {
          mistralKeyMasked.value = mistralData.masked
        }
      }
    }

    if (ionosKey.value) {
      ionosKey.value = ''
      const ionosResponse = await fetch('/api/settings/ionos-key', {
        credentials: 'include'
      })
      if (ionosResponse.ok) {
        const ionosData = await ionosResponse.json()
        if (ionosData.exists) {
          ionosKeyMasked.value = ionosData.masked
        }
      }
    }

    if (mammouthKey.value) {
      mammouthKey.value = ''
      const mammouthResponse = await fetch('/api/settings/mammouth-key', {
        credentials: 'include'
      })
      if (mammouthResponse.ok) {
        const mammouthData = await mammouthResponse.json()
        if (mammouthData.exists) {
          mammouthKeyMasked.value = mammouthData.masked
        }
      }
    }

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
        // Load settings only if authenticated
        loadSettings()
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
  // Session 133: Load Ollama models for dropdown (no auth required)
  loadOllamaModels()
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
  min-height: 100vh;
  background: #000;
  padding: 20px;
  padding-bottom: 120px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  color: #fff;
}

.settings-header {
  border-bottom: 2px solid #ccc;
  margin-bottom: 20px;
  background: #fff;
  border: 1px solid #ccc;
}

.settings-header h1 {
  margin: 0;
  padding: 15px 15px 0 15px;
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.tabs {
  display: flex;
  gap: 0;
  padding: 0 15px;
  margin-top: 10px;
}

.tab-btn {
  padding: 10px 20px;
  background: #e0e0e0;
  border: 1px solid #ccc;
  border-bottom: none;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  font-weight: 500;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: #d0d0d0;
}

.tab-btn.active {
  background: #fff;
  color: #333;
  font-weight: 600;
  border-top: 3px solid #007bff;
  padding-top: 8px;
}

.loading, .error {
  padding: 15px;
  background: #fff;
  border: 1px solid #ccc;
  margin-bottom: 20px;
  color: #333;
}

.error {
  color: #c00;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  background: #fff;
  border: 1px solid #ccc;
  padding: 15px;
}

.section.dsgvo-warning {
  background: #fff3cd;
  border: 2px solid #ffc107;
  border-inline-start: 5px solid #ff9800;
}

.section.dsgvo-warning h2 {
  color: #856404;
}

.section.dsgvo-warning ul {
  margin: 10px 0;
  padding-inline-start: 20px;
}

.section.dsgvo-warning li {
  color: #721c24;
  font-family: monospace;
  font-size: 12px;
  margin: 4px 0;
}

.section.dsgvo-warning code {
  background: rgba(0,0,0,0.1);
  padding: 2px 6px;
  border-radius: 3px;
}

.section h2 {
  margin: 0 0 10px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.section .help {
  margin: 0 0 10px 0;
  font-size: 13px;
  color: #666;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #999;
}

.config-table tr {
  border-bottom: 1px solid #999;
}

.config-table tr:last-child {
  border-bottom: none;
}

.label-cell {
  width: 250px;
  padding: 8px 12px;
  background: #f0f0f0;
  font-weight: 500;
  font-size: 13px;
  color: #000;
  vertical-align: middle;
  text-align: start;
  border-inline-end: 1px solid #999;
}

.value-cell {
  padding: 8px 12px;
  background: #fff;
  text-align: start;
  color: #000;
}

.value-cell select,
.value-cell input.text-input {
  padding: 6px 8px;
  border: 1px solid #ccc;
  font-size: 13px;
  font-family: monospace;
  background: white;
  color: #000;
  width: 100%;
  max-width: 600px;
}

.value-cell input[type="radio"] {
  margin-inline-end: 5px;
}

.value-cell label {
  margin-inline-end: 15px;
  color: #000;
}

.help-text {
  margin-inline-start: 10px;
  color: #666;
  font-size: 12px;
}

.action-btn {
  background: #555;
  color: #fff;
  border: 1px solid #999;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}

.action-btn:hover {
  background: #777;
}

.button-row {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #fff;
  border: 1px solid #ccc;
}

.save-btn {
  background: #666;
  color: #fff;
  border: 1px solid #999;
  padding: 8px 20px;
  font-size: 14px;
  cursor: pointer;
  font-weight: 500;
}

.save-btn:hover {
  background: #888;
}

.apply-btn {
  background: #4a90e2;
  color: #fff;
  border: 1px solid #3a7bc8;
  padding: 8px 20px;
  font-size: 14px;
  cursor: pointer;
  font-weight: 500;
  margin-inline-start: 10px;
}

.apply-btn:hover:not(:disabled) {
  background: #3a7bc8;
}

.apply-btn:disabled {
  background: #999;
  cursor: not-allowed;
  opacity: 0.6;
}

.save-message {
  font-size: 13px;
  color: #333;
}

.error-message {
  color: #c00;
}

.info-note {
  padding: 10px 12px;
  background: #f0f0f0;
  border: 1px solid #999;
  font-size: 12px;
  color: #333;
}

.info-box {
  padding: 12px 15px;
  background: #fff4e6;
  border: 1px solid #ffa500;
  border-inline-start: 4px solid #ffa500;
  border-radius: 4px;
  font-size: 13px;
  color: #333;
  line-height: 1.5;
}

.info-box-success {
  background: #e6f7e6;
  border-color: #4CAF50;
  border-inline-start-color: #4CAF50;
}

.info-box strong {
  display: block;
  margin-bottom: 8px;
  color: #000;
  font-size: 14px;
}

.info-box p {
  margin: 6px 0;
}

.info-box code {
  background: rgba(0, 0, 0, 0.05);
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
  color: #2e7d32 !important;
  font-weight: 500;
}

.gpu-error {
  color: #f57c00 !important;
}
</style>
