<template>
  <div class="rave-container">
    <div class="rave-header">
      <h1>RAVE Training — mini70</h1>
      <div class="status-badge" :class="status.running ? 'running' : 'stopped'">
        {{ status.running ? 'TRAINING' : 'STOPPED' }}
      </div>
    </div>

    <!-- Status Panel -->
    <div class="section">
      <h2>Status</h2>
      <table class="info-table">
        <tbody>
          <tr>
            <td class="label-cell">State</td>
            <td class="value-cell">
              <span v-if="status.running" style="color: #4CAF50; font-weight: 600;">
                Running (PID {{ status.pid }})
              </span>
              <span v-else style="color: #999;">Stopped</span>
            </td>
          </tr>
          <tr v-if="status.epoch !== null">
            <td class="label-cell">Epoch</td>
            <td class="value-cell">{{ status.epoch }}</td>
          </tr>
          <tr v-if="status.total_steps !== null">
            <td class="label-cell">Steps</td>
            <td class="value-cell">
              {{ formatNumber(status.total_steps) }} / {{ formatNumber(status.max_steps) }}
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
              </div>
              <span class="help-text">{{ progressPercent.toFixed(1) }}%</span>
            </td>
          </tr>
          <tr v-if="status.checkpoint">
            <td class="label-cell">Checkpoint</td>
            <td class="value-cell mono">{{ shortPath(status.checkpoint) }}</td>
          </tr>
          <tr v-if="status.exported_model">
            <td class="label-cell">Exported Model</td>
            <td class="value-cell mono">{{ shortPath(status.exported_model) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Controls -->
    <div class="section">
      <h2>Controls</h2>
      <div class="button-row">
        <button
          v-if="!status.running && !status.checkpoint"
          class="action-btn start"
          @click="doAction('start')"
          :disabled="actionInProgress"
        >Start Training</button>

        <button
          v-if="!status.running && status.checkpoint"
          class="action-btn resume"
          @click="doAction('resume')"
          :disabled="actionInProgress"
        >Resume Training</button>

        <button
          v-if="status.running"
          class="action-btn stop"
          @click="doAction('stop')"
          :disabled="actionInProgress"
        >Stop Training</button>

        <button
          class="action-btn"
          @click="doAction('export')"
          :disabled="actionInProgress || status.running"
          :title="status.running ? 'Stop training first' : ''"
        >Export Model</button>

        <button
          class="action-btn"
          @click="doAction('test')"
          :disabled="actionInProgress"
        >Test Reconstruction</button>

        <button
          class="action-btn"
          @click="fetchMetrics"
          :disabled="metricsLoading"
        >{{ metricsLoading ? 'Loading...' : 'Refresh Metrics' }}</button>
      </div>
      <div v-if="actionMessage" class="action-message" :class="{ error: !actionSuccess }">
        {{ actionMessage }}
      </div>
    </div>

    <!-- Schedule -->
    <div class="section">
      <h2>Schedule</h2>
      <div class="schedule-top-row">
        <label class="toggle-label">
          <input type="checkbox" v-model="schedule.enabled" @change="saveSchedule" />
          Enabled
        </label>
        <label class="toggle-label">
          <input type="checkbox" v-model="schedule.manual_override" @change="saveSchedule" />
          Manual override
        </label>
        <div class="schedule-status-inline">
          <span v-if="!schedule.enabled" style="color: #999;">Off</span>
          <span v-else-if="schedule.manual_override" style="color: #ffa726;">Paused</span>
          <span v-else-if="scheduleShould === true" style="color: #4CAF50;">Active</span>
          <span v-else-if="scheduleShould === false" style="color: #999;">Outside hours</span>
        </div>
      </div>

      <div v-if="schedule.enabled" class="schedule-slots">
        <div v-for="(slot, i) in schedule.slots" :key="i" class="schedule-slot">
          <div class="slot-header">Slot {{ i + 1 }}</div>
          <div class="slot-times">
            <input type="time" v-model="slot.start" @change="saveSchedule" class="time-input" step="3600" />
            <span class="schedule-label">—</span>
            <input type="time" v-model="slot.stop" @change="saveSchedule" class="time-input" step="3600" />
          </div>
          <div class="slot-days">
            <button
              v-for="(label, key) in dayLabels"
              :key="key"
              :class="['day-btn', { active: slot.days[key] }]"
              @click="slot.days[key] = !slot.days[key]; saveSchedule()"
            >{{ label }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Metrics Charts -->
    <div v-if="Object.keys(metrics).length > 0" class="section">
      <h2>Training Metrics</h2>
      <div class="charts-grid">
        <div v-for="(data, tag) in metrics" :key="tag" class="chart-card">
          <div class="chart-title">{{ formatTag(tag) }}</div>
          <div class="chart-info">
            {{ data.values.length }} points | last: {{ data.values[data.values.length - 1]?.toFixed(4) }}
            @ step {{ formatNumber(data.steps[data.steps.length - 1]) }}
          </div>
          <svg :viewBox="`0 0 600 200`" class="chart-svg" preserveAspectRatio="none">
            <!-- Grid lines -->
            <line x1="0" y1="50" x2="600" y2="50" stroke="#333" stroke-width="0.5" />
            <line x1="0" y1="100" x2="600" y2="100" stroke="#333" stroke-width="0.5" />
            <line x1="0" y1="150" x2="600" y2="150" stroke="#333" stroke-width="0.5" />
            <!-- Data line -->
            <polyline
              :points="chartPoints(data)"
              fill="none"
              :stroke="chartColor(tag)"
              stroke-width="1.5"
              vector-effect="non-scaling-stroke"
            />
          </svg>
        </div>
      </div>
    </div>

    <!-- Test Reconstructions -->
    <div v-if="status.test_files && status.test_files.length > 0" class="section">
      <h2>Test Reconstructions</h2>
      <div class="audio-grid">
        <div v-for="file in status.test_files" :key="file" class="audio-card">
          <div class="audio-label">{{ file }}</div>
          <audio controls :src="'/api/rave/test-audio/' + file" preload="none"></audio>
        </div>
      </div>
    </div>

    <!-- Log -->
    <div v-if="status.log_tail && status.log_tail.length > 0" class="section">
      <h2>Training Log</h2>
      <pre class="log-output">{{ status.log_tail.join('\n') }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const status = ref({
  running: false,
  pid: null,
  epoch: null,
  step: null,
  total_steps: null,
  max_steps: 6000000,
  checkpoint: null,
  exported_model: null,
  log_tail: [],
  test_files: [],
})

const metrics = ref({})
const metricsLoading = ref(false)
const actionInProgress = ref(false)
const actionMessage = ref('')
const actionSuccess = ref(true)
const defaultSlot = () => ({
  start: '00:00', stop: '00:00',
  days: { mon: true, tue: true, wed: true, thu: true, fri: true, sat: true, sun: true },
})
const schedule = ref({
  enabled: false,
  manual_override: false,
  slots: [
    { start: '22:00', stop: '07:00', days: { mon: true, tue: true, wed: true, thu: true, fri: true, sat: true, sun: true } },
    { start: '00:00', stop: '00:00', days: { mon: false, tue: false, wed: false, thu: false, fri: false, sat: false, sun: false } },
    { start: '00:00', stop: '00:00', days: { mon: false, tue: false, wed: false, thu: false, fri: false, sat: false, sun: false } },
  ],
})
const scheduleShould = ref(null)
const dayLabels = { mon: 'Mo', tue: 'Tu', wed: 'We', thu: 'Th', fri: 'Fr', sat: 'Sa', sun: 'Su' }
let pollInterval = null
let scheduleInterval = null

const progressPercent = computed(() => {
  if (!status.value.total_steps || !status.value.max_steps) return 0
  return (status.value.total_steps / status.value.max_steps) * 100
})

const TAG_COLORS = {
  fullband_spectral_distance: '#42a5f5',
  multiband_spectral_distance: '#66bb6a',
  adversarial: '#ef5350',
  loss_dis: '#ff7043',
  feature_matching: '#ab47bc',
  validation: '#ffa726',
}

function formatNumber(n) {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString()
}

function formatTag(tag) {
  return tag.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function shortPath(p) {
  if (!p) return ''
  const parts = p.split('/')
  const idx = parts.indexOf('runs')
  return idx >= 0 ? parts.slice(idx).join('/') : parts.slice(-3).join('/')
}

function chartColor(tag) {
  return TAG_COLORS[tag] || '#888'
}

function chartPoints(data) {
  if (!data.values || data.values.length === 0) return ''
  const vals = data.values
  const minV = Math.min(...vals)
  const maxV = Math.max(...vals)
  const range = maxV - minV || 1
  const w = 600
  const h = 200
  const pad = 10

  return vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * w
    const y = pad + ((maxV - v) / range) * (h - 2 * pad)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/rave/status', { credentials: 'include' })
    if (res.ok) {
      status.value = await res.json()
    }
  } catch (e) {
    console.warn('[RAVE] Status fetch failed:', e)
  }
}

async function fetchSchedule() {
  try {
    const res = await fetch('/api/rave/schedule', { credentials: 'include' })
    if (res.ok) {
      const data = await res.json()
      schedule.value = { ...schedule.value, ...data }
      scheduleShould.value = data.should_train
    }
  } catch (e) {
    console.warn('[RAVE] Schedule fetch failed:', e)
  }
}

async function saveSchedule() {
  try {
    await fetch('/api/rave/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(schedule.value),
    })
  } catch (e) {
    console.warn('[RAVE] Schedule save failed:', e)
  }
}

async function scheduleTick() {
  if (!schedule.value.enabled) return
  try {
    await fetch('/api/rave/schedule/tick', {
      method: 'POST',
      credentials: 'include',
    })
    fetchStatus()
  } catch (e) {
    // silent
  }
}

async function fetchMetrics() {
  metricsLoading.value = true
  try {
    const res = await fetch('/api/rave/metrics', { credentials: 'include' })
    if (res.ok) {
      const data = await res.json()
      if (data.metrics) {
        metrics.value = data.metrics
      }
    }
  } catch (e) {
    console.warn('[RAVE] Metrics fetch failed:', e)
  } finally {
    metricsLoading.value = false
  }
}

async function doAction(action) {
  actionInProgress.value = true
  actionMessage.value = `Running ${action}...`
  actionSuccess.value = true

  try {
    const res = await fetch(`/api/rave/${action}`, {
      method: 'POST',
      credentials: 'include',
    })
    const data = await res.json()

    if (data.success) {
      actionMessage.value = `${action} completed.`
      actionSuccess.value = true
    } else {
      actionMessage.value = data.error || data.stderr || `${action} failed`
      actionSuccess.value = false
    }

    setTimeout(fetchStatus, 1000)
  } catch (e) {
    actionMessage.value = `Error: ${e.message}`
    actionSuccess.value = false
  } finally {
    actionInProgress.value = false
    setTimeout(() => { actionMessage.value = '' }, 5000)
  }
}

onMounted(() => {
  fetchStatus()
  fetchMetrics()
  fetchSchedule()
  pollInterval = setInterval(fetchStatus, 5000)
  scheduleInterval = setInterval(scheduleTick, 30000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (scheduleInterval) clearInterval(scheduleInterval)
})
</script>

<style scoped>
.rave-container {
  min-height: 100vh;
  background: #000;
  padding: 20px;
  padding-bottom: 120px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  color: #fff;
}

.rave-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  background: #fff;
  border: 1px solid #ccc;
  padding: 15px;
}

.rave-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.status-badge {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  border-radius: 3px;
}

.status-badge.running {
  background: #1b5e20;
  color: #a5d6a7;
  border: 1px solid #4CAF50;
}

.status-badge.stopped {
  background: #333;
  color: #999;
  border: 1px solid #666;
}

.section {
  background: #fff;
  border: 1px solid #ccc;
  padding: 15px;
  margin-bottom: 16px;
}

.section h2 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.info-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #999;
}

.info-table tr { border-bottom: 1px solid #ddd; }
.info-table tr:last-child { border-bottom: none; }

.label-cell {
  width: 180px;
  padding: 8px 12px;
  background: #f0f0f0;
  font-weight: 500;
  font-size: 13px;
  color: #000;
  border-right: 1px solid #999;
}

.value-cell {
  padding: 8px 12px;
  font-size: 13px;
  color: #000;
}

.value-cell.mono {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.progress-bar {
  width: 100%;
  max-width: 400px;
  height: 6px;
  background: #e0e0e0;
  border-radius: 3px;
  margin: 6px 0 4px;
}

.progress-fill {
  height: 100%;
  background: #4CAF50;
  border-radius: 3px;
  transition: width 0.5s;
}

.help-text {
  color: #666;
  font-size: 12px;
}

.button-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.action-btn {
  background: #555;
  color: #fff;
  border: 1px solid #999;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.action-btn:hover:not(:disabled) { background: #777; }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.action-btn.start { background: #1b5e20; border-color: #4CAF50; }
.action-btn.start:hover:not(:disabled) { background: #2e7d32; }
.action-btn.resume { background: #0d47a1; border-color: #42a5f5; }
.action-btn.resume:hover:not(:disabled) { background: #1565c0; }
.action-btn.stop { background: #b71c1c; border-color: #ef5350; }
.action-btn.stop:hover:not(:disabled) { background: #c62828; }

.action-message {
  margin-top: 10px;
  font-size: 13px;
  color: #333;
  padding: 8px 12px;
  background: #e8f5e9;
  border: 1px solid #4CAF50;
}

.action-message.error {
  background: #ffebee;
  border-color: #ef5350;
  color: #b71c1c;
}

/* Schedule */
.schedule-top-row {
  display: flex;
  align-items: center;
  gap: 20px;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #333;
  cursor: pointer;
}

.toggle-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
}

.schedule-status-inline {
  font-size: 12px;
  font-weight: 600;
  margin-left: auto;
}

.schedule-slots {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ddd;
}

.schedule-slot {
  background: #f5f5f5;
  border: 1px solid #ddd;
  padding: 10px;
}

.slot-header {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}

.slot-times {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.schedule-label {
  font-size: 13px;
  color: #333;
}

.time-input {
  padding: 4px 6px;
  border: 1px solid #ccc;
  font-size: 13px;
  font-family: monospace;
  background: white;
  color: #000;
  width: 80px;
}

.slot-days {
  display: flex;
  gap: 2px;
}

.day-btn {
  padding: 4px 6px;
  border: 1px solid #ccc;
  background: #e0e0e0;
  color: #666;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}

.day-btn.active {
  background: #1b5e20;
  color: #fff;
  border-color: #4CAF50;
}

.day-btn:hover { opacity: 0.8; }

/* Charts */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}

.chart-card {
  background: #1a1a1a;
  border: 1px solid #333;
  padding: 12px;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #ccc;
  margin-bottom: 4px;
}

.chart-info {
  font-size: 11px;
  color: #666;
  margin-bottom: 8px;
  font-family: 'Courier New', monospace;
}

.chart-svg {
  width: 100%;
  height: 120px;
  background: #111;
  border: 1px solid #222;
}

/* Audio */
.audio-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.audio-card {
  background: #f5f5f5;
  border: 1px solid #ddd;
  padding: 10px;
}

.audio-label {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #333;
  margin-bottom: 6px;
}

.audio-card audio {
  width: 100%;
}

.log-output {
  background: #1a1a1a;
  color: #aaa;
  padding: 12px;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
  border: 1px solid #333;
}
</style>
