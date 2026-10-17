/**
 * Whether the sign-in of this device's place still holds, asked while a page
 * stands open (2026-09-24). The server ends it when the place's code is
 * replaced or its access ended, or when the course closes
 * (lab/auth_service.py); a device learned it only at its next reload. It asks
 * every 30 seconds while its window is in front, and at once when the window
 * comes back to the front (stores/labAuth.ts, `checkPlaceSession`).
 * components/PlaceSignInEnded.vue, in App.vue, shows the row that says so.
 */
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useLabAuthStore } from '@/stores/labAuth'

export const PLACE_CHECK_MS = 30_000

export function usePlaceSessionCheck() {
  const auth = useLabAuthStore()
  const router = useRouter()
  let timer: number | undefined

  /** The window came back to the front: a question already out answers it. */
  function checkInFront(): void {
    if (document.visibilityState === 'visible') void auth.checkPlaceSession()
  }

  /** The interval asks anew, even while a question is out. */
  function checkOnTime(): void {
    if (document.visibilityState === 'visible') void auth.checkPlaceSession(true)
  }

  onMounted(() => {
    // Not every page restores the session: the router does on the lab
    // routes (router/index.ts), the kept perspectives where a page keeps
    // them (stores/keptPerspectives.ts); a device reloaded on another page
    // would not know its place.
    if (auth.user === null) void auth.fetchMe()
    timer = window.setInterval(checkOnTime, PLACE_CHECK_MS)
    document.addEventListener('visibilitychange', checkInFront)
    window.addEventListener('focus', checkInFront)
  })

  onUnmounted(() => {
    window.clearInterval(timer)
    document.removeEventListener('visibilitychange', checkInFront)
    window.removeEventListener('focus', checkInFront)
  })

  /** "Sign in" on the row: the row goes, the store takes over what the server
   *  says now, and the login page opens. */
  async function signInAgain(): Promise<void> {
    auth.dismissEndedPlace()
    await auth.fetchMe()
    await router.push({ name: 'login' })
  }

  return { signInAgain }
}
