<template>
  <div class="matrix-container">
    <div class="matrix-header">
      <h2>{{ $t('settings.matrix.title') }}</h2>
      <p v-if="!editing" class="help">
        {{ $t('settings.matrix.help') }}
      </p>
      <p v-else class="help edit-hint">
        {{ $t('settings.matrix.editHelp') }}
        <code>mistral-large-latest</code>
        {{ $t('settings.matrix.editHelpTail') }}
      </p>
      <p v-if="props.detectedVramTier" class="hardware-info">
        {{ $t('settings.matrix.detectedHardware') }} <strong>{{ getVramLabel(props.detectedVramTier) }}</strong>
      </p>
    </div>

    <div class="matrix-scroll-container">
      <table class="model-matrix">
        <thead>
          <!-- Column headers -->
          <tr class="column-header-row">
            <th class="row-label-header">{{ $t('settings.matrix.applicationArea') }}</th>
            <!-- What the user set themselves. Not a provider: the rows here may come
                 from different services, so the recorded status sits on each cell. -->
            <th
              class="column-header user-column"
              :class="{ 'column-empty': !hasUserRecord }"
              @click="onUserColumnClick"
              :title="editing
                ? $t('settings.matrix.editingNoApply')
                : (hasUserRecord ? $t('settings.matrix.restoreUserTitle') : $t('settings.matrix.noUserRecord'))"
            >
              <span class="col-label">{{ $t('settings.matrix.lastUserSetting') }}</span>
            </th>
            <!-- Local column -->
            <th
              class="column-header local-column"
              :class="{
                'column-active': props.selectedProvider === 'none' || props.selectedProvider === 'local'
              }"
              @click="onHeaderClick('local')"
              :title="editing ? $t('settings.matrix.editingNoApply') : $t('settings.matrix.applyLocalTitle')"
            >
              <span class="col-label">{{ $t('settings.matrix.local') }}</span>
              <span class="vram-sub">({{ getVramLabel(props.detectedVramTier || 'vram_16') }})</span>
              <span
                v-if="localColumn.recorded === true"
                class="dsgvo-badge dsgvo-ok"
                :title="localColumn.note"
              >{{ $t('settings.matrix.dsgvo.yes') }}</span>
            </th>
            <!-- Cloud columns -->
            <th
              v-for="col in cloudColumns"
              :key="col.id"
              class="column-header cloud-column"
              :class="{
                'column-active': props.selectedProvider === col.id,
                'dsgvo-warning': col.recorded === false,
                'dsgvo-unrecorded': col.recorded === null
              }"
              @click="onHeaderClick(col.id)"
              :title="editing ? $t('settings.matrix.editingNoApply') : $t('settings.matrix.applyCloudTitle', { provider: col.label })"
            >
              <span class="col-label">{{ col.label }}</span>
              <span
                v-if="col.recorded === true"
                class="dsgvo-badge dsgvo-ok"
                :title="col.note"
              >{{ $t('settings.matrix.dsgvo.yes') }}</span>
              <span
                v-else-if="col.recorded === false"
                class="dsgvo-badge dsgvo-no"
                :title="col.note"
              >{{ $t('settings.matrix.dsgvo.no') }}</span>
              <span
                v-else
                class="dsgvo-badge dsgvo-unrecorded"
                :title="col.note || $t('settings.matrix.dsgvo.noneTitle')"
              >{{ $t('settings.matrix.dsgvo.none') }}</span>

              <!-- Whether this provider may answer for another one. The condition
                   is not shown per column on purpose: the chain is built per role,
                   from the saved setting, so one box could not state it truthfully. -->
              <label class="fallback-box" @click.stop
                     :title="$t('settings.matrix.fallbackTitle')">
                <input
                  type="checkbox"
                  :checked="editing ? draftFallback(col.id) : col.fallback"
                  :disabled="!editing"
                  @change="setDraftFallback(col.id, ($event.target as HTMLInputElement).checked)"
                />
                <span>{{ $t('settings.matrix.fallback') }}</span>
              </label>
              <!-- The operator records the status here, in the file this tab
                   edits -- with the grounds for it, which is what makes it an
                   entry rather than an assertion. -->
              <div v-if="editing" class="dsgvo-edit" @click.stop>
                <div class="dsgvo-switch">
                  <button
                    type="button"
                    class="dsgvo-switch-btn ok"
                    :class="{ picked: draftRecorded(col.id) === true }"
                    @click="setDraftRecorded(col.id, true)"
                    :title="$t('settings.matrix.dsgvo.setYesTitle')"
                  >{{ $t('settings.matrix.dsgvo.yes') }}</button>
                  <button
                    type="button"
                    class="dsgvo-switch-btn no"
                    :class="{ picked: draftRecorded(col.id) === false }"
                    @click="setDraftRecorded(col.id, false)"
                    :title="$t('settings.matrix.dsgvo.setNoTitle')"
                  >{{ $t('settings.matrix.dsgvo.setNoShort') }}</button>
                </div>
                <input
                  class="dsgvo-note-input"
                  :class="{ missing: draftRecorded(col.id) !== null && !draftNote(col.id).trim() }"
                  :value="draftNote(col.id)"
                  @input="setDraftNote(col.id, $event)"
                  :placeholder="$t('settings.matrix.dsgvo.notePlaceholder')"
                  spellcheck="false"
                />
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in matrixRows" :key="row.field" class="data-row" :class="{ 'vision-row': isVisionField(row.field) }">
            <td class="row-label">
              {{ row.label }}
              <span v-if="isVisionField(row.field)" class="local-only-badge">{{ $t('settings.matrix.localOnly') }}</span>
              <span
                v-if="props.defaultsInUse?.includes(row.field)"
                class="default-badge"
                :title="$t('settings.matrix.defaultBadgeTitle')"
              >{{ $t('settings.matrix.defaultBadge') }}</span>
            </td>
            <!-- What the user set themselves, with the status of the service THIS row
                 reaches -- handed over by the backend, never derived here. -->
            <td
              class="matrix-cell user-cell"
              :title="userRecord(row.field) ? displayModelName(userRecord(row.field)!.model) : ''"
            >
              <template v-if="userRecord(row.field)">
                <span class="model-name">{{ displayModelName(userRecord(row.field)!.model) }}</span>
                <span
                  class="cell-dsgvo"
                  :class="{
                    ok: userRecord(row.field)!.recorded === true,
                    no: userRecord(row.field)!.recorded === false,
                    none: userRecord(row.field)!.recorded === null
                  }"
                >{{ userRecord(row.field)!.service }} &middot; {{ cellStatusLabel(userRecord(row.field)!.recorded) }}</span>
              </template>
              <span v-else class="model-name">&ndash;</span>
            </td>
            <!-- Local column -->
            <td
              class="matrix-cell"
              :class="{
                'cell-active': isCellActive(row.field, 'local'),
                'cell-highlighted': props.selectedProvider === 'none' || props.selectedProvider === 'local'
              }"
              :title="displayModelName(getLocalModel(row.field))"
            >
              <input
                v-if="editing"
                class="cell-input"
                :value="draftValue('local', row.field)"
                @input="writeModel('local', row.field, ($event.target as HTMLInputElement).value)"
                spellcheck="false"
              />
              <template v-else>
                <span class="model-name">{{ displayModelName(getLocalModel(row.field)) }}</span>
                <span v-if="isCellActive(row.field, 'local')" class="active-indicator"></span>
              </template>
            </td>
            <!-- Cloud columns -->
            <td
              v-for="col in cloudColumns"
              :key="col.id"
              class="matrix-cell"
              :class="{
                'cell-active': isCellActive(row.field, col.id),
                'cell-highlighted': props.selectedProvider === col.id,
                'dsgvo-warning-cell': col.recorded === false,
                'vision-auto-cell': isVisionField(row.field)
              }"
              :title="displayModelName(getCloudModel(col.id, row.field))"
            >
              <span v-if="isVisionField(row.field)" class="model-name auto-vision">
                {{ $t('settings.matrix.autoLocal') }}
              </span>
              <input
                v-else-if="editing"
                class="cell-input"
                :value="draftValue(col.id, row.field)"
                @input="writeModel(col.id, row.field, ($event.target as HTMLInputElement).value)"
                spellcheck="false"
              />
              <template v-else>
                <span class="model-name">{{ displayModelName(getCloudModel(col.id, row.field)) }}</span>
                <span v-if="isCellActive(row.field, col.id)" class="active-indicator"></span>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="matrix-legend">
      <span class="legend-item">
        <span class="legend-color active-color"></span> {{ $t('settings.matrix.legend.selection') }}
      </span>
      <span class="legend-item">
        <span class="legend-color dsgvo-color"></span> {{ $t('settings.matrix.legend.dsgvo') }}
      </span>
      <span class="legend-item">
        <span class="legend-color notdsgvo-color"></span> {{ $t('settings.matrix.legend.notDsgvo') }}
      </span>
      <span class="legend-item">
        <span class="legend-color norecord-color"></span> {{ $t('settings.matrix.legend.noRecord') }}
      </span>
      <span class="legend-item">
        <span class="legend-color vision-color"></span> {{ $t('settings.matrix.legend.vision') }}
      </span>
    </div>

    <div class="matrix-notes">
      <p><strong>{{ $t('settings.matrix.visionTerm') }}</strong> {{ $t('settings.matrix.visionNote') }}</p>
    </div>

    <div class="matrix-edit-section">
      <template v-if="!editing">
        <button @click="startEditing" class="edit-matrix-btn">{{ $t('settings.matrix.edit') }}</button>
        <button @click="resetToDefaults" class="reset-btn" :disabled="busy">
          {{ $t('settings.matrix.reset') }}
        </button>
      </template>
      <template v-else>
        <button @click="saveMatrix" class="save-btn" :disabled="busy">{{ $t('settings.matrix.save') }}</button>
        <button @click="cancelEditing" class="cancel-btn" :disabled="busy">{{ $t('settings.matrix.cancel') }}</button>
      </template>
      <span v-if="saveMessage" :class="['save-message', { 'error': !saveSuccess }]">
        {{ saveMessage }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ModelField, MatrixRow, VramTier } from '@/types/settings'
import { MODEL_ROLES } from '@/data/modelRoles'
import { readDsgvoRecord } from '@/lib/dsgvoRecord'
import { modelShort } from '@/lib/modelPlace'

const { t } = useI18n()

// New matrix structure types
interface NewHardwareMatrix {
  vision_presets: Record<string, Record<string, string>>
  llm_presets: Record<string, LlmPreset>
  local_llm_presets: Record<string, LlmPreset>
}

// `DSGVO_CONFORMITY` is deliberately nullable: yes, no, and "nothing is
// recorded" are three different answers, and the third one is not the second.
// AWS Bedrock is the case that forces it -- it is compliant only if the AWS
// account is restricted to European regions, which this platform cannot see.
// A boolean would make whoever fills it in choose an untruth.
interface LlmPreset {
  label: string
  EXTERNAL_LLM_PROVIDER: string
  DSGVO_CONFORMITY: boolean | null
  DSGVO_NOTE?: string
  // Whether this column may answer for another one when a call fails. Absent is not
  // a yes: joining the chain is a decision somebody made, not a default.
  FALLBACK_ENABLED?: boolean
  models: Record<string, string>
}

// One recorded row of the user's own setting, as the backend hands it over: the model,
// the service it reaches, and what the register holds about that service.
interface UserRecordEntry {
  model: string
  service: string
  recorded: boolean | null
}

interface StatusColumn {
  id: string
  label: string
  recorded: boolean | null
  note: string
  fallback: boolean
}

// Editing state. `draft` holds a private copy of the matrix while editing, so a
// half-typed model name never reaches the running configuration.
const editing = ref(false)
const busy = ref(false)
const draft = ref<NewHardwareMatrix | null>(null)
const saveMessage = ref('')
const saveSuccess = ref(true)

const props = defineProps<{
  matrix: NewHardwareMatrix
  currentSettings: Record<string, string>
  selectedProvider: string
  detectedVramTier: VramTier | null
  defaultsInUse?: string[]
  lastUserModels?: Record<string, UserRecordEntry>
}>()

const emit = defineEmits<{
  (e: 'apply-preset', provider: string): void
  (e: 'matrix-updated'): void
}>()

// Order and short display label of the cloud columns. This is presentation --
// which column stands where, and what it is called on screen.
//
// What a provider's DSGVO status IS does NOT stand here and must never be
// written here again: it is configuration, it is read from hardware_matrix.json
// (the file this very tab edits), and frontend code is not a place to keep a
// data-protection statement. Until 2026-08-16 the flag stood in this array as a
// second, hand-kept list beside the file.
const COLUMN_ORDER: Array<{ id: string; label: string }> = [
  { id: 'mistral', label: 'Mistral EU' },
  { id: 'ionos', label: 'IONOS EU' },
  { id: 'mammouth', label: 'Mammouth EU' },
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'openrouter', label: 'OpenRouter' },
  { id: 'bedrock', label: 'AWS Bedrock' },
]

// The matrix decides WHICH providers exist and what is recorded about each. The
// list above only decides the order: a provider the matrix does not carry has no
// column, and one it carries beyond the list is appended under its own label.
const cloudColumns = computed<StatusColumn[]>(() => {
  const presets = props.matrix?.llm_presets || {}
  const known = COLUMN_ORDER.filter(col => presets[col.id])
  const extra = Object.keys(presets)
    .filter(id => !COLUMN_ORDER.some(col => col.id === id))
    .map(id => ({ id, label: presets[id]?.label || id }))
  return [...known, ...extra].map(col => ({
    ...col,
    ...readStatus(presets[col.id]),
    fallback: presets[col.id]?.FALLBACK_ENABLED === true
  }))
})

// The rule itself lives in lib/dsgvoRecord: the settings API tab reads the same
// register and must give the same answer.
const readStatus = readDsgvoRecord

// Same for the local column. Nothing leaves the installation there, and the
// matrix records exactly that per VRAM tier -- so it is read, not asserted.
const localColumn = computed<StatusColumn>(() => ({
  id: 'local',
  label: 'Local',
  ...readStatus(props.matrix?.local_llm_presets?.[currentVramTier()], false),
  // The local column carries no fallback box: what one picks as a fallback is by
  // nature an external service. Nothing to record here.
  fallback: false
}))

// --- what the user set themselves ----------------------------------------------
function userRecord(field: ModelField): UserRecordEntry | null {
  return props.lastUserModels?.[field] || null
}

const hasUserRecord = computed(() => Object.keys(props.lastUserModels || {}).length > 0)

function cellStatusLabel(recorded: boolean | null): string {
  if (recorded === true) return t('settings.matrix.dsgvo.yes')
  if (recorded === false) return t('settings.matrix.dsgvo.no')
  return t('settings.matrix.dsgvo.none')
}

async function onUserColumnClick() {
  if (editing.value || !hasUserRecord.value || busy.value) return
  busy.value = true
  try {
    const response = await fetch('/api/settings/apply-last-user-models', {
      method: 'POST',
      credentials: 'include',
    })
    const result = await response.json()
    if (result.success) {
      flash(t('settings.matrix.userSettingRestored'), true)
      emit('matrix-updated')
    } else {
      flash(result.error || t('settings.matrix.restoreFailed'), false)
    }
  } catch (e) {
    flash(t('settings.matrix.restoreFailedWith', { error: (e as Error).message }), false)
  } finally {
    busy.value = false
  }
}

// --- the fallback box ------------------------------------------------------------
// Ticking it records that this provider MAY answer for another one. Whether it then
// does is decided per role when a call fails, and only where the recorded
// data-protection status matches the one that role runs on -- not "as good or
// better": a run recorded as taking one data path must not quietly continue on
// another. That condition cannot be shown per column, because one column stands for
// every role at once.

function draftFallback(provider: string): boolean {
  return draftPreset(provider)?.FALLBACK_ENABLED === true
}

function setDraftFallback(provider: string, checked: boolean) {
  const preset = draftPreset(provider)
  if (!preset) return
  preset.FALLBACK_ENABLED = checked
}

// --- the register, while it is being edited -------------------------------
function draftPreset(provider: string): LlmPreset | null {
  return draft.value?.llm_presets?.[provider] || null
}

function draftRecorded(provider: string): boolean | null {
  const flag = draftPreset(provider)?.DSGVO_CONFORMITY
  return flag === null || flag === undefined ? null : Boolean(flag)
}

function draftNote(provider: string): string {
  return draftPreset(provider)?.DSGVO_NOTE || ''
}

// Clicking the side that is already picked takes the status back off -- that is
// the way to "nothing is recorded", which has to stay reachable.
function setDraftRecorded(provider: string, value: boolean) {
  const preset = draftPreset(provider)
  if (!preset) return
  preset.DSGVO_CONFORMITY = draftRecorded(provider) === value ? null : value
}

function setDraftNote(provider: string, event: Event) {
  const preset = draftPreset(provider)
  if (!preset) return
  preset.DSGVO_NOTE = (event.target as HTMLInputElement).value
}

// Refuse the save rather than write a status nobody has to answer for.
function unreasonedColumns(): string[] {
  const presets = draft.value?.llm_presets || {}
  return Object.keys(presets)
    .filter(id => {
      const flag = presets[id]?.DSGVO_CONFORMITY
      return flag !== null && flag !== undefined && !(presets[id]?.DSGVO_NOTE || '').trim()
    })
    .map(id => presets[id]?.label || id)
}

// Vision fields that are always local
const visionFields: ModelField[] = ['IMAGE_ANALYSIS_MODEL']

function isVisionField(field: ModelField): boolean {
  return visionFields.includes(field)
}

// Helper to get VRAM label
function getVramLabel(tier: VramTier | string): string {
  const labels: Record<string, string> = {
    'vram_8': '8 GB',
    'vram_16': '16 GB',
    'vram_24': '24 GB',
    'vram_32': '32 GB',
    'vram_48': '48 GB',
    'vram_96': '96 GB',
  }
  return labels[tier] || tier
}


// Row definitions -- the names and the order come from the one list every
// surface reads. A second set of names stood here until 2026-08-16 and made the
// two tables read as if they configured different things.
const matrixRows = computed<MatrixRow[]>(() =>
  MODEL_ROLES.map(role => ({ field: role.field, label: t(role.labelKey) }))
)

// Get local model (from local_llm_presets + vision_presets)
function getLocalModel(field: ModelField): string {
  const vramTier = props.detectedVramTier || 'vram_16'

  if (isVisionField(field)) {
    return props.matrix?.vision_presets?.[vramTier]?.[field] || '-'
  }

  return props.matrix?.local_llm_presets?.[vramTier]?.models?.[field] || '-'
}

// Get cloud model (from llm_presets, vision always from vision_presets)
function getCloudModel(provider: string, field: ModelField): string {
  const vramTier = props.detectedVramTier || 'vram_16'

  if (isVisionField(field)) {
    // Vision is always local
    return props.matrix?.vision_presets?.[vramTier]?.[field] || '-'
  }

  return props.matrix?.llm_presets?.[provider]?.models?.[field] || '-'
}

// What a cell shows is the model's own path, the part after the service — the
// platform's one reading of an id (lib/modelPlace.ts). The service is never
// shown and never asked for: the column already says which
// provider a cell belongs to, and the backend puts the service in front of
// what the operator typed when the matrix is saved
// (settings_routes._prefix_cells). Until then a regex here listed eight
// service names of its own. The path is shown in full — never truncated.
function displayModelName(fullModel: string): string {
  if (!fullModel || fullModel === '-') return '-'
  return modelShort(fullModel)
}

function currentVramTier(): string {
  return props.detectedVramTier || 'vram_16'
}

// The value shown in an editable cell — the model's own path, the same as the
// cell shows when it is not being edited. What the operator types is stored as
// typed; the service goes in front of it in the backend.
function draftValue(provider: string, field: ModelField): string {
  const m = draft.value
  if (!m) return ''
  const tier = currentVramTier()
  if (isVisionField(field)) return modelShort(m.vision_presets?.[tier]?.[field] || '')
  if (provider === 'local') return modelShort(m.local_llm_presets?.[tier]?.models?.[field] || '')
  return modelShort(m.llm_presets?.[provider]?.models?.[field] || '')
}

function writeModel(provider: string, field: ModelField, value: string) {
  const m = draft.value
  if (!m) return
  const tier = currentVramTier()

  if (isVisionField(field)) {
    if (!m.vision_presets[tier]) m.vision_presets[tier] = {}
    m.vision_presets[tier][field] = value
    return
  }

  if (provider === 'local') {
    if (!m.local_llm_presets[tier]) {
      m.local_llm_presets[tier] = {
        label: tier, EXTERNAL_LLM_PROVIDER: 'none', DSGVO_CONFORMITY: true, models: {},
      }
    }
    if (!m.local_llm_presets[tier].models) m.local_llm_presets[tier].models = {}
    m.local_llm_presets[tier].models[field] = value
    return
  }

  if (!m.llm_presets[provider]) {
    // A conformity value is never invented here. It comes from the matrix, and
    // where the matrix says nothing, nothing is claimed -- false, never a green
    // badge conjured out of a list in this file. (Until 2026-08-16 this seeded
    // the entry from the hardcoded column array, which wrote a frontend
    // statement about data protection back into the configuration.)
    const preset = props.matrix?.llm_presets?.[provider]
    m.llm_presets[provider] = {
      label: preset?.label || provider,
      EXTERNAL_LLM_PROVIDER: provider,
      DSGVO_CONFORMITY: preset?.DSGVO_CONFORMITY ?? null,
      DSGVO_NOTE: preset?.DSGVO_NOTE || '',
      models: {},
    }
  }
  if (!m.llm_presets[provider].models) m.llm_presets[provider].models = {}
  m.llm_presets[provider].models[field] = value
}

function startEditing() {
  draft.value = JSON.parse(JSON.stringify(props.matrix || {})) as NewHardwareMatrix
  if (!draft.value.vision_presets) draft.value.vision_presets = {}
  if (!draft.value.llm_presets) draft.value.llm_presets = {}
  if (!draft.value.local_llm_presets) draft.value.local_llm_presets = {}
  saveMessage.value = ''
  editing.value = true
}

function cancelEditing() {
  editing.value = false
  draft.value = null
  saveMessage.value = ''
}

// A cell left empty means "this preset does not cover that role" — store the
// absence, not an empty model id, which downstream code would treat as configured.
function stripEmptyModels(matrix: NewHardwareMatrix): NewHardwareMatrix {
  const out = JSON.parse(JSON.stringify(matrix)) as NewHardwareMatrix
  for (const tier of Object.keys(out.vision_presets || {})) {
    const preset = out.vision_presets[tier]
    if (!preset) continue
    for (const [field, value] of Object.entries(preset)) {
      if (!String(value).trim()) delete preset[field]
    }
  }
  for (const group of [out.llm_presets, out.local_llm_presets]) {
    for (const key of Object.keys(group || {})) {
      const models = group[key]?.models || {}
      for (const [field, value] of Object.entries(models)) {
        if (!String(value).trim()) delete models[field]
      }
    }
  }
  return out
}

function flash(message: string, ok: boolean) {
  saveMessage.value = message
  saveSuccess.value = ok
  setTimeout(() => { saveMessage.value = '' }, 4000)
}

// Check if a specific cell matches current settings
function isCellActive(field: ModelField, provider: string): boolean {
  const currentModel = props.currentSettings?.[field]
  if (!currentModel) return false

  let presetModel: string
  if (provider === 'local') {
    presetModel = getLocalModel(field)
  } else {
    presetModel = getCloudModel(provider, field)
  }

  return currentModel === presetModel
}

// Apply preset when column header is clicked
function applyPreset(provider: string) {
  emit('apply-preset', provider)
}

function onHeaderClick(provider: string) {
  if (editing.value) return
  applyPreset(provider)
}

async function saveMatrix() {
  if (!draft.value) return

  const unreasoned = unreasonedColumns()
  if (unreasoned.length) {
    flash(t('settings.matrix.dsgvo.noteMissing', { columns: unreasoned.join(', ') }), false)
    return
  }

  busy.value = true
  try {
    const response = await fetch('/api/settings/hardware-matrix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(stripEmptyModels(draft.value)),
    })
    const result = await response.json()

    if (result.success) {
      editing.value = false
      draft.value = null
      flash(t('settings.matrix.saved'), true)
      emit('matrix-updated')
    } else {
      flash(result.error || t('settings.matrix.saveFailed'), false)
    }
  } catch (e) {
    flash(t('settings.matrix.saveFailedWith', { error: (e as Error).message }), false)
  } finally {
    busy.value = false
  }
}

async function resetToDefaults() {
  const confirmed = window.confirm(t('settings.matrix.resetConfirm'))
  if (!confirmed) return

  busy.value = true
  try {
    const response = await fetch('/api/settings/hardware-matrix/reset', {
      method: 'POST',
      credentials: 'include',
    })
    const result = await response.json()

    if (result.success) {
      editing.value = false
      draft.value = null
      flash(t('settings.matrix.resetDone'), true)
      emit('matrix-updated')
    } else {
      flash(result.error || t('settings.matrix.resetFailed'), false)
    }
  } catch (e) {
    flash(t('settings.matrix.resetFailedWith', { error: (e as Error).message }), false)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.matrix-container {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  padding: 15px;
}

.matrix-header {
  margin-bottom: 15px;
}

.matrix-header h2 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 700;
  color: #e0e0e0;
}

.matrix-header .help {
  margin: 0;
  font-size: 13px;
  color: #b0b0b0;
}

.matrix-header .hardware-info {
  margin: 8px 0 0 0;
  font-size: 13px;
  color: #64b5f6;
  background: rgba(33, 150, 243, 0.14);
  padding: 6px 10px;
  border-radius: 4px;
  display: inline-block;
}

.matrix-scroll-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.model-matrix {
  width: 100%;
  min-width: 1100px;
  border-collapse: collapse;
  font-size: 12px;
  table-layout: fixed;
}

.row-label-header {
  background: var(--surface-2);
  color: #e0e0e0;
  font-weight: 400;
  text-align: left;
  padding: 8px 10px;
  width: 160px;
  min-width: 160px;
  position: sticky;
  left: 0;
  z-index: 2;
  border: 1px solid var(--surface-4);
}

/* Column headers */
.column-header-row th {
  padding: 8px 6px;
  text-align: center;
  font-weight: 400;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid var(--surface-4);
  vertical-align: middle;
}

.column-header:hover {
  filter: brightness(0.9);
}

.local-column {
  background: rgba(76, 175, 80, 0.14);
  color: #81c784;
  min-width: 130px;
}

.cloud-column {
  background: rgba(33, 150, 243, 0.14);
  color: #82b1ff;
  min-width: 130px;
}

.cloud-column.dsgvo-warning {
  background: rgba(229, 57, 53, 0.12);
  color: #ff7b72;
}

.cloud-column.dsgvo-unrecorded {
  background: rgba(160, 160, 160, 0.10);
  color: #b8b8b8;
}

.column-active {
  box-shadow: inset 0 0 0 3px #2196f3;
  font-weight: 700;
}

.col-label {
  display: block;
  font-size: 12px;
  margin-bottom: 2px;
}

.vram-sub {
  display: block;
  font-size: 10px;
  font-weight: 400;
  opacity: 0.8;
}

.dsgvo-badge {
  display: inline-block;
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 700;
  margin-top: 3px;
}

.dsgvo-ok {
  background: #4caf50;
  color: #fff;
}

.dsgvo-no {
  background: #e53935;
  color: #fff;
}

.dsgvo-unrecorded {
  background: #5a5a5a;
  color: #e8e8e8;
}

/* The operator's control. It sits in the column head only while editing, so a
   status and its grounds are set where the status is read. */
.dsgvo-edit {
  display: block;
  margin-top: 5px;
  cursor: default;
}

.dsgvo-switch {
  display: flex;
  gap: 2px;
  justify-content: center;
}

.dsgvo-switch-btn {
  flex: 1;
  font-size: 9px;
  font-weight: 700;
  padding: 2px 0;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  background: transparent;
  color: #999;
  cursor: pointer;
}

.dsgvo-switch-btn:hover {
  border-color: #888;
  color: #ddd;
}

.dsgvo-switch-btn.ok.picked {
  background: #4caf50;
  border-color: #4caf50;
  color: #fff;
}

.dsgvo-switch-btn.no.picked {
  background: #e53935;
  border-color: #e53935;
  color: #fff;
}

.dsgvo-note-input {
  width: 100%;
  margin-top: 3px;
  padding: 2px 4px;
  font-size: 9px;
  font-weight: 400;
  font-family: inherit;
  background: var(--surface-4);
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  color: #e0e0e0;
}

.dsgvo-note-input::placeholder {
  color: #777;
}

.dsgvo-note-input.missing {
  border-color: #e53935;
}

/* Data rows */
.data-row {
  border-bottom: 1px solid var(--surface-4);
}

.data-row:hover {
  background: var(--surface-2);
}

.vision-row {
  background: rgba(76, 175, 80, 0.14);
}

.vision-row:hover {
  background: rgba(76, 175, 80, 0.22);
}

.user-column {
  background: rgb(var(--surface-3-rgb) / 0.9);
  color: #cfd8e3;
}

.user-column.column-empty {
  opacity: 0.55;
  cursor: default;
}

.user-cell {
  background: rgb(var(--surface-2-rgb) / 0.75);
}

.cell-dsgvo {
  display: block;
  font-size: 9px;
  letter-spacing: 0.04em;
  margin-top: 2px;
  opacity: 0.85;
}

.cell-dsgvo.ok { color: #81c784; }
.cell-dsgvo.no { color: #e57373; }
.cell-dsgvo.none { color: #9e9e9e; }

.fallback-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 9px;
  font-weight: 400;
  letter-spacing: 0.03em;
  cursor: pointer;
}

.fallback-box input[disabled] {
  cursor: not-allowed;
}

.fallback-box:has(input[disabled]) {
  opacity: 0.45;
  cursor: not-allowed;
}

.row-label {
  background: var(--surface-2);
  padding: 6px 10px;
  font-weight: 400;
  color: #e0e0e0;
  text-align: left;
  /* The role names say what the model is to do, so they are sentences rather
     than single words. They wrap instead of pushing the provider columns off
     the right edge -- this column is sticky and would otherwise eat the table. */
  white-space: normal;
  max-width: 210px;
  line-height: 1.3;
  position: sticky;
  left: 0;
  z-index: 1;
  border-right: 1px solid var(--surface-4);
}

.local-only-badge {
  display: inline-block;
  font-size: 8px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 700;
  background: #2e7d32;
  color: #fff;
  margin-left: 6px;
}

.default-badge {
  display: inline-block;
  font-size: 8px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 700;
  background: #ff9800;
  color: #fff;
  margin-left: 6px;
}

/* Matrix cells */
.matrix-cell {
  padding: 5px 4px;
  text-align: center;
  border: 1px solid var(--surface-4);
  position: relative;
  transition: all 0.15s ease;
}

.matrix-cell:hover {
  background: var(--surface-2);
}

.cell-highlighted {
  background: rgba(33, 150, 243, 0.14) !important;
}

.cell-active {
  background: rgba(33, 150, 243, 0.20) !important;
  font-weight: 700;
}

.dsgvo-warning-cell {
  background: rgba(229, 57, 53, 0.12);
}

.vision-auto-cell {
  background: rgba(76, 175, 80, 0.14) !important;
}

.vision-auto-cell.cell-highlighted {
  background: rgba(76, 175, 80, 0.14) !important;
}

/* Model ids are shown in full — they are the thing being configured, so they
   wrap rather than getting cut off. */
.model-name {
  font-family: 'Courier New', monospace;
  font-size: 10px;
  line-height: 1.35;
  color: #e0e0e0;
  display: block;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.cell-input {
  width: 100%;
  box-sizing: border-box;
  font-family: 'Courier New', monospace;
  font-size: 10px;
  padding: 4px 5px;
  background: var(--bg-base);
  color: #f2f2f2;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
}

.cell-input:focus {
  outline: none;
  border-color: #2196f3;
}

.edit-hint code {
  font-family: 'Courier New', monospace;
  background: var(--surface-2);
  padding: 1px 4px;
  border-radius: 3px;
}

.model-name.auto-vision {
  color: #66bb6a;
  font-style: italic;
  font-family: inherit;
}

.active-indicator {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 8px;
  height: 8px;
  background: #2196f3;
  border-radius: 50%;
}

/* Legend */
.matrix-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--surface-4);
  font-size: 12px;
  color: #b0b0b0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-color {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid var(--surface-4);
}

.active-color {
  background: rgba(33, 150, 243, 0.20);
}

.dsgvo-color {
  background: #4caf50;
}

.notdsgvo-color {
  background: #e53935;
}

.norecord-color {
  background: #5a5a5a;
}

.vision-color {
  background: rgba(76, 175, 80, 0.14);
}

/* Notes section */
.matrix-notes {
  margin-top: 12px;
  padding: 10px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  font-size: 12px;
  color: #c0c0c0;
}

.matrix-notes p {
  margin: 4px 0;
}

.matrix-notes p:first-child {
  margin-top: 0;
}

.matrix-notes p:last-child {
  margin-bottom: 0;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .matrix-header .help {
    font-size: 11px;
  }

  .model-matrix {
    font-size: 10px;
  }

  .model-name {
    font-size: 9px;
  }

  .row-label {
    font-size: 11px;
    padding: 4px 6px;
  }

  .col-label {
    font-size: 10px;
  }
}

/* Edit / reset toolbar */
.matrix-edit-section {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid var(--surface-4);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.edit-matrix-btn,
.reset-btn,
.save-btn,
.cancel-btn {
  padding: 8px 16px;
  font-size: 13px;
  border-radius: 4px;
  cursor: pointer;
}

.edit-matrix-btn {
  background: var(--surface-4);
  color: #fff;
  border: 1px solid var(--surface-4);
}

.edit-matrix-btn:hover {
  background: #666;
}

.reset-btn {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  color: #e0e0e0;
}

.reset-btn:hover:not(:disabled) {
  background: var(--surface-3);
}

.save-btn {
  background: #2e7d32;
  border: 1px solid #1b5e20;
  color: #fff;
}

.save-btn:hover:not(:disabled) {
  background: #388e3c;
}

.cancel-btn {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  color: #e0e0e0;
}

.cancel-btn:hover:not(:disabled) {
  background: var(--surface-3);
}

.edit-matrix-btn:disabled,
.reset-btn:disabled,
.save-btn:disabled,
.cancel-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.save-message {
  font-size: 13px;
  color: #66bb6a;
}

.save-message.error {
  color: #ff7b72;
}
</style>
