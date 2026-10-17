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
                  <StatusBadge tone="unavailable">{{ $t('settings.backendStatus.notDetected') }}</StatusBadge>
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
            <StatusBadge :tone="gpuService.reachable ? 'available' : 'unavailable'">
              {{ gpuService.reachable ? $t('settings.backendStatus.reachable') : $t('settings.backendStatus.unreachable') }}
            </StatusBadge>
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
                  <StatusBadge :tone="info.available ? 'available' : 'unavailable'">
                    {{ info.available ? $t('settings.backendStatus.available') : $t('settings.backendStatus.unavailable') }}
                  </StatusBadge>
                  <span v-if="info.models && info.models.length" class="model-list-inline">
                    {{ info.models.join(', ') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- VRAM Coordinator -->
          <div v-if="gpuService.reachable && gpuService.gpu_info" class="vram-info" dir="ltr">
            <span class="vram-label">{{ t('settings.backendStatus.vram') }}</span>
            <span v-if="gpuService.gpu_info?.free_gb != null" class="mono">
              {{ t('settings.backendStatus.vramFreeOfTotal', { free: gpuService.gpu_info.free_gb.toFixed(1), total: gpuService.gpu_info.total_vram_gb?.toFixed(1) }) }}
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
                      <StatusBadge :tone="model.in_use > 0 ? 'in-use' : 'idle'">
                        {{ model.in_use > 0 ? $t('settings.backendStatus.inUse') : $t('settings.backendStatus.idle') }}
                      </StatusBadge>
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

        <!-- Who has the card, and who is next -->
        <div class="subsection">
          <h3>
            {{ $t('settings.backendStatus.gpuQueue') }}
            <StatusBadge :tone="!queue.reachable ? 'caution' : queue.active ? 'in-use' : 'idle'">
              {{ !queue.reachable ? $t('settings.backendStatus.queueUnreachable')
                : queue.active ? $t('settings.backendStatus.queueBusy')
                : $t('settings.backendStatus.queueIdle') }}
            </StatusBadge>
          </h3>
          <table v-if="queue.reachable && (queue.active || queue.rows.length)" class="status-table" dir="ltr">
            <tbody>
              <tr v-if="queue.active">
                <td class="label-cell">
                  <StatusBadge tone="in-use" compact>{{ $t('settings.backendStatus.queueRunning') }}</StatusBadge>
                </td>
                <td class="value-cell mono">{{ queue.active.model_id }}</td>
                <td class="value-cell">{{ remainingLabel(queue.active.expected_remaining_s) }}</td>
              </tr>
              <tr v-for="row in queue.rows" :key="row.id">
                <td class="label-cell mono">{{ row.position }}.</td>
                <td class="value-cell mono">
                  {{ row.model_id }}
                  <StatusBadge v-if="row.overtaken > 0" tone="caution" compact>
                    {{ $t('settings.backendStatus.queuePassedOver', { n: row.overtaken }) }}
                  </StatusBadge>
                </td>
                <td class="value-cell">{{ startsInLabel(row.expected_start_in_s) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else-if="!queue.reachable" class="queue-empty">
            {{ $t('settings.backendStatus.queueNoAnswer') }}
          </p>
          <p v-else class="queue-empty">{{ $t('settings.backendStatus.queueNothing') }}</p>
          <p v-if="queue.reachable && queue.approaching > 0" class="queue-approaching">
            {{ $t('settings.backendStatus.queueApproaching', { n: queue.approaching }, queue.approaching) }}
          </p>
        </div>

        <!-- ComfyUI / SwarmUI -->
        <div class="subsection">
          <h3>
            {{ $t('settings.backendStatus.comfyui') }}
            <span class="port-tag" dir="ltr">:{{ comfyuiPort }}</span>
            <StatusBadge :tone="comfyui.reachable ? 'available' : 'unavailable'">
              {{ comfyui.reachable ? $t('settings.backendStatus.reachable') : $t('settings.backendStatus.unreachable') }}
            </StatusBadge>
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

        <!-- Local LLM -->
        <div class="subsection">
          <h3>
            {{ $t('settings.backendStatus.localLlm') }}
            <StatusBadge :tone="llm.reachable ? 'available' : 'unavailable'">
              {{ llm.reachable ? $t('settings.backendStatus.reachable') : $t('settings.backendStatus.unreachable') }}
            </StatusBadge>
          </h3>

          <template v-if="llm.reachable && llm.models.length">
            <button class="toggle-btn" @click="showLlmModels = !showLlmModels">
              {{ showLlmModels ? $t('settings.backendStatus.hideModels') : $t('settings.backendStatus.showModels') }}
              ({{ llm.models.length }})
            </button>
            <div v-if="showLlmModels" class="model-details" dir="ltr">
              <table class="status-table">
                <tbody>
                  <tr v-for="model in llm.models" :key="model.name">
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
            </tr>
          </thead>
          <tbody>
            <tr v-for="(info, provider) in cloudApis" :key="provider">
              <td class="label-cell" dir="ltr">{{ formatProviderName(String(provider)) }}</td>
              <td class="value-cell">
                <StatusBadge :tone="info.key_configured ? 'available' : 'unavailable'">
                  {{ info.key_configured ? $t('settings.backendStatus.configured') : $t('settings.backendStatus.notConfigured') }}
                </StatusBadge>
              </td>
              <td class="value-cell">
                <DsgvoBadge :recorded="info.dsgvo_recorded" />
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
                  <StatusBadge :tone="cfg.available ? 'available' : 'unavailable'">
                    {{ cfg.available ? $t('settings.backendStatus.available') : $t('settings.backendStatus.unavailable') }}
                  </StatusBadge>
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
import StatusBadge from './StatusBadge.vue'
import DsgvoBadge from './DsgvoBadge.vue'
import { providerName } from '@/data/providers'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiBase } from '@/services/labApi'

const { t } = useI18n()

// --- State ---
const loading = ref(true)
const refreshing = ref(false)
const error = ref<string | null>(null)
const data = ref<any>(null)

// Collapsible sections
const showComfyuiModels = ref(false)
const showLlmModels = ref(false)
const showLoadedModels = ref(true)
const showForeignProcesses = ref(false)

// --- Computed accessors ---
const gpuHardware = computed(() => data.value?.local_infrastructure?.gpu_hardware ?? { detected: false })
const gpuService = computed(() => data.value?.local_infrastructure?.gpu_service ?? { reachable: false, sub_backends: {} })
const comfyui = computed(() => data.value?.local_infrastructure?.comfyui ?? { reachable: false, models: {} })
const llm = computed(() => data.value?.local_infrastructure?.llm ?? { reachable: false, models: [] })
const cloudApis = computed(() => data.value?.cloud_apis ?? {})

// Three answers, not two -- the mark itself is DsgvoBadge, and it stands in this
// file and in the API management tab. Nothing recorded is its own answer and
// reads grey, never as a weaker red. The same rule stands in the model matrix,
// which is where an operator records a status and the grounds for it.
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
  if (seconds < 60) return t('settings.backendStatus.ago.seconds', { n: seconds })
  if (seconds < 3600) return t('settings.backendStatus.ago.minutes', { n: Math.floor(seconds / 60) })
  if (seconds < 86400) return t('settings.backendStatus.ago.hours', { n: Math.floor(seconds / 3600) })
  return t('settings.backendStatus.ago.days', { n: Math.floor(seconds / 86400) })
}

// Kept as a local name so the template reads unchanged; the spellings come
// from the one list. See src/data/providers.ts.
function formatProviderName(name: string): string {
  return providerName(name)
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

    const baseUrl = apiBase()
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

/**
 * Who holds the card and who is next, in the order the gate will really serve
 * them. Read from the backend, never derived here: this window must not become
 * a second opinion about the queue.
 *
 * A run marked as passed over is one the gate let others go ahead of because
 * their model was already loaded. It is bounded — after a fixed number of
 * passes, or after five minutes, it goes next regardless.
 */
const queue = ref<{ active: any; rows: any[]; approaching: number; reachable: boolean }>(
  { active: null, rows: [], approaching: 0, reachable: true })
let queueTimer: ReturnType<typeof setInterval> | null = null
// A poll every three seconds against a call that can wait on the gate would
// otherwise stack up, and the answers would land out of order: the table would
// step backwards to an older queue.
let queueInFlight = false

async function fetchQueue() {
  if (queueInFlight) return
  queueInFlight = true
  try {
    const baseUrl = apiBase()
    const resp = await fetch(`${baseUrl}/api/schema/pipeline/queue-forecast`,
                             { credentials: 'include' })
    if (!resp.ok) {
      // Keeping the last good rows on screen would present minutes-old numbers
      // as current. The queue is not known right now, and that is what it says.
      queue.value = { active: null, rows: [], approaching: 0, reachable: false }
      return
    }
    const d = await resp.json()
    queue.value = {
      active: d.active ?? null,
      rows: Array.isArray(d.queue) ? d.queue : [],
      approaching: Number(d.approaching_count) || 0,
      // The card being free and the card not being visible are two different
      // answers, and only one of them means anyone can start.
      reachable: d.gate_reachable !== false,
    }
  } catch {
    // A queue nobody can read is not an error worth a red box in a status tab.
    queue.value = { active: null, rows: [], approaching: 0, reachable: false }
  } finally {
    queueInFlight = false
  }
}

// null means the gate has no measurement for this model yet. It has to stay
// visible as "not known" — a dash, not a zero.
function secondsLabel(v: any): string {
  if (v === null || v === undefined || !isFinite(Number(v))) return '\u2014'
  const s = Number(v)
  // The rounding picks the unit, so 88 s and 90 s do not end up with two
  // different names for the same wait.
  const r = Math.round(s / 5) * 5
  if (r < 60) return `${r} s`
  return `${Math.max(1, Math.round(s / 60))} min`
}
function remainingLabel(v: any): string {
  const l = secondsLabel(v)
  return l === '\u2014' ? l : t('settings.backendStatus.queueRemaining', { time: l })
}
function startsInLabel(v: any): string {
  const l = secondsLabel(v)
  return l === '\u2014' ? l : t('settings.backendStatus.queueStartsIn', { time: l })
}

onMounted(() => {
  fetchStatus()
  fetchQueue()
  queueTimer = setInterval(fetchQueue, 3000)
})
onBeforeUnmount(() => {
  if (queueTimer) clearInterval(queueTimer)
  queueTimer = null
})
</script>

<style scoped>
.backend-status {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.loading, .error {
  padding: 15px;
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  color: #e0e0e0;
}

.error {
  color: #ff6b6b;
}

/* Refresh bar */
.refresh-bar {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 10px 15px;
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
}

.action-btn {
  background: var(--surface-4);
  color: #fff;
  border: 1px solid var(--surface-4);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 400;
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
  color: #e0e0e0;
}

/* Sections */
.queue-empty,
.queue-approaching {
  font-size: 12px;
  color: rgb(255 255 255 / 0.5);
  margin: 4px 0 0;
}

.section {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  padding: 15px;
}

.section h2 {
  margin: 0 0 15px 0;
  font-size: 16px;
  font-weight: 700;
  color: #e0e0e0;
}

/* Subsections within Local Infrastructure */
.subsection {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--surface-4);
}

.subsection:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.subsection h3, .backend-group h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 700;
  color: #e0e0e0;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Status table */
.status-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--surface-4);
}

.status-table th,
.status-table td {
  padding: 6px 10px;
  font-size: 13px;
  text-align: start;
  border-bottom: 1px solid var(--surface-4);
}

.status-table th {
  background: var(--surface-3);
  font-weight: 700;
  color: #e0e0e0;
}

.status-table .label-cell {
  width: 220px;
  background: var(--surface-2);
  font-weight: 400;
  color: #f2f2f2;
  border-inline-end: 1px solid var(--surface-4);
}

.status-table .value-cell {
  background: var(--surface-1);
  color: #f2f2f2;
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

/* Port tags */
.port-tag {
  font-size: 11px;
  color: #9a9a9a;
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
  color: #b0b0b0;
  font-family: monospace;
}

/* VRAM info bar */
.vram-info {
  margin-top: 8px;
  padding: 6px 10px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  font-size: 12px;
  color: #e0e0e0;
}

.vram-label {
  font-weight: 700;
  margin-inline-end: 8px;
}

/* Toggle button for collapsible model lists */
.toggle-btn {
  background: none;
  border: 1px solid var(--surface-4);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #c0c0c0;
  margin-bottom: 8px;
}

.toggle-btn:hover {
  background: var(--surface-2);
}

/* Model details (collapsible) */
.model-details {
  margin-top: 8px;
}

.model-details h4 {
  margin: 8px 0 4px 0;
  font-size: 12px;
  font-weight: 700;
  color: #c0c0c0;
}

.model-details ul {
  margin: 0;
  padding-inline-start: 20px;
  list-style: disc;
}

.model-details li {
  font-size: 11px;
  color: #e0e0e0;
  margin: 2px 0;
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
  font-weight: 700;
  background: var(--surface-3);
  color: #c0c0c0;
}

.hidden-config {
  opacity: 0.5;
}

.hidden-tag {
  font-size: 10px;
  color: #909090;
  font-style: italic;
  margin-inline-start: 6px;
}

.media-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 400;
  background: var(--surface-2);
  color: #b0b0b0;
  border: 1px solid var(--surface-4);
}

/* VRAM Bar */
.vram-bar-container {
  margin-top: 8px;
}

.vram-bar {
  height: 16px;
  background: var(--surface-3);
  border: 1px solid var(--surface-4);
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
  color: #c0c0c0;
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
  background: var(--surface-3);
  border: 1px solid var(--surface-4);
}

.no-models {
  font-size: 12px;
  color: #9a9a9a;
  padding: 6px 0;
  font-style: italic;
}
</style>
