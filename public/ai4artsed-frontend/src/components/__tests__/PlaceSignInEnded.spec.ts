/**
 * The row over every page when the sign-in of this device's place has ended
 * (components/PlaceSignInEnded.vue, 2026-09-24).
 */
import { describe, it, expect, beforeEach, afterEach, vi, type Mock } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/stores/safetyLevel', () => ({
  useSafetyLevelStore: () => ({ fetchLevel: vi.fn(async () => {}) }),
}))
vi.mock('@/composables/useCrossmodalPicture', () => ({ clearCrossmodalPicture: vi.fn() }))
const { push } = vi.hoisted(() => ({ push: vi.fn(async () => {}) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

import axios from 'axios'
import i18n from '@/i18n'
import appSource from '@/App.vue?raw'
import { useLabAuthStore } from '@/stores/labAuth'
import PlaceSignInEnded from '../PlaceSignInEnded.vue'

const get = axios.get as unknown as Mock
const post = axios.post as unknown as Mock
const participant = {
  id: 7, role: 'participant', display_name: '', identifier: '', locale: 'en', is_active: true,
}
const signedOut = { data: { user: null, course_id: null, place: null } }

let wrapper: VueWrapper | undefined
const row = () => document.body.querySelector('.action-confirm-row')
const buttons = () => [...document.body.querySelectorAll<HTMLButtonElement>('.action-confirm-row button')]

Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' })

beforeEach(() => {
  localStorage.clear()
  get.mockReset()
  post.mockReset()
  push.mockClear()
  setActivePinia(createPinia())
  i18n.global.locale.value = 'en'
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

/** A device at place `n`, with the row mounted over its page. */
async function atPlace(n: number) {
  post.mockResolvedValueOnce({ data: { user: participant, course: { id: 4 }, place: n } })
  const auth = useLabAuthStore()
  await auth.participantLogin('ACDEF')
  wrapper = mount(PlaceSignInEnded, { global: { plugins: [i18n] } })
  return auth
}

/** The window comes back to the front, and the server has ended the sign-in. */
async function ended() {
  get.mockResolvedValueOnce(signedOut)
  window.dispatchEvent(new Event('focus'))
  await flushPromises()
  await nextTick()
}

describe('PlaceSignInEnded', () => {
  it('App.vue shows it on every page', () => {
    expect(appSource).toMatch(/<PlaceSignInEnded\s*\/>/)
  })

  it('shows nothing while the sign-in holds', async () => {
    await atPlace(3)
    get.mockResolvedValueOnce({ data: { user: participant, course_id: 4, place: 3 } })
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
    expect(row()).toBeNull()
  })

  it('says which place ended, over the page, with "Sign in" and "Close"', async () => {
    await atPlace(3)
    await ended()
    expect(row()?.parentElement).toBe(document.body)
    expect(row()?.textContent).toContain('The sign-in of place 3 has ended.')
    expect(buttons().map((b) => b.textContent?.trim())).toEqual(['Sign in', 'Close'])
  })

  it('"Close" takes the row away and leaves the page as it is', async () => {
    const auth = await atPlace(3)
    await ended()
    buttons()[1]!.click()
    await nextTick()
    expect(row()).toBeNull()
    expect(auth.user).toEqual(participant)
    expect(push).not.toHaveBeenCalled()
  })

  it('"Sign in" takes over what the server says and opens the login', async () => {
    const auth = await atPlace(3)
    await ended()
    get.mockResolvedValueOnce(signedOut)
    buttons()[0]!.click()
    await flushPromises()
    expect(push).toHaveBeenCalledWith({ name: 'login' })
    expect(auth.user).toBeNull()
    expect(row()).toBeNull()
  })
})
