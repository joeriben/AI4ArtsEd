/**
 * A picture read into a template line whose reading the platform's checks
 * refused: the picture has no pass for the level of whoever asks, or what was
 * read of it was withheld at the result. The route answers 403 with the block
 * message (devserver/my_app/routes/media_routes.py), and the line says the
 * refusal, which also goes to the safety window, instead of a reading that
 * failed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

let answer: { status: number; data: unknown } = { status: 200, data: {} }

vi.mock('@/services/directRun', () => ({
  postStreamedRun: vi.fn(async () => answer),
}))
vi.mock('@/services/labApi', () => ({ apiBase: () => '' }))
vi.mock('vue-i18n', async (importOriginal) => {
  const { ref: aRef } = await import('vue')
  return {
    ...(await importOriginal<typeof import('vue-i18n')>()),
    useI18n: () => ({ locale: aRef('de'), t: (key: string) => key }),
  }
})

import { usePictureTemplate } from '../usePictureTemplate'
import { useSafetyEventStore } from '@/stores/safetyEvent'

function refused(checkpoint: string, reason_key: string) {
  return {
    status: 403,
    data: {
      error: 'safety_blocked',
      safety_block: { checkpoint, field: 'analysis', reason_key, reason: '' },
    },
  }
}

async function read() {
  const line = ref('')
  let template!: ReturnType<typeof usePictureTemplate>
  mount(defineComponent({
    setup() {
      template = usePictureTemplate(line)
      return () => null
    },
  }))
  template.handlePicture({ image_path: '/uploads/a.png', preview_url: 'blob:a' })
  await vi.waitFor(() => expect(template.reading.value).toBe(false))
  return { line, template }
}

describe('a picture read into a template line', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('says a refused reading as the refusal and sends it to the safety window', async () => {
    answer = refused('result', 'content')
    const { line, template } = await read()
    expect(template.readingFailedKey.value).toBe('safetyBlocked.generic')
    expect(line.value).toBe('')
    const event = useSafetyEventStore().consume()
    expect(event?.block?.checkpoint).toBe('result')
    expect(event?.operational).toBe(false)
  })

  it('says a check that could not be carried out as the fault it is', async () => {
    answer = refused('before_model', 'unavailable')
    const { template } = await read()
    expect(template.readingFailedKey.value).toBe('safetyBlocked.systemUnavailable')
    expect(useSafetyEventStore().consume()?.operational).toBe(true)
  })

  it('still says a reading that did not come back as that', async () => {
    answer = { status: 502, data: { error: 'Image analysis failed' } }
    const { template } = await read()
    expect(template.readingFailedKey.value).toBe('latentLab.interception.models.readingFailed')
    expect(useSafetyEventStore().consume()).toBeNull()
  })

  it('puts a reading that passed into the line', async () => {
    answer = { status: 200, data: { success: true, analysis: 'a house' } }
    const { line, template } = await read()
    expect(line.value).toBe('a house')
    expect(template.readingFailedKey.value).toBe('')
  })
})
