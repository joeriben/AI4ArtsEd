<template>
  <div class="workshop-page">
    <h1 class="page-title">{{ $t('workshop.title') }}</h1>

    <!-- Trashy Chat -->
    <div class="trashy-section">
      <div class="chat-header">
        <img :src="trashyIcon" alt="Trashy" class="trashy-icon" />
        <span class="chat-title">Trashy</span>
      </div>

      <div class="chat-messages" ref="messagesRef">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="chat-bubble"
          :class="msg.role"
        >
          {{ msg.content }}
        </div>
        <div v-if="isLoading" class="chat-bubble assistant loading">
          <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
        </div>
      </div>

      <div class="chat-input-area">
        <input
          v-model="userInput"
          class="chat-input"
          :placeholder="t('trashy.placeholder')"
          @keydown.enter="sendMessage"
          :disabled="isLoading"
        />
      </div>
    </div>

    <!-- Memory Visualization -->
    <div class="memory-section">
      <div class="memory-label">{{ $t('workshop.memory.label') }}</div>
      <div
        class="memory-container"
        @dragover.prevent="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
        :class="{ 'drag-over': isDragOver }"
      >
        <!-- Loaded models (already on GPU, shown individually) -->
        <div
          v-for="lm in loadedModelSegments"
          :key="'loaded-' + lm.name"
          class="memory-segment loaded"
          :style="{ width: segmentWidth(lm.gb) + '%' }"
        >
          <span class="segment-label">{{ lm.name }}</span>
          <button class="segment-remove" @click="confirmUnload(lm)">&times;</button>
        </div>
        <!-- Safety models (individually labeled) -->
        <div
          v-for="sm in safetyModelSegments"
          :key="'safety-' + sm.name"
          class="memory-segment safety"
          :style="{ width: segmentWidth(sm.vram_gb) + '%' }"
        >
          <span class="segment-label">{{ sm.name }}</span>
        </div>
        <!-- Remaining system overhead (CUDA caches, ComfyUI, misc) -->
        <div
          v-if="systemOverheadGb > 0.5"
          class="memory-segment system-overhead"
          :style="{ width: segmentWidth(systemOverheadGb) + '%' }"
        >
          <span class="segment-label">{{ $t('workshop.memory.system') }}</span>
        </div>
        <!-- Selected models (not yet loaded) -->
        <div
          v-for="model in unloadedSelectedModels"
          :key="model.id"
          class="memory-segment model"
          :style="{ width: segmentWidth(model.vram_gb) + '%' }"
          draggable="true"
          @dragstart="onDragStartFromMemory($event, model)"
        >
          <span class="segment-label">{{ model.name }}</span>
          <button class="segment-remove" @click="removeModel(model.id)">&times;</button>
        </div>
        <!-- Free space -->
        <div class="memory-segment free" :style="{ width: freePercent + '%' }">
          <span v-if="freePercent > 12" class="free-label">{{ $t('workshop.memory.free') }}</span>
        </div>
      </div>
      <div class="memory-stats">
        {{ $t('workshop.memory.used', { used: usedGb, total: totalGb }) }}
        <span v-if="overBudget" class="over-budget">{{ $t('workshop.memory.overBudget') }}</span>
      </div>
      <div class="memory-actions">
        <button
          v-if="preloadableSelected.length > 0"
          class="action-btn load-btn"
          :disabled="isPreloading"
          @click="preloadModels"
        >
          {{ isPreloading ? $t('workshop.confirm.loading') : $t('workshop.confirm.load') }}
        </button>
        <button
          v-if="loadedModelSegments.length > 0"
          class="action-btn clear-btn"
          :disabled="isPreloading"
          @click="confirmClearAll"
        >
          {{ $t('workshop.actions.clearAll') }}
        </button>
      </div>
    </div>

    <!-- Model Cards -->
    <div class="models-section">
      <div class="models-label">{{ $t('workshop.models.label') }}</div>
      <div class="models-grid">
        <div
          v-for="model in physicalModels"
          :key="model.id"
          class="model-card"
          :class="{
            'is-selected': isSelected(model.id),
            'is-cloud': !model.local,
            'is-loaded': isAlreadyLoaded(model.id),
          }"
          draggable="true"
          @dragstart="onDragStart($event, model)"
          @click="toggleModel(model)"
        >
          <div class="card-header">
            <span class="card-media-badge" :class="model.media_type">{{ mediaLabel(model.media_type) }}</span>
          </div>
          <div class="card-title">{{ model.name }}</div>
          <div class="card-facts">
            <div v-if="model.local" class="card-fact">
              {{ $t('workshop.models.needsGb', { gb: model.vram_gb }) }}
              <span v-if="isAlreadyLoaded(model.id)" class="loaded-badge">{{ $t('workshop.models.loaded') }}</span>
            </div>
            <div v-else class="card-fact cloud-fact">
              {{ model.cloud_region === 'EU' ? $t('workshop.models.cloudEu') : $t('workshop.models.cloudUs') }}
            </div>
            <div class="card-fact">{{ model.gen_time }}</div>
          </div>
          <div v-if="model.note" class="card-note">{{ model.note }}</div>
          <div class="card-publisher">{{ model.publisher }}</div>
        </div>
      </div>
    </div>

    <!-- Planning summary -->
    <div v-if="selectedModels.length > 0" class="planning-summary">
      <div v-if="overBudget" class="over-budget-notice">{{ $t('workshop.memory.overBudget') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useGpuStatus, SAFETY_VRAM_GB, SAFETY_MODELS, COMFYUI_OVERHEAD_GB, type PhysicalModel } from '@/composables/useGpuStatus'
import { SUPPORTED_LANGUAGES } from '@/i18n'
import trashyIcon from '@/assets/trashy-icon.png'

const { t, locale } = useI18n()

const { status, refresh, metaphors, physicalModels } = useGpuStatus()

// --- Selected Models (planning only — models load on first generate) ---
const selectedModels = ref<PhysicalModel[]>([])


const totalGb = computed(() => {
  if (!status.value) return 0
  return Math.round(status.value.totalMb / 1024)
})

/** Baseline = safety models + overhead (known constants, not live PyTorch data) */
const baselineGb = computed(() => SAFETY_VRAM_GB)

/** Check if a physical model is already loaded on the GPU */
const LOADED_MODEL_PATTERNS: Record<string, string[]> = {
  sd35_large: ['stable-diffusion-3.5', 'sd3.5'],
  flux2: ['FLUX.2', 'flux2', 'flux1'],
  qwen_t2i: ['qwen', 'Qwen2.5-VL'],
  qwen_i2i: ['qwen', 'Qwen2.5-VL'],
  qwen_multi: ['qwen', 'Qwen2.5-VL'],
  wan22_t2v: ['wan', 'Wan2.1', 'umt5'],
  wan22_i2v: ['wan', 'Wan2.1', 'umt5'],
  ltx_video: ['ltx', 'LTX'],
  heartmula: ['heartmula', 'HeartMuLa'],
  acestep: ['ace', 'ACE-Step'],
  stable_audio: ['stable_audio', 'stable-audio'],
}

function isAlreadyLoaded(id: string): boolean {
  if (!status.value) return false
  const patterns = LOADED_MODEL_PATTERNS[id]
  if (!patterns) return false
  return status.value.loadedModels.some(
    m => patterns.some(p => m.model.includes(p) || m.backend.includes(p))
  )
}

/** Loaded models as named segments for the memory bar */
const loadedModelSegments = computed(() => {
  if (!status.value) return []
  return status.value.loadedModels
    .filter(m => m.vram_mb > 500) // skip tiny models
    .map(m => ({
      name: m.model.split('/').pop()?.replace(/-/g, ' ') || m.backend,
      gb: Math.round(m.vram_mb / 1024),
      backend: m.backend,
      model: m.model,
    }))
})

const loadedModelsVramGb = computed(() =>
  loadedModelSegments.value.reduce((sum, m) => sum + m.gb, 0)
)

/** Safety model segments for the memory bar */
const safetyModelSegments = computed(() => [...SAFETY_MODELS])

const safetyModelsVramGb = computed(() =>
  SAFETY_MODELS.reduce((sum, m) => sum + m.vram_gb, 0)
)

/** Remaining system overhead not explained by loaded models or safety models */
const systemOverheadGb = computed(() =>
  Math.max(0, baselineGb.value - loadedModelsVramGb.value - safetyModelsVramGb.value)
)

/** Selected models that are NOT already on the GPU */
const unloadedSelectedModels = computed(() =>
  selectedModels.value.filter(m => m.local && !isAlreadyLoaded(m.id))
)

const usedGb = computed(() => {
  const additionalVram = unloadedSelectedModels.value
    .reduce((sum, m) => sum + m.vram_gb, 0)
  return baselineGb.value + additionalVram
})

const freePercent = computed(() => {
  if (totalGb.value === 0) return 100
  const used = usedGb.value / totalGb.value * 100
  return Math.max(0, 100 - used)
})

const overBudget = computed(() => usedGb.value > totalGb.value)

function isSelected(id: string) {
  return selectedModels.value.some(m => m.id === id)
}

function segmentWidth(gb: number) {
  if (totalGb.value === 0 || gb === 0) return 3
  return Math.max(3, (gb / totalGb.value) * 100)
}

function mediaLabel(type: string): string {
  const keyMap: Record<string, string> = {
    image: 'workshop.models.image',
    video: 'workshop.models.video',
    music: 'workshop.models.music',
    sound: 'workshop.models.sound',
    '3d': 'workshop.models.threeD',
  }
  return keyMap[type] ? t(keyMap[type]) : type
}

// --- Drag & Drop ---
const isDragOver = ref(false)
let draggedModelId: string | null = null
let dragFromMemory = false

function onDragStart(e: DragEvent, model: PhysicalModel) {
  draggedModelId = model.id
  dragFromMemory = false
  e.dataTransfer!.effectAllowed = 'move'
}

function onDragStartFromMemory(e: DragEvent, model: PhysicalModel) {
  draggedModelId = model.id
  dragFromMemory = true
  e.dataTransfer!.effectAllowed = 'move'
}

function onDragOver(e: DragEvent) {
  isDragOver.value = true
  e.dataTransfer!.dropEffect = 'move'
}

function onDragLeave() {
  isDragOver.value = false
}

function onDrop() {
  isDragOver.value = false
  if (!draggedModelId || dragFromMemory) return
  addModel(draggedModelId)
  draggedModelId = null
}

function addModel(id: string) {
  if (isSelected(id)) return
  const model = physicalModels.find(m => m.id === id)
  if (!model) return
  selectedModels.value.push(model)

  if (!model.local) {
    const region = model.cloud_region === 'EU' ? t('workshop.chat.regionEu') : t('workshop.chat.regionUs')
    addChatMessage('assistant',
      t('workshop.chat.cloudAdded', { name: model.name, publisher: model.publisher, region })
    )
  } else if (overBudget.value) {
    addChatMessage('assistant',
      t('workshop.chat.overBudget', { name: model.name, gb: model.vram_gb })
    )
  } else {
    const freeGb = totalGb.value - usedGb.value
    addChatMessage('assistant',
      t('workshop.chat.freeSpace', { name: model.name, gb: model.vram_gb, free: freeGb })
    )
  }
}

function removeModel(id: string) {
  const idx = selectedModels.value.findIndex(m => m.id === id)
  if (idx >= 0) selectedModels.value.splice(idx, 1)
}

function toggleModel(model: PhysicalModel) {
  if (isSelected(model.id)) {
    removeModel(model.id)
  } else {
    addModel(model.id)
  }
}

// --- Chat ---
interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const isLoading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
let nextId = 0

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

function addChatMessage(role: 'user' | 'assistant', content: string) {
  messages.value.push({ id: nextId++, role, content })
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return

  addChatMessage('user', text)
  userInput.value = ''
  isLoading.value = true

  try {
    const history = messages.value.map(m => ({ role: m.role, content: m.content }))
    const res = await fetch(`${getBaseUrl()}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: history.slice(0, -1),
        context: { workshop_planning: true },
        draft_context: buildDraftContext(),
        language: locale.value,
      })
    })
    const data = await res.json()
    if (data.reply) {
      addChatMessage('assistant', data.reply)
    }
  } catch {
    addChatMessage('assistant', t('workshop.chat.connectionError'))
  } finally {
    isLoading.value = false
  }
}

function buildDraftContext(): string {
  const parts: string[] = []
  if (status.value) {
    parts.push(`Grafikkarte: ${status.value.gpuName}, ${totalGb.value} GB Speicher`)
    parts.push(`Sicherheitssysteme: ${SAFETY_VRAM_GB} GB (immer geladen)`)
    parts.push(`Ausgewählte Modelle: ${selectedModels.value.map(m => `${m.name} (${m.vram_gb} GB)`).join(', ') || 'keine'}`)
    parts.push(`Belegt: ${usedGb.value} GB, Frei: ${totalGb.value - usedGb.value} GB`)
    if (overBudget.value) parts.push('ACHTUNG: Auswahl übersteigt den verfügbaren Speicher!')
  }
  return parts.join('\n')
}


// --- Preloading & Unloading ---
const isPreloading = ref(false)

/** Selected models that can actually be preloaded */
const preloadableSelected = computed(() =>
  selectedModels.value.filter(m => m.preloadable && !isAlreadyLoaded(m.id))
)

async function preloadModels() {
  const models = preloadableSelected.value
  if (models.length === 0 || isPreloading.value) return

  isPreloading.value = true
  addChatMessage('assistant', t('workshop.chat.preloadStart', { count: models.length }))

  try {
    const ids = models.map(m => m.id)
    const res = await fetch(`${getBaseUrl()}/api/settings/workshop/preload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ models: ids }),
    })

    if (!res.ok || !res.headers.get('content-type')?.includes('text/event-stream')) {
      // Fallback: non-SSE response (old endpoint format)
      const data = await res.json()
      const loaded: string[] = []
      const skipped: string[] = []
      const errors: string[] = []
      for (const [mid, result] of Object.entries(data.results || {})) {
        const r = result as { success: boolean; skipped?: boolean; error?: string }
        const name = models.find(m => m.id === mid)?.name || mid
        if (r.skipped) skipped.push(name)
        else if (r.success) loaded.push(name)
        else errors.push(`${name}: ${r.error}`)
      }
      if (loaded.length) addChatMessage('assistant', t('workshop.confirm.resultLoaded', { models: loaded.join(', ') }))
      if (skipped.length) addChatMessage('assistant', t('workshop.confirm.resultSkipped', { models: skipped.join(', ') }))
      if (errors.length) addChatMessage('assistant', t('workshop.confirm.resultError', { details: errors.join('; ') }))
      await refresh()
      isPreloading.value = false
      return
    }

    // SSE streaming response
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      let eventType = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ') && eventType) {
          try {
            const data = JSON.parse(line.slice(6))
            if (eventType === 'model_start') {
              addChatMessage('assistant', t('workshop.chat.preloadModel', { name: data.name || data.model_id }))
            } else if (eventType === 'model_complete') {
              addChatMessage('assistant', t('workshop.chat.preloadDone', { name: data.name || data.model_id }))
              await refresh()
            } else if (eventType === 'model_error') {
              addChatMessage('assistant', t('workshop.confirm.resultError', { details: `${data.name || data.model_id}: ${data.error}` }))
            } else if (eventType === 'done') {
              addChatMessage('assistant', t('workshop.confirm.ready'))
            }
          } catch { /* skip malformed */ }
          eventType = ''
        }
      }
    }
    await refresh()
  } catch {
    addChatMessage('assistant', t('workshop.chat.connectionError'))
  } finally {
    isPreloading.value = false
  }
}

interface LoadedSegment {
  name: string
  gb: number
  backend?: string
  model?: string
}

function confirmUnload(lm: LoadedSegment) {
  // Determine if this is a ComfyUI model (heuristic: backend contains comfyui or model loaded via ComfyUI)
  const isComfyUI = (lm.backend || '').toLowerCase().includes('comfyui')

  const message = isComfyUI
    ? t('workshop.actions.confirmUnloadComfyui', { name: lm.name })
    : t('workshop.actions.confirmUnload', { name: lm.name })

  if (!window.confirm(message)) return
  unloadModel(lm)
}

async function unloadModel(lm: LoadedSegment) {
  addChatMessage('assistant', t('workshop.chat.unloading', { name: lm.name }))
  try {
    const res = await fetch(`${getBaseUrl()}/api/settings/workshop/unload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_name: lm.name,
        backend: lm.backend || '',
        model: lm.model || '',
      }),
    })
    const data = await res.json()
    if (data.success) {
      addChatMessage('assistant', t('workshop.chat.unloaded', { name: lm.name }))
    } else {
      addChatMessage('assistant', t('workshop.confirm.resultError', { details: data.error || 'unknown' }))
    }
    await refresh()
  } catch {
    addChatMessage('assistant', t('workshop.chat.connectionError'))
  }
}

function confirmClearAll() {
  if (!window.confirm(t('workshop.actions.confirmClearAll'))) return
  clearAllGpuMemory()
}

async function clearAllGpuMemory() {
  addChatMessage('assistant', t('workshop.chat.clearingAll'))
  try {
    const res = await fetch(`${getBaseUrl()}/api/settings/workshop/clear-all`, {
      method: 'POST',
    })
    const data = await res.json()
    if (data.success) {
      addChatMessage('assistant', t('workshop.chat.clearedAll'))
    } else {
      addChatMessage('assistant', t('workshop.confirm.resultError', { details: data.error || 'unknown' }))
    }
    await refresh()
  } catch {
    addChatMessage('assistant', t('workshop.chat.connectionError'))
  }
}

// --- Greeting (LLM-generated in user's language) ---
function buildGreetingTemplate(): string {
  const m = metaphors()
  const tgb = totalGb.value
  const memLine = tgb > 0 && m
    ? t('workshop.greeting.memoryMetaphor', { gb: tgb, books: m.booksCount.toLocaleString(), meters: m.booksMeters })
    : ''

  const parts = [
    t('workshop.greeting.intro'),
    t('workshop.greeting.resources') + memLine,
    t('workshop.greeting.limits'),
    t('workshop.greeting.planning'),
    t('workshop.greeting.flexibility'),
    t('workshop.greeting.callToAction'),
  ]
  return parts.join('\n\n')
}

const langLabel = computed(() => {
  const entry = SUPPORTED_LANGUAGES.find(l => l.code === locale.value)
  return entry?.label ?? 'Deutsch'
})

async function fetchGreeting() {
  const template = buildGreetingTemplate()
  addChatMessage('assistant', t('trashy.thinking'))
  const placeholderId = nextId - 1

  try {
    const res = await fetch(`${getBaseUrl()}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: `Greet the workshop participants in ${langLabel.value}. Help them plan which AI models to use. Your greeting should cover these points (adapt freely, do not translate literally):\n\n${template}`,
        history: [],
        context: { workshop_planning: true },
        draft_context: buildDraftContext(),
        language: locale.value,
      })
    })
    const data = await res.json()
    const msg = messages.value.find(m => m.id === placeholderId)
    if (msg) msg.content = data.reply || template
    else addChatMessage('assistant', data.reply || template)
  } catch {
    const msg = messages.value.find(m => m.id === placeholderId)
    if (msg) msg.content = template
    else addChatMessage('assistant', template)
  }
}

onMounted(() => {
  fetchGreeting()
})
</script>

<style scoped>
.workshop-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 1.5rem 1rem 6rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  min-height: 100vh;
}

.page-title {
  font-size: 1.3rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
}

/* --- Trashy Chat --- */
.trashy-section {
  display: flex;
  flex-direction: column;
  background: rgba(15, 15, 15, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.trashy-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
}

.chat-title {
  font-size: 1rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.chat-messages {
  overflow-y: visible;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.chat-bubble {
  max-width: 90%;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  font-size: 0.95rem;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-line;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
  border-bottom-left-radius: 4px;
}

.chat-bubble.user {
  align-self: flex-end;
  background: rgba(76, 175, 80, 0.15);
  color: rgba(255, 255, 255, 0.9);
  border-bottom-right-radius: 4px;
}

.chat-bubble.loading {
  padding: 0.75rem 1rem;
}

.typing-dots span {
  animation: typing 1.2s infinite;
  font-size: 1.2rem;
  color: rgba(255, 255, 255, 0.4);
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

.chat-input-area {
  padding: 0.75rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.chat-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.95rem;
  outline: none;
}

.chat-input:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

/* --- Memory Visualization --- */
.memory-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.memory-label {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.memory-container {
  display: flex;
  align-items: stretch;
  min-height: 52px;
  background: rgba(255, 255, 255, 0.03);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.2s ease;
}

.memory-container.drag-over {
  border-color: rgba(76, 175, 80, 0.5);
  background: rgba(76, 175, 80, 0.05);
}

.memory-segment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.6rem;
  min-width: 0;
  transition: width 0.3s ease;
}

.memory-segment.loaded {
  background: rgba(100, 180, 255, 0.12);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.memory-segment.safety {
  background: rgba(255, 170, 60, 0.12);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.memory-segment.system-overhead {
  background: rgba(255, 255, 255, 0.06);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.memory-segment.model {
  background: rgba(76, 175, 80, 0.15);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  cursor: grab;
}

.memory-segment.model:hover {
  background: rgba(76, 175, 80, 0.25);
}

.memory-segment.free {
  justify-content: center;
}

.segment-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.7);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.segment-remove {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.3);
  font-size: 1rem;
  cursor: pointer;
  padding: 0 0.2rem;
  flex-shrink: 0;
}

.segment-remove:hover {
  color: rgba(255, 100, 100, 0.8);
}

.free-label {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.2);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.memory-stats {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.4);
  text-align: center;
}

.over-budget {
  color: rgba(255, 80, 80, 0.9);
  font-weight: 600;
}

/* --- Memory Actions --- */
.memory-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
}

.action-btn {
  padding: 0.5rem 1.2rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.25);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.load-btn {
  border-color: rgba(76, 175, 80, 0.4);
  color: rgba(76, 175, 80, 0.9);
}

.load-btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.1);
  border-color: rgba(76, 175, 80, 0.6);
}

.clear-btn {
  border-color: rgba(255, 100, 100, 0.3);
  color: rgba(255, 100, 100, 0.7);
}

.clear-btn:hover:not(:disabled) {
  background: rgba(255, 100, 100, 0.08);
  border-color: rgba(255, 100, 100, 0.5);
}

.card-note {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
  font-style: italic;
}

/* --- Model Cards --- */
.models-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.models-label {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
}

.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}

.model-card {
  padding: 0.9rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.model-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.06);
}

.model-card.is-selected {
  border-color: rgba(76, 175, 80, 0.5);
  background: rgba(76, 175, 80, 0.08);
}

.model-card.is-loaded {
  border-color: rgba(100, 180, 255, 0.3);
}

.model-card.is-cloud {
  border-style: dashed;
}

.loaded-badge {
  color: rgba(100, 180, 255, 0.7);
}

.card-header {
  display: flex;
  align-items: center;
}

.card-media-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.85);
}

.card-media-badge.image { background: rgba(255, 107, 107, 0.3); }
.card-media-badge.video { background: rgba(233, 30, 99, 0.3); }
.card-media-badge.music { background: rgba(156, 39, 176, 0.3); }
.card-media-badge.sound { background: rgba(255, 152, 0, 0.3); }
.card-media-badge.\33d { background: rgba(0, 188, 212, 0.3); }

.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.card-facts {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.card-fact {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.4;
}

.cloud-fact {
  color: rgba(255, 179, 0, 0.7);
}

.card-publisher {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.3);
  margin-top: auto;
}

/* --- Planning Summary --- */
.planning-summary {
  text-align: center;
  padding: 0.5rem 0;
}

.over-budget-notice {
  color: rgba(255, 80, 80, 0.9);
  font-weight: 600;
  font-size: 0.95rem;
  padding: 0.75rem;
  border: 1px solid rgba(255, 80, 80, 0.3);
  border-radius: 10px;
  background: rgba(255, 80, 80, 0.08);
}
</style>
