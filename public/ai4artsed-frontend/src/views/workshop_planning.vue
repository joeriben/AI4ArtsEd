<template>
  <div class="workshop-page">
    <!-- Trashy Chat (central, dominant) -->
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
            @keydown.enter="sendMessage"
          :disabled="isLoading"
        />
      </div>
    </div>

    <!-- Loading indicator -->
    <div v-if="loadingModelId" class="loading-indicator">
      Modell wird in den Speicher geladen...
    </div>

    <!-- Memory Visualization (drop zone) -->
    <div class="memory-section">
      <div class="memory-label">Speicher der Grafikkarte</div>
      <div
        class="memory-container"
        @dragover.prevent="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
        :class="{ 'drag-over': isDragOver }"
      >
        <!-- Baseline: safety systems, Ollama etc. -->
        <div
          v-if="baselineUsedMb > 0"
          class="memory-baseline"
          :style="{ width: cardWidth(baselineUsedMb) + '%' }"
        >
          <span class="card-name">Sicherheitssysteme</span>
        </div>
        <!-- Workshop models -->
        <div
          v-for="card in activeModels"
          :key="card.id"
          class="memory-card"
          :style="{ width: cardWidth(card.vram_mb) + '%' }"
          draggable="true"
          @dragstart="onDragStartFromMemory($event, card)"
        >
          <span class="card-name">{{ card.name }} ({{ Math.round(card.vram_mb / 1024) }} GB)</span>
          <button class="card-remove" @click="removeModel(card.id)" title="Entfernen">&times;</button>
        </div>
        <div class="memory-free" :style="{ width: freePercent + '%' }">
          <span v-if="freePercent > 15" class="free-label">frei</span>
        </div>
      </div>
      <div class="memory-stats">
        {{ Math.round((baselineUsedMb + usedMb) / 1024) }} / {{ totalGb }} Gigabyte belegt
        <span v-if="baselineUsedMb > 0" class="baseline-note">(davon {{ Math.round(baselineUsedMb / 1024) }} GB fuer Sicherheitssysteme)</span>
      </div>
    </div>

    <!-- Available Model Cards -->
    <div class="models-section">
      <div class="models-label">Verfuegbare Modelle — zum Aktivieren in den Speicher ziehen</div>
      <div class="models-grid">
        <div
          v-for="model in availableModels"
          :key="model.id"
          class="model-card"
          :class="{
            'is-active': isActive(model.id),
            'is-loading': isModelLoading(model.id),
            'is-cloud': !model.local,
          }"
          :style="{ minHeight: cardHeight(model.vram_mb) + 'px' }"
          draggable="true"
          @dragstart="onDragStart($event, model)"
          @click="toggleModel(model)"
        >
          <div class="card-title">{{ model.name }}</div>
          <div class="card-desc">{{ model.description }}</div>
          <div v-if="!model.local" class="card-cloud-badge">Cloud (DSGVO-konform)</div>
        </div>
      </div>
    </div>

    <!-- Confirm Button -->
    <div v-if="activeModels.length > 0" class="confirm-section">
      <button class="confirm-btn" @click="confirmSelection">
        Einigung sichern
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useGpuStatus, type ModelCost } from '@/composables/useGpuStatus'
import trashyIcon from '@/assets/trashy-icon.png'

const { status, metaphors, refresh } = useGpuStatus()

// Baseline: VRAM already used before workshop models (safety systems, Ollama, etc.)
const baselineUsedMb = ref(0)

// --- Chat State ---
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

// --- Active Models (in memory, with measured VRAM) ---
interface ActiveModel {
  id: string
  name: string
  vram_mb: number  // measured after real loading
  local: boolean
}

const activeModels = ref<ActiveModel[]>([])
const loadingModelId = ref<string | null>(null)

const availableModels = computed(() => {
  if (!status.value) return []
  // Show image generation models for the prototype
  return status.value.modelCosts.filter(m =>
    m.media_type === 'image' || m.media_type === 'music' || m.media_type === 'video' || m.media_type === 'audio'
  )
})

const totalGb = computed(() => {
  if (!status.value) return 0
  return Math.round(status.value.totalMb / 1024)
})

const usedMb = computed(() => {
  return activeModels.value.reduce((sum, m) => sum + m.vram_mb, 0)
})

const usedGb = computed(() => Math.round(usedMb.value / 1024))

const freePercent = computed(() => {
  if (!status.value || status.value.totalMb === 0) return 100
  return Math.max(0, 100 - (usedMb.value / status.value.totalMb) * 100)
})

function isActive(id: string) {
  return activeModels.value.some(m => m.id === id)
}

function isModelLoading(id: string) {
  return loadingModelId.value === id
}

function cardWidth(vramMb: number) {
  if (!status.value || status.value.totalMb === 0 || vramMb === 0) return 5
  return Math.max(5, (vramMb / status.value.totalMb) * 100)
}

function cardHeight(vramMb: number) {
  if (vramMb === 0) return 80 // Cloud models — small
  // Proportional: 28GB → 140px, 8GB → 80px, 24GB → 120px
  return Math.max(70, Math.min(160, 50 + vramMb / 300))
}

// --- Drag & Drop ---
const isDragOver = ref(false)
let draggedModelId: string | null = null
let dragFromMemory = false

function onDragStart(e: DragEvent, model: ModelCost) {
  draggedModelId = model.id
  dragFromMemory = false
  e.dataTransfer!.effectAllowed = 'move'
}

function onDragStartFromMemory(e: DragEvent, model: ActiveModel) {
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

function onDrop(e: DragEvent) {
  isDragOver.value = false
  if (!draggedModelId || dragFromMemory) return
  addModel(draggedModelId)
  draggedModelId = null
}

async function addModel(id: string) {
  if (isActive(id) || loadingModelId.value) return
  const model = status.value?.modelCosts.find(m => m.id === id)
  if (!model) return

  // Cloud models: no loading needed
  if (!model.local) {
    activeModels.value.push({ id, name: model.name, vram_mb: 0, local: false })
    addChatMessage('assistant',
      `${model.name} ist ein Cloud-Modell. Es braucht keinen Platz auf der Grafikkarte, aber eure Texte werden an einen geschuetzten Server in Europa geschickt. Jedes Bild kostet Geld aus dem Projektbudget.`
    )
    return
  }

  // Local model: trigger REAL loading on GPU
  loadingModelId.value = id
  addChatMessage('assistant',
    `${model.name} wird jetzt in den Speicher der Grafikkarte geladen. Das dauert einen Moment...`
  )

  try {
    // Trigger real model load via GPU service (proxied through DevServer)
    const loadRes = await fetch(`${getBaseUrl()}/api/settings/gpu-preload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: id }),
    })

    if (!loadRes.ok) {
      const err = await loadRes.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${loadRes.status}`)
    }

    // Model loaded — now query real VRAM usage
    await refresh()
    const vramAfter = status.value ? status.value.totalMb - status.value.freeMb : 0
    const vramBefore = usedMb.value
    const measuredVram = Math.max(0, vramAfter - vramBefore)

    activeModels.value.push({ id, name: model.name, vram_mb: measuredVram, local: true })

    const freeGb = status.value ? Math.round(status.value.freeMb / 1024) : 0
    addChatMessage('assistant',
      `${model.name} ist geladen und braucht ${Math.round(measuredVram / 1024)} Gigabyte. Noch ${freeGb} Gigabyte frei.`
    )
  } catch (e: any) {
    addChatMessage('assistant',
      `${model.name} konnte nicht geladen werden: ${e.message}. Fragt die Kursleitung.`
    )
  } finally {
    loadingModelId.value = null
  }
}

function removeModel(id: string) {
  const idx = activeModels.value.findIndex(m => m.id === id)
  if (idx >= 0) {
    activeModels.value.splice(idx, 1)
    // TODO: optionally trigger unload on GPU service
  }
}

function toggleModel(model: ModelCost) {
  if (isActive(model.id)) {
    removeModel(model.id)
  } else {
    addModel(model.id)
  }
}

// --- Chat ---
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
      })
    })
    const data = await res.json()
    if (data.reply) {
      addChatMessage('assistant', data.reply)
    }
  } catch {
    addChatMessage('assistant', 'Verbindungsfehler — bitte nochmal versuchen.')
  } finally {
    isLoading.value = false
  }
}

function buildDraftContext(): string {
  const parts: string[] = []
  if (status.value) {
    parts.push(`GPU: ${status.value.gpuName}, ${totalGb.value} GB total, ${usedGb.value} GB belegt`)
    parts.push(`Aktive Modelle: ${activeModels.value.map(m => m.name).join(', ') || 'keine'}`)
    parts.push(`Freier Speicher: ${Math.round((status.value.totalMb - usedMb.value) / 1024)} GB`)
  }
  return parts.join('\n')
}

async function confirmSelection() {
  // TODO: POST to /api/workshop/session with settings password
  addChatMessage('assistant',
    `Einigung gesichert: ${activeModels.value.map(m => m.name).join(', ')}. Alle Geraete sehen jetzt diese Auswahl.`
  )
}

// --- Greeting ---
function buildGreeting(): string {
  const m = metaphors()
  const tgb = totalGb.value
  // GPU-specific numbers — empty string if not yet available
  const memLine = tgb > 0 && m
    ? ` Wir haben hier ${tgb} Gigabyte Grafikkartenspeicher zur Verfuegung. Das ist soviel wie ${m.booksCount.toLocaleString()} Buecher — wenn man die aneinanderreiht gibt das eine Buecherschlange von ${m.booksMeters} Metern.`
    : ''

  return `Hallo, ich bin Trashy, das Hilfe-System fuer diese Plattform. Wenn Ihr einen gemeinsamen Workshop oder eine Unterrichtseinheit mit vielen Endgeraeten durchfuehren wollt, dann ist es sinnvoll vorher zu ueberlegen worum es gehen soll.

Mit Kuenstlicher Intelligenz zu arbeiten braucht erstaunlich viele Ressourcen. Es braucht vor allem eine Grafikkarte mit moeglichst viel Speicher.${memLine}

Aber die KI-Modelle die Ihr verwendet sind so riesig, dass selbst dieser grosse Speicher schnell an Grenzen stoesst.

Daher solltet ihr planen und gemeinsam abstimmen was ihr vorhabt, und mit welchen Modellen. Denn wenn der Speicher voll ist und jemand von Euch ein weiteres neues Modell aktiviert, entstehen lange Wartezeiten und manchmal ein Stau. Es dauert zwischen 30 Sekunden und 2 Minuten, nur um ein Modell in den Speicher zu laden. Ist es einmal im Speicher, dann geht alles meistens ganz schnell.

Natuerlich ist es kein Problem wenn Ihr mehr oder andere Modelle verwendet — das kann ich verwalten. Aber dann dauert alles etwas laenger. Und: Es ist immer gut sich vorher zu ueberlegen was man mit welchen Mitteln erreichen will. Wenn Ihr kuenstlerisch arbeiten wollt, geht Ihr schliesslich auch nicht einfach auf die Strasse und greift den ersten Gegenstand auf, um damit etwas zu tun.

Also denkt mal gemeinsam nach. Zieht die Modellkarten unten in den Speicher und schaut, welche Modelle Ihr gut miteinander kombinieren koennt. ODER sagt mir was Ihr gerne tun moechtet, und ich schlage Euch geeignete Modelle vor.`
}

onMounted(() => {
  addChatMessage('assistant', buildGreeting())
  // Capture baseline VRAM usage (safety models, Ollama, etc.)
  const captureBaseline = setInterval(() => {
    if (status.value && status.value.totalMb > 0) {
      clearInterval(captureBaseline)
      baselineUsedMb.value = status.value.totalMb - status.value.freeMb
    }
  }, 500)
  setTimeout(() => clearInterval(captureBaseline), 10000)
})
</script>

<style scoped>
.workshop-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  min-height: 100vh;
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
  flex: 1;
  overflow-y: auto;
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

.chat-input::placeholder {
  color: rgba(255, 255, 255, 0.25);
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
  min-height: 60px;
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

.memory-baseline {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.06);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  min-width: 0;
}

.memory-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  background: rgba(76, 175, 80, 0.15);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  cursor: grab;
  transition: background 0.15s ease;
  min-width: 0;
}

.memory-card:hover {
  background: rgba(76, 175, 80, 0.25);
}

.card-name {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-remove {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0 0.25rem;
  flex-shrink: 0;
}

.card-remove:hover {
  color: rgba(255, 100, 100, 0.8);
}

.memory-free {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  transition: width 0.3s ease;
}

.free-label {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.2);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.memory-stats {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.4);
  text-align: center;
}

.loading-indicator {
  text-align: center;
  color: rgba(255, 179, 0, 0.8);
  font-size: 0.9rem;
  animation: pulse-loading 1.5s ease-in-out infinite;
}

.baseline-note {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.7rem;
}

/* --- Model Cards Grid --- */
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
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.model-card {
  flex: 1 1 200px;
  max-width: 250px;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  cursor: grab;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.model-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.06);
}

.model-card.is-active {
  border-color: rgba(76, 175, 80, 0.5);
  background: rgba(76, 175, 80, 0.08);
  opacity: 0.5;
  cursor: default;
  pointer-events: none;
}

.model-card.is-loading {
  border-color: rgba(255, 179, 0, 0.5);
  background: rgba(255, 179, 0, 0.08);
  animation: pulse-loading 1.5s ease-in-out infinite;
  pointer-events: none;
}

@keyframes pulse-loading {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}

.model-card.is-cloud {
  border-style: dashed;
}

.card-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.card-desc {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.4;
}

.card-cloud-badge {
  font-size: 0.7rem;
  color: rgba(100, 180, 255, 0.7);
  margin-top: auto;
}

/* --- Confirm --- */
.confirm-section {
  display: flex;
  justify-content: center;
  padding: 1rem 0;
}

.confirm-btn {
  background: rgba(76, 175, 80, 0.2);
  border: 1px solid rgba(76, 175, 80, 0.4);
  color: rgba(76, 175, 80, 0.9);
  padding: 0.75rem 2rem;
  border-radius: 10px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.confirm-btn:hover {
  background: rgba(76, 175, 80, 0.3);
  border-color: rgba(76, 175, 80, 0.6);
}
</style>
