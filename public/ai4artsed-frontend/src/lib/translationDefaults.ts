/**
 * What a Canvas translation node shows, and the executor sends, where the node
 * leaves its instruction empty: the platform's translation instruction, and
 * English where no target language is chosen either (GET /api/canvas/translation, from
 * devserver/my_app/services/translation_instruction.py). The backend holds the
 * wording; where the request fails, the node says so with the cause.
 *
 * Asked for once and shared by every translation node on the board. A failed
 * request is asked again by the next node that mounts or has its field focused.
 */
import { ref } from 'vue'

export const translationDefaults = ref({ instruction: '', language: '' })
export const translationDefaultsError = ref('')

let asked = false

export function loadTranslationDefaults(): void {
  if (asked) return
  asked = true
  fetch('/api/canvas/translation')
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return response.json()
    })
    .then(data => {
      if (!data?.instruction) throw new Error('no instruction in the answer')
      translationDefaults.value = { instruction: data.instruction, language: data.language }
      translationDefaultsError.value = ''
    })
    .catch((error: unknown) => {
      asked = false
      translationDefaultsError.value = error instanceof Error ? error.message : String(error)
    })
}
