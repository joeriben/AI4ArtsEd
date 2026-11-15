/**
 * What a block event carries, and what the window makes of it.
 *
 * A surface reports the server's block message, and the window says the
 * sentence its `reason_key` names; the reason in it is never rendered. What a
 * block message cannot carry is a surface's own check that did not run at all —
 * there is no message then. That travels as a fact of the event instead, and
 * these hold that shape in place: the default, the flag, and the one reader
 * that has to look at it. There are no fail-open checks.
 */
import { describe, it, expect, beforeEach } from 'vitest'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — vite hands a file's own text back under ?raw
import overlaySource from '../../components/ChatOverlay.vue?raw'
import { setActivePinia, createPinia } from 'pinia'
import { useSafetyEventStore } from '../safetyEvent'
import { safetyBlockKeyForEvent, type SafetyBlock } from '../../composables/useGenerationStream'

const REFUSED_NAME: SafetyBlock = {
  checkpoint: 'intake', field: 'text', reason_key: 'personal_data', reason: 'DSGVO: Max Muster',
}

describe('safetyEvent store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('carries no operational claim unless one is made', () => {
    const store = useSafetyEventStore()
    store.reportBlock(REFUSED_NAME)
    expect(store.pendingBlock?.operational).toBe(false)
    expect(safetyBlockKeyForEvent(store.consume()!)).toBe('safetyBlocked.dsgvo')
  })

  it('carries the check that could not run, through to the sentence', () => {
    const store = useSafetyEventStore()
    // What every surface passes when its own check failed: no block message,
    // because there is none — nothing judged anything.
    store.reportBlock(null, { operational: true })
    const event = store.consume()!
    expect(event.block).toBeNull()
    expect(event.operational).toBe(true)
    expect(safetyBlockKeyForEvent(event)).toBe('safetyBlocked.systemUnavailable')
  })

  it('keeps the description a picture check sends with a content refusal', () => {
    const store = useSafetyEventStore()
    store.reportBlock(
      { checkpoint: 'intake', field: 'image', reason_key: 'image_content', reason: 'nicht freigegeben' },
      { vlmDescription: 'a weapon' },
    )
    const event = store.consume()!
    expect(event.vlmDescription).toBe('a weapon')
    expect(event.operational).toBe(false)
    expect(safetyBlockKeyForEvent(event)).toBe('safetyBlocked.inputImage')
  })

  it('reads the server\'s fault as the fault it is, whatever its wording', () => {
    // The server says a check could not run under the key `unavailable`,
    // beside a German sentence that may wear any prefix, a DSGVO one included.
    // A technical fault must never read as a rating of what someone made.
    const store = useSafetyEventStore()
    store.reportBlock({
      checkpoint: 'intake', field: 'text', reason_key: 'unavailable',
      reason: 'DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte GPU Service neustarten.',
    })
    expect(safetyBlockKeyForEvent(store.consume()!)).toBe('safetyBlocked.systemUnavailable')
  })

  it('is read by the window through the event, not through the reason', () => {
    // The one consumer of pendingBlock. Read from the source, because mounting
    // that component would test the mount and not this: what has to hold is
    // that it reads the EVENT, its block message and its flag — a reading of
    // the reason there would silently turn every fault back into a rating.
    expect(overlaySource).toContain('safetyBlockKeyForEvent')
    expect(overlaySource).toContain('block: event.block')
    expect(overlaySource).toContain('operational: event.operational')
  })
})
