/**
 * Which sentence a blocked run gets — the half the surfaces do not see.
 *
 * The block a surface reports is CLASSIFIED, never rendered: the window runs
 * `safetyBlockKeyForEvent` over it and shows the key that comes back. So a
 * surface that holds material back because the check could not run has to be
 * able to say so as a FACT of the event; a sentence cannot carry it, because
 * the matcher reads German markers the backend writes and no client string is
 * one of them. This was found before it reached anyone: the first version of
 * the fail-closed change passed the translated operational sentence as the
 * reason, and every one of its six sites classified to „your picture was rated
 * unsuitable". There are no fail-open checks.
 */
import { describe, it, expect } from 'vitest'
import { safetyBlockKey, safetyBlockKeyForEvent } from '../useGenerationStream'

describe('safetyBlockKeyForEvent', () => {
  it('says the check did not run, whatever the stage and whatever the reason', () => {
    expect(safetyBlockKeyForEvent({ operational: true, stage: 'vlm_input', reason: '' }))
      .toBe('safetyBlocked.systemUnavailable')
    expect(safetyBlockKeyForEvent({ operational: true, stage: 1, reason: '' }))
      .toBe('safetyBlocked.systemUnavailable')
    // A rating that arrived would be a rating; the marker is not overridden by
    // wording that happens to travel with it.
    expect(safetyBlockKeyForEvent({ operational: true, stage: 'vlm_input', reason: 'Kids-Filter' }))
      .toBe('safetyBlocked.systemUnavailable')
  })

  it('leaves every other block to the reading the platform already had', () => {
    expect(safetyBlockKeyForEvent({ stage: 'vlm_input', reason: 'was auch immer' }))
      .toBe('safetyBlocked.inputImage')
    expect(safetyBlockKeyForEvent({ stage: 1, reason: 'DSGVO' })).toBe('safetyBlocked.dsgvo')
    expect(safetyBlockKeyForEvent({ stage: 1, reason: '' })).toBe('safetyBlocked.generic')
  })

  it('keeps reading the backend\'s own German operational marker', () => {
    // The server states this one in words and has done since the wording
    // existed; the flag is the client's way of saying the same thing.
    expect(safetyBlockKey('⚠️ Technische Störung bei der Bildprüfung', 'vlm_input'))
      .toBe('safetyBlocked.systemUnavailable')
    expect(safetyBlockKeyForEvent({ stage: 'vlm_input', reason: '⚠️ Technische Störung' }))
      .toBe('safetyBlocked.systemUnavailable')
  })

  it('does not read a translated sentence as a rating, because it never sees one', () => {
    // The en/de strings of `safetyBlocked.systemUnavailable`, which the first
    // version of the change passed as the reason. Both classify as a content
    // rating — which is why the case travels as a flag now.
    const en = 'The safety check could not be completed because of a technical fault.'
    expect(safetyBlockKey(en, 'vlm_input')).toBe('safetyBlocked.inputImage')
    expect(safetyBlockKeyForEvent({ stage: 'vlm_input', reason: en, operational: true }))
      .toBe('safetyBlocked.systemUnavailable')
  })
})
