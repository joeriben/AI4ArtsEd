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
        :class="msg.role"
      >
        <template v-if="msg.role === 'assistant'">
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
import trashyIcon from '@/assets/trashy-icon.png'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  comparisonContext: string
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

const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const isLoading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
let nextId = 0

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
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

function buildHistory(): Array<{ role: string; content: string }> {
  return messages.value.map(m => ({ role: m.role, content: m.content }))
}

async function callChat(message: string, extraHistory?: Array<{ role: string; content: string }>): Promise<string | null> {
  const history = extraHistory ?? buildHistory()
  const response = await fetch(`${getBaseUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      context: { comparison_mode: true, language: userPreferences.language },
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
    const history = messages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content }))
    const reply = await callChat(text, history)
    if (reply) {
      addMessage('assistant', reply)
    } else {
      addMessage('assistant', '[No response]')
    }
  } catch (e) {
    addMessage('assistant', '[Connection error]')
  } finally {
    isLoading.value = false
  }
}

/** Called by parent to inject Trashy messages proactively */
function injectMessage(content: string) {
  addMessage('assistant', content)
}

/** Reset chat for new comparison run */
function resetChat() {
  messages.value = []
  fetchProactiveGreeting()
}

/** Fetch a proactive greeting with prompt suggestions from the LLM */
async function fetchProactiveGreeting() {
  isLoading.value = true
  try {
    const reply = await callChat(
      'Greet the user briefly. Suggest 2-3 concrete test prompts that would reveal interesting encoding biases when compared across languages. Use [PROMPT: ...] format for each suggestion.',
      []
    )
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

// Watch context changes — Trashy can react
watch(() => props.comparisonContext, (ctx) => {
  if (ctx && ctx.includes('generation_complete')) {
    sendAutoComment(ctx)
  }
})

async function sendAutoComment(context: string) {
  isLoading.value = true
  try {
    const reply = await callChat(
      'The comparison is complete. Comment on visible differences between the language variants and explain why CLIP/T5 encoding causes this. Then suggest 1-2 follow-up prompts using [PROMPT: ...] format.'
    )
    if (reply) {
      addMessage('assistant', reply)
    }
  } catch {
    // Silent fail for auto-comments
  } finally {
    isLoading.value = false
  }
}

defineExpose({ injectMessage, resetChat })
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
