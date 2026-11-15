/**
 * The training page and the platform's checks.
 *
 * A handful of images the intake refuses leaves the set, and the block goes to
 * the safety window; what was staged before stays. A description the check at
 * the result withheld says so in its field. A start the intake refuses says
 * the platform's sentence for the block in the protocol, and reports the block.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'

const http = vi.hoisted(() => ({ post: vi.fn(), clientGet: vi.fn(), get: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ post: http.post, get: http.clientGet }), get: http.get, post: vi.fn() },
}))

import TrainingView from '../TrainingView.vue'
import ShellRun from '@/components/ShellRun.vue'
import { useSafetyEventStore } from '@/stores/safetyEvent'

const t = (key: string, named: Record<string, unknown> = {}) => i18n.global.t(key, named)

function picture(name: string): File {
  return new File([new Uint8Array([1, 2, 3])], name, { type: 'image/png' })
}

function item(file: string, caption: string | null, withheld = false) {
  return { file, caption, failed: false, withheld }
}

function refusal(block: Record<string, string>) {
  return Object.assign(new Error('Request failed with status code 403'), {
    response: { status: 403, data: { error: 'safety_blocked', safety_block: block } },
  })
}

let wrapper: VueWrapper | null = null

function mountView(): VueWrapper {
  const pinia = createPinia()
  setActivePinia(pinia)
  wrapper = mount(TrainingView, {
    global: { plugins: [i18n, pinia], stubs: { ShellRun: true, ColumnFold: true } },
  })
  return wrapper
}

/** Add files through the hidden input, as a click on the drop zone does. */
async function add(view: VueWrapper, files: File[]) {
  const input = view.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: files, configurable: true })
  await input.trigger('change')
  await flushPromises()
}

beforeEach(() => {
  http.post.mockReset()
  http.clientGet.mockReset()
  http.get.mockReset()
  http.get.mockResolvedValue({ data: {} })
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ json: () => Promise.resolve({}) })))
  Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:picture'), revokeObjectURL: vi.fn() })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('the training page and the checks', () => {
  it('lets a handful the intake refused leave the set and reports the block', async () => {
    const view = mountView()
    const block = { checkpoint: 'intake', reason_key: 'image_content', reason: '', field: 'images[1]' }
    http.post.mockRejectedValueOnce(refusal(block))
    await add(view, [picture('a.png'), picture('b.png')])

    expect(view.find('.drop-zone').text()).toBe(t('training.labels.dropZone'))
    expect(view.findAll('.caption-card')).toHaveLength(0)
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
    expect(useSafetyEventStore().pendingBlock?.block).toEqual(block)
    expect(useSafetyEventStore().pendingBlock?.operational).toBe(false)
  })

  it('keeps what was staged before when a later handful is refused', async () => {
    const view = mountView()
    const staged = [item('001.png', 'a red door')]
    http.post.mockResolvedValueOnce({ data: { token: 't1', running: false, items: staged } })
    http.get.mockResolvedValue({ data: { running: false, items: staged } })
    await add(view, [picture('a.png')])

    http.post.mockRejectedValueOnce(
      refusal({ checkpoint: 'intake', reason_key: 'image_content', reason: '', field: 'images[0]' }))
    await add(view, [picture('b.png')])

    expect((http.post.mock.calls[1]![1] as FormData).get('token')).toBe('t1')
    expect(view.findAll('.caption-card')).toHaveLength(1)
    expect((view.find('textarea').element as HTMLTextAreaElement).value).toBe('a red door')
    expect(view.find('.drop-zone').text()).toBe(t('training.labels.imagesSelected', { count: 1 }))
  })

  it('says in its field that the check withheld a description', async () => {
    const view = mountView()
    http.post.mockResolvedValueOnce({ data: { token: 't1', running: true, items: [item('001.png', null)] } })
    http.get.mockResolvedValue({ data: { running: false, items: [item('001.png', null, true)] } })
    await add(view, [picture('a.png')])

    const field = () => view.find('textarea')
    expect((field().element as HTMLTextAreaElement).placeholder).toBe(t('training.captions.waiting'))
    await new Promise((resolve) => setTimeout(resolve, 1700))
    await flushPromises()
    expect((field().element as HTMLTextAreaElement).placeholder).toBe(t('training.captions.withheld'))
    expect(field().classes()).not.toContain('caption-pending')
  })

  it('says a start the intake refused in the protocol and reports the block', async () => {
    const view = mountView()
    const items = ['001', '002', '003', '004', '005'].map((n) => item(`${n}.png`, 'a door'))
    http.post.mockResolvedValueOnce({ data: { token: 't1', running: false, items } })
    http.get.mockResolvedValue({ data: { running: false, items } })
    await add(view, ['a', 'b', 'c', 'd', 'e'].map((n) => picture(`${n}.png`)))
    await view.find('input.setting-input').setValue('Lisa Muster')

    const block = { checkpoint: 'intake', reason_key: 'personal_data', reason: '', field: 'project_name' }
    http.clientGet.mockResolvedValueOnce({ data: { can_train: true, total_gb: 96, used_gb: 0,
      free_gb: 96, usage_percent: 0, min_required_gb: 50, recommendation: null } })
    http.post.mockRejectedValueOnce(refusal(block))
    view.findComponent(ShellRun).vm.$emit('run')
    await flushPromises()
    await view.find('.proceed-btn').trigger('click')
    await flushPromises()

    const calls = http.post.mock.calls
    expect(calls[calls.length - 1]![0]).toBe('/api/training/start')
    const lines = view.findAll('.log-line').map((line) => line.text())
    expect(lines[lines.length - 1]).toBe(`Error: ${t('safetyBlocked.dsgvo')}`)
    expect(useSafetyEventStore().pendingBlock?.block).toEqual(block)
  })
})
