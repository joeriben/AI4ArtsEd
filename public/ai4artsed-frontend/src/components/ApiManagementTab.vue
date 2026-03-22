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

      <!-- ==================== Section 1: Mammouth Billing ==================== -->
      <div v-if="data.mammouth_billing" class="section">
        <h2>Mammouth — {{ $t('settings.apiManagement.accountOverview') }}</h2>

        <div v-if="data.mammouth_billing.error" class="error-inline">
          {{ $t('settings.apiManagement.billingError') }}: {{ data.mammouth_billing.error }}
        </div>

        <template v-else>
          <div class="billing-cards" dir="ltr">
            <div class="billing-card">
              <div class="billing-label">{{ $t('settings.apiManagement.currentSpend') }}</div>
              <div class="billing-value spend">${{ data.mammouth_billing.spend?.toFixed(2) ?? '—' }}</div>
            </div>
            <div class="billing-card">
              <div class="billing-label">{{ $t('settings.apiManagement.budgetLimit') }}</div>
              <div class="billing-value">
                {{ data.mammouth_billing.max_budget ? `$${data.mammouth_billing.max_budget.toFixed(2)}` : $t('settings.apiManagement.unlimited') }}
              </div>
            </div>
            <div class="billing-card">
              <div class="billing-label">{{ $t('settings.apiManagement.remaining') }}</div>
              <div :class="['billing-value', remainingClass]">
                {{ data.mammouth_billing.remaining != null ? `$${data.mammouth_billing.remaining.toFixed(2)}` : '—' }}
              </div>
            </div>
          </div>

          <!-- Budget bar -->
          <div v-if="data.mammouth_billing.max_budget" class="budget-bar-container" dir="ltr">
            <div class="budget-bar">
              <div :class="['budget-fill', budgetBarClass]" :style="{ width: budgetPercent + '%' }"></div>
            </div>
            <span class="budget-percent">{{ budgetPercent }}%</span>
          </div>

          <table class="status-table" dir="ltr">
            <tbody>
              <tr v-if="data.mammouth_billing.budget_reset_at">
                <td class="label-cell">{{ $t('settings.apiManagement.resetDate') }}</td>
                <td class="value-cell mono">{{ formatDate(data.mammouth_billing.budget_reset_at) }}</td>
              </tr>
              <tr v-if="data.mammouth_billing.rpm_limit">
                <td class="label-cell">{{ $t('settings.apiManagement.rateLimit') }}</td>
                <td class="value-cell mono">{{ data.mammouth_billing.rpm_limit }} RPM / {{ formatTokens(data.mammouth_billing.tpm_limit) }} TPM</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>

      <!-- ==================== Section 2: Local Usage Tracking ==================== -->
      <div class="section">
        <h2>{{ $t('settings.apiManagement.localUsage') }} ({{ data.local_usage?.period_days ?? 30 }}d)</h2>

        <div v-if="!data.local_usage || data.local_usage.total_calls === 0" class="empty-state">
          {{ $t('settings.apiManagement.noUsageData') }}
        </div>

        <template v-else>
          <!-- Totals -->
          <div class="usage-totals" dir="ltr">
            <span>{{ data.local_usage.total_calls }} {{ $t('settings.apiManagement.calls') }}</span>
            <span>{{ formatTokens(data.local_usage.total_input_tokens) }} in</span>
            <span>{{ formatTokens(data.local_usage.total_output_tokens) }} out</span>
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
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, model) in data.local_usage.by_model" :key="String(model)">
                  <td class="mono">{{ model }}</td>
                  <td class="mono right">{{ stats.calls }}</td>
                  <td class="mono right">{{ formatTokens(stats.input_tokens) }}</td>
                  <td class="mono right">{{ formatTokens(stats.output_tokens) }}</td>
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
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, stage) in data.local_usage.by_stage" :key="String(stage)">
                  <td>{{ stageLabel(String(stage)) }}</td>
                  <td class="mono right">{{ stats.calls }}</td>
                  <td class="mono right">{{ formatTokens(stats.input_tokens) }}</td>
                  <td class="mono right">{{ formatTokens(stats.output_tokens) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- By Date (last 7 visible, expandable) -->
          <div class="subsection">
            <h3>
              {{ $t('settings.apiManagement.byDate') }}
              <button v-if="Object.keys(data.local_usage.by_date).length > 7"
                      class="toggle-btn" @click="showAllDates = !showAllDates">
                {{ showAllDates ? $t('settings.apiManagement.showLess') : $t('settings.apiManagement.showAll') }}
              </button>
            </h3>
            <table class="status-table" dir="ltr">
              <thead>
                <tr>
                  <th>{{ $t('settings.apiManagement.date') }}</th>
                  <th>{{ $t('settings.apiManagement.calls') }}</th>
                  <th>{{ $t('settings.apiManagement.inputTokens') }}</th>
                  <th>{{ $t('settings.apiManagement.outputTokens') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, dateStr) in visibleDates" :key="String(dateStr)">
                  <td class="mono">{{ dateStr }}</td>
                  <td class="mono right">{{ stats.calls }}</td>
                  <td class="mono right">{{ formatTokens(stats.input_tokens) }}</td>
                  <td class="mono right">{{ formatTokens(stats.output_tokens) }}</td>
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
              <th>DSGVO</th>
              <th>{{ $t('settings.apiManagement.region') }}</th>
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
                <template v-if="info.credits != null">
                  ${{ info.credits.spend != null ? info.credits.spend.toFixed(2) : '—' }}
                  <span v-if="info.credits.remaining != null" class="credits-remaining">
                    / ${{ info.credits.remaining.toFixed(2) }} {{ $t('settings.apiManagement.remaining') }}
                  </span>
                </template>
                <span v-else-if="!info.key_configured" class="text-muted">—</span>
                <span v-else class="text-muted">—</span>
              </td>
              <td>
                <span :class="info.dsgvo ? 'dsgvo-ok' : 'dsgvo-warn'">
                  {{ info.dsgvo ? 'DSGVO' : 'Non-EU' }}
                </span>
              </td>
              <td class="mono">{{ info.region }}</td>
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
            <tr v-for="(model, role) in data.model_assignments" :key="String(role)">
              <td>{{ role }}</td>
              <td class="mono">{{ model }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const loading = ref(true)
const refreshing = ref(false)
const error = ref<string | null>(null)
const data = ref<any>(null)
const showAllDates = ref(false)

// --- Computed ---

const budgetPercent = computed(() => {
  if (!data.value?.mammouth_billing?.max_budget) return 0
  const pct = (data.value.mammouth_billing.spend / data.value.mammouth_billing.max_budget) * 100
  return Math.min(Math.round(pct), 100)
})

const budgetBarClass = computed(() => {
  const pct = budgetPercent.value
  if (pct >= 90) return 'budget-critical'
  if (pct >= 75) return 'budget-warning'
  return 'budget-spend'
})

const remainingClass = computed(() => {
  if (!data.value?.mammouth_billing?.max_budget) return ''
  const pct = budgetPercent.value
  if (pct >= 80) return 'text-critical'
  if (pct >= 50) return 'text-warning'
  return ''
})

const visibleDates = computed(() => {
  const dates = data.value?.local_usage?.by_date ?? {}
  if (showAllDates.value) return dates
  const entries = Object.entries(dates).slice(0, 7)
  return Object.fromEntries(entries)
})

// --- Helpers ---

const STAGE_LABELS: Record<string, string> = {
  stage1: 'Translation (Stage 1)',
  stage2: 'Transformation (Stage 2)',
  stage3: 'Safety (Stage 3)',
  stage4: 'Generation (Stage 4)',
  chat: 'Chat Helper',
}

function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage
}

const PROVIDER_LABELS: Record<string, string> = {
  mammouth: 'Mammouth AI',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  mistral: 'Mistral AI',
  ionos: 'IONOS',
}

function providerLabel(name: string): string {
  return PROVIDER_LABELS[name] ?? name
}

function formatTokens(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toString()
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

    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const resp = await fetch(`${baseUrl}/api/settings/api-usage`, { credentials: 'include' })
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
  background: #1a1a1a;
  border: 1px solid #333;
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
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 6px;
  color: #e0e0e0;
  cursor: pointer;
  font-size: 13px;
}
.action-btn:hover:not(:disabled) { background: #333; }
.action-btn:disabled { opacity: 0.5; cursor: default; }

.summary-text {
  color: #888;
  font-size: 13px;
}

.section {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 18px;
}
.section h2 {
  margin: 0 0 14px 0;
  font-size: 16px;
  color: #e0e0e0;
  font-weight: 500;
}

.subsection {
  margin-top: 16px;
}
.subsection h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #aaa;
  font-weight: 500;
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
.billing-card {
  flex: 1;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 14px 18px;
}
.billing-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}
.billing-value {
  font-size: 24px;
  font-weight: 600;
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
  background: #2a2a2a;
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
  color: #888;
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
  color: #666;
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
  color: #888;
  font-weight: 500;
  border-bottom: 1px solid #2a2a2a;
}
.status-table td {
  padding: 8px 12px;
  color: #ccc;
  border-bottom: 1px solid #1a1a1a;
}
.status-table .label-cell {
  color: #888;
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
  font-weight: 500;
}
.status-available {
  background: rgba(76, 175, 80, 0.15);
  color: #4caf50;
}
.status-unavailable {
  background: rgba(255, 107, 107, 0.15);
  color: #ff6b6b;
}
.dsgvo-ok {
  color: #4caf50;
  font-size: 12px;
}
.dsgvo-warn {
  color: #ffb74d;
  font-size: 12px;
}

.toggle-btn {
  padding: 2px 8px;
  background: none;
  border: 1px solid #444;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  font-size: 11px;
}
.toggle-btn:hover { color: #ccc; border-color: #666; }

.credits-remaining {
  color: #888;
  font-size: 11px;
}
.text-muted {
  color: #555;
}
</style>
