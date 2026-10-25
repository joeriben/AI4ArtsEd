import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useSafetyEventStore = defineStore('safetyEvent', () => {
  const pendingBlock = ref<{
    stage: number | string
    reason: string
    foundTerms: string[]
    vlmDescription?: string
    /**
     * The check did not run to a verdict — the material is held back by a fault
     * of this platform, not by a judgement of what someone made. Carried here
     * since 2026-09-04 so the window can say which of the two it is without
     * matching a German substring out of `reason`, which every translated or
     * re-worded sentence would fall through.
     */
    operational?: boolean
  } | null>(null)
  const pendingAnalysis = ref<{ description: string; safe: boolean } | null>(null)

  function reportBlock(
    stage: number | string,
    reason: string,
    foundTerms: string[] = [],
    vlmDescription?: string,
    operational = false,
  ) {
    pendingBlock.value = { stage, reason, foundTerms, vlmDescription, operational }
  }

  function reportAnalysis(description: string, safe: boolean) {
    pendingAnalysis.value = { description, safe }
  }

  function consume() {
    const event = pendingBlock.value
    pendingBlock.value = null
    return event
  }

  function consumeAnalysis() {
    const event = pendingAnalysis.value
    pendingAnalysis.value = null
    return event
  }

  return { pendingBlock, pendingAnalysis, reportBlock, reportAnalysis, consume, consumeAnalysis }
})
