/**
 * The course a leader or an admin works in, chosen in the sign-in field of
 * the header (stores/labAuth.ts, `chooseCourse`, 2026-11-14): the server holds
 * the choice, and the page follows its answer.
 */
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const fetchLevel = vi.fn(async () => {})
vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../safetyLevel', () => ({ useSafetyLevelStore: () => ({ fetchLevel }) }))
vi.mock('@/composables/useCrossmodalPicture', () => ({ clearCrossmodalPicture: vi.fn() }))

import axios from 'axios'
import { useLabAuthStore } from '../labAuth'

const get = axios.get as unknown as Mock
const post = axios.post as unknown as Mock

const educator = {
  id: 8, role: 'educator', display_name: '', identifier: '', locale: 'en', is_active: true,
}
const inCourse = (id: number, name: string) =>
  ({ data: { user: educator, course_id: id, course: { id, name }, place: null } })
const ownUse = { data: { user: educator, course_id: null, course: null, place: null } }

beforeEach(() => {
  localStorage.clear()
  get.mockReset()
  post.mockReset()
  fetchLevel.mockClear()
  setActivePinia(createPinia())
})

describe('chooseCourse', () => {
  it('takes the course the server answers with, and the gate follows', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(ownUse)
    await auth.fetchMe()
    post.mockResolvedValueOnce(inCourse(4, 'Klasse 7b'))
    expect(await auth.chooseCourse(4)).toBeNull()
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/active-course'), { course_id: 4 }, { withCredentials: true })
    expect(auth.activeCourseId).toBe(4)
    expect(auth.course).toEqual({ id: 4, name: 'Klasse 7b' })
    expect(fetchLevel).toHaveBeenCalledTimes(1)
  })

  it('returns to the own use', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(inCourse(4, 'Klasse 7b'))
    await auth.fetchMe()
    post.mockResolvedValueOnce(ownUse)
    expect(await auth.chooseCourse(null)).toBeNull()
    expect(auth.activeCourseId).toBeNull()
    expect(auth.course).toBeNull()
  })

  it('changes nothing where the server refuses, and names the cause', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(inCourse(4, 'Klasse 7b'))
    await auth.fetchMe()
    fetchLevel.mockClear()
    post.mockRejectedValueOnce(
      Object.assign(new Error('403'), { response: { status: 403, data: { error: 'Forbidden' } } }))
    expect(await auth.chooseCourse(5)).toBe('Forbidden')
    expect(auth.activeCourseId).toBe(4)
    expect(auth.course).toEqual({ id: 4, name: 'Klasse 7b' })
    expect(fetchLevel).not.toHaveBeenCalled()
  })
})

describe('fetchMe', () => {
  it('reads the session once the gate refused the choice for want of a sign-in', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(inCourse(4, 'Klasse 7b'))
    await auth.fetchMe()
    post.mockRejectedValueOnce(Object.assign(new Error('401'),
      { response: { status: 401, data: { error: 'sign_in_required' } } }))
    get.mockResolvedValueOnce({ data: { user: null, course_id: null, course: null, place: null } })
    expect(await auth.chooseCourse(5)).toBe('sign_in_required')
    await vi.waitFor(() => expect(auth.user).toBeNull())
    expect(auth.sessionLost).toBe(1)
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('ends a choice the server has ended', async () => {
    localStorage.setItem('ai4artsed.activeCourseId', '4')
    const auth = useLabAuthStore()
    expect(auth.activeCourseId).toBe(4)
    get.mockResolvedValueOnce(ownUse)
    await auth.fetchMe()
    expect(auth.activeCourseId).toBeNull()
    expect(auth.course).toBeNull()
  })
})

describe('fetchMe and what watches the account', () => {
  it('leaves the account and the course as they are where the answer names the same', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(inCourse(4, 'Klasse 7b'))
    await auth.fetchMe()
    const account = auth.user
    const course = auth.course
    get.mockResolvedValueOnce(inCourse(4, 'Klasse 7b'))
    await auth.fetchMe()
    expect(auth.user).toBe(account)
    expect(auth.course).toBe(course)
  })
})

describe('checkLeaderSession', () => {
  it('shows the course the server holds, where an answer took the choice back', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(ownUse)
    await auth.fetchMe()
    post.mockResolvedValueOnce(inCourse(4, 'Klasse 7b'))
    await auth.chooseCourse(4)
    fetchLevel.mockClear()
    get.mockResolvedValueOnce(ownUse)
    await auth.checkLeaderSession(true)
    expect(auth.activeCourseId).toBeNull()
    expect(auth.course).toBeNull()
    expect(fetchLevel).toHaveBeenCalledTimes(1)
  })

  it('asks nothing for a device that is no leader', async () => {
    const auth = useLabAuthStore()
    await auth.checkLeaderSession(true)
    expect(get).not.toHaveBeenCalled()
  })
})

describe('chooseCourse and a sign-out', () => {
  it('signs out only after a choice that is out has come back', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(ownUse)
    await auth.fetchMe()
    let answer!: (value: unknown) => void
    post.mockReturnValueOnce(new Promise((r) => { answer = r }))
    const choice = auth.chooseCourse(4)
    post.mockResolvedValueOnce({ data: { success: true } })
    const out = auth.logout()
    await Promise.resolve()
    expect(post).toHaveBeenCalledTimes(1)
    answer(inCourse(4, 'Klasse 7b'))
    expect(await choice).toBeNull()
    await out
    expect(post).toHaveBeenCalledTimes(2)
    expect(post.mock.calls[1]?.[0]).toContain('/api/auth/logout')
    expect(auth.user).toBeNull()
    expect(auth.activeCourseId).toBeNull()
    expect(auth.course).toBeNull()
  })

  it('names the status where the answer is no answer of the server', async () => {
    const auth = useLabAuthStore()
    get.mockResolvedValueOnce(ownUse)
    await auth.fetchMe()
    post.mockResolvedValueOnce({ status: 200, headers: { 'content-type': 'text/html' }, data: '<!doctype html>' })
    expect(await auth.chooseCourse(4)).toBe('HTTP 200 text/html')
    expect(auth.activeCourseId).toBeNull()
  })
})
