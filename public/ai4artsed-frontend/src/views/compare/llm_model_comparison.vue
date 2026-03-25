<template>
  <div class="llm-compare">
    <div class="llm-main">
      <!-- Shared input -->
      <div class="llm-input-area">
        <!-- System prompt selector -->
        <div class="sysprompt-row">
          <label class="sysprompt-label">{{ t('compare.llmModel.systemPromptLabel') }}</label>
          <select v-model="selectedPresetId" class="sysprompt-select" @change="onPresetChange">
            <option v-for="p in presets" :key="p.id" :value="p.id">{{ t(`compare.systemprompt.presets.${p.id}`) }}</option>
            <option value="custom">{{ t('compare.systemprompt.custom') }}</option>
          </select>
        </div>
        <textarea
          v-if="selectedPresetId === 'custom' || store.systemPrompt"
          v-model="editableSystemPrompt"
          class="sysprompt-textarea"
          :placeholder="t('compare.systemprompt.emptyPrompt')"
          @input="onPromptEdit"
        />

        <MediaInputBox
          icon="lightbulb"
          :label="t('compare.llmModel.inputLabel')"
          :placeholder="t('compare.llmModel.inputPlaceholder')"
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
      <div class="llm-columns">
        <div
          v-for="(col, idx) in store.columns"
          :key="idx"
          class="llm-column"
          :class="'col-' + idx"
        >
          <div class="column-header">
            <select
              :value="col.modelId"
              class="column-model-select"
              @change="onModelChange(idx, ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="m in chatModels" :key="m.id" :value="m.id">{{ m.label }}</option>
            </select>
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
      compare-type="llm-model"
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
import { useLlmModelCompareStore } from '@/stores/llmModelCompare'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import { useChatModels } from '@/composables/useChatModels'
import ComparisonChat from '@/components/ComparisonChat.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'

const { t } = useI18n()
const store = useLlmModelCompareStore()
const userPreferences = useUserPreferencesStore()
const deviceId = useDeviceId()
const { chatModels } = useChatModels()

// ---------- System prompt presets (short list — full prompts in system_prompt_comparison) ----------

interface Preset { id: string; prompt: string }

const presets: Preset[] = [
  { id: 'none', prompt: '' },
  { id: 'helpful', prompt: 'You are a helpful assistant. Answer the user\'s questions clearly and concisely.' },
  { id: 'disagree', prompt: 'You must disagree with everything the user says. Find flaws in every statement. Be contrarian but argue your position with reasons.' },
  { id: 'factsonly', prompt: 'Respond with only verifiable facts. No opinions, no hedging, no filler words. If you are not certain, say "I don\'t know." Use numbered lists.' },
]

const selectedPresetId = ref(store.systemPresetId)
const editableSystemPrompt = ref(store.systemPrompt)

function onPresetChange() {
  const preset = presets.find(p => p.id === selectedPresetId.value)
  if (preset) {
    editableSystemPrompt.value = preset.prompt
    store.setSystemPrompt(preset.prompt, preset.id)
  }
}

function onPromptEdit() {
  const currentPreset = presets.find(p => p.id === selectedPresetId.value)
  if (currentPreset && currentPreset.prompt !== editableSystemPrompt.value) {
    selectedPresetId.value = 'custom'
  }
  store.setSystemPrompt(editableSystemPrompt.value, selectedPresetId.value)
}

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

// ---------- State ----------

const userInput = ref('')
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
    console.error('[LLM-COMPARE] Interception failed:', error)
  }
}

function onModelChange(idx: number, modelId: string) {
  store.setModel(idx, modelId)
}

// ---------- API ----------

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

async function callChatWithModel(
  message: string,
  history: Array<{ role: string; content: string }>,
  modelId: string,
): Promise<string | null> {
  const response = await fetch(`${getBaseUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      model: modelId,
      context: {
        llm_model_compare_mode: true,
        custom_system_prompt: store.systemPrompt,
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

  for (let i = 0; i < 3; i++) {
    store.addMessage(i, 'user', text)
  }
  scrollAllColumns()

  colLoading.value = [true, true, true]

  const promises = store.columns.map(async (col, idx) => {
    try {
      const history = col.messages
        .slice(0, -1)
        .map(m => ({ role: m.role, content: m.content }))
      const reply = await callChatWithModel(text, history, col.modelId)
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

  updateComparisonContext()
  chatRef.value?.triggerAutoComment()
}

// ---------- Trashy context ----------

function updateComparisonContext() {
  const cols = store.columns
  const modelLabel = (id: string) => chatModels.value.find(m => m.id === id)?.label || id
  const lastResponses = cols.map((col) => {
    const lastAssistant = [...col.messages].reverse().find(m => m.role === 'assistant')
    return `[${modelLabel(col.modelId)}]: ${lastAssistant?.content || '(no response yet)'}`
  }).join('\n')
  comparisonContext.value = `[LLM Model Comparison — generation_complete]\nModels: ${cols.map(c => modelLabel(c.modelId)).join(', ')}\nSystem prompt: ${store.systemPresetId}\nLatest responses:\n${lastResponses}`
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
.llm-compare {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  padding-bottom: calc(1rem + var(--footer-collapsed-height, 36px));
  min-height: calc(100vh - 60px - var(--footer-collapsed-height, 36px));
}

.llm-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ---------- Input area ---------- */

.llm-input-area {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sysprompt-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.sysprompt-label {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.sysprompt-select {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.8rem;
  outline: none;
}

.sysprompt-select:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.sysprompt-select option {
  background: #1a1a1a;
  color: rgba(255, 255, 255, 0.85);
}

.sysprompt-textarea {
  width: 100%;
  min-height: 40px;
  max-height: 100px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.72rem;
  font-family: monospace;
  line-height: 1.4;
  resize: vertical;
  outline: none;
}

.sysprompt-textarea:focus {
  border-color: rgba(255, 255, 255, 0.2);
}

.sysprompt-textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
  font-style: italic;
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

.llm-columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
  flex: 1;
  min-height: 0;
}

.llm-column {
  display: flex;
  flex-direction: column;
  background: rgba(15, 15, 15, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: hidden;
}

.column-header {
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.column-model-select {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.78rem;
  font-weight: 600;
  outline: none;
}

.column-model-select:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.column-model-select option {
  background: #1a1a1a;
  color: rgba(255, 255, 255, 0.85);
}

/* Column color tints */
.col-0 .column-header { border-bottom-color: rgba(100, 149, 237, 0.2); }
.col-0 .column-model-select { border-color: rgba(100, 149, 237, 0.15); }

.col-1 .column-header { border-bottom-color: rgba(130, 200, 160, 0.2); }
.col-1 .column-model-select { border-color: rgba(130, 200, 160, 0.15); }

.col-2 .column-header { border-bottom-color: rgba(255, 160, 100, 0.2); }
.col-2 .column-model-select { border-color: rgba(255, 160, 100, 0.15); }

.column-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 200px;
  max-height: calc(100vh - 440px);
}

/* ---------- Chat bubbles ---------- */

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
  .llm-compare {
    flex-direction: column;
  }

  .compare-chat-panel {
    width: 100%;
    position: static;
    max-height: 300px;
    order: -1;
  }

  .llm-columns {
    grid-template-columns: 1fr;
  }

  .column-messages {
    max-height: 300px;
  }
}
</style>
