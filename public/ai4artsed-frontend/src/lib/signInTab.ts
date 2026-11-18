/**
 * The tab of the sign-in page (views/LoginView.vue) on which the last sign-in
 * on this device was made. The page opens on it, unless the page asked for
 * needs a leader (2026-11-15). Kept in this browser only; without the
 * browser's storage the page opens on its default.
 */
export type SignInTab = 'educator' | 'participant'

const LAST_TAB_KEY = 'ai4artsed.signInTab'

export function lastSignInTab(): SignInTab | null {
  try {
    const kept = window.localStorage.getItem(LAST_TAB_KEY)
    return kept === 'educator' || kept === 'participant' ? kept : null
  } catch {
    return null
  }
}

export function keepSignInTab(which: SignInTab): void {
  try {
    window.localStorage.setItem(LAST_TAB_KEY, which)
  } catch {
    // Without the browser's storage the page opens on its default.
  }
}
