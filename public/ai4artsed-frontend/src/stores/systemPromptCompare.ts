import { ref } from 'vue'
import { defineStore } from 'pinia'
import { chatColumnState, type ColumnMessage } from '@/lib/chatColumns'

export interface SysPromptColumn {
  systemPrompt: string
  presetId: string
  messages: ColumnMessage[]
}

export const useSystemPromptCompareStore = defineStore('systemPromptCompare', () => {
  // A preset's text is resolved from views/compare/system_prompt_presets.ts
  // when the surface mounts; until then the store holds only presetId.
  const columns = ref<SysPromptColumn[]>([
    { systemPrompt: '', presetId: 'claude_opus_3', messages: [] },
    { systemPrompt: '', presetId: 'claude_opus_4', messages: [] },
    { systemPrompt: '', presetId: 'claude_opus_5', messages: [] },
  ])

  /** The ONE model all three columns run on; '' is „Default (Settings)": the
   *  request then names no model. Kept here, with the answers it gave. */
  const modelId = ref('')

  function setSystemPrompt(colIdx: number, prompt: string, presetId: string) {
    const col = columns.value[colIdx]
    if (col) {
      col.systemPrompt = prompt
      col.presetId = presetId
    }
  }

  return {
    columns,
    modelId,
    // The messages, the randomness and the last round (lib/chatColumns.ts).
    ...chatColumnState(columns),
    setSystemPrompt,
  }
})
