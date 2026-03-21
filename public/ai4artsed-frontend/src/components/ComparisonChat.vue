<template>
  <div class="comparison-chat">
    <div class="chat-header">
      <img :src="trashyIcon" alt="Trashy" class="trashy-icon" />
      <span class="chat-title">Trashy</span>
    </div>

    <div class="chat-messages" ref="messagesRef">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="chat-bubble"
        :class="[msg.role, { separator: msg.isSeparator }]"
      >
        <template v-if="msg.isSeparator">
          <span class="separator-line"></span>
          <span class="separator-label">{{ msg.content }}</span>
          <span class="separator-line"></span>
        </template>
        <template v-else-if="msg.role === 'assistant'">
          <span v-for="(part, idx) in parseSuggestions(msg.content)" :key="idx">
            <span v-if="part.type === 'text'">{{ part.text }}</span>
            <button v-else class="prompt-suggestion" @click="emit('use-prompt', part.text)">{{ part.text }}</button>
          </span>
        </template>
        <template v-else>{{ msg.content }}</template>
      </div>
      <div v-if="isLoading" class="chat-bubble assistant loading">
        <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
      </div>
    </div>

    <div class="chat-input-area">
      <input
        v-model="userInput"
        class="chat-input"
        :placeholder="t('compare.chatPlaceholder')"
        @keydown.enter="sendMessage"
        :disabled="isLoading"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import trashyIcon from '@/assets/trashy-icon.png'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  isSeparator?: boolean
}

interface Props {
  comparisonContext: string
  compareType?: 'language' | 'model' | 'vlm-analysis' | 'temperature' | 'systemprompt' | 'llm-model'
}

interface ContentPart {
  type: 'text' | 'prompt'
  text: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'use-prompt': [prompt: string]
}>()
const { t } = useI18n()
const userPreferences = useUserPreferencesStore()
const deviceId = useDeviceId()

const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const isLoading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
let nextId = 0
let runCounter = 0

/** Parse [PROMPT: ...] markers into clickable suggestions */
function parseSuggestions(content: string): ContentPart[] {
  const parts: ContentPart[] = []
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

function addMessage(role: 'user' | 'assistant', content: string) {
  messages.value.push({ id: nextId++, role, content })
  scrollToBottom()
}

function addSeparator(label: string) {
  messages.value.push({ id: nextId++, role: 'system', content: label, isSeparator: true })
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

/** Build history for the LLM — excludes separators, keeps conversation flow */
function buildHistory(): Array<{ role: string; content: string }> {
  return messages.value
    .filter(m => !m.isSeparator)
    .map(m => ({ role: m.role, content: m.content }))
}

async function callChat(message: string, extraHistory?: Array<{ role: string; content: string }>): Promise<string | null> {
  const history = extraHistory ?? buildHistory()
  const response = await fetch(`${getBaseUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      context: {
        comparison_mode: true,
        compare_type: props.compareType || 'language',
        language: userPreferences.language,
        device_id: deviceId,
      },
      draft_context: props.comparisonContext,
    })
  })
  const data = await response.json()
  return data.reply || null
}

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return

  addMessage('user', text)
  userInput.value = ''
  isLoading.value = true

  try {
    const history = messages.value
      .filter(m => !m.isSeparator)
      .slice(0, -1)
      .map(m => ({ role: m.role, content: m.content }))
    const reply = await callChat(text, history)
    if (reply) {
      addMessage('assistant', reply)
    } else {
      addMessage('assistant', t('compare.shared.noResponse'))
    }
  } catch (e) {
    addMessage('assistant', t('compare.shared.error'))
  } finally {
    isLoading.value = false
  }
}

/** Called by parent to inject Trashy messages proactively */
function injectMessage(content: string) {
  addMessage('assistant', content)
}

/**
 * Called by parent when a new comparison run starts.
 * Adds a visual separator instead of clearing the chat,
 * so the conversation history accompanies the full session.
 */
function onNewRun() {
  runCounter++
  if (messages.value.length > 0) {
    addSeparator(`Run ${runCounter}`)
  }
}

/** Fetch a proactive greeting with prompt suggestions from the LLM */
async function fetchProactiveGreeting() {
  isLoading.value = true
  const greetingPrompt = props.compareType === 'model'
    ? 'Greet the user. Explain briefly: this mode compares how different image generation models interpret the same prompt — revealing hidden biases in training data. '
      + 'There are two presets — current top models (SD 3.5, Flux 2, Gemini) and SD history (SD 1.5 → SDXL → SD 3.5). '
      + 'Suggest 2-3 prompts that probe BIAS DIMENSIONS in image generation. Pick from these dimensions (vary each session): '
      + 'gender & gender roles, age, disability & body norms, phenotype & skin tone, ethnicity & cultural origin, socioeconomic status, body size & weight, beauty standards, sexual orientation & family forms, Global North default (geographic-cultural bias), religious & cultural symbolism, professional roles & occupations. '
      + 'Each prompt should be simple and neutral on the surface (e.g. "a doctor", "a family having dinner", "a beautiful person", "a CEO giving a speech", "a wedding celebration") '
      + 'but designed to reveal what the model assumes as default. Use [PROMPT: ...] format for each.'
    : props.compareType === 'vlm-analysis'
    ? 'Greet the user. Explain briefly: this mode shows how different vision models describe the same image. The user uploads or draws an image, picks an analysis perspective (neutral, art-historical, ethical, decolonial, etc.), and multiple models describe what they see. You then analyze what the models noticed and missed. Suggest uploading an image with visual complexity — faces, text in the image, spatial depth, or cultural symbols work well.'
    : props.compareType === 'temperature'
    ? 'Greet the user briefly. Explain that this mode sends the same message to an AI at three different "temperature" levels (0 = deterministic, 0.5 = balanced, 1.0 = creative). Temperature controls randomness — low temperature always picks the most likely word, high temperature explores surprising alternatives. Suggest ONE starting prompt where temperature differences are especially visible. Use [PROMPT: ...] format.'
    : props.compareType === 'systemprompt'
    ? 'Greet the user briefly. Explain that this mode sends the same message to an AI with three different system prompts. The system prompt shapes the AI\'s personality and perspective. Suggest ONE starting prompt that would reveal how different system prompts change the response. Use [PROMPT: ...] format.'
    : props.compareType === 'llm-model'
    ? 'Greet the user briefly. Explain that this mode sends the same message to three different AI models simultaneously. Each model has different training data, safety policies, and cultural perspectives — the same question can produce very different answers. Suggest 2-3 starting prompts that reveal these differences. Focus on ethical questions, not partisan politics. Examples: gender-neutral toilets, AI in medical diagnosis, cultural attitudes to eating meat, historical events different countries teach differently. Use [PROMPT: ...] format for each suggestion.'
    : 'Greet the user. State briefly what this mode does. Suggest ONE starting prompt where encoding differences between languages are likely, and explain in one sentence why. Use [PROMPT: ...] format.'
  try {
    const reply = await callChat(greetingPrompt, [])
    if (reply) {
      addMessage('assistant', reply)
    } else {
      addMessage('assistant', t('compare.trashyGreeting'))
    }
  } catch {
    addMessage('assistant', t('compare.trashyGreeting'))
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  fetchProactiveGreeting()
})

// Watch context changes — Trashy reacts to completed comparisons
watch(() => props.comparisonContext, (ctx) => {
  if (ctx && ctx.includes('generation_complete')) {
    sendAutoComment(ctx)
  }
})

async function sendAutoComment(_context: string) {
  isLoading.value = true
  const autoPrompt = props.compareType === 'model'
    ? 'The model comparison run just completed. Analyze the VLM image descriptions in your context. '
      + 'Focus on BIAS: What does each model assume as default? Who is depicted — what gender, age, skin tone, body type, cultural context? '
      + 'What is absent or invisible? Are there differences between models in how they default? '
      + 'Name the bias dimensions concretely: gender & gender roles, age, disability & body norms, phenotype & skin tone, ethnicity & cultural origin, socioeconomic status, body size & weight, beauty standards, sexual orientation & family forms, Global North default, religious & cultural symbolism, professional roles & occupations. '
      + 'Then suggest ONE follow-up prompt that probes a DIFFERENT bias dimension than the current one. Use [PROMPT: ...] format. '
      + 'Do not suggest prompts from a generic list — derive from the concrete observation. Do not simulate excitement.'
    : props.compareType === 'vlm-analysis'
    ? 'The VLM image analysis just completed. Multiple vision models described the same image. '
      + 'Analyze the descriptions in your context: what does each model focus on? What do they miss? '
      + 'Where does model size make a visible difference in detail or nuance? '
      + 'If one model mentions something no other does, highlight it. '
      + 'Do not use technical jargon. Do not simulate excitement.'
    : props.compareType === 'temperature'
    ? 'The user just sent the same message at three different temperatures (0, 0.5, 1.0). '
      + 'Compare the three responses concisely. Focus on concrete differences in content, style, and creativity. '
      + 'If the responses diverge interestingly, suggest ONE follow-up prompt that would amplify the divergence. '
      + 'Use [PROMPT: ...] format. Do not simulate excitement.'
    : props.compareType === 'systemprompt'
    ? 'The user just sent the same message with three different system prompts. '
      + 'Compare the three responses concisely. Focus on how the system prompt shaped tone, content, and perspective. '
      + 'If the responses diverge interestingly, suggest ONE follow-up prompt that would amplify the divergence. '
      + 'Use [PROMPT: ...] format. Do not simulate excitement.'
    : props.compareType === 'llm-model'
    ? 'The user just sent the same message to three different AI models. '
      + 'Compare the responses concisely. Focus on: which model was more cautious or more open? Did any model refuse or redirect? '
      + 'Were there factual differences? Did cultural or training biases become visible? '
      + 'If the responses diverge interestingly, suggest ONE follow-up that would deepen the divergence. '
      + 'Use [PROMPT: ...] format. Do not simulate excitement.'
    : 'The language comparison run just completed. Analyze the VLM image descriptions in your context. '
      + 'State factually what differs between the language variants and why (grounded in the specific descriptions, not generic CLIP bias). '
      + 'If a significant divergence exists, derive ONE follow-up prompt from the concrete observation. Use [PROMPT: ...] format. '
      + 'Do not suggest prompts from a generic list. Do not simulate excitement.'
  try {
    const reply = await callChat(autoPrompt)
    if (reply) {
      addMessage('assistant', reply)
    }
  } catch {
    // Silent fail for auto-comments
  } finally {
    isLoading.value = false
  }
}

/** Session 273: Return chat messages for context persistence */
function getMessages(): Array<{ role: string; content: string }> {
  return messages.value
    .filter(m => !m.isSeparator)
    .map(m => ({ role: m.role, content: m.content }))
}

/** Clear all messages and re-greet */
function clearMessages() {
  messages.value = []
  nextId = 0
  runCounter = 0
  fetchProactiveGreeting()
}

/** Trigger auto-comment programmatically (for text compare views) */
function triggerAutoComment() {
  sendAutoComment(props.comparisonContext)
}

defineExpose({ injectMessage, onNewRun, getMessages, clearMessages, triggerAutoComment })
</script>

<style scoped>
.comparison-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgba(15, 15, 15, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.trashy-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.chat-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.chat-bubble {
  max-width: 90%;
  padding: 0.5rem 0.75rem;
  border-radius: 12px;
  font-size: 0.8rem;
  line-height: 1.4;
  word-break: break-word;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.8);
  border-bottom-left-radius: 4px;
}

.chat-bubble.user {
  align-self: flex-end;
  background: rgba(76, 175, 80, 0.15);
  color: rgba(255, 255, 255, 0.9);
  border-bottom-right-radius: 4px;
}

.chat-bubble.separator {
  align-self: center;
  max-width: 100%;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0;
  background: none;
  border-radius: 0;
}

.separator-line {
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
}

.separator-label {
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.2);
  text-transform: uppercase;
  letter-spacing: 1px;
  white-space: nowrap;
}

.chat-bubble.loading {
  padding: 0.6rem 1rem;
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

.prompt-suggestion {
  display: inline;
  background: rgba(255, 179, 0, 0.12);
  border: 1px solid rgba(255, 179, 0, 0.3);
  border-radius: 6px;
  padding: 0.15rem 0.4rem;
  color: rgba(255, 179, 0, 0.9);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
  line-height: 1.4;
}

.prompt-suggestion:hover {
  background: rgba(255, 179, 0, 0.22);
  border-color: rgba(255, 179, 0, 0.5);
}

.chat-input-area {
  padding: 0.5rem 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.chat-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.8rem;
  outline: none;
}

.chat-input:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.chat-input::placeholder {
  color: rgba(255, 255, 255, 0.25);
}

.chat-input:disabled {
  opacity: 0.5;
}
</style>
