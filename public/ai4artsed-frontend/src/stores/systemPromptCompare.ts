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

  // Default presets are resolved from the component's preset list on mount.
  // Store only holds presetId; systemPrompt gets populated by the component.
  const columns = ref<SysPromptColumn[]>([
    { systemPrompt: '', presetId: 'none', messages: [] },
    { systemPrompt: '', presetId: 'claude', messages: [] },
    { systemPrompt: '', presetId: 'pirate', messages: [] },
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
