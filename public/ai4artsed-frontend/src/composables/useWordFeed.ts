/**
 * Words at reading pace, kept apart from the pace they arrive at.
 *
 * A model answers in bursts. Stage 1+2 sends dozens of small chunks, a few
 * characters each; the adaption sends its whole text in a single chunk and is
 * done. Written straight into a box the first one jitters and the second one
 * appears out of nothing, and both make the box look like a field that was
 * filled rather than a station that worked.
 *
 * Everything goes through a queue here instead: whatever arrives is cut into
 * words, and one word leaves every 50 ms. The mechanism is the one the media
 * input boxes carried on the transform surface -- same cut, same 50 ms, same
 * repair against the stream's own final text at the end. The word queue is
 * built into both boxes.
 *
 * Word by word rather than character by character: it reads better, and it
 * empties the queue fast enough that a long text stops trickling once the
 * stream itself is long finished.
 */

/** One word every 50 ms — the pace the transform surface was read at for a year. */
export const WORD_MS = 50

export interface WordFeed {
  /** More text has arrived. It is queued; none of it is shown at once. */
  push(text: string): void
  /**
   * Nothing more will arrive. The queue goes on draining, and once it is empty
   * the box is set to `finalText` if the two ever came apart. Resolves then --
   * or at once, if the feed was flushed or given up in the meantime.
   */
  finish(finalText?: string): Promise<void>
  /** Everything still queued, now: the box holds the whole text from here on. */
  flush(): void
  /** Give up. The timers go, the queue goes, what stands in the box stays. */
  stop(): void
}

/**
 * `write` is handed the WHOLE text each time, not the new word: a box that
 * appends for itself has a second copy of the same accumulation, and the two
 * come apart the moment somebody types into it.
 */
export function wordFeed(write: (text: string) => void, tickMs = WORD_MS): WordFeed {
  const queue: string[] = []
  let shown = ''
  let final: string | undefined
  let tick: ReturnType<typeof setInterval> | null = null
  let watch: ReturnType<typeof setInterval> | null = null
  let pending: (() => void) | null = null

  const clearTimers = () => {
    if (tick !== null) {
      clearInterval(tick)
      tick = null
    }
    if (watch !== null) {
      clearInterval(watch)
      watch = null
    }
  }
  const settle = () => {
    const p = pending
    pending = null
    if (p) p()
  }

  tick = setInterval(() => {
    const word = queue.shift()
    if (word === undefined) return
    shown += word
    write(shown)
  }, tickMs)

  return {
    push(text: string) {
      if (!text) return
      // Each word carries its own trailing whitespace, so the queue can be
      // emptied one entry at a time with the spacing intact. Whitespace that
      // stands before the first word is an entry of its own.
      const lead = text.match(/^\s+/)
      if (lead) queue.push(lead[0])
      queue.push(...(text.match(/\S+\s*/g) || []))
    },
    finish(finalText?: string) {
      final = finalText
      return new Promise<void>((resolve) => {
        if (tick === null) {
          // Already flushed or given up: there is nothing left to wait for.
          resolve()
          return
        }
        pending = resolve
        if (watch !== null) clearInterval(watch)
        watch = setInterval(() => {
          if (queue.length) return
          clearTimers()
          // The queue is a display and a display can fall behind. What the
          // stream itself said is what the box ends up holding.
          if (final !== undefined && shown !== final) {
            shown = final
            write(shown)
          }
          settle()
        }, tickMs)
      })
    },
    flush() {
      if (tick === null && !queue.length) return
      clearTimers()
      if (queue.length) {
        shown += queue.join('')
        queue.length = 0
      }
      if (final !== undefined && shown !== final) shown = final
      write(shown)
      settle()
    },
    stop() {
      clearTimers()
      queue.length = 0
      settle()
    },
  }
}
