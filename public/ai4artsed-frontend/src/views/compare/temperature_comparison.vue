<template>
  <div class="temp-compare">
    <div class="temp-main">
      <!-- Shared input -->
      <div class="temp-input-area">
        <div class="model-select-row">
          <label class="model-label">{{ t('compare.shared.modelLabel') }}</label>
          <select v-model="selectedModel" class="model-select">
            <option
              v-for="m in chatModels"
              :key="m.id"
              :value="m.id"
              :disabled="!m.available"
            >{{ m.label }}{{ !m.available ? ` ${t('compare.shared.modelNotDownloaded')}` : '' }}</option>
          </select>
        </div>
        <MediaInputBox
          icon="lightbulb"
          :label="t('compare.temperature.inputLabel')"
          :placeholder="t('compare.temperature.inputPlaceholder')"
          :value="userInput"
          @update:value="userInput = $event"
          :rows="2"
          :disabled="isSending"
          :show-preset-button="true"
          @copy="copyPrompt"
          @paste="pastePrompt"
          @clear="clearPrompt"
          @open-preset-selector="showPresetOverlay = true"
        />
        <GenerationButton
          :disabled="!userInput.trim()"
          :executing="isSending"
          :label="t('compare.shared.sendAll')"
          :executing-label="t('compare.shared.sending')"
          @click="sendToAll"
        />
        <button
          v-if="store.hasConversation"
          class="clear-btn"
          @click="startNewConversation"
        >
          {{ t('compare.shared.newConversation') }}
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
    <ComparisonChat
      ref="chatRef"
      class="compare-chat-panel"
      :comparison-context="comparisonContext"
      compare-type="temperature"
      @use-prompt="userInput = $event"
    />

    <!-- Interception Preset Overlay -->
    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTemperatureCompareStore } from '@/stores/temperatureCompare'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import { useChatModels } from '@/composables/useChatModels'
import ComparisonChat from '@/components/ComparisonChat.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'

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
const selectedModel = ref('')
const isSending = ref(false)
const colLoading = ref([false, false, false])
const chatRef = ref<InstanceType<typeof ComparisonChat> | null>(null)
const comparisonContext = ref('')
const showPresetOverlay = ref(false)

// --- Clipboard ---
function copyPrompt() { window.navigator.clipboard.writeText(userInput.value) }
async function pastePrompt() { userInput.value = await window.navigator.clipboard.readText() }
function clearPrompt() { userInput.value = '' }

// --- Interception Preset ---
async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!userInput.value.trim()) return

  const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
  try {
    const res = await fetch(`${baseUrl}/api/schema/pipeline/stage2`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        schema: payload.configId,
        input_text: userInput.value,
        device_id: deviceId,
      })
    })
    if (res.ok) {
      const data = await res.json()
      const result = data.interception_result || data.stage2_result
      if (data.success && result) {
        userInput.value = typeof result === 'string' ? result : JSON.stringify(result)
      }
    }
  } catch (error) {
    console.error('[TEMP-COMPARE] Interception failed:', error)
  }
}

const { chatModels } = useChatModels()

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
      ...(selectedModel.value ? { model: selectedModel.value } : {}),
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
      store.addMessage(idx, 'assistant', reply || t('compare.shared.noResponse'))
    } catch {
      store.addMessage(idx, 'assistant', t('compare.shared.error'))
    } finally {
      colLoading.value[idx] = false
      scrollColumn(idx)
    }
  })

  await Promise.allSettled(promises)
  isSending.value = false

  // Trigger Trashy auto-analysis via ComparisonChat
  updateComparisonContext()
  chatRef.value?.triggerAutoComment()
}

// ---------- Trashy context ----------

function updateComparisonContext() {
  const cols = store.columns
  const lastResponses = cols.map((col) => {
    const lastAssistant = [...col.messages].reverse().find(m => m.role === 'assistant')
    return `T=${col.temperature}: ${lastAssistant?.content || '(no response yet)'}`
  }).join('\n')
  comparisonContext.value = `[Temperature Comparison Mode — generation_complete]\nTemperatures: 0 (deterministic), 0.5 (balanced), 1.0 (creative)\nLatest responses:\n${lastResponses}`
}

function startNewConversation() {
  store.clearAll()
  chatRef.value?.clearMessages()
}

// ---------- Init ----------

onMounted(() => {
  if (store.hasConversation) {
    scrollAllColumns()
  }
})
</script>

<style scoped>
.temp-compare {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  padding-bottom: calc(1rem + var(--footer-collapsed-height, 36px));
  min-height: calc(100vh - 60px - var(--footer-collapsed-height, 36px));
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

.model-select-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.model-label {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.model-select {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.8rem;
  outline: none;
}

.model-select:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.model-select option {
  background: #1a1a1a;
  color: rgba(255, 255, 255, 0.85);
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
  max-height: calc(100vh - 360px);
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

.compare-chat-panel {
  width: 300px;
  flex-shrink: 0;
  position: sticky;
  top: 80px;
  height: calc(100vh - 120px - var(--footer-collapsed-height, 36px));
  max-height: calc(100vh - 120px - var(--footer-collapsed-height, 36px));
}

/* ---------- Responsive ---------- */

@media (max-width: 900px) {
  .temp-compare {
    flex-direction: column;
  }

  .compare-chat-panel {
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
