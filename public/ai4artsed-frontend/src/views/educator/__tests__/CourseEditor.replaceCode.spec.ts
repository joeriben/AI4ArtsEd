/**
 * The leader's yes before the code of a place is replaced
 * (views/educator/CourseEditor.vue, 2026-09-24).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'

const { api } = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    palette: vi.fn(),
    availablePresets: vi.fn(),
    replacePlaceCode: vi.fn(),
    addPlaces: vi.fn(),
    deletionImpact: vi.fn(),
  },
}))
vi.mock('@/services/labApi', () => ({ coursesApi: api }))
vi.mock('@/stores/keptPerspectives', () => ({
  useKeptPerspectivesStore: () => ({ items: [], byId: () => undefined, load: async () => {} }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

import i18n from '@/i18n'
import CourseEditor from '../CourseEditor.vue'

const issuedAt = '2026-09-24T13:23:00Z'
const course = () => ({
  id: 1, name: 'Viewing course', description: '', safety_level: 'kids',
  educator_can_view_participant_works: false, archived: false, educators: [],
  place_count: 3, access_until: null, access_open: false,
  places: [
    { number: 1, has_code: true, code_issued_at: issuedAt },
    { number: 2, has_code: true, code_issued_at: issuedAt },
    { number: 3, has_code: false, code_issued_at: null },
  ],
})
const issued = (number: number) => ({
  data: { place: { number, code: 'KMNPQ', has_code: true, code_issued_at: issuedAt } },
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => { resolve = r })
  return { promise, resolve }
}

let wrapper: VueWrapper | undefined
const row = () => document.body.querySelector('.action-confirm-row')
const rowButtons = () => [...document.body.querySelectorAll<HTMLButtonElement>('.action-confirm-row button')]
const listButton = (n: number) => wrapper!.findAll('ul.place-rows li')[n - 1]!.find('button')

async function mounted() {
  wrapper = mount(CourseEditor, { global: { plugins: [i18n], stubs: { RouterLink: true } } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  for (const f of Object.values(api)) f.mockReset()
  api.get.mockResolvedValue({ data: { course: course() } })
  api.palette.mockResolvedValue({ data: { palette: [] } })
  api.availablePresets.mockResolvedValue({ data: { presets: [] } })
  i18n.global.locale.value = 'en'
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('CourseEditor: replacing the code of a place', () => {
  it('asks first, and replaces the code at the yes', async () => {
    await mounted()
    await listButton(2).trigger('click')
    expect(api.replacePlaceCode).not.toHaveBeenCalled()
    expect(row()?.textContent).toContain(
      'Place 2 gets a new code. A device signed in with the old one is signed out.',
    )
    const [yes, cancel] = rowButtons()
    expect(yes!.textContent?.trim()).toBe('Replace code')
    expect(yes!.classList.contains('danger')).toBe(true)
    expect(cancel!.textContent?.trim()).toBe('Cancel')
    api.replacePlaceCode.mockResolvedValueOnce(issued(2))
    yes!.click()
    await flushPromises()
    expect(api.replacePlaceCode).toHaveBeenCalledWith(1, 2)
    expect(row()).toBeNull()
    expect(wrapper!.text()).toContain('KMNPQ')
  })

  it('"Cancel" replaces nothing', async () => {
    await mounted()
    await listButton(1).trigger('click')
    rowButtons()[1]!.click()
    await flushPromises()
    expect(row()).toBeNull()
    expect(api.replacePlaceCode).not.toHaveBeenCalled()
  })

  it('gives a place without a code its first at once', async () => {
    await mounted()
    api.replacePlaceCode.mockResolvedValueOnce(issued(3))
    await listButton(3).trigger('click')
    await flushPromises()
    expect(api.replacePlaceCode).toHaveBeenCalledWith(1, 3)
    expect(row()).toBeNull()
  })

  it('holds the yes back while another change of the places is under way', async () => {
    await mounted()
    await listButton(2).trigger('click')
    api.addPlaces.mockReturnValueOnce(new Promise(() => {}))
    const makeCodes = wrapper!.findAll('button').find((b) => b.text() === 'Generate codes')!
    await makeCodes.trigger('click')
    expect(rowButtons()[0]!.disabled).toBe(true)
  })

  it('the delete dialog takes the row away, and the list asks nothing behind it', async () => {
    await mounted()
    await listButton(2).trigger('click')
    expect(row()).not.toBeNull()
    const impact = deferred<{ data: { impact: object } }>()
    api.deletionImpact.mockReturnValueOnce(impact.promise)
    await wrapper!.find('.danger-zone button.danger').trigger('click')
    expect(row()).toBeNull()
    await listButton(1).trigger('click')         // while the impact is read
    expect(row()).not.toBeNull()
    impact.resolve({ data: { impact: { places: 3, course_works: 0, course_custom_prompts: 0 } } })
    await flushPromises()
    expect(wrapper!.find('.modal').exists()).toBe(true)
    expect(row()).toBeNull()
    await listButton(1).trigger('click')         // behind the open dialog
    await listButton(3).trigger('click')
    await flushPromises()
    expect(row()).toBeNull()
    expect(api.replacePlaceCode).not.toHaveBeenCalled()
  })
})
