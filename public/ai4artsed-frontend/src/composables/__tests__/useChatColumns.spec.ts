/**
 * The round of a chat comparison (composables/useChatColumns.ts), against the
 * store of Model Comparison (Transformers Lab).
 *
 * What is held: a round outlives the surface that sent it — a surface is
 * unmounted when its tab is left and a fresh one is built on the way back,
 * and that one must find the round still out —, a column without a model sits
 * the round out, a failed answer is not handed on as the model's own, and Help
 * is told the settings the round was SENT with.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const turns: Array<{ body: any; resolve: (v: { reply: string }) => void; reject: (e: unknown) => void }> = []

vi.mock('@/lib/chatTurn', () => {
  class ChatStreamError extends Error {}
  class ChatNoReplyError extends Error {}
  return {
    ChatStreamError,
    ChatNoReplyError,
    chatTurn: (_url: string, body: unknown) =>
      new Promise((resolve, reject) => { turns.push({ body, resolve, reject }) }),
  }
})

vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key }),
}))

import { useChatColumns } from '../useChatColumns'
import { useSystemPromptAcrossModelsStore } from '@/stores/systemPromptAcrossModels'

function surface(store: ReturnType<typeof useSystemPromptAcrossModelsStore>, recorded: unknown[]) {
  return useChatColumns(store, {
    tag: 'TEST',
    runs: idx => !!store.columns[idx]?.modelId,
    body: (idx, message, history) => ({ message, history, model: store.columns[idx]?.modelId }),
    sentWith: () => ({ models: store.columns.map(c => c.modelId), temperature: store.temperature }),
    afterRound: sent => { recorded.push(sent) },
  })
}

const settle = () => new Promise(r => setTimeout(r, 0))

describe('useChatColumns', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    turns.length = 0
  })

  it('a surface built while a round is out finds it out, and locked', async () => {
    const store = useSystemPromptAcrossModelsStore()
    store.preselect(['a', 'b'])
    const recorded: unknown[] = []
    const first = surface(store, recorded)
    first.userInput.value = 'Hallo'
    const round = first.sendToAll()

    // The tab is left and come back to: a second surface over the same store.
    const second = surface(store, recorded)
    expect(second.isSending.value).toBe(true)
    expect(second.colLoading.value).toEqual([true, true, false])
    second.userInput.value = 'Noch etwas'
    expect(second.canSend.value).toBe(false)
    await second.sendToAll()
    expect(turns).toHaveLength(2)

    turns[0]!.resolve({ reply: 'A' })
    turns[1]!.resolve({ reply: 'B' })
    await round
    expect(second.isSending.value).toBe(false)
    expect(store.columns.map(c => c.messages.map(m => m.content))).toEqual([['Hallo', 'A'], ['Hallo', 'B'], []])
  })

  it('a column without a model is not asked', async () => {
    const store = useSystemPromptAcrossModelsStore()
    store.preselect(['a'])
    const s = surface(store, [])
    expect(s.total.value).toBe(1)
    s.userInput.value = 'Hallo'
    const round = s.sendToAll()
    expect(turns.map(t => t.body.model)).toEqual(['a'])
    turns[0]!.resolve({ reply: 'A' })
    await round
    expect(store.columns[1]!.messages).toEqual([])
  })

  it('an answer that never came is not handed on as the model\'s', async () => {
    const store = useSystemPromptAcrossModelsStore()
    store.preselect(['a'])
    const s = surface(store, [])
    s.userInput.value = 'eins'
    const r1 = s.sendToAll()
    turns[0]!.resolve({ reply: '' })
    await r1
    expect(store.columns[0]!.messages.map(m => [m.content, !!m.failed])).toEqual([
      ['eins', false], ['compare.shared.noResponse', true],
    ])
    s.userInput.value = 'zwei'
    const r2 = s.sendToAll()
    expect(turns[1]!.body.history).toEqual([])
    turns[1]!.resolve({ reply: 'Z' })
    await r2
  })

  it('Help is told what the round was sent with', async () => {
    const store = useSystemPromptAcrossModelsStore()
    store.preselect(['a', 'b', 'c'])
    store.temperature = 0.7
    const recorded: any[] = []
    const s = surface(store, recorded)
    s.userInput.value = 'Hallo'
    const round = s.sendToAll()
    store.temperature = 1.5
    store.setModel(0, 'x')
    for (const turn of turns) turn.resolve({ reply: 'R' })
    await round
    await settle()
    expect(recorded).toEqual([{ models: ['a', 'b', 'c'], temperature: 0.7 }])
  })
})
