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

const props = defineProps<Props>()
const { t } = useI18n()
const userPreferences = useUserPreferencesStore()

const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const isLoading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
let nextId = 0

function addMessage(role: 'user' | 'assistant', content: string) {
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

  addMessage('user', text)
  userInput.value = ''
  isLoading.value = true

  try {
    const isDev = import.meta.env.DEV
    const baseUrl = isDev ? 'http://localhost:17802' : ''

    // Build history from prior messages (exclude the just-added user message)
    const history = messages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content
    }))

    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history,
        context: { comparison_mode: true, language: userPreferences.language },
        draft_context: props.comparisonContext,
      })
    })

    const data = await response.json()
    if (data.reply) {
      addMessage('assistant', data.reply)
    } else if (data.error) {
      addMessage('assistant', `[Error: ${data.error}]`)
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
  addMessage('assistant', t('compare.trashyGreeting'))
}

onMounted(() => {
  addMessage('assistant', t('compare.trashyGreeting'))
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
    const isDev = import.meta.env.DEV
    const baseUrl = isDev ? 'http://localhost:17802' : ''

    const history = messages.value.map(m => ({ role: m.role, content: m.content }))

    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: 'The comparison is complete. Comment on visible differences between the language variants and explain why CLIP/T5 encoding causes this.',
        history,
        context: { comparison_mode: true, language: userPreferences.language },
        draft_context: context,
      })
    })

    const data = await response.json()
    if (data.reply) {
      addMessage('assistant', data.reply)
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
