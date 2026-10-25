/**
 * What a failed column of a comparison surface says.
 *
 * The view puts one question to three models at once and shows each answer in
 * its own column. While it called the blocking `/api/chat`, three endings
 * arrived as a body with no `reply` in it and the column read "No response
 * received": a turn the server itself ended, a request it refused before
 * answering, and an answer that came back unreadable. Moved onto the stream on
 * 2026-09-04, two of those three became a thrown error and the column read
 * "Connection error" instead — a different thing said to a room about a model
 * that had in fact been asked and had in fact not answered.
 *
 * The classification lives inside a `<script setup>` block and cannot be
 * imported, so it is read here from the source. What is held is that the view
 * still hands all three endings to the "no response" path, and that a torn
 * connection is not among them: a column claiming a model said nothing, when
 * nothing ever reached the model, is the failure this must not trade for the
 * other. (The two sister views that shared this logic, the language-model and
 * the temperature comparison, were removed on 2026-10-10 as unrouted.)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { en } from '../../../i18n/en'

const HERE = dirname(fileURLToPath(import.meta.url))

const VIEWS = ['llm_model_comparison.vue', 'system_prompt_comparison.vue']

/** The `catch` block of the view's own chat call, source and all. */
function chatCatch(source: string): string {
  const start = source.indexOf('await chatTurn(')
  expect(start, 'the view takes its turn through chatTurn').toBeGreaterThan(-1)
  const from = source.indexOf('} catch (e) {', start)
  expect(from, 'that call has a catch of its own').toBeGreaterThan(-1)
  return source.slice(from, source.indexOf('\n}', from))
}

describe('the two words a comparison column has for a column that failed', () => {
  it('are both in en.ts, under the names the views use', () => {
    expect(en.compare.shared.noResponse).toBeTruthy()
    expect(en.compare.shared.error).toBeTruthy()
    expect(en.compare.shared.noResponse).not.toBe(en.compare.shared.error)
  })

  for (const view of VIEWS) {
    describe(view, () => {
      const source = readFileSync(resolve(HERE, '..', view), 'utf8')

      it('reads all three endings as "no response"', () => {
        const block = chatCatch(source)
        // The turn the server ended inside the stream.
        expect(block).toContain('ChatStreamError')
        // The stream that was refused before it opened — a non-2xx, which is
        // exactly what the blocking endpoint answered with.
        expect(block).toContain('SseHttpError')
        // The turn that ended without a terminal event.
        expect(block).toContain('ChatNoReplyError')
        // All three leave through the same door: a null reply, which the caller
        // shows as compare.shared.noResponse.
        expect(block).toContain('return null')
      })

      it('lets everything else through to the error branch', () => {
        // A torn connection and an abort are not endings of a turn, and the
        // column must keep saying so.
        expect(chatCatch(source)).toContain('throw e')
      })

      it('still shows the two wordings where they belong', () => {
        expect(source).toContain("t('compare.shared.noResponse')")
        expect(source).toContain("t('compare.shared.error')")
      })
    })
  }
})
