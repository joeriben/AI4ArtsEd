import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { ChatMessage } from './personaChat'

export interface TempColumn {
  temperature: number
  messages: ChatMessage[]
}

export const useTemperatureCompareStore = defineStore('temperatureCompare', () => {
  let nextMsgId = 0

  const columns = ref<TempColumn[]>([
    { temperature: 0, messages: [] },
    { temperature: 0.5, messages: [] },
    { temperature: 1.0, messages: [] },
  ])

  const hasConversation = computed(() =>
    columns.value.some(col => col.messages.length > 0)
  )

  function addMessage(colIdx: number, role: 'user' | 'assistant', content: string) {
    const col = columns.value[colIdx]
    if (col) col.messages.push({ id: nextMsgId++, role, content })
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
    clearAll,
  }
})
