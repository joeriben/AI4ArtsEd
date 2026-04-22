import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { ChatMessage } from './personaChat'

export interface LlmModelColumn {
  modelId: string
  messages: ChatMessage[]
}

export const useLlmModelCompareStore = defineStore('llmModelCompare', () => {
  let nextMsgId = 0

  const columns = ref<LlmModelColumn[]>([
    { modelId: 'local/qwen3:4b', messages: [] },
    { modelId: 'local/phi-3.5-mini', messages: [] },
    { modelId: 'local/gemma-2-2b', messages: [] },
  ])

  const systemPrompt = ref('')
  const systemPresetId = ref('none')

  const hasConversation = computed(() =>
    columns.value.some(col => col.messages.length > 0)
  )

  function setModel(colIdx: number, modelId: string) {
    const col = columns.value[colIdx]
    if (col) col.modelId = modelId
  }

  function setSystemPrompt(prompt: string, presetId: string) {
    systemPrompt.value = prompt
    systemPresetId.value = presetId
  }

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
    systemPrompt,
    systemPresetId,
    hasConversation,
    setModel,
    setSystemPrompt,
    addMessage,
    clearAll,
  }
})
