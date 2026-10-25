/**
 * The check whether the sign-in of this device's place still holds
 * (stores/labAuth.ts, `checkPlaceSession`, 2026-09-24).
 */
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../safetyLevel', () => ({
  useSafetyLevelStore: () => ({ fetchLevel: vi.fn(async () => {}) }),
}))
vi.mock('@/composables/useCrossmodalPicture', () => ({ clearCrossmodalPicture: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

import axios from 'axios'
import { useLabAuthStore } from '../labAuth'
import { usePlaceSessionCheck, PLACE_CHECK_MS } from '@/composables/usePlaceSessionCheck'

type Auth = ReturnType<typeof useLabAuthStore>

const get = axios.get as unknown as Mock
const post = axios.post as unknown as Mock

const participant = {
  id: 7, role: 'participant', display_name: '', identifier: '', locale: 'en', is_active: true,
}
const educator = { ...participant, id: 8, role: 'educator' }
const atPlace = (n: number) => ({ data: { user: participant, course_id: 4, place: n } })
const signedOut = { data: { user: null, course_id: null, place: null } }
const unverified = { data: { ...signedOut.data, unverified: true } }
const refused = (error: string) =>
  Object.assign(new Error(error), { response: { status: 401, data: { error } } })

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((r, j) => { resolve = r; reject = j })
  return { promise, resolve, reject }
}

async function enteredAt(n: number) {
  post.mockResolvedValueOnce({ data: { user: participant, course: { id: 4 }, place: n } })
  const auth = useLabAuthStore()
  expect(await auth.participantLogin('ACDEF')).toBe(true)
  return auth
}

/** What the page holds of its session. */
const seen = (auth: Auth) => ({
  user: auth.user, place: auth.place, course: auth.activeCourseId, endedPlace: auth.endedPlace,
})

Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' })

beforeEach(() => {
  localStorage.clear()
  get.mockReset()
  post.mockReset()
  setActivePinia(createPinia())
})

describe('checkPlaceSession', () => {
  it('records the end of the sign-in and leaves the page as it is', async () => {
    const auth = await enteredAt(3)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    expect(seen(auth)).toEqual({ user: participant, place: 3, course: 4, endedPlace: 3 })
  })

  it('asks no more once the end is known, and after "Close" neither', async () => {
    const auth = await enteredAt(3)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    await auth.checkPlaceSession(true)
    auth.dismissEndedPlace()
    await auth.checkPlaceSession(true)
    expect(get).toHaveBeenCalledTimes(1)
    expect(auth.endedPlace).toBeNull()
    expect(auth.user).toEqual(participant)
  })

  it('changes nothing where the sign-in holds, and asks again next time', async () => {
    const auth = await enteredAt(3)
    get.mockResolvedValue(atPlace(3))
    await auth.checkPlaceSession()
    await auth.checkPlaceSession()
    expect(get).toHaveBeenCalledTimes(2)
    expect(auth.endedPlace).toBeNull()
  })

  it('reads another place, another account, or a leader in this browser as the end', async () => {
    const answers = [
      atPlace(5),
      // place 3 of another course: every course numbers its places from 1
      { data: { user: { ...participant, id: 12 }, course_id: 9, place: 3 } },
      { data: { user: educator, course_id: null, place: null } },
    ]
    for (const answer of answers) {
      setActivePinia(createPinia())
      const auth = await enteredAt(3)
      get.mockResolvedValueOnce(answer)
      await auth.checkPlaceSession()
      expect(seen(auth)).toEqual({ user: participant, place: 3, course: 4, endedPlace: 3 })
    }
  })

  it('takes nothing from an unchecked session, a body that is no answer, or a failed request', async () => {
    const auth = await enteredAt(3)
    get.mockResolvedValueOnce(unverified)
    await auth.checkPlaceSession()
    get.mockResolvedValueOnce({ data: '<!doctype html>' })
    await auth.checkPlaceSession()
    get.mockResolvedValueOnce({ data: { error: 'maintenance' } })
    await auth.checkPlaceSession()
    get.mockRejectedValueOnce(new Error('Network Error'))
    await auth.checkPlaceSession()
    expect(auth.endedPlace).toBeNull()
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    expect(get).toHaveBeenCalledTimes(5)
    expect(auth.endedPlace).toBe(3)
  })

  it('sends one request while a check is under way', async () => {
    const auth = await enteredAt(3)
    const late = deferred<ReturnType<typeof atPlace>>()
    get.mockReturnValueOnce(late.promise)
    const first = auth.checkPlaceSession()
    const second = auth.checkPlaceSession()
    late.resolve(atPlace(3))
    await Promise.all([first, second])
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('asks anew on time while a question never comes back', async () => {
    const auth = await enteredAt(3)
    get.mockReturnValueOnce(new Promise(() => {}))
    void auth.checkPlaceSession()
    void auth.checkPlaceSession()
    expect(get).toHaveBeenCalledTimes(1)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession(true)
    expect(get).toHaveBeenCalledTimes(2)
    expect(auth.endedPlace).toBe(3)
  })

  it('keeps one question out where a slow one settles behind a later one', async () => {
    const auth = await enteredAt(3)
    const slow = deferred<ReturnType<typeof atPlace>>()
    const later = deferred<ReturnType<typeof atPlace>>()
    get.mockReturnValueOnce(slow.promise).mockReturnValueOnce(later.promise)
    const first = auth.checkPlaceSession()
    const second = auth.checkPlaceSession(true)
    slow.resolve(atPlace(3))
    await first
    const third = auth.checkPlaceSession()
    expect(get).toHaveBeenCalledTimes(2)
    later.resolve(atPlace(3))
    await Promise.all([second, third])
  })

  it('sends one request while a restore is under way', async () => {
    const auth = useLabAuthStore()
    get.mockRejectedValueOnce(new Error('Network Error'))
    await auth.fetchMe()
    const late = deferred<ReturnType<typeof atPlace>>()
    get.mockReturnValueOnce(late.promise)
    const first = auth.checkPlaceSession()
    const second = auth.checkPlaceSession()
    late.resolve(atPlace(3))
    await Promise.all([first, second])
    expect(get).toHaveBeenCalledTimes(2)
    expect(auth.place).toBe(3)
  })

  it('asks nothing for a device that is no participant', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(signedOut)
    await auth.fetchMe()
    await auth.checkPlaceSession(true)
    post.mockResolvedValueOnce({ data: { user: educator } })
    await auth.login('edu@example.org', 'secret12')
    await auth.checkPlaceSession(true)
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('closes the row at a new sign-in and asks again for it', async () => {
    const auth = await enteredAt(3)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    expect(auth.endedPlace).toBe(3)
    await enteredAt(3)
    expect(auth.endedPlace).toBeNull()
    get.mockResolvedValueOnce(atPlace(3))
    await auth.checkPlaceSession()
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('asks again once "Sign in" finds the device signed in', async () => {
    const auth = await enteredAt(3)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    auth.dismissEndedPlace()
    get.mockResolvedValueOnce(atPlace(3))        // signed in again in another tab
    await auth.fetchMe()
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    expect(auth.endedPlace).toBe(3)
  })

  it('drops an answer that comes in after the page took over what the server says', async () => {
    const auth = await enteredAt(3)
    const late = deferred<typeof signedOut>()
    get.mockReturnValueOnce(late.promise)
    const slow = auth.checkPlaceSession()
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession(true)
    expect(auth.endedPlace).toBe(3)
    auth.dismissEndedPlace()
    get.mockResolvedValueOnce(signedOut)
    await auth.fetchMe()                         // "Sign in" takes over the server's answer
    late.resolve(signedOut)
    await slow
    expect(seen(auth)).toEqual({ user: null, place: null, course: null, endedPlace: null })
  })
})

describe('a sign-in or a sign-out on this page', () => {
  it.each([
    ['a sign-out', (auth: Auth) => auth.logout()],
    ['a code', (auth: Auth) => auth.participantLogin('ACDEG')],
    ['a leader', (auth: Auth) => auth.login('edu@example.org', 'secret12')],
  ])('%s calls off the questions out and asks nothing while it is under way', async (_, sign) => {
    const auth = await enteredAt(3)
    get.mockReturnValueOnce(new Promise(() => {}))
    void auth.checkPlaceSession()
    const { signal } = get.mock.calls[0]![1] as { signal: AbortSignal }
    const answered = deferred<{ data: unknown }>()
    post.mockReturnValueOnce(answered.promise)
    const out = sign(auth)
    expect(signal.aborted).toBe(true)
    await auth.checkPlaceSession(true)
    await auth.fetchMe()
    expect(get).toHaveBeenCalledTimes(1)
    answered.resolve({ data: { success: true, user: participant, course: { id: 4 }, place: 5 } })
    await out
  })

  it('shows no row while a sign-in is under way, for an answer in before it began', async () => {
    const auth = await enteredAt(3)
    const late = deferred<typeof signedOut>()
    get.mockReturnValueOnce(late.promise)
    const check = auth.checkPlaceSession()
    const answered = deferred<{ data: unknown }>()
    post.mockReturnValueOnce(answered.promise)
    late.resolve(signedOut)                      // in, and not yet read
    const signing = auth.participantLogin('ACDEG')
    await check
    expect(auth.endedPlace).toBeNull()
    answered.resolve({ data: { user: participant, course: { id: 4 }, place: 5 } })
    expect(await signing).toBe(true)
    expect(seen(auth)).toEqual({ user: participant, place: 5, course: 4, endedPlace: null })
  })

  it.each([
    ['a sign-out', (auth: Auth) => {
      post.mockResolvedValueOnce({ data: { success: true } })
      return auth.logout()
    }],
    ['a refused code', (auth: Auth) => {
      post.mockRejectedValueOnce(refused('invalid_code'))
      return auth.participantLogin('ZZZZZ')
    }],
    ['a leader', (auth: Auth) => {
      post.mockResolvedValueOnce({ data: { user: educator } })
      return auth.login('edu@example.org', 'secret12')
    }],
  ])('asks again after %s and a new code on this page', async (_, sign) => {
    const auth = await enteredAt(3)
    await sign(auth)
    await enteredAt(5)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    expect(get).toHaveBeenCalledTimes(1)
    expect(auth.endedPlace).toBe(5)
  })

  it('drops the answer to a check sent before a new sign-in', async () => {
    const auth = await enteredAt(3)
    const late = deferred<typeof signedOut>()
    get.mockReturnValueOnce(late.promise)
    const check = auth.checkPlaceSession()
    post.mockResolvedValueOnce({ data: { user: participant, course: { id: 4 }, place: 5 } })
    await auth.participantLogin('ACDEG')
    late.resolve(signedOut)
    await check
    expect(seen(auth)).toEqual({ user: participant, place: 5, course: 4, endedPlace: null })
  })

  it('drops the answer to a restore sent before a sign-in', async () => {
    const auth = useLabAuthStore()
    get.mockRejectedValueOnce(new Error('Network Error'))
    await auth.fetchMe()
    const late = deferred<typeof signedOut>()
    get.mockReturnValueOnce(late.promise)
    const check = auth.checkPlaceSession()
    post.mockResolvedValueOnce({ data: { user: participant, course: { id: 4 }, place: 5 } })
    await auth.participantLogin('ACDEG')
    late.resolve(signedOut)
    await check
    expect(seen(auth)).toEqual({ user: participant, place: 5, course: 4, endedPlace: null })
  })

  it('drops the answer to the first question of the page sent before a sign-in', async () => {
    const auth = useLabAuthStore()
    const late = deferred<typeof signedOut>()
    get.mockReturnValueOnce(late.promise)
    const start = auth.fetchMe()
    post.mockResolvedValueOnce({ data: { user: participant, course: { id: 4 }, place: 2 } })
    await auth.participantLogin('ACDEF')
    late.resolve(signedOut)
    await start
    expect(seen(auth)).toEqual({ user: participant, place: 2, course: 4, endedPlace: null })
  })

  it('drops the answer to a check sent before a sign-out, and shows no row after it', async () => {
    const auth = await enteredAt(3)
    const late = deferred<ReturnType<typeof atPlace>>()
    get.mockReturnValueOnce(late.promise)
    const check = auth.checkPlaceSession()
    post.mockResolvedValueOnce({ data: { success: true } })
    await auth.logout()
    late.resolve(atPlace(3))
    await check
    await auth.checkPlaceSession(true)
    expect(get).toHaveBeenCalledTimes(1)
    expect(seen(auth)).toEqual({ user: null, place: null, course: null, endedPlace: null })
  })

  it('closes the row at a sign-out and at a leader sign-in on this device', async () => {
    let auth = await enteredAt(3)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    post.mockResolvedValueOnce({ data: { success: true } })
    await auth.logout()
    expect(seen(auth)).toEqual({ user: null, place: null, course: null, endedPlace: null })

    setActivePinia(createPinia())
    auth = await enteredAt(3)
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    post.mockResolvedValueOnce({ data: { user: educator } })
    await auth.login('edu@example.org', 'secret12')
    expect(seen(auth)).toEqual({ user: educator, place: null, course: null, endedPlace: null })
  })

  it('asks nothing after a sign-out, where a restore had failed before the sign-in', async () => {
    const auth = useLabAuthStore()
    get.mockRejectedValueOnce(new Error('Network Error'))
    await auth.fetchMe()
    await enteredAt(3)
    post.mockResolvedValueOnce({ data: { success: true } })
    await auth.logout()
    await auth.checkPlaceSession(true)
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('a refused code or password changes nothing on the page', async () => {
    const auth = await enteredAt(3)
    post.mockRejectedValueOnce(refused('invalid_code'))
    expect(await auth.participantLogin('ZZZZZ')).toBe(false)
    post.mockRejectedValueOnce(refused('invalid credentials'))
    expect(await auth.login('edu@example.org', 'wrong')).toBe(false)
    expect(seen(auth)).toEqual({ user: participant, place: 3, course: 4, endedPlace: null })
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    expect(auth.endedPlace).toBe(3)
  })

  it('reads the session anew where a sign-in got no answer', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(signedOut)
    await auth.fetchMe()
    post.mockRejectedValueOnce(new Error('Network Error'))
    expect(await auth.participantLogin('ACDEF')).toBe(false)
    get.mockResolvedValueOnce(atPlace(2))       // the server did sign it in
    await auth.checkPlaceSession()
    expect(seen(auth)).toEqual({ user: participant, place: 2, course: 4, endedPlace: null })
  })
})

describe('a page that knows its place', () => {
  it.each(['unverified', 'failed'])(
    'reads the end where a later start question came back %s',
    async (how) => {
      const auth = useLabAuthStore()
      const first = deferred<ReturnType<typeof atPlace>>()
      const later = deferred<unknown>()
      get.mockReturnValueOnce(first.promise).mockReturnValueOnce(later.promise)
      const a = auth.fetchMe()
      const b = auth.fetchMe()
      first.resolve(atPlace(3))
      await a
      if (how === 'failed') later.reject(new Error('Network Error'))
      else later.resolve(unverified)
      await b
      get.mockResolvedValueOnce(signedOut)
      await auth.checkPlaceSession()
      expect(seen(auth)).toEqual({ user: participant, place: 3, course: 4, endedPlace: 3 })
    },
  )

  it('reads the end after a restore that failed while the device signed in', async () => {
    const auth = useLabAuthStore()
    get.mockRejectedValueOnce(new Error('Network Error'))
    await auth.fetchMe()
    const late = deferred<never>()
    get.mockReturnValueOnce(late.promise)
    const check = auth.checkPlaceSession()
    post.mockResolvedValueOnce({ data: { user: participant, course: { id: 4 }, place: 5 } })
    await auth.participantLogin('ACDEG')
    late.reject(new Error('Network Error'))
    await check
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    expect(seen(auth)).toEqual({ user: participant, place: 5, course: 4, endedPlace: 5 })
  })

  it('asks nothing after "Close", whatever a start question brings later', async () => {
    const auth = useLabAuthStore()
    const first = deferred<ReturnType<typeof atPlace>>()
    const later = deferred<never>()
    get.mockReturnValueOnce(first.promise).mockReturnValueOnce(later.promise)
    const a = auth.fetchMe()
    const b = auth.fetchMe()
    first.resolve(atPlace(3))
    await a
    get.mockResolvedValueOnce(signedOut)
    await auth.checkPlaceSession()
    auth.dismissEndedPlace()
    later.reject(new Error('Network Error'))
    await b
    get.mockResolvedValue(signedOut)
    await auth.checkPlaceSession(true)
    expect(get).toHaveBeenCalledTimes(3)
    expect(seen(auth)).toEqual({ user: participant, place: 3, course: 4, endedPlace: null })
  })
})

describe('with the interval of usePlaceSessionCheck', () => {
  it('asks again on time after a question that never comes back', async () => {
    vi.useFakeTimers()
    try {
      const auth = await enteredAt(3)
      get.mockReturnValueOnce(new Promise(() => {}))
      const host = mount(defineComponent({ setup() { usePlaceSessionCheck(); return () => null } }))
      await vi.advanceTimersByTimeAsync(PLACE_CHECK_MS)
      expect(get).toHaveBeenCalledTimes(1)
      get.mockResolvedValue(signedOut)
      await vi.advanceTimersByTimeAsync(PLACE_CHECK_MS)
      expect(get).toHaveBeenCalledTimes(2)
      expect(auth.endedPlace).toBe(3)
      host.unmount()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('fetchMe', () => {
  it('keeps the course where the session could not be read, and the next check restores it', async () => {
    localStorage.setItem('ai4artsed.activeCourseId', '4')
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(unverified)
    await auth.fetchMe()
    expect(auth.user).toBeNull()
    expect(auth.activeCourseId).toBe(4)

    get.mockResolvedValueOnce(atPlace(3))
    await auth.checkPlaceSession()
    expect(seen(auth)).toEqual({ user: participant, place: 3, course: 4, endedPlace: null })
  })

  it('takes nothing from a body that is no answer', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce({ data: '<!doctype html>' })
    await auth.fetchMe()
    get.mockResolvedValueOnce({ data: { error: 'maintenance' } })
    await auth.fetchMe()
    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('drops the course where the server holds no session', async () => {
    localStorage.setItem('ai4artsed.activeCourseId', '4')
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(signedOut)
    await auth.fetchMe()
    expect(auth.activeCourseId).toBeNull()
  })
})
