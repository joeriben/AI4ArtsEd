<template>
  <div class="temp-compare">
    <div class="temp-main">
      <!-- Shared input -->
      <div class="temp-input-area">
        <div class="input-row">
          <input
            v-model="userInput"
            class="temp-input"
            :placeholder="t('compare.temperature.inputPlaceholder')"
            @keydown.enter="sendToAll"
            :disabled="isSending"
          />
          <button
            class="send-btn"
            :disabled="!canSend"
            @click="sendToAll"
          >
            {{ isSending ? t('compare.temperature.sending') : t('compare.temperature.sendAll') }}
          </button>
        </div>
        <button
          v-if="store.hasConversation"
          class="clear-btn"
          @click="startNewConversation"
        >
          {{ t('compare.temperature.newConversation') }}
        </button>
      </div>

      <!-- 3 columns -->
      <div class="temp-columns">
        <div
          v-for="(col, idx) in store.columns"
          :key="idx"
          class="temp-column"
          :class="columnClass(idx)"
        >
          <div class="column-header">
            <span class="temp-label">T={{ col.temperature }}</span>
            <span class="temp-desc">{{ columnDesc(idx) }}</span>
          </div>
          <div class="column-messages" :ref="el => setColRef(idx, el)">
            <div
              v-for="msg in col.messages"
              :key="msg.id"
              class="chat-bubble"
              :class="msg.role"
            >
              {{ msg.content }}
            </div>
            <div v-if="colLoading[idx]" class="chat-bubble assistant loading">
              <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Trashy sidebar -->
    <div class="trashy-panel">
      <div class="trashy-header">
        <img :src="trashyIcon" alt="" class="trashy-icon" />
        <span class="trashy-title">Trashy</span>
      </div>
      <div class="trashy-messages" ref="trashyMessagesRef">
        <div
          v-for="msg in trashyMessages"
          :key="msg.id"
          class="chat-bubble"
          :class="msg.role"
        >
          <template v-if="msg.role === 'assistant'">
            <span v-for="(part, pidx) in parseSuggestions(msg.content)" :key="pidx">
              <span v-if="part.type === 'text'">{{ part.text }}</span>
              <button v-else class="prompt-suggestion" @click="userInput = part.text">{{ part.text }}</button>
            </span>
          </template>
          <template v-else>{{ msg.content }}</template>
        </div>
        <div v-if="trashyLoading" class="chat-bubble assistant loading">
          <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
        </div>
      </div>
      <div class="trashy-input-area">
        <input
          v-model="trashyInput"
          class="trashy-input"
          :placeholder="t('compare.chatPlaceholder')"
          @keydown.enter="sendToTrashy"
          :disabled="trashyLoading"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTemperatureCompareStore } from '@/stores/temperatureCompare'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import trashyIcon from '@/assets/trashy-icon.png'

const { t } = useI18n()
const store = useTemperatureCompareStore()
const userPreferences = useUserPreferencesStore()
const deviceId = useDeviceId()

// ---------- Column refs ----------

const colRefs: (HTMLElement | null)[] = [null, null, null]

function setColRef(idx: number, el: unknown) {
  colRefs[idx] = el as HTMLElement | null
}

function scrollColumn(idx: number) {
  nextTick(() => {
    const el = colRefs[idx]
    if (el) el.scrollTop = el.scrollHeight
  })
}

function scrollAllColumns() {
  for (let i = 0; i < 3; i++) scrollColumn(i)
}

// ---------- Column state ----------

const userInput = ref('')
const isSending = ref(false)
const colLoading = ref([false, false, false])

const canSend = computed(() => userInput.value.trim().length > 0 && !isSending.value)

const COL_CLASSES = ['col-cold', 'col-warm', 'col-hot'] as const
const COL_KEYS = ['compare.temperature.cold', 'compare.temperature.warm', 'compare.temperature.hot'] as const

function columnClass(idx: number): string {
  return COL_CLASSES[idx] ?? 'col-warm'
}

function columnDesc(idx: number): string {
  return t(COL_KEYS[idx] ?? COL_KEYS[1])
}

// ---------- API ----------

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

async function callChatWithTemp(
  message: string,
  history: Array<{ role: string; content: string }>,
  temperature: number
): Promise<string | null> {
  const response = await fetch(`${getBaseUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      temperature,
      context: {
        temperature_compare_mode: true,
        language: userPreferences.language,
        device_id: deviceId,
      },
    })
  })
  const data = await response.json()
  return data.reply || null
}

// ---------- Send to all 3 columns ----------

async function sendToAll() {
  const text = userInput.value.trim()
  if (!text || isSending.value) return

  userInput.value = ''
  isSending.value = true

  // Add user message to all columns
  for (let i = 0; i < 3; i++) {
    store.addMessage(i, 'user', text)
  }
  scrollAllColumns()

  // Fire 3 parallel requests
  colLoading.value = [true, true, true]

  const promises = store.columns.map(async (col, idx) => {
    try {
      const history = col.messages
        .slice(0, -1) // exclude the just-added user message
        .map(m => ({ role: m.role, content: m.content }))
      const reply = await callChatWithTemp(text, history, col.temperature)
      store.addMessage(idx, 'assistant', reply || t('compare.temperature.noResponse'))
    } catch {
      store.addMessage(idx, 'assistant', t('compare.temperature.error'))
    } finally {
      colLoading.value[idx] = false
      scrollColumn(idx)
    }
  })

  await Promise.allSettled(promises)
  isSending.value = false

  // Trigger Trashy auto-analysis
  autoAnalyze()
}

// ---------- Trashy sidebar ----------

interface TrashyMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

const trashyMessages = ref<TrashyMessage[]>([])
const trashyInput = ref('')
const trashyLoading = ref(false)
const trashyMessagesRef = ref<HTMLElement | null>(null)
let trashyNextId = 0

function addTrashyMessage(role: 'user' | 'assistant', content: string) {
  trashyMessages.value.push({ id: trashyNextId++, role, content })
  nextTick(() => {
    if (trashyMessagesRef.value) {
      trashyMessagesRef.value.scrollTop = trashyMessagesRef.value.scrollHeight
    }
  })
}

function parseSuggestions(content: string): Array<{ type: 'text' | 'prompt'; text: string }> {
  const parts: Array<{ type: 'text' | 'prompt'; text: string }> = []
  const regex = /\[PROMPT:\s*(.+?)\]/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', text: content.slice(lastIndex, match.index) })
    }
    parts.push({ type: 'prompt', text: match[1]! })
    lastIndex = regex.lastIndex
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', text: content.slice(lastIndex) })
  }
  return parts.length > 0 ? parts : [{ type: 'text', text: content }]
}

function buildTrashyContext(): string {
  const cols = store.columns
  const lastResponses = cols.map((col, i) => {
    const lastAssistant = [...col.messages].reverse().find(m => m.role === 'assistant')
    return `T=${col.temperature}: ${lastAssistant?.content || '(no response yet)'}`
  }).join('\n')

  return `[Temperature Comparison Mode]\nTemperatures: 0 (deterministic), 0.5 (balanced), 1.0 (creative)\nLatest responses:\n${lastResponses}`
}

async function callTrashy(message: string): Promise<string | null> {
  const history = trashyMessages.value.map(m => ({ role: m.role, content: m.content }))
  const response = await fetch(`${getBaseUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      context: {
        comparison_mode: true,
        language: userPreferences.language,
        device_id: deviceId,
      },
      draft_context: buildTrashyContext(),
    })
  })
  const data = await response.json()
  return data.reply || null
}

async function sendToTrashy() {
  const text = trashyInput.value.trim()
  if (!text || trashyLoading.value) return

  addTrashyMessage('user', text)
  trashyInput.value = ''
  trashyLoading.value = true

  try {
    const reply = await callTrashy(text)
    addTrashyMessage('assistant', reply || '[No response]')
  } catch {
    addTrashyMessage('assistant', '[Connection error]')
  } finally {
    trashyLoading.value = false
  }
}

async function autoAnalyze() {
  // Only auto-analyze if there's at least one complete round
  if (!store.hasConversation) return

  trashyLoading.value = true
  try {
    const reply = await callTrashy(
      'The user just sent the same message at three different temperatures (0, 0.5, 1.0). '
      + 'Compare the three responses concisely. Focus on concrete differences in content, style, and creativity. '
      + 'If the responses diverge interestingly, suggest ONE follow-up prompt that would amplify the divergence. '
      + 'Use [PROMPT: ...] format. Do not simulate excitement.'
    )
    if (reply) {
      addTrashyMessage('assistant', reply)
    }
  } catch {
    // Silent fail for auto-analysis
  } finally {
    trashyLoading.value = false
  }
}

async function fetchGreeting() {
  trashyLoading.value = true
  try {
    const langNames: Record<string, string> = {
      de: 'German', en: 'English', tr: 'Turkish', ko: 'Korean',
      uk: 'Ukrainian', fr: 'French', es: 'Spanish', he: 'Hebrew', ar: 'Arabic', bg: 'Bulgarian'
    }
    const lang = langNames[userPreferences.language] || 'English'
    const reply = await callTrashy(
      `Greet the user briefly. Explain that this mode sends the same message to an AI at three different "temperature" levels (0 = deterministic, 0.5 = balanced, 1.0 = creative). `
      + `Temperature controls randomness — low temperature always picks the most likely word, high temperature explores surprising alternatives. `
      + `Suggest ONE starting prompt where temperature differences are especially visible. Use [PROMPT: ...] format. Speak in ${lang}.`
    )
    if (reply) {
      addTrashyMessage('assistant', reply)
    } else {
      addTrashyMessage('assistant', t('compare.temperature.subtitle'))
    }
  } catch {
    addTrashyMessage('assistant', t('compare.temperature.subtitle'))
  } finally {
    trashyLoading.value = false
  }
}

function startNewConversation() {
  store.clearAll()
  trashyMessages.value = []
  trashyNextId = 0
  fetchGreeting()
}

// ---------- Init ----------

onMounted(() => {
  if (store.hasConversation) {
    scrollAllColumns()
  } else {
    fetchGreeting()
  }
})
</script>

<style scoped>
.temp-compare {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  min-height: calc(100vh - 60px);
}

.temp-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ---------- Input area ---------- */

.temp-input-area {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.input-row {
  display: flex;
  gap: 0.5rem;
}

.temp-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 0.7rem 1rem;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.15s ease;
}

.temp-input:focus {
  border-color: rgba(255, 255, 255, 0.25);
}

.temp-input::placeholder {
  color: rgba(255, 255, 255, 0.2);
}

.temp-input:disabled {
  opacity: 0.5;
}

.send-btn {
  padding: 0.7rem 1.5rem;
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  border-radius: 10px;
  color: rgba(76, 175, 80, 0.9);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  font-family: inherit;
}

.send-btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.25);
  border-color: rgba(76, 175, 80, 0.5);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.clear-btn {
  align-self: flex-start;
  padding: 0.35rem 0.75rem;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.clear-btn:hover {
  border-color: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.6);
}

/* ---------- 3 columns ---------- */

.temp-columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
  flex: 1;
  min-height: 0;
}

.temp-column {
  display: flex;
  flex-direction: column;
  background: rgba(15, 15, 15, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: hidden;
}

.column-header {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.temp-label {
  font-size: 0.8rem;
  font-weight: 700;
  font-family: monospace;
}

.temp-desc {
  font-size: 0.7rem;
  opacity: 0.5;
}

/* Column color tints */
.col-cold .column-header {
  border-bottom-color: rgba(100, 149, 237, 0.2);
}

.col-cold .temp-label {
  color: rgba(100, 149, 237, 0.9);
}

.col-warm .column-header {
  border-bottom-color: rgba(255, 255, 255, 0.1);
}

.col-warm .temp-label {
  color: rgba(255, 255, 255, 0.7);
}

.col-hot .column-header {
  border-bottom-color: rgba(255, 179, 0, 0.2);
}

.col-hot .temp-label {
  color: rgba(255, 179, 0, 0.9);
}

.column-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 200px;
  max-height: calc(100vh - 280px);
}

/* ---------- Chat bubbles (shared) ---------- */

.chat-bubble {
  max-width: 95%;
  padding: 0.5rem 0.7rem;
  border-radius: 10px;
  font-size: 0.8rem;
  line-height: 1.45;
  word-break: break-word;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
  border-bottom-left-radius: 3px;
}

.chat-bubble.user {
  align-self: flex-end;
  background: rgba(76, 175, 80, 0.12);
  color: rgba(255, 255, 255, 0.9);
  border-bottom-right-radius: 3px;
}

.chat-bubble.loading {
  padding: 0.5rem 0.8rem;
}

.typing-dots span {
  animation: typing 1.2s infinite;
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.4);
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

.prompt-suggestion {
  display: inline;
  background: rgba(255, 179, 0, 0.12);
  border: 1px solid rgba(255, 179, 0, 0.3);
  border-radius: 6px;
  padding: 0.1rem 0.35rem;
  color: rgba(255, 179, 0, 0.9);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.prompt-suggestion:hover {
  background: rgba(255, 179, 0, 0.22);
  border-color: rgba(255, 179, 0, 0.5);
}

/* ---------- Trashy sidebar ---------- */

.trashy-panel {
  width: 300px;
  flex-shrink: 0;
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  background: rgba(15, 15, 15, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
}

.trashy-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.trashy-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.trashy-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.trashy-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.trashy-input-area {
  padding: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.trashy-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.8rem;
  outline: none;
}

.trashy-input:focus {
  border-color: rgba(255, 255, 255, 0.25);
}

.trashy-input::placeholder {
  color: rgba(255, 255, 255, 0.2);
}

/* ---------- Responsive ---------- */

@media (max-width: 900px) {
  .temp-compare {
    flex-direction: column;
  }

  .trashy-panel {
    width: 100%;
    position: static;
    max-height: 300px;
    order: -1;
  }

  .temp-columns {
    grid-template-columns: 1fr;
  }

  .column-messages {
    max-height: 300px;
  }
}
</style>
