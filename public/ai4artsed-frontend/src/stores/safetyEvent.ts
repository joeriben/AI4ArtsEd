import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { SafetyBlock } from '@/composables/useGenerationStream'

export const useSafetyEventStore = defineStore('safetyEvent', () => {
  const pendingBlock = ref<{
    /**
     * The server's block message (`safety_block`). Null where a surface holds
     * material back without one: its own check could not be carried out.
     */
    block: SafetyBlock | null
    vlmDescription?: string
    /**
     * The check did not run to a verdict — the material is held back by a fault
     * of this platform, not by a judgement of what someone made. Carried here
     * since 2026-09-04 so the window can say which of the two it is without
     * matching a German substring out of `reason`, which every translated or
     * re-worded sentence would fall through.
     */
    operational?: boolean
    /**
     * The refused picture is one the platform made and was handed back: a
     * Latent Lab instrument records its own pictures through the check where
     * material comes in (latent_lab_recorder_routes, 2026-10-31). It is said
     * as a made picture, not as one somebody brought.
     */
    generated?: boolean
  } | null>(null)
  const pendingAnalysis = ref<{ description: string; safe: boolean } | null>(null)

  function reportBlock(
    block: SafetyBlock | null | undefined,
    extras: { vlmDescription?: string; operational?: boolean; generated?: boolean } = {},
  ) {
    pendingBlock.value = {
      block: block ?? null,
      vlmDescription: extras.vlmDescription,
      operational: !!extras.operational,
      generated: !!extras.generated,
    }
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
