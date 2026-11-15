/**
 * A refusal of the platform's checks on a Crossmodal Lab instrument: the route
 * answers 403 with the block message (devserver/my_app/routes/
 * cross_aesthetic_routes.py), and the instrument sends it to the safety window
 * and says it on its own line.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { refusalKeyOf, reportRefusal } from '../useLabRun'
import { useSafetyEventStore } from '@/stores/safetyEvent'

function answered(status: number, data: unknown) {
  return Object.assign(new Error(`status ${status}`), { response: { status, data } })
}

function refused(reason_key: string) {
  return answered(403, {
    success: false,
    error: 'safety_blocked',
    safety_block: { checkpoint: 'before_model', field: 'prompt', reason_key, reason: 'ein Satz' },
  })
}

describe('reportRefusal', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('sends a refusal to the safety window and hands back its block message', () => {
    const block = reportRefusal(refused('content'))
    expect(block?.checkpoint).toBe('before_model')
    const event = useSafetyEventStore().consume()
    expect(event?.block?.reason_key).toBe('content')
    expect(event?.operational).toBe(false)
    expect(refusalKeyOf(refused('content'))).toBe('safetyBlocked.generic')
  })

  it('says a check that could not be carried out as the fault it is', () => {
    reportRefusal(refused('unavailable'))
    expect(useSafetyEventStore().consume()?.operational).toBe(true)
  })

  it('sends nothing for a failure that is no refusal', () => {
    expect(reportRefusal(answered(503, { success: false, error: 'busy' }))).toBeNull()
    expect(reportRefusal('a sentence')).toBeNull()
    expect(useSafetyEventStore().consume()).toBeNull()
  })
})
