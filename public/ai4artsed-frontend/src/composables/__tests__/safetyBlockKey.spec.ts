/**
 * Which sentence a blocked run gets — the half the surfaces do not see.
 *
 * The block a surface reports is READ, never rendered: the window runs
 * `safetyBlockKeyForEvent` over it and shows the key that comes back. The key
 * comes from the block message the server sends (`safety_block`), by its
 * `reason_key`; the reason in it is German and is never shown. A surface that
 * holds material back because its own check could not run has no block
 * message to pass, and says so as a FACT of the event (`operational`). This
 * was found before it reached anyone: the first version of the fail-closed
 * change passed the translated operational sentence as the reason, and every
 * one of its six sites classified to „your picture was rated unsuitable".
 * There are no fail-open checks.
 */
import { describe, it, expect } from 'vitest'
import {
  safetyBlockKeyForEvent,
  safetyBlockMessageKey,
  safetyBlockOf,
  type SafetyBlock,
} from '../useGenerationStream'

function block(reason_key: string, checkpoint = 'intake', field = ''): SafetyBlock {
  return { checkpoint, field, reason_key, reason: 'ein deutscher Satz' }
}

describe('safetyBlockMessageKey', () => {
  it('says each kind of block in its own sentence', () => {
    expect(safetyBlockMessageKey(block('unavailable'))).toBe('safetyBlocked.systemUnavailable')
    expect(safetyBlockMessageKey(block('symbol', 'before_model'))).toBe('safetyBlocked.para86a')
    expect(safetyBlockMessageKey(block('personal_data'))).toBe('safetyBlocked.dsgvo')
    for (const key of ['content', 'code', 'refusal', 'image_unchecked', '', 'a key not known yet']) {
      expect(safetyBlockMessageKey(block(key, 'before_model'))).toBe('safetyBlocked.generic')
    }
  })

  it('tells a picture the platform made from one it was given', () => {
    // Read as anything else, a picture the platform refused reads as a refused
    // prompt, and the reader is told to reword what was never the subject.
    expect(safetyBlockMessageKey(block('image_content', 'result', 'image'))).toBe('safetyBlocked.vlm')
    expect(safetyBlockMessageKey(block('image_content', 'intake', 'image'))).toBe('safetyBlocked.inputImage')
  })

  it('says a refused video as a video', () => {
    // Only the check at the result looks at a video, so a refused one is one
    // the platform made, and the sentence must not call it a picture.
    expect(safetyBlockMessageKey(block('video_content', 'result', 'video'))).toBe('safetyBlocked.video')
    expect(safetyBlockKeyForEvent({ block: block('video_content', 'result', 'video') }))
      .toBe('safetyBlocked.video')
    expect(safetyBlockKeyForEvent({ block: block('video_content', 'result', 'video'), generated: true }))
      .toBe('safetyBlocked.video')
  })

  it('never reads a fault as a rating, wherever it stopped', () => {
    for (const checkpoint of ['intake', 'before_model', 'result']) {
      expect(safetyBlockMessageKey(block('unavailable', checkpoint, 'image')))
        .toBe('safetyBlocked.systemUnavailable')
    }
  })
})

describe('safetyBlockKeyForEvent', () => {
  it('says the check did not run, whatever block travels with it', () => {
    expect(safetyBlockKeyForEvent({ operational: true })).toBe('safetyBlocked.systemUnavailable')
    expect(safetyBlockKeyForEvent({ block: null, operational: true }))
      .toBe('safetyBlocked.systemUnavailable')
    // The surface's own word that its check could not run is not overridden by
    // a block message beside it.
    expect(safetyBlockKeyForEvent({ block: block('personal_data'), operational: true }))
      .toBe('safetyBlocked.systemUnavailable')
  })

  it('reads every other block by its message', () => {
    expect(safetyBlockKeyForEvent({ block: block('image_content', 'intake', 'image') }))
      .toBe('safetyBlocked.inputImage')
    expect(safetyBlockKeyForEvent({ block: block('personal_data') })).toBe('safetyBlocked.dsgvo')
    expect(safetyBlockKeyForEvent({ block: null })).toBe('safetyBlocked.generic')
    expect(safetyBlockKeyForEvent({})).toBe('safetyBlocked.generic')
  })

  it('says a picture the platform made as made, wherever it was refused', () => {
    // A Latent Lab instrument hands its own pictures back when it records a
    // run, and the check where material comes in refuses them there.
    const made = block('image_content', 'intake', 'outputs[0]')
    expect(safetyBlockKeyForEvent({ block: made, generated: true })).toBe('safetyBlocked.vlm')
    expect(safetyBlockKeyForEvent({ block: made, generated: false })).toBe('safetyBlocked.inputImage')
    // It changes the sentence of a refused picture and of nothing else.
    expect(safetyBlockKeyForEvent({ block: block('personal_data', 'intake', 'parameters[prompt]'), generated: true }))
      .toBe('safetyBlocked.dsgvo')
    expect(safetyBlockKeyForEvent({ block: block('unavailable', 'intake', 'outputs[0]'), generated: true }))
      .toBe('safetyBlocked.systemUnavailable')
    expect(safetyBlockKeyForEvent({ block: made, operational: true, generated: true }))
      .toBe('safetyBlocked.systemUnavailable')
  })

  it('never looks at the wording', () => {
    // The en sentence of `safetyBlocked.systemUnavailable`, which the first
    // version of the fail-closed change passed as the reason, and one of the
    // server's own German ones: the key decides, the words decide nothing.
    const en = 'The safety check could not be completed because of a technical fault.'
    expect(safetyBlockKeyForEvent({ block: { ...block('content'), reason: en } }))
      .toBe('safetyBlocked.generic')
    expect(safetyBlockKeyForEvent({ block: { ...block('image_content'), reason: '⚠️ Technische Störung' } }))
      .toBe('safetyBlocked.inputImage')
  })
})

describe('safetyBlockOf', () => {
  it('reads the block message off a body, an event and an axios error', () => {
    const b = block('symbol', 'intake', 'input_text')
    expect(safetyBlockOf({ status: 'blocked', safety_block: b })).toEqual(b)
    expect(safetyBlockOf({ response: { data: { success: false, safety_block: b } } })).toEqual(b)
  })

  it('finds none where the answer carries no block message', () => {
    expect(safetyBlockOf(null)).toBeNull()
    expect(safetyBlockOf({ status: 'success' })).toBeNull()
    expect(safetyBlockOf({ status: 'blocked', reason: 'gesperrt' })).toBeNull()
    expect(safetyBlockOf({ safety_block: 'gesperrt' })).toBeNull()
  })
})
