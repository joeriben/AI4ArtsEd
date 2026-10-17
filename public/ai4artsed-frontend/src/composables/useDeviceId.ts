/**
 * Shared device ID composable.
 *
 * Combines a persistent browser identifier with the current date
 * so that the same physical device gets a new identity each day
 * (important for shared classroom iPads where different kids use
 * the same browser on different days).
 */
import { randomId } from '@/lib/randomId'

export function useDeviceId(): string {
  let browserId = localStorage.getItem('browser_id')
  if (!browserId) {
    // Only when there is none. An id already in this browser is read back and
    // never drawn again: favourites, journals and recordings hang on it.
    browserId = randomId()
    localStorage.setItem('browser_id', browserId)
  }
  const today = new Date().toISOString().split('T')[0]
  return `${browserId}_${today}`
}
