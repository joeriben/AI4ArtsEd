/**
 * What the two chat comparisons do the same: the message field with its
 * clipboard and its perspective ring, and the round that puts ONE message to
 * all three columns at once and files each answer, or the failure of one, in
 * its column.
 *
 * System Prompts (views/compare/system_prompt_comparison.vue) and Model
 * Comparison (Transformers Lab, views/latent_lab/system_prompt_across_models.vue)
 * differ in what a column is sent with, a system prompt of its own or a model
 * of its own; that is the `body` each surface passes in. Until 2026-10-27 the
 * rest stood in System Prompts alone, and the second surface would have been
 * its copy.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { chatTurn, ChatStreamError, ChatNoReplyError } from '@/lib/chatTurn'
import { SseHttpError } from '@/lib/sseStream'
import { historyOf, type ColumnMessage, type HistoryTurn } from '@/lib/chatColumns'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { useDeviceId } from '@/composables/useDeviceId'
import { apiBase } from '@/services/labApi'

export interface ChatColumnsStore {
  columns: { messages: ColumnMessage[] }[]
  sending: boolean
  loading: boolean[]
  roundCols: number[]
  addMessage(colIdx: number, role: 'user' | 'assistant', content: string, failed?: boolean): void
}

export interface ChatColumnsOptions<S> {
  /** What the console says a failed turn came from. */
  tag: string
  /** Whether a column takes part in a round. A column with nothing to run on sits it out. */
  runs?: (colIdx: number) => boolean
  /**
   * What one column is sent. Called for all columns of a round in the same
   * tick, before the first answer can come back, so every column is asked
   * under the same settings.
   */
  body: (colIdx: number, message: string, history: HistoryTurn[]) => Record<string, unknown>
  /**
   * What the round was sent with, taken as it is sent, so that what Help is
   * told afterwards names the settings the answers were drawn under and not
   * whatever stands there when the last one arrives.
   */
  sentWith: () => S
  /** After every column of the round has answered or failed. */
  afterRound?: (sent: S) => void
}

export function useChatColumns<S>(store: ChatColumnsStore, opts: ChatColumnsOptions<S>) {
  const { t } = useI18n()
  const deviceId = useDeviceId()
  const runs = opts.runs ?? (() => true)

  const userInput = ref('')

  // The round itself is the store's (lib/chatColumns.ts): it outlives the
  // surface that sent it.
  const isSending = computed(() => store.sending)
  const colLoading = computed(() => store.loading)

  /** The columns a press would put the message to now. */
  const runnable = computed(() => store.columns.map((_, i) => i).filter(i => runs(i)))

  /**
   * How many have answered — what the bar counts while a round is out. The
   * columns go out at once, so this counts what has come BACK.
   */
  const answered = computed(() => store.roundCols.filter(i => !store.loading[i]).length)
  const total = computed(() => (store.sending ? store.roundCols.length : runnable.value.length))

  // --- Clipboard ---
  function copyPrompt() { window.navigator.clipboard.writeText(userInput.value) }
  async function pastePrompt() { userInput.value = await window.navigator.clipboard.readText() }
  function clearPrompt() { userInput.value = '' }

  // --- Perspective ---
  // What the ring in the corner of the field says when the perspective wrote
  // nothing: a refusal, a failure with its status, an empty answer, or no
  // connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
  // the console, and the ring spun and stopped in silence.
  const showPresetOverlay = ref(false)
  // The perspective is at work on the prompt: the symbol that was pressed pulses.
  const enriching = ref(false)
  const perspectiveError = ref('')

  /**
   * Whether a press would send. Not while the perspective is still rewriting
   * the message: the round would go out with the old text, and the new one
   * would land in the field after it had been emptied.
   */
  const canSend = computed(() =>
    !!userInput.value.trim() && !store.sending && !enriching.value && runnable.value.length > 0
  )

  async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
    showPresetOverlay.value = false
    if (!userInput.value.trim()) return

    enriching.value = true
    perspectiveError.value = ''
    try {
      const outcome = await interceptPrompt(payload.configId, userInput.value, deviceId)
      if ('written' in outcome) {
        userInput.value = outcome.written
      } else {
        perspectiveError.value = perspectiveFailureText(t, outcome)
      }
    } catch (error) {
      perspectiveError.value = generationErrorFor(t, error)
    } finally {
      enriching.value = false
    }
  }

  // --- One turn ---

  async function takeTurn(body: Record<string, unknown>): Promise<string | null> {
    try {
      const data = await chatTurn(`${apiBase()}/api/chat/stream`, body)
      return data.reply || null
    } catch (e) {
      // Three endings that this call read as "no reply" while it went to the
      // blocking endpoint, and the column showed as such: a turn the server
      // itself ended (a non-2xx JSON body then, an event in the stream now), a
      // refusal before the stream opened (the non-2xx itself), and a stream
      // that stopped without a turn in it. All three keep that wording — with
      // the cause on the console. A torn connection and an abort throw
      // something else and still reach the round's error branch, which says
      // something else.
      if (e instanceof ChatStreamError || e instanceof SseHttpError
          || e instanceof ChatNoReplyError) {
        console.error(`[${opts.tag}] chat turn failed:`, e)
        return null
      }
      throw e
    }
  }

  // --- The round ---

  async function sendToAll() {
    if (!canSend.value) return
    const text = userInput.value.trim()
    const round = runnable.value
    const sent = opts.sentWith()

    userInput.value = ''
    store.sending = true
    store.roundCols = round

    for (const idx of round) {
      store.addMessage(idx, 'user', text)
      store.loading[idx] = true
    }

    await Promise.allSettled(round.map(async (idx) => {
      try {
        // Everything before the message just added.
        const history = historyOf(store.columns[idx]?.messages.slice(0, -1) ?? [])
        const reply = await takeTurn(opts.body(idx, text, history))
        if (reply) store.addMessage(idx, 'assistant', reply)
        else store.addMessage(idx, 'assistant', t('compare.shared.noResponse'), true)
      } catch {
        store.addMessage(idx, 'assistant', t('compare.shared.error'), true)
      } finally {
        store.loading[idx] = false
      }
    }))

    store.sending = false
    opts.afterRound?.(sent)
  }

  return {
    userInput,
    isSending,
    colLoading,
    answered,
    total,
    canSend,
    copyPrompt,
    pastePrompt,
    clearPrompt,
    showPresetOverlay,
    enriching,
    perspectiveError,
    handlePresetSelected,
    sendToAll,
  }
}
