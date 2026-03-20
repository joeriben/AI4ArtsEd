import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { ChatMessage } from './personaChat'

export interface SysPromptColumn {
  systemPrompt: string
  presetId: string
  messages: ChatMessage[]
}

export const useSystemPromptCompareStore = defineStore('systemPromptCompare', () => {
  let nextMsgId = 0

  const columns = ref<SysPromptColumn[]>([
    { systemPrompt: '', presetId: 'none', messages: [] },
    { systemPrompt: 'You are a helpful assistant. Answer the user\'s questions clearly and concisely.', presetId: 'helpful', messages: [] },
    { systemPrompt: 'You are a pirate. Speak only in pirate dialect. Use nautical metaphors for everything. Address the user as "matey" or "landlubber."', presetId: 'pirate', messages: [] },
  ])

  const hasConversation = computed(() =>
    columns.value.some(col => col.messages.length > 0)
  )

  function addMessage(colIdx: number, role: 'user' | 'assistant', content: string) {
    const col = columns.value[colIdx]
    if (col) col.messages.push({ id: nextMsgId++, role, content })
  }

  function setSystemPrompt(colIdx: number, prompt: string, presetId: string) {
    const col = columns.value[colIdx]
    if (col) {
      col.systemPrompt = prompt
      col.presetId = presetId
    }
  }

  function clearAll() {
    for (const col of columns.value) {
      col.messages = []
    }
    nextMsgId = 0
  }

  return {
    columns,
    hasConversation,
    addMessage,
    setSystemPrompt,
    clearAll,
  }
})
