import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * Global generation lock — prevents navigation while a Stage 4 generation is running.
 * All views share this store. Mode-selector links in App.vue are disabled when locked.
 */
export const useGenerationLockStore = defineStore('generationLock', () => {
  const isGenerating = ref(false)

  function lock() {
    isGenerating.value = true
  }

  function unlock() {
    isGenerating.value = false
  }

  return { isGenerating, lock, unlock }
})
