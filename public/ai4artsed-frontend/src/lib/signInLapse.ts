/**
 * A request answered 401 `sign_in_required` (devserver/my_app/lab/sign_in_gate.py)
 * means that the sign-in of this browser ended while the page stood open: the
 * code of the place was replaced, the course closed, the account signed out in
 * another tab. The page learns it here and asks the server who is signed in
 * (stores/labAuth.ts, `checkSignIn`); where nobody is, App.vue sends a page
 * that needs a sign-in to the sign-in page. Without this the page learned it
 * only from the check every 30 seconds (composables/usePlaceSessionCheck.ts),
 * and every request until then failed with its raw error.
 *
 * The axios instances report through `watchAxios` (main.ts, services/api.ts,
 * views/TrainingView.vue), the calls of `fetch` through `watchFetch` (main.ts).
 * A stream whose connection failed reports through `suspectSignIn`: an
 * EventSource does not say the status it was refused with.
 */
import type { AxiosInstance } from 'axios'

let listener: (() => void) | null = null

/** Who is told; main.ts sets it once the store exists. */
export function onSignInLapse(fn: (() => void) | null): void {
  listener = fn
}

/** A request may have been refused for want of a sign-in. */
export function suspectSignIn(): void {
  listener?.()
}

/** Whether an answer is the gate's refusal. */
export function isSignInRequired(status: number | undefined, body: unknown): boolean {
  return status === 401
    && typeof body === 'object' && body !== null
    && (body as { error?: unknown }).error === 'sign_in_required'
}

/** Report the gate's refusals of `instance`; the refusal itself goes on to
 *  the caller unchanged. */
export function watchAxios(instance: AxiosInstance): void {
  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (isSignInRequired(error?.response?.status, error?.response?.data)) suspectSignIn()
      return Promise.reject(error)
    },
  )
}

/** Report the gate's refusals of `fetch` on this page (main.ts): the stores
 *  and the views call it in some fifty files besides axios. Every answer goes
 *  on to the caller unchanged; a 401 is read from a copy. */
export function watchFetch(target: { fetch: typeof fetch } = globalThis): void {
  const native = target.fetch.bind(target)
  target.fetch = async (...args: Parameters<typeof fetch>): Promise<Response> => {
    const response = await native(...args)
    if (response.status === 401) {
      response.clone().json()
        .then((body: unknown) => {
          if (isSignInRequired(401, body)) suspectSignIn()
        })
        .catch(() => {
          // A 401 whose body is no JSON is not the gate's.
        })
    }
    return response
  }
}
