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
  /** Kept since the cards can be pulled to a size; older entries have none. */
  w?: number
  h?: number
  outputUrl: string | null
  mediaType: string
  runId: string | null
  isFavorited: boolean
  /** What was asked for, and of which model — the card's back side. */
  prompt?: string
  configId?: string
  createdAt?: number
}

export const usePersonaChatStore = defineStore('personaChat', () => {
  const messages = ref<ChatMessage[]>([])
  let nextMsgId = 0

  const mediaBoxes = ref<StoredMediaBox[]>([])

  // Track session run ID for context persistence
  const sessionRunId = ref<string | null>(null)

  const hasConversation = computed(() => messages.value.length > 0)

  function addMessage(role: 'user' | 'assistant', content: string): number {
    const id = nextMsgId++
    messages.value.push({ id, role, content })
    return id
  }

  /** A line that is still being written. Returns false once its id is gone
   *  (the conversation was cleared while the answer was on its way). */
  function setContent(id: number, content: string): boolean {
    const msg = messages.value.find(m => m.id === id)
    if (!msg) return false
    msg.content = content
    return true
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
    setContent,
    clearConversation,
    saveMediaBox,
    removeMediaBox,
  }
})
