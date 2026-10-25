<template>
  <div class="api-management">
    <!-- Loading / Error -->
    <div v-if="loading" class="loading">{{ $t('settings.apiManagement.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else-if="data">
      <!-- Refresh bar -->
      <div class="refresh-bar">
        <button class="action-btn" :disabled="refreshing" @click="fetchData(true)">
          {{ refreshing ? $t('settings.apiManagement.refreshing') : $t('settings.apiManagement.refresh') }}
        </button>
        <span class="summary-text">
          {{ $t('settings.apiManagement.activeProvider') }}:
          <strong>{{ data.active_provider === 'none' ? $t('settings.apiManagement.noProvider') : data.active_provider }}</strong>
        </span>
      </div>

      <!-- ==================== Section 1: The accounts ==================== -->
      <!-- One block for every provider whose key file holds a key, headed by
           the provider's name, in two parts: what concerns the key of this
           installation (what it has spent, its own budget period, the rate
           limit it runs under), and the account behind it, over all its
           keys. Where the provider's interface does not report the key's
           spend, or reports neither the account's budget nor its balance,
           that part says so; a row it does not report is left out. Which
           interface a provider answers stands in
           devserver/config/llm_providers.json (`account_api`), read by
           services/provider_account.read_account. -->
      <div v-for="a in data.accounts || []" :key="a.provider" class="section">
        <h2>{{ providerLabel(a.provider) }}</h2>

        <div v-if="a.reading?.error" class="error-inline">
          {{ $t('settings.apiManagement.billingError') }}: {{ a.reading.error }}
        </div>

        <template v-else>
          <div class="subsection">
            <h3>{{ $t('settings.apiManagement.installationHead') }}</h3>
            <div class="billing-cards" dir="ltr">
              <!-- What the key in the key file has spent, as its provider
                   reports it: a LiteLLM account from the key's entry in its
                   answer, within the key's own budget period where it has
                   one; OpenRouter in the current month (UTC). -->
              <div class="billing-card">
                <div class="billing-label">{{ $t('settings.apiManagement.currentSpend') }}</div>
                <div v-if="a.reading?.key_spend != null" class="billing-value spend">{{ dollars(a.reading.key_spend) }}</div>
                <div v-else class="billing-value text-muted not-reported">{{ $t('settings.apiManagement.notReported') }}</div>
              </div>
            </div>
            <!-- The rate limit this key runs under: the lowest of the key's,
                 the account's and its team's. -->
            <table v-if="a.reading?.key_budget_reset_at || a.reading?.rpm_limit != null || a.reading?.tpm_limit != null" class="status-table" dir="ltr">
              <tbody>
                <tr v-if="a.reading.key_budget_reset_at">
                  <td class="label-cell">{{ $t('settings.apiManagement.resetDate') }}</td>
                  <td class="value-cell mono">{{ formatDate(a.reading.key_budget_reset_at) }}</td>
                </tr>
                <tr v-if="a.reading.rpm_limit != null || a.reading.tpm_limit != null">
                  <td class="label-cell">{{ $t('settings.apiManagement.rateLimit') }}</td>
                  <td class="value-cell mono">{{ rateText(a.reading) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="subsection">
            <h3>{{ $t('settings.apiManagement.accountHead') }}</h3>
            <!-- Only the figures the provider reports. The budget card stands
                 where the answer carries a budget field; an account without a
                 budget then reads as unlimited. Where the provider refused
                 the account's figures to this key, its answer stands here. -->
            <div v-if="a.reading?.account_error" class="error-inline">
              {{ $t('settings.apiManagement.billingError') }}: {{ a.reading.account_error }}
            </div>
            <div v-else-if="accountReports(a.reading)" class="billing-cards" dir="ltr">
              <div v-if="a.reading && 'max_budget' in a.reading" class="billing-card">
                <div class="billing-label">{{ $t('settings.apiManagement.budgetLimit') }}</div>
                <div class="billing-value">
                  {{ a.reading.max_budget != null ? dollars(a.reading.max_budget) : $t('settings.apiManagement.unlimited') }}
                </div>
              </div>
              <div v-if="a.reading && 'remaining' in a.reading" class="billing-card">
                <div class="billing-label">{{ $t('settings.apiManagement.remaining') }}</div>
                <div :class="['billing-value', remainingClass(a.reading)]">
                  {{ a.reading.remaining != null ? dollars(a.reading.remaining) : '—' }}
                </div>
              </div>
            </div>
            <div v-else class="empty-state">{{ $t('settings.apiManagement.notReported') }}</div>

            <!-- The account's budget and what all its keys have spent against it. -->
            <div v-if="a.reading?.max_budget" class="budget-bar-container" dir="ltr">
              <div class="budget-bar">
                <div :class="['budget-fill', budgetBarClass(a.reading)]" :style="{ width: budgetPercent(a.reading) + '%' }"></div>
              </div>
              <span class="budget-percent">{{ budgetPercent(a.reading) }}%</span>
            </div>

            <table v-if="a.reading?.budget_reset_at" class="status-table" dir="ltr">
              <tbody>
                <tr>
                  <td class="label-cell">{{ $t('settings.apiManagement.resetDate') }}</td>
                  <td class="value-cell mono">{{ formatDate(a.reading.budget_reset_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <!-- ==================== Section 2: Local Usage Tracking ==================== -->
      <div class="section">
        <h2>{{ $t('settings.apiManagement.localUsage') }}</h2>

        <!-- Period selector -->
        <div class="period-selector" dir="ltr">
          <div class="period-presets">
            <button v-for="p in periodPresets" :key="p.key"
                    :class="['preset-btn', { active: activePeriod === p.key }]"
                    @click="selectPeriod(p.key)">
              {{ t(p.labelKey) }}
            </button>
          </div>
          <div class="period-custom">
            <label>{{ $t('settings.apiManagement.from') }}</label>
            <input type="date" v-model="customFrom" @change="selectPeriod('custom')" />
            <label>{{ $t('settings.apiManagement.to') }}</label>
            <input type="date" v-model="customTo" @change="selectPeriod('custom')" />
          </div>
        </div>

        <div v-if="!data.local_usage || data.local_usage.total_calls === 0" class="empty-state">
          {{ $t('settings.apiManagement.noUsageData') }}
        </div>

        <template v-else>
          <!-- Totals -->
          <div class="usage-totals" dir="ltr">
            <span>{{ data.local_usage.total_calls }} {{ $t('settings.apiManagement.calls') }}</span>
            <span>{{ formatTokens(data.local_usage.total_input_tokens) }} in</span>
            <span>{{ formatTokens(data.local_usage.total_output_tokens) }} out</span>
            <span v-if="data.local_usage.total_cost" class="cost-total">
              ~${{ data.local_usage.total_cost.toFixed(2) }}
            </span>
          </div>

          <!-- By Model -->
          <div class="subsection">
            <h3>{{ $t('settings.apiManagement.byModel') }}</h3>
            <table class="status-table" dir="ltr">
              <thead>
                <tr>
                  <th>{{ $t('settings.apiManagement.model') }}</th>
                  <th>{{ $t('settings.apiManagement.calls') }}</th>
                  <th>{{ $t('settings.apiManagement.inputTokens') }}</th>
                  <th>{{ $t('settings.apiManagement.outputTokens') }}</th>
                  <th>{{ $t('settings.apiManagement.estCost') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, model) in data.local_usage.by_model" :key="String(model)">
                  <td class="mono">{{ model }}</td>
                  <td class="mono right">{{ stats.calls }}</td>
                  <td class="mono right">{{ formatTokens(stats.input_tokens) }}</td>
                  <td class="mono right">{{ formatTokens(stats.output_tokens) }}</td>
                  <td class="mono right cost-cell">{{ formatCost(stats.cost) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- By Stage -->
          <div class="subsection">
            <h3>{{ $t('settings.apiManagement.byStage') }}</h3>
            <table class="status-table" dir="ltr">
              <thead>
                <tr>
                  <th>{{ $t('settings.apiManagement.stage') }}</th>
                  <th>{{ $t('settings.apiManagement.calls') }}</th>
                  <th>{{ $t('settings.apiManagement.inputTokens') }}</th>
                  <th>{{ $t('settings.apiManagement.outputTokens') }}</th>
                  <th>{{ $t('settings.apiManagement.estCost') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, stage) in data.local_usage.by_stage" :key="String(stage)">
                  <td>{{ stageLabel(String(stage)) }}</td>
                  <td class="mono right">{{ stats.calls }}</td>
                  <td class="mono right">{{ formatTokens(stats.input_tokens) }}</td>
                  <td class="mono right">{{ formatTokens(stats.output_tokens) }}</td>
                  <td class="mono right cost-cell">{{ formatCost(stats.cost) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <!-- ==================== Section 3: Provider Status ==================== -->
      <div class="section">
        <h2>{{ $t('settings.apiManagement.providerStatus') }}</h2>
        <table class="status-table" dir="ltr">
          <thead>
            <tr>
              <th>{{ $t('settings.apiManagement.provider') }}</th>
              <th>{{ $t('settings.apiManagement.apiKey') }}</th>
              <th>{{ $t('settings.apiManagement.credits') }}</th>
              <th>{{ t('settings.apiManagement.dsgvo') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(info, name) in data.providers" :key="String(name)">
              <td>{{ providerLabel(String(name)) }}</td>
              <td>
                <span :class="['status-badge', info.key_configured ? 'status-available' : 'status-unavailable']">
                  {{ info.key_configured ? $t('settings.apiManagement.configured') : $t('settings.apiManagement.notConfigured') }}
                </span>
              </td>
              <td class="mono">
                <span v-if="info.credits?.remaining != null">{{ dollars(info.credits.remaining) }}</span>
                <span v-else class="text-muted">—</span>
              </td>
              <td>
                <DsgvoBadge :recorded="info.dsgvo_recorded" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ==================== Section 4: Model Assignments ==================== -->
      <div class="section">
        <h2>{{ $t('settings.apiManagement.modelAssignments') }}</h2>
        <table class="status-table" dir="ltr">
          <thead>
            <tr>
              <th>{{ $t('settings.apiManagement.function') }}</th>
              <th>{{ $t('settings.apiManagement.model') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="role in assignedRoles" :key="role.field">
              <td>{{ $t(role.labelKey) }}</td>
              <td class="mono">{{ modelShort(role.model) }}<template v-if="roleVia(role.model)"> · {{ roleVia(role.model) }}</template></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import DsgvoBadge from './DsgvoBadge.vue'
import { MODEL_ROLES } from '@/data/modelRoles'
import { providerName } from '@/data/providers'
import { modelShort } from '@/lib/modelPlace'
import { useI18n } from 'vue-i18n'
import { apiBase } from '@/services/labApi'

const { t } = useI18n()

const loading = ref(true)
const refreshing = ref(false)
const error = ref<string | null>(null)
const data = ref<any>(null)

// --- Period selection ---
const activePeriod = ref('month')
const customFrom = ref('')
const customTo = ref('')

const periodPresets = [
  { key: 'today', labelKey: 'settings.apiManagement.period.today', days: 1 },
  { key: 'week', labelKey: 'settings.apiManagement.period.week', days: 7 },
  { key: 'month', labelKey: 'settings.apiManagement.period.month', days: 30 },
  { key: 'year', labelKey: 'settings.apiManagement.period.year', days: 365 },
  { key: 'all', labelKey: 'settings.apiManagement.period.all', days: 0 },
]

function selectPeriod(key: string) {
  activePeriod.value = key
  if (key !== 'custom') {
    customFrom.value = ''
    customTo.value = ''
  }
  fetchData(true)
}

// --- An account's reading ---

/** Whether the provider reports a budget or a balance for the account. */
function accountReports(r: any): boolean {
  return !!r && ('max_budget' in r || 'remaining' in r)
}

/** RPM and TPM, each only where the reading carries one: an unset limit is
    none. A limit of 0 is a limit and stands. */
function rateText(r: any): string {
  return [r.rpm_limit != null ? `${r.rpm_limit} RPM` : '', r.tpm_limit != null ? `${formatTokens(r.tpm_limit)} TPM` : '']
    .filter(Boolean)
    .join(' / ')
}

/** The share of the account's budget all its keys have spent, in whole
    percent, at most 100. */
function budgetPercent(r: any): number {
  if (!r?.max_budget) return 0
  return Math.min(Math.round(((r.spend ?? 0) / r.max_budget) * 100), 100)
}

function budgetBarClass(r: any): string {
  const pct = budgetPercent(r)
  if (pct >= 90) return 'budget-critical'
  if (pct >= 75) return 'budget-warning'
  return 'budget-spend'
}

function remainingClass(r: any): string {
  if (!r?.max_budget) return ''
  const pct = budgetPercent(r)
  if (pct >= 80) return 'text-critical'
  if (pct >= 50) return 'text-warning'
  return ''
}

// --- Helpers ---

// The rows of the usage table are the same roles the two model tables configure,
// so they carry the same names -- there is one set of names for these, not a
// second one with stage numbers in it. The generation step is not a configurable
// role and has its own label.
// The assignments the backend reports, in the surface's order and under the
// surface's names. It sends field names; a role it does not report has no model
// set and is left out, as before.
const assignedRoles = computed(() =>
  MODEL_ROLES
    .map(role => ({ ...role, model: data.value?.model_assignments?.[role.field] }))
    .filter(role => !!role.model)
)

/** The provider an assignment goes through, by its name; nothing for a model
 *  that runs here. The id itself, with the provider in front, is the
 *  platform's and is not shown. */
function roleVia(id: string): string {
  if (!id.includes('/') || id.startsWith('local/')) return ''
  return providerName(id.split('/', 1)[0] ?? '')
}

const STAGE_LABEL_KEYS: Record<string, string> = {
  stage1: 'settings.models.stage1Text',
  stage2: 'settings.models.stage2Interception',
  stage3: 'settings.models.stage3',
  stage4: 'settings.apiManagement.roleGeneration',
  chat: 'settings.models.chatHelper',
}

function stageLabel(stage: string): string {
  const key = STAGE_LABEL_KEYS[stage]
  return key ? t(key) : stage
}

// The spellings come from the one list. See src/data/providers.ts.
function providerLabel(name: string): string {
  return providerName(name)
}

function formatTokens(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toString()
}

function formatCost(cost: number | undefined): string {
  if (!cost || cost === 0) return '—'
  if (cost < 0.01) return '<$0.01'
  return `$${cost.toFixed(2)}`
}

/** A dollar amount; one closer to zero than half a cent reads $0.00 (toFixed
    writes a small negative amount as -0.00). */
function dollars(v: number): string {
  return `$${(Math.abs(v) < 0.005 ? 0 : v).toFixed(2)}`
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString()
  } catch {
    return dateStr
  }
}

// --- Data fetching ---

async function fetchData(forceRefresh = false) {
  try {
    if (forceRefresh) {
      refreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null

    const baseUrl = apiBase()
    const params = new URLSearchParams()
    if (activePeriod.value === 'custom') {
      if (customFrom.value) params.set('from', customFrom.value)
      if (customTo.value) params.set('to', customTo.value)
    } else {
      const preset = periodPresets.find(p => p.key === activePeriod.value)
      if (preset) params.set('days', String(preset.days))
    }
    const qs = params.toString() ? `?${params.toString()}` : ''
    const resp = await fetch(`${baseUrl}/api/settings/api-usage${qs}`, { credentials: 'include' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    data.value = await resp.json()
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => fetchData())
</script>

<style scoped>
.api-management {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.loading, .error {
  padding: 15px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 8px;
  color: #ccc;
}
.error { color: #ff6b6b; }

.error-inline {
  padding: 10px 14px;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  border-radius: 6px;
  color: #ff6b6b;
  font-size: 13px;
}

.refresh-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-btn {
  padding: 6px 16px;
  background: var(--surface-3);
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  color: #e0e0e0;
  cursor: pointer;
  font-size: 13px;
}
.action-btn:hover:not(:disabled) { background: var(--surface-4); }
.action-btn:disabled { opacity: 0.5; cursor: default; }

.summary-text {
  color: #9a9a9a;
  font-size: 13px;
}

.section {
  background: var(--surface-1);
  border: 1px solid var(--surface-3);
  border-radius: 8px;
  padding: 18px;
}
.section h2 {
  margin: 0 0 14px 0;
  font-size: 16px;
  color: #e0e0e0;
  font-weight: 400;
}

.subsection {
  margin-top: 16px;
}
.subsection h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #aaa;
  font-weight: 400;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Billing cards */
.billing-cards {
  display: flex;
  gap: 14px;
  margin-bottom: 14px;
}
/* A card keeps the width it had while the tab always showed three in a
   row: a block can now hold one or two. */
.billing-card {
  flex: 0 1 calc((100% - 28px) / 3);
  background: var(--surface-2);
  border: 1px solid var(--surface-3);
  border-radius: 8px;
  padding: 14px 18px;
}
.billing-label {
  font-size: 12px;
  color: #9a9a9a;
  margin-bottom: 4px;
}
.billing-value {
  font-size: 24px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: #e0e0e0;
}
.billing-value.spend { color: #64b5f6; }
.billing-value.text-warning { color: #ffb74d; }
.billing-value.text-critical { color: #ff6b6b; }

/* Budget bar */
.budget-bar-container {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.budget-bar {
  flex: 1;
  height: 8px;
  background: var(--surface-3);
  border-radius: 4px;
  overflow: hidden;
}
.budget-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.budget-spend { background: #64b5f6; }
.budget-warning { background: #ffb74d; }
.budget-critical { background: #ff6b6b; }
.budget-percent {
  font-size: 12px;
  color: #9a9a9a;
  font-family: 'JetBrains Mono', monospace;
  min-width: 36px;
}

/* Usage totals */
.usage-totals {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #aaa;
  margin-bottom: 16px;
  font-family: 'JetBrains Mono', monospace;
}

.empty-state {
  padding: 20px;
  text-align: center;
  color: #b0b0b0;
  font-size: 14px;
}

/* Tables */
.status-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.status-table th {
  text-align: left;
  padding: 8px 12px;
  color: #9a9a9a;
  font-weight: 400;
  border-bottom: 1px solid var(--surface-3);
}
.status-table td {
  padding: 8px 12px;
  color: #ccc;
  border-bottom: 1px solid var(--surface-2);
}
.status-table .label-cell {
  color: #9a9a9a;
  width: 180px;
}
.status-table .value-cell {
  color: #e0e0e0;
}
.mono {
  font-family: 'JetBrains Mono', monospace;
}
.right {
  text-align: right;
}

/* Status badges */
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 400;
}
.status-available {
  background: rgba(76, 175, 80, 0.15);
  color: #4caf50;
}
.status-unavailable {
  background: rgba(255, 107, 107, 0.15);
  color: #ff6b6b;
}

/* Period selector */
.period-selector {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.period-presets {
  display: flex;
  gap: 4px;
}
.preset-btn {
  padding: 5px 12px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  color: #9a9a9a;
  cursor: pointer;
  font-size: 12px;
}
.preset-btn:hover { color: #ccc; border-color: var(--surface-4); }
.preset-btn.active {
  background: var(--surface-3);
  border-color: #64b5f6;
  color: #64b5f6;
}
.period-custom {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #9a9a9a;
}
.period-custom input[type="date"] {
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  color: #ccc;
  padding: 4px 8px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
}
.period-custom input[type="date"]::-webkit-calendar-picker-indicator {
  filter: invert(0.7);
}

.cost-cell {
  color: #64b5f6;
}
.cost-total {
  color: #64b5f6;
  font-weight: 700;
}

.not-reported {
  font-family: inherit;
  font-size: 14px;
  font-weight: normal;
}

.text-muted {
  color: #c0c0c0;
}
</style>
