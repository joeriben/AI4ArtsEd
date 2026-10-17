import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { apiBase } from '@/services/labApi'

export const useUiModeStore = defineStore('uiMode', () => {
  const mode = ref<'easy' | 'medium' | 'expert'>('medium') // safe default
  const loaded = ref(false)

  async function fetchMode() {
    try {
      const baseUrl = apiBase()
      const { data } = await axios.get(`${baseUrl}/api/settings/ui-mode`)
      mode.value = data.ui_mode
      loaded.value = true
    } catch (e) {
      console.error('[UiMode] Failed to fetch UI mode:', e)
      loaded.value = true
    }
  }

  const isExpert = computed(() => mode.value === 'expert')
  const isEasy = computed(() => mode.value === 'easy')

  return { mode, loaded, isExpert, isEasy, fetchMode }
})
