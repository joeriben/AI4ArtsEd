/**
 * What a chat comparison keeps about its columns, in its store: the lines of
 * each column's conversation, the randomness the comparison runs at, and what
 * the last round produced for Help.
 *
 * Two stores hold this since 2026-10-27, System Prompts' (stores/
 * systemPromptCompare.ts) and that of Model Comparison in the Transformers Lab
 * (stores/systemPromptAcrossModels.ts). Their columns differ in what sets a
 * column apart, a system prompt or a model, and in nothing else, so the rest
 * stands here once and each store spreads it beside its own columns.
 */
import { computed, ref, type Ref } from 'vue'
import type { ChatMessage } from '@/stores/personaChat'

/**
 * A line of a column. `failed` marks the line that stands where an answer
 * did not come: the platform's own words, not the model's.
 */
export interface ColumnMessage extends ChatMessage {
  failed?: boolean
}

/** A turn as the model is handed it. */
export interface HistoryTurn {
  role: 'user' | 'assistant'
  content: string
}

/**
 * What a column has said so far, as the model is handed it. A line that stands
 * for an answer that never came is left out: sent as the model's own turn, the
 * model would be told it had once answered "No response received". The message
 * it failed to answer goes with it, so the history never holds two of the
 * visitor's turns in a row.
 */
export function historyOf(messages: readonly ColumnMessage[]): HistoryTurn[] {
  const out: HistoryTurn[] = []
  messages.forEach((m, i) => {
    if (m.failed) return
    if (m.role === 'user' && messages[i + 1]?.failed) return
    out.push({ role: m.role, content: m.content })
  })
  return out
}

/** The last round, as Help is told it (`instrumentRuns`). */
export interface ChatRound {
  label: string
  text: string
}

/**
 * The state beside the columns. It lives in the store and not in the surface,
 * so a visitor who comes back finds the randomness the answers were drawn at
 * and Help still knows what the columns hold — and finds a round that is still
 * out still out: a surface is unmounted when its tab is left, the answers of
 * its round arrive anyway, and a fresh surface that took the round for over
 * would unlock „New conversation" and the settings while they are on their way.
 */
export function chatColumnState<C extends { messages: ColumnMessage[] }>(columns: Ref<C[]>) {
  let nextMsgId = 0

  /** null until it is first moved: the axis then stands at its own start. */
  const temperature = ref<number | null>(null)

  const lastRound = ref<ChatRound | null>(null)

  /** A round is out. */
  const sending = ref(false)
  /** Per column: its answer is still out. */
  const loading = ref<boolean[]>(columns.value.map(() => false))
  /** The columns the round that is out, or that came back last, was put to. */
  const roundCols = ref<number[]>([])

  const hasConversation = computed(() =>
    columns.value.some(col => col.messages.length > 0)
  )

  function addMessage(colIdx: number, role: 'user' | 'assistant', content: string, failed = false) {
    const col = columns.value[colIdx]
    if (col) col.messages.push({ id: nextMsgId++, role, content, ...(failed ? { failed } : {}) })
  }

  /** A new conversation: the columns are emptied, and Help is told nothing of the old one. */
  function clearAll() {
    for (const col of columns.value) {
      col.messages = []
    }
    nextMsgId = 0
    lastRound.value = null
  }

  return { temperature, lastRound, sending, loading, roundCols, hasConversation, addMessage, clearAll }
}
