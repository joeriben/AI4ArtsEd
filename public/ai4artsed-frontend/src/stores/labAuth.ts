/**
 * Pinia auth store for the Lab user/course system (Phase 0).
 *
 * Mirrors the existing store style (defineStore setup-form, refs, computed) and
 * reuses cookie-based sessions. In dev the frontend is cross-origin
 * (5173 -> 17802), so the auth calls use `withCredentials` + the one
 * `apiBase()` of services/labApi.ts, as the rest of the app does.
 *
 * `activeCourseId` is set by the server: a participant is pinned to one course
 * for the session, an educator adopts the server's selection. It is mirrored to
 * localStorage so a reload keeps the scope. There is no UI that picks a course.
 */
import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'
import { useSafetyLevelStore } from './safetyLevel'
import { clearCrossmodalPicture } from '@/composables/useCrossmodalPicture'
import axios from 'axios'
import { apiBase } from '@/services/labApi'

export type Role = 'admin' | 'educator' | 'participant'

export interface AuthUser {
  id: number
  role: Role
  display_name: string
  identifier: string
  locale: string
  is_active: boolean
}

const ACTIVE_COURSE_KEY = 'ai4artsed.activeCourseId'

/** An answer of /api/auth/me: the account, and for a place its course and number. */
type MeAnswer = { user: AuthUser | null; [k: string]: any }

/** Whether a body is an answer of /api/auth/me: an object with a `user`. */
function isMeAnswer(data: unknown): data is MeAnswer {
  return typeof data === 'object' && data !== null && 'user' in data
}

/** Read the persisted active-course id from localStorage (null = presets only). */
function loadActiveCourseId(): number | null {
  try {
    const raw = localStorage.getItem(ACTIVE_COURSE_KEY)
    if (raw === null || raw === '' || raw === 'null') return null
    const n = Number(raw)
    return Number.isFinite(n) ? n : null
  } catch {
    return null
  }
}

export const useLabAuthStore = defineStore('labAuth', () => {
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  /** Seconds until the next code may be tried, with `too_many_attempts`. */
  const retryAfter = ref<number | null>(null)
  /** The number of the place this device entered with; null for everyone else. */
  const place = ref<number | null>(null)
  /** The place whose sign-in the server ended while this page stood open
   *  (`checkPlaceSession`); components/PlaceSignInEnded.vue says so until
   *  the row is closed. */
  const endedPlace = ref<number | null>(null)

  // What `checkPlaceSession` weighs an answer against, kept out of the view.
  // `sessions` counts every change of the session on this page: an answer to a
  // question sent before one belongs to the session before it.
  let sessions = 0
  /** The end of this device's sign-in is known; nothing more is asked. */
  let placeEnded = false
  /** The last answer could not read the session; the next check asks for it. */
  let sessionUnknown = false
  /** Sign-ins and sign-outs under way; nothing is asked meanwhile. */
  let signing = 0
  /** The questions to /api/auth/me that are out. */
  const questions = new Set<AbortController>()
  let placeCheck: Promise<void> | null = null

  // v2: explicit active-course selection (decision 1) — client-side only in P0.
  const activeCourseId = ref<number | null>(loadActiveCourseId())

  const isAuthenticated = computed(() => user.value !== null)
  const role = computed<Role | null>(() => user.value?.role ?? null)
  const isAdmin = computed(() => role.value === 'admin')
  const isEducator = computed(() => role.value === 'educator' || role.value === 'admin')
  const isParticipant = computed(() => role.value === 'participant')

  /** True when no course is active -> resolver uses PRESET styles only (P3). */

  // Persist the active-course selection across reloads.
  watch(activeCourseId, (id) => {
    try {
      if (id === null) localStorage.removeItem(ACTIVE_COURSE_KEY)
      else localStorage.setItem(ACTIVE_COURSE_KEY, String(id))
    } catch {
      /* localStorage unavailable (private mode) — selection is in-memory only. */
    }
  })

  /**
   * A participant's material goes when the participant does.
   *
   * The Crossmodal Lab's two picture instruments share ONE uploaded photograph
   * for the length of the tab (composables/useCrossmodalPicture.ts), which is
   * what lets the same picture be read twice. A workshop machine is handed on
   * between participants, and nothing put that picture away: the next
   * participant found the last one's photograph standing in the field, with
   * ImageBind Guidance's trigger live on it (2026-09-05). A change of course is
   * a change of group even where the sign-in did not change.
   */
  watch(activeCourseId, () => {
    clearCrossmodalPicture()
  })

  /** Explicitly pick the active course, or null for "no course / presets only". */
  function setActiveCourse(id: number | null): void {
    activeCourseId.value = id
  }

  /** One question to /api/auth/me: its answer; `unknown` where the answer
   *  does not read the session (the request failed, the body is no answer of
   *  /api/auth/me, or the server could not check the place session and says
   *  `unverified`); `stale` where a sign-in or a sign-out on this page came
   *  between. While one is under way nothing is asked. */
  async function askMe(): Promise<MeAnswer | 'unknown' | 'stale'> {
    if (signing > 0) return 'stale'
    const asked = sessions
    const question = new AbortController()
    questions.add(question)
    let data: unknown
    try {
      ({ data } = await axios.get(`${apiBase()}/api/auth/me`, {
        withCredentials: true,
        signal: question.signal,
      }))
    } catch {
      data = undefined
    } finally {
      questions.delete(question)
    }
    if (asked !== sessions) return 'stale'
    return isMeAnswer(data) && !data.unverified ? data : 'unknown'
  }

  /** Call once on app init to restore a server session.
   *  P1: /api/auth/me now also returns the session's course_id (a participant's
   *  fixed binding, or the educator's chosen active course). A participant is
   *  server-pinned to exactly one course, so we honour the server value.
   *  An answer that could not read the session changes nothing, and the next
   *  check asks again; one to a question sent before a sign-in or a sign-out
   *  on this page is dropped (2026-09-24). */
  async function fetchMe(): Promise<void> {
    const data = await askMe()
    if (data === 'stale') return
    if (data === 'unknown') {
      sessionUnknown = true
      return
    }
    sessions++
    sessionUnknown = false
    user.value = data.user
    place.value = data.user?.role === 'participant' ? (data.place ?? null) : null
    if (!data.user) {
      // No session, no course. A place session ends on the server when its
      // course closes or its code is replaced; the course it was bound to
      // must not stay behind in this browser as the active scope.
      activeCourseId.value = null
    } else {
      placeEnded = false
      endedPlace.value = null
      if (typeof data.course_id !== 'undefined') {
        const serverCid: number | null = data.course_id
        if (data.user.role === 'participant') {
          activeCourseId.value = serverCid                 // fixed binding
        } else if (serverCid !== null) {
          activeCourseId.value = serverCid                 // educator: adopt server selection
        }
      }
    }
  }

  /** Whether the server still holds this device's place (2026-09-24). The
   *  server ends the sign-in when the place's code is replaced or its access
   *  ended, when the course closes (its access window ends, it is archived or
   *  deleted), and when the account is no longer an active participant
   *  (lab/auth_service.py); a sign-in or a sign-out in another tab of this
   *  browser ends it for this page as well. The page learns it here. It only
   *  records the end: the page stays as it is, and
   *  components/PlaceSignInEnded.vue says so.
   *
   *  A page that knows no place and could not read its session asks for the
   *  session here. One question is out at a time; with `again`, as the
   *  interval asks, one goes out even while another is out, so that a
   *  question that never comes back holds none after it. */
  function checkPlaceSession(again = false): Promise<void> {
    if (placeEnded) return Promise.resolve()
    const knows = isParticipant.value && place.value !== null
    if (!knows && !sessionUnknown) return Promise.resolve()
    if (placeCheck !== null && !again) return placeCheck
    const check: Promise<void> = (knows ? askPlace() : fetchMe()).finally(() => {
      if (placeCheck === check) placeCheck = null
    })
    placeCheck = check
    return check
  }

  /** The sign-in holds while the server answers with the same account at the
   *  same place: every place has an account of its own, and every course
   *  numbers its places from 1. */
  async function askPlace(): Promise<void> {
    const was = user.value
    const at = place.value
    const data = await askMe()
    if (data === 'stale' || data === 'unknown') return
    if (data.user?.role === 'participant' && data.user.id === was?.id && data.place === at) return
    placeEnded = true
    endedPlace.value = at
  }

  /** "Close" on the row: the row goes, and the page stays as it is. */
  function dismissEndedPlace(): void {
    endedPlace.value = null
  }

  /** Before a sign-in or a sign-out goes out, the questions still out are
   *  called off, and what they bring belongs to the session before. Flask
   *  sets the cookie of a permanent session again with every answer, from
   *  the session the request carried: an answer that came in after the
   *  sign-in or the sign-out would put the session before back into this
   *  browser. */
  function beginSigning(): void {
    signing++
    sessions++
    for (const question of questions) question.abort()
  }

  /** A sign-in or a sign-out on this page has come back: a new session, at `at`. */
  function newSession(at: number | null): void {
    sessions++
    sessionUnknown = false
    placeEnded = false
    endedPlace.value = null
    place.value = at
  }

  async function login(identifier: string, password: string): Promise<boolean> {
    loading.value = true
    error.value = null
    beginSigning()
    try {
      const { data } = await axios.post(
        `${apiBase()}/api/auth/login`,
        { identifier, password },
        { withCredentials: true },
      )
      user.value = data.user
      newSession(null)
      // The server drops the course of whatever session this browser held,
      // a place session included (auth_service.login_user), and with it that
      // course's safety level; the scope and the gate here follow it. A
      // leader chooses a course afterwards (Entscheid 1).
      setActiveCourse(null)
      await useSafetyLevelStore().fetchLevel()
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error ?? 'Login failed'
      // A refused sign-in leaves the session as it was, on the server and
      // here; where no answer came, the next check reads it again.
      sessionUnknown = true
      return false
    } finally {
      loading.value = false
      signing--
    }
  }

  /** Participant entry (2026-09-23): a device enters with the code of one of
   *  its course's places. On success the server pins the session to that one
   *  course; we mirror it into activeCourseId so the whole app is scoped to that
   *  course. A refused code leaves the server's reason in `error`
   *  (`invalid_code`, `access_closed`, `too_many_attempts` with the wait in
   *  `retryAfter`), which the login view puts into words. */
  async function participantLogin(code: string): Promise<boolean> {
    loading.value = true
    error.value = null
    retryAfter.value = null
    beginSigning()
    try {
      const { data } = await axios.post(
        `${apiBase()}/api/auth/participant-login`,
        { code },
        { withCredentials: true },
      )
      user.value = data.user
      newSession(data.place ?? null)
      if (data.course?.id != null) activeCourseId.value = data.course.id
      // The server has just pinned the session to this course, and the course
      // may enforce a stricter safety level than the installation. The gating
      // store read the level at app boot, before any of this — without a
      // refetch the interface would keep offering what the course forbids.
      await useSafetyLevelStore().fetchLevel()
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error ?? e?.message ?? 'Sign-in failed'
      // `too_many_attempts` (429) carries the seconds until the next attempt.
      const wait = Number(e?.response?.data?.retry_after ?? e?.response?.headers?.['retry-after'])
      retryAfter.value = Number.isFinite(wait) && wait > 0 ? Math.ceil(wait) : null
      // As with a refused leader sign-in: the session stays as it was.
      sessionUnknown = true
      return false
    } finally {
      loading.value = false
      signing--
    }
  }

  async function logout(): Promise<void> {
    beginSigning()
    try {
      await axios.post(`${apiBase()}/api/auth/logout`, {}, { withCredentials: true })
    } catch {
      /* ignore — clear client state regardless */
    } finally {
      signing--
    }
    user.value = null
    newSession(null)
    // What this participant brought with them goes with them — see the watch
    // above; said here as well, because a sign-out with no course active
    // changes nothing for that watch to answer.
    clearCrossmodalPicture()
    // Forget the active course on logout — the next user picks their own.
    setActiveCourse(null)
    // The course binding is gone; the gate must follow it back up.
    await useSafetyLevelStore().fetchLevel()
  }

  return {
    user, loading, error, retryAfter, place, endedPlace,
    activeCourseId,
    isAuthenticated, role, isAdmin, isEducator, isParticipant,
    setActiveCourse,
    fetchMe, login, participantLogin, logout, checkPlaceSession, dismissEndedPlace,
  }
})
