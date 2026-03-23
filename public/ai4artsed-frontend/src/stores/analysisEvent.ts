import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useAnalysisEventStore = defineStore('analysisEvent', () => {
  const pendingReflection = ref<{
    analysisText: string
    userPrompt: string
    viewType: string
  } | null>(null)

  function requestReflection(analysisText: string, userPrompt: string, viewType: string) {
    pendingReflection.value = { analysisText, userPrompt, viewType }
  }

  function consume() {
    const event = pendingReflection.value
    pendingReflection.value = null
    return event
  }

  return { pendingReflection, requestReflection, consume }
})
