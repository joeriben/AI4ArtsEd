/**
 * What a column of a chat comparison hands the model as its history, and what
 * a new conversation leaves of the old one (lib/chatColumns.ts).
 */
import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { chatColumnState, historyOf, type ColumnMessage } from '../chatColumns'

const line = (id: number, role: 'user' | 'assistant', content: string, failed = false): ColumnMessage =>
  ({ id, role, content, ...(failed ? { failed } : {}) })

describe('historyOf', () => {
  it('hands on a conversation that went through as it stands', () => {
    const h = historyOf([line(0, 'user', 'a'), line(1, 'assistant', 'b'), line(2, 'user', 'c'), line(3, 'assistant', 'd')])
    expect(h).toEqual([
      { role: 'user', content: 'a' },
      { role: 'assistant', content: 'b' },
      { role: 'user', content: 'c' },
      { role: 'assistant', content: 'd' },
    ])
  })

  it('leaves out an answer that never came, and the message it did not answer', () => {
    const h = historyOf([
      line(0, 'user', 'a'),
      line(1, 'assistant', 'No response received', true),
      line(2, 'user', 'c'),
      line(3, 'assistant', 'd'),
    ])
    expect(h).toEqual([
      { role: 'user', content: 'c' },
      { role: 'assistant', content: 'd' },
    ])
  })

  it('never holds two of the visitor\'s turns in a row after a failure', () => {
    const h = historyOf([line(0, 'user', 'a'), line(1, 'assistant', 'Connection error', true), line(2, 'user', 'c')])
    expect(h).toEqual([{ role: 'user', content: 'c' }])
  })

  it('carries no flag of its own to the model', () => {
    const h = historyOf([line(0, 'user', 'a'), line(1, 'assistant', 'b')])
    for (const turn of h) expect(Object.keys(turn).sort()).toEqual(['content', 'role'])
  })
})

describe('chatColumnState', () => {
  it('marks a failed line and only that one', () => {
    const columns = ref([{ messages: [] as ColumnMessage[] }])
    const state = chatColumnState(columns)
    state.addMessage(0, 'user', 'a')
    state.addMessage(0, 'assistant', 'x', true)
    expect(columns.value[0]!.messages.map(m => !!m.failed)).toEqual([false, true])
  })

  it('a new conversation empties the columns and forgets the last round', () => {
    const columns = ref([{ messages: [] as ColumnMessage[] }, { messages: [] as ColumnMessage[] }])
    const state = chatColumnState(columns)
    state.addMessage(0, 'user', 'a')
    state.addMessage(1, 'user', 'a')
    state.lastRound.value = { label: 'T=0.5', text: 'round' }
    state.temperature.value = 1.2
    expect(state.hasConversation.value).toBe(true)
    state.clearAll()
    expect(state.hasConversation.value).toBe(false)
    expect(state.lastRound.value).toBeNull()
    // The randomness is a setting of the surface, not of the conversation.
    expect(state.temperature.value).toBe(1.2)
  })
})
