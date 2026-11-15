/**
 * A recording the platform's check refuses where it comes in
 * (latent_lab_recorder_routes, 2026-10-31): nothing is written, and the
 * safety window says why — of a refused picture, as one the platform made.
 */
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    isAxiosError: (e: unknown) => !!(e as { isAxiosError?: boolean } | null)?.isAxiosError,
  },
}))

import axios from 'axios'
import { useLatentLabRecorder, type RecordData } from '../useLatentLabRecorder'
import { safetyBlockKeyForEvent } from '../useGenerationStream'
import { useSafetyEventStore } from '@/stores/safetyEvent'

const post = axios.post as unknown as Mock

const RUN: RecordData = {
  parameters: { prompt: 'a lighthouse' },
  outputs: [{ type: 'image', format: 'png', dataBase64: 'AAAA' }],
}

function answered(status: number, data: unknown) {
  return Object.assign(new Error(`status ${status}`), { isAxiosError: true, response: { status, data } })
}

function refused(reason_key: string, field: string) {
  return answered(403, {
    error: 'safety_blocked',
    safety_block: { checkpoint: 'intake', field, reason_key, reason: 'ein deutscher Satz' },
  })
}

const sitting = (id: string) => ({ data: { session_id: id } })

function recorder() {
  let rec!: ReturnType<typeof useLatentLabRecorder>
  mount(defineComponent({
    setup() {
      rec = useLatentLabRecorder('composable_diffusion')
      return () => null
    },
  }))
  return rec
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  post.mockReset()
  setActivePinia(createPinia())
  vi.spyOn(console, 'warn').mockImplementation(() => {})
})

describe('a recording the check refuses', () => {
  it('writes no run and says a refused picture as one the platform made', async () => {
    post.mockResolvedValueOnce(sitting('lab_1')).mockRejectedValueOnce(refused('image_content', 'outputs[0]'))
    expect(await recorder().record(RUN)).toBeNull()
    const event = useSafetyEventStore().consume()
    expect(event?.block?.field).toBe('outputs[0]')
    expect(safetyBlockKeyForEvent(event!)).toBe('safetyBlocked.vlm')
    // Refused is not lost: the sitting is not opened again, and the run is not
    // sent a second time.
    expect(post).toHaveBeenCalledTimes(2)
  })

  it('says a name as a name', async () => {
    post.mockResolvedValueOnce(sitting('lab_1')).mockRejectedValueOnce(refused('personal_data', 'parameters[prompt]'))
    expect(await recorder().record(RUN)).toBeNull()
    expect(safetyBlockKeyForEvent(useSafetyEventStore().consume()!)).toBe('safetyBlocked.dsgvo')
  })

  it('says a check that could not run as the fault it is', async () => {
    post.mockResolvedValueOnce(sitting('lab_1')).mockRejectedValueOnce(refused('unavailable', 'outputs[0]'))
    expect(await recorder().record(RUN)).toBeNull()
    const event = useSafetyEventStore().consume()
    expect(event?.operational).toBe(true)
    expect(safetyBlockKeyForEvent(event!)).toBe('safetyBlocked.systemUnavailable')
  })

  it('is reported where the sitting had to be opened again first', async () => {
    post
      .mockResolvedValueOnce(sitting('lab_1'))
      .mockRejectedValueOnce(answered(404, { error: 'No open session: lab_1' }))
      .mockResolvedValueOnce(sitting('lab_2'))
      .mockRejectedValueOnce(refused('image_content', 'outputs[0]'))
    expect(await recorder().record(RUN)).toBeNull()
    expect(safetyBlockKeyForEvent(useSafetyEventStore().consume()!)).toBe('safetyBlocked.vlm')
    expect(post).toHaveBeenCalledTimes(4)
  })

  it('reports nothing where the write failed for another reason', async () => {
    post.mockResolvedValueOnce(sitting('lab_1')).mockRejectedValueOnce(answered(500, { error: 'disk full' }))
    expect(await recorder().record(RUN)).toBeNull()
    expect(useSafetyEventStore().consume()).toBeNull()
  })

  it('hands back the run of a recording that passes', async () => {
    post.mockResolvedValueOnce(sitting('lab_1')).mockResolvedValueOnce({ data: { run_id: 'run_1' } })
    expect(await recorder().record(RUN)).toBe('run_1')
    expect(useSafetyEventStore().consume()).toBeNull()
  })
})
