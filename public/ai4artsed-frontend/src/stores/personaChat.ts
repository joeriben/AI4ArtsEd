import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

export interface StoredMediaBox {
  id: string
  x: number
  y: number
  outputUrl: string | null
  mediaType: string
  runId: string | null
  isFavorited: boolean
}

export const usePersonaChatStore = defineStore('personaChat', () => {
  const messages = ref<ChatMessage[]>([])
  let nextMsgId = 0

  const mediaBoxes = ref<StoredMediaBox[]>([])

  // Session 273: Track session run ID for context persistence
  const sessionRunId = ref<string | null>(null)

  const hasConversation = computed(() => messages.value.length > 0)

  function addMessage(role: 'user' | 'assistant', content: string) {
    messages.value.push({ id: nextMsgId++, role, content })
  }

  function clearConversation() {
    messages.value = []
    nextMsgId = 0
    mediaBoxes.value = []
    sessionRunId.value = null
  }

  function saveMediaBox(box: StoredMediaBox) {
    const idx = mediaBoxes.value.findIndex(b => b.id === box.id)
    if (idx >= 0) {
      mediaBoxes.value[idx] = box
    } else {
      mediaBoxes.value.push(box)
    }
  }

  function removeMediaBox(id: string) {
    mediaBoxes.value = mediaBoxes.value.filter(b => b.id !== id)
  }

  return {
    messages,
    mediaBoxes,
    sessionRunId,
    hasConversation,
    addMessage,
    clearConversation,
    saveMediaBox,
    removeMediaBox,
  }
})
