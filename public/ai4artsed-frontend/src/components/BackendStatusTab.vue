<template>
  <div class="backend-status">
    <!-- Loading / Error -->
    <div v-if="loading" class="loading">{{ $t('settings.backendStatus.loading') }}</div>
    <div v-else-if="error" class="error">{{ $t('common.error') }}: {{ error }}</div>

    <template v-else-if="data">
      <!-- Refresh bar -->
      <div class="refresh-bar">
        <button class="action-btn" :disabled="refreshing" @click="fetchStatus(true)">
          {{ refreshing ? $t('settings.backendStatus.refreshing') : $t('settings.backendStatus.refresh') }}
        </button>
        <span v-if="data.output_configs?.summary" class="summary-text">
          {{ $t('settings.backendStatus.configsAvailable', {
            available: data.output_configs.summary.available,
            total: data.output_configs.summary.total
          }) }}
        </span>
      </div>

      <!-- ==================== Section 1: Local Infrastructure ==================== -->
      <div class="section">
        <h2>{{ $t('settings.backendStatus.localInfrastructure') }}</h2>

        <!-- GPU Hardware -->
        <div class="subsection">
          <h3>{{ $t('settings.backendStatus.gpuHardware') }}</h3>
          <table class="status-table" dir="ltr">
            <tbody>
              <tr v-if="gpuHardware.detected">
                <td class="label-cell">GPU</td>
                <td class="value-cell mono">{{ gpuHardware.gpu_name }}</td>
              </tr>
              <tr v-if="gpuHardware.detected">
                <td class="label-cell">VRAM</td>
                <td class="value-cell mono">{{ gpuHardware.vram_gb }} GB ({{ gpuHardware.vram_tier }})</td>
              </tr>
              <tr v-if="!gpuHardware.detected">
                <td class="label-cell">GPU</td>
                <td class="value-cell">
                  <span class="status-badge status-unavailable">{{ $t('settings.backendStatus.notDetected') }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- GPU Service -->
        <div class="subsection">
          <h3>
            {{ $t('settings.backendStatus.gpuService') }}
            <span class="port-tag" dir="ltr">:17803</span>
            <span :class="['status-badge', gpuService.reachable ? 'status-available' : 'status-unavailable']">
              {{ gpuService.reachable ? $t('settings.backendStatus.reachable') : $t('settings.backendStatus.unreachable') }}
            </span>
          </h3>

          <table v-if="gpuService.reachable" class="status-table" dir="ltr">
            <thead>
              <tr>
                <th class="label-cell">{{ $t('settings.backendStatus.subBackend') }}</th>
                <th class="value-cell">{{ $t('settings.backendStatus.status') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(info, name) in gpuService.sub_backends" :key="name">
                <td class="label-cell mono">{{ formatBackendName(String(name)) }}</td>
                <td class="value-cell">
                  <span :class="['status-badge', info.available ? 'status-available' : 'status-unavailable']">
                    {{ info.available ? $t('settings.backendStatus.available') : $t('settings.backendStatus.unavailable') }}
                  </span>
                  <span v-if="info.models && info.models.length" class="model-list-inline">
                    {{ info.models.join(', ') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- VRAM Coordinator -->
          <div v-if="gpuService.reachable && gpuService.gpu_info" class="vram-info" dir="ltr">
            <span class="vram-label">VRAM:</span>
            <span v-if="gpuService.gpu_info?.free_gb != null" class="mono">
              {{ gpuService.gpu_info.free_gb.toFixed(1) }} GB free
              / {{ gpuService.gpu_info.total_vram_gb?.toFixed(1) }} GB total
            </span>
          </div>

          <!-- VRAM Bar -->
          <div v-if="vramCoordinator && gpuService.gpu_info?.total_vram_gb" class="vram-bar-container" dir="ltr">
            <div class="vram-bar">
              <div
                class="vram-segment vram-own"
                :style="{ width: ownVramPercent + '%' }"
                :title="$t('settings.backendStatus.ownModels') + ': ' + ownVramGb.toFixed(1) + ' GB'"
              ></div>
              <div
                v-if="foreignVramGb > 0"
                class="vram-segment vram-foreign"
                :style="{ width: foreignVramPercent + '%' }"
                :title="$t('settings.backendStatus.foreignProcesses') + ': ' + foreignVramGb.toFixed(1) + ' GB'"
              ></div>
            </div>
            <div class="vram-bar-legend">
              <span class="legend-item"><span class="legend-dot vram-own-dot"></span> {{ $t('settings.backendStatus.ownModels') }} ({{ ownVramGb.toFixed(1) }} GB)</span>
              <span v-if="foreignVramGb > 0" class="legend-item"><span class="legend-dot vram-foreign-dot"></span> {{ $t('settings.backendStatus.foreignProcesses') }} ({{ foreignVramGb.toFixed(1) }} GB)</span>
              <span class="legend-item"><span class="legend-dot vram-free-dot"></span> Free ({{ gpuService.gpu_info.free_gb.toFixed(1) }} GB)</span>
            </div>
          </div>

          <!-- Loaded Models (collapsible) -->
          <template v-if="vramCoordinator">
            <button class="toggle-btn" @click="showLoadedModels = !showLoadedModels">
              {{ showLoadedModels ? $t('settings.backendStatus.hideLoadedModels') : $t('settings.backendStatus.showLoadedModels') }}
              ({{ loadedModels.length }})
            </button>
            <div v-if="showLoadedModels" class="model-details" dir="ltr">
              <div v-if="loadedModels.length === 0" class="no-models">
                {{ $t('settings.backendStatus.noModelsLoaded') }}
              </div>
              <table v-else class="status-table">
                <thead>
                  <tr>
                    <th class="label-cell">{{ $t('settings.backendStatus.subBackend') }}</th>
                    <th class="value-cell">{{ $t('settings.backendStatus.model') }}</th>
                    <th class="value-cell">{{ $t('settings.backendStatus.vramUsage') }}</th>
                    <th class="value-cell">{{ $t('settings.backendStatus.status') }}</th>
                    <th class="value-cell">{{ $t('settings.backendStatus.lastUsed') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="model in loadedModels" :key="model.backend + model.model">
                    <td class="label-cell mono">{{ formatBackendName(model.backend) }}</td>
                    <td class="value-cell mono">{{ formatModelName(model.model) }}</td>
                    <td class="value-cell mono">{{ (model.vram_mb / 1024).toFixed(1) }} GB</td>
                    <td class="value-cell">
                      <span :class="['status-badge', model.in_use > 0 ? 'status-in-use' : 'status-idle']">
                        {{ model.in_use > 0 ? $t('settings.backendStatus.inUse') : $t('settings.backendStatus.idle') }}
                      </span>
                    </td>
                    <td class="value-cell mono">{{ formatRelativeTime(model.last_used) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Foreign GPU Processes (collapsible) -->
            <template v-if="foreignProcesses.length > 0">
              <button class="toggle-btn" @click="showForeignProcesses = !showForeignProcesses">
                {{ showForeignProcesses ? $t('settings.backendStatus.hideProcesses') : $t('settings.backendStatus.showProcesses') }}
                ({{ foreignProcesses.length }})
              </button>
              <div v-if="showForeignProcesses" class="model-details" dir="ltr">
                <table class="status-table">
                  <thead>
                    <tr>
                      <th class="label-cell">{{ $t('settings.backendStatus.pid') }}</th>
                      <th class="value-cell">{{ $t('settings.backendStatus.command') }}</th>
                      <th class="value-cell">{{ $t('settings.backendStatus.vramUsage') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="proc in foreignProcesses" :key="proc.pid">
                      <td class="label-cell mono">{{ proc.pid }}</td>
                      <td class="value-cell mono">{{ proc.cmdline }}</td>
                      <td class="value-cell mono">{{ (proc.vram_mb / 1024).toFixed(1) }} GB</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </template>
        </div>

        <!-- ComfyUI / SwarmUI -->
        <div class="subsection">
          <h3>
            {{ $t('settings.backendStatus.comfyui') }}
            <span class="port-tag" dir="ltr">:{{ comfyuiPort }}</span>
            <span :class="['status-badge', comfyui.reachable ? 'status-available' : 'status-unavailable']">
              {{ comfyui.reachable ? $t('settings.backendStatus.reachable') : $t('settings.backendStatus.unreachable') }}
            </span>
          </h3>

          <template v-if="comfyui.reachable && comfyui.models">
            <button class="toggle-btn" @click="showComfyuiModels = !showComfyuiModels">
              {{ showComfyuiModels ? $t('settings.backendStatus.hideModels') : $t('settings.backendStatus.showModels') }}
              ({{ comfyuiModelCount }})
            </button>
            <div v-if="showComfyuiModels" class="model-details" dir="ltr">
              <div v-for="(models, category) in comfyui.models" :key="category">
                <template v-if="models.length">
                  <h4>{{ formatBackendName(String(category)) }} ({{ models.length }})</h4>
                  <ul>
                    <li v-for="model in models" :key="model" class="mono">{{ model }}</li>
                  </ul>
                </template>
              </div>
            </div>
          </template>
        </div>

        <!-- Ollama -->
        <div class="subsection">
          <h3>
            {{ $t('settings.backendStatus.ollama') }}
            <span class="port-tag" dir="ltr">:11434</span>
            <span :class="['status-badge', ollama.reachable ? 'status-available' : 'status-unavailable']">
              {{ ollama.reachable ? $t('settings.backendStatus.reachable') : $t('settings.backendStatus.unreachable') }}
            </span>
          </h3>

          <template v-if="ollama.reachable && ollama.models.length">
            <button class="toggle-btn" @click="showOllamaModels = !showOllamaModels">
              {{ showOllamaModels ? $t('settings.backendStatus.hideModels') : $t('settings.backendStatus.showModels') }}
              ({{ ollama.models.length }})
            </button>
            <div v-if="showOllamaModels" class="model-details" dir="ltr">
              <table class="status-table">
                <tbody>
                  <tr v-for="model in ollama.models" :key="model.name">
                    <td class="label-cell mono">{{ model.name }}</td>
                    <td class="value-cell mono">{{ model.size }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </div>

      <!-- ==================== Section 2: Cloud APIs ==================== -->
      <div class="section">
        <h2>{{ $t('settings.backendStatus.cloudApis') }}</h2>
        <table class="status-table">
          <thead>
            <tr>
              <th class="label-cell">{{ $t('settings.backendStatus.provider') }}</th>
              <th class="value-cell">{{ $t('settings.backendStatus.keyStatus') }}</th>
              <th class="value-cell">{{ $t('settings.backendStatus.dsgvoLabel') }}</th>
              <th class="value-cell">{{ $t('settings.backendStatus.region') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(info, provider) in cloudApis" :key="provider">
              <td class="label-cell" dir="ltr">{{ formatProviderName(String(provider)) }}</td>
              <td class="value-cell">
                <span :class="['status-badge', info.key_configured ? 'status-available' : 'status-unavailable']">
                  {{ info.key_configured ? $t('settings.backendStatus.configured') : $t('settings.backendStatus.notConfigured') }}
                </span>
              </td>
              <td class="value-cell">
                <span :class="info.dsgvo_compliant ? 'dsgvo-ok' : 'dsgvo-warn'">
                  {{ info.dsgvo_compliant ? $t('settings.backendStatus.dsgvoCompliant') : $t('settings.backendStatus.dsgvoNotCompliant') }}
                </span>
              </td>
              <td class="value-cell">
                <span class="region-tag" dir="ltr">{{ info.region }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ==================== Section 3: Output Configs by Backend ==================== -->
      <div class="section">
        <h2>{{ $t('settings.backendStatus.outputConfigs') }}</h2>

        <div v-for="(configs, backendType) in configsByBackend" :key="backendType" class="backend-group">
          <h3 dir="ltr">
            {{ formatBackendName(String(backendType)) }}
            <span class="count-tag">{{ configs.length }}</span>
          </h3>
          <table class="status-table" dir="ltr">
            <tbody>
              <tr v-for="cfg in configs" :key="cfg.id" :class="{ 'hidden-config': cfg.hidden }">
                <td class="label-cell mono">{{ cfg.id }}</td>
                <td class="value-cell">
                  {{ cfg.name }}
                  <span v-if="cfg.hidden" class="hidden-tag">{{ $t('settings.backendStatus.hidden') }}</span>
                </td>
                <td class="value-cell status-col">
                  <span class="media-tag">{{ cfg.media_type }}</span>
                  <span :class="['status-badge', cfg.available ? 'status-available' : 'status-unavailable']">
                    {{ cfg.available ? $t('settings.backendStatus.available') : $t('settings.backendStatus.unavailable') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// --- State ---
const loading = ref(true)
const refreshing = ref(false)
const error = ref<string | null>(null)
const data = ref<any>(null)

// Collapsible sections
const showComfyuiModels = ref(false)
const showOllamaModels = ref(false)
const showLoadedModels = ref(true)
const showForeignProcesses = ref(false)

// --- Computed accessors ---
const gpuHardware = computed(() => data.value?.local_infrastructure?.gpu_hardware ?? { detected: false })
const gpuService = computed(() => data.value?.local_infrastructure?.gpu_service ?? { reachable: false, sub_backends: {} })
const comfyui = computed(() => data.value?.local_infrastructure?.comfyui ?? { reachable: false, models: {} })
const ollama = computed(() => data.value?.local_infrastructure?.ollama ?? { reachable: false, models: [] })
const cloudApis = computed(() => data.value?.cloud_apis ?? {})
const configsByBackend = computed(() => data.value?.output_configs?.by_backend ?? {})

// VRAM coordinator data
const vramCoordinator = computed(() => gpuService.value?.vram_coordinator ?? null)

const loadedModels = computed(() => {
  return vramCoordinator.value?.loaded_models ?? []
})

const foreignProcesses = computed(() => {
  const procs = vramCoordinator.value?.gpu_processes ?? []
  return procs.filter((p: any) => p.foreign)
})

const ownVramGb = computed(() => {
  const models = loadedModels.value
  const totalMb = models.reduce((sum: number, m: any) => sum + (m.vram_mb || 0), 0)
  return totalMb / 1024
})

const foreignVramGb = computed(() => {
  const mb = vramCoordinator.value?.foreign_vram_mb ?? 0
  return mb / 1024
})

const ownVramPercent = computed(() => {
  const total = gpuService.value?.gpu_info?.total_vram_gb ?? 1
  return Math.min(100, (ownVramGb.value / total) * 100)
})

const foreignVramPercent = computed(() => {
  const total = gpuService.value?.gpu_info?.total_vram_gb ?? 1
  return Math.min(100, (foreignVramGb.value / total) * 100)
})

const comfyuiPort = computed(() => {
  const url = comfyui.value?.url ?? ''
  const match = url.match(/:(\d+)$/)
  return match ? match[1] : '7821'
})

const comfyuiModelCount = computed(() => {
  const models = comfyui.value?.models ?? {}
  return Object.values(models).reduce((sum: number, arr: any) => sum + (Array.isArray(arr) ? arr.length : 0), 0)
})

// --- Helpers ---
const BACKEND_DISPLAY_NAMES: Record<string, string> = {
  diffusers: 'Diffusers',
  heartmula: 'HeartMuLa',
  stable_audio: 'Stable Audio',
  cross_aesthetic: 'Cross-Aesthetic',
  mmaudio: 'MMAudio',
  text: 'Text (Transformers)',
  llm_inference: 'LLM Inference',
  comfyui: 'ComfyUI',
  comfyui_legacy: 'ComfyUI (Legacy)',
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  config_model: 'Config Model (Code)',
  checkpoints: 'Checkpoints',
  unets: 'UNETs',
  vaes: 'VAEs',
  clips: 'CLIPs',
}

function formatBackendName(name: string): string {
  return BACKEND_DISPLAY_NAMES[name] ?? name
}

const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  openrouter: 'OpenRouter',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  mistral: 'Mistral AI',
  aws_bedrock: 'AWS Bedrock',
}

function formatModelName(modelId: string): string {
  // Shorten common model ID prefixes for display
  return modelId
    .replace('stabilityai/', '')
    .replace('black-forest-labs/', '')
    .replace('Wan-AI/', '')
}

function formatRelativeTime(timestamp: number): string {
  if (!timestamp) return '—'
  const seconds = Math.floor(Date.now() / 1000 - timestamp)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function formatProviderName(name: string): string {
  return PROVIDER_DISPLAY_NAMES[name] ?? name
}

// --- Data fetching ---
async function fetchStatus(forceRefresh = false) {
  try {
    if (forceRefresh) {
      refreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null

    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const url = forceRefresh
      ? `${baseUrl}/api/settings/backend-status?force_refresh=true`
      : `${baseUrl}/api/settings/backend-status`

    const resp = await fetch(url, { credentials: 'include' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    data.value = await resp.json()
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => fetchStatus())
</script>

<style scoped>
.backend-status {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.loading, .error {
  padding: 15px;
  background: #fff;
  border: 1px solid #ccc;
  color: #333;
}

.error {
  color: #c00;
}

/* Refresh bar */
.refresh-bar {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 10px 15px;
  background: #fff;
  border: 1px solid #ccc;
}

.action-btn {
  background: #555;
  color: #fff;
  border: 1px solid #999;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}

.action-btn:hover:not(:disabled) {
  background: #777;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.summary-text {
  font-size: 13px;
  color: #333;
}

/* Sections */
.section {
  background: #fff;
  border: 1px solid #ccc;
  padding: 15px;
}

.section h2 {
  margin: 0 0 15px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

/* Subsections within Local Infrastructure */
.subsection {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #e0e0e0;
}

.subsection:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.subsection h3, .backend-group h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Status table */
.status-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #999;
}

.status-table th,
.status-table td {
  padding: 6px 10px;
  font-size: 13px;
  text-align: start;
  border-bottom: 1px solid #ddd;
}

.status-table th {
  background: #e8e8e8;
  font-weight: 600;
  color: #333;
}

.status-table .label-cell {
  width: 220px;
  background: #f0f0f0;
  font-weight: 500;
  color: #000;
  border-inline-end: 1px solid #999;
}

.status-table .value-cell {
  background: #fff;
  color: #000;
}

.status-table .status-col {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.status-table tr:last-child td {
  border-bottom: none;
}

/* Status badges */
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.status-available {
  background: #e6f7e6;
  color: #2e7d32;
  border: 1px solid #4CAF50;
}

.status-unavailable {
  background: #fdecea;
  color: #c62828;
  border: 1px solid #ef5350;
}

/* Port tags */
.port-tag {
  font-size: 11px;
  color: #888;
  font-family: monospace;
  font-weight: 400;
}

/* Monospace */
.mono {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

/* Model list inline (for text backend models) */
.model-list-inline {
  margin-inline-start: 10px;
  font-size: 12px;
  color: #666;
  font-family: monospace;
}

/* VRAM info bar */
.vram-info {
  margin-top: 8px;
  padding: 6px 10px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  font-size: 12px;
  color: #333;
}

.vram-label {
  font-weight: 600;
  margin-inline-end: 8px;
}

/* Toggle button for collapsible model lists */
.toggle-btn {
  background: none;
  border: 1px solid #ccc;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #555;
  margin-bottom: 8px;
}

.toggle-btn:hover {
  background: #f5f5f5;
}

/* Model details (collapsible) */
.model-details {
  margin-top: 8px;
}

.model-details h4 {
  margin: 8px 0 4px 0;
  font-size: 12px;
  font-weight: 600;
  color: #555;
}

.model-details ul {
  margin: 0;
  padding-inline-start: 20px;
  list-style: disc;
}

.model-details li {
  font-size: 11px;
  color: #333;
  margin: 2px 0;
}

/* Cloud API styling */
.dsgvo-ok {
  color: #2e7d32;
  font-weight: 500;
  font-size: 12px;
}

.dsgvo-warn {
  color: #e65100;
  font-weight: 500;
  font-size: 12px;
}

.region-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  font-family: monospace;
  background: #f0f0f0;
  color: #333;
  border: 1px solid #ccc;
}

/* Backend groups (output configs) */
.backend-group {
  margin-bottom: 15px;
}

.backend-group:last-child {
  margin-bottom: 0;
}

.count-tag {
  display: inline-block;
  padding: 0 6px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  background: #e0e0e0;
  color: #555;
}

.hidden-config {
  opacity: 0.5;
}

.hidden-tag {
  font-size: 10px;
  color: #999;
  font-style: italic;
  margin-inline-start: 6px;
}

.media-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
  background: #f0f0f0;
  color: #666;
  border: 1px solid #ddd;
}

/* VRAM Bar */
.vram-bar-container {
  margin-top: 8px;
}

.vram-bar {
  height: 16px;
  background: #e0e0e0;
  border: 1px solid #999;
  border-radius: 3px;
  display: flex;
  overflow: hidden;
}

.vram-segment {
  height: 100%;
  transition: width 0.3s ease;
}

.vram-own {
  background: #4CAF50;
}

.vram-foreign {
  background: #FF9800;
}

.vram-bar-legend {
  display: flex;
  gap: 14px;
  margin-top: 4px;
  font-size: 11px;
  color: #555;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.vram-own-dot {
  background: #4CAF50;
}

.vram-foreign-dot {
  background: #FF9800;
}

.vram-free-dot {
  background: #e0e0e0;
  border: 1px solid #999;
}

/* In-use / Idle badges */
.status-in-use {
  background: #e3f2fd;
  color: #1565c0;
  border: 1px solid #42a5f5;
}

.status-idle {
  background: #f5f5f5;
  color: #757575;
  border: 1px solid #bdbdbd;
}

.no-models {
  font-size: 12px;
  color: #888;
  padding: 6px 0;
  font-style: italic;
}
</style>
