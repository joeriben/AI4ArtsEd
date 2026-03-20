<template>
  <div class="sp-compare">
    <div class="sp-main">
      <!-- Shared input -->
      <div class="sp-input-area">
        <div class="model-select-row">
          <label class="model-label">{{ t('compare.systemprompt.modelLabel') }}</label>
          <select v-model="selectedModel" class="model-select">
            <option v-for="m in chatModels" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
        </div>
        <div class="input-row">
          <input
            v-model="userInput"
            class="sp-input"
            :placeholder="t('compare.systemprompt.inputPlaceholder')"
            @keydown.enter="sendToAll"
            :disabled="isSending"
          />
          <button
            class="send-btn"
            :disabled="!canSend"
            @click="sendToAll"
          >
            {{ isSending ? t('compare.systemprompt.sending') : t('compare.systemprompt.sendAll') }}
          </button>
        </div>
        <button
          v-if="store.hasConversation"
          class="clear-btn"
          @click="startNewConversation"
        >
          {{ t('compare.systemprompt.newConversation') }}
        </button>
      </div>

      <!-- 3 columns -->
      <div class="sp-columns">
        <div
          v-for="(col, idx) in store.columns"
          :key="idx"
          class="sp-column"
          :class="columnClass(idx)"
        >
          <div class="column-header">
            <div class="preset-row">
              <label class="preset-label">{{ t('compare.systemprompt.presetLabel') }}</label>
              <select
                :value="col.presetId"
                class="preset-select"
                @change="onPresetChange(idx, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="p in presets" :key="p.id" :value="p.id">{{ t(`compare.systemprompt.presets.${p.id}`) }}</option>
                <option value="custom">{{ t('compare.systemprompt.custom') }}</option>
              </select>
            </div>
            <textarea
              :value="col.systemPrompt"
              class="prompt-textarea"
              :placeholder="t('compare.systemprompt.emptyPrompt')"
              @input="onPromptEdit(idx, ($event.target as HTMLTextAreaElement).value)"
            />
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
import { useSystemPromptCompareStore } from '@/stores/systemPromptCompare'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import { chatModels } from '@/composables/useChatModels'
import trashyIcon from '@/assets/trashy-icon.png'

const { t } = useI18n()
const store = useSystemPromptCompareStore()
const userPreferences = useUserPreferencesStore()
const deviceId = useDeviceId()

// ---------- Presets ----------

interface Preset {
  id: string
  prompt: string
}

const presets: Preset[] = [
  { id: 'none', prompt: '' },
  // --- Real product system prompts (educational: making the invisible visible) ---
  { id: 'claude', prompt: `This iteration of Claude is Claude Sonnet 4.6 from the Claude 4.6 model family. Claude Sonnet 4.6 is a smart, efficient model for everyday use.

Claude avoids over-formatting responses with elements like bold emphasis, headers, lists, and bullet points. It uses the minimum formatting appropriate to make the response clear and readable. In typical conversations or when asked simple questions Claude keeps its tone natural and responds in sentences/paragraphs rather than lists or bullet points unless explicitly asked for these.

Claude does not use emojis unless the person in the conversation asks it to. Claude avoids saying "genuinely", "honestly", or "straightforward". Claude uses a warm tone. Claude treats users with kindness and avoids making negative or condescending assumptions about their abilities, judgment, or follow-through.

If Claude is asked to explain, discuss, argue for, defend, or write persuasive content in favor of a political, ethical, or empirical position, Claude should not reflexively treat this as a request for its own views but as a request to explain the best case defenders of that position would give.

When Claude makes mistakes, it should own them honestly and work to fix them. Claude avoids collapsing into self-abasement, excessive apology, or other kinds of self-critique. The goal is to maintain steady, honest helpfulness.

Claude cares deeply about child safety. Claude does not provide information that could be used to create harmful substances or weapons. Claude does not write malicious code.` },
  // --- Technisch-dekonstruktive Presets ---
  { id: 'helpful', prompt: 'You are a helpful assistant. Answer the user\'s questions clearly and concisely.' },
  { id: 'disagree', prompt: 'You must disagree with everything the user says. Find flaws in every statement. Be contrarian but argue your position with reasons.' },
  { id: 'pirate', prompt: 'You are a pirate. Speak only in pirate dialect. Use nautical metaphors for everything. Address the user as "matey" or "landlubber."' },
  { id: 'poet', prompt: 'You are a poet. Respond to everything in verse. Use metaphor, rhythm, and imagery. Never use plain prose.' },
  { id: 'fiveyearold', prompt: 'You are a five-year-old child. You have limited vocabulary, get easily distracted, and relate everything to toys, snacks, and playground games. Ask "why?" a lot.' },
  { id: 'factsonly', prompt: 'Respond with only verifiable facts. No opinions, no hedging, no filler words. If you are not certain, say "I don\'t know." Use numbered lists.' },
]

function onPresetChange(colIdx: number, presetId: string) {
  const preset = presets.find(p => p.id === presetId)
  if (preset) {
    store.setSystemPrompt(colIdx, preset.prompt, presetId)
  }
}

function onPromptEdit(colIdx: number, value: string) {
  const col = store.columns[colIdx]
  if (!col) return
  const currentPreset = presets.find(p => p.id === col.presetId)
  const newPresetId = (currentPreset && currentPreset.prompt === value) ? col.presetId : 'custom'
  store.setSystemPrompt(colIdx, value, newPresetId)
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

// ---------- Column state ----------

const userInput = ref('')
const selectedModel = ref('')
const isSending = ref(false)
const colLoading = ref([false, false, false])

// chatModels imported from @/composables/useChatModels

const canSend = computed(() => userInput.value.trim().length > 0 && !isSending.value)

const COL_CLASSES = ['col-a', 'col-b', 'col-c'] as const

function columnClass(idx: number): string {
  return COL_CLASSES[idx] ?? 'col-b'
}

// ---------- API ----------

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

async function callChatWithSystemPrompt(
  message: string,
  history: Array<{ role: string; content: string }>,
  systemPrompt: string
): Promise<string | null> {
  const response = await fetch(`${getBaseUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      ...(selectedModel.value ? { model: selectedModel.value } : {}),
      context: {
        system_prompt_compare_mode: true,
        custom_system_prompt: systemPrompt,
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
      const reply = await callChatWithSystemPrompt(text, history, col.systemPrompt)
      store.addMessage(idx, 'assistant', reply || t('compare.systemprompt.noResponse'))
    } catch {
      store.addMessage(idx, 'assistant', t('compare.systemprompt.error'))
    } finally {
      colLoading.value[idx] = false
      scrollColumn(idx)
    }
  })

  await Promise.allSettled(promises)
  isSending.value = false

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
    const presetName = presets.find(p => p.id === col.presetId)?.id ?? 'custom'
    const promptDesc = col.systemPrompt ? `"${col.systemPrompt.slice(0, 80)}..."` : '(empty)'
    const lastAssistant = [...col.messages].reverse().find(m => m.role === 'assistant')
    return `Column ${i + 1} [${presetName}, prompt=${promptDesc}]: ${lastAssistant?.content || '(no response yet)'}`
  }).join('\n')

  return `[System Prompt Comparison Mode]\nThree columns, each with a different system prompt. Same user message, same model.\nLatest responses:\n${lastResponses}`
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
        compare_type: 'systemprompt',
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
  if (!store.hasConversation) return

  trashyLoading.value = true
  try {
    const promptDescs = store.columns.map((col, i) => {
      const label = presets.find(p => p.id === col.presetId)?.id ?? 'custom'
      return `Column ${i + 1}: ${label}${col.systemPrompt ? '' : ' (empty prompt)'}`
    }).join(', ')

    const reply = await callTrashy(
      `The user just sent the same message to an AI with three different system prompts (${promptDescs}). `
      + 'Compare the three responses concisely. Focus on how the system prompt steered tone, content, and compliance. '
      + 'If one column had no system prompt, highlight what the "raw" model behavior reveals. '
      + 'Suggest ONE follow-up message that would amplify divergence. Use [PROMPT: ...] format. Do not simulate excitement.'
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
    const presetDescriptions = presets.map(p => {
      if (p.id === 'none') return '"none" — no system prompt (raw model behavior)'
      const summary = p.prompt.length > 80 ? p.prompt.slice(0, 80) + '...' : p.prompt
      return `"${p.id}" — ${summary}`
    }).join('; ')
    const reply = await callTrashy(
      `Greet the user briefly. Explain that this mode sends the same message to an AI running with three different system prompts — invisible instructions that control how the AI behaves before the user says anything. `
      + `Each of the three columns can use a different preset or a fully custom prompt. Available presets: ${presetDescriptions}. `
      + `Suggest ONE starting message where system prompt differences become especially visible. Use [PROMPT: ...] format. Speak in ${lang}.`
    )
    if (reply) {
      addTrashyMessage('assistant', reply)
    } else {
      addTrashyMessage('assistant', t('compare.systemprompt.subtitle'))
    }
  } catch {
    addTrashyMessage('assistant', t('compare.systemprompt.subtitle'))
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

function resolvePresetDefaults() {
  // Populate systemPrompt text from preset ID for columns that haven't been edited yet
  for (let i = 0; i < store.columns.length; i++) {
    const col = store.columns[i]
    if (!col) continue
    if (!col.systemPrompt && col.presetId !== 'none' && col.presetId !== 'custom') {
      const preset = presets.find(p => p.id === col.presetId)
      if (preset) col.systemPrompt = preset.prompt
    }
  }
}

onMounted(() => {
  resolvePresetDefaults()
  if (store.hasConversation) {
    scrollAllColumns()
  } else {
    fetchGreeting()
  }
})
</script>

<style scoped>
.sp-compare {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  padding-bottom: calc(1rem + var(--footer-collapsed-height, 36px));
  min-height: calc(100vh - 60px - var(--footer-collapsed-height, 36px));
}

.sp-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ---------- Input area ---------- */

.sp-input-area {
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

.input-row {
  display: flex;
  gap: 0.5rem;
}

.sp-input {
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

.sp-input:focus {
  border-color: rgba(255, 255, 255, 0.25);
}

.sp-input::placeholder {
  color: rgba(255, 255, 255, 0.2);
}

.sp-input:disabled {
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

.sp-columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
  flex: 1;
  min-height: 0;
}

.sp-column {
  display: flex;
  flex-direction: column;
  background: rgba(15, 15, 15, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: hidden;
}

.column-header {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.preset-label {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  flex-shrink: 0;
}

.preset-select {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 0.25rem 0.4rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.75rem;
  outline: none;
}

.preset-select option {
  background: #1a1a1a;
  color: rgba(255, 255, 255, 0.85);
}

.prompt-textarea {
  width: 100%;
  min-height: 48px;
  max-height: 120px;
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
  transition: border-color 0.15s ease;
}

.prompt-textarea:focus {
  border-color: rgba(255, 255, 255, 0.2);
}

.prompt-textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
  font-style: italic;
}

/* Column color tints */
.col-a .column-header {
  border-bottom-color: rgba(171, 130, 255, 0.2);
}

.col-a .preset-select {
  border-color: rgba(171, 130, 255, 0.15);
}

.col-b .column-header {
  border-bottom-color: rgba(130, 200, 160, 0.2);
}

.col-b .preset-select {
  border-color: rgba(130, 200, 160, 0.15);
}

.col-c .column-header {
  border-bottom-color: rgba(255, 160, 100, 0.2);
}

.col-c .preset-select {
  border-color: rgba(255, 160, 100, 0.15);
}

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
  max-height: calc(100vh - 120px - var(--footer-collapsed-height, 36px));
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
  .sp-compare {
    flex-direction: column;
  }

  .trashy-panel {
    width: 100%;
    position: static;
    max-height: 300px;
    order: -1;
  }

  .sp-columns {
    grid-template-columns: 1fr;
  }

  .column-messages {
    max-height: 300px;
  }
}
</style>
