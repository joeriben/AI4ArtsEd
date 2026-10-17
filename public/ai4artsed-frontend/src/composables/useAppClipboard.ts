import { ref } from 'vue'

/**
 * The platform's own hand — one slot, shared by every copy and paste button on
 * the platform. It carries plain text.
 *
 * Until 2026-10-10 it could carry a whole RUN as well, under a marker: the copy
 * button of the favourites' enlargement put one there, and the media input box
 * took it out on paste. That button went on 2026-10-03 (a run is dragged from
 * the favourites straight into a field, composables/useMaterialIntake.ts), and
 * with it the only writer; the channel followed, with its reader.
 *
 * The hand belongs to the PLATFORM, not to one page of it. A slot that is a
 * variable in the open document and nothing else empties on every reload and
 * does not exist for a second tab: copy on one surface, open the next in a
 * new window, press paste — nothing. It is written to `localStorage`
 * instead, which is shared by every tab of this installation and
 * outlives a reload, and a copy made in another tab arrives here through the
 * `storage` event while both stand open. A browser that refuses storage (a
 * private window, site data switched off) keeps the slot for its own page, as
 * before.
 */

const SLOT = 'ai4artsed.clipboard'

function stored(): string {
  try {
    return localStorage.getItem(SLOT) ?? ''
  } catch {
    return ''
  }
}

// Global clipboard state shared across all components, tabs and reloads
const appClipboard = ref(stored())

/** Put something in the hand, for every tab of this installation. */
function hold(text: string) {
  appClipboard.value = text
  try {
    localStorage.setItem(SLOT, text)
  } catch {
    /* storage refused: this page's slot still holds it */
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', e => {
    if (e.key === SLOT) appClipboard.value = e.newValue ?? ''
  })
}

export function useAppClipboard() {
  const copy = (text: string) => {
    hold(text)
  }

  const paste = () => {
    // A run marker left in storage by the channel that went on 2026-10-10 is
    // not text anybody wrote; the hand is empty then.
    return appClipboard.value.startsWith('ai4artsed:run:') ? '' : appClipboard.value
  }

  const clear = () => {
    hold('')
  }

  return {
    appClipboard,
    copy,
    paste,
    clear
  }
}
