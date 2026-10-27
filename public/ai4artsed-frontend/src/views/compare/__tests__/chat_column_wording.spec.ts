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
 * The classification is read here from the source. What is held is that it
 * still hands all three endings to the "no response" path, and that a torn
 * connection is not among them: a column claiming a model said nothing, when
 * nothing ever reached the model, is the failure this must not trade for the
 * other.
 *
 * Since 2026-10-27 the turn of System Prompts and of Model Comparison
 * (Transformers Lab) is taken in one place, composables/useChatColumns.ts, and both
 * surfaces are held to taking it there. The language-model comparison
 * (llm_model_comparison.vue) is unrouted, marked deprecated on 2026-08-11 and
 * frozen, and still carries a turn of its own; the temperature comparison was
 * removed on 2026-10-10.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { en } from '../../../i18n/en'

const HERE = dirname(fileURLToPath(import.meta.url))

// Where a turn is taken, relative to views/compare.
const VIEWS = [
  'llm_model_comparison.vue',
  '../../composables/useChatColumns.ts',
]

// The surfaces that take their turns through the composable above.
const ROUND_SURFACES = [
  'system_prompt_comparison.vue',
  '../latent_lab/system_prompt_across_models.vue',
]

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

  for (const view of ROUND_SURFACES) {
    it(`${view} takes its turns through useChatColumns and nowhere else`, () => {
      const source = readFileSync(resolve(HERE, '..', view), 'utf8')
      expect(source).toContain('useChatColumns(store,')
      expect(source).not.toContain('chatTurn(')
    })
  }

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
