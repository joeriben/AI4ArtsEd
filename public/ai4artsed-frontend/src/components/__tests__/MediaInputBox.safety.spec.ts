/**
 * The text field's own check, at the field.
 *
 * Everything here was found by review rather than by a test, which is the point
 * of the file: the shared check has had tests since it was written, and every
 * .vue that CALLS it had none — so a fail-open could be put back at any call
 * site with all of them still green. There must be no fail-open checks.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import MediaInputBox from '../MediaInputBox.vue'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

/** The route's answer, in the transport this client speaks. */
function streamed(body: unknown): Response {
  const frames = [
    ': heartbeat\n\n',
    'event: complete\ndata: ' + JSON.stringify({ http_status: 200, body }) + '\n\n',
  ]
  const encoder = new TextEncoder()
  let i = 0
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: () => Promise.resolve(null),
    body: {
      getReader: () => ({
        read: () =>
          i < frames.length
            ? Promise.resolve({ done: false, value: encoder.encode(frames[i++]!) })
            : Promise.resolve({ done: true, value: undefined }),
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

function field(value = 'ein satz über ein haus') {
  return mount(MediaInputBox, {
    props: { value, inputType: 'text' },
    global: { plugins: [i18n] },
  })
}

describe('MediaInputBox — the text check at the field', () => {
  it('keeps what was written when no verdict came back', async () => {
    // The whole point of `operational`: the check could not be carried out, the
    // fault is this platform's, and the text says nothing about it. Deleting it
    // would tell the writer the opposite.
    fetchMock.mockResolvedValueOnce(streamed({ status: 'error', error: 'upstream gone' }))
    const w = field()
    await (w.vm as any).checkSafety()
    expect(w.emitted('update:value')).toBeUndefined()
    expect((w.vm as any).safetyResult).toMatchObject({ safe: false, operational: true })
    w.unmount()
  })

  it('says nothing on a blur that could not reach a verdict', async () => {
    // Every blur and every paste runs this check. While the route is down each
    // one would throw the same explanation over the field somebody is writing
    // in — the ways OUT of the box say it instead, when they are used.
    fetchMock.mockResolvedValueOnce(streamed({ status: 'error' }))
    const w = field()
    await (w.vm as any).checkSafety()
    expect(useSafetyEventStore().pendingBlock).toBeNull()
    w.unmount()
  })

  it('takes the text and states the reason when the check refused it', async () => {
    fetchMock.mockResolvedValueOnce(
      streamed({ safe: false, error_message: 'Kids-Filter: nicht freigegeben' })
    )
    const w = field()
    await (w.vm as any).checkSafety()
    expect(w.emitted('update:value')?.[0]).toEqual([''])
    const block = useSafetyEventStore().pendingBlock
    expect(block?.reason).toBe('Kids-Filter: nicht freigegeben')
    expect(block?.operational).toBe(false)
    w.unmount()
  })

  it('lets a verdict live only as long as the text it judged', async () => {
    // The tap that presses a button blurs the field first, so a verdict about
    // the previous text was one gesture away from standing for the next one —
    // in both directions: an edited line going out on the last one's pass, and
    // a fresh line reported as blocked because the line before it was.
    fetchMock.mockResolvedValueOnce(streamed({ safe: true, checks_passed: ['dsgvo_ner'] }))
    const w = field('ein haus')
    await (w.vm as any).checkSafety()
    expect((w.vm as any).safetyResult?.safe).toBe(true)
    await w.setProps({ value: 'etwas ganz anderes' })
    expect((w.vm as any).safetyResult).toBeNull()
    w.unmount()
  })

  it('translates only what the check has passed', async () => {
    // The translate route runs no check of its own, so this button is a way out
    // of the box. It asks for a verdict where none stands, and stops where the
    // answer holds the text back.
    fetchMock.mockResolvedValueOnce(
      streamed({ safe: false, error_message: 'Kids-Filter: nicht freigegeben' })
    )
    const w = field()
    await w.find('.translate-btn').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))
    const called = fetchMock.mock.calls.map(c => String(c[0]))
    expect(called.some(u => u.includes('/safety/quick'))).toBe(true)
    expect(called.some(u => u.includes('/pipeline/translate'))).toBe(false)
    w.unmount()
  })

  it('translates text the check passed', async () => {
    fetchMock
      .mockResolvedValueOnce(streamed({ safe: true, checks_passed: [] }))
      .mockResolvedValueOnce(streamed({ status: 'success', translated_text: 'a house' }))
    const w = field('ein haus')
    await w.find('.translate-btn').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(fetchMock.mock.calls.map(c => String(c[0])).some(u => u.includes('/pipeline/translate')))
      .toBe(true)
    w.unmount()
  })
})
