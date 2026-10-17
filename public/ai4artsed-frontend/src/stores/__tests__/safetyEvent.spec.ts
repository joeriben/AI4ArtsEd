/**
 * What a block event carries, and what the window makes of it.
 *
 * The reason a surface reports is CLASSIFIED and never rendered, so the one
 * thing a surface cannot say in words is „the check did not run at all" — a
 * client sentence belongs to no language the matcher reads, and every site that
 * tried it classified as a rating of the picture. It travels as a fact of the
 * event instead, and these hold that shape in place: the default, the flag, and
 * the one reader that has to look at it. There are no fail-open checks.
 */
import { describe, it, expect, beforeEach } from 'vitest'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — vite hands a file's own text back under ?raw
import overlaySource from '../../components/ChatOverlay.vue?raw'
import { setActivePinia, createPinia } from 'pinia'
import { useSafetyEventStore } from '../safetyEvent'
import { safetyBlockKeyForEvent, safetyBlockKey } from '../../composables/useGenerationStream'

describe('safetyEvent store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('carries no operational claim unless one is made', () => {
    const store = useSafetyEventStore()
    store.reportBlock(1, 'Kids-Filter: nicht freigegeben')
    expect(store.pendingBlock?.operational).toBe(false)
    expect(safetyBlockKeyForEvent(store.consume()!)).toBe('safetyBlocked.kids')
  })

  it('carries the check that could not run, through to the sentence', () => {
    const store = useSafetyEventStore()
    // What every surface passes when its own check failed: no reason at all,
    // because there is none — nothing judged anything.
    store.reportBlock('vlm_input', '', [], undefined, true)
    const event = store.consume()!
    expect(event.operational).toBe(true)
    expect(safetyBlockKeyForEvent(event)).toBe('safetyBlocked.systemUnavailable')
  })

  it('keeps the description a picture check sends with a content refusal', () => {
    const store = useSafetyEventStore()
    store.reportBlock('vlm_input', 'nicht freigegeben', [], 'a weapon')
    const event = store.consume()!
    expect(event.vlmDescription).toBe('a weapon')
    expect(event.operational).toBe(false)
  })

  it('reads the backend\'s own unavailable wordings as the fault they are', () => {
    // These reach the window as German sentences from the server, so the
    // classifier has to know them: a technical fault must never read as a
    // rating of what someone made.
    expect(safetyBlockKey('⚠️ Technische Störung bei der Bildprüfung', 'vlm_input'))
      .toBe('safetyBlocked.systemUnavailable')
    expect(safetyBlockKey('Sicherheitssystem-Fehler', 1)).toBe('safetyBlocked.systemUnavailable')
    expect(safetyBlockKey('DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte GPU Service neustarten.', 1))
      .toBe('safetyBlocked.systemUnavailable')
    // A real name finding keeps its own sentence.
    expect(safetyBlockKey('DSGVO: Persönliche Daten erkannt', 1)).toBe('safetyBlocked.dsgvo')
  })

  it('is read by the window through the event, not through the reason', () => {
    // The one consumer of pendingBlock. Read from the source, because mounting
    // that component would test the mount and not this: what has to hold is
    // that it classifies the EVENT — going back to `safetyBlockKey(reason)`
    // there would silently turn every fault back into a rating.
    expect(overlaySource).toContain('safetyBlockKeyForEvent')
    expect(overlaySource).toContain('operational: event.operational')
  })
})
