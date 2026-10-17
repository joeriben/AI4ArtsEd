/**
 * When a device asks whether the sign-in of its place still holds
 * (composables/usePlaceSessionCheck.ts, 2026-09-24).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'

const { auth, push, order } = vi.hoisted(() => {
  const order: string[] = []
  return {
    order,
    auth: {
      user: null as unknown,
      fetchMe: vi.fn(async () => { order.push('fetchMe') }),
      checkPlaceSession: vi.fn(async () => {}),
      dismissEndedPlace: vi.fn(() => { order.push('dismiss') }),
    },
    push: vi.fn(async (to: unknown) => { order.push(`push ${JSON.stringify(to)}`) }),
  }
})
vi.mock('@/stores/labAuth', () => ({ useLabAuthStore: () => auth }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

import { usePlaceSessionCheck, PLACE_CHECK_MS } from '../usePlaceSessionCheck'

let visibility: DocumentVisibilityState = 'visible'
Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility })

let host: ReturnType<typeof mount> | undefined
let api: ReturnType<typeof usePlaceSessionCheck>

function mountHost() {
  const Host = defineComponent({
    setup() {
      api = usePlaceSessionCheck()
      return () => null
    },
  })
  host = mount(Host)
}

function toFront(state: DocumentVisibilityState) {
  visibility = state
  document.dispatchEvent(new Event('visibilitychange'))
}

beforeEach(() => {
  vi.useFakeTimers()
  visibility = 'visible'
  auth.user = { role: 'participant' }
  order.length = 0
  auth.fetchMe.mockClear()
  auth.checkPlaceSession.mockClear()
  auth.dismissEndedPlace.mockClear()
  push.mockClear()
})

afterEach(() => {
  host?.unmount()
  host = undefined
  vi.useRealTimers()
})

describe('usePlaceSessionCheck', () => {
  it('restores the session at the start where none is known', () => {
    auth.user = null
    mountHost()
    expect(auth.fetchMe).toHaveBeenCalledTimes(1)
    host!.unmount()
    auth.user = { role: 'participant' }
    mountHost()
    expect(auth.fetchMe).toHaveBeenCalledTimes(1)
  })

  it('asks every 30 seconds while the window is in front, even while a question is out', () => {
    expect(PLACE_CHECK_MS).toBe(30_000)
    mountHost()
    vi.advanceTimersByTime(PLACE_CHECK_MS)
    expect(auth.checkPlaceSession).toHaveBeenCalledTimes(1)
    expect(auth.checkPlaceSession).toHaveBeenLastCalledWith(true)
    vi.advanceTimersByTime(PLACE_CHECK_MS)
    expect(auth.checkPlaceSession).toHaveBeenCalledTimes(2)
    visibility = 'hidden'
    vi.advanceTimersByTime(3 * PLACE_CHECK_MS)
    expect(auth.checkPlaceSession).toHaveBeenCalledTimes(2)
  })

  it('asks at once when the window comes back to the front', () => {
    mountHost()
    toFront('hidden')
    expect(auth.checkPlaceSession).not.toHaveBeenCalled()
    toFront('visible')
    expect(auth.checkPlaceSession).toHaveBeenCalledTimes(1)
    expect(auth.checkPlaceSession).toHaveBeenLastCalledWith()
    window.dispatchEvent(new Event('focus'))
    expect(auth.checkPlaceSession).toHaveBeenCalledTimes(2)
    expect(auth.checkPlaceSession).toHaveBeenLastCalledWith()
  })

  it('asks no more once the page is gone', () => {
    mountHost()
    host!.unmount()
    host = undefined
    vi.advanceTimersByTime(2 * PLACE_CHECK_MS)
    toFront('visible')
    window.dispatchEvent(new Event('focus'))
    expect(auth.checkPlaceSession).not.toHaveBeenCalled()
  })

  it('"Sign in" closes the row, takes over what the server says, and then opens the login', async () => {
    mountHost()
    let answer!: () => void
    auth.fetchMe.mockImplementationOnce(
      () => new Promise<void>((resolve) => { answer = () => { order.push('fetchMe'); resolve() } }),
    )
    const done = api.signInAgain()
    await Promise.resolve()
    expect(order).toEqual(['dismiss'])
    expect(push).not.toHaveBeenCalled()
    answer()
    await done
    expect(order).toEqual(['dismiss', 'fetchMe', 'push {"name":"login"}'])
  })
})
