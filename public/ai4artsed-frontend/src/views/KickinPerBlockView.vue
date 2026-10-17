<template>
  <div class="perblock">
    <div class="header">
      <h1>Delayed Kick-In — research datasets</h1>

      <div class="dataset-bar">
        <label for="ds-select">Dataset:</label>
        <select id="ds-select" v-model="selectedId" @change="onDatasetChange" :disabled="datasets.length === 0">
          <option v-for="ds in datasets" :key="ds.id" :value="ds.id">
            {{ ds.label || ds.id }}
          </option>
        </select>
        <button class="refresh-btn" @click="fetchDatasets">Reload datasets</button>
      </div>

      <div v-if="currentMeta" class="meta">
        prompt_early: <b>{{ currentMeta.prompt_early }}</b>
        → prompt_full: <b>{{ currentMeta.prompt_full }}</b>
        · seed {{ currentMeta.seed }}
        · {{ currentMeta.steps }} steps
        · CFG {{ currentMeta.cfg }}
        · {{ currentMeta.width }}×{{ currentMeta.height }}
      </div>

      <div class="legend">
        Main run conditioned on <b>prompt_early</b>; hook(s) replace <code>encoder_hidden_states</code>
        at the target block(s) with the captured <b>prompt_full</b> trajectory from <i>step</i> onwards.
        Per-block: single block hooked. Cumulative: hooks on every block 0..N.
        Click an image to view at full resolution.
      </div>
    </div>

    <!-- LAUNCH SECTION -->
    <section class="section launch-section">
      <h2>New run</h2>
      <div class="launch-grid">
        <label class="launch-field">
          Run name
          <input v-model="launcher.name" type="text" class="probe-input">
        </label>
        <label class="launch-field">
          prompt_early
          <input v-model="launcher.promptEarly" type="text" class="probe-input">
        </label>
        <label class="launch-field">
          prompt_full
          <input v-model="launcher.promptFull" type="text" class="probe-input">
        </label>
        <label>
          Seed
          <input v-model.number="launcher.seed" type="number" class="probe-input">
        </label>
        <button class="probe-btn secondary" @click="randomizeSeed" :disabled="launcher.busy">
          Random seed
        </button>
      </div>
      <div class="launch-actions">
        <button class="probe-btn" @click="launchSweep(['perblock'])"
                :disabled="launcher.busy || !launcherValid">Start per-block</button>
        <button class="probe-btn" @click="launchSweep(['cumulative'])"
                :disabled="launcher.busy || !launcherValid">Start cumulative</button>
        <button class="probe-btn" @click="launchSweep(['perblock', 'cumulative'])"
                :disabled="launcher.busy || !launcherValid">Start both</button>
      </div>
      <div v-if="launcher.error" class="probe-error">{{ launcher.error }}</div>
      <div v-if="launcher.lastMessage" class="launch-status">{{ launcher.lastMessage }}</div>
    </section>

    <!-- PER-BLOCK SECTION -->
    <section class="section">
      <h2>Per-block (single hook on block N)</h2>
      <div class="status">
        <span v-if="perblock.loading">Loading…</span>
        <span v-else>
          {{ perblock.completed.length }} / {{ perblock.total }} blocks complete
          <span v-if="perblock.inProgress.length > 0">
            · block {{ perblock.inProgress[0] }} in progress</span>
        </span>
        <button class="refresh-btn" @click="fetchPerblock" :disabled="perblock.loading">Refresh</button>
      </div>

      <div v-if="perblockSorted.length > 0" class="grid" :style="gridStyle">
        <div class="corner">Block ↓ / step →</div>
        <div v-for="k in steps" :key="`ph-${k}`" class="col-header">{{ stepLabel(k) }}</div>

        <template v-for="block in perblockSorted" :key="`pr-${block}`">
          <div class="row-header">
            <div class="block-num">Block {{ pad2(block) }}</div>
          </div>
          <div v-for="k in steps" :key="`pc-${block}-${k}`" class="cell"
               @click="showFullscreen(`/api/dev/kickin-research/${selectedId}/perblock/${block}/kickin_${pad2(k)}.png`)">
            <img :src="`/api/dev/kickin-research/${selectedId}/perblock/${block}/kickin_${pad2(k)}.png`"
                 :alt="`block ${block} step ${k}`" loading="lazy">
          </div>
        </template>
      </div>
      <div v-else class="empty-state">No per-block data yet for this dataset.</div>
      <div v-if="perblockPending.length > 0" class="pending-list">
        Pending: {{ perblockPending.map(pad2).join(', ') }}
      </div>
    </section>

    <!-- CUMULATIVE SECTION -->
    <section class="section">
      <h2>Cumulative (hooks on every block 0..N)</h2>
      <div class="status">
        <span v-if="cumul.loading">Loading…</span>
        <span v-else>
          {{ cumul.completed.length }} / {{ cumul.total }} depths complete
          <span v-if="cumul.inProgress.length > 0">
            · depth {{ cumul.inProgress[0] }} in progress</span>
        </span>
        <button class="refresh-btn" @click="fetchCumul" :disabled="cumul.loading">Refresh</button>
      </div>

      <div v-if="cumulSorted.length > 0" class="grid" :style="gridStyle">
        <div class="corner">up_to N ↓ / step →</div>
        <div v-for="k in steps" :key="`ch-${k}`" class="col-header">{{ stepLabel(k) }}</div>

        <template v-for="upto in cumulSorted" :key="`cr-${upto}`">
          <div class="row-header">
            <div class="block-num">0..{{ pad2(upto) }}</div>
          </div>
          <div v-for="k in steps" :key="`cc-${upto}-${k}`" class="cell"
               @click="showFullscreen(`/api/dev/kickin-research/${selectedId}/cumulative/${upto}/kickin_${pad2(k)}.png`)">
            <img :src="`/api/dev/kickin-research/${selectedId}/cumulative/${upto}/kickin_${pad2(k)}.png`"
                 :alt="`up_to ${upto} step ${k}`" loading="lazy">
          </div>
        </template>
      </div>
      <div v-else class="empty-state">No cumulative data yet for this dataset.</div>
      <div v-if="cumulPending.length > 0" class="pending-list">
        Pending: {{ cumulPending.map(pad2).join(', ') }}
      </div>
    </section>

    <!-- The platform's one fullscreen layer; see components/MediaFullscreen.vue. -->
    <MediaFullscreen :src="fullscreenSrc" @close="fullscreenSrc = null" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'

import { STANDARD_SEED } from '@/composables/useSeedAutomatic'
interface DatasetMeta {
  id: string
  label?: string
  prompt_early?: string
  prompt_full?: string
  seed?: number
  steps?: number
  cfg?: number
  width?: number
  height?: number
  kickin_steps?: number[]
}

interface StatusResponse {
  completed_blocks: number[]
  in_progress_blocks: number[]
  total_blocks: number
  kickin_steps: number[]
}

const datasets = ref<DatasetMeta[]>([])
const selectedId = ref<string>('')
const steps = ref<number[]>([0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 14, 18, 23])
const fullscreenSrc = ref<string | null>(null)

const launcher = reactive({
  name: '',
  promptEarly: '',
  promptFull: '',
  seed: STANDARD_SEED,
  busy: false,
  error: '' as string,
  lastMessage: '' as string,
})

const launcherValid = computed(() =>
  launcher.name.trim().length > 0
  && launcher.promptEarly.trim().length > 0
  && launcher.promptFull.trim().length > 0
)

function randomizeSeed() {
  launcher.seed = Math.floor(Math.random() * 2147483647)
}

async function launchSweep(sweepTypes: string[]) {
  if (launcher.busy || !launcherValid.value) return
  launcher.busy = true
  launcher.error = ''
  launcher.lastMessage = ''
  try {
    const r = await fetch('/api/dev/research-sweep/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id: launcher.name.trim(),
        prompt_early: launcher.promptEarly.trim(),
        prompt_full: launcher.promptFull.trim(),
        seed: launcher.seed,
        sweep_types: sweepTypes,
      }),
    })
    const data = await r.json()
    if (!r.ok || !data.success) {
      launcher.error = data.error || `HTTP ${r.status}`
      return
    }
    launcher.lastMessage =
      `Launched dataset_id="${data.dataset_id}" seed=${data.seed} (${sweepTypes.join(' → ')}). `
      + `Log: ${data.log_file}. Dropdown will refresh automatically when the dataset folder appears.`
    await fetchDatasets()
  } catch (e) {
    launcher.error = (e as Error).message
  } finally {
    launcher.busy = false
  }
}

const perblock = reactive({
  loading: false,
  completed: [] as number[],
  inProgress: [] as number[],
  total: 38,
  completedSet: new Set<number>(),
  inProgressSet: new Set<number>(),
})

const cumul = reactive({
  loading: false,
  completed: [] as number[],
  inProgress: [] as number[],
  total: 38,
  completedSet: new Set<number>(),
  inProgressSet: new Set<number>(),
})

const currentMeta = computed(() => datasets.value.find(d => d.id === selectedId.value) || null)
const perblockSorted = computed(() => [...perblock.completed].sort((a, b) => a - b))
const cumulSorted = computed(() => [...cumul.completed].sort((a, b) => a - b))
const allIndices = computed(() => Array.from({ length: perblock.total }, (_, i) => i))
const perblockPending = computed(() => allIndices.value.filter(i => !perblock.completedSet.has(i)))
const cumulPending = computed(() => allIndices.value.filter(i => !cumul.completedSet.has(i)))

const gridStyle = computed(() => ({
  gridTemplateColumns: `100px repeat(${steps.value.length}, minmax(0, 1fr))`,
}))

const pad2 = (n: number) => String(n).padStart(2, '0')
const stepLabel = (k: number) => k === 0 ? 'step=0 (full)' : `step=${k}`

function showFullscreen(src: string) {
  fullscreenSrc.value = src
}

async function fetchDatasets() {
  try {
    const r = await fetch('/api/dev/kickin-research/datasets')
    if (!r.ok) return
    const data = await r.json()
    datasets.value = data.datasets || []
    const last = datasets.value[datasets.value.length - 1]
    if (last && !datasets.value.find(d => d.id === selectedId.value)) {
      selectedId.value = last.id
      onDatasetChange()
    }
  } catch (e) {
    console.error('[KickinView] datasets fetch failed:', e)
  }
}

async function fetchStatusFor(kind: 'perblock' | 'cumulative', target: typeof perblock) {
  if (!selectedId.value) return
  target.loading = true
  try {
    const r = await fetch(`/api/dev/kickin-research/${selectedId.value}/${kind}/status`)
    if (r.ok) {
      const data: StatusResponse = await r.json()
      target.completed = data.completed_blocks
      target.inProgress = data.in_progress_blocks
      target.total = data.total_blocks
      target.completedSet = new Set(data.completed_blocks)
      target.inProgressSet = new Set(data.in_progress_blocks)
      if (data.kickin_steps && data.kickin_steps.length > 0) steps.value = data.kickin_steps
    }
  } catch (e) {
    console.error('[KickinView] status fetch failed:', kind, e)
  } finally {
    target.loading = false
  }
}

const fetchPerblock = () => fetchStatusFor('perblock', perblock)
const fetchCumul = () => fetchStatusFor('cumulative', cumul)

function onDatasetChange() {
  perblock.completed = []; perblock.inProgress = []
  perblock.completedSet = new Set(); perblock.inProgressSet = new Set()
  cumul.completed = []; cumul.inProgress = []
  cumul.completedSet = new Set(); cumul.inProgressSet = new Set()
  fetchPerblock()
  fetchCumul()
}

let pollTimer: number | null = null

onMounted(async () => {
  await fetchDatasets()
  pollTimer = window.setInterval(() => {
    fetchPerblock()
    fetchCumul()
  }, 30_000)
})

onUnmounted(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
})
</script>

<style scoped>
.perblock {
  background: var(--bg-base);
  color: #ddd;
  min-height: 100%;
  padding: 24px;
  font-family: var(--font-sans);
}
.header h1 { font-size: 22px; margin: 0 0 10px 0; }

.dataset-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.dataset-bar label {
  font-size: 12px;
  color: #aaa;
}
.dataset-bar select {
  background: var(--surface-1);
  color: #ddd;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  padding: 5px 10px;
  font-size: 13px;
  min-width: 320px;
}

.meta { color: #888; font-size: 13px; margin-bottom: 12px; }
.legend {
  color: #888;
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 12px;
  max-width: 1100px;
}
.section { margin-top: 28px; }

.launch-section {
  background: var(--surface-1);
  border: 1px solid var(--surface-3);
  border-radius: 6px;
  padding: 16px;
}
.launch-grid {
  display: grid;
  grid-template-columns: 1fr 2fr 2fr 1fr auto;
  gap: 10px;
  align-items: end;
  margin-bottom: 10px;
}
.launch-grid label {
  display: flex;
  flex-direction: column;
  font-size: 11px;
  color: #aaa;
  gap: 4px;
}
.launch-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}
.launch-status {
  font-size: 12px;
  color: #9cf;
  padding: 6px 10px;
  background: #0e1a26;
  border-radius: 3px;
  margin-top: 8px;
}
.probe-input {
  background: var(--surface-1);
  color: #ddd;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  padding: 6px 8px;
  font-size: 13px;
  width: 100%;
}
.probe-input:focus {
  outline: none;
  border-color: #4af;
}
.probe-btn {
  background: #1c4a6e;
  color: #fff;
  border: 1px solid #2a6080;
  border-radius: 3px;
  padding: 7px 14px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.probe-btn.secondary { background: var(--surface-2); color: #ddd; border-color: var(--surface-4); }
.probe-btn:hover:not(:disabled) { filter: brightness(1.15); }
.probe-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.probe-error {
  color: #d96b5a;
  font-size: 12px;
  padding: 6px 10px;
  background: #2a1a1a;
  border-radius: 3px;
  margin-bottom: 10px;
}
.probe-history {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}
.probe-item {
  background: var(--surface-1);
  border-radius: 4px;
  overflow: hidden;
}
.probe-image {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  display: block;
  cursor: pointer;
  transition: outline 0.1s;
}
.probe-image:hover { outline: 1px solid #4af; }
.probe-caption {
  padding: 6px 8px;
}
.probe-prompt {
  font-size: 11px;
  color: #ddd;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.probe-meta {
  font-size: 10px;
  color: #777;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}
@media (max-width: 800px) {
  .probe-grid { grid-template-columns: 1fr; }
}
.section h2 {
  color: #9cf;
  font-size: 16px;
  margin: 0 0 8px 0;
}
.status {
  color: #aaa;
  font-size: 12px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.refresh-btn {
  background: var(--surface-2);
  color: #ddd;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  padding: 4px 10px;
  font-size: 11px;
  cursor: pointer;
}
.refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.refresh-btn:hover:not(:disabled) { background: var(--surface-3); }

.grid {
  display: grid;
  gap: 4px;
}
.corner {
  font-size: 10px;
  color: #555;
  padding: 4px;
  text-align: center;
  align-self: end;
}
.col-header {
  font-size: 10px;
  color: #aaa;
  text-align: center;
  padding: 4px 2px;
  align-self: end;
  word-break: break-word;
}
.row-header {
  font-size: 11px;
  color: #9cf;
  padding: 6px 4px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.block-num { font-variant-numeric: tabular-nums; }
.cell {
  background: var(--surface-1);
  border-radius: 3px;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  position: relative;
  cursor: pointer;
  transition: outline 0.1s;
}
.cell:hover { outline: 1px solid #4af; }
.cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pending-list {
  margin-top: 10px;
  font-size: 11px;
  color: #666;
  font-variant-numeric: tabular-nums;
}
.empty-state {
  padding: 20px;
  color: #555;
  font-size: 13px;
  font-style: italic;
  text-align: center;
  background: var(--bg-base);
  border: 1px dashed var(--surface-2);
  border-radius: 4px;
}

</style>
