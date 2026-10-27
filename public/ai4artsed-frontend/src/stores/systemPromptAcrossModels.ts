/**
 * Model Comparison (Transformers Lab): ONE system prompt for all three
 * columns, and a model per column — System Prompts with the two axes exchanged
 * (stores/systemPromptCompare.ts holds the other one).
 *
 * The columns open on no model of their own: which models they show first is
 * filled in by the surface once the platform has said which models it offers,
 * and only once (`preselected`), so a visitor who comes back finds the models
 * they chose.
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { chatColumnState, type ColumnMessage } from '@/lib/chatColumns'

export interface ModelColumn {
  /** '' is a column with no model chosen: it sits a round out. */
  modelId: string
  messages: ColumnMessage[]
}

export const useSystemPromptAcrossModelsStore = defineStore('systemPromptAcrossModels', () => {
  const columns = ref<ModelColumn[]>([
    { modelId: '', messages: [] },
    { modelId: '', messages: [] },
    { modelId: '', messages: [] },
  ])

  const systemPrompt = ref('')
  const presetId = ref('none')

  /**
   * Whether the columns' first models have been filled in, or a visitor has
   * already chosen one by hand. Either ends the preselection.
   */
  const preselected = ref(false)

  /** A model chosen by hand. It also ends the preselection: a list that
   *  arrives late must not overwrite what a visitor has already chosen. */
  function setModel(colIdx: number, modelId: string) {
    const col = columns.value[colIdx]
    if (col) col.modelId = modelId
    preselected.value = true
  }

  /** The first models, in column order; a column with none left has none. */
  function preselect(modelIds: string[]) {
    columns.value.forEach((col, i) => {
      col.modelId = modelIds[i] ?? ''
    })
    preselected.value = true
  }

  function setSystemPrompt(prompt: string, id: string) {
    systemPrompt.value = prompt
    presetId.value = id
  }

  return {
    columns,
    // The messages, the randomness and the last round (lib/chatColumns.ts).
    ...chatColumnState(columns),
    systemPrompt,
    presetId,
    preselected,
    setModel,
    preselect,
    setSystemPrompt,
  }
})
