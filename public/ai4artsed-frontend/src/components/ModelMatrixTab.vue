<template>
  <div class="matrix-container">
    <div class="matrix-header">
      <h2>Model Selection Matrix</h2>
      <p class="help">
        Click a column header to apply that preset. Vision models are always local and auto-selected based on your hardware.
      </p>
      <p v-if="props.detectedVramTier" class="hardware-info">
        Detected Hardware: <strong>{{ getVramLabel(props.detectedVramTier) }}</strong>
        <span class="vision-note">→ Vision: {{ getVisionModel() }}</span>
      </p>
    </div>

    <div class="matrix-scroll-container">
      <table class="model-matrix">
        <thead>
          <!-- Column headers -->
          <tr class="column-header-row">
            <th class="row-label-header">Application Area</th>
            <!-- Local column -->
            <th
              class="column-header local-column"
              :class="{
                'column-active': props.selectedProvider === 'none' || props.selectedProvider === 'local'
              }"
              @click="applyPreset('local')"
              title="Click to use local models only"
            >
              <span class="col-label">Local</span>
              <span class="vram-sub">({{ getVramLabel(props.detectedVramTier || 'vram_16') }})</span>
              <span class="dsgvo-badge dsgvo-ok">DSGVO</span>
            </th>
            <!-- Cloud columns -->
            <th
              v-for="col in cloudColumns"
              :key="col.id"
              class="column-header cloud-column"
              :class="{
                'column-active': props.selectedProvider === col.id,
                'dsgvo-warning': !col.dsgvoCompliant
              }"
              @click="applyPreset(col.id)"
              :title="'Click to use ' + col.label + ' for LLM tasks'"
            >
              <span class="col-label">{{ col.label }}</span>
              <span v-if="col.dsgvoCompliant" class="dsgvo-badge dsgvo-ok">DSGVO</span>
              <span v-else class="dsgvo-badge dsgvo-no">US</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in matrixRows" :key="row.field" class="data-row" :class="{ 'vision-row': isVisionField(row.field) }">
            <td class="row-label">
              <span class="stage-badge">{{ row.stage }}</span>
              {{ row.label }}
              <span v-if="isVisionField(row.field)" class="local-only-badge">LOCAL</span>
            </td>
            <!-- Local column -->
            <td
              class="matrix-cell"
              :class="{
                'cell-active': isCellActive(row.field, 'local'),
                'cell-highlighted': props.selectedProvider === 'none' || props.selectedProvider === 'local'
              }"
              :title="getLocalModel(row.field)"
            >
              <span class="model-name">{{ getShortModelName(getLocalModel(row.field)) }}</span>
              <span v-if="isCellActive(row.field, 'local')" class="active-indicator"></span>
            </td>
            <!-- Cloud columns -->
            <td
              v-for="col in cloudColumns"
              :key="col.id"
              class="matrix-cell"
              :class="{
                'cell-active': isCellActive(row.field, col.id),
                'cell-highlighted': props.selectedProvider === col.id,
                'dsgvo-warning-cell': !col.dsgvoCompliant,
                'vision-auto-cell': isVisionField(row.field)
              }"
              :title="getCloudModel(col.id, row.field)"
            >
              <span v-if="isVisionField(row.field)" class="model-name auto-vision">
                auto (local)
              </span>
              <span v-else class="model-name">{{ getShortModelName(getCloudModel(col.id, row.field)) }}</span>
              <span v-if="isCellActive(row.field, col.id)" class="active-indicator"></span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="matrix-legend">
      <span class="legend-item">
        <span class="legend-color active-color"></span> Current selection
      </span>
      <span class="legend-item">
        <span class="legend-color dsgvo-color"></span> DSGVO compliant
      </span>
      <span class="legend-item">
        <span class="legend-color us-color"></span> NOT DSGVO
      </span>
      <span class="legend-item">
        <span class="legend-color vision-color"></span> Vision (always local)
      </span>
    </div>

    <div class="matrix-notes">
      <p><strong>Vision models</strong> are always run locally and selected based on your VRAM. They work with any LLM provider.</p>
      <p><strong>OpenRouter:</strong> EU server routing configurable, but NOT DSGVO compliant (US company).</p>
    </div>

    <!-- Developer: Edit Matrix Button -->
    <div class="matrix-edit-section">
      <button @click="openJsonEditor" class="edit-matrix-btn">
        Edit Matrix (JSON)
      </button>
      <span v-if="saveMessage" :class="['save-message', { 'error': !saveSuccess }]">
        {{ saveMessage }}
      </span>
    </div>

    <!-- JSON Editor Modal -->
    <div v-if="showJsonEditor" class="json-editor-overlay" @click.self="closeJsonEditor">
      <div class="json-editor-modal">
        <div class="json-editor-header">
          <h3>Edit Hardware Matrix (JSON)</h3>
          <button @click="closeJsonEditor" class="close-btn">&times;</button>
        </div>
        <div class="json-editor-body">
          <textarea
            v-model="jsonContent"
            class="json-textarea"
            spellcheck="false"
          ></textarea>
          <p v-if="jsonError" class="json-error">{{ jsonError }}</p>
        </div>
        <div class="json-editor-footer">
          <button @click="validateJson" class="validate-btn">Validate</button>
          <button @click="saveMatrix" class="save-btn" :disabled="!!jsonError">Save</button>
          <button @click="closeJsonEditor" class="cancel-btn">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ModelField, MatrixRow, VramTier } from '@/types/settings'

// New matrix structure types
interface NewHardwareMatrix {
  vision_presets: Record<string, Record<string, string>>
  llm_presets: Record<string, {
    label: string
    EXTERNAL_LLM_PROVIDER: string
    DSGVO_CONFORMITY: boolean
    models: Record<string, string>
  }>
  local_llm_presets: Record<string, {
    label: string
    EXTERNAL_LLM_PROVIDER: string
    DSGVO_CONFORMITY: boolean
    models: Record<string, string>
  }>
}

interface CloudColumn {
  id: string
  label: string
  dsgvoCompliant: boolean
}

// JSON Editor state
const showJsonEditor = ref(false)
const jsonContent = ref('')
const jsonError = ref('')
const saveMessage = ref('')
const saveSuccess = ref(true)

const props = defineProps<{
  matrix: NewHardwareMatrix
  currentSettings: Record<string, string>
  selectedProvider: string
  detectedVramTier: VramTier | null
}>()

const emit = defineEmits<{
  (e: 'apply-preset', provider: string): void
  (e: 'matrix-updated'): void
}>()

// Cloud column definitions (4 providers)
const cloudColumns: CloudColumn[] = [
  { id: 'mistral', label: 'Mistral EU', dsgvoCompliant: true },
  { id: 'ionos', label: 'IONOS EU', dsgvoCompliant: true },
  { id: 'anthropic', label: 'Anthropic', dsgvoCompliant: false },
  { id: 'openai', label: 'OpenAI', dsgvoCompliant: false },
  { id: 'openrouter', label: 'OpenRouter', dsgvoCompliant: false },
]

// Vision fields that are always local
const visionFields: ModelField[] = ['STAGE1_VISION_MODEL', 'IMAGE_ANALYSIS_MODEL']

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

// Get vision model for detected VRAM
function getVisionModel(): string {
  const vramTier = props.detectedVramTier || 'vram_16'
  const vision = props.matrix?.vision_presets?.[vramTier]
  if (vision?.STAGE1_VISION_MODEL) {
    return getShortModelName(vision.STAGE1_VISION_MODEL)
  }
  return 'auto'
}

// Row definitions
const matrixRows: MatrixRow[] = [
  { field: 'STAGE1_TEXT_MODEL', label: 'Text Model', stage: 'S1' },
  { field: 'STAGE1_VISION_MODEL', label: 'Vision Model', stage: 'S1' },
  { field: 'STAGE2_INTERCEPTION_MODEL', label: 'Interception', stage: 'S2' },
  { field: 'STAGE2_OPTIMIZATION_MODEL', label: 'Optimization', stage: 'S2' },
  { field: 'STAGE3_MODEL', label: 'Translation/Safety', stage: 'S3' },
  { field: 'STAGE4_LEGACY_MODEL', label: 'Legacy Model', stage: 'S4' },
  { field: 'CHAT_HELPER_MODEL', label: 'Chat Helper', stage: 'H' },
  { field: 'IMAGE_ANALYSIS_MODEL', label: 'Image Analysis', stage: 'H' },
  { field: 'CODING_MODEL', label: 'Coding', stage: 'H' },
]

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

// Get shortened model name for display
function getShortModelName(fullModel: string): string {
  if (!fullModel || fullModel === '-') return '-'

  // Remove all provider prefixes (local/, ionos/openai/, ionos/meta-llama/, etc.)
  // Strip known provider prefixes, then known org prefixes
  let name = fullModel
    .replace(/^(local|bedrock|mistral|ionos|anthropic|openai|openrouter)\//, '')
    .replace(/^(openai|meta-llama|mistralai|openGPT-X)\//, '')

  // Shorten long model names
  if (name.length > 22) {
    // Try to find a meaningful short form
    // e.g. "Meta-Llama-3.1-405B-Instruct-FP8" → "Llama-3.1-405B"
    const match = name.match(/(Llama[- ]\d[\w.-]*\d+B|gpt-oss[:\-]\w+|Mistral[- ]\w+|claude[- ]\w+)/i)
    if (match?.[1]) return match[1]
    return name.substring(0, 18) + '...'
  }
  return name
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

// JSON Editor functions
function openJsonEditor() {
  jsonContent.value = JSON.stringify(props.matrix, null, 2)
  jsonError.value = ''
  showJsonEditor.value = true
}

function closeJsonEditor() {
  showJsonEditor.value = false
  jsonError.value = ''
}

function validateJson() {
  try {
    JSON.parse(jsonContent.value)
    jsonError.value = ''
    saveMessage.value = 'JSON is valid'
    saveSuccess.value = true
    setTimeout(() => { saveMessage.value = '' }, 2000)
  } catch (e) {
    jsonError.value = `Invalid JSON: ${(e as Error).message}`
  }
}

async function saveMatrix() {
  try {
    const matrixData = JSON.parse(jsonContent.value)
    jsonError.value = ''

    const response = await fetch('/api/settings/hardware-matrix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(matrixData)
    })

    const result = await response.json()

    if (result.success) {
      saveMessage.value = 'Matrix saved successfully'
      saveSuccess.value = true
      showJsonEditor.value = false
      emit('matrix-updated')
    } else {
      saveMessage.value = result.error || 'Save failed'
      saveSuccess.value = false
    }
  } catch (e) {
    jsonError.value = `Error: ${(e as Error).message}`
    saveMessage.value = 'Save failed'
    saveSuccess.value = false
  }

  setTimeout(() => { saveMessage.value = '' }, 3000)
}
</script>

<style scoped>
.matrix-container {
  background: #fff;
  border: 1px solid #ccc;
  padding: 15px;
}

.matrix-header {
  margin-bottom: 15px;
}

.matrix-header h2 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.matrix-header .help {
  margin: 0;
  font-size: 13px;
  color: #666;
}

.matrix-header .hardware-info {
  margin: 8px 0 0 0;
  font-size: 13px;
  color: #1565c0;
  background: #e3f2fd;
  padding: 6px 10px;
  border-radius: 4px;
  display: inline-block;
}

.vision-note {
  margin-left: 10px;
  color: #2e7d32;
  font-weight: normal;
}

.matrix-scroll-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.model-matrix {
  width: 100%;
  min-width: 700px;
  border-collapse: collapse;
  font-size: 12px;
}

.row-label-header {
  background: #f0f0f0;
  color: #333;
  font-weight: 500;
  text-align: left;
  padding: 8px 10px;
  width: 160px;
  min-width: 160px;
  position: sticky;
  left: 0;
  z-index: 2;
  border: 1px solid #999;
}

/* Column headers */
.column-header-row th {
  padding: 8px 6px;
  text-align: center;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid #999;
  vertical-align: middle;
}

.column-header:hover {
  filter: brightness(0.9);
}

.local-column {
  background: #e8f5e9;
  color: #1b5e20;
  min-width: 100px;
}

.cloud-column {
  background: #e3f2fd;
  color: #0d47a1;
  min-width: 100px;
}

.cloud-column.dsgvo-warning {
  background: #fff3e0;
  color: #e65100;
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
  font-weight: normal;
  opacity: 0.8;
}

.dsgvo-badge {
  display: inline-block;
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
  margin-top: 3px;
}

.dsgvo-ok {
  background: #4caf50;
  color: #fff;
}

.dsgvo-no {
  background: #ff9800;
  color: #fff;
}

/* Data rows */
.data-row {
  border-bottom: 1px solid #ddd;
}

.data-row:hover {
  background: #fafafa;
}

.vision-row {
  background: #f1f8e9;
}

.vision-row:hover {
  background: #e8f5e9;
}

.row-label {
  background: #f5f5f5;
  padding: 6px 10px;
  font-weight: 500;
  color: #333;
  text-align: left;
  white-space: nowrap;
  position: sticky;
  left: 0;
  z-index: 1;
  border-right: 1px solid #999;
}

.stage-badge {
  display: inline-block;
  width: 22px;
  text-align: center;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: #666;
  border-radius: 3px;
  margin-right: 6px;
  padding: 1px 0;
}

.local-only-badge {
  display: inline-block;
  font-size: 8px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
  background: #2e7d32;
  color: #fff;
  margin-left: 6px;
}

/* Matrix cells */
.matrix-cell {
  padding: 5px 4px;
  text-align: center;
  border: 1px solid #e0e0e0;
  position: relative;
  transition: all 0.15s ease;
}

.matrix-cell:hover {
  background: #f0f0f0;
}

.cell-highlighted {
  background: #e3f2fd !important;
}

.cell-active {
  background: #bbdefb !important;
  font-weight: 600;
}

.dsgvo-warning-cell {
  background: #fff8e1;
}

.vision-auto-cell {
  background: #f1f8e9 !important;
}

.vision-auto-cell.cell-highlighted {
  background: #c8e6c9 !important;
}

.model-name {
  font-family: 'Courier New', monospace;
  font-size: 10px;
  color: #333;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 90px;
}

.model-name.auto-vision {
  color: #2e7d32;
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
  border-top: 1px solid #ddd;
  font-size: 12px;
  color: #666;
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
  border: 1px solid #ccc;
}

.active-color {
  background: #bbdefb;
}

.dsgvo-color {
  background: #4caf50;
}

.us-color {
  background: #ff9800;
}

.vision-color {
  background: #c8e6c9;
}

/* Notes section */
.matrix-notes {
  margin-top: 12px;
  padding: 10px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  color: #555;
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
    max-width: 70px;
  }

  .row-label {
    font-size: 11px;
    padding: 4px 6px;
  }

  .col-label {
    font-size: 10px;
  }
}

/* JSON Editor */
.matrix-edit-section {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ddd;
  display: flex;
  align-items: center;
  gap: 15px;
}

.edit-matrix-btn {
  background: #555;
  color: #fff;
  border: 1px solid #333;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
}

.edit-matrix-btn:hover {
  background: #666;
}

.save-message {
  font-size: 13px;
  color: #2e7d32;
}

.save-message.error {
  color: #c62828;
}

.json-editor-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.json-editor-modal {
  background: #fff;
  border-radius: 8px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.json-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #ddd;
  background: #f5f5f5;
  border-radius: 8px 8px 0 0;
}

.json-editor-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  line-height: 1;
}

.close-btn:hover {
  color: #333;
}

.json-editor-body {
  flex: 1;
  padding: 15px 20px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.json-textarea {
  width: 100%;
  flex: 1;
  min-height: 400px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  padding: 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  resize: none;
  line-height: 1.4;
}

.json-error {
  margin-top: 10px;
  padding: 8px 12px;
  background: #ffebee;
  color: #c62828;
  border-radius: 4px;
  font-size: 12px;
}

.json-editor-footer {
  padding: 15px 20px;
  border-top: 1px solid #ddd;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  background: #f5f5f5;
  border-radius: 0 0 8px 8px;
}

.validate-btn,
.save-btn,
.cancel-btn {
  padding: 8px 16px;
  font-size: 13px;
  border-radius: 4px;
  cursor: pointer;
}

.validate-btn {
  background: #fff;
  border: 1px solid #999;
  color: #333;
}

.save-btn {
  background: #2e7d32;
  border: 1px solid #1b5e20;
  color: #fff;
}

.save-btn:disabled {
  background: #ccc;
  border-color: #999;
  cursor: not-allowed;
}

.cancel-btn {
  background: #fff;
  border: 1px solid #999;
  color: #333;
}
</style>
