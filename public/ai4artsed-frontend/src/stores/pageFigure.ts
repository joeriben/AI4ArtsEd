import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * The channel between a page that carries a platform voice and the overlay that
 * draws the one mask.
 *
 * The mask is rendered by ChatOverlay (from App.vue) and the pages are routed
 * views, so the two are siblings and no prop can reach across.
 *
 * It used to carry a second thing: which AGENT the mask was. Two surfaces
 * declared it to be their own — the workshop, the contesting machine — and
 * wrote their state onto it, took its click and had no help panel. That is
 * gone: the mask is the normal help mask everywhere, and the two agents are
 * represented only by what they put out as text, voice and items, which is
 * directly by what they do. There is nothing here for a page to claim.
 *
 * What remains is the platform voice — the page's authored address. It speaks
 * ON the page rather than in a panel, its waiting reaches the mask, and its
 * asking place is opened from there.
 */
export const usePageFigureStore = defineStore('pageFigure', () => {
  // ---- the platform voice, where a page carries one ----
  // Counted rather than a flag: a route change mounts the incoming page's voice
  // before the outgoing one is unmounted, and a flag would be left false.
  const voiceCount = ref(0)
  const hasVoice = computed(() => voiceCount.value > 0)
  /** The voice is waiting for its reply. */
  const voiceWaiting = ref(false)
  /** Its asking place stands open at the mask. */
  const voiceAsking = ref(false)
  /** Carried into that asking place when it is opened from the helper panel, so
   *  switching channels does not throw away what was already typed. */
  const voiceDraft = ref('')

  function registerVoice(): void {
    voiceCount.value += 1
  }

  function unregisterVoice(): void {
    voiceCount.value = Math.max(0, voiceCount.value - 1)
    if (voiceCount.value === 0) {
      voiceAsking.value = false
      voiceWaiting.value = false
      voiceDraft.value = ''
    }
  }

  /** Open the voice's asking place at the mask, carrying a draft into it. */
  function askVoice(draft = ''): void {
    voiceDraft.value = draft
    voiceAsking.value = true
  }

  function closeVoiceAsk(): void {
    voiceAsking.value = false
    voiceDraft.value = ''
  }

  return {
    hasVoice,
    voiceCount,
    voiceWaiting,
    voiceAsking,
    voiceDraft,
    registerVoice,
    unregisterVoice,
    askVoice,
    closeVoiceAsk,
  }
})
